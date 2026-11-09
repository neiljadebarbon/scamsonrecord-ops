"""Snapshots and numbers for reviewing a draft before the owner sees it.

  python editor/tools/review.py done/my-video-draft-v1.mp4 [--out DIR] [--preset reel]

Writes into work/<name>/review-vN/ (or --out):
  hook.jpg       frames at 0.5, 1.0, 1.5, 2.0, 2.5 and 3.0 s: is the hook readable, big and clear?
  contact.jpg    12 frames spread over the whole draft: captions, framing, colour
  guides.png     one frame with the safe zones drawn on: yellow = graphics zone (y 230 to 1300),
                 cyan = caption box, red = TikTok's buttons. Nothing important may sit in the red area.
  review.json    duration, size, fps, loudness (LUFS, true peak), and the image paths

Claude looks at the images with its own eyes and writes the short report for the owner.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import core
import captions


def review(video, settings: dict, out_dir=None, preset: str | None = None, media=None) -> dict:
    video = Path(video)
    info = core.probe(video)
    m = re.match(r"(.+)-draft-v(\d+)$", video.stem)
    name, ver = (m.group(1), int(m.group(2))) if m else (core.slugify(video.stem), 0)
    out = Path(out_dir) if out_dir else core.media_dir("work", media) / name / (f"review-v{ver}" if ver else "review")
    out = core.guard_output(out, media)
    out.mkdir(parents=True, exist_ok=True)
    dur = info["duration"]
    if not preset:
        preset = next((k for k, p in settings["presets"].items()
                       if p["width"] == info.get("width") and p["height"] == info.get("height")), settings["export"]["preset"])
    tmp = out / "_frames"
    tmp.mkdir(exist_ok=True)
    hook_items = []
    for t in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
        if t < dur:
            hook_items.append((core.extract_frame(video, t, tmp / f"h{t:.1f}.png", width=540), f"{t:.1f}s"))
    core.contact_sheet(hook_items, out / "hook.jpg", cols=3, tile_w=360, title=f"{video.name}: first 3 seconds")
    n = 12
    items = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        items.append((core.extract_frame(video, t, tmp / f"c{i:02d}.png", width=360), core.hms(t)))
    core.contact_sheet(items, out / "contact.jpg", cols=4, tile_w=270, title=f"{video.name}: {core.hms(dur)}")
    ass_text, _ = captions.build_ass([], settings, preset, guides=True)
    gass = out / "guides.ass"
    gass.write_text(ass_text, encoding="utf-8")
    core.extract_frame(video, min(1.2, dur / 2), out / "guides.png", vf=captions.ass_filter(gass))
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    gass.unlink()
    loud = core.loudness(video) if info["has_audio"] else None
    rep = {"video": str(video), "name": name, "version": ver, "preset": preset, "duration_s": round(dur, 2),
           "size": f"{info.get('width')}x{info.get('height')}", "fps": info.get("fps"),
           "lufs": loud["lufs"] if loud else None, "true_peak": loud["true_peak"] if loud else None,
           "images": {"hook": str(out / "hook.jpg"), "contact": str(out / "contact.jpg"), "guides": str(out / "guides.png")}}
    core.write_json(out / "review.json", rep)
    return rep


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video", nargs="?", help="draft to review (default: newest file in done/)")
    p.add_argument("--out")
    p.add_argument("--preset")
    p.add_argument("--account")
    p.add_argument("--media")
    a = p.parse_args(argv)
    try:
        settings = core.load_account(a.account)
        v = Path(a.video) if a.video else core.newest_file(core.media_dir("done", a.media))
        if not v:
            raise core.ToolError("No draft in done/ yet.")
        rep = review(v, settings, a.out, a.preset, a.media)
        print(f"{rep['size']} {rep['fps']} fps {rep['duration_s']} s, {rep['lufs']} LUFS, true peak {rep['true_peak']} dBTP")
        for k, path in rep["images"].items():
            print(f"  {k}: {path}")
        return 0
    except core.ToolError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
