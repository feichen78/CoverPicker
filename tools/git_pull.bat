@echo off
cd /d %~dp0..

echo ==========================
echo  CoverPicker Git Pull
echo ==========================

git pull origin main

echo Done!
pause