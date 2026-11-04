"""Findings from docs/audit/host.md as normal tests. Test names carry the finding ids.
No real command runs: the runner is fake, nothing presses keys."""
import json, os, queue, subprocess, sys, types
import pytest
from frostbite_host.actions import Actions
from frostbite_host.ctl import HOOK_EVENTS, hooks_snippet
from frostbite_host.daemon import Daemon
from frostbite_host.device import *
from frostbite_host.hook import hook_to_message
from frostbite_host.state import Board, fit_lr, Slot
from frostbite_host.train import RunState, TrainWatcher, parse_line

TTY = "/dev/ttys001"


class Runner:
    """`tab` is the tty of the focused tab; "" means it cannot be read."""

    def __init__(self, front="com.apple.Terminal", tab=""):
        self.front, self.tab, self.calls = front, tab, []

    def __call__(self, args, **kw):
        self.calls.append(args)
        out = ""
        if args[:2] == ["lsappinfo", "front"]:
            out = "ASN:0x0-0x1:\n"
        elif args[:2] == ["lsappinfo", "info"]:
            out = f'"CFBundleIdentifier"="{self.front}"\n'
        elif args[0] == "osascript" and "key code" in " ".join(args):
            out = "sent\n"
        elif args[0] == "osascript" and "tty of" in " ".join(args):
            out = self.tab + "\n"
        return subprocess.CompletedProcess(args, 0, out, "")

    @property
    def keys(self):
        return [a for a in self.calls if a[0] == "osascript" and "key code" in " ".join(a)]


def rig(front="com.apple.Terminal", tab=""):
    r = Runner(front, tab)
    b = Board()
    return r, b, Daemon(b, Actions(runner=r, out=lambda s: None), send=lambda m: None)


def ev(event, sid="A", bundle="com.apple.Terminal", **kw):
    return hook_to_message({"hook_event_name": event, "session_id": sid,
                            "cwd": kw.pop("cwd", f"/w/{sid}"), **kw},
                           {"__CFBundleIdentifier": bundle} if bundle else {})


def feed(b, *msgs, now=1000.0):
    for m in msgs:
        if m is not None:
            b.apply(m, now)


ASK = dict(tool_name="Bash", tool_input={"command": "rm -rf build"})


def running_session(b, sid="A", tty=TTY, bundle="com.apple.Terminal"):
    """A running session. The tab the runner reports as focused decides whether Stop may act."""
    feed(b, ev("UserPromptSubmit", sid, bundle=bundle, prompt="go"))
    b.slots[b.find(f"claude:{sid}")].terminal["tty"] = tty


def live_request(d, clock=None, **kw):
    """A PermissionRequest hook connected and waiting, past the OLED settling time."""
    reply = queue.Queue()
    d.handle(("ipc", ev("PermissionRequest", **{**ASK, **kw}), reply))
    d._shown_at -= 10
    return reply


# -- passes: these must keep passing -----------------------------------------------------
def test_pass_pretooluse_never_means_needs():
    assert ev("PreToolUse", **ASK)["status"] == "run"


def test_pass_permissionrequest_means_needs():
    assert ev("PermissionRequest", **ASK)["status"] == "needs"


def test_pass_refuses_nonterminal_front():
    r, b, d = rig("com.tinyspeck.slackmacgap", tab=TTY)
    running_session(b)
    d.handle_device(KeyEvent(KEY_STOP, TAP))
    assert r.keys == []


def test_pass_refuses_other_known_terminal_app():
    r, b, d = rig("com.googlecode.iterm2", tab=TTY)
    running_session(b)
    d.handle_device(KeyEvent(KEY_STOP, TAP))
    assert r.keys == []


def test_pass_no_shell_or_script_built_from_untrusted_text():
    evil = '"; do shell script "touch /tmp/pwn"; --'
    r, b, d = rig()
    b.apply({"op": "update", "source": "claude", "key": "k", "name": evil, "cwd": "/tmp/" + evil,
             "log": "/tmp/" + evil + ".jsonl", "status": "needs", "detail": evil,
             "terminal": {"bundle": "com.apple.Terminal", "tty": '/dev/ttys001"; x'}}, 0.0)
    a = Actions(runner=r, out=lambda s: None)
    a.focus(b.slots[0])
    assert r.calls == [["open", "-b", "com.apple.Terminal"]]  # bad tty rejected by TTY_RE


def test_pass_nonascii_names_never_overflow():
    b = Board()
    feed(b, {"op": "update", "source": "claude", "key": "k", "name": "\U0001F9CA\U0001F9CA frost",
             "status": "needs", "detail": "日本語"})
    for ln in b.oled_lines(1000.0):
        assert len(ln) <= OLED_COLS and ln.isascii()


