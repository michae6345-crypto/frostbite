#!/usr/bin/env node
/*
 * Frostbite Studio verification harness (Agent E). Node >= 16, no npm installs.
 *
 *   node verify/run.js                 # full run, writes verify/report.md
 *   node verify/run.js --random 2000   # more random specs
 *   node verify/run.js --seed 7        # different random set
 *
 * Exit code: 0 = no hard failures, 1 = hard failures, 2 = harness crashed.
 * Hard = contract broken or a spec FB.check approves is physically unsound.
 * Soft = approximate physical-fit warnings, robustness edge cases, style.
 */
'use strict';
process.on('uncaughtException', e => { console.error('verify harness crashed:', e && e.stack || e); process.exit(2); });
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.join(__dirname, 'report.md');
const argv = process.argv.slice(2);
const argVal = (k, d) => { const i = argv.indexOf(k); return i >= 0 && argv[i + 1] !== undefined ? argv[i + 1] : d; };
const N_RANDOM = parseInt(argVal('--random', '500'), 10);
const SEED = parseInt(argVal('--seed', '20261103'), 10);
const HARD = 'hard', SOFT = 'soft';

// ---------------------------------------------------------------- module loading (contract order)
const MODULES = [
  { file: 'dims.js', provides: ['dims'] },
  { file: 'layouts.js', provides: ['layouts', 'layoutById'] },
  { file: 'catalog.js', provides: ['catalog'] },
  { file: 'constraints.js', provides: ['check'] },
  { file: 'render-top.js', provides: ['renderTop'] },
  { file: 'render-side.js', provides: ['renderSide', 'renderExploded'] }
];
const loads = MODULES.map(m => {
  const p = path.join(ROOT, m.file);
  const rec = { file: m.file, ok: false, stub: false, error: null, missing: [], bytes: 0 };
  try {
    const src = fs.readFileSync(p, 'utf8');
    rec.bytes = src.length;
    rec.stub = /\bstub\b/i.test(src);
    require(p);
    const g = globalThis.FB || {};
    rec.missing = m.provides.filter(k => g[k] === undefined);
    rec.ok = rec.missing.length === 0;
  } catch (e) {
    rec.error = String((e && e.message) || e).split('\n')[0];
  }
  return rec;
});
const FB = globalThis.FB || {};
const stubOf = fn => { const owner = { renderTop: 'render-top.js', renderSide: 'render-side.js', renderExploded: 'render-side.js', check: 'constraints.js' }[fn]; const r = loads.find(l => l.file === owner); return !!(r && r.stub); };

// ---------------------------------------------------------------- result bookkeeping
const families = new Map();          // family -> {run, hard, soft}
const buckets = new Map();           // sev|type -> {sev, type, family, count, examples[]}
function fam(f) { if (!families.has(f)) families.set(f, { run: 0, hard: 0, soft: 0 }); return families.get(f); }
function record(family, sev, type, msg, spec) {
  const F = fam(family); F[sev]++;
  const key = sev + '|' + type;
  if (!buckets.has(key)) buckets.set(key, { sev, type, family, count: 0, examples: [] });
  const b = buckets.get(key); b.count++;
  const ex = { msg: String(msg).slice(0, 300), spec: spec ? specLabel(spec) : '' };
  if (b.examples.length < 3 && !b.examples.some(e => e.msg === ex.msg && e.spec === ex.spec)) b.examples.push(ex);
}
function expect(family, cond, sev, type, msg, spec) { fam(family).run++; if (!cond) record(family, sev, type, typeof msg === 'function' ? msg() : msg, spec); return !!cond; }
function safe(family, type, fn, spec, sev) {
  try { return { ok: true, v: fn() }; } catch (e) { fam(family).run++; record(family, sev || HARD, type, 'threw: ' + String((e && e.message) || e).split('\n')[0], spec); return { ok: false }; }
}
const fin = v => typeof v === 'number' && Number.isFinite(v);
const clone = o => JSON.parse(JSON.stringify(o));
const r2 = v => (fin(v) ? Math.round(v * 100) / 100 : String(v));

// ---------------------------------------------------------------- contract constants
const CONTRACT_OPTIONS = {
  layout: ['stratum9', 'mirror9', 'pocket6', 'stagger9', 'twin9', 'wide9', 'console4'],
  shell: ['iced', 'milk', 'glacier', 'smoke', 'lilac', 'mint'],
  texture: ['satin', 'layer-lines', 'speckle'],
  plate: ['floating', 'flush', 'deep-dish', 'tray'],
  glowColor: ['ice', 'white', 'cyan', 'lavender', 'mint', 'warm'],
  glowPlace: ['gap', 'band', 'base', 'none'],
  corner: [4, 8, 12, 16], bezel: [6, 9, 12],
  knob: ['knurled-alu', 'frosted', 'soft-white', 'ringlit', 'puck'],
  oledColor: ['white', 'ice', 'blue'], capProfile: ['DSA', 'XDA'],
  agentCap: ['frosted', 'clear', 'milky'], commandCap: ['white', 'frost-white', 'glacier', 'graphite'],
  legends: ['blank', 'icons'], screws: ['hidden', 'top', 'side'], wordmark: ['none', 'front', 'plate'], tilt: [0, 4, 8]
};
const STATUSES = ['idle', 'run', 'done', 'needs', 'error'];
const LIMITS = { pins: 11, pcb: 100, shellW: 200, shellH: 200, shellZ: 100, switches: 16, encoders: 2, leds: 16, oled: 1, inputsLt: 16 };
const opts = () => (FB.catalog && FB.catalog.options) || CONTRACT_OPTIONS;
const defaults = () => (FB.catalog && FB.catalog.defaultSpec) || {
  layout: 'stratum9', shell: 'iced', texture: 'satin', plate: 'floating', glowColor: 'ice', glowPlace: 'gap', corner: 12, bezel: 9,
  knob: 'knurled-alu', oledColor: 'white', capProfile: 'DSA', agentCap: 'frosted', commandCap: 'white', legends: 'blank', screws: 'hidden',
  wordmark: 'front', wordmarkText: 'frostbite', tilt: 4, statuses: ['run', 'done', 'run', 'needs', 'idle', 'error'] };
function specLabel(s) {
  if (!s || typeof s !== 'object') return String(s);
  const d = defaults(), parts = [];
  for (const k of Object.keys(CONTRACT_OPTIONS)) if (s[k] !== d[k]) parts.push(`${k}=${s[k]}`);
  if (s.wordmarkText !== d.wordmarkText) parts.push(`wordmarkText=${JSON.stringify(s.wordmarkText)}`);
  if (JSON.stringify(s.statuses) !== JSON.stringify(d.statuses)) parts.push(`statuses=${JSON.stringify(s.statuses)}`);
  return parts.length ? parts.join(' ') : '(default spec)';
}

