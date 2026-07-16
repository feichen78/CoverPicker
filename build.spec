# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_all

# 使用 collect_all 一次性收集 PySide6 和 shiboken6 的所有内容
pyside6_datas, pyside6_binaries, pyside6_hiddenimports = collect_all('PySide6')
shiboken6_datas, shiboken6_binaries, shiboken6_hiddenimports = collect_all('shiboken6')

# 合并
all_datas = pyside6_datas + shiboken6_datas
all_binaries = pyside6_binaries + shiboken6_binaries
all_hiddenimports = pyside6_hiddenimports + shiboken6_hiddenimports + [
    'qasync',
    'asyncio',
    'sqlite3',
]

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddenimports,
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