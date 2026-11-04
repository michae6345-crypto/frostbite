#!/usr/bin/env python3
"""Round 2 end-to-end loop. Real: Daemon, Board, DeviceLink, SocketServer, frostbite-hook processes, the compiled
keymap.c and QMK OLED driver. Fake: the USB wire (ShimTransport), the Mac (FakeMac answers lsappinfo/osascript and
records "presses"; nothing is ever executed, so no key can be sent). The hook's tty is stubbed; tty_probe.py covers it.
Usage (from host/): uv run --frozen python ../docs/audit/round2-tests/e2e.py <fw_e2e> <scratch> [scenario ...]"""
import json, logging, os, queue, subprocess, sys, tempfile, threading, time, types
from pathlib import Path
from frostbite_host import actions as A, daemon as DM, device as D, ipc
from frostbite_host.state import Board

FW, SCRATCH = sys.argv[1], sys.argv[2]
os.chdir(tempfile.mkdtemp(dir=SCRATCH))
os.environ["FROSTBITE_DIR"] = "."
HOST = str(Path(D.__file__).resolve().parents[1])
RESULTS = []
def check(name, ok, extra=""):
    RESULTS.append((name, bool(ok)))
    print(("  PASS " if ok else "  FAIL ") + name + (f"   [{extra}]" if extra != "" else ""), flush=True)

