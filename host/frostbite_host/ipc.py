"""Local Unix-socket IPC between frostbite-hook / frostbite-ctl and frostbite-daemon.

Wire format: one JSON object per connection, newline-terminated. Messages are dicts
with an "op" key (see state.Board.apply). The daemon answers ops that want a reply
(e.g. "status") with one JSON line.

Kept stdlib-only and import-light: frostbite-hook runs on every Claude Code hook.
"""

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


def ensure_state_dir(path: Path | None = None) -> Path:
    d = path or state_dir()
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(d, 0o700)
    return d


def send(msg: dict, timeout: float = 0.25, want_reply: bool = False,
         path: Path | None = None) -> dict | None:
    """Send one message. Raises OSError if the daemon is not reachable."""
    p = str(path or socket_path())
    data = (json.dumps(msg, separators=(",", ":"), ensure_ascii=True) + "\n").encode()
    if len(data) > MAX_MSG:
        raise ValueError("message too large")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(p)
        s.sendall(data)
        if not want_reply:
            return None
        s.shutdown(socket.SHUT_WR)
        buf = b""
        while not buf.endswith(b"\n") and len(buf) < MAX_MSG:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
        return json.loads(buf) if buf.strip() else None
