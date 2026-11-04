"""Check the coupon STLs: watertight, rib and window sizes, overhangs, fit, print time estimate.

Run:  verify/.venv/bin/python docs/concepts/generative/coupon/verify_coupon.py
All sizes are measured from the exported meshes, never from the source polygons.
Print frame: wall X = design x + tx, Y = pcb y + ty, Z = tz - design z. Fence Z = design z + tz.
"""
from __future__ import annotations

import json
import math
from itertools import combinations
from pathlib import Path

import numpy as np
import shapely
import trimesh
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
B = json.loads((HERE / "build.json").read_text())
XL, MIN_RIB, MIN_WIN = -9.0, 1.6, 1.8
LAYER, LINE = 0.2, 0.45
P_WALL = B["parts"]["coupon-wall"]["translate"]
P_FENCE = B["parts"]["coupon-fence"]["translate"]


def load(name):
    return trimesh.load_mesh(HERE / f"{name}.stl")


def section(mesh, origin, normal, axes):
    """Even-odd cross-section as shapely geometry. verify/.venv has no scipy, so no trimesh Path."""
    seg = trimesh.intersections.mesh_plane(mesh, normal, origin)
    lines = shapely.linestrings(np.round(seg[:, :, list(axes)], 6))
    return shapely.build_area(shapely.line_merge(shapely.node(shapely.multilinestrings(lines))))


def loops(mesh, x):
    """Section at print-frame X = x: the outline and its window holes, in (print y, print z)."""
    g = section(mesh, [x, 0, 0], [1, 0, 0], (1, 2))
    p = max(g.geoms, key=lambda q: q.area) if hasattr(g, "geoms") else g
    return [Polygon(p.exterior)] + [Polygon(r) for r in p.interiors]


def skin_elevation(mesh, depth):
    x = XL + depth + P_WALL[0]
    rings = loops(mesh, x)
    outline, wins = rings[0], [p for p in rings[1:] if p.area > 0.5]
    pairs = [(a.distance(b), i, j) for (i, a), (j, b) in combinations(enumerate(wins), 2)]
    rib, i, j = min(pairs)
    edge = min(w.exterior.distance(outline.exterior) for w in wins)
    ins = [2 * shapely.maximum_inscribed_circle(w, tolerance=0.005).length for w in wins]
    feret = [min(_mrr_sides(w)) for w in wins]
    locs = LineString(shapely.ops.nearest_points(wins[i], wins[j])).centroid
    return {"depth_from_skin_mm": depth, "windows": len(wins), "open_area_mm2": round(sum(w.area for w in wins), 1),
            "min_rib_between_windows_mm": round(rib, 3), "min_rib_at_pcb_y": round(locs.x - P_WALL[1], 1),
            "min_rib_at_design_z": round(P_WALL[2] - locs.y, 1), "min_window_to_outline_mm": round(edge, 3),
            "min_window_inscribed_d_mm": round(min(ins), 3), "min_window_short_side_mm": round(min(feret), 3),
            "ribs_below_limit": sum(1 for d, _, _ in pairs if d < MIN_RIB - 0.005),
            "windows_below_limit": sum(1 for d in ins if d < MIN_WIN - 0.005)}


def _mrr_sides(p):
    c = np.array(p.minimum_rotated_rectangle.exterior.coords)
    return float(np.hypot(*(c[1] - c[0]))), float(np.hypot(*(c[2] - c[1])))


