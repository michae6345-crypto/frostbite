# Frostbite 9 PCB

KiCad 10 project for the Frostbite 9 Hackpad: 3×3 MX keys, EC11E encoder, 0.91" I²C OLED,
13 × SK6812 MINI-E and a Seeed XIAO RP2040 on the underside. Two layers, 61.15 × 83.15 mm.

| | |
|---|---|
| ![schematic](images/schematic.png) | ![3D](images/pcb_render_3d.png) |
| ![PCB front (top)](images/pcb_render_top.png) | ![PCB back (bottom, mirrored view)](images/pcb_render_bottom.png) |

2D copper/silk plots: [front](images/pcb_front.png), [back, mirrored](images/pcb_back.png).

## Files

| file | what |
|---|---|
| `frostbite.kicad_pro` / `.kicad_sch` / `.kicad_pcb` | the project (open the `.kicad_pro`) |
| `frostbite.kicad_dru` | JLCPCB 2-layer 1 oz custom rules (copied from `verify/rules/`) |
| `sym-lib-table`, `fp-lib-table` | project libraries (care package, derived footprints, KiCad standard) |
| `lib/` | Hack Club care package files + `frostbite.pretty` (derived LED footprints) |
| `tools/` | generators and checks (below) |
| `build/` | regenerated intermediates: netlist, DSN/SES, ERC/DRC JSON, gerbers, pos file |
| `../production/gerbers.zip` | Gerbers (F/B Cu, Mask, Paste, Silkscreen, Edge.Cuts) + PTH/NPTH Excellon drill + job file |

## How it was generated / how to regenerate

Everything is generated from `../design.json`; nothing was placed by hand.

```sh
sh PCB/tools/build_all.sh
```

1. `tools/make_libs.py` – writes the derived LED footprints, `sym-lib-table`, `fp-lib-table`
   and (first run only) `frostbite.kicad_pro` with net classes (Default 0.25 mm / Power 0.5 mm for GND, +5V, +3V3; clearance 0.2 mm).
2. `tools/gen_schematic.py` – writes `frostbite.kicad_sch` (S-expression) with symbols copied into
   the lib cache, a wire stub + global label (signals) or power symbol on every pin, no-connect flags,
   PWR_FLAGs. Deterministic UUIDs, so the PCB stays linked across runs.
3. `kicad-cli sch erc --severity-error --exit-code-violations`.
4. `kicad-cli sch export netlist` → `tools/check_netlist.py` recomputes every net from `design.json`
   and checks it, plus `Firmware/qmk/keyboards/frostbite/keyboard.json` (matrix pins, COL2ROW,
   encoder pins, WS2812 pin, `rgb_matrix` order vs `keys[].led`). Exit 1 on any difference.
