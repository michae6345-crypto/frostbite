(function (root) {
  const FB = root.FB = root.FB || {};
  // FB.check(spec) -> { ok, errors, warnings, extras, stats }, see CONTRACT.md.
  // Errors   = breaks a Hackpad rule or cannot physically work.
  // Warnings = builds fine but is risky, looks off, or needs parts outside the kit.
  // Extras   = things to buy with your own money.

  const KIT = { pins: 11, switches: 16, caps: 16, encoders: 2, oled: 1, leds: 16, diodes: 20, screws: 6, inserts: 6 };
  const LIMIT = { pcb: 100, shellW: 200, shellH: 200, shellZ: 100, pcbMargin: 2 };
  const GLOW_LEDS = 4;      // LEDs that light the gap / band / base
  const RING_LEDS = 4;      // LEDs under each ring-lit knob (they share the LED data chain: no extra pin)

  const D = FB.dims;
  const NOT_PRINTED = /acrylic|perspex|plexi|laser|\bcnc\b|machined|milled|lasercut|laser-cut/i;
  const FREE_TEXT = { wordmarkText: true, statuses: true };

  const r1 = (x) => Math.round(x * 10) / 10;
  const plural = (n, one, many) => `${n} ${n === 1 ? one : (many || one + "s")}`;

  function normalize(specIn) {
    const s = { ...FB.catalog.defaultSpec };
    const src = specIn || {};
    for (const k of Object.keys(src)) if (src[k] !== undefined && src[k] !== null) s[k] = src[k];
    const opts = FB.catalog.options;
    for (const k of Object.keys(opts)) {
      if (typeof opts[k][0] === "number" && typeof s[k] === "string" && s[k].trim() !== "" && !isNaN(Number(s[k]))) s[k] = Number(s[k]);
    }
    return s;
  }

  // Estimated height, desk to highest point:
  //   pcbTop   = floor + XIAO (on the PCB underside) + 1 mm air + PCB
  //   lift     = 3 mm when the plate floats on standoffs above the shell rim, else 0
  //   plateTop = pcbTop + lift + switchHeightBelowPlate
  //   capTop   = plateTop + switchHeightAbovePlate + cap height. Ignores stem overlap, so it reads a little high.
  //   rimTop   = plateTop + 8 for deep-dish, + 2 for tray, plateTop for flush, pcbTop + 5 for floating
  //   dialTop  = pcbTop + lift + EC11 shaft + 1 mm knob crown
  //   height   = max(capTop, rimTop, dialTop) + depth × tan(tilt). The dials sit at the back, the high end.
  function heightModel(s, L, depth) {
    const minWall = D.minWall, xiaoT = D.xiao.t, pcbT = D.pcbThickness;
    const below = D.switchHeightBelowPlate, above = D.switchHeightAbovePlate;
    const capH = s.capProfile === "XDA" ? D.capHeightXDA : D.capHeightDSA;
    const shaft = D.ec11.shaftAbovePcb;
    const pcbTop = minWall + xiaoT + 1 + pcbT;
    const lift = s.plate === "floating" ? 3 : 0;
    const plateTop = pcbTop + lift + below;
    const capTop = plateTop + above + capH;
    const rimTop = s.plate === "deep-dish" ? plateTop + 8
      : s.plate === "tray" ? plateTop + 2
      : s.plate === "flush" ? plateTop
      : pcbTop + 5;
    const hasDial = L && L.dials && L.dials.length > 0;
    const dialTop = hasDial ? pcbTop + lift + shaft + 1 : 0;
    const tilt = Number(s.tilt) || 0;
    const rise = depth * Math.tan(tilt * Math.PI / 180);
    const front = Math.max(capTop, rimTop);
    const back = Math.max(front, dialTop) + rise;
    return { pcbTop: r1(pcbTop), lift, plateTop: r1(plateTop), capTop: r1(capTop), rimTop: r1(rimTop),
             dialTop: r1(dialTop), rise: r1(rise), front: r1(front), height: r1(back) };
  }

  FB.check = function check(specIn) {
    const s = normalize(specIn);
    const errors = [], warnings = [], extras = [];
    const err = (code, msg) => errors.push({ code, msg });
    const warn = (code, msg) => warnings.push({ code, msg });
    const buy = (item, qty, why) => { if (qty > 0) extras.push({ item, qty, why }); };

    const opts = FB.catalog.options;
    for (const axis of Object.keys(opts)) {
      if (!opts[axis].includes(s[axis])) {
        err("bad-value", `"${s[axis]}" is not a valid ${axis}. Choose one of: ${opts[axis].join(", ")}.`);
      }
    }
    for (const k of Object.keys(s)) {
      if (FREE_TEXT[k]) continue;
      const v = s[k];
      if ((typeof v === "string" && NOT_PRINTED.test(v)) || NOT_PRINTED.test(k) && v) {
        err("not-printed", `${k}: "${v}" needs acrylic, laser cutting or CNC. Hackpad cases must be fully 3D printed.`);
      }
    }

    const L = FB.layoutById(s.layout);
    const keys = L.keys;
    const agentKeys = keys.filter(k => k.role === "agent").length;
    const cmdKeys = keys.length - agentKeys;
    const dials = L.dials.length;
    const oleds = Array.isArray(L.oleds) ? L.oleds.length : (L.oled ? 1 : 0);
    const P = L.pins;
    const pins = P.matrix + P.dial + P.oled + P.led;
    const bezel = Number(s.bezel) || 0, corner = Number(s.corner) || 0, tilt = Number(s.tilt) || 0;
    const pcb = { w: r1(L.W + 2 * LIMIT.pcbMargin), h: r1(L.H + 2 * LIMIT.pcbMargin) };
    const shellW = r1(L.W + 2 * (bezel + D.sideWallExtra)), shellD = r1(L.H + 2 * bezel);
    const hm = heightModel(s, L, shellD);
    const glowOn = s.glowPlace === "gap" || s.glowPlace === "band" || s.glowPlace === "base";
    const ringlit = s.knob === "ringlit";
    const leds = keys.length + (glowOn ? GLOW_LEDS : 0) + (ringlit ? RING_LEDS * dials : 0);
    const profile = s.capProfile === "XDA" ? "XDA" : "DSA";

    // Hackpad limits
    if (pins > KIT.pins) {
      err("pins", `Needs ${pins} GPIO (matrix ${P.matrix}, dials ${P.dial}, OLED ${P.oled}, LEDs ${P.led}) but the XIAO RP2040 has ${KIT.pins} (D0–D10).`);
    }
    if (pcb.w > LIMIT.pcb || pcb.h > LIMIT.pcb) {
      err("pcb-size", `PCB would be ${pcb.w} × ${pcb.h} mm (content plus ${LIMIT.pcbMargin} mm margin each side); Hackpad PCBs must fit in ${LIMIT.pcb} × ${LIMIT.pcb} mm.`);
    }
    if (shellW > LIMIT.shellW || shellD > LIMIT.shellH) {
      err("shell-size", `Case footprint ${shellW} × ${shellD} mm is over the ${LIMIT.shellW} × ${LIMIT.shellH} mm Hackpad limit.`);
    }
    if (hm.height > LIMIT.shellZ) {
      err("shell-height", `Case is about ${hm.height} mm tall; the Hackpad limit is ${LIMIT.shellZ} mm.`);
    }
    if (oleds > KIT.oled) {
      err("oled-count", `${oleds} OLEDs: the 0.91" modules share one fixed I²C address (0x3C) on D4/D5, so a second one cannot be told apart. Use one OLED.`);
    }
    // Extra switches and encoders can be bought. Their real limit is the 11 GPIO, checked above.
    if (keys.length > KIT.switches) {
      warn("switches-extra", `${keys.length} switches; the kit has ${KIT.switches}. Buy ${keys.length - KIT.switches} more Gateron Yellow KS-3 (and caps).`);
      buy("Gateron Yellow KS-3 switches", keys.length - KIT.switches, `Kit includes ${KIT.switches}.`);
    }
    if (keys.length > KIT.diodes) buy("1N4148 diodes", keys.length - KIT.diodes, `Kit includes ${KIT.diodes}; one per switch.`);
    if (dials > KIT.encoders) {
      warn("encoders-extra", `${dials} encoders; the kit has ${KIT.encoders}. Extra EC11E encoders are cheap, but each needs 2 more GPIO.`);
      buy("EC11E rotary encoders with push", dials - KIT.encoders, `Kit includes ${KIT.encoders}.`);
    }

    // Physical rules
    if (s.glowPlace === "gap" && s.plate !== "floating") {
      err("glow-gap-plate", `Gap glow needs the floating plate: a ${FB.catalog.valueLabel("plate", s.plate).toLowerCase()} plate leaves no gap for light to escape. Use band or base glow instead.`);
    }
    // Exposed top screws go through the plate into a heat-set insert in the shell wall. The wall must hold
    // the insert hole plus a printed wall on each side, and fit the M3 head with ~1 mm around it.
    const insertNeed = Math.max(D.heatSetInsert.holeDiameter + 2 * D.minWall, D.m3Head + 2);
    if (s.screws === "top" && bezel < insertNeed) {
      err("screws-top-bezel", `Exposed top screws need a bezel of at least ${r1(insertNeed)} mm (Ø${D.heatSetInsert.holeDiameter} mm insert hole + ${D.minWall} mm walls); this bezel is ${bezel} mm. Use 9 mm or more, or hide the screws.`);
    }
    if (s.plate === "deep-dish" && bezel < 9) {
      err("deep-dish-bezel", `Deep-dish walls rise 8 mm above the plate and need a bezel of at least 9 mm to be printable and stiff; this bezel is ${bezel} mm.`);
    }
    if (corner > bezel + 4) {
      err("corner-clip", `A ${corner} mm corner radius with a ${bezel} mm bezel cuts into the corner keys and OLED. Keep the radius ≤ bezel + 4 mm (${bezel + 4} mm), or widen the bezel.`);
    }

    // Warnings
    if (s.shell === "smoke" && glowOn) {
      warn("smoke-glow", `Smoke PETG absorbs most light, so the ${FB.catalog.valueLabel("glowPlace", s.glowPlace).toLowerCase()} glow will look dim. Run those LEDs brighter or pick a lighter shell.`);
    }
    if (s.agentCap === "clear") {
      warn("clear-caps", "Clear agent caps show the switch housing, stem and the bare LED hotspot instead of an even glow.");
    }
    if (leds > KIT.leds) {
      warn("led-count", `${leds} LEDs (${keys.length} keys${glowOn ? ` + ${GLOW_LEDS} ${s.glowPlace}` : ""}${ringlit ? ` + ${RING_LEDS * dials} ring` : ""}) but the kit has ${KIT.leds} SK6812 MINI-E. Buy ${leds - KIT.leds} more; they chain on the same data pin.`);
      buy("SK6812 MINI-E LEDs", leds - KIT.leds, `${leds} needed, kit has ${KIT.leds}.`);
    }
    if (profile === "XDA") {
      warn("xda-not-kit", `The kit caps are DSA. XDA caps for all ${keys.length} keys must be bought.`);
    }
    if (s.commandCap === "graphite" && cmdKeys > 0) {
      warn("graphite-not-kit", "Graphite command caps are not in the kit (it only has white).");
    }
    if (s.legends === "icons") {
      warn("icon-caps", cmdKeys > 0
        ? "Icon legends need relegendable caps (clear cover over a printed insert) or 3D-printed caps with embossed icons; kit caps are blank."
        : "This layout has no command keys, so icons go on the agent slots: use relegendable caps with translucent printed inserts so status colour still shows.");
    }
    if (tilt >= 8 && bezel <= 6) {
      warn("thin-tilt", "An 8° wedge with a 6 mm bezel makes the back wall look like a thin blade. Use a 9 mm bezel or 4° tilt.");
    }
    const bossOd = D.heatSetInsert.holeDiameter + 2 * D.minWall;
    if (bezel < bossOd) {
      warn("insert-boss", `A ${bezel} mm bezel can't hold a Ø${r1(bossOd)} mm heat-set insert boss in every corner. Put the inserts through mounting holes in the PCB, or use a 9 mm bezel.`);
    }
    if (s.screws === "side" && bezel < D.heatSetInsert.length + D.minWall + D.printTolerance) {
      warn("side-screws-thin", `Side screws in a ${bezel} mm wall leave little room around the ${D.heatSetInsert.length} mm-long inserts. It prints, but the wall may bulge.`);
    }
    if (cmdKeys < 3) {
      if (L.dialPress) {
        warn("few-commands", `${L.name} has ${cmdKeys ? plural(cmdKeys, "command key") : "no command keys"}: Approve moves to the dial press; Talk and Stop become dial gestures (long-press, double-press).`);
      } else {
        warn("few-commands", `${L.name} has ${cmdKeys ? plural(cmdKeys, "command key") : "no command keys"} and its dial pushes are not wired (all ${KIT.pins} GPIO used): Approve, Talk and Stop become long-presses on agent slots and dial gestures.`);
      }
    }
    if (s.wordmark !== "none") {
      const text = String(s.wordmarkText == null ? "" : s.wordmarkText);
      if (!text.trim()) {
        warn("wordmark-empty", "Wordmark is on but the text is empty.");
      } else {
        // ~5 mm cap height embossed letters are ~3.5 mm wide each; leave 10 mm at each end.
        const room = s.wordmark === "front" ? shellW - 20 : Math.max(L.W * 0.6, 30);
        const maxChars = Math.max(1, Math.floor(room / 3.5));
        if (text.length > maxChars) warn("wordmark-long", `"${text}" is ${text.length} characters; about ${maxChars} fit on the ${s.wordmark} at a legible size.`);
      }
    }

    // Extras
    const finish = { frosted: "Frosted", clear: "Clear", milky: "Milky" }[s.agentCap] || "Translucent";
    const iconsOnAgents = s.legends === "icons" && cmdKeys === 0;
    if (agentKeys > 0 && !iconsOnAgents) {
      buy(`${finish} translucent ${profile} keycaps (blank)`, agentKeys, "Kit caps are opaque white; agent slots need translucent caps for status glow.");
    }
    if (s.legends === "icons") {
      const q = cmdKeys > 0 ? cmdKeys : agentKeys;
      buy(`Relegendable ${profile} keycaps (clear cover + printed insert), or print icon caps`, q,
        cmdKeys > 0 ? "Icons on Approve / Talk / Stop." : "Icons on the agent slots (no command row).");
    } else if (cmdKeys > 0) {
      if (s.commandCap === "graphite") buy(`Graphite ${profile} keycaps (blank)`, cmdKeys, "Kit caps are white only.");
      else if (s.commandCap !== "white") buy(`${FB.catalog.valueLabel("commandCap", s.commandCap)} ${profile} keycaps (blank)`, cmdKeys, "Kit caps are plain white.");
      else if (profile === "XDA") buy("White blank XDA keycaps", cmdKeys, "Kit caps are DSA.");
    }
    if (dials > 0) {
      if (s.knob === "knurled-alu") buy("Knurled aluminium knob, 6 mm D-shaft", dials, "Bought machined part (not part of the printed case).");
      else if (s.knob === "soft-white") buy("Soft-touch white knob, 6 mm D-shaft (or print in white PETG)", dials, "Not in the kit.");
      else if (s.knob === "ringlit") {
        buy("Clear knob or light-pipe ring for EC11 (or print in clear PETG)", dials, `Carries light from ${RING_LEDS} LEDs per dial around the knob.`);
      }
      // frosted and puck knobs are printed: covered by filament below.
    }
    const clearParts = [];
    if (s.glowPlace === "gap") clearParts.push("gap spacer");
    if (s.glowPlace === "band") clearParts.push("shell band");
    if (s.glowPlace === "base") clearParts.push("base diffuser ring");
    if (dials > 0 && s.knob === "frosted") clearParts.push("frosted knob");
    if (dials > 0 && s.knob === "ringlit") clearParts.push("knob light ring");
    if (clearParts.length) buy("Clear / natural PETG filament (~50 g)", 1, `For the ${clearParts.join(", ")}.`);
    if (s.screws === "side") buy("M3 × 8 button-head screws", KIT.screws, "Kit M3 × 16 screws are too long to go sideways through the wall.");
    if (oleds > 0 && s.oledColor === "blue") buy('0.91" 128×32 I²C OLED, blue (GND-VCC-SCL-SDA)', 1, "Only if your kit module is white.");

    const stats = {
      pins, pinsMax: KIT.pins, switches: keys.length, encoders: dials, leds, ledsKit: KIT.leds, oled: oleds,
      pcb, shell: { w: shellW, h: shellD, height: hm.height },
      agentKeys, commandKeys: cmdKeys, stack: hm
    };
    return { ok: errors.length === 0, errors, warnings, extras, stats };
  };

  FB.check.rules = {
    "bad-value":        { level: "error", summary: "Value is not one of the catalog options." },
    "not-printed":      { level: "error", summary: "Acrylic, laser-cut or CNC parts are not allowed; case must be 3D printed." },
    "pins":             { level: "error", summary: "More GPIO than the XIAO RP2040's 11." },
    "pcb-size":         { level: "error", summary: "PCB (content + 2 mm margin) over 100 × 100 mm." },
    "shell-size":       { level: "error", summary: "Case footprint over 200 × 200 mm." },
    "shell-height":     { level: "error", summary: "Case taller than 100 mm." },
    "oled-count":       { level: "error", summary: "More than one OLED on the single I²C address." },
    "glow-gap-plate":   { level: "error", summary: "Gap glow needs a floating plate." },
    "screws-top-bezel": { level: "error", summary: "Exposed top screws need a bezel ≥ 9 mm for heat-set inserts." },
    "deep-dish-bezel":  { level: "error", summary: "Deep-dish plate needs a bezel ≥ 9 mm." },
    "corner-clip":      { level: "error", summary: "Corner radius > bezel + 4 mm clips keys / OLED." },
    "switches-extra":   { level: "warning", summary: "More than 16 switches: buy extras." },
    "encoders-extra":   { level: "warning", summary: "More than 2 encoders: buy extras." },
    "smoke-glow":       { level: "warning", summary: "Smoke shell dims the ambient glow." },
    "clear-caps":       { level: "warning", summary: "Clear agent caps show the switch housing." },
    "led-count":        { level: "warning", summary: "More than the 16 kit LEDs." },
    "xda-not-kit":      { level: "warning", summary: "XDA caps are not in the kit." },
    "graphite-not-kit": { level: "warning", summary: "Graphite caps are not in the kit." },
    "icon-caps":        { level: "warning", summary: "Icon legends need relegendable or printed caps." },
    "thin-tilt":        { level: "warning", summary: "8° tilt with a 6 mm bezel looks thin." },
    "side-screws-thin": { level: "warning", summary: "Side screws in a thin wall." },
    "insert-boss":      { level: "warning", summary: "Bezel too thin for corner heat-set insert bosses." },
    "few-commands":     { level: "warning", summary: "Layout has fewer than 3 command keys." },
    "wordmark-empty":   { level: "warning", summary: "Wordmark enabled with no text." },
    "wordmark-long":    { level: "warning", summary: "Wordmark text too long to fit legibly." }
  };
  FB.check.heightModel = heightModel;

  if (typeof module !== "undefined" && module.exports) module.exports = FB.check;
})(typeof window !== "undefined" ? window : globalThis);