class Fw:
    """Compiled firmware. A pump thread advances its clock with real time unless manual or suspended."""
    def __init__(self, pump=True):
        env = {**os.environ, "ASAN_OPTIONS": "detect_leaks=0"}
        self.p = subprocess.Popen([FW], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
        self.lock = threading.Lock(); self.inbox = queue.Queue(); self.state = None; self.frozen = False; self.alive = True
        self.t0 = time.monotonic(); self.done_ms = 0
        if pump:
            threading.Thread(target=self._pump, daemon=True).start()
    def cmd(self, line):
        with self.lock:
            if not self.alive:
                raise OSError("firmware gone")
            self.p.stdin.write(line + "\n"); self.p.stdin.flush()
            passed = None
            while True:
                l = self.p.stdout.readline()
                if not l:
                    self.alive = False
                    raise RuntimeError("firmware process died (sanitizer?)")
                if l.startswith("R "):
                    self.inbox.put(bytes.fromhex(l[2:].strip()))
                elif l.startswith("P "):
                    passed = int(l[2:])
                elif l.startswith("S "):
                    self.state = json.loads(l[2:]); self.state["pass"] = passed
                    return self.state
    def _pump(self):
        while self.alive:
            time.sleep(0.005)
            if self.frozen:
                continue
            want = int((time.monotonic() - self.t0) * 1000)
            n = want - self.done_ms
            if n > 0:
                self.done_ms = want
                try:
                    self.cmd(f"T {min(n, 500)}")
                except (OSError, RuntimeError, ValueError):
                    return
    def tap(self, key, ms=60):
        r, c = key // 3, key % 3
        self.cmd(f"K {r} {c} 1"); time.sleep(ms / 1000); return self.cmd(f"K {r} {c} 0")
    def hold(self, key, ms=480):
        return self.tap(key, ms)
    def kill(self):
        self.alive = False
        try:
            self.p.stdin.close()
        except OSError:
            pass
        self.p.wait()

class Wire:
    """The USB cable. Exactly 32-byte reports; unplug makes both directions raise like hidapi does."""
    def __init__(self, fw=None):
        self.fw = fw; self.stall_until = 0.0; self.sleeping = False; self.writes = []; self.hold_rx_until = 0.0
    def opener(self):
        return ShimTransport(self) if self.fw is not None else None

class ShimTransport:
    def __init__(self, wire):
        self.w, self.fw = wire, wire.fw
    def _gate(self):
        while self.w.sleeping or time.monotonic() < self.w.stall_until:
            time.sleep(0.01)
        if self.w.fw is not self.fw:
            raise OSError("device unplugged")
    def write(self, report):
        assert len(report) == 32
        self._gate()
        self.w.writes.append(report)
        self.fw.cmd("H " + report.hex())
    def read(self, timeout_ms):
        self._gate()
        end = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < self.w.hold_rx_until:  # bytes sitting in a USB or hidapi buffer
            time.sleep(0.01)
        try:
            return self.fw.inbox.get(timeout=max(0.001, end - time.monotonic()))
        except queue.Empty:
            return None
    def close(self):
        pass

class FakeMac:
    """Answers the only commands actions.py may run. subprocess is never touched."""
    def __init__(self):
        self.front = "com.apple.Terminal"; self.tab = "/dev/ttys001"; self.tabs = {"/dev/ttys001", "/dev/ttys002", "/dev/ttys003"}
        self.calls = []; self.presses = []; self.raise_on_press = None; self.flip_after_check = False
    def __call__(self, args, **kw):
        self.calls.append(args)
        ok = lambda out="": subprocess.CompletedProcess(args, 0, out, "")
        if args[0] == "lsappinfo":
            return ok("ASN:0x0-0x1:\n") if args[1] == "front" else ok(f'"CFBundleIdentifier"="{self.front}"\n')
        if args[0] == "open":
            return ok()
        assert args[0] == "osascript", args
        script = args[2]
        if "key code" in script and len(args) == 6:
            bundle, tty, code = args[3:6]
            if self.raise_on_press:
                self.presses.append(("maybe", self.front, self.tab, int(code)))
                raise self.raise_on_press
            if self.flip_after_check:
                self.front = "com.apple.Safari"
            if self.front != bundle or self.tab != tty:
                return ok("refused\n")
            self.presses.append(("sent", self.front, self.tab, int(code)))
            return ok("sent\n")
        if "selected of t to true" in script or "select s" in script:
            if args[3] in self.tabs:
                self.tab = args[3]; self.front = "com.apple.Terminal"
                return ok("ok\n")
            return ok("notfound\n")
        return ok(self.tab + "\n")  # READ_TTY

class Rig:
    def __init__(self, wire, mac=None, name="s", clock_mod=None, **board_kw):
        self.wire, self.mac = wire, mac or FakeMac()
        self.sock = Path(f"{name}{os.getpid()%1000}.sock")
        self.board = Board(**board_kw)
        self.actions = A.Actions(dry_run=False, runner=self.mac, out=lambda s: None)
        self.link = None
        clock = (lambda: time.monotonic() - clock_mod.slept) if clock_mod else time.monotonic
        self.d = DM.Daemon(self.board, self.actions, send=lambda m: self.link.send(m), clock=clock, watcher_opts={})
        self.link = D.DeviceLink(wire.opener, self.d.on_device, keepalive=self.d.keepalive, retry_interval=0.2)
        self.d.connected = self.link.connected.is_set
        self.srv = DM.SocketServer(self.sock, self.d); self.srv.start()
        self.link.start()
        self.th = threading.Thread(target=self.d.run, daemon=True); self.th.start()
    def hook(self, event, sid, tty=None, bundle="com.apple.Terminal", cwd=None, **kw):
        payload = {"hook_event_name": event, "session_id": sid, "cwd": cwd or f"/tmp/{sid}",
                   "transcript_path": f"/tmp/{sid}.jsonl", **kw}
        stub = f"import frostbite_host.hook as h; h.controlling_tty=lambda:{tty or ''!r}; h.main()"
        env = {k: v for k, v in os.environ.items() if k not in ("TERM_PROGRAM", "ITERM_SESSION_ID", "__CFBundleIdentifier")}
        env.update(__CFBundleIdentifier=bundle, FROSTBITE_SOCKET=str(self.sock), PYTHONPATH=HOST, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, "-c", stub], input=json.dumps(payload), text=True, capture_output=True, env=env, timeout=5)
        assert r.returncode == 0 and r.stdout == "", (r.returncode, r.stdout, r.stderr)
        time.sleep(0.05)
    def status(self):
        return ipc.send({"op": "status"}, timeout=2.0, want_reply=True, path=self.sock)
    def stop(self):
        self.d.stop_event.set(); self.th.join(2); self.link.stop(); self.srv.stop()

def bash(c):
    return {"tool_name": "Bash", "tool_input": {"command": c}}
def settle(s=0.35):
    time.sleep(s)
def wait_for(pred, timeout=6.0):
    t = time.monotonic()
    while time.monotonic() - t < timeout:
        v = pred()
        if v:
            return time.monotonic() - t
        time.sleep(0.02)
    return None