// ---------------------------------------------------------------- 1. module + catalog contract
for (const l of loads) {
  expect('modules', l.ok, HARD, 'module-load', `${l.file}: ${l.error || 'missing FB.' + l.missing.join(', FB.')}`);
}
if (FB.catalog) {
  const o = FB.catalog.options || {};
  for (const [axis, vals] of Object.entries(CONTRACT_OPTIONS))
    for (const v of vals) expect('catalog contract', Array.isArray(o[axis]) && o[axis].includes(v), HARD, 'catalog-missing-option', `options.${axis} lacks ${JSON.stringify(v)}`);
  const pal = FB.catalog.palette || {};
  const need = [['shell', 'shell', ['top', 'base', 'edge']], ['glow', 'glowColor'], ['commandCap', 'commandCap'], ['agentCapBase', 'agentCap'], ['knob', 'knob', ['face', 'ring']], ['oled', 'oledColor']];
  for (const [pk, axis, fields] of need) for (const v of CONTRACT_OPTIONS[axis]) {
    const e = pal[pk] && pal[pk][v];
    expect('catalog contract', e !== undefined && (!fields || fields.every(f => typeof e[f] === 'string')), HARD, 'palette-missing', `palette.${pk}.${v} missing or incomplete`);
  }
  for (const st of STATUSES) expect('catalog contract', pal.status && typeof pal.status[st] === 'string', HARD, 'palette-missing', `palette.status.${st} missing`);
  expect('catalog contract', typeof FB.catalog.randomSpec === 'function', HARD, 'catalog-api', 'randomSpec is not a function');
  expect('catalog contract', Array.isArray(FB.catalog.presets) && FB.catalog.presets.length > 0, HARD, 'catalog-api', 'presets is not a non-empty array');
}
if (FB.layouts && FB.layoutById) for (const id of CONTRACT_OPTIONS.layout) {
  const L = FB.layouts.find(l => l.id === id);
  expect('catalog contract', !!L, HARD, 'layout-missing', `FB.layouts has no "${id}"`);
  if (L) {
    const pins = ['matrix', 'dial', 'oled', 'led'].reduce((a, k) => a + (L.pins[k] || 0), 0);
    expect('catalog contract', pins <= LIMITS.pins, HARD, 'layout-pins', `${id} needs ${pins} GPIO (>11)`);
    expect('catalog contract', L.keys.length <= LIMITS.switches && L.dials.length <= LIMITS.encoders, HARD, 'layout-kit', `${id}: ${L.keys.length} keys, ${L.dials.length} dials`);
    expect('catalog contract', pins < LIMITS.pins, SOFT, 'layout-no-spare-gpio', `${id} uses ${pins}/11 GPIO: zero spare pins for fixes (e.g. encoder push, LED level shifting)`);
  }
}
function validateSpec(spec, family) {
  const o = opts(); let good = true;
  for (const axis of Object.keys(CONTRACT_OPTIONS))
    good = expect(family, Array.isArray(o[axis]) && o[axis].includes(spec[axis]), HARD, 'spec-invalid-value', `${axis}=${JSON.stringify(spec[axis])} not in options`, spec) && good;
  good = expect(family, Array.isArray(spec.statuses) && spec.statuses.length > 0 && spec.statuses.every(s => STATUSES.includes(s)), HARD, 'spec-invalid-statuses', `statuses=${JSON.stringify(spec.statuses)}`, spec) && good;
  good = expect(family, typeof spec.wordmarkText === 'string', HARD, 'spec-invalid-wordmark', 'wordmarkText not a string', spec) && good;
  return good;
}

