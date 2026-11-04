# Frostbite case (CAD)

A fully 3D-printed sandwich case, generated in CadQuery from `../design.json`. Screw positions, boss OD, shell size and the USB window come from `case` in that file.

![Frostbite case, exploded view](previews/exploded-iso.svg.png)

```sh
cd CAD && uv venv --python 3.12 .venv && uv pip install --python .venv -r requirements.txt
cd .. && CAD/.venv/bin/python CAD/frostbite_case.py   # parts, assembly, previews (~10 s)
CAD/.venv/bin/python CAD/check_fit.py --no-build      # without the flag it rewrites production/
```

## Parts

Exported to `../production/` in print orientation. Top, Bottom and OLEDSupport are matte black PETG, the GlowBand is clear PETG.

| Part | Size (mm) | Notes |
|---|---|---|
| Top | 79.15 × 97.15 × 16.0 | MX plate and skirt. Plate 1.5 at the 14.0 cutouts, 2.5 elsewhere. Inserts in the side walls. |
| GlowBand | 78.15 × 96.15, 2.0 visible, 8.8 overall | Ring, riser wall inside the Top pocket, a pad under each glow LED, a tongue under the USB window. |
| Bottom | 79.15 × 97.15, 3.1 front to 9.9 back | 4° wedge tray, 2.5 floor, Ø3.4 holes with Ø5.8 counterbores. |
| OLEDSupport | 33.9 × 13.5 × 1.4 | C-shaped spacer under the OLED module, taped on both faces. |
| Knob (optional) | Ø18 × 15 | D-bore Ø6.2 / 4.7 across the flat, 12.3 deep. Fit on a real shaft is untested. |

On a desk the top face is 21.1 mm high at the front and 27.8 mm at the back. Keycaps add about 13.6 mm and the knob top is about 22.5 mm above the plate. With both the assembly is 79.2 × 98.9 × 49.5 mm.

### Vertical stack (z = 0 at the PCB underside)

```
 +6.60  Top face = plate top (PCB top + 5.0, fixed by the MX switch)
 +6.05  OLED glass top
 +5.10  plate underside at the clips (1.5)   +5.60 lip underside   +4.60 OLED board top
 +4.10  plate underside elsewhere (2.5)      +3.40 OLED board underside
 +3.00  screw tip (blind Ø3.4 hole ends at 3.4, 3.2 of skin above)
 0..1.6 PCB, in a pocket of PCB + 0.3 per side (61.75 × 83.75)
 -2.60  top of the GlowBand pads and riser (0.6 below any 2.0 lead tail)
 -2.83  USB-C centre = centre of the 13.5 × 8 window
 -9.40  Top skirt rim, inserts pressed in from here to -5.40 | GlowBand ring top
-11.40  GlowBand bottom | Bottom rim
-13.00  screw head seat; underside -16.5 at the front screws, -20.2 at the back screws
```

### Design decisions

- **PCB path.** The PCB can only enter from the skirt side, so nothing printed may stand in that path and the inserts sit fully in the side walls. Bosses tucked 1.35 mm under the PCB edge pass every seated check and still cannot be assembled.
- **Width 79.15.** Tolerance 0.3 + boss OD 8.7 gives 9.0 per side from the PCB edge. Front and back walls stay 7 mm because no screw is there.
- **Top height 16.** It fits the USB window inside the skirt with the inserts at the rim. M3×16 with recessed heads then sets the Bottom's depth.
- **PCB support.** The PCB hangs from the 9 soldered switches. The back 26 mm has no switch, so hard pushes there flex it slightly (estimated 0.35 mm at 10 N).
- **EC11 opening.** The plate is only 0.5 above the EC11 body, so the opening clears the body: 12.98 × 16.0, r 2. Its corners reach 9.49 from the shaft against the knob's 9.0, so it shows from shallow angles.
- **OLED.** A standard 2.5 header would put the glass 0.15 proud, so the plastic comes off and the OLEDSupport sets the height. The glass ends 0.55 below the plate. The module is soldered before the Top so it can be tested and cannot fall away, which means nothing aligns it: the window is 31.0 × 12.98 around the 30 × 11.5 glass, enough for ±1° and ±0.1. The feet sit under both ends of the glass. The force path is untested.
- **USB-C.** The window leaves 0.5 per side around a 12.5 × 7 overmold. The Top has a notch and the GlowBand tongue rises into it, so the Top prints without a long bridge.

### Glow

