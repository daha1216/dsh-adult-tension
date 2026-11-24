"""Hero from the user's own lo-fi bedroom picture (Option C — AVG Cinema Dialogue Rail + Framed Neon Marquee):
the picture is embedded untouched; layered ambient SMIL effects (city lights, aviation beacons, neon signs,
three-point cinematic lighting, ticking clock, harmonized screens, dust, curved guitar notes), a framed neon
rooftop marquee signboard, an unobstructed bottom AVG Surface<->Inner dialogue rail, a synchronized TENSION
meter selling-point strip, and a harmonized three-column feature band sit cleanly on top and below."""
import base64
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import overlay_fx as fx  # noqa: E402
import pixkit as pk  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "source", os.environ.get("OVERLAY_SRC", "bedroom.webp"))
OUT = os.environ.get("OVERLAY_OUT") or os.path.join(HERE, "..", "..", ".github", "readme-lofi", "hero.svg")
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif"
MONO = "ui-monospace,'Cascadia Mono',Consolas,monospace"
TITLE_FONT = "'Arial Black','Segoe UI Black','Helvetica Neue',Impact,sans-serif"

raw = open(SRC, "rb").read()
vp = raw.index(b"VP8X")
W, IW, IH = 1280, int.from_bytes(raw[vp + 12:vp + 15], "little") + 1, int.from_bytes(raw[vp + 15:vp + 18], "little") + 1
CROP = int(os.environ.get("OVERLAY_CROP", 0))
S = W / IW
H = round((IH - CROP) * S)
STRIP_H = 84
BAND_H = 128
BY = H + STRIP_H
H2 = BY + BAND_H
CW = W / 3
DATA = base64.b64encode(raw).decode()

index = json.load(open(os.path.join(HERE, "..", "..", "skill", "adult-tension", "content", "index.json"), encoding="utf-8"))
NWORLDS = sum(1 for w in index["worlds"] if w["status"] == "released")
T = fx.T


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def dots_v(x, y0, y1, c):
    return f'<path fill="{c}" d="{"".join(f"M{x} {y}h2v2h-2z" for y in range(y0, y1, 6))}"/>'


def pxborder(x0, y0, x1, y1, fill, edge, cut=4, t=2, fill_op="0.88"):
    """Crisp pixel-stepped chamfered box with translucent dark-glass fill and 1-step pixel border."""
    w, h = x1 - x0, y1 - y0
    outer = (
        f'<rect x="{x0 + cut}" y="{y0}" width="{w - 2 * cut}" height="{t}" fill="{edge}"/>'
        f'<rect x="{x0 + cut}" y="{y1 - t}" width="{w - 2 * cut}" height="{t}" fill="{edge}"/>'
        f'<rect x="{x0}" y="{y0 + cut}" width="{t}" height="{h - 2 * cut}" fill="{edge}"/>'
        f'<rect x="{x1 - t}" y="{y0 + cut}" width="{t}" height="{h - 2 * cut}" fill="{edge}"/>'
        f'<rect x="{x0 + t}" y="{y0 + t}" width="{cut - t}" height="{cut - t}" fill="{edge}"/>'
        f'<rect x="{x1 - cut}" y="{y0 + t}" width="{cut - t}" height="{cut - t}" fill="{edge}"/>'
        f'<rect x="{x0 + t}" y="{y1 - cut}" width="{cut - t}" height="{cut - t}" fill="{edge}"/>'
        f'<rect x="{x1 - cut}" y="{y1 - cut}" width="{cut - t}" height="{cut - t}" fill="{edge}"/>'
    )
    inner = (
        f'<g opacity="{fill_op}">'
        f'<rect x="{x0 + cut}" y="{y0 + t}" width="{w - 2 * cut}" height="{h - 2 * t}" fill="{fill}"/>'
        f'<rect x="{x0 + t}" y="{y0 + cut}" width="{w - 2 * t}" height="{h - 2 * cut}" fill="{fill}"/>'
        f'</g>'
    )
    return inner + outer


