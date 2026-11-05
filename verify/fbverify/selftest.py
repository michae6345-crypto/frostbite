"""--self-test. Each case builds a clean copy of the project, with fixtures generated from
design.json where a real file cannot serve, and requires PASS. It then injects one fault and
requires FAIL with a reason that names the fault."""
from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from . import checks as C
from . import geom, sexpr
from .core import FAIL, NOT_RUN, PASS, Check, Ctx, base_env, find_kicad_cli, scrub, sha256
from .main import NEEDS_REAL_PARTS, exit_code, write_report

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
               f' (fp_rect (start {-r["w"] / 2} {-r["h"] / 2}) (end {r["w"] / 2} {r["h"] / 2}) (layer "B.Fab"))'
               ' (pad "12" smd rect (at -7.6 -5.0) (size 1 0.8) (layers "B.Cu") (net "+3V3") (pinfunction "3V3"))'
               ' (pad "13" smd rect (at -7.6 -2.5) (size 1 0.8) (layers "B.Cu") (net "GND") (pinfunction "GND")))')
    for k in d["keys"]:
        n = k["ref"][2:]
        out.append(f' (footprint "Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal" (layer "F.Cu") {A(k["x"], k["y"] + 8.5)}'
                   f' (property "Reference" "D{n}") (property "Value" "1N4148")'
                   f' (pad "1" thru_hole rect (at -3.81 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask") (net "ROW{k["row"]}"))'
                   f' (pad "2" thru_hole circle (at 3.81 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask")))')
    # GND pour on B.Cu: a corner patch, standing in for a fill that keeps a relief gap to every pad
    out.append(f' (zone (net "GND") (layer "B.Cu") (connect_pads (clearance 0.3)) (min_thickness 0.25)'
               f' (filled_polygon (layer "B.Cu") (pts (xy {OX + 1} {OY + 1}) (xy {OX + 3} {OY + 1}) (xy {OX + 3} {OY + 3}) (xy {OX + 1} {OY + 3}))))')
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
    if fault == "five_volt":
        node("+5V", "U1", "14", "5V")
        node("+5V", "SW10", "S1", "S1")
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
    if fault == "led_part":
        comps.append(("LED1", "SK6812MINI-E", "frostbite:SK6812MINI-E_key"))
        node("+3V3", "LED1", "1", "VDD")
        node("GND", "LED1", "3", "GND")
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


def synth_solid(d: dict):
    """A plain watertight plate: only G4.stl_mesh uses it."""
    import shapely.geometry as g
    import trimesh
    sh = d["case"]["shell"]
    return trimesh.creation.extrude_polygon(g.box(0, 0, sh["w"], sh["h"]).buffer(-1), 1.5)


def synth_box(height: float):
    import trimesh
    return trimesh.creation.box(extents=(34.0, 13.5, height))


def _stack(layers, W, H):
    """Extrude [(polygon, z0, z1)] into one mesh, centred like an export."""
    import trimesh
    meshes = []
    for poly, z0, z1 in layers:
        for p in (poly.geoms if hasattr(poly, "geoms") else [poly]):
            m = trimesh.creation.extrude_polygon(p, z1 - z0)
            m.apply_translation([-W / 2, -H / 2, z0])
            meshes.append(m)
    return trimesh.util.concatenate(meshes)


def _shell(d: dict):
    import shapely.geometry as g
    W, H = d["pcb"]["w"], d["pcb"]["h"]
    sh = d["case"]["shell"]
    x0, y0 = (W - sh["w"]) / 2, (H - sh["h"]) / 2
    return g.box(x0, y0, x0 + sh["w"], y0 + sh["h"]), x0, y0


def synth_top(d: dict, cut=14.0, move=None, enc=("rect", 12.98, 16.0), window=(31.0, 12.98), window_dx=0.0,
              depth=5.43, hole_move=0.0, hole_d=3.4, tongue=True):
    """A Top like the real one, in print orientation: plate top on the bed at z=0, USB tongue rising to z=depth."""
    import shapely.geometry as g
    import shapely.ops as o
    W, H = d["pcb"]["w"], d["pcb"]["h"]
    shell, x0, y0 = _shell(d)
    tol = d["case"]["tolerance"]
    cuts, pockets = [], []
    for i, k in enumerate(d["keys"]):
        x, y = k["x"], k["y"]
        c = cut[i] if isinstance(cut, list) else cut
        if move and move[0] == i:
            x += move[1]
        cuts.append(g.box(x - c / 2, y - c / 2, x + c / 2, y + c / 2))
        pockets.append(g.box(x - 7.7, y - 7.7, x + 7.7, y + 7.7))
    ex, ey = d["encoder"]["x"], d["encoder"]["y"]
    if enc[0] == "round":
        eo = g.Point(ex, ey).buffer(enc[1] / 2, 64)
    else:
        eo = g.box(ex - enc[1] / 2, ey - enc[2] / 2, ex + enc[1] / 2, ey + enc[2] / 2)
    w, mod = d["oled"]["window"], d["oled"]["module"]
    cxw, cyw = w["x"] + w["w"] / 2, w["y"] + w["h"] / 2
    cxw += window_dx
    win = g.box(cxw - window[0] / 2, cyw - window[1] / 2, cxw + window[0] / 2, cyw + window[1] / 2)
    recess = g.box(mod["x"] - 1.1, mod["y"] - 0.8, mod["x"] + mod["w"] + tol, mod["y"] + mod["h"] + 0.8)
    holes = [g.Point(sc["x"] + (hole_move if i == 0 else 0.0), sc["y"]).buffer(hole_d / 2, 48)
             for i, sc in enumerate(d["case"]["screws"]["positions"])]
    all_holes = o.unary_union(holes)
    layers = [(shell.difference(o.unary_union(cuts + [eo, win])).difference(all_holes), 0.0, 1.0),
              (shell.difference(o.unary_union(cuts + [eo, recess])).difference(all_holes), 1.0, 1.5),
              (shell.difference(o.unary_union(pockets + [eo, recess])).difference(all_holes), 1.5, 2.5)]
    if tongue:
        uw = d["case"]["usb_cutout"]["w"]
        xc = d["mcu"]["rect"]["x"] + d["mcu"]["rect"]["w"] / 2
        layers.append((g.box(xc - uw / 2 + 0.2, y0, xc + uw / 2 - 0.2, -tol), 2.5, depth))
    return _stack(layers, W, H)


