// Plain Node test for catalog.js + constraints.js. Run: node test/constraints.test.js
"use strict";
const path = require("path");
const R = (f) => require(path.join(__dirname, "..", f));
R("dims.js"); R("layouts.js"); R("catalog.js"); R("constraints.js");
const FB = globalThis.FB;

let failures = 0, passes = 0;
function assert(cond, msg) {
  if (cond) { passes++; return; }
  failures++;
  console.error("FAIL: " + msg);
}
const codes = (list) => list.map(x => x.code);
const D = FB.catalog.defaultSpec;
const spec = (over) => ({ ...D, statuses: D.statuses.slice(), ...over });

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function finiteDeep(x, where) {
  if (typeof x === "number") { assert(isFinite(x), `non-finite number at ${where}`); return; }
  if (x && typeof x === "object") for (const k of Object.keys(x)) finiteDeep(x[k], `${where}.${k}`);
}
function checkShape(res, label) {
  assert(typeof res.ok === "boolean", `${label}: ok is boolean`);
  for (const k of ["errors", "warnings", "extras"]) assert(Array.isArray(res[k]), `${label}: ${k} is array`);
  for (const e of res.errors.concat(res.warnings)) assert(typeof e.code === "string" && typeof e.msg === "string" && e.msg.length > 10, `${label}: issue shape ${JSON.stringify(e)}`);
  for (const x of res.extras) assert(typeof x.item === "string" && Number.isFinite(x.qty) && x.qty > 0 && typeof x.why === "string", `${label}: extra shape ${JSON.stringify(x)}`);
  const s = res.stats;
  for (const k of ["pins", "pinsMax", "switches", "encoders", "leds", "ledsKit", "oled"]) assert(Number.isFinite(s[k]), `${label}: stats.${k} finite (${s[k]})`);
  for (const k of ["w", "h"]) assert(Number.isFinite(s.pcb[k]) && s.pcb[k] > 0, `${label}: stats.pcb.${k}`);
  for (const k of ["w", "h", "height"]) assert(Number.isFinite(s.shell[k]) && s.shell[k] > 0, `${label}: stats.shell.${k}`);
  assert(s.pinsMax === 11 && s.ledsKit === 16, `${label}: pinsMax/ledsKit constants`);
  finiteDeep(s, label + ".stats");
  assert(res.ok === (res.errors.length === 0), `${label}: ok matches errors`);
}

// Catalog shape
const C = FB.catalog;
const seedAxes = {
  layout: ["stratum9", "mirror9", "pocket6", "stagger9", "twin9", "wide9", "console4"],
  shell: ["black", "iced", "milk", "glacier", "smoke", "lilac", "mint"], texture: ["satin", "layer-lines", "speckle"],
  plate: ["floating", "flush", "deep-dish", "tray"], glowColor: ["ice", "white", "cyan", "lavender", "mint", "warm"],
  glowPlace: ["gap", "band", "base", "none"], corner: [4, 8, 12, 16], bezel: [6, 9, 12],
  knob: ["knurled-alu", "frosted", "soft-white", "ringlit", "puck"], oledColor: ["white", "ice", "blue"],
  capProfile: ["DSA", "XDA"], agentCap: ["frosted", "clear", "milky"], commandCap: ["white", "frost-white", "glacier", "graphite"],
  legends: ["blank", "icons"], screws: ["hidden", "top", "side"], wordmark: ["none", "front", "plate"], tilt: [0, 4, 8]
};
for (const [axis, vals] of Object.entries(seedAxes)) {
  assert(JSON.stringify(C.options[axis]) === JSON.stringify(vals), `options.${axis} unchanged`);
  assert(typeof C.axisLabels[axis] === "string", `axisLabels.${axis}`);
  for (const v of vals) {
    const info = C.valueInfo[axis] && C.valueInfo[axis][v];
    assert(info && info.name && typeof info.desc === "string", `valueInfo.${axis}.${v}`);
  }
}
for (const k of ["black", "iced", "milk", "glacier", "smoke", "lilac", "mint"]) assert(C.palette.shell[k], `palette.shell.${k}`);
const uiAxes = C.axesForUI.flatMap(g => g.axes);
assert(uiAxes.length === Object.keys(C.options).length && Object.keys(C.options).every(a => uiAxes.includes(a)), "axesForUI covers every axis exactly once");

