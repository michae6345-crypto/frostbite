"""Minimal S-expression reader/writer for KiCad files (strings keep their quotes)."""
from __future__ import annotations


class Q(str):
    """A quoted string atom."""


def parse(text: str):
    i, n = 0, len(text)
    stack, cur = [], []
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "(":
            stack.append(cur)
            cur = []
            i += 1
        elif c == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j:j + 2])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            cur.append(Q("".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            cur.append(text[i:j])
            i = j
    assert not stack
    return cur[0] if len(cur) == 1 else cur


def dump(e, ind=0) -> str:
    if isinstance(e, Q):
        return '"' + str(e) + '"'
    if isinstance(e, str):
        return e
    if isinstance(e, (int, float)):
        return fmt(e)
    simple = all(not isinstance(x, list) for x in e)
    if simple:
        return "(" + " ".join(dump(x) for x in e) + ")"
    pad = "\t" * (ind + 1)
    parts = []
    head = []
    for x in e:
        if isinstance(x, list):
            parts.append("\n" + pad + dump(x, ind + 1))
        elif not parts:
            head.append(dump(x))
        else:
            parts.append("\n" + pad + dump(x))
    return "(" + " ".join(head) + "".join(parts) + "\n" + "\t" * ind + ")"


def fmt(v) -> str:
    if isinstance(v, int):
        return str(v)
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def find(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]


def find1(e, key):
    r = find(e, key)
    return r[0] if r else None


def walk(e):
    yield e
    for x in e:
        if isinstance(x, list):
            yield from walk(x)
