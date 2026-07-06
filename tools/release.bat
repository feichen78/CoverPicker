@echo off
cd /d %~dp0..

echo ==========================
echo  CoverPicker Release
echo ==========================

set /p version="Enter version (e.g. v3.0): "

git add .
git commit -m "release %version%"
git tag %version%
git push origin main
git push origin %version%

echo.
echo Release %version% done!
pause