# frostbite case in cadquery
# pip install cadquery==2.8.0, then python CAD/frostbite_case.py
# writes production/*.step + *.stl and CAD/frostbite.step
#
# x = pcb x, y = -pcb y, z = 0 at the pcb underside. all mm

import math
from pathlib import Path

import cadquery as cq

CAD = Path(__file__).resolve().parent
PROD = CAD.parent / "production"

TOL = 0.3
PCB_W, PCB_H, PCB_T = 61.15, 83.15, 1.6
SHELL_W, SHELL_H, CORNER = 75.15, 97.15, 3
MARGIN_Y = (SHELL_H - PCB_H) / 2

KEYS = [(x, y) for y in (33.525, 52.575, 71.625) for x in (11.525, 30.575, 49.625)]
SCREWS = [(-3.0, -3.0), (64.15, -3.0), (-3.0, 86.15), (64.15, 86.15)]

# switch plate
PCB_TOP = PCB_T
PLATE_TOP = PCB_TOP + 5.0
PLATE_T_CLIP = 1.5
PLATE_T = 2.5
PLATE_UNDER = PLATE_TOP - PLATE_T
CUTOUT = 14.0
CLIP_POCKET = 15.4
RIM = PLATE_UNDER

# m3x16 from the top into heat set inserts, the screw length sets the case height
INSERT_HOLE, INSERT_DEPTH = 4.7, 4.0
SCREW_CLR, SCREW_LEN = 3.4, 16.0
SCREW_TIP = PLATE_TOP - SCREW_LEN
BLIND_CLR, SKIN = 0.4, 1.0
Z_UNDER = SCREW_TIP - BLIND_CLR - SKIN
FLOOR_T = 2.5
Z_FLOOR = Z_UNDER + FLOOR_T
GROOVE_Z, GROOVE_D, GROOVE_UP = -3.35, 0.6, 0.9

# oled, header plastic comes off and it sits on the OLEDSupport
OLED_WINDOW = (6.0, 7.25, 30.0, 11.5)
OLED_MODULE = (2.5, 7.0, 38.0, 12.0)
OLED_PIN_X, OLED_PIN_Y, OLED_PITCH = 39.0, 13.0, 2.54
OLED_GAP = 1.8
OLED_BOARD_T, OLED_GLASS_T = 1.2, 1.45
OLED_BOARD_Z0 = PCB_TOP + OLED_GAP
OLED_BOARD_Z1 = OLED_BOARD_Z0 + OLED_BOARD_T
OLED_GLASS_Z1 = OLED_BOARD_Z1 + OLED_GLASS_T
OLED_RECESS_TOP = PLATE_TOP - 1.0
OLED_WIN_CLR_X, OLED_WIN_CLR_Y = 0.5, 0.74
OLED_RECESS_FAR, OLED_RECESS_Y = 1.1, 0.8
SUPPORT_FAR = (3.5, 9.5, 7.6, 21.1)
SUPPORT_NEAR = (32.2, 37.4, 8.0, 21.1)
SUPPORT_RAIL = (3.5, 37.4, 19.5, 21.1)

# encoder
EN_X, EN_Y = 49.15, 13.0
EC_BODY = (11.7, 12.0, 4.5)
EC_BUSH_D, EC_BUSH_H = 7.0, 7.0
EC_SHAFT_D, EC_SHAFT_FLAT, EC_SHAFT_TIP = 6.0, 4.5, PCB_TOP + 24.5
EC_SHAFT_D_LEN = 10.0
EC_OPEN = (12.98, 16.0, 2.0)

# knob
KNOB_D, KNOB_H, KNOB_BORE_DEPTH = 18.0, 15.0, 12.3
KNOB_Z0 = PCB_TOP + EC_BODY[2] + EC_BUSH_H + 1.0
KNOB_RELIEF_D, KNOB_RELIEF_H = 7.6, 3.2

