import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from frostbite_host import ipc
from frostbite_host.actions import Actions
from frostbite_host.daemon import Daemon, SocketServer
from frostbite_host.device import (HOLD, TAP, DeviceLink, EncoderEvent, FakeDevice, KeyEvent,
                                   OledLine, SetSelected, Status, encode)
from frostbite_host.state import Board

FIX = Path(__file__).parent / "fixtures"
TTY = "/dev/ttys004"
ESCAPE = "key code 53"


class FakeRunner:
    """Stands in for subprocess.run: answers lsappinfo and tty reads, records the rest."""

    def __init__(self, front="com.apple.Terminal", tab=TTY):
        self.front = front
        self.tab = tab
        self.calls = []

    def __call__(self, args, **kw):
        if args[:2] == ["lsappinfo", "front"]:
            return subprocess.CompletedProcess(args, 0, "ASN:0x0-0x1234:\n", "")
        if args[:2] == ["lsappinfo", "info"]:
            return subprocess.CompletedProcess(args, 0, f'"CFBundleIdentifier"="{self.front}"\n', "")
        joined = " ".join(args)
        if args[0] == "osascript" and "tty of" in joined and "key code" not in joined and "wanted" not in joined:
            return subprocess.CompletedProcess(args, 0, self.tab + "\n", "")
        self.calls.append(args)
        out = "sent\n" if "key code" in joined else ""
        return subprocess.CompletedProcess(args, 0, out, "")

    def keystrokes(self):
        """Which key each keystroke script pressed."""
        return [re.search(r"key code \d+", " ".join(c)).group(0) for c in self.calls
                if c[0] == "osascript" and "key code" in " ".join(c)]


def make(front="com.apple.Terminal", tab=TTY):
    fake = FakeDevice()
    runner = FakeRunner(front, tab)
    clock = [1000.0]
    d = Daemon(Board(), Actions(runner=runner, out=lambda s: None), send=lambda m: fake.write(encode(m)),
               clock=lambda: clock[0])
    return d, fake, runner, clock


def hook(d, name, reply=None, **over):
    from frostbite_host.hook import hook_to_message

    payload = {**json.loads((FIX / "hooks" / name).read_text()), **over}
    msg = hook_to_message(payload, {"__CFBundleIdentifier": "com.apple.Terminal"})
    if "terminal" in msg:
        msg["terminal"]["tty"] = TTY
    d.handle(("ipc", msg, reply))
    return msg


def ask(d, clock, **over):
    """A PermissionRequest hook connected and waiting; its request has been on the OLED a while."""
    reply = queue.Queue()
    msg = hook(d, "permission_request.json", reply, **over)
    clock[0] += 1
    return msg["id"], reply


def test_claude_session_flow_bytes():
    d, fake, runner, clock = make()
    hook(d, "user_prompt_submit.json")
    assert fake.slots[0] is Status.RUN
    hook(d, "pre_tool_use_bash.json")
    rid, reply = ask(d, clock)
    assert fake.slots[0] is Status.NEEDS
    assert fake.oled[0] == "claude#1 my-app  WAIT"
    assert fake.oled[1].rstrip() == "Bash(npm test)?"
    # exact report for the status change
    all_reports = [r for r in fake.reports if r[0] == 0x02]
    assert all_reports[-1] == bytes([0x02, 3, 0, 0, 0, 0, 0]) + bytes(25)
    # approve answers that hook and presses nothing
    d.handle(("dev", KeyEvent(6, TAP)))
    assert reply.get_nowait() == {"id": rid, "decision": "allow"}
    assert runner.calls == []
    assert fake.slots[0] is Status.RUN           # flipped at once: no hook fires at approval
    assert fake.oled[1].rstrip() == "approved"
    hook(d, "post_tool_use.json")
    assert fake.slots[0] is Status.RUN
    hook(d, "stop.json")
    assert fake.slots[0] is Status.DONE
    clock[0] += 601
    d.tick()
    assert fake.slots[0] is Status.IDLE
    assert fake.oled[0].rstrip() == "#1 empty"


