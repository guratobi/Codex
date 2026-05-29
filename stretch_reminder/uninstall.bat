@echo off
setlocal

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LNK=%STARTUP%\Stretch Reminder.lnk"

echo.
echo  ============================================
echo    Stretch Reminder - Uninstall (autostart)
echo  ============================================
echo.

if exist "%LNK%" (
    del /f /q "%LNK%"
    echo  [OK] Removed the startup shortcut.
) else (
    echo  [INFO] No startup shortcut found. Already removed.
)

echo.
echo  Also stop the reminder that is running now?
echo  (Warning: this stops ALL pythonw.exe processes, if any.)
choice /c YN /n /m "  Press Y to stop, or N to keep it running: "
if errorlevel 2 goto :done

taskkill /im pythonw.exe /f >nul 2>&1
echo  [OK] Stopped pythonw.exe.

:done
echo.
pause
endlocal
exit /b 0
