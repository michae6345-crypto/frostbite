# Frostbite verification report

Generated 2026-11-03T20:22:28+00:00 by `verify/run.sh`. Every row comes from `verify/evidence/<check>.json` (commands, exit codes, output tails, SHA-256 of inputs). NOT_RUN is never a pass.

**PASS 24 · FAIL 0 · NOT_RUN 0** — exit code 0

kicad-cli: `~/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`

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
| [`G3.drc`](evidence/G3.drc.json) | G3 | **PASS** | 1 command(s), 12 input file(s) |
| [`G3.drc_jlcpcb`](evidence/G3.drc_jlcpcb.json) | G3 | **PASS** | 1 command(s), 13 input file(s) |
| [`G3.gerbers_export`](evidence/G3.gerbers_export.json) | G3 | **PASS** | 2 command(s), 2 input file(s) |
| [`G3.gerbers_zip`](evidence/G3.gerbers_zip.json) | G3 | **PASS** | 0 command(s), 2 input file(s) |
| [`G4.check_fit`](evidence/G4.check_fit.json) | G4 | **PASS** | 1 command(s), 3 input file(s) |
| [`G4.stl_mesh`](evidence/G4.stl_mesh.json) | G4 | **PASS** | 0 command(s), 4 input file(s) |
| [`G4.switch_cutouts`](evidence/G4.switch_cutouts.json) | G4 | **PASS** | 0 command(s), 2 input file(s) |
| [`G5.bom_kit`](evidence/G5.bom_kit.json) | G5 | **PASS** | 0 command(s), 2 input file(s) |
| [`G6.qmk_lint`](evidence/G6.qmk_lint.json) | G6 | **PASS** | 1 command(s), 7 input file(s) |
| [`G6.compile_default`](evidence/G6.compile_default.json) | G6 | **PASS** | 1 command(s), 7 input file(s) |
| [`G6.compile_ledtest`](evidence/G6.compile_ledtest.json) | G6 | **PASS** | 1 command(s), 7 input file(s) |
| [`G6.production_uf2`](evidence/G6.production_uf2.json) | G6 | **PASS** | 0 command(s), 2 input file(s) |
| [`G7.host_tests`](evidence/G7.host_tests.json) | G7 | **PASS** | 1 command(s), 35 input file(s) |
| [`G8.package`](evidence/G8.package.json) | G8 | **PASS** | 0 command(s), 12 input file(s) |
| [`X.cross_positions`](evidence/X.cross_positions.json) | X | **PASS** | 0 command(s), 2 input file(s) |
| [`X.boss_vs_pads`](evidence/X.boss_vs_pads.json) | X | **PASS** | 0 command(s), 4 input file(s) |

## Fix loop

Owner of the failing gate fixes the cause, then rerun `verify/run.sh`. Max 3 rounds per failure, then a human decides (see verify/README.md).
