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
| `../production/{Top,Bottom,GlowBand,OLEDSupport,Knob}.{step,stl}` | Print-ready parts, already in print orientation |

```sh
cd CAD && ~/.local/bin/uv venv --python 3.12 .venv && ~/.local/bin/uv pip install --python .venv -r requirements.txt
cd .. && CAD/.venv/bin/python CAD/frostbite_case.py     # parts, assembly, previews (~10 s)
CAD/.venv/bin/python CAD/check_fit.py                    # rebuild + all checks (~15 s)
```

## Parts

| Part | Material | Size | Notes |
|---|---|---|---|
| **Top** | iced (translucent) PETG | 79.15 × 97.15 × 16.0 | Integrated MX plate plus a solid skirt that hides the PCB edge. The plate is 1.5 mm at the 14.0 cutouts (15.4 clip pockets from below) and 2.5 mm elsewhere. Holds the 4 heat-set inserts in its side walls. OLED window, EC11 opening, USB-C window. |
| **GlowBand** | clear / natural PETG | 78.15 × 96.15 ring, 2.0 visible, 8.8 overall | Light guide: the visible 2 mm ring (0.5 mm behind the shell skin), a 2 mm riser wall that stands inside the Top pocket, and a pad under each glow LED. A tongue forms the bottom edge of the USB window. |
| **Bottom** | iced PETG | 79.15 × 97.15, 3.1 (front) to 9.9 (back) | A 4° wedge tray with a 2.5 mm floor and an open chamber under the PCB (XIAO and glow LEDs hang into it). Ø3.4 screw holes with Ø5.8 counterbores from underneath. |
| **OLEDSupport** | any PETG (dark hides best) | 33.9 × 13.5 × 1.4 C-shape | Fills the gap under the OLED module and rests on the PCB. One foot under the far end, one beside J1, joined by a rail outside the module. Thin double-sided tape on both faces. Same idea as mediapad's printed display support. |
| **Knob** (optional) | PETG | Ø18 × 15 | 30 vertical knurl ribs. D-bore Ø6.2 / 4.7 across the flat (0.1 mm clearance per side on the round, 0.2 across the flat), 12.3 deep, with a Ø7.6 × 3.2 mouth relief over the round part of the shaft. Prints upright without supports. Fit on the real shaft is untested: print one first. |

Assembled on a desk (from `positions.json`): top face **21.1 mm** at the front, **27.8 mm** at the back. Keycaps add about 13.6 mm and the knob top is about 22.5 mm above the plate. Case bounding box 79.2 × 98.9 × 27.9 mm. The assembly with keycaps and knob is 79.2 × 98.9 × 49.5 mm, well under 200 × 200 × 100.

### Vertical stack (design frame, z = 0 at the PCB underside)

```
 +6.60  Top face = plate top (PCB top + 5.0, fixed by the MX switch)
 +6.05  OLED glass top (0.55 below the plate)
 +5.60  underside of the 1.0 lip over the module ends
 +5.10  plate underside at the clips (1.5)       +4.60 OLED module board top (1.0 under the lip)
 +4.10  plate underside elsewhere (2.5)          +3.40 OLED module board underside
 +3.00  screw tip (blind Ø3.4 hole ends at 3.4, 3.2 mm of skin above)
 +1.80..3.20  OLEDSupport (0.2 tape above and below)
 0..1.6 PCB, in a pocket of PCB + 0.3 per side in the Top and the Bottom (61.75 × 83.75)
 -2.60  top of the GlowBand pads and riser wall (0.6 below any 2.0 mm lead tail)
 -2.83  USB-C receptacle centre = centre of the 13.5 × 8 window
 -5.40  top of the 4 mm inserts
 -9.40  Top skirt rim: inserts pressed in from here | GlowBand ring top
-11.40  GlowBand bottom | Bottom rim
-13.00  screw head seat;  head bottom -16.0;  underside -16.5 at the front screws, -20.2 at the back screws
```

### Design decisions

