"""Shared helpers for the AI editor tools (paths, ffmpeg, probing, audio, JSON, time formats).

Every tool in this folder imports this module. Nothing here is specific to one account:
account settings live in editor/account.json.

Folder layout. The account folder that Claude's Local session is pointed at,
e.g. "D:\\AI Editor\\My Account", is also the ops repo checkout:

    <account folder>/
        raw/          recordings, never changed or deleted by these tools
        references/   reels downloaded for private study
        done/         drafts: <name>-draft-v1.mp4, -v2 ...
        work/         working files per video (safe to delete)
        music/        licensed music tracks you may use
        editor/       these tools, account.json, style.md

The media root defaults to the repo root (the folder that holds editor/). Set the EDITOR_MEDIA
environment variable, or pass --media, to keep footage somewhere else.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
EDITOR = TOOLS.parent
REPO = EDITOR.parent
FONTS = EDITOR / "fonts"
ACCOUNT_FILE = EDITOR / "account.json"
MEDIA_KINDS = ("raw", "references", "done", "work", "music")

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts", ".m2ts", ".3gp"}
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}

# Plain ASCII output so the Windows console never chokes on a character.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


class ToolError(RuntimeError):
    """A step failed in a way the person can fix; the message says how."""


# ---------------------------------------------------------------- paths

def media_root(override: str | os.PathLike | None = None) -> Path:
    """Root that holds raw/ references/ done/ work/ music/ (repo root unless EDITOR_MEDIA or --media)."""
    p = override or os.environ.get("EDITOR_MEDIA") or REPO
    return Path(p).expanduser().resolve()


def media_dir(kind: str, override=None, create: bool = True) -> Path:
    if kind not in MEDIA_KINDS:
        raise ValueError(kind)
    d = media_root(override) / kind
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def guard_output(path: Path, media=None) -> Path:
    """Refuse to write anything inside raw/ (raw footage is never changed)."""
    path = Path(path).resolve()
    raw = media_dir("raw", media, create=False).resolve()
    if path == raw or raw in path.parents:
        raise ToolError(f"Refusing to write into raw/: {path}. Raw footage is never changed.")
    return path


def models_dir(override=None) -> Path:
    """Where Whisper models are cached: --models-dir, EDITOR_WHISPER_MODELS, or editor/models (git-ignored)."""
    p = override or os.environ.get("EDITOR_WHISPER_MODELS") or (EDITOR / "models")
    p = Path(p).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def slugify(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "-", text.strip()).strip("-").lower()
    return s[:60] or "video"


def is_media_file(p: Path, kinds=("video", "audio")) -> bool:
    ext = p.suffix.lower()
    if p.name.startswith((".", "~$")) or ext in {".part", ".crdownload", ".tmp"}:
        return False
    return ("video" in kinds and ext in VIDEO_EXT) or ("audio" in kinds and ext in AUDIO_EXT)


def newest_file(folder: Path, kinds=("video",)) -> Path | None:
    files = [p for p in Path(folder).iterdir() if p.is_file() and is_media_file(p, kinds)] if Path(folder).exists() else []
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def fingerprint(path: Path) -> str:
    """Cheap identity for a media file: size, mtime and a hash of its first and last MiB."""
    path = Path(path)
    st = path.stat()
    h = hashlib.sha1(f"{st.st_size}:{int(st.st_mtime)}".encode())
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
        if st.st_size > (2 << 20):
            f.seek(-(1 << 20), os.SEEK_END)
            h.update(f.read())
    return h.hexdigest()[:16]


def hash_obj(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- json / account

def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
    return path


def deep_merge(base: dict, over: dict | None) -> dict:
    out = json.loads(json.dumps(base))
    for k, v in (over or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        elif v is not None:
            out[k] = v
    return out


def load_account(path=None) -> dict:
    """editor/account.json (or EDITOR_ACCOUNT / --account)."""
    p = Path(path or os.environ.get("EDITOR_ACCOUNT") or ACCOUNT_FILE)
    data = read_json(p)
    if data is None:
        raise ToolError(f"No account profile at {p}. Copy editor/account.json from the template and edit it.")
    return data


def settings_for(account: dict, overrides: dict | None = None) -> dict:
    """Account settings with one video's overrides (work/<name>/edit.json) merged on top."""
    return deep_merge(account, overrides or {})


# ---------------------------------------------------------------- running ffmpeg

