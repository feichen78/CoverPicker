@echo off
chcp 65001 >nul
title CoverPicker 打包工具

echo ========================================
echo   CoverPicker 一键打包工具 (v3.5)
echo   模式: 自动激活虚拟环境 + 使用 spec 配置
echo ========================================
echo.

:: 检查是否在项目根目录
if not exist "main.py" (
    echo [错误] 请在项目根目录下运行此脚本！
    echo 当前目录: %cd%
    pause
    exit /b 1
)

:: 如果存在虚拟环境，激活它
if exist ".venv\Scripts\activate" (
    echo [提示] 检测到虚拟环境，正在激活...
    call .venv\Scripts\activate
    echo [OK] 虚拟环境已激活
    echo 当前 Python 路径:
    where python
) else (
    echo [警告] 未找到虚拟环境，使用系统 Python
)

echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请安装 Python 3.8+ 并添加到 PATH。
    pause
    exit /b 1
)

:: 检查 PyInstaller（必须在虚拟环境中）
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [提示] PyInstaller 未安装，正在安装到虚拟环境...
    pip install pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败，请手动安装。
        pause
        exit /b 1
    )
)

:: 显示当前使用的 Python 和 PyInstaller 路径（帮助调试）
echo 当前 Python 解释器:
where python
echo 当前 PyInstaller 路径:
where pyinstaller
echo.

:: 清理旧构建缓存
echo.
echo [1/3] 清理旧构建缓存...
if exist "build" (
    rmdir /s /q build
)
if exist "dist" (
    rmdir /s /q dist
)

echo.
echo [2/3] 开始打包（使用 coverpicker.spec 配置）...
echo 命令: pyinstaller coverpicker.spec
echo.

python -m PyInstaller coverpicker.spec

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！错误码: %errorlevel%
    pause
    exit /b 1
)

echo.
echo [3/3] 打包完成！
echo.
echo ========================================
echo   打包成功！
echo   输出目录: dist\CoverPicker\
echo   可执行文件: dist\CoverPicker\CoverPicker.exe
echo ========================================
echo.
echo 按任意键退出...
pause