def neon_crisp(x, y, s, size, glow_col, core_col, anchor="start", spacing=2, weight=800, shadow_col="#12061c", blur="g4"):
    """Crisp high-contrast neon typography matching lofi_set.py (deep dark shadow + tight glow + warm-white core)."""
    d = max(2, round(size / 18))
    return (
        f'<text x="{x + d}" y="{y + d}" font-family="{SANS}" font-size="{size}" font-weight="{weight}" fill="{shadow_col}" text-anchor="{anchor}" letter-spacing="{spacing}" opacity="0.92">{esc(s)}</text>'
        f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="{size}" font-weight="{weight}" fill="{glow_col}" text-anchor="{anchor}" letter-spacing="{spacing}" filter="url(#{blur})" opacity="0.72">{esc(s)}</text>'
        f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="{size}" font-weight="{weight}" fill="{core_col}" text-anchor="{anchor}" letter-spacing="{spacing}" stroke="{glow_col}" stroke-width="{max(0.6, size / 44):.1f}" paint-order="stroke">{esc(s)}</text>'
    )


def px_icon(rows, pal, x, y, px=5):
    cells = "".join(
        f'<rect x="{x + c * px}" y="{y + r * px}" width="{px}" height="{px}" fill="{pal[ch]}"/>'
        for r, row in enumerate(rows) for c, ch in enumerate(row) if ch != "."
    )
    return f'<g shape-rendering="crispEdges">{cells}</g>'


# ==============================================================================
# FRAMED NEON ROOFTOP MARQUEE SIGNBOARD
# ==============================================================================
def marquee_title():
    x0, y0, x1, y1 = 682, 11, 1004, 122
    cx = (x0 + x1) / 2
    frame = (
        f'<ellipse cx="{cx}" cy="{(y0 + y1) / 2}" rx="185" ry="62" fill="#ff5fa8" fill-opacity="0.14" filter="url(#g18)">'
        f'<animate attributeName="fill-opacity" values="0.11;0.20;0.11" dur="5.4s" repeatCount="indefinite"/></ellipse>'
        f'<g shape-rendering="crispEdges">'
        + pxborder(x0, y0, x1, y1, "#12071e", "#ff74b5", cut=6, t=2, fill_op="0.74")
        + pxborder(x0 + 6, y0 + 6, x1 - 6, y1 - 6, "#12071e", "#b48aff", cut=4, t=1, fill_op="0.0")
        + f'<rect x="{x0 + 9}" y="{y0 + 9}" width="3" height="3" fill="#e8c68a"/>'
        + f'<rect x="{x1 - 12}" y="{y0 + 9}" width="3" height="3" fill="#e8c68a"/>'
        + f'<rect x="{x0 + 9}" y="{y1 - 12}" width="3" height="3" fill="#e8c68a"/>'
        + f'<rect x="{x1 - 12}" y="{y1 - 12}" width="3" height="3" fill="#e8c68a"/>'
        + "</g>"
    )

    def marquee_word(word, y, glow, stroke, spacing, buzz_idx=None):
        sh = f'<text x="{cx + 3}" y="{y + 3}" font-family="{TITLE_FONT}" font-size="36" font-weight="900" fill="#0d0416" text-anchor="middle" letter-spacing="{spacing}">{word}</text>'
        gl = f'<text x="{cx}" y="{y}" font-family="{TITLE_FONT}" font-size="36" font-weight="900" fill="{glow}" text-anchor="middle" letter-spacing="{spacing}" filter="url(#g6)" opacity="0.85">{word}</text>'
        spans = []
        for idx, ch in enumerate(word):
            anim = (
                fx.blink(T, [(0, 1), (8.6, 0.42), (8.72, 1), (8.88, 0.52), (8.96, 1)], attr="fill-opacity")
                if buzz_idx is not None and idx == buzz_idx else ""
            )
            spans.append(f"<tspan>{anim}{ch}</tspan>")
        core = (
            f'<text x="{cx}" y="{y}" font-family="{TITLE_FONT}" font-size="36" font-weight="900" '
            f'fill="#fff7fc" stroke="{stroke}" stroke-width="1.2" paint-order="stroke" text-anchor="middle" letter-spacing="{spacing}">'
            + "".join(spans) + "</text>"
        )
        return sh + gl + core

    sub = f'<text x="{cx}" y="108" font-family="{MONO}" font-size="11.5" font-weight="700" fill="#edd098" text-anchor="middle" letter-spacing="2.2">NIGHT SHIFT · {NWORLDS} WORLDS</text>'
    return (
        frame
        + marquee_word("ADULT", 50, "#ff6fae", "#ff96c8", 6, buzz_idx=3)
        + marquee_word("TENSION", 87, "#c48aff", "#d4a8ff", 4, buzz_idx=4)
        + sub
    )


