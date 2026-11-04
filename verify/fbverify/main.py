"""Entry point: python -m fbverify [--self-test] [--only PATTERN] [--no-qmk]."""
from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import shutil
import sys
import traceback
from pathlib import Path

from . import checks as C
from .core import FAIL, NOT_RUN, PASS, Check, Ctx, base_env, find_kicad_cli

VERIFY = Path(__file__).resolve().parents[1]
ROOT = VERIFY.parent

PIPELINE = [
    ("G0.studio_run", C.g0_studio_run), ("G0.studio_constraints", C.g0_studio_constraints),
    ("G0.design_json", C.g0_design_json),
    ("G2.firmware_pins", C.g2_firmware_pins), ("G2.netlist", C.g2_netlist), ("G2.erc", C.g2_erc),
    ("G3.outline_layers", C.g3_outline_layers), ("G3.positions", C.g3_positions), ("G3.drc", C.g3_drc),
    ("G3.drc_jlcpcb", C.g3_drc_jlcpcb), ("G3.gerbers_export", C.g3_gerbers), ("G3.gerbers_zip", C.g3_gerbers_zip),
    ("G3.gnd_thermal", C.g3_gnd_thermal),
    ("G4.check_fit", C.g4_check_fit), ("G4.stl_mesh", C.g4_stl_mesh), ("G4.switch_cutouts", C.g4_switch_cutouts),
    ("G4.encoder_clearance", C.g4_encoder_clearance), ("G4.oled_clearance", C.g4_oled_clearance),
    ("G4.step_parts", C.g4_step_parts),
    ("G5.bom_kit", C.g5_bom_kit),
    ("G6.qmk_lint", C.g6_qmk_lint), ("G6.compile_default", lambda ctx: C.g6_compile(ctx, "default")),
    ("G6.compile_ledtest", lambda ctx: C.g6_compile(ctx, "ledtest")), ("G6.production_uf2", C.g6_production_uf2),
    ("G6.firmware_harness", C.g6_firmware_harness), ("G6.oled_strip_panel", C.g6_oled_strip_panel),
    ("G7.host_tests", C.g7_host_tests),
    ("G8.package", C.g8_package),
    ("X.cross_positions", C.x_cross_positions), ("X.boss_vs_pads", C.x_boss_vs_pads),
    ("X.pcb_insertion", C.x_pcb_insertion), ("X.usb_ids", C.x_usb_ids),
]

# Audit items no tool here can settle. A green report does not cover them.
NEEDS_REAL_PARTS = [
    ("OLED flip", "docs/audit/firmware.md F2", "FROSTBITE_OLED_FLIP is set from reference boards. Flash ledtest with the OLED fitted and read the text."),
    ("EC11 resolution", "docs/audit/firmware.md F6, electrical.md E9", "Resolution 4 may need two clicks per step on a 30/15 part. Turn the kit encoder in ledtest; direction is open too."),
    ("Glow brightness", "docs/audit/case.md M2", "The light reaching the band is a model and an estimate. Print one corner with one SK6812 and look at it."),
    ("LED data level", "docs/audit/electrical.md E3", "3.3 V data is below the datasheet VIH of 3.5 V at 5 V. Run the LED test in docs/BUILD.md on the real board."),
    ("OLED flex clearance", "docs/audit/case.md M3", "The module's flex and tape height at the far end is unknown. Caliper the kit module against the lip gap."),
]


def run_one(fn, ctx: Ctx, cid: str) -> dict:
    try:
        chk = fn(ctx)
    except Exception as e:  # a crashing check is a FAIL, never a pass
        chk = Check(ctx, cid, cid.split(".")[0], "verifier crashed")
        chk.fail(f"verifier error: {type(e).__name__}: {e}")
        chk.details["traceback"] = traceback.format_exc().splitlines()[-15:]
    return chk.write()


def exit_code(records) -> int:
    return 1 if any(r["status"] == FAIL for r in records) else 0


