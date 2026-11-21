#!/usr/bin/env python3
"""SOLMERE — a travel poster for a place that does not exist.

Renders a vintage-style travel poster (pure Python standard library, no
network, no third-party packages) and writes it to entry.png in the
output directory ($MAKEFUN_OUTPUT_DIR, else /output, else ./out).

The poster: at Solmere the sun sets twice — once into the sea, and once
again in the mirror-still bay beneath the lighthouse headland. The scene
is drawn procedurally (gradients, span fills, scanline polygons and a
small hand-made stroke alphabet for the place's name) on a supersampled
canvas and downsampled for smooth edges.
"""

import math
import os
import struct
import zlib

# ---------------------------------------------------------------- canvas

FINAL_W, FINAL_H = 832, 1024          # the poster's real size (<=1024x1024)
SS = 2                                # supersampling factor
W, H = FINAL_W * SS, FINAL_H * SS     # working canvas

buf = bytearray(W * H * 3)


def px(x, y, rgb):
    """Set one pixel (working-canvas coordinates)."""
    i = (y * W + x) * 3
    buf[i] = rgb[0]
    buf[i + 1] = rgb[1]
    buf[i + 2] = rgb[2]


def fill_span(y, x0, x1, rgb):
    """Fill a horizontal run of pixels on row y, clipped to the canvas."""
    if y < 0 or y >= H:
        return
    x0 = max(0, x0)
    x1 = min(W - 1, x1)
    if x1 < x0:
        return
    row = bytes(rgb) * (x1 - x0 + 1)
    i = (y * W + x0) * 3
    buf[i:i + len(row)] = row


def fill_rect(x0, y0, x1, y1, rgb):
    for y in range(max(0, y0), min(H, y1 + 1)):
        fill_span(y, x0, x1, rgb)


def blend_span(y, x0, x1, rgb, alpha):
    """Alpha-blend a horizontal run over whatever is already drawn."""
    if y < 0 or y >= H:
        return
    x0 = max(0, x0)
    x1 = min(W - 1, x1)
    if x1 < x0:
        return
    inv = 1.0 - alpha
    i = (y * W + x0) * 3
    for k in range(x1 - x0 + 1):
        j = i + 3 * k
        buf[j] = int(buf[j] * inv + rgb[0] * alpha)
        buf[j + 1] = int(buf[j + 1] * inv + rgb[1] * alpha)
        buf[j + 2] = int(buf[j + 2] * inv + rgb[2] * alpha)


def fill_circle(cx, cy, r, rgb):
    """Filled circle via row spans."""
    r = int(math.ceil(r))
    for dy in range(-r, r + 1):
        y = cy + dy
        if 0 <= y < H:
            half = int(math.sqrt(max(0.0, r * r - dy * dy)))
            fill_span(y, cx - half, cx + half, rgb)


def fill_polygon(points, rgb):
    """Scanline even-odd polygon fill. points are (x, y) working coords."""
    ys = [p[1] for p in points]
    y_lo = max(0, int(math.floor(min(ys))))
    y_hi = min(H - 1, int(math.ceil(max(ys))))
    n = len(points)
    for y in range(y_lo, y_hi + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            if y1 == y2:
                continue
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                t = (yc - y1) / (y2 - y1)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            fill_span(y, int(math.ceil(xs[k])), int(math.floor(xs[k + 1])), rgb)


def blend_polygon(points, rgb, alpha):
    """Polygon fill with per-pixel alpha blending (for the light beam)."""
    ys = [p[1] for p in points]
    y_lo = max(0, int(math.floor(min(ys))))
    y_hi = min(H - 1, int(math.ceil(max(ys))))
    n = len(points)
    for y in range(y_lo, y_hi + 1):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % n]
            if y1 == y2:
                continue
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                t = (yc - y1) / (y2 - y1)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            blend_span(y, int(math.ceil(xs[k])), int(math.floor(xs[k + 1])),
                       rgb, alpha)


