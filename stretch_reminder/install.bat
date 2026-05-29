@echo off
setlocal

rem ===== Run relative to this batch file's folder =====
set "HERE=%~dp0"
set "SCRIPT=%HERE%stretch_reminder.pyw"

echo.
echo  ============================================
echo    Stretch Reminder - Startup Installer
echo  ============================================
echo.

rem ----- Check the .pyw exists -----
if not exist "%SCRIPT%" (
    echo  [ERROR] stretch_reminder.pyw not found next to install.bat.
    echo          Keep both files in the same folder and run again.
    echo          ^(looked for: %SCRIPT%^)
    goto :fail
)

rem ----- Find pythonw.exe (fall back to the pyw.exe launcher) -----
set "PYW="
for /f "delims=" %%I in ('where pythonw.exe 2^>nul') do if not defined PYW set "PYW=%%I"
if not defined PYW (
    for /f "delims=" %%I in ('where pyw.exe 2^>nul') do if not defined PYW set "PYW=%%I"
)
if not defined PYW (
    echo  [ERROR] pythonw.exe was not found on PATH.
    echo          Reinstall Python with "Add Python to PATH" checked.
    echo          https://www.python.org
    goto :fail
)

echo   - Python : %PYW%
echo   - Script : %SCRIPT%

rem ----- Startup folder / shortcut path -----
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LNK=%STARTUP%\Stretch Reminder.lnk"

rem ----- Pass values via env vars to dodge batch/PowerShell quoting issues -----
set "SR_TARGET=%PYW%"
set "SR_ARG=%SCRIPT%"
set "SR_WORKDIR=%HERE%"
set "SR_LNK=%LNK%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$q=[char]34; $ws=New-Object -ComObject WScript.Shell; $sc=$ws.CreateShortcut($env:SR_LNK); $sc.TargetPath=$env:SR_TARGET; $sc.Arguments=$q+$env:SR_ARG+$q; $sc.WorkingDirectory=$env:SR_WORKDIR; $sc.IconLocation=$env:SR_TARGET; $sc.Save()"

if not exist "%LNK%" (
    echo  [ERROR] Failed to create the startup shortcut.
    goto :fail
)

echo.
echo  [OK] Registered in Startup:
echo       %LNK%
echo.

rem ----- (Optional) tray-icon packages; OK to fail, app works without them -----
echo  Installing optional tray-icon packages (pystray, pillow)...
set "PY="
for /f "delims=" %%I in ('where python.exe 2^>nul') do if not defined PY set "PY=%%I"
if not defined PY set "PY=%PYW%"
"%PY%" -m pip install --user --quiet --disable-pip-version-check pystray pillow
if errorlevel 1 (
    echo  [NOTE] Could not install tray packages ^(offline / blocked^).
    echo         The reminder still works fine without the tray icon.
) else (
    echo  [OK] Tray icon ready.
)
echo.

rem ----- Launch now (single-instance guard prevents duplicates) -----
echo  Starting in the background now...
start "" "%PYW%" "%SCRIPT%"

echo.
echo  Done. It will start automatically from the next boot.
echo  Run uninstall.bat to remove autostart.
echo.
pause
endlocal
exit /b 0

:fail
echo.
pause
endlocal
exit /b 1
