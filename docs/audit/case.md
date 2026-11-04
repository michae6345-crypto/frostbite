# Frostbite mechanical audit (case)

Independent audit of the printed parts in `production/` and `CAD/frostbite-assembly.step`. `CAD/check_fit.py` was neither reused nor run (it re-exports into `CAD/` and `production/`). Every number below comes from my own scripts on the real STEP/STL, unless marked "estimate".

## Verdict

**The case cannot be assembled as designed.** The PCB cannot enter the Top, because the four insert bosses block its path. `check_fit.py` passes because it tests final positions only, never the path into them. Once that is fixed, the rest of the design is close: the Z stack, USB-C, screws, inserts and printability all check out. The main remaining risk is the glow band, which looks poorly fed and needs a test print.

| Severity | Count | IDs |
|---|---:|---|
| BLOCKER | 1 | B1 |
| MAJOR | 3 | M1, M2, M3 |
| MINOR | 12 | N1–N12 |
| Verified passes | 26 | see "Verified passes" |

Status labels: CONFIRMED = measured on the real parts. LIKELY = the geometry is measured but the effect is inferred. UNVERIFIED = needs the physical check named in the finding.

## Method and sources

- Parts loaded from `production/*.step` into the design frame (X = PCB x, Y = −PCB y, Z = 0 at the PCB underside). The frame was checked by landing rays on known features: Top Z −9.4…6.6, Band −11.4…−2.6, Bottom −21.33…−11.4.
- `production/*.stl` volumes equal the STEP volumes (37.33 / 25.55 / 5.90 / 3.28 cm³), and the matching solids in `CAD/frostbite-assembly.step` have the same volumes. The assembly's PCB solid is a plain 61.15 × 83.15 × 1.6 prism (8135.4 mm³).
- Real component data:
  - **EC11:** official Alps STEP, plus the drawing and part page at <https://tech.alpsalpine.com/e/products/detail/EC11E15244G1/> (drawing gif and `EC11E-05SW.STEP` via the page's cms.media links). The Digi-Key URL in `docs/DIMENSIONS.md` returned 403.
  - **XIAO RP2040:** `refs/SplashPad/PCB/3D Models/Seeed_Studio_XIAO_RP2040_v26.step`, plus <https://wiki.seeedstudio.com/XIAO-RP2040/>.
  - **MX switch:** `refs/SplashPad/PCB/3D Models/MX_Switch.step`.
  - **SK6812 MINI-E:** <https://cdn-shop.adafruit.com/product-files/4960/4960_SK6812MINI-E_REV02_EN.pdf>, pp. 4, 5, 10.
- Real builds used for comparison: `refs/mediapad/irl_assets/*.jpeg`, `refs/froskeys/irl.jpg` with `production/Top.3mf`.
- Caution: the two community EC11 models in `refs/` (SplashPad, stratum) show body 6.5 / bushing top 14 / tip 26.5. The official Alps data shows 4.5 / 11.5 / 24.5. I trusted Alps, so `DIMENSIONS.md` is correct on this. See the EC11 section for what happens if the kit part is a generic EC11.

## Findings

### B1. BLOCKER, CONFIRMED: the PCB cannot enter the Top

**Evidence**
- The bosses are built at `CAD/frostbite_case.py:176-183`. They run from the skirt rim (Z −9.4) up to Z −0.3, and they stick into the PCB pocket.
- Rays on `production/Top.step`: at PCB y = 9 and Z from −9 to −2, the free width is x = 1.35…59.8 = **58.45 mm**. The same width appears at y = 62.1 (rays at Z −5). The PCB is **61.15 mm** wide. Above the chamfer (Z ≥ −0.3) the pocket is 61.75 wide, so the PCB fits only in its final seat.
- The only way in is from the skirt side, because the plate closes the other side. Sweeping the real PCB outline up to its seat cuts all four bosses: **48.47 mm³ each, 193.86 mm³ total**, X 0…1.35 and 59.8…61.15.
- `PCB/frostbite.kicad_pcb` Edge.Cuts is a plain rectangle with R1 corners and no notches.
- `CAD/README.md:73` (step 3, "Lower the PCB onto the switch pins") cannot be done.

