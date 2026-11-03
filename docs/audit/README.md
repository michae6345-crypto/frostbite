# Design audits

Independent reviews of Frostbite, written before the fix round. Each report records the state of the
design at the time, so it is a record, not current status. `verify/REPORT.md` is current status.

| Report | Area |
|---|---|
| electrical.md | Pinouts, LED chain, power, matrix |
| pcb-physical.md | Part collisions, fabrication, hand soldering |
| firmware.md | QMK behaviour, host-simulated |
| case.md | Print, fit and assembly order |
| hackpad-rules.md | Hackpad requirements and lessons from other builds |
| host.md | Laptop companion |

`host-tests/` is the audit's test kit. Its findings tests moved to `host/tests/test_audit_findings.py` and now
pass there, so running the kit here reports strict XPASS failures; that's expected. `test_audit_protocol.py`
still runs through `verify/run.sh`, which patches a private copy of its stub.
