# Frostbite PCB: physical layout and manufacturability audit

Audited the real `PCB/frostbite.kicad_pcb` and `production/gerbers.zip`, 2026-11-03. No design files were changed. Coordinates are PCB mm (origin top-left, y down). "Top" is the switch side.

## Result

| Severity | Count | Items |
|---|---:|---|
| BLOCKER | 0 | Nothing found that stops fabrication or fit |
| MAJOR | 2 | M1, M2: hand-soldering heat sinks on GND |
| MINOR | 6 | m1 to m6 |
| Verified passes | 30 | See "Verified passes" |
| Open items | 3 | See "Not settled" |

The board can be fabricated by JLCPCB and the real parts fit. Both MAJOR findings are one fix (see "Fix for M1 and M2"), tested on a scratch copy: DRC 0 errors, 0 unconnected.

Scale of the evidence: all geometry below was measured from the board file or Gerbers. Hand-soldering effects are engineering judgment, and nothing here has been built.

## Findings

### M1. MAJOR: `U1` pad 13 (the only XIAO GND pin) is solid to the pour on both layers

Geometry CONFIRMED. Soldering effect LIKELY; a build would settle it.

- `PCB/frostbite.kicad_pcb:12805` has `(zone_connect 2)` (solid). It is deliberate: `PCB/tools/gen_pcb.py:218-221`, comment "castellated GND pad: solid connection to the pour".
- A ring sampled 0.15 mm outside the true pad outline is 100 % copper on F.Cu and 89.3 % on B.Cu. Every other GND through-hole pad has spokes: J1.1 15-16 %, ENC1 lugs 15-20 %, ENC1 C 30 %.
- This pad is joined to about 3,558 mm² of F.Cu pour and 3,083 mm² of B.Cu pour, and it is the hardest joint on the board to heat.
- Why it matters more here: it is the sole GND link between the XIAO and the board. A cold joint takes out the LEDs, OLED and matrix reference together.
- Tried to disprove: my first ring was centred wrongly because of the footprint's drill offset, so I redid it from true outlines, and the override in the file confirms it. Removing the override in a scratch copy gave exactly one DRC error, `starved_thermal` on B.Cu, 1 spoke instead of 2. That is probably why it was made solid.

### M2. MAJOR: all 13 LED GND pads are flooded directly into the B.Cu pour

Geometry CONFIRMED. Soldering effect LIKELY; a build would settle it.

- Zone setting is `ZONE_CONNECTION_THT_THERMAL`, "SMD LED pads solid, THT thermal" (`gen_pcb.py:356`). Pad 3 perimeter touching copper: 49 to 78 % across LED1-13.
- The pads are small (0.82 × 1.25 mm) and belong to a heat-limited part. The datasheet's soldering-heat test is 260 °C, 10 s, 3 times.
- A cold GND joint turns that LED off.
- Reference boards with pours (mediapad, froskeys) use thermal mode for all pads, gap 0.5, spoke 0.5.
- Tried to disprove: the pour is 1 oz and already cut up by tracks, so the heat sinking is moderate rather than extreme. I rate this MAJOR because it repeats on 13 joints of a heat-sensitive part and the fix is one line. With thermal mode, perimeter copper falls to 11.5-18.3 % on the three pads sampled (LED1, LED10, LED13).

### Fix for M1 and M2 (tested)

On a scratch copy: removed the pad override, set the zones to `ZONE_CONNECTION_THERMAL`, set `min_resolved_spokes` to 1 in the project, refilled.

- Result: `kicad-cli pcb drc` 0 violations, 0 unconnected.
- U1.13 then has 2 spokes on F.Cu and 1 on B.Cu. Three 0.4 mm spokes carry the 0.48 A worst case comfortably (IPC-2221, 1 oz, 10 °C rise, about 1.2 A each).
- Real files to change: `PCB/tools/gen_pcb.py:218-221` and `:356`, `PCB/frostbite.kicad_pro:151`. Then rebuild.

### m1. MINOR: LED11 is crowded by SW3 pin 2

CONFIRMED.

