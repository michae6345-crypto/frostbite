"""A printed part as cross-sections, placed in PCB coordinates from its own geometry.

No section height or opening shape is assumed. Section heights are the mesh's own vertex levels
plus the heights where real parts start or stop. Checks then ask whether a real part's outline
is clear of material at a height.

(x, y) = PCB coordinates. h = depth below the part's upper face as assembled: the plate top face
for the Top, the rim for the Bottom. Both models look down on the case from above, so a point
means the same thing in either.
"""
from __future__ import annotations

import math

import numpy as np
import shapely.geometry as g
import shapely.ops as o
from shapely import affinity

EPS = 0.01


def _material(mesh, point, n, u, v):
    """Even-odd cross-section in (u, v) plane coordinates, as one shapely geometry.

    Crossing points are keyed by mesh edge so loops close exactly. Rounding coordinates instead
    can drop a whole loop, and the material with it, without any error."""
    V = mesh.vertices
    d = (V - point) @ n
    F = mesh.faces
    above = d[F] > 0
    cnt = above.sum(axis=1)
    nodes = {}
    adj = {}
    for tri, ab in zip(F[(cnt == 1) | (cnt == 2)], above[(cnt == 1) | (cnt == 2)]):
        ends = []
        for i in range(3):
            a, b = int(tri[i]), int(tri[(i + 1) % 3])
            if ab[i] != ab[(i + 1) % 3]:
                k = (a, b) if a < b else (b, a)
                if k not in nodes:
                    ta = d[k[0]] / (d[k[0]] - d[k[1]])
                    q = V[k[0]] + ta * (V[k[1]] - V[k[0]]) - point
                    nodes[k] = (float(q @ u), float(q @ v))
                ends.append(k)
        if len(ends) == 2:
            adj.setdefault(ends[0], []).append(ends[1])
            adj.setdefault(ends[1], []).append(ends[0])
    seen, rings = set(), []
    for start in adj:
        if start in seen:
            continue
        ring, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [q for q in adj[cur] if q != prev]
            if not nxt:
                break
            step = next((q for q in nxt if q not in seen), None)
            if step is None:
                break
            seen.add(step)
            ring.append(step)
            prev, cur = cur, step
        if len(ring) >= 3:
            rings.append(g.Polygon([nodes[k] for k in ring]).buffer(0))
    mat = g.GeometryCollection()
    for r in sorted((x for x in rings if not x.is_empty and x.area > 1e-7), key=lambda x: -x.area):
        mat = r if mat.is_empty else mat.symmetric_difference(r)
    return mat


def _axis_and_up(mesh):
    """Plate axis: normal of the largest planar face. register() tries both signs."""
    n = None
    try:
        if len(mesh.facets_area):
            n = np.asarray(mesh.facets_normal[int(np.argmax(mesh.facets_area))], float)
    except Exception:
        pass
    if n is None:
        a = mesh.area_faces
        bins = {}
        for fn, ar in zip(np.round(mesh.face_normals, 3), a):
            k = tuple(fn)
            bins[k] = bins.get(k, 0) + ar
        n = np.array(max(bins, key=bins.get), float)
    return n / np.linalg.norm(n)


def _in_plane_axes(mesh, n):
    """(u, v) with u x v = n, aligned with the part's side walls (area-weighted wall direction)."""
    ref = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    e1 = ref - n * np.dot(ref, n)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    fn = mesh.face_normals
    perp = np.abs(fn @ n) < 0.02
    if perp.any():
        ang = np.degrees(np.arctan2(fn[perp] @ e2, fn[perp] @ e1)) % 90.0
        ang = np.round(ang, 1) % 90.0
        vals, inv = np.unique(ang, return_inverse=True)
        w = np.bincount(inv, weights=mesh.area_faces[perp])
        th = math.radians(float(vals[int(np.argmax(w))]))
    else:
        th = 0.0
    u = math.cos(th) * e1 + math.sin(th) * e2
    return u, np.cross(n, u)


