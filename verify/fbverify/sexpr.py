"""Minimal S-expression reader for KiCad files (.kicad_pcb, kicadsexpr netlists)."""
from __future__ import annotations

import math
import re

_TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse(text: str):
    stack, cur = [], []
    for m in _TOK.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif t.startswith('"'):
            cur.append(Str(t[1:-1].replace('\\"', '"').replace("\\\\", "\\")))
        else:
            cur.append(t)
    if stack:
        raise ValueError("unbalanced S-expression")
    return cur[0] if len(cur) == 1 else cur


class Str(str):
    """Quoted string (kept distinct from bare atoms)."""


def head(node):
    return node[0] if isinstance(node, list) and node else None


def children(node, name):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == name] if isinstance(node, list) else []


def child(node, name):
    c = children(node, name)
    return c[0] if c else None


def walk(node):
    if isinstance(node, list):
        yield node
        for c in node[1:]:
            yield from walk(c)


def num(x) -> float:
    return float(x)


# ---------------------------------------------------------------- PCB model

def _rot(px, py, deg):
    """KiCad: y down, positive angle = counter-clockwise on screen."""
    a = math.radians(deg)
    return px * math.cos(a) + py * math.sin(a), -px * math.sin(a) + py * math.cos(a)


def _net_name(pad):
    n = child(pad, "net")
    if n is None:
        return None
    # KiCad <=9: (net 3 "GND"); KiCad 10 may write (net "GND")
    vals = [v for v in n[1:] if not isinstance(v, list)]
    strs = [v for v in vals if isinstance(v, Str)]
    if strs:
        return str(strs[-1])
    return str(vals[-1]) if vals else None


def _graphic_points(g):
    pts = []
    for key in ("start", "end", "mid", "center"):
        c = child(g, key)
        if c is not None and len(c) >= 3:
            pts.append((num(c[1]), num(c[2])))
    pl = child(g, "pts")
    if pl is not None:
        for xy in children(pl, "xy"):
            pts.append((num(xy[1]), num(xy[2])))
    return pts


def _arc_points(start, mid, end, n=64):
    (x1, y1), (x2, y2), (x3, y3) = start, mid, end
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-12:
        return [start, mid, end]
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    a1, a2, a3 = (math.atan2(y - uy, x - ux) for x, y in (start, mid, end))

    def norm(a):
        return a % (2 * math.pi)
    # go from a1 to a3 through a2
    ccw_span = norm(a3 - a1)
    if norm(a2 - a1) <= ccw_span:
        span = ccw_span
    else:
        span = ccw_span - 2 * math.pi
    return [(ux + r * math.cos(a1 + span * i / n), uy + r * math.sin(a1 + span * i / n)) for i in range(n + 1)]


def _edge_points(g):
    h = head(g)
    s, e, m, c = (child(g, k) for k in ("start", "end", "mid", "center"))
    P = lambda n: (num(n[1]), num(n[2]))  # noqa: E731
    if h in ("gr_arc", "fp_arc") and s is not None and m is not None and e is not None:
        return _arc_points(P(s), P(m), P(e))
    if h in ("gr_circle", "fp_circle") and c is not None and e is not None:
        cx, cy = P(c)
        r = math.hypot(P(e)[0] - cx, P(e)[1] - cy)
        return [(cx - r, cy - r), (cx + r, cy + r)]
    if h in ("gr_rect", "fp_rect") and s is not None and e is not None:
        return [P(s), P(e)]
    return _graphic_points(g)


def layer_of(node):
    l = child(node, "layer")
    return str(l[1]) if l is not None and len(l) > 1 else None