**Attempts to disprove**
- Static overlap: 0.0 mm³, so `check_fit.py:197-201` is right about the seated position. It simply never tests the insertion path.
- Tilted entry: I ran a 3-axis search (x, z, tilt ±25°; grid 0.1 mm / 0.2 mm / 0.5°) on a bare PCB section through the bosses. From the seat the PCB can move down only about 0.4 mm, and it can never reach the outside. With switches clipped in, even that tilt is unavailable.
- Press past the bosses: not possible. The interference is at least 1.05 mm per side even with the PCB pushed fully to one side, against solid PETG with a rigid board.

**Fix options (either one, then add a Z-sweep test to `check_fit.py`)**
- **A (preferred, no PCB respin):** remove the tuck and widen the shell. An insert needs 1.3 + 4.7 + 1.3 = 7.3 mm of wall, and the wall is 6.7 today. Use skin at x = −7.6 and axis at x = −3.95 (mirrored on the right), shell width **76.35**. Band and Bottom follow.
- **B (PCB respin):** notch the PCB edge at the four bosses, about 1.65 × 9.3 mm (x ≤ 1.65 and the mirror, y 4.35–13.65 and 57.45–66.75). I found no tracks or vias within 0.3 mm of three notches. The right-front notch has B.Cu tracks near (60.45, 57.2) and (59.49, 58.3) that would need rerouting.

### M1. MAJOR, LIKELY: GlowBand pads have zero clearance in the Top pocket

**Evidence**
- Pad faces measured at x = −0.3 and 61.45, and at y = 83.45 on the front pads. The Top pocket walls are at exactly the same coordinates, so the gap is **0.00 mm**.
- Span between outer pad faces: 61.75, equal to the pocket. The front pads also fill into a square inner corner.
- Source: `frostbite_case.py:219-221`. The USB tongue beside it has a 0.2 gap (`:109`), and the project rule is 0.2–0.4 per side.

**Attempt to disprove:** both parts shrink alike, which removes part of the risk. But FDM outside faces print slightly proud and inside faces slightly small, so printing cannot make the fit looser. Boolean overlap is 0, which is why `check_fit.py` passes.

**Effect:** the pads bind about 6.8 mm deep in the pocket. The band then cannot sit flat on the skirt rim until the pads are filed.

**Fix:** set back each pad's wall faces by 0.3.

### M2. MAJOR, LIKELY (brightness UNVERIFIED): the glow band gets very little light and the skirt gets more

**Evidence, Monte-Carlo first-hit model** of the four LEDs against the measured geometry (Lambert emission, which fits the 120° pattern on datasheet p.10):

| LED | Pad | Band ring | Top skirt | Floor | Bottom wall |
|---|---:|---:|---:|---:|---:|
| back pair (y 25.4) | 85% | **1.0%** | 6.3% | 4.7% | 1.7% |
| front pair (y 80.6) | 83% | **0.2%** | 11.4% | 3.9% | 0.5% |

The pads therefore do almost all the work. How they pass light on:
- A side pad touches the skirt over 47.6 mm² and the ring over only 14 mm², so **3.4× more** contact goes to the frosted skirt than to the clear ring. A front pad: 103 vs 30.3 mm².
- By area share, about 3.5–8% of the pad's scattered light reaches the ring and 12–27% reaches the skirt. This is an area-ratio estimate, not an optical simulation.

Other geometry:
- Distance from a point on the visible band face to the nearest LED: min 9.1, median 19.7, **max 40.9 mm at back centre**. Side centre 29.9, front centre 27.1.
- The clear band's visible face is 2 mm tall, and light must cross a 6.2 mm wide ring to reach it.
- The PCB does not shadow the LEDs. They are below it, facing down.

**Is it visible at all?** Rough estimate only: `#7fe3ff` at 27% (`README.md:118`) with datasheet p.5 midpoints gives about 1.25 lm per LED. If about 4% reaches the ring and half survives 6 mm of FDM clear PETG, the 640 mm² face reaches roughly 50 cd/m². That would be visible in a dim room and faint in a bright one, with hot spots near the LEDs and a dimmer back edge.

**Attempts to disprove:** I looked for a built Hackpad with a lit translucent band. mediapad's "spacer" (`refs/mediapad/Production/spacer.stl`) is a 6 × 6 × 3.6 post, not a light guide, and its side gap looks dark in `irl_assets/1.jpeg`. So no reference proves this approach works, and none proves it fails.

**To settle:** print one corner of band, pad and skirt with a single SK6812 before printing the whole set, and photograph it at 27%.

