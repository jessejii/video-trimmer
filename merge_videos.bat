@echo off
chcp 65001 >nul
:start
python merge_videos.py
echo.
echo 按回车键继续处理，或关闭窗口退出...
pause >nul
goto start