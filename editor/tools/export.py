"""Export a finished video as a numbered draft in done/, using a platform preset.

  python editor/tools/export.py <video> --name my-video [--preset reel] [--ass captions.ass] [--audio mix.m4a]

Presets (editor/account.json "presets"):
  reel     1080x1920, 30 fps   TikTok, Reels, Shorts
  youtube  1920x1080, 30 fps   YouTube, Facebook landscape
  square   1080x1080, 30 fps   feed posts
All are H.264 High profile, CRF 18, yuv420p, BT.709 colour tags, AAC 192 kbps 48 kHz, faststart.
A source with another shape is scaled to fill and centre-cropped (account.json export.fit = "crop"),
or fitted with navy bars ("pad").

--ass burns captions in during the same encode, --audio swaps in a mixed soundtrack (from music.py),
so the picture is encoded only once more. --overlay FILE@START[-END][@X,Y] lays a graphic on top (a HyperFrames
or Remotion render: .mov ProRes 4444 or .webm VP9 with transparency, or a plain .mp4/.png), under the
captions. edit.py reads overlays from work/<name>/edit.json: "overlays": [{"file": "...", "at": 1.2}].

Output: done/<name>-draft-vN.mp4, where N is one more than any earlier draft of that name. An earlier
draft is never overwritten. A note of what went into each draft is kept in work/<name>/draft-vN.json.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import core
import captions
from cut import video_chain


def overlay_inputs(overlays, first_index: int):
    """ffmpeg input args and filter steps for graphics laid over the video, in order."""
    args, steps = [], []
    for k, o in enumerate(overlays or []):
        f = Path(o["file"])
        if not f.exists():
            raise core.ToolError(f"Overlay not found: {f}")
        if f.suffix.lower() == ".webm":
            args += ["-c:v", "libvpx-vp9"]  # the built-in VP9 decoder drops transparency
        if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
            args += ["-loop", "1"]
        args += ["-i", str(f)]
        at = float(o.get("at", 0))
        until = o.get("until")
        if until is None and f.suffix.lower() in (".png", ".jpg", ".jpeg"):
            until = at + 3.0
        enable = f"between(t,{at:.3f},{float(until):.3f})" if until is not None else f"gte(t,{at:.3f})"
        steps.append((first_index + k, at, enable, int(o.get("x", 0)), int(o.get("y", 0))))
    return args, steps


def export(video, settings: dict, name: str, preset_name: str | None = None, ass=None, audio=None,
           media=None, out=None, meta: dict | None = None, overlays=None) -> tuple[Path, int]:
    preset_name = preset_name or settings["export"]["preset"]
    preset = settings["presets"][preset_name]
    info = core.probe(video)
    if not info["has_video"]:
        raise core.ToolError(f"{video} has no picture.")
    done = core.media_dir("done", media)
    work = core.media_dir("work", media) / name
    work.mkdir(parents=True, exist_ok=True)
    if out:
        final, n = core.guard_output(Path(out), media), 0
        if final.exists():
            raise core.ToolError(f"{final} already exists; drafts are never overwritten.")
    else:
        final, n = core.next_draft(done, work, name)
    part = work / (final.stem + ".part.mp4")
    W, H, fps = preset["width"], preset["height"], preset["fps"]
    same = info.get("width") == W and info.get("height") == H and abs((info.get("fps") or 0) - fps) < 0.01 and not info.get("hdr")
    vf = "setsar=1,format=yuv420p" if same else video_chain(info, preset, fps, settings["export"].get("fit", "crop"))
    args = ["-y", "-v", "error", "-i", str(video)]
    if audio:
        args += ["-i", str(audio)]
    o_args, steps = overlay_inputs(overlays, 2 if audio else 1)
    args += o_args
    graph = [f"[0:v]{vf}[v0]"]
    last = "v0"
    for k, (idx, at, enable, x, y) in enumerate(steps):
        graph.append(f"[{idx}:v]scale={W}:-2:flags=lanczos,setpts=PTS-STARTPTS+{at:.3f}/TB[o{k}]")
        graph.append(f"[{last}][o{k}]overlay=x={x}:y={y}:enable='{enable}':eof_action=pass:format=auto[v{k + 1}]")
        last = f"v{k + 1}"
    tail = (captions.ass_filter(Path(ass)) + "," if ass else "") + "format=yuv420p"
    graph.append(f"[{last}]{tail}[vout]")
    args += ["-filter_complex", ";".join(graph),
             "-map", "[vout]", "-map", "1:a:0" if audio else "0:a:0?",
             "-c:v", "libx264", "-preset", settings["export"].get("x264_preset", "medium"), "-crf", str(preset.get("crf", 18)),
             "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(fps), "-g", str(int(fps * 2)),
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-c:a", "aac", "-b:a", f"{preset.get('audio_kbps', 192)}k", "-ar", "48000", "-ac", "2",
             "-shortest", "-movflags", "+faststart", str(part)]
    core.ffmpeg(args)
    if final.exists():  # someone made the same draft meanwhile: take the next number
        final, n = core.next_draft(done, work, name)
    try:
        os.rename(part, final)
    except OSError:
        shutil.move(str(part), str(final))
    if n:
        core.write_json(work / f"draft-v{n}.json", {"draft": str(final), "version": n, "preset": preset_name,
                                                    "source": str(Path(video).resolve()), "created": core.now(),
                                                    **(meta or {})})
    return final, n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("video")
    p.add_argument("--name", help="draft name (default: the video's file name)")
    p.add_argument("--preset", choices=["reel", "youtube", "square"])
    p.add_argument("--ass", help="captions .ass to burn in")
    p.add_argument("--audio", help="soundtrack to use instead of the video's own")
    p.add_argument("--overlay", action="append", default=[], metavar="FILE@START[-END][@X,Y]",
                   help="graphic to lay over the video from START (to END) seconds at X,Y px; repeatable")
    p.add_argument("--out", help="exact output path instead of done/<name>-draft-vN.mp4 (must not exist)")
    p.add_argument("--account")
    p.add_argument("--media")
    a = p.parse_args(argv)
    try:
        settings = core.load_account(a.account)
        name = a.name or core.slugify(Path(a.video).stem)
        overlays = []
        for o in a.overlay:
            parts = o.split("@")
            xy = parts.pop() if len(parts) >= 3 else "0,0"
            t = parts.pop()
            at, _, until = t.partition("-")
            x, _, y = xy.partition(",")
            overlays.append({"file": "@".join(parts), "at": float(at), "until": float(until) if until else None,
                             "x": int(x or 0), "y": int(y or 0)})
        path, n = export(a.video, settings, name, a.preset, a.ass, a.audio, a.media, a.out, overlays=overlays)
        print(f"draft v{n}: {path}" if n else f"exported: {path}")
        return 0
    except core.ToolError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
