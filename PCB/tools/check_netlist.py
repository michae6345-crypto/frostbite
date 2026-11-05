"""Diff a kicadsexpr netlist against design.json and keyboard.json. Exit 1 on any mismatch.

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

# Expected nets, from design.json only
exp: dict[str, set] = {}


def add(net, ref, pin):
    exp.setdefault(net, set()).add((ref, pin))


for p in design["pins"]:
    add(p["net"], "U1", str(int(p["xiao"][1:]) + 1))          # XIAO pad n+1 = Dn
add("+3V3", "U1", "12"); add("GND", "U1", "13")
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

errors = []
# Unnamed "unconnected-(...)" nets are the no-connect pins.
act = {k: v for k, v in actual.items() if not k.startswith("unconnected-")}
for name in sorted(set(exp) | set(act)):
    if exp.get(name) != act.get(name):
        errors.append(f"net {name}: expected {sorted(exp.get(name, []))} got {sorted(act.get(name, []))}")
nc = sorted(p for k, v in actual.items() if k.startswith("unconnected-") for p in v)
if nc != sorted([("ENC1", "S1"), ("ENC1", "S2"), ("U1", "7"), ("U1", "14")]):   # encoder push, XIAO D6, XIAO 5V
    errors.append(f"unexpected unconnected pins {nc}")

want_refs = {"U1", "J1", "ENC1"} | {f"SW{k}" for k in range(1, 10)} | {f"D{k}" for k in range(1, 10)}
if set(comps) != want_refs:
    errors.append(f"refs differ: missing {want_refs - set(comps)}, extra {set(comps) - want_refs}")

# Firmware pins
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

print(f"netlist: {len(act)} named nets, {sum(len(v) for v in act.values())} pins, {len(comps)} components")
if errors:
    print("MISMATCH:")
    for e in errors:
        print("  " + e)
    sys.exit(1)
print("netlist matches design.json and keyboard.json: 0 differences")