**Fix ideas:** add an air gap or foil between pad and skirt, line the skirt's inner wall with foil or white paint, and consider a fifth light path toward the back edge.

### M3. MAJOR, UNVERIFIED: the OLED flex at the far end may not fit under the 0.3 mm lip gap

**Evidence**
- At the far (non-header) end, the Top has a 1.0 mm lip over x = 2.2…5.7 (ray: Z 5.6…6.6). The design module's board top is at Z 5.3, leaving **0.3 mm**.
- Both real modules in the photos (`mediapad/irl_assets/3.jpeg`, `froskeys/irl.jpg`) show a flex ribbon and tape folded around that end of the board, in exactly the space under this lip. Neither build has a lip there: both show the whole module through the opening.
- `CAD/frostbite_case.py:286` models only a board and a glass block, with no flex.

**Attempt to disprove:** I searched for a module drawing giving the glass position and flex height. Vendor pages only give outline sizes, and sizes vary (35.8–38 long). The KiCad footprint silk (x 3.5–33) supports the CAD's glass position, so the glass itself should fit. The flex height is what remains unknown.

**To settle:** measure the kit module with calipers, flex height above the board at the far end, and glass position from both ends.

**Fix (cheap):** extend the window through the lip at that end, as both real builds do.

### Minor findings

| ID | Status | Finding and evidence | Fix |
|---|---|---|---|
| N1 | CONFIRMED | **Knob sits 2 mm higher than designed.** The Alps shaft is round until 10 mm below the tip (Z 16.1). The knob's D-bore runs full length with no relief, so at the design height Z 14.1 it overlaps the real shaft by 10.0 mm³. It seats at Z ≥ 16.1 (0.0 mm³). The placeholder shaft is a D for its full length (`frostbite_case.py:295`). Result: Z 16.1…31.1, 9.5 above the plate, and the 12.98 × 16 opening is visible from shallow angles. Both reference knobs have a mouth relief (stratum Ø9, SplashPad Ø10). | Add Ø7.6 × 3.2 relief at the mouth |
| N2 | UNVERIFIED | **Knob fit is not a press fit as modelled.** Measured bore Ø6.2 × 4.7 across the flat (README says 4.6), against Alps Ø6.0 × 4.43–4.5. Reference knobs differ a lot: stratum 6.33 / 4.83, SplashPad 5.6 / 4.1. There is no set screw. | Print a test knob on the real shaft |
| N3 | LIKELY | **OLED header joints meet the lip.** Pin row x = 39 is under the lip with 0.3 mm above the board. Domed joints are visible in the mediapad photo. Even when trimmed flush, a joint can exceed 0.3. | Thin the lip locally to 0.7 |
| N4 | CONFIRMED | **OLED held by the header only.** 36.5 mm of module is cantilevered with nothing under it in `Top.step`. A header tilt of about 0.5° uses up the 0.3 gap at the far end. mediapad printed an 8 × 8 × 2 support (`support_display.stl`) for this. | Solder J1 with the PCB seated (see order below), add a 2.4 mm foam pad |
| N5 | CONFIRMED | **BOOT and RESET unreachable once closed.** They are on the XIAO's component side at the end away from the USB (real photo, model), so they sit at x 15–19 and 23–27, PCB y 18.2–20.7, facing down into the sealed chamber. `README.md:124-125` lists both. Recovery needs the 4 screws out, which is acceptable. Bootmagic Approve + Stop works only with good firmware. | Flash before closing, note it in the assembly steps |
| N6 | CONFIRMED (hanging) / LIKELY (effect) | **PCB hangs from the switches only.** The bosses leave a 0.3 gap, and nothing else touches it. The back 26 mm (USB, encoder, OLED; row 0 cutouts start at y 26.5) has no switch. mediapad and orpheuspad each use extra PCB screws. Fix option A in B1 also removes the bosses as rests. Hand-estimated PCB deflection under a 10 N knob press is about 0.35 mm, which is tolerable. | Optional: a rest rib on the Top wall that clears the PCB's path |
| N7 | LIKELY | **Front edge weakly clamped.** Screw axes sit 16 mm from the back skin and 28 mm from the front skin. A warped part would open the band gap on the side the user sees. | Check when test-fitting |
| N8 | CONFIRMED | **Bottom rim prints as a staircase.** Rim is 4° to the bed, so terraces are 2.86 mm long at 0.2 mm layers. The slice shows a sliver at the last layer (z 9.9). The band mating face is stepped by one layer, up to 0.2 mm. | Accept, or print a flat-rim variant |
| N9 | LIKELY | **Light leaks around the OLED.** The 0.3 PCB perimeter gap links the chamber to the space under the plate, which reaches the OLED recess. The 1.0 lip is the thinnest plate area, so it will glow most. A similar leak around the OLED is visible in `mediapad/irl_assets/3.jpeg`. | Foil or black tape on the lip's underside |
| N10 | LIKELY | **Active area off-centre in the window.** Estimated from photo 3, with about ±1 mm error: active area centre about 2.5 mm toward the header. That gives about 6.6 mm of blank glass on the left and 1.6 mm on the right of the 30.6 window. Cosmetic. | Accept, or shift the window once the module is measured |
| N11 | CONFIRMED | **No feet or foot recess** in the CAD or BOM. Light (about 145–170 g, estimate) on bare PETG, so a stiff cable will drag it. The flat underside takes stick-on feet. | Add 4 feet to the BOM |
| N12 | UNVERIFIED | **Switch centre-post fit against shrink.** Hole Ø3.988 and post Ø3.85 leave 0.069 per side, and the cutouts have no play. Corner keys are 26.9 mm from centre, so plate shrink above about 0.26% loads the posts. froskeys got a printed plate with 14.0 cutouts to fit, but I do not know its shrink. | Measure SW1→SW3 pitch (38.10) on the print before the PCB goes on |

