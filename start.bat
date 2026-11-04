@echo off
rem ============================================================
rem  BADAWI PROJECT - launcher
rem  المنفذ / Port : 17760
rem  1) لو في نسخة شغالة بالفعل -> يفتح المتصفح عليها
rem  2) يجرب BADAWI PROJECT.exe
rem  3) لو اتمنع (Smart App Control) أو ما اشتغل، يستخدم Python
rem ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "PORT=17760"
set "URL=http://localhost:%PORT%"
set "SCRIPT=%~dp0BADAWI PROJECT.py"
set "EXE=%~dp0BADAWI PROJECT.exe"

rem ---------- 0) نسخة شغالة بالفعل؟ ----------
call :probe
if !errorlevel! equ 0 (
    echo [BADAWI PROJECT] البرنامج يعمل بالفعل على %URL%
    start "" "%URL%"
    goto :done
)

rem ---------- 1) ملف Python موجود؟ ----------
if not exist "%SCRIPT%" set "SCRIPT="

rem ---------- 2) تشغيل الـ exe ثم فحص الصحة ----------
if exist "%EXE%" (
    echo [BADAWI PROJECT] جاري التشغيل...
    start "" "%EXE%"
    call :wait_ready 15
    if !errorlevel! equ 0 (
        echo [BADAWI PROJECT] يعمل بنجاح: %URL%
        goto :done
    )
    echo [BADAWI PROJECT] تعذّر تشغيل ملف الـ exe (قد يمنعها Windows).
)

rem ---------- 3) تشغيل عبر Python ----------
if not defined SCRIPT (
    echo [BADAWI PROJECT] لا يوجد "BADAWI PROJECT.py" بجانب هذا الملف.
    pause
    exit /b 1
)

set "PY="
for %%P in (pythonw.exe python.exe) do (
    if not defined PY (
        where %%P >nul 2>nul && set "PY=%%P"
    )
)
if not defined PY (
    echo.
    echo [BADAWI PROJECT] Python غير مثبت، وملف الـ exe لم يعمل.
    echo   - ثبّت Python 3 من https://www.python.org/downloads/
    echo   - او شغّل "BADAWI PROJECT.py" بـ Python بعد التثبيت.
    echo.
    echo   Install Python 3, then run: python "BADAWI PROJECT.py"
    echo.
    pause
    exit /b 1
)

echo [BADAWI PROJECT] جاري التشغيل عبر %PY% ...
start "" %PY% "%SCRIPT%"
call :wait_ready 15
if !errorlevel! equ 0 (
    echo [BADAWI PROJECT] يعمل بنجاح: %URL%
) else (
    echo [BADAWI PROJECT] لم يستجب البرنامج. شغّل يدوياً:
    echo    %PY% "%SCRIPT%"
    pause
)
goto :done

rem ---------- فحص صحة المنفذ المحدد فقط ----------
:probe
powershell -NoProfile -Command "try{$r=Invoke-RestMethod -Uri '%URL%/api/ping' -TimeoutSec 2; if($r.app -eq 'badawi-hospital'){exit 0}else{exit 1}}catch{exit 1}" >nul 2>nul
exit /b %errorlevel%

rem ---------- انتظار جاهزية البرنامج ----------
:wait_ready
set /a _tries=%1
for /l %%i in (1,1,!_tries!) do (
    call :probe
    if !errorlevel! equ 0 exit /b 0
    timeout /t 1 /nobreak >nul
)
exit /b 1

:done
endlocal