def synth_bottom(d: dict, hole_move=0.0, no_hole=False, usb_w=None, notch=True, boss_in=0.0, floor_post=False):
    """A Bottom like the real one, in print orientation: underside on the bed at z=0, rim at z=14.9."""
    import shapely.geometry as g
    import shapely.ops as o
    W, H = d["pcb"]["w"], d["pcb"]["h"]
    shell, x0, y0 = _shell(d)
    tol, sc = d["case"]["tolerance"], d["case"]["screws"]
    pocket = g.box(-tol, -tol, W + tol, H + tol)
    wall = shell.difference(pocket)
    centres = [(p["x"] + (boss_in if p["x"] < W / 2 else -boss_in), p["y"] + (boss_in if p["y"] < H / 2 else -boss_in))
               for p in sc["positions"]]
    if boss_in:
        wall = wall.union(o.unary_union([g.Point(c).buffer(sc["boss_od"] / 2, 48) for c in centres]))
    centres = [(x + (hole_move if i == 0 else 0.0), y) for i, (x, y) in enumerate(centres)]
    inserts = o.unary_union([g.Point(c).buffer(2.35, 48) for i, c in enumerate(centres) if not (no_hole and i == 0)])
    clear = o.unary_union([g.Point(c).buffer(1.7, 48) for c in centres])
    uw = d["case"]["usb_cutout"]["w"] if usb_w is None else usb_w
    xc = d["mcu"]["rect"]["x"] + d["mcu"]["rect"]["w"] / 2
    cut = g.box(xc - uw / 2, y0 - 1, xc + uw / 2, 1.0) if notch else g.GeometryCollection()
    floor = shell.difference(clear)
    layers = [(shell, 0.0, 1.0), (floor, 1.0, 2.5), (wall.difference(clear), 2.5, 3.97),
              (wall.difference(clear).difference(cut), 3.97, 10.9), (wall.difference(inserts).difference(cut), 10.9, 14.9)]
    if floor_post:                                # stands under the XIAO, up to the PCB underside
        layers.append((g.box(19.0, 8.0, 23.0, 12.0), 2.5, 10.8))
    m = _stack(layers, W, H)
    m.apply_scale([1, -1, 1])     # exported as modelled: mesh y is minus PCB y, where the Top is turned over about x
    return m


class SkipCase(Exception):
    pass


class Case:
    def __init__(self, name, cid, fn, clean, fault, expect_reason, kicad=False):
        self.name, self.cid, self.fn, self.clean, self.fault, self.expect = name, cid, fn, clean, fault, expect_reason
        self.kicad = kicad


def _ctx(root: Path, base: Path, kicad=False) -> Ctx:
    ev = base / "evidence"
    work = base / "work"
    work.mkdir(parents=True, exist_ok=True)
    return Ctx(root=root, evidence_dir=ev, work=work, kicad_cli=find_kicad_cli() if kicad else None, env=base_env(),
               run_qmk=False, allow_regen=False)


def _copy_project(real: Path, dst: Path):
    dst.mkdir(parents=True)
    shutil.copy2(real / "design.json", dst / "design.json")
    for sub in ("Firmware", "PCB", "production", "CAD", "host"):
        if (real / sub).is_dir():
            shutil.copytree(real / sub, dst / sub, ignore=shutil.ignore_patterns(
                ".venv", "*-backups", ".build", "__pycache__", ".pytest_cache", "previews", "images"))
    for f in ("README.md", "BOM.csv"):
        if (real / f).is_file():
            shutil.copy2(real / f, dst / f)


def _edit_json(p: Path, fn):
    j = json.loads(p.read_text())
    fn(j)
    p.write_text(json.dumps(j, indent=2))


def _drop_stls(prod: Path):
    for q in prod.glob("*"):
        if q.suffix.lower() == ".stl":
            q.unlink()


def _positions(d: dict, oled_window: dict) -> dict:
    """A CAD/positions.json that agrees with design.json."""
    r = d["mcu"]["rect"]
    return {"keys": [{"ref": k["ref"], "x": k["x"], "y": k["y"]} for k in d["keys"]],
            "encoder": {"x": d["encoder"]["x"], "y": d["encoder"]["y"]},
            "usb_cutout": {"x": r["x"] + r["w"] / 2, "w": d["case"]["usb_cutout"]["w"], "h": d["case"]["usb_cutout"]["h"]},
            "oled_window": oled_window,
            "screws": [dict(p) for p in d["case"]["screws"]["positions"]]}


def real_fault(real: Path, name: str):
    """A fault made by editing the real part in CadQuery (probe_fault.py). Runs on the copy at root."""
    def fn(root):
        py = real / "CAD/.venv/bin/python"
        if not py.is_file():
            raise SkipCase("CAD/.venv/bin/python missing")
        env = {**base_env(), "PYTHONDONTWRITEBYTECODE": "1"}
        subprocess.run([str(py), str(Path(__file__).with_name("probe_fault.py")), str(root), name], check=True, env=env,
                       capture_output=True, text=True, timeout=120)
    return fn


def _edit_bom(root: Path, fn):
    p = root / "BOM.csv"
    rows = list(csv.DictReader(io.StringIO(p.read_text())))
    fn(rows)
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    p.write_text(out.getvalue())