# xiao, sits under the pcb
MCU_X, MCU_W, MCU_H = 12.1, 17.8, 21.0
XIAO_T = 1.2
USB_W, USB_H, USB_OVERHANG = 8.94, 3.26, 1.4
USB_CX = MCU_X + MCU_W / 2
USB_CZ = -XIAO_T - USB_H / 2
USB_CUT_W, USB_CUT_H = 13.5, 8.0
USB_TONGUE_GAP = 0.2

BLACK = (0.08, 0.08, 0.09, 1)
WHITE = (0.97, 0.97, 0.97, 1)


def Y(y):
    return -y


def box(x0, x1, y0, y1, z0, z1):
    return (cq.Workplane("XY")
            .box(x1 - x0, y1 - y0, z1 - z0, centered=False)
            .translate((x0, Y(y1), z0)))


def cbox(x, y, w, h, z0, z1):
    return box(x - w / 2, x + w / 2, y - h / 2, y + h / 2, z0, z1)


def cyl(x, y, r, z0, z1):
    return cq.Workplane("XY", origin=(x, Y(y), z0)).circle(r).extrude(z1 - z0)


def rrect(x, y, w, h, r, z0, z1):
    s = cq.Workplane("XY", origin=(x, Y(y), z0)).rect(w, h).extrude(z1 - z0)
    return s.edges("|Z").fillet(r) if r > 0 else s


def shell_prism(z0, z1):
    return rrect(PCB_W / 2, PCB_H / 2, SHELL_W, SHELL_H, CORNER, z0, z1)


def d_profile(r, flat, z0, z1, x, y):
    c = cq.Workplane("XY", origin=(x, Y(y), z0)).circle(r).extrude(z1 - z0)
    return c.intersect(box(x - r - 1, x + flat, y - r - 1, y + r + 1, z0 - 1, z1 + 1))


def solid(wp):
    s = wp.val()
    if isinstance(s, cq.Compound) and len(s.Solids()) == 1:
        s = s.Solids()[0]
    return s


def make_top():
    body = shell_prism(PLATE_UNDER, PLATE_TOP)
    for x, y in KEYS:
        body = body.cut(cbox(x, y, CUTOUT, CUTOUT, PLATE_UNDER - 1, PLATE_TOP + 1))
        body = body.cut(cbox(x, y, CLIP_POCKET, CLIP_POCKET, PLATE_UNDER - 1, PLATE_TOP - PLATE_T_CLIP))

    wx, wy, ww, wh = OLED_WINDOW
    body = body.cut(box(wx - OLED_WIN_CLR_X, wx + ww + OLED_WIN_CLR_X,
                        wy - OLED_WIN_CLR_Y, wy + wh + OLED_WIN_CLR_Y,
                        OLED_RECESS_TOP - 0.5, PLATE_TOP + 1))
    mx, my, mw, mh = OLED_MODULE
    body = body.cut(box(mx - OLED_RECESS_FAR, mx + mw + TOL, my - OLED_RECESS_Y, my + mh + OLED_RECESS_Y,
                        PLATE_UNDER - 1, OLED_RECESS_TOP))

    body = body.cut(rrect(EN_X, EN_Y, EC_OPEN[0], EC_OPEN[1], EC_OPEN[2], PLATE_UNDER - 1, PLATE_TOP + 1))
    for x, y in SCREWS:
        body = body.cut(cyl(x, y, SCREW_CLR / 2, PLATE_UNDER - 1, PLATE_TOP + 1))

    # tongue that closes the usb notch from above
    return body.union(box(USB_CX - USB_CUT_W / 2 + USB_TONGUE_GAP, USB_CX + USB_CUT_W / 2 - USB_TONGUE_GAP,
                          -MARGIN_Y, -TOL, USB_CZ + USB_CUT_H / 2, PLATE_UNDER))


