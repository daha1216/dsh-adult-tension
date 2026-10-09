"""Lo-fi pixel README set to match the bedroom hero: five section banners, a corkboard world wall, a cassette shelf of materials.
Writes into .github/readme-lofi/ next to hero.svg (made by readme_overlay.py). The banners and the shelf's window show crops of
the user's own bedroom picture (cropped, never repainted), and everything shares the hero's violet-and-grey palette."""
import base64
import io
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pixkit as pk  # noqa: E402
from PIL import Image  # noqa: E402  (dev-only: crops the user's picture)

OUT = os.environ.get("README_OUT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".github", "readme-lofi")
os.makedirs(OUT, exist_ok=True)
BG = os.environ.get("README_BG", "dusk")       # dusk (default): dithered sky; wall: striped wallpaper; mosaic: the picture in big dark blocks
C = 4
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif"
MONO = "ui-monospace,Consolas,monospace"
PIC = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "source", "bedroom.webp")).convert("RGB")
GLOW, CORE, SUBT = "#a874ff", "#efeaf5", "#c4bfcc"        # the hero's violet glow, grey-white type, grey subtitle
BULBS = ["#c9a2ff", "#ff8fc4", "#e9dcff"]
LIT = ["#ffd88a", "#ffb7d6", "#9fe9ff", "#ffe6b0", "#d7b8ff"]
pk.FONT["K"] = ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"]
pk.FONT["M"] = ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size, fill, weight=700, anchor="start", spacing=0, family=SANS, extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}" letter-spacing="{spacing}" {extra}>{esc(s)}</text>')


def neon(x, y, s, size, anchor="start", col=GLOW, core=CORE, flicker=False):
    anim = ('<animate attributeName="opacity" values="1;1;0.55;1;1;0.7;1" keyTimes="0;0.8;0.81;0.83;0.93;0.94;1" dur="6s" repeatCount="indefinite"/>'
            if flicker else "")
    d = max(2, round(size / 16))                                   # a harder, greyer drop shadow under the glow
    return (f'<g>{anim}' + text(x + d, y + d, s, size, "#4e4a56", 800, anchor, 3, SANS)
            + text(x, y, s, size, col, 800, anchor, 3, SANS, 'filter="url(#g6)"')
            + text(x, y, s, size, core, 800, anchor, 3, SANS, f'stroke="{col}" stroke-width="{size / 34:.1f}"') + '</g>')


DEFS = '''<pattern id="wallp" width="48" height="8" patternUnits="userSpaceOnUse"><rect width="48" height="8" fill="#2d2131"/><rect x="36" width="12" height="8" fill="#302434"/></pattern>
    <filter id="g6" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
    <filter id="g15" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="15"/></filter>
    <filter id="g30" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="30"/></filter>
    <linearGradient id="lineg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#a874ff"/><stop offset="0.5" stop-color="#ff6fae"/><stop offset="1" stop-color="#a874ff"/></linearGradient>
    <linearGradient id="glint" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset="0.5" stop-color="#ffffff" stop-opacity="0.55"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
    <radialGradient id="vig" cx="0.5" cy="0.5" r="0.78"><stop offset="0.6" stop-color="#05020a" stop-opacity="0"/><stop offset="1" stop-color="#05020a" stop-opacity="0.5"/></radialGradient>'''


def crop(box, x, y, w, h, fade=None):
    """A losslessly re-encoded crop of the user's picture placed at (x, y, w, h); fade=(id, start) melts its right edge."""
    buf = io.BytesIO()
    PIC.crop(box).save(buf, "WEBP", lossless=True)
    href = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    img = f'<image href="{href}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" style="image-rendering:pixelated"/>'
    if not fade:
        return img
    fid, t = fade
    return (f'<defs><linearGradient id="{fid}g" x1="{x}" y1="0" x2="{x + w}" y2="0" gradientUnits="userSpaceOnUse">'
            f'<stop offset="{t}" stop-color="#fff"/><stop offset="1" stop-color="#000"/></linearGradient>'
            f'<mask id="{fid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{fid}g)"/></mask></defs>'
            f'<g mask="url(#{fid})">{img}</g>')


def dotline(W, y, begin=0.0):
    """The hero's 2px dotted gradient edge with a dithered fade and a slow glint running along it."""
    return (f'<g fill="url(#lineg)" shape-rendering="crispEdges">'
            f'<path d="{"".join(f"M{x} {y}h2v2h-2z" for x in range(0, W, 4))}"/>'
            f'<path opacity="0.45" d="{"".join(f"M{x} {y + 2}h2v2h-2z" for x in range(2, W, 4))}"/>'
            f'<path opacity="0.18" d="{"".join(f"M{x} {y + 4}h2v2h-2z" for x in range(0, W, 8))}"/></g>'
            f'<rect x="-120" y="{y - 3}" width="120" height="9" fill="url(#glint)">'
            f'<animate attributeName="x" values="-120;{W}" dur="6s" begin="{begin:.1f}s" repeatCount="indefinite"/></rect>')


PARTS = {}


def webp_href(img):
    buf = io.BytesIO()
    img.save(buf, "WEBP", lossless=True)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


DUSK = [(17, 13, 34), (24, 17, 48), (33, 21, 60), (44, 25, 70), (57, 28, 76), (70, 30, 78), (84, 33, 80)]


