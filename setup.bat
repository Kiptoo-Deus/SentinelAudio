@echo off
echo ============================================
echo   SENTINEL AUDIO - Setup
echo ============================================
echo.

echo [1/3] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ from python.org
    pause
    exit /b 1
)

echo [2/3] Installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed. Check your internet connection.
    pause
    exit /b 1
)

echo [3/3] Setup complete.
echo.
echo To run Sentinel Audio:
echo   run.bat
echo.
pause
