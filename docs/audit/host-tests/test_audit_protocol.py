"""Host encoder vs the REAL keymap.c, compiled with stubs (fw_harness.c).
Needs clang. Run: cd host && uv run pytest ../docs/audit/host-tests/test_audit_protocol.py -q"""
import pathlib, shutil, subprocess, pytest
from frostbite_host.device import *
from frostbite_host import device as D

HERE = pathlib.Path(__file__).parent

@pytest.fixture(scope="module")
def fw(tmp_path_factory):
    if not shutil.which("clang"):
        pytest.skip("no clang")
    exe = tmp_path_factory.mktemp("fw") / "fw"
    subprocess.run(["clang", "-std=gnu11", "-w", "-DQMK_KEYBOARD_H=\"qmk_stub.h\"", f"-I{HERE/'fw_stub'}",
                    str(HERE / "fw_harness.c"), "-o", str(exe)], check=True)
    return exe

def run(fw, *cmds):
    out = subprocess.run([str(fw)], input="\n".join(cmds) + "\n", capture_output=True, text=True, check=True)
    return out.stdout.splitlines()

R = lambda m: "R " + encode(m).hex()
PING = R(Ping())

def test_report_len_and_hid_write_shape():
    sent = []
    class Dev:
        def write(self, b): sent.append(b); return len(b)
    t = HidTransport(Dev(), {})
    t.write(encode(Ping()))
    assert len(sent[0]) == 33 and sent[0][0] == 0 and sent[0][1] == 5 and len(encode(Ping())) == 32

def test_set_all(fw):
    st = run(fw, PING, R(SetAll((Status.IDLE, Status.RUN, Status.DONE, Status.NEEDS, Status.ERROR, Status.RUN))), "D")[-1]
    assert "status=012341" in st

def test_set_slot(fw):
    assert "status=000300" in run(fw, PING, R(SetSlot(3, Status.NEEDS)), "D")[-1]

def test_oled_exact(fw):
    st = run(fw, PING, R(OledLine(0, "claude#1 my-app  WAIT")), R(OledLine(1, "Bash(npm test)?".ljust(21))), "D")[-1]
    assert "line0=[claude#1 my-app  WAIT]" in st and "line1=[Bash(npm test)?      ]" in st
    assert "oled0=[claude#1 my-app  WAIT]" in st

def test_oled_nonascii_never_reaches_firmware_as_high_bytes(fw):
    rep = encode(OledLine(0, "café-\U0001F9CA-日本"))
    assert all(0x20 <= b <= 0x7e for b in rep[3:3 + rep[2]])
    assert "line0=[cafe-?-??]" in run(fw, PING, "R " + rep.hex(), "D")[-1]

def test_glow(fw):
    assert "glow=ffb020@160" in run(fw, PING, R(SetGlow(0xff, 0xb0, 0x20, 160)), "D")[-1]

def test_selected(fw):
    assert "sel=4" in run(fw, PING, R(SetSelected(4)), "D")[-1]

def test_ping_reply_decodes(fw):
    lines = run(fw, R(SetSelected(2)), PING)
    send = [l for l in lines if l.startswith("SEND")][-1].split()[1]
    assert len(send) == 64 and decode_device(bytes.fromhex(send)) == PingReply(1, 2)

@pytest.mark.parametrize("idx", range(9))
def test_key_tap_decodes(fw, idx):
    lines = run(fw, PING, "T 1", f"K {idx} 1", "T 50", f"K {idx} 0")
    sends = [l for l in lines if l.startswith("SEND")][1:]
    assert decode_device(bytes.fromhex(sends[0].split()[1])) == KeyEvent(idx, TAP) and len(sends) == 1

def test_key_hold_decodes_once_no_tap_on_release(fw):
    lines = run(fw, PING, "T 1", "K 6 1", "T 401", "T 10", "K 6 0")
    sends = [decode_device(bytes.fromhex(l.split()[1])) for l in lines if l.startswith("SEND")][1:]
    assert sends == [KeyEvent(6, HOLD)]

def test_encoder_decodes_wrap(fw):
    lines = run(fw, PING, "T 1", "E 0", "E 1", "E 1")
    sends = [decode_device(bytes.fromhex(l.split()[1])) for l in lines if l.startswith("SEND")][1:]
    assert sends == [EncoderEvent(-1, 5), EncoderEvent(1, 0), EncoderEvent(1, 1)]

def test_host_timeout_is_5s_and_ping_2s_keeps_it(fw):
    assert "host=1" in run(fw, PING, "T 4999", "D")[-1]
    assert "host=0" in run(fw, PING, "T 5000", "D")[-1]

def test_garbage_reports_do_not_crash_fw(fw):
    cmds = [PING] + ["R " + (bytes([c]) + b"\xff" * 31).hex() for c in range(256)] + ["D"]
    assert run(fw, *cmds)[-1].startswith("STATE")
