@echo off
setlocal enabledelayedexpansion

REM 切换到 bat 所在目录，避免相对路径问题
cd /d "%~dp0"

REM 如果有命令行参数，直接透传给 Python 脚本
if not "%~1"=="" (
    python remove_srt_segments.py %*
    echo.
    pause
    exit /b
)

:start
cls
echo ====================================
echo SRT 字幕时间段删除工具
echo ====================================
echo.
echo 提示: 可直接拖拽 .srt 或 .srt.txt 文件到本窗口
echo.

:input_file
set "input_file="
set /p input_file="请输入字幕文件路径(.srt/.srt.txt): "

if "!input_file!"=="" (
    echo 错误: 文件路径不能为空
    echo.
    goto input_file
)

REM 去除两端引号
set "input_file=!input_file:"=!"

if exist "!input_file!" (
    goto file_ok
)

if exist "%cd%\!input_file!" (
    set "input_file=%cd%\!input_file!"
    goto file_ok
)

echo 错误: 文件不存在
echo 当前输入: !input_file!
echo.
goto input_file

:file_ok

REM 校验扩展名（支持 .srt 和 .srt.txt）
set "is_valid_ext=0"
for %%I in ("!input_file!") do (
    set "name=%%~nxI"
    set "ext=%%~xI"
)
if /i "!ext!"==".srt" set "is_valid_ext=1"
if /i "!name:~-8!"==".srt.txt" set "is_valid_ext=1"

if "!is_valid_ext!"=="0" (
    echo 警告: 文件扩展名不是 .srt 或 .srt.txt，仍将尝试处理
    echo.
)

echo.
echo 已选择: !input_file!
echo.
echo ====================================
echo 删除时间段格式说明
echo ====================================
echo 格式: 开始-结束,开始-结束,...
echo 示例: 1:00-2:00,5:00-6:00
echo.
echo 时间格式支持:
echo   - HH:MM:SS,mmm (标准 SRT)
echo   - HH:MM:SS
echo   - MM:SS
echo   - SS
echo.

:input_ranges
set "ranges="
set /p ranges="请输入要删除的时间段: "

if "!ranges!"=="" (
    echo 错误: 时间段不能为空
    echo.
    goto input_ranges
)

echo.
echo 输入文件: !input_file!
echo 删除区间: !ranges!
echo.

:confirm
set "confirm=Y"
set /p confirm="确认开始处理？(Y/N): "
if /i "!confirm!"=="N" goto start
if /i not "!confirm!"=="Y" goto confirm

echo.
echo ====================================
echo 开始处理...
echo ====================================
echo.

python remove_srt_segments.py "!input_file!" "!ranges!"

if errorlevel 1 (
    echo.
    echo 处理失败，请检查输入后重试
) else (
    echo.
    echo ====================================
    echo 处理完成
    echo ====================================
)

echo.
echo 按回车继续处理下一个文件，或直接关闭窗口退出...
pause >nul
goto start
