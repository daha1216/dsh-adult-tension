"""Tiny pixel-art raster kit: a cell grid with ordered dithering, shaded blobs, polygons, a 5x7 font, and SVG output (one path per colour)."""
import math

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def dth(x, y, f):
    """True when a cell at (x, y) should take the next tone for fraction f in [0, 1]."""
    return f * 16 > BAYER[int(y) % 4][int(x) % 4] + 0.5


def ramp(pal, t, x, y):
    t = min(max(t, 0.0), 0.9999)
    v = t * (len(pal) - 1)
    i = int(v)
    if i + 1 < len(pal) and dth(x, y, v - i):
        i += 1
    return pal[i]


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.g = [[None] * w for _ in range(h)]
        self.mask = None

    def put(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h and c:
            self.g[y][x] = c
            if self.mask is not None:
                self.mask.add((x, y))

    def get(self, x, y):
        return self.g[y][x] if 0 <= x < self.w and 0 <= y < self.h else None

    def clear(self, x0, y0, x1, y1):
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                self.g[y][x] = None

    def fn(self, x0, y0, x1, y1, f):
        for y in range(max(0, int(y0)), min(self.h, int(math.ceil(y1)))):
            for x in range(max(0, int(x0)), min(self.w, int(math.ceil(x1)))):
                c = f(x, y)
                if c:
                    self.put(x, y, c)

    def rect(self, x0, y0, x1, y1, c):
        self.fn(x0, y0, x1, y1, (lambda x, y: c(x, y)) if callable(c) else (lambda x, y: c))

    def ellipse(self, cx, cy, rx, ry, c):
        def f(x, y):
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1:
                return c(x, y) if callable(c) else c
        self.fn(cx - rx - 1, cy - ry - 1, cx + rx + 1, cy + ry + 1, f)

    def poly(self, pts, c):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]

        def inside(px, py):
            r = False
            n = len(pts)
            for i in range(n):
                (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
                if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
                    r = not r
            return r

        def f(x, y):
            if inside(x + 0.5, y + 0.5):
                return c(x, y) if callable(c) else c
        self.fn(min(xs), min(ys), max(xs) + 1, max(ys) + 1, f)

    def line(self, x0, y0, x1, y1, c, w=1):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for k in range(n + 1):
            t = k / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            for a in range(w):
                for b in range(w):
                    self.put(round(x) + a - w // 2, round(y) + b - w // 2, c(x, y) if callable(c) else c)

    def vgrad(self, x0, y0, x1, y1, pal, ya=None, yb=None):
        ya = y0 if ya is None else ya
        yb = y1 if yb is None else yb
        self.rect(x0, y0, x1, y1, lambda x, y: ramp(pal, (y - ya) / max(1, yb - ya), x, y))

    def text(self, s, x, y, c, sc=1, font=None):
        font = font or FONT
        for ch in s:
            for j, row in enumerate(font[ch]):
                for i, b in enumerate(row):
                    if b == "#":
                        self.rect(x + i * sc, y + j * sc, x + (i + 1) * sc, y + (j + 1) * sc, c)
            x += 6 * sc

    def emit(self, C, ox=0, oy=0):
        paths = {}
        for y in range(self.h):
            x = 0
            while x < self.w:
                col = self.g[y][x]
                x1 = x
                while x1 < self.w and self.g[y][x1] == col:
                    x1 += 1
                if col:
                    paths.setdefault(col, []).append(f"M{(x + ox) * C},{(y + oy) * C}h{(x1 - x) * C}v{C}h{-(x1 - x) * C}z")
                x = x1
        return "\n".join(f'<path fill="{c}" d="{"".join(d)}"/>' for c, d in paths.items())


def blob_shade(cv, puffs, pal, squash=1.0, light=(-0.55, -0.8), tex=None, rnd=None, edge=None):
    """Draw overlapping round puffs (cx, cy, r) lit from `light`; each cell takes the puff it is deepest inside."""
    lx, ly = light
    x0 = min(p[0] - p[2] for p in puffs) - 1
    x1 = max(p[0] + p[2] for p in puffs) + 1
    y0 = min(p[1] - p[2] / squash for p in puffs) - 1
    y1 = max(p[1] + p[2] / squash for p in puffs) + 1

    def f(x, y):
        best = None
        for cx, cy, r in puffs:
            dx, dy = (x + 0.5 - cx) / r, (y + 0.5 - cy) * squash / r
            d = dx * dx + dy * dy
            if d <= 1 and (best is None or d < best[0]):
                best = (d, dx, dy)
        if best is None:
            return None
        d, nx, ny = best
        nz = math.sqrt(max(0, 1 - nx * nx - ny * ny))
        lum = lx * nx + ly * ny + 0.45 * nz
        t = (lum + 0.9) / 1.9
        if edge:
            t = edge(x, y, t)
        if tex and rnd and rnd.random() < tex:
            t += rnd.choice([-0.22, 0.18])
        return ramp(pal, t, x, y)
    cv.fn(x0, y0, x1, y1, f)


FONT = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    ".": [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    ":": [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
    "·": [".....", ".....", ".....", "..#..", ".....", ".....", "....."],
    " ": ["....."] * 7,
}


def svg_doc(W, H, title, desc, defs, body):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
  <title id="t">{title}</title>
  <desc id="d">{desc}</desc>
  <defs>
    {defs}
    <clipPath id="frame"><rect width="{W}" height="{H}" rx="16"/></clipPath>
  </defs>
  <g clip-path="url(#frame)">
{body}
  </g>
</svg>
'''
