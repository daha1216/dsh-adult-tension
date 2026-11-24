"""Dev-only: animated layers for the bedroom hero. Every layer sits on top of the untouched picture; positions are
measured on the 2000x778 source and scaled by S. Loops are slow and staggered so the room breathes without flashing."""
import math
import random

from PIL import Image

T = 20          # shared cycle of the dual-layer dialogue rail, marquee buzz, tension meter, and NPC glint


def kt(n):
    return ";".join(f"{i / n:.4f}" for i in range(n))


def onehot(n, k):
    return ";".join("1" if i == k else "0" for i in range(n))


def blink(dur, pairs, begin=0.0, attr="opacity"):
    """Discrete track: pairs of (time, value) in seconds, value held until the next time."""
    ts = [p[0] for p in pairs]
    assert ts[0] == 0
    return (
        f'<animate attributeName="{attr}" calcMode="discrete" dur="{dur}s" begin="{begin:.2f}s" repeatCount="indefinite" '
        f'values="{";".join(str(v) for _, v in pairs)}" keyTimes="{";".join(f"{t / dur:.4f}" for t in ts)}"/>'
    )


def hexc(c):
    return "#%02x%02x%02x" % c


class FX:
    SEG = {
        "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
        "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg",
    }
    NOTES = [
        ["..XXX.", "..X..X", "..X...", "..X...", "XXX...", "XXX...", ".X...."],
        [".XXXXX", ".X...X", ".X...X", ".X...X", "XX..XX", "XX..XX"],
    ]

    def __init__(self, src, S):
        self.im = Image.open(src).convert("RGB")
        self.S = S
        self.rnd = random.Random(7)

    def p(self, v):
        return round(v * self.S, 1)

    # --- city window lights going off and on -------------------------------------------------------------------------
    def city_lights(self, n=30):
        im, (w, h) = self.im, self.im.size
        skip = [
            (770, 100, 1010, 440), (1205, 205, 1480, 380),
            (1060, 300, 1200, 400), (1460, 230, 1560, 400),
            (1050, 20, 1560, 190),
        ]
        lit = {}
        for y in range(0, 330, 2):
            for x in range(600, 1790, 2):
                if any(a <= x < c and b <= y < d for a, b, c, d in skip):
                    continue
                r, g, b = im.getpixel((x, y))
                if r + g + b > 520:
                    lit[(x, y)] = 1
        seen, blobs = set(), []
        for q in lit:
            if q in seen:
                continue
            stack, pts = [q], []
            seen.add(q)
            while stack:
                x, y = stack.pop()
                pts.append((x, y))
                for nb in ((x + 2, y), (x - 2, y), (x, y + 2), (x, y - 2)):
                    if nb in lit and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            xs, ys = [a for a, _ in pts], [b for _, b in pts]
            bw, bh = max(xs) - min(xs) + 2, max(ys) - min(ys) + 2
            if 3 <= len(pts) <= 30 and bw <= 22 and bh <= 22:
                blobs.append((min(xs), min(ys), bw, bh))
        self.rnd.shuffle(blobs)
        out = []
        for x, y, bw, bh in blobs[:n]:
            ring = [
                self.im.getpixel((min(w - 1, max(0, xx)), min(h - 1, max(0, yy))))
                for xx in range(x - 3, x + bw + 3, 2) for yy in (y - 3, y + bh + 2)
            ]
            ring.sort(key=sum)
            dark = hexc(ring[len(ring) // 3])
            dur = self.rnd.uniform(6, 13)
            t0 = self.rnd.uniform(0.5, dur - 2.5)
            t1 = t0 + self.rnd.uniform(0.8, 2.2)
            out.append(
                f'<rect x="{self.p(x - 1)}" y="{self.p(y - 1)}" width="{self.p(bw + 2)}" height="{self.p(bh + 2)}" fill="{dark}" opacity="0">'
                + blink(dur, [(0, 0), (t0, 1), (t1, 0)], self.rnd.uniform(0, 6)) + "</rect>"
            )
        return f'<g shape-rendering="crispEdges">{"".join(out)}</g>'

    # --- distant skyscraper aviation red beacons ---------------------------------------------------------------------
    def beacons(self):
        pts = [(676, 18, 2.8, 0.0), (1052, 26, 3.4, 1.2), (1492, 16, 2.5, 0.6), (1680, 42, 3.1, 1.9)]
        out = []
        for x, y, dur, beg in pts:
            px_, py_ = self.p(x), self.p(y)
            out.append(
                f'<circle cx="{px_}" cy="{py_}" r="5" fill="#ff3b6b" opacity="0.2" filter="url(#g4)">'
                f'<animate attributeName="opacity" values="0.05;0.55;0.05" dur="{dur}s" begin="{beg}s" repeatCount="indefinite"/></circle>'
                f'<rect x="{px_ - 1}" y="{py_ - 1}" width="2" height="2" fill="#ff94b2">'
                f'<animate attributeName="opacity" values="0.2;1;0.2" dur="{dur}s" begin="{beg}s" repeatCount="indefinite"/></rect>'
            )
        return "".join(out)

    # --- neon signs out of the window: breathing glow plus a rare cut-out -------------------------------------------
    def neon(self):
        signs = [
            (1240, 135, 70, 48, "#ff5fa8", 4.2, 7.9),
            (1150, 218, 70, 22, "#ff6fae", 5.1, 3.3),
            (858, 52, 46, 40, "#ffd0f0", 3.7, 11.2),
            (655, 216, 62, 26, "#7b9dff", 4.8, 6.1),
            (822, 150, 42, 14, "#ff7ad0", 3.3, 9.4),
        ]
        out = []
        for i, (x, y, rx, ry, c, dur, cut) in enumerate(signs):
            out.append(
                f'<ellipse cx="{self.p(x)}" cy="{self.p(y)}" rx="{self.p(rx)}" ry="{self.p(ry)}" fill="{c}" fill-opacity="0.16" filter="url(#g15)">'
                f'<animate attributeName="fill-opacity" values="0.09;0.26;0.09" dur="{dur}s" repeatCount="indefinite" begin="-{i * 0.9:.1f}s"/></ellipse>'
            )
            out.append(
                f'<ellipse cx="{self.p(x)}" cy="{self.p(y)}" rx="{self.p(rx * 0.8)}" ry="{self.p(ry * 0.75)}" fill="#1a0c33" opacity="0" filter="url(#g3)">'
                + blink(13, [(0, 0), (cut, 0.5), (cut + 0.12, 0), (cut + 0.25, 0.35), (cut + 0.33, 0)]) + "</ellipse>"
            )
        return "".join(out)

    # --- non-destructive cinematic lighting pass: lamp warmth, monitor glass veil, upper window sheen, soft vignette -
    def three_point_lighting(self, width, height):
        lamp = (
            '<ellipse cx="145" cy="175" rx="150" ry="90" fill="#ffb86c" fill-opacity="0.09" filter="url(#g15)">'
            '<animate attributeName="fill-opacity" values="0.06;0.13;0.06" dur="6.4s" repeatCount="indefinite"/></ellipse>'
            '<ellipse cx="575" cy="240" rx="115" ry="130" fill="#ff7ab8" fill-opacity="0.06" filter="url(#g15)">'
            '<animate attributeName="fill-opacity" values="0.04;0.09;0.04" dur="5.2s" repeatCount="indefinite"/></ellipse>'
        )
        mon_veil = '<rect x="785" y="145" width="143" height="81" fill="#1b0e30" fill-opacity="0.22"/>'
        glass_sheen = (
            '<g clip-path="url(#winclip)" opacity="0.55">'
            '<polygon points="-160,0 -80,0 -220,160 -300,160" fill="url(#sheen)">'
            '<animateTransform attributeName="transform" type="translate" values="340 0;1280 0" dur="14s" repeatCount="indefinite"/>'
            '</polygon></g>'
        )
        vig = (
            f'<rect width="{width}" height="{height}" fill="url(#roomvig)"/>'
            f'<rect y="{height - 58}" width="{width}" height="58" fill="url(#botfade)"/>'
        )
        return lamp + mon_veil + glass_sheen + vig

    # --- the alarm clock really ticks: seconds 30, 31, ... and a blinking colon -------------------------------------
    def digit(self, d, x, y, w, h, t):
        seg = {
            "a": (x, y, w, t), "b": (x + w - t, y, t, h / 2), "c": (x + w - t, y + h / 2, t, h / 2),
            "d": (x, y + h - t, w, t), "e": (x, y + h / 2, t, h / 2), "f": (x, y, t, h / 2), "g": (x, y + (h - t) / 2, w, t),
        }
        return "".join(f'<rect x="{a:.1f}" y="{b:.1f}" width="{c:.1f}" height="{e:.1f}"/>' for a, b, c, e in (seg[s] for s in self.SEG[d]))

    def clock(self):
        p = self.p
        cover = (
            f'<rect x="{p(203)}" y="{p(377)}" width="{p(49)}" height="{p(37)}" rx="3" fill="#8a0c1a" filter="url(#g3)"/>'
            f'<rect x="{p(207)}" y="{p(382)}" width="{p(42)}" height="{p(29)}" rx="3" fill="#dc2430" filter="url(#g3)"/>'
        )
        x1, x2, y, w, h, t = p(212), p(232), p(384), p(15), p(25), p(4.2)
        ones = "".join(
            f'<g opacity="0">{self.digit(str(k), x2, y, w, h, t)}'
            f'<animate attributeName="opacity" calcMode="discrete" dur="10s" repeatCount="indefinite" values="{onehot(10, k)}" keyTimes="{kt(10)}"/></g>'
            for k in range(10)
        )
        seq = "345012"
        tens = "".join(
            f'<g opacity="0">{self.digit(dg, x1, y, w, h, t)}'
            f'<animate attributeName="opacity" calcMode="discrete" dur="60s" repeatCount="indefinite" values="{onehot(6, k)}" keyTimes="{kt(6)}"/></g>'
            for k, dg in enumerate(seq)
        )
        colon = (
            f'<g>{blink(1, [(0, 1), (0.5, 0.15)])}<rect x="{p(206)}" y="{p(389)}" width="{p(4)}" height="{p(4)}"/>'
            f'<rect x="{p(206)}" y="{p(400)}" width="{p(4)}" height="{p(4)}"/></g>'
        )
        body = ones + tens + colon
        return cover + f'<g fill="#ff6a50" filter="url(#g3)">{body}</g><g fill="#ffb08e" shape-rendering="crispEdges">{body}</g>'

    # --- the monitor and the harmonized violet/pink laptop equalizer ------------------------------------------------
    def screens(self):
        p = self.p
        glow = (
            f'<ellipse cx="{p(1340)}" cy="{p(290)}" rx="{p(165)}" ry="{p(96)}" fill="#b69eff" fill-opacity="0.06" filter="url(#g15)">'
            '<animate attributeName="fill-opacity" values="0.04;0.12;0.06;0.10;0.04" dur="4.8s" repeatCount="indefinite"/></ellipse>'
            f'<rect x="{p(1228)}" y="{p(228)}" width="{p(224)}" height="{p(5)}" fill="#e6dcff" fill-opacity="0.09">'
            f'<animate attributeName="y" values="{p(228)};{p(346)}" dur="3.4s" repeatCount="indefinite"/></rect>'
        )
        bars, x0, base, top = [], 1531, 411, 352
        for i in range(12):
            col = "#ff6fae" if i % 2 == 0 else "#b48aff"
            hs = [self.rnd.randint(10, base - top - 2) for _ in range(8)]
            hs.append(hs[0])
            dur = self.rnd.choice([2.4, 2.8, 3.2])
            bars.append(
                f'<rect x="{p(x0 + i * 10.6)}" width="{p(4.5)}" fill="{col}">'
                f'<animate attributeName="height" calcMode="discrete" dur="{dur}s" repeatCount="indefinite" values="{";".join(str(p(v)) for v in hs)}"/>'
                f'<animate attributeName="y" calcMode="discrete" dur="{dur}s" repeatCount="indefinite" values="{";".join(str(p(base - v)) for v in hs)}"/></rect>'
            )
        laptop = f'<rect x="{p(1526)}" y="{p(top - 2)}" width="{p(138)}" height="{p(base - top + 4)}" fill="#0b0512"/><g shape-rendering="crispEdges">{"".join(bars)}</g>'
        return glow + laptop

    # --- floating dust in the lamp light and window light -----------------------------------------------------------
    def dust(self, n=16):
        out = []
        for i in range(n):
            if i < 10:
                x, y = self.rnd.uniform(25, 330), self.rnd.uniform(120, 260)
            else:
                x, y = self.rnd.uniform(380, 500), self.rnd.uniform(130, 250)
            dur, dx, dy = self.rnd.uniform(7, 12), self.rnd.uniform(-10, 14), -self.rnd.uniform(18, 40)
            out.append(
                f'<rect x="{x:.0f}" y="{y:.0f}" width="2" height="2" fill="#ffe2b8" opacity="0">'
                f'<animate attributeName="opacity" values="0;0.75;0.55;0" dur="{dur:.1f}s" begin="-{self.rnd.uniform(0, dur):.1f}s" repeatCount="indefinite"/>'
                f'<animateTransform attributeName="transform" type="translate" values="0 0;{dx:.0f} {dy:.0f}" dur="{dur:.1f}s" begin="-{self.rnd.uniform(0, dur):.1f}s" repeatCount="indefinite"/></rect>'
            )
        return "".join(out)

    # --- S-curve floating pixel notes + subtle guitar harmonic pluck ripples ----------------------------------------
    def notes(self):
        out, ox, oy, px = [], 634, 272, 3
        ripple = (
            '<circle cx="595" cy="285" r="8" fill="none" stroke="#ff8fc4" stroke-width="1.5" opacity="0">'
            '<animate attributeName="r" values="8;44" dur="2.8s" begin="0.4s" repeatCount="indefinite"/>'
            '<animate attributeName="opacity" values="0.42;0.18;0" keyTimes="0;0.45;1" dur="2.8s" begin="0.4s" repeatCount="indefinite"/></circle>'
            '<circle cx="595" cy="285" r="6" fill="none" stroke="#c9a2ff" stroke-width="1.2" opacity="0">'
            '<animate attributeName="r" values="6;36" dur="2.8s" begin="1.8s" repeatCount="indefinite"/>'
            '<animate attributeName="opacity" values="0.34;0.14;0" keyTimes="0;0.45;1" dur="2.8s" begin="1.8s" repeatCount="indefinite"/></circle>'
        )
        specs = [
            (0, "#ff8fc4", 4.6, 56, 0.0, 12),
            (1, "#d8c4ff", 5.2, 38, 1.6, -10),
            (0, "#f2cf94", 4.4, 74, 3.1, 14),
        ]
        for shape, col, dur, dx, begin, sway in specs:
            cells = "".join(
                f'<rect x="{c * px}" y="{r * px}" width="{px}" height="{px}"/>'
                for r, row in enumerate(self.NOTES[shape]) for c, ch in enumerate(row) if ch == "X"
            )
            pts = []
            for k in range(9):
                t = k / 8
                px_ = dx * t + math.sin(t * math.pi * 2) * sway
                py_ = -96 * t
                pts.append(f"{px_:.1f} {py_:.1f}")
            out.append(
                f'<g opacity="0">'
                f'<animate attributeName="opacity" values="0;0.95;0.95;0" keyTimes="0;0.14;0.68;1" dur="{dur}s" begin="-{begin}s" repeatCount="indefinite"/>'
                f'<animateTransform attributeName="transform" type="translate" values="{";".join(pts)}" dur="{dur}s" begin="-{begin}s" repeatCount="indefinite"/>'
                f'<g transform="translate({ox} {oy})" fill="{col}" shape-rendering="crispEdges">'
                f'<g fill="#10061a" opacity="0.65" transform="translate(2 2)">{cells}</g>{cells}</g></g>'
            )
        return ripple + "".join(out)
