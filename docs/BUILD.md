# Building Frostbite

This guide takes you from a bag of parts to a working Frostbite 9. It assumes you have never soldered. It follows the [Hackpad assembly](https://hackpad.hackclub.com/assembly) order: diodes, other components, switches into the plate, electrical test, then the case.

Work in order, because later parts block access to earlier ones. Stop at the first failed test and fix it before you go on.

## 1. Words used in this guide

| Word | Meaning |
|---|---|
| Top, Bottom | The printed case parts. The Top is the flat plate with the switch cutouts. The Bottom is the tray. |
| Top side | The PCB side the switches, diodes, encoder and OLED sit on. It says `XIAO ON BACK`. |
| Underside | The PCB side the XIAO solders to. It says `XIAO HERE`. |
| Back edge | The PCB edge with the USB-C connector. The front edge is nearest you when you use the pad. |
| Pad, joint | A pad is the bare metal patch you solder to. A joint is one solder connection. |
| Tail | The piece of a wire lead sticking out past a joint. |
| Short | Two things connected that should not be. |

**Left and right swap when you turn the board over**, so this guide always says which view it means. Keep the back edge away from you in both views. This is the underside view, with the XIAO pins as seen from there:

![PCB underside](../PCB/images/pcb_back.png)

| Left column | Net | | Right column | Net |
|---|---|---|---|---|
| D0 | ROW0 | | 5V | not connected |
| D1 | ROW1 | | GND | GND |
| D2 | ROW2 | | 3V3 | +3V3 |
| D3 | COL0 | | D10 | COL2 |
| D4 | SDA | | D9 | COL1 |
| D5 | SCL | | D8 | ENC_B |
| D6 | not connected | | D7 | ENC_A |

## 2. Tools

- A temperature-controlled soldering iron with a fine tip, plus a tip you can use for heat-set inserts.
- Thin rosin-core solder, flux, solder wick and a tip cleaner.
- Flush cutters, small pliers, fine tweezers and a needle file.
- A multimeter with continuity and diode modes, and calipers.
- A third hand or small vise that holds the PCB on edge.
- Two blocks at least 22 mm tall.
- A driver that fits the kit's M3 screws.
- A USB-C cable that carries data. A charge-only cable will not work.
- Safety glasses, because cut tails fly.

Set the iron to [370 °C for 60/40 solder or 400 °C for lead-free](https://learn.adafruit.com/adafruit-guide-excellent-soldering). Work with ventilation, wash your hands after handling leaded solder, and put the iron in its stand every time.

## 3. Parts check

Count everything against the [kit table in BOM.md](BOM.md#kit-usage) before you heat anything. Then check the real parts:

1. Switches have 2 metal pins, 2 side pegs and 1 centre post, all straight.
2. The encoder shaft has a D-flat. Inserts are OD 5, length 4.
3. Hold the OLED module display side up with the header end on your right. From back to front the pins must read `GND`, `VCC`, `SCL`, `SDA`, matching the silkscreen beside J1. Some clones swap GND and VCC, which would reverse-power the module. If yours differs, stop and do not solder it.
4. The OLED needs a 4-pin header, loose or fitted. A fitted header must have its long pins pointing away from the display. If there is no header, cut 4 pieces of lead from spare diodes and use those as pins.
5. On the PCB, find `XIAO HERE` on the underside and `GND VCC SCL SDA` beside J1.

## 4. Practice first

Solder spare diodes onto a spare PCB until your joints look smooth and shiny. The tracks are as thin as 0.2 mm, and a first-time solderer can lift one.

To fix a joint, add flux and reheat. Never press or lever a part. To remove a part, melt all its joints first and lift only when it moves freely. Never hold the iron on one pad for long. Stop, let it cool, and try again with more flux.

## 5. Test prints and OLED measurement

Do this before the full case prints. Ask your printer whether they can run the coupons first.

Coupons are small test pieces cut from the real case. Print them with the case's settings: PETG, 0.4 mm nozzle, [240 °C, bed 80 °C](../CAD/README.md#print-settings), 4 perimeters, 25 % gyroid, no supports, hole or XY compensation off for the first run. Print the OLEDSupport and the Knob at the same time.

[The coupon page](coupons/README.md) has each test and what to do with each result. You need three passes:

- Coupon 1: **38.10 mm** across the columns, within 0.3 %, and a switch that clips firmly into the 14.0 cutout.
- Coupon 2: an insert that holds in Ø4.7. You have only **2 spare inserts**, and the case needs the other 4.
- Coupon 3: a bare spare PCB that seats, and a USB cable boot that enters at least 6 mm.

### OLED ribbon clearance

Measure the kit OLED with calipers before the Top prints. Ribbon height is the thickness at the far end (away from the header), over the folded ribbon and tape, minus the board thickness at a plain edge. If you change `design.json`, rerun `CAD/frostbite_case.py` and `CAD/check_fit.py`, then print the new Top.

| Measure | Room in the design | If it does not fit |
|---|---|---|
| Ribbon height above the board | 1.0 mm | Widen `oled.window` in `design.json` through the far lip |
| Ribbon or tape past the far board end | 1.1 mm | The same |
| Joint height after trimming, header end | 1.0 mm | Trim again |
| Parts on the module's underside at the support feet: 1 to 7 mm from the far end, 3.1 to 8.3 mm from the header end | None | Move the feet in `CAD/frostbite_case.py`. A part on a foot lifts that end. |
| Glass thickness | 1.45 mm | Thinner only sinks the glass further |
| Module length | 38 mm | On a 36 mm module, shift the window |

## 6. Heat-set inserts

Do this when the Bottom arrives. The four holes are in the Bottom's corners and open at the rim. Start at [about 230 °C](../CAD/README.md#assembly-order). Coupon 2 shows whether your print needs more. [CNC Kitchen gives 245 °C for PETG](https://cnckitchen.com/blog/tips-and-tricks-for-heat-set-inserts). Go hotter only if the insert will not sink under light pressure.

1. Stand the Bottom on its underside with the rim up. Set one insert straight on a hole.
2. Put the hot tip into the insert and press lightly. Let the heat sink it. Do not push hard.
3. Melt it in about 90 % of the way, then finish with a flat tool.
4. Press it **flush with the rim** and hold it still for a moment. An insert that stands proud stops the Top from sitting flat.
5. Keep the iron off the rim and walls. The wall around each insert is only about 1.5 mm thick.
6. Repeat for all four. After cooling, run an M3 screw in by hand. It should go straight.

If plastic pushes down into the screw hole, press more slowly and clear the hole with an M3 screw while it is warm.

## 7. Soldering order

Checks A to F are in [section 8](#8-multimeter-checks).

### Stage A: bare board

Do check A on the PCB you will use.

### Stage B: XIAO on the underside

1. Turn the board underside up and find `XIAO HERE`.
2. Lay the XIAO flat on that outline with **its components facing you, away from the PCB**. On the top side the pinout would be mirrored and 5V would land on a signal pad.
3. Point USB-C at the back edge and line up the XIAO board edge with the PCB edge. The USB connector overhangs a little, which is correct. Check the 14 XIAO edge pads sit over the 14 PCB pads, 7 per side.
4. Tack one corner. Check the XIAO is flat and square, then tack the opposite corner.
5. Solder all 14 pins. Touch the iron to the exposed PCB pad at the XIAO's edge and feed solder. If a pin is hard to reach, heat the pad from the top side and feed solder down the plated hole. Keep top-side solder low, because the OLED module sits 1.8 mm above these pads. Leave no blobs under the XIAO.
6. Take extra care with GND, second from the USB end. It is the XIAO's only GND link, so a bad joint takes out the OLED and keys together.

### Stage C: first flash

Do check B, then [the first flash](#first-flash-on-a-blank-xiao). This proves USB and the XIAO before you add anything else. Unplug USB before the next stage.

### Stage D: diodes, band toward the front edge

The plate sits 2.5 mm above the PCB, so a raised diode would hit it.

1. Top side up, back edge away from you. Each diode sits to the right of its switch, and the square pad is marked `K`. Bend the leads to fit the holes, 7.62 mm apart.
2. Put the **black band on the `K` end**. On all nine diodes that is the end **nearest the front edge**. A backward diode means a dead key.
3. Press the diode flat. It must end up at most 2.2 mm tall. Splay the leads a little on the underside so it stays put.
4. Solder both leads from the underside.
5. Do D1 first and test it with check C. Then do the other eight and check each one.

### Stage E: encoder

1. Fit it from the **top side**, the same side as the diodes. Check this twice. Turn it so the three-pin row (A, C, B) faces the keys and the two-pin row faces the back edge.
2. Press straight down until the side lugs snap through their slots. Expect a firm press. If a barb will not pass, file it, because forcing it can damage the plated hole.
3. Check it sits flat and square.
4. Turn the board over. Solder the three pins, the two lugs and the two pins of the unused push switch, which add strength. The lugs and pin C go to GND and need a little longer to heat.
5. Try the Knob on the shaft while the PCB is on the bench. File the bore until the Knob presses on by hand, then take it off.

### Stage F: trim tails

On the underside, cut all through-hole tails to **2.0 mm or less**. Measure them, then do check D.

### Stage G: OLED on J1

The header's black plastic comes off and the printed OLEDSupport sets the height. With the plastic on, the glass would stand proud of the plate.

1. Compare the module's labels with the silkscreen beside J1 once more.
2. If the header is loose, put its short pins up through the module from underneath, with the black plastic on the underside. Solder the four pins and trim them **flush on the display side**.
3. **Slide the black plastic strip off the pins**, toward their free ends, with small pliers. Work from both ends and go gently. The pins stay soldered to the module, so do not pull on the joints.
4. Lay the OLEDSupport on the top side of the PCB. The small foot goes by J1, the large foot goes at the far end, and the rail goes on the side facing the keys.
5. Put the pins through J1, display up, and lower the module until it rests on both feet.
6. **Square the module.** Measure from the PCB's back edge to the module's long edge at both ends. Both should read **7.0 mm** and agree within 0.5 mm.
7. Hold the PCB on edge in the third hand with the underside toward you. Press the module gently toward the PCB with one finger and solder one end pin.
8. Check the module still sits on the support and still reads 7.0 mm. If it moved, reheat that pin and correct it.
9. Solder the other 3 pins and trim them to **2.0 mm or less**. The support is now held in place.
10. Do check E, then the [OLED and dial test](#oled-and-dial-test).


### Stage H: switches

The switch flange is wider than the plate cutout, so switches clip in from the top face and get soldered to the PCB afterwards. The PCB ends up hanging from the 9 switches, which is correct.

1. Clip all 9 switches into the plate **from the top face** until the clips seat. Check every pin is straight.
2. Turn the Top upside down on **two blocks at least 22 mm tall**, under the plate margin. The encoder shaft will stand 19.5 mm proud of the plate, or 21.5 mm on a generic EC11. Shorter blocks stop the PCB from seating.
3. Hold the PCB with its underside facing you and lower it straight down. The encoder shaft enters its opening first, about 22 mm before the PCB seats. The switch pins meet their holes at 3.3 mm and the OLED meets its recess at 2 mm.
4. Do not force it. If it stops, lift it out and look for a bent pin.
5. Solder the 18 switch joints from the underside, 2 per switch.
6. Trim the switch tails to **2.0 mm or less**.

### Stage I: electrical test

Leave the Top upside down on the blocks, so BOOT and RESET stay reachable.

1. Do check F.
2. Run the [key test](#key-test).
3. Flash [`firmware.uf2`](#10-flashing-firmwareuf2).

## 8. Multimeter checks

**Keep USB unplugged for every continuity check.** A steady tone means two points are connected. A short chirp that fades can be a capacitor charging. With parts fitted a meter may show a resistance value, which is fine unless it is near zero. If a "silent" pair gives a steady tone, **do not plug in**. Look for a solder bridge, starting with the last part you fitted, clean it with wick, and test again.

| Check | When | Must stay silent | Must give a tone |
|---|---|---|---|
| A | Bare board | 3V3 to GND, D0 to D1, D1 to D2, D3 to D9, D9 to D10 | |
| B | After the XIAO | **5V to GND**, **3V3 to GND**, 5V to 3V3, each XIAO pin to the next pin down in both columns | XIAO GND to J1 pin 1, XIAO 3V3 to J1 pin 2 |
| C | After each diode | See below | See below |
| D | After the encoder and tails | ENC1 pin A to GND, ENC1 pin B to GND, D0 to D10 each to GND | ENC1 pin C to GND |
| E | After the OLED | **5V to GND**, **3V3 to GND**, SDA to SCL (D4 to D5) | |
| F | After the switches | **5V to GND**, **3V3 to GND** | See below |

- Check B: a silent XIAO GND to J1 pin 1 means the XIAO's GND joint is bad.
- Check C: use diode mode. Red on the anode end and black on the `K` end should give a reading, and swapped should give none. If it reads the wrong way round, the diode is backwards, so fix it now. Then repeat the row and column checks from check A.
- Check F: use diode mode with red on a column pin and black on a row pin. Each key should connect its column to its row only while it is held down.

## 9. Flashing bringup.uf2

`production/bringup.uf2` checks each key, the dial direction and the OLED. Keep it on the XIAO until every test here has passed. BOOT and RESET (B and R) are on the XIAO's component side, so you can reach them until the case closes.

### First flash on a blank XIAO

**Use the BOOT button.** The double-tap and Approve + Stop are part of the Frostbite firmware, so they do nothing until it is on the XIAO.

1. Unplug the XIAO. Press and hold **BOOT**, plug the USB-C cable into the laptop, then let go.
2. A drive named **RPI-RP2** appears. Drag `production/bringup.uf2` onto it. The board reboots by itself and the drive goes away.
3. Measure with DC volts. 5V to GND should read about 5 V and 3V3 to GND about 3.3 V.
4. Check the laptop sees it, from the repo root. A non-empty list means the XIAO is running Frostbite firmware.

```sh
cd host && uv run python -c "from frostbite_host.device import HidTransport; print(HidTransport.find())"
```

| Result | Meaning | Next |
|---|---|---|
| RPI-RP2 appears, flash works, the check lists a device | USB, XIAO and power are good | Go to Stage D |
| RPI-RP2 does not appear | Charge-only cable, or BOOT released too early | Try a data cable, and hold BOOT longer |
| Laptop reports a USB problem, or the XIAO gets hot | Possible short | Unplug at once. Redo check B. |
| RPI-RP2 appears, but no device afterwards | Drag failed, or the file is wrong | Flash again and check the file name |

### OLED and dial test

Plug in. For the first 3 s every OLED pixel is on, so look for dead pixels or lines. Then the screen shows this:

```
BRINGUP  keys 0/9
seen .........
key: -
knob: turn it
```

Read it with the back edge away from you.

1. **OLED orientation.** All four rows must be readable and the right way up. If the text is upside down, comment out `#define FROSTBITE_OLED_FLIP` in `Firmware/qmk/keyboards/frostbite/config.h` and [rebuild](../Firmware/README.md#build).
2. **Dial direction.** Turn the shaft clockwise. `knob:` must read `CW` and the count must go up. If it reads `CCW`, swap `pin_a` and `pin_b` in `keyboard.json` and do not resolder. Then follow [the bring-up notes](../Firmware/README.md#bring-up) to update the two checks that read those pins.
3. **Dial steps.** Turn one click. The count should move by 1. If it moves by 2, double `encoder.rotary[0].resolution` in `keyboard.json`. If two clicks move it by 1, set the value to 2.

### Key test

Press each key once. The count must reach `9/9` and `seen` must read `123456789`. A dot means that key has not been seen. The `key:` row names the last key and its matrix row and column. Agent 1 to 3 is `r0`, Agent 4 to 6 is `r1`, and Approve, Talk, Stop is `r2`, with `c0`, `c1`, `c2` from left to right in top view.

Keys send their fallback codes during this test, so Stop sends Escape to the laptop. The dial leaves the volume alone.

## 10. Flashing firmware.uf2

Do this after the OLED, dial and key tests pass, **with the case still open**.

1. Enter the bootloader. Double-tap **RESET**, or hold **BOOT** while plugging in, or hold **Approve + Stop** (bottom-left and bottom-right keys) while plugging in. The last one also clears EEPROM.
2. Drag `production/firmware.uf2` onto **RPI-RP2**. The board reboots by itself.

With no laptop app running, the OLED reads `FROSTBITE   no host`, and row 4 shows the slot strip ending in `KBD`. Keys send F13 to F20 and Escape, and the dial changes volume. Press every key and turn the dial while you can still reach BOOT. On macOS, F14 and F15 may change screen brightness.

## 11. Final assembly

Do not start until sections 9 and 10 pass. After this, BOOT and RESET mean removing 4 screws.

![Frostbite case, exploded view](images/exploded.png)

1. Measure the tails one last time. All must be 2.0 mm or less.
2. Stand the Bottom on the bench with the rim up. Lift the Top with the PCB hanging from it and lower both straight into the Bottom. The USB receptacle drops into the notch and the tongue follows it. The Top must sit flat on the rim.
3. Drive the 4 kit M3 × 16 screws **from the plate top** into the inserts. A longer screw will not fit.
4. Turn each one a little at a time, in a cross pattern, and stop as soon as it is **snug**. Use a small hand driver. PETG creeps, so do not over-tighten.
5. Press on the 9 white keycaps, straight down.
6. Press on the Knob with the D-flat lined up. Use light force, because the load goes into the PCB.
7. Plug in USB-C and check the plug seats fully. Press every key and turn the dial.

Snug means the head has seated and the parts have closed up. An insert that spins, or a screw that suddenly gets loose, means stop. A screw that binds early is usually off its thread, so back it out and start it straight.

To reach BOOT and RESET later, remove the 4 screws and lift the Top and PCB out. To take the PCB off the Top, release the 9 switches from the plate with a switch puller, or desolder 18 joints.

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Approve + Stop does nothing | Firmware not on it, or keys or matrix not working | Use BOOT. Remove the 4 screws if closed. |
| OLED blank | J1 joint, or VCC and GND order | Check SDA, SCL, VCC, GND. Compare labels with J1. |
| Glass catches on the window | Module not square | Check the 7.0 mm at both ends. |
| Glass stands proud of the plate | Plastic left on, or a part under a foot | Check both |
| One key dead | Bad switch joint, or diode backwards | Reflow. Do check C on that diode. |
| A row or column dead | XIAO pin joint on that row or column | Reflow that XIAO pin. Check its neighbour. |
| Pressing one key shows two | Bridge between row or column pins | Redo the neighbour checks |
| PCB will not seat in the Top | Bent switch pin, or blocks under 22 mm | Lift out and check both |
| Top will not sit flat on the Bottom | Insert standing proud, or something in the USB notch | Lift out and check |
| USB plug will not seat | Plug overmold too big | Coupon 3. Cables up to about 13.4 × 7.9 mm should work. |
| Pad falls back to `KBD` | No PING for 5 s | Check the daemon runs |
| OLED went dark | 10-minute burn-in protection | Press a key or turn the knob |
| Approve does nothing, or OLED says `answer in terminal` | No hook is waiting on that slot, or the pad cannot act on this one | Answer in the terminal |
| OLED says `tap slot first` | Another tab or app is in front when you press Stop | Tap the agent key, then press Stop |

## 13. Laptop companion

The pad works as a plain keyboard with nothing installed. The companion adds agent status, Approve and Stop. Nothing here installs itself or edits your settings. [`host/README.md`](../host/README.md) is the full reference.

From the repo root, with `uv` installed and the pad plugged in:

```sh
uv tool install ./host
frostbite-daemon --dry-run      # no pad needed: prints every report it would send
frostbite-daemon                # OLED row 4 should change from KBD to HID
```

Test it in a second terminal. The OLED should show slot 3 as `RUN`, then `DONE`, then clear.

```sh
frostbite-ctl set 3 run "CI build"; frostbite-ctl set 3 done "CI build"
frostbite-ctl status; frostbite-ctl clear 3
```

Run `frostbite-ctl hooks --hook "$(which frostbite-hook)"` to print the Claude Code hooks snippet, and merge it into `~/.claude/settings.json` yourself. Tap Approve to allow the request on the OLED, or hold Approve to deny it.

**With no daemon running, Stop is a plain Escape to whatever app is in front.** The same is true for a couple of seconds after the Mac wakes. With the daemon running, macOS asks for Accessibility and Automation the first time Stop needs them, as [the host guide](../host/README.md#stop) explains.

Talk sends F20 while held, so bind your dictation tool to it.

When your pad works, take a photo. Stardance's build stage asks for a demo video, physical build devlogs and a photo in the README.
