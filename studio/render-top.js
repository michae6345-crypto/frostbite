(function (root) {
  const FB = root.FB = root.FB || {};
  // Bird's-eye renderer, to scale. Units are mm, with the origin at the top-left of the layout
  // content area (the bezel extends outside it). Light comes from the top-left.

  let counter = 0;
  const STATUS_TEXT = { idle: "IDLE", run: "RUNNING", done: "DONE", needs: "WAITING", error: "ERROR" };
  const MONO = "'JetBrains Mono','IBM Plex Mono','SF Mono',ui-monospace,Menlo,Consolas,'DejaVu Sans Mono',monospace";
  const SANS = "'Space Grotesk','Inter','Helvetica Neue',Helvetica,Arial,sans-serif";
  const NB = " "; // non-breaking space (keeps OLED columns aligned)

  const num = v => { v = +v; if (!isFinite(v)) v = 0; v = Math.round(v * 100) / 100; return v === 0 ? 0 : v; };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const esc = s => String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  function rgb(hex) {
    let h = String(hex || "#888888").replace("#", "");
    if (h.length === 3) h = h.split("").map(c => c + c).join("");
    const n = parseInt(h.slice(0, 6), 16);
    if (!isFinite(n)) return [136, 136, 136];
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function mix(a, b, t) {
    const A = rgb(a), B = rgb(b);
    return "#" + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, "0")).join("");
  }
  const lum = hex => { const c = rgb(hex); return (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]) / 255; };
  const BLACK = "#000000", WHITE = "#ffffff";

  function normalize(specIn) {
    const def = FB.catalog.defaultSpec, opt = FB.catalog.options;
    const s = Object.assign({}, def, specIn || {});
    for (const k of Object.keys(opt)) {
      const list = opt[k];
      if (!list.some(v => v === s[k] || (typeof v === "number" && +s[k] === v))) s[k] = def[k];
      if (typeof list[0] === "number") s[k] = +s[k];
    }
    const stat = FB.catalog.palette.status;
    const st = Array.isArray(s.statuses) ? s.statuses.filter(x => stat[x]) : [];
    s.statuses = st.length ? st : def.statuses.slice();
    s.wordmarkText = String(s.wordmarkText == null ? "frostbite" : s.wordmarkText).slice(0, 24);
    return s;
  }

  function wedge(cx, cy, r, a1, a2) {
    const p1 = [cx + r * Math.cos(a1), cy + r * Math.sin(a1)], p2 = [cx + r * Math.cos(a2), cy + r * Math.sin(a2)];
    return `M${num(cx)} ${num(cy)}L${num(p1[0])} ${num(p1[1])}A${num(r)} ${num(r)} 0 0 1 ${num(p2[0])} ${num(p2[1])}Z`;
  }

  FB.renderTop = function (specIn, opts) {
    opts = opts || {};
    const pal = FB.catalog.palette;
    const D = FB.dims;
    const s = normalize(specIn);
    const L = FB.layoutById(s.layout);
    const P = D.pitch;
    let p = String(opts.idPrefix || ("fbt" + (++counter)));
    if (!/^[A-Za-z_][\w-]*$/.test(p)) p = "fbt" + p.replace(/[^\w-]/g, "");
    const id = n => p + "-" + n;
    const url = n => `url(#${id(n)})`;
    const tick = Math.floor(+opts.t || 0);

    const sh = pal.shell[s.shell];
    const glow = pal.glow[s.glowColor];
    const darkShell = lum(sh.top) < 0.45;
    const opaqueDark = darkShell && sh.opacity >= 1; // no light passes through, so no glow on the surface
    const W = L.W, H = L.H, b = s.bezel;
    const x0 = -b, y0 = -b, SW = W + 2 * b, SH = H + 2 * b;
    const R = clamp(s.corner, 0.5, Math.min(SW, SH) / 2);
    const m = 9;
    const vb = [x0 - m, y0 - m, SW + 2 * m + (opts.dims ? 14 : 0), SH + 2 * m + (opts.dims ? 12 : 0)];
    const shadowCol = darkShell ? mix(sh.edge, BLACK, 0.7) : mix(sh.edge, BLACK, 0.55);

    const defs = [];
    const out = [];
    const filters = {};
    function blur(name, sd) {
      if (!filters[name]) {
        filters[name] = 1;
        defs.push(`<filter id="${id(name)}" filterUnits="userSpaceOnUse" x="${num(vb[0])}" y="${num(vb[1])}" width="${num(vb[2])}" height="${num(vb[3])}" color-interpolation-filters="sRGB"><feGaussianBlur stdDeviation="${sd}"/></filter>`);
      }
      return url(name);
    }
    const rr = (x, y, w, h, r, extra) => `<rect x="${num(x)}" y="${num(y)}" width="${num(Math.max(0, w))}" height="${num(Math.max(0, h))}" rx="${num(clamp(r, 0, Math.min(w, h) / 2))}"${extra ? " " + extra : ""}/>`;
    const shellRect = (inset, extra) => rr(x0 + inset, y0 + inset, SW - 2 * inset, SH - 2 * inset, R - inset, extra);
    const stops = arr => arr.map(([o, c, a]) => `<stop offset="${o}" stop-color="${c}"${a !== undefined && a !== 1 ? ` stop-opacity="${a}"` : ""}/>`).join("");
    const lin = (name, x1, y1, x2, y2, st, user) => defs.push(`<linearGradient id="${id(name)}" x1="${num(x1)}" y1="${num(y1)}" x2="${num(x2)}" y2="${num(y2)}"${user ? ' gradientUnits="userSpaceOnUse"' : ""}>${stops(st)}</linearGradient>`);
    const rad = (name, cx, cy, r, st, extra) => defs.push(`<radialGradient id="${id(name)}" cx="${cx}" cy="${cy}" r="${r}"${extra ? " " + extra : ""}>${stops(st)}</radialGradient>`);

    lin("shg", 0, 0, 0.35, 1, [[0, mix(sh.top, WHITE, darkShell ? 0.12 : 0.4)], [0.55, sh.top], [1, sh.base]]);
    lin("bsg", 0, 0, 0.35, 1, [[0, mix(sh.base, WHITE, darkShell ? 0.08 : 0.3)], [0.6, sh.base], [1, sh.edge]]);
    lin("rim", x0, y0, x0 + SW, y0 + SH, [[0, WHITE, darkShell ? 0.35 : 0.85], [0.42, WHITE, 0], [0.58, BLACK, 0], [1, BLACK, darkShell ? 0.45 : 0.2]], true);
    lin("rimin", x0, y0, x0 + SW, y0 + SH, [[0, BLACK, darkShell ? 0.5 : 0.28], [0.45, BLACK, 0], [0.55, WHITE, 0], [1, WHITE, darkShell ? 0.25 : 0.7]], true);
    lin("sheen", x0, y0, x0 + SW * 0.7, y0 + SH, [[0, WHITE, darkShell ? 0.1 : 0.32], [0.4, WHITE, 0.05], [0.7, WHITE, 0]], true);
    lin("wall", 0, 0, 1, 1, [[0, WHITE, 0.6], [0.42, WHITE, 0], [0.58, BLACK, 0], [1, BLACK, 0.24]]);
    lin("spec", 0, 0, 1, 1, [[0, WHITE, 0.9], [0.45, WHITE, 0]]);
    rad("dish", 0.62, 0.66, 0.78, [[0, WHITE, 0.55], [0.5, WHITE, 0.08], [0.85, BLACK, 0.05], [1, BLACK, 0.2]], 'fx="0.68" fy="0.72"');
    defs.push(`<clipPath id="${id("sc")}">${shellRect(0)}</clipPath>`);

    // drop shadow on the desk and base halo
    out.push(`<g opacity="0.3" fill="${shadowCol}" filter="${blur("fs", 2.2)}">${rr(x0 + 1, y0 + 2.2, SW - 0.6, SH - 0.4, R)}</g>`);
    out.push(`<g opacity="0.5" fill="${shadowCol}" filter="${blur("fc", 0.7)}">${rr(x0 + 0.4, y0 + 0.9, SW - 0.6, SH - 0.6, R)}</g>`);
    if (s.glowPlace === "base") {
      out.push(`<g opacity="0.85" fill="${glow}" filter="${blur("gB", 2.8)}">${shellRect(-1.6)}</g>`);
      out.push(`<g opacity="0.95" fill="${mix(glow, WHITE, 0.3)}" filter="${blur("gb", 1)}">${shellRect(-0.5)}</g>`);
    }
    if (s.glowPlace === "band") {
      out.push(`<g opacity="0.9" fill="none" stroke="${glow}" stroke-width="2.4" filter="${blur("gb", 1)}">${shellRect(-0.4)}</g>`);
    }

    const floating = s.plate === "floating";
    const g = clamp(b * 0.24, 1.4, 2.2); // floating-plate inset, the visible base ring
    out.push(`<g opacity="${sh.opacity}">`);
    out.push(shellRect(0, `fill="${floating ? url("bsg") : url("shg")}"`));
    if (floating) {
      // light (or shadow) leaking out of the gap under the plate
      if (s.glowPlace === "gap") {
        out.push(`<g fill="none" stroke="${glow}">${shellRect(g, `stroke-width="1.5" opacity="0.9" filter="${blur("gs", 0.6)}"`)}${shellRect(g - 0.1, `stroke-width="0.7" stroke="${mix(glow, WHITE, 0.55)}"`)}</g>`);
      } else {
        out.push(`<g fill="none" stroke="${mix(sh.base, BLACK, 0.45)}" stroke-width="1.1" opacity="0.6" filter="${blur("ib", 0.45)}">${shellRect(g)}</g>`);
      }
      out.push(shellRect(g, `fill="${url("shg")}"`));
    }
    out.push(`</g>`);

    // textures (clipped to the shell)
    const tex = [];
    if (s.texture === "satin") {
      defs.push(`<filter id="${id("nz")}" filterUnits="userSpaceOnUse" x="${num(x0)}" y="${num(y0)}" width="${num(SW)}" height="${num(SH)}"><feTurbulence type="fractalNoise" baseFrequency="1.7" numOctaves="2" seed="7"/><feColorMatrix values="0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0.9 0 0 0 -0.4"/></filter>`);
      tex.push(`<rect x="${num(x0)}" y="${num(y0)}" width="${num(SW)}" height="${num(SH)}" filter="${url("nz")}" opacity="${opaqueDark ? 0.1 : darkShell ? 0.35 : 0.8}"/>`);
    } else if (s.texture === "layer-lines") {
      defs.push(`<pattern id="${id("ll")}" patternUnits="userSpaceOnUse" width="8" height="0.42"><rect width="8" height="0.12" fill="${WHITE}" opacity="${darkShell ? 0.12 : 0.45}"/><rect y="0.21" width="8" height="0.09" fill="${BLACK}" opacity="${darkShell ? 0.25 : 0.07}"/></pattern>`);
      tex.push(`<rect x="${num(x0)}" y="${num(y0)}" width="${num(SW)}" height="${num(SH)}" fill="${url("ll")}"/>`);
    } else if (s.texture === "speckle") {
      let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
      const cols = [mix(sh.edge, BLACK, 0.5), mix(sh.edge, BLACK, 0.25), WHITE, mix(sh.edge, "#4a6a88", 0.5)];
      let dots = "";
      for (let i = 0; i < 16; i++) dots += `<circle cx="${num(rnd() * 7)}" cy="${num(rnd() * 7)}" r="${num(0.07 + rnd() * 0.13)}" fill="${cols[i % 4]}" opacity="${num(0.35 + rnd() * 0.4)}"/>`;
      defs.push(`<pattern id="${id("sp")}" patternUnits="userSpaceOnUse" width="7" height="7">${dots}</pattern>`);
      tex.push(`<rect x="${num(x0)}" y="${num(y0)}" width="${num(SW)}" height="${num(SH)}" fill="${url("sp")}"/>`);
    }
    tex.push(`<rect x="${num(x0)}" y="${num(y0)}" width="${num(SW)}" height="${num(SH)}" fill="${url("sheen")}"/>`);
    // light diffusing inside the translucent shell
    if ((s.glowPlace === "gap" || s.glowPlace === "band") && sh.opacity < 1) tex.push(`<g fill="none" stroke="${glow}" stroke-width="4" opacity="${darkShell ? 0.3 : 0.15}" filter="${blur("gB", 2.8)}">${shellRect(1.5)}</g>`);
    out.push(`<g clip-path="${url("sc")}">${tex.join("")}</g>`);

    // soft rounded edges
    const rimW = clamp(b * 0.28, 1.4, 2.6);
    out.push(`<g fill="none">${shellRect(rimW / 2, `stroke="${url("rim")}" stroke-width="${num(rimW)}"`)}${shellRect(0.12, `stroke="${sh.edge}" stroke-width="0.25" opacity="0.9"`)}</g>`);
    if (floating) {
      out.push(`<g fill="none">${shellRect(g + 0.55, `stroke="${url("rim")}" stroke-width="1.1"`)}${shellRect(g, `stroke="${mix(sh.edge, BLACK, 0.15)}" stroke-width="0.2" opacity="0.8"`)}</g>`);
      if (s.glowPlace === "gap" && !opaqueDark) out.push(`<g fill="none" stroke="${glow}" opacity="0.45">${shellRect(g + 0.35, `stroke-width="0.5"`)}</g>`);
    } else {
      const seam = clamp(b * 0.13, 0.8, 1.4);
      if (s.glowPlace === "gap") {
        out.push(`<g fill="none" stroke="${glow}">${shellRect(seam, `stroke-width="1.6" opacity="0.9" filter="${blur("gb", 1)}"`)}${shellRect(seam, `stroke-width="0.4" stroke="${mix(glow, WHITE, 0.5)}"`)}</g>`);
      } else {
        out.push(`<g fill="none">${shellRect(seam, `stroke="${mix(sh.edge, BLACK, 0.3)}" stroke-width="0.22" opacity="0.6"`)}${shellRect(seam + 0.22, `stroke="${WHITE}" stroke-width="0.2" opacity="${darkShell ? 0.15 : 0.6}"`)}</g>`);
      }
    }
    if (s.glowPlace === "band") {
      out.push(`<g fill="none">${shellRect(0.3, `stroke="${mix(glow, WHITE, 0.35)}" stroke-width="0.6"`)}${shellRect(0.9, `stroke="${glow}" stroke-width="0.8" opacity="0.35"`)}</g>`);
    }

    // key well (deep-dish) or tray
    const keys = L.keys;
    let kx1 = Infinity, ky1 = Infinity, kx2 = -Infinity, ky2 = -Infinity;
    keys.forEach(k => { kx1 = Math.min(kx1, k.x); ky1 = Math.min(ky1, k.y); kx2 = Math.max(kx2, k.x + P); ky2 = Math.max(ky2, k.y + P); });
    if (!keys.length) { kx1 = ky1 = kx2 = ky2 = 0; }
    if (keys.length && s.plate === "deep-dish") {
      const pd = 1.2, wx = kx1 - pd, wy = ky1 - pd, ww = kx2 - kx1 + 2 * pd, wh = ky2 - ky1 + 2 * pd, wr = 3;
      defs.push(`<clipPath id="${id("wc")}">${rr(wx, wy, ww, wh, wr)}</clipPath>`);
      out.push(rr(wx, wy, ww, wh, wr, `fill="${mix(sh.base, sh.top, 0.35)}" opacity="${sh.opacity}"`));
      out.push(`<g clip-path="${url("wc")}" fill="none"><g filter="${blur("ib2", 1.1)}" stroke="${mix(sh.edge, BLACK, darkShell ? 0.6 : 0.5)}" opacity="0.85">${rr(wx - 0.4, wy - 0.6, ww + 0.4, wh + 0.6, wr, 'stroke-width="4.4"')}</g>${rr(wx + 0.5, wy + 0.5, ww - 1, wh - 1, wr - 0.5, `stroke="${url("rimin")}" stroke-width="1"`)}</g>`);
      out.push(rr(wx, wy, ww, wh, wr, `fill="none" stroke="${WHITE}" stroke-width="0.25" opacity="${darkShell ? 0.2 : 0.55}"`));
    } else if (keys.length && s.plate === "tray") {
      const po = 2.0, pi = 0.45, ox = kx1 - po, oy = ky1 - po, ow = kx2 - kx1 + 2 * po, oh = ky2 - ky1 + 2 * po;
      out.push(`<g opacity="0.35" fill="${shadowCol}" filter="${blur("ib", 0.45)}">${rr(ox + 0.4, oy + 0.8, ow, oh, 3.4)}</g>`);
      out.push(rr(ox, oy, ow, oh, 3.4, `fill="${url("shg")}" opacity="${sh.opacity}"`));
      out.push(rr(ox + po - pi, oy + po - pi, ow - 2 * (po - pi), oh - 2 * (po - pi), 2, `fill="${mix(sh.base, sh.top, 0.5)}"`));
      out.push(`<g fill="none">${rr(ox + 0.4, oy + 0.4, ow - 0.8, oh - 0.8, 3, `stroke="${url("rim")}" stroke-width="0.8"`)}${rr(ox + po - pi + 0.3, oy + po - pi + 0.3, ow - 2 * (po - pi) - 0.6, oh - 2 * (po - pi) - 0.6, 1.8, `stroke="${url("rimin")}" stroke-width="0.6"`)}${rr(ox, oy, ow, oh, 3.4, `stroke="${sh.edge}" stroke-width="0.2"`)}</g>`);
    }

    if (s.screws === "top") {
      const hr = D.m3Head / 2;
      const k = hr + 1.6;
      let d = Math.max(b / 2, R - (R - k) / Math.SQRT2);
      d = Math.min(d, b - 0.4);
      lin("scr", 0, 0, 1, 1, [[0, mix(pal.knob["knurled-alu"].face, WHITE, 0.6)], [0.5, pal.knob["knurled-alu"].face], [1, mix(pal.knob["knurled-alu"].ring, BLACK, 0.2)]]);
      const hexCol = mix(pal.knob["knurled-alu"].ring, BLACK, 0.7);
      [[x0 + d, y0 + d], [x0 + SW - d, y0 + d], [x0 + d, y0 + SH - d], [x0 + SW - d, y0 + SH - d]].forEach(([cx, cy]) => {
        let hex = "";
        for (let i = 0; i < 6; i++) { const a = Math.PI / 6 + i * Math.PI / 3; hex += (i ? "L" : "M") + num(cx + 1.25 * Math.cos(a)) + " " + num(cy + 1.25 * Math.sin(a)); }
        out.push(`<circle cx="${num(cx + 0.2)}" cy="${num(cy + 0.4)}" r="${num(hr)}" fill="${shadowCol}" opacity="0.35"/><circle cx="${num(cx)}" cy="${num(cy)}" r="${num(hr)}" fill="${url("scr")}" stroke="${mix(pal.knob["knurled-alu"].ring, BLACK, 0.3)}" stroke-width="0.2"/><path d="${hex}Z" fill="${hexCol}"/><path d="${hex}Z" fill="none" stroke="${WHITE}" stroke-width="0.15" opacity="0.35" transform="translate(0.15 0.15)"/>`);
      });
    }

    const wm = s.wordmarkText.trim();
    if (wm && s.wordmark !== "none") {
      const engraveCol = darkShell ? mix(sh.top, WHITE, 0.55) : mix(sh.edge, BLACK, 0.45);
      const hiCol = darkShell ? BLACK : WHITE;
      const textW = (fs, n) => n * (fs * 0.56 + fs * 0.12);
      let place = null;
      if (s.wordmark === "plate") {
        const obst = [];
        keys.forEach(k => obst.push([k.x, k.y, k.x + P, k.y + P]));
        if (L.oled) obst.push([L.oled.x, L.oled.y, L.oled.x + L.oled.w, L.oled.y + L.oled.h]);
        const kr = D.ec11.knobDiameter / 2 + 0.6;
        L.dials.forEach(dl => obst.push([dl.x - kr, dl.y - kr, dl.x + kr, dl.y + kr]));
        const pref = L.oled ? [L.oled.x + L.oled.w / 2, L.oled.y + L.oled.h + 2.5] : [W / 2, 11];
        for (const fs of [2.6, 2.1, 1.7]) {
          const tw = textW(fs, wm.length), th = fs * 1.15;
          let best = null;
          for (let cx = x0 + 2.5 + tw / 2; cx <= x0 + SW - 2.5 - tw / 2; cx += 0.5) {
            for (let cy = y0 + 2.5 + th / 2; cy <= y0 + SH - 2.5 - th / 2; cy += 0.5) {
              const r1 = [cx - tw / 2 - 0.5, cy - th / 2 - 0.5, cx + tw / 2 + 0.5, cy + th / 2 + 0.5];
              if (obst.some(o => r1[0] < o[2] && r1[2] > o[0] && r1[1] < o[3] && r1[3] > o[1])) continue;
              const inside = cx - tw / 2 >= -0.5 && cx + tw / 2 <= W + 0.5 && cy - th / 2 >= -0.5 && cy + th / 2 <= H + 0.5;
              const sc = Math.hypot(cx - pref[0], cy - pref[1]) + (inside ? 0 : 25);
              if (!best || sc < best.sc) best = { sc, cx, cy, fs };
            }
          }
          if (best) { place = best; break; }
        }
      }
      if (!place) {
        let fs = Math.min(2.8, b * 0.36);
        const maxW = SW - 2 * (s.screws === "top" ? b + 3 : R * 0.6 + 2);
        while (fs > 1.2 && textW(fs, wm.length) > maxW) fs -= 0.1;
        place = { cx: W / 2, cy: H + b / 2, fs };
      }
      const yb = place.cy + place.fs * 0.36;
      const attrs = `x="${num(place.cx)}" text-anchor="middle" font-family="${SANS}" font-size="${num(place.fs)}" font-weight="600" letter-spacing="${num(place.fs * 0.12)}"`;
      out.push(`<text ${attrs} y="${num(yb + 0.14)}" fill="${hiCol}" opacity="${darkShell ? 0.5 : 0.75}">${esc(wm)}</text><text ${attrs} y="${num(yb)}" fill="${engraveCol}" opacity="0.85">${esc(wm)}</text>`);
    }

    const agents = keys.filter(k => k.role === "agent");
    const nSt = s.statuses.length;
    const statusOf = i => s.statuses[(((i + tick) % nSt) + nSt) % nSt];

    if (L.oled) {
      const o = L.oled, oc = pal.oled[s.oledColor] || pal.oled.white;
      const glass = mix(pal.shell.smoke.edge, BLACK, 0.82);
      out.push(rr(o.x - 0.5, o.y - 0.5, o.w + 1, o.h + 1, 1.3, `fill="${mix(sh.edge, BLACK, darkShell ? 0.5 : 0.25)}" opacity="0.55"`));
      out.push(rr(o.x, o.y, o.w, o.h, 0.9, `fill="${glass}"`));
      const aw = Math.min(D.oledActive.w, o.w - 2), ah = Math.min(D.oledActive.h, o.h - 1.6);
      const ax = o.x + (o.w - aw) / 2, ay = o.y + (o.h - ah) / 2;
      const nA = Math.max(1, agents.length);
      const slot = (((tick % nA) + nA) % nA);
      const st = agents.length ? statusOf(slot) : "idle";
      const l1 = ("claude#" + (slot + 1)).padEnd(10, NB) + (STATUS_TEXT[st] || "IDLE");
      const l2 = st === "error" ? `loss${NB}inf${NB}▸${NB}ep${12 + Math.abs(tick)}` : `loss${NB}${(0.418 * Math.pow(0.985, Math.abs(tick) % 60)).toFixed(3)}${NB}▸${NB}ep${12 + Math.abs(tick)}`;
      const fs = ah * 0.43;
      const pxp = num(aw / 128);
      defs.push(`<pattern id="${id("px")}" patternUnits="userSpaceOnUse" x="${num(ax)}" y="${num(ay)}" width="${pxp}" height="${pxp}"><rect width="${pxp}" height="${num(pxp * 0.22)}" fill="${glass}"/><rect width="${num(pxp * 0.22)}" height="${pxp}" fill="${glass}"/></pattern>`);
      const ta = `font-family="${MONO}" font-size="${num(fs)}" font-weight="700" textLength="${num(aw)}" lengthAdjust="spacingAndGlyphs"`;
      const line = (txt, y) => `<text x="${num(ax)}" y="${num(y)}" ${ta}>${esc(txt)}</text>`;
      out.push(`<g fill="${oc}" stroke="${oc}" stroke-width="0.35" opacity="0.28">${line(l1, ay + ah * 0.42)}${line(l2, ay + ah * 0.93)}</g>`);
      out.push(`<g fill="${mix(oc, WHITE, 0.25)}">${line(l1, ay + ah * 0.42)}${line(l2, ay + ah * 0.93)}</g>`);
      out.push(`<rect x="${num(ax)}" y="${num(ay - 0.3)}" width="${num(aw)}" height="${num(ah + 0.6)}" fill="${url("px")}" opacity="0.4"/>`);
      // glass reflection and cutout edge
      out.push(`<path d="M${num(o.x + o.w * 0.55)} ${num(o.y)}h${num(o.w * 0.18)}l${num(-o.h * 0.9)} ${num(o.h)}h${num(-o.w * 0.18)}Z" fill="${WHITE}" opacity="0.06"/>`);
      out.push(rr(o.x + 0.2, o.y + 0.2, o.w - 0.4, o.h - 0.4, 0.8, `fill="none" stroke="${url("rimin")}" stroke-width="0.4"`));
    }

    // shadows of caps and knobs, in one blurred group
    const cb = D.capBottom;
    const XDA = s.capProfile === "XDA";
    const ct = XDA ? D.capTopXDA : D.capTopDSA;
    const kr = D.ec11.knobDiameter / 2;
    let shadows = "";
    keys.forEach(k => { shadows += rr(k.x + (P - cb) / 2 + 0.5, k.y + (P - cb) / 2 + 1.1, cb, cb, 2.2); });
    L.dials.forEach(dl => { shadows += `<circle cx="${num(dl.x + (s.knob === "puck" ? 0.4 : 0.9))}" cy="${num(dl.y + (s.knob === "puck" ? 0.7 : 1.8))}" r="${num(kr + 0.2)}"/>`; });
    // switch sockets visible between caps
    let sockets = "";
    keys.forEach(k => { sockets += rr(k.x + 0.15, k.y + 0.15, P - 0.3, P - 0.3, 1.4); });
    out.push(`<g fill="${mix(sh.base, BLACK, darkShell ? 0.4 : 0.22)}" opacity="0.35">${sockets}</g>`);
    out.push(`<g fill="${shadowCol}" opacity="${darkShell ? 0.6 : 0.4}" filter="${blur("ks", 0.9)}">${shadows}</g>`);

    // status glow around the agent caps
    const capType = s.agentCap;
    const haloOp = { frosted: 0.6, clear: 0.75, milky: 0.5 }[capType] || 0.6;
    let halos = "";
    agents.forEach((k, i) => { halos += rr(k.x - 0.6, k.y - 0.6, P + 1.2, P + 1.2, 4, `fill="${pal.status[statusOf(i)]}"`); });
    if (halos) out.push(`<g opacity="${haloOp}" filter="${blur("kh", 1.7)}">${halos}</g>`);

    const capBaseCol = pal.agentCapBase[capType] || pal.agentCapBase.frosted;
    const tint = { frosted: 0.55, clear: 0.68, milky: 0.4 }[capType] || 0.55;
    const skirtOp = { frosted: 0.93, clear: 0.8, milky: 1 }[capType] || 0.93;
    const madeSt = {};
    function statusGrads(st) {
      if (madeSt[st]) return; madeSt[st] = 1;
      const c = pal.status[st];
      const body = mix(capBaseCol, c, tint);
      lin("ak-" + st, 0, 0, 1, 1, [[0, mix(body, WHITE, 0.45)], [0.5, body], [1, mix(body, BLACK, 0.15)]]);
      const hotR = capType === "clear" ? 0.3 : capType === "milky" ? 0.62 : 0.45;
      rad("at-" + st, 0.5, 0.5, 0.72, [[0, mix(c, WHITE, capType === "milky" ? 0.65 : 0.82)], [hotR, mix(c, WHITE, capType === "clear" ? 0.15 : 0.3)], [1, mix(body, WHITE, 0.3)]]);
    }
    const cmdCol = pal.commandCap[s.commandCap] || pal.commandCap.white;
    const cmdDark = lum(cmdCol) < 0.45;
    lin("ck", 0, 0, 1, 1, [[0, mix(cmdCol, WHITE, cmdDark ? 0.18 : 0.6)], [0.5, cmdCol], [1, mix(cmdCol, BLACK, cmdDark ? 0.3 : 0.12)]]);
    rad("ct", 0.42, 0.38, 0.8, [[0, mix(cmdCol, WHITE, cmdDark ? 0.1 : 0.5)], [1, mix(cmdCol, BLACK, cmdDark ? 0.08 : 0.04)]]);
    const iconCol = cmdDark ? mix(cmdCol, WHITE, 0.82) : mix(cmdCol, BLACK, 0.62);
    const dishOp = XDA ? 0.5 : 0.95;
    const topR = XDA ? 2.4 : 3.1;
    const cmdNames = ["approve", "talk", "stop"];
    const cmdKeys = keys.filter(k => k.role === "command").sort((a, b2) => a.x - b2.x || a.y - b2.y);

    keys.forEach(k => {
      const cx = k.x + P / 2, cy = k.y + P / 2;
      const bx = cx - cb / 2, by = cy - cb / 2, tx = cx - ct / 2, ty = cy - ct / 2 - (XDA ? 0 : 0.35);
      let g1 = "";
      if (k.role === "agent") {
        const i = agents.indexOf(k), st = statusOf(i), c = pal.status[st];
        statusGrads(st);
        g1 += rr(bx, by, cb, cb, 2.2, `fill="${url("ak-" + st)}" opacity="${skirtOp}"`);
        g1 += rr(bx, by, cb, cb, 2.2, `fill="${url("wall")}" opacity="${capType === "clear" ? 0.6 : 0.85}"`);
        const swOp = capType === "clear" ? 0.28 : capType === "frosted" ? 0.1 : 0;
        if (swOp) g1 += `<g fill="none" stroke="${mix(c, BLACK, 0.45)}" opacity="${swOp}">${capType === "clear" ? rr(cx - 7, cy - 7, 14, 14, 1, 'stroke-width="0.3"') : ""}<path d="M${num(cx - 2)} ${num(cy)}h4M${num(cx)} ${num(cy - 2)}v4" stroke-width="1.1"/></g>`;
        g1 += rr(tx, ty, ct, ct, topR, `fill="${url("at-" + st)}" opacity="${capType === "clear" ? 0.88 : 0.96}"`);
        g1 += rr(tx, ty, ct, ct, topR, `fill="${url("dish")}" opacity="${dishOp * 0.75}"`);
        g1 += rr(tx + 0.2, ty + 0.2, ct - 0.4, ct - 0.4, topR - 0.2, `fill="none" stroke="${url("spec")}" stroke-width="0.4"`);
        g1 += rr(bx, by, cb, cb, 2.2, `fill="none" stroke="${mix(c, WHITE, 0.6)}" stroke-width="0.25" opacity="0.8"`);
        if (s.legends === "icons") g1 += `<text x="${num(tx + 1.4)}" y="${num(ty + 3.4)}" font-family="${MONO}" font-size="2.4" font-weight="700" fill="${mix(c, BLACK, 0.5)}" opacity="0.55">${i + 1}</text>`;
      } else {
        g1 += rr(bx, by, cb, cb, 2.2, `fill="${url("ck")}"`);
        g1 += rr(bx, by, cb, cb, 2.2, `fill="${url("wall")}" opacity="${cmdDark ? 0.5 : 0.7}"`);
        g1 += rr(tx, ty, ct, ct, topR, `fill="${url("ct")}"`);
        g1 += rr(tx, ty, ct, ct, topR, `fill="${url("dish")}" opacity="${dishOp * (cmdDark ? 0.45 : 0.65)}"`);
        g1 += rr(tx + 0.2, ty + 0.2, ct - 0.4, ct - 0.4, topR - 0.2, `fill="none" stroke="${url("spec")}" stroke-width="0.35" opacity="${cmdDark ? 0.4 : 0.9}"`);
        g1 += rr(bx, by, cb, cb, 2.2, `fill="none" stroke="${mix(cmdCol, BLACK, 0.2)}" stroke-width="0.2" opacity="0.6"`);
        if (s.legends === "icons") {
          const name = cmdNames[cmdKeys.indexOf(k) % 3];
          const icy = ty + ct / 2;
          const st1 = `fill="none" stroke="${iconCol}" stroke-width="0.75" stroke-linecap="round" stroke-linejoin="round"`;
          if (name === "approve") g1 += `<path d="M${num(cx - 2.6)} ${num(icy + 0.1)}l1.8 1.9l3.6 -4" ${st1}/>`;
          else if (name === "talk") g1 += `<g ${st1}>${rr(cx - 1.1, icy - 3, 2.2, 3.9, 1.1)}<path d="M${num(cx - 2.2)} ${num(icy - 0.4)}a2.2 2.2 0 0 0 4.4 0M${num(cx)} ${num(icy + 1.8)}v1.3M${num(cx - 1.1)} ${num(icy + 3.1)}h2.2"/></g>`;
          else g1 += rr(cx - 1.9, icy - 1.9, 3.8, 3.8, 0.45, `fill="${iconCol}"`);
        }
      }
      out.push(`<g>${g1}</g>`);
    });

    const kp = pal.knob[s.knob];
    const ang = (-50 + tick * 24) * Math.PI / 180;
    const alu = s.knob === "knurled-alu" || s.knob === "ringlit";
    if (L.dials.length) {
      lin("kside", 0, 0, 1, 1, [[0, mix(kp.ring, WHITE, 0.55)], [0.5, kp.ring], [1, mix(kp.ring, BLACK, 0.35)]]);
      if (alu) defs.push(`<radialGradient id="${id("spun")}" cx="0.5" cy="0.5" r="0.045" spreadMethod="repeat">${stops([[0, kp.face], [0.35, mix(kp.face, WHITE, 0.45)], [0.6, kp.face], [1, mix(kp.face, kp.ring, 0.55)]])}</radialGradient>`);
      else rad("kface", 0.4, 0.36, 0.75, [[0, mix(kp.face, WHITE, 0.7)], [0.7, kp.face], [1, mix(kp.face, kp.ring, 0.6)]]);
    }
    L.dials.forEach(dl => {
      const cx = dl.x, cy = dl.y;
      let k1 = "";
      if (s.knob === "ringlit") {
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(kr + 0.9)}" fill="none" stroke="${glow}" stroke-width="1.8" opacity="0.95" filter="${blur("gb", 1)}"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(kr + 0.45)}" fill="none" stroke="${mix(glow, WHITE, 0.45)}" stroke-width="0.6"/>`;
      }
      if (alu) {
        const rf = kr * 0.74;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(kr)}" fill="${url("kside")}"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(kr - 0.75)}" fill="none" stroke="${mix(kp.ring, BLACK, 0.45)}" stroke-width="1.4" stroke-dasharray="0.28 0.3" opacity="0.7"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(kr - 0.75)}" fill="none" stroke="${WHITE}" stroke-width="1.4" stroke-dasharray="0.12 0.46" opacity="0.35"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(rf + 0.35)}" fill="${mix(kp.ring, BLACK, 0.25)}" opacity="0.6"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(rf)}" fill="${url("spun")}"/>`;
        // anisotropic highlights of a spun finish
        [[-135, 0.2], [45, 0.2]].forEach(([a0, op]) => {
          [26, 15, 7].forEach(w => { k1 += `<path d="${wedge(cx, cy, rf, (a0 - w) * Math.PI / 180, (a0 + w) * Math.PI / 180)}" fill="${WHITE}" opacity="${op}"/>`; });
        });
        [[-45, 0.07], [135, 0.07]].forEach(([a0, op]) => {
          [24, 12].forEach(w => { k1 += `<path d="${wedge(cx, cy, rf, (a0 - w) * Math.PI / 180, (a0 + w) * Math.PI / 180)}" fill="${BLACK}" opacity="${op}"/>`; });
        });
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(rf - 0.15)}" fill="none" stroke="${url("spec")}" stroke-width="0.35"/>`;
        const pc = mix(kp.ring, BLACK, 0.55);
        k1 += `<path d="M${num(cx + rf * 0.3 * Math.cos(ang))} ${num(cy + rf * 0.3 * Math.sin(ang))}L${num(cx + rf * 0.86 * Math.cos(ang))} ${num(cy + rf * 0.86 * Math.sin(ang))}" stroke="${WHITE}" stroke-width="0.55" stroke-linecap="round" opacity="0.6" transform="translate(0.14 0.14)"/>`;
        k1 += `<path d="M${num(cx + rf * 0.3 * Math.cos(ang))} ${num(cy + rf * 0.3 * Math.sin(ang))}L${num(cx + rf * 0.86 * Math.cos(ang))} ${num(cy + rf * 0.86 * Math.sin(ang))}" stroke="${pc}" stroke-width="0.55" stroke-linecap="round"/>`;
      } else if (s.knob === "puck") {
        const rf = kr - 0.7;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(kr)}" fill="${url("kside")}"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(rf)}" fill="${url("kface")}"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(rf * 0.55)}" fill="none" stroke="${kp.ring}" stroke-width="0.2" opacity="0.6"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(rf - 0.1)}" fill="none" stroke="${url("spec")}" stroke-width="0.3"/>`;
        k1 += `<circle cx="${num(cx + rf * 0.78 * Math.cos(ang))}" cy="${num(cy + rf * 0.78 * Math.sin(ang))}" r="0.6" fill="${mix(kp.ring, BLACK, 0.45)}"/>`;
      } else {
        const frosted = s.knob === "frosted";
        const rf = kr * 0.8;
        const tintGlow = frosted && s.glowPlace !== "none";
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(kr)}" fill="${url("kside")}" opacity="${frosted ? 0.85 : 1}"/>`;
        if (tintGlow) k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(kr - 0.2)}" fill="none" stroke="${glow}" stroke-width="0.9" opacity="0.4"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(kr - 0.8)}" fill="none" stroke="${mix(kp.ring, BLACK, 0.3)}" stroke-width="1.3" stroke-dasharray="0.3 0.35" opacity="${frosted ? 0.25 : 0.4}"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(rf)}" fill="${url("kface")}" opacity="${frosted ? 0.92 : 1}"/>`;
        k1 += `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(rf - 0.15)}" fill="none" stroke="${url("spec")}" stroke-width="0.35"/>`;
        const pcol = frosted ? glow : mix(kp.ring, BLACK, 0.4);
        k1 += `<path d="M${num(cx + rf * 0.45 * Math.cos(ang))} ${num(cy + rf * 0.45 * Math.sin(ang))}L${num(cx + rf * 0.85 * Math.cos(ang))} ${num(cy + rf * 0.85 * Math.sin(ang))}" stroke="${pcol}" stroke-width="${frosted ? 0.8 : 0.6}" stroke-linecap="round"/>`;
      }
      out.push(`<g>${k1}</g>`);
    });

    if (opts.dims) {
      const dc = mix(pal.shell.smoke.top, pal.shell.iced.base, 0.35);
      const fmt = v => (Math.round(v * 10) / 10).toFixed(1).replace(/\.0$/, "");
      const yd = y0 + SH + 6, xd = x0 + SW + 6;
      const arrow = (x, y, dx, dy) => `<path d="M${num(x)} ${num(y)}l${num(dx * 1.6 - dy * 0.55)} ${num(dy * 1.6 - dx * 0.55)}l${num(dy * 1.1)} ${num(dx * 1.1)}Z" fill="${dc}" stroke="none"/>`;
      let d1 = `<g stroke="${dc}" stroke-width="0.25" fill="none">`;
      d1 += `<path d="M${num(x0)} ${num(y0 + SH + 1.5)}V${num(yd + 1.5)}M${num(x0 + SW)} ${num(y0 + SH + 1.5)}V${num(yd + 1.5)}M${num(x0)} ${num(yd)}H${num(x0 + SW)}"/>`;
      d1 += arrow(x0, yd, 1, 0) + arrow(x0 + SW, yd, -1, 0);
      d1 += `<path d="M${num(x0 + SW + 1.5)} ${num(y0)}H${num(xd + 1.5)}M${num(x0 + SW + 1.5)} ${num(y0 + SH)}H${num(xd + 1.5)}M${num(xd)} ${num(y0)}V${num(y0 + SH)}"/>`;
      d1 += arrow(xd, y0, 0, 1) + arrow(xd, y0 + SH, 0, -1) + `</g>`;
      const ft = `font-family="${SANS}" font-size="3" font-weight="600" fill="${dc}" text-anchor="middle"`;
      d1 += `<text x="${num(x0 + SW / 2)}" y="${num(yd + 4.4)}" ${ft}>${fmt(SW)} mm</text>`;
      d1 += `<text x="${num(xd + 4.4)}" y="${num(y0 + SH / 2)}" ${ft} transform="rotate(90 ${num(xd + 4.4)} ${num(y0 + SH / 2)})">${fmt(SH)} mm</text>`;
      out.push(d1);
    }

    const lbl = `${L.name} top view: ${s.shell} ${s.texture} shell, ${s.plate} plate, ${s.glowColor} ${s.glowPlace === "none" ? "no" : s.glowPlace} glow, ${s.knob} knob, ${(L.oled ? "OLED, " : "")}${keys.length} keys, ${num(SW)} × ${num(SH)} mm` + (opts.label ? ". " + opts.label : "");
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${vb.map(num).join(" ")}" role="img" aria-label="${esc(lbl)}" data-shell-w="${num(SW)}" data-shell-h="${num(SH)}"><title>${esc(lbl)}</title><defs>${defs.join("")}</defs>${out.join("")}</svg>`;
  };
  if (typeof module !== "undefined" && module.exports) module.exports = FB.renderTop;
})(typeof window !== "undefined" ? window : globalThis);
