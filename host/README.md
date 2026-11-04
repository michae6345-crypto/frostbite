# Frostbite host

The laptop side of Frostbite. A small daemon talks Raw HID to the pad (VID `0xFEED`, PID `0x4642`,
usage page `0xFF60`, usage `0x61`, 32-byte reports, as defined under `"protocol"` in `../design.json`). It shows the
status of Claude Code sessions, training runs and anything else you script on the six agent
keys and the OLED. Approve answers Claude Code's permission request directly, with no keystroke. Stop sends Escape, but
only to a session it can prove is in front.

```
Claude Code hooks ──► frostbite-hook ─┐
frostbite-ctl (CI, scripts) ──────────┼─► unix socket ─► frostbite-daemon ◄──► pad (Raw HID)
--watch-train log / metrics.jsonl ────┘   ~/Library/Application Support/frostbite/frostbite.sock (dir 0700, socket 0600)
```

| Command | What it is |
|---|---|
| `frostbite-daemon` | Owns the pad, sends a PING and `SET_ALL` every 2 s (the firmware drops to F-keys after 5 s without one), reconnects after an unplug, runs the training watchers |
| `frostbite-hook` | Called by Claude Code hooks. Reads the hook JSON on stdin and forwards one event. 0.2 s to connect, 2 s hard limit, nothing on stdout, always exits 0. The exception is `PermissionRequest`, which waits up to 30 s for the pad and prints a decision only after a press |
| `frostbite-ctl` | `set 3 run "CI build"`, `clear 3`, `select 3`, `status`, `watch PATH --name N`, `unwatch N`, `hooks` |

## Install

```sh
uv tool install ./host            # puts frostbite-daemon / -hook / -ctl in ~/.local/bin
# or run from the checkout without installing:
cd host && uv run frostbite-daemon --dry-run
```

Check the pad is seen: `uv run python -c "from frostbite_host.device import HidTransport; print(HidTransport.find())"`.

Try it without hardware:

```sh
frostbite-daemon --fake             # simulated pad; type: tap 1, hold 1, tap approve, cw, show
frostbite-daemon --dry-run          # prints every report it would send
```

## Slots and the OLED

- A new source takes the first free slot (agent1 = slot 1 ... agent6 = slot 6). The same session or run keeps its slot.
- `done` slots stay green for 10 minutes and then free up (`--linger-minutes`). `error` slots stay for 30 minutes. If all six are taken, the oldest finished slot is reused. Running and waiting slots are never pushed out.
- Turn the encoder or tap an agent key to select a slot. The OLED shows that slot:

```
claude#2 my-app  WAIT     <- source#slot name, status word right-aligned (21 ASCII chars)
Bash(npm test)?           <- what it is doing or waiting on / "e3 s812 loss 0.4213"
```

Only a project name too long for the line switches to the short label (`c#2 frostbite-host`, `t#3 ...`),
and the middle of the name is cut so both ends stay readable.

Status words: `IDLE RUN DONE WAIT ERR`. An empty slot shows a summary such as `1 wait 2 run`.
The light gap glows red if anything failed, amber if anything is waiting on you, and ice blue otherwise.
If all six slots are busy and a seventh session asks for you, the glow goes amber and the OLED says so.

A slot also goes away without any event, because a crash or a closed window sends none. A Claude session silent for
15 minutes drops from `run` to idle, or after 1 hour inside one tool call (Stop does not fire after an interrupt). An
amber slot no pad press can answer drops to idle after 30 minutes. Any slot silent for 24 hours is freed. These timers
count awake time only. A new Claude session on the same tty replaces a finished slot, but not a running or waiting one.

## Claude Code

Find the installed hook's absolute path with `which frostbite-hook`, then print a snippet
that already contains it:

```sh
frostbite-ctl hooks --hook "$(which frostbite-hook)"
```

Merge it into the `"hooks"` object of `~/.claude/settings.json` yourself. Nothing here edits your settings.
This is the snippet with a placeholder path (also in `examples/claude-hooks.json`):

```json
{
  "hooks": {
    "SessionStart":      [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "UserPromptSubmit":  [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "PreToolUse":        [{ "matcher": "*", "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "PermissionRequest": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 40 }] }],
    "PostToolUse":       [{ "matcher": "*", "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "PostToolUseFailure":[{ "matcher": "*", "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "Notification":      [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "PreCompact":        [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "Stop":              [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "StopFailure":       [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "SessionEnd":        [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }]
  }
}
```

