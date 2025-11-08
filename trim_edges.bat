@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
echo ====================================
echo 视频开头结尾裁剪工具
echo ====================================
echo.

REM 如果有命令行参数，直接执行
if not "%~1"=="" (
    python trim_edges.py %*
    echo.
    pause
    exit /b
)

REM 交互式模式
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
echo.
echo ====================================
echo 裁剪说明
echo ====================================
echo 此工具用于裁剪视频的开头和结尾部分
echo.
echo 开头时间: 从 0:00 到该时间点的内容会被删除
echo 结尾时间: 从该时间点到视频结束的内容会被删除
echo.
echo 时间格式支持:
echo   - HH:MM:SS (例如: 1:30:45)
echo   - MM:SS (例如: 1:30)
echo   - SS (例如: 90)
echo.
echo 示例:
echo   开头输入 1:00   = 删除 0:00-1:00 的内容, 结尾输入 32:00  = 删除 32:00-结束 的内容
echo.

:input_start
set "start_time="
set /p start_time="请输入开头裁剪时间点 (直接回车跳过): "

if "!start_time!"=="" (
    set "start_time=0"
    echo 跳过开头裁剪
)

echo.

:input_end
set "end_time="
set /p end_time="请输入结尾裁剪时间点 (直接回车跳过): "

if "!end_time!"=="" (
    echo 跳过结尾裁剪
)

echo.
echo ====================================
echo 裁剪设置确认
echo ====================================
if "!start_time!"=="0" (
    echo 开头: 不裁剪
) else (
    echo 开头: 删除 0:00 - !start_time!
)

if "!end_time!"=="" (
    echo 结尾: 不裁剪
) else (
    echo 结尾: 删除 !end_time! - 视频结束
)
echo.

:confirm_settings
set /p confirm="确认设置正确吗？(Y/N): "
if /i "!confirm!"=="N" goto input_start
if /i not "!confirm!"=="Y" goto confirm_settings

echo.
echo ====================================
echo 开始处理...
echo ====================================
echo.

if "!end_time!"=="" (
    python trim_edges.py "!input_path!" "!start_time!"
) else (
    python trim_edges.py "!input_path!" "!start_time!" "!end_time!"
)

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
pause
