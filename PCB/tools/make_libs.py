"""Derive project-local library files from the Hack Club care package in lib/.

* lib/frostbite.pretty/SK6812MINI-E_key.kicad_mod: care-package SK6812MINI-E_fixed with pads
  pulled 0.3 mm clear of the LED cut-out (JLCPCB copper-to-edge rule).
* lib/frostbite.pretty/EC11E-Switch_Vertical_H20mm_Slot3.4x1.5.kicad_mod: KiCad's slotted EC11E
  footprint with slots that pass JLCPCB's 2:1 rule.
* lib/frostbite.pretty/SK6812MINI-E_glow_down.kicad_mod: the same, with its copper/mask/paste/
  silk/courtyard moved from B.* to F.*.  Placed and flipped to the bottom side in pcbnew, it is a
  MINI-E soldered on the underside with its lens facing DOWN (away from the PCB) and its back in
  the same board cut-out: the mirror image of the per-key (lens-up) pin arrangement, as it must be.
* sym-lib-table / fp-lib-table for the project.
"""
from pathlib import Path

PCB = Path(__file__).resolve().parents[1]
src = (PCB / "lib/hackpad.pretty/SK6812MINI-E_fixed.kicad_mod").read_text()


def derive(name, descr, front_layers):
    """Copy of the care-package MINI-E footprint with the pads moved 0.175 mm outward and
    shortened on the inside (centre +-2.775, length 1.25: copper 2.15..3.40 from the centre, the
    same outer edge as the care package) so copper stays >= 0.3 mm from the routed LED cut-out
    (the original pads come within 0.1 mm of it).  Courtyard tightened to cut-out/pads + 0.25."""
    out = src.replace('(footprint "SK6812-rounded"', f'(footprint "{name}"')
    out = out.replace("(at -2.599999 ", "(at -2.775 ").replace("(at 2.600001 ", "(at 2.775 ")
    out = out.replace("(size 0.82 1.6)", "(size 0.82 1.25)")
    for a_, b_ in [("-3.799999", "-3.65"), ("3.800001", "3.65"), ("-2.102842", "-2.04"), ("1.897158", "1.83")]:
        out = out.replace(a_, b_)
    if front_layers:
        for a_, b_ in [('"B.Cu"', '"F.Cu"'), ('"B.Mask"', '"F.Mask"'), ('"B.Paste"', '"F.Paste"'),
                       ('"B.SilkS"', '"F.SilkS"'), ('"B.CrtYd"', '"F.CrtYd"')]:
            out = out.replace(a_, b_)
        out = out.replace("(justify mirror)", "")
    out = out.replace("Add-on for regular MX-footprints with SK6812 MINI-E", descr)
    (PCB / "lib/frostbite.pretty" / f"{name}.kicad_mod").write_text(out)


(PCB / "lib/frostbite.pretty").mkdir(exist_ok=True)
derive("SK6812MINI-E_key",
       "Per-key SK6812 MINI-E, reverse mounted on the underside, lens up through the cut-out (from Hack Club SK6812MINI-E_fixed, pads 0.3 mm clear of the cut-out)",
       front_layers=False)
# Glow LEDs: same part on the underside but lens facing DOWN, back of the body in the cut-out.
# Defined with F.* layers so that pcbnew's flip to the bottom puts the pads on B.Cu in the
# mirrored (lens-down) arrangement and the footprint reports side = bottom.
derive("SK6812MINI-E_glow_down",
       "SK6812 MINI-E on the underside, lens facing down (from Hack Club SK6812MINI-E_fixed; place flipped on B.Cu)",
       front_layers=True)

# EC11E with switch: KiCad's slotted footprint with the lug slots lengthened from 2.8 x 1.5 to
# 3.4 x 1.5 mm.  Lug centres stay at +-5.6, so the slot's outer edge stays at 6.35 (Alps: 6.25, barb
# tip: 6.55) and the barb still catches.  The length meets JLCPCB's "slot length >= 2 x width" rule
# and takes the slot's rounded ends past the 2.5 mm wide lug's corners (see README).
# Pads grow to 4.0 x 2.1 to keep a 0.3 mm annular ring all round.
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
sym = [("XIAO_RP2040", "${KIPRJMOD}/lib/XIAO_RP2040.kicad_sym", "Hack Club care package"),
       ("SK6812MINI-E", "${KIPRJMOD}/lib/SK6812MINI-E.kicad_sym", "Hack Club care package")]
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

# ---------------------------------------------------------------- project file
import json  # noqa: E402

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
                      "min_resolved_spokes": 1,
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
        "netclass_patterns": [{"netclass": "Power", "pattern": p} for p in ("GND", "+5V", "+3V3")],
    },
    "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
    "sheets": [[__import__("uuid").uuid5(__import__("uuid").UUID("6f1c3a52-0b7e-4f1e-9a51-f7057b17e000"), "root").__str__(), "Root"]],
    "text_variables": {},
}
pro_path = PCB / "frostbite.kicad_pro"
if not pro_path.exists():
    pro_path.write_text(json.dumps(pro, indent=2) + "\n")
    print("wrote frostbite.kicad_pro")
else:
    # KiCad rewrites the project file; keep the settings the board depends on.
    cur = json.loads(pro_path.read_text())
    # U1.13 reaches 2 spokes on F.Cu but only 1 on B.Cu; 3 x 0.4 mm spokes carry the 0.48 A worst case.
    cur["board"]["design_settings"]["rules"]["min_resolved_spokes"] = 1
    pro_path.write_text(json.dumps(cur, indent=2) + "\n")