def _bin(name: str, env: str) -> str:
    p = os.environ.get(env) or shutil.which(name)
    if not p and os.name == "nt":
        # winget installs FFmpeg for new terminals only; find it before the PATH refreshes
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet"
        cands = [local / "Links" / f"{name}.exe"] + sorted((local / "Packages").glob(f"Gyan.FFmpeg*/*/bin/{name}.exe"))
        p = next((str(c) for c in cands if c.exists()), None)
    if not p:
        raise ToolError(f"{name} not found. On Windows run: winget install -e --id Gyan.FFmpeg  (then open a new terminal). "
                        f"Run python editor/tools/doctor.py to check everything.")
    return p


def ffmpeg_bin() -> str:
    return _bin("ffmpeg", "FFMPEG")


def ffprobe_bin() -> str:
    return _bin("ffprobe", "FFPROBE")


VERBOSE = bool(os.environ.get("EDITOR_VERBOSE"))


def run(cmd, cwd=None, capture=True, input_bytes=None, check=True) -> subprocess.CompletedProcess:
    """Run a program with list arguments (no shell, safe with spaces in Windows paths)."""
    cmd = [str(c) for c in cmd]
    if VERBOSE:
        print("  $", subprocess.list2cmdline(cmd), file=sys.stderr)
    res = subprocess.run(cmd, cwd=cwd, input=input_bytes,
                         stdout=subprocess.PIPE if capture else None,
                         stderr=subprocess.PIPE if capture else None)
    if check and res.returncode != 0:
        err = (res.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        raise ToolError(f"{Path(cmd[0]).name} failed (exit {res.returncode}):\n  " + "\n  ".join(err[-25:]))
    return res


def ffmpeg(args, **kw) -> subprocess.CompletedProcess:
    return run([ffmpeg_bin(), "-hide_banner", "-nostdin", *args], **kw)


_FF_VERSION = None


def ffmpeg_version() -> tuple[int, int]:
    global _FF_VERSION
    if _FF_VERSION is None:
        out = run([ffmpeg_bin(), "-hide_banner", "-version"]).stdout.decode("utf-8", "replace")
        m = re.search(r"version\s+n?(\d+)\.(\d+)", out)
        # git builds ("version 2026-11-01-git-...") are newer than any release
        _FF_VERSION = (int(m.group(1)), int(m.group(2))) if m and int(m.group(1)) < 100 else (99, 0)
    return _FF_VERSION


def filter_script_args(script: Path) -> list[str]:
    """Pass a long filter graph from a file (keeps Windows' command-line length limit out of the way)."""
    major, _ = ffmpeg_version()
    if major >= 7:
        return ["-/filter_complex", str(script)]
    return ["-filter_complex_script", str(script)]


def ff_escape(value) -> str:
    """Escape a value (usually a file path) for a filter option, e.g. ass=filename=<this>.

    Two levels: the option parser (\\ : ') and the filter graph parser (\\ ' [ ] , ;).
    Forward slashes are used so "D:\\AI Editor\\x.ass" becomes D\\\\\\:/AI Editor/x.ass.
    """
    v = Path(value).resolve().as_posix() if isinstance(value, Path) else str(value).replace("\\", "/")
    for ch in "\\:'":
        v = v.replace(ch, "\\" + ch)
    for ch in "\\'[],;":
        v = v.replace(ch, "\\" + ch)
    return v


# ---------------------------------------------------------------- probing

def _rate(s: str | None) -> float:
    if not s or s in ("0/0", "N/A"):
        return 0.0
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b) if float(b) else 0.0
    return float(s)


