---
name: editor-graphics
description: Add graphics to a Scams on Record editor draft - the source line, a REENACTMENT label, a cover box over a scam link or phone number, title cards, lower thirds, callouts - made with HyperFrames (2D motion graphics, skills installed for the Windows user) or the channel's own engine parts (tools/video/kit.py), rendered with transparency and laid over the cut via overlays in work/<name>/edit.json. Use for "add the source line", "cover that number", "add a title card", "put a lower third", "animate this", "add a graphic".
---

# Editor graphics

Goal: on-brand graphics on a draft, placed on the spoken word, inside the safe zones, rendered the same way every time.

## Which tool

| Need | Tool | Where |
|---|---|---|
| Source line, REENACTMENT label, lower third, callout, kinetic text, end card, simple chart | HyperFrames (HTML to video) | the `hyperframes`, `hyperframes-cli` and `hyperframes-registry` skills (installed for the Windows user by editor-setup; read `hyperframes` first). Runs with `npx hyperframes`. |
| The channel's own parts: glass cards, chips, quote cards, stamps, stat rows, red-flag rows | the engine | `tools/video/engine.py` and `tools/video/kit.py`; an episode's `video/render.py` shows how they're used |
| Cover a scam link, a phone number or a personal detail | a plain PNG box | `work/<name>/graphics/cover.png`, sized to the area, near-black #080A10 or a blurred crop |

Pick HyperFrames for a new motion graphic, and the engine parts when the graphic should look exactly like an episode. Don't change `tools/video/engine.py` or `kit.py` for one video: write a small script in `work/<name>/graphics/` that imports them. If the HyperFrames skills aren't installed, run the editor-setup step for them first.

## Steps

1. Read the cut's words with times: `work/<name>/cut/words.json` (seconds on the draft's timeline). Anchor every graphic to a spoken word, never to a guessed second. The source line runs for the last 10 seconds.
2. Design inside the safe zones of a 1080x1920 reel (RULES.md, Video; `editor/account.json` presets):
   - content between y 230 and 1300
   - captions own the band around y 1440 (y 1310 to 1570); keep graphics out of it
   - nothing important right of x 940 below y 1000 (TikTok's buttons)
   - brand (tools/video/engine.py): near-black #080A10 to #0C101E ground, off-white #F6F7F9, muted #949EB0, yellow #FFD60A, red #FF4545, green #30D158, paper #F3F0E9 with ink #18181C for quote cards; Inter Black and Inter Display Black (in `editor/fonts`)
   - motion eases (fast start, soft landing), nothing pops or flashes without a reason, few words
3. Render with transparency at the reel's width (1080): ProRes 4444 `.mov` or VP9 `.webm` with alpha (HyperFrames can do both), or a `.png` for a still. A full-screen card with no transparency can be a plain `.mp4`. Put renders in `work/<name>/graphics/`.
4. Look at a still of the graphic before using it.
5. Add it to `work/<name>/edit.json`:
   `"overlays": [{"file": "graphics/source-line.mov", "at": 21.8, "until": 31.8, "x": 0, "y": 1180}]`
   (`at` and `until` are seconds on the draft's timeline; `x`, `y` put the graphic's top-left corner on the frame; a `.png` without `until` stays 3 seconds.) Captions stay on top of graphics.
6. Make the next draft: `bash editor/py.sh editor/tools/edit.py --name <name> --note "<the owner's note>" --changes "added source line 21.8 to 31.8 s"` (or `editor\py.cmd` in PowerShell).
7. Check `work/<name>/review-vN/` images and a frame in the middle of each graphic (`guides.png` shows the zones). Then report.

For a quick one-off test without edit.json: `bash editor/py.sh editor/tools/export.py work/<name>/cut/cut.mp4 --name <name> --ass work/<name>/captions.ass --audio work/<name>/mix.m4a --overlay "work/<name>/graphics/title.mov@0.0-2.5@0,400"`.

## Channel rules

- Every word on screen is checked against the official record (RULES.md, Big Law). Quotes are labelled by what they are ("FROM THE U.S. ATTORNEY'S RELEASE"); "court record" only for a court filing. Agency seals and logos stay out.
- The source line names the record (office and date, or the short URL); the full URL goes in the post caption.
- Mock-up texts and calls only under a REENACTMENT label, and only as the record describes them. Never a working scam link or a real scam phone number.
- On-screen text: no em dashes, no AI melody, short.
- Never use other creators' graphics, footage or music. References are for study only.
- HyperFrames telemetry stays off (`.claude/settings.json` sets it); don't change that file. Don't sign in or publish with HyperFrames unless the owner asks.