def test_approve_with_nothing_waiting():
    d, fake, runner, clock = make()
    d.handle(("dev", KeyEvent(6, TAP)))
    assert fake.oled[1].rstrip() == "nothing to approve"
    assert runner.calls == []


def test_stop_refused_when_session_is_not_in_front():
    for kw in ({"front": "com.google.Chrome"}, {"front": "com.googlecode.iterm2"}, {"tab": "/dev/ttys009"}):
        d, fake, runner, clock = make(**kw)
        hook(d, "user_prompt_submit.json")
        d.handle(("dev", KeyEvent(8, TAP)))
        assert runner.keystrokes() == []
        assert fake.slots[0] is Status.RUN and fake.oled[1].rstrip() == "tap slot first"


def test_hold_approve_denies_without_a_keystroke():
    d, fake, runner, clock = make()
    rid, reply = ask(d, clock)
    d.handle(("dev", KeyEvent(6, HOLD)))
    assert reply.get_nowait() == {"id": rid, "decision": "deny"}
    assert runner.calls == []
    assert fake.oled[1].rstrip() == "denied" and fake.slots[0] is Status.RUN


def test_stop_escapes_only_a_running_session():
    d, fake, runner, clock = make()
    ask(d, clock)
    d.handle(("dev", KeyEvent(8, TAP)))           # waiting, not running
    assert runner.keystrokes() == [] and fake.oled[1].rstrip() == "answer in terminal"
    clock[0] += 5
    hook(d, "user_prompt_submit.json")
    d.handle(("dev", KeyEvent(8, TAP)))
    assert runner.keystrokes() == [ESCAPE]
    assert fake.slots[0] is Status.DONE and fake.oled[1].rstrip() == "stop sent"
    assert d.board.slots[0].detail == "interrupted"


def test_talk_does_nothing():
    d, fake, runner, _ = make()
    d.handle(("dev", KeyEvent(7, TAP)))
    assert runner.calls == []


def test_agent_key_selects_and_focuses_terminal_tab():
    d, fake, runner, _ = make()
    from frostbite_host.hook import hook_to_message

    payload = json.loads((FIX / "hooks" / "user_prompt_submit.json").read_text())
    payload["cwd"] = str(FIX)
    msg = hook_to_message(payload, {"__CFBundleIdentifier": "com.apple.Terminal"})
    msg["terminal"]["tty"] = "/dev/ttys004"
    d.handle(("ipc", msg, None))
    d.handle(("ipc", {"op": "set_slot", "slot": 2, "status": "run", "name": "CI"}, None))
    d.handle(("dev", KeyEvent(2, TAP)))
    assert fake.selected == 2 and fake.oled[0].startswith("#3 CI")
    assert runner.calls == []                 # ctl slot: just select
    d.handle(("dev", KeyEvent(0, TAP)))
    assert fake.selected == 0
    assert runner.calls[-1][:2] == ["osascript", "-e"] and runner.calls[-1][-1] == "/dev/ttys004"


def test_agent_hold_opens_log(tmp_path):
    d, fake, runner, _ = make()
    p = tmp_path / "run.log"
    p.write_text("step 1 loss 1\n")
    d.handle(("ipc", {"op": "set_slot", "slot": 1, "status": "run", "name": "x", "log": str(p)}, None))
    d.handle(("dev", KeyEvent(1, HOLD)))
    assert runner.calls[-1] == ["open", "-t", str(p)]


def test_encoder_updates_selection_without_echo():
    d, fake, runner, _ = make()
    n = len(fake.messages)
    d.handle(("dev", EncoderEvent(1, 4)))
    assert d.board.selected == 4
    new = fake.messages[n:]
    assert all(type(m).__name__ != "SetSelected" for m in new)
    assert any(isinstance(m, OledLine) and m.text.startswith("#5 empty") for m in new)


