@echo off
setlocal
chcp 65001 >nul
title 스트레칭 알리미 설치

rem ===== 이 배치 파일이 있는 폴더 기준으로 동작 =====
set "HERE=%~dp0"
set "SCRIPT=%HERE%stretch_reminder.pyw"

echo.
echo  ============================================
echo    목·어깨 스트레칭 알리미 - 시작프로그램 등록
echo  ============================================
echo.

rem ----- stretch_reminder.pyw 존재 확인 -----
if not exist "%SCRIPT%" (
    echo  [오류] stretch_reminder.pyw 를 찾을 수 없습니다.
    echo         install.bat 와 같은 폴더에 두고 다시 실행하세요.
    echo         ^(찾은 위치: %SCRIPT%^)
    goto :fail
)

rem ----- pythonw.exe 찾기 (없으면 pyw.exe 런처로 폴백) -----
set "PYW="
for /f "delims=" %%I in ('where pythonw.exe 2^>nul') do if not defined PYW set "PYW=%%I"
if not defined PYW (
    for /f "delims=" %%I in ('where pyw.exe 2^>nul') do if not defined PYW set "PYW=%%I"
)
if not defined PYW (
    echo  [오류] pythonw.exe 를 찾지 못했습니다.
    echo         Python 설치 시 "Add Python to PATH" 를 체크했는지 확인하세요.
    echo         https://www.python.org 에서 설치할 수 있습니다.
    goto :fail
)

echo   - 파이썬 :   %PYW%
echo   - 스크립트 : %SCRIPT%

rem ----- 시작프로그램 폴더 / 바로가기 경로 -----
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LNK=%STARTUP%\Stretch Reminder.lnk"

rem ----- 따옴표 충돌을 피하려고 값은 환경변수로 PowerShell 에 전달 -----
set "SR_TARGET=%PYW%"
set "SR_ARG=%SCRIPT%"
set "SR_WORKDIR=%HERE%"
set "SR_LNK=%LNK%"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$q=[char]34; $ws=New-Object -ComObject WScript.Shell; $sc=$ws.CreateShortcut($env:SR_LNK); $sc.TargetPath=$env:SR_TARGET; $sc.Arguments=$q+$env:SR_ARG+$q; $sc.WorkingDirectory=$env:SR_WORKDIR; $sc.IconLocation=$env:SR_TARGET; $sc.Save()"

if not exist "%LNK%" (
    echo  [오류] 바로가기 생성에 실패했습니다.
    goto :fail
)

echo.
echo  [완료] 시작프로그램에 등록되었습니다.
echo         %LNK%
echo.

rem ----- (선택) 시스템 트레이 아이콘용 패키지 설치 -----
rem        실패해도 본체는 트레이 없이 정상 동작한다.
echo  시스템 트레이 아이콘용 패키지(pystray, pillow) 설치를 시도합니다...
set "PY="
for /f "delims=" %%I in ('where python.exe 2^>nul') do if not defined PY set "PY=%%I"
if not defined PY set "PY=%PYW%"
"%PY%" -m pip install --user --quiet --disable-pip-version-check pystray pillow
if errorlevel 1 (
    echo  [참고] 트레이 패키지 설치 실패 ^(인터넷 미연결 등^). 트레이 없이도 동작합니다.
) else (
    echo  [완료] 트레이 아이콘 사용 준비됨.
)
echo.

rem ----- 지금 바로 한 번 실행 (이미 실행 중이면 중복 안 됨) -----
echo  지금 바로 백그라운드에서 실행합니다...
start "" "%PYW%" "%SCRIPT%"

echo.
echo  다음 부팅부터는 자동으로 실행됩니다.
echo  ^(자동 실행을 해제하려면 uninstall.bat 를 실행하세요.^)
echo.
pause
endlocal
exit /b 0

:fail
echo.
pause
endlocal
exit /b 1
