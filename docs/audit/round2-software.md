# Frostbite round 2 software audit

Audited 2026-11-03 on this Mac (Darwin 25.6.0, arm64, Python 3.12.16, hidapi 0.15.0, Claude Code 2.1.316 binary on disk).
No pad was plugged in, no key was sent, and no hook, LaunchAgent or Claude Code setting was installed or changed.

| Severity | Confirmed | Likely | Unverified | Total |
|---|---:|---:|---:|---:|
| BLOCKER | 1 | 0 | 0 | 1 |
| MAJOR | 3 | 1 | 0 | 4 |
| MINOR | 10 | 4 | 2 | 16 |
| Total | 14 | 5 | 2 | 21 |

The answers to the brief's questions:

- **Can a keystroke still reach the wrong place?** Yes. The K-01 fix proves the tab, not the dialog. A stale amber slot sends a real Return into whatever is in that tab, then reports `approved` (R2-01). Approve can answer a different dialog from the one on the OLED (R2-02). In fallback, Stop is a raw Escape to the frontmost app (R2-03).
- **Does the check-then-press race remain?** Yes, narrower. Nothing holds focus between the last check and the key (R2-10).
- **Does anything report `sent` when nothing was?** The code path does not: it needs the script's own `sent`. The state is still wrong in one way: R2-01 reports `approved` when no prompt existed. Secure Keyboard Entry is an open question (R2-21).
- **Is pad Approve effectively never going to work?** No, but it has never been seen working. `/dev/tty` always fails in a real hook. The `ps` fallback gets the right tty, but only because the shell execs a plain path (R2-05).
- **Stale log amber forever?** Not forever. It lasts 24 awake hours and comes back on every daemon restart. The pad cannot clear it (R2-04).
- **1 h rule against long work?** A real mislabel, but rare. Foreground Bash is capped at 10 minutes by default (R2-13).
- **Hooks?** Documented event names, and no meaningful delay. A verified pass.

## How this was tested

**Kit.** Everything is in `docs/audit/round2-tests/`:

| File | What it does |
|---|---|
| `build.sh`, `fw_e2e.c` | Wraps the unmodified `Firmware/tests/harness.c`: real `keymap.c`, real QMK OLED driver, SSD1306 GDDRAM model, ASan and UBSan. Adds panel text, LED values, display power, the keycodes that reach USB, and USB suspend |
| `e2e.py` | Real `Daemon`, `DeviceLink`, `SocketServer` and `frostbite-hook` processes against that binary over a 32-byte shim. Firmware time follows real time |
| `state_probes.py` | Real `Board`, `Daemon` and `TrainWatcher` with an injected clock |
| `tty_probe.py` | Runs the real `controlling_tty()` in the process shape Claude Code uses, under a real pty |
| `hook_latency.py` | Times the real hook with the daemon absent, healthy and wedged |
| `e2e.out`, `state_probes.out` | Final run output, quoted below |

```sh
S=<a scratch dir>; docs/audit/round2-tests/build.sh $S/fw
cd host && uv run --frozen python ../docs/audit/round2-tests/e2e.py $S/fw/fw_e2e $S     # 26 pass, 10 fail
uv run --frozen python ../docs/audit/round2-tests/state_probes.py $S
uv run --frozen python ../docs/audit/round2-tests/tty_probe.py
uv run --frozen python ../docs/audit/round2-tests/hook_latency.py $S
```

Each `FAIL` in `e2e.py` asserts the safe behaviour, so a fix turns it into a pass. All 10 map to findings here. Three other first-run failures were my own test faults (a wait that returned early, a panel read mid-render, and an over-strict text match) and are fixed in the kit. The text match did expose the truncation in R2-09.

**Fake parts.** `FakeMac` answers `lsappinfo` and `osascript` and records presses without running anything. The hook's tty is stubbed in `e2e.py`, and `tty_probe.py` covers the real lookup. Sleep is simulated: the wire freezes, the firmware jumps ahead, and the host clock does not advance.

**Not tested.**

- A real pad, real hidapi I/O, or real sleep and wake.
- A real Claude Code session driving these hooks, because the brief forbids installing hooks.
- Real AppleScript execution. The Terminal scripts were compiled with `osacompile` only (rc 0).
- The iTerm2 scripts. iTerm2 is not installed here, so they were not even compiled.

