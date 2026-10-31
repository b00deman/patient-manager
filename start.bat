@echo off
chcp 65001 >nul 2>&1
title تسجيل بيانات المرضى
cd /d "%~dp0"
python server.py
pause
