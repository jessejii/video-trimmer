@echo off
chcp 65001 >nul

:start
cls
echo ================================
echo    SRT转ASS字幕格式转换工具
echo ================================
echo.

if "%~1"=="" (
    set /p srt_file="请输入SRT文件路径 (输入 q 退出): "
) else (
    set srt_file=%~1
    set first_run=1
)

if /i "%srt_file%"=="q" (
    echo 退出程序...
    exit /b 0
)

if not exist "%srt_file%" (
    echo 错误: 文件不存在
    echo.
    pause
    goto start
)

python srt_to_ass.py "%srt_file%"

echo.
if defined first_run (
    pause
    exit /b 0
)

set srt_file=
goto start