def run_selftest(verify: Path, real: Path) -> int:
    d = json.loads((real / "design.json").read_text())
    tmp = Path(tempfile.mkdtemp(prefix="fbverify-selftest-"))
    results = []
    kb_rel = Path(C.KB_DIR) / "keyboard.json"
    have_fw = (real / kb_rel).is_file()

    # Fixture builders edit the project copy at `root`.
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

    def fw_ws2812(root):
        _edit_json(root / kb_rel, lambda j: j.update(ws2812={"pin": "GP0", "driver": "vendor"}))

    def fw_rgb_matrix(root):
        _edit_json(root / kb_rel, lambda j: j["features"].update(rgb_matrix=True))

    def pcb_clean(root):
        pd = root / "PCB"
        shutil.rmtree(pd, ignore_errors=True)
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

    def pcb_led_back(root):
        """One SK6812 footprint added to the board that is there, real or generated."""
        p = root / "PCB/frostbite.kicad_pcb"
        t = p.read_text().rstrip()
        assert t.endswith(")"), "fixture: board file does not end in )"
        fp = ('(footprint "frostbite:SK6812MINI-E_key" (layer "F.Cu") (at 130 80)\n'
              ' (property "Reference" "LED1" (at 0 0 0) (layer "F.SilkS"))\n (property "Value" "SK6812MINI-E" (at 0 0 0) (layer "F.Fab"))\n'
              ' (pad "1" smd rect (at -1.6 -0.7) (size 1 0.8) (layers "F.Cu") (net "+5V"))\n'
              ' (pad "3" smd rect (at 1.6 0.7) (size 1 0.8) (layers "F.Cu") (net "GND")))\n')
        p.write_text(t[:-1] + fp + ")\n")

    def uf2_clean(root):
        (root / "production").mkdir(exist_ok=True)
        for n in ("firmware.uf2", "bringup.uf2"):
            p = root / "production" / n
            if not p.is_file():
                p.write_bytes(synth_uf2())
            if (root / C.KB_DIR).is_dir():
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

    def bringup_truncate(root):
        p = root / "production/bringup.uf2"
        b = p.read_bytes()
        p.write_bytes(b[: len(b) - 512 * 2 - 100])

    def bringup_missing(root):
        (root / "production/bringup.uf2").unlink()

    def old_led_test_uf2(root):
        (root / "production/led-test.uf2").write_bytes(synth_uf2())

    def stale_glowband(root):
        synth_solid(d).export(root / "production/GlowBand.stl")

    def stl_clean(root):
        prod = root / "production"
        prod.mkdir(exist_ok=True)
        _drop_stls(prod)
        for n in C.PARTS:
            synth_solid(d).export(prod / f"{n}.stl")

    def stl_hole(root):
        import trimesh
        p = root / "production/Top.stl"
        m = trimesh.load(str(p), force="mesh")
        keep = [True] * len(m.faces)
        keep[0] = keep[1] = False
        m.update_faces(keep)
        m.export(p)

    def top_write(root, bot=None, **kw):
        prod = root / "production"
        prod.mkdir(exist_ok=True)
        _drop_stls(prod)
        dd = kw.pop("dd", d)
        synth_top(dd, **kw).export(prod / "Top.stl")
        synth_bottom(dd, **(bot or {})).export(prod / "Bottom.stl")
        synth_box(dd["case"]["oled_support"]["module_gap"]).export(prod / "OLEDSupport.stl")
        o = d["oled"]["window"]
        c = kw.get("window", (31.0, 12.98))
        cut = {"x": o["x"] + o["w"] / 2 + kw.get("window_dx", 0.0) - c[0] / 2, "y": o["y"] + o["h"] / 2 - c[1] / 2, "w": c[0], "h": c[1]}
        (root / "CAD").mkdir(exist_ok=True)
        (root / "CAD/positions.json").write_text(json.dumps(_positions(d, {**o, "cut": cut})))

    def t(**kw):
        return lambda root: top_write(root, **kw)

    def b(**kw):
        return lambda root: top_write(root, bot=kw)

    def with_gap(gap):
        def fn(root):
            _edit_json(root / "design.json", lambda j: j["case"]["oled_support"].__setitem__("module_gap", gap))
        return fn

    def sunk(**kw):
        """Glass under the lip (module_gap 0.9): a window smaller than the glass is fine if the active area shows."""
        def fn(root):
            dd = json.loads(json.dumps(d))
            dd["case"]["oled_support"]["module_gap"] = 0.9
            top_write(root, dd=dd, **kw)
            with_gap(0.9)(root)
        return fn

    def prose_edit(root):
        _edit_json(root / "design.json", lambda j: j["oled"].__setitem__("mount", "reworded"))

    def no_gap(root):
        _edit_json(root / "design.json", lambda j: j["case"]["oled_support"].pop("module_gap"))

    def wrong_support(root):
        synth_box(2.0).export(root / "production/OLEDSupport.stl")

    def support_missing(root):
        (root / "production/OLEDSupport.stl").unlink()

    def step_swapped(root):
        shutil.copy2(root / "production/Knob.step", root / "production/OLEDSupport.step")

    def annular_019(root):
        p = root / "PCB/frostbite.kicad_pcb"
        t0 = p.read_text()
        t1, n = re.subn(r'\(size 2\.3 2\.3\)(\s+)\(drill 1\.524\)', r'(size 1.904 1.904)\1(drill 1.524)', t0, count=1)
        assert n == 1, "fixture: no 2.3 / 1.524 pad in the PCB"
        p.write_text(t1)

    def project_loosens(root):
        p = root / "PCB/frostbite.kicad_dru"
        t0 = p.read_text()
        assert "(min 0.20mm)" in t0, "fixture: project rule text changed"
        p.write_text(t0.replace("(min 0.20mm)", "(min 0.15mm)"))

    def top_broken(root):
        import trimesh
        p = root / "production/Top.stl"
        m = trimesh.load(str(p), force="mesh")
        walls = (abs(m.face_normals[:, 2]) < 0.01).nonzero()[0]
        keep = [True] * len(m.faces)
        for i in walls[: len(walls) // 2]:
            keep[i] = False
        m.update_faces(keep)
        m.export(p)

    def old_b1(root):
        """The real audited blocked tray (B1, the old Top with its bosses inside the envelope) in place of the Bottom."""
        shutil.copy2(verify / "fixtures/old_b1_Top.stl", root / "production/Bottom.stl")

    def stale_cut(root):
        _edit_json(root / "CAD/positions.json", lambda j: j["oled_window"].__setitem__("cut", dict(d["oled"]["window"])))

    def usb_filter_removed(root):
        p = root / "host/frostbite_host/device.py"
        t0 = p.read_text()
        t1 = t0.replace("hid.enumerate(VENDOR_ID, PRODUCT_ID)", "hid.enumerate()")
        t1 = t1.replace('if d.get("vendor_id") == VENDOR_ID and d.get("product_id") == PRODUCT_ID\n            and d.get("usage_page")',
                        'if d.get("usage_page")')
        assert t1 != t0 and "d.get(\"vendor_id\") == VENDOR_ID" not in t1, "fixture: filter text not found in device.py"
        p.write_text(t1)

    def fw_pid(root):
        _edit_json(root / kb_rel, lambda j: j["usb"].__setitem__("pid", "0x4643"))

    def design_pid(root):
        _edit_json(root / "design.json", lambda j: j["firmware"]["usb"].__setitem__("pid", "0x4643"))

    def gnd_override(root):
        p = root / "PCB/frostbite.kicad_pcb"
        t0 = p.read_text()
        key = '(size 1 0.8) (layers "B.Cu") (net "GND")'
        assert key in t0, "fixture: GND pad not found"
        p.write_text(t0.replace(key, '(size 1 0.8) (layers "B.Cu") (zone_connect 2) (net "GND")', 1))

    def gnd_zone_solid(root):
        p = root / "PCB/frostbite.kicad_pcb"
        p.write_text(p.read_text().replace("(connect_pads (clearance 0.3))", "(connect_pads yes (clearance 0.3))"))

    def gnd_flooded_fill(root):
        p = root / "PCB/frostbite.kicad_pcb"
        t0 = p.read_text()
        p.write_text(t0.replace(f'(xy {OX + 1} {OY + 1}) (xy {OX + 3} {OY + 1}) (xy {OX + 3} {OY + 3}) (xy {OX + 1} {OY + 3})',
                                f'(xy {OX} {OY}) (xy {OX + 61} {OY}) (xy {OX + 61} {OY + 83}) (xy {OX} {OY + 83})'))

    def real_gnd_clean(root):
        if not (root / "PCB/frostbite.kicad_pcb").is_file():
            raise SkipCase("real PCB not present")

    def real_gnd_override(root):
        p = root / "PCB/frostbite.kicad_pcb"
        t0 = p.read_text()
        t1, n = re.subn(r'\(pad "13" thru_hole (\w+)', r'(pad "13" thru_hole \1 (zone_connect 2)', t0, count=1)
        assert n == 1, "fixture: U1 pad 13 not found"
        p.write_text(t1)

    def f1_back(root):
        p = root / C.KB_DIR / "keymaps/default/keymap.c"
        t0 = p.read_text()
        key = "for (uint8_t x = 0; x < 126; x += 3) oled_write_pixel(x, 19, true);"
        assert key in t0, "fixture: divider loop not found in keymap.c"
        p.write_text(t0.replace(key, 'oled_set_cursor(0, 2); oled_write_P(PSTR("                     "), false);\n    ' + key))

    def bringup_broken(root):
        p = root / C.KB_DIR / "keymaps/bringup/keymap.c"
        t0 = p.read_text()
        t1 = t0.replace("knob: turn it", "knob: spin it")
        assert t1 != t0, "fixture: start screen text not found in the bringup keymap"
        p.write_text(t1)

    def runsh_bad_exit(root):
        p = root / "Firmware/tests/run.sh"
        t0 = p.read_text()
        assert t0.rstrip().endswith("exit $rc2"), "fixture: run.sh does not end in exit $rc2"
        p.write_text(t0.rstrip()[: -len("exit $rc2")] + "exit 7\n")

    def runsh_skips_bringup(root):
        p = root / "Firmware/tests/run.sh"
        t0 = p.read_text()
        key = "./bringup_test\nrc2=$?"
        assert key in t0, "fixture: bringup run not found in run.sh"
        p.write_text(t0.replace(key, "rc2=0"))

    def host_test_breaks(root):
        (root / "host/tests/test_selftest_fault.py").write_text("def test_fault():\n    assert False\n")

    def cadpos_clean(root):
        shutil.rmtree(root / "PCB", ignore_errors=True)
        for s in (root / "production").glob("*.stl") if (root / "production").is_dir() else []:
            s.unlink()
        (root / "CAD").mkdir(exist_ok=True)
        (root / "CAD/positions.json").write_text(json.dumps(_positions(d, dict(d["oled"]["window"]))))

    def cadpos_move(root):
        _edit_json(root / "CAD/positions.json", lambda j: j["keys"][6].__setitem__("y", j["keys"][6]["y"] + 0.4))

    def cadpos_usb_narrow(root):
        _edit_json(root / "CAD/positions.json", lambda j: j["usb_cutout"].__setitem__("w", 13.0))

    def boss_clean(root):
        pcb_clean(root)
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
            {"ref": "TP1", "pad": "1", "x0": b["x"] + 3.95, "y0": b["y"] - 0.5, "x1": b["x"] + 4.95, "y1": b["y"] + 0.5}))

    def pad_shifted_json(root):
        def edit(j):
            p = next(p for p in j["pads"] if p["ref"] == "U1" and p["pad"] == "1")
            p["x0"] -= 1.0
            p["x1"] -= 1.0
        _edit_json(root / "PCB/build/bottom_pads.json", edit)

    def real_boss_clean(root):
        if not (root / "PCB/frostbite.kicad_pcb").is_file() or not (root / "PCB/build/bottom_pads.json").is_file():
            raise SkipCase("real PCB or PCB/build/bottom_pads.json not present")

    def design_bad_pin(root):
        _edit_json(root / "design.json", lambda j: next(p for p in j["pins"] if p["xiao"] == "D9").__setitem__("gpio", "GP5"))

    def design_led_din(root):
        _edit_json(root / "design.json", lambda j: j["pins"].append({"xiao": "D6", "gpio": "GP0", "net": "LED_DIN"}))

    def design_leds_block(root):
        _edit_json(root / "design.json", lambda j: j.update(leds={"count": 13, "glow": []}))

    def design_key_led(root):
        _edit_json(root / "design.json", lambda j: j["keys"][1].__setitem__("led", 0))

    def design_tilt(root):
        _edit_json(root / "design.json", lambda j: j["case"]["shell"].__setitem__("tilt_deg", 6))

    def design_five_volt(root):
        _edit_json(root / "design.json", lambda j: j["power"].__setitem__("5V", "XIAO 5V -> LEDs"))

    def bom_too_many(root):
        _edit_json(root / "design.json", lambda j: j["case"].__setitem__("inserts", "8 x M3 heat-set (OD 5, L 4, hole 4.7)"))

    def pkg_clean(root):
        """The real README and BOM.csv, on stand-in files."""
        (root / "CAD").mkdir(exist_ok=True)
        if not any(q.suffix.lower() in (".step", ".stp", ".3mf") for q in (root / "CAD").rglob("*")):
            (root / "CAD/frostbite.step").write_text("ISO-10303-21;")
        pcb_clean(root)
        prod = root / "production"
        prod.mkdir(exist_ok=True)
        (prod / "gerbers.zip").write_bytes(b"PK\x05\x06" + b"\0" * 18)
        (prod / "firmware.uf2").write_bytes(synth_uf2())
        (prod / "bringup.uf2").write_bytes(synth_uf2())
        for n in C.PARTS:
            (prod / f"{n}.step").write_text("ISO-10303-21;")
            (prod / f"{n}.stl").write_text("solid x")
        for m in C.IMG_RE.finditer((root / "README.md").read_text()):
            src = m.group(2) or m.group(3)
            if not re.match(r"https?://", src):
                (root / src).parent.mkdir(parents=True, exist_ok=True)
                (root / src).write_bytes(b"\x89PNG")

    def pkg_broken(root):
        (root / "production/gerbers.zip").unlink()
        (root / "production/OLEDSupport.step").unlink()
        (root / "PCB/images/schematic.png").unlink()

    def readme_drop(*names):
        def fn(root):
            p = root / "README.md"
            lines = p.read_text().splitlines(keepends=True)
            keep = [ln for ln in lines if not any(n in ln and "src=" in ln for n in names)]
            assert len(keep) == len(lines) - len(names), f"fixture: image lines {names} not found in README.md"
            p.write_text("".join(keep))
        return fn

    def readme_no_bom_table(root):
        p = root / "README.md"
        p.write_text(re.sub(r"^\|.*\|\s*$\n", "", p.read_text(), flags=re.M))

    def bom_missing(root):
        (root / "BOM.csv").unlink()

    def bom_blank(col):
        def fn(root):
            _edit_bom(root, lambda rows: rows[3].__setitem__(col, ""))
        return fn

    def bom_price_text(root):
        _edit_bom(root, lambda rows: rows[-1].__setitem__("price_usd", "free-ish"))

    def bom_link_text(root):
        _edit_bom(root, lambda rows: rows[0].__setitem__("link", "see the kit"))

    def bom_no_column(root):
        def edit(rows):
            for r in rows:
                r.pop("price_usd")
        _edit_bom(root, edit)

    def netlist_check(kind):
        def fn(ctx):
            chk = Check(ctx, "G2.netlist", "G2", "self-test netlist logic")
            text = synth_netlist(d, None if kind == "clean" else kind)
            C.check_netlist(chk, d, sexpr.load_netlist(text))
            return chk
        return fn

    def noop(root):
        pass

    cases = [
        Case("design.json: wrong GPIO for a XIAO pin", "G0.design_json", C.g0_design_json, noop, design_bad_pin, "D9"),
        Case("design.json: LED_DIN back in the pins", "G0.design_json", C.g0_design_json, noop, design_led_din, "net LED_DIN"),
        Case("design.json: leds block back", "G0.design_json", C.g0_design_json, noop, design_leds_block, "leds: block"),
        Case("design.json: a key has an led index", "G0.design_json", C.g0_design_json, noop, design_key_led, "SW2"),
        Case("design.json: a 5V rail back", "G0.design_json", C.g0_design_json, noop, design_five_volt, "rails"),
        Case("design.json: case tilted", "G0.design_json", C.g0_design_json, noop, design_tilt, "tilt_deg"),
        Case("keyboard.json: swapped column pins", "G2.firmware_pins", C.g2_firmware_pins, fw_clean, fw_swap_cols, "matrix_pins.cols"),
        Case("config.h: swapped I2C SDA/SCL", "G2.firmware_pins", C.g2_firmware_pins, fw_clean, fw_swap_i2c, "I2C1_SDA_PIN"),
        Case("keyboard.json: ws2812 back", "G2.firmware_pins", C.g2_firmware_pins, fw_clean, fw_ws2812, "ws2812"),
        Case("keyboard.json: rgb_matrix feature back", "G2.firmware_pins", C.g2_firmware_pins, fw_clean, fw_rgb_matrix, "rgb_matrix"),
        Case("netlist: OLED SCL/SDA swapped", "G2.netlist", netlist_check("oled_swap"), noop, None, "OLED1 pin 3"),
        Case("netlist: +5V net back", "G2.netlist", netlist_check("five_volt"), noop, None, "5 V net"),
        Case("netlist: an SK6812 part back", "G2.netlist", netlist_check("led_part"), noop, None, "LED parts"),
        Case("netlist: XIAO D9/D10 swapped", "G2.netlist", netlist_check("xiao_pin"), noop, None, "XIAO D9"),
        Case("pcb: SW5 moved 0.2 mm", "G3.positions", C.g3_positions, pcb_clean, pcb_move_sw5, "SW5"),
        Case("pcb: an LED footprint back", "G3.positions", C.g3_positions, pcb_clean, pcb_led_back, "LED footprints"),
        Case("real PCB: an LED footprint back", "G3.positions", C.g3_positions, real_gnd_clean, pcb_led_back, "LED footprints"),
        Case("real PCB: an LED footprint on +5V back", "G3.positions", C.g3_positions, real_gnd_clean, pcb_led_back, "5 V net"),
        Case("pcb: 3 copper layers", "G3.outline_layers", C.g3_outline_layers, pcb_clean, pcb_three_layers, "copper layers"),
        Case("uf2: truncated", "G6.production_uf2", C.g6_production_uf2, uf2_clean, uf2_truncate, "multiple of 512"),
        Case("uf2: wrong family ID", "G6.production_uf2", C.g6_production_uf2, uf2_clean, uf2_family, "family"),
        Case("uf2: bringup.uf2 truncated", "G6.production_uf2", C.g6_production_uf2, uf2_clean, bringup_truncate, "production/bringup.uf2: size"),
        Case("uf2: bringup.uf2 missing", "G6.production_uf2", C.g6_production_uf2, uf2_clean, bringup_missing, "bringup.uf2 missing"),
        Case("uf2: old led-test.uf2 left behind", "G6.production_uf2", C.g6_production_uf2, uf2_clean, old_led_test_uf2, "led-test.uf2"),
        Case("stl: non-watertight Top", "G4.stl_mesh", C.g4_stl_mesh, stl_clean, stl_hole, "not watertight"),
        Case("stl: GlowBand.stl left behind", "G4.stl_mesh", C.g4_stl_mesh, stl_clean, stale_glowband, "GlowBand.stl is not a part"),
        Case("CAD positions: SW7 moved 0.4 mm", "X.cross_positions", C.x_cross_positions, cadpos_clean, cadpos_move, "SW7"),
        Case("CAD positions: USB cutout 13.0 < 13.5 mm", "X.cross_positions", C.x_cross_positions, cadpos_clean, cadpos_usb_narrow, "usb_cutout w"),
        Case("boss (design.json) moved onto D9 pad", "X.boss_vs_pads", C.x_boss_vs_pads, boss_clean, boss_on_pad_design, "[design.json vs"),
        Case("boss (CAD/positions.json) moved onto D9 pad", "X.boss_vs_pads", C.x_boss_vs_pads, boss_clean, boss_on_pad_cad, "[CAD/positions.json vs"),
        Case("bottom_pads.json: pad 0.15 mm from a boss", "X.boss_vs_pads", C.x_boss_vs_pads, boss_clean, pad_under_boss_json, "vs PCB/build/bottom_pads.json] boss 0"),
        Case("real PCB: design.json boss moved onto D9 pad", "X.boss_vs_pads", C.x_boss_vs_pads, real_boss_clean, boss_on_pad_design, "D9 pad 2"),
        Case("real PCB: bottom_pads.json and the parse disagree by 1 mm", "X.boss_vs_pads", C.x_boss_vs_pads, real_boss_clean, pad_shifted_json, "sources disagree"),
        Case("stl: OLEDSupport.stl missing", "G4.stl_mesh", C.g4_stl_mesh, stl_clean, support_missing, "production/OLEDSupport.stl missing"),
        Case("top: one cutout 14.3 mm", "G4.switch_cutouts", C.g4_switch_cutouts, t(), t(cut=[14.0] * 4 + [14.3] + [14.0] * 4), "14.300"),
        Case("top: one cutout moved 0.5 mm", "G4.switch_cutouts", C.g4_switch_cutouts, t(), t(move=(4, 0.5)), "opening centre"),
        Case("top with a longer tongue: heights come from the part", "G4.switch_cutouts", C.g4_switch_cutouts, t(depth=8.0), t(depth=8.0, cut=13.7), "13.700"),
        Case("top: walls missing, slicer must not guess", "G4.switch_cutouts", C.g4_switch_cutouts, t(), top_broken, "lost material"),
        Case("encoder: round 17.4 clears, 15.0 hits the body", "G4.encoder_clearance", C.g4_encoder_clearance, t(enc=("round", 17.4)), t(enc=("round", 15.0)), "EC11 body"),
        Case("encoder: 12.98 x 16 clears, 11.9 x 16 does not", "G4.encoder_clearance", C.g4_encoder_clearance, t(), t(enc=("rect", 11.9, 16.0)), "EC11 body"),
        Case("oled window: 34 x 16 passes, 29 x 12.98 hits the glass", "G4.oled_clearance", C.g4_oled_clearance, t(window=(34.0, 16.0)), t(window=(29.0, 12.98)), "OLED glass hits"),
        Case("oled window: 12.98 clears the turned glass, 12.4 does not", "G4.oled_clearance", C.g4_oled_clearance, t(), t(window=(31.0, 12.4)), "OLED glass hits"),
        Case("oled window: smaller than the glass passes if the glass stays under the lip", "G4.oled_clearance", C.g4_oled_clearance,
             sunk(window=(28.0, 10.4), window_dx=1.8), sunk(window=(20.0, 10.4), window_dx=1.8), "active area not fully visible"),
        Case("oled: lip over the active area", "G4.oled_clearance", C.g4_oled_clearance, sunk(window=(28.0, 10.4), window_dx=1.8), sunk(window=(28.0, 6.0), window_dx=1.8), "active area not fully visible"),
        Case("oled gap 3.0 read from design.json: board hits the lip", "G4.oled_clearance", C.g4_oled_clearance, t(), with_gap(3.0), "OLED board hits"),
        Case("oled gap 2.5 read from design.json: glass proud", "G4.oled_clearance", C.g4_oled_clearance, t(), with_gap(2.5), "stands proud"),
        Case("oled gap missing from design.json", "G4.oled_clearance", C.g4_oled_clearance, t(), no_gap, "module_gap missing"),
        Case("oled: support height disagrees with module_gap", "G4.oled_clearance", C.g4_oled_clearance, t(), wrong_support, "OLEDSupport is 2.000"),
        Case("oled: OLEDSupport.stl missing", "G4.oled_clearance", C.g4_oled_clearance, t(), support_missing, "OLEDSupport.stl missing"),
        Case("step: OLEDSupport.step is another part", "G4.step_parts", C.g4_step_parts, noop, step_swapped, "OLEDSupport: STEP volume"),
        Case("step: prose edit in design.json is fine, a real geometry edit is stale", "G4.step_parts", C.g4_step_parts, prose_edit, with_gap(2.0), "OLEDSupport: production STEP"),
        Case("oled: positions.json states the design window, not the cut", "G4.oled_clearance", C.g4_oled_clearance, t(), stale_cut, "oled_window cut"),
        Case("pcb insertion: bosses 1.5 mm inside the corners", "X.pcb_insertion", C.x_pcb_insertion, t(), b(boss_in=1.5), "cannot reach its seat"),
        Case("pcb insertion: the real audited B1 part as the tray", "X.pcb_insertion", C.x_pcb_insertion, t(), old_b1, "cannot reach its seat"),
        Case("pcb insertion: post under the XIAO", "X.pcb_insertion", C.x_pcb_insertion, t(), b(floor_post=True), "XIAO board"),
        Case("pcb insertion: tongue wider than the notch", "X.pcb_insertion", C.x_pcb_insertion, t(), b(usb_w=12.0), "Top below the rim"),
        Case("pcb insertion: notch closed, receptacle stopped", "X.pcb_insertion", C.x_pcb_insertion, noop, real_fault(real, "close_notch"), "USB receptacle"),
        Case("mesh: insert hole 0.5 mm off", "X.cross_positions", C.x_cross_positions, t(), b(hole_move=0.5), "insert hole 0"),
        Case("mesh: insert hole removed from Bottom", "X.cross_positions", C.x_cross_positions, t(), b(no_hole=True), "no insert hole"),
        Case("mesh: USB notch 13.0 < 13.5 mm", "X.cross_positions", C.x_cross_positions, t(), b(usb_w=13.0), "USB notch"),
        Case("mesh: USB notch closed in Bottom", "X.cross_positions", C.x_cross_positions, t(), b(notch=False), "back wall is closed"),
        Case("mesh: screw hole 0.5 mm off in Top", "X.cross_positions", C.x_cross_positions, t(), t(hole_move=0.5), "screw hole 0"),
        Case("mesh: screw hole 2.6 mm in Top", "X.cross_positions", C.x_cross_positions, t(), t(hole_d=2.6), "screw hole 0"),
        Case("mesh: USB tongue gone from Top", "X.cross_positions", C.x_cross_positions, t(), t(tongue=False), "no tongue"),
        Case("real Top: screw hole moved 0.5 mm", "X.cross_positions", C.x_cross_positions, noop, real_fault(real, "move_top_hole"), "screw hole 0"),
        Case("real Bottom: insert hole filled", "X.cross_positions", C.x_cross_positions, noop, real_fault(real, "plug_insert"), "no insert hole"),
        Case("real Bottom: USB notch closed", "X.cross_positions", C.x_cross_positions, noop, real_fault(real, "close_notch"), "back wall is closed"),
        Case("usb: host VID/PID filter removed", "X.usb_ids", C.x_usb_ids, noop, usb_filter_removed, "keychron"),
        Case("usb: keyboard.json PID differs", "X.usb_ids", C.x_usb_ids, noop, fw_pid, "keyboard.json usb"),
        Case("usb: design.json PID differs", "X.usb_ids", C.x_usb_ids, noop, design_pid, "VENDOR_ID/PRODUCT_ID"),
        Case("drc: pad annular 0.19 fails", "G3.drc_jlcpcb", C.g3_drc_jlcpcb, real_gnd_clean, annular_019, "annular_width", True),
        Case("drc: project rules loosened to 0.15, pinned file still gates and 0.20 floor fails", "G3.drc_jlcpcb", C.g3_drc_jlcpcb, real_gnd_clean, project_loosens, "PTH annular ring gates at 0.18", True),
        Case("gnd: one pad set to full", "G3.gnd_thermal", C.g3_gnd_thermal, pcb_clean, gnd_override, "zone_connect 2"),
        Case("gnd: zone set to solid", "G3.gnd_thermal", C.g3_gnd_thermal, pcb_clean, gnd_zone_solid, "must be thermal"),
        Case("gnd: pour floods the pads", "G3.gnd_thermal", C.g3_gnd_thermal, pcb_clean, gnd_flooded_fill, "no working thermal relief"),
        Case("gnd: real U1 pad 13 set to full", "G3.gnd_thermal", C.g3_gnd_thermal, real_gnd_clean, real_gnd_override, "U1 pad 13"),
        Case("firmware: F1 blanking line back in keymap.c", "G6.oled_strip_panel", C.g6_oled_strip_panel, noop, f1_back, "PASS F1 HID: slot strip"),
        Case("firmware: harness fails with F1 back", "G6.firmware_harness", C.g6_firmware_harness, noop, f1_back, "FAIL F1 HID"),
        Case("firmware: bringup keymap draws the wrong screen", "G6.firmware_harness", C.g6_firmware_harness, noop, bringup_broken, "FAIL bringup"),
        Case("firmware: bringup screen missing from the panel lines", "G6.oled_strip_panel", C.g6_oled_strip_panel, noop, bringup_broken, "PASS bringup: start screen"),
        Case("firmware: run.sh exits non-zero with no FAIL line", "G6.firmware_harness", C.g6_firmware_harness, noop, runsh_bad_exit, "harness exited 7"),
        Case("firmware: panel check sees run.sh exit non-zero", "G6.oled_strip_panel", C.g6_oled_strip_panel, noop, runsh_bad_exit, "harness exited 7"),
        Case("firmware: run.sh stops running the bringup program", "G6.firmware_harness", C.g6_firmware_harness, noop, runsh_skips_bringup, "bringup keymap"),
        Case("host: a failing test in host/tests", "G7.host_tests", C.g7_host_tests, noop, host_test_breaks, "pytest exited"),
        Case("BOM: 8 inserts > kit 6", "G5.bom_kit", C.g5_bom_kit, noop, bom_too_many, "design needs 8 inserts"),
        Case("BOM: an LED footprint on the real PCB", "G5.bom_kit", C.g5_bom_kit, real_gnd_clean, pcb_led_back, "LED footprints"),
        Case("package: gerbers.zip and schematic image missing", "G8.package", C.g8_package, pkg_clean, pkg_broken, "gerbers.zip"),
        Case("package: schematic image file missing", "G8.package", C.g8_package, pkg_clean, pkg_broken, "does not resolve: PCB/images/schematic.png"),
        Case("package: bringup.uf2 missing", "G8.package", C.g8_package, pkg_clean, bringup_missing, "bringup.uf2 missing"),
        Case("package: GlowBand.stl left behind", "G8.package", C.g8_package, pkg_clean, stale_glowband, "GlowBand.stl is not a part"),
        Case("package: README loses the hackpad image", "G8.package", C.g8_package, pkg_clean, readme_drop("docs/images/hackpad.png"), "whole hackpad"),
        Case("package: README loses the exploded image", "G8.package", C.g8_package, pkg_clean, readme_drop("docs/images/exploded.png"), "case fit"),
        Case("package: README loses the schematic image", "G8.package", C.g8_package, pkg_clean, readme_drop("PCB/images/schematic.png"), "for the schematic"),
        Case("package: README loses both PCB renders, the badge does not count", "G8.package", C.g8_package, pkg_clean,
             readme_drop("pcb_render_top", "pcb_render_bottom"), "for the PCB"),
        Case("package: README loses the BOM table", "G8.package", C.g8_package, pkg_clean, readme_no_bom_table, "no markdown table"),
        Case("package: BOM.csv missing", "G8.package", C.g8_package, pkg_clean, bom_missing, "BOM.csv missing"),
        Case("package: BOM.csv row with no item", "G8.package", C.g8_package, pkg_clean, bom_blank("item"), "item is empty"),
        Case("package: BOM.csv row with no link", "G8.package", C.g8_package, pkg_clean, bom_blank("link"), "link is empty"),
        Case("package: BOM.csv row with no price", "G8.package", C.g8_package, pkg_clean, bom_blank("price_usd"), "price_usd is empty"),
        Case("package: BOM.csv link is not a URL", "G8.package", C.g8_package, pkg_clean, bom_link_text, "is not a URL"),
        Case("package: BOM.csv price is not a number", "G8.package", C.g8_package, pkg_clean, bom_price_text, "not a number of US dollars"),
        Case("package: BOM.csv has no price_usd column", "G8.package", C.g8_package, pkg_clean, bom_no_column, "no column"),
    ]

    for i, cs in enumerate(cases):
        base = tmp / f"case{i:02d}"
        root = base / "project"
        _copy_project(real, root)
        row = {"case": cs.name, "check": cs.cid}
        try:
            cs.clean(root)
            if cs.kicad and find_kicad_cli() is None:
                raise SkipCase("kicad-cli not installed")
            if cs.fault is None:  # netlist cases: fn carries the fault
                clean = netlist_check("clean")(_ctx(root, base / "clean"))
                faulty = cs.fn(_ctx(root, base / "fault"))
            else:
                clean = cs.fn(_ctx(root, base / "clean", cs.kicad))
                cs.fault(root)
                faulty = cs.fn(_ctx(root, base / "fault", cs.kicad))
            row["clean_status"] = clean.status
            row["clean_reasons"] = clean.failures[:3] or ([clean.not_run_reason] if clean.not_run_reason else [])
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
            row.update(ok=False, why=f"self-test crashed: {type(e).__name__}: {e}",
                       traceback=traceback.format_exc().splitlines()[-8:])
        results.append(row)
        mark = {True: "ok  ", False: "BAD ", None: "skip"}[row["ok"]]
        print(f"{mark} {cs.cid:20} {cs.name:48} clean={row.get('clean_status')} fault={row.get('fault_status')} "
              f"{(row.get('fault_reasons') or [row.get('skipped') or row.get('why') or ''])[0]}")

    # Harness assertions: missing inputs give NOT_RUN, and only FAIL sets the exit code.
    meta = []
    empty = tmp / "empty"
    empty.mkdir()
    (empty / "design.json").write_text((real / "design.json").read_text())
    ectx = _ctx(empty, tmp / "empty-ev")
    for fn, cid in ((C.g3_drc, "G3.drc"), (C.g2_erc, "G2.erc"), (C.g4_stl_mesh, "G4.stl_mesh"),
                    (C.g6_production_uf2, "G6.production_uf2"), (C.g7_host_tests, "G7.host_tests"),
                    (C.x_pcb_insertion, "X.pcb_insertion")):
        st = fn(ectx).status
        meta.append({"assert": f"{cid} on an empty project is NOT_RUN", "got": st, "ok": st == NOT_RUN})
    fake = [{"status": PASS}, {"status": NOT_RUN}]
    meta.append({"assert": "exit code 0 when only PASS/NOT_RUN", "got": exit_code(fake), "ok": exit_code(fake) == 0})
    fake.append({"status": FAIL})
    meta.append({"assert": "exit code 1 when any FAIL", "got": exit_code(fake), "ok": exit_code(fake) == 1})
    rep = tmp / "report.md"
    write_report([], rep, ectx)
    text = rep.read_text()
    for name, _, _ in NEEDS_REAL_PARTS:
        meta.append({"assert": f"REPORT lists '{name}' under Needs real parts", "got": name in text, "ok": name in text})
    meta.append({"assert": "exactly the 3 agreed Needs real parts items", "got": len(NEEDS_REAL_PARTS), "ok": len(NEEDS_REAL_PARTS) == 3})
    pinned = sha256(verify / C.JLC_DRU.split("verify/")[1]) == C.JLC_DRU_SHA256
    meta.append({"assert": "pinned JLCPCB rules file matches its SHA-256", "got": pinned, "ok": pinned})
    for m in meta:
        print(f"{'ok  ' if m['ok'] else 'BAD '} meta: {m['assert']} (got {m['got']})")

    bad = [r for r in results if r["ok"] is False] + [m for m in meta if not m["ok"]]
    summary = {"timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
               "status": "PASS" if not bad else "FAIL", "cases": results, "meta": meta,
               "skipped": [r["case"] for r in results if r["ok"] is None]}
    (verify / "selftest.json").write_text(scrub(json.dumps(summary, indent=2)) + "\n")
    n_ok = sum(1 for r in results if r["ok"])
    print(f"self-test {summary['status']}: {n_ok}/{len(results)} fault cases caught, "
          f"{len(summary['skipped'])} skipped, {sum(m['ok'] for m in meta)}/{len(meta)} harness assertions; wrote verify/selftest.json")
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if not bad else 1
