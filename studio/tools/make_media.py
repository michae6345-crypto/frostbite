"""Builds docs/images/status-cycle.gif and docs/images/presets-grid.png.

Usage (macOS; needs qlmanage and Pillow):
  node studio/tools/export-media.js <work-dir>
  uvx --python 3.12 --with pillow python studio/tools/make_media.py <work-dir> <images-dir>
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

work = Path(sys.argv[1]).resolve()
dest = Path(sys.argv[2]).resolve()
media = json.loads((work / "media.json").read_text())
WHITE = (255, 255, 255)


def raster(rel, px):
    """SVG -> RGB PNG via Quick Look, cropped to content (Quick Look pads to a square)."""
    svg = work / rel
    subprocess.run(["qlmanage", "-t", "-s", str(px), "-o", str(svg.parent), str(svg)],
                   check=True, capture_output=True)
    png = svg.with_name(svg.name + ".png")
    im = Image.open(png).convert("RGBA")
    flat = Image.new("RGB", im.size, WHITE)
    flat.paste(im, mask=im.split()[3])
    return flat


def bbox(im):
    diff = ImageChops.difference(im, Image.new("RGB", im.size, WHITE)).convert("L")
    return diff.point(lambda v: 255 if v > 6 else 0).getbbox()


def font(size, bold=False):
    for name in ("HelveticaNeue.ttc", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(f"/System/Library/Fonts/{name}", size, index=1 if bold else 0)
        except OSError:
            pass
    return ImageFont.load_default()


# status-cycle.gif
frames = [raster(f, 1400) for f in media["frames"]]
boxes = [bbox(f) for f in frames]
box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
W = 700
margin = 24
inner = W - 2 * margin
scale = inner / (box[2] - box[0])
H = round((box[3] - box[1]) * scale) + 2 * margin
gif = []
for f in frames:
    c = f.crop(box).resize((inner, H - 2 * margin), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), WHITE)
    canvas.paste(c, (margin, margin))
    gif.append(canvas)
# One shared palette (no dithering) avoids speckle in the glows and lets the
# GIF store only changed pixels. Half comes from the all-idle frame (greys of
# the shell and caps), half from the coloured frames (status hues).
strip = Image.new("RGB", (W, H * (len(gif) - 1)))
for i, g in enumerate(gif[1:]):
    strip.paste(g, (0, H * i))
greys = gif[0].quantize(colors=128, method=Image.Quantize.MEDIANCUT).getpalette()[:128 * 3]
hues = strip.quantize(colors=128, method=Image.Quantize.FASTOCTREE).getpalette()[:128 * 3]
pal = Image.new("P", (1, 1))
pal.putpalette(greys + hues)
q = [g.quantize(palette=pal, dither=Image.Dither.NONE) for g in gif]
q[0].save(dest / "status-cycle.gif", save_all=True, append_images=q[1:], duration=1000, loop=0, optimize=True)

# presets-grid.png
COLS, GW = 4, 1400
pad, gap, label_h = 28, 16, 40
cell_w = (GW - 2 * pad - (COLS - 1) * gap) // COLS
art_h = 380
rows = (len(media["presets"]) + COLS - 1) // COLS
GH = 2 * pad + rows * (art_h + label_h) + (rows - 1) * gap
grid = Image.new("RGB", (GW, GH), WHITE)
draw = ImageDraw.Draw(grid)
f_name = font(20, bold=True)
for i, p in enumerate(media["presets"]):
    im = raster(p["file"], 1000)
    im = im.crop(bbox(im))
    s = min((cell_w - 8) / im.width, (art_h - 8) / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    r, c = divmod(i, COLS)
    x0 = pad + c * (cell_w + gap)
    y0 = pad + r * (art_h + label_h + gap)
    grid.paste(im, (x0 + (cell_w - im.width) // 2, y0 + art_h - im.height))
    tw = draw.textlength(p["name"], font=f_name)
    draw.text((x0 + (cell_w - tw) / 2, y0 + art_h + 10), p["name"], fill=(70, 78, 88), font=f_name)
grid.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG) \
    .save(dest / "presets-grid.png", optimize=True)
print("ok")