- LED11 pad 3 (GND) is 0.838 mm from SW3 pad 2 (SW3_D). This is the closest LED-to-other-joint gap on the board; the next is 2.34 mm. The switch joint is soldered last, next to a finished LED joint, so bridging is the risk.
- LED11's polarity triangle is 0.045 mm from that same pad, flagged by DRC at the 0.15 mm rule. JLCPCB removes silk within 0.15 mm of pads, so its tip may be trimmed. The mark should stay readable, but that is UNVERIFIED until boards arrive.

### m2. MINOR: silk crosses all 14 XIAO pads in the Gerbers

CONFIRMED in the Gerbers. Effect cosmetic.

- `B_Silkscreen.gbr` has 23.9 mm of silk line inside the 14 U1 mask openings, 1.7 to 1.75 mm per pad. `(subtractmaskfromsilk no)` is set at `frostbite.kicad_pcb:82` and `build_all.sh:34` does not pass `--subtract-soldermask`. JLCPCB's KiCad guide says to select it.
- This should not reach the board: JLCPCB says anything "overlapping with solder pads or copper areas within 0.15mm will be removed". Four of the five reference boards also plot with the option off.
- This accounts for 21 of the 26 DRC warnings: 20 from U1 silk plus the LED11 triangle (m1). The other 5 are U1 silk at the board edge.
- Footprint silk strokes are thinner than JLCPCB's 0.15 mm minimum: 0.12 on D, ENC1 and J1, and 0.1 on LED marks (filled shapes). Text is exactly 1.0 / 0.15, at the limit. This is normal KiCad library artwork.

### m3. MINOR: no pin names at J1, and no side warning for the XIAO

CONFIRMED absent. Risk is a human factor, UNVERIFIED.

- The Hackpad guide warns the OLED must match the PCB, and `PCB/README.md` warns some clones swap GND and VCC. The board shows only "J1" and a square pad 1, so there is nothing to compare against at the bench. Reverse power can kill the module. Add `GND VCC SCL SDA` to B.Silkscreen beside the J1 pins; that side is free.
- The XIAO pads are bare on the top side with no marking there. Fitting it on top would mirror the pinout (5V onto D0). "XIAO HERE" is on the bottom only, which is correct but easy to miss. Add a small "XIAO on other side" to F.Silkscreen outside the OLED outline.

### m4. MINOR: LED cut-out has no margin against worst-case tolerances

LIKELY fine. Settle by test-fitting one LED on received boards.

- Nominal hole 3.4 × 3.0, body 3.2 × 2.8 ±0.1, JLCPCB outline tolerance ±0.2. Worst-case stack is 0.1 mm interference.
- This is only MINOR because Matyas, mediapad and stratum use the same care-package hole, and froskeys uses one of the same size. If one binds, the fix is a light pass with a needle file.

### m5. MINOR: documentation and CAD errors about the LED and the XIAO

CONFIRMED against primary sources. No fit consequence found.

| Where | Says | Source says |
|---|---|---|
| `docs/DIMENSIONS.md:106` | Gateron shows a "4.00 × 1.10 window, 4.0 from the housing centre line" | Those dimensions are the stem cross: their extension lines end on the cross. The drawing does not dimension the LED opening |
| `DIMENSIONS.md:85,106`, `PCB/README.md:128` | Lens is the 0.94 side; per-key bodies protrude 0.84, glow lenses 0.94 | The emitter is the 0.84 side: the cup in the side view (297 and 221 px) matches the two circles in the top view exactly. So per-key backs protrude 0.94 below B.Cu; glow emitters 0.84 |
| `CAD/frostbite_case.py:282` and CAD README | Glow LED occupies z −1.78 to 0, "0.82 mm under each LED" | The real LED hangs about 0.84 below the PCB, so the band pad gap is about 1.76, not 0.82. Safe for fit, but it may change how much light reaches the band |
| `DIMENSIONS.md:42` | XIAO 17.8 wide | Seeed wiki says 17.8; Seeed's own STEP measures 17.5 × 21.0 × 1.2 |
| `DIMENSIONS.md:83`, `frostbite_case.py:105`, `PCB/README.md:130` | USB overhang 1.4 / 1.42 | Seeed's footprint silk gives 1.42; Seeed's STEP gives 1.0. Unresolved between the two Seeed sources; see check 25 |
| `PCB/README.md`, BOM | "Soldered by its castellated pads" | True but incomplete: the real part has full holes and edge half-holes, and the footprint has plated holes, so the top-side method below also works |

