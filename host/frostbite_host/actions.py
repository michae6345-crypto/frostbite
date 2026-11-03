"""macOS actions behind the command keys. Conservative by design: these are real
keystrokes into a real terminal, so every one is guarded and logged.

Rule for every keystroke (Approve = Return, hold Approve = Escape, Stop = Escape):
the frontmost app must be a known terminal (Terminal, iTerm2, Ghostty, WezTerm, VS Code)
and, when the slot's own terminal app is known, it must be that one. Otherwise nothing
is sent and the OLED shows "focus the terminal".

Keystrokes go through `osascript` / System Events, which needs Accessibility permission
for whatever runs the daemon (see README).
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Callable

from .state import Slot

log = logging.getLogger("frostbite.actions")

TERMINAL_APPS = {
    "com.apple.Terminal": "Terminal",
    "com.googlecode.iterm2": "iTerm2",
    "com.mitchellh.ghostty": "Ghostty",
    "com.github.wez.wezterm": "WezTerm",
    "com.microsoft.VSCode": "VS Code",
    "com.microsoft.VSCodeInsiders": "VS Code",
}
KEY_CODES = {"return": 36, "escape": 53}
TTY_RE = re.compile(r"^/dev/tty[a-z]?\d+$")

FOCUS_TERMINAL = """
on run argv
  set wanted to item 1 of argv
  tell application "Terminal"
    repeat with w in windows
      repeat with t in tabs of w
        if tty of t is wanted then
          set selected of t to true
          set index of w to 1
          activate
          return "ok"
        end if
      end repeat
    end repeat
    activate
  end tell
  return "notfound"
end run
"""

FOCUS_ITERM = """
on run argv
  set wanted to item 1 of argv
  tell application "iTerm2"
    repeat with w in windows
      repeat with t in tabs of w
        repeat with s in sessions of t
          if tty of s is wanted then
            select w
            select t
            select s
            activate
            return "ok"
          end if
        end repeat
      end repeat
    end repeat
    activate
  end tell
  return "notfound"
end run
"""

FRONTMOST_SCRIPT = ('tell application "System Events" to get bundle identifier of '
                    'first application process whose frontmost is true')

Runner = Callable[..., subprocess.CompletedProcess]


class Actions:
    def __init__(self, dry_run: bool = False, runner: Runner = subprocess.run,
                 out: Callable[[str], None] = print):
        self.dry_run = dry_run
        self.runner = runner
        self.out = out

    # ------------------------------------------------------------------ helpers
    def _run(self, args: list[str], timeout: float = 3.0) -> subprocess.CompletedProcess | None:
        try:
            return self.runner(args, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("command failed %s: %s", args[0], e)
            return None

    def _act(self, what: str, args: list[str]) -> bool:
        """Run a side-effecting command, or print it in dry-run mode. Always logged."""
        if self.dry_run:
            self.out(f"[dry-run] ACTION {what}: {' '.join(args)}")
            log.info("ACTION (dry-run) %s", what)
            return True
        log.info("ACTION %s", what)
        r = self._run(args)
        if r is None or r.returncode != 0:
            log.warning("ACTION %s failed: %s", what, (r.stderr.strip() if r else "no result"))
            return False
        return True

    def frontmost(self) -> str:
        """Bundle id of the frontmost app ('' if unknown). Read-only, runs in dry-run too."""
        r = self._run(["lsappinfo", "front"], timeout=1.0)
        asn = r.stdout.strip() if r and r.returncode == 0 else ""
        if asn:
            r = self._run(["lsappinfo", "info", "-only", "bundleid", asn], timeout=1.0)
            m = re.search(r'"CFBundleIdentifier"\s*=\s*"([^"]+)"', r.stdout if r else "")
            if m:
                return m.group(1)
        r = self._run(["osascript", "-e", FRONTMOST_SCRIPT], timeout=2.0)
        return r.stdout.strip() if r and r.returncode == 0 else ""

    # ------------------------------------------------------------------ guarded keystrokes
    def guarded_key(self, key: str, slot: Slot | None, why: str) -> tuple[bool, str]:
        """Send Return/Escape to the frontmost app only if it is a terminal.
        Returns (sent, oled message)."""
        front = self.frontmost()
        app = TERMINAL_APPS.get(front)
        if app is None:
            log.info("ACTION refused %s (%s): frontmost app is %r, not a terminal",
                     key, why, front or "unknown")
            return False, "focus the terminal"
        want = (slot.terminal.get("bundle") if slot else None) or ""
        if want and want in TERMINAL_APPS and want != front:
            log.info("ACTION refused %s (%s): slot runs in %s but %s is frontmost",
                     key, why, want, front)
            return False, f"focus {TERMINAL_APPS[want]}"
        code = KEY_CODES[key]
        ok = self._act(f"{why}: key {key} -> {app}",
                       ["osascript", "-e", f'tell application "System Events" to key code {code}'])
        return ok, (why if ok else "keystroke failed")

    # ------------------------------------------------------------------ focus / log
    def focus(self, slot: Slot | None) -> str | None:
        """Bring the slot's terminal to the front when we know enough; else do nothing.
        Returns an OLED message or None."""
        if slot is None or slot.source != "claude" or not slot.cwd:
            return None
        bundle = slot.terminal.get("bundle", "")
        tty = slot.terminal.get("tty", "")
        if bundle in ("com.microsoft.VSCode", "com.microsoft.VSCodeInsiders"):
            if os.path.isdir(slot.cwd):
                self._act(f"focus VS Code {slot.cwd}", ["open", "-b", bundle, slot.cwd])
                return None
            return None
        if bundle == "com.apple.Terminal":
            script = FOCUS_TERMINAL
        elif bundle == "com.googlecode.iterm2":
            script = FOCUS_ITERM
        else:
            return None  # Ghostty / WezTerm / unknown: selecting the slot is enough
        if tty and TTY_RE.match(tty):
            self._act(f"focus {TERMINAL_APPS[bundle]} tab {tty}", ["osascript", "-e", script, tty])
        else:
            self._act(f"activate {TERMINAL_APPS[bundle]}", ["open", "-b", bundle])
        return None

    def open_log(self, slot: Slot | None) -> str:
        if slot is None:
            return "empty slot"
        path = slot.log_path
        if not path:
            return "no log for slot"
        log.info("log for %s: %s", slot.key, path)
        self.out(f"log: {path}")
        if not os.path.exists(path):
            return "log missing"
        # Transcripts can be huge: reveal them in Finder; open text logs in the editor.
        args = ["open", "-R", path] if path.endswith(".jsonl") else ["open", "-t", path]
        self._act(f"open log {path}", args)
        return os.path.basename(path)
