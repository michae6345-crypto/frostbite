#!/bin/sh
# Regenerate everything in PCB/ from design.json and verify it with KiCad's own tools.
# usage: sh PCB/tools/build_all.sh      (from anywhere; macOS paths for KiCad 10)
set -eu
PCB="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(dirname "$PCB")"
K="$HOME/Applications/KiCad/KiCad.app/Contents"
CLI="$K/MacOS/kicad-cli"
PY="$K/Frameworks/Python.framework/Versions/Current/bin/python3"
cd "$PCB"
mkdir -p build images

echo "== libraries, lib tables, project file"
python3 tools/make_libs.py

echo "== schematic + ERC"
python3 tools/gen_schematic.py
"$CLI" sch erc --format json --severity-error --exit-code-violations -o build/erc.json frostbite.kicad_sch

echo "== netlist vs design.json / keyboard.json"
"$CLI" sch export netlist --format kicadsexpr -o build/frostbite.net frostbite.kicad_sch
python3 tools/check_netlist.py build/frostbite.net

echo "== placement + Freerouting"
"$PY" tools/gen_pcb.py place
"$PY" tools/gen_pcb.py route

echo "== DRC with schematic parity"
"$CLI" pcb drc --format json --severity-error --exit-code-violations --schematic-parity \
    -o build/drc.json frostbite.kicad_pcb

echo "== fabrication outputs"
rm -rf build/gerbers && mkdir -p build/gerbers
"$CLI" pcb export gerbers --no-protel-ext -l F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
    -o build/gerbers/ frostbite.kicad_pcb
"$CLI" pcb export drill --format excellon --excellon-separate-th --generate-map --map-format gerberx2 \
    -o build/gerbers/ frostbite.kicad_pcb
"$CLI" pcb export pos --format csv --units mm --side both -o build/frostbite-pos.csv frostbite.kicad_pcb
mkdir -p "$ROOT/production"
rm -f "$ROOT/production/gerbers.zip"
(cd build/gerbers && zip -q -X "$ROOT/production/gerbers.zip" ./*)

echo "== images"
"$CLI" sch export pdf -o build/schematic.pdf frostbite.kicad_sch
sips -s format png -Z 3000 build/schematic.pdf --out images/schematic.png >/dev/null
"$CLI" pcb export pdf --mode-single --scale 0 --bg-color "#ffffff" -l F.Cu,F.SilkS,F.Mask,Edge.Cuts \
    -o build/pcb_front.pdf frostbite.kicad_pcb
"$CLI" pcb export pdf --mode-single --scale 0 --bg-color "#ffffff" --mirror -l B.Cu,B.SilkS,B.Mask,Edge.Cuts \
    -o build/pcb_back.pdf frostbite.kicad_pcb
for s in front back; do sips -s format png -Z 2400 "build/pcb_$s.pdf" --out "images/pcb_$s.png" >/dev/null; done
"$CLI" pcb render --side top --width 1400 --height 1800 --quality high --background opaque -o images/pcb_render_top.png frostbite.kicad_pcb
"$CLI" pcb render --side bottom --width 1400 --height 1800 --quality high --background opaque -o images/pcb_render_bottom.png frostbite.kicad_pcb
"$CLI" pcb render --rotate "-40,0,30" --perspective --zoom 0.8 --width 1600 --height 1200 --quality high --background opaque \
    -o images/pcb_render_3d.png frostbite.kicad_pcb
echo "== done"
