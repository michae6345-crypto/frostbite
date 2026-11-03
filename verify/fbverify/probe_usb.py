"""Run the host's real device code against a fake `hid` module. Usage: probe_usb.py <host dir> <vid> <pid> <page> <usage>.
Standalone on purpose: it imports frostbite_host only, and never touches a real device."""
import json
import sys
import types

host, vid, pid, page, usage = sys.argv[1], *[int(v, 0) for v in sys.argv[2:6]]
sys.path.insert(0, host)
state = {"devices": [], "opened": []}


class FakeDevice:
    def open_path(self, path):
        state["opened"].append(path.decode() if isinstance(path, bytes) else str(path))

    def open(self, *a, **k):
        state["opened"].append(f"open{a}")

    def set_nonblocking(self, *_):
        pass

    def close(self):
        pass


def enumerate_(vendor_id=0, product_id=0):
    return [dict(d) for d in state["devices"]
            if (not vendor_id or d["vendor_id"] == vendor_id) and (not product_id or d["product_id"] == product_id)]


fake = types.ModuleType("hid")
fake.enumerate = enumerate_
fake.device = FakeDevice
fake.Device = FakeDevice
sys.modules["hid"] = fake
from frostbite_host import device as D  # noqa: E402


def dev(name, v, p, up, u):
    return {"path": name.encode(), "vendor_id": v, "product_id": p, "usage_page": up, "usage": u,
            "manufacturer_string": name, "product_string": name}


pad = dev("frostbite-raw", vid, pid, page, usage)
scenes = {
    "other QMK board with the same Raw HID usage, listed first, plus the pad": [dev("keychron", 0x3434, 0x0123, page, usage), pad],
    "only another QMK board": [dev("keychron", 0x3434, 0x0123, page, usage)],
    "same VID, other PID": [dev("sibling", vid, pid + 1, page, usage)],
    "same PID, other VID": [dev("cousin", vid + 1, pid, page, usage)],
    "the pad's keyboard interface only": [dev("frostbite-kbd", vid, pid, 0x01, 0x06)],
}
want = {k: (["frostbite-raw"] if "plus the pad" in k else []) for k in scenes}
out = {"vendor_id": getattr(D, "VENDOR_ID", None), "product_id": getattr(D, "PRODUCT_ID", None), "scenes": {}}
for name, devs in scenes.items():
    state.update(devices=devs, opened=[])
    t = D.HidTransport.open()
    out["scenes"][name] = {"opened": list(state["opened"]), "want": want[name], "returned": t is not None}
print(json.dumps(out))
