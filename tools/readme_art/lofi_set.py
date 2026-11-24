"""Lo-fi pixel README set to match the bedroom hero: five section banners, the VHS tape wall, a genre counter, a cassette shelf of materials.
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
GLOW, CORE, SUBT = "#c48aff", "#fff7fc", "#d4cce0"        # bright lavender glow, warm white type, soft lavender-grey subtitle
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
    anim = ('<animate attributeName="opacity" values="1;1;0.68;1;1;0.82;1" keyTimes="0;0.8;0.81;0.83;0.93;0.94;1" dur="6s" repeatCount="indefinite"/>'
            if flicker else "")
    d = max(2, round(size / 18))                                   # deep dark shadow so bright type pops cleanly off the dusk wall
    return (f'<g>{anim}' + text(x + d, y + d, s, size, "#160a22", 800, anchor, 3, SANS)
            + text(x, y, s, size, col, 800, anchor, 3, SANS, 'filter="url(#g8)" opacity="0.9"')
            + text(x, y, s, size, core, 800, anchor, 3, SANS, f'stroke="{col}" stroke-width="{size / 44:.1f}" paint-order="stroke"') + '</g>')


DEFS = '''<pattern id="wallp" width="48" height="8" patternUnits="userSpaceOnUse"><rect width="48" height="8" fill="#2d2131"/><rect x="36" width="12" height="8" fill="#302434"/></pattern>
    <filter id="g6" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
    <filter id="g8" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="8"/></filter>
    <filter id="g15" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="15"/></filter>
    <filter id="g30" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="30"/></filter>
    <linearGradient id="lineg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#a874ff"/><stop offset="0.5" stop-color="#ff6fae"/><stop offset="1" stop-color="#a874ff"/></linearGradient>
    <linearGradient id="glint" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset="0.5" stop-color="#ffffff" stop-opacity="0.55"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
    <radialGradient id="vig" cx="0.5" cy="0.5" r="0.8"><stop offset="0.62" stop-color="#05020a" stop-opacity="0"/><stop offset="1" stop-color="#05020a" stop-opacity="0.48"/></radialGradient>'''


def crop(box, x, y, w, h, fade=None, vfade=False):
    """A losslessly re-encoded crop of the user's picture placed at (x, y, w, h); fade melts its right edge; vfade melts its bottom edge."""
    buf = io.BytesIO()
    PIC.crop(box).save(buf, "WEBP", lossless=True)
    href = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    img = f'<image href="{href}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" style="image-rendering:pixelated"/>'
    if not fade:
        return img
    fid, t = fade
    if not vfade:
        mid = round((t + 1.0) / 2, 2)
        return (f'<defs><linearGradient id="{fid}g" x1="{x}" y1="0" x2="{x + w}" y2="0" gradientUnits="userSpaceOnUse">'
                f'<stop offset="0" stop-color="#fff"/><stop offset="{t}" stop-color="#fff"/><stop offset="{mid}" stop-color="#888"/><stop offset="1" stop-color="#000"/></linearGradient>'
                f'<mask id="{fid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{fid}g)"/></mask></defs>'
                f'<g mask="url(#{fid})" opacity="0.88">{img}</g>')
    return (f'<defs>'
            f'<linearGradient id="{fid}hg" x1="{x}" y1="0" x2="{x + w}" y2="0" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="#fff"/><stop offset="{t}" stop-color="#fff"/><stop offset="0.68" stop-color="#888"/><stop offset="0.93" stop-color="#000"/><stop offset="1" stop-color="#000"/></linearGradient>'
            f'<linearGradient id="{fid}vg" x1="0" y1="{y}" x2="0" y2="{y + h}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="#fff"/><stop offset="0.48" stop-color="#fff"/><stop offset="0.72" stop-color="#8c8c8c"/><stop offset="0.88" stop-color="#262626"/><stop offset="0.96" stop-color="#000"/><stop offset="1" stop-color="#000"/></linearGradient>'
            f'<mask id="{fid}h"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{fid}hg)"/></mask>'
            f'<mask id="{fid}v"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#{fid}vg)"/></mask></defs>'
            f'<g mask="url(#{fid}h)" opacity="0.88"><g mask="url(#{fid}v)">{img}</g></g>')


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


DUSK = [(17, 13, 34), (24, 17, 48), (33, 21, 60), (44, 25, 70), (55, 27, 73), (63, 27, 72), (72, 29, 75)]


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


VX = 113                    # where a banner's vignette starts, between the picture crop and the title


def banner(name, title, sub, seed, box, vig):
    rnd = random.Random(seed)
    cv = pk.Canvas(BW, BH)
    vc = pk.Canvas(80, BH)                                          # the section's own little object on a wall shelf
    extra = vig(vc, rnd)
    vc.rect(0, DESK, 78, DESK + 2, "#6a4430")
    vc.rect(0, DESK, 78, DESK + 1, "#9a6a48")
    vc.rect(0, DESK + 2, 78, DESK + 3, "#140c10")
    for bx in (6, 68):
        vc.poly([(bx, DESK + 2), (bx + 4, DESK + 2), (bx, DESK + 6)], "#3a3440")
    core_layers = f'''    <ellipse cx="{BW * C - 280}" cy="98" rx="290" ry="70" fill="{GLOW}" fill-opacity="0.16" filter="url(#g30)"/>
    <g shape-rendering="crispEdges">{cv.emit(C)}</g>
    <g transform="translate({VX * C} 0)"><g shape-rendering="crispEdges">{vc.emit(C)}</g>{extra}</g>
    {neon(BW * C - 46, 96, title, 48, "end", GLOW, CORE, flicker=True)}
    {text(BW * C - 48, 138, sub, 20, SUBT, 600, "end", 1.8)}'''
    body = f'''    {crop(box, 0, 0, 480, BH * C, ("fade", 0.38))}
{core_layers}
    {dotline(BW * C, 0, seed * 0.9)}'''
    doc(name, BW * C, BH * C, title, sub, "", body)
    PARTS[name + ":lib"] = (BW * C, BH * C, "", f"    {crop(box, 0, 0, 480, BH * C, ('libfade', 0.36), vfade=True)}\n{core_layers}")


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
    ("宫廷与江湖", "#8c7a9e", [
        "深巷闭户俏寡妇", "风雪古刹借宿夜", "大理寺提刑女官", "紫禁封宫夜", "孤烽燧的和亲公主", "破庙拔毒女刺客", "雪封行宫长皇女", "冰窖验骨女仵作", "摘星楼漏刻女官", "画舫琵琶女行首"
    ]),
    ("仙侠与志怪", "#768a9e", [
        "未摘狐面的妖女", "鬼市掌灯引路娘", "仙山客栈老板娘", "走火入魔女剑仙", "守陵村的剑巫女"
    ]),
    ("和风与神社", "#9e6b78", [
        "幕末微醺的艺伎", "横滨量体华族妻", "退魔巫女破戒夜", "守至破晓女剑士", "破产名门女家督", "百日祭的新寡当主", "受困神龛大巫女", "华族洋馆清算夜", "神乐夜的伏魔殿"
    ]),
    ("清末民国", "#8a7a62", [
        "报馆截稿女主编", "名册除名落魄女", "月份牌上的女郎", "霞飞路暗房女谍", "76号冷艳女处长", "流沙殿摸金女魁", "督军千金下金库", "天池采参女把头"
    ]),
    ("欧陆古典", "#7e6f8e", [
        "雾夜马车俏贵妇", "发条马戏的伶人", "递辞呈的女仆长", "掌权的冷艳女管家", "公爵夫人更衣室", "告解窗前小修女", "失态的首席舞姬"
    ]),
    ("邻里与屋檐下", "#8c7d70", [
        "喫茶街的熟客账", "世纪末网吧包厢", "封山私汤若女将", "藏离婚书的人妻", "六叠合租俏青梅", "薄墙那头的主妇", "断桥守灵未亡人", "交班十分钟的账", "三楼暗室的绳结", "拆迁前的老街坊", "悬空单轨的辣妹", "退租夜的室友", "风吕屋少老板娘", "首发前夜女店长", "女仆咖啡的台柱", "冷柜前夜班店员"
    ]),
    ("百工与夜铺", "#6d8478", [
        "艺术季的酒局", "抢救孤本掌卷女", "茶室里的准家元", "赶稿暗室女画师", "落槌后的女拍卖师", "车行里的女机械师", "宗祠绣轩苏绣娘", "沙暴封窟夜", "赶工GK的涂装师", "矿洞里的鉴定师", "大屏前的仙女画师", "揭幕前的修复师", "评委前的甜品主厨", "粉钻压轴设计师"
    ]),
    ("学府与书斋", "#6f78a0", [
        "旧校地窖女会长", "被窥破的催眠师", "冰山女物理学家", "零点放榜理事长", "梅雨阁楼编目员", "吊笼里的管理员", "老图书厅的硕士生", "礼堂侧幕的主席", "成人礼的礼仪讲师", "铜书梯上的馆员"
    ]),
    ("黑道与豪门", "#9a7394", [
        "握黑账的女社长", "暴雨游艇极道女", "地下金库财阀千金", "雷暴专机女总裁", "更衣室的造假底片", "夜半移门名门媳", "雪屋取弹黑道女", "铐精算师女若头", "佛堂守灵少夫人", "风球夜跌打医馆", "压载舱里的人质", "防弹密室女军火商", "安全屋的财团千金", "开库日的少夫人", "暗渠里的女董事长", "嘴硬的马术女骑手", "十号风球船坞"
    ]),
    ("职场与律政", "#6a7f90", [
        "停刊号的天窗", "防护服裂女主刀", "雪困专列女上司", "考评门外女主任", "雪夜地热泵房", "雪国线的乘务长", "风暴天桥女合伙人", "头等舱配餐间", "规培护士查房夜", "港交所敲钟日", "名宠水疗院院长"
    ]),
    ("谍战与战地", "#6f7f96", [
        "假面蜜月女卧底", "压载舱的王牌女谍", "七号车厢女法医", "断电夜的侧写官", "宪兵查证假新婚", "台风夜解剖室", "暗堡进水女报务", "破冰底舱女缉私", "冷库里的女刑警", "远海接舷女警官", "敢死第零番队", "弹尽粮绝女少校", "战地救护女军医"
    ]),
    ("舞台与镜头", "#9e6f86", [
        "第七任中之人", "琴库里的首席", "红毯夹裙女明星", "评弹女先生留扣", "湿透舞台女团C位", "金色大厅女指挥", "登台前的Coser", "裂鱼尾裙女影后", "吊威亚的汉服模特", "签售会的游戏声优", "第十一次告白", "大殿暖阁梳头师", "首演前钢琴千金", "辣妹设计师首秀", "唱诗班的领唱", "点茶的若夫人", "香槟塔前的司仪", "夺冠后的女主播", "幕布后高定车模", "开播前的电台主持", "水上洛神女舞者", "赌输的大提琴家", "昆曲闺门旦", "谢幕时的舞见"
    ]),
    ("赛场与博弈", "#8a7068", [
        "九段女棋圣封手夜", "地下剑馆女冠军", "花泳冠军与池底灯", "中日擂台女擂主", "大运会女单决赛", "太鼓下的女主将", "救球扑地女主攻"
    ]),
    ("绝境与重工", "#8a6f78", [
        "极夜里的女极客", "失控列车女司机", "万米深海女潜员", "核井防爆门下沉", "饱和舱第二十一天", "深井提升斗女总工", "高原井喷女地质师", "洪峰水坝女调度", "加氢塔下的检修季", "斗轮机女总指挥", "台风夜的月池", "好望角的女轮机长", "十马赫风洞女总师", "发射前四十秒", "不肯签字的女飞官", "雷暴里的半潜台"
    ]),
    ("科幻与末世", "#688288", [
        "改写故障日志", "隔离第二十天", "偏厅受审除籍女", "神经诊所的筹码", "定格十二分钟", "救生舱的王牌机师", "悬空的双人座舱", "酸雨天轨缆车", "皇家飞艇泄压", "高空风暴女上尉", "极寒避难所", "枕下的旧恨", "最后三支血清", "酸雨夜的净化师"
    ]),
    ("圣堂与魔裔", "#7c6f9a", [
        "魔石灯下的远征队", "藏起堕纹的圣女", "受审的高傲女骑士", "黑石水牢女骑士", "单膝正骨女祭司", "火刑颈圈小魔女", "九十九层的吊篮", "水银殿的女审判长", "王座受降魔皇女", "断头台前恶千金", "禁触的雪线圣女", "末代血族千金", "地下救护所女牧师"
    ]),
    ("王都与剑魔", "#76708e", [
        "同居魔族女勇者", "神殿药浴女祭司", "背负黑账看板娘", "弑神血旗女团长", "秘药高热女首席", "血脉觉醒的高热夜", "暴走的暗精灵斥候", "政变雪夜的皇女", "退队的重甲统领", "慢半拍的总务长", "公爵千金的药圃", "围城四十天骑士长", "停战使节魔军统帅", "宫廷大占星术士", "巡林的精灵游侠", "河港水门的铁骑", "嘴硬的精灵王女"
    ]),
]
BANDS = [("Ⅰ 东方与古典", 4), ("Ⅱ 西式与年代", 4), ("Ⅲ 都市与暗线", 4), ("Ⅳ 幻想与绝境", 5)]   # rows of the board, left to right
STARS = {"大理寺提刑女官", "紫禁封宫夜", "薄墙那头的主妇", "递辞呈的女仆长", "雷暴专机女总裁", "握黑账的女社长", "禁触的雪线圣女", "同居魔族女勇者"}   # gold-pinned picks, two a row
NWORLDS = sum(len(w) for _, _, w in REGIONS)
WALL_DESC = (f"{NWORLDS} 盒录像带平放叠在一家深夜租碟店的胡桃木货架上，侧脊朝外印着世界名，按题材分为{'、'.join(r for r, _, _ in REGIONS)}共 {len(REGIONS)} 栏，排成四层（{'、'.join(b[2:] for b, _ in BANDS)}；第三层「舞台与镜头」以双列并排展示），"
             f"每层配暖光射灯与铜铭牌，每栏标着世界数，{len(STARS)} 盒店长推荐片抽出亮金带扫光，全部已开放，可直接开局。")


