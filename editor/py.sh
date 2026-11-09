#!/usr/bin/env sh
# Runs Python for the AI editor, so every command uses the same interpreter.
# Order: $EDITOR_PYTHON, the shared venv one level above the account folder
# ("D:\AI Editor\.venv" on Windows, made with: py -3.12 -m venv "D:\AI Editor\.venv"),
# then Python 3.12 from the Windows py launcher, then python3, then python.
# Usage (Git Bash, macOS, Linux):  bash editor/py.sh editor/tools/doctor.py
here="$(cd "$(dirname "$0")" && pwd)"
root="$(dirname "$(dirname "$here")")"
for c in "$EDITOR_PYTHON" "$root/.venv/Scripts/python.exe" "$root/.venv/bin/python"; do
  if [ -n "$c" ] && [ -x "$c" ]; then exec "$c" "$@"; fi
done
if command -v py >/dev/null 2>&1 && py -3.12 -c "" >/dev/null 2>&1; then exec py -3.12 "$@"; fi
if command -v python3 >/dev/null 2>&1; then exec python3 "$@"; fi
exec python "$@"
