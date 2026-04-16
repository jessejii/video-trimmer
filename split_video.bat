@echo off
setlocal enabledelayedexpansion

REM 如果有命令行参数，直接执行
set "startup_arg=%~1"

:main_loop
cls
echo ====================================
echo 视频分割工具
echo ====================================
echo 功能: 将视频按时间点分割成多段，输出文件名自动加序号 (_1, _2, _3 ...)
echo.

REM 如果有启动参数，跳过路径输入（仅首次生效）
if defined startup_arg (
    set "input_path=!startup_arg!"
    REM 清除启动参数，避免循环时重复使用
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

:input_mode
echo.
echo 分割模式:
echo   1. 快速无损分割（关键帧对齐，速度极快，可能略不精确）
echo   2. 精确分割（帧级精确，非关键帧处短重编码）
echo.
set "mode_choice="
set /p mode_choice="请选择模式 [1/2] (默认1): "

if "!mode_choice!"=="" set "mode_choice=1"
if "!mode_choice!"=="1" (
    set "mode_flag="
    echo 已选择: 快速无损分割
) else if "!mode_choice!"=="2" (
    set "mode_flag=--precise"
    echo 已选择: 精确分割
) else (
    echo 错误: 无效选择
    goto input_mode
)

echo.
echo ====================================
echo 开始分割...
echo Filename: !input_path!
echo Split Time: !split_time!
echo Mode: !mode_flag!
echo ====================================

python split_video.py "!input_path!" "!split_time!" !mode_flag!

if errorlevel 1 (
    echo.
    echo 分割过程中出错!
) else (
    echo.
    echo ====================================
    echo 分割完成!
    echo ====================================
)

echo.
echo 按回车键返回开始，或输入 Q 退出...
set /p continue_choice=""
if /i "!continue_choice!"=="Q" (
    exit /b
)
goto main_loop
