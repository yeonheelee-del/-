@echo off
chcp 65001 >nul
echo.
echo  ========================================
echo   premiere-auto-edit  자동 편집 도구
echo  ========================================
echo.

if "%~1"=="" (
    echo  [오류] 영상 파일을 이 파일 위에 끌어다 놓으세요!
    echo.
    echo  사용법: 영상 파일을 이 .bat 파일 위에 드래그 앤 드롭
    echo.
    pause
    exit /b
)

echo  입력: %~1
echo  처리 중...
echo.

py -m premiere_auto_edit.cli auto "%~1" --no-subtitle

echo.
echo  ========================================
echo   완료! 같은 폴더에 XML 파일이 생성되었습니다.
echo   Premiere Pro에서 File ^> Import로 열어주세요.
echo  ========================================
echo.
pause
