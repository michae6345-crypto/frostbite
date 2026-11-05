"""Damage a real printed part and write it over production/<part>.stl, so the self-test faults real geometry.
Run with CAD/.venv's python on a self-test copy: probe_fault.py <project root> <fault>"""
import sys
from pathlib import Path

import cadquery as cq

root, fault = Path(sys.argv[1]), sys.argv[2]
sys.path.insert(0, str(root / "CAD"))
import frostbite_case as fc  # noqa: E402

sx, sy = fc.SCREWS[0]
bottom, top = fc.solid(fc.make_bottom()), fc.solid(fc.make_top())
if fault == "plug_insert":           # one insert hole filled: the corner is solid down to the Ø3.4 hole
    name, s = "Bottom", bottom.fuse(fc.solid(fc.cyl(sx, sy, fc.INSERT_HOLE / 2 + 0.1, fc.RIM - fc.INSERT_DEPTH, fc.RIM)))
elif fault == "close_notch":         # the back wall of the Bottom as if it had no notch
    w = fc.UC["w"] / 2 + 0.1
    name, s = "Bottom", bottom.fuse(fc.solid(fc.box(fc.USB_CX - w, fc.USB_CX + w, -fc.MARGIN_Y, -fc.TOL,
                                                    fc.USB_CZ - fc.UC["h"] / 2 - 0.1, fc.RIM)))
elif fault == "move_top_hole":       # one Ø3.4 hole 0.5 off the design axis
    plate = fc.solid(fc.cyl(sx, sy, fc.SCREW_CLR / 2 + 0.1, fc.PLATE_UNDER, fc.PLATE_TOP))
    name, s = "Top", top.fuse(plate).cut(fc.solid(fc.cyl(sx + 0.5, sy, fc.SCREW_CLR / 2, fc.PLATE_UNDER - 1, fc.PLATE_TOP + 1)))
else:
    sys.exit(f"unknown fault {fault}")
cq.exporters.export(fc.print_orient(name, s.clean()), str(root / "production" / f"{name}.stl"), tolerance=0.01, angularTolerance=0.1)
