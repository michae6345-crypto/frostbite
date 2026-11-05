"""Frostbite case, generated from design.json with CadQuery.

Run from the repo root: CAD/.venv/bin/python CAD/frostbite_case.py
Writes production/{Top,Bottom,OLEDSupport,Knob}.{step,stl} in print orientation,
CAD/frostbite-assembly.step on the desk with the PCB and placeholder parts,
CAD/positions.json and CAD/previews/*.svg with PNG copies.

Design frame, used for every part: X = PCB x, Y = -PCB y (back edge y=0 is +Y, the user is at -Y),
Z = 0 at the PCB underside. The assembly STEP is this frame raised so the Bottom underside is on Z = 0.

Stack in the design frame (mm):
  9.60  screw head top
  6.60  Top face = MX plate top (PCB top + 5.0, set by the switch); screw heads seat here
  5.10  plate underside at the switch clips (1.5 thick at the 14.0 cutouts)
  4.10  plate underside elsewhere (2.5 thick) = Bottom rim, heat-set inserts press in from here
  0..1.6 PCB
 -8.30  Bottom floor top
 -9.40  screw tip (M3x16 from the plate top)
 -9.80  blind hole end
-10.80  Bottom underside, so the case is 17.4 tall

The PCB drops into the Bottom from above, so nothing printed may stand inside the PCB insertion
envelope (PCB + tolerance). That is why the inserts sit in the tray corners, outside the PCB corners.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import cadquery as cq

CAD = Path(__file__).resolve().parent
ROOT = CAD.parent
PROD = ROOT / "production"
D = json.loads((ROOT / "design.json").read_text())

TOL = D["case"]["tolerance"]                    # 0.3 per side where print meets PCB
PCB_W, PCB_H, PCB_T = D["pcb"]["w"], D["pcb"]["h"], 1.6
SH = D["case"]["shell"]
SHELL_W, SHELL_H, CORNER = SH["w"], SH["h"], SH["corner"]
MARGIN_Y = (SHELL_H - PCB_H) / 2                 # front and back wall thickness

PCB_TOP = PCB_T
PLATE_TOP = PCB_TOP + 5.0                        # MX: plate top 5.0 above PCB top
PLATE_T_CLIP = 1.5
PLATE_T = 2.5
PLATE_UNDER = PLATE_TOP - PLATE_T                # 4.1, leaves 2.5 for THT diodes lying flat
CUTOUT = 14.0
CLIP_POCKET = 15.4                               # clip span 14.9 + 0.5
RIM = PLATE_UNDER                                # Bottom rim, the plate rests on it

INSERT_HOLE, INSERT_DEPTH = 4.7, 4.0
SCREW_CLR, SCREW_LEN = 3.4, 16.0
HEAD_D, HEAD_H = 5.5, 3.0
SEAT = PLATE_TOP                                 # heads sit on the plate top and show
SCREW_TIP = SEAT - SCREW_LEN                     # -9.4
BLIND_CLR, SKIN = 0.4, 1.0                       # hole past the tip, floor left under the hole
Z_UNDER = SCREW_TIP - BLIND_CLR - SKIN           # -10.8, this sets the case height
FLOOR_T = 2.5
Z_FLOOR = Z_UNDER + FLOOR_T                      # -8.3
CASE_H = PLATE_TOP - Z_UNDER                     # 17.4
GROOVE_Z, GROOVE_D, GROOVE_UP = -3.35, 0.6, 0.9  # V groove round the Bottom, upper flank steep so it prints
SCREWS = [(float(p["x"]), float(p["y"])) for p in D["case"]["screws"]["positions"]]
BOSS_OD = float(D["case"]["screws"]["boss_od"])  # 7.6 = insert hole 4.7 + 2 x 1.45 wall, in the tray corner
# Lead tails and solder joints on the PCB underside that the case must clear
PADS_FILE = ROOT / "PCB" / "build" / "bottom_pads.json"
THT_TAIL, SMD_JOINT, PAD_CLEAR = 2.0, 0.3, 0.5


# OLED. The header plastic comes off: the module rests on the printed OLEDSupport, which sets the height.
OL = D["oled"]
SUP = D["case"]["oled_support"]
OLED_GAP = float(SUP["module_gap"])              # 1.8, also the printed height of the OLEDSupport
OLED_BOARD_T, OLED_GLASS_T = 1.2, 1.45
OLED_BOARD_Z0 = PCB_TOP + OLED_GAP               # 3.4
OLED_BOARD_Z1 = OLED_BOARD_Z0 + OLED_BOARD_T     # 4.6
OLED_GLASS_Z1 = OLED_BOARD_Z1 + OLED_GLASS_T     # 6.05, 0.55 below the plate top
OLED_LIP_T = 1.0
OLED_RECESS_TOP = PLATE_TOP - OLED_LIP_T         # 5.6, 1.0 of air above the module board
# The module is soldered to J1 before it meets the Top, so the opening must take its misalignment:
# about +/-1 deg of yaw (pin play in the J1 holes) and +/-0.1 shift. Far end also leaves ribbon room.
OLED_WIN_CLR_X, OLED_WIN_CLR_Y = 0.5, 0.74       # window 31.0 x 12.98 around the 30 x 11.5 design window
OLED_RECESS_FAR, OLED_RECESS_Y = 1.1, 0.8        # recess past the far end / past each long side
OLED_YAW_DEG, OLED_SHIFT = 1.0, 0.1              # misalignment the path check must survive
# x0, x1, y0, y1 in PCB coords, on free PCB top: U1 pad rows at x 10.5-14.2 and 25.8-31.4, y up to 19.0; J1 pads from x 38.15
SUPPORT_FAR, SUPPORT_NEAR = (3.5, 9.5, 7.6, 21.1), (32.2, 37.4, 8.0, 21.1)
SUPPORT_RAIL = (3.5, 37.4, 19.5, 21.1)
RIBBON_UP, RIBBON_OUT = 0.8, 0.8                 # unknown ribbon: room left above the board and past its end
JOINT_UP = 0.8                                   # room for trimmed header joints above the board
# Encoder
EN = D["encoder"]
EC_BODY = (11.7, 12.0, 4.5)
EC_BUSH_D, EC_BUSH_H = 7.0, 7.0
EC_SHAFT_D, EC_SHAFT_FLAT, EC_SHAFT_TIP = 6.0, 4.5, PCB_TOP + 24.5
EC_OPEN = (12.98, 16.0, 2.0)                     # rounded-rect opening (x, y, r): clears body
EC_SHAFT_D_LEN = 10.0                            # the D-flat is only the last 10 mm of the shaft
# Knob
KNOB_D, KNOB_H, KNOB_BORE_DEPTH = 18.0, 15.0, 12.3
KNOB_Z0 = PCB_TOP + EC_BODY[2] + EC_BUSH_H + 1.0  # 1 mm above the bushing
KNOB_RELIEF_D, KNOB_RELIEF_H = 7.6, 3.2          # mouth relief over the round part of the shaft
# XIAO
MCU = D["mcu"]["rect"]
XIAO_T = 1.2
USB_W, USB_H, USB_OVERHANG = 8.94, 3.26, 1.4
USB_CX = MCU["x"] + MCU["w"] / 2
USB_CZ = -XIAO_T - USB_H / 2                     # -2.83
UC = D["case"]["usb_cutout"]
USB_TONGUE_GAP = 0.2                             # printed-to-printed side gap


def Y(y_pcb: float) -> float:
    return -y_pcb


def box(x0, x1, y0, y1, z0, z1) -> cq.Workplane:
    """Box from PCB-coordinate ranges (y is flipped into the design frame)."""
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


def shell_prism(z0, z1, inset=0.0):
    return rrect(PCB_W / 2, PCB_H / 2, SHELL_W - 2 * inset, SHELL_H - 2 * inset, CORNER - inset, z0, z1)


def pocket_prism(z0, z1, extra=TOL):
    return box(-extra, PCB_W + extra, -extra, PCB_H + extra, z0, z1)


def d_profile(r, flat_from_centre, z0, z1, x, y):
    c = cq.Workplane("XY", origin=(x, Y(y), z0)).circle(r).extrude(z1 - z0)
    keep = box(x - r - 1, x + flat_from_centre, y - r - 1, y + r + 1, z0 - 1, z1 + 1)
    return c.intersect(keep)


def solid(wp: cq.Workplane) -> cq.Shape:
    s = wp.val()
    if isinstance(s, cq.Compound) and len(s.Solids()) == 1:
        s = s.Solids()[0]
    return s


def oled_recess(z0, z1) -> cq.Workplane:
    m = OL["module"]
    return box(m["x"] - OLED_RECESS_FAR, m["x"] + m["w"] + TOL,
               m["y"] - OLED_RECESS_Y, m["y"] + m["h"] + OLED_RECESS_Y, z0, z1)


def make_top() -> cq.Workplane:
    body = shell_prism(PLATE_UNDER, PLATE_TOP)
    # switch cutouts, with clip pockets that thin the plate to 1.5
    for k in D["keys"]:
        body = body.cut(cbox(k["x"], k["y"], CUTOUT, CUTOUT, PLATE_UNDER - 1, PLATE_TOP + 1))
        body = body.cut(cbox(k["x"], k["y"], CLIP_POCKET, CLIP_POCKET, PLATE_UNDER - 1, PLATE_TOP - PLATE_T_CLIP))
    # OLED window through the plate, module recess from below
    w = OL["window"]
    body = body.cut(box(w["x"] - OLED_WIN_CLR_X, w["x"] + w["w"] + OLED_WIN_CLR_X,
                        w["y"] - OLED_WIN_CLR_Y, w["y"] + w["h"] + OLED_WIN_CLR_Y,
                        OLED_RECESS_TOP - 0.5, PLATE_TOP + 1))
    body = body.cut(oled_recess(PLATE_UNDER - 1, OLED_RECESS_TOP))
    # encoder: the plate is only 0.5 above the EC11 body, so the opening clears the body
    body = body.cut(rrect(EN["x"], EN["y"], EC_OPEN[0], EC_OPEN[1], EC_OPEN[2], PLATE_UNDER - 1, PLATE_TOP + 1))
    for sx, sy in SCREWS:
        body = body.cut(cyl(sx, sy, SCREW_CLR / 2, PLATE_UNDER - 1, PLATE_TOP + 1))
    # tongue that closes the USB notch of the Bottom from above and forms the top edge of the window
    return body.union(box(USB_CX - UC["w"] / 2 + USB_TONGUE_GAP, USB_CX + UC["w"] / 2 - USB_TONGUE_GAP,
                          -MARGIN_Y, -TOL, USB_CZ + UC["h"] / 2, PLATE_UNDER))


def make_bottom() -> cq.Workplane:
    """Tray with walls and floor. Inserts in the corners, USB notch in the back wall.

    The notch is open at the rim so the XIAO receptacle can drop in with the PCB, and it spares the
    print a 13.5 mm bridge. The groove is two chamfers, so it needs no support.
    """
    low = shell_prism(Z_UNDER, GROOVE_Z).faces(">Z").edges().chamfer(GROOVE_D)
    high = shell_prism(GROOVE_Z, RIM).faces("<Z").edges().chamfer(GROOVE_UP, GROOVE_D)
    body = low.union(high).cut(pocket_prism(Z_FLOOR, RIM + 1))
    for sx, sy in SCREWS:
        body = body.cut(cyl(sx, sy, INSERT_HOLE / 2, RIM - INSERT_DEPTH, RIM + 1))
        body = body.cut(cyl(sx, sy, SCREW_CLR / 2, SCREW_TIP - BLIND_CLR, RIM))
    return body.cut(box(USB_CX - UC["w"] / 2, USB_CX + UC["w"] / 2, -MARGIN_Y - 2, 1.0,
                        USB_CZ - UC["h"] / 2, RIM + 1))


def make_oled_support() -> cq.Workplane:
    """C-shaped part between the module and the PCB that carries finger load on the glass to the PCB.

    One foot under the far end, one beside J1, joined by a rail that clears the XIAO pad rows.
    Its height is the module gap, so the part is held in place once the module is soldered.
    """
    z0, z1 = PCB_TOP, OLED_BOARD_Z0
    return box(*SUPPORT_FAR, z0, z1).union(box(*SUPPORT_NEAR, z0, z1)).union(box(*SUPPORT_RAIL, z0, z1))


def make_knob() -> cq.Workplane:
    """18 mm knob for a 6 mm D-shaft, with 30 vertical knurl ribs that print without supports."""
    n, ro, ri = 30, KNOB_D / 2, KNOB_D / 2 - 0.5
    pts = []
    for i in range(2 * n):
        a = math.pi * i / n
        r = ro if i % 2 == 0 else ri
        pts.append((r * math.cos(a), r * math.sin(a)))
    knob = (cq.Workplane("XY", origin=(EN["x"], Y(EN["y"]), KNOB_Z0)).polyline(pts).close()
            .extrude(KNOB_H))
    knob = knob.faces(">Z").edges().chamfer(0.6)
    # top dimple marker
    knob = knob.cut(cyl(EN["x"], EN["y"] - 5.5, 0.8, KNOB_Z0 + KNOB_H - 0.6, KNOB_Z0 + KNOB_H + 1))
    bore = d_profile(3.1, EC_SHAFT_FLAT - EC_SHAFT_D / 2 + 0.1, KNOB_Z0 - 1, KNOB_Z0 + KNOB_BORE_DEPTH,
                     EN["x"], EN["y"])
    knob = knob.cut(cyl(EN["x"], EN["y"], KNOB_RELIEF_D / 2, KNOB_Z0 - 1, KNOB_Z0 + KNOB_RELIEF_H))
    return knob.cut(bore)


def placeholders() -> dict[str, cq.Workplane]:
    ph: dict[str, cq.Workplane] = {}
    ph["PCB"] = box(0, PCB_W, 0, PCB_H, 0, PCB_T)
    for k in D["keys"]:
        r, x, y = k["ref"], k["x"], k["y"]
        sw = cbox(x, y, 14.0, 14.0, PCB_TOP, PLATE_TOP)
        sw = sw.union(cbox(x, y, 14.9, 5.0, PLATE_TOP - PLATE_T_CLIP - 0.8, PLATE_TOP - PLATE_T_CLIP))
        sw = sw.union(cbox(x, y, 15.6, 15.6, PLATE_TOP, PLATE_TOP + 6.6))
        sw = sw.union(cbox(x, y, 4.0, 4.0, PLATE_TOP + 6.6, PLATE_TOP + 10.2))
        ph[f"{r}_switch"] = sw
        pins = cyl(x, y, 3.85 / 2, PCB_TOP - 2.8, PCB_TOP)
        for dx, dy, dd in ((-5.08, 0, 1.7), (5.08, 0, 1.7), (-3.81, -2.54, 1.5), (2.54, -5.08, 1.5)):
            pins = pins.union(cyl(x + dx, y + dy, dd / 2, PCB_TOP - 3.3, PCB_TOP))
        ph[f"{r}_pins"] = pins
        cap = (cq.Workplane("XY", origin=(x, Y(y), PLATE_TOP + 6.0)).rect(18.2, 18.2)
               .workplane(offset=7.6).rect(12.7, 12.7).loft())
        ph[f"{r}_keycap"] = cap
    m, w, h = OL["module"], OL["window"], OL["header"]
    pins = None
    for i in range(4):                          # bare header pins, plastic removed
        p = cbox(h["pin_row_x"], h["centre_y"] + (i - 1.5) * h["pitch"], 0.64, 0.64, -THT_TAIL, OLED_BOARD_Z1)
        pins = p if pins is None else pins.union(p)
    ph["OLED_pins"] = pins
    ph["OLED_board"] = box(m["x"], m["x"] + m["w"], m["y"], m["y"] + m["h"], OLED_BOARD_Z0, OLED_BOARD_Z1)
    ph["OLED_glass"] = box(w["x"], w["x"] + w["w"], w["y"], w["y"] + w["h"], OLED_BOARD_Z1, OLED_GLASS_Z1)
    ph["XIAO_board"] = box(MCU["x"], MCU["x"] + MCU["w"], MCU["y"], MCU["y"] + MCU["h"], -XIAO_T, 0)
    ph["XIAO_usb"] = box(USB_CX - USB_W / 2, USB_CX + USB_W / 2, -USB_OVERHANG, 7.35 - USB_OVERHANG,
                         -XIAO_T - USB_H, -XIAO_T)
    ph["XIAO_shield"] = cbox(USB_CX, 13.5, 12.0, 11.0, -XIAO_T - 1.0, -XIAO_T)
    ex, ey = EN["x"], EN["y"]
    ph["EC11_body"] = cbox(ex, ey, EC_BODY[0], EC_BODY[1], PCB_TOP, PCB_TOP + EC_BODY[2]).union(
        cbox(ex, ey, 12.5, 1.5, PCB_TOP - 3.5, PCB_TOP + 1.5))
    ph["EC11_bushing"] = cyl(ex, ey, EC_BUSH_D / 2, PCB_TOP + EC_BODY[2], PCB_TOP + EC_BODY[2] + EC_BUSH_H)
    # Alps shaft: round to 10 mm below the tip, D-flat above that
    ph["EC11_shaft"] = cyl(ex, ey, EC_SHAFT_D / 2, PCB_TOP + EC_BODY[2] + EC_BUSH_H,
                           EC_SHAFT_TIP - EC_SHAFT_D_LEN).union(
        d_profile(EC_SHAFT_D / 2, EC_SHAFT_FLAT - EC_SHAFT_D / 2, EC_SHAFT_TIP - EC_SHAFT_D_LEN, EC_SHAFT_TIP, ex, ey))
    pins = None
    for dx, dy in ((-2.5, 7.5), (0, 7.5), (2.5, 7.5), (-2.5, -7.0), (2.5, -7.0)):
        p = cyl(ex + dx, ey + dy, 0.5, PCB_TOP - 3.5, PCB_TOP)
        pins = p if pins is None else pins.union(p)
    ph["EC11_pins"] = pins
    return ph


def oled_envelopes() -> dict[str, cq.Workplane]:
    """Room left for parts of the module that have no drawing yet."""
    m, h = OL["module"], OL["header"]
    ribbon = box(m["x"] - RIBBON_OUT, OL["window"]["x"], m["y"], m["y"] + m["h"],
                 OLED_BOARD_Z0, OLED_BOARD_Z1 + RIBBON_UP)
    joints = None
    for i in range(4):
        c = cyl(h["pin_row_x"], h["centre_y"] + (i - 1.5) * h["pitch"], 1.1, OLED_BOARD_Z1, OLED_BOARD_Z1 + JOINT_UP)
        joints = c if joints is None else joints.union(c)
    return {"OLED_ribbon_room": ribbon, "OLED_joint_room": joints}


def switch_rigid(x, y) -> cq.Workplane:
    """Switch without its sprung clips, which is what must pass the 14.0 cutout."""
    return (cbox(x, y, 14.0, 14.0, PCB_TOP, PLATE_TOP)
            .union(cbox(x, y, 15.6, 15.6, PLATE_TOP, PLATE_TOP + 6.6))
            .union(cbox(x, y, 4.0, 4.0, PLATE_TOP + 6.6, PLATE_TOP + 10.2)))


def bottom_pads() -> list[dict]:
    return json.loads(PADS_FILE.read_text())["pads"]


def usb_overmold() -> cq.Workplane:
    """12.5 x 7 cable overmold seated against the receptacle, run out through the wall."""
    return cbox(USB_CX, -15.0, 12.5, 26.0, USB_CZ - 3.5, USB_CZ + 3.5).cut(
        box(-100, 200, -1.9, 100, -50, 50))


def to_desk(s: cq.Shape) -> cq.Shape:
    return s.translate(cq.Vector(0, 0, -Z_UNDER))


def print_orient(name: str, s: cq.Shape) -> cq.Shape:
    if name == "Top":       # top face on the (textured) bed: no supports
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180)
    bb = s.BoundingBox()
    return s.translate(cq.Vector(-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))


def build() -> dict:
    parts = {"Top": make_top(), "Bottom": make_bottom(), "Knob": make_knob(), "OLEDSupport": make_oled_support()}
    return {"parts": {k: solid(v) for k, v in parts.items()},
            "ph": {k: solid(v) for k, v in placeholders().items()}}


BLACK = (0.08, 0.08, 0.09, 1.0)                  # every printed part
WHITE = (0.97, 0.97, 0.97, 1.0)                  # kit keycaps


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


def assembly(model: dict, explode: float = 0.0) -> cq.Assembly:
    a = cq.Assembly(name="frostbite")
    lift = {"Bottom": 0, "Top": 2, "Knob": 3, "OLEDSupport": 1.5}
    for k, s in model["parts"].items():
        s2 = to_desk(s).translate(cq.Vector(0, 0, explode * lift[k]))
        a.add(s2, name=k, color=cq.Color(*BLACK))
    for k, s in model["ph"].items():
        s2 = to_desk(s).translate(cq.Vector(0, 0, explode * 1.5))
        a.add(s2, name=k, color=cq.Color(*ph_color(k)))
    return a


def positions() -> dict:
    w = OL["window"]
    return {
        "_about": "Case feature centres in PCB coordinates (mm), written by CAD/frostbite_case.py",
        "keys": [{"ref": k["ref"], "id": k["id"], "x": k["x"], "y": k["y"], "cutout": CUTOUT} for k in D["keys"]],
        "encoder": {"x": EN["x"], "y": EN["y"], "opening": {"w": EC_OPEN[0], "h": EC_OPEN[1], "r": EC_OPEN[2]}},
        "oled_window": {"x": w["x"], "y": w["y"], "w": w["w"], "h": w["h"],
                        "cut": {"x": w["x"] - OLED_WIN_CLR_X, "y": w["y"] - OLED_WIN_CLR_Y,
                                "w": w["w"] + 2 * OLED_WIN_CLR_X, "h": w["h"] + 2 * OLED_WIN_CLR_Y}},
        "oled_stack": {"module_gap": OLED_GAP, "glass_below_plate": round(PLATE_TOP - OLED_GLASS_Z1, 2),
                       "lip_gap": round(OLED_RECESS_TOP - OLED_BOARD_Z1, 2), "header_plastic": "removed"},
        "usb_cutout": {"x": USB_CX, "z_from_pcb_bottom": USB_CZ, "w": UC["w"], "h": UC["h"]},
        "screws": [{"x": sx, "y": sy, "insert": "Bottom", "head": "plate top", "boss_od": BOSS_OD}
                   for sx, sy in SCREWS],
        "shell": {"w": SHELL_W, "h": SHELL_H},
    }


def export_all(model: dict) -> dict:
    PROD.mkdir(exist_ok=True)
    out = {}
    for name, s in model["parts"].items():
        p = print_orient(name, s)
        cq.exporters.export(p, str(PROD / f"{name}.step"))
        cq.exporters.export(p, str(PROD / f"{name}.stl"), tolerance=0.01, angularTolerance=0.1)
        out[name] = p
    assembly(model).export(str(CAD / "frostbite-assembly.step"))
    pos = positions()
    bb = cq.Compound.makeCompound([to_desk(s) for k, s in model["parts"].items() if k != "Knob"]).BoundingBox()
    pos["heights"] = {"case_mm": round(CASE_H, 2), "head_top_mm": round(SEAT + HEAD_H - Z_UNDER, 2),
                      "_note": "Plate top above the desk, and screw head top; keycaps add ~13.6 above the plate",
                      "case_bbox_desk_mm": [round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)]}
    (CAD / "positions.json").write_text(json.dumps(pos, indent=2) + "\n")
    return out


def view(shape: cq.Shape, az: float, el: float) -> cq.Shape:
    """Turn the model so a camera on +Z sees it from azimuth az (deg, about Z) and elevation el."""
    o = cq.Vector(0, 0, 0)
    return shape.rotate(o, cq.Vector(0, 0, 1), az).rotate(o, cq.Vector(1, 0, 0), -(90 - el))


def previews(model: dict):
    pv = CAD / "previews"
    pv.mkdir(exist_ok=True)
    opts = dict(width=900, height=640, marginLeft=60, marginTop=60, showAxes=False,
                strokeWidth=0.25, showHidden=False, projectionDir=(0, 0, 1))
    asm = assembly(model).toCompound()
    exp = assembly(model, explode=16).toCompound()
    cq.exporters.export(view(asm, 30, 35), str(pv / "assembly-iso.svg"), opt=opts)
    cq.exporters.export(view(exp, 30, 25), str(pv / "exploded-iso.svg"), opt=opts)
    cq.exporters.export(model["parts"]["Top"], str(pv / "top-plan.svg"), opt=opts)
    cq.exporters.export(view(asm, 90, 0), str(pv / "side-left.svg"), opt=opts)
    cq.exporters.export(view(asm, 180, 0), str(pv / "back-usb.svg"), opt=opts)
    for svg in pv.glob("*.svg"):                 # macOS Quick Look writes <name>.svg.png; skipped elsewhere
        subprocess.run(["qlmanage", "-t", "-s", "900", "-o", str(pv), str(svg)],
                       check=False, capture_output=True, timeout=60)


if __name__ == "__main__":
    m = build()
    export_all(m)
    if "--no-previews" not in sys.argv:
        previews(m)
    print(json.dumps(json.loads((CAD / "positions.json").read_text())["heights"]))
