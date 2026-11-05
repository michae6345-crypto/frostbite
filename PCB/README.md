# Frostbite 9 PCB

KiCad 10 project. Open `frostbite.kicad_pro`.

The board has 9 MX keys, an EC11E encoder, a 0.91" I2C OLED and a Seeed XIAO RP2040 on the underside. It has two layers and measures 61.15 x 83.15 mm.

Plots: [front](images/pcb_front.png), [back, mirrored](images/pcb_back.png).

| | |
|---|---|
| ![schematic](images/schematic.png) | ![3D](images/pcb_render_3d.png) |
| ![PCB front (top)](images/pcb_render_top.png) | ![PCB back (bottom, mirrored view)](images/pcb_render_bottom.png) |

## Regenerate

Everything comes from `../design.json`. Nothing is placed by hand. Run `sh PCB/tools/build_all.sh`. It does these steps:

1. `make_libs.py` writes the derived footprint, the lib tables and the project settings. Net classes are Default (0.25 mm) and Power (0.5 mm, for GND and +3V3). Clearance is 0.2 mm.
2. `gen_schematic.py` writes the schematic, then ERC runs. UUIDs are deterministic, so the PCB stays linked across runs.
3. `check_netlist.py` works out every net from `design.json`, then checks the exported netlist and `keyboard.json` against it.
4. `gen_pcb.py place` adds the outline, footprints, nets and silkscreen, and writes the Specctra DSN. It needs KiCad's bundled Python.
5. `gen_pcb.py route` runs Freerouting 2.5.0 headless, with the DSN clearance raised to 0.3 mm to stay clear of the board edge. Neck-downs go back to 0.2 mm, then the GND pours are added.
6. DRC runs with schematic parity.
7. `export_bottom_pads.py` writes `build/bottom_pads.json` for the case checks.
8. The script exports Gerbers, drill files, the pos file, `production/gerbers.zip` and the images.

`frostbite.kicad_dru` holds the JLCPCB 2-layer 1 oz rules from `verify/rules/`. The PTH annular ring is raised from 0.18 to JLCPCB's published 0.20.

`gerbers.zip` has F/B Cu, Mask, Paste, Silkscreen and Edge.Cuts with Protel names, silk clipped at the mask, PTH and NPTH Excellon drill files, and a job file.

Last results with KiCad 10.0.8:

* ERC: 0 violations.
* DRC: 0 errors, 0 unconnected, 0 parity issues. At all severities there are 25 warnings, all from the care-package XIAO silk.
* Netlist: 0 differences (21 named nets, 56 pins, 21 parts).
* Freerouting: 0 unrouted, 126 track segments, 3 vias.

## Footprints

* The XIAO symbol and `XIAO-Generic-Hybrid-14P-2.54-21X17.8MM` come from the care package, `github.com/hackclub/hackpad`, `extras/kicad_care_package/`, at `clean` `fb6f7d2cd5d704b01ff011619e0581c751318d15`.
* `MX-Solderable-1U` comes from the same path at `main` `ff97fbd16f7aa6db5860ee1d027b3caf95594599`.
* Diodes and J1 are KiCad standard: `D_DO-35_SOD27_P7.62mm_Horizontal` and `PinHeader_1x04_P2.54mm_Vertical`.
* `lib/frostbite.pretty/EC11E-Switch_Vertical_H20mm_Slot3.4x1.5` is KiCad's slotted EC11E with 3.4 x 1.5 lug slots and 4.0 x 2.1 pads.

## Assembly

Solder the XIAO to the underside at `XIAO HERE`, with its components facing away from the PCB. Fit the switches, diodes, encoder and J1 from the top.

## Placement

PCB coordinates are in mm, with the origin at the top left and y pointing down. `kicad-cli pcb export pos` negates y. ENC1's origin is pad A (46.65, 20.5). J1's origin is pin 1.

