# Frostbite electrical audit

Audit of what would stop the real, soldered board working. It covers `PCB/frostbite.kicad_pcb` (commit d58ec31) against manufacturer data and the eight reference boards. Nothing has been built: every result comes from documents, models and board data, so no result here is a bench measurement.

## Result

**0 BLOCKER, 2 MAJOR, 8 MINOR.** The highest-risk question, whether the underside XIAO is mirrored, has a clear answer: it is **not** mirrored. Every pad maps to the right net.

| # | Severity | Status | Finding |
|---|---|---|---|
| E1 | MAJOR | LIKELY | Glow LEDs must go in the opposite way up from the key LEDs, and neither the board nor the build docs tell the builder. Done the natural way, the glow chain goes dark and two DOUT pins drive each other. |
| E2 | MAJOR | LIKELY | The Ø2.6 round encoder lug holes make the barbs deflect about 0.59 mm, against about 0.30 mm for Alps' own slot. Six of seven reference boards use slots. |
| E3 | MINOR | CONFIRMED out of spec; practical effect UNVERIFIED | 3.3 V LED data is below VIH (3.5 V at 5 V) unless VBUS sags to about 4.71 V. |
| E4 | MINOR | CONFIRMED geometry; failure UNVERIFIED | Tented `LED_DIN` and `COL0` vias sit directly under the XIAO's bare VIN and GND back pads. |
| E5 | MINOR | CONFIRMED | No LED decoupling capacitors, which the datasheet calls essential. `docs/VERIFICATION.md` still lists them as a requirement. |
| E6 | MINOR | CONFIRMED | J1 has no pin labels on silkscreen, and some 0.91" modules list a different pin order. |
| E7 | MINOR | CONFIRMED | XIAO RESET and BOOT face the case floor with no access hole. Bootmagic is the only recovery with the case closed. |
| E8 | MINOR | UNVERIFIED | Lens position against the Gateron LED window depends on an ambiguous dimension. |
| E9 | MINOR | UNVERIFIED | `resolution: 4` registers every second click if the kit encoder is a true EC11E. |
| E10 | MINOR | CONFIRMED | Docs swap the MINI-E's lens and back heights. No functional effect. |

## Verified passes

### 1. XIAO on the underside: correct, not mirrored (CONFIRMED)

**The real part.** Seeed's front render, with USB up and components facing the viewer, shows D0–D6 down the left and VBUS, GND, 3V3, D10, D9, D8, D7 down the right. D0 and VBUS are the pair next to the USB end. Seeed's back render, with USB up, shows the board's own silk: `VCC GND 3V3 10 9 8 7` on the **left** and `0 1 2 3 4 5 6` on the **right**.

**The physical case.** The XIAO hangs below the PCB, back against B.Cu and components facing down (`docs/BOM.md:12`, "face-down"). Looking down through the PCB from above, you see the XIAO's **back**. So the correct top-view layout is the back render: D0 top-right, 5V top-left.

**The board** (`pcbnew` absolute coordinates, top view, y down):

| Pad | XIAO pin | Position | Net | Check |
|---|---|---|---|---|
| 1 | D0 | 28.625, 2.88 | ROW0 | right, USB end |
| 2 | D1 | 28.625, 5.42 | ROW1 | right |
| 3 | D2 | 28.625, 7.96 | ROW2 | right |
| 4 | D3 | 28.625, 10.50 | COL0 | right |
| 5 | D4 | 28.625, 13.04 | SDA | right |
| 6 | D5 | 28.625, 15.58 | SCL | right |
| 7 | D6 | 28.625, 18.12 | LED_DIN | right, far end |
| 8 | D7 | 13.375, 18.12 | ENC_A | left, far end |
| 9 | D8 | 13.375, 15.58 | ENC_B | left |
| 10 | D9 | 13.375, 13.04 | COL1 | left |
| 11 | D10 | 13.375, 10.50 | COL2 | left |
| 12 | 3V3 | 13.375, 7.96 | +3V3 | left |
| 13 | GND | 13.375, 5.42 | GND | left |
| 14 | 5V | 13.375, 2.88 | +5V | left, USB end |

The native footprint has pad 1 at (−7.625, −7.62), left and at the USB end, matching the front render. Flipped at rotation 180 it lands at (+7.625, −7.62) from the centre (21.0, 10.5). So x mirrors and y does not, and the D0 and 5V end stays at low y. That is the USB end pointing at y=0. The footprint has no USB graphic, so this rests on pad numbers.