### m6. MINOR: Gerber file names are not JLCPCB's preferred form

CONFIRMED. Will not stop the order.

JLCPCB's guide says it "prefers Protel filename extensions"; `build_all.sh:34` passes `--no-protel-ext`. ByteBoard, mediapad and orpheuspad were all submitted with `.gbr` names, and froskeys also shipped `drl_map` files. Dropping the flag is a one-word change if `verify/` does not depend on the names (not checked).

## Verified passes

### Top-side fit (item 1)

1. **Diodes are outside every switch footprint.** D1-9 modelled at JEDEC maximum 5.08 × 2.0: 1.525 mm to the 14.0 housing, 0.725 to a 15.6 flange (which sits above the plate anyway).
2. **D3/D6/D9 at the edge.** Body 1.0 mm from the board edge, pad 1.2 mm.
3. **Diode height under the plate.** Plate underside is 2.5 above PCB top; the clip pockets leave a 3.65 mm rib over each diode column. A flat diode (2.0 max) clears by 0.5. Diodes must lie flat, as CAD README step 2 says (≤ 2.2).
4. **OLED module.** Outline 2.5-40.5 × 7-19. Beneath it are only flat items: 10 U1 pads, one tented via, and J1's own pins. Nothing taller, so a 2.5 mm spacer clears it.
5. **XIAO pads under the OLED.** They are flush copper. No pins poke up with a flat-mounted XIAO.
6. **OLED to neighbours.** 2.65 mm to EC11 body, 1.45 to ENC1 lug pad, 7.5 to nearest switch.
7. **EC11.** 7.5 mm to SW3 housing. Same `CircularMountingHoles` footprint as ByteBoard.

### Switch footprint (item 2)

8. **The kit switch is 5-pin.** Gateron drawing KS-3Y10B050NW-X1 Rev 2 shows two side pegs (about 10.2 mm apart by scale) and "Layout of PCB" lists φ1.70 ±0.05 holes.
9. **Every hole matches the drawing.** Centre 3.988 (φ4.0 ±0.10), pegs 1.702 (φ1.70 ±0.05), pins 1.524 (φ1.50 ±0.05), at (−3.81, −2.54) and (+2.54, −5.08), pegs ±5.08.
10. **Same use as reference boards.** Pad coordinates and rotation match orpheuspad and froskeys exactly.
11. **Plated holes per the Gerber drill.** 18 pin holes at 1.524 (PTH), 18 peg + 9 centre (NPTH).

### LED cut-out (item 3)

12. **It is a real milled cut-out.** 16-segment closed loops on Edge.Cuts, in the Gerber as 13 internal loops of 3.499 × 3.137 (bbox including dogbones). Not pad-defined.
13. **Router compatible.** Dogbone radius is 0.500. JLCPCB support: "0.5mm milling tool radius ... minimum internal cutout width of 1mm". Body corners stay inside the dogbones: 0.40 from dogbone centre nominal, 0.47 worst case.
14. **The 0.175 mm pad change is safe.** Diff against the care package: only pad x (±2.6 to ±2.775), pad length (1.6 to 1.25), courtyard, and a hidden text moved. Edge.Cuts arcs are identical. Copper runs 2.15-3.40; outer end unchanged.
15. **Lead contact.** Lead tip at 2.94 (span 5.88), so 0.79 mm of lead on pad (0.74 at −0.05 tolerance). More than stratum (0.64 mm of a ±3.1 pad) and froskeys (0.54).
16. **Copper to cut-out** 0.40-0.45 mm, against JLCPCB's ≥ 0.2.
17. **LED centres under the switch window.** Hole and pads centre at switch +(0, 4.977). Scale reading of the drawing gives a round pocket about φ3.6 at about 5.2 from centre (3.4 to 7.0), opposite the pins. The φ2.4 emitter spans 3.78-6.18, fully inside. References: froskeys 5.08, Matyas 4.55.
18. **Pinout and chirality.** Datasheet top view: 1 VDD, 2 DOUT, 3 GND (chamfered lead), 4 DIN, counter-clockwise. Per-key from above and glow from below both run counter-clockwise, so both are right. Triangles sit at GND. Data chain DOUT to DIN verified from pad nets. A flipped LED cannot align its chamfered lead with the mark.

