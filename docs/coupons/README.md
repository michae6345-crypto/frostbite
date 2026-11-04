# Frostbite test coupons

Small prints that check your printer and the risky fits before you spend hours on the full case. Nothing here has been printed. `make_coupons.py` cuts them from the real case source and stops if a coupon differs from the real part in the region they share. Each has a `.stl` and a `.step`, already in print orientation, with previews in `previews/`. Mass and time are estimates from a simple flow model (`check_coupons.py`) and exclude heat-up.

| Print | File | Material | Size (mm) | Est. mass | Est. time | As exported |
|---|---|---|---|---|---|---|
| 1 Plate | `coupon1_plate` | black PETG | 57.2 × 52.1 × 3.1 | 5.5 g | 21 min | Plate top face down on textured PEI, labels up, as the real Top |
| 2 Inserts | `coupon2_inserts` | black PETG | 28.7 × 39.0 × 16.0 | 6.6 g | 28 min | Plate end on the bed, hole mouths up, spacer ring beside the bar |
| 3 Pocket + USB | `coupon3_pocket_usb` | black PETG | 50.4 × 36.4 × 7.6 | 6.1 g | 24 min | Plate top face down, walls up, USB block with its window axis vertical |
| 4 Glow band | `coupon4_glow_band` | clear/natural PETG | 17.0 × 43.0 × 8.8 | 2.3 g | 10 min | Flat, ring on the bed |
| 4 Glow cap | `coupon4_glow_cap` | black PETG | 19.0 × 21.0 × 3.6 | 0.9 g | 4 min | Flat, feet up |

## Print settings

Use the settings you plan to use for the case: PETG, 0.4 mm nozzle, 240 °C, bed 80 °C, 4 perimeters, 25 % gyroid, 0.2 mm layers, **no supports**. Keep hole or XY compensation off for the first run. Print coupon 1 at 0.16 if you will print the Top at 0.16. The glow band needs **100 % infill** (or 6 perimeters).

## Measure the print first

On coupon 1, measure centre to centre across the three columns, using cutout edges on the same side. The design value is **38.10**. Scale error = (your reading − 38.10) / 38.10, and the edge shift at the PCB = scale error × 30.6 mm. A reading of 38.00 means −0.26 % and costs about 0.08 mm per side. If the error is over 0.3 %, correct the slicer's XY shrinkage compensation first, and leave the CAD alone.

## 1. Plate: which cutout clips well

