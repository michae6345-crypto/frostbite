"""Slot model: six slots, assignment, lingering, selection, OLED text and glow colour.

Pure and clock-injected (every mutating call takes `now`) so it is easy to test.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from .device import NUM_SLOTS, OLED_COLS, Status, to_ascii

log = logging.getLogger("frostbite.state")

LINGER_DONE = 10 * 60.0     # finished slots stay green this long, then free
LINGER_ERROR = 30 * 60.0    # failed slots stay red a bit longer
QUIET_RUN = 60 * 60.0       # a Claude session this silent is not running: Stop never fires
                            # after an interrupt, and a turn can end without any event
DEAD_AFTER = 24 * 60 * 60.0 # any slot this silent is dead (crash, closed window, no SessionEnd)
ANSWER_GRACE = 15.0         # Notification arrives ~6 s after the dialog: ignore it once answered
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

# design.json protocol.status_colours, used for the glow ring (worst status wins).
STATUS_RGB = {
    Status.IDLE: (0xEE, 0xF2, 0xF5),
    Status.RUN: (0x3D, 0x8B, 0xFF),
    Status.DONE: (0x2F, 0xBF, 0x5B),
    Status.NEEDS: (0xFF, 0xB0, 0x20),
    Status.ERROR: (0xFF, 0x4D, 0x4F),
}
ICE_BLUE = (0x9F, 0xD8, 0xFF)
SEVERITY = [Status.ERROR, Status.NEEDS, Status.RUN, Status.DONE, Status.IDLE]


def clean(text: object, limit: int = 200) -> str:
    """ASCII, single-spaced, trimmed."""
    if text is None:
        return ""
    return " ".join(to_ascii(str(text)).split())[:limit]


def fit_lr(left: str, right: str, width: int = OLED_COLS) -> str:
    """Left text truncated so `right` sits flush at the right edge."""
    left, right = clean(left), clean(right)
    if not right:
        return left[:width]
    room = width - len(right) - 1
    if room <= 0:
        return right[:width]
    return fit_middle(left, room).ljust(room) + " " + right


def fit(text: str, width: int = OLED_COLS) -> str:
    return clean(text)[:width]


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
    kind: str = "permission"  # "permission" (Return answers it) or "question" (needs reading)


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
    def __init__(self, linger_done: float = LINGER_DONE, linger_error: float = LINGER_ERROR):
        self.slots: list[Slot | None] = [None] * NUM_SLOTS
        self.selected = 0
        self.linger_done = linger_done
        self.linger_error = linger_error
        self.quiet_run = QUIET_RUN
        self.dead_after = DEAD_AFTER
        self.overflow: dict[str, float] = {}  # sessions waiting on you with no slot to show it
        self._flash: tuple[str, float, float] | None = None

    # ------------------------------------------------------------------ lookup / assignment
    def find(self, key: str) -> int | None:
        for i, s in enumerate(self.slots):
            if s is not None and s.key == key:
                return i
        return None

    def _claim(self, key: str, now: float) -> int | None:
        for i, s in enumerate(self.slots):
            if s is None:
                return i
        # Full: reuse a finished slot, then an idle one. A red slot may not have been seen
        # yet, so it goes last. Running and waiting slots are never pushed out.
        for wanted in ((Status.DONE,), (Status.IDLE,), (Status.ERROR,)):
            cands = [(s.since, i) for i, s in enumerate(self.slots) if s and s.status in wanted]
            if cands:
                _, i = min(cands)
                log.info("slots full: evicting slot %d (%s) for %s", i + 1, self.slots[i].key, key)
                return i
        log.warning("slots full, all busy: ignoring %s", key)
        return None

    def statuses(self) -> list[Status]:
        return [s.status if s else Status.IDLE for s in self.slots]

    # ------------------------------------------------------------------ mutation
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
            i = self._claim(key, now)
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
            self._drop_same_tty(i, s, now)
        if tool is not None:
            s.tool = clean(tool)
        s.updated = now
        return i

    def _drop_same_tty(self, index: int, s: Slot, now: float) -> None:
        """One tty runs one Claude session, so an older slot on it is dead. Left in place it
        could pass the tty check and have Approve answer the wrong session."""
        tty = s.terminal.get("tty")
        if not tty or s.source != "claude":
            return
        for j, other in enumerate(self.slots):
            if j != index and other and other.source == "claude" and other.terminal.get("tty") == tty:
                log.info("slot %d freed: %s took over %s", j + 1, s.key, tty)
                self.slots[j] = None

    # ------------------------------------------------------------------ prompts
    def answer(self, index: int, now: float, *, status: Status, detail: str,
               all_prompts: bool = False) -> None:
        """A keystroke was sent for this slot. No hook fires at that moment, so close the
        prompt here. That also makes Approve one-shot."""
        s = self.slots[index]
        if s is None:
            return
        if all_prompts:
            s.pending.clear()
        elif s.pending:
            s.pending.pop(0)
        s.answered = now
        s.updated = now
        if s.pending:
            s.detail = s.pending[0].text
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
            limit = {Status.DONE: self.linger_done, Status.ERROR: self.linger_error}.get(s.status)
            quiet = now - s.updated
            if (limit is not None and now - s.since >= limit) or quiet >= self.dead_after:
                log.info("slot %d expired (%s %s)", i + 1, s.key, s.status.name.lower())
                self.slots[i] = None
                changed = True
            elif s.source == "claude" and s.status == Status.RUN and quiet >= self.quiet_run:
                log.info("slot %d went quiet (%s)", i + 1, s.key)
                s.status = Status.IDLE
                s.since = now
                s.detail = f"quiet {ago(quiet)}"
                changed = True
        return changed

    def select(self, index: int) -> None:
        self.selected = int(index) % NUM_SLOTS

    def flash(self, text: str, now: float, seconds: float = FLASH_SECONDS) -> None:
        self._flash = (clean(text), now, seconds)

    def flash_active(self, now: float) -> bool:
        return self._flash is not None and 0 <= now - self._flash[1] < self._flash[2]

    # ------------------------------------------------------------------ apply IPC messages
    def apply(self, msg: dict, now: float) -> bool:
        """Apply one IPC message (from frostbite-hook, frostbite-ctl or a watcher).
        Returns True if anything visible may have changed."""
        op = msg.get("op")
        if op == "update":
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
                prompt = Prompt(clean(detail), tool, agent, msg.get("kind") or "permission")
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
            return False
        self.overflow.pop(key, None)
        s = self.slots[i]
        if prompt is not None and not (prompt.kind == "question" and any(
                p.kind == "question" and p.tool == prompt.tool and p.agent == prompt.agent
                for p in s.pending)):
            s.pending = (s.pending + [prompt])[-MAX_PENDING:]
        if s.pending:
            s.detail = s.pending[0].text  # the oldest prompt is the dialog on screen
        return True

    # ------------------------------------------------------------------ rendering
    def oled_lines(self, now: float) -> tuple[str, str]:
        i = self.selected
        s = self.slots[i]
        if s is None:
            line0 = fit_lr(f"#{i + 1} empty", "")
            line1 = self.summary()
        else:
            line0 = fit_lr(s.title(i), STATUS_WORD[s.status])
            if s.detail:
                line1 = fit(s.detail)
            elif s.status in (Status.DONE, Status.ERROR):
                line1 = fit(f"{s.status.name.lower()} {ago(now - s.since)} ago")
            else:
                line1 = fit(f"{ago(now - s.updated)} ago")
        if self.flash_active(now):
            line1 = fit(self._flash[0])
        return line0, line1

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
            return (*STATUS_RGB[Status.ERROR], 160)
        if Status.NEEDS in sts or self.overflow:
            return (*STATUS_RGB[Status.NEEDS], 160)
        if Status.RUN in sts:
            return (*ICE_BLUE, 110)
        return (*ICE_BLUE, 50)

    def to_dict(self, now: float) -> dict:
        return {
            "selected": self.selected + 1,
            "slots": [s.to_dict(i) if s else None for i, s in enumerate(self.slots)],
            "oled": list(self.oled_lines(now)),
        }
