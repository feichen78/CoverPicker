@echo off
cd /d %~dp0..

echo ==========================
echo  CoverPicker Git Push
echo ==========================

git status

echo.
set /p msg="Enter commit message: "

git add .

git commit -m "%msg%"

git push origin main

echo.
echo Done!
pause