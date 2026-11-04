# Verification

Nothing in this repo has been built or tested on hardware. The firmware has only run in a desktop
harness, and the host code has only talked to a fake `hid` module. A PASS means the files agree with
each other and with `design.json`. It does not mean the macropad works.

The PCB is ordered once and the case is printed once, so these checks run before either is paid for.
[`verify/README.md`](../verify/README.md) covers running them. Results are in `verify/REPORT.md`.

## What is checked

| Check | Passes when |
|---|---|
| `G0.studio_run`, `G0.studio_constraints` | The Studio harness and unit tests exit 0, on a copy of `studio/`. |
| `G0.design_json` | Schema holds; pins and nets are unique; every XIAO pin has its Seeed GPIO; one key per (row, col); LED indices are 0..12; keys are at least 19.0 mm apart; PCB is at most 100 × 100 mm and 2 layers; at most 16 switches. |
| `G2.firmware_pins` | `keyboard.json` and `config.h` match `design.json`: matrix, encoder, WS2812 pin and `vendor` driver, 13 LEDs and their key mapping, layout order, I2C1 on GP6/GP7, OLED 128×32 at 0x3C, Raw HID usage, layer 0 key count. |
| `G2.netlist` | From the exported netlist: XIAO signal and power nets; a COL, switch, diode, ROW path for every key; OLED pins 1-4 are GND, 3V3, SCL, SDA; 13 SK6812 on the XIAO 5V net in one DIN to DOUT chain from D6; encoder A/B/C wired, push not on a GPIO. |
| `G2.erc` | `kicad-cli sch erc --severity-error` reports 0 errors. |
| `G3.outline_layers` | Copper is F.Cu and B.Cu only; Edge.Cuts equals `design.json` ± 0.1 mm and fits 100 × 100; "Frostbite" is on silkscreen; "XIAO HERE" is on B.Silkscreen. |
| `G3.positions` | Switches, encoder shaft, OLED header, XIAO on B.Cu, glow LEDs and the LED chain order all land within 0.05 mm of `design.json`. |
| `G3.drc`, `G3.drc_jlcpcb` | DRC with schematic parity gives 0 violations, 0 unconnected items and 0 parity errors, once with the project rules and once with the pinned JLCPCB rules merged in. The stricter bound gates, and PTH annular ring must gate at 0.20 mm or more. |
| `G3.gerbers_export`, `G3.gerbers_zip` | A fresh export and `production/gerbers.zip` both parse in gerbonara with every layer and a drill file, and the outline equals `design.json` ± 0.1 mm. |
| `G3.gnd_thermal` | Every GND pour uses thermal relief, no pad or rule forces solid, and at most 45 % of a ring 0.15 mm outside each GND pad is pour. Relief measured 11-30 %, solid 49-100 %. |
| `G4.check_fit` | `CAD/check_fit.py --no-build` exits 0 on the shipped files. |
| `G4.stl_mesh` | All five printed parts load, are watertight with consistent winding and positive volume, and together fit 200 × 200 × 100 mm. |
| `G4.switch_cutouts` | From the Top mesh: a 13.9 mm housing fits at each key down to the PCB, the narrowest opening is 14.0 ± 0.1 mm and centred ± 0.1, and the clips engage 1.5 ± 0.15 mm of plate. |
| `G4.encoder_clearance` | A 12 × 12 mm body swept from the skirt rim to its seat, and the Ø7 bushing above it, stay at least 0.2 mm from the Top. Any opening shape passes if it clears. |
| `G4.oled_clearance` | The glass and 38 × 12 mm board, turned ±1° about J1 and shifted ±0.1 mm, reach their seats clear of the Top; the glass is not proud; the 22.384 × 5.584 mm active area is visible wherever it sits on the glass; `OLEDSupport.stl` height equals `module_gap` minus 2 × tape. Window size is free. |
| `G4.step_parts` | Each part's STEP reopens, its STL volume is within 1 %, and its STEP volume is within 0.1 % of a rebuild from `CAD/frostbite_case.py`. |
| `G5.bom_kit` | Counts from `design.json` and the PCB fit the kit, and PCB counts equal `design.json`. Extras to buy are listed in the evidence. |
| `G6.qmk_lint`, `G6.compile_default`, `G6.compile_ledtest` | `qmk lint` and both compiles exit 0, and each fresh UF2 has valid magic numbers, block numbering and RP2040 family, and is under 2 MB. |
| `G6.production_uf2` | Production UF2 files parse the same way, and `firmware.uf2` is byte-identical to this run's build or newer than every firmware source. |
| `G6.firmware_harness` | The real `keymap.c` and QMK's OLED driver run on the desktop under ASan and UBSan with no FAIL line, and `proto_test.py` runs the real host encoder and Daemon against that binary with 0 bad. |
| `G6.oled_strip_panel` | The four F1 lines pass, and the last panel dump shows 0 bytes differing from the frame buffer. |
| `G7.host_tests` | `pytest` exits 0 on every file in `host/tests`. Tests still in `docs/audit/host-tests` run on a private copy. Strict xfails are listed as open findings. |
| `G8.package` | The submission files exist, and `README.md` has images for the render, schematic, PCB and case, working image links, and a BOM table. Missing files are FAIL here. |
| `X.cross_positions` | `design.json` agrees with the PCB, with `CAD/positions.json`, and with the Top mesh: insert holes Ø4.7 ± 0.1 mm on the screw positions, and a USB opening at least the design width, centred on the XIAO ± 0.1 mm. |
| `X.boss_vs_pads` | Every insert boss is at least 0.5 mm from every bottom-copper pad, judged separately against the pcbnew export and our own parse. |
| `X.pcb_insertion` | The PCB plus `case.tolerance` per side, swept from skirt rim to seat through `Top.stl`, meets under 0.01 mm³ of material. This shares no code with `check_fit`. |
| `X.usb_ids` | Host, `keyboard.json` and `design.json` agree on VID and PID. The host's `HidTransport.open`, run against a fake `hid`, opens the pad and nothing else in 5 scenes. Only `device.py` imports `hid`. |

