@echo off
cd /d %~dp0..

echo [1/3] Checking virtual environment...

if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: .venv not found!
    pause
    exit /b
)

echo [2/3] Activating environment...
call .venv\Scripts\activate.bat

echo [3/3] Starting CoverPicker...
python main.py

pause