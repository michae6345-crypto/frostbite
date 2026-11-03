# verify/ — Frostbite verification loop

One command checks the whole project from real tool output and file contents only:

```sh
verify/run.sh              # all checks -> verify/REPORT.md + verify/evidence/<check>.json, exit 1 on any FAIL
verify/run.sh --only 'G3.*'   # a subset (evidence only, REPORT.md is not rewritten)
verify/run.sh --no-qmk     # skip qmk lint/compile (those checks become NOT_RUN)
verify/run.sh --self-test  # inject known faults into copies, assert the right checks FAIL -> verify/selftest.json
```

`run.sh` runs `uv run --frozen --python 3.12 --project verify python -m fbverify`, with the env in `verify/.venv`
(git-ignored). Scratch exports go to `verify/.cache/` (git-ignored). Nothing outside `verify/` is written, except
what the tools themselves write: `qmk compile` builds in `~/qmk_firmware/.build` and copies `frostbite_<km>.uf2`
to `~/qmk_firmware/`, and the host tests use a uv environment in `verify/.cache/host-venv`. The Studio harness
and all KiCad DRC runs work on copies, so `studio/verify/report.md` and `PCB/` are never touched.

## Status rules

| Status | Meaning |
|---|---|
| PASS | every command exited 0 and every parsed value matched design.json within the stated tolerance |
| FAIL | a command exited non-zero, a value did not match, a required file is malformed, or the verifier itself crashed |
| NOT_RUN | an input file or tool is missing. **Never counted as a pass.** |

The process exits 1 if any check FAILs. NOT_RUN alone exits 0, so read the NOT_RUN list in REPORT.md before
calling anything done. Each `evidence/<check>.json` holds: check id, gate, status, fail reasons, not-run reason,
every command (argv, cwd, exit code, duration, last 60 lines of stdout and stderr), the SHA-256 of every input file
read, structured measurements (`details`), and a UTC timestamp. A claim that something works counts only when
there is an evidence file for it, written by this harness, with input hashes that match the current files.

## Checks: what each proves and what it does not

