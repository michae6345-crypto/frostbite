# verify

Checks the project from tool output and file contents. Nothing has been built or tested on hardware,
so a green report means the files agree and no more. [`docs/VERIFICATION.md`](../docs/VERIFICATION.md)
says what each check compares and what the checks cannot prove.

```sh
verify/run.sh                # all checks; writes REPORT.md and evidence/<check>.json; exit 1 on any FAIL
verify/run.sh --only 'G3.*'  # a subset; evidence only, REPORT.md is left alone
verify/run.sh --no-qmk       # skip qmk lint and compile; those checks become NOT_RUN
verify/run.sh --self-test    # inject known faults into copies; writes selftest.json
```

`run.sh` needs uv. The env is in `verify/.venv` and scratch files in `verify/.cache/`, both git-ignored.
The checks also use KiCad, the QMK CLI with `~/qmk_firmware`, node and clang; a missing tool gives
NOT_RUN. Studio and DRC runs work on copies. Outside `verify/`, `qmk compile` writes to
`~/qmk_firmware/`. Never run `CAD/check_fit.py` without `--no-build`: it rewrites production files.

## Status

- **PASS**: every command exited 0 and every parsed value matched `design.json` within tolerance.
- **FAIL**: a command failed, a value did not match, a required file is malformed, or the verifier crashed.
- **NOT_RUN**: an input file or tool is missing. This is never a pass.

The process exits 1 on any FAIL. NOT_RUN alone exits 0, so read the NOT_RUN list in `REPORT.md` before
calling anything done. Tolerances are constants at the top of `fbverify/checks.py`: PCB positions
0.05 mm, outline 0.1 mm, cutouts 14.0 ± 0.1 mm, CAD positions 0.1 mm.

## How the Top and Bottom are measured

`fbverify/topmodel.py` assumes no section height or opening shape. The axis is the largest flat face,
and the frame comes from the outline, which must match `case.shell` ± 0.2 mm. The Top's rotation is
the one that leaves the design's key, encoder and OLED points open. The Bottom's is the one that puts
the USB notch on the back wall. Depth is measured from the plate top on the Top and from the rim on
the Bottom. Sections are taken at every mesh vertex height and wherever a real part starts or stops.
They must integrate back to the mesh volume ± 0.5 %, so the slicer cannot lose material unnoticed.

`CAD/positions.json` is optional and is compared with `design.json` and the Top mesh if present.

## Self-test

`--self-test` runs 102 fault cases and 13 harness assertions, listed in `fbverify/selftest.py`.
Each case requires PASS on a clean copy, then FAIL with a reason naming the injected fault. A skipped
case is listed in `selftest.json` and is not a pass. `fbverify/probe_fault.py` makes the cases that
damage the real Top and Bottom, on a copy, with CadQuery.

`fixtures/old_b1_Top.stl` is the audited blocked part from the old case, where the inserts sat in a
skirted Top (`Top.step` SHA-256 `94e8d2e54376959ea3a7be846a5e88537d7fa13eb7b8c0a7cf2d25036615ec39`).
It stands in for the Bottom as a real tray that blocks the PCB: the PCB envelope alone meets 162.4 mm³ of it.

## Fix loop

Read the Failures section of `REPORT.md`, fix the cause and rerun. A mismatch with `design.json` is
fixed in the file at fault, unless the spec itself changes. After 3 rounds on the same failure, a human
decides: change the spec, accept a documented deviation, or change the check with a written reason here.

## Sources

- `rules/JLCPCB-2L-1oz.kicad_dru`: `JLCPCB/JLCPCB-2L-1oz.kicad_dru` from https://github.com/Cimos/kicad-druid at commit `8af046d6a1839320a360a4b6790ac11eb27a78ae`, MIT licence. `G3.drc_jlcpcb` checks its SHA-256 on every run. The file says PTH annular ring 0.18 mm and JLCPCB publishes 0.20, so the check merges it with `PCB/frostbite.kicad_dru` rule by rule in `strictest_rules()`. The stricter bound wins. Plain concatenation fails because KiCad lets a later rule override an earlier one.
- XIAO pin to GPIO table: Seeed Studio XIAO RP2040 wiki. Pads 1-7 are D0-D6, 8-11 are D7-D10, 12 is 3V3, 13 GND, 14 5V.
