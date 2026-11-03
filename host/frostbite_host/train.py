"""Training-run watcher: tails a text log or a JSONL metrics file.

  run    once lines arrive (detail: "e3 s812 loss 0.4213")
  done   on a final line ("training complete", {"event": "end"}, --done-pattern ...)
  needs  when the file stops growing for `stale_minutes`: a killed run also just goes
         quiet, so silence is never shown as success (--stale-status done restores that)
  error  on a nan/inf loss, a Python traceback or an "...Error:" line
"""

from __future__ import annotations

import codecs
import json
import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger("frostbite.train")

CHUNK = 1 << 20           # bytes read at a time
MAX_BACKLOG = 16 << 20    # a file bigger than this is read from its last 16 MiB
MAX_PARTIAL = 1 << 20     # longest line kept while waiting for its newline
HEAD_BYTES = 256          # start of the file, compared to notice copytruncate

NUM = r"[-+]?(?:nan|inf(?:inity)?|\d+(?:\.\d*)?(?:e[-+]?\d+)?|\.\d+(?:e[-+]?\d+)?)"
BAD = r"(?:nan|[-+]?inf(?:inity)?)"
NUM_END = r"(?![\w-]|\.\d)"                 # "info", "nan-safe" and "0.5.1" are not numbers
WRAP = r"(?:tensor\(|array\()?\[?"          # loss: tensor(0.42, grad_fn=...)
QUOTE = r"[\x27\x22]?"

STEP_RE = re.compile(r"\b(?:global[_ ]?step|step|iter(?:ation)?|it|batch)\b" + QUOTE
                     + r"\s*[:=#]?\s*\[?\s*(\d+)(?:\s*/\s*(\d+))?", re.I)
EPOCH_RE = re.compile(r"\bepoch\b" + QUOTE + r"\s*[:=#]?\s*\[?\s*(\d+(?:\.\d+)?)(?:\s*/\s*(\d+))?", re.I)
# "loss" as its own word (train_loss / train loss allowed); val_loss and paths are skipped.
LOSS_RE = re.compile(r"(?<![-\w./])(?:train(?:ing)?[_/ ])?loss\b" + QUOTE + r"\s*(?:[:=]|\bis\b)?\s*"
                     + QUOTE + r"\s*" + WRAP + "(" + NUM + ")" + NUM_END, re.I)
# Any loss metric (val_loss, loss_ce, ...) that went non-finite. Not loss_scale (AMP) and
# not file names such as best-loss-nan.pt or val_loss_inf.pt.
BAD_LOSS_RE = re.compile(
    r"(?<![-\w./])(?P<name>(?:[a-z0-9]+[_/])*loss(?:[_/](?!scal)[a-z0-9]+)*)\b" + QUOTE
    + r"\s*(?:[:=]|=>|->|\bis\b|\bwas\b|\bbecame\b|\bbecomes\b|\bwent to\b)?\s*" + QUOTE + r"\s*"
    + WRAP + BAD + r"(?![-\w])", re.I)
BAD_FIRST_RE = re.compile(r"(?<![-\w./])(?:nan|inf)\s+(?:value\s+)?(?:(?:in|for|on)\s+(?:the\s+)?)?"
                          r"(?P<name>loss)\b", re.I)
# "best_loss: inf" is the usual starting value, not a failure.
TRACKER_RE = re.compile(r"\b(?:best|min|minimum|lowest|prev\w*)[_ /]", re.I)

TRACEBACK_RE = re.compile(r"Traceback \(most recent call last\):")
# What loggers and launchers put in front of an exception line.
LOG_PREFIX = (r"^\s*(?:\[[^\]]*\]:?\s*|[\d:,.TZ/-]+\s+|(?:ERROR|CRITICAL|FATAL)\b[:\s-]*)*")
EXC_RE = re.compile(LOG_PREFIX + r"((?:[A-Za-z_]\w*\.)*[A-Za-z_]\w*(?:Error|Exception)|KeyboardInterrupt)"
                    r"\b(?::\s*(.*))?$")
RECOVERS_RE = re.compile(r"\b(?:retry|retries|retrying|retried|skip|skips|skipped|skipping|continu\w+|"
                         r"ignor\w+|recover\w+|will try|falling back)\b", re.I)
FATAL_RE = re.compile(r"\b(?:CUDA|MPS|GPU|backend)\b.*\bout of memory\b|\bSegmentation fault\b|"
                      r"\bcore dumped\b|^\s*Killed(?::\s*9)?\s*$|\boom-kill\b", re.I)
DONE_RE = re.compile(
    r"\b(training (?:is )?(?:complete|completed|finished|done)|finished training|done training|"
    r"run (?:complete|completed|finished)|saved final model|saving final model|"
    r"training ended|FROSTBITE_DONE)\b", re.I)
