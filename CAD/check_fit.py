"""Frostbite case fit and printability checks (gate G4).

Run from the repo root:  CAD/.venv/bin/python CAD/check_fit.py   [--no-build]
Rebuilds the parts from design.json (unless --no-build), re-exports production
STEP/STL + the assembly, then checks geometry. Exit code 0 only if every check passes.
Warnings (thin spots, bridges) are printed but do not fail the run.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import cadquery as cq
from OCP.gp import gp_Dir, gp_Lin, gp_Pnt
from OCP.IntCurvesFace import IntCurvesFace_ShapeIntersector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frostbite_case as fc  # noqa: E402

D = fc.D
EPS_VOL = 0.01      # mm^3, "no interference"
RESULTS: list[tuple[str, bool, str]] = []
WARN: list[str] = []


def rec(name, ok, detail):
    RESULTS.append((name, bool(ok), detail))


# ------------------------------------------------------------------ geometry helpers
class Ray:
    def __init__(self, shape: cq.Shape):
        self.it = IntCurvesFace_ShapeIntersector()
        self.it.Load(shape.wrapped, 1e-7)

    def hits(self, o, d, maxd=500.0):
        n = math.sqrt(sum(c * c for c in d))
        self.it.Perform(gp_Lin(gp_Pnt(*o), gp_Dir(*(c / n for c in d))), 0.0, maxd)
        return sorted(self.it.WParameter(i) for i in range(1, self.it.NbPnt() + 1))

    def first(self, o, d, min_t=1e-6):
        h = [t for t in self.hits(o, d) if t > min_t]
        return h[0] if h else math.inf


def P(x, y, z):          # PCB coords -> design frame point
    return (x, -y, z)


def inter_vol(a: cq.Shape, b: cq.Shape) -> float:
    ba, bb = a.BoundingBox(), b.BoundingBox()
    if (ba.xmax < bb.xmin or bb.xmax < ba.xmin or ba.ymax < bb.ymin or bb.ymax < ba.ymin
            or ba.zmax < bb.zmin or bb.zmax < ba.zmin):
        return 0.0
    return a.intersect(b).Volume()


def dist(a: cq.Shape, b: cq.Shape) -> float:
    return a.distance(b)


# ------------------------------------------------------------------ checks
def check_envelope(m, printed):
    asm = fc.assembly(m).toCompound()
    bb = asm.BoundingBox()
    ok = bb.xlen <= 200 and bb.ylen <= 200 and bb.zlen <= 100
    rec("Assembly bbox <= 200x200x100", ok, f"{bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f} mm (incl. keycaps, knob)")
    worst = max(max(s.BoundingBox().xlen, s.BoundingBox().ylen) for s in printed.values())
    rec("Each part fits a 200x200 bed", worst <= 200, f"largest footprint {worst:.2f} mm")


def check_reopen(m, printed):
    bad = []
    for name, s in printed.items():
        r = cq.importers.importStep(str(fc.PROD / f"{name}.step")).val()
        if abs(r.Volume() - s.Volume()) > 1e-3 * s.Volume():
            bad.append(name)
    a = cq.importers.importStep(str(fc.CAD / "frostbite-assembly.step"))
    nsol = len(a.solids().vals())
    expect = len(m["parts"]) + len(m["ph"])
    rec("STEP files reopen in CadQuery", not bad and nsol >= expect,
        f"4 part STEPs volume-identical; assembly has {nsol} solids (>= {expect})" if not bad else f"mismatch {bad}")
    try:
        import trimesh
        nonwt = []
        for name in printed:
            t = trimesh.load(str(fc.PROD / f"{name}.stl"), force="mesh", process=True)
            if not (t.is_watertight and t.is_winding_consistent and t.volume > 0):
                nonwt.append(name)
        rec("STL watertight", not nonwt, "all 4 watertight, consistent winding" if not nonwt else f"bad: {nonwt}")
    except ImportError:
        WARN.append("trimesh not installed: STL watertightness not checked")


def check_pocket(m):
    want_w, want_h = fc.PCB_W + 2 * fc.TOL, fc.PCB_H + 2 * fc.TOL
    cx, cy = fc.PCB_W / 2, fc.PCB_H / 2
    rows = []
    ok = True
    for name, z in (("Top", -5.0), ("GlowBand", -10.4), ("Bottom", -12.0)):
        r = Ray(m["parts"][name])
        w = r.first(P(cx, cy, z), (1, 0, 0)) + r.first(P(cx, cy, z), (-1, 0, 0))
        h = r.first(P(cx, cy, z), (0, -1, 0)) + r.first(P(cx, cy, z), (0, 1, 0))
        ok &= abs(w - want_w) < 0.01 and abs(h - want_h) < 0.01
        rows.append(f"{name} {w:.2f}x{h:.2f}")
    rec("PCB pocket = PCB + 2x tolerance", ok, f"want {want_w:.2f}x{want_h:.2f}: " + ", ".join(rows))


def check_interference(m):
    parts, ph = m["parts"], m["ph"]
    worst, hits = 0.0, []
    for pn, ps in parts.items():
        for hn, hs in ph.items():
            v = inter_vol(ps, hs)
            worst = max(worst, v)
            if v > EPS_VOL:
                hits.append(f"{pn}x{hn}={v:.3f}")
    names = list(parts)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            v = inter_vol(parts[names[i]], parts[names[j]])
            worst = max(worst, v)
            if v > EPS_VOL:
                hits.append(f"{names[i]}x{names[j]}={v:.3f}")
    rec("Interference: printed parts vs PCB/components/each other", not hits,
        f"{len(parts) * len(ph) + 6} pairs, max overlap {worst:.4f} mm^3" + ("; " + ", ".join(hits[:6]) if hits else ""))
    # keycaps at bottom-out (4 mm travel)
    down = [ph[f"{k['ref']}_keycap"].translate(cq.Vector(0, 0, -4.0)) for k in D["keys"]]
    v = sum(inter_vol(parts[p], c) for p in parts for c in down)
    rec("Interference: keycaps bottomed out (-4 mm)", v < EPS_VOL, f"overlap {v:.4f} mm^3")
    # PCB clearance to every printed part
    dd = {p: dist(parts[p], ph["PCB"]) for p in ("Top", "GlowBand", "Bottom")}
    rec("Printed parts clear the PCB by >= tolerance", min(dd.values()) >= fc.TOL - 1e-3,
        ", ".join(f"{k} {v:.2f}" for k, v in dd.items()) + " mm")


def check_switch_cutouts(m):
    top = m["parts"]["Top"]
    r = Ray(top)
    zc = fc.PLATE_TOP - fc.PLATE_T_CLIP / 2
    ws, ts, te = [], [], []
    for k in D["keys"]:
        o = P(k["x"], k["y"], zc)
        ws.append(r.first(o, (1, 0, 0)) + r.first(o, (-1, 0, 0)))
        ws.append(r.first(o, (0, 1, 0)) + r.first(o, (0, -1, 0)))
        h = r.hits(P(k["x"] + 7.35, k["y"], -1.0), (0, 0, 1))
        h = [t - 1.0 for t in h if t - 1.0 > fc.PLATE_UNDER - 0.5]
        ts.append(h[1] - h[0])
        h = r.hits(P(k["x"] + 9.525, k["y"], -1.0), (0, 0, 1))
        h = [t - 1.0 for t in h if t - 1.0 > fc.PLATE_UNDER - 0.5]
        te.append(h[1] - h[0] if len(h) >= 2 else 0)
    ok = all(abs(w - 14.0) <= 0.1 for w in ws)
    rec("Switch cutouts 14.0 +/-0.1 (9 keys)", ok, f"min {min(ws):.3f}, max {max(ws):.3f} mm")
    rec("Plate 1.5 at the clips, thicker between", all(abs(t - 1.5) < 0.02 for t in ts) and min(te) >= 2.0,
        f"clip zone {min(ts):.2f}-{max(ts):.2f}, web {min(te):.2f} mm")
    sw = sum(inter_vol(top, m["ph"][f"{k['ref']}_switch"]) for k in D["keys"])
    dmin = min(dist(top, m["ph"][f"{k['ref']}_switch"].translate(cq.Vector(0, 0, 0))) for k in D["keys"][:1])
    rec("Switch bodies vs plate", sw < EPS_VOL, f"overlap {sw:.4f} mm^3 (housing 14.0 in a 14.0 cutout, clips in 15.4 pockets)")
    _ = dmin


def check_keycaps(m):
    top, knob = m["parts"]["Top"], m["parts"]["Knob"]
    caps = [m["ph"][f"{k['ref']}_keycap"] for k in D["keys"]]
    rest = min(dist(top, c) for c in caps)
    down = min(dist(top, c.translate(cq.Vector(0, 0, -4.0))) for c in caps)
    kn = min(dist(knob, c) for c in caps)
    rec("Keycap to Top clearance >= 1 mm", min(rest, down) >= 1.0,
        f"rest {rest:.2f}, bottomed out {down:.2f} mm (plate-flush top, no wall above the plate)")
    rec("Keycap to knob clearance >= 1 mm", kn >= 1.0, f"{kn:.2f} mm")
    # plan clearance cap -> shell skin
    cap_minx = min(k["x"] for k in D["keys"]) - 9.1
    edge = -(fc.SHELL_W - fc.PCB_W) / 2
    rec("Keycaps inside the shell outline", cap_minx - edge >= 1.0, f"cap to outer skin {cap_minx - edge:.2f} mm in plan")


def check_inserts(m):
    top, bot, band, pcb = m["parts"]["Top"], m["parts"]["Bottom"], m["parts"]["GlowBand"], m["ph"]["PCB"]
    rt, rb = Ray(top), Ray(bot)
    depth, dia, walls, rows = [], [], [], []
    for sx, sy in fc.SCREWS:
        o = P(sx, sy + 2.0, fc.SKIRT_BOT - 1.0)            # inside the 4.7 bore, outside the 3.4 hole
        depth.append(rt.first(o, (0, 0, 1)) - 1.0)          # mouth -> step to 3.4
        z = fc.SKIRT_BOT + 2.0
        rr = []
        for a in range(0, 360, 15):
            d = (math.cos(math.radians(a)), math.sin(math.radians(a)), 0)
            t0 = rt.first(P(sx, sy, z), d)
            rr.append(t0)
            hs = [t for t in rt.hits(P(sx, sy, z), d) if t > t0 + 1e-4]
            walls.append(hs[0] - t0 if hs else math.inf)
        dia.append(2 * min(rr))
    rec("Insert holes 4.7 x 4 deep (Top)", all(abs(d - 4.7) < 0.02 for d in dia) and all(abs(x - 4.0) < 0.02 for x in depth),
        f"dia {min(dia):.2f}, depth {min(depth):.2f}-{max(depth):.2f} mm")
    rec("Wall around inserts >= 1.3 (ruthex min)", min(walls) >= 1.3, f"min wall {min(walls):.2f} mm")
    bosses = [fc.solid(fc.cyl(sx, sy, fc.TOP_BOSS_R, fc.SKIRT_BOT, -fc.TOL)) for sx, sy in fc.SCREWS]
    bd = min(dist(b.intersect(top), pcb) for b in bosses)
    v = sum(inter_vol(b.intersect(top), pcb) for b in bosses)
    rec("Insert bosses vs PCB outline", v < EPS_VOL and bd >= fc.TOL - 1e-3,
        f"overlap {v:.4f} mm^3, boss-PCB gap {bd:.2f} mm (bosses tuck 0.3 under the PCB edge)")
    # features must not collide with insert holes: distance from feature cutters to insert cylinders
    w, mo = fc.OL["window"], fc.OL["module"]
    feats = {f"{k['ref']} cutout": fc.cbox(k["x"], k["y"], fc.CLIP_POCKET, fc.CLIP_POCKET, fc.PLATE_UNDER, fc.PLATE_TOP)
             for k in D["keys"]}
    feats["OLED recess"] = fc.box(mo["x"] - fc.TOL, mo["x"] + mo["w"] + fc.TOL, mo["y"] - fc.TOL, mo["y"] + mo["h"] + fc.TOL,
                                  fc.PLATE_UNDER, fc.PLATE_TOP)
    feats["encoder opening"] = fc.rrect(fc.EN["x"], fc.EN["y"], *fc.EC_OPEN, fc.PLATE_UNDER, fc.PLATE_TOP)
    feats["USB window"] = fc.box(fc.USB_CX - fc.UC["w"] / 2, fc.USB_CX + fc.UC["w"] / 2, -9, 1,
                                 fc.USB_CZ - fc.UC["h"] / 2, fc.USB_CZ + fc.UC["h"] / 2)
    holes = [fc.solid(fc.cyl(sx, sy, fc.INSERT_HOLE / 2, fc.SKIRT_BOT, fc.SCREW_TIP + 0.4)) for sx, sy in fc.SCREWS]
    near = min((dist(fc.solid(f), h), n) for n, f in feats.items() for h in holes)
    rec("Cutouts/OLED/encoder/USB clear of screw bosses", near[0] >= 1.2, f"closest: {near[1]} {near[0]:.2f} mm")
    # screws: shank + head vs printed parts, head recessed, full thread engagement
    v, recess = 0.0, []
    for sx, sy in fc.SCREWS:
        shank = fc.solid(fc.cyl(sx, sy, 1.5, fc.SEAT, fc.SCREW_TIP))
        head = fc.solid(fc.cyl(sx, sy, fc.HEAD_D / 2, fc.SEAT - fc.HEAD_H, fc.SEAT))
        for p in (top, band, bot):
            v += inter_vol(p, shank) + inter_vol(p, head)
        under = rb.first(P(sx, sy + 3.0, -100), (0, 0, 1)) - 100   # underside next to the counterbore
        recess.append((fc.SEAT - fc.HEAD_H) - under)
    eng = min(fc.SCREW_TIP, fc.SKIRT_BOT + fc.INSERT_DEPTH) - max(fc.SEAT, fc.SKIRT_BOT)
    rec("M3x16: no clash, head hidden, full insert engagement",
        v < EPS_VOL and min(recess) >= 0.15 and eng >= fc.INSERT_DEPTH - 1e-6,
        f"overlap {v:.4f}, head recess {min(recess):.2f}-{max(recess):.2f} mm, thread in insert {eng:.1f} mm")


def check_usb(m):
    top = cq.Compound.makeCompound([m["parts"]["Top"], m["parts"]["GlowBand"]])
    r = Ray(top)
    yw = -(fc.SHELL_H - fc.PCB_H) / 4          # mid back wall
    o = P(fc.USB_CX, yw, fc.USB_CZ)
    xp, xm = r.first(o, (1, 0, 0)), r.first(o, (-1, 0, 0))
    zp, zm = r.first(o, (0, 0, 1)), r.first(o, (0, 0, -1))
    w, h = xp + xm, zp + zm
    cx, cz = fc.USB_CX + (xp - xm) / 2, fc.USB_CZ + (zp - zm) / 2
    rec_c = (fc.USB_CX, fc.USB_CZ)
    ok = abs(cx - rec_c[0]) <= 0.5 and abs(cz - rec_c[1]) <= 0.5 and w >= fc.UC["w"] - 0.01 and h >= fc.UC["h"] - 0.01
    rec("USB-C opening (Top + band tongue) centred on receptacle (<=0.5)", ok,
        f"{w:.2f}x{h:.2f} at x {cx:.2f}, z {cz:.2f}; receptacle x {rec_c[0]:.2f}, z {rec_c[1]:.2f}")
    om = fc.solid(fc.usb_overmold())
    v = sum(inter_vol(m["parts"][p], om) for p in ("Top", "GlowBand", "Bottom"))
    c = min(dist(m["parts"][p], om) for p in ("Top", "GlowBand", "Bottom"))
    rec("12.5x7 cable overmold passes the wall", v < EPS_VOL, f"overlap {v:.4f} mm^3, clearance {c:.2f} mm per side")


def check_encoder(m):
    top, knob, ph = m["parts"]["Top"], m["parts"]["Knob"], m["ph"]
    r = Ray(top)
    z = fc.PLATE_TOP - 0.25
    rad = [r.first(P(fc.EN["x"], fc.EN["y"], z), (math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
           for a in range(0, 360, 10)]
    v = inter_vol(top, ph["EC11_bushing"]) + inter_vol(top, ph["EC11_body"])
    db = dist(top, ph["EC11_body"])
    rec("Encoder opening vs bushing (>= 7.4)", 2 * min(rad) >= 7.4 and v < EPS_VOL,
        f"smallest opening {2 * min(rad):.2f} mm (bushing 7.0); body clearance {db:.2f} mm, overlap {v:.4f}")
    kv = inter_vol(knob, ph["EC11_shaft"]) + inter_vol(knob, ph["EC11_bushing"])
    kd = dist(knob, ph["EC11_shaft"])
    rec("Knob bore fits the 6 mm D-shaft", kv < EPS_VOL and 0.03 <= kd <= 0.3,
        f"overlap {kv:.4f}, bore-shaft gap {kd:.2f} mm, knob {fc.KNOB_D:.0f} mm")


def check_oled(m):
    top, ph = m["parts"]["Top"], m["ph"]
    r = Ray(top)
    w = fc.OL["window"]
    cx, cy = w["x"] + w["w"] / 2, w["y"] + w["h"] / 2
    o = P(cx, cy, fc.PLATE_TOP - 0.25)
    xp, xm, yp, ym = (r.first(o, d) for d in ((1, 0, 0), (-1, 0, 0), (0, -1, 0), (0, 1, 0)))
    mw, mh = xp + xm, yp + ym
    v = sum(inter_vol(top, ph[n]) for n in ("OLED_glass", "OLED_board", "OLED_header"))
    ok = abs(mw - (w["w"] + 2 * fc.TOL)) < 0.01 and abs(mh - (w["h"] + 2 * fc.TOL)) < 0.01 and v < EPS_VOL
    rec("OLED window = design window + tol, module recess", ok,
        f"window {mw:.2f}x{mh:.2f} (design {w['w']}x{w['h']}), overlap {v:.4f}; glass {fc.OLED_GLASS_Z1 - fc.PLATE_TOP:+.2f} mm vs plate top")


def check_glow(m):
    band, ph = m["parts"]["GlowBand"], m["ph"]
    r = Ray(band)
    gaps, cover = [], []
    for g in fc.GLOW:
        led = ph[f"glow{g['led']}_led"]
        gaps.append(dist(band, led))
        t = r.first(P(g["x"], g["y"], -fc.LED_T), (0, 0, -1))
        cover.append(t)
    rec("GlowBand: 2.0 tall light gap, pads under each glow LED",
        fc.BAND_H >= 2.0 and all(c < 1.0 for c in cover) and min(gaps) >= fc.TOL - 1e-3,
        f"band {fc.BAND_H:.1f} mm; LED-to-pad air {min(cover):.2f}-{max(cover):.2f} mm")


def check_bottom_pads(m):
    """PCB/build/bottom_pads.json: printed parts vs bottom-side pads, solder joints and lead tails."""
    import json
    if not fc.PADS_FILE.is_file():
        rec("Bottom-side pads clear (PCB/build/bottom_pads.json)", False, "pads file missing")
        return
    pads = json.loads(fc.PADS_FILE.read_text())["pads"]
    zone = fc.THT_TAIL + fc.PAD_CLEAR          # anything this close under the PCB must keep the plan rule
    plan = [fc.solid(fc.box(p["x0"], p["x1"], p["y0"], p["y1"], -zone, 0)) for p in pads]
    tails = [fc.solid(fc.box(p["x0"], p["x1"], p["y0"], p["y1"],
                             -(fc.THT_TAIL if p["through_hole"] else fc.SMD_JOINT), 0)) for p in pads]
    plan_c, tail_c = cq.Compound.makeCompound(plan), cq.Compound.makeCompound(tails)
    under = fc.solid(fc.box(0, fc.PCB_W, 0, fc.PCB_H, -zone, 0))
    rows, ok = [], True
    for name in ("Top", "GlowBand", "Bottom"):
        part = m["parts"][name]
        piece = part.intersect(under)
        if piece.Volume() > 1e-6:                # printed feature within 2.5 mm under the PCB
            dp = dist(piece, plan_c)
            ok &= dp >= fc.PAD_CLEAR - 1e-6
            rows.append(f"{name} under-PCB features {dp:.2f} in plan")
        dt = dist(part, tail_c)
        ok &= dt >= fc.PAD_CLEAR - 1e-6
        rows.append(f"{name} to joints/tails {dt:.2f}")
    rec(f"Bottom-side pads clear >= {fc.PAD_CLEAR} ({len(pads)} pads, THT tails {fc.THT_TAIL})", ok, "; ".join(rows) + " mm")
    # insert boss footprints (full circle, ignoring the chamfer) vs every pad, in plan
    worst = (math.inf, None)
    for sx, sy in fc.SCREWS:
        for p in pads:
            dx = max(p["x0"] - sx, 0, sx - p["x1"])
            dy = max(p["y0"] - sy, 0, sy - p["y1"])
            d = math.hypot(dx, dy) - fc.TOP_BOSS_R
            if d < worst[0]:
                worst = (d, f"{p['ref']}.{p['pad']} vs boss ({sx}, {sy})")
    rec("Insert boss footprints (OD %.1f) >= 0.5 from every pad" % fc.BOSS_OD, worst[0] >= fc.PAD_CLEAR,
        f"closest {worst[0]:.2f} mm: {worst[1]}")
    tb = dist(m["parts"]["Bottom"], cq.Compound.makeCompound(
        [t for t, p in zip(tails, pads) if p["through_hole"]]))
    rec("THT lead tails (2.0) clear the Bottom floor and bosses", tb >= fc.PAD_CLEAR, f"{tb:.2f} mm")


# ------------------------------------------------------------------ printability
def tri_normals(face: cq.Face, tol=0.05):
    vs, tris = face.tessellate(tol, 0.2)
    out = []
    for a, b, c in tris:
        A, B, C = vs[a], vs[b], vs[c]
        n = (B - A).cross(C - A)
        ar = n.Length / 2
        if ar < 1e-6:
            continue
        out.append(((A + B + C) * (1 / 3), n * (1 / (2 * ar)), ar))
    return out


def overhangs(name, s: cq.Shape):
    bad_area, bridges = 0.0, []
    for f in s.Faces():
        tri = tri_normals(f)
        down = [(c, n, a) for c, n, a in tri if n.z < -0.72 and c.z > 0.25]
        if not down:
            continue
        area = sum(a for _, _, a in down)
        flat = all(n.z < -0.98 for _, n, _ in down)
        bb = f.BoundingBox()
        span = max(bb.xlen, bb.ylen)          # conservative bridge length
        if flat:
            bridges.append((span, area, round(bb.center.z, 1)))
        else:
            bad_area += area
    return bad_area, bridges


def thin_walls(s: cq.Shape, limit=1.2, per_face=40):
    r = Ray(s)
    spots = {}
    for f in s.Faces():
        tri = tri_normals(f, 0.1)
        step = max(1, len(tri) // per_face)
        for c, n, a in tri[::step]:
            if a < 0.02:
                continue
            o = (c.x - n.x * 1e-3, c.y - n.y * 1e-3, c.z - n.z * 1e-3)
            hs = [h for h in r.hits(o, (-n.x, -n.y, -n.z)) if h > 2e-3]
            if not hs:
                continue
            # a facet of a concave (hole) surface sits in the air by the chord sagitta: skip that entry hit
            t = (hs[1] - hs[0] if len(hs) > 1 else math.inf) if hs[0] < 0.05 else hs[0]
            if t < limit:
                key = (round(c.x / 3) * 3, round(c.y / 3) * 3, round(c.z / 3) * 3)
                if key not in spots or t < spots[key][0]:
                    spots[key] = (t, (round(c.x, 1), round(c.y, 1), round(c.z, 1)))
    return sorted(spots.values())


def check_printability(printed, m):
    rows, ok_all = [], True
    for name, s in printed.items():
        bad, br = overhangs(name, s)
        big = [b for b in br if b[0] > 10.0]
        ok = bad < 1.0 and not big
        ok_all &= ok
        rows.append(f"{name}: >45deg overhang {bad:.1f} mm^2, bridges {len(br)}"
                    + (f" (max span {max(b[0] for b in br):.1f} mm)" if br else ""))
    rec("Printable without supports (no >45 deg overhang, bridges <= 10 mm)", ok_all, "; ".join(rows))
    mins = []
    for name in ("Top", "GlowBand", "Bottom"):
        sp = thin_walls(m["parts"][name])
        hard = [x for x in sp if x[0] < 0.8]
        mins.append(f"{name} {sp[0][0]:.2f}" if sp else f"{name} ok")
        for t, p in sp[:6]:
            WARN.append(f"{name}: wall {t:.2f} mm near design-frame {p}")
        if hard:
            ok_all = False
    rec("Walls >= 0.8 printable (spots < 1.2 listed as warnings)", all(
        not [x for x in thin_walls(m["parts"][n]) if x[0] < 0.8] for n in ("Top", "GlowBand", "Bottom")),
        "thinnest: " + ", ".join(mins) + " mm (knob knurl ribs excluded)")


def check_mesh_sections():
    """Same idea as verify G4.switch_cutouts: section production/Top.stl through the plate."""
    try:
        import numpy as np
        import trimesh
    except ImportError:
        return
    import shapely.geometry as g
    import shapely.ops as o
    t = trimesh.load(str(fc.PROD / "Top.stl"), force="mesh")
    # print orientation: top face on z=0, so the 1.5 clip zone is z in (0, 1.5)
    segs = trimesh.intersections.mesh_plane(t, (0, 0, 1), (0, 0, 0.8))
    lines = [g.LineString(sg[:, :2]) for sg in np.round(segs, 5) if not np.allclose(sg[0], sg[1])]
    faces = [p for p in o.polygonize(o.unary_union(lines)) if p.area > 1e-6]
    outer = max(faces, key=lambda p: g.Polygon(p.exterior).area)
    holes = []
    for ring in outer.interiors:
        xs, ys = np.array(ring.coords).T
        holes.append((xs.max() - xs.min(), ys.max() - ys.min()))
    sq = [h for h in holes if abs(h[0] - 14.0) < 0.15 and abs(h[1] - 14.0) < 0.15]
    rec("Top.stl section: 9 square 14.0 holes", len(sq) == len(D["keys"]),
        f"{len(sq)} found, sizes {min(min(h) for h in sq):.3f}-{max(max(h) for h in sq):.3f} mm" if sq else "none")


def main():
    if "--no-build" in sys.argv:
        m = fc.build()
        printed = {k: cq.importers.importStep(str(fc.PROD / f"{k}.step")).val() for k in m["parts"]}
    else:
        m = fc.build()
        printed = fc.export_all(m)
    check_envelope(m, printed)
    check_reopen(m, printed)
    check_pocket(m)
    check_interference(m)
    check_switch_cutouts(m)
    check_keycaps(m)
    check_inserts(m)
    check_usb(m)
    check_encoder(m)
    check_oled(m)
    check_glow(m)
    check_bottom_pads(m)
    check_printability(printed, m)
    check_mesh_sections()

    wn = max(len(n) for n, _, _ in RESULTS)
    print(f"\n{'check'.ljust(wn)}  result  detail")
    print(f"{'-' * wn}  ------  {'-' * 40}")
    for n, ok, d in RESULTS:
        print(f"{n.ljust(wn)}  {'PASS' if ok else 'FAIL':6}  {d}")
    if WARN:
        print("\nwarnings:")
        for w in WARN:
            print("  - " + w)
    nf = sum(1 for _, ok, _ in RESULTS if not ok)
    print(f"\n{len(RESULTS) - nf}/{len(RESULTS)} checks pass")
    return 1 if nf else 0


if __name__ == "__main__":
    sys.exit(main())
