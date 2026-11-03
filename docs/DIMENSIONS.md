# Frostbite — verified part dimensions (Agent F)

All values in mm unless noted. `FB.dims` in `dims.js` mirrors this table. Original keys and nesting are unchanged; extra keys were added under `// ---- added detail`. Every leaf in `FB.dims` is a positive finite number. String data such as pin names lives only in this file.

Confidence: **H** = read directly off the manufacturer drawing or datasheet. **M** = a reputable secondary source, or read from a drawing scale. **L** = typical or estimated value.

Kit part list (from the Hackpad guide at https://hackpad.hackclub.com/parts, read from the site bundle): 16 MX-style switches (Gateron KS-3 Yellow, spec KS-3Y10B050NW-X1), 2 Alps EC11E encoders with push switch, a 0.91" OLED (pin order GND-VCC-SCL-SDA), 16 white blank DSA caps, 16 SK6812 MINI-E, 6 M3×16 screws, 6 "M3x5mx4mm" heat-set inserts (the AliExpress Voron-guide insert). The same guide's case notes say: "use a 4.7mm hole for the insert", "make a 4.7mm diameter hole, 4mm deep", 3.4 mm for screw pass-through, 2.9 mm to screw straight into plastic.

## Changed values (old → new)

| key | old | new | why |
|---|---|---|---|
| `ec11.body` | 12.5 | **12.0** | Alps drawing: the body is 11.7 × 12.0 (6 + 6). The 12.5 figure is the outer span of the mounting-lug slots (now `ec11Detail.lugOuterSpan`). |
| `ec11.shaftAbovePcb` | 20.0 | **24.5** | Alps gives shaft length L1 = 20 measured from the body top. The body is 4.5 tall, so the tip is 24.5 above the PCB. The drawing dimensions 24.5 overall and (20) as reference. |
| `heatSetInsert.od` | 4.0 | **5.0** | "M3x5x4" (Voron) means M3, OD 5.0, L 4.0 (ruthex / CNC Kitchen Voron insert: D1 5.0, L 4.0). |
| `heatSetInsert.holeDiameter` | 4.0 | **4.7** | The Hackpad guide gives 4.7 mm, 4 deep. ruthex recommends 4.4. Kept the kit guide's value, which is also the easier fit. A 4.0 hole would crack bosses. |
| `capHeightXDA` | 9.1 | **9.5** | Sources give 9.1 to 9.56. Kept the taller, conservative value for height and clearance. |

Every other original value checked out and is unchanged.

## Table

| key | value | unit | source | note |
|---|---|---|---|---|
| `pitch` | 19.05 | mm | Cherry MX datasheet (https://cdn.sparkfun.com/datasheets/Components/Switches/MX%20Series.pdf), the 0.75" standard | H |
| `switchCutout` | 14.0 | mm | Cherry: 0.551" ±0.002. Gateron KS-3Y10B050NW drawing: housing 14.00 ±0.03 (https://cdn.shopify.com/s/files/1/0565/8070/2297/files/SPEC-KS-3Y10B050NW-X1-Yellow_Switch.pdf?v=1675841028) | H. For a printed plate, test 14.0 to 14.1, because FDM holes print about 0.1 undersize. |
| `plateThickness` | 1.5 | mm | Cherry: 0.06" ±0.004 (1.5 ±0.1) for clip engagement | H. A printed plate can be thicker elsewhere but must be 1.5 at the clips, for example with an underside pocket. |
| `pcbThickness` | 1.6 | mm | JLCPCB default 2-layer | H |
| `switchHeightAbovePlate` | 6.6 | mm | Cherry/Gateron: 11.6 (PCB to housing top) − 5.0 | H. This is the **housing** top. The stem rises another 3.6. |
| `switchHeightBelowPlate` | 5.0 | mm | Cherry 0.20"; Gateron 5.00 (plate top to housing bottom / PCB top) | H. Excludes the 3.3 pins. |
| `capBottom` | 18.2 | mm | SP DSA base 0.718" ≈ 18.24 (SP keycap spec page https://spkeyboards.com/blogs/product-guides/keycap-family-specs, which returned HTTP 429 when fetched, so this is from memory of the SP drawing) | M |
| `capTopDSA` | 12.7 | mm | SP DSA top 0.500" (same source) | M |
| `capTopXDA` | 15.9 | mm | XDA top is about 16. Vendor drawings vary (https://akkogear.eu/blogs/news/xda-keycaps-overview) | L–M |
| `capHeightDSA` | 7.6 | mm | SP DSA 0.291" = 7.39 (https://deskthority.net/wiki/Signature_Plastics_DSA_family). Generic DSA blogs say 7.6. | M. Kept 7.6 as the conservative value. |
| `capHeightXDA` | 9.5 | mm | 9.1 (most blogs, https://hirosarts.com/blog/what-are-xda-profile-keycaps) to 9.56 | L–M, conservative |
| `oledModule.w/h` | 38.0 / 12.0 | mm | KiCad footprint linked by the Hackpad guide (https://github.com/gorbachev/KiCad-SSD1306-0.91-OLED-4pin-128x32.pretty/blob/master/SSD1306-0.91-OLED-4pin-128x32.kicad_mod): board outline 38 × 12. Vendor I²C module listing "38.0 × 12.0" (https://www.buydisplay.com/0-91-inch-128x32-oled-display-module-serial-spi-ssd1306-white-on-black). | H for the board outline. Some clones are 35.8 to 36 long (Waveshare 36 × 12.5), so 38 is the conservative value. |
| `oledModule.t` | 3.6 | mm | One vendor lists 38 × 12 × 2.7. Glass 1.45 + board about 1.2 + back-side parts. | M. Kept 3.6 as the envelope. Add the header spacer (2.5) if the module is soldered on a header. |
| `oledActive` | 22.4 × 5.6 | mm | 22.384 × 5.584 (multiple SSD1306 0.91" panel datasheets, e.g. https://marketplace.oled-info.com/view/12/Wc091-12832) | H |
| `ec11.body` | 12.0 | mm | Alps EC11 catalog, EC11E vertical with push switch (https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/6727/alps_alps-s-a0008379064-1-1733314-1-13.pdf, p.263): 11.7 × (6+6) | H |
| `ec11.shaftAbovePcb` | 24.5 | mm | Same drawing: 24.5 overall, L1 (20) from the body top. Alps product page "actuator length 20 mm", φ6 (https://tech.alpsalpine.com/e/products/detail/EC11E15244G1/). The distributor height "24.50" matches. | H, for the kit's 20 mm (H20mm footprint) part |
| `ec11.knobDiameter` | 18.0 | mm | Typical aftermarket knob (15–20 range) | L. This is a design choice. |
| `xiao.w/h` | 17.8 / 21.0 | mm | Seeed wiki "21 × 17.8" (https://wiki.seeedstudio.com/XIAO-RP2040/). Seeed KiCad footprint outline is 20.975 × 17.8 (https://github.com/Seeed-Studio/OPL_Kicad_Library/blob/master/Seeed%20Studio%20XIAO%20Series%20Library/XIAO-RP2040-DIP.kicad_mod). | H. Some retailers say 20 × 17.5. Kept the larger value. |
| `xiao.t` | 3.5 | mm | Retail listings "20 × 17.5 × 3.5" (https://shop.pimoroni.com/en-us/products/seeed-xiao-rp2040) | M. Size cavities to `xiaoDetail.tMax` (4.5). |
| `sk6812MiniE` | 3.2 × 2.8 | mm | OPSCO SK6812MINI-E datasheet rev 02, p.4 (https://cdn-shop.adafruit.com/product-files/4960/4960_SK6812MINI-E_REV02_EN.pdf) | H |
| `heatSetInsert.od` | 5.0 | mm | ruthex M3 Voron insert: D1 5.0, D2 4.25, L 4.0, hole 4.4, min wall 1.3 (https://www.3djake.com/ruthex/threaded-insert-m3-voron-100-pieces). CNC Kitchen Voron M3×5×4 (https://3djake.ch/en-CH/cnc-kitchen/threaded-inserts-m3-voron). | H |
| `heatSetInsert.length` | 4.0 | mm | same | H |
| `heatSetInsert.holeDiameter` | 4.7 | mm | Hackpad guide (https://hackpad.hackclub.com/parts, case section) | H for the kit. ruthex says 4.4. |
| `m3Head` | 5.5 | mm | ISO 4762 / DIN 912 M3 socket head, dk max 5.5, k 3.0 | H |
| `printTolerance` | 0.3 | mm | Hackpad contract 0.2–0.4 per side | H for the project rule |
| `minWall` | 2.0 | mm | FDM practice: at least 4 perimeters at 0.4 mm nozzle for a structural, light-tight shell. 1.2 is printable but flexes and glows through. | M |
| `switchHousingTop` | 15.6 | mm | Cherry 0.61" (15.6). Gateron KS-3 drawing 15.40. | H. Kept 15.6 (conservative). |
| `switchHousingBottom` | 14.0 | mm | Gateron 14.00 ±0.03 | H |
| `switchClipSpan` | 14.9 | mm | Gateron 14.90 ±0.3 | H |
| `switchStemAboveHousing` | 3.6 | mm | Cherry 0.14" | H |
| `switchStemTopAbovePlate` | 10.2 | mm | 11.6 + 3.6 − 5.0. The Gateron drawing scales to about 10.15. | H |
| `switchTravel` | 4.0 | mm | Gateron "Total travel 4.0 max", pretravel 2.0 ±0.6 | H |
| `switchPinLength` | 3.3 | mm | Cherry 0.13" (3.30), Gateron 3.30 | H |
| `switchCenterPostLength` | 2.8 | mm | Gateron 2.80 ±0.10, post φ3.85 | H |
| `plateGapBelow` | 3.5 | mm | 5.0 − 1.5 | H |
| `switchPins.*` | centre hole 4.0, peg holes 1.7 at (±5.08, 0), contact holes 1.5 at (−3.81, −2.54) and (+2.54, −5.08) | mm | Cherry PCB layout (φ0.157", φ0.067", φ0.059", 0.05" grid). Coordinates are KiCad top view, y down, relative to the switch centre. Values are stored as magnitudes. | H. The kit KS-3 Y10B050NW is a 5-pin (PCB-mount) switch, so the peg holes are needed or the pegs must be clipped. |
| `capRimAbovePlate` | 6.0 | mm | Estimate: stem top 10.2 minus about 4 mm socket engagement | L. Must be at least 4 (travel) for bottom-out clearance. |
| `capTopAbovePlateDSA` / `XDA` | 13.6 / 15.5 | mm | rim + cap height | L |
| `oledGlass` | 30.0 × 11.5 × 1.45 | mm | Common 0.91" panel ("30.00 × 11.50 × 1.45", buydisplay / oled-info listings). The KiCad silk shows the panel spanning 3.5–33 on the 38 board. | M. Some panels are 1.2–1.34 thick. |
| `oledGlassInset` | 3.5 | mm | KiCad footprint silk line at x = 3.5 (non-header end) | M |
| `oledHeader` | 4 pins, 2.54 pitch, row 1.5 from board end, spacer 2.5 | mm | KiCad footprint pads at x 36.5, y 2.19/4.73/7.27/9.81 (centred on the 12 mm height). Pin order **GND, VCC, SCL, SDA** starting from pad 1 (Hackpad guide: "MAKE SURE YOUR PCB MATCHES"). | H |
| `oledGlassTopAbovePcb` | 5.2 | mm | 2.5 header plastic + about 1.2 board + 1.45 glass | L–M. This is about the plate-top height (5.0). |
| (no key) OLED mounting holes | none | — | The common 0.91" 4-pin I²C module has **no mounting holes**, unlike the 0.96" module's four M2 holes. It is held by the header plus a printed clamp or ledge. | M |
| `ec11Detail.bodyW/bodyD/bodyH` | 11.7 / 12.0 / 4.5 | mm | Alps p.263 (side view: 4.5 from mounting surface to body top) | H/H/M |
| `ec11Detail.bushingDiameter/Height` | 7 / 7 | mm | Alps p.268 flat type: L1 20 → LB 7, φ7 bushing (M7 thread only on EC11B) | H |
| `ec11Detail.shaftDiameter` | 6.0 | mm | Alps φ6 | H |
| `ec11Detail.shaftFlat` | 4.5 | mm | Alps: 4.5 measured across the D-flat | H |
| `ec11Detail.flatLength` | 10 | mm | Alps: 10 on push-switch versions (12 without the switch) | H |
| `ec11Detail.shaftL1Short/L1/L1Long` | 15 / 20 / 25 | mm | Alps flat-type table (L1 from the body top). Tip above PCB = L1 + 4.5 → 19.5 / 24.5 / 29.5. Knurled (18-tooth serrated) comes in 20 / 25. | H. The 15 mm option is listed as "does not comply with EC111" and may not be stocked with a switch. |
| `ec11Detail.pinPitch` | 2.5 | mm | A-C-B row 2.5 pitch (5 total) | H |
| `ec11Detail.switchPinSpacing` | 5.0 | mm | D-E 5.0 apart | H |
| `ec11Detail.pinRowSpacing` | 14.5 | mm | ABC row 7.5 from body centre, DE row 7 on the other side | H |
| `ec11Detail.pinHole` | 1.0 | mm | "5-φ1 holes" | H |
| `ec11Detail.lugOuterSpan` | 12.5 | mm | Lug slots about 1.5 wide, 12.5 outer-to-outer (centres about 11) | M (read from the drawing) |
| `ec11Detail.pinLength` | 3.5 | mm | Terminals and lugs 3.5 below the mounting surface | H |
| `ec11Detail.pushTravel` | 0.5 | mm | 0.5 (or 1.5 on some part numbers) | H |
| `knobTypical` | φ15–20, height about 15, bore about 12 deep | mm | Typical aluminium knobs for 6 mm D shafts | L. Knob bottom sits about 1 mm above the bushing top, so about 12.5 above the PCB (about 7.5 above the plate top), below the cap tops (about 13.6). |
| `xiaoDetail` | pitch 2.54, rows 15.24 apart, 7 per side, tMax 4.5 | mm | Seeed KiCad footprint pads at ±7.62. tMax is a conservative envelope: 3.26 USB-C receptacle + board. | H / H / H / L |
| `xiaoUsbC` | w 9.0, h 3.3, overhang 1.4 | mm | Seeed footprint silk: USB outline y ±4.5, extends to x 11.95 vs board edge 10.55 → 1.4 overhang. USB-C receptacle shell is typically 8.94 × 3.26. | M |
| `usbPlugRelief` | 13 × 8 | mm | USB-C spec recommended max plug overmold about 12.35 × 6.5, plus clearance. Fat cables are larger. | M |
| `sk6812Detail` | t 1.78, lead span 5.88, lens 0.94 below leads, hole 3.4 × 3.0 | mm | Datasheet p.4: 1.78 total, 0.84 above the lead plane, so 0.94 below; the recommended PCB opening is the 3.2 × 2.8 body | H. The 3.4 × 3.0 hole is the datasheet body + 0.1 per side for fab tolerance (L–M). |
| `heatSetHoleDepth` | 4.0 | mm | Hackpad guide "4mm deep". Leave a φ3.4 continuation below it if the M3×16 runs past the insert. | H |
| `heatSetBossOd` | 8.0 | mm | 4.7 + 2 × 1.6 wall (ruthex minimum wall 1.3) | M |
| `m3Clearance` / `m3SelfTap` | 3.4 / 2.9 | mm | Hackpad guide | H |
| `m3HeadHeight` / `m3Counterbore` | 3.0 / 6.0 | mm | ISO 4762 k = 3.0; counterbore = 5.5 + 0.5 | H / M |
| `m3ScrewLength` | 16 | mm | Kit M3×16 | H |

Print tolerances: 0.2–0.4 per side where printed parts meet the PCB (Hackpad). PCB pockets: PCB outline + 0.3 per side, so the pocket is 0.6 larger than the board. Holes print about 0.1–0.2 undersize on FDM, so oversize them or ream. Minimum printable wall is about 0.8–1.2 (2–3 perimeters). Use 2.0 for shell walls.

## Fit issues for lead

Checked numerically against `layouts.js` with the corrected dims. The calculation script is in Agent F's scratchpad and is not shipped.

1. **The OLED module board overhangs the content area (stratum9, pocket6, stagger9, mirror9).** `oled` is placed as the 30 × 11.5 *glass*, at x = 0 (or ending at W). The 38 × 12 board extends 3.5 past the glass on one end and 4.5 on the header end, so the board spans x = −3.5…34.5 (or −4.5…33.5) and runs 3.5–4.5 mm into the bezel wall. **Fix:** stratum9/pocket6/stagger9 `oled.x = 4` (glass 4–34, board 0.5–38.5 with the header toward the dial). mirror9 `oled.x = W − 34 = 23.15` (header toward the dial). Both leave about 2.4 mm to the EC11 lugs and about 2.6 mm to the EC11 body. y is fine: board y 5–17, first switch cutout at y 24.5, so 7.2 mm of plate web.
2. **wide9: a 38 mm module cannot fit a 36 mm control column.** With glass at x = W3 + 3, the board spans 56.65–94.65. That overlaps the keycaps (which end at 56.7, switch cutouts at 54.6) and the right edge (93.15). **Fix:** column 36 → **42** (W = 99.15, still ≤ 100 PCB). `oled.x = W3 + 5.5` (board W3 + 2 … W3 + 40), dial x = W3 + 21.
3. **The plate needs body-size cutouts over the OLED and EC11, not window-size ones.** The plate underside is 3.5 above the PCB. The EC11 body is 4.5 tall, so it collides by 1.0. The OLED board on a 2.5 header sits at 2.5–3.7, colliding by 0.2. Plate openings: EC11 ≥ 12.6 × 12.6 (13.1 to clear the lugs). OLED ≥ 38.6 × 12.6 (module + 0.3 per side). The glass top ends up about flush with the plate top (≈ 5.0–5.2 above the PCB). That works well for a frosted top-plate window.
4. **Knob size.** At dial x = W − 10 or x = 10 with y = 11, an 18 mm knob leaves 2.4 mm to the nearest keycap and 1.0 mm to the content edge. A 20 mm knob leaves 1.4 to the caps and **0.0** to the edge, so it overhangs the shell wall on tray/deep-dish plates. The knob bottom sits about 7.5 above the plate, below the DSA cap tops (about 13.6), so the plan gap matters. **Fix:** cap knobs at 18 mm, or move dials to x = W − 11 / 11 and y = 11 for 20 mm. Want ≥ 1.5 to caps and ≥ 1 to the wall. console4: an 18 knob overlaps the OLED module ends by up to 0.6 in plan. This is harmless, because the knob is about 7 mm above the board. The plate web between the OLED and EC11 openings there is only about 2.0 on the right side, so keep it ≥ minWall.
5. **Bezel and heat-set bosses.** A boss needs φ8 (4.7 hole + 1.6 walls) plus 0.3 to the PCB, so 8.3. **Bezel 6 cannot hold an insert boss** (it fails by about 2.3). The PCB would need mounting holes inside the content area instead, which the guide recommends ("use the M3 mounting hole footprint"). **Bezel 9 works on straight edges** (0.55 margin on each side), but **not on the corner diagonal when corner ≥ 8**. The margin to the outer skin is 3.05 / 1.39 / −0.26 for R = 8 / 12 / 16, against 3.95 needed. Place inserts on the side walls: for R = 12 start at y ≥ 0 from the content corner, for R = 16 at y ≥ 3.5. Bezel 12 is fine at corners up to R = 8. Note: constraints.js `screws-top-bezel` computes 4.7 + 2 × minWall = 8.7 ≤ 9, which is consistent.
6. **Keycap to wall.** Caps (18.2 in a 19.05 cell) sit **0.425** from the content edge. If a shell wall or lip rises above the plate (tray, deep-dish, flush), caps rub and can bind at 4 mm travel. **Fix:** inner wall ≥ 1.0 from caps, which means offsetting the shell inner outline by about +0.6 from the content area. Equivalently, the PCB/plate is about 1.2 larger than `W/H`. The guide's "≤ 100 mm PCB" still holds.
7. **USB-C through a 9–12 mm wall.** The XIAO sits on the underside. Its USB-C overhangs the XIAO board by 1.4 (9 × 3.3). Put the XIAO with its USB lip at the PCB edge. A 9 mm bezel is deeper than the plug's 6.65 mm mating length, so the wall needs a **≥ 13 × 8 relief** for the cable overmold (`usbPlugRelief`), centred on the receptacle. Otherwise only bare-plug cables will seat. The bottom-shell floor needs ≥ `xiaoDetail.tMax` (4.5) + 0.5 air under the PCB, or + 2.5 if the XIAO is socketed on headers.
8. **Height model note (constraints.js, informational).** With the corrected `ec11.shaftAbovePcb` = 24.5, `dialTop` rises 4.5 mm. That is real: the kit encoder's shaft tip is about 19.5 above the plate. A knob adds about +3 over the tip (height 15, bore 12). `capTop = plateTop + 6.6 + capH` over-estimates by about 0.6 (the real cap top is about 13.6 above the plate for DSA), which is fine as an upper bound. If a lower dial is wanted, use the L1 = 15 shaft (tip 19.5 above PCB), but check that a switch version is stocked.
9. **SK6812 MINI-E reverse mount.** The lens protrudes 0.94 below the lead plane into a 3.4 × 3.0 PCB hole, so on a 1.6 PCB it stays inside the board. Under-glow diffusers can sit right under the PCB. Per-key LEDs shine up through the hole into the switch's LED window. The Gateron drawing shows a 4.00 × 1.10 window, 4.0 from the housing centre line; check its orientation against the footprint.
10. **The kit switch is 5-pin.** KS-3Y10B050NW is a PCB-mount part. The footprint needs the φ1.7 peg holes at ±5.08, or the builder clips the pegs.
