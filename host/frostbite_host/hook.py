"""frostbite-hook: called by Claude Code hooks, forwards a status event to the daemon.

Reads the hook JSON on stdin, maps it to a slot update, sends it over the local socket.
It never blocks or fails the hook: hard 2 s deadline, 0.2 s socket timeout, prints
nothing on stdout (UserPromptSubmit stdout would be added to Claude's context), exit 0.

Mapping (hook_event_name -> slot status):
  SessionStart           register the session (idle if new)
  UserPromptSubmit       run   (detail: the prompt)
  PreToolUse             run   (detail: "Bash(npm test)")
  PermissionRequest      needs (detail: "Bash(npm test)?")
  PostToolUse(+Failure)  run   (clears needs after you approve)
  Notification           needs for permission prompts / questions; done for "waiting for input"
  PreCompact             run   (detail: compacting)
  Stop                   done
  SubagentStop           ignored (folded into the parent session)
  SessionEnd             free the slot
"""

from __future__ import annotations

import json
import os
import re
import select
import sys
from urllib.parse import urlparse

MAX_STDIN = 1024 * 1024

TERM_PROGRAM_BUNDLES = {
    "apple_terminal": "com.apple.Terminal",
    "iterm.app": "com.googlecode.iterm2",
    "vscode": "com.microsoft.VSCode",
    "ghostty": "com.mitchellh.ghostty",
    "wezterm": "com.github.wez.wezterm",
}


def _s(v: object) -> str:
    return v if isinstance(v, str) else ""


def _one_line(text: str, limit: int = 120) -> str:
    return " ".join(str(text).split())[:limit]


def describe_tool(name: object, tool_input: object) -> str:
    name = _s(name)
    if not name:
        return ""
    inp = tool_input if isinstance(tool_input, dict) else {}
    short = name.split("__")[-1] if name.startswith("mcp__") else name
    arg = ""
    if name == "Bash":
        arg = _s(inp.get("command"))
    elif name in ("Edit", "Write", "Read", "MultiEdit", "NotebookEdit"):
        arg = os.path.basename(_s(inp.get("file_path")) or _s(inp.get("notebook_path")))
    elif name in ("Grep", "Glob"):
        arg = _s(inp.get("pattern"))
    elif name == "WebFetch":
        arg = urlparse(_s(inp.get("url"))).netloc or _s(inp.get("url"))
    elif name == "WebSearch":
        arg = _s(inp.get("query"))
    elif name in ("Task", "Agent"):
        arg = _s(inp.get("description")) or _s(inp.get("subagent_type"))
    else:
        arg = next((v for v in inp.values() if isinstance(v, str) and v.strip()), "")
    arg = _one_line(arg, 100)
    return _one_line(f"{short}({arg})" if arg else short)


def terminal_info(env: dict, want_tty: bool = False) -> dict:
    bundle = env.get("__CFBundleIdentifier") or TERM_PROGRAM_BUNDLES.get(
        env.get("TERM_PROGRAM", "").lower(), "")
    info = {"bundle": bundle, "term_program": env.get("TERM_PROGRAM", "")}
    if env.get("ITERM_SESSION_ID"):
        info["iterm_session"] = env["ITERM_SESSION_ID"]
    if want_tty:
        info["tty"] = controlling_tty()
    return {k: v for k, v in info.items() if v}