# ==============================================================================
# BOTTOM AVG SURFACE <-> INNER DIALOGUE RAIL (UNOBSTRUCTED BEDROOM COMPOSITION)
# ==============================================================================
def avg_dialogue_rail():
    x0, y0 = 264, 412
    bw, bh = 752, 72
    x1, y1 = x0 + bw, y0 + bh

    surf_text = "「吵到你了？这就停。门没锁，拿完东西就走。」"
    inner_text = "「……别光站门外听，进来把门反锁啊。」"

    surf_vis = fx.blink(T, [(0, 1), (7.20, 0), (19.48, 1)])
    inner_vis = fx.blink(T, [(0, 0), (7.20, 1), (19.48, 0)])

    def px_chevron(cx, cy, col):
        return (
            f'<g fill="{col}" shape-rendering="crispEdges">'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;0 3;0 0" dur="1.1s" repeatCount="indefinite"/>'
            f'<rect x="{cx}" y="{cy}" width="12" height="2"/>'
            f'<rect x="{cx + 2}" y="{cy + 2}" width="8" height="2"/>'
            f'<rect x="{cx + 4}" y="{cy + 4}" width="4" height="2"/>'
            f'<rect x="{cx + 5}" y="{cy + 6}" width="2" height="2"/>'
            f'</g>'
        )

    surf_g = (
        f'<g opacity="1">{surf_vis}'
        + '<g shape-rendering="crispEdges">'
        + pxborder(x0, y0, x1, y1, "#120820", "#9c8ac8", cut=4, t=2, fill_op="0.86")
        + f'<rect x="{x0 + 14}" y="{y0 + 13}" width="92" height="46" fill="#251842"/>'
        + f'<rect x="{x0 + 14}" y="{y0 + 13}" width="4" height="46" fill="#a894e0"/>'
        + "</g>"
        + f'<text x="{x0 + 62}" y="{y0 + 35}" font-family="{SANS}" font-size="15" font-weight="800" fill="#e6defc" text-anchor="middle" letter-spacing="1">嘴上说</text>'
        + f'<text x="{x0 + 62}" y="{y0 + 52}" font-family="{MONO}" font-size="11" font-weight="700" fill="#a999d0" text-anchor="middle" letter-spacing="1.2">SURFACE</text>'
        + f'<text x="{x0 + 124}" y="{y0 + 44.5}" font-family="{SANS}" font-size="23.5" font-weight="700" fill="#efe9fb" letter-spacing="1.3">{esc(surf_text)}</text>'
        + px_chevron(x1 - 30, y0 + 35, "#b49eff")
        + "</g>"
    )

    inner_g = (
        f'<g opacity="0">{inner_vis}'
        + f'<rect x="{x0 - 2}" y="{y0 - 2}" width="{bw + 4}" height="{bh + 4}" rx="6" fill="none" stroke="#ff5fa8" stroke-width="5" filter="url(#g6)" opacity="0.55">'
        + '<animate attributeName="opacity" values="0.42;0.74;0.42" dur="1.6s" repeatCount="indefinite"/></rect>'
        + '<g shape-rendering="crispEdges">'
        + pxborder(x0, y0, x1, y1, "#1f0824", "#ff6fae", cut=4, t=2, fill_op="0.90")
        + f'<rect x="{x0 + 14}" y="{y0 + 13}" width="92" height="46" fill="#4f1535"/>'
        + f'<rect x="{x0 + 14}" y="{y0 + 13}" width="4" height="46" fill="#ff6fae"/>'
        + "</g>"
        + f'<text x="{x0 + 62}" y="{y0 + 35}" font-family="{SANS}" font-size="15" font-weight="800" fill="#ffe6f2" text-anchor="middle" letter-spacing="1">心里想</text>'
        + f'<text x="{x0 + 62}" y="{y0 + 52}" font-family="{MONO}" font-size="11" font-weight="700" fill="#ffa8d0" text-anchor="middle" letter-spacing="1.2">INNER</text>'
        + '<g clip-path="url(#avgReveal)">'
        + neon_crisp(x0 + 124, y0 + 44.5, inner_text, 23.5, "#ff6fae", "#fff4fa", "start", 1.3, 800, "#1c0514", "g4")
        + "</g>"
        + px_chevron(x1 - 30, y0 + 35, "#ff74b5")
        + "</g>"
    )

    scan = (
        f'<g opacity="0">'
        f'<animate attributeName="opacity" values="0;0;0.95;0.95;0;0;0.88;0.88;0;0" keyTimes="0;0.359;0.360;0.388;0.390;0.959;0.960;0.974;0.976;1" dur="{T}s" repeatCount="indefinite"/>'
        f'<animateTransform attributeName="transform" type="translate" values="382 0;382 0;892 0;892 0;382 0;382 0" keyTimes="0;0.360;0.388;0.960;0.974;1" dur="{T}s" repeatCount="indefinite"/>'
        f'<rect x="-6" y="{y0 + 6}" width="16" height="{bh - 12}" fill="#ff5fa8" filter="url(#g4)" opacity="0.75"/>'
        f'<rect x="0" y="{y0 + 4}" width="4" height="{bh - 8}" fill="#fff0f8" shape-rendering="crispEdges"/>'
        f'</g>'
    )
    return surf_g + inner_g + scan


