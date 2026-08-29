@echo off
setlocal enabledelayedexpansion

REM 如果有命令行参数，直接执行
if not "%~1"=="" (
    python extract_audio.py %*
    echo.
    pause
    exit /b
)

REM 交互式模式 - 主循环
:start
cls
echo ====================================
echo 视频音频提取工具
echo ====================================
echo.
echo 提取视频中的所有音轨，重编码为 MP3 输出为单独文件
echo 使用最高压缩模式尽量减小体积
echo 输出文件保存到输入文件所在目录
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
echo 开始处理...
echo ====================================
echo.

python extract_audio.py "!input_path!"

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
