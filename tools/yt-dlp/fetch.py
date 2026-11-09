"""Download videos, audio and transcripts with yt-dlp, with safe defaults.

  python fetch.py own <url>          your own video, best quality MP4 + thumbnail + subtitles + info
  python fetch.py audio <url>        audio only, MP3
  python fetch.py transcript <url>   subtitles only (yours or auto-generated) as .vtt and a plain .txt
  python fetch.py ref <url>          a reference copy (up to 720p) to study privately
  python fetch.py list <url>         list a channel or playlist (title, link, date, length) to a CSV, no downloads

Options:
  --out DIR                 where files go (default: downloads/<command>/)
  --lang en                 transcript language (default en)
  --cookies-from-browser B  use your browser's login (chrome, edge, firefox...) for your own private,
                            unlisted or members-only videos

Everything lands in downloads/ next to this file, which git ignores.
Rules: your own content is yours to download. Other people's videos are for private
reference only: never re-upload them or put their footage, audio or thumbnails in your videos
without permission. See README.md.
"""
import argparse
import csv
import os
import re
import sys
from datetime import datetime, timezone

import yt_dlp

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = "%(uploader,channel,extractor)s/%(upload_date>%Y-%m-%d,NA)s %(title).80B [%(id)s].%(ext)s"


def base_opts(args, kind):
    out = args.out or os.path.join(HERE, "downloads", kind)
    os.makedirs(out, exist_ok=True)
    opts = {
        "outtmpl": os.path.join(out, TEMPLATE),
        "restrictfilenames": False,
        "windowsfilenames": True,  # safe names on Windows
        "noplaylist": kind != "list",
        "writeinfojson": True,
        "retries": 5,
        "concurrent_fragment_downloads": 4,
        "quiet": False,
        "no_warnings": False,
    }
    if args.cookies_from_browser:
        opts["cookiesfrombrowser"] = (args.cookies_from_browser,)
    return opts, out


def subs_opts(lang):
    return {
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [lang, lang + ".*"],
        "subtitlesformat": "vtt/best",
    }


def vtt_to_text(path):
    """Plain transcript from a .vtt: drops timings, tags and the repeated lines auto-captions have."""
    lines, last = [], None
    for raw in open(path, encoding="utf-8", errors="ignore"):
        s = raw.strip()
        if not s or s == "WEBVTT" or "-->" in s or re.match(r"^(Kind|Language|NOTE)\b", s) or s.isdigit():
            continue
        s = re.sub(r"<[^>]+>", "", s).strip()
        if s and s != last:
            lines.append(s)
            last = s
    txt = os.path.splitext(path)[0] + ".txt"
    open(txt, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return txt


def run(args):
    kind = args.command
    opts, out = base_opts(args, kind)
    if kind == "own":
        opts.update({
            "format": "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b",
            "merge_output_format": "mp4",
            "writethumbnail": True,
            **subs_opts(args.lang),
        })
    elif kind == "audio":
        opts.update({
            "format": "ba/b",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        })
    elif kind == "transcript":
        opts.update({"skip_download": True, **subs_opts(args.lang)})
    elif kind == "ref":
        opts.update({
            "format": "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/b",
            "merge_output_format": "mp4",
        })
    elif kind == "list":
        opts.update({"extract_flat": "in_playlist", "skip_download": True, "writeinfojson": False})

    with yt_dlp.YoutubeDL(opts) as ydl:
        if kind == "list":
            info = ydl.extract_info(args.url, download=False)
            rows = info.get("entries") or []
            name = re.sub(r"[^A-Za-z0-9_-]+", "-", info.get("title") or "list").strip("-")[:60] or "list"
            path = os.path.join(out, f"{name}.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["title", "url", "upload_date", "duration_s", "views"])
                for e in rows:
                    w.writerow([e.get("title"), e.get("url") or e.get("webpage_url"), e.get("upload_date"), e.get("duration"), e.get("view_count")])
            print(f"{len(rows)} videos -> {path}")
            return 0
        info = ydl.extract_info(args.url, download=True)

    if kind == "transcript":
        done = []
        for root, _dirs, files in os.walk(out):
            for fn in files:
                if fn.endswith(".vtt") and info.get("id", "") in fn:
                    done.append(vtt_to_text(os.path.join(root, fn)))
        print("transcript:", ", ".join(done) if done else "none found (the video may have no subtitles in that language)")
    if kind == "ref":
        # Note where it came from, so a reference never gets mistaken for your own footage.
        note = os.path.join(out, f"REFERENCE ONLY [{info.get('id')}].txt")
        open(note, "w", encoding="utf-8").write(
            f"Reference copy for private study. Not yours to reuse.\n"
            f"Source: {info.get('webpage_url')}\nCreator: {info.get('uploader') or info.get('channel')}\n"
            f"Title: {info.get('title')}\nDownloaded: {datetime.now(timezone.utc).date().isoformat()}\n"
        )
    print("saved in", out)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["own", "audio", "transcript", "ref", "list"])
    p.add_argument("url")
    p.add_argument("--out")
    p.add_argument("--lang", default="en")
    p.add_argument("--cookies-from-browser", dest="cookies_from_browser")
    args = p.parse_args(argv)
    try:
        return run(args)
    except yt_dlp.utils.DownloadError as e:
        print("Download failed:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
