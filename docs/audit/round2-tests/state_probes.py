#!/usr/bin/env python3
"""State-level probes with injected clocks and the real Board, Daemon and TrainWatcher. Nothing is pressed.
Usage (from host/): uv run --frozen python ../docs/audit/round2-tests/state_probes.py <scratch>"""
import logging, os, subprocess, sys, tempfile, time
from frostbite_host import actions as A, daemon as DM, device as D, hook as H, train as T
from frostbite_host.state import Board
logging.disable(logging.CRITICAL)
os.chdir(tempfile.mkdtemp(dir=sys.argv[1]))
TERM = {"bundle": "com.apple.Terminal", "tty": "/dev/ttys001"}
HOUR = 3600.0

class Clock:
    t = 1000.0
    def __call__(self):
        return self.t
class Mac:
    def __init__(self): self.presses = []
    def __call__(self, a, **k):
        ok = lambda o="": subprocess.CompletedProcess(a, 0, o, "")
        if a[0] == "lsappinfo":
            return ok("ASN:0x0-0x1:\n") if a[1] == "front" else ok('"CFBundleIdentifier"="com.apple.Terminal"\n')
        if a[0] == "osascript" and len(a) == 6:
            self.presses.append(int(a[5])); return ok("sent\n")
        return ok("/dev/ttys001\n")
def rig():
    clk, mac, sent = Clock(), Mac(), []
    d = DM.Daemon(Board(), A.Actions(runner=mac, out=lambda s: None), send=sent.append, clock=clk)
    return d, clk, mac
def m(key="claude:a", **kw):
    return {"op": "update", "source": "claude", "key": key, "name": key, **kw}
def say(*a):
    print(*a, flush=True)

say("== long tool call and the 1 h rule")
d, clk, mac = rig(); b = d.board
b.apply(m(status="run", detail="Bash(python train.py)", tool="Bash(python train.py)", terminal=TERM), clk())
clk.t += HOUR + 1; d.tick()
s = b.slots[0]; say("after 1 h 1 s in one tool call:", s.status.name, repr(s.detail))
d._stop(clk()); say("pad Stop:", repr(b.oled_lines(clk())[1]), "presses", mac.presses)
for i in range(1, 6):
    b.apply(m(f"claude:s{i}", status="run", detail="x"), clk())
b.apply(m("claude:new", register_only=True), clk())
say("6 busy, a NEW idle session arrives; slot 1 is now:", b.slots[0].key, "| long-running session still shown:", b.find("claude:a") is not None)
b.apply(m(status="run", resolve={"tool": "Bash(python train.py)", "agent": ""}), clk())
say("its PostToolUse after eviction: slot", b.find("claude:a"))

say("== interrupt in the terminal: no hook, Stop does not fire")
d, clk, mac = rig(); b = d.board
b.apply(m(status="run", detail="working", terminal=TERM), clk())
clk.t += 59 * 60; d.tick(); say("59 min after a real Esc:", b.slots[0].status.name)

say("== background subagent tool after Stop")
d, clk, mac = rig(); b = d.board
b.apply(m(status="done", detail="finished", clears=True), clk())
b.apply(m(status="run", detail="Read(x)", tool="Read(x)", agent="bg1"), clk())
say("slot after main Stop then a background agent's PreToolUse:", b.slots[0].status.name, "(no further Stop for the main turn)")

say("== NEEDS lifetime")
d, clk, mac = rig(); b = d.board
b.apply(m(status="needs", detail="Bash(x)?", tool="Bash(x)", terminal=TERM), clk())
clk.t += 23.9 * HOUR; d.tick(); s = b.slots[0]
say("needs after 23.9 h with no event:", s.status.name if s else None, "glow", b.glow())
d._approve(False, clk()); s = b.slots[0]
say("Approve on it: presses", mac.presses, "status", s.status.name, repr(s.detail))
clk.t += 59 * 60; d.tick(); say("59 min later that false RUN is still:", b.slots[0].status.name)

say("== a second session on the tty frees the first, whatever it was doing")
d, clk, mac = rig(); b = d.board
b.apply(m(status="needs", detail="Bash(rm)?", tool="Bash(rm)", terminal=TERM), clk())
b.apply(m("claude:child", register_only=True, terminal=TERM), clk())
say("slots:", [(s.key, s.status.name) for s in b.slots if s])

say("== resume elsewhere with a failed tty lookup keeps the OLD tty")
d, clk, mac = rig(); b = d.board
b.apply(m(status="run", terminal=TERM), clk())
b.apply(m(status="run", terminal={"bundle": "com.apple.Terminal"}), clk())
say("terminal after resume with no tty:", b.slots[0].terminal)

say("== stale training logs")
class Em:
    def __init__(self, d): self.d = d
    def __call__(self, msg): self.d.handle(("ipc", msg, None))
def watcher(path, clk, d, **kw):
    return T.TrainWatcher(path, "run", Em(d), clock=clk, **kw)