def thick_line(x1, y1, x2, y2, r, rgb):
    """A round-capped thick line: circles stamped along the segment."""
    steps = max(1, int(math.hypot(x2 - x1, y2 - y1) / max(1.0, r * 0.5)))
    for s in range(steps + 1):
        t = s / steps
        fill_circle(int(x1 + (x2 - x1) * t), int(y1 + (y2 - y1) * t), r, rgb)


# ---------------------------------------------------------------- helpers

def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return (int(lerp(c1[0], c2[0], t)),
            int(lerp(c1[1], c2[1], t)),
            int(lerp(c1[2], c2[2], t)))


def gradient_color(stops, t):
    """stops: sorted list of (position, rgb)."""
    if t <= stops[0][0]:
        return stops[0][1]
    for i in range(len(stops) - 1):
        p1, c1 = stops[i]
        p2, c2 = stops[i + 1]
        if t <= p2:
            return lerp_color(c1, c2, (t - p1) / (p2 - p1))
    return stops[-1][1]


class Lcg:
    """Tiny deterministic pseudo-random generator (seeded, stable)."""

    def __init__(self, seed):
        self.state = seed & 0x7FFFFFFF

    def next(self):
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.state / 0x7FFFFFFF


def S(v):
    """Scale a final-poster coordinate to the working canvas."""
    return int(round(v * SS))


# ---------------------------------------------------------------- palette

CREAM = (247, 237, 216)
INK = (30, 27, 54)            # deep plum-navy for silhouettes
SUN_CORE = (255, 232, 176)
LAMP = (255, 214, 110)
CORAL = (217, 93, 78)

SKY_STOPS = [
    (0.00, (34, 46, 92)),
    (0.34, (101, 66, 116)),
    (0.60, (188, 90, 99)),
    (0.84, (240, 138, 90)),
    (1.00, (249, 199, 132)),
]
SEA_STOPS = [
    (0.00, (214, 118, 84)),
    (0.30, (148, 84, 106)),
    (0.68, (66, 62, 108)),
    (1.00, (35, 42, 82)),
]

HORIZON = 600                 # final coords: where sky meets sea


def sky_color_at(y_final):
    return gradient_color(SKY_STOPS, y_final / HORIZON)


# ---------------------------------------------------------------- scene

def draw_sky_and_sea():
    for y in range(H):
        yf = y / SS
        if yf < HORIZON:
            c = gradient_color(SKY_STOPS, yf / HORIZON)
        else:
            c = gradient_color(SEA_STOPS, (yf - HORIZON) / (FINAL_H - HORIZON))
        fill_span(y, 0, W - 1, c)


def draw_stars():
    rng = Lcg(20261121)
    for _ in range(150):
        xf = rng.next() * FINAL_W
        yf = 30 + rng.next() * 330
        fade = 1.0 - yf / 420.0
        if fade <= 0.15:
            continue
        base = sky_color_at(yf)
        c = lerp_color(base, (255, 246, 224), 0.35 + 0.55 * fade * rng.next())
        x, y = S(xf), S(yf)
        px(x, y, c)
        if rng.next() > 0.72:
            px(x + 1, y, c)
            px(x, y + 1, c)


def draw_sun():
    cx, cy, r = S(430), S(HORIZON), S(148)
    # posterised glow: two flat halos, then the core disc
    fill_circle(cx, cy, r + S(46), (243, 166, 96))
    fill_circle(cx, cy, r + S(22), (248, 190, 110))
    fill_circle(cx, cy, r, SUN_CORE)
    # retro bands: thin sky-coloured stripes cut across the sun's face,
    # clipped to the disc's chord so the sky itself stays clean
    for yy, hh in [(536, 4), (560, 6), (586, 8)]:
        c = sky_color_at(yy - 30)
        mid = yy + hh / 2 - HORIZON
        half = int(math.sqrt(max(0.0, 148 * 148 - mid * mid)))
        fill_rect(S(430 - half), S(yy), S(430 + half), S(yy + hh), c)


