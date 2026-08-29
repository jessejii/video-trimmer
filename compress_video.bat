@echo off
setlocal enabledelayedexpansion

REM 如果有命令行参数，直接执行
if not "%~1"=="" (
    python compress_video.py %*
    echo.
    pause
    exit /b
)

REM 交互式模式 - 主循环
:start
cls
echo ====================================
echo 视频压缩工具
echo ====================================
echo.
echo 使用 H.264 编码压缩视频文件，支持单个文件或批量处理
echo 输出文件保存到输入文件所在目录，文件名添加 _compressed 后缀
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
echo 选择压缩质量
echo ====================================
echo.
echo 1. 低质量 (文件最小, QP 28, 默认)
echo 2. 中等质量 (平衡大小和画质, QP 23)
echo 3. 高质量 (文件较大, QP 18)
echo.

:quality_choice
set "quality_choice="
set /p quality_choice="请选择质量 (1/2/3, 默认1): "

if "!quality_choice!"=="" set "quality_choice=1"

if "!quality_choice!"=="1" (
    set "quality=low"
    goto start_compress
) else if "!quality_choice!"=="2" (
    set "quality=medium"
    goto start_compress
) else if "!quality_choice!"=="3" (
    set "quality=high"
    goto start_compress
) else (
    echo 无效的选择，请输入 1, 2 或 3
    echo.
    goto quality_choice
)

:start_compress
echo.
echo 质量预设: !quality!
echo ====================================
echo 开始处理...
echo ====================================
echo.

python compress_video.py "!input_path!" "!quality!"

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