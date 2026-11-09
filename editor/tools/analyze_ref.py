"""Measure reference reels for the taste step: pacing, speech, loudness, hook frames and colours.

  python editor/tools/analyze_ref.py                         every video under references/
  python editor/tools/analyze_ref.py references/some-reel.mp4 [more files ...]

Per reference it writes references/<name>/:
  analysis.json  duration, size, cuts (ffmpeg scene detection) with cuts per minute and shot lengths,
                 speech (Whisper): words per minute, when the first word lands, the words spoken in
                 the first 3 seconds; loudness (LUFS, true peak); brightness, saturation, main colours
  contact.jpg    16 frames across the whole video
  hook.jpg       6 frames from the first 3 seconds (hook text, caption style, framing)
  palette.png    the main colours with their share of the picture
  transcript.txt what was said (for study; never reuse their lines)
and one combined references/refs-analysis.json with every reference and the medians across them.

References are for private study only: learn the principles (pace, hook, caption size, colour) and
write them in our own words in editor/style.md. Never reuse their footage, music, captions,
catchphrases or structure beat for beat.
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
from pathlib import Path

import core

SKIP_DIRS = {"_frames"}


def ref_name(p: Path) -> str:
    m = re.search(r"\[([A-Za-z0-9_-]{5,})\]", p.stem)
    base = re.sub(r"\s*\[[^\]]*\]\s*", " ", p.stem).strip()
    return core.slugify((base[:40] + "-" + m.group(1)) if m else base)


def scene_cuts(video, threshold=0.3) -> list[float]:
    """Times of hard cuts (ffmpeg scene score above threshold, on a small copy for speed)."""
    res = core.ffmpeg(["-v", "info", "-i", str(video), "-an", "-vf",
                       f"scale=240:-2,select='gt(scene,{threshold})',showinfo", "-f", "null", "-"])
    txt = res.stderr.decode("utf-8", "replace")
    times = [float(m) for m in re.findall(r"pts_time:\s*([\d.]+)", txt)]
    out = []
    for t in times:  # ignore flashes: two cuts closer than 0.2 s count once
        if not out or t - out[-1] > 0.2:
            out.append(round(t, 3))
    return out


def colours(images, k=6) -> dict:
    """Main colours (median cut), mean brightness and saturation over the frames."""
    from PIL import Image
    import numpy as np
    thumbs = [Image.open(p).convert("RGB").resize((96, 170)) for p in images]
    strip = Image.new("RGB", (96 * len(thumbs), 170))
    for i, t in enumerate(thumbs):
        strip.paste(t, (96 * i, 0))
    q = strip.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: 3 * k]
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    main = [{"hex": "#%02X%02X%02X" % tuple(pal[3 * i: 3 * i + 3]), "share_pct": round(100 * c / total, 1)} for c, i in counts]
    hsv = np.asarray(strip.convert("HSV"), dtype=np.float32)
    return {"main": main, "brightness_pct": round(float(hsv[..., 2].mean()) / 2.55, 1),
            "saturation_pct": round(float(hsv[..., 1].mean()) / 2.55, 1)}


def palette_png(main, out):
    from PIL import Image, ImageDraw, ImageFont
    w, h = 720, 120
    im = Image.new("RGB", (w, h + 34), (12, 12, 18))
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype(str(core.FONTS / "DMSans-Bold.ttf"), 18)
    except OSError:
        font = ImageFont.load_default()
    x = 0
    for c in main:
        cw = max(1, int(round(w * c["share_pct"] / 100)))
        d.rectangle([x, 0, x + cw, h], fill=c["hex"])
        if cw > 60:
            d.text((x + 4, h + 6), f"{c['hex']} {c['share_pct']:.0f}%", fill=(230, 230, 230), font=font)
        x += cw
    im.save(out)


def analyze(video: Path, refs_dir: Path, model, settings, threshold=0.3) -> dict:
    import transcribe as tr
    info = core.probe(video)
    name = ref_name(video)
    out = refs_dir / name
    out.mkdir(parents=True, exist_ok=True)
    dur = info["duration"]
    cuts = scene_cuts(video, threshold)
    edges = [0.0] + cuts + [dur]
    shots = [round(b - a, 2) for a, b in zip(edges, edges[1:]) if b - a > 0.05]
    res = {"name": name, "file": str(video), "duration_s": round(dur, 2),
           "size": f"{info.get('width')}x{info.get('height')}", "fps": info.get("fps"),
           "cuts": len(cuts), "cut_times": cuts, "cuts_per_min": round(len(cuts) / (dur / 60), 1) if dur else 0,
           "shot_avg_s": round(statistics.mean(shots), 2) if shots else None,
           "shot_median_s": round(statistics.median(shots), 2) if shots else None,
           "shot_min_s": min(shots) if shots else None, "shot_max_s": max(shots) if shots else None,
           "first_cut_s": cuts[0] if cuts else None, "scene_threshold": threshold}
    if info["has_audio"]:
        w = settings.get("whisper", {})
        data = tr.transcribe(video, w.get("model", "small.en"), w.get("language", "en"), "", False, model=model)
        words = data["words"]
        (out / "transcript.txt").write_text(tr.transcript_text(words), encoding="utf-8")
        # speaking time: word spans with gaps under 0.3 s joined (pauses left out)
        talk, cur = 0.0, None
        for x in words:
            if cur and x["start"] - cur[1] < 0.3:
                cur[1] = max(cur[1], x["end"])
            else:
                if cur:
                    talk += cur[1] - cur[0]
                cur = [x["start"], x["end"]]
        talk += (cur[1] - cur[0]) if cur else 0.0
        res.update({
            "words": len(words), "wpm": round(len(words) / (dur / 60), 0) if dur else 0,
            "wpm_without_pauses": round(len(words) / (talk / 60), 0) if talk > 1 else None,
            "talk_share_pct": round(100 * talk / dur, 0) if dur else 0,
            "first_word_s": words[0]["start"] if words else None,
            "first_3s_words": " ".join(x["word"] for x in words if x["start"] < 3.0),
        })
        loud = core.loudness(video)
        res.update({"lufs": loud["lufs"], "true_peak": loud["true_peak"], "lra": loud["lra"]})
    tmp = out / "_frames"
    tmp.mkdir(exist_ok=True)
    items = []
    for i in range(16):
        t = dur * (i + 0.5) / 16
        items.append((core.extract_frame(video, t, tmp / f"c{i:02d}.png", width=360), core.hms(t)))
    core.contact_sheet(items, out / "contact.jpg", cols=4, tile_w=270, title=f"{name}: {core.hms(dur)}, {len(cuts)} cuts")
    hook = []
    for t in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5):
        if t < dur:
            hook.append((core.extract_frame(video, t + 0.04, tmp / f"h{t:.1f}.png", width=540), f"{t:.1f}s"))
    core.contact_sheet(hook, out / "hook.jpg", cols=3, tile_w=360, title=f"{name}: first 3 seconds")
    res["colour"] = colours([p for p, _ in items])
    palette_png(res["colour"]["main"], out / "palette.png")
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    res["images"] = {k: str(out / f) for k, f in (("contact", "contact.jpg"), ("hook", "hook.jpg"), ("palette", "palette.png"))}
    core.write_json(out / "analysis.json", res)
    return res


def summary(results: list[dict]) -> dict:
    def med(k):
        v = [r[k] for r in results if isinstance(r.get(k), (int, float))]
        return round(float(statistics.median(v)), 2) if v else None
    keys = ["duration_s", "cuts_per_min", "shot_avg_s", "shot_median_s", "first_cut_s", "wpm", "wpm_without_pauses",
            "first_word_s", "lufs", "true_peak"]
    return {"references": len(results), **{f"median_{k}": med(k) for k in keys}}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("videos", nargs="*", help="reference videos (default: every video under references/)")
    p.add_argument("--threshold", type=float, default=0.3, help="scene-cut sensitivity, 0.2 (more cuts) to 0.5 (fewer)")
    p.add_argument("--models-dir")
    p.add_argument("--account")
    p.add_argument("--media")
    a = p.parse_args(argv)
    try:
        import transcribe as tr
        settings = core.load_account(a.account)
        refs = core.media_dir("references", a.media)
        vids = [Path(v) for v in a.videos] or sorted(
            f for f in refs.rglob("*") if f.is_file() and core.is_media_file(f, ("video",))
            and not (f.parent / "analysis.json").exists() and not SKIP_DIRS & set(f.parts))
        if not vids:
            raise core.ToolError(f"No reference videos in {refs}. Download some with tools/yt-dlp/fetch.py ref <url> --out \"{refs}\"")
        model = tr.load_model(settings.get("whisper", {}).get("model", "small.en"), a.models_dir)
        results = []
        for v in vids:
            print(f"analysing {v.name} ...", flush=True)
            r = analyze(v, refs, model, settings, a.threshold)
            results.append(r)
            print(f"  {r['duration_s']} s, {r['cuts']} cuts ({r['cuts_per_min']}/min, shots avg {r['shot_avg_s']} s), "
                  f"{r.get('wpm')} wpm, first word at {r.get('first_word_s')} s, {r.get('lufs')} LUFS -> {refs / r['name']}")
        combined = {"created": core.now(), "summary": summary(results), "references": results}
        core.write_json(refs / "refs-analysis.json", combined)
        print("summary:", combined["summary"])
        print("combined:", refs / "refs-analysis.json")
        return 0
    except core.ToolError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
