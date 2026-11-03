# Frostbite host

The laptop side of Frostbite. A small daemon talks Raw HID to the pad (usage page `0xFF60`,
usage `0x61`, 32-byte reports, as defined under `"protocol"` in `../design.json`). It shows the
status of Claude Code sessions, training runs and anything else you script on the six agent
keys and the OLED, and it handles the Approve / Stop keys.

```
Claude Code hooks ──► frostbite-hook ─┐
frostbite-ctl (CI, scripts) ──────────┼─► unix socket ─► frostbite-daemon ◄──► pad (Raw HID)
--watch-train log / metrics.jsonl ────┘   ~/Library/Application Support/frostbite/frostbite.sock (dir 0700, socket 0600)
```

| Command | What it is |
|---|---|
| `frostbite-daemon` | Owns the pad, sends a PING every 2 s (the firmware drops to F-keys after 5 s without one), reconnects after an unplug, runs the training watchers |
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
frostbite-daemon --fake --dry-run   # simulated pad; type: tap 1, hold 1, tap approve, cw, show
frostbite-daemon --dry-run          # prints every report it would send; never presses keys
```

## Slots and the OLED

- A new source takes the first free slot (agent1 = slot 1 ... agent6 = slot 6). The same session or run keeps its slot.
- `done` slots stay green for 10 minutes and then free up (`--linger-minutes`). `error` slots stay for 30 minutes. If all six are taken, the oldest finished slot is reused. Running and waiting slots are never pushed out.
- Turn the encoder or tap an agent key to select a slot. The OLED shows that slot:

```
claude#2 my-app  WAIT     <- source#slot name, status word right-aligned (21 ASCII chars)
Bash(npm test)?           <- what it is doing or waiting on / "e3 s812 loss 0.4213"
```

Status words: `IDLE RUN DONE WAIT ERR`. An empty slot shows a summary such as `1 wait 2 run`.
The light gap glows red if anything failed, amber if anything is waiting on you, and ice blue otherwise.

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
    "Notification":      [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "PreCompact":        [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "Stop":              [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }],
    "SessionEnd":        [{ "hooks": [{ "type": "command", "command": "/ABSOLUTE/PATH/TO/frostbite-hook", "timeout": 5 }] }]
  }
}
```

| Hook | Slot |
|---|---|
| SessionStart | claims a slot (idle) and records the terminal app + tty |
| UserPromptSubmit | `run`, line 2 = the prompt |
| PreToolUse | `run`, line 2 = `Bash(npm test)` |
| PermissionRequest, Notification (permission prompt) | `needs`, line 2 = `Bash(npm test)?` |
| PostToolUse | back to `run` after you approve |
| Notification "waiting for your input" | `done` |
| Stop | `done` |
| SubagentStop | ignored (folded into the parent session) |
| SessionEnd | slot freed |

If your Claude Code version lacks `PermissionRequest`, the `Notification` hook still covers permission prompts. Leaving out a hook that Claude Code does not know is harmless.

## Keys

Every keystroke is logged (`ACTION ...` lines in the daemon log). Keystrokes are sent only when the
frontmost app is a terminal (Terminal, iTerm2, Ghostty, WezTerm or VS Code). If the slot's session is
known to run in a different terminal app, nothing is sent either. Otherwise the OLED shows
`focus the terminal` and nothing happens.

| Key | Daemon action |
|---|---|
| agent tap | Select the slot. For a Claude session with a known cwd: Terminal/iTerm2 switch to the tab with the session's tty, VS Code runs `open -b com.microsoft.VSCode <cwd>`. Other apps: select only |
| agent hold | Open the slot's log (training log in your text editor; Claude transcript revealed in Finder), path printed to the log |
| Approve tap | Only if the selected slot is `needs`: Return to the terminal |
| Approve hold | Only if the selected slot is `needs`: Escape (deny) |
| Talk | Nothing in the daemon (see below) |
| Stop | Escape to the terminal (Claude Code interrupt) |

Keystrokes go through `osascript` / System Events. macOS asks for permission the first time:
allow **Accessibility** (System Settings → Privacy & Security → Accessibility) and **Automation →
System Events** for the program running the daemon. That is your terminal when started by hand, or
the tool's Python when started by launchd (`head -1 ~/.local/bin/frostbite-daemon` shows its path).
Tab switching also asks for Automation → Terminal / iTerm2.

Tip: tap the agent key first (its terminal comes to the front), then Approve.

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
- `error`: a nan/inf in any loss, `Traceback (most recent call last):` (line 2 shows the exception line that follows), `...Error:` lines, CUDA/MPS out of memory. An error stays until the file is truncated or replaced (a new run).
- `done`: lines such as `Training complete`, `Saving final model`, `FROSTBITE_DONE`, or your own `--done-pattern REGEX`. A run is also marked done when the file stops growing for `--stale-minutes` (default 10). Pass `--stale-status needs` to show amber instead.
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
- The pad owns the encoder: it moves the selection itself and reports it in `ENCODER`. The host follows that value and only sends `SET_SELECTED` when an agent key selects a slot or after a reconnect. The selection in PING replies is not used, so the two sides never fight over it.
- After every (re)connect the host sends the full state: `SET_ALL`, both OLED lines, `SET_SELECTED`, `SET_GLOW`. Later it sends only what changed.
- Reports the host does not understand are ignored.

## Tests

```sh
cd host && uv run pytest -q
```

The tests cover protocol round-trips and exact bytes, slot assignment and lingering, OLED truncation,
hook payloads (`tests/fixtures/hooks/`), training logs (normal, NaN at step 812, traceback, finished,
JSONL, tqdm, stale), key-action guards with a fake `osascript`, and an end-to-end run. The end-to-end run
starts a threaded daemon on a FakeDevice and real socket, sends events from real `frostbite-hook` and
`frostbite-ctl` processes and a live log file, then unplugs and replugs the fake pad.
