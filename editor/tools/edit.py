"""Raw recording to draft in one go: transcribe, cut, check, captions, music, export, review.

  python editor/tools/edit.py                                newest video in raw/
  python editor/tools/edit.py raw/IMG_0412.MOV --name par-explained --hook "What does *par* mean?"
  python editor/tools/edit.py --name par-explained --note "make the hook bigger"   (after editing edit.json)

Steps (each writes into work/<name>/, nothing in raw/ is ever changed):
  1. transcribe   Whisper words with times (reused on later runs if the raw file hasn't changed)
  2. cut          pauses, fillers and retakes out (edl.json lists every removal), re-encoded in sync
  3. check        Whisper listens to the cut again: are all the words still there, and where?
                  (kept_pct, missing words, timing drift). A low score means look before sending.
  4. captions     word-by-word .ass from the re-timed words + the hook title; also captions.srt
  5. music        track under the voice with ducking, then -14 LUFS / -1 dBTP
  6. export       done/<name>-draft-vN.mp4 (N goes up every run; old drafts are never overwritten)
  7. review       hook frames, contact sheet, safe-zone frame and loudness in work/<name>/review-vN/
  8. report       work/<name>/report-vN.md with the numbers

Per-video settings live in work/<name>/edit.json, made on the first run. It holds only what differs
from editor/account.json for this video, in the same shape, for example:
  {"hook": {"text": "What does *par* mean?", "size": 130}, "captions": {"size": 100},
   "cut": {"force_keep": [[12.4, 15.0]]}, "music": {"track": "music/calm-guitar.mp3", "under_speech_db": 22},
   "fixes": {"birdy": "birdie"},
   "overlays": [{"file": "graphics/title.mov", "at": 0.0, "until": 2.5}]}   (graphics: see editor-graphics skill)
To act on the owner's notes: change edit.json, run edit.py again with the same --name, and record the
note with --note and what you changed with --changes. The result is the next draft number.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import core
import captions
import cut as cutmod
import export as exportmod
import music as musicmod
import review as reviewmod
import transcribe as tr

SECTIONS = ("captions", "hook", "cut", "music", "fixes", "voice", "loudness", "export", "whisper")


def load_edit(work: Path, src: Path, fp: str) -> dict:
    p = work / "edit.json"
    data = core.read_json(p)
    if data is None:
        data = {"_about": "This video's changes from editor/account.json (same shape). Edit, then run edit.py again with the same --name.",
                "source": str(src.resolve()), "fingerprint": fp, "preset": None,
                "hook": {"text": ""}, "captions": {}, "cut": {}, "music": {}, "fixes": {}, "history": []}
    elif data.get("fingerprint") and data["fingerprint"] != fp:
        raise core.ToolError(f"work/{work.name}/edit.json belongs to a different recording ({data.get('source')}). "
                             f"Use --name to give this video its own name.")
    return data


def run(args) -> dict:
    media = args.media
    account = core.load_account(args.account)
    raw = core.media_dir("raw", media)
    src = Path(args.input) if args.input else None
    if src is None and args.name:
        prev = core.read_json(core.media_dir("work", media) / args.name / "edit.json")
        src = Path(prev["source"]) if prev else None
    src = src or core.newest_file(raw)
    if not src or not src.exists():
        raise core.ToolError(f"No video found. Put the recording in {raw} (or give its path).")
    src = src.resolve()
    name = args.name or core.slugify(src.stem)
    work = core.media_dir("work", media) / name
    work.mkdir(parents=True, exist_ok=True)
    core.guard_output(work, media)
    fp = core.fingerprint(src)
    edit = load_edit(work, src, fp)
    if args.hook is not None:
        edit.setdefault("hook", {})["text"] = args.hook
    if args.preset:
        edit["preset"] = args.preset
    if args.music is not None:
        edit.setdefault("music", {})["track"] = args.music
    settings = core.settings_for(account, {k: edit.get(k) for k in SECTIONS if isinstance(edit.get(k), dict)})
    preset_name = edit.get("preset") or settings["export"]["preset"]
    preset = settings["presets"][preset_name]
    # pin the music choice so later drafts use the same track
    track = musicmod.pick_track(settings["music"].get("track", "auto"), media)
    edit.setdefault("music", {})["track"] = str(track) if track else "none"
    log = lambda s: print(s, flush=True)

    # 1. transcribe (cached)
    wcfg = settings.get("whisper", {})
    model = args.model or wcfg.get("model", "small.en")
    tdir = work / "transcript"
    cached = core.read_json(tdir / "words.json")
    prompt_now = " ".join(x for x in [tr.FILLER_HINT if wcfg.get("write_fillers", True) else "", wcfg.get("vocabulary", "")] if x).strip() or None
    whisper_model = None
    if cached and cached.get("fingerprint") == fp and cached.get("model") == model and cached.get("prompt") == prompt_now:
        log(f"1/7 transcript: reusing {len(cached['words'])} words")
        tdata = cached
    else:
        log(f"1/7 transcribing with Whisper {model} ...")
        whisper_model = tr.load_model(model, args.models_dir)
        tdata = tr.transcribe(src, model, wcfg.get("language", "en"), wcfg.get("vocabulary", ""),
                              wcfg.get("write_fillers", True), args.models_dir, model=whisper_model)
        tr.write_outputs(tdata, tdir, settings, preset_name)
        log(f"    {len(tdata['words'])} words in {tdata['seconds_taken']} s")
    words = tdata["words"]

    # 2. cut
    cdir = work / "cut"
    cdir.mkdir(exist_ok=True)
    audio = core.decode_audio(src, 16000)
    edl = cutmod.plan(words, audio, 16000, len(audio) / 16000, settings["cut"], float(preset["fps"]))
    edl.update({"source": str(src), "preset": preset_name})
    cwords = cutmod.retime(words, edl)
    state = core.hash_obj({"fp": fp, "keep": edl["keep"], "preset": preset_name, "fit": settings["export"].get("fit")})
    old = core.read_json(cdir / "edl.json", {})
    core.write_json(cdir / "edl.json", edl)
    core.write_json(cdir / "words.json", {"source": str(cdir / "cut.mp4"), "words": cwords})
    s = edl["summary"]
    log(f"2/7 cut: {s['before_s']} s -> {s['after_s']} s, {s['pauses']} pauses, {s['fillers']} fillers, {s['retakes']} retakes")
    if s.get("words_lost"):
        log(f"    WARNING: {s['words_lost']} words have no audio left in the cut: {s.get('lost_words')}")
    if args.plan_only:
        core.write_json(work / "edit.json", edit)
        return {"work": str(work), "edl": edl}
    if old.get("state") == state and (cdir / "cut.mp4").exists() and (cdir / "cut.wav").exists():
        log("    reusing the rendered cut (same edit list)")
    else:
        cutmod.render(src, edl, cdir / "cut.mp4", cdir / "cut.wav", preset, settings["export"].get("fit", "crop"),
                      x264_preset=settings["export"].get("x264_preset_intermediate", "veryfast"), work=cdir)
    edl["state"] = state
    core.write_json(cdir / "edl.json", edl)

    # 3. check the cut by listening again
    verify = None
    if settings["cut"].get("verify", True):
        vpath = cdir / "verify.json"
        verify = core.read_json(vpath)
        if not verify or verify.get("state") != state:
            log("3/7 checking the cut (Whisper listens again) ...")
            whisper_model = whisper_model or tr.load_model(model, args.models_dir)
            heard = tr.transcribe(cdir / "cut.wav", model, wcfg.get("language", "en"), wcfg.get("vocabulary", ""),
                                  wcfg.get("write_fillers", True), args.models_dir, model=whisper_model)["words"]
            verify = cutmod.compare_words(cwords, heard)
            verify["state"] = state
            core.write_json(vpath, verify)
        else:
            log("3/7 check: reusing the last check (same cut)")
        log(f"    words kept {verify['matched']}/{verify['expected']} ({verify['kept_pct']}%), "
            f"caption timing off by {verify['start_diff_median_s']} s median, {verify['start_diff_p90_s']} s p90")
    else:
        log("3/7 check skipped (cut.verify is off)")

    # 4. captions
    hook_text = (settings.get("hook", {}).get("text") or "").strip() or None
    ass = work / "captions.ass"
    crep = captions.write_ass(cwords, ass, settings, preset_name, hook_text)
    captions.write_srt(cwords, work / "captions.srt", settings.get("fixes"))
    log(f"4/7 captions: {crep['pages']} pages, widest line {crep['widest_line_px']}/{crep['max_width']} px"
        + (f", hook {crep['hook']['size']} px" if crep.get("hook") else ""))
    for w in crep["warnings"]:
        log(f"    WARNING: {w}")

    # 5. music + loudness
    log("5/7 music and loudness ..." if track else "5/7 loudness (no music track in music/) ...")
    mrep = musicmod.mix(cdir / "cut.wav", track, work / "mix.m4a", settings, cwords, work=work)
    if mrep["music"]:
        log(f"    {Path(mrep['music']['track']).name}: {mrep['music']['measured_under_speech_db']} dB under the voice while talking")
    log(f"    {mrep['final_lufs']} LUFS, true peak {mrep['final_true_peak']} dBTP")

    # 6. export
    meta = {"settings_hash": core.hash_obj(settings), "hook": hook_text, "music": edit["music"]["track"],
            "cut_summary": s, "notes": args.note or ""}
    overlays = [dict(o, file=str((work / o["file"]) if not Path(o["file"]).is_absolute() and (work / o["file"]).exists()
                                 else Path(o["file"]))) for o in edit.get("overlays", [])]
    if overlays:
        log(f"    {len(overlays)} graphic overlay(s) from edit.json")
    draft, n = exportmod.export(cdir / "cut.mp4", settings, name, preset_name, ass, work / "mix.m4a", media, meta=meta,
                                overlays=overlays)
    log(f"6/7 draft v{n}: {draft}")

    # 7. review
    rrep = reviewmod.review(draft, settings, preset=preset_name, media=media)
    log(f"7/7 review images in {Path(rrep['images']['hook']).parent}")

    edit["history"] = edit.get("history", []) + [{"version": n, "date": core.now(), "notes": args.note or "",
                                                   "changes": args.changes or ("first draft" if n == 1 else "")}]
    core.write_json(work / "edit.json", edit)
    report = write_report(work, n, src, draft, edl, verify, crep, mrep, rrep, edit)
    log(f"report: {report}")
    return {"draft": str(draft), "version": n, "report": str(report), "review": rrep, "cut": s, "verify": verify,
            "music": mrep, "captions": crep}


def write_report(work, n, src, draft, edl, verify, crep, mrep, rrep, edit) -> Path:
    s = edl["summary"]
    L = [f"# {work.name}: draft v{n}", "",
         f"- Raw: `{src.name}` ({s['before_s']} s)",
         f"- Draft: `{draft.name}` ({rrep['duration_s']} s, {rrep['size']}, {rrep['fps']} fps)",
         f"- Cut: {s['removed_s']} s removed ({s['removed_pct']}%): {s['pauses']} pauses, {s['fillers']} fillers, "
         f"{s['retakes']} retakes, lead-in {s['lead_in_s']} s, tail {s['tail_s']} s",
         ]
    if verify:
        L.append(f"- Check: {verify['matched']} of {verify['expected']} words heard again in the cut ({verify['kept_pct']}%), "
                 f"caption timing off by {verify['start_diff_median_s']} s median")
        if verify.get("changed"):
            L.append("  - Heard a little differently: " + ", ".join(f"{c['word']} as {c['heard']} @{core.hms(c['t'])}" for c in verify["changed"][:12]))
        if verify["missing"]:
            L.append("  - Not heard again (look at these spots): " + ", ".join(f"{m['word']} @{core.hms(m['t'])}" for m in verify["missing"][:12]))
    L.append(f"- Captions: {crep['pages']} pages, widest line {crep['widest_line_px']} of {crep['max_width']} px, right edge {crep['right_edge_px']} px")
    if crep.get("hook"):
        L.append(f"- Hook: \"{crep['hook']['text']}\" at {crep['hook']['size']} px for {crep['hook']['seconds']} s")
    if mrep["music"]:
        m = mrep["music"]
        L.append(f"- Music: `{Path(m['track']).name}` {m['measured_under_speech_db']} dB under the voice while talking"
                 + (", looped" if m["looped"] else ""))
    else:
        L.append("- Music: none")
    L.append(f"- Loudness: {mrep['final_lufs']} LUFS, true peak {mrep['final_true_peak']} dBTP (target -14 / -1)")
    rem = [r for r in edl["removed"] if r["reason"] not in ("pause", "lead-in", "tail")]
    if rem:
        L += ["", "## Removed besides pauses (put back with cut.force_keep in edit.json)", ""]
        L += [f"- {core.hms(r['start'])} to {core.hms(r['end'])} ({r['reason']}): {r['text']}" for r in rem]
    for w in crep["warnings"]:
        L.append(f"- WARNING: {w}")
    L += ["", "## Review images", "", f"- {rrep['images']['hook']}", f"- {rrep['images']['contact']}", f"- {rrep['images']['guides']}"]
    if edit.get("history"):
        L += ["", "## Notes so far", ""] + [f"- v{h['version']}: {h.get('notes') or '-'} | {h.get('changes') or '-'}" for h in edit["history"]]
    p = work / f"report-v{n}.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return p


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", nargs="?", help="raw video (default: newest in raw/, or this --name's source)")
    p.add_argument("--name", help="short name for this video (default: the raw file's name)")
    p.add_argument("--hook", help="hook title for the first seconds; *stars* mark accent words ('' for none)")
    p.add_argument("--preset", choices=["reel", "youtube", "square"])
    p.add_argument("--music", help="track path, 'auto' (newest in music/) or 'none'")
    p.add_argument("--note", help="the owner's note this draft answers, in their words")
    p.add_argument("--changes", help="what was changed for this draft")
    p.add_argument("--plan-only", action="store_true", help="transcribe and plan the cut, render nothing")
    p.add_argument("--model", help="Whisper model (default from account.json)")
    p.add_argument("--models-dir")
    p.add_argument("--account")
    p.add_argument("--media")
    a = p.parse_args(argv)
    try:
        run(a)
        return 0
    except core.ToolError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
