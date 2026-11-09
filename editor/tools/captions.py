"""Word-by-word captions: build the .ass file from words.json and burn it into a video with ffmpeg/libass.

  python editor/tools/captions.py <video> --words words.json [--out captioned.mp4] [--preset reel] [--hook "text"]
  python editor/tools/captions.py --words words.json --ass-only captions.ass [--preset reel]
  python editor/tools/captions.py <video> --words words.json --guides --out check.mp4   (draws the safe zones)

The look comes from editor/account.json ("captions", "hook", "presets"), with one video's overrides from
work/<name>/edit.json when edit.py runs it:
- DM Sans ExtraBold, white with a navy outline; the word being spoken turns neon green (#31ED31).
- At most max_words_per_line words per line and max_lines lines. Line width is measured with the real
  font file from editor/fonts, so a line is never wider than the preset's max_width (820 px on a reel).
- Centred on caption_y (1440 on a 1080x1920 reel) at caption_x (510, left of centre), so the right edge
  stays clear of TikTok's buttons (x > 940 below y 1000).
- Optional hook title for the first seconds, inside the graphics zone (y 230 to 1300). Wrap words in
  *stars* to set them in Instrument Serif italic, gold: --hook "What does *par* mean?"

On-screen text follows the account's rules: no em dashes (refused in a hook, removed from captions), and the
hook is checked for AI-melody phrases. Captions are what was said, so spelling fixes go in
account.json "fixes" (e.g. "youtube": "YouTube").
"""
from __future__ import annotations

import argparse
import math
import re
import struct
import sys
from functools import lru_cache
from pathlib import Path

import core

EM_DASHES = ("—", "–", "―")
WEAK = {"a", "an", "the", "to", "of", "in", "into", "on", "at", "for", "with", "and", "or", "but", "your", "my", "our",
        "their", "his", "her", "its", "is", "are", "was", "be", "that", "this", "from", "by", "as", "if", "so", "you", "i"}
MELODY = ["here's the thing", "it's not just", "not just", "what most people don't realize", "picture this",
          "delve", "nuance", "quietly", "landscape", "carries weight", "let's dive", "game-changer", "unlock"]


# ---------------------------------------------------------------- fonts and measuring

def ttf_metrics(path: Path) -> tuple[int, int, int]:
    """(unitsPerEm, usWinAscent, usWinDescent): libass sizes text so winAscent+winDescent = font size."""
    data = Path(path).read_bytes()
    num = struct.unpack(">H", data[4:6])[0]
    tables = {}
    for i in range(num):
        tag, _cs, off, _ln = struct.unpack(">4sIII", data[12 + 16 * i: 28 + 16 * i])
        tables[tag.decode("latin-1")] = off
    upem = struct.unpack(">H", data[tables["head"] + 18: tables["head"] + 20])[0]
    o = tables["OS/2"]
    wa, wd = struct.unpack(">HH", data[o + 74: o + 78])
    return upem, wa, wd


@lru_cache(maxsize=None)
def font_index() -> dict:
    """Maps lower-case names ('dm sans extrabold', 'dm sans|bold', ...) to font files in editor/fonts."""
    idx = {}
    try:
        from PIL import ImageFont
    except ImportError:
        return idx
    for f in sorted(core.FONTS.glob("*.[ot]tf")):
        try:
            fam, style = ImageFont.truetype(str(f), 20).getname()
        except OSError:
            continue
        fam, style = (fam or "").lower(), (style or "regular").lower()
        idx.setdefault(f"{fam} {style}", f)
        idx.setdefault(f"{fam}|{style}", f)
        if style == "regular":
            idx.setdefault(fam, f)
    return idx


def find_font(name: str, bold=False, italic=False) -> Path | None:
    idx = font_index()
    n = name.lower()
    style = {(True, True): "bold italic", (True, False): "bold", (False, True): "italic"}.get((bold, italic), "regular")
    return idx.get(f"{n}|{style}") or idx.get(n) or idx.get(f"{n} {style}") or idx.get(f"{n}|bold")


class Measure:
    """Width in output pixels of text set in an ASS font at an ASS size (matches libass within ~1%)."""

    def __init__(self, font: str, size: float, bold=False, italic=False):
        self.size = size
        self.file = find_font(font, bold, italic)
        self.font = None
        if self.file:
            from PIL import ImageFont
            upem, wa, wd = ttf_metrics(self.file)
            self.em = size * upem / (wa + wd)
            self.font = ImageFont.truetype(str(self.file), max(1, int(round(self.em))))
        else:
            self.em = size * 0.75

    def width(self, text: str) -> float:
        if self.font is not None:
            return float(self.font.getlength(text))
        return 0.56 * self.em * len(text)


# ---------------------------------------------------------------- layout

def layout_for(settings: dict, preset: str) -> dict:
    p = settings["presets"][preset]
    s = dict(p["safe"])
    scale = p.get("caption_scale", 1.0)
    cap = dict(settings["captions"])
    cap["size"] = cap["size"] * scale
    hook = dict(settings.get("hook", {}))
    hook["size"] = hook.get("size", 100) * scale
    hook["y"] = p.get("hook_y", hook.get("y", 560))
    return {"preset": preset, "width": p["width"], "height": p["height"], "safe": s, "cap": cap, "hook": hook}


def clean_word(w: str, cap: dict) -> str:
    t = w.strip()
    for d in EM_DASHES:
        t = t.replace(d, " ")
    t = t.replace("{", "(").replace("}", ")").replace("\\", "/")
    if cap.get("punctuation", "drop") == "drop":
        t = re.sub(r"[.,;:]+$", "", t)
    if cap.get("uppercase"):
        t = t.upper()
    return t.strip()


def wrap(tokens: list[str], measure: Measure, max_w: float, max_words: int, max_lines: int = 2) -> list[list[int]] | None:
    """Split one page's words into lines: one line if it fits, else the most even split. None if it can't fit."""
    n = len(tokens)
    width = lambda a, b: measure.width(" ".join(tokens[a:b]))
    if n <= max_words and width(0, n) <= max_w:
        return [list(range(n))]
    if max_lines < 2:
        return None
    best = None
    for i in range(1, n):
        if i > max_words or n - i > max_words:
            continue
        w1, w2 = width(0, i), width(i, n)
        if w1 <= max_w and w2 <= max_w:
            score = max(w1, w2) + (40 if core.norm_word(tokens[i - 1]) in WEAK else 0)
            if best is None or score < best[0]:
                best = (score, i)
    if best is None:
        return None
    return [list(range(best[1])), list(range(best[1], n))]


