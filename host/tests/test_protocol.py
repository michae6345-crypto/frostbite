import sys
import types

import pytest

from frostbite_host.device import (CCW, CW, HOLD, REPORT_LEN, TAP, EncoderEvent, HidTransport, KeyEvent,
                                   OledLine, Ping, PingReply, SetAll, SetGlow, SetSelected,
                                   SetSlot, Status, Unknown, decode_device, decode_host, encode,
                                   encode_device, to_ascii)

HOST_MSGS = [
    SetSlot(0, Status.IDLE),
    SetSlot(5, Status.ERROR),
    SetAll((Status.RUN, Status.DONE, Status.NEEDS, Status.ERROR, Status.IDLE, Status.RUN)),
    OledLine(0, "claude#2 my-app  WAIT"),
    OledLine(1, ""),
    SetGlow(0xFF, 0xB0, 0x20, 160),
    Ping(),
    SetSelected(3),
]


@pytest.mark.parametrize("msg", HOST_MSGS, ids=lambda m: type(m).__name__)
def test_host_round_trip(msg):
    rep = encode(msg)
    assert len(rep) == REPORT_LEN
    assert decode_host(rep) == msg


@pytest.mark.parametrize("msg", [PingReply(1, 4), KeyEvent(0, TAP), KeyEvent(8, HOLD),
                                 EncoderEvent(1, 2), EncoderEvent(-1, 5)])
def test_device_round_trip(msg):
    rep = encode_device(msg)
    assert len(rep) == REPORT_LEN
    assert decode_device(rep) == msg


def test_exact_bytes_match_design_json():
    z = bytes
    assert encode(SetSlot(2, Status.NEEDS)) == z([0x01, 2, 3]) + z(29)
    assert encode(SetAll((1, 0, 2, 3, 4, 0))) == z([0x02, 1, 0, 2, 3, 4, 0]) + z(25)
    assert encode(OledLine(1, "Bash(npm test)?")) == z([0x03, 1, 15]) + b"Bash(npm test)?" + z(14)
    assert encode(SetGlow(1, 2, 3, 4)) == z([0x04, 1, 2, 3, 4]) + z(27)
    assert encode(Ping()) == z([0x05]) + z(31)
    assert encode(SetSelected(5)) == z([0x06, 5]) + z(30)
    assert decode_device(z([0x81, 6, 2])) == KeyEvent(6, HOLD)
    assert decode_device(z([0x82, CW, 1])) == EncoderEvent(1, 1)
    assert decode_device(z([0x82, CCW, 0])) == EncoderEvent(-1, 0)
    assert decode_device(z([0x05, 1, 3])) == PingReply(1, 3)


def test_oled_line_truncates_to_21_ascii():
    rep = encode(OledLine(0, "héllo wörld → this is far too long"))
    assert rep[2] == 21
    text = rep[3:3 + 21].decode("ascii")
    assert text == "hello world > this is"
    assert rep[24:] == bytes(8)


def test_to_ascii():
    assert to_ascii("naïve “quotes”\ttab") == 'naive "quotes" tab'
    assert to_ascii("日本") == "??"
    assert all(0x20 <= ord(c) <= 0x7E for c in to_ascii("\x00\x07é☃"))


def test_validation():
    with pytest.raises(ValueError):
        encode(SetSlot(6, Status.RUN))
    with pytest.raises(ValueError):
        encode(SetAll((Status.RUN,) * 5))
    with pytest.raises(ValueError):
        encode(OledLine(2, "x"))
    with pytest.raises(ValueError):
        encode(SetGlow(256, 0, 0, 0))


def test_unknown_and_malformed_device_reports():
    assert isinstance(decode_device(bytes([0x99, 1, 2])), Unknown)
    assert isinstance(decode_device(bytes([0x81, 9, 1])), Unknown)   # key index out of range
    assert isinstance(decode_device(bytes([0x81, 0, 3])), Unknown)   # bad action
    assert isinstance(decode_device(bytes([0x82, 2, 0])), Unknown)   # bad direction
    assert decode_device(b"") == Unknown(bytes(32))                   # short report padded


def test_status_parse():
    assert Status.parse("wait") is Status.NEEDS
    assert Status.parse("FAIL") is Status.ERROR
    assert Status.parse("2") is Status.DONE
    with pytest.raises(ValueError):
        Status.parse("bogus")


def fake_hid(monkeypatch, devices):
    fake = types.ModuleType("hid")
    opened = []

    class Dev:
        def open_path(self, path):
            opened.append(path)

    fake.device = Dev
    fake.enumerate = lambda *a: list(devices)   # returns everything, whatever is asked for
    monkeypatch.setitem(sys.modules, "hid", fake)
    return opened


def hid_entry(path, vid, pid, page=0xFF60, usage=0x61):
    return {"path": path, "vendor_id": vid, "product_id": pid, "usage_page": page, "usage": usage}


def test_only_frostbite_is_opened_next_to_a_via_keyboard(monkeypatch):
    opened = fake_hid(monkeypatch, [hid_entry(b"via", 0x3434, 0x0121),
                                    hid_entry(b"same-vid", 0xFEED, 0x0001),
                                    hid_entry(b"same-pid", 0x3434, 0x4642),
                                    hid_entry(b"kbd-iface", 0xFEED, 0x4642, page=0x01, usage=0x06),
                                    hid_entry(b"pad", 0xFEED, 0x4642)])
    assert HidTransport.open() is not None
    assert opened == [b"pad"]


def test_no_frostbite_means_nothing_is_opened(monkeypatch):
    opened = fake_hid(monkeypatch, [hid_entry(b"via", 0x3434, 0x0121)])
    assert HidTransport.open() is None and opened == []
