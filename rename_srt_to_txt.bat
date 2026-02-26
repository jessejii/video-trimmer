@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM 交互式模式 - 主循环
:main_loop
cls
echo ====================================
echo 字幕文件后缀修改工具
echo ====================================
echo.
echo 功能: 将字幕文件(如 .srt) 后缀修改为 .srt.txt
echo 示例: 1.srt -^> 1.srt.txt
echo 支持处理单个文件 or 整个文件夹(含子目录)
echo.

:input_path
set "input_path="
set /p input_path="请输入文件或文件夹路径(可拖入): "

if "!input_path!"=="" (
    goto input_path
)

REM 去除引号
set input_path=!input_path:"=!

if not exist "!input_path!" (
    echo.
    echo 错误: 路径不存在
    echo.
    goto input_path
)

echo.
echo 正在处理: "!input_path!"
echo.

REM 判断是文件还是文件夹
if exist "!input_path!\" (
    REM 是文件夹
    pushd "!input_path!"
    set "count=0"
    
    REM 遍历常见的字幕格式 (支持递归)
    for %%x in (srt ass vtt lrc) do (
        for /r %%f in (*.%%x) do (
             echo 重命名: "%%f" -^> "%%~nxf.txt"
             ren "%%f" "%%~nxf.txt"
             set /a count+=1
        )
    )
    popd
    echo.
    echo 文件夹处理完成，共处理 !count! 个文件。
) else (
    REM 是单个文件
    REM 获取文件所在的目录和文件名
    for %%F in ("!input_path!") do (
        set "filename=%%~nxF"
        set "parent_dir=%%~dpF"
    )
    
    pushd "!parent_dir!"
    echo 重命名: "!filename!" -^> "!filename!.txt"
    ren "!filename!" "!filename!.txt"
    popd
    
    echo.
    echo 单个文件处理完成。
)

echo.
echo ====================================
echo 按回车键返回开始，或输入 Q 退出...
set /p continue_choice=""
if /i "!continue_choice!"=="Q" (
    exit /b
)
goto main_loop
