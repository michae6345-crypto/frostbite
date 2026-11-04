# Building Frostbite

The step-by-step build guide for Frostbite 9, written for someone who has never soldered before.
Hack Club's own `/assembly` page is an unfinished stub (`docs/audit/hackpad-rules.md`), so use this guide instead.

**Nobody has built this board yet.** Every check so far was done on files, not on hardware. Stop at the first failure and
fix it before you go on.

Two kinds of statement appear here:

- Project facts come from this repo. Each section ends with a **Source** line.
- Advice marked *(general practice)* is ordinary soldering technique that the repo does not cover.

Temperatures appear only with a linked source. Where the repo gives no number, this guide says so.

## Contents

1. [Words used in this guide](#1-words-used-in-this-guide)
2. [Tools](#2-tools)
3. [Parts check against the kit](#3-parts-check-against-the-kit)
4. [Lessons from other builds](#4-lessons-from-other-builds)
5. [Test prints (coupons)](#5-test-prints-coupons)
6. [Heat-set inserts](#6-heat-set-inserts)
7. [Soldering order](#7-soldering-order)
8. [Multimeter checks before power](#8-multimeter-checks-before-power)
9. [Flashing led-test.uf2](#9-flashing-led-testuf2)
10. [Finding a dead LED](#10-finding-a-dead-led)
11. [Needs real parts: measure and adjust](#11-needs-real-parts-measure-and-adjust)
12. [Flashing firmware.uf2](#12-flashing-firmwareuf2)
13. [Final assembly](#13-final-assembly)
14. [Troubleshooting](#14-troubleshooting)
15. [Laptop companion](#15-laptop-companion)
16. [Resolved, and what is still open](#16-resolved-and-what-is-still-open)
17. [External sources](#17-external-sources)

## 1. Words used in this guide

| Word | Meaning |
|---|---|
| Top side | The side the switches, diodes, encoder and OLED sit on. It says `FROSTBITE` and `XIAO ON BACK`. |
| Underside | The side the XIAO and all 13 LEDs solder to. It says `XIAO HERE`. |
| Back edge | The edge with the USB-C connector. |
| Front edge | The edge nearest you when you use the pad. |
| Joint | One solder connection. |
| Tail | The piece of a wire lead sticking out past a joint. |
| Pad | The bare metal patch on the board that you solder to. |
| Short | Two things connected that should not be. |
| Chain | The 13 LEDs in a line. Each LED passes data to the next. |
| Coupon | A small test print that checks one risky fit. |

**Left and right swap when you turn the board over.** This guide always says which view it means. Keep the back edge
away from you (at the top) in both views.

Underside view, USB at the top:

![PCB underside](../PCB/images/pcb_back.png)

XIAO pins seen from the underside, USB at the top:

| Left column | Net | | Right column | Net |
|---|---|---|---|---|
| D0 | ROW0 | | 5V | +5V |
| D1 | ROW1 | | GND | GND |
| D2 | ROW2 | | 3V3 | +3V3 |
| D3 | COL0 | | D10 | COL2 |
| D4 | SDA | | D9 | COL1 |
| D5 | SCL | | D8 | ENC_B |
| D6 | LED_DIN | | D7 | ENC_A |

**Source:** `design.json` (`pins`), `PCB/frostbite.kicad_pcb`, `PCB/README.md` (Nets).

## 2. Tools

| Tool | Used for |
|---|---|
| Multimeter with continuity and diode modes | Every check in section 8 |
| Calipers | OLED, printed pitch, tail length, module squareness |
| Needle file | A tight LED cut-out, or an encoder barb that will not pass |
| Soldering iron with a tip for heat-set inserts | Inserts |
| USB-C cable that carries data | Everything after first power. A charge-only cable will not work. |
| Small pliers | Sliding the black plastic off the OLED header |
| Two blocks at least 22 mm tall | Holding the Top upside down in Stage K |
| Black tape and printer paper | Glow coupon, and paper strips as a feeler gauge on the pocket coupon |
| Switch puller | Only if the PCB must come out later |

Also get these *(general practice)*:

- A temperature-controlled iron with a fine tip. A long, slim tip helps at the switch joints.
- Thin rosin-core solder. Adafruit calls 60/40 leaded solder the easiest to work with.
- Flux, solder wick and a tip cleaner.
- Fine tweezers. The LED datasheet says to pick parts up with tweezers and not to press on the lens.
- Flush cutters and safety glasses, because cut tails fly.
- A magnifier and a way to hold the board still.
- A driver that fits the kit's M3 screws. The shaft must reach down a 5.8 mm hole, up to 4.2 mm deep.

Safety: work with ventilation, wash your hands after handling leaded solder, and put the iron in its stand every time
*(general practice)*. The datasheet warns that SK6812s can be damaged by static and are bright enough to hurt your eyes,
so use anti-static precautions and do not stare at them.

**Iron temperature.** The repo gives no iron temperature. Adafruit's soldering guide says to set
[370 °C for 60/40 or 400 °C for lead-free](https://learn.adafruit.com/adafruit-guide-excellent-soldering).
The LED datasheet gives no hand-soldering figure. Its only related test is
[260 °C for 10 s, 3 times](https://cdn-shop.adafruit.com/product-files/4960/4960_SK6812MINI-E_REV02_EN.pdf) (p.12).
So keep each LED touch short, and let a joint cool before you try it again.

**Source:** `CAD/README.md` (Assembly order), `docs/audit/pcb-physical.md`, [SK6812 MINI-E datasheet](https://cdn-shop.adafruit.com/product-files/4960/4960_SK6812MINI-E_REV02_EN.pdf) pp. 12, 17, 18.

## 3. Parts check against the kit

Count everything before you heat anything.

| Kit part | In kit | Used | Spare | Check |
|---|---:|---:|---:|---|
| Seeed XIAO RP2040 | 1 | 1 | 0 | No spare, so take care. |
| Gateron Yellow KS-3 switches | 16 | 9 | 7 | 5-pin: 2 metal pins, 2 side pegs, 1 centre post. Pins straight. |
| White blank DSA keycaps | 16 | 3 | 13 | For Approve, Talk, Stop. |
| 1N4148 diodes | 20 | 9 | 11 | Black band at one end. |
| Alps EC11E encoders | 2 | 1 | 1 | Check the shaft has a D-flat. |
| 0.91" OLED | 1 | 1 | 0 | Read the pin labels now. See below. |
| SK6812 MINI-E LEDs | 16 | 13 | 3 | Only 3 spares. Handle gently. |
| M3 × 16 screws | 6 | 4 | 2 | |
| M3 heat-set inserts | 6 | 4 | 2 | OD 5, length 4. Coupon 2 uses the spares. |

You also need these, from outside the kit:

| Item | Qty | Note |
|---|---:|---|
| PCB, 61.15 × 83.15 mm | 1 | From `production/gerbers.zip`. You get 5, so you have 4 for practice and coupon 3. |
| Top, Bottom | 1 each | Iced PETG. |
| GlowBand | 1 | Clear or natural PETG. |
| OLEDSupport | 1 | Any PETG, dark hides best. |
| Coupons | 5 prints | See section 5. |
| Frosted translucent DSA keycaps | 6 | For agent keys 1-6. Kit caps are opaque, so colours would not show. |
| Knob, 18 mm, 6 mm D-shaft | 1 | Buy, or print `production/Knob.stl`. |
| Thin double-sided tape | 1 roll | About 0.2 mm. Not foam tape. |
| Stick-on feet | 4 | The case has no feet of its own. |

Printing Legion promises no material, so ask the printer about iced and clear PETG, and about the coupons, before you post.

Check these on the real parts:

1. **OLED labels.** Hold the module display side up with the header end on your right. From back to front the pins
   should read `GND`, `VCC`, `SCL`, `SDA`, matching the silkscreen beside J1. Some clones swap GND and VCC, and a swap
   would reverse-power the module. If yours differs, stop. The repo has no fix for a swapped module.
2. **OLED header.** The kit list names no header, so look for one. If it is missing, buy a 4-pin 2.54 mm header. The long
   pins must point away from the display.
3. **PCB markings.** Find `XIAO HERE`, four `LENS OUT` marks, the two-line LED legend and `GND VCC SCL SDA` beside J1.
4. **LED fit.** On a spare PCB, drop one LED into a cut-out. If it binds, ease the cut-out with a needle file.

**Source:** `docs/BOM.md`, `PCB/README.md` (Assembly, OLED pin order), `docs/audit/pcb-physical.md`, `docs/audit/hackpad-rules.md` (Printing Legion risk).

## 4. Lessons from other builds

These are real failures on other Hackpads. Each one shaped a step below.

| What went wrong | What to do here |
|---|---|
| A first-time solderer could not fit the LEDs, **pulled up a trace** and shipped with no RGB. | Practise first (below). Never pull a part that is still held by solder. Frostbite has 13 LEDs on small pads (0.82 × 1.25 mm), thin 0.2 mm signal tracks and only 3 spares. |
| An encoder went on the wrong side, and a leg snapped off during removal. Only the kit's spare saved the build. | Fit the encoder from the top side and check twice before you solder. |
| A diode went in backwards and the builder had no tools to fix it. | Check the band on every diode before soldering. Have wick ready. |
| Firmware compiled but had never met hardware, and was replaced a month later. | Frostbite is the same so far. Treat the `led-test.uf2` results as real news. |
| LED power needed rework after the build. | Run the LED data checks in section 11 before you go further. |
| Prints did not fit first time, and measurements were the regret. | Print the coupons in section 5 first. |

**Practise before you touch the real board.** You have spare PCBs and 11 spare diodes. Solder diodes on a spare board
until your joints look smooth and shiny. Then practise tacking a small part on spare LED pads. Spare LEDs are few, so do
not use them all.

**How to avoid ripping a trace** *(general practice)*:

- If a joint needs fixing, add flux and reheat. Do not press or lever the part.
- To remove a part, melt all its joints first, with wick or by alternating the iron. Lift only when it moves freely.
- Never hold the iron on one pad for a long time. Stop, cool, and try again with more flux.

**Source:** `docs/audit/hackpad-rules.md` (section 3).

## 5. Test prints (coupons)

**Do this first, before the full case prints.** The coupons are small pieces cut from the real case. The files are in
[`docs/coupons/`](coupons/README.md), and that page has every result and fix in full.

| Print | Checks | Material | Estimated |
|---|---|---|---|
| 1 Plate | Switch cutouts and printer scale | Iced PETG | 21 min, 5.5 g |
| 2 Inserts | Insert hole size | Iced PETG | 28 min, 6.6 g |
| 3 Pocket + USB | PCB fit and your USB cable | Iced PETG | 24 min, 6.1 g |
| 4 Glow band | How far light carries | Clear or natural PETG | 10 min, 2.3 g |
| 4 Glow cap | Stands in for the PCB | Iced or opaque PETG | 4 min, 0.9 g |

Print them with the settings the case will use: PETG, 0.4 mm nozzle, [240 °C, bed 80 °C](../CAD/README.md#print-settings),
4 perimeters, 25 % gyroid, no supports. Keep hole or XY compensation off for the first run. The glow band uses 100 % infill.
Print the OLEDSupport and the knob at the same time.

**Coupon 1, scale.** Measure centre to centre across the three columns. It should read **38.10 mm**. If the error is over
0.3 %, fix the slicer's XY shrinkage first. Do not change the CAD.

**Coupon 1, switches.** Push a real switch in from the flat side.

| Result | Do this |
|---|---|
| 14.0 clips firmly and does not rock | Nothing |
| 14.0 is too hard, 14.1 is good | Slicer hole/XY compensation of 0.05 |
| 14.0 is loose, 13.9 is good | Reduce hole compensation or flow, then reprint. Do not change the CAD. |

**Coupon 2, inserts.** You have **2 spare inserts**, and the case needs the other 4, so do not use one in every hole.

1. Heat-set one spare into the **Ø4.7** hole, using the method in section 6.
2. Pass an M3×16 through the spacer ring into the insert and tighten until snug.
3. If it goes in straight and stays put, you are done. Keep the second spare.
4. If it spins or pulls out, use the second spare in Ø4.5. If it needed heavy force or the wall bulged, use it in Ø4.9.

**Coupon 3, PCB pocket.**

1. Clip one spare switch into the cutout from the flat side.
2. Lower a bare spare PCB onto its pins, front-left corner into the coupon's corner. Do not solder anything.
3. Use strips of printer paper, about 0.1 mm each, as a feeler at each step.
4. One sheet at 0.2, two at 0.3 and three or more at 0.4 means it printed as intended.
5. If 0.3 stops the board, read the coupon page before you print the case.

**Coupon 3, USB.** Push your real cable through the block from the top. The moulded boot should enter freely for at least
6 mm. If not, try another cable.

**Coupon 4** needs a lit glow LED, so it waits for [Stage F](#stage-f-flipped-glow-leds).

**Measure the OLED now** ([section 11](#oled-ribbon-clearance)). It decides whether the Top needs changing.

**When to print the full set.** Send the Top and Bottom after coupons 1 to 3 and the OLED measurement pass. You can solder
Stages A to F with no case at all, so hold the GlowBand print until coupon 4 passes if your printer allows it.

**Source:** `docs/coupons/README.md`, `CAD/README.md` (Print settings, Assembly order), `docs/BOM.md` (Kit usage).

## 6. Heat-set inserts

**When:** as soon as the Top arrives, and always before the PCB goes near it.

**Which side:** the four holes open at the skirt rim, in the side walls of the Top. Stand the Top skirt-up so the holes
face you. The Bottom and GlowBand get no inserts.

**Temperature:** start at [about 230 °C](../CAD/README.md#assembly-order), the repo's figure. CNC Kitchen gives
[245 °C for PETG](https://cnckitchen.com/blog/tips-and-tricks-for-heat-set-inserts), or 10-20 °C above print temperature.
Use coupon 2 to find yours: go hotter only if the insert will not sink under light pressure.

1. Sit the Top skirt-up on a flat surface.
2. Set one insert on a hole. It should sit straight.
3. Put the hot tip into the insert and press lightly. Let it sink under heat. Do not push hard.
4. Melt it in about 90 % of the way, then finish with a flat tool, as CNC Kitchen advises.
5. Press it flush with the rim and hold it still for a moment so it does not creep back.
6. Keep the iron off the rim and walls. The wall around each insert is only about 2 mm thick.
7. Repeat for all four.
8. After cooling, run an M3 screw in by hand. It should go straight.

There is clearance hole beyond each insert, so displaced plastic has somewhere to go. If it pushes up into the screw hole,
press more slowly and clear the hole with an M3 screw while it is warm.

**Source:** `CAD/README.md` (Assembly order step 1, What `check_fit.py` verifies), `docs/coupons/README.md` (coupon 2), `docs/audit/case.md`.

## 7. Soldering order

| Stage | Part | Why it comes here |
|---|---|---|
| A | Bare board check | Finds a board fault before parts hide it. |
| B | XIAO | Every later test needs it. Flashing needs nothing else. |
| C | First flash | Proves USB and the XIAO before you add 13 LEDs. |
| D | LED1 alone | LED1 is the one LED that sees 3.3 V data. If it fails, all 13 fail. |
| E | LED2 to LED9 | The chain feeds the glow LEDs, so these must work first. |
| F | LED10, tested, then LED11 to LED13 | One test catches a wrong fit before you repeat it three times. |
| G | Diodes | They lie flat and go under the plate. |
| H | Encoder | Tall, and goes in before the board meets the Top. |
| I | Trim tails | The GlowBand sits 0.6 mm below a 2.0 mm tail. |
| J | OLED, soldered to J1 | Once soldered it cannot fall away when the PCB turns over. You can also test it while everything is open. |
| K | Switches | The PCB can only enter the Top with the switches clipped in. |

### Stage A: bare board

1. Do [check A](#check-a-bare-board) on the PCB you will use.

### Stage B: XIAO, castellated, on the underside

Why flat: it is soldered by its edge pads, so no pins poke up under the OLED.

1. Turn the board underside up. Find `XIAO HERE`.
2. Lay the XIAO flat on that outline with **its components facing you, away from the PCB**.
3. Point USB-C at the back edge. Line up the XIAO board edge with the PCB edge. The USB connector overhangs a little, which is correct.
4. Check the 14 XIAO edge pads sit over the 14 PCB pads, 7 per side.
5. Tack one corner. Check the XIAO is flat and square. Then tack the opposite corner.
6. Solder all 14 pins. Touch the iron to the exposed PCB pad at the XIAO's edge and feed solder.
7. If a pin is hard to reach, there is a second method: from the top side, heat the pad and feed solder down the plated hole.
8. Take extra care with the GND pin, second from the USB end. It is the XIAO's only GND link, so a bad joint takes out the
   LEDs, OLED and keys together.
9. Do not leave solder blobs under the XIAO.

Fitting it on the top side would mirror the pinout and put 5V onto D0. That is why the top side says `XIAO ON BACK`.

### Stage C: first flash

1. Do [check B](#check-b-after-the-xiao).
2. Do [the first flash](#first-flash-on-a-blank-xiao).

### Stage D: LED1 alone

**Fit for LED1 to LED9:** lens **into** the hole, back of the part facing you. Light goes up into the switch.

The lens is the side with the ring. The back has a rib and a small round mark.

1. Unplug USB.
2. Find LED1 on the underside. It is under SW1.
3. Tin one pad lightly. Use the pad beside the triangle.
4. Hold the LED with tweezers. Drop the body into the cut-out, **back facing you**.
5. Put the chamfered lead on the triangle pad. The triangle marks GND, pad 3.
6. Reheat that pad until the lead sinks in. Keep it short.
7. Check all four leads sit on their pads. Then solder the other three.
8. Do [check C](#check-c-after-each-led), then the [LED1 test](#led1-test).

### Stage E: LED2 to LED9

1. Fit one LED the same way. Lens into the hole, chamfer on the triangle.
2. Unplug, do check C, plug in, and confirm it lights in turn.
3. Repeat in chain order. Testing as you go means a fault can only be the LED you just fitted.

LED9's GND pad, and LED11's in the next stage, connect by tracks and not by the copper pour. Both are normal.

### Stage F: flipped glow LEDs

**Fit for LED10 to LED13: flipped. Lens OUT, facing you, back of the part in the hole.** Light goes down into the glow
band. Look for the `LENS OUT` text and the ring-and-dot mark beside each one. The legend mid-board says
`LED1-9: LENS INTO HOLE` and `LED10-13 FLIPPED: LENS OUT`.

Nothing physically stops a wrong fit, because the cut-out takes either face. After nine LEDs, your hands will want to do the same again.

1. Stop and read the marks at LED10.
2. Put the ring-side lens toward you and the back into the hole.
3. Put the chamfered lead on the triangle. **Both must be true: lens out and chamfer on triangle.**
4. If you cannot get both at once, the part is the wrong way up. Stop and turn it over.
5. Solder LED10 the same way as the others.
6. Do check C, then run `led-test.uf2`. LED10 must light, facing you.
7. Do the glow coupon below.
8. Fit LED11, LED12 and LED13, testing each.

**The triangle is your check.** The four pads form a 5.55 × 1.5 mm rectangle, so a part can only sit at 0° or 180°. A part
that is the wrong way up can never put its chamfered lead on the triangle.

**What goes wrong if fitted like the others.** Neither VDD nor GND reaches its own pad. At LED10:

| Position | VDD lead on | DOUT lead on | GND lead on | DIN lead on |
|---|---|---|---|---|
| Correct, lens out | +5V | `LED_D10` | GND | `LED_D9` |
| Lens in, 0° | `LED_D9` | GND | `LED_D10` | +5V |
| Lens in, 180° | `LED_D10` | +5V | `LED_D9` | GND |

The supply leads end up on data nets and the rails on the data pins. Expect the glow chain to stay dark, the light to go into
the board, and LED9's output to be at risk because it feeds `LED_D9`. This is worked out from the pad geometry, and nothing has
been built. Do not leave a suspect glow LED powered. Unplug and fix it.

Where they go, seen from the underside with USB at the top:

| LED | Corner, underside view |
|---|---|
| LED10 | Back right |
| LED11 | Back left |
| LED12 | Front left |
| LED13 | Front right |

**Glow coupon, with LED10 working.** See [section 11](#glow-brightness).

### Stage G: diodes, band toward the front edge

Why now: they lie flat and are easy to reach. The plate sits 2.5 mm above the PCB, so a raised diode would hit it.

1. Top side up, back edge away from you.
2. Find D1. Each diode sits to the right of its switch. The square pad is marked `K`.
3. Bend the leads to fit the holes, 7.62 mm apart.
4. Put the **black band on the `K` end**. On all nine diodes that is the end **nearest the front edge**.
5. Check the band against the silkscreen on this diode before you solder it.
6. Press it flat onto the board. It must end up at most 2.2 mm tall.
7. Turn the board over and solder both leads.
8. Do the first diode, then check it with [check D](#check-d-after-the-diodes) before you do all nine.

The band points at the row: cathode to the row, `COL2ROW`. A backward diode means a dead key.

### Stage H: encoder

1. Fit it from the **top side**. Check this twice. The body sits on the same side as the diodes.
2. Turn it so the three-pin row (A, C, B) faces the keys and the two-pin row faces the back edge.
3. Press straight down until the side lugs snap through their slots. Expect a firm press.
4. If a barb will not pass, file it. Do not force it, because that puts the plated hole at risk. Lug figures come from
   Alps' model, and a kit clone may differ.
5. Check it sits flat and square.
6. Turn the board over. Solder the three pins, the two lugs and the two pins of the unused push switch *(general practice: the push switch has no signal, but the joints add strength)*.
7. The lugs and pin C go to GND and need a little longer to heat.

### Stage I: trim tails

1. On the underside, cut all through-hole tails (diodes, encoder) to **2.0 mm or less**.
2. Do [check E](#check-e-after-the-encoder-and-tails).

### Stage J: OLED, soldered to J1

The OLED goes on now, on the bench, with the top of the PCB facing up. The black header plastic comes off and the printed
OLEDSupport sets the height instead. With the plastic on, the glass would stand proud of the plate.

1. Compare the module's labels with the silkscreen beside J1 once more.
2. If the header is loose, put its short pins up through the module from underneath. The black plastic goes on the
   underside. Solder the four pins and trim them **flush on the display side**.
3. **Slide the black plastic strip off the pins**, toward their free ends, with small pliers. Work from both ends. The pins stay
   soldered to the module, so do not pull on the joints. Nobody has tried this by hand yet, so go gently.
4. Put thin double-sided tape on **both faces of the OLEDSupport's two feet**. Use about 0.2 mm tape, not foam tape.
5. Try the fit first with the backing on *(general practice)*. The small foot sits beside the pins, the large foot sits at
   the far end, and the rail runs outside the module on the side facing the keys.
6. Stick the support to the underside of the module.
7. Put the pins through J1, display up, until the support sits on the PCB and sticks.
8. **Square the module now.** Measure from the PCB's back edge to the module's long edge at both ends. Both should read
   **7.0 mm** and agree within 0.5 mm.
9. Turn the board over. The tape holds the module.
10. Solder the 4 J1 pins from the underside, and trim them to **2.0 mm or less**.
11. Do [check F](#check-f-after-the-oled).
12. **Test now, while BOOT is easy to reach:** plug in and run `led-test.uf2`. Read the OLED and turn the knob. See
    [OLED flip](#oled-flip) and [EC11 resolution](#ec11-resolution).

The module is held by its pins and tape, and it should stay square. That has not been tested on real parts.

### Stage K: switches

The Top's plate closes one side, so the PCB can only enter from the skirt side. The switch flange is wider than the plate
cutout, so switches must clip in from the top face. That is why they go into the plate first and get soldered through the PCB.

1. Measure SW1 to SW3 on the full Top: 38.10 mm centre to centre.
2. Clip all 9 switches into the plate **from the top face**. Press until the clips seat.
3. Check every switch pin is straight.
4. Turn the Top upside down on **two blocks at least 22 mm tall**, under the plate margin. The switch stems stand 10.2 mm
   proud, and the encoder shaft will stand 19.5 mm proud, or 21.5 mm on a generic EC11. Shorter blocks stop the PCB from seating.
5. Hold the PCB with its underside facing you. Lower it straight down the skirt.
6. **Start the encoder shaft in its opening first**, about 22 mm before the PCB seats.
7. Keep going. In order: the PCB enters the skirt, the USB enters the notch, the switch pins meet their holes, and the OLED
   glass meets its recess last.
8. Do not force it. If it stops, lift it out and look for a bent pin.
9. Solder the 18 switch joints from underneath (2 per switch).
10. **How the iron reaches:** the PCB underside sits 9.4 mm below the skirt rim. The closest switch pin is about 8 mm from
    the wall, so lean the iron about 40 degrees at the rim. That is a normal angle. Keep the hot shaft off the printed wall.
11. Take care at SW3 pin 2. It is the closest joint to any LED, about 1.1 mm from LED11's GND pad, and its pad is smaller than
    the others. Use a small amount of solder and check for a bridge.
12. Trim the switch tails to **2.0 mm or less**.
13. Do [check G](#check-g-after-the-switches).
14. Test every key with `led-test.uf2`.

The PCB now hangs from the 9 switches. Nothing rests under it, and that is by design.

**Source:** `CAD/README.md` (Assembly order, Design decisions), `PCB/README.md` (Assembly, Placement, Encoder lugs, GND pours), `PCB/frostbite.kicad_pcb`, `CAD/frostbite_case.py`, `docs/audit/electrical.md`, `docs/audit/pcb-physical.md`, `docs/audit/case.md`, `docs/audit/round2-hardware.md`.

## 8. Multimeter checks before power

**USB unplugged for every continuity check.** A steady tone between two points means they are connected.

A short chirp that fades can be a capacitor charging. A steady tone means a short *(general practice)*. With parts
fitted, a meter may also show a resistance value, which is fine so long as it is not near zero.

If a "must not beep" check beeps, **do not plug in**. Look for a solder bridge, clean it with wick, then test again.

### Check A: bare board

| Probe between | Expect |
|---|---|
| 5V pad and GND pad | No tone |
| 3V3 pad and GND pad | No tone |
| 5V pad and 3V3 pad | No tone |
| D0 and D1, D1 and D2 (rows) | No tone |
| D3 and D9, D9 and D10 (columns) | No tone |

### Check B: after the XIAO

| Probe between | Expect |
|---|---|
| **5V and GND** | **No steady tone. This is the check that matters most.** |
| **3V3 and GND** | **No steady tone** |
| 5V and 3V3 | No steady tone |
| Each XIAO pin and the next pin down, both columns | No tone |
| XIAO GND and J1 pin 1 | Tone |
| XIAO 3V3 and J1 pin 2 | Tone |
| XIAO 5V and LED1 pad 1 | Tone |

A silent reading from XIAO GND to J1 pin 1 means the XIAO's only GND joint is bad.

### Check C: after each LED

| Probe between | Expect |
|---|---|
| **5V and GND** | **No steady tone** |
| LED pad 1 and pad 2 | No tone |
| LED pad 3 and pad 4 | No tone |

The two pads on each side of an LED are only 0.68 mm apart, so they are the likely bridges.

### Check D: after the diodes

1. Set the meter to diode mode.
2. Put the red probe on the anode end and black on the `K` end. You should get a reading.
3. Swap the probes. You should get no reading.
4. If it reads the wrong way round, the diode is backwards. Fix it now.
5. Repeat the row and column checks from check A.

### Check E: after the encoder and tails

| Probe between | Expect |
|---|---|
| 5V and GND | No steady tone |
| ENC1 pin A and GND | No tone |
| ENC1 pin B and GND | No tone |
| ENC1 pin C and GND | Tone |
| D0 to D10, each against GND | No tone |

Measure the tails. Any tail over 2.0 mm gets cut.

### Check F: after the OLED

| Probe between | Expect |
|---|---|
| **5V and GND** | **No steady tone** |
| **3V3 and GND** | **No steady tone** |
| SDA and SCL (D4 and D5) | No tone |

### Check G: after the switches

| Probe between | Expect |
|---|---|
| **5V and GND** | **No steady tone** |
| SW3 pin 2 and LED11 pad 3 | No tone |

Then press each key while you probe its row and column. It should only connect with the key held down, and through a diode.

### First voltage reading

The first time you plug in, set the meter to DC volts:

| Probe between | Expect |
|---|---|
| 5V and GND | About 5 V. This is raw USB power. Write it down for section 11. |
| 3V3 and GND | About 3.3 V |

**Source:** `docs/VERIFICATION.md` (G10), `PCB/frostbite.kicad_pcb`, `docs/audit/electrical.md`, `docs/audit/pcb-physical.md`.

## 9. Flashing led-test.uf2

`production/led-test.uf2` is the test program. Keep it on the XIAO until the LEDs, OLED, knob and keys have all passed.

### Bootloader access

BOOT and RESET sit on the XIAO's component side, at the end away from USB. They stay reachable from the open skirt until
the GlowBand goes on. After that they face the sealed chamber with no access hole, and reaching them means taking out the 4
screws. With the case closed, only Approve + Stop works, and only if the keys and firmware are good.

Seeed's wiki calls these buttons B and R.

### First flash on a blank XIAO

**Use the BOOT button for this one.** The double-tap and the Approve + Stop combo are both part of the Frostbite firmware,
so they cannot work until Frostbite firmware is on the XIAO. Neither the repo nor Seeed's wiki says what program a new XIAO
ships with, so assume nothing.

1. Unplug the XIAO.
2. Press and hold **BOOT**.
3. Plug the USB-C cable into the laptop while you hold it.
4. Let go.
5. A drive named **RPI-RP2** appears.
6. Drag `production/led-test.uf2` onto it.
7. The board reboots by itself and the drive goes away.

Check the laptop sees it, from the repo root:

```sh
cd host && uv run python -c "from frostbite_host.device import HidTransport; print(HidTransport.find())"
```

A non-empty list means the pad is running Frostbite firmware.

### What the first flash results mean

| Result | Meaning | Next |
|---|---|---|
| RPI-RP2 appears, flash works, the check lists a device | USB, XIAO and power are good | Go to Stage D |
| RPI-RP2 does not appear | Charge-only cable, or BOOT was released too early | Try a data cable, and hold BOOT longer |
| Laptop reports a USB problem, or the XIAO gets hot | Possible short | Unplug at once. Redo check B. |
| RPI-RP2 appears, but no device afterwards | Drag failed, or the file is wrong | Flash again and check the file name |

### LED1 test

Use your highest-voltage USB port. With only LED1 fitted, it lights red, green, blue, white, then **stays dark for about 17
seconds**. That is normal: the test runs through all 13 positions whether the LEDs exist or not. Each LED gets 1.4 s (4
colours at 350 ms), so a full pass takes 18.2 s.

| Result | Meaning | Next |
|---|---|---|
| Red, green, blue, white, steady | LED1 and data are good | Go on |
| Never lights | Bad joint, wrong way round, or data level too low | See section 10, then section 11 |
| Flickers or shows random colours | 3.3 V data is marginal | Section 11, [LED data level](#led-data-level) |
| Colours in the wrong order, such as green during the red step | Colour order fault | A firmware fault, not soldering. Note it. |

### Full led-test results

The OLED shows this once J1 is soldered. Before that, use the timing above. The test runs fine with no OLED.

```
LED TEST 5/13
colour: green
key: r1 c2
knob: 3
```

| LED | Chain position | Location, top view | Lights after LED1 |
|---|---:|---|---:|
| LED1 | 1 | Under SW1, Agent 1 | 0 s |
| LED2 | 2 | Under SW2, Agent 2 | 1.4 s |
| LED3 | 3 | Under SW3, Agent 3 | 2.8 s |
| LED4 | 4 | Under SW6, Agent 6 | 4.2 s |
| LED5 | 5 | Under SW5, Agent 5 | 5.6 s |
| LED6 | 6 | Under SW4, Agent 4 | 7.0 s |
| LED7 | 7 | Under SW7, Approve | 8.4 s |
| LED8 | 8 | Under SW8, Talk | 9.8 s |
| LED9 | 9 | Under SW9, Stop | 11.2 s |
| LED10 | 10 | Glow, back left | 12.6 s |
| LED11 | 11 | Glow, back right | 14.0 s |
| LED12 | 12 | Glow, front right | 15.4 s |
| LED13 | 13 | Glow, front left | 16.8 s |

The middle row runs right to left, so the order zig-zags. That is correct.

After the switches are in, each key should show once:

| Key | OLED shows | | Key | OLED shows | | Key | OLED shows |
|---|---|---|---|---|---|---|---|
| Agent 1 | `r0 c0` | | Agent 2 | `r0 c1` | | Agent 3 | `r0 c2` |
| Agent 4 | `r1 c0` | | Agent 5 | `r1 c1` | | Agent 6 | `r1 c2` |
| Approve | `r2 c0` | | Talk | `r2 c1` | | Stop | `r2 c2` |

Keys send their fallback codes during this test, so Stop sends Escape to the laptop. Turning the knob changes `knob:` without changing the volume.

**Source:** `Firmware/README.md` (Flash, Keymap), `Firmware/qmk/keyboards/frostbite/keymaps/ledtest/keymap.c`, `Firmware/qmk/keyboards/frostbite/config.h`, `Firmware/qmk/keyboards/frostbite/frostbite.c`, `docs/audit/case.md`, `docs/audit/firmware.md`, `host/README.md` (Install), [Seeed XIAO RP2040 wiki](https://wiki.seeedstudio.com/XIAO-RP2040/).

## 10. Finding a dead LED

**What it looks like.** Each LED rebuilds the data signal for the next one. So one bad LED or joint usually darkens itself
**and every LED after it**, while the OLED keeps counting up through the dark ones. LEDs before the fault work normally.

If LED n works and LED n+1 never lights, the fault is in LED n's DOUT, LED n+1's DIN, or LED n+1's 5V or GND.

Pad numbers: 1 = 5V, 2 = DOUT, 3 = GND (triangle), 4 = DIN.

1. Note the last LED that works. Call it n.
2. Unplug USB.
3. Look at both LEDs under a magnifier. Check the leads sit on their pads and the fit is right for that LED.
4. Check continuity from LED n pad 2 to LED n+1 pad 4. Expect a tone.
5. Check LED n+1 pad 3 to XIAO GND. Expect a tone.
6. Check LED n+1 pad 1 to XIAO 5V. Expect a tone.
7. Plug in. Measure LED n+1 pad 1 to pad 3 in DC volts. Expect about 5 V.
8. Reflow any doubtful joint with flux.
9. If the wiring is good and it stays dark, replace LED n+1. You have 3 spares.
10. If the replacement stays dark too, replace LED n, since its DOUT may be dead.

**Removing an LED without ripping a trace** *(general practice)*:

1. Add flux and fresh solder to all four joints.
2. Heat one side's two leads and then the other's, or use wick to clear each side.
3. Lift only when the part moves on its own.
4. Clean the pads with wick, gently. Do not scrub.

Single-LED faults that do not affect the chain:

| Symptom | Likely cause |
|---|---|
| One colour missing on one LED | A damaged LED. Replace it. |
| LED works but looks dim through the switch | Lens position against the switch window. This is unproven and affects brightness only. |
| Key LEDs fine, all glow LEDs dark | LED10 fitted wrong. See Stage F. |

**Source:** `Firmware/README.md` (Flash), `Firmware/qmk/keyboards/frostbite/keymaps/ledtest/keymap.c`, `PCB/README.md` (Nets), `docs/audit/electrical.md`.

## 11. Needs real parts: measure and adjust

No file check can prove these five things. Only you can settle them.

| Item | When | Setting to change |
|---|---|---|
| OLED ribbon clearance | Before the Top prints | `oled.window` in `design.json`, then reprint the Top |
| LED data level | Stage D and after Stage F | **No setting exists** |
| Glow brightness | When LED10 works | `GLOW_DEFAULT_BRI` in `keymap.c`, and `glow()` in `host/frostbite_host/state.py` |
| OLED flip | Stage J | `FROSTBITE_OLED_FLIP` in `config.h` |
| EC11 resolution | Stage J | `encoder.rotary[0].resolution` in `keyboard.json` |

### OLED ribbon clearance

**What is unknown:** nobody has measured the kit OLED, and no drawing of it was found. The ribbon and tape at the far end have
to fit under a printed lip. The numbers below are allowances, not facts.

Measure the kit module with calipers:

1. Module board thickness at a plain edge.
2. Thickness at the far end (the end away from the header), over the folded ribbon and tape.
3. Subtract: that is the ribbon height above the board.
4. How far the ribbon or tape runs past the far end of the board.
5. Glass position from both ends of the module, and the module's length.
6. Any parts on the module's underside where the support feet touch: 1 to 7 mm from the far end, and 3.1 to 8.3 mm from
   the header end.
7. Joint height after trimming, at the header end.

| Measure | Room in the design | If it does not fit |
|---|---|---|
| Ribbon height above the board | 1.0 mm | Widen `oled.window` through the far lip, as both reference builds do |
| Ribbon past the far board end | 1.1 mm | The same |
| Joint height after trimming | 1.0 mm | Trim again, or thin the lip locally (a CAD change) |
| Part on the module's underside at a foot | None planned | Move the feet in `CAD/frostbite_case.py`. A part on a foot lifts that end. |
| Glass thickness | 1.45 mm assumed, 1.2 mm exists | Thinner only sinks the glass further |
| Module length | 38 mm assumed, 36 mm exists | The glass moves in the window. Shift the window. |

After changing `design.json`, rerun `CAD/frostbite_case.py` and `CAD/check_fit.py`, then send the new Top. Decide before you print.

### LED data level

**What is unknown:** the LEDs' datasheet asks for 3.5 V data at 5 V power, and the XIAO gives 3.3 V. Only LED1 sees this, but
LED1 feeds all 13. The data only meets the spec if USB power falls to 4.71 V (3.3 / 0.7). This batch's real threshold is unmeasured.

The hardest case is LED1 alone on your highest-voltage USB port, because higher power raises the threshold.

1. Measure 5V to GND on the XIAO on each port. Use the highest.
2. Run `led-test.uf2` with LED1 alone. Watch for flicker or wrong colours.
3. Repeat with all 13 fitted. Every LED must step through its colours cleanly.
4. Once `firmware.uf2` is on, run the all-LEDs check in [section 15](#install). All 13 light together.
5. Try each USB port and cable you will use.

No shipped build runs the whole chain at full white. `led-test` lights one LED at a time at level 90 of 255, and the
normal firmware caps total output at 40 % of full scale.

**There is no single setting for this.** It is not a firmware option. If LED1 is unreliable, the only remedy is to feed its VDD
through a spare 1N4148, which drops it to about 4.3 V. The board has no footprint for that, so it means cutting a trace. Stop
and get advice before you cut anything.

### Glow brightness

**What is unknown:** whether the 2 mm band glows enough. The estimate says it is visible in a dim room and faint in a bright one,
with hot spots near the LEDs and the back edge dimmest.

Use coupon 4 with LED10 working. `led-test` never shows the glow colour, so use the real firmware:

1. Cover the two cut end faces of the band coupon with black tape, or they will glow and mislead you.
2. Flash `firmware.uf2` ([section 12](#12-flashing-firmwareuf2)). Run it with no daemon. The glow shows ice blue `#7fe3ff` at
   70 of 255, about 27 %.
3. Hold the band under LED10 at its real position. Leave the cap off.
4. Look at the 2 mm outer face in a normally lit room, then a dim one.
5. Flash `led-test.uf2` again before you carry on.

| Result | Do this |
|---|---|
| Visible along the whole 31 mm run, even with a hot spot at the pad | Print the full band |
| Bright near the pad, gone within about 15 mm | Try 6 perimeters, or printing slower and hotter. Then foil or white paint on the skirt's inner wall. |
| Cloudy, layer lines, little carry | Raise temperature, slow down, 100 % infill, thicker layers |

This shows how far light carries, not the final brightness. The coupon has no skirt or Bottom, so it will look better than the
case. A phone torch only shows the shape of the spread.

To change brightness with no daemon, set `GLOW_DEFAULT_BRI` in `keymap.c` and rebuild. With the daemon running, `glow()` in
`host/frostbite_host/state.py` decides: 50 of 255 when nothing runs, 110 while something runs, and 160 for amber or red. A limiter caps
total LED output at 40 %, so more brightness will not always show.

### OLED flip

1. Run `led-test.uf2` with J1 soldered.
2. Read the text. It should be upright with the back edge away from you.
3. Upright: change nothing.
4. Upside down: comment out one line in `Firmware/qmk/keyboards/frostbite/config.h`, then [rebuild](#rebuilding):

   ```c
   // #define FROSTBITE_OLED_FLIP
   ```

The flip is on now because four reference Hackpads with this header position use it. No Frostbite module has confirmed it.

### EC11 resolution

1. Run `led-test.uf2`, and watch `knob:` on the OLED.
2. Turn the knob **one click** and see how far the count moves.
3. Change `encoder.rotary[0].resolution` in `keyboard.json`. It is 4 now.

| You see | Do this |
|---|---|
| One click moves the count by 1 | Nothing |
| One click moves the count by 2 | Double the value |
| Two clicks are needed for one count | Set it to 2. This is expected on a true 30-detent/15-pulse EC11E. |

Direction: clockwise should count up. If it counts down, swap `pin_a` and `pin_b` in `keyboard.json`. Do not resolder. That swap
makes `PCB/tools/check_netlist.py` and `verify` report a pin mismatch, so note it for whoever runs them next.

### Rebuilding

Any firmware change means a rebuild. You need QMK set up first ([QMK docs](https://docs.qmk.fm/newbs)). From `Firmware/`:

```sh
export PATH="$HOME/.local/bin:$HOME/Library/Application Support/qmk/bin:$PATH"
ln -sfn "$PWD/qmk/keyboards/frostbite" ~/qmk_firmware/keyboards/frostbite   # once
qmk lint    -kb frostbite
qmk compile -kb frostbite -km default
qmk compile -kb frostbite -km ledtest
cp ~/qmk_firmware/frostbite_default.uf2 ../production/firmware.uf2
cp ~/qmk_firmware/frostbite_ledtest.uf2 ../production/led-test.uf2
```

**Source:** `verify/REPORT.md` (Needs real parts), `Firmware/README.md`, `CAD/README.md` (Unknowns, Glow), `docs/coupons/README.md` (coupon 4), `Firmware/qmk/keyboards/frostbite/keymaps/default/keymap.c`, `host/frostbite_host/state.py`, `docs/audit/electrical.md`, `docs/audit/case.md`.

## 12. Flashing firmware.uf2

Do this after every key, the knob, the OLED and all 13 LEDs pass in `led-test.uf2`, **with the case still open**.

1. Enter the bootloader. Frostbite firmware is on the XIAO now, so any of these works:
   - Double-tap **RESET**, or
   - Hold **BOOT** while plugging in, or
   - Hold **Approve + Stop** (bottom-left and bottom-right keys) while plugging in. This also clears EEPROM. Both keys are required.
2. Drag `production/firmware.uf2` onto **RPI-RP2**.
3. The board reboots by itself.

With no laptop app running you should see this:

- Agent LEDs dim white, command keys dim white.
- Glow LEDs ice blue.
- OLED row 4 shows the slot strip, ending in `KBD`.
- Keys send F13 to F20 and Escape. The knob changes volume.

Press every key and turn the knob while you can still reach BOOT. On macOS, F14 and F15 may change screen brightness
in fallback mode. That has not been tested and is not a fault.

**Source:** `Firmware/README.md` (Flash, Keymap, Host mode), `Firmware/qmk/keyboards/frostbite/frostbite.c`.

## 13. Final assembly

Do not start until sections 9, 11 and 12 pass. After this, BOOT and RESET mean removing 4 screws.

1. Measure tails one last time. All must be 2.0 mm or less. Six diode joints sit right over the GlowBand's riser.
2. With the Top still upside down, lower the **GlowBand** onto the skirt.
3. The riser and pads go into the pocket, and the tongue goes into the USB notch.
4. Check the band sits flat, with no gaps.
5. Lay the **Bottom** on the band.
6. Put the 4 M3 × 16 screws in from underneath.
7. Turn each one a little at a time, working in a cross pattern *(general practice)*.
8. Stop each one as soon as it is **snug**.
9. Press on the 3 white caps (Approve, Talk, Stop) and 6 frosted caps (agent keys).
10. Fit the knob, with the D-flat lined up. Ream the bore if a printed knob is too tight.
11. Add 4 stick-on feet.
12. Plug in USB-C and check the plug seats fully.

**Screw torque.** The repo gives no torque number, so do not chase one. Its advice is to tighten until snug and no more,
because PETG creeps. Use a small hand driver, not a power driver *(general practice)*. Snug here means the head has
seated and the parts have closed up. The thread is in a metal insert with 4 mm of engagement, so an insert that spins or a
screw that suddenly gets loose means stop.

The screws sit nearer the back than the front (28 mm from the front skin, 16 mm from the back). If a part has warped, the band
gap opens at the front, where you will see it. Check this as you tighten. A screw that binds early is usually off its
thread, so back it out and start it straight.

Use the kit screws. A 16 mm screw stops 0.4 mm short of the blind end of its hole, so a longer one will not fit.

To take the PCB out later, release the 9 switches from the plate with a puller and lift it out with them, or desolder 18 joints.

**Source:** `CAD/README.md` (Assembly order), `docs/audit/case.md`, `docs/audit/round2-hardware.md`.

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| RPI-RP2 never appears | Charge-only cable, or BOOT released early | Use a data cable. Hold BOOT while plugging in. |
| Double-tap does nothing on a new XIAO | Double-tap is a Frostbite firmware feature | Use BOOT for the first flash |
| Approve + Stop does nothing | Firmware not on it, or keys or matrix not working | Use BOOT. Remove the 4 screws if closed. |
| Steady tone between 5V and GND | Solder bridge | Do not plug in. Check the last part you fitted, then the LEDs. |
| Everything dead after an LED is added | That LED or a bridge | Unplug. Do check C. |
| No LEDs light, OLED counts | LED1, or the D6 data joint | Section 10 |
| LEDs stop at one point | Fault at that LED or the next | Section 10 |
| Key LEDs fine, glow dark | LED10 wrong way up | Stage F |
| LEDs flicker | Marginal 3.3 V data | Section 11 |
| Glow visible only on the skirt, or too dim | Light path | Section 11 |
| OLED blank | J1 joint, or VCC/GND order | Check SDA, SCL, VCC, GND. Compare labels with J1. |
| OLED text upside down | `FROSTBITE_OLED_FLIP` | Section 11 |
| Black strip will not slide off | Tight header | Work from both ends, in small moves. Do not pull on the joints. |
| Glass catches on the window | Module not square | Check the 7.0 mm at both ends. The window allows about ±1° and ±0.1 mm. |
| Glass stands proud of the plate | Tape too thick, plastic left on, or a part under a foot | Check all three |
| One key dead | Bad switch joint, or diode backwards | Reflow. Do check D on that diode. |
| A row or column dead | XIAO pin joint on that row or column | Reflow that XIAO pin. Check its neighbour. |
| Pressing one key shows two | Bridge between row or column pins | Re-run the neighbour checks |
| Knob needs two clicks per step | `resolution` too high | Section 11 |
| Knob jumps two steps per click | `resolution` too low | Section 11 |
| Knob runs backwards | A and B order | Swap `pin_a` and `pin_b` |
| Knob too tight or loose | Untested print fit | Ream the bore, or use a bought knob |
| Switches too tight in the plate | Print tolerance | Coupon 1 in section 5 |
| PCB will not seat in the Top | Bent switch pin, or blocks under 22 mm | Lift out and check both |
| GlowBand will not sit flat | Tail over 2.0 mm, or printing | Trim tails and check again |
| Band gap at the front | Warped part | Recheck the screws, without over-tightening |
| USB plug will not seat | Plug overmold too big | Coupon 3. Cables up to about 13.4 × 7.9 mm should work. |
| Pad falls back to `KBD` | No PING for 5 s | Check the daemon runs |
| OLED went dark | 10-minute burn-in protection | Press a key or turn the knob |
| Approve does nothing | No hook is waiting on that slot | Answer in the terminal |
| OLED says `answer in terminal` | The pad cannot act on this one | Answer in the terminal |
| OLED says `tap slot first` | Another tab or app is in front when you press Stop | Tap the agent key, then press Stop |
| Stop refused every time | Automation permission missing | Section 15 |
| Stop interrupted the wrong app | No daemon running, so Stop is a plain Escape | Start the daemon |
| Laptop does not find the pad | Wrong cable, or firmware not flashed | Run the check in section 9 |

**Source:** `Firmware/README.md`, `host/README.md` (Approve, Keys), `CAD/README.md`, `docs/audit/case.md`.

## 15. Laptop companion

The pad works as a plain keyboard with nothing installed. The companion adds agent status, Approve and Stop.

**Nothing here installs itself.** Steps marked **BY HAND** change your own laptop. No script does them for you, and nothing
in the project edits your settings.

No real pad or real Claude Code session has run this yet, so expect to find things on your first try.

### Install

1. **BY HAND.** Install the host tools from the repo root. This needs `uv`.

   ```sh
   uv tool install ./host
   ```

2. Try it with no pad. This prints every report it would send:

   ```sh
   frostbite-daemon --dry-run
   ```

3. Plug in the pad and check it is seen (run from `host/`):

   ```sh
   uv run python -c "from frostbite_host.device import HidTransport; print(HidTransport.find())"
   ```

4. Start the daemon. OLED row 4 should change from `KBD` to `HID`.

   ```sh
   frostbite-daemon
   ```

5. Test it in a second terminal. Slot 3 should turn blue, then green, then clear:

   ```sh
   frostbite-ctl set 3 run "CI build"
   frostbite-ctl set 3 done "CI build"
   frostbite-ctl status
   frostbite-ctl clear 3
   ```

6. **All-LEDs check.** Lights all 13 together for the [LED data level](#led-data-level) test. Watch for flicker, then clear them:

   ```sh
   for n in 1 2 3 4 5 6; do frostbite-ctl set $n run "test $n"; done
   for n in 1 2 3 4 5 6; do frostbite-ctl clear $n; done
   ```

### Claude Code hooks: BY HAND

1. Print a snippet with the right path already in it:

   ```sh
   frostbite-ctl hooks --hook "$(which frostbite-hook)"
   ```

2. Open `~/.claude/settings.json` yourself.
3. Merge the snippet into the `"hooks"` object. Keep any hooks you already have.
4. Save, and start a new Claude Code session.

Leaving out a hook your Claude Code version does not know is harmless.

### How Approve works

Approve sends **no keystroke**. It answers Claude Code's `PermissionRequest` hook directly, so it needs no macOS permission and
works in every terminal, including VS Code and SSH.

1. Claude asks for permission. The slot goes amber, and the OLED shows the tool and its input. Long commands page every 2 s.
2. **Tap Approve** to allow that one request. **Hold Approve** to deny it.
3. Each press answers one call. No rule or mode is saved.
4. If you do nothing, the hook gives up after 30 s and the normal terminal prompt handles it.

Questions, plan approval and MCP dialogs are shown but never answered from the pad, since the answer is the content. A slot with no
waiting hook shows `answer in terminal`, however amber it is.

### How Stop works

Stop is the one real keystroke, and it needs macOS permission. With the daemon running, it sends Escape only when the selected
slot is a Claude session in `run`, in Terminal or iTerm2, with that app in front and that tab focused. VS Code, Ghostty, WezTerm,
Cursor, the desktop app, SSH and tmux can never be proved, so they show `answer in terminal`.

**With no daemon, Stop is a plain Escape to whatever app is in front.** The same is true for a couple of seconds after the Mac wakes.

### macOS permissions: BY HAND

macOS asks the first time Stop needs them. These are for Stop only. In **System Settings → Privacy & Security**, allow:

| Permission | Allow for |
|---|---|
| **Accessibility** | The program running the daemon |
| **Automation → System Events** | The same program |
| **Automation → Terminal** | The same program |
| **Automation → iTerm2** | The same program |

The program is your terminal if you started the daemon by hand. If launchd started it, it is the tool's Python, and
`head -1 ~/.local/bin/frostbite-daemon` shows its path. Without Automation the tty cannot be read, so Stop is refused.

### Start at login: BY HAND, optional

1. Replace `YOUR_USER` in `host/examples/com.frostbite.daemon.plist`.
2. Copy it to `~/Library/LaunchAgents/`.
3. Load it:

   ```sh
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.frostbite.daemon.plist
   tail -f ~/Library/Logs/frostbite-daemon.log
   ```

To stop it: `launchctl bootout gui/$(id -u)/com.frostbite.daemon`

### Talk key: BY HAND, optional

Talk sends F20 for as long as you hold it. Bind your dictation tool to it:

- **Wispr Flow:** Settings → Shortcuts → push-to-talk shortcut, click the field, press Talk.
- **macOS Dictation:** System Settings → Keyboard → Dictation → Shortcut → Customize, press Talk.

**Source:** `host/README.md`, `docs/audit/round2-software.md`.

## 16. Resolved, and what is still open

Settled from the source of truth, in this order: `PCB/frostbite.kicad_pcb`, `keyboard.json` and `keymap.c`,
`CAD/frostbite_case.py` and `production/`, `design.json`, then the READMEs.

### Resolved

| # | Old claim | Truth | Evidence |
|---:|---|---|---|
| 1 | A wrong-way glow LED still gets power, and two DOUT pins fight | Neither VDD nor GND reaches its own pad | `.kicad_pcb`: LED10 pads form a 5.55 × 1.5 rectangle |
| 2 | Fit glow LEDs before key LEDs | Key LEDs first | `.kicad_pcb`: LED10 DIN is `LED_D9`, from LED9 |
| 3 | Key LEDs are top-side parts | All 13 are on the underside | `.kicad_pcb`: every LED pad is B.Cu |
| 4 | Solder the OLED first, or last from underneath in the Top | On the bench, on J1, plastic off, before the PCB meets the Top | `frostbite_case.py` `make_oled_support`; `design.json` `case.oled_support` |
| 5 | Solder switches first, then clip them in | Clip in first | `frostbite_case.py`: 14.0 cutout against 15.6 flange, and the plate closes the Top |
| 6 | Flash firmware before the OLED is on | Keep `led-test` until OLED, knob and keys pass | `ledtest/keymap.c` shows `key:` and `knob:` |
| 7 | Test the whole chain at full white | No build does that. The hardest data case is LED1 alone on the highest port | `ledtest/keymap.c` `TEST_LEVEL`; `keymap.c` `POWER_BUDGET` |
| 8 | Fit a 1N4148 on LED1's VDD | No footprint, so it means cutting a trace | `.kicad_pcb`: only D1 to D9 |
| 9 | G10 uses an I²C scan, `KEY_LOG` and a host `ping` | None exist. Use the `led-test` rows and `HidTransport.find()` | `ledtest/keymap.c`; `ctl.py` subcommands |
| 10 | Swapping encoder pins is free | It is the right fix, but two checks fail | `check_netlist.py`; `verify/fbverify/checks.py` |
| 11 | Feet need no BOM entry | 4 feet needed | `frostbite_case.py` has no feet. Added to `docs/BOM.md` |
| 12 | The kit header is assumed | J1 needs one, and no kit list names it | `.kicad_pcb` J1 through-hole pins; `docs/BOM.md` |
| 13 | USB-C is flush with the back edge | The XIAO board is flush, and the connector overhangs | `.kicad_pcb` U1; `design.json` `mcu` |
| 14 | The case prints once, with no test prints | Coupons first, then the case once | `docs/coupons/`, generated from the real case |
| 15 | Glow runs at 27 % | 27 % with no daemon. 50, 110 or 160 of 255 with it | `keymap.c` `GLOW_DEFAULT_BRI`; `state.py` `glow()` |
| 16 | Pad gap under a glow LED is 0.82 | About 1.76. The 0.82 comes from a 1.78 placeholder | `frostbite_case.py` `PAD_TOP`, `LED_T`; lens at 0.84 |
| 17 | `VERIFICATION.md` old pin map and PCB mounting holes | Use `design.json`. There are no mounting holes | `.kicad_pcb`: none; `design.json` `pins` |
| 18 | Frosted caps can be DSA or XDA | DSA | `frostbite_case.py` cap model; kit caps are DSA |
| 19 | Bootmagic needs one key | Approve and Stop together | `frostbite.c` `bootmagic_should_reset` |
| 20 | Insert iron 230 °C or 245 °C | Start at 230 °C and let coupon 2 decide | No design source sets this, so a test does |
| 21 | Trim tails once, before the switches | Trim after Stages I, J and K | `frostbite_case.py` `THT_TAIL` 2.0 |

Found while settling these:

| Old claim | Truth | Evidence |
|---|---|---|
| Blocks 11 mm tall hold the upside-down Top | At least 22 mm. The encoder shaft stands 19.5 to 21.5 mm proud | `frostbite_case.py` `EC_SHAFT_TIP` |
| The OLED leads into the Top | The encoder shaft leads, and the glass is last | `frostbite_case.py` heights |
| Coupon 2 takes one insert per hole | Only 2 spares exist. Use Ø4.7 first | `docs/BOM.md` kit table |
| Coupon 4 runs on `led-test` | `led-test` never shows the glow colour. Use `firmware.uf2` | `ledtest/keymap.c` |

### Needs a real part

| Item | Where |
|---|---|
| Kit OLED size, ribbon, header, strip removal, tape, staying square | Sections 3, 11, Stage J |
| OLED flip, EC11 resolution and direction | Section 11 |
| LED data level, and LED body fit in the cut-out | Sections 3, 11 |
| Glow brightness | Section 11 |
| Print fit: switches, inserts, pocket, knob | Section 5 |
| Wrong-way LED table, from geometry only | Stage F |
| Pressing the glass: the support is geometry only, and the force path is untested | Stage J |
| Approve and Stop in a real Claude Code session with a real pad | Section 15 |

The exact USB overhang (1.0 or 1.42 mm) is also unmeasured, but the case fits both, so nothing depends on it.

### Open decisions

1. **Fallback Stop.** It is a plain Escape to the front app when no daemon runs. Keep it, or move it to an unassigned key, which
   is a one-line change in `keymap.c` and `design.json`.
2. **Encoder direction checks.** If the kit encoder runs backwards, decide how `check_netlist.py` and `verify` should accept the swap.
3. **Printing.** Ask whether Printing Legion will run the coupons and can supply iced and clear PETG.
4. **If LED1 fails on data level.** The only fallback cuts a trace, so a board respin with a diode footprint may be better.

### Docs still to correct

These files were outside this round's edit list:

- `docs/coupons/README.md`: old assembly step numbers, CAD line numbers, one insert per hole, and `led-test` for the glow check.
- `BOM.csv`: OLEDSupport, tape, feet.
- `verify/fbverify/main.py`, which writes the "full white" line in `verify/REPORT.md`.

## 17. External sources

| Source | Used for |
|---|---|
| [Adafruit Guide to Excellent Soldering](https://learn.adafruit.com/adafruit-guide-excellent-soldering) | Iron temperature, solder type |
| [SK6812 MINI-E datasheet Rev 02](https://cdn-shop.adafruit.com/product-files/4960/4960_SK6812MINI-E_REV02_EN.pdf) | Pin map (p.4), heat test (p.12), handling (p.17), static and eye warnings (p.18) |
| [CNC Kitchen: heat-set insert tips](https://cnckitchen.com/blog/tips-and-tricks-for-heat-set-inserts) | Insert temperature and method |
| [Seeed XIAO RP2040 wiki](https://wiki.seeedstudio.com/XIAO-RP2040/) | Bootloader entry |
| [QMK docs](https://docs.qmk.fm/newbs) | Setting up the build tools |

When your pad works, take a photo. Stardance's build stage asks for a demo video, physical build devlogs and a photo in the
README (`docs/audit/hackpad-rules.md`).
