// Renders the default Frostbite spec to SVGs for the README.
// Usage: node studio/tools/export-images.js <out-dir>
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
for (const f of ["dims", "layouts", "catalog", "constraints", "render-top", "render-side"]) require(path.join(root, f + ".js"));
const FB = globalThis.FB;

const out = path.resolve(process.argv[2] || path.join(root, "..", "docs", "images"));
fs.mkdirSync(out, { recursive: true });

const spec = FB.catalog.defaultSpec;
const views = {
  "top": FB.renderTop(spec, { idPrefix: "top" }),
  "top-dims": FB.renderTop(spec, { idPrefix: "topd", dims: true }),
  "side": FB.renderSide(spec, { idPrefix: "side", dims: true }),
  "exploded": FB.renderExploded(spec, { idPrefix: "exp" })
};
for (const [name, svg] of Object.entries(views)) {
  if (/NaN|undefined/.test(svg)) throw new Error(`${name}: bad SVG output`);
  fs.writeFileSync(path.join(out, `${name}.svg`), svg);
  console.log(`${name}.svg ${svg.length} bytes`);
}