# ==============================================================================
# SELLING-POINT STRIP WITH SYNCHRONIZED TENSION METER (CALM <-> PULSE)
# ==============================================================================
def selling_strip():
    top_line = (
        f'<rect y="{H - 4}" width="{W}" height="10" fill="url(#lineg)" fill-opacity="0.28" filter="url(#g6)"/>'
        f'<g fill="url(#lineg)" shape-rendering="crispEdges">'
        f'<path d="{"".join(f"M{x} {H}h2v2h-2z" for x in range(0, W, 4))}"/>'
        f'<path opacity="0.45" d="{"".join(f"M{x} {H + 2}h2v2h-2z" for x in range(2, W, 4))}"/>'
        f'<path opacity="0.18" d="{"".join(f"M{x} {H + 4}h2v2h-2z" for x in range(0, W, 8))}"/></g>'
    )
    badge = (
        f'<g><animate attributeName="opacity" values="1;1;0.74;1;1" keyTimes="0;0.86;0.87;0.89;1" dur="5.6s" repeatCount="indefinite"/>'
        f'<rect x="36" y="{H + 15}" width="108" height="54" rx="10" fill="none" stroke="#b67aff" stroke-width="5" filter="url(#g6)" opacity="0.85"/>'
        f'<rect x="36" y="{H + 15}" width="108" height="54" rx="10" fill="#1a0c2e" stroke="#e4cfff" stroke-width="2.2"/>'
        + neon_crisp(90, H + 55, "18+", 35, "#b67aff", "#fff7fc", "middle", 1, 900)
        + "</g>"
    )
    headline = (
        neon_crisp(168, H + 55, "尺度全开", 32, "#c08cff", "#fff7fc", "start", 2, 800)
        + f'<rect x="318" y="{H + 39}" width="7" height="7" fill="#ff74b5"/>'
        + neon_crisp(340, H + 55, "真实成人互动", 32, "#c08cff", "#fff7fc", "start", 2, 800)
    )

    mx0 = 601
    mid_parts = [
        dots_v(562, H + 18, H + 68, "#6a5488"),
        f'<text x="{mx0}" y="{H + 31}" font-family="{MONO}" font-size="12.5" font-weight="700" fill="#b6a4d8" letter-spacing="2.2">TENSION</text>',
        f'<text x="{mx0 + 274.5}" y="{H + 31}" font-family="{MONO}" font-size="12.5" font-weight="700" fill="#c4b3e6" text-anchor="end" letter-spacing="1.4" opacity="1">'
        f'{fx.blink(T, [(0, 1), (7.20, 0), (19.48, 1)])}CALM</text>',
        f'<text x="{mx0 + 274.5}" y="{H + 31}" font-family="{MONO}" font-size="12.5" font-weight="700" fill="#ff80bc" text-anchor="end" letter-spacing="1.4" opacity="0">'
        f'{fx.blink(T, [(0, 0), (7.20, 1), (19.48, 0)])}PULSE</text>',
    ]
    colors = [
        "#7a58c8", "#845dd0", "#8e62d8", "#9868df", "#a46ee5", "#b272e8", "#c274e6", "#d274df",
        "#e073d4", "#eb72c7", "#f470ba", "#fa6fae", "#ff6ea4", "#ff689b", "#ff5e92", "#ff4f86",
    ]
    for k in range(16):
        bx = mx0 + k * 17.5
        col = colors[k]
        mid_parts.append(f'<rect x="{bx:.1f}" y="{H + 43}" width="12" height="17" fill="#2b1940" opacity="0.85"/>')
        if k < 5:
            mid_parts.append(
                f'<rect x="{bx:.1f}" y="{H + 43}" width="12" height="17" fill="{col}">'
                f'<animate attributeName="opacity" values="0.75;0.95;0.75;1;0.85;0.75" keyTimes="0;0.18;0.36;0.55;0.82;1" dur="{T}s" repeatCount="indefinite"/></rect>'
            )
        else:
            t_on = 7.2 + (k - 5) * 0.045
            t_off = 19.2 - (15 - k) * 0.02
            if k == 12:
                pairs = [(0, 0.14), (t_on, 0.96), (13.4, 0.82), (14.4, 1.0), (t_off, 0.14)]
            elif k == 13:
                pairs = [(0, 0.14), (t_on, 0.95), (12.0, 0.72), (13.1, 0.98), (16.0, 0.78), (17.2, 0.96), (t_off, 0.14)]
            elif k == 14:
                pairs = [(0, 0.14), (t_on, 0.92), (10.2, 0.48), (10.9, 0.96), (13.8, 0.55), (15.0, 0.94), (t_off, 0.14)]
            elif k == 15:
                pairs = [(0, 0.14), (t_on, 0.88), (9.6, 0.32), (10.6, 0.82), (11.5, 0.38), (14.6, 0.92), (16.2, 0.42), (t_off, 0.14)]
            else:
                pairs = [(0, 0.16), (t_on, 0.95), (t_off, 0.16)]
            mid_parts.append(
                f'<rect x="{bx:.1f}" y="{H + 43}" width="12" height="17" fill="{col}" opacity="0.16">'
                f'{fx.blink(T, pairs)}</rect>'
            )
        mid_parts.append(f'<rect x="{bx:.1f}" y="{H + 43}" width="12" height="2" fill="#ffffff" opacity="0.18"/>')
    meter = f'<g shape-rendering="crispEdges">{"".join(mid_parts)}</g>'

    right_brand = (
        dots_v(W - 366, H + 18, H + 68, "#6a5488")
        + f'<text x="{W - 36}" y="{H + 36}" font-family="{MONO}" font-size="13.5" font-weight="700" fill="#b4a3d8" text-anchor="end" letter-spacing="2.8">REBUILT FROM SCRATCH</text>'
        + neon_crisp(W - 36, H + 66, "Claude Opus 5.5 从零重构", 23, "#b48aff", "#f3ecff", "end", 1, 800)
    )
    sweep = (
        f'<rect x="-260" y="{H + 6}" width="260" height="78" fill="url(#sweep)">'
        f'<animate attributeName="x" values="-260;{W}" dur="7.5s" repeatCount="indefinite"/></rect>'
    )
    return f'<rect y="{H}" width="{W}" height="{STRIP_H}" fill="url(#stripg)"/>' + top_line + badge + headline + meter + right_brand + sweep


