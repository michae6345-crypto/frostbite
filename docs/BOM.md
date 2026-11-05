# Frostbite bill of materials

This matches [`BOM.csv`](../BOM.csv), [`design.json`](../design.json) and the footprints in [`PCB/frostbite.kicad_pcb`](../PCB/frostbite.kicad_pcb). "Kit" parts ship in the Hack Club Hackpad kit. The two Hackpad grants pay for the PCB and the printed case, so there is nothing else to buy. Wiring is in [`images/pinout.png`](images/pinout.png).

## Parts

| Qty | Part | Source | Cost | Refs | Notes | Footprint |
|---:|---|---|---:|---|---|---|
| 1 | Seeed XIAO RP2040 | Kit | Free | U1 | Soldered flat to the PCB underside by its castellated pads, components facing away from the PCB. Its board edge is flush with the PCB's back edge, so the USB-C receptacle overhangs by about 1.0 to 1.4 mm. | `hackpad:XIAO-Generic-Hybrid-14P-2.54-21X17.8MM` |
| 9 | MX switch, Gateron Yellow KS-3 | Kit | Free | SW1–SW9 | 3×3 matrix: agent1–6, approve, talk, stop. | `hackpad:MX-Solderable-1U` |
| 9 | White blank DSA keycap | Kit | Free | | One on every key. | |
| 9 | 1N4148 diode, through-hole | Kit | Free | D1–D9 | COL2ROW, cathode (band) toward the row. | `Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal` |
| 1 | Alps EC11E rotary encoder with switch | Kit | Free | ENC1 | A = D7/GP1, B = D8/GP2. Push switch not wired. | `frostbite:EC11E-Switch_Vertical_H20mm_Slot3.4x1.5` |
| 1 | 0.91" 128×32 SSD1306 I²C OLED | Kit | Free | J1 | Address 0x3C. Header order GND, VCC, SCL, SDA. VCC from 3V3. Soldered to J1 with the header's black plastic removed. | `Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical` |
| 4 | M3 × 16 screw | Kit | Free | | Driven from the plate top, through the Top, into the inserts. The heads show at the corners. | |
| 4 | M3 heat-set insert (M3 × 5 OD × 4 L) | Kit | Free | | In the Bottom corners, flush with the rim. 4.7 mm hole, 4 mm deep. | |
| 1 | PCB, 2-layer, 61.15 × 83.15 mm | JLCPCB | $10 grant | | `production/gerbers.zip`. Minimum order is 5 boards, so you get 4 spares for practice and coupon 3. The price is the grant limit and includes shipping. | |
| 1 | Top | Printing Legion | $5 grant, whole case | | `production/Top.stl`, black. The flat plate. | |
| 1 | Bottom | Printing Legion | Included | | `production/Bottom.stl`, black. The tray. | |
| 1 | OLEDSupport | Printing Legion | Included | | `production/OLEDSupport.stl`, black. Sits between the OLED module and the PCB. | |
| 1 | Knob | Printing Legion | Included | | `production/Knob.stl`, black. 18 mm, for the 6 mm D-shaft. | |

## Kit usage

| Kit part | In kit | Used | Left over |
|---|---:|---:|---:|
| Seeed XIAO RP2040 | 1 | 1 | 0 |
| Gateron Yellow KS-3 MX switches | 16 | 9 | 7 |
| White blank DSA keycaps | 16 | 9 | 7 |
| 1N4148 diodes | 20 | 9 | 11 |
| Alps EC11E encoders | 2 | 1 | 1 |
| 0.91" OLED | 1 | 1 | 0 |
| M3 × 16 screws | 6 | 4 | 2 |
| M3 heat-set inserts | 6 | 4 | 2 |
| **Total** | **68** | **38** | **30** |

The kit's 16 SK6812 MINI-E LEDs stay in the bag. Frostbite does not use them.

## Notes

- The Hack Club parts list names no header for the OLED. A header that comes loose, or one fitted with long pins pointing away from the display, works as it is. With no header, use lead offcuts from spare diodes as pins.
- The [test coupons](coupons/README.md) use the same black filament and print before the case.
