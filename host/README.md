# host

```sh
uv tool install ./host
frostbite-daemon
frostbite-ctl hooks --hook "$(which frostbite-hook)"
```

Paste the hooks output into `~/.claude/settings.json`.

Try it with no pad: `frostbite-daemon --fake`
