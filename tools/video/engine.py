"""Shared motion engine for Scams on Record videos (1080x1920, 30 fps).
Animated gradient background, grain, particles, glass cards, glow text, word-synced captions,
story-style progress bar, scene transitions. Episode files supply the scenes."""
import math, re
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30

FONT_FILES = {
    'black': '/usr/share/fonts/opentype/inter/Inter-Black.otf',
    'xbold': '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf',
    'dblack': '/usr/share/fonts/opentype/inter/InterDisplay-Black.otf',
    'dbold': '/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf',
    'bold': '/usr/share/fonts/opentype/inter/Inter-Bold.otf',
    'semi': '/usr/share/fonts/opentype/inter/Inter-SemiBold.otf',
    'med': '/usr/share/fonts/opentype/inter/Inter-Medium.otf',
    'reg': '/usr/share/fonts/opentype/inter/Inter-Regular.otf',
    'serif': '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
    'mono': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',
}

WHITE = (246, 247, 249)
MUTED = (148, 158, 176)
DIM = (92, 102, 120)
RED = (255, 69, 69)
YEL = (255, 214, 10)
GREEN = (48, 209, 88)
PAPER = (243, 240, 233)
INK = (24, 24, 28)


@lru_cache(maxsize=None)
def F(k, s):
    return ImageFont.truetype(FONT_FILES[k], int(round(s)))


# ---------- easing ----------
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x

def eo(x):
    x = clamp(x); return 1 - (1 - x) ** 3

def eio(x):
    x = clamp(x); return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2

def back(x, s=1.9):
    x = clamp(x); return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2

def spring(t, freq=2.6, damp=7.0):
    """0 -> 1 with a little overshoot; t in seconds since start."""
    if t <= 0:
        return 0.0
    return 1 - math.exp(-damp * t) * math.cos(2 * math.pi * freq * t)

def p(t, t0, d=0.3):
    return clamp((t - t0) / d) if d > 0 else (1.0 if t >= t0 else 0.0)


# ---------- sprites ----------
def text_size(text, font):
    b = font.getbbox(text)
    return b[2] - b[0], b[3] - b[1], b

