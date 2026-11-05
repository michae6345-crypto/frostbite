"""Write lib/frostbite.pretty (derived EC11E footprint), the lib tables and the project file."""
import json
import uuid
from pathlib import Path

PCB = Path(__file__).resolve().parents[1]
(PCB / "lib/frostbite.pretty").mkdir(exist_ok=True)

# KiCad's slotted EC11E with the lug slots lengthened from 2.8 x 1.5 to 3.4 x 1.5 mm. Lug centres stay
# at +-5.6, so the slot's outer edge stays at 6.35 (Alps: 6.25, barb tip: 6.55) and the barb still
# catches. The length meets JLCPCB's "slot length >= 2 x width" rule and takes the rounded slot ends
# past the 2.5 mm lug's corners (see README). Pads grow to 4.0 x 2.1 to keep a 0.3 mm annular ring.
ENC = Path.home() / ("Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Rotary_Encoder.pretty/"
                     "RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm.kicad_mod")
enc = ENC.read_text()
enc = enc.replace('(footprint "RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm"',
                  '(footprint "EC11E-Switch_Vertical_H20mm_Slot3.4x1.5"', 1)
assert enc.count("(drill oval 2.8 1.5)") == 2 and enc.count("(size 3.2 2)") == 2
enc = enc.replace("(drill oval 2.8 1.5)", "(drill oval 3.4 1.5)").replace("(size 3.2 2)", "(size 4 2.1)")
for old, new in (("5.5 -3.4", "5.2 -3.4"), ("5.5 8.4", "5.2 8.4"), ("9.5 -3.4", "9.8 -3.4"), ("9.5 8.4", "9.8 8.4")):
    enc = enc.replace(old, new)   # body outline silk: stay 0.15 clear of the longer pads
(PCB / "lib/frostbite.pretty/EC11E-Switch_Vertical_H20mm_Slot3.4x1.5.kicad_mod").write_text(enc)

S = "${KICAD10_SYMBOL_DIR}"
F = "${KICAD10_FOOTPRINT_DIR}"
sym = [("XIAO_RP2040", "${KIPRJMOD}/lib/XIAO_RP2040.kicad_sym", "Hack Club care package")]
sym += [(n, f"{S}/{n}.kicad_sym", "KiCad standard") for n in ("Device", "Switch", "Connector_Generic", "power")]
fp = [("hackpad", "${KIPRJMOD}/lib/hackpad.pretty", "Hack Club care package"),
      ("frostbite", "${KIPRJMOD}/lib/frostbite.pretty", "Frostbite derived footprints")]
fp += [(n, f"{F}/{n}.pretty", "KiCad standard") for n in ("Rotary_Encoder", "Diode_THT", "Connector_PinHeader_2.54mm")]


def table(kind, rows):
    body = "\n".join(f'  (lib (name "{n}")(type "KiCad")(uri "{u}")(options "")(descr "{d}"))' for n, u, d in rows)
    return f"({kind}\n  (version 7)\n{body}\n)\n"


(PCB / "sym-lib-table").write_text(table("sym_lib_table", sym))
(PCB / "fp-lib-table").write_text(table("fp_lib_table", fp))
print("libs ok")

POWER_PATTERNS = [{"netclass": "Power", "pattern": p} for p in ("GND", "+3V3")]
pro = {
    "meta": {"filename": "frostbite.kicad_pro", "version": 3},
    "board": {
        "design_settings": {
            "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2,
                         "silk_line_width": 0.15, "silk_text_size_h": 1.0, "silk_text_size_v": 1.0,
                         "silk_text_thickness": 0.15},
            "rules": {"min_clearance": 0.15, "min_track_width": 0.2, "min_via_diameter": 0.6,
                      "min_through_hole_diameter": 0.3, "min_via_annular_width": 0.13,
                      "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
                      "min_copper_edge_clearance": 0.3, "min_silk_clearance": 0.0,
                      "min_resolved_spokes": 2,
                      "min_text_height": 0.8, "min_text_thickness": 0.12,
                      "solder_mask_to_copper_clearance": 0.0},
            "track_widths": [0.0, 0.25, 0.5],
            "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.7, "drill": 0.35}],
        }
    },
    "net_settings": {
        "classes": [
            {"name": "Default", "clearance": 0.2, "track_width": 0.25, "via_diameter": 0.7, "via_drill": 0.35,
             "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.25,
             "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0, "schematic_color": "rgba(0, 0, 0, 0.000)",
             "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647},
            {"name": "Power", "clearance": 0.2, "track_width": 0.5, "via_diameter": 0.8, "via_drill": 0.4,
             "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.25,
             "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0, "schematic_color": "rgba(0, 0, 0, 0.000)",
             "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 0},
        ],
        "meta": {"version": 4},
        "netclass_patterns": POWER_PATTERNS,
    },
    "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
    "sheets": [[str(uuid.uuid5(uuid.UUID("6f1c3a52-0b7e-4f1e-9a51-f7057b17e000"), "root")), "Root"]],
    "text_variables": {},
}
pro_path = PCB / "frostbite.kicad_pro"
if not pro_path.exists():
    pro_path.write_text(json.dumps(pro, indent=2) + "\n")
    print("wrote frostbite.kicad_pro")
else:
    # KiCad rewrites the project file, so reapply the settings this script owns.
    cur = json.loads(pro_path.read_text())
    cur["board"]["design_settings"]["rules"]["min_resolved_spokes"] = 2
    cur["net_settings"]["netclass_patterns"] = POWER_PATTERNS
    pro_path.write_text(json.dumps(cur, indent=2) + "\n")