class PartModel:
    def __init__(self, mesh, n, u, v, top, cx, cy, s, pcb_c, extra_h=()):
        self.mesh, self.n, self.u, self.v, self.top = mesh, n, u, v, top
        self.c = (cx, cy)      # outline centre in (u, v)
        self.s = s             # +1 or -1 (180 degree ambiguity)
        self.pcb_c = pcb_c     # PCB-coordinate point that sits at the outline centre
        hv = np.round(top - mesh.vertices @ n, 3)
        self.hmax = float(hv.max())
        hs = sorted(set(hv.tolist()) | {h for h in extra_h if 0 < h < self.hmax})
        lv = [hs[0]]
        for h in hs[1:]:
            if h - lv[-1] >= 0.02:
                lv.append(h)
        self.levels = lv
        self.slabs = []
        vol = 0.0
        for h0, h1 in zip(lv, lv[1:]):
            mids = (h0 + EPS, (h0 + h1) / 2, h1 - EPS)
            secs = [self._pcb(self._section(h)) for h in mids]
            a = [m.area for m in secs]
            vol += (a[0] + 4 * a[1] + a[2]) / 6 * (h1 - h0 - 2 * EPS) + (a[0] + a[2]) * EPS
            self.slabs.append({"h0": h0, "h1": h1, "mat": o.unary_union(secs), "area": a[1]})
        self.section_volume = vol
        self.mesh_volume = float(mesh.volume)

    def _section(self, h):
        return _material(self.mesh, self.n * (self.top - h), self.n, self.u, self.v)

    def _pcb(self, geom2d):
        """(a, b) plane coordinates -> PCB (x, y). PCB y runs towards the user: b up in plan is -y."""
        ca, cb = self.c
        px, py = self.pcb_c
        s = self.s
        # x = px + s*(a-ca) ; y = py - s*(b-cb)
        return affinity.affine_transform(geom2d, [s, 0, 0, -s, px - s * ca, py + s * cb])

    def slabs_between(self, h_lo, h_hi):
        return [s for s in self.slabs if s["h1"] > h_lo + 1e-9 and s["h0"] < h_hi - 1e-9]

    def min_gap(self, shape, h_lo, h_hi):
        """Smallest distance from a real part's outline to material over a height range.
        On overlap this is minus the overlap area, not a depth."""
        worst = (math.inf, None)
        for s in self.slabs_between(h_lo, h_hi):
            mat = s["mat"]
            if mat.is_empty:
                continue
            ov = mat.intersection(shape).area
            d = -ov if ov > 1e-4 else mat.distance(shape)
            if d < worst[0]:
                worst = (d, [s["h0"], s["h1"]])
        return worst

    def spans(self, x, y, axis, h_lo, h_hi):
        """Free span through (x, y) along an axis, per slab: [(a, b, h0, h1)], or None if (x, y) is in material."""
        out = []
        p = g.Point(x, y)
        for s in self.slabs_between(h_lo, h_hi):
            ln = g.LineString([(x - 60, y), (x + 60, y)] if axis == "x" else [(x, y - 60), (x, y + 60)])
            free = ln.difference(s["mat"])
            segs = [free] if free.geom_type == "LineString" else list(getattr(free, "geoms", []))
            hit = None
            for sg in segs:
                if not sg.is_empty and sg.distance(p) < 1e-6:
                    b = sg.bounds
                    hit = (b[0], b[2]) if axis == "x" else (b[1], b[3])
            if hit is None:
                return None
            out.append((hit[0], hit[1], s["h0"], s["h1"]))
        return out

    def opening_at(self, x, y, h):
        """The closed free region around (x, y) at depth h, as measured, whatever its shape."""
        p = g.Point(x, y)
        for s in self.slabs_between(h, h + 0.001):
            m = s["mat"]
            for pl in (list(m.geoms) if hasattr(m, "geoms") else [m]):
                for r in getattr(pl, "interiors", []):
                    hole = g.Polygon(r)
                    if hole.contains(p):
                        return hole
        return None


