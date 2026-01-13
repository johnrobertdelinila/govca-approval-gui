#!/usr/bin/env python3
"""
GovCA Approval Automation - Desktop GUI Application
Entry point for the application.
"""

import sys
import os

# Ensure the package can be imported when running as script or as module
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)

# Add paths for imports to work in various execution contexts
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)


def main():
    """Application entry point"""
    # Import here to ensure path is set up first
    try:
        from src.app import main as app_main
        app_main()
    except ImportError:
        # Try direct import (when running from src directory)
        from app import main as app_main
        app_main()


if __name__ == "__main__":
    main()
