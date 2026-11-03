# Frostbite case (CAD)

Fully 3D-printed sandwich case, generated in CadQuery from `../design.json`. Nothing is laser-cut, CNC'd or acrylic.

![Frostbite case, exploded view](previews/exploded-iso.svg.png)

| File | What it is |
|---|---|
| `frostbite_case.py` | Builds every part from design.json and writes the exports below |
| `check_fit.py` | Fit and printability checks (gate G4). Rebuilds, re-exports, prints a table, exits 1 on any failure |
| `frostbite-assembly.step` | Full assembly on the desk (4° tilt): case parts, PCB slab, switches, keycaps, OLED, XIAO, EC11, LEDs |
| `positions.json` | Case feature centres in PCB coordinates, plus the case heights. Read by `verify/` |
| `previews/` | SVG line drawings (+ PNG): iso, exploded, top plan, left side, back (USB) |
| `../production/{Top,Bottom,GlowBand,Knob}.{step,stl}` | Print-ready parts, already in print orientation |

```sh
cd CAD && ~/.local/bin/uv venv --python 3.12 .venv && ~/.local/bin/uv pip install --python .venv -r requirements.txt
cd .. && CAD/.venv/bin/python CAD/frostbite_case.py     # parts, assembly, previews (~10 s)
CAD/.venv/bin/python CAD/check_fit.py                    # rebuild + all checks (~15 s)
```

## Parts

| Part | Material | Size | Notes |
|---|---|---|---|
| **Top** | iced (translucent) PETG | 75.15 × 97.15 × 16.0 | Integrated MX plate plus a solid skirt that hides the PCB edge. The plate is 1.5 mm at the 14.0 cutouts (15.4 clip pockets from below) and 2.5 mm elsewhere. Holds the 4 heat-set inserts. OLED window, EC11 opening, USB-C window. |
| **GlowBand** | clear / natural PETG | 74.15 × 96.15 × 2.0 ring | The visible light gap. It sits 0.5 mm behind the shell skin so it reads as a glowing line. Four light pads rise under the glow LEDs (top 2.6 below the PCB, 0.82 mm under each LED, clear of 2.0 mm lead tails), and a tongue forms the bottom edge of the USB window. |
| **Bottom** | iced PETG | 75.15 × 97.15, 3.1 (front) to 9.9 (back) | A 4° wedge tray with a 2.5 mm floor. It leaves a large open glow chamber under the PCB (XIAO and LEDs hang into it). Four screw bosses with Ø5.8 counterbores from underneath. |
| **Knob** (optional) | PETG | Ø18 × 15 | 30 vertical knurl ribs, D-bore Ø6.2 / 4.6 across the flat (0.1 mm clearance), 12.3 deep, marker dimple. Prints upright without supports. |

Assembled on a desk (from `positions.json`): top face **21.1 mm** at the front, **27.8 mm** at the back. Keycaps add about 13.6 mm and the knob top is at about 23 mm above the plate. Case bounding box 75.2 × 98.9 × 27.9 mm. The assembly with keycaps and knob is 75.2 × 98.9 × 49.5 mm, well under 200 × 200 × 100.

### Vertical stack (design frame, z = 0 at the PCB underside)

```
 +6.60  Top face = plate top (PCB top + 5.0, fixed by the MX switch)
 +5.10  plate underside at the clips (1.5)       +4.10 plate underside elsewhere (2.5)
 +3.00  screw tip (blind Ø3.4 hole ends at 3.4, 3.2 mm of skin above)
 0..1.6 PCB, in a pocket of PCB + 0.3 per side in every part (61.75 × 83.75)
 -0.30  top of the insert bosses (they tuck 1.0 mm under the PCB edge)
 -2.83  USB-C receptacle centre = centre of the 13.5 × 8 window
 -9.40  Top skirt bottom: inserts pressed in from here, 4 deep  | GlowBand top
-11.40  GlowBand bottom | Bottom rim
-13.00  screw head seat;  head bottom -16.0;  underside 0.3-4.6 below that (4° plane)
```

### Design decisions