// Presets
assert(C.presets.length >= 30 && C.presets.length <= 40, `30–40 presets (got ${C.presets.length})`);
const ids = new Set();
for (const p of C.presets) {
  assert(p.id && p.name && p.note && p.spec, `preset ${p.id} has id/name/note/spec`);
  assert(!ids.has(p.id), `preset id unique: ${p.id}`); ids.add(p.id);
  for (const axis of Object.keys(C.options)) assert(C.options[axis].includes(p.spec[axis]), `preset ${p.id} ${axis}=${p.spec[axis]} valid`);
  const res = FB.check(p.spec);
  checkShape(res, `preset ${p.id}`);
  assert(res.ok, `preset ${p.id} ok (errors: ${JSON.stringify(res.errors)})`);
}
assert(C.presets[0].id === "frostbite", "first preset is Frostbite");
const specKey = (s) => JSON.stringify(Object.keys(C.options).map(a => s[a]));
assert(new Set(C.presets.map(p => specKey(p.spec))).size === C.presets.length, "presets are all distinct specs");

// Known-bad specs
function expectError(over, code, label) {
  const res = FB.check(spec(over));
  checkShape(res, label);
  assert(!res.ok && codes(res.errors).includes(code), `${label}: expected error ${code}, got ${JSON.stringify(codes(res.errors))}`);
}
function expectWarning(over, code, label) {
  const res = FB.check(spec(over));
  checkShape(res, label);
  assert(codes(res.warnings).includes(code), `${label}: expected warning ${code}, got ${JSON.stringify(codes(res.warnings))}`);
}
expectError({ glowPlace: "gap", plate: "flush" }, "glow-gap-plate", "gap glow on flush plate");
expectError({ glowPlace: "gap", plate: "tray" }, "glow-gap-plate", "gap glow on tray");
expectError({ screws: "top", bezel: 6, corner: 4 }, "screws-top-bezel", "top screws on 6 mm bezel");
expectError({ plate: "deep-dish", glowPlace: "band", bezel: 6, corner: 4 }, "deep-dish-bezel", "deep dish on 6 mm bezel");
expectError({ corner: 16, bezel: 9 }, "corner-clip", "16 mm corner on 9 mm bezel");
expectError({ corner: 12, bezel: 6 }, "corner-clip", "12 mm corner on 6 mm bezel");
expectError({ caseMaterial: "acrylic" }, "not-printed", "acrylic case");
expectError({ plateMaterial: "laser-cut aluminium" }, "not-printed", "laser-cut plate");
expectError({ shell: "chrome" }, "bad-value", "unknown shell");
expectError({ corner: 10 }, "bad-value", "unknown corner");
assert(FB.check(spec({ corner: "12", bezel: "9" })).ok, "numeric axes given as strings are coerced");
assert(FB.check(spec({ wordmarkText: "laser cnc acrylic" })).ok, "wordmark text is free text, not a material");
assert(FB.check({}).ok, "empty spec falls back to defaults");

