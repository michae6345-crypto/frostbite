#!/usr/bin/env python3
"""How long does the real frostbite-hook hold up Claude Code? Hooks are synchronous by default.
Usage (from host/): uv run --frozen python ../docs/audit/round2-tests/hook_latency.py <scratch dir>"""
import json, os, shutil, socket, statistics, subprocess, sys, tempfile, threading, time
scratch = sys.argv[1]
d = tempfile.mkdtemp(dir=scratch)
os.chdir(d)  # AF_UNIX paths are limited to 104 bytes, so bind relative to the scratch dir
sock = "f.sock"
env = {**os.environ, "FROSTBITE_DIR": ".", "FROSTBITE_SOCKET": sock, "PYTHONDONTWRITEBYTECODE": "1",
       "PYTHONPATH": os.path.dirname(os.path.dirname(os.path.abspath(__import__("frostbite_host").__file__)))}
hook = [sys.executable, "-m", "frostbite_host.hook"]
ev = lambda name, **kw: json.dumps({"hook_event_name": name, "session_id": "s", "cwd": "/tmp/p", **kw})
def run(payload, keep_open=0.0):
    t = time.perf_counter()
    p = subprocess.Popen(hook, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    epipe = False
    try:
        p.stdin.write(payload.encode()); p.stdin.flush()
    except BrokenPipeError:
        epipe = True
    if keep_open:  # stdin stays open: time the hook's own exit, not this sleep
        rc = p.wait(timeout=keep_open)
        return time.perf_counter() - t, rc, b"", epipe
    try:
        p.stdin.close()
    except BrokenPipeError:
        epipe = True
    out = p.stdout.read(); p.wait()
    return time.perf_counter() - t, p.returncode, out, epipe
def series(label, payload, n=15):
    r = [run(payload) for _ in range(n)]
    ts = sorted(x[0] * 1000 for x in r)
    print(f"{label:<44} median {statistics.median(ts):7.1f} ms  max {ts[-1]:7.1f} ms  rc={ {x[1] for x in r} } stdout_bytes={sum(len(x[2]) for x in r)}")
pre = ev("PreToolUse", tool_name="Bash", tool_input={"command": "ls"})
req = ev("PermissionRequest", tool_name="Bash", tool_input={"command": "ls"})
series("daemon absent, PreToolUse", pre)
series("daemon absent, PermissionRequest (ps lookup)", req)
# live listener that accepts and drains
s = socket.socket(socket.AF_UNIX); s.bind(sock); s.listen(64)
stop = threading.Event()
def drain():
    s.settimeout(0.2)
    while not stop.is_set():
        try:
            c, _ = s.accept(); c.recv(65536); c.close()
        except OSError:
            pass
th = threading.Thread(target=drain, daemon=True); th.start()
series("healthy listener, PreToolUse", pre)
stop.set(); th.join(); s.close(); os.unlink(sock)
# wedged daemon: bound, backlog 1, never accepts (a SIGSTOPped daemon looks like this)
s = socket.socket(socket.AF_UNIX); s.bind(sock); s.listen(1)
fill = []
for _ in range(8):
    c = socket.socket(socket.AF_UNIX); c.setblocking(False)
    try:
        c.connect(sock); fill.append(c)
    except OSError:
        break
print("backlog filled with", len(fill), "connections")
series("wedged daemon, backlog full", pre, 6)
s.close(); os.unlink(sock)
t, rc, out, _ = run(pre, keep_open=4.0)
print(f"stdin held open 4 s by the writer: {t*1000:.0f} ms rc={rc} (alarm is 2 s)")
big = ev("PostToolUse", tool_name="Bash", tool_input={"command": "ls"}, tool_response={"stdout": "x" * (20 << 20)})
t, rc, out, epipe = run(big)
print(f"20 MiB PostToolUse payload: {t*1000:.0f} ms rc={rc} writer_got_EPIPE={epipe} (over MAX_STDIN, message is dropped)")
shutil.rmtree(d, ignore_errors=True)
