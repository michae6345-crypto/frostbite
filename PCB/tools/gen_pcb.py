"""Build PCB/frostbite.kicad_pcb from design.json + the exported schematic netlist, then route it.

Run with KiCad's bundled Python (it has the pcbnew module):
  PY=~/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
  $PY PCB/tools/gen_pcb.py place    # new board: outline, footprints, nets, silkscreen -> build/frostbite.dsn
  $PY PCB/tools/gen_pcb.py route    # Freerouting on build/frostbite.dsn, import SES, GND zones, fill, save

Placement rules (all positions in design.json PCB coordinates, mm, origin top-left, y down):
  SWn   switch centre = keys[n-1].(x, y)
  Dn    vertical in the 5 mm gap right of its switch, centre (x + 9.525, y), anode (pad 2) up
  LEDn  per-key: reverse-mount MINI-E under the switch's LED window, (x, y + 5.08)
        glow : leds.glow[].(x, y), on the bottom side, lens facing down
  U1    XIAO on the bottom side, rect centre (mcu.rect), USB-C edge flush with y = 0
  ENC1  shaft centre = encoder.(x, y)
  J1    pin 1 at (oled.header.pin_row_x, centre_y - 1.5 * pitch), pins downward
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).parent))
from sexp import find, find1, parse  # noqa: E402

PCB = Path(__file__).resolve().parents[1]
ROOT = PCB.parent
BUILD = PCB / "build"
BOARD = PCB / "frostbite.kicad_pcb"
D = json.loads((ROOT / "design.json").read_text())
STDFP = Path.home() / "Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
LIBPATH = {"hackpad": PCB / "lib/hackpad.pretty", "frostbite": PCB / "lib/frostbite.pretty"}
FREEROUTING = Path.home() / ".local/share/freerouting/freerouting-2.5.0.jar"

W, H = D["pcb"]["w"], D["pcb"]["h"]
CORNER_R = 1.0
LED_KEY_DY = 5.08          # MX LED window: switch centre + (0, +5.08)
# design.json glow LEDs at y 26 / 80 put their courtyards on top of SW3's pad 2 and the row-2
# per-key LEDs.  Moved the minimum needed (kept symmetric); reported to the lead.
GLOW_Y = {26.0: 25.4, 80.0: 80.6}
ROUTE_CLEARANCE_UM = 300
MIN_SIGNAL_TRACK = 0.2     # brief: >= 0.2 mm signal tracks
ENC_ROT = 90               # A/C/B row toward the keys (y = 20.5), clear of the OLED header J1


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


# ---------------------------------------------------------------- placement table
def targets():
    """ref -> dict(x, y, rot, bottom). Coordinates are where the footprint origin goes."""
    t = {}
    for k, key in enumerate(D["keys"], start=1):
        x, y = key["x"], key["y"]
        t[f"SW{k}"] = dict(x=x, y=y, rot=0, bottom=False)
        # diode footprint origin = pad 1 (cathode); rotated 90 deg pad 2 sits 7.62 above it
        t[f"D{k}"] = dict(x=x + 9.525, y=y + 3.81, rot=90, bottom=False)
        t[f"LED{key['led'] + 1}"] = dict(x=x, y=y + LED_KEY_DY, rot=0, bottom=False)
    for g in D["leds"]["glow"]:
        t[f"LED{g['led'] + 1}"] = dict(x=g["x"], y=GLOW_Y.get(g["y"], g["y"]), rot=0, bottom=True)
    r = D["mcu"]["rect"]
    t["U1"] = dict(x=r["x"] + r["w"] / 2, y=r["y"] + r["h"] / 2, rot=0, bottom=True)
    e = D["encoder"]
    t["ENC1"] = dict(x=e["x"], y=e["y"], rot=ENC_ROT, bottom=False, centre="MP")  # shaft = MP midpoint
    h = D["oled"]["header"]
    t["J1"] = dict(x=h["pin_row_x"], y=h["centre_y"] - 1.5 * h["pitch"], rot=0, bottom=False)
    return t


def read_netlist():
    nl = parse((BUILD / "frostbite.net").read_text())
    comps = {}
    for c in find(find1(nl, "components"), "comp"):
        comps[str(find1(c, "ref")[1])] = dict(value=str(find1(c, "value")[1]),
                                              footprint=str(find1(c, "footprint")[1]),
                                              uuid=str(find1(c, "tstamps")[1]))
    nets = {}
    for n in find(find1(nl, "nets"), "net"):
        name = str(find1(n, "name")[1])
        for node in find(n, "node"):
            nets[(str(find1(node, "ref")[1]), str(find1(node, "pin")[1]))] = name
    return comps, nets


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = LIBPATH.get(lib, STDFP / f"{lib}.pretty")
    fp = pcbnew.FootprintLoad(str(path), name)
    assert fp is not None, fpid
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


# ---------------------------------------------------------------- graphics helpers
def seg(board, layer, a, b, width=0.15):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(pt(*a))
    s.SetEnd(pt(*b))
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    board.Add(s)


def arc(board, layer, centre, start, angle_deg, width=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(pt(*centre))
    s.SetStart(pt(*start))
    s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle_deg, pcbnew.DEGREES_T), True)
    s.SetLayer(layer)
    s.SetWidth(mm(width))
    board.Add(s)


def text(board, layer, s, x, y, size=1.5, thick=0.25, mirror=False, angle=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(pt(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(thick))
    t.SetMirrored(mirror)
    t.SetTextAngleDegrees(angle)
    board.Add(t)


def outline(board):
    r, L = CORNER_R, pcbnew.Edge_Cuts
    seg(board, L, (r, 0), (W - r, 0), 0.1)
    seg(board, L, (W, r), (W, H - r), 0.1)
    seg(board, L, (W - r, H), (r, H), 0.1)
    seg(board, L, (0, H - r), (0, r), 0.1)
    arc(board, L, (W - r, r), (W - r, 0), 90)
    arc(board, L, (W - r, H - r), (W, H - r), 90)
    arc(board, L, (r, H - r), (r, H), 90)
    arc(board, L, (r, r), (0, r), 90)


def snowflake(board, layer, cx, cy, R, width=0.2):
    """Six-armed snowflake: spokes with two pairs of branches each."""
    for k in range(6):
        a = math.radians(90 + 60 * k)
        ux, uy = math.cos(a), -math.sin(a)
        seg(board, layer, (cx, cy), (cx + R * ux, cy + R * uy), width)
        for f, bl in ((0.45, 0.32), (0.72, 0.22)):
            bx, by = cx + f * R * ux, cy + f * R * uy
            for s in (-1, 1):
                b = a + s * math.radians(45)
                seg(board, layer, (bx, by), (bx + bl * R * math.cos(b), by - bl * R * math.sin(b)), width)


# ---------------------------------------------------------------- place
def place():
    comps, nets = read_netlist()
    tg = targets()
    assert set(comps) == set(tg), (set(comps) ^ set(tg))
    board = pcbnew.NewBoard(str(BOARD))
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(1.6))

    outline(board)

    netitems = {}
    for name in sorted(set(nets.values())):
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        netitems[name] = ni

    sheetfile = "frostbite.kicad_sch"
    for ref in sorted(comps, key=lambda r: (r.rstrip("0123456789"), int("0" + "".join(c for c in r if c.isdigit())))):
        c, p = comps[ref], tg[ref]
        fp = load_fp(c["footprint"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetPath(pcbnew.KIID_PATH("/" + c["uuid"]))
        fp.SetSheetname("/")
        fp.SetSheetfile(sheetfile)
        board.Add(fp)
        fp.SetPosition(pt(p["x"], p["y"]))
        fp.SetOrientationDegrees(p["rot"])
        if p["bottom"]:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if p.get("centre"):  # put the midpoint of the named pads on the target
            pads = [q for q in fp.Pads() if q.GetNumber() == p["centre"]]
            cx = sum(q.GetPosition().x for q in pads) / len(pads)
            cy = sum(q.GetPosition().y for q in pads) / len(pads)
            fp.Move(pcbnew.VECTOR2I(int(round(mm(p["x"]) - cx)), int(round(mm(p["y"]) - cy))))
        for pad in fp.Pads():
            key = (ref, pad.GetNumber())
            if key in nets:
                pad.SetNet(netitems[nets[key]])
        ref_t = fp.Reference()
        ref_t.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
        ref_t.SetTextThickness(mm(0.15))
        if ref.startswith("LED"):
            # LEDs are soldered from the underside: label them on B.Silkscreen, clear of the
            # switch holes (per-key: below the LED; glow: toward the board's centre line)
            ref_t.SetLayer(pcbnew.B_SilkS)
            ref_t.SetMirrored(True)
            ref_t.SetTextAngleDegrees(0)
            if p["bottom"]:
                dy = 3.0 if p["y"] < H / 2 else -3.0
                ref_t.SetPosition(pt(p["x"], p["y"] + dy))
            else:
                ref_t.SetPosition(pt(p["x"], p["y"] + 2.4))
        if ref == "U1":   # castellated GND pad: solid connection to the pour
            for q in fp.Pads():
                if q.GetNumber() == "13":
                    q.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
        fp.Value().SetVisible(False)

    # ---- silkscreen
    F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
    text(board, F, "FROSTBITE", 39.0, 3.2, size=1.6, thick=0.28)
    snowflake(board, F, 55.6, 3.4, 2.4)
    text(board, B, "FROSTBITE", W / 2, 43.4, size=3.0, thick=0.45, mirror=True)
    text(board, B, "Frostbite 9  rev A  Hack Club Hackpad", W / 2, 61.9, size=1.0, thick=0.15, mirror=True)
    snowflake(board, B, 8.0, 43.4, 2.4)
    snowflake(board, B, W - 8.0, 43.4, 2.4)
    r = D["mcu"]["rect"]
    text(board, B, "XIAO HERE", r["x"] + r["w"] / 2, r["y"] + r["h"] + 1.6, size=1.2, thick=0.2, mirror=True)
    text(board, B, "USB-C", r["x"] + r["w"] / 2, 3.0, size=1.0, thick=0.15, mirror=True)

    pcbnew.SaveBoard(str(BOARD), board)
    BUILD.mkdir(exist_ok=True)
    dsn = BUILD / "frostbite.dsn"
    ok = pcbnew.ExportSpecctraDSN(board, str(dsn))
    # Route with 0.3 mm clearance (DRC rule is 0.2): Freerouting treats board edges and the LED
    # cut-outs with the net clearance, and the board's copper-to-edge rule is 0.3 mm.
    dsn_text = dsn.read_text()
    dsn_text = re.sub(r"\(clearance (\d+)\)", lambda m: f"(clearance {max(int(m.group(1)), ROUTE_CLEARANCE_UM)})", dsn_text)
    dsn.write_text(dsn_text)
    print("placed", len(comps), "footprints; DSN export", ok)
    report_positions(board)


def report_positions(board):
    """Max deviation of switch / encoder / header / LED / XIAO positions from design.json."""
    worst = 0.0
    rows = []
    want = {f"SW{k}": (key["x"], key["y"]) for k, key in enumerate(D["keys"], start=1)}
    want["ENC1"] = (D["encoder"]["x"], D["encoder"]["y"])
    for g in D["leds"]["glow"]:
        want[f"LED{g['led'] + 1}"] = (g["x"], g["y"])
    for key in D["keys"]:
        want[f"LED{key['led'] + 1}"] = (key["x"], key["y"] + LED_KEY_DY)
    r = D["mcu"]["rect"]
    want["U1"] = (r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref == "ENC1":   # shaft centre = midpoint of the two mounting lugs
            mp = [p for p in fp.Pads() if p.GetNumber() == "MP"]
            c = ((mp[0].GetPosition().x + mp[1].GetPosition().x) / 2, (mp[0].GetPosition().y + mp[1].GetPosition().y) / 2)
            got = (pcbnew.ToMM(c[0]), pcbnew.ToMM(c[1]))
        else:
            got = (pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y))
        if ref in want:
            d = math.dist(got, want[ref])
            worst = max(worst, d)
            rows.append(f"{ref}: {got} want {want[ref]} d={d:.4f}")
    j1 = board.FindFootprintByReference("J1")
    pads = sorted(j1.Pads(), key=lambda p: int(p.GetNumber()))
    ys = [pcbnew.ToMM(p.GetPosition().y) for p in pads]
    xs = {round(pcbnew.ToMM(p.GetPosition().x), 4) for p in pads}
    h = D["oled"]["header"]
    jd = max(abs(sum(ys) / 4 - h["centre_y"]), max(abs(x - h["pin_row_x"]) for x in xs))
    worst = max(worst, jd)
    rows.append(f"J1 pins x={xs} y={ys} (centre {sum(ys) / 4:.3f}) d={jd:.4f}")
    u1 = board.FindFootprintByReference("U1")
    print("U1 side:", "bottom" if u1.IsFlipped() else "top")
    print("\n".join(rows))
    print(f"max position deviation vs design.json: {worst:.4f} mm")


def keepout(board, name, x0, y0, x1, y1):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetZoneName(name)
    z.SetLayerSet(pcbnew.LSET.AllCuMask(2))
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetDoNotAllowZoneFills(False)   # the GND pour keeps its own 0.3 mm edge clearance
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        ol.Append(mm(x), mm(y))
    board.Add(z)


def add_keepouts(board):
    """Track/via keep-outs so Freerouting honours the 0.3 mm copper-to-edge rule: a band along
    the outline and a box around every SK6812 cut-out (cut-out +-1.75 x -1.67..1.47, plus 0.35)."""
    b = 0.45
    keepout(board, "edge_top", 0, 0, W, b)
    keepout(board, "edge_bottom", 0, H - b, W, H)
    keepout(board, "edge_left", 0, 0, b, H)
    keepout(board, "edge_right", W - b, 0, W, H)
    for fp in board.GetFootprints():
        if fp.GetReference().startswith("LED"):
            x, y = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
            keepout(board, f"cutout_{fp.GetReference()}", x - 2.1, y - 2.05, x + 2.1, y + 1.85)


# ---------------------------------------------------------------- route
def route():
    dsn, ses = BUILD / "frostbite.dsn", BUILD / "frostbite.ses"
    if ses.exists():
        ses.unlink()
    cmd = ["java", "-jar", str(FREEROUTING), "-de", str(dsn), "-do", str(ses), "-mp", "100"]
    print(" ".join(cmd))
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    (BUILD / "freerouting.log").write_text(p.stdout + p.stderr)
    assert ses.exists(), "Freerouting produced no SES (see build/freerouting.log)"
    board = pcbnew.LoadBoard(str(BOARD))
    ok = pcbnew.ImportSpecctraSES(board, str(ses))
    print("SES import", ok)
    # Freerouting necks tracks down (x0.75) near obstacles; restore the 0.2 mm signal minimum.
    widened = 0
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetWidth() < mm(MIN_SIGNAL_TRACK):
            t.SetWidth(mm(MIN_SIGNAL_TRACK))
            widened += 1
    print("widened", widened, "neck-down segments to", MIN_SIGNAL_TRACK, "mm")
    add_zones(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(BOARD), board)
    print("tracks", len(board.GetTracks()))


def add_zones(board):
    gnd = board.FindNet("GND")
    for z in list(board.Zones()):
        if not z.GetIsRuleArea():
            board.Remove(z)
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        z.SetIsRuleArea(False)
        z.SetLocalClearance(mm(0.3))
        z.SetMinThickness(mm(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)  # SMD LED pads solid, THT thermal
        z.SetThermalReliefGap(mm(0.3))
        z.SetThermalReliefSpokeWidth(mm(0.4))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in ((0, 0), (W, 0), (W, H), (0, H)):
            ol.Append(mm(x), mm(y))
        board.Add(z)


if __name__ == "__main__":
    {"place": place, "route": route, "report": lambda: report_positions(pcbnew.LoadBoard(str(BOARD)))}[sys.argv[1]]()
