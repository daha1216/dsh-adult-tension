"""Hero from the user's own lo-fi bedroom picture: the picture is embedded untouched; the skill name, a pixel tagline and
slow animated layers (city lights, neon signs, ticking clock, screens, dust, guitar notes) sit on top of it, and the
lo-fi hero's selling-point strip and feature band sit below it."""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import overlay_fx as fx  # noqa: E402
import pixkit as pk  # noqa: E402
import pxtext  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "source", os.environ.get("OVERLAY_SRC", "bedroom.webp"))   # the user's own crop
OUT = os.environ.get("OVERLAY_OUT") or os.path.join(HERE, "..", "..", ".github", "readme-lofi", "hero.svg")
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif"
raw = open(SRC, "rb").read()
vp = raw.index(b"VP8X")
W, IW, IH = 1280, int.from_bytes(raw[vp + 12:vp + 15], "little") + 1, int.from_bytes(raw[vp + 15:vp + 18], "little") + 1
CROP = int(os.environ.get("OVERLAY_CROP", 0))
S = W / IW
H = round((IH - CROP) * S)
data = base64.b64encode(raw).decode()


def px_icon(rows, pal, x, y, px=5):
    cells = "".join(f'<rect x="{x + c * px}" y="{y + r * px}" width="{px}" height="{px}" fill="{pal[ch]}"/>'
                    for r, row in enumerate(rows) for c, ch in enumerate(row) if ch != ".")
    return f'<g shape-rendering="crispEdges">{cells}</g>'


def icon_fx(k, x, y):
    """Band icons with a small idle loop: the NPC blinks, the globe turns, the gear spins."""
    rows, pal = ns["ICONS"][k], ns["PAL"][k]
    if k == "npc":
        lids = "".join(f'<rect x="{x + c * 5}" y="{y + 3 * 5}" width="5" height="5" fill="{pal["O"]}"/>' for c in (3, 7))
        return px_icon(rows, pal, x, y) + f'<g opacity="0">{fx.blink(4.6, [(0, 0), (3.9, 1), (4.05, 0), (4.25, 1), (4.38, 0)])}{lids}</g>'
    if k == "world":
        frames = []
        for f in range(4):
            out = []
            for row in rows:
                land = [ch for ch in row if ch in "GB"]
                land = land[f % len(land):] + land[:f % len(land)] if land else land
                it = iter(land)
                out.append("".join(next(it) if ch in "GB" else ch for ch in row))
            frames.append(f'<g opacity="{1 if f == 0 else 0}"><animate attributeName="opacity" calcMode="discrete" dur="3.2s" '
                          f'repeatCount="indefinite" values="{fx.onehot(4, f)}" keyTimes="{fx.kt(4)}"/>{px_icon(out, pal, x, y)}</g>')
        return "".join(frames)
    cx, cy = x + 27.5, y + 27.5
    return (f'<g><animateTransform attributeName="transform" type="rotate" values="0 {cx} {cy};360 {cx} {cy}" dur="12s" '
            f'repeatCount="indefinite"/>{px_icon(rows, pal, x, y)}</g>')


src = open(os.path.join(HERE, "readme_px_room.py"), encoding="utf-8").read()
ns = {"os": os, "W": W, "SY0": H, "SANS": SANS, "icon_fx": icon_fx}
code = src[src.index("STRIPS = {"):src.index("body = f'''")]
sel = 'SP = STRIPS[os.environ.get("LOFI_STRIP", "gold")]'
assert sel in code
# badge glow, badge fill, badge edge, 18+ core (violet), word glow, word core, dot (grey)
code = code.replace(sel, 'SP = ("#a874ff", "#1a0c2e", "#e0ccff", "#f4ecff", "#a39dad", "#ebe8ef", "#c4bfcc")')
for a, b in [("+ icon(k, int(CW * i) + 40, BY + 36)", "+ '<g opacity=\"0.8\">' + icon_fx(k, int(CW * i) + 40, BY + 36) + '</g>'"),
             ('fill="#ffa82e" fill-opacity="0.18"', 'fill="#ffa82e" fill-opacity="0.12"')]:   # band icons a touch dimmer
    assert a in code, a
    code = code.replace(a, b)
exec(code, ns)
BY, BH, CW = ns["BY"], ns["BH"], ns["CW"]


def dots_v(x, y0, y1, c):
    return f'<path fill="{c}" d="{"".join(f"M{x} {y}h2v2h-2z" for y in range(y0, y1, 6))}"/>'


