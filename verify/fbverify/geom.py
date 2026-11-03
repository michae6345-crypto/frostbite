"""UF2 parsing and mesh measurement (numpy + shapely only, no judgement)."""
from __future__ import annotations

import itertools
import math
import struct

import numpy as np

UF2_MAGIC0, UF2_MAGIC1, UF2_MAGIC_END = 0x0A324655, 0x9E5D5157, 0x0AB16F30
UF2_FLAG_FAMILY = 0x00002000
RP2040_FAMILY = 0xE48BFF56


def parse_uf2(data: bytes) -> dict:
    """Return {ok, errors[], blocks, family_ids, payload_bytes, size}."""
    errs = []
    if len(data) == 0:
        errs.append("file is empty")
    if len(data) % 512:
        errs.append(f"size {len(data)} is not a multiple of 512 (truncated or padded)")
    nblk = len(data) // 512
    fams, payload, declared = set(), 0, set()
    addrs = []
    for i in range(nblk):
        b = data[i * 512:(i + 1) * 512]
        m0, m1, flags, addr, size, bno, ntot, fam = struct.unpack_from("<8I", b, 0)
        (mend,) = struct.unpack_from("<I", b, 508)
        if m0 != UF2_MAGIC0 or m1 != UF2_MAGIC1 or mend != UF2_MAGIC_END:
            errs.append(f"block {i}: bad magic ({m0:#x},{m1:#x},{mend:#x})")
            continue
        if bno != i:
            errs.append(f"block {i}: block number field is {bno}")
        declared.add(ntot)
        if size > 476:
            errs.append(f"block {i}: payload size {size} > 476")
        payload += size
        addrs.append(addr)
        if flags & UF2_FLAG_FAMILY:
            fams.add(fam)
        else:
            errs.append(f"block {i}: familyID flag not set")
    if len(declared) > 1:
        errs.append(f"inconsistent numBlocks fields {sorted(declared)}")
    elif declared and next(iter(declared)) != nblk:
        errs.append(f"numBlocks field says {next(iter(declared))}, file has {nblk} blocks (truncated?)")
    if fams and fams != {RP2040_FAMILY}:
        errs.append("family IDs " + ", ".join(f"{f:#010x}" for f in sorted(fams)) + f" != {RP2040_FAMILY:#010x} (RP2040)")
    if len(data) >= 2 * 1024 * 1024:
        errs.append(f"size {len(data)} >= 2 MB")
    return {"ok": not errs, "errors": errs[:20], "n_errors": len(errs), "blocks": nblk,
            "declared_blocks": sorted(declared), "family_ids": [f"{f:#010x}" for f in sorted(fams)],
            "payload_bytes": payload, "size": len(data),
            "flash_range": [f"{min(addrs):#x}", f"{max(addrs):#x}"] if addrs else None}


# ---------------------------------------------------------------- meshes

def section_polygons(mesh, origin, normal):
    """Planar section of a mesh -> (shapely polygons with depth, to_3d matrix).

    depth 0 = outer boundary, 1 = hole in material, 2 = island ... (even-odd nesting)."""
    import shapely.geometry as g
    import shapely.ops as o
    import trimesh

    normal = np.asarray(normal, float) / np.linalg.norm(normal)
    segs = trimesh.intersections.mesh_plane(mesh, normal, origin)
    if len(segs) == 0:
        return [], None
    # build a 2D frame on the plane
    ref = np.array([1.0, 0, 0]) if abs(normal[0]) < 0.9 else np.array([0, 1.0, 0])
    u = ref - normal * np.dot(ref, normal)
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    o3 = np.asarray(origin, float)
    pts2 = np.stack([np.einsum("ijk,k->ij", segs - o3, u), np.einsum("ijk,k->ij", segs - o3, v)], axis=-1)
    lines = [g.LineString(s) for s in np.round(pts2, 5) if not np.allclose(s[0], s[1])]
    faces = [p for p in o.polygonize(o.unary_union(lines)) if p.area > 1e-6]
    out = []
    shells = [g.Polygon(q.exterior) for q in faces]
    for i, p in enumerate(faces):
        rp = p.representative_point()
        depth = sum(1 for j, q in enumerate(shells) if j != i and q.area > shells[i].area and q.contains(rp))
        out.append({"poly": p, "depth": depth})
    return out, (o3, u, v)


def rect_measure(poly):
    """Min rotated rectangle side lengths and centroid chords along its axes."""
    import shapely.geometry as g
    mrr = poly.minimum_rotated_rectangle
    c = list(mrr.exterior.coords)[:4]
    e1 = np.subtract(c[1], c[0])
    e2 = np.subtract(c[2], c[1])
    l1, l2 = float(np.linalg.norm(e1)), float(np.linalg.norm(e2))
    cen = poly.centroid
    chords = []
    for e in (e1, e2):
        d = e / np.linalg.norm(e) * 100
        ln = g.LineString([(cen.x - d[0], cen.y - d[1]), (cen.x + d[0], cen.y + d[1])])
        chords.append(float(poly.intersection(ln).length))
    return {"sides": sorted([l1, l2]), "chords": sorted(chords), "cx": cen.x, "cy": cen.y,
            "area": poly.area, "circularity": 4 * math.pi * poly.area / poly.length ** 2}


def dominant_normal(mesh):
    """Normal of the largest planar facet (the plate face)."""
    try:
        areas = mesh.facets_area
        if len(areas):
            return mesh.facets_normal[int(np.argmax(areas))]
    except Exception:
        pass
    return np.array([0, 0, 1.0])


def pairwise_compare(design_pts, measured_pts):
    """Rigid-motion-invariant comparison: sorted pairwise distances. Returns max |diff| (mm)."""
    def dists(P):
        return sorted(math.dist(a, b) for a, b in itertools.combinations(P, 2))
    a, b = dists(design_pts), dists(measured_pts)
    if len(a) != len(b):
        return float("inf")
    return max((abs(x - y) for x, y in zip(a, b)), default=0.0)


def best_rigid_fit(design_pts, measured_pts):
    """Least-squares rigid fit (rotation/reflection + translation) with brute-force correspondence
    for small sets via Hungarian-free greedy after Procrustes on sorted-by-distance-to-centroid order.
    Returns (max residual, mapping list) – used only for reporting which measured point is which."""
    D = np.asarray(design_pts, float)
    M = np.asarray(measured_pts, float)
    best = (float("inf"), None)
    for refl in (False, True):
        Mr = M * np.array([1, -1]) if refl else M
        for ang in np.radians(np.arange(0, 360, 90)):
            R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
            Q = (Mr - Mr.mean(0)) @ R.T + D.mean(0)
            # greedy nearest assignment
            used, mapping, res = set(), [], []
            for i, d in enumerate(D):
                dist = [(np.linalg.norm(Q[j] - d), j) for j in range(len(Q)) if j not in used]
                if not dist:
                    break
                r, j = min(dist)
                used.add(j)
                mapping.append(j)
                res.append(r)
            if len(mapping) == len(D):
                # refine with Procrustes on this correspondence
                A = Mr[mapping] - Mr[mapping].mean(0)
                B = D - D.mean(0)
                U, _, Vt = np.linalg.svd(A.T @ B)
                Rf = U @ Vt
                if np.linalg.det(Rf) < 0:
                    U[:, -1] *= -1
                    Rf = U @ Vt
                fit = A @ Rf + D.mean(0)
                r = float(np.max(np.linalg.norm(fit - D, axis=1)))
                if r < best[0]:
                    best = (r, mapping)
    return best