| Hook | Slot |
|---|---|
| SessionStart | claims a slot (idle) and records the terminal app + tty |
| UserPromptSubmit | `run`, line 2 = the prompt, closes any open prompt |
| PreToolUse | `run`, line 2 = `Bash(npm test)`. `AskUserQuestion` / `ExitPlanMode`: `needs` |
| PermissionRequest | `needs`, line 2 = `Bash(npm test)?`, and the hook waits for the pad (see Approve below) |
| Notification (permission prompt) | `needs`, shown only: this covers prompts no `PermissionRequest` announced |
| PostToolUse, PostToolUseFailure | closes the prompt for that tool |
| Notification (question, MCP dialog, agent needs input) | `needs`, answered in the terminal only |
| Notification "waiting for your input" | `done`, unless a prompt is open |
| Stop | `done` |
| StopFailure | `error` (an API error ended the turn) |
| SubagentStop | ignored (folded into the parent session) |
| SessionEnd | slot freed |

`needs` is tracked per prompt (tool, input and subagent), so events from sibling tools and subagents do not clear a
prompt that is still open. Line 2 stays on the oldest open prompt.

If your Claude Code version lacks `PermissionRequest`, the `Notification` hook still covers permission prompts. Leaving out a hook that Claude Code does not know is harmless.

No hook fires when you answer a prompt in the terminal. A tool you approved there stays amber until it finishes, and a
prompt you denied there stays amber until your next message, the next Stop, or 30 minutes. That amber cannot do any
harm: with no hook waiting, the pad has nothing to answer.

Cancelling a tool with Esc in the terminal fires nothing either, so the slot stays blue until the timers above.

## Approve

Approve sends **no keystroke**. `PermissionRequest` is a hook that can return a decision, so the pad answers through it:

1. Claude Code is about to ask for permission and runs `frostbite-hook`.
2. The hook gives this request a random id, connects to the daemon and stays connected.
3. The slot goes amber and the OLED shows the tool and its input. A long command pages through every 2 s, so you can
   read its tail. If the selected slot has no live request, the pad switches to this one.
4. **Approve** prints an allow for that id only. **Hold Approve** prints a deny, and Claude carries on and is told you
   denied it. Each press answers one call, and no rule or mode is saved.
5. Anything else prints nothing, and the normal terminal prompt handles it: the wait ends, the daemon is not running,
   no pad is plugged in, `--dry-run` or `--fake` is on, or anything goes wrong.

A press goes to the id last sent to the OLED, down that hook's own connection, so it cannot answer anything else. The
request must also have been on the OLED for 0.6 s, so a press aimed at the previous text does not land on the next one.
A message such as `approved` hides the request and restarts that 0.6 s. A slot with no connected hook has nothing to
answer and shows `answer in terminal`, however amber it is.

`AskUserQuestion`, plan approval and MCP dialogs are shown but never answered from the pad, since the answer is the
content. Sandbox network prompts reach the pad only through `Notification`, so those are shown only as well. If your
Claude Code version lacks `PermissionRequest`, every prompt is shown only.

### Why it waits 30 seconds

The wait is 30 s (`FROSTBITE_APPROVE_WAIT`, up to 120, `0` turns pad answers off). If you raise it, raise the handler's
`timeout` to at least 5 s more, or Claude Code cancels the hook first; the snippet uses 40.

The docs do not say whether the terminal prompt shows while the hook runs, so this is built for the worst case: if the
prompt were hidden, you would wait at most 30 s before it appears. That is long enough to notice the amber and read the
OLED. Reading the Claude Code 2.1.316 binary suggests the worst case is the exception. In an ordinary session the dialog
appears at once and races the hook, and whichever answers first wins. For teammates the hook runs before the dialog,
so there the wait does delay it. That comes from reading the code, not from a run, and it can change in any release.

### What the Claude Code docs say