**Attempted disproof:**

- **Stratum** has the same flip: U1 on B.Cu, rotation 180, pad 1 at +7.625, pad 14 at −7.625, USB end toward its top edge. Its firmware confirms the pad numbers under that flip: pad 1 ROW0 = GP26 (D0), pad 7 COL1 = GP0 (D6), pad 8 COL2 = GP1 (D7), pad 9 ENC-A = GP2 (D8), pad 10 ENC-B = GP4 (D9), pad 11 LED-DATA = GP3 (D10).
- **Matyas** also uses B.Cu at rotation 180 with pad 1 on the right at the USB end.
- **Orpheuspad, mediapad** on the top side have pad 1 at left and pad 14 at right, the expected mirror of this.
- The opposite mounting, components against the PCB, is ruled out physically: the USB shell and can would hit the board.

**GPIO:** all eleven Dn to GPn mappings in `design.json` match the Seeed table, and `keyboard.json` uses the same pins. Seeed's wiki calls GP6/GP7 "I2C0", but that is wrong: RP2040 datasheet p.13 lists GPIO6 as I2C1 SDA and GPIO7 as I2C1 SCL. The firmware's `I2C_DRIVER I2CD1` (`config.h:10`) and `RP_I2C_USE_I2C1 TRUE` (`mcuconf.h:9`) are correct per QMK's RP2040 table.

### 2. SK6812 MINI-E pins and sides: correct (CONFIRMED)

**Datasheet (Rev 02, p.4).** In the view with the ring and chamfer, 1 VDD is top-left, 2 DOUT bottom-left, 3 GND bottom-right (chamfered lead), 4 DIN top-right. The side view shows flat leads 0.84 mm below that face and 0.94 mm above the rear. The reflector taper opens towards the ring face, so that face is the lens. The rear has a rib and a small round mark.

The application circuit on p.9 shows different pin numbers (1 DIN, 2 VDD, 3 DOUT, 4 VSS). Its own drawing is labelled SK6812MINI, a different package. The p.4 table is the MINI-E's and the footprint follows it.

**Key LEDs (LED1–LED9): correct.** Copper is on B.Cu, the body goes in from below, and the lens points up through the cut-out. In top view, pad 1 +5V is left-upper, 2 DOUT left-lower, 3 GND right-lower, 4 DIN right-upper at (∓2.775, −0.853 / +0.647). That is the datasheet lens view, because the lens faces the viewer. Adafruit confirms the mount: the "body of the LED will nestle inside of the cutout" and the light "shines through a cutout".

The same layout appears on froskeys (+5V, DOUT, GND, DIN at those four corners) and on the care-package footprint used by stratum and Matyas. Pad spacing differs only in x (care package ±2.6, Frostbite ±2.775).

**Pad fit: passes.** Pads span 2.15–3.40 mm from centre; the datasheet lead tip is at 5.88/2 = 2.94, and its recommended land ends at 1.6 + 1.8 = 3.4. So each lead sits on 0.79 mm of pad, with 0.46 mm spare for the fillet. Pitch 1.5 mm matches 0.82 + 0.68.

**Glow LEDs (LED10–LED13): electrically correct for lens-down.** Copper is on B.Cu, and from above the layout is mirrored: pad 1 right-upper, 2 right-lower, 3 left-lower, 4 left-upper. Looking up from below, that becomes 1 top-left, 2 bottom-left, 3 bottom-right, 4 top-right, which is the datasheet lens view with the lens facing the viewer below the board. Because the leads are flat, the part can be soldered either way up, with the 0.94 mm rear inside the 1.6 mm board. Lens-down is mechanically valid, but see E1.

**Band path: passes.** The GlowBand has light pads under each LED, with their tops 2.6 mm below the PCB (`CAD/README.md`). The lens face is at −0.84 mm.

**Cut-outs and marks: pass.** Cut-out centres match pad centroids exactly on LED1 (11.525, 38.502), LED10 (5.000, 25.297) and LED13 (5.000, 80.497). The B.SilkS triangle is beside pad 3 on all three, the lead the datasheet chamfers. Body 3.2 × 2.8 fits the 3.4 × 3.0 cut-out, the same outline as the care package.

