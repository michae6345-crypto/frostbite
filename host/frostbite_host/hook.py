from __future__ import annotations

import json
import os
import re
import select
import sys
from urllib.parse import urlparse

MAX_STDIN = 16 * 1024 * 1024

# these have several options so the pad just shows them, answer in the terminal
QUESTION_TOOLS = ("AskUserQuestion", "ExitPlanMode")

DEFAULT_WAIT = 30.0
MAX_WAIT = 120.0
DENY_MESSAGE = "Denied from the Frostbite pad."

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
    if env.get("TMUX"):
        info["tmux"] = "1"
    info = {k: v for k, v in info.items() if v}
    if want_tty:
        info["tty"] = controlling_tty()
    return info


# hooks have no terminal of their own so walk up to a parent that does
def controlling_tty() -> str:
    try:
        import subprocess

        pid = os.getppid()
        for _ in range(8):
            if pid <= 1:
                break
            out = subprocess.run(["ps", "-o", "ppid=,tty=", "-p", str(pid)], capture_output=True,
                                 text=True, timeout=0.3).stdout.split()
            if len(out) != 2:
                break
            if out[1] not in ("??", "?", "-"):
                return out[1] if out[1].startswith("/dev/") else "/dev/" + out[1]
            pid = int(out[0])
    except Exception:
        pass
    return ""


def approve_wait(env: dict) -> float:
    try:
        return min(max(float(env.get("FROSTBITE_APPROVE_WAIT", DEFAULT_WAIT)), 0.0), MAX_WAIT)
    except (TypeError, ValueError):
        return DEFAULT_WAIT


PERMISSION_RE = re.compile(r"permission|approve|allow", re.I)
TOOL_IN_MSG_RE = re.compile(r"\buse\s+([A-Za-z_][\w.-]*)", re.I)
IDLE_RE = re.compile(r"waiting for (your )?input", re.I)


def hook_to_message(payload: dict, env: dict | None = None) -> dict | None:
    env = os.environ if env is None else env
    if not isinstance(payload, dict):
        return None
    event = _s(payload.get("hook_event_name"))
    sid = _s(payload.get("session_id")) or env.get("CLAUDE_SESSION_ID", "")
    if not event or not sid:
        return None
    cwd = _s(payload.get("cwd")) or env.get("CLAUDE_PROJECT_DIR", "")
    name = os.path.basename(cwd.rstrip("/")) or "claude"
    base = {
        "op": "update", "source": "claude", "key": f"claude:{sid}", "name": name,
        "cwd": cwd or None, "log": _s(payload.get("transcript_path")) or None,
    }

    def msg(**kw):
        m = dict(base)
        m["terminal"] = terminal_info(env, want_tty=True)
        m.update(kw)
        return {k: v for k, v in m.items() if v is not None}

    tool_name = _s(payload.get("tool_name"))
    tool = describe_tool(tool_name, payload.get("tool_input"))
    agent = _s(payload.get("agent_id")) or None
    question = "question" if tool_name in QUESTION_TOOLS else None

    if event == "SessionStart":
        return msg(register_only=True)
    if event == "UserPromptSubmit":
        prompt = _one_line(_s(payload.get("prompt")), 80)
        return msg(status="run", detail=("> " + prompt) if prompt else "working", clears=True)
    if event == "PreToolUse":
        if question:
            return msg(status="needs", detail="question?", tool=tool, agent=agent, kind=question)
        return msg(status="run", detail=tool or "working", tool=tool or None, agent=agent)
    if event == "PermissionRequest":
        ask = msg(status="needs", detail=(tool + "?") if tool else None, tool=tool or None,
                  agent=agent, kind=question)
        wait = approve_wait(env)
        if question or wait <= 0:
            return ask
        return {**ask, "op": "permission", "id": os.urandom(8).hex(), "wait": wait}
    if event in ("PostToolUse", "PostToolUseFailure"):
        if payload.get("is_interrupt") is True:
            return msg(status="done", detail="interrupted", clears=True)
        return msg(status="run", resolve={"tool": tool, "agent": agent})
    if event == "PreCompact":
        return msg(status="run", detail="compacting")
    if event == "Notification":
        ntype = _s(payload.get("notification_type"))
        text = _s(payload.get("message"))
        if ntype == "permission_prompt" or (not ntype and PERMISSION_RE.search(text)):
            m = TOOL_IN_MSG_RE.search(text)
            return msg(status="needs", tool_hint=m.group(1) if m else None, notification=True)
        if ntype in ("elicitation_dialog", "elicitation_url_dialog", "agent_needs_input"):
            return msg(status="needs", detail=_one_line(text, 80) or "question?", kind="question",
                       notification=True)
        if ntype == "idle_prompt" or (not ntype and IDLE_RE.search(text)):
            return msg(status="done", detail="waiting for input")
        return None
    if event == "Stop":
        last = _s(payload.get("last_assistant_message"))
        first = next((ln for ln in last.splitlines() if ln.strip()), "")
        return msg(status="done", detail=_one_line(first, 80) or "finished", clears=True)
    if event == "StopFailure":
        reason = _s(payload.get("error")) or _s(payload.get("error_details")) or "API error"
        return msg(status="error", detail=_one_line(reason, 80), clears=True)
    if event == "SessionEnd":
        return {"op": "free", "key": base["key"]}
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


# one press answers one call, no saved rules
def decision_for(reply: object, request_id: str) -> dict | None:
    if not isinstance(reply, dict) or reply.get("id") != request_id:
        return None
    if reply.get("decision") == "allow":
        decision = {"behavior": "allow"}
    elif reply.get("decision") == "deny":
        decision = {"behavior": "deny", "message": DENY_MESSAGE}
    else:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}


# claude code adds hook stdout to context, so print nothing unless it's a decision.
# no output means the normal terminal prompt stays in charge
def main(argv: list[str] | None = None) -> int:
    try:
        import signal

        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(2)
    except Exception:
        signal = None
    try:
        raw = read_stdin()
        payload = json.loads(raw) if raw.strip() else {}
        message = hook_to_message(payload)
        if message is not None:
            from . import ipc

            if message.get("op") == "permission":
                wait = float(message["wait"])
                if signal is not None:
                    signal.alarm(int(wait) + 4)
                output = decision_for(ipc.ask(message, wait=wait + 2.0), message["id"])
                if output is not None:
                    sys.stdout.write(json.dumps(output) + "\n")
                    sys.stdout.flush()
            else:
                ipc.send(message, timeout=0.2)
    except BaseException:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
