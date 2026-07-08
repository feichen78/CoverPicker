@echo off

echo ==========================
echo  CoverPicker Git Auto Push
echo ==========================

git add .

set /p msg=请输入提交说明：

git commit -m "%msg%"

git push

echo ==========================
echo  完成提交
echo ==========================
pause