| Check | Proves | Does not prove |
|---|---|---|
| `G0.studio_run`, `G0.studio_constraints` | the Studio harness and unit tests exit 0 (run on a copy of `studio/`) | anything about the real PCB/case; the Studio models are approximations |
| `G0.design_json` | design.json is self-consistent: schema, unique pins/nets, every XIAO pin maps to the GPIO in Seeed's XIAO RP2040 pinout, the matrix has one key per (row, col), LED indices are exactly 0..12, keys ≥ 19.0 mm apart, PCB ≤ 100×100 and 2 layers, < 16 inputs | that the chosen pins are electrically suitable beyond the pinout (e.g. PIO timing) |
| `G2.firmware_pins` | `keyboard.json` + `config.h` match design.json: row/col pins and order, COL2ROW, encoder A/B, WS2812 pin and `vendor` (PIO) driver, 13 LEDs, rgb_matrix LED *i* ↔ the key whose `led` is *i*, layout entries = keys in keys[] order, I2C1 SDA/SCL on GP6/GP7 with the matching I2C driver, OLED 128×32 at 0x3C, Raw HID usage page/id, layer-0 key count in each keymap | that the firmware logic (Raw HID handler, animations) is correct; that is G7/G10 |
| `G2.netlist` | from `kicad-cli sch export netlist`: each XIAO pin's net name = design.json; XIAO 5V/3V3/GND on power nets; every switch has a COLc→switch→diode(A→K)→ROWr path (COL2ROW) through a 2-node net; OLED header pins 1-4 = GND, 3V3, SCL, SDA; 13 SK6812 with VDD on the XIAO 5V net and an unbroken DIN→DOUT chain starting at D6; encoder A/B on ENC_A/ENC_B, C on GND, push not on a GPIO | that 3.3 V data into 5 V SK6812s is reliable (VIH ≈ 3.5 V; prove at G10), that there is decoupling, that the symbol pins match the real footprint pinout |
| `G2.erc` | `kicad-cli sch erc --severity-error --exit-code-violations` reports 0 errors | warnings; ERC only knows what the symbols declare |
| `G3.outline_layers` | parsed `.kicad_pcb`: only F.Cu/B.Cu, Edge.Cuts bbox ≤ 100×100 and = design.json w/h ± 0.1, "Frostbite" on silkscreen, "XIAO HERE" on B.Silkscreen | that the outline is a closed shape (DRC covers that) |
| `G3.positions` | parsed `.kicad_pcb`, origin = Edge.Cuts top-left: SW1–SW9 origins, encoder shaft (midpoint of its two MP pads), OLED header pads (x = 39.0, centre y = 13.0, pitch 2.54, pad 1 at the back), XIAO on B.Cu with its 17.8×21 Fab outline on design.json's rect, glow LEDs at their positions on the bottom, and the PCB LED chain (followed through pad nets from LED_DIN) with chain LED *i* under the key whose `led` is *i*; all within 0.05 mm. Also records `kicad-cli pcb export pos` output | per-key LED offset under the switch, mounting holes, USB overhang depth, courtyard clearances (DRC) |
| `G3.drc`, `G3.drc_jlcpcb` | `kicad-cli pcb drc --severity-error --exit-code-violations --schematic-parity` has 0 violations, 0 unconnected items, 0 parity errors — once with the project's rules, once with the pinned JLCPCB 2-layer rules added | signal integrity, LED data level shifting, that the board works; JLCPCB's own DFM check may still differ |
| `G3.gerbers_export` | a fresh `kicad-cli pcb export gerbers` + `drill` parsed by gerbonara has top/bottom copper, mask, silk, outline and drill files, outline (minus stroke width) = design.json ± 0.1 | that the zip you upload is that export (see next) |
| `G3.gerbers_zip` | the same for `production/gerbers.zip` | that it is current with the `.kicad_pcb` (compare with `G3.gerbers_export`) |
| `G4.check_fit` | `CAD/check_fit.py` exits 0 (its own fit checks; see its output in the evidence) | anything the script does not test |
| `G4.stl_mesh` | every `production/*.stl` loads, is watertight with consistent winding and positive volume; combined bounds ≤ 200×200×100 | printability (overhangs, bridges, wall thickness) |
| `G4.switch_cutouts` | the Top/plate STL, sectioned perpendicular to its largest flat face at 19 depths: the best section has exactly 9 square holes whose centroid chords are 14.0 ± 0.1 and whose centre pattern matches the design.json key pattern (sorted pairwise distances, ± 0.1 mm) | absolute placement against the case outline (rigid-motion invariant), clip/relief geometry, plate thickness at the clips |
| `G5.bom_kit` | counts implied by design.json (and PCB footprint counts when a PCB exists) ≤ the Hackpad kit (16 switches, 16 caps, 20 diodes, 2 EC11, 1 OLED, 16 SK6812 MINI-E, 6 screws, 6 inserts, 1 XIAO), PCB counts = design.json; lists extras to buy | prices, that the kit actually ships those parts |
| `G6.qmk_lint`, `G6.compile_default`, `G6.compile_ledtest` | `~/qmk_firmware/keyboards/frostbite` resolves to this repo's `Firmware/qmk/keyboards/frostbite`; `qmk lint` and both `qmk compile` runs exit 0; each fresh `.uf2` has valid magic numbers on every block, sequential block numbers, consistent numBlocks, family 0xe48bff56 (RP2040), < 2 MB | that it boots or runs correctly on hardware (G10) |
| `G6.production_uf2` | `production/firmware.uf2` (and any other production `.uf2`) parses as above, and is byte-identical to this run's default build or newer than every file in the keyboard dir | that the file was built from the committed sources if neither identity nor time order is conclusive |
| `G7.host_tests` | `uv run --project host pytest -q` exits 0 | behaviour against a real device or real Claude Code hooks |
| `G8.package` | submission tree: one assembly `.step/.stp/.3mf` in CAD/, `.kicad_pro/.kicad_sch/.kicad_pcb` in PCB/, Firmware/keyboard.json, `production/gerbers.zip`, `production/firmware.uf2`, ≥ 1 case STEP/STL; README has images for render / schematic / PCB / case (by alt text or path), every local image link resolves, and a BOM heading with a markdown table | that the screenshots are current or show the right thing; a reviewer still reads it (G9). Missing files are FAIL here, not NOT_RUN: missing is exactly what this check is for |
| `X.boss_vs_pads` | every case insert boss (circle of `case.screws.boss_od` at each `case.screws.positions`, and at each `CAD/positions.json` screw) is ≥ 0.5 mm from every bottom-copper pad box. Pads come from two sources, each judged separately: `PCB/build/bottom_pads.json` (pcbnew export; if missing or older than the `.kicad_pcb` it is regenerated into `verify/.cache/` with KiCad's bundled python and `PCB/tools/export_bottom_pads.py`), and the verifier's own `.kicad_pcb` parse (pads on `B.Cu`/`*.Cu`; rotated-rect bounding box, drill offset covered in both directions, so it is never smaller than pcbnew's box). Also `CAD/positions.json` screws = design.json ± 0.1 | 3D clearance (boss height vs component bodies and THT leads), screw head clearance, anything on the top side |
| `X.cross_positions` | design.json ↔ PCB (as G3.positions), ↔ a CAD positions file if CAD writes one (key/encoder/OLED window positions, screws = design.json, USB cutout centred on the XIAO and at least `case.usb_cutout` w × h = 13.5 × 8.0), ↔ the Top STL: encoder hole (round, Ø 5–13) and OLED window (≈ 30 × 11.5) relative to the 9 measured switch cutouts, ± 0.1 mm | USB cutout position from the mesh (only through the positions file); the case-to-PCB stack height |

Tolerances: PCB 0.05 mm, outline 0.1 mm, cutouts 14.0 ± 0.1, CAD positions 0.1 mm. They are constants at the top
of `fbverify/checks.py`.

**CAD positions file (optional, read if present).** `CAD/positions.json` (or `production/positions.json`) in PCB
coordinates: `{"keys":[{"ref":"SW1","x":..,"y":..},...], "encoder":{"x":..,"y":..}, "usb_cutout":{"x":..,"w":..,"h":..},
"oled_window":{"x":..,"y":..,"w":..,"h":..}, "screws":[{"x":..,"y":..},...]}`. Without it the cross-check measures the Top STL instead.

## Self-test

`--self-test` copies the project into a temp dir and runs 25 cases. Each case first runs the check on a clean copy
and requires PASS, then injects one fault and requires FAIL with a reason that names it. Where the real input does
not exist yet, the clean copy uses a fixture generated from design.json (a minimal `.kicad_pcb`, a kicadsexpr
netlist, a Top plate STL, a UF2). Faults: wrong XIAO GPIO and duplicate LED index in design.json; swapped column
pins, swapped I2C SDA/SCL and a missing LED in the firmware; OLED SCL/SDA swapped, LED chain broken and XIAO D9/D10
swapped in the netlist; SW5 moved 0.2 mm, two chain LEDs swapped and a third copper layer in the PCB; truncated UF2
and wrong family ID; a non-watertight STL, a 14.3 mm cutout, a cutout moved 0.5 mm and an encoder hole moved 1 mm;
SW7 moved and a 13.0 mm USB cutout in a CAD positions file; an insert boss moved onto diode D9's pad in design.json,
in CAD/positions.json, and on the real PCB, plus a pad added 0.15 mm from a boss in bottom_pads.json; 17 LEDs vs the kit's 16; missing gerbers.zip and README image. It also asserts
that missing inputs give NOT_RUN, that the exit code follows FAIL, and that the pinned rules file hash matches.
Result: `verify/selftest.json`; exit 0 only if every case behaved.

The KiCad-CLI checks (netlist export, ERC, DRC, gerber export) are not in the self-test because they need a real
KiCad project; their parsing was smoke-tested against KiCad 10.0.8's bundled `Arduino_Micro` template (outline
48.26 × 17.78 read identically from Edge.Cuts and from the exported gerbers; DRC/ERC JSON parsed).

## Fix loop

1. Run `verify/run.sh`.
2. Read `verify/REPORT.md`: the Failures section quotes every fail reason verbatim from the evidence files.
3. Send each FAIL to the owner of the cause (gate table in `docs/VERIFICATION.md`): Firmware → firmware agent,
   PCB/netlist/DRC → PCB agent, STL/check_fit → CAD agent, host → host agent, design.json → lead. A mismatch
   against design.json is fixed in the artifact, not by editing design.json, unless the lead decides the spec
   changes (then everything downstream reruns).
4. The owner fixes it; the verifier reruns. The owner does not mark anything passed.
5. At most 3 rounds per failure. If the same check still FAILs after the third rerun, stop and a human decides
   (change the spec, accept a documented deviation, or change the check with a written reason in this README).

## Provenance

- Python 3.12 via uv 0.13.7. Pinned in `pyproject.toml` / `uv.lock`: gerbonara 1.6.3, trimesh 5.2.0, numpy 2.5.4,
  shapely 2.2.0, networkx 3.7, jsonschema 4.26.0, mapbox-earcut 2.1.0 (only for the self-test plate fixture).
- `rules/JLCPCB-2L-1oz.kicad_dru` from https://github.com/Cimos/kicad-druid, file `JLCPCB/JLCPCB-2L-1oz.kicad_dru`
  at commit `8af046d6a1839320a360a4b6790ac11eb27a78ae`, MIT licence. SHA-256
  `292b812a764c76785446b9de5e00c9e76bc58bd4019071f1f99294e81f3874d2`, checked on every DRC run; a mismatch is a FAIL.
  For the JLCPCB DRC run the rules are copied next to a temporary copy of the board (merged after the project's own
  `.kicad_dru` if it has one).
- XIAO RP2040 pin → GPIO table: Seeed Studio XIAO RP2040 wiki pinout (D0–D3 = GP26–29, D4/D5 = GP6/GP7,
  D6 = GP0, D7 = GP1, D8 = GP2, D9 = GP4, D10 = GP3). Pad numbers 1–7 = D0–D6, 8–11 = D7–D10, 12 = 3V3, 13 = GND,
  14 = 5V (used only when a symbol pin has no D-name).
- SK6812 MINI-E pins 1 VDD, 2 DOUT, 3 GND, 4 DIN (datasheet), used only when the symbol has no pin names.
- Tools found at run time: kicad-cli at `~/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (10.0.8 when this
  was written), qmk CLI 1.2.0, node v24.