Documentation errors, all harmless:
- XIAO USB overhang is 1.0 mm, not 1.4.
- Glow LED lens is at Z −0.84 (datasheet p.4), so the pad gap is 1.76, not 0.82. The hole for the LED back exists.
- Underside at the front screws is −16.5, not −16.2. Head recess is 0.5 at the front, 4.2 at the back.
- The README's "tuck 1.0" (`CAD/README.md:40`) conflicts with 1.35 (`:49`). Measured reach past the PCB edge: 1.35.

## 1. Z stack (measured, design frame)

| Z | Item | Source |
|---:|---|---|
| −21.33 / −14.55 | Bottom underside at back / front skin | Rays on Bottom |
| −18.27 … −12.54 | Bottom floor top (y 1 → 83) | Rays; floor 2.5 |
| −11.4 | Bottom rim / band underside | Rays |
| −9.4 | Band top / skirt rim | Rays |
| −5.4 | Insert top | Hole Ø4.7 → Ø3.4 |
| −4.405 | XIAO USB shell lowest point | Real model, placed |
| −2.85 / −3.2 | XIAO buttons / shield | Real model |
| −2.6 | Pad top | Rays |
| −0.84 | Glow LED lens | Datasheet p.4 |
| 0 … 1.6 | PCB | Hangs from switches |
| 3.4 | Blind screw hole end | Rays |
| 4.1 / 5.1 / 6.6 | Plate underside / clip underside / plate top | Rays |

- **Switch seat:** plate top is exactly 5.0 above PCB top. The real MX model gives 5.0 from housing bottom to flange, and clips end about 1.55 below it. **Clips will work:** 1.5 plate, 14.0 cutouts on all 9, 15.4 pockets.
- **Key bottom-out:** the Top's highest point is the flat plate at Z 6.6, so there is no rim to hit. A cap (rim about 6.0 above plate, an estimate) stays about 2 mm above it at 4 mm travel. The OLED is 5.4 mm away from the nearest cap in plan.
- **On the desk:** Top face 21.1 (front) to 27.8 (back). Cap tops about 35.3 and 39.2 (DSA, estimate). Knob top about 50.9 after N1.

## 2. EC11 (official Alps STEP placed at the design location)

- Body and bushing against Top: 0.0 mm³. Opening 12.98 × 16 clears the 11.7 × 12 body by 0.64 in x and 2.0 in y.
- Body top Z 6.1 is 0.5 below the plate top. Bushing top is Z 13.1, shaft tip Z 26.1, so the shaft stands **19.5 above the Top**.
- The knob presses on nothing: bottom at Z 16.1 (N1), 9.5 above the plate, 3.0 above the bushing.
- Turns freely: 2.4 mm in plan to the SW3 cap.
- The push switch (0.5 travel) is not blocked. There is 3.0 under the knob, and the bore roof clears the tip by 2.3.
- If the kit part is a generic EC11 matching the community models, it still fits: body 1.5 above the plate through the opening, tip Z 28.1, knob at least 0.2 above the bushing. Push travel could then be limited to about 0.2, and the push switch is unused. Check the kit part.

