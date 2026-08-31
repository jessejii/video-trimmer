@echo off
REM 视频处理工具集 - 一键打包成 Windows 可执行程序
REM
REM   build.bat              单目录模式（默认，推荐）
REM   build.bat --onefile    单文件模式
REM   build.bat --clean      构建前先清理上次产物
REM
REM 图标：把自己准备的 app.ico 放到 assets\ 下即生效，没有也能打包
REM
REM 打包机与运行机需要同样的位数（64 位 Python 打出 64 位 exe）
REM 程序不含 ffmpeg，运行机仍需 PATH 中有 ffmpeg / ffprobe

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo 未找到 python，请先安装 Python 3.9 及以上版本并加入 PATH
    pause
    exit /b 1
)

python build.py %*
if errorlevel 1 (
    echo.
    echo 打包失败，请看上面的输出
    pause
    exit /b 1
)

echo.
echo 打包完成，产物在 dist 目录下
pause
