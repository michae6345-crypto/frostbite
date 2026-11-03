# Frostbite host audit

Audited 2026-11-03 on this Mac (Darwin 25.6.0, arm64, Python 3.12.16, uv 0.13.7, hidapi 0.15.0).
No pad was plugged in. No real keystroke was sent: every key path ran with a fake command runner.
No Claude Code config, hook or LaunchAgent was touched. Nothing in `host/`, `Firmware/` or `design.json` changed.

| Severity | Confirmed | Likely | Unverified | Total |
|---|---|---|---|---|
| BLOCKER | 2 | 0 | 0 | 2 |
| MAJOR | 14 | 1 | 1 | 16 |
| MINOR | 23 | 0 | 2 | 25 |

CONFIRMED means I ran it or read it directly. On a finding that ends in a real-world effect I could not safely run
(a keystroke landing, a real keyboard), the entry says which part was run and which part is reasoning.

**Evidence kit.** `docs/audit/host-tests/` holds two files:

- `test_audit_protocol.py` compiles the real, unmodified `keymap.c` with stubs (`fw_harness.c`, `fw_stub/`) and drives it with host-encoded bytes. 21 tests, all pass.
- `test_audit_findings.py` asserts the safe behaviour for each finding as a strict xfail, so a fix makes that test fail until it is un-marked. The test names carry the finding IDs.

```sh
cd host && uv run pytest ../docs/audit/host-tests -q -p no:cacheprovider --rootdir=../docs/audit/host-tests
# 29 passed, 63 xfailed in 0.97s
# add --runxfail to see each failure: 63 failed, 29 passed in 0.44s
```

The project's own suite still passes: `76 passed in 2.28s`.

Hooks doc used: https://code.claude.com/docs/en/hooks (fetched as `hooks.md`, 284,286 bytes, 2026-11-03).

---

## Biggest problems

1. **D-01**: the daemon opens any device with the QMK Raw HID usage, not just Frostbite. On a VIA keyboard its bytes are keymap-write and keymap-reset commands.
2. **K-01**: Approve answers whichever tab is frontmost, not the session on the OLED.
3. **H-01 + K-05**: `needs` does not clear when you answer, so a second tap sends another Return.

---

## BLOCKER

### D-01 Opens any QMK Raw HID device; on VIA keyboards the protocol is destructive. BLOCKER, CONFIRMED (selection), read from source (VIA effect)

- `device.py:296-302` filters only on usage page `0xFF60` and usage `0x61`. `device.py:308-317` opens the first match. VID/PID are ignored, though `keyboard.json:8-9` gives `0xFEED` / `0x4642`. `config.h:20` itself notes these usage values are the QMK defaults.
- The link is marked connected without a PING reply. `last_pong` is written (`device.py:546`) and never read.
- Test with a fake `hid` module listing a Keychron-style device (no Frostbite present in `test_device_selection_requires_frostbite_vid_pid`; both present in the probe):

```
log: opened Keychron Keychron Q1 (3434:0121)
opened b'via' connected True last_pong 0.0 events ['connected']
first bytes written ['00 05 00 00 00', '00 02 00 00 00', '00 06 00 00 00', '00 05 00 00 00']
```

- QMK `quantum/via.h`: `0x05 = id_dynamic_keymap_set_keycode`, `0x06 = id_dynamic_keymap_reset`, plus `0x0A = id_eeprom_reset` and `0x0B = id_bootloader_jump` (not sent by the host).
- QMK `quantum/via.c`: `command_id = data[0]`, `command_data = &data[1]`; `0x05` calls `dynamic_keymap_set_keycode(d[0], d[1], d[2], (d[3]<<8)|d[4])`; `0x06` calls `dynamic_keymap_reset()`.
- `quantum/dynamic_keymap.c`: both write through `nvm_dynamic_keymap_*`; reset erases the stored keymap and rewrites the compiled defaults.

So on a VIA board, each PING (every 2 s) writes keycode 0 to layer 0, row 0, col 0. Each connect sends `SET_SELECTED 0` (`06 00`), which is a full dynamic keymap reset. This loop runs whenever such a keyboard is attached and the daemon is up, pad or no pad, since `open()` retries every second. Not run on a real keyboard. The `nvm_*` implementation was not read, so "persistent" is inferred from the name.