LOG = "train.log"
open(LOG, "w").write("epoch 1 step 10 loss 0.5\n`Trainer.fit` stopped: `max_epochs=10` reached.\n")
for line in ("`Trainer.fit` stopped: `max_epochs=10` reached.", "Epoch 10/10 - loss: 0.01", "100%|##########| 500/500 [10:00<00:00]",
             "Training completed. Do not forget to share your model", "wandb: Run summary:", "Training complete", "Saved model to out/final.pt"):
    i = T.parse_line(line); say(f"  done={i.done!s:<5} {line}")
d, clk, mac = rig(); b = d.board
w = watcher(LOG, clk, d); w.poll_once()
say("finished run, fresh start:", b.slots[0].status.name)
clk.t += 601; w.poll_once(); d.tick(); s = b.slots[0]
say("after 10 min:", s.status.name, repr(s.detail), "glow", b.glow())
b.selected = 0; d._approve(False, clk()); say("Approve:", repr(b.oled_lines(clk())[1]))
d._stop(clk()); say("Stop:", repr(b.oled_lines(clk())[1]))
clk.t += 23.5 * HOUR; w.poll_once(); d.tick(); say("23.5 h later:", b.slots[0].status.name if b.slots[0] else None)
clk.t += 1 * HOUR; w.poll_once(); d.tick(); say("24.5 h later:", b.slots[0].status.name if b.slots[0] else None, "glow", b.glow())
d2, clk2, _ = rig(); os.utime(LOG, (time.time() - 30 * 86400, time.time() - 30 * 86400))
w2 = watcher(LOG, clk2, d2); w2.poll_once()
say("daemon restart on a 30-day-old log:", d2.board.slots[0].status.name, repr(d2.board.slots[0].detail))
clk2.t += 601; w2.poll_once(); d2.tick(); say("  10 min later:", d2.board.slots[0].status.name)

say("== legitimately quiet stretch")
d, clk, mac = rig(); open(LOG, "w").write("step 1 loss 0.5\n"); w = watcher(LOG, clk, d); w.poll_once()
clk.t += 601; w.poll_once(); d.tick(); say("15 min eval pass, nothing logged:", d.board.slots[0].status.name, repr(d.board.slots[0].detail))
open(LOG, "a").write("step 2 loss 0.4\n"); clk.t += 1; w.poll_once(); d.tick(); say("lines resume:", d.board.slots[0].status.name)

say("== growing log with no metrics, 24 h rule")
d, clk, mac = rig(); open(LOG, "w").write("working on shard 1\n"); w = watcher(LOG, clk, d); w.poll_once()
for h in range(1, 26):
    open(LOG, "a").write(f"working on shard {h}\n"); clk.t += HOUR; w.poll_once(); d.tick()
    if h in (23, 24, 25):
        s = d.board.slots[0]; say(f"hour {h}, log still growing:", s.status.name if s else "SLOT GONE")
d, clk, mac = rig(); say("== ctl slot"); d.board.apply({"op": "set_slot", "slot": 2, "status": "run", "name": "CI"}, clk()); clk.t += 24 * HOUR; d.tick(); say("ctl run after 24 h:", d.board.slots[2])

say("== OLED text fits")
say("flash texts over 21:", [t for t in ("agent waiting, no slot", A.TAP_FIRST, A.USE_TERMINAL, "keystroke failed", "nothing to approve", "nothing to stop", "tab not found") if len(t) > 21])

say("== hooks snippet")
from frostbite_host import ctl
import json
ex = json.load(open(os.path.join(os.path.dirname(H.__file__), "..", "examples", "claude-hooks.json")))
say("examples == ctl output:", ex == ctl.hooks_snippet("/ABSOLUTE/PATH/TO/frostbite-hook"))
say("spaced path command:", ctl.hooks_snippet("/Users/a b/frostbite-hook")["hooks"]["Stop"][0]["hooks"][0]["command"])

say("== frontmost() with the real lsappinfo (read-only)")
say(repr(A.Actions(dry_run=True, out=lambda s: None).frontmost()))

say("== sessions that can never be proved, and questions")
for bundle, tty in (("com.microsoft.VSCode", "/dev/ttys001"), ("com.mitchellh.ghostty", "/dev/ttys001"), ("com.github.wez.wezterm", "/dev/ttys001"),
                    ("", "/dev/ttys001"), ("com.apple.Terminal", ""), ("com.apple.Terminal", "ttys001"), ("com.apple.Terminal", "/dev/console")):
    d, clk, mac = rig(); b = d.board
    b.apply(m(status="needs", detail="Bash(x)?", tool="Bash(x)", terminal={"bundle": bundle, "tty": tty}), clk())
    d._approve(False, clk()); say(f"{bundle or '(none)':<26} tty={tty or '(none)':<14} presses={mac.presses} oled={b.oled_lines(clk())[1].strip()!r}")
d, clk, mac = rig(); b = d.board
b.apply(m(status="needs", detail="question?", tool="AskUserQuestion", kind="question", terminal=TERM), clk())
d._approve(False, clk()); say("question dialog: presses", mac.presses, repr(b.oled_lines(clk())[1].strip()))
