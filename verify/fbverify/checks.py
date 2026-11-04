"""All checks. Each function takes a Ctx, returns a finished Check (written by the caller).

Rules: a status comes only from a tool exit code or a value parsed out of a file and compared
with a number from design.json. Missing input or tool -> NOT_RUN, never PASS."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import time
from pathlib import Path

from . import geom, sexpr
from .core import Check, Ctx, sha256

# Seeed XIAO RP2040 pinout (Seeed wiki "XIAO RP2040 pin multiplexing", schematic v1.0).
XIAO_RP2040_GPIO = {"D0": "GP26", "D1": "GP27", "D2": "GP28", "D3": "GP29", "D4": "GP6", "D5": "GP7",
                    "D6": "GP0", "D7": "GP1", "D8": "GP2", "D9": "GP4", "D10": "GP3"}
# XIAO castellated pad numbering: 1..7 = D0..D6 down the left, 8..11 = D7..D10, 12 3V3, 13 GND, 14 5V.
XIAO_PADNUM = {**{str(i + 1): f"D{i}" for i in range(7)}, "8": "D7", "9": "D8", "10": "D9", "11": "D10",
               "12": "3V3", "13": "GND", "14": "5V"}
# Hackpad kit (task brief + docs/VERIFICATION.md "Kit max" row; XIAO from the same rules table).
KIT = {"switches": 16, "keycaps": 16, "diodes": 20, "encoders": 2, "oled": 1, "leds": 16,
       "screws": 6, "inserts": 6, "mcu_xiao_rp2040": 1}
JLC_DRU = "verify/rules/JLCPCB-2L-1oz.kicad_dru"
JLC_DRU_SHA256 = "292b812a764c76785446b9de5e00c9e76bc58bd4019071f1f99294e81f3874d2"
JLC_PTH_ANNULAR_MIN = 0.20   # jlcpcb.com/capabilities/pcb-capabilities; the pinned third-party file says 0.18
PARTS = ("Top", "Bottom", "GlowBand", "Knob", "OLEDSupport")
POS_TOL = 0.05
OUTLINE_TOL = 0.1
CUTOUT = 14.0
CUTOUT_TOL = 0.1
CAD_POS_TOL = 0.1
# Real part dimensions (docs/DIMENSIONS.md, Alps EC11E drawing; audited in docs/audit/case.md).
# h = depth below the plate top. Plate top is 5.0 above PCB top: that is the MX switch itself.
MX_PLATE_TO_PCB = 5.0
PCB_T = 1.6
SWITCH_W = 14.0
CLIP_PLATE, CLIP_PLATE_TOL = 1.5, 0.15
EC11_BODY_W = 12.0          # Alps 11.7 x 12.0; square so the check holds for either footprint rotation
EC11_BODY_H = 4.5
EC11_BUSH_D = 7.0
EC11_CLEAR = 0.2            # printed part to real part (docs/VERIFICATION.md fits)
OLED_BOARD_T, OLED_GLASS_T = 1.2, 1.45     # docs/DIMENSIONS.md; the stack height is design.json case.oled_support.module_gap
OLED_ACTIVE = (22.384, 5.584)               # panel datasheets, docs/DIMENSIONS.md oledActive
# Where the active area sits on the glass isn't documented: centred, up to 3.5 toward the header (audit N10: 2.5 +/-1), +/-1.5 in y
OLED_ACTIVE_DX, OLED_ACTIVE_DY = (0.0, 3.5), 1.5
OLED_YAW, OLED_SHIFT = 1.0, 0.1             # soldered to J1 before the Top: pin play about the header, CAD/README.md
SHELL_TOL = 0.2
INSERT_HOLE, INSERT_HOLE_TOL = 4.7, 0.1
USB_WALL_Y = (-0.5, -3.5, -6.5)
SWEEP_LIMIT = 0.01          # mm3 of material inside the PCB envelope, over the whole path
KB_DIR = "Firmware/qmk/keyboards/frostbite"


# ---------------------------------------------------------------- shared loaders

def design(chk: Check):
    p = chk.ctx.p("design.json")
    if not p.is_file():
        chk.not_run("design.json missing")
        return None
    try:
        return json.loads(chk.read(p))
    except json.JSONDecodeError as e:
        chk.fail(f"design.json is not valid JSON: {e}")
        return None


def net_of(d, name):
    for p in d["pins"]:
        if p["net"] == name:
            return p
    return None


def norm_net(n):
    if n is None:
        return None
    n = str(n)
    n = n.split("/")[-1] if n.startswith("/") else n
    return n.lstrip("+").upper()


def is_net(n, *names):
    nn = norm_net(n)
    return nn is not None and nn in {x.lstrip("+").upper() for x in names}


POWER_ALIASES = {"5V": ("5V", "VBUS", "+5V"), "3V3": ("3V3", "+3V3", "3.3V", "+3.3V", "VCC3V3"), "GND": ("GND", "GNDD")}


def find_one(root: Path, pattern: str, exclude=(".venv", "node_modules", "-backups", ".build")):
    out = []
    if not root.exists():
        return out
    for p in sorted(root.rglob(pattern)):
        if any(x in str(p) for x in exclude) or not p.is_file():
            continue
        if p.name.startswith("_autosave") or p.name.startswith("~"):
            continue
        out.append(p)
    return out


def kicad_files(ctx: Ctx):
    pcb_dir = ctx.p("PCB")
    pros = find_one(pcb_dir, "*.kicad_pro")
    pcbs = find_one(pcb_dir, "*.kicad_pcb")
    schs = find_one(pcb_dir, "*.kicad_sch")
    stem = pros[0].stem if pros else None
    pick = lambda lst: next((p for p in lst if p.stem == stem), lst[0] if lst else None)  # noqa: E731
    return {"pro": pros[0] if pros else None, "pcb": pick(pcbs), "sch": pick(schs)}


def need_kicad(chk: Check) -> bool:
    if chk.ctx.kicad_cli is None:
        chk.not_run("kicad-cli not installed (looked in ~/Applications/KiCad/KiCad.app/Contents/MacOS)")
        return False
    return True


def keyboard_json(chk: Check):
    p = chk.ctx.p(KB_DIR) / "keyboard.json"
    if not p.is_file():
        alts = find_one(chk.ctx.p("Firmware"), "keyboard.json")
        p = alts[0] if alts else None
    if p is None:
        chk.not_run("Firmware keyboard.json missing")
        return None, None
    try:
        return json.loads(chk.read(p)), p
    except json.JSONDecodeError as e:
        chk.fail(f"{p.name} is not valid JSON: {e}")
        return None, p


def c_defines(text: str) -> dict:
    out = {}
    for m in re.finditer(r"^\s*#\s*define\s+(\w+)(?:[ \t]+([^\n]*?))?\s*(?://.*|/\*.*)?$", text, re.M):
        out[m.group(1)] = (m.group(2) or "").strip()
    return out


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


# ================================================================ G0

def _studio_copy(ctx: Ctx, chk: Check):
    src = ctx.p("studio")
    if not src.is_dir():
        return None
    dst = ctx.work / "studio_copy"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("node_modules", "img"))
    for f in sorted(src.rglob("*.js")):
        chk.hash(f)
    return dst


def g0_studio_run(ctx: Ctx) -> Check:
    chk = Check(ctx, "G0.studio_run", "G0", "Studio harness: node studio/verify/run.js (run on a copy so studio/ is not written)")
    if not (ctx.p("studio/verify/run.js")).is_file():
        return chk.not_run("studio/verify/run.js missing")
    if not shutil.which("node", path=ctx.env["PATH"]):
        return chk.not_run("node not on PATH")
    dst = _studio_copy(ctx, chk)
    code, out, err = chk.run(["node", "verify/run.js"], cwd=dst, timeout=300)
    rep = dst / "verify/report.md"
    if rep.is_file():
        txt = rep.read_text()
        chk.details["report_md_sha256"] = sha256(rep)
        chk.details["report_md_head"] = txt.splitlines()[:40]
    if code != 0:
        chk.fail(f"node verify/run.js exited {code}")
    return chk


def g0_studio_constraints(ctx: Ctx) -> Check:
    chk = Check(ctx, "G0.studio_constraints", "G0", "Studio unit tests: node studio/test/constraints.test.js")
    if not ctx.p("studio/test/constraints.test.js").is_file():
        return chk.not_run("studio/test/constraints.test.js missing")
    dst = _studio_copy(ctx, chk)
    code, out, err = chk.run(["node", "test/constraints.test.js"], cwd=dst, timeout=300)
    if code != 0:
        chk.fail(f"node test/constraints.test.js exited {code}")
    return chk


def g0_design_json(ctx: Ctx) -> Check:
    chk = Check(ctx, "G0.design_json", "G0", "design.json internal consistency (pins, matrix, LED indices, PCB size)")
    d = design(chk)
    if d is None:
        return chk
    try:
        import jsonschema
        schema = {
            "type": "object",
            "required": ["pins", "matrix", "pcb", "keys", "leds", "encoder", "oled", "case", "mcu", "firmware"],
            "properties": {
                "pins": {"type": "array", "items": {"type": "object", "required": ["xiao", "gpio", "net"]}},
                "keys": {"type": "array", "items": {"type": "object", "required": ["ref", "row", "col", "x", "y", "led"]}},
                "pcb": {"type": "object", "required": ["w", "h", "layers"]},
                "matrix": {"type": "object", "required": ["rows", "cols", "diode_direction"]},
                "leds": {"type": "object", "required": ["count", "glow"]},
            }}
        errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(d), key=lambda e: list(e.path))
        for e in errs:
            chk.fail(f"schema: {'/'.join(map(str, e.path))}: {e.message}")
        if errs:
            return chk
    except ImportError:
        chk.note("jsonschema not installed; schema step skipped")
    pins = d["pins"]
    for k in ("xiao", "gpio", "net"):
        vals = [p[k] for p in pins]
        dup = {v for v in vals if vals.count(v) > 1}
        if dup:
            chk.fail(f"pins: duplicate {k} {sorted(dup)}")
    if len(pins) > 11:
        chk.fail(f"pins: {len(pins)} used > 11 XIAO GPIO")
    for p in pins:
        ref = XIAO_RP2040_GPIO.get(p["xiao"])
        if ref != p["gpio"]:
            chk.fail(f"pins: {p['xiao']} is {ref} on the XIAO RP2040, design.json says {p['gpio']}")
    m = d["matrix"]
    need = [f"ROW{i}" for i in range(m["rows"])] + [f"COL{i}" for i in range(m["cols"])] + \
        ["SDA", "SCL", "LED_DIN", "ENC_A", "ENC_B"]
    for n in need:
        if net_of(d, n) is None:
            chk.fail(f"pins: net {n} not assigned to any XIAO pin")
    keys = d["keys"]
    if len(keys) != m["rows"] * m["cols"]:
        chk.fail(f"keys: {len(keys)} keys but matrix is {m['rows']}x{m['cols']}")
    rc = [(k["row"], k["col"]) for k in keys]
    if len(set(rc)) != len(rc):
        chk.fail("keys: duplicate (row, col)")
    for k in keys:
        if not (0 <= k["row"] < m["rows"] and 0 <= k["col"] < m["cols"]):
            chk.fail(f"keys: {k['ref']} row/col outside matrix")
        if not (0 < k["x"] < d["pcb"]["w"] and 0 < k["y"] < d["pcb"]["h"]):
            chk.fail(f"keys: {k['ref']} centre outside the PCB")
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            dist = math.dist((keys[a]["x"], keys[a]["y"]), (keys[b]["x"], keys[b]["y"]))
            if dist < 19.0:
                chk.fail(f"keys: {keys[a]['ref']}-{keys[b]['ref']} {dist:.3f} mm apart < 19.0 (MX pitch 19.05)")
    leds = [k["led"] for k in keys] + [g["led"] for g in d["leds"]["glow"]]
    if sorted(leds) != list(range(d["leds"]["count"])):
        chk.fail(f"leds: indices {sorted(leds)} are not exactly 0..{d['leds']['count'] - 1}")
    if d["pcb"]["w"] > 100 or d["pcb"]["h"] > 100:
        chk.fail(f"pcb: {d['pcb']['w']} x {d['pcb']['h']} exceeds 100 x 100")
    if d["pcb"]["layers"] != 2:
        chk.fail(f"pcb: layers {d['pcb']['layers']} != 2")
    if d["firmware"]["raw_hid"]["report_bytes"] != 32:
        chk.fail("firmware.raw_hid.report_bytes != 32")
    inputs_count = len(keys) + 1  # + encoder
    if len(keys) > 16:  # kit limit; the old "< 16 inputs" rule is not on the live Hackpad pages (docs/audit/hackpad-rules.md)
        chk.fail(f"{len(keys)} switches > 16 in the kit")
    chk.details = {"pins": len(pins), "keys": len(keys), "leds": d["leds"]["count"], "inputs": inputs_count}
    return chk


# ================================================================ G2

def _keymap_layer0_count(text: str):
    text = re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)
    m = re.search(r"\[\s*0\s*\]\s*=\s*LAYOUT\w*\s*\(", text)
    if not m:
        k = text.find("keymaps")
        m = re.compile(r"\bLAYOUT\w*\s*\(").search(text, max(k, 0))
    if not m:
        return None
    i, depth, args, cur = m.end(), 1, [], ""
    while i < len(text) and depth:
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if depth == 0:
            break
        if ch == "," and depth == 1:
            args.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    args.append(cur)
    args = [a.strip() for a in args]
    return len([a for a in args if a])


def g2_firmware_pins(ctx: Ctx) -> Check:
    chk = Check(ctx, "G2.firmware_pins", "G2", "Firmware keyboard.json / config.h pins vs design.json")
    d = design(chk)
    kb, kbp = keyboard_json(chk)
    if d is None or kb is None:
        return chk
    G = lambda n: net_of(d, n)["gpio"] if net_of(d, n) else None  # noqa: E731
    m = d["matrix"]
    exp_rows = [G(f"ROW{i}") for i in range(m["rows"])]
    exp_cols = [G(f"COL{i}") for i in range(m["cols"])]
    mp = kb.get("matrix_pins", {})
    rows, cols = mp.get("rows"), mp.get("cols")
    if rows != exp_rows:
        chk.fail(f"matrix_pins.rows {rows} != design {exp_rows}")
    if cols != exp_cols:
        chk.fail(f"matrix_pins.cols {cols} != design {exp_cols}")
    if kb.get("diode_direction") != m["diode_direction"]:
        chk.fail(f"diode_direction {kb.get('diode_direction')!r} != design {m['diode_direction']!r}")
    enc = (kb.get("encoder") or {}).get("rotary") or []
    if len(enc) != 1:
        chk.fail(f"encoder.rotary has {len(enc)} entries, design has 1 encoder")
    else:
        if enc[0].get("pin_a") != G("ENC_A") or enc[0].get("pin_b") != G("ENC_B"):
            chk.fail(f"encoder pins A/B {enc[0].get('pin_a')}/{enc[0].get('pin_b')} != design {G('ENC_A')}/{G('ENC_B')}")
    ws = kb.get("ws2812") or {}
    if ws.get("pin") != G("LED_DIN"):
        chk.fail(f"ws2812.pin {ws.get('pin')} != design LED_DIN {G('LED_DIN')}")
    if ws.get("driver") != "vendor":
        chk.fail(f"ws2812.driver {ws.get('driver')!r} != 'vendor' (RP2040 PIO, design.json pins note)")
    # LED count
    rgbm = kb.get("rgb_matrix") or {}
    layout = rgbm.get("layout")
    led_count = len(layout) if layout is not None else (kb.get("rgblight") or {}).get("led_count")
    if led_count != d["leds"]["count"]:
        chk.fail(f"LED count {led_count} != design {d['leds']['count']}")
    if layout:
        by_led = {k["led"]: k for k in d["keys"]}
        for i, e in enumerate(layout):
            k = by_led.get(i)
            mtx = e.get("matrix")
            if k is not None and mtx != [k["row"], k["col"]]:
                chk.fail(f"rgb_matrix.layout[{i}].matrix {mtx} != design {k['ref']} [{k['row']}, {k['col']}] (led {i})")
            if k is None and mtx is not None:
                chk.fail(f"rgb_matrix.layout[{i}] has matrix {mtx} but design led {i} is a glow LED")
    # layout / matrix size
    lays = kb.get("layouts") or {}
    if len(lays) != 1:
        chk.fail(f"{len(lays)} layouts defined, expected 1")
    for name, L in lays.items():
        ents = L.get("layout", [])
        if len(ents) != len(d["keys"]):
            chk.fail(f"layout {name}: {len(ents)} keys != design {len(d['keys'])}")
        got = sorted(tuple(e.get("matrix", [])) for e in ents)
        want = sorted((k["row"], k["col"]) for k in d["keys"])
        if got != want:
            chk.fail(f"layout {name}: matrix positions {got} != design {want}")
        for e, k in zip(ents, d["keys"]):
            if tuple(e.get("matrix", [])) != (k["row"], k["col"]):
                chk.fail(f"layout {name}: entry order differs from design keys[] at {k['ref']} (protocol key index)")
                break
    # config.h: I2C + OLED + raw HID
    cfg = ctx.p(KB_DIR) / "config.h"
    if not cfg.is_file():
        chk.fail("config.h missing (I2C pins cannot be checked)")
    else:
        df = c_defines(chk.read(cfg))
        sda, scl = df.get("I2C1_SDA_PIN"), df.get("I2C1_SCL_PIN")
        if sda != G("SDA") or scl != G("SCL"):
            chk.fail(f"config.h I2C1_SDA_PIN/I2C1_SCL_PIN {sda}/{scl} != design {G('SDA')}/{G('SCL')}")
        if sda and re.fullmatch(r"GP\d+", sda):
            unit = (int(sda[2:]) // 2) % 2
            if df.get("I2C_DRIVER") != f"I2CD{unit}":
                chk.fail(f"I2C_DRIVER {df.get('I2C_DRIVER')} but {sda} is on RP2040 I2C{unit}")
        if "OLED_DISPLAY_128X32" not in df:
            chk.fail("OLED_DISPLAY_128X32 not defined in config.h")
        addr = df.get("OLED_DISPLAY_ADDRESS")
        if addr is not None and int(addr, 0) != int(d["oled"]["address"], 0):
            chk.fail(f"OLED_DISPLAY_ADDRESS {addr} != design {d['oled']['address']}")
        rh = d["firmware"]["raw_hid"]
        for key, want, default in (("RAW_USAGE_PAGE", rh["usage_page"], "0xFF60"), ("RAW_USAGE_ID", rh["usage"], "0x61")):
            have = df.get(key, default)
            if int(have, 0) != int(want, 0):
                chk.fail(f"{key} {have} != design {want}")
    if not (kb.get("features") or {}).get("raw"):
        chk.fail("features.raw is not true (Raw HID protocol needs RAW_ENABLE)")
    # keymaps: layer 0 count
    for km in ("default", "ledtest"):
        kp = ctx.p(KB_DIR) / "keymaps" / km / "keymap.c"
        if not kp.is_file():
            chk.fail(f"keymaps/{km}/keymap.c missing")
            continue
        n = _keymap_layer0_count(chk.read(kp))
        if n is not None and n != len(d["keys"]):
            chk.fail(f"keymaps/{km}: layer 0 LAYOUT has {n} keys != {len(d['keys'])}")
        if n is None:
            chk.note(f"keymaps/{km}: no LAYOUT(...) call found")
    chk.details = {"expected": {"rows": exp_rows, "cols": exp_cols, "enc": [G("ENC_A"), G("ENC_B")],
                                "ws2812": G("LED_DIN"), "sda_scl": [G("SDA"), G("SCL")]},
                   "found": {"rows": rows, "cols": cols, "enc": enc, "ws2812": ws, "led_count": led_count}}
    return chk


def _pin_role(node, comp_kind):
    """Map a netlist node to a role name, by pinfunction first, then by a documented pin number table."""
    pf = (node.get("pinfunction") or "").upper()
    pin = node["pin"]
    if comp_kind == "xiao":
        m = re.search(r"(?:^|[^A-Z0-9])D(\d{1,2})(?:$|[^0-9])", "/" + pf + "/")
        if m:
            return f"D{int(m.group(1))}"
        for k in ("5V", "VBUS", "3V3", "GND"):
            if k in pf.replace(".", "").replace("+", ""):
                return {"VBUS": "5V"}.get(k, k)
        return XIAO_PADNUM.get(pin)
    if comp_kind == "led":
        for k in ("DIN", "DOUT", "VDD", "GND", "VSS"):
            if k in pf:
                return {"VSS": "GND"}.get(k, k)
        return {"1": "VDD", "2": "DOUT", "3": "GND", "4": "DIN"}.get(pin)  # SK6812 MINI-E datasheet
    if comp_kind == "diode":
        if pf in ("K", "A"):
            return pf
        return {"1": "K", "2": "A"}.get(pin)  # KiCad Device:D convention
    if comp_kind == "enc":
        for k in ("A", "B", "C", "S1", "S2"):
            if pf == k:
                return k
        return {"A": "A", "B": "B", "C": "C", "S1": "S1", "S2": "S2"}.get(pin.upper())
    return pf or pin


def classify(comp):
    s = " ".join([comp.get("value", ""), comp.get("footprint", ""), comp.get("lib", ""), comp.get("lib_id", "")]).upper()
    ref = comp["ref"].upper()
    if "XIAO" in s:
        return "xiao"
    if re.search(r"SK6812|WS2812|NEOPIXEL", s):
        return "led"
    if re.search(r"ROTARY|EC11|ENCODER", s):
        return "enc"
    if re.search(r"OLED|SSD1306", s) or ref.startswith("OLED"):
        return "oled"
    if re.search(r"MOUNTINGHOLE|MOUNTING_HOLE", s) or ref.startswith("H"):
        return "hole"
    if ref.startswith("SW") and not re.search(r"ROTARY|EC11", s):
        return "switch"
    if ref.startswith("D") and re.search(r"1N4148|DO-35|DO35|SOD|DIODE|D_", s):
        return "diode"
    return "other"


def g2_netlist(ctx: Ctx) -> Check:
    chk = Check(ctx, "G2.netlist", "G2", "Schematic netlist vs design.json (XIAO nets, matrix, OLED order, LED chain, power)")
    d = design(chk)
    kf = kicad_files(ctx)
    if d is None:
        return chk
    if kf["sch"] is None:
        return chk.not_run("no PCB/*.kicad_sch")
    if not need_kicad(chk):
        return chk
    chk.hash(kf["sch"])
    for s in find_one(ctx.p("PCB"), "*.kicad_sch"):
        chk.hash(s)
    out = ctx.work / "netlist.net"
    code, so, se = chk.run([ctx.kicad_cli, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out, kf["sch"]])
    if code != 0 or not out.is_file():
        chk.fail(f"kicad-cli sch export netlist exited {code}")
        return chk
    chk.details["netlist_sha256"] = sha256(out)
    nl = sexpr.load_netlist(out.read_text())
    check_netlist(chk, d, nl)
    return chk


def check_netlist(chk: Check, d: dict, nl: dict):
    comps, nets = nl["components"], nl["nets"]
    kinds = {r: classify(c) for r, c in comps.items()}
    pin_net = {}  # (ref, role) -> net
    for name, nodes in nets.items():
        for nd in nodes:
            role = _pin_role(nd, kinds.get(nd["ref"], "other"))
            pin_net[(nd["ref"], role)] = name
            pin_net[(nd["ref"], "#" + nd["pin"])] = name
    xiaos = [r for r, k in kinds.items() if k == "xiao"]
    if len(xiaos) != 1:
        chk.fail(f"expected 1 XIAO component, found {xiaos}")
        return
    X = xiaos[0]
    for p in d["pins"]:
        got = pin_net.get((X, p["xiao"]))
        if not is_net(got, p["net"]):
            chk.fail(f"XIAO {p['xiao']} net {got!r} != design {p['net']!r}")
    for rail in ("5V", "3V3", "GND"):
        got = pin_net.get((X, rail))
        if got is None or not is_net(got, *POWER_ALIASES[rail]):
            chk.fail(f"XIAO {rail} pin net {got!r} is not a {rail} net")
    netname = {r: pin_net.get((X, r)) for r in ("5V", "3V3", "GND")}
    # matrix: COLc -[SW]- n -[D A->K]- ROWr  (or diode first)
    by_ref = {k["ref"]: k for k in d["keys"]}
    diodes = [r for r, k in kinds.items() if k == "diode"]
    for ref, k in by_ref.items():
        if ref not in comps:
            chk.fail(f"switch {ref} missing from schematic")
            continue
        sw_nets = sorted({v for (r, role), v in pin_net.items() if r == ref and role.startswith("#")})
        col, row = f"COL{k['col']}", f"ROW{k['row']}"
        ok = False
        for D in diodes:
            a, kk = pin_net.get((D, "A")), pin_net.get((D, "K"))
            if a is None or kk is None:
                continue
            if is_net(kk, row) and a in sw_nets and any(is_net(n, col) for n in sw_nets) \
                    and len(nets.get(a, [])) == 2:
                ok = True
            if is_net(a, col) and kk in sw_nets and any(is_net(n, row) for n in sw_nets) \
                    and len(nets.get(kk, [])) == 2:
                ok = True
            if ok:
                break
        if not ok:
            chk.fail(f"{ref}: no {col} -> switch -> diode(A->K) -> {row} path (COL2ROW) found; switch nets {sw_nets}")
    # OLED header order
    oleds = [r for r, k in kinds.items() if k == "oled"]
    if len(oleds) != 1:
        chk.fail(f"expected 1 OLED component/header, found {oleds}")
    else:
        O = oleds[0]
        want = d["oled"]["header"]["pins_top_to_bottom"]
        alias = {"GND": POWER_ALIASES["GND"], "VCC": POWER_ALIASES["3V3"], "SCL": ("SCL",), "SDA": ("SDA",)}
        for i, role in enumerate(want, start=1):
            got = pin_net.get((O, f"#{i}"))
            if not is_net(got, *alias[role]):
                chk.fail(f"OLED {O} pin {i} net {got!r}, expected {role} ({'/'.join(alias[role])})")
    # LEDs
    leds = [r for r, k in kinds.items() if k == "led"]
    if len(leds) != d["leds"]["count"]:
        chk.fail(f"{len(leds)} SK6812 LEDs in schematic != design {d['leds']['count']}")
    for L in leds:
        if pin_net.get((L, "VDD")) != netname["5V"] or netname["5V"] is None:
            chk.fail(f"{L} VDD on {pin_net.get((L, 'VDD'))!r}, not the XIAO 5V net {netname['5V']!r}")
        if pin_net.get((L, "GND")) != netname["GND"]:
            chk.fail(f"{L} GND on {pin_net.get((L, 'GND'))!r}")
    chain, cur, seen = [], pin_net.get((X, "D6")), set()
    din_of = {pin_net.get((L, "DIN")): L for L in leds}
    while cur in din_of and din_of[cur] not in seen:
        L = din_of[cur]
        chain.append(L)
        seen.add(L)
        cur = pin_net.get((L, "DOUT"))
    chk.details["led_chain"] = chain
    if len(chain) != d["leds"]["count"]:
        chk.fail(f"LED chain from XIAO D6 (LED_DIN) reaches {len(chain)} LEDs ({chain}), design needs {d['leds']['count']}")
    # encoder
    encs = [r for r, k in kinds.items() if k == "enc"]
    if len(encs) != 1:
        chk.fail(f"expected 1 encoder, found {encs}")
    else:
        E = encs[0]
        if not is_net(pin_net.get((E, "A")), "ENC_A") or not is_net(pin_net.get((E, "B")), "ENC_B"):
            chk.fail(f"encoder {E} A/B on {pin_net.get((E, 'A'))!r}/{pin_net.get((E, 'B'))!r}, expected ENC_A/ENC_B")
        if pin_net.get((E, "C")) != netname["GND"]:
            chk.fail(f"encoder {E} C on {pin_net.get((E, 'C'))!r}, expected GND")
        gp = {pin_net.get((X, p["xiao"])) for p in d["pins"]}
        for s in ("S1", "S2"):
            if pin_net.get((E, s)) in gp - {None}:
                chk.fail(f"encoder {E} {s} wired to a GPIO net, design says push not wired")
    chk.details["components"] = {k: sorted(r for r in kinds if kinds[r] == k) for k in set(kinds.values())}


def g2_erc(ctx: Ctx) -> Check:
    chk = Check(ctx, "G2.erc", "G2", "kicad-cli sch erc --severity-error --exit-code-violations")
    kf = kicad_files(ctx)
    if kf["sch"] is None:
        return chk.not_run("no PCB/*.kicad_sch")
    if not need_kicad(chk):
        return chk
    for s in find_one(ctx.p("PCB"), "*.kicad_sch"):
        chk.hash(s)
    out = ctx.work / "erc.json"
    code, so, se = chk.run([ctx.kicad_cli, "sch", "erc", "--format", "json", "--severity-error",
                            "--exit-code-violations", "-o", out, kf["sch"]])
    viol = []
    if out.is_file():
        rep = json.loads(out.read_text())
        for sh in rep.get("sheets", []):
            viol += [f"{v.get('type')}: {v.get('description')}" for v in sh.get("violations", [])]
    chk.details["violations"] = viol[:50]
    if code != 0 or viol:
        chk.fail(f"ERC exit {code}, {len(viol)} error violations" + (f"; first: {viol[0]}" if viol else ""))
    return chk


# ================================================================ G3

def _pcb(chk: Check):
    kf = kicad_files(chk.ctx)
    if kf["pcb"] is None:
        chk.not_run("no PCB/*.kicad_pcb")
        return None, None
    key = ("pcb", str(kf["pcb"]))
    if key not in chk.ctx.cache:
        chk.ctx.cache[key] = sexpr.load_pcb(kf["pcb"].read_text())
    chk.hash(kf["pcb"])
    return chk.ctx.cache[key], kf["pcb"]


def _rule_blocks(text: str) -> list[tuple[str, str]]:
    """[(name, block text)] for each (rule "name" ...) in a .kicad_dru. Comment lines are dropped."""
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    out, i = [], 0
    while True:
        m = re.compile(r'\(rule\s+"([^"]*)"').search(text, i)
        if not m:
            return out
        depth, j, quoted = 0, m.start(), False
        while j < len(text):
            ch = text[j]
            if ch == '"':
                quoted = not quoted
            elif not quoted and ch == "(":
                depth += 1
            elif not quoted and ch == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append((m.group(1), text[m.start():j + 1]))
        i = j + 1


CONSTRAINT_RE = re.compile(r"\(constraint\s+(\w+)((?:\s*\((?:min|opt|max)\s+[\d.]+mm\))+)\s*\)")
BOUND_RE = re.compile(r"\((min|opt|max)\s+([\d.]+)mm\)")


def _condition(block: str):
    m = re.search(r'\(condition\s+"((?:[^"\\]|\\.)*)"\)', block)
    return m.group(1) if m else None


def strictest_rules(pinned: str, project: str) -> tuple[str, list[dict]]:
    """One rule set in which the stricter of the two files gates, whatever their order.

    KiCad lets a later rule override an earlier one, so concatenating the files lets the last
    one loosen the other. Rules with the same name and condition are merged bound by bound."""
    own = {(n, _condition(b)): b for n, b in _rule_blocks(project)}
    used, blocks, tightened = set(), [], []
    for name, block in _rule_blocks(pinned):
        key = (name, _condition(block))
        other = own.get(key)
        if other is not None:
            used.add(key)
            theirs = {}
            for c, body in CONSTRAINT_RE.findall(other):
                theirs[c] = {b: float(v) for b, v in BOUND_RE.findall(body)}

            def merge(m, name=name, theirs=theirs):
                c, body = m.group(1), m.group(2)
                vals = {b: float(v) for b, v in BOUND_RE.findall(body)}
                for bound, val in vals.items():
                    t = theirs.get(c, {}).get(bound)
                    if t is None or t == val or bound == "opt":
                        continue
                    gate = max(val, t) if bound == "min" else min(val, t)
                    if gate != val:
                        tightened.append({"rule": name, "constraint": c, "bound": bound, "pinned": val, "project": t, "gates": gate})
                    vals[bound] = gate
                return f"(constraint {c} " + " ".join(f"({b} {v:g}mm)" for b, v in vals.items()) + ")"
            block = CONSTRAINT_RE.sub(merge, block)
        blocks.append(block)
    blocks += [b for k, b in own.items() if k not in used]
    return "(version 1)\n\n" + "\n\n".join(blocks) + "\n", tightened


def rule_value(text: str, rule: str, constraint: str, bound: str):
    for name, block in _rule_blocks(text):
        if name == rule:
            for c, body in CONSTRAINT_RE.findall(block):
                if c == constraint:
                    for b, v in BOUND_RE.findall(body):
                        if b == bound:
                            return float(v)
    return None


def _drc(ctx: Ctx, cid: str, title: str, jlc: bool) -> Check:
    chk = Check(ctx, cid, "G3", title)
    kf = kicad_files(ctx)
    if kf["pcb"] is None:
        return chk.not_run("no PCB/*.kicad_pcb")
    if not need_kicad(chk):
        return chk
    dst = ctx.work / ("drc_jlc" if jlc else "drc")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(ctx.p("PCB"), dst, ignore=shutil.ignore_patterns("*-backups", "*.lck"))
    for f in find_one(ctx.p("PCB"), "*.kicad_*"):
        chk.hash(f)
    board = dst / kf["pcb"].relative_to(ctx.p("PCB"))
    if jlc:
        dru = ctx.p(JLC_DRU) if ctx.p(JLC_DRU).is_file() else Path(__file__).resolve().parents[2] / JLC_DRU
        if not dru.is_file():
            return chk.not_run(f"{JLC_DRU} missing")
        chk.hash(dru)
        got = sha256(dru)
        if got != JLC_DRU_SHA256:
            chk.fail(f"{JLC_DRU} SHA-256 {got} != pinned {JLC_DRU_SHA256}")
            return chk
        target = board.with_suffix(".kicad_dru")
        own = target.read_text() if target.is_file() else ""
        rules, tightened = strictest_rules(dru.read_text(), own)
        chk.details["rules_tightened"] = tightened
        for t in tightened:
            chk.note(f"{t['rule']}: {t['constraint']} {t['bound']} is {t['gates']} (pinned {t['pinned']}, project {t['project']})")
        pth = rule_value(rules, "JLCPCB: PTH Annular Ring", "annular_width", "min")
        chk.details["pth_annular_gates_at_mm"] = pth
        if pth is None or pth < JLC_PTH_ANNULAR_MIN:
            chk.fail(f"PTH annular ring gates at {pth} mm, JLCPCB's published minimum is {JLC_PTH_ANNULAR_MIN}")
        target.write_text(rules)
    out = dst / "drc.json"
    code, so, se = chk.run([ctx.kicad_cli, "pcb", "drc", "--format", "json", "--severity-error",
                            "--exit-code-violations", "--schematic-parity", "-o", out, board], timeout=600)
    counts = {}
    if out.is_file():
        rep = json.loads(out.read_text())
        for k in ("violations", "unconnected_items", "schematic_parity"):
            items = rep.get(k, [])
            counts[k] = len(items)
            chk.details[k] = [f"{v.get('type')}: {v.get('description')}" for v in items[:30]]
    chk.details["counts"] = counts
    if code != 0 or any(counts.values()):
        kinds = sorted({v.split(":")[0] for v in chk.details.get("violations", [])})
        chk.fail(f"DRC exit {code}, counts {counts}, violation types {kinds}" +
                 (f"; first: {chk.details.get('violations', [''])[0]}" if chk.details.get("violations") else ""))
    return chk


def g3_drc(ctx):
    return _drc(ctx, "G3.drc", "kicad-cli pcb drc (project rules) --schematic-parity", False)


def g3_drc_jlcpcb(ctx):
    return _drc(ctx, "G3.drc_jlcpcb", "kicad-cli pcb drc: pinned JLCPCB 2-layer rules, tightened by the project rules where those are stricter", True)


def pcb_origin(pcb):
    if not pcb["edge_pts"]:
        return None
    x0, y0, x1, y1 = bbox(pcb["edge_pts"])
    return {"x0": x0, "y0": y0, "w": x1 - x0, "h": y1 - y0}


def fp_by(pcb, kind):
    out = []
    for f in pcb["footprints"]:
        c = {"ref": f["ref"] or "", "value": f["value"] or "", "footprint": f["lib"], "lib": f["lib"]}
        if classify(c) == kind:
            out.append(f)
    return out


def g3_outline_layers(ctx: Ctx) -> Check:
    chk = Check(ctx, "G3.outline_layers", "G3", "Board outline vs design.json, copper layer count, silkscreen text")
    d = design(chk)
    pcb, path = _pcb(chk)
    if d is None or pcb is None:
        return chk
    cu = [l["name"] for l in pcb["layers"] if re.fullmatch(r"(F|B|In\d+)\.Cu", l["name"])]
    if sorted(cu) != ["B.Cu", "F.Cu"]:
        chk.fail(f"copper layers {cu} != [F.Cu, B.Cu]")
    o = pcb_origin(pcb)
    if o is None:
        chk.fail("no Edge.Cuts geometry")
        return chk
    W, H = d["pcb"]["w"], d["pcb"]["h"]
    if o["w"] > 100 or o["h"] > 100:
        chk.fail(f"outline {o['w']:.3f} x {o['h']:.3f} exceeds 100 x 100")
    if abs(o["w"] - W) > OUTLINE_TOL or abs(o["h"] - H) > OUTLINE_TOL:
        chk.fail(f"outline {o['w']:.3f} x {o['h']:.3f} != design {W} x {H} (tol {OUTLINE_TOL})")
    texts = pcb["texts"]
    silk = [t for t in texts if t["layer"] and "Silk" in t["layer"]]
    if not any("FROSTBITE" in t["text"].upper() for t in silk):
        chk.fail("no 'Frostbite' text on a silkscreen layer")
    if not any("XIAO HERE" in t["text"].upper() and t["layer"].startswith("B.") for t in silk):
        chk.fail("no 'XIAO HERE' text on B.Silkscreen")
    chk.details = {"copper": cu, "outline": o}
    return chk


def pcb_positions(chk: Check, d: dict, pcb: dict):
    """Footprint positions in design coordinates. Returns dict of measured points."""
    o = pcb_origin(pcb)
    if o is None:
        chk.fail("no Edge.Cuts geometry, cannot set the origin")
        return None
    X = lambda x: x - o["x0"]  # noqa: E731
    Y = lambda y: y - o["y0"]  # noqa: E731
    fps = {f["ref"]: f for f in pcb["footprints"] if f["ref"]}
    meas = {}
    rules = {}
    for k in d["keys"]:
        f = fps.get(k["ref"])
        if f is None:
            chk.fail(f"{k['ref']} footprint missing")
            continue
        mx, my = X(f["x"]), Y(f["y"])
        meas[k["ref"]] = (mx, my)
        if math.dist((mx, my), (k["x"], k["y"])) > POS_TOL or abs(mx - k["x"]) > POS_TOL or abs(my - k["y"]) > POS_TOL:
            chk.fail(f"{k['ref']} at ({mx:.3f}, {my:.3f}), design ({k['x']}, {k['y']}) tol {POS_TOL}")
    encs = fp_by(pcb, "enc")
    if len(encs) != 1:
        chk.fail(f"expected 1 encoder footprint, found {[f['ref'] for f in encs]}")
    else:
        f = encs[0]
        mps = [p for p in f["pads"] if p["num"].upper() in ("MP", "SH", "0")]
        if len(mps) == 2:
            cx, cy = (mps[0]["x"] + mps[1]["x"]) / 2, (mps[0]["y"] + mps[1]["y"]) / 2
            rules["encoder"] = "midpoint of the two MP pads (shaft centre)"
        else:
            cx, cy = f["x"], f["y"]
            rules["encoder"] = "footprint origin (no MP pad pair found)"
        meas["encoder"] = (X(cx), Y(cy))
        e = d["encoder"]
        if abs(X(cx) - e["x"]) > POS_TOL or abs(Y(cy) - e["y"]) > POS_TOL:
            chk.fail(f"encoder {f['ref']} centre ({X(cx):.3f}, {Y(cy):.3f}) [{rules['encoder']}], design ({e['x']}, {e['y']})")
    oleds = fp_by(pcb, "oled")
    if len(oleds) != 1:
        chk.fail(f"expected 1 OLED header footprint (ref/value/lib containing OLED or SSD1306), found {[f['ref'] for f in oleds]}")
    else:
        f = oleds[0]
        hd = d["oled"]["header"]
        pads = sorted([p for p in f["pads"] if re.fullmatch(r"\d+", p["num"])], key=lambda p: int(p["num"]))
        if len(pads) != 4:
            chk.fail(f"OLED {f['ref']} has {len(pads)} numbered pads, expected 4")
        else:
            xs = [X(p["x"]) for p in pads]
            ys = [Y(p["y"]) for p in pads]
            meas["oled_header"] = (sum(xs) / 4, sum(ys) / 4)
            if max(abs(x - hd["pin_row_x"]) for x in xs) > POS_TOL:
                chk.fail(f"OLED header pad x {[round(x, 3) for x in xs]} != pin_row_x {hd['pin_row_x']}")
            if abs(sum(ys) / 4 - hd["centre_y"]) > POS_TOL:
                chk.fail(f"OLED header centre y {sum(ys) / 4:.3f} != design {hd['centre_y']}")
            if [p["num"] for p in sorted(pads, key=lambda p: p["y"])] != ["1", "2", "3", "4"]:
                chk.fail("OLED header pad 1..4 do not run top-to-bottom (back to front)")
            gaps = [ys[i + 1] - ys[i] for i in range(3)]
            if any(abs(abs(g) - hd["pitch"]) > POS_TOL for g in gaps):
                chk.fail(f"OLED header pitch {gaps} != {hd['pitch']}")
    xiaos = fp_by(pcb, "xiao")
    if len(xiaos) != 1:
        chk.fail(f"expected 1 XIAO footprint, found {[f['ref'] for f in xiaos]}")
    else:
        f = xiaos[0]
        r = d["mcu"]["rect"]
        if f["layer"] != "B.Cu":
            chk.fail(f"XIAO {f['ref']} on {f['layer']}, design says bottom (B.Cu)")
        fab = [p for g in f["graphics"] if g["layer"] in ("B.Fab", "F.Fab") for p in g["pts"]]
        use = None
        if fab:
            x0, y0, x1, y1 = bbox(fab)
            if abs((x1 - x0) - r["w"]) <= 0.1 and abs((y1 - y0) - r["h"]) <= 0.1:
                use = ((x0 + x1) / 2, (y0 + y1) / 2)
                rules["xiao"] = "centre of the Fab-layer outline (17.8 x 21 body)"
        if use is None:
            use = (f["x"], f["y"])
            rules["xiao"] = "footprint origin (no 17.8 x 21 Fab outline found)"
        meas["xiao"] = (X(use[0]), Y(use[1]))
        want = (r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)
        if abs(meas["xiao"][0] - want[0]) > POS_TOL or abs(meas["xiao"][1] - want[1]) > POS_TOL:
            chk.fail(f"XIAO centre ({meas['xiao'][0]:.3f}, {meas['xiao'][1]:.3f}) [{rules['xiao']}], design ({want[0]}, {want[1]})")
    # LEDs: glow positions, chain order -> keys
    leds = fp_by(pcb, "led")
    if len(leds) != d["leds"]["count"]:
        chk.fail(f"{len(leds)} LED footprints != design {d['leds']['count']}")
    for g in d["leds"]["glow"]:
        hit = [f for f in leds if abs(X(f["x"]) - g["x"]) <= POS_TOL and abs(Y(f["y"]) - g["y"]) <= POS_TOL]
        if not hit:
            chk.fail(f"no LED footprint at glow led {g['led']} ({g['x']}, {g['y']})")
        elif g.get("side") == "bottom" and hit[0]["layer"] != "B.Cu":
            chk.fail(f"glow LED {hit[0]['ref']} on {hit[0]['layer']}, design says bottom")
    din = {}
    for f in leds:
        roles = {(_pin_role({"pin": p["num"], "pinfunction": p["pinfunction"]}, "led")): p["net"] for p in f["pads"]}
        din[roles.get("DIN")] = (f, roles.get("DOUT"))
    start = next((n for n in din if n is not None and is_net(n, "LED_DIN")), None)
    chain, cur = [], start
    while cur in din and din[cur][0]["ref"] not in [c["ref"] for c in chain] and cur is not None:
        f, cur = din[cur]
        chain.append(f)
    chk.details["pcb_led_chain"] = [f["ref"] for f in chain]
    if start is None:
        chk.note("LED pads carry no LED_DIN net (netlist not imported?); chain-to-key mapping not checked")
        if leds:
            chk.fail("LED chain order cannot be derived from PCB pad nets (no pad on net LED_DIN)")
    else:
        by_led = {k["led"]: k for k in d["keys"]}
        glow = {g["led"]: g for g in d["leds"]["glow"]}
        if len(chain) != d["leds"]["count"]:
            chk.fail(f"PCB LED chain from LED_DIN has {len(chain)} LEDs, design {d['leds']['count']}")
        for i, f in enumerate(chain):
            p = (X(f["x"]), Y(f["y"]))
            if i in by_led:
                near = min(d["keys"], key=lambda k: math.dist(p, (k["x"], k["y"])))
                if near["ref"] != by_led[i]["ref"]:
                    chk.fail(f"chain LED {i} ({f['ref']}) sits under {near['ref']}, design says {by_led[i]['ref']}")
            elif i in glow and math.dist(p, (glow[i]["x"], glow[i]["y"])) > POS_TOL:
                chk.fail(f"chain LED {i} ({f['ref']}) at ({p[0]:.2f}, {p[1]:.2f}), design glow ({glow[i]['x']}, {glow[i]['y']})")
    chk.details["measured"] = {k: [round(v[0], 4), round(v[1], 4)] for k, v in meas.items()}
    chk.details["centre_rules"] = rules
    return meas


def g3_positions(ctx: Ctx) -> Check:
    chk = Check(ctx, "G3.positions", "G3", "Footprint positions (parsed .kicad_pcb) vs design.json within 0.05 mm")
    d = design(chk)
    pcb, path = _pcb(chk)
    if d is None or pcb is None:
        return chk
    meas = pcb_positions(chk, d, pcb)
    ctx.cache["pcb_meas"] = meas
    ctx.cache["G3.positions_failures"] = list(chk.failures)
    if ctx.kicad_cli is not None:
        out = ctx.work / "pos.csv"
        code, so, se = chk.run([ctx.kicad_cli, "pcb", "export", "pos", "--format", "csv", "--units", "mm",
                                "--side", "both", "-o", out, path])
        if code != 0:
            chk.fail(f"kicad-cli pcb export pos exited {code}")
        elif out.is_file():
            chk.details["pos_csv_sha256"] = sha256(out)
            chk.details["pos_csv_head"] = out.read_text().splitlines()[:30]
    return chk


def _gerber_stack_check(chk: Check, stack, d):
    want = {("top", "copper"): "F.Cu", ("bottom", "copper"): "B.Cu", ("top", "mask"): "F.Mask",
            ("bottom", "mask"): "B.Mask", ("top", "silk"): "F.Silk", ("bottom", "silk"): "B.Silk",
            ("mechanical", "outline"): "Edge.Cuts"}
    have = {k: str(getattr(v, "original_path", "") or "") for k, v in stack.graphic_layers.items()}
    chk.details["layers_found"] = {f"{a} {b}": Path(p).name for (a, b), p in have.items()}
    for k, name in want.items():
        if k not in stack.graphic_layers:
            chk.fail(f"gerber layer missing: {name} ({k[0]} {k[1]})")
    drills = list(stack.drill_layers) + [x for x in (stack.drill_pth, stack.drill_npth) if x is not None]
    if not drills:
        chk.fail("no drill file found")
    chk.details["drill_files"] = len(drills)
    if ("mechanical", "outline") in stack.graphic_layers:
        (x0, y0), (x1, y1) = stack.board_bounds(unit="mm")
        stroke = 0.0
        try:
            from gerbonara.utils import MM
            ws = [o.aperture.equivalent_width(MM) for o in stack.outline.objects if getattr(o, "aperture", None)]
            stroke = max(ws) if ws else 0.0
        except Exception as e:  # pragma: no cover - API drift
            chk.note(f"outline stroke width not read: {e}")
        w, h = x1 - x0 - stroke, y1 - y0 - stroke
        chk.details["outline_mm"] = {"w": round(w, 4), "h": round(h, 4), "stroke": stroke}
        if abs(w - d["pcb"]["w"]) > OUTLINE_TOL or abs(h - d["pcb"]["h"]) > OUTLINE_TOL:
            chk.fail(f"gerber outline {w:.3f} x {h:.3f} != design {d['pcb']['w']} x {d['pcb']['h']}")
        if w > 100 or h > 100:
            chk.fail(f"gerber outline {w:.3f} x {h:.3f} exceeds 100 x 100")


def g3_gerbers(ctx: Ctx) -> Check:
    chk = Check(ctx, "G3.gerbers_export", "G3", "Fresh gerber + drill export parsed with gerbonara")
    d = design(chk)
    pcb, path = _pcb(chk)
    if d is None or pcb is None:
        return chk
    if not need_kicad(chk):
        return chk
    out = ctx.work / "gerbers"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    c1, *_ = chk.run([ctx.kicad_cli, "pcb", "export", "gerbers", "-o", str(out) + "/", path])
    c2, *_ = chk.run([ctx.kicad_cli, "pcb", "export", "drill", "-o", str(out) + "/", path])
    if c1 or c2:
        chk.fail(f"gerber export exit {c1}, drill export exit {c2}")
        return chk
    from gerbonara import LayerStack
    try:
        import warnings
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter("always")
            stack = LayerStack.open(out)
        chk.details["gerbonara_warnings"] = [str(w.message).split("/")[-1][:200] for w in ws[:10]]
        _gerber_stack_check(chk, stack, d)
    except Exception as e:
        chk.fail(f"gerbonara could not open the export: {e}")
    return chk


def g3_gerbers_zip(ctx: Ctx) -> Check:
    chk = Check(ctx, "G3.gerbers_zip", "G3", "production/gerbers.zip parsed with gerbonara")
    d = design(chk)
    z = ctx.p("production/gerbers.zip")
    if d is None:
        return chk
    if not z.is_file():
        return chk.not_run("production/gerbers.zip missing")
    chk.hash(z)
    from gerbonara import LayerStack
    try:
        import warnings
        with warnings.catch_warnings(record=True) as ws:
            warnings.simplefilter("always")
            stack = LayerStack.open(z)
        chk.details["gerbonara_warnings"] = [str(w.message).split("/")[-1][:200] for w in ws[:10]]
        _gerber_stack_check(chk, stack, d)
    except Exception as e:
        chk.fail(f"gerbonara could not open gerbers.zip: {e}")
    return chk


# ================================================================ G4

def g4_check_fit(ctx: Ctx) -> Check:
    chk = Check(ctx, "G4.check_fit", "G4", "CAD/.venv/bin/python CAD/check_fit.py --no-build (checks the shipped files, rewrites nothing)")
    py, script = ctx.p("CAD/.venv/bin/python"), ctx.p("CAD/check_fit.py")
    if not script.is_file():
        return chk.not_run("CAD/check_fit.py missing")
    if not py.is_file():
        return chk.not_run("CAD/.venv/bin/python missing")
    for f in find_one(ctx.p("CAD"), "*.py"):
        chk.hash(f)
    chk.hash(ctx.p("design.json"))
    code, so, se = chk.run([py, script, "--no-build"], cwd=ctx.root, timeout=900, env={"PYTHONDONTWRITEBYTECODE": "1"})
    if code != 0:
        chk.fail(f"check_fit.py exited {code}")
    return chk


def stl_files(ctx: Ctx):
    prod = ctx.p("production")
    return sorted(p for p in prod.glob("*") if p.suffix.lower() == ".stl") if prod.is_dir() else []


def load_mesh(chk: Check, p: Path):
    import trimesh
    chk.hash(p)
    m = trimesh.load(str(p), force="mesh", process=True)
    return m


def g4_stl_mesh(ctx: Ctx) -> Check:
    chk = Check(ctx, "G4.stl_mesh", "G4", "production/*.stl: watertight, positive volume, combined bounds <= 200x200x100")
    stls = stl_files(ctx)
    if not stls:
        return chk.not_run("no production/*.stl")
    import numpy as np
    names = {p.stem for p in stls}
    for n in PARTS:
        if n not in names:
            chk.fail(f"production/{n}.stl missing")
    lo, hi, parts = None, None, {}
    for p in stls:
        try:
            m = load_mesh(chk, p)
        except Exception as e:
            chk.fail(f"{p.name}: cannot load ({e})")
            continue
        info = {"faces": int(len(m.faces)), "watertight": bool(m.is_watertight),
                "winding_consistent": bool(m.is_winding_consistent), "volume": float(m.volume),
                "extents": [round(float(x), 3) for x in m.extents]}
        parts[p.name] = info
        if not m.is_watertight:
            chk.fail(f"{p.name}: not watertight")
        if not m.is_winding_consistent:
            chk.fail(f"{p.name}: inconsistent winding")
        if not (m.volume > 0):
            chk.fail(f"{p.name}: volume {m.volume:.3f} not positive")
        b = m.bounds
        lo = b[0] if lo is None else np.minimum(lo, b[0])
        hi = b[1] if hi is None else np.maximum(hi, b[1])
    if lo is not None:
        ext = (hi - lo).tolist()
        chk.details["combined_extents"] = [round(x, 3) for x in ext]
        for v, lim, ax in zip(ext, (200, 200, 100), "xyz"):
            if v > lim:
                chk.fail(f"combined bounds {ax} = {v:.2f} mm > {lim}")
    chk.details["parts"] = parts
    return chk


def top_stl(ctx: Ctx):
    return [p for p in stl_files(ctx) if re.search(r"top|plate", p.stem, re.I)]


def module_gap(d: dict):
    return ((d.get("case") or {}).get("oled_support") or {}).get("module_gap")


def heights(d: dict) -> dict:
    """Depth below the plate top of everything that starts or stops somewhere, from design.json where it says."""
    h = {"ec11_body_top": MX_PLATE_TO_PCB - EC11_BODY_H, "pcb_top": MX_PLATE_TO_PCB,
         "pcb_under": MX_PLATE_TO_PCB + PCB_T, "clip": CLIP_PLATE}
    gap = module_gap(d)
    if gap is not None:
        h["oled_board_under"] = MX_PLATE_TO_PCB - gap
        h["oled_board_top"] = h["oled_board_under"] - OLED_BOARD_T
        h["oled_glass_top"] = h["oled_board_top"] - OLED_GLASS_T
    return h


def top_model(chk: Check, d: dict):
    """The Top part, registered into PCB coordinates from its own outline. None -> status already set."""
    from . import topmodel
    tops = top_stl(chk.ctx)
    if not tops:
        chk.not_run("no production STL with 'top' or 'plate' in its name")
        return None
    if len(tops) > 1:
        chk.note(f"several top/plate STLs {[p.name for p in tops]}; using {tops[0].name}")
    key = ("top", str(tops[0]), tops[0].stat().st_mtime_ns)
    if key not in chk.ctx.cache:
        chk.ctx.cache[key] = topmodel.register(load_mesh(chk, tops[0]), d, extra_h=tuple(heights(d).values()))
    chk.hash(tops[0])
    M, info = chk.ctx.cache[key]
    chk.details["registration"] = info
    sh = d["case"]["shell"]
    wu, wv = info["outline_mm"]
    if abs(wu - sh["w"]) > SHELL_TOL or abs(wv - sh["h"]) > SHELL_TOL:
        chk.fail(f"{tops[0].name} outline {wu:.2f} x {wv:.2f} != design.json case.shell {sh['w']} x {sh['h']} (tol {SHELL_TOL})")
    if abs(M.section_volume - M.mesh_volume) > 0.005 * abs(M.mesh_volume):
        chk.fail(f"cross-sections integrate to {M.section_volume:.1f} mm3, mesh volume is {M.mesh_volume:.1f}: "
                 "the slicer lost material, no measurement here can be trusted")
    return M


def g4_switch_cutouts(ctx: Ctx) -> Check:
    chk = Check(ctx, "G4.switch_cutouts", "G4", "Top: a real switch fits, clips in, and sits on its design.json position")
    d = design(chk)
    if d is None:
        return chk
    M = top_model(chk, d)
    if M is None:
        return chk
    import shapely.geometry as g
    H = MX_PLATE_TO_PCB
    half = (SWITCH_W - 2 * CUTOUT_TOL) / 2
    rows = []
    for k in d["keys"]:
        x, y = k["x"], k["y"]
        sx, sy = M.spans(x, y, "x", 0, H), M.spans(x, y, "y", 0, H)
        if sx is None or sy is None:
            chk.fail(f"{k['ref']}: no opening at design position ({x}, {y})")
            continue
        nx, ny = min(sx, key=lambda q: q[1] - q[0]), min(sy, key=lambda q: q[1] - q[0])
        wx, wy = nx[1] - nx[0], ny[1] - ny[0]
        ccx, ccy = (nx[0] + nx[1]) / 2, (ny[0] + ny[1]) / 2
        tx = sum(q[3] - q[2] for q in sx if q[1] - q[0] <= SWITCH_W + CUTOUT_TOL)
        ty = sum(q[3] - q[2] for q in sy if q[1] - q[0] <= SWITCH_W + CUTOUT_TOL)
        clip = min(tx, ty)
        fit, at = M.min_gap(g.box(x - half, y - half, x + half, y + half), 0, H)
        rows.append({"ref": k["ref"], "narrowest_mm": [round(wx, 3), round(wy, 3)], "centre": [round(ccx, 3), round(ccy, 3)],
                     "clip_plate_mm": round(clip, 3), "housing_gap_mm": round(fit, 3)})
        if abs(wx - SWITCH_W) > CUTOUT_TOL or abs(wy - SWITCH_W) > CUTOUT_TOL:
            chk.fail(f"{k['ref']}: narrowest opening {wx:.3f} x {wy:.3f}, want {SWITCH_W} +/-{CUTOUT_TOL}")
        if abs(ccx - x) > CAD_POS_TOL or abs(ccy - y) > CAD_POS_TOL:
            chk.fail(f"{k['ref']}: opening centre ({ccx:.3f}, {ccy:.3f}), design ({x}, {y}) tol {CAD_POS_TOL}")
        if fit < 0:
            chk.fail(f"{k['ref']}: a {2 * half:.1f} mm switch housing hits the Top at depth {at} mm")
        if abs(clip - CLIP_PLATE) > CLIP_PLATE_TOL:
            chk.fail(f"{k['ref']}: clips engage {clip:.2f} mm of plate, want {CLIP_PLATE} +/-{CLIP_PLATE_TOL}")
    chk.details["switches"] = rows
    return chk


def g4_encoder_clearance(ctx: Ctx) -> Check:
    chk = Check(ctx, "G4.encoder_clearance", "G4", "Top clears the real EC11 body and bushing along the PCB's path, any opening shape")
    d = design(chk)
    if d is None:
        return chk
    M = top_model(chk, d)
    if M is None:
        return chk
    import shapely.geometry as g
    e = d["encoder"]
    x, y = e["x"], e["y"]
    h = EC11_BODY_W / 2
    bt = heights(d)["ec11_body_top"]
    body, at = M.min_gap(g.box(x - h, y - h, x + h, y + h), bt, M.hmax)
    bush, at2 = M.min_gap(g.Point(x, y).buffer(EC11_BUSH_D / 2, 64), 0, bt)
    chk.details["body_gap_mm"], chk.details["bushing_gap_mm"] = round(body, 3), round(bush, 3)
    for name, gap, where in (("body", body, at), ("bushing", bush, at2)):
        if gap < EC11_CLEAR:
            chk.fail(f"EC11 {name} gap {gap:.3f} mm at depth {where} mm, want >= {EC11_CLEAR}")
    op = M.opening_at(x, y, 0.05)
    if op is not None:
        b = op.bounds
        chk.details["measured_opening"] = {"bounds": [round(v, 3) for v in b], "w": round(b[2] - b[0], 3), "h": round(b[3] - b[1], 3)}
        cp, rel = load_cad_positions(ctx, chk)
        o = ((cp or {}).get("encoder") or {}).get("opening")
        if o and (abs(o["w"] - (b[2] - b[0])) > 0.2 or abs(o["h"] - (b[3] - b[1])) > 0.2):
            chk.fail(f"{rel}: encoder opening says {o['w']} x {o['h']}, the Top measures {b[2] - b[0]:.2f} x {b[3] - b[1]:.2f}")
    return chk


def _pose_envelope(rect, pivot):
    """Everywhere a part soldered to J1 can be: turned about the header, then shifted. Union of the extreme poses."""
    import shapely.ops as o
    from shapely import affinity
    poses = []
    for yaw in (-OLED_YAW, 0.0, OLED_YAW):
        turned = affinity.rotate(rect, yaw, origin=pivot)
        poses += [affinity.translate(turned, dx, dy) for dx in (-OLED_SHIFT, OLED_SHIFT) for dy in (-OLED_SHIFT, OLED_SHIFT)]
    return o.unary_union(poses).convex_hull


def g4_oled_clearance(ctx: Ctx) -> Check:
    chk = Check(ctx, "G4.oled_clearance", "G4", "OLED glass and board clear the Top along the PCB's path; active area fully visible; window size is free")
    d = design(chk)
    if d is None:
        return chk
    M = top_model(chk, d)
    if M is None:
        return chk
    gap = module_gap(d)
    if gap is None:
        chk.fail("design.json case.oled_support.module_gap missing: the OLED height is not known")
        return chk
    import shapely.geometry as g
    w, mod, hdr = d["oled"]["window"], d["oled"]["module"], d["oled"]["header"]
    H = heights(d)
    pivot = (hdr["pin_row_x"], hdr["centre_y"])
    glass = _pose_envelope(g.box(w["x"], w["y"], w["x"] + w["w"], w["y"] + w["h"]), pivot)
    board = _pose_envelope(g.box(mod["x"], mod["y"], mod["x"] + mod["w"], mod["y"] + mod["h"]), pivot)
    cx, cy = w["x"] + w["w"] / 2, w["y"] + w["h"] / 2
    aw, ah = OLED_ACTIVE
    active = _pose_envelope(g.box(cx + OLED_ACTIVE_DX[0] - aw / 2, cy - OLED_ACTIVE_DY - ah / 2,
                                  cx + OLED_ACTIVE_DX[1] + aw / 2, cy + OLED_ACTIVE_DY + ah / 2), pivot)
    chk.details["stack_depth_below_plate_top"] = {k: round(v, 3) for k, v in H.items() if k.startswith("oled")}
    chk.details["module_gap"] = gap
    gt, bt = H["oled_glass_top"], H["oled_board_top"]
    if gt < 0:
        chk.fail(f"OLED glass stands proud of the plate by {-gt:.2f} mm with module_gap {gap}")
    gg, a1 = M.min_gap(glass, max(gt, 0.0), M.hmax)
    gb, a2 = M.min_gap(board, bt, M.hmax)
    chk.details["glass_gap_mm"], chk.details["board_gap_mm"] = round(gg, 3), round(gb, 3)
    if gg < 0:
        chk.fail(f"OLED glass hits the Top on its way in, at depth {a1} mm ({-gg:.2f} mm2, module turned {OLED_YAW} deg and shifted {OLED_SHIFT})")
    if gb < 0:
        chk.fail(f"OLED board hits the Top on its way in, at depth {a2} mm ({-gb:.2f} mm2, module turned {OLED_YAW} deg and shifted {OLED_SHIFT})")
    if gt > 0:
        ga, a3 = M.min_gap(active, 0.0, gt)
        chk.details["active_area_gap_mm"] = round(ga, 3)
        if ga < 0:
            chk.fail(f"active area not fully visible: {-ga:.2f} mm2 covered by the Top at depth {a3} mm")
    support = ctx.p("production/OLEDSupport.stl")
    tape = (d["case"]["oled_support"] or {}).get("tape", 0.0)
    if support.is_file():
        import numpy as np
        ext = float(np.min(load_mesh(chk, support).extents))
        want = gap - 2 * tape
        chk.details["support_height_mm"] = round(ext, 3)
        if abs(ext - want) > 0.05:
            chk.fail(f"OLEDSupport is {ext:.3f} mm tall, module_gap {gap} - 2 x tape {tape} needs {want:.3f}")
    else:
        chk.fail("production/OLEDSupport.stl missing: nothing sets the module height")
    op = M.opening_at(cx, cy, 0.05)
    if op is None:
        chk.note("no closed opening around the window centre at the plate top; the record check is skipped")
        return chk
    b = op.bounds
    cut = {"x": round(b[0], 3), "y": round(b[1], 3), "w": round(b[2] - b[0], 3), "h": round(b[3] - b[1], 3)}
    chk.details["measured_window"] = cut
    cp, rel = load_cad_positions(ctx, chk)
    pw = (cp or {}).get("oled_window")
    if pw is not None:                     # the record must describe the file; any size is allowed
        stated = pw.get("cut", pw)
        if any(abs(stated[k] - cut[k]) > CAD_POS_TOL for k in ("x", "y", "w", "h")):
            chk.fail(f"{rel}: oled_window cut {stated} != measured {cut}")
    return chk


def g4_step_parts(ctx: Ctx) -> Check:
    chk = Check(ctx, "G4.step_parts", "G4", "Every printed part: STEP reopens, its STL is the same solid, and both match a rebuild from the current source")
    py = Path(__file__).resolve().parents[2] / "CAD/.venv/bin/python"
    if not py.is_file():
        return chk.not_run("CAD/.venv/bin/python missing")
    pairs = [(n, ctx.p(f"production/{n}.step"), ctx.p(f"production/{n}.stl")) for n in PARTS]
    have = [(n, a, b) for n, a, b in pairs if a.is_file() and b.is_file()]
    if not have:
        return chk.not_run("no production STEP/STL pairs")
    for n, a, b in pairs:
        if not (a.is_file() and b.is_file()):
            chk.fail(f"{n}: production .step or .stl missing")
    for _, a, _ in have:
        chk.hash(a)
    code, so, se = chk.run([py, Path(__file__).with_name("probe_step.py"), ctx.root, *[a for _, a, _ in have]], timeout=300,
                           env={"PYTHONDONTWRITEBYTECODE": "1"})
    if code != 0:
        chk.fail(f"probe_step.py exited {code}")
        return chk
    r = json.loads(so.strip().splitlines()[-1])
    rows = {}
    for n, a, b in have:
        vs, vm = r["step"][str(a)], float(load_mesh(chk, b).volume)
        vb = r["built"].get(n)
        rows[n] = {"step_mm3": round(vs, 1), "stl_mm3": round(vm, 1), "rebuilt_mm3": None if vb is None else round(vb, 1)}
        if abs(vs - vm) > 0.01 * abs(vs):
            chk.fail(f"{n}: STEP volume {vs:.1f} mm3, STL volume {vm:.1f} mm3: not the same part")
        if vb is None:
            chk.fail(f"{n}: the CAD source no longer builds this part")
        elif abs(vb - vs) > 0.001 * abs(vb):
            chk.fail(f"{n}: production STEP is {vs:.1f} mm3, a rebuild from the current source is {vb:.1f} mm3: stale, rebuild the case")
    chk.details["parts"] = rows
    return chk


# ================================================================ G5

def g5_bom_kit(ctx: Ctx) -> Check:
    chk = Check(ctx, "G5.bom_kit", "G5", "Part counts (design.json, PCB footprints) vs Hackpad kit")
    d = design(chk)
    if d is None:
        return chk
    m = re.match(r"\s*(\d+)\s*x", d["case"]["inserts"])
    inserts = int(m.group(1)) if m else None
    need = {"switches": len(d["keys"]), "keycaps": len(d["keys"]), "diodes": len(d["keys"]),
            "encoders": 1, "oled": 1, "leds": d["leds"]["count"], "screws": inserts, "inserts": inserts,
            "mcu_xiao_rp2040": 1}
    for k, v in need.items():
        if v is None:
            chk.fail(f"design.json: cannot read a count for {k}")
        elif v > KIT[k]:
            chk.fail(f"design needs {v} {k}, kit has {KIT[k]}")
    extras = [{"item": "knob: " + d["encoder"]["knob"], "qty": 1, "why": "kit has no knob"}]
    pcb_counts = None
    kf = kicad_files(ctx)
    if kf["pcb"] is not None:
        pcb = sexpr.load_pcb(chk.read(kf["pcb"]))
        pcb_counts = {"switches": len(fp_by(pcb, "switch")), "diodes": len(fp_by(pcb, "diode")),
                      "encoders": len(fp_by(pcb, "enc")), "oled": len(fp_by(pcb, "oled")),
                      "leds": len(fp_by(pcb, "led")), "mcu_xiao_rp2040": len(fp_by(pcb, "xiao"))}
        others = [f["ref"] for f in pcb["footprints"] if classify({"ref": f["ref"] or "", "value": f["value"] or "",
                                                                  "footprint": f["lib"], "lib": f["lib"]}) == "other"]
        for k, v in pcb_counts.items():
            if v > KIT[k]:
                chk.fail(f"PCB has {v} {k} footprints, kit has {KIT[k]}")
            if v != need[k]:
                chk.fail(f"PCB has {v} {k} footprints, design.json implies {need[k]}")
        if others:
            chk.details["pcb_unclassified_footprints"] = others
            extras.append({"item": "unclassified PCB footprints (not in kit)", "qty": len(others), "why": ", ".join(others[:20])})
    else:
        chk.note("no PCB yet: footprint counts not compared")
    chk.details.update({"kit": KIT, "design_needs": need, "pcb_counts": pcb_counts, "extras_to_buy": extras,
                        "spare_in_kit": {k: KIT[k] - v for k, v in need.items() if v is not None}})
    return chk


# ================================================================ G6

def fw_sources(ctx: Ctx):
    """Files that change the build: everything under the keyboard dir except docs."""
    return [p for p in find_one(ctx.p(KB_DIR), "*") if p.suffix in (".c", ".h", ".json", ".mk") or p.name == "rules.mk"]


def _qmk_link(chk: Check) -> bool:
    ctx = chk.ctx
    link = ctx.qmk_home / "keyboards/frostbite"
    if not shutil.which("qmk", path=ctx.env["PATH"]):
        chk.not_run("qmk CLI not on PATH")
        return False
    if not ctx.p(KB_DIR).is_dir():
        chk.not_run(f"{KB_DIR} missing")
        return False
    if not link.exists():
        chk.not_run(f"{link} does not exist (firmware not linked into QMK home)")
        return False
    if link.resolve() != ctx.p(KB_DIR).resolve():
        chk.fail(f"{link} resolves to {link.resolve()}, not this project's {KB_DIR}")
        return False
    chk.details["qmk_link"] = str(link.resolve())
    for f in fw_sources(ctx):
        chk.hash(f)
    return True


def g6_qmk_lint(ctx: Ctx) -> Check:
    chk = Check(ctx, "G6.qmk_lint", "G6", "qmk lint -kb frostbite")
    if not ctx.run_qmk:
        return chk.not_run("QMK steps disabled (--no-qmk)")
    if not _qmk_link(chk):
        return chk
    code, so, se = chk.run(["qmk", "lint", "-kb", "frostbite"], cwd=ctx.qmk_home, timeout=300)
    if code != 0:
        chk.fail(f"qmk lint exited {code}")
    return chk


def check_uf2_bytes(chk: Check, data: bytes, label: str) -> dict:
    info = geom.parse_uf2(data)
    chk.details[f"uf2_{label}"] = info
    for e in info["errors"]:
        chk.fail(f"{label}: {e}")
    return info


def g6_compile(ctx: Ctx, km: str) -> Check:
    chk = Check(ctx, f"G6.compile_{km}", "G6", f"qmk compile -kb frostbite -km {km} + UF2 parse")
    if not ctx.run_qmk:
        return chk.not_run("QMK steps disabled (--no-qmk)")
    if not _qmk_link(chk):
        return chk
    if not (ctx.p(KB_DIR) / "keymaps" / km).is_dir():
        return chk.not_run(f"keymap {km} missing")
    t0 = time.time()
    code, so, se = chk.run(["qmk", "compile", "-kb", "frostbite", "-km", km], cwd=ctx.qmk_home, timeout=900)
    if code != 0:
        chk.fail(f"qmk compile -km {km} exited {code}")
        return chk
    uf2 = ctx.qmk_home / f"frostbite_{km}.uf2"
    if not uf2.is_file() or uf2.stat().st_mtime < t0 - 1:
        chk.fail(f"{uf2} not produced by this compile")
        return chk
    data = uf2.read_bytes()
    keep = ctx.work / uf2.name
    keep.write_bytes(data)
    chk.details["uf2_path"] = str(uf2)
    chk.details["uf2_sha256"] = sha256(keep)
    check_uf2_bytes(chk, data, uf2.name)
    ctx.cache[f"uf2_{km}"] = keep
    return chk


def g6_production_uf2(ctx: Ctx) -> Check:
    chk = Check(ctx, "G6.production_uf2", "G6", "production/firmware.uf2 valid and current (identical to fresh build or newer than sources)")
    p = ctx.p("production/firmware.uf2")
    if not p.is_file():
        return chk.not_run("production/firmware.uf2 missing")
    data = chk.read(p, "b")
    check_uf2_bytes(chk, data, "production/firmware.uf2")
    for other in sorted(ctx.p("production").glob("*.uf2")):
        if other.name != "firmware.uf2":
            check_uf2_bytes(chk, chk.read(other, "b"), f"production/{other.name}")
    fresh = ctx.cache.get("uf2_default")
    srcs = fw_sources(ctx)
    newest = max((s.stat().st_mtime for s in srcs), default=0)
    identical = bool(fresh and fresh.read_bytes() == data)
    newer = p.stat().st_mtime >= newest
    chk.details.update({"identical_to_fresh_build": identical if fresh else None,
                        "newer_than_all_firmware_sources": newer})
    if not identical and not newer:
        stale = max(srcs, key=lambda s: s.stat().st_mtime)
        chk.fail(f"production/firmware.uf2 differs from the fresh build and is older than {stale.relative_to(ctx.root)}")
    return chk


# ================================================================ G6 firmware behaviour on the desk

F1_LINES = ("PASS F1 KBD: panel matches buffer on all 4 pages", "PASS F1 idle screen: 0 I2C bytes in 1000 loops",
            "PASS F1 HID: slot strip and HID reach the panel", "PASS F1 divider all 42 dots on panel")


def _harness(chk: Check) -> str | None:
    ctx = chk.ctx
    run = ctx.p("Firmware/tests/run.sh")
    if not run.is_file():
        chk.not_run("Firmware/tests/run.sh missing")
        return None
    if not shutil.which("clang", path=ctx.env["PATH"]):
        chk.not_run("clang not on PATH")
        return None
    if not (ctx.qmk_home / "drivers/oled/oled_driver.c").is_file():
        chk.not_run(f"{ctx.qmk_home} has no drivers/oled/oled_driver.c")
        return None
    for f in find_one(ctx.p("Firmware/tests"), "*") + fw_sources(ctx):
        chk.hash(f)
    key = ("fw_harness", str(run))
    if key not in ctx.cache:
        out = ctx.work / "fwtest"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        code, so, se = chk.run(["bash", run, out], timeout=300, env={"QMK_HOME": str(ctx.qmk_home)})
        ctx.cache[key] = (code, so, out)
    code, so, out = ctx.cache[key]
    return so if code is not None else None


def g6_firmware_harness(ctx: Ctx) -> Check:
    chk = Check(ctx, "G6.firmware_harness", "G6", "Real keymap.c + real QMK OLED driver on the desk under ASan/UBSan, plus the host<->firmware protocol")
    so = _harness(chk)
    if so is None:
        return chk
    code, _, out = ctx.cache[("fw_harness", str(ctx.p("Firmware/tests/run.sh")))]
    passed = [l for l in so.splitlines() if l.startswith("PASS ")]
    failed = [l for l in so.splitlines() if l.startswith("FAIL ")]
    chk.details["harness"] = {"exit_code": code, "pass": len(passed), "fail": len(failed)}
    if code != 0:
        chk.fail(f"harness exited {code}" + (f"; {failed[0]}" if failed else ""))
    for l in failed[:20]:
        chk.fail(l)
    if not passed:
        chk.fail("harness printed no PASS lines")
    binary, proto = out / "harness", ctx.p("Firmware/tests/proto_test.py")
    if binary.is_file() and proto.is_file() and ctx.p("host/pyproject.toml").is_file():
        uv = shutil.which("uv", path=ctx.env["PATH"]) or str(Path.home() / ".local/bin/uv")
        venv = Path(__file__).resolve().parents[1] / ".cache" / "host-venv"
        c2, o2, e2 = chk.run([uv, "run", "--project", ctx.p("host"), "python", proto, binary], timeout=300,
                             env={"UV_PROJECT_ENVIRONMENT": str(venv), "PYTHONDONTWRITEBYTECODE": "1"})
        m = re.search(r"^ok (\d+) bad (\d+)", o2, re.M)
        chk.details["protocol"] = {"exit_code": c2, "ok": int(m.group(1)) if m else None, "bad": int(m.group(2)) if m else None}
        if c2 != 0 or not m or m.group(2) != "0" or m.group(1) == "0":
            chk.fail(f"proto_test.py exited {c2}, summary {m.group(0) if m else 'missing'}")
    else:
        chk.note("protocol test not run (harness binary, proto_test.py or host project missing)")
    return chk


def g6_oled_strip_panel(ctx: Ctx) -> Check:
    chk = Check(ctx, "G6.oled_strip_panel", "G6", "F1 regression: slot strip and divider reach the simulated SSD1306, not just the frame buffer")
    so = _harness(chk)
    if so is None:
        return chk
    lines = so.splitlines()
    for want in F1_LINES:
        if want not in lines:
            chk.fail(f"missing from harness output: '{want}'")
    pages = [l for l in lines if re.match(r"page\d buffer ", l)]
    chk.details["panel_dump"] = pages[-8:]
    if not pages:
        chk.fail("harness printed no panel dump")
    for l in pages[-4:]:
        m = re.search(r"bytes differing=(\d+) never-written=(\d+)", l)
        if not m or m.group(1) != "0" or m.group(2) != "0":
            chk.fail(f"panel differs from the frame buffer: {l}")
    return chk


# ================================================================ G7

def g7_host_tests(ctx: Ctx) -> Check:
    chk = Check(ctx, "G7.host_tests", "G7", "uv run --project host pytest -q, every test file, audit tests included")
    proj = ctx.p("host/pyproject.toml")
    if not proj.is_file():
        return chk.not_run("host/pyproject.toml missing")
    tests = find_one(ctx.p("host/tests"), "test_*.py") + find_one(ctx.p("host/tests"), "*_test.py")
    if not tests:
        return chk.not_run("no host/tests/test_*.py")
    for f in find_one(ctx.p("host"), "*.py") + [proj] + find_one(ctx.p("host/tests/fixtures"), "*"):
        chk.hash(f)
    uv = shutil.which("uv", path=ctx.env["PATH"]) or str(Path.home() / ".local/bin/uv")
    venv = Path(__file__).resolve().parents[1] / ".cache" / "host-venv"
    env = {"UV_PROJECT_ENVIRONMENT": str(venv), "PYTHONDONTWRITEBYTECODE": "1"}
    code, so, se = chk.run([uv, "run", "--project", str(ctx.p("host")), "pytest", "-q", "-p", "no:cacheprovider",
                            "-rx", "--tb=short"], cwd=ctx.p("host"), timeout=600, env=env)
    if code == 5:
        return chk.not_run("pytest collected no tests (exit 5)")
    if code != 0:
        chk.fail(f"pytest exited {code}")
    m = re.search(r"^.*\d+ (?:passed|failed|error).*$", so, re.M)
    chk.details["summary"] = m.group(0).strip("= ") if m else None
    xf = re.findall(r"^XFAIL \S+::(\S+)(?: - (.*))?$", so, re.M)
    chk.details["xfailed_known_open"] = [f"{a}: {b}" for a, b in xf]
    if xf:
        chk.note(f"{len(xf)} tests are strict xfail: open audit findings, not passes")
    names = {f.name for f in tests}
    chk.details["test_files"] = sorted(names)
    audit = find_one(ctx.p("docs/audit/host-tests"), "test_*.py")
    left = [f for f in audit if f.name not in names]
    if left:
        # Run a private copy: the audit stub predates F12 (tap_code_delay), and docs/audit is a record, not ours to edit.
        mirror = ctx.work / "audit-mirror"
        if mirror.exists():
            shutil.rmtree(mirror)
        dst = mirror / "docs/audit/host-tests"
        shutil.copytree(ctx.p("docs/audit/host-tests"), dst, ignore=shutil.ignore_patterns("__pycache__"))
        (mirror / "Firmware").symlink_to(ctx.p("Firmware").resolve())
        stub = dst / "fw_stub/qmk_stub.h"
        if stub.is_file() and "tap_code_delay" not in stub.read_text():
            t = stub.read_text().replace('static inline void tap_code(uint16_t k){printf("TAP %d\\n",k);}',
                                         'static inline void tap_code(uint16_t k){printf("TAP %d\\n",k);}\n'
                                         'static inline void tap_code_delay(uint16_t k,uint16_t d){(void)d;tap_code(k);}')
            stub.write_text(t)
            chk.note("audit stub copy gained tap_code_delay (keymap uses it since F12); docs/audit is unchanged")
    for f in left:
        c2, o2, e2 = chk.run([uv, "run", "--project", str(ctx.p("host")), "pytest", "-q", "-p", "no:cacheprovider",
                              f"--rootdir={dst}", str(dst / f.name)], cwd=ctx.p("host"), timeout=300, env=env)
        chk.details[f"audit_{f.name}"] = (re.findall(r"\d+ (?:passed|failed|error)[^=\n]*", o2) or [None])[-1]
        if c2 != 0:
            chk.fail(f"{f.name} (docs/audit/host-tests) exited {c2}")
    return chk


# ================================================================ G8

IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)|<img[^>]*src=[\"']([^\"']+)[\"'][^>]*>", re.I)


def g8_package(ctx: Ctx) -> Check:
    chk = Check(ctx, "G8.package", "G8", "Hackpad submission structure and README sections")
    r = ctx.root
    cad = [p for p in find_one(ctx.p("CAD"), "*") if p.suffix.lower() in (".step", ".stp", ".3mf")]
    if len(cad) != 1:
        chk.fail(f"CAD/ must hold exactly one full-assembly .step/.stp/.3mf, found {[str(p.relative_to(r)) for p in cad]}")
    kf = kicad_files(ctx)
    for k, ext in (("pro", ".kicad_pro"), ("sch", ".kicad_sch"), ("pcb", ".kicad_pcb")):
        if kf[k] is None:
            chk.fail(f"PCB/ has no {ext}")
    if not find_one(ctx.p("Firmware"), "keyboard.json"):
        chk.fail("Firmware/ has no keyboard.json")
    for f in ("production/gerbers.zip", "production/firmware.uf2"):
        if not ctx.p(f).is_file():
            chk.fail(f"{f} missing")
        else:
            chk.hash(ctx.p(f))
    parts = [p for p in (ctx.p("production").glob("*") if ctx.p("production").is_dir() else [])
             if p.suffix.lower() in (".step", ".stp", ".stl")]
    for n in PARTS:
        st = ctx.p(f"production/{n}.step")
        if not ctx.p(f"production/{n}.stl").is_file():
            chk.fail(f"production/{n}.stl missing")
        if not st.is_file():
            chk.fail(f"production/{n}.step missing")
        elif not st.read_bytes()[:12].startswith(b"ISO-10303-21"):
            chk.fail(f"production/{n}.step is not a STEP file")
    for p in cad + parts:
        chk.hash(p)
    readme = ctx.p("README.md")
    if not readme.is_file():
        chk.fail("README.md missing")
        return chk
    txt = chk.read(readme)
    imgs = []
    for m in IMG_RE.finditer(txt):
        alt, src = (m.group(1) or ""), (m.group(2) or m.group(3))
        imgs.append((alt, src))
        if not re.match(r"https?://", src) and not (r / src.split("#")[0]).is_file():
            chk.fail(f"README image link does not resolve: {src}")
    chk.details["images"] = [{"alt": a, "src": s} for a, s in imgs]
    for need, pat in (("whole hackpad render", r"render|hackpad|frostbite|assembly|overview"),
                      ("schematic", r"schematic|sch"), ("PCB", r"pcb|board|layout"),
                      ("case fit", r"case|fit|exploded|cad")):
        if not any(re.search(pat, a + " " + s, re.I) for a, s in imgs):
            chk.fail(f"README has no image for the {need} (alt text or path matching /{pat}/)")
    bom = re.search(r"^#+\s*(BOM|Bill of materials)\b.*$", txt, re.I | re.M)
    if not bom:
        chk.fail("README has no 'BOM' / 'Bill of Materials' heading")
    else:
        after = txt[bom.end():]
        nxt = re.search(r"^#+\s", after, re.M)
        sect = after[:nxt.start()] if nxt else after
        if not re.search(r"^\s*\|.*\|\s*$\n^\s*\|[\s:|-]+\|\s*$", sect, re.M):
            chk.fail("README BOM section has no markdown table")
    return chk


# ================================================================ cross-consistency

def load_cad_positions(ctx: Ctx, chk: Check):
    for rel in ("CAD/positions.json", "production/positions.json", "CAD/build/positions.json"):
        p = ctx.p(rel)
        if p.is_file():
            try:
                return json.loads(chk.read(p)), rel
            except json.JSONDecodeError as e:
                chk.fail(f"{rel} is not valid JSON: {e}")
    return None, None


def x_cross_positions(ctx: Ctx) -> Check:
    chk = Check(ctx, "X.cross_positions", "X", "design.json vs PCB vs CAD: keys, encoder, OLED, USB")
    d = design(chk)
    if d is None:
        return chk
    ran = []
    # design <-> PCB
    meas = ctx.cache.get("pcb_meas")
    if meas is None:
        pcb, _ = _pcb(Check(ctx, "_tmp", "X", ""))
        if pcb is not None:
            sub = Check(ctx, "_tmp", "X", "")
            meas = pcb_positions(sub, d, pcb)
            for f in sub.failures:
                chk.fail("PCB: " + f)
            chk.inputs.update(sub.inputs)
    else:
        g3 = ctx.cache.get("G3.positions_failures", [])
        for f in g3:
            chk.fail("PCB: " + f)
    if meas:
        ran.append("design<->PCB")
        chk.details["pcb"] = {k: [round(v[0], 3), round(v[1], 3)] for k, v in meas.items()}
    # design <-> CAD positions file
    cp, rel = load_cad_positions(ctx, chk)
    if cp is not None:
        ran.append(f"design<->{rel}")
        for k in d["keys"]:
            got = next((e for e in cp.get("keys", []) if e.get("ref") == k["ref"] or e.get("id") == k["id"]), None)
            if got is None:
                chk.fail(f"{rel}: no entry for {k['ref']}")
            elif abs(got["x"] - k["x"]) > CAD_POS_TOL or abs(got["y"] - k["y"]) > CAD_POS_TOL:
                chk.fail(f"{rel}: {k['ref']} at ({got['x']}, {got['y']}), design ({k['x']}, {k['y']})")
        e = cp.get("encoder")
        if e is None:
            chk.fail(f"{rel}: no encoder entry")
        elif abs(e["x"] - d["encoder"]["x"]) > CAD_POS_TOL or abs(e["y"] - d["encoder"]["y"]) > CAD_POS_TOL:
            chk.fail(f"{rel}: encoder at ({e['x']}, {e['y']}), design ({d['encoder']['x']}, {d['encoder']['y']})")
        u = cp.get("usb_cutout")
        xc = d["mcu"]["rect"]["x"] + d["mcu"]["rect"]["w"] / 2
        du = d["case"].get("usb_cutout", {})
        if u is None:
            chk.fail(f"{rel}: no usb_cutout entry")
        else:
            if abs(u["x"] - xc) > CAD_POS_TOL:
                chk.fail(f"{rel}: usb_cutout centre x {u['x']} != XIAO centre x {xc}")
            for k in ("w", "h"):
                if k in du and (u.get(k) is None or u[k] < du[k] - 1e-9):
                    chk.fail(f"{rel}: usb_cutout {k} {u.get(k)} < design.json case.usb_cutout.{k} {du[k]}")
        ds = (d["case"].get("screws") or {}).get("positions")
        if ds is not None:
            cs = cp.get("screws")
            got = sorted((round(s["x"], 3), round(s["y"], 3)) for s in cs) if isinstance(cs, list) else None
            want = sorted((round(s["x"], 3), round(s["y"], 3)) for s in ds)
            if got is None or len(got) != len(want) or any(math.dist(a, b) > CAD_POS_TOL for a, b in zip(got, want)):
                chk.fail(f"{rel}: screws {got} != design.json case.screws {want}")
        w = cp.get("oled_window")
        ow = d["oled"]["window"]
        if w is None:
            chk.fail(f"{rel}: no oled_window entry")
        elif any(abs(w[k] - ow[k]) > CAD_POS_TOL for k in ("x", "y", "w", "h")):
            chk.fail(f"{rel}: oled_window {w} != design {ow}")
    # design <-> what the Top mesh really is (registered from its outline; no positions file involved)
    if top_stl(ctx):
        M = top_model(chk, d)
        if M is not None:
            ran.append("design<->Top STL")
            meas = {}
            for i, sc in enumerate((d["case"].get("screws") or {}).get("positions", [])):
                op = M.opening_at(sc["x"], sc["y"], M.hmax - 0.05)
                if op is None:
                    chk.fail(f"Top STL: no insert hole at design screw {i} ({sc['x']}, {sc['y']})")
                    continue
                b = op.bounds
                cx, cy, w = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2, b[2] - b[0]
                meas[f"screw{i}"] = {"centre": [round(cx, 3), round(cy, 3)], "d": round(w, 3)}
                if abs(cx - sc["x"]) > CAD_POS_TOL or abs(cy - sc["y"]) > CAD_POS_TOL:
                    chk.fail(f"Top STL: insert hole {i} at ({cx:.3f}, {cy:.3f}), design ({sc['x']}, {sc['y']})")
                if abs(w - INSERT_HOLE) > INSERT_HOLE_TOL:
                    chk.fail(f"Top STL: insert hole {i} is {w:.3f} mm, want {INSERT_HOLE} +/-{INSERT_HOLE_TOL}")
            du = d["case"].get("usb_cutout")
            if du:
                xc = d["mcu"]["rect"]["x"] + d["mcu"]["rect"]["w"] / 2
                z = -(1.2 + 3.26 / 2)            # receptacle centre below the PCB underside (XIAO 1.2 + shell 3.26 / 2)
                h = heights(d)["pcb_under"] - z
                spans = [M.spans(xc, y, "x", h, h + 0.001) for y in USB_WALL_Y]
                if any(not q for q in spans):
                    chk.fail(f"Top STL: back wall is solid at the USB receptacle (x {xc}, depth {h:.2f} mm)")
                else:
                    a, b = max(q[0][0] for q in spans), min(q[0][1] for q in spans)
                    meas["usb_width"] = round(b - a, 3)
                    meas["usb_centre_x"] = round((a + b) / 2, 3)
                    if b - a < du["w"] - 1e-3:
                        chk.fail(f"Top STL: USB opening {b - a:.3f} mm wide through the wall, design.json needs {du['w']}")
                    if abs((a + b) / 2 - xc) > CAD_POS_TOL:
                        chk.fail(f"Top STL: USB opening centred at x {(a + b) / 2:.3f}, XIAO at {xc}")
            chk.details["top_measured"] = meas
    chk.details["comparisons_run"] = ran
    if not ran:
        chk.not_run("no PCB, no CAD positions file and no Top STL to compare with design.json")
    return chk


# ================================================================ PCB path into the Top

def x_pcb_insertion(ctx: Ctx) -> Check:
    chk = Check(ctx, "X.pcb_insertion", "X", "PCB envelope (design.json pcb + tolerance) swept from the skirt rim to its seat through Top.stl")
    d = design(chk)
    if d is None:
        return chk
    M = top_model(chk, d)
    if M is None:
        return chk
    import shapely.geometry as g
    tol = d["case"]["tolerance"]
    W, H = d["pcb"]["w"], d["pcb"]["h"]
    env = g.box(-tol, -tol, W + tol, H + tol)
    seat = heights(d)["pcb_top"]
    vol, rows, worst = 0.0, [], None
    for s in M.slabs_between(seat, M.hmax):
        ov = s["mat"].intersection(env)
        dv = ov.area * (s["h1"] - s["h0"])
        vol += dv
        rows.append({"depth_mm": [s["h0"], s["h1"]], "overlap_mm2": round(ov.area, 4)})
        if ov.area > 0 and (worst is None or ov.area > worst[0]):
            worst = (ov.area, [round(v, 2) for v in ov.bounds], [s["h0"], s["h1"]])
    chk.details.update({"envelope": [-tol, -tol, W + tol, H + tol], "sweep_from_depth": M.hmax, "seat_depth": seat,
                        "slabs": rows, "swept_overlap_mm3": round(vol, 4)})
    if vol > SWEEP_LIMIT:
        chk.fail(f"PCB cannot reach its seat: {vol:.2f} mm3 of Top inside the {W + 2 * tol:.2f} x {H + 2 * tol:.2f} envelope "
                 f"on the way in; worst {worst[0]:.2f} mm2 at depth {worst[2]} mm, bounds {worst[1]}")
    return chk


# ================================================================ USB IDs

def x_usb_ids(ctx: Ctx) -> Check:
    chk = Check(ctx, "X.usb_ids", "X", "Host VID/PID filter = keyboard.json usb = design.json firmware.usb, and enforced when opening")
    d = design(chk)
    kb, _ = keyboard_json(chk)
    dev = ctx.p("host/frostbite_host/device.py")
    if d is None or kb is None:
        return chk
    if not dev.is_file():
        return chk.not_run("host/frostbite_host/device.py missing")
    usb = (d.get("firmware") or {}).get("usb")
    if not usb:
        chk.fail("design.json has no firmware.usb")
        return chk
    want = (int(usb["vid"], 0), int(usb["pid"], 0))
    fw = (int(kb["usb"]["vid"], 0), int(kb["usb"]["pid"], 0))
    if fw != want:
        chk.fail(f"keyboard.json usb {fw[0]:#06x}:{fw[1]:#06x} != design.json firmware.usb {want[0]:#06x}:{want[1]:#06x}")
    for f in find_one(ctx.p("host/frostbite_host"), "*.py"):
        chk.hash(f)
        if f.name != "device.py" and re.search(r"^\s*(import\s+hid|from\s+hid\b)", f.read_text(), re.M):
            chk.fail(f"{f.name} imports hid directly: every open must go through the filtered HidTransport")
    rh = d["firmware"]["raw_hid"]
    code, so, se = chk.run([Path(__file__).resolve().parents[1] / ".venv/bin/python", "-I", Path(__file__).with_name("probe_usb.py"),
                            ctx.p("host"), usb["vid"], usb["pid"], rh["usage_page"], rh["usage"]], timeout=60,
                           env={"PYTHONDONTWRITEBYTECODE": "1"})
    if code != 0:
        chk.fail(f"probe of the host's device code exited {code}")
        return chk
    r = json.loads(so.strip().splitlines()[-1])
    chk.details.update(r)
    host = (r["vendor_id"], r["product_id"])
    if host != want:
        chk.fail(f"host VENDOR_ID/PRODUCT_ID {host} != design.json {want}")
    for name, sc in r["scenes"].items():
        if sc["opened"] != sc["want"]:
            chk.fail(f"host opened {sc['opened']} in scene '{name}', must open {sc['want']}")
    return chk


# ================================================================ GND thermal relief

def pad_outline(p):
    """True copper outline of a pad (rect-family pads are treated as plain rectangles)."""
    import shapely.geometry as g
    from shapely import affinity
    cx, cy, w, h = p["cx"], p["cy"], p["w"], p["h"]
    if p["shape"] == "circle":
        return g.Point(cx, cy).buffer(w / 2, 32)
    if p["shape"] == "oval":
        r = min(w, h) / 2
        dx, dy = (w / 2 - r, 0) if w >= h else (0, h / 2 - r)
        sh = g.LineString([(cx - dx, cy - dy), (cx + dx, cy + dy)]).buffer(r, 32)
    else:
        sh = g.box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    return affinity.rotate(sh, p["angle"], origin=(cx, cy))   # shapely is CCW on a y-up plot, KiCad CCW on y-down


THERMAL_RING = 0.15
THERMAL_MAX_COPPER = 0.45     # thermal pads measured 11-30 %, solid 49-100 % (docs/audit/pcb-physical.md M1, M2)


def g3_gnd_thermal(ctx: Ctx) -> Check:
    chk = Check(ctx, "G3.gnd_thermal", "G3", "GND pads: no solid zone override, thermal relief in the file and in the poured copper")
    pcb, path = _pcb(chk)
    if pcb is None:
        return chk
    import shapely
    import shapely.ops as o
    import shapely.geometry as g
    zones = [z for z in pcb["zones"] if z["net"] and norm_net(z["net"]) == "GND" and not z["keepout"]]
    if not zones:
        return chk.not_run("no GND zones in the .kicad_pcb")
    for z in zones:
        if z["connect"] != "thermal":
            chk.fail(f"GND zone on {z['layers']}: pad connection is '{z['connect']}', must be thermal relief")
    for dru in find_one(ctx.p("PCB"), "*.kicad_dru"):
        for line in chk.read(dru).splitlines():
            if not line.lstrip().startswith("#") and re.search(r"constraint\s+zone_connection\s+solid", line):
                chk.fail(f"{dru.name}: rule forces solid zone connection: {line.strip()}")
    fill = {}
    for z in zones:
        for f in z["fills"]:
            if len(f["pts"]) >= 3:
                fill.setdefault(f["layer"], []).append(shapely.make_valid(g.Polygon(f["pts"])))
    fill = {k: o.unary_union(v) for k, v in fill.items()}
    if not fill:
        chk.fail("GND zones are not filled: relief cannot be measured")
    rows = []
    for f in pcb["footprints"]:
        for p in f["pads"]:
            if norm_net(p["net"]) != "GND":
                continue
            name = f"{f['ref']} pad {p['num']}"
            if p["zone_connect"] not in (None, 1):
                chk.fail(f"{name}: zone_connect {p['zone_connect']} override (2 = solid), must inherit thermal")
            if f.get("zone_connect") not in (None, 1):
                chk.fail(f"{name}: footprint zone_connect {f['zone_connect']} override")
            ring = pad_outline(p).buffer(THERMAL_RING).exterior
            for lay, cu in fill.items():
                if not any(l == lay or l == "*.Cu" or l == "F&B.Cu" for l in p["layers"]):
                    continue
                frac = ring.intersection(cu).length / ring.length
                rows.append({"pad": name, "layer": lay, "ring_copper": round(frac, 3)})
                if frac > THERMAL_MAX_COPPER:
                    chk.fail(f"{name} on {lay}: {frac:.0%} of the ring around the pad is pour, no working thermal relief "
                             f"(max {THERMAL_MAX_COPPER:.0%})")
    if not rows:
        chk.fail("no GND pad measured against a GND pour")
    chk.details["pads_measured"] = len(rows)
    chk.details["worst"] = sorted(rows, key=lambda r: -r["ring_copper"])[:8]
    return chk


# ================================================================ bosses vs bottom pads

BOSS_CLEARANCE = 0.5
KICAD_PY = Path.home() / "Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3"


def pad_on_bottom(p) -> bool:
    return any(l in ("B.Cu", "*.Cu", "F&B.Cu") for l in p.get("layers", []))


def circle_rect_gap(cx, cy, r, x0, y0, x1, y1) -> float:
    dx = max(x0 - cx, 0.0, cx - x1)
    dy = max(y0 - cy, 0.0, cy - y1)
    return math.hypot(dx, dy) - r


def parser_bottom_pads(pcb) -> list[dict]:
    """Bottom-copper pad bboxes from our own .kicad_pcb parse, in design coordinates (Edge.Cuts top-left)."""
    o = pcb_origin(pcb)
    out = []
    for f in pcb["footprints"]:
        for p in f["pads"]:
            if not pad_on_bottom(p):
                continue
            out.append({"ref": f["ref"], "pad": p["num"], "x0": p["x"] - p["hw"] - o["x0"], "y0": p["y"] - p["hh"] - o["y0"],
                        "x1": p["x"] + p["hw"] - o["x0"], "y1": p["y"] + p["hh"] - o["y0"], "shape": p["shape"]})
    return out


def x_boss_vs_pads(ctx: Ctx) -> Check:
    chk = Check(ctx, "X.boss_vs_pads", "X", f"Case insert bosses (design.json case.screws) >= {BOSS_CLEARANCE} mm from every bottom-side pad")
    d = design(chk)
    if d is None:
        return chk
    sc = (d.get("case") or {}).get("screws")
    if not sc or "positions" not in sc or "boss_od" not in sc:
        chk.fail("design.json case.screws.positions / boss_od missing")
        return chk
    r = sc["boss_od"] / 2
    bosses = [(s["x"], s["y"]) for s in sc["positions"]]
    pcb, pcb_path = _pcb(chk)
    if pcb is None:
        return chk
    sources = {}
    # source 1: PCB/build/bottom_pads.json (pcbnew export), regenerated into verify/.cache if missing or stale
    bp = ctx.p("PCB/build/bottom_pads.json")
    fresh = bp.is_file() and bp.stat().st_mtime >= pcb_path.stat().st_mtime
    if not fresh:
        tool = ctx.p("PCB/tools/export_bottom_pads.py")
        why = "missing" if not bp.is_file() else "older than the .kicad_pcb"
        if ctx.allow_regen and tool.is_file() and KICAD_PY.is_file():
            out = ctx.work / "bottom_pads.json"
            chk.hash(tool)
            code, so, se = chk.run([KICAD_PY, tool, pcb_path, out], timeout=300)
            if code != 0 or not out.is_file():
                chk.fail(f"export_bottom_pads.py exited {code} (bottom_pads.json was {why})")
            else:
                chk.note(f"PCB/build/bottom_pads.json was {why}; regenerated into {out}")
                bp, fresh = out, True
        else:
            chk.note(f"PCB/build/bottom_pads.json {why} and could not be regenerated (KiCad python or tool missing); "
                     "using the parsed .kicad_pcb only")
    if fresh:
        try:
            sources[bp.name if bp.parent == ctx.work else "PCB/build/bottom_pads.json"] = json.loads(chk.read(bp))["pads"]
        except (json.JSONDecodeError, KeyError) as e:
            chk.fail(f"{bp}: unreadable ({e})")
    # source 2: independent parse of the .kicad_pcb
    sources["parsed .kicad_pcb"] = parser_bottom_pads(pcb)
    cp, rel = load_cad_positions(ctx, chk)
    boss_sets = {"design.json": bosses}
    if cp is not None and isinstance(cp.get("screws"), list):
        boss_sets[rel] = [(s["x"], s["y"]) for s in cp["screws"]]
    worst = {}
    for bname, bl in boss_sets.items():
        for src, pads in sources.items():
            hits = []
            for i, (bx, by) in enumerate(bl):
                for p in pads:
                    g = circle_rect_gap(bx, by, r, p["x0"], p["y0"], p["x1"], p["y1"])
                    key = f"{bname} boss {i} ({bx}, {by}) vs {src}"
                    if key not in worst or g < worst[key][0]:
                        worst[key] = (round(g, 3), f"{p['ref']} pad {p['pad']}")
                    if g < BOSS_CLEARANCE:
                        hits.append((g, i, p))
            for g, i, p in sorted(hits, key=lambda h: h[0])[:20]:
                chk.fail(f"[{bname} vs {src}] boss {i} at ({bl[i][0]}, {bl[i][1]}) OD {sc['boss_od']} is {g:.3f} mm from "
                         f"{p['ref']} pad {p['pad']} [{p['x0']:.3f},{p['y0']:.3f} - {p['x1']:.3f},{p['y1']:.3f}] (min {BOSS_CLEARANCE})")
    for src, pads in sources.items():
        chk.details[f"pads_{src}"] = len(pads)
    chk.details["closest_pad_per_boss"] = worst
    if len(sources) == 2:
        a, b = list(sources.values())
        unc = [f"{q['ref']} pad {q['pad']}" for q in a
               if not any(p["ref"] == q["ref"] and p["x0"] <= q["x0"] + 0.005 and p["y0"] <= q["y0"] + 0.005
                          and p["x1"] >= q["x1"] - 0.005 and p["y1"] >= q["y1"] - 0.005 for p in b)]
        chk.details["json_pads_not_inside_parsed_bbox"] = unc[:30]
        if unc:
            chk.note(f"{len(unc)} pads in bottom_pads.json are not inside the parsed pad boxes (sources disagree)")
    # CAD positions must use the same screw positions
    if cp is not None:
        cs = cp.get("screws")
        if not isinstance(cs, list):
            chk.fail(f"{rel}: no screws list")
        else:
            got = sorted((round(s["x"], 3), round(s["y"], 3)) for s in cs)
            want = sorted((round(x, 3), round(y, 3)) for x, y in bosses)
            if len(got) != len(want) or any(math.dist(a, b) > CAD_POS_TOL for a, b in zip(got, want)):
                chk.fail(f"{rel}: screws {got} != design.json case.screws {want} (tol {CAD_POS_TOL})")
    return chk