**Baselines, all green, which is why they missed everything below.** `host` pytest: `188 passed`. `Firmware/tests/run.sh`: `fails=0`. `proto_test.py`: `ok 23 bad 0`.

**Docs used.** https://code.claude.com/docs/en/hooks and https://code.claude.com/docs/en/env-vars (fetched), `man clock_gettime` (local), Apple TN2150 (fetched).

---

## BLOCKER

### R2-01. BLOCKER, CONFIRMED: the proof covers the tab, not the dialog, so a stale `needs` sends Return into whatever is there

`guarded_key` (`actions.py:170-205`) proves that the slot's tty is the focused tab. It does not prove that Claude Code is still running there, or that any dialog is open. `_approve` trusts `slot.status == NEEDS` (`daemon.py`, `_approve`), and that status can be long stale:

- `expire` never ages out `needs` before 24 hours (`state.py:283-287`; only `run` has a quiet rule).
- The README itself says a prompt denied in the terminal stays amber until the next message or Stop (the paragraph under the hook table).
- `README.md:55` says a crash or closed window sends no event.

Real firmware, real daemon, session gone, shell in the same tab:

```
== s9_stale_prompt_keystroke
    panel |claude#1 dead     RUN|
          |approved             |
          |1R 2- 3- 4- 5- 6- HID| ... glow=[159, 216, 255, 110]
  FAIL no live dialog: no key reaches the tab   [[('sent', 'com.apple.Terminal', '/dev/ttys001', 36)]]
```

`state_probes.out` shows the window and the false state afterwards:

```
needs after 23.9 h with no event: NEEDS glow (255, 176, 32, 160)
Approve on it: presses [36] status RUN 'approved'
59 min later that false RUN is still: RUN
```

Three ordinary routes reach this:

1. Deny in the terminal, then Approve. Return lands in Claude's input box and submits any draft.
2. Claude crashes, leaving a shell in the tab. Return runs a half-typed command.
3. The tab closes and macOS reuses the tty number for a new tab.

The pad then shows blue `approved` for up to an hour.

Tried to disprove it: no hook closes the prompt, `_drop_same_tty` needs a new Claude session on that tty, and the cooldown and one-shot guards only stop a repeat. The key itself was recorded, not sent. That Return runs a shell line or submits a draft is reasoning about terminals.

Fix options:

- Store Claude's pid from the hook and refuse if it is gone. This covers the dead-session routes only.
- Read the tab text inside the press script (`contents of selected tab`, or iTerm's `contents`) and require a permission dialog on screen, ideally naming the tool. This also fixes R2-02.

---

## MAJOR

### R2-02. MAJOR, CONFIRMED: Approve can answer a different dialog from the one on the OLED

No hook fires when a prompt is answered in the terminal, so `pending[0]` stays on the dialog already answered until its tool finishes. The next queued dialog is then on screen while the OLED still names the old one.

```
== s10_second_dialog_after_terminal_answer
    panel |claude#1 a       WAIT|
          |Bash(npm test)?      |
    user answers 'npm test' in the terminal; the tool runs for minutes, no hook fires; 'rm -rf ~/data' is now on screen
    panel |claude#1 a       WAIT|
          |approved             |
  FAIL pad never approves a dialog other than the one on the OLED   [OLED said 'npm test', screen had rm -rf, presses=[('sent', 'com.apple.Terminal', '/dev/ttys001', 36)]]
```

The tab must be in front, so the real dialog is visible, which limits this to MAJOR. That dialogs queue this way comes from the project's own `Prompt` comment (`state.py`) and was not observed in a real session. Same fix as R2-01.

### R2-03. MAJOR, CONFIRMED: in fallback, Stop is a raw Escape to the frontmost app, with no proof

`keymap.c:140` maps Stop to `KC_ESC`, and `keymap.c:228` passes it through when not in host mode. `design.json` documents this. But `README.md:115` says "Approve and Stop only ever reach the selected slot's own session", and the module rule in `actions.py` is fail closed.

```
== s14_fallback_keys
  FAIL host gone >5 s: Stop is never a raw Escape   [pass=1 (1 means KC_ESC goes to the frontmost app)]
```

It applies whenever the daemon is dead or stopped, and also after every host sleep until the first PING. Measured in `s7`, on both wakes, pad back in host mode after 1.6 s and 1.7 s. During that window the panel shows the KBD screen or, after a long sleep, is dark (R2-08). So a user reaching for Stop on slot 3 can interrupt whichever Claude session is focused, or cancel a dialog in any app.

Tried to disprove it: Escape does not stick across transitions (a verified pass), and F19 for Approve is harmless. Only Stop has this problem.

Fix: make fallback Stop an unassigned key such as F21, or correct the README and accept it.

### R2-04. MAJOR, CONFIRMED: an ordinary finished run stays amber for a day, and the pad cannot clear it

A run counts as finished only on a matched final line. Anything else goes quiet and becomes `needs` (`train.py:356-359`). Common final lines do not match:

```
  done=False `Trainer.fit` stopped: `max_epochs=10` reached.
  done=False Epoch 10/10 - loss: 0.01
  done=False 100%|##########| 500/500 [10:00<00:00]
  done=False Saved model to out/final.pt
```

```
after 10 min: NEEDS 'quiet 10m e1 s10 loss 0.5' glow (255, 176, 32, 160)
Approve: 'nothing to approve'
Stop: 'nothing to stop'
23.5 h later: NEEDS
24.5 h later: None glow (159, 216, 255, 50)
daemon restart on a 30-day-old log: RUN 'e1 s10 loss 0.5'
  10 min later: NEEDS
```

So it is bounded, not forever: 24 hours measured on a clock that stops in sleep (R2-17), which is several days for a laptop. But `_last_growth` starts at `clock()` (`train.py:316`) and ignores file mtime, so any restart replays it. A LaunchAgent with `--watch-train` and `KeepAlive` repeats it after every crash or login: a 30-day-old log shows `run`, then amber. During that time the glow is the same amber as a real Claude prompt, which hides real ones. `_claim` never evicts `needs`, so it also holds a slot.

The only clears are `frostbite-ctl clear N` or `unwatch` (from reading the code, not run). A 15-minute eval pass goes amber the same way and returns to `run` when lines resume. That is the documented trade-off and works as described.

Fix: seed `_last_growth` from mtime and treat an old file as ended; give stale runs a distinct look, not the `needs` glow; let Approve acknowledge a stale slot.

### R2-05. MAJOR, LIKELY: the tty proof rests on an undocumented shell optimisation and has never run against real Claude Code

The docs: "On macOS and Linux, command hooks run in their own session without a controlling terminal. The hook process and any child processes can't open `/dev/tty`". The 2.1.316 binary agrees: `XCe(uo,[],{env:un,cwd:rr,shell:_i,detached:Sr,...})` with `Sr=!Ot`, that is `spawn(cmd, {shell:true, detached:true})` on macOS.

So the first branch of `controlling_tty()` (`hook.py:92`) can never succeed. Everything depends on `ps -o tty= -p <ppid>` (`hook.py:102`), and that works only if the parent is Claude Code itself, which happens only when the shell execs the hook in place of forking. Real hook code under a real pty, in Claude's process shape:

```
REAL_TTY /dev/ttys001
/bin/sh  | plain path (shipped snippet) | ... "dev_tty": "ERR [Errno 6] Device not configured: '/dev/tty'", "controlling_tty": "/dev/ttys001"
/bin/sh  | path + redirect              | ... "controlling_tty": ""
/bin/sh  | trailing true                | ... "controlling_tty": ""
/bin/sh  | wrapped by uv run            | ... "controlling_tty": ""
/bin/bash| plain path (shipped snippet) | ... "controlling_tty": "/dev/ttys001"
/bin/zsh | plain path (shipped snippet) | ... "controlling_tty": "/dev/ttys001"
```

The shipped snippet is a plain path, so Approve should work in Terminal. That is why this is not a "never works" finding. It stays LIKELY because this reproduces the shape and was not seen in a real session.

The failure is safe but silent. Anything that adds a process makes every session show `answer in terminal` forever, with no log or diagnostic. Examples: a user's `2>/dev/null` or `; true`, a wrapper, or `CLAUDE_CODE_SHELL_PREFIX`, which the binary applies to hook commands (`uo=...vn?fge(vn,hn):hn`). The first three are tested above; the prefix case is from reading the binary.

Fix: walk up the parent chain until a process has a tty; remove the dead `/dev/tty` branch and its misleading comment; add a `frostbite-ctl doctor` that reports whether a tty was captured; test once in a real session.

---

## MINOR

### R2-06. MINOR, CONFIRMED: a daemon restart forgets a dialog that is on screen

No state is saved and no hook re-announces an open dialog. The session is waiting, but the pad says nothing is:

```
== s6_restart_existing_sessions
    panel |#1 empty             |
          |no agents            |
  FAIL restart with a dialog on screen: pad still amber   [board forgot it, no hook re-announces an open dialog]
```

### R2-07. MINOR, CONFIRMED: after a restart, a running session has no tty and shows the wrong message

Only some events carry the tty (`hook.py:145-173`). `PreToolUse` and `PostToolUse` do not, so a session rebuilt from those has none:

```
    slot after restart: run {'bundle': 'com.apple.Terminal'}
    panel |claude#1 a        RUN|
          |answer in terminal   |
  FAIL restart: Stop works on a running pre-restart session   [presses=[] oled='answer in terminal   ']
```

It fails closed and lasts until the next prompt. Capturing the tty on every event costs about 6 ms (see the verified passes).

### R2-08. MINOR, CONFIRMED: F9 is still open, so the OLED stays dark after a sleep over 10 minutes

There is no `suspend_wakeup_init_user`. On resume `keymap.c:454` latches `oled_asleep`, even with a prompt waiting:

```
    in suspend (60 min): oled=0 hm=0
    panel |claude#1 a       WAIT|
          |Bash(npm test)?      |
          |1? 2- 3- 4- 5- 6- HID| hm=1 oled=0 asleep=1 st=[3, 0, 0, 0, 0, 0] ...
  FAIL 60 min sleep: OLED lit after wake   [asleep=1 st=[3, 0, 0, 0, 0, 0]]
```

A 5-minute sleep is fine. Any key wakes it. `Firmware/tests/harness.c:135` prints this condition but does not assert it, so `fails=0` hides it. Fix: call `wake()` in `suspend_wakeup_init_user`.

### R2-09. MINOR, CONFIRMED: a seventh session keeps the glow amber after it is answered

`self.overflow[key]` is set only for `needs` (`state.py:381-382`) and is cleared only by getting a slot or by `free`. Later events from that session do not clear it:

```
  PASS 7th needs: glow amber, flash   [text is 22 chars, panel has 21: 'agent waiting, no slo']
  FAIL 7th answered and stopped: amber gone   [overflow=['claude:seven']]
```

It lasts up to `OVERFLOW_TTL`, 1 hour. Every event from that session re-flashes the false message (`daemon.py:130`), and the message is one character too long for the panel.

### R2-10. MINOR, CONFIRMED by reading: the check-then-press race remains, narrower

`_PRESS` reads the frontmost app, then the tty, then presses (`actions.py:104-108`), as three separate Apple Events with nothing holding focus. A focus change after line 107 sends Return to another app. The window is one Apple Event round trip, not measured here. The double check is a real improvement, and a move caught by the script is reported correctly (`s8` passes).

A stronger fix exists for iTerm2: write to the session object itself, so the key cannot reach another app. It needs testing, and Terminal.app has no equivalent for Escape.

### R2-11. MINOR, CONFIRMED: tmux shows `tap slot first`, and tapping never helps

The README (`README.md:127`) promises `answer in terminal` for tmux panes. A pane's tty never equals the Terminal tab's tty, so the code takes the `TAP_FIRST` branch forever. It is safe, but the instruction is wrong:

```
  PASS tmux: no key
  FAIL tmux: README's 'answer in terminal', not 'tap slot first'   [tap slot first       ]
    after tapping the slot as told: 'tap slot first       ' tab /dev/ttys001
```

### R2-12. MINOR, LIKELY: `MAX_KEY_AGE` counts from the read, not the press

`on_device` stamps the time when the report is dequeued (`daemon.py:54`, checked at `:174`). A report that sat in a buffer looks new:

```
  FAIL a press older than MAX_KEY_AGE (1 s) is dropped   [pressed 2.9 s after the key]
```

Shown with a delayed read in the shim. A real I/O stall under 5 s should do the same, which is why this is LIKELY. The tty proof still runs at action time.

### R2-13. MINOR, CONFIRMED: a tool call silent for over 1 hour goes idle, can't be stopped from the pad, and can be evicted

```
after 1 h 1 s in one tool call: IDLE 'quiet 1h00'
pad Stop: 'nothing to stop' presses []
6 busy, a NEW idle session arrives; slot 1 is now: claude:new | long-running session still shown: False
its PostToolUse after eviction: slot 0
```

This contradicts the README line that running slots are never pushed out. It recovers at `PostToolUse`. Reach is small: foreground Bash has a default ceiling of 10 minutes (`BASH_MAX_TIMEOUT_MS`, default 600000, env-vars doc), so this needs a raised limit or a long MCP tool. Fix: keep a slot in `run` while a `PreToolUse` has no matching `PostToolUse`, and say `quiet` without leaving `run`.

### R2-14. MINOR, CONFIRMED: Esc in the terminal leaves the slot blue for up to an hour

Docs for Stop: "Does not run if the stoppage occurred due to a user interrupt." Docs for `is_interrupt`: "Cancelling a running tool does not fire this hook". So the `is_interrupt` branch in `hook.py` rarely runs, and `README.md:95` overstates it.

```
59 min after a real Esc: RUN
```

### R2-15. MINOR, LIKELY: a background subagent turns a finished slot blue with no end event

The Stop input lists `background_tasks`, so work can outlast the turn. No later Stop arrives for it:

```
slot after main Stop then a background agent's PreToolUse: RUN (no further Stop for the main turn)
```

The state effect is confirmed. That hooks fire this way after Stop is inferred from the docs, not observed.

### R2-16. MINOR, CONFIRMED: a live run with no metrics loses its slot at 24 hours and never returns

`_publish` drops repeats (`train.py:365`), so a log with no step or loss never refreshes `updated`, and the slot expires while the file grows:

```
hour 23, log still growing: RUN
hour 24, log still growing: SLOT GONE
hour 25, log still growing: SLOT GONE
```

A later error or done does bring it back. Fix: refresh the slot on file growth.

### R2-17. MINOR, CONFIRMED: every host timer stops during sleep

`time.get_clock_info('monotonic')` reports `mach_absolute_time()`. `man clock_gettime` says that clock "does not increment while the system is asleep". In `s7`, after 65 simulated minutes of sleep:

```
    daemon age of the slot after 65 min slept: 4.3 s
```

`N ago` text under-reports, and the 24-hour limit, the 1-hour rule and the linger times all count awake time only. This is why R2-01 and R2-04 last longer than they read. It also has a benefit: sleep cannot cause a false stale run or PONG timeout (see the verified passes). Use wall time for display and long expiries, and keep monotonic for the link.

### R2-18. MINOR, LIKELY: a second session on a tty deletes the first, even one with a prompt open

```
slots: [('claude:child', 'IDLE')]
```

`_drop_same_tty` (`state.py:213`) assumes one session per tty. The state effect is confirmed: a `needs` slot vanished. The trigger is not: a `claude -p` run from the same tab, if it shares the tty. Limit the rule to `idle` and `done` slots, or check that the old process is gone.

### R2-19. MINOR, LIKELY: a failed tty lookup keeps the old tty

`s.terminal.update` keeps old values when the new one is empty (`state.py:206`):

```
terminal after resume with no tty: {'bundle': 'com.apple.Terminal', 'tty': '/dev/ttys001'}
```

A session resumed elsewhere with a failed lookup is then proved against its old tab. The state is confirmed; the sequence in real use is not. When a want-tty event arrives with no tty, clear it.

### R2-20. MINOR, UNVERIFIED: `keystroke failed` can be wrong after a timeout

`_run` turns a 3 s timeout into `None`, so `guarded_key` reports `keystroke failed` (`actions.py:205`). The cooldown does not start and the prompt stays armed:

```
  FAIL a press whose outcome is unknown does not leave the prompt armed   [2 attempts, oled='keystroke failed     ']
```

If `osascript` hung after the key landed, a retry would send a second Return. The fake raises instantly, and I have no evidence that `osascript` ever hangs at that point. Treating a timeout as "maybe sent" is still cheap.

### R2-21. MINOR, UNVERIFIED: Secure Keyboard Entry might swallow the key while the script says `sent`

`actions.py:108` cannot tell whether the key was delivered. With Secure Keyboard Entry on in Terminal, the event might not arrive, and the slot would still go to `run`. Apple TN2150 covers interception only and says nothing about injected events, so it neither supports nor rules this out. Try it once by hand.

---

## Verified passes

**End to end, real firmware and daemon**

- Daemon before plug-in: the full state reached the panel 0.11 s after plug-in (`s1`).
- Daemon after plug-in: host mode and `no agents` in 0.08 s (`s2`).
- Unplug mid-run: detected. A status changed while out, and it reached a freshly booted firmware after replug, in 0.15 s (`s3`).
- PING gap of 5.6 s: KBD screen, stored status kept, back to WAIT in about 1 s with no reconnect. F3 holds.
- PING gap of 7.2 s: exceeds the PONG timeout, reopens, full state in 2.8 s (`s4`).
- Seven sessions: the first six keep their slots, the seventh gets amber, and it takes a freed slot on its next event (`s5`, apart from R2-09).
- Sleep and wake: no false PONG timeout, no false stale state, host mode back unaided (`s7`).
- Approve path: wrong tab gives no key and `tap slot first`; an agent tap focuses the tab; Return goes only to that tty; the slot goes to `run`; a second tap sends nothing; a focus move inside the script is reported as refused (`s8`).

**K-01 paths that hold**

- No key for VS Code, Ghostty, WezTerm, no bundle, no tty, a malformed tty, `/dev/console`, or a question dialog (`state_probes.out`, all `presses=[]`).
- `sent` is returned only when the script prints `sent`. Non-zero exit gives `keystroke failed` (`actions.py:198-205`).
- `frontmost()` parses real `lsappinfo` output (read-only, returned `com.anthropic.claudefordesktop`).
- The Terminal press, focus and read scripts compile.

**Firmware**

- F1, F2, F3, F4, F8 and F11: covered by `Firmware/tests/run.sh`, `fails=0`, and read in the output.
- Talk held across host to fallback and fallback to host: F20 down then up, no stuck key.
- Stop pressed in fallback and released in host: not stuck.
- Stop pressed in host and released in fallback: no Escape at all, no stray release (`s14`).
- Tap and hold across 16-bit and 32-bit timer wrap: correct.
- Sanitizers: no ASan or UBSan error in any e2e run.
- EEPROM: no writer in the keyboard directory (grep empty). The three init calls are the `_noeeprom` forms; `rgb_matrix_mode_noeeprom` passes `write_to_eeprom=false`. Nothing writes during normal running.
- `production/firmware.uf2` is newer than `keymap.c` (13:51 against 13:48) and `G6.production_uf2` passes. I did not rebuild it.

**Hooks**

- All 11 event names are in the docs and in the 2.1.316 binary.
- `matcher: "*"` and a `timeout` in seconds are documented. `examples/claude-hooks.json` equals `frostbite-ctl hooks` output, and a path with a space is quoted.
- The hook never wrote to stdout and always exited 0:

```
daemon absent, PreToolUse                    median    27.0 ms  max    27.5 ms
daemon absent, PermissionRequest (ps lookup) median    33.1 ms  max    34.1 ms
healthy listener, PreToolUse                 median    27.6 ms  max    29.1 ms
wedged daemon, backlog full                  median    27.6 ms  max    28.1 ms
stdin held open 4 s by the writer: 2070 ms rc=0 (alarm is 2 s)
20 MiB PostToolUse payload: 42 ms rc=0 writer_got_EPIPE=True (over MAX_STDIN, message is dropped)
```

Hooks block by default, but about 30 ms per event is negligible and 2.07 s is the worst case, below the 5 s timeout. Note that `README.md:17` says "Gives up after 0.2 s": that is the socket only, and the whole-hook limit is 2 s. The EPIPE case is not reachable with normal tool output, and I did not test how Claude Code treats it.

## Fix order

1. R2-01 and R2-02 together: verify the dialog is on screen inside the press script.
2. R2-03: decide fallback Stop, then make the README and the firmware agree.
3. R2-04: seed from mtime, and give stale runs their own look and a pad acknowledge.
4. R2-05: walk the parent chain, add a diagnostic, and do one real-session test with a real pad.
5. R2-08: one-line firmware fix, then assert it in the harness.

## Audit conduct

The brief said no git. I ran `git log --oneline` and `git status --short` (also with `--ignored`), all read-only, before catching this. Nothing was staged or committed. `host/`, `Firmware/` and `design.json` show no changes in that status. `docs/BUILD.md`, `docs/concepts/generative/coupon/` and `docs/coupons/` are untracked and are not from this audit.

The `Firmware/tests/run.sh` output went to scratch. `~/.claude/settings.json` was not touched by this audit. No frostbite LaunchAgent is loaded.