# "Stage 1 training complete, starting stage 2" and "warmup training finished" are not the end.
NOT_FINAL_RE = re.compile(r"\b(?:warm-?up|stage|phase|pre-?train\w*)\b|,\s*(?:now\s+)?"
                          r"(?:starting|start|moving|next|beginning|begin|proceeding)\b", re.I)
START_RE = re.compile(r"\b(?:starting|beginning|resuming|start)\s+(?:a\s+new\s+)?(?:training|run|experiment)\b|"
                      r"\btraining\s+(?:started|starts|begins)\b", re.I)

LOSS_KEYS = ("loss", "train_loss", "train/loss", "training_loss", "loss_train")
STEP_KEYS = ("step", "global_step", "iteration", "iter", "it", "trainer/global_step", "_step")
EPOCH_KEYS = ("epoch", "train/epoch")
MARKER_KEYS = ("event", "status", "state")
DONE_VALUES = {"end", "ended", "done", "finished", "complete", "completed", "success",
               "train_end", "training_end", "run_end", "training_complete"}
ERROR_VALUES = {"error", "failed", "failure", "crash", "crashed", "exception"}
START_VALUES = {"start", "started", "begin", "train_start", "training_start", "run_start"}


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


def _is_loss_key(key: object) -> bool:
    k = str(key).lower()
    return "loss" in k and "scal" not in k and not TRACKER_RE.search(k)


@dataclass
class LineInfo:
    step: int | None = None
    epoch: float | None = None
    loss: float | None = None
    error: str | None = None
    bad_loss: bool = False
    done: bool = False
    traceback: bool = False
    start: bool = False


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
    has_loss = info.loss is not None
    for k, v in obj.items():
        if not _is_loss_key(k):
            continue
        n = _num(v)
        if n is None:
            continue
        has_loss = True
        if info.loss is None:
            info.loss = n
        if not math.isfinite(n):
            info.error = f"{k}={v}"
            info.bad_loss = True
            break
    # Only whole marker values count. {"event": "validation complete"} and
    # {"message": "error rate 0.02"} are not the end of a run, and a line that still
    # carries a loss is a metrics row.
    for k in MARKER_KEYS:
        value = str(obj.get(k, "")).strip().lower()
        if value in ERROR_VALUES:
            info.error = info.error or value
        elif value in DONE_VALUES and not has_loss:
            info.done = True
        elif value in START_VALUES:
            info.start = True
    return info


def _bad_loss(line: str) -> str | None:
    for rx in (BAD_LOSS_RE, BAD_FIRST_RE):
        for m in rx.finditer(line):
            head = line[max(0, m.start() - 10):m.start()] + m.group("name")
            if not TRACKER_RE.search(head):
                return m.group(0).strip()
    return None


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
    if TRACEBACK_RE.search(line):
        info.traceback = True
        info.error = "Traceback"
        return info
    m = EXC_RE.match(line)
    if m and not RECOVERS_RE.search(line):
        info.error = line[m.start(1):].strip()
        return info
    if FATAL_RE.search(line) and not RECOVERS_RE.search(line):
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
    bad = _bad_loss(line)
    if bad:
        info.error = bad
        info.bad_loss = True
    if START_RE.search(line):
        info.start = True
    if (DONE_RE.search(line) and not NOT_FINAL_RE.search(line)) or (done_re and done_re.search(line)):
        info.done = True
    return info


def _fmt_epoch(e: float) -> str:
    return str(int(e)) if float(e).is_integer() else f"{e:.2f}"


@dataclass
class RunState:
    """Folds parsed lines into a status + detail string."""
    status: str = "idle"          # idle | run | done | needs | error
    step: int | None = None
    epoch: float | None = None
    loss: float | None = None
    error: str | None = None
    bad_loss: bool = False
    in_traceback: bool = False
    finished: bool = False        # a real final line was seen, not just silence
    lines: int = 0

    def _restart(self) -> None:
        lines = self.lines
        self.__dict__.update(RunState(status="run", lines=lines).__dict__)

    def feed(self, info: LineInfo, raw: str = "") -> None:
        self.lines += 1
        if info.start and not info.error:
            self._restart()               # a new run appended to the same log
        if self.status == "error":
            # Errors stay until a new run starts; only refine a traceback's message with
            # the exception line that ends it.
            if self.in_traceback and self.error == "Traceback" and info.error:
                self.error = info.error
            return
        moved_on = info.step is not None and (self.step is None or info.step > self.step)
        if self.finished and not moved_on and not info.error:
            return                        # trailing lines after the end (wandb summary etc.)
        if info.step is not None:
            self.step = info.step
        if info.epoch is not None:
            self.epoch = info.epoch
        if info.loss is not None:
            self.loss = info.loss
        if info.traceback:
            self.in_traceback = True
            self.status = "error"
            self.error = "Traceback"
            return
        if info.error:
            self.error = info.error
            self.bad_loss = info.bad_loss
            self.status = "error"
            return
        if info.done:
            self.status = "done"
            self.finished = True
            return
        self.finished = False
        if raw.strip():
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
            if self.bad_loss:
                where = f" s{self.step}" if self.step is not None else ""
                return f"NaN/inf loss{where}"
            return self.error or "error"
        if self.status == "done":
            p = self.progress()
            return ("done " + p) if p else "done"
        return self.progress() or "running"


