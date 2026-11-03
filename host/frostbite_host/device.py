"""Raw HID link to the Frostbite pad.

Protocol (design.json "protocol"): 32-byte reports, byte 0 = command, unused bytes zero.

host -> device
  0x01 SET_SLOT      [0x01, slot 0-5, status]
  0x02 SET_ALL       [0x02, s0..s5]
  0x03 OLED_LINE     [0x03, line 0-1, len, up to 21 ASCII bytes]
  0x04 SET_GLOW      [0x04, r, g, b, brightness]
  0x05 PING          [0x05]
  0x06 SET_SELECTED  [0x06, slot 0-5]
device -> host
  0x05 PING reply    [0x05, protocol_version, selected_slot]
  0x81 KEY           [0x81, key index 0-8, action 1=tap 2=hold]
  0x82 ENCODER       [0x82, 1=cw / 0xFF=ccw, selected_slot after the move]

The firmware falls back to plain keycodes after 5 s without a PING, so the link
pings every 2 s and reconnects on its own after an unplug.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Protocol

log = logging.getLogger("frostbite.device")

USAGE_PAGE = 0xFF60
USAGE = 0x61
REPORT_LEN = 32
PROTOCOL_VERSION = 1
NUM_SLOTS = 6
OLED_COLS = 21
PING_INTERVAL = 2.0


class Status(IntEnum):
    IDLE = 0
    RUN = 1
    DONE = 2
    NEEDS = 3
    ERROR = 4

    @classmethod
    def parse(cls, word: str) -> "Status":
        w = str(word).strip().lower()
        aliases = {
            "idle": cls.IDLE, "run": cls.RUN, "running": cls.RUN, "working": cls.RUN,
            "done": cls.DONE, "ok": cls.DONE, "success": cls.DONE, "finished": cls.DONE,
            "needs": cls.NEEDS, "wait": cls.NEEDS, "waiting": cls.NEEDS, "ask": cls.NEEDS,
            "error": cls.ERROR, "err": cls.ERROR, "fail": cls.ERROR, "failed": cls.ERROR,
            "failure": cls.ERROR,
        }
        if w in aliases:
            return aliases[w]
        if w.isdigit() and int(w) in cls._value2member_map_:
            return cls(int(w))
        raise ValueError(f"unknown status {word!r}")


class Cmd(IntEnum):
    SET_SLOT = 0x01
    SET_ALL = 0x02
    OLED_LINE = 0x03
    SET_GLOW = 0x04
    PING = 0x05
    SET_SELECTED = 0x06
    KEY = 0x81
    ENCODER = 0x82


KEY_NAMES = ["agent1", "agent2", "agent3", "agent4", "agent5", "agent6", "approve", "talk", "stop"]
KEY_APPROVE, KEY_TALK, KEY_STOP = 6, 7, 8
TAP, HOLD = 1, 2
CW, CCW = 1, 0xFF


# --------------------------------------------------------------------------- messages

@dataclass(frozen=True)
class SetSlot:
    slot: int
    status: Status


@dataclass(frozen=True)
class SetAll:
    statuses: tuple[Status, ...]


@dataclass(frozen=True)
class OledLine:
    line: int
    text: str


@dataclass(frozen=True)
class SetGlow:
    r: int
    g: int
    b: int
    brightness: int


@dataclass(frozen=True)
class Ping:
    pass


@dataclass(frozen=True)
class SetSelected:
    slot: int


@dataclass(frozen=True)
class PingReply:
    version: int
    selected: int


@dataclass(frozen=True)
class KeyEvent:
    key: int
    action: int  # TAP or HOLD

    @property
    def name(self) -> str:
        return KEY_NAMES[self.key] if 0 <= self.key < len(KEY_NAMES) else f"key{self.key}"


@dataclass(frozen=True)
class EncoderEvent:
    direction: int  # +1 or -1
    selected: int


@dataclass(frozen=True)
class Unknown:
    raw: bytes


HostMsg = SetSlot | SetAll | OledLine | SetGlow | Ping | SetSelected
DeviceMsg = PingReply | KeyEvent | EncoderEvent | Unknown


# --------------------------------------------------------------------------- encoding

def _report(*payload: int) -> bytes:
    if len(payload) > REPORT_LEN:
        raise ValueError("report too long")
    for b in payload:
        if not 0 <= b <= 0xFF:
            raise ValueError(f"byte out of range: {b}")
    return bytes(payload) + bytes(REPORT_LEN - len(payload))


def _slot(slot: int) -> int:
    if not 0 <= slot < NUM_SLOTS:
        raise ValueError(f"slot out of range: {slot}")
    return slot


def to_ascii(text: str) -> str:
    """Printable ASCII only (0x20-0x7E): accents are stripped, whitespace controls become
    spaces, anything else becomes '?'. Spaces are preserved (layout padding)."""
    import unicodedata

    subs = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-",
            "—": "-", "…": "...", "→": ">", "×": "x"}
    text = unicodedata.normalize("NFKD", "".join(subs.get(c, c) for c in str(text)))
    out = []
    for ch in text:
        if unicodedata.combining(ch):
            continue
        if ch in "\t\r\n\v\f":
            ch = " "
        out.append(ch if 0x20 <= ord(ch) <= 0x7E else "?")
    return "".join(out)


def encode(msg: HostMsg) -> bytes:
    match msg:
        case SetSlot(slot, status):
            return _report(Cmd.SET_SLOT, _slot(slot), int(status))
        case SetAll(statuses):
            if len(statuses) != NUM_SLOTS:
                raise ValueError("SET_ALL needs 6 statuses")
            return _report(Cmd.SET_ALL, *(int(s) for s in statuses))
        case OledLine(line, text):
            if line not in (0, 1):
                raise ValueError("line must be 0 or 1")
            data = to_ascii(text)[:OLED_COLS].encode("ascii")
            return _report(Cmd.OLED_LINE, line, len(data), *data)
        case SetGlow(r, g, b, brightness):
            return _report(Cmd.SET_GLOW, r, g, b, brightness)
        case Ping():
            return _report(Cmd.PING)
        case SetSelected(slot):
            return _report(Cmd.SET_SELECTED, _slot(slot))
    raise TypeError(f"not a host message: {msg!r}")


def encode_device(msg: DeviceMsg) -> bytes:
    """Device-side encoding (used by FakeDevice and tests)."""
    match msg:
        case PingReply(version, selected):
            return _report(Cmd.PING, version, selected)
        case KeyEvent(key, action):
            return _report(Cmd.KEY, key, action)
        case EncoderEvent(direction, selected):
            return _report(Cmd.ENCODER, CW if direction > 0 else CCW, selected)
        case Unknown(raw):
            return bytes(raw[:REPORT_LEN]).ljust(REPORT_LEN, b"\0")
    raise TypeError(f"not a device message: {msg!r}")


def _norm(report: bytes | list[int]) -> bytes:
    data = bytes(report)
    return data[:REPORT_LEN].ljust(REPORT_LEN, b"\0")


def decode_host(report: bytes | list[int]) -> HostMsg | Unknown:
    """Decode a host->device report (what the firmware receives)."""
    r = _norm(report)
    cmd = r[0]
    try:
        if cmd == Cmd.SET_SLOT:
            return SetSlot(r[1], Status(r[2]))
        if cmd == Cmd.SET_ALL:
            return SetAll(tuple(Status(b) for b in r[1:7]))
        if cmd == Cmd.OLED_LINE:
            n = min(r[2], OLED_COLS)
            return OledLine(r[1], r[3:3 + n].decode("ascii", "replace"))
        if cmd == Cmd.SET_GLOW:
            return SetGlow(r[1], r[2], r[3], r[4])
        if cmd == Cmd.PING:
            return Ping()
        if cmd == Cmd.SET_SELECTED:
            return SetSelected(r[1])
    except ValueError:
        pass
    return Unknown(r)


def decode_device(report: bytes | list[int]) -> DeviceMsg:
    """Decode a device->host report. Unknown or malformed reports become Unknown."""
    r = _norm(report)
    cmd = r[0]
    if cmd == Cmd.PING:
        return PingReply(r[1], r[2])
    if cmd == Cmd.KEY and r[1] < len(KEY_NAMES) and r[2] in (TAP, HOLD):
        return KeyEvent(r[1], r[2])
    if cmd == Cmd.ENCODER and r[1] in (CW, CCW):
        return EncoderEvent(1 if r[1] == CW else -1, r[2])
    return Unknown(r)


def describe(msg: object) -> str:
    match msg:
        case SetAll(statuses):
            return "SET_ALL " + " ".join(s.name.lower() for s in statuses)
        case SetSlot(slot, status):
            return f"SET_SLOT {slot} {status.name.lower()}"
        case OledLine(line, text):
            return f"OLED_LINE {line} {text!r}"
        case SetGlow(r, g, b, br):
            return f"SET_GLOW #{r:02x}{g:02x}{b:02x} @{br}"
        case Ping():
            return "PING"
        case SetSelected(slot):
            return f"SET_SELECTED {slot}"
    return repr(msg)


# --------------------------------------------------------------------------- transports

class Transport(Protocol):
    def write(self, report: bytes) -> None: ...
    def read(self, timeout_ms: int) -> bytes | None: ...
    def close(self) -> None: ...


class HidTransport:
    """A real pad, found by Raw HID usage page / usage."""

    def __init__(self, dev, info: dict):
        self._dev = dev
        self.info = info

    @classmethod
    def find(cls) -> list[dict]:
        import hid

        return [
            d for d in hid.enumerate()
            if d.get("usage_page") == USAGE_PAGE and d.get("usage") == USAGE
        ]

    @classmethod
    def open(cls) -> "HidTransport | None":
        import hid

        for info in cls.find():
            dev = hid.device()
            try:
                dev.open_path(info["path"])
            except OSError as e:
                log.debug("open %s failed: %s", info.get("path"), e)
                continue
            log.info("opened %s %s (%04x:%04x)", info.get("manufacturer_string"),
                     info.get("product_string"), info.get("vendor_id", 0), info.get("product_id", 0))
            return cls(dev, info)
        return None

    def write(self, report: bytes) -> None:
        # Report ID 0 prefix: QMK's raw HID interface has no report IDs.
        n = self._dev.write(b"\x00" + _norm(report))
        if n < 0:
            raise OSError("hid write failed")

    def read(self, timeout_ms: int) -> bytes | None:
        data = self._dev.read(REPORT_LEN, timeout_ms)
        return bytes(data) if data else None

    def close(self) -> None:
        try:
            self._dev.close()
        except Exception:  # noqa: BLE001
            pass


class DryRunTransport:
    """Prints what would be sent; never receives anything."""

    def __init__(self, out=print):
        self.out = out
        self._pinged = False

    def write(self, report: bytes) -> None:
        msg = decode_host(report)
        if isinstance(msg, Ping):
            if self._pinged:
                return
            self._pinged = True
            self.out("[dry-run] -> PING (further pings every 2 s not shown)")
            return
        self.out(f"[dry-run] -> {describe(msg)}   {report[:8].hex(' ')}...")

    def read(self, timeout_ms: int) -> bytes | None:
        time.sleep(timeout_ms / 1000)
        return None

    def close(self) -> None:
        pass


@dataclass
class FakeDevice:
    """Simulated firmware. Records every report, answers PING, emits KEY/ENCODER on demand.

    Use `press()`, `turn()`, `unplug()`, `replug()` from tests; inspect `messages`,
    `slots`, `oled`, `selected`, `glow`.
    """

    version: int = PROTOCOL_VERSION
    plugged: bool = True
    reports: list[bytes] = field(default_factory=list)
    messages: list[object] = field(default_factory=list)
    slots: list[Status] = field(default_factory=lambda: [Status.IDLE] * NUM_SLOTS)
    oled: list[str] = field(default_factory=lambda: ["", ""])
    selected: int = 0
    glow: tuple[int, int, int, int] | None = None
    pings: int = 0
    echo: Callable[[str], None] | None = None

    def __post_init__(self):
        self._inbox: "queue.Queue[bytes]" = queue.Queue()
        self._lock = threading.Lock()

    # transport interface
    def write(self, report: bytes) -> None:
        if not self.plugged:
            raise OSError("fake device unplugged")
        report = _norm(report)
        msg = decode_host(report)
        with self._lock:
            self.reports.append(report)
            if not isinstance(msg, Ping):
                self.messages.append(msg)
            match msg:
                case SetSlot(slot, status) if 0 <= slot < NUM_SLOTS:
                    self.slots[slot] = status
                case SetAll(statuses):
                    self.slots = list(statuses)
                case OledLine(line, text) if line in (0, 1):
                    self.oled[line] = text
                case SetGlow(r, g, b, br):
                    self.glow = (r, g, b, br)
                case SetSelected(slot) if 0 <= slot < NUM_SLOTS:
                    self.selected = slot
                case Ping():
                    self.pings += 1
                    self._inbox.put(encode_device(PingReply(self.version, self.selected)))
        if self.echo and not isinstance(msg, Ping):
            self.echo(f"[fake] <- {describe(msg)}")

    def read(self, timeout_ms: int) -> bytes | None:
        if not self.plugged:
            raise OSError("fake device unplugged")
        try:
            return self._inbox.get(timeout=timeout_ms / 1000)
        except queue.Empty:
            return None

    def close(self) -> None:
        pass

    # simulation helpers
    def press(self, key: int | str, action: int = TAP) -> None:
        idx = KEY_NAMES.index(key) if isinstance(key, str) else key
        self._inbox.put(encode_device(KeyEvent(idx, action)))

    def turn(self, direction: int = 1) -> None:
        with self._lock:
            self.selected = (self.selected + (1 if direction > 0 else -1)) % NUM_SLOTS
            sel = self.selected
        self._inbox.put(encode_device(EncoderEvent(direction, sel)))

    def unplug(self) -> None:
        self.plugged = False

    def replug(self) -> None:
        with self._lock:
            self.slots = [Status.IDLE] * NUM_SLOTS
            self.oled = ["", ""]
            self.selected = 0
            self.glow = None
        self._inbox = queue.Queue()
        self.plugged = True

    def opener(self) -> Callable[[], "FakeDevice | None"]:
        return lambda: self if self.plugged else None

    def snapshot(self) -> dict:
        with self._lock:
            return {"slots": list(self.slots), "oled": list(self.oled),
                    "selected": self.selected, "glow": self.glow}


# --------------------------------------------------------------------------- link

class DeviceLink:
    """Owns the transport on a single I/O thread: writes queued reports, pings every 2 s,
    reads device reports, reconnects after an unplug.

    `on_event(obj)` receives decoded device messages plus the strings "connected" /
    "disconnected". It is called from the I/O thread; hand off to your own queue.
    """

    def __init__(self, opener: Callable[[], Transport | None], on_event: Callable[[object], None],
                 ping_interval: float = PING_INTERVAL, retry_interval: float = 1.0,
                 read_timeout_ms: int = 50):
        self.opener = opener
        self.on_event = on_event
        self.ping_interval = ping_interval
        self.retry_interval = retry_interval
        self.read_timeout_ms = read_timeout_ms
        self._out: "queue.Queue[bytes]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.transport: Transport | None = None
        self.connected = threading.Event()
        self.last_pong: float = 0.0
        self.version: int | None = None

    def send(self, msg: HostMsg) -> None:
        if self.connected.is_set():
            self._out.put(encode(msg))

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="frostbite-hid", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._close()

    def _close(self) -> None:
        if self.transport is not None:
            self.transport.close()
        self.transport = None
        was = self.connected.is_set()
        self.connected.clear()
        while not self._out.empty():
            try:
                self._out.get_nowait()
            except queue.Empty:
                break
        if was:
            log.warning("device disconnected")
            self.on_event("disconnected")

    def _run(self) -> None:
        last_ping = 0.0
        missing_logged = False
        while not self._stop.is_set():
            if self.transport is None:
                try:
                    t = self.opener()
                except Exception as e:  # noqa: BLE001
                    log.debug("open failed: %s", e)
                    t = None
                if t is None:
                    if not missing_logged:
                        log.info("pad not found; retrying every %.0f s", self.retry_interval)
                        missing_logged = True
                    self._stop.wait(self.retry_interval)
                    continue
                missing_logged = False
                self.transport = t
                self.connected.set()
                last_ping = 0.0
                self.on_event("connected")
            try:
                while True:
                    try:
                        rep = self._out.get_nowait()
                    except queue.Empty:
                        break
                    self.transport.write(rep)
                now = time.monotonic()
                if now - last_ping >= self.ping_interval:
                    self.transport.write(encode(Ping()))
                    last_ping = now
                data = self.transport.read(self.read_timeout_ms)
                if data:
                    msg = decode_device(data)
                    if isinstance(msg, PingReply):
                        self.last_pong = time.monotonic()
                        if self.version != msg.version:
                            self.version = msg.version
                            if msg.version != PROTOCOL_VERSION:
                                log.warning("firmware protocol v%d, host speaks v%d",
                                            msg.version, PROTOCOL_VERSION)
                            else:
                                log.info("firmware protocol v%d", msg.version)
                    self.on_event(msg)
            except Exception as e:  # noqa: BLE001  (OSError on unplug, anything else: reconnect)
                log.info("device I/O error: %s", e)
                self._close()
                self._stop.wait(self.retry_interval)
