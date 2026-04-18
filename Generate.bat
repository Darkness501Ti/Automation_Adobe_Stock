@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Adobe Stock Batch Generator
echo Make sure ComfyUI is running on 127.0.0.1:8188
echo ==============================================
echo.

python script\main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred during the batch process.
    pause
    exit /b %ERRORLEVEL%
)

echo.
pause