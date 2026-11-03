"""Training-run watcher: tails a text log or a JSONL metrics file.

  run    once lines arrive (detail: "e3 s812 loss 0.4213")
  done   on a final line ("training complete", {"event": "end"}, --done-pattern ...)
         or when the file stops growing for `stale_minutes`
  error  on a nan/inf loss or a Python traceback / "...Error:" line
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger("frostbite.train")

NUM = r"[-+]?(?:nan|inf(?:inity)?|\d+(?:\.\d*)?(?:e[-+]?\d+)?|\.\d+(?:e[-+]?\d+)?)"

STEP_RE = re.compile(r"\b(?:global[_ ]?step|step|iter(?:ation)?|it|batch)\b[\x27\x22]?\s*[:=#]?\s*\[?\s*(\d+)(?:\s*/\s*(\d+))?", re.I)
EPOCH_RE = re.compile(r"\bepoch\b[\x27\x22]?\s*[:=#]?\s*\[?\s*(\d+(?:\.\d+)?)(?:\s*/\s*(\d+))?", re.I)
# "loss" as its own word (train_loss / train loss allowed); val_loss etc. are skipped here.
LOSS_RE = re.compile(r"(?:\btrain[_ ]|\b)loss\b[\x27\x22]?\s*[:=]?\s*(" + NUM + r")", re.I)
# Any loss-like metric (val_loss, loss_ce, ...) that went non-finite is an error.
BAD_LOSS_RE = re.compile(r"\w*loss\w*['\"]?\s*[:=]?\s*['\"]?\s*([-+]?(?:nan|inf(?:inity)?))\b", re.I)
TRACEBACK_RE = re.compile(r"^\s*Traceback \(most recent call last\):")
EXC_RE = re.compile(r"^\s*((?:[A-Za-z_][\w]*\.)*[A-Za-z_]\w*(?:Error|Exception)|KeyboardInterrupt|Killed)\b(?::\s*(.*))?$")
FATAL_RE = re.compile(r"CUDA out of memory|Segmentation fault|core dumped|\bOOM\b|Killed\s*$", re.I)
DONE_RE = re.compile(
    r"\b(training (?:is )?(?:complete|completed|finished|done)|finished training|done training|"
    r"run (?:complete|completed|finished)|all done|saved final model|saving final model|"
    r"training ended|FROSTBITE_DONE)\b", re.I)

LOSS_KEYS = ("loss", "train_loss", "train/loss", "training_loss", "loss_train")
STEP_KEYS = ("step", "global_step", "iteration", "iter", "it", "trainer/global_step", "_step")
EPOCH_KEYS = ("epoch", "train/epoch")


def _num(v) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip())
        except ValueError:
            return None
    return None


@dataclass
class LineInfo:
    step: int | None = None
    epoch: float | None = None
    loss: float | None = None
    error: str | None = None
    done: bool = False
    traceback: bool = False


def parse_json_line(obj: dict) -> LineInfo:
    info = LineInfo()
    for k in STEP_KEYS:
        n = _num(obj.get(k))
        if n is not None and math.isfinite(n):
            info.step = int(n)
            break
    for k in EPOCH_KEYS:
        n = _num(obj.get(k))
        if n is not None and math.isfinite(n):
            info.epoch = n
            break
    for k in LOSS_KEYS:
        n = _num(obj.get(k))
        if n is not None:
            info.loss = n
            break
    if info.loss is None:
        for k, v in obj.items():
            if "loss" in str(k).lower():
                n = _num(v)
                if n is not None:
                    info.loss = n
                    break
    for k, v in obj.items():
        if "loss" in str(k).lower():
            n = _num(v)
            if n is not None and not math.isfinite(n):
                info.error = f"{k}={v}"
                break
    marker = " ".join(str(obj.get(k, "")) for k in ("event", "status", "state", "msg", "message"))
    if re.search(r"\b(end|ended|done|finished|complete|completed|success)\b", marker, re.I):
        info.done = True
    if re.search(r"\b(error|failed|crash(ed)?|exception)\b", marker, re.I):
        info.error = info.error or marker.strip()
    return info


def parse_line(line: str, done_re: re.Pattern | None = None) -> LineInfo:
    line = line.strip()
    if not line:
        return LineInfo()
    if line.startswith("{") and line.endswith("}"):
        try:
            obj = json.loads(line)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            info = parse_json_line(obj)
            if done_re and done_re.search(line):
                info.done = True
            return info
    info = LineInfo()
    if TRACEBACK_RE.match(line):
        info.traceback = True
        info.error = "Traceback"
        return info
    m = EXC_RE.match(line)
    if m:
        info.error = m.group(0).strip()
        return info
    if FATAL_RE.search(line):
        info.error = line
        return info
    m = STEP_RE.search(line)
    if m:
        info.step = int(m.group(1))
    m = EPOCH_RE.search(line)
    if m:
        info.epoch = float(m.group(1))
    m = LOSS_RE.search(line)
    if m:
        info.loss = float(m.group(1))
    m = BAD_LOSS_RE.search(line)
    if m:
        info.error = f"{m.group(0).strip()}"
    if info.loss is not None and not math.isfinite(info.loss):
        info.error = info.error or f"loss {m.group(1) if m else info.loss}"
    if DONE_RE.search(line) or (done_re and done_re.search(line)):
        info.done = True
    return info


def _fmt_epoch(e: float) -> str:
    return str(int(e)) if float(e).is_integer() else f"{e:.2f}"


@dataclass
class RunState:
    """Folds parsed lines into a status + detail string."""
    status: str = "idle"          # idle | run | done | error
    step: int | None = None
    epoch: float | None = None
    loss: float | None = None
    error: str | None = None
    in_traceback: bool = False
    lines: int = 0
    history: list[str] = field(default_factory=list)

    def feed(self, info: LineInfo, raw: str = "") -> None:
        self.lines += 1
        if self.status == "error":
            # Errors are sticky until the file restarts; only refine a traceback's message
            # with the exception line that ends it.
            if self.in_traceback and self.error == "Traceback" and info.error:
                self.error = info.error
            return
        if info.step is not None:
            self.step = info.step
        if info.epoch is not None:
            self.epoch = info.epoch
        if info.loss is not None:
            self.loss = info.loss
        if info.traceback:
            self.in_traceback = True
            self.status = "error"
            self.error = self.error or "Traceback"
            return
        if info.error:
            self.error = info.error
            self.status = "error"
            return
        if info.done:
            self.status = "done"
            return
        if raw.strip() and self.status in ("idle", "done"):
            self.status = "run"

    def progress(self) -> str:
        parts = []
        if self.epoch is not None:
            parts.append("e" + _fmt_epoch(self.epoch))
        if self.step is not None:
            parts.append(f"s{self.step}")
        if self.loss is not None:
            parts.append(f"loss {self.loss:.4g}")
        return " ".join(parts)

    def detail(self) -> str:
        if self.status == "error":
            err = self.error or "error"
            if "nan" in err.lower() or "inf" in err.lower():
                where = f" s{self.step}" if self.step is not None else ""
                return f"NaN/inf loss{where}" if "nan" in err.lower() else f"inf loss{where}"
            return err
        if self.status == "done":
            p = self.progress()
            return ("done " + p) if p else "done"
        return self.progress() or "running"


class TrainWatcher:
    """Tails one file in a background thread and calls `emit(message)` with daemon
    "update" messages whenever the status or detail changes."""

    def __init__(self, path: str, name: str | None, emit: Callable[[dict], None], *,
                 stale_minutes: float = 10.0, stale_status: str = "done",
                 done_pattern: str | None = None, poll: float = 1.0, from_start: bool = True,
                 clock: Callable[[], float] = time.time):
        self.path = os.path.abspath(os.path.expanduser(path))
        self.name = name or os.path.splitext(os.path.basename(self.path))[0]
        self.key = f"train:{self.name}"
        self.emit = emit
        self.stale = stale_minutes * 60.0
        self.stale_status = stale_status
        self.done_re = re.compile(done_pattern, re.I) if done_pattern else None
        self.poll = poll
        self.from_start = from_start
        self.clock = clock
        self.state = RunState()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_sent: tuple[str, str] | None = None
        self._last_growth = clock()
        self._fh = None
        self._ino = None
        self._pos = 0
        self._partial = ""

    # -- feeding (also used directly by tests)
    def feed_text(self, text: str) -> None:
        data = self._partial + text
        parts = re.split(r"\r\n|\r|\n", data)
        self._partial = parts.pop()  # incomplete last line
        for ln in parts:
            self.state.feed(parse_line(ln, self.done_re), ln)
        self._last_growth = self.clock()
        self._publish()

    def check_stale(self) -> None:
        if self.state.status == "run" and self.clock() - self._last_growth >= self.stale:
            if self._partial.strip():
                self.state.feed(parse_line(self._partial, self.done_re), self._partial)
                self._partial = ""
            if self.state.status == "run":
                mins = int(self.stale // 60)
                self.state.status = self.stale_status
                prog = self.state.progress()
                self._publish(detail=f"quiet {mins}m {prog}".strip())
                return
            self._publish()

    def _publish(self, detail: str | None = None) -> None:
        st = self.state.status
        det = detail or self.state.detail()
        if (st, det) == self._last_sent:
            return
        self._last_sent = (st, det)
        self.emit({"op": "update", "source": "train", "key": self.key, "name": self.name,
                   "status": st, "detail": det, "log": self.path})

    # -- file tailing
    def _open(self) -> bool:
        try:
            fh = open(self.path, "r", encoding="utf-8", errors="replace", newline="")
            st = os.fstat(fh.fileno())
        except OSError:
            return False
        self._fh, self._ino = fh, st.st_ino
        self._pos = 0 if self.from_start else st.st_size
        fh.seek(self._pos)
        self._partial = ""
        log.info("watching %s as %s", self.path, self.key)
        return True

    def poll_once(self) -> None:
        if self._fh is None:
            if not self._open():
                return
        try:
            st = os.stat(self.path)
        except OSError:
            st = None
        if st is None or st.st_ino != self._ino or st.st_size < self._pos:
            # rotated / truncated / replaced: a new run
            log.info("%s restarted", self.path)
            self._fh.close()
            self._fh = None
            self.state = RunState()
            self._last_sent = None
            if st is not None:
                self._open()
            return
        chunk = self._fh.read()
        if chunk:
            self._pos = self._fh.tell()
            self.feed_text(chunk)
        else:
            self.check_stale()

    def start(self) -> None:
        self.emit({"op": "update", "source": "train", "key": self.key, "name": self.name,
                   "register_only": True, "detail": "waiting for log", "log": self.path})
        self._thread = threading.Thread(target=self._run, name=f"watch-{self.name}", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception as e:  # noqa: BLE001
                log.warning("watcher %s: %s", self.name, e)
            self._stop.wait(self.poll)

    def stop(self) -> None:
        self._stop.set()
        if self._fh:
            self._fh.close()
