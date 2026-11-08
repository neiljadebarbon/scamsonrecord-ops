"""Caught #1 video. Usage:
  python3 render.py stills <outdir>        sample frames per beat
  python3 render.py video <out_noaudio.mp4>
Reads ../script/captions.json and ../audio/caught_001_words.json (word timings from tools/voice/align.py)."""
import json, math, os, subprocess, sys
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
EP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EP, '..', '..', 'tools', 'video'))
from engine import *  # noqa

CAPS = json.load(open(os.path.join(EP, 'script', 'captions.json')))
WORDS = json.load(open(os.path.join(EP, 'audio', 'caught_001_words.json')))
AUDIO_END = WORDS[-1]['words'][-1][2]

BEATS = []
for i, para in enumerate(WORDS):
    st = 0.0 if i == 0 else para['words'][0][1] - 0.3
    BEATS.append({'id': CAPS[i]['id'], 'start': st, 'w': para['words']})
for a, b in zip(BEATS, BEATS[1:]):
    a['end'] = b['start']
BEATS[-1]['end'] = AUDIO_END + 1.4
TOTAL = BEATS[-1]['end']
GROUPS = build_groups([c['chunks'] for c in CAPS], [para['words'] for para in WORDS])


def T(b, word, n=0):
    """Time of the nth occurrence of word in beat b, relative to the beat start."""
    k = 0
    for w, t0, t1 in b['w']:
        if w.lower() == word.lower():
            if k == n:
                return t0 - b['start']
            k += 1
    raise KeyError(word)

def TE(b, word, n=0):
    k = 0
    for w, t0, t1 in b['w']:
        if w.lower() == word.lower():
            if k == n:
                return t1 - b['start']
            k += 1
    raise KeyError(word)

def B(i):
    return BEATS[i]


# ---------- shake events (absolute times) ----------
SHAKES = []

def shake(t):
    dx = dy = 0.0
    for t0, amp, dur in SHAKES:
        if t0 <= t < t0 + dur:
            k = 1 - (t - t0) / dur
            dx += amp * k * math.sin((t - t0) * 90)
            dy += amp * k * math.cos((t - t0) * 77)
    return dx, dy


# ---------- small drawing helpers ----------
def ring(layer, cx, cy, r, a, color=WHITE, width=3):
    if a <= 0.01:
        return
    s = int(r * 2 + width * 2 + 4)
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((2, 2, s - 3, s - 3), outline=color + (255,), width=width)
    paste(layer, img, cx, cy, a)

