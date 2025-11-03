@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:start
cls
echo ========================================
echo 视频转 MP4 格式工具
echo ========================================
echo.

REM 检查 ffmpeg 是否安装
where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo 错误: 未找到 ffmpeg
    echo 请先安装 ffmpeg 并添加到系统 PATH
    echo.
    pause
    exit /b 1
)

echo 请输入视频文件路径 (支持拖拽文件到窗口):
echo 提示: 可以直接拖拽文件到此窗口，然后按回车
echo.
set /p "input=文件路径: "

REM 去除路径两端的引号
set "input=%input:"=%"

REM 检查文件是否存在
if not exist "%input%" (
    echo.
    echo 错误: 文件不存在
    echo.
    pause
    goto start
)

REM 获取文件信息
for %%F in ("%input%") do (
    set "dir=%%~dpF"
    set "name=%%~nF"
    set "ext=%%~xF"
)

echo.
echo 文件名: %name%%ext%
echo 文件位置: %dir%
echo.

REM 如果已经是 mp4 格式
if /i "%ext%"==".mp4" (
    echo 注意: 文件已经是 MP4 格式
    echo 是否重新编码? (y/n^)
    set /p "reencode="
    if /i not "!reencode!"=="y" (
        echo 已取消
        echo.
        pause
        goto start
    )
)

REM 设置输出文件
set "output=%dir%%name%.mp4"

REM 如果输出文件已存在
if exist "%output%" (
    if /i not "%input%"=="%output%" (
        set "output=%dir%%name%_converted.mp4"
        echo 注意: 目标文件已存在，将保存为 %name%_converted.mp4
        echo.
    )
)

echo 选择转换模式:
echo 1. 快速模式 (只转换容器，不重新编码，速度快)
echo 2. 重新编码 (转换为 H.264，兼容性好但速度慢)
echo.
set /p "mode=请选择 (1/2，默认1): "

if not defined mode set "mode=1"
if "%mode%"=="" set "mode=1"

echo.
echo 开始转换...
echo.

if "%mode%"=="1" (
    echo 使用快速模式...
    REM 快速模式：只复制流，不重新编码
    ffmpeg -i "%input%" -c copy -y "%output%"
) else (
    echo 使用重新编码模式...
    REM 重新编码模式
    ffmpeg -i "%input%" -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k -y "%output%"
)

echo.
echo ========================================

if exist "%output%" (
    echo ✓ 转换成功!
    echo 输出文件: %output%
) else (
    echo ✗ 转换失败
)

echo ========================================
echo.
echo 是否继续转换其他文件? (y/n^)
set /p "continue="
if /i "!continue!"=="y" goto start

echo.
echo 按任意键退出...
pause >nul
