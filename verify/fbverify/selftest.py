"""--self-test: prove every check can FAIL.

For each case: build a clean copy (real project files where they exist, synthetic fixtures
generated from design.json where they do not), assert the check PASSes on it, inject one known
fault, assert the check FAILs and that a fail reason names the fault."""
from __future__ import annotations

import copy
import datetime as _dt
import json
import re
import shutil
import struct
import tempfile
from pathlib import Path

from . import checks as C
from . import geom
from .core import FAIL, NOT_RUN, PASS, Check, Ctx, base_env, sha256
from .main import exit_code

# ---------------------------------------------------------------- synthetic fixtures

OX, OY = 100.0, 50.0  # KiCad sheet offset for the synthetic board


def synth_pcb(d: dict) -> str:
    W, H = d["pcb"]["w"], d["pcb"]["h"]
    A = lambda x, y: f"(at {OX + x:.4f} {OY + y:.4f})"  # noqa: E731
    out = ['(kicad_pcb (version 20240108) (generator "fbverify-selftest")',
           ' (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user) (5 "F.SilkS" user "F.Silkscreen")'
           ' (7 "B.SilkS" user "B.Silkscreen") (13 "F.Fab" user) (15 "B.Fab" user))',
           f' (gr_rect (start {OX} {OY}) (end {OX + W} {OY + H}) (layer "Edge.Cuts"))',
           f' (gr_text "Frostbite" (at {OX + 10} {OY + 60}) (layer "F.SilkS"))',
           f' (gr_text "XIAO HERE" (at {OX + 20} {OY + 10}) (layer "B.SilkS"))']
    g = {p["net"]: p for p in d["pins"]}
    for k in d["keys"]:
        out.append(f' (footprint "frostbite:MX_V2" (layer "F.Cu") {A(k["x"], k["y"])}'
                   f' (property "Reference" "{k["ref"]}") (property "Value" "MX")'
                   f' (pad "1" thru_hole circle (at -3.81 -2.54) (size 2 2) (net "COL{k["col"]}"))'
                   f' (pad "2" thru_hole circle (at 2.54 -5.08) (size 2 2) (net "Net-({k["ref"]}-2)")))')
    e = d["encoder"]
    out.append(f' (footprint "Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm" (layer "F.Cu")'
               f' {A(e["x"] - 7.0, e["y"] + 2.5)} (property "Reference" "SW10") (property "Value" "EC11")'
               ' (pad "A" thru_hole rect (at 0 0) (size 2 2) (net "ENC_A")) (pad "B" thru_hole circle (at 0 5) (size 2 2) (net "ENC_B"))'
               ' (pad "MP" thru_hole rect (at 7 -8.1) (size 3 2)) (pad "MP" thru_hole rect (at 7 3.1) (size 3 2)))')
    h = d["oled"]["header"]
    nets = {"GND": "GND", "VCC": "+3V3", "SCL": "SCL", "SDA": "SDA"}
    y0 = h["centre_y"] - 1.5 * h["pitch"]
    pads = " ".join(f'(pad "{i + 1}" thru_hole circle (at 0 {i * h["pitch"]:.3f}) (size 1.7 1.7) (net "{nets[n]}"))'
                    for i, n in enumerate(h["pins_top_to_bottom"]))
    out.append(f' (footprint "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical" (layer "F.Cu")'
               f' {A(h["pin_row_x"], y0)} (property "Reference" "OLED1") (property "Value" "SSD1306") {pads})')
    r = d["mcu"]["rect"]
    out.append(f' (footprint "Seeed:XIAO-RP2040-DIP" (layer "B.Cu") {A(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)}'
               ' (property "Reference" "U1") (property "Value" "XIAO-RP2040")'
               f' (fp_rect (start {-r["w"] / 2} {-r["h"] / 2}) (end {r["w"] / 2} {r["h"] / 2}) (layer "B.Fab")))')
    pos = {k["led"]: (k["x"], k["y"] + 5.08, "F.Cu") for k in d["keys"]}
    pos.update({gl["led"]: (gl["x"], gl["y"], "B.Cu") for gl in d["leds"]["glow"]})
    for i in range(d["leds"]["count"]):
        x, y, side = pos[i]
        din = "LED_DIN" if i == 0 else f"LEDN{i - 1}"
        out.append(f' (footprint "frostbite:LED_SK6812MINI-E" (layer "{side}") {A(x, y)}'
                   f' (property "Reference" "LED{i + 1}") (property "Value" "SK6812MINI-E")'
                   f' (pad "1" smd rect (at -1.6 -0.7) (size 1 0.8) (net "+5V") (pinfunction "VDD"))'
                   f' (pad "2" smd rect (at -1.6 0.7) (size 1 0.8) (net "LEDN{i}") (pinfunction "DOUT"))'
                   f' (pad "3" smd rect (at 1.6 0.7) (size 1 0.8) (net "GND") (pinfunction "GND"))'
                   f' (pad "4" smd rect (at 1.6 -0.7) (size 1 0.8) (net "{din}") (pinfunction "DIN")))')
    for k in d["keys"]:
        n = k["ref"][2:]
        out.append(f' (footprint "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal" (layer "F.Cu") {A(k["x"], k["y"] + 8.5)}'
                   f' (property "Reference" "D{n}") (property "Value" "1N4148")'
                   f' (pad "1" thru_hole rect (at -3.81 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask") (net "ROW{k["row"]}"))'
                   f' (pad "2" thru_hole circle (at 3.81 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask")))')
    out.append(")")
    return "\n".join(out)


