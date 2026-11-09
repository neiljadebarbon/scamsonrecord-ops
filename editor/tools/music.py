"""Put a music track under the voice, duck it while you talk, and set the final loudness for social.

  python editor/tools/music.py <video or voice audio> --music track.mp3 [--out mixed.mp4] [--words words.json]
  python editor/tools/music.py <video> --music none --out loud.mp4      loudness only, no music

What it does (numbers from editor/account.json "music", "voice" and "loudness"):
1. Voice clean-up: high-pass at 80 Hz and gentle compression (3:1), so the voice sits steady.
2. Measures the voice and the music in LUFS, then sets the music so it sits under_speech_db (20 dB)
   under the voice while you speak, and rises to gap_db (12 dB) under in longer gaps. The ducking is
   keyed from the voice itself (a sidechain): the music dips 0.1 s before you start talking (attack
   0.08 s), stays down through short gaps (hold 0.35 s) and comes back up gently (release 0.45 s).
3. Music fades in (0.5 s) and out (1.5 s) and loops if it's shorter than the video.
4. Two-pass loudness normalisation of the whole mix to -14 LUFS with true peak at or under -1 dBTP
   (what TikTok, Reels, Shorts and YouTube play back at).
5. Measures the result and reports it: final LUFS and true peak, and how far under the voice the
   music really sits during speech and in gaps.

Only use music you have the rights to (your own, licensed, or royalty-free with a licence that covers
social posts). Never use audio from references/: those reels are for study only. For trending sounds,
export without music (--music none) and add the sound in the TikTok/Instagram app.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import core

SR = 48000
HOP = 0.01


def voice_chain(vcfg: dict) -> str:
    parts = []
    if vcfg.get("highpass_hz"):
        parts.append(f"highpass=f={vcfg['highpass_hz']}")
    if vcfg.get("denoise"):
        parts.append("afftdn=nf=-25")
    if vcfg.get("compress", True):
        parts.append("acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=1")
    return ",".join(parts) or "anull"


def speech_mask(voice_mono, words=None, hold=0.35, lookahead=0.1):
    """True for each 10 ms frame where the voice is talking (holding through short gaps)."""
    import numpy as np
    db = core.frame_db(voice_mono, SR, HOP)
    thr = max(float(np.percentile(db, 10)) + 12, float(np.percentile(db, 95)) - 30)
    m = db > thr
    for w in words or []:
        m[int(w["start"] / HOP): int(w["end"] / HOP) + 1] = True
    # hold through gaps shorter than `hold`
    idx = np.flatnonzero(m)
    if len(idx):
        gaps = np.diff(idx)
        for a, g in zip(idx[:-1], gaps):
            if 1 < g <= hold / HOP:
                m[a:a + g] = True
    # start ducking a little before speech starts
    la = int(lookahead / HOP)
    starts = np.flatnonzero(np.diff(m.astype(int)) == 1) + 1
    for s in starts:
        m[max(0, s - la):s] = True
    return m, db


def envelope(mask, g_speech, g_gap, attack, release):
    """Per-frame music gain in dB: g_speech while talking, g_gap in gaps, smoothed (fast down, slow up)."""
    import numpy as np
    target = np.where(mask, g_speech, g_gap).astype(np.float64)
    out = np.empty_like(target)
    a_dn = 1 - np.exp(-HOP / max(attack, 1e-3))
    a_up = 1 - np.exp(-HOP / max(release, 1e-3))
    cur = target[0]
    for i, t in enumerate(target):
        cur += (t - cur) * (a_dn if t < cur else a_up)
        out[i] = cur
    return out


def _loudnorm_two_pass(src: Path, out: Path, lcfg: dict, codec_args: list[str], pre_args=(), post_args=()):
    I, TP, LRA = lcfg.get("target_lufs", -14), lcfg.get("true_peak", -1.0), lcfg.get("lra", 11)
    m = core.loudness(src)["raw"]
    chain = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
             f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
             f"linear=true:print_format=json,aresample={SR}")
    res = core.ffmpeg(["-y", "-v", "info", *pre_args, "-i", str(src), *post_args, "-af", chain, *codec_args, str(out)])
    txt = res.stderr.decode("utf-8", "replace")
    j = re.findall(r"\{[^{}]*\"normalization_type\"[^{}]*\}", txt, re.S)
    return json.loads(j[-1]).get("normalization_type", "?") if j else "?"


def mix(voice_src, music_src, out, settings: dict, words=None, work=None) -> dict:
    """Mix and normalise. out: .wav/.m4a (audio only) or .mp4/.mov (video copied from voice_src)."""
    import numpy as np
    out = core.guard_output(Path(out))
    work = Path(work or out.parent)
    work.mkdir(parents=True, exist_ok=True)
    mcfg, vcfg, lcfg = settings.get("music", {}), settings.get("voice", {}), settings.get("loudness", {})
    voice = core.decode_audio(voice_src, SR, 2, af=voice_chain(vcfg))
    n = len(voice)
    vpath = work / "voice.wav"
    core.write_audio(vpath, voice, SR, ["-c:a", "pcm_f32le"])
    v_l = core.loudness(vpath)
    report = {"voice_lufs": v_l["lufs"], "music": None}
    mixed = voice
    if music_src:
        mp = Path(music_src).resolve()
        refs = core.media_dir("references", create=False).resolve()
        if refs in mp.parents:
            raise core.ToolError("That track is in references/. Reference reels are for study only; use music you have the rights to.")
        music = core.decode_audio(mp, SR, 2)
        if len(music) < SR // 2:
            raise core.ToolError(f"{mp.name} is too short to use as music.")
        reps = int(np.ceil(n / len(music)))
        music = np.tile(music, (reps, 1))[:n] if reps > 1 else music[:n]
        mpath = work / "music-trim.wav"
        core.write_audio(mpath, music, SR, ["-c:a", "pcm_f32le"])
        m_l = core.loudness(mpath)
        rel = v_l["lufs"] - m_l["lufs"]
        under, gap = float(mcfg.get("under_speech_db", 20)), float(mcfg.get("gap_db", 12))
        mask, vdb = speech_mask(voice.mean(axis=1), words, float(mcfg.get("hold", 0.35)))
        env_db = envelope(mask, rel - under, rel - gap, float(mcfg.get("attack", 0.08)), float(mcfg.get("release", 0.45)))
        t_frames = (np.arange(len(env_db)) + 0.5) * HOP
        t = np.arange(n) / SR
        g = 10 ** (np.interp(t, t_frames, env_db) / 20)
        fi, fo = float(mcfg.get("fade_in", 0.5)), float(mcfg.get("fade_out", 1.5))
        g *= np.clip(t / max(fi, 1e-3), 0, 1) * np.clip((n / SR - t) / max(fo, 1e-3), 0, 1)
        ducked = music * g[:, None].astype(np.float32)
        mixed = voice + ducked
        # measured result: level of the ducked music against the voice, speech frames vs gaps
        mdb = core.frame_db(ducked.mean(axis=1), SR, HOP)[: len(mask)]
        vdb = vdb[: len(mdb)]
        mk = mask[: len(mdb)]
        loud = vdb > np.percentile(vdb, 50)
        sp = mk & loud
        diff_speech = float(np.median(vdb[sp] - mdb[sp])) if sp.any() else None
        interior = (t_frames[: len(mdb)] > fi + 0.3) & (t_frames[: len(mdb)] < n / SR - fo - 0.3)
        gp = ~mk & interior
        report["music"] = {
            "track": str(mp), "music_lufs": m_l["lufs"], "looped": reps > 1,
            "set_under_speech_db": under, "set_gap_db": gap,
            "measured_under_speech_db": round(diff_speech, 1) if diff_speech is not None else None,
            "measured_gap_db": round(float(np.median(vdb[sp]) - np.median(mdb[gp])), 1) if gp.any() and sp.any() else None,
            "gap_seconds": round(float(gp.sum() * HOP), 2),
        }
    mpath = work / "mix.wav"
    core.write_audio(mpath, mixed, SR, ["-c:a", "pcm_f32le"])
    kbps = settings.get("presets", {}).get(settings.get("export", {}).get("preset", "reel"), {}).get("audio_kbps", 192)
    if out.suffix.lower() in (".mp4", ".mov", ".m4v", ".mkv"):
        tmp_audio = work / "mix-normalised.m4a"
        ntype = _loudnorm_two_pass(mpath, tmp_audio, lcfg, ["-c:a", "aac", "-b:a", f"{kbps}k"])
        core.ffmpeg(["-y", "-v", "error", "-i", str(voice_src), "-i", str(tmp_audio), "-map", "0:v:0", "-map", "1:a:0",
                     "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(out)])
    else:
        codec = ["-c:a", "pcm_s24le"] if out.suffix.lower() == ".wav" else ["-c:a", "aac", "-b:a", f"{kbps}k"]
        ntype = _loudnorm_two_pass(mpath, out, lcfg, codec)
    final = core.loudness(out)
    report.update({"normalization": ntype, "final_lufs": final["lufs"], "final_true_peak": final["true_peak"],
                   "final_lra": final["lra"], "target_lufs": lcfg.get("target_lufs", -14),
                   "target_true_peak": lcfg.get("true_peak", -1.0), "out": str(out)})
    for f in (vpath, work / "music-trim.wav"):
        f.unlink(missing_ok=True)
    return report


def pick_track(choice, media=None) -> Path | None:
    """'none' -> None, a path -> that file, 'auto' -> newest audio file in music/."""
    if not choice or str(choice).lower() == "none":
        return None
    if str(choice).lower() != "auto":
        p = Path(choice)
        if not p.is_absolute() and not p.exists():
            # "bed.mp3" and "music/bed.mp3" both mean the file in the account's music/ folder
            music_dir = core.media_dir("music", media)
            for cand in (music_dir.parent / p, music_dir / p, music_dir / p.name):
                if cand.exists():
                    p = cand
                    break
        if not p.exists():
            raise core.ToolError(f"Music track not found: {choice}")
        return p
    return core.newest_file(core.media_dir("music", media), kinds=("audio",))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", help="video (or voice audio) to put music under")
    p.add_argument("--music", default=None, help="track file, 'auto' (newest in music/) or 'none'")
    p.add_argument("--out", help="output .mp4 (video copied) or .wav/.m4a (default <input>-mix.mp4)")
    p.add_argument("--words", help="words.json for the same timeline (helps the ducking)")
    p.add_argument("--under", type=float, help="dB under the voice while talking (default 20)")
    p.add_argument("--account")
    p.add_argument("--media")
    a = p.parse_args(argv)
    try:
        settings = core.load_account(a.account)
        if a.under is not None:
            settings["music"]["under_speech_db"] = a.under
        src = Path(a.input)
        out = Path(a.out) if a.out else src.with_name(src.stem + "-mix.mp4")
        track = pick_track(a.music if a.music is not None else settings["music"].get("track", "auto"), a.media)
        words = core.load_words(a.words) if a.words else None
        rep = mix(src, track, out, settings, words, work=out.parent)
        m = rep["music"]
        if m:
            print(f"music: {Path(m['track']).name} set {m['set_under_speech_db']} dB under, measured {m['measured_under_speech_db']} dB under the voice while talking")
        else:
            print("no music (voice only)")
        print(f"final loudness {rep['final_lufs']} LUFS, true peak {rep['final_true_peak']} dBTP ({rep['normalization']}) -> {out}")
        return 0
    except core.ToolError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