def draw_sea_over_sun():
    """The sea covers the sun's drowned half; only the reflection stays."""
    for y in range(S(HORIZON), H):
        yf = y / SS
        c = gradient_color(SEA_STOPS, (yf - HORIZON) / (FINAL_H - HORIZON))
        fill_span(y, 0, W - 1, c)


def draw_beam(lamp_x, lamp_y):
    """A soft wedge of light sweeping from the lighthouse to the right."""
    pts = [(S(lamp_x), S(lamp_y)),
           (S(838), S(268)),
           (S(838), S(408)),
           (S(lamp_x), S(lamp_y + 16))]
    blend_polygon(pts, (255, 224, 150), 0.13)
    blend_polygon([(x, y + S(4)) for (x, y) in
                   [(S(lamp_x), S(lamp_y)), (S(838), S(292)),
                    (S(838), S(384)), (S(lamp_x), S(lamp_y + 12))]],
                  (255, 230, 170), 0.10)


def draw_reflection():
    rng = Lcg(777)
    cx = 430.0
    for yf in range(HORIZON + 6, 946):
        depth = (yf - HORIZON) / (FINAL_H - HORIZON)
        half_w = 24 + depth * 120
        wobble = math.sin(yf * 0.11) * 6 + (rng.next() - 0.5) * 10
        sea = gradient_color(SEA_STOPS, depth)
        lit = lerp_color(sea, SUN_CORE, 0.55 - depth * 0.30)
        x = cx + wobble - half_w
        end = cx + wobble + half_w
        while x < end:
            seg = 6 + rng.next() * 26
            if rng.next() > 0.30:
                fill_span(S(yf), S(x), S(min(end, x + seg)), lit)
            x += seg + 4 + rng.next() * 14


def draw_headland_and_lighthouse():
    # rocky headland jutting in from the left
    headland = [(0, 566), (96, 556), (178, 552), (238, 560), (286, 578),
                (306, 606), (282, 640), (196, 660), (96, 664), (0, 656)]
    fill_polygon([(S(x), S(y)) for (x, y) in headland], INK)

    # lighthouse: a tapered tower on the point, cream and coral bands
    base_y, top_y = 560, 428
    bx, tx = 232, 224                       # tower centre drifts slightly
    for band, (yf0, yf1, c) in enumerate([
            (428, 452, CORAL), (452, 482, CREAM), (482, 512, CORAL),
            (512, 560, CREAM)]):
        w0 = 15 + (yf0 - top_y) * 0.055
        w1 = 15 + (yf1 - top_y) * 0.055
        cx0 = bx + (tx - bx) * (yf0 - top_y) / (base_y - top_y)
        cx1 = bx + (tx - bx) * (yf1 - top_y) / (base_y - top_y)
        fill_polygon([(S(cx0 - w0), S(yf0)), (S(cx0 + w0), S(yf0)),
                      (S(cx1 + w1), S(yf1)), (S(cx1 - w1), S(yf1))], c)
    # gallery + lamp room + cap
    fill_rect(S(tx - 17), S(414), S(tx + 17), S(428), INK)
    fill_rect(S(tx - 11), S(392), S(tx + 11), S(414), LAMP)
    fill_polygon([(S(tx - 15), S(392)), (S(tx + 15), S(392)),
                  (S(tx + 4), S(376)), (S(tx - 4), S(376))], INK)
    # lamp glow
    fill_circle(S(tx), S(403), S(15), LAMP)
    fill_circle(S(tx), S(403), S(7), (255, 240, 200))

    # two tiny cottages with lit windows on the slope
    for hx, hy, hw, hh in [(96, 540, 40, 24), (148, 532, 30, 20)]:
        fill_rect(S(hx), S(hy), S(hx + hw), S(hy + hh), INK)
        fill_polygon([(S(hx - 4), S(hy)), (S(hx + hw + 4), S(hy)),
                      (S(hx + hw - 6), S(hy - 12)), (S(hx + 6), S(hy - 12))],
                     INK)
        fill_rect(S(hx + 8), S(hy + 8), S(hx + 14), S(hy + 14), LAMP)
        fill_rect(S(hx + hw - 14), S(hy + 8), S(hx + hw - 8), S(hy + 14), LAMP)