# pixel edges: the strip's top line becomes a 2px dotted gradient with a dithered fade, the dividers become dotted
top_line = (f'<rect y="{H - 4}" width="{W}" height="10" fill="url(#lineg)" fill-opacity="0.25" filter="url(#g6)"/>'
            f'<g fill="url(#lineg)" shape-rendering="crispEdges">'
            f'<path d="{"".join(f"M{x} {H}h2v2h-2z" for x in range(0, W, 4))}"/>'
            f'<path opacity="0.45" d="{"".join(f"M{x} {H + 2}h2v2h-2z" for x in range(2, W, 4))}"/>'
            f'<path opacity="0.18" d="{"".join(f"M{x} {H + 4}h2v2h-2z" for x in range(0, W, 8))}"/></g>')
strip, band = ns["strip"], ns["band"]
for old, new in [(f'<rect y="{H}" width="{W}" height="2" fill="#ff6fae"/><rect y="{H - 4}" width="{W}" height="10" fill="#ff6fae" fill-opacity="0.35" filter="url(#g6)"/>', top_line),
                 (f'<rect x="{W - 372}" y="{H + 20}" width="2" height="48" fill="#5a4a6a"/>', dots_v(W - 372, H + 20, H + 68, "#6a5a7c"))]:
    assert old in strip, old
    strip = strip.replace(old, new)
for i in (1, 2):
    old = f'<rect x="{int(CW * i)}" y="{BY + 28}" width="2" height="{BH - 56}" fill="#2a1f36"/>'
    assert old in band, old
    band = band.replace(old, dots_v(int(CW * i), BY + 28, BY + BH - 28, "#4a3d5c"))
sweep = (f'<rect x="-260" y="{H + 6}" width="260" height="78" fill="url(#sweep)">'
         f'<animate attributeName="x" values="-260;{W}" dur="7s" repeatCount="indefinite"/></rect>')

tx = 1300 * S                            # right of the girl, in the window above the monitor
FONT = "'Arial Black','Segoe UI Black','Helvetica Neue',Impact,sans-serif"
letters = iter(range(12))
name = (f'<g font-family="{FONT}" font-weight="900" fill="#0b0710" text-anchor="middle" stroke="#ffe3f0" stroke-width="5" '
        f'stroke-linejoin="round" paint-order="stroke" letter-spacing="2">'
        + "".join(f'<text x="{tx:.0f}" y="{y}" font-size="54">'
                  + "".join(f'<tspan>{fx.title_track(next(letters))}{ch}</tspan>' for ch in word) + '</text>'
                  for word, y in (("ADULT", 62), ("TENSION", 118))) + '</g>')
chars = pxtext.comic_chars(["专为高张力、强连续性", "成人互动叙事打造"], 110, 266, 2, "#ffffff", "#0b0710", indent=(0, 1))
tag = "".join(f'<g opacity="0">{fx.type_track(n)}{c}</g>' for n, c in enumerate(chars))   # left of the girl, typed in

F = fx.FX(SRC, S)
body = f'''    <svg x="0" y="0" width="{W}" height="{H}" viewBox="0 {CROP} {IW} {IH - CROP}"><image href="data:image/webp;base64,{data}" width="{IW}" height="{IH}"/></svg>
    {F.city_lights()}
    {F.neon()}
    {F.screens()}
    {F.clock()}
    {F.dust()}
    {F.notes()}
    {name}
    {tag}
    {strip}
    {sweep}
    {band}'''
defs = '''<filter id="g3" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.5"/></filter>
    <filter id="g6" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
    <filter id="g15" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="15"/></filter>
    <linearGradient id="lineg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#a874ff"/><stop offset="0.5" stop-color="#ff6fae"/><stop offset="1" stop-color="#a874ff"/></linearGradient>
    <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset="0.5" stop-color="#ffffff" stop-opacity="0.08"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>'''
svg = pk.svg_doc(W, ns["H2"], "Adult Tension",
                 "像素风黄昏卧室：一个人坐在床边抱着红色电吉他，大窗外是粉紫色的霓虹城市，书桌上亮着显示器，墙上贴满海报。窗外楼灯明灭、霓虹招牌呼吸闪烁，闹钟秒数在跳，显示器微光起伏，笔记本上的柱状图上下跳动，灯光里浮着细尘，吉他上飘出像素音符。人物右侧的窗上是逐字点亮的黑色粗体字 ADULT TENSION；人物左侧是逐字打出的两行像素字：专为高张力、强连续性成人互动叙事打造。图下一行：18+、尺度全开、真实成人互动、Claude Opus 5.5 从零重构。再下方三栏：活人感 NPC、数十个深度世界、自运行状态机。",
                 defs, body)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8", newline="\n").write(svg)
print("overlay", len(svg) // 1024, "KB", W, ns["H2"])