## 3. OLED

- Window 30.6 × 12.1 (x 5.7–36.3, y 6.95–19.05). Recess 38.6 × 12.6 up to Z 5.6.
- On the design's numbers (2.5 spacer, 1.2 board, 1.45 glass): board Z 4.1–5.3, glass top Z 6.75, 0.15 proud of the plate. The module is taller than the 3.5 gap below the plate, which is why the recess exists.
- The header stands in the recess without touching the plate.
- It cannot be fitted after the Top is on. The 38 mm board is longer than the 30.6 window, and the PCB blocks the underside. Solder J1 last, from underneath (see the order below).
- Retention: lip above, header below, see M3, N3, N4.

## 4. USB-C (real XIAO placed flat on the underside)

- Receptacle section Z −1.195…−4.405, centre **−2.80**. Window centre −2.83, so **0.03 off**. x centre 21.00. Real XIAO against Top, Band, Bottom: 0.0 mm³.
- Receptacle mouth is at PCB y = −1.0, so 6.0 from the outer skin.
- Overmold test along the full wall depth:

| Overmold | Clear? | Margins (top / bottom / side) |
|---|---|---|
| 12.35 × 6.5 | yes | 0.72 / 0.78 / 0.58 |
| 12.5 × 7 | yes | 0.47 / 0.53 / 0.50 |
| 13 × 7.5 | yes | 0.22 / 0.28 / 0.25 |
| 13.5 × 8 | no | overlaps Top |

- With 0.15 per side print undersize, 12.5 × 7 still clears by 0.32 or more.
- A plug shell is 6.65 long and the mouth is 6.0 behind the skin, so a cable that doesn't fit the window engages only about 0.65 mm. That means only overmolds above about 13.4 × 7.9 fail.
- The receptacle passes up through the notch during assembly: sweep against Top 0.0 mm³.
- Plug force goes through the switches into the plate. See N6.

## 5. Assembly

**Today:** the order fails at `CAD/README.md:73` (B1).

**Real order, once B1 is fixed:**

1. Print test pieces first: a plate corner, band corner and knob.
2. Measure the SW1→SW3 pitch and the kit OLED (M3, N12).
3. Heat-set 4 inserts into the Top, skirt up.
4. Solder the XIAO, 13 LEDs and diodes flat. Glow LEDs go lens down, back in the cut-out.
5. Solder the EC11 and trim all tails to ≤ 2.0.
6. Flash `led-test` and firmware with the BOOT button (N5).
7. Solder the header to the OLED and trim. Sit it in J1 **unsoldered**.
8. Clip 9 switches into the plate from the top face.
9. Lower the PCB onto the switch pins. USB rises up the notch, the EC11 goes through its opening, the glass enters the window.
10. Solder 18 switch joints from underneath, then J1, so the module aligns itself to the window.
11. Test everything, with BOOT still reachable.
12. Fit the band (pads in the pocket, tongue in the notch), then the Bottom.
13. Drive 4 M3×16 until snug.
14. Fit keycaps, then the knob.

Checks on this order:
- **Iron reach:** the PCB underside is 9.4 below the skirt rim. The closest switch pin is 8.02 from a wall, which needs a 40.5° lean at the rim, a normal soldering angle. Closest boss distance is 8.4 (if kept).
- **J1:** 9 mm from the XIAO and about 4.5 from the EC11 lug.
- **Inserts:** the hole opens upward at the skirt rim with nothing nearby, so the iron goes straight in. Wall to skin 1.65, and 8.8 mm of Ø3.4 clearance beyond the insert takes the melt. Ruthex minimum is 1.3.
- **M3×16:** head seat Z −13.0, tip +3.0. It passes Bottom 1.6 + band 2.0, gets **full 4.0 thread engagement**, and stops 0.4 short of the blind end, in the skirt, well clear of the plate. Head recess is 0.5 at the front and 4.2 at the back.
- **PCB removal:** after a fix, either desolder 18 joints or release the 9 switches with a puller from the top and lift the PCB out with them.

## 6. Printability (`production/*.stl` as exported, no supports)