5. `tools/gen_pcb.py place` (KiCad's bundled Python + `pcbnew`) – board outline (R 1.0 corners),
   footprints from the libraries placed at `design.json` coordinates, pads assigned from the
   netlist, symbol links (path/sheet) set for parity, silkscreen; exports Specctra DSN.
6. `tools/gen_pcb.py route` – Freerouting 2.5.0 headless (`-de … -do … -mp 100`, DSN clearance
   raised to 0.3 mm so traces keep clear of the board edge and LED cut-outs), SES import, Freerouting
   neck-downs widened back to the 0.2 mm minimum, GND pours on both layers, zone fill, save.
7. `kicad-cli pcb drc --severity-error --exit-code-violations --schematic-parity`.
8. Gerbers, drill, pos file, `production/gerbers.zip`, images (`sch export pdf` / `pcb export pdf`
   → PNG via `sips`, and `pcb render`).

## Hack Club care package

From `github.com/hackclub/hackpad`, `extras/kicad_care_package/`:

| file | branch | commit |
|---|---|---|
| `XIAO_RP2040.kicad_sym`, `SK6812MINI-E.kicad_sym`, `XIAO-Generic-Hybrid-14P-2.54-21X17.8MM.kicad_mod`, `SK6812MINI-E_fixed.kicad_mod` | `clean` (default) | `fb6f7d2cd5d704b01ff011619e0581c751318d15` |
| `MX-Solderable-1U.kicad_mod` (not on `clean`) | `main` | `ff97fbd16f7aa6db5860ee1d027b3caf95594599` |

The XIAO footprint is byte-identical on both branches. Derived footprints (`lib/frostbite.pretty`):

* `SK6812MINI-E_key` – the care-package MINI-E with pads moved 0.175 mm outward and shortened on
  the inside (copper 2.15–3.40 mm from centre) so it is ≥ 0.3 mm from the routed LED cut-out
  (the original pads are 0.1 mm from it, which fails JLCPCB's copper-to-edge rule). Courtyard tightened.
* `SK6812MINI-E_glow_down` – the same on F.* layers; flipped to the bottom it is a MINI-E on the
  underside with the lens facing **down** (its back sits in the cut-out), i.e. the mirrored pin
  arrangement of the per-key (lens-up) LEDs.

Other footprints: KiCad standard `Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal`,
`Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm_CircularMountingHoles` (the slotted
variant's 2.8 × 1.5 slots fail JLCPCB's 2:1 slot rule) and `Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical`.

## Results

ERC (`build/erc.json`, KiCad 10.0.8, severities `error`): **0 violations** (also 0 at all severities).

DRC (`build/drc.json`, KiCad 10.0.8, severities `error`, schematic parity on):
`"violations": [], "unconnected_items": [], "schematic_parity": []` → **0 errors, 0 unconnected, 0 parity issues**.
At all severities there are 26 silkscreen warnings, all from library artwork (care-package XIAO
silk over its own pads, its USB outline past the board edge, one MINI-E pin-1 marker near SW3).

Netlist check: `netlist matches design.json and keyboard.json: 0 differences` (35 named nets, 109 pins, 34 parts).

Routing: Freerouting reports 0 unrouted, 0 violations; 467 track segments (0.2 / 0.25 signal,
0.375 / 0.5 power), 33 vias. Board outline 61.15 × 83.15 mm (Edge.Cuts gerber extents 0…61.15 × 0…83.15).

## Placement (PCB coordinates, mm, origin top-left, y down)

| ref | where | position |
|---|---|---|
| SW1–SW9 | top | switch centres exactly at `design.json keys[]` |
| D1–D9 | top, vertical in the 5 mm gap right of each switch | (x + 9.525, y), anode up, cathode (K, square pad) at y + 3.81 |
| LED1–LED9 | per-key, reverse mounted on the underside, lens up through the cut-out | (x, y + 5.08) under each switch's LED window; LEDn = chain index n−1 per `keys[].led` |
| LED10–LED13 | glow, underside, lens down | (5.0, 25.4) (56.15, 25.4) (56.15, 80.6) (5.0, 80.6) – see deviations |
| U1 | bottom (flipped), USB-C toward y = 0 | rect 12.1…29.9 × 0…21.0, centre (21.0, 10.5) |
| ENC1 | top, rotated 90° (A/C/B row toward the keys) | shaft (49.15, 13.0); A/C/B at y 20.5 (x 46.65/49.15/51.65); S1/S2 at y 6.0; lugs (43.55, 13.0) (54.75, 13.0) |
| J1 | top | pin row x 39.0, pins 1–4 at y 9.19 / 11.73 / 14.27 / 16.81 = GND, VCC, SCL, SDA |

Note for `kicad-cli pcb export pos`: KiCad reports footprint origins with y negated; ENC1's origin
is pad A (46.65, 20.5), not the shaft, and J1's origin is pin 1.

## OLED pin order

The common 0.91" 128×32 module, display side up with the header at the **right** end, presents
GND, VCC, SCL, SDA from the back edge (top of the PCB view) to the front edge: a vendor photo of
the module in that orientation has SDA on the pin nearest the viewer, and the gorbachev footprint
the Hackpad guide links (38 × 12 board, pads at x 36.5, GND at y 2.19) is the same. So J1 matches
`design.json` as written. Some clones swap GND/VCC: check the silkscreen on the kit module before soldering.

## Nets

| net | |
|---|---|
| ROW0 / ROW1 / ROW2 | XIAO D0/D1/D2 (GP26/27/28) to the cathodes of D1–3 / D4–6 / D7–9 |
| COL0 / COL1 / COL2 | XIAO D3 (GP29) / D9 (GP4) / D10 (GP3) to pin 1 of the switches in column 0 / 1 / 2 |
| SW1_D … SW9_D | switch pin 2 to its 1N4148 anode (COL2ROW) |
| SDA / SCL | XIAO D4 (GP6) / D5 (GP7) to J1 pin 4 / pin 3 (I²C1; the module has its own pull-ups) |
| ENC_A / ENC_B | XIAO D7 (GP1) / D8 (GP2) to encoder A / B (C and lugs to GND; push switch S1/S2 not connected) |
| LED_DIN | XIAO D6 (GP0) to LED1 DIN (3.3 V data into a 5 V chain, see VERIFICATION.md) |
| LED_D1 … LED_D12 | LEDn DOUT → LED(n+1) DIN; LED13 DOUT is not connected |
| +5V | XIAO 5V (VBUS) to every SK6812 VDD (0.5 mm tracks) |
| +3V3 | XIAO 3V3 to J1 pin 2 (OLED VCC) |
| GND | common; pours on both layers |

## For the case

* Bottom side: XIAO (≈3.5 mm, allow `xiaoDetail.tMax` 4.5 + 0.5), MINI-E bodies 0.84 mm (per-key)
  and lenses ≈0.94 mm (glow LEDs, shining down), THT lead ends ≈1.7–2 mm (switches, encoder, diodes, J1).
* USB-C: receptacle centred at x = 21.0, 9.0 wide, on the underside, overhanging the y = 0 edge by 1.42 mm.
* Top side: only the diodes (Ø 2 mm, under the plate) and J1/ENC1; OLED module outline (x 2.5–40.5, y 7–19) is free of parts apart from flush XIAO pads.
* No mounting holes: `design.json` puts the M3 inserts in the bezel, outside the PCB.