- **Inserts in the Top, screws from underneath.** Hidden screws mean the thread has to be in the upper part, so the four inserts sit in the Top and the M3×16 heads sit in counterbores under the Bottom.
- **Nothing printed stands in the PCB's path.** The plate closes the top of the Top, so the PCB can only enter from the skirt side. The first version of this case tucked the insert bosses 1.35 mm under the PCB edge. It passed every seated-position check and could not be assembled (audit B1, `docs/audit/case.md`). The inserts now sit fully in the side walls.
- **Why the shell is 79.15 wide.** Tolerance 0.3 + boss OD 8.7 (hole 4.7 + 2 × 2.0 wall, the G4 rule) = 9.0 from the PCB edge per side, which is also `case.shell.bezel`. So the screw axis is 4.65 outside the PCB edge and the width is 61.15 + 18 = 79.15. The smallest shell that keeps only the ruthex 1.3 wall is 76.35, but then the Ø5.8 counterbore leaves a 0.75 skin; 1.2 of counterbore skin needs 77.25. Front and back walls stay 7 mm, because no screw is there.
- **PCB support.** The PCB hangs from the 9 soldered switches. Nothing rests under it. The back 26 mm (USB, encoder, OLED) has no switch, so hard pushes there flex the board slightly (audit estimate about 0.35 mm at 10 N).
- **Why the Top is 16 mm tall.** The 13.5 × 8 USB window fits inside the skirt, with the inserts at the rim. M3×16 with recessed heads then sets the depth of the Bottom.
- **EC11 opening.** The plate top is only 0.5 mm above the EC11 body (body 4.5 tall per Alps, plate 5.0 above the PCB). A Ø7.4 bushing hole would need a plate above the body, so the opening clears the body: a 12.98 × 16.0 rounded rectangle (r 2), 0.64 mm from the body. These numbers came from an old verifier shape test that has since been replaced by a real clearance check, so a plain round hole of about Ø17.4 would also pass. The knob does not quite cover it: the corners reach 9.49 mm from the shaft against the knob's 9.0, and it shows from shallow angles (audit m1).
- **OLED.** The switch fixes the plate at 5.0 above the PCB, and the standard 2.5 mm header plastic would put the glass 0.15 proud, 0.45 if the module sat on the lip (audit H1). So the plastic comes off and the printed OLEDSupport sets the height: module underside 1.8 above the PCB (`case.oled_support.module_gap`). The glass ends 0.55 below the plate, still 0.35 below with tape 0.1 thicker on each face. There is 1.0 mm of air under the lip.
- **Why the module is soldered before the Top.** Once soldered to J1 it cannot fall away when the PCB is turned over (H1), and the OLED can be tested while everything is still open. The cost is that nothing aligns it to the window as it solders. The opening is therefore wider than the glass: window 31.0 × 12.98 around the 30 × 11.5 glass, recess 39.4 × 13.6. The sweep passes with the module turned ±1° and shifted ±0.1. The price is a visible gap of about 0.5–0.7 mm around the glass.
- **Pressing the glass (H2).** The feet sit under both ends of the glass, so a press lands between two supports and no longer levers on the pin row. This is geometry only; the force path has not been tested.
- **USB-C.** The window is centred on the receptacle (x 21.00, z −2.83) and sized from `case.usb_cutout`: 13.5 × 8.0, or 0.5 mm per side around a 12.5 × 7 overmold. The Top has a notch down to its rim and the GlowBand tongue rises into it (0.2 mm gap), so the Top prints without a long bridge.

### Glow: geometry improved, brightness unproven

The glow LEDs face down from the PCB underside, and the visible band is 2 mm tall. The audit's estimate is that this may be faint. **Only a test print can settle it:** print coupon 4 (`docs/coupons/`) and hold it under a working glow LED running `firmware.uf2` with no daemon, which shows `#7fe3ff` at 70 of 255, about 27 %. With the daemon running the host sets the glow instead: 50 of 255 when nothing runs and 110 while something does (`glow()` in `host/frostbite_host/state.py`).

What the geometry now does:

- Pads and riser stand in the pocket with 0.3 mm of air, so there is no pad-to-skirt contact (was 47.6 mm² per side pad, 103 mm² per front pad).
- The riser wall gives pad light a clear path around the perimeter down into the ring.
- The ring top is relieved 0.3 mm except for a 1.5 mm land at the visible face and around the screws, so ring-to-skirt contact is about 755 mm² (about 1840 mm² before).