- **Inserts in the Top, screws from underneath.** Hidden screws mean the thread has to be in the upper part, so the four inserts sit in the Top and the M3×16 heads sit in counterbores under the Bottom. The shell is only 7 mm wider than the PCB per side (75.15 vs 61.15), but a 4.7 mm insert needs 1.3 mm of wall around it. That cannot fit beside the PCB, and the R12 corners leave even less room (about 4.9 mm on the diagonal). So the inserts sit *below* the PCB, on the long side walls at the positions in `design.json` `case.screws.positions` (PCB y = 9.0 and 62.1, axis 3.0 mm outside the PCB edge). The bosses (`boss_od` 8.7) tuck 1.35 mm under the PCB edge with a 45° chamfer and a 0.3 mm air gap. They double as PCB rests.
- **Why the Top is 16 mm tall.** The four 4 mm inserts have to sit below the PCB. The 13.5 × 8 USB window then fits inside the skirt. M3×16 screws with fully recessed heads then set the depth of the Bottom: heads 0.3 mm or more below the underside at the front screws, and the wedge adds height toward the back. This also places a slicing plane of the verifier inside the 1.5 mm clip zone, so `verify` G4/X find the OLED window there.
- **EC11 opening.** The plate top is only 0.5 mm above the EC11 body (body 4.5 tall, plate 5.0 above the PCB). A bushing-sized Ø7.4 hole would need a plate above the body, so the opening clears the body instead: a 12.98 × 16.0 rounded rectangle (r 2), 0.64 mm from the body. The 18 mm knob covers it.
- **OLED.** On a 2.5 mm header the glass top ends 5.15 mm above the PCB, which is 0.15 mm proud of the plate. So the window is the design window + 0.3 per side (30.6 × 12.1), and a 38.6 × 12.6 recess from below holds the module board. That leaves a 1.0 mm lip over the board ends. **Trim the header pins flush on the module's top side.**
- **USB-C.** The window is centred on the receptacle (x 21.00, z −2.83). The Top has a notch down to its bottom edge, and the GlowBand tongue fills that notch, so the Top prints without a long bridge. The window size comes from design.json (`case.usb_cutout`, now 13.5 × 8.0). That gives 0.5 mm per side around a 12.5 × 7 overmold.
- **Glow.** The SK6812 glow LEDs face down from the PCB underside. The band's pads sit 0.82 mm under each LED and carry the light into the 2 mm band, which is lit all the way round. The open chamber under the PCB scatters the rest of the light into the translucent Bottom.

## Print settings

PETG, 0.4 mm nozzle, 240 °C / bed 80 °C, 4 perimeters, 25 % gyroid, **no supports on any part**.

| Part | Orientation (as exported) | Layer | Notes |
|---|---|---|---|
| Top | top face down on textured PEI (gives a frosted face) | 0.2 (0.16 for nicer cutouts) | Skirt, pockets and insert holes all open upward. Print a cutout test first: if switches are too tight, use 0.05 hole/XY compensation (FDM holes print about 0.1 undersize). |
| Bottom | 4° underside on the bed | 0.2 | Only bridges are the four Ø5.8 counterbore roofs. |
| GlowBand | flat | 0.2 | Clear/natural PETG, 100 % infill (or 6 perimeters) so it glows evenly. Pads and tongue grow upward. |
| Knob | upright, bore opening on the bed | 0.12 | 5 perimeters. Press-fit: ream the D-bore if it is too tight. |

Material: Top about 37.3 cm³, Bottom 25.6, GlowBand 5.9, Knob 3.3 (about 73 cm³ if solid, at most about 93 g of PETG; less with 25 % infill).

## Assembly order

1. Heat-set 4 inserts (OD 5, L 4) into the Top: skirt face up, iron about 230 °C, flush with the face. (The kit has 6 inserts and 6 screws; 4 of each are used.)
2. Solder the bottom-side parts on the PCB: XIAO (castellated, flat), 13 SK6812 MINI-E, THT diodes lying flat (≤ 2.2 mm above the PCB top, the plate is 2.5 above), EC11, and the OLED on a 2.5 mm header with the pins trimmed flush on top.
3. Clip the 9 switches into the Top plate. Lower the PCB onto the switch pins, check the OLED glass sits in its window, then solder the switches.
4. With the Top upside down, lay the GlowBand on the skirt (tongue into the USB notch), then the Bottom.
5. Drive 4 M3×16 from underneath until snug. PETG creeps, so don't over-tighten.
6. Keycaps, then the knob (D-flat aligned) or a bought 18 mm aluminium knob.

