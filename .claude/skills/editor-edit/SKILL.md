---
name: editor-edit
description: Edit recorded footage or a voice take into a Scams on Record short-video draft (prompt 3) - take the newest file in raw/, cut pauses, fillers and retakes, add word-by-word captions with the active word in yellow and a hook title, lay the channel's synthesized bed under the voice, run the whisper check, export done/<name>-draft-v1.mp4 at -14 LUFS, check safe zones, scam links and the source line with snapshots, and report. Also finishing checks of engine renders. Then turn the owner's plain-words notes into draft-v2, v3. Use for "edit the newest recording in raw", "make a draft", "cut this recording", "check this episode", or any note about a draft.
---

# Editor edit (prompt 3)

Goal: a draft in `done\` that follows RULES.md, a short report, and fast revisions from the owner's notes.
Run Python only through the launcher: `bash editor/py.sh ...` (Git Bash) or `editor\py.cmd ...` (PowerShell). Before the first edit in a session, read `RULES.md`, `persona/NARRATOR.md`, `editor/style.md` and `editor/account.json`.

## First draft

1. Pick the recording: the newest video in `raw\`, unless the owner names one. Choose a short name for it (lowercase, hyphens, e.g. `gold-bar-texts`). Never change, rename or delete anything in `raw\`. The tools need picture and sound: for a voice take with no picture, make `work/<name>-on-dark.mp4` first (the command is in `editor/README.md`) and edit that file.
2. Plan without rendering: `bash editor/py.sh editor/tools/edit.py "raw/<file>" --name <name> --plan-only`
3. Read `work/<name>/transcript/transcript.txt` and `work/<name>/cut/edl.json`:
   - Words marked `[?word]` were unclear. Fix spellings of names, places and agencies with `"fixes"` in `work/<name>/edit.json` (e.g. `{"Kanas": "Kansas"}`); channel-wide fixes go in `editor/account.json`. Captions show what was said; never reword it.
   - Check every removal that isn't a pause (fillers, retakes). A "retake" must really be a restart of the same line. If one is wrong, put it back with `"cut": {"force_keep": [[start, end]]}` (source seconds from edl.json).
   - Facts: every claim must match the episode's `source/source.md` (an official record). Don't cut or change a claim that looks wrong; flag it in the report with the time. Watch for: "accused" until a plea or verdict, ages with whose age and when, totals that stay totals.
4. Write the hook title, if `editor/style.md` uses one: 3 to 6 words, the strongest true fact from the record, stated plainly (GAMEPLAN.md beat 1). Wrap the key number or outcome in stars for the yellow accent: `*$1 million* in gold bars`. No em dashes, no AI melody, no movie-trailer opener, nothing the record doesn't say.
5. Render: `bash editor/py.sh editor/tools/edit.py "raw/<file>" --name <name> --hook "<hook>"`
   It transcribes (or reuses the transcript), cuts, listens to the cut again, burns captions, lays the bed from `music\` under the voice (newest file, or none), sets -14 LUFS, exports `done/<name>-draft-v1.mp4`, and writes `work/<name>/report-v1.md` and review images.
6. Check before you tell the owner:
   - Report numbers: words kept should be 98% or more. Look at every word listed as missing or heard differently. Loudness should read -14 plus or minus 1 LUFS, true peak at or under -1.
   - Whisper check (RULES.md: no whispering at all): `bash editor/py.sh -c "import sys; sys.path.insert(0, 'tools/voice'); import qc; print(qc.voiced_ratio(sys.argv[1]))" work/<name>/cut/cut.wav`. 0.58 or more passes. Under 0.58 sounds whispered: say so and don't call the draft ready. An ElevenLabs take gets regenerated with `tools/voice/gen_vo.py`, which retakes until it passes. (Needs `praat-parselmouth`; never run it on a file inside `raw\`, it writes a temp file next to the input.)
   - Look at `work/<name>/review-v1/hook.jpg`, `contact.jpg` and `guides.png`: captions readable and spelled right, the active word yellow, inside the cyan box at y 1440; content inside the yellow box (y 230 to 1300); nothing important in the red button area (right of x 940 below y 1000); hook big and clear in the first second.
   - Every frame with a phone or a screen: no working scam link, no real scam phone number, no victim detail beyond the record. Cover any with an overlay (editor-graphics) and render again.
   - The source line is on screen for the last 10 seconds (RULES.md, Sources), and any mock-up text or call carries a REENACTMENT label. If the footage doesn't have them, add them as overlays (editor-graphics).
   - The channel is faceless: flag any face or personal detail of the owner in the footage.
   - Fix anything wrong and render again before reporting (that makes v2; say so).
7. Report to the owner in a few short lines: the draft's path, length before and after, what was cut besides pauses (quote retakes), the hook text, bed and loudness, the whisper check number, anything they should check (flagged facts, unclear words, covered links). Remind them the independent fact-check (RULES.md, Big Law) still has to pass before posting. Then ask for notes.

## Finishing an engine render

For a finished episode (`episodes/<ep>/video/<name>.mp4`):
- Check: `bash editor/py.sh editor/tools/review.py "episodes/<ep>/video/<name>.mp4" --out work/<name>/review`. Look at the three images and the loudness the same way as step 6.
- Lay a graphic on top (a cover box, a corrected label) without touching the episode file: `bash editor/py.sh editor/tools/export.py "episodes/<ep>/video/<name>.mp4" --name <name> --overlay "work/<name>/graphics/cover.png@12.0-15.5@120,640"`. That makes `done/<name>-draft-vN.mp4`.
- Engine renders are drawn for 1080x1920. A landscape or square export crops them, so don't make one unless the owner asks and the framing is checked.

## Revisions from notes

The owner writes notes in plain words. Turn each into a change in `work/<name>/edit.json` (same shape as `editor/account.json`; only the values that differ), then run:
`bash editor/py.sh editor/tools/edit.py --name <name> --note "<their words>" --changes "<what you changed>"`
That makes the next draft number (`draft-v2`, `v3` ...). Earlier drafts are never overwritten, and the transcript and cut are reused when they didn't change.

| Note | Change |
|---|---|
| make the hook bigger / smaller | `hook.size` up or down about 25% (100 to 125); it wraps by itself |
| hook stays too short / too long | `hook.seconds` (default 3.0) |
| change the hook to ... | `hook.text` (same rules as above) |
| captions bigger / smaller | `captions.size` (default 85) |
| fewer words on screen | `captions.max_words_per_line` 3, or `captions.max_lines` 1 |
| all caps | `captions.uppercase` true |
| too choppy / cuts too tight | `cut.min_pause` 0.6, `cut.pad` 0.15 |
| tighter / faster | `cut.min_pause` 0.35 |
| put back the part where I say X | find X in `work/<name>/transcript/words.json`, add its source range to `cut.force_keep` |
| cut the part where I say X | add its source range to `cut.force_remove` |
| keep my "um"s | `cut.fillers` false |
| bed louder / quieter | `music.under_speech_db` down or up by 3 (stay within 15 to 24) |
| different bed / no bed | `music.track` to another file in `music\` made with `tools/video/sound.py`, or "none" |
| wrong word in the captions | `fixes` |
| add the source line / a REENACTMENT label / a cover box | editor-graphics skill, then `overlays` in edit.json |
| add a title card / lower third / graphic | editor-graphics skill, then `overlays` in edit.json |

After each revision, check it the same way (step 6), and tell the owner what changed in one or two lines.

## Channel rules

- Never change or delete raw footage. Never overwrite a draft. Never commit media (raw, references, done, work and music are git-ignored). This repo is public.
- Facts only from official records (RULES.md, Sources). Nothing is posted before the independent fact-check passes.
- On-screen text: no em dashes, no AI melody (RULES.md, Writing). Short and plain.
- No whispering at all. ElevenLabs voices (voiceover, pickups) follow RULES.md, Voice, and are made with `tools/voice/gen_vo.py`.
- Sound: the synthesized bed and effects only (`tools/video/sound.py`). Never use audio from references, licensed music or trending sounds.
- Never show a working scam link, a real scam phone number or a victim detail beyond the record.
- References are for study only.