class TrainWatcher:
    """Tails one file in a background thread and calls `emit(message)` with daemon
    "update" messages whenever the status or detail changes. A file that is rotated or
    truncated, even if it regrows past the old offset, is treated as a new run. The old
    run's status stays on the slot until the new file has content."""

    def __init__(self, path: str, name: str | None, emit: Callable[[dict], None], *,
                 stale_minutes: float = 10.0, stale_status: str = "needs",
                 done_pattern: str | None = None, poll: float = 1.0, from_start: bool = True,
                 clock: Callable[[], float] = time.monotonic):
        self.path = os.path.abspath(os.path.expanduser(path))
        self.name = name or os.path.splitext(os.path.basename(self.path))[0]
        self.key = f"train:{name}" if name else f"train:{self.path}"
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
        self._head = b""
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._partial = ""
        self._partial_flushed = False
        self._discard_first = False
        self._fresh = False          # next content belongs to a new run

    # -- feeding (also used directly by tests)
    def feed_text(self, text: str) -> None:
        if self._fresh and text:
            self._fresh = False
            self.state = RunState()
            self._last_sent = None
        parts = re.split(r"\r\n|\r|\n", self._partial + text)
        self._partial = parts.pop()  # incomplete last line
        self._partial_flushed = False
        if self._discard_first and parts:
            parts.pop(0)             # started mid-file: the first line is cut
            self._discard_first = False
        if len(self._partial) > MAX_PARTIAL:
            self._partial = self._partial[-MAX_PARTIAL:]
        for ln in parts:
            self.state.feed(parse_line(ln, self.done_re), ln)
        self._last_growth = self.clock()
        self._publish()

    def _flush_partial(self) -> None:
        """A final line with no newline still counts if it ends or fails the run."""
        if self._partial_flushed or not self._partial.strip():
            return
        self._partial_flushed = True
        info = parse_line(self._partial, self.done_re)
        if info.done or info.error:
            self.state.feed(info, self._partial)
            self._publish()

    def check_stale(self) -> None:
        if self.state.status == "run" and self.clock() - self._last_growth >= self.stale:
            mins = int(self.stale // 60)
            self.state.status = self.stale_status
            self._publish(detail=f"quiet {mins}m {self.state.progress()}".strip())

    def _publish(self, detail: str | None = None) -> None:
        st = self.state.status
        det = detail or self.state.detail()
        if (st, det) == self._last_sent:
            return
        self._last_sent = (st, det)
        self.emit({"op": "update", "source": "train", "key": self.key, "name": self.name,
                   "status": st, "detail": det, "log": self.path})

    # -- file tailing
    def _open(self, start: int | None = None) -> bool:
        try:
            fh = open(self.path, "rb", buffering=0)
            st = os.fstat(fh.fileno())
        except OSError:
            return False
        self._fh, self._ino = fh, st.st_ino
        if start is None:
            start = 0 if self.from_start else st.st_size
        if st.st_size - start > MAX_BACKLOG:
            start = st.st_size - MAX_BACKLOG
            self._discard_first = True
        self._seek(start)
        log.info("watching %s as %s", self.path, self.key)
        return True

    def _seek(self, pos: int) -> None:
        self._fh.seek(pos)
        self._pos = pos
        self._decoder.reset()
        self._partial = ""
        self._head = os.pread(self._fh.fileno(), HEAD_BYTES, 0)

    def _close(self) -> None:
        if self._fh is not None:
            self._fh.close()
        self._fh = None

    def _read_available(self) -> bool:
        got = False
        while True:
            data = self._fh.read(CHUNK)
            if not data:
                return got
            got = True
            self._pos += len(data)
            self.feed_text(self._decoder.decode(data))
            if self._stop.is_set():
                return got

    def _head_changed(self) -> bool:
        head = os.pread(self._fh.fileno(), HEAD_BYTES, 0)
        if head[:len(self._head)] != self._head:
            return True
        self._head = head
        return False

    def poll_once(self) -> None:
        if self._fh is None and not self._open():
            self.check_stale()
            return
        try:
            st = os.stat(self.path)
        except OSError:
            st = None
        if st is None or st.st_ino != self._ino:
            # Rotated or deleted. Lines written just before that are only on the old fd.
            log.info("%s was replaced", self.path)
            self._read_available()
            self._close()
            self._fresh = True
            if st is not None:
                self._open(0)
            self.check_stale()
            return
        if st.st_size < self._pos or self._head_changed():
            log.info("%s was truncated", self.path)
            self._seek(0)
            self._fresh = True
        if not self._read_available():
            self._flush_partial()
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
        self._close()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is None:
            self._close()