@lru_cache(maxsize=4096)
def text_sprite(text, fk, size, fill, glow=None, glow_r=18, shadow=0, track=0):
    font = F(fk, size)
    pad = max(glow_r * 2 if glow else 0, shadow * 3, 6)
    if track:
        widths = [font.getlength(c) + track for c in text]
        tw = int(sum(widths) - track)
    else:
        tw = int(font.getlength(text))
    asc, desc = font.getmetrics()
    th = asc + desc
    img = Image.new('RGBA', (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    mask = Image.new('L', img.size, 0)
    md = ImageDraw.Draw(mask)
    if track:
        x = pad
        for c, w in zip(text, widths):
            md.text((x, pad), c, font=font, fill=255)
            x += w
    else:
        md.text((pad, pad), text, font=font, fill=255)
    if shadow:
        sh = mask.filter(ImageFilter.GaussianBlur(shadow))
        img.paste((0, 0, 0, 255), (0, 0), sh.point(lambda v: int(v * 0.75)))
    if glow:
        g = mask.filter(ImageFilter.GaussianBlur(glow_r))
        gl = Image.new('RGBA', img.size, glow[:3] + (0,))
        gl.putalpha(g.point(lambda v: min(255, int(v * (glow[3] if len(glow) > 3 else 1.0) * 1.6))))
        img = Image.alpha_composite(img, gl)
    solid = Image.new('RGBA', img.size, fill[:3] + (255,))
    solid.putalpha(mask)
    img = Image.alpha_composite(img, solid)
    return img

@lru_cache(maxsize=512)
def rrect_sprite(w, h, r, fill=None, outline=None, width=2):
    img = Image.new('RGBA', (int(w), int(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, int(w) - 1, int(h) - 1), radius=r, fill=fill, outline=outline, width=width)
    return img

@lru_cache(maxsize=256)
def shadow_sprite(w, h, r, blur=28, strength=0.55, spread=10):
    pad = blur * 3
    img = Image.new('L', (int(w) + 2 * pad, int(h) + 2 * pad), 0)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((pad - spread // 2, pad + spread, pad + int(w) + spread // 2, pad + int(h) + spread * 2), radius=r, fill=int(255 * strength))
    img = img.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    out.putalpha(img)
    return out, pad

def fade(sprite, a):
    if a >= 0.999:
        return sprite
    s = sprite.copy()
    s.putalpha(s.getchannel('A').point(lambda v: int(v * a)))
    return s

def paste(layer, sprite, x, y, a=1.0, scale=1.0, anchor='mm', rot=0.0):
    """Composite sprite onto layer with alpha, scale and rotation. (x, y) is the anchor point."""
    if a <= 0.004 or sprite is None:
        return
    s = sprite
    if abs(scale - 1) > 0.002:
        nw, nh = max(1, int(s.width * scale)), max(1, int(s.height * scale))
        s = s.resize((nw, nh), Image.BICUBIC)
    if abs(rot) > 0.05:
        s = s.rotate(rot, expand=True, resample=Image.BICUBIC)
    s = fade(s, a)
    if anchor == 'mm':
        px, py = x - s.width / 2, y - s.height / 2
    elif anchor == 'lm':
        px, py = x, y - s.height / 2
    elif anchor == 'rm':
        px, py = x - s.width, y - s.height / 2
    elif anchor == 'lt':
        px, py = x, y
    else:
        px, py = x - s.width / 2, y
    layer.alpha_composite(s, (int(round(px)), int(round(py))))

def text(layer, x, y, txt, fk, size, fill=WHITE, a=1.0, anchor='mm', glow=None, glow_r=18, shadow=0, track=0, scale=1.0, rot=0.0):
    spr = text_sprite(txt, fk, size, fill, glow, glow_r, shadow, track)
    pad = max(glow_r * 2 if glow else 0, shadow * 3, 6)
    if anchor == 'lm':
        paste(layer, spr, x - pad * scale, y, a, scale, 'lm', rot)
    elif anchor == 'rm':
        paste(layer, spr, x + pad * scale, y, a, scale, 'rm', rot)
    else:
        paste(layer, spr, x, y, a, scale, 'mm', rot)

def wrap(txt, fk, size, maxw):
    font = F(fk, size)
    words, lines, cur = txt.split(), [], ''
    for w in words:
        c = (cur + ' ' + w).strip()
        if font.getlength(c) <= maxw or not cur:
            cur = c
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


# ---------- background ----------
class Background:
    def __init__(self, seed=3):
        hw, hh = W // 2, H // 2
        y = np.linspace(0, 1, hh)[:, None, None]
        top = np.array([8, 10, 16], float); bot = np.array([12, 16, 30], float)
        base = top * (1 - y) + bot * y
        self.base_half = Image.fromarray(np.broadcast_to(base, (hh, hw, 3)).astype(np.uint8), 'RGB').convert('RGBA')
        self.blobs = [self._blob(640, (215, 38, 48), 0.55), self._blob(700, (52, 70, 210), 0.42), self._blob(420, (230, 140, 30), 0.18)]
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for gy in range(30, H, 46):
            for gx in range(30, W, 46):
                d.ellipse((gx - 1.6, gy - 1.6, gx + 1.6, gy + 1.6), fill=(170, 185, 215, 26))
        yy = np.linspace(-1, 1, H)[:, None]; xx = np.linspace(-1, 1, W)[None, :]
        r = np.sqrt((xx * 0.85) ** 2 + (yy * 0.7) ** 2)
        vig = (np.clip(r - 0.55, 0, 1) ** 1.6 * 200).astype(np.uint8)
        v = Image.new('RGBA', (W, H), (0, 0, 0, 0)); v.putalpha(Image.fromarray(vig, 'L'))
        self.overlay = Image.alpha_composite(ov, v)
        rng = np.random.default_rng(seed)
        self.grain = []
        for _ in range(4):
            n = rng.integers(0, 255, (H // 2, W // 2), dtype=np.uint8)
            g = Image.fromarray(n, 'L').resize((W, H), Image.NEAREST).convert('RGBA')
            g.putalpha(11)
            self.grain.append(g)
        self.parts = [(rng.uniform(40, W - 40), rng.uniform(0, H), rng.uniform(8, 26), rng.uniform(1.2, 3.2), rng.uniform(0, 6.28)) for _ in range(38)]

    @staticmethod
    def _blob(size, color, strength):
        s = size // 2
        yy, xx = np.mgrid[-1:1:complex(0, s), -1:1:complex(0, s)]
        r = np.sqrt(xx ** 2 + yy ** 2)
        a = (np.clip(1 - r, 0, 1) ** 2.2 * 255 * strength).astype(np.uint8)
        img = Image.new('RGBA', (s, s), color + (0,))
        img.putalpha(Image.fromarray(a, 'L'))
        return img

    def frame(self, t, fi):
        half = self.base_half.copy()
        pos = [(130 + 90 * math.sin(0.21 * t), 170 + 80 * math.cos(0.17 * t)),
               (420 + 70 * math.cos(0.15 * t), 700 + 90 * math.sin(0.19 * t)),
               (300 + 120 * math.sin(0.11 * t + 1), 470 + 100 * math.cos(0.13 * t))]
        for b, (x, y) in zip(self.blobs, pos):
            half.alpha_composite(b, (int(x - b.width / 2), int(y - b.height / 2)))
        img = half.resize((W, H), Image.BILINEAR)
        img.alpha_composite(self.overlay)
        d = ImageDraw.Draw(img)
        for (x0, y0, sp, r, ph) in self.parts:
            y = (y0 - sp * t) % H
            x = x0 + 14 * math.sin(t * 0.5 + ph)
            tw = 0.5 + 0.5 * math.sin(t * 1.3 + ph)
            c = int(70 + 70 * tw)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(c, c, int(c * 1.1), 255))
        img.alpha_composite(self.grain[(fi // 2) % 4])
        return img


def glass(layer, bg, box, r=34, a=1.0, tint=(255, 255, 255), tint_a=18, border_a=46, blur=26, shadow=True):
    """Frosted glass card: blurred backdrop, tint, top highlight, hairline border, soft shadow."""
    if a <= 0.004:
        return
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    if shadow:
        sh, pad = shadow_sprite(w, h, r)
        paste(layer, sh, x0 - pad, y0 - pad, a * 0.9, anchor='lt')
    crop = bg.crop((max(0, x0), max(0, y0), min(W, x1), min(H, y1))).filter(ImageFilter.GaussianBlur(blur))
    card = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    card.paste(crop, (max(0, x0) - x0, max(0, y0) - y0))
    tint_l = Image.new('RGBA', (w, h), tint + (tint_a,))
    card = Image.alpha_composite(card, tint_l)
    hl = np.linspace(26, 0, max(1, h // 2)).astype(np.uint8)
    hl_img = Image.new('RGBA', (w, max(1, h // 2)), (255, 255, 255, 0))
    hl_img.putalpha(Image.fromarray(np.repeat(hl[:, None], w, axis=1), 'L'))
    card.alpha_composite(hl_img, (0, 0))
    mask = rrect_sprite(w, h, r, fill=(255, 255, 255, 255)).getchannel('A')
    card.putalpha(mask)
    card.alpha_composite(rrect_sprite(w, h, r, outline=(255, 255, 255, border_a), width=2))
    paste(layer, card, x0, y0, a, anchor='lt')


def light_sweep(layer, k):
    """Diagonal light band crossing the frame, k in 0..1."""
    if k <= 0 or k >= 1:
        return
    band = _band()
    x = -900 + k * (W + 1800)
    paste(layer, band, x, H / 2, 0.55 * math.sin(math.pi * k), anchor='mm')

@lru_cache(maxsize=1)
def _band():
    w, h = 520, 2600
    xs = np.linspace(-1, 1, w)
    a = (np.exp(-(xs * 2.4) ** 2) * 60).astype(np.uint8)
    img = Image.new('RGBA', (w, h), (255, 236, 230, 0))
    img.putalpha(Image.fromarray(np.repeat(a[None, :], h, axis=0), 'L'))
    return img.rotate(-18, expand=True, resample=Image.BICUBIC)


def composite_layer(frame, layer, scale=1.0, a=1.0, blur=0.0, dx=0, dy=0):
    L = layer
    if blur > 0.4:
        L = L.filter(ImageFilter.GaussianBlur(blur))
    if abs(scale - 1) > 0.001:
        nw, nh = int(W * scale), int(H * scale)
        R = L.resize((nw, nh), Image.BILINEAR)
        if scale > 1:
            ox, oy = (nw - W) // 2, (nh - H) // 2
            L = R.crop((ox, oy, ox + W, oy + H))
        else:
            L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            L.alpha_composite(R, ((W - nw) // 2, (H - nh) // 2))
    if a < 0.999:
        L = fade(L, a)
    frame.alpha_composite(L, (int(dx), int(dy)))


# ---------- captions ----------
def _norm(w):
    return re.sub(r"[^a-z0-9']", '', w.lower())

def build_groups(chunks_per_beat, words_per_beat):
    """chunks: [{display, spoken}], words: [[word, t0, t1], ...] per beat -> caption groups with per-display-word times."""
    groups = []
    for chunks, words in zip(chunks_per_beat, words_per_beat):
        i = 0
        for c in chunks:
            n = len(re.findall(r"[A-Za-z']+", c['spoken'].replace('-', ' ')))
            sw = words[i:i + n]; i += n
            disp = c['display'].split(' ')
            out, k = [], 0
            for j, d in enumerate(disp):
                if k < len(sw) and _norm(d) == sw[k][0].lower():
                    out.append((d, sw[k][1], sw[k][2])); k += 1
                else:
                    nxt = _norm(disp[j + 1]) if j + 1 < len(disp) else None
                    e = k
                    while e < len(sw) and (nxt is None or sw[e][0].lower() != nxt):
                        e += 1
                    e = max(e, k + 1)
                    out.append((d, sw[min(k, len(sw) - 1)][1], sw[min(e, len(sw)) - 1][2])); k = e
            groups.append({'start': out[0][1], 'end': out[-1][2], 'words': out})
    for a, b in zip(groups, groups[1:]):
        a['hold'] = min(b['start'], a['end'] + 0.6)
    groups[-1]['hold'] = groups[-1]['end'] + 1.2
    return groups

@lru_cache(maxsize=2048)
def _caption_sprite(words, active, size=70, maxw=820):
    font = F('black', size)
    space = font.getlength(' ')
    lines, cur, cw = [], [], 0
    for i, w in enumerate(words):
        ww = font.getlength(w)
        if cur and cw + space + ww > maxw:
            lines.append(cur); cur, cw = [], 0
        cur.append((i, w, ww)); cw += (space if len(cur) > 1 else 0) + ww
    if cur:
        lines.append(cur)
    lh = int(size * 1.12)
    Wc, Hc = maxw + 120, lh * len(lines) + 120
    mask_all = Image.new('L', (Wc, Hc), 0)
    md = ImageDraw.Draw(mask_all)
    pos = []
    for li, ln in enumerate(lines):
        tw = sum(w for _, _, w in ln) + space * (len(ln) - 1)
        x = (Wc - tw) / 2
        y = 60 + li * lh
        for i, w, ww in ln:
            md.text((x, y), w, font=font, fill=255)
            pos.append((i, w, x, y))
            x += ww + space
    img = Image.new('RGBA', (Wc, Hc), (0, 0, 0, 0))
    sh = mask_all.filter(ImageFilter.GaussianBlur(9))
    img.paste((0, 0, 0, 255), (0, 0), sh.point(lambda v: int(v * 0.85)))
    d = ImageDraw.Draw(img)
    for i, w, x, y in pos:
        if i == active:
            g = Image.new('L', (Wc, Hc), 0)
            ImageDraw.Draw(g).text((x, y), w, font=font, fill=255)
            g = g.filter(ImageFilter.GaussianBlur(14))
            gl = Image.new('RGBA', (Wc, Hc), (255, 190, 0, 0)); gl.putalpha(g.point(lambda v: int(v * 0.9)))
            img = Image.alpha_composite(img, gl); d = ImageDraw.Draw(img)
            d.text((x, y), w, font=font, fill=YEL)
        elif active is not None and i < active:
            d.text((x, y), w, font=font, fill=WHITE)
        else:
            d.text((x, y), w, font=font, fill=(205, 210, 220) if active is None else (170, 176, 190))
    return img

def draw_captions(frame, groups, t, y=1440):
    for gi, g in enumerate(groups):
        if g['start'] - 0.08 <= t < g['hold']:
            words = tuple(w for w, _, _ in g['words'])
            active = None
            for i, (_, t0, t1) in enumerate(g['words']):
                if t >= t0 - 0.04:
                    active = i
            if t > g['end'] + 0.15:
                active = len(words)
            spr = _caption_sprite(words, active)
            k = eo((t - g['start'] + 0.08) / 0.16)
            paste(frame, spr, W / 2, y + 26 * (1 - k), k, anchor='mm')
            return


# ---------- header ----------
def draw_header(frame, t, beats, label, sub, a=1.0):
    n = len(beats)
    x0, x1, gap = 60, 1020, 8
    sw = (x1 - x0 - gap * (n - 1)) / n
    d = ImageDraw.Draw(frame)
    for i, b in enumerate(beats):
        sx = x0 + i * (sw + gap)
        d.rounded_rectangle((sx, 78, sx + sw, 84), radius=3, fill=(255, 255, 255, 60) if False else (64, 70, 84))
        k = clamp((t - b['start']) / (b['end'] - b['start']))
        if k > 0:
            d.rounded_rectangle((sx, 78, sx + max(6, sw * k), 84), radius=3, fill=WHITE)
    pill = rrect_sprite(250, 64, 32, fill=(18, 20, 28, 210), outline=(255, 255, 255, 40), width=2)
    paste(frame, pill, 60, 110, a, anchor='lt')
    pulse = 0.55 + 0.45 * math.sin(t * 5)
    dot = rrect_sprite(18, 18, 9, fill=RED + (255,))
    paste(frame, dot, 92, 142, a * (0.5 + 0.5 * pulse))
    text(frame, 114, 142, label, 'black', 32, WHITE, a, anchor='lm')
    text(frame, 330, 142, sub, 'semi', 30, MUTED, a, anchor='lm')