def _tint_hex(hx, amt=0.28):
    r, g, b = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
    r = min(255, int(r + (255 - r) * amt))
    g = min(255, int(g + (255 - g) * amt))
    b = min(255, int(b + (255 - b) * amt))
    return f"#{r:02x}{g:02x}{b:02x}"


def _shade_hex(hx, factor=0.55):
    r, g, b = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
    return f"#{int(r * factor):02x}{int(g * factor):02x}{int(b * factor):02x}"


def worlds():
    STEP = 12                                                     # 48px per VHS tape, spine out
    HEAD = 28                                                     # brass plaque + genre sign + track lamp headroom
    bands, k = [], 0
    for _, n in BANDS:
        bands.append(REGIONS[k:k + n])
        k += n
    assert k == len(REGIONS)

    # Shelf III splits the 24-world "舞台与镜头" into a double-wide 12+12 twin bay (slashes 336px of dead wall!)
    def shelf_row_max(b, band):
        mx = 0
        for region, _, wl in band:
            mx = max(mx, (len(wl) + 1) // 2 if (b == 2 and len(wl) >= 20) else len(wl))
        return mx

    tops, shelves, y = [], [], 60
    for b, band in enumerate(bands):
        tops.append(y)
        rows = shelf_row_max(b, band)
        shelves.append(y + HEAD + rows * STEP + 3)
        y = shelves[-1] + 15                                      # roomy gap for shelf board, brackets & next ceiling lamps
    BY1 = shelves[-1] + 8                                         # solid walnut base plinth bottom
    GW, GH = 300, BY1 + 16                                        # generous bottom margin clear of rx=16 glass frame
    rnd = random.Random(31)
    cv = pk.Canvas(GW, GH)
    BX0, BY0 = 8, 52
    BX1 = 292

    # --- Walnut cabinet architecture: crown molding, beveled pilasters, wood planks & solid base plinth --------------
    cv.rect(BX0 - 4, BY0 - 6, BX1 + 4, BY0 - 4, "#12090d")        # outer top shadow
    cv.rect(BX0 - 4, BY0 - 5, BX1 + 4, BY0 - 2, "#5c3b29")        # walnut crown molding
    cv.rect(BX0 - 4, BY0 - 5, BX1 + 4, BY0 - 4, "#8a5d40")        # crown top catchlight
    cv.rect(BX0 - 3, BY0 - 2, BX1 + 3, BY0 - 1, "#9c7448")        # slim antique brass inlay trim
    cv.rect(BX0 - 3, BY0 - 1, BX1 + 3, BY1 + 3, "#140b0f")        # outer cabinet carcass shadow
    cv.rect(BX0 - 2, BY0, BX0, BY1, "#4e3224")                    # left walnut pilaster
    cv.rect(BX0 - 2, BY0, BX0 - 1, BY1, "#704934")                # left pilaster highlight
    cv.rect(BX1, BY0, BX1 + 2, BY1, "#4a2f22")                    # right walnut pilaster
    cv.rect(BX1 + 1, BY0, BX1 + 2, BY1, "#2a1914")                # right pilaster shade
    cv.rect(BX0, BY0, BX1, BY1, "#2a1b19")                        # warm dark walnut back panel
    for x in range(BX0 + 23, BX1, 24):                            # subtle plank seams
        cv.rect(x, BY0, x + 1, BY1, "#211516")
    for _ in range(int(1750 * (BY1 - BY0) / 480)):                # organic wood grain
        gx, gy = rnd.randrange(BX0, BX1), rnd.randrange(BY0, BY1)
        cv.put(gx, gy, rnd.choice(["#32211d", "#261816", "#392621"]))
    cv.rect(BX0, BY0, BX1, BY0 + 2, "#190f11")                    # under-crown recess shadow
    cv.rect(BX0, BY0, BX0 + 1, BY1, "#1c1214")                    # left interior ambient occlusion
    cv.rect(BX1 - 1, BY0, BX1, BY1, "#1c1214")                    # right interior ambient occlusion

    over, glow, sheen_defs, sheen_fx = [], [], [], []
    colw = (BX1 - BX0 - 8) / 5                                    # 55.2 cells (220.8px) per bay column
    TAPE = "#1c1722"
    PAPERS = ["#f2e9d6", "#ece1cc", "#f5eddd", "#e8ddc7"]

    # --- True catenary-draped pixel fairy lights cleanly clear of OPEN chains & symmetric on both sides -------------
    PW = 62
    plaque_x0 = (BX0 + BX1) // 2 - PW // 2
    fairy_pal = ["#ffd98e", "#ff7eb8", "#c9a2ff"]
    for side_idx, (fx0, fx1) in enumerate([(BX0 + 28, plaque_x0 - 5), (plaque_x0 + PW + 5, BX1 - 31)]):
        span = fx1 - fx0
        cv.rect(fx0 - 1, BY0 + 1, fx0 + 1, BY0 + 3, "#c9a24a")    # brass hook
        cv.rect(fx1 - 1, BY0 + 1, fx1 + 1, BY0 + 3, "#c9a24a")
        for x in range(fx0, fx1 + 1):
            t = (x - fx0) / max(1, span)
            wy = BY0 + 2 + round(4.0 * 4 * t * (1 - t))
            cv.put(x, wy, "#150c10")
            if x % 2 == 0:
                cv.put(x, wy - 1, "#2f2026")
        n_bulbs = 7
        for bi in range(1, n_bulbs):
            t = bi / n_bulbs
            bx_ = round(fx0 + t * span)
            by_ = BY0 + 2 + round(4.0 * 4 * t * (1 - t)) + 1
            col = fairy_pal[(bi + side_idx) % 3]
            cv.put(bx_, by_, col)
            glow.append(
                f'<circle cx="{(bx_ + 0.5) * C}" cy="{(by_ + 0.5) * C}" r="8" fill="{col}" fill-opacity="0.58" filter="url(#g6)">'
                f'<animate attributeName="fill-opacity" values="0.68;0.24;0.68" dur="{2.4 + (bi % 3) * 0.6:.1f}s" begin="-{(bi + side_idx * 3) * 0.35:.2f}s" repeatCount="indefinite"/></circle>'
            )

    star_idx = 0
    for b, band in enumerate(bands):
        TY, SY = tops[b], shelves[b]
        # Build slot layout: each item is (region, rc, world_list, col_start, col_span)
        slots = []
        if b == 2:
            c = 0
            for region, rc, wl in band:
                if len(wl) >= 20:
                    slots.append((region, rc, wl, c, 2))
                    c += 2
                else:
                    slots.append((region, rc, wl, c, 1))
                    c += 1
            total_cols = c
        else:
            for i, (region, rc, wl) in enumerate(band):
                slots.append((region, rc, wl, i, 1))
            total_cols = len(band)
        x_off = (5 - total_cols) * colw / 2

        # Subtle vertical recessed cubby lines between columns
        for ci in range(1, total_cols):
            # Skip internal divider between the two halves of double-wide 舞台与镜头
            if b == 2 and ci == 4:
                continue
            dx = int(BX0 + 4 + x_off + ci * colw)
            cv.rect(dx, TY + 13, dx + 1, SY, "#221515")

        # Canopy brass track spotlights + soft Gaussian-feathered warm tungsten cones (zero razor triangle lines!)
        if b == 0:
            glow.append(
                f'<ellipse cx="{(BX0 + BX1) / 2 * C}" cy="{(TY + 20) * C}" rx="420" ry="130" fill="#ffcf8a" fill-opacity="0.09" filter="url(#g30)"/>'
            )
        else:
            lamp_y = TY - 5
            for lx in (BX0 + 74, BX1 - 74):
                cv.rect(lx - 3, lamp_y, lx + 3, lamp_y + 2, "#8a6630")
                cv.rect(lx - 2, lamp_y + 2, lx + 2, lamp_y + 3, "#ffd98e")
                glow.append(
                    f'<polygon points="{(lx - 4) * C},{(lamp_y + 3) * C} {(lx + 4) * C},{(lamp_y + 3) * C} '
                    f'{(lx + 72) * C},{(SY - 4) * C} {(lx - 72) * C},{(SY - 4) * C}" fill="url(#lampcone)" filter="url(#g15)"/>'
                )

        # Shelf board (Shelves I-III) OR Solid Walnut Base Plinth (Shelf IV — zero protruding brackets!)
        if b < 3:
            cv.rect(BX0, SY, BX1, SY + 4, "#6e4732")
            cv.rect(BX0, SY, BX1, SY + 1, "#a67450")
            cv.rect(BX0, SY + 3, BX1, SY + 4, "#4b2e1f")
            cv.rect(BX0, SY + 4, BX1, SY + 6, "#160c10")          # crisp contact cast shadow
            # Place mirror-symmetric iron brackets strictly in inter-column gaps (never colliding with price tags or lamps!)
            if total_cols == 4:
                br_xs = [BX0 + 18, (BX0 + BX1) // 2 - 2, BX1 - 24]
            else:
                br_xs = [BX0 + 10, int(BX0 + 4 + 2 * colw) - 3, int(BX0 + 4 + 3 * colw) - 3, BX1 - 16]
            for bx in br_xs:
                cv.poly([(bx, SY + 5), (bx + 6, SY + 5), (bx, SY + 11)], "#3a3342")
                cv.rect(bx, SY + 5, bx + 1, SY + 11, "#5c5368")
                cv.put(bx + 2, SY + 6, "#8c829a")
        else:
            # Solid walnut base apron + recessed kick panel + brass-shod feet (100% inside cabinet bounds!)
            cv.rect(BX0 - 2, SY, BX1 + 2, SY + 4, "#6e4732")
            cv.rect(BX0 - 2, SY, BX1 + 2, SY + 1, "#a67450")
            cv.rect(BX0 - 2, SY + 4, BX1 + 2, SY + 8, "#472c1e")
            cv.rect(BX0, SY + 5, BX1, SY + 7, "#362016")
            for fx in (BX0 + 8, BX1 - 18):
                cv.rect(fx, SY + 7, fx + 10, SY + 9, "#2a1812")
                cv.rect(fx, SY + 8, fx + 10, SY + 9, "#9c7448")   # brass foot shoe

        # Readable vintage brass-clipped shelf price tags ("¥3/夜", 12.5px legible at GitHub 894px!)
        for region, rc, wl, c0, cspan in slots:
            cx_mid = BX0 + 4 + x_off + (c0 + cspan / 2) * colw
            tx = int(cx_mid) - 7
            cv.rect(tx + 1, SY + 1, tx + 15, SY + 5, "#2b1912")   # subtle shadow
            cv.rect(tx, SY, tx + 14, SY + 4, "#f4ead4")
            cv.rect(tx, SY, tx + 2, SY + 4, _tint_hex(rc, 0.10))  # color-keyed stub matching column genre!
            over.append(text((tx + 8.0) * C, (SY + 3.0) * C, "¥3/夜", 12.5, "#3a1e24", 800, "middle", 0, SANS))

        # Brass section plaque (aligned with genres.svg: PW=62, brighter gold, strictly symmetric rivets, 17px centered!)
        px0 = (BX0 + BX1) // 2 - PW // 2
        cv.rect(px0 + 1, TY - 1, px0 + PW + 1, TY + 9, "#0e080a")
        cv.rect(px0, TY - 2, px0 + PW, TY + 8, "#cfa850")
        cv.rect(px0, TY - 2, px0 + PW, TY - 1, "#f5dc94")
        cv.rect(px0, TY + 7, px0 + PW, TY + 8, "#8a6a28")
        for sx in (px0 + 2, px0 + PW - 3):                        # strictly symmetric 2-cell inset rivets!
            cv.put(sx, TY + 3, "#7a5a20")
        over.append(text((px0 + PW / 2) * C, (TY + 4.9) * C, BANDS[b][0], 17, "#452e0c", 900, "middle", 2, SANS))

        # Genre sign bars + VHS tape stacks
        LY = TY + 12
        for region, rc, wl, c0, cspan in slots:
            bx_l = BX0 + 4 + x_off + c0 * colw
            bx_r = bx_l + cspan * colw
            tx0, tx1 = int(bx_l + 2), int(bx_r - 2)
            # Genre header sign: tinted top highlight (NO harsh pure #ffffff!), proper bottom shadow, gold count!
            cv.rect(tx0 + 1, LY + 1, tx1 + 1, LY + 10, "#0e080a")
            cv.rect(tx0, LY, tx1, LY + 9, rc)
            cv.rect(tx0, LY, tx1, LY + 1, _tint_hex(rc, 0.34))
            cv.rect(tx0, LY + 8, tx1, LY + 9, _shade_hex(rc, 0.55))
            cnt_col = "#ffe6a0" if len(wl) >= 14 else "#f2e6ff"
            over.append(
                f'<text x="{(tx0 + tx1) / 2 * C:.1f}" y="{(LY + 6.1) * C:.1f}" font-family="{SANS}" font-size="16" '
                f'font-weight="800" fill="#fff9fc" text-anchor="middle" letter-spacing="1" '
                f'stroke="#1e1224" stroke-width="3" paint-order="stroke">{esc(region)} '
                f'<tspan font-family="{MONO}" font-size="15" fill="{cnt_col}">{len(wl)}</tspan></text>'
            )

            # Distribute worlds across cspan sub-columns (1 normally; 2 balanced halves for 舞台与镜头 12+12)
            if cspan == 2:
                half = (len(wl) + 1) // 2
                sub_cols = [(0, wl[:half]), (1, wl[half:])]
            else:
                sub_cols = [(0, wl)]

            for sc_i, sub_w in sub_cols:
                cx0 = bx_l + sc_i * colw
                n = len(sub_w)
                for j, name in enumerate(sub_w):
                    star = name in STARS
                    y0 = SY - (n - j) * STEP
                    y1 = y0 + STEP - 1
                    if star:
                        # Zero-collision pulled-out pick: cover sleeve peeks 4 cells left, spine shifts only +1.4 cells right (23px safe gutter!)
                        cov_x0 = int(cx0 + 1)
                        x0 = cov_x0 + 4
                        x1 = x0 + 47
                        cv.vgrad(cov_x0, y0 + 1, x0, y1 - 1, [_tint_hex(rc, 0.28), "#ff6fae", _shade_hex(rc, 0.65)])
                        cv.rect(x0 - 1, y0 + 1, x0, y1 - 1, "#ffd98e")   # crisp gold foil spine crease
                    else:
                        jitter = rnd.choice([-1, 0, 0, 1])
                        x0 = int(cx0 + 3.5 + jitter)
                        x1 = x0 + 48
                    # Tape casing + 1-cell bottom contact shadow
                    cv.rect(x0, y1, x1, y1 + 1, "#120c14")
                    cv.rect(x0, y0, x1, y1, TAPE)
                    cv.rect(x0, y0, x1, y0 + 1, "#3b3248")
                    # Vintage paper tone variation
                    paper = "#ffecd4" if star else PAPERS[(sum(map(ord, name)) + j) % len(PAPERS)]
                    cv.rect(x0 + 2, y0 + 2, x1 - 3, y1 - 2, paper)
                    cv.rect(x0 + 2, y0 + 2, x0 + 4, y1 - 2, "#ff6fae" if star else rc)
                    # Subtle embossed VHS reel notch on right shell edge (no confusing random colored dots!)
                    cv.rect(x1 - 2, y0 + 3, x1 - 1, y1 - 3, "#342b40")
                    if star:
                        # Tiny crisp champagne-gold star emblem at right end of label + slow diagonal gold sheen sweep!
                        sx_, sy_ = x1 - 6, y0 + 5
                        cv.put(sx_, sy_ - 1, "#d48a28")
                        cv.put(sx_, sy_ + 1, "#d48a28")
                        cv.put(sx_ - 1, sy_, "#d48a28")
                        cv.put(sx_ + 1, sy_, "#d48a28")
                        cv.put(sx_, sy_, "#ffd96a")
                        cid = f"stclip{star_idx}"
                        lx0_px, ly0_px = (x0 + 2) * C, (y0 + 2) * C
                        lw_px, lh_px = (x1 - x0 - 5) * C, (y1 - y0 - 4) * C
                        sheen_defs.append(f'<clipPath id="{cid}"><rect x="{lx0_px}" y="{ly0_px}" width="{lw_px}" height="{lh_px}"/></clipPath>')
                        beg = star_idx * 0.72
                        sheen_fx.append(
                            f'<g clip-path="url(#{cid})"><rect x="{lx0_px - 44}" y="{ly0_px}" width="44" height="{lh_px}" fill="url(#goldsheen)">'
                            f'<animate attributeName="x" values="{lx0_px - 44};{lx0_px + lw_px + 20};{lx0_px + lw_px + 20}" keyTimes="0;0.24;1" dur="6.4s" begin="{beg:.2f}s" repeatCount="indefinite"/></rect></g>'
                            f'<circle cx="{(sx_ + 0.5) * C}" cy="{(sy_ + 0.5) * C}" r="9" fill="#ffd98e" fill-opacity="0.45" filter="url(#g4)">'
                            f'<animate attributeName="fill-opacity" values="0.58;0.18;0.58" dur="3.0s" begin="-{beg:.2f}s" repeatCount="indefinite"/></circle>'
                        )
                        star_idx += 1
                    usable_px = (x1 - x0 - (11 if star else 8)) * C
                    size = min(15.5, usable_px / len(name))
                    over.append(text((x0 + 5.5) * C, (y0 + 7.2) * C, name, round(size, 1), "#1f1622", 800, "start", 0))

        # --- Curated Midnight Store Props & Wall Accents (Zero Floating / Zero Glitches / 23:00 Easter Egg!) ---------
        L0 = BX0 + 4
        R0 = int(BX0 + 4 + x_off + total_cols * colw) + 2
        FT = LY + 10                                              # safely below genre signs

        if b == 0:
            # 1) Shelf I Left: Lo-fi CRT TV on VCR with calm 3.6s amber-violet PLAY scanline (NO 0.8s white seizure flash!)
            cv.rect(L0 + 1, SY - 5, L0 + 24, SY, "#2a2432")
            cv.rect(L0 + 1, SY - 5, L0 + 24, SY - 4, "#4b4158")
            cv.rect(L0 + 4, SY - 3, L0 + 14, SY - 2, "#0d0912")
            cv.put(L0 + 20, SY - 3, "#ff6fae")                    # soft pink REC/PLAY power dot
            cv.rect(L0 + 2, SY - 23, L0 + 23, SY - 5, "#362c3a")
            cv.rect(L0 + 2, SY - 23, L0 + 23, SY - 22, "#594a60")
            cv.vgrad(L0 + 4, SY - 21, L0 + 18, SY - 7, ["#1c1538", "#342254", "#5c3368"])
            for sy_ in range(SY - 20, SY - 7, 2):                 # subtle CRT scanlines
                cv.rect(L0 + 4, sy_, L0 + 18, sy_ + 1, "#251a42")
            # Tiny pixel PLAY triangle on screen
            cv.poly([(L0 + 9, SY - 16), (L0 + 9, SY - 11), (L0 + 14, SY - 13.5)], "#ffd98e")
            for ky in (SY - 18, SY - 14):
                cv.put(L0 + 20, ky, "#cfa850")
            cv.line(L0 + 8, SY - 23, L0 + 4, SY - 30, "#8a8098")
            cv.line(L0 + 14, SY - 23, L0 + 19, SY - 29, "#8a8098")
            glow.append(
                f'<rect x="{(L0 + 4) * C}" y="{(SY - 21) * C}" width="{14 * C}" height="{2 * C}" fill="#ffd6ee" opacity="0.22">'
                f'<animate attributeName="y" values="{(SY - 21) * C};{(SY - 9) * C}" dur="3.6s" repeatCount="indefinite"/></rect>'
                f'<ellipse cx="{(L0 + 11) * C}" cy="{(SY - 14) * C}" rx="64" ry="44" fill="#c48aff" fill-opacity="0.16" filter="url(#g15)">'
                '<animate attributeName="fill-opacity" values="0.12;0.22;0.12" dur="4.2s" repeatCount="indefinite"/></ellipse>'
                f'<circle cx="{(L0 + 20.5) * C}" cy="{(SY - 2.5) * C}" r="5" fill="#ff6fae" fill-opacity="0.65" filter="url(#g4)"/>'
            )

            # 2) Shelf I Right Top: Properly hung OPEN neon sign (chains anchored to cabinet ceiling + roomy frame!)
            ox0, oy0, ox1, oy1 = R0 - 1, FT + 4, R0 + 27, FT + 17
            cv.line(ox0 + 4, BY0 + 2, ox0 + 4, oy0, "#6e6478")    # anchored all the way up to ceiling!
            cv.line(ox1 - 5, BY0 + 2, ox1 - 5, oy0, "#6e6478")
            cv.rect(ox0 + 1, oy0 + 1, ox1 + 1, oy1 + 1, "#0c060c")
            cv.rect(ox0, oy0, ox1, oy1, "#160c1c")
            cv.rect(ox0, oy0, ox1, oy0 + 1, "#5c3d68")
            cv.rect(ox0, oy1 - 1, ox1, oy1, "#3b2345")
            cv.text("OPEN", ox0 + 3, oy0 + 3, "#ff74b5")
            glow.append(
                f'<ellipse cx="{(ox0 + ox1) / 2 * C}" cy="{(oy0 + oy1) / 2 * C}" rx="68" ry="38" fill="#ff6fae" fill-opacity="0.30" filter="url(#g15)">'
                '<animate attributeName="fill-opacity" values="0.32;0.32;0.12;0.32;0.28" dur="4.6s" repeatCount="indefinite"/></ellipse>'
            )

            # 3) Shelf I Right Bottom: 3 Loose returns stacked FLUSH (zero 4px air gap!)
            for k in range(3):
                ly_ = SY - 3 - k * 3
                cv.rect(R0 + 2 + k, ly_, R0 + 22 + k, ly_ + 3, TAPE)
                cv.rect(R0 + 2 + k, ly_, R0 + 22 + k, ly_ + 1, "#3a3246")
                cv.rect(R0 + 4 + k, ly_ + 1, R0 + 18 + k, ly_ + 2, ["#ff6fae", "#f2e9d6", "#b88cff"][k])

            # 4) Shelf I Short-Stack Wall Accent above 仙侠与志怪 5: wall-mounted featured cover sleeve (fills 240px void!)
            col1_cx = int(BX0 + 4 + x_off + 1.5 * colw)
            col1_top = SY - len(band[1][2]) * STEP
            fx0, fy0 = col1_cx - 13, LY + 14
            fx1, fy1 = col1_cx + 13, col1_top - 6
            if fy1 - fy0 >= 28:
                fy0 = (LY + 11 + col1_top - 3) // 2 - 17
                fy1 = fy0 + 34
                cv.rect(fx0 + 1, fy0 + 1, fx1 + 1, fy1 + 1, "#0d070c")
                cv.rect(fx0, fy0, fx1, fy1, "#1c1722")
                cv.rect(fx0, fy0, fx1, fy0 + 1, "#584c68")
                cv.rect(fx0 + 1, fy0 + 1, fx1 - 1, fy0 + 5, "#768a9e")
                cover_art(cv, "仙侠与志怪", fx0 + 1, fy0 + 5, fx1 - 1, fy1 - 7, rnd, glow)
                cv.rect(fx0 + 1, fy1 - 7, fx1 - 1, fy1 - 1, "#f2e9d6")
                cv.put((fx0 + fx1) // 2, fy0 - 1, "#cfa850")      # tiny brass wall pin
                over.append(text((fx0 + fx1) / 2 * C, (fy1 - 2.3) * C, "本周特展", 13.5, "#24192a", 800, "middle", 0.4, SANS))

        elif b == 1:
            # 1) Shelf II Left Top: Pinned wooden-framed 会员须知 (bumped to 13.5px legible!)
            cv.rect(L0 + 1, FT + 2, L0 + 26, FT + 20, "#0e080a")
            cv.rect(L0, FT + 1, L0 + 25, FT + 19, "#4a2f20")
            cv.rect(L0 + 1, FT + 2, L0 + 24, FT + 18, "#f5ecd8")
            cv.put(L0 + 12, FT + 1, "#cfa850")                    # brass pin
            cv.rect(L0 + 3, FT + 9, L0 + 22, FT + 10, "#c83a54")
            for k in range(3):
                cv.rect(L0 + 3, FT + 11 + k * 2, L0 + 20 - k * 3, FT + 12 + k * 2, "#9a8a74")
            over.append(text((L0 + 12.5) * C, (FT + 7.4) * C, "会员须知", 13.5, "#3a2218", 900, "middle", 0.6, SANS))

            # 2) Shelf II Left Bottom: Plant + Steaming Mug (animated rising steam!)
            plant(cv, L0 + 7, SY)
            mug(cv, L0 + 15, SY)
            glow.append(f'<g shape-rendering="crispEdges">{steam(L0 + 16, SY - 8)}</g>')

            # 3) Shelf II Right Bottom: Clean Angled Return Drop Box (NO "two-eyed purple robot face"!)
            cv.rect(R0 + 1, SY - 20, R0 + 25, SY, "#3e264c")
            cv.rect(R0 + 1, SY - 20, R0 + 25, SY - 19, "#6a4980")
            cv.rect(R0 + 1, SY - 1, R0 + 25, SY, "#1e1226")
            # Beveled drop slot + a single slanted VHS tape edge sliding into the chute
            cv.rect(R0 + 4, SY - 16, R0 + 22, SY - 13, "#120916")
            cv.rect(R0 + 4, SY - 13, R0 + 22, SY - 12, "#74548a")
            cv.poly([(R0 + 7, SY - 15), (R0 + 19, SY - 15), (R0 + 21, SY - 22), (R0 + 9, SY - 22)], TAPE)
            cv.poly([(R0 + 8, SY - 16), (R0 + 18, SY - 16), (R0 + 20, SY - 21), (R0 + 10, SY - 21)], "#f2e9d6")
            cv.line(R0 + 9, SY - 21, R0 + 19, SY - 21, "#ff6fae")
            # Crisp brass-rimmed nameplate
            cv.rect(R0 + 4, SY - 10, R0 + 22, SY - 3, "#241530")
            cv.rect(R0 + 4, SY - 10, R0 + 22, SY - 9, "#cfa850")
            over.append(text((R0 + 13) * C, (SY - 5.2) * C, "还片处", 14.5, "#ffe9b8", 900, "middle", 1.5, SANS))

            # 4) Shelf II Above Col 0 (欧陆古典 7): 新片到货 poster seated FLUSH on top tape!
            ex0 = int(BX0 + 4 + x_off)
            top0 = SY - len(band[0][2]) * STEP
            PX0, PY0 = ex0 + int(colw / 2) - 17, top0 - 36        # PY0 + 36 == top0 -> 100% FLUSH!
            cv.rect(PX0 + 1, PY0 + 1, PX0 + 35, top0, "#0e080a")
            cv.rect(PX0, PY0, PX0 + 34, top0, "#f5ecd8")
            cv.rect(PX0 + 14, PY0 - 1, PX0 + 20, PY0 + 1, "#f2dfb0")   # top masking tape
            cv.vgrad(PX0 + 3, PY0 + 12, PX0 + 31, PY0 + 33, ["#1d2350", "#3a2a66", "#6a3778", "#a2477e"])
            for kk in range(4):
                lx, ly = PX0 + 7 + kk * 7, PY0 + 18 - kk * 0.5
                cv.rect(lx, PY0 + 12, lx + 1, int(ly), "#2a1e38")      # real lantern cord
                cv.ellipse(lx, ly + 3, 2.4, 3, lambda x, y, lx=lx: "#ffcf6a" if x == int(lx) else "#e0402f")
            cv.poly([(PX0 + 3, PY0 + 30), (PX0 + 10, PY0 + 26), (PX0 + 17, PY0 + 29), (PX0 + 24, PY0 + 25), (PX0 + 31, PY0 + 29), (PX0 + 31, PY0 + 33), (PX0 + 3, PY0 + 33)], "#1a1228")
            over.append(text((PX0 + 17) * C, (PY0 + 9.0) * C, "新片到货", 17, "#c8324a", 900, "middle", 2, SANS))

        elif b == 2:
            # Shelf III has 5 bays [17, 11, 13, 12, 12] -> every prop seats cleanly in the natural niches above short stacks!
            # 1) Above Col 1 (职场与律政 11): 想租的片 Standee seated FLUSH + centered typography + gold highlight!
            ex1 = int(BX0 + 4 + colw)
            top1 = SY - len(band[1][2]) * STEP
            NX0, NY0 = ex1 + 3, top1 - 30                         # NY0 + 30 == top1 -> FLUSH & clear of Col 0!
            NW_ = int(colw) - 6
            cv.rect(NX0 + 1, NY0 + 1, NX0 + NW_ + 1, top1, "#0d070c")
            cv.rect(NX0, NY0, NX0 + NW_, top1, "#221730")
            cv.rect(NX0, NY0, NX0 + NW_, NY0 + 1, "#ff6fae")
            cv.rect(NX0, top1 - 1, NX0 + NW_, top1, "#cfa850")
            cv.rect(NX0, NY0 + 1, NX0 + 1, top1 - 1, "#4a3662")
            cv.rect(NX0 + NW_ - 1, NY0 + 1, NX0 + NW_, top1 - 1, "#4a3662")
            ncx = (NX0 + NW_ / 2) * C
            over.append(text(ncx, (NY0 + 8.5) * C, "想租的片不在架上？", 14.5, "#f0e4ff", 800, "middle", 0.4, SANS))
            over.append(text(ncx, (NY0 + 16.5) * C, "直接说", 14.5, "#dfd2f0", 700, "middle", 1, SANS))
            over.append(text(ncx, (NY0 + 24.5) * C, "“自定义世界”", 16.5, "#ffd98e", 900, "middle", 1, SANS))

            # 2) Above Col 2 (谍战与战地 13): Striped Popcorn Bucket + 3 Leaning 新到 Sleeves braced by brass L-bookend!
            ex2 = int(BX0 + 4 + 2 * colw)
            top2 = SY - len(band[2][2]) * STEP
            pbx = ex2 + 6
            cv.rect(pbx, top2 - 11, pbx + 10, top2, lambda x, y: "#d03c4e" if (x // 2) % 2 else "#f5ecd8")
            for (px_, py_) in [(pbx + 2, top2 - 12), (pbx + 5, top2 - 13), (pbx + 8, top2 - 12), (pbx + 4, top2 - 11)]:
                cv.ellipse(px_, py_, 1.6, 1.4, "#fff2c6")
            for k in range(3):
                sx = ex2 + 21 + k * 7
                cv.poly([(sx, top2), (sx + 5, top2), (sx + 9, top2 - 19), (sx + 4, top2 - 19)], ["#3b2966", "#6a3478", "#9e4478"][k])
                cv.poly([(sx + 1, top2 - 3), (sx + 4, top2 - 3), (sx + 7, top2 - 16), (sx + 4, top2 - 16)], ["#ff74b5", "#ffd98e", "#c9a2ff"][k])
            # Crisp brass L-bookend bracing the right side of the leaning sleeves (physically grounded!)
            cv.rect(ex2 + 44, top2 - 15, ex2 + 46, top2, "#cfa850")
            cv.rect(ex2 + 44, top2 - 15, ex2 + 45, top2, "#f5dc94")
            cv.rect(ex2 + 40, top2 - 2, ex2 + 46, top2, "#8a6a28")
            # Pinned brass/plum 新到 mini plaque above the leaning sleeves
            cv.rect(ex2 + 23, top2 - 28, ex2 + 45, top2 - 21, "#221630")
            cv.rect(ex2 + 23, top2 - 28, ex2 + 45, top2 - 27, "#cfa850")
            cv.put(ex2 + 34, top2 - 29, "#cfa850")                # brass wall pin
            over.append(text((ex2 + 34) * C, (top2 - 22.8) * C, "新 到", 13.5, "#ffd98e", 900, "middle", 1, SANS))

            # 3) Above Double-Wide Bay Col 3+4 (舞台与镜头 12+12, 5 rows = 60 cells free across 110-cell span!):
            #    Centered 午夜场 cinema poster + 23:00 Easter-egg wall clock right beside it!
            bay_l = int(BX0 + 4 + 3 * colw)
            bay_r = int(BX0 + 4 + 5 * colw)
            top34 = SY - 12 * STEP
            MX0 = bay_l + 6
            MY0 = LY + 15
            # Symmetric masking tape (1-cell overhang on BOTH left and right!)
            cv.rect(MX0 + 1, MY0 + 1, MX0 + 73, MY0 + 45, "#0d070c")
            cv.rect(MX0, MY0, MX0 + 72, MY0 + 44, "#ebe0ca")
            cv.vgrad(MX0 + 2, MY0 + 2, MX0 + 70, MY0 + 36, ["#0e1030", "#1d2350", "#3a2a66", "#6a3778"])
            for _ in range(26):
                cv.put(rnd.randrange(MX0 + 3, MX0 + 69), rnd.randrange(MY0 + 3, MY0 + 22), rnd.choice(["#d4dcff", "#949ad0"]))
            # Clean mathematically masked crescent moon (ZERO flat-color dither patch artifact!)
            mcx, mcy = MX0 + 56, MY0 + 11
            for my_ in range(mcy - 6, mcy + 6):
                for mx_ in range(mcx - 6, mcx + 6):
                    if math.hypot(mx_ - mcx, my_ - mcy) <= 5.0 and math.hypot(mx_ - (mcx + 2.2), my_ - (mcy - 1.4)) > 4.2:
                        cv.put(mx_, my_, "#fff2c6")
            cv.poly([(MX0 + 2, MY0 + 32), (MX0 + 14, MY0 + 25), (MX0 + 26, MY0 + 30), (MX0 + 40, MY0 + 22), (MX0 + 54, MY0 + 29), (MX0 + 70, MY0 + 24), (MX0 + 70, MY0 + 36), (MX0 + 2, MY0 + 36)], "#140c22")
            cv.rect(MX0 + 2, MY0 + 36, MX0 + 70, MY0 + 42, "#1a1418")
            for fx in range(MX0 + 4, MX0 + 69, 4):
                cv.rect(fx, MY0 + 37, fx + 2, MY0 + 38, "#ebe0ca")
                cv.rect(fx, MY0 + 40, fx + 2, MY0 + 41, "#ebe0ca")
            cv.rect(MX0 - 1, MY0 - 1, MX0 + 6, MY0 + 2, "#f6e6b0")          # left tape: 1-cell overhang
            cv.rect(MX0 + 66, MY0 - 1, MX0 + 73, MY0 + 2, "#f6e6b0")        # right tape: exact 1-cell overhang!
            over.append(text((MX0 + 36) * C, (MY0 + 19) * C, "午夜场", 30, "#ff74b5", 900, "middle", 6, SANS,
                             'stroke="#140c22" stroke-width="4" paint-order="stroke"'))
            over.append(text((MX0 + 36) * C, (MY0 + 30.0) * C, "每晚 23:00 · 两片连映", 14, "#ffe0ef", 800, "middle", 1.2, SANS))
            glow.append(f'<ellipse cx="{(MX0 + 36) * C}" cy="{(MY0 + 16) * C}" rx="120" ry="48" fill="#ff6fae" fill-opacity="0.12" filter="url(#g15)"/>')

            # Wall clock set precisely to 23:00 (Easter egg matching "每晚 23:00"!) right of the poster
            clk_x, clk_y = bay_r - 17, MY0 + 18
            cv.ellipse(clk_x + 1, clk_y + 1, 8, 8, "#0d070c")
            cv.ellipse(clk_x, clk_y, 8, 8, "#cfa850")             # brass bezel
            cv.ellipse(clk_x, clk_y, 6.6, 6.6, "#f5ecd8")         # cream dial
            for px_, py_ in [(clk_x, clk_y - 5), (clk_x + 5, clk_y), (clk_x, clk_y + 5), (clk_x - 5, clk_y)]:
                cv.put(px_, py_, "#6e4e2a")                       # 12/3/6/9 cardinal ticks
            cv.line(clk_x, clk_y, clk_x, clk_y - 5, "#1f1622")    # minute hand straight up at 12 (:00)
            cv.line(clk_x, clk_y, clk_x - 3, clk_y - 3, "#c83a54")  # distinct 11-o'clock hour hand (23:00!)
            cv.put(clk_x, clk_y, "#cfa850")                       # center brass pin
            over.append(text(clk_x * C, (clk_y + 12.8) * C, "23:00", 13.5, "#e6d8f5", 800, "middle", 1.0, MONO))

        else:
            # Shelf IV (5 cols):
            # 1) Above Col 0 (赛场与博弈 7): Flush-seated Velvet-Plum & Champagne-Gold VIP Card + Wall Featured Sleeve!
            ex0 = int(BX0 + 4)
            top0 = SY - len(band[0][2]) * STEP
            TX0, TY0 = ex0 + int(colw / 2) - 21, top0 - 12        # TY0 + 12 == top0 -> 100% FLUSH!
            cv.rect(TX0 + 1, TY0 + 1, TX0 + 43, top0, "#0d070c")
            cv.rect(TX0, TY0, TX0 + 42, top0, "#4a1e44")
            cv.rect(TX0, TY0, TX0 + 42, TY0 + 1, "#cfa850")
            cv.rect(TX0, top0 - 1, TX0 + 42, top0, "#240e24")
            cv.rect(TX0 + 32, TY0 + 3, TX0 + 39, TY0 + 8, "#ffd98e")   # gold chip
            cv.rect(TX0 + 34, TY0 + 5, TX0 + 37, TY0 + 6, "#a67428")
            cv.text("CLUB", TX0 + 3, TY0 + 3, "#ffe9c4")
            # Animated metallic sheen across the VIP card
            sheen_defs.append(f'<clipPath id="vipclip"><rect x="{TX0 * C}" y="{TY0 * C}" width="{42 * C}" height="{12 * C}"/></clipPath>')
            sheen_fx.append(
                f'<g clip-path="url(#vipclip)"><rect x="{(TX0 - 12) * C}" y="{TY0 * C}" width="{12 * C}" height="{12 * C}" fill="url(#goldsheen)">'
                f'<animate attributeName="x" values="{(TX0 - 12) * C};{(TX0 + 48) * C};{(TX0 + 48) * C}" keyTimes="0;0.25;1" dur="5.8s" repeatCount="indefinite"/></rect></g>'
            )
            # Wall-mounted featured cover sleeve above the VIP card to balance the tall left wall niche!
            fx0, fy0 = ex0 + int(colw / 2) - 13, LY + 22
            fx1, fy1 = fx0 + 26, fy0 + 36
            cv.rect(fx0 + 1, fy0 + 1, fx1 + 1, fy1 + 1, "#0d070c")
            cv.rect(fx0, fy0, fx1, fy1, "#1c1722")
            cv.rect(fx0, fy0, fx1, fy0 + 1, "#584c68")
            cv.rect(fx0 + 1, fy0 + 1, fx1 - 1, fy0 + 5, "#8a7068")
            cover_art(cv, "赛场与博弈", fx0 + 1, fy0 + 5, fx1 - 1, fy1 - 7, rnd, glow)
            cv.rect(fx0 + 1, fy1 - 7, fx1 - 1, fy1 - 1, "#f2e9d6")
            cv.put((fx0 + fx1) // 2, fy0 - 1, "#cfa850")
            over.append(text((fx0 + fx1) / 2 * C, (fy1 - 2.3) * C, "深夜必看", 13.5, "#24192a", 800, "middle", 0.4, SANS))

            # 2) Above Col 3 (圣堂与魔裔 13): Redesigned Loafed Black Cat (2 tucked paws, side tail, tight gold pupils!)
            cx = int(BX0 + 4 + 3 * colw + colw / 2) + 2
            top3 = SY - len(band[3][2]) * STEP
            CAT = [
                "..x.......x.....",
                ".xp.......px....",
                ".xxx.....xxx....",
                ".xxxxxxxxxxx....",
                "xxxxxxxxxxxxx...",
                "xxeexxxxxeexx...",
                "xxxxxxnxxxxxx...",
                ".xxxxxxxxxxx....",
                "..xxxxxxxxx.....",
                ".xxxxxxxxxxx....",
                ".xxxxxxxxxxxx.x.",
                "xxxxxxxxxxxxxx.x",
                "xxxxxxxxxxxxxxx.",
                "xxxxxxxxxxxxxx..",
                ".xxxx...xxxx....",
            ]
            cx0, cy0 = cx - 8, top3 - len(CAT)                    # bottom row sits FLUSH on top3!
            for r, row in enumerate(CAT):
                for q, ch in enumerate(row):
                    if ch == ".":
                        continue
                    edge = q == 0 or row[q - 1] == "." or r == 0 or CAT[r - 1][q] == "."
                    cv.put(cx0 + q, cy0 + r, {"e": "#ffd96a", "n": "#e07494", "p": "#824064"}.get(ch, "#4c3c64" if edge else "#1d1526"))
            # Tight per-eye golden glint (ZERO muddy forehead fog!) + slow 5s blink
            for ex in (cx0 + 2, cx0 + 9):
                glow.append(
                    f'<circle cx="{(ex + 1) * C}" cy="{(cy0 + 5.5) * C}" r="5.5" fill="#ffd96a" fill-opacity="0.38" filter="url(#g4)"/>'
                    f'<rect x="{ex * C}" y="{(cy0 + 5) * C}" width="{2 * C}" height="{C}" fill="#1d1526" opacity="0">'
                    '<animate attributeName="opacity" values="0;0;1;0;0" keyTimes="0;0.90;0.93;0.96;1" dur="5.2s" repeatCount="indefinite"/></rect>'
                )

    # --- Header title + crisp rental-store legend (replaces orphan pink square!) -------------------------------------
    # Tiny crisp pixel gold star in legend at left of legend copy
    l_star = (
        '<g fill="#ffd98e" shape-rendering="crispEdges">'
        '<rect x="332" y="153" width="4" height="12"/><rect x="328" y="157" width="12" height="4"/>'
        '<rect x="332" y="157" width="4" height="4" fill="#fff7dc"/></g>'
    )
    title_block = (
        f'<g>{text(600 + 3, 82 + 3, f"{NWORLDS} 个世界", 52, "#12061c", 800, "middle", 3, SANS)}'
        f'{text(600, 82, f"{NWORLDS} 个世界", 52, GLOW, 800, "middle", 3, SANS, "filter=\"url(#g4)\" opacity=\"0.85\"")}'
        f'{text(600, 82, f"{NWORLDS} 个世界", 52, CORE, 800, "middle", 3, SANS, "stroke=\"#c48aff\" stroke-width=\"1.2\" paint-order=\"stroke\"")}</g>'
    )
    body = f'''    <g shape-rendering="crispEdges">{cv.emit(C)}</g>
    {"".join(glow)}
    {"".join(over)}
    {"".join(sheen_fx)}
    {title_block}
    {text(600, 122, "选一个直接开局，或者说“自定义世界”当场写一个", 20.5, SUBT, 600, "middle", 1.8)}
    {l_star}
    {text(350, 165, f"抽出亮金 = 店长推荐（{len(STARS)} 部）  ·  全部 {NWORLDS} 部已开放，喊出片名直接开局", 15.5, "#ebdcf8", 700, "start", 0.8)}
    {text(600, (BY1 + 10.5) * C, f"· 全部 {NWORLDS} 个世界已开放 · 名单会继续变长 ·", 16.5, "#cfc3df", 600, "middle", 1.6)}'''
    worlds_defs = (
        '<filter id="g4" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3.5"/></filter>'
        '<linearGradient id="lampcone" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd894" stop-opacity="0.18"/><stop offset="0.55" stop-color="#ffcf8a" stop-opacity="0.05"/><stop offset="1" stop-color="#ffcf8a" stop-opacity="0"/></linearGradient>'
        '<linearGradient id="goldsheen" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff4d6" stop-opacity="0"/><stop offset="0.5" stop-color="#fff4d6" stop-opacity="0.45"/><stop offset="1" stop-color="#fff4d6" stop-opacity="0"/></linearGradient>'
        + "".join(sheen_defs)
    )
    doc("worlds.svg", GW * C, GH * C, f"{NWORLDS} 个世界", WALL_DESC, worlds_defs, body)

# ================================================================ compact inventory stat panel
ITEMS = [("1090+", "地点"), ("1320+", "NPC 角色"), ("1020+", "玩家身份"), ("2050+", "人物组合"), ("890+", "张力引擎"),
         ("1530+", "日常活动"), ("1320+", "压力事件"), ("3090+", "开场钩子"), ("1650+", "中期转折"), ("1750+", "规矩与风俗")]
EXACT = {
    "开场钩子": 3092, "人物组合": 2052, "规矩与风俗": 1756, "中期转折": 1654, "日常活动": 1538,
    "NPC 角色": 1322, "压力事件": 1321, "地点": 1096, "玩家身份": 1023, "张力引擎": 899,
}
TOTAL_EXACT = sum(EXACT.values())
MATERIAL = "一万五千余项素材"
_ITEMS_BY_LABEL = {lbl: num for num, lbl in ITEMS}
INV_DESC = f"紧凑复古数据面板展示 {TOTAL_EXACT:,} 项独立叙事素材，右侧按数量降序排列分段像素条：{'、'.join(f'{_ITEMS_BY_LABEL[l]} {l}' for l, _ in sorted(EXACT.items(), key=lambda kv: -kv[1]))}。"
BAR_ACCENTS = [
    "#ffd98e", "#ff9bc2", "#ff6fae", "#ef72ca", "#d877e6",
    "#c27af5", "#ac7eff", "#967cf8", "#8477ea", "#746fdc",
]


def inventory():
    GW, GH = 300, 62
    cv = pk.Canvas(GW, GH)
    over, fx, tips = [], [], []
    item_map = {lbl: num for num, lbl in ITEMS}

    # Outer sleek 4-side framed console aligned strictly with genres sleeves (10..290)
    CX0, CY0, CX1, CY1 = 10, 5, 290, GH - 5
    cv.rect(CX0 + 2, CY0 + 2, CX1 + 2, CY1 + 2, "#09050d")
    cv.rect(CX0, CY0, CX1, CY1, "#1c1428")
    SX = 98
    cv.rect(CX0 + 1, CY0 + 1, SX, CY1 - 1, "#231932")
    cv.rect(CX0, CY0, CX1, CY0 + 1, "#634f80")
    cv.rect(CX0, CY1 - 1, CX1, CY1, "#100918")
    cv.rect(CX0, CY0 + 1, CX0 + 1, CY1 - 1, "#4c3b66")
    cv.rect(CX1 - 1, CY0 + 1, CX1, CY1 - 1, "#3b2c52")
    cv.rect(SX, CY0 + 4, SX + 1, CY1 - 4, "#473760")

    # Left hero total card (optically balanced top/bottom padding)
    fx.append(f'<ellipse cx="{(CX0 + SX) / 2 * C}" cy="{(CY0 + 21) * C}" rx="120" ry="48" fill="#b985ff" fill-opacity="0.18" filter="url(#g30)"/>')
    over.append(text((CX0 + SX) / 2 * C, (CY0 + 9.2) * C, "NARRATIVE BUILDING BLOCKS", 11.5, "#b8a9cc", 700, "middle", 1.8, MONO))
    over.append(neon((CX0 + SX) / 2 * C, (CY0 + 22.4) * C, f"{TOTAL_EXACT:,}", 46, "middle", GLOW, CORE, flicker=True))
    over.append(text((CX0 + SX) / 2 * C, (CY0 + 31.2) * C, "项 独 立 叙 事 素 材", 17.5, "#ffe49e", 800, "middle", 2, SANS))
    over.append(text((CX0 + SX) / 2 * C, (CY0 + 38.8) * C, "同世界精准组合 · 绝不随机拼凑", 13.5, "#ccc0dc", 600, "middle", 0.8, SANS))
    for idx, dc in enumerate(["#a874ff", "#ff6fae", "#ffe49e"]):
        cv.rect(CX0 + 38 + idx * 5, CY1 - 7, CX0 + 40 + idx * 5, CY1 - 5, dc)

    # Right 2 cols x 5 rows sorted descending by real count + visible unlit grid + uniform 8px live tip pulse
    sorted_items = sorted(EXACT.items(), key=lambda kv: -kv[1])
    max_val = sorted_items[0][1]
    col_x = [SX + 8, SX + 100]
    row_y0, row_step = CY0 + 5, 9
    for idx, (label, val) in enumerate(sorted_items):
        rx = col_x[idx // 5]
        ry = row_y0 + (idx % 5) * row_step
        acc = BAR_ACCENTS[idx]
        num_col = "#ffe6a0" if val >= 2000 else "#f6f0ff"
        over.append(text(rx * C, (ry + 3.2) * C, label, 15, "#ebe2f5", 700, "start", 0.5, SANS))
        over.append(text((rx + 84) * C, (ry + 3.2) * C, item_map[label], 16, num_col, 900, "end", 0.5, MONO))
        by = ry + 5
        for sx in range(rx, rx + 84, 3):
            cv.rect(sx, by, sx + 2, by + 2, "#2b1f3d")
        fill_w = max(9, round(84 * val / max_val / 3) * 3)
        segs = list(range(rx, rx + fill_w, 3))
        for sx in segs[:-1]:
            cv.rect(sx, by, sx + 2, by + 2, acc)
        last_sx = segs[-1]
        dur = 2.4 + (idx % 5) * 0.35
        beg = idx * 0.27
        tips.append(
            f'<rect x="{last_sx * C}" y="{by * C}" width="{2 * C}" height="{2 * C}" fill="{acc}">'
            f'<animate attributeName="opacity" values="0.52;1;0.52" dur="{dur:.2f}s" begin="-{beg:.2f}s" repeatCount="indefinite"/></rect>'
        )

    body = f'''    <g shape-rendering="crispEdges">{cv.emit(C)}{"".join(tips)}</g>
    {"".join(fx)}
    {"".join(over)}'''
    doc("inventory.svg", GW * C, GH * C, MATERIAL, INV_DESC, "", body)


COVERS = {   # cover art per genre: sky ramp top to bottom, motif
    "宫廷与江湖": (["#0e0b22", "#2a1a3a", "#5a2a3a"], "lantern"),
    "仙侠与志怪": (["#101a2a", "#24405a", "#5a8a9a"], "immortal"),
    "和风与神社": (["#1a0e22", "#3a1a3a", "#8a3a4a"], "torii"),
    "清末民国": (["#1a1428", "#4a3a50", "#a07a5a"], "clocktower"),
    "欧陆古典": (["#1d1742", "#48357c", "#9c669c"], "castle"),
    "邻里与屋檐下": (["#141a30", "#2a3050", "#4a4060"], "flats"),
    "百工与夜铺": (["#0e0b1a", "#22183a", "#4a2a4a"], "shop"),
    "学府与书斋": (["#101428", "#24305a", "#4a5a8a"], "study"),
    "黑道与豪门": (["#14080e", "#3a0e1a", "#7a1e2a"], "mansion"),
    "职场与律政": (["#0a0e1a", "#14243a", "#2a4a5a"], "tower"),
    "谍战与战地": (["#0d1414", "#1f322a", "#465e44"], "front"),
    "舞台与镜头": (["#1a0a1a", "#3a0e2a", "#6a1a3a"], "stage"),
    "赛场与博弈": (["#0a1020", "#142a3a", "#1a3c34"], "arena"),
    "绝境与重工": (["#160d10", "#4a2218", "#b25824"], "plant"),
    "科幻与末世": (["#06061a", "#141a3a", "#2a1a5a"], "planet"),
    "圣堂与魔裔": (["#170e2a", "#3a1e58", "#743884"], "cathedral"),
    "王都与剑魔": (["#1a0e22", "#4a1e3a", "#a2477e"], "sword"),
}
INK = "#100a18"


def cover_art(cv, genre, ax0, at, ax1, ab, rnd, glow):
    """A tiny night scene for one genre's sleeve, inside the art box (ax0, at)-(ax1, ab)."""
    sky, motif = COVERS[genre]
    cv.vgrad(ax0, at, ax1, ab, sky)
    cx = (ax0 + ax1) // 2

    def stars(n=6):
        for _ in range(n):
            cv.put(rnd.randrange(ax0 + 1, ax1 - 1), rnd.randrange(at + 1, at + 12), rnd.choice(["#e9dcff", "#9fa8e0"]))

    def moon(x, y, r=2.5, col="#fff3c8"):
        cv.ellipse(x, y, r, r, col)

    def halo(x, y, r, col, op=0.6):
        glow.append(f'<circle cx="{x * C}" cy="{y * C}" r="{r}" fill="{col}" fill-opacity="{op}" filter="url(#g6)"/>')

    if motif == "lantern":                                          # a hall roof and a red lantern under the eave
        stars()
        cv.poly([(ax0, ab - 7), (ax0 + 5, ab - 12), (ax1 - 5, ab - 12), (ax1, ab - 7)], INK)
        cv.rect(ax0 + 3, ab - 7, ax1 - 3, ab, INK)
        cv.rect(cx - 2, ab - 5, cx + 2, ab, "#ffcf6a")
        cv.rect(ax0 + 7, at + 2, ax0 + 8, at + 8, "#3a2228")
        cv.ellipse(ax0 + 7.5, at + 11, 3, 3.6, lambda x, y: "#ffcf6a" if x == ax0 + 7 else "#e0402f")
        halo(ax0 + 7.5, at + 11, 22, "#ff7a4a", 0.45)
    elif motif == "immortal":                                       # floating peaks in a cloud sea, a flying sword
        for px_, top, w in [(ax0 + 5, at + 9, 5), (ax1 - 7, at + 6, 6)]:
            cv.poly([(px_ - w, ab - 6), (px_, top), (px_ + w, ab - 6)], "#1a2a3a")
            cv.poly([(px_ - 2, top + 4), (px_, top), (px_ + 2, top + 4)], "#cfe8f0")
        cv.rect(ax0, ab - 5, ax1, ab, "#a8c8d8")
        for xx in range(ax0, ax1, 3):
            cv.rect(xx, ab - 6, xx + 2, ab - 5, "#a8c8d8")
        cv.line(cx - 4, at + 5, cx + 3, at + 2, "#9fe9ff")
        halo(cx, at + 3.5, 12, "#9fe9ff", 0.7)
    elif motif == "torii":                                          # a torii gate under a big moon
        moon(cx, at + 8, 6, "#ffd6c0")
        cv.rect(ax0 + 3, at + 13, ax1 - 3, at + 15, "#c8303a")
        cv.rect(ax0 + 2, at + 12, ax1 - 2, at + 13, "#e0404a")
        cv.rect(ax0 + 5, at + 17, ax1 - 5, at + 18, "#c8303a")
        for tx in (ax0 + 7, ax1 - 9):
            cv.rect(tx, at + 13, tx + 2, ab, "#a82030")
        cv.rect(ax0, ab - 2, ax1, ab, INK)
        halo(cx, at + 8, 26, "#ffb0a0", 0.3)
    elif motif == "clocktower":                                     # a customs-house clock tower and a street lamp
        stars(4)
        cv.rect(cx - 3, at + 7, cx + 3, ab, INK)
        cv.poly([(cx - 3, at + 7), (cx, at + 2), (cx + 3, at + 7)], INK)
        cv.ellipse(cx + 0.5, at + 10, 2, 2, "#ffe9a8")
        cv.rect(ax0 + 1, ab - 8, cx - 3, ab, INK)
        cv.rect(cx + 3, ab - 6, ax1 - 1, ab, INK)
        cv.rect(ax1 - 5, ab - 14, ax1 - 4, ab - 6, "#2a2030")
        cv.rect(ax1 - 6, ab - 15, ax1 - 3, ab - 14, "#ffcf6a")
        halo(cx + 0.5, at + 10, 10, "#ffe9a8", 0.7)
        halo(ax1 - 4.5, ab - 14.5, 12, "#ffcf6a", 0.6)
    elif motif == "castle":                                         # towers with moonlight rim and warm windows
        stars()
        for tx, th in [(ax0 + 3, 16), (cx - 3, 20), (ax1 - 8, 14)]:
            cv.rect(tx, ab - th, tx + 6, ab, INK)
            cv.rect(tx, ab - th, tx + 1, ab - 8, "#7e6aa8")
            cv.poly([(tx - 1, ab - th), (tx + 3, ab - th - 5), (tx + 7, ab - th)], INK)
            cv.line(tx - 1, ab - th, tx + 3, ab - th - 5, "#9c88c8")
        cv.rect(ax0 + 1, ab - 8, ax1 - 1, ab, INK)
        cv.rect(cx - 1, ab - 15, cx + 1, ab - 12, "#ffd88a")
        cv.rect(ax0 + 5, ab - 12, ax0 + 7, ab - 10, "#ffcf8a")
        moon(ax0 + 6, at + 5)
        halo(cx, ab - 13.5, 13, "#ffd88a")
    elif motif == "flats":                                          # an apartment block, one pink window
        stars()
        cv.rect(ax0 + 2, ab - 18, ax1 - 2, ab, INK)
        for wy in range(ab - 16, ab - 1, 4):
            for wx in range(ax0 + 4, ax1 - 4, 4):
                cv.rect(wx, wy, wx + 2, wy + 2, "#ffd88a" if (wx * 3 + wy) % 7 == 0 else "#2a2440")
        cv.rect(cx, ab - 12, cx + 2, ab - 10, "#ff8fc4")
        moon(ax0 + 5, at + 5)
        halo(cx + 1, ab - 11, 10, "#ff8fc4", 0.7)
    elif motif == "shop":                                           # a night stall with a striped awning and a lit sign
        stars(4)
        cv.rect(ax0 + 2, ab - 14, ax1 - 2, ab, INK)
        cv.rect(ax0 + 1, ab - 16, ax1 - 1, ab - 13, lambda x, y: "#e0402f" if (x // 2) % 2 else "#f6eedd")
        cv.rect(ax0 + 4, ab - 11, ax1 - 4, ab - 3, "#ffcf8a")
        cv.rect(ax0 + 4, ab - 4, ax1 - 4, ab - 3, "#a86a3a")
        cv.rect(cx - 4, ab - 21, cx + 4, ab - 17, "#ff6fae")
        halo(cx, ab - 7, 22, "#ffcf8a", 0.5)
        halo(cx, ab - 19, 12, "#ff6fae", 0.6)
    elif motif == "study":                                          # an arched library window and a desk lamp over books
        cv.rect(cx - 7, at + 5, cx + 7, ab - 6, "#3a4a7a")
        cv.ellipse(cx, at + 5, 7, 4, "#3a4a7a")
        for gx in (cx - 3, cx + 2):
            cv.rect(gx, at + 2, gx + 1, ab - 6, INK)
        cv.rect(cx - 7, at + 12, cx + 7, at + 13, INK)
        cv.rect(ax0, ab - 6, ax1, ab, INK)
        for k, col in enumerate(["#c8423a", "#3f7fb0", "#e2a33b"]):
            cv.rect(ax0 + 3, ab - 8 - k * 2, ax0 + 11 - k, ab - 6 - k * 2, col)
        cv.rect(ax1 - 6, ab - 12, ax1 - 5, ab - 6, "#2a2030")
        cv.poly([(ax1 - 9, ab - 12), (ax1 - 2, ab - 12), (ax1 - 4, ab - 15), (ax1 - 7, ab - 15)], "#3fa96a")
        halo(ax1 - 5.5, ab - 10, 14, "#ffe9a8", 0.6)
    elif motif == "mansion":                                        # a gated villa under a red moon
        moon(ax1 - 6, at + 5, 3, "#ff6f7f")
        cv.rect(ax0 + 3, ab - 15, ax1 - 3, ab, INK)
        cv.poly([(ax0 + 1, ab - 15), (cx, ab - 21), (ax1 - 1, ab - 15)], INK)
        for wx in range(ax0 + 6, ax1 - 6, 5):
            cv.rect(wx, ab - 12, wx + 2, ab - 9, "#ffb84a")
        for gx in range(ax0, ax1, 2):
            cv.rect(gx, ab - 5, gx + 1, ab, "#2a1a20")
        cv.rect(ax0, ab - 5, ax1, ab - 4, "#2a1a20")
        halo(cx, ab - 10, 20, "#ffb84a", 0.4)
    elif motif == "tower":                                          # a skyscraper in the rain, the top floor lit
        cv.rect(cx - 5, at + 4, cx + 5, ab, INK)
        cv.rect(cx - 1, at + 1, cx, at + 4, INK)
        cv.rect(cx - 4, at + 6, cx + 4, at + 8, "#9fe9ff")
        for wy in range(at + 11, ab - 1, 3):
            cv.rect(cx - 3, wy, cx + 3, wy + 1, "#1e2a3a")
        cv.rect(ax0 + 1, ab - 6, ax0 + 6, ab, INK)
        cv.rect(ax1 - 6, ab - 9, ax1 - 1, ab, INK)
        for _ in range(14):
            rx, ry = rnd.randrange(ax0, ax1 - 1), rnd.randrange(at, ab - 3)
            cv.put(rx, ry, "#6a8aa8")
            cv.put(rx + 1, ry + 1, "#4a6a88")
        glow.append(f'<rect x="{(cx - 4) * C}" y="{(at + 6) * C}" width="{8 * C}" height="{2 * C}" fill="#9fe9ff" filter="url(#g6)" opacity="0.9"/>')
    elif motif == "front":                                          # crossing searchlights over barbed wire
        stars(4)
        for x0_, x1_ in [(ax0 + 4, cx + 7), (ax1 - 4, cx - 7)]:
            glow.append(f'<polygon points="{x0_ * C},{(ab - 6) * C} {(x0_ + 1) * C},{(ab - 6) * C} {(x1_ + 4) * C},{at * C} {(x1_ - 3) * C},{at * C}" '
                        f'fill="#f5f5c8" fill-opacity="0.34"/>')
            glow.append(f'<polygon points="{x0_ * C},{(ab - 6) * C} {(x0_ + 1) * C},{(ab - 6) * C} {(x1_ + 1.5) * C},{at * C} {(x1_ - 0.5) * C},{at * C}" '
                        f'fill="#ffffe6" fill-opacity="0.28"/>')
        cv.poly([(ax0, ab), (ax0, ab - 6), (ax0 + 6, ab - 9), (ax0 + 10, ab - 6), (cx + 4, ab - 7), (ax1, ab - 5), (ax1, ab)], INK)
        cv.rect(ax0 + 4, ab - 7, ax0 + 8, ab - 6, "#ffd27a")
        halo(ax0 + 6, ab - 6.5, 10, "#ffd27a", 0.65)
        for xx in range(ax0, ax1, 3):
            cv.put(xx, ab - 11 + (xx % 2), "#b4b8a0")
            cv.put(xx + 1, ab - 10, "#9ea28a")
        for px_ in (ax0 + 2, cx, ax1 - 3):
            cv.rect(px_, ab - 12, px_ + 1, ab - 6, "#4d5244")
    elif motif == "stage":                                          # red curtains, a spotlight on an empty mic
        cv.rect(ax0, at, ax1, at + 3, "#8a1e2a")
        for xx in range(ax0, ax0 + 6):
            cv.rect(xx, at, xx + 1, ab - 3 - (xx - ax0), "#a82838" if xx % 2 else "#7a1424")
        for xx in range(ax1 - 6, ax1):
            cv.rect(xx, at, xx + 1, ab - 3 - (ax1 - 1 - xx), "#a82838" if xx % 2 else "#7a1424")
        glow.append(f'<polygon points="{(cx - 1) * C},{(at + 3) * C} {(cx + 1) * C},{(at + 3) * C} {(cx + 6) * C},{(ab - 3) * C} {(cx - 6) * C},{(ab - 3) * C}" '
                    f'fill="#fff0c8" fill-opacity="0.3"/>')
        cv.rect(ax0, ab - 3, ax1, ab, "#3a2418")
        cv.rect(cx, ab - 12, cx + 1, ab - 3, "#c8c8d0")
        cv.ellipse(cx + 0.5, ab - 13, 1.6, 2, "#e8e8f0")
    elif motif == "arena":                                          # floodlights over a nocturnal pitch
        stars(3)
        for fx in (ax0 + 3, ax1 - 4):
            cv.rect(fx, at + 6, fx + 1, ab - 6, "#3a3e52")
            cv.rect(fx - 2, at + 4, fx + 3, at + 6, "#f0f4ff")
            halo(fx + 0.5, at + 5, 16, "#cfe8ff", 0.65)
        cv.poly([(ax0, ab), (ax0 + 4, ab - 7), (ax1 - 4, ab - 7), (ax1, ab)], lambda x, y: "#1b4a32" if (x // 2) % 2 else "#22583c")
        cv.line(ax0 + 4, ab - 4, ax1 - 4, ab - 4, "#9fd2b2")
        cv.line(cx, ab - 7, cx, ab - 1, "#9fd2b2")
    elif motif == "plant":                                          # a crane, chimney and glowing molten furnace windows
        cv.rect(ax0 + 3, at + 6, ax0 + 6, ab, INK)
        cv.rect(ax0 + 3, at + 6, ax0 + 4, ab, "#4a3234")
        cv.rect(ax0 + 3, at + 6, ax1 - 2, at + 7, "#342428")
        cv.line(ax1 - 4, at + 7, ax1 - 4, at + 14, "#6a5256")
        cv.rect(ax1 - 6, at + 14, ax1 - 2, at + 16, "#f0b44c")
        cv.rect(cx, ab - 14, cx + 4, ab, INK)
        cv.rect(cx, ab - 14, cx + 1, ab, "#4a3030")
        cv.rect(ax0 + 1, ab - 7, ax1 - 1, ab, INK)
        for wx in (ax0 + 7, ax0 + 11, ax1 - 6):
            cv.rect(wx, ab - 5, wx + 2, ab - 2, "#ffae42")
        halo(cx, ab - 3.5, 18, "#ff7b2e", 0.5)
        cv.rect(ax0 + 4, at + 4, ax0 + 5, at + 5, "#ff4a4a")
        glow.append(f'<circle cx="{(ax0 + 4.5) * C}" cy="{(at + 4.5) * C}" r="11" fill="#ff4a4a" fill-opacity="0.85" filter="url(#g6)">'
                    '<animate attributeName="fill-opacity" values="0.9;0.15;0.9" dur="1.6s" repeatCount="indefinite"/></circle>')
        for k in range(3):
            cv.ellipse(cx + 2 + k, ab - 16 - k * 3, 2 + k * 0.5, 1.5, "#785a56")
    elif motif == "planet":                                         # a ringed planet and a rising rocket
        stars(9)
        cv.ellipse(ax0 + 9, at + 9, 5, 5, lambda x, y: "#c87ae0" if y < at + 9 else "#7a3a9a")
        cv.line(ax0 + 1, at + 11, ax0 + 17, at + 7, "#ffd6a0")
        cv.rect(ax1 - 6, ab - 15, ax1 - 3, ab - 6, "#e8e8f0")
        cv.poly([(ax1 - 6, ab - 15), (ax1 - 4.5, ab - 19), (ax1 - 3, ab - 15)], "#e8e8f0")
        cv.rect(ax1 - 6, ab - 6, ax1 - 3, ab - 4, "#ffcf6a")
        halo(ax1 - 4.5, ab - 4, 12, "#ff9a4a", 0.8)
        cv.rect(ax0, ab - 2, ax1, ab, INK)
    elif motif == "cathedral":                                      # a gothic church with moonlight rims & stained glass
        stars(4)
        cv.rect(cx - 6, ab - 16, cx + 6, ab, INK)
        cv.poly([(cx - 7, ab - 16), (cx, ab - 23), (cx + 7, ab - 16)], INK)
        cv.line(cx - 7, ab - 16, cx, ab - 23, "#8a62b0")
        for sx in (ax0 + 1, ax1 - 5):
            cv.rect(sx, ab - 20, sx + 4, ab, INK)
            cv.poly([(sx, ab - 20), (sx + 2, ab - 25), (sx + 4, ab - 20)], INK)
            cv.line(sx, ab - 20, sx + 2, ab - 25, "#8a62b0")
            cv.rect(sx + 2, ab - 14, sx + 3, ab - 9, "#c9a2ff")
        cv.ellipse(cx + 0.5, ab - 13, 3, 3, lambda x, y: "#ff6fae" if (x + y) % 2 else "#a874ff")
        cv.rect(cx - 1, ab - 6, cx + 2, ab, "#ffcf6a")
        halo(cx + 0.5, ab - 13, 15, "#d080ff", 0.75)
    else:                                                           # a sword in the ground under a red moon
        moon(ax0 + 7, at + 6, 3.5, "#ff6f7f")
        cv.poly([(ax0, ab), (ax0, ab - 4), (cx, ab - 7), (ax1, ab - 3), (ax1, ab)], INK)
        cv.rect(cx, ab - 20, cx + 2, ab - 6, "#d8dcea")
        cv.rect(cx, ab - 20, cx + 1, ab - 6, "#ffffff")
        cv.rect(cx - 3, ab - 21, cx + 5, ab - 20, "#e2b25a")
        cv.rect(cx, ab - 24, cx + 2, ab - 21, "#6a3a2a")
        glow.append(f'<rect x="{cx * C}" y="{(ab - 20) * C}" width="{2 * C}" height="{14 * C}" fill="#c8d8ff" filter="url(#g6)" opacity="0.7"/>')


GENRES_DESC = ("世界分类展示：{} 盒录像带封面朝外排成两排，一类一盒：{}；每盒顶上写着这一类有几个世界，"
               "封面是这一类的小夜景，底下贴着分类名。全部世界已开放，整面录像带墙就在 README 的下方。")


def genres():
    """The short version for the top of the README: one face-out sleeve per genre, two rows straight on the wall, in wall order."""
    assert set(COVERS) == {r for r, _, _ in REGIONS}
    rows, k = [], 0
    for half in (BANDS[:2], BANDS[2:]):                             # shelves I+II on top, III+IV below
        n = sum(c for _, c in half)
        rows.append(REGIONS[k:k + n])
        k += n
    GW, GH = 300, 138
    rnd = random.Random(53)
    cv = pk.Canvas(GW, GH)
    over, glow = [], []
    X0, X1 = 8, 292
    PW = 62                                                         # brass plaque
    px0 = (X0 + X1) // 2 - PW // 2
    cv.rect(px0 + 1, 5, px0 + PW + 1, 15, "#0e080a")
    cv.rect(px0, 4, px0 + PW, 14, "#cfa850")
    cv.rect(px0, 4, px0 + PW, 5, "#f5dc94")
    cv.rect(px0, 13, px0 + PW, 14, "#8a6a28")
    for sx in (px0 + 2, px0 + PW - 3):
        cv.put(sx, 9, "#7a5a20")
    over.append(text((px0 + PW / 2) * C, 10.9 * C, f"世界分类 · {len(REGIONS)} 类", 17, "#452e0c", 900, "middle", 2, SANS))
    pitch = (X1 - X0) / max(len(r) for r in rows)
    base_size = min(16, (pitch - 8) * C / 5)                        # balanced size for 4-5 char labels
    TOP, SLEEVE, GAP = 20, 48, 5                                    # two rows of sleeves straight on the wall, no frame between them
    BOT = TOP + len(rows) * (SLEEVE + GAP) - GAP                    # the foot of the lower row
    for ri, row in enumerate(rows):
        y0 = TOP + ri * (SLEEVE + GAP)
        y1 = y0 + SLEEVE
        x_off = (len(rows[1]) - len(row)) * pitch / 2 if len(row) < max(len(r) for r in rows) else 0
        for i, (genre, rc, worlds_) in enumerate(row):
            x0 = int(X0 + x_off + i * pitch + 2)
            x1 = int(X0 + x_off + (i + 1) * pitch - 2)
            cv.rect(x0 + 2, y0 + 2, x1 + 2, y1 + 2, "#0b070c")        # drop shadow on the wall
            cv.rect(x0, y0, x1, y1, "#1c1820")                      # the sleeve
            cv.rect(x0, y0, x1, y0 + 1, "#524a5e")
            cv.rect(x0 + 1, y0 + 1, x1 - 1, y0 + 7, rc)             # genre band with the world count
            cover_art(cv, genre, x0 + 1, y0 + 7, x1 - 1, y0 + 33, rnd, glow)
            cv.rect(x0 + 1, y0 + 33, x1 - 1, y1 - 1, "#f2ead8")     # genre label
            cv.rect(x0 + 1, y0 + 33, x1 - 1, y0 + 34, "#ffffff")
            cv.rect(x0 + 1, y0 + 34, x0 + 3, y1 - 1, rc)
            cnt_col = "#ffe6a0" if len(worlds_) >= 17 else "#ffffff"
            over.append(text((x0 + x1) / 2 * C, (y0 + 5.6) * C, f"{len(worlds_)} 个世界", 13.5, cnt_col, 800, "middle", 0.8, SANS,
                             'stroke="#241420" stroke-width="2.6" paint-order="stroke"'))
            lbl_size = 14.5 if len(genre) >= 6 else round(base_size, 1)
            lbl_sp = -0.3 if len(genre) >= 6 else 0
            over.append(text((x0 + x1 + 2) / 2 * C, (y0 + 41.0) * C, genre, lbl_size, "#201724", 900, "middle", lbl_sp, SANS))
    sleeves_body = f'''    <g shape-rendering="crispEdges">{cv.emit(C)}</g>
    {"".join(glow)}
    {"".join(over)}'''
    body = sleeves_body + f'\n    {text(GW * C / 2, (BOT + 10.2) * C, f"· 全部 {NWORLDS} 个世界已开放，下方就是整面录像带墙 ·", 17.5, "#d8cde4", 600, "middle", 1.5)}'
    doc("genres.svg", GW * C, GH * C, "世界分类", GENRES_DESC.format(len(REGIONS), "、".join(r for r, _, _ in REGIONS)), "", body)
    PARTS["genres.svg:lib"] = (GW * C, 126 * C, "", sleeves_body)


banner("section-proof.svg", "体验切片", "真实机制驱动下的对局现场", 1, (1180, 222, 1490, 352), v_proof)      # the monitor
banner("section-why.svg", "为什么不会崩盘", "模型写故事，本地引擎守事实", 2, (70, 300, 470, 468), v_why)       # clock and desk
banner("section-worlds.svg", "内置世界库", "跨时代独立世界框架，开局即入戏", 3, (990, 0, 1430, 168), v_worlds)   # the city outside
banner("section-start.svg", "怎么开始", "不用记语法，直接说大白话", 4, (610, 190, 1050, 375), v_start)          # the guitar
banner("section-install.svg", "安装", "只需交给 AI 操作，原生 SKILL", 5, (1440, 280, 1800, 431), v_install)           # the laptop
worlds()
genres()
inventory()


def library():
    """The world-library banner, the genre sleeves, the compact inventory console, and the bottom tape-wall pointer
    stacked into one seamless picture (1200x976): 2D crop fade protects the globe shelf with zero duplicate-wall hack."""
    names = ["section-worlds.svg:lib", "genres.svg:lib", "inventory.svg"]
    W = PARTS[names[0]][0]
    H = 976
    defs = "".join(PARTS[n][2] for n in names)
    y, parts = 0, []
    for n in names:
        parts.append(f'    <g transform="translate(0 {y})">{PARTS[n][3]}</g>')
        y += PARTS[n][1]
    parts.append(f'    {text(W / 2, 952, f"· 全部 {NWORLDS} 个世界已开放，下方就是整面录像带墙 ·", 17.5, "#dfd4ec", 600, "middle", 1.5)}')
    doc("world-library.svg", W, H, "内置世界库",
        f"内置世界库：跨时代独立世界框架，开局即入戏。{GENRES_DESC.format(len(REGIONS), '、'.join(r for r, _, _ in REGIONS))}{INV_DESC}",
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
        """An axis-aligned 1-cell wire from (x0, y0) to (x1,
        y1) with a pixel arrowhead at the far end."""
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
    for k, line in enumerate(["一次记录 = 原子事务", "重试不会重复推进", "同一种子，同一结果"]):
        over.append(text((NX0 + 5) * C, (NY0 + 13 + k * 9) * C, line, 17, "#5a3a20", 800, "start", 1))
    wire(57, 57, 79, 57)
    wire(221, 57, 182, 57)
    over.append(text(201 * C, 54 * C, "按需读取", 14, "#bfb2c8", 700, "middle", 1))
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
    {neon(600, 82, "SKILL 架构", 52, "middle", GLOW, CORE, flicker=True)}
    {text(600, 122, "无需理会，当正常 SKILL 使用就行", 21, SUBT, 600, "middle", 2)}
    {dotline(GW * C, 0, 2.4)}'''
    doc("architecture.svg", GW * C, GH * C, "SKILL 架构",
        "玩家对 Agent 宿主说话，宿主按 SKILL.md 的规则写正文，用 JSON 调用本地运行时并拿回结果和下一回合上下文。"

        "运行时只用 Python 标准库，分 adapters/cli、application、content、projections、persistence、domain 六层：application 是唯一写入口，"
        "domain 只放纯函数，persistence 把每次记录写成单个 SQLite 原子事务，存进用户数据目录。世界源文件由 tools 编译成只读世界包，开局时读取。", "", body)


architecture()
