@echo off
setlocal
title fast-clone Setup

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "TOOL_DIR=%%~fI"

REM ---- Check Python in PATH ----
python --version >nul 2>&1
if %errorlevel%==0 (set "PYTHON=python" & goto :run)

python3 --version >nul 2>&1
if %errorlevel%==0 (set "PYTHON=python3" & goto :run)

echo Python not found in PATH.
echo Please install Python 3.7+: https://www.python.org/downloads/
echo If already installed, add it to your system PATH.
pause
exit /b 1

:run
"%PYTHON%" "%TOOL_DIR%\fastclone.py" --setup
pause
exit /b %ERRORLEVEL%
