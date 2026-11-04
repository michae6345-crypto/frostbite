# Building Frostbite

This guide takes you from a bag of parts to a working Frostbite 9, and it assumes you have never soldered. Use it instead of Hack Club's `/assembly` page, which is an unfinished stub (`docs/audit/hackpad-rules.md`).

**Nobody has built this board yet.** Every check so far ran on files, so treat each step as untested on hardware. Stop at the first failure and fix it before you go on. Anything marked *(general practice)* is ordinary soldering technique from outside this repo.

## 1. Words used in this guide

| Word | Meaning |
|---|---|
| Top side | The side the switches, diodes, encoder and OLED sit on. It says `FROSTBITE` and `XIAO ON BACK`. |
| Underside | The side the XIAO and all 13 LEDs solder to. It says `XIAO HERE`. |
| Back edge | The edge with the USB-C connector. The front edge is nearest you when you use the pad. |
| Pad, joint | A pad is the bare metal patch you solder to. A joint is one solder connection. |
| Tail | The piece of a wire lead sticking out past a joint. |
| Short | Two things connected that should not be. |
| Chain | The 13 LEDs in a line. Each LED passes data to the next. |

**Left and right swap when you turn the board over**, so this guide always says which view it means. Keep the back edge away from you in both views. Underside view, and XIAO pins from that view, USB at the top:

![PCB underside](../PCB/images/pcb_back.png)

| Left column | Net | | Right column | Net |
|---|---|---|---|---|
| D0 | ROW0 | | 5V | +5V |
| D1 | ROW1 | | GND | GND |
| D2 | ROW2 | | 3V3 | +3V3 |
| D3 | COL0 | | D10 | COL2 |
| D4 | SDA | | D9 | COL1 |
| D5 | SCL | | D8 | ENC_B |
| D6 | LED_DIN | | D7 | ENC_A |

## 2. Tools

You need a multimeter with continuity and diode modes, calipers, a needle file, a soldering iron with a tip for heat-set inserts, small pliers, black tape, printer paper, two blocks at least 22 mm tall, and a USB-C cable that carries data. A charge-only cable will not work. A switch puller is only needed if the PCB must come out later.

Also get these *(general practice)*:

- A temperature-controlled iron with a fine tip. A long, slim tip helps at the switch joints.
- Thin rosin-core solder. Adafruit calls 60/40 leaded solder the easiest to work with.
- Flux, solder wick, a tip cleaner, flush cutters, a magnifier and a way to hold the board still.
- Fine tweezers. The [LED datasheet](https://cdn-shop.adafruit.com/product-files/4960/4960_SK6812MINI-E_REV02_EN.pdf) (p.17) says to pick parts up with tweezers and keep off the lens.
- Safety glasses, because cut tails fly.
- A driver that fits the kit's M3 screws. The shaft must reach down a 5.8 mm hole, up to 4.2 mm deep.

Work with ventilation, wash your hands after handling leaded solder, and put the iron in its stand every time *(general practice)*. The datasheet (p.18) warns that SK6812s can be damaged by static and are bright enough to hurt your eyes, so use anti-static precautions and do not stare at them.

The repo gives no iron temperature. Adafruit says to set [370 °C for 60/40 or 400 °C for lead-free](https://learn.adafruit.com/adafruit-guide-excellent-soldering). The datasheet gives no hand-soldering figure, and its only related test is 260 °C for 10 s, 3 times (p.12). Keep each LED touch short, and let a joint cool before you try again.

## 3. Parts check against the kit

Count everything against the [kit table in BOM.md](BOM.md#kit-usage) before you heat anything. The same file lists what you must buy or print. Printing Legion promises no material, so ask the printer about black and clear PETG, and about the coupons (section 5), before you post.

Check these on the real parts:

1. Switches have 2 metal pins, 2 side pegs and 1 centre post, all straight. The encoder shaft has a D-flat. Inserts are OD 5, length 4.
2. Hold the OLED module display side up with the header end on your right. From back to front the pins should read `GND`, `VCC`, `SCL`, `SDA`, matching the silkscreen beside J1. Some clones swap GND and VCC, which would reverse-power the module. If yours differs, stop. The repo has no fix for a swapped module.
3. Look for an OLED header, since the kit list names none. If yours has none, buy a 4-pin 2.54 mm header. The long pins must point away from the display.
4. On the PCB, find `XIAO HERE`, four `LENS OUT` marks, the two-line LED legend and `GND VCC SCL SDA` beside J1.
5. On a spare PCB, drop one LED into a cut-out. If it binds, ease the cut-out with a needle file.

## 4. Lessons from other builds

**Practise first.** On other Hackpads a first-time solderer pulled up a trace fitting LEDs and shipped with no RGB, and an encoder leg snapped off during removal. Frostbite's LED pads are small (0.82 × 1.25 mm), its signal tracks are 0.2 mm, and you have only 3 spare LEDs. Solder spare diodes on a spare PCB until your joints look smooth and shiny, then practise tacking a small part on spare LED pads.

**Avoid ripping a trace** *(general practice)*. To fix a joint, add flux and reheat. Never press or lever a part. To remove one, melt all its joints first and lift only when it moves freely. Never hold the iron on one pad for long. Stop, cool, and try again with more flux.

## 5. Test prints (coupons)

**Do this before the full case prints.** Coupons are small test pieces cut from the real case, each checking one risky fit. Print them with the case's settings: PETG, 0.4 mm nozzle, [240 °C, bed 80 °C](../CAD/README.md#print-settings), 4 perimeters, 25 % gyroid, no supports, hole or XY compensation off for the first run. Print the OLEDSupport and the knob at the same time.

Then follow [the coupon page](coupons/README.md), which has each test and what to do with each result. You are looking for three passes:

- Coupon 1: **38.10 mm** across the columns, within 0.3 %, and a switch that clips firmly into the 14.0 cutout.
- Coupon 2: an insert that holds in Ø4.7. You have only **2 spare inserts**, and the case needs the other 4.
- Coupon 3: a bare spare PCB that seats, and a USB cable boot that enters at least 6 mm.

Coupon 4 needs a lit glow LED, so it waits for [Stage F](#stage-f-flipped-glow-leds). **Measure the OLED now** ([section 11](#oled-ribbon-clearance)), because it decides whether the Top needs changing. Send the Top and Bottom after coupons 1 to 3 and the OLED measurement pass. You can solder Stages A to F with no case at all, so hold the GlowBand print until coupon 4 passes if your printer allows it.

## 6. Heat-set inserts

Do this as soon as the Top arrives, and always before the PCB goes near it. The four holes open at the skirt rim, in the side walls of the Top. The Bottom and GlowBand get no inserts.

Start at [about 230 °C](../CAD/README.md#assembly-order), the repo's figure. CNC Kitchen gives [245 °C for PETG](https://cnckitchen.com/blog/tips-and-tricks-for-heat-set-inserts), or 10-20 °C above print temperature. Use coupon 2 to find yours, and go hotter only if the insert will not sink under light pressure.

1. Sit the Top skirt-up on a flat surface and set one insert straight on a hole.
2. Put the hot tip into the insert and press lightly. Let heat sink it. Do not push hard.
3. Melt it in about 90 % of the way, then finish with a flat tool, as CNC Kitchen advises.
4. Press it flush with the rim and hold it still for a moment so it does not creep back.
5. Keep the iron off the rim and walls. The wall around each insert is only about 2 mm thick.
6. Repeat for all four. After cooling, run an M3 screw in by hand. It should go straight.

If plastic pushes up into the screw hole, press more slowly and clear the hole with an M3 screw while it is warm.

## 7. Soldering order

Work through the stages in order. Each one relies on the test before it, and later parts block access to earlier ones. Checks A to G are in [section 8](#8-multimeter-checks-before-power).

### Stage A: bare board

Do check A on the PCB you will use.

### Stage B: XIAO, castellated, on the underside

1. Turn the board underside up and find `XIAO HERE`.
2. Lay the XIAO flat on that outline with **its components facing you, away from the PCB**. On the top side it would mirror the pinout and put 5V onto D0.
3. Point USB-C at the back edge and line up the XIAO board edge with the PCB edge. The USB connector overhangs a little, which is correct. Check the 14 XIAO edge pads sit over the 14 PCB pads, 7 per side.
4. Tack one corner. Check the XIAO is flat and square, then tack the opposite corner.
5. Solder all 14 pins. Touch the iron to the exposed PCB pad at the XIAO's edge and feed solder. If a pin is hard to reach, heat the pad from the top side and feed solder down the plated hole. Leave no solder blobs under the XIAO.
6. Take extra care with the GND pin, second from the USB end. It is the XIAO's only GND link, so a bad joint takes out the LEDs, OLED and keys together.

### Stage C: first flash

Do check B, then [the first flash](#first-flash-on-a-blank-xiao), then the first voltage reading. This proves USB and the XIAO before you add 13 LEDs.

### Stage D: LED1 alone

LED1 is the one LED that sees 3.3 V data. If it fails, all 13 fail. **Fit for LED1 to LED9:** lens **into** the hole, back of the part facing you, so light goes up into the switch. The lens is the side with the ring. The back has a rib and a small round mark.

1. Unplug USB. Find LED1 on the underside, under SW1.
2. Lightly tin the pad beside the triangle. The triangle marks GND, pad 3.
3. Hold the LED with tweezers and drop the body into the cut-out, **back facing you**.
4. Put the chamfered lead on the triangle pad. Reheat that pad until the lead sinks in. Keep it short.
5. Check all four leads sit on their pads, then solder the other three.
6. Do check C, then the [LED1 test](#led1-test).

### Stage E: LED2 to LED9

The chain feeds the glow LEDs, so these must work first. Fit one LED the same way, lens into the hole and chamfer on the triangle. Unplug, do check C, plug in, and confirm it lights in turn. Repeat in chain order, so a fault can only be the LED you just fitted. LED9's GND pad, and LED11's in the next stage, connect by tracks and miss the copper pour. Both are normal.

### Stage F: flipped glow LEDs

**Fit for LED10 to LED13: flipped. Lens OUT, facing you, back of the part in the hole.** Light goes down into the glow band. Look for the `LENS OUT` text and the ring-and-dot mark beside each one. The legend mid-board says `LED1-9: LENS INTO HOLE` and `LED10-13 FLIPPED: LENS OUT`.

Nothing physically stops a wrong fit, because the cut-out takes either face, and after nine LEDs your hands will want to do the same again.

1. Stop and read the marks at LED10. Underside view, USB at the top: LED10 back right, LED11 back left, LED12 front left, LED13 front right.
2. Put the ring-side lens toward you and the back into the hole.
3. Put the chamfered lead on the triangle. **Both must be true: lens out and chamfer on triangle.** The four pads form a 5.55 × 1.5 mm rectangle, so a part can only sit at 0° or 180°, and a part the wrong way up can never put its chamfer on the triangle. If you cannot get both, stop and turn it over.
4. Solder it like the others. Do check C, then run `led-test.uf2`. LED10 must light, facing you.
5. Do the [glow coupon](#glow-brightness).
6. Fit LED11, LED12 and LED13, testing each.

If one goes in lens-in, neither VDD nor GND reaches its own pad. At LED10:

| Position | VDD lead on | DOUT lead on | GND lead on | DIN lead on |
|---|---|---|---|---|
| Correct, lens out | +5V | `LED_D10` | GND | `LED_D9` |
| Lens in, 0° | `LED_D9` | GND | `LED_D10` | +5V |
| Lens in, 180° | `LED_D10` | +5V | `LED_D9` | GND |

Expect the glow chain to stay dark, the light to go into the board, and LED9's output to be at risk because it feeds `LED_D9`. This comes from the pad geometry, and nothing has been built. Do not leave a suspect glow LED powered. Unplug and fix it.

### Stage G: diodes, band toward the front edge

The plate sits 2.5 mm above the PCB, so a raised diode would hit it.

1. Top side up, back edge away from you. Each diode sits to the right of its switch, and the square pad is marked `K`. Bend the leads to fit the holes, 7.62 mm apart.
2. Put the **black band on the `K` end**. On all nine diodes that is the end **nearest the front edge**. The band points at the row (cathode to the row, `COL2ROW`), and a backward diode means a dead key.
3. Check the band against the silkscreen, then press the diode flat. It must end up at most 2.2 mm tall.
4. Turn the board over and solder both leads.
5. Do D1 first, and test it with check D before you do the other eight.

### Stage H: encoder

1. Fit it from the **top side**, the same side as the diodes. Check this twice. Turn it so the three-pin row (A, C, B) faces the keys and the two-pin row faces the back edge.
2. Press straight down until the side lugs snap through their slots. Expect a firm press. If a barb will not pass, file it, since forcing it puts the plated hole at risk. Lug figures come from Alps' model, and a kit clone may differ.
3. Check it sits flat and square.
4. Turn the board over. Solder the three pins, the two lugs and the two pins of the unused push switch *(general practice: the push switch has no signal, but the joints add strength)*. The lugs and pin C go to GND and need a little longer to heat.

### Stage I: trim tails

The GlowBand sits 0.6 mm below a 2.0 mm tail. On the underside, cut all through-hole tails (diodes, encoder) to **2.0 mm or less**, then do check E.

### Stage J: OLED, soldered to J1

Do this on the bench, with the top of the PCB facing up. The black header plastic comes off and the printed OLEDSupport sets the height. With the plastic on, the glass would stand proud of the plate.

1. Compare the module's labels with the silkscreen beside J1 once more.
2. If the header is loose, put its short pins up through the module from underneath, black plastic on the underside. Solder the four pins and trim them **flush on the display side**.
3. **Slide the black plastic strip off the pins**, toward their free ends, with small pliers. Work from both ends. The pins stay soldered to the module, so do not pull on the joints. Nobody has tried this by hand yet, so go gently.
4. Put thin double-sided tape on **both faces of the OLEDSupport's two feet**. Use about 0.2 mm tape and never foam tape.
5. Try the fit first with the backing on *(general practice)*. The small foot sits beside the pins, the large foot sits at the far end, and the rail runs outside the module on the side facing the keys. Then stick the support to the underside of the module.
6. Put the pins through J1, display up, until the support sits on the PCB and sticks.
7. **Square the module now.** Measure from the PCB's back edge to the module's long edge at both ends. Both should read **7.0 mm** and agree within 0.5 mm.
8. Turn the board over. Solder the 4 J1 pins from the underside and trim them to **2.0 mm or less**. Whether the tape keeps the module square here is untested.
9. Do check F.
10. **Test now, while BOOT is easy to reach.** Plug in and run `led-test.uf2`. Read the OLED and turn the knob. See [OLED flip](#oled-flip) and [EC11 resolution](#ec11-resolution).

### Stage K: switches

The plate closes one side of the Top, so the PCB can only enter from the skirt side. The switch flange is wider than the plate cutout, so switches clip in from the top face and get soldered through the PCB afterwards. The PCB ends up hanging from the 9 switches with nothing under it, by design.

1. Measure SW1 to SW3 on the full Top: 38.10 mm centre to centre.
2. Clip all 9 switches into the plate **from the top face** until the clips seat. Check every pin is straight.
3. Turn the Top upside down on **two blocks at least 22 mm tall**, under the plate margin. The switch stems stand 10.2 mm proud, and the encoder shaft will stand 19.5 mm proud, or 21.5 mm on a generic EC11. Shorter blocks stop the PCB from seating.
4. Hold the PCB with its underside facing you and lower it straight down the skirt. **Start the encoder shaft in its opening first**, about 22 mm before the PCB seats. Then the PCB enters the skirt, the USB enters the notch, the switch pins meet their holes, and the OLED glass meets its recess last.
5. Do not force it. If it stops, lift it out and look for a bent pin.
6. Solder the 18 switch joints from underneath (2 per switch). The PCB underside sits 9.4 mm below the skirt rim and the closest pin is about 8 mm from the wall, so lean the iron about 40 degrees at the rim. Keep the hot shaft off the printed wall.
7. Take care at SW3 pin 2. It is the closest joint to any LED, about 1.1 mm from LED11's GND pad, and its pad is smaller than the others. Use a small amount of solder and check for a bridge.
8. Trim the switch tails to **2.0 mm or less**. Do check G, then test every key with `led-test.uf2`.

## 8. Multimeter checks before power

**Keep USB unplugged for every continuity check.** A steady tone means two points are connected. A short chirp that fades can be a capacitor charging *(general practice)*. With parts fitted a meter may show a resistance value, which is fine unless it is near zero. If a "silent" pair gives a steady tone, **do not plug in**. Look for a solder bridge, starting with the last part you fitted, clean it with wick, and test again.

| Check | When | Must stay silent | Must give a tone |
|---|---|---|---|
| A | Bare board | 5V to GND, 3V3 to GND, 5V to 3V3, D0 to D1, D1 to D2 (rows), D3 to D9, D9 to D10 (columns) | |
| B | After the XIAO | **5V to GND** (the check that matters most), **3V3 to GND**, 5V to 3V3, each XIAO pin to the next pin down in both columns | XIAO GND to J1 pin 1, XIAO 3V3 to J1 pin 2, XIAO 5V to LED1 pad 1 |
| C | After each LED | **5V to GND**, LED pad 1 to pad 2, LED pad 3 to pad 4 | |
| E | After the encoder and tails | 5V to GND, ENC1 pin A to GND, ENC1 pin B to GND, D0 to D10 each to GND | ENC1 pin C to GND |
| F | After the OLED | **5V to GND**, **3V3 to GND**, SDA to SCL (D4 to D5) | |
| G | After the switches | **5V to GND**, SW3 pin 2 to LED11 pad 3 | |

- Check B: a silent XIAO GND to J1 pin 1 means the XIAO's only GND joint is bad.
- Check C: the two pads on each side of an LED are only 0.68 mm apart, so they are the likely bridges.
- Check D, after the diodes: in diode mode, red on the anode end and black on the `K` end should give a reading, and swapped should give none. If it reads the wrong way round, the diode is backwards, so fix it now. Then repeat the row and column checks from check A.
- Check E: measure the tails too. Any tail over 2.0 mm gets cut.
- Check G: press each key while you probe its row and column. It should connect only with the key held down, and through a diode.
- First voltage reading: the first time you plug in, use DC volts. 5V to GND should read about 5 V, which is raw USB power. Write it down for section 11. 3V3 to GND should read about 3.3 V.

## 9. Flashing led-test.uf2

`production/led-test.uf2` is the test program. Keep it on the XIAO until the LEDs, OLED, knob and keys have all passed. BOOT and RESET (B and R in [Seeed's wiki](https://wiki.seeedstudio.com/XIAO-RP2040/)) sit on the XIAO's component side, at the end away from USB. They stay reachable from the open skirt until the GlowBand goes on. After that, reaching them means taking out the 4 screws. With the case closed, only Approve + Stop works, and only if the keys and firmware are good.

### First flash on a blank XIAO

**Use the BOOT button.** The double-tap and Approve + Stop are part of the Frostbite firmware, so they do nothing until it is on the XIAO.

1. Unplug the XIAO. Press and hold **BOOT**, plug the USB-C cable into the laptop, then let go.
2. A drive named **RPI-RP2** appears. Drag `production/led-test.uf2` onto it. The board reboots by itself and the drive goes away.
3. Check the laptop sees it, from the repo root. A non-empty list means the pad is running Frostbite firmware.

```sh
cd host && uv run python -c "from frostbite_host.device import HidTransport; print(HidTransport.find())"
```

| Result | Meaning | Next |
|---|---|---|
| RPI-RP2 appears, flash works, the check lists a device | USB, XIAO and power are good | Go to Stage D |
| RPI-RP2 does not appear | Charge-only cable, or BOOT released too early | Try a data cable, and hold BOOT longer |
| Laptop reports a USB problem, or the XIAO gets hot | Possible short | Unplug at once. Redo check B. |
| RPI-RP2 appears, but no device afterwards | Drag failed, or the file is wrong | Flash again and check the file name |

### LED1 test

Use your highest-voltage USB port. With only LED1 fitted, it lights red, green, blue, white, then **stays dark for about 17 seconds**. That is normal, because the test runs through all 13 positions whether the LEDs exist or not. Each LED gets 1.4 s (4 colours at 350 ms), so a full pass takes 18.2 s.

| Result | Meaning | Next |
|---|---|---|
| Red, green, blue, white, steady | LED1 and data are good | Go on |
| Never lights | Bad joint, wrong way round, or data level too low | Section 10, then section 11 |
| Flickers or shows random colours | 3.3 V data is marginal | [LED data level](#led-data-level) |
| Wrong colour order, such as green during the red step | Colour order fault in firmware | Note it. Soldering is not the cause. |

### Full led-test results

Once J1 is soldered, the OLED shows lines like `LED TEST 5/13`, `colour: green`, `key: r1 c2` and `knob: 3`. The test runs fine with no OLED, so before that, use the timing below.

Chain order under the keys is SW1, SW2, SW3, SW6, SW5, SW4, SW7, SW8, SW9. The middle row runs right to left, so the order zig-zags, and that is correct. LED10 to LED13 follow: glow back left, back right, front right, front left, in top view. LED n lights 1.4 × (n − 1) s after LED1, so LED9 comes at 11.2 s, LED10 at 12.6 s and LED13 at 16.8 s.

With the switches in, each key should show once on `key:`. The Agent 1 to 3 row is `r0`, Agent 4 to 6 is `r1`, and Approve, Talk, Stop is `r2`, with `c0`, `c1`, `c2` from left to right. Keys send their fallback codes during this test, so Stop sends Escape to the laptop. Turning the knob changes `knob:` and leaves the volume alone.

## 10. Finding a dead LED

Each LED rebuilds the data signal for the next one. So one bad LED or joint usually darkens itself **and every LED after it**, while the OLED keeps counting up through the dark ones. Pad numbers: 1 = 5V, 2 = DOUT, 3 = GND (triangle), 4 = DIN. Call the last working LED n.

1. Unplug USB. Look at LED n and LED n+1 under a magnifier. Check the leads sit on their pads and the fit is right for that LED.
2. Check for a tone from LED n pad 2 to LED n+1 pad 4, from LED n+1 pad 3 to XIAO GND, and from LED n+1 pad 1 to XIAO 5V.
3. Plug in. Measure LED n+1 pad 1 to pad 3 in DC volts. Expect about 5 V.
4. Reflow any doubtful joint with flux.
5. If the wiring is good and it stays dark, replace LED n+1. If the replacement stays dark too, replace LED n, since its DOUT may be dead.

To remove an LED *(general practice)*, add flux and fresh solder to all four joints. Heat one side's two leads and then the other's, or use wick to clear each side. Lift only when the part moves on its own, then clean the pads gently with wick.

One colour missing on one LED means a damaged LED, so replace it. An LED that works but looks dim through the switch may be down to lens position against the switch window, which is unproven and affects brightness only. Key LEDs fine and all glow LEDs dark means LED10 is fitted wrong ([Stage F](#stage-f-flipped-glow-leds)).

## 11. Needs real parts: measure and adjust

### OLED ribbon clearance

Do this before the Top prints. Nobody has measured the kit OLED, and no drawing of it was found, so the room below is an allowance. Measure with calipers. Ribbon height is the thickness at the far end (away from the header), over the folded ribbon and tape, minus the board thickness at a plain edge. Also record the glass position from both ends of the module. After changing `design.json`, rerun `CAD/frostbite_case.py` and `CAD/check_fit.py`, then send the new Top.

| Measure | Room in the design | If it does not fit |
|---|---|---|
| Ribbon height above the board | 1.0 mm | Widen `oled.window` in `design.json` through the far lip, as both reference builds do |
| Ribbon or tape past the far board end | 1.1 mm | The same |
| Joint height after trimming, header end | 1.0 mm | Trim again, or thin the lip locally (a CAD change) |
| Parts on the module's underside at the feet: 1 to 7 mm from the far end, 3.1 to 8.3 mm from the header end | None planned | Move the feet in `CAD/frostbite_case.py`. A part on a foot lifts that end. |
| Glass thickness | 1.45 mm assumed, 1.2 mm exists | Thinner only sinks the glass further |
| Module length | 38 mm assumed, 36 mm exists | The glass moves in the window. Shift the window. |

### LED data level

Test this at Stage D and again after Stage F. The datasheet asks for 3.5 V data at 5 V power, and the XIAO gives 3.3 V. Only LED1 sees this, but LED1 feeds all 13. The data meets the spec only if USB power falls to 4.71 V (3.3 / 0.7), and this batch's real threshold is unmeasured. No shipped build runs the whole chain at full white: `led-test` lights one LED at a time at level 90 of 255, and the normal firmware caps total output at 40 % of full scale.

1. Measure 5V to GND on the XIAO on each port and use the highest. Higher power raises the threshold, so LED1 alone on that port is the hardest case.
2. Run `led-test.uf2` with LED1 alone. Watch for flicker or wrong colours.
3. Repeat with all 13 fitted. Every LED must step through its colours cleanly.
4. Once `firmware.uf2` is on, run the all-LEDs check in [section 15](#install). Try each USB port and cable you will use.

**No setting fixes this.** If LED1 is unreliable, the only remedy is to feed its VDD through a spare 1N4148, which drops it to about 4.3 V. The board has no footprint for that, so it means cutting a trace. Stop and get advice before you cut anything.

### Glow brightness

Do this when LED10 works. Nobody knows yet whether the 2 mm band glows enough. The estimate says it is visible in a dim room and faint in a bright one, with hot spots near the LEDs and the back edge dimmest. `led-test` never shows the glow colour, so use the real firmware.

1. Cover the two cut end faces of the band coupon with black tape, or they will glow and mislead you.
2. Flash `firmware.uf2` ([section 12](#12-flashing-firmwareuf2)) and run it with no daemon. The glow shows ice blue `#7fe3ff` at 70 of 255, about 27 %.
3. Hold the band under LED10 at its real position, with the cap off.
4. Look at the 2 mm outer face in a normally lit room, then a dim one.
5. Flash `led-test.uf2` again before you carry on.

| Result | Do this |
|---|---|
| Visible along the whole 31 mm run, even with a hot spot at the pad | Print the full band |
| Bright near the pad, gone within about 15 mm | Try 6 perimeters, or printing slower and hotter. Then line the skirt's inner wall with white paint or white paper. Keep foil away from the board, because a loose piece can short the solder tails. |
| Cloudy, layer lines, little carry | Raise temperature, slow down, 100 % infill, thicker layers |

The coupon shows how far light carries, and it has no skirt or Bottom, so it will look better than the case, where black plastic absorbs stray light. If the band looks weak in the case, try white paper on the Bottom floor first. A phone torch only shows the shape of the spread.

To change brightness with no daemon, set `GLOW_DEFAULT_BRI` in `keymap.c` and rebuild. With the daemon running, `glow()` in `host/frostbite_host/state.py` decides: 50 of 255 when nothing runs, 110 while something runs, and 160 for amber or red. A limiter caps total LED output at 40 %, so more brightness will not always show.

### OLED flip

Do this at Stage J. Run `led-test.uf2` and read the text with the back edge away from you. If it is upside down, comment out `#define FROSTBITE_OLED_FLIP` in `Firmware/qmk/keyboards/frostbite/config.h` and [rebuild](#rebuilding). The flip is on now because four reference Hackpads with this header position use it, and no Frostbite module has confirmed it.

### EC11 resolution

Do this at Stage J. Run `led-test.uf2`, turn the knob **one click**, and see how far `knob:` moves. The setting is `encoder.rotary[0].resolution` in `keyboard.json`, 4 now. If one click moves the count by 1, change nothing. If it moves by 2, double the value. If two clicks are needed for one count, set it to 2, which is expected on a true 30-detent/15-pulse EC11E.

Clockwise should count up. If it counts down, swap `pin_a` and `pin_b` in `keyboard.json` and do not resolder. That swap makes `PCB/tools/check_netlist.py` and `verify` report a pin mismatch, so note it for whoever runs them next.

### Rebuilding

Any firmware change means a rebuild. Set up QMK first ([QMK docs](https://docs.qmk.fm/newbs)), then follow "Build" in [`Firmware/README.md`](../Firmware/README.md).

## 12. Flashing firmware.uf2

Do this after every key, the knob, the OLED and all 13 LEDs pass in `led-test.uf2`, **with the case still open**.

1. Enter the bootloader. Double-tap **RESET**, or hold **BOOT** while plugging in, or hold **Approve + Stop** (bottom-left and bottom-right keys, both required) while plugging in. The last one also clears EEPROM.
2. Drag `production/firmware.uf2` onto **RPI-RP2**. The board reboots by itself.

With no laptop app running, the agent LEDs and command keys should be dim white and the glow LEDs ice blue. OLED row 4 shows the slot strip, ending in `KBD`. Keys send F13 to F20 and Escape, and the knob changes volume. Press every key and turn the knob while you can still reach BOOT. On macOS, F14 and F15 may change screen brightness in fallback mode. That has not been tested and is not a fault.

## 13. Final assembly

Do not start until sections 9, 11 and 12 pass. After this, BOOT and RESET mean removing 4 screws.

1. Measure tails one last time. All must be 2.0 mm or less. Six diode joints sit right over the GlowBand's riser.
2. With the Top still upside down, lower the **GlowBand** onto the skirt, riser and pads into the pocket and tongue into the USB notch. Check it sits flat, with no gaps.
3. Lay the **Bottom** on the band and put the 4 M3 × 16 screws in from underneath. Use the kit screws. A 16 mm screw stops 0.4 mm short of the blind end of its hole, so a longer one will not fit.
4. Turn each one a little at a time, in a cross pattern *(general practice)*, and stop as soon as it is **snug**.
5. Press on the 3 white caps (Approve, Talk, Stop) and 6 frosted caps (agent keys).
6. Fit the knob with the D-flat lined up. Ream the bore if a printed knob is too tight.
7. Add 4 stick-on feet, plug in USB-C, and check the plug seats fully.

The repo gives no torque number. Snug means the head has seated and the parts have closed up. PETG creeps, so stop there, and use a small hand driver instead of a power driver *(general practice)*. The thread is in a metal insert with 4 mm of engagement, so an insert that spins or a screw that suddenly gets loose means stop. A screw that binds early is usually off its thread, so back it out and start it straight. The screws sit nearer the back (16 mm from the back skin, 28 mm from the front). If a part has warped, the band gap opens at the front, so watch it as you tighten. To take the PCB out later, release the 9 switches from the plate with a puller and lift it out with them, or desolder 18 joints.

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Approve + Stop does nothing | Firmware not on it, or keys or matrix not working | Use BOOT. Remove the 4 screws if closed. |
| Everything dead after an LED is added | That LED or a bridge | Unplug. Do check C. |
| No LEDs light, OLED counts | LED1, or the D6 data joint | Section 10 |
| OLED blank | J1 joint, or VCC/GND order | Check SDA, SCL, VCC, GND. Compare labels with J1. |
| Glass catches on the window | Module not square | Check the 7.0 mm at both ends. The window allows about ±1° and ±0.1 mm. |
| Glass stands proud of the plate | Tape too thick, plastic left on, or a part under a foot | Check all three |
| One key dead | Bad switch joint, or diode backwards | Reflow. Do check D on that diode. |
| A row or column dead | XIAO pin joint on that row or column | Reflow that XIAO pin. Check its neighbour. |
| Pressing one key shows two | Bridge between row or column pins | Re-run the neighbour checks |
| PCB will not seat in the Top | Bent switch pin, or blocks under 22 mm | Lift out and check both |
| GlowBand will not sit flat | Tail over 2.0 mm, or printing | Trim tails and check again |
| Band gap at the front | Warped part | Recheck the screws, without over-tightening |
| USB plug will not seat | Plug overmold too big | Coupon 3. Cables up to about 13.4 × 7.9 mm should work. |
| Pad falls back to `KBD` | No PING for 5 s | Check the daemon runs |
| OLED went dark | 10-minute burn-in protection | Press a key or turn the knob |
| Approve does nothing, or OLED says `answer in terminal` | No hook is waiting on that slot, or the pad cannot act on this one | Answer in the terminal |
| OLED says `tap slot first` | Another tab or app is in front when you press Stop | Tap the agent key, then press Stop |

## 15. Laptop companion

The pad works as a plain keyboard with nothing installed. The companion adds agent status, Approve and Stop. Nothing here installs itself or edits your settings, and no real pad or real Claude Code session has run it yet. [`host/README.md`](../host/README.md) is the full reference.

### Install

**By hand**, from the repo root. This needs `uv`. Plug in the pad and run the check from section 9 before you start the daemon.

```sh
uv tool install ./host
frostbite-daemon --dry-run      # no pad needed: prints every report it would send
frostbite-daemon                # OLED row 4 should change from KBD to HID
```

Test it in a second terminal. Slot 3 should turn blue, then green, then clear. The loop is the all-LEDs check for [LED data level](#led-data-level): it lights all 13 together, so watch for flicker before you clear them.

```sh
frostbite-ctl set 3 run "CI build"; frostbite-ctl set 3 done "CI build"
frostbite-ctl status; frostbite-ctl clear 3
for n in 1 2 3 4 5 6; do frostbite-ctl set $n run "test $n"; done
for n in 1 2 3 4 5 6; do frostbite-ctl clear $n; done
```

### Claude Code hooks: BY HAND

Run `frostbite-ctl hooks --hook "$(which frostbite-hook)"` to print a snippet with the right path in it. Merge it into the `"hooks"` object of `~/.claude/settings.json` yourself, keeping any hooks you already have, and start a new Claude Code session. Leaving out a hook your Claude Code version does not know is harmless.

### Approve and Stop

Approve sends no keystroke. It answers Claude Code's `PermissionRequest` hook, so it needs no macOS permission and works in every terminal. The slot goes amber and the OLED shows the tool and its input, paging long commands every 2 s. **Tap Approve** to allow that one request, or **hold Approve** to deny it. No rule or mode is saved. If you do nothing, the hook gives up after 30 s and the normal terminal prompt handles it. Questions, plan approval and MCP dialogs are shown but never answered from the pad.

Stop is the one real keystroke. With the daemon running, it sends Escape only when the selected slot is a Claude session in `run`, in Terminal or iTerm2, with that app in front and that tab focused. VS Code, Ghostty, WezTerm, Cursor, the desktop app, SSH and tmux can never be proved, so they show `answer in terminal`. **With no daemon, Stop is a plain Escape to whatever app is in front.** The same is true for a couple of seconds after the Mac wakes.

### macOS permissions: BY HAND

macOS asks the first time Stop needs them. In **System Settings → Privacy & Security**, allow **Accessibility** and **Automation → System Events, Terminal and iTerm2** for the program running the daemon. That is your terminal if you started the daemon by hand. If launchd started it, it is the tool's Python, and `head -1 ~/.local/bin/frostbite-daemon` shows its path. Without Automation the tty cannot be read, so Stop is refused.

### Optional: BY HAND

To start at login, replace `YOUR_USER` in `host/examples/com.frostbite.daemon.plist`, copy it to `~/Library/LaunchAgents/`, and load it. To stop it, run `launchctl bootout gui/$(id -u)/com.frostbite.daemon`.

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.frostbite.daemon.plist
tail -f ~/Library/Logs/frostbite-daemon.log
```

Talk sends F20 for as long as you hold it, so bind your dictation tool to it. In Wispr Flow: Settings → Shortcuts → push-to-talk shortcut, click the field, press Talk. In macOS Dictation: System Settings → Keyboard → Dictation → Shortcut → Customize, press Talk.

## 16. What is still open

These need a real part: kit OLED size, ribbon, header, strip removal, tape and staying square; OLED flip; EC11 resolution and direction; LED data level and LED body fit; glow brightness; print fit of switches, inserts, pocket and knob; the wrong-way LED behaviour, which comes from geometry only; the force path when you press the glass; and Approve and Stop in a real Claude Code session with a real pad. The exact USB overhang (1.0 or 1.42 mm) is also unmeasured, but the case fits both.

Open decisions:

1. Fallback Stop can stay a plain Escape, or move to an unassigned key with a one-line change in `keymap.c` and `design.json`.
2. If the kit encoder runs backwards, decide how `check_netlist.py` and `verify` should accept the swap.
3. If LED1 fails on data level, the only fallback cuts a trace, so a board respin with a diode footprint may be better.

## 17. Sources

Repo facts come from `design.json`, `PCB/frostbite.kicad_pcb`, `CAD/frostbite_case.py`, the READMEs in `CAD/`, `PCB/`, `Firmware/` and `host/`, `docs/VERIFICATION.md`, `verify/REPORT.md` and `docs/audit/`. Where they disagree, trust them in this order: `PCB/frostbite.kicad_pcb`, `keyboard.json` and `keymap.c`, `CAD/frostbite_case.py` and `production/`, `design.json`, then the READMEs. Outside sources are linked where they are used.

When your pad works, take a photo. Stardance's build stage asks for a demo video, physical build devlogs and a photo in the README (`docs/audit/hackpad-rules.md`).
