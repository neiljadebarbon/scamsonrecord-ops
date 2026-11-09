# Style: Scams on Record short videos

The editor-taste skill fills this in after studying 3 to 5 reference reels the owner likes, and keeps `editor/account.json` in step with it. Write in our own words. Describe principles, never a copy of someone else's video. `RULES.md`, `persona/NARRATOR.md` and the look in `GAMEPLAN.md` always win over anything here.

Status: TEMPLATE (not filled in yet)
References studied: (names and links, date)
Numbers from: `references/refs-analysis.json`

## Hook (first 3 seconds)

- What happens before the first word (target: first word by about 0.3 s):
- On-screen hook title: yes or no, how many words, size, where (inside the content zone, y 230 to 1300):
- What the first line does (the strongest true fact from the record, stated plainly; no movie-trailer opener):
- First cut or visual change by (seconds; GAMEPLAN: something new on screen every 2 to 3 seconds):

## Pacing

- Cuts or visual changes per minute (references median / ours):
- Average shot length:
- Pauses: cut above 0.45 s, keep 0.12 s each side (change in account.json `cut`):
- Speaking pace (wpm) and target length (61 to 100 seconds; Caught episodes about 90):

## Captions

- Font, weight, size, case (ours: Inter Black, 85 in account.json, sentence case):
- Words per line, lines per page:
- Colours (ours: off-white #F6F7F9 text, yellow #FFD60A on the spoken word, near-black #080A10 outline):
- Position (fixed by RULES.md: centred on y 1440, max width 820, right edge clear below y 1000):

## Colour

- Main colours seen in the references (palette.png) and what we take from them:
- Our palette (tools/video/engine.py): near-black #080A10 to #0C101E ground, off-white #F6F7F9, muted #949EB0, yellow #FFD60A, red #FF4545, green #30D158, paper #F3F0E9, ink #18181C; red, blue and orange glows.
- Look of the footage (brightness, warmth, contrast):

## Music and sound

- Synthesized bed and effects only (`tools/video/sound.py`), ducked under the voice (default: 20 dB under while talking):
- Sound effects (sparing, on a cut, a number or a stamp):
- Final loudness: -14 LUFS, true peak -1.5 dBTP.
- Voice: no whispering at all; full voice on tension beats.

## Graphics

- Quote cards, chips, stamps, red-flag rows (the engine, `tools/video/kit.py`) and HyperFrames overlays: when and how often:
- Source line on screen for the last 10 seconds; REENACTMENT label on any mock-up.
- Text on screen stays short, true and checked against the official record.

## For the engine

- Anything from the references that should change `tools/video/engine.py` or an episode's `render.py` (caption size, pacing of on-screen changes). Ideas only; the owner decides before any engine change.

## What we will NOT copy

- Their footage, music, voice, faces, logos or thumbnails.
- Their exact caption design (same font, colours and animation together).
- Their catchphrases, opening lines or sign-offs.
- Their structure beat for beat (ours is the seven beats in GAMEPLAN.md).
- Their facts, numbers or story details: a reel is never a source. Facts come only from official records.
