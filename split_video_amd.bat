@echo off
setlocal enabledelayedexpansion

REM 如果有命令行参数，直接执行
set "startup_arg=%~1"

:main_loop
cls
echo ================================================
echo  AMD 显卡加速视频分割工具（帧级精确）
echo ================================================
echo 功能: 使用 AMD AMF 硬件加速分割视频，帧级精确
echo       无需关键帧对齐，硬件解码+编码速度极快
echo.
echo 注意: 需要 AMD 显卡驱动 + 支持 AMF 的 ffmpeg
echo.

REM 如果有启动参数，跳过路径输入
if defined startup_arg (
    set "input_path=!startup_arg!"
    set "startup_arg="
    goto input_time
)

:input_path
set "input_path="
set /p input_path="请输入视频文件路径(可拖拽文件到此窗口): "

if "!input_path!"=="" (
    echo 错误: 路径不能为空
    goto input_path
)

REM 去除引号
set input_path=!input_path:"=!

if not exist "!input_path!" (
    echo 错误: 文件不存在
    goto input_path
)

:input_time
echo.
echo 已选择: !input_path!
echo.
echo 请输入分割时间点，支持以下格式:
echo 时间格式:
echo   - MM:SS (例如 1:30)
echo   - HH:MM:SS (例如 1:30:05)
echo   - SS (例如 90)
echo   - 多个时间点: 1:30,3:00,5:20
echo.

set "split_time="
set /p split_time="请输入分割时间点: "

if "!split_time!"=="" (
    echo 错误: 时间不能为空
    goto input_time
)

:input_quality
echo.
echo 质量预设:
echo   1. balanced (平衡，默认)
echo   2. speed (速度优先)
echo   3. quality (质量优先)
echo.
set "quality_choice="
set /p quality_choice="请选择质量预设 [1/2/3] (默认1): "

if "!quality_choice!"=="" set "quality_choice=1"
if "!quality_choice!"=="1" (
    set "quality_flag=--quality balanced"
) else if "!quality_choice!"=="2" (
    set "quality_flag=--quality speed"
) else if "!quality_choice!"=="3" (
    set "quality_flag=--quality quality"
) else (
    echo 错误: 无效选择
    goto input_quality
)

:input_bitrate
echo.
set "bitrate_val="
set /p bitrate_val="请输入目标码率(kbps, 回车则自动匹配原视频码率): "

REM 可选码率控制
set "bitrate_flag="
if not "!bitrate_val!"=="" (
    set "bitrate_flag=--bitrate !bitrate_val!"
)

echo.
echo ================================================
echo 开始分割...
echo 文件: !input_path!
echo 分割点: !split_time!
echo 质量预设: !quality_flag!
echo 码率: !bitrate_val! (空=自动匹配原视频)
echo ================================================

python split_video_amd.py "!input_path!" "!split_time!" !quality_flag! !bitrate_flag!

if errorlevel 1 (
    echo.
    echo 分割过程中出错!
) else (
    echo.
    echo ================================================
    echo 分割完成!
    echo ================================================
)

echo.
echo 按回车键返回开始，或输入 Q 退出...
set /p continue_choice=""
if /i "!continue_choice!"=="Q" (
    exit /b
)
goto main_loop
