# Frostbite host

The laptop side of Frostbite. A daemon talks Raw HID to the pad and shows the status of Claude Code sessions,
training runs and your own scripts on the OLED. Approve answers Claude Code's permission
request through a hook and sends no keystroke. Stop sends Escape, and only to a session it can prove is in front.
The HID protocol is at the top of `frostbite_host/device.py` and under `"protocol"` in `../design.json`.

| Command | Job |
|---|---|
| `frostbite-daemon` | Owns the pad and the local socket (directory 0700, socket 0600), runs the training watchers |
| `frostbite-hook` | Called by Claude Code. Forwards one event, prints nothing and exits 0 within 2 s. `PermissionRequest` is the exception: it waits for the pad |
| `frostbite-ctl` | `set 3 run "CI build"`, `clear 3`, `select 3`, `status`, `watch PATH --name N`, `unwatch N`, `hooks` |

## Install

```sh
uv tool install ./host        # puts the three commands in ~/.local/bin
frostbite-daemon --fake       # simulated pad, type: tap 1, hold 1, tap approve, cw, show
frostbite-daemon --dry-run    # prints every report it would send
frostbite-ctl hooks --hook "$(which frostbite-hook)"   # prints the Claude Code hooks snippet
```

Merge it into `~/.claude/settings.json` yourself (`examples/claude-hooks.json` shows it). Nothing here edits your settings.

## Slots and the OLED

```
claude#2 my-app  WAIT     <- source#slot name, status word (IDLE RUN DONE WAIT ERR)
Bash(npm test)?           <- what it is doing or waiting on, or "e3 s812 loss 0.4213"
```

A new source takes the first free slot and keeps it. Turn the encoder or tap an agent key to select a slot. An empty
slot shows a summary such as `1 wait 2 run`. A seventh session asking for you shows `agent waits, no slot` for 3 s.

`done` slots free after 10 minutes (`--linger-minutes`) and `error` slots after 30. When all six are taken the oldest
finished slot is reused; running and waiting slots are never pushed out. A silent Claude session drops to idle after 15
minutes (1 hour inside one tool call), a `WAIT` slot the pad cannot answer after 30, and any slot silent for 24 hours
is freed. No hook fires when you answer in the terminal or cancel a tool with Esc, so the slot keeps its status
word until the next event. That `WAIT` is harmless: with no hook waiting, the pad has nothing to answer.

## Keys

Actions and refusals are logged as `ACTION ...`. A command key over 1 s old, or just after a USB read stall, is dropped.

| Key | Action |
|---|---|
| agent tap | Select the slot and bring its Terminal or iTerm2 tab forward (VS Code: open the project). Tapping the selected slot clears a finished, failed or quiet training or script slot |
| agent hold | Open the slot's log: training logs in your editor, Claude transcripts in Finder |
| Approve tap / hold | Allow / deny the request on the OLED |
| Stop | Escape to the selected Claude session, if it is running and provably in front. The slot goes to `done` |
| Talk | Nothing in the daemon. The pad sends F20 while held, so bind your dictation tool to it |

### Approve

When Claude Code is about to ask for permission it runs `frostbite-hook`, which gives the request a random id, stays
connected to the daemon and waits. The slot goes to `WAIT` and the OLED shows the tool and input, paging every 2 s if long.
Approve prints an allow for that id, and holding Approve prints a deny. Each press answers one call and saves no rule.

A press reaches only the id last sent to the OLED, down that hook's own connection, and the request must have been on
the OLED for 0.6 s. A slot with no connected hook shows `answer in terminal`, even on `WAIT`. If the wait ends, the
daemon is down, no pad is plugged in, `--dry-run` or `--fake` is on, or anything fails, the hook exits 0 with no output
and the normal terminal prompt handles it. Nothing but a press produces a decision.

- Your deny and ask rules still apply after a press. Another allowing `PermissionRequest` hook can answer first.
- `AskUserQuestion`, plan approval, MCP dialogs and sandbox network prompts are shown only. Answer them in the terminal.
- Sessions that cannot prompt deny the call when no hook decides, so a missed wait there is a denied call.

The wait is 30 s (`FROSTBITE_APPROVE_WAIT`, up to 120, `0` turns pad answers off). If you raise it, keep the handler's
`timeout` at least 5 s longer, or Claude Code cancels the hook first; the snippet uses 40. The docs do not say whether
the terminal prompt shows during the hook, so the wait assumes it might not, and at worst the prompt comes 30 s late.

### Stop

Stop is the one real keystroke. Escape is sent only when all of this holds, checked just before the key and again
inside the script that presses it: the session runs in Terminal or iTerm2, that app is frontmost, and the focused tab
or pane has the session's tty. Otherwise nothing is sent. `tap slot first` means tap the agent key to bring the tab
forward, then press Stop. VS Code, Ghostty, WezTerm, Cursor, the desktop app, SSH, tmux panes and a tty two running
slots both claim can never be proved, so they show `answer in terminal`.

macOS asks for permission the first time. Allow Accessibility, and Automation for System Events, Terminal and iTerm2,
for the program running the daemon (your terminal, or the tool's Python under launchd). Without Automation the tty
cannot be read and Stop is refused. Approve needs none of this and works in every terminal.

### With no daemon running

All of the above needs the daemon. When it is stopped, or for a couple of seconds after the Mac wakes, the pad is a plain
keyboard. **Stop is a plain Escape to whatever app is in front**, with no proof of anything, so it can interrupt
whichever Claude session has focus or cancel a dialog in any app. Agent keys are F13-F18, Approve is F19, Talk is F20.

## Training runs

```sh
frostbite-daemon --watch-train ~/code/my-model/runs/latest/train.log --name my-model   # text log, may not exist yet
frostbite-ctl watch ~/code/my-model/metrics.jsonl --name my-model                     # JSONL, on a running daemon
```

| Status | Set by |
|---|---|
| `error` | A nan/inf in any loss, a traceback, an `...Error:` line, or GPU out of memory. Stays until a new run starts or the file is replaced |
| `done` | `Training complete`, `Saving final model`, `FROSTBITE_DONE`, `{"event": "end"}`, or your `--done-pattern REGEX` |
| idle (`quiet 10m`) | No growth for `--stale-minutes`. A killed run also goes quiet, so silence never shows `DONE`. Frees after 10 minutes; `--stale-status done` shows `DONE` instead |

## Scripts, login, tests

`frostbite-ctl set 3 run "CI build" --detail "deploy #42"` drives a slot from anything, and
`examples/gh-actions-slot.sh` mirrors GitHub Actions that way. `examples/com.frostbite.daemon.plist` is an example
LaunchAgent: replace `YOUR_USER`, copy it to `~/Library/LaunchAgents/` and load it with `launchctl bootstrap`.
Run the tests with `cd host && uv run pytest -q`. None sends a real keystroke or installs a hook.
