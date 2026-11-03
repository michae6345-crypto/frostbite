# Frostbite verification report

Generated 2026-11-03T22:16:57+00:00 by `verify/run.sh`. Every row comes from `verify/evidence/<check>.json` (commands, exit codes, output tails, SHA-256 of inputs). NOT_RUN is never a pass.

**PASS 31 · FAIL 0 · NOT_RUN 0** — exit code 0

kicad-cli: `~/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`

## Needs real parts

Green below means the files agree. It does not prove these, and no check here can:

- **OLED flip** (docs/audit/firmware.md F2): FROSTBITE_OLED_FLIP is set from reference boards. Flash ledtest with the OLED fitted and read the text.
- **EC11 resolution** (docs/audit/firmware.md F6, electrical.md E9): Resolution 4 may need two clicks per step on a 30/15 part. Turn the kit encoder in ledtest; direction is open too.
- **Glow brightness** (docs/audit/case.md M2): The light reaching the band is a model and an estimate. Print one corner with one SK6812 and look at it.
- **LED data level** (docs/audit/electrical.md E3): 3.3 V data is below the datasheet VIH of 3.5 V at 5 V. Run the whole chain at full white on the real board.
- **OLED flex clearance** (docs/audit/case.md M3): The module's flex and tape height at the far end is unknown. Caliper the kit module against the lip gap.

## Checks

| Check | Gate | Status | Summary |
|---|---|---|---|
| [`G0.studio_run`](evidence/G0.studio_run.json) | G0 | **PASS** | 1 command(s), 11 input file(s) |
| [`G0.studio_constraints`](evidence/G0.studio_constraints.json) | G0 | **PASS** | 1 command(s), 11 input file(s) |
| [`G0.design_json`](evidence/G0.design_json.json) | G0 | **PASS** | 0 command(s), 1 input file(s) |
| [`G2.firmware_pins`](evidence/G2.firmware_pins.json) | G2 | **PASS** | 0 command(s), 5 input file(s) |
| [`G2.netlist`](evidence/G2.netlist.json) | G2 | **PASS** | 1 command(s), 2 input file(s) |
| [`G2.erc`](evidence/G2.erc.json) | G2 | **PASS** | 1 command(s), 1 input file(s) |
| [`G3.outline_layers`](evidence/G3.outline_layers.json) | G3 | **PASS** | 0 command(s), 2 input file(s) |
| [`G3.positions`](evidence/G3.positions.json) | G3 | **PASS** | 1 command(s), 2 input file(s) |
| [`G3.drc`](evidence/G3.drc.json) | G3 | **PASS** | 1 command(s), 13 input file(s) |
| [`G3.drc_jlcpcb`](evidence/G3.drc_jlcpcb.json) | G3 | **PASS** | 1 command(s), 14 input file(s) |
| [`G3.gerbers_export`](evidence/G3.gerbers_export.json) | G3 | **PASS** | 2 command(s), 2 input file(s) |
| [`G3.gerbers_zip`](evidence/G3.gerbers_zip.json) | G3 | **PASS** | 0 command(s), 2 input file(s) |
| [`G3.gnd_thermal`](evidence/G3.gnd_thermal.json) | G3 | **PASS** | 0 command(s), 2 input file(s) |
| [`G4.check_fit`](evidence/G4.check_fit.json) | G4 | **PASS** | 1 command(s), 3 input file(s) |
| [`G4.stl_mesh`](evidence/G4.stl_mesh.json) | G4 | **PASS** | 0 command(s), 4 input file(s) |
| [`G4.switch_cutouts`](evidence/G4.switch_cutouts.json) | G4 | **PASS** | 0 command(s), 2 input file(s) |
| [`G4.encoder_clearance`](evidence/G4.encoder_clearance.json) | G4 | **PASS** | 0 command(s), 3 input file(s) |
| [`G4.oled_clearance`](evidence/G4.oled_clearance.json) | G4 | **PASS** | 0 command(s), 3 input file(s) |
| [`G5.bom_kit`](evidence/G5.bom_kit.json) | G5 | **PASS** | 0 command(s), 2 input file(s) |
| [`G6.qmk_lint`](evidence/G6.qmk_lint.json) | G6 | **PASS** | 1 command(s), 7 input file(s) |
| [`G6.compile_default`](evidence/G6.compile_default.json) | G6 | **PASS** | 1 command(s), 7 input file(s) |
| [`G6.compile_ledtest`](evidence/G6.compile_ledtest.json) | G6 | **PASS** | 1 command(s), 7 input file(s) |
| [`G6.production_uf2`](evidence/G6.production_uf2.json) | G6 | **PASS** | 0 command(s), 2 input file(s) |
| [`G6.firmware_harness`](evidence/G6.firmware_harness.json) | G6 | **PASS** | 2 command(s), 28 input file(s) |
| [`G6.oled_strip_panel`](evidence/G6.oled_strip_panel.json) | G6 | **PASS** | 0 command(s), 28 input file(s) |
| [`G7.host_tests`](evidence/G7.host_tests.json) | G7 | **PASS** | 2 command(s), 37 input file(s) |
| [`G8.package`](evidence/G8.package.json) | G8 | **PASS** | 0 command(s), 12 input file(s) |
| [`X.cross_positions`](evidence/X.cross_positions.json) | X | **PASS** | 0 command(s), 3 input file(s) |
| [`X.boss_vs_pads`](evidence/X.boss_vs_pads.json) | X | **PASS** | 0 command(s), 4 input file(s) |
| [`X.pcb_insertion`](evidence/X.pcb_insertion.json) | X | **PASS** | 0 command(s), 2 input file(s) |
| [`X.usb_ids`](evidence/X.usb_ids.json) | X | **PASS** | 1 command(s), 11 input file(s) |

## Fix loop

Owner of the failing gate fixes the cause, then rerun `verify/run.sh`. Max 3 rounds per failure, then a human decides (see verify/README.md).