def register(mesh, d, extra_h=()):
    """Find plate axis, top side and in-plane rotation from the part itself. Returns (model, info)."""
    shell = d["case"]["shell"]
    W, H = d["pcb"]["w"], d["pcb"]["h"]
    px = shell.get("x", (W - shell["w"]) / 2) + shell["w"] / 2
    py = shell.get("y", (H - shell["h"]) / 2) + shell["h"] / 2
    n0 = _axis_and_up(mesh)
    tries = []
    for n in (n0, -n0):
        top = float((mesh.vertices @ n).max())
        area0 = _material(mesh, n * (top - 0.05), n, *_in_plane_axes(mesh, n)).area
        tries.append((area0, n, top))
    amax = max(t[0] for t in tries)
    pts = [(k["x"], k["y"]) for k in d["keys"]]
    pts += [(d["encoder"]["x"], d["encoder"]["y"])]
    w = d["oled"]["window"]
    pts += [(w["x"] + w["w"] / 2, w["y"] + w["h"] / 2)]
    best = None
    for area0, n, top in tries:
        if area0 < 0.9 * amax:
            continue
        u, v = _in_plane_axes(mesh, n)
        eu, ev = mesh.vertices @ u, mesh.vertices @ v
        wu, wv = float(eu.max() - eu.min()), float(ev.max() - ev.min())
        if abs(wv - shell["w"]) + abs(wu - shell["h"]) < abs(wu - shell["w"]) + abs(wv - shell["h"]):
            u, v = v, -u
            eu, ev = mesh.vertices @ u, mesh.vertices @ v
            wu, wv = float(eu.max() - eu.min()), float(ev.max() - ev.min())
        cu, cv = (eu.max() + eu.min()) / 2, (ev.max() + ev.min()) / 2
        for s in (1, -1):
            sec = _material(mesh, n * (top - 0.05), n, u, v)
            m = PartModel.__new__(PartModel)
            m.c, m.s, m.pcb_c = (float(cu), float(cv)), s, (px, py)
            mat = m._pcb(sec)
            score = sum(1 for p in pts if not mat.contains(g.Point(p)))
            if best is None or score > best[0]:
                best = (score, n, u, v, top, float(cu), float(cv), s, wu, wv)
    score, n, u, v, top, cu, cv, s, wu, wv = best
    model = PartModel(mesh, n, u, v, top, cu, cv, s, (px, py), extra_h=extra_h)
    return model, {"plate_normal": [round(float(x), 4) for x in n], "outline_mm": [round(wu, 3), round(wv, 3)],
                   "rotation_sign": s, "feature_points_open_at_plate_top": f"{score}/{len(pts)}",
                   "levels_h": model.levels, "section_volume_mm3": round(model.section_volume, 1),
                   "mesh_volume_mm3": round(model.mesh_volume, 1)}


def register_tray(mesh, d, below_plate=()):
    """Same for the Bottom: h=0 at the rim, opening up. The rim side has the smaller section.

    The 180 degree choice is the one that puts the USB notch on the back wall. With no notch both
    choices are equal and the checks report the missing notch. below_plate: heights to section
    at, as depth below the plate top. model.rim is the plate top to rim depth, from the part's
    height and design.json case.shell.height."""
    shell = d["case"]["shell"]
    W, H = d["pcb"]["w"], d["pcb"]["h"]
    px = shell.get("x", (W - shell["w"]) / 2) + shell["w"] / 2
    py = shell.get("y", (H - shell["h"]) / 2) + shell["h"] / 2
    n0 = _axis_and_up(mesh)
    tries = []
    for n in (n0, -n0):
        top = float((mesh.vertices @ n).max())
        tries.append((_material(mesh, n * (top - 0.05), n, *_in_plane_axes(mesh, n)).area, n, top))
    area0, n, top = min(tries, key=lambda t: t[0])
    u, v = _in_plane_axes(mesh, n)
    eu, ev = mesh.vertices @ u, mesh.vertices @ v
    wu, wv = float(eu.max() - eu.min()), float(ev.max() - ev.min())
    if abs(wv - shell["w"]) + abs(wu - shell["h"]) < abs(wu - shell["w"]) + abs(wv - shell["h"]):
        u, v = v, -u
        eu, ev = mesh.vertices @ u, mesh.vertices @ v
        wu, wv = float(eu.max() - eu.min()), float(ev.max() - ev.min())
    cu, cv = float(eu.max() + eu.min()) / 2, float(ev.max() + ev.min()) / 2
    height = top - float((mesh.vertices @ n).min())
    rim = shell["height"] - height
    r = d["mcu"]["rect"]
    usb = g.Point(r["x"] + r["w"] / 2, -(shell["h"] - H) / 4)      # middle of the back wall, on the USB axis
    best = None
    for s in (1, -1):
        m = PartModel.__new__(PartModel)
        m.c, m.s, m.pcb_c = (cu, cv), s, (px, py)
        is_open = not m._pcb(_material(mesh, n * (top - 0.05), n, u, v)).contains(usb)
        if best is None or (is_open and not best[0]):
            best = (is_open, s)
    is_open, s = best
    model = PartModel(mesh, n, u, v, top, cu, cv, s, (px, py), extra_h=tuple(h - rim for h in below_plate))
    model.rim = rim
    return model, {"rim_normal": [round(float(x), 4) for x in n], "outline_mm": [round(wu, 3), round(wv, 3)],
                   "height_mm": round(height, 3), "rim_below_plate_top_mm": round(rim, 3), "rotation_sign": s,
                   "usb_notch_found_on_back_wall": bool(is_open), "levels_h": model.levels,
                   "section_volume_mm3": round(model.section_volume, 1), "mesh_volume_mm3": round(model.mesh_volume, 1)}
