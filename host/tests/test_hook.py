import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from frostbite_host.hook import describe_tool, hook_to_message

FIX = Path(__file__).parent / "fixtures" / "hooks"
ENV = {"TERM_PROGRAM": "iTerm.app", "ITERM_SESSION_ID": "w0t0p0:ABC"}
KEY = "claude:9f2c1e4a-7b3d-4c11-a2e5-0d8f6b1c3e77"


def load(name):
    return json.loads((FIX / name).read_text())


def test_user_prompt_submit_is_run():
    m = hook_to_message(load("user_prompt_submit.json"), ENV)
    assert m["op"] == "update" and m["key"] == KEY and m["status"] == "run"
    assert m["name"] == "my-app"
    assert m["detail"] == "> fix the failing tests in the auth module"
    assert m["terminal"]["bundle"] == "com.googlecode.iterm2"
    assert m["log"].endswith(".jsonl")


def test_pre_tool_use_is_run_with_tool():
    m = hook_to_message(load("pre_tool_use_bash.json"), ENV)
    assert m["status"] == "run" and m["detail"] == "Bash(npm test)" and m["tool"] == "Bash(npm test)"


def test_permission_request_is_needs():
    m = hook_to_message(load("permission_request.json"), ENV)
    assert m["status"] == "needs" and m["detail"] == "Bash(npm test)?"


@pytest.mark.parametrize("name", ["notification_permission.json",
                                  "notification_permission_untyped.json"])
def test_permission_notification_is_needs(name):
    m = hook_to_message(load(name), ENV)
    assert m["status"] == "needs" and m["tool_hint"] == "Bash" and "detail" not in m


def test_idle_notification_is_done():
    assert hook_to_message(load("notification_idle.json"), ENV)["status"] == "done"


def test_post_tool_use_back_to_run():
    m = hook_to_message(load("post_tool_use.json"), ENV)
    assert m["status"] == "run" and "detail" not in m


def test_stop_done_subagent_ignored_session_end_frees():
    assert hook_to_message(load("stop.json"), ENV)["status"] == "done"
    assert hook_to_message(load("subagent_stop.json"), ENV) is None
    assert hook_to_message(load("session_end.json"), ENV) == {"op": "free", "key": KEY}


def test_session_start_registers():
    m = hook_to_message(load("session_start.json"), ENV)
    assert m["register_only"] is True and "status" not in m


def test_minimal_payload_and_mcp_tool():
    m = hook_to_message(load("pre_tool_use_mcp_minimal.json"), {})
    assert m["key"] == "claude:abc" and m["name"] == "claude"
    assert m["detail"] == "create_pull_request(Add frostbite host)"
    assert "cwd" not in m


@pytest.mark.parametrize("payload", [{}, [], "x", {"hook_event_name": "Stop"},
                                     {"session_id": "s"}, {"session_id": 5, "hook_event_name": 7},
                                     {"session_id": "s", "hook_event_name": "Weird"}])
def test_bad_payloads_are_ignored(payload):
    assert hook_to_message(payload, {}) is None


def test_needs_events_capture_the_tty(monkeypatch):
    monkeypatch.setattr("frostbite_host.hook.controlling_tty", lambda: "/dev/ttys007")
    for name in ("permission_request.json", "notification_permission.json"):
        assert hook_to_message(load(name), ENV)["terminal"]["tty"] == "/dev/ttys007"


def test_tool_events_carry_the_agent():
    p = load("permission_request.json")
    p["agent_id"] = "s1"
    assert hook_to_message(p, ENV)["agent"] == "s1"
    p = load("post_tool_use.json")
    p["agent_id"] = "s1"
    assert hook_to_message(p, ENV)["resolve"] == {"tool": "Bash(npm test)", "agent": "s1"}


def test_ask_user_question_waits_on_you():
    p = load("pre_tool_use_bash.json")
    p.update(tool_name="AskUserQuestion", tool_input={"questions": [{"question": "Which?"}]})
    m = hook_to_message(p, ENV)
    assert m["status"] == "needs" and m["kind"] == "question"


def test_stop_failure_is_error_and_interrupt_ends_the_turn():
    p = load("stop.json")
    p.update(hook_event_name="StopFailure", error="rate_limit")
    m = hook_to_message(p, ENV)
    assert m["status"] == "error" and m["detail"] == "rate_limit" and m["clears"]
    p = load("post_tool_use.json")
    p.update(hook_event_name="PostToolUseFailure", is_interrupt=True)
    m = hook_to_message(p, ENV)
    assert m["status"] == "done" and m["detail"] == "interrupted"


def test_cwd_root_has_a_name():
    p = load("stop.json")
    p["cwd"] = "/"
    assert hook_to_message(p, ENV)["name"] == "claude"


def test_describe_tool():
    assert describe_tool("Edit", {"file_path": "/a/b/c.py"}) == "Edit(c.py)"
    assert describe_tool("WebFetch", {"url": "https://docs.qmk.fm/x"}) == "WebFetch(docs.qmk.fm)"
    assert describe_tool("Bash", {"command": "ls\n  -la"}) == "Bash(ls -la)"
    assert describe_tool("Bash", None) == "Bash"
    assert describe_tool(None, {}) == ""


@pytest.mark.parametrize("stdin", ["", "not json", (FIX / "stop.json").read_text()])
def test_hook_cli_never_fails_without_daemon(stdin):
    env = {**os.environ, "FROSTBITE_SOCKET": os.path.join(tempfile.mkdtemp(prefix="fb"), "missing.sock")}
    r = subprocess.run([sys.executable, "-m", "frostbite_host.hook"], input=stdin,
                       capture_output=True, text=True, timeout=5, env=env)
    assert r.returncode == 0
    assert r.stdout == ""
