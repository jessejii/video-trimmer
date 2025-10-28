@echo off

cls
echo.
echo ========================================
echo      Video Batch Trimming Tool
echo ========================================
echo.
echo Time format support:
echo   - Seconds: 90
echo   - Min:Sec: 1:30
echo   - Hour:Min:Sec: 1:30:30
echo.
echo ========================================
echo.

REM Interactive input
set /p START_TIME=Enter start trim time (e.g. 1:30): 
set /p END_TIME=Enter end trim time (e.g. 2:00): 

if "%START_TIME%"=="" (
    echo.
    echo Error: Start time cannot be empty
    pause
    exit /b 1
)

if "%END_TIME%"=="" (
    echo.
    echo Error: End time cannot be empty
    pause
    exit /b 1
)

echo.
echo Processing...
echo.

REM Call Python script
python trim_videos.py "%START_TIME%" "%END_TIME%"

echo.
pause
