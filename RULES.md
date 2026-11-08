# Rules: read before making any episode

Also read `persona/NARRATOR.md`.

## BIG LAW: independent fact-check of every script
No script is final, and no audio or video is published, until a separate reviewer who did not write it has checked every claim in the voiceover AND every word on screen against the official source. The reviewer rules each claim OK, WRONG, UNSUPPORTED or OVERSTATED, quotes the source wording, and gives the fix. If anything fails: fix the script, regenerate only the changed paragraphs, re-align, re-render. The fact-check table goes in the episode's `script/script.md`.

Caught #1 is why this matters. The first script put "38-year-old" on events from 2021 when 38 was his age at sentencing in 2024, and labeled a press release quote "court record". Both were caught by the reviewer.

## Sources
- Story facts only from official records: DOJ and U.S. Attorney's Office press releases (justice.gov), FTC (consumer.ftc.gov, ftc.gov), FBI and IC3 (fbi.gov, ic3.gov), state attorney general sites, court filings.
- Safety advice from FTC or FBI pages, checked each time.
- Label quotes by what they are: "FROM THE U.S. ATTORNEY'S RELEASE", "FROM THE FTC ALERT", "FROM THE INDICTMENT". Say "court record" only for an actual court filing.
- Federal agency text is public domain and can be shown word for word. State, local and news text is copyrighted: facts only, own words, headline and outlet name at most. Agency seals and logos stay out.
- Source line on screen for the last 10 seconds, source URL in the post caption.

## Accuracy
- Charged is not convicted: "accused" and "prosecutors say" until a plea or verdict.
- Ages, dates and amounts exactly as the record states them, with whose age and when.
- Totals stay totals. Restitution of $867,149 to all victims is never "she lost $867,149".
- Reenactments only on screen, labeled REENACTMENT, consistent with the record.
- Never show a working scam link, a real scam phone number, or any victim detail beyond the record.
- Never explain how to run a scam: no spoofing, no buying data, no getting around bank checks. Show the scam as the target sees it.

## Writing: no "AI melody"
- No rule-of-three lists, no "here's the thing", no "it's not just X, it's Y", no "what most people don't realize".
- No setup-then-reveal lines ("Then comes the catch.", "Here's where it gets dark."). Say the thing.
- No movie-trailer openers ("Picture this...", "$X. That's what..."). Open with the fact itself.
- No rhetorical-question transitions, at most one per episode.
- No tidy moral at the end. The close is the practical step and the follow line.
- Uneven sentence lengths. Contractions. Plain words. No em dashes.
- Banned words: nuance, delve, quietly, landscape, journey, game-changer, buckle up, let's dive in, stick around, trust me.
- Vary paragraph openers. Never two in a row starting the same way.

## Voice
- ElevenLabs voice `7mN3HOhMedH0rcubaqVy`, model `eleven_v4`, stability 0.4 (env `STABILITY`), similarity 0.8.
- This is a true-crime story channel, so the voice acts. Each beat gets its own emotion tag that fits what's happening (set on Caught #1):
    - Hook: `[grave, serious] `
    - Setup: `[low, suspenseful] `
    - Trust: `[tense, worried] `
    - The ask: `[hushed, ominous] `
    - The fall: `[intrigued, building tension] `
    - Ending: `[firm, matter-of-fact] `
    - Red flags: `[warm, direct, protective] `
- **No whispering (owner rule, Nov 8).** Never use hushed, whisper, low or ominous tags; Caught #1's "[hushed, ominous]" came out whispered. Tension tags get "full voice" added, e.g. `[building tension, full voice] `. `tools/voice/qc.py` measures the voiced share of every take and `gen_vo.py` retakes anything under 0.58.
- Be a storyteller: tags like `[serious, gripping storyteller]`, `[curious, conversational storyteller]`, `[concerned, emphatic]`, `[dramatic, emphatic]`, `[firm, serious]`, `[warm, direct, protective]`. Pick each from what the beat is doing.
- Dramatic pauses with "..." inside a line (before the sentence length, before the gag order's consequence, before "hang up"). Captions don't show them.
- Pauses of 0.6 to 0.9 s between paragraphs (uneven), then a 5% slowdown (atempo 0.95). `tools/voice/gen_vo.py` does it and retakes any paragraph with a stutter, a doubled word or a pace outside 115 to 235 wpm.
- Spell numbers the way they're said in `voice.json`: "eight hundred sixty-seven thousand dollars", "twenty twenty-one". Captions show digits.
- Key: environment variable `XI` or `ELEVENLABS_API_KEY`, or a local `.env`. Never in a committed file. This repo is public.

## Video
- 1080 x 1920, 30 fps, 61 to 100 seconds (TikTok only pays on videos over one minute). Caught episodes run about 90 seconds (owner, Nov 8).
- Seven beats: hook, setup, trust, the ask, the fall, ending, red flags (see GAMEPLAN.md).
- Content stays between y 230 and 1300. Captions sit at y 1440, max width 820. Keep the right edge clear below y 1000 (TikTok buttons).
- Word-synced captions from `tools/voice/align.py`; the active word is yellow.
- Sound: synthesized bed and effects only (`tools/video/sound.py`), ducked under the voice, final mix about -14 LUFS.

## Posting checklist
1. Fact-check table in `script/script.md` shows PASS.
2. TikTok: Personal account, AI-generated label ON (the voice is AI), source URL in the caption.
3. Upload the clean MP4 to TikTok, YouTube Shorts, Instagram Reels and Facebook Reels. Never repost a downloaded TikTok with its watermark.
4. Pin the episode number in the title: "Caught #N: ...".