# ==============================================================================
# HARMONIZED THREE-COLUMN FEATURE BAND (EQUAL-DIAMETER 52x52 STEPPED PIXEL GEAR)
# ==============================================================================
def make_sym_gear(phase, boost=0.0):
    """Mathematically 4-way & 90-deg symmetric 13x13 8-tooth pixel gear (both frames exact 52x52 span)."""
    rows = []
    for y in range(13):
        row = []
        for x in range(13):
            dx, dy = x - 6, y - 6
            r = math.hypot(dx, dy)
            ang = math.atan2(dy, dx)
            rad = 5.15 + boost + 1.05 * math.cos(8 * (ang - phase))
            if r <= 1.25:
                ch = "P"
            elif r <= 2.35:
                ch = "H"
            elif r <= rad - 0.95:
                ch = "O"
            elif r <= rad:
                ch = "X"
            else:
                ch = "."
            row.append(ch)
        rows.append("".join(row))
    return rows


NPC_ROWS = [
    "...XXXXX...",
    "..XDDDDDX..",
    ".XDDDDDDDX.",
    ".XDEDDDEDX.",
    ".XDDDDDDDX.",
    ".XDDPPPDDX.",
    "..XDDDDDX..",
    "...XXXXX...",
    ".....X.....",
    "..XX.X.XX..",
    ".X..XXX..X.",
]
NPC_PAL = {"X": "#e8c68a", "D": "#2c193f", "E": "#fff4e0", "P": "#ff6fae"}

