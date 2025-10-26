@echo off
chcp 65001 >nul
setlocal

REM 检查参数
if "%~1"=="" (
    echo 用法: trim_videos.bat ^<开头秒数^> ^<结尾秒数^> [输入文件夹] [输出文件夹]
    echo.
    echo 示例:
    echo   trim_videos.bat 60 120
    echo   trim_videos.bat 1:30 2:00
    echo   trim_videos.bat 10 10 video trimmed
    exit /b 1
)

if "%~2"=="" (
    echo 错误: 请提供结尾秒数
    echo 用法: trim_videos.bat ^<开头秒数^> ^<结尾秒数^> [输入文件夹] [输出文件夹]
    exit /b 1
)

REM 调用 Python 脚本
python trim_videos.py %*

endlocal
