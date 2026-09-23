@echo off
chcp 65001 >nul
echo.
echo  ========================================
echo   premiere-auto-edit  자동 편집 + 자막
echo  ========================================
echo.

if "%~1"=="" (
    echo  [오류] 영상 파일을 이 파일 위에 끌어다 놓으세요!
    echo.
    pause
    exit /b
)

echo  입력: %~1
echo  처리 중... (자막 생성 포함 - 시간이 걸릴 수 있습니다)
echo.

py -m premiere_auto_edit.cli auto "%~1"

echo.
echo  ========================================
echo   완료! XML + SRT 파일이 생성되었습니다.
echo  ========================================
echo.
pause
