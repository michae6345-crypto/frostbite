from __future__ import annotations

import logging
import queue
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Protocol

log = logging.getLogger("frostbite.device")

# 0xFF60/0x61 are just the qmk defaults, on a via board ping means set keycode.
# so check vid/pid too and never open anything else
VENDOR_ID = 0xFEED
PRODUCT_ID = 0x4642
USAGE_PAGE = 0xFF60
USAGE = 0x61
REPORT_LEN = 32
PROTOCOL_VERSION = 1
NUM_SLOTS = 6
OLED_COLS = 21
PING_INTERVAL = 2.0
PONG_TIMEOUT = 6.5
HANDSHAKE_TIMEOUT = 1.0
STALL_SECONDS = 0.5


class Status(IntEnum):
    IDLE = 0
    RUN = 1
    DONE = 2
    NEEDS = 3
    ERROR = 4

    @classmethod
    def parse(cls, word: str) -> Status:
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


# 32 byte reports, byte 0 is the command. has to match keymap.c
class Cmd(IntEnum):
    SET_SLOT = 0x01
    SET_ALL = 0x02
    OLED_LINE = 0x03
    PING = 0x05
    SET_SELECTED = 0x06
    KEY = 0x81
    ENCODER = 0x82


KEY_NAMES = ["agent1", "agent2", "agent3", "agent4", "agent5", "agent6", "approve", "talk", "stop"]
KEY_APPROVE, KEY_TALK, KEY_STOP = 6, 7, 8
TAP, HOLD = 1, 2
CW, CCW = 1, 0xFF


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
    action: int

    @property
    def name(self) -> str:
        return KEY_NAMES[self.key] if 0 <= self.key < len(KEY_NAMES) else f"key{self.key}"


@dataclass(frozen=True)
class EncoderEvent:
    direction: int
    selected: int


@dataclass(frozen=True)
class Unknown:
    raw: bytes


HostMsg = SetSlot | SetAll | OledLine | Ping | SetSelected
DeviceMsg = PingReply | KeyEvent | EncoderEvent | Unknown


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
        case Ping():
            return _report(Cmd.PING)
        case SetSelected(slot):
            return _report(Cmd.SET_SELECTED, _slot(slot))
    raise TypeError(f"not a host message: {msg!r}")


def encode_device(msg: DeviceMsg) -> bytes:
    match msg:
        case PingReply(version, selected):
            return _report(Cmd.PING, version, selected)
        case KeyEvent(key, action):
            return _report(Cmd.KEY, key, action)
        case EncoderEvent(direction, selected):
            return _report(Cmd.ENCODER, CW if direction > 0 else CCW, selected)
    raise TypeError(f"not a device message: {msg!r}")


def _norm(report: bytes | list[int]) -> bytes:
    data = bytes(report)
    return data[:REPORT_LEN].ljust(REPORT_LEN, b"\0")


def decode_host(report: bytes | list[int]) -> HostMsg | Unknown:
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
        if cmd == Cmd.PING:
            return Ping()
        if cmd == Cmd.SET_SELECTED:
            return SetSelected(r[1])
    except ValueError:
        pass
    return Unknown(r)


def decode_device(report: bytes | list[int]) -> DeviceMsg:
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
        case Ping():
            return "PING"
        case SetSelected(slot):
            return f"SET_SELECTED {slot}"
    return repr(msg)


class Transport(Protocol):
    def write(self, report: bytes) -> None: ...
    def read(self, timeout_ms: int) -> bytes | None: ...
    def close(self) -> None: ...


class HidTransport:

    def __init__(self, dev, info: dict):
        self._dev = dev
        self.info = info

    @classmethod
    def find(cls) -> list[dict]:
        import hid

        return [
            d for d in hid.enumerate(VENDOR_ID, PRODUCT_ID)
            if d.get("vendor_id") == VENDOR_ID and d.get("product_id") == PRODUCT_ID
            and d.get("usage_page") == USAGE_PAGE and d.get("usage") == USAGE
        ]

    @classmethod
    def open(cls) -> HidTransport | None:
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
        n = self._dev.write(b"\x00" + _norm(report))
        if n < 0:
            raise OSError("hid write failed")

    def read(self, timeout_ms: int) -> bytes | None:
        data = self._dev.read(REPORT_LEN, timeout_ms)
        return bytes(data) if data else None

    def close(self) -> None:
        try:
            self._dev.close()
        except Exception:
            pass


class DryRunTransport:

    def __init__(self, out=print):
        self.out = out
        self._pinged = False
        self._replies: queue.Queue[bytes] = queue.Queue()
        self._last_all: object = None

    def write(self, report: bytes) -> None:
        msg = decode_host(report)
        if isinstance(msg, Ping):
            self._replies.put(encode_device(PingReply(PROTOCOL_VERSION, 0)))
            if self._pinged:
                return
            self._pinged = True
            self.out("[dry-run] -> PING (further pings every 2 s not shown)")
            return
        if isinstance(msg, SetAll):
            if msg == self._last_all:
                return
            self._last_all = msg
        self.out(f"[dry-run] -> {describe(msg)}   {report[:8].hex(' ')}...")

    def read(self, timeout_ms: int) -> bytes | None:
        try:
            return self._replies.get(timeout=timeout_ms / 1000)
        except queue.Empty:
            return None

    def close(self) -> None:
        pass


@dataclass
class FakeDevice:

    version: int = PROTOCOL_VERSION
    plugged: bool = True
    reports: list[bytes] = field(default_factory=list)
    messages: list[object] = field(default_factory=list)
    slots: list[Status] = field(default_factory=lambda: [Status.IDLE] * NUM_SLOTS)
    oled: list[str] = field(default_factory=lambda: ["", ""])
    selected: int = 0
    pings: int = 0
    echo: Callable[[str], None] | None = None

    def __post_init__(self):
        self._inbox: queue.Queue[bytes] = queue.Queue()
        self._lock = threading.Lock()

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
        self._inbox = queue.Queue()
        self.plugged = True

    def opener(self) -> Callable[[], FakeDevice | None]:
        return lambda: self if self.plugged else None

    def snapshot(self) -> dict:
        with self._lock:
            return {"slots": list(self.slots), "oled": list(self.oled),
                    "selected": self.selected}


class DeviceLink:

    def __init__(self, opener: Callable[[], Transport | None], on_event: Callable[[object], None],
                 ping_interval: float = PING_INTERVAL, retry_interval: float = 1.0,
                 read_timeout_ms: int = 50, keepalive: Callable[[], HostMsg | None] | None = None,
                 pong_timeout: float = PONG_TIMEOUT, handshake_timeout: float = HANDSHAKE_TIMEOUT):
        self.opener = opener
        self.on_event = on_event
        self.keepalive = keepalive
        self.pong_timeout = pong_timeout
        self.handshake_timeout = handshake_timeout
        self.ping_interval = ping_interval
        self.retry_interval = retry_interval
        self.read_timeout_ms = read_timeout_ms
        self._out: queue.Queue[bytes] = queue.Queue()
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

    def _handshake(self, t: Transport) -> bool:
        t.write(encode(Ping()))
        end = time.monotonic() + self.handshake_timeout
        while time.monotonic() < end and not self._stop.is_set():
            data = t.read(self.read_timeout_ms)
            if not data:
                continue
            msg = decode_device(data)
            if isinstance(msg, PingReply):
                self.version = msg.version
                if msg.version == PROTOCOL_VERSION:
                    log.info("firmware protocol v%d", msg.version)
                    return True
                log.warning("firmware protocol v%d, host speaks v%d: not using this device",
                            msg.version, PROTOCOL_VERSION)
                return False
        log.warning("device did not answer PING: not using it")
        return False

    def _run(self) -> None:
        last_ping = 0.0
        missing_logged = False
        open_error = ""
        while not self._stop.is_set():
            if self.transport is None:
                try:
                    t = self.opener()
                except Exception as e:
                    if str(e) != open_error:
                        open_error = str(e)
                        log.warning("cannot open the pad: %s", e)
                    t = None
                if t is None:
                    if not missing_logged:
                        log.info("pad not found; retrying every %.0f s", self.retry_interval)
                        missing_logged = True
                    self._stop.wait(self.retry_interval)
                    continue
                missing_logged = False
                open_error = ""
                try:
                    ok = self._handshake(t)
                except Exception as e:
                    log.info("handshake failed: %s", e)
                    ok = False
                if not ok:
                    t.close()
                    self._stop.wait(self.retry_interval)
                    continue
                self.transport = t
                self.connected.set()
                last_ping = time.monotonic()
                self.last_pong = last_ping
                read_end = last_ping
                distrust_until = 0.0
                self.on_event("connected")
            try:
                while True:
                    try:
                        rep = self._out.get_nowait()
                    except queue.Empty:
                        break
                    self.transport.write(rep)
                now = time.monotonic()
                if now - self.last_pong >= self.pong_timeout:
                    raise OSError(f"no PING reply for {self.pong_timeout:.1f} s")
                if now - last_ping >= self.ping_interval:
                    self.transport.write(encode(Ping()))
                    last_ping = now
                    extra = self.keepalive() if self.keepalive else None
                    if extra is not None:
                        self.transport.write(encode(extra))
                read_start = time.monotonic()
                data = self.transport.read(self.read_timeout_ms)
                now = time.monotonic()
                if (read_start - read_end > STALL_SECONDS
                        or now - read_start > self.read_timeout_ms / 1000 + STALL_SECONDS):
                    distrust_until = now + 0.2
                read_end = now
                if data:
                    msg = decode_device(data)
                    if isinstance(msg, PingReply):
                        self.last_pong = now
                    if isinstance(msg, KeyEvent) and now < distrust_until:
                        log.info("dropped %s press: it may be from before a stall", msg.name)
                        continue
                    self.on_event(msg)
            except Exception as e:
                log.info("device I/O error: %s", e)
                self._close()
                self._stop.wait(self.retry_interval)