def test_dry_run_sends_no_keystrokes():
    out = []
    runner = FakeRunner()
    a = Actions(dry_run=True, runner=runner, out=out.append)
    from frostbite_host.state import Slot

    slot = Slot("k", "claude", "n", terminal={"bundle": "com.apple.Terminal", "tty": TTY})
    ok, msg = a.guarded_escape(slot, "stop sent")
    assert ok and runner.keystrokes() == [] and "key code 53" in out[-1]


# ----------------------------------------------------------------- threaded end to end

def wait_for(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def running():
    tmp = tempfile.mkdtemp(prefix="fb")   # short path: AF_UNIX limit is 104 bytes on macOS
    sock = Path(tmp) / "s.sock"
    fake = FakeDevice()
    runner = FakeRunner()
    board = Board()
    holder = {}
    d = Daemon(board, Actions(runner=runner, out=lambda s: None),
               send=lambda m: holder["link"].send(m))
    link = DeviceLink(fake.opener(), d.on_device, ping_interval=0.2, retry_interval=0.1,
                      read_timeout_ms=10, keepalive=d.keepalive)
    holder["link"] = link
    server = SocketServer(sock, d)
    server.start()
    link.start()
    t = threading.Thread(target=d.run, daemon=True)
    t.start()
    yield d, fake, runner, sock, tmp
    d.stop_event.set()
    t.join(2)
    link.stop()
    server.stop()


def test_end_to_end_hook_ctl_train_unplug(running):
    d, fake, runner, sock, tmp = running
    assert oct(os.stat(sock).st_mode & 0o777) == "0o600"
    assert oct(os.stat(tmp).st_mode & 0o777) == "0o700"
    env = {**os.environ, "FROSTBITE_SOCKET": str(sock), "__CFBundleIdentifier": "com.apple.Terminal"}

    # real frostbite-hook process -> socket -> daemon -> FakeDevice
    for name in ("user_prompt_submit.json", "pre_tool_use_bash.json", "notification_permission.json"):
        r = subprocess.run([sys.executable, "-m", "frostbite_host.hook"],
                           input=(FIX / "hooks" / name).read_text(), capture_output=True,
                           text=True, env=env, timeout=5)
        assert r.returncode == 0 and r.stdout == ""
    assert wait_for(lambda: fake.slots[0] is Status.NEEDS)
    assert wait_for(lambda: fake.oled[1].rstrip() == "Bash(npm test)?")
    assert wait_for(lambda: fake.pings >= 2)

    # frostbite-ctl
    r = subprocess.run([sys.executable, "-m", "frostbite_host.ctl", "set", "3", "run", "CI build"],
                       env=env, capture_output=True, text=True, timeout=5)
    assert r.returncode == 0, r.stderr
    assert wait_for(lambda: fake.slots[2] is Status.RUN)
    st = ipc.send({"op": "status"}, timeout=2, want_reply=True, path=sock)
    assert st["slots"][2]["name"] == "CI build"

    # training watcher via ctl watch
    log = Path(tmp) / "train.log"
    log.write_text("Epoch 3/10 | step 811 | loss: 0.4199\n")
    r = subprocess.run([sys.executable, "-m", "frostbite_host.ctl", "watch", str(log), "--name",
                        "my-model"], env=env, capture_output=True, text=True, timeout=5)
    assert r.returncode == 0, r.stderr
    assert wait_for(lambda: fake.slots[1] is Status.RUN)
    with log.open("a") as f:
        f.write("Epoch 3/10 | step 812 | loss: nan\n")
    assert wait_for(lambda: fake.slots[1] is Status.ERROR)

    # the hook that raised the amber has gone, so Approve finds nothing to answer
    fake.press("approve")
    assert wait_for(lambda: fake.oled[1].rstrip() == "answer in terminal")
    assert runner.keystrokes() == []

    # unplug / replug: full state comes back
    fake.unplug()
    time.sleep(0.3)
    fake.replug()
    assert wait_for(lambda: fake.slots[:3] == [Status.NEEDS, Status.ERROR, Status.RUN])
    assert wait_for(lambda: fake.oled[0].startswith("claude#1 my-app"))
    assert fake.glow is not None and fake.glow[:3] == (0xFF, 0x4D, 0x4F)


def test_second_daemon_refused_and_stale_socket_cleaned(running):
    d, fake, runner, sock, tmp = running
    with pytest.raises(SystemExit):
        SocketServer(sock, d).start()
    stale = Path(tmp) / "stale.sock"
    import socket as s

    x = s.socket(s.AF_UNIX, s.SOCK_STREAM)
    x.bind(str(stale))
    x.close()                              # file left behind, nobody listening
    srv = SocketServer(stale, d)
    srv.start()
    srv.stop()


# ----------------------------------------------------------------- pad recovery and identity

def test_set_all_goes_out_with_every_ping(running):
    d, fake, runner, sock, tmp = running
    ipc.send({"op": "set_slot", "slot": 1, "status": "run", "name": "x"}, path=sock)
    assert wait_for(lambda: fake.slots[1] is Status.RUN)
    start = fake.pings
    fake.slots[1] = Status.IDLE                 # the pad lost it during a PING gap
    assert wait_for(lambda: fake.slots[1] is Status.RUN, 2)
    assert fake.pings > start
    time.sleep(0.5)
    reports = [r[0] for r in list(fake.reports)]
    pairs = sum(1 for a, b in zip(reports, reports[1:]) if a == 0x05 and b == 0x02)
    assert pairs >= fake.pings - 2


def link_with(opener, **kw):
    events = []
    link = DeviceLink(opener, events.append, ping_interval=0.05, retry_interval=0.02,
                      read_timeout_ms=5, **kw)
    return link, events


def test_nothing_but_ping_reaches_a_device_with_the_wrong_protocol():
    fake = FakeDevice(version=2)
    link, events = link_with(fake.opener(), handshake_timeout=0.1)
    link.start()
    assert wait_for(lambda: fake.pings >= 2)
    link.send(SetSelected(0))
    link.stop()
    assert "connected" not in events and all(r[0] == 0x05 for r in fake.reports)


def test_nothing_but_ping_reaches_a_silent_device():
    class Mute(FakeDevice):
        def write(self, report):
            self.reports.append(report)

    fake = Mute()
    link, events = link_with(fake.opener(), handshake_timeout=0.05)
    link.start()
    assert wait_for(lambda: len(fake.reports) >= 2)
    link.stop()
    assert "connected" not in events and all(r[0] == 0x05 for r in fake.reports)


def test_wedged_device_is_reopened():
    fake = FakeDevice()
    link, events = link_with(fake.opener(), pong_timeout=0.1)
    link.start()
    assert wait_for(lambda: "connected" in events)
    real_write = fake.write
    fake.write = lambda report: None            # stops answering, writes still succeed
    assert wait_for(lambda: "disconnected" in events)
    fake.write = real_write
    assert wait_for(lambda: events.count("connected") == 2)
    link.stop()


def test_open_failure_is_logged_once_not_hidden(caplog):
    def broken():
        raise ImportError("hidapi is broken")

    link, events = link_with(broken)
    with caplog.at_level("WARNING", logger="frostbite.device"):
        link.start()
        assert wait_for(lambda: "hidapi is broken" in caplog.text)
        time.sleep(0.1)
        link.stop()
    assert caplog.text.count("hidapi is broken") == 1


def test_stale_queued_press_is_dropped():
    d, fake, runner, clock = make()
    rid, reply = ask(d, clock)
    d.handle(("dev", KeyEvent(6, TAP), time.monotonic() - 2))
    assert reply.empty() and fake.slots[0] is Status.NEEDS
    d.handle(("dev", KeyEvent(6, TAP), time.monotonic()))
    assert reply.get_nowait()["decision"] == "allow"


def test_double_tap_cannot_answer_the_next_prompt():
    d, fake, runner, clock = make()
    first, a = ask(d, clock)
    second, b = ask(d, clock, tool_input={"command": "rm -rf build"})
    d.handle(("dev", KeyEvent(6, TAP)))
    d.handle(("dev", KeyEvent(6, TAP)))           # "approved" is on the OLED, not the next prompt
    assert a.get_nowait() == {"id": first, "decision": "allow"} and b.empty()
    assert fake.slots[0] is Status.NEEDS
    clock[0] += 3.1
    d.tick()
    assert "rm -rf" in fake.oled[1]
    d.handle(("dev", KeyEvent(6, TAP)))           # on screen, but not long enough to have been read
    assert b.empty()
    clock[0] += 1
    d.handle(("dev", KeyEvent(6, TAP)))
    assert b.get_nowait() == {"id": second, "decision": "allow"}


def test_question_is_never_answered_from_the_pad():
    d, fake, runner, clock = make()
    for key in (TAP, HOLD):
        hook(d, "permission_request.json", tool_name="AskUserQuestion", tool_input={})
        d.handle(("dev", KeyEvent(6, key)))
    assert d.requests == {} and runner.calls == []
    assert fake.oled[1].rstrip() == "answer in terminal"


def test_stop_in_sessions_the_pad_can_never_prove():
    for term in ({"bundle": "com.mitchellh.ghostty", "tty": TTY},
                 {"bundle": "com.apple.Terminal", "tty": "/dev/ttys050", "tmux": "1"}):
        d, fake, runner, clock = make(tab="/dev/ttys001")
        d.handle(("ipc", {"op": "update", "source": "claude", "key": "claude:g", "name": "n",
                          "status": "run", "terminal": term}, None))
        d.handle(("dev", KeyEvent(8, TAP)))
        assert runner.keystrokes() == [] and fake.oled[1].rstrip() == "answer in terminal"


def test_refused_at_the_keystroke_is_not_counted_as_stopped():
    d, fake, runner, clock = make()
    hook(d, "user_prompt_submit.json")

    class Late(FakeRunner):
        def __call__(self, args, **kw):
            r = super().__call__(args, **kw)
            return subprocess.CompletedProcess(args, 0, "refused\n", "") if r.stdout == "sent\n" else r

    d.actions.runner = Late()
    d.handle(("dev", KeyEvent(8, TAP)))
    assert fake.slots[0] is Status.RUN and fake.oled[1].rstrip() == "tap slot first"


def test_fake_flag_never_sends_real_keystrokes(monkeypatch):
    import frostbite_host.daemon as dm

    seen = {}

    class Stop(Exception):
        pass

    def spy(dry_run=False, **kw):
        seen["dry_run"] = dry_run
        raise Stop

    monkeypatch.setattr(dm, "Actions", spy)
    with pytest.raises(Stop):
        dm.main(["--fake"])
    assert seen["dry_run"] is True


def test_custom_socket_leaves_parent_permissions_alone():
    tmp = tempfile.mkdtemp(prefix="fb")
    os.chmod(tmp, 0o755)
    d = Daemon(Board(), Actions(dry_run=True, out=lambda s: None), send=lambda m: None)
    srv = SocketServer(Path(tmp) / "s.sock", d)
    srv.start()
    srv.stop()
    assert oct(os.stat(tmp).st_mode & 0o777) == "0o755"


def test_malformed_ipc_leaves_no_half_slot():
    d = Daemon(Board(), Actions(dry_run=True, out=lambda s: None), send=lambda m: None)
    r = d.handle_ipc({"op": "update", "source": "claude", "key": "k2", "terminal": "str"})
    assert r["ok"] is False and d.board.find("k2") is None
