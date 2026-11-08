"""Caught #2 video. Usage:
  python3 render.py stills <outdir> [t1,t2,...]
  python3 render.py events <events.json>
  python3 render.py video <out_noaudio.mp4>
Reads ../script/captions.json and ../audio/caught_002_words.json (from tools/voice/align.py).
Without the words file it estimates timings from the script so scenes can be previewed."""
import json, math, os, re, subprocess, sys
from multiprocessing import Pool
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
EP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EP, '..', '..', 'tools', 'video'))
from engine import *  # noqa
from kit import *  # noqa

CAPS = json.load(open(os.path.join(EP, 'script', 'captions.json')))
WF = os.path.join(EP, 'audio', 'caught_002_words.json')
if os.path.exists(WF):
    WORDS = json.load(open(WF))
else:
    WORDS, t = [], 0.3
    for c in CAPS:
        ws = []
        for ch in c['chunks']:
            for w in re.findall(r"[A-Za-z']+", ch['spoken'].replace('-', ' ')):
                ws.append([w, round(t, 3), round(t + 0.3, 3)]); t += 0.34
        WORDS.append({'words': ws}); t += 0.75
AUDIO_END = WORDS[-1]['words'][-1][2]

BEATS = []
for i, para in enumerate(WORDS):
    st = 0.0 if i == 0 else para['words'][0][1] - 0.3
    BEATS.append({'id': CAPS[i]['id'], 'start': st, 'w': para['words']})
for a_, b_ in zip(BEATS, BEATS[1:]):
    a_['end'] = b_['start']
BEATS[-1]['end'] = AUDIO_END + 1.4
TOTAL = BEATS[-1]['end']
GROUPS = build_groups([c['chunks'] for c in CAPS], [para['words'] for para in WORDS])
GOLD = (255, 196, 64)


def T(b, word, n=0):
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


SHAKES = []
def shake(t):
    dx = dy = 0.0
    for t0, amp, dur in SHAKES:
        if t0 <= t < t0 + dur:
            k = 1 - (t - t0) / dur
            dx += amp * k * math.sin((t - t0) * 90); dy += amp * k * math.cos((t - t0) * 77)
    return dx, dy


# ---------- sprites ----------
_gb = {}
def gold_bar(w=190):
    if w not in _gb:
        h = int(w * 0.48)
        s = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(s)
        top_h = int(h * 0.36)
        d.polygon([(w * 0.12, 0), (w * 0.88, 0), (w, top_h), (0, top_h)], fill=(255, 226, 120, 255))
        for i in range(h - top_h):
            k = i / max(1, h - top_h)
            c = (int(235 - 70 * k), int(170 - 60 * k), int(40 - 20 * k), 255)
            d.line((0, top_h + i, w, top_h + i), fill=c)
        d.rounded_rectangle((w * 0.3, top_h + 8, w * 0.7, h - 10), radius=6, outline=(150, 98, 20, 255), width=2)
        t = text_sprite('1 KG', 'black', int(w * 0.11), (120, 76, 14))
        s.alpha_composite(t, (int(w / 2 - t.width / 2), int(top_h + (h - top_h) / 2 - t.height / 2)))
        _gb[w] = s
    return _gb[w]

def gold_stack(L, cx, cy, n_show, lt, scale=1.0, shimmer_t=0.0):
    """16 bars in rows of 5, 4, 4, 3 (bottom to top); n_show bars visible (float for the pop)."""
    rows = [5, 4, 4, 3]
    bw = int(150 * scale); bh = int(bw * 0.48)
    idx = 0
    for r, cnt in enumerate(rows):
        y = cy - r * (bh * 0.62)
        x0 = cx - (cnt - 1) * bw * 0.52
        for i in range(cnt):
            if idx < n_show:
                k = clamp(n_show - idx)
                sp = spring(k * 0.6, 3, 7) if k < 1 else 1
                paste(L, gold_bar(bw), x0 + i * bw * 1.04, y - 40 * (1 - clamp(sp)), clamp(k * 2), 0.8 + 0.2 * clamp(sp))
            idx += 1
    if shimmer_t > 0:
        k = (shimmer_t % 2.2) / 1.0
        if k < 1:
            band = Image.new('RGBA', (90, 420), (255, 255, 230, 0))
            band.putalpha(Image.fromarray(np.repeat((np.exp(-(np.linspace(-1, 1, 90) * 2.2) ** 2) * 120).astype(np.uint8)[None, :], 420, axis=0), 'L'))
            band = band.rotate(-20, expand=True)
            paste(L, band, cx - 420 + 840 * k, cy - 100, 0.8)