| Part | Bed area mm² | Overhang > 45° | Bridges | Thin walls (layer slices) |
|---|---:|---|---|---|
| Top | 4838 | none (boss chamfers exactly 45°, 44 mm²) | none | nothing < 1.2 by slice. < 2.0: 1.65 insert to skin, 1.86 OLED recess to EC opening, 1.0 hole to pocket over a short arc |
| Bottom | 7089 | 4 counterbore roofs, 17.3 mm² each | Ø5.8 roof with a Ø3.4 hole, ring about 1.2 wide | only the last-layer rim sliver < 1.2 (N8). 1.1 counterbore to skin |
| GlowBand | 2043 | none | none | nothing < 1.2. Ring 6.2 wide, 1.0 beside the screw holes |
| Knob | 215 | bore roof only | 4.7 × 6.2 | none |

- All four parts are printable without supports. The orientations in the exports match `CAD/README.md`.
- **The 1.0–1.1 mm walls are not structural.** The 1.0 hole-to-pocket wall carries no radial load, the 1.0 OLED lip only limits upward travel, and the 1.1 counterbore wall is a thin skin, not the head seat. The 1.0 band wall is clamped in compression. The head seat itself is 1.6 thick and 1.05 wide.
- **GlowBand:** 2 mm tall but 6.2 wide, and clamped flat between two rigid parts, so it is printable and strong enough.
- **Shrink against the 0.3 tolerance** (no shrink value sourced, so these are limits): the pocket fits the PCB up to 0.72% shrink, or 0.48% with holes printing 0.1 small per side.
- **Cutouts:** froskeys built a printed 1.5 plate with 14.0 cutouts (`production/Top.3mf`, `irl.jpg`), so this size works in practice. The plate-down first layer can narrow cutouts slightly, so print the test corner.

## 7. Glow and light bleed

See M2 and N9.
- The glow LEDs do sit over the band pads, and the PCB does not block them.
- Key LEDs sit under the switch LED window: the MX model is open at y = −5.08 in its frame, matching the footprint offset (x, y + 5.08) in KiCad's y-down frame.
- The Top and Bottom are translucent, so the skirt and floor will also glow. Direct light alone reaches the skirt about 6× (back LEDs) to 50× (front LEDs) more than the ring.

## 8. Stability

- Pressing a key cannot tip it. The key-axis line through the cap tops lands inside the flat footprint by at least **18.5 mm** (SW9, side and front), and top-row keys by 37.6 mm or more. A knob-edge press lands 10.0 mm inside.
- Estimated mass 145–170 g, centre of mass about 18–19 mm above the desk and near the footprint centre. Printed-part figures are measured, others are estimates.
- A sideways 1.0–1.2 N at the knob top would tip it in theory. With PETG on a desk it slides first, and turning a knob applies a couple, not a side force.
- 4° tilt confirmed on the parts: underside rise 6.78 mm over 97.15 mm. No feet (N11).

## Verified passes

1. Plate top 5.0 above PCB top
2. Plate 1.5 at clips
3. 14.0 cutouts at all 9 keys
4. 15.4 clip pockets
5. Caps clear at bottom-out (no rim)
6. EC11 clears the opening
7. Shaft and knob height work, push not blocked
8. Knob turns freely
9. OLED glass enters window (on CAD dimensions)
10. Header stands clear of the plate
11. USB-C centred within 0.03
12. 12.5 × 7 overmold seats fully
13. Receptacle passes up the notch
14. XIAO clears all parts
15. M3×16 length and engagement
16. Insert hole Ø4.7 × 4.0, wall 1.65
17. Iron reaches all switch joints
18. All parts support-free
19. No wall below 1.2 except non-structural spots
20. GlowBand printable and strong
21. STL and STEP volumes match
22. Assembly STEP volumes match production
23. Glow LEDs have the hole their backs need
24. Key LED under the switch window
25. Keys cannot tip the pad
26. Heads recessed

## Scripts

All in `(temporary folder, since deleted)/case_audit/`: `frames.py` (frame loader), `m1.py` (PCB sweep), `m6.py` (stack rays), `m7_print.py` (overhangs), `m8.py` (knob vs Alps), `m9_tilt.py` (tilt search), `m10_thin.py` (thin walls), `m13.py` (MX and knobs), `m15.py` and `m17.py` (XIAO, overmold), `m16.py` (stability, iron), `m18_glow.py` (glow), `m19.py` (notch copper).