def write_report(records, path: Path, ctx: Ctx):
    n = {s: sum(1 for r in records if r["status"] == s) for s in (PASS, FAIL, NOT_RUN)}
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    L = ["# Frostbite verification report", "",
         f"Generated {now} by `verify/run.sh`. Every row comes from `verify/evidence/<check>.json` "
         f"(commands, exit codes, output tails, SHA-256 of inputs). NOT_RUN is never a pass.", "",
         f"**PASS {n[PASS]} · FAIL {n[FAIL]} · NOT_RUN {n[NOT_RUN]}**, exit code {exit_code(records)}", "",
         f"kicad-cli: `{ctx.kicad_cli or 'not installed'}`", "",
         "## Needs real parts", "",
         "Green below means the files agree. It does not prove these, and no check here can:", ""]
    L += [f"- **{a}** ({b}): {c}" for a, b, c in NEEDS_REAL_PARTS]
    L += ["", "## Checks", "", "| Check | Gate | Status | Summary |", "|---|---|---|---|"]
    for r in records:
        if r["status"] == FAIL:
            s = r["fail_reasons"][0] + (f" (+{len(r['fail_reasons']) - 1} more)" if len(r["fail_reasons"]) > 1 else "")
        elif r["status"] == NOT_RUN:
            s = r["not_run_reason"]
        else:
            s = f"{len(r['commands'])} command(s), {len(r['inputs_sha256'])} input file(s)"
        s = s.replace("|", "\\|")
        L.append(f"| [`{r['check']}`](evidence/{r['check']}.json) | {r['gate']} | **{r['status']}** | {s} |")
    fails = [r for r in records if r["status"] == FAIL]
    if fails:
        L += ["", "## Failures (verbatim from evidence)", ""]
        for r in fails:
            L.append(f"### {r['check']}: {r['title']}")
            L += [f"- {f}" for f in r["fail_reasons"]]
            for c in r["commands"]:
                L.append(f"- command `{' '.join(c['argv'])}` exit {c['exit_code']}")
            L.append("")
    nr = [r for r in records if r["status"] == NOT_RUN]
    if nr:
        L += ["", "## Not run", ""] + [f"- `{r['check']}`: {r['not_run_reason']}" for r in nr]
    L += ["", "## Fix loop", "", "Fix the cause, then rerun `verify/run.sh`. "
          "After 3 rounds on the same failure, a human decides (see verify/README.md).", ""]
    path.write_text("\n".join(L).replace(str(Path.home()), "~"))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="verify/run.sh")
    ap.add_argument("--self-test", action="store_true", help="inject known faults into copies and assert FAIL")
    ap.add_argument("--only", help="glob of check ids to run, e.g. 'G2.*'")
    ap.add_argument("--no-qmk", action="store_true", help="skip qmk lint/compile (NOT_RUN)")
    a = ap.parse_args(argv)
    if a.self_test:
        from .selftest import run_selftest
        return run_selftest(VERIFY, ROOT)
    work = VERIFY / ".cache" / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    ev = VERIFY / "evidence"
    ev.mkdir(exist_ok=True)
    ctx = Ctx(root=ROOT, evidence_dir=ev, work=work, kicad_cli=find_kicad_cli(), env=base_env(),
              run_qmk=not a.no_qmk)
    records = []
    for cid, fn in PIPELINE:
        if a.only and not fnmatch.fnmatch(cid, a.only):
            continue
        (ev / f"{cid}.json").unlink(missing_ok=True)
        r = run_one(fn, ctx, cid)
        print(f"{r['status']:8} {r['check']:24} {(r['fail_reasons'] or [r['not_run_reason'] or ''])[0]}", flush=True)
        records.append(r)
    if not a.only:
        write_report(records, VERIFY / "REPORT.md", ctx)
        print(f"wrote {VERIFY / 'REPORT.md'}")
    return exit_code(records)


if __name__ == "__main__":
    sys.exit(main())