def make_bottom():
    # groove round the side is two chamfers so it prints without supports
    low = shell_prism(Z_UNDER, GROOVE_Z).faces(">Z").edges().chamfer(GROOVE_D)
    high = shell_prism(GROOVE_Z, RIM).faces("<Z").edges().chamfer(GROOVE_UP, GROOVE_D)
    body = low.union(high).cut(box(-TOL, PCB_W + TOL, -TOL, PCB_H + TOL, Z_FLOOR, RIM + 1))
    for x, y in SCREWS:
        body = body.cut(cyl(x, y, INSERT_HOLE / 2, RIM - INSERT_DEPTH, RIM + 1))
        body = body.cut(cyl(x, y, SCREW_CLR / 2, SCREW_TIP - BLIND_CLR, RIM))
    return body.cut(box(USB_CX - USB_CUT_W / 2, USB_CX + USB_CUT_W / 2, -MARGIN_Y - 2, 1.0,
                        USB_CZ - USB_CUT_H / 2, RIM + 1))


def make_oled_support():
    z0, z1 = PCB_TOP, OLED_BOARD_Z0
    return box(*SUPPORT_FAR, z0, z1).union(box(*SUPPORT_NEAR, z0, z1)).union(box(*SUPPORT_RAIL, z0, z1))


def make_knob():
    n, ro, ri = 30, KNOB_D / 2, KNOB_D / 2 - 0.5
    pts = []
    for i in range(2 * n):
        a = math.pi * i / n
        r = ro if i % 2 == 0 else ri
        pts.append((r * math.cos(a), r * math.sin(a)))
    knob = cq.Workplane("XY", origin=(EN_X, Y(EN_Y), KNOB_Z0)).polyline(pts).close().extrude(KNOB_H)
    knob = knob.faces(">Z").edges().chamfer(0.6)
    knob = knob.cut(cyl(EN_X, EN_Y - 5.5, 0.8, KNOB_Z0 + KNOB_H - 0.6, KNOB_Z0 + KNOB_H + 1))
    bore = d_profile(3.1, EC_SHAFT_FLAT - EC_SHAFT_D / 2 + 0.1, KNOB_Z0 - 1, KNOB_Z0 + KNOB_BORE_DEPTH, EN_X, EN_Y)
    knob = knob.cut(cyl(EN_X, EN_Y, KNOB_RELIEF_D / 2, KNOB_Z0 - 1, KNOB_Z0 + KNOB_RELIEF_H))
    return knob.cut(bore)


