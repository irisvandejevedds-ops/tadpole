"""Draws the two Tadpole icons from the widget's sprite sheet.
The web app is a green frog on deep pond blue; the widget app is a yellow tadpole on dark amber, so the two are easy to tell apart on a home screen.
Both web icons are full-bleed squares with the picture well inside the safe zone: Android adds its own shape and a transparent corner shows up as a white disc."""
import json
import pathlib
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPRITES = json.loads((ROOT / "android/assets/tadpole.json").read_text())
WEB = {"stage": 5, "color": "green", "bg": "#123A43"}
WIDGET = {"stage": 0, "color": "yellow", "bg": "#3D2F0E"}


def sprite(stage, color, cell):
    rows, pal = SPRITES["stages"][stage], SPRITES["palettes"][color]
    cells = [(x, y, pal[ch]) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch != "."]
    x0, x1 = min(c[0] for c in cells), max(c[0] for c in cells)
    y0, y1 = min(c[1] for c in cells), max(c[1] for c in cells)
    im = Image.new("RGBA", ((x1 - x0 + 1) * cell, (y1 - y0 + 1) * cell), (0, 0, 0, 0))
    for x, y, col in cells:
        im.paste(Image.new("RGBA", (cell, cell), col), ((x - x0) * cell, (y - y0) * cell))
    return im


def icon(spec, size, fraction, background=True):
    s = sprite(spec["stage"], spec["color"], 1)
    cell = max(1, int(size * fraction) // s.width)
    s = sprite(spec["stage"], spec["color"], cell)
    out = Image.new("RGBA", (size, size), spec["bg"] if background else (0, 0, 0, 0))
    out.paste(s, ((size - s.width) // 2, (size - s.height) // 2), s)
    return out


if __name__ == "__main__":
    web = ROOT / "app/tadpole/static/icons"
    for name, size in (("icon-192.png", 192), ("icon-512.png", 512), ("icon-maskable-512.png", 512)):
        icon(WEB, size, 0.66).save(web / name)
    android = ROOT / "android/res"
    icon(WIDGET, 432, 0.58, background=False).save(android / "drawable-xxxhdpi/ic_launcher_fg.png")
    icon(WIDGET, 192, 0.66).save(android / "mipmap-xxxhdpi/ic_launcher.png")
    (android / "values/colors.xml").write_text(f'<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_bg">{WIDGET["bg"]}</color>\n</resources>\n')
    print("icons written")
