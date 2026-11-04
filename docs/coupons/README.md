# Frostbite test coupons

Small prints that check your printer and the risky fits before you spend hours on the full case. They come from the real case source, and `make_coupons.py` stops if a coupon differs from the real part in the region they share.

Mass and time below are **estimates** from a simple flow model (`check_coupons.py`), not a slicer. They exclude heat-up. Check them in your slicer.

| Print | File | Material | Size (mm) | Est. mass | Est. time |
|---|---|---|---|---|---|
| 1 Plate | `coupon1_plate` | iced PETG (same as the Top) | 57.2 × 52.1 × 3.1 | 5.5 g | 21 min |
| 2 Inserts | `coupon2_inserts` | iced PETG | 28.7 × 39.0 × 16.0 | 6.6 g | 28 min |
| 3 Pocket + USB | `coupon3_pocket_usb` | iced PETG | 50.4 × 36.4 × 7.6 | 6.1 g | 24 min |
| 4 Glow band | `coupon4_glow_band` | clear/natural PETG | 17.0 × 43.0 × 8.8 | 2.3 g | 10 min |
| 4 Glow cap | `coupon4_glow_cap` | iced or any opaque PETG | 19.0 × 21.0 × 3.6 | 0.9 g | 4 min |

Each has a `.stl` and a `.step`, already in print orientation. Previews are in `previews/`.

## Print settings

Use the settings you plan to use for the case, or the result tells you nothing about it. **No supports on any coupon.**

PETG, 0.4 mm nozzle, 240 °C, bed 80 °C, 4 perimeters, 25 % gyroid. Keep hole or XY compensation off for the first run.

| Print | Orientation (as exported) | Layer | Notes |
|---|---|---|---|
| 1 Plate | plate top face down on textured PEI, labels up | 0.2 (or 0.16 if you will print the Top at 0.16) | Same way up as the real Top, so first-layer squish affects the cutouts the same way |
| 2 Inserts | plate end on the bed, hole mouths up | 0.2 | Holes open upward, as they do in the Top. The spacer ring prints beside the bar |
| 3 Pocket + USB | plate top face down, walls up | 0.2 | The USB block stands on the bed with its window axis vertical |
| 4 Glow band | flat, ring on the bed | 0.2 | **100 % infill** (or 6 perimeters), as for the real GlowBand |
| 4 Glow cap | flat, feet up | 0.2 | Any opaque or iced PETG |

## Measure the print first

On coupon 1, measure centre to centre across the three columns (use cutout edges on the same side). The design value is **38.10**.

- Scale error = (your reading − 38.10) / 38.10.
- Edge shift at the PCB = scale error × 30.6 mm. This is what the pocket coupon cannot show (see coupon 3).
- A reading of 38.00 means −0.26 % and costs about 0.08 mm per side.
- If the error is over 0.3 %, correct the slicer's XY shrinkage compensation before anything else. Do not change the CAD for it.

## 1. Plate: which cutout clips well

Tests the 14.0 cutout, 1.5 mm plate at the clips, the 15.4 clip pocket and the real 19.05 pitch. It has four real cutouts plus one each at 13.9 and 14.1. Sizes are embossed next to each cutout.

Push a real Gateron KS-3 in from the flat (bed) side, the same way as assembly step 8. It should press in with a firm click, stay put when you turn the plate over, and not rock. Then try a keycap on two neighbouring switches: they should not touch.

| Result | Meaning | Change |
|---|---|---|
| 14.0 clips firmly | Correct as designed | Nothing |
| 14.0 needs hard force or the plate bulges, 14.1 is good | Holes print about 0.1 small, as expected on FDM | First choice: slicer hole/XY compensation of 0.05 (as `CAD/README.md` says), no CAD change. If you prefer CAD: `CUTOUT = 14.1` in `CAD/frostbite_case.py`, line 54 |
| 14.0 is loose or the switch rocks, 13.9 is good | Holes print large | Do **not** change the CAD: a 13.9 cutout overlaps the 14.0 housing in the model and four fit checks fail. Reduce slicer hole compensation or flow until the 14.0 fits, then reprint coupon 1 |
| Clips do not catch on any size | Plate is thicker than 1.5 at the clips, or the clip pocket is too small | Measure the thin section. If it is over 1.6, fix first-layer squish. Otherwise raise `CLIP_POCKET` in `CAD/frostbite_case.py`, line 55 |

