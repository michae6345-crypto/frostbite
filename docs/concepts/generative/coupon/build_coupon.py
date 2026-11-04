"""Lantern Ribcage wall coupon: a test piece, not a case change.

Run:  CAD/.venv/bin/python docs/concepts/generative/coupon/build_coupon.py
Writes coupon-wall and coupon-fence as .step/.stl in print orientation, plus build.json.

Everything is modelled in the design frame of CAD/frostbite_case.py (read only, never written):
X = PCB x, Y = -PCB y, Z = 0 at the PCB underside. The section is the left side wall.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True      # importing the case module must leave no files in CAD/

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "CAD"))

import cadquery as cq                # noqa: E402
import frostbite_case as fc          # noqa: E402

# ---------------------------------------------------------------- concept values (README, generate.py)
XL = -(fc.SHELL_W - fc.PCB_W) / 2    # -9.0, outer skin
RIB_DEPTH = 3.0
SKIN_IN = XL + RIB_DEPTH             # -6.0
POCKET_X = -fc.TOL                   # -0.3
CHANNEL_TOP = -0.8
FENCE_GAP = 0.3
FENCE_T = 1.6
FENCE_TOP_SPAN = -1.1                # concept says -0.9, which leaves 0.1 under the channel roof; see README
FENCE_TOP_BOSS = -2.6                # under the PCB, clear of 2.0 lead tails
CHAMFER = 0.4
SEC_Y0, SEC_Y1 = 19.1, 67.0          # PCB y, keeps LED (25.4) and boss (62.1) at their real spacing
CAP = 1.2                            # coupon-only end cap, closes the cut channel
FENCE_Y0, FENCE_Y1 = 20.6, 65.5
# side windows fully inside the section, indices into patterns/lantern_windows.json "side"
WINDOW_IDS = [14, 2, 13, 17, 3, 11, 4, 12, 5, 15, 6, 10]

LED = next(g for g in fc.GLOW if g["led"] == 9)    # x 5.0, y 25.4
BOSS_X, BOSS_Y = -4.65, 62.1
assert (BOSS_X, BOSS_Y) in fc.SCREWS
BASE_BOT = fc.Z_UNDER_FRONT_SCREW    # -16.5, so the kit M3x16 lands exactly as in the real stack
LEAD_PLANE = 0.0                     # PCB underside; lens at -0.84, 1.76 above the pad, per audit


def window_prism(pts):
    """Window cut from the skin into the channel, along +X. pts are (pcb_y, z)."""
    w = cq.Workplane("YZ", origin=(XL - 1, 0, 0)).polyline([(-s, z) for s, z in pts[:-1]]).close()
    return w.extrude(RIB_DEPTH + 2)


def make_wall() -> cq.Workplane:
    y0, y1 = SEC_Y0, SEC_Y1
    body = fc.box(XL, POCKET_X, y0, y1, fc.SKIRT_BOT, fc.PLATE_TOP)
    channel = fc.box(SKIN_IN, POCKET_X + 1, y0 + CAP, y1 - CAP, fc.SKIRT_BOT - 1, CHANNEL_TOP)
    channel = channel.cut(fc.cyl(BOSS_X, BOSS_Y, fc.BOSS_OD / 2, fc.SKIRT_BOT - 2, CHANNEL_TOP + 1))
    body = body.cut(channel)
    pat = json.loads((HERE.parent / "patterns" / "lantern_windows.json").read_text())["side"]
    for i in WINDOW_IDS:
        body = body.cut(window_prism(pat[i]))
    body = chamfer_windows(body)
    body = body.cut(fc.cyl(BOSS_X, BOSS_Y, fc.INSERT_HOLE / 2, fc.SKIRT_BOT - 1, fc.SKIRT_BOT + fc.INSERT_DEPTH))
    body = body.cut(fc.cyl(BOSS_X, BOSS_Y, fc.SCREW_CLR / 2, fc.SKIRT_BOT, fc.SCREW_TIP + 0.4))
    return body


def chamfer_windows(body: cq.Workplane) -> cq.Workplane:
    """Concept check 'sharp bits': 0.4 chamfer on the outer rib edges."""
    sel = cq.selectors.BoxSelector((XL - .01, -SEC_Y1 + .5, -7.8), (XL + .01, -SEC_Y0 - .5, -.7))
    return body.edges(sel).chamfer(CHAMFER)


def make_fence() -> cq.Workplane:
    y0, y1 = SEC_Y0, SEC_Y1
    ring = fc.box(XL + fc.BAND_INSET, 2.0, y0, y1, fc.BAND_BOT, fc.BAND_TOP)
    relief = fc.box(XL + fc.BAND_INSET + fc.RING_LAND, 3.0, y0 - 1, y1 + 1, fc.BAND_TOP - fc.RING_RELIEF, fc.BAND_TOP + 1)
    relief = relief.cut(fc.cyl(BOSS_X, BOSS_Y, fc.BOSS_OD / 2 + 0.5, fc.BAND_TOP - 2, fc.BAND_TOP + 2))
    ring = ring.cut(relief)
    base = fc.box(XL, 2.0, y0, y1, BASE_BOT, fc.BAND_BOT)

    # light bridge + pad, concept lantern_plan(): x -5.7 to LED + 3.5, LED y +- 3.5
    gx, gy = LED["x"], LED["y"]
    px1 = gx + fc.PAD_REACH
    bridge = fc.box(SKIN_IN + FENCE_GAP, px1, gy - fc.PAD_REACH, gy + fc.PAD_REACH, fc.BAND_TOP - fc.RING_RELIEF, fc.PAD_TOP)
    pad_foot = fc.box(2.0, px1, gy - fc.PAD_REACH, gy + fc.PAD_REACH, BASE_BOT, fc.BAND_TOP - fc.RING_RELIEF + .01)

    # fence: band 0.3 to 1.9 inside the cavity outline, wrapping the boss
    r_in, r_out = fc.BOSS_OD / 2 + FENCE_GAP, fc.BOSS_OD / 2 + FENCE_GAP + FENCE_T
    x0 = SKIN_IN + FENCE_GAP
    z0 = fc.BAND_TOP - fc.RING_RELIEF - .01

    def plan(z1):
        outer = fc.box(x0, 3.0, FENCE_Y0, FENCE_Y1, z0, z1).cut(fc.cyl(BOSS_X, BOSS_Y, r_in, z0 - 1, z1 + 1))
        inner = fc.box(x0 + FENCE_T, 4.0, FENCE_Y0 - 1, FENCE_Y1 + 1, z0 - 1, z1 + 1).cut(
            fc.cyl(BOSS_X, BOSS_Y, r_out, z0 - 2, z1 + 2))
        return outer.cut(inner)

    tall = plan(FENCE_TOP_SPAN).intersect(fc.box(-10, POCKET_X, 0, 90, -20, 5))
    low = plan(FENCE_TOP_BOSS)

    # LED pocket: U of 1.75 wide rails open toward the fence. Leads sit on the rails at the PCB
    # underside plane, the lens hangs between them, the back block sets LED x.
    rail_in, rail_out = 3.5 / 2, fc.PAD_REACH
    r1 = fc.box(gx - 2.2, gx + 2.7, gy - rail_out, gy - rail_in, fc.PAD_TOP - .01, LEAD_PLANE)
    r2 = fc.box(gx - 2.2, gx + 2.7, gy + rail_in, gy + rail_out, fc.PAD_TOP - .01, LEAD_PLANE)
    stop = fc.box(gx + 1.5, gx + 2.7, gy - rail_in - .01, gy + rail_in + .01, fc.PAD_TOP - .01, LEAD_PLANE)

    part = base.union(ring).union(pad_foot).union(bridge).union(tall).union(low).union(r1).union(r2).union(stop)
    part = part.cut(fc.cyl(BOSS_X, BOSS_Y, fc.SCREW_CLR / 2, BASE_BOT - 1, fc.BAND_TOP + 1))
    part = part.cut(fc.cyl(BOSS_X, BOSS_Y, fc.CBORE_D / 2, BASE_BOT - 1, fc.SEAT))
    return part


def to_print(s: cq.Shape, flip: bool):
    r = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180) if flip else s
    bb = r.BoundingBox()
    t = (-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin)
    return r.translate(cq.Vector(*t)), t


def main():
    wall, fence = fc.solid(make_wall()), fc.solid(make_fence())
    meta = {"section_pcb_y": [SEC_Y0, SEC_Y1], "window_ids": WINDOW_IDS, "parts": {}}
    for name, s, flip in (("coupon-wall", wall, True), ("coupon-fence", fence, False)):
        p, t = to_print(s, flip)
        cq.exporters.export(p, str(HERE / f"{name}.step"))
        cq.exporters.export(p, str(HERE / f"{name}.stl"), tolerance=0.01, angularTolerance=0.1)
        bb = p.BoundingBox()
        meta["parts"][name] = {"flip_about_x": flip, "translate": t, "solids": len(s.Solids()), "valid": s.isValid(),
                               "volume_mm3": round(s.Volume(), 1), "size_mm": [round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)]}
    meta["interference_mm3"] = round(wall.intersect(fence).Volume(), 4)
    (HERE / "build.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
