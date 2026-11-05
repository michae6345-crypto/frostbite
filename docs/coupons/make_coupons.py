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
CORNER_REACH = 4.0                                  # the real corner is cut 4 past the PCB corner
CORNER_PITCH = 13.0
FLANGE_W, FLANGE_T = 9.0, 2.0
CLAMP_T = fc.PLATE_TOP - fc.PLATE_UNDER             # 2.5: the Top plate under the screw head

# coupon 3
STEPS = (0.3, 0.2, 0.4)                             # from the corner out: the real 0.3 corner first
STEP_LEN = 8.5
ARM = STEP_LEN * len(STEPS)
POCKET_WALL = 3.0
POCKET_RIM = 7.6                                    # height above the bed, 1.0 past the PCB underside
USB_MARGIN = 3.0


def text(s: str, x: float, y: float, z: float, angle: float = 0.0, size: float = FONT_SIZE) -> cq.Workplane:
    """Raised label, reading correctly from +z in the print frame."""
    font = {"fontPath": str(FONT)} if FONT.exists() else {"kind": "bold"}
    t = cq.Workplane("XY").text(s, size, EMBOSS, halign="center", valign="center", combine=False, **font)
    if angle:
        t = t.rotate((0, 0, 0), (0, 0, 1), angle)
    return t.translate((x, y, z))


def flip(wp: cq.Workplane) -> cq.Workplane:
    """Top print orientation: plate top on the bed (z = 0), rim up, print x/y = PCB x/y."""
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
def inserts(bottom: cq.Workplane) -> cq.Shape:
    """Three copies of the real back-left Bottom corner, cut from the real part, with a trial hole in each."""
    sx, sy = min(fc.SCREWS)                                     # (-3.0, -3.0)
    edge = (fc.PCB_W - fc.SHELL_W) / 2                          # -7.0, the outer skin
    win = fc.box(edge, CORNER_REACH, edge, CORNER_REACH, fc.Z_UNDER, fc.RIM)
    corner = bottom.intersect(win).union(fc.cyl(sx, sy, fc.INSERT_HOLE / 2, fc.RIM - fc.INSERT_DEPTH, fc.RIM))
    body = None
    for i, d in enumerate(INSERT_TRIALS):
        c = corner.cut(fc.cyl(sx, sy, d / 2, fc.RIM - fc.INSERT_DEPTH, fc.RIM + 1))
        if d == fc.INSERT_HOLE:
            same_as_real("insert corner", c, bottom, win)
        c = c.translate((0, -i * CORNER_PITCH, 0))
        body = c if body is None else body.union(c)
    # label flange, far from the holes, so it cannot change their walls
    y1 = CORNER_REACH + (len(INSERT_TRIALS) - 1) * CORNER_PITCH
    body = body.union(fc.box(CORNER_REACH - 0.5, CORNER_REACH + FLANGE_W, edge, y1, fc.Z_UNDER, fc.Z_UNDER + FLANGE_T))
    for i, d in enumerate(INSERT_TRIALS):
        y = (edge + CORNER_REACH) / 2 + i * CORNER_PITCH
        body = body.union(text(f"{d:.1f}", CORNER_REACH + FLANGE_W / 2, -y, fc.Z_UNDER + FLANGE_T))
    # clamp ring standing in for the Top plate, so an M3x16 reaches its real depth and can be tightened
    ring = (cq.Workplane("XY").circle(4.0).circle(fc.SCREW_CLR / 2).extrude(CLAMP_T)
            .translate((edge - 6.0, -(y1 + edge) / 2, fc.Z_UNDER)))
    return centred(cq.Compound.makeCompound([fc.solid(body), ring.val()]))


# ------------------------------------------------------------------ 3 pocket + USB
def pocket(top: cq.Workplane, bottom: cq.Workplane) -> cq.Shape:
    """Front-left corner around SW7 in one piece: real plate above, Bottom pocket wall stepped along both arms.

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
    same_as_real("plate at SW7", body, top, fc.box(px, px + STEP_LEN, py - STEP_LEN, py, fc.PLATE_UNDER, fc.PLATE_TOP))
    same_as_real("pocket corner", body, bottom, fc.box(px - 0.6, px + STEP_LEN, py - STEP_LEN, py + 0.6, rim, fc.PLATE_UNDER))
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


# ------------------------------------------------------------------ output
def view(s: cq.Shape, az: float, el: float) -> cq.Shape:
    return fc.view(s, az, el)


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
    top, bottom = fc.make_top(), fc.make_bottom()
    export("coupon1_plate", plate(top))
    export("coupon2_inserts", inserts(bottom), az=-60)
    export("coupon3_pocket_usb", pocket(top, bottom))


if __name__ == "__main__":
    main()
