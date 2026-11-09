---
name: editor-taste
description: Learn the Scams on Record video style from 3 to 5 reference reels the owner likes (prompt 2) - download them for private study, measure pacing, speech, loudness, hooks and colours with analyze_ref.py, look at the contact sheets, then write editor/style.md in our own words and update editor/account.json within RULES.md. Take inspiration, never copy, never take facts from a reel. Use for "learn my taste from these reels", "study these reels", "learn my style", or when style.md is still a template.
---

# Editor taste (prompt 2)

Goal: a filled-in `editor/style.md` and matching numbers in `editor/account.json`, so every edit for this channel looks like this channel.
Take inspiration, but don't copy. Run Python only through the launcher: `bash editor/py.sh ...` (Git Bash) or `editor\py.cmd ...` (PowerShell). `RULES.md`, `persona/NARRATOR.md` and the look in `GAMEPLAN.md` win over anything a reference does.

## Steps

1. Get 3 to 5 links from the owner (TikTok, Instagram, YouTube Shorts). If fewer than 3, ask for more. Ask what they like about each in a few words, if they haven't said.
2. Download each one for private study into `references\`:
   `bash editor/py.sh tools/yt-dlp/fetch.py ref "<url>" --out references`
   It saves up to 720p plus a "REFERENCE ONLY" note with the source and creator. Instagram or private posts may need `--cookies-from-browser edge` (or chrome). Cloud sessions can't reach video sites, so this runs on the owner's PC. If a download fails, say which one and carry on with the rest.
3. Measure them: `bash editor/py.sh editor/tools/analyze_ref.py`
   Per reference it writes `references/<name>/analysis.json`, `contact.jpg` (16 frames), `hook.jpg` (first 3 seconds), `palette.png` and `transcript.txt`, and one `references/refs-analysis.json` with the medians.
4. Look with your own eyes (Read the images): every `hook.jpg`, `contact.jpg` and `palette.png`. Note for each: what happens in the first second, whether there's a hook title and how big, caption font weight, size, case, words per page, highlight colour, where captions sit, how often something new comes on screen, quote cards or documents on screen, how the source is shown, colour and light, sound bed or not.
5. Read the numbers: cuts per minute, average shot length, first cut, words per minute, first word time, loudness. Use the medians, and say when one reference is an outlier.
6. Write `editor/style.md` (keep its sections, change "Status" to filled in with the date and the references studied). Describe principles in our own words with our numbers, e.g. "first word by 0.3 s; a hook title of 3 to 5 words for the first 2.5 s; something new on screen every 2 to 3 s". Put ideas for the engine under "For the engine". Fill "What we will NOT copy" with the specific things from these references we leave alone.
7. Update `editor/account.json` to match, only where the references give a reason:
   - `cut.min_pause` (0.35 for very tight pacing, 0.45 default, 0.6 for a calmer feel) and `cut.pad`
   - `captions`: size, `max_words_per_line`, `max_lines`, `uppercase`; keep the channel's font (Inter Black) and colours (off-white #F6F7F9, yellow #FFD60A on the spoken word, near-black #080A10 outline)
   - `hook`: enabled, size, seconds
   - `music.under_speech_db` (18 to 22)
   Don't touch `presets` safe zones (RULES.md: content y 230 to 1300, captions at y 1440 max width 820, right edge clear below y 1000) or `loudness` (-14 LUFS) without the owner asking. Don't change `tools/video/engine.py` either.
8. Show the owner a short summary: 5 or 6 lines on what we're taking (in our words) and what we're not, plus the key numbers. Ask them to approve. If there's a recording in `raw\`, offer to make a draft with the new style (editor-edit skill).
9. After the owner approves the style, ask whether to delete the downloaded reference videos. The analysis folders can stay; they never go in git.

## Take inspiration, never copy

- Never reuse their footage, audio, music, voice, faces, logos or thumbnails in our videos.
- Never copy their exact caption design (their font, colours and animation together). We use the channel's fonts and colours.
- Never reuse their catchphrases, opening lines, sign-offs or jokes. Transcripts are for measuring pace, not for lines.
- Never copy their structure beat for beat. Take the principle ("show the outcome in the first 2 seconds"), not the sequence. Our structure is the seven beats in GAMEPLAN.md.
- Never take a fact, number, name or story from a reference. Facts come only from official records (RULES.md, Sources).
- Style.md describes principles in our own words. No quotes from their videos.
- The `reverse-any-video` and `style-sampling` skills rebuild other people's videos; don't use them on references.

## Channel rules that apply here too

- Everything written in style.md and on screen: no em dashes, no AI melody (RULES.md, Writing), plain words.
- The narrator never claims a job, a badge or a past (persona/NARRATOR.md). Never write a style that needs one.
- No whispering at all; tension comes from the order of events, not a hushed voice.
- References are for private study only and are never committed (git ignores `references/`). This repo is public.
