# Frostbite Studio contract

Note: Studio is the design explorer from earlier concepts. The final design has no LEDs and is defined by [`design.json`](../design.json).

Frostbite is a Hack Club Hackpad macropad that shows the status of coding agents and ML training runs.
The base design has 3×3 keys, a 0.91" OLED and an EC11 dial along the top, and a matte black shell with
the top plate floating over a glowing light gap. The top two rows are "agent slots" whose frosted caps
glow a status colour. The bottom row holds the white "command" keys: Approve, Talk, Stop.

This folder is a static page that draws permutations of Frostbite in code.

## Rules

- Plain browser JS with no build step and no npm packages in shipped files. Node is fine for tests.
- Every module uses this wrapper so it runs in a classic `<script>` and under Node `require`:
  ```js
  (function (root) {
    const FB = root.FB = root.FB || {};
    // ... define FB.something ...
    if (typeof module !== "undefined" && module.exports) module.exports = FB.something;
  })(typeof window !== "undefined" ? window : globalThis);
  ```
- Load order: `dims.js`, `layouts.js`, `catalog.js`, `constraints.js`, `render-top.js`, `render-side.js`,
  `app.js`. Node tests require them in the same order.
- The page may load only Google Fonts and scripts from cdnjs/jsdelivr/unpkg. No `fetch()` of remote URLs.
- All units are millimetres unless named otherwise.

## Data model

`FB.dims` (dims.js) holds real part dimensions. Sources are in `../docs/DIMENSIONS.md`.

`FB.layouts` (layouts.js) is an array of layout objects, and `FB.layoutById(id)` returns one:
```
{ id, name, blurb,
  W, H,                       // content area size. Origin top-left. The bezel is added outside it.
  keys:  [{ x, y, role }],    // x,y = top-left of a 19.05 mm key cell; role "agent" | "command"
  dials: [{ x, y }],          // dial centre
  oled:  { x, y, w, h } | null, // visible display window
  pins:  { matrix, dial, oled, led },  // GPIO used; XIAO RP2040 has 11
  matrix: "3×3",              // human label
  dialPress: boolean }        // is the encoder push wired into the matrix
```

Every module takes this design spec:
```js
{
  layout: "stratum9",          // id from FB.layouts
  shell: "black",              // black | iced | milk | glacier | smoke | lilac | mint
  texture: "satin",            // satin | layer-lines | speckle
  plate: "floating",           // floating | flush | deep-dish | tray
  glowColor: "ice",            // ice | white | cyan | lavender | mint | warm
  glowPlace: "gap",            // gap | band | base | none
  corner: 12,                  // 4 | 8 | 12 | 16  (outer corner radius)
  bezel: 9,                    // 6 | 9 | 12  (shell wall around the content area)
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
Statuses: idle (white), run (blue, agent working), done (green), needs (amber, waiting on you),
error (red, failed / NaN loss).

`FB.catalog` (catalog.js) holds the option lists, display names, colour palettes, `defaultSpec`, `presets`
and `randomSpec(lockedAxes, rng)`. Renderers read colours from `FB.catalog.palette`.

`FB.check(spec)` (constraints.js) returns:
```
{ ok: boolean,                         // false if any error
  errors:   [{ code, msg }],           // breaks a Hackpad rule or can't physically work
  warnings: [{ code, msg }],           // works but risky / looks wrong
  extras:   [{ item, qty, why }],      // things to buy outside the kit
  stats: { pins, pinsMax: 11, switches, encoders, leds, ledsKit: 16, oled,
           pcb: { w, h }, shell: { w, h, height } } }
```

## Renderers

- `FB.renderTop(spec, opts)` (render-top.js): bird's-eye view to scale. `opts`: `t` (animation tick that
  rotates statuses), `idPrefix` (unique per SVG on the page), `dims` (draw dimension lines), `label`.
- `FB.renderSide(spec, opts)` (render-side.js): side elevation, front on the left, tilt applied.
- `FB.renderExploded(spec, opts)` (render-side.js): exploded stack of the sandwich case.
- Each returns a complete `<svg>` string with `viewBox`, `role="img"` and an `aria-label`, and no `NaN` or
  `undefined`. All `id`s start with `opts.idPrefix` so many SVGs can share one page.

## Hackpad constraints

- PCB ≤ 100 × 100 mm, 2 layers. Case ≤ 200 × 200 × 100 mm, fully 3D printed: no acrylic, laser-cut or CNC.
- MCU is the Seeed XIAO RP2040: 11 GPIO (D0–D10). OLED uses I²C on D4/D5. Analog only on D0–D3.
- Kit: 16 MX switches (Gateron Yellow KS-3, linear), 16 white blank DSA caps, 2 EC11E encoders with push,
  1 × 0.91" 128×32 I²C OLED (pin order GND-VCC-SCL-SDA), 16 SK6812 MINI-E LEDs, 20 1N4148 diodes,
  6 M3×16 screws, 6 M3 heat-set inserts. Extra parts are allowed if bought with your own money.
- Leave about 0.2–0.4 mm tolerance where printed parts meet the PCB.
- Sandwich mount (bottom shell + plate), XIAO on the PCB underside per the Hackpad guide.

The studio is a concept model. Its width and depth match `design.json`, but its heights do not (43.4 mm tall against 49.5 mm for the CAD assembly with keycaps and knob). Use `CAD/` for real heights.
