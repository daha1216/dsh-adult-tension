"""Dev-only: animated layers for the bedroom hero. Every layer sits on top of the untouched picture; positions are
measured on the 2000x778 source and scaled by S. Loops are slow and staggered so the room breathes without flashing."""
import random

from PIL import Image

T = 16          # shared cycle of the title and the tagline


def kt(n):
    return ";".join(f"{i / n:.4f}" for i in range(n))


def onehot(n, k):
    return ";".join("1" if i == k else "0" for i in range(n))


def blink(dur, pairs, begin=0.0, attr="opacity"):
    """Discrete opacity track: pairs of (time, value) in seconds, value held until the next time."""
    ts = [p[0] for p in pairs]
    assert ts[0] == 0
    return (f'<animate attributeName="{attr}" calcMode="discrete" dur="{dur}s" begin="{begin:.2f}s" repeatCount="indefinite" '
            f'values="{";".join(str(v) for _, v in pairs)}" keyTimes="{";".join(f"{t / dur:.4f}" for t in ts)}"/>')


def hexc(c):
    return "#%02x%02x%02x" % c


class FX:
    def __init__(self, src, S):
        self.im = Image.open(src).convert("RGB")
        self.S = S
        self.rnd = random.Random(7)

    def p(self, v):
        return round(v * self.S, 1)

    # --- city window lights going off and on -------------------------------------------------------------------------
    def city_lights(self, n=30):
        im, (w, h) = self.im, self.im.size
        skip = [(770, 100, 1010, 440), (1205, 205, 1480, 380), (1060, 300, 1200, 400), (1460, 230, 1560, 400),
                (1050, 20, 1560, 190)]                                     # girl, monitor, small laptop, plant, title
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
            ring = [self.im.getpixel((min(w - 1, max(0, xx)), min(h - 1, max(0, yy))))
                    for xx in range(x - 3, x + bw + 3, 2) for yy in (y - 3, y + bh + 2)]
            ring.sort(key=sum)
            dark = hexc(ring[len(ring) // 3])
            dur = self.rnd.uniform(6, 13)
            t0 = self.rnd.uniform(0.5, dur - 2.5)
            t1 = t0 + self.rnd.uniform(0.8, 2.2)
            out.append(f'<rect x="{self.p(x - 1)}" y="{self.p(y - 1)}" width="{self.p(bw + 2)}" height="{self.p(bh + 2)}" fill="{dark}" opacity="0">'
                       + blink(dur, [(0, 0), (t0, 1), (t1, 0)], self.rnd.uniform(0, 6)) + '</rect>')
        return f'<g shape-rendering="crispEdges">{"".join(out)}</g>'

    # --- neon signs out of the window: breathing glow plus a rare cut-out ----------------------------------------------
    def neon(self):
        signs = [(1240, 135, 70, 48, "#ff5fa8", 4.2, 7.9), (1150, 218, 70, 22, "#ff6fae", 5.1, 3.3),
                 (858, 52, 46, 40, "#ffd0f0", 3.7, 11.2), (655, 216, 62, 26, "#57c8ff", 4.8, 6.1),
                 (822, 150, 42, 14, "#ff7ad0", 3.3, 9.4)]
        out = []
        for i, (x, y, rx, ry, c, dur, cut) in enumerate(signs):
            out.append(f'<ellipse cx="{self.p(x)}" cy="{self.p(y)}" rx="{self.p(rx)}" ry="{self.p(ry)}" fill="{c}" fill-opacity="0.18" filter="url(#g15)">'
                       f'<animate attributeName="fill-opacity" values="0.1;0.3;0.1" dur="{dur}s" repeatCount="indefinite" begin="-{i * 0.9:.1f}s"/></ellipse>')
            out.append(f'<ellipse cx="{self.p(x)}" cy="{self.p(y)}" rx="{self.p(rx * 0.8)}" ry="{self.p(ry * 0.75)}" fill="#1a0c33" opacity="0" filter="url(#g3)">'
                       + blink(13, [(0, 0), (cut, 0.55), (cut + 0.12, 0), (cut + 0.25, 0.4), (cut + 0.33, 0)]) + '</ellipse>')
        return "".join(out)

    # --- the alarm clock really ticks: seconds 30, 31, ... and a blinking colon ----------------------------------------
    SEG = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc", "7": "abc",
           "8": "abcdefg", "9": "abcdfg"}

    def digit(self, d, x, y, w, h, t):
        seg = {"a": (x, y, w, t), "b": (x + w - t, y, t, h / 2), "c": (x + w - t, y + h / 2, t, h / 2),
               "d": (x, y + h - t, w, t), "e": (x, y + h / 2, t, h / 2), "f": (x, y, t, h / 2), "g": (x, y + (h - t) / 2, w, t)}
        return "".join(f'<rect x="{a:.1f}" y="{b:.1f}" width="{c:.1f}" height="{e:.1f}"/>' for a, b, c, e in (seg[s] for s in self.SEG[d]))

    def clock(self):
        p = self.p
        # the seconds sit in a red bloom: dark-red rim, bright-red middle, both soft-edged like the picture's glow
        cover = (f'<rect x="{p(203)}" y="{p(377)}" width="{p(49)}" height="{p(37)}" rx="3" fill="#8a0c1a" filter="url(#g3)"/>'
                 f'<rect x="{p(207)}" y="{p(382)}" width="{p(42)}" height="{p(29)}" rx="3" fill="#dc2430" filter="url(#g3)"/>')
        x1, x2, y, w, h, t = p(212), p(232), p(384), p(15), p(25), p(4.2)
        ones = "".join(f'<g opacity="0">{self.digit(str(k), x2, y, w, h, t)}'
                       f'<animate attributeName="opacity" calcMode="discrete" dur="10s" repeatCount="indefinite" values="{onehot(10, k)}" keyTimes="{kt(10)}"/></g>'
                       for k in range(10))
        seq = "345012"
        tens = "".join(f'<g opacity="0">{self.digit(dg, x1, y, w, h, t)}'
                       f'<animate attributeName="opacity" calcMode="discrete" dur="60s" repeatCount="indefinite" values="{onehot(6, k)}" keyTimes="{kt(6)}"/></g>'
                       for k, dg in enumerate(seq))
        colon = (f'<g>{blink(1, [(0, 1), (0.5, 0.15)])}<rect x="{p(206)}" y="{p(389)}" width="{p(4)}" height="{p(4)}"/>'
                 f'<rect x="{p(206)}" y="{p(400)}" width="{p(4)}" height="{p(4)}"/></g>')
        body = ones + tens + colon
        return (cover + f'<g fill="#ff6a50" filter="url(#g3)">{body}</g>'
                + f'<g fill="#ffb08e" shape-rendering="crispEdges">{body}</g>')

    # --- the monitor and the trading laptop -----------------------------------------------------------------------------
    def screens(self):
        p = self.p
        glow = (f'<ellipse cx="{p(1340)}" cy="{p(290)}" rx="{p(175)}" ry="{p(105)}" fill="#a8d8ff" fill-opacity="0.08" filter="url(#g15)">'
                '<animate attributeName="fill-opacity" values="0.05;0.16;0.08;0.13;0.05" dur="4.5s" repeatCount="indefinite"/></ellipse>'
                f'<rect x="{p(1228)}" y="{p(228)}" width="{p(224)}" height="{p(124)}" fill="#ffffff" fill-opacity="0">'
                '<animate attributeName="fill-opacity" values="0;0.07;0;0.04;0" dur="4.5s" repeatCount="indefinite"/></rect>'
                f'<rect x="{p(1228)}" y="{p(228)}" width="{p(224)}" height="{p(6)}" fill="#ffffff" fill-opacity="0.08">'
                f'<animate attributeName="y" values="{p(228)};{p(346)}" dur="3.2s" repeatCount="indefinite"/></rect>')
        bars, x0, base, top = [], 1531, 411, 352
        for i in range(12):
            col = "#e0525e" if i % 2 == 0 else "#5fd0b8"
            hs = [self.rnd.randint(10, base - top - 2) for _ in range(6)]
            hs.append(hs[0])
            dur = self.rnd.choice([2.4, 3.0, 3.6])
            bars.append(f'<rect x="{p(x0 + i * 10.6)}" width="{p(4.5)}" fill="{col}">'
                        f'<animate attributeName="height" calcMode="discrete" dur="{dur}s" repeatCount="indefinite" values="{";".join(str(p(v)) for v in hs)}"/>'
                        f'<animate attributeName="y" calcMode="discrete" dur="{dur}s" repeatCount="indefinite" values="{";".join(str(p(base - v)) for v in hs)}"/></rect>')
        laptop = f'<rect x="{p(1526)}" y="{p(top - 2)}" width="{p(138)}" height="{p(base - top + 4)}" fill="#050204"/><g shape-rendering="crispEdges">{"".join(bars)}</g>'
        return glow + laptop

    # --- floating dust in the lamp light and the window light -------------------------------------------------------
    def dust(self, n=16):
        out = []
        for i in range(n):
            if i < 10:
                x, y = self.rnd.uniform(25, 330), self.rnd.uniform(120, 260)
            else:
                x, y = self.rnd.uniform(380, 490), self.rnd.uniform(130, 250)
            dur, dx, dy = self.rnd.uniform(7, 12), self.rnd.uniform(-10, 14), -self.rnd.uniform(18, 40)
            out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="2" height="2" fill="#ffe2b8" opacity="0">'
                       f'<animate attributeName="opacity" values="0;0.75;0.6;0" dur="{dur:.1f}s" begin="-{self.rnd.uniform(0, dur):.1f}s" repeatCount="indefinite"/>'
                       f'<animateTransform attributeName="transform" type="translate" values="0 0;{dx:.0f} {dy:.0f}" dur="{dur:.1f}s" begin="-{self.rnd.uniform(0, dur):.1f}s" repeatCount="indefinite"/></rect>')
        return "".join(out)

    # --- pixel notes rising off the guitar ------------------------------------------------------------------------------
    NOTES = [["..XXX.", "..X..X", "..X...", "..X...", "XXX...", "XXX...", ".X...."],
             [".XXXXX", ".X...X", ".X...X", ".X...X", "XX..XX", "XX..XX"]]

    def notes(self):
        out, ox, oy, px = [], 640, 268, 3
        for i, (shape, col, dur, dx, begin) in enumerate([(0, "#ff8fc4", 4.2, 70, 0), (1, "#e9dcff", 4.8, 46, 1.5),
                                                          (0, "#ffd27a", 4.0, 92, 2.9)]):
            cells = "".join(f'<rect x="{c * px}" y="{r * px}" width="{px}" height="{px}"/>'
                            for r, row in enumerate(self.NOTES[shape]) for c, ch in enumerate(row) if ch == "X")
            path = f"0 0;{dx * 0.3:.0f} -28;{dx * 0.55:.0f} -50;{dx * 0.8:.0f} -72;{dx} -92"
            out.append(f'<g opacity="0"><animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.15;0.6;1" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>'
                       f'<animateTransform attributeName="transform" type="translate" values="{path}" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>'
                       f'<g transform="translate({ox} {oy})" fill="{col}" shape-rendering="crispEdges">'
                       f'<g fill="#0b0710" opacity="0.5" transform="translate(2 2)">{cells}</g>{cells}</g></g>')
        return "".join(out)


def title_track(i):
    """ADULT TENSION letter i: lights up in turn, holds, a couple of letters flicker, all go dark before the loop."""
    on = 0.3 + i * 0.09
    pairs = [(0, 0.15), (on, 1)]
    if i in (2, 9):
        pairs += [(9.0 + i * 0.01, 0.25), (9.12, 1), (9.3, 0.4), (9.36, 1)]
    pairs.append((15.6, 0.15))
    return blink(T, pairs, attr="fill-opacity") + blink(T, pairs, attr="stroke-opacity")


def type_track(n):
    """Tagline character n: typed in after the title lights, held, cleared before the loop."""
    return blink(T, [(0, 0), (2.0 + n * 0.12, 1), (15.6, 0)])
