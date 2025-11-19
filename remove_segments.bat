@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM 如果有命令行参数，直接执行
if not "%~1"=="" (
    python remove_segments.py %*
    echo.
    pause
    exit /b
)

REM 交互式模式 - 主循环
:start
cls
echo ====================================
echo 视频片段删除工具
echo ====================================
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
echo   1:00-2:00              删除 1分钟 到 2分钟
echo   1:00-2:00,5:00-6:00    删除两个时间段
echo   0:30-1:00,10:00-10:30  删除开头和中间的片段
echo.

:input_segments
set "segments="
set /p segments="请输入要删除的时间段: "

if "!segments!"=="" (
    echo 错误: 时间段不能为空
    echo.
    goto input_segments
)

echo.
echo 要删除的时间段: !segments!
echo.

:confirm_segments
set /p confirm="确认时间段正确吗？(Y/N): "
if /i "!confirm!"=="N" goto input_segments
if /i not "!confirm!"=="Y" goto confirm_segments

echo.
echo ====================================
echo 开始处理...
echo ====================================
echo.

python remove_segments.py "!input_path!" "!segments!"

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