// Fake layouts (added to the runtime array only, removed afterwards) for the size / pin / part-count rules.
const P = 19.05;
const grid = (cols, rows) => { const k = []; for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) k.push({ x: c * P, y: 22 + r * P, role: r < rows - 1 ? "agent" : "command" }); return k; };
const fakes = [
  { id: "t-big", name: "Big", W: 6 * P, H: 22 + 3 * P, keys: grid(6, 3), dials: [{ x: 10, y: 11 }, { x: 50, y: 11 }, { x: 90, y: 11 }],
    oled: { x: 0, y: 5, w: 30, h: 11.5 }, pins: { matrix: 9, dial: 6, oled: 2, led: 1 }, matrix: "3×6", dialPress: false },
  { id: "t-huge", name: "Huge", W: 190, H: 60, keys: grid(3, 2), dials: [], oled: null, pins: { matrix: 5, dial: 0, oled: 0, led: 1 }, matrix: "x", dialPress: false },
  { id: "t-two-oled", name: "Two OLED", W: 3 * P, H: 22 + 3 * P, keys: grid(3, 3), dials: [{ x: 47, y: 11 }],
    oled: { x: 0, y: 5, w: 30, h: 11.5 }, oleds: [{ x: 0, y: 5, w: 30, h: 11.5 }, { x: 0, y: 5, w: 30, h: 11.5 }], pins: { matrix: 6, dial: 2, oled: 2, led: 1 }, matrix: "3×3", dialPress: false },
  { id: "t-tall", name: "Tall", W: 80, H: 190, keys: grid(3, 3), dials: [{ x: 47, y: 11 }], oled: null, pins: { matrix: 6, dial: 2, oled: 0, led: 1 }, matrix: "3×3", dialPress: false }
];
FB.layouts.push(...fakes);
C.options.layout.push(...fakes.map(f => f.id));
try {
  const big = FB.check(spec({ layout: "t-big" }));
  checkShape(big, "t-big");
  for (const c of ["pins", "pcb-size"]) assert(codes(big.errors).includes(c), `t-big: error ${c} (${JSON.stringify(codes(big.errors))})`);
  for (const c of ["switches-extra", "encoders-extra", "led-count"]) assert(codes(big.warnings).includes(c), `t-big: warning ${c}`);
  assert(big.stats.pins === 18 && big.stats.switches === 18 && big.stats.encoders === 3, "t-big stats counts");
  assert(big.extras.some(x => /switch/i.test(x.item) && x.qty === 2), "t-big: buys 2 extra switches");
  assert(big.extras.some(x => /encoder/i.test(x.item) && x.qty === 1), "t-big: buys 1 extra encoder");
  const huge = FB.check(spec({ layout: "t-huge", bezel: 12 }));
  assert(codes(huge.errors).includes("shell-size") && codes(huge.errors).includes("pcb-size"), "t-huge: shell-size + pcb-size");
  const two = FB.check(spec({ layout: "t-two-oled" }));
  assert(codes(two.errors).includes("oled-count"), "t-two-oled: oled-count");
  const tall = FB.check(spec({ layout: "t-tall", tilt: 8, bezel: 12 }));
  assert(codes(tall.errors).includes("shell-height") || codes(tall.errors).includes("shell-size"), "t-tall: size errors");
  assert(tall.stats.shell.height > 30, "t-tall: tilt raises height");
} finally {
  FB.layouts.splice(FB.layouts.length - fakes.length, fakes.length);
  C.options.layout.splice(C.options.layout.length - fakes.length, fakes.length);
}
assert(C.options.layout.length === 7 && FB.layouts.length === 7, "fake layouts removed");

// Warnings + extras
expectWarning({ shell: "smoke" }, "smoke-glow", "smoke + gap");
expectWarning({ agentCap: "clear" }, "clear-caps", "clear caps");
expectWarning({ knob: "ringlit" }, "led-count", "ringlit stratum9 = 17 LEDs");
expectWarning({ capProfile: "XDA" }, "xda-not-kit", "XDA");
expectWarning({ commandCap: "graphite" }, "graphite-not-kit", "graphite");
expectWarning({ legends: "icons" }, "icon-caps", "icons");
expectWarning({ tilt: 8, bezel: 6, corner: 4 }, "thin-tilt", "8° + 6 mm");
expectWarning({ layout: "pocket6" }, "few-commands", "pocket6");
expectWarning({ layout: "console4" }, "few-commands", "console4");
const halo = FB.check(spec({ knob: "ringlit" }));
assert(halo.stats.leds === 17 && halo.stats.pins === 11, `ringlit: 17 LEDs, no extra pin (got ${halo.stats.leds}, ${halo.stats.pins})`);
assert(halo.extras.some(x => /SK6812/.test(x.item) && x.qty === 1), "ringlit: buys 1 extra LED");
assert(halo.extras.some(x => /light-pipe/i.test(x.item)), "ringlit: buys light pipe");
const base = FB.check(spec({}));
assert(base.ok && base.warnings.length === 0, `default spec ok with no warnings (${JSON.stringify(codes(base.warnings))})`);
assert(base.stats.leds === 13 && base.stats.pins === 11 && base.stats.oled === 1, "default stats");
assert(base.extras.some(x => /Frosted/.test(x.item) && x.qty === 6), "default: buys 6 frosted agent caps");
assert(base.extras.some(x => /PETG/.test(x.item)), "default: clear PETG for gap spacer");
assert(base.extras.some(x => /aluminium knob/i.test(x.item) && x.qty === 1), "default: 1 alu knob");
assert(base.stats.shell.height > 25 && base.stats.shell.height < 60, `default height sensible (${base.stats.shell.height})`);
assert(FB.check(spec({ tilt: 0 })).stats.shell.height < base.stats.shell.height, "tilt 0 is lower than tilt 4");
const xda = FB.check(spec({ capProfile: "XDA" }));
assert(xda.extras.some(x => /XDA/.test(x.item)), "XDA: buys XDA caps");

