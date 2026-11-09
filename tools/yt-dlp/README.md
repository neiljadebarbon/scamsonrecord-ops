# yt-dlp: download videos, audio and transcripts

[yt-dlp](https://github.com/yt-dlp/yt-dlp) downloads from YouTube, TikTok, Instagram, Facebook, X and about a thousand other sites. `fetch.py` wraps it with safe defaults so every repo uses it the same way. Downloads go to `downloads/` here, which git ignores.

## What it's for

| Command | Use |
|---|---|
| `python fetch.py own <url>` | Back up **your own** video: best quality MP4, thumbnail, subtitles and the post's details (`.info.json`). |
| `python fetch.py audio <url>` | Audio only, as MP3 (e.g. an old episode you want to re-edit). |
| `python fetch.py transcript <url>` | Subtitles only (yours, or the platform's auto captions) as `.vtt` plus a plain `.txt`. Handy for reading what your own old videos said. |
| `python fetch.py ref <url>` | A reference copy, up to 720p, to study a style or a hook. Adds a "REFERENCE ONLY" note with the source and creator. |
| `python fetch.py list <channel or playlist url>` | A CSV of every video (title, link, date, length, views). Downloads nothing. |

Options: `--out DIR`, `--lang en`, and `--cookies-from-browser chrome` (or `edge`, `firefox`) to use your browser's login for your own private, unlisted or members-only videos.

## Rules (owner, Nov 9, 2026)

- Your own uploads are yours: download them freely.
- Other people's videos are for **private reference only**: study the pacing, hook or layout. Never a source for facts: those come only from official records (`RULES.md`). Don't re-upload them, and don't put their footage, audio, music or thumbnails in your videos without written permission. Their creator owns them, and platforms take down reused clips.
- Keep references in `downloads/` (never committed) and delete them when you're done.
- Respect each site's terms. yt-dlp can't and won't get around paywalls or DRM.

## Setup on your PC (Windows)

1. Python 3.10 or newer and FFmpeg (needed to join video and audio, and for MP3): `winget install Python.Python.3.12` and `winget install Gyan.FFmpeg`.
2. In this folder: `pip install -r requirements.txt`
3. Run a command, e.g. `python fetch.py transcript https://www.youtube.com/watch?v=...`

Update when downloads start failing (sites change often): `pip install -U yt-dlp`, then update the version in `requirements.txt`.

## In Claude cloud sessions

The cloud environment's network blocks video sites (youtube.com and the like), so downloading happens on your PC. To allow it in a cloud session you'd add the site in the environment's Network access settings; YouTube serves video from changing server addresses, so that usually needs broader network access, not one host.

## Use in another repo

Copy this folder (`fetch.py`, `requirements.txt`, `.gitignore`, this README) into the new repo's `tools/`. Nothing in it is specific to one account. It comes from the owner's private AI editor template; keep `fetch.py` identical to the template's.
