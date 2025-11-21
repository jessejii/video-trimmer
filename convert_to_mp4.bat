@echo off
chcp 65001 >nul

REM 视频转 MP4 格式工具 - 启动器
REM 调用 Python 脚本执行实际转换

REM 检查 Python 是否安装
where python >nul 2>nul
if errorlevel 1 (
    echo 错误: 未找到 Python
    echo 请先安装 Python 3 并添加到系统 PATH
    echo.
    pause
    exit /b 1
)

REM 运行 Python 脚本
python "%~dp0convert_to_mp4.py"

REM 如果脚本执行失败
if errorlevel 1 (
    echo.
    echo 脚本执行出错
    pause
)
