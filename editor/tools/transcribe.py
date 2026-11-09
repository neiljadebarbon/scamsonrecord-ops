"""Transcribe speech with faster-whisper, with a start and end time for every word.

  python editor/tools/transcribe.py <video or audio> [--out DIR] [--model small.en] [--language en]

Writes into DIR (default work/<name>/transcript/):
  words.json       every word with start/end seconds and confidence (cut.py and captions.py read this)
  transcript.txt   plain text, one line per sentence; words Whisper was unsure of are marked [?word]
  captions.srt     upload-ready captions (YouTube, Facebook, LinkedIn)
  captions.vtt     the same as WebVTT
  captions.ass     word-by-word highlighted captions styled from editor/account.json

Audio is decoded by ffmpeg to 16 kHz mono float32 and handed to Whisper as an array, because
faster-whisper 1.2.1's own loader breaks with newer PyAV builds.

Model: small.en by default (English, about 480 MB, fine on a CPU). Use --model medium.en for harder
audio or --model small with --language for other languages. A model already in the default Hugging Face
cache (~/.cache/huggingface/hub) is used from there; new downloads go to editor/models (git-ignored),
or wherever EDITOR_WHISPER_MODELS / --models-dir points. Never commit a model. Whisper uses up to 8 CPU
threads (EDITOR_WHISPER_THREADS to change).

The account's vocabulary (account.json whisper.vocabulary: "names, brands and special words ...") is given to
Whisper as a hint so the account's words and names come out spelled right. With write_fillers on, the hint
also nudges Whisper to write "um" and "uh", so cut.py can remove them.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

import core

FILLER_HINT = "Umm, uh, so, let me think. Uh, okay."


def model_repo(name: str) -> str:
    try:
        from faster_whisper.utils import _MODELS
        if name in _MODELS:
            return _MODELS[name]
    except Exception:
        pass
    return name if "/" in name else f"Systran/faster-whisper-{name}"


def hf_cache() -> Path:
    """The default Hugging Face cache (where a plain faster-whisper install puts models)."""
    try:
        from huggingface_hub.constants import HF_HUB_CACHE
        return Path(HF_HUB_CACHE)
    except Exception:
        return Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"


def model_downloaded(name: str, mdir: Path, also_hf_cache: bool = True) -> Path | None:
    """Path to the model's files if already downloaded: a local folder, the editor's cache, or the default HF cache."""
    p = Path(name)
    if p.is_dir() and (p / "model.bin").exists():
        return p
    sub = "models--" + model_repo(name).replace("/", "--")
    for root in [mdir] + ([hf_cache()] if also_hf_cache else []):
        folder = root / sub / "snapshots"
        for snap in sorted(folder.glob("*")) if folder.exists() else []:
            if (snap / "model.bin").exists():
                return snap
    return None


def load_model(name: str, models_dir=None, allow_download=True):
    from faster_whisper import WhisperModel
    mdir = core.models_dir(models_dir)
    local = model_downloaded(name, mdir)
    if not local and not allow_download:
        raise core.ToolError(f"Whisper model {name} is not downloaded. Run: python editor/tools/doctor.py --download-model")
    if not local:
        print(f"Downloading Whisper model {name} into {mdir} (one time) ...", flush=True)
    threads = int(os.environ.get("EDITOR_WHISPER_THREADS") or min(os.cpu_count() or 4, 8))
    return WhisperModel(str(local) if local else name, device="cpu", compute_type="int8", cpu_threads=threads,
                        download_root=str(mdir), local_files_only=bool(local))


def transcribe(path, model_name="small.en", language="en", vocabulary="", write_fillers=True,
               models_dir=None, beam_size=5, model=None) -> dict:
    """Words with times for a media file. Returns {"words": [...], "segments": [...], ...}."""
    t0 = time.time()
    audio = core.decode_audio(path, 16000)
    dur = len(audio) / 16000
    if dur < 0.3:
        raise core.ToolError(f"{path} has no usable audio.")
    model = model or load_model(model_name, models_dir)
    prompt = " ".join(x for x in [FILLER_HINT if write_fillers else "", vocabulary or ""] if x).strip() or None
    lang = language or None
    if model_name.endswith(".en"):
        lang = "en"
    segments, info = model.transcribe(audio, language=lang, word_timestamps=True, beam_size=beam_size,
                                      vad_filter=False, condition_on_previous_text=False, initial_prompt=prompt)
    words, segs = [], []
    for s in segments:
        if s.no_speech_prob > 0.6 and s.avg_logprob < -1.0:
            continue  # likely a hallucination over silence
        segs.append({"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text.strip()})
        for w in s.words or []:
            text = w.word.strip()
            if not text:
                continue
            words.append({"word": text, "start": round(w.start, 3), "end": round(w.end, 3), "prob": round(w.probability, 3)})
    # keep times sane: increasing, inside the file, at least 40 ms long
    last = 0.0
    for w in words:
        w["start"] = max(w["start"], last)
        w["end"] = min(max(w["end"], w["start"] + 0.04), dur)
        last = w["start"]
    return {"source": str(Path(path).resolve()), "fingerprint": core.fingerprint(path), "duration": round(dur, 3),
            "model": model_name, "language": info.language, "prompt": prompt, "created": core.now(),
            "seconds_taken": round(time.time() - t0, 1), "words": words, "segments": segs}


def transcript_text(words: list[dict], low_prob=0.45) -> str:
    lines, cur = [], []
    for w in words:
        t = w["word"]
        cur.append(f"[?{t}]" if w.get("prob", 1) < low_prob else t)
        if re.search(r"[.?!]$", t):
            lines.append(" ".join(cur))
            cur = []
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines) + "\n"


def write_outputs(data: dict, out: Path, settings: dict | None = None, preset=None) -> dict:
    import captions
    out.mkdir(parents=True, exist_ok=True)
    core.write_json(out / "words.json", data)
    (out / "transcript.txt").write_text(transcript_text(data["words"]), encoding="utf-8")
    fixes = (settings or {}).get("fixes")
    captions.write_srt(data["words"], out / "captions.srt", fixes)
    captions.write_vtt(data["words"], out / "captions.vtt", fixes)
    rep = None
    if settings:
        rep = captions.write_ass(data["words"], out / "captions.ass", settings, preset or settings["export"]["preset"])
    return {"dir": str(out), "ass": rep}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", help="video or audio file")
    p.add_argument("--out", help="output folder (default work/<name>/transcript)")
    p.add_argument("--model", help="Whisper model (default from account.json, small.en)")
    p.add_argument("--language", help="language code, e.g. en, es, tl (default from account.json)")
    p.add_argument("--models-dir", help="model cache folder (default editor/models or EDITOR_WHISPER_MODELS)")
    p.add_argument("--no-fillers", action="store_true", help="don't nudge Whisper to write um/uh")
    p.add_argument("--account", help="account.json to use")
    p.add_argument("--media", help="media root (default: repo root or EDITOR_MEDIA)")
    a = p.parse_args(argv)
    try:
        settings = core.load_account(a.account)
        w = settings.get("whisper", {})
        src = Path(a.input)
        out = Path(a.out) if a.out else core.media_dir("work", a.media) / core.slugify(src.stem) / "transcript"
        core.guard_output(out, a.media)
        data = transcribe(src, a.model or w.get("model", "small.en"), a.language or w.get("language", "en"),
                          w.get("vocabulary", ""), w.get("write_fillers", True) and not a.no_fillers, a.models_dir)
        write_outputs(data, out, settings)
        unsure = sum(1 for x in data["words"] if x["prob"] < 0.45)
        print(f"{len(data['words'])} words in {data['duration']:.1f} s of audio ({data['seconds_taken']} s to transcribe), "
              f"{unsure} unsure -> {out}")
        return 0
    except core.ToolError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