def background(name, W, H):
    """The backdrop behind every picture, picked by README_BG; each picture gets its own patch, chosen by its name."""
    if BG == "wall":
        return f'<rect width="{W}" height="{H}" fill="url(#wallp)"/>'
    rnd = random.Random(sum(map(ord, name)))
    if BG == "mosaic":
        BLK = 24
        pw, ph = PIC.size
        cw = min(pw, ph * W / H)
        ch = cw * H / W
        x0 = rnd.uniform(0, pw - cw)
        y0 = rnd.uniform(0, ph - ch)
        small = PIC.crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch))).resize((max(1, W // BLK), max(1, H // BLK)), Image.BOX)
        small = Image.eval(small, lambda v: int(v * 0.32))                   # darken so type and notes stay readable
        tint = Image.new("RGB", small.size, (40, 20, 60))
        small = Image.blend(small, tint, 0.25)                                  # pull every block toward the violet wall
        return (f'<image href="{webp_href(small)}" width="{W}" height="{H}" preserveAspectRatio="none" style="image-rendering:pixelated"/>')
    # dusk: an ordered-dither ramp in 8px blocks, deep violet at the top to a dim rose at the bottom, a few blinking stars
    BLK = 8
    w, h = W // BLK, H // BLK
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = min(0.9999, y / max(1, h - 1))
            v = t * (len(DUSK) - 1)
            i = int(v)
            if i + 1 < len(DUSK) and pk.dth(x, y, v - i):
                i += 1
            px[x, y] = DUSK[i]
    stars = "".join(f'<rect x="{rnd.randrange(w) * BLK}" y="{rnd.randrange(max(1, h * 2 // 3)) * BLK}" width="4" height="4" fill="#e9dcff">'
                    f'<animate attributeName="opacity" values="0.7;0.1;0.7" dur="{rnd.uniform(2.5, 5):.1f}s" begin="-{rnd.uniform(0, 4):.1f}s" repeatCount="indefinite"/></rect>'
                    for _ in range(max(4, W * H // 60000)))
    return (f'<image href="{webp_href(img)}" width="{W}" height="{H}" preserveAspectRatio="none" style="image-rendering:pixelated"/>'
            f'<g shape-rendering="crispEdges">{stars}</g>')


def doc(name, W, H, title, desc, defs, body):
    PARTS[name] = (W, H, defs, body)
    svg = pk.svg_doc(W, H, esc(title), esc(desc), DEFS + defs, f'    {background(name, W, H)}\n' + body
                     + f'\n    <rect width="{W}" height="{H}" fill="url(#vig)"/>')
    open(os.path.join(OUT, name), "w", encoding="utf-8", newline="\n").write(svg)
    print(name, len(svg) // 1024, "KB")


# ================================================================ shared pieces
def city(cv, x0, y0, x1, y1, rnd, sun=None):
    """Dusk skyline filling the glass rectangle; returns antenna blink positions."""
    h = y1 - y0
    cv.vgrad(x0, y0, x1, y1, ["#221d4c", "#2c2460", "#392b72", "#4c3283", "#653a92", "#82419b", "#a0499f", "#bc539f",
                              "#d4619f", "#e675a2", "#f28ca6", "#f9a6a8", "#fcc0a6"], y0, y1 - h * 0.12)
    for _ in range(int((x1 - x0) / 12)):
        cy = rnd.randint(y0 + 2, y0 + int(h * 0.5))
        cx = rnd.randint(x0 - 10, x1)
        w = rnd.randint(10, 30)
        for x in range(max(cx, x0), min(cx + w, x1)):
            cv.put(x, cy, "#a24c9c")
            cv.put(x, cy + 1, "#f2a2bf" if cy > y0 + h * 0.3 else "#c873b0")
    if sun:
        sx, sy, sr = sun
        for y in range(sy - sr, sy + sr):
            for x in range(sx - sr, sx + sr):
                if math.hypot(x + 0.5 - sx, y + 0.5 - sy) <= sr and not (y > sy - 2 and (y - sy) % 3 == 0):
                    cv.put(x, y, pk.ramp(["#ffb48a", "#ffc994", "#ffdca4", "#fff0c4"], 1 - (y - sy + sr) / (2 * sr), x, y))
    blinks = []

    def building(x, w, top, base, rim, lit, gx=2, roof=True):
        cv.rect(max(x, x0), top, min(x + w, x1), y1, base)
        if x >= x0:
            cv.rect(x, top, x + 1, y1, rim)
        cv.rect(max(x, x0), top, min(x + w, x1), top + 1, rim)
        for yy in range(top + 3, y1 - 1, 3):
            for xx in range(x + 2, x + w - 1, gx):
                if x0 <= xx < x1 and rnd.random() < lit:
                    cv.put(xx, yy, rnd.choice(LIT))
        if roof and rnd.random() < 0.45:
            ax = x + rnd.randint(2, max(2, w - 3))
            if x0 <= ax < x1:
                hh = rnd.randint(3, 7)
                cv.rect(ax, top - hh, ax + 1, top, base)
                blinks.append((ax, top - hh))

    for frac_lo, frac_hi, base, rim, lit, gap, wr, roof in ((0.62, 0.82, "#6a4592", "#8a5aa8", 0.08, 0, (6, 14), False),
                                                            (0.5, 0.8, "#432f78", "#6a4a9e", 0.22, 3, (8, 16), True),
                                                            (0.35, 0.78, "#261b4d", "#5a3f8f", 0.3, 5, (10, 20), True)):
        x = x0 - 4
        while x < x1:
            w = rnd.randint(*wr)
            building(x, w, int(y0 + h * rnd.uniform(frac_lo, frac_hi)), base, rim, lit, 3 if base == "#261b4d" else 2, roof)
            x += w + rnd.randint(0, gap)
    cv.rect(x0, y1 - 3, x1, y1, lambda x, y: pk.ramp(["#2a1e4e", "#4a2f6a", "#7a4278"], (y - y1 + 3) / 3, x, y))
    for x in range(x0, x1, 3):
        if rnd.random() < 0.5:
            cv.put(x, y1 - 1, rnd.choice(["#ffcf8a", "#ff9ac2"]))
    return blinks


def window(cv, x0, y0, x1, y1, rnd, mullion=None, transom=None, sun=None, curtain=True):
    blinks = city(cv, x0, y0, x1, y1, rnd, sun)
    cv.rect(x0 - 3, y0 - 3, x1 + 3, y0, "#17101a")
    cv.rect(x0 - 3, y0, x0, y1, "#17101a")
    cv.rect(x1, y0, x1 + 3, y1, "#17101a")
    if mullion:
        cv.rect(mullion, y0, mullion + 2, y1, "#17101a")
        cv.rect(mullion, y0, mullion + 1, y1, "#5c3a5e")
    if transom:
        cv.rect(x0, transom, x1, transom + 1, "#17101a")
        cv.rect(x0, transom + 1, x1, transom + 2, "#4a3050")
    cv.rect(x0 - 5, y1, x1 + 5, y1 + 2, "#3a2630")
    cv.rect(x0 - 5, y1, x1 + 5, y1 + 1, "#a06478")
    cv.rect(x0 - 5, y1 + 2, x1 + 5, y1 + 3, "#1e1419")
    if curtain:
        CURT = ["#2a0d18", "#3c1421", "#521c2c", "#6a2637", "#823246"]
        for x in range(x0 - 9, x0 + 1):
            for y in range(y0 - 3, y1 + 6):
                t = 0.5 + 0.45 * math.sin((x - x0) * 0.85 + (y - y0) / 40)
                cv.put(x, y, "#c2587e" if x == x0 else pk.ramp(CURT, t, x, y))
    return [b for b in blinks if b[1] >= y0]


def fairy(cv, x0, x1, y, sag, nails, step=6):
    """Fairy lights hanging in swags between nails; returns bulbs for the glow overlay."""
    bulbs = []
    pts = [x0 + (x1 - x0) * k / nails for k in range(nails + 1)]
    for a, b in zip(pts, pts[1:]):
        n = int(b - a)
        for i in range(n + 1):
            t = i / n
            cv.put(a + i, y + sag * 4 * t * (1 - t), "#3a2a2e")
        for i in range(step // 2, n, step):
            t = i / n
            col = BULBS[len(bulbs) % 3]
            yy = y + sag * 4 * t * (1 - t)
            cv.rect(a + i, yy + 1, a + i + 2, yy + 3, col)
            bulbs.append((a + i, yy + 2, col))
        cv.rect(a - 1, y - 1, a + 1, y + 1, "#5a4048")
    return bulbs


def fairy_svg(bulbs, rnd):
    return "".join(f'<circle cx="{(x + 1) * C}" cy="{y * C}" r="13" fill="{c}" fill-opacity="0.5" filter="url(#g6)"><animate attributeName="fill-opacity" values="0.55;0.12;0.55" '
                   f'dur="{rnd.uniform(2, 4):.1f}s" begin="-{rnd.uniform(0, 3):.1f}s" repeatCount="indefinite"/></circle>' for x, y, c in bulbs)


def blinks_svg(blinks, rnd):
    return "".join(f'<rect x="{x * C}" y="{y * C}" width="{C}" height="{C}" fill="#ff4a5a"><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.55;1" '
                   f'dur="{rnd.uniform(1.6, 2.6):.1f}s" repeatCount="indefinite"/></rect>' for x, y in blinks)


def steam(x, y):
    return "".join(f'<rect x="{(x + k * 2) * C}" y="{y * C}" width="{C}" height="{C}" fill="#ffffff"><animateTransform attributeName="transform" type="translate" values="0 0;{(-1) ** k * 5} -30" '
                   f'dur="2.6s" begin="-{k * 0.9:.1f}s" repeatCount="indefinite"/><animate attributeName="opacity" values="0;0.6;0" dur="2.6s" begin="-{k * 0.9:.1f}s" repeatCount="indefinite"/></rect>' for k in range(3))


def silhouette_rim(cv, draw, top_col, side_col, side=-1):
    cv.mask = set()
    draw()
    m = cv.mask
    cv.mask = None
    for (x, y) in m:
        if (x, y - 1) not in m:
            cv.put(x, y, top_col)
        elif (x + side, y) not in m:
            cv.put(x, y, side_col)
    return m


def plant(cv, x, y, pot="#b0603e"):
    cv.rect(x - 4, y - 6, x + 4, y, lambda xx, yy: pk.ramp(["#8a3e2a", pot, "#c87a52"], (xx - x + 4) / 8, xx, yy))
    cv.rect(x - 5, y - 7, x + 5, y - 6, "#c87a52")
    for (lx, ly, r) in [(x - 3, y - 10, 3), (x + 2, y - 12, 4), (x, y - 16, 3), (x + 4, y - 8, 3), (x - 4, y - 14, 3)]:
        pk.blob_shade(cv, [(lx, ly, r)], ["#1f4a2e", "#2e6a40", "#3f8a52", "#64b070"], squash=1.3)


def mug(cv, x, y):
    cv.rect(x, y - 6, x + 5, y, "#ece4d8")
    cv.rect(x, y - 6, x + 5, y - 5, "#ffffff")
    cv.rect(x + 5, y - 5, x + 7, y - 2, "#ece4d8")
    cv.rect(x + 1, y - 3, x + 4, y - 2, "#ff9ac2")


# ================================================================ section banners
BW, BH = 300, 44
DESK = 38


def banner(name, title, sub, seed, box):
    rnd = random.Random(seed)
    cv = pk.Canvas(BW, BH)
    body = f'''    {crop(box, 0, 0, 440, BH * C, ("fade", 0.72))}
    <ellipse cx="{BW * C - 300}" cy="100" rx="300" ry="70" fill="{GLOW}" fill-opacity="0.12" filter="url(#g30)"/>
    <g shape-rendering="crispEdges">{cv.emit(C)}</g>
    {neon(BW * C - 48, 98, title, 46, "end", "#a29dab", "#ecebef", flicker=True)}
    {text(BW * C - 50, 140, sub, 20, SUBT, 600, "end", 2)}
    {dotline(BW * C, 0, seed * 0.9)}'''
    doc(name, BW * C, BH * C, title, sub, "", body)


def v_proof(cv, rnd):        # the monitor with the chat
    MX0, MY0, MX1, MY1 = 14, 6, 62, 32
    cv.rect(MX0, MY0, MX1, MY1, "#0e0c12")
    cv.rect(MX0 + 2, MY0 + 2, MX1 - 2, MY1 - 2, "#1a1d32")
    cv.rect(MX0 + 2, MY0 + 2, MX1 - 2, MY0 + 4, "#262b4a")
    for i, c in enumerate(["#ff6f7f", "#ffd06f", "#6fe08f"]):
        cv.put(MX0 + 4 + i * 2, MY0 + 3, c)
    for k, (side, w) in enumerate([("l", 26), ("r", 16), ("l", 32), ("r", 12)]):
        y = MY0 + 6 + k * 5
        if side == "l":
            cv.ellipse(MX0 + 5.5, y + 1.5, 1.6, 1.6, "#ffb7d6")
            x0, bc, tc = MX0 + 8, "#d85a8e", "#ffd6e6"
        else:
            x0, bc, tc = MX1 - 4 - w, "#3fa9bd", "#d6f7fb"
        cv.rect(x0, y, x0 + w, y + 3, bc)
        for xx in range(x0 + 2, x0 + w - 2):
            if (xx * 7 + k) % 5:
                cv.put(xx, y + 1, tc)
    cv.rect(36, MY1, 40, DESK - 1, "#0e0c12")
    cv.rect(30, DESK - 1, 46, DESK, "#0e0c12")
    cv.rect(18, DESK - 2, 28, DESK, "#3a3446")
    cv.rect(48, DESK - 2, 58, DESK, "#3a3446")
    mug(cv, 66, DESK)
    cur = (MX0 + 8 + 26 + 1, MY0 + 6 + 15)
    return (f'<ellipse cx="{38 * C}" cy="{19 * C}" rx="130" ry="70" fill="#6fd0ff" fill-opacity="0.16" filter="url(#g15)"/>'
            f'<g shape-rendering="crispEdges">{steam(67, DESK - 8)}<rect x="{cur[0] * C}" y="{cur[1] * C}" width="{C}" height="{3 * C}" fill="#ffd6e6">'
            '<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1s" repeatCount="indefinite"/></rect></g>')


def v_why(cv, rnd):          # a notebook for the story, a locked card cabinet for the facts
    cv.poly([(6, DESK), (25, DESK - 1), (25, DESK - 8), (8, DESK - 7)], "#f2e8d6")
    cv.poly([(25, DESK - 1), (44, DESK), (42, DESK - 7), (25, DESK - 8)], "#e6dac6")
    cv.rect(24, DESK - 8, 26, DESK, "#b8a890")
    for k in range(3):
        cv.line(10, DESK - 5 + k * 1.5, 22, DESK - 5.6 + k * 1.5, "#d97aa6")
        cv.line(28, DESK - 5.6 + k * 1.5, 40, DESK - 5 + k * 1.5, "#8a7fae")
    cv.line(30, DESK - 12, 40, DESK - 4, "#e2a33b", 1)
    cv.line(31, DESK - 12, 41, DESK - 4, "#c8842a", 1)
    cv.put(41, DESK - 3, "#2a2030")
    cv.put(30, DESK - 13, "#ff9ac2")
    # cabinet
    cv.rect(48, 10, 72, DESK, "#3e3850")
    cv.rect(48, 10, 72, 11, "#6a6284")
    cv.rect(48, 10, 49, DESK, "#5a5274")
    for k in range(3):
        y = 13 + k * 8
        cv.rect(50, y, 70, y + 7, "#4c4562")
        cv.rect(50, y + 6, 70, y + 7, "#2a2438")
        cv.rect(56, y + 1, 64, y + 3, "#9fe9ff")
        cv.rect(57, y + 4, 63, y + 5, "#8a82a0")
    cv.rect(66, 15, 69, 19, "#e2b25a")
    cv.put(67, 16, "#2a2030")
    cv.rect(52, 6, 66, 10, "#efe6d4")              # index cards peeking from the top
    cv.rect(54, 4, 64, 6, "#f9f3e6")
    cv.rect(55, 5, 59, 6, "#ff9ac2")
    return ''.join(f'<rect x="{56 * C}" y="{(14 + k * 8) * C}" width="{8 * C}" height="{2 * C}" fill="#9fe9ff" filter="url(#g6)" opacity="0.8"/>' for k in range(3))


def v_worlds(cv, rnd):       # a globe on a stack of books, a festival lantern
    for i, (col, w) in enumerate([("#3f7fb0", 30), ("#c8423a", 26), ("#e2a33b", 28)]):
        y = DESK - 2 - i * 2
        cv.rect(36 - w / 2, y, 36 + w / 2, y + 2, col)
        cv.rect(36 - w / 2, y, 36 + w / 2, y + 1, "#f2e8d6" if i == 1 else col)
    cv.rect(31, DESK - 8, 41, DESK - 6, "#a07a4a")
    cv.rect(35, DESK - 11, 37, DESK - 8, "#a07a4a")
    GX, GY, GR = 36, 17, 12
    for y in range(GY - GR, GY + GR):
        for x in range(GX - GR, GX + GR):
            dx, dy = (x + 0.5 - GX) / GR, (y + 0.5 - GY) / GR
            if dx * dx + dy * dy > 1:
                continue
            nz = math.sqrt(1 - dx * dx - dy * dy)
            lum = (-0.5 * dx - 0.6 * dy + 0.6 * nz + 0.8) / 1.9
            land = math.sin(x * 0.55 + 1.3) + math.sin(y * 0.7 + x * 0.2) + 0.6 * math.sin(x * 0.3 - y * 0.5) > 0.9
            pal = ["#7a3f7a", "#b45a92", "#e486ae", "#ffc0d8"] if land else ["#1c2e5a", "#24477a", "#2f6a96", "#4a9ab8", "#8ad6e0"]
            cv.put(x, y, pk.ramp(pal, lum, x, y))
    for a in range(0, 360, 4):                     # brass meridian
        r = math.radians(a)
        if -100 < a - 180 < 100:
            cv.put(GX + (GR + 2) * math.cos(r), GY + (GR + 2) * math.sin(r), "#d9b45a")
    cv.rect(GX - 1, GY - GR - 3, GX + 1, GY - GR - 1, "#d9b45a")
    # hanging lantern
    cv.rect(62, 0, 63, 8, "#3a2a2e")
    cv.ellipse(62.5, 13, 4, 5, lambda x, y: "#ffcf6a" if x == 62 else "#e0402f")
    cv.rect(60, 7, 65, 8, "#3a2228")
    cv.rect(60, 18, 65, 19, "#3a2228")
    cv.rect(62, 19, 63, 22, "#ffcf6a")
    return (f'<circle cx="{36 * C}" cy="{17 * C}" r="70" fill="#8ad6e0" fill-opacity="0.16" filter="url(#g15)"/>'
            f'<circle cx="{62.5 * C}" cy="{13 * C}" r="34" fill="#ff8a5a" fill-opacity="0.45" filter="url(#g15)"><animate attributeName="fill-opacity" values="0.45;0.25;0.45" dur="3s" repeatCount="indefinite"/></circle>')


def v_start(cv, rnd):        # a phone on a stand with the first word sent, the cat watching it
    cv.rect(22, 4, 42, DESK - 2, "#141018")
    cv.rect(23, 6, 41, DESK - 5, "#1a1d32")
    cv.rect(29, 5, 35, 6, "#2a2434")
    for k, w in enumerate([12, 9]):
        cv.ellipse(25.5, 9.5 + k * 5, 1.4, 1.4, "#ffb7d6")
        cv.rect(28, 8 + k * 5, 28 + w, 11 + k * 5, "#d85a8e")
        for xx in range(30, 26 + w):
            if (xx + k) % 4:
                cv.put(xx, 9 + k * 5, "#ffd6e6")
    cv.rect(28, 22, 40, 28, "#3fa9bd")             # the player's bubble, text drawn as vector
    cv.rect(20, DESK - 2, 44, DESK, "#3a3446")
    # cat
    CX, CY = 56, DESK

    def cat():
        cv.ellipse(CX, CY - 5, 6, 6, "#140c14")
        cv.ellipse(CX - 1, CY - 13, 4, 3.6, "#140c14")
        cv.poly([(CX - 5, CY - 14), (CX - 4.5, CY - 19), (CX - 2, CY - 15)], "#140c14")
        cv.poly([(CX + 3, CY - 14), (CX + 2.5, CY - 19), (CX, CY - 15)], "#140c14")
        for k in range(9):
            cv.put(CX + 6 + (1 if k > 3 else 0) + (1 if k > 6 else 0), CY - 1 - k * 0.5 - (k > 5) * k * 0.3, "#140c14")
    silhouette_rim(cv, cat, "#7fe6f0", "#4aa8c0", side=-1)
    cv.put(CX - 3, CY - 13, "#9fe9ff")
    return (f'<ellipse cx="{32 * C}" cy="{20 * C}" rx="90" ry="80" fill="#6fd0ff" fill-opacity="0.18" filter="url(#g15)"/>'
            + text(34 * C, 26.6 * C, "开局", 15, "#ffffff", 800, "middle", 1))


def v_install(cv, rnd):      # an opened parcel with the skill inside
    BX0, BX1, BY = 8, 48, 22
    cv.rect(BX0, BY, BX1, DESK, lambda x, y: pk.ramp(["#8a5a32", "#a8723e", "#c48c50"], 0.75 - (y - BY) / 30 - (0.2 if x > BX1 - 6 else 0), x, y))
    cv.poly([(BX0, BY), (BX0 - 6, BY - 6), (BX0 + 12, BY - 7), (BX0 + 16, BY)], "#d29c5e")
    cv.poly([(BX1, BY), (BX1 + 5, BY - 7), (BX1 - 12, BY - 8), (BX1 - 16, BY)], "#b8824a")
    cv.rect(BX0 + 14, BY - 4, BX1 - 14, BY, "#3a2a40")            # the dark inside
    cv.rect(BX0 + 15, BY - 9, BX0 + 25, BY - 1, "#ffe9a8")         # a glowing card standing in the box
    cv.rect(BX0 + 16, BY - 8, BX0 + 24, BY - 7, "#ff9ac2")
    cv.rect(BX0 + 16, BY - 5, BX0 + 22, BY - 4, "#c8a870")
    cv.rect(BX0, BY, BX1, BY + 2, "#e2c27a")                       # tape
    cv.rect(BX0 + 3, 27, BX1 - 3, 36, "#f4ecdc")                   # label
    cv.rect(BX0 + 3, 27, BX1 - 3, 28, "#ffffff")
    cv.text("SKILL", BX0 + 6, 28, "#c9367e")
    plant(cv, 60, DESK)
    mug(cv, 68, DESK)
    return (f'<ellipse cx="{28 * C}" cy="{17 * C}" rx="60" ry="40" fill="#ffe9a8" fill-opacity="0.4" filter="url(#g15)"><animate attributeName="fill-opacity" values="0.4;0.15;0.4" dur="3s" repeatCount="indefinite"/></ellipse>'
            f'<g shape-rendering="crispEdges">{steam(69, DESK - 8)}</g>')


# ================================================================ world wall
REGIONS = [
    ("历史风云", "#8c7a9e", [("坊门落锁后", "盛唐 · 长安", 1), ("幕末町屋与道场", "1863 · 京都", 1), ("洋裁町", "1881 · 横滨", 1),
                          ("民国报馆与手艺街", "1926 · 通商口岸", 1), ("在册", "1928 · 芝加哥", 1), ("喫茶街", "1987 · 东京近郊", 1),
                          ("长明古刹", "明末 · 雪夜孤寺", 1), ("法租界暗房", "1940 · 上海", 1), ("黑石古堡", "维多利亚晚期", 1),
                          ("长安洗冤局", "唐末 · 长安暴雨", 1), ("玉门关外黑风暴", "开元 · 河西走廊", 1), ("紫禁城封禁夜", "架空皇朝 · 大雪", 1),
                          ("百乐门香闺", "1941 · 上海孤岛", 1), ("凡尔赛更衣室", "1789 · 化装舞会", 1), ("红叶别庄", "昭和初 · 伊豆", 1),
                          ("梅雨古刹", "大正 · 鞍马山", 1), ("断壁古堡", "19 世纪 · 黑森林", 1)]),
    ("都市暗流", "#9a7394", [("月份牌", "1930s · 片厂与舞厅", 1), ("雾都号牌", "蒸汽浴场", 1), ("第七任", "虚拟主播公司", 1), ("后巷三楼", "写真与绳艺", 1),
                          ("雪夜汤宿", "1980s · 封山温泉", 1), ("八十八层封楼夜", "暴雨 · 顶层", 1), ("黑龙丸", "极道 · 暴风雨游艇", 1),
                          ("银座暴雨夜", "地下政商俱乐部", 1), ("东京湾地下赌场", "1990s · 极道若头", 1), ("雨夜守灵", "极道 · 少夫人", 1),
                          ("雪山木屋", "极道 · 暴风雪", 1), ("油麻地跌打医馆", "1980s · 八号风球", 1), ("特搜审讯室", "警视厅 · 单向镜", 1),
                          ("万米高空", "女总裁 · 雷暴", 1), ("公海蜜月套房", "1990s · 间谍邮轮", 1), ("货舱密审", "女特工 · 冰海", 1),
                          ("冻土快车", "1978 · 中苏边境", 1)]),
    ("当代市井", "#6f78a0", [("港口夜班", "1998 · 集装箱码头", 1), ("世纪末网吧", "1999 · 通宵网吧", 1), ("半条街", "拆迁前的夏天", 1),
                          ("最后一期", "停刊前的报社", 1), ("成年创作者与艺术季", "旧厂区艺术季", 1), ("台风断电夜", "老街 · 青梅竹马", 1),
                          ("暴风雨游艇", "名门长媳 · 套房", 1), ("六叠合租", "高円寺 · 梅雨季", 1), ("下町薄墙", "1990s · 隔壁主妇", 1),
                          ("山宅守灵", "昭和 · 素白未亡人", 1), ("雪困柴油车", "荒原 · 女上司", 1), ("台风棋室", "千驮谷 · 女棋圣", 1),
                          ("沉船压载舱", "邮轮底舱 · 千金", 1), ("旧校舍地窖", "2000s · 学生会长", 1), ("财阀金库", "首尔 · 断电夜", 1),
                          ("午夜催眠诊室", "研究所 · 顶层", 1), ("隔离病栋", "1990s · 负压病区", 1)]),
    ("末世与蒸汽", "#8579b0", [("夜班修理局", "近未来巨城", 1), ("检疫环", "边境空间站", 1), ("修补集市", "灾后十五年", 1), ("寒冬避难所公共生活", "长冬第三年", 1),
                         ("酸雨沉船城", "浩劫后 · 神经诊所", 1), ("时停实验室", "量子实验室 · 午夜", 1), ("酸雨避难所", "核冬天 · 女军医", 1),
                         ("雪夜战壕", "帝国末年 · 冻土", 1), ("绝壁要塞", "蒸汽装甲战争", 1), ("浮空城禁术工房", "魔导蒸汽 · 雷暴", 1),
                         ("机械马戏", "每城只停七天", 1)]),
    ("异界幻想", "#76708e", [("鬼市商路", "大漠 · 千佛窟", 1), ("旧町神怪与灯会", "河湾 · 灯会", 1), ("山下镇", "仙侠 · 山脚集镇", 1),
                          ("勇者退休以后", "魔王死后十年", 1), ("登记城", "灵气复苏十年", 1), ("大圣堂告解夜", "圣女与封印学者", 1),
                          ("枯枝神殿", "迷雾纪元末", 1), ("公会暗室", "剑与魔法 · 边境", 1), ("迷宫深层", "坍塌的安全区", 1),
                          ("巨龙坠落之堑", "屠龙决死前夜", 1), ("深渊要塞地牢", "女骑士长 · 血月", 1), ("地牢夜盟", "落难女骑士", 1),
                          ("禁书库炼药台", "魔导院 · 秘药", 1), ("遗迹石室", "黑暗精灵斥候", 1), ("破结界神社", "巫女长 · 神乐铃", 1),
                          ("神乐殿夜祓", "明治 · 斩鬼巫女", 1)]),
]


def worlds():
    ROWS = max(len(w) for _, _, w in REGIONS)
    BY1 = max(210, 66 + ROWS * 24 + 6)
    GW, GH = 300, BY1 + 12
    rnd = random.Random(31)
    cv = pk.Canvas(GW, GH)
    BX0, BY0 = 8, 48
    BX1 = 292
    cv.rect(BX0 - 3, BY0 - 3, BX1 + 3, BY1 + 3, "#4a2e26")         # frame
    cv.rect(BX0 - 3, BY0 - 3, BX1 + 3, BY0 - 2, "#8a5c44")
    cv.rect(BX0 - 1, BY0 - 1, BX1 + 1, BY0, "#2a1a16")
    cv.rect(BX0, BY0, BX1, BY1, "#9a6b45")
    for _ in range(2600):                                         # cork grain
        x, y = rnd.randrange(BX0, BX1), rnd.randrange(BY0, BY1)
        cv.put(x, y, rnd.choice(["#875c3a", "#ab7a50", "#8f6240"]))
    cv.rect(BX0, BY0, BX1, BY0 + 2, "#6a4630")                     # shadow under the top frame
    cv.rect(BX0, BY0, BX0 + 2, BY1, "#7a5236")
    over = []
    pins = []
    colw = (BX1 - BX0 - 8) / 5
    for i, (region, rc, worlds_) in enumerate(REGIONS):
        cx0 = BX0 + 4 + i * colw
        tx0, tx1 = int(cx0 + 3), int(cx0 + colw - 3)
        cv.rect(tx0 + 1, 53, tx1 + 1, 61, "#5a3a26")                # tape shadow
        cv.rect(tx0, 52, tx1, 60, rc)
        cv.rect(tx0, 52, tx1, 53, "#ffffff")
        cv.rect(tx0, 53, tx1, 54, rc)
        for y in range(52, 60, 2):                                  # torn tape ends
            cv.put(tx0, y, "#9a6b45")
            cv.put(tx1 - 1, y + 1, "#9a6b45")
        over.append(text((tx0 + tx1) / 2 * C, 58.4 * C, region, 18, "#ffffff", 800, "middle", 3, SANS, 'stroke="#2a1a24" stroke-width="3" paint-order="stroke"'))
        for j, (name, era, open_) in enumerate(worlds_):
            y0 = 66 + j * 24
            x0 = int(cx0 + 4 + rnd.choice([-1, 0, 1]))
            x1 = x0 + int(colw) - 8
            y1 = y0 + 20
            paper = "#f6eedd" if open_ else "#cbbfae"
            cv.rect(x0 + 1, y0 + 1, x1 + 1, y1 + 1, "#5a3a26")
            cv.rect(x0, y0, x1, y1, paper)
            cv.rect(x0, y0, x1, y0 + 1, "#fffaf0" if open_ else "#dcd2c2")
            cv.rect(x0, y0, x0 + 2, y1, rc if open_ else "#9a8e86")
            cv.rect(x1 - 3, y1 - 3, x1, y1, "#e6dcc8" if open_ else "#b8ac9c")   # dog-ear
            cv.put(x1 - 3, y1 - 3, "#5a3a26")
            px = (x0 + x1) // 2
            pins.append((px, y0 + 1, open_))
            ink = "#2a1e2e" if open_ else "#5e5260"
            over.append(text((x0 + 4.5) * C, (y0 + 10) * C, name, 17 if len(name) < 9 else 15.5, ink, 800, "start", 0.5 if len(name) < 9 else 0))
            over.append(text((x0 + 4.5) * C, (y0 + 16.6) * C, era, 13, "#7a6a72" if open_ else "#7e7278", 600, "start", 0.5))
            if open_:
                over.append(f'<rect x="{(x1 - 14) * C}" y="{(y0 - 2) * C}" width="{14 * C}" height="{5 * C}" rx="3" fill="#ff6fae" transform="rotate(4 {(x1 - 7) * C} {y0 * C})"/>'
                            + text((x1 - 7) * C, (y0 + 2) * C, "已开放", 12.5, "#ffffff", 800, "middle", 1, SANS, f'transform="rotate(4 {(x1 - 7) * C} {y0 * C})"'))
    # a polaroid of the lantern festival, a ticket stub, a note
    SHORT = 66 + len(REGIONS[3][2]) * 24 + 6
    PX0, PY0 = int(BX0 + 4 + 3 * colw + 10), SHORT + 38
    cv.rect(PX0 + 1, PY0 + 1, PX0 + 35, PY0 + 37, "#5a3a26")
    cv.rect(PX0, PY0, PX0 + 34, PY0 + 36, "#f6f2ea")
    cv.vgrad(PX0 + 3, PY0 + 3, PX0 + 31, PY0 + 27, ["#1d2350", "#3a2a66", "#6a3778", "#a2477e"])
    cv.line(PX0 + 3, PY0 + 8, PX0 + 31, PY0 + 6, "#2a1e3a")
    for k in range(4):
        lx, ly = PX0 + 6 + k * 7, PY0 + 9 - k * 0.5
        cv.ellipse(lx, ly + 3, 2.4, 3, lambda x, y, lx=lx: "#ffcf6a" if x == int(lx) else "#e0402f")
    cv.poly([(PX0 + 3, PY0 + 22), (PX0 + 9, PY0 + 17), (PX0 + 15, PY0 + 21), (PX0 + 22, PY0 + 16), (PX0 + 31, PY0 + 21), (PX0 + 31, PY0 + 27), (PX0 + 3, PY0 + 27)], "#1a1228")
    pins.append((PX0 + 17, PY0 + 1, False))
    NX0, NY0 = int(BX0 + 4 + 3 * colw + 5), SHORT
    cv.rect(NX0 + 1, NY0 + 1, NX0 + int(colw) - 7, NY0 + 31, "#5a3a26")
    cv.rect(NX0, NY0, NX0 + int(colw) - 8, NY0 + 30, "#ffe9a0")
    cv.rect(NX0, NY0, NX0 + int(colw) - 8, NY0 + 2, "#f2d880")
    pins.append((NX0 + int(colw) // 2 - 4, NY0 + 1, False))
    for k, line in enumerate(["想去的地方", "不在板上？", "说“自定义世界”"]):
        over.append(text((NX0 + 4) * C, (NY0 + 10 + k * 7) * C, line, 16, "#5a3a20", 800, "start", 1, SANS))
    TX0, TY0 = int(BX0 + 4 + 3 * colw + 6), SHORT + 82
    cv.rect(TX0 + 1, TY0 + 1, TX0 + 43, TY0 + 13, "#5a3a26")
    cv.rect(TX0, TY0, TX0 + 42, TY0 + 12, "#d85a8e")
    for y in range(TY0, TY0 + 12, 2):
        cv.put(TX0 + 35, y, "#f6eedd")
    cv.text("ADMIT", TX0 + 3, TY0 + 3, "#ffe3f0")
    cv.text("1", TX0 + 37, TY0 + 3, "#ffe3f0")
    for px, py, open_ in pins:
        cv.rect(px - 1, py - 1, px + 2, py + 2, "#ff6fae" if open_ else "#8a8094")
        cv.put(px - 1, py - 1, "#ffd6e8" if open_ else "#c0b8c8")
        cv.put(px + 1, py + 2, "#5a3a26")
    pin_glow = "".join(f'<circle cx="{(px + 0.5) * C}" cy="{(py + 0.5) * C}" r="12" fill="#ff6fae" fill-opacity="0.5" filter="url(#g6)">'
                       f'<animate attributeName="fill-opacity" values="0.6;0.2;0.6" dur="{rnd.uniform(2, 3.5):.1f}s" begin="-{rnd.uniform(0, 2):.1f}s" repeatCount="indefinite"/></circle>'
                       for px, py, o in pins if o)
    # legend pins
    cv.rect(124, 37, 127, 40, "#ff6fae")
    cv.put(124, 37, "#ffd6e8")
    body = f'''    <g shape-rendering="crispEdges">{cv.emit(C)}</g>
    {pin_glow}
    {"".join(over)}
    {neon(600, 82, "78 个世界", 52, "middle", "#a29dab", "#ecebef", flicker=True)}
    {text(600, 122, "选一个直接开局，或者说“自定义世界”当场写一个", 21, SUBT, 600, "middle", 2)}
    {text(520, 159, "全部已开放，可直接开局", 16, "#ffd6e8", 700, "start", 1)}
    {text(BX1 * C, (BY1 + 9.5) * C, "名单会继续变长", 16, "#bfb2c8", 700, "end", 2)}'''
    doc("worlds.svg", GW * C, GH * C, "78 个世界",
        "内置世界钉在一块软木板上，分为历史风云、都市暗流、当代市井、末世与蒸汽、异界幻想五栏，全部已开放，可直接开局。", "", body)


# ================================================================ cassette shelf
ITEMS = [("390+", "地点"), ("470+", "NPC 角色"), ("400+", "玩家身份"), ("500+", "人物组合"), ("360+", "张力引擎"),
         ("490+", "日常活动"), ("470+", "压力事件"), ("1080+", "开场钩子"), ("550+", "中期转折"), ("680+", "规矩与风俗")]
TAPES = ["#8e5f78", "#4f6f80", "#8a7550", "#6a6290", "#87574f", "#5d7258", "#82607e", "#55628a", "#8a6a58", "#56786f"]


def inventory():
    GW, GH = 300, 128
    rnd = random.Random(41)
    cv = pk.Canvas(GW, GH)
    pic = crop((1410, 0, 1710, 95), 216 * C, 6 * C, 74 * C, 24 * C)
    over, reels = [], []
    for r in range(2):
        sy = 72 + r * 46                                            # shelf board y
        cv.rect(4, sy, 296, sy + 3, "#8a5c44")
        cv.rect(4, sy, 296, sy + 1, "#c08060")
        cv.rect(4, sy + 3, 296, sy + 4, "#2a1a16")
        for bx in (10, 288):
            cv.rect(bx, sy + 3, bx + 3, sy + 7, "#4a2e26")
        for i in range(5):
            k = r * 5 + i
            x0 = 8 + i * 58
            y0 = sy - 34
            x1, y1 = x0 + 52, sy
            body = TAPES[k]
            cv.rect(x0 + 1, y0 + 1, x1 + 1, y1, "#140d14")
            cv.rect(x0, y0, x1, y1, body)
            for (sx, sy2) in [(x0 + 2, y0 + 2), (x1 - 3, y0 + 2), (x0 + 2, y1 - 3), (x1 - 3, y1 - 3)]:
                cv.put(sx, sy2, "#2a2030")                         # screws
            cv.rect(x0 + 4, y0 + 3, x1 - 4, y0 + 19, "#221c28")      # label
            cv.rect(x0 + 4, y0 + 3, x1 - 4, y0 + 5, body)
            cv.rect(x0 + 4, y0 + 5, x1 - 4, y0 + 6, "#4a4054")
            cv.rect(x0 + 14, y0 + 20, x1 - 14, y0 + 27, "#1a1420")    # reel window
            cv.rect(x0 + 15, y0 + 20, x1 - 15, y0 + 26, "#3a2c3e")
            cv.rect(x0 + 21, y0 + 21, x1 - 21, y0 + 25, "#5a3a2e")   # tape between reels
            for rx in (x0 + 18, x1 - 18):
                cv.ellipse(rx, y0 + 23, 3.2, 3.2, "#f2e8d6")
                cv.rect(rx - 1, y0 + 22, rx + 1, y0 + 24, "#1a1420")
                reels.append((rx, y0 + 23))
            cv.poly([(x0 + 10, y1), (x0 + 13, y0 + 29), (x1 - 13, y0 + 29), (x1 - 10, y1)], "#2a2030")
            for hx in (x0 + 17, x1 - 18):
                cv.rect(hx, y1 - 3, hx + 2, y1 - 1, "#140d14")
            num, label = ITEMS[k]
            over.append(text((x0 + x1) / 2 * C, (y0 + 12.6) * C, num, 30, "#ffffff", 900, "middle", 1, SANS))
            over.append(text((x0 + x1) / 2 * C, (y0 + 17.6) * C, label, 15, SUBT, 800, "middle", 2))
    # spinning spokes as two alternating pixel frames
    spin = []
    for rx, ry in reels:
        a = "".join(f'<rect x="{(rx + dx) * C}" y="{(ry + dy) * C}" width="{C}" height="{C}"/>' for dx, dy in [(0, -2), (0, 1), (-2, 0), (1, 0)])
        b = "".join(f'<rect x="{(rx + dx) * C}" y="{(ry + dy) * C}" width="{C}" height="{C}"/>' for dx, dy in [(-2, -2), (1, 1), (-2, 1), (1, -2)])
        spin.append(f'<g fill="#8a7a6a">{a}<animate attributeName="opacity" values="1;0" dur="0.5s" calcMode="discrete" repeatCount="indefinite"/></g>'
                    f'<g fill="#8a7a6a" opacity="0">{b}<animate attributeName="opacity" values="0;1" dur="0.5s" calcMode="discrete" repeatCount="indefinite"/></g>')
    body = f'''    <g shape-rendering="crispEdges">{cv.emit(C)}</g>
    <rect x="{213 * C}" y="{3 * C}" width="{80 * C}" height="{30 * C}" fill="#17101a"/>
    {pic}
    <g shape-rendering="crispEdges">{"".join(spin)}</g>
    {"".join(over)}
    {neon(40, 82, "五千余项素材", 50, "start", "#a29dab", "#ecebef", flicker=True)}
    {text(42, 120, "地点、人物、钩子和规矩，每次开局都从同一个世界里组合", 20, SUBT, 600, "start", 1.5)}'''
    doc("inventory.svg", GW * C, GH * C, "五千余项素材",
        "一排磁带架上的十盒磁带，标签写着素材数量：390+ 地点、470+ NPC 角色、400+ 玩家身份、500+ 人物组合、360+ 张力引擎、490+ 日常活动、470+ 压力事件、1080+ 开场钩子、550+ 中期转折、680+ 规矩与风俗。", "", body)


banner("section-proof.svg", "体验切片", "真实会话交付实录", 1, (1180, 222, 1490, 352))          # the monitor
banner("section-why.svg", "为什么不会崩盘", "模型写故事，本地引擎守事实", 2, (70, 300, 470, 468))       # clock and desk
banner("section-worlds.svg", "内置世界库", "跨时代独立世界框架和五千余项素材", 3, (990, 0, 1390, 168))   # the city outside
banner("section-start.svg", "怎么开始", "不用记语法，直接说大白话", 4, (610, 190, 1050, 375))          # the guitar
banner("section-install.svg", "安装", "只需交给 AI 操作，原生 SKILL", 5, (1440, 280, 1800, 431))           # the laptop
worlds()
inventory()


def library():
    """The world-library banner, the corkboard and the cassette shelf stacked into one seamless picture: one wall, one frame,
    one vignette; the banner's picture crop also melts into the wall at its bottom edge."""
    names = ["section-worlds.svg", "worlds.svg", "inventory.svg"]
    W = PARTS[names[0]][0]
    H = sum(PARTS[n][1] for n in names)
    BHPX = PARTS[names[0]][1]
    defs = "".join(PARTS[n][2] for n in names) + (
        f'<linearGradient id="seamg" x1="0" y1="{BHPX - 60}" x2="0" y2="{BHPX}" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#000"/><stop offset="1" stop-color="#fff"/></linearGradient>'
        f'<mask id="seam"><rect width="440" height="{BHPX}" fill="url(#seamg)"/></mask>')
    y, parts = 0, []
    for n in names:
        parts.append(f'    <g transform="translate(0 {y})">{PARTS[n][3]}</g>')
        y += PARTS[n][1]
    parts.insert(1, f'    <g mask="url(#seam)">{background("world-library.svg", W, H)}</g>')
    doc("world-library.svg", W, H, "内置世界库",
        "内置世界库：跨时代独立世界框架和五千余项素材。78 个世界钉在一块软木板上，分为历史风云、都市暗流、当代市井、末世与蒸汽、异界幻想五栏，全部已开放，可直接开局。"
        "下方磁带架写着五千余项素材：390+ 地点、470+ NPC 角色、400+ 玩家身份、500+ 人物组合、360+ 张力引擎、490+ 日常活动、470+ 压力事件、1080+ 开场钩子、550+ 中期转折、680+ 规矩与风俗。",
        defs, "\n".join(parts))


library()


# ================================================================ architecture board
KINDS = {   # body, top highlight, accent bar, title ink, subtitle ink
    "run": ("#3e3850", "#6a6284", "#a874ff", "#efeaf5", SUBT),
    "data": ("#2c4450", "#4f6f80", "#9fe9ff", "#e6fbff", "#a9cfd9"),
    "note": ("#f6eedd", "#fffaf0", "#ff6fae", "#2a1e2e", "#7a6a72"),
}
WIRE, DATA_WIRE = "#c4bfcc", "#9fe9ff"


def architecture():
    """How one turn travels: the player talks to the host, the host calls the local runtime with JSON, the runtime's layers
    hand down to the pure domain and write one SQLite transaction in the user's data folder; world packs are compiled ahead."""
    GW, GH = 300, 228
    cv = pk.Canvas(GW, GH)
    over, packets = [], []

    def panel(x0, y0, x1, y1, kind, title, sub):
        body, hi, acc, ink, subink = KINDS[kind]
        cv.rect(x0 + 1, y0 + 1, x1 + 1, y1 + 1, "#140d14")
        cv.rect(x0, y0, x1, y1, body)
        cv.rect(x0, y0, x1, y0 + 1, hi)
        cv.rect(x0, y0, x0 + 2, y1, acc)
        for sx, sy in [(x1 - 2, y0 + 2), (x1 - 2, y1 - 3)]:
            cv.put(sx, sy, "#2a2030" if kind != "note" else "#c8bca8")
        cx = (x0 + 2 + x1) / 2 * C
        over.append(text(cx, (y0 + 6.2) * C, title, 21, ink, 800, "middle", 1))
        over.append(text(cx, (y0 + 11) * C, sub, 15, subink, 600, "middle", 1))

    def wire(x0, y0, x1, y1, col=WIRE):
        """An axis-aligned 1-cell wire from (x0, y0) to (x1, y1) with a pixel arrowhead at the far end."""
        if y0 == y1:
            d = 1 if x1 > x0 else -1
            cv.rect(min(x0, x1), y0, max(x0, x1), y0 + 1, col)
            for k in range(3):
                cv.rect(x1 - d * (k + 1), y0 - k, x1 - d * (k + 1) + 1, y0 + k + 1, col)
        else:
            d = 1 if y1 > y0 else -1
            cv.rect(x0, min(y0, y1), x0 + 1, max(y0, y1), col)
            for k in range(3):
                cv.rect(x0 - k, y1 - d * (k + 1), x0 + k + 1, y1 - d * (k + 1) + 1, col)
        a, b = ((x0 + 0.5) * C, (y0 + 0.5) * C), ((x1 + 0.5) * C, (y1 + 0.5) * C)
        dur = max(1.2, math.hypot(b[0] - a[0], b[1] - a[1]) / 90)
        packets.append(f'<rect x="-4" y="-4" width="8" height="8" fill="{col}" filter="url(#g6)" opacity="0.9">'
                       f'<animateMotion path="M{a[0]:.0f} {a[1]:.0f}L{b[0]:.0f} {b[1]:.0f}" dur="{dur:.1f}s" begin="-{len(packets) * 0.37 % dur:.1f}s" repeatCount="indefinite"/></rect>'
                       f'<rect x="-2" y="-2" width="4" height="4" fill="#ffffff">'
                       f'<animateMotion path="M{a[0]:.0f} {a[1]:.0f}L{b[0]:.0f} {b[1]:.0f}" dur="{dur:.1f}s" begin="-{(len(packets) - 1) * 0.37 % dur:.1f}s" repeatCount="indefinite"/></rect>')

    # the runtime case, with a strip of tape for its label
    FX0, FY0, FX1, FY1 = 6, 86, 200, 184
    cv.rect(FX0 + 1, FY0 + 1, FX1 + 2, FY1 + 2, "#140d14")
    cv.rect(FX0, FY0, FX1 + 1, FY1 + 1, "#5a5274")
    cv.rect(FX0 + 1, FY0 + 1, FX1, FY1, "#221c2e")
    cv.rect(FX0 + 1, FY0 + 1, FX1, FY0 + 2, "#6a6284")
    for sx, sy in [(FX0 + 2, FY0 + 3), (FX1 - 2, FY0 + 3), (FX0 + 2, FY1 - 2), (FX1 - 2, FY1 - 2)]:
        cv.put(sx, sy, "#8a82a0")
    cv.rect(15, FY0 - 4, 113, FY0 + 4, "#8579b0")
    cv.rect(15, FY0 - 4, 113, FY0 - 3, "#ffffff")
    over.append(text(64 * C, (FY0 + 1.8) * C, "runtime/ · 只用 Python 标准库", 17, "#ffffff", 800, "middle", 2, SANS,
                     'stroke="#2a1a24" stroke-width="3" paint-order="stroke"'))

    panel(8, 50, 56, 64, "note", "玩家", "说一句话")
    panel(80, 50, 180, 64, "note", "Agent 宿主 + 模型", "写正文 · 决定提交哪些操作")
    panel(222, 50, 292, 64, "note", "SKILL.md", "规则 + references")
    panel(14, 94, 192, 108, "run", "adapters/cli", "解析参数 · 输出 JSON 信封 · 退出码")
    panel(14, 116, 192, 130, "run", "application", "唯一写入口：幂等 · revision 检查 · 一次写一个事务")
    panel(14, 138, 70, 152, "run", "content", "只读世界包")
    panel(75, 138, 131, 152, "run", "projections", "上下文 · 状态")
    panel(136, 138, 192, 152, "run", "persistence", "SQLite 仓储")
    panel(14, 160, 192, 174, "run", "domain", "纯函数：操作校验 · 时间结算 · 开局 · 随机派生")
    panel(222, 138, 292, 152, "data", "用户数据目录", "SQLite 存档库")
    panel(8, 198, 70, 212, "data", "content/", "编译好的世界包")
    panel(116, 198, 180, 212, "note", "tools/", "编译 · 校验 · 生成参考")
    panel(222, 198, 292, 212, "note", "content-src/", "世界源文件")

    NX0, NY0, NX1, NY1 = 224, 90, 290, 128                        # a sticky note with the three promises
    cv.rect(NX0 + 1, NY0 + 1, NX1 + 1, NY1 + 1, "#140d14")
    cv.rect(NX0, NY0, NX1, NY1, "#ffe9a0")
    cv.rect(NX0, NY0, NX1, NY0 + 2, "#f2d880")
    cv.rect(NX1 - 4, NY1 - 4, NX1, NY1, "#e6cf80")
    cv.rect(256, NY0 - 1, 259, NY0 + 2, "#ff6fae")
    cv.put(256, NY0 - 1, "#ffd6e8")
    for k, line in enumerate(["一回合 = 一次事务", "重试不会重复推进", "同一种子，同一结果"]):
        over.append(text((NX0 + 5) * C, (NY0 + 13 + k * 9) * C, line, 17, "#5a3a20", 800, "start", 1))
    wire(57, 57, 79, 57)
    wire(221, 57, 182, 57)
    over.append(text(201 * C, 54 * C, "每回合加载", 14, "#bfb2c8", 700, "middle", 1))
    wire(120, 65, 120, 93)
    wire(140, 93, 140, 66)
    over.append(text(117 * C, 81 * C, "JSON 调用", 15, "#d9d2e2", 700, "end", 1))
    over.append(text(143 * C, 81 * C, "结果 + 下一回合上下文", 15, "#d9d2e2", 700, "start", 1))
    wire(103, 109, 103, 115)
    for x in (42, 103, 164):
        wire(x, 131, x, 137)
    wire(72, 131, 72, 159)
    wire(193, 145, 221, 145, DATA_WIRE)
    wire(221, 205, 182, 205)
    wire(115, 205, 72, 205)
    wire(39, 197, 39, 186, DATA_WIRE)
    over.append(text(43 * C, 192.4 * C, "开局时读取", 14, "#a9cfd9", 700, "start", 1))

    for k, (kind, label) in enumerate([("note", "宿主与开发工具"), ("run", "运行时分层"), ("data", "数据")]):
        x = 8 + k * 62
        cv.rect(x, 219, x + 4, 223, KINDS[kind][0])
        cv.rect(x, 219, x + 1, 223, KINDS[kind][2])
        over.append(text((x + 7) * C, 222.6 * C, label, 14, "#bfb2c8", 700, "start", 1))

    body = f'''    <g shape-rendering="crispEdges">{cv.emit(C)}</g>
    <g shape-rendering="crispEdges">{"".join(packets)}</g>
    {"".join(over)}
    {neon(600, 82, "SKILL架构", 52, "middle", "#a29dab", "#ecebef", flicker=True)}
    {text(600, 122, "无需理会，当正常SKILL使用就行", 21, SUBT, 600, "middle", 2)}
    {dotline(GW * C, 0, 2.4)}'''
    doc("architecture.svg", GW * C, GH * C, "SKILL架构",
        "玩家对 Agent 宿主说话，宿主按 SKILL.md 的规则写正文，用 JSON 调用本地运行时并拿回结果和下一回合上下文。"
        "运行时只用 Python 标准库，分 adapters/cli、application、content、projections、persistence、domain 六层：application 是唯一写入口，"
        "domain 只放纯函数，persistence 把每一回合写成一次 SQLite 事务，存进用户数据目录。世界源文件由 tools 编译成只读世界包，开局时读取。", "", body)


architecture()