`CUTOUT = 14.1` builds a sound case, and only one `CAD/check_fit.py` row fails: "Switch cutouts 14.0 +/-0.1" (tested in a scratch copy). 14.1 sits exactly on that limit. To keep the checks green, widen the 0.1 to 0.15 at `CAD/check_fit.py` line 153 and set `CUTOUT_TOL = 0.15` in `verify/fbverify/checks.py` line 32. Leave `SWITCH_W` alone: it is the switch, not the hole. The `verify` edit comes from reading the source and was not run.

## 2. Inserts: which hole holds an insert

Tests the real insert hole in a real length of side wall, from the Top: 8.7 mm wide, 16 mm tall, Ø3.4 blind continuation, 3.2 mm skin at the end. The holes are Ø4.5, Ø4.7 (real) and Ø4.9, labelled on the flange. The bar stays 8.7 wide, as it would if you changed only the hole, so the walls are 2.1 / 2.0 / 1.9. That is the only part of this coupon that varies.

Heat-set one kit insert in each hole, iron about 230 °C, flush with the rim. Let it cool. Then pass an M3×16 through the spacer ring into the insert and tighten until snug. The ring stands in for the GlowBand and Bottom (3.6 mm), so the screw reaches its real depth.

| Result | Meaning | Change |
|---|---|---|
| Ø4.7 goes in straight, stays put when tightened, no bulge | Correct as designed | Nothing |
| Ø4.7 spins or pulls out, Ø4.5 holds | Hole prints large or the insert is on the small side | `INSERT_HOLE, INSERT_DEPTH = 4.5, 4.0` in `CAD/frostbite_case.py`, line 64 |
| Ø4.7 needs heavy force, bulges or cracks the wall, Ø4.9 is good | Hole prints small | `INSERT_HOLE, INSERT_DEPTH = 4.9, 4.0`, same line. Wall drops to 1.9, still above the 1.3 minimum |
| All three are bad, or the wall bulges on all | Wrong insert, too much heat, or under-extrusion | Check the kit insert (OD 5, L 4), lower the iron or press more slowly, reprint |
| Plastic pushes up into the screw hole | Molten plastic pooled below the insert | Press more slowly and clear the hole with an M3 screw while warm. No CAD change |

Changing `INSERT_HOLE` builds and passes every other fit check, but two hard-coded 4.7 values then fail (tested for `check_fit.py`, read from source for `verify`): update `CAD/check_fit.py` line 192 and `INSERT_HOLE` in `verify/fbverify/checks.py` line 47. Also update the `case.inserts` text in `design.json` (`hole 4.7`) and the `boss_od` note, and the `heatSetInsert.holeDiameter` row in `docs/DIMENSIONS.md`, so the docs stay true. `boss_od` itself can stay 8.7.

## 3. Pocket and USB: how the real PCB fits

### Pocket corner

This is the front-left corner of the Top around SW7, with the real plate and a real 14.0 cutout at its real distance from the walls. Both arms step through 0.3 (the real value, at the corner), 0.2 and 0.4 mm from the PCB edge. The values are labelled on the flange.

The switch is what makes this work. An L corner has no opposite wall, so a loose board just slides into the corner and proves nothing. In the real case the PCB is held by the switches, so the switch sets its position here too.

1. Clip one real switch into the cutout, from the flat side.
2. Lower the bare PCB onto the switch pins from the wall side, straight down, as in assembly step 9. Line up its front-left corner with the coupon's corner. Do not solder anything.
3. Press until the switch housing touches the PCB. Printer paper is about 0.1 mm thick, so use strips of it as a feeler gauge at each step on both arms.

