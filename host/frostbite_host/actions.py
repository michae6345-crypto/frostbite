from __future__ import annotations

import logging
import os
import re
import subprocess
from typing import Callable

from .state import Slot

log = logging.getLogger("frostbite.actions")

APP_NAMES = {
    "com.apple.Terminal": "Terminal",
    "com.googlecode.iterm2": "iTerm2",
    "com.mitchellh.ghostty": "Ghostty",
    "com.github.wez.wezterm": "WezTerm",
    "com.microsoft.VSCode": "VS Code",
    "com.microsoft.VSCodeInsiders": "VS Code",
}
VSCODE_BUNDLES = ("com.microsoft.VSCode", "com.microsoft.VSCodeInsiders")
ESCAPE_KEY_CODE = 53
TTY_RE = re.compile(r"^/dev/tty[a-z]?\d+$")

TAP_FIRST = "tap slot first"
USE_TERMINAL = "answer in terminal"

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

READ_TTY = {
    "com.apple.Terminal": 'tell application "Terminal" to get tty of selected tab of front window',
    "com.googlecode.iterm2": 'tell application "iTerm2" to get tty of current session of current window',
}

_PRESS = """
on run argv
  set wantBundle to item 1 of argv
  set wantTty to item 2 of argv
  tell application "System Events" to set frontBundle to bundle identifier of first application process whose frontmost is true
  if frontBundle is not wantBundle then return "refused"
  {read_tty}
  if frontTty is not wantTty then return "refused"
  tell application "System Events" to key code 53
  return "sent"
end run
"""
PRESS_ESCAPE = {
    "com.apple.Terminal": _PRESS.format(
        read_tty='tell application "Terminal" to set frontTty to tty of selected tab of front window'),
    "com.googlecode.iterm2": _PRESS.format(
        read_tty='tell application "iTerm2" to set frontTty to tty of current session of current window'),
}

FRONTMOST_SCRIPT = ('tell application "System Events" to get bundle identifier of '
                    'first application process whose frontmost is true')


class Actions:
    # escape is the only real keystroke. it only goes out if the session is provably in front
    def __init__(self, dry_run: bool = False,
                 runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
                 out: Callable[[str], None] = print):
        self.dry_run = dry_run
        self.runner = runner
        self.out = out

    def _run(self, args: list[str], timeout: float = 3.0) -> subprocess.CompletedProcess | None:
        try:
            return self.runner(args, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as e:
            log.warning("command failed %s: %s", args[0], e)
            return None

    def _act(self, what: str, args: list[str]) -> subprocess.CompletedProcess | None:
        if self.dry_run:
            self.out(f"[dry-run] ACTION {what}: {' '.join(args)}")
            log.info("ACTION (dry-run) %s", what)
            return None
        log.info("ACTION %s", what)
        r = self._run(args)
        if r is None or r.returncode != 0:
            log.warning("ACTION %s failed: %s", what, (r.stderr.strip() if r else "no result"))
        return r

    def frontmost(self) -> str:
        r = self._run(["lsappinfo", "front"], timeout=1.0)
        asn = r.stdout.strip() if r and r.returncode == 0 else ""
        if asn:
            r = self._run(["lsappinfo", "info", "-only", "bundleid", asn], timeout=1.0)
            m = re.search(r'"CFBundleIdentifier"\s*=\s*"([^"]+)"', r.stdout if r else "")
            if m:
                return m.group(1)
        r = self._run(["osascript", "-e", FRONTMOST_SCRIPT], timeout=2.0)
        return r.stdout.strip() if r and r.returncode == 0 else ""

    def front_tty(self, bundle: str) -> str:
        r = self._run(["osascript", "-e", READ_TTY[bundle]], timeout=2.0)
        return r.stdout.strip() if r and r.returncode == 0 else ""

    def guarded_escape(self, slot: Slot | None, why: str) -> tuple[bool | None, str]:
        terminal = slot.terminal if slot else {}
        bundle = terminal.get("bundle", "")
        tty = terminal.get("tty", "")
        if bundle not in PRESS_ESCAPE or not TTY_RE.match(tty) or terminal.get("tmux"):
            log.info("ACTION refused escape (%s): session cannot be proved (bundle %r, tty %r, tmux %r)",
                     why, bundle, tty, terminal.get("tmux"))
            return False, USE_TERMINAL
        front = self.frontmost()
        if front != bundle:
            log.info("ACTION refused escape (%s): frontmost app is %r, session runs in %s",
                     why, front or "unknown", bundle)
            return False, TAP_FIRST
        front_tty = self.front_tty(bundle)
        if front_tty != tty:
            log.info("ACTION refused escape (%s): focused tab is %r, session is on %s",
                     why, front_tty or "unknown", tty)
            return False, TAP_FIRST
        if self.frontmost() != bundle:
            log.info("ACTION refused escape (%s): focus moved during the check", why)
            return False, TAP_FIRST
        what = f"{why}: key escape -> {APP_NAMES[bundle]} {tty}"
        if self.dry_run:
            self.out(f"[dry-run] ACTION {what}: key code {ESCAPE_KEY_CODE}")
            log.info("ACTION (dry-run) %s", what)
            return True, why
        r = self._act(what, ["osascript", "-e", PRESS_ESCAPE[bundle], bundle, tty])
        if r is None:
            return None, "keystroke unknown"
        if r.returncode != 0:
            return False, "keystroke failed"
        if r.stdout.strip() == "sent":
            return True, why
        log.info("ACTION refused escape (%s): focus moved at the keystroke", why)
        return False, TAP_FIRST

    def focus(self, slot: Slot | None) -> str | None:
        if slot is None or slot.source != "claude" or not slot.cwd:
            return None
        bundle = slot.terminal.get("bundle", "")
        tty = slot.terminal.get("tty", "")
        if bundle in VSCODE_BUNDLES:
            if os.path.isdir(slot.cwd):
                self._act(f"focus VS Code {slot.cwd}", ["open", "-b", bundle, slot.cwd])
            return None
        if bundle == "com.apple.Terminal":
            script = FOCUS_TERMINAL
        elif bundle == "com.googlecode.iterm2":
            script = FOCUS_ITERM
        else:
            return None
        if tty and TTY_RE.match(tty):
            r = self._act(f"focus {APP_NAMES[bundle]} tab {tty}", ["osascript", "-e", script, tty])
            if r is not None and r.stdout.strip() == "notfound":
                return "tab not found"
        else:
            self._act(f"activate {APP_NAMES[bundle]}", ["open", "-b", bundle])
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
        args = ["open", "-R", path] if path.endswith(".jsonl") else ["open", "-t", path]
        self._act(f"open log {path}", args)
        return os.path.basename(path)