## What `check_fit.py` verifies

| Check | How |
|---|---|
| Assembly ≤ 200 × 200 × 100, parts fit the bed | Bounding box of the full desk assembly incl. keycaps and knob |
| STEP reopen, STL watertight | Re-import every exported STEP (volume equal), trimesh watertight / winding on every STL |
| PCB pocket = PCB + 2 × tolerance | Rays from the PCB centre in Top, GlowBand and Bottom: 61.75 × 83.75 |
| Interference | Boolean intersection volume (< 0.01 mm³) of every printed part with the PCB and every placeholder (switch housings and clips, pins, keycaps, OLED board/glass/header, XIAO board/USB/shield, EC11 body/bushing/shaft/pins, all LEDs), and of the printed parts with each other; keycaps again at 4 mm bottom-out; PCB clearance ≥ 0.3 |
| Switch cutouts | Ray widths at the clip zone: 14.0 ± 0.1 in x and y for all 9; plate 1.5 at the clips, 2.5 web; switch bodies vs plate volume 0 |
| Keycaps | Minimum distance to the Top ≥ 1 mm at rest and bottomed out; to the knob ≥ 1 mm; inside the shell in plan |
| Inserts and screws | Hole Ø4.7 × 4.0 measured by rays; wall around the insert ≥ 1.3; bosses vs PCB (no overlap, gap ≥ 0.3); switch pockets, OLED recess, EC11 opening and USB window ≥ 1.2 from the insert holes; M3×16 shank and head clash-free, head recessed, 4 mm thread in the insert |
| USB-C | Opening measured by rays in Top + band: centred within 0.5 mm of the receptacle (x and z), at least the design.json size (13.5 × 8); a 12.5 × 7 cable overmold passes the wall with no overlap |
| Encoder | Smallest opening ≥ 7.4 and no overlap with bushing or body; knob D-bore vs shaft: no overlap, 0.03–0.3 gap |
| OLED | Window = design window + 0.3 per side; glass, board and header do not touch the Top |
| GlowBand | 2.0 mm band; a pad directly under each glow LED, air gap ≥ 0.3 (0.82 now) |
| Printability | Print orientation: no face steeper than 45° overhang above the bed, flat bridges ≤ 10 mm (conservative bbox span). Thin walls: rays inward from sampled surface points. Fails below 0.8; spots < 1.2 are listed as warnings (known: 1.0 OLED lip, 1.0 between the Ø3.4 screw hole and the PCB pocket, 1.1 counterbore skin). The knob's knurl ribs are excluded. |
| Bottom-side pads | Every pad in `PCB/build/bottom_pads.json` becomes a keep-out: THT pads as a 2.0 mm lead tail, SMD pads as a 0.3 mm joint. Each printed part must stay ≥ 0.5 from them in 3D. Any printed feature within 2.5 mm under the PCB must also stay ≥ 0.5 from every pad in plan. Insert-boss footprints (full Ø8.7 circle) ≥ 0.5 from every pad. Lead tails vs Bottom floor and bosses ≥ 0.5 |
| Mesh section | `production/Top.stl` sectioned through the clip zone shows 9 square 14.0 holes (the same idea as `verify` G4.switch_cutouts) |

## Notes for the PCB (`design.json`)

- **Bottom-side keep-outs** come from the insert bosses, which sit 0.3 mm under the board. Each is a Ø8.7 circle around a `case.screws` position (it reaches x ≤ 1.35 / x ≥ 59.8 at y 4.65–13.35 and 57.75–66.45). They are written to `positions.json` → `bottom_side_keepouts`. `check_fit.py` checks them against every pad in `PCB/build/bottom_pads.json` (regenerate with `PCB/tools/export_bottom_pads.py`). Closest today: D6 pad 1, 2.12 mm from the right-front boss.
- Screw positions, boss OD and the USB window width are read from design.json. Moving them there and rerunning both scripts updates every part.
- Top-side THT parts under the plate (diodes) must stay ≤ 2.2 mm tall: the plate underside is 2.5 mm above the PCB.