A first-hit Monte Carlo (the audit's method, Lambert emission) puts 91 % of back-LED light and 85 % of front-LED light directly on clear parts. Direct light on the frosted skirt falls from 6.3 % to 2.8 % for the back LEDs, but only from 11.4 % to 10.7 % for the front LEDs. That model stops at the first surface. It says nothing about how much light survives FDM PETG and leaves the visible face, and hot spots near the LEDs are likely.

Not improved: the back-centre point of the band is still about 41 mm from the nearest LED, and the riser steps down under the XIAO there, so expect the back edge to be dimmest. LED positions were not changed. If the test print is too dim, the next steps are foil or white paint on the skirt's inner wall, then moving light sources at the PCB level.

## Print settings

PETG, 0.4 mm nozzle, 240 °C / bed 80 °C, 4 perimeters, 25 % gyroid, **no supports on any part**.

| Part | Orientation (as exported) | Layer | Notes |
|---|---|---|---|
| Top | top face down on textured PEI (gives a frosted face) | 0.2 (0.16 for nicer cutouts) | Skirt, pockets and insert holes all open upward. Print a cutout test first: if switches are too tight, use 0.05 hole/XY compensation (FDM holes print about 0.1 undersize). |
| Bottom | 4° underside on the bed | 0.2 | Only bridges are the four Ø5.8 counterbore roofs. |
| OLEDSupport | flat | 0.2 | 2 walls, 100 % infill. Prints in minutes: print it with the test pieces. |
| GlowBand | flat | 0.2 | Clear/natural PETG, 100 % infill (or 6 perimeters) so it glows evenly. Riser, pads and tongue grow upward. |
| Knob | upright, bore opening on the bed | 0.12 | 5 perimeters. Press-fit: ream the D-bore if it is too tight. |

Material: Top about 43.2 cm³, Bottom 28.0, GlowBand 10.4, Knob 3.2, OLEDSupport 0.3 (about 85 cm³ if solid, at most about 108 g of PETG; less with 25 % infill).

## Assembly order

This order replaces earlier ones. The soldering stages follow `docs/BUILD.md`; what changed is the OLED: **it is soldered to J1, on its support, before the PCB meets the Top.** `check_fit.py` sweeps steps 1, 12, 14 and 16–18 along these paths.

The PCB cannot be fitted or removed without the switches: it goes in from the skirt side, and the switches are soldered through it.

**Before printing the full set**

- Print the test coupons in `docs/coupons/`, the knob and the OLEDSupport. Measure the SW1→SW3 pitch on coupon 1 (38.10).
- Measure the kit OLED, see "Unknowns" below. This decides whether the Top needs changing, so do it before the Top goes to a printer.

**Top**

1. With the Top skirt-up, heat-set 4 inserts (OD 5, L 4), iron about 230 °C, flush with the rim. The kit has 6 of each; 4 are used.

**PCB, on the bench**

2. Solder the XIAO (castellated, flat, on the underside) and flash `led-test.uf2` with the BOOT button.
3. Fit LED1 and test it, then LED2–LED9, then glow LED10, test it, then LED11–LED13. The glow LEDs go lens down on the underside. The chain feeds them, so this is the only order that can test one.
4. Solder the 9 diodes flat on the top side (≤ 2.2 mm above the PCB top; the plate underside is 2.5 above).
5. Solder the EC11 on the top side.
6. Trim all tails on the underside to ≤ 2.0 mm. The GlowBand sits 0.6 mm below that.

**OLED, still on the bench, top of the PCB facing up**

7. If the header is loose, put its short pins up through the module from underneath, solder them and trim flush on the display side. Check the pin labels against the silkscreen beside J1.
8. **Remove the black plastic strip** from the pins: slide it off toward the free ends with small pliers, working from both ends. The pins stay soldered to the module. Without this step the glass stands proud.
9. Stick thin double-sided tape (about 0.2 mm, not foam tape) on both faces of the OLEDSupport's two feet. Stick the support to the module's underside: small foot beside the pins, large foot at the far end, rail outside the module on the side facing the keys.
10. Put the pins through J1, display up, until the support sits on the PCB and sticks. Square the module now: measure from the PCB's back edge to the module's long edge at both ends. Both should read 7.0 mm and agree within 0.5 mm.
11. Turn the board over and solder the 4 J1 pins from the underside, then trim to ≤ 2.0 mm. The tape holds the module while you do this. **Test the OLED and the knob now** with `led-test`, while BOOT is easy to reach.

**Into the Top**

12. Clip the 9 switches into the plate from the top face. Check every pin is straight.
13. Turn the Top upside down on two blocks at least 22 mm tall under the plate margin. The switch stems stand 10.2 mm proud of the plate and the encoder shaft 19.5, or 21.5 on a generic EC11, so anything shorter stops the PCB before it seats.
14. Lower the PCB straight down the skirt, underside facing you. The encoder shaft goes in first: start it in its opening about 22 mm before the PCB seats. Then the PCB enters the skirt at 11 mm, the USB enters the notch at about 8, the switch pins meet their holes at about 3.3, and the OLED glass meets the recess last, at about 2. Don't force it. If it stops, lift out and look.
15. Solder the 18 switch joints from underneath, leaning the iron about 40° at the rim. Trim tails to ≤ 2.0 mm. Test every key with `led-test`, then flash `firmware.uf2` while BOOT is still reachable.

**Closing**

16. Lower the GlowBand onto the skirt: riser and pads into the pocket, tongue into the USB notch.
17. Lay the Bottom on the band and drive 4 M3×16 from underneath until snug. PETG creeps, so don't over-tighten.
18. Press on the keycaps, then the knob (D-flat aligned) or a bought 18 mm aluminium knob. Add 4 stick-on feet.

After closing, BOOT and RESET face into the sealed chamber, so reaching them means removing the 4 screws. Taking the PCB out later means releasing the 9 switches from the plate with a puller and lifting the PCB out with them, or desoldering 18 joints.

## Unknowns: measure the real module

Nobody has measured the kit OLED, and no drawing of it was found. These numbers are allowances, not facts.

| Measure | Room left | If it doesn't fit |
|---|---|---|
| Ribbon height above the module board, far end | 1.0 (0.8 allowance + 0.2 spare) | Widen `oled.window` through the far lip, as both reference builds do |
| Ribbon or tape past the far board end | 1.1 | Same |
| Joint height above the board after trimming | 1.0 | Trim again, or thin the lip locally (a CAD change) |
| Parts on the module's underside where the feet touch (x 3.5–9.5 and 32.2–37.4) | None planned; 1.8 total under the module | Move the feet in `frostbite_case.py`, or lower `case.oled_support` height. A part on a foot lifts that end |
| Glass thickness | 1.45 assumed; 1.2 is listed by one vendor | Thinner only sinks the glass further |
| Module length | 38 assumed; 36 exists. The module locates from the header end, so the glass moves in the window | Shift the window |

Also untested: removing the plastic strip by hand, tape thickness, and whether the module stays square while J1 is soldered. Tape about 0.1 thicker on each face is covered.

## What `check_fit.py` verifies

| Check | How |
|---|---|
| Assembly ≤ 200 × 200 × 100, parts fit the bed | Bounding box of the full desk assembly incl. keycaps and knob |
| STEP reopen, STL watertight | Re-import every exported STEP (volume equal), trimesh watertight / winding on every STL |
| PCB pocket = PCB + 2 × tolerance | Rays from the PCB centre in Top and Bottom: 61.75 × 83.75 |
| Interference | Boolean intersection volume (< 0.01 mm³) of every printed part with the PCB and every placeholder (switch housings and clips, pins, keycaps, OLED board/glass/header, XIAO board/USB/shield, EC11 body/bushing/shaft/pins, all LEDs), and of the printed parts with each other; keycaps again at 4 mm bottom-out; PCB clearance ≥ 0.3 |
| Switch cutouts | Ray widths at the clip zone: 14.0 ± 0.1 in x and y for all 9; plate 1.5 at the clips, 2.5 web; switch bodies vs plate volume 0 |
| Keycaps | Minimum distance to the Top ≥ 1 mm at rest and bottomed out; to the knob ≥ 1 mm; inside the shell in plan |
| Inserts and screws | Hole Ø4.7 × 4.0 measured by rays; wall around the insert ≥ 1.3 (2.0 now); boss OD outside the PCB insertion envelope; no Top material inside that envelope below the plate; switch pockets, OLED recess, EC11 opening and USB window ≥ 1.2 from the insert holes; M3×16 shank and head clash-free, head recessed, 4 mm thread in the insert |
| USB-C | Opening measured by rays in Top + band: centred within 0.5 mm of the receptacle (x and z), at least the design.json size (13.5 × 8); a 12.5 × 7 cable overmold passes the wall with no overlap |
| Encoder | Smallest opening ≥ 7.4 and no overlap with bushing or body; knob at its design height on a shaft modelled as the Alps part (round, then the last 10 mm D-flat): no overlap, 0.03–0.3 gap |
| OLED | Window 31.0 × 12.98 around the design window; glass, board and pins do not touch the Top; glass below the plate top, also with 0.3 tape; lip gap ≥ 0.8 measured by rays on the Top at the far lip and over the pins; ribbon and joint allowances fit with spare room |
| OLEDSupport | Footprint ≥ 0.5 in plan from every plated pad and via (J1, U1 pads, parsed from `bottom_pads.json` and the `.kicad_pcb`); tape gap under and over it; clear of the pins and the Top; feet span the glass |
| GlowBand | 2.0 mm band; a pad directly under each glow LED, air gap ≥ 0.3 (0.82 against the 1.78 placeholder; the real lens hangs 0.84 below the PCB, so about 1.76); pads and riser ≥ 0.3 from the pocket walls, tongue ≥ 0.2 from the notch |
| Assembly path | Each step moves along its real straight path to its seat, intersecting at every 0.5 mm: inserts, switches (rigid body, the sprung clips are excluded), the PCB with everything soldered to it (including the OLED on J1, its support and the ribbon and joint allowances), GlowBand, Bottom, screws, keycaps, knob. Parts already fitted count as obstacles, including 2.0 mm lead tails from `bottom_pads.json`. PCB holes are not modelled, so switch pins are not obstacles for the PCB itself. |
| OLED misalignment | The module, turned ±1° about the J1 pin row and shifted ±0.1 in x and y (8 cases), swept into the Top |
| Sweep self-tests | The old tuck bosses added back to the Top must block the PCB (37.6 mm³), and the module at 3° must block (20.0 mm³). If either passes clean, the path checks prove nothing. |
| Printability | Print orientation: no face steeper than 45° overhang above the bed, flat bridges ≤ 10 mm (conservative bbox span). Thin walls: rays inward from sampled surface points. Fails below 0.8; spots < 1.2 are listed as warnings (known: the 1.0 OLED lip). The knob's knurl ribs are excluded. |
| Bottom-side pads | Every pad in `PCB/build/bottom_pads.json` becomes a keep-out: THT pads as a 2.0 mm lead tail, SMD pads as a 0.3 mm joint. Each printed part must stay ≥ 0.5 from them in 3D. Any printed feature within 2.5 mm under the PCB must also stay ≥ 0.5 from every pad in plan. Insert-boss footprints (full Ø8.7 circle) ≥ 0.5 from every pad. Lead tails vs Bottom floor and bosses ≥ 0.5 |
| Mesh section | `production/Top.stl` sectioned through the clip zone shows 9 square 14.0 holes (the same idea as `verify` G4.switch_cutouts) |

## Notes for the PCB (`design.json`)

- Screw positions, boss OD, shell size and USB window width are read from `case` in design.json. Change them there and rerun both scripts.
- The bosses are now outside the PCB, so they add no bottom-side keep-outs. The only printed parts under the board are the GlowBand pads and riser, which stay 2.6 mm below it. They overlap some pads in plan, by design: the pads sit under the glow LEDs. Lead tails must stay ≤ 2.0 mm.
- Top-side THT parts under the plate (diodes) must stay ≤ 2.2 mm tall: the plate underside is 2.5 mm above the PCB.
- The placeholder USB receptacle overhangs 1.4 mm as in design.json. The audit measured 1.0 on the real XIAO model, which is safe.