def probe(path) -> dict:
    """Duration, size, fps, rotation, audio presence and colour info of a media file."""
    path = Path(path)
    if not path.exists():
        raise ToolError(f"File not found: {path}")
    out = run([ffprobe_bin(), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]).stdout
    info = json.loads(out.decode("utf-8", "replace"))
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")), None)
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    fmt = info.get("format", {})
    d = {
        "path": str(path),
        "duration": float(fmt.get("duration") or (v or a or {}).get("duration") or 0),
        "has_video": v is not None,
        "has_audio": a is not None,
    }
    if v:
        w, h = int(v.get("width", 0)), int(v.get("height", 0))
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(float(sd["rotation"]))
        if not rot and v.get("tags", {}).get("rotate"):
            rot = int(v["tags"]["rotate"])
        if abs(rot) % 180 == 90:
            w, h = h, w
        afr, rfr = _rate(v.get("avg_frame_rate")), _rate(v.get("r_frame_rate"))
        d.update({
            "width": w, "height": h, "rotation": rot,
            "fps": round(afr or rfr, 3), "vfr": bool(afr and rfr and abs(afr - rfr) > 0.01),
            "vcodec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
            "color_transfer": v.get("color_transfer"), "color_primaries": v.get("color_primaries"),
            "hdr": v.get("color_transfer") in ("arib-std-b67", "smpte2084"),
        })
    if a:
        d.update({"acodec": a.get("codec_name"), "sample_rate": int(a.get("sample_rate") or 0),
                  "channels": int(a.get("channels") or 0)})
    return d


# ---------------------------------------------------------------- audio

def decode_audio(path, sr: int = 16000, channels: int = 1, af: str | None = None):
    """Decode any media file's audio with ffmpeg to a float32 numpy array (mono: shape (n,), else (n, ch)).

    faster-whisper 1.2.1's own loader breaks with newer PyAV, so all audio goes through ffmpeg.
    """
    import numpy as np
    args = ["-v", "error", "-i", str(path), "-vn", "-map", "0:a:0"]
    if af:
        args += ["-af", af]
    args += ["-ac", str(channels), "-ar", str(sr), "-f", "f32le", "-"]
    raw = ffmpeg(args).stdout
    a = np.frombuffer(raw, dtype=np.float32).copy()
    return a if channels == 1 else a.reshape(-1, channels)


def write_audio(path, samples, sr: int, extra_args=()):
    """Write a float32 numpy array (n,) or (n, ch) to any format ffmpeg knows (wav, m4a, ...)."""
    import numpy as np
    arr = np.ascontiguousarray(samples, dtype=np.float32)
    ch = 1 if arr.ndim == 1 else arr.shape[1]
    ffmpeg(["-y", "-v", "error", "-f", "f32le", "-ar", str(sr), "-ac", str(ch), "-i", "-", *extra_args, str(path)],
           input_bytes=arr.tobytes())
    return Path(path)


def frame_db(samples, sr: int, hop: float = 0.01):
    """RMS level in dBFS per hop (10 ms default) of a mono float array."""
    import numpy as np
    n = int(sr * hop)
    m = len(samples) // n
    if m == 0:
        return np.array([-120.0])
    x = samples[: m * n].reshape(m, n)
    rms = np.sqrt(np.mean(x.astype(np.float64) ** 2, axis=1))
    return 20 * np.log10(np.maximum(rms, 1e-6))


def loudness(path_or_args, af: str | None = None) -> dict:
    """Integrated loudness (LUFS), true peak (dBTP) and range (LU), measured with ffmpeg loudnorm."""
    args = list(path_or_args) if isinstance(path_or_args, (list, tuple)) else ["-i", str(path_or_args)]
    chain = (af + "," if af else "") + "loudnorm=I=-14:TP=-1:LRA=11:print_format=json"
    res = ffmpeg(["-v", "info", *args, "-vn", "-af", chain, "-f", "null", "-"])
    txt = res.stderr.decode("utf-8", "replace")
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", txt, re.S)
    if not m:
        raise ToolError("Could not measure loudness:\n" + txt[-800:])
    j = json.loads(m[-1])
    f = lambda k: float(j[k]) if j.get(k) not in (None, "-inf", "inf") else -99.0
    return {"lufs": round(f("input_i"), 2), "true_peak": round(f("input_tp"), 2), "lra": round(f("input_lra"), 2),
            "threshold": round(f("input_thresh"), 2), "raw": j}


# ---------------------------------------------------------------- words

FILLERS = {"um", "umm", "ummm", "uh", "uhh", "uhm", "er", "erm", "ah", "hmm", "hm", "mm", "mhm"}


def norm_word(w: str) -> str:
    return re.sub(r"[^a-z0-9']+", "", w.lower().replace("\u2019", "'"))


def load_words(path) -> list[dict]:
    data = read_json(path)
    if data is None:
        raise ToolError(f"No words file at {path}. Run transcribe.py first.")
    return data["words"] if isinstance(data, dict) else data


