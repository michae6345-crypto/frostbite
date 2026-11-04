#!/usr/bin/env python3
"""Reproduce how Claude Code 2.1.316 spawns a shell-form hook on macOS, with no hook installed.

Binary evidence: XCe(cmd, [], {env, cwd, shell:true, detached:true}) -> setsid + /bin/sh -c cmd.
Layout built here:  pty slave (stands in for the Terminal tab)
                    `- "claude" stand-in, session leader with that ctty
                       `- setsid child, /bin/sh -c '<hook>'     (no ctty, like detached:true)
Runs the REAL frostbite_host.hook.controlling_tty(). Usage: tty_probe.py
"""
import json, os, pty, select, shlex, subprocess, sys, tempfile, textwrap

py = sys.executable
inner = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
inner.write(textwrap.dedent(f"""\
    #!{py}
    import json, os, sys
    sys.dont_write_bytecode = True
    from frostbite_host import hook
    dev = None
    try:
        fd = os.open("/dev/tty", os.O_RDONLY | os.O_NOCTTY | os.O_NONBLOCK); dev = os.ttyname(fd); os.close(fd)
    except OSError as e:
        dev = "ERR " + str(e)
    print(json.dumps({{"pid": os.getpid(), "ppid": os.getppid(), "sid": os.getsid(0),
                       "dev_tty": dev, "controlling_tty": hook.controlling_tty()}}))
"""))
inner.close()
os.chmod(inner.name, 0o755)

launcher = textwrap.dedent(f"""\
    import os, subprocess, sys
    tty = os.ttyname(0)
    forms = {{
      "plain path (shipped snippet)": {shlex.quote(inner.name)!r},
      "path + redirect":   {shlex.quote(inner.name)!r} + " 2>/dev/null",
      "trailing true":     {shlex.quote(inner.name)!r} + "; true",
      "wrapped by uv run": "/bin/sh -c " + repr({inner.name!r}) + "; :",
    }}
    print("REAL_TTY", tty, flush=True)
    for shell in ("/bin/sh", "/bin/bash", "/bin/zsh"):
        for name, cmd in forms.items():
            p = subprocess.run([shell, "-c", cmd], start_new_session=True, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=10)
            print(shell, "|", name, "|", p.stdout.strip() or p.stderr.strip()[-160:], flush=True)
""")
pid, master = pty.fork()
if pid == 0:
    os.execv(py, [py, "-c", launcher])
buf = b""
while True:
    r, _, _ = select.select([master], [], [], 20)
    if not r:
        break
    try:
        d = os.read(master, 65536)
    except OSError:
        break
    if not d:
        break
    buf += d
os.waitpid(pid, 0)
print(buf.decode(errors="replace").replace("\r", ""))
os.unlink(inner.name)