def draw_boat():
    # a small sailboat silhouette, right of the reflection
    hull = [(596, 726), (668, 726), (652, 742), (610, 742)]
    fill_polygon([(S(x), S(y)) for (x, y) in hull], INK)
    fill_polygon([(S(630), S(724)), (S(630), S(668)), (S(662), S(724))], INK)
    fill_polygon([(S(624), S(724)), (S(624), S(680)), (S(600), S(724))],
                 (43, 38, 74))


def draw_foreground():
    left = [(0, 1024), (0, 918), (88, 884), (196, 892), (268, 940),
            (300, 1024)]
    right = [(832, 1024), (832, 936), (742, 898), (648, 900), (580, 946),
             (556, 1024)]
    fill_polygon([(S(x), S(y)) for (x, y) in left], INK)
    fill_polygon([(S(x), S(y)) for (x, y) in right], INK)
    # two cypress spikes on the right hill
    for cx, base, h in [(716, 906, 86), (756, 922, 62)]:
        fill_polygon([(S(cx - 9), S(base)), (S(cx + 9), S(base)),
                      (S(cx), S(base - h))], INK)


def draw_birds():
    for cx, cy, s in [(588, 236, 13), (636, 268, 10), (548, 292, 9)]:
        x, y = S(cx), S(cy)
        r = max(2, S(2.2))
        thick_line(x - S(s), y, x, y - S(s * 0.55), r, INK)
        thick_line(x, y - S(s * 0.55), x + S(s), y, r, INK)


def draw_border():
    m = S(26)
    fill_rect(m, m, W - 1 - m, m + S(5), CREAM)
    fill_rect(m, H - 1 - m - S(5), W - 1 - m, H - 1 - m, CREAM)
    fill_rect(m, m, m + S(5), H - 1 - m, CREAM)
    fill_rect(W - 1 - m - S(5), m, W - 1 - m, H - 1 - m, CREAM)
    m2 = S(40)
    fill_rect(m2, m2, W - 1 - m2, m2 + S(1.6), CREAM)
    fill_rect(m2, H - 1 - m2 - S(1.6), W - 1 - m2, H - 1 - m2, CREAM)
    fill_rect(m2, m2, m2 + S(1.6), H - 1 - m2, CREAM)
    fill_rect(W - 1 - m2 - S(1.6), m2, W - 1 - m2, H - 1 - m2, CREAM)


# ------------------------------------------------------- the name, by hand
# A small stroke alphabet on a 10 x 14 grid (y down), just the letters
# SOLMERE needs. Polylines are stamped with round nibs, poster-style.

GLYPHS = {
    "S": [[(8.6, 2.2), (7.0, 0.7), (4.6, 0.3), (2.6, 1.0), (1.4, 2.8),
           (1.6, 4.8), (3.2, 6.2), (5.6, 7.2), (7.6, 8.3), (8.7, 10.0),
           (8.3, 12.2), (6.6, 13.6), (4.2, 14.0), (2.2, 13.4), (1.0, 11.8)]],
    "L": [[(2.2, 0.0), (2.2, 13.7), (8.8, 13.7)]],
    "M": [[(1.2, 14.0), (1.2, 0.0), (5.0, 6.0), (8.8, 0.0), (8.8, 14.0)]],
    "E": [[(8.6, 0.2), (2.2, 0.2), (2.2, 13.8), (8.6, 13.8)],
          [(2.2, 7.0), (7.2, 7.0)]],
    "R": [[(2.2, 14.0), (2.2, 0.0), (6.2, 0.0)],
          [(2.2, 7.0), (6.4, 7.0)],
          [(5.6, 7.0), (9.0, 14.0)]],
}


