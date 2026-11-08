"""Reusable scene parts for Scams on Record episodes (built on engine.py)."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from engine import *  # noqa


def ring(layer, cx, cy, r, a, color=WHITE, width=3):
    if a <= 0.01:
        return
    s = int(r * 2 + width * 2 + 4)
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((2, 2, s - 3, s - 3), outline=color + (255,), width=width)
    paste(layer, img, cx, cy, a)


def chip(layer, bg, cx, cy, label, a=1.0, size=28, color=WHITE, dot=None, fk='bold', track=2, padx=28, h=62, tint=(255, 255, 255), tint_a=22):
    if a <= 0.01:
        return
    tw = F(fk, size).getlength(label) + track * len(label)
    w = int(tw + padx * 2 + (30 if dot else 0))
    glass(layer, bg, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), r=h // 2, a=a, tint=tint, tint_a=tint_a, shadow=False)
    x = cx - w / 2 + padx
    if dot:
        paste(layer, rrect_sprite(16, 16, 8, fill=dot + (255,)), x + 8, cy, a)
        x += 30
    text(layer, x, cy, label, fk, size, color, a, anchor='lm', track=track)


def bezier(p0, p1, p2, k):
    return ((1 - k) ** 2 * p0[0] + 2 * (1 - k) * k * p1[0] + k ** 2 * p2[0],
            (1 - k) ** 2 * p0[1] + 2 * (1 - k) * k * p1[1] + k ** 2 * p2[1])


def dashed_curve(layer, p0, p1, p2, k, color=WHITE, a=1.0, width=5, glow=False):
    if k <= 0 or a <= 0.01:
        return
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    n = 120
    pts = [bezier(p0, p1, p2, i / n * k) for i in range(n + 1)]
    for i in range(n):
        if (i // 3) % 2 == 0:
            d.line((pts[i], pts[i + 1]), fill=color + (255,), width=width)
    if glow:
        layer.alpha_composite(fade(img.filter(ImageFilter.GaussianBlur(8)), a))
    layer.alpha_composite(fade(img, a))


def pin(layer, cx, cy, a=1.0, color=RED, scale=1.0, t=0.0):
    if a <= 0.01:
        return
    s = Image.new('RGBA', (120, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.ellipse((24, 10, 96, 82), fill=color + (255,))
    d.polygon([(30, 62), (90, 62), (60, 128)], fill=color + (255,))
    d.ellipse((46, 32, 74, 60), fill=(14, 16, 24, 255))
    g = s.filter(ImageFilter.GaussianBlur(12))
    for k in range(2):
        ph = ((t * 0.8) + k / 2) % 1
        ring(layer, cx, cy, 20 + 70 * ph, a * (1 - ph) * 0.7, color, 3)
    paste(layer, g, cx, cy - 64 * scale, a * 0.8, scale)
    paste(layer, s, cx, cy - 64 * scale, a, scale)


def typed(txt, k):
    return txt[:int(round(len(txt) * clamp(k)))]


def release_card(L, cx, cy, w, quote, hl_words, hl_k, a, rot=0.0, qsize=40,
                 header="FROM THE U.S. ATTORNEY'S RELEASE", footer='U.S. Attorney’s Office'):
    if a <= 0.01:
        return
    lines = wrap(quote, 'serif', qsize, w - 96)
    lh = int(qsize * 1.45)
    h = 110 + lh * len(lines) + 70
    card = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    card.alpha_composite(rrect_sprite(w, h, 26, fill=PAPER + (255,)))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((48, 40, 58, 72), radius=3, fill=(176, 28, 34))
    d.text((74, 40), header, font=F('bold', 24), fill=(150, 26, 30))
    f = F('serif', qsize)
    sp = f.getlength(' ')
    targets = [x.lower() for x in hl_words]
    yb = 100
    for i, ln in enumerate(lines):
        x = 48
        for wd in ln.split(' '):
            ww = f.getlength(wd)
            clean = wd.strip('“”".,’\'').lower()
            if hl_k > 0 and clean in targets:
                d.rounded_rectangle((x - 6, yb + i * lh - 2, x - 6 + (ww + 12) * hl_k, yb + i * lh + qsize + 10), radius=6, fill=YEL + (255,))
            d.text((x, yb + i * lh), wd, font=f, fill=INK)
            x += ww + sp
    d.text((48, h - 54), footer, font=F('med', 24), fill=(98, 96, 92))
    sh, pad = shadow_sprite(w, h, 26, 30, 0.75, 18)
    paste(L, sh, cx, cy + 24, a, rot=rot)
    paste(L, card, cx, cy, a, rot=rot)


_stamps = {}
def stamp_sprite(word, color=RED, size=150):
    if word not in _stamps:
        tw = F('dblack', size).getlength(word)
        w = int(tw + 140)
        s = Image.new('RGBA', (w, 300), (0, 0, 0, 0))
        d = ImageDraw.Draw(s)
        d.rounded_rectangle((16, 16, w - 16, 284), radius=34, outline=color + (255,), width=14)
        t = text_sprite(word, 'dblack', size, color)
        s.alpha_composite(t, (int(w / 2 - t.width / 2), int(150 - t.height / 2)))
        rng = np.random.default_rng(11)
        a = np.array(s.getchannel('A'), dtype=np.int16)
        holes = rng.random(a.shape) < 0.05
        a[holes] = (a[holes] * 0.3).astype(np.int16)
        s.putalpha(Image.fromarray(a.clip(0, 255).astype(np.uint8), 'L'))
        g = s.filter(ImageFilter.GaussianBlur(20))
        out = Image.new('RGBA', s.size, (0, 0, 0, 0))
        out.alpha_composite(fade(g, 0.8)); out.alpha_composite(s)
        _stamps[word] = out.rotate(7, expand=True, resample=Image.BICUBIC)
    return _stamps[word]


def stamp(L, word, cx, cy, lt, t0, color=RED, scale=0.95):
    """Slam a stamp in at local time t0. Returns True once landed."""
    if lt < t0:
        return False
    k = clamp((lt - t0) / 0.16)
    sc = 2.2 - 1.2 * eo(k)
    paste(L, stamp_sprite(word, color), cx, cy, clamp(k * 1.3), sc * scale)
    if k >= 1:
        kk = p(lt, t0 + 0.16, 0.7)
        rng = np.random.default_rng(21)
        for i in range(24):
            ang = rng.uniform(0, 2 * math.pi); sp = rng.uniform(160, 420)
            r = sp * eo(kk)
            paste(L, rrect_sprite(8, 8, 4, fill=(255, 120, 110, 255)), cx + math.cos(ang) * (300 + r), cy + math.sin(ang) * (120 + r * 0.6), (1 - kk) * 0.9)
    return k >= 1


def stat_row(L, bg, y, val, label, a, col=WHITE, sub=None):
    if a <= 0.01:
        return
    glass(L, bg, (110, y - 56, 970, y + 56), r=28, a=a, tint_a=16)
    text(L, 150, y, val, 'dblack', 64, col, a, anchor='lm')
    if sub:
        text(L, 930, y - 16, label, 'semi', 30, WHITE, a, anchor='rm')
        text(L, 930, y + 20, sub, 'med', 24, MUTED, a, anchor='rm')
    else:
        text(L, 930, y, label, 'semi', 32, MUTED, a, anchor='rm')


def silhouette(d, cx, cy, s=1.0, fill=(120, 124, 134, 255)):
    d.ellipse((cx - 44 * s, cy - 88 * s, cx + 44 * s, cy), fill=fill)
    d.pieslice((cx - 92 * s, cy + 6 * s, cx + 92 * s, cy + 192 * s), 180, 360, fill=fill)


def flag_rows(L, bg, lt, rows, y0=460, step=126):
    y = y0
    for t0, txt in rows:
        k = spring(lt - t0, 2.2, 7)
        if lt >= t0:
            ra = clamp(k * 1.5)
            dx = 60 * (1 - clamp(k))
            glass(L, bg, (100 + dx, y - 52, 980 + dx, y + 52), r=26, a=ra, tint_a=14)
            paste(L, rrect_sprite(64, 64, 32, fill=RED + (255,)), 160 + dx, y, ra)
            kx = eo(p(lt, t0 + 0.1, 0.3))
            xi = Image.new('RGBA', (64, 64), (0, 0, 0, 0)); xd = ImageDraw.Draw(xi)
            xd.line((20, 20, 20 + 24 * kx, 20 + 24 * kx), fill=WHITE, width=7)
            if kx > 0.5:
                k2 = (kx - 0.5) * 2
                xd.line((44, 20, 44 - 24 * k2, 20 + 24 * k2), fill=WHITE, width=7)
            paste(L, xi, 160 + dx, y, ra)
            lines = wrap(txt, 'bold', 38, 700)
            for j, ln in enumerate(lines):
                text(L, 214 + dx, y + (j - (len(lines) - 1) / 2) * 44, ln, 'bold', 38, WHITE, ra, anchor='lm')
        y += step


def warn_title(L, lt, title='RED FLAGS', y=300):
    a = eo(p(lt, 0.0, 0.4))
    tri = Image.new('RGBA', (110, 100), (0, 0, 0, 0))
    td = ImageDraw.Draw(tri)
    td.polygon([(55, 4), (106, 96), (4, 96)], fill=RED + (255,))
    td.rounded_rectangle((50, 34, 60, 70), radius=4, fill=(20, 10, 10, 255))
    td.ellipse((49, 76, 61, 88), fill=(20, 10, 10, 255))
    paste(L, tri, 250, y, a, 0.9)
    text(L, 590, y, title, 'dblack', 96, RED, a, glow=(255, 40, 40, 0.7), glow_r=24)


def action_card(L, bg, lt, t0, line1, line2, y0=862):
    if lt < t0:
        return
    k = spring(lt - t0, 2.0, 7)
    ga = clamp(k * 1.5)
    glass(L, bg, (100, y0, 980, y0 + 168), r=30, a=ga, tint=(48, 209, 88), tint_a=34)
    paste(L, rrect_sprite(84, 84, 42, fill=GREEN + (255,)), 176, y0 + 84, ga, 0.8 + 0.2 * clamp(k))
    ck = Image.new('RGBA', (84, 84), (0, 0, 0, 0)); cdr = ImageDraw.Draw(ck)
    cdr.line((24, 44, 38, 58), fill=WHITE, width=8); cdr.line((38, 58, 62, 28), fill=WHITE, width=8)
    paste(L, ck, 176, y0 + 84, ga)
    text(L, 244, y0 + 52, line1, 'black', 46, WHITE, ga, anchor='lm')
    text(L, 244, y0 + 112, line2, 'semi', 30, WHITE, ga, anchor='lm')


def follow_pill(L, lt, t0, label, y=1110):
    if lt < t0:
        return
    k = spring(lt - t0, 2.2, 7)
    fa = clamp(k * 1.5)
    paste(L, rrect_sprite(540, 84, 42, fill=RED + (255,)), 540, y, fa, 0.85 + 0.15 * clamp(k) + 0.02 * math.sin(lt * 6))
    text(L, 540, y, label, 'black', 34, WHITE, fa, track=1)


def source_line(L, lt, line1, line2, y=1228):
    sa = eo(p(lt, 0.3, 0.5))
    text(L, 540, y, line1, 'med', 26, MUTED, sa)
    text(L, 540, y + 36, line2, 'med', 26, MUTED, sa)


def dot_map(L, bg, box, km, land=None):
    x0, y0, x1, y1 = box
    glass(L, bg, box, r=40, a=km, tint_a=14)
    dots = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    for gy in range(y0 + 40, y1 - 30, 30):
        for gx in range(x0 + 40, x1 - 30, 30):
            on = land(gx, gy) if land else True
            c = (120, 132, 160, 150) if on else (80, 90, 110, 60)
            dd.ellipse((gx - 2.2, gy - 2.2, gx + 2.2, gy + 2.2), fill=c)
    L.alpha_composite(fade(dots, km))
