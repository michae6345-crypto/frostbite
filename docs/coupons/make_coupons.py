"""Frostbite test coupons, generated from the real case source (CadQuery).

Run from the repo root:  CAD/.venv/bin/python docs/coupons/make_coupons.py
Writes docs/coupons/*.{step,stl} (print orientation, z = 0 on the bed) and previews/*.svg|png.
Then measure them:       verify/.venv/bin/python docs/coupons/check_coupons.py

Every shared value comes from CAD/frostbite_case.py (which reads design.json), so the coupons follow
the case. This script only reads CAD/: it writes nothing there, and bytecode is turned off so that
importing the case module leaves no __pycache__ behind.

Each coupon is compared with the real part in a window where the two should be identical. A
coupon that has drifted from the case fails here, before anything is exported.

Frames: coupons are modelled in the case's design frame with PCB coordinates. flip() turns the
plate-down ones over the same way print_orient("Top") does, which gives print x = PCB x and
print y = PCB y, so positions stay readable in that frame.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "CAD"))

import cadquery as cq  # noqa: E402

import frostbite_case as fc  # noqa: E402

PV = HERE / "previews"
FONT = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")
EMBOSS = 0.6            # 3 layers at 0.2
FONT_SIZE = 6.5         # digits about 4.7 tall, strokes about 1 wide

KEYS = {k["ref"]: k for k in fc.D["keys"]}

# coupon 2
INSERT_TRIALS = (4.5, 4.7, 4.9)
INSERT_PITCH = 13.0
INSERT_Y_REAL = max(y for _, y in fc.SCREWS)        # the real screw at y 62.1 is the middle hole
INSERT_X = min(x for x, _ in fc.SCREWS)             # -4.65, in the left side wall
WALL_OUT = (fc.PCB_W - fc.SHELL_W) / 2              # -9.0, outer skin of the left wall
FLANGE_W, FLANGE_T = 9.0, 2.0
CLAMP_T = fc.SKIRT_BOT - fc.SEAT                    # 3.6: GlowBand + Bottom under the screw head

# coupon 3
STEPS = (0.3, 0.2, 0.4)                             # from the corner out: the real 0.3 corner first
STEP_LEN = 8.5
ARM = STEP_LEN * len(STEPS)
POCKET_WALL = 3.0
POCKET_RIM = 7.6                                    # height above the bed, 1.0 past the PCB underside
USB_MARGIN = 3.0

# coupon 4
BAND_Y0, BAND_Y1 = 14.0, 57.0                       # clear of the screw reliefs at y 9.0 and 62.1
GLOW = fc.GLOW[0]                                   # LED 9, back left, side pad
# docs/audit/pcb-physical.md: the emitter hangs about 0.84 below the PCB, not the 1.78 the CAD
# placeholder uses, so the real air gap above the pad is about 1.76, not 0.82.
LED_DROP_REAL = 0.84
LED_GAP = -fc.PAD_TOP - LED_DROP_REAL               # 1.76
CAP_T = 1.8                                         # LED 1.78 tall: back flush, emitter at the cap face


def text(s: str, x: float, y: float, z: float, angle: float = 0.0, size: float = FONT_SIZE) -> cq.Workplane:
    """Raised label, reading correctly from +z in the print frame."""
    font = {"fontPath": str(FONT)} if FONT.exists() else {"kind": "bold"}
    t = cq.Workplane("XY").text(s, size, EMBOSS, halign="center", valign="center", combine=False, **font)
    if angle:
        t = t.rotate((0, 0, 0), (0, 0, 1), angle)
    return t.translate((x, y, z))


def flip(wp: cq.Workplane) -> cq.Workplane:
    """Top-style print orientation: plate top on the bed (z = 0), rim up, print x/y = PCB x/y."""
    return wp.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, fc.PLATE_TOP))


def centred(s: cq.Shape) -> cq.Shape:
    bb = s.BoundingBox()
    return s.translate(cq.Vector(-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


def same_as_real(name: str, coupon: cq.Workplane, real: cq.Workplane, window: cq.Workplane) -> None:
    """Coupon and real part must be the same solid inside the window (both in the design frame)."""
    a, b = coupon.intersect(window), real.intersect(window)
    extra = a.cut(b).val().Volume() if a.val().Volume() else 0.0
    lost = b.cut(a).val().Volume()
    print(f"same as real, {name}: real {b.val().Volume():.1f} mm^3 in window, "
          f"coupon extra {extra:.4f}, coupon missing {lost:.4f}")
    if b.val().Volume() < 1.0 or extra > 0.01 or lost > 0.01:
        raise SystemExit(f"{name}: coupon differs from the real part")


def cut_switch(body: cq.Workplane, x: float, y: float, cutout: float) -> cq.Workplane:
    """The same two cuts as make_top(), with the cutout size as a parameter."""
    body = body.cut(fc.cbox(x, y, cutout, cutout, fc.PLATE_UNDER - 1, fc.PLATE_TOP + 1))
    return body.cut(fc.cbox(x, y, fc.CLIP_POCKET, fc.CLIP_POCKET, fc.PLATE_UNDER - 1, fc.PLATE_TOP - fc.PLATE_T_CLIP))


# ------------------------------------------------------------------ 1 plate
def plate(top: cq.Workplane) -> cq.Shape:
    """SW1-SW6 at their real positions: four real cutouts, then 13.9 and 14.1 in the third column."""
    half = fc.CLIP_POCKET / 2 + (19.05 - fc.CLIP_POCKET) / 2     # half a pitch
    strip = 7.0
    sizes = {"SW1": 14.0, "SW2": 14.0, "SW4": 14.0, "SW5": 14.0, "SW3": 13.9, "SW6": 14.1}
    x0, x1 = KEYS["SW1"]["x"] - half, KEYS["SW3"]["x"] + half
    y0, y1 = KEYS["SW1"]["y"] - half, KEYS["SW4"]["y"] + half
    body = fc.box(x0, x1, y0 - strip, y1 + strip, fc.PLATE_UNDER, fc.PLATE_TOP)
    for ref, size in sizes.items():
        body = cut_switch(body, KEYS[ref]["x"], KEYS[ref]["y"], size)
    window = fc.box(x0, KEYS["SW2"]["x"] + half, y0, y1, fc.PLATE_UNDER, fc.PLATE_TOP)
    same_as_real("plate 2x2", body, top, window)
    body = flip(body)
    for ref, size in sizes.items():
        ly = y0 - strip / 2 if KEYS[ref]["row"] == 0 else y1 + strip / 2
        body = body.union(text(f"{size:.1f}", KEYS[ref]["x"], ly, fc.PLATE_T))
    return centred(fc.solid(body))


# ------------------------------------------------------------------ 2 inserts
def inserts(top: cq.Workplane) -> cq.Shape:
    """A length of the real side wall: same width, height, hole axis and blind screw hole."""
    ys = [INSERT_Y_REAL + (i - 1) * INSERT_PITCH for i in range(3)]
    y0, y1 = ys[0] - INSERT_PITCH / 2, ys[-1] + INSERT_PITCH / 2
    body = fc.box(WALL_OUT, -fc.TOL, y0, y1, fc.SKIRT_BOT, fc.PLATE_TOP)
    for d, y in zip(INSERT_TRIALS, ys):
        body = body.cut(fc.cyl(INSERT_X, y, d / 2, fc.SKIRT_BOT - 1, fc.SKIRT_BOT + fc.INSERT_DEPTH))
        body = body.cut(fc.cyl(INSERT_X, y, fc.SCREW_CLR / 2, fc.SKIRT_BOT, fc.SCREW_TIP + 0.4))
    window = fc.box(WALL_OUT, -fc.TOL, INSERT_Y_REAL - INSERT_PITCH / 2, INSERT_Y_REAL + INSERT_PITCH / 2,
                    fc.SKIRT_BOT, fc.PLATE_TOP)
    same_as_real("insert wall", body, top, window)
    body = flip(body)
    # label flange at the plate end, far from the holes, so it cannot change their walls
    body = body.union(cq.Workplane("XY").box(FLANGE_W, y1 - y0, FLANGE_T, centered=False)
                      .translate((-fc.TOL, y0, 0)))
    for d, y in zip(INSERT_TRIALS, ys):
        body = body.union(text(f"{d:.1f}", -fc.TOL + FLANGE_W / 2, y, FLANGE_T))
    # spacer standing in for GlowBand + Bottom, so an M3x16 reaches its real depth and can be tightened
    spacer = (cq.Workplane("XY").circle(4.0).circle(fc.SCREW_CLR / 2).extrude(CLAMP_T)
              .translate((WALL_OUT - 7.0, INSERT_Y_REAL, 0)))
    bar = fc.solid(body)
    return centred(cq.Compound.makeCompound([bar, spacer.val()]))


# ------------------------------------------------------------------ 3 pocket + USB
def pocket(top: cq.Workplane) -> cq.Shape:
    """Front-left corner of the Top around SW7, with the pocket walls stepped along both arms.

    The real switch cutout stays at its real distance from the walls. A switch clipped into it holds
    the PCB where the real case will, so the gaps at the steps mean something. An L alone has no
    opposite wall: a loose board would just slide into the corner and show nothing.
    """
    sw = KEYS["SW7"]
    px, py = 0.0, fc.PCB_H                                       # the PCB corner
    wall = max(STEPS) + POCKET_WALL
    flange = 7.5
    rim = fc.PLATE_TOP - POCKET_RIM
    body = fc.box(px - wall - flange, px + ARM, py - ARM, py + wall + flange, fc.PLATE_UNDER, fc.PLATE_TOP)
    body = body.union(fc.box(px - wall, px + ARM, py - ARM, py + wall, rim, fc.PLATE_TOP))
    room = fc.box(px, px + ARM + 1, py - ARM - 1, py, rim - 1, fc.PLATE_UNDER)
    for i, t in enumerate(STEPS):
        room = room.union(fc.box(px - t, px, py - (i + 1) * STEP_LEN, py - i * STEP_LEN, rim - 1, fc.PLATE_UNDER))
        room = room.union(fc.box(px + i * STEP_LEN, px + (i + 1) * STEP_LEN, py, py + t, rim - 1, fc.PLATE_UNDER))
    room = room.union(fc.box(px - STEPS[0], px, py, py + STEPS[0], rim - 1, fc.PLATE_UNDER))   # the real corner
    room = room.union(fc.box(px - 1, px + ARM + 1, py - ARM - 1, py - ARM, rim - 1, fc.PLATE_UNDER))
    body = body.cut(room)
    body = cut_switch(body, sw["x"], sw["y"], fc.CUTOUT)
    window = fc.box(px - wall, px + STEP_LEN, py - STEP_LEN, py + wall, rim, fc.PLATE_TOP)
    same_as_real("pocket corner", body, top, window)
    body = flip(body)
    lz = fc.PLATE_T
    for i, t in enumerate(STEPS):
        mid = (i + 0.5) * STEP_LEN - 0.3        # keeps the outer label on the flange
        body = body.union(text(f"{t:.1f}", px - wall - flange / 2, py - mid, lz, 90, 5.5))
        body = body.union(text(f"{t:.1f}", px + mid, py + wall + flange / 2, lz, 0, 5.5))
    # USB-C window copy: the real size and wall depth, axis vertical so it needs no bridge
    depth = (fc.SHELL_H - fc.PCB_H) / 2 - fc.TOL                  # 6.7, shell skin to pocket
    bw, bh = fc.UC["h"] + 2 * USB_MARGIN, fc.UC["w"] + 2 * USB_MARGIN
    bx = px - wall - flange - bw
    by = py - ARM
    block = cq.Workplane("XY").box(bw, bh, depth, centered=False).translate((bx, by, 0))
    hole = (cq.Workplane("XY").box(fc.UC["h"], fc.UC["w"], depth + 2, centered=False)
            .translate((bx + USB_MARGIN, by + USB_MARGIN, -1)))
    return centred(fc.solid(body.union(block.cut(hole))))


# ------------------------------------------------------------------ 4 glow
def glow_band(band: cq.Workplane) -> tuple[cq.Shape, cq.Workplane]:
    """A slice of the real GlowBand, cut by intersection, so it cannot differ. Real print orientation."""
    cut = fc.box(-20, 20, BAND_Y0, BAND_Y1, fc.BAND_BOT - 1, 1)
    section = band.intersect(cut)
    return centred(fc.solid(section)), section


def glow_cap() -> cq.Shape:
    """PCB stand-in: holds one LED over the real pad spot, and doubles as a torch aperture."""
    x0, x1, y0, y1 = -8.0, 11.0, 15.0, 36.0
    cap = cq.Workplane("XY").box(x1 - x0, y1 - y0, CAP_T, centered=False).translate((x0, y0, 0))
    window = (cq.Workplane("XY").box(6.3, 3.0, CAP_T + 2, centered=(True, True, False))
              .translate((GLOW["x"], GLOW["y"], -1)))
    cap = cap.cut(window)
    for fy in (y0, y1 - 2.0):           # feet stand on the riser (x 0..2), away from the pad
        cap = cap.union(cq.Workplane("XY").box(fc.RISER_T, 2.0, LED_GAP, centered=False)
                        .translate((0, fy, CAP_T)))
    return centred(fc.solid(cap))


# ------------------------------------------------------------------ output
def view(s: cq.Shape, az: float, el: float) -> cq.Shape:
    return fc._view(s, az, el)


def export(name: str, s: cq.Shape, az: float = 30, el: float = 40) -> None:
    cq.exporters.export(s, str(HERE / f"{name}.step"))
    cq.exporters.export(s, str(HERE / f"{name}.stl"), tolerance=0.01, angularTolerance=0.1)
    svg = PV / f"{name}.svg"
    opts = dict(width=900, height=640, marginLeft=60, marginTop=60, showAxes=False, strokeWidth=0.25,
                showHidden=False, projectionDir=(0, 0, 1))
    cq.exporters.export(view(s, az, el), str(svg), opt=opts)
    subprocess.run(["qlmanage", "-t", "-s", "900", "-o", str(PV), str(svg)],
                   check=False, capture_output=True, timeout=60)
    bb = s.BoundingBox()
    print(f"{name}: {bb.xlen:.2f} x {bb.ylen:.2f} x {bb.zlen:.2f} mm, {s.Volume() / 1000:.2f} cm^3")


def main() -> None:
    PV.mkdir(exist_ok=True)
    top, band = fc.make_top(), fc.make_band()
    export("coupon1_plate", plate(top))
    export("coupon2_inserts", inserts(top), az=-60)
    export("coupon3_pocket_usb", pocket(top))
    gb, section = glow_band(band)
    export("coupon4_glow_band", gb)
    export("coupon4_glow_cap", glow_cap())
    print(f"LED gap in the cap {LED_GAP:.2f} mm (audit value; the CAD placeholder gives 0.82)")


if __name__ == "__main__":
    main()
