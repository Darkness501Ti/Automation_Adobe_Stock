@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Adobe Stock Batch Generator (Z-Image-Base)
echo Make sure ComfyUI is running on 127.0.0.1:8188
echo ==============================================
echo.

py script\main_zimage.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred during the batch process.
    pause
    exit /b %ERRORLEVEL%
)

echo.
pause
