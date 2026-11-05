# Frostbite test coupons

Small prints that check your printer and the risky fits before the full case. `make_coupons.py` cuts them from the real case source and stops if a coupon differs from the real part in the region they share. Each has a `.stl` and a `.step` in print orientation, with previews in `previews/`. Mass and time are estimates from a simple flow model (`check_coupons.py`) and exclude heat-up.

| Print | File | Material | Size (mm) | Est. mass | Est. time | As exported |
|---|---|---|---|---|---|---|
| 1 Plate | `coupon1_plate` | black PETG | 57.2 × 52.1 × 3.1 | 5.5 g | 21 min | Plate top face down on textured PEI, labels up, as the real Top |
| 2 Inserts | `coupon2_inserts` | black PETG | 30.0 × 37.0 × 14.9 | 6.3 g | 26 min | Floor on the bed, hole mouths up, clamp ring beside the corners |
| 3 Pocket + USB | `coupon3_pocket_usb` | black PETG | 50.4 × 36.4 × 7.6 | 6.1 g | 24 min | Plate top face down, walls up, USB block with its window axis vertical |

## Print settings

Use the settings you plan to use for the case: PETG, 0.4 mm nozzle, 240 °C, bed 80 °C, 4 perimeters, 25 % gyroid, 0.2 mm layers, **no supports**. Keep hole or XY compensation off for the first run. Print coupon 1 at 0.16 if you will print the Top at 0.16.

## Measure the print first

On coupon 1, measure centre to centre across the three columns, using cutout edges on the same side. The design value is **38.10**. Scale error = (your reading − 38.10) / 38.10, and the edge shift at the PCB = scale error × 30.6 mm. A reading of 38.00 means −0.26 % and costs about 0.08 mm per side. If the error is over 0.3 %, correct the slicer's XY shrinkage compensation first, and leave the CAD alone.

## 1. Plate: which cutout clips well

