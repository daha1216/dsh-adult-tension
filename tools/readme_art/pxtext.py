"""Dev-only helper: rasterise CJK text with SimSun glyphs drawn without anti-aliasing (Pillow) into SVG pixel runs."""
from PIL import Image, ImageDraw, ImageFont


def mask(lines, size=12, gap=3):
    f = ImageFont.truetype("C:/Windows/Fonts/simsun.ttc", size)
    w = max(len(s) for s in lines) * size + 2
    h = len(lines) * (size + gap) + 2
    im = Image.new("1", (w, h), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    for i, s in enumerate(lines):
        d.text((1, 1 + i * (size + gap)), s, font=f, fill=1)
    return {(x, y) for y in range(h) for x in range(w) if im.getpixel((x, y))}


def runs(pts, ox, oy, sc, c):
    out, rows = [], {}
    for x, y in pts:
        rows.setdefault(y, []).append(x)
    for y, xs in sorted(rows.items()):
        xs.sort(); s = p = xs[0]
        for x in xs[1:] + [None]:
            if x == p + 1:
                p = x; continue
            out.append(f"M{ox + s * sc} {oy + y * sc}h{(p - s + 1) * sc}v{sc}h-{(p - s + 1) * sc}z")
            if x is not None:
                s = p = x
    return f'<path fill="{c}" d="{"".join(out)}"/>'


def block(lines, ox, oy, sc, fg, edge, size=12):
    m = mask(lines, size)
    ring = {(x + dx, y + dy) for x, y in m for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - m
    return runs(ring, ox, oy, sc, edge) + runs(m, ox, oy, sc, fg)


def comic(lines, ox, oy, sc, fill, ink, shadow, font="msyhbd.ttc", size=14, indent=(0,), gap=4):
    """Manga-style pixel lettering: solid fill, one-dot ink outline, hard drop shadow two dots down-right."""
    f = ImageFont.truetype("C:/Windows/Fonts/" + font, size)
    w = max(len(s) + i for s, i in zip(lines, indent + (0,) * len(lines))) * size + 8
    im = Image.new("1", (w, len(lines) * (size + gap) + 8), 0)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    for i, s in enumerate(lines):
        d.text((2 + (indent[i] if i < len(indent) else 0) * size, 2 + i * (size + gap)), s, font=f, fill=1)
    m = {(x, y) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y))}
    if not ink:                                    # no outline: just a soft one-dot shadow down-right
        drop = {(x + 1, y + 1) for x, y in m} - m
        return runs(drop, ox, oy, sc, shadow).replace("<path", '<path opacity="0.55"', 1) + runs(m, ox, oy, sc, fill)
    edge = {(x + dx, y + dy) for x, y in m for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - m
    solid = m | edge
    drop = {(x + dx, y + dy) for x, y in solid for dx in (1, 2) for dy in (1, 2)} - solid
    return runs(drop, ox, oy, sc, shadow) + runs(edge, ox, oy, sc, ink) + runs(m, ox, oy, sc, fill)


def comic_chars(lines, ox, oy, sc, fill, shadow, font="msyhbd.ttc", size=14, indent=(0,), gap=4):
    """Same lettering as comic(ink=None), one SVG group per character so each can be typed in on its own."""
    f = ImageFont.truetype("C:/Windows/Fonts/" + font, size)
    out = []
    for i, s in enumerate(lines):
        for j, ch in enumerate(s):
            im = Image.new("1", (size + 4, size + 4), 0)
            d = ImageDraw.Draw(im)
            d.fontmode = "1"
            d.text((2, 2), ch, font=f, fill=1)
            m = {(x, y) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y))}
            drop = {(x + 1, y + 1) for x, y in m} - m
            gx = ox + ((indent[i] if i < len(indent) else 0) + j) * size * sc
            gy = oy + i * (size + gap) * sc
            out.append(runs(drop, gx, gy, sc, shadow).replace("<path", '<path opacity="0.55"', 1) + runs(m, gx, gy, sc, fill))
    return out