TAPE_ROWS = [
    ".............",
    "XXXXXXXXXXXXX",
    "XLLLLLLLLLLLX",
    "XLPPPPPPPPPLX",
    "XLLLLLLLLLLLX",
    "XDDDDDDDDDDDX",
    "XDWWWDDDWWWDX",
    "XDWHWTTTWHWDX",
    "XDWWWDDDWWWDX",
    "XBBBBBBBBBBBX",
    ".XXXXXXXXXXX.",
]
TAPE_PAL = {
    "X": "#e8c68a", "L": "#f5ecf8", "P": "#ff6fae", "D": "#1b1028",
    "B": "#2b193d", "W": "#fff4e6", "H": "#4a275e", "T": "#a874ff",
}

GEAR_FRAMES = [make_sym_gear(0.0, 0.0), make_sym_gear(math.pi / 8, 0.35)]
GEAR_PAL = {"X": "#e8c68a", "O": "#3a2154", "H": "#c48aff", "P": "#ff6fae"}


def icon_fx(kind, x, y):
    if kind == "npc":
        base = px_icon(NPC_ROWS, NPC_PAL, x, y, px=5)
        lids = (
            f'<rect x="{x + 3 * 5}" y="{y + 3 * 5}" width="5" height="5" fill="{NPC_PAL["D"]}"/>'
            f'<rect x="{x + 7 * 5}" y="{y + 3 * 5}" width="5" height="5" fill="{NPC_PAL["D"]}"/>'
        )
        blink_g = f'<g opacity="0">{fx.blink(4.8, [(0, 0), (4.0, 1), (4.16, 0), (4.36, 1), (4.5, 0)])}{lids}</g>'
        inner_glint = (
            f'<g opacity="0" shape-rendering="crispEdges">'
            f'{fx.blink(T, [(0, 0), (7.3, 1), (19.2, 0)])}'
            f'<rect x="{x + 7 * 5}" y="{y + 3 * 5}" width="5" height="5" fill="#ff6fae"/>'
            f'<rect x="{x + 10 * 5}" y="{y - 2}" width="4" height="4" fill="#ff6fae"/>'
            f'<rect x="{x + 11 * 5 + 1}" y="{y - 7}" width="5" height="5" fill="#ffb8da"/>'
            f'</g>'
        )
        return base + blink_g + inner_glint
    if kind == "world":
        frames = []
        for f, (sr, sc) in enumerate([(-1, 0), (0, 1), (1, 0), (0, -1)]):
            out = [list(row) for row in TAPE_ROWS]
            for hc in (3, 9):
                out[7 + sr][hc + sc] = "H"
            frames.append(
                f'<g opacity="{1 if f == 0 else 0}">'
                f'<animate attributeName="opacity" calcMode="discrete" dur="1.2s" repeatCount="indefinite" values="{fx.onehot(4, f)}" keyTimes="{fx.kt(4)}"/>'
                f'{px_icon(["".join(r) for r in out], TAPE_PAL, x + 1, y + 5, px=4)}</g>'
            )
        return "".join(frames)
    frames = []
    for f, rows in enumerate(GEAR_FRAMES):
        frames.append(
            f'<g opacity="{1 if f == 0 else 0}">'
            f'<animate attributeName="opacity" calcMode="discrete" dur="1.1s" repeatCount="indefinite" values="{fx.onehot(2, f)}" keyTimes="{fx.kt(2)}"/>'
            f'{px_icon(rows, GEAR_PAL, x + 1, y + 1, px=4)}</g>'
        )
    core_pulse = (
        f'<rect x="{x + 1 + 6 * 4}" y="{y + 1 + 6 * 4}" width="4" height="4" fill="#ffd4ea" shape-rendering="crispEdges">'
        f'<animate attributeName="opacity" values="0.2;1;0.2" dur="1.6s" repeatCount="indefinite"/></rect>'
    )
    return "".join(frames) + core_pulse


