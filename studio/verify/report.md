# Frostbite Studio verification report

Generated 2026-11-03T20:09:07.052Z by `node verify/run.js` (seed 20261103, 500 random specs, Node v24.22.1).

**Result: PASS** — 0 hard failures, 33 warnings.

## Modules

| file | loaded | stub | bytes | note |
|---|---|---|---|---|
| dims.js | yes | - | 5357 |  |
| layouts.js | yes | - | 3533 |  |
| catalog.js | yes | - | 20223 |  |
| constraints.js | yes | - | 20369 |  |
| render-top.js | yes | - | 32720 |  |
| render-side.js | yes | - | 56390 |  |

## Test set

1889 specs: 37 preset, 1344 exhaustive, 500 random, 8 robustness. Exhaustive = layout × plate × glowPlace × bezel × corner with other axes at defaultSpec. Robustness specs (empty statuses, `&<>` in wordmark, extremes) only produce warnings.

## Summary

| check family | checks | hard | soft | status |
|---|---|---|---|---|
| modules | 6 | 0 | 0 | pass |
| catalog contract | 128 | 0 | 7 | warn |
| spec validity | 10205 | 0 | 0 | pass |
| harness self-test | 10 | 0 | 0 | pass |
| FB.check shape | 3770 | 0 | 0 | pass |
| FB.check limits | 14154 | 0 | 0 | pass |
| presets pass | 37 | 0 | 0 | pass |
| geometry vs FB.check | 1881 | 0 | 0 | pass |
| renderTop | 4031 | 0 | 0 | pass |
| renderSide | 1881 | 0 | 0 | pass |
| renderExploded | 1881 | 0 | 0 | pass |
| robustness | 32 | 0 | 0 | pass |
| geometry (layout) | 7 | 0 | 6 | warn |
| geometry (shell) | 84 | 0 | 20 | warn |

## FB.check outcomes

Strict specs checked: 1314 ok, 567 rejected (0 rejected specs also have geometry issues, i.e. correctly rejected).

- Error codes: `corner-clip` ×336, `glow-gap-plate` ×252, `deep-dish-bezel` ×112
- Warning codes: `few-commands` ×523, `insert-boss` ×518, `xda-not-kit` ×253, `icon-caps` ×243, `clear-caps` ×156, `graphite-not-kit` ×95, `led-count` ×60, `smoke-glow` ×59, `side-screws-thin` ×34, `thin-tilt` ×24

## SVG output

| render | stub | renders | min bytes | avg bytes | max bytes |
|---|---|---|---|---|---|
| renderTop | - | 1889 | 13716 | 20264 | 26205 |
| renderTop+dims | - | 1889 | 15010 | 21229 | 27116 |
| renderSide | - | 1889 | 7895 | 11675 | 14955 |
| renderExploded | - | 1889 | 24724 | 39273 | 44925 |

Colours not in `FB.catalog.palette` (info only; contract says renderers read palette colours): `#ffc766` ×89431, `#be8724` ×29798, `#de9c22` ×29798, `#d5d8d7` ×23094, `#bec1c0` ×23094, `#273f33` ×14899, `#cdefde` ×14899, `#7a8186` ×13223, `#c2c5c4` ×13013, `#a4a7a8` ×11547, `#a2a5a6` ×11547, `#bbbebe` ×11547

## Geometry per layout

Assumptions: cap footprint 18.2 mm, switch housing 15.6 mm, knob Ø18, EC11 body 12 mm, OLED board 38×12 under the window (glass edge aligned, header end either side), XIAO 17.8×21 on the underside at an edge, insert boss Ø8.7. Top-side parts need ≥ 1 mm to each other and to the shell outline; under-plate parts need ≥ 2.3 mm (wall + print tolerance) to the outline.

| layout | content W×H | min top clearance | worst edge distance (any bezel/corner) | OLED board | XIAO (underside) | insert corners b6 / b9 / b12 (worst corner radius) |
|---|---|---|---|---|---|---|
| stratum9 | 57.15×79.15 | 2.42 (key3–dial1) | 2.46 (key7 cap, b6/r16) | header→right ok | back @ 19.75 **under OLED** | 2/4 / 4/4 / 4/4 |
| mirror9 | 57.15×79.15 | 2.42 (key1–dial1) | 2.46 (key7 cap, b6/r16) | header→left ok | back @ 19.75 **under OLED** | 2/4 / 4/4 / 4/4 |
| pocket6 | 57.15×60.1 | 2.42 (key3–dial1) | 2.46 (key4 cap, b6/r16) | header→right ok | back @ 19.75 **under OLED** | 2/4 / 4/4 / 4/4 |
| stagger9 | 57.15×86.15 | 4.15 (dial1–oled) | 2.46 (key7 cap, b6/r16) | header→right ok | back @ 19.75 **under OLED** | 4/4 / 4/4 / 4/4 |
| twin9 | 57.15×79.15 | 2.42 (key1–dial1) | 2.46 (key7 cap, b6/r16) | none | back @ 19.75 | 2/4 / 4/4 / 4/4 |
| wide9 | 95.75×57.15 | 4.23 (key3–oled) | 2.46 (key1 cap, b6/r16) | header→right ok | back @ 56 **under OLED** | 2/4 / 4/4 / 4/4 |
| console4 | 76.2×41.05 | 2 (dial1–oled) | 2.46 (key4 cap, b6/r16) | header→right ok | back @ 29.25 **under OLED** | 4/4 / 4/4 / 4/4 |

## Hard failures (0)

None.

## Warnings (33)

### `insert-boss` ×20 — geometry (shell)
- stratum9 bezel 6 corner 4: only 2/4 corners fit a Ø8.7 insert boss (Ø4.7 hole + 2 wall) clear of parts — FB.check approves it
- stratum9 bezel 6 corner 8: only 2/4 corners fit a Ø8.7 insert boss (Ø4.7 hole + 2 wall) clear of parts — FB.check approves it
- stratum9 bezel 6 corner 12: only 2/4 corners fit a Ø8.7 insert boss (Ø4.7 hole + 2 wall) clear of parts

### `layout-no-spare-gpio` ×7 — catalog contract
- stratum9 uses 11/11 GPIO: zero spare pins for fixes (e.g. encoder push, LED level shifting)
- mirror9 uses 11/11 GPIO: zero spare pins for fixes (e.g. encoder push, LED level shifting)
- pocket6 uses 11/11 GPIO: zero spare pins for fixes (e.g. encoder push, LED level shifting)

### `xiao-under-oled` ×6 — geometry (layout)
- stratum9: XIAO only fits under the OLED board (back edge, x=19.75); trim XIAO pins flush and raise the OLED on its header
- mirror9: XIAO only fits under the OLED board (back edge, x=19.75); trim XIAO pins flush and raise the OLED on its header
- pocket6: XIAO only fits under the OLED board (back edge, x=19.75); trim XIAO pins flush and raise the OLED on its header

## How to read this

- `checker-gap:*` = FB.check said ok but the geometry check found a physical problem: constraints.js should reject or warn.
- `geometry (shell)` warnings list every layout × bezel × corner combination with a problem, whether or not FB.check approves it.
- `[stub]` = the renderer file still says it is a stub; re-run after Agents A/C land.
