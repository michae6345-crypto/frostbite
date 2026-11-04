# Frostbite Studio verification report

Generated 2026-11-04T04:47:48.240Z by `node verify/run.js` (seed 20261103, 500 random specs, Node v24.22.1).

**Result: PASS**: 0 hard failures, 13 warnings.

## Modules

| file | loaded | bytes | note |
|---|---|---|---|
| dims.js | yes | 5292 |  |
| layouts.js | yes | 3533 |  |
| catalog.js | yes | 18942 |  |
| constraints.js | yes | 17063 |  |
| render-top.js | yes | 31953 |  |
| render-side.js | yes | 53014 |  |

## Test set

1889 specs: 37 preset, 1344 exhaustive, 500 random, 8 edge cases. Exhaustive = layout × plate × glowPlace × bezel × corner with other axes at defaultSpec. Edge-case specs (empty statuses, `&<>` in wordmark, extremes) only produce warnings.

## Summary

| check family | checks | hard | soft | status |
|---|---|---|---|---|
| modules | 6 | 0 | 0 | pass |
| catalog contract | 130 | 0 | 7 | warn |
| spec validity | 10205 | 0 | 0 | pass |
| harness self-test | 10 | 0 | 0 | pass |
| FB.check shape | 3770 | 0 | 0 | pass |
| FB.check limits | 12840 | 0 | 0 | pass |
| presets pass | 37 | 0 | 0 | pass |
| geometry vs FB.check | 1881 | 0 | 0 | pass |
| renderTop | 4031 | 0 | 0 | pass |
| renderSide | 1881 | 0 | 0 | pass |
| renderExploded | 1881 | 0 | 0 | pass |
| edge cases | 32 | 0 | 0 | pass |
| geometry (layout) | 7 | 0 | 6 | warn |
| geometry (shell) | 84 | 0 | 0 | pass |

## FB.check outcomes

Strict specs checked: 1314 ok, 567 rejected (0 rejected specs also have geometry issues, i.e. correctly rejected).

- Error codes: `corner-clip` ×336, `glow-gap-plate` ×252, `deep-dish-bezel` ×112
- Warning codes: `few-commands` ×523, `insert-boss` ×518, `xda-not-kit` ×253, `icon-caps` ×243, `clear-caps` ×156, `graphite-not-kit` ×95, `led-count` ×60, `smoke-glow` ×38, `side-screws-thin` ×34, `thin-tilt` ×24

## SVG output

| render | renders | min bytes | avg bytes | max bytes |
|---|---|---|---|---|
| renderTop | 1889 | 13717 | 19789 | 26206 |
| renderTop+dims | 1889 | 15014 | 20754 | 27120 |
| renderSide | 1889 | 7846 | 11537 | 14790 |
| renderExploded | 1889 | 24622 | 39077 | 44789 |

Colours not in `FB.catalog.palette` (info only; contract says renderers read palette colours): `#ffc766` ×88383, `#be8724` ×29798, `#de9c22` ×29798, `#aeaeac` ×22512, `#9c9c9b` ×22512, `#273f33` ×14899, `#cdefde` ×14899, `#7a8186` ×13223, `#9f9f9e` ×12687, `#888988` ×11256, `#868787` ×11256, `#999a99` ×11256

## Geometry per layout

Assumptions: cap footprint 18.2 mm, switch housing 15.6 mm, knob Ø18, EC11 body 12 mm, OLED board 38×12 under the window (glass edge aligned, header end either side), XIAO 17.8×21 on the underside at an edge, insert boss Ø8.7. Top-side parts need ≥ 1 mm to each other and to the shell outline; under-plate parts need ≥ 2.3 mm (wall + print tolerance) to the outline.

| layout | content W×H | min top clearance | worst edge distance (any bezel/corner) | OLED board | XIAO (underside) | insert corners b6 / b9 / b12 (worst corner radius) |
|---|---|---|---|---|---|---|
| stratum9 | 57.15×79.15 | 2.42 (key3–dial1) | 3.79 (key7 cap, b6/r16) | header→right ok | back @ 19.75 **under OLED** | 4/4 / 4/4 / 4/4 |
| mirror9 | 57.15×79.15 | 2.42 (key1–dial1) | 3.79 (key7 cap, b6/r16) | header→left ok | back @ 19.75 **under OLED** | 4/4 / 4/4 / 4/4 |
| pocket6 | 57.15×60.1 | 2.42 (key3–dial1) | 3.79 (key4 cap, b6/r16) | header→right ok | back @ 19.75 **under OLED** | 4/4 / 4/4 / 4/4 |
| stagger9 | 57.15×86.15 | 4.15 (dial1–oled) | 3.79 (key7 cap, b6/r16) | header→right ok | back @ 19.75 **under OLED** | 4/4 / 4/4 / 4/4 |
| twin9 | 57.15×79.15 | 2.42 (key1–dial1) | 3.79 (key7 cap, b6/r16) | none | back @ 19.75 | 4/4 / 4/4 / 4/4 |
| wide9 | 95.75×57.15 | 4.23 (key3–oled) | 3.79 (key1 cap, b6/r16) | header→right ok | back @ 56 **under OLED** | 4/4 / 4/4 / 4/4 |
| console4 | 76.2×41.05 | 2 (dial1–oled) | 3.79 (key4 cap, b6/r16) | header→right ok | back @ 29.25 **under OLED** | 4/4 / 4/4 / 4/4 |

## Hard failures (0)

None.

## Warnings (13)

### `layout-no-spare-gpio` ×7, catalog contract
- stratum9 uses 11/11 GPIO: zero spare pins for fixes (e.g. encoder push, LED level shifting)
- mirror9 uses 11/11 GPIO: zero spare pins for fixes (e.g. encoder push, LED level shifting)
- pocket6 uses 11/11 GPIO: zero spare pins for fixes (e.g. encoder push, LED level shifting)

### `xiao-under-oled` ×6, geometry (layout)
- stratum9: XIAO only fits under the OLED board (back edge, x=19.75); trim XIAO pins flush and raise the OLED on its header
- mirror9: XIAO only fits under the OLED board (back edge, x=19.75); trim XIAO pins flush and raise the OLED on its header
- pocket6: XIAO only fits under the OLED board (back edge, x=19.75); trim XIAO pins flush and raise the OLED on its header

## How to read this

- `checker-gap:*` = FB.check said ok but the geometry check found a physical problem: constraints.js should reject or warn.
- `geometry (shell)` warnings list every layout × bezel × corner combination with a problem, whether or not FB.check approves it.
