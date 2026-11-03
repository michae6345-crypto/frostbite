# Frostbite host

The laptop side of Frostbite. A small daemon talks Raw HID to the pad (VID `0xFEED`, PID `0x4642`,
usage page `0xFF60`, usage `0x61`, 32-byte reports, as defined under `"protocol"` in `../design.json`). It shows the
status of Claude Code sessions, training runs and anything else you script on the six agent
keys and the OLED, and it handles the Approve / Stop keys.

```
Claude Code hooks ──► frostbite-hook ─┐
frostbite-ctl (CI, scripts) ──────────┼─► unix socket ─► frostbite-daemon ◄──► pad (Raw HID)
--watch-train log / metrics.jsonl ────┘   ~/Library/Application Support/frostbite/frostbite.sock (dir 0700, socket 0600)
```

| Command | What it is |
|---|---|
| `frostbite-daemon` | Owns the pad, sends a PING and `SET_ALL` every 2 s (the firmware drops to F-keys after 5 s without one), reconnects after an unplug, runs the training watchers |
| `frostbite-hook` | Called by Claude Code hooks. Reads the hook JSON on stdin and forwards one event. Gives up after 0.2 s, never writes to stdout, always exits 0 |
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

A slot also goes away without any event, because a crash or a closed window sends none. A Claude session silent
for 1 hour drops from `run` to idle (Stop does not fire after an interrupt). Any slot silent for 24 hours is freed.
A new Claude session on the same tty replaces the old slot.

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
    "PermissionRequest": [{ "matcher": "*", "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
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
| PermissionRequest, Notification (permission prompt) | `needs`, line 2 = `Bash(npm test)?` |
| PostToolUse, PostToolUseFailure | closes the prompt for that tool; an interrupted tool ends the turn (`done`) |
| Notification (question, MCP dialog, agent needs input) | `needs`, answered in the terminal only |
| Notification "waiting for your input" | `done`, unless a prompt is open |
| Stop | `done` |
| StopFailure | `error` (an API error ended the turn) |
| SubagentStop | ignored (folded into the parent session) |
| SessionEnd | slot freed |

`needs` is tracked per prompt (tool, input and subagent), so events from sibling tools and subagents do not clear a
prompt that is still open. Line 2 stays on the oldest open prompt.

If your Claude Code version lacks `PermissionRequest`, the `Notification` hook still covers permission prompts. Leaving out a hook that Claude Code does not know is harmless.

No hook fires when you answer a prompt in the terminal. A tool you approved there stays amber until it finishes, and
a prompt you denied there stays amber until your next message or the next Stop.

## Keys

Every keystroke and every refusal is logged (`ACTION ...` lines in the daemon log).

**Approve and Stop only ever reach the selected slot's own session.** A keystroke is sent only when all of this is true,
checked just before the key and again inside the script that presses it:

- the session runs in Terminal or iTerm2, the two apps whose focused tab can be read,
- that app is frontmost,
- the focused tab or pane has the session's tty.

If another tab or app is in front, nothing is sent and the OLED shows `tap slot first`. Tap the agent key (its tab comes
forward), then press Approve.

Some sessions can never be proved, so the pad never presses a key for them and shows `answer in terminal`: **VS Code**
(nothing says whether the editor or the terminal panel has focus, and Return would type into an open file), Ghostty,
WezTerm, Cursor, the desktop app, SSH and tmux panes. Questions (`AskUserQuestion`, plan approval, MCP dialogs) show the
same message in every terminal, since Return would pick an option you have not read.

| Key | Daemon action |
|---|---|
| agent tap | Select the slot. For a Claude session with a known cwd: Terminal/iTerm2 switch to the tab with the session's tty, VS Code runs `open -b com.microsoft.VSCode <cwd>`. Other apps: select only |
| agent hold | Open the slot's log (training log in your text editor; Claude transcript revealed in Finder), path printed to the log |
| Approve tap | Only if the selected slot is a Claude session waiting on a permission prompt: Return, then the slot goes to `run` |
| Approve hold | Same condition: Escape (deny), then the slot goes to `done` |
| Talk | Nothing in the daemon (see below) |
| Stop | Only if the selected slot is a Claude session in `run` or `needs`: Escape, then the slot goes to `done`. Empty, training and script slots: nothing |

Approve is one-shot: the prompt closes when the key is sent, presses within 1 s of a keystroke are ignored, and a press
that waited over 1 s in the queue is dropped.

Keystrokes go through `osascript` / System Events. macOS asks for permission the first time:
allow **Accessibility** (System Settings → Privacy & Security → Accessibility) and **Automation →
System Events**, **Terminal** and **iTerm2** for the program running the daemon. That is your terminal when started by
hand, or the tool's Python when started by launchd (`head -1 ~/.local/bin/frostbite-daemon` shows its path).
Without Automation the tty cannot be read, so every keystroke is refused.

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
- `needs`: the file stopped growing for `--stale-minutes` (default 10). A killed run also just goes quiet, so silence is amber, not green, and it returns to `run` if lines resume. `--stale-status done` shows green instead.
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
`tests/test_audit_findings.py` holds the findings from `docs/audit/host.md`. No test sends a real keystroke.