def test_pass_non_utf8_and_tqdm(tmp_path):
    p = tmp_path / "x.log"
    p.write_bytes(b"step 1 loss 0.5 \xff\xfe\x00\nstep 2 loss 0.4\n")
    w = TrainWatcher(str(p), "r", lambda m: None)
    w.poll_once()
    assert (w.state.status, w.state.step) == ("run", 2)


def test_pass_split_multibyte_does_not_look_like_truncation(tmp_path):
    p = tmp_path / "x.log"
    data = "step 1 loss 0.5 █ x\n".encode()
    p.write_bytes(data[:17])
    w = TrainWatcher(str(p), "r", lambda m: None)
    w.poll_once()
    with open(p, "ab") as f:
        f.write(data[17:])
    w.poll_once()
    assert w.state.lines == 1 and w.state.step == 1


# -- device selection --------------------------------------------------------------------
def test_device_selection_requires_frostbite_vid_pid(monkeypatch):
    fake = types.ModuleType("hid")
    opened = []

    class Dev:
        def open_path(self, p):
            opened.append(p)

    fake.device = Dev
    fake.enumerate = lambda *a: [{"path": b"via", "vendor_id": 0x3434, "product_id": 0x0121,
                                  "usage_page": 0xFF60, "usage": 0x61}]
    monkeypatch.setitem(sys.modules, "hid", fake)
    HidTransport.open()
    assert opened == []  # a Keychron/VIA board must never be opened


# -- keystrokes --------------------------------------------------------------------------
def test_stop_checks_the_frontmost_tab_is_the_slots_session():
    r, b, d = rig(tab="/dev/ttys002")            # session B's tab is in front
    running_session(b, "A", "/dev/ttys001")
    running_session(b, "B", "/dev/ttys002")
    d.handle_device(KeyEvent(KEY_STOP, TAP))     # slot 1 selected
    d.push()
    assert any("tty" in " ".join(c) for c in r.calls) and r.keys == []
    assert b.oled_lines(d.clock())[1] == "tap slot first"
    assert b.slots[0].status == Status.RUN       # nothing was stopped


def test_vscode_gets_no_keystroke_without_knowing_terminal_panel_has_focus():
    r, b, d = rig("com.microsoft.VSCode", tab=TTY)
    running_session(b, bundle="com.microsoft.VSCode")  # even with a tty there is no focus proof
    d.handle_device(KeyEvent(KEY_STOP, TAP))
    assert r.keys == []


@pytest.mark.parametrize("msg", [None,
                                 {"op": "update", "source": "train", "key": "t", "name": "t", "status": "run"},
                                 {"op": "set_slot", "slot": 0, "status": "run", "name": "CI"}])
def test_stop_needs_a_claude_slot(msg):
    r, b, d = rig(tab=TTY)
    feed(b, msg)
    d.handle_device(KeyEvent(KEY_STOP, TAP))
    assert r.keys == []


@pytest.mark.parametrize("msg", [{"op": "update", "source": "train", "key": "t", "name": "t", "status": "needs"},
                                 {"op": "set_slot", "slot": 0, "status": "needs", "name": "CI"}])
def test_approve_needs_a_claude_slot(msg):
    r, b, d = rig(tab=TTY)
    feed(b, msg)
    d.handle_device(KeyEvent(KEY_APPROVE, TAP))
    assert r.calls == [] and d.requests == {}


@pytest.mark.parametrize("bundle", ["com.anthropic.claudefordesktop", "", "com.todesktop.230313mzl4w4u92"])
def test_unknown_session_terminal_fails_closed(bundle):
    r, b, d = rig(tab=TTY)
    running_session(b, bundle=bundle)
    d.handle_device(KeyEvent(KEY_STOP, TAP))
    assert r.keys == []


def test_second_approve_tap_sends_nothing():
    r, b, d = rig()
    reply = live_request(d)
    d.handle_device(KeyEvent(KEY_APPROVE, TAP))
    d.push()
    d.handle_device(KeyEvent(KEY_APPROVE, TAP))
    assert reply.qsize() == 1 and r.calls == []


def test_oled_keeps_the_oldest_unanswered_prompt():
    r, b, d = rig()
    feed(b, ev("PermissionRequest", tool_name="Bash", tool_input={"command": "rm -rf build"}),
         ev("PermissionRequest", tool_name="Bash", tool_input={"command": "ls"}))
    assert "rm -rf" in b.slots[0].detail


def test_frontmost_rechecked_at_keystroke():
    class Race(Runner):
        def __call__(self, args, **kw):
            res = super().__call__(args, **kw)
            if args[:2] == ["lsappinfo", "info"]:
                self.front = "com.tinyspeck.slackmacgap"
            return res

    r = Race(tab=TTY)
    b = Board()
    d = Daemon(b, Actions(runner=r, out=lambda s: None), send=lambda m: None)
    running_session(b)
    d.handle_device(KeyEvent(KEY_STOP, TAP))
    assert r.keys == []


