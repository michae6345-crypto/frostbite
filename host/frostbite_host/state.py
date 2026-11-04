"""Slot model: six slots, assignment, lingering, selection, OLED text and glow colour.
Every mutating call takes `now`, so there is no clock here."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .device import NUM_SLOTS, OLED_COLS, Status, to_ascii

log = logging.getLogger("frostbite.state")

LINGER_DONE = 10 * 60.0     # finished slots stay green this long, then free
LINGER_ERROR = 30 * 60.0    # failed slots stay red a bit longer
QUIET_RUN = 60 * 60.0       # silent this long inside one tool call: Stop never fires after an
                            # interrupt, and cancelling a tool fires nothing either
QUIET_TURN = 15 * 60.0      # silent this long with no tool in flight
QUIET_NEEDS = 30 * 60.0     # an amber slot nobody can answer from the pad stops being amber
DEAD_AFTER = 24 * 60 * 60.0 # any slot this silent is dead (crash, closed window, no SessionEnd)
ANSWER_GRACE = 15.0         # Notification arrives ~6 s after the dialog: ignore it once answered
PAGE_SECONDS = 2.0          # a prompt too long for the OLED pages through at this rate
OVERFLOW_TTL = 60 * 60.0    # how long a session with no free slot keeps the glow amber
MAX_PENDING = 16
FLASH_SECONDS = 3.0

STATUS_WORD = {
    Status.IDLE: "IDLE",
    Status.RUN: "RUN",
    Status.DONE: "DONE",
    Status.NEEDS: "WAIT",
    Status.ERROR: "ERR",
}

# Glow colours. The first two are design.json protocol.status_colours.
ERROR_RGB = (0xFF, 0x4D, 0x4F)
NEEDS_RGB = (0xFF, 0xB0, 0x20)
ICE_BLUE = (0x9F, 0xD8, 0xFF)
SEVERITY = [Status.ERROR, Status.NEEDS, Status.RUN, Status.DONE, Status.IDLE]


def clean(text: object, limit: int = 200) -> str:
    """ASCII, single-spaced, trimmed."""
    if text is None:
        return ""
    return " ".join(to_ascii(str(text)).split())[:limit]


def fit_lr(left: str, right: str) -> str:
    """Left text truncated so `right` sits flush at the right edge."""
    left, right = clean(left), clean(right)
    if not right:
        return left[:OLED_COLS]
    room = OLED_COLS - len(right) - 1
    if room <= 0:
        return right[:OLED_COLS]
    return fit_middle(left, room).ljust(room) + " " + right


def fit(text: str) -> str:
    return clean(text)[:OLED_COLS]


def fit_middle(text: str, width: int) -> str:
    """Too long: keep both ends, since project names tend to share a start or an end."""
    if len(text) <= width:
        return text
    tail = (width - 1) // 2
    return text[:width - 1 - tail] + "~" + (text[-tail:] if tail else "")


def ago(seconds: float) -> str:
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    return f"{s // 3600}h{(s % 3600) // 60:02d}"


@dataclass
class Prompt:
    """One open question from Claude Code. Dialogs queue, so a slot can hold several."""
    text: str                 # what the OLED shows, e.g. "Bash(npm test)?"
    tool: str = ""            # matched against PostToolUse to close it
    agent: str | None = ""    # subagent id, "" for the main thread, None if unknown
    kind: str = "permission"  # "permission", or "question" (only the terminal can answer it)
    request: str | None = None  # id of the hook waiting on the pad; None once nothing is waiting


@dataclass
class Slot:
    key: str                 # stable source id, e.g. "claude:<session_id>", "train:<name>", "slot:3"
    source: str              # "claude" | "train" | "ctl"
    name: str
    status: Status = Status.IDLE
    detail: str = ""
    updated: float = 0.0     # last event of any kind
    since: float = 0.0       # when `status` last changed
    cwd: str | None = None
    log_path: str | None = None
    terminal: dict = field(default_factory=dict)  # {"bundle": ..., "app": ..., "tty": ...}
    tool: str = ""           # last tool description (Claude), used for "needs" detail
    pending: list[Prompt] = field(default_factory=list)  # oldest first
    answered: float = -1e12  # when a prompt was last closed
    tool_open: bool = False  # a PreToolUse has had no PostToolUse yet

    def title(self, index: int) -> str:
        n = index + 1
        room = OLED_COLS - 5  # what is left next to a 4-letter status word
        if self.source == "claude":
            full, short = f"claude#{n} {self.name}", f"c#{n} {self.name}"
        elif self.source == "train":
            full, short = f"train#{n} {self.name}", f"t#{n} {self.name}"
        else:
            full = short = f"#{n} {self.name}"
        return (full if len(full) <= room else short).strip()

    def to_dict(self, index: int) -> dict:
        return {
            "slot": index + 1, "key": self.key, "source": self.source, "name": self.name,
            "status": self.status.name.lower(), "detail": self.detail, "updated": self.updated,
            "since": self.since, "cwd": self.cwd, "log": self.log_path, "terminal": self.terminal,
            "pending": [p.text for p in self.pending],
        }


class Board:
    def __init__(self, linger_done: float = LINGER_DONE):
        self.slots: list[Slot | None] = [None] * NUM_SLOTS
        self.selected = 0
        self.linger_done = linger_done
        self.overflow: dict[str, float] = {}  # sessions waiting on you with no slot to show it
        self._flash: tuple[str, float] | None = None

    def find(self, key: str) -> int | None:
        for i, s in enumerate(self.slots):
            if s is not None and s.key == key:
                return i
        return None

    def _claim(self, key: str) -> int | None:
        if None in self.slots:
            return self.slots.index(None)
        # Full: reuse a finished slot, then an idle one. A red slot may not have been seen
        # yet, so it goes last. Running and waiting slots are never pushed out.
        for wanted in (Status.DONE, Status.IDLE, Status.ERROR):
            cands = [(s.since, i) for i, s in enumerate(self.slots)
                     if s.status == wanted and not s.tool_open]
            if cands:
                _, i = min(cands)
                log.info("slots full: evicting slot %d (%s) for %s", i + 1, self.slots[i].key, key)
                return i
        log.warning("slots full, all busy: ignoring %s", key)
        return None

    def statuses(self) -> list[Status]:
        return [s.status if s else Status.IDLE for s in self.slots]

    def update(self, key: str, source: str, now: float, *, name: str | None = None,
               status: Status | None = None, detail: str | None = None, cwd: str | None = None,
               log_path: str | None = None, terminal: dict | None = None, tool: str | None = None,
               slot: int | None = None) -> int | None:
        """Create or update the slot for `key`. Returns the slot index or None if no room.
        Arguments left as None keep their previous value."""
        i = self.find(key)
        if slot is not None:
            if not 0 <= slot < NUM_SLOTS:
                raise ValueError(f"slot out of range: {slot}")
            if i is not None and i != slot:
                self.slots[i] = None
            if self.slots[slot] is not None and self.slots[slot].key != key:
                log.info("slot %d: %s replaced by %s", slot + 1, self.slots[slot].key, key)
                self.slots[slot] = None
            i = slot
        if i is None:
            i = self._claim(key)
            if i is None:
                return None
            self.slots[i] = None
        s = self.slots[i]
        if s is None:
            s = Slot(key=key, source=source, name=clean(name or key, 40), updated=now, since=now,
                     status=status if status is not None else Status.IDLE)
            self.slots[i] = s
            log.info("slot %d <- %s (%s)", i + 1, key, s.name)
        sticky = s.source == "claude"  # a session stays its project after `cd packages/ui`
        if name and not sticky:
            s.name = clean(name, 40)
        if status is not None and status != s.status:
            s.status = Status(status)
            s.since = now
        if detail is not None:
            s.detail = clean(detail)
        if cwd and not (sticky and s.cwd):
            s.cwd = cwd
        if log_path:
            s.log_path = log_path
        if terminal:
            s.terminal.update({k: v for k, v in terminal.items() if v})
            if "tty" in terminal and not terminal["tty"]:
                s.terminal.pop("tty", None)  # a failed lookup must not keep proving the old tab
            self._drop_same_tty(i, s)
        if tool is not None:
            s.tool = clean(tool)
        s.updated = now
        return i

    def _drop_same_tty(self, index: int, s: Slot) -> None:
        """A finished slot on a tty a new session now uses is dead. A running or waiting one
        might be a nested `claude -p`, so it stays."""
        tty = s.terminal.get("tty")
        if not tty or s.source != "claude":
            return
        for j, other in enumerate(self.slots):
            if (j != index and other and other.source == "claude" and other.terminal.get("tty") == tty
                    and other.status in (Status.IDLE, Status.DONE)):
                log.info("slot %d freed: %s took over %s", j + 1, s.key, tty)
                self.slots[j] = None

    @staticmethod
    def _showing(s: Slot) -> Prompt | None:
        """The prompt a slot shows: the oldest the pad can answer, else the oldest open."""
        return next((p for p in s.pending if p.request), s.pending[0] if s.pending else None)

    def find_request(self, request: str) -> tuple[int, Prompt] | None:
        for i, s in enumerate(self.slots):
            if s is not None:
                for p in s.pending:
                    if p.request == request:
                        return i, p
        return None

    def shown_request(self, now: float) -> str | None:
        """The request on the OLED right now, if any. A flash hides it."""
        s = self.slots[self.selected]
        if s is None or not s.pending or self.flash_active(now):
            return None
        return self._showing(s).request

    def has_live_request(self, index: int) -> bool:
        s = self.slots[index]
        return s is not None and any(p.request for p in s.pending)

    def release_request(self, request: str) -> None:
        """Nothing is waiting on the pad any more. The prompt itself may still be on screen."""
        found = self.find_request(request)
        if found:
            found[1].request = None
            s = self.slots[found[0]]
            s.detail = self._showing(s).text

    def answer(self, index: int, now: float, *, status: Status, detail: str,
               request: str | None = None, all_prompts: bool = False) -> None:
        """A press answered a request, or Stop ended the turn. No hook fires at that moment,
        so close it here."""
        s = self.slots[index]
        if s is None:
            return
        if all_prompts:
            s.pending.clear()
        else:
            s.pending = [p for p in s.pending if p.request != request]
        s.answered = now
        s.updated = now
        if s.pending:
            s.detail = self._showing(s).text
            return
        if s.status != status:
            s.status = status
            s.since = now
        s.detail = clean(detail)

    def _close_prompt(self, s: Slot, resolve: dict, now: float) -> bool:
        tool, agent = resolve.get("tool") or "", resolve.get("agent") or ""
        for p in s.pending:
            # A prompt raised by a Notification may know neither, so any finished tool closes it.
            if (not p.tool or p.tool == clean(tool)) and (p.agent is None or p.agent == agent):
                s.pending.remove(p)
                s.answered = now
                return True
        return False

    def free(self, key: str) -> bool:
        self.overflow.pop(key, None)
        i = self.find(key)
        if i is None:
            return False
        log.info("slot %d freed (%s)", i + 1, key)
        self.slots[i] = None
        return True

    def clear_slot(self, index: int) -> bool:
        if 0 <= index < NUM_SLOTS and self.slots[index] is not None:
            self.slots[index] = None
            return True
        return False

    def expire(self, now: float) -> bool:
        changed = False
        for key, seen in list(self.overflow.items()):
            if not 0 <= now - seen < OVERFLOW_TTL:
                del self.overflow[key]
                changed = True
        for i, s in enumerate(self.slots):
            if s is None:
                continue
            s.since, s.updated = min(s.since, now), min(s.updated, now)  # clock stepped back
            limits = {Status.DONE: self.linger_done, Status.ERROR: LINGER_ERROR}
            if s.source == "train":
                limits[Status.IDLE] = self.linger_done  # a run that went quiet
            limit = limits.get(s.status)
            quiet = now - s.updated
            if (limit is not None and now - s.since >= limit) or quiet >= DEAD_AFTER:
                log.info("slot %d expired (%s %s)", i + 1, s.key, s.status.name.lower())
                self.slots[i] = None
                changed = True
            elif s.source == "claude" and (
                    (s.status == Status.RUN and quiet >= (QUIET_RUN if s.tool_open else QUIET_TURN))
                    or (s.status == Status.NEEDS and quiet >= QUIET_NEEDS and not self.has_live_request(i))):
                log.info("slot %d went quiet (%s)", i + 1, s.key)
                s.status = Status.IDLE
                s.since = now
                s.detail = f"quiet {ago(quiet)}"
                s.pending.clear()
                changed = True
        return changed

    def select(self, index: int) -> None:
        self.selected = int(index) % NUM_SLOTS

    def flash(self, text: str, now: float) -> None:
        self._flash = (clean(text), now)

    def flash_active(self, now: float) -> bool:
        return self._flash is not None and 0 <= now - self._flash[1] < FLASH_SECONDS

    def apply(self, msg: dict, now: float) -> bool:
        """Apply one IPC message (from frostbite-hook, frostbite-ctl or a watcher).
        Returns True if anything visible may have changed."""
        op = msg.get("op")
        if op in ("update", "permission"):
            return self._apply_update(msg, now)
        if op == "free":
            return self.free(str(msg.get("key")))
        if op == "set_slot":
            slot = int(msg["slot"])
            return self.update(
                f"slot:{slot + 1}", "ctl", now, name=msg.get("name") or f"slot {slot + 1}",
                status=Status.parse(msg.get("status", "idle")), detail=msg.get("detail", ""),
                slot=slot, log_path=msg.get("log"),
            ) is not None
        if op == "clear_slot":
            return self.clear_slot(int(msg["slot"]))
        if op == "select":
            self.select(int(msg["slot"]))
            return True
        return False

    def _apply_update(self, msg: dict, now: float) -> bool:
        key = msg.get("key")
        terminal = msg.get("terminal")
        if not key or not isinstance(key, str):
            return False
        # Check everything first: a bad message must not leave half a slot behind.
        if terminal is not None and not isinstance(terminal, dict):
            raise ValueError("terminal must be an object")
        status = msg.get("status")
        st = Status.parse(status) if status is not None else None
        detail = msg.get("detail")
        i = self.find(key)
        prev = self.slots[i] if i is not None else None
        source = prev.source if prev else msg.get("source", "ctl")
        prompt = None
        if source == "claude":
            if prev and msg.get("clears"):
                prev.pending.clear()
            resolve = msg.get("resolve")
            closed = bool(prev and isinstance(resolve, dict) and self._close_prompt(prev, resolve, now))
            if st == Status.NEEDS:
                if msg.get("notification") and prev:
                    # A Notification names no tool, so it adds nothing to an open prompt,
                    # and one arriving just after an answer is about the closed dialog.
                    if prev.pending or now - prev.answered < ANSWER_GRACE:
                        prev.updated = now
                        return False
                if detail is None:
                    hint = msg.get("tool_hint")
                    if prev and prev.tool and (not hint or prev.tool.startswith(hint)):
                        detail = prev.tool + "?"
                    else:
                        detail = (hint or "permission") + "?"
                tool = clean(msg.get("tool"))
                agent = msg.get("agent") or ""
                if msg.get("notification"):
                    agent = None
                    hint = msg.get("tool_hint")
                    if prev and prev.tool and hint and prev.tool.startswith(hint):
                        tool = prev.tool
                prompt = Prompt(clean(detail), tool, agent, msg.get("kind") or "permission",
                                msg.get("id") if msg.get("op") == "permission" else None)
            elif prev and prev.pending:
                # Something else in this session moved on; the open prompt is still open.
                st, detail = None, None
            elif closed:
                detail = msg.get("detail", prev.tool or "working")
        if msg.get("register_only") and i is None and st is None:
            st = Status.IDLE
        i = self.update(
            key, msg.get("source", "ctl"), now, name=msg.get("name"), status=st,
            detail=detail, cwd=msg.get("cwd"), log_path=msg.get("log"),
            terminal=terminal, tool=msg.get("tool"), slot=msg.get("slot"),
        )
        if i is None:
            if st == Status.NEEDS:
                self.overflow[key] = now
            else:
                self.overflow.pop(key, None)  # answered: no longer waiting on you
            return False
        self.overflow.pop(key, None)
        s = self.slots[i]
        if source == "claude":
            if msg.get("tool") and status == "run":
                s.tool_open = True
            elif msg.get("resolve") or msg.get("clears"):
                s.tool_open = False
        if prompt is not None and not (prompt.kind == "question" and any(
                p.kind == "question" and p.tool == prompt.tool and p.agent == prompt.agent
                for p in s.pending)):
            s.pending = (s.pending + [prompt])[-MAX_PENDING:]
        if s.pending:
            s.detail = self._showing(s).text
        return True

    def oled_lines(self, now: float) -> tuple[str, str]:
        i = self.selected
        s = self.slots[i]
        if s is None:
            line0 = fit_lr(f"#{i + 1} empty", "")
            line1 = self.summary()
        else:
            line0 = fit_lr(s.title(i), STATUS_WORD[s.status])
            if s.detail:
                line1 = self._paged(s.detail, now) if s.pending else fit(s.detail)
            elif s.status in (Status.DONE, Status.ERROR):
                line1 = fit(f"{s.status.name.lower()} {ago(now - s.since)} ago")
            else:
                line1 = fit(f"{ago(now - s.updated)} ago")
        if self.flash_active(now):
            line1 = fit(self._flash[0])
        return line0, line1

    @staticmethod
    def _paged(text: str, now: float) -> str:
        """A long prompt pages through, so the tail of a command can be read before answering."""
        if len(text) <= OLED_COLS:
            return text
        size = OLED_COLS - 1
        pages = [text[i:i + size] for i in range(0, len(text), size)]
        page = int(now // PAGE_SECONDS) % len(pages)
        return pages[page] + (">" if page < len(pages) - 1 else "")

    def summary(self) -> str:
        counts = {st: 0 for st in Status}
        for s in self.slots:
            if s is not None:
                counts[s.status] += 1
        parts = [f"{counts[st]} {STATUS_WORD[st].lower()}" for st in SEVERITY if counts[st]]
        return fit(" ".join(parts) if parts else "no agents")

    def glow(self) -> tuple[int, int, int, int]:
        """Light-gap colour: red if anything failed, amber if anything waits on you,
        otherwise the ice-blue case glow (dimmer when nothing is running)."""
        sts = {s.status for s in self.slots if s is not None}
        if Status.ERROR in sts:
            return (*ERROR_RGB, 160)
        if Status.NEEDS in sts or self.overflow:
            return (*NEEDS_RGB, 160)
        if Status.RUN in sts:
            return (*ICE_BLUE, 110)
        return (*ICE_BLUE, 50)

    def to_dict(self, now: float) -> dict:
        return {
            "selected": self.selected + 1,
            "slots": [s.to_dict(i) if s else None for i, s in enumerate(self.slots)],
            "oled": list(self.oled_lines(now)),
        }