**Limits.** Sizes and the kit come from the Hackpad pages; [`audit/hackpad-rules.md`](audit/hackpad-rules.md)
records which are live. Kit: 16 MX switches, 16 keycaps, 20 1N4148, 2 EC11, 1 OLED, 16 SK6812 MINI-E,
6 M3 screws, 6 inserts, 1 XIAO RP2040. Fits: 0.2 mm between printed parts, 0.2 to 0.4 mm to the PCB.

**Steps no check runs.** G1: every value in `docs/DIMENSIONS.md` needs a source, and calipered values
go back in when the kit arrives. G9: print the PCB at 1:1, set the parts on the paper, try a USB-C
cable in a wall offcut, and read the README as a reviewer. G10: bring-up follows
[`BUILD.md`](BUILD.md) in order and stops at the first failure.

## How evidence works

Each check writes `verify/evidence/<check>.json`: status, fail reasons, every command with its exit
code and last 60 lines of output, the SHA-256 of every input file, the measurements, and a UTC
timestamp. A status comes only from an exit code or a parsed value compared with `design.json`. If
a check crashes it is a FAIL. A missing tool or input is NOT_RUN, and NOT_RUN is never a pass. A
claim counts only if an evidence file backs it and its input hashes match the current files.

`verify/run.sh --self-test` copies the project, requires each check to PASS on a clean copy, injects
one known fault, and requires FAIL with a reason that names the fault. It has 57 fault cases and 14
assertions about the harness itself. Ten checks have no injected fault, so their failure path is
untested: both Studio checks, `G2.erc`, `G3.drc`, both gerber checks, `G4.check_fit`, `G6.qmk_lint`
and both compiles. The `G2.netlist` cases use a generated netlist.

## What the checks cannot prove

- **Electrical.** That the board powers up or that LED data is reliable. ERC and DRC know only what
  the symbols and rules declare, and nothing confirms the symbol pins match the real parts. The board
  has no decoupling capacitors, because the kit has none. That is a known risk.
- **Fabrication.** JLCPCB's own DFM review can differ from DRC. Thermal relief in the file does not
  show that a joint solders well.
- **Case.** Printability, shrink, clip force, tilted PCB entry, boss height against component bodies
  and THT leads, and the Bottom and GlowBand sides of the USB window.
- **Stale files.** `G4.step_parts` compares volumes, so a moved feature that keeps the volume passes
  it. The checks on the Top catch some of those. `G6.production_uf2` falls back on file times.
- **Everything else.** RP2040 timing, the real LEDs, encoder and USB stack, a real enumeration on
  macOS, real Claude Code hooks, whether README images are current, and what the kit really ships.

## Needs real parts

`verify/REPORT.md` opens with this list. A green report does not cover these items.

| Item | Why it is open | How to settle it | Audit |
|---|---|---|---|
| OLED flip | `FROSTBITE_OLED_FLIP` is set from reference boards. | Flash `ledtest` with the OLED fitted and read the text. | `docs/audit/firmware.md` F2 |
| EC11 resolution | Resolution 4 may need two clicks per step on a 30/15 part. Direction is open too. | Turn the kit encoder in `ledtest`. | `docs/audit/firmware.md` F6, `electrical.md` E9 |
| Glow brightness | The light reaching the band is a model and an estimate. | Print one corner with one SK6812 and look at it. | `docs/audit/case.md` M2 |
| LED data level | 3.3 V data is below the datasheet VIH of 3.5 V at 5 V. | Run the whole chain in the LED test from docs/BUILD.md on the real board. | `docs/audit/electrical.md` E3 |
| OLED flex clearance | The module's flex and tape height at the far end is unknown. | Caliper the kit module against the lip gap. | `docs/audit/case.md` M3 |