def show(fw):
    s = fw.state
    print(f"    panel |{s['p0']}|\n          |{s['p1']}|\n          |{s['p3']}| hm={s['hm']} oled={s['oled']} asleep={s['asleep']} st={s['st']} sel={s['sel']} glow={s['glow']}")

SC = {}
def scenario(f):
    SC[f.__name__] = f
    return f

@scenario
def s1_daemon_before_plugin():
    w = Wire(); r = Rig(w)
    r.hook("SessionStart", "a", tty="/dev/ttys001"); r.hook("UserPromptSubmit", "a", prompt="fix the build", tty="/dev/ttys001")
    check("no pad: daemon up, connected false", r.status()["connected"] is False)
    fw = Fw(); w.fw = fw
    dt = wait_for(lambda: fw.cmd("W")["p3"].startswith("1R") and fw.state["hm"])
    show(fw)
    check("plug-in after daemon: full state reaches the panel", dt is not None and "RUN" in fw.state["p0"] and "fix the build" in fw.state["p1"], f"{dt}")
    r.stop(); fw.kill()

@scenario
def s2_daemon_after_plugin():
    fw = Fw(); w = Wire(fw); settle(1.0)
    print("    before daemon:", fw.cmd("W")["p0"], fw.state["hm"])
    r = Rig(w)
    dt = wait_for(lambda: "empty" in fw.cmd("W")["p0"] and fw.state["p3"].endswith("HID"))
    show(fw)
    check("daemon after pad: host mode, panel says no agents", dt is not None and "empty" in fw.state["p0"] and "no agents" in fw.state["p1"], f"{dt}")
    r.stop(); fw.kill()

@scenario
def s3_unplug_mid_run():
    fw = Fw(); w = Wire(fw); r = Rig(w)
    wait_for(lambda: r.link.connected.is_set())
    r.hook("UserPromptSubmit", "a", prompt="go", tty="/dev/ttys001"); settle()
    old, w.fw = fw, None
    check("unplug detected", wait_for(lambda: not r.link.connected.is_set(), 2) is not None)
    r.hook("PermissionRequest", "a", tty="/dev/ttys001", **bash("npm test")); old.kill()
    fw = Fw(); w.fw = fw
    dt = wait_for(lambda: fw.cmd("W")["p3"].startswith("1?"))
    show(fw)
    check("replug: fresh firmware gets the state that changed while out", dt is not None and "WAIT" in fw.state["p0"] and "npm test" in fw.state["p1"] and fw.state["glow"][:3] == [255, 176, 32], f"{dt}")
    r.stop(); fw.kill()

@scenario
def s4_ping_gaps():
    for gap in (5.6, 7.2):
        fw = Fw(); w = Wire(fw); r = Rig(w)
        wait_for(lambda: r.link.connected.is_set())
        r.hook("PermissionRequest", "a", tty="/dev/ttys001", **bash("npm test")); settle()
        conn = []
        orig = r.d.on_device
        w.stall_until = time.monotonic() + gap
        dt = wait_for(lambda: not fw.cmd("W")["hm"], gap)
        settle(0.15); fw.cmd("W")  # the driver sends one block per loop, so let the render drain
        print(f"    gap {gap}: pad fell back after {dt}"); show(fw)
        check(f"gap {gap}: KBD screen, stored status kept", fw.state["p3"].endswith("KBD") and fw.state["st"][0] == 3)
        dt2 = wait_for(lambda: fw.cmd("W")["hm"] and fw.state["p3"].startswith("1?"), 6)
        show(fw)
        check(f"gap {gap}: recovers to WAIT with text", dt2 is not None and "WAIT" in fw.state["p0"], f"{dt2}")
        r.stop(); fw.kill()