// ---------------------------------------------------------------- 2. build the test set
function mulberry32(a) { return function () { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const tests = []; // {spec, source, strict}
const base = clone(defaults());
if (FB.catalog && Array.isArray(FB.catalog.presets)) FB.catalog.presets.forEach(p => {
  const spec = p && p.spec ? p.spec : p;
  if (validateSpec(spec, 'spec validity')) tests.push({ spec: clone(spec), source: 'preset:' + (p.id || p.name || '?'), strict: true });
});
const O = opts();
for (const layout of O.layout || []) for (const plate of O.plate || []) for (const glowPlace of O.glowPlace || [])
  for (const bezel of O.bezel || []) for (const corner of O.corner || [])
    tests.push({ spec: { ...clone(base), layout, plate, glowPlace, bezel, corner }, source: 'exhaustive', strict: true });
if (FB.catalog && typeof FB.catalog.randomSpec === 'function') {
  const rng = mulberry32(SEED);
  for (let i = 0; i < N_RANDOM; i++) {
    const r = safe('spec validity', 'randomSpec-threw', () => FB.catalog.randomSpec({}, rng));
    if (r.ok && validateSpec(r.v, 'spec validity')) tests.push({ spec: clone(r.v), source: 'random', strict: true });
  }
  const a = safe('spec validity', 'randomSpec-threw', () => { const g = mulberry32(99); return [0, 1, 2].map(() => JSON.stringify(FB.catalog.randomSpec({}, g))); });
  const b = safe('spec validity', 'randomSpec-threw', () => { const g = mulberry32(99); return [0, 1, 2].map(() => JSON.stringify(FB.catalog.randomSpec({}, g))); });
  if (a.ok && b.ok) expect('spec validity', a.v.join() === b.v.join(), SOFT, 'randomSpec-not-seeded', 'randomSpec ignores the rng argument (not reproducible)');
  const lk = safe('spec validity', 'randomSpec-threw', () => FB.catalog.randomSpec({ layout: 'wide9', bezel: 6 }, mulberry32(5)));
  if (lk.ok) expect('spec validity', lk.v.layout === 'wide9' && lk.v.bezel === 6, HARD, 'randomSpec-ignores-lock', 'randomSpec({layout:"wide9",bezel:6}) did not keep locked axes');
}
// Robustness edge cases: failures are soft (contract does not spell these out, but the page will hit them).
const robust = [
  { ...base, statuses: [] }, { ...base, statuses: ['error'] }, { ...base, statuses: Array(12).fill('needs') },
  { ...base, wordmarkText: 'Frost & <Bite> "v2"' }, { ...base, wordmarkText: '' }, { ...base, wordmarkText: 'x'.repeat(48) },
  { ...base, layout: 'console4', plate: 'deep-dish', bezel: 12, corner: 16, tilt: 8, capProfile: 'XDA' },
  { ...base, layout: 'wide9', plate: 'tray', bezel: 6, corner: 16, tilt: 0, glowPlace: 'none' }
].map(s => ({ spec: clone(s), source: 'robustness', strict: false }));
tests.push(...robust);

// ---------------------------------------------------------------- 3. geometry (layout x bezel x corner)
const D = FB.dims || {};
const num = (v, d) => (fin(v) ? v : d);
const G = {
  P: num(D.pitch, 19.05), cap: num(D.capBottom, 18.2), cut: num(D.switchCutout, 14), swBody: 15.6 /* MX housing below plate */,
  knobD: num(D.ec11 && D.ec11.knobDiameter, 18), ec11: num(D.ec11 && D.ec11.body, 12.5),
  om: { w: num(D.oledModule && D.oledModule.w, 38), h: num(D.oledModule && D.oledModule.h, 12) },
  xiao: { w: num(D.xiao && D.xiao.w, 17.8), h: num(D.xiao && D.xiao.h, 21) },
  minWall: num(D.minWall, 2), tol: num(D.printTolerance, 0.3),
  insertHole: 4.7, /* Hackpad resources page: 4.7 mm hole, 4 mm deep for the kit inserts */
  topClear: 1.0, keepout: 0.5
};
const rect = (x, y, w, h) => ({ x, y, w, h });
const centred = (cx, cy, s) => rect(cx - s / 2, cy - s / 2, s, s);
function dRR(a, b) {
  const dx = Math.max(a.x - (b.x + b.w), b.x - (a.x + a.w), 0), dy = Math.max(a.y - (b.y + b.h), b.y - (a.y + a.h), 0);
  if (dx > 0 || dy > 0) return Math.hypot(dx, dy);
  return -Math.min(a.x + a.w - b.x, b.x + b.w - a.x, a.y + a.h - b.y, b.y + b.h - a.y);
}
function dRC(r, c) {
  const nx = Math.max(r.x, Math.min(c.cx, r.x + r.w)), ny = Math.max(r.y, Math.min(c.cy, r.y + r.h));
  const d = Math.hypot(c.cx - nx, c.cy - ny);
  if (d > 0) return d - c.r;
  return -(c.r + Math.min(c.cx - r.x, r.x + r.w - c.cx, c.cy - r.y, r.y + r.h - c.cy));
}
const dCC = (a, b) => Math.hypot(a.cx - b.cx, a.cy - b.cy) - a.r - b.r;
const dist = (a, b) => (a.r !== undefined ? (b.r !== undefined ? dCC(a, b) : dRC(b, a)) : (b.r !== undefined ? dRC(a, b) : dRR(a, b)));
function outlineDistPt(px, py, L, b, rad) { // inside distance to the rounded shell outline (negative = outside)
  const hx = L.W / 2 + b, hy = L.H / 2 + b, cx = L.W / 2, cy = L.H / 2, rr = Math.min(rad, hx, hy);
  const qx = Math.abs(px - cx) - (hx - rr), qy = Math.abs(py - cy) - (hy - rr);
  return -(Math.hypot(Math.max(qx, 0), Math.max(qy, 0)) + Math.min(Math.max(qx, qy), 0) - rr);
}
const outlineDist = (s, L, b, rad) => (s.r !== undefined ? outlineDistPt(s.cx, s.cy, L, b, rad) - s.r
  : Math.min(...[[s.x, s.y], [s.x + s.w, s.y], [s.x, s.y + s.h], [s.x + s.w, s.y + s.h]].map(([x, y]) => outlineDistPt(x, y, L, b, rad))));
const inContent = (s, L, e = 1e-6) => (s.r !== undefined ? s.cx - s.r >= -e && s.cy - s.r >= -e && s.cx + s.r <= L.W + e && s.cy + s.r <= L.H + e
  : s.x >= -e && s.y >= -e && s.x + s.w <= L.W + e && s.y + s.h <= L.H + e);

const layoutGeo = new Map();
function geoLayout(L) {
  if (layoutGeo.has(L.id)) return layoutGeo.get(L.id);
  const P = G.P, hard = [], soft = [];
  const keys = L.keys.map((k, i) => {
    const cx = k.x + P / 2, cy = k.y + P / 2;
    return { name: `key${i + 1}`, cell: rect(k.x, k.y, P, P), cap: centred(cx, cy, G.cap), cut: centred(cx, cy, G.cut), body: centred(cx, cy, G.swBody) };
  });
  const dials = L.dials.map((d, i) => ({ name: `dial${i + 1}`, knob: { cx: d.x, cy: d.y, r: G.knobD / 2 }, body: centred(d.x, d.y, G.ec11) }));
  const win = L.oled ? rect(L.oled.x, L.oled.y, L.oled.w, L.oled.h) : null;
  for (let i = 0; i < keys.length; i++) for (let j = i + 1; j < keys.length; j++) {
    const d = dRR(keys[i].cell, keys[j].cell);
    if (d < -1e-6) hard.push({ type: 'key-overlap', msg: `${L.id}: ${keys[i].name}/${keys[j].name} cells overlap by ${r2(-d)} mm` });
  }
  const top = [...keys.map(k => ({ n: k.name, s: k.cap, kind: 'key' })), ...dials.map(d => ({ n: d.name, s: d.knob, kind: 'dial' }))];
  if (win) top.push({ n: 'oled', s: win, kind: 'oled' });
  let minClear = { d: Infinity, pair: '-' };
  for (let i = 0; i < top.length; i++) for (let j = i + 1; j < top.length; j++) {
    if (top[i].kind === 'key' && top[j].kind === 'key') continue;
    const d = dist(top[i].s, top[j].s);
    if (d < minClear.d) minClear = { d, pair: `${top[i].n}–${top[j].n}` };
    if (d < G.topClear) hard.push({ type: d < 0 ? 'element-overlap' : 'element-clearance', msg: `${L.id}: ${top[i].n} vs ${top[j].n} ${d < 0 ? 'overlap' : 'gap'} ${r2(d)} mm (need ≥ ${G.topClear})` });
  }
  for (const k of keys) if (!inContent(k.cell, L)) hard.push({ type: 'outside-content', msg: `${L.id}: ${k.name} cell leaves the ${r2(L.W)}×${r2(L.H)} content area` });
  for (const d of dials) if (!inContent(d.knob, L)) hard.push({ type: 'outside-content', msg: `${L.id}: ${d.name} knob leaves the content area` });
  if (win && !inContent(win, L)) hard.push({ type: 'outside-content', msg: `${L.id}: OLED window leaves the content area` });

  // OLED module (38×12 board) under the 30 mm window: header end can point either way.
  let oled = null;
  if (win) {
    // Glass starts oledGlassInset from the board end opposite the header (docs/DIMENSIONS.md).
    const inset = num(D.oledGlassInset, 3.5);
    const cands = [['header→right', rect(win.x - inset, win.y + (win.h - G.om.h) / 2, G.om.w, G.om.h)], ['header→left', rect(win.x + win.w + inset - G.om.w, win.y + (win.h - G.om.h) / 2, G.om.w, G.om.h)]]
      .map(([orient, r]) => {
        const over = Math.max(0, -r.x, r.x + r.w - L.W, -r.y, r.y + r.h - L.H);
        const hits = [...keys.filter(k => dRR(r, k.body) < G.keepout).map(k => k.name), ...dials.filter(d => dRR(r, d.body) < G.keepout).map(d => d.name + ' EC11')];
        return { orient, r, over, hits, score: hits.length * 100 + over };
      }).sort((a, b) => a.score - b.score);
    oled = cands[0];
    if (oled.score > 0) soft.push({ type: 'oled-module-fit', msg: `${L.id}: no orientation of the ${G.om.w}×${G.om.h} OLED board fits; best ${oled.orient} overhangs content by ${r2(oled.over)} mm${oled.hits.length ? ', hits ' + oled.hits.join(', ') : ''}` });
  }
  for (const d of dials) for (const k of keys) if (dRR(d.body, k.body) < G.keepout) soft.push({ type: 'ec11-vs-switch', msg: `${L.id}: ${d.name} EC11 body within ${G.keepout} mm of ${k.name} switch housing` });

  // XIAO on the underside, USB-C at an edge. Blocked by switch housings / EC11 bodies; under the OLED board is allowed but noted.
  const blockers = [...keys.map(k => k.body), ...dials.map(d => d.body)];
  const edges = [['back', G.xiao.w, G.xiao.h], ['left', G.xiao.h, G.xiao.w], ['right', G.xiao.h, G.xiao.w]];
  let xiao = null;
  // Prefer the position closest to the middle of its edge (centred USB-C, away from rounded corners).
  outer: for (const pass of ['clean', 'underOled']) for (const [edge, w, h] of edges) {
    const pts = [];
    if (edge === 'back') for (let x = 0; x <= L.W - w + 1e-9; x += 0.25) pts.push([x, 0]);
    else for (let y = 0; y <= L.H - h + 1e-9; y += 0.25) pts.push([edge === 'left' ? 0 : L.W - w, y]);
    const mid = edge === 'back' ? [L.W / 2, h / 2] : [edge === 'left' ? w / 2 : L.W - w / 2, L.H / 2];
    pts.sort((a, b) => Math.hypot(a[0] + w / 2 - mid[0], a[1] + h / 2 - mid[1]) - Math.hypot(b[0] + w / 2 - mid[0], b[1] + h / 2 - mid[1]));
    for (const [x, y] of pts) {
      const r = rect(x, y, w, h);
      if (blockers.some(b => dRR(r, b) < G.keepout)) continue;
      const under = !!(oled && dRR(r, oled.r) < 0);
      if (pass === 'clean' && under) continue;
      xiao = { edge, r, under }; break outer;
    }
  }
  if (!xiao) soft.push({ type: 'xiao-no-room', msg: `${L.id}: no edge position for the ${G.xiao.w}×${G.xiao.h} XIAO clear of switch housings and EC11 bodies` });
  else if (xiao.under) soft.push({ type: 'xiao-under-oled', msg: `${L.id}: XIAO only fits under the OLED board (${xiao.edge} edge, x=${r2(xiao.r.x)}); trim XIAO pins flush and raise the OLED on its header` });
  const g = { L, keys, dials, win, oled, xiao, hard, soft, minClear };
  layoutGeo.set(L.id, g);
  return g;
}
const comboGeo = new Map();
function geoCombo(L, b, rad) {
  const key = `${L.id}|${b}|${rad}`;
  if (comboGeo.has(key)) return comboGeo.get(key);
  const g = geoLayout(L), hard = [], soft = [];
  const topItems = [...g.keys.map(k => [k.name + ' cap', k.cap]), ...g.dials.map(d => [d.name + ' knob', d.knob])];
  if (g.win) topItems.push(['OLED window', g.win]);
  const wallItems = [...g.keys.map(k => [k.name + ' switch', k.body]), ...g.dials.map(d => [d.name + ' EC11', d.body])];
  if (g.oled) wallItems.push(['OLED board', g.oled.r]);
  if (g.xiao) wallItems.push(['XIAO', g.xiao.r]);
  const needWall = G.minWall + G.tol;
  let eff = { d: Infinity, what: '-' };
  for (const [n, s] of topItems) {
    const d = outlineDist(s, L, b, rad);
    if (d < eff.d) eff = { d, what: n };
    if (d < G.topClear) hard.push({ type: d < 0 ? 'clipped-by-shell' : 'edge-clearance-top', msg: `${n} is ${r2(d)} mm from the shell outline (bezel ${b}, corner ${rad}; need ≥ ${G.topClear})` });
  }
  for (const [n, s] of wallItems) {
    const d = outlineDist(s, L, b, rad);
    if (d < eff.d) eff = { d, what: n };
    if (d < needWall) hard.push({ type: d < 0 ? 'clipped-by-shell' : 'edge-clearance-wall', msg: `${n} is ${r2(d)} mm from the shell outline (bezel ${b}, corner ${rad}; need ≥ ${needWall} wall + tolerance)` });
  }
  // Heat-set insert bosses: hole Ø4.7 + minWall each side; one per corner region, clear of PCB parts by tolerance.
  const Rb = G.insertHole / 2 + G.minWall;
  const keepouts = wallItems.map(w => w[1]);
  const corners = [[-b, -b, 1, 1], [L.W + b, -b, -1, 1], [-b, L.H + b, 1, -1], [L.W + b, L.H + b, -1, -1]];
  let okCorners = 0;
  for (const [ox, oy, sx, sy] of corners) {
    let found = false;
    for (let u = 0; u <= 30 && !found; u += 0.5) for (let v = 0; v <= 30 && !found; v += 0.5) {
      const c = { cx: ox + sx * u, cy: oy + sy * v, r: Rb };
      if (outlineDistPt(c.cx, c.cy, L, b, rad) < Rb) continue;
      if (keepouts.some(k => dRC(k, c) < G.tol)) continue;
      found = true;
    }
    if (found) okCorners++;
  }
  if (okCorners < 4) soft.push({ type: 'insert-boss', msg: `${L.id} bezel ${b} corner ${rad}: only ${okCorners}/4 corners fit a Ø${r2(2 * Rb)} insert boss (Ø${G.insertHole} hole + ${G.minWall} wall) clear of parts` });
  const c = { hard, soft, eff, okCorners };
  comboGeo.set(key, c);
  return c;
}

// ---------------------------------------------------------------- 4. SVG checks (tiny XML parser)
const ENT = /&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)/;
function parseXml(s) {
  const problems = [], stack = [], elements = [];
  let i = 0, roots = 0, root = null, closedRoot = false;
  const n = s.length;
  while (i < n) {
    const lt = s.indexOf('<', i);
    const text = s.slice(i, lt < 0 ? n : lt);
    if (text.trim()) {
      if (!stack.length) problems.push(`text outside root: "${text.trim().slice(0, 30)}"`);
      if (ENT.test(text)) problems.push(`unescaped & in text: "${text.trim().slice(0, 30)}"`);
    }
    if (lt < 0) break;
    const skip = (open, close) => { const e = s.indexOf(close, lt + open.length); if (e < 0) { problems.push(`unterminated ${open}`); i = n; } else i = e + close.length; };
    if (s.startsWith('<!--', lt)) { skip('<!--', '-->'); continue; }
    if (s.startsWith('<![CDATA[', lt)) { skip('<![CDATA[', ']]>'); continue; }
    if (s.startsWith('<?', lt)) { skip('<?', '?>'); continue; }
    if (s.startsWith('<!', lt)) { skip('<!', '>'); continue; }
    let j = lt + 1, q = null;
    for (; j < n; j++) {
      const ch = s[j];
      if (q) { if (ch === q) q = null; else if (ch === '<') { problems.push('< inside attribute value'); } }
      else if (ch === '"' || ch === "'") q = ch;
      else if (ch === '>') break;
      else if (ch === '<') { problems.push(`< inside tag near "${s.slice(lt, lt + 30)}"`); break; }
    }
    if (j >= n) { problems.push(`unterminated tag "${s.slice(lt, lt + 30)}"`); break; }
    const body = s.slice(lt + 1, j); i = j + 1;
    if (s[j] === '<') { i = j; continue; }
    if (body[0] === '/') {
      const name = body.slice(1).trim(), top = stack.pop();
      if (top !== name) problems.push(`</${name}> closes <${top || 'nothing'}>`);
      if (!stack.length) closedRoot = true;
      continue;
    }
    const self = /\/\s*$/.test(body), inner = self ? body.replace(/\/\s*$/, '') : body;
    const m = /^([A-Za-z_][\w:.-]*)/.exec(inner);
    if (!m) { problems.push(`bad tag "<${inner.slice(0, 20)}"`); continue; }
    const name = m[1], attrs = {};
    const re = /\s+([A-Za-z_:][\w:.-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')/y;
    re.lastIndex = name.length;
    let mm, pos = name.length;
    while ((mm = re.exec(inner))) {
      pos = re.lastIndex;
      const v = mm[2] !== undefined ? mm[2] : mm[3];
      if (attrs[mm[1]] !== undefined) problems.push(`duplicate attribute ${mm[1]} on <${name}>`);
      if (ENT.test(v)) problems.push(`unescaped & in ${mm[1]} on <${name}>`);
      attrs[mm[1]] = v;
    }
    if (inner.slice(pos).trim()) problems.push(`malformed attributes on <${name}>: "${inner.slice(pos).trim().slice(0, 30)}"`);
    if (!stack.length) { roots++; if (roots > 1 || closedRoot) problems.push(`extra root element <${name}>`); if (!root) root = { name, attrs }; }
    elements.push({ name, attrs });
    if (!self) stack.push(name);
  }
  if (stack.length) problems.push(`unclosed <${stack.join('> <')}>`);
  if (!root) problems.push('no root element');
  return { problems, root, elements };
}
const NUM_ATTRS = new Set(['x', 'y', 'width', 'height', 'cx', 'cy', 'r', 'rx', 'ry', 'x1', 'y1', 'x2', 'y2', 'stroke-width', 'opacity', 'fill-opacity', 'stroke-opacity', 'font-size', 'offset']);
const NON_NEG = new Set(['width', 'height', 'r', 'rx', 'ry', 'stroke-width']);
const NUM_RE = /^\s*[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?\s*(px|%|mm|em|pt)?\s*$/i;
let paletteSet = null;
const offPalette = new Map();
function checkSvg(svg, prefix) {
  const out = [];
  if (typeof svg !== 'string' || !svg.trim()) return [{ type: 'svg-not-string', msg: `returned ${typeof svg}` }];
  for (const bad of ['NaN', 'undefined', 'Infinity', '[object Object]']) {
    const k = svg.indexOf(bad);
    if (k >= 0) out.push({ type: 'svg-bad-token', msg: `contains "${bad}": …${svg.slice(Math.max(0, k - 40), k + 20)}…` });
  }
  const x = parseXml(svg);
  x.problems.slice(0, 2).forEach(p => out.push({ type: 'svg-xml', msg: p }));
  const R = x.root;
  if (R) {
    if (R.name !== 'svg') out.push({ type: 'svg-root', msg: `root is <${R.name}>` });
    const vb = (R.attrs.viewBox || '').trim().split(/[\s,]+/).map(Number);
    if (vb.length !== 4 || !vb.every(Number.isFinite) || vb[2] <= 0 || vb[3] <= 0) out.push({ type: 'svg-viewbox', msg: `viewBox="${R.attrs.viewBox}"` });
    if (R.attrs.role !== 'img') out.push({ type: 'svg-a11y', msg: 'root lacks role="img"' });
    if (!R.attrs['aria-label'] || !R.attrs['aria-label'].trim()) out.push({ type: 'svg-a11y', msg: 'root lacks a non-empty aria-label' });
    if (R.attrs.xmlns !== 'http://www.w3.org/2000/svg') out.push({ type: 'svg-xmlns', soft: true, msg: 'root lacks xmlns (breaks use as <img>/download)' });
  }
  const ids = new Set();
  for (const el of x.elements) {
    const id = el.attrs.id;
    if (id !== undefined) {
      if (ids.has(id)) out.push({ type: 'svg-duplicate-id', msg: `id "${id}" used twice` });
      ids.add(id);
      if (prefix && !id.startsWith(prefix)) out.push({ type: 'svg-id-prefix', msg: `id "${id}" does not start with idPrefix "${prefix}"` });
    }
    for (const [a, v] of Object.entries(el.attrs)) {
      if (NUM_ATTRS.has(a) && !['auto', 'inherit', 'none'].includes(v.trim()) && !(el.name === 'svg' && (a === 'width' || a === 'height'))) {
        if (!NUM_RE.test(v)) out.push({ type: 'svg-bad-number', msg: `<${el.name} ${a}="${v.slice(0, 20)}">` });
        else if (NON_NEG.has(a) && parseFloat(v) < 0) out.push({ type: 'svg-negative-size', msg: `<${el.name} ${a}="${v}">` });
      }
      if (paletteSet && /^(fill|stroke|stop-color|flood-color|style)$/.test(a)) for (const c of v.match(/#[0-9a-fA-F]{3,8}\b/g) || []) {
        const lc = c.toLowerCase(); if (!paletteSet.has(lc)) offPalette.set(lc, (offPalette.get(lc) || 0) + 1);
      }
    }
  }
  for (const el of x.elements) for (const [a, v] of Object.entries(el.attrs)) {
    const refs = [...v.matchAll(/url\(\s*['"]?#([^'")\s]+)/g)].map(m => m[1]);
    if ((a === 'href' || a === 'xlink:href') && v.startsWith('#')) refs.push(v.slice(1));
    for (const r of refs) if (!ids.has(r)) out.push({ type: 'svg-broken-ref', msg: `<${el.name} ${a}> references missing #${r}` });
  }
  return out;
}
// Self-test of the SVG checker so a silent parser bug cannot turn every render green.
(function selfTest() {
  const good = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" role="img" aria-label="t"><defs><linearGradient id="p_g"/></defs><!-- c --><rect x="1" y="1" width="2" height="2" fill="url(#p_g)"/><text>a &amp; b</text></svg>';
  const bad = [
    ['<svg viewBox="0 0 10 10" role="img" aria-label="t"><g></svg>', 'svg-xml'],
    ['<svg viewBox="0 0 10 10" role="img" aria-label="t"><rect x="NaN"/></svg>', 'svg-bad-token'],
    ['<svg role="img" aria-label="t"></svg>', 'svg-viewbox'],
    ['<svg viewBox="0 0 10 10" role="img" aria-label="t"><text>A & B</text></svg>', 'svg-xml'],
    ['<svg viewBox="0 0 10 10" role="img" aria-label="t"><g id="zz"/></svg>', 'svg-id-prefix'],
    ['<svg viewBox="0 0 10 10" role="img" aria-label="t"><rect fill="url(#p_x)"/></svg>', 'svg-broken-ref'],
    ['<svg viewBox="0 0 10 10" role="img" aria-label="t"><rect width="-2"/></svg>', 'svg-negative-size'],
    ['<svg viewBox="0 0 10 10" role="img" aria-label="t"><rect x="1" x="2"/></svg>', 'svg-xml'],
    ['<svg viewBox="0 0 10 10" aria-label="t"></svg>', 'svg-a11y']
  ];
  const saved = paletteSet; paletteSet = null;
  const g = checkSvg(good, 'p_');
  expect('harness self-test', g.length === 0, HARD, 'selftest', 'good SVG flagged: ' + JSON.stringify(g));
  for (const [svg, type] of bad) expect('harness self-test', checkSvg(svg, 'p_').some(p => p.type === type), HARD, 'selftest', `missed ${type} in ${svg}`);
  paletteSet = saved;
})();
if (FB.catalog && FB.catalog.palette) {
  paletteSet = new Set(['#000', '#000000', '#fff', '#ffffff']);
  (function walk(o) { for (const v of Object.values(o)) { if (typeof v === 'string' && v[0] === '#') paletteSet.add(v.toLowerCase()); else if (v && typeof v === 'object') walk(v); } })(FB.catalog.palette);
}

// ---------------------------------------------------------------- 5. run every spec
const checkCodes = { errors: new Map(), warnings: new Map() };
const svgStats = {};
let okCount = 0, rejCount = 0, expectedGeoRejections = 0;
const comboOkSpecs = new Map();
const bump = (m, k) => m.set(k, (m.get(k) || 0) + 1);
const isStr = v => typeof v === 'string' && v.length > 0;
function checkShape(res, spec) {
  const F = 'FB.check shape', p = [];
  if (!res || typeof res !== 'object') return expect(F, false, HARD, 'check-shape', 'FB.check returned ' + typeof res, spec), false;
  if (typeof res.ok !== 'boolean') p.push('ok not boolean');
  for (const k of ['errors', 'warnings']) {
    if (!Array.isArray(res[k])) p.push(`${k} not array`);
    else res[k].forEach((e, i) => { if (!e || !isStr(e.code) || !isStr(e.msg)) p.push(`${k}[${i}] lacks code/msg strings`); });
  }
  if (!Array.isArray(res.extras)) p.push('extras not array');
  else res.extras.forEach((e, i) => { if (!e || !isStr(e.item) || !fin(e.qty) || typeof e.why !== 'string') p.push(`extras[${i}] lacks item/qty/why`); });
  const st = res.stats || {};
  for (const k of ['pins', 'pinsMax', 'switches', 'encoders', 'leds', 'ledsKit', 'oled']) if (!fin(st[k])) p.push(`stats.${k}=${st[k]}`);
  if (!st.pcb || !fin(st.pcb.w) || !fin(st.pcb.h)) p.push('stats.pcb.w/h not finite');
  if (!st.shell || !fin(st.shell.w) || !fin(st.shell.h) || !fin(st.shell.height)) p.push('stats.shell.w/h/height not finite');
  if (Array.isArray(res.errors) && typeof res.ok === 'boolean' && res.ok !== (res.errors.length === 0)) p.push(`ok=${res.ok} but ${res.errors.length} errors`);
  if (st.pinsMax !== undefined && st.pinsMax !== 11) p.push(`pinsMax=${st.pinsMax}`);
  if (st.ledsKit !== undefined && st.ledsKit !== 16) p.push(`ledsKit=${st.ledsKit}`);
  fam(F).run++;
  p.forEach(m => record(F, HARD, 'check-shape', m, spec));
  return p.length === 0;
}
tests.forEach((t, idx) => {
  const spec = t.spec, sevFor = sev => (t.strict ? sev : SOFT), famFor = f => (t.strict ? f : 'robustness');
  const L = FB.layoutById ? FB.layoutById(spec.layout) : null;
  // FB.check
  let res = null;
  if (typeof FB.check === 'function') {
    const r = safe(famFor('FB.check shape'), 'check-threw', () => FB.check(clone(spec)), spec, sevFor(HARD));
    if (r.ok && checkShape(r.v, spec)) res = r.v;
  }
  if (res && t.strict) {
    const st = res.stats, F = 'FB.check limits';
    if (res.ok) {
      okCount++;
      expect(F, st.pins <= LIMITS.pins, HARD, 'ok-but-pins', `ok with ${st.pins} pins`, spec);
      expect(F, st.pcb.w <= LIMITS.pcb && st.pcb.h <= LIMITS.pcb, HARD, 'ok-but-pcb', `ok with PCB ${r2(st.pcb.w)}×${r2(st.pcb.h)}`, spec);
      expect(F, st.shell.w <= LIMITS.shellW && st.shell.h <= LIMITS.shellH && st.shell.height <= LIMITS.shellZ, HARD, 'ok-but-shell', `ok with shell ${r2(st.shell.w)}×${r2(st.shell.h)}×${r2(st.shell.height)}`, spec);
      // Over-kit parts are allowed if bought (Hackpad FAQ), so they must show up in extras. One OLED max: fixed I2C address.
      expect(F, st.oled <= LIMITS.oled, HARD, 'ok-but-oled', `ok with ${st.oled} OLEDs (one I²C address on D4/D5)`, spec);
      const ex = res.extras.map(e => String(e.item)).join(' | ');
      for (const [k, lim, re] of [['switches', LIMITS.switches, /switch/i], ['encoders', LIMITS.encoders, /encoder|ec11/i], ['leds', LIMITS.leds, /led|sk6812/i]])
        if (st[k] > lim) expect(F, re.test(ex), HARD, 'over-kit-not-in-extras', `ok with ${st[k]} ${k} (kit ${lim}) but extras has no matching item: [${ex}]`, spec);
      expect(F, st.switches + st.encoders < LIMITS.inputsLt, HARD, 'ok-but-inputs', `ok with ${st.switches + st.encoders} inputs (Hackpad: < 16)`, spec);
    } else {
      rejCount++;
      res.errors.forEach(e => bump(checkCodes.errors, e.code));
    }
    res.warnings.forEach(e => bump(checkCodes.warnings, e.code));
    if (L) {
      expect(F, st.switches === L.keys.length && st.encoders === L.dials.length && st.oled === (L.oled ? 1 : 0), HARD, 'stats-vs-layout', `stats ${st.switches} sw/${st.encoders} enc/${st.oled} oled vs layout ${L.keys.length}/${L.dials.length}/${L.oled ? 1 : 0}`, spec);
      expect(F, st.pcb.w >= L.W - 1e-6 && st.pcb.h >= L.H - 1e-6, HARD, 'pcb-smaller-than-content', `PCB ${r2(st.pcb.w)}×${r2(st.pcb.h)} < content ${r2(L.W)}×${r2(L.H)}`, spec);
      expect(F, st.shell.w >= st.pcb.w + 2 * G.minWall && st.shell.h >= st.pcb.h + 2 * G.minWall, HARD, 'shell-smaller-than-pcb', `shell ${r2(st.shell.w)}×${r2(st.shell.h)} vs PCB ${r2(st.pcb.w)}×${r2(st.pcb.h)} + 2×${G.minWall} wall`, spec);
      const lp = ['matrix', 'dial', 'oled', 'led'].reduce((a, k) => a + (L.pins[k] || 0), 0);
      expect(F, st.pins >= lp, SOFT, 'stats-pins-below-layout', `stats.pins ${st.pins} < layout pin sum ${lp}`, spec);
    }
    if (t.source.startsWith('preset')) expect('presets pass', res.ok, HARD, 'preset-rejected', `${t.source} rejected: ${res.errors.map(e => e.code).join(', ')}`, spec);
    const again = safe('FB.check shape', 'check-threw', () => FB.check(clone(spec)), spec);
    if (again.ok) expect('FB.check shape', JSON.stringify(again.v) === JSON.stringify(res), SOFT, 'check-nondeterministic', 'two calls returned different results', spec);
  }
  // geometry vs checker
  if (L && t.strict && fin(spec.bezel) && fin(spec.corner)) {
    const gl = geoLayout(L), gc = geoCombo(L, spec.bezel, spec.corner);
    const issues = [...gl.hard, ...gc.hard];
    const key = `${L.id}|${spec.bezel}|${spec.corner}`;
    if (res && res.ok) bump(comboOkSpecs, key);
    if (res && !res.ok && issues.length) expectedGeoRejections++;
    fam('geometry vs FB.check').run++;
    if (res && res.ok) issues.forEach(is => record('geometry vs FB.check', HARD, 'checker-gap:' + is.type, is.msg, spec));
  }
  // renders
  const prefix = `vt${idx}_`;
  const calls = [
    ['renderTop', () => FB.renderTop(spec, { t: 0, idPrefix: prefix, dims: false, label: '' })],
    ['renderTop+dims', () => FB.renderTop(spec, { t: 3, idPrefix: prefix, dims: true, label: 'Frostbite test' })],
    ['renderSide', () => FB.renderSide(spec, { t: 0, idPrefix: prefix })],
    ['renderExploded', () => FB.renderExploded(spec, { t: 0, idPrefix: prefix })]
  ];
  for (const [name, fn] of calls) {
    const fnName = name.split('+')[0];
    if (typeof FB[fnName] !== 'function') continue;
    const F = t.strict ? fnName : 'robustness';
    const tag = stubOf(fnName) ? ' [stub]' : '';
    const r = safe(F, fnName + '-threw' + tag, fn, spec, sevFor(HARD));
    if (!r.ok) continue;
    const st = svgStats[name] = svgStats[name] || { n: 0, sum: 0, max: 0, min: Infinity };
    const len = typeof r.v === 'string' ? r.v.length : 0;
    st.n++; st.sum += len; st.max = Math.max(st.max, len); st.min = Math.min(st.min, len);
    const probs = checkSvg(r.v, prefix);
    fam(F).run++;
    probs.forEach(p => record(F, p.soft ? SOFT : sevFor(HARD), `${fnName}:${p.type}${tag}`, p.msg, spec));
    if (name === 'renderTop' && t.strict && idx % 7 === 0) {
      const again = safe(F, fnName + '-threw', fn, spec);
      if (again.ok) expect(F, again.v === r.v, SOFT, 'renderTop:nondeterministic' + tag, 'same spec + opts rendered differently', spec);
    }
  }
});

// layout/combo-level geometry results (recorded once, not per spec)
if (FB.layouts) for (const L of FB.layouts) {
  const gl = geoLayout(L);
  fam('geometry (layout)').run++;
  gl.hard.forEach(i => record('geometry (layout)', HARD, i.type, i.msg));
  gl.soft.forEach(i => record('geometry (layout)', SOFT, i.type, i.msg));
  for (const b of (opts().bezel || [])) for (const c of (opts().corner || [])) {
    const gc = geoCombo(L, b, c);
    fam('geometry (shell)').run++;
    // Hard only matters when FB.check approves it (reported above as checker-gap). Here: soft inventory.
    gc.hard.forEach(i => record('geometry (shell)', SOFT, i.type, `${L.id}: ${i.msg}`));
    gc.soft.forEach(i => record('geometry (shell)', SOFT, i.type, i.msg + ((comboOkSpecs.get(`${L.id}|${b}|${c}`) || 0) ? ' — FB.check approves it' : '')));
  }
}
const ih = D.heatSetInsert && D.heatSetInsert.holeDiameter;
expect('catalog contract', !fin(ih) || Math.abs(ih - 4.7) < 0.15, SOFT, 'dims-insert-hole', `dims.heatSetInsert.holeDiameter=${ih}; Hackpad resources say 4.7 mm hole, 4 mm deep for the kit inserts`);

// ---------------------------------------------------------------- 6. report
let hardTotal = 0, softTotal = 0;
for (const b of buckets.values()) (b.sev === HARD ? (hardTotal += b.count) : (softTotal += b.count));
const L_ = [];
const w = s => L_.push(s);
const stubs = loads.filter(l => l.stub).map(l => l.file);
w('# Frostbite Studio verification report');
w('');
w(`Generated ${new Date().toISOString()} by \`node verify/run.js\` (seed ${SEED}, ${N_RANDOM} random specs, Node ${process.version}).`);
w('');
w(`**Result: ${hardTotal ? 'FAIL' : 'PASS'}** — ${hardTotal} hard failures, ${softTotal} warnings.` + (stubs.length ? ` Modules still marked as stubs: ${stubs.map(s => '`' + s + '`').join(', ')}; failures tagged **[stub]** come from placeholder code and are expected until those agents land.` : ''));
w('');
w('## Modules');
w('');
w('| file | loaded | stub | bytes | note |');
w('|---|---|---|---|---|');
loads.forEach(l => w(`| ${l.file} | ${l.ok ? 'yes' : '**no**'} | ${l.stub ? 'stub' : '-'} | ${l.bytes} | ${l.error ? 'error: ' + l.error.replace(/\|/g, '\\|') : l.missing.length ? 'missing FB.' + l.missing.join(', FB.') : ''} |`));
w('');
const src = tests.reduce((m, t) => (m[t.source.split(':')[0]] = (m[t.source.split(':')[0]] || 0) + 1, m), {});
w('## Test set');
w('');
w(`${tests.length} specs: ${Object.entries(src).map(([k, v]) => `${v} ${k}`).join(', ')}. Exhaustive = layout × plate × glowPlace × bezel × corner with other axes at defaultSpec. Robustness specs (empty statuses, \`&<>\` in wordmark, extremes) only produce warnings.`);
w('');
w('## Summary');
w('');
w('| check family | checks | hard | soft | status |');
w('|---|---|---|---|---|');
for (const [f, v] of families) w(`| ${f} | ${v.run} | ${v.hard} | ${v.soft} | ${v.hard ? 'FAIL' : v.soft ? 'warn' : 'pass'} |`);
w('');
w('## FB.check outcomes');
w('');
w(`Strict specs checked: ${okCount} ok, ${rejCount} rejected (${expectedGeoRejections} rejected specs also have geometry issues, i.e. correctly rejected).`);
const tally = m => [...m.entries()].sort((a, b) => b[1] - a[1]).map(([k, v]) => `\`${k}\` ×${v}`).join(', ') || 'none';
w('');
w(`- Error codes: ${tally(checkCodes.errors)}`);
w(`- Warning codes: ${tally(checkCodes.warnings)}`);
w('');
w('## SVG output');
w('');
w('| render | stub | renders | min bytes | avg bytes | max bytes |');
w('|---|---|---|---|---|---|');
for (const [k, s] of Object.entries(svgStats)) w(`| ${k} | ${stubOf(k.split('+')[0]) ? 'stub' : '-'} | ${s.n} | ${s.min} | ${Math.round(s.sum / Math.max(1, s.n))} | ${s.max} |`);
if (offPalette.size) {
  w('');
  w(`Colours not in \`FB.catalog.palette\` (info only; contract says renderers read palette colours): ${[...offPalette.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([c, n]) => `\`${c}\` ×${n}`).join(', ')}`);
}
w('');
w('## Geometry per layout');
w('');
w(`Assumptions: cap footprint ${G.cap} mm, switch housing ${G.swBody} mm, knob Ø${G.knobD}, EC11 body ${G.ec11} mm, OLED board ${G.om.w}×${G.om.h} under the window (glass edge aligned, header end either side), XIAO ${G.xiao.w}×${G.xiao.h} on the underside at an edge, insert boss Ø${r2(G.insertHole + 2 * G.minWall)}. Top-side parts need ≥ ${G.topClear} mm to each other and to the shell outline; under-plate parts need ≥ ${r2(G.minWall + G.tol)} mm (wall + print tolerance) to the outline.`);
w('');
w('| layout | content W×H | min top clearance | worst edge distance (any bezel/corner) | OLED board | XIAO (underside) | insert corners b6 / b9 / b12 (worst corner radius) |');
w('|---|---|---|---|---|---|---|');
if (FB.layouts) for (const L of FB.layouts) {
  const g = geoLayout(L);
  let worst = { d: Infinity };
  for (const b of opts().bezel) for (const c of opts().corner) { const gc = geoCombo(L, b, c); if (gc.eff.d < worst.d) worst = { d: gc.eff.d, what: gc.eff.what, b, c }; }
  const ins = opts().bezel.map(b => Math.min(...opts().corner.map(c => geoCombo(L, b, c).okCorners)) + '/4').join(' / ');
  const ol = g.oled ? `${g.oled.orient}${g.oled.score ? ` **overhang ${r2(g.oled.over)}${g.oled.hits.length ? ', hits ' + g.oled.hits.join(' ') : ''}**` : ' ok'}` : 'none';
  const xi = g.xiao ? `${g.xiao.edge} @ ${r2(g.xiao.edge === 'back' ? g.xiao.r.x : g.xiao.r.y)}${g.xiao.under ? ' **under OLED**' : ''}` : '**no room**';
  w(`| ${L.id} | ${r2(L.W)}×${r2(L.H)} | ${r2(g.minClear.d)} (${g.minClear.pair}) | ${r2(worst.d)} (${worst.what}, b${worst.b}/r${worst.c}) | ${ol} | ${xi} | ${ins} |`);
}
w('');
const section = (sev, title) => {
  const list = [...buckets.values()].filter(b => b.sev === sev).sort((a, b) => b.count - a.count);
  w(`## ${title} (${list.reduce((a, b) => a + b.count, 0)})`);
  w('');
  if (!list.length) { w('None.'); w(''); return; }
  for (const b of list) {
    w(`### \`${b.type}\` ×${b.count} — ${b.family}`);
    b.examples.forEach(e => w(`- ${e.msg.replace(/\n/g, ' ')}${e.spec ? ` — spec: \`${e.spec}\`` : ''}`));
    w('');
  }
};
section(HARD, 'Hard failures');
section(SOFT, 'Warnings');
w('## How to read this');
w('');
w('- `checker-gap:*` = FB.check said ok but the geometry check found a physical problem: constraints.js should reject or warn.');
w('- `geometry (shell)` warnings list every layout × bezel × corner combination with a problem, whether or not FB.check approves it.');
w('- `[stub]` = the renderer file still says it is a stub; re-run after Agents A/C land.');
fs.writeFileSync(OUT, L_.join('\n') + '\n');

console.log(`frostbite verify: ${tests.length} specs, ${hardTotal} hard, ${softTotal} soft -> ${path.relative(process.cwd(), OUT)}`);
for (const [f, v] of families) console.log(`  ${(v.hard ? 'FAIL' : v.soft ? 'warn' : 'pass').padEnd(4)} ${f.padEnd(22)} checks=${v.run} hard=${v.hard} soft=${v.soft}`);
process.exitCode = hardTotal ? 1 : 0;
