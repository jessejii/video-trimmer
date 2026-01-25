@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM 保存启动参数（如果有）
set "startup_arg=%~1"

:main_loop
cls
echo ====================================
echo 视频分割工具
echo ====================================
echo 功能: 输入一个时间点，将视频分割为两部分 (_1 和 _2)
echo.

REM 如果有启动参数且未处理，直接使用
if defined startup_arg (
    set "input_path=!startup_arg!"
    REM 清空启动参数，防止死循环使用同一个文件
    set "startup_arg="
    goto input_time
)

:input_path
set "input_path="
set /p input_path="请输入视频文件路径(支持直接拖入文件): "

if "!input_path!"=="" (
    echo 错误: 路径不能为空
    goto input_path
)

REM 去除引号
set input_path=!input_path:"=!

if not exist "!input_path!" (
    echo 错误: 路径不存在
    goto input_path
)

:input_time
echo.
echo 已选择: !input_path!
echo.
echo 请输入分割时间点
echo 支持格式: 
echo   - MM:SS (例如 1:30)
echo   - HH:MM:SS (例如 1:30:05)
echo   - SS (例如 90)
echo.

set "split_time="
set /p split_time="请输入分割时间: "

if "!split_time!"=="" (
    echo 错误: 时间不能为空
    goto input_time
)

echo.
echo ====================================
echo 开始处理...
echo Filename: !input_path!
echo Split Time: !split_time!
echo ====================================

python split_video.py "!input_path!" "!split_time!"

if errorlevel 1 (
    echo.
    echo 处理出错!
) else (
    echo.
    echo ====================================
    echo 处理完成!
    echo ====================================
)

echo.
echo 按任意键继续处理下一个文件...
pause >nul
goto main_loop