**Key LED side of switch: passes.** LEDs sit at switch +y, opposite the switch pins at (−3.81, −2.54) and (+2.54, −5.08). Orpheuspad and froskeys have those exact pad positions. KiCad's Cherry footprint on stratum, mediapad, Matyas, ByteBoard and SplashPad has the same two positions with pad numbers swapped. The exact offset is E8.

### 3. Data chain and power as routed: correct (CONFIRMED)

I walked each net geometrically, joining track ends, vias and pad shapes by my own code rather than KiCad's connectivity (`walk.py` in the scratchpad). Each net formed exactly one connected group, on tracks alone with no zone fill:

`U1.7 → LED1.4`, `LED1.2 → LED2.4`, `LED2.2 → LED3.4`, `LED3.2 → LED4.4`, `LED4.2 → LED5.4`, `LED5.2 → LED6.4`, `LED6.2 → LED7.4`, `LED7.2 → LED8.4`, `LED8.2 → LED9.4`, `LED9.2 → LED10.4`, `LED10.2 → LED11.4`, `LED11.2 → LED12.4`, `LED12.2 → LED13.4`. LED13 DOUT is unconnected.

All thirteen pad 1s and `U1.14` are one +5V group (minimum width 0.375 mm). All thirteen pad 3s, `U1.13`, `J1.1`, `ENC1.C` and both lugs are one GND group. Physical order matches `keys[].led` and `rgb_matrix` indices. GND pours are filled on both layers; B.Cu has one small 5.5 mm² second island, which is harmless because the tracks connect everything anyway.

**Gerbers match the board:** regenerated F.Cu, B.Cu, F.Mask, B.Mask and Edge.Cuts differ by 0 lines from `production/gerbers.zip`, excluding date and attribute lines.

### 4. EC11E pins: correct (CONFIRMED)

The Alps catalogue (Drawing No. 3, EC11E15244B2) has A, C, B left to right with those terminals at the bottom of the shaft-end view, 2.5 mm pitch, 7.5 mm from the shaft, and D/E 7.0 mm the other side, 5 mm apart. Its STEP model has pins within 0.08 mm of those positions.

The board, with shaft at (49.15, 13.0): A 46.65, C 49.15 (GND), B 51.65 at y=20.5, S pads at x 46.65/51.65, y=6.0. Offsets and A-to-B direction match. A swap would only reverse the turn direction anyway. C is the centre pin and goes to GND, and lugs go to GND. Encoder pins are set as inputs with pull-ups by QMK (`gpio_set_pin_input_high`). The push switch is unconnected by design. Lug holes are E2.

### 5. OLED: correct for the standard module (CONFIRMED against references)

J1: pad 1 GND (39.0, 9.19), pad 2 +3V3 (11.73), pad 3 SCL (14.27), pad 4 SDA (16.81). This is identical to the care-package 0.91" footprint offset from the module's corner (36.5, 2.19), and stratum, froskeys, mediapad, Matyas and ByteBoard all carry that footprint. Orpheuspad uses a plain header with SDA first, which is the same pin sequence seen from the opposite end. That fits the module being rotated 180°, though I did not confirm it from its case.

J1 is through-hole with its pins going down and clear of the XIAO: the U1 copper ends at x=31.4 and J1 is at 39. The net walk confirms `J1.3 → U1.6` (SCL) and `J1.4 → U1.5` (SDA).

**Supply and pull-ups: pass.** TinyTronics lists 3.3–5 V and 4.7 kΩ built-in pull-ups at 3.3 V logic. It does not name the pull-up rail, but feeding VCC from +3V3 keeps either arrangement within RP2040 limits. Matyas and ByteBoard run theirs from 5 V; Frostbite's choice is the safer one.

### 6. Power: passes (CONFIRMED)

**The 5V pin is raw VBUS.** Seeed schematic v1.3: USB A4/B9 and B4/A9 → net VBUS → J4 pin 7, the 5V pin. There is no series element; D2 (NRS0320) feeds only the LDO. CC1 and CC2 each have 5.1 kΩ, so USB-C to C cables get power.

**Current:**

| Case | Calculation | Result |
|---|---|---|
| Theoretical full white | 13 × (3 × 12 mA) + 13 × 1 mA IDD | 481 mA |
| Firmware limit | `POWER_BUDGET` = 40 % of full scale (`keymap.c:93`, applied at 402) | 187 mA LEDs + 13 mA = 200 mA |
| USB descriptor default | QMK `USB_MAX_POWER_CONSUMPTION` | 500 mA |

This leaves 300 mA for the XIAO and OLED. Those loads were not measured. The default keymap's effective limit is this limiter, not `max_brightness: 200`, because it writes through `rgb_matrix_set_color`. `ledtest` runs one LED at a time at level 90.

**Timing: passes.** QMK defaults against the datasheet: T0H 350 ns (0.2–0.4 µs), T1H 900 ns (0.58–1.0 µs), T0L 900 ns (≥ 0.8), T1L 350 ns (≥ 0.2), reset 280 µs (> 80). Byte order GRB matches datasheet section 15.

### 7. Matrix: correct (CONFIRMED)

Netlist: D1–D9 pin 1 = K on ROWn, pin 2 = A on `SWn_D`, and switch pin 1 on COLn (all nine checked). On the board, D1's cathode (pad 1, the marked pad) is at y=37.335, the silk band at y=34.80–35.05 is on that side of the body, and the anode is at y=29.715.

QMK's COL2ROW drives each row low and reads pulled-up columns, and its docs say "the black mark on your diode is facing to the rows". The press path is GP29 pull-up → SW1 → anode → cathode → ROW0 driven low, which forward-biases the diode. All pins match `keyboard.json`.

## Findings

### E1. Glow LEDs mount opposite to key LEDs, with no marking (MAJOR, LIKELY)

**Evidence:** Both LED types sit on B.Cu pads around an identical cut-out, with an identical triangle by pad 3. Only the lens direction differs. The only statements of it are `PCB/README.md:66–68, 95`. `docs/BOM.md:18` says "shining down" without saying the part is inverted relative to the others, and `README.md` has no assembly step. Board text is limited to `FROSTBITE`, `USB-C`, `XIAO HERE` and the rev line (`gen_pcb.py:226–234`).

**What goes wrong:** A builder who has just fitted nine LEDs lens-into-hole will fit the next four the same way. Lining up the chamfer with the triangle puts VDD and GND on the right pads, because they are diagonal. But the leads then land mirrored, which swaps the data pins:

| Lead | Lands on | Net at LED10 |
|---|---|---|
| 1 VDD | pad 1 | +5V |
| 3 GND | pad 3 | GND |
| 2 DOUT | pad 4 | `LED_D9`, which LED9 DOUT also drives |
| 4 DIN | pad 2 | `LED_D10` |

The glow chain gets no data, and DOUT fights DOUT on `LED_D9`. The light also goes up into the board rather than down. Key LEDs 0–8 should still work, so the fault would show only at the end of bring-up.

**Attempted disproof:** I looked for a wrong-way-proof feature. Nothing is mechanically keyed, since the cut-out accepts either face. I also checked `led-test.uf2`, which would reveal it, but only after soldering. This is a build-error risk, not a design error, which is why it is not a blocker.

**Fix:** Add B.SilkS text at each glow LED, such as `LENS DOWN`, and a build step. This is cheap before ordering.

### E2. Round encoder lug holes need twice the barb deflection (MAJOR, LIKELY)

**Evidence:** Alps specifies 1.5 × 2.6 mm slots, 12.5 mm over the outer edges, so outer edges are at ±6.25. Frostbite has Ø2.6 round holes at ±5.6 (lug pads at x 43.55 and 54.75). I sliced Alps' `EC11E-15SW.STEP`; the lug is 2.5 mm wide (half-width 1.25) and 0.4 mm thick:

| z (mm) | Lug x (mm) | Note | Past Ø2.6 hole edge | Past Alps slot edge |
|---|---|---|---|---|
| −4.0 | 5.45–5.85 | straight section | fits, corner radius 1.275 of 1.30 | fits |
| −5.2 | 6.15–6.55 | barb, widest | **0.59** | 0.30 |

At y=±1.25 the circle's edge is at only 5.6 + 0.357 = 5.96, so the barb must flex almost double what Alps designed for. In the straight section only 0.025 mm of radial clearance remains at the corners. JLCPCB's drill tolerance was not fetched, so I cannot say how a real hole sits in that margin.

**Attempted disproof:** ByteBoard uses this same circular footprint and is reported as built, so the fit is possible. That is why this is not a blocker. KiCad's slotted version (2.8 × 1.5 at ±5.6, outer edge 6.35) on orpheuspad, stratum, froskeys, mediapad, Matyas and SplashPad would need only about 0.20 mm.

