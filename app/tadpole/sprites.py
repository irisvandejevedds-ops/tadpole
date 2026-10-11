"""The tadpole and the frog it grows into, drawn on a small grid. Letters: o outline, b body, l light, d shade, v belly, w eye white, k pupil, m mouth, . empty.
Six stages (tadpole, leg buds, back legs, four legs, froglet, frog) in three colour moods (green, yellow, red)."""
import json
import math

W, H = 32, 24
PALETTES = {
    "green":  {"o": "#16351F", "b": "#4CBB59", "l": "#8EE27B", "d": "#2F8442", "v": "#CDEFA2", "w": "#FFFFFF", "k": "#101810", "m": "#16351F"},
    "yellow": {"o": "#3A3510", "b": "#D6BF3A", "l": "#F3E56F", "d": "#9A8620", "v": "#F8F0BC", "w": "#FFFFFF", "k": "#181808", "m": "#3A3510"},
    "red":    {"o": "#3A1410", "b": "#D5503A", "l": "#F28C70", "d": "#93291D", "v": "#F8C7B0", "w": "#FFFFFF", "k": "#180808", "m": "#3A1410"},
}
MOODS = tuple(PALETTES)
STAGE_COUNT = 6


class Grid:
    def __init__(self):
        self.g = [["."] * W for _ in range(H)]

    def put(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.g[y][x] = c

    def get(self, x, y):
        return self.g[y][x] if 0 <= x < W and 0 <= y < H else "."

    def ellipse(self, cx, cy, rx, ry, c="b"):
        for y in range(H):
            for x in range(W):
                if ((x - cx) / (rx + 0.35)) ** 2 + ((y - cy) / (ry + 0.35)) ** 2 <= 1.0:
                    self.g[y][x] = c

    def thick_line(self, pts, t=1, c="b"):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(abs(x1 - x0), abs(y1 - y0), 1)
            for i in range(n + 1):
                x, y = round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)
                for dx in range(t):
                    for dy in range(t):
                        self.put(x + dx, y + dy, c)

    def tail(self, x0, x1, yc, half0, amp=1.6):
        for x in range(x0, x1 + 1):
            f = (x - x0) / max(1, x1 - x0)
            half = half0 * (1 - f) + 0.2
            y = yc + math.sin(f * 5.0) * amp * f
            for yy in range(H):
                if abs(yy - y) <= half:
                    self.put(x, yy, "b")

    def finish(self):
        """Light on top edges, shade on bottom edges, belly underneath, then an outline around everything."""
        g = self.g
        base = [row[:] for row in g]
        for y in range(H):
            for x in range(W):
                if base[y][x] == "b":
                    if base[y - 1][x] == "." if y else True:
                        g[y][x] = "l"
                    elif y + 1 >= H or base[y + 1][x] == ".":
                        g[y][x] = "d"
        out = [row[:] for row in g]
        for y in range(H):
            for x in range(W):
                if g[y][x] == "." and any(self.get(x + dx, y + dy) not in (".", "o") for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    out[y][x] = "o"
        self.g = out
        return ["".join(r) for r in out]


def eye(g, x, y, big=True):
    if big:
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            g.put(x + dx, y + dy, "w")
        g.put(x, y + 1, "k")
        g.put(x, y, "k") if False else None
    else:
        g.put(x, y, "w")
        g.put(x, y + 1, "k")


def belly(g, cx, cy, rx, ry, below):
    for y in range(H):
        for x in range(W):
            if g.get(x, y) in ("b", "d", "l") and y >= below and ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                g.put(x, y, "v")


def leg(g, pts, t=2):
    g.thick_line(pts, t, "b")


def stage_rows(stage):
    g = Grid()
    if stage <= 3:                                    # tadpole body at the left, tail to the right
        g.tail(14, 30, 11, 3.2 if stage < 3 else 2.6)
        g.ellipse(9, 11, 7, 6)
        belly(g, 9, 14, 6, 4, 13)
        if stage >= 1:
            g.ellipse(14, 16, 1, 1) if stage == 1 else None
        if stage == 1:
            g.thick_line([(12, 16), (13, 18)], 2, "b")
        if stage >= 2:                                # back legs: thigh, shin, foot
            leg(g, [(12, 15), (15, 18), (19, 19)], 2)
            leg(g, [(19, 19), (22, 19)], 1)
            g.put(22, 20, "b")
            g.put(20, 20, "b")
        if stage >= 3:                                # front legs under the head
            leg(g, [(7, 16), (7, 19), (5, 20)], 2)
            g.put(4, 20, "b")
        eye(g, 5, 8)
        g.put(2, 12, "m")
        g.put(3, 12, "m")
    elif stage == 4:                                  # froglet: longer body, a short tail, big legs
        g.tail(21, 27, 12, 1.6, 0.8)
        g.ellipse(11, 12, 9, 5)
        g.ellipse(6, 9, 4, 3)
        belly(g, 11, 15, 8, 4, 14)
        leg(g, [(14, 15), (18, 19), (24, 20)], 2)
        leg(g, [(24, 20), (28, 20)], 1)
        g.put(28, 21, "b")
        g.put(26, 21, "b")
        leg(g, [(7, 15), (7, 19), (4, 20)], 2)
        g.put(3, 20, "b")
        eye(g, 4, 7)
        g.put(2, 10, "m")
        g.put(3, 10, "m")
        g.put(4, 10, "m")
    else:                                             # the frog, sitting
        g.ellipse(16, 14, 10, 6)
        g.ellipse(8, 11, 6, 4)
        g.ellipse(6, 6, 2, 2)
        g.ellipse(11, 6, 2, 2)
        belly(g, 16, 17, 9, 4, 16)
        g.ellipse(21, 16, 5, 4)                       # folded back leg
        leg(g, [(18, 20), (22, 21), (29, 21)], 2)
        g.put(30, 22, "b")
        g.put(28, 22, "b")
        leg(g, [(8, 17), (8, 21), (5, 22)], 2)
        g.put(4, 22, "b")
        eye(g, 5, 5)
        eye(g, 10, 5)
        for x in range(2, 9):
            g.put(x, 13, "m")
    return g.finish()


_cache = {}


def rows(stage):
    stage = max(0, min(STAGE_COUNT - 1, stage))
    if stage not in _cache:
        _cache[stage] = stage_rows(stage)
    return _cache[stage]


def svg(stage, mood="green", scale=8, cls=""):
    pal = PALETTES.get(mood, PALETTES["green"])
    r = rows(stage)
    parts = []
    for y, row in enumerate(r):
        x = 0
        while x < len(row):
            c = row[x]
            if c == ".":
                x += 1
                continue
            x2 = x
            while x2 < len(row) and row[x2] == c:
                x2 += 1
            parts.append(f'<rect x="{x}" y="{y}" width="{x2 - x}" height="1" fill="{pal[c]}"/>')
            x = x2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="{cls}" width="{W * scale}" height="{H * scale}" viewBox="0 0 {W} {H}" '
            f'shape-rendering="crispEdges" role="img" aria-label="Tadpole">' + "".join(parts) + "</svg>")


def android_json():
    return json.dumps({"w": W, "h": H, "stages": [rows(i) for i in range(STAGE_COUNT)], "palettes": PALETTES})