def house(L, cx, cy, a, label, bg):
    if a <= 0.01:
        return
    s = Image.new('RGBA', (160, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.ellipse((10, 6, 150, 146), fill=(52, 56, 72, 255), outline=GOLD + (255,), width=5)
    silhouette(d, 80, 82, 0.5, (190, 194, 206, 255))
    paste(L, s, cx, cy, a)
    g = Image.new('RGBA', (220, 220), (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse((40, 40, 180, 180), fill=GOLD + (140,))
    paste(L, g.filter(ImageFilter.GaussianBlur(30)), cx, cy + 20, a * 0.6)
    text(L, cx, cy + 110, label, 'bold', 24, WHITE, a, track=2)


# ---------- scene 0: hook ----------
def s_hook(L, bg, t, lt, b):
    t_pol = T(b, 'police'); t_carry = T(b, 'carrying'); t_worth = T(b, 'worth'); t_days = T(b, 'days'); t_homes = T(b, 'belonged')
    # siren glow
    if lt >= t_pol - 0.2:
        ka = eo(p(lt, t_pol - 0.2, 0.4))
        ph = (math.sin(lt * 9) + 1) / 2
        for col, x, w_ in (((255, 50, 60), 140, ph), ((60, 110, 255), 940, 1 - ph)):
            g = Image.new('RGBA', (500, 500), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((100, 100, 400, 400), fill=col + (255,))
            paste(L, g.filter(ImageFilter.GaussianBlur(70)), x, 300, ka * (0.25 + 0.45 * w_))
    chip(L, bg, 540, 300, 'ARRESTED · ILLINOIS · MARCH 27, 2024', eo(p(lt, t_pol - 0.15, 0.35)), 24, WHITE, dot=RED, fk='black')
    n = 16 * eo(p(lt, t_carry - 0.3, 1.5))
    shrink = eio(p(lt, t_days - 0.2, 0.6))
    gold_stack(L, 540, 720 - 60 * shrink, n, lt, 1.0 - 0.25 * shrink, lt - t_carry if lt > t_carry + 1.2 else 0)
    ka = eo(p(lt, t_carry, 0.35))
    chip(L, bg, 540, 840 - 80 * shrink, '16 GOLD BARS · 1 KG EACH', ka * (1 - shrink), 24, GOLD, fk='black')
    kv = p(lt, t_worth - 0.1, 1.0)
    if kv > 0:
        val = '$' + format(int(round(1000000 * eo(kv))), ',') + ('+' if kv >= 1 else '')
        glow = (255, 170, 30, 0.8) if kv >= 1 else None
        text(L, 540, 960 - 90 * shrink, val, 'dblack', 128, GOLD, eo(p(lt, t_worth - 0.1, 0.25)), glow=glow, glow_r=30,
             scale=1 + 0.06 * max(0, 1 - spring(lt - t_worth - 0.9, 3, 6)) if lt > t_worth + 0.9 else 1)
        text(L, 540, 1050 - 90 * shrink, 'worth more than a million dollars', 'semi', 34, MUTED, eo(p(lt, t_worth + 0.3, 0.3)) * (1 - shrink))
    kh = spring(lt - t_homes + 0.2, 2.2, 7)
    if lt >= t_homes - 0.2:
        house(L, 300, 1080, clamp(kh * 1.5), 'VICTIM · LITTLETON, CO', bg)
        house(L, 780, 1080, clamp(kh * 1.5), 'VICTIM · KANSAS CITY, MO', bg)


# ---------- scene 1: the computer ----------
def laptop(L, bg, cx, cy, lt, b, a):
    sw, sh = 820, 520
    body = Image.new('RGBA', (sw + 40, sh + 110), (0, 0, 0, 0))
    d = ImageDraw.Draw(body)
    d.rounded_rectangle((0, 0, sw + 39, sh + 40), radius=26, fill=(36, 39, 50, 255), outline=(92, 98, 115, 255), width=3)
    yy = np.linspace(0, 1, sh)[:, None, None]
    grad = np.array([30, 60, 120], float) * (1 - yy) + np.array([60, 30, 90], float) * yy
    scr = Image.fromarray(np.broadcast_to(grad, (sh, sw, 3)).astype(np.uint8), 'RGB').convert('RGBA')
    sd = ImageDraw.Draw(scr)
    for i in range(4):
        sd.rounded_rectangle((40, 40 + i * 92, 112, 112 + i * 92), radius=14, fill=(255, 255, 255, 40))
    sd.rectangle((0, sh - 48, sw, sh), fill=(10, 12, 20, 200))
    t_mal = T(b, 'malware')
    if lt >= t_mal - 0.1:
        k = spring(lt - t_mal + 0.1, 3, 6)
        win = Image.new('RGBA', (560, 330), (0, 0, 0, 0))
        wd = ImageDraw.Draw(win)
        wd.rounded_rectangle((0, 0, 559, 329), radius=18, fill=(248, 248, 250, 255))
        wd.rounded_rectangle((0, 0, 559, 70), radius=18, fill=(214, 38, 46, 255))
        wd.rectangle((0, 40, 559, 70), fill=(214, 38, 46, 255))
        tt = text_sprite('⚠  SECURITY ALERT', 'black', 30, WHITE)
        win.alpha_composite(tt, (28, int(35 - tt.height / 2)))
        tt = text_sprite('Call support now:', 'semi', 30, INK)
        win.alpha_composite(tt, (40, 108))
        num = Image.new('RGBA', (480, 80), (0, 0, 0, 0))
        nd = ImageDraw.Draw(num)
        nd.rounded_rectangle((0, 0, 479, 79), radius=14, fill=(255, 236, 236, 255))
        nt = text_sprite('1-8XX-XXX-XXXX', 'black', 46, (190, 20, 30))
        num.alpha_composite(nt, (int(240 - nt.width / 2), int(40 - nt.height / 2)))
        num = num.filter(ImageFilter.GaussianBlur(3.5))
        win.alpha_composite(num, (40, 160))
        tt = text_sprite('number blurred · reenactment', 'med', 20, (120, 120, 128))
        win.alpha_composite(tt, (40, 262))
        sc = 0.7 + 0.3 * clamp(k)
        jit = (lt - t_mal) < 0.45
        ox = int(6 * math.sin(lt * 60)) if jit else 0
        w2 = win.resize((int(560 * sc), int(330 * sc)), Image.BICUBIC)
        if jit:
            r_ = fade(w2, 0.5)
            scr.alpha_composite(r_, (int(sw / 2 - w2.width / 2) + 12, int(sh / 2 - w2.height / 2 - 20)))
        scr.alpha_composite(fade(w2, clamp(k * 1.5)), (int(sw / 2 - w2.width / 2) + ox, int(sh / 2 - w2.height / 2 - 20)))
    m = rrect_sprite(sw, sh, 14, fill=(255, 255, 255, 255)).getchannel('A')
    scr.putalpha(m)
    body.alpha_composite(scr, (20, 20))
    d = ImageDraw.Draw(body)
    d.polygon([(-0, sh + 40), (sw + 39, sh + 40), (sw + 39 - 0, sh + 70), (0, sh + 70)], fill=(70, 74, 88, 255))
    sh_, pad = shadow_sprite(sw + 40, sh + 70, 26, 34, 0.7, 20)
    paste(L, sh_, cx, cy + 30, a)
    paste(L, body, cx, cy, a)

def s_setup(L, bg, t, lt, b):
    k = spring(lt, 1.8, 6.5)
    chip(L, bg, 540, 300, 'REENACTMENT', clamp(k * 1.5), 22, RED, fk='black')
    laptop(L, bg, 540, 640 + 300 * (1 - clamp(k)), lt, b, clamp(k * 1.5))
    t_calls = T(b, 'calls'); t_ms = TE(b, 'number', 1)
    if lt >= t_calls - 0.15:
        kc = spring(lt - t_calls + 0.15, 2.4, 7)
        ph = Image.new('RGBA', (120, 120), (0, 0, 0, 0))
        pd = ImageDraw.Draw(ph)
        pd.ellipse((0, 0, 119, 119), fill=GREEN + (255,))
        pd.rounded_rectangle((44, 30, 76, 90), radius=10, outline=WHITE, width=6)
        ang = 12 * math.sin(lt * 30) if lt - t_calls < 1.2 else 0
        paste(L, ph, 540, 1000, clamp(kc * 1.5), 0.8 + 0.2 * clamp(kc), rot=ang)
        for j in range(2):
            ph_ = ((lt * 1.2) + j / 2) % 1
            ring(L, 540, 1000, 64 + 60 * ph_, (1 - ph_) * 0.6 * clamp(kc), GREEN, 3)
    chip(L, bg, 540, 1140, 'ON THE OTHER END: THE SCAMMERS', eo(p(lt, t_ms - 0.1, 0.35)), 24, WHITE, fk='black')


# ---------- scene 2: the call grows ----------
def tile(L, bg, x0, y0, w, h, label, a, ring_col, lt):
    if a <= 0.01:
        return
    glass(L, bg, (x0, y0, x0 + w, y0 + h), r=28, a=a, tint_a=16)
    s = Image.new('RGBA', (220, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.ellipse((10, 10, 210, 210), fill=(52, 56, 72, 255), outline=ring_col + (255,), width=6)
    silhouette(d, 110, 112, 0.62, (140, 144, 156, 255))
    m = Image.new('L', (220, 220), 0); ImageDraw.Draw(m).ellipse((10, 10, 210, 210), fill=255)
    s.putalpha(Image.fromarray(np.minimum(np.array(s.getchannel('A')), np.array(m)), 'L'))
    paste(L, s, x0 + w / 2, y0 + h / 2 - 26, a, 0.7)
    text(L, x0 + w / 2, y0 + h - 40, label, 'bold', 28, WHITE, a)
    for i in range(5):
        hgt = 6 + 16 * abs(math.sin(lt * 8 + i + x0))
        paste(L, rrect_sprite(8, int(hgt), 4, fill=GREEN + (230,)), x0 + 30 + i * 13, y0 + 34, a)

def banner(L, bg, y, txt, a, dx=0):
    if a <= 0.01:
        return
    glass(L, bg, (100 + dx, y - 54, 980 + dx, y + 54), r=28, a=a, tint=(255, 59, 59), tint_a=40)
    paste(L, rrect_sprite(56, 56, 14, fill=RED + (255,)), 158 + dx, y, a)
    text(L, 158 + dx, y, '!', 'black', 36, WHITE, a)
    lines = wrap(txt, 'bold', 34, 720)
    for j, ln in enumerate(lines):
        text(L, 206 + dx, y + (j - (len(lines) - 1) / 2) * 40, ln, 'bold', 34, WHITE, a, anchor='lm')

def s_trust(L, bg, t, lt, b):
    a0 = eo(p(lt, 0, 0.35))
    chip(L, bg, 540, 300, 'REENACTMENT · WHO THEY CLAIM TO BE', a0, 22, RED, fk='black')
    t_ms = T(b, 'microsoft'); t_bank = T(b, 'bank'); t_gov = T(b, 'government'); t_law = T(b, 'law')
    tiles = [(t_ms - 0.15, '“Microsoft”', (110, 150, 255)), (t_bank - 0.1, 'Bank official', GOLD),
             (t_gov - 0.1, 'Government employee', (200, 200, 210)), (t_law - 0.1, 'Law enforcement', RED)]
    pos = [(100, 360), (550, 360), (100, 650), (550, 650)]
    for (t0, lab, col), (x0, y0) in zip(tiles, pos):
        k = spring(lt - t0, 2.4, 7)
        if lt >= t0:
            tile(L, bg, x0, y0 + 30 * (1 - clamp(k)), 430, 270, lab, clamp(k * 1.5), col, lt)
    t_id = T(b, 'identity'); t_money = T(b, 'money')
    k1 = spring(lt - t_id + 0.1, 2.4, 7)
    if lt >= t_id - 0.1:
        banner(L, bg, 1010, 'Your identity has been compromised', clamp(k1 * 1.5), int(80 * (1 - clamp(k1))))
    k2 = spring(lt - t_money + 0.1, 2.4, 7)
    if lt >= t_money - 0.1:
        banner(L, bg, 1140, 'Your money isn’t safe in the bank', clamp(k2 * 1.5), int(80 * (1 - clamp(k2))))


# ---------- scene 3: savings into gold ----------
def account(L, bg, x0, y0, label, frac, a):
    if a <= 0.01:
        return
    glass(L, bg, (x0, y0, x0 + 400, y0 + 170), r=28, a=a, tint_a=16)
    text(L, x0 + 30, y0 + 44, label, 'bold', 24, MUTED, a, anchor='lm', track=2)
    text(L, x0 + 30, y0 + 96, '$ ' + ('•' * max(0, int(round(7 * frac)))), 'black', 40, WHITE, a, anchor='lm')
    paste(L, rrect_sprite(340, 14, 7, fill=(70, 76, 92, 255)), x0 + 30, y0 + 138, a, anchor='lm')
    if frac > 0.02:
        paste(L, rrect_sprite(max(14, int(340 * frac)), 14, 7, fill=GREEN + (255,)), x0 + 30, y0 + 138, a, anchor='lm')

def s_ask(L, bg, t, lt, b):
    t_cash = T(b, 'cash'); t_gold = T(b, 'gold'); t_when = T(b, 'when'); t_safe = T(b, 'safekeeping'); t_some = T(b, 'some'); t_dept = T(b, 'department')
    ph1 = 1 - eio(p(lt, t_when - 0.3, 0.5))
    if ph1 > 0.01:
        a = eo(p(lt, 0, 0.35)) * ph1
        chip(L, bg, 540, 300, 'VICTIMS AGED 61 TO 80', a, 26, WHITE, fk='black')
        drain = 1 - eio(p(lt, t_cash, 1.6))
        account(L, bg, 90, 380, 'BANK ACCOUNT', drain, a)
        account(L, bg, 590, 380, 'RETIREMENT', drain, a)
        for i in range(10):
            k = p(lt, t_cash + 0.1 + i * 0.12, 0.7)
            if 0 < k < 1:
                src = (290, 560) if i % 2 == 0 else (790, 560)
                pt = bezier(src, (540, 600), (540, 820), eo(k))
                paste(L, text_sprite('$', 'black', 40, GREEN), pt[0], pt[1], a * (1 - k * 0.3))
        n = 16 * eo(p(lt, t_gold - 0.3, 0.9))
        gold_stack(L, 540, 900, n, lt, 0.8, lt - t_gold if lt > t_gold + 0.6 else 0)
    if lt >= t_when - 0.3:
        kq = spring(lt - t_when + 0.3, 1.8, 6.5) * (1 - eio(p(lt, t_some - 0.3, 0.4)))
        release_card(L, 540 + 400 * (1 - clamp(kq)), 700, 900, QUOTE_SAFE, QUOTE_SAFE_HL,
                     eo(p(lt, t_safe - 0.1, 0.6)), clamp(kq * 1.5), rot=-1.8, qsize=38,
                     footer='U.S. Attorney’s Office, Western District of Missouri')
    if lt >= t_some - 0.3:
        kl = spring(lt - t_some + 0.3, 1.8, 6.5)
        a = clamp(kl * 1.5)
        lab = Image.new('RGBA', (820, 470), (0, 0, 0, 0))
        ld = ImageDraw.Draw(lab)
        ld.rounded_rectangle((0, 0, 819, 469), radius=22, fill=(250, 248, 242, 255), outline=(30, 30, 34, 255), width=4)
        ld.rectangle((0, 0, 819, 76), fill=(30, 30, 34, 255))
        ld.text((30, 18), 'SHIPPING LABEL', font=F('black', 34), fill=WHITE)
        ld.text((560, 24), 'REENACTMENT', font=F('bold', 24), fill=(255, 110, 110))
        ld.text((30, 108), 'TO:', font=F('bold', 28), fill=(110, 106, 98))
        kt = p(lt, t_dept - 0.2, 0.7)
        ld.text((30, 150), typed('DEPARTMENT OF JUSTICE', kt), font=F('mono', 46), fill=INK)
        ld.text((30, 230), 'ATTN:', font=F('bold', 28), fill=(110, 106, 98))
        ld.rounded_rectangle((130, 226, 560, 270), radius=6, fill=(30, 30, 34, 255))
        ld.text((30, 300), 'a specific name the scammers gave', font=F('med', 26), fill=(110, 106, 98))
        for i in range(30):
            x = 30 + i * 24
            ld.rectangle((x, 370, x + (8 if i % 3 else 14), 440), fill=INK)
        paste(L, lab, 540, 760 + 300 * (1 - clamp(kl)), a, rot=2 * (1 - clamp(kl)) - 1.2)


# ---------- scene 4: the courier ----------
def s_courier(L, bg, t, lt, b):
    ka = spring(lt, 1.7, 6.5)
    a = clamp(ka * 1.5)
    cw, ch = 860, 820
    card = Image.new('RGBA', (cw, ch + 60), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((40, 0, 300, 90), radius=18, fill=(226, 218, 200, 255))
    cd.rounded_rectangle((0, 50, cw - 1, ch + 59), radius=26, fill=PAPER + (255,))
    cd.text((60, 16), 'CASE FILE', font=F('black', 30), fill=(70, 66, 60))
    cd.text((44, 96), 'Caught #2', font=F('black', 56), fill=INK)
    cd.rounded_rectangle((44, 180, 290, 228), radius=24, fill=(176, 28, 34, 255))
    cd.text((66, 189), 'THE COURIER', font=F('black', 26), fill=WHITE)
    sx, sy = cw - 210, 110
    cd.rounded_rectangle((sx - 120, sy - 30, sx + 120, sy + 210), radius=18, fill=(214, 208, 196, 255))
    silhouette(cd, sx, sy + 100, 1.0)
    scan = sy - 30 + (240 * ((lt * 0.6) % 1))
    cd.rectangle((sx - 120, scan, sx + 120, scan + 4), fill=(255, 69, 69, 160))
    cd.text((sx - 108, sy + 220), 'FACE NOT SHOWN', font=F('bold', 18), fill=(110, 106, 98))
    rows = [(T(b, 'courier') - 0.1, 'FROM', 'Illinois'),
            (TE(b, 'illinois') + 0.1, 'AGE', '38 (at sentencing)'),
            (T(b, 'carrying') - 0.1, 'ROLE', 'Picked up gold and cash'),
            (T(b, 'across') - 0.1, 'MOVED IT', 'Across state lines')]
    yy = 380
    for t0, lab, val in rows:
        if lt >= t0:
            cd.line((44, yy - 22, cw - 44, yy - 22), fill=(212, 204, 190), width=2)
            cd.text((44, yy), lab, font=F('bold', 22), fill=(130, 124, 114))
            cd.text((44, yy + 32), typed(val, (lt - t0) / 0.45), font=F('mono', 40), fill=INK)
        yy += 112
    sh, pad = shadow_sprite(cw, ch + 60, 26, 30, 0.7, 18)
    sc = 0.94 + 0.06 * clamp(ka)
    paste(L, sh, 540, 770 + 24, a, sc, rot=-1.5)
    paste(L, card, 540, 770, a, sc, rot=-1.5)


# ---------- scenes 5 and 6: the run and the arrest ----------
MAPBOX = (60, 340, 1020, 1120)
def mxy(lon, lat):
    return (90 + (lon + 107) / 21 * 900, 340 + (43 - lat) / 7 * 760)
LIT, KC, IL = mxy(-105.0, 39.6), mxy(-94.58, 39.1), mxy(-90.23, 39.73)

def _land(gx, gy):
    return True

def s_run(L, bg, t, lt, b):
    km = eo(p(lt, 0, 0.45))
    dot_map(L, bg, MAPBOX, km, _land)
    text(L, 540, 400, 'CENTRAL U.S.', 'bold', 22, DIM, km, track=4)
    chip(L, bg, 540, 470, 'MARCH 25–26, 2024', eo(p(lt, T(b, 'march') - 0.1, 0.35)), 30, YEL, dot=YEL, fk='black')
    t_lit = T(b, 'littleton'); t_kc = T(b, 'kansas')
    for (pt, lab, t0, dy) in ((LIT, 'LITTLETON, CO', t_lit, 70), (KC, 'KANSAS CITY, MO', t_kc, 70)):
        if lt >= t0 - 0.2:
            k = spring(lt - t0 + 0.2, 2.4, 7)
            pin(L, pt[0], pt[1], clamp(k * 1.5), GOLD, 1.0, t)
            chip(L, bg, pt[0] + (60 if pt == LIT else 0), pt[1] + dy, lab, clamp(k * 1.5), 22, WHITE)
    t_pick = T(b, 'picks')
    n = 16 * eo(p(lt, t_pick, 2.6))
    if lt >= t_pick - 0.2:
        a = eo(p(lt, t_pick - 0.2, 0.3))
        glass(L, bg, (250, 930, 830, 1060), r=30, a=a, tint=(255, 196, 64), tint_a=26)
        paste(L, gold_bar(120), 340, 995, a)
        text(L, 420, 975, '%d × 1 KG GOLD BARS' % int(round(n)), 'black', 36, GOLD, a, anchor='lm')
        text(L, 420, 1020, 'more than $1 million', 'semi', 26, WHITE, a, anchor='lm')

def s_catch(L, bg, t, lt, b):
    km = 1 - eio(p(lt, T(b, 'deputy') - 0.4, 0.5))
    if km > 0.01:
        dot_map(L, bg, MAPBOX, km, _land)
        pin(L, LIT[0], LIT[1], km, GOLD, 1.0, t)
        pin(L, KC[0], KC[1], km, GOLD, 1.0, t)
        k = eo(p(lt, 0.1, 1.0))
        dashed_curve(L, LIT, (500, 500), IL, k, RED, km, 5, glow=True)
        dashed_curve(L, KC, (720, 600), IL, k, RED, km, 5, glow=True)
        if lt >= 0.9:
            kp = spring(lt - 0.9, 2.4, 7)
            pin(L, IL[0], IL[1], clamp(kp * 1.5) * km, RED, 1.0, t)
            chip(L, bg, IL[0] - 40, IL[1] + 70, 'ILLINOIS', clamp(kp * 1.5) * km, 24, WHITE, fk='black')
    else:
        ph = (math.sin(lt * 9) + 1) / 2
        for col, x, w_ in (((255, 50, 60), 140, ph), ((60, 110, 255), 940, 1 - ph)):
            g = Image.new('RGBA', (560, 560), (0, 0, 0, 0))
            ImageDraw.Draw(g).ellipse((110, 110, 450, 450), fill=col + (255,))
            paste(L, g.filter(ImageFilter.GaussianBlur(80)), x, 420, 0.25 + 0.5 * w_)
    t_arr = T(b, 'arrest')
    chip(L, bg, 540, 300, 'MARCH 27, 2024 · ILLINOIS', eo(p(lt, T(b, 'next') - 0.1, 0.35)), 28, WHITE, dot=RED, fk='black')
    stamp(L, 'ARRESTED', 540, 560, lt, t_arr - 0.05)
    for t0, y, lab in ((T(b, 'deputy') - 0.1, 790, 'MORGAN COUNTY DEPUTY SHERIFF'), (T(b, 'sergeant') - 0.1, 880, 'ILLINOIS STATE HIGHWAY PATROL SERGEANT')):
        if lt >= t0:
            chip(L, bg, 540, y, lab, eo(p(lt, t0, 0.3)), 24, WHITE, dot=(110, 150, 255))
    t_g = T(b, 'gold')
    if lt >= t_g - 0.2:
        a = eo(p(lt, t_g - 0.2, 0.35))
        gold_stack(L, 540, 1110, 16, lt, 0.55, lt - t_g)
        chip(L, bg, 540, 1210, 'GOLD BARS STILL WITH HIM', a, 24, GOLD, fk='black')


# ---------- scene 7: sentencing ----------
def s_ending(L, bg, t, lt, b):
    chip(L, bg, 540, 300, 'KANSAS CITY · MAY 21, 2026', eo(p(lt, 0.0, 0.35)), 28, WHITE, dot=GREEN, fk='black')
    stamp(L, 'SENTENCED', 540, 520, lt, T(b, 'sentences') - 0.05)
    t_f = T(b, 'fifteen'); t_tw = T(b, 'twelve')
    stat_row(L, bg, 740, '15½ years', 'federal prison', eo(p(lt, t_f - 0.1, 0.35)), WHITE, 'no parole')
    k = p(lt, t_f + 1.2, 0.9)
    stat_row(L, bg, 870, '$' + format(int(round(4754000 * eo(k))), ','), 'restitution', eo(p(lt, t_f + 1.1, 0.35)), RED)
    stat_row(L, bg, 1000, '12 victims', 'identified', eo(p(lt, t_tw - 0.1, 0.35)), WHITE, 'more than $6 million lost')
    stat_row(L, bg, 1130, 'Gold bars', 'forfeited', eo(p(lt, TE(b, 'dollars') - 0.2, 0.35)), GOLD)


# ---------- scene 8: red flags ----------
def s_flags(L, bg, t, lt, b):
    warn_title(L, lt)
    flag_rows(L, bg, lt, [(T(b, 'company') - 0.1, 'A screen telling you to call a number'),
                          (T(b, 'gold') - 0.1, 'Told your money isn’t safe in the bank'),
                          (T(b, 'courier') - 0.1, 'Anyone collecting gold or cash “for safekeeping”')])
    action_card(L, bg, lt, T(b, 'call', 0) - 0.1, 'Don’t call it.', 'Call your bank on the number from your card.')
    follow_pill(L, lt, T(b, 'follow') - 0.1, 'FOLLOW FOR CAUGHT #3')
    source_line(L, lt, 'Source: U.S. Attorney’s Office, Western District of Missouri', 'Press release, May 21, 2026')


QUOTE_SAFE = os.environ.get('QUOTE_SAFE', 'victims were told to give the gold to a co-conspirator for “safekeeping”')
QUOTE_SAFE_HL = ['safekeeping']
qf = os.path.join(EP, 'source', 'quotes.json')
if os.path.exists(qf):
    _q = json.load(open(qf))
    QUOTE_SAFE = _q.get('safekeeping', QUOTE_SAFE)
    QUOTE_SAFE_HL = _q.get('safekeeping_hl', QUOTE_SAFE_HL)

SCENES = [s_hook, s_setup, s_trust, s_ask, s_courier, s_run, s_catch, s_ending, s_flags]
NO_CUT = {(5, 6)}
BG = None

def init():
    global BG, SHAKES
    BG = Background(seed=8)
    b6, b7 = BEATS[6], BEATS[7]
    SHAKES = [(b6['start'] + T(b6, 'arrest') + 0.11, 14, 0.4), (b7['start'] + T(b7, 'sentences') + 0.11, 16, 0.45)]

def render_frame(fi):
    t = fi / FPS
    bg = BG.frame(t, fi)
    frame = bg.copy()
    bi = len(BEATS) - 1
    for i, b in enumerate(BEATS):
        if b['start'] <= t < b['end']:
            bi = i; break
    b = BEATS[bi]
    lt = t - b['start']
    L = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    SCENES[bi](L, bg, t, lt, b)
    dur = b['end'] - b['start']
    scale = 1 + 0.025 * clamp(lt / dur)
    alpha, blur = 1.0, 0.0
    if bi > 0 and (bi - 1, bi) not in NO_CUT:
        ke = eo(lt / 0.32); scale *= 0.94 + 0.06 * ke; alpha *= ke; blur += 8 * (1 - ke)
    if bi < len(BEATS) - 1 and (bi, bi + 1) not in NO_CUT:
        kx = clamp((lt - (dur - 0.22)) / 0.22); scale *= 1 + 0.07 * eio(kx); alpha *= 1 - eio(kx); blur += 8 * kx
    if bi == len(BEATS) - 1:
        alpha *= 1 - clamp((lt - (dur - 0.5)) / 0.5)
    dx, dy = shake(t)
    composite_layer(frame, L, scale, alpha, blur, dx, dy)
    for bb in BEATS[1:]:
        k = (t - (bb['start'] - 0.12)) / 0.5
        if 0 < k < 1:
            light_sweep(frame, k)
    for t0, _, _ in SHAKES:
        if t0 <= t < t0 + 0.35:
            frame.alpha_composite(Image.new('RGBA', (W, H), (255, 40, 40, int(55 * (1 - (t - t0) / 0.35)))))
    draw_header(frame, t, BEATS, 'CAUGHT #2', 'Real case · Missouri', eo(t / 0.5))
    draw_captions(frame, GROUPS, t)
    return frame.convert('RGB').tobytes()


def events():
    init()
    ev = []
    for i, b in enumerate(BEATS[1:], 1):
        if (i - 1, i) not in NO_CUT:
            ev.append(['whoosh', round(b['start'] - 0.15, 3), 0.22])
    b0, b1, b2, b3, b4, b5, b6, b7, b8 = BEATS
    tc = b0['start'] + T(b0, 'carrying') - 0.3
    for i in range(16):
        ev.append(['tick', tc + 1.5 * (1 - (1 - (i + 1) / 16) ** (1 / 3)), 0.12])
    ev.append(['boom', b0['start'] + T(b0, 'worth') + 0.9, 0.55])
    ev.append(['pop', b0['start'] + T(b0, 'police') - 0.15, 0.2])
    ev.append(['boom', b1['start'] + T(b1, 'malware') - 0.1, 0.3])
    ev.append(['pop', b1['start'] + T(b1, 'calls') - 0.15, 0.2])
    for w, n in (('bank', 0), ('law', 0), ('identity', 0), ('money', 0)):
        ev.append(['pop', b2['start'] + T(b2, w, n) - 0.1, 0.2])
    ev.append(['pop', b2['start'] + T(b2, 'microsoft') - 0.15, 0.18])
    ev.append(['pop', b2['start'] + T(b2, 'government') - 0.1, 0.18])
    for i in range(8):
        ev.append(['tick', b3['start'] + T(b3, 'cash') + 0.1 + i * 0.12, 0.07])
    ev.append(['whoosh', b3['start'] + T(b3, 'when') - 0.35, 0.16])
    ev.append(['whoosh', b3['start'] + T(b3, 'some') - 0.35, 0.16])
    for j in range(10):
        ev.append(['type', b3['start'] + T(b3, 'department') - 0.2 + j * 0.06, 0.12])
    for w, f in (('courier', T), ('illinois', TE), ('carrying', T), ('across', T)):
        t0 = b4['start'] + f(b4, w) - (0.1 if f is T else -0.1)
        for j in range(7):
            ev.append(['type', t0 + j * 0.055, 0.11])
    ev.append(['pop', b5['start'] + T(b5, 'littleton') - 0.2, 0.2])
    ev.append(['pop', b5['start'] + T(b5, 'kansas') - 0.2, 0.2])
    for i in range(16):
        ev.append(['tick', b5['start'] + T(b5, 'picks') + i * 0.16, 0.08])
    ev.append(['boom', b6['start'] + T(b6, 'arrest') + 0.11, 0.7])
    ev.append(['boom', b7['start'] + T(b7, 'sentences') + 0.11, 0.75])
    for w in ('company', 'gold', 'courier', 'follow'):
        ev.append(['pop', b8['start'] + T(b8, w) - 0.1, 0.2])
    ev.append(['pop', b8['start'] + T(b8, 'call', 0) - 0.1, 0.2])
    return ev


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'info':
        print(json.dumps([{'id': b['id'], 'start': round(b['start'], 2), 'end': round(b['end'], 2)} for b in BEATS]))
        print('total', round(TOTAL, 2), 'groups', len(GROUPS))
    elif mode == 'events':
        ev = events()
        json.dump({'total': TOTAL, 'events': [[a, round(b_, 3), c] for a, b_, c in ev]}, open(sys.argv[2], 'w'), indent=1)
        print(len(ev), 'events')
    elif mode == 'stills':
        init()
        out = sys.argv[2]; os.makedirs(out, exist_ok=True)
        times = [float(x) for x in sys.argv[3].split(',')] if len(sys.argv) > 3 else None
        if times is None:
            times = [b['start'] + (b['end'] - b['start']) * fr for b in BEATS for fr in (0.2, 0.55, 0.92)]
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