def synth_netlist(d: dict, fault: str | None = None) -> str:
    comps, nets = [], {}

    def node(net, ref, pin, fn=None):
        nets.setdefault(net, []).append((ref, pin, fn))
    comps.append(("U1", "XIAO-RP2040", "Seeed:XIAO-RP2040-DIP"))
    swap = {"D9": "D10", "D10": "D9"} if fault == "xiao_pin" else {}
    for p in d["pins"]:
        x = swap.get(p["xiao"], p["xiao"])
        node("/" + p["net"], "U1", str(int(x[1:]) + 1), x)
    node("+5V", "U1", "14", "5V")
    node("+3V3", "U1", "12", "3V3")
    node("GND", "U1", "13", "GND")
    for k in d["keys"]:
        n = k["ref"][2:]
        comps.append((k["ref"], "MX", "frostbite:MX_V2"))
        comps.append((f"D{n}", "1N4148", "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal"))
        node(f"/COL{k['col']}", k["ref"], "1")
        node(f"Net-(D{n}-A)", k["ref"], "2")
        node(f"Net-(D{n}-A)", f"D{n}", "2", "A")
        node(f"/ROW{k['row']}", f"D{n}", "1", "K")
    comps.append(("OLED1", "SSD1306", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"))
    onets = ["GND", "+3V3", "/SDA", "/SCL"] if fault == "oled_swap" else ["GND", "+3V3", "/SCL", "/SDA"]
    for i, (role, net) in enumerate(zip(d["oled"]["header"]["pins_top_to_bottom"], onets), 1):
        node(net, "OLED1", str(i), role)
    comps.append(("SW10", "RotaryEncoder_Switch", "Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm"))
    node("/ENC_A", "SW10", "A", "A")
    node("/ENC_B", "SW10", "B", "B")
    node("GND", "SW10", "C", "C")
    for i in range(d["leds"]["count"]):
        ref = f"LED{i + 1}"
        comps.append((ref, "SK6812MINI-E", "frostbite:LED_SK6812MINI-E"))
        node("+5V", ref, "1", "VDD")
        node(f"Net-(LED{i + 1}-DOUT)", ref, "2", "DOUT")
        node("GND", ref, "3", "GND")
        din = "/LED_DIN" if i == 0 else f"Net-(LED{i}-DOUT)"
        if fault == "chain_break" and i == 7:
            din = "Net-(cut)"
        node(din, ref, "4", "DIN")
    L = ['(export (version "E")', " (components"]
    for ref, val, fp in comps:
        L.append(f'  (comp (ref "{ref}") (value "{val}") (footprint "{fp}") (libsource (lib "x") (part "{val}")))')
    L.append(" )")
    L.append(" (nets")
    for i, (name, nodes) in enumerate(nets.items(), 1):
        nd = " ".join(f'(node (ref "{r}") (pin "{p}")' + (f' (pinfunction "{f}")' if f else "") + ")" for r, p, f in nodes)
        L.append(f'  (net (code "{i}") (name "{name}") {nd})')
    L.append(" ))")
    return "\n".join(L)


def synth_uf2(nblocks=8, family=geom.RP2040_FAMILY) -> bytes:
    out = b""
    for i in range(nblocks):
        hdr = struct.pack("<8I", geom.UF2_MAGIC0, geom.UF2_MAGIC1, geom.UF2_FLAG_FAMILY, 0x10000000 + 256 * i,
                          256, i, nblocks, family)
        out += hdr + bytes([i & 0xFF]) * 256 + b"\0" * (476 - 256) + struct.pack("<I", geom.UF2_MAGIC_END)
    return out


def synth_plate(d: dict, cut=14.0, move=None):
    """Top plate: shell outline with switch cutouts, encoder hole and OLED window. CAD frame = y up."""
    import shapely.geometry as g
    import trimesh
    sh = d["case"]["shell"]
    ox, oy = (sh["w"] - d["pcb"]["w"]) / 2, (sh["h"] - d["pcb"]["h"]) / 2
    T = lambda x, y: (x + ox, sh["h"] - (y + oy))  # noqa: E731
    poly = g.box(0, 0, sh["w"], sh["h"])
    for i, k in enumerate(d["keys"]):
        x, y = T(k["x"], k["y"])
        c = cut[i] if isinstance(cut, list) else cut
        if move and move[0] == i:
            x += move[1]
        poly = poly.difference(g.box(x - c / 2, y - c / 2, x + c / 2, y + c / 2))
    ex, ey = T(d["encoder"]["x"], d["encoder"]["y"])
    poly = poly.difference(g.Point(ex, ey).buffer(3.75, 64))
    w = d["oled"]["window"]
    wx, wy = T(w["x"] + w["w"] / 2, w["y"] + w["h"] / 2)
    poly = poly.difference(g.box(wx - w["w"] / 2, wy - w["h"] / 2, wx + w["w"] / 2, wy + w["h"] / 2))
    return trimesh.creation.extrude_polygon(poly, 1.5)


# ---------------------------------------------------------------- harness

class Case:
    def __init__(self, name, cid, fn, clean, fault, expect_reason):
        self.name, self.cid, self.fn, self.clean, self.fault, self.expect = name, cid, fn, clean, fault, expect_reason


def _ctx(root: Path, base: Path) -> Ctx:
    ev = base / "evidence"
    work = base / "work"
    work.mkdir(parents=True, exist_ok=True)
    return Ctx(root=root, evidence_dir=ev, work=work, kicad_cli=None, env=base_env(), run_qmk=False, allow_regen=False)


def _copy_project(real: Path, dst: Path):
    dst.mkdir(parents=True)
    shutil.copy2(real / "design.json", dst / "design.json")
    for sub in ("Firmware", "PCB", "production", "CAD"):
        if (real / sub).is_dir():
            shutil.copytree(real / sub, dst / sub, ignore=shutil.ignore_patterns(".venv", "*-backups", ".build"))
    if (real / "README.md").is_file():
        shutil.copy2(real / "README.md", dst / "README.md")


def _edit_json(p: Path, fn):
    j = json.loads(p.read_text())
    fn(j)
    p.write_text(json.dumps(j, indent=2))


def run_selftest(verify: Path, real: Path) -> int:
    d = json.loads((real / "design.json").read_text())
    tmp = Path(tempfile.mkdtemp(prefix="fbverify-selftest-"))
    results = []
    kb_rel = Path(C.KB_DIR) / "keyboard.json"
    have_fw = (real / kb_rel).is_file()

    # -------- fixture builders (each returns nothing; mutate the copy at `root`)
    def fw_clean(root):
        if not have_fw:
            raise SkipCase("Firmware keyboard.json not in project yet")

    def fw_swap_cols(root):
        _edit_json(root / kb_rel, lambda j: j["matrix_pins"].__setitem__("cols", [j["matrix_pins"]["cols"][1], j["matrix_pins"]["cols"][0]] + j["matrix_pins"]["cols"][2:]))

    def fw_swap_i2c(root):
        p = root / C.KB_DIR / "config.h"
        t = p.read_text()
        t = t.replace("I2C1_SDA_PIN GP6", "I2C1_SDA_PIN GPX").replace("I2C1_SCL_PIN GP7", "I2C1_SCL_PIN GP6").replace("I2C1_SDA_PIN GPX", "I2C1_SDA_PIN GP7")
        p.write_text(t)

    def fw_led_count(root):
        _edit_json(root / kb_rel, lambda j: j["rgb_matrix"]["layout"].pop())

    def pcb_clean(root):
        pd = root / "PCB"
        if pd.exists():
            shutil.rmtree(pd)
        pd.mkdir()
        (pd / "frostbite.kicad_pro").write_text("{}")
        (pd / "frostbite.kicad_sch").write_text("(kicad_sch)")
        (pd / "frostbite.kicad_pcb").write_text(synth_pcb(d))

    def pcb_move_sw5(root):
        p = root / "PCB/frostbite.kicad_pcb"
        t = p.read_text()
        k = next(k for k in d["keys"] if k["ref"] == "SW5")
        old = f"(at {OX + k['x']:.4f} {OY + k['y']:.4f}) (property \"Reference\" \"SW5\")"
        assert old in t, "fixture: SW5 placement not found"
        p.write_text(t.replace(old, f"(at {OX + k['x'] + 0.2:.4f} {OY + k['y']:.4f}) (property \"Reference\" \"SW5\")"))

    def pcb_three_layers(root):
        p = root / "PCB/frostbite.kicad_pcb"
        p.write_text(p.read_text().replace('(2 "B.Cu" signal)', '(2 "B.Cu" signal) (4 "In1.Cu" signal)'))

    def pcb_swap_led_chain(root):
        p = root / "PCB/frostbite.kicad_pcb"
        t = p.read_text()
        # swap physical positions of chain LEDs 3 and 4 (LED4 <-> LED5 refs keep their nets)
        a = re.search(r'\(at [\d.]+ [\d.]+\) \(property "Reference" "LED4"\)', t).group(0)
        b = re.search(r'\(at [\d.]+ [\d.]+\) \(property "Reference" "LED5"\)', t).group(0)
        at_a, at_b = a.split(" (property")[0], b.split(" (property")[0]
        t = t.replace(a, at_b + ' (property "Reference" "LED4")').replace(b, at_a + ' (property "Reference" "LED5")')
        p.write_text(t)

    def uf2_clean(root):
        (root / "production").mkdir(exist_ok=True)
        p = root / "production/firmware.uf2"
        if not p.is_file():
            p.write_bytes(synth_uf2())
        for other in (root / "production").glob("*.uf2"):
            if other.name != "firmware.uf2":
                other.unlink()
        if (root / C.KB_DIR).is_dir():
            import os
            import time
            t = time.time()
            os.utime(p, (t, t))  # copy is newer than the copied sources

    def uf2_truncate(root):
        p = root / "production/firmware.uf2"
        b = p.read_bytes()
        p.write_bytes(b[: len(b) - 512 * 2 - 100])

    def uf2_family(root):
        p = root / "production/firmware.uf2"
        b = bytearray(p.read_bytes())
        struct.pack_into("<I", b, 28, 0x00FF00FF)
        p.write_bytes(bytes(b))

    def stl_clean(root):
        prod = root / "production"
        prod.mkdir(exist_ok=True)
        for s in prod.glob("*"):
            if s.suffix.lower() == ".stl":
                s.unlink()
        synth_plate(d).export(prod / "Top.stl")

    def stl_hole(root):
        import trimesh
        p = root / "production/Top.stl"
        m = trimesh.load(str(p), force="mesh")
        keep = [True] * len(m.faces)
        for i in range(0, 12):
            keep[i] = False
        m.update_faces(keep)
        m.export(p)

    def stl_big_cutout(root):
        synth_plate(d, cut=[14.0] * 4 + [14.3] + [14.0] * 4).export(root / "production/Top.stl")

    def stl_moved_cutout(root):
        synth_plate(d, move=(4, 0.5)).export(root / "production/Top.stl")

    def cadpos_clean(root):
        pd = root / "PCB"
        if pd.exists():
            shutil.rmtree(pd)
        for s in (root / "production").glob("*.stl") if (root / "production").is_dir() else []:
            s.unlink()
        r = d["mcu"]["rect"]
        pos = {"keys": [{"ref": k["ref"], "x": k["x"], "y": k["y"]} for k in d["keys"]],
               "encoder": {"x": d["encoder"]["x"], "y": d["encoder"]["y"]},
               "usb_cutout": {"x": r["x"] + r["w"] / 2, "w": d["case"]["usb_cutout"]["w"], "h": d["case"]["usb_cutout"]["h"]},
               "oled_window": dict(d["oled"]["window"]),
               "screws": [dict(p) for p in d["case"].get("screws", {}).get("positions", [])]}
        (root / "CAD").mkdir(exist_ok=True)
        (root / "CAD/positions.json").write_text(json.dumps(pos))

    def cadpos_move(root):
        _edit_json(root / "CAD/positions.json", lambda j: j["keys"][6].__setitem__("y", j["keys"][6]["y"] + 0.4))

    def plate_encoder_moved(root):
        stl_clean(root)
        import shapely.geometry as g  # noqa: F401
        dd = copy.deepcopy(d)
        dd["encoder"]["x"] += 1.0
        synth_plate(dd).export(root / "production/Top.stl")

    def cadpos_usb_narrow(root):
        _edit_json(root / "CAD/positions.json", lambda j: j["usb_cutout"].__setitem__("w", 13.0))

    def boss_clean(root):
        pcb_clean(root)
        from . import sexpr
        pads = C.parser_bottom_pads(sexpr.load_pcb((root / "PCB/frostbite.kicad_pcb").read_text()))
        (root / "PCB/build").mkdir(exist_ok=True)
        (root / "PCB/build/bottom_pads.json").write_text(json.dumps({"source": "frostbite.kicad_pcb", "pads": pads}))
        cadpos = root / "CAD/positions.json"
        if cadpos.is_file():
            _edit_json(cadpos, lambda j: j.__setitem__("screws", [dict(p) for p in d["case"]["screws"]["positions"]]))

    def _d9_pad2(root):
        j = json.loads((root / "PCB/build/bottom_pads.json").read_text())
        p = next(p for p in j["pads"] if p["ref"] == "D9" and p["pad"] == "2")
        return (p["x0"] + p["x1"]) / 2, (p["y0"] + p["y1"]) / 2

    def boss_on_pad_design(root):
        x, y = _d9_pad2(root)
        _edit_json(root / "design.json", lambda j: j["case"]["screws"]["positions"][3].update(x=round(x + 4.0, 3), y=round(y, 3)))

    def boss_on_pad_cad(root):
        x, y = _d9_pad2(root)
        _edit_json(root / "CAD/positions.json", lambda j: j["screws"][3].update(x=round(x + 4.0, 3), y=round(y, 3)))

    def pad_under_boss_json(root):
        b = d["case"]["screws"]["positions"][0]
        _edit_json(root / "PCB/build/bottom_pads.json", lambda j: j["pads"].append(
            {"ref": "TP1", "pad": "1", "x0": b["x"] + 4.5, "y0": b["y"] - 0.5, "x1": b["x"] + 5.5, "y1": b["y"] + 0.5}))

    def real_boss_clean(root):
        if not (root / "PCB/frostbite.kicad_pcb").is_file() or not (root / "PCB/build/bottom_pads.json").is_file():
            raise SkipCase("real PCB or PCB/build/bottom_pads.json not present")

    def design_bad_pin(root):
        _edit_json(root / "design.json", lambda j: j["pins"][9].__setitem__("gpio", "GP5"))

    def design_dup_led(root):
        _edit_json(root / "design.json", lambda j: j["keys"][1].__setitem__("led", 0))

    def bom_too_many(root):
        _edit_json(root / "design.json", lambda j: j["leds"].__setitem__("count", 17))

    def pkg_clean(root):
        (root / "CAD").mkdir(exist_ok=True)
        if not any(q.suffix.lower() in (".step", ".stp", ".3mf") for q in (root / "CAD").rglob("*")):
            (root / "CAD/frostbite.step").write_text("ISO-10303-21;")
        pcb_clean(root)
        prod = root / "production"
        prod.mkdir(exist_ok=True)
        (prod / "gerbers.zip").write_bytes(b"PK\x05\x06" + b"\0" * 18)
        (prod / "firmware.uf2").write_bytes(synth_uf2())
        (prod / "Top.step").write_text("ISO-10303-21;")
        img = root / "docs"
        img.mkdir(exist_ok=True)
        for n in ("render", "schematic", "pcb", "case-exploded"):
            (img / f"{n}.png").write_bytes(b"\x89PNG")
        (root / "README.md").write_text(
            "# Frostbite\n![Frostbite render](docs/render.png)\n![Schematic](docs/schematic.png)\n"
            "![PCB](docs/pcb.png)\n![Case exploded](docs/case-exploded.png)\n\n## BOM\n\n| Part | Qty |\n|---|---|\n| XIAO | 1 |\n")

    def pkg_broken(root):
        (root / "production/gerbers.zip").unlink()
        (root / "docs/schematic.png").unlink()

    def netlist_check(kind):
        def fn(ctx):
            chk = Check(ctx, "G2.netlist", "G2", "self-test netlist logic")
            text = synth_netlist(d, None if kind == "clean" else kind)
            from . import sexpr
            C.check_netlist(chk, d, sexpr.load_netlist(text))
            return chk
        return fn

    def noop(root):
        pass

    cases = [
        Case("design.json: wrong GPIO for a XIAO pin", "G0.design_json", C.g0_design_json, noop, design_bad_pin, "D9"),
        Case("design.json: duplicate LED index", "G0.design_json", C.g0_design_json, noop, design_dup_led, "leds"),
        Case("keyboard.json: swapped column pins", "G2.firmware_pins", C.g2_firmware_pins, fw_clean, fw_swap_cols, "matrix_pins.cols"),
        Case("config.h: swapped I2C SDA/SCL", "G2.firmware_pins", C.g2_firmware_pins, fw_clean, fw_swap_i2c, "I2C1_SDA_PIN"),
        Case("keyboard.json: 12 LEDs instead of 13", "G2.firmware_pins", C.g2_firmware_pins, fw_clean, fw_led_count, "LED count"),
        Case("netlist: OLED SCL/SDA swapped", "G2.netlist", netlist_check("oled_swap"), noop, None, "OLED1 pin 3"),
        Case("netlist: LED chain broken after LED7", "G2.netlist", netlist_check("chain_break"), noop, None, "LED chain"),
        Case("netlist: XIAO D9/D10 swapped", "G2.netlist", netlist_check("xiao_pin"), noop, None, "XIAO D9"),
        Case("pcb: SW5 moved 0.2 mm", "G3.positions", C.g3_positions, pcb_clean, pcb_move_sw5, "SW5"),
        Case("pcb: chain LEDs 3/4 swapped", "G3.positions", C.g3_positions, pcb_clean, pcb_swap_led_chain, "chain LED 3"),
        Case("pcb: 3 copper layers", "G3.outline_layers", C.g3_outline_layers, pcb_clean, pcb_three_layers, "copper layers"),
        Case("uf2: truncated", "G6.production_uf2", C.g6_production_uf2, uf2_clean, uf2_truncate, "multiple of 512"),
        Case("uf2: wrong family ID", "G6.production_uf2", C.g6_production_uf2, uf2_clean, uf2_family, "family"),
        Case("stl: non-watertight Top", "G4.stl_mesh", C.g4_stl_mesh, stl_clean, stl_hole, "not watertight"),
        Case("stl: one cutout 14.3 mm", "G4.switch_cutouts", C.g4_switch_cutouts, stl_clean, stl_big_cutout, "14.3"),
        Case("stl: one cutout moved 0.5 mm", "G4.switch_cutouts", C.g4_switch_cutouts, stl_clean, stl_moved_cutout, "pattern"),
        Case("stl: encoder hole 1 mm off", "X.cross_positions", C.x_cross_positions, stl_clean, plate_encoder_moved, "encoder"),
        Case("CAD positions: SW7 moved 0.4 mm", "X.cross_positions", C.x_cross_positions, cadpos_clean, cadpos_move, "SW7"),
        Case("CAD positions: USB cutout 13.0 < 13.5 mm", "X.cross_positions", C.x_cross_positions, cadpos_clean, cadpos_usb_narrow, "usb_cutout w"),
        Case("boss (design.json) moved onto D9 pad", "X.boss_vs_pads", C.x_boss_vs_pads, boss_clean, boss_on_pad_design, "[design.json vs"),
        Case("boss (CAD/positions.json) moved onto D9 pad", "X.boss_vs_pads", C.x_boss_vs_pads, boss_clean, boss_on_pad_cad, "[CAD/positions.json vs"),
        Case("bottom_pads.json: pad 0.15 mm from a boss", "X.boss_vs_pads", C.x_boss_vs_pads, boss_clean, pad_under_boss_json, "vs PCB/build/bottom_pads.json] boss 0"),
        Case("real PCB: design.json boss moved onto D9 pad", "X.boss_vs_pads", C.x_boss_vs_pads, real_boss_clean, boss_on_pad_design, "D9 pad 2"),
        Case("BOM: 17 LEDs > kit 16", "G5.bom_kit", C.g5_bom_kit, noop, bom_too_many, "leds"),
        Case("package: gerbers.zip and schematic image missing", "G8.package", C.g8_package, pkg_clean, pkg_broken, "gerbers.zip"),
    ]

    for i, cs in enumerate(cases):
        base = tmp / f"case{i:02d}"
        root = base / "project"
        _copy_project(real, root)
        row = {"case": cs.name, "check": cs.cid}
        try:
            cs.clean(root)
            clean = cs.fn(_ctx(root, base / "clean"))
            row["clean_status"] = clean.status
            row["clean_reasons"] = clean.failures[:3] or ([clean.not_run_reason] if clean.not_run_reason else [])
            if cs.fault is None:
                # netlist-style cases build their own fault inside fn; reuse fn with fault kind
                faulty = None
            else:
                cs.fault(root)
                faulty = cs.fn(_ctx(root, base / "fault"))
            if faulty is None:
                kind = {"OLED1 pin 3": "oled_swap", "LED chain": "chain_break", "XIAO D9": "xiao_pin"}[cs.expect]
                clean = netlist_check("clean")(_ctx(root, base / "clean"))
                row["clean_status"] = clean.status
                row["clean_reasons"] = clean.failures[:3]
                faulty = netlist_check(kind)(_ctx(root, base / "fault"))
            row["fault_status"] = faulty.status
            row["fault_reasons"] = faulty.failures[:5]
            hit = any(cs.expect in f for f in faulty.failures)
            row["ok"] = clean.status == PASS and faulty.status == FAIL and hit
            if not row["ok"]:
                row["why"] = ("clean copy did not PASS" if clean.status != PASS else
                              "fault not detected" if faulty.status != FAIL else f"no reason mentions {cs.expect!r}")
        except SkipCase as e:
            row.update(ok=None, skipped=str(e))
        except Exception as e:
            import traceback
            row.update(ok=False, why=f"self-test crashed: {type(e).__name__}: {e}",
                       traceback=traceback.format_exc().splitlines()[-8:])
        results.append(row)
        mark = {True: "ok  ", False: "BAD ", None: "skip"}[row["ok"]]
        print(f"{mark} {cs.cid:20} {cs.name:48} clean={row.get('clean_status')} fault={row.get('fault_status')} "
              f"{(row.get('fault_reasons') or [row.get('skipped') or row.get('why') or ''])[0]}")

    # harness-level assertions: NOT_RUN must not pass for missing tools/inputs, FAIL drives the exit code
    meta = []
    empty = tmp / "empty"
    empty.mkdir()
    (empty / "design.json").write_text((real / "design.json").read_text())
    ectx = _ctx(empty, tmp / "empty-ev")
    for fn, cid in ((C.g3_drc, "G3.drc"), (C.g2_erc, "G2.erc"), (C.g4_stl_mesh, "G4.stl_mesh"),
                    (C.g6_production_uf2, "G6.production_uf2"), (C.g7_host_tests, "G7.host_tests")):
        st = fn(ectx).status
        meta.append({"assert": f"{cid} on an empty project is NOT_RUN", "got": st, "ok": st == NOT_RUN})
    fake = [{"status": PASS}, {"status": NOT_RUN}]
    meta.append({"assert": "exit code 0 when only PASS/NOT_RUN", "got": exit_code(fake), "ok": exit_code(fake) == 0})
    fake.append({"status": FAIL})
    meta.append({"assert": "exit code 1 when any FAIL", "got": exit_code(fake), "ok": exit_code(fake) == 1})
    pinned = sha256(verify / C.JLC_DRU.split("verify/")[1]) == C.JLC_DRU_SHA256
    meta.append({"assert": "pinned JLCPCB rules file matches its SHA-256", "got": pinned, "ok": pinned})
    for m in meta:
        print(f"{'ok  ' if m['ok'] else 'BAD '} meta: {m['assert']} (got {m['got']})")

    bad = [r for r in results if r["ok"] is False] + [m for m in meta if not m["ok"]]
    summary = {"timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
               "status": "PASS" if not bad else "FAIL", "cases": results, "meta": meta,
               "skipped": [r["case"] for r in results if r["ok"] is None], "tmp": str(tmp)}
    (verify / "selftest.json").write_text(json.dumps(summary, indent=2) + "\n")
    n_ok = sum(1 for r in results if r["ok"])
    print(f"self-test {summary['status']}: {n_ok}/{len(results)} fault cases caught, "
          f"{len(summary['skipped'])} skipped, {sum(m['ok'] for m in meta)}/{len(meta)} harness assertions; wrote verify/selftest.json")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if not bad else 1


class SkipCase(Exception):
    pass
