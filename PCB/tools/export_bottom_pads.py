"""Write PCB/build/bottom_pads.json: every pad that has copper on B.Cu, in design.json coordinates.

The case uses it to keep screw-insert bosses and other parts clear of solder joints on the underside.
Run with KiCad's bundled Python: <KiCad.app>/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
"""
import json
import os
import sys

import pcbnew

here = os.path.dirname(os.path.abspath(__file__))
pcb_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "frostbite.kicad_pcb")
out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "..", "build", "bottom_pads.json")

board = pcbnew.LoadBoard(pcb_path)
edges = board.GetBoardEdgesBoundingBox()
# Edge.Cuts line width (0.1 mm) widens the bounding box by half a width on each side.
ox = pcbnew.ToMM(edges.GetX()) + 0.05
oy = pcbnew.ToMM(edges.GetY()) + 0.05

pads = []
for fp in board.GetFootprints():
    for pad in fp.Pads():
        if not pad.IsOnLayer(pcbnew.B_Cu):
            continue
        r = pad.GetBoundingBox()
        pads.append({
            "ref": fp.GetReference(),
            "pad": pad.GetNumber(),
            "through_hole": pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH,
            "x0": round(pcbnew.ToMM(r.GetLeft()) - ox, 3),
            "y0": round(pcbnew.ToMM(r.GetTop()) - oy, 3),
            "x1": round(pcbnew.ToMM(r.GetRight()) - ox, 3),
            "y1": round(pcbnew.ToMM(r.GetBottom()) - oy, 3),
        })

os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w") as f:
    json.dump({"source": os.path.basename(pcb_path), "units": "mm", "origin": "PCB top-left (design.json)", "pads": pads}, f, indent=1)
print(f"{len(pads)} bottom pads -> {out_path}")
