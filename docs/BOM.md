# Frostbite bill of materials

Everything here comes from [`design.json`](../design.json) and the footprints in
[`PCB/frostbite.kicad_pcb`](../PCB/frostbite.kicad_pcb). "Kit" means the part ships in the
Hack Club Hackpad kit; "Buy" means you source it yourself. Wiring is in
[`images/pinout.png`](images/pinout.png).

## Parts on the board

| Qty | Part | Kit / Buy | Refs | Notes | Footprint |
|---:|---|---|---|---|---|
| 1 | Seeed XIAO RP2040 | Kit | U1 | All 11 GPIO used. Soldered face-down on the underside of the PCB by its castellated pads, USB-C flush with the back edge. | `hackpad:XIAO-Generic-Hybrid-14P-2.54-21X17.8MM` |
| 9 | MX switch, Gateron Yellow KS-3 | Kit | SW1–SW9 | 3×3 matrix: agent1–6, approve, talk, stop. | `hackpad:MX-Solderable-1U` |
| 9 | 1N4148 diode, through-hole | Kit | D1–D9 | One per switch, COL2ROW, cathode (band) toward the row. | `Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal` |
| 1 | Alps EC11E rotary encoder with switch | Kit | ENC1 | A = D7/GP1, B = D8/GP2. Push switch not wired (no free GPIO). | `Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm_CircularMountingHoles` |
| 1 | 0.91" 128×32 SSD1306 I²C OLED | Kit | J1 | Address 0x3C. Header order GND, VCC, SCL, SDA. VCC from 3V3. Standard 2.54 mm header so the glass sits near plate level. | `Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical` |
| 9 | SK6812 MINI-E, per-key | Kit | LED1–LED9 | Reverse-mounted under each switch, chain 0–8 serpentine. | `frostbite:SK6812MINI-E_key` |
| 4 | SK6812 MINI-E, glow | Kit | LED10–LED13 | On the PCB underside, shining down into the clear PETG light-gap band, chain 9–12. | `frostbite:SK6812MINI-E_glow_down` |
| 3 | White blank DSA keycap | Kit | — | On the command keys: approve, talk, stop. | — |
| 6 | Frosted translucent MX keycap, 1u | Buy | — | On agent1–6 so the status colours show through. Pick a low profile (DSA or XDA) so they sit level with the white DSA caps. | — |
| 1 | Knob, 18 mm, for 6 mm D-shaft | Buy or print | — | Knurled aluminium, or print `production/Knob.stl`. Keep it at 18 mm: 20 mm crowds the keycaps and the wall. | — |
| 1 | PCB, 2-layer, 61.15 × 83.15 mm | Buy | — | JLCPCB from `production/gerbers.zip`. Minimum order is 5 boards. | — |

## Case and hardware

| Qty | Part | Kit / Buy | Notes |
|---:|---|---|---|
| 4 | M3 heat-set insert (M3 × 5 OD × 4 L) | Kit | In the bezel, 4.7 mm hole, 4 mm deep. |
| 4 | M3 × 16 screw | Kit | Driven from underneath into the inserts, so no screws show on top. |
| 1 | Top (plate and shell) | Print | `production/Top.stl`, iced/frosted PETG. |
| 1 | Bottom | Print | `production/Bottom.stl`, iced/frosted PETG. |
| 1 | Glow band | Print | `production/GlowBand.stl` in clear or natural PETG. This is the ~2 mm ice-blue light gap under the floating plate. |
| 1 | Knob (if not buying one) | Print | `production/Knob.stl`. |
| 1 | USB-C data cable | Buy / own | Any data-capable USB-C cable. |

## Buy yourself

| Qty | Item | Notes |
|---:|---|---|
| 6 | Frosted translucent MX keycaps, 1u | For agent1–6. DSA or XDA profile. |
| 1 | 18 mm knob for a 6 mm D-shaft | Or print `production/Knob.stl` instead. |
| 1 | Clear or natural PETG filament | For the glow band. |
| 1 order | PCB from JLCPCB | `production/gerbers.zip`, 2 layers, 61.15 × 83.15 mm. You get 5, need 1. |
| 1 set | Printed case | Top + Bottom in iced/frosted PETG, Glow band in clear PETG. |

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

## Left over from the kit

- 7 Gateron Yellow KS-3 switches
- 13 white DSA keycaps
- 11 1N4148 diodes
- 1 EC11E encoder
- 3 SK6812 MINI-E
- 2 M3 × 16 screws
- 2 M3 heat-set inserts

## Notes

- No decoupling capacitors or level shifter in the kit. LED data is 3.3 V into 5 V SK6812s, which is
  common on Hackpad builds and usually fine. It is flagged in [`VERIFICATION.md`](VERIFICATION.md).
- The SK6812s run from 5V (VBUS). The OLED runs from 3V3.
