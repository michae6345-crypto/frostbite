"""Volumes of each production STEP and of the same part rebuilt from the current CAD source and design.json.
Writes nothing. Run with CAD/.venv's python: probe_step.py <project root> <file.step> ..."""
import json
import sys
from pathlib import Path

import cadquery as cq

root = Path(sys.argv[1])
sys.path.insert(0, str(root / "CAD"))
out = {"step": {}, "built": {}}
for p in sys.argv[2:]:
    out["step"][p] = sum(v.Volume() for v in cq.importers.importStep(p).vals())
import frostbite_case as fc  # noqa: E402

for name, wp in fc.build()["parts"].items():
    out["built"][name] = sum(v.Volume() for v in wp.vals()) if hasattr(wp, "vals") else wp.Volume()
print(json.dumps(out))