Disproved attempt: this Mac has no such device today (`HidTransport.find()` returned `[]`), so nothing happens here. It is conditional on owning a VIA board, which is common among macropad builders.

### K-01 Approve and Stop act on whichever tab is frontmost. BLOCKER, CONFIRMED

`actions.py:129-142` checks only the frontmost app's bundle id. It never compares the slot's tty with the active tab, though the slot holds it. Two sessions in Terminal.app, slot 1 selected:

```
slots [('claude:A','NEEDS','Bash(rm -rf build)?',{..'tty':'/dev/ttys001'}),
       ('claude:B','NEEDS','Bash(git push -f)?',{..'tty':'/dev/ttys002'})]
calls [['lsappinfo','front'],['lsappinfo','info','-only'],
       ['osascript','-e','tell application "System Events" to key code 36']]
```

If ttys002 is the visible tab, the Return approves `git push -f` while the OLED says `rm -rf build`. That last step is reasoning: no key was sent. The README tip (tap the agent key first) helps only on Terminal/iTerm2 and is not enforced: `actions.py:153-163` does not switch tabs in VS Code, Ghostty or WezTerm. tmux panes are also indistinguishable to this check.

---

## MAJOR

### Keystrokes

**K-02 VS Code: Return goes into whatever has focus. CONFIRMED** (sent to VS Code; the effect on the editor is reasoning). `com.microsoft.VSCode` is in `TERMINAL_APPS` (`actions.py:30`) with no way to tell an editor from the terminal panel. `test_vscode_return_not_sent_...` shows `key code 36` sent. In an editor that inserts a newline or replaces a selection. Docs (Notification section) also say VS Code extension sessions use a `canUseTool` host, so a prompt may not be a terminal prompt at all.

**K-03 Stop and Approve are not tied to a Claude slot. CONFIRMED.** `daemon.py:157-159` sends Escape with no status or source check. `daemon.py:149-156` requires `NEEDS` but not `source == "claude"`.

```
empty slot keys [[..'key code 53']]    train slot keys [[..'key code 53']]    done claude slot keys [[..'key code 53']]
train needs keys [[..'key code 36']]   ctl needs keys [[..'key code 36']]
```

So with `--stale-status needs` (train.py:263), a quiet training run turns amber, and Approve sends Return to whatever terminal is in front.

**K-04 Guard is skipped when the session's terminal is unknown. CONFIRMED.** `actions.py:136` compares only when the slot's bundle is in `TERMINAL_APPS`. With the Claude desktop app, Cursor (`com.todesktop...`) or no bundle (SSH), Return went to frontmost Terminal: `bundle 'com.anthropic.claudefordesktop' ... keys 1`, `bundle '' ... keys 1`, `bundle 'com.todesktop.230313mzl4w4u92' ... keys 1`. It should fail closed. The bundle list itself is README-accurate.

