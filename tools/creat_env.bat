@echo off
cd /d %~dp0..

echo Creating virtual environment...

python -m venv .venv

call .venv\Scripts\activate.bat

pip install -r requirements.txt

echo Done!
pause