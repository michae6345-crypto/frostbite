#!/usr/bin/env python3
"""Frostbite generative concept drawings, to scale, from design.json. No AI image generation.

Run from anywhere:
  ~/.local/bin/uv run --python 3.12 --with shapely --with numpy --with scipy \
      --with pillow --with scikit-image docs/concepts/generative/generate.py
  add --check to run only the FE benchmark, --force to rerun the topology optimisation.

Writes next to this file:
  concept-1-lantern-ribcage.png   graded wall ribs, FE-checked, plan section and elevations
  simp-vs-pattern-side-wall.png   what a real 2D SIMP run gives, next to the pattern used
  concept-2-bone-floor.png        Voronoi floor, bottom view (pattern only, not optimised)
  concept-3-root-floor.png        branching floor with PCB rest columns, bottom view (pattern only)
  patterns/*.json                 the polygons, in PCB or wall coordinates (mm), ready for CadQuery
  patterns/wall_*.npz             cached SIMP density fields
  results.json                    every number quoted in README.md

Coordinates are PCB coordinates: x right, y toward the user, origin at the PCB back-left corner.
z = 0 is the PCB underside, the same frame as CAD/frostbite_case.py.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import scipy.ndimage as ndi
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import shapely
import shapely.ops
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from shapely.geometry import LineString, MultiPoint, Point, Polygon, box
from shapely.ops import unary_union
from skimage import measure

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PAT = HERE / "patterns"
D = json.loads((ROOT / "design.json").read_text())

# ------------------------------------------------------------------ the real object
PCB_W, PCB_H = D["pcb"]["w"], D["pcb"]["h"]
SH = D["case"]["shell"]
SHELL_W, SHELL_H, CORNER = SH["w"], SH["h"], SH["corner"]
TOL = D["case"]["tolerance"]
CX, CY = PCB_W / 2, PCB_H / 2
XL, XR = CX - SHELL_W / 2, CX + SHELL_W / 2     # shell skin
YB, YF = CY - SHELL_H / 2, CY + SHELL_H / 2     # back and front skin
SCREWS = [(p["x"], p["y"]) for p in D["case"]["screws"]["positions"]]
BOSS_OD = D["case"]["screws"]["boss_od"]
TILT = math.radians(SH["tilt_deg"])
PLATE_TOP, SKIRT_BOT, BAND_BOT = 6.6, -9.4, -11.4
Y_FRONT_SCREW = max(y for _, y in SCREWS)


def z_under(y):
    """Bottom underside, from CAD/frostbite_case.py and the audit (-16.5 at the front screws)."""
    return -16.5 - (Y_FRONT_SCREW - y) * math.tan(TILT)


# Rules applied to every pattern
MIN_STRUT = 1.2          # 3 extrusion lines at a 0.4 mm nozzle, floors
MIN_RIB = 1.6            # exposed wall ribs, 4 lines, they meet fingers and desk knocks
RIB_DEPTH = 3.0          # wall ribs are this deep, an open channel sits behind them
MIN_WINDOW = 1.8         # narrower holes close up or stay full of stringing
MAX_FLOOR_HOLE = 7.5     # largest inscribed circle in a floor hole, keeps fingers and coins out
BRIDGE_MAX = 3.0         # flat roof allowed in print orientation, wider roofs get 45 deg gussets
E_PETG, NU = 2000.0, 0.38   # MPa, a typical PETG datasheet value, not measured on this filament
DENSITY = 1.27           # g/cm3 PETG

SHELL = box(XL + CORNER, YB + CORNER, XR - CORNER, YF - CORNER).buffer(CORNER, quad_segs=24)
POCKET = box(-TOL, -TOL, PCB_W + TOL, PCB_H + TOL)
MCU = D["mcu"]["rect"]
KEYS = [(k["x"], k["y"], k["role"]) for k in D["keys"]]
EN = D["encoder"]
OLED = D["oled"]["window"]
GLOW = [(g["x"], g["y"]) for g in D["leds"]["glow"]]
PADS = json.loads((ROOT / "PCB/build/bottom_pads.json").read_text())["pads"]
UC = D["case"]["usb_cutout"]
USB_CX = MCU["x"] + MCU["w"] / 2
USB_CZ = -2.83


# ------------------------------------------------------------------ 2D plane-stress FE and SIMP
def element_ke(nu):
    a11 = np.array([[12, 3, -6, -3], [3, 12, 3, 0], [-6, 3, 12, -3], [-3, 0, -3, 12]], float)
    a12 = np.array([[-6, -3, 0, 3], [-3, -6, -3, -6], [0, -3, -6, 3], [3, -6, 3, -6]], float)
    b11 = np.array([[-4, 3, -2, 9], [3, -4, -9, 4], [-2, -9, -4, -3], [9, 4, -3, -4]], float)
    b12 = np.array([[2, -3, 4, -9], [-3, 2, 9, -2], [4, 9, 2, 3], [-9, -2, 3, 2]], float)
    return (np.block([[a11, a12], [a12.T, a11]]) + nu * np.block([[b11, b12], [b12.T, b11]])) / (24 * (1 - nu ** 2))


class Grid:
    """Rows run downward from the top edge, columns run along the wall."""

    def __init__(self, nely, nelx):
        self.nely, self.nelx = nely, nelx
        self.ndof = 2 * (nelx + 1) * (nely + 1)
        n = np.arange((nelx + 1) * (nely + 1)).reshape(nelx + 1, nely + 1).T[:-1, :-1].ravel("F")
        b = 2 * n + 2
        s = 2 * nely
        self.edof = np.stack([b, b + 1, b + s + 2, b + s + 3, b + s, b + s + 1, b - 2, b - 1], 1)
        self.ke = element_ke(NU)
        self.ik = np.kron(self.edof, np.ones((8, 1), int)).ravel()
        self.jk = np.kron(self.edof, np.ones((1, 8), int)).ravel()

    def node(self, i, j):
        return j * (self.nely + 1) + i

    def solve(self, e_field, loads, fixed):
        """e_field: element stiffness E*t (N/mm). loads: list of (dofs, values). Returns U per load."""
        vals = np.outer(e_field.ravel("F"), self.ke.ravel()).ravel()
        k = sp.coo_matrix((vals, (self.ik, self.jk)), shape=(self.ndof, self.ndof)).tocsc()
        free = np.setdiff1d(np.arange(self.ndof), fixed)
        lu = spla.splu(k[free][:, free], permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.0,
                       options={"SymmetricMode": True})
        out = []
        for dofs, values in loads:
            f = np.zeros(self.ndof)
            np.add.at(f, dofs, values)
            u = np.zeros(self.ndof)
            u[free] = lu.solve(f[free])
            out.append(u)
        return out

    def energy(self, u):
        ue = u[self.edof]
        return ((ue @ self.ke) * ue).sum(1).reshape(self.nely, self.nelx, order="F")

    def von_mises(self, u, solid, e=E_PETG):
        """Stress at element centres (MPa), h independent for square elements."""
        c = e / (1 - NU ** 2)
        ue = u[self.edof]
        # node order: bottom-left, bottom-right, top-right, top-left; strain = B u / h, h taken as 1
        bx = np.array([-.5, .5, .5, -.5])
        by = np.array([-.5, -.5, .5, .5])
        ux, uy = ue[:, 0::2], ue[:, 1::2]
        exx, eyy = ux @ bx, uy @ by
        gxy = ux @ by + uy @ bx
        sx, sy = c * (exx + NU * eyy), c * (eyy + NU * exx)
        txy = e / (2 * (1 + NU)) * gxy
        vm = np.sqrt(sx ** 2 + sy ** 2 - sx * sy + 3 * txy ** 2)
        return vm.reshape(self.nely, self.nelx, order="F") * solid


def fe_benchmark():
    """Cantilever 40 x 8 x 5 mm, 10 N tip load, against Timoshenko beam theory."""
    h, L, H, t, F = 0.25, 40.0, 8.0, 5.0, 10.0
    nelx, nely = int(L / h), int(H / h)
    g = Grid(nely, nelx)
    fixed = np.arange(2 * (nely + 1))
    tip = g.node(np.arange(nely + 1), nelx)
    w = np.full(nely + 1, 1 / nely)
    w[[0, -1]] /= 2
    u = g.solve(np.full((nely, nelx), E_PETG * t), [(2 * tip + 1, -F * w)], fixed)[0]
    fe = -float((u[2 * tip + 1] * w).sum())
    i = t * H ** 3 / 12
    gm = E_PETG / (2 * (1 + NU))
    beam = F * L ** 3 / (3 * E_PETG * i) + 6 / 5 * F * L / (gm * t * H)
    return {"fe_mm": fe, "timoshenko_mm": beam, "error_pct": 100 * (fe - beam) / beam}


def cone_filter(r_el):
    k = int(math.ceil(r_el))
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    w = np.clip(r_el - np.hypot(xx, yy), 0, None)
    return w / w.sum()


def simp(grid, solid, void, t, loads, fixed, volfrac, r_el, x0, iters=130):
    """Multi-load compliance minimisation: density filter, Heaviside projection, OC update.
    solid and void are passive masks, everything else is design."""
    design = ~(solid | void)
    x = np.where(solid, 1.0, 0.0)
    x[design] = x0[design]
    w = cone_filter(r_el)
    norm = ndi.convolve(np.ones_like(x), w, mode="constant")
    filt = lambda a: ndi.convolve(a, w, mode="constant") / norm
    filt_t = lambda a: ndi.convolve(a / norm, w, mode="constant")
    eta, beta = 0.5, 2.0
    emin = 1e-6

    def project(a, b):
        d = math.tanh(b * eta) + math.tanh(b * (1 - eta))
        return (math.tanh(b * eta) + np.tanh(b * (a - eta))) / d, \
            b * (1 - np.tanh(b * (a - eta)) ** 2) / d

    hist = []
    for it in range(iters):
        if it and it % 26 == 0:
            beta = min(beta * 2, 16)
        xt = filt(x)
        xp, dxp = project(xt, beta)
        xp[solid], xp[void] = 1, 0
        e = (emin + xp ** 3 * (1 - emin)) * E_PETG * t
        us = grid.solve(e, loads, fixed)
        ce = sum(grid.energy(u) for u in us)
        c = float((e * ce).sum())
        hist.append(c)
        dc = -3 * xp ** 2 * (1 - emin) * E_PETG * t * ce
        dc = filt_t(dc * dxp)
        dv = filt_t(design * dxp)
        dc[~design] = 0
        lo, hi = 1e-12, 1e12
        while (hi - lo) / (hi + lo) > 1e-5:
            lm = math.sqrt(lo * hi)
            xn = x.copy()
            ratio = np.sqrt(np.maximum(-dc, 0) / np.maximum(dv * lm, 1e-30))
            xn[design] = np.clip((x * ratio)[design], np.maximum(x - 0.15, 0)[design], np.minimum(x + 0.15, 1)[design])
            if project(filt(xn), beta)[0][design].mean() > volfrac:
                lo = lm
            else:
                hi = lm
        x = xn
    xp = project(filt(x), beta)[0]
    xp[solid], xp[void] = 1, 0
    return xp, hist


# ------------------------------------------------------------------ walls
def disk(r_px):
    k = int(math.ceil(r_px))
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    return xx ** 2 + yy ** 2 <= r_px ** 2


def fast_open(mask, r_px):
    """Opening by a disk, using distance transforms so it stays fast on big masks."""
    er = ndi.distance_transform_edt(mask) > r_px
    return ndi.distance_transform_edt(~er) <= r_px


def gusset_for_print(void, print_up_is_down_the_image, bridge_px):
    """Fill void so every roof in print orientation closes at 45 deg, or spans <= bridge_px flat."""
    v = void if print_up_is_down_the_image else void[::-1]
    v = v.copy()
    for i in range(v.shape[0] - 2, -1, -1):
        row, above = v[i], v[i + 1]
        if not row.any():
            continue
        allowed = ndi.binary_dilation(above, structure=np.ones(3, bool))
        lab, n = ndi.label(row)
        new = np.zeros_like(row)
        for k in range(1, n + 1):
            idx = np.flatnonzero(lab == k)
            keep = idx[allowed[idx]]
            if keep.size:
                new[keep] = True
            else:                       # flat roof: keep a central bridge, the sides become gussets
                m = idx.size
                c = idx[0] + m // 2
                half = min(m, bridge_px) // 2
                new[c - half:c + half] = True
        v[i] = new
    return v if print_up_is_down_the_image else v[::-1]


class Wall:
    def __init__(self, name, s0, s1, z_low, thick, run, boss_spans, void_rects, load_points, feet):
        self.name, self.s0, self.s1, self.thick = name, s0, s1, thick
        self.h = 0.3
        self.ztop = PLATE_TOP
        self.zbot = min(z_low(s0), z_low(s1))
        self.nelx = int(round((s1 - s0) / self.h))
        self.nely = int(round((self.ztop - self.zbot) / self.h))
        self.z_low, self.run, self.boss_spans = z_low, run, boss_spans
        self.void_rects, self.load_points, self.feet = void_rects, load_points, feet
        self.grid = Grid(self.nely, self.nelx)
        ss = s0 + (np.arange(self.nelx) + .5) * self.h
        zz = self.ztop - (np.arange(self.nely) + .5) * self.h
        self.ss, self.zz = np.meshgrid(ss, zz)
        self.outside = self.zz < np.vectorize(z_low)(self.ss)
        for a, b, c, d in void_rects:
            self.outside |= (self.ss > a) & (self.ss < b) & (self.zz > c) & (self.zz < d)
        web = (self.zz > WEB_Z0) & (self.zz < WEB_Z1) & (self.ss > run[0]) & (self.ss < run[1])
        for a, b in boss_spans:
            web &= ~((self.ss > a) & (self.ss < b))
        for a, b, c, d in void_rects:   # keep a solid margin around cut-outs
            web &= ~((self.ss > a - 1.6) & (self.ss < b + 1.6))
        self.web = web & ~self.outside
        self.solid = ~self.web & ~self.outside
        self.tmap = np.full(self.ss.shape, float(thick))        # channel behind the ribs thins the skirt
        layer = (self.zz >= SKIRT_BOT) & (self.zz < WEB_Z1)
        for a, b in boss_spans:
            layer &= ~((self.ss > a) & (self.ss < b))
        self.tmap[layer] = RIB_DEPTH
        self._bc()

    def _bc(self):
        g = self.grid
        fixed, self.feet_nodes = [], []
        for n, s in enumerate(self.feet):
            js = [j for j in range(g.nelx + 1) if abs(self.s0 + j * self.h - s) <= 4]
            nodes = []
            for j in js:
                col = ~self.outside[:, min(j, g.nelx - 1)]
                i = np.flatnonzero(col)[-1] + 1
                nodes.append(g.node(i, j))
            fixed += [2 * m + 1 for m in nodes]
            if n == 0:
                fixed += [2 * m for m in nodes]
            self.feet_nodes.append(nodes)
        self.fixed = np.array(sorted(set(fixed)))
        self.loads = []
        for s, f in self.load_points:
            js = [j for j in range(g.nelx + 1) if abs(self.s0 + j * self.h - s) <= 3]
            nodes = np.array([g.node(0, j) for j in js])
            self.loads.append((2 * nodes + 1, np.full(len(nodes), -f / len(nodes))))

    def evaluate(self, solid_mask):
        e = np.where(solid_mask, E_PETG, 1e-6 * E_PETG) * self.tmap
        us = self.grid.solve(e, self.loads, self.fixed)
        defl = [float(-np.mean(u[dofs])) for u, (dofs, _) in zip(us, self.loads)]
        comp = float(sum((u[d] * v).sum() for u, (d, v) in zip(us, self.loads)))
        vm = np.max([self.grid.von_mises(u, solid_mask) for u in us], axis=0) / self.h
        return {"compliance_mm_per_N_sum": comp, "max_deflection_mm": max(defl),
                "vm_99_9pct_MPa": float(np.percentile(vm[solid_mask], 99.9)), "vm_max_MPa": float(vm.max())}

    def run_simp(self, force):
        f = PAT / f"wall_{self.name}.npz"
        if f.exists() and not force:
            c = np.load(f)
            return c["xp"], c["hist"]
        t0 = time.time()
        # hex-seeded start: compliance alone merges everything into a few thick members, the seed
        # keeps a finer truss. The result is a local optimum, so it is judged by re-running the FE.
        k = 2 * math.pi / SEED_PITCH
        hexf = sum(np.cos(k * (self.ss * math.cos(a) + self.zz * math.sin(a))) for a in (0, math.pi / 3, 2 * math.pi / 3)) / 3
        x0 = np.clip(SOLID_FRAC + 0.45 * hexf, 0.02, 1)
        xp, hist = simp(self.grid, self.solid, self.outside, self.tmap, self.loads, self.fixed,
                        volfrac=SOLID_FRAC, r_el=1.0 / self.h, x0=x0)
        print(f"  SIMP {self.name}: {self.nelx}x{self.nely}, {time.time() - t0:.0f} s")
        np.savez_compressed(f, xp=xp.astype(np.float32), hist=np.array(hist))
        return xp, np.array(hist)

    def finish(self, xp):
        """Threshold, enforce strut and window limits on a 0.1 mm raster, add print gussets."""
        z = int(round(self.h / 0.1))
        px = 0.1
        up = lambda a: np.kron(a.astype(float), np.ones((z, z)))
        field = ndi.gaussian_filter(up(xp), 2.0)
        web = up(self.web) > .5
        out = up(self.outside) > .5
        v = web & (field < 0.5)
        v = fast_open(v, MIN_WINDOW / 2 / px) & web
        for _ in range(3):                                      # thicken ribs that came out thin
            w = ~v & ~out
            thin = w & ~fast_open(w, MIN_RIB / 2 / px) & web
            if not thin.any():
                break
            v &= ~ndi.binary_dilation(thin, disk(4))
        v = gusset_for_print(v, True, int(BRIDGE_MAX / px)) & web
        lab, n = ndi.label(v)
        area = ndi.sum(v, lab, np.arange(1, n + 1)) * px ** 2
        for i, a in enumerate(area, 1):
            if a < 4.0:
                v[lab == i] = False
        self.void_hi, self.out_hi, self.web_hi, self.px = v, out, web, px
        return v, self.coarsen(v)

    def coarsen(self, v):
        z = int(round(self.h / 0.1))
        return v[:z * self.nely, :z * self.nelx].reshape(self.nely, z, self.nelx, z).mean((1, 3)) > .5

    def web_spans(self):
        cuts = sorted(list(self.boss_spans) + [(a - 1.6, b + 1.6) for a, b, _, _ in self.void_rects])
        spans, s = [], self.run[0]
        for a, b in cuts:
            if a > s:
                spans.append((s, a))
            s = max(s, b)
        spans.append((s, self.run[1]))
        return [q for q in spans if q[1] - q[0] > 3]

    def bone_web(self, seed):
        """Graded Voronoi window pattern. Cells shrink and ribs thicken where the solid wall stores
        the most strain energy. This is a pattern informed by one FE field, not an optimisation."""
        us = self.grid.solve(self.tmap * E_PETG * (~self.outside + 1e-6), self.loads, self.fixed)
        e = sum(self.grid.energy(u) for u in us)
        e = ndi.gaussian_filter(e * self.tmap * self.web, 8) / max(ndi.gaussian_filter(self.web * 1.0, 8).max(), 1e-9)
        e = np.sqrt(np.clip(e / np.percentile(e[self.web], 95), 0, 1))
        def level(s, z):
            j = int(np.clip((s - self.s0) / self.h, 0, self.nelx - 1))
            i = int(np.clip((self.ztop - z) / self.h, 0, self.nely - 1))
            return float(e[i, j])
        rng = np.random.default_rng(seed)
        region = unary_union([box(a, WEB_Z0, b, WEB_Z1) for a, b in self.web_spans()])
        pts = []
        minx, miny, maxx, maxy = region.bounds
        for _ in range(40000):
            s, z = rng.uniform(minx, maxx), rng.uniform(miny, maxy)
            if not region.contains(Point(s, z)):
                continue
            r = 5.5 - 1.5 * level(s, z)
            if all(math.dist((s, z), q) > r for q in pts):
                pts.append((s, z))
        grown = region.buffer(0.8, join_style=2)
        for _ in range(3):                                      # relax a little so ribs read as even bone
            cells = shapely.voronoi_polygons(MultiPoint(pts), extend_to=grown.buffer(10))
            new = []
            for c in cells.geoms:
                cc = c.intersection(region)
                if not cc.is_empty:
                    m = cc.centroid
                    new.append((m.x, m.y))
            pts = new
        cells = shapely.voronoi_polygons(MultiPoint(pts), extend_to=grown.buffer(10))
        holes = []
        for c in cells.geoms:
            cc = c.intersection(grown)
            if cc.is_empty:
                continue
            m = cc.centroid
            rib = MIN_RIB + 0.3 * level(m.x, m.y)
            h = cc.buffer(-rib / 2, join_style=2).buffer(-MIN_WINDOW / 2).buffer(MIN_WINDOW / 2, quad_segs=6)
            holes += [g for g in polys(h) if g.area > 2.5]
        px = 0.1
        hh, ww = self.nely * 3, self.nelx * 3
        im = Image.new("L", (ww, hh), 0)
        dr = ImageDraw.Draw(im)
        for g in holes:
            dr.polygon([((a - self.s0) / px, (self.ztop - b) / px) for a, b in g.exterior.coords], fill=255)
        v = np.asarray(im) > 127
        web = self.web_hi
        v = gusset_for_print(v & web, True, int(BRIDGE_MAX / px)) & web
        return v

    def polygons(self, v):
        """Window outlines as (s, z) rings in mm."""
        out = []
        pad = np.pad(v.astype(float), 1)
        for c in measure.find_contours(ndi.gaussian_filter(pad, 0.7), 0.5):
            s = self.s0 + (c[:, 1] - 1 + .5) * self.px
            zv = self.ztop - (c[:, 0] - 1 + .5) * self.px
            p = Polygon(np.c_[s, zv]).buffer(0).simplify(0.04)
            if p.geom_type == "Polygon" and p.area > 1:
                out.append([[round(a, 3), round(b, 3)] for a, b in p.exterior.coords])
        return out

    def stats(self, v):
        px = self.px
        w = ~v & ~self.out_hi
        opened = fast_open(w, MIN_RIB / 2 / px)
        lost = w & ~opened & self.web_hi
        # corners of ribs always lose a little to an opening, so only depth matters here
        depth = ndi.distance_transform_edt(~opened)[lost].max() * px if lost.any() else 0.0
        dt = ndi.distance_transform_edt(v) * px
        # Top prints face down, so print-up is down this image: a roof is void with solid one row on
        roof = v[:-1] & ~v[1:]
        runs = [int((ndi.label(r)[0] == k).sum()) for r in roof if r.any() for k in range(1, ndi.label(r)[1] + 1)]
        return {"max_flat_roof_mm": max(runs, default=0) * px, "windows": int(ndi.label(v)[1]), "window_area_mm2": float(v.sum() * px ** 2),
                "removed_cm3": float(v.sum() * px ** 2 * RIB_DEPTH / 1000),
                "web_open_fraction": float(v.sum() / self.web_hi.sum()),
                "strut_ok_max_sliver_mm": float(depth), "largest_window_inscribed_d_mm": float(2 * dt.max())}

    def diamond_benchmark(self, area_target):
        """Plain 45 deg zigzag of ribs with the same web area, as a same-mass comparison."""
        pitch = 2 * (WEB_Z1 - WEB_Z0)
        tri = np.abs(((self.ss - self.s0) / pitch) % 1 - .5) * 2 * (WEB_Z1 - WEB_Z0) + WEB_Z0
        lo, hi = .2, 6.0
        for _ in range(30):
            w = (lo + hi) / 2
            ribs = np.abs(self.zz - tri) < w / 2 * math.sqrt(2)
            area = (self.web & ~ribs).sum() * self.h ** 2
            if area > area_target:
                lo = w
            else:
                hi = w
        solid = (self.web & ribs) | self.solid
        return self.evaluate(solid), w


WEB_Z0, WEB_Z1 = -7.6, -0.8   # 1.8 mm rim rail above the band, stays below the PCB
SOLID_FRAC, SEED_PITCH = 0.40, 5.6


def build_walls():
    run_side = (YB + CORNER, YF - CORNER)
    run_end = (XL + CORNER, XR - CORNER)
    bosses = sorted({(y - BOSS_OD / 2, y + BOSS_OD / 2) for _, y in SCREWS})
    side_t, end_t = -TOL - XL, YF - (PCB_H + TOL)
    rows = sorted({k[1] for k in KEYS})
    cols = sorted({k[0] for k in KEYS})
    z_front, z_back = z_under(YF), z_under(YB)
    side = Wall("side", YB, YF, z_under, side_t, run_side, bosses, [],
                [(EN["y"], 10.0)] + [(r, 5.0) for r in rows], (YB + 5, YF - 5))
    front = Wall("front", XL, XR, lambda s: z_front, end_t, run_end, [], [],
                 [(c, 5.0) for c in cols], (XL + 5, XR - 5))
    notch = (USB_CX - UC["w"] / 2 - .2, USB_CX + UC["w"] / 2 + .2, SKIRT_BOT, USB_CZ + UC["h"] / 2)
    back = Wall("back", XL, XR, lambda s: z_back, end_t, run_end, [], [notch],
                [(EN["x"], 10.0)] + [(c, 5.0) for c in cols], (XL + 5, XR - 5))
    return side, front, back


# ------------------------------------------------------------------ floors
XIAO_ZONE = box(MCU["x"] - 1.2, -TOL, MCU["x"] + MCU["w"] + 1.2, MCU["h"] + 1.8).buffer(-1.5).buffer(1.5)
XIAO_ZONE = XIAO_ZONE.union(box(MCU["x"] - 1.2, -TOL, MCU["x"] + MCU["w"] + 1.2, 3))


def post_pts():
    return [Point(max(-TOL, min(x, PCB_W + TOL)), y) for x, y in SCREWS]


def floor_checks(solid_floor):
    """Measured on the floor domain only: open area, worst hole, thin struts."""
    region = POCKET.buffer(-0.01)
    fl = solid_floor.intersection(region)
    opened = solid_floor.buffer(-MIN_STRUT / 2, join_style=2).buffer(MIN_STRUT / 2, join_style=2)
    # raster the holes to get the biggest inscribed circle
    res = 0.1
    w, h = int((PCB_W + 2 * TOL) / res), int((PCB_H + 2 * TOL) / res)
    img = Image.new("1", (w, h), 1)
    dr = ImageDraw.Draw(img)
    for g in polys(fl):
        dr.polygon([((a + TOL) / res, (b + TOL) / res) for a, b in g.exterior.coords], fill=0)
        for r in g.interiors:
            dr.polygon([((a + TOL) / res, (b + TOL) / res) for a, b in r.coords], fill=1)
    edt = ndi.distance_transform_edt(np.pad(np.array(img), 1))    # the pad makes the rim count as solid
    open_frac = 1 - fl.area / region.area
    lost = fl.difference(opened.buffer(0.05))
    # a real thin strut leaves a long sliver, a sharp junction corner leaves a short one
    slivers = [g for g in polys(lost) if g.area > 0.02]
    longest = max((math.hypot(*(np.ptp(np.array(g.exterior.coords), axis=0))) for g in slivers), default=0)
    return {"open_fraction": open_frac, "open_area_mm2": region.area - fl.area,
            "removed_cm3_at_2p5": (region.area - fl.area) * 2.5 / 1000,
            "largest_hole_inscribed_d_mm": 2 * float(edt.max()) * res,
            "thin_sliver_longest_mm": float(longest), "holes": sum(len(g.interiors) for g in polys(fl))}


def polys(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [p for p in getattr(g, "geoms", []) for p in polys(p)]


def bone_floor():
    """Graded Voronoi. Pattern only: the floor carries almost no load, nothing here is optimised."""
    rng = np.random.default_rng(11)
    posts = post_pts()
    def dist_field(p):
        return min(XIAO_ZONE.distance(p), min(q.distance(p) for q in posts))
    def spacing(p):
        return 3.7 + 3.0 * min(dist_field(p) / 24, 1)
    seeds = []
    for _ in range(30000):
        p = Point(rng.uniform(-TOL, PCB_W + TOL), rng.uniform(-TOL, PCB_H + TOL))
        if XIAO_ZONE.contains(p):
            continue
        r = spacing(p)
        if all(math.dist(p.coords[0], q) > r for q in seeds):
            seeds.append(p.coords[0])
    field = POCKET.difference(XIAO_ZONE.buffer(0.0))
    for _ in range(2):                                          # half a Lloyd step, keeps the grading
        cells = shapely.voronoi_polygons(MultiPoint(seeds), extend_to=POCKET.buffer(20))
        moved = []
        for c in cells.geoms:
            cc = c.intersection(field)
            if cc.is_empty:
                continue
            s = min(seeds, key=lambda q: math.dist(q, (c.representative_point().x, c.representative_point().y)) if not c.contains(Point(q)) else -1)
            m = cc.centroid
            moved.append((s[0] * .5 + m.x * .5, s[1] * .5 + m.y * .5))
        seeds = moved
    cells = shapely.voronoi_polygons(MultiPoint(seeds), extend_to=POCKET.buffer(20))
    holes = []
    for c in cells.geoms:
        cc = c.intersection(field)
        if cc.is_empty or cc.geom_type != "Polygon":
            continue
        d = dist_field(cc.centroid)
        strut = 1.3 + 1.3 * (1 - min(d / 22, 1))              # thicker toward posts and the XIAO shield
        rim_gap = 0.3 if POCKET.exterior.distance(cc.centroid) < 5 else 0
        h = cc.buffer(-strut / 2 - rim_gap, join_style=2)
        h = h.buffer(-1.1).buffer(1.1, quad_segs=8)             # corner radius, no needle points
        for g in polys(h):
            if g.area > 5.0:
                holes.append(g)
    solid = SHELL.difference(unary_union(holes))
    return holes, solid, seeds


def rest_columns():
    """Spots on the PCB underside for Ø3 rest columns, at least 0.5 mm clear of every pad and part."""
    obstacles = [box(p["x0"], p["y0"], p["x1"], p["y1"]) for p in PADS]
    obstacles += [box(x - 1.6, y - 1.4, x + 1.6, y + 1.4) for x, y in GLOW]
    obstacles += [box(MCU["x"], -1.4, MCU["x"] + MCU["w"], MCU["h"])]
    obs = unary_union(obstacles)
    zones = [(36.0, 24.0, "behind row 0, OLED side"), (56.0, 16.0, "beside the EC11"),
             (4.5, 15.0, "under the OLED left end"), (42.0, 11.0, "under the OLED header end"),
             (30.5, 43.0, "centre"), (21.0, 62.0, "row 2 left"), (40.0, 62.0, "row 2 right")]
    out = []
    for zx, zy, why in zones:
        best, score = None, -1
        for dx in np.arange(-6, 6.01, 0.5):
            for dy in np.arange(-6, 6.01, 0.5):
                p = Point(zx + dx, zy + dy)
                if not (2.5 < p.x < PCB_W - 2.5 and 2.5 < p.y < PCB_H - 2.5):
                    continue
                c = min(obs.distance(p), 4.0) - 0.05 * math.hypot(dx, dy)
                if c > score:
                    best, score = p, c
        if best is not None and obs.distance(best) >= 2.0:    # r 1.5 + 0.5 clear
            out.append({"x": float(best.x), "y": float(best.y), "pad_clear_mm": float(obs.distance(best) - 1.5), "why": why})
    return out


def chaikin(pts, n=2):
    p = np.asarray(pts, float)
    for _ in range(n):
        q = np.repeat(p[:-1], 2, axis=0) * np.tile([[.75], [.25]], (len(p) - 1, 1)) + \
            np.repeat(p[1:], 2, axis=0) * np.tile([[.25], [.75]], (len(p) - 1, 1))
        p = np.vstack([p[0], q, p[-1]])
    return p


def root_floor(columns):
    """Space colonisation from the screw posts and rest columns. Each tip then runs on along its
    heading until it meets another branch, the rim or the XIAO shield, so nothing is left as a free
    cantilever. Widths follow a Murray-style rule. It reads as biology, it is not a load calculation."""
    rng = np.random.default_rng(23)
    field = POCKET.buffer(-1.0).difference(XIAO_ZONE.buffer(1.0))
    pts = []
    while len(pts) < 460:
        p = Point(rng.uniform(-TOL, PCB_W + TOL), rng.uniform(-TOL, PCB_H + TOL))
        if field.contains(p):
            pts.append(p.coords[0])
    att = np.array(pts)
    seeds = [(p.x + (1.5 if p.x < CX else -1.5), p.y) for p in post_pts()] + [(c["x"], c["y"]) for c in columns]
    nodes = np.array(seeds, float)
    parent = [-1] * len(nodes)
    influence, kill, step = 16.0, 3.4, 2.0
    for _ in range(120):
        if not len(att):
            break
        d = np.linalg.norm(att[:, None] - nodes[None], axis=2)
        near = d.argmin(1)
        keep = d.min(1) > kill
        att, near, d = att[keep], near[keep], d[keep]
        moved = {}
        for a, n in enumerate(near):
            if d[a, n] < influence:
                moved.setdefault(int(n), []).append((att[a] - nodes[n]) / max(d[a, n], 1e-6))
        if not moved:
            break
        add = []
        for n, vs in moved.items():
            v = np.mean(vs, 0)
            v /= max(np.linalg.norm(v), 1e-6)
            q = nodes[n] + v * step
            if POCKET.contains(Point(q)) and not XIAO_ZONE.contains(Point(q)):
                add.append(q)
                parent.append(n)
        if not add:
            break
        nodes = np.vstack([nodes, add])
    n = len(nodes)
    kids = [[] for _ in range(n)]
    for i, p in enumerate(parent):
        if p >= 0:
            kids[p].append(i)
    w = np.zeros(n)
    tip_w, exp_m = MIN_STRUT + 0.1, 2.6
    for i in range(n - 1, -1, -1):
        w[i] = tip_w if not kids[i] else sum(w[k] ** exp_m for k in kids[i]) ** (1 / exp_m)
    w = np.clip(w, tip_w, 3.2)
    # chains between junctions, smoothed so the branches read as grown rather than stepped
    chains = []
    for i in range(n):
        if parent[i] == -1 or len(kids[parent[i]]) > 1:
            chain = [parent[i], i] if parent[i] >= 0 else [i]
            while len(kids[chain[-1]]) == 1:
                chain.append(kids[chain[-1]][0])
            if len(chain) > 1:
                chains.append(chain)
    segs, lines = [], []
    for ch in chains:
        c = chaikin(nodes[ch], 3)
        ws = np.interp(np.linspace(0, 1, len(c)), np.linspace(0, 1, len(ch)), w[ch])
        lines.append(LineString(c))
        for a in range(len(c) - 1):
            segs.append(LineString([c[a], c[a + 1]]).buffer((ws[a] + ws[a + 1]) / 4, quad_segs=6))
    links = 0
    targets = [POCKET.exterior, XIAO_ZONE.exterior]
    all_lines = shapely.MultiLineString(lines)
    for ch in chains:
        t = ch[-1]
        if kids[t]:
            continue
        p = nodes[t]
        dirn = nodes[t] - nodes[ch[-2]]
        dirn /= max(np.linalg.norm(dirn), 1e-6)
        own = LineString(nodes[ch]).buffer(1.2)
        others = all_lines.difference(own)
        ray = LineString([p + dirn * .5, p + dirn * 13])
        best = None
        for tgt in [others] + targets:
            hit = ray.intersection(tgt)
            if hit.is_empty:
                continue
            q = shapely.ops.nearest_points(Point(p), hit)[1]
            dq = Point(p).distance(q)
            if best is None or dq < best[0]:
                best = (dq, (q.x, q.y))
        if best is None:
            for tgt in [others] + targets:
                q = shapely.ops.nearest_points(Point(p), tgt)[1]
                dq = Point(p).distance(q)
                if best is None or dq < best[0]:
                    best = (dq, (q.x, q.y))
        segs.append(LineString([p, best[1]]).buffer(tip_w / 2, quad_segs=6))
        links += 1
    net = unary_union(segs).buffer(0.35).buffer(-0.35)
    feet = [Point(c["x"], c["y"]).buffer(2.4) for c in columns]
    solid_in = unary_union([net, XIAO_ZONE] + feet).intersection(POCKET)
    # a vein across any hole that is still too big, along its shortest chord through the widest point
    veins = 0
    for _ in range(40):
        big = None
        for g in polys(POCKET.difference(solid_in)):
            c = shapely.maximum_inscribed_circle(g, tolerance=0.05)
            r = c.length
            if r * 2 > MAX_FLOOR_HOLE - 0.3 and (big is None or r > big[0]):
                big = (r, g, Point(c.coords[0]))
        if big is None:
            break
        _, g, ctr = big
        best = None
        for ang in np.linspace(0, math.pi, 13)[:-1]:
            dx, dy = math.cos(ang) * 60, math.sin(ang) * 60
            ray = LineString([(ctr.x - dx, ctr.y - dy), (ctr.x + dx, ctr.y + dy)]).intersection(g)
            for part in (ray.geoms if hasattr(ray, "geoms") else [ray]):
                if part.distance(ctr) < 1e-6 and (best is None or part.length < best.length):
                    best = part
        solid_in = solid_in.union(best.buffer(tip_w / 2, quad_segs=6))
        veins += 1
    holes = []
    for g in polys(POCKET.difference(solid_in)):
        for h in polys(g.buffer(-0.95, quad_segs=8).buffer(0.95, quad_segs=8)):
            if h.area > 5.0:
                holes.append(h)
    solid = SHELL.difference(unary_union(holes))
    return holes, solid, {"nodes": n, "tips": sum(1 for ch in chains if not kids[ch[-1]]), "tip_links": links, "extra_veins": veins}


# ------------------------------------------------------------------ drawing
SS = 2
INK = (222, 232, 240)
DIM = (130, 150, 165)
BG = (11, 14, 19)
PART = (20, 23, 28)
EDGE = (64, 74, 86)
ICE_LO, ICE_HI = np.array([18, 88, 112.]), np.array([214, 248, 255.])
WARM = (255, 176, 64)


def font(size, bold=False):
    size = int(size * SS)
    for name, idx in (("/System/Library/Fonts/HelveticaNeue.ttc", 1 if bold else 0),
                      ("/System/Library/Fonts/Helvetica.ttc", 1 if bold else 0),
                      ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0)):
        try:
            return ImageFont.truetype(name, size, index=idx)
        except OSError:
            continue
    return ImageFont.load_default(size)


class Sheet:
    def __init__(self, w, h):
        self.w, self.h = w * SS, h * SS
        self.a = np.empty((self.h, self.w, 3), np.float32)
        self.a[:] = BG

    def fill(self, mask, color):
        self.a[mask > 127] = color

    def composite(self, mask, rgb):
        m = (mask[..., None] / 255.0).astype(np.float32)
        self.a[:] = self.a * (1 - m) + rgb * m

    def add(self, rgb):
        self.a[:] = np.clip(self.a + rgb, 0, 255)

    def image(self):
        return Image.fromarray(self.a.clip(0, 255).astype(np.uint8))

    def set(self, img):
        self.a[:] = np.asarray(img.convert("RGB"), np.float32)

    def blank(self):
        return Image.new("L", (self.w, self.h), 0)


class View:
    """Maps PCB coordinates to sheet pixels. mirror=True is the underside, flipped about the long axis."""

    def __init__(self, ox, oy, scale, mirror=False):
        self.ox, self.oy, self.s, self.mirror = ox, oy, scale, mirror

    def __call__(self, x, y):
        u = (XR - x) if self.mirror else (x - XL)
        return (self.ox + u * self.s) * SS, (self.oy + (y - YB) * self.s) * SS

    def ring(self, coords):
        return [self(a, b) for a, b in coords]


def poly_mask(sheet, geoms, view):
    m = sheet.blank()
    d = ImageDraw.Draw(m)
    for g in geoms:
        for p in polys(g):
            d.polygon(view.ring(p.exterior.coords), fill=255)
            for r in p.interiors:
                d.polygon(view.ring(r.coords), fill=0)
    return np.asarray(m)


def glow_field(sheet, view, boost=1.0):
    """Inverse-square falloff from the four glow LEDs. Colour only, not an optical simulation."""
    yy, xx = np.mgrid[0:sheet.h, 0:sheet.w].astype(np.float32)
    f = np.zeros_like(xx)
    for gx, gy in GLOW:
        px, py = view(gx, gy)
        dist2 = ((xx - px) ** 2 + (yy - py) ** 2) / (view.s * SS) ** 2
        f += 1 / (dist2 + 260)
    f = (f / f.max()) ** 1.6 * boost
    return np.clip(f, 0, 1)[..., None]


def ice(f):
    return (ICE_LO * (1 - f) + ICE_HI * f).astype(np.float32)


def dashed(d, pts, color, width=1, on=7, off=5):
    on, off = on * SS, off * SS
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        pos = 0.0
        while pos < L:
            e = min(pos + on, L)
            d.line([(x0 + (x1 - x0) * pos / L, y0 + (y1 - y0) * pos / L),
                    (x0 + (x1 - x0) * e / L, y0 + (y1 - y0) * e / L)], fill=color, width=width * SS)
            pos += on + off


def rect_ring(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def ghost_top_features(d, view, col=DIM):
    """Keys, OLED window, dial and PCB, dashed, so the pattern can be read against the real layout."""
    dashed(d, view.ring(rect_ring(0, 0, PCB_W, PCB_H)), col, on=4, off=6)
    for x, y, role in KEYS:
        dashed(d, view.ring(rect_ring(x - 7, y - 7, x + 7, y + 7)), col, on=5, off=4)
    dashed(d, view.ring(rect_ring(OLED["x"], OLED["y"], OLED["x"] + OLED["w"], OLED["y"] + OLED["h"])), col, on=5, off=4)
    r = [(EN["x"] + 9 * math.cos(a), EN["y"] + 9 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 49)]
    dashed(d, view.ring(r), col, on=4, off=4)


def draw_xiao(d, view):
    r = rect_ring(MCU["x"], MCU["y"], MCU["x"] + MCU["w"], MCU["y"] + MCU["h"])
    dashed(d, view.ring(r), WARM, on=5, off=4)
    x, y = view(MCU["x"] + MCU["w"] / 2, MCU["y"] + MCU["h"] / 2)
    d.text((x, y), "XIAO", fill=WARM, font=font(13), anchor="mm")


def draw_posts(d, view, boss=True):
    for x, y in SCREWS:
        px, py = view(x, y)
        s = view.s * SS
        for dia, col, w in ((BOSS_OD, EDGE, 2), (5.8, INK, 2), (3.4, DIM, 1)):
            r = dia / 2 * s
            d.ellipse([px - r, py - r, px + r, py + r], outline=col, width=w * SS)


def draw_leds(d, view):
    for x, y in GLOW:
        px, py = view(x, y)
        r = 3 * SS
        d.ellipse([px - r, py - r, px + r, py + r], fill=(255, 255, 255))


def label(d, xy, text, size=15, color=INK, anchor="la", bold=False):
    d.text((xy[0] * SS, xy[1] * SS), text, fill=color, font=font(size, bold), anchor=anchor)


def callout(d, start_px, text_xy, text, side="l", size=14, color=INK):
    """Leader from a point in sheet pixels (already scaled by SS) to a label in sheet units."""
    tx, ty = text_xy[0] * SS, text_xy[1] * SS
    d.line([start_px, (tx - (6 * SS if side == "l" else -6 * SS), ty)], fill=DIM, width=SS)
    r = 2.5 * SS
    d.ellipse([start_px[0] - r, start_px[1] - r, start_px[0] + r, start_px[1] + r], fill=color)
    lines = text.split("\n")
    for i, t in enumerate(lines):
        y = ty - (len(lines) - 1) * (size + 3) * SS / 2 + i * (size + 3) * SS
        d.text((tx, y), t, fill=color, font=font(size), anchor="lm" if side == "l" else "rm")


def scale_bar(d, x, y, scale, mm=20):
    x0, y0 = x * SS, y * SS
    x1 = x0 + mm * scale * SS
    d.line([(x0, y0), (x1, y0)], fill=INK, width=2 * SS)
    for xx in (x0, x1):
        d.line([(xx, y0 - 5 * SS), (xx, y0 + 5 * SS)], fill=INK, width=2 * SS)
    d.text(((x0 + x1) / 2, y0 + 8 * SS), f"{mm} mm", fill=INK, font=font(13), anchor="ma")


def draw_floor(name, title, sub, holes, solid, notes, extra=None):
    scale = 9.5
    W, H = 1400, 1120
    sheet = Sheet(W, H)
    ox = W - SHELL_W * scale - 70
    oy = 128
    v = View(ox, oy, scale, mirror=True)
    shell_m = poly_mask(sheet, [SHELL], v)
    hole_m = poly_mask(sheet, holes, v)
    floor_rgb = ice(glow_field(sheet, v))
    # soft bloom off the lit holes, then the black part, then the holes themselves
    bloom = Image.fromarray(hole_m).filter(ImageFilter.GaussianBlur(26 * SS))
    b = np.asarray(bloom, np.float32)[..., None] / 255
    halo = Image.fromarray(shell_m).filter(ImageFilter.GaussianBlur(30 * SS))
    sheet.add(np.asarray(halo, np.float32)[..., None] / 255 * np.array([12, 46, 58], np.float32))
    sheet.fill(shell_m, PART)
    sheet.add(b * np.array([10, 34, 42], np.float32) * (shell_m[..., None] > 127))
    sheet.composite(hole_m, floor_rgb)
    img = sheet.image()
    d = ImageDraw.Draw(img)
    d.line(v.ring(SHELL.exterior.coords), fill=EDGE, width=2 * SS)
    ghost_top_features(d, v, col=(150, 170, 182))
    draw_posts(d, v)
    draw_leds(d, v)
    draw_xiao(d, v)
    if extra:
        extra(d, v)
    label(d, (48, 34), title, 30, bold=True)
    label(d, (48, 74), sub, 16, DIM)
    y = 150
    label(d, (48, y), "Measured on this pattern", 15, bold=True)
    for i, t in enumerate(notes):
        label(d, (48, y + 26 + i * 23), t, 14, DIM)
    # legend, bottom left
    ly = H - 150
    d.line([(52 * SS, ly * SS), (84 * SS, ly * SS)], fill=(150, 170, 182), width=SS)
    label(d, (94, ly - 9), "dashed: PCB, keys, OLED, dial (above)", 13, DIM)
    d.ellipse([(62 * SS, (ly + 18) * SS), (74 * SS, (ly + 30) * SS)], outline=INK, width=2 * SS)
    label(d, (94, ly + 15), "screw post, Ø5.8 counterbore", 13, DIM)
    d.ellipse([(65 * SS, (ly + 45) * SS), (71 * SS, (ly + 51) * SS)], fill=(255, 255, 255))
    label(d, (94, ly + 39), "glow LED (on the PCB, above)", 13, DIM)
    scale_bar(d, 60, H - 56, scale)
    label(d, (W - 48, H - 62), "Underside view, flipped about the long axis. USB edge at the top.", 13, DIM, "ra")
    label(d, (W - 48, H - 40), "Glow colour is illustrative, not an optical simulation.", 13, DIM, "ra")
    bx = v(30.5, YB - 1)
    d.text((bx[0], bx[1] - 6 * SS), "USB-C, back", fill=DIM, font=font(13), anchor="ms")
    img = img.resize((W, H), Image.LANCZOS)
    img.save(HERE / name, optimize=True)


def lantern_plan():
    """Plan shapes of the channel behind the ribs, the iced fence and the LED light bridges."""
    bosses = unary_union([Point(x, y).buffer(BOSS_OD / 2, quad_segs=32) for x, y in SCREWS])
    cavity = unary_union([POCKET, SHELL.buffer(-RIB_DEPTH)]).difference(bosses).buffer(-0.2).buffer(0.2)
    cavity = max(polys(cavity), key=lambda g: g.area)
    usb = box(USB_CX - UC["w"] / 2 - .2, YB, USB_CX + UC["w"] / 2 + .2, 4)
    fence = cavity.buffer(-0.3).difference(cavity.buffer(-1.9)).difference(usb)
    bridges = []
    for gx, gy in GLOW:
        left, back_led = gx < CX, gy < CY
        x0, x1 = (XL + RIB_DEPTH + .3, gx + 3.5) if left else (gx - 3.5, XR - RIB_DEPTH - .3)
        bridges.append(box(x0, gy - 3.5, x1, gy + 3.5).intersection(cavity.buffer(-0.3)))
    return cavity, fence, bridges


def led_intensity(w):
    """Relative irradiance along a wall from the 4 glow LEDs, inverse square. For colour only."""
    pts = w.s0 + (np.arange(int(round((w.s1 - w.s0) / w.px))) + .5) * w.px
    i = np.zeros_like(pts)
    for gx, gy in GLOW:
        if w.name == "side":
            i += 1 / ((pts - gy) ** 2 + (gx - XL) ** 2 + 40)
        elif w.name == "front":
            i += 1 / ((pts - gx) ** 2 + (YF - gy) ** 2 + 40)
        else:
            i += 1 / ((pts - gx) ** 2 + (gy - YB) ** 2 + 40)
    return i


def draw_lantern(walls, finals, numbers):
    W, H = 1840, 1170
    sc = 9.2
    sheet = Sheet(W, H)
    v = View(60, 150, sc)
    side, front, back = walls
    vs, vf, vb = finals["side"], finals["front"], finals["back"]
    zc = -5.7

    def intervals(w, v_hi):
        row = int(round((w.ztop - zc) / w.px))
        lab, n = ndi.label(v_hi[row])
        out = []
        for k in range(1, n + 1):
            idx = np.flatnonzero(lab == k)
            out.append((w.s0 + idx[0] * w.px, w.s0 + (idx[-1] + 1) * w.px))
        return out

    windows = []
    for a, b in intervals(side, vs):
        windows += [box(XL, a, XL + RIB_DEPTH, b), box(XR - RIB_DEPTH, a, XR, b)]
    for a, b in intervals(front, vf):
        windows.append(box(a, YF - RIB_DEPTH, b, YF))
    for a, b in intervals(back, vb):
        windows.append(box(a, YB, b, YB + RIB_DEPTH))
    cavity, fence, bridges = lantern_plan()
    shell_m = poly_mask(sheet, [SHELL], v)
    cav_m = poly_mask(sheet, [cavity], v)
    win_m = poly_mask(sheet, windows, v)
    core_m = poly_mask(sheet, [fence] + bridges, v)
    f = glow_field(sheet, v, 1.0)
    halo = Image.fromarray(win_m).filter(ImageFilter.GaussianBlur(26 * SS))
    sheet.add(np.asarray(halo, np.float32)[..., None] / 255 * np.array([34, 112, 138], np.float32))
    sheet.fill(shell_m, (30, 34, 40))
    sheet.composite(cav_m, (ice(f * .12) * .42).astype(np.float32))
    sheet.composite(win_m, ice(f * .7 + .1))
    sheet.composite(core_m, ice(np.clip(f * .8 + .3, 0, 1)))
    ex = 790
    rows = [("Left side wall from outside. Back at left, front at right.", side, vs, 118),
            ("Front wall, from the user's side.", front, vf, 436),
            ("Back wall. USB-C window with the band tongue under it.", back, vb, 684)]
    imax = max(led_intensity(w).max() for w in walls)
    drawn = []
    for title, w, vh, top in rows:
        hh, ww = vh.shape
        tw, th = int(round(ww * w.px * sc * SS)), int(round(hh * w.px * sc * SS))
        zz = w.ztop - (np.arange(hh) + .5) * w.px
        ss = w.s0 + (np.arange(ww) + .5) * w.px
        Z, S = np.meshgrid(zz, ss, indexing="ij")
        i = np.clip((led_intensity(w)[:ww] / imax), 0, 1) ** .5
        lit = ice(np.clip(i * .85 + .1, 0, 1)[:, None])[None, :, :] * np.ones((hh, 1, 1), np.float32)
        rgb = np.empty((hh, ww, 3), np.float32)
        rgb[:] = BG
        rgb[Z >= SKIRT_BOT] = (26, 29, 35)
        band = (Z < SKIRT_BOT) & (Z >= BAND_BOT)
        rgb[band] = (lit[band] * .55 + 110).clip(0, 255)
        low = Z < BAND_BOT
        rgb[low] = (lit[low] * .32 + np.array([44, 54, 62], np.float32) * .9).clip(0, 255)
        rgb[vh] = lit[vh]
        if w is back:
            uw = UC["w"] / 2
            hole = (np.abs(S - USB_CX) < uw + .2) & (Z < USB_CZ + UC["h"] / 2) & (Z >= USB_CZ - UC["h"] / 2)
            tongue = (np.abs(S - USB_CX) < uw) & (Z < USB_CZ - UC["h"] / 2) & (Z >= SKIRT_BOT)
            rgb[hole] = (6, 7, 9)
            rgb[tongue] = (lit[tongue] * .55 + 110).clip(0, 255)
        rgb[Z < w.z_low(S)] = BG
        im = Image.fromarray(rgb.clip(0, 255).astype(np.uint8)).resize((tw, th), Image.LANCZOS)
        ox_px, oy_px = int(ex * SS), int((top + 44) * SS)
        mask = (vh | ((Z < SKIRT_BOT) & (Z >= BAND_BOT)))
        glow = Image.fromarray((mask * 255).astype(np.uint8)).resize((tw, th)).filter(ImageFilter.GaussianBlur(7 * SS))
        sheet.a[oy_px:oy_px + th, ox_px:ox_px + tw] = np.asarray(im, np.float32)
        sheet.a[oy_px:oy_px + th, ox_px:ox_px + tw] += np.asarray(glow, np.float32)[..., None] / 255 * np.array([8, 34, 42], np.float32)
        drawn.append((title, w, top, ox_px, oy_px, tw, th))
    sheet.a[:] = sheet.a.clip(0, 255)
    img = sheet.image()
    d = ImageDraw.Draw(img)
    d.line(v.ring(SHELL.exterior.coords), fill=EDGE, width=2 * SS)
    ghost_top_features(d, v)
    draw_posts(d, v)
    draw_leds(d, v)
    for title, w, top, ox, oy, tw, th in drawn:
        label(d, (ex, top), title, 14, INK)

        def sp(s, z):
            return ox + (s - w.s0) * sc * SS, oy + (w.ztop - z) * sc * SS

        if w is side:
            for y in sorted({y for _, y in SCREWS}):
                r = BOSS_OD / 2
                dashed(d, [sp(y - r, SKIRT_BOT), sp(y - r, 3.4), sp(y + r, 3.4), sp(y + r, SKIRT_BOT)], (120, 138, 152), on=3, off=3)
                d.text(sp(y, 3.9), "M3 boss", fill=DIM, font=font(11), anchor="ms")
        seen = []
        for s, fn in sorted(w.load_points, key=lambda t: -t[1]):
            if any(abs(s - q) < 3 for q in seen):
                continue
            seen.append(s)
            xa, ya = sp(s, w.ztop)
            d.line([(xa, ya - 16 * SS), (xa, ya - 3 * SS)], fill=WARM, width=2 * SS)
            d.polygon([(xa - 4 * SS, ya - 8 * SS), (xa + 4 * SS, ya - 8 * SS), (xa, ya - 1 * SS)], fill=WARM)
            d.text((xa, ya - 18 * SS), f"{fn:.0f} N", fill=WARM, font=font(11), anchor="ms")
        for s in w.feet:
            xa = sp(s, 0)[0]
            ya = sp(s, float(w.z_low(s)))[1] + 3 * SS
            d.polygon([(xa, ya), (xa - 6 * SS, ya + 9 * SS), (xa + 6 * SS, ya + 9 * SS)], fill=DIM)
    label(d, (48, 30), "Lantern Ribcage: black ribs over a lit iced core", 30, bold=True)
    label(d, (48, 70), "Left: plan section at z = -5.7 mm through the skirt. Right: wall elevations, same scale. Graded Voronoi ribs, FE-checked, not optimised.", 16, DIM)
    n = numbers
    s_ = n["side"]
    notes = [
        f"Top in matte black PETG: {RIB_DEPTH:.0f} mm rib skin, open channel behind it. GlowBand in iced PETG, grown into a 1.6 mm fence that stands in the channel.",
        f"Ribs ≥ {MIN_RIB} mm, windows ≥ {MIN_WINDOW} mm. Roofs 45° or flat ≤ {BRIDGE_MAX:.0f} mm as printed (Top prints face down, so windows point at the band).",
        f"{n['windows']} windows, {n['window_area_mm2']:.0f} mm² of lit wall. {n['removed_cm3']:.1f} cm³ of CAD volume out of the Top, {n['fence_cm3']:.1f} cm³ added to the band.",
        f"Side wall FE, worst load: no windows {s_['solid']['max_deflection_mm'] * 1000:.1f} µm, these ribs {s_['ribs']['max_deflection_mm'] * 1000:.1f} µm, plain 45° zigzag of equal open area {s_['zigzag']['max_deflection_mm'] * 1000:.1f} µm.",
    ]
    for i, t in enumerate(notes):
        label(d, (ex, 1012 + i * 23), t, 13.5, DIM)
    scale_bar(d, 60, H - 70, sc)
    label(d, (280, H - 88), "Bright ice: fence and LED light bridges. Ice gaps in the rim: windows at this height.", 13, DIM)
    label(d, (280, H - 66), "Triangles: stick-on feet, the FE supports. Orange: FE loads.", 13, DIM)
    label(d, (280, H - 44), "Glow colour is inverse-square shading, not an optical simulation.", 13, DIM)
    a_ = v(USB_CX, YB)
    d.text((a_[0], a_[1] - 8 * SS), "USB-C, back", fill=DIM, font=font(13), anchor="ms")
    img = img.resize((W, H), Image.LANCZOS)
    img.save(HERE / "concept-1-lantern-ribcage.png", optimize=True)


def draw_simp_strip(w, finals, r):
    """What the optimiser alone produces next to the pattern used, same wall, same loads."""
    sc, W, H = 13, 1340, 560
    rows = [(finals["side_simp"], f"SIMP result: {r['simp_stats']['windows']} windows, {r['simp_stats']['web_open_fraction'] * 100:.0f} % of the web open, "
             f"{r['simp']['max_deflection_mm'] * 1000:.2f} µm. A plain zigzag at that open area: {r['zigzag_at_simp_area']['max_deflection_mm'] * 1000:.2f} µm."),
            (finals["side"], f"Pattern used: {r['stats']['windows']} windows, {r['stats']['web_open_fraction'] * 100:.0f} % of the web open, "
             f"{r['ribs']['max_deflection_mm'] * 1000:.2f} µm. A plain zigzag at that open area: {r['zigzag']['max_deflection_mm'] * 1000:.2f} µm.")]
    img = Image.new("RGB", (W * SS, H * SS), BG)
    d = ImageDraw.Draw(img)
    label(d, (40, 26), "Side wall: optimiser output against the pattern used", 24, bold=True)
    z0, z1 = 0.8, -9.4
    for n, (v, cap) in enumerate(rows):
        top = 92 + n * 228
        i0, i1 = int((w.ztop - z0) / w.px), int((w.ztop - z1) / w.px)
        j0, j1 = int((YB + CORNER - 2 - w.s0) / w.px), int((YF - CORNER + 2 - w.s0) / w.px)
        crop = v[i0:i1, j0:j1]
        rgb = np.empty(crop.shape + (3,), np.uint8)
        rgb[:] = (30, 34, 40)
        rgb[crop] = (150, 226, 245)
        pic = Image.fromarray(rgb).resize((int(crop.shape[1] * w.px * sc * SS), int(crop.shape[0] * w.px * sc * SS)), Image.LANCZOS)
        img.paste(pic, (40 * SS, (top + 30) * SS))
        d = ImageDraw.Draw(img)
        label(d, (40, top), cap, 15, INK)
    scale_bar(d, 40, H - 44, sc, 10)
    label(d, (260, H - 42), "Deflection is the worst single load on one wall (10 N knob, 5 N key), PETG E = 2 GPa, supported on two feet.", 13, DIM)
    img.resize((W, H), Image.LANCZOS).save(HERE / "simp-vs-pattern-side-wall.png", optimize=True)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="run the FE benchmark only")
    ap.add_argument("--force", action="store_true", help="rerun SIMP instead of using cached fields")
    a = ap.parse_args()
    bench = fe_benchmark()
    print("FE benchmark", bench)
    if a.check:
        return
    PAT.mkdir(exist_ok=True)
    res = {"inputs": {"shell_w": SHELL_W, "shell_h": SHELL_H, "corner": CORNER, "screws": SCREWS, "boss_od": BOSS_OD,
                      "E_MPa": E_PETG, "nu": NU, "min_strut": MIN_STRUT, "min_window": MIN_WINDOW},
           "fe_benchmark": bench}

    walls = build_walls()
    finals, wall_res, poly_out = {}, {}, {}
    for w in walls:
        xp, hist = w.run_simp(a.force)
        v_simp, coarse_simp = w.finish(xp)
        simp_stats = w.stats(v_simp)
        simp_eval = w.evaluate(~coarse_simp & ~w.outside)
        v = w.bone_web(3 + len(w.name))
        finals[w.name] = v
        finals[w.name + "_simp"] = v_simp
        coarse = w.coarsen(v)
        ribs = w.evaluate(~coarse & ~w.outside)
        solid_web = w.evaluate(~w.outside)
        target_area = (coarse & w.web).sum() * w.h ** 2
        zig, zig_w = w.diamond_benchmark(target_area)
        # the same open area as the SIMP result, so that comparison is like for like
        zig_s, _ = w.diamond_benchmark((coarse_simp & w.web).sum() * w.h ** 2)
        s = w.stats(v)
        wall_res[w.name] = {"thick_mm": w.thick, "rib_depth_mm": RIB_DEPTH, "stats": s, "simp_stats": simp_stats,
                            "ribs": ribs, "simp": simp_eval, "solid": solid_web, "zigzag": zig, "zigzag_rib_w_mm": zig_w,
                            "zigzag_at_simp_area": zig_s, "simp_iters": len(hist), "web_mm2": float(w.web.sum() * w.h ** 2)}
        poly_out[w.name] = w.polygons(v)
        print(w.name, s, simp_stats["web_open_fraction"], "defl solid/bone/zig | simp/zig um",
              [round(1000 * x["max_deflection_mm"], 2) for x in (solid_web, ribs, zig, simp_eval, zig_s)])
    (PAT / "lantern_windows.json").write_text(json.dumps({
        "_about": "Window outlines (s, z) in mm. side: s = PCB y, mirror to both side walls, cut x from skin to the pocket wall. front and back: s = PCB x.",
        **poly_out}))
    total_rm = 2 * wall_res["side"]["stats"]["removed_cm3"] + wall_res["front"]["stats"]["removed_cm3"] + wall_res["back"]["stats"]["removed_cm3"]
    total_win = 2 * wall_res["side"]["stats"]["window_area_mm2"] + wall_res["front"]["stats"]["window_area_mm2"] + wall_res["back"]["stats"]["window_area_mm2"]
    n_win = 2 * wall_res["side"]["stats"]["windows"] + wall_res["front"]["stats"]["windows"] + wall_res["back"]["stats"]["windows"]
    cavity, fence, bridges = lantern_plan()
    fence_cm3 = fence.area * (-0.9 - SKIRT_BOT) / 1000
    channel_cm3 = (cavity.area - POCKET.area) * (WEB_Z1 - SKIRT_BOT) / 1000
    total_rm += channel_cm3
    res["lantern"] = {"walls": wall_res, "windows": n_win, "window_area_mm2": total_win, "removed_cm3": total_rm,
                      "channel_cm3": channel_cm3, "fence_added_cm3": fence_cm3,
                      "cavity_area_mm2": cavity.area, "pocket_area_mm2": POCKET.area}

    holes, solid, _ = bone_floor()
    chk = floor_checks(solid)
    res["bone_floor"] = chk
    print("bone", chk)
    (PAT / "bone_floor_holes.json").write_text(json.dumps({
        "_about": "Through-holes in the Bottom floor, PCB coordinates (mm)",
        "holes": [[[round(a, 3), round(b, 3)] for a, b in h.exterior.simplify(0.03).coords] for h in holes]}))
    draw_floor("concept-2-bone-floor.png", "Bone Floor: graded Voronoi Bottom",
               "Black floor over a lit chamber. Looks generative: the floor carries almost no load, so this pattern is not optimised.",
               holes, solid,
               [f"{chk['holes']} holes, {chk['open_fraction'] * 100:.0f} % open",
                "Struts 1.3 to 2.6 mm by construction",
                f"Largest hole: Ø{chk['largest_hole_inscribed_d_mm']:.1f} inscribed (limit Ø{MAX_FLOOR_HOLE})",
                "Solid shield under the XIAO",
                f"{chk['removed_cm3_at_2p5']:.1f} cm³ removed from a 2.5 mm floor"])

    cols = rest_columns()
    holes2, solid2, tree = root_floor(cols)
    chk2 = floor_checks(solid2)
    res["root_floor"] = {**chk2, "tree": tree, "columns": cols}
    print("root", chk2, tree, cols)
    (PAT / "root_floor_holes.json").write_text(json.dumps({
        "_about": "Through-holes and rest columns for the Bottom floor, PCB coordinates (mm)", "columns": cols,
        "holes": [[[round(a, 3), round(b, 3)] for a, b in h.exterior.simplify(0.03).coords] for h in holes2]}))

    def cols_draw(d, v):
        for c in cols:
            px, py = v(c["x"], c["y"])
            r = 1.5 * v.s * SS
            d.ellipse([px - r, py - r, px + r, py + r], fill=(60, 66, 76), outline=WARM, width=2 * SS)

    draw_floor("concept-3-root-floor.png", "Root Floor: branching floor with PCB rest columns",
               "Roots grow from the 4 screw posts and the rest columns (orange). Looks generative: space colonisation, not a load calculation.",
               holes2, solid2,
               [f"{chk2['holes']} holes, {chk2['open_fraction'] * 100:.0f} % open",
                f"Tips {MIN_STRUT + .1:.1f} mm, trunks up to 3.2 mm, Murray-style taper",
                f"Largest hole: Ø{chk2['largest_hole_inscribed_d_mm']:.1f} inscribed (limit Ø{MAX_FLOOR_HOLE})",
                f"{len(cols)} Ø3 rest columns, ≥ {min(c['pad_clear_mm'] for c in cols):.2f} mm clear of every pad",
                f"{tree['tip_links']} of {tree['tips']} tips fused to a neighbour"], cols_draw)

    draw_lantern(walls, finals, {"windows": n_win, "window_area_mm2": total_win, "removed_cm3": total_rm, "fence_cm3": fence_cm3, "side": wall_res["side"]})
    draw_simp_strip(walls[0], finals, wall_res["side"])
    (HERE / "results.json").write_text(json.dumps(res, indent=1))
    print("done")


if __name__ == "__main__":
    main()