This tests the 14.0 cutout, the 1.5 mm plate at the clips, the 15.4 clip pocket and the real 19.05 pitch, with four real cutouts plus one each at 13.9 and 14.1. Push a real Gateron KS-3 in from the flat (bed) side, as in [Stage H](../BUILD.md#stage-h-switches). It should press in with a firm click, stay put when you turn the plate over, and not rock. Keycaps on two neighbouring switches should not touch.

| Result | Meaning | Change |
|---|---|---|
| 14.0 clips firmly | Correct as designed | Nothing |
| 14.0 needs hard force or the plate bulges, 14.1 is good | Holes print about 0.1 small, as expected on FDM | Slicer hole/XY compensation of 0.05. In CAD, `CUTOUT = 14.1` in `CAD/frostbite_case.py` |
| 14.0 is loose or the switch rocks, 13.9 is good | Holes print large | Reduce slicer hole compensation or flow, then reprint. Leave the CAD alone: 13.9 overlaps the 14.0 housing in the model and four fit checks fail |
| Clips do not catch on any size | Plate over 1.5 at the clips, or clip pocket too small | If the thin section is over 1.6, fix first-layer squish. Otherwise raise `CLIP_POCKET` |

`CUTOUT = 14.1` sits on the limit of the "Switch cutouts 14.0 +/-0.1" row of `CAD/check_fit.py`. To keep that row passing, widen its 0.1 to 0.15 and set `CUTOUT_TOL = 0.15` in `verify/fbverify/checks.py`. Leave `SWITCH_W` alone.

## 2. Inserts: which hole holds an insert

This is the real back-left Bottom corner, three times, at full height. The holes are Ø4.5, Ø4.7 (real) and Ø4.9. The thinnest walls, at the pocket corner, are 1.57 / 1.47 / 1.37. You have 2 spare inserts (6 supplied, 4 used), so start with Ø4.7.

Heat-set one spare into Ø4.7, iron about 230 °C, flush with the rim, by the method in [BUILD.md section 6](../BUILD.md#6-heat-set-inserts). Let it cool. Pass an M3×16 through the clamp ring into the insert and tighten until snug. The ring stands in for the Top plate (2.5 mm), so the screw head seats at its real height and the tip reaches its real depth. The screw must seat without bottoming in the blind hole. If it passes, keep the second spare. If it fails, use the second spare in the hole the table names.

| Result | Meaning | Change |
|---|---|---|
| Ø4.7 goes in straight, stays put when tightened, no bulge | Correct as designed | Nothing |
| Ø4.7 spins or pulls out, Ø4.5 holds | Hole prints large or the insert is small | `INSERT_HOLE, INSERT_DEPTH = 4.5, 4.0` in `CAD/frostbite_case.py` |
| Ø4.7 needs heavy force, bulges or cracks the wall, Ø4.9 is good | Hole prints small | `INSERT_HOLE, INSERT_DEPTH = 4.9, 4.0`. Wall drops to 1.37, above the 1.3 minimum |
| All are bad, or the wall bulges on all | Wrong insert, too much heat, or under-extrusion | Check the kit insert (OD 5, L 4), lower the iron or press more slowly, reprint |
| Plastic pushes down into the screw hole | Molten plastic pooled below the insert | Press more slowly and clear the hole with an M3 screw while warm |
| Screw bottoms before the head seats | Screw hole blocked, or the screw runs long | Clear the hole. The blind hole leaves 0.4 past the tip |

Changing `INSERT_HOLE` also means updating the "Insert holes" row in `CAD/check_fit.py`, `INSERT_HOLE` in `verify/fbverify/checks.py`, the `case.inserts` text in `design.json`, and `heatSetInsert.holeDiameter` in `docs/DIMENSIONS.md`.

## 3. Pocket and USB: how the real PCB fits

**Pocket corner.** This is the front-left corner around SW7 in one piece: the real plate with a real 14.0 cutout, and the Bottom pocket wall hanging from it. Both arms step through 0.3 (the real value, at the corner), 0.2 and 0.4 mm from the PCB edge. A switch sets the board's position, as in the case, because a loose board would slide into an L corner and prove nothing. Clip one real switch into the cutout from the flat side. Lower a bare spare PCB onto its pins from the wall side, straight down, front-left corner in the coupon's corner. Solder nothing. Press until the switch housing touches the PCB. Printer paper is about 0.1 mm thick, so use strips as a feeler gauge at each step on both arms.

| Result | Meaning | Change |
|---|---|---|
| Board seats. 1 sheet fits at 0.2, 2 at 0.3, 3 or more at 0.4 | Printed as intended | Keep `"tolerance": 0.3` (`case.tolerance` in `design.json`) |
| 0.2 pinches or stops the board, 0.3 is free | 0.3 works, with little margin if 0.2 stops it | Keep 0.3, and apply the scale error from coupon 1 |
| 0.2 and 0.3 both stop the board, 0.4 is free | 0.3 is too tight on your printer | Set `"tolerance": 0.4`, move the screw axes out or thin `boss_od`, then read the "Boss OD" row of `check_fit.py` |
| All steps have a big gap (over 0.2 more than labelled) | Walls print outward, or the cutout is off | Check flow. A loose fit is harmless, so `"tolerance": 0.2` is possible |
| One arm reads differently from the other | X and Y differ on your printer | Fix belts or scale before the full print. Leave the CAD alone |

`case.tolerance` also moves the OLED window and recess and the pocket, so rerun `CAD/frostbite_case.py` and `CAD/check_fit.py` after changing it.

This covers only 26 mm near one switch, so a 62 mm pocket can lose more. Subtract the edge shift from your best gap. The wall is 3 mm here and 6.7 in the real Bottom, so it flexes more. The board has 1 mm rounded corners and the pocket's are sharp, so a rounded printed corner is unlikely to touch it.

**USB-C opening.** A copy of the real window: 13.5 × 8.0 through 6.7 mm, the back wall's depth from the skin to the pocket. Push your real cable through from the top of the block, since the bed side has first-layer squish. The moulded boot should enter freely for at least 6 mm, with a visible gap. The skin to receptacle mouth distance is 5.6 on the case model and about 6.0 by Seeed's STEP, which disagrees with its footprint. If the boot is tight or stops early, try another cable first. To widen the opening, change `case.usb_cutout.w` or `.h` in `design.json`. `.h` is limited by the stack, so rerun `check_fit.py` and read its USB rows. This coupon cannot show alignment with the receptacle. The real window is a notch in the Bottom closed by a tongue on the Top, while this copy is a closed window that avoids a 13.5 mm bridge.

## Regenerate and check

```sh
CAD/.venv/bin/python docs/coupons/make_coupons.py       # STEP, STL, previews (about 10 s)
verify/.venv/bin/python docs/coupons/check_coupons.py   # exit 1 on any failure
```

`make_coupons.py` imports `CAD/frostbite_case.py` and writes nothing in `CAD/`. The trial sizes (13.9 / 14.1, Ø4.5 / Ø4.9, 0.2 / 0.3 / 0.4) are fixed, so after changing a real value, update `STEPS`, `INSERT_TRIALS` or `sizes` in `plate()`. `check_coupons.py` holds the intended numbers on its own, so update those too.
