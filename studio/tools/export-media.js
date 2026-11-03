// Renders SVG sources for the README media (status animation + presets grid).
// Usage: node studio/tools/export-media.js <out-dir>
// Writes <out-dir>/frames/frame-NN.svg and <out-dir>/presets/NN-<id>.svg plus
// <out-dir>/media.json (frame list and preset names). Rasterise and assemble
// them with studio/tools/make_media.py.
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
for (const f of ["dims", "layouts", "catalog", "constraints", "render-top", "render-side"]) require(path.join(root, f + ".js"));
const FB = globalThis.FB;

const out = path.resolve(process.argv[2] || "media-src");
for (const d of ["frames", "presets"]) fs.mkdirSync(path.join(out, d), { recursive: true });

// Six agent keys, eight beats: everything idle, agents start, one asks for
// input (amber), it resumes, one fails (red), the rest finish (green).
const story = [
  ["idle", "idle", "idle", "idle", "idle", "idle"],
  ["run", "run", "idle", "run", "idle", "run"],
  ["run", "run", "run", "needs", "idle", "run"],
  ["needs", "run", "run", "needs", "run", "run"],
  ["run", "done", "run", "run", "run", "run"],
  ["run", "done", "error", "run", "run", "done"],
  ["done", "done", "error", "run", "needs", "done"],
  ["done", "done", "error", "done", "run", "done"]
];

function check(name, svg) {
  if (/NaN|undefined/.test(svg)) throw new Error(`${name}: bad SVG output`);
  return svg;
}

const media = { frames: [], presets: [] };
const base = FB.catalog.defaultSpec;
story.forEach((want, t) => {
  // renderTop shows statuses[(i + t) % n] on agent i and cycles the OLED
  // through slot t % n, so rotate the list by -t to pin each key's colour.
  const n = want.length;
  const statuses = want.map((_, j) => want[(((j - t) % n) + n) % n]);
  const svg = check(`frame ${t}`, FB.renderTop(Object.assign({}, base, { statuses }), { idPrefix: "f" + t, t }));
  const file = `frames/frame-${String(t).padStart(2, "0")}.svg`;
  fs.writeFileSync(path.join(out, file), svg);
  media.frames.push(file);
});

const pick = ["frostbite", "polar-night", "lilac-haze", "mint-wide",
  "ember-frost", "console", "blue-hour", "stagger",
  "night-shift", "lilac-pocket", "deep-dish", "twin-halo"];
pick.forEach((id, i) => {
  const p = FB.catalog.presets.find(x => x.id === id);
  if (!p) throw new Error(`no preset ${id}`);
  const svg = check(id, FB.renderTop(p.spec, { idPrefix: "p" + i }));
  const file = `presets/${String(i).padStart(2, "0")}-${id}.svg`;
  fs.writeFileSync(path.join(out, file), svg);
  media.presets.push({ file, id, name: p.name });
});

fs.writeFileSync(path.join(out, "media.json"), JSON.stringify(media, null, 2));
console.log(`${media.frames.length} frames, ${media.presets.length} presets -> ${out}`);
