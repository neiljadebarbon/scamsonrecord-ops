@echo off
rem Runs Python for the AI editor, so every command uses the same interpreter.
rem Order: EDITOR_PYTHON, the shared venv one level above the account folder
rem ("D:\AI Editor\.venv", made with: py -3.12 -m venv "D:\AI Editor\.venv"),
rem then Python 3.12 from the py launcher, then python.
rem Usage (PowerShell or cmd):  editor\py.cmd editor\tools\doctor.py
setlocal
set "ROOT=%~dp0..\.."
set "PY="
if defined EDITOR_PYTHON set "PY=%EDITOR_PYTHON%"
if not defined PY if exist "%ROOT%\.venv\Scripts\python.exe" set "PY=%ROOT%\.venv\Scripts\python.exe"
if defined PY goto run
py -3.12 -c "" >nul 2>&1
if errorlevel 1 goto plain
py -3.12 %*
exit /b
:plain
python %*
exit /b
:run
"%PY%" %*
exit /b