def paginate(words: list[dict], lay: dict, measure: Measure) -> list[dict]:
    """Group words into caption pages: phrases first (punctuation, pauses), then each phrase into the
    fewest pages that fit, split evenly so no page is left with one stray word."""
    cap = lay["cap"]
    max_w = lay["safe"]["max_width"] - 2 * cap.get("outline", 0)
    mwpl, mlines = int(cap.get("max_words_per_line", 3)), int(cap.get("max_lines", 2))
    max_secs = float(cap.get("max_page_seconds", 2.6))
    phrases, cur = [], []
    for w in words:
        if cur:
            prev = cur[-1]
            if (re.search(r"[.?!,;:]$", prev["word"].strip()) or w["start"] - prev["end"] >= cap.get("break_on_pause", 0.35)):
                phrases.append(cur)
                cur = []
        cur.append(w)
    if cur:
        phrases.append(cur)
    pages = []
    for ph in phrases:
        n = len(ph)
        k = max(1, -(-n // (mwpl * mlines)))
        while True:
            # even chunk sizes, then nudge each boundary off a weak word ("the", "into") when there's room
            sizes = [n // k + (1 if i < n % k else 0) for i in range(k)]
            bounds = [sum(sizes[:i + 1]) for i in range(k - 1)]
            for j, b in enumerate(bounds):
                lo = bounds[j - 1] if j else 0
                hi = bounds[j + 1] if j + 1 < len(bounds) else n
                if core.norm_word(ph[b - 1]["word"]) in WEAK and hi - b < mwpl * mlines and b - 1 - lo >= 2:
                    bounds[j] = b - 1
            edges = [0] + bounds + [n]
            chunks = [ph[a:b] for a, b in zip(edges, edges[1:])]
            lines = [wrap([w["text"] for w in c], measure, max_w, mwpl, mlines) for c in chunks]
            too_long = any(c[-1]["end"] - c[0]["start"] > max_secs and len(c) > 1 for c in chunks)
            if all(lines) and not too_long or k >= n:
                break
            k += 1
        for c, ln in zip(chunks, lines):
            pages.append({"words": c, "lines": ln or [list(range(len(c)))]})
    return pages


def _page_text(page: dict, active: int | None, base: str, hl: str) -> str:
    rows = []
    for line in page["lines"]:
        parts = []
        for i in line:
            t = page["words"][i]["text"]
            parts.append(f"{{\\c{hl}}}{t}{{\\c{base}}}" if i == active else t)
        rows.append(" ".join(parts))
    return "\\N".join(rows)


def hook_markup(text: str, lay: dict) -> tuple[str, float]:
    """ASS text for the hook (stars mark accent words) and its widest line in px."""
    h = lay["hook"]
    main_m = Measure(h["font"], h["size"])
    acc_size = h["size"] * h.get("accent_scale", 1.2)
    acc_m = Measure(h["accent_font"], acc_size, italic=True)
    tokens, accent = [], False
    for part in re.split(r"(\*)", text):
        if part == "*":
            accent = not accent
            continue
        for w in part.split():
            tokens.append((w, accent))
    max_w = lay["safe"]["max_width"] - 2 * h.get("outline", 0)
    lines, cur, cur_w = [], [], 0.0
    space = main_m.width(" ")
    for w, acc in tokens:
        ww = (acc_m if acc else main_m).width(w)
        add = ww + (space if cur else 0)
        if cur and cur_w + add > max_w:
            lines.append((cur, cur_w))
            cur, cur_w = [], 0.0
            add = ww
        cur.append((w, acc))
        cur_w += add
    if cur:
        lines.append((cur, cur_w))
    acc_c, base_c = core.ass_inline(h["accent_color"]), core.ass_inline(h["color"])
    rows = []
    for ln, _w in lines:
        bits = []
        for w, acc in ln:
            w = w.replace("{", "(").replace("}", ")")
            if acc:
                bits.append(f"{{\\fn{h['accent_font']}\\i1\\fs{acc_size:.0f}\\c{acc_c}}}{w}{{\\fn{h['font']}\\i0\\fs{h['size']:.0f}\\c{base_c}}}")
            else:
                bits.append(w)
        rows.append(" ".join(bits))
    widest = max((w for _l, w in lines), default=0.0)
    return "\\N".join(rows), widest


def lint_on_screen(text: str, strict=True) -> list[str]:
    """On-screen text rules: no em dashes, no AI-melody phrases."""
    issues = []
    if any(d in text for d in EM_DASHES):
        issues.append("has an em or en dash (rule: none on screen)")
    low = text.lower()
    for p in MELODY:
        if re.search(r"\b" + re.escape(p) + r"\b", low):
            issues.append(f"AI-melody phrase: '{p}'")
    return issues


def guide_events(lay: dict) -> list[str]:
    """Outlines of the safe zones, for review frames only."""
    W, H, s = lay["width"], lay["height"], lay["safe"]
    cx, cy, mw = s["caption_x"], s["caption_y"], s["max_width"]

    def rect(x0, y0, x1, y1, color, fill_alpha="FF", label=""):
        ev = (f"Dialogue: 9,0:00:00.00,9:00:00.00,Guide,,0,0,0,,{{\\an7\\pos(0,0)\\p1\\bord3\\shad0\\1a&H{fill_alpha}&"
              f"\\3c{core.ass_inline(color)}\\1c{core.ass_inline(color)}}}m {x0} {y0} l {x1} {y0} l {x1} {y1} l {x0} {y1}{{\\p0}}")
        lab = (f"Dialogue: 9,0:00:00.00,9:00:00.00,Guide,,0,0,0,,{{\\an7\\pos({x0 + 8},{y0 + 6})\\fs28\\bord2\\c{core.ass_inline(color)}}}{label}")
        return [ev, lab] if label else [ev]

    ev = rect(0, s["graphics_top"], W, s["graphics_bottom"], "#FFD700", label="graphics zone")
    ev += rect(cx - mw // 2, cy - 130, cx + mw // 2, cy + 130, "#00E5FF", label="captions")
    if s["right_clear_x"] < W:
        ev += rect(s["right_clear_x"], s["right_clear_below_y"], W, H, "#FF3030", fill_alpha="B0", label="buttons")
    return ev


def build_ass(words: list[dict], settings: dict, preset: str = "reel", hook_text: str | None = None,
              guides: bool = False) -> tuple[str, dict]:
    """The .ass file text and a report (pages, widest line, right edge, warnings)."""
    lay = layout_for(settings, preset)
    cap, s, hook = lay["cap"], lay["safe"], lay["hook"]
    measure = Measure(cap["font"], cap["size"], bold=cap.get("bold", False))
    warnings = []
    if measure.file is None:
        warnings.append(f"font '{cap['font']}' is not in editor/fonts; libass will substitute another font")
    ws = []
    for w in core.apply_fixes(words, settings.get("fixes")):
        t = clean_word(w["word"], cap)
        if t:
            ws.append(dict(w, text=t))
    pages = paginate(ws, lay, measure) if cap.get("enabled", True) else []

    base, hl = core.ass_inline(cap["color"]), core.ass_inline(cap["highlight"])
    style = lambda name, font, size, prim, outc, outl, shad, bold=0, italic=0, align=5: (
        f"Style: {name},{font},{size:.0f},{prim},{prim},{outc},{core.ass_color(cap.get('shadow_color', '#000000'), 0x60)},"
        f"{bold},{italic},0,0,100,100,0,0,1,{outl},{shad},{align},0,0,0,1")
    head = [
        "[Script Info]", "; made by editor/tools/captions.py from words.json and editor/account.json",
        "ScriptType: v4.00+", f"PlayResX: {lay['width']}", f"PlayResY: {lay['height']}", "WrapStyle: 2",
        "ScaledBorderAndShadow: yes", "YCbCr Matrix: TV.709", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style("Caption", cap["font"], cap["size"], core.ass_color(cap["color"]), core.ass_color(cap["outline_color"]), cap["outline"], cap["shadow"],
              bold=-1 if cap.get("bold") else 0),
        style("Hook", hook.get("font", cap["font"]), hook.get("size", 100), core.ass_color(hook.get("color", "#FFFFFF")),
              core.ass_color(hook.get("outline_color", "#050833")), hook.get("outline", 8), hook.get("shadow", 4)),
        style("Guide", "DM Sans Bold", 28, "&H00FFFFFF", "&H00000000", 2, 0, align=7),
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = []
    cx, cy = s["caption_x"], s["caption_y"]
    widest = 0.0
    for k, pg in enumerate(pages):
        pw = [w for w in pg["words"]]
        nxt = pages[k + 1]["words"][0]["start"] if k + 1 < len(pages) else math.inf
        p_end = pw[-1]["end"] + 0.3
        if nxt - pw[-1]["end"] < 0.6:
            p_end = nxt
        p_end = min(p_end, nxt)
        for line in pg["lines"]:
            widest = max(widest, measure.width(" ".join(pw[i]["text"] for i in line)))
        for i, w in enumerate(pw):
            t0 = w["start"] if i else pw[0]["start"]
            t1 = pw[i + 1]["start"] if i + 1 < len(pw) else p_end
            if round(t1, 2) <= round(t0, 2):
                continue
            events.append(f"Dialogue: 1,{core.ts_ass(t0)},{core.ts_ass(t1)},Caption,,0,0,0,,{{\\an5\\pos({cx},{cy})}}"
                          + _page_text(pg, i, base, hl))
    hook_info = None
    if hook_text and hook.get("enabled", True):
        bad = lint_on_screen(hook_text)
        if any("dash" in b for b in bad):
            raise core.ToolError(f"Hook text {hook_text!r}: {'; '.join(bad)}. Rewrite it.")
        warnings += [f"hook: {b}" for b in bad]
        txt, hw = hook_markup(hook_text, lay)
        hx = lay["width"] // 2
        dur = float(hook.get("seconds", 3.0))
        events.insert(0, f"Dialogue: 2,{core.ts_ass(0)},{core.ts_ass(dur)},Hook,,0,0,0,,"
                         f"{{\\an5\\pos({hx},{hook['y']})\\fad(120,250)\\fscx88\\fscy88\\t(0,260,0.5,\\fscx100\\fscy100)}}{txt}")
        hook_info = {"text": hook_text, "size": round(hook["size"]), "y": hook["y"], "width_px": round(hw), "seconds": dur}
        if hook["y"] < s["graphics_top"] or hook["y"] > s["graphics_bottom"]:
            warnings.append(f"hook y {hook['y']} is outside the graphics zone {s['graphics_top']}-{s['graphics_bottom']}")
    if guides:
        events += guide_events(lay)
    right = cx + widest / 2 + cap["outline"]
    if right > s["right_clear_x"] and s["right_clear_below_y"] < cy:
        warnings.append(f"caption right edge {right:.0f} px crosses the button area (x > {s['right_clear_x']})")
    report = {"preset": preset, "pages": len(pages), "words": len(ws), "font_file": str(measure.file) if measure.file else None,
              "size": round(cap["size"]), "widest_line_px": round(widest), "max_width": s["max_width"],
              "right_edge_px": round(right), "caption_y": cy, "hook": hook_info, "warnings": warnings}
    return "\n".join(head + events) + "\n", report


# ---------------------------------------------------------------- srt / vtt

def subtitle_blocks(words: list[dict], max_words=9, max_secs=3.5, max_chars=50) -> list[tuple[float, float, str]]:
    blocks, cur = [], []
    for w in words:
        if cur:
            text = " ".join(x["word"].strip() for x in cur + [w])
            if (re.search(r"[.?!]$", cur[-1]["word"].strip()) or w["start"] - cur[-1]["end"] > 0.6
                    or len(cur) >= max_words or w["end"] - cur[0]["start"] > max_secs or len(text) > max_chars):
                blocks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        blocks.append(cur)
    out = []
    for i, b in enumerate(blocks):
        end = b[-1]["end"] + 0.2
        if i + 1 < len(blocks):
            end = min(end, blocks[i + 1][0]["start"])
        text = " ".join(x["word"].strip() for x in b)
        for d in EM_DASHES:
            text = text.replace(d, ", ")
        out.append((b[0]["start"], max(end, b[-1]["end"]), text))
    return out


def write_srt(words, path, fixes=None):
    blocks = subtitle_blocks(core.apply_fixes(words, fixes))
    with open(path, "w", encoding="utf-8") as f:
        for i, (a, b, t) in enumerate(blocks, 1):
            f.write(f"{i}\n{core.ts_srt(a)} --> {core.ts_srt(b)}\n{t}\n\n")
    return Path(path)


def write_vtt(words, path, fixes=None):
    blocks = subtitle_blocks(core.apply_fixes(words, fixes))
    with open(path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for a, b, t in blocks:
            f.write(f"{core.ts_vtt(a)} --> {core.ts_vtt(b)}\n{t}\n\n")
    return Path(path)


def write_ass(words, path, settings, preset="reel", hook_text=None, guides=False) -> dict:
    text, report = build_ass(words, settings, preset, hook_text, guides)
    Path(path).write_text(text, encoding="utf-8")
    return report


def ass_filter(ass_path: Path) -> str:
    return f"ass=filename={core.ff_escape(Path(ass_path))}:fontsdir={core.ff_escape(core.FONTS)}"


def burn(video, ass_path, out, crf=18, x264_preset="medium"):
    out = core.guard_output(Path(out))
    core.ffmpeg(["-y", "-v", "error", "-i", str(video), "-vf", ass_filter(ass_path) + ",format=yuv420p",
                 "-c:v", "libx264", "-preset", x264_preset, "-crf", str(crf), "-c:a", "copy",
                 "-movflags", "+faststart", str(out)])
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video", nargs="?", help="video to caption (omit with --ass-only)")
    p.add_argument("--words", required=True, help="words.json from transcribe.py or cut.py")
    p.add_argument("--out", help="output video (default: <video>-captions.mp4 next to it)")
    p.add_argument("--ass-only", help="only write the .ass file to this path")
    p.add_argument("--preset", help="reel, youtube or square (default from account.json)")
    p.add_argument("--hook", help="hook title for the first seconds; *stars* mark accent words")
    p.add_argument("--guides", action="store_true", help="draw the safe zones (for checking only)")
    p.add_argument("--account", help="account.json to use")
    p.add_argument("--settings", help="per-video overrides (work/<name>/edit.json)")
    p.add_argument("--crf", type=int, default=16)
    a = p.parse_args(argv)
    try:
        settings = core.settings_for(core.load_account(a.account), core.read_json(a.settings, {}) if a.settings else {})
        preset = a.preset or settings["export"]["preset"]
        words = core.load_words(a.words)
        hook = a.hook if a.hook is not None else settings.get("hook", {}).get("text") or None
        if a.ass_only:
            rep = write_ass(words, a.ass_only, settings, preset, hook, a.guides)
        else:
            if not a.video:
                p.error("give a video, or --ass-only")
            v = Path(a.video)
            out = Path(a.out) if a.out else v.with_name(v.stem + "-captions.mp4")
            ass = out.with_suffix(".ass")
            rep = write_ass(words, ass, settings, preset, hook, a.guides)
            burn(v, ass, out, a.crf, settings["export"].get("x264_preset", "medium"))
            print("captioned video:", out)
        print(f"{rep['pages']} caption pages, widest line {rep['widest_line_px']} px of {rep['max_width']}, right edge {rep['right_edge_px']} px")
        for w in rep["warnings"]:
            print("WARNING:", w)
        return 0
    except core.ToolError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