// Every layout × a few variants: shape + finiteness
for (const L of C.options.layout) for (const knob of C.options.knob) for (const plate of C.options.plate) {
  const res = FB.check(spec({ layout: L, knob, plate, glowPlace: plate === "floating" ? "gap" : "band" }));
  checkShape(res, `${L}/${knob}/${plate}`);
}

// randomSpec
let randOk = 0;
for (let seed = 1; seed <= 1000; seed++) {
  const s = C.randomSpec(null, mulberry32(seed));
  const res = FB.check(s);
  if (res.ok) randOk++; else assert(false, `randomSpec seed ${seed} not ok: ${JSON.stringify(res.errors)}`);
  checkShape(res, `random ${seed}`);
}
assert(randOk === 1000, `randomSpec ok for 1000 seeds (${randOk})`);
const r1 = C.randomSpec(null, mulberry32(42)), r2 = C.randomSpec(null, mulberry32(42));
assert(JSON.stringify(r1) === JSON.stringify(r2), "randomSpec is deterministic for a seeded rng");
const seen = new Set();
for (let seed = 1; seed <= 200; seed++) seen.add(specKey(C.randomSpec(null, mulberry32(seed))));
assert(seen.size > 150, `randomSpec gives variety (${seen.size}/200 distinct)`);
for (let seed = 1; seed <= 300; seed++) {
  const lock = { layout: "console4", shell: "smoke", bezel: 6 };
  const s = C.randomSpec(lock, mulberry32(seed));
  assert(s.layout === "console4" && s.shell === "smoke" && s.bezel === 6 && FB.check(s).ok, `locked randomSpec seed ${seed}`);
}
const lockedArr = C.randomSpec(["layout", "glowColor"], mulberry32(7), spec({ layout: "wide9", glowColor: "warm" }));
assert(lockedArr.layout === "wide9" && lockedArr.glowColor === "warm" && FB.check(lockedArr).ok, "randomSpec with array of locked axis names + base");
const impossible = C.randomSpec({ glowPlace: "gap", plate: "flush" }, mulberry32(3));
assert(impossible.glowPlace === "gap" && impossible.plate === "flush", "impossible lock falls back to default merged with lock");

// randomSpec without constraints.js loaded (fresh module scope via a separate global).
{
  const vm = require("vm"), fs = require("fs");
  const ctx = { console };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  for (const f of ["dims.js", "layouts.js", "catalog.js"]) vm.runInContext(fs.readFileSync(path.join(__dirname, "..", f), "utf8"), ctx, { filename: f });
  assert(typeof ctx.FB.check === "undefined", "isolated context has no FB.check");
  let ok = 0;
  for (let seed = 1; seed <= 500; seed++) { const s = ctx.FB.catalog.randomSpec(null, mulberry32(seed)); if (FB.check(s).ok) ok++; }
  assert(ok === 500, `randomSpec without constraints.js still yields ok specs (${ok}/500)`);
}

// Report
const allCodes = new Set();
for (const p of C.presets) for (const w of FB.check(p.spec).warnings) allCodes.add(w.code);
console.log(`presets: ${C.presets.length}; preset warning codes seen: ${[...allCodes].sort().join(", ")}`);
console.log(`rules: ${Object.keys(FB.check.rules).join(", ")}`);
console.log(`default stats: ${JSON.stringify({ ...base.stats, stack: undefined })}`);
if (failures) { console.error(`\n${failures} failed, ${passes} passed`); process.exit(1); }
console.log(`\nAll ${passes} assertions passed.`);