The band may be faint: the LEDs face down and only 2 mm shows. Test it by holding coupon 4 (`docs/coupons/`) under a glow LED running `firmware.uf2` with no daemon, which shows `#7fe3ff` at 70 of 255. The daemon uses 50 when idle and 110 while something runs. CAD shows 0.82 mm of air under the 1.78 placeholder LED, and the real lens leaves about 1.76. Expect the back edge to be dimmest, about 41 mm from the nearest LED. If it is too dim, try white paint or white paper on the skirt's inner wall and the Bottom floor, then move light sources at the PCB level.

## Print settings

PETG, 0.4 mm nozzle, 240 °C / bed 80 °C, 4 perimeters, 25 % gyroid, **no supports on any part**. At most about 108 g of PETG.

| Part | Orientation (as exported) | Layer | Notes |
|---|---|---|---|
| Top | top face down on textured PEI | 0.2 (0.16 for nicer cutouts) | Print a cutout test first. If switches are tight, use 0.05 hole/XY compensation. |
| Bottom | 4° underside on the bed | 0.2 | The only bridges are the counterbore roofs. |
| OLEDSupport | flat | 0.2 | 2 walls, 100 % infill. |
| GlowBand | flat | 0.2 | 100 % infill (or 6 perimeters) so it glows evenly. |
| Knob | upright, bore opening on the bed | 0.12 | 5 perimeters. Ream the D-bore if it is tight. |

## Assembly order

Print the coupons in `docs/coupons/`, the knob and the OLEDSupport first, and measure the kit OLED (see Unknowns). Soldering detail is in `docs/BUILD.md`. The PCB cannot be removed without the switches, so test before step 12.

1. Heat-set 4 inserts into the Top, skirt up, flush with the rim, iron about 230 °C.
2. Solder the XIAO flat on the underside and flash `led-test.uf2` with BOOT.
3. Fit LED1 and test it, then LED2–LED9, then glow LED10, test it, then LED11–LED13. Glow LEDs go lens down on the underside. The chain feeds them, so only this order can test one.
4. Solder the 9 diodes flat on the top side, ≤ 2.2 mm tall.
5. Solder the EC11 on the top side.
6. Trim all underside tails to ≤ 2.0 mm.
7. If the OLED header is loose, solder its short pins up through the module and trim flush. Check pin labels against the silkscreen beside J1.
8. **Slide the black plastic strip off the pins** toward the free ends. Without this the glass stands proud.
9. Put thin tape (about 0.2 mm, no foam) on both faces of the OLEDSupport's feet and stick it to the module's underside: small foot by the pins, large foot at the far end, rail on the side facing the keys.
10. Put the pins through J1 until the support sticks to the PCB. Square it: back PCB edge to the module's long edge reads 7.0 mm at both ends, within 0.5.
11. Solder the 4 J1 pins from the underside and trim to ≤ 2.0 mm. **Test the OLED and knob** with `led-test`.
12. Clip the 9 switches into the plate from the top face. Check every pin is straight.
13. Turn the Top upside down on two blocks at least 22 mm tall under the plate margin. The encoder shaft stands 19.5 proud, or 21.5 on a generic EC11.
14. Lower the PCB straight down the skirt, underside facing you. The shaft enters its opening about 22 mm before the PCB seats, the skirt at 11, the USB notch at 8, the switch holes at 3.3 and the OLED recess at 2. If it stops, lift out and look.
15. Solder the 18 switch joints from underneath, iron leaning about 40°. Trim to ≤ 2.0 mm. Test every key, then flash `firmware.uf2` while BOOT is reachable.
16. Lower the GlowBand on: riser and pads into the pocket, tongue into the USB notch.
17. Lay the Bottom on and drive 4 M3×16 from underneath until snug. PETG creeps, so don't over-tighten.
18. Press on the keycaps and the knob (D-flat aligned) or a bought 18 mm knob. Add 4 stick-on feet.

After closing, reaching BOOT and RESET means removing the 4 screws.

## Unknowns

Nobody has measured the kit OLED. Room left: ribbon 1.0 above the board and 1.1 past the far end (widen `oled.window` if not), trimmed joints 1.0 (trim again), and nothing planned for parts under the feet at x 3.5–9.5 and 32.2–37.4 (move the feet). Glass is assumed 1.45 and length 38; a 36 module means shifting the window. Strip removal, tape thickness and squareness while soldering are untested.

## What `check_fit.py` verifies

Interference between every part and placeholder, the pocket, cutouts, inserts, USB and OLED fit, and print limits (no overhang over 45°, bridges ≤ 10 mm, walls ≥ 0.8). It sweeps assembly steps 1, 12, 14 and 16–18 along their straight paths, including the OLED turned ±1°. Two self-tests must block the sweep or it proves nothing. Every pad in `PCB/build/bottom_pads.json` is a keep-out.
