# Frostbite Studio — shared contract

Frostbite is a Hack Club Hackpad macropad that shows the status of AI coding agents and ML training runs.
Base design: Stratum-style 3×3 keys, a 0.91" OLED and an EC11 dial along the top, frosted iced-PETG
shell, top plate floating over a glowing light gap. The top two rows of keys are "agent slots" whose
frosted caps glow a status color. The bottom row holds the white "command" keys: Approve, Talk, Stop.

This folder becomes a static web page (published as a claude.ai Artifact) that explores many
permutations of Frostbite, drawn in code. No AI image credits are used.

## Hard rules for every agent

- Plain browser JS, no build step, no npm packages in shipped files. Node is fine for tests.
- Every module uses this wrapper so it runs both in the browser (classic `<script>`) and under Node `require`:
  ```js
  (function (root) {
    const FB = root.FB = root.FB || {};
    // ... define FB.something ...
    if (typeof module !== "undefined" && module.exports) module.exports = FB.something;
  })(typeof window !== "undefined" ? window : globalThis);
  ```
- Browser load order (index.html): `dims.js`, `layouts.js`, `catalog.js`, `constraints.js`,
  `render-top.js`, `render-side.js`, `app.js`. Node tests require them in the same order.
- Only edit the files you own (table below). If another module has a bug or is missing something you need,
  work around it defensively and write the request in your final report. Do not edit their file.
- The page may load only Google Fonts and scripts from cdnjs/jsdelivr/unpkg. No other network requests.
  Everything else ships with the page. No `fetch()` of remote URLs.
- All units are millimetres unless named otherwise.

## File ownership

| File | Owner |
|---|---|
| `CONTRACT.md`, `layouts.js`, `img/` | lead (frozen) |
| `dims.js`, `../docs/DIMENSIONS.md` | Agent F (dimensions) |
| `catalog.js`, `constraints.js`, `test/constraints.test.js` | Agent B (catalog + constraints) |
| `render-top.js` | Agent A (top-down renderer) |
| `render-side.js` | Agent C (side + exploded renderer) |
| `index.html`, `app.js`, `styles.css` | Agent D (page) |
| `../docs/VERIFICATION.md`, `verify/*` | Agent E (verification) |

## Data model

### FB.dims (dims.js)
Real part dimensions. Keys are frozen; values may be corrected by Agent F. See the file.

### FB.layouts (layouts.js) — frozen
`FB.layouts` is an array of layout objects:
```
{ id, name, blurb,
  W, H,                       // content area (PCB-ish) size, mm. Origin top-left. Shell bezel is added outside it.
  keys:  [{ x, y, role }],    // x,y = top-left of a 19.05 mm key cell; role "agent" | "command"
  dials: [{ x, y }],          // dial centre
  oled:  { x, y, w, h } | null, // visible display window
  pins:  { matrix, dial, oled, led },  // GPIO used; XIAO RP2040 has 11
  matrix: "3×3",              // human label
  dialPress: boolean }        // is the encoder push wired into the matrix
```
`FB.layoutById(id)` returns one.

### Design spec (the object every module takes)
```js
{
  layout: "stratum9",          // id from FB.layouts
  shell: "iced",               // iced | milk | glacier | smoke | lilac | mint
  texture: "satin",            // satin | layer-lines | speckle
  plate: "floating",           // floating | flush | deep-dish | tray
  glowColor: "ice",            // ice | white | cyan | lavender | mint | warm
  glowPlace: "gap",            // gap | band | base | none
  corner: 12,                  // 4 | 8 | 12 | 16  (outer corner radius, mm)
  bezel: 9,                    // 6 | 9 | 12  (shell wall around content area, mm)
  knob: "knurled-alu",         // knurled-alu | frosted | soft-white | ringlit | puck
  oledColor: "white",          // white | ice | blue
  capProfile: "DSA",           // DSA | XDA
  agentCap: "frosted",         // frosted | clear | milky
  commandCap: "white",         // white | frost-white | glacier | graphite
  legends: "blank",            // blank | icons
  screws: "hidden",            // hidden | top | side
  wordmark: "front",           // none | front | plate
  wordmarkText: "frostbite",
  tilt: 4,                     // 0 | 4 | 8 degrees
  statuses: ["run","done","run","needs","idle","error"]  // per agent key, cycles if fewer
}
```
Status meanings: idle (white), run (blue, agent working), done (green), needs (amber, waiting on you),
error (red, failed / NaN loss).

`FB.catalog` (catalog.js) holds the option lists, display names, colour palettes, `FB.catalog.defaultSpec`,
`FB.catalog.presets` (named curated specs) and `FB.catalog.randomSpec(lockedAxes, rng)`.
Renderers must read colours from `FB.catalog.palette`, never hard-code their own palette, so the page stays consistent.

### Constraint result (constraints.js)
`FB.check(spec)` returns
```
{ ok: boolean,                         // false if any error
  errors:   [{ code, msg }],           // breaks a Hackpad rule or can't physically work
  warnings: [{ code, msg }],           // works but risky / looks wrong
  extras:   [{ item, qty, why }],      // things to buy outside the kit
  stats: { pins, pinsMax: 11, switches, encoders, leds, ledsKit: 16, oled,
           pcb: { w, h }, shell: { w, h, height } } }
```

### Renderers
- `FB.renderTop(spec, opts) -> string` (render-top.js): a complete `<svg>` string, bird's-eye view, to scale.
  `opts`: `{ t: 0 /* animation tick that rotates statuses */, idPrefix: "x1" /* unique per SVG on the page */, dims: false /* draw dimension lines */, label: "" }`.
- `FB.renderSide(spec, opts) -> string` (render-side.js): side elevation, front on the left, tilt applied.
- `FB.renderExploded(spec, opts) -> string` (render-side.js): exploded stack of the sandwich case
  (bottom shell, glow spacer / band, PCB with XIAO on the underside, plate, switches, caps, knob).
- Every SVG sets `viewBox`, has `role="img"` and an `aria-label`, and must not contain `NaN` or `undefined`.
  All `id`s inside an SVG must start with `opts.idPrefix` so many SVGs can share one page.

## Hackpad constraints (source of truth for constraints.js and verification)
- PCB ≤ 100 × 100 mm, 2 layers. Case ≤ 200 × 200 × 100 mm. Case fully 3D printed: no acrylic, laser-cut or CNC.
- MCU must be the Seeed XIAO RP2040: 11 GPIO (D0–D10). OLED uses I²C on D4/D5. Analog only on D0–D3.
- Kit: 16 MX switches (Gateron Yellow KS-3, linear), 16 white blank DSA caps, 2 EC11E encoders with push,
  1 × 0.91" 128×32 I²C OLED (pin order GND-VCC-SCL-SDA), 16 SK6812 MINI-E LEDs, 20 1N4148 diodes,
  6 M3×16 screws, 6 M3 heat-set inserts. Extra parts are allowed but bought with your own money.
- Leave ~0.2–0.4 mm tolerance where printed parts meet the PCB.
- Sandwich mount (bottom shell + plate), XIAO mounted on the PCB underside per the Hackpad guide.
