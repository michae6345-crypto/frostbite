"""Evidence records, command runner, hashing. Every status comes from here."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

PASS, FAIL, NOT_RUN = "PASS", "FAIL", "NOT_RUN"
TAIL_LINES = 60


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tail(text: str, n: int = TAIL_LINES) -> list[str]:
    lines = text.splitlines()
    return lines[-n:]


@dataclass
class Ctx:
    root: Path                     # project root (or a self-test copy of it)
    evidence_dir: Path
    work: Path                     # scratch dir for exports
    kicad_cli: Path | None
    env: dict
    run_qmk: bool = True
    run_slow: bool = True
    allow_regen: bool = True
    qmk_home: Path = Path.home() / "qmk_firmware"
    cache: dict = field(default_factory=dict)

    def p(self, rel: str) -> Path:
        return self.root / rel


class Check:
    """One check = one evidence file. Status only changes through fail()/not_run()/finish()."""

    def __init__(self, ctx: Ctx, cid: str, gate: str, title: str):
        self.ctx, self.id, self.gate, self.title = ctx, cid, gate, title
        self.commands: list[dict] = []
        self.inputs: dict[str, str] = {}
        self.failures: list[str] = []
        self.notes: list[str] = []
        self.not_run_reason: str | None = None
        self.details: dict = {}
        self.started = time.time()

    # -- inputs -----------------------------------------------------------
    def read(self, path: Path, mode: str = "t"):
        """Read a file and record its SHA-256. Returns str (mode 't') or bytes."""
        self.hash(path)
        return path.read_text(encoding="utf-8", errors="replace") if mode == "t" else path.read_bytes()

    def hash(self, path: Path):
        path = Path(path)
        if path.is_file():
            try:
                key = str(path.relative_to(self.ctx.root))
            except ValueError:
                key = str(path)
            self.inputs[key] = sha256(path)

    # -- commands ---------------------------------------------------------
    def run(self, argv: list[str], cwd: Path | None = None, timeout: int = 600, env: dict | None = None):
        cwd = cwd or self.ctx.root
        t0 = time.time()
        e = dict(self.ctx.env)
        if env:
            e.update(env)
        try:
            p = subprocess.run([str(a) for a in argv], cwd=str(cwd), env=e, capture_output=True,
                               text=True, timeout=timeout, errors="replace")
            code, out, err = p.returncode, p.stdout, p.stderr
        except FileNotFoundError as ex:
            code, out, err = 127, "", f"{ex}"
        except subprocess.TimeoutExpired as ex:
            code = 124
            out = (ex.stdout or b"").decode(errors="replace") if isinstance(ex.stdout, bytes) else (ex.stdout or "")
            err = f"TIMEOUT after {timeout}s"
        rec = {
            "argv": [str(a) for a in argv], "cwd": str(cwd), "exit_code": code,
            "duration_s": round(time.time() - t0, 2),
            "stdout_tail": tail(out), "stderr_tail": tail(err),
        }
        self.commands.append(rec)
        return code, out, err

    # -- status -----------------------------------------------------------
    def fail(self, msg: str):
        self.failures.append(msg)

    def note(self, msg: str):
        self.notes.append(msg)

    def not_run(self, reason: str):
        self.not_run_reason = reason
        return self

    @property
    def status(self) -> str:
        if self.failures:
            return FAIL
        if self.not_run_reason:
            return NOT_RUN
        return PASS

    def record(self) -> dict:
        return {
            "check": self.id, "gate": self.gate, "title": self.title, "status": self.status,
            "fail_reasons": self.failures, "not_run_reason": self.not_run_reason,
            "notes": self.notes, "commands": self.commands, "inputs_sha256": self.inputs,
            "details": self.details,
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "duration_s": round(time.time() - self.started, 2),
        }

    def write(self) -> dict:
        rec = self.record()
        self.ctx.evidence_dir.mkdir(parents=True, exist_ok=True)
        # Evidence is committed to a public repo: show the home folder as ~ instead of the local username.
        text = json.dumps(rec, indent=2).replace(str(Path.home()), "~")
        (self.ctx.evidence_dir / f"{self.id}.json").write_text(text + "\n")
        return rec


def find_kicad_cli() -> Path | None:
    cands = [Path.home() / "Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
             Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")]
    w = shutil.which("kicad-cli")
    if w:
        cands.insert(0, Path(w))
    for c in cands:
        if c.is_file() and os.access(c, os.X_OK):
            return c
    return None


def base_env() -> dict:
    e = dict(os.environ)
    home = str(Path.home())
    extra = [f"{home}/.local/bin", f"{home}/Library/Application Support/qmk/bin"]
    e["PATH"] = ":".join(extra + [e.get("PATH", "")])
    e.pop("VIRTUAL_ENV", None)
    return e
