"""Cut the pauses (and optionally "um"/"uh" and false starts) out of a talking video.

  python editor/tools/cut.py <video> [--words words.json] [--out cut.mp4] [--min-pause 0.45] [--pad 0.12]
  python editor/tools/cut.py <video> --plan-only          only write the edit list, render nothing

How it decides (all numbers come from editor/account.json "cut", overridable here):
1. Pauses: the audio is measured in 10 ms steps. A stretch quieter than the threshold (auto: 10 dB over
   the room noise, at least 35 dB under the voice) that lasts longer than min_pause (0.45 s) is a pause.
   Whisper gaps longer than min_pause + 0.25 s also count (catches breaths and noisy rooms).
   Each pause is cut down to pad (0.12 s) on each side, so word ends and starts are never clipped.
2. Word guard: if a Whisper word sits inside a "pause" (a quiet or whispered word), that word and its
   padding are kept.
3. Fillers (--fillers): words like um, uh, erm are removed. "Like" and "you know" are never touched.
4. Retakes (--retakes): when a phrase is restarted (the same first 3+ words again, and most of the first
   attempt repeated), the earlier attempt is removed and the last take is kept. Every removal is listed
   with its text so a wrong one is easy to put back with --keep START-END.
5. Lead-in and tail: silence before the first word is trimmed to lead_in (0.15 s), after the last to tail.
Without words.json it falls back to the audio measurement alone (same idea as ffmpeg silencedetect).

Outputs (default work/<name>/cut/):
  edl.json     the edit list: kept ranges, every removal with reason, text and seconds, and a summary
  cut.mp4      re-encoded (not stream-copied) so audio and picture stay in sync; segment edges are
               snapped to the frame grid and get 6 ms audio fades so joins don't click
  cut.wav      the cut audio, for music.py
  words.json   the words re-timed to the cut, for captions

Scaling: --preset reel (default from account.json) scales and crops to 1080x1920 at 30 fps; iPhone HDR
footage is tone-mapped to normal video so it doesn't look washed out. --preset none keeps the size.
The raw file is only read, never changed.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import core


# ---------------------------------------------------------------- interval helpers

def union(iv):
    out = []
    for s, e, *rest in sorted(iv, key=lambda x: x[0]):
        if out and s <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], e)
            if rest:
                out[-1][2] |= set(rest[0])
        else:
            out.append([s, e, set(rest[0]) if rest else set()])
    return out


def subtract(iv, cut):
    """Remove the ranges in cut from each (s, e, reasons) in iv."""
    res = list(iv)
    for cs, ce in cut:
        nxt = []
        for s, e, r in res:
            if ce <= s or cs >= e:
                nxt.append([s, e, r])
                continue
            if cs > s:
                nxt.append([s, cs, r])
            if ce < e:
                nxt.append([ce, e, r])
        res = nxt
    return res


def runs(mask, hop):
    out, start = [], None
    for i, m in enumerate(mask):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append((start * hop, i * hop))
            start = None
    if start is not None:
        out.append((start * hop, len(mask) * hop))
    return out


def parse_range(s: str):
    a, b = s.replace(",", ".").split("-")
    return float(a), float(b)


# ---------------------------------------------------------------- planning

def find_retakes(words, energy_gaps, min_gap=0.3, window=20.0):
    """[(remove_start, remove_end, text, kept_text)]: earlier attempts of a restarted phrase."""
    import re
    phrases, cur = [], []
    for w in words:
        if cur:
            prev = cur[-1]
            gap = w["start"] - prev["end"]
            mid0, mid1 = (prev["start"] + prev["end"]) / 2, (w["start"] + w["end"]) / 2
            if gap >= min_gap or re.search(r"[.?!]$", prev["word"]) or any(
                    s >= mid0 and e <= mid1 + 0.3 and e - s >= min_gap for s, e in energy_gaps):
                phrases.append(cur)
                cur = []
        cur.append(w)
    if cur:
        phrases.append(cur)
    norm = lambda ph: [n for n in (core.norm_word(x["word"]) for x in ph) if n and n not in core.FILLERS]
    found = []
    for i, a in enumerate(phrases):
        na = norm(a)
        if len(na) < 2:
            continue
        for j in (i + 1, i + 2):
            if j >= len(phrases) or phrases[j][0]["start"] - a[0]["start"] > window:
                break
            nb = norm(phrases[j])
            k = 0
            while k < min(len(na), len(nb)) and na[k] == nb[k]:
                k += 1
            if k >= 3 and k >= 0.6 * len(na) and len(na) <= len(nb) + 2:
                gone = [w for p in phrases[i:j] for w in p]
                found.append((a[0]["start"], phrases[j][0]["start"], " ".join(w["word"] for w in gone),
                              " ".join(w["word"] for w in phrases[j][:8])))
                break
    return found


def plan(words, audio, sr, duration, cfg, fps=30.0):
    """Work out what to keep. Returns the edit list (dict)."""
    import numpy as np
    hop = 0.01
    db = core.frame_db(audio, sr, hop)
    speech_lvl = float(np.percentile(db, 95))
    noise_lvl = float(np.percentile(db, 10))
    sdb = cfg.get("silence_db", "auto")
    if sdb in (None, "auto"):
        thr = max(noise_lvl + 10, speech_lvl - 35)
        thr = min(thr, speech_lvl - 15)
    else:
        thr = float(sdb)
    quiet = runs(db < thr, hop)
    min_pause, pad = float(cfg.get("min_pause", 0.45)), float(cfg.get("pad", 0.12))
    lead, tail = float(cfg.get("lead_in", 0.15)), float(cfg.get("tail", 0.4))
    removals = []  # [s, e, {reason}]
    texts = []     # (s, e, reason, text) for the report

    # 1. pauses from the audio
    pauses = []
    for s, e in quiet:
        if s <= 0.001:
            if e - lead > 0.05:
                pauses.append((0.0, e - lead, "lead-in"))
        elif e >= duration - 0.011:
            if duration - (s + tail) > 0.05:
                pauses.append((s + tail, duration, "tail"))
        elif e - s >= min_pause:
            pauses.append((s + pad, e - pad, "pause"))
    # Whisper gaps the meter missed (breaths, room noise)
    for a, b in zip(words, words[1:]):
        g0, g1 = a["end"], b["start"]
        if g1 - g0 >= min_pause + 0.25:
            covered = sum(max(0, min(e, g1) - max(s, g0)) for s, e, _ in pauses)
            if covered < 0.5 * (g1 - g0):
                pauses.append((g0 + pad + 0.05, g1 - pad - 0.05, "pause"))
    if words:
        first, last = words[0]["start"], words[-1]["end"]
        if not any(r == "lead-in" for *_x, r in pauses) and first - lead > 0.3:
            pauses.append((0.0, first - lead - 0.1, "lead-in"))
        if not any(r == "tail" for *_x, r in pauses) and duration - last - tail > 0.3:
            pauses.append((last + tail + 0.1, duration, "tail"))

    # 2. word guard: keep any word that sits mostly inside a pause and has some sound there
    #    (a quiet or whispered word). Whisper often stretches a word over the silence before it;
    #    those spans have no sound in the pause, so they don't block the cut.
    faint = db > noise_lvl + 4
    protect = []
    for w in words:
        d = w["end"] - w["start"]
        if d < 0.08:
            continue
        for s, e, _r in pauses:
            o0, o1 = max(s, w["start"]), min(e, w["end"])
            if o1 - o0 >= 0.7 * d and faint[int(o0 / hop):int(o1 / hop) + 1].sum() * hop >= 0.06:
                protect.append((w["start"] - pad, w["end"] + pad))
                break
    guarded = subtract([[s, e, {r}] for s, e, r in pauses if e > s], protect)
    removals += [g for g in guarded if g[1] - g[0] > 0.04]

    # 3. fillers
    dropped_words = set()
    if cfg.get("fillers", True):
        loud = db > thr
        for i, w in enumerate(words):
            if core.norm_word(w["word"]) in core.FILLERS:
                # Whisper's times for "um" are often short: widen to the whole sound (where the level
                # drops under the pause threshold), but never into the neighbouring words
                lo = (words[i - 1]["end"] + 0.02) if i else 0.0
                hi = (words[i + 1]["start"] - 0.02) if i + 1 < len(words) else duration
                c = int(((w["start"] + w["end"]) / 2) / hop)
                a = c
                while a > 0 and loud[a - 1] and (a - 1) * hop > max(lo, w["start"] - 0.6):
                    a -= 1
                b = c
                while b < len(loud) - 1 and loud[b + 1] and (b + 1) * hop < min(hi, w["end"] + 0.6):
                    b += 1
                s = max(min(a * hop, w["start"]) - 0.01, lo)
                e = min(max((b + 1) * hop, w["end"]) + 0.01, hi)
                if e > s:
                    removals.append([s, e, {"filler"}])
                    texts.append((s, e, "filler", w["word"]))
                    dropped_words.add(i)

    # 4. retakes
    if cfg.get("retakes", True) and words:
        gaps = [(s, e) for s, e in quiet]
        for s, e, text, kept in find_retakes(words, gaps):
            # start where the false start's sound begins, end just before the good take begins
            onset = max([qe for qs, qe in quiet if qe <= s + 0.1] or [s])
            s2 = max(onset - pad, 0.0) if s - onset < 0.4 else s - 0.03
            onset2 = max([qe for qs, qe in quiet if qe <= e + 0.1] or [e])
            e2 = (onset2 - pad) if e - onset2 < 0.4 else e - pad
            if e2 > s2:
                removals.append([s2, e2, {"retake"}])
                texts.append((s2, e2, "retake", f"{text}  (kept the later take: {kept} ...)"))
                for i, w in enumerate(words):
                    if s2 <= (w["start"] + w["end"]) / 2 <= e2:
                        dropped_words.add(i)

    # 5. manual ranges
    for s, e in cfg.get("force_remove", []) or []:
        removals.append([float(s), float(e), {"manual"}])
        texts.append((float(s), float(e), "manual", ""))
        for i, w in enumerate(words):
            if s <= (w["start"] + w["end"]) / 2 <= e:
                dropped_words.add(i)
    merged = union([(max(0.0, s), min(duration, e), r) for s, e, r in removals if e > s])
    force_keep = [(float(s), float(e)) for s, e in (cfg.get("force_keep") or [])]
    merged = subtract(merged, force_keep)
    if force_keep:
        dropped_words = {i for i in dropped_words
                         if not any(s <= (words[i]["start"] + words[i]["end"]) / 2 <= e for s, e in force_keep)}

    # keep = complement, snapped outward to the frame grid
    import math
    keep, t = [], 0.0
    for s, e, _r in merged:
        if s > t:
            keep.append([t, s])
        t = max(t, e)
    if t < duration:
        keep.append([t, duration])
    snapped = []
    for s, e in keep:
        s2, e2 = math.floor(s * fps + 1e-6) / fps, min(math.ceil(e * fps - 1e-6) / fps, duration)
        if snapped and s2 <= snapped[-1][1]:
            snapped[-1][1] = max(snapped[-1][1], e2)
        elif e2 - s2 >= 2 / fps or any(s2 <= (w["start"] + w["end"]) / 2 <= e2 for w in words):
            snapped.append([s2, e2])
    out_t = 0.0
    keeps = []
    for s, e in snapped:
        keeps.append({"start": round(s, 4), "end": round(e, 4), "out_start": round(out_t, 4)})
        out_t += e - s

    # removal report (from the final keep list, so it matches the render exactly)
    removed, t = [], 0.0
    for k in keeps + [{"start": duration, "end": duration}]:
        if k["start"] - t > 1e-3:
            reasons = set()
            for s, e, r in merged:
                if min(e, k["start"]) - max(s, t) > 1e-3:
                    reasons |= r
            text = "; ".join(x[3] for x in texts if min(x[1], k["start"]) - max(x[0], t) > 1e-3 and x[3])
            removed.append({"start": round(t, 3), "end": round(k["start"], 3), "seconds": round(k["start"] - t, 3),
                            "reason": "+".join(sorted(reasons)) or "edge", "text": text})
        t = k["end"]
    count = lambda r: sum(1 for x in removed if r in x["reason"])
    secs = lambda r: round(sum(x["seconds"] for x in removed if r in x["reason"]), 2)
    summary = {
        "before_s": round(duration, 2), "after_s": round(out_t, 2), "removed_s": round(duration - out_t, 2),
        "removed_pct": round(100 * (duration - out_t) / duration, 1) if duration else 0,
        "pauses": count("pause"), "pause_s": secs("pause"), "fillers": count("filler"), "retakes": count("retake"),
        "retake_s": secs("retake"), "lead_in_s": secs("lead-in"), "tail_s": secs("tail"), "manual": count("manual"),
        "segments": len(keeps), "words_kept": len(words) - len(dropped_words), "words_dropped": len(dropped_words),
    }
    # safety: a word that should stay but has no audio left in the cut
    lost = [w["word"] for i, w in enumerate(words) if i not in dropped_words
            and not any(min(k["end"], w["end"]) - max(k["start"], w["start"]) > 0.03 for k in keeps)]
    summary["words_lost"] = len(lost)
    if lost:
        summary["lost_words"] = lost
    return {
        "tool": "editor/tools/cut.py", "created": core.now(), "fps_grid": fps,
        "settings": {"min_pause": min_pause, "pad": pad, "lead_in": lead, "tail": tail,
                     "fillers": bool(cfg.get("fillers", True)), "retakes": bool(cfg.get("retakes", True)),
                     "silence_db": sdb, "force_keep": cfg.get("force_keep") or [], "force_remove": cfg.get("force_remove") or []},
        "measured": {"threshold_db": round(thr, 1), "speech_db": round(speech_lvl, 1), "noise_db": round(noise_lvl, 1),
                     "used_words": bool(words)},
        "summary": summary, "keep": keeps, "removed": removed,
        "dropped_words": sorted(dropped_words),
    }


def retime(words, edl):
    """Words moved onto the cut's timeline (dropped fillers/retakes left out)."""
    keeps, drop = edl["keep"], set(edl.get("dropped_words", []))
    out = []
    for i, w in enumerate(words):
        if i in drop:
            continue
        # the kept range that holds most of the word (Whisper may stretch a word into a cut pause)
        ov = [(min(k["end"], w["end"]) - max(k["start"], w["start"]), k) for k in keeps]
        best, k = max(ov, key=lambda x: x[0], default=(0, None))
        if k is None or best <= 0:
            continue
        s = max(w["start"], k["start"]) - k["start"] + k["out_start"]
        e = min(w["end"], k["end"]) - k["start"] + k["out_start"]
        out.append(dict(w, start=round(s, 3), end=round(max(e, s + 0.04), 3), src_start=w["start"]))
    return out


