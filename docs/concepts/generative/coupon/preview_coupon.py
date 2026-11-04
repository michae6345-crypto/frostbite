"""Plain material previews of the coupon. No light is simulated: the iced part is a flat colour.

Run:  CAD/.venv/bin/python docs/concepts/generative/coupon/preview_coupon.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shapely
import trimesh
import vtk
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MPath
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray

HERE = Path(__file__).resolve().parent
B = json.loads((HERE / "build.json").read_text())["parts"]
BLACK, ICE, BG = (0.09, 0.10, 0.11), (0.70, 0.90, 0.97), (0.93, 0.94, 0.95)


def design(name):
    """Mesh back in the design frame."""
    m = trimesh.load_mesh(HERE / f"{name}.stl")
    m.apply_translation(-np.array(B[name]["translate"]))
    if B[name]["flip_about_x"]:
        m.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))
    return m


def actor(m, rgb):
    pts = vtk.vtkPoints()
    pts.SetData(numpy_to_vtk(np.asarray(m.vertices, float), deep=True))
    f = np.hstack([np.full((len(m.faces), 1), 3), m.faces]).astype(np.int64).ravel()
    cells = vtk.vtkCellArray()
    cells.SetCells(len(m.faces), numpy_to_vtkIdTypeArray(f, deep=True))
    pd = vtk.vtkPolyData()
    pd.SetPoints(pts)
    pd.SetPolys(cells)
    n = vtk.vtkPolyDataNormals()
    n.SetInputData(pd)
    n.SetFeatureAngle(35)
    mp = vtk.vtkPolyDataMapper()
    mp.SetInputConnection(n.GetOutputPort())
    a = vtk.vtkActor()
    a.SetMapper(mp)
    p = a.GetProperty()
    p.SetColor(*rgb)
    p.SetAmbient(0.25)
    p.SetDiffuse(0.75)
    p.SetSpecular(0.08)
    return a


def shot(parts, focal, direction, up, scale, out, size=(1500, 700)):
    r = vtk.vtkRenderer()
    r.SetBackground(*BG)
    for m, c in parts:
        r.AddActor(actor(m, c))
    w = vtk.vtkRenderWindow()
    w.SetOffScreenRendering(1)
    w.AddRenderer(r)
    w.SetSize(*size)
    cam = r.GetActiveCamera()
    cam.ParallelProjectionOn()
    cam.SetFocalPoint(*focal)
    cam.SetPosition(*(np.array(focal) + 200 * np.array(direction)))
    cam.SetViewUp(*up)
    cam.SetParallelScale(scale)
    r.ResetCameraClippingRange()
    w.Render()
    f = vtk.vtkWindowToImageFilter()
    f.SetInput(w)
    f.Update()
    png = vtk.vtkPNGWriter()
    png.SetFileName(str(HERE / out))
    png.SetInputConnection(f.GetOutputPort())
    png.Write()


def sections(wall, fence):
    fig, axes = plt.subplots(1, 3, figsize=(13, 5.2), sharey=True, constrained_layout=True)
    for ax, (y, title) in zip(axes, ((25.4, "At the LED, PCB y 25.4"), (45.0, "Mid span, PCB y 45"), (62.1, "Through the M3 boss, PCB y 62.1"))):
        for m, c in ((wall, "#17191c"), (fence, "#9fdcf0")):
            seg = trimesh.intersections.mesh_plane(m, [0, 1, 0], [0, -y, 0])
            lines = shapely.linestrings(np.round(seg[:, :, [0, 2]], 6))
            g = shapely.build_area(shapely.line_merge(shapely.node(shapely.multilinestrings(lines))))
            verts, codes = [], []
            for p in (g.geoms if hasattr(g, "geoms") else [g]):
                for r in [p.exterior, *p.interiors]:
                    d = np.array(r.coords)
                    verts += d.tolist()
                    codes += [MPath.MOVETO] + [MPath.LINETO] * (len(d) - 2) + [MPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MPath(verts, codes), fc=c, ec="#333", lw=.4))
        ax.set_title(title, fontsize=11)
        ax.set_xlim(-10, 10)
        ax.set_ylim(-17.5, 7.5)
        ax.set_aspect("equal")
        ax.set_xlabel("x, mm (outside at left)")
        ax.grid(alpha=.25)
    axes[0].set_ylabel("z, mm (PCB underside = 0)")
    axes[0].plot([5], [-0.84], "o", c="#d33", ms=4)
    axes[0].annotate("LED lens", (5, -0.84), (3.2, 3), fontsize=9, arrowprops=dict(arrowstyle="-", lw=.6))
    fig.savefig(HERE / "preview-sections.png", dpi=130)


def main():
    wall, fence = design("coupon-wall"), design("coupon-fence")
    c = np.array([-3, -43, -5])
    lifted = wall.copy()
    lifted.apply_translation([0, 0, 22])
    shot([(wall, BLACK), (fence, ICE)], c + [0, 0, 0], (-1, 0, 0), (0, 0, 1), 15, "preview-outside.png", (1500, 520))
    el = math.radians(30)
    shot([(wall, BLACK), (fence, ICE)], c, (-math.cos(el), 0, math.sin(el)), (0, 0, 1), 15, "preview-seated-30deg.png", (1500, 520))
    shot([(lifted, BLACK), (fence, ICE)], c + [0, 0, 11], (0.75, -0.45, 0.5), (0, 0, 1), 31, "preview-exploded.png", (1300, 950))
    pw = trimesh.load_mesh(HERE / "coupon-wall.stl")
    pf = trimesh.load_mesh(HERE / "coupon-fence.stl")
    pf.apply_translation([26, 0, 0])
    shot([(pw, BLACK), (pf, ICE)], (13, 0, 8), (-0.6, -0.65, 0.5), (0, 0, 1), 31, "preview-print-orientation.png", (1300, 900))
    sections(wall, fence)


if __name__ == "__main__":
    main()