This tests the 14.0 cutout, the 1.5 mm plate at the clips, the 15.4 clip pocket and the real 19.05 pitch, with four real cutouts plus one each at 13.9 and 14.1. Push a real Gateron KS-3 in from the flat (bed) side, as in [Stage K](../BUILD.md#stage-k-switches). It should press in with a firm click, stay put when you turn the plate over, and not rock. Keycaps on two neighbouring switches should not touch.

| Result | Meaning | Change |
|---|---|---|
| 14.0 clips firmly | Correct as designed | Nothing |
| 14.0 needs hard force or the plate bulges, 14.1 is good | Holes print about 0.1 small, as expected on FDM | Slicer hole/XY compensation of 0.05. In CAD, `CUTOUT = 14.1` in `CAD/frostbite_case.py` |
| 14.0 is loose or the switch rocks, 13.9 is good | Holes print large | Reduce slicer hole compensation or flow, then reprint. Leave the CAD alone: 13.9 overlaps the 14.0 housing in the model and four fit checks fail |
| Clips do not catch on any size | Plate over 1.5 at the clips, or clip pocket too small | If the thin section is over 1.6, fix first-layer squish. Otherwise raise `CLIP_POCKET` |

`CUTOUT = 14.1` builds a sound case, but it sits on the limit of the "Switch cutouts 14.0 +/-0.1" row of `CAD/check_fit.py` (tested in a scratch copy). To keep that row passing, widen its 0.1 to 0.15 and set `CUTOUT_TOL = 0.15` in `verify/fbverify/checks.py` (read from source, not run). Leave `SWITCH_W` alone.

## 2. Inserts: which hole holds an insert

This is a real length of side wall from the Top: 8.7 mm wide, 16 mm tall, Ø3.4 blind continuation, 3.2 mm skin at the end. The holes are Ø4.5, Ø4.7 (real) and Ø4.9, so the walls are 2.1 / 2.0 / 1.9. You have only 2 spare inserts (6 supplied, 4 used), so buy a few extra M3×5×4 inserts if you want to test all three.

Heat-set one spare into Ø4.7, iron about 230 °C, flush with the rim, by the method in [BUILD.md section 6](../BUILD.md#6-heat-set-inserts). Let it cool. Pass an M3×16 through the spacer ring into the insert and tighten until snug. The ring stands in for the GlowBand and Bottom (3.6 mm). If it passes, keep the second spare. If it fails, use the second spare in the hole the table names.

| Result | Meaning | Change |
|---|---|---|
| Ø4.7 goes in straight, stays put when tightened, no bulge | Correct as designed | Nothing |
| Ø4.7 spins or pulls out, Ø4.5 holds | Hole prints large or the insert is small | `INSERT_HOLE, INSERT_DEPTH = 4.5, 4.0` in `CAD/frostbite_case.py` |
| Ø4.7 needs heavy force, bulges or cracks the wall, Ø4.9 is good | Hole prints small | `INSERT_HOLE, INSERT_DEPTH = 4.9, 4.0`. Wall drops to 1.9, above the 1.3 minimum |
| All are bad, or the wall bulges on all | Wrong insert, too much heat, or under-extrusion | Check the kit insert (OD 5, L 4), lower the iron or press more slowly, reprint |
| Plastic pushes up into the screw hole | Molten plastic pooled below the insert | Press more slowly and clear the hole with an M3 screw while warm |

Changing `INSERT_HOLE` also means updating the "Insert holes" row in `CAD/check_fit.py` (tested), `INSERT_HOLE` in `verify/fbverify/checks.py` (read from source), the `case.inserts` text and `boss_od` note in `design.json`, and `heatSetInsert.holeDiameter` in `docs/DIMENSIONS.md`. `boss_od` itself can stay 8.7.

## 3. Pocket and USB: how the real PCB fits

**Pocket corner.** This is the front-left corner of the Top around SW7, with the real plate and a real 14.0 cutout. Both arms step through 0.3 (the real value, at the corner), 0.2 and 0.4 mm from the PCB edge. A switch sets the board's position, as in the case, because a loose board would slide into an L corner and prove nothing. Clip one real switch into the cutout from the flat side. Lower a bare spare PCB onto its pins from the wall side, straight down, front-left corner in the coupon's corner. Solder nothing. Press until the switch housing touches the PCB. Printer paper is about 0.1 mm thick, so use strips as a feeler gauge at each step on both arms.

| Result | Meaning | Change |
|---|---|---|
| Board seats. 1 sheet fits at 0.2, 2 at 0.3, 3 or more at 0.4 | Printed as intended | Keep `"tolerance": 0.3` (`case.tolerance` in `design.json`) |
| 0.2 pinches or stops the board, 0.3 is free | 0.3 works, with little margin if 0.2 stops it | Keep 0.3, and apply the scale error from coupon 1 |
| 0.2 and 0.3 both stop the board, 0.4 is free | 0.3 is too tight on your printer | Set `"tolerance": 0.4` **and** `"boss_od": 8.5` (`case.screws`). Tested: 0.4 alone fails "Boss OD clear of the PCB insertion envelope", and both pass `check_fit.py`. The insert wall drops to 1.9 on the pocket side |
| All steps have a big gap (over 0.2 more than labelled) | Walls print outward, or the cutout is off | Check flow. A loose fit is harmless, so `"tolerance": 0.2` is possible and passes `check_fit.py` (tested) |
| One arm reads differently from the other | X and Y differ on your printer | Fix belts or scale before the full print. Leave the CAD alone |

`case.tolerance` also moves the OLED window and recess and the GlowBand riser gaps, so rerun `CAD/frostbite_case.py` and `CAD/check_fit.py` after changing it. The 0.2 and 0.4 builds ran in a scratch copy with `check_fit.py` only, and `verify` X.pcb_insertion was not run.

This covers only 26 mm near one switch, so a 62 mm pocket can lose more. Subtract the edge shift from your best gap. The wall is 3 mm here (7 to 9 in the real Top), so it flexes more. The board has 1 mm rounded corners and the pocket's are sharp, so a rounded printed corner is unlikely to touch it.

**USB-C opening.** A copy of the real window: 13.5 × 8.0 through 6.7 mm, the back wall's depth from the skin to the pocket. Push your real cable through from the top of the block, since the bed side has first-layer squish. The moulded boot should enter freely for at least 6 mm, with a visible gap. The skin to receptacle mouth distance is 5.6 on the case model and about 6.0 by Seeed's STEP, which disagrees with its footprint. If the boot is tight or stops early, try another cable first. To widen the opening, change `case.usb_cutout.w` or `.h` in `design.json`. `.h` is limited by the stack, so rerun `check_fit.py` and read its USB rows. This coupon cannot show alignment with the receptacle. The real window is an open notch closed by the GlowBand tongue, while this copy is a closed window that avoids a 13.5 mm bridge.

## 4. Glow: how light spreads in clear PETG

The band is a true slice of the real GlowBand (PCB y 14 to 57, back-left LED 9), 43 mm long. The cap stands in for the PCB, holding the LED window over the real LED spot, 1.76 mm above the pad. That gap comes from `docs/audit/pcb-physical.md`: the real LED hangs about 0.84 below the PCB, where the CAD placeholder uses 1.78 and gets 0.82.

Cover the two cut end faces of the band with black tape, or they will glow and mislead you. The easiest light source is a real glow LED on the real PCB running `firmware.uf2`, with the band held at the real position and no cap ([Glow brightness](../BUILD.md#glow-brightness)). The firmware default is `#7fe3ff` at 70 of 255 (about 27 %), so judge it there. `led-test` only steps each LED briefly through its test colours. A loose SK6812 MINI-E needs 5 V and a data signal, so if you wire one, tape the cap on, drop it in the window, emitter toward the pad, and tape the back. A phone torch pressed against the cap's back shows only the **shape** of the spread. Look at the 2 mm outer face (the narrow ring face) in a normally lit room, then a dim one.

| Result | Meaning | Change |
|---|---|---|
| Visible along the whole 31 mm run from the LED, even with a hot spot at the pad | Good sign for the band | Print the full band |
| Bright near the pad, gone within about 15 mm | Expect dark stretches: the front, side and back centres are 27, 30 and 41 mm from the nearest LED | Try 6 perimeters or slower, hotter printing. Then white paint or white paper on the skirt's inner wall, then moving light sources at PCB level. Keep foil away from the board, because a loose piece can short the solder tails |
| Cloudy, with visible layer lines and little carry | Print clarity is the limit | Raise temperature, slow down, 100 % infill, thicker layers |

Geometry values if you change it: `PAD_REACH`, `RISER_T`, `RING_RELIEF` and `RING_LAND` in `CAD/frostbite_case.py`. LED positions are `leds.glow` in `design.json`, which is a PCB change. This coupon shows how far light carries. Final brightness stays open (audit M2) until a real LED is seen at firmware brightness in the assembled case. The coupon has no skirt or Bottom, so it looks better than the case, where black PETG absorbs the light. It has one LED, one pad and one straight side, and reaches only 31.6 mm from the LED. The cap is not solder mask. Phone cameras raise exposure on dim scenes, so trust your eye in a lit room. Clear PETG varies by brand, so use the spool you will print the band with.

## Regenerate and check

```sh
CAD/.venv/bin/python docs/coupons/make_coupons.py       # STEP, STL, previews (about 10 s)
verify/.venv/bin/python docs/coupons/check_coupons.py   # exit 1 on any failure
```

`make_coupons.py` imports `CAD/frostbite_case.py` and writes nothing in `CAD/`. The trial sizes (13.9 / 14.1, Ø4.5 / Ø4.9, 0.2 / 0.3 / 0.4) are fixed, so after changing a real value, update `STEPS`, `INSERT_TRIALS` or `sizes` in `plate()`. `check_coupons.py` holds the intended numbers on its own, so update those too. Current result: **55 of 55 pass**, on the files only. Every part is watertight, no face is past 45° of overhang and there are no bridges. The thinnest wall is 1.5 mm, labels excluded, and all 51 label glyphs have strokes of at least 0.4 mm. The same-as-real check found no difference from the real Top in the 2 × 2 plate, the Ø4.7 wall section and the 0.3 pocket corner, and the band matches `production/GlowBand.stl` in all six compared sections.
