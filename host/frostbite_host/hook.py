"""frostbite-hook: called by Claude Code hooks, forwards a status event to the daemon.

Reads the hook JSON on stdin, maps it to a slot update, sends it over the local socket.
Every event but one returns at once: 2 s hard deadline, 0.2 s to connect, nothing on stdout
(UserPromptSubmit stdout would be added to Claude's context), exit 0.

The exception is PermissionRequest. The hook stays connected and waits a bounded time for a
press on the pad, then prints Claude Code's decision JSON for that one request. Timeout,
no daemon, no pad, or any error: it exits 0 with no output, which leaves the normal terminal
prompt in charge. Only a press can produce a decision. Nothing here allows anything itself.

Mapping (hook_event_name -> slot status). `needs` is tracked per prompt in the daemon, so
events from sibling tools and subagents do not clear a prompt that is still open:
  SessionStart           register the session (idle if new)
  UserPromptSubmit       run, closes any open prompt (detail: the prompt)
  PreToolUse             run (detail: "Bash(npm test)"); AskUserQuestion / ExitPlanMode: needs
  PermissionRequest      needs (detail: "Bash(npm test)?"), waits for the pad
  PostToolUse(+Failure)  run, closes the prompt for that tool; an interrupted tool: done
  Notification           needs for permission prompts / questions; done for "waiting for input"
  PreCompact             run (detail: compacting)
  Stop                   done, closes open prompts
  StopFailure            error (API error ended the turn), closes open prompts
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

MAX_STDIN = 16 * 1024 * 1024  # PostToolUse carries tool output; dropping it leaves a prompt open

# Their dialogs have several options and the answer is the content, so the pad only shows them.
QUESTION_TOOLS = ("AskUserQuestion", "ExitPlanMode")

DEFAULT_WAIT = 30.0   # seconds a PermissionRequest waits for the pad (see README for why)
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
        info["tty"] = controlling_tty()  # kept when empty: it says the old tty no longer holds
    return info


def controlling_tty() -> str:
    """Best effort: the terminal Claude Code runs in, used only to focus its tab and to prove
    Stop. Hooks run in their own session with no controlling terminal, so /dev/tty cannot work:
    walk up to the nearest ancestor that has one. A wrapper in between adds a step, nothing else."""
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
    except Exception:  # noqa: BLE001
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
    """Map one Claude Code hook payload to a daemon message, or None to ignore it."""
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
            return ask  # shown on the pad, answered in the terminal
        return {**ask, "op": "permission", "id": os.urandom(8).hex(), "wait": wait}
    if event in ("PostToolUse", "PostToolUseFailure"):
        if payload.get("is_interrupt") is True:  # Stop does not fire after an interrupt
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


def decision_for(reply: object, request_id: str) -> dict | None:
    """Claude Code's decision JSON for this request, or None to leave the terminal prompt alone.
    Only an exact answer to this id counts. Never updatedInput or updatedPermissions: a press
    answers this one call and changes nothing else."""
    if not isinstance(reply, dict) or reply.get("id") != request_id:
        return None
    if reply.get("decision") == "allow":
        decision = {"behavior": "allow"}
    elif reply.get("decision") == "deny":
        decision = {"behavior": "deny", "message": DENY_MESSAGE}
    else:
        return None
    return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}


def main(argv: list[str] | None = None) -> int:
    try:
        import signal

        signal.signal(signal.SIGALRM, lambda *_: os._exit(0))
        signal.alarm(2)
    except Exception:  # noqa: BLE001
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
    except BaseException:  # noqa: BLE001  never fail the hook: no output means no decision
        pass
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
