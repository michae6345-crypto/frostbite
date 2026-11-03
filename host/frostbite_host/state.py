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
    return left[:room].ljust(room) + " " + right


def fit(text: str, width: int = OLED_COLS) -> str:
    return clean(text)[:width]


def ago(seconds: float) -> str:
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    return f"{s // 3600}h{(s % 3600) // 60:02d}"


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

    def title(self, index: int) -> str:
        n = index + 1
        if self.source == "claude":
            return f"claude#{n} {self.name}".strip()
        if self.source == "train":
            return f"train#{n} {self.name}".strip()
        return f"#{n} {self.name}".strip()

    def to_dict(self, index: int) -> dict:
        return {
            "slot": index + 1, "key": self.key, "source": self.source, "name": self.name,
            "status": self.status.name.lower(), "detail": self.detail, "updated": self.updated,
            "since": self.since, "cwd": self.cwd, "log": self.log_path, "terminal": self.terminal,
        }


class Board:
    def __init__(self, linger_done: float = LINGER_DONE, linger_error: float = LINGER_ERROR):
        self.slots: list[Slot | None] = [None] * NUM_SLOTS
        self.selected = 0
        self.linger_done = linger_done
        self.linger_error = linger_error
        self._flash: tuple[str, float] | None = None

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
        # Full: evict the oldest lingering done/error slot, then the oldest idle one.
        for wanted in ((Status.DONE, Status.ERROR), (Status.IDLE,)):
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
        if name:
            s.name = clean(name, 40)
        if status is not None and status != s.status:
            s.status = Status(status)
            s.since = now
        if detail is not None:
            s.detail = clean(detail)
        if cwd:
            s.cwd = cwd
        if log_path:
            s.log_path = log_path
        if terminal:
            s.terminal.update({k: v for k, v in terminal.items() if v})
        if tool is not None:
            s.tool = clean(tool)
        s.updated = now
        return i

    def free(self, key: str) -> bool:
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
        for i, s in enumerate(self.slots):
            if s is None:
                continue
            limit = {Status.DONE: self.linger_done, Status.ERROR: self.linger_error}.get(s.status)
            if limit is not None and now - s.since >= limit:
                log.info("slot %d expired (%s %s)", i + 1, s.key, s.status.name.lower())
                self.slots[i] = None
                changed = True
        return changed

    def select(self, index: int) -> None:
        self.selected = int(index) % NUM_SLOTS

    def flash(self, text: str, now: float, seconds: float = FLASH_SECONDS) -> None:
        self._flash = (clean(text), now + seconds)

    def flash_active(self, now: float) -> bool:
        return self._flash is not None and now < self._flash[1]

    # ------------------------------------------------------------------ apply IPC messages
    def apply(self, msg: dict, now: float) -> bool:
        """Apply one IPC message (from frostbite-hook, frostbite-ctl or a watcher).
        Returns True if anything visible may have changed."""
        op = msg.get("op")
        if op == "update":
            key = msg.get("key")
            if not key:
                return False
            status = msg.get("status")
            st = Status.parse(status) if status is not None else None
            detail = msg.get("detail")
            i = self.find(key)
            prev = self.slots[i] if i is not None else None
            if st == Status.NEEDS and detail is None:
                hint = msg.get("tool_hint")
                if prev and prev.tool and (not hint or prev.tool.startswith(hint)):
                    detail = prev.tool + "?"
                else:
                    detail = (hint or "permission") + "?"
            if msg.get("register_only") and i is None and st is None:
                st = Status.IDLE
            return self.update(
                key, msg.get("source", "ctl"), now, name=msg.get("name"), status=st,
                detail=detail, cwd=msg.get("cwd"), log_path=msg.get("log"),
                terminal=msg.get("terminal"), tool=msg.get("tool"), slot=msg.get("slot"),
            ) is not None
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
        if Status.NEEDS in sts:
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
