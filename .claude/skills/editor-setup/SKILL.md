---
name: editor-setup
description: Set up the AI editor (prompt 1) for Scams on Record on the owner's Windows PC - check out scamsonrecord-ops into D:\AI Editor\Scams on Record if needed, use the shared Python 3.12 venv, install and verify FFmpeg, Python packages, the Whisper model, yt-dlp, Node, the HyperFrames CLI and the HyperFrames skills (for the Windows user, telemetry off), create the media folders and the sound bed, and report a version table. Use for "run the editor setup", "set up the editor", "install the tools", "check my setup", or when an editor tool says something is missing.
---

# Editor setup (prompt 1)

Goal: every tool the editor needs is installed and verified, and the owner gets one short table.
Read `CLAUDE.md` and `editor/README.md` once for the layout. Write to the owner in plain words, numbered steps, no em dashes.

## Where things live

- Account folder: `D:\AI Editor\Scams on Record`. It is the scamsonrecord-ops checkout and holds the footage folders at its root: `raw\`, `references\`, `done\`, `work\`, `music\`. Git ignores all of them.
- Shared Python venv one level up: `D:\AI Editor\.venv` (the same venv as the owner's other account folders on D:).
- Always run Python through the launcher, which picks that venv: `bash editor/py.sh ...` in Git Bash, or `editor\py.cmd ...` in PowerShell or cmd. Never call bare `python` or `pip`.

## Steps

1. Is this folder the repo checkout? Run `git rev-parse --show-toplevel`.
   - Yes: run `git pull` (ask first if there are local changes) and go to step 2.
   - No (a plain folder with raw\ references\ done\ work\ README.txt from make-folders.ps1): check the repo out into it. The folder isn't empty, so don't clone. Run these in the folder:
     1. `git init`
     2. `git remote add origin https://github.com/neiljadebarbon/scamsonrecord-ops.git`
     3. `git fetch origin`
     4. `git checkout -t origin/main`
     If `git checkout` stops because a file in the folder has the same name as one in the repo (for example a README.txt or .gitignore), don't delete anything: move that file to `work\` and run the checkout again.
   The repo is public, so fetching needs no login. Pushing does: Git Credential Manager (part of Git for Windows) opens a browser sign-in. Never ask for a token in chat. raw\ references\ done\ work\ are ignored, so the checkout leaves the footage alone. Then tell the owner to start a new Local session in this folder so the skills load.
2. Run `bash editor/py.sh editor/tools/doctor.py` and read the table and the "To fix" list.
3. Python: the tools need 3.10 to 3.13 (3.12 is the target). Python 3.14 and newer have no PyAV wheels yet, so `pip install faster-whisper` fails there. List what is installed with `py -0p`.
   - No 3.12: `winget install -e --id Python.Python.3.12`
   - No venv yet: `py -3.12 -m venv "D:\AI Editor\.venv"` (quote it, it has a space)
   - Packages: `bash editor/py.sh -m pip install -r editor/requirements.txt`
   - The channel's own voice tools (`tools/voice/qc.py`, `align.py`, `gen_vo.py`) also need `pocketsphinx` and `praat-parselmouth` (the whisper check). Ask, then: `bash editor/py.sh -m pip install pocketsphinx praat-parselmouth`
4. Install what doctor lists as missing, one at a time, and say what each is for:
   - FFmpeg (cuts, exports, burned-in captions need libass): `winget install -e --id Gyan.FFmpeg`
   - Node 22 or newer (HyperFrames): `winget install -e --id OpenJS.NodeJS.LTS`
   - Git: `winget install -e --id Git.Git`
   winget changes PATH for new terminals only. The tools also look in `%LOCALAPPDATA%\Microsoft\WinGet\Links`, so FFmpeg usually works at once; if not, ask the owner to restart the Claude app.
5. HyperFrames skills, once per Windows user. This repo is public and doesn't carry copies of the 9 HyperFrames skills. Tell the owner what this does, then run:
   1. `npx --yes hyperframes@0.9.26 skills` (copies the skills into `%USERPROFILE%\.claude\skills` and `%USERPROFILE%\.agents\skills`, so every Claude session for this Windows user has them)
   2. `npx --yes hyperframes@0.9.26 telemetry disable`
   Skip step 1 if `%USERPROFILE%\.claude\skills\hyperframes` already exists (for example from another account's setup). Never copy the skills into this repo's `.claude/skills/`. `.claude/settings.json` here also sets HYPERFRAMES_NO_TELEMETRY=1 and DO_NOT_TRACK=1; don't change it. The HyperFrames CLI itself runs on demand with `npx hyperframes`. A new Local session loads the skills.
6. Whisper model (about 0.5 GB, once): `bash editor/py.sh editor/tools/doctor.py --download-model`. A model already in the default Hugging Face cache is used from there; a new download goes to `editor/models` (git-ignored). Never commit a model.
7. Media folders: `bash editor/py.sh editor/tools/doctor.py --make-folders` (adds any of raw, references, done, work, music that are missing).
8. Sound bed: RULES.md allows only synthesized sound. If `music\` has no audio file, offer to make the channel's bed: write `work/bed-events.json` with `{"total": 120, "events": []}`, then run `bash editor/py.sh tools/video/sound.py bed work/bed-events.json music/scams-bed-120s.wav`.
9. Run doctor again. Every line should be OK (WARN on HyperFrames is fine if the owner doesn't need graphics yet; "Remotion: no Remotion project" is expected).
10. Report to the owner: the table (tool, version, OK or not), anything still missing with the one command that fixes it, and what to do next (drop a recording in `raw\`, then say "edit the newest recording in raw", or study references first with the taste step).

## Safety

- Never delete or move anything in raw\, references\ or done\.
- Never commit media, models or `.venv`. If doctor says a media folder is NOT ignored by git, fix `.gitignore` before anything else.
- This repo is public. Never write a key, a password, a personal detail about the owner or a private path into any file here. The ElevenLabs key stays in the environment (`XI` or `ELEVENLABS_API_KEY`) or the ignored local `.env`. Never ask the owner to paste a key in chat.
- Ask before installing anything the owner didn't ask for, and before any `git push`.

## Channel rules that apply to every editor job

- `RULES.md` and `persona/NARRATOR.md` override habits. Facts only from official records; nothing is posted before the independent fact-check passes.
- On-screen text: no em dashes, no AI melody (RULES.md, Writing). Short.
- No whispering at all in any voice. ElevenLabs voices are made with `tools/voice/gen_vo.py`, which retakes whispered takes.
- Never show a working scam link, a real scam phone number or a victim detail beyond the record.
- Reference videos are for private study only, and never a source for facts.