# rough models of the bought parts, just for the assembly
def placeholders():
    ph = {"PCB": box(0, PCB_W, 0, PCB_H, 0, PCB_T)}

    for i, (x, y) in enumerate(KEYS, 1):
        sw = cbox(x, y, 14.0, 14.0, PCB_TOP, PLATE_TOP)
        sw = sw.union(cbox(x, y, 14.9, 5.0, PLATE_TOP - PLATE_T_CLIP - 0.8, PLATE_TOP - PLATE_T_CLIP))
        sw = sw.union(cbox(x, y, 15.6, 15.6, PLATE_TOP, PLATE_TOP + 6.6))
        sw = sw.union(cbox(x, y, 4.0, 4.0, PLATE_TOP + 6.6, PLATE_TOP + 10.2))
        ph[f"SW{i}_switch"] = sw
        pins = cyl(x, y, 3.85 / 2, PCB_TOP - 2.8, PCB_TOP)
        for dx, dy, dd in ((-5.08, 0, 1.7), (5.08, 0, 1.7), (-3.81, -2.54, 1.5), (2.54, -5.08, 1.5)):
            pins = pins.union(cyl(x + dx, y + dy, dd / 2, PCB_TOP - 3.3, PCB_TOP))
        ph[f"SW{i}_pins"] = pins
        ph[f"SW{i}_keycap"] = (cq.Workplane("XY", origin=(x, Y(y), PLATE_TOP + 6.0)).rect(18.2, 18.2)
                               .workplane(offset=7.6).rect(12.7, 12.7).loft())

    mx, my, mw, mh = OLED_MODULE
    wx, wy, ww, wh = OLED_WINDOW
    pins = None
    for i in range(4):
        p = cbox(OLED_PIN_X, OLED_PIN_Y + (i - 1.5) * OLED_PITCH, 0.64, 0.64, -2.0, OLED_BOARD_Z1)
        pins = p if pins is None else pins.union(p)
    ph["OLED_pins"] = pins
    ph["OLED_board"] = box(mx, mx + mw, my, my + mh, OLED_BOARD_Z0, OLED_BOARD_Z1)
    ph["OLED_glass"] = box(wx, wx + ww, wy, wy + wh, OLED_BOARD_Z1, OLED_GLASS_Z1)

    ph["XIAO_board"] = box(MCU_X, MCU_X + MCU_W, 0, MCU_H, -XIAO_T, 0)
    ph["XIAO_usb"] = box(USB_CX - USB_W / 2, USB_CX + USB_W / 2, -USB_OVERHANG, 7.35 - USB_OVERHANG,
                         -XIAO_T - USB_H, -XIAO_T)
    ph["XIAO_shield"] = cbox(USB_CX, 13.5, 12.0, 11.0, -XIAO_T - 1.0, -XIAO_T)

    ph["EC11_body"] = cbox(EN_X, EN_Y, EC_BODY[0], EC_BODY[1], PCB_TOP, PCB_TOP + EC_BODY[2]).union(
        cbox(EN_X, EN_Y, 12.5, 1.5, PCB_TOP - 3.5, PCB_TOP + 1.5))
    ph["EC11_bushing"] = cyl(EN_X, EN_Y, EC_BUSH_D / 2, PCB_TOP + EC_BODY[2], PCB_TOP + EC_BODY[2] + EC_BUSH_H)
    ph["EC11_shaft"] = cyl(EN_X, EN_Y, EC_SHAFT_D / 2, PCB_TOP + EC_BODY[2] + EC_BUSH_H,
                           EC_SHAFT_TIP - EC_SHAFT_D_LEN).union(
        d_profile(EC_SHAFT_D / 2, EC_SHAFT_FLAT - EC_SHAFT_D / 2, EC_SHAFT_TIP - EC_SHAFT_D_LEN,
                  EC_SHAFT_TIP, EN_X, EN_Y))
    pins = None
    for dx, dy in ((-2.5, 7.5), (0, 7.5), (2.5, 7.5), (-2.5, -7.0), (2.5, -7.0)):
        p = cyl(EN_X + dx, EN_Y + dy, 0.5, PCB_TOP - 3.5, PCB_TOP)
        pins = p if pins is None else pins.union(p)
    ph["EC11_pins"] = pins
    return ph


def ph_color(name):
    if name == "PCB":
        return (0.10, 0.35, 0.20, 1)
    if name.endswith("keycap"):
        return WHITE
    if name.endswith("switch"):
        return (0.95, 0.80, 0.15, 1)
    if name.startswith("OLED_glass"):
        return (0.05, 0.05, 0.08, 1)
    if name.startswith("XIAO") or name.startswith("OLED"):
        return (0.15, 0.25, 0.55, 1)
    return (0.6, 0.6, 0.62, 1)


def to_desk(s):
    return s.translate(cq.Vector(0, 0, -Z_UNDER))


def print_orient(name, s):
    if name == "Top":
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180)
    bb = s.BoundingBox()
    return s.translate(cq.Vector(-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


if __name__ == "__main__":
    parts = {"Top": make_top(), "Bottom": make_bottom(), "Knob": make_knob(), "OLEDSupport": make_oled_support()}
    parts = {k: solid(v) for k, v in parts.items()}

    asm = cq.Assembly(name="frostbite")
    for name, s in parts.items():
        asm.add(to_desk(s), name=name, color=cq.Color(*BLACK))
        p = print_orient(name, s)
        cq.exporters.export(p, str(PROD / f"{name}.step"))
        cq.exporters.export(p, str(PROD / f"{name}.stl"), tolerance=0.01, angularTolerance=0.1)
    for name, wp in placeholders().items():
        asm.add(to_desk(solid(wp)), name=name, color=cq.Color(*ph_color(name)))
    asm.export(str(CAD / "frostbite.step"))
