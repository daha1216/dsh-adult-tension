"""Polished lo-fi pixel bedroom at dusk: neon city through a big window (ADULT TENSION sign, passing train), fairy lights,
a person on the bed reading a glowing phone, a cat on the sill, a desk with a chat on screen, a neon sign on the wall."""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pixkit as pk  # noqa: E402

# Not used for the README any more: readme_overlay.py borrows its strip and band. Standalone runs go to scratch.
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "reports", "tmp", "readme_art")
os.makedirs(OUT, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
C, GW, GH = 4, 320, 180
W, H = GW * C, GH * C
rnd = random.Random(11)
WX0, WY0, WX1, WY1 = 92, 18, 292, 110            # glass area
MUL = (190, 194)

city = pk.Canvas(GW, GH)
room = pk.Canvas(GW, GH)
anim = []                                         # decorative SMIL overlays

# ================================================================ CITY
city.vgrad(WX0, WY0, WX1, WY1, ["#221d4c", "#2c2460", "#392b72", "#4c3283", "#653a92", "#82419b", "#a0499f", "#bc539f",
                                "#d4619f", "#e675a2", "#f28ca6", "#f9a6a8", "#fcc0a6"], WY0, 96)
# streaky clouds lit from below
for _ in range(14):
    cy = rnd.randint(WY0 + 4, 62)
    cx = rnd.randint(WX0 - 10, WX1)
    w = rnd.randint(16, 46)
    h = rnd.randint(2, 4)
    for x in range(cx, cx + w):
        e = abs((x - cx) / w - 0.5) * 2
        hh = max(1, round(h * (1 - e * e)))
        for k in range(hh):
            col = "#7a3c8e" if k == 0 else "#a24c9c"
            if k == hh - 1:
                col = "#f2a2bf" if cy > 40 else "#c873b0"
            if WX0 <= x < WX1:
                city.put(x, cy + k, col)
# retro sun
SUNX, SUNY, SUNR = 244, 84, 13
for y in range(SUNY - SUNR, SUNY + SUNR):
    for x in range(SUNX - SUNR, SUNX + SUNR):
        d = math.hypot(x + 0.5 - SUNX, y + 0.5 - SUNY)
        if d <= SUNR and not (y > SUNY - 2 and (y - SUNY) % 4 in (0,) and y - SUNY < 11):
            city.put(x, y, pk.ramp(["#ffb48a", "#ffc994", "#ffdca4", "#fff0c4"], 1 - (y - SUNY + SUNR) / (2 * SUNR), x, y))

LIT = ["#ffd88a", "#ffb7d6", "#9fe9ff", "#ffe6b0", "#d7b8ff"]


def building(x, w, top, base_col, rim, lit_p, grid=(2, 3), roof=True):
    city.rect(x, top, x + w, WY1, base_col)
    city.rect(x, top, x + 1, WY1, rim)
    city.rect(x, top, x + w, top + 1, rim)
    gx, gy = grid
    for yy in range(top + 3, WY1 - 1, gy):
        for xx in range(x + 2, x + w - 1, gx):
            if rnd.random() < lit_p:
                city.put(xx, yy, rnd.choice(LIT))
    if roof and rnd.random() < 0.5:
        if rnd.random() < 0.5:
            ax = x + rnd.randint(2, max(2, w - 3))
            h = rnd.randint(5, 12)
            city.rect(ax, top - h, ax + 1, top, base_col)
            anim.append(("blink", ax, top - h))
        else:
            tx = x + rnd.randint(1, max(1, w - 6))
            city.rect(tx, top - 5, tx + 5, top - 2, base_col)
            city.rect(tx + 1, top - 2, tx + 2, top, base_col)
            city.rect(tx + 3, top - 2, tx + 4, top, base_col)


x = WX0 - 6
while x < WX1:                                   # far haze
    w = rnd.randint(6, 14)
    building(x, w, rnd.randint(64, 82), "#6a4592", "#8a5aa8", 0.08, roof=False)
    x += w
x = WX0 - 4
while x < WX1:                                   # middle
    w = rnd.randint(8, 16)
    building(x, w, rnd.randint(48, 80), "#432f78", "#6a4a9e", 0.22)
    x += w + rnd.randint(0, 3)
x = WX0 - 2
while x < WX1:                                   # near towers
    w = rnd.randint(10, 20)
    top = rnd.randint(28, 72)
    if 206 <= x <= 262:
        top = max(top, 58)                       # leave room for the sign
    building(x, w, top, "#261b4d", "#5a3f8f", 0.3, grid=(3, 3))
    x += w + rnd.randint(1, 5)
# neon billboards on towers
for bx, by, bw, bh, col in [(104, 54, 10, 6, "#ff6fae"), (148, 44, 7, 12, "#6ff0ff"), (170, 70, 12, 4, "#ffd06f"), (276, 60, 8, 10, "#6ff0ff")]:
    city.rect(bx - 1, by - 1, bx + bw + 1, by + bh + 1, "#140e2c")
    city.rect(bx, by, bx + bw, by + bh, lambda x, y, bx=bx, by=by, bw=bw, bh=bh, col=col: col if x in (bx, bx + bw - 1) or y in (by, by + bh - 1) or (x + y) % 3 == 0 else None)
# the ADULT TENSION sign on a rooftop frame
SX, SY = 204, 42
SW = 13 * 6 + 5
city.rect(SX + 18, SY + 13, SX + 20, 60, "#140e2c")
city.rect(SX + SW - 22, SY + 13, SX + SW - 20, 60, "#140e2c")
for k in range(SY + 14, 60, 4):
    city.line(SX + 18, k, SX + SW - 21, k + 3, "#140e2c")
city.rect(SX - 3, SY - 4, SX + SW, SY + 13, "#140e2c")
city.rect(SX - 2, SY - 3, SX + SW - 1, SY + 12, lambda x, y: "#ff6fae" if x in (SX - 2, SX + SW - 2) or y in (SY - 3, SY + 11) else None)
for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
    city.text("ADULT TENSION", SX + 1 + dx, SY + 1 + dy, "#c9367e")
city.text("ADULT TENSION", SX + 1, SY + 1, "#ffe3f0")
# street-level glow and elevated track
city.rect(WX0, 102, WX1, WY1, lambda x, y: pk.ramp(["#2a1e4e", "#4a2f6a", "#7a4278"], (y - 102) / 8, x, y))
for x in range(WX0, WX1, 3):
    if rnd.random() < 0.5:
        city.put(x, 106 + rnd.randint(0, 2), rnd.choice(["#ffcf8a", "#ff9ac2"]))
city.rect(WX0, 96, WX1, 99, "#1a1236")
city.rect(WX0, 96, WX1, 97, "#3a2a62")
for x in range(WX0 + 6, WX1, 22):
    city.rect(x, 99, x + 2, WY1, "#1a1236")

# ================================================================ ROOM
room.rect(0, 0, GW, GH, lambda x, y: "#2d2131" if (x // 3) % 4 else "#302434")
room.rect(0, 0, GW, 8, "#130d15")
room.rect(0, 8, GW, 9, "#22171f")
room.rect(0, 120, GW, 156, lambda x, y: "#271c2a" if (x // 3) % 4 else "#2a1e2d")       # lower wall
room.rect(0, 119, GW, 120, "#3d2c3a")
room.clear(WX0, WY0, WX1, WY1)
# window frame, recess, mullion, transom, sill
room.rect(WX0 - 5, WY0 - 5, WX1 + 5, WY0, "#17101a")
room.rect(WX0 - 5, WY0, WX0, WY1, "#17101a")
room.rect(WX1, WY0, WX1 + 5, WY1, "#17101a")
room.rect(WX0 - 2, WY0 - 2, WX1 + 2, WY0, "#241826")
room.rect(MUL[0], WY0, MUL[1], WY1, "#17101a")
room.rect(MUL[0], WY0, MUL[0] + 1, WY1, "#5c3a5e")
room.rect(WX0, 30, WX1, 32, "#17101a")
room.rect(WX0, 32, WX1, 33, "#4a3050")
room.rect(WX0 - 7, WY1, WX1 + 7, WY1 + 4, "#3a2630")
room.rect(WX0 - 7, WY1, WX1 + 7, WY1 + 1, "#a06478")
room.rect(WX0 - 7, WY1 + 4, WX1 + 7, WY1 + 5, "#1e1419")
# pink light spill on the wall under the window and on the floor
room.rect(WX0, WY1 + 5, WX1, 120, lambda x, y: "#3c2a3e" if pk.dth(x, y, 1 - (y - WY1 - 5) / 10) else None)

# curtain (left) and rod
room.rect(78, 12, 304, 14, "#17101a")
room.rect(76, 11, 80, 15, "#5a4048")
room.rect(302, 11, 306, 15, "#5a4048")
CURT = ["#2a0d18", "#3c1421", "#521c2c", "#6a2637", "#823246"]
for x in range(78, 96):
    for y in range(14, 152):
        sway = (y - 14) / 138
        t = 0.5 + 0.45 * math.sin((x - 78) * 0.85 + sway * 1.5)
        col = pk.ramp(CURT, t, x, y)
        if x >= 93 - int(sway * 2):
            col = "#c2587e"                      # rim from the window
        if x > 95 - int(sway * 3) and y > 100:
            continue
        room.put(x, y, col)
room.rect(76, 96, 96, 99, "#a07a4a")            # tie-back

# fairy lights along the rod
def fairy_lights():
    bulbs = []
    for i in range(31):
        t = i / 30
        x = 82 + t * 218
        y = 15 + 6 * 4 * t * (1 - t)
        room.put(x, y, "#3a2a2e")
        if i % 2 == 0:
            col = ["#ffd27a", "#ff9ac2", "#9fe8ff"][(i // 2) % 3]
            room.rect(x, y + 1, x + 2, y + 3, col)
            bulbs.append((x, y + 2, col))
    for i in range(1, 218):
        t = i / 218
        room.put(82 + t * 218, 15 + 6 * 4 * t * (1 - t), "#3a2a2e")
    return bulbs


bulbs = fairy_lights()

# ---------------------------------------------------------------- left wall: posters, neon sign, shelf


def frame(x0, y0, x1, y1):
    room.rect(x0 - 2, y0 - 2, x1 + 2, y1 + 2, "#140d14")
    room.rect(x0 - 1, y0 - 1, x1 + 1, y0, "#4a3a44")


# poster 1: lantern festival at night
frame(5, 16, 29, 40)
room.vgrad(5, 16, 29, 40, ["#1d2350", "#3a2a66", "#6a3778", "#a2477e"])
for k in range(3):
    lx, ly = 9 + k * 7, 20 + (k % 2) * 2
    room.line(5, 21, 29, 21, "#2a1e3a")
    room.ellipse(lx + 1.5, ly + 4, 2.6, 3.4, lambda x, y: "#ffcf6a" if x == int(lx + 1) else "#e0402f")
    room.put(lx + 1, ly, "#2a1e3a")
room.poly([(5, 34), (9, 31), (13, 34), (17, 30), (23, 34), (29, 32), (29, 40), (5, 40)], "#1a1228")
for wx in (8, 15, 22, 26):
    room.put(wx, 37, "#ffcf6a")
# poster 2: harbour crane
frame(34, 16, 56, 40)
room.vgrad(34, 16, 56, 40, ["#16243f", "#24395c", "#36557a"])
room.ellipse(51, 21, 2.5, 2.5, "#f3e9cf")
room.rect(39, 22, 41, 36, "#ff9a4a")
room.rect(36, 22, 55, 24, "#ff9a4a")
room.rect(49, 24, 50, 29, "#e9eef4")
room.rect(47, 29, 52, 32, "#e05a4a")
room.rect(34, 36, 56, 40, "#122038")
room.rect(43, 33, 49, 36, "#3f8fbf")
# poster 3: snowy cabin
frame(61, 16, 77, 40)
room.vgrad(61, 16, 77, 40, ["#121c36", "#22345a"])
room.rect(61, 33, 77, 40, "#e6edf5")
room.poly([(64, 30), (69, 25), (74, 30)], "#e6edf5")
room.rect(65, 30, 73, 34, "#7a4a2e")
room.rect(67, 31, 69, 33, "#ffd27a")
for _ in range(10):
    room.put(rnd.randint(61, 76), rnd.randint(16, 32), "#ffffff")
# neon sign board (the text itself is vector, drawn later)
room.rect(4, 57, 79, 79, "#1a1119")
room.rect(4, 57, 79, 58, "#3a2834")
for sx in (6, 77):
    room.put(sx, 59, "#7a6a70")
    room.put(sx, 77, "#7a6a70")
# shelf with clock, books, a plant
room.rect(3, 93, 76, 95, "#6a4a3e")
room.rect(3, 93, 76, 94, "#8a6450")
room.rect(6, 82, 32, 93, "#0d090c")
room.rect(6, 82, 32, 83, "#2a2026")
room.text("20:30", 7, 84, "#ff4d5e")
for i, col in enumerate(["#c8423a", "#3f7fb0", "#e2a33b", "#6a9a5a", "#b06aa8", "#3a5a8a"]):
    h = rnd.randint(7, 10)
    room.rect(40 + i * 3, 93 - h, 42 + i * 3, 93, col)
    room.rect(40 + i * 3, 93 - h, 41 + i * 3, 93, "#000000" if False else col)
room.rect(62, 86, 70, 93, "#b0603e")
for dx, dy in [(-2, -3), (0, -6), (3, -4), (5, -7), (-3, -7), (2, -9)]:
    room.rect(65 + dx, 86 + dy, 67 + dx, 88 + dy, "#5f9a5a")

# ---------------------------------------------------------------- bed
room.rect(0, 98, 6, 132, "#3a2622")                      # headboard
room.rect(0, 98, 6, 99, "#5a3e34")
room.rect(0, 118, 154, 124, lambda x, y: pk.ramp(["#5a5062", "#6e6478", "#82788c"], 1 - (y - 118) / 6, x, y))
room.ellipse(18, 117, 14, 6, lambda x, y: pk.ramp(["#6e6478", "#8a8098", "#a49cb2"], 1 - (y - 111) / 10, x, y))
BLANK = ["#132830", "#183440", "#1f4250", "#2a5262", "#3a6676"]
room.poly([(34, 121), (154, 121), (156, 146), (30, 146)], lambda x, y: pk.ramp(BLANK, 0.45 + 0.3 * math.sin((x * 0.9 - y * 1.6) / 9), x, y))
room.poly([(70, 121), (104, 121), (90, 146), (52, 146)], lambda x, y: pk.ramp(["#2a5262", "#3a6676", "#5a7e8e"], 0.4 + 0.3 * math.sin((x - y) / 6), x, y) if pk.dth(x, y, 0.7) else None)   # window light
room.rect(0, 146, 158, 152, "#2a1a1e")
room.rect(0, 146, 158, 147, "#4a3034")
room.rect(0, 152, 158, 156, "#140d10")

# ---------------------------------------------------------------- cat on the sill, back to us
CX, CY = 168, 110
room.mask = set()
room.ellipse(CX, CY - 4, 5, 5, "#140c14")
room.ellipse(CX, CY - 11, 3.6, 3.3, "#140c14")
room.poly([(CX - 3.5, CY - 12), (CX - 3, CY - 17), (CX - 0.5, CY - 13)], "#140c14")
room.poly([(CX + 3.5, CY - 12), (CX + 3, CY - 17), (CX + 0.5, CY - 13)], "#140c14")
for k in range(8):
    room.put(CX + 4 + (1 if k > 2 else 0), CY - 1 + k, "#140c14")
cat = room.mask
room.mask = None
for (x, y) in cat:
    if (x, y - 1) not in cat and y < CY:
        room.put(x, y, "#e486ae")
    elif (x - 1, y) not in cat and y < CY:
        room.put(x, y, "#a8558a")

# ---------------------------------------------------------------- desk, monitor, lamp, chair
DT = 118
room.rect(194, DT, 302, DT + 3, "#8a5c44")
room.rect(194, DT, 302, DT + 1, "#c08060")
room.rect(194, DT + 3, 302, DT + 6, "#4a2e26")
room.rect(198, DT + 6, 201, 158, "#2a1a1a")
room.rect(296, DT + 6, 299, 158, "#2a1a1a")
# drawers
room.rect(268, DT + 6, 295, 154, "#3a2420")
for y in (130, 142):
    room.rect(268, y, 295, y + 1, "#241614")
    room.rect(279, y - 5, 284, y - 4, "#a08060")
# pc tower with rgb
room.rect(204, 126, 220, 156, "#18141c")
room.rect(204, 126, 220, 127, "#2e2834")
room.rect(206, 130, 207, 152, lambda x, y: pk.ramp(["#ff6fae", "#c98aff", "#6ff0ff"], (y - 130) / 22, x, y))
for y in range(132, 150, 3):
    room.rect(210, y, 218, y + 1, "#242030")
# monitor with a chat
MX0, MY0, MX1, MY1 = 214, 82, 266, 114
room.rect(MX0, MY0, MX1, MY1, "#0e0c12")
room.rect(MX0 + 2, MY0 + 2, MX1 - 2, MY1 - 2, "#1a1d32")
room.rect(MX0 + 2, MY0 + 2, MX1 - 2, MY0 + 5, "#262b4a")
for i, c in enumerate(["#ff6f7f", "#ffd06f", "#6fe08f"]):
    room.put(MX0 + 4 + i * 2, MY0 + 3, c)
msgs = [("l", 24), ("r", 18), ("l", 30), ("r", 14), ("l", 20)]
for k, (side, w) in enumerate(msgs):
    y = MY0 + 7 + k * 5
    if side == "l":
        room.ellipse(MX0 + 5.5, y + 1.5, 1.6, 1.6, "#ffb7d6")
        x0 = MX0 + 8
        bc, tc = "#d85a8e", "#ffd6e6"
    else:
        x0 = MX1 - 4 - w
        bc, tc = "#3fa9bd", "#d6f7fb"
    room.rect(x0, y, x0 + w, y + 3, bc)
    for xx in range(x0 + 2, x0 + w - 2):
        if (xx * 7 + k) % 5:
            room.put(xx, y + 1, tc)
CURSOR = (MX0 + 8 + 20 + 1, MY0 + 7 + 4 * 5)
room.rect(238, MY1, 242, DT, "#0e0c12")
room.rect(230, DT - 1, 250, DT, "#0e0c12")
# keyboard, mug, speaker, plant
room.rect(222, DT - 2, 258, DT, "#3a3446")
for x in range(223, 257, 2):
    room.put(x, DT - 2, "#5e5870")
room.rect(262, DT - 6, 267, DT, "#ece4d8")
room.rect(262, DT - 6, 267, DT - 5, "#ffffff")
room.rect(267, DT - 5, 269, DT - 2, "#ece4d8")
room.rect(272, DT - 10, 278, DT, "#221c26")
room.ellipse(275, DT - 6, 1.8, 1.8, "#4a4258")
room.rect(282, DT - 9, 292, DT, lambda x, y: pk.ramp(["#8a3e2a", "#b0603e", "#c87a52"], (x - 282) / 10, x, y))
for (lx, ly, r) in [(284, 98, 5), (290, 96, 6), (287, 90, 5), (293, 103, 4), (280, 104, 4), (287, 102, 5)]:
    pk.blob_shade(room, [(lx, ly, r)], ["#1f4a2e", "#2e6a40", "#3f8a52", "#64b070"], squash=1.3)
room.line(287, 109, 287, 96, "#2e6a40")
# desk lamp
room.rect(200, DT - 2, 210, DT, "#2a2430")
room.line(205, DT - 2, 201, 100, "#3a3442", 2)
room.line(201, 100, 210, 94, "#3a3442", 2)
room.poly([(206, 92), (214, 92), (216, 99), (204, 99)], "#e2b25a")
room.rect(204, 99, 216, 100, "#fff0b0")
# chair
CH = "#130f17"
room.ellipse(250, 124, 12, 15, CH)
room.rect(236, 136, 264, 142, CH)
room.rect(248, 142, 252, 155, CH)
room.rect(236, 155, 264, 157, CH)
for wx in (236, 249, 262):
    room.rect(wx, 157, wx + 2, 159, CH)
rim = [(xx, yy) for yy in range(108, 158) for xx in range(234, 266) if room.get(xx, yy) == CH and room.get(xx - 1, yy) != CH]
top = [(xx, yy) for yy in range(108, 158) for xx in range(234, 266) if room.get(xx, yy) == CH and room.get(xx, yy - 1) != CH]
for (x, y) in rim:
    room.put(x, y, "#5a3a5e")
for (x, y) in top:
    room.put(x, y, "#4a3050")

# right wall bookshelf
room.rect(304, 22, GW, 158, "#3a2622")
for sy in (52, 84, 116, 148):
    room.rect(304, sy, GW, sy + 2, "#7a5442")
    x = 306
    while x < GW - 1:
        h = rnd.randint(8, 14)
        room.rect(x, sy - h, x + 2, sy, rnd.choice(["#c8423a", "#3f7fb0", "#e2a33b", "#6a9a5a", "#b06aa8", "#e6d8c4"]))
        x += 3

# ---------------------------------------------------------------- floor and rug
room.rect(0, 156, GW, GH, lambda x, y: "#24171c" if (y - 156) % 6 == 0 or (x + (y - 156) // 6 * 17) % 46 == 0 else ("#2c1d22" if ((y - 156) // 6) % 2 else "#301f25"))
room.poly([(96, 156), (196, 156), (186, 180), (40, 180)], lambda x, y: "#4a2c3e" if pk.dth(x, y, 0.55 - (y - 156) / 60) else None)   # window light
room.ellipse(236, 170, 58, 9, lambda x, y: pk.ramp(["#4a2834", "#5e3440", "#76444e"], 0.5 + 0.4 * math.sin(math.hypot((x - 236) / 6, (y - 170)) * 1.2), x, y))
room.ellipse(236, 170, 58, 9, lambda x, y: "#9a5a60" if abs(((x + 0.5 - 236) / 58) ** 2 + ((y + 0.5 - 170) / 9) ** 2 - 0.82) < 0.08 else None)

# ---------------------------------------------------------------- person on the edge of the bed, reading a phone
OX, OY = 124, 136
HAIR = ["#140b12", "#1d1119", "#2a1722", "#3e1f2e"]
SKIN = ["#8a5a5a", "#a87068", "#c48a7e", "#d8a092"]
TEE = ["#5e5670", "#736a86", "#8a809c", "#a196b2"]
room.mask = set()
room.poly([(OX - 11, OY - 40), (OX + 11, OY - 40), (OX + 12, OY - 26), (OX + 9, OY - 23), (OX - 9, OY - 23), (OX - 12, OY - 26)], HAIR[1])     # hair back
room.rect(OX - 2, OY - 27, OX + 2, OY - 22, SKIN[0])                                                                                    # neck
room.poly([(OX - 13, OY - 24), (OX + 13, OY - 24), (OX + 16, OY - 15), (OX + 12, OY - 13), (OX + 11, OY + 1), (OX - 11, OY + 1), (OX - 12, OY - 13), (OX - 16, OY - 15)],
          lambda x, y: pk.ramp(TEE, 0.85 - (x - OX + 13) / 34 - (0.15 if (x - OX) % 7 == 0 and y > OY - 14 else 0), x, y))
room.ellipse(OX, OY + 9, 24, 3, "#0e1c22")                                                                                             # shadow on the blanket
room.poly([(OX - 18, OY - 1), (OX + 18, OY - 1), (OX + 21, OY + 4), (OX + 15, OY + 9), (OX - 15, OY + 9), (OX - 21, OY + 4)],
          lambda x, y: pk.ramp(SKIN, 0.85 - (x - OX + 21) / 52 - (y - OY) / 30, x, y))                                                 # crossed legs
room.line(OX - 15, OY + 7, OX + 11, OY + 3, SKIN[0])
room.line(OX - 15, OY + 6, OX + 11, OY + 2, SKIN[3])
for fx in (OX - 21, OX + 16):
    room.rect(fx, OY + 3, fx + 5, OY + 7, "#ddd6e2")
    room.rect(fx, OY + 6, fx + 5, OY + 7, "#b8b0c4")
room.rect(OX - 11, OY - 3, OX + 11, OY + 2, "#262030")                                                                                  # shorts
# arms bent toward the phone
for side in (-1, 1):
    sx = OX + side * 13
    room.poly([(sx - 2, OY - 19), (sx + 2, OY - 19), (sx + 2 * side + 1, OY - 8), (sx + 2 * side - 3, OY - 8)], lambda x, y: pk.ramp(SKIN, 0.55 - side * 0.15, x, y))
    room.poly([(sx + 2 * side - 3, OY - 10), (sx + 2 * side + 1, OY - 8), (OX + side * 2, OY - 12), (OX + side * 3, OY - 15)], lambda x, y: pk.ramp(SKIN, 0.6, x, y))
    room.poly([(sx - 3, OY - 24), (sx + 3, OY - 24), (sx + 3 * side + 1, OY - 17), (sx - 3 + side, OY - 16)], TEE[2] if side < 0 else TEE[1])      # sleeves
room.rect(OX - 3, OY - 17, OX + 3, OY - 11, "#1c2030")                                                                                  # phone
room.rect(OX - 2, OY - 16, OX + 2, OY - 12, "#c8f8ff")
# head
room.ellipse(OX, OY - 33, 7.5, 8.5, lambda x, y: pk.ramp(SKIN, 0.95 - (x - OX + 7) / 22 + (0.12 if y > OY - 30 else 0), x, y))
room.ellipse(OX, OY - 38, 10, 7, lambda x, y: pk.ramp(HAIR, 0.55 - (x - OX + 10) / 30 + (0.35 if (x - OX + y) % 6 == 0 and y < OY - 39 else 0), x, y))
room.poly([(OX - 9, OY - 39), (OX + 9, OY - 39), (OX + 9, OY - 33), (OX + 6, OY - 35), (OX + 3, OY - 33), (OX, OY - 35), (OX - 3, OY - 33), (OX - 6, OY - 35), (OX - 9, OY - 33)], HAIR[1])  # bangs
room.rect(OX - 10, OY - 38, OX - 7, OY - 26, HAIR[1])
room.rect(OX + 7, OY - 38, OX + 10, OY - 26, HAIR[0])
for (x, y, c) in [(OX - 4, OY - 31, "#3a1a26"), (OX - 3, OY - 31, "#3a1a26"), (OX + 2, OY - 31, "#3a1a26"), (OX + 3, OY - 31, "#3a1a26"),
                  (OX - 5, OY - 29, "#e88a94"), (OX + 4, OY - 29, "#e88a94"), (OX, OY - 27, "#a04a56"), (OX + 6, OY - 41, "#ff5a7a"), (OX + 7, OY - 41, "#ff5a7a")]:
    room.put(x, y, c)
person = room.mask
room.mask = None
for (x, y) in person:                            # rim light from the window behind
    if y < OY + 2 and (x - 1, y) not in person:
        room.put(x, y, "#e486ae")
    elif y < OY - 20 and (x, y - 1) not in person:
        room.put(x, y, "#f0a0c4")
    elif y < OY + 2 and (x + 1, y) not in person:
        room.put(x, y, "#8a6aae")


# ================================================================ squash the window: drop SQ rows per column (left wall below the posters,
# the sky at the top of the glass, the empty bookshelf top), then shift everything below up by SQ
SQ = int(os.environ.get("LOFI_SQ", 14))
BANDS = [(0, 76, 43), (76, 304, 20), (304, GW, 23)]


def squash(cv):
    g = [[None] * cv.w for _ in range(cv.h - SQ)]
    for x0, x1, y0 in BANDS:
        for x in range(x0, x1):
            col = [cv.g[y][x] for y in range(cv.h) if not y0 <= y < y0 + SQ]
            for y in range(cv.h - SQ):
                g[y][x] = col[y]
    cv.g, cv.h = g, cv.h - SQ


def d(y):
    return y - SQ if y >= 34 else y


squash(city)
squash(room)
bulbs = fairy_lights()
GH -= SQ
H = GH * C
WY1 -= SQ

# ================================================================ overlays
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif"
ov = []
train = pk.Canvas(60, 4)
train.rect(0, 0, 58, 3, "#d6cfe6")
train.rect(0, 0, 58, 1, "#f2eefa")
train.rect(0, 2, 58, 3, "#8a82a0")
for x in range(2, 56, 4):
    train.rect(x, 1, x + 2, 2, "#ffe9a8")
train_g = (f'<g clip-path="url(#glass)"><g>{train.emit(C, WX0 - 70, d(93))}'
           f'<animateTransform attributeName="transform" type="translate" values="0 0;{(WX1 - WX0 + 140) * C} 0" dur="11s" repeatCount="indefinite"/></g></g>')
blinks = "".join(f'<rect x="{x * C}" y="{d(y) * C}" width="{C}" height="{C}" fill="#ff4a5a"><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.55;1" dur="{rnd.uniform(1.6, 2.6):.1f}s" repeatCount="indefinite"/></rect>'
                 for kind, x, y in anim if kind == "blink" and WX0 <= x < WX1 and 34 <= y)
fairy = "".join(f'<circle cx="{(x + 1) * C}" cy="{y * C}" r="14" fill="{c}" fill-opacity="0.5" filter="url(#g6)"><animate attributeName="fill-opacity" values="0.55;0.15;0.55" dur="{rnd.uniform(2, 4):.1f}s" begin="-{rnd.uniform(0, 3):.1f}s" repeatCount="indefinite"/></circle>'
                for x, y, c in bulbs)
sign_cx, sign_cy = (SX + SW / 2) * C, d(SY + 4) * C
steam = "".join(f'<rect x="{(264 + k * 2) * C}" y="{d(DT - 8) * C}" width="{C}" height="{C}" fill="#ffffff"><animateTransform attributeName="transform" type="translate" values="0 0;{(-1) ** k * 6} -40" dur="2.6s" begin="-{k * 0.9:.1f}s" repeatCount="indefinite"/><animate attributeName="opacity" values="0;0.6;0" dur="2.6s" begin="-{k * 0.9:.1f}s" repeatCount="indefinite"/></rect>' for k in range(3))
cursor = f'<rect x="{CURSOR[0] * C}" y="{d(CURSOR[1]) * C}" width="{C}" height="{3 * C}" fill="#ffd6e6"><animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1s" repeatCount="indefinite"/></rect>'
TOP, LIFT = int(os.environ.get('LOFI_TOP', 40)), int(os.environ.get('LOFI_LIFT', 48))   # crop the ceiling, raise the strip over the floor
SY0 = H - 84 - LIFT
# badge glow, badge fill, badge edge, badge core, text glow, text core, separator dot
STRIPS = {"pink": ("#ff4d6d", "#2a0a14", "#ffb3c4", "#ffe3ea", "#ff6fae", "#ffe3f0", "#ffd27a"),
          "gold": ("#ffa82e", "#2a1906", "#ffe1a0", "#fff4dc", "#ffc54a", "#fff6e2", "#ff6fae"),
          "cyan": ("#22e0d0", "#04221f", "#b0fff6", "#e6fffb", "#4feedd", "#eafffc", "#ffd27a"),
          "violet": ("#a874ff", "#1a0c2e", "#e0ccff", "#f4ecff", "#c09aff", "#f6efff", "#6fd8ff")}
SP = STRIPS[os.environ.get("LOFI_STRIP", "gold")]


def neon_t(x, y, s, size, col, core, anchor="start", spacing=3):
    return (f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="{size}" font-weight="900" fill="{col}" text-anchor="{anchor}" letter-spacing="{spacing}" filter="url(#g6)">{s}</text>'
            f'<text x="{x}" y="{y}" font-family="{SANS}" font-size="{size}" font-weight="900" fill="{core}" text-anchor="{anchor}" letter-spacing="{spacing}" stroke="{col}" stroke-width="1.2">{s}</text>')


strip = (f'<rect y="{SY0}" width="{W}" height="84" fill="#0b0710" fill-opacity="0.82"/>'
         f'<rect y="{SY0}" width="{W}" height="2" fill="#ff6fae"/><rect y="{SY0 - 4}" width="{W}" height="10" fill="#ff6fae" fill-opacity="0.35" filter="url(#g6)"/>'
         # 18+ badge
         f'<g><animate attributeName="opacity" values="1;1;0.6;1;1" keyTimes="0;0.86;0.87;0.89;1" dur="5s" repeatCount="indefinite"/>'
         f'<rect x="40" y="{SY0 + 16}" width="112" height="56" rx="10" fill="none" stroke="{SP[0]}" stroke-width="6" filter="url(#g6)"/>'
         f'<rect x="40" y="{SY0 + 16}" width="112" height="56" rx="10" fill="{SP[1]}" stroke="{SP[2]}" stroke-width="2.5"/>'
         + neon_t(96, SY0 + 58, "18+", 38, SP[0], SP[3], "middle", 1) + '</g>'
         + neon_t(180, SY0 + 58, "尺度全开", 34, SP[4], SP[5])
         + f'<rect x="352" y="{SY0 + 40}" width="8" height="8" fill="{SP[6]}"/>'
         + neon_t(378, SY0 + 58, "真实成人互动", 34, SP[4], SP[5])
         + f'<rect x="{W - 372}" y="{SY0 + 20}" width="2" height="48" fill="#5a4a6a"/>'
         + f'<text x="{W - 40}" y="{SY0 + 40}" font-family="ui-monospace,Consolas,monospace" font-size="15" font-weight="700" fill="#9fe9ff" text-anchor="end" letter-spacing="3">REBUILT FROM SCRATCH</text>'
         + neon_t(W - 40, SY0 + 70, "Claude Opus 5.5 从零重构", 24, "#6fd8ff", "#e6fbff", "end", 1))
# feature band under the room: three pixel icons with a title and one line each
BH = 128
BY = SY0 + 84
H2 = BY + BH
ICONS = {
    "npc": ["...XXXXX...", "..XOOOOOX..", ".XOOOOOOOX.", ".XOEOOOEOX.", ".XOOOOOOOX.", ".XOOHOHOOX.", "..XOOHOOX..",
            "...XXXXX...", ".....X.....", "..XX.X.XX..", ".X..XXX..X."],
    "world": ["...XXXXX...", "..XGGBBBX..", ".XGGGBBBBX.", "XGGGBBBBGGX", "XBGBBBBGGGX", "XBBBBBGGGBX", "XBBBGGGGBBX",
              ".XBBGGGBBX.", "..XBBBBBX..", "...XXXXX...", "....XXX...."],
    "engine": ["....XXX....", ".XX.XOX.XX.", ".XOXXOXXOX.", "..XOOOOOX..", "XXXOOXOOXXX", "XOOOXHXOOOX", "XXXOOXOOXXX",
               "..XOOOOOX..", ".XOXXOXXOX.", ".XX.XOX.XX.", "....XXX...."],
}
PAL = {"npc": {"X": "#ffc54a", "O": "#3a2412", "E": "#fff4dc", "H": "#ff6fae"},
       "world": {"X": "#ffc54a", "G": "#4feedd", "B": "#1d3a6a"},
       "engine": {"X": "#ffc54a", "O": "#5a3a14", "H": "#fff4dc"}}
FEATS = [("npc", "活人感 NPC", "嘴上一套心里一套，心里话你看得见"),
         ("world", "数十个深度世界", "地点、人物、规矩、暗流，各有一整套"),
         ("engine", "自运行状态机", "本地记账，关系和后果都不会忘")]


def icon(kind, x, y, px=5):
    out = []
    for r, row in enumerate(ICONS[kind]):
        for c, ch in enumerate(row):
            if ch != ".":
                out.append(f'<rect x="{x + c * px}" y="{y + r * px}" width="{px}" height="{px}" fill="{PAL[kind][ch]}"/>')
    return f'<g shape-rendering="crispEdges">{"".join(out)}</g>'


CW = W / 3
band = (f'<rect y="{BY}" width="{W}" height="{BH}" fill="#0b0710"/>'
        f'<rect y="{BY}" width="{W}" height="2" fill="#2a1f36"/>'
        + "".join(f'<rect x="{int(CW * i)}" y="{BY + 28}" width="2" height="{BH - 56}" fill="#2a1f36"/>' for i in (1, 2))
        + "".join(f'<ellipse cx="{int(CW * i) + 68}" cy="{BY + 64}" rx="34" ry="34" fill="#ffa82e" fill-opacity="0.18" filter="url(#g15)"/>'
                  + icon(k, int(CW * i) + 40, BY + 36)
                  + neon_t(int(CW * i) + 118, BY + 62, t, 30, SP[4], SP[5], "start", 2)
                  + f'<text x="{int(CW * i) + 120}" y="{BY + 96}" font-family="{SANS}" font-size="17" fill="#cbbcdc" letter-spacing="1">{d}</text>'
                  for i, (k, t, d) in enumerate(FEATS)))
body = f'''    <g shape-rendering="crispEdges">{city.emit(C)}</g>
    <circle cx="{SUNX * C}" cy="{d(SUNY) * C}" r="110" fill="#ffb48a" fill-opacity="0.35" filter="url(#g30)"/>
    <ellipse cx="{sign_cx}" cy="{sign_cy}" rx="200" ry="70" fill="#ff6fae" fill-opacity="0.3" filter="url(#g30)"><animate attributeName="fill-opacity" values="0.3;0.3;0.08;0.3;0.3;0.1;0.3" keyTimes="0;0.7;0.72;0.74;0.9;0.91;1" dur="5s" repeatCount="indefinite"/></ellipse>
    <g shape-rendering="crispEdges">{blinks}{train_g}</g>
    <g clip-path="url(#glass)" fill="#ffffff" fill-opacity="0.05"><path d="M{(WX0 + 20) * C},{WY0 * C} l140,0 l-260,{(WY1 - WY0) * C} l-140,0 Z"/><path d="M{(WX0 + 130) * C},{WY0 * C} l50,0 l-260,{(WY1 - WY0) * C} l-50,0 Z"/></g>
    <g shape-rendering="crispEdges">{room.emit(C)}</g>
    {fairy}
    <circle cx="{OX * C}" cy="{d(OY - 14) * C}" r="60" fill="#9ff0ff" fill-opacity="0.3" filter="url(#g15)"/>
    <ellipse cx="{240 * C}" cy="{d(98) * C}" rx="150" ry="90" fill="#6fd0ff" fill-opacity="0.13" filter="url(#g30)"/>
    <path d="M{204 * C},{d(100) * C} L{216 * C},{d(100) * C} L{236 * C},{d(DT) * C} L{186 * C},{d(DT) * C} Z" fill="url(#lamp)"/>
    <ellipse cx="{210 * C}" cy="{d(DT) * C}" rx="110" ry="24" fill="#ffd27a" fill-opacity="0.22" filter="url(#g15)"/>
    <g shape-rendering="crispEdges">{steam}{cursor}</g>
    <text x="{41.5 * C}" y="{d(70) * C}" font-family="{SANS}" font-size="25" font-weight="800" fill="#ff7ab6" text-anchor="middle" letter-spacing="2" filter="url(#g6)">这次，NPC 是活人。</text>
    <text x="{41.5 * C}" y="{d(70) * C}" font-family="{SANS}" font-size="25" font-weight="800" fill="#ffe3f0" text-anchor="middle" letter-spacing="2" stroke="#ff6fae" stroke-width="1.2">这次，NPC 是活人。</text>
    <rect width="{W}" height="{H}" fill="url(#vig)"/>
    {strip}
    {band}'''
defs = f'''<filter id="g6" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
    <filter id="g15" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="15"/></filter>
    <filter id="g30" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="30"/></filter>
    <linearGradient id="lamp" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe2a0" stop-opacity="0.45"/><stop offset="1" stop-color="#ffe2a0" stop-opacity="0.05"/></linearGradient>
    <radialGradient id="vig" cx="0.5" cy="0.45" r="0.78"><stop offset="0.62" stop-color="#05020a" stop-opacity="0"/><stop offset="1" stop-color="#05020a" stop-opacity="0.5"/></radialGradient>
    <clipPath id="glass"><rect x="{WX0 * C}" y="{WY0 * C}" width="{(WX1 - WX0) * C}" height="{(WY1 - WY0) * C}"/></clipPath>'''
svg = pk.svg_doc(W, H2, "Adult Tension：这次，NPC 是活人。",
                 "像素风黄昏房间：大窗外是粉紫色的霓虹城市和落日，楼顶亮着 ADULT TENSION 的招牌，一列电车从高架上驶过；窗台上一只猫背对着我们；有人盘腿坐在床上低头看发光的手机；书桌显示器里是一来一回的对话；墙上挂着灯会、港口、雪夜的小海报，和一块写着“这次，NPC 是活人。”的霓虹灯牌。底部一行：18+、尺度全开、真实成人互动、Claude Opus 5.5 从零重构。再往下三栏：活人感 NPC、数十个深度世界、自运行状态机。",
                 defs, body)
svg = svg.replace(f'viewBox="0 0 {W} {H2}" width="{W}" height="{H2}"', f'viewBox="0 {TOP} {W} {H2 - TOP}" width="{W}" height="{H2 - TOP}"', 1)
svg = svg.replace(f'<clipPath id="frame"><rect width="{W}" height="{H2}" rx="16"/>', f'<clipPath id="frame"><rect y="{TOP}" width="{W}" height="{H2 - TOP}" rx="16"/>', 1)
assert f'viewBox="0 {TOP} ' in svg and f'<rect y="{TOP}" width="{W}" height="{H2 - TOP}" rx="16"' in svg
open(os.environ.get("LOFI_OUT") or os.path.join(OUT, "hero.svg"), "w", encoding="utf-8", newline="\n").write(svg)
print("room", len(svg) // 1024, "KB")
