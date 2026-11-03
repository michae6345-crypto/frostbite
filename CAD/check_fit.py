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
    for name, z in (("Top", -5.0), ("Bottom", -12.0)):
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
    rec("Switch bodies vs plate", sw < EPS_VOL, f"overlap {sw:.4f} mm^3 (housing 14.0 in a 14.0 cutout, clips in 15.4 pockets)")


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
    # the insert boss is a circle of the side wall: it must stay outside the PCB insertion envelope
    env_edge = [max(-fc.TOL - sx, sx - (fc.PCB_W + fc.TOL)) for sx, _ in fc.SCREWS]
    gap = min(e - fc.BOSS_OD / 2 for e in env_edge)
    hole_wall = min(e - fc.INSERT_HOLE / 2 for e in env_edge)
    rec("Boss OD clear of the PCB insertion envelope", gap >= -1e-6,
        f"boss OD {fc.BOSS_OD} edge to envelope {gap:.2f} mm, insert hole to envelope {hole_wall:.2f} mm")
    env = fc.solid(fc.pocket_prism(fc.SKIRT_BOT, fc.PLATE_UNDER))
    v_env = inter_vol(top, env)
    rec("No Top material inside the PCB envelope below the plate", v_env < EPS_VOL, f"{v_env:.4f} mm^3")
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
    rec("Knob seats at design height on the real shaft", kv < EPS_VOL and 0.03 <= kd <= 0.3,
        f"overlap {kv:.4f}, bore-shaft gap {kd:.2f} mm, knob {fc.KNOB_D:.0f} mm at z {fc.KNOB_Z0:.1f}, "
        f"{fc.KNOB_Z0 - fc.PLATE_TOP:.1f} above the plate, {fc.KNOB_Z0 - (fc.PCB_TOP + fc.EC_BODY[2] + fc.EC_BUSH_H):.1f} above the bushing")


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
    # M1: everything of the band that stands inside the Top needs real clearance
    top = m["parts"]["Top"]
    inside = fc.solid(fc.box(-1, fc.PCB_W + 1, -0.05, fc.PCB_H + 1, fc.BAND_TOP + 0.01, 1))
    riser = band.intersect(inside)
    tongue = band.intersect(fc.solid(fc.box(0, fc.PCB_W, -9, -0.1, fc.BAND_TOP + 0.01, 1)))
    dr, dt = dist(riser, top), dist(tongue, top)
    rec("GlowBand risers clear the Top pocket (M1)", dr >= fc.TOL - 1e-3 and dt >= 0.2 - 1e-3,
        f"pads and riser {dr:.2f} mm to the pocket wall, USB tongue {dt:.2f} mm to the notch")


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
            d = math.hypot(dx, dy) - fc.BOSS_OD / 2
            if d < worst[0]:
                worst = (d, f"{p['ref']}.{p['pad']} vs boss ({sx}, {sy})")
    rec("Insert boss footprints (OD %.1f) >= 0.5 from every pad" % fc.BOSS_OD, worst[0] >= fc.PAD_CLEAR,
        f"closest {worst[0]:.2f} mm: {worst[1]}")
    tb = dist(m["parts"]["Bottom"], cq.Compound.makeCompound(
        [t for t, p in zip(tails, pads) if p["through_hole"]]))
    rec("THT lead tails (2.0) clear the Bottom floor and bosses", tb >= fc.PAD_CLEAR, f"{tb:.2f} mm")


# ------------------------------------------------------------------ assembly path
def shifted_bb(bb, dz):
    return bb.xmin, bb.xmax, bb.ymin, bb.ymax, bb.zmin + dz, bb.zmax + dz


def sweep(moving: dict, fixed: dict, start: float, step: float = 0.5):
    """Move each solid from offset `start` (z) to its seat (0) and intersect every position.

    A discrete sweep along the real straight path: the step is smaller than any moving or fixed
    feature, so nothing can be jumped over. Returns (worst sum at one position, offenders).
    """
    n = int(round(abs(start) / step))
    offs = [start * (1 - i / n) for i in range(n + 1)]
    fb = {k: v.BoundingBox() for k, v in fixed.items()}
    worst, off = 0.0, {}
    for dz in offs:
        total = 0.0
        for mn, ms in moving.items():
            mb = ms.BoundingBox()
            x0, x1, y0, y1, z0, z1 = shifted_bb(mb, dz)
            placed = None
            for fn, fs in fixed.items():
                b = fb[fn]
                if x1 < b.xmin or b.xmax < x0 or y1 < b.ymin or b.ymax < y0 or z1 < b.zmin or b.zmax < z0:
                    continue
                if placed is None:
                    placed = ms.translate(cq.Vector(0, 0, dz))
                v = placed.intersect(fs).Volume()
                if v > EPS_VOL:
                    total += v
                    if v > off.get((mn, fn), (0,))[0]:
                        off[(mn, fn)] = (v, dz)
        worst = max(worst, total)
    return worst, off


