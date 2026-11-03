(function (root) {
  const FB = root.FB = root.FB || {};
  const P = (FB.dims && FB.dims.pitch) || 19.05;
  const STRIP = 22;
  const W3 = 3 * P, W4 = 4 * P;
  // OLED window x positions keep the whole 38 mm module board (glass inset 3.5 mm from the end
  // opposite the header) inside the content area and clear of the EC11 bodies.
  const OLED_L = 4, OLED_R = W3 - 34, SIDE = 38.6;

  function grid(cols, rows, x0, y0, roleFn) {
    const out = [];
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) out.push({ x: x0 + c * P, y: y0 + r * P, role: roleFn(c, r) });
    return out;
  }
  const twoAgentRows = (c, r) => (r < 2 ? "agent" : "command");
  const allAgent = () => "agent";

  FB.layouts = [
    { id: "stratum9", name: "Frostbite 9", blurb: "The base design. OLED left, dial right, 6 agent slots over Approve / Talk / Stop.",
      W: W3, H: STRIP + 3 * P, keys: grid(3, 3, 0, STRIP, twoAgentRows),
      dials: [{ x: W3 - 10, y: 11 }], oled: { x: OLED_L, y: 5.25, w: 30, h: 11.5 },
      pins: { matrix: 6, dial: 2, oled: 2, led: 1 }, matrix: "3×3", dialPress: false },
    { id: "mirror9", name: "Mirror 9", blurb: "Same parts, dial on the left for a left-hand-on-pad setup.",
      W: W3, H: STRIP + 3 * P, keys: grid(3, 3, 0, STRIP, twoAgentRows),
      dials: [{ x: 10, y: 11 }], oled: { x: OLED_R, y: 5.25, w: 30, h: 11.5 },
      pins: { matrix: 6, dial: 2, oled: 2, led: 1 }, matrix: "3×3", dialPress: false },
    { id: "pocket6", name: "Pocket 6", blurb: "Only the 6 agent slots. The dial press becomes Approve.",
      W: W3, H: STRIP + 2 * P, keys: grid(3, 2, 0, STRIP, allAgent),
      dials: [{ x: W3 - 10, y: 11 }], oled: { x: OLED_L, y: 5.25, w: 30, h: 11.5 },
      pins: { matrix: 6, dial: 2, oled: 2, led: 1 }, matrix: "2×4 (7 used)", dialPress: true },
    { id: "stagger9", name: "Stagger 9", blurb: "Columns staggered like a split keyboard for a hand-shaped look.",
      W: W3, H: STRIP + 3 * P + 7,
      keys: grid(3, 3, 0, STRIP, twoAgentRows).map(k => ({ ...k, y: k.y + [7, 0, 3.5][Math.round(k.x / P)] })),
      dials: [{ x: W3 - 10, y: 11 }], oled: { x: OLED_L, y: 5.25, w: 30, h: 11.5 },
      pins: { matrix: 6, dial: 2, oled: 2, led: 1 }, matrix: "3×3", dialPress: false },
    { id: "twin9", name: "Twin 9", blurb: "Second encoder instead of the OLED. One dial picks slots, one scrolls.",
      W: W3, H: STRIP + 3 * P, keys: grid(3, 3, 0, STRIP, twoAgentRows),
      dials: [{ x: 10, y: 11 }, { x: W3 - 10, y: 11 }], oled: null,
      pins: { matrix: 6, dial: 4, oled: 0, led: 1 }, matrix: "3×3", dialPress: false },
    { id: "wide9", name: "Wide 9", blurb: "Landscape. Keys on the left, a control column with OLED and dial on the right.",
      W: W3 + SIDE, H: 3 * P, keys: grid(3, 3, 0, 0, twoAgentRows),
      dials: [{ x: W3 + SIDE / 2, y: 38 }], oled: { x: W3 + 3.8, y: 3, w: 30, h: 11.5 },
      pins: { matrix: 6, dial: 2, oled: 2, led: 1 }, matrix: "3×3", dialPress: false },
    { id: "console4", name: "Console 4", blurb: "Four big agent slots under an OLED flanked by two dials.",
      W: W4, H: STRIP + P, keys: grid(4, 1, 0, STRIP, allAgent),
      dials: [{ x: 10, y: 11 }, { x: W4 - 10, y: 11 }], oled: { x: 21, y: 5.25, w: 30, h: 11.5 },
      pins: { matrix: 4, dial: 4, oled: 2, led: 1 }, matrix: "4 direct", dialPress: false }
  ];
  FB.layoutById = id => FB.layouts.find(l => l.id === id) || FB.layouts[0];
  if (typeof module !== "undefined" && module.exports) module.exports = FB.layouts;
})(typeof window !== "undefined" ? window : globalThis);
