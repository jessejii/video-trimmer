@echo off
REM 视频处理工具集 - 图形界面启动器
REM 用 pythonw 启动，不弹出控制台黑窗

cd /d "%~dp0"

where pythonw >nul 2>nul
if errorlevel 1 (
    python main.py
) else (
    start "" pythonw main.py
)