`PCB/README.md:71–72` says slots "fail JLCPCB's 2:1 slot rule", but those six boards were made with them. I could not confirm which fab they used. The model is a genuine Alps part, and a kit clone may differ.

**Fix:** Use the slotted footprint, relaxing the local verify rule if needed, or confirm your fab accepts it. Otherwise expect a hard press-in. If the barb will not pass, file it rather than forcing it, because the plating is at risk.

### E3. 3.3 V data is below VIH (MINOR)

**Evidence:** Datasheet VIH is 0.7 × VDD, 3.5 V at 5.0 V. VDD is raw VBUS with no diode, so the 3.3 V level only reaches VIH if VDD falls to 3.3 / 0.7 = 4.71 V. RP2040 output cannot exceed IOVDD, 3.3 V (datasheet: VOH min 2.62 V). Only LED1 sees this, because its DOUT regenerates at VDD, but LED1 is a single point of failure for all 13.

**Attempted disproof:** All seven references with readable parts drive their LEDs straight from a GPIO with no shifter (chinnyyys' board file gave no parts). Stratum, froskeys, Matyas, ByteBoard and SplashPad do this at 5 V with an SK6812 chain, orpheuspad with WS2812B at VCC. Mediapad runs its LEDs from 3.3 V, which avoids the problem but is below the 3.7 V supply minimum. So this is out of spec and usually works. The real threshold of this batch is unmeasured.

`docs/VERIFICATION.md:65–66` offers a 1N4148 on LED1's VDD (about 4.3 V, VIH about 3.0 V), but the board has no footprint for it, so that means cutting a trace.

**Settle it:** Solder LED1 alone, run `led-test.uf2` on your highest-VBUS port, and watch for flicker before fitting the rest. Add a diode footprint on LED1 VDD if you respin.

### E4. Tented vias under bare XIAO back pads (MINOR)

**Evidence:** Seeed's back render shows bare gold GND and VIN pads at the far end, plus test pads and USB shell tabs near USB. Calibrating against the 15.24 mm pin row (60.7 px/mm, about ±0.3 mm), on Frostbite coordinates:

| XIAO pad | x (mm) | y (mm) | Via (Ø0.7) | Via centre |
|---|---|---|---|---|
| GND | 19.11–20.08 | 18.07–20.05 | COL0 | 19.856, 19.437 |
| VIN | 21.70–22.69 | 18.07–20.05 | LED_DIN | 22.543, 18.416 |

Both vias lie in or overlapping those pads. Tenting is on (`frostbite.kicad_pcb:39–42`), and `B_Mask.gbr` has no opening at all inside x 14.5–27.5, y 0–21 (nearest flash to either via is over 7 mm away), so solder mask is the only insulation. Masked tracks also cross these pads: COL0 and ENC_B under GND, LED_DIN and ENC_B under VIN. The 0.5 mm +3V3 track passes 0.15 mm from the near corner of the lower-right USB shell tab, which is a GND joint on the XIAO's back that may protrude. Seeed's callout labels these two pads the other way round from its own silk; either way one is at about 5 V and one is GND.

**If it failed:** VIN on GP0 would exceed the RP2040 limit of IOVDD + 0.3 V; COL0 on GND would read as all column-0 keys held.

**Attempted disproof:** Matyas has a ROW0 via under the same GND pad region (9.33, 1.68 in the same frame) and is reported working, so tented mask does hold. All these distances carry the ±0.3 mm measurement error.

**Fix:** Move these two vias out of the regions, and shift the +3V3 diagonal away from the tab. This costs almost nothing before ordering, and the downside if it failed is the highest here.

### E5. No LED decoupling (MINOR)

**Evidence:** Datasheet section 16 draws a capacitor at every LED and calls the capacitance "essential". The board has none, by decision (`design.json:80`), but `docs/VERIFICATION.md:62` still says "every LED has a 100 nF cap".

**Attempted disproof:** Stratum, froskeys, Matyas, ByteBoard and SplashPad have no capacitors, and orpheuspad and mediapad none on their LED nets either. The firmware cap also keeps current swings down. Update the doc so it matches the board.

### E6. J1 has no pin labels (MINOR)

**Evidence:** The care-package footprint prints GND, VCC, SCL and SDA on silk. Frostbite's plain header prints only the reference. TinyTronics lists its module's pins as VCC, GND, SDA, SCL; that may be list order rather than physical order, but `PCB/README.md` also warns that clones swap GND and VCC. A swap would reverse-power the module. Add the four labels.

### E7. RESET and BOOT face the floor (MINOR)

**Evidence:** Seeed's front render shows both buttons on the component face at the end away from USB, which on this board is about y=19–21, facing down. `frostbite_case.py` has no button opening (a search for `reset` and `button` found none). `README.md:124–125` and `config.h:5` rely on those buttons.

**Attempted disproof:** Bootmagic on Approve (`keyboard.json:21`) works with the case closed unless the matrix or firmware is broken, in which case the four screws come out. The README's "Approve + Stop" is more than needed, since only [2,0] is configured. Harmless.

### E8. LED window offset (MINOR, UNVERIFIED)

**Evidence:** `docs/DIMENSIONS.md:106` quotes the Gateron window as 4.00 × 1.10 mm "4.0 from the housing centre line", without saying to which edge. The lens centre is at +4.98 mm and its ring is Ø2.4 (3.78–6.18 mm). If 4.0 is the window's centre, the window covers 3.45–4.55 mm and catches only the lens's inner edge. If it is the near edge, it covers 4.0–5.1 mm and lines up well.

Froskeys sits at +5.08 mm and Matyas at +4.52 mm, so Frostbite is within the built range. This affects brightness only.

**Settle it:** Check the KS-3 drawing, or test one switch with `led-test.uf2`.

### E9. Encoder resolution (MINOR, UNVERIFIED)

**Evidence:** `keyboard.json:30` sets `resolution: 4`. Every part in Alps' EC11E table has detents = 2 × pulses (18/9, 30/15, 36/18), so one detent is 2 quadrature transitions. QMK ticks after `resolution` transitions, so a true EC11E would step once per two clicks.

**Attempted disproof:** Stratum and SplashPad also use 4, which suggests a kit part with 4 transitions per detent, but the kit part number is unknown. `BOM.md` calls it an Alps EC11E.

**Settle it:** Turn one click in `ledtest`, which shows the encoder count. Use 2 if it needs two clicks. This is a firmware change only.

### E10. Lens and back heights swapped in docs (MINOR)

**Evidence:** `docs/DIMENSIONS.md:106` says the lens protrudes 0.94 mm into the hole, and `PCB/README.md:129` lists bodies 0.84 mm and lenses ≈0.94 mm. The datasheet side view is the reverse: lens face 0.84 mm from the leads, rear 0.94 mm. This is confirmed by the pin map: the references only work if the ring face is the lens.

**Effect:** Key LEDs hang 0.94 mm below the PCB and glow lenses 0.84 mm. The case model uses a conservative 1.78 mm, so nothing changes. Correct the text.

## Not established

- Real SK6812 switching threshold, and XIAO and OLED current. Both need a bench test.
- That any reference board was built exactly as its files show. I took "built and working" from the brief.
- Physical pin order on the kit's OLED module. Compare its printed labels with J1 before soldering.

## Sources

- SK6812 MINI-E datasheet Rev 02: https://cdn-shop.adafruit.com/product-files/4960/4960_SK6812MINI-E_REV02_EN.pdf (pp. 4–7, 9)
- Adafruit product page: https://www.adafruit.com/product/4960
- Seeed wiki: https://wiki.seeedstudio.com/XIAO-RP2040/
- Seeed pinout renders: https://files.seeedstudio.com/wiki/XIAO-RP2040/img/XIAO_RP2040_front_pinout.png and `.../XIAO_RP2040_back_pinout.png`
- Seeed schematic v1.3: https://files.seeedstudio.com/wiki/XIAO-RP2040/res/Seeed-Studio-XIAO-RP2040-v1.3.pdf
- RP2040 datasheet: https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf (pp. 13, 616–617)
- Alps EC11E catalogue: https://www.alpsalpine.com/cms.media/product_catalog_ec_01_ec11e_en_611f078659.pdf
- Alps 3D model: https://www.alpsalpine.com/cms.media/product_3dcad_ec11e15244b2_en_e8eed3a0b5.zip
- TinyTronics module: https://www.tinytronics.nl/en/displays/oled/0.91-inch-oled-display-128*32-pixels-white-i2c
- QMK: https://docs.qmk.fm/platformdev_rp2040, https://docs.qmk.fm/drivers/ws2812, https://docs.qmk.fm/config_options, `quantum/matrix.c`, `drivers/encoder/encoder_quadrature.c` (qmk_firmware master)
