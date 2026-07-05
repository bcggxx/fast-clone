@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "FASTCLONE_PY=%SCRIPT_DIR%..\fastclone.py"

REM ============================================
REM Double-click detection: show help, no flash-close
REM ============================================
if "%~1"=="" (
    echo ============================================================
    echo   fast-clone — mirror-accelerated git clone
    echo ============================================================
    echo.
    echo Run from command line. Examples:
    echo.
    echo   fast-clone https://github.com/user/repo
    echo   fast-clone --fastest https://github.com/user/repo
    echo   fast-clone --list-mirrors
    echo   fast-clone --dry-run https://github.com/user/repo
    echo   fast-clone --help
    echo.
    echo Setup: run setup.bat as administrator
    echo Config: edit mirror.json
    echo Manual: README.md
    echo.
    pause
    exit /b 0
)

REM ============================================
REM Check Python (PATH only)
REM ============================================
python --version >nul 2>&1
if %errorlevel%==0 (
    python "%FASTCLONE_PY%" %*
    exit /b %ERRORLEVEL%
)

python3 --version >nul 2>&1
if %errorlevel%==0 (
    python3 "%FASTCLONE_PY%" %*
    exit /b %ERRORLEVEL%
)

echo [ERROR] Python not found in PATH.
echo.
echo Please install Python 3.7+:
echo   https://www.python.org/downloads/
echo.
echo If already installed, add Python to your system PATH:
echo   "This PC" -^> Properties -^> Advanced -^> Environment Variables
echo   Add these to Path:
echo     C:\Users\YourName\AppData\Local\Programs\Python\Python3xx\
echo     C:\Users\YourName\AppData\Local\Programs\Python\Python3xx\Scripts\
echo.
echo Or run directly:
echo   python "%FASTCLONE_PY%" [args]
pause
exit /b 1
