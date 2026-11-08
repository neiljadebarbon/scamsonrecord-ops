# Script brief: one episode

Read first: `RULES.md`, `persona/NARRATOR.md`, `GAMEPLAN.md`, and `episodes/Caught 001 - Grandparent Scam Courier/` as the file format example.

## Steps
1. Pick the source and save it in `source/source.md`: URL, date, office, and the facts you will use, each with the short source wording.
2. Decide the one takeaway (one sentence in `script/script.md`). Cut anything that doesn't serve it.
3. Write the seven beats (GAMEPLAN.md beat sheet), 170 to 190 spoken words.
4. AI-melody pass on every paragraph (RULES.md list).
5. Independent fact-check by a reviewer who did not write it. Table goes in `script/script.md`. Fix and re-check until PASS.
6. Only then: voice, alignment, render, mix.

## Files per episode
- `source/source.md`: the facts and where they come from.
- `script/voice.json`: `[[tag, text, pause_seconds], ...]`, one entry per beat, numbers spelled as spoken. Tag: `[calm, serious, storytelling] `. Pauses 0.6 to 0.9, uneven, last one 0.
- `script/captions.json`: per beat, the chunks shown on screen: `{"display": "In January 2021,", "spoken": "In January twenty twenty-one,"}`. The spoken chunks joined must equal the beat's text in `voice.json` word for word.
- `script/script.md`: title, takeaway, the voiceover, every on-screen text, word count, the fact-check table with verdict, posting copy.
- `audio/<name>_voice.mp3`, `.timeline.json`, `_words.json`: from `tools/voice/gen_vo.py` and `tools/voice/align.py`.
- `video/render.py`: the episode's scenes on top of `tools/video/engine.py`. Start from the last episode's file. `video/events.json` drives the sound effects.
- `video/<name>.mp4`: the final cut.
