@echo off
setlocal enabledelayedexpansion

REM 如果有命令行参数，直接执行
if not "%~1"=="" (
    python batch_trim_edges_amd.py %*
    echo.
    pause
    exit /b
)

REM 交互式模式 - 主循环
:main_loop
cls
echo ========================================
echo 批量视频开头结尾裁剪工具 (AMD 显卡加速)
echo ========================================
echo.
echo 此工具会使用 AMD 显卡 (AMF 硬件加速) 批量剪掉
echo 视频开头的 X 时间和结尾的 Y 时间。
echo 特点: 帧级精确，无需关键帧对齐，速度极快！
echo 提示: 可以直接拖拽文件夹到此窗口
echo.

:input_path
set "input_path="
set /p input_path="请输入视频文件夹路径: "

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
if exist "%cd%\!input_path!" (
    set "input_path=%cd%\!input_path!"
    goto path_exists
)

echo 错误: 路径不存在
echo 当前输入: !input_path!
echo.
goto input_path

:path_exists

echo.
echo 已选择目录: !input_path!
echo.
echo ========================================
echo 裁剪时长设置
echo ========================================
echo 时间格式支持:
echo   - HH:MM:SS (例如: 00:01:30 代表1分30秒)
echo   - MM:SS (例如: 1:30)
echo   - SS (例如: 90)
echo.

:input_start
set "start_cut="
set /p start_cut="请输入开头要切掉的时长 (直接回车为0): "

if "!start_cut!"=="" (
    set "start_cut=0"
)

echo.

:input_end
set "end_cut="
set /p end_cut="请输入结尾要切掉的时长 (直接回车为0): "

if "!end_cut!"=="" (
    set "end_cut=0"
)

echo.

:input_quality
echo ========================================
echo AMD 质量设置
echo ========================================
echo   1. balanced   (默认, 平衡速度与质量)
echo   2. speed      (优先速度)
echo   3. quality    (优先质量)
echo.
set "quality_choice="
set /p quality_choice="请选择质量预设 (1/2/3，直接回车为 1): "
if "!quality_choice!"=="" set "quality_choice=1"
if "!quality_choice!"=="1" set "quality=balanced"
if "!quality_choice!"=="2" set "quality=speed"
if "!quality_choice!"=="3" set "quality=quality"
if not defined quality (
    echo 错误: 输入无效，请输入 1/2/3
    echo.
    goto input_quality
)

echo.
echo ========================================
echo 裁剪设置确认
echo ========================================
echo 文件夹:     !input_path!
echo 开头切割:   !start_cut! (从0开始往后切这么长)
echo 结尾切割:   !end_cut! (从末尾往前切这么长)
echo 质量预设:   !quality!
echo.
echo 处理后的文件将保存在子目录 [cut] 下。
echo.

:confirm_settings
set /p confirm="确认开始处理吗？(Y/N，默认Y): "
if "!confirm!"=="" set "confirm=Y"
if /i "!confirm!"=="N" goto main_loop
if /i not "!confirm!"=="Y" goto confirm_settings

echo.
echo ========================================
echo 正在运行 AMD 显卡加速脚本...
echo ========================================
echo.

python batch_trim_edges_amd.py "!input_path!" "!start_cut!" "!end_cut!" --quality "!quality!"

if errorlevel 1 (
    echo.
    echo 处理过程中出现错误
) else (
    echo.
    echo ========================================
    echo 批量裁切处理完成 (AMD 显卡加速)！
    echo ========================================
)

echo.
echo 按回车键返回主菜单，或输入 Q 退出...
set /p continue_choice=""
if /i "!continue_choice!"=="Q" (
    exit /b
)
goto main_loop
