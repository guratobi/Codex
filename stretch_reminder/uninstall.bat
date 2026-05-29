@echo off
setlocal
chcp 65001 >nul
title 스트레칭 알리미 제거

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LNK=%STARTUP%\Stretch Reminder.lnk"

echo.
echo  ============================================
echo    목·어깨 스트레칭 알리미 - 자동 실행 해제
echo  ============================================
echo.

if exist "%LNK%" (
    del /f /q "%LNK%"
    echo  [완료] 시작프로그램에서 제거했습니다.
) else (
    echo  [정보] 등록된 바로가기가 없습니다. 이미 해제된 상태입니다.
)

echo.
echo  지금 실행 중인 알리미도 종료할까요?
echo  ^(주의: 다른 pythonw.exe 스크립트가 있다면 함께 종료됩니다.^)
choice /c YN /n /m "  종료하려면 Y, 그대로 두려면 N 을 누르세요: "
if errorlevel 2 goto :done

taskkill /im pythonw.exe /f >nul 2>&1
echo  [완료] pythonw.exe 프로세스를 종료했습니다.

:done
echo.
pause
endlocal
exit /b 0
