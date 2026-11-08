# scamsonrecord-ops

The playbook and production kit for **Scams on Record**, a faceless short-video channel (TikTok, YouTube Shorts, Instagram Reels, Facebook Reels). One real scam case per video, told from official records, with the source on screen.

**Start here:** `GAMEPLAN.md` for what the channel is and how it runs. Then `RULES.md` and `persona/NARRATOR.md` before writing anything.

## Folders

- `GAMEPLAN.md`: the channel plan. Series, formats, beat sheet, weekly routine, money path.
- `RULES.md`: the laws. Independent fact-check, no AI melody, accuracy rules, voice settings, video spec, posting checklist.
- `persona/NARRATOR.md`: who the narrator is and what never to invent.
- `SCRIPT_BRIEF.md`: how to write one episode, file formats, what to deliver.
- `tools/voice/`: ElevenLabs voiceover generator with stutter, pace and whisper checks (`gen_vo.py`, `qc.py`), word alignment for captions (`align.py`).
- `tools/video/`: the motion engine (`engine.py`: background, glass cards, word-synced captions, transitions), reusable scene parts (`kit.py`: chips, pins, maps, quote cards, stamps, stat rows, red-flag rows), and the synthesized sound bed and final mix (`sound.py`).
- `episodes/`: one folder per episode (`Caught 001 - Grandparent Scam Courier/`, `Caught 002 - Gold Bar Courier/`) with `source/`, `script/`, `audio/`, `video/`. Start a new episode from the latest one's `video/render.py`.

## Make an episode

```
python3 tools/voice/gen_vo.py "<ep>/script/voice.json" /tmp/vo "<ep>/audio/<name>_voice.mp3"
python3 tools/voice/align.py "<ep>/audio/<name>_voice.mp3" "<ep>/audio/<name>_voice.timeline.json" "<ep>/audio/<name>_words.json"
python3 "<ep>/video/render.py" video /tmp/noaudio.mp4
python3 "<ep>/video/render.py" events "<ep>/video/events.json"
python3 tools/video/sound.py bed "<ep>/video/events.json" /tmp/bed.wav
python3 tools/video/sound.py mix "<ep>/audio/<name>_voice.mp3" /tmp/bed.wav /tmp/noaudio.mp4 "<ep>/video/<name>.mp4"
```

Needs Python 3 with `numpy`, `Pillow`, `pocketsphinx`, plus `ffmpeg`. Fonts: Inter and DejaVu (paths in `tools/video/engine.py`).

## Keys

This repo is **public**. The ElevenLabs key never goes in a file here. Set `XI` (or `ELEVENLABS_API_KEY`) in the environment, or put it in a local `.env` file, which `.gitignore` keeps out of commits.
