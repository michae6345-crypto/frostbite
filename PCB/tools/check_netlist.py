"""Diff the KiCad netlist (kicad-cli sch export netlist --format kicadsexpr) against design.json
and the compiled firmware's keyboard.json.  Exit 1 on any mismatch.

usage: python3 PCB/tools/check_netlist.py [path/to/frostbite.net]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sexp import find, find1, parse  # noqa: E402

PCB = Path(__file__).resolve().parents[1]
ROOT = PCB.parent
design = json.loads((ROOT / "design.json").read_text())
kb = json.loads((ROOT / "Firmware/qmk/keyboards/frostbite/keyboard.json").read_text())

net_path = Path(sys.argv[1]) if len(sys.argv) > 1 else PCB / "build/frostbite.net"
nl = parse(net_path.read_text())

actual: dict[str, set] = {}
for net in find(find1(nl, "nets"), "net"):
    name = str(find1(net, "name")[1])
    actual[name] = {(str(find1(n, "ref")[1]), str(find1(n, "pin")[1])) for n in find(net, "node")}

comps = {str(find1(c, "ref")[1]): str(find1(c, "footprint")[1]) for c in find(find1(nl, "components"), "comp")}

# ---------------------------------------------------------------- expected, from design.json only
exp: dict[str, set] = {}


def add(net, ref, pin):
    exp.setdefault(net, set()).add((ref, pin))


for p in design["pins"]:
    add(p["net"], "U1", str(int(p["xiao"][1:]) + 1))          # XIAO pad n+1 = Dn
add("+3V3", "U1", "12"); add("GND", "U1", "13"); add("+5V", "U1", "14")
vcc = {"GND": "GND", "VCC": "+3V3", "SCL": "SCL", "SDA": "SDA"}
for i, name in enumerate(design["oled"]["header"]["pins_top_to_bottom"]):
    add(vcc[name], "J1", str(i + 1))
add("ENC_A", "ENC1", "A"); add("ENC_B", "ENC1", "B"); add("GND", "ENC1", "C"); add("GND", "ENC1", "MP")
for k, key in enumerate(design["keys"], start=1):
    assert key["ref"] == f"SW{k}"
    add(f"COL{key['col']}", f"SW{k}", "1")
    add(f"SW{k}_D", f"SW{k}", "2")
    add(f"SW{k}_D", f"D{k}", "2")          # anode toward the switch
    add(f"ROW{key['row']}", f"D{k}", "1")  # cathode toward the row (COL2ROW)
n = design["leds"]["count"]
for i in range(n):
    ref = f"LED{i + 1}"
    add("+5V", ref, "1"); add("GND", ref, "3")
    add("LED_DIN" if i == 0 else f"LED_D{i}", ref, "4")
    if i < n - 1:
        add(f"LED_D{i + 1}", ref, "2")

errors = []
# Unnamed single-pin nets ("unconnected-(...)") are the no-connect pins; ignore them.
act = {k: v for k, v in actual.items() if not k.startswith("unconnected-")}
for name in sorted(set(exp) | set(act)):
    if exp.get(name) != act.get(name):
        errors.append(f"net {name}: expected {sorted(exp.get(name, []))} got {sorted(act.get(name, []))}")
nc = sorted(p for k, v in actual.items() if k.startswith("unconnected-") for p in v)
if nc != sorted([("ENC1", "S1"), ("ENC1", "S2"), (f"LED{n}", "2")]):
    errors.append(f"unexpected unconnected pins {nc}")

# ---------------------------------------------------------------- refs and footprints
want_refs = {"U1", "J1", "ENC1"} | {f"SW{k}" for k in range(1, 10)} | {f"D{k}" for k in range(1, 10)} \
    | {f"LED{k}" for k in range(1, n + 1)}
if set(comps) != want_refs:
    errors.append(f"refs differ: missing {want_refs - set(comps)}, extra {set(comps) - want_refs}")

# ---------------------------------------------------------------- firmware (keyboard.json) agreement
gp = {p["gpio"]: p["net"] for p in design["pins"]}
mp = kb["matrix_pins"]
if [gp[g] for g in mp["cols"]] != ["COL0", "COL1", "COL2"]:
    errors.append(f"firmware cols {mp['cols']} -> {[gp.get(g) for g in mp['cols']]}")
if [gp[g] for g in mp["rows"]] != ["ROW0", "ROW1", "ROW2"]:
    errors.append(f"firmware rows {mp['rows']} -> {[gp.get(g) for g in mp['rows']]}")
if kb["diode_direction"] != design["matrix"]["diode_direction"]:
    errors.append("diode direction differs")
enc = kb["encoder"]["rotary"][0]
if (gp[enc["pin_a"]], gp[enc["pin_b"]]) != ("ENC_A", "ENC_B"):
    errors.append(f"firmware encoder pins {enc}")
if gp[kb["ws2812"]["pin"]] != "LED_DIN":
    errors.append(f"firmware ws2812 pin {kb['ws2812']['pin']}")
layout = kb["rgb_matrix"]["layout"]
if len(layout) != n:
    errors.append(f"firmware rgb_matrix has {len(layout)} LEDs, design {n}")
for key in design["keys"]:
    entry = layout[key["led"]]
    if entry.get("matrix") != [key["row"], key["col"]]:
        errors.append(f"rgb_matrix[{key['led']}] = {entry.get('matrix')} but {key['ref']} is {[key['row'], key['col']]}")
for g in design["leds"]["glow"]:
    if "matrix" in layout[g["led"]]:
        errors.append(f"rgb_matrix[{g['led']}] should be a glow LED")

print(f"netlist: {len(act)} named nets, {sum(len(v) for v in act.values())} pins, {len(comps)} components")
if errors:
    print("MISMATCH:")
    for e in errors:
        print("  " + e)
    sys.exit(1)
print("netlist matches design.json and keyboard.json: 0 differences")
