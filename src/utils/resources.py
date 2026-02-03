"""
Resource path helpers for GovCA Approval Automation.
Handles paths for bundled resources (GIF, etc.) in both development and frozen (PyInstaller) modes.
"""

import os
import sys


def get_base_path():
    """Get the base path for resources"""
    if getattr(sys, 'frozen', False):
        # Running as bundled app (PyInstaller)
        return sys._MEIPASS
    else:
        # Running in development - go up from utils/ to src/
        return os.path.dirname(os.path.dirname(__file__))


def get_gif_path():
    """Get the path to the loading GIF with fallback options"""
    base_path = get_base_path()

    # Primary location
    gif_path = os.path.join(base_path, 'assets', 'loading.gif')

    if os.path.exists(gif_path):
        return gif_path

    # Fallback 1: Check relative to executable (for Windows bundled app)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        alt_paths = [
            os.path.join(exe_dir, 'assets', 'loading.gif'),
            os.path.join(exe_dir, '_internal', 'assets', 'loading.gif'),
        ]
        for alt_path in alt_paths:
            if os.path.exists(alt_path):
                return alt_path

    # Fallback 2: Search common development locations
    search_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'assets', 'loading.gif'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'loading.gif'),
        os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'assets', 'loading.gif'),
    ]

    for path in search_paths:
        normalized = os.path.normpath(path)
        if os.path.exists(normalized):
            return normalized

    # Return original path (will cause controlled error in app.py)
    return gif_path


def resource_exists(resource_name):
    """Check if a resource file exists"""
    base_path = get_base_path()
    resource_path = os.path.join(base_path, 'assets', resource_name)
    return os.path.exists(resource_path)


def get_resource_path(resource_name):
    """Get the full path to a resource file"""
    base_path = get_base_path()
    return os.path.join(base_path, 'assets', resource_name)
