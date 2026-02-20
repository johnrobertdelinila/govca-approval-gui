# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for macOS

import os
import platform

# Auto-detect architecture: arm64 for Apple Silicon, x86_64 for Intel
current_arch = 'arm64' if platform.machine() == 'arm64' else 'x86_64'

block_cipher = None

# Get project root (specs/macos/ -> project root)
spec_dir = os.path.dirname(os.path.abspath(SPEC))
project_root = os.path.dirname(os.path.dirname(spec_dir))

a = Analysis(
    [os.path.join(project_root, 'src', 'main.py')],
    pathex=[project_root],
    binaries=[
        # Include BOTH geckodriver versions for Universal Binary support
        (os.path.join(project_root, 'drivers', 'geckodriver-macos-arm64'), 'drivers'),
        (os.path.join(project_root, 'drivers', 'geckodriver-macos-x64'), 'drivers'),
    ],
    datas=[
        (os.path.join(project_root, 'src', 'assets'), 'assets'),
    ],
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
        'wakepy._macos',
        'src.gui',
        'src.gui.design_system',
        'src.gui.components',
        'src.gui.sidebar',
        'src.gui.config_panel',
        'src.gui.progress_panel',
        'src.gui.completion_view',
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
    [],
    exclude_binaries=True,
    name='GovCAApproval',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=current_arch,  # Auto-detect: builds x86_64 on Intel, arm64 on Apple Silicon
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GovCAApproval',
)

app = BUNDLE(
    coll,
    name='GovCAApproval.app',
    icon=os.path.join(project_root, 'src', 'assets', 'AppIcon.icns'),
    bundle_identifier='com.govca.approval',
    info_plist={
        'CFBundleName': 'GovCA Approval',
        'CFBundleDisplayName': 'PNPKI Approval Automation',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.13.0',
        'NSRequiresAquaSystemAppearance': False,
    },
)
