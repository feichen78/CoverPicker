# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_all

# 获取虚拟环境的 site-packages 路径（在虚拟环境中运行时）
site_packages = os.path.join(sys.prefix, 'Lib', 'site-packages')

# 如果不在虚拟环境中，使用系统的 site-packages
if not os.path.exists(site_packages):
    site_packages = os.path.join(sys.base_prefix, 'Lib', 'site-packages')

# 收集 PySide6 的所有内容
pyside6_datas, pyside6_binaries, pyside6_hiddenimports = collect_all('PySide6')

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[site_packages],  # 关键：添加 site-packages 到搜索路径
    binaries=pyside6_binaries,
    datas=pyside6_datas,
    hiddenimports=pyside6_hiddenimports + ['qasync', 'asyncio', 'sqlite3'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'IPython', 'jupyter', 'pandas', 'numpy', 'scipy',
        'PIL', 'cryptography', 'Crypto', 'yaml', 'httpx', 'uvicorn',
        'fastapi', 'starlette', 'watchfiles', 'websockets', 'anyio',
        'httpcore', 'idna', 'certifi', 'click', 'dotenv', 'oauthlib',
        'requests', 'urllib3',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyd = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyd,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='CoverPicker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CoverPicker',
)