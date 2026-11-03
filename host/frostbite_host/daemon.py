"""frostbite-daemon: owns the pad, the slot board and the local socket.

Threads: HID I/O (device.DeviceLink), socket server, one per training watcher, all
feeding one queue consumed by the main loop, which is the only code touching the Board.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from . import ipc
from .actions import Actions
from .device import (HOLD, KEY_APPROVE, KEY_NAMES, KEY_STOP, KEY_TALK, NUM_SLOTS, OLED_COLS,
                     DeviceLink, DryRunTransport, EncoderEvent, FakeDevice, HidTransport,
                     KeyEvent, OledLine, PingReply, SetAll, SetGlow, SetSelected, Status, Unknown)
from .state import Board
from .train import TrainWatcher

log = logging.getLogger("frostbite.daemon")


class Daemon:
    def __init__(self, board: Board, actions: Actions, send: Callable[[object], None],
                 clock: Callable[[], float] = time.time, watcher_opts: dict | None = None):
        self.board = board
        self.actions = actions
        self.send = send
        self.clock = clock
        self.q: "queue.Queue[tuple]" = queue.Queue()
        self._sent: dict[str, object] = {}
        self.watchers: dict[str, TrainWatcher] = {}
        self.watcher_opts = watcher_opts or {}
        self.stop_event = threading.Event()
        self.connected: Callable[[], bool | None] = lambda: None

    # ------------------------------------------------------------------ inputs (any thread)
    def on_device(self, ev: object) -> None:
        self.q.put(("dev", ev))

    def submit(self, msg: dict, reply: "queue.Queue | None" = None) -> None:
        self.q.put(("ipc", msg, reply))

    # ------------------------------------------------------------------ output
    def push(self) -> None:
        """Send whatever differs from what the pad last got."""
        now = self.clock()
        b = self.board
        sts = tuple(b.statuses())
        if self._sent.get("all") != sts:
            self.send(SetAll(sts))
            self._sent["all"] = sts
        for i, text in enumerate(b.oled_lines(now)):
            padded = text.ljust(OLED_COLS)  # full width so stale characters are overwritten
            if self._sent.get(f"line{i}") != padded:
                self.send(OledLine(i, padded))
                self._sent[f"line{i}"] = padded
        if self._sent.get("sel") != b.selected:
            self.send(SetSelected(b.selected))
            self._sent["sel"] = b.selected
        glow = b.glow()
        if self._sent.get("glow") != glow:
            self.send(SetGlow(*glow))
            self._sent["glow"] = glow

    # ------------------------------------------------------------------ handlers (main thread)
    def handle(self, item: tuple) -> None:
        kind = item[0]
        try:
            if kind == "dev":
                self.handle_device(item[1])
            elif kind == "ipc":
                reply = self.handle_ipc(item[1])
                if item[2] is not None:
                    item[2].put(reply)
        except Exception:  # noqa: BLE001  one bad event must not kill the daemon
            log.exception("error handling %r", item[:2])
            if kind == "ipc" and item[2] is not None:
                item[2].put({"ok": False, "error": "internal error"})
        self.push()

    def handle_ipc(self, msg: dict) -> dict | None:
        now = self.clock()
        if not isinstance(msg, dict):
            return {"ok": False, "error": "not an object"}
        op = msg.get("op")
        if op == "status":
            return {"ok": True, "connected": self.connected(), **self.board.to_dict(now)}
        if op == "watch":
            path = str(msg.get("path", ""))
            w = self.add_watcher(path, msg.get("name"), **{
                k: msg[k] for k in ("stale_minutes", "stale_status", "done_pattern") if k in msg})
            return {"ok": True, "key": w.key}
        if op == "unwatch":
            key = f"train:{msg.get('name')}"
            w = self.watchers.pop(key, None)
            if w:
                w.stop()
            self.board.free(key)
            return {"ok": bool(w)}
        try:
            changed = self.board.apply(msg, now)
        except (ValueError, KeyError, TypeError) as e:
            log.warning("bad message %s: %s", msg, e)
            return {"ok": False, "error": str(e)}
        log.debug("ipc %s -> %s", msg.get("op"), changed)
        return {"ok": True}

    def handle_device(self, ev: object) -> None:
        now = self.clock()
        b = self.board
        if ev == "connected":
            log.info("pad connected; sending full state")
            self._sent.clear()
            return
        if ev == "disconnected":
            return
        if isinstance(ev, EncoderEvent):
            sel = ev.selected if 0 <= ev.selected < NUM_SLOTS else b.selected + ev.direction
            b.select(sel)
            self._sent["sel"] = b.selected  # the pad already shows this selection
            return
        if isinstance(ev, PingReply):
            return
        if isinstance(ev, Unknown):
            log.debug("unknown report %s", ev.raw[:4].hex())
            return
        if not isinstance(ev, KeyEvent):
            return
        held = ev.action == HOLD
        log.info("key %s %s", ev.name, "hold" if held else "tap")
        if ev.key < NUM_SLOTS:
            b.select(ev.key)
            slot = b.slots[ev.key]
            msg = self.actions.open_log(slot) if held else self.actions.focus(slot)
            if msg:
                b.flash(msg, now)
            return
        slot = b.slots[b.selected]
        if ev.key == KEY_APPROVE:
            if slot is None or slot.status != Status.NEEDS:
                log.info("ACTION none: approve pressed but slot %d is not waiting", b.selected + 1)
                b.flash("nothing to approve", now)
                return
            _, msg = self.actions.guarded_key("escape" if held else "return", slot,
                                              "denied" if held else "approved")
            b.flash(msg, now)
        elif ev.key == KEY_STOP:
            _, msg = self.actions.guarded_key("escape", slot, "stop sent")
            b.flash(msg, now)
        elif ev.key == KEY_TALK:
            log.info("talk: left to the firmware's F20 / your dictation hotkey")

    def tick(self) -> None:
        now = self.clock()
        self.board.expire(now)
        self.push()

    # ------------------------------------------------------------------ watchers
    def add_watcher(self, path: str, name: str | None = None, **opts) -> TrainWatcher:
        o = {**self.watcher_opts, **opts}
        w = TrainWatcher(path, name, lambda m: self.submit(m), **o)
        old = self.watchers.pop(w.key, None)
        if old:
            old.stop()
        self.watchers[w.key] = w
        w.start()
        return w

    # ------------------------------------------------------------------ main loop
    def run(self) -> None:
        last_tick = 0.0
        self.push()
        while not self.stop_event.is_set():
            try:
                item = self.q.get(timeout=0.25)
            except queue.Empty:
                item = None
            if item is not None:
                self.handle(item)
            if time.monotonic() - last_tick >= 1.0:
                self.tick()
                last_tick = time.monotonic()
        for w in self.watchers.values():
            w.stop()


class SocketServer:
    """Accepts one JSON line per connection and hands it to the daemon queue."""

    def __init__(self, path: Path, daemon: Daemon):
        self.path = path
        self.daemon = daemon
        self.sock: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        ipc.ensure_state_dir(self.path.parent)
        if self.path.exists():
            try:
                ipc.send({"op": "ping"}, timeout=0.3, path=self.path)
            except OSError:
                self.path.unlink()  # stale socket from a crashed daemon
            else:
                raise SystemExit(f"another frostbite-daemon is listening on {self.path}")
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old = os.umask(0o177)
        try:
            s.bind(str(self.path))
        finally:
            os.umask(old)
        os.chmod(self.path, 0o600)
        s.listen(16)
        s.settimeout(0.5)
        self.sock = s
        self._thread = threading.Thread(target=self._serve, name="frostbite-sock", daemon=True)
        self._thread.start()
        log.info("listening on %s", self.path)

    def _serve(self) -> None:
        while not self.daemon.stop_event.is_set():
            try:
                conn, _ = self.sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn: socket.socket) -> None:
        with conn:
            conn.settimeout(1.0)
            buf = b""
            try:
                while b"\n" not in buf and len(buf) < ipc.MAX_MSG:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                msg = json.loads(buf.split(b"\n", 1)[0] or b"null")
            except (OSError, ValueError) as e:
                log.debug("bad client message: %s", e)
                return
            if not isinstance(msg, dict) or msg.get("op") == "ping":
                return
            want_reply = msg.get("op") in ("status", "watch", "unwatch") or msg.get("reply")
            reply_q: "queue.Queue | None" = queue.Queue() if want_reply else None
            self.daemon.submit(msg, reply_q)
            if reply_q is not None:
                try:
                    reply = reply_q.get(timeout=1.0)
                    conn.sendall((json.dumps(reply) + "\n").encode())
                except (queue.Empty, OSError):
                    pass

    def stop(self) -> None:
        if self.sock:
            self.sock.close()
        try:
            self.path.unlink()
        except OSError:
            pass


# --------------------------------------------------------------------------- fake console

FAKE_HELP = ("fake pad commands: tap N|approve|talk|stop, hold N|approve|stop, cw, ccw, "
             "show, unplug, replug, help")


def fake_console(fake: FakeDevice, stop: threading.Event) -> None:
    print(FAKE_HELP, flush=True)
    for line in sys.stdin:
        if stop.is_set():
            break
        parts = line.split()
        if not parts:
            continue
        cmd, arg = parts[0], (parts[1] if len(parts) > 1 else "")
        try:
            if cmd in ("tap", "hold"):
                key = int(arg) - 1 if arg.isdigit() else KEY_NAMES.index(arg)
                fake.press(key, HOLD if cmd == "hold" else 1)
            elif cmd in ("cw", "ccw"):
                fake.turn(1 if cmd == "cw" else -1)
            elif cmd == "show":
                snap = fake.snapshot()
                print(" ".join(s.name.lower() for s in snap["slots"]), "| sel", snap["selected"] + 1)
                print("+" + "-" * OLED_COLS + "+")
                for ln in snap["oled"]:
                    print("|" + ln.ljust(OLED_COLS) + "|")
                print("+" + "-" * OLED_COLS + "+", flush=True)
            elif cmd == "unplug":
                fake.unplug()
            elif cmd == "replug":
                fake.replug()
            else:
                print(FAKE_HELP, flush=True)
        except (ValueError, IndexError):
            print(FAKE_HELP, flush=True)


# --------------------------------------------------------------------------- entry point

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="frostbite-daemon", description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="never write to the pad or press keys; print what would be sent")
    p.add_argument("--fake", action="store_true",
                   help="use a simulated pad (type tap/hold/cw/show on stdin)")
    p.add_argument("--watch-train", action="append", default=[], metavar="PATH",
                   help="tail a training log or JSONL metrics file (repeatable)")
    p.add_argument("--name", action="append", default=[],
                   help="slot name for the matching --watch-train (repeatable, same order)")
    p.add_argument("--stale-minutes", type=float, default=10.0,
                   help="mark a run finished when its log stops growing this long (default 10)")
    p.add_argument("--stale-status", choices=["done", "needs"], default="done",
                   help="status for a stale run (default done)")
    p.add_argument("--done-pattern", help="extra regex that marks the final log line")
    p.add_argument("--linger-minutes", type=float, default=10.0,
                   help="how long finished slots stay green before they free (default 10)")
    p.add_argument("--socket", type=Path, default=None, help="socket path (default: state dir)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    board = Board(linger_done=args.linger_minutes * 60)
    actions = Actions(dry_run=args.dry_run)
    fake: FakeDevice | None = None
    if args.fake:
        fake = FakeDevice(echo=(lambda s: print(s, flush=True)) if args.dry_run else None)
        opener = fake.opener()
    elif args.dry_run:
        dry = DryRunTransport(out=lambda s: print(s, flush=True))
        opener = lambda: dry  # noqa: E731
    else:
        opener = HidTransport.open

    holder: dict[str, DeviceLink] = {}
    daemon = Daemon(board, actions, send=lambda m: holder["link"].send(m),
                    watcher_opts={"stale_minutes": args.stale_minutes,
                                  "stale_status": args.stale_status,
                                  "done_pattern": args.done_pattern})
    link = DeviceLink(opener, daemon.on_device)
    holder["link"] = link
    daemon.connected = link.connected.is_set

    server = SocketServer(args.socket or ipc.socket_path(), daemon)
    server.start()
    names = list(args.name)
    for i, path in enumerate(args.watch_train):
        daemon.add_watcher(path, names[i] if i < len(names) else None)
    link.start()
    if fake is not None and sys.stdin.isatty():
        threading.Thread(target=fake_console, args=(fake, daemon.stop_event), daemon=True).start()

    import signal

    def _stop(*_):
        daemon.stop_event.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("frostbite-daemon running%s%s", " (dry-run)" if args.dry_run else "",
             " (fake pad)" if args.fake else "")
    try:
        daemon.run()
    finally:
        link.stop()
        server.stop()
        log.info("stopped")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
