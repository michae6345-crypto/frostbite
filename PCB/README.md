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
| `frostbite.kicad_dru` | JLCPCB 2-layer 1 oz custom rules (from `verify/rules/`, with the PTH annular ring raised from 0.18 to JLCPCB's published 0.20) |
| `sym-lib-table`, `fp-lib-table` | project libraries (care package, derived footprints, KiCad standard) |
| `lib/` | Hack Club care package files + `frostbite.pretty` (derived LED footprints) |
| `tools/` | generators and checks (below) |
| `build/` | regenerated intermediates: netlist, DSN/SES, ERC/DRC JSON, gerbers, pos file, `bottom_pads.json` (underside pads, used by the case checks) |
| `../production/gerbers.zip` | Gerbers (F/B Cu, Mask, Paste, Silkscreen, Edge.Cuts, Protel file names, silk clipped at the mask) + PTH/NPTH Excellon drill + job file |

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
   neck-downs widened back to the 0.2 mm minimum, GND pours on both layers with thermal relief on
   every pad, zone fill, save.
7. `kicad-cli pcb drc --severity-error --exit-code-violations --schematic-parity`.
8. `tools/export_bottom_pads.py` writes `build/bottom_pads.json`.
9. Gerbers, drill, pos file, `production/gerbers.zip`, images (`sch export pdf` / `pcb export pdf`
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
  underside with the lens facing **out of the board** (its back sits in the cut-out), i.e. the
  mirrored pin arrangement of the per-key (lens-into-hole) LEDs.
* `EC11E-Switch_Vertical_H20mm_Slot3.4x1.5` – KiCad's slotted EC11E footprint with 3.4 × 1.5 lug
  slots and 4.0 × 2.1 pads (see "Encoder lugs").

Other footprints: KiCad standard `Diode_THT:D_DO-35_SOD27_P7.62mm_Horizontal` and
`Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical`. SW3's pad 2 is reduced to Ø2.0 on
the board only (not in the library), which is why DRC notes one footprint-vs-library mismatch. Do
not "update footprints from library" on SW3 without restoring it.

## Assembly: the glow LEDs go in the other way up

All 13 MINI-Es solder to B.Cu pads around an identical cut-out, but:

| | LEDs | Fit | Light |
|---|---|---|---|
| Key LEDs | LED1–LED9 | Lens **into** the hole, back of the part facing you | Up, into the switch |
| Glow LEDs | LED10–LED13 | **Flipped: lens out**, facing you, back of the part in the hole | Down, into the glow band |

Both ways, line the chamfered lead up with the board's triangle. The silkscreen shows `LENS OUT`
and a ring-and-dot mark beside each glow LED, and a two-line legend sits at the middle of the underside.

The triangle is also the check. The four pads form a 5.55 × 1.5 mm rectangle, so a part can only sit
at 0° or 180°, and a part that is the wrong way up can never put its chamfer on the triangle. If the
chamfer will not line up, stop and turn the part over.

Soldered lens-in at a glow position anyway, neither VDD nor GND reaches its own pad. At LED10:

| Position | VDD lead on | DOUT lead on | GND lead on | DIN lead on |
|---|---|---|---|---|
| Correct, lens out | +5V | `LED_D10` | GND | `LED_D9` |
| Lens in, 0° | `LED_D9` | GND | `LED_D10` | +5V |
| Lens in, 180° | `LED_D10` | +5V | `LED_D9` | GND |

The supply leads end up on data nets and the rails on the data pins, so expect the glow chain to
stay dark, and LED9's DOUT is at risk as well because it feeds `LED_D9`. Light would also go into the
board. This is worked out from the pad geometry; nothing has been built. Do not leave a suspect glow
LED powered. Glow LEDs get their data through LED1–LED9, so fit those first, then fit LED10 alone and test it with
`led-test.uf2` before fitting the rest.

Solder the XIAO to the underside (`XIAO HERE`), with its components facing away from the PCB. Compare
the kit OLED's pin labels with the `GND VCC SCL SDA` silkscreen beside J1 before soldering it.

## Results

ERC (`build/erc.json`, KiCad 10.0.8, severities `error`): **0 violations** (also 0 at all severities).

DRC (`build/drc.json`, KiCad 10.0.8, severities `error`, schematic parity on):
`"violations": [], "unconnected_items": [], "schematic_parity": []` → **0 errors, 0 unconnected, 0 parity issues**.
At all severities there are 26 warnings and no errors: 25 from care-package XIAO silk (over its own
pads, and its USB outline past the board edge), plus the deliberate SW3 pad change above.

Netlist check: `netlist matches design.json and keyboard.json: 0 differences` (35 named nets, 109 pins, 34 parts).

Routing: Freerouting reports 0 unrouted, 0 violations; 499 track segments (0.2 / 0.25 signal,
0.375 / 0.5 power), 40 vias. Board outline 61.15 × 83.15 mm (Edge.Cuts gerber extents 0…61.15 × 0…83.15).

## Placement (PCB coordinates, mm, origin top-left, y down)

| ref | where | position |
|---|---|---|
| SW1–SW9 | top | switch centres exactly at `design.json keys[]` |
| D1–D9 | top, vertical in the 5 mm gap right of each switch | (x + 9.525, y), anode up, cathode (K, square pad) at y + 3.81 |
| LED1–LED9 | per-key, on the underside, lens into the cut-out, shining up | (x, y + 5.08) under each switch's LED window; LEDn = chain index n−1 per `keys[].led` |
| LED10–LED13 | glow, underside, flipped: lens out, shining down | (5.0, 25.4) (56.15, 25.4) (56.15, 80.6) (5.0, 80.6) |
| U1 | bottom (flipped), USB-C toward y = 0 | rect 12.1…29.9 × 0…21.0, centre (21.0, 10.5) |
| ENC1 | top, rotated 90° (A/C/B row toward the keys) | shaft (49.15, 13.0); A/C/B at y 20.5 (x 46.65/49.15/51.65); S1/S2 at y 6.0; lugs (43.55, 13.0) (54.75, 13.0) |
| J1 | top | pin row x 39.0, pins 1–4 at y 9.19 / 11.73 / 14.27 / 16.81 = GND, VCC, SCL, SDA |

Note for `kicad-cli pcb export pos`: KiCad reports footprint origins with y negated; ENC1's origin
is pad A (46.65, 20.5), not the shaft, and J1's origin is pin 1.

## Under the XIAO

The XIAO's back sits directly on this board, and that back has bare VIN, GND, SWCLK, SWDIO and RST
pads plus USB shell tabs. The rule area `xiao_back` (x 15.4–26.6, y 0.4–21) keeps B.Cu tracks and vias
out. Two more clear the pour under the bare pads: `xiao_vin_gnd` (x 18.5–23.3, y 17.5–20.65) and
`xiao_swd_rst` (x 18.7–23.3, y 0.7–5.5). Pad positions are scaled from Seeed's render (± 0.3 mm). The rest
of the pour under the XIAO stays, insulated by solder mask only, and it is GND. `xiao_swd_rst` is added
after routing because it only affects the pour.

## GND pours

Pours use thermal relief on every pad, SMD and through-hole (gap 0.3, spoke 0.4), so no joint fights
the pour. LED9 and LED11 pad 3 have no pour contact at all and connect by their 0.5 mm GND tracks.
`min_resolved_spokes` is 1 because U1 pad 13, the only XIAO GND pin, gets 2 spokes on F.Cu but 1 on
B.Cu. Those three 0.4 mm spokes comfortably carry the 0.48 A worst case.

## Encoder lugs

The lug is 2.5 mm wide with a barb tip at 6.55 mm from the shaft. How far the barb must flex past the
hole edge, in mm, at the lug's centre and at its corners against a rounded slot end:

| Hole | Lug centre | Lug corner | Passes JLCPCB 2:1 slot rule? |
|---|---|---|---|
| Ø2.6 round at ±5.6 (previous board) | none | 0.59 | n/a |
| KiCad 2.8 × 1.5 at ±5.6 | 0.20 | 0.50 | No |
| Alps 2.6 × 1.5 at ±5.5, if its ends are round | 0.30 | 0.78 | No |
| **3.4 × 1.5 at ±5.6 (this board)** | **0.20** | **0.26** | Yes, 2.27:1 |

Width and centre match KiCad's slot, which six reference boards use, so the barb still catches the
outer edge. The extra length only clears the corners and adds no play across the lug. Figures are
from Alps' STEP model; a kit clone may differ.

## OLED pin order

The common 0.91" 128×32 module, display side up with the header at the **right** end, presents
GND, VCC, SCL, SDA from the back edge (top of the PCB view) to the front edge: a vendor photo of
the module in that orientation has SDA on the pin nearest the viewer, and the gorbachev footprint
the Hackpad guide links (38 × 12 board, pads at x 36.5, GND at y 2.19) is the same. So J1 matches
`design.json` as written. Some clones swap GND/VCC, so compare the kit module's labels with the
`GND VCC SCL SDA` silkscreen beside J1 (on both faces) before soldering.

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
| +5V | XIAO 5V (VBUS) to every SK6812 VDD (0.5 mm tracks, 0.375 mm over about 26 mm where Freerouting necked them down) |
| +3V3 | XIAO 3V3 to J1 pin 2 (OLED VCC) |
| GND | common; pours on both layers |

## For the case

* Bottom side: XIAO (≈3.5 mm, allow `xiaoDetail.tMax` 4.5 + 0.5). Per-key LED backs protrude ≈0.94 mm
  below B.Cu, glow LED lenses ≈0.84 mm (the lens is the 0.84 side of the part). THT lead ends ≈1.7–2 mm (switches, encoder, diodes, J1).
* USB-C: receptacle centred at x = 21.0, 9.0 wide, on the underside, overhanging the y = 0 edge by
  1.42 mm per Seeed's footprint (Seeed's STEP gives 1.0; a real XIAO settles it). The XIAO board edge itself is flush with
  y = 0, and the case fits with either overhang.
* ENC1 lug pads are 2.1 × 4.0 at (43.55, 13.0) and (54.75, 13.0); parts sit where they did.
* Top side: only the diodes (Ø 2 mm, under the plate) and J1/ENC1; OLED module outline (x 2.5–40.5, y 7–19) is free of parts apart from flush XIAO pads.
* No mounting holes: `design.json` puts the M3 inserts in the bezel, outside the PCB.
