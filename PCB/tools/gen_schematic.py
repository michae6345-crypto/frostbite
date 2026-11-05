"""Generate PCB/frostbite.kicad_sch from design.json.

Every pin gets a 2.54 mm wire stub ending in a net label or power symbol. Unused pins get no-connect
flags. Symbols are copied from KiCad's library and the Hack Club care package into lib_symbols.

usage: python3 PCB/tools/gen_schematic.py
"""
from __future__ import annotations

import itertools
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sexp import Q, dump, find, find1, parse, walk  # noqa: E402

PCB = Path(__file__).resolve().parents[1]
ROOT = PCB.parent
STD = Path.home() / "Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"
DESIGN = json.loads((ROOT / "design.json").read_text())
NS = uuid.UUID("6f1c3a52-0b7e-4f1e-9a51-f7057b17e000")  # deterministic UUIDs keep the PCB linked
ROOT_UUID = str(uuid.uuid5(NS, "root"))


def uid(tag: str) -> str:
    return str(uuid.uuid5(NS, tag))


FP = {
    "SW": "hackpad:MX-Solderable-1U",
    "D": "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal",
    "U": "hackpad:XIAO-Generic-Hybrid-14P-2.54-21X17.8MM",
    "ENC": "frostbite:EC11E-Switch_Vertical_H20mm_Slot3.4x1.5",
    "J": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
}
LIBS = {
    "Device:D": (STD / "Device.kicad_sym", "D"),
    "Switch:SW_Push": (STD / "Switch.kicad_sym", "SW_Push"),
    "Device:RotaryEncoder_Switch_MP": (STD / "Device.kicad_sym", "RotaryEncoder_Switch_MP"),
    "Connector_Generic:Conn_01x04": (STD / "Connector_Generic.kicad_sym", "Conn_01x04"),
    "power:GND": (STD / "power.kicad_sym", "GND"),
    "power:+3V3": (STD / "power.kicad_sym", "+3V3"),
    "power:PWR_FLAG": (STD / "power.kicad_sym", "PWR_FLAG"),
    "XIAO_RP2040:Seeed XIAO RP2040 board": (PCB / "lib/XIAO_RP2040.kicad_sym", "Seeed XIAO RP2040 board"),
}
POWER = {"GND", "+3V3"}


def normalise_hide(e):
    """Old-format bare `hide` atoms -> (hide yes)."""
    for node in walk(e):
        for i, x in enumerate(node):
            if x == "hide" and i != 0:
                node[i] = ["hide", "yes"]


def load_symbol(lib_id):
    path, name = LIBS[lib_id]
    lib = parse(path.read_text())
    sym = next(s for s in find(lib, "symbol") if s[1] == name)
    assert not find(sym, "extends"), lib_id
    sym = parse(dump(sym))  # deep copy that keeps Q atoms
    normalise_hide(sym)
    sym[1] = Q(lib_id)
    return sym


def pins_of(sym):
    """{number: (x, y, angle)} in library coordinates (y up)."""
    pins = {}
    for node in walk(sym):
        if node and node[0] == "pin" and find1(node, "number"):
            at = find1(node, "at")
            num = str(find1(node, "number")[1])
            pins[num] = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0)
    return pins


SYMS = {k: load_symbol(k) for k in LIBS}
PINS = {k: pins_of(v) for k, v in SYMS.items()}

items = []
pwr_count = itertools.count(1)


def eff(size=1.27, hide=False, justify=None):
    e = ["effects", ["font", ["size", size, size]]]
    if justify:
        e.append(["justify", justify])
    if hide:
        e.append(["hide", "yes"])
    return e


def prop(name, value, x, y, hide=False, angle=0, justify=None):
    return ["property", Q(name), Q(value), ["at", x, y, angle], eff(hide=hide, justify=justify)]


