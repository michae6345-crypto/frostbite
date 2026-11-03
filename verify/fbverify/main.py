"""Entry point: python -m fbverify [--self-test] [--only PATTERN] [--no-qmk]."""
from __future__ import annotations

import argparse
import datetime as _dt
import fnmatch
import json
import shutil
import sys
import traceback
from pathlib import Path

from . import checks as C
from .core import FAIL, NOT_RUN, PASS, Check, Ctx, base_env, find_kicad_cli

VERIFY = Path(__file__).resolve().parents[1]
ROOT = VERIFY.parent

PIPELINE = [
    C.g0_studio_run, C.g0_studio_constraints, C.g0_design_json,
    C.g2_firmware_pins, C.g2_netlist, C.g2_erc,
    C.g3_outline_layers, C.g3_positions, C.g3_drc, C.g3_drc_jlcpcb, C.g3_gerbers, C.g3_gerbers_zip,
    C.g4_check_fit, C.g4_stl_mesh, C.g4_switch_cutouts,
    C.g5_bom_kit,
    C.g6_qmk_lint, lambda ctx: C.g6_compile(ctx, "default"), lambda ctx: C.g6_compile(ctx, "ledtest"),
    C.g6_production_uf2,
    C.g7_host_tests,
    C.g8_package,
    C.x_cross_positions, C.x_boss_vs_pads,
]
IDS = ["G0.studio_run", "G0.studio_constraints", "G0.design_json", "G2.firmware_pins", "G2.netlist", "G2.erc",
       "G3.outline_layers", "G3.positions", "G3.drc", "G3.drc_jlcpcb", "G3.gerbers_export", "G3.gerbers_zip",
       "G4.check_fit", "G4.stl_mesh", "G4.switch_cutouts", "G5.bom_kit", "G6.qmk_lint", "G6.compile_default",
       "G6.compile_ledtest", "G6.production_uf2", "G7.host_tests", "G8.package", "X.cross_positions",
       "X.boss_vs_pads"]


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
    L = [f"# Frostbite verification report", "",
         f"Generated {now} by `verify/run.sh`. Every row comes from `verify/evidence/<check>.json` "
         f"(commands, exit codes, output tails, SHA-256 of inputs). NOT_RUN is never a pass.", "",
         f"**PASS {n[PASS]} · FAIL {n[FAIL]} · NOT_RUN {n[NOT_RUN]}** — exit code {exit_code(records)}", "",
         f"kicad-cli: `{ctx.kicad_cli or 'not installed'}`", "",
         "| Check | Gate | Status | Summary |", "|---|---|---|---|"]
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
            L.append(f"### {r['check']} — {r['title']}")
            L += [f"- {f}" for f in r["fail_reasons"]]
            for c in r["commands"]:
                L.append(f"- command `{' '.join(c['argv'])}` exit {c['exit_code']}")
            L.append("")
    nr = [r for r in records if r["status"] == NOT_RUN]
    if nr:
        L += ["", "## Not run", ""] + [f"- `{r['check']}`: {r['not_run_reason']}" for r in nr]
    L += ["", "## Fix loop", "", "Owner of the failing gate fixes the cause, then rerun `verify/run.sh`. "
          "Max 3 rounds per failure, then a human decides (see verify/README.md).", ""]
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
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    ev = VERIFY / "evidence"
    ev.mkdir(exist_ok=True)
    ctx = Ctx(root=ROOT, evidence_dir=ev, work=work, kicad_cli=find_kicad_cli(), env=base_env(),
              run_qmk=not a.no_qmk)
    records = []
    for fn, cid in zip(PIPELINE, IDS):
        if a.only and not fnmatch.fnmatch(cid, a.only):
            continue
        stale = ev / f"{cid}.json"
        if stale.exists():
            stale.unlink()
        r = run_one(fn, ctx, cid)
        print(f"{r['status']:8} {r['check']:24} {(r['fail_reasons'] or [r['not_run_reason'] or ''])[0]}", flush=True)
        records.append(r)
    if not a.only:
        write_report(records, VERIFY / "REPORT.md", ctx)
        print(f"wrote {VERIFY / 'REPORT.md'}")
    return exit_code(records)


if __name__ == "__main__":
    sys.exit(main())