def load_pcb(text: str) -> dict:
    tree = parse(text)
    layers = []
    L = child(tree, "layers")
    if L is not None:
        for entry in L[1:]:
            if isinstance(entry, list) and len(entry) >= 3:
                layers.append({"id": str(entry[0]), "name": str(entry[1]), "type": str(entry[2])})
    edge_pts = []
    for g in tree[1:]:
        if isinstance(g, list) and head(g) in ("gr_line", "gr_arc", "gr_rect", "gr_circle", "gr_poly", "gr_curve") \
                and layer_of(g) == "Edge.Cuts":
            edge_pts += _edge_points(g)
    fps = []
    for fp in children(tree, "footprint") + children(tree, "module"):
        lib = str(fp[1]) if len(fp) > 1 and not isinstance(fp[1], list) else ""
        at = child(fp, "at")
        x, y = num(at[1]), num(at[2])
        rot = num(at[3]) if len(at) > 3 and not isinstance(at[3], list) else 0.0
        ref = val = None
        for prop in children(fp, "property"):
            if str(prop[1]) == "Reference":
                ref = str(prop[2])
            elif str(prop[1]) == "Value":
                val = str(prop[2])
        for t in children(fp, "fp_text"):
            if str(t[1]) == "reference" and ref is None:
                ref = str(t[2])
            if str(t[1]) == "value" and val is None:
                val = str(t[2])
        pads = []
        for pad in children(fp, "pad"):
            pat = child(pad, "at")
            lx, ly = num(pat[1]), num(pat[2])
            dx, dy = _rot(lx, ly, rot)
            pf = child(pad, "pinfunction")
            sz = child(pad, "size")
            w, h = (num(sz[1]), num(sz[2])) if sz is not None and len(sz) > 2 else (0.0, 0.0)
            pa = num(pat[3]) if len(pat) > 3 and not isinstance(pat[3], list) else rot
            lay = child(pad, "layers")
            a = 0.0 if (len(pad) > 3 and str(pad[3]) == "circle") else math.radians(pa)
            hw = (abs(w * math.cos(a)) + abs(h * math.sin(a))) / 2
            hh = (abs(w * math.sin(a)) + abs(h * math.cos(a))) / 2
            dr = child(pad, "drill")
            off = child(dr, "offset") if dr is not None else None
            if off is not None:
                # copper is shifted by the drill offset; its direction on flipped footprints is easy to get
                # wrong, so cover both signs (conservative for clearance checks)
                ox, oy = num(off[1]), num(off[2])
                hw += abs(ox * math.cos(a)) + abs(oy * math.sin(a))
                hh += abs(ox * math.sin(a)) + abs(oy * math.cos(a))
            pads.append({"num": str(pad[1]), "x": x + dx, "y": y + dy, "net": _net_name(pad),
                         "pinfunction": str(pf[1]) if pf is not None else None,
                         "type": str(pad[2]) if len(pad) > 2 else None, "shape": str(pad[3]) if len(pad) > 3 else None,
                         "w": w, "h": h, "angle": pa, "hw": hw, "hh": hh,
                         "layers": [str(v) for v in lay[1:]] if lay is not None else []})
        graphics = []
        for g in fp[1:]:
            if isinstance(g, list) and head(g) in ("fp_line", "fp_rect", "fp_poly", "fp_arc", "fp_circle"):
                pts = [(x + _rot(px, py, rot)[0], y + _rot(px, py, rot)[1]) for px, py in _edge_points(g)]
                graphics.append({"kind": head(g), "layer": layer_of(g), "pts": pts})
        fps.append({"lib": lib, "ref": ref, "value": val, "x": x, "y": y, "rot": rot,
                    "layer": layer_of(fp), "pads": pads, "graphics": graphics})
    texts = []
    for t in children(tree, "gr_text"):
        texts.append({"text": str(t[1]), "layer": layer_of(t)})
    for fp in children(tree, "footprint"):
        for t in children(fp, "fp_text"):
            texts.append({"text": str(t[2]) if len(t) > 2 else "", "layer": layer_of(t)})
    return {"layers": layers, "edge_pts": edge_pts, "footprints": fps, "texts": texts}


def load_netlist(text: str) -> dict:
    tree = parse(text)
    comps = {}
    cs = child(tree, "components")
    for c in children(cs, "comp") if cs is not None else []:
        ref = str(child(c, "ref")[1])
        g = lambda k: (str(child(c, k)[1]) if child(c, k) is not None and len(child(c, k)) > 1 else "")  # noqa: E731
        ls = child(c, "libsource")
        lib = " ".join(str(x[1]) for x in ls[1:] if isinstance(x, list)) if ls is not None else ""
        comps[ref] = {"ref": ref, "value": g("value"), "footprint": g("footprint"), "lib": lib}
    nets = {}
    ns = child(tree, "nets")
    for n in children(ns, "net") if ns is not None else []:
        name = str(child(n, "name")[1])
        nodes = []
        for nd in children(n, "node"):
            pf = child(nd, "pinfunction")
            nodes.append({"ref": str(child(nd, "ref")[1]), "pin": str(child(nd, "pin")[1]),
                          "pinfunction": str(pf[1]) if pf is not None else None})
        nets[name] = nodes
    return {"components": comps, "nets": nets}
