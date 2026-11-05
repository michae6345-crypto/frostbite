"""drive the slots by hand

  frostbite-ctl set 3 run "CI build" [--detail "deploy #42"] [--log PATH]
  frostbite-ctl clear 3
  frostbite-ctl select 3
  frostbite-ctl status [--json]
  frostbite-ctl watch PATH [--name my-model] [--stale-minutes 10]
  frostbite-ctl unwatch NAME
  frostbite-ctl hooks [--hook PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys

from . import ipc
from .device import NUM_SLOTS, Status
from .hook import DEFAULT_WAIT
from .train import done_pattern

HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest",
               "PostToolUse", "PostToolUseFailure", "Notification", "PreCompact", "Stop",
               "StopFailure", "SessionEnd"]
TOOL_EVENTS = {"PreToolUse", "PermissionRequest", "PostToolUse", "PostToolUseFailure"}
HOOK_TIMEOUT = 5
PERMISSION_TIMEOUT = int(DEFAULT_WAIT) + 10


def hooks_snippet(hook_path: str) -> dict:
    entry = {"type": "command", "command": shlex.quote(hook_path)}
    hooks = {}
    for ev in HOOK_EVENTS:
        timeout = PERMISSION_TIMEOUT if ev == "PermissionRequest" else HOOK_TIMEOUT
        group: dict = {"hooks": [{**entry, "timeout": timeout}]}
        if ev in TOOL_EVENTS:
            group = {"matcher": "*", **group}
        hooks[ev] = [group]
    return {"hooks": hooks}


def _slot(text: str) -> int:
    n = int(text)
    if not 1 <= n <= NUM_SLOTS:
        raise argparse.ArgumentTypeError(f"slot must be 1-{NUM_SLOTS}")
    return n - 1


def _status(text: str) -> str:
    try:
        return Status.parse(text).name.lower()
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="frostbite-ctl", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("set", help="set a slot's status")
    s.add_argument("slot", type=_slot)
    s.add_argument("status", type=_status, help="idle|run|done|needs|error")
    s.add_argument("name", nargs="?", default=None)
    s.add_argument("--detail", default="")
    s.add_argument("--log", default=None)
    c = sub.add_parser("clear", help="free a slot")
    c.add_argument("slot", type=_slot)
    se = sub.add_parser("select", help="select a slot (OLED shows it)")
    se.add_argument("slot", type=_slot)
    st = sub.add_parser("status", help="show the board")
    st.add_argument("--json", action="store_true")
    w = sub.add_parser("watch", help="ask the running daemon to watch a training log")
    w.add_argument("path")
    w.add_argument("--name")
    w.add_argument("--stale-minutes", type=float)
    w.add_argument("--done-pattern", type=done_pattern)
    u = sub.add_parser("unwatch", help="stop watching a training run")
    u.add_argument("name")
    h = sub.add_parser("hooks", help="print a Claude Code hooks JSON snippet")
    h.add_argument("--hook", default=None, help="path to frostbite-hook (default: from PATH)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "hooks":
        path = args.hook or shutil.which("frostbite-hook") or "/ABSOLUTE/PATH/TO/frostbite-hook"
        print(json.dumps(hooks_snippet(os.path.abspath(path) if args.hook else path), indent=2))
        return 0
    if args.cmd == "set":
        msg = {"op": "set_slot", "slot": args.slot, "status": args.status,
               "name": args.name, "detail": args.detail, "log": args.log}
    elif args.cmd == "clear":
        msg = {"op": "clear_slot", "slot": args.slot}
    elif args.cmd == "select":
        msg = {"op": "select", "slot": args.slot}
    elif args.cmd == "status":
        msg = {"op": "status"}
    elif args.cmd == "watch":
        msg = {"op": "watch", "path": os.path.abspath(os.path.expanduser(args.path)),
               "name": args.name}
        if args.stale_minutes is not None:
            msg["stale_minutes"] = args.stale_minutes
        if args.done_pattern:
            msg["done_pattern"] = args.done_pattern
    else:
        msg = {"op": "unwatch", "name": args.name}
    try:
        reply = ipc.send(msg, timeout=2.0, want_reply=args.cmd in ("status", "watch", "unwatch"))
    except OSError as e:
        print(f"frostbite-ctl: daemon not reachable at {ipc.socket_path()} ({e})", file=sys.stderr)
        return 2
    if args.cmd == "status" and reply:
        if args.json:
            print(json.dumps(reply, indent=2))
        else:
            for i, slot in enumerate(reply.get("slots", [])):
                mark = ">" if reply.get("selected") == i + 1 else " "
                if slot:
                    print(f"{mark}{i + 1} {slot['status']:<5} {slot['source']:<6} "
                          f"{slot['name']:<20} {slot['detail']}")
                else:
                    print(f"{mark}{i + 1} -")
            print("OLED: " + " | ".join(reply.get("oled", [])))
    elif reply is not None and not reply.get("ok", True):
        print(f"frostbite-ctl: {reply.get('error')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