def apply_fixes(words: list[dict], fixes: dict | None) -> list[dict]:
    """Caption spelling fixes from account.json / edit.json, e.g. {"youtube": "YouTube"} (case-insensitive, whole word)."""
    if not fixes:
        return words
    low = {norm_word(k): v for k, v in fixes.items() if " " not in k.strip()}
    out = []
    for w in words:
        n = norm_word(w["word"])
        if n in low:
            lead = re.match(r"^\W*", w["word"]).group(0)
            trail = re.search(r"\W*$", w["word"]).group(0)
            w = dict(w, word=lead + low[n] + trail)
        out.append(w)
    return out


# ---------------------------------------------------------------- time formats

def ts_srt(t: float) -> str:
    ms = int(round(max(t, 0) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def ts_vtt(t: float) -> str:
    return ts_srt(t).replace(",", ".")


def ts_ass(t: float) -> str:
    cs = int(round(max(t, 0) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def hms(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def ass_color(hex_color: str, alpha: int = 0) -> str:
    """#RRGGBB -> ASS &HAABBGGRR."""
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_inline(hex_color: str) -> str:
    """#RRGGBB -> &HBBGGRR& for inline tags like \\c."""
    h = hex_color.lstrip("#")
    return f"&H{h[4:6]}{h[2:4]}{h[0:2]}&".upper()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- drafts

def draft_versions(done: Path, work: Path | None, name: str) -> list[int]:
    pat = re.compile(rf"^{re.escape(name)}-draft-v(\d+)\.mp4$", re.I)
    vs = [int(m.group(1)) for p in done.glob("*.mp4") if (m := pat.match(p.name))]
    if work and work.exists():
        vs += [int(m.group(1)) for p in work.glob("draft-v*.json") if (m := re.match(r"draft-v(\d+)\.json$", p.name))]
    return sorted(set(vs))


def next_draft(done: Path, work: Path | None, name: str) -> tuple[Path, int]:
    """Next free <name>-draft-vN.mp4: N is one more than any draft in done/ or recorded in work/."""
    vs = draft_versions(done, work, name)
    n = (vs[-1] + 1) if vs else 1
    while (done / f"{name}-draft-v{n}.mp4").exists():
        n += 1
    return done / f"{name}-draft-v{n}.mp4", n


def print_table(rows: list[list[str]], header: list[str] | None = None):
    rows = [[str(c) for c in r] for r in rows]
    if header:
        rows = [header] + rows
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for k, r in enumerate(rows):
        print("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)).rstrip())
        if header and k == 0:
            print("  ".join("-" * w for w in widths))


# ---------------------------------------------------------------- frames and contact sheets

def extract_frame(video, t: float, out, width: int | None = None, vf: str | None = None) -> Path:
    """One frame at time t (seconds) as PNG/JPG."""
    chain = [x for x in [vf, f"scale={width}:-2" if width else None] if x]
    args = ["-y", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(video), "-frames:v", "1", "-update", "1"]
    if chain:
        args += ["-vf", ",".join(chain)]
    ffmpeg(args + [str(out)])
    return Path(out)


def contact_sheet(items, out, cols: int = 4, tile_w: int = 270, title: str | None = None) -> Path:
    """Grid of frames with a time label under each. items: [(image_path, label)]."""
    from PIL import Image, ImageDraw, ImageFont
    tiles = []
    for path, label in items:
        im = Image.open(path).convert("RGB")
        h = int(round(im.height * tile_w / im.width))
        tiles.append((im.resize((tile_w, h), Image.LANCZOS), label))
    if not tiles:
        raise ToolError("no frames for the contact sheet")
    th = max(t.height for t, _ in tiles)
    lab_h, top = 34, (48 if title else 0)
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile_w + (cols + 1) * 6, top + rows * (th + lab_h + 6) + 6), (12, 12, 18))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(str(FONTS / "DMSans-Bold.ttf"), 22)
        tfont = ImageFont.truetype(str(FONTS / "DMSans-Bold.ttf"), 28)
    except OSError:
        font = tfont = ImageFont.load_default()
    if title:
        d.text((10, 10), title, fill=(255, 255, 255), font=tfont)
    for i, (im, label) in enumerate(tiles):
        x = 6 + (i % cols) * (tile_w + 6)
        y = top + 6 + (i // cols) * (th + lab_h + 6)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + th + 5), label, fill=(49, 237, 49), font=font)
    sheet.save(out, quality=88)
    return Path(out)
