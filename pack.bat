@echo off
chcp 65001 >nul
title CoverPicker 打包工具
echo ========================================
echo   CoverPicker 一键打包工具 (v2.1)
echo ========================================
echo.

:: 检查是否在项目根目录
if not exist "main.py" (
    echo [错误] 请在项目根目录下运行此脚本！
    echo 当前目录: %cd%
    pause
    exit /b 1
)

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请安装 Python 3.8+ 并添加到 PATH。
    pause
    exit /b 1
)

:: 检查 PyInstaller
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [提示] PyInstaller 未安装，正在安装...
    pip install pyinstaller
    if errorlevel 1 (
        echo [错误] PyInstaller 安装失败，请手动安装。
        pause
        exit /b 1
    )
)

:: 检测 UPX（优化3）
set upx_arg=
where upx >nul 2>&1
if not errorlevel 1 (
    set upx_arg=--upx-dir "C:\upx"
    echo [提示] 使用 UPX 压缩（压缩包体积减少 20-30%%）
) else (
    echo [提示] UPX 未安装，跳过压缩。如需启用，请下载 UPX 并放置到 C:\upx
)

:: 检测虚拟环境
set path_arg=
if exist ".venv\Lib\site-packages" (
    set path_arg=--paths .venv\Lib\site-packages
    echo 使用虚拟环境包路径: .venv\Lib\site-packages
) else (
    echo 未找到虚拟环境，使用系统 Python 包路径。
)

:: 清理旧构建（可选）
echo.
echo [1/3] 清理旧构建缓存...
if exist "build" (
    rmdir /s /q build
)
if exist "dist" (
    rmdir /s /q dist
)

echo.
echo [2/3] 开始打包...
echo 命令: pyinstaller --onedir --name CoverPicker --windowed %path_arg% --collect-all PySide6 --collect-all shiboken6 --hidden-import qasync --hidden-import src.database --hidden-import src.video_scanner --hidden-import src.controllers.segment_controller --noconfirm %upx_arg% main.py
echo.

python -m PyInstaller --onedir --name CoverPicker --windowed %path_arg% --collect-all PySide6 --collect-all shiboken6 --hidden-import qasync --hidden-import src.database --hidden-import src.video_scanner --hidden-import src.controllers.segment_controller --noconfirm %upx_arg% main.py

if errorlevel 1 (
    echo.
    echo [错误] 打包失败！请检查错误信息。
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
echo.
if not "%upx_arg%"=="" (
    echo   已启用 UPX 压缩，体积已优化。
)
echo ========================================
pause