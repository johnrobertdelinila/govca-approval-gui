# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Windows

import os

block_cipher = None

# Get project root (specs/windows/ -> project root)
spec_dir = os.path.dirname(os.path.abspath(SPEC))
project_root = os.path.dirname(os.path.dirname(spec_dir))

a = Analysis(
    [os.path.join(project_root, 'src', 'main.py')],
    pathex=[project_root],
    binaries=[
        (os.path.join(project_root, 'drivers', 'geckodriver.exe'), 'drivers'),
    ],
    datas=[],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.firefox',
        'selenium.webdriver.firefox.service',
        'selenium.webdriver.firefox.options',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'wakepy',
        'wakepy._windows',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GovCAApproval',
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