def path_groups(m):
    ph = m["ph"]
    rigid = {f"{k['ref']}_rigid": fc.solid(fc.switch_rigid(k["x"], k["y"])) for k in D["keys"]}
    # everything soldered to the PCB before it meets the switches (OLED sits loose in J1, moves with it)
    board = {k: v for k, v in ph.items()
             if k == "PCB" or k.startswith(("XIAO", "EC11", "OLED", "glow")) or k.endswith("_led")}
    pins = {k: v for k, v in ph.items() if k.endswith("_pins")}
    tails = {f"tail_{p['ref']}.{p['pad']}": fc.solid(fc.box(p["x0"], p["x1"], p["y0"], p["y1"], -fc.THT_TAIL, 0))
             for p in fc.bottom_pads() if p["through_hole"]}
    caps = {k: v for k, v in ph.items() if k.endswith("keycap")}
    return rigid, board, pins, tails, caps


def stage(name, moving, fixed, start, step=0.5):
    w, off = sweep(moving, fixed, start, step)
    top3 = sorted(off.items(), key=lambda kv: -kv[1][0])[:3]
    txt = ", ".join(f"{a} into {b} {v[0]:.2f} mm^3 at dz {v[1]:+.1f}" for (a, b), v in top3)
    rec(f"Path: {name}", w < EPS_VOL, f"{len(moving)} solids, dz {start:+.0f} to seat: "
        + ("clear" if not off else f"BLOCKED ({w:.2f} mm^3): {txt}"))
    return w


LEGACY_X = (-3.0, 64.15)      # the blocked design: bosses stood 1.35 mm inside the PCB envelope
LEGACY_Y = (9.0, 62.1)


def legacy_top(top):
    """Today's Top with the old insert bosses added back, as a negative control for the sweep."""
    out = top
    for x in LEGACY_X:
        for y in LEGACY_Y:
            boss = fc.solid(fc.cyl(x, y, 8.7 / 2, fc.SKIRT_BOT, -fc.TOL))
            out = out.fuse(boss)
    return out.clean()


def check_assembly_path(m):
    """Assembly order from CAD/README.md, each step along its real straight path."""
    parts, ph = m["parts"], m["ph"]
    top = parts["Top"]
    rigid, board, pins, tails, caps = path_groups(m)
    # negative control first: this must report a blockage or the test proves nothing
    w, off = sweep({"PCB": ph["PCB"]}, {"Top": legacy_top(top)}, -40.0, 1.0)
    rec("Self-test: sweep FAILS on the old tuck bosses", w > 1.0,
        f"old bosses block the PCB, {w:.1f} mm^3 overlap at the worst step (must be > 0)")

    inserts = {f"insert{i}": fc.solid(fc.cyl(sx, sy, fc.INSERT_HOLE / 2, fc.SKIRT_BOT, fc.SKIRT_BOT + fc.INSERT_DEPTH))
               for i, (sx, sy) in enumerate(fc.SCREWS)}
    stage("1 inserts into Top", inserts, {"Top": top}, -30.0)
    stage("2 switches into plate (no clips)", rigid, {"Top": top}, +30.0)
    stage("3 PCB + soldered parts into Top", board, {"Top": top, **rigid}, -45.0)
    seated = {"Top": top, **rigid, **board, **pins, **tails}
    stage("4 GlowBand onto Top", {"GlowBand": parts["GlowBand"]}, seated, -45.0)
    stage("5 Bottom onto stack", {"Bottom": parts["Bottom"]}, {**seated, "GlowBand": parts["GlowBand"]}, -45.0)
    screws = {}
    for i, (sx, sy) in enumerate(fc.SCREWS):
        screws[f"shank{i}"] = fc.solid(fc.cyl(sx, sy, 1.5, fc.SEAT, fc.SCREW_TIP))
        screws[f"head{i}"] = fc.solid(fc.cyl(sx, sy, fc.HEAD_D / 2, fc.SEAT - fc.HEAD_H, fc.SEAT))
    case = {k: parts[k] for k in ("Top", "GlowBand", "Bottom")}
    stage("6 screws from underneath", screws, case, -40.0)
    enc = {k: v for k, v in ph.items() if k.startswith("EC11")}
    stage("7 keycaps onto stems", caps, {"Top": top, **enc, "OLED_glass": ph["OLED_glass"]}, +30.0)
    stage("8 knob onto shaft", {"Knob": parts["Knob"]}, {"Top": top, **enc, **caps}, +30.0)


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
    check_assembly_path(m)
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