def feature_band():
    feats = [
        ("npc", "活人感 NPC", "嘴上一套心里一套，心里话你看得见"),
        ("world", f"{NWORLDS} 个深度世界", "地点、人物、规矩、暗流，各有一整套"),
        ("engine", "自运行状态机", "本地记账，关系和后果都不会忘"),
    ]
    parts = [
        f'<rect y="{BY}" width="{W}" height="{BAND_H}" fill="url(#bandg)"/>',
        f'<rect y="{BY}" width="{W}" height="1" fill="#3a2454"/>',
    ]
    for i in (1, 2):
        parts.append(dots_v(int(CW * i), BY + 26, BY + BAND_H - 26, "#4d3868"))
    for i, (k, title, desc) in enumerate(feats):
        x0 = int(CW * i)
        parts.append(f'<ellipse cx="{x0 + 56}" cy="{BY + 64}" rx="34" ry="30" fill="#a874ff" fill-opacity="0.16" filter="url(#g15)"/>')
        parts.append(f'<g opacity="0.92">{icon_fx(k, x0 + 28, BY + 36)}</g>')
        parts.append(neon_crisp(x0 + 100, BY + 58, title, 28, "#b882ff", "#fff7fc", "start", 1.5, 800))
        parts.append(f'<text x="{x0 + 101}" y="{BY + 92}" font-family="{SANS}" font-size="16" fill="#cfc3df" letter-spacing="0.5">{esc(desc)}</text>')
    return "".join(parts)


