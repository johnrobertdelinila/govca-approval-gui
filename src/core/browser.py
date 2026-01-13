"""
Browser setup and Firefox profile detection for GovCA Approval Automation.
Cross-platform support for Windows and macOS.
"""

import os
import sys
import platform


def find_firefox_profile():
    """
    Find the default Firefox profile path.
    Cross-platform: supports Windows, macOS, and Linux.

    Returns:
        str: Path to Firefox profile, or None if not found
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        profile_base = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")
    elif system == "Windows":
        profile_base = os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles")
    elif system == "Linux":
        profile_base = os.path.expanduser("~/.mozilla/firefox")
    else:
        return None

    if not os.path.exists(profile_base):
        return None

    try:
        profiles = [d for d in os.listdir(profile_base)
                    if os.path.isdir(os.path.join(profile_base, d))]

        if not profiles:
            return None

        # Look for default profile
        for profile in profiles:
            if 'default' in profile.lower():
                return os.path.join(profile_base, profile)

        # Return first profile if no default found
        return os.path.join(profile_base, profiles[0])

    except (PermissionError, OSError):
        return None


def get_bundled_geckodriver():
    """
    Get path to bundled geckodriver for the current platform.
    Works both when running as script and as frozen executable.

    Returns:
        str: Path to geckodriver, or None if not found
    """
    system = platform.system()
    machine = platform.machine().lower()

    # Determine base path
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller)
        base_path = os.path.join(sys._MEIPASS, 'drivers')
    else:
        # Running as script - look for drivers directory
        # First try relative to this file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.join(script_dir, '..', '..', 'drivers')
        base_path = os.path.normpath(base_path)

        # If not found, try project root
        if not os.path.exists(base_path):
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
            base_path = os.path.join(project_root, 'drivers')

    # Determine driver filename based on platform
    if system == "Windows":
        driver_name = "geckodriver.exe"
    elif system == "Darwin":  # macOS
        if 'arm' in machine or 'aarch64' in machine:
            driver_name = "geckodriver-macos-arm64"
        else:
            driver_name = "geckodriver-macos-x64"
    else:  # Linux
        driver_name = "geckodriver-linux64"

    driver_path = os.path.join(base_path, driver_name)

    if os.path.exists(driver_path):
        return driver_path

    # Fallback: try to find geckodriver in PATH
    return None


def get_firefox_profiles_list():
    """
    Get list of all available Firefox profiles.

    Returns:
        list: List of tuples (profile_name, profile_path)
    """
    system = platform.system()

    if system == "Darwin":
        profile_base = os.path.expanduser("~/Library/Application Support/Firefox/Profiles")
    elif system == "Windows":
        profile_base = os.path.expandvars(r"%APPDATA%\Mozilla\Firefox\Profiles")
    elif system == "Linux":
        profile_base = os.path.expanduser("~/.mozilla/firefox")
    else:
        return []

    if not os.path.exists(profile_base):
        return []

    try:
        profiles = []
        for d in os.listdir(profile_base):
            full_path = os.path.join(profile_base, d)
            if os.path.isdir(full_path):
                profiles.append((d, full_path))
        return profiles
    except (PermissionError, OSError):
        return []


def check_firefox_installed():
    """
    Check if Firefox is installed on the system.

    Returns:
        bool: True if Firefox is found, False otherwise
    """
    system = platform.system()

    if system == "Darwin":
        paths = [
            "/Applications/Firefox.app",
            os.path.expanduser("~/Applications/Firefox.app")
        ]
    elif system == "Windows":
        paths = [
            os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"),
            os.path.expandvars(r"%LocalAppData%\Mozilla Firefox\firefox.exe")
        ]
    else:  # Linux
        paths = [
            "/usr/bin/firefox",
            "/usr/local/bin/firefox",
            os.path.expanduser("~/.local/bin/firefox")
        ]

    for path in paths:
        if os.path.exists(path):
            return True

    # Try which/where command as fallback
    import shutil
    return shutil.which("firefox") is not None


def check_geckodriver_available():
    """
    Check if geckodriver is available (bundled or in PATH).

    Returns:
        tuple: (bool, str) - (is_available, path_or_error_message)
    """
    # First check for bundled driver
    bundled = get_bundled_geckodriver()
    if bundled and os.path.exists(bundled):
        return True, bundled

    # Check PATH
    import shutil
    in_path = shutil.which("geckodriver")
    if in_path:
        return True, in_path

    return False, "geckodriver not found. Please install it or ensure drivers/ directory contains the binary."
