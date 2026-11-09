# AI editor for Scams on Record

Most episodes are made by the channel's own engine from a voiceover (`tools/voice/`, `tools/video/`, see the main README). The AI editor covers the rest:

- **Recorded footage or voice takes.** A screen recording, a phone clip, a voiceover recorded on a mic. Claude cuts the pauses and false starts, adds word-by-word captions with the spoken word in yellow, lays the channel's sound bed under the voice, sets -14 LUFS and hands back a draft.
- **Reference study (taste).** Claude studies 3 to 5 reels you like and writes this channel's style in its own words.
- **Finishing and export.** A safe-zone and loudness check of any finished video (engine renders too), graphics laid on top, a numbered draft in `done\`.

You reply with notes in plain words ("captions bigger") and get draft v2. Every draft is measured (seconds cut, words kept, caption timing, loudness) and Claude looks at snapshots before you do.

Every edit follows `RULES.md` and `persona/NARRATOR.md`: facts only from official records, the source line on screen, no working scam link or real scam phone number on screen, no whispering at all, the 1080x1920 safe zones, -14 LUFS. No draft gets posted before the independent fact-check passes (RULES.md, Big Law).

## Set up once (Windows)

1. Install the basics. Open PowerShell and run these one at a time:
   ```
   winget install -e --id Python.Python.3.12
   winget install -e --id OpenJS.NodeJS.LTS
   winget install -e --id Gyan.FFmpeg
   winget install -e --id Git.Git
   ```
   Gyan.FFmpeg is the full build, which has libass (needed to burn captions in).
2. Make the account folder `D:\AI Editor\Scams on Record` with `editor/make-folders.ps1` (paste it into PowerShell). It makes raw, references, done and work inside. Skip this if the folder is already there.
3. Make the shared Python for the drive, once (Python 3.12, because 3.14 and newer can't install the Whisper packages yet). Skip this if `D:\AI Editor\.venv` already exists:
   ```
   py -3.12 -m venv "D:\AI Editor\.venv"
   ```
4. Open the Claude desktop app, start a Claude Code Local session, and choose `D:\AI Editor\Scams on Record` as its folder.
5. Paste prompt 1 (below). Claude checks out this repo into the folder, installs what's missing into the venv, installs the HyperFrames skills for your Windows user (with telemetry off), downloads the Whisper model (or uses the one you already have) and shows you a table of versions.
6. When Claude says the repo is checked out, start a new Local session in the same folder so the editor skills load.

## What goes where

The account folder is both the git repo and the footage folder. Git ignores the footage folders, so videos never go to GitHub. This repo is public: keys, footage and personal details never go in it.

| Folder | What's in it |
|---|---|
| `raw\` | Your recordings. Drop new takes here. Claude never changes or deletes them. |
| `references\` | Reels you like, downloaded for private study (pacing, hook, captions). Never reused, and never a source for facts. |
| `done\` | Drafts: `name-draft-v1.mp4`, then v2, v3 after your notes. |
| `work\` | Claude's working files per video: transcript, cut list, captions, report, snapshots. Safe to delete. |
| `music\` | The channel's synthesized sound bed (see below). RULES.md allows no licensed or trending music. |
| `editor\` | The tools, `account.json` (this channel's look), `style.md` (this channel's style in words). |

Footage somewhere else on the drive? Set the `EDITOR_MEDIA` environment variable to that folder (it needs the same raw, references, done, work and music folders inside).

**Sound bed.** RULES.md: synthesized bed and effects only. Make one bed, longer than any video, and the editor puts it under the voice with ducking:
1. Save `work\bed-events.json` with this text: `{"total": 120, "events": []}`
2. Run `editor\py.cmd tools\video\sound.py bed work\bed-events.json music\scams-bed-120s.wav`

**A voice take with no picture.** The editor needs picture and sound. Put the take on a dark frame first, then edit that file:
```
ffmpeg -f lavfi -i color=c=0x080A10:s=1080x1920:r=30 -i "raw\take.wav" -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac "work\take-on-dark.mp4"
```

## The three prompts

### Prompt 1: set up (once)

```
Set up the AI editor in this folder. If this folder isn't a git checkout of https://github.com/neiljadebarbon/scamsonrecord-ops yet, check it out here without moving or deleting my files (git init, git remote add origin, git fetch origin, git checkout -t origin/main). Then follow .claude/skills/editor-setup/SKILL.md: run the doctor, install anything missing (winget, and pip into the shared venv one folder up), install the HyperFrames skills for my user with telemetry off, download the Whisper model, create the media folders, and show me a table of versions.
```

### Prompt 2: learn my style (once, and again whenever your taste changes)

```
Use the editor-taste skill. Study these reels I like and write this channel's style. Take inspiration, but don't copy.
1. <link>
2. <link>
3. <link>
```

Three to five links. Claude downloads them for study only, measures them (cuts per minute, words per minute, loudness, hook frames, colours), looks at them, writes `editor/style.md` in its own words and updates `editor/account.json` inside the limits of RULES.md.

### Prompt 3: edit

```
Use the editor-edit skill. Edit the newest recording in raw.
```

You get `done\<name>-draft-v1.mp4` and a short report. Then reply with notes, for example:

```
Captions bigger, and cut the part where I say "let me start again".
```

That becomes `done\<name>-draft-v2.mp4`. Notes Claude knows how to act on: hook bigger or smaller, different hook text, captions bigger, fewer words on screen, cuts too tight or too loose, put back or cut a part, bed louder or quieter or none, fix a word in the captions, add the source line, cover a number or link, add a title card or lower third.

To finish an engine render instead: "Use the editor-edit skill. Check episodes/<episode>/video/<file>.mp4 for safe zones and loudness."

## What happens in an edit

1. Transcribe: Whisper (small.en, on your PC) writes every word with its time.
2. Cut: pauses longer than 0.45 s are cut down to 0.12 s each side, "um" and "uh" go, and a restarted line keeps only the last take. Every removal is listed with its text.
3. Check: Whisper listens to the cut again and counts the words. Anything missing is flagged. Claude also runs the channel's whisper check (`tools/voice/qc.py`): a take under 0.58 voiced is treated as whispered and doesn't go out.
4. Captions: Inter Black, off-white with a near-black outline, the spoken word in yellow (#FFD60A), at most 4 words a line, centred on y 1440, no wider than 820 px, clear of TikTok's buttons. A hook title for the first 3 seconds if the style uses one.
5. Sound: the bed from `music\` about 20 dB under the voice while you talk, a little louder in gaps, fades in and out.
6. Loudness: -14 LUFS, true peak -1.5 dBTP (same as `tools/video/sound.py`).
7. Export: 1080x1920, 30 fps, H.264, to `done\`.
8. Review: snapshots of the first 3 seconds, the whole video and the safe zones (content y 230 to 1300, captions, buttons), which Claude checks before reporting.

## Commands (Claude runs these; here for reference)

Python always runs through the launcher, which picks `D:\AI Editor\.venv`: `bash editor/py.sh` in Git Bash, `editor\py.cmd` in PowerShell or cmd.

| Command | Does |
|---|---|
| `editor\py.cmd editor\tools\doctor.py` | Checks every tool and says how to fix what's missing |
| `editor\py.cmd editor\tools\edit.py` | Newest recording in raw to a draft in done, all steps |
| `editor\py.cmd editor\tools\edit.py --name gold-bars --note "captions bigger"` | Next draft after changing `work\gold-bars\edit.json` |
| `editor\py.cmd editor\tools\review.py <video> --out work\<name>\review` | Safe-zone frames and loudness for any finished video |
| `editor\py.cmd editor\tools\analyze_ref.py` | Measures every reference video |
| `editor\py.cmd tools\yt-dlp\fetch.py ref <url> --out references` | Downloads a reference for study |
| `transcribe.py`, `cut.py`, `captions.py`, `music.py`, `export.py`, `review.py` | The single steps; each has `--help` |

## Rules

- `RULES.md` and `persona/NARRATOR.md` come first. Facts only from official records; the source line on screen for the last 10 seconds; "accused" until a plea or verdict; REENACTMENT on any mock-up.
- Never show a working scam link, a real scam phone number or a victim detail beyond the record. Cover it in the edit.
- No whispering at all. Any ElevenLabs voice is made with `tools/voice/gen_vo.py`, which retakes whispered takes.
- On-screen text: no em dashes, no AI melody (RULES.md, Writing).
- Raw footage is never changed. Drafts are never overwritten. Media, models, keys and the venv never go in git.
- References are for private study only. Never reuse their footage, music, captions, catchphrases or structure.

## Template and re-sync

This editor comes from the owner's private AI editor template. The tools in `editor/tools/`, the launchers, `editor/requirements.txt` and `tools/yt-dlp/fetch.py` are kept identical to the template; only `account.json`, `style.md`, the fonts, this README and the `editor-*` skills are this channel's own. To take a fix from the template, copy its `editor/tools/` folder over this one (and `tools/yt-dlp/fetch.py` if it changed), then run `editor\py.cmd editor\tools\doctor.py`.

## If something goes wrong

1. Run `editor\py.cmd editor\tools\doctor.py` and do what its "To fix" list says.
2. "ffmpeg not found" right after installing it: restart the Claude app (new PATH).
3. `pip install` fails building "av": that's Python 3.14 or newer. Use the 3.12 venv (setup step 3).
4. A download of a reference fails: update yt-dlp with `editor\py.cmd -m pip install -U yt-dlp`, and for Instagram add `--cookies-from-browser edge`.
