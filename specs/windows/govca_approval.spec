# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Windows

import os
import sys

block_cipher = None

# Get project root (specs/windows/ -> project root)
spec_dir = os.path.dirname(os.path.abspath(SPEC))
project_root = os.path.dirname(os.path.dirname(spec_dir))
src_dir = os.path.join(project_root, 'src')

# Find customtkinter package location
import customtkinter
ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    [os.path.join(src_dir, 'main.py')],
    pathex=[project_root, src_dir],
    binaries=[
        (os.path.join(project_root, 'drivers', 'geckodriver.exe'), 'drivers'),
    ],
    datas=[
        (os.path.join(src_dir, 'assets'), 'assets'),
        # Include customtkinter package with all its assets
        (ctk_path, 'customtkinter'),
    ],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'PIL.Image',
        'PIL.ImageTk',
        # Selenium - complete list
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.common',
        'selenium.webdriver.common.by',
        'selenium.webdriver.common.keys',
        'selenium.webdriver.common.action_chains',
        'selenium.webdriver.support',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.webdriver.support.wait',
        'selenium.webdriver.firefox',
        'selenium.webdriver.firefox.webdriver',
        'selenium.webdriver.firefox.service',
        'selenium.webdriver.firefox.options',
        'selenium.webdriver.remote',
        'selenium.webdriver.remote.webdriver',
        'selenium.webdriver.remote.webelement',
        'selenium.webdriver.remote.remote_connection',
        'selenium.webdriver.remote.command',
        'selenium.webdriver.remote.errorhandler',
        'selenium.common',
        'selenium.common.exceptions',
        'wakepy',
        'wakepy.methods',
        'wakepy.methods.windows',
        # App modules
        'app',
        'logging_handler',
        'core',
        'core.bot',
        'core.browser',
        'utils',
        'utils.settings',
        'utils.resources',
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
    icon=os.path.join(project_root, 'src', 'assets', 'AppIcon.ico'),
)