**K-05 Approve is not one-shot. CONFIRMED** (keystroke count; the effect on Claude's UI was not run). `keys after 2 taps 2 status NEEDS`. Nothing clears `needs` on Approve (see H-01), and queued key events carry no timestamp, so presses made while the main loop waits in `guarded_key` also fire later. A second Return can land on the next prompt.

**K-06 OLED shows the newest request, not the dialog on screen. LIKELY.** `state.py:165-166` overwrites `detail` on each `PermissionRequest`; `test_oled_keeps_the_oldest_unanswered_prompt` confirms that part. Docs (Notification note) say a request can wait "behind the open dialog", so requests do queue. The display order of queued dialogs is not documented.

### Hook lifecycle

Hook detection itself is sound (see Verified passes). The gaps are in when `needs` and `run` end.

**H-01 `needs` outlives the answer. CONFIRMED** (long tool: docs plus code; deny: code, and docs show no event). README:85 says PostToolUse puts the slot back to `run` "after you approve". Docs: PostToolUse "Runs immediately after a tool completes successfully". No event fires at approval, so a 20-minute `npm test` shows amber "waiting on you" for 20 minutes. On a manual deny: PermissionDenied "doesn't run when you manually deny a permission dialog", and hold-Approve leaves `NEEDS` (`test_deny_leaves_needs`). A stale `needs` keeps Approve armed, so it sends Return into Claude's input box, or the shell after Claude exits. Fix sketch: flip to `run` in the daemon when Approve is sent. Manual answers in the terminal stay undetected.

**H-02 `needs` is cleared by unrelated events in the same session. CONFIRMED.** `hook.py:142-147` sets `run` unconditionally, and `agent_id` is ignored. Docs: subagent tool events fire the same hooks and carry `agent_id`.

```
after PermissionRequest NEEDS Bash(rm x)?
after sibling PostToolUse(Read) RUN Bash(rm x)?
approve -> ('nothing to approve', ...)
sub1 asks NEEDS / sub2 reads RUN   slots used 1
```

So a real prompt goes blue and Approve refuses it. Notification `permission_prompt` may re-raise it after about 6 s, until the next event clears it again. Subagents share one slot, which is intended, and they do not collide across slots.

**H-03 Ended turns can stay `run` forever. CONFIRMED** (docs plus code). Docs, Stop: "Does not run if the stoppage occurred due to a user interrupt. API errors fire StopFailure instead." `expire` ignores `RUN` (`state.py:197`), and StopFailure is unmapped (`hook.py:167`, output `StopFailure -> None`) and absent from the snippet (`ctl.py:25`). So the Stop key itself leaves the slot blue indefinitely: `7 days later RUN`. An `idle_prompt` might rescue it after 60 s; the docs do not say it fires after an interrupt. `PostToolUseFailure` is handled at `hook.py:146` but also missing from the snippet, the README and `examples/claude-hooks.json`, so a failed approved tool leaves `needs` until the next event.

**H-06 AskUserQuestion probably shows `run` while waiting on you. MAJOR, UNVERIFIED.** It maps to `run` (`detail: 'AskUserQuestion'`) at PreToolUse; that much is confirmed. Whether PermissionRequest or a Notification also fires for it is not stated in the docs, and I did not run a real session because that would mean installing hooks. If it does, Approve's Return would pick the highlighted option unseen. Check with one real session.

### Slots

**S-01 Dead sessions never free. CONFIRMED.** Only `DONE`/`ERROR` expire (`state.py:197`). After a crash or closed window with no SessionEnd: `expire(30d) -> False [('claude:dead','NEEDS'), ('claude:dead2','RUN'), ('claude:i','IDLE')]`. Stuck `RUN`/`NEEDS` slots are also never evicted (`state.py:119-127`), so six of them wedge the board until the daemon restarts or `frostbite-ctl clear`. Whether SessionEnd fires on a killed terminal is not documented.

**S-02 A seventh waiting session is invisible. CONFIRMED.** With six busy slots: `7th needs apply() -> False`, `glow (159, 216, 255, 110)` (not amber), `daemon reply {'ok': True}`, only a log line `slots full, all busy: ignoring claude:6`. The pad gives no sign someone is waiting.

### Training

**T-01 False sticky `error`. CONFIRMED.** Your "inf in info" case is real, through `LOSS_RE`, not `BAD_LOSS_RE`: `NUM` has no trailing boundary (`train.py:23,28`), so `loss info` parses as `inf`, and sticky error (`train.py:168-173`) lasts until the file is replaced.

```
'loss info: using cross entropy'  err='loss inf'   loss=inf
'Using loss inf-norm'             err='loss inf'
'Using loss: nan-safe mean'       err='loss: nan'
'saved best-loss-nan.pt'          err='loss-nan'
'saved val_loss_inf.pt'           err='val_loss_inf'
'loss_scale: inf'                 err='loss_scale: inf'   (AMP scaler, not a loss)
'ConnectionError: retrying in 5s' err=...   'ValueError: bad sample 17 skipped, continuing' err=...
'avoid OOM by lowering batch'     err=...
'{"msg":"no error so far","step":9}' err='no error so far'   '{"message":"error rate 0.02"}' err=...
```

Disproved: bare `nan`/`inf` in a path with no adjacent "loss" is safe (`Saved /runs/nan_fix/ckpt.pt`, `Saved /runs/inf-test/model.pt`, `loading nan_guard.py`, `2026-01-01 INFO info: model loaded` all gave `err=None`). `loss function: info_nce` is also safe.

**T-02 Real failures missed, then shown green. CONFIRMED.** These all gave `err=None`: `loss: tensor(nan, grad_fn=<MeanBackward0>)` (PyTorch's default print), `loss is nan`, `Loss became NaN at step 5`, `[rank0]: Traceback (most recent call last):`, `2026-01-01 12:00:00 ERROR Traceback ...`, `MPS backend out of memory (...)`. `TRACEBACK_RE` and `EXC_RE` are anchored to line start (`train.py:31-32`). README:137 claims "CUDA/MPS out of memory", but `FATAL_RE` has only CUDA (`train.py:33`); `RuntimeError: MPS...` is caught only by `EXC_RE`. After a missed crash the file goes quiet and T-03 reports `done`.

**T-03 False `done`. CONFIRMED.** A SIGKILLed run with no traceback: `('done', 'quiet 10m s1 loss 0.5')`. This is documented, but green means success to a reader, so `needs` would be a safer default. A 10-minute eval flips to done and back: `done`, then `('run', 's2 loss 0.4')`. Mid-run lines also match: `Data preprocessing: all done`, `warmup training finished, starting main loop`, `Stage 1 training complete, starting stage 2`, `{"event":"validation complete","step":5}`, `{"status":"success","step":5,"loss":0.3}`, `{"state":"finished epoch"}`. These recover at the next line.

**T-05 Rotation and truncation lose state. CONFIRMED.** `train.py:300-309`.

- Rotate: lines appended just before the rename are never read, so a final traceback is lost: `status idle`, last event `('run','s1 loss 0.5')`.
- `copytruncate` that regrows past the old offset is not detected: `after truncate+regrow error ValueError: boom pos 480 size 480`.
- Deleted log: the slot stays `run` forever because `poll_once` returns before the stale check: `events [('run','s1 loss 0.5')]` after 5 fake hours.

**T-06 Whole file is read into memory. CONFIRMED.** `self._fh.read()` at `train.py:310`, from offset 0 by default (`from_start=True`):

```
lines 300 MB: first poll 28.3 s; ru_maxrss MB 1231 lines 6168094 partial 0
noline 300 MB: first poll 0.92 s; ru_maxrss MB 621 lines 0 partial 314572800
```

Ping cadence stayed healthy during the parse (gaps 2.00-2.06 s), so the firmware does not drop to keyboard mode. Memory is the cost. `_partial` is also unbounded on data with no newline.

---

## MINOR

| ID | Finding | Status | Evidence |
|---|---|---|---|
| K-07 | No re-check of the frontmost app before the keystroke. Focus moved to Slack after the check: `keystrokes after focus moved to Slack: 1 ; frontmost re-checked: 1 time(s)`. Window is at least 7.6 ms `frontmost()` plus 32 ms osascript start (measured with `return 1`, not `key code`) | CONFIRMED | `actions.py:129-142` |
| K-08 | `--fake` alone uses real keystrokes. Help says "simulated pad" only | CONFIRMED | `daemon.py:341` `Actions(dry_run=args.dry_run)`, read not run |
| K-09 | With no daemon, Stop is a raw Esc to any app, unguarded. As designed | CONFIRMED | `keymap.c:131`, `design.json` fallback |
| K-10 | Prompt text and Bash commands reach the OLED and `ctl status`, including any secret in the first characters | CONFIRMED | `hook.py:56,139,143` |
| H-04 | `elicitation_url_dialog` and `agent_needs_input` ignored, though both wait on you | CONFIRMED | `hook.py:150-160`, docs matcher table |
| H-05 | `frostbite-ctl hooks --hook "/a/My Tools/..."` emits an unquoted shell command: `sh: .../My: No such file or directory`, `rc=127` | CONFIRMED | `ctl.py:31` |
| H-07 | 17+ simultaneous connects overflow `listen(16)`: 18 of a 64-burst got `ConnectionRefusedError`. Hook drops them silently. Unrealistic at 6 sessions | CONFIRMED | `daemon.py:222` |
| H-08 | Stdin over 1 MB is truncated and the event dropped, safely (rc 0, 24 ms) | CONFIRMED | `hook.py:29,180` |
| S-03 | Full board evicts an unseen ERROR before any IDLE: red slot replaced by a new idle session, glow back to blue | CONFIRMED | `state.py:120` |
| S-04 | `time.time()` is used everywhere; stepping back 1 h keeps a 3 s flash for an hour (`after clock back 1h then +10min True`) and stretches linger. A forward jump expires slots at once. `ago()` clamps safely | CONFIRMED | `state.py:207-211`, `daemon.py:34` |
| S-05 | Name follows `cwd`: `/w/app` becomes `ui` after `cd packages/ui`. For VS Code, `open -b ... cwd` then targets the subfolder. `cwd=/` gives name `claude:A` | CONFIRMED | `hook.py:122`, `actions.py:155` |
| S-06 | Only 7 name chars fit with status: `frostbite-host` and `frostbite-firmware` both give `claude#1 frostbi WAIT`. Matters given K-01 | CONFIRMED | `state.py:46-54` |
| D-02 | Selection can desync: crossing `SET_SELECTED` and `ENCODER` leave host=1, pad=2, and PING's selected is ignored: `after PING reply pad=2: host still 1`. Approve then targets a slot the strip does not highlight. Simulated, narrow timing | CONFIRMED | `daemon.py:127-133` |
| D-03 | A wedged device stays "connected": no PONG watchdog. A broken hidapi import appears only at DEBUG, then logs `pad not found` | CONFIRMED | `device.py:478,517-523` |
| T-04 | True `done` overwritten by trailing lines (wandb summary): events end at `run`, then "quiet 10m" after 10 min | CONFIRMED | `train.py:192` |
| T-07 | `runs/A/train.log` and `runs/B/train.log` without `--name` collide: `keys train:train train:train ... A stopped True`, no warning | CONFIRMED | `train.py:227`, `daemon.py:172` |
| T-08 | Error label misreports: `RuntimeError: inference failed` shows `inf loss`, `FileNotFoundError: data/finance.csv` shows `NaN/inf loss`. Status is still right | CONFIRMED | `train.py:208` substring test |
| T-09 | New run appended to the same log keeps the old error (documented). A final line with no newline waits for the stale timer | CONFIRMED | `train.py:168`, `train.py:258` |
| I-01 | Plist has `--` inside an XML comment: `xmllint` "Double hyphen within comment", Python `plistlib` `ExpatError`. `plutil -lint` says OK, so launchd likely accepts it | CONFIRMED | `com.frostbite.daemon.plist:20-23` |
| I-02 | `--socket path` chmods the parent directory to 0700 (`par` went `drwxr-xr-x` to `drwx------`) | CONFIRMED | `daemon.py:207`, `ipc.py:38` |
| I-03 | Simultaneous starts: loser dies with a raw traceback (`Address already in use`, `FileNotFoundError`). 5 rounds never left two alive; the unlink race at `daemon.py:212` is not reproduced | CONFIRMED | stress run |
| I-04 | Board is memory-only: a daemon restart drops a waiting `needs` until the next event | CONFIRMED | `daemon.py:340` |
| I-05 | Malformed IPC can half-apply: `{"terminal":"str"}` returned `internal error` but left slot `k2`. Local same-UID only | CONFIRMED | `state.py:171-172` |
| I-06 | uv's Python is ad-hoc signed (`Signature=adhoc`), so a TCC grant may not survive `uv python upgrade`, and launchd prompts may not appear | UNVERIFIED | needs a real grant |
| D-04 | Seize-open may require Input Monitoring on some macOS versions. hidapi defaults to exclusive (`hid_init` → `hid_darwin_set_open_exclusive(1)`). No device here | UNVERIFIED | `libusb/hidapi mac/hid.c`, master |

---

## Verified passes

**Hooks (item 1)**

- All 9 snippet events exist as doc sections, plus SubagentStop. Fields `session_id`, `cwd`, `hook_event_name`, `transcript_path`, `prompt`, `tool_name`, `tool_input`, `message`, `notification_type`, `last_assistant_message` and `reason` are documented. `CLAUDE_SESSION_ID` (`hook.py:118`) is not in the hooks page; it is an unused fallback.
- A permission moment is detectable: PermissionRequest fires when Claude is about to ask, Notification `permission_prompt` about 6 s later. Sandbox network prompts only get the Notification, which is handled.
- PreToolUse does **not** wrongly mark `needs` for auto-approved tools (`hook.py:142`; docs: "whether or not it needs permission").
- Matcher `*` is valid. Notification, Stop etc. correctly omit it.
- Parallel sessions take separate slots: 6 real `frostbite-hook` sessions, 192 runs in 0.79 s, all ended `done` in their own slot.
- The hook never slows Claude meaningfully, on the installed tool:

```
socket absent:   n 40 min 23.1 p50 23.5 p95 29.2 max 584.8 (first run, .pyc compile)
missing dir:     n 40 min 23.1 p50 23.6 p95 24.3 max 24.4
stale socket 23.6 ms; hung listener 23.2-23.6 ms; SessionStart (tty lookup) 34 ms
stdin never closed: exit after 2022 ms, rc 0
garbage / empty / array / 1.5 MB stdin: rc 0, no stdout, no stderr
```

Docs: failures do not block, and SessionEnd's budget rises to the snippet's `timeout: 5`.

**Protocol (item 2)**

- Every message matches the compiled `keymap.c`: `SET_SLOT`, `SET_ALL`, `OLED_LINE`, `SET_GLOW`, `SET_SELECTED`, `PING` and its reply, `KEY` tap and hold for all 9 keys, `ENCODER` with wrap, 5 s host timeout. 256 garbage commands did not disturb it.
- Reports are 32 bytes, written as 33 with leading `0x00`. hidapi `mac/hid.c` (master branch; not diffed against the 0.15.0 wheel) strips it when `data[0]==0`. `read(32, 50)` matches `hid.device.read(max_length, timeout_ms)`. `hid.device` exists in 0.15.0.
- Disconnect: `hid_read_timeout` returns -1, which the binding should raise as an error and which the link turns into a reconnect; the fake-device path passed, the real binding path did not run.
- Two daemons on one socket: the second exits 1 with `another frostbite-daemon is listening`. On different sockets, exclusive open should fail the second one, but it would log only `pad not found` (D-03). Not run: no device.

**Keystrokes (item 3)**

- No injection: `cwd`, `log`, name and tty never reach a shell or AppleScript source. Commands are argv lists, tty goes through `TTY_RE` and `on run argv`. A hostile tty was rejected, leaving `['open','-b','com.apple.Terminal']`.
- `FOCUS_TERMINAL` compiles (`osacompile rc=0`); Terminal's sdef has writable `selected` and readable `tty`.
- Refuses non-terminal front and a different known terminal app. `frontmost()` parses real `lsappinfo` output (`'com.brave.Browser'`, 7.6 ms).
- Socket: mode `srw-------`, directory `drwx------`, umask set before bind. 18 malformed payloads, two 200 KB messages (connection closed) and a stalled client (dropped after 1.0 s) left the daemon alive.

**Watcher (item 4)**

Non-UTF-8 and NUL bytes, tqdm `\r` lines, and partial JSON lines work. My suspicion that text-mode `tell()` would break on a multibyte split was wrong: `pos 34`, no false restart, and 4093-byte splits rejoined cleanly.

**State (item 5)**

Emoji, CJK, ZWJ, RTL ligatures, escapes, lone surrogates: all printable ASCII, at most 21 columns. Running and waiting slots are never evicted, as README says.

**Install (item 6)**

- `uv tool install ./host` works in a throwaway `UV_TOOL_DIR`: 3 executables, `hid.cpython-312-darwin.so` loads with system frameworks only, `hid.enumerate()` returned 24 devices.
- `--fake --dry-run` and `--dry-run` start, stop cleanly on SIGTERM and SIGINT (exit 0), and leave no socket. SIGKILL's stale socket is reclaimed on restart.
- Plist passes `plutil -lint`. It was not loaded.

---

## Not tested

Real pad, real macOS HID open and read/write, real keystrokes and what Claude's UI does with them, real Accessibility/Automation prompts, launchd loading, real Claude Code event ordering (including AskUserQuestion and whether Stop fires after a denial), and sleep/wake.
