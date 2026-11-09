"""Check every tool the AI editor needs and say exactly how to fix anything missing.

  bash editor/py.sh editor/tools/doctor.py                  table of versions + fixes
  bash editor/py.sh editor/tools/doctor.py --make-folders   also create raw/ references/ done/ work/ music/
  bash editor/py.sh editor/tools/doctor.py --download-model download the Whisper model (small.en) once
  bash editor/py.sh editor/tools/doctor.py --json           machine-readable
(In PowerShell or cmd use editor\\py.cmd instead of bash editor/py.sh.)

Checks: the Python running this (version 3.10 to 3.13, and whether it's the shared venv at
<AI Editor>\\.venv), FFmpeg (with libass for burned-in captions, libx264, zscale for iPhone HDR),
ffprobe, faster-whisper and whether the Whisper model is downloaded, numpy, Pillow, yt-dlp,
Node (22 or newer), Remotion (only if a Remotion project is in this repo), the HyperFrames CLI,
Git, the brand fonts, the media folders (and that git ignores them), and free disk space.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

import core

WIN = os.name == "nt"
VENV = core.REPO.parent / ".venv"
OK, WARN, MISSING = "OK", "WARN", "MISSING"


def sh(cmd, timeout=60) -> tuple[int, str]:
    try:
        exe = shutil.which(cmd[0]) or cmd[0]
        r = subprocess.run([exe, *cmd[1:]], capture_output=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)


def py_launcher() -> str:
    return r"editor\py.cmd" if WIN else "bash editor/py.sh"


def check_python(rows, fixes):
    v = sys.version_info
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    here = Path(sys.executable)
    is_shared = in_venv and VENV.exists() and Path(sys.prefix).resolve() == VENV.resolve()
    where = "shared venv" if is_shared else ("a venv" if in_venv else "system Python")
    detail = f"{v.major}.{v.minor}.{v.micro} at {here} ({where})"
    if (v.major, v.minor) < (3, 10):
        rows.append(["Python", MISSING, detail])
        fixes.append("Install Python 3.12: winget install -e --id Python.Python.3.12")
    elif (v.major, v.minor) >= (3, 14):
        rows.append(["Python", WARN, detail + ": too new, faster-whisper's PyAV has no wheels for it yet"])
        fixes.append(f'Use Python 3.12 in a venv: winget install -e --id Python.Python.3.12, then py -3.12 -m venv "{VENV}", '
                     f"then {py_launcher()} -m pip install -r editor/requirements.txt")
    else:
        rows.append(["Python", OK, detail])
    if not is_shared:
        if VENV.exists():
            fixes.append(f"Run the tools through {py_launcher()} so they use the shared venv at {VENV}")
        elif WIN:
            fixes.append(f'Create the shared venv (once per drive): py -3.12 -m venv "{VENV}" '
                         f"then {py_launcher()} -m pip install -r editor/requirements.txt")
    if WIN and shutil.which("py"):
        code, out = sh(["py", "-0p"])
        if code == 0:
            have = re.findall(r"-V?:?(\d\.\d+)", out)
            rows.append(["py launcher", OK, "Pythons: " + (", ".join(sorted(set(have))) or out.strip()[:60])])


def check_ffmpeg(rows, fixes):
    try:
        ff = core.ffmpeg_bin()
    except core.ToolError:
        rows.append(["FFmpeg", MISSING, "not on PATH"])
        fixes.append("winget install -e --id Gyan.FFmpeg   (full build with libass; open a new terminal after)")
        return
    _, out = sh([ff, "-hide_banner", "-version"])
    ver = (re.search(r"ffmpeg version (\S+)", out) or [None, "?"])[1]
    _, filt = sh([ff, "-hide_banner", "-filters"])
    _, enc = sh([ff, "-hide_banner", "-encoders"])
    has = lambda name: re.search(rf"^\s*\S+\s+{name}\s", filt, re.M) is not None
    libass = has("ass") and has("subtitles")
    x264 = "libx264" in enc
    rows.append(["FFmpeg", OK if libass and x264 else MISSING,
                 f"{ver}; libass {'yes' if libass else 'NO'}; libx264 {'yes' if x264 else 'NO'}; "
                 f"zscale {'yes' if has('zscale') else 'no (iPhone HDR clips will look grey)'}"])
    if not (libass and x264):
        fixes.append("This FFmpeg can't burn captions or encode H.264. winget install -e --id Gyan.FFmpeg (the full build).")
    try:
        fp = core.ffprobe_bin()
        _, out = sh([fp, "-hide_banner", "-version"])
        rows.append(["ffprobe", OK, (re.search(r"ffprobe version (\S+)", out) or [None, "?"])[1]])
    except core.ToolError:
        rows.append(["ffprobe", MISSING, "comes with FFmpeg"])


def check_python_packages(rows, fixes, account, models_override):
    need_pip = False
    for mod, label in (("faster_whisper", "faster-whisper"), ("numpy", "numpy"), ("PIL", "Pillow"), ("yt_dlp", "yt-dlp")):
        try:
            m = __import__(mod)
            ver = getattr(m, "__version__", None)
            if mod == "yt_dlp":
                ver = m.version.__version__
            rows.append([label, OK, ver or "installed"])
        except Exception as e:
            rows.append([label, MISSING, type(e).__name__])
            need_pip = True
    if need_pip:
        fixes.append(f"{py_launcher()} -m pip install -r editor/requirements.txt")
    import transcribe as tr
    model = account.get("whisper", {}).get("model", "small.en")
    mdir = core.models_dir(models_override)
    got = tr.model_downloaded(model, mdir)
    rows.append([f"Whisper {model}", OK if got else MISSING, str(got) if got else f"not downloaded (cache: {mdir})"])
    if not got:
        fixes.append(f"{py_launcher()} editor/tools/doctor.py --download-model   (about 0.5 GB, once)")


def check_node(rows, fixes):
    code, out = sh(["node", "--version"])
    if code != 0:
        rows.append(["Node", MISSING, "needed for HyperFrames and Remotion"])
        fixes.append("winget install -e --id OpenJS.NodeJS.LTS   (Node 22 or newer)")
        return
    m = re.search(r"v(\d+)", out)
    major = int(m.group(1)) if m else 0
    rows.append(["Node", OK if major >= 22 else WARN, out.strip()])
    if major < 22:
        fixes.append("Node is older than 22: winget upgrade -e --id OpenJS.NodeJS.LTS")


def check_remotion(rows, fixes):
    projects = []
    for pj in core.REPO.glob("tools/**/package.json"):
        if "node_modules" in pj.parts:
            continue
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if "remotion" in {**data.get("dependencies", {}), **data.get("devDependencies", {})}:
            projects.append(pj.parent)
    if not projects:
        rows.append(["Remotion", OK, "no Remotion project in this repo (optional)"])
    for d in projects:
        inst = d / "node_modules" / "remotion" / "package.json"
        rel = d.relative_to(core.REPO).as_posix()
        if inst.exists():
            rows.append(["Remotion", OK, f"{json.loads(inst.read_text(encoding='utf-8')).get('version')} in {rel}"])
        else:
            rows.append(["Remotion", WARN, f"{rel}: not installed"])
            fixes.append(f'cd "{rel}" && npm install   (only needed for Remotion videos)')


def check_hyperframes(rows, fixes):
    local = core.REPO / "tools" / "hyperframes" / "node_modules" / ".bin" / ("hyperframes.cmd" if WIN else "hyperframes")
    exe = str(local) if local.exists() else shutil.which("hyperframes")
    if exe:
        code, out = sh([exe, "--version"])
        ver = out.strip().splitlines()[-1] if out.strip() else "?"
        rows.append(["HyperFrames CLI", OK if code == 0 else WARN, f"{ver} ({'tools/hyperframes' if local.exists() else 'global'})"])
    elif (core.REPO / "tools" / "hyperframes" / "package.json").exists():
        rows.append(["HyperFrames CLI", WARN, "tools/hyperframes not installed"])
        fixes.append('cd tools/hyperframes && npm install   (only needed for HyperFrames graphics)')
    else:
        rows.append(["HyperFrames CLI", OK if shutil.which("npx") else WARN, "not installed here; runs with npx hyperframes (optional)"])


def check_git(rows, fixes):
    code, out = sh(["git", "--version"])
    if code != 0:
        rows.append(["Git", MISSING, ""])
        fixes.append("winget install -e --id Git.Git")
        return
    rows.append(["Git", OK, out.strip().replace("git version ", "")])
    if not (core.REPO / ".git").exists():
        rows.append(["Repo checkout", WARN, f"{core.REPO} is not a git checkout"])


def check_fonts(rows, fixes, account):
    import captions
    names = {(account["captions"]["font"], False), (account["hook"]["font"], False), (account["hook"]["accent_font"], True)}
    missing = [n for n, it in names if not captions.find_font(n, italic=it)]
    rows.append(["Brand fonts", OK if not missing else WARN,
                 "in editor/fonts" if not missing else f"missing: {', '.join(missing)} (put the .ttf files in editor/fonts)"])


def check_media(rows, fixes, make, media):
    root = core.media_root(media)
    missing = [k for k in core.MEDIA_KINDS if not (root / k).is_dir()]
    if make:
        for k in core.MEDIA_KINDS:
            (root / k).mkdir(parents=True, exist_ok=True)
        missing = []
    rows.append(["Media folders", OK if not missing else WARN,
                 f"{root}" + (f" (missing: {', '.join(missing)})" if missing else "")])
    if missing:
        fixes.append(f"{py_launcher()} editor/tools/doctor.py --make-folders")
    if (core.REPO / ".git").exists() and shutil.which("git"):
        leaks, inside = [], 0
        for k in core.MEDIA_KINDS:
            p = root / k
            try:
                rel = p.relative_to(core.REPO)
            except ValueError:
                continue  # outside the repo, git can't see it
            inside += 1
            code, _ = sh(["git", "-C", str(core.REPO), "check-ignore", "-q", rel.as_posix() + "/"])
            if code != 0:
                leaks.append(k)
        rows.append(["Media ignored by git", OK if not leaks else MISSING,
                     ("yes" if inside else "media is outside the repo (EDITOR_MEDIA)") if not leaks
                     else f"NOT ignored: {', '.join(leaks)}"])
        if leaks:
            fixes.append("Add " + ", ".join(f"/{k}/" for k in leaks) + " to .gitignore before committing anything")
    free = shutil.disk_usage(root if root.exists() else root.anchor).free / 1e9
    rows.append(["Free disk", OK if free > 10 else WARN, f"{free:.0f} GB on {root.anchor or '/'}"])


def download_model(account, models_override, name=None):
    import transcribe as tr
    name = name or account.get("whisper", {}).get("model", "small.en")
    mdir = core.models_dir(models_override)
    if tr.model_downloaded(name, mdir):
        print(f"Whisper {name} is already downloaded in {mdir}")
        return
    from faster_whisper import WhisperModel
    print(f"Downloading Whisper {name} into {mdir} ...", flush=True)
    WhisperModel(name, device="cpu", compute_type="int8", download_root=str(mdir))
    print("done:", tr.model_downloaded(name, mdir))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--make-folders", action="store_true", help="create raw/ references/ done/ work/ music/")
    p.add_argument("--download-model", nargs="?", const="", metavar="MODEL", help="download the Whisper model (default from account.json)")
    p.add_argument("--models-dir")
    p.add_argument("--json", action="store_true")
    p.add_argument("--account")
    p.add_argument("--media")
    a = p.parse_args(argv)
    account = core.load_account(a.account)
    if a.download_model is not None:
        try:
            download_model(account, a.models_dir, a.download_model or None)
        except Exception as e:  # network or disk problems: say so plainly
            print("ERROR downloading the model:", e, file=sys.stderr)
    rows, fixes = [], []
    check_python(rows, fixes)
    check_ffmpeg(rows, fixes)
    check_python_packages(rows, fixes, account, a.models_dir)
    check_node(rows, fixes)
    check_remotion(rows, fixes)
    check_hyperframes(rows, fixes)
    check_git(rows, fixes)
    check_fonts(rows, fixes, account)
    check_media(rows, fixes, a.make_folders, a.media)
    if a.json:
        print(json.dumps({"checks": [dict(zip(("check", "status", "detail"), r)) for r in rows], "fixes": fixes,
                          "platform": platform.platform()}, indent=2))
    else:
        print(f"AI editor check on {platform.system()} {platform.release()}, account folder {core.REPO}\n")
        core.print_table(rows, ["Check", "Status", "Version / detail"])
        if fixes:
            print("\nTo fix:")
            for i, f in enumerate(fixes, 1):
                print(f"{i}. {f}")
        else:
            print("\nEverything is ready.")
    return 1 if any(r[1] == MISSING for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