def draw_letter_o(cx, cy, rx, ry, nib, rgb):
    steps = 64
    prev = None
    for i in range(steps + 1):
        a = 2 * math.pi * i / steps
        p = (cx + rx * math.cos(a), cy + ry * math.sin(a))
        if prev is not None:
            thick_line(int(prev[0]), int(prev[1]), int(p[0]), int(p[1]),
                       nib, rgb)
        prev = p


def draw_name():
    name = "SOLMERE"
    advance, spacing = 10.0, 3.4
    total_units = len(name) * advance + (len(name) - 1) * spacing
    avail = FINAL_W - 2 * 26 - 2 * 34            # inside the frame
    unit = avail / total_units                   # final px per grid unit
    height = 14 * unit
    x0 = (FINAL_W - total_units * unit) / 2
    y0 = 64.0                                    # top of the cap height
    nib = max(2, S(unit * 0.82))
    for layer, dy, rgb in [(0, 5.0, INK), (1, 0.0, CREAM)]:
        ox = x0
        for ch in name:
            gx, gy = S(ox), S(y0 + dy)
            su = unit * SS
            if ch == "O":
                draw_letter_o(gx + int(5 * su), gy + int(7 * su),
                              4.3 * su, 6.7 * su, nib, rgb)
            else:
                for stroke in GLYPHS[ch]:
                    pts = [(gx + int(x * su), gy + int(y * su))
                           for (x, y) in stroke]
                    if ch == "R" and stroke is GLYPHS["R"][0]:
                        # close the bowl with an arc after the stem+top
                        pass
                    for a, b in zip(pts, pts[1:]):
                        thick_line(a[0], a[1], b[0], b[1], nib, rgb)
                    if ch == "R" and stroke is GLYPHS["R"][0]:
                        cx = gx + int(6.2 * su)
                        cy = gy + int(3.5 * su)
                        prev = None
                        for i in range(17):
                            ang = -math.pi / 2 + math.pi * i / 16
                            p = (cx + int(2.7 * su * math.cos(ang)),
                                 cy + int(3.5 * su * math.sin(ang)))
                            if prev is not None:
                                thick_line(prev[0], prev[1], p[0], p[1],
                                           nib, rgb)
                            prev = p
            ox += (advance + spacing) * unit
    return y0 + height


# ---------------------------------------------------------------- output

def downsample():
    out = bytearray(FINAL_W * FINAL_H * 3)
    for y in range(FINAL_H):
        for x in range(FINAL_W):
            i00 = ((2 * y) * W + 2 * x) * 3
            r = g = b = 0
            for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                j = i00 + dy * W * 3 + dx * 3
                r += buf[j]
                g += buf[j + 1]
                b += buf[j + 2]
            o = (y * FINAL_W + x) * 3
            out[o] = r >> 2
            out[o + 1] = g >> 2
            out[o + 2] = b >> 2
    return out


def encode_png(pixels, quantise=1):
    raw = bytearray()
    stride = FINAL_W * 3
    for y in range(FINAL_H):
        raw.append(0)
        row = pixels[y * stride:(y + 1) * stride]
        if quantise > 1:
            row = bytes((v // quantise) * quantise for v in row)
        raw += row

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", FINAL_W, FINAL_H, 8, 2,
                                      0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    return png


def main():
    draw_sky_and_sea()
    draw_stars()
    draw_sun()
    draw_sea_over_sun()
    draw_reflection()
    draw_headland_and_lighthouse()
    draw_beam(224, 403)
    draw_boat()
    draw_foreground()
    draw_birds()
    draw_border()
    draw_name()

    pixels = downsample()
    png = encode_png(pixels)
    q = 2
    while len(png) > 1_000_000 and q <= 16:      # stay under the 1 MiB gate
        png = encode_png(pixels, q)
        q *= 2

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or (
        "/output" if os.path.isdir("/output") else "out")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(png)
    print(f"wrote {path}: {FINAL_W}x{FINAL_H}, {len(png)} bytes")


if __name__ == "__main__":
    main()
