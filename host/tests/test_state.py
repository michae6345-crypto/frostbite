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
    b.apply({"op": "update", "key": "claude:s", "status": "needs", "tool_hint": "Edit"}, 2)
    assert b.slots[0].detail == "Edit?"


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


def test_glow_worst_status():
    b = Board()
    assert b.glow()[3] == 50
    b.update("a", "ctl", 0, status=Status.NEEDS)
    assert b.glow()[:3] == (0xFF, 0xB0, 0x20)
    b.update("b", "ctl", 0, status=Status.ERROR)
    assert b.glow()[:3] == (0xFF, 0x4D, 0x4F)
