# Frostbite bill of materials

Everything here comes from [`design.json`](../design.json) and the footprints in [`PCB/frostbite.kicad_pcb`](../PCB/frostbite.kicad_pcb). "Kit" parts ship in the Hack Club Hackpad kit, and you source the rest. Wiring is in [`images/pinout.png`](images/pinout.png).

## Parts

| Qty | Part | Source | Refs | Notes | Footprint |
|---:|---|---|---|---|---|
| 1 | Seeed XIAO RP2040 | Kit | U1 | All 11 GPIO used. Soldered flat to the PCB underside by its castellated pads, components facing away from the PCB. Its board edge is flush with the PCB's back edge, so the USB-C receptacle overhangs by about 1.0 to 1.4 mm. | `hackpad:XIAO-Generic-Hybrid-14P-2.54-21X17.8MM` |
| 9 | MX switch, Gateron Yellow KS-3 | Kit | SW1–SW9 | 3×3 matrix: agent1–6, approve, talk, stop. | `hackpad:MX-Solderable-1U` |
| 9 | 1N4148 diode, through-hole | Kit | D1–D9 | COL2ROW, cathode (band) toward the row. | `Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal` |
| 1 | Alps EC11E rotary encoder with switch | Kit | ENC1 | A = D7/GP1, B = D8/GP2. Push switch not wired (no free GPIO). | `frostbite:EC11E-Switch_Vertical_H20mm_Slot3.4x1.5` |
| 1 | 0.91" 128×32 SSD1306 I²C OLED | Kit | J1 | Address 0x3C. Header order GND, VCC, SCL, SDA. VCC from 3V3. Soldered to J1 with the header's black plastic removed. | `Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical` |
| 9 | SK6812 MINI-E, per-key | Kit | LED1–LED9 | Reverse-mounted under each switch, chain 0–8 serpentine. | `frostbite:SK6812MINI-E_key` |
| 4 | SK6812 MINI-E, glow | Kit | LED10–LED13 | Chain 9–12. Mounted flipped, shining down into the band. Follow the `LENS OUT` silkscreen, chamfered lead on the triangle. Fitted lens-in, neither VDD nor GND reaches its own pad, the glow chain stays dark and LED9 is at risk. | `frostbite:SK6812MINI-E_glow_down` |
| 3 | White blank DSA keycap | Kit | | On approve, talk, stop. | |
| 4 | M3 heat-set insert (M3 × 5 OD × 4 L) | Kit | | In the Top's side walls, 4.7 mm hole, 4 mm deep. | |
| 4 | M3 × 16 screw | Kit | | Driven from underneath into the inserts, so no screws show on top. | |
| 6 | Frosted translucent MX keycap, 1u | Buy | | On agent1–6, since kit caps are opaque and colours would not show. Use DSA profile to sit level with the white caps. The case model assumes DSA height. | |
| 1 | Knob, 18 mm, for 6 mm D-shaft | Buy or print | | Knurled aluminium, or print `production/Knob.stl`. Keep it at 18 mm: 20 mm crowds the keycaps and the wall. | |
| 1 | PCB, 2-layer, 61.15 × 83.15 mm | Buy | | JLCPCB from `production/gerbers.zip`. Minimum order is 5 boards, so you get 4 spares for practice and coupon 3. | |
| 1 each | Top, Bottom | Print | | `production/Top.stl`, `production/Bottom.stl`, matte black PETG. Matte or satin, because gloss shows fingerprints. | |
| 1 | Glow band | Print | | `production/GlowBand.stl`, clear or natural PETG. The ~2 mm ice-blue light gap under the floating plate. Buy the filament if your printer lacks it. | |
| 1 | OLEDSupport | Print | | `production/OLEDSupport.stl`, black PETG. Sits under the OLED module. | |
| 5 prints | Test coupons | Print | | [`coupons/`](coupons/README.md) come first. | |
| 1 | Thin double-sided tape, about 0.2 mm, not foam tape | Buy | | Holds the OLEDSupport to the module and the PCB. | |
| 4 | Stick-on feet | Buy | | The case has no feet or recess. They stop it sliding on a desk. | |
| 1 | USB-C data cable | Buy or own | | Any data-capable USB-C cable. | |
| 1 | 4-pin 2.54 mm header | Buy if needed | | Only if the kit OLED arrives without one. See below. | |

## Kit usage

| Kit part | In kit | Used | Left over |
|---|---:|---:|---:|
| Seeed XIAO RP2040 | 1 | 1 | 0 |
| Gateron Yellow KS-3 MX switches | 16 | 9 | 7 |
| White blank DSA keycaps | 16 | 3 | 13 |
| 1N4148 diodes | 20 | 9 | 11 |
| Alps EC11E encoders | 2 | 1 | 1 |
| 0.91" OLED | 1 | 1 | 0 |
| SK6812 MINI-E LEDs | 16 | 13 | 3 |
| M3 × 16 screws | 6 | 4 | 2 |
| M3 heat-set inserts | 6 | 4 | 2 |
| **Total** | **84** | **45** | **39** |

## Notes

- The kit has no decoupling capacitors or level shifter. The SK6812s run from 5V (VBUS) and the OLED from 3V3. LED data is 3.3 V, below the datasheet's 3.5 V. That is common on Hackpad builds and usually fine, but it is flagged in [`VERIFICATION.md`](VERIFICATION.md) and needs [a test on this board](BUILD.md#led-data-level).
- The Hack Club parts list names no header for the OLED, and nobody has seen the kit module yet. A header that comes loose, or fitted with long pins pointing away from the display, works as it is.