| ref | where | position |
|---|---|---|
| SW1 to SW9 | top | switch centres at `design.json keys[]` |
| D1 to D9 | top, vertical in the 5 mm gap right of each switch | (x + 9.525, y), anode up, cathode (K, square pad) at y + 3.81 |
| U1 | bottom (flipped), USB-C toward y = 0 | rect x 12.1 to 29.9, y 0 to 21.0, centre (21.0, 10.5) |
| ENC1 | top, rotated 90 degrees so the A/C/B row faces the keys, clear of J1 | shaft (49.15, 13.0); A/C/B at y 20.5 (x 46.65, 49.15, 51.65); S1/S2 at y 6.0; lugs (43.55, 13.0) and (54.75, 13.0) |
| J1 | top | pin row x 39.0; pins 1 to 4 at y 9.19, 11.73, 14.27, 16.81 = GND, VCC, SCL, SDA |

## GND pours

The XIAO's back sits on this board. It has bare VIN, GND, SWCLK, SWDIO and RST pads, plus USB shell tabs.

* Rule area `xiao_back` (x 15.4 to 26.6, y 0.4 to 21) keeps B.Cu tracks and vias out.
* `xiao_vin_gnd` (x 18.5 to 23.3, y 17.5 to 20.65) also clears the pour.
* `xiao_swd_rst` (x 18.7 to 23.3, y 0.7 to 5.5) also clears the pour.

Pad positions are scaled from Seeed's render (+/- 0.3 mm). The rest of the pour stays. It is GND, and solder mask insulates it.

Pours on both layers use thermal relief on every pad (gap 0.3, spoke 0.4). `min_resolved_spokes` is KiCad's default of 2.

## Encoder lugs

The lug is 2.5 mm wide with a barb tip 6.55 mm from the shaft. KiCad's 2.8 x 1.5 slot at +/-5.6 fails JLCPCB's 2:1 slot rule, and the barb must flex 0.50 mm at the lug corners.

This board's 3.4 x 1.5 slot at +/-5.6 passes at 2.27:1. The flex is 0.20 mm at the centre and 0.26 mm at the corners. Width and centre match KiCad's slot, so the barb still catches the outer edge. The extra length adds no play across the lug.

These figures come from Alps' STEP model. A kit clone may differ.

## OLED pin order

Take the common 0.91" 128x32 module, display side up, with the header at the right end. It presents GND, VCC, SCL, SDA from the back edge to the front edge. A vendor photo and the gorbachev footprint linked from the Hackpad guide agree, so J1 matches `design.json`.

Some clones swap GND and VCC. Compare the kit module's labels with the `GND VCC SCL SDA` silkscreen beside J1 before soldering. The silkscreen is on both faces.

## Nets

| net | |
|---|---|
| ROW0, ROW1, ROW2 | XIAO D0, D1, D2 (GP26, GP27, GP28) to the cathodes of D1-3, D4-6, D7-9 |
| COL0, COL1, COL2 | XIAO D3 (GP29), D9 (GP4), D10 (GP3) to pin 1 of the switches in column 0, 1, 2 |
| SW1_D to SW9_D | switch pin 2 to its 1N4148 anode (COL2ROW) |
| SDA, SCL | XIAO D4 (GP6), D5 (GP7) to J1 pin 4, pin 3 (I2C1; the module has its own pull-ups) |
| ENC_A, ENC_B | XIAO D7 (GP1), D8 (GP2) to encoder A, B |
| GND | XIAO GND, J1 pin 1, encoder C and lugs, both pours |
| +3V3 | XIAO 3V3 to J1 pin 2 (OLED VCC) |

Not connected: XIAO D6, XIAO 5V, and the encoder push switch (S1, S2).

## For the case

* Bottom side: the XIAO is about 3.5 mm tall (allow `xiaoDetail.tMax` 4.5 + 0.5). THT lead ends reach about 1.7 to 2 mm.
* USB-C: the receptacle is centred at x = 21.0, 9.0 wide, on the underside. It overhangs y = 0 by 1.42 mm per Seeed's footprint. Seeed's STEP gives 1.0, and the case fits either. The XIAO board edge is flush with y = 0.
* Top side: only the diodes (2 mm diameter, under the plate), J1 and ENC1. The OLED outline (x 2.5 to 40.5, y 7 to 19) is free of parts apart from flush XIAO pads.
* There are no mounting holes. `design.json` puts the M3 inserts in the bezel, outside the PCB.
