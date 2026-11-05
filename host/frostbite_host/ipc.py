from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

MAX_MSG = 64 * 1024


def state_dir() -> Path:
    env = os.environ.get("FROSTBITE_DIR")
    if env:
        return Path(env)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "frostbite"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "frostbite"


def socket_path() -> Path:
    env = os.environ.get("FROSTBITE_SOCKET")
    return Path(env) if env else state_dir() / "frostbite.sock"


def _encode(msg: dict) -> bytes:
    data = (json.dumps(msg, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
    if len(data) > MAX_MSG:
        raise ValueError("message too large")
    return data


def _read_reply(s: socket.socket) -> dict | None:
    buf = b""
    while not buf.endswith(b"\n") and len(buf) < MAX_MSG:
        chunk = s.recv(4096)
        if not chunk:
            break
        buf += chunk
    return json.loads(buf) if buf.strip() else None


def send(msg: dict, timeout: float = 0.25, want_reply: bool = False,
         path: Path | None = None) -> dict | None:
    data = _encode(msg)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(str(path or socket_path()))
        s.sendall(data)
        if not want_reply:
            return None
        s.shutdown(socket.SHUT_WR)
        return _read_reply(s)


# the open connection is how the daemon knows the request is still alive
def ask(msg: dict, wait: float, connect_timeout: float = 0.2, path: Path | None = None) -> dict | None:
    data = _encode(msg)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(connect_timeout)
        s.connect(str(path or socket_path()))
        s.sendall(data)
        s.settimeout(wait)
        return _read_reply(s)