From the [hooks reference](https://code.claude.com/docs/en/hooks.md), read 2026-11-03. These are paraphrased, with the
section to check:

| Point | Section | What this means here |
|---|---|---|
| Output is `hookSpecificOutput` with `hookEventName` and `decision.behavior` `allow` or `deny`, plus an optional `message` for deny | PermissionRequest decision control | Exactly what the hook prints. `updatedInput`, `updatedPermissions` and `interrupt` are never set |
| Exit 2 is not honoured for this event, so a deny must be the `decision` object | PermissionRequest decision control | The hook always exits 0 |
| An allow does not override a matching deny or ask rule | PermissionRequest decision control | Your rules still apply after a press |
| The event fires only when Claude is about to ask, or would auto-deny a call that cannot prompt | PermissionRequest input | Auto-approved tools never reach the pad |
| The input has `tool_name` and `tool_input` but no `tool_use_id` | PermissionRequest input | The request id is the hook's own, and prompts are matched to `PostToolUse` by tool, input and subagent |
| The default `command` timeout is 600 s, and a timed-out hook's output is discarded | Hook handler fields, Timeouts | A timeout gives no decision. The hook's own wait always ends first |
| Matching hooks run in parallel, and an identical handler in two settings files runs once | Hook handler fields | The wait does not hold up other hooks on this event |
| `Notification` `permission_prompt` fires only after about six seconds | PermissionRequest | Too late to be the signal, so `PermissionRequest` is |
| No `PermissionRequest` runs for a sandboxed command's network request | PermissionRequest | Those are shown from `Notification`, never answered |
| In sessions that cannot prompt, "if no hook returns a decision, it denies the tool call" | PermissionRequest | There, a missed wait is a denied call. It is never an allow |

**Not stated in the docs:**

- Whether the terminal prompt shows during the hook. Handled by assuming it might not (see above).
- Which decision wins between several `PermissionRequest` hooks. The docs give a precedence order for `PreToolUse` only.
  Fail-safe: this hook never answers without a press. If you run another hook that allows things, it can answer first.
- How a cancelled hook is terminated. The daemon treats a closed connection as the request ending.

**Known limit.** If you answer in the terminal and then press Approve within the wait, the press has nothing to act on
(the 2.1.316 code drops a late hook answer), but the slot says `approved` until the next event.

## Keys

Every action and refusal is logged (`ACTION ...` lines in the daemon log).

| Key | Daemon action |
|---|---|
| agent tap | Select the slot. For a Claude session with a known cwd: Terminal/iTerm2 switch to the tab with the session's tty, VS Code runs `open -b com.microsoft.VSCode <cwd>`. Other apps: select only. Tapping the already selected slot clears a finished, failed or quiet training or script slot |
| agent hold | Open the slot's log (training log in your text editor; Claude transcript revealed in Finder), path printed to the log |
| Approve tap | Answer the request on the OLED: allow |
| Approve hold | Answer the request on the OLED: deny |
| Talk | Nothing in the daemon (see below) |
| Stop | Only if the selected slot is a Claude session in `run`: Escape, then the slot goes to `done`. Waiting, empty, training and script slots: nothing |

A command key that waited over 1 s in the queue, or arrived just after a stall in USB reads, is dropped.

**Stop is the one real keystroke**, and in host mode it reaches only the selected slot's own session. It is sent only
when all of this is true, checked just before the key and again inside the script that presses it:

- the session runs in Terminal or iTerm2, the two apps whose focused tab can be read,
- that app is frontmost,
- the focused tab or pane has the session's tty.

If another tab or app is in front, nothing is sent and the OLED shows `tap slot first`. Tap the agent key (its tab comes
forward), then press Stop. **VS Code** (nothing says whether the editor or the terminal panel has focus), Ghostty,
WezTerm, Cursor, the desktop app, SSH and tmux panes can never be proved, so they show `answer in terminal`. So does a
tty two running slots both claim.

Escape goes through `osascript` / System Events. macOS asks for permission the first time: allow **Accessibility**
(System Settings → Privacy & Security → Accessibility) and **Automation → System Events**, **Terminal** and **iTerm2**
for the program running the daemon. That is your terminal when started by hand, or the tool's Python when started by
launchd (`head -1 ~/.local/bin/frostbite-daemon` shows its path). Without Automation the tty cannot be read, so Stop
is refused. Approve needs none of these permissions and works in every terminal, including VS Code and SSH.

### With no daemon running

None of the above applies when the pad is not in host mode: the daemon is stopped, or for a couple of seconds after the
Mac wakes, until the first PING. The pad is then a plain keyboard. **Stop is a plain Escape to whatever app is in
front**, with no proof of anything. It can interrupt whichever Claude session has focus, or cancel a dialog in any
app. Approve is F19, the agent keys are F13-F18 and Talk is F20. Changing fallback Stop to an unassigned key is a
one-line change in `Firmware/qmk/keyboards/frostbite/keymaps/default/keymap.c` and in `design.json`.

## Talk (dictation)

The daemon leaves Talk alone. The pad sends **F20** for Talk, held down for as long as you hold the key.
Bind your dictation tool to F20:

- **Wispr Flow**: Settings → Shortcuts → push-to-talk shortcut → click the field and press Talk. Hold Talk to dictate, release to insert.
- **macOS Dictation**: System Settings → Keyboard → Dictation → Shortcut → Customize… → press Talk. Press Talk to start and press it again to stop.

F13-F19 (agent keys and Approve when no host is running) can be bound the same way, for example in Raycast or Hammerspoon.

## Training runs

```sh
frostbite-daemon --watch-train ~/code/my-model/runs/latest/train.log --name my-model
frostbite-daemon --watch-train a.log --name run-a --watch-train b.jsonl --name run-b
frostbite-ctl watch ~/code/my-model/metrics.jsonl --name my-model   # add to a running daemon
```

- Text logs: step / epoch / loss from lines such as `Epoch 3/10 | step 812 | loss: 0.42`, `{'loss': 0.25, 'epoch': 0.5}`, `iter 1200/5000 train_loss=1.2e-2` and tqdm `loss=0.43`. `val_loss` is not shown as the training loss.
- JSONL: keys `loss` / `train_loss` / `train/loss`, `step` / `global_step`, `epoch`. `{"event": "end"}` or `{"status": "done"}` marks the run finished.
- `error`: a nan/inf in any loss (`loss: tensor(nan, ...)`, `loss is nan`, `Loss became NaN`), a traceback even with a log prefix such as `[rank0]:` (line 2 shows the exception line that follows), `...Error:` lines, CUDA/MPS out of memory. Not `best_loss: inf`, `loss_scale: inf`, file names, or `ConnectionError: retrying`. An error stays until a new run starts (`Starting training`, `{"event": "start"}`) or the file is truncated or replaced.
- `done`: lines such as `Training complete`, `Saving final model`, `FROSTBITE_DONE`, or your own `--done-pattern REGEX`. Not `warmup training finished, starting main loop`.
- Quiet: the file stopped growing for `--stale-minutes` (default 10), by the file's own age, so an old log is quiet straight after a restart. A killed run also just goes quiet, so silence is not shown as green, and nothing is waiting on you, so it is not amber: the slot goes dim (`quiet 10m ...`), returns to `run` if lines resume, and frees itself after 10 minutes. Tap the selected slot to clear it sooner. `--stale-status done` shows green instead.
- A file rotated or truncated, even one that regrows past the old size, counts as a new run. Lines written just before a rotation are still read. A file over 16 MiB is read from its last 16 MiB.
- The file may not exist yet. It is picked up when it appears.

## Anything else

```sh
frostbite-ctl set 3 run "CI build" --detail "deploy #42"
frostbite-ctl set 3 done "CI build"
frostbite-ctl clear 3
frostbite-ctl status
```

`examples/gh-actions-slot.sh` mirrors the current repo's latest GitHub Actions run on a slot with `gh run watch`.

## Start at login

`examples/com.frostbite.daemon.plist` is an example LaunchAgent. It is not installed. Replace
`YOUR_USER`, copy it to `~/Library/LaunchAgents/`, then:

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.frostbite.daemon.plist
tail -f ~/Library/Logs/frostbite-daemon.log
launchctl bootout gui/$(id -u)/com.frostbite.daemon     # stop
```

## Protocol notes for the firmware

- Host writes are 32-byte reports with no report ID (hidapi gets a leading `0x00`).
- `OLED_LINE` is always sent padded to 21 characters, so the firmware can draw it as is. A shorter `len` should still blank the rest of the line.
- The host opens only VID `0xFEED` + PID `0x4642` + usage page `0xFF60` + usage `0x61`. Those usage values alone are QMK defaults, and on a VIA keyboard PING (`0x05`) is a keymap write and `SET_SELECTED` (`0x06`) a keymap reset.
- A newly opened pad gets one PING and nothing else until it answers with protocol version 1. A pad that stops answering for 6.5 s is closed and reopened.
- Line 2 changes every 2 s while a long prompt pages through. Nothing else about the protocol changed for Approve.
- The pad owns the encoder: it moves the selection itself and reports it in `ENCODER`. The host sends `SET_SELECTED` when an agent key selects a slot or after a reconnect, and follows the selection in PING replies unless its own `SET_SELECTED` went out in the last 0.5 s. So a crossing `ENCODER` and `SET_SELECTED` settle on what the pad shows.
- After every (re)connect the host sends the full state: `SET_ALL`, both OLED lines, `SET_SELECTED`, `SET_GLOW`. Later it sends what changed, plus `SET_ALL` right after every PING so the pad recovers from a PING gap.
- Reports the host does not understand are ignored.

## Tests

```sh
cd host && uv run pytest -q
```

The tests cover protocol round-trips and exact bytes, device selection, slot assignment and lingering,
OLED truncation, hook payloads (`tests/fixtures/hooks/`), training logs (normal, NaN at step 812, traceback,
finished, JSONL, tqdm, stale, rotation), key-action guards with a fake `osascript`, and an end-to-end run. The
end-to-end run starts a threaded daemon on a FakeDevice and real socket, sends events from real `frostbite-hook`
and `frostbite-ctl` processes and a live log file, then unplugs and replugs the fake pad.
`tests/test_audit_findings.py` and `tests/test_round2.py` hold the audit findings, the second with real `frostbite-hook`
processes waiting on a real daemon. No test sends a real keystroke or installs a hook.
