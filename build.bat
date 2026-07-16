@echo off
cd /d "%~dp0"

echo =======================================
echo   NPE Tool - PyInstaller Build Script
echo =======================================

where pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] PyInstaller not found. Installing...
    python -m pip install pyinstaller
)

echo [INFO] Cleaning previous builds...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo [INFO] Building executable...
pyinstaller --onedir --name NPE_Tool ^
    --add-data "templates;templates" ^
    --clean ^
    start.py

if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Build complete!
echo Output: dist\NPE_Tool\
echo.
echo Distribution steps:
echo   1. Copy dist\NPE_Tool\ folder to target machine
echo   2. (Optional) Place existing npe.db next to NPE_Tool.exe
echo   3. Double-click NPE_Tool.exe to run
echo.
pause
