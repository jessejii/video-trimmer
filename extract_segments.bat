@echo off
setlocal enabledelayedexpansion

REM 如果有命令行参数，直接执行（可透传 --amd 等选项）
if not "%~1"=="" (
    python extract_segments.py %*
    echo.
    pause
    exit /b
)

REM 交互式模式 - 主循环
:start
cls
echo ====================================
echo 视频片段提取工具
echo ====================================
echo.
echo 模式说明:
echo   快速模式(默认): 直接流复制，无损、速度极快，切点对齐关键帧
echo   AMD 硬件加速模式: 重新编码，帧级精确分割，需要 AMD 显卡
echo.
echo 支持处理单个文件或整个文件夹
echo 提示: 可以直接拖拽文件或文件夹到此窗口
echo.

:input_path
set "input_path="
set /p input_path="请输入视频文件或文件夹路径: "

if "!input_path!"=="" (
    echo 错误: 路径不能为空
    echo.
    goto input_path
)

REM 去除路径两端的引号
set input_path=!input_path:"=!

REM 检查路径是否存在
if exist "!input_path!" (
    goto path_exists
)

REM 如果路径不存在，尝试相对路径
if exist "!cd!\!input_path!" (
    set "input_path=!cd!\!input_path!"
    goto path_exists
)

echo 错误: 路径不存在
echo 当前输入: !input_path!
echo 提示: 可以拖拽文件/文件夹到窗口中，或输入完整路径
echo.
goto input_path

:path_exists

echo.
echo 已选择: !input_path!

REM 清空模式相关参数，避免上一轮残留
set "mode_flag="
set "mode_name=快速模式"
set "quality_flag="
set "quality_choice="
set "bitrate_val="
set "bitrate_flag="

echo.
echo ====================================
echo 选择提取模式
echo ====================================
echo   1. 快速模式 - 流复制，无损且速度极快（默认）
echo   2. AMD 硬件加速 - 帧级精确分割，需要 AMD 显卡
echo.

:input_mode
set "mode_choice="
set /p mode_choice="请选择提取模式 [1/2] (默认1): "

if "!mode_choice!"=="" set "mode_choice=1"
if "!mode_choice!"=="1" goto mode_fast
if "!mode_choice!"=="2" goto mode_amd
echo 错误: 无效选择，请输入 1 或 2
echo.
goto input_mode

:mode_fast
set "mode_name=快速模式"
goto segments_intro

:mode_amd
set "mode_flag=--amd"
set "mode_name=AMD 硬件加速模式"

:input_quality
echo.
echo 质量预设:
echo   1. balanced (平衡，默认)
echo   2. speed (速度优先)
echo   3. quality (质量优先)
echo.
set "quality_flag=--quality balanced"
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
    echo.
    goto input_quality
)

:input_bitrate
echo.
set "bitrate_val="
set /p bitrate_val="请输入目标码率 kbps，回车自动匹配原视频码率: "

set "bitrate_flag="
if not "!bitrate_val!"=="" (
    set "bitrate_flag=--bitrate !bitrate_val!"
)

:segments_intro

echo.
echo ====================================
echo 时间段格式说明
echo ====================================
echo 格式: 开始-结束,开始-结束,...
echo.
echo 时间格式支持:
echo   - HH:MM:SS (例如: 1:30:45)
echo   - MM:SS (例如: 1:30)
echo   - SS (例如: 90)
echo.
echo 示例:
echo   1:00-2:00              提取 1分钟 到 2分钟 的片段
echo   1:00-2:00,5:00-6:00    提取两个时间段，各生成独立文件
echo   0:30-1:00,10:00-10:30  提取开头和中间的片段，各生成独立文件
echo.
echo 提示: 每个时间段会输出为单独文件，文件名包含序号和时间范围
echo.

:input_segments
set "segments="
set /p segments="请输入要提取的时间段: "

if "!segments!"=="" (
    echo 错误: 时间段不能为空
    echo.
    goto input_segments
)

echo.
echo 要提取的时间段: !segments!
echo 提取模式: !mode_name!
if not "!mode_flag!"=="" (
    echo 质量预设: !quality_flag!
    echo 目标码率: !bitrate_val! ，留空表示自动匹配原视频码率
)
echo.

:confirm_segments
set "confirm=Y"
set /p confirm="确认时间段正确吗？(Y/N): "
if /i "!confirm!"=="N" goto input_segments
if /i not "!confirm!"=="Y" goto confirm_segments

echo.
echo ====================================
echo 开始处理...
echo 文件: !input_path!
echo 时间段: !segments!
echo 模式: !mode_name!
echo ====================================
echo.

python extract_segments.py !mode_flag! !quality_flag! !bitrate_flag! "!input_path!" "!segments!"

if errorlevel 1 (
    echo.
    echo 处理过程中出现错误
) else (
    echo.
    echo ====================================
    echo 处理完成
    echo ====================================
)

echo.
echo 按回车键继续处理下一个文件，或关闭窗口退出...
pause >nul
goto start
