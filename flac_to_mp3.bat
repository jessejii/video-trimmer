@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo 未检测到 ffmpeg，请先安装并加入 PATH。
    pause
    exit /b 1
)

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

echo ========================================
echo FLAC/音频 转 MP3 工具
echo ========================================
echo.
echo 支持格式: flac, ape, wav, m4a, aac, ogg, opus, wma 等
echo.

set "count=0"
set "failed=0"

for /r "%SCRIPT_DIR%" %%f in (*.flac *.ape *.wav *.m4a *.aac *.ogg *.oga *.opus *.wma *.aiff *.aif *.m4b *.mka) do (
    set "input=%%f"
    set "output=%%~dpnf.mp3"
    
    if exist "!output!" (
        echo 跳过(已存在): %%~nxf
    ) else (
        set /a count+=1
        echo 转换中: %%~nxf -^> %%~nf.mp3
        ffmpeg -hide_banner -y -i "!input!" -map_metadata 0 -codec:a libmp3lame -q:a 0 -id3v2_version 3 "!output!" >nul 2>&1
        if errorlevel 1 (
            echo   [失败] %%~nxf
            set /a failed+=1
        )
    )
)

echo.
echo ========================================
if !count! equ 0 (
    echo 没有找到需要转换的音频文件。
) else (
    echo 转换完成: !count! 个文件，失败: !failed! 个。
)
echo ========================================
echo.
pause