| Result | Meaning | Change |
|---|---|---|
| Board seats. 1 sheet fits at 0.2, 2 at 0.3, 3 or more at 0.4 | Printed as intended | Keep `"tolerance": 0.3` in `design.json` (`case.tolerance`) |
| Board seats, but 0.2 pinches and 0.3 is free | 0.3 is the right call | Keep 0.3 |
| The 0.2 step stops the board, 0.3 is free | Walls are printing in by more than 0.2. 0.3 still works, but with little margin | Keep 0.3, and apply the scale error from "Measure the print first" |
| The 0.2 and 0.3 steps both stop the board, 0.4 is free | The real 0.3 is too tight on your printer | In `design.json` set `"tolerance": 0.4` **and** `"boss_od": 8.5` (`case.screws`). Tested: 0.4 alone fails "Boss OD clear of the PCB insertion envelope", and both together pass `check_fit.py`. The insert wall drops to 1.9 on the pocket side |
| All steps have a big gap (over 0.2 more than labelled) | Walls print outward, or the cutout is off | Check flow. A loose fit is harmless to the PCB, so 0.2 is possible: `"tolerance": 0.2` passes `check_fit.py` (tested) |
| One arm reads differently from the other | X and Y are not the same on your printer | Fix belts or scale before the full print. Do not change the CAD |

`case.tolerance` also moves the OLED window and recess and the GlowBand riser gaps, so rerun both `CAD/frostbite_case.py` and `CAD/check_fit.py` after changing it. The 0.2 and 0.4 builds were run in a scratch copy with `check_fit.py` only, not the whole `verify` suite. `verify` X.pcb_insertion reads the tolerance from `design.json`, so it should follow, but that was not run.

What this cannot show:

- **Shrinkage over the full board.** It only covers 26 mm near one switch. A pocket 62 mm wide can lose more than this corner shows. Use the 38.10 measurement above and subtract the edge shift from your best gap.
- **The switch pattern.** One switch cannot show whether nine switches and the PCB holes line up. The pitch reading on coupon 1 is the check for that.
- **The real wall's stiffness.** The wall is 3 mm thick here (7 to 9 in the real Top), so it can flex a little more and it cools differently. Only its inner faces are real.

The board has 1 mm rounded corners and the pocket's are sharp, so a rounded printed corner is unlikely to touch the board.

### USB-C opening

A copy of the real window: 13.5 × 8.0 through 6.7 mm, the depth of the back wall from the skin to the pocket.

Push your real cable through, from the top of the block (the bed side has first-layer squish). The moulded boot should enter freely for at least 6 mm. The skin to receptacle mouth distance is 5.6 on the case model and about 6.0 by Seeed's STEP, which disagrees with its footprint.

| Result | Meaning | Change |
|---|---|---|
| Boot passes with a visible gap | Correct | Nothing |
| Boot is tight, or stops before 6 mm | That cable is too large, or the opening prints small | Try another cable first. To widen: `case.usb_cutout.w` or `.h` in `design.json`. `.h` is limited by the stack, so rerun `check_fit.py` and read its USB rows |

It cannot show alignment with the real receptacle, because that needs the XIAO in the assembled stack. The real window also differs in how it is printed: the Top makes it as an open notch with the GlowBand tongue closing the bottom. This copy is a closed window with its axis vertical, which avoids a 13.5 mm bridge. Its size tests your cable, not the exact edges of the real notch.

## 4. Glow: how light spreads in clear PETG

The band is a true slice of the real GlowBand (PCB y 14 to 57, back-left LED 9), 43 mm long, with the real ring, riser and pad. The cap stands in for the PCB. Its feet rest on the riser and hold the LED window over the real LED spot, 1.76 mm above the pad.

That 1.76 is deliberate. `docs/audit/pcb-physical.md` found that the real LED hangs about 0.84 below the PCB, not 1.78 as the CAD placeholder does, so the real gap is about 1.76, not the 0.82 in `CAD/README.md`.

Cover the two cut end faces of the band with black tape, or they will glow brightly and mislead you. Then tape the cap on and use one of these:

