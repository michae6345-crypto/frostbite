"""Measure the exported coupon STLs with trimesh. Exit code 0 only if every check passes.

Run from the repo root:  verify/.venv/bin/python docs/coupons/check_coupons.py
Intended values are written out here instead of imported from the generator, so a wrong
generator cannot agree with itself. Overhang and wall rules are the ones in CAD/check_fit.py:
no face over 45 deg past vertical (nz < -0.72) above the first layer, flat bridges <= 10 mm,
walls >= 0.8 mm. Print time and mass are estimates from a simple flow model, not a slicer.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh
from shapely.affinity import translate
from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TOL_DIM = 0.02
RESULTS: list[tuple[str, bool, str]] = []
PETG = 1.27          # g/cm^3
FLOW = 3.5           # mm^3/s, a cautious PETG average
LAYER_S = 2.0        # s per layer for travel and layer change


def rec(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))


def near(a, b, tol=TOL_DIM):
    return abs(a - b) <= tol


def section(m: trimesh.Trimesh, z: float):
    """Material polygons of the mesh at height z. Written on shapely because verify/.venv has no
    scipy, which trimesh's own Path sections need. Do not use a z that lands exactly on a face."""
    v, above = m.vertices, m.vertices[:, 2] > z
    points: dict[tuple[int, int], tuple[float, float]] = {}

    def point(i, j):
        key = (min(i, j), max(i, j))        # one exact point per mesh edge, so rings close exactly
        if key not in points:
            a, b = v[key[0]], v[key[1]]
            p = a + (b - a) * (z - a[2]) / (b[2] - a[2])
            points[key] = (float(p[0]), float(p[1]))
        return points[key]

    segments = []
    for f in m.faces[above[m.faces].sum(axis=1) % 3 != 0]:
        ends = [point(f[i], f[(i + 1) % 3]) for i in range(3) if above[f[i]] != above[f[(i + 1) % 3]]]
        if ends[0] != ends[1]:
            segments.append(LineString(ends))
    lines = unary_union(segments)
    faces = list(polygonize(lines))
    fills = [Polygon(f.exterior) for f in faces]
    out = []
    for i, f in enumerate(faces):
        pt = f.representative_point()
        depth = sum(1 for j, g in enumerate(fills) if j != i and g.contains(pt))
        if depth % 2 == 0:
            out.append(f)
    return out