def bodies(mesh):
    parent = list(range(len(mesh.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b in mesh.face_adjacency:
        parent[find(a)] = find(b)
    return len({find(i) for i in range(len(parent))})


def overhangs(mesh):
    n, a = mesh.face_normals, mesh.area_faces
    centres = mesh.triangles_center
    down = (n[:, 2] < -1e-6) & (centres[:, 2] > 0.02)      # the bed face is not an overhang
    ang = np.degrees(np.arcsin(np.clip(-n[:, 2], 0, 1)))    # 0 = vertical wall, 90 = flat ceiling
    flat = down & (ang > 85)
    slope = down & ~flat
    steep = down & (ang > 46)                                # flat bridges plus the short facets that join them
    res = {"max_sloped_overhang_deg": round(float(ang[slope].max()), 1) if slope.any() else 0.0,
           "sloped_area_over_45_5deg_mm2": round(float(a[slope & (ang > 45.5)].sum()), 3),
           "sloped_area_over_50deg_mm2": round(float(a[slope & (ang > 50)].sum()), 3),
           "sloped_area_over_60deg_mm2": round(float(a[slope & (ang > 60)].sum()), 3)}
    idx = np.flatnonzero(steep)
    roofs = []
    if idx.size:
        for g in flat_groups(mesh, idx):
            v = mesh.vertices[mesh.faces[g]].reshape(-1, 3)
            d = v.max(0) - v.min(0)
            roofs.append({"x_mm": round(float(d[0]), 2), "y_mm": round(float(d[1]), 2), "z_mm": round(float(v[:, 2].mean()), 2),
                          "area_mm2": round(float(a[g].sum()), 2)})
    res["flat_roofs"] = sorted(roofs, key=lambda r: -max(r["x_mm"], r["y_mm"]))
    return res


def flat_groups(mesh, idx):
    members = set(int(i) for i in idx)
    links = {i: [] for i in members}
    for a, b in mesh.face_adjacency:
        if int(a) in members and int(b) in members:
            links[int(a)].append(int(b))
            links[int(b)].append(int(a))
    seen, groups = set(), []
    for i in members:
        if i in seen:
            continue
        stack, g = [i], []
        seen.add(i)
        while stack:
            j = stack.pop()
            g.append(j)
            for k in links[j]:
                if k not in seen:
                    seen.add(k)
                    stack.append(k)
        groups.append(g)
    return groups


def time_estimate(mesh, infill):
    """Very rough. Layer sections, 4 walls, 4 solid skins, no slicer involved."""
    hs = np.arange(LAYER / 2, mesh.bounds[1, 2], LAYER)
    layers = [section(mesh, [0, 0, h], [0, 0, 1], (0, 1)).buffer(0) for h in hs]
    t = 0.0
    for i, g in enumerate(layers):
        islands = list(g.geoms) if hasattr(g, "geoms") else [g]
        core = g.buffer(-4 * LINE)
        wall_a = g.area - core.area
        over = layers[min(i + 4, len(layers) - 1)]
        under = layers[max(i - 4, 0)]
        solid = core.difference(over.intersection(under).buffer(0)) if 4 <= i < len(layers) - 4 else core
        sparse = core.area - solid.area
        t += wall_a / LINE / 35 + solid.area / LINE / 40 + sparse * infill / LINE / 60
        t += 0.8 * len(islands) + 1.0                       # retract and travel per island, layer change
    return round(t * 1.15 / 60, 1)                           # acceleration losses, no heat-up


def fit(wall, fence):
    w = wall.copy()
    w.apply_translation(-np.array(P_WALL))
    w.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
    f = fence.copy()
    f.apply_translation(-np.array(P_FENCE))
    out = {"wall": section(w, [0, 0, -5.7], [0, 0, 1], (0, 1)), "fence": section(f, [0, 0, -5.7], [0, 0, 1], (0, 1))}
    # design frame Y = -pcb y, so the mid-span probe at pcb y 45 is at -45
    span = LineString([(-12, -45), (3, -45)])
    fx = out["fence"].intersection(span)
    skin = out["wall"].intersection(span)
    fx0, fx1 = fx.bounds[0], fx.bounds[2]
    skin_in = max(g.bounds[2] for g in (skin.geoms if hasattr(skin, "geoms") else [skin]) if g.bounds[2] < -5)
    hole = Point(-4.65, -62.1)
    boss = out["wall"]
    hole_ring = min((g for g in _rings(boss) if g.distance(hole) < 0.05 and g.area < 30), key=lambda g: g.area)
    wall_min = min(_insert_wall(w, z) for z in (-5.7, -6.5, -7.5, -8.5, -9.2))
    return {"probe": "design z -5.7, pcb y 45 unless noted", "min_wall_around_insert_mm": wall_min,
            "fence_thickness_mm": round(fx1 - fx0, 3), "gap_fence_to_skin_mm": round(fx0 - skin_in, 3),
            "led_centre_to_fence_mm": round(5.0 - fx1, 3), "led_centre_to_skin_outer_mm": round(5.0 - XL, 3),
            "insert_hole_d_mm": round(2 * math.sqrt(hole_ring.area / math.pi), 2),
            "wall_hole_to_outer_skin_mm": round(hole_ring.bounds[0] - XL, 3),
            "wall_hole_to_boss_inner_mm": round(-0.3 - hole_ring.bounds[2], 3)}


def _insert_wall(w, z):
    """Thinnest wall round the insert hole at this height, to any other boundary of the section."""
    g = section(w, [0, 0, z], [0, 0, 1], (0, 1))
    hole = Point(-4.65, -62.1)
    rings = list(g.geoms) if hasattr(g, "geoms") else [g]
    p = min(rings, key=lambda q: q.distance(hole))
    inner = [Polygon(r) for r in p.interiors if Polygon(r).distance(hole) < 0.05 and Polygon(r).area < 30]
    others = [r for r in list(p.interiors) + [p.exterior] if not (Polygon(r).distance(hole) < 0.05 and Polygon(r).area < 30)]
    return round(min(inner[0].exterior.distance(r) for r in others), 3)


def _rings(g):
    for p in (g.geoms if hasattr(g, "geoms") else [g]):
        yield from (Polygon(r) for r in p.interiors)
        yield Polygon(p.exterior)


def main():
    wall, fence = load("coupon-wall"), load("coupon-fence")
    res = {}
    for name, m in (("wall", wall), ("fence", fence)):
        res[name] = {"watertight": bool(m.is_watertight), "winding_consistent": bool(m.is_winding_consistent),
                     "bodies": bodies(m), "volume_mm3": round(float(m.volume), 1),
                     "faces": len(m.faces), "size_mm": [round(float(v), 2) for v in m.extents],
                     "overhangs": overhangs(m)}
    res["wall"]["elevation"] = [skin_elevation(wall, d) for d in (0.1, 0.45, 1.5, 2.9)]
    res["wall"]["time_min_25pct_infill"] = time_estimate(wall, 0.25)
    res["fence"]["time_min_25pct_infill"] = time_estimate(fence, 0.25)
    res["fence"]["time_min_100pct_infill"] = time_estimate(fence, 1.0)
    res["fit"] = fit(wall, fence)
    res["fit"]["interference_mm3_from_cadquery"] = B["interference_mm3"]
    (HERE / "results.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