def compare_words(expected, heard):
    """How many expected words Whisper hears again in the cut, and how far their times moved.

    expected: the words the cut should contain (cut/words.json); heard: a fresh transcript of the cut.
    A word heard slightly differently ("an" as "and") counts as kept but is listed under "changed".
    """
    import difflib
    e = [core.norm_word(w["word"]) for w in expected]
    o = [core.norm_word(w["word"]) for w in heard]
    sm = difflib.SequenceMatcher(a=e, b=o, autojunk=False)
    pairs, changed = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            pairs += [(i1 + k, j1 + k) for k in range(i2 - i1)]
        elif tag == "replace" and i2 - i1 == j2 - j1:
            for k in range(i2 - i1):
                a, b = e[i1 + k], o[j1 + k]
                if difflib.SequenceMatcher(a=a, b=b).ratio() >= 0.6 or a.startswith(b) or b.startswith(a):
                    pairs.append((i1 + k, j1 + k))
                    changed.append({"word": expected[i1 + k]["word"], "heard": heard[j1 + k]["word"], "t": expected[i1 + k]["start"]})
    got, used = {i for i, _ in pairs}, {j for _, j in pairs}
    diffs = sorted(abs(heard[j]["start"] - expected[i]["start"]) for i, j in pairs)
    pct = lambda q: round(diffs[min(len(diffs) - 1, int(q * len(diffs)))], 3) if diffs else None
    return {
        "expected": len(e), "heard": len(o), "matched": len(pairs),
        "kept_pct": round(100 * len(pairs) / len(e), 1) if e else 100.0,
        "missing": [{"word": expected[i]["word"], "t": expected[i]["start"]} for i in range(len(e)) if i not in got],
        "changed": changed,
        "extra": [{"word": heard[j]["word"], "t": heard[j]["start"]} for j in range(len(o)) if j not in used],
        "start_diff_median_s": pct(0.5), "start_diff_p90_s": pct(0.9), "start_diff_max_s": round(diffs[-1], 3) if diffs else None,
    }


