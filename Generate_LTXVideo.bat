@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Adobe Stock Video Batch Generator (LTX-2.3)
echo Make sure ComfyUI is running on 127.0.0.1:8188
echo ==============================================
echo.

py script\main_ltxvideo.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred during the batch process.
    pause
    exit /b %ERRORLEVEL%
)

echo.
pause