F = fx.FX(SRC, S)
body = f'''    <svg x="0" y="0" width="{W}" height="{H}" viewBox="0 {CROP} {IW} {IH - CROP}"><image href="data:image/webp;base64,{DATA}" width="{IW}" height="{IH}"/></svg>
    {F.city_lights()}
    {F.beacons()}
    {F.neon()}
    {F.screens()}
    {F.clock()}
    {F.dust()}
    {F.notes()}
    {F.three_point_lighting(W, H)}
    {marquee_title()}
    {avg_dialogue_rail()}
    {selling_strip()}
    {feature_band()}'''

defs = f'''<filter id="g3" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.5"/></filter>
    <filter id="g4" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3.5"/></filter>
    <filter id="g6" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
    <filter id="g15" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="15"/></filter>
    <filter id="g18" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="18"/></filter>
    <linearGradient id="lineg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#a874ff"/><stop offset="0.5" stop-color="#ff6fae"/><stop offset="1" stop-color="#a874ff"/></linearGradient>
    <linearGradient id="stripg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#24123b"/><stop offset="1" stop-color="#140922"/></linearGradient>
    <linearGradient id="bandg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#11081c"/><stop offset="1" stop-color="#0b0512"/></linearGradient>
    <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset="0.5" stop-color="#f3e6ff" stop-opacity="0.07"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
    <linearGradient id="sheen" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset="0.5" stop-color="#ffe6f6" stop-opacity="0.07"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
    <radialGradient id="roomvig" cx="0.48" cy="0.46" r="0.72"><stop offset="0.58" stop-color="#090312" stop-opacity="0"/><stop offset="1" stop-color="#090312" stop-opacity="0.46"/></radialGradient>
    <linearGradient id="botfade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1c0d30" stop-opacity="0"/><stop offset="1" stop-color="#1c0d30" stop-opacity="0.72"/></linearGradient>
    <clipPath id="winclip"><rect x="386" y="0" width="122" height="142"/><rect x="616" y="0" width="400" height="138"/></clipPath>
    <clipPath id="avgReveal"><rect x="382" y="412" width="0" height="72"><animate attributeName="width" values="0;0;510;510;0;0" keyTimes="0;0.360;0.388;0.960;0.974;1" dur="{T}s" repeatCount="indefinite"/></rect></clipPath>'''

svg = pk.svg_doc(
    W, H2, "Adult Tension",
    "像素风黄昏卧室：一个人坐在床边抱着红色电吉他，大窗外是粉紫色的霓虹城市，书桌上亮着显示器，墙上贴满海报。窗外楼灯明灭、远楼航空红灯慢闪、霓虹招牌呼吸闪烁，闹钟秒数在跳，显示器微光起伏，笔记本紫粉电平上下跳动，灯光里浮着细尘，吉他上荡出微光波纹并飘起 S 曲线像素音符。右上窗面挂着带金铆钉的双框像素霓虹灯箱：ADULT TENSION · NIGHT SHIFT · "
    + f"{NWORLDS} WORLDS。画面底部无遮挡地叠放一条 AVG 表里双轨对话栏：先呈冷银紫「嘴上说：吵到你了？这就停。门没锁，拿完东西就走。」，随后扫线翻转为绯粉霓虹「心里想：……别光站门外听，进来把门反锁啊。」。图下卖点条展示 18+、尺度全开·真实成人互动、与表里切换同步由 CALM 升至 PULSE 的 16 段 TENSION 张力电平条，以及 Claude Opus 5.5 从零重构。再下方三栏：活人感 NPC（切入里层时亮起绯粉微光）、"
    + f"{NWORLDS} 个深度世界（转动双轴的录像带）、自运行状态机（对称步进像素齿轮）。",
    defs, body,
)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8", newline="\n").write(svg)
print("overlay", len(svg) // 1024, "KB", W, H2)