@scenario
def s5_seven_sessions():
    fw = Fw(); w = Wire(fw); r = Rig(w)
    wait_for(lambda: r.link.connected.is_set())
    for i in range(6):
        r.hook("UserPromptSubmit", f"s{i}", prompt=f"job {i}", tty=f"/dev/ttys{i+10:03d}")
    settle()
    r.hook("SessionStart", "seven", tty="/dev/ttys020"); r.hook("UserPromptSubmit", "seven", prompt="job 7", tty="/dev/ttys020")
    check("7th running session has no slot", all(s and s["key"] != "claude:seven" for s in r.status()["slots"]))
    r.hook("PermissionRequest", "seven", tty="/dev/ttys020", **bash("rm x")); settle()
    fw.cmd("W"); show(fw)
    check("7th needs: glow amber, flash", fw.state["glow"][:3] == [255, 176, 32] and "agent waiting" in fw.state["p1"], f"text is {len('agent waiting, no slot')} chars, panel has 21: {fw.state['p1']!r}")
    print("    overflow:", list(r.board.overflow))
    r.hook("PostToolUse", "seven", **bash("rm x")); r.hook("Stop", "seven", last_assistant_message="ok"); settle(3.3)
    fw.cmd("W"); show(fw)
    check("7th answered and stopped: amber gone", fw.state["glow"][:3] != [255, 176, 32], f"overflow={list(r.board.overflow)}")
    r.hook("Stop", "s1"); r.hook("SessionEnd", "s1", reason="other"); settle()
    r.hook("PermissionRequest", "seven", tty="/dev/ttys020", **bash("rm y")); settle()
    st = r.status()["slots"]
    check("freed slot: 7th appears on its next event", any(s and s["key"] == "claude:seven" and s["status"] == "needs" for s in st))
    r.stop(); fw.kill()

@scenario
def s6_restart_existing_sessions():
    fw = Fw(); w = Wire(fw); r = Rig(w, name="a")
    wait_for(lambda: r.link.connected.is_set())
    r.hook("SessionStart", "a", tty="/dev/ttys001"); r.hook("UserPromptSubmit", "a", prompt="go", tty="/dev/ttys001")
    r.hook("PermissionRequest", "a", tty="/dev/ttys001", **bash("npm test")); settle()
    mac = r.mac; r.stop()
    r = Rig(w, mac, name="b")
    wait_for(lambda: r.link.connected.is_set()); settle(0.5)
    fw.cmd("W"); show(fw)
    check("restart with a dialog on screen: pad still amber", fw.state["st"][0] == 3, "board forgot it, no hook re-announces an open dialog")
    r.hook("PostToolUse", "a", **bash("npm test")); r.hook("PreToolUse", "a", **bash("sleep 5")); settle()
    slot = r.status()["slots"][0]
    print("    slot after restart:", slot["status"], slot["terminal"])
    fw.tap(8); settle(0.5); fw.cmd("W"); show(fw)
    check("restart: Stop works on a running pre-restart session", any(p[3] == 53 for p in r.mac.presses), f"presses={r.mac.presses} oled={fw.state['p1']!r}")
    r.stop(); fw.kill()

@scenario
def s7_sleep_wake():
    clk = types.SimpleNamespace(slept=0.0)
    real = time.monotonic
    fake_time = types.SimpleNamespace(monotonic=lambda: real() - clk.slept)
    D.time = fake_time  # mach_absolute_time stops in sleep, so the link sees no time pass
    try:
        fw = Fw(); w = Wire(fw); r = Rig(w, clock_mod=clk)
        wait_for(lambda: r.link.connected.is_set())
        r.hook("PermissionRequest", "a", tty="/dev/ttys001", **bash("npm test")); settle()
        for ms, label in ((300000, "5 min"), (3600000, "60 min")):
            w.sleeping = True; fw.frozen = True; t = real(); time.sleep(0.2)
            s = fw.cmd(f"Z {ms}"); print(f"    in suspend ({label}): oled={s['oled']} hm={s['hm']}")
            clk.slept += real() - t; fw.t0 -= 0  # pump keeps its own real-time base
            fw.t0 = real() - fw.done_ms / 1000
            fw.frozen = False; w.sleeping = False
            s = fw.cmd("T 20"); print(f"    20 ms after resume: hm={s['hm']} p3={s['p3']}")
            dt = wait_for(lambda: fw.cmd("W")["hm"], 4)
            settle(0.3); fw.cmd("W"); show(fw)
            check(f"{label} sleep: host mode back", dt is not None, f"{dt}")
            check(f"{label} sleep: OLED lit after wake", fw.state["oled"] == 1, f"asleep={fw.state['asleep']} st={fw.state['st']}")
        before = r.status()["slots"][0]["updated"]
        print("    daemon age of the slot after 65 min slept:", round(r.d.clock() - before, 1), "s")
        r.stop(); fw.kill()
    finally:
        D.time = time

