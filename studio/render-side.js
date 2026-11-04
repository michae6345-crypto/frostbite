(function (root) {
  const FB = root.FB = root.FB || {};
  // Side elevation and exploded stack.
  //
  // Stack in mm, measured perpendicular to the plate from the case underside:
  //   floor 2.0, XIAO cavity (xiao.t + 1.5), PCB, then plate top zP = PCB top + switchHeightBelowPlate.
  //   Top shell: slab from zP - 4 up to zP, +8 rim for deep-dish, +3 lip for tray.
  //   Gap between bottom-shell rim and top shell: floating 3.2, else 1.6 if glowPlace = gap, else 0.
  //   Knob top = PCB top + ec11.shaftAbovePcb + 0.5, so the knob covers the shaft tip.
  // Tilt: the bottom is a wedge flat on the desk and everything above it is rotated about the front edge,
  // so body-plane z at distance X from the front has height Y = lift + z / cos(t) + X * tan(t).
  // lift is the 2 mm light-guide foot when glowPlace = base.

  let PREC = 100;   // 2 decimals for the side view, 1 for the larger exploded view
  function num(n) {
    if (typeof n !== "number" || !isFinite(n)) return "0";
    const r = Math.round(n * PREC) / PREC;
    return String(r === 0 ? 0 : r);
  }
  const pt = p => num(p[0]) + " " + num(p[1]);
  const esc = s => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const FONT = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif";

  function rgb(h) {
    let s = String(h || "").replace("#", "");
    if (s.length === 3) s = s.split("").map(c => c + c).join("");
    const n = parseInt(s.slice(0, 6), 16);
    return isFinite(n) ? [(n >> 16) & 255, (n >> 8) & 255, n & 255] : [136, 136, 136];
  }
  function mix(a, b, t) {
    const A = rgb(a), B = rgb(b);
    return "#" + A.map((v, i) => clamp(Math.round(v + (B[i] - v) * t), 0, 255).toString(16).padStart(2, "0")).join("");
  }
  const first = o => o[Object.keys(o)[0]];
  const pick = (o, k) => (o && o[k] !== undefined ? o[k] : first(o));

  function norm(spec) {
    const def = FB.catalog.defaultSpec, O = FB.catalog.options;
    const s = Object.assign({}, def, spec || {});
    for (const k of Object.keys(O)) {
      if (k === "tilt" || k === "corner" || k === "bezel") continue;
      if (!O[k].includes(s[k])) s[k] = O[k].includes(def[k]) ? def[k] : O[k][0];
    }
    const n = (v, d, lo, hi) => { v = Number(v); return isFinite(v) ? clamp(v, lo, hi) : d; };
    s.tilt = n(s.tilt, 0, 0, 20);
    s.corner = n(s.corner, 8, 0, 40);
    s.bezel = n(s.bezel, 9, 3, 30);
    s.statuses = Array.isArray(s.statuses) && s.statuses.length ? s.statuses : ["idle"];
    return s;
  }

  function D() {
    const d = FB.dims, ed = d.ec11Detail;
    return {
      pitch: d.pitch, cut: d.switchCutout, plateT: d.plateThickness, pcbT: d.pcbThickness,
      above: d.switchHeightAbovePlate, below: d.switchHeightBelowPlate, capBottom: d.capBottom,
      capTopDSA: d.capTopDSA, capTopXDA: d.capTopXDA, capHDSA: d.capHeightDSA, capHXDA: d.capHeightXDA,
      oledW: d.oledModule.w, oledH: d.oledModule.h, oledAW: d.oledActive.w, oledAH: d.oledActive.h,
      ecBody: d.ec11.body, shaft: d.ec11.shaftAbovePcb, knobD: d.ec11.knobDiameter,
      xiaoW: d.xiao.w, xiaoH: d.xiao.h, xiaoT: d.xiao.t, ledW: d.sk6812MiniE.w, ledH: d.sk6812MiniE.h,
      insOD: d.heatSetInsert.od, m3Head: d.m3Head, stemAbove: d.switchStemAboveHousing,
      capRim: d.capRimAbovePlate, knobH: d.knobTypical.height,
      ecBodyH: ed.bodyH, bushD: ed.bushingDiameter, bushH: ed.bushingHeight, shaftD: ed.shaftDiameter,
      usbW: d.xiaoUsbC.w, usbH: d.xiaoUsbC.h, usbOver: d.xiaoUsbC.overhang,
      bossOD: d.heatSetBossOd, m3HeadH: d.m3HeadHeight, m3Len: d.m3ScrewLength,
      oledTopAbovePcb: d.oledGlassTopAbovePcb, sideWallExtra: d.sideWallExtra
    };
  }

  function colors(s) {
    const pal = FB.catalog.palette, status = pal.status;
    const sh = pick(pal.shell, s.shell), ink = pal.shell.smoke.edge, white = pal.glow.white;
    const alu = pal.knob["knurled-alu"];
    return {
      sh, ink, white, status,
      glow: pick(pal.glow, s.glowColor),
      knob: pick(pal.knob, s.knob),
      oled: pick(pal.oled, s.oledColor),
      cmd: pick(pal.commandCap, s.commandCap),
      agentBase: pick(pal.agentCapBase, s.agentCap),
      pcb: mix(status.done, ink, 0.62),
      pad: mix(pal.glow.warm, status.needs, 0.45),
      brass: mix(status.needs, ink, 0.25),
      metal: alu.ring,
      metalLight: alu.face,
      housing: mix(pal.agentCapBase.milky, sh.edge, 0.25),
      stem: status.needs
    };
  }
  function statusOf(s, i, t) {
    const n = s.statuses.length;
    return s.statuses[(((i + (t | 0)) % n) + n) % n];
  }
  function busiest(s, t) {
    const order = ["error", "needs", "run", "done", "idle"];
    let best = 99, which = "idle";
    for (let i = 0; i < s.statuses.length; i++) {
      const st = statusOf(s, i, t), r = order.indexOf(st);
      if (r >= 0 && r < best) { best = r; which = st; }
    }
    return which;
  }
  const valueName = (axis, v) => FB.catalog.valueLabel(axis, v);

  function geom(spec) {
    const s = norm(spec);
    const L = FB.layoutById(s.layout);
    const d = D();
    const b = s.bezel, depth = L.H + 2 * b, width = L.W + 2 * (b + d.sideWallExtra);
    const t = s.tilt * Math.PI / 180, cos = Math.cos(t), sin = Math.sin(t), tan = Math.tan(t);
    const floor = 2.0;
    const pcbBot = floor + d.xiaoT + 1.5, pcbTop = pcbBot + d.pcbT;
    const zP = pcbTop + d.below, plateBot = zP - d.plateT;
    const topBot = zP - 4;
    const gap = s.plate === "floating" ? 3.2 : (s.glowPlace === "gap" ? 1.6 : 0);
    const rimZ = topBot - gap;
    const rimH = s.plate === "deep-dish" ? 8 : s.plate === "tray" ? 3 : 0;
    const topZ = zP + rimH;
    const lift = s.glowPlace === "base" ? 2 : 0;
    const xda = s.capProfile === "XDA";
    const cap = { h: xda ? d.capHXDA : d.capHDSA, top: xda ? d.capTopXDA : d.capTopDSA, bottom: d.capBottom, v0: d.capRim, dish: xda ? 0.45 : 0.9, r: xda ? 1.6 : 2.4 };
    const knobTopV = pcbTop + d.shaft + 0.5 - zP;
    const puck = s.knob === "puck";
    const kh = puck ? 8 : s.knob === "soft-white" ? d.knobH - 1 : d.knobH;
    const knob = { r: (puck ? d.knobD * 1.3 : d.knobD) / 2, vt: knobTopV, vb: Math.max(1, knobTopV - kh) };
    const Y = (X, z) => lift + z / cos + X * tan;
    const P = d.pitch;
    const keys = L.keys.map((k, i) => ({ ...k, i, dc: b + (L.H - (k.y + P / 2)), cx: k.x + P / 2, cy: k.y + P / 2 }));
    let ai = 0; keys.forEach(k => { k.ai = k.role === "agent" ? ai++ : -1; });
    const dials = L.dials.map(q => ({ ...q, dc: b + (L.H - q.y) }));
    // world position of a point in a part's local frame (u along the plate, v up from plate top)
    const world = (dc, u, v) => [dc + u * cos - v * sin, Y(dc, zP) + u * sin + v * cos];
    // screw / boss inset from the outer corner, kept inside the rounded outline
    const wall = 2.4, bossR = d.bossOD / 2, e = wall + bossR - 1;
    const rr = Math.min(s.corner, width / 2, depth / 2);
    const q = rr > e ? Math.max(e, rr - (rr - e) / Math.SQRT2) : e;
    // XIAO on the PCB underside: centred under the top strip (or the control column), USB-C at the back edge
    const keyTop = Math.min(...L.keys.map(k => k.y));
    const xiaoCx = keyTop >= 20 ? L.W / 2 : (Math.max(...L.keys.map(k => k.x)) + P + L.W) / 2;
    const xiao = [clamp(xiaoCx - d.xiaoW / 2, -2, L.W + 2 - d.xiaoW), -1.2, d.xiaoW, d.xiaoH];
    return { xiao, s, L, d, b, depth, width, t, cos, sin, tan, floor, pcbBot, pcbTop, plateBot, zP, topBot, gap, rimZ, rimH, topZ, lift,
      cap, knob, Y, keys, dials, world, wall, bossR, q, rr };
  }

  function stats(g) {
    let maxH = Math.max(g.Y(0, g.topZ), g.Y(g.depth, g.topZ)), frontKey = 0, frontDc = Infinity;
    g.keys.forEach(k => {
      const hw = g.cap.top / 2, v = g.cap.v0 + g.cap.h;
      const top = Math.max(g.world(k.dc, -hw, v)[1], g.world(k.dc, hw, v)[1]);
      maxH = Math.max(maxH, top);
      if (k.dc < frontDc) { frontDc = k.dc; frontKey = top; }
    });
    g.dials.forEach(q => {
      const top = Math.max(g.world(q.dc, -g.knob.r, g.knob.vt)[1], g.world(q.dc, g.knob.r, g.knob.vt)[1]);
      maxH = Math.max(maxH, top);
    });
    const r1 = x => Math.round(x * 10) / 10;
    return {
      frontHeight: r1(g.Y(0, g.topZ)),       // case top at the front edge, caps excluded
      backHeight: r1(g.Y(g.depth, g.topZ)),  // case top at the back edge, caps excluded
      depth: r1(g.depth),
      maxHeight: r1(maxH),                   // highest cap or knob
      frontKeyTop: r1(frontKey)              // top of the front-row caps
    };
  }

  function roundPoly(pts, radii) {
    const n = pts.length; let d = "";
    for (let i = 0; i < n; i++) {
      const P = pts[i], A = pts[(i - 1 + n) % n], B = pts[(i + 1) % n];
      const la = Math.hypot(A[0] - P[0], A[1] - P[1]), lb = Math.hypot(B[0] - P[0], B[1] - P[1]);
      const r = Math.min(radii[i] || 0, la / 2, lb / 2);
      if (r < 0.02 || la === 0 || lb === 0) { d += (i ? "L" : "M") + pt(P); continue; }
      const p1 = [P[0] + (A[0] - P[0]) * r / la, P[1] + (A[1] - P[1]) * r / la];
      const p2 = [P[0] + (B[0] - P[0]) * r / lb, P[1] + (B[1] - P[1]) * r / lb];
      d += (i ? "L" : "M") + pt(p1) + "Q" + pt(P) + " " + pt(p2);
    }
    return d + "Z";
  }

  FB.renderSide = function (spec, opts) {
    opts = opts || {};
    const p = String(opts.idPrefix || "side");
    const g = geom(spec), s = g.s, c = colors(s), d = g.d, L = g.L;
    const st = stats(g);
    const Dp = g.depth, deg = s.tilt;
    const defs = [], out = [];
    const sv = Y => -Y;                                     // world height -> svg y
    const darkShell = (rgb(c.sh.base).reduce((a, v) => a + v, 0) / 3) < 110;

    // band between body planes za..zb across X0..X1 (vertical ends); za null => desk/lift level
    function slab(x0, x1, za, zb, rt, rb, floorY) {
      const ya0 = za == null ? floorY : g.Y(x0, za), ya1 = za == null ? floorY : g.Y(x1, za);
      return roundPoly([[x0, sv(ya0)], [x0, sv(g.Y(x0, zb))], [x1, sv(g.Y(x1, zb))], [x1, sv(ya1)]], [rb, rt, rt, rb]);
    }
    // gradient running perpendicular to the plate (from plane za down/up to zb) at mid-depth
    function perpGrad(id, za, zb, stops) {
      const xm = Dp / 2, A = [xm, sv(g.Y(xm, za))];
      const dz = zb - za, B = [xm - dz * g.sin, sv(g.Y(xm, za)) - dz * g.cos];
      defs.push(`<linearGradient id="${p}-${id}" gradientUnits="userSpaceOnUse" x1="${num(A[0])}" y1="${num(A[1])}" x2="${num(B[0])}" y2="${num(B[1])}">` +
        stops.map(([o, col, a]) => `<stop offset="${o}" stop-color="${col}" stop-opacity="${a}"/>`).join("") + `</linearGradient>`);
      return `url(#${p}-${id})`;
    }

    const cr = Math.min(s.corner, Dp / 3), cf = num(cr / Dp);
    defs.push(`<filter id="${p}-blur" x="-30%" y="-300%" width="160%" height="700%"><feGaussianBlur stdDeviation="1.4"/></filter>`);
    defs.push(`<filter id="${p}-soft" x="-30%" y="-600%" width="160%" height="1300%"><feGaussianBlur stdDeviation="2.4"/></filter>`);
    defs.push(`<filter id="${p}-sm" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="0.8"/></filter>`);
    defs.push(`<linearGradient id="${p}-bshell" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c.sh.top}"/><stop offset="1" stop-color="${mix(c.sh.base, c.sh.edge, 0.6)}"/></linearGradient>`);
    defs.push(`<linearGradient id="${p}-tshell" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${mix(c.sh.top, c.white, 0.35)}"/><stop offset="1" stop-color="${c.sh.base}"/></linearGradient>`);
    defs.push(`<linearGradient id="${p}-ends" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="${num(Dp)}" y2="0">` +
      `<stop offset="0" stop-color="${c.ink}" stop-opacity="0.26"/><stop offset="${cf}" stop-color="${c.ink}" stop-opacity="0"/>` +
      `<stop offset="${num(1 - cr / Dp)}" stop-color="${c.ink}" stop-opacity="0"/><stop offset="1" stop-color="${c.ink}" stop-opacity="0.3"/></linearGradient>`);
    defs.push(`<linearGradient id="${p}-metal" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${mix(c.metal, c.ink, 0.35)}"/><stop offset="0.35" stop-color="${c.metalLight}"/><stop offset="0.55" stop-color="${mix(c.metalLight, c.white, 0.6)}"/><stop offset="1" stop-color="${mix(c.metal, c.ink, 0.45)}"/></linearGradient>`);
    let texFill = "";
    if (s.texture === "layer-lines") {
      defs.push(`<pattern id="${p}-tex" width="6" height="0.7" patternUnits="userSpaceOnUse"><rect width="6" height="0.28" fill="${darkShell ? c.white : c.ink}" opacity="${darkShell ? 0.08 : 0.07}"/></pattern>`);
      texFill = `url(#${p}-tex)`;
    } else if (s.texture === "speckle") {
      defs.push(`<pattern id="${p}-tex" width="7" height="5" patternUnits="userSpaceOnUse"><circle cx="1" cy="1.2" r="0.28" fill="${c.ink}" opacity="0.28"/><circle cx="4.6" cy="3.4" r="0.22" fill="${c.ink}" opacity="0.22"/><circle cx="3" cy="0.6" r="0.2" fill="${c.white}" opacity="0.5"/><circle cx="6.1" cy="4.4" r="0.25" fill="${c.ink}" opacity="0.18"/></pattern>`);
      texFill = `url(#${p}-tex)`;
    }
    const finish = dd => (texFill ? `<path d="${dd}" fill="${texFill}"/>` : "") + `<path d="${dd}" fill="url(#${p}-ends)"/>`;
    const op = c.sh.opacity == null ? 1 : c.sh.opacity;

    // desk, shadow, halo
    const mL = opts.dims ? 25 : 7, mR = opts.dims ? 26 : 7;
    out.push(`<rect x="${num(-mL)}" y="0" width="${num(Dp + mL + mR)}" height="3.5" fill="${c.sh.edge}" opacity="0.12"/>`);
    out.push(`<line x1="${num(-mL)}" y1="0" x2="${num(Dp + mR)}" y2="0" stroke="${c.sh.edge}" stroke-width="0.3" opacity="0.8"/>`);
    out.push(`<ellipse cx="${num(Dp / 2)}" cy="0.3" rx="${num(Dp / 2 + 3)}" ry="1.6" fill="${c.ink}" opacity="0.32" filter="url(#${p}-soft)"/>`);
    if (s.glowPlace === "base") {
      out.push(`<ellipse cx="${num(Dp / 2)}" cy="0.4" rx="${num(Dp / 2 + 6)}" ry="2.6" fill="${c.glow}" opacity="0.85" filter="url(#${p}-soft)"/>`);
      out.push(`<rect x="2.5" y="${num(-g.lift)}" width="${num(Dp - 5)}" height="${num(g.lift)}" fill="${c.glow}"/>`);
      out.push(`<rect x="3.5" y="${num(-g.lift * 0.62)}" width="${num(Dp - 7)}" height="${num(g.lift * 0.3)}" fill="${c.white}" opacity="0.75"/>`);
    }
    out.push(`<rect x="1" y="-0.5" width="${num(Dp - 2)}" height="0.6" fill="${c.ink}" opacity="${s.glowPlace === "base" ? 0.12 : 0.35}" filter="url(#${p}-sm)"/>`);

    // internals seen through a translucent shell
    if (op < 0.97) {
      const ghost = 0.9 - op * 0.75;
      out.push(`<path d="${slab(g.b - 2, Dp - g.b + 2, g.pcbBot, g.pcbTop, 0, 0)}" fill="${c.pcb}" opacity="${num(ghost)}"/>`);
      const xd = g.b + L.H - (g.xiao[1] + g.xiao[3] / 2);
      out.push(`<path d="${slab(clamp(xd - d.xiaoH / 2, 3, Dp - 3), clamp(xd + d.xiaoH / 2, 3, Dp - 3), g.pcbBot - d.xiaoT, g.pcbBot, 0, 0)}" fill="${c.ink}" opacity="${num(ghost * 0.8)}"/>`);
    }

    // bottom shell (wedge)
    const bTopR = s.plate === "floating" || s.glowPlace === "gap" ? 1.0 : 0.4;
    const bshell = slab(0, Dp, null, g.rimZ, bTopR, 0.8, g.lift);
    out.push(`<path d="${bshell}" fill="url(#${p}-bshell)" fill-opacity="${op}" stroke="${c.sh.edge}" stroke-width="0.25"/>`);
    out.push(finish(bshell));
    if (s.glowPlace === "band") {
      const z0 = g.rimZ * 0.45 - 1.2, z1 = z0 + 2.4;
      out.push(`<path d="${slab(0, Dp, z0 - 1.2, z1 + 1.2, 0, 0)}" fill="${c.glow}" opacity="0.55" filter="url(#${p}-blur)"/>`);
      out.push(`<path d="${slab(0, Dp, z0, z1, 0, 0)}" fill="${c.glow}"/>`);
      out.push(`<path d="${slab(0.6, Dp - 0.6, z0 + 0.8, z1 - 0.8, 0, 0)}" fill="${c.white}" opacity="0.7"/>`);
    }
    if (s.glowPlace === "gap") {
      out.push(`<path d="${slab(0, Dp, g.rimZ - 6, g.rimZ, 0, 0)}" fill="${perpGrad("spill", g.rimZ, g.rimZ - 6, [[0, c.glow, op >= 1 && darkShell ? 0.1 : 0.55], [1, c.glow, 0]])}"/>`);
    }
    if (s.screws === "side") {
      const zs = g.rimZ * 0.55;
      [g.q, Dp - g.q].forEach(X => {
        const y = sv(g.Y(X, zs)), r = d.m3Head / 2;
        out.push(`<circle cx="${num(X)}" cy="${num(y)}" r="${num(r)}" fill="${c.metalLight}" stroke="${c.metal}" stroke-width="0.3"/>` +
          `<path d="M${num(X - 1.1)} ${num(y - 0.64)}L${num(X)} ${num(y - 1.27)}L${num(X + 1.1)} ${num(y - 0.64)}L${num(X + 1.1)} ${num(y + 0.64)}L${num(X)} ${num(y + 1.27)}L${num(X - 1.1)} ${num(y + 0.64)}Z" fill="${c.ink}" opacity="0.7"/>`);
      });
    }
    // top-edge highlight of the bottom shell
    out.push(`<path d="M${num(1.2)} ${num(sv(g.Y(1.2, g.rimZ)) + 0.25)}L${num(Dp - 1.2)} ${num(sv(g.Y(Dp - 1.2, g.rimZ)) + 0.25)}" stroke="${c.white}" stroke-width="0.35" opacity="${darkShell ? 0.25 : 0.7}"/>`);

    // light gap or dark gap
    if (g.gap > 0) {
      if (s.glowPlace === "gap") {
        out.push(`<path d="${slab(-1, Dp + 1, g.rimZ - 1.5, g.topBot + 1.5, 0, 0)}" fill="${c.glow}" opacity="0.6" filter="url(#${p}-blur)"/>`);
        out.push(`<path d="${slab(0.8, Dp - 0.8, g.rimZ, g.topBot, 0, 0)}" fill="${c.glow}"/>`);
        out.push(`<path d="${slab(1.5, Dp - 1.5, g.rimZ + g.gap * 0.32, g.topBot - g.gap * 0.32, 0, 0)}" fill="${c.white}" opacity="0.8"/>`);
      } else {
        out.push(`<path d="${slab(1.5, Dp - 1.5, g.rimZ, g.topBot, 0, 0)}" fill="${c.ink}" opacity="0.5"/>`);
        [g.q, Dp - g.q].forEach(X => out.push(`<path d="${slab(X - 2.6, X + 2.6, g.rimZ, g.topBot, 0, 0)}" fill="${c.sh.edge}"/>`));
      }
    }

    // switches, caps and knobs, far column first
    const tf = dc => { const a = g.world(dc, 0, 0); return `translate(${num(a[0])} ${num(-a[1])}) rotate(${num(-deg)})`; };
    const usedStatus = {};
    const parts = [];
    g.keys.forEach(k => parts.push({ x: k.cx, kind: "key", k }));
    g.dials.forEach(q => parts.push({ x: q.x, kind: "dial", q }));
    parts.sort((a, b) => b.x - a.x);
    const cap = g.cap, bw = cap.bottom / 2, tw = cap.top / 2, v0 = cap.v0, v1 = cap.v0 + cap.h;
    const capPath = roundPoly([[-bw, -v0], [-tw, -v1], [tw, -v1], [bw, -v0]], [0.5, cap.r, cap.r, 0.5]);
    const dishPath = `M${num(-tw + cap.r * 0.6)} ${num(-v1 + 0.05)}Q0 ${num(-v1 + cap.dish * 2)} ${num(tw - cap.r * 0.6)} ${num(-v1 + 0.05)}Z`;
    const swPath = `M-7.8 0L-7.8 -1L-7.3 -1L-5.9 ${num(-d.above + 0.6)}Q-5.8 ${num(-d.above)} -5.2 ${num(-d.above)}L5.2 ${num(-d.above)}Q5.8 ${num(-d.above)} 5.9 ${num(-d.above + 0.6)}L7.3 -1L7.8 -1L7.8 0Z`;
    defs.push(`<linearGradient id="${p}-sw" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${mix(c.housing, c.ink, 0.12)}"/><stop offset="0.5" stop-color="${mix(c.housing, c.white, 0.4)}"/><stop offset="1" stop-color="${mix(c.housing, c.ink, 0.2)}"/></linearGradient>`);
    const cmdGrad = `${p}-cmd`;
    defs.push(`<linearGradient id="${cmdGrad}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${mix(c.cmd, c.white, 0.35)}"/><stop offset="1" stop-color="${mix(c.cmd, c.ink, 0.14)}"/></linearGradient>`);
    const agentGrad = stName => {
      const id = `${p}-ag-${stName}`;
      if (!usedStatus[stName]) {
        usedStatus[stName] = 1;
        const sc = c.status[stName] || c.agentBase;
        const strength = s.agentCap === "milky" ? 0.45 : s.agentCap === "clear" ? 0.8 : 0.62;
        defs.push(`<linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${mix(c.agentBase, sc, strength * 0.55)}"/><stop offset="0.7" stop-color="${mix(c.agentBase, sc, strength)}"/><stop offset="1" stop-color="${mix(sc, c.white, 0.25)}"/></linearGradient>`);
      }
      return `url(#${id})`;
    };
    const ringStatus = c.status[busiest(s, opts.t)] || c.glow;
    let knGrad = 0;
    parts.forEach(it => {
      if (it.kind === "key") {
        const k = it.k, agent = k.role === "agent";
        const stName = agent ? statusOf(s, k.ai, opts.t) : null, sc = agent ? (c.status[stName] || c.agentBase) : null;
        let o = `<g transform="${tf(k.dc)}">`;
        o += `<path d="${swPath}" fill="url(#${p}-sw)" stroke="${mix(c.housing, c.ink, 0.35)}" stroke-width="0.15"/>`;
        o += `<rect x="-2" y="${num(-v0 - 1)}" width="4" height="${num(1.4)}" fill="${c.stem}"/>`;
        if (agent) o += `<ellipse cx="0" cy="${num(-v0 + 0.6)}" rx="8.5" ry="1.4" fill="${sc}" opacity="0.65" filter="url(#${p}-sm)"/>`;
        const fill = agent ? agentGrad(stName) : `url(#${cmdGrad})`;
        const edge = agent ? mix(sc, c.ink, 0.25) : mix(c.cmd, c.ink, 0.3);
        o += `<path d="${capPath}" fill="${fill}" ${agent && s.agentCap !== "milky" ? 'fill-opacity="0.94" ' : ""}stroke="${edge}" stroke-width="0.2"/>`;
        o += `<path d="${dishPath}" fill="${agent ? mix(c.agentBase, sc, 0.25) : mix(c.cmd, c.ink, 0.08)}" opacity="0.8"/>`;
        o += `<path d="M${num(-tw + 0.9)} ${num(-v1 + 0.35)}L${num(-bw + 0.8)} ${num(-v0 - 0.4)}" stroke="${c.white}" stroke-width="0.35" opacity="0.55"/>`;
        o += `</g>`;
        out.push(o);
      } else {
        const kn = g.knob, R = kn.r, vb = kn.vb, vt = kn.vt, kc = c.knob;
        let o = `<g transform="${tf(it.q.dc)}">`;
        const bushTop = clamp(g.pcbTop + d.ecBodyH + d.bushH - g.zP, 0.5, vb + 1);
        o += `<rect x="${num(-d.shaftD / 2)}" y="${num(-vb - 1)}" width="${num(d.shaftD)}" height="${num(vb + 1)}" fill="${c.metal}"/>`;
        o += `<rect x="${num(-d.bushD / 2)}" y="${num(-bushTop)}" width="${num(d.bushD)}" height="${num(bushTop)}" fill="${mix(c.metal, c.ink, 0.3)}"/>`;
        if (s.knob === "ringlit") {
          o += `<rect x="${num(-R - 1.5)}" y="${num(-vb - 1.2)}" width="${num(2 * R + 3)}" height="3" fill="${ringStatus}" opacity="0.7" filter="url(#${p}-sm)"/>`;
        }
        const body = s.knob === "soft-white" ? roundPoly([[-R, -vb], [-R, -vt], [R, -vt], [R, -vb]], [0.6, 4, 4, 0.6])
          : s.knob === "puck" ? roundPoly([[-R, -vb], [-R, -vt + 1.6], [-R + 1.6, -vt], [R - 1.6, -vt], [R, -vt + 1.6], [R, -vb]], [0.6, 0.6, 0.6, 0.6, 0.6, 0.6])
          : roundPoly([[-R, -vb], [-R, -vt + 0.8], [-R + 0.8, -vt], [R - 0.8, -vt], [R, -vt + 0.8], [R, -vb]], [0.3, 0.2, 0.2, 0.2, 0.2, 0.3]);
        if (s.knob === "knurled-alu" || s.knob === "ringlit") {
          o += `<path d="${body}" fill="url(#${p}-metal)" stroke="${mix(c.metal, c.ink, 0.4)}" stroke-width="0.2"/>`;
          let kl = "";
          for (let u = -R + 1; u < R - 0.5; u += 1.1) kl += `M${num(u)} ${num(-vb - 0.6)}V${num(-vt + 3.2)}`;
          o += `<path d="${kl}" stroke="${mix(c.metal, c.ink, 0.45)}" stroke-width="0.28" opacity="0.55"/>`;
          o += `<rect x="${num(-R + 0.2)}" y="${num(-vt + 0.9)}" width="${num(2 * R - 0.4)}" height="1.6" fill="${c.metalLight}" opacity="0.9"/>`;
        } else {
          const fc = kc.face, rc = kc.ring;
          if (!knGrad++) defs.push(`<linearGradient id="${p}-kn" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${mix(rc, c.ink, 0.12)}"/><stop offset="0.45" stop-color="${mix(fc, c.white, 0.5)}"/><stop offset="1" stop-color="${mix(rc, c.ink, 0.2)}"/></linearGradient>`);
          o += `<path d="${body}" fill="url(#${p}-kn)" ${s.knob === "frosted" ? 'fill-opacity="0.9" ' : ""}stroke="${rc}" stroke-width="0.2"/>`;
          if (s.knob === "puck") o += `<path d="M${num(-R + 2)} ${num(-vt + 0.5)}H${num(R - 2)}" stroke="${c.white}" stroke-width="0.5" opacity="0.7"/>`;
        }
        if (s.knob === "ringlit") {
          o += `<rect x="${num(-R - 0.3)}" y="${num(-vb - 1.4)}" width="${num(2 * R + 0.6)}" height="1.4" rx="0.5" fill="${ringStatus}"/>`;
          o += `<rect x="${num(-R + 0.5)}" y="${num(-vb - 0.95)}" width="${num(2 * R - 1)}" height="0.45" fill="${c.white}" opacity="0.7"/>`;
        }
        o += `</g>`;
        out.push(o);
      }
    });

    // top shell or plate
    const tTopR = s.plate === "floating" ? 1.3 : s.plate === "flush" ? 1.0 : 1.6;
    const tBotR = g.gap > 0 ? (s.plate === "floating" ? 1.3 : 0.6) : 0;
    const tshell = slab(0, Dp, g.topBot, g.topZ, tTopR, tBotR);
    out.push(`<path d="${tshell}" fill="url(#${p}-tshell)" fill-opacity="${op}" stroke="${c.sh.edge}" stroke-width="0.25"/>`);
    out.push(finish(tshell));
    if (s.glowPlace === "gap" && g.gap > 0) {
      out.push(`<path d="${slab(0, Dp, g.topBot, g.topBot + 2.6, 0, tBotR)}" fill="${perpGrad("spillT", g.topBot, g.topBot + 2.6, [[0, c.glow, op >= 1 && darkShell ? 0.1 : 0.6], [1, c.glow, 0]])}"/>`);
    }
    if (g.gap === 0) {
      out.push(`<path d="M0.4 ${num(sv(g.Y(0.4, g.topBot)))}L${num(Dp - 0.4)} ${num(sv(g.Y(Dp - 0.4, g.topBot)))}" stroke="${c.ink}" stroke-width="0.2" opacity="0.35"/>`);
    }
    out.push(`<path d="M${num(tTopR + 0.3)} ${num(sv(g.Y(tTopR + 0.3, g.topZ)) + 0.25)}L${num(Dp - tTopR - 0.3)} ${num(sv(g.Y(Dp - tTopR - 0.3, g.topZ)) + 0.25)}" stroke="${c.white}" stroke-width="0.4" opacity="${darkShell ? 0.3 : 0.85}"/>`);
    if (s.screws === "top") {
      [g.q, Dp - g.q].forEach(X => {
        const y = sv(g.Y(X, g.topZ));
        out.push(`<path d="M${num(X - d.m3Head / 2)} ${num(y + 0.05)}h${num(d.m3Head)}" stroke="${c.metal}" stroke-width="0.6"/>`);
      });
    }

    // bloom over everything
    if (s.glowPlace === "gap" && g.gap > 0) {
      out.push(`<path d="${slab(0, Dp, g.rimZ, g.topBot, 0, 0)}" fill="${c.glow}" opacity="0.35" filter="url(#${p}-blur)"/>`);
    }

    if (opts.dims) {
      const ink = "currentColor", fs = 3.1;
      const tick = (x, y) => `<path d="M${num(x - 0.9)} ${num(y + 0.9)}L${num(x + 0.9)} ${num(y - 0.9)}" stroke="${ink}" stroke-width="0.3"/>`;
      const dimV = (x, y0, y1, label, anchor, tx) => {
        let o = `<path d="M${num(x)} ${num(-y0)}V${num(-y1)}" stroke="${ink}" stroke-width="0.22"/>` + tick(x, -y0) + tick(x, -y1);
        o += `<text x="${num(tx)}" y="${num(-(y0 + y1) / 2 + 1.1)}" font-size="${fs}" text-anchor="${anchor}" fill="${ink}">${esc(label)}</text>`;
        return o;
      };
      const ext = (x0, y, x1) => `<path d="M${num(x0)} ${num(-y)}H${num(x1)}" stroke="${ink}" stroke-width="0.15" stroke-dasharray="0.8 0.6" opacity="0.6"/>`;
      let o = `<g font-family="${FONT}" opacity="0.85">`;
      o += ext(-6, st.frontHeight, 0.5) + dimV(-4, 0, st.frontHeight, num(st.frontHeight), "end", -5.6);
      o += ext(Dp - 0.5, st.backHeight, Dp + 6) + dimV(Dp + 4, 0, st.backHeight, num(st.backHeight), "start", Dp + 5.6);
      o += ext(Dp - 0.5, st.maxHeight, Dp + 14) + dimV(Dp + 12.5, 0, st.maxHeight, num(st.maxHeight), "start", Dp + 14);
      o += ext(-14, st.frontKeyTop, 0.5) + dimV(-12, 0, st.frontKeyTop, num(st.frontKeyTop), "end", -13.4);
      const yb = 6.5;
      o += `<path d="M0 ${num(yb)}H${num(Dp)}M0 1.2V${num(yb + 1.5)}M${num(Dp)} 1.2V${num(yb + 1.5)}" stroke="${ink}" stroke-width="0.22"/>` + tick(0, yb) + tick(Dp, yb);
      o += `<text x="${num(Dp / 2)}" y="${num(yb - 1)}" font-size="${fs}" text-anchor="middle" fill="${ink}">${num(st.depth)} mm deep · ${num(s.tilt)}° tilt</text>`;
      o += `<text x="${num(-mL + 1)}" y="${num(yb + 4.2)}" font-size="2.4" fill="${ink}" opacity="0.7">heights in mm: case front / front caps · case back / overall</text>`;
      o += `</g>`;
      out.push(o);
    }

    const top = st.maxHeight + (opts.dims ? 7 : 5);
    const bottom = opts.dims ? 12 : 5;
    const vb = [-mL, -top, Dp + mL + mR, top + bottom];
    const label = esc(opts.label || `${L.name} side view, front on the left: ${valueName("plate", s.plate)} plate, ${s.glowPlace === "none" ? "no glow" : valueName("glowPlace", s.glowPlace) + " glow"}, ${s.capProfile} caps, ${num(s.tilt)}° tilt, ${num(st.frontHeight)} mm front to ${num(st.backHeight)} mm back`);
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb.map(num).join(" ")}" role="img" aria-label="${label}"><title>${label}</title><defs>${defs.join("")}</defs>${out.join("")}</svg>`;
  };

  FB.renderExploded = function (spec, opts) {
    opts = opts || {};
    PREC = 10;
    try { return exploded(spec, opts); } finally { PREC = 100; }
  };
  function exploded(spec, opts) {
    const p = String(opts.idPrefix || "exp");
    const g = geom(spec), s = g.s, c = colors(s), d = g.d, L = g.L, b = g.b;
    const K = 0.866, S = 0.36, RX = Math.SQRT2 * K, RY = Math.SQRT2 * S, P = d.pitch;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    const pr = (x, y, z) => {
      const X = (x - y) * K, Y = (x + y) * S - z;
      if (X < minX) minX = X; if (X > maxX) maxX = X; if (Y < minY) minY = Y; if (Y > maxY) maxY = Y;
      return [X, Y];
    };
    const defs = [], out = [];
    let gid = 0;
    const darkShell = (rgb(c.sh.base).reduce((a, v) => a + v, 0) / 3) < 110;
    const op = c.sh.opacity == null ? 1 : c.sh.opacity;

    function rr(x, y, w, h, r, n) {
      r = clamp(r, 0, Math.min(w, h) / 2); n = n || 5;
      const pts = [], cs = [[x + w - r, y + r, -90], [x + w - r, y + h - r, 0], [x + r, y + h - r, 90], [x + r, y + r, 180]];
      cs.forEach(([cx, cy, a0]) => {
        if (r < 0.05) { pts.push([cx + Math.sign(Math.cos((a0 + 45) * Math.PI / 180)) * r, cy + Math.sign(Math.sin((a0 + 45) * Math.PI / 180)) * r]); return; }
        for (let i = 0; i <= n; i++) { const a = (a0 + 90 * i / n) * Math.PI / 180; pts.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); }
      });
      return pts;
    }
    const proj = (pts, z) => pts.map(q => pr(q[0], q[1], z));
    const poly = pts => pts.map(pt).join(" ");
    const pathOf = pts => "M" + pts.map(pt).join("L") + "Z";
    function hull(pts) {
      const a = pts.slice().sort((u, v) => u[0] - v[0] || u[1] - v[1]);
      const cross = (o, u, v) => (u[0] - o[0]) * (v[1] - o[1]) - (u[1] - o[1]) * (v[0] - o[0]);
      const lo = [], up = [];
      for (const q of a) { while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], q) <= 0) lo.pop(); lo.push(q); }
      for (let i = a.length - 1; i >= 0; i--) { const q = a[i]; while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], q) <= 0) up.pop(); up.push(q); }
      return lo.slice(0, -1).concat(up.slice(0, -1));
    }
    // extruded convex outline: side silhouette (front/right faces split by gradient), then top face
    function prism(outline, z0, z1, top, front, right, attrs) {
      const B = proj(outline, z0), T = proj(outline, z1);
      const H = hull(B.concat(T));
      let xmin = Infinity, xmax = -Infinity, xc = 0, best = -Infinity;
      outline.forEach((q, i) => { const X = B[i][0]; if (X < xmin) xmin = X; if (X > xmax) xmax = X; if (q[0] + q[1] > best) { best = q[0] + q[1]; xc = X; } });
      const id = `${p}-g${gid++}`, f = xmax > xmin ? clamp((xc - xmin) / (xmax - xmin), 0, 1) : 0.5;
      defs.push(`<linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${num(xmin)}" y1="0" x2="${num(xmax)}" y2="0"><stop offset="0" stop-color="${front}"/><stop offset="${num(f)}" stop-color="${front}"/><stop offset="${num(f)}" stop-color="${right}"/><stop offset="1" stop-color="${right}"/></linearGradient>`);
      const a = attrs || "";
      return { side: `<path d="${pathOf(H)}" fill="url(#${id})" ${a}/>`, top: `<path d="${pathOf(T)}" fill="${top}" ${a}/>`, T, B, H };
    }
    const box = (x, y, w, h, z0, z1, top, front, right, attrs) => frustum(x + w / 2, y + h / 2, w / 2, w / 2, z0, z1, top, front, right, attrs, h / 2, h / 2);
    function cyl(cx, cy, r, z0, z1, side, topc, attrs) {
      const rx = RX * r, ry = RY * r, B = pr(cx, cy, z0), T = pr(cx, cy, z1);
      pr(cx + r, cy - r, z1); pr(cx - r, cy + r, z0); pr(cx + r, cy + r, z0); pr(cx - r, cy - r, z1);
      const a = attrs || "";
      return `<path d="M${num(B[0] - rx)} ${num(B[1])}A${num(rx)} ${num(ry)} 0 0 0 ${num(B[0] + rx)} ${num(B[1])}L${num(T[0] + rx)} ${num(T[1])}L${num(T[0] - rx)} ${num(T[1])}Z" fill="${side}" ${a}/>` +
        `<ellipse cx="${num(T[0])}" cy="${num(T[1])}" rx="${num(rx)}" ry="${num(ry)}" fill="${topc}" ${a}/>`;
    }
    const flat = (pts, z, fill, attrs) => `<polygon points="${poly(proj(pts, z))}" fill="${fill}" ${attrs || ""}/>`;
    const quad = (x, y, w, h) => [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
    const ell = (cx, cy, r, z, fill, attrs) => { const C = pr(cx, cy, z); return `<ellipse cx="${num(C[0])}" cy="${num(C[1])}" rx="${num(RX * r)}" ry="${num(RY * r)}" fill="${fill}" ${attrs || ""}/>`; };
    const shade = (col, k) => (k >= 0 ? mix(col, c.white, k) : mix(col, c.ink, -k));

    const ox = -b - d.sideWallExtra, oy = -b, ow = L.W + 2 * (b + d.sideWallExtra), oh = L.H + 2 * b, R = g.rr;
    const outer = rr(ox, oy, ow, oh, R, 6);
    const inner = rr(ox + g.wall, oy + g.wall, ow - 2 * g.wall, oh - 2 * g.wall, Math.max(R - g.wall, 1), 6);
    const bosses = [[ox + g.q, oy + g.q], [ox + ow - g.q, oy + g.q], [ox + ow - g.q, oy + oh - g.q], [ox + g.q, oy + oh - g.q]];
    const pcbR = [-2, -2, L.W + 4, L.H + 4];
    const xiao = g.xiao;
    const oledMod = L.oled ? [clamp(L.oled.x + L.oled.w / 2 - d.oledW / 2, -2, L.W + 2 - d.oledW), clamp(L.oled.y + L.oled.h / 2 - d.oledH / 2, -2, L.H + 2 - d.oledH), d.oledW, d.oledH] : null;

    // z layout of the exploded stack
    const G = 15;
    const layers = [];
    let z = 0;
    const glowLayer = s.glowPlace !== "none";
    if (s.glowPlace === "base") { layers.push({ id: "glow", z0: 0, z1: 2 }); z = 2 + G * 0.8; }
    const bot = { id: "bottom", z0: z, z1: z + g.rimZ }; layers.push(bot); z = bot.z1 + G;
    if (glowLayer && s.glowPlace !== "base") { const h = s.glowPlace === "gap" ? Math.max(g.gap, 2.4) : 2.4; layers.push({ id: "glow", z0: z, z1: z + h }); z += h + G; }
    const xl = { id: "xiao", z0: z, z1: z + 1 + Math.max(d.usbH, 2.4) }; layers.push(xl); z = xl.z1 + 24;
    const pcb = { id: "pcb", z0: z, z1: z + d.pcbT }; layers.push(pcb); z = pcb.z1 + d.ecBodyH + d.bushH + 4 + G * 0.6;
    const plH = 4 + g.rimH;
    const pl = { id: "plate", z0: z, z1: z + plH, face: z + 4 }; layers.push(pl); z = pl.z1 + G;
    if (s.screws !== "hidden" && s.screws !== "side") layers.push({ id: "screws", z0: z, z1: z + d.m3Len + d.m3HeadH });
    const sw = { id: "switches", z0: z, z1: z + d.below + d.above }; layers.push(sw); z = sw.z1 + d.stemAbove + G * 1.5;
    const kn = { id: "knob", z0: z, z1: z + (g.knob.vt - g.knob.vb) }; if (L.dials.length) layers.push(kn);
    const kc = { id: "caps", z0: z + 4, z1: z + 4 + g.cap.h }; layers.push(kc);
    if (s.screws === "hidden") layers.unshift({ id: "screws", z0: (layers[0].z0) - G - d.m3Len - d.m3HeadH, z1: layers[0].z0 - G, below: true });

    // dashed alignment axes, drawn in the gaps after each layer
    const nearKey = L.keys.slice().sort((a, b2) => (b2.x + b2.y) - (a.x + a.y))[0];
    const axes = bosses.map(q => ({ x: q[0], y: q[1] }));
    if (nearKey) axes.push({ x: nearKey.x + P / 2, y: nearKey.y + P / 2, key: true });
    const dash = (x, y, za, zb) => { if (zb - za < 0.5) return ""; const A = pr(x, y, za), B2 = pr(x, y, zb); return `<path d="M${pt(A)}L${pt(B2)}" stroke="currentColor" stroke-width="0.22" stroke-dasharray="1.2 1" opacity="0.45"/>`; };

    const labels = [];
    const anchorOf = (pts, z0) => { let best = null; pts.forEach(q => { const A = pr(q[0], q[1], z0); if (!best || A[0] > best[0]) best = A; }); return best; };
    const nAgent = L.keys.filter(k => k.role === "agent").length, nCmd = L.keys.length - nAgent;

    const shellTop = darkShell ? c.sh.top : shade(c.sh.top, 0.25), shellFront = c.sh.base, shellRight = mix(c.sh.base, c.sh.edge, 0.8);
    const shellAttr = `fill-opacity="${op}" stroke="${c.sh.edge}" stroke-width="0.25" stroke-linejoin="round"`;

    const draw = {
      glow(l) {
        const outerG = s.glowPlace === "base" ? rr(ox + 3, oy + 3, ow - 6, oh - 6, Math.max(R - 3, 1), 6) : rr(ox + 1, oy + 1, ow - 2, oh - 2, Math.max(R - 1, 1), 6);
        const innerG = s.glowPlace === "base" ? rr(ox + 6, oy + 6, ow - 12, oh - 12, Math.max(R - 6, 1), 6) : rr(ox + 4, oy + 4, ow - 8, oh - 8, Math.max(R - 4, 1), 6);
        const q = prism(outerG, l.z0, l.z1, c.glow, mix(c.glow, c.white, 0.25), mix(c.glow, c.ink, 0.1));
        const hole = proj(innerG, l.z0), topIn = proj(innerG, l.z1);
        let o = `<path d="${pathOf(q.H)} ${pathOf(hole)}" fill-rule="evenodd" fill="${c.glow}" opacity="0.6" filter="url(#${p}-bloom)"/>`;
        o += `<path d="${pathOf(q.H)} ${pathOf(hole)}" fill-rule="evenodd" fill="${mix(c.glow, c.white, 0.3)}"/>`;
        o += `<path d="${pathOf(q.T)} ${pathOf(topIn)}" fill-rule="evenodd" fill="${c.glow}" stroke="${mix(c.glow, c.ink, 0.15)}" stroke-width="0.2"/>`;
        labels.push({ a: anchorOf(outerG, l.z1), t: s.glowPlace === "gap" ? "Glow spacer" : s.glowPlace === "band" ? "Glow band" : "Light-guide foot",
          sub: `${valueName("glowColor", s.glowColor)} · ${s.glowPlace === "gap" ? "lit gap under the plate" : s.glowPlace === "band" ? "clear PETG mid-shell stripe" : "halo on the desk"}` });
        return o;
      },
      bottom(l) {
        const q = prism(outer, l.z0, l.z1, shellTop, shellFront, shellRight, shellAttr);
        let o = `<ellipse cx="${num(pr(ox + ow / 2, oy + oh / 2, l.z0)[0])}" cy="${num(pr(ox + ow / 2, oy + oh / 2, l.z0)[1] + 3)}" rx="${num((ow + oh) * 0.48)}" ry="${num((ow + oh) * 0.16)}" fill="${c.ink}" opacity="0.18" filter="url(#${p}-bloom)"/>`;
        o += q.side + q.top;
        const opening = proj(inner, l.z1);
        defs.push(`<clipPath id="${p}-cav"><path d="${pathOf(opening)}"/></clipPath>`);
        o += `<path d="${pathOf(opening)}" fill="${mix(c.sh.base, c.sh.edge, 0.7)}"/>`;
        o += `<g clip-path="url(#${p}-cav)">`;
        o += flat(inner, l.z0 + g.floor, mix(c.sh.base, c.sh.edge, 0.25));
        // XIAO pocket and USB-C notch at the back
        o += flat(quad(xiao[0] - 1, xiao[1] - 1, xiao[2] + 2, xiao[3] + 2), l.z0 + g.floor, mix(c.sh.base, c.sh.edge, 0.5));
        bosses.slice().sort((a, b2) => (a[0] + a[1]) - (b2[0] + b2[1])).forEach(([x, y]) => {
          o += cyl(x, y, g.bossR, l.z0 + g.floor, l.z1 - 0.4, mix(c.sh.base, c.sh.edge, 0.4), shellTop);
          o += ell(x, y, 1.7, l.z1 - 0.4, mix(c.sh.base, c.ink, 0.6));
        });
        o += `</g>`;
        if (s.screws === "side") {
          [bosses[1], bosses[2]].forEach(([x, y]) => {
            const zz = l.z0 + g.rimZ * 0.55;
            o += screwH(ox + ow + 4, y, zz);
          });
        }
        const sideTxt = s.screws === "side" ? "side-entry inserts" : "4 M3 screw holes";
        labels.push({ a: anchorOf(outer, l.z1), t: "Bottom shell", sub: `${valueName("shell", s.shell)} PETG · ${sideTxt}` });
        return o;
      },
      xiao(l) {
        const [x, y, w, h] = xiao, zb = l.z1 - 1, ztop = l.z1;
        let o = "";
        // components hang below the board (it is mounted face-down under the PCB)
        o += box(x + 4, y + 7, 7, 7, zb - 1, zb, mix(c.ink, c.white, 0.15), c.ink, c.ink);
        o += box(x + (w - d.usbW) / 2, y - d.usbOver, d.usbW, 7.3, zb - d.usbH, zb, c.metalLight, c.metal, mix(c.metal, c.ink, 0.3));
        o += box(x, y, w, h, zb, ztop, mix(c.ink, c.status.run, 0.25), c.ink, mix(c.ink, c.white, 0.08));
        for (let i = 0; i < 7; i++) {
          const yy = y + 2.5 + i * 2.54;
          o += ell(x + 0.9, yy, 0.6, ztop, c.pad) + ell(x + w - 0.9, yy, 0.6, ztop, c.pad);
        }
        labels.push({ a: anchorOf(quad(x, y, w, h), ztop), t: "XIAO RP2040", sub: "on the PCB underside, USB-C to the back" });
        return o;
      },
      pcb(l) {
        const pts = rr(pcbR[0], pcbR[1], pcbR[2], pcbR[3], 1.5, 3);
        const q = prism(pts, l.z0, l.z1, c.pcb, mix(c.pcb, c.ink, 0.25), mix(c.pcb, c.ink, 0.45));
        let o = q.side + q.top;
        const zt = l.z1;
        // x-ray outline of the XIAO underneath
        o += `<polygon points="${poly(proj(quad(xiao[0], xiao[1], xiao[2], xiao[3]), zt))}" fill="none" stroke="${c.pad}" stroke-width="0.25" stroke-dasharray="1 0.8" opacity="0.8"/>`;
        bosses.forEach(([x, y]) => { if (x > pcbR[0] + 2 && x < pcbR[0] + pcbR[2] - 2 && y > pcbR[1] + 2 && y < pcbR[1] + pcbR[3] - 2) o += ell(x, y, 1.9, zt, c.pad) + ell(x, y, 1.6, zt, c.ink); });
        L.keys.forEach(k => {
          const cx = k.x + P / 2, cy = k.y + P / 2;
          o += ell(cx, cy, 2, zt, mix(c.pcb, c.ink, 0.6));
          o += ell(cx - 3.81, cy - 2.54, 0.75, zt, c.pad) + ell(cx + 2.54, cy - 5.08, 0.75, zt, c.pad);
          o += flat(quad(cx - d.ledW / 2, cy + 5.08 - d.ledH / 2, d.ledW, d.ledH), zt, c.white);
          o += flat(quad(cx - 0.8, cy + 5.08 - 0.7, 1.6, 1.4), zt + 0.01, mix(c.white, c.status.done, 0.2));
          o += flat(quad(cx + 3.6, cy + 5.5, 3.6, 1.6), zt, c.ink) + flat(quad(cx + 3.9, cy + 5.5, 0.6, 1.6), zt, c.metalLight);
          o += flat(quad(cx + 2.7, cy + 5.6, 0.8, 1.4), zt, c.pad) + flat(quad(cx + 7.3, cy + 5.6, 0.8, 1.4), zt, c.pad);
        });
        L.dials.forEach(q2 => {
          const e = d.ecBody / 2, zb = zt + d.ecBodyH, zbu = zb + d.bushH;
          o += box(q2.x - e, q2.y - e, d.ecBody, d.ecBody, zt, zb, mix(c.metal, c.white, 0.2), c.metal, mix(c.metal, c.ink, 0.3));
          o += cyl(q2.x, q2.y, d.bushD / 2, zb, zbu, c.metal, c.metalLight);
          o += cyl(q2.x, q2.y, d.shaftD / 2, zbu, zbu + 4, mix(c.metal, c.ink, 0.1), c.metalLight);
        });
        if (oledMod) {
          const [x, y, w, h] = oledMod;
          const zg = zt + d.oledTopAbovePcb, zbd = zg - 1.45;
          o += box(x + 1, y + 1.5, 2.5, h - 3, zt, zbd - 1.2, c.ink, c.ink, c.ink);
          o += box(x, y, w, h, zbd - 1.2, zbd, mix(c.ink, c.status.run, 0.3), c.ink, c.ink);
          o += box(x + 4.5, y + 0.25, w - 8, h - 0.5, zbd, zg, c.ink, mix(c.ink, c.white, 0.1), c.ink);
          const ax = x + 4.5 + (w - 8 - d.oledAW) / 2, ay = y + (h - d.oledAH) / 2;
          o += flat(quad(ax, ay, d.oledAW, d.oledAH), zg, c.oled, 'opacity="0.9"');
        }
        const oledTxt = L.oled ? ' · 0.91" OLED' : "";
        const ledCount = L.keys.length + (s.glowPlace !== "none" ? 4 : 0);
        labels.push({ a: anchorOf(pts, zt), t: "PCB", sub: `2-layer · ${ledCount} SK6812 MINI-E · ${L.keys.length} 1N4148${oledTxt}` });
        return o;
      },
      plate(l) {
        const topC = darkShell ? c.sh.top : shade(c.sh.top, 0.35);
        const q = prism(outer, l.z0, l.z1, topC, shellFront, shellRight, shellAttr);
        let o = q.side + q.top;
        let faceZ = l.z1;
        if (g.rimH > 0) {
          const lipW = s.plate === "tray" ? 2.2 : 3.2;
          const pk = rr(ox + lipW, oy + lipW, ow - 2 * lipW, oh - 2 * lipW, Math.max(R - lipW, 1), 6);
          const open = proj(pk, l.z1);
          defs.push(`<clipPath id="${p}-dish"><path d="${pathOf(open)}"/></clipPath>`);
          o += `<path d="${pathOf(open)}" fill="${mix(c.sh.base, c.sh.edge, 0.55)}" fill-opacity="${op}"/>`;
          o += `<g clip-path="url(#${p}-dish)">` + flat(pk, l.face, mix(c.sh.top, c.sh.base, 0.4), `fill-opacity="${op}"`);
          faceZ = l.face;
        }
        let holes = "";
        L.keys.forEach(k => { const cx = k.x + P / 2, cy = k.y + P / 2, h2 = d.cut / 2; holes += flat(quad(cx - h2, cy - h2, d.cut, d.cut), faceZ, c.ink, 'opacity="0.55"'); });
        L.dials.forEach(q2 => { holes += ell(q2.x, q2.y, 4, faceZ, c.ink, 'opacity="0.55"'); });
        if (L.oled) holes += flat(quad(L.oled.x, L.oled.y, L.oled.w, L.oled.h), faceZ, c.ink, 'opacity="0.6"');
        if (s.screws === "top") bosses.forEach(([x, y]) => { holes += ell(x, y, 1.7, l.z1, c.ink, 'opacity="0.5"'); });
        o += holes + (g.rimH > 0 ? `</g>` : "");
        const nm = { floating: "floating plate on the light gap", flush: "flush with the shell rim", "deep-dish": "keys sunk 8 mm below the rim", tray: "3 mm raised lip" }[s.plate];
        labels.push({ a: anchorOf(outer, l.z1), t: s.plate === "floating" ? "Plate" : "Top shell", sub: `${nm} · 1.5 mm at cutouts · 4 heat-set inserts` });
        return o;
      },
      screws(l) {
        let o = "";
        bosses.slice().sort((a, b2) => (a[0] + a[1]) - (b2[0] + b2[1])).forEach(([x, y]) => {
          if (l.below) {
            o += cyl(x, y, 1.5, l.z0 + d.m3HeadH, l.z1, mix(c.metal, c.ink, 0.2), c.metalLight);
            o += cyl(x, y, d.m3Head / 2, l.z0, l.z0 + d.m3HeadH, c.metal, mix(c.metal, c.ink, 0.25));
          } else {
            o += cyl(x, y, 1.5, l.z0, l.z1 - d.m3HeadH, mix(c.metal, c.ink, 0.2), c.metalLight);
            o += cyl(x, y, d.m3Head / 2, l.z1 - d.m3HeadH, l.z1, c.metal, c.metalLight);
            o += ell(x, y, 1.3, l.z1, c.ink, 'opacity="0.6"');
          }
        });
        labels.push({ a: anchorOf([bosses[1]], l.below ? l.z0 : l.z1), t: "M3 screws", sub: l.below ? "4 × M3×16 from underneath" : "4 × M3×16, heads on the bezel" });
        return o;
      },
      switches(l) {
        let o = "";
        const ks = L.keys.slice().sort((a, b2) => (a.x + a.y) - (b2.x + b2.y));
        const hb = mix(c.housing, c.ink, 0.15);
        ks.forEach(k => {
          const cx = k.x + P / 2, cy = k.y + P / 2, zf = l.z0 + d.below;
          o += box(cx - 7, cy - 7, 14, 14, l.z0, zf, hb, mix(hb, c.ink, 0.1), mix(hb, c.ink, 0.25));
          const fl = prism(quad(cx - 7.8, cy - 7.8, 15.6, 15.6), zf, zf + 1, c.housing, mix(c.housing, c.ink, 0.1), mix(c.housing, c.ink, 0.22));
          o += fl.side + fl.top;
          o += frustum(cx, cy, 7.3, 5.6, zf + 1, zf + d.above, shade(c.housing, 0.3), mix(c.housing, c.ink, 0.06), mix(c.housing, c.ink, 0.2));
          o += box(cx - 2, cy - 0.6, 4, 1.2, zf + d.above, zf + d.above + 3.6, c.stem, mix(c.stem, c.ink, 0.15), mix(c.stem, c.ink, 0.3));
          o += box(cx - 0.6, cy - 2, 1.2, 4, zf + d.above, zf + d.above + 3.6, c.stem, mix(c.stem, c.ink, 0.15), mix(c.stem, c.ink, 0.3));
        });
        labels.push({ a: anchorOf(L.keys.map(k => [k.x + P / 2 + 7.8, k.y + P / 2 - 7.8]), l.z0 + d.below + 1), t: "Switches", sub: `${L.keys.length} × Gateron Yellow KS-3 (MX, linear)` });
        return o;
      },
      knob(l) {
        let o = "";
        const kc2 = c.knob, Rk = g.knob.r;
        const ring = c.status[busiest(s, opts.t)] || c.glow;
        L.dials.slice().sort((a, b2) => (a.x + a.y) - (b2.x + b2.y)).forEach(q2 => {
          if (s.knob === "ringlit") o += cyl(q2.x, q2.y, Rk + 1.2, l.z0 - 2, l.z0 - 0.6, ring, mix(ring, c.white, 0.4));
          const metal = s.knob === "knurled-alu" || s.knob === "ringlit";
          o += cyl(q2.x, q2.y, Rk, l.z0, l.z1, metal ? `url(#${p}-kmetal)` : mix(kc2.ring, kc2.face, 0.4), shade(kc2.face, 0.3), s.knob === "frosted" ? 'fill-opacity="0.92"' : "");
          o += ell(q2.x, q2.y, Rk * 0.72, l.z1, shade(kc2.face, metal ? -0.08 : 0.45));
          if (metal) {
            const T = pr(q2.x, q2.y, l.z1), B2 = pr(q2.x, q2.y, l.z0 + 1.5);
            let kl = "";
            for (let a = -80; a <= 80; a += 10) { const dx = Math.sin(a * Math.PI / 180) * RX * Rk, dy = Math.cos(a * Math.PI / 180) * RY * Rk; kl += `M${num(T[0] + dx)} ${num(T[1] + dy + 2.5)}L${num(B2[0] + dx)} ${num(B2[1] + dy)}`; }
            o += `<path d="${kl}" stroke="${mix(c.metal, c.ink, 0.4)}" stroke-width="0.25" opacity="0.5"/>`;
          }
          if (metal && !defs.some(x2 => x2.indexOf(`${p}-kmetal"`) >= 0)) {
            defs.push(`<linearGradient id="${p}-kmetal" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="${mix(c.metal, c.ink, 0.3)}"/><stop offset="0.4" stop-color="${c.metalLight}"/><stop offset="0.6" stop-color="${shade(c.metalLight, 0.5)}"/><stop offset="1" stop-color="${mix(c.metal, c.ink, 0.4)}"/></linearGradient>`);
          }
        });
        const kname = valueName("knob", s.knob);
        labels.push({ a: anchorOf([[L.dials[0].x + Rk, L.dials[0].y - Rk]], l.z1), t: L.dials.length > 1 ? "Knobs" : "Knob", sub: `${kname} · EC11${L.dials.length > 1 ? " × " + L.dials.length : ""}` });
        return o;
      },
      caps(l) {
        let o = "";
        const tw2 = g.cap.top / 2, bw2 = g.cap.bottom / 2;
        const ks = L.keys.map((k, i) => ({ k, i })).sort((a, b2) => (a.k.x + a.k.y) - (b2.k.x + b2.k.y));
        let ai = 0; const aidx = L.keys.map(k => (k.role === "agent" ? ai++ : -1));
        ks.forEach(({ k, i }) => {
          const cx = k.x + P / 2, cy = k.y + P / 2, agent = k.role === "agent";
          const base = agent ? mix(c.agentBase, c.status[statusOf(s, aidx[i], opts.t)] || c.agentBase, s.agentCap === "milky" ? 0.5 : s.agentCap === "clear" ? 0.78 : 0.64) : c.cmd;
          if (agent) o += ell(cx, cy, 10, l.z0, base, `opacity="0.5" filter="url(#${p}-bloom)"`);
          o += frustum(cx, cy, bw2, tw2, l.z0, l.z1, shade(base, 0.3), shade(base, agent ? 0.08 : -0.06), shade(base, agent ? -0.14 : -0.18), agent && s.agentCap === "clear" ? 'fill-opacity="0.9"' : "");
          const dish = rr(cx - tw2 + 1.6, cy - tw2 + 1.6, 2 * tw2 - 3.2, 2 * tw2 - 3.2, g.cap.r, 3);
          o += flat(dish, l.z1, shade(base, s.capProfile === "DSA" ? -0.05 : 0.1), 'opacity="0.8"');
        });
        const names = `${nAgent} agent (${valueName("agentCap", s.agentCap).toLowerCase()})${nCmd ? ` · ${nCmd} command (${valueName("commandCap", s.commandCap).toLowerCase()})` : ""}`;
        labels.push({ a: anchorOf(L.keys.map(k => [k.x + P / 2 + bw2, k.y + P / 2 - bw2]), l.z0 + 1), t: `Keycaps · ${s.capProfile}`, sub: names });
        return o;
      }
    };
    function frustum(cx, cy, hb, ht, z0, z1, top, front, right, attrs, hby, hty) {
      const a = attrs || "", by = hby == null ? hb : hby, ty = hty == null ? ht : hty;
      const B = [[cx - hb, cy - by], [cx + hb, cy - by], [cx + hb, cy + by], [cx - hb, cy + by]].map(q => pr(q[0], q[1], z0));
      const T = [[cx - ht, cy - ty], [cx + ht, cy - ty], [cx + ht, cy + ty], [cx - ht, cy + ty]].map(q => pr(q[0], q[1], z1));
      return `<path d="M${pt(B[1])}L${pt(B[2])}L${pt(T[2])}L${pt(T[1])}Z" fill="${right}" ${a}/>` +
        `<path d="M${pt(B[2])}L${pt(B[3])}L${pt(T[3])}L${pt(T[2])}Z" fill="${front}" ${a}/>` +
        `<path d="M${pt(T[0])}L${pt(T[1])}L${pt(T[2])}L${pt(T[3])}Z" fill="${top}" ${a}/>`;
    }
    function screwH(x, y, zz) {
      // horizontal M3 pointing at the right-hand wall (-x)
      const A = pr(x, y, zz), B2 = pr(x + 16, y, zz), r = 1.5, hr = d.m3Head / 2;
      let o = `<path d="M${num(A[0])} ${num(A[1] - r)}L${num(B2[0])} ${num(B2[1] - r)}L${num(B2[0])} ${num(B2[1] + r)}L${num(A[0])} ${num(A[1] + r)}Z" fill="${c.metal}"/>`;
      const H2 = pr(x + 19, y, zz);
      o += `<path d="M${num(B2[0])} ${num(B2[1] - hr)}L${num(H2[0])} ${num(H2[1] - hr)}L${num(H2[0])} ${num(H2[1] + hr)}L${num(B2[0])} ${num(B2[1] + hr)}Z" fill="${mix(c.metal, c.ink, 0.2)}"/>`;
      o += `<ellipse cx="${num(H2[0])}" cy="${num(H2[1])}" rx="${num(hr * 0.7)}" ry="${num(hr)}" fill="${c.metalLight}"/>`;
      labelsSide.push(pr(x + 19, y, zz));
      return o;
    }
    const labelsSide = [];

    defs.push(`<filter id="${p}-bloom" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="2.2"/></filter>`);

    // draw bottom -> top, with dashed alignment segments in the gap above each layer
    const order = layers.slice().sort((a, b2) => a.z0 - b2.z0);
    const after = {};
    const chain = (ids, list) => {
      const ch = order.filter(l => ids.includes(l.id));
      for (let i = 0; i + 1 < ch.length; i++) {
        const A = ch[i], B2 = ch[i + 1];
        (after[A.id] = after[A.id] || []).push(...list.map(ax => dash(ax.x, ax.y, A.z1, B2.z0)));
      }
    };
    chain(["glow", "bottom", "pcb", "plate", "screws"], axes.filter(a => !a.key));
    chain(["pcb", "plate", "switches", "caps"], axes.filter(a => a.key));
    order.forEach(l => {
      out.push(draw[l.id](l));
      if (after[l.id]) out.push(after[l.id].join(""));
    });
    if (s.screws === "side") labels.push({ a: labelsSide[0] || [maxX, 0], t: "M3 screws", sub: "4 × M3×16 through the side walls" });

    // labels on the right
    const fs = 4.2, fs2 = 3.1, lx = maxX + 12;
    labels.sort((a, b2) => a.a[1] - b2.a[1]);
    let last = -Infinity;
    labels.forEach(lb => { lb.y = Math.max(lb.a[1], last + 10); last = lb.y; });
    let lab = `<g font-family="${FONT}" fill="currentColor">`;
    let wmax = 0;
    labels.forEach(lb => {
      lab += `<path d="M${pt(lb.a)}L${num(lx - 6)} ${num(lb.y)}L${num(lx - 2)} ${num(lb.y)}" fill="none" stroke="currentColor" stroke-width="0.25" opacity="0.5"/>`;
      lab += `<circle cx="${num(lb.a[0])}" cy="${num(lb.a[1])}" r="0.7" opacity="0.7"/>`;
      lab += `<text x="${num(lx)}" y="${num(lb.y + 1.2)}" font-size="${fs}" font-weight="600">${esc(lb.t)}</text>`;
      lab += `<text x="${num(lx)}" y="${num(lb.y + 5.4)}" font-size="${fs2}" opacity="0.65">${esc(lb.sub)}</text>`;
      wmax = Math.max(wmax, lb.t.length * fs * 0.56, lb.sub.length * fs2 * 0.53);
      if (lb.y + 7 > maxY) maxY = lb.y + 7;
    });
    lab += `</g>`;
    out.push(lab);

    const pad = 6;
    const vb = [minX - pad, minY - pad, (lx + wmax + pad) - (minX - pad), (maxY + pad) - (minY - pad)];
    const label = esc(opts.label || `${L.name} exploded view: ${labels.map(l => l.t).join(", ")}`);
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb.map(num).join(" ")}" role="img" aria-label="${label}"><title>${label}</title><defs>${defs.join("")}</defs>${out.join("")}</svg>`;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { renderSide: FB.renderSide, renderExploded: FB.renderExploded };
})(typeof window !== "undefined" ? window : globalThis);