### Hand soldering (item 4)

19. **Which side to touch on the XIAO.** Seeed's STEP shows a full φ0.8 hole at ±7.75 and a half-hole at the ±8.75 edge. The board has plated φ1.0 holes at ±7.625, offset 0.125 from the XIAO's, with bottom pads reaching about 1.5-1.7 mm past the XIAO edge (range covers both the 17.5 and 17.8 widths). Either works: from the underside, iron on the exposed pad at the castellation; or from the top, iron on the top pad, feeding solder down the hole. All 14 pins are reachable both ways before the OLED goes on, and from the underside afterwards. No pad is unreachable.
20. **XIAO lies flat.** No exposed copper under it apart from its own pads; two tented vias only. Stratum and Matyas also put this footprint on B.Cu.
21. **LED pads.** Gap 0.68 (datasheet land pattern), 0.46 mm of pad past the lead tip for the iron. Same gap on built boards.
22. **Assembly order works.** XIAO, LEDs, diodes, EC11, OLED, then switches into the plate (CAD README). No joint is blocked by an earlier part: nearest switch pin is 7 mm from the XIAO body, J1 is 9 mm from it, and EC11 and J1 are soldered from the open underside. Do the XIAO before the OLED if using the top-side method. `led-test.uf2` runs before the switches go on.
23. **Thermal spokes elsewhere.** Gap 0.3, spoke 0.4. J1.1 and ENC1 C and lugs have 3 to 5 copper arcs. All switch and diode pads are signal nets, so the pour never touches them.

### Fabrication (item 5)

24. **The zip is current and complete.** Regenerated from the board with the same commands: identical except date stamps; `PTH.drl`, `NPTH.drl` and job file byte-identical. 9 Gerber layers, mm, decimal, absolute, as JLCPCB's guide asks.
    - Edge.Cuts: 216 segments, 0 odd-degree endpoints, 14 closed loops, outer 61.15 × 83.15. Job file's 61.25 × 83.25 is the same outline plus line width.
    - Drills: 94 plated (33 vias + 18 + 18 + 23 + 2) and 27 NPTH, all accounted for.

| Check | Measured | JLCPCB 1-2 layer |
|---|---|---|
| Track width | 0.2 min | ≥ 0.10 |
| Track to track | 0.30 | ≥ 0.10 |
| Round pad to track | 0.30 | n/a, DRC clean |
| Via to track | 0.30 | n/a, DRC clean |
| Via hole / diameter | 0.35 / 0.7, 0.4 / 0.8 | ≥ 0.15 / 0.25 |
| PTH annular ring | 0.25 min (U1.1) | 0.18 min, 0.25 recommended |
| Hole to hole (edge to edge) | 0.78 | ≥ 0.45 |
| Mask web | 0.50 (ENC1 pads), 0.186 pad to tented via | ≥ 0.10 |
| Copper to edge | 0.33 track, 0.36 via, 0.3 pour | ≥ 0.2 |
| Via in pad | None; 33 vias, all tented in both mask Gerbers | n/a |
| FR4 web, LED12/13 to board edge | 1.085 | No published limit found |

DRC at all severities on a scratch copy: 0 errors, 26 warnings (explained in m2), 0 unconnected.

### Current and USB (item 6)