@scenario
def s8_approve_flow():
    fw = Fw(); w = Wire(fw); r = Rig(w)
    wait_for(lambda: r.link.connected.is_set())
    r.hook("SessionStart", "a", tty="/dev/ttys001"); r.hook("SessionStart", "b", tty="/dev/ttys002")
    r.hook("PermissionRequest", "a", tty="/dev/ttys001", **bash("rm -rf build"))
    r.hook("PermissionRequest", "b", tty="/dev/ttys002", **bash("git push -f")); settle()
    r.mac.tab = "/dev/ttys002"
    fw.tap(6); settle(0.6); fw.cmd("W"); show(fw)
    check("wrong tab: no key, tap slot first", not r.mac.presses and "tap slot first" in fw.state["p1"])
    fw.tap(0); settle(0.4)
    check("agent tap focuses the tab", r.mac.tab == "/dev/ttys001")
    fw.tap(6); settle(0.6); fw.cmd("W"); show(fw)
    check("right tab: Return to ttys001 only", r.mac.presses == [("sent", "com.apple.Terminal", "/dev/ttys001", 36)], str(r.mac.presses))
    check("slot moves to RUN and panel says approved", "RUN" in fw.state["p0"] and "approved" in fw.state["p1"])
    fw.tap(6); settle(0.6)
    check("second tap: one-shot, no second key", len(r.mac.presses) == 1)
    r.mac.flip_after_check = True; fw.cmd("E 1"); settle(0.4); time.sleep(1.1)
    r.mac.tab = "/dev/ttys002"; fw.tap(6); settle(0.6); fw.cmd("W"); show(fw)
    check("focus moved inside the press script: reported refused", len(r.mac.presses) == 1 and "tap slot first" in fw.state["p1"])
    r.stop(); fw.kill()

@scenario
def s9_stale_prompt_keystroke():
    fw = Fw(); w = Wire(fw); r = Rig(w)
    wait_for(lambda: r.link.connected.is_set())
    r.hook("SessionStart", "dead", tty="/dev/ttys001")
    r.hook("PermissionRequest", "dead", tty="/dev/ttys001", **bash("npm test")); settle()
    print("    Claude crashed or was closed, no SessionEnd; ttys001 now holds a shell with a half-typed line")
    r.mac.tab = "/dev/ttys001"
    fw.tap(6); settle(0.6); fw.cmd("W"); show(fw)
    check("no live dialog: no key reaches the tab", not r.mac.presses, str(r.mac.presses))
    r.stop(); fw.kill()

@scenario
def s10_second_dialog_after_terminal_answer():
    fw = Fw(); w = Wire(fw); r = Rig(w)
    wait_for(lambda: r.link.connected.is_set())
    r.hook("SessionStart", "a", tty="/dev/ttys001")
    r.hook("PermissionRequest", "a", tty="/dev/ttys001", **bash("npm test"))
    r.hook("PermissionRequest", "a", tty="/dev/ttys001", **bash("rm -rf ~/data")); settle()
    fw.cmd("W"); show(fw)
    print("    user answers 'npm test' in the terminal; the tool runs for minutes, no hook fires; 'rm -rf ~/data' is now on screen")
    fw.tap(6); settle(0.6); fw.cmd("W"); show(fw)
    shown_before = "npm test"
    check("pad never approves a dialog other than the one on the OLED", not r.mac.presses, f"OLED said {shown_before!r}, screen had rm -rf, presses={r.mac.presses}")
    r.stop(); fw.kill()

@scenario
def s11_timeout_retry():
    fw = Fw(); w = Wire(fw); r = Rig(w)
    wait_for(lambda: r.link.connected.is_set())
    r.hook("SessionStart", "a", tty="/dev/ttys001")
    r.hook("PermissionRequest", "a", tty="/dev/ttys001", **bash("npm test")); settle()
    r.mac.raise_on_press = subprocess.TimeoutExpired("osascript", 3.0)
    fw.tap(6); settle(0.3); fw.tap(6); settle(0.6); fw.cmd("W"); show(fw)
    # The fake raises at once. A real timeout blocks 3 s, so this shows only that a timeout is treated as "not sent".
    check("a press whose outcome is unknown does not leave the prompt armed", len(r.mac.presses) == 1, f"{len(r.mac.presses)} attempts, oled={fw.state['p1']!r}")
    r.stop(); fw.kill()