def place(lib_id, ref, value, x, y, footprint="", angle=0, extra_props=(),
          ref_at=None, val_at=None, ref_just=None, val_just=None, val_angle=0):
    """ref_at / val_at: absolute text positions (default: 6.35 above / below the origin)."""
    ref_at = ref_at or (x, y - 6.35)
    val_at = val_at or (x, y + 6.35)
    sym = ["symbol", ["lib_id", Q(lib_id)], ["at", x, y, angle], ["unit", 1],
           ["exclude_from_sim", "no"], ["in_bom", "no" if ref.startswith("#") else "yes"],
           ["on_board", "no" if ref.startswith("#") else "yes"], ["dnp", "no"],
           ["uuid", Q(uid("sym" + ref))],
           prop("Reference", ref, *ref_at, hide=ref.startswith("#"), justify=ref_just),
           prop("Value", value, *val_at, justify=val_just, angle=val_angle),
           prop("Footprint", footprint, x, y, hide=True),
           prop("Datasheet", "", x, y, hide=True),
           prop("Description", "", x, y, hide=True)]
    for k, v in extra_props:
        sym.append(prop(k, v, x, y, hide=True))
    for num in PINS[lib_id]:
        sym.append(["pin", Q(num), ["uuid", Q(uid(f"pin{ref}.{num}"))]])
    sym.append(["instances", ["project", Q("frostbite"),
                              ["path", Q("/" + ROOT_UUID), ["reference", Q(ref)], ["unit", 1]]]])
    items.append(sym)


def pin_point(lib_id, num, x, y):
    px, py, ang = PINS[lib_id][num]
    out = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}[int(ang) % 360]  # schematic coords
    return (round(x + px, 4), round(y - py, 4)), out


def wire(a, b):
    items.append(["wire", ["pts", ["xy", a[0], a[1]], ["xy", b[0], b[1]]],
                  ["stroke", ["width", 0], ["type", "default"]], ["uuid", Q(uid(f"w{a}{b}"))]])


def power_symbol(net, p, angle=0, out=None):
    """Power symbol with its pin at p. `out` is the direction the graphic points (sch coords)."""
    ref = f"#PWR{next(pwr_count):02d}"
    out = out or ((0, 1) if net == "GND" else (0, -1))
    val = (round(p[0] + out[0] * 3.81, 4), round(p[1] + out[1] * (4.45 if net == "GND" else 3.81), 4))
    just = {(1, 0): "left", (-1, 0): "right"}.get(out)
    # field angles are stored relative to the symbol: cancel the rotation so the text reads level;
    # KiCad turns a net 180 deg text upright by swapping its justification, so pre-swap it
    if just and (angle + angle % 180) % 360 == 180:
        just = {"left": "right", "right": "left"}[just]
    place(f"power:{net}", ref, net, p[0], p[1], angle=angle, val_at=val, val_just=just, val_angle=angle % 180)


def connect(lib_id, ref, num, x, y, net):
    p, d = pin_point(lib_id, num, x, y)
    if net is None:
        items.append(["no_connect", ["at", p[0], p[1]], ["uuid", Q(uid(f"nc{ref}.{num}"))]])
        return
    end = (round(p[0] + d[0] * 2.54, 4), round(p[1] + d[1] * 2.54, 4))
    wire(p, end)
    if net in POWER:
        # point the graphic away from the pin
        down = net == "GND"
        ang = {(0, 1): 0 if down else 180, (0, -1): 180 if down else 0,
               (1, 0): 90 if down else 270, (-1, 0): 270 if down else 90}[d]
        power_symbol(net, end, ang, out=d)
    else:
        ang = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[d]
        # global labels keep net names un-prefixed ("ROW0", not "/ROW0"), matching design.json
        items.append(["global_label", Q(net), ["shape", "passive"], ["at", end[0], end[1], ang],
                      ["fields_autoplaced", "yes"],
                      eff(justify="left" if ang in (0, 90) else "right"),
                      ["uuid", Q(uid(f"lbl{ref}.{num}"))],
                      ["property", Q("Intersheetrefs"), Q("${INTERSHEET_REFS}"), ["at", end[0], end[1], 0],
                       eff(hide=True)]])