- **One SK6812 MINI-E.** Drop it in the window, emitter toward the pad, and tape the back. It needs 5 V and a data signal, so a loose LED will not light by itself. The easiest route is a real glow LED on the real PCB running `led-test`: hold the band under it at the real position, with no cap. The firmware default is `#7fe3ff` at brightness 70 of 255 (about 27 %), so judge it there, not at full white.
- **A phone torch.** Press the cap's back against the torch, so the window acts as a small source. This only shows the **shape** of the spread.

Look at the 2 mm outer face (the narrow ring face) in a normally lit room, then a dim one.

| Result | Meaning | Change |
|---|---|---|
| Visible along the whole 31 mm run from the LED, even with a hot spot at the pad | Good sign for the band | Print the full band |
| Bright near the pad, gone within about 15 mm | Expect dark stretches, because the front, side and back centres are 27, 30 and 41 mm from the nearest LED | Try 6 perimeters or slower, hotter printing for clarity. Then the steps in `CAD/README.md`: foil or white paint on the skirt's inner wall, then moving light sources at PCB level |
| Cloudy, with visible layer lines and little carry | Print clarity is the limit | Raise temperature, slow down, 100 % infill, thicker layers. No CAD change |

Geometry values if you do change it: `PAD_REACH` (line 118), `RISER_T` (line 119) and `RING_RELIEF`, `RING_LAND` (line 120) in `CAD/frostbite_case.py`. LED positions are `leds.glow` in `design.json`, which is a PCB change.

**What this coupon cannot show:**

- **It cannot tell you the final brightness.** It can show how far light carries, not how bright the finished case will look. The audit's concern (M2) stays open until a real LED is seen at firmware brightness in the assembled case.
- **A phone torch proves nothing about brightness.** It is far brighter than an SK6812 at 27 %, is white and not ice blue, and your eyes and camera adapt to it. A good torch result does not mean the LED will look good.
- **The skirt and Bottom are missing.** In the real case, frosted PETG touches the ring and takes a share of the light, and that light is lost. There is no skirt here, so the coupon will look better than the case.
- **Four LEDs are not modelled.** Only one LED, one pad and one straight side are here. The corners, the back edge where the riser steps down under the XIAO, and the front pads are absent. The 41 mm point at back centre is out of reach: this slice only goes 31.6 mm from the LED.
- **The PCB's surface is missing.** The cap is not solder mask, so reflection from the board differs.
- **Photos mislead.** Phone cameras raise exposure on dim scenes. Use manual exposure if you want to compare photos, and trust your eye in a lit room.
- **It will not match a different filament.** Clear PETG varies a lot by brand and print settings, so use the spool you will print the band with.

## Regenerate and check

```sh
CAD/.venv/bin/python docs/coupons/make_coupons.py       # STEP, STL, previews (about 10 s)
verify/.venv/bin/python docs/coupons/check_coupons.py   # exit 1 on any failure
```

`make_coupons.py` imports `CAD/frostbite_case.py`, so case changes carry through. The trial sizes (13.9 / 14.1, Ø4.5 / Ø4.9, 0.2 / 0.3 / 0.4) are fixed test values, so after changing a real value the same-as-real check stops the script until you update the trials to include it (`STEPS`, `INSERT_TRIALS`, or `sizes` in `plate()`). The script writes nothing in `CAD/`.

`check_coupons.py` holds the intended numbers on its own, so after a case change it will report the differences until you update them.

Current result: **55 of 55 pass.** Every part is watertight. Sizes, cutouts, pitch, holes, walls, step offsets and the USB window were measured from the STLs. No face is past 45° of overhang and there are no bridges (the rules from `CAD/check_fit.py`). The thinnest wall is 1.5 mm, labels excluded, and all 51 label glyphs have strokes of at least 0.4 mm.

These checks confirm the files, not the printed parts. Nothing here has been printed.

The same-as-real check in `make_coupons.py` found no difference from the real Top in the 2 × 2 plate, the Ø4.7 wall section and the 0.3 pocket corner. The band matches `production/GlowBand.stl` in all six compared sections.