@scenario
def s12_tmux_message():
    fw = Fw(); w = Wire(fw); r = Rig(w)
    wait_for(lambda: r.link.connected.is_set())
    r.hook("SessionStart", "a", tty="/dev/ttys050")  # tmux pane pty; the Terminal tab holds the tmux client's tty
    r.hook("PermissionRequest", "a", tty="/dev/ttys050", **bash("ls")); settle()
    r.mac.tab = "/dev/ttys001"
    fw.tap(6); settle(0.6); fw.cmd("W"); show(fw)
    check("tmux: no key", not r.mac.presses)
    check("tmux: README's 'answer in terminal', not 'tap slot first'", "answer in terminal" in fw.state["p1"], fw.state["p1"])
    fw.tap(0); settle(0.4); fw.tap(6); settle(0.6); fw.cmd("W")
    print("    after tapping the slot as told:", repr(fw.state["p1"]), "tab", r.mac.tab)
    r.stop(); fw.kill()

@scenario
def s13_buffered_key():
    fw = Fw(); w = Wire(fw); r = Rig(w)
    wait_for(lambda: r.link.connected.is_set())
    r.hook("SessionStart", "a", tty="/dev/ttys001")
    r.hook("PermissionRequest", "a", tty="/dev/ttys001", **bash("npm test")); settle()
    w.hold_rx_until = time.monotonic() + 3.0  # daemon's I/O thread late by 3 s
    fw.tap(6); t = time.monotonic()
    wait_for(lambda: r.mac.presses, 5)
    late = time.monotonic() - t
    check("a press older than MAX_KEY_AGE (1 s) is dropped", not r.mac.presses, f"pressed {late:.1f} s after the key")
    r.stop(); fw.kill()

@scenario
def s14_fallback_keys():
    fw = Fw(pump=False)
    fw.cmd("H 05" + "00" * 31); fw.cmd("T 100")
    # Talk across each transition
    s = fw.cmd("K 2 1 1"); a = s["pass"]; fw.cmd("T 5100"); s = fw.cmd("K 2 1 0")
    check("Talk host->fallback: F20 down then up", a == 1 and s["pass"] == 1 and s["down"] == 0)
    s = fw.cmd("K 2 1 1"); a = s["pass"]; fw.cmd("H 05" + "00" * 31); fw.cmd("T 100"); s = fw.cmd("K 2 1 0")
    check("Talk fallback->host: F20 down then up", a == 1 and s["pass"] == 1 and s["down"] == 0)
    fw.cmd("H 05" + "00" * 31); fw.cmd("T 5100")
    s = fw.cmd("K 2 2 1"); a = s["pass"]; fw.cmd("H 05" + "00" * 31); fw.cmd("T 100"); s = fw.cmd("K 2 2 0")
    check("Escape pressed in fallback, released in host: not stuck", a == 1 and s["pass"] == 1 and s["down"] == 0)
    fw.cmd("H 05" + "00" * 31); fw.cmd("T 100")
    s = fw.cmd("K 2 2 1"); a = s["pass"]; fw.cmd("T 5100"); s = fw.cmd("K 2 2 0")
    check("Stop pressed in host, released in fallback: no Escape at all", a == 0 and s["pass"] == 0 and s["down"] == 0 and s["stray"] == 0)
    fw.cmd("T 10")
    s = fw.cmd("K 2 2 1")
    check("host gone >5 s: Stop is never a raw Escape", s["pass"] == 0, f"pass={s['pass']} (1 means KC_ESC goes to the frontmost app)")
    fw.cmd("K 2 2 0"); fw.kill()

def main():
    names = sys.argv[3:] or list(SC)
    logging.disable(logging.CRITICAL)
    for n in names:
        print(f"== {n}", flush=True)
        try:
            SC[n]()
        except Exception as e:  # noqa: BLE001
            check(n + " completed", False, repr(e))
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(bad)} pass, {len(bad)} fail")
    for n in bad:
        print("  fail:", n)

main()