def build():
    G = 2.54
    xiao = "XIAO_RP2040:Seeed XIAO RP2040 board"
    ux, uy = 24 * G, 30 * G
    place(xiao, "U1", "XIAO RP2040", ux, uy, FP["U"], ref_at=(ux, uy - 12.7), val_at=(ux, uy + 12.7))
    pinnet = {str(int(p["xiao"][1:]) + 1): p["net"] for p in DESIGN["pins"]}
    pinnet.update({"12": "+3V3", "13": "GND"})
    for num in PINS[xiao]:              # D6 (pad 7) and 5V (pad 14) are not in the design: no-connect
        connect(xiao, "U1", num, ux, uy, pinnet.get(num))

    hdr = DESIGN["oled"]["header"]["pins_top_to_bottom"]
    jnet = {"GND": "GND", "VCC": "+3V3", "SCL": "SCL", "SDA": "SDA"}
    conn = "Connector_Generic:Conn_01x04"
    jx, jy = 46 * G, 24 * G
    place(conn, "J1", "OLED_0.91in_I2C", jx, jy, FP["J"], ref_at=(jx, jy - 5.08), val_at=(jx, jy + 8.89))
    for i, name in enumerate(hdr):
        connect(conn, "J1", str(i + 1), jx, jy, jnet[name])

    enc = "Device:RotaryEncoder_Switch_MP"
    ex, ey = 46 * G, 40 * G
    place(enc, "ENC1", "EC11E", ex, ey, FP["ENC"], ref_at=(ex, ey - 7.62), val_at=(ex + 7.62, ey + 7.62),
          val_just="left")
    for num, net in {"A": "ENC_A", "B": "ENC_B", "C": "GND", "S1": None, "S2": None, "MP": "GND"}.items():
        connect(enc, "ENC1", num, ex, ey, net)

    sw, dio = "Switch:SW_Push", "Device:D"
    for k, key in enumerate(DESIGN["keys"], start=1):
        r, c = key["row"], key["col"]
        sx, sy = (66 + 22 * c) * G, (16 + 12 * r) * G
        place(sw, f"SW{k}", "MX_" + key["id"], sx, sy, FP["SW"])
        connect(sw, f"SW{k}", "1", sx, sy, f"COL{c}")
        connect(sw, f"SW{k}", "2", sx, sy, f"SW{k}_D")
        dx, dy = sx + 6 * G, sy + 4 * G
        place(dio, f"D{k}", "1N4148", dx, dy, FP["D"])
        connect(dio, f"D{k}", "2", dx, dy, f"SW{k}_D")   # anode from switch
        connect(dio, f"D{k}", "1", dx, dy, f"ROW{r}")    # cathode to row

    for j, net in enumerate(["GND", "+3V3"]):
        fx, fy = (10 + 12 * j) * G, 62 * G
        place("power:PWR_FLAG", f"#FLG{j + 1:02d}", "PWR_FLAG", fx, fy, val_at=(fx, fy - 5.08))
        wire((fx, fy), (fx + 3 * G, fy))
        power_symbol(net, (fx + 3 * G, fy))

    items.append(["text", Q("Frostbite 9 - 3x3 COL2ROW matrix, EC11E (push not wired), 0.91in I2C OLED on J1 (GND VCC SCL SDA).\\n"
                            "XIAO D6 and 5V not connected. Generated by PCB/tools/gen_schematic.py from design.json."),
                  ["exclude_from_sim", "no"], ["at", 10 * G, 70 * G, 0], eff(justify="left"),
                  ["uuid", Q(uid("note"))]])


def main():
    build()
    doc = ["kicad_sch", ["version", 20250114], ["generator", Q("eeschema")], ["generator_version", Q("9.0")],
           ["uuid", Q(ROOT_UUID)], ["paper", Q("A3")],
           ["title_block", ["title", Q("Frostbite 9")], ["rev", Q("A")],
            ["company", Q("Hack Club Hackpad")], ["comment", 1, Q("Generated from design.json by PCB/tools/gen_schematic.py")]],
           ["lib_symbols"] + list(SYMS.values())]
    doc += items
    doc += [["sheet_instances", ["path", Q("/"), ["page", Q("1")]]], ["embedded_fonts", "no"]]
    (PCB / "frostbite.kicad_sch").write_text(dump(doc) + "\n")
    print(f"wrote frostbite.kicad_sch: {len(items)} items")


if __name__ == "__main__":
    main()
