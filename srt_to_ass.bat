@echo off
chcp 65001 >nul
echo ================================
echo    SRT转ASS字幕格式转换工具
echo ================================
echo.

if "%~1"=="" (
    set /p srt_file="请输入SRT文件路径: "
) else (
    set srt_file=%~1
)

if not exist "%srt_file%" (
    echo 错误: 文件不存在
    pause
    exit /b 1
)

python srt_to_ass.py "%srt_file%"

echo.
pause
