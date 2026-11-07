@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
    python "pharmacy.py" %*
) else (
    echo Python 3 is required. Install it from https://www.python.org/downloads/
    pause
)
