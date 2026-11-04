"""Findings from docs/audit/round2-software.md, and the Approve redesign they led to.

Approve sends no keystroke. It answers one connected PermissionRequest hook. These tests run real
`frostbite-hook` processes against a real daemon and socket on a FakeDevice. Nothing presses keys:
the Mac is a fake runner. No test touches Claude Code settings.
"""
import json
import os
import queue
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from conftest import REAL_CONTROLLING_TTY
from test_daemon import ESCAPE, FIX, TTY, FakeRunner, ask, hook, make, wait_for

from frostbite_host import actions as A
from frostbite_host import hook as H
from frostbite_host import ipc
from frostbite_host.actions import Actions
from frostbite_host.ctl import HOOK_EVENTS, hooks_snippet
from frostbite_host.daemon import Daemon, SocketServer
from frostbite_host.device import (HOLD, TAP, DeviceLink, FakeDevice, KeyEvent, Status, encode_device)
from frostbite_host.state import Board
from frostbite_host.train import TrainWatcher, parse_line

HOST = Path(__file__).resolve().parents[1]
PAYLOAD = (FIX / "hooks" / "permission_request.json").read_text()


@pytest.fixture
def live():
    """A real daemon loop and socket on a fake pad."""
    tmp = tempfile.mkdtemp(prefix="fb")
    sock = Path(tmp) / "s.sock"
    fake = FakeDevice()
    runner = FakeRunner()
    holder = {}
    d = Daemon(Board(), Actions(runner=runner, out=lambda s: None), send=lambda m: holder["link"].send(m))
    link = DeviceLink(fake.opener(), d.on_device, ping_interval=0.2, retry_interval=0.05,
                      read_timeout_ms=10, keepalive=d.keepalive)
    holder["link"] = link
    d.connected = link.connected.is_set
    server = SocketServer(sock, d)
    server.start()
    link.start()
    t = threading.Thread(target=d.run, daemon=True)
    t.start()
    assert wait_for(link.connected.is_set)
    yield d, fake, runner, sock
    d.stop_event.set()
    t.join(2)
    link.stop()
    server.stop()


