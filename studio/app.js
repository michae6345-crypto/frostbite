/* Frostbite Studio page controller. FB.* calls are guarded so a module that fails to load
   degrades one panel instead of the whole page. */
(function () {
  "use strict";

  var FB = window.FB || (window.FB = {});
  var cat = FB.catalog || {};
  var OPTIONS = (cat.options && typeof cat.options === "object") ? cat.options : {};
  var AXES = Object.keys(OPTIONS).filter(function (k) { return Array.isArray(OPTIONS[k]) && OPTIONS[k].length; });
  var PAL = cat.palette || {};
  var STATUS_ORDER = ["idle", "run", "done", "needs", "error"];
  var STATUS_KEYS = (function () {
    var keys = PAL.status ? Object.keys(PAL.status) : [];
    var ordered = STATUS_ORDER.filter(function (k) { return keys.indexOf(k) !== -1 || !keys.length; });
    keys.forEach(function (k) { if (ordered.indexOf(k) === -1) ordered.push(k); });
    return ordered.length ? ordered : STATUS_ORDER.slice();
  })();
  var STATUS_FALLBACK_COLORS = { idle: "#eef2f5", run: "#3d8bff", done: "#2fbf5b", needs: "#ffb020", error: "#ff4d4f" };
  var STATUS_FALLBACK_LABELS = { idle: "Idle", run: "Working", done: "Done", needs: "Waiting on you", error: "Failed / NaN" };
  var MAX_COMPARE = 4;
  var PERM_TARGET = 36;
  var STORE_KEY = "frostbite-studio:v1";

  var reducedMotion = false;
  try { reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) { /* ignore */ }

  // helpers
  function $(id) { return document.getElementById(id); }
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function num(v) { return typeof v === "number" && isFinite(v); }
  function fmt(v) { return num(v) ? String(Math.round(v * 10) / 10) : "–"; }
  function humanize(v) {
    var s = String(v).replace(/[-_]+/g, " ").replace(/([a-z])([A-Z])/g, "$1 $2");
    return s.charAt(0).toUpperCase() + s.slice(1);
  }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function msgOf(item) {
    if (item == null) return "";
    if (typeof item === "string") return item;
    return item.msg || item.message || item.text || item.code || "";
  }
  function mulberry32(a) {
    return function () {
      a |= 0; a = a + 0x6D2B79F5 | 0;
      var t = Math.imul(a ^ a >>> 15, 1 | a);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  function hashStr(s) {
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function store(patch) {
    try {
      var cur = JSON.parse(localStorage.getItem(STORE_KEY) || "{}") || {};
      Object.keys(patch).forEach(function (k) { cur[k] = patch[k]; });
      localStorage.setItem(STORE_KEY, JSON.stringify(cur));
    } catch (e) { /* storage unavailable: conveniences only */ }
  }
  function loadStore() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || "{}") || {}; } catch (e) { return {}; }
  }
  var liveTimer = 0;
  function announce(text) {
    var el = $("live"); if (!el) return;
    el.textContent = "";
    clearTimeout(liveTimer);
    liveTimer = setTimeout(function () { el.textContent = text; }, 30);
  }
  function layoutOf(id) {
    try { if (typeof FB.layoutById === "function") return FB.layoutById(id) || null; } catch (e) { /* ignore */ }
    var list = arr(FB.layouts);
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return list[0] || null;
  }

  // labels
  var AXIS_FALLBACK_LABELS = {
    layout: "Layout", shell: "Shell plastic", texture: "Surface", plate: "Top plate", glowColor: "Glow colour",
    glowPlace: "Glow placement", corner: "Corner radius", bezel: "Bezel", knob: "Knob", oledColor: "OLED colour",
    capProfile: "Cap profile", agentCap: "Agent caps", commandCap: "Command caps", legends: "Legends",
    screws: "Screws", wordmark: "Wordmark", tilt: "Tilt", wordmarkText: "Wordmark text", statuses: "Agent slots"
  };
  var UNITS = { corner: " mm", bezel: " mm", tilt: "°" };

  function pickLabel(v) {
    if (v == null) return null;
    if (typeof v === "string") return v;
    if (typeof v === "object") return v.label || v.name || v.title || null;
    return null;
  }
  function axisLabel(axis) {
    var sources = [cat.axisLabels, cat.labels && cat.labels.axes, cat.labels && cat.labels.axis];
    for (var i = 0; i < sources.length; i++) {
      var l = sources[i] && pickLabel(sources[i][axis]);
      if (l) return l;
    }
    return AXIS_FALLBACK_LABELS[axis] || humanize(axis);
  }
  function valueLabel(axis, v) {
    if (axis === "layout") { var L = layoutOf(v); if (L && L.id === v && L.name) return L.name; }
    var info = cat.valueInfo && cat.valueInfo[axis] && cat.valueInfo[axis][v];
    if (info && pickLabel(info)) return pickLabel(info);
    if (typeof cat.valueLabel === "function") {
      try { var fl = cat.valueLabel(axis, v); if (typeof fl === "string" && fl && fl !== String(v)) return fl; } catch (e) { /* ignore */ }
    }
    var sources = [cat.labels && cat.labels[axis], cat.valueLabels && cat.valueLabels[axis], cat.names && cat.names[axis], cat.displayNames && cat.displayNames[axis]];
    for (var i = 0; i < sources.length; i++) {
      var l = sources[i] && pickLabel(sources[i][v]);
      if (l) return l;
    }
    if (typeof v === "number") return v + (UNITS[axis] || "");
    if (axis === "capProfile") return String(v);
    return humanize(v);
  }
  function valueDesc(axis, v) {
    var info = cat.valueInfo && cat.valueInfo[axis] && cat.valueInfo[axis][v];
    return (info && typeof info === "object" && (info.desc || info.description || info.note)) || "";
  }
  function statusLabel(k) {
    var src = cat.labels && cat.labels.status;
    return (src && pickLabel(src[k])) || STATUS_FALLBACK_LABELS[k] || humanize(k);
  }
  function statusColor(k) { return (PAL.status && PAL.status[k]) || STATUS_FALLBACK_COLORS[k] || "#ccc"; }
  function swatchFor(axis, v) {
    try {
      if (axis === "shell" && PAL.shell && PAL.shell[v]) return PAL.shell[v].top || PAL.shell[v].base;
      if (axis === "glowColor" && PAL.glow) return PAL.glow[v];
      if (axis === "commandCap" && PAL.commandCap) return PAL.commandCap[v];
      if (axis === "agentCap" && PAL.agentCapBase) return PAL.agentCapBase[v];
      if (axis === "oledColor" && PAL.oled) return PAL.oled[v];
      if (axis === "knob" && PAL.knob && PAL.knob[v]) return PAL.knob[v].face;
    } catch (e) { /* ignore */ }
    return null;
  }

  // spec model
  var DEFAULT = (function () {
    var d = cat.defaultSpec ? clone(cat.defaultSpec) : {};
    AXES.forEach(function (k) { if (OPTIONS[k].indexOf(d[k]) === -1) d[k] = OPTIONS[k][0]; });
    if (typeof d.wordmarkText !== "string") d.wordmarkText = "frostbite";
    if (!Array.isArray(d.statuses) || !d.statuses.length) d.statuses = ["run", "done", "run", "needs", "idle", "error"];
    return d;
  })();

  function cleanText(t) { return String(t || "").replace(/[^A-Za-z0-9 .\-_]/g, "").slice(0, 20); }

  function normalizeSpec(raw) {
    var s = clone(DEFAULT);
    if (!raw || typeof raw !== "object") return s;
    AXES.forEach(function (k) {
      if (raw[k] === undefined) return;
      var opts = OPTIONS[k];
      for (var i = 0; i < opts.length; i++) if (String(opts[i]) === String(raw[k])) { s[k] = opts[i]; return; }
    });
    if (typeof raw.wordmarkText === "string") s.wordmarkText = cleanText(raw.wordmarkText);
    if (Array.isArray(raw.statuses)) {
      var st = raw.statuses.filter(function (x) { return STATUS_KEYS.indexOf(x) !== -1; }).slice(0, 12);
      if (st.length) s.statuses = st;
    }
    Object.keys(DEFAULT).forEach(function (k) {
      if (AXES.indexOf(k) !== -1 || k === "wordmarkText" || k === "statuses") return;
      if (raw[k] !== undefined && typeof raw[k] === typeof DEFAULT[k]) s[k] = raw[k];
    });
    return s;
  }
  function designKey(s) { return AXES.map(function (k) { return s[k]; }).join("|") + "|" + (s.wordmarkText || ""); }

  // checks + renders
  var checkCache = new Map();
  function check(spec) {
    var key = designKey(spec);
    if (checkCache.has(key)) return checkCache.get(key);
    var r = null;
    try { r = typeof FB.check === "function" ? FB.check(clone(spec)) : null; }
    catch (e) { r = { ok: false, errors: [{ code: "checker", msg: "The rule checker crashed: " + e.message }] }; }
    if (!r || typeof r !== "object") r = { ok: true, errors: [], warnings: [{ code: "no-checker", msg: "Rule checker not loaded." }] };
    var out = {
      errors: arr(r.errors).map(function (x) { return { code: (x && x.code) || "", msg: msgOf(x) }; }),
      warnings: arr(r.warnings).map(function (x) { return { code: (x && x.code) || "", msg: msgOf(x) }; }),
      extras: arr(r.extras).map(function (x) {
        if (typeof x === "string") return { item: x, qty: 1, why: "" };
        return { item: (x && (x.item || x.name)) || "Part", qty: x && x.qty != null ? x.qty : 1, why: (x && x.why) || "" };
      }),
      stats: (r.stats && typeof r.stats === "object") ? r.stats : {}
    };
    out.ok = r.ok !== false && out.errors.length === 0;
    if (checkCache.size > 600) checkCache.clear();
    checkCache.set(key, out);
    return out;
  }
  function placeholder(text) { return '<div class="ph">' + esc(text) + "</div>"; }
  function renderSVG(fnName, spec, opts) {
    var fn = FB[fnName];
    if (typeof fn !== "function") return placeholder("Drawing module not loaded (" + fnName + ")");
    try {
      var s = clone(spec);
      s.wordmarkText = cleanText(s.wordmarkText);
      var out = fn(s, opts || {});
      if (typeof out !== "string" || out.indexOf("<svg") === -1) return placeholder("No drawing returned");
      return out;
    } catch (e) {
      if (window.console) console.error(fnName + " failed", e);
      return placeholder("Drawing failed: " + e.message);
    }
  }

  // state
  var saved = loadStore();
  var state = {
    spec: normalizeSpec(saved.spec || DEFAULT),
    locks: {},
    view: ["top", "side", "exploded"].indexOf(saved.view) !== -1 ? saved.view : "top",
    dims: !!saved.dims,
    simulate: !reducedMotion,
    t: 0,
    compare: [],
    permFilter: "mix",
    permSeed: 1,
    hideBad: !!saved.hideBad,
    theme: ["auto", "light", "dark"].indexOf(saved.theme) !== -1 ? saved.theme : "auto"
  };
  if (saved.locks && typeof saved.locks === "object") {
    AXES.forEach(function (k) { if (saved.locks[k]) state.locks[k] = true; });
  }
  arr(saved.compare).slice(0, MAX_COMPARE).forEach(function (c) {
    if (c && c.spec) state.compare.push({ name: String(c.name || "Pinned design").slice(0, 60), spec: normalizeSpec(c.spec) });
  });

  // theme
  function applyTheme() {
    var root = document.documentElement;
    if (state.theme === "auto") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", state.theme);
    var names = { auto: "Auto", light: "Light", dark: "Dark" };
    var lbl = $("theme-label"); if (lbl) lbl.textContent = names[state.theme];
    var btn = $("theme-toggle");
    if (btn) btn.setAttribute("aria-label", "Colour theme: " + names[state.theme].toLowerCase() + ". Click to change.");
  }

  // control groups
  var DEFAULT_GROUPS = [
    { title: "Form", axes: ["layout", "tilt", "plate"] },
    { title: "Shell", axes: ["shell", "texture", "corner", "bezel", "screws", "wordmark"] },
    { title: "Light", axes: ["glowColor", "glowPlace", "oledColor"] },
    { title: "Keys and dial", axes: ["capProfile", "agentCap", "commandCap", "legends", "knob"] }
  ];
  function axisIdOf(a) {
    if (typeof a === "string") return a;
    if (a && typeof a === "object") return a.key || a.id || a.axis || a.name || null;
    return null;
  }
  function uiGroups() {
    var raw = cat.axesForUI, groups = null;
    try {
      if (typeof raw === "function") raw = raw();
      if (Array.isArray(raw) && raw.length) {
        if (raw[0] && typeof raw[0] === "object" && (Array.isArray(raw[0].axes) || Array.isArray(raw[0].keys) || Array.isArray(raw[0].items))) {
          groups = raw.map(function (g) {
            return { title: g.title || g.group || g.name || g.label || "Options", axes: arr(g.axes || g.keys || g.items).concat(arr(g.text)).map(axisIdOf) };
          });
        } else {
          var byName = {}, order = [];
          raw.forEach(function (a) {
            var id = axisIdOf(a); if (!id) return;
            var g = (a && typeof a === "object" && (a.group || a.section)) || "Options";
            if (!byName[g]) { byName[g] = []; order.push(g); }
            byName[g].push(id);
          });
          groups = order.map(function (g) { return { title: g, axes: byName[g] }; });
        }
      } else if (raw && typeof raw === "object") {
        groups = Object.keys(raw).map(function (g) { return { title: g, axes: arr(raw[g]).map(axisIdOf) }; });
      }
    } catch (e) { groups = null; }
    if (!groups || !groups.length) groups = clone(DEFAULT_GROUPS);
    var seen = {};
    groups.forEach(function (g) {
      g.axes = g.axes.filter(function (a) {
        if (!a || seen[a]) return false;
        if (AXES.indexOf(a) === -1 && a !== "wordmarkText" && a !== "statuses") return false;
        seen[a] = true; return true;
      });
    });
    var missing = AXES.filter(function (a) { return !seen[a]; });
    if (missing.length) groups.push({ title: "More", axes: missing });
    groups = groups.filter(function (g) { return g.axes.length; });
    if (!seen.statuses) groups.push({ title: "Agent slots", axes: ["statuses"] });
    if (!seen.wordmarkText) {
      var host = groups.filter(function (g) { return g.axes.indexOf("wordmark") !== -1; })[0] || groups[0];
      var at = host.axes.indexOf("wordmark");
      host.axes.splice(at === -1 ? host.axes.length : at + 1, 0, "wordmarkText");
    }
    return groups;
  }

  var LOCK_SVG = '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">' +
    '<rect x="3" y="7" width="10" height="7" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.4"/>' +
    '<path class="lk-closed" d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" fill="none" stroke="currentColor" stroke-width="1.4"/>' +
    '<path class="lk-open" d="M5.5 7V5a2.5 2.5 0 0 1 4.9-.7" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>';

  function buildControls() {
    var form = $("controls-form"); if (!form) return;
    var html = "";
    uiGroups().forEach(function (g, gi) {
      html += '<section class="ctl-group" aria-labelledby="grp-' + gi + '"><h4 id="grp-' + gi + '">' + esc(g.title) + "</h4>";
      g.axes.forEach(function (axis) {
        if (axis === "wordmarkText") {
          html += '<div class="axis"><div class="axis-head"><label class="axis-label" for="ax-wordmarkText">' + esc(axisLabel("wordmarkText")) +
            '</label></div><input class="text-input" id="ax-wordmarkText" name="wordmarkText" type="text" maxlength="20" spellcheck="false" autocapitalize="off"></div>';
          return;
        }
        if (axis === "statuses") {
          html += '<div class="axis" role="group" aria-labelledby="ax-statuses-l"><div class="axis-head"><span class="axis-label" id="ax-statuses-l">Slot status (click to cycle)</span></div>' +
            '<div class="slots" id="ax-statuses"></div></div>';
          return;
        }
        var opts = OPTIONS[axis];
        html += '<fieldset class="axis" id="axis-' + axis + '"><legend class="sr-only">' + esc(axisLabel(axis)) + "</legend>" +
          '<div class="axis-head"><span class="axis-label" aria-hidden="true">' + esc(axisLabel(axis)) + "</span>" +
          '<button type="button" class="lock" id="lock-' + axis + '" data-lock="' + axis + '" aria-pressed="false" aria-label="Lock ' + esc(axisLabel(axis)) + ' when shuffling">' + LOCK_SVG + "</button></div>" +
          '<div class="seg">';
        opts.forEach(function (v, i) {
          var id = "ax-" + axis + "-" + i, sw = swatchFor(axis, v), desc = valueDesc(axis, v);
          html += '<input type="radio" id="' + id + '" name="ax-' + axis + '" value="' + i + '" data-axis="' + axis + '">' +
            '<label for="' + id + '"' + (desc ? ' title="' + esc(desc) + '"' : "") + ">" + (sw ? '<span class="swatch round" style="background:' + esc(sw) + '"></span>' : "") + esc(valueLabel(axis, v)) + "</label>";
        });
        html += "</div></fieldset>";
      });
      html += "</section>";
    });
    form.innerHTML = html;

    form.addEventListener("change", function (e) {
      var t = e.target;
      if (t && t.dataset && t.dataset.axis) {
        var axis = t.dataset.axis, v = OPTIONS[axis][+t.value];
        if (v !== undefined) setAxis(axis, v);
      }
    });
    var wm = $("ax-wordmarkText");
    if (wm) {
      var wmTimer = 0;
      wm.addEventListener("input", function () {
        var clean = cleanText(wm.value);
        clearTimeout(wmTimer);
        wmTimer = setTimeout(function () { state.spec.wordmarkText = clean; specChanged({ skipControls: true }); }, 140);
      });
    }
    form.addEventListener("submit", function (e) { e.preventDefault(); });
    form.addEventListener("click", function (e) {
      var lock = e.target.closest && e.target.closest("[data-lock]");
      if (lock) {
        var a = lock.getAttribute("data-lock");
        state.locks[a] = !state.locks[a];
        if (!state.locks[a]) delete state.locks[a];
        syncLocks(); persist();
        announce(axisLabel(a) + (state.locks[a] ? " locked" : " unlocked"));
        if (state.permFilter === "mix") schedulePerms();
        return;
      }
      var slot = e.target.closest && e.target.closest("[data-slot]");
      if (slot) {
        var i = +slot.getAttribute("data-slot");
        var orig = state.spec.statuses, st = orig.slice();
        while (st.length <= i) st.push(orig[st.length % orig.length] || "idle");
        var next = STATUS_KEYS[(STATUS_KEYS.indexOf(st[i]) + 1) % STATUS_KEYS.length];
        st[i] = next; state.spec.statuses = st;
        specChanged({ skipPerms: true });
        announce("Slot " + (i + 1) + ": " + statusLabel(next));
      }
    });
  }

  function agentSlotCount() {
    var L = layoutOf(state.spec.layout);
    var n = L ? arr(L.keys).filter(function (k) { return k.role === "agent"; }).length : 6;
    return Math.max(n, 1);
  }
  function syncControls() {
    AXES.forEach(function (axis) {
      var i = OPTIONS[axis].indexOf(state.spec[axis]);
      var el = $("ax-" + axis + "-" + i);
      if (el && !el.checked) el.checked = true;
    });
    var wm = $("ax-wordmarkText");
    if (wm && document.activeElement !== wm) wm.value = state.spec.wordmarkText || "";
    syncSlots();
    syncLocks();
  }
  function syncSlots() {
    var box = $("ax-statuses"); if (!box) return;
    var n = agentSlotCount(), st = state.spec.statuses, html = "";
    if (box.children.length === n) {
      for (var j = 0; j < n; j++) {
        var kk = st[j % st.length], b = box.children[j];
        b.setAttribute("aria-label", "Agent slot " + (j + 1) + ": " + statusLabel(kk) + ". Click for next status.");
        b.querySelector(".swatch").style.background = statusColor(kk);
        b.querySelector(".slot-t").textContent = statusLabel(kk);
      }
      return;
    }
    for (var i = 0; i < n; i++) {
      var k = st[i % st.length];
      html += '<button type="button" class="slot" data-slot="' + i + '" aria-label="Agent slot ' + (i + 1) + ": " + esc(statusLabel(k)) + '. Click for next status.">' +
        '<span class="swatch" style="background:' + esc(statusColor(k)) + '"></span><span class="slot-n">' + (i + 1) + '</span><span class="slot-t">' + esc(statusLabel(k)) + "</span></button>";
    }
    box.innerHTML = html;
  }
  function syncLocks() {
    AXES.forEach(function (a) {
      var b = $("lock-" + a);
      if (b) {
        var on = !!state.locks[a];
        b.setAttribute("aria-pressed", on ? "true" : "false");
        b.setAttribute("aria-label", (on ? "Unlock " : "Lock ") + axisLabel(a) + " when shuffling");
      }
    });
    var any = Object.keys(state.locks).length;
    var u = $("btn-unlock"); if (u) { u.disabled = !any; u.textContent = any ? "Unlock all (" + any + ")" : "Unlock all"; }
    renderPermFilters();
  }

  // spec changes
  var rafPending = false, permTimer = 0, persistTimer = 0;
  function setAxis(axis, v) {
    state.spec[axis] = v;
    specChanged({ skipControls: true });
  }
  function setSpec(spec, why) {
    var keepWordmark = state.spec.wordmarkText;
    state.spec = normalizeSpec(spec);
    if (!spec || typeof spec.wordmarkText !== "string") state.spec.wordmarkText = keepWordmark;
    specChanged({});
    if (why) announce(why);
  }
  function specChanged(o) {
    o = o || {};
    if (!o.skipControls) syncControls(); else syncSlots();
    if (!rafPending) {
      rafPending = true;
      nextFrame(function () { rafPending = false; renderStage(); renderChecks(); syncPinButtons(); markCurrentCards(); });
    }
    if (!o.skipPerms) schedulePerms();
    persist();
  }
  // rAF alone stalls in hidden previews/background tabs; whichever fires first wins.
  function nextFrame(fn) {
    var done = false;
    function run() { if (!done) { done = true; fn(); } }
    try { requestAnimationFrame(run); } catch (e) { /* ignore */ }
    setTimeout(run, 64);
  }
  function persist() {
    clearTimeout(persistTimer);
    persistTimer = setTimeout(function () {
      store({ spec: state.spec, locks: state.locks, view: state.view, dims: state.dims, compare: state.compare, hideBad: state.hideBad, theme: state.theme });
    }, 400);
  }

  // stage
  function renderStage() {
    var s = state.spec, L = layoutOf(s.layout);
    var nm = $("stage-name"); if (nm) nm.textContent = (L && L.name) || valueLabel("layout", s.layout);
    var bl = $("stage-blurb"); if (bl) bl.textContent = (L && L.blurb) || "";
    renderView();
    var cap = $("spec-caption");
    if (cap) {
      var parts = [
        valueLabel("shell", s.shell) + " shell, " + valueLabel("texture", s.texture).toLowerCase(),
        valueLabel("plate", s.plate) + " plate",
        valueLabel("glowColor", s.glowColor) + " glow" + (s.glowPlace === "none" ? " off" : " in " + valueLabel("glowPlace", s.glowPlace).toLowerCase()),
        valueLabel("knob", s.knob) + " knob",
        s.capProfile + " caps",
        "r" + s.corner + " corners, " + s.bezel + " mm bezel, " + s.tilt + "° tilt"
      ];
      cap.textContent = parts.join(" · ");
    }
    var json = $("spec-json"); if (json) json.value = JSON.stringify(s, null, 2);
  }
  function renderView() {
    var panel = $("view-panel"); if (!panel) return;
    var s = state.spec, opts = { t: state.t, idPrefix: "main-" + state.view + "-", dims: state.dims };
    var fn = state.view === "side" ? "renderSide" : state.view === "exploded" ? "renderExploded" : "renderTop";
    panel.innerHTML = renderSVG(fn, s, opts);
  }
  function setView(v, focus) {
    state.view = v;
    ["top", "side", "exploded"].forEach(function (k) {
      var b = $("tab-" + k); if (!b) return;
      var on = k === v;
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.tabIndex = on ? 0 : -1;
      if (on && focus) b.focus();
    });
    var panel = $("view-panel"); if (panel) panel.setAttribute("aria-labelledby", "tab-" + v);
    renderView(); persist();
  }

  function renderLegend() {
    var ul = $("status-legend"); if (!ul) return;
    ul.innerHTML = STATUS_KEYS.map(function (k) {
      return '<li><span class="swatch" style="background:' + esc(statusColor(k)) + '"></span>' + esc(statusLabel(k)) + "</li>";
    }).join("") + '<li><span class="swatch" style="background:' + esc((PAL.commandCap && PAL.commandCap.white) || "#f7f7f4") + '"></span>Command key (Approve, Talk, Stop)</li>';
  }

  // simulate
  var simTimer = 0;
  function setSimulate(on) {
    state.simulate = on;
    var b = $("toggle-sim"); if (b) b.setAttribute("aria-pressed", on ? "true" : "false");
    clearInterval(simTimer);
    if (on) {
      simTimer = setInterval(function () {
        if (document.hidden) return;
        state.t = (state.t + 1) % 1000;
        renderView();
      }, 1400);
    }
  }

  // checks panel
  function meter(label, val, max, opts) {
    opts = opts || {};
    var v = num(val) ? val : 0, m = num(max) && max > 0 ? max : 1;
    var over = v > m, pct = Math.min(100, Math.round(v / m * 100));
    var cls = over ? "over" : (opts.warnAtFull && v === m ? "full" : "");
    var ticks = "";
    if (m <= 20) { for (var i = 0; i < m; i++) ticks += "<i></i>"; }
    return '<div class="meter-row"><span>' + esc(label) + '</span><span class="m-val' + (over ? " over" : "") + '">' + fmt(val) + " / " + fmt(max) + (opts.unit || "") + "</span>" +
      '<div class="meter ' + cls + '" role="meter" aria-label="' + esc(label) + '" aria-valuemin="0" aria-valuemax="' + m + '" aria-valuenow="' + v + '"><span style="width:' + pct + '%"></span>' +
      (ticks ? '<span class="meter-ticks" aria-hidden="true">' + ticks + "</span>" : "") + "</div></div>";
  }
  function envelopeSVG(w, h, limW, limH, label) {
    var pad = 6, scale = 100 / Math.max(limW, limH);
    var lw = limW * scale, lh = limH * scale;
    var vw = num(w) ? w * scale : 0, vh = num(h) ? h * scale : 0;
    var over = (num(w) && w > limW) || (num(h) && h > limH);
    var VW = Math.max(lw, vw) + pad * 2, VH = Math.max(lh, vh) + pad * 2;
    return '<svg viewBox="0 0 ' + fmt(VW) + " " + fmt(VH) + '" role="img" aria-label="' + esc(label) + '">' +
      '<rect class="env-limit" x="' + pad + '" y="' + pad + '" width="' + fmt(lw) + '" height="' + fmt(lh) + '" rx="2"/>' +
      (vw && vh ? '<rect class="env-fill' + (over ? " over" : "") + '" x="' + pad + '" y="' + pad + '" width="' + fmt(vw) + '" height="' + fmt(vh) + '" rx="2"/>' : "") +
      "</svg>";
  }
  function heightSVG(hgt, lim) {
    var scale = 100 / lim, pad = 6, bh = num(hgt) ? Math.min(hgt, lim * 1.2) * scale : 0, over = num(hgt) && hgt > lim;
    var VH = 100 * 1.2 + pad * 2;
    var base = pad + 120;
    return '<svg viewBox="0 0 34 ' + VH + '" role="img" aria-label="Case height ' + fmt(hgt) + ' of ' + lim + ' millimetres">' +
      '<rect class="env-limit" x="' + pad + '" y="' + (base - 100) + '" width="22" height="100" rx="2"/>' +
      (bh ? '<rect class="env-fill' + (over ? " over" : "") + '" x="' + pad + '" y="' + fmt(base - bh) + '" width="22" height="' + fmt(bh) + '" rx="2"/>' : "") +
 "</svg>";
  }
  function renderChecks() {
    var body = $("checks-body"); if (!body) return;
    var c = check(state.spec), st = c.stats || {}, L = layoutOf(state.spec.layout);
    var html = "";

    html += '<div class="chk-block"><h4>Rules</h4><ul class="issues">';
    c.errors.forEach(function (e) { html += '<li class="issue err"><span class="ic">ERROR</span><span>' + esc(e.msg) + (e.code ? "<code>" + esc(e.code) + "</code>" : "") + "</span></li>"; });
    c.warnings.forEach(function (w) { html += '<li class="issue warn"><span class="ic">WARN</span><span>' + esc(w.msg) + (w.code ? "<code>" + esc(w.code) + "</code>" : "") + "</span></li>"; });
    if (!c.errors.length && !c.warnings.length) html += '<li class="issue good"><span class="ic">PASS</span><span>Fits every Hackpad rule the checker knows.</span></li>';
    else if (!c.errors.length) html += '<li class="issue good"><span class="ic">PASS</span><span>No hard rule broken.</span></li>';
    html += "</ul></div>";

    html += '<div class="chk-block"><h4>Budget</h4><div class="meters">' +
      meter("GPIO on XIAO RP2040", st.pins, st.pinsMax || 11, { warnAtFull: true }) +
      meter("SK6812 MINI-E LEDs", st.leds, st.ledsKit || 16) +
      meter("MX switches", st.switches, 16) +
      meter("EC11E encoders", st.encoders, 2) +
      "</div></div>";

    var pcb = st.pcb || {}, sh = st.shell || {};
    html += '<div class="chk-block"><h4>Envelope</h4><div class="env">' +
      "<figure>" + envelopeSVG(pcb.w, pcb.h, 100, 100, "PCB " + fmt(pcb.w) + " by " + fmt(pcb.h) + " millimetres inside a 100 by 100 limit") +
      '<figcaption>PCB<br><span class="mono">' + fmt(pcb.w) + " × " + fmt(pcb.h) + " mm</span><br>limit 100 × 100, 2-layer</figcaption></figure>" +
      '<figure><div class="env-pair">' +
      envelopeSVG(sh.w, sh.h, 200, 200, "Case footprint " + fmt(sh.w) + " by " + fmt(sh.h) + " millimetres inside a 200 by 200 limit") +
      heightSVG(sh.height, 100) + "</div>" +
      '<figcaption>Printed case<br><span class="mono">' + fmt(sh.w) + " × " + fmt(sh.h) + " × " + fmt(sh.height) + " mm</span><br>limit 200 × 200 × 100</figcaption></figure>" +
      "</div></div>";

    var switches = num(st.switches) ? st.switches : (L ? arr(L.keys).length : 0);
    var diodes = switches + (L && L.dialPress ? 1 : 0);
    var rows = [
      ["Seeed XIAO RP2040", "1"],
      ["MX switch, Gateron Yellow KS-3", fmt(switches) + " / 16"],
      [state.spec.capProfile === "DSA" ? "DSA keycap, white blank" : "Keycaps, " + state.spec.capProfile + " profile", fmt(switches)],
      ["EC11E encoder with push", fmt(st.encoders) + " / 2"],
      ['0.91" 128×32 I²C OLED', fmt(num(st.oled) ? st.oled : (L && L.oled ? 1 : 0)) + " / 1"],
      ["SK6812 MINI-E LED", fmt(st.leds) + " / 16"],
      ["1N4148 diode", fmt(diodes) + " / 20"],
      ["M3×16 screw + heat-set insert", "≤ 6"]
    ];
    html += '<div class="chk-block"><h4>Parts</h4><table class="bom"><tbody>';
    rows.forEach(function (r) { html += "<tr><th scope=\"row\">" + esc(r[0]) + "</th><td>" + esc(r[1]) + "</td></tr>"; });
    c.extras.forEach(function (x) {
      html += '<tr class="extra"><th scope="row">' + esc(x.item) + (x.why ? '<span class="why">' + esc(x.why) + "</span>" : "") + "</th><td>buy × " + esc(x.qty) + "</td></tr>";
    });
    html += "</tbody></table>" + (c.extras.length ? "" : '<p class="muted small" style="margin-top:6px">Nothing to buy outside the kit.</p>') + "</div>";
    body.innerHTML = html;

    var v = $("verdict");
    if (v) {
      var cls = c.errors.length ? "is-err" : c.warnings.length ? "is-warn" : "";
      var text = c.errors.length ? "<b>Breaks " + c.errors.length + " rule" + (c.errors.length > 1 ? "s" : "") + ":</b> " + esc(c.errors[0].msg)
        : c.warnings.length ? "<b>" + c.warnings.length + " warning" + (c.warnings.length > 1 ? "s" : "") + ":</b> " + esc(c.warnings[0].msg)
        : "<b>Passes the Hackpad rules.</b>" + (c.extras.length ? " " + c.extras.length + " extra part" + (c.extras.length > 1 ? "s" : "") + " to buy." : " Kit parts only.");
      v.className = "verdict " + cls;
      v.innerHTML = '<span class="dot" aria-hidden="true"></span><span>' + text + '</span><span class="v-pins mono">' + fmt(st.pins) + "/" + fmt(st.pinsMax || 11) + " GPIO</span>";
    }
  }

  // copy JSON
  var copyTimer = 0;
  function copySpec() {
    var text = JSON.stringify(state.spec, null, 2);
    var label = $("copy-label");
    function done(msg) {
      if (label) label.textContent = msg;
      announce(msg);
      clearTimeout(copyTimer);
      copyTimer = setTimeout(function () { if (label) label.textContent = "Copy spec JSON"; }, 1800);
    }
    function fallback() {
      var d = $("json-details"), ta = $("spec-json");
      if (d) d.open = true;
      if (ta) {
        ta.value = text; ta.focus(); ta.select();
        var ok = false;
        try { ok = document.execCommand && document.execCommand("copy"); } catch (e) { ok = false; }
        done(ok ? "Copied" : "Selected, press Ctrl or Cmd + C");
      }
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () { done("Copied"); }, fallback);
      } else fallback();
    } catch (e) { fallback(); }
  }

  // lazy thumbnails
  var thumbData = new WeakMap();
  var thumbQueue = [], pumping = false;
  var io = ("IntersectionObserver" in window) ? new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (en.isIntersecting) { io.unobserve(en.target); thumbQueue.push(en.target); }
    });
    pump();
  }, { rootMargin: "300px 0px" }) : null;
  function pump() {
    if (pumping) return;
    pumping = true;
    setTimeout(step, 0);
  }
  function step() {
    var start = performance.now();
    while (thumbQueue.length && performance.now() - start < 10) {
      var el = thumbQueue.shift();
      if (!el.isConnected) continue;
      var d = thumbData.get(el); if (!d) continue;
      el.innerHTML = renderSVG("renderTop", d.spec, { t: 0, idPrefix: d.id, dims: false });
    }
    if (thumbQueue.length) setTimeout(step, 16); else pumping = false;
  }
  function observeThumbs(root) {
    var els = root.querySelectorAll("[data-thumb]");
    for (var i = 0; i < els.length; i++) {
      if (io) io.observe(els[i]); else thumbQueue.push(els[i]);
    }
    if (!io) pump();
  }
  var thumbSeq = 0;
  function nextThumbId(prefix) { thumbSeq += 1; return prefix + thumbSeq + "-"; }

  // cards
  var PIN_SVG = '<svg viewBox="0 0 12 12" aria-hidden="true" focusable="false"><path d="M1.5 3h9M1.5 6h9M1.5 9h9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>';
  var cardItems = {}; // listId -> array of {name, spec}

  function badgeFor(c) {
    if (!c.ok) return '<span class="badge err">Breaks rule</span>';
    if (c.warnings.length) return '<span class="badge warn">' + c.warnings.length + " warning" + (c.warnings.length > 1 ? "s" : "") + "</span>";
    return '<span class="badge ok">Pass</span>';
  }
  function cardHTML(listId, i, item, prefix) {
    var c = check(item.spec), sh = c.stats.shell || {};
    var bad = !c.ok;
    var errText = bad ? c.errors.map(function (e) { return e.msg; }).join(" · ") : "";
    var key = designKey(item.spec);
    var pinned = isPinned(item.spec);
    return '<article class="card' + (bad ? " is-bad" : "") + '"' + (bad ? ' title="' + esc(errText) + '"' : "") + ">" +
      '<div class="thumb" data-thumb data-tid="' + esc(nextThumbId(prefix)) + '" data-list="' + listId + '" data-i="' + i + '"></div>' +
      '<div class="card-body">' +
      '<button type="button" class="pin" data-pin="' + listId + ":" + i + '" data-pin-key="' + esc(key) + '" aria-pressed="' + (pinned ? "true" : "false") + '" aria-label="Pin ' + esc(item.name) + ' to compare">' + PIN_SVG + "Compare</button>" +
      '<h4 class="card-title">' + esc(item.name) + "</h4>" +
      (item.note ? '<p class="card-note">' + esc(item.note) + "</p>" : "") +
      (bad ? '<p class="card-err">' + esc(errText) + "</p>" : "") +
      '<div class="card-meta">' + badgeFor(c) + '<span class="mono">' + fmt(sh.w) + " × " + fmt(sh.h) + " mm</span>" +
      '<span class="mono">' + fmt(c.stats.pins) + "/" + fmt(c.stats.pinsMax || 11) + " GPIO</span></div>" +
      "</div>" +
      '<button type="button" class="card-hit" data-load="' + listId + ":" + i + '" data-spec-key="' + esc(designKey(item.spec)) + '" aria-label="Load ' + esc(item.name) + ' into the configurator"></button>' +
      "</article>";
  }
  function bindThumbData(root) {
    var els = root.querySelectorAll("[data-thumb]");
    for (var i = 0; i < els.length; i++) {
      var el = els[i], list = cardItems[el.getAttribute("data-list")], item = list && list[+el.getAttribute("data-i")];
      if (item) thumbData.set(el, { spec: item.spec, id: el.getAttribute("data-tid") });
    }
    observeThumbs(root);
  }
  function itemFromRef(ref) {
    var p = String(ref).split(":"), list = cardItems[p[0]];
    return list ? list[+p[1]] : null;
  }
  function onCardClick(e) {
    var pin = e.target.closest && e.target.closest("[data-pin]");
    if (pin) { var it = itemFromRef(pin.getAttribute("data-pin")); if (it) togglePin(it); return; }
    var hit = e.target.closest && e.target.closest("[data-load]");
    if (hit) {
      var item = itemFromRef(hit.getAttribute("data-load"));
      if (!item) return;
      var keep = state.spec.statuses;
      var spec = clone(item.spec);
      if (!item.keepStatuses) spec.statuses = keep;
      setSpec(spec, "Loaded " + item.name);
      var st = $("configurator");
      if (st && st.scrollIntoView) st.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
    }
  }
  function markCurrentCards() {
    var k = designKey(state.spec);
    var hits = document.querySelectorAll("[data-spec-key]");
    for (var i = 0; i < hits.length; i++) {
      var card = hits[i].parentNode;
      if (card && card.classList) card.classList.toggle("is-current", hits[i].getAttribute("data-spec-key") === k);
    }
  }

  // presets
  function renderPresets() {
    var grid = $("preset-grid"); if (!grid) return;
    var list = arr(cat.presets).filter(function (p) { return p && (p.spec || typeof p === "object"); });
    if (!list.length) list = [{ id: "frostbite", name: "Frostbite", spec: DEFAULT }];
    cardItems.p = list.map(function (p, i) {
      var spec = normalizeSpec(p.spec || p);
      return { name: String(p.name || p.title || p.id || "Preset " + (i + 1)), note: String(p.note || p.blurb || p.description || ""), spec: spec, keepStatuses: !!(p.spec && p.spec.statuses) };
    });
    grid.innerHTML = cardItems.p.map(function (item, i) { return cardHTML("p", i, item, "pr"); }).join("");
    bindThumbData(grid);
    markCurrentCards();
  }

  // permutations
  var MIX_ORDER = ["layout", "shell", "glowColor", "plate", "knob", "glowPlace", "commandCap", "agentCap", "texture", "corner", "screws", "bezel", "tilt", "capProfile", "oledColor", "wordmark", "legends"];
  var PARTNER = {
    layout: "shell", shell: "glowColor", glowColor: "glowPlace", glowPlace: "glowColor", plate: "glowPlace",
    texture: "shell", corner: "bezel", bezel: "corner", knob: "shell", oledColor: "glowColor", capProfile: "plate",
    agentCap: "glowColor", commandCap: "shell", legends: "commandCap", screws: "corner", wordmark: "plate", tilt: "plate"
  };
  var MIX_PAIRS = [["shell", "glowColor"], ["plate", "glowPlace"], ["knob", "commandCap"], ["layout", "shell"], ["texture", "corner"]];

  function buildVariants(base, filter, seed) {
    var out = [], seen = {};
    seen[designKey(base)] = true;
    function add(changes, group) {
      var s = normalizeSpec(Object.assign(clone(base), changes));
      var k = designKey(s);
      if (seen[k]) return false;
      seen[k] = true;
      out.push({ spec: s, changes: changes, group: group });
      return true;
    }
    var rng = mulberry32(seed * 7919 + hashStr(designKey(base) + filter));
    function others(a) { return OPTIONS[a].filter(function (v) { return v !== base[a]; }); }
    function shuffled(list) {
      var l = list.slice();
      for (var i = l.length - 1; i > 0; i--) { var j = Math.floor(rng() * (i + 1)); var t = l[i]; l[i] = l[j]; l[j] = t; }
      return l;
    }

    if (filter === "mix") {
      var axes = MIX_ORDER.filter(function (a) { return AXES.indexOf(a) !== -1; })
        .concat(AXES.filter(function (a) { return MIX_ORDER.indexOf(a) === -1; }))
        .filter(function (a) { return !state.locks[a]; });
      var singlesCap = PERM_TARGET - 8;
      axes.forEach(function (a) {
        var vals = others(a);
        if (!vals.length) return;
        if (out.length + vals.length > singlesCap) {
          if (out.length >= singlesCap - 1) return;
          vals = (seed > 1 ? shuffled(vals) : vals).slice(0, singlesCap - out.length);
        }
        vals.forEach(function (v) { var ch = {}; ch[a] = v; add(ch, a); });
      });
      var guard = 0;
      var pairs = MIX_PAIRS.filter(function (p) { return AXES.indexOf(p[0]) !== -1 && AXES.indexOf(p[1]) !== -1 && !state.locks[p[0]] && !state.locks[p[1]]; });
      guard = 0;
      while (out.length < PERM_TARGET && pairs.length && guard++ < 200) {
        var p = pairs[guard % pairs.length];
        var oa = others(p[0]), ob = others(p[1]);
        if (!oa.length || !ob.length) continue;
        var chp = {}; chp[p[0]] = oa[Math.floor(rng() * oa.length)]; chp[p[1]] = ob[Math.floor(rng() * ob.length)];
        add(chp, "pairs");
      }
      return out;
    }

    var A = filter;
    if (AXES.indexOf(A) === -1) return out;
    others(A).forEach(function (v) { var c = {}; c[A] = v; add(c, A); });
    var B = PARTNER[A];
    if (!B || AXES.indexOf(B) === -1 || B === A) B = AXES.filter(function (x) { return x !== A && !state.locks[x]; })[0];
    if (B) {
      var bVals = shuffled(others(B));
      var aVals = OPTIONS[A].slice();
      var guard2 = 0, idx = 0;
      while (out.length < PERM_TARGET && guard2++ < 400 && bVals.length) {
        var av = aVals[idx % aVals.length], bv = bVals[Math.floor(idx / aVals.length) % bVals.length];
        idx++;
        var cc = {}; cc[A] = av; cc[B] = bv;
        add(cc, A + "+" + B);
        if (idx > aVals.length * bVals.length) break;
      }
    }
    return out;
  }
  function groupTitle(g) {
    if (g === "pairs") return "Two axes at once";
    var parts = g.split("+");
    if (parts.length === 2) return axisLabel(parts[0]) + " + " + axisLabel(parts[1]).toLowerCase();
    return axisLabel(g);
  }
  function variantName(v) {
    return Object.keys(v.changes).map(function (a) { return valueLabel(a, v.changes[a]); }).join(" + ");
  }
  function variantNote(v) {
    return Object.keys(v.changes).map(function (a) { return axisLabel(a) + ": " + valueLabel(a, state.spec[a]) + " → " + valueLabel(a, v.changes[a]); }).join("; ");
  }

  function renderPermFilters() {
    var box = $("perm-filters"); if (!box) return;
    var items = [{ k: "mix", label: "Mixed" }].concat(AXES.map(function (a) { return { k: a, label: axisLabel(a) }; }));
    box.innerHTML = items.map(function (it) {
      var locked = it.k !== "mix" && state.locks[it.k];
      return '<button type="button" class="fchip" data-filter="' + esc(it.k) + '" aria-pressed="' + (state.permFilter === it.k ? "true" : "false") + '">' +
        esc(it.label) + (locked ? '<span class="lk"> locked</span>' : "") + "</button>";
    }).join("");
  }

  var permGen = 0;
  function schedulePerms() {
    clearTimeout(permTimer);
    permTimer = setTimeout(renderPerms, 260);
  }
  function renderPerms() {
    var wrap = $("perm-groups"); if (!wrap) return;
    permGen++;
    var variants = buildVariants(state.spec, state.permFilter, state.permSeed);
    var items = [], groups = {}, order = [];
    var badCount = 0;
    variants.forEach(function (v) {
      var c = check(v.spec);
      if (!c.ok) badCount++;
      if (!c.ok && state.hideBad) return;
      if (!groups[v.group]) { groups[v.group] = []; order.push(v.group); }
      var item = { name: variantName(v), note: variantNote(v), spec: v.spec };
      groups[v.group].push(items.length);
      items.push(item);
    });
    cardItems.v = items;
    var html = "";
    order.forEach(function (g) {
      html += '<section class="perm-group" aria-label="' + esc(groupTitle(g)) + '"><h3>' + esc(groupTitle(g)) + ' <span class="mono">' + groups[g].length + "</span></h3>" +
        '<div class="grid cards">' + groups[g].map(function (i) { return cardHTML("v", i, items[i], "pv" + permGen + "-"); }).join("") + "</div></section>";
    });
    if (!items.length) {
      html = '<p class="compare-empty">' + (variants.length ? "Every variant here breaks a rule and rule-breakers are hidden." : "Nothing to vary: every axis is locked or has a single option. Unlock an axis or pick another filter.") + "</p>";
    }
    wrap.innerHTML = html;
    bindThumbData(wrap);
    markCurrentCards();

    var sum = $("perm-summary");
    if (sum) {
      var lockedN = Object.keys(state.locks).length;
      var t = variants.length + " variants around " + ((layoutOf(state.spec.layout) || {}).name || "the current spec") +
        (state.permFilter === "mix" ? ", one or two axes at a time" + (lockedN ? ", skipping " + lockedN + " locked axis" + (lockedN > 1 ? "es" : "") : "") : ", exploring " + axisLabel(state.permFilter).toLowerCase()) + ". ";
      if (badCount) t += state.hideBad ? badCount + " rule-breaking variant" + (badCount > 1 ? "s" : "") + " hidden." : badCount + " break a Hackpad rule and are dimmed with the reason shown.";
      else t += "All pass the Hackpad rules.";
      sum.textContent = t;
    }
  }

  // compare
  function isPinned(spec) {
    var k = designKey(spec);
    return state.compare.some(function (c) { return designKey(c.spec) === k; });
  }
  function togglePin(item) {
    var k = designKey(item.spec);
    var idx = -1;
    state.compare.forEach(function (c, i) { if (designKey(c.spec) === k) idx = i; });
    if (idx !== -1) { state.compare.splice(idx, 1); announce("Removed " + item.name + " from compare"); }
    else {
      if (state.compare.length >= MAX_COMPARE) { announce("Compare tray is full. Remove a design first."); flashDock(); return; }
      state.compare.push({ name: item.name, spec: clone(item.spec) });
      announce("Pinned " + item.name + " to compare (" + state.compare.length + " of " + MAX_COMPARE + ")");
    }
    renderCompare(); syncPinButtons(); persist();
  }
  function flashDock() {
    var d = $("compare-dock"); if (!d) return;
    d.textContent = "Tray full (4/4)";
    setTimeout(updateDock, 1600);
  }
  function updateDock() {
    var d = $("compare-dock"); if (!d) return;
    d.hidden = state.compare.length === 0;
    d.innerHTML = 'Compare <span class="mono">' + state.compare.length + "</span>/" + MAX_COMPARE;
  }
  function syncPinButtons() {
    var keys = {};
    state.compare.forEach(function (c) { keys[designKey(c.spec)] = true; });
    var btns = document.querySelectorAll("[data-pin-key]");
    for (var i = 0; i < btns.length; i++) btns[i].setAttribute("aria-pressed", keys[btns[i].getAttribute("data-pin-key")] ? "true" : "false");
    var cur = $("btn-pin-current");
    if (cur) {
      var on = !!keys[designKey(state.spec)];
      cur.setAttribute("aria-pressed", on ? "true" : "false");
      cur.textContent = on ? "Pinned" : "Pin to compare";
    }
    updateDock();
  }
  function renderCompare() {
    var tray = $("compare-tray"); if (!tray) return;
    if (!state.compare.length) {
      tray.innerHTML = '<div class="compare-empty">Nothing pinned yet. Use <b>Compare</b> on any card, or <b>Pin to compare</b> in the configurator.</div>';
      return;
    }
    var cols = state.compare.map(function (c) { return { c: c, chk: check(c.spec), L: layoutOf(c.spec.layout) }; });
    var rows = [
      ["Layout", function (x) { return (x.L && x.L.name) || x.c.spec.layout; }],
      ["Matrix", function (x) { return (x.L && x.L.matrix) || "–"; }],
      ["Shell", function (x) { return valueLabel("shell", x.c.spec.shell) + ", " + valueLabel("texture", x.c.spec.texture).toLowerCase(); }],
      ["Plate", function (x) { return valueLabel("plate", x.c.spec.plate); }],
      ["Glow", function (x) { return valueLabel("glowColor", x.c.spec.glowColor) + " / " + valueLabel("glowPlace", x.c.spec.glowPlace).toLowerCase(); }],
      ["Knob", function (x) { return valueLabel("knob", x.c.spec.knob); }],
      ["Caps", function (x) { return x.c.spec.capProfile + ", " + valueLabel("agentCap", x.c.spec.agentCap).toLowerCase() + " + " + valueLabel("commandCap", x.c.spec.commandCap).toLowerCase(); }],
      ["Geometry", function (x) { return "r" + x.c.spec.corner + " · " + x.c.spec.bezel + " mm · " + x.c.spec.tilt + "°"; }],
      ["GPIO", function (x) { return fmt(x.chk.stats.pins) + " / " + fmt(x.chk.stats.pinsMax || 11); }],
      ["LEDs", function (x) { return fmt(x.chk.stats.leds) + " / " + fmt(x.chk.stats.ledsKit || 16); }],
      ["PCB", function (x) { var p = x.chk.stats.pcb || {}; return fmt(p.w) + " × " + fmt(p.h) + " mm"; }],
      ["Case", function (x) { var s = x.chk.stats.shell || {}; return fmt(s.w) + " × " + fmt(s.h) + " × " + fmt(s.height) + " mm"; }],
      ["Extras", function (x) { return x.chk.extras.length ? x.chk.extras.map(function (e) { return e.item; }).join(", ") : "none"; }],
      ["Rules", function (x) { return !x.chk.ok ? "breaks " + x.chk.errors.length : x.chk.warnings.length ? x.chk.warnings.length + " warning" + (x.chk.warnings.length > 1 ? "s" : "") : "pass"; }, function (x) { return !x.chk.ok ? "td-err" : x.chk.warnings.length ? "td-warn" : "td-ok"; }]
    ];
    var gen = ++permGen;
    var html = '<div class="compare-scroll"><table class="cmp" style="min-width:' + (100 + cols.length * 150) + 'px"><thead><tr><th scope="col"><span class="sr-only">Property</span></th>';
    cols.forEach(function (x, i) {
      html += '<th scope="col"><div class="cmp-head"><div class="cmp-thumb">' + renderSVG("renderTop", x.c.spec, { t: 0, idPrefix: "cmp" + gen + "-" + i + "-", dims: false }) + "</div>" +
        '<span class="cmp-name">' + esc(x.c.name) + "</span>" +
        '<div class="cmp-actions"><button type="button" class="btn btn-small" data-cmp-load="' + i + '" aria-label="Load ' + esc(x.c.name) + ' into the configurator">Load</button>' +
        '<button type="button" class="btn btn-small btn-quiet" data-cmp-remove="' + i + '" aria-label="Remove ' + esc(x.c.name) + ' from compare">Remove</button></div></div></th>';
    });
    html += "</tr></thead><tbody>";
    rows.forEach(function (r) {
      var vals = cols.map(function (x) { try { return String(r[1](x)); } catch (e) { return "–"; } });
      var diff = cols.length > 1 && vals.some(function (v) { return v !== vals[0]; });
      html += "<tr" + (diff ? ' class="diff"' : "") + '><th scope="row">' + esc(r[0]) + "</th>";
      vals.forEach(function (v, i) { html += "<td" + (r[2] ? ' class="' + r[2](cols[i]) + '"' : "") + ">" + esc(v) + "</td>"; });
      html += "</tr>";
    });
    html += "</tbody></table></div>" +
      '<div class="compare-foot"><button type="button" class="btn btn-small btn-quiet" id="cmp-clear">Clear tray</button></div>';
    tray.innerHTML = html;
  }

  // shuffle
  function shuffle() {
    var locked = {};
    AXES.forEach(function (k) { if (state.locks[k]) locked[k] = state.spec[k]; });
    var s = null;
    try { if (typeof cat.randomSpec === "function") s = cat.randomSpec(locked, Math.random, clone(state.spec)); } catch (e) { s = null; }
    if (!s || typeof s !== "object") {
      s = clone(state.spec);
      AXES.forEach(function (k) { if (!state.locks[k]) s[k] = OPTIONS[k][Math.floor(Math.random() * OPTIONS[k].length)]; });
    }
    s = normalizeSpec(s);
    Object.keys(locked).forEach(function (k) { s[k] = locked[k]; });
    s.statuses = state.spec.statuses.slice();
    s.wordmarkText = state.spec.wordmarkText;
    setSpec(s, "Shuffled. " + (layoutOf(s.layout) || {}).name + ", " + valueLabel("shell", s.shell) + " shell");
  }

  // wire up
  function wire() {
    var tt = $("theme-toggle");
    if (tt) tt.addEventListener("click", function () {
      state.theme = { auto: "light", light: "dark", dark: "auto" }[state.theme];
      applyTheme(); persist();
    });

    var tabs = document.querySelectorAll('[role="tab"][data-view]');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener("click", function () { setView(this.getAttribute("data-view")); });
      tabs[i].addEventListener("keydown", function (e) {
        var views = ["top", "side", "exploded"], at = views.indexOf(state.view), nx = null;
        if (e.key === "ArrowRight") nx = views[(at + 1) % 3];
        else if (e.key === "ArrowLeft") nx = views[(at + 2) % 3];
        else if (e.key === "Home") nx = views[0];
        else if (e.key === "End") nx = views[2];
        if (nx) { e.preventDefault(); setView(nx, true); }
      });
    }

    var dims = $("toggle-dims");
    if (dims) dims.addEventListener("click", function () {
      state.dims = !state.dims;
      dims.setAttribute("aria-pressed", state.dims ? "true" : "false");
      renderView(); persist();
    });
    var sim = $("toggle-sim");
    if (sim) sim.addEventListener("click", function () { setSimulate(!state.simulate); announce(state.simulate ? "Simulating runs" : "Simulation paused"); });

    var sh = $("btn-shuffle"); if (sh) sh.addEventListener("click", shuffle);
    var rs = $("btn-reset"); if (rs) rs.addEventListener("click", function () { setSpec(clone(DEFAULT), "Reset to the base Frostbite design"); });
    var un = $("btn-unlock"); if (un) un.addEventListener("click", function () {
      state.locks = {}; syncLocks(); persist(); announce("All axes unlocked");
      if (state.permFilter === "mix") schedulePerms();
    });
    var pc = $("btn-pin-current"); if (pc) pc.addEventListener("click", function () {
      var L = layoutOf(state.spec.layout);
      togglePin({ name: ((L && L.name) || "Design") + ", " + valueLabel("shell", state.spec.shell).toLowerCase(), spec: state.spec });
    });
    var cp = $("btn-copy"); if (cp) cp.addEventListener("click", copySpec);

    ["preset-grid", "perm-groups"].forEach(function (id) { var el = $(id); if (el) el.addEventListener("click", onCardClick); });

    var pf = $("perm-filters");
    if (pf) pf.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("[data-filter]");
      if (!b) return;
      state.permFilter = b.getAttribute("data-filter");
      renderPermFilters(); renderPerms();
    });
    var hb = $("perm-hide-bad");
    if (hb) {
      hb.setAttribute("aria-pressed", state.hideBad ? "true" : "false");
      hb.addEventListener("click", function () {
        state.hideBad = !state.hideBad;
        hb.setAttribute("aria-pressed", state.hideBad ? "true" : "false");
        renderPerms(); persist();
      });
    }
    var rr = $("perm-reroll"); if (rr) rr.addEventListener("click", function () { state.permSeed += 1; renderPerms(); });

    var tray = $("compare-tray");
    if (tray) tray.addEventListener("click", function (e) {
      var t = e.target.closest && e.target.closest("button");
      if (!t) return;
      if (t.id === "cmp-clear") { state.compare = []; renderCompare(); syncPinButtons(); persist(); announce("Compare tray cleared"); return; }
      if (t.hasAttribute("data-cmp-remove")) {
        var r = state.compare.splice(+t.getAttribute("data-cmp-remove"), 1)[0];
        renderCompare(); syncPinButtons(); persist(); if (r) announce("Removed " + r.name);
        return;
      }
      if (t.hasAttribute("data-cmp-load")) {
        var c = state.compare[+t.getAttribute("data-cmp-load")];
        if (c) {
          setSpec(clone(c.spec), "Loaded " + c.name);
          var cf = $("configurator"); if (cf && cf.scrollIntoView) cf.scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "start" });
        }
      }
    });

    document.addEventListener("visibilitychange", function () { if (!document.hidden && state.simulate) renderView(); });
  }

  function init() {
    applyTheme();
    buildControls();
    renderLegend();
    wire();
    var dims = $("toggle-dims"); if (dims) dims.setAttribute("aria-pressed", state.dims ? "true" : "false");
    setView(state.view);
    syncControls();
    renderStage();
    renderChecks();
    setSimulate(state.simulate);
    renderCompare();
    renderPresets();
    renderPermFilters();
    syncPinButtons();
    // Defer the permutation wall so first paint is the configurator.
    setTimeout(renderPerms, 60);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