def holes(polys):
    """(cx, cy, w, h, equivalent diameter) of every interior ring."""
    out = []
    for p in polys:
        for r in p.interiors:
            q = Polygon(r)
            x0, y0, x1, y1 = q.bounds
            out.append(((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0, 2 * (q.area / np.pi) ** 0.5))
    return out


def overhangs(m):
    down = np.where((m.face_normals[:, 2] < -0.72) & (m.triangles_center[:, 2] > 0.25))[0]
    bad, spans = 0.0, []
    if len(down):
        sub = m.submesh([down], append=True, repair=False)
        for c in sub.split(only_watertight=False):
            flat = (c.face_normals[:, 2] < -0.98).all()
            if flat:
                e = c.extents
                spans.append(max(e[0], e[1]))
            else:
                bad += c.area
    return bad, spans


def thin_wall(m, zmax=None, xmax=None, n=4000):
    """Smallest inward ray thickness from sampled faces, skipping labels (above zmax or past xmax).
    Label strokes have their own check, text_strokes()."""
    idx = np.arange(len(m.faces))
    if zmax is not None:
        idx = idx[m.triangles_center[idx, 2] <= zmax]
    if xmax is not None:
        idx = idx[(m.triangles_center[idx, 0] <= xmax) | (m.triangles_center[idx, 2] < 2.0 - 1e-3)]
    idx = idx[m.area_faces[idx] > 0.005]
    if len(idx) > n:
        idx = np.random.default_rng(1).choice(idx, n, replace=False)
    o = m.triangles_center[idx] - m.face_normals[idx] * 1e-3
    d = -m.face_normals[idx]
    loc, ray, _ = m.ray.intersects_location(o, d, multiple_hits=True)
    dist = np.linalg.norm(loc - o[ray], axis=1)
    best = np.inf
    for i in range(len(idx)):
        h = np.sort(dist[ray == i])
        h = h[h > 2e-3]
        if len(h):
            t = (h[1] - h[0] if len(h) > 1 else np.inf) if h[0] < 0.05 else h[0]
            best = min(best, t)
    return best


def estimate(m, infill=0.25):
    """Extruded volume from 4 perimeters (1.6) and 5 solid layers top and bottom (1.0), rest at infill."""
    nz = np.abs(m.face_normals[:, 2])
    side, flat = m.area_faces[nz < 0.5].sum(), m.area_faces[nz >= 0.5].sum()
    shell = min(m.volume, side * 1.6 + flat * 1.0)
    v = shell + infill * (m.volume - shell)
    layers = m.extents[2] / 0.2
    return v * PETG / 1000, (v / FLOW + layers * LAYER_S) / 60


def common(name, stl, size, bodies=1, zmax=None, xmax=None, infill=0.25):
    m = trimesh.load(HERE / stl, force="mesh")
    rec(f"{name}: watertight, winding ok", m.is_watertight and m.is_winding_consistent and m.volume > 0,
        f"{m.volume / 1000:.2f} cm^3 solid")
    n = len(m.split(only_watertight=True))
    rec(f"{name}: bodies", n == bodies, f"{n}")
    e = m.extents
    rec(f"{name}: bounding box", all(near(a, b, 0.03) for a, b in zip(e, size)),
        f"{e[0]:.2f} x {e[1]:.2f} x {e[2]:.2f}, want {size}")
    rec(f"{name}: on the bed", near(m.bounds[0, 2], 0.0, 1e-3), f"zmin {m.bounds[0, 2]:.3f}")
    bad, spans = overhangs(m)
    rec(f"{name}: overhang <1 mm^2 past 45 deg, bridges <=10", bad < 1.0 and all(s <= 10 for s in spans),
        f"overhang {bad:.2f} mm^2, bridges {len(spans)}" + (f", max {max(spans):.1f}" if spans else ""))
    t = thin_wall(m, zmax, xmax)
    rec(f"{name}: walls >= 0.8", t >= 0.8, f"thinnest {t:.2f} mm" + (" (labels excluded)" if zmax or xmax else ""))
    g, mins = estimate(m, infill)
    rec(f"{name}: estimate under 15 g, 30 min", g < 15 and mins < 30, f"ESTIMATE {g:.1f} g, {mins:.0f} min")
    return m


def text_strokes(name, m, z, glyphs, others=0):
    polys = section(m, z)
    thin = [p for p in polys if p.buffer(-0.2).is_empty]
    rec(f"{name}: all {glyphs} label glyphs present, strokes >= 0.4 wide", not thin and len(polys) == glyphs + others,
        f"{len(polys) - others} glyphs, {len(thin)} too thin")


def plate():
    n = "1 plate"
    m = common(n, "coupon1_plate.stl", (57.15, 52.10, 3.10), zmax=2.5 + 1e-3)
    clip = sorted(holes(section(m, 0.75)), key=lambda h: (round(h[1]), h[0]))
    w = [round(h[2], 3) for h in clip]
    want = sorted([14.0, 14.0, 14.0, 14.0, 13.9, 14.1])
    rec(f"{n}: cutout sizes 4 x 14.0, 13.9, 14.1", all(near(a, b) for a, b in zip(sorted(w), want))
        and all(near(h[2], h[3]) for h in clip), str(sorted(w)))
    xs = sorted(h[0] for h in clip)
    rec(f"{n}: pitch 19.05", near(xs[2] - xs[0], 19.05) and near(xs[4] - xs[2], 19.05)
        and near(max(h[1] for h in clip) - min(h[1] for h in clip), 19.05), f"x span {xs[-1] - xs[0]:.3f}")
    pk = holes(section(m, 2.0))
    rec(f"{n}: 6 clip pockets 15.4", len(pk) == 6 and all(near(h[2], 15.4) and near(h[3], 15.4) for h in pk))
    below, above = holes(section(m, 1.45)), holes(section(m, 1.55))
    rec(f"{n}: plate 1.5 at the clips, 2.5 web", near(max(h[2] for h in below), 14.1) and near(min(h[2] for h in above), 15.4)
        and sum(p.area for p in section(m, 2.55)) < 0.2 * sum(p.area for p in section(m, 2.45)), "step at z 1.5, web ends at z 2.5")
    text_strokes(n, m, 2.8, 24)


def inserts():
    n = "2 inserts"
    m = common(n, "coupon2_inserts.stl", (28.70, 39.00, 16.00), bodies=2, xmax=14.35 - 9.0 + 1e-3)
    hs = sorted([h for h in holes(section(m, 14.0))], key=lambda h: h[1])
    ds = [round(h[4], 2) for h in hs]
    rec(f"{n}: holes 4.5 / 4.7 / 4.9", len(hs) == 3 and all(near(a, b, 0.03) for a, b in zip(ds, (4.5, 4.7, 4.9))), str(ds))
    sect = max(section(m, 14.0), key=lambda p: p.area)
    x0, _, x1, _ = sect.bounds
    walls = [round(min(h[0] - h[4] / 2 - x0, x1 - h[0] - h[4] / 2), 2) for h in hs]
    rec(f"{n}: wall 2.1 / 2.0 / 1.9 (bar 8.7 wide)", near(x1 - x0, 8.7) and all(near(a, b, 0.03) for a, b in
        zip(walls, (2.1, 2.0, 1.9))), f"walls {walls}, bar {x1 - x0:.2f}")
    d4 = [round(h[4], 2) for h in holes(section(m, 12.05))]
    d3 = [round(h[4], 2) for h in holes(section(m, 11.95)) if h[4] < 4.0]
    rec(f"{n}: insert depth 4.0, then 3.4", len(d4) == 3 and min(d4) > 4.4 and len(d3) == 3 and all(near(d, 3.4, 0.03) for d in d3),
        f"above z 12 {d4}, below {d3}")
    deep = [h for h in holes(section(m, 3.3)) if near(h[4], 3.4, 0.03)]
    shallow = [h for h in holes(section(m, 3.1)) if near(h[4], 3.4, 0.03)]
    # the spacer's bore ends at z 3.6, so it counts at both heights
    rec(f"{n}: skin 3.2 under the blind hole", len(deep) == 4 and len(shallow) == 1, f"bores at z 3.3: {len(deep)}, at z 3.1: {len(shallow)}")
    spacer = min(m.split(only_watertight=True), key=lambda b: b.volume)
    rec(f"{n}: spacer 3.6 tall", near(spacer.extents[2], 3.6), f"{spacer.extents.round(2).tolist()}")
    text_strokes(n, m, 2.3, 9, others=2)


def pocket():
    n = "3 pocket"
    m = common(n, "coupon3_pocket_usb.stl", (50.40, 36.40, 7.60), zmax=2.5 + 1e-3)
    hs = holes(section(m, 0.75))
    sw = [h for h in hs if near(h[2], 14.0) and near(h[3], 14.0)]
    usb = [h for h in hs if near(h[2], 8.0) and near(h[3], 13.5)]
    rec(f"{n}: real 14.0 cutout present", len(sw) == 1)
    rec(f"{n}: USB window 13.5 x 8 through", len(usb) == 1 and len([h for h in holes(section(m, 6.5)) if near(h[3], 13.5)]) == 1,
        f"{[(round(h[3], 2), round(h[2], 2)) for h in usb]}")
    cx, cy = sw[0][0], sw[0][1]
    edge_x, edge_y = cx - 11.525, cy + 11.525            # the PCB corner, located from the cutout
    poly = unary_union(section(m, 5.0))
    got = {"left arm": [], "front arm": []}
    for i, t in enumerate((0.3, 0.2, 0.4)):
        mid = (i + 0.5) * 8.5
        hit = poly.intersection(LineString([(edge_x + 3, edge_y - mid), (edge_x - 2, edge_y - mid)]))
        got["left arm"].append(round(edge_x - hit.bounds[2], 3))
        hit = poly.intersection(LineString([(edge_x + mid, edge_y - 3), (edge_x + mid, edge_y + 2)]))
        got["front arm"].append(round(hit.bounds[1] - edge_y, 3))
    for arm, vals in got.items():
        rec(f"{n}: {arm} steps 0.3 / 0.2 / 0.4 from the PCB edge", all(near(a, b) for a, b in zip(vals, (0.3, 0.2, 0.4))), str(vals))
    text_strokes(n, m, 2.8, 18, others=2)


def glow():
    n = "4 band"
    m = common(n, "coupon4_glow_band.stl", (17.00, 43.00, 8.80), infill=1.0)
    # compare sections with the same slice of the real part. Real print frame: x = pcb x - 30.575,
    # y = 41.575 - pcb y, both centred on the shell. Coupon: y span 14..57 centred.
    real = trimesh.load(ROOT / "production" / "GlowBand.stl", force="mesh")
    clip = box(-40, 41.575 - 57.0, -20.575 + 0.0, 41.575 - 14.0)
    worst = 0.0
    for z in (0.5, 1.5, 1.85, 3.0, 5.0, 8.5):
        a = unary_union([translate(p, -30.575, 41.575 - 35.5) for p in section(m, z)])
        b = unary_union(section(real, z)).intersection(clip)
        worst = max(worst, a.symmetric_difference(b).area / b.area)
    rec(f"{n}: matches that slice of production/GlowBand.stl", worst < 0.005, f"worst section difference {worst * 100:.3f} %")
    c = common("4 cap", "coupon4_glow_cap.stl", (19.00, 21.00, 3.56))
    win = holes(section(c, 0.9))
    rec("4 cap: LED window 6.3 x 3.0", len(win) == 1 and near(win[0][2], 6.3) and near(win[0][3], 3.0))
    feet = section(c, 2.5)
    rec("4 cap: 2 feet, 1.76 tall on 1.8 plate", len(feet) == 2 and near(c.extents[2] - 1.8, 1.76),
        f"{len(feet)} feet, gap {c.extents[2] - 1.8:.2f}")
    fx = np.mean([p.centroid.x for p in feet])
    rec("4 cap: LED 5.0 from the PCB edge when feet sit on the riser", near(win[0][0] - (fx - 1.0), 5.0), f"{win[0][0] - (fx - 1.0):.2f}")


def main():
    plate()
    inserts()
    pocket()
    glow()
    w = max(len(r[0]) for r in RESULTS)
    for name, ok, d in RESULTS:
        print(f"{name.ljust(w)}  {'PASS' if ok else 'FAIL'}  {d}")
    fails = sum(1 for r in RESULTS if not r[1])
    print(f"\n{len(RESULTS) - fails} pass, {fails} fail")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
