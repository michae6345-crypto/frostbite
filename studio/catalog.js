(function (root) {
  const FB = root.FB = root.FB || {};
  const options = {
    layout: ["stratum9", "mirror9", "pocket6", "stagger9", "twin9", "wide9", "console4"],
    shell: ["black", "iced", "milk", "glacier", "smoke", "lilac", "mint"],
    texture: ["satin", "layer-lines", "speckle"],
    plate: ["floating", "flush", "deep-dish", "tray"],
    glowColor: ["ice", "white", "cyan", "lavender", "mint", "warm"],
    glowPlace: ["gap", "band", "base", "none"],
    corner: [4, 8, 12, 16],
    bezel: [6, 9, 12],
    knob: ["knurled-alu", "frosted", "soft-white", "ringlit", "puck"],
    oledColor: ["white", "ice", "blue"],
    capProfile: ["DSA", "XDA"],
    agentCap: ["frosted", "clear", "milky"],
    commandCap: ["white", "frost-white", "glacier", "graphite"],
    legends: ["blank", "icons"],
    screws: ["hidden", "top", "side"],
    wordmark: ["none", "front", "plate"],
    tilt: [0, 4, 8]
  };

  const palette = {
    shell: {
      black:   { top: "#26282b", base: "#1b1d1f", edge: "#101112", opacity: 1.0 },
      iced:    { top: "#e8eef1", base: "#d4dde1", edge: "#c3cdd2", opacity: 0.92 },
      milk:    { top: "#f4f4f1", base: "#e2e2dd", edge: "#cfcfc9", opacity: 1.0 },
      glacier: { top: "#dbe9f2", base: "#c4d8e4", edge: "#a9c2d1", opacity: 0.9 },
      smoke:   { top: "#4a4f55", base: "#33373c", edge: "#25282c", opacity: 0.94 },
      lilac:   { top: "#e7e2f2", base: "#d3cce6", edge: "#bdb3d8", opacity: 0.92 },
      mint:    { top: "#e0f0ea", base: "#c9e3d9", edge: "#aed2c4", opacity: 0.92 }
    },
    glow: { ice: "#7fe3ff", white: "#f4fbff", cyan: "#4fdbe6", lavender: "#b9a6ff", mint: "#8ff0c8", warm: "#ffd9a0" },
    status: { idle: "#eef2f5", run: "#3d8bff", done: "#2fbf5b", needs: "#ffb020", error: "#ff4d4f" },
    commandCap: { white: "#f7f7f4", "frost-white": "#eef3f5", glacier: "#d6e6ef", graphite: "#3a3d42" },
    agentCapBase: { frosted: "#f2f6f8", clear: "#e9f3f8", milky: "#f6f6f2" },
    knob: {
      "knurled-alu": { face: "#d9dcde", ring: "#a9afb3" },
      frosted: { face: "#eef3f5", ring: "#c7d1d6" },
      "soft-white": { face: "#f5f5f2", ring: "#d6d6d0" },
      ringlit: { face: "#d9dcde", ring: "#a9afb3" },
      puck: { face: "#e9ecee", ring: "#c9cfd2" }
    },
    oled: { white: "#eef6ff", ice: "#a8ecff", blue: "#5aa7ff" }
  };

  const axisLabels = {
    layout: "Layout", shell: "Shell", texture: "Texture", plate: "Plate", glowColor: "Glow colour",
    glowPlace: "Glow placement", corner: "Corner radius", bezel: "Bezel", knob: "Knob",
    oledColor: "OLED colour", capProfile: "Cap profile", agentCap: "Agent caps", commandCap: "Command caps",
    legends: "Legends", screws: "Screws", wordmark: "Wordmark", wordmarkText: "Wordmark text",
    tilt: "Tilt", statuses: "Agent statuses"
  };

  // valueInfo[axis][value] = { name, desc }
  const valueInfo = {
    layout: Object.fromEntries(FB.layouts.map(L => [L.id, { name: L.name, desc: L.blurb }])),
    shell: {
      black:   { name: "Black", desc: "Opaque matte black PETG. Hides grime, but absorbs stray glow, so test the band first." },
      iced:    { name: "Iced", desc: "Translucent frosted PETG. Pretty, but it shows dirt." },
      milk:    { name: "Milk", desc: "Opaque soft white. Calm, appliance-like." },
      glacier: { name: "Glacier", desc: "Pale blue translucent PETG with deeper edges." },
      smoke:   { name: "Smoke", desc: "Dark translucent grey. Moody, but swallows glow." },
      lilac:   { name: "Lilac", desc: "Lavender-tinted translucent PETG." },
      mint:    { name: "Mint", desc: "Cool mint-tinted translucent PETG." }
    },
    texture: {
      satin:         { name: "Satin", desc: "Smooth textured-sheet finish, even and soft to touch." },
      "layer-lines": { name: "Layer lines", desc: "Honest visible print lines that catch light." },
      speckle:       { name: "Speckle", desc: "Flecked filament, like fresh snow on stone." }
    },
    plate: {
      floating:    { name: "Floating", desc: "Plate hovers over the shell rim on a glowing light gap." },
      flush:       { name: "Flush", desc: "Plate sits level with the shell rim. Clean and simple." },
      "deep-dish": { name: "Deep dish", desc: "Plate sunk inside tall walls that cradle the caps." },
      tray:        { name: "Tray", desc: "Plate in a shallow tray with a low raised lip." }
    },
    glowColor: {
      ice:      { name: "Ice", desc: "Cold aqua-blue glow." },
      white:    { name: "White", desc: "Neutral daylight white." },
      cyan:     { name: "Cyan", desc: "Saturated electric cyan." },
      lavender: { name: "Lavender", desc: "Soft violet glow." },
      mint:     { name: "Mint", desc: "Fresh green-mint glow." },
      warm:     { name: "Warm", desc: "Candle-warm amber white." }
    },
    glowPlace: {
      gap:  { name: "Light gap", desc: "Light spills from the gap under the floating plate." },
      band: { name: "Band", desc: "A clear PETG band runs around the middle of the shell." },
      base: { name: "Base", desc: "Light washes onto the desk from under the base." },
      none: { name: "None", desc: "No ambient glow; only the agent caps light up." }
    },
    corner: {
      4:  { name: "4 mm", desc: "Crisp, nearly square corners." },
      8:  { name: "8 mm", desc: "Gently rounded." },
      12: { name: "12 mm", desc: "Soft pebble corners (Frostbite default)." },
      16: { name: "16 mm", desc: "Very round, pillowy. Needs a 12 mm bezel." }
    },
    bezel: {
      6:  { name: "6 mm", desc: "Thin wall, compact footprint." },
      9:  { name: "9 mm", desc: "Balanced wall; room for heat-set inserts." },
      12: { name: "12 mm", desc: "Chunky wall with lots of shell to glow through." }
    },
    knob: {
      "knurled-alu": { name: "Knurled aluminium", desc: "Bought machined knob with fine knurling." },
      frosted:       { name: "Frosted", desc: "Printed in translucent PETG to match the shell." },
      "soft-white":  { name: "Soft white", desc: "Matte white soft-touch knob." },
      ringlit:       { name: "Ring-lit", desc: "Light-pipe ring under the knob glows with status." },
      puck:          { name: "Puck", desc: "Low wide printed puck, almost flush with the caps." }
    },
    oledColor: {
      white: { name: "White", desc: "Standard white-on-black 0.91\" OLED." },
      ice:   { name: "Ice", desc: "White OLED seen through an ice-tinted window." },
      blue:  { name: "Blue", desc: "Blue-pixel OLED module variant." }
    },
    capProfile: {
      DSA: { name: "DSA", desc: "Low uniform spherical caps (kit profile)." },
      XDA: { name: "XDA", desc: "Wider, flatter tops. Bought separately." }
    },
    agentCap: {
      frosted: { name: "Frosted", desc: "Translucent frosted caps that diffuse status colour evenly." },
      clear:   { name: "Clear", desc: "Crystal caps: vivid colour, switch housing visible." },
      milky:   { name: "Milky", desc: "Dense milky caps with a soft, pastel glow." }
    },
    commandCap: {
      white:         { name: "White", desc: "Kit white DSA caps." },
      "frost-white": { name: "Frost white", desc: "Cool off-white caps." },
      glacier:       { name: "Glacier", desc: "Pale ice-blue caps." },
      graphite:      { name: "Graphite", desc: "Dark grey caps for strong contrast." }
    },
    legends: {
      blank: { name: "Blank", desc: "No legends; position tells you the key." },
      icons: { name: "Icons", desc: "Approve / Talk / Stop icons on the command keys." }
    },
    screws: {
      hidden: { name: "Hidden", desc: "Screwed from underneath; top stays clean." },
      top:    { name: "Exposed top", desc: "Screw heads on the bezel corners, industrial look." },
      side:   { name: "Side", desc: "Screws enter through the shell walls." }
    },
    wordmark: {
      none:  { name: "None", desc: "No text on the case." },
      front: { name: "Front", desc: "Wordmark embossed on the front edge." },
      plate: { name: "Plate", desc: "Wordmark on the top plate beside the keys." }
    },
    tilt: {
      0: { name: "Flat", desc: "Sits flat on the desk." },
      4: { name: "4°", desc: "Gentle typing tilt." },
      8: { name: "8°", desc: "Steep wedge; looks thin with a 6 mm bezel." }
    }
  };

  const labels = {
    status: { idle: "Idle", run: "Working", done: "Done", needs: "Waiting on you", error: "Failed / NaN" },
    axis: axisLabels
  };

  function valueLabel(axis, value) {
    const a = valueInfo[axis];
    const v = a && a[value];
    return v ? v.name : String(value);
  }

  // Configurator groups. `axes` are keys of `options`, `text` lists free-text fields.
  const axesForUI = [
    { id: "layout",   name: "Layout",        axes: ["layout"] },
    { id: "shell",    name: "Shell & light", axes: ["shell", "texture", "glowColor", "glowPlace"] },
    { id: "form",     name: "Plate & form",  axes: ["plate", "corner", "bezel", "tilt"] },
    { id: "controls", name: "Controls",      axes: ["knob", "oledColor"] },
    { id: "caps",     name: "Keycaps",       axes: ["capProfile", "agentCap", "commandCap", "legends"] },
    { id: "details",  name: "Details",       axes: ["screws", "wordmark"], text: ["wordmarkText"] }
  ];

  const defaultSpec = {
    layout: "stratum9", shell: "black", texture: "satin", plate: "floating", glowColor: "ice", glowPlace: "gap",
    corner: 12, bezel: 9, knob: "knurled-alu", oledColor: "white", capProfile: "DSA", agentCap: "frosted",
    commandCap: "white", legends: "blank", screws: "hidden", wordmark: "front", wordmarkText: "frostbite",
    tilt: 4, statuses: ["run", "done", "run", "needs", "idle", "error"]
  };

  function cloneSpec(s) {
    const out = { ...s };
    out.statuses = Array.isArray(s.statuses) ? s.statuses.slice() : defaultSpec.statuses.slice();
    return out;
  }
  const mk = (over) => cloneSpec({ ...defaultSpec, shell: "iced", ...over });

  // All presets must pass FB.check (enforced by test/constraints.test.js).
  const presets = [
    { id: "frostbite", name: "Frostbite", note: "The build: matte black shell, floating plate over an ice-blue light gap.",
      spec: cloneSpec(defaultSpec) },
    { id: "frostbite-halo", name: "Frostbite Halo", note: "The original with a ring-lit dial that glows with the busiest agent.",
      spec: mk({ knob: "ringlit" }) },
    { id: "glacier", name: "Glacier", note: "Pale-blue shell, glacier command caps and an ice-tinted OLED.",
      spec: mk({ shell: "glacier", commandCap: "glacier", oledColor: "ice", corner: 16, bezel: 12 }) },
    { id: "whiteout", name: "Whiteout", note: "Milk shell and white glow: quiet, appliance-white, all soft light.",
      spec: mk({ shell: "milk", glowColor: "white", agentCap: "milky", commandCap: "frost-white", knob: "soft-white" }) },
    { id: "polar-night", name: "Polar Night", note: "Smoke shell with a cyan gap; status colours pop on dark.",
      spec: mk({ shell: "smoke", glowColor: "cyan", commandCap: "graphite", oledColor: "blue", bezel: 12 }) },
    { id: "lilac-haze", name: "Lilac Haze", note: "Lavender shell and lavender glow, dreamy and soft.",
      spec: mk({ shell: "lilac", glowColor: "lavender", commandCap: "frost-white", knob: "frosted" }) },
    { id: "mint-frost", name: "Mint Frost", note: "Mint shell with a mint gap glow, fresh and cool.",
      spec: mk({ shell: "mint", glowColor: "mint", commandCap: "frost-white" }) },
    { id: "deep-dish", name: "Deep Dish", note: "Keys sunk in tall iced walls with a glowing mid-shell band.",
      spec: mk({ plate: "deep-dish", glowPlace: "band", bezel: 12, corner: 12 }) },
    { id: "tray", name: "Tray", note: "Plate in a low-lipped tray; glow pools on the desk below.",
      spec: mk({ plate: "tray", glowPlace: "base", corner: 8 }) },
    { id: "xda-soft", name: "XDA Soft", note: "Wide flat XDA caps, pillow corners and a soft-white knob.",
      spec: mk({ capProfile: "XDA", knob: "soft-white", corner: 16, bezel: 12, agentCap: "milky" }) },
    { id: "icon-caps", name: "Icon Caps", note: "Approve, Talk and Stop get printed icons; no guessing.",
      spec: mk({ legends: "icons" }) },
    { id: "mirror", name: "Mirror", note: "Dial on the left for a mouse-in-right-hand setup.",
      spec: mk({ layout: "mirror9" }) },
    { id: "pocket", name: "Pocket", note: "Just the six agent slots; press the dial to approve.",
      spec: mk({ layout: "pocket6", corner: 8 }) },
    { id: "stagger", name: "Stagger", note: "Columns staggered like a split keyboard for a hand-shaped silhouette.",
      spec: mk({ layout: "stagger9" }) },
    { id: "twin", name: "Twin", note: "Two dials, no OLED: one picks the slot, one scrolls the log.",
      spec: mk({ layout: "twin9" }) },
    { id: "wide", name: "Wide", note: "Landscape: keys left, OLED and dial in a control column.",
      spec: mk({ layout: "wide9", corner: 8 }) },
    { id: "console", name: "Console", note: "Four big agent slots under an OLED flanked by two dials.",
      spec: mk({ layout: "console4", tilt: 8, bezel: 12 }) },
    { id: "exposed-screws", name: "Exposed Screws", note: "Four screw heads on the bezel corners, honest and industrial.",
      spec: mk({ screws: "top", texture: "layer-lines" }) },
    { id: "side-bolt", name: "Side Bolt", note: "Screws through the shell walls keep the top completely clean.",
      spec: mk({ screws: "side", wordmark: "plate" }) },
    { id: "ember-frost", name: "Ember Frost", note: "Milk shell lit warm from below, like snow at sunset.",
      spec: mk({ shell: "milk", glowColor: "warm", glowPlace: "base", agentCap: "milky" }) },
    { id: "crystal", name: "Crystal", note: "Clear agent caps for vivid, jewel-like status colour.",
      spec: mk({ agentCap: "clear", glowColor: "white" }) },
    { id: "flat-ice", name: "Flat Ice", note: "Flush plate, no tilt, a thin glow at the base. Minimal.",
      spec: mk({ plate: "flush", glowPlace: "base", tilt: 0, corner: 8, wordmark: "none" }) },
    { id: "ridge", name: "Ridge", note: "Steep 8° wedge with a chunky bezel; reads like a little console.",
      spec: mk({ tilt: 8, bezel: 12, corner: 16 }) },
    { id: "snowfall", name: "Snowfall", note: "Speckled milk shell, like fresh snow on granite.",
      spec: mk({ shell: "milk", texture: "speckle", glowColor: "white", commandCap: "white" }) },
    { id: "strata", name: "Strata", note: "Visible layer lines turn the light gap into contour lines.",
      spec: mk({ texture: "layer-lines", glowColor: "cyan" }) },
    { id: "hushed", name: "Hushed", note: "No ambient glow; only the agent caps speak.",
      spec: mk({ plate: "flush", glowPlace: "none", knob: "frosted" }) },
    { id: "puck", name: "Puck", note: "A low printed puck dial that almost disappears into the keys.",
      spec: mk({ knob: "puck", corner: 8 }) },
    { id: "blue-hour", name: "Blue Hour", note: "Glacier shell, cyan glow and a blue OLED: the colour of 5 pm in winter.",
      spec: mk({ shell: "glacier", glowColor: "cyan", oledColor: "blue", commandCap: "frost-white" }) },
    { id: "arctic-console", name: "Arctic Console", note: "Console 4 with both dials ring-lit.",
      spec: mk({ layout: "console4", knob: "ringlit", bezel: 12, corner: 12 }) },
    { id: "twin-halo", name: "Twin Halo", note: "Twin dials, both haloed in ice light.",
      spec: mk({ layout: "twin9", knob: "ringlit" }) },
    { id: "lilac-pocket", name: "Lilac Pocket", note: "The six-slot pocket in lilac with a lavender glow.",
      spec: mk({ layout: "pocket6", shell: "lilac", glowColor: "lavender", knob: "frosted", corner: 8 }) },
    { id: "mint-wide", name: "Mint Wide", note: "Landscape mint with a puck dial in the control column.",
      spec: mk({ layout: "wide9", shell: "mint", glowColor: "mint", knob: "puck", corner: 8 }) },
    { id: "graphite-ice", name: "Graphite Ice", note: "Iced shell with graphite command keys for crisp contrast.",
      spec: mk({ commandCap: "graphite" }) },
    { id: "sharp-ice", name: "Sharp Ice", note: "Thin 6 mm bezel and crisp 4 mm corners; as small as Frostbite gets.",
      spec: mk({ bezel: 6, corner: 4 }) },
    { id: "pillow", name: "Pillow", note: "Milk shell, 16 mm corners, XDA caps: soft everywhere.",
      spec: mk({ shell: "milk", corner: 16, bezel: 12, capProfile: "XDA", glowColor: "white", knob: "soft-white" }) },
    { id: "plate-mark", name: "Plate Mark", note: "Wordmark moved onto the plate beside the dial.",
      spec: mk({ wordmark: "plate", commandCap: "glacier" }) },
    { id: "night-shift", name: "Night Shift", note: "Smoke shell and warm base glow for late training runs.",
      spec: mk({ shell: "smoke", glowColor: "warm", glowPlace: "base", commandCap: "graphite", oledColor: "white" }) }
  ];

  // The axis-only rules from constraints.js, so randomSpec works without it. FB.check wins when loaded.
  function basicOk(s) {
    if (s.glowPlace === "gap" && s.plate !== "floating") return false;
    if (s.screws === "top" && s.bezel < 9) return false;
    if (s.plate === "deep-dish" && s.bezel < 9) return false;
    if (s.corner > s.bezel + 4) return false;
    return true;
  }
  function isOk(s) {
    if (typeof FB.check === "function") {
      try { return !!FB.check(s).ok; } catch (e) { return basicOk(s); }
    }
    return basicOk(s);
  }
  function coerce(axis, v) {
    const opts = options[axis];
    if (opts && typeof opts[0] === "number" && typeof v === "string" && v.trim() !== "" && !isNaN(Number(v))) return Number(v);
    return v;
  }
  // locked is { axis: value } or an array/Set of axis names, whose values come from base or defaultSpec.
  function normalizeLocked(locked, base) {
    const out = {};
    if (!locked) return out;
    const src = base || defaultSpec;
    if (Array.isArray(locked) || locked instanceof Set) {
      for (const k of locked) if (src[k] !== undefined) out[k] = coerce(k, src[k]);
      return out;
    }
    for (const k of Object.keys(locked)) if (locked[k] !== undefined && locked[k] !== null) out[k] = coerce(k, locked[k]);
    return out;
  }
  function randomSpec(locked, rng, base) {
    const r = typeof rng === "function" ? rng : Math.random;
    const lock = normalizeLocked(locked, base);
    const MAX_TRIES = 300;
    for (let t = 0; t < MAX_TRIES; t++) {
      const s = cloneSpec(defaultSpec);
      for (const k of Object.keys(options)) {
        if (lock[k] !== undefined) { s[k] = lock[k]; continue; }
        const list = options[k];
        s[k] = list[Math.min(list.length - 1, Math.floor(r() * list.length))];
      }
      if (lock.wordmarkText !== undefined) s.wordmarkText = lock.wordmarkText;
      if (Array.isArray(lock.statuses)) s.statuses = lock.statuses.slice();
      if (isOk(s)) return s;
    }
    return cloneSpec({ ...defaultSpec, ...lock });
  }

  FB.catalog = {
    options, palette, labels, axisLabels, valueInfo, valueLabel, axesForUI,
    defaultSpec, presets, randomSpec
  };
  if (typeof module !== "undefined" && module.exports) module.exports = FB.catalog;
})(typeof window !== "undefined" ? window : globalThis);