# ---------------------------------------------------------------- rendering

HDR_CHAIN = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
             "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")


def video_chain(info: dict, preset: dict | None, fps: float, fit: str = "crop") -> str:
    chain = HDR_CHAIN if info.get("hdr") else ""
    chain += f"fps={fps:g},"
    if preset:
        W, H = preset["width"], preset["height"]
        if fit == "pad":
            chain += (f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
                      f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x050833,")
        else:
            chain += f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
    return chain + "setsar=1,format=yuv420p"


def render(src, edl, out_mp4, out_wav=None, preset=None, fit="crop", crf=16, x264_preset="veryfast", work=None):
    info = core.probe(src)
    if not info["has_video"] or not info["has_audio"]:
        raise core.ToolError(f"{src} needs both picture and sound (has video: {info['has_video']}, audio: {info['has_audio']}).")
    keeps = edl["keep"]
    n = len(keeps)
    fps = edl.get("fps_grid", 30)
    lines = [f"[0:v]split={n}" + "".join(f"[v{i}]" for i in range(n)) + ";",
             f"[0:a]asplit={n}" + "".join(f"[a{i}]" for i in range(n)) + ";"]
    for i, k in enumerate(keeps):
        d = k["end"] - k["start"]
        f = min(0.006, d / 4)
        lines.append(f"[v{i}]trim=start={k['start']:.4f}:end={k['end']:.4f},setpts=PTS-STARTPTS[w{i}];")
        lines.append(f"[a{i}]atrim=start={k['start']:.4f}:end={k['end']:.4f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={f:.4f},afade=t=out:st={d - f:.4f}:d={f:.4f}[b{i}];")
    lines.append("".join(f"[w{i}][b{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac];")
    lines.append(f"[vc]{video_chain(info, preset, fps, fit)}[vout];")
    lines.append("[ac]aresample=48000,asplit=2[aout][awav]" if out_wav else "[ac]aresample=48000[aout]")
    work = Path(work or Path(out_mp4).parent)
    script = work / "cut.filter.txt"
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args = ["-y", "-v", "error", "-i", str(src), *core.filter_script_args(script),
            "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", x264_preset, "-crf", str(crf),
            "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out_mp4)]
    if out_wav:
        args += ["-map", "[awav]", "-c:a", "pcm_s16le", str(out_wav)]
    core.ffmpeg(args)
    return Path(out_mp4)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video")
    p.add_argument("--words", help="words.json from transcribe.py (default work/<name>/transcript/words.json)")
    p.add_argument("--out", help="output folder (default work/<name>/cut)")
    p.add_argument("--min-pause", type=float)
    p.add_argument("--pad", type=float)
    p.add_argument("--silence-db", help="'auto' or a level like -40")
    p.add_argument("--fillers", dest="fillers", action="store_true", default=None)
    p.add_argument("--no-fillers", dest="fillers", action="store_false")
    p.add_argument("--retakes", dest="retakes", action="store_true", default=None)
    p.add_argument("--no-retakes", dest="retakes", action="store_false")
    p.add_argument("--keep", action="append", default=[], metavar="START-END", help="always keep this source range (seconds)")
    p.add_argument("--remove", action="append", default=[], metavar="START-END", help="always remove this source range")
    p.add_argument("--preset", help="reel, youtube, square, or none (default from account.json)")
    p.add_argument("--plan-only", action="store_true", help="write edl.json only")
    p.add_argument("--account")
    p.add_argument("--media")
    a = p.parse_args(argv)
    try:
        settings = core.load_account(a.account)
        cfg = dict(settings.get("cut", {}))
        for k in ("min_pause", "pad", "silence_db", "fillers", "retakes"):
            if getattr(a, k) is not None:
                cfg[k] = getattr(a, k)
        cfg["force_keep"] = list(cfg.get("force_keep") or []) + [parse_range(x) for x in a.keep]
        cfg["force_remove"] = list(cfg.get("force_remove") or []) + [parse_range(x) for x in a.remove]
        src = Path(a.video)
        name = core.slugify(src.stem)
        out = Path(a.out) if a.out else core.media_dir("work", a.media) / name / "cut"
        core.guard_output(out, a.media)
        out.mkdir(parents=True, exist_ok=True)
        wpath = Path(a.words) if a.words else core.media_dir("work", a.media) / name / "transcript" / "words.json"
        words = core.load_words(wpath) if wpath.exists() else []
        if not words:
            print("No words.json found: cutting on the audio level only (fillers and retakes need a transcript).")
            cfg["fillers"] = cfg["retakes"] = False
        info = core.probe(src)
        preset_name = a.preset or settings["export"]["preset"]
        preset = None if preset_name == "none" else settings["presets"][preset_name]
        fps = float(preset["fps"]) if preset else (info.get("fps") or 30.0)
        audio = core.decode_audio(src, 16000)
        edl = plan(words, audio, 16000, len(audio) / 16000, cfg, fps)
        edl["source"] = str(src.resolve())
        edl["preset"] = preset_name
        core.write_json(out / "edl.json", edl)
        core.write_json(out / "words.json", {"source": str(out / "cut.mp4"), "retimed_from": str(wpath),
                                            "words": retime(words, edl)})
        s = edl["summary"]
        print(f"{s['before_s']} s -> {s['after_s']} s ({s['removed_pct']}% removed): {s['pauses']} pauses ({s['pause_s']} s), "
              f"{s['fillers']} fillers, {s['retakes']} retakes, lead-in {s['lead_in_s']} s, tail {s['tail_s']} s")
        for r in edl["removed"]:
            if r["reason"] not in ("pause",):
                print(f"  removed {core.hms(r['start'])}-{core.hms(r['end'])} {r['reason']}: {r['text']}")
        if a.plan_only:
            print("edit list:", out / "edl.json")
            return 0
        render(src, edl, out / "cut.mp4", out / "cut.wav", preset, settings["export"].get("fit", "crop"),
               x264_preset=settings["export"].get("x264_preset_intermediate", "veryfast"))
        print("cut video:", out / "cut.mp4")
        return 0
    except core.ToolError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