def start_hook(sock, wait="5", payload=PAYLOAD):
    env = {**os.environ, "FROSTBITE_SOCKET": str(sock), "FROSTBITE_APPROVE_WAIT": wait}
    p = subprocess.Popen([sys.executable, "-m", "frostbite_host.hook"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env, cwd=HOST)
    p.stdin.write(payload)
    p.stdin.close()
    return p


def result(p):
    rc = p.wait(timeout=10)
    return rc, p.stdout.read(), p.stderr.read()


def shown(d):
    return wait_for(lambda: d._shown_id is not None) and time.sleep(0.7)


# ------------------------------------------------------------------ the decision reaches Claude Code

def test_approve_prints_the_documented_allow_for_that_hook(live):
    d, fake, runner, sock = live
    p = start_hook(sock)
    shown(d)
    fake.press("approve")
    rc, out, err = result(p)
    assert (rc, err) == (0, "")
    assert json.loads(out) == {"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                                      "decision": {"behavior": "allow"}}}
    assert runner.calls == []
    assert wait_for(lambda: fake.slots[0] is Status.RUN)


def test_hold_approve_prints_a_deny_that_keeps_claude_running(live):
    d, fake, runner, sock = live
    p = start_hook(sock)
    shown(d)
    fake.press("approve", HOLD)
    rc, out, err = result(p)
    decision = json.loads(out)["hookSpecificOutput"]["decision"]
    assert rc == 0 and decision["behavior"] == "deny" and decision["message"]
    assert "interrupt" not in decision and runner.calls == []


def test_timeout_leaves_the_terminal_prompt_in_charge(live):
    d, fake, runner, sock = live
    p = start_hook(sock, wait="1")
    assert wait_for(lambda: fake.slots[0] is Status.NEEDS)
    assert result(p) == (0, "", "")
    assert wait_for(lambda: not d.requests)
    time.sleep(0.05)
    assert fake.slots[0] is Status.NEEDS         # the dialog may still be open
    fake.press("approve")                        # a late press has nothing to answer
    assert wait_for(lambda: fake.oled[1].rstrip() == "answer in terminal")


def test_daemon_absent_is_no_decision():
    t = time.monotonic()
    p = start_hook(os.path.join(tempfile.mkdtemp(prefix="fb"), "gone.sock"))
    assert result(p) == (0, "", "")
    assert time.monotonic() - t < 2


def test_garbage_and_wrong_id_replies_are_no_decision():
    good = H.decision_for({"id": "a", "decision": "allow"}, "a")
    assert good["hookSpecificOutput"]["decision"] == {"behavior": "allow"}
    for reply in (None, [], "allow", {}, {"id": "b", "decision": "allow"}, {"id": "a"},
                  {"id": "a", "decision": None}, {"id": "a", "decision": "ask"}, {"decision": "allow"}):
        assert H.decision_for(reply, "a") is None


def test_no_pad_answers_at_once_with_no_decision(live):
    d, fake, runner, sock = live
    fake.unplug()
    assert wait_for(lambda: not d.connected())
    assert result(start_hook(sock, wait="20")) == (0, "", "")
    assert d.requests == {}


def test_dry_run_never_answers_a_real_session():
    d, fake, runner, clock = make()
    d.actions.dry_run = True
    rid, reply = ask(d, clock)
    assert reply.get_nowait() == {"id": rid, "decision": None}
    assert fake.slots[0] is Status.NEEDS and d.requests == {}
    d.handle(("dev", KeyEvent(6, TAP)))
    assert reply.empty()


def test_daemon_dying_mid_wait_is_no_decision():
    path = os.path.join(tempfile.mkdtemp(prefix="fb"), "s.sock")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    listener.listen(1)

    def die():
        conn, _ = listener.accept()
        conn.recv(4096)
        conn.close()                             # what process exit does to the connection

    threading.Thread(target=die, daemon=True).start()
    assert result(start_hook(path, wait="20")) == (0, "", "")
    listener.close()


def test_cancelled_hook_closes_its_request_at_once(live):
    d, fake, runner, sock = live
    p = start_hook(sock, wait="30")
    assert wait_for(lambda: d.requests)
    p.send_signal(signal.SIGTERM)                # what a hook timeout does
    p.wait(timeout=5)
    assert wait_for(lambda: not d.requests)
    fake.press("approve")
    assert wait_for(lambda: fake.oled[1].rstrip() == "answer in terminal")


# ------------------------------------------------------------------ R2-01 / R2-02: which request

def test_r2_01_stale_amber_has_nothing_to_answer():
    d, fake, runner, clock = make()
    rid, reply = ask(d, clock)
    clock[0] += 31                               # the hook gave up; the session has since died
    d.tick()
    assert reply.get_nowait() == {"id": rid, "decision": None}
    assert fake.slots[0] is Status.NEEDS
    for key in (TAP, HOLD):
        d.handle(("dev", KeyEvent(6, key)))
    assert reply.empty() and runner.calls == []
    assert fake.slots[0] is Status.NEEDS         # never reports `approved` for nothing
    assert "approved" not in fake.oled[1]


def test_r2_02_a_press_answers_the_request_on_the_oled_and_no_other():
    d, fake, runner, clock = make()
    first, a = ask(d, clock, tool_input={"command": "npm test"})
    second, b = ask(d, clock, tool_input={"command": "rm -rf ~/data"})
    assert "npm test" in fake.oled[1]
    d.handle(("dev", KeyEvent(6, TAP)))
    assert a.get_nowait() == {"id": first, "decision": "allow"} and b.empty()


def test_r2_02_when_the_shown_request_ends_the_next_needs_its_own_look():
    d, fake, runner, clock = make()
    first, a = ask(d, clock, tool_input={"command": "npm test"})
    second, b = ask(d, clock, tool_input={"command": "rm -rf ~/data"})
    d.handle(("ipc", {"op": "request_gone", "id": first}, None))  # answered in the terminal
    assert "rm -rf" in fake.oled[1]
    d.handle(("dev", KeyEvent(6, TAP)))          # the press was meant for what was just there
    assert b.empty()
    clock[0] += 1
    d.handle(("dev", KeyEvent(6, TAP)))
    assert b.get_nowait() == {"id": second, "decision": "allow"}


def test_a_press_on_another_slot_answers_nothing():
    d, fake, runner, clock = make()
    rid, reply = ask(d, clock)
    d.handle(("dev", KeyEvent(3, TAP)))          # slot 4 is empty
    clock[0] += 1
    d.handle(("dev", KeyEvent(6, TAP)))
    assert reply.empty()


def test_new_request_comes_up_by_itself_but_never_steals_a_live_one():
    d, fake, runner, clock = make()
    d.handle(("dev", KeyEvent(4, TAP)))
    rid, reply = ask(d, clock)
    assert d.board.selected == 0
    other = queue.Queue()
    hook(d, "permission_request.json", other, session_id="other")
    assert d.board.selected == 0


def test_tool_finishing_closes_its_request():
    d, fake, runner, clock = make()
    rid, reply = ask(d, clock)
    hook(d, "post_tool_use.json")                # answered in the terminal, tool ran
    assert reply.get_nowait() == {"id": rid, "decision": None}
    assert fake.slots[0] is Status.RUN


def test_prompt_or_session_end_closes_its_request():
    for name in ("user_prompt_submit.json", "stop.json", "session_end.json"):
        d, fake, runner, clock = make()
        rid, reply = ask(d, clock)
        hook(d, name)
        assert reply.get_nowait() == {"id": rid, "decision": None}


def test_never_auto_approved():
    """Only a KeyEvent can produce a decision: every other message leaves the hook waiting or
    releases it with none."""
    d, fake, runner, clock = make()
    rid, reply = ask(d, clock)
    for msg in ({"op": "status"}, {"op": "update", "key": "x", "decision": "allow"},
                {"op": "permission", "id": rid, "decision": "allow"}, {"op": "allow", "id": rid},
                {"op": "select", "slot": 0}, {"op": "set_slot", "slot": 3, "status": "run"}):
        d.handle(("ipc", msg, queue.Queue()))
    assert all(v.get("decision") != "allow" for v in list(reply.queue))
    clock[0] += 30
    d.tick()
    assert reply.get_nowait()["decision"] is None


def test_duplicate_request_id_cannot_borrow_a_waiting_hook():
    d, fake, runner, clock = make()
    rid, reply = ask(d, clock)
    thief = queue.Queue()
    d.handle(("ipc", {"op": "permission", "id": rid, "key": "claude:x", "source": "claude",
                      "status": "needs", "wait": 5}, thief))
    assert thief.get_nowait() == {"id": rid, "decision": None}
    d.handle(("dev", KeyEvent(6, TAP)))
    assert reply.get_nowait()["decision"] == "allow"


def test_agent_and_tool_events_do_not_release_a_waiting_request():
    d, fake, runner, clock = make()
    rid, reply = ask(d, clock, agent_id="s1")
    hook(d, "pre_tool_use_bash.json", agent_id="s2")
    hook(d, "post_tool_use.json", agent_id="s2")
    assert reply.empty() and fake.slots[0] is Status.NEEDS


def test_question_tools_do_not_wait():
    p = json.loads(PAYLOAD)
    p.update(tool_name="AskUserQuestion", tool_input={})
    m = H.hook_to_message(p, {})
    assert m["op"] == "update" and m["kind"] == "question"


def test_request_ids_are_unique():
    p = json.loads(PAYLOAD)
    ids = {H.hook_to_message(p, {})["id"] for _ in range(100)}
    assert len(ids) == 100


def test_wait_is_bounded_and_configurable():
    assert H.approve_wait({}) == H.DEFAULT_WAIT
    assert H.approve_wait({"FROSTBITE_APPROVE_WAIT": "5"}) == 5
    assert H.approve_wait({"FROSTBITE_APPROVE_WAIT": "9999"}) == H.MAX_WAIT
    assert H.approve_wait({"FROSTBITE_APPROVE_WAIT": "soon"}) == H.DEFAULT_WAIT
    p = json.loads(PAYLOAD)
    assert H.hook_to_message(p, {"FROSTBITE_APPROVE_WAIT": "0"})["op"] == "update"


def test_snippet_gives_the_hook_longer_than_its_wait():
    hooks = hooks_snippet("/x")["hooks"]
    assert hooks["PermissionRequest"][0]["hooks"][0]["timeout"] > H.DEFAULT_WAIT + 2
    assert hooks["PermissionRequest"][0]["matcher"] == "*"
    assert hooks["Stop"][0]["hooks"][0]["timeout"] == 5
    assert set(hooks) == set(HOOK_EVENTS)


def test_return_keystroke_path_is_gone():
    source = (HOST / "frostbite_host" / "actions.py").read_text()
    assert "key code 36" not in source and '"return"' not in source and "keystroke \"" not in source
    assert not hasattr(Actions, "guarded_key")
    assert all("key code 53" in script for script in A.PRESS_ESCAPE.values())


# ------------------------------------------------------------------ Stop

def test_r2_03_readme_says_what_fallback_stop_does():
    readme = " ".join((HOST / "README.md").read_text().split())
    assert "Stop is a plain Escape to whatever app is in front" in readme
    assert "only ever reach" not in readme


def test_r2_12_press_after_a_stall_is_dropped_but_later_ones_count():
    class Stalls(FakeDevice):
        stall = 0.0

        def read(self, timeout_ms):
            wait, self.stall = self.stall, 0.0
            if wait:
                self._inbox.put(encode_device(KeyEvent(6, TAP)))
                time.sleep(wait)
            return super().read(timeout_ms)

    fake = Stalls()
    events = []
    link = DeviceLink(fake.opener(), events.append, ping_interval=0.05, read_timeout_ms=5)
    link.start()
    assert wait_for(lambda: "connected" in events)
    fake.stall = 0.8
    time.sleep(1.2)
    assert not any(isinstance(e, KeyEvent) for e in events)
    fake.press("approve")
    assert wait_for(lambda: any(isinstance(e, KeyEvent) for e in events))
    link.stop()


def test_r2_07_every_event_carries_the_tty(monkeypatch):
    monkeypatch.setattr(H, "controlling_tty", lambda: TTY)
    for name in ("pre_tool_use_bash.json", "post_tool_use.json", "stop.json"):
        m = H.hook_to_message(json.loads((FIX / "hooks" / name).read_text()), {})
        assert m["terminal"]["tty"] == TTY


def test_r2_07_restart_stop_works_on_a_running_session():
    d, fake, runner, clock = make()
    hook(d, "pre_tool_use_bash.json")            # first event this daemon has heard
    d.handle(("dev", KeyEvent(8, TAP)))
    assert runner.keystrokes() == [ESCAPE]


def test_r2_11_tmux_message():
    d, fake, runner, clock = make()
    d.handle(("ipc", {"op": "update", "source": "claude", "key": "claude:t", "name": "n", "status": "run",
                      "terminal": {"bundle": "com.apple.Terminal", "tty": "/dev/ttys050", "tmux": "1"}}, None))
    d.handle(("dev", KeyEvent(8, TAP)))
    assert fake.oled[1].rstrip() == "answer in terminal"
    assert H.terminal_info({"TMUX": "/tmp/tmux,1,0"})["tmux"] == "1"


def test_r2_18_two_running_sessions_on_one_tty_get_no_stop():
    d, fake, runner, clock = make()
    hook(d, "user_prompt_submit.json")
    hook(d, "user_prompt_submit.json", session_id="child")
    assert d.board.find("claude:child") is not None
    assert d.board.slots[0] is not None          # a running slot is not deleted
    d.handle(("dev", KeyEvent(8, TAP)))
    assert runner.keystrokes() == [] and fake.oled[1].rstrip() == "answer in terminal"


def test_r2_20_unknown_outcome_is_not_retried():
    d, fake, runner, clock = make()
    hook(d, "user_prompt_submit.json")

    class Hangs(FakeRunner):
        def __call__(self, args, **kw):
            if "key code" in " ".join(args):
                self.calls.append(args)
                raise subprocess.TimeoutExpired(args, 3)
            return super().__call__(args, **kw)

    r = Hangs()
    d.actions.runner = r
    d.handle(("dev", KeyEvent(8, TAP)))
    d.handle(("dev", KeyEvent(8, TAP)))
    assert len(r.keystrokes()) == 1


def test_r2_05_tty_lookup_walks_past_a_wrapper(monkeypatch):
    chain = {4000: "3000 ??", 3000: "2000 ??", 2000: "1000 ttys007"}
    monkeypatch.setattr(os, "getppid", lambda: 4000)

    def fake_run(args, **kw):
        return subprocess.CompletedProcess(args, 0, chain[int(args[-1])] + "\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert REAL_CONTROLLING_TTY() == "/dev/ttys007"


def test_r2_05_no_tty_anywhere_is_empty(monkeypatch):
    monkeypatch.setattr(os, "getppid", lambda: 4000)

    def fake_run(args, **kw):
        return subprocess.CompletedProcess(args, 0, "1 ??\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert REAL_CONTROLLING_TTY() == ""


# ------------------------------------------------------------------ R2-04, R2-16: training runs

def test_r2_04_stale_log_is_not_amber_and_the_pad_clears_it(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("Epoch 10/10 - loss: 0.01\n")
    d, fake, runner, clock = make()
    w = TrainWatcher(str(p), "run", lambda m: d.handle(("ipc", m, None)), clock=lambda: clock[0])
    w.poll_once()
    assert fake.slots[0] is Status.RUN
    clock[0] += 601
    w.poll_once()
    assert fake.slots[0] is Status.IDLE and d.board.glow()[:3] != (0xFF, 0xB0, 0x20)
    assert fake.oled[1].startswith("quiet 10m")
    d.handle(("dev", KeyEvent(0, TAP)))          # already selected: acknowledges
    assert d.board.slots[0] is None and fake.oled[1].rstrip() == "cleared"
    w.poll_once()
    assert d.board.slots[0] is None              # stays gone
    with p.open("a") as f:
        f.write("step 9 loss 0.2\n")
    w.poll_once()
    assert fake.slots[0] is Status.RUN           # back if it really is alive


def test_r2_04_a_tap_only_selects_first():
    d, fake, runner, clock = make()
    d.handle(("ipc", {"op": "set_slot", "slot": 2, "status": "done", "name": "CI"}, None))
    d.handle(("dev", KeyEvent(2, TAP)))
    assert d.board.selected == 2 and d.board.slots[2] is not None
    d.handle(("dev", KeyEvent(2, TAP)))
    assert d.board.slots[2] is None


def test_r2_04_a_tap_never_clears_running_or_claude_slots():
    d, fake, runner, clock = make()
    hook(d, "stop.json")
    d.handle(("ipc", {"op": "set_slot", "slot": 1, "status": "run", "name": "CI"}, None))
    d.handle(("dev", KeyEvent(0, TAP)))
    d.handle(("dev", KeyEvent(1, TAP)))
    d.handle(("dev", KeyEvent(1, TAP)))
    assert d.board.slots[0] is not None and d.board.slots[1] is not None


def test_r2_04_quiet_run_frees_itself():
    b = Board()
    b.apply({"op": "update", "source": "train", "key": "t", "name": "t", "status": "idle",
             "detail": "quiet 10m"}, 0)
    assert not b.expire(599)
    assert b.expire(600) and b.slots[0] is None


def test_r2_04_restart_on_an_old_log_is_quiet_at_once(tmp_path):
    p = tmp_path / "old.log"
    p.write_text("step 10 loss 0.5\n")
    month = time.time() - 30 * 86400
    os.utime(p, (month, month))
    out = []
    w = TrainWatcher(str(p), "r", out.append)
    w.poll_once()
    assert out[-1]["status"] == "idle" and out[-1]["detail"].startswith("quiet")


@pytest.mark.parametrize("line", ["`Trainer.fit` stopped: `max_epochs=10` reached."])
def test_r2_04_common_final_lines(line):
    assert parse_line(line).done is True


def test_r2_16_growing_log_with_no_metrics_keeps_its_slot(tmp_path):
    clock = [0.0]
    b = Board()
    w = TrainWatcher(str(tmp_path / "x"), "r", lambda m: b.apply(m, clock[0]), clock=lambda: clock[0])
    for hour in range(30):
        for _ in range(6):
            clock[0] += 600
            w.feed_text("still working\n")
        b.expire(clock[0])
    assert b.find(w.key) is not None


# ------------------------------------------------------------------ R2-09 overflow, R2-13

def test_r2_09_overflow_clears_when_the_seventh_is_answered():
    d, fake, runner, clock = make()
    for i in range(6):
        d.handle(("ipc", {"op": "update", "source": "claude", "key": f"c{i}", "name": "n", "status": "run"}, None))
    seven = {"op": "update", "source": "claude", "key": "c6", "name": "n"}
    assert d.handle_ipc({**seven, "status": "needs"})["ok"] is False
    assert d.board.glow()[:3] == (0xFF, 0xB0, 0x20)
    assert len(d.board.oled_lines(clock[0])[1]) <= 21 and d.board.oled_lines(clock[0])[1] == "agent waits, no slot"
    d.handle_ipc({**seven, "status": "run"})
    assert d.board.overflow == {} and d.board.glow()[:3] != (0xFF, 0xB0, 0x20)


def test_seventh_request_is_released_at_once():
    d, fake, runner, clock = make()
    for i in range(6):
        d.handle(("ipc", {"op": "update", "source": "claude", "key": f"c{i}", "name": "n", "status": "run"}, None))
    rid, reply = ask(d, clock)
    assert reply.get_nowait() == {"id": rid, "decision": None}
    assert d.board.glow()[:3] == (0xFF, 0xB0, 0x20)


def test_r2_13_a_tool_in_flight_is_not_evicted():
    b = Board()
    b.apply({"op": "update", "source": "claude", "key": "c0", "name": "n", "status": "run",
             "tool": "Bash(x)", "detail": "Bash(x)"}, 0)
    b.slots[0].status = Status.IDLE
    for i in range(1, 6):
        b.apply({"op": "update", "source": "claude", "key": f"c{i}", "name": "n", "status": "run"}, 0)
    assert b.apply({"op": "update", "source": "claude", "key": "new", "name": "n", "register_only": True}, 1) is False
    assert b.find("c0") == 0