25. **USB opening is where the connector is.** Sliced `production/Top.stl`: window x 14.25-27.75, z −6.83 to +1.17 at three depths. Seeed's STEP, flat-mounted: shell x 16.53-25.47, z −4.405 to −1.2, centre −2.80 (case assumes −2.83). Over 2.2 mm margin on every side. XIAO is flush with y = 0 by pad positions.
    - With either overhang (1.0 or 1.42) a plug's overmold must enter the window 5.6 to 6.0 mm, so cables up to 13.5 × 8 seat.
26. **+5V.** Datasheet 12 mA × 3 + 1 mA IC = 37 mA per LED, 481 mA for 13. Nodal solve of every real +5V segment: worst drop 45.1 mV (LED12).
    - Highest branch 0.48 A on 0.5 mm track. Narrowest +5V track 0.375 mm (17.3 mm total), carrying at most 0.30 A. IPC-2221 allows 1.17 A there.
27. **GND return.** Rasterised solve of both pours with tracks and 9 layer stitches: worst rise 3.1 mV. Worst total loss 48 mV. All LED GND pads in the main net.
28. **USB budget.** 481 mA is close to 500 mA at full white, but firmware caps it: `POWER_BUDGET` is 40 % of full scale (`keymap.c:93`), and `max_brightness` is 200.

### Silkscreen (item 7)

29. **Polarity marks survive assembly.** Square K pads on both sides and "K" beside each; LED triangles beside each pad 3; J1 square pad 1. Diode body hides only the footprint's cathode bar.
30. **Text is on the right side and readable.** All bottom text mirrored, all top text not. 1.0 / 0.15 minimum. "XIAO HERE" stays visible with the XIAO on; `U1`, `USB-C`, `XIAO` and `Seeed Studio` are hidden after placement, which is harmless. Only the U1 graphics and the LED11 triangle were flagged near pads, so no text will be removed.

## Not settled

| Item | Why open | What settles it |
|---|---|---|
| Voltage drop inside the XIAO's 5V path | Seeed's wiki does not say, and the schematic URL I tried returned 403. The 45 mV above covers only this board | XIAO schematic, or measure 5V at LED12 |
| USB overhang 1.0 vs 1.42 | Seeed's own STEP and footprint disagree | Calipers on a real XIAO. Fit passes with both |
| Kit OLED header and module back | Not measured on a real part: whether the header comes fitted, pin length, and height of parts on the module back | Inspect the kit module |

## Sources and method

- JLCPCB capabilities: https://jlcpcb.com/capabilities/pcb-capabilities
- JLCPCB KiCad guide: https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-8
- JLCPCB silk rules: https://jlcpcb.com/blog/technical-guidance-character-design-specifications
- JLCPCB cut-out tool, as relayed in 2023 from JLCPCB support; JLCPCB's own capabilities page does not state it: https://techoverflow.net/2023/04/12/jlcpcb-which-milling-tool-radius-is-used-for-internal-cutouts
- OPSCO SK6812MINI-E Rev 02: https://cdn-shop.adafruit.com/product-files/4960/4960_SK6812MINI-E_REV02_EN.pdf
- Gateron KS-3Y10B050NW-X1 Rev 2: https://cdn.shopify.com/s/files/1/0565/8070/2297/files/SPEC-KS-3Y10B050NW-X1-Yellow_Switch.pdf?v=1675841028
- Seeed XIAO RP2040: https://wiki.seeedstudio.com/XIAO-RP2040/ and its 3D model ZIP, https://files.seeedstudio.com/wiki/XIAO-RP2040/res/seeed-studio-xiao-rp2040-3d-model.zip
- Tools: KiCad 10.0.8 `pcbnew` and `kicad-cli`, gerbonara, CadQuery/trimesh, numpy/scipy. Copper 1 oz (35 µm) at 20 °C. Scripts and scratch copies are in the session scratchpad; a scratch venv held pymupdf, pillow, ezdxf, numpy and scipy.
- Reference comparison used: ByteBoard, Matyas, SplashPad, froskeys, mediapad, orpheuspad, stratum-macropad. chinnyyys-hackpad's board file has no footprints, so it was not usable.
