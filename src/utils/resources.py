"""
Resource path helpers for GovCA Approval Automation.
Handles paths for bundled resources (GIF, etc.) in both development and frozen (PyInstaller) modes.
"""

import os
import sys


def get_gif_path():
    """Get the path to the loading GIF"""
    if getattr(sys, 'frozen', False):
        # Running as bundled app
        base_path = sys._MEIPASS
    else:
        # Running in development
        base_path = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_path, 'assets', 'loading.gif')