def controlling_tty() -> str:
    """Best effort: the terminal the Claude Code process runs in (for focusing its tab)."""
    try:
        fd = os.open("/dev/tty", os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            return os.ttyname(fd)
        finally:
            os.close(fd)
    except OSError:
        pass
    try:
        import subprocess

        for pid in (os.getppid(),):
            out = subprocess.run(["ps", "-o", "tty=", "-p", str(pid)], capture_output=True,
                                 text=True, timeout=0.3).stdout.strip()
            if out and out not in ("??", "?"):
                return out if out.startswith("/dev/") else "/dev/" + out
    except Exception:  # noqa: BLE001
        pass
    return ""


PERMISSION_RE = re.compile(r"permission|approve|allow", re.I)
TOOL_IN_MSG_RE = re.compile(r"\buse\s+([A-Za-z_][\w.-]*)", re.I)
IDLE_RE = re.compile(r"waiting for (your )?input", re.I)


def hook_to_message(payload: dict, env: dict | None = None) -> dict | None:
    """Map one Claude Code hook payload to a daemon message, or None to ignore it."""
    env = os.environ if env is None else env
    if not isinstance(payload, dict):
        return None
    event = _s(payload.get("hook_event_name"))
    sid = _s(payload.get("session_id")) or env.get("CLAUDE_SESSION_ID", "")
    if not event or not sid:
        return None
    cwd = _s(payload.get("cwd")) or env.get("CLAUDE_PROJECT_DIR", "")
    name = os.path.basename(cwd.rstrip("/")) if cwd else "claude"
    base = {
        "op": "update", "source": "claude", "key": f"claude:{sid}", "name": name,
        "cwd": cwd or None, "log": _s(payload.get("transcript_path")) or None,
        "terminal": terminal_info(env) or None,
    }

    def msg(**kw):
        m = dict(base)
        m.update(kw)
        return {k: v for k, v in m.items() if v is not None}

    tool = describe_tool(payload.get("tool_name"), payload.get("tool_input"))

    if event == "SessionStart":
        return msg(register_only=True, terminal=terminal_info(env, want_tty=True))
    if event == "UserPromptSubmit":
        prompt = _one_line(_s(payload.get("prompt")), 80)
        return msg(status="run", detail=("> " + prompt) if prompt else "working",
                   terminal=terminal_info(env, want_tty=True))
    if event == "PreToolUse":
        return msg(status="run", detail=tool or "working", tool=tool or None)
    if event == "PermissionRequest":
        return msg(status="needs", detail=(tool + "?") if tool else None, tool=tool or None)
    if event in ("PostToolUse", "PostToolUseFailure"):
        return msg(status="run")
    if event == "PreCompact":
        return msg(status="run", detail="compacting")
    if event == "Notification":
        ntype = _s(payload.get("notification_type"))
        text = _s(payload.get("message"))
        if ntype == "permission_prompt" or (not ntype and PERMISSION_RE.search(text)):
            m = TOOL_IN_MSG_RE.search(text)
            return msg(status="needs", tool_hint=m.group(1) if m else None)
        if ntype == "elicitation_dialog":
            return msg(status="needs", detail=_one_line(text, 80) or "question?")
        if ntype == "idle_prompt" or (not ntype and IDLE_RE.search(text)):
            return msg(status="done", detail="waiting for input")
        return None
    if event == "Stop":
        last = _s(payload.get("last_assistant_message"))
        first = next((ln for ln in last.splitlines() if ln.strip()), "")
        return msg(status="done", detail=_one_line(first, 80) or "finished")
    if event == "SessionEnd":
        return {"op": "free", "key": base["key"]}
    # SubagentStop and anything unknown: no change.
    return None


def read_stdin(timeout: float = 1.0) -> str:
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    try:
        r, _, _ = select.select([sys.stdin], [], [], timeout)
    except (OSError, ValueError):
        r = [sys.stdin]
    if not r:
        return ""
    return sys.stdin.read(MAX_STDIN)


def main(argv: list[str] | None = None) -> int:
    try:
        import signal

        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(2)
    except Exception:  # noqa: BLE001
        pass
    try:
        raw = read_stdin()
        payload = json.loads(raw) if raw.strip() else {}
        message = hook_to_message(payload)
        if message is not None:
            from . import ipc

            ipc.send(message, timeout=0.2)
    except BaseException:  # noqa: BLE001  never fail or block the hook
        pass
    return 0


def entry() -> None:  # pragma: no cover
    main()
    os._exit(0)


if __name__ == "__main__":  # pragma: no cover
    entry()
