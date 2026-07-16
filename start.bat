@echo off
cd /d "%~dp0"

REM Kill any process using port 8080 (prevents "Internal Server Error" on restart)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080"') do (
    if "%%a" NEQ "0" (
        taskkill /F /PID %%a >nul 2>&1
        echo [Cleanup] Stopped previous server (PID: %%a)
    )
)

echo ========================================
echo    NPE - New Program Process Evaluation
echo ========================================
echo.
echo Installing flask...
python -m pip install flask --quiet 2>nul
echo.
echo Starting server...
echo Browser will open automatically at http://localhost:8080
echo Press Ctrl+C to stop.
echo.
python start.py
pause