# -- hook lifecycle ----------------------------------------------------------------------
def test_needs_clears_when_approved_tool_starts():
    # Docs: the only later events are PostToolUse (tool finished) / PostToolUseFailure.
    r, b, d = rig()
    live_request(d)
    d.handle_device(KeyEvent(KEY_APPROVE, TAP))
    assert b.slots[0].status != Status.NEEDS


def test_deny_leaves_needs():
    r, b, d = rig()
    live_request(d)
    d.handle_device(KeyEvent(KEY_APPROVE, HOLD))
    assert b.slots[0].status != Status.NEEDS


def test_sibling_posttooluse_keeps_needs():
    r, b, d = rig()
    feed(b, ev("PermissionRequest", **ASK), ev("PostToolUse", tool_name="Read", tool_input={}))
    assert b.slots[0].status == Status.NEEDS


def test_subagent_tool_keeps_needs_of_other_subagent():
    r, b, d = rig()
    feed(b, ev("PermissionRequest", agent_id="s1", **ASK),
         ev("PreToolUse", agent_id="s2", tool_name="Read", tool_input={"file_path": "/a"}))
    assert b.slots[0].status == Status.NEEDS


def test_interrupted_turn_does_not_stay_run_forever():
    b = Board()
    feed(b, ev("UserPromptSubmit", prompt="x"), ev("PreToolUse", tool_name="Bash", tool_input={"command": "x"}))
    b.expire(1000.0 + 7 * 86400)  # Stop never comes after an interrupt (docs, "Stop")
    assert b.slots[0] is None or b.slots[0].status != Status.RUN


def test_stopfailure_handled():
    assert ev("StopFailure", error="rate_limit") is not None and "StopFailure" in HOOK_EVENTS


def test_posttoolusefailure_in_snippet():
    assert "PostToolUseFailure" in hooks_snippet("/x")["hooks"]


@pytest.mark.parametrize("ntype", ["elicitation_url_dialog", "agent_needs_input"])
def test_other_waiting_notifications_mapped(ntype):
    assert ev("Notification", notification_type=ntype, message="x") is not None


def test_hooks_snippet_quotes_paths_with_spaces():
    cmd = hooks_snippet("/Users/a/My Tools/frostbite-hook")["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert '"' in cmd or "'" in cmd or "\\ " in cmd


# -- slots -------------------------------------------------------------------------------
def test_dead_sessions_free_eventually():
    b = Board()
    feed(b, {"op": "update", "source": "claude", "key": "claude:x", "name": "x", "status": "needs"}, now=0.0)
    b.expire(30 * 86400.0)
    assert b.slots[0] is None


def test_seventh_waiting_session_is_visible_somewhere():
    b = Board()
    d = Daemon(b, Actions(dry_run=True, out=lambda s: None), send=lambda m: None)
    for i in range(6):
        feed(b, {"op": "update", "source": "claude", "key": f"c{i}", "name": "n", "status": "run"})
    reply = d.handle_ipc({"op": "update", "source": "claude", "key": "c6", "name": "n", "status": "needs"})
    assert reply["ok"] is False or b.glow()[:3] == (0xFF, 0xB0, 0x20)


def test_idle_evicted_before_unseen_error():
    b = Board()
    feed(b, {"op": "update", "source": "train", "key": "t", "name": "t", "status": "error"}, now=100.0)
    for i in range(5):
        feed(b, {"op": "update", "source": "claude", "key": f"c{i}", "name": "n", "register_only": True}, now=0.0)
    feed(b, {"op": "update", "source": "claude", "key": "new", "name": "n", "register_only": True}, now=200.0)
    assert b.find("t") is not None


def test_flash_survives_clock_step_back_only_seconds():
    b = Board()
    b.flash("approved", 10000.0)
    assert not b.flash_active(10000.0 - 3600 + 600)  # time.time() stepped back 1 h, 10 min later


def test_session_name_survives_cd():
    b = Board()
    feed(b, ev("UserPromptSubmit", cwd="/w/app", prompt="x"),
         ev("PreToolUse", cwd="/w/app/packages/ui", tool_name="Read", tool_input={"file_path": "/x"}))
    assert b.slots[0].name == "app"


def test_two_repos_distinguishable_on_oled():
    a = fit_lr(Slot("k", "claude", "frostbite-host").title(0), "WAIT")
    c = fit_lr(Slot("k", "claude", "frostbite-firmware").title(0), "WAIT")
    assert a != c


def test_selection_converges_after_crossing_encoder_event():
    sent = []
    b = Board()
    d = Daemon(b, Actions(dry_run=True, out=lambda s: None), send=sent.append)
    d.push()
    d.handle_device(KeyEvent(2, TAP))     # host -> SET_SELECTED 2
    d.push()
    d.handle_device(EncoderEvent(1, 1))   # was in flight: pad moved to 1, then applied 2
    d.handle_device(PingReply(1, 2))      # pad says 2
    d.push()
    assert b.selected == 2


# -- training ----------------------------------------------------------------------------
@pytest.mark.parametrize("line", [
    "loss info: using cross entropy", "Using loss inf-norm", "Using loss: nan-safe mean",
    "saved best-loss-nan.pt", "saved val_loss_inf.pt", "loss_scale: inf",
    "ConnectionError: retrying in 5s", "ValueError: bad sample 17 skipped, continuing",
    "avoid OOM by lowering batch", '{"msg":"no error so far","step":9}',
    '{"message":"error rate 0.02"}'])
def test_no_false_error(line):
    assert parse_line(line).error is None


@pytest.mark.parametrize("line", [
    "loss: tensor(nan, grad_fn=<MeanBackward0>)", "loss is nan", "Loss became NaN at step 5",
    "[rank0]: Traceback (most recent call last):",
    "2026-01-01 12:00:00 ERROR Traceback (most recent call last):",
    "MPS backend out of memory (MPS allocated: 18 GB)"])
def test_no_missed_error(line):
    assert parse_line(line).error is not None


@pytest.mark.parametrize("line", [
    "Data preprocessing: all done", "warmup training finished, starting main loop",
    "Stage 1 training complete, starting stage 2", '{"event":"validation complete","step":5}',
    '{"status":"success","step":5,"loss":0.3}', '{"state":"finished epoch"}'])
def test_no_false_done(line):
    assert parse_line(line).done is False


def test_killed_process_is_not_green(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("step 1 loss 0.5\n")
    t = [0.0]
    out = []
    w = TrainWatcher(str(p), "r", out.append, clock=lambda: t[0])
    w.poll_once()
    t[0] = 601
    w.poll_once()
    assert out[-1]["status"] != "done"


def test_done_not_overwritten_by_trailing_lines(tmp_path):
    out = []
    w = TrainWatcher(str(tmp_path / "x"), "r", out.append)
    w.feed_text("Training complete\nwandb: Waiting for W&B process to finish\n")
    assert out[-1]["status"] == "done"


def test_rotation_reads_tail_of_old_file(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("step 1 loss 0.5\n")
    out = []
    w = TrainWatcher(str(p), "r", out.append)
    w.poll_once()
    with open(p, "a") as f:
        f.write("RuntimeError: final crash\n")
    os.rename(p, str(p) + ".1")
    p.write_text("")
    w.poll_once()
    w.poll_once()
    assert out[-1]["status"] == "error"


def test_copytruncate_regrow_is_a_new_run(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("ValueError: boom\n")
    w = TrainWatcher(str(p), "r", lambda m: None)
    w.poll_once()
    p.write_text("new run step 1 loss 0.5\n" * 20)
    w.poll_once()
    assert w.state.status == "run"


def test_deleted_log_does_not_stay_run_forever(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("step 1 loss 0.5\n")
    t = [0.0]
    out = []
    w = TrainWatcher(str(p), "r", out.append, clock=lambda: t[0])
    w.poll_once()
    os.unlink(p)
    for _ in range(5):
        t[0] += 3600
        w.poll_once()
    assert out[-1]["status"] != "run"


def test_two_logs_with_same_stem_both_watched(tmp_path):
    d = Daemon(Board(), Actions(dry_run=True, out=lambda s: None), send=lambda m: None,
               watcher_opts={"poll": 0.01})
    a = d.add_watcher(str(tmp_path / "A" / "train.log"))
    b = d.add_watcher(str(tmp_path / "B" / "train.log"))
    a_stopped = a._stop.is_set()
    a.stop(), b.stop()
    assert not a_stopped


@pytest.mark.parametrize("err", ["RuntimeError: inference failed", "FileNotFoundError: data/finance.csv"])
def test_error_label_is_not_called_a_loss_problem(err):
    r = RunState()
    r.feed(parse_line(err), err)
    assert "loss" not in r.detail()


def test_new_run_appended_after_error_clears_it(tmp_path):
    p = tmp_path / "x.log"
    p.write_text("RuntimeError: x\n")
    w = TrainWatcher(str(p), "r", lambda m: None)
    w.poll_once()
    with open(p, "a") as f:
        f.write("Starting training\nstep 1 loss 0.5\n")
    w.poll_once()
    assert w.state.status == "run"