def chip(layer, bg, cx, cy, label, a=1.0, size=28, color=WHITE, dot=None, fk='bold', track=2, padx=28, h=62):
    if a <= 0.01:
        return
    tw = F(fk, size).getlength(label) + track * len(label)
    w = int(tw + padx * 2 + (30 if dot else 0))
    glass(layer, bg, (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), r=h // 2, a=a, tint_a=22, shadow=False)
    x = cx - w / 2 + padx
    if dot:
        paste(layer, rrect_sprite(16, 16, 8, fill=dot + (255,)), x + 8, cy, a)
        x += 30
    text(layer, x, cy, label, fk, size, color, a, anchor='lm', track=track)

def bezier(p0, p1, p2, k):
    return ((1 - k) ** 2 * p0[0] + 2 * (1 - k) * k * p1[0] + k ** 2 * p2[0],
            (1 - k) ** 2 * p0[1] + 2 * (1 - k) * k * p1[1] + k ** 2 * p2[1])

def dashed_curve(layer, p0, p1, p2, k, color=WHITE, a=1.0, width=5, dash=0.035, glow=False):
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
        g = img.filter(ImageFilter.GaussianBlur(8))
        layer.alpha_composite(fade(g, a))
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


# ---------- scene 0: hook ----------
DIGITS = '$867,149'
def odometer(layer, cx, cy, k_start, lt, size=176):
    font = F('dblack', size)
    dw = max(font.getlength(str(i)) for i in range(10))
    widths = [dw if c.isdigit() else font.getlength(c) for c in DIGITS]
    total_w = sum(widths)
    asc, desc = font.getmetrics()
    sh = int(asc * 0.95)
    x = cx - total_w / 2
    di = 0
    for c, w in zip(DIGITS, widths):
        if not c.isdigit():
            col = RED if c == '$' else WHITE
            text(layer, x + w / 2, cy, c, 'dblack', size, col, eo(p(lt, k_start - 0.1, 0.25)))
        else:
            target = int(c)
            spins = 2 + (di % 3)
            dur = 1.0 + 0.05 * di
            k = eo(p(lt, k_start + 0.04 * di, dur))
            v = k * (target + 10 * spins)
            cur = int(math.floor(v)) % 10
            nxt = (cur + 1) % 10
            frac = v - math.floor(v)
            slot = Image.new('RGBA', (int(w) + 12, sh + 40), (0, 0, 0, 0))
            for dig, off in ((cur, -frac), (nxt, 1 - frac)):
                spr = text_sprite(str(dig), 'dblack', size, WHITE)
                yy = (slot.height - spr.height) / 2 + off * slot.height * 0.9
                slot.alpha_composite(spr, (int((slot.width - spr.width) / 2), int(yy)))
            if 0 < k < 1:
                slot = slot.filter(ImageFilter.GaussianBlur(min(5, 9 * (1 - k))))
            grad = np.concatenate([np.linspace(0, 255, 18), np.full(slot.height - 36, 255), np.linspace(255, 0, 18)]).astype(np.uint8)
            m = Image.fromarray(np.repeat(grad[:, None], slot.width, axis=1), 'L')
            a_ch = Image.fromarray((np.array(slot.getchannel('A'), dtype=np.uint16) * np.array(m) // 255).astype(np.uint8), 'L')
            slot.putalpha(a_ch)
            paste(layer, slot, x + w / 2, cy + 6, eo(p(lt, k_start - 0.1, 0.25)))
            di += 1
        x += w

def gavel_sprite(scale=1.0):
    s = Image.new('RGBA', (220, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.rounded_rectangle((40, 50, 170, 100), radius=14, fill=(236, 238, 242, 255))
    d.rounded_rectangle((52, 44, 70, 106), radius=6, fill=(200, 204, 212, 255))
    d.rounded_rectangle((140, 44, 158, 106), radius=6, fill=(200, 204, 212, 255))
    d.rounded_rectangle((98, 96, 112, 200), radius=7, fill=(236, 238, 242, 255))
    return s

def scene_hook(L, bg, t, lt, b):
    t_ord = T(b, 'ordered'); t_eight = T(b, 'eight'); t_dol = TE(b, 'dollars'); t_sen = T(b, 'seniors')
    k = spring(lt - 0.05)
    glass(L, bg, (448, 378, 632, 562), r=92, a=clamp(k), tint_a=20)
    ang = -38 * (1 - eio(p(lt, t_ord - 0.35, 0.33))) + 10 * (1 - eo(p(lt, t_ord - 0.02, 0.25))) * (lt >= t_ord - 0.02)
    paste(L, gavel_sprite(), 540, 470, clamp(k), 0.78 * (0.6 + 0.4 * clamp(k)), rot=ang)
    if lt >= t_ord - 0.02:
        kk = p(lt, t_ord - 0.02, 0.6)
        ring(L, 540, 470, 95 + 120 * eo(kk), (1 - kk) * 0.8, WHITE, 3)
    chip(L, bg, 540, 640, 'RESTITUTION ORDERED', eo(p(lt, T(b, 'pay') - 0.25, 0.35)), 26, WHITE, dot=RED)
    land = t_eight - 0.1 + 0.04 * 5 + 1.0 + 0.05 * 5
    if lt >= land:
        kk = p(lt, land, 0.9)
        glow = text_sprite(DIGITS, 'dblack', 176, RED, (255, 40, 40, 0.9), 42)
        paste(L, glow, 540, 798, 0.55 * eo(kk) * (0.75 + 0.25 * math.sin(lt * 3)))
        ring(L, 540, 800, 200 + 420 * eo(kk), (1 - kk) * 0.5, RED, 4)
    sc = 1 + 0.06 * max(0, 1 - spring(lt - land, 3.2, 6)) if lt >= land else 1
    sub = Image.new('RGBA', (W, 260), (0, 0, 0, 0))
    odometer(sub, W / 2, 130, t_eight - 0.1, lt)
    paste(L, sub, 540, 800, 1.0, sc)
    a = eo(p(lt, t_sen - 0.25, 0.4))
    text(L, 540, 960 + 18 * (1 - a), 'to seniors who got scammed', 'semi', 46, WHITE, a)
    text(L, 540, 1030 + 18 * (1 - a), 'one man · one federal case', 'med', 34, MUTED, eo(p(lt, t_sen + 0.4, 0.4)))


# ---------- phone (scenes 1 and 2) ----------
PW, PH = 500, 1010
def phone_sprite(t, mode, lt, b, caller='Unknown'):
    s = Image.new('RGBA', (PW, PH), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.rounded_rectangle((0, 0, PW - 1, PH - 1), radius=78, fill=(30, 33, 42, 255), outline=(92, 98, 115, 255), width=3)
    scr = Image.new('RGBA', (PW - 28, PH - 28), (0, 0, 0, 0))
    yy = np.linspace(0, 1, scr.height)[:, None, None]
    grad = np.array([42, 22, 48], float) * (1 - yy) + np.array([12, 16, 34], float) * yy
    gimg = Image.fromarray(np.broadcast_to(grad, (scr.height, scr.width, 3)).astype(np.uint8), 'RGB').convert('RGBA')
    sm = rrect_sprite(scr.width, scr.height, 64, fill=(255, 255, 255, 255)).getchannel('A')
    gimg.putalpha(sm)
    scr.alpha_composite(gimg)
    sd = ImageDraw.Draw(scr)
    cx = scr.width // 2
    sd.rounded_rectangle((cx - 64, 18, cx + 64, 52), radius=17, fill=(6, 6, 10, 255))
    sd.text((40, 26), '9:41', font=F('semi', 26), fill=WHITE)
    rp = rrect_sprite(200, 40, 20, outline=RED + (255,), width=2)
    scr.alpha_composite(rp, (cx - 100, 74))
    tsp = text_sprite('REENACTMENT', 'bold', 20, RED, track=2)
    scr.alpha_composite(tsp, (int(cx - tsp.width / 2), int(94 - tsp.height / 2)))
    if mode == 'ring':
        tsp = text_sprite('incoming call', 'med', 28, MUTED)
        scr.alpha_composite(tsp, (int(cx - tsp.width / 2), 150))
        tsp = text_sprite(caller, 'semi', 54, WHITE)
        scr.alpha_composite(tsp, (int(cx - tsp.width / 2), 196))
        ay = 470
        for kk in range(3):
            ph = ((lt * 0.75) + kk / 3) % 1
            r = 96 + 110 * ph
            rr = Image.new('RGBA', scr.size, (0, 0, 0, 0))
            ImageDraw.Draw(rr).ellipse((cx - r, ay - r, cx + r, ay + r), outline=(255, 255, 255, int(110 * (1 - ph))), width=2)
            scr.alpha_composite(rr)
        sd = ImageDraw.Draw(scr)
        sd.ellipse((cx - 92, ay - 92, cx + 92, ay + 92), fill=(70, 74, 92, 255))
        q = text_sprite('?', 'dblack', 110, WHITE)
        scr.alpha_composite(q, (int(cx - q.width / 2), int(ay - q.height / 2 - 4)))
        for i in range(13):
            hgt = 10 + 34 * abs(math.sin(lt * 7 + i * 0.7)) * (0.4 + 0.6 * abs(math.sin(i * 1.3)))
            x = cx - 156 + i * 26
            sd.rounded_rectangle((x, 660 - hgt / 2, x + 12, 660 + hgt / 2), radius=6, fill=(255, 255, 255, 160))
        for bx, col, lab in ((cx - 120, (255, 59, 48), 'Decline'), (cx + 120, GREEN, 'Accept')):
            pul = 1 + (0.06 * math.sin(lt * 6) if lab == 'Accept' else 0)
            r = 52 * pul
            if lab == 'Accept':
                gl = Image.new('RGBA', scr.size, (0, 0, 0, 0))
                ImageDraw.Draw(gl).ellipse((bx - r - 14, 830 - r - 14, bx + r + 14, 830 + r + 14), fill=GREEN + (120,))
                scr.alpha_composite(gl.filter(ImageFilter.GaussianBlur(14)))
                sd = ImageDraw.Draw(scr)
            sd.ellipse((bx - r, 830 - r, bx + r, 830 + r), fill=col + (255,))
            tsp = text_sprite(lab, 'med', 24, MUTED)
            scr.alpha_composite(tsp, (int(bx - tsp.width / 2), 896))
        sd.line((cx - 136, 814, cx - 104, 846), fill=WHITE, width=6)
        sd.line((cx - 104, 814, cx - 136, 846), fill=WHITE, width=6)
        sd.line((cx + 104, 832, cx + 116, 846), fill=WHITE, width=6)
        sd.line((cx + 116, 846, cx + 138, 816), fill=WHITE, width=6)
    else:
        tsp = text_sprite('Grandchild?', 'semi', 36, WHITE)
        scr.alpha_composite(tsp, (int(cx - tsp.width / 2), 140))
        secs = 14 + int(lt)
        tsp = text_sprite('00:%02d' % secs, 'med', 26, GREEN)
        scr.alpha_composite(tsp, (int(cx - tsp.width / 2), 190))
        msgs = [(T(b, 'arrested') - 0.7, 'Grandma, I got arrested after a car accident.'),
                (T(b, 'needs') - 0.5, 'I need money for bail.')]
        y = 270
        for t0, msg in msgs:
            if lt < t0 - 0.55:
                break
            if lt < t0:
                bub = rrect_sprite(110, 64, 32, fill=(58, 62, 78, 255))
                scr.alpha_composite(bub, (34, y))
                sd = ImageDraw.Draw(scr)
                for i in range(3):
                    jy = 4 * math.sin(lt * 12 - i * 0.9)
                    sd.ellipse((58 + i * 24, y + 26 + jy, 70 + i * 24, y + 38 + jy), fill=(200, 205, 215, 255))
                break
            lines = wrap(msg, 'med', 34, 300)
            bw = int(max(F('med', 34).getlength(l) for l in lines) + 48)
            bh = len(lines) * 44 + 34
            bub = rrect_sprite(bw, bh, 30, fill=(58, 62, 78, 255))
            k = spring(lt - t0, 3, 8)
            bb = bub.copy()
            bd = ImageDraw.Draw(bb)
            for i, l in enumerate(lines):
                bd.text((24, 16 + i * 44), l, font=F('med', 34), fill=WHITE)
            sc = 0.85 + 0.15 * k
            bb2 = bb.resize((max(1, int(bw * sc)), max(1, int(bh * sc))), Image.BICUBIC)
            scr.alpha_composite(fade(bb2, clamp(k * 1.5)), (34, y))
            y += bh + 18
    s.alpha_composite(scr, (14, 14))
    hl = Image.new('RGBA', (PW, PH), (0, 0, 0, 0))
    ImageDraw.Draw(hl).polygon([(PW * 0.55, 0), (PW * 0.85, 0), (PW * 0.25, PH), (0, PH)], fill=(255, 255, 255, 10))
    s.alpha_composite(hl)
    return s

def draw_phone(L, t, lt, b, mode, caller, x, y, scale, rot, a=1.0):
    sh, pad = shadow_sprite(PW, PH, 78, 40, 0.7, 26)
    paste(L, sh, x, y + 30 * scale, a * 0.9, scale, rot=rot)
    paste(L, phone_sprite(t, mode, lt, b, caller), x, y, a, scale, rot=rot)

def scene_setup(L, bg, t, lt, b):
    k = spring(lt, 1.6, 6.5)
    y = 790 + 520 * (1 - k) + 6 * math.sin(t * 1.6)
    rot = -7 * (1 - k)
    caller = 'Unknown'
    if lt >= T(b, 'grandchild') - 0.1:
        caller = 'Grandchild?'
    if lt >= T(b, 'lawyer') - 0.1:
        caller = 'Lawyer?'
    draw_phone(L, t, lt, b, 'ring', caller, 540, y, 1.0, rot, clamp(k * 1.4))

def release_card(L, bg, cx, cy, w, quote, hl_words, hl_k, a, rot=0.0, qsize=40):
    if a <= 0.01:
        return
    lines = wrap(quote, 'serif', qsize, w - 96)
    lh = int(qsize * 1.45)
    h = 110 + lh * len(lines) + 70
    card = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    card.alpha_composite(rrect_sprite(w, h, 26, fill=PAPER + (255,)))
    rng = np.random.default_rng(5)
    noise = rng.integers(0, 18, (h, w), dtype=np.uint8)
    nimg = Image.new('RGBA', (w, h), (120, 100, 70, 0)); nimg.putalpha(Image.fromarray(noise, 'L'))
    nm = rrect_sprite(w, h, 26, fill=(255, 255, 255, 255)).getchannel('A')
    nimg.putalpha(Image.fromarray((np.array(nimg.getchannel('A'), dtype=np.uint16) * np.array(nm) // 255).astype(np.uint8), 'L'))
    card.alpha_composite(nimg)
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((48, 40, 58, 72), radius=3, fill=(176, 28, 34))
    d.text((74, 40), "FROM THE U.S. ATTORNEY'S RELEASE", font=F('bold', 24), fill=(150, 26, 30))
    f = F('serif', qsize)
    sp = f.getlength(' ')
    targets = [x.lower() for x in hl_words]
    yb = 100
    for i, ln in enumerate(lines):
        x = 48
        for wd in ln.split(' '):
            ww = f.getlength(wd)
            clean = wd.strip('“”".,’').lower()
            if hl_k > 0 and clean in targets:
                d.rounded_rectangle((x - 6, yb + i * lh - 2, x - 6 + (ww + 12) * hl_k, yb + i * lh + qsize + 10), radius=6, fill=YEL + (255,))
            d.text((x, yb + i * lh), wd, font=f, fill=INK)
            x += ww + sp
    d.text((48, h - 54), 'U.S. Attorney’s Office, District of Rhode Island', font=F('med', 24), fill=(98, 96, 92))
    sh, pad = shadow_sprite(w, h, 26, 30, 0.75, 18)
    paste(L, sh, cx, cy + 24, a, rot=rot)
    paste(L, card, cx, cy, a, rot=rot)

def scene_trust(L, bg, t, lt, b):
    t_told = T(b, 'told')
    k = eio(p(lt, t_told - 0.3, 0.6))
    x = 540 - 150 * k
    sc = 1.0 - 0.18 * k
    y = 790 - 120 * k + 6 * math.sin(t * 1.6)
    draw_phone(L, t, lt, b, 'call', '', x, y, sc, -4 * k, 1.0 - 0.45 * k)
    kc = spring(lt - t_told + 0.1, 1.8, 6.5)
    if lt >= t_told - 0.1:
        release_card(L, bg, 560 + 500 * (1 - kc), 1030, 900,
                     'members of the conspiracy falsely told victims that a “gag order” was in place in their relative’s legal matter',
                     ['gag', 'order'], eo(p(lt, T(b, 'gag') - 0.05, 0.5)), clamp(kc * 1.5), rot=-2.2 * (1 - 0.3 * kc))


# ---------- scene 3: cash shipped ----------
def box_sprite(close, tape):
    s = Image.new('RGBA', (460, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    bx0, bx1, top, bot = 50, 410, 170, 400
    d.polygon([(bx0, top), (bx1, top), (bx1 - 34, top - 56), (bx0 + 34, top - 56)], fill=(122, 84, 46, 255))
    fl = 1 - close
    if fl > 0.02:
        d.polygon([(bx0, top), (bx0 - 70 * fl, top - 90 * fl), (230 - 40 * fl, top - 110 * fl), (230, top)], fill=(196, 140, 84, 255))
        d.polygon([(bx1, top), (bx1 + 70 * fl, top - 90 * fl), (230 + 40 * fl, top - 110 * fl), (230, top)], fill=(186, 130, 76, 255))
    return s

def box_front(close, tape):
    s = Image.new('RGBA', (460, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    bx0, bx1, top, bot = 50, 410, 170, 400
    for i in range(bot - top):
        c = int(176 - 30 * i / (bot - top))
        d.line((bx0, top + i, bx1, top + i), fill=(c, int(c * 0.7), int(c * 0.42), 255))
    if close > 0.98:
        d.polygon([(bx0, top), (bx1, top), (bx1 - 34, top - 56), (bx0 + 34, top - 56)], fill=(206, 150, 92, 255))
        if tape > 0:
            d.polygon([(210, top - 56), (250, top - 56), (250, top - 56 + (56 + 230) * tape), (210, top - 56 + (56 + 230) * tape)], fill=(226, 196, 140, 255))
    t = text_sprite('CASH', 'black', 44, (92, 60, 30))
    s.alpha_composite(t, (int(230 - t.width / 2), 300))
    return s

def bill_sprite():
    s = Image.new('RGBA', (190, 92), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.rounded_rectangle((0, 0, 189, 91), radius=10, fill=(78, 160, 106, 255), outline=(40, 110, 68, 255), width=4)
    d.ellipse((70, 21, 120, 71), outline=(200, 240, 210, 255), width=4)
    t = text_sprite('$', 'black', 40, (225, 250, 230))
    s.alpha_composite(t, (int(95 - t.width / 2), int(46 - t.height / 2)))
    return s

BILL = None
def scene_ask(L, bg, t, lt, b):
    global BILL
    if BILL is None:
        BILL = bill_sprite()
    t_th = T(b, 'thousands'); t_ship = T(b, 'ship'); t_addr = T(b, 'address')
    kc = spring(lt - 0.15, 1.8, 6.5)
    release_card(L, bg, 540 + 300 * (1 - kc), 360, 900, 'had been shipped by the victims to designated addresses',
                 ['shipped', 'designated', 'addresses'], eo(p(lt, t_ship - 0.1, 0.8)), clamp(kc * 1.5), rot=1.5, qsize=38)
    close = eo(p(lt, t_ship - 0.45, 0.3))
    tape = eo(p(lt, t_ship - 0.15, 0.25))
    mv = eio(p(lt, t_ship + 0.05, 0.9))
    p0, p1, p2 = (540, 830), (300, 1000), (360, 1150)
    bxy = bezier(p0, p1, p2, mv)
    bsc = 1 - 0.5 * mv
    kb = spring(lt, 2.0, 7)
    paste(L, box_sprite(close, tape), bxy[0], bxy[1], clamp(kb * 1.5), bsc * (0.8 + 0.2 * clamp(kb)))
    for i in range(6):
        t0 = t_th - 0.2 + i * 0.16
        k = p(lt, t0, 0.5)
        if 0 < k < 1:
            sx = -120 if i % 2 == 0 else W + 120
            sy = 520 + 40 * i
            ex, ey = 540 + (i - 2.5) * 30, 800
            cxp = (sx + ex) / 2
            pt = bezier((sx, sy), (cxp, sy - 260), (ex, ey), eo(k))
            paste(L, BILL, pt[0], pt[1], 1.0, 0.9, rot=(1 - k) * (200 if i % 2 else -200))
    paste(L, box_front(close, tape), bxy[0], bxy[1], clamp(kb * 1.5), bsc * (0.8 + 0.2 * clamp(kb)))
    if lt >= t_ship + 0.05:
        dashed_curve(L, (bxy[0] + 60, bxy[1]), (560, 1260), (760, 1170), eo(p(lt, t_ship + 0.3, 0.7)), WHITE, 0.85, 5)
    kp = spring(lt - t_addr - 0.15, 2.4, 7)
    if lt >= t_addr - 0.15:
        pin(L, 760, 1170, clamp(kp * 1.5), RED, 0.9 + 0.1 * clamp(kp), t)
        chip(L, bg, 760, 1268, 'ADDRESS GIVEN BY THE CALLERS', eo(p(lt, t_addr + 0.1, 0.3)), 22, WHITE)


# ---------- scene 4: courier dossier + map ----------
def typed(txt, k):
    n = int(round(len(txt) * clamp(k)))
    return txt[:n]

def scene_fall(L, bg, t, lt, b):
    t_trav = T(b, 'travels')
    split = t_trav - 0.35
    if lt < split + 0.35:
        ka = spring(lt, 1.7, 6.5)
        out = eo(p(lt, split, 0.35))
        a = clamp(ka * 1.5) * (1 - out)
        cw, ch = 860, 860
        card = Image.new('RGBA', (cw, ch + 60), (0, 0, 0, 0))
        cd = ImageDraw.Draw(card)
        cd.rounded_rectangle((40, 0, 300, 90), radius=18, fill=(226, 218, 200, 255))
        cd.rounded_rectangle((0, 50, cw - 1, ch + 59), radius=26, fill=PAPER + (255,))
        cd.text((60, 16), 'CASE FILE', font=F('black', 30), fill=(70, 66, 60))
        cd.text((44, 96), 'Caught #1', font=F('black', 56), fill=INK)
        cd.rounded_rectangle((44, 180, 290, 228), radius=24, fill=(176, 28, 34, 255))
        cd.text((66, 189), 'THE COURIER', font=F('black', 26), fill=WHITE)
        sx, sy = cw - 210, 110
        cd.rounded_rectangle((sx - 120, sy - 30, sx + 120, sy + 210), radius=18, fill=(214, 208, 196, 255))
        cd.ellipse((sx - 44, sy + 10, sx + 44, sy + 98), fill=(120, 124, 134, 255))
        cd.pieslice((sx - 92, sy + 104, sx + 92, sy + 290), 180, 360, fill=(120, 124, 134, 255))
        scan = sy - 30 + (240 * ((lt * 0.6) % 1))
        cd.rectangle((sx - 120, scan, sx + 120, scan + 4), fill=(255, 69, 69, 160))
        cd.text((sx - 108, sy + 220), 'FACE NOT SHOWN', font=F('bold', 18), fill=(110, 106, 98))
        rows = [(T(b, 'collecting') - 0.1, 'ROLE', 'Collected the cash'),
                (T(b, 'new') - 0.1, 'FROM', 'New York City'),
                (TE(b, 'city') + 0.1, 'AGE', '38 (at sentencing)'),
                (T(b, 'travels') - 0.4, 'TRAVELED TO', 'Rhode Island and other places')]
        yy = 380
        for t0, lab, val in rows:
            if lt >= t0:
                cd.line((44, yy - 22, cw - 44, yy - 22), fill=(212, 204, 190), width=2)
                cd.text((44, yy), lab, font=F('bold', 22), fill=(130, 124, 114))
                cd.text((44, yy + 32), typed(val, (lt - t0) / 0.5), font=F('mono', 40), fill=INK)
            yy += 118
        sh, pad = shadow_sprite(cw, ch + 60, 26, 30, 0.7, 18)
        sc = 0.94 + 0.06 * clamp(ka) - 0.08 * out
        paste(L, sh, 540, 770 + 24, a, sc, rot=-1.5)
        paste(L, card, 540, 770, a, sc, rot=-1.5)
    if lt >= split:
        lm = lt - split
        km = eo(p(lm, 0, 0.5))
        x0, y0, x1, y1 = 70, 320, 1010, 1220
        glass(L, bg, (x0, y0, x1, y1), r=40, a=km, tint_a=14)
        dots = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dd = ImageDraw.Draw(dots)
        for gy in range(y0 + 40, y1 - 30, 30):
            for gx in range(x0 + 40, x1 - 30, 30):
                land = (gx - x0) * 0.62 + (gy - y0) > 260 and not ((gx - 560) ** 2 / 1.6 + (gy - 920) ** 2 < 180 ** 2)
                c = (120, 132, 160, 150) if land else (80, 90, 110, 60)
                dd.ellipse((gx - 2.2, gy - 2.2, gx + 2.2, gy + 2.2), fill=c)
        L.alpha_composite(fade(dots, km))
        NYC, NH, RI = (315, 955), (534, 736), (845, 551)
        k1 = spring(lm - 0.2, 2.4, 7)
        pin(L, NYC[0], NYC[1], clamp(k1 * 1.5), WHITE, 1.0, t)
        chip(L, bg, NYC[0] + 10, NYC[1] + 60, 'NEW YORK CITY', clamp(k1 * 1.5), 22, WHITE)
        t_ri = T(b, 'rhode') - split
        if lm >= t_ri - 0.4:
            ka2 = eo(p(lm, t_ri - 0.4, 0.8))
            dashed_curve(L, NYC, (380, 500), RI, ka2, RED, 1.0, 6, glow=True)
            if ka2 >= 1:
                mv = ((lm - t_ri) * 0.45) % 1
                pt = bezier(NYC, (380, 500), RI, mv)
                paste(L, rrect_sprite(22, 22, 11, fill=YEL + (255,)), pt[0], pt[1], 1.0)
            k2 = spring(lm - t_ri - 0.3, 2.4, 7)
            pin(L, RI[0], RI[1], clamp(k2 * 1.5), RED, 1.0, t)
            chip(L, bg, RI[0] - 40, RI[1] + 60, 'RHODE ISLAND', clamp(k2 * 1.5), 22, WHITE)
        t_jan = T(b, 'january') - split
        chip(L, bg, 540, 390, 'JANUARY 2021', eo(p(lm, t_jan - 0.15, 0.35)), 30, YEL, dot=YEL, fk='black')
        t_nh = T(b, 'haven') - split
        if lm >= t_nh - 0.3:
            k3 = spring(lm - t_nh + 0.3, 2.4, 7)
            pin(L, NH[0], NH[1], clamp(k3 * 1.5), (110, 150, 255), 1.0, t)
            chip(L, bg, NH[0] + 20, NH[1] + 60, 'NEW HAVEN POLICE', clamp(k3 * 1.5), 22, WHITE)
        t_rep = T(b, 'reports') - split
        if lm >= t_rep - 0.2:
            for i, (sxp, syp, cxp, cyp) in enumerate(((90, 560, 200, 600), (330, 1200, 330, 900), (980, 1000, 820, 900))):
                kk = eo(p(lm, t_rep - 0.2 + 0.15 * i, 0.7))
                dashed_curve(L, (sxp, syp), (cxp, cyp), NH, kk, (110, 150, 255), 0.9, 5)
            chip(L, bg, 540, 1060, 'REPORTS FROM OTHER STATES', eo(p(lm, t_rep + 0.3, 0.3)), 22, WHITE)
        t_fbi = T(b, 'fbi') - split
        chip(L, bg, 540, 1150, 'THE FBI JOINS THE INVESTIGATION', eo(p(lm, t_fbi - 0.1, 0.35)), 26, WHITE, dot=(110, 150, 255), fk='black')


# ---------- scene 5: sentencing ----------
STAMP = None
def stamp_sprite():
    global STAMP
    if STAMP is None:
        s = Image.new('RGBA', (900, 300), (0, 0, 0, 0))
        d = ImageDraw.Draw(s)
        d.rounded_rectangle((16, 16, 884, 284), radius=34, outline=(255, 69, 69, 255), width=14)
        t = text_sprite('SENTENCED', 'dblack', 150, RED)
        s.alpha_composite(t, (int(450 - t.width / 2), int(150 - t.height / 2)))
        rng = np.random.default_rng(11)
        a = np.array(s.getchannel('A'), dtype=np.int16)
        holes = rng.random(a.shape) < 0.05
        a[holes] = (a[holes] * 0.3).astype(np.int16)
        s.putalpha(Image.fromarray(a.clip(0, 255).astype(np.uint8), 'L'))
        g = s.filter(ImageFilter.GaussianBlur(20))
        out = Image.new('RGBA', s.size, (0, 0, 0, 0))
        out.alpha_composite(fade(g, 0.8)); out.alpha_composite(s)
        STAMP = out.rotate(7, expand=True, resample=Image.BICUBIC)
    return STAMP

def stat_row(L, bg, y, val, label, a, col=WHITE):
    if a <= 0.01:
        return
    glass(L, bg, (110, y - 56, 970, y + 56), r=28, a=a, tint_a=16)
    text(L, 150, y, val, 'dblack', 66, col, a, anchor='lm')
    text(L, 930, y, label, 'semi', 32, MUTED, a, anchor='rm')

def scene_ending(L, bg, t, lt, b):
    t_pl = T(b, 'pleads'); t_mail = T(b, 'mail'); t_sent = T(b, 'sentences'); t_th = T(b, 'thirty'); t_pr = T(b, 'prison')
    a1 = eo(p(lt, t_pl - 0.1, 0.35))
    chip(L, bg, 540, 330, 'PLEADED GUILTY · ' + typed('FEB 24, 2023', (lt - t_pl) / 0.6), a1, 28, WHITE, dot=GREEN, fk='black')
    text(L, 540, 420, 'Mail fraud and conspiracy to commit mail fraud', 'med', 32, WHITE, eo(p(lt, t_mail - 0.1, 0.35)))
    if lt >= t_sent - 0.05:
        k = clamp((lt - t_sent + 0.05) / 0.16)
        sc = 2.2 - 1.2 * eo(k)
        st = stamp_sprite()
        paste(L, st, 540, 640, clamp(k * 1.3), sc * 0.95)
        if k >= 1:
            kk = p(lt, t_sent + 0.11, 0.7)
            rng = np.random.default_rng(21)
            for i in range(26):
                ang = rng.uniform(0, 2 * math.pi); sp = rng.uniform(160, 420)
                r = sp * eo(kk)
                x = 540 + math.cos(ang) * (300 + r); y = 640 + math.sin(ang) * (120 + r * 0.6)
                paste(L, rrect_sprite(8, 8, 4, fill=(255, 120, 110, 255)), x, y, (1 - kk) * 0.9)
    stat_row(L, bg, 880, str(int(round(30 * eo(p(lt, t_th, 0.6))))) + ' months', 'federal prison', eo(p(lt, t_th - 0.1, 0.35)))
    stat_row(L, bg, 1010, '3 years', 'supervised release', eo(p(lt, t_th + 0.4, 0.35)))
    k3 = p(lt, t_th + 0.85, 0.9)
    stat_row(L, bg, 1140, '$' + format(int(round(867149 * eo(k3))), ','), 'restitution', eo(p(lt, t_th + 0.8, 0.35)), RED)


# ---------- scene 6: red flags + call to action ----------
def scene_flags(L, bg, t, lt, b):
    a = eo(p(lt, 0.0, 0.4))
    tri = Image.new('RGBA', (110, 100), (0, 0, 0, 0))
    td = ImageDraw.Draw(tri)
    td.polygon([(55, 4), (106, 96), (4, 96)], fill=RED + (255,))
    td.rounded_rectangle((50, 34, 60, 70), radius=4, fill=(20, 10, 10, 255))
    td.ellipse((49, 76, 61, 88), fill=(20, 10, 10, 255))
    paste(L, tri, 250, 300, a, 0.9)
    text(L, 590, 300, 'RED FLAGS', 'dblack', 96, RED, a, glow=(255, 40, 40, 0.7), glow_r=24)
    rows = [(T(b, 'caller') - 0.1, 'A call about a relative in jail'),
            (T(b, 'cash') - 0.1, 'Pressure to send cash fast'),
            (T(b, 'quiet') - 0.1, 'Being told to keep it secret')]
    y = 460
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
            text(L, 214 + dx, y, txt, 'bold', 40, WHITE, ra, anchor='lm')
        y += 126
    t_h = T(b, 'hang')
    if lt >= t_h - 0.1:
        k = spring(lt - t_h + 0.1, 2.0, 7)
        ga = clamp(k * 1.5)
        glass(L, bg, (100, 862, 980, 1030), r=30, a=ga, tint=(48, 209, 88), tint_a=34)
        paste(L, rrect_sprite(84, 84, 42, fill=GREEN + (255,)), 176, 946, ga, 0.8 + 0.2 * clamp(k))
        ck = Image.new('RGBA', (84, 84), (0, 0, 0, 0)); cdr = ImageDraw.Draw(ck)
        cdr.line((24, 44, 38, 58), fill=WHITE, width=8); cdr.line((38, 58, 62, 28), fill=WHITE, width=8)
        paste(L, ck, 176, 946, ga)
        text(L, 244, 914, 'Hang up.', 'black', 48, WHITE, ga, anchor='lm')
        text(L, 244, 974, 'Call family on a number you already know.', 'semi', 30, WHITE, ga, anchor='lm')
    t_f = T(b, 'follow')
    if lt >= t_f - 0.1:
        k = spring(lt - t_f + 0.1, 2.2, 7)
        fa = clamp(k * 1.5)
        pill = rrect_sprite(520, 84, 42, fill=RED + (255,))
        paste(L, pill, 540, 1110, fa, 0.85 + 0.15 * clamp(k) + 0.02 * math.sin(lt * 6))
        text(L, 540, 1110, 'FOLLOW FOR CAUGHT #2', 'black', 34, WHITE, fa, track=1)
    sa = eo(p(lt, 0.3, 0.5))
    text(L, 540, 1228, 'Source: U.S. Attorney’s Office, District of Rhode Island', 'med', 26, MUTED, sa)
    text(L, 540, 1264, 'Press release, Feb 29, 2024', 'med', 26, MUTED, sa)


SCENES = [scene_hook, scene_setup, scene_trust, scene_ask, scene_fall, scene_ending, scene_flags]
NO_CUT = {(1, 2)}
BG = None

def init():
    global BG, SHAKES
    BG = Background()
    b0, b5 = B(0), B(5)
    SHAKES = [(b0['start'] + T(b0, 'ordered') - 0.02, 7, 0.25),
              (b5['start'] + T(b5, 'sentences') + 0.11, 16, 0.45)]

def render_frame(fi):
    t = fi / FPS
    bg = BG.frame(t, fi)
    frame = bg.copy()
    bi = len(BEATS) - 1
    for i, b in enumerate(BEATS):
        if b['start'] <= t < b['end']:
            bi = i
            break
    b = BEATS[bi]
    lt = t - b['start']
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    SCENES[bi](L, bg, t, lt, b)
    dur = b['end'] - b['start']
    scale = 1 + 0.025 * clamp(lt / dur)
    alpha, blur = 1.0, 0.0
    if bi > 0 and (bi - 1, bi) not in NO_CUT:
        ke = eo(lt / 0.32)
        scale *= 0.94 + 0.06 * ke
        alpha *= ke
        blur += 8 * (1 - ke)
    if bi < len(BEATS) - 1 and (bi, bi + 1) not in NO_CUT:
        kx = clamp((lt - (dur - 0.22)) / 0.22)
        scale *= 1 + 0.07 * eio(kx)
        alpha *= 1 - eio(kx)
        blur += 8 * kx
    if bi == len(BEATS) - 1:
        alpha *= 1 - clamp((lt - (dur - 0.5)) / 0.5)
    dx, dy = shake(t)
    composite_layer(frame, L, scale, alpha, blur, dx, dy)
    for bb in BEATS[1:]:
        k = (t - (bb['start'] - 0.12)) / 0.5
        if 0 < k < 1:
            light_sweep(frame, k)
    if 5 <= bi:
        tsn = B(5)['start'] + T(B(5), 'sentences') + 0.11
        if tsn <= t < tsn + 0.35:
            fl = Image.new('RGBA', (W, H), (255, 40, 40, int(60 * (1 - (t - tsn) / 0.35))))
            frame.alpha_composite(fl)
    draw_header(frame, t, BEATS, 'CAUGHT #1', 'Real case · Rhode Island', eo(t / 0.5))
    draw_captions(frame, GROUPS, t)
    return frame.convert('RGB').tobytes()


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'events':
        init()
        ev = []
        for i, b in enumerate(BEATS[1:], 1):
            if (i - 1, i) not in NO_CUT:
                ev.append(['whoosh', round(b['start'] - 0.15, 3), 0.22])
        b0, b1, b2, b3, b4, b5, b6 = BEATS
        ev.append(['boom', b0['start'] + T(b0, 'ordered') - 0.02, 0.45])
        te = T(b0, 'eight') - 0.1
        k = 0.0
        while k < 1.25:
            ev.append(['tick', te + k, 0.08]); k += 0.06
        ev.append(['boom', te + 0.2 + 1.0 + 0.25, 0.6])
        for w in ('grandchild', 'lawyer'):
            ev.append(['pop', b1['start'] + T(b1, w) - 0.1, 0.18])
        ev.append(['pop', b2['start'] + T(b2, 'arrested') - 0.7, 0.2])
        ev.append(['pop', b2['start'] + T(b2, 'needs') - 0.5, 0.2])
        ev.append(['whoosh', b2['start'] + T(b2, 'told') - 0.2, 0.18])
        ev.append(['pop', b3['start'] + T(b3, 'address') - 0.15, 0.22])
        ev.append(['pop', b4['start'] + T(b4, 'rhode'), 0.2])
        ev.append(['pop', b4['start'] + T(b4, 'haven') - 0.3, 0.2])
        ev.append(['whoosh', b4['start'] + T(b4, 'travels') - 0.45, 0.18])
        for w, dt in (('collecting', -0.1), ('new', -0.1), ('city', 0.35)):
            t0 = b4['start'] + (T(b4, w) if w != 'city' else TE(b4, w)) + dt
            for j in range(8):
                ev.append(['type', t0 + j * 0.055, 0.12])
        ev.append(['boom', b5['start'] + T(b5, 'sentences') + 0.11, 0.75])
        for w in ('caller', 'cash', 'quiet', 'hang', 'follow'):
            ev.append(['pop', b6['start'] + T(b6, w) - 0.1, 0.2])
        json.dump({'total': TOTAL, 'events': [[a, round(b_, 3), c] for a, b_, c in ev]}, open(sys.argv[2], 'w'), indent=1)
        print(len(ev), 'events')
    elif mode == 'info':
        print(json.dumps([{'id': b['id'], 'start': round(b['start'], 2), 'end': round(b['end'], 2)} for b in BEATS]))
        print('total', round(TOTAL, 2), 'groups', len(GROUPS))
    elif mode == 'stills':
        init()
        out = sys.argv[2]; os.makedirs(out, exist_ok=True)
        times = [float(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else None
        if times is None:
            times = []
            for b in BEATS:
                for fr in (0.2, 0.55, 0.9):
                    times.append(b['start'] + (b['end'] - b['start']) * fr)
        for tt in times:
            Image.frombytes('RGB', (W, H), render_frame(int(tt * FPS))).save('%s/f_%06.2f.png' % (out, tt))
    elif mode == 'video':
        out = sys.argv[2]
        n = int(math.ceil(TOTAL * FPS))
        cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', out]
        pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        with Pool(2, initializer=init) as pool:
            for k, raw in enumerate(pool.imap(render_frame, range(n), chunksize=4)):
                pr.stdin.write(raw)
                if k % 300 == 0:
                    print('frame', k, '/', n, flush=True)
        pr.stdin.close(); pr.wait()
        print('done', out)
