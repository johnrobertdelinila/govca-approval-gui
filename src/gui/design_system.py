"""
Design System - Colors, Typography, Spacing, and Radius for PNPKI Approval Automation.
Extracted from app.py and extended with elevation-based tokens and layout constants.
"""

import sys
import customtkinter as ctk


class Spacing:
    """8px-grid spacing constants for consistent layout."""
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32
    SECTION = 20    # Between major sections
    CARD_PAD = 16   # Inside cards
    PAGE_PAD = 24   # Page margins


class Radius:
    """Corner radius constants."""
    SM = 6      # Inputs, small buttons
    MD = 8      # Cards, panels
    LG = 10     # Primary buttons
    XL = 14     # Icon circles
    PILL = 20   # Badges, tags


class ColorPalette:
    """Modern color palette with elevation-based depth system."""

    # Dark Mode Colors — 5-level elevation staircase
    # Each level ~7-8 RGB units apart for clear visual separation
    DARK = {
        # Elevation levels (sidebar is darkest → overlay is lightest)
        'bg_base':    '#181b25',   # Content floor — clearly lighter than sidebar
        'bg_raised':  '#1f2230',   # Elevated panels
        'bg_card':    '#272b38',   # Cards, dialogs
        'bg_overlay': '#2f3446',   # Hover states, tooltips
        'bg_input':   '#12151e',   # Input fields (recessed below base)

        # Backward-compatible aliases
        'bg_primary':   '#181b25',
        'bg_secondary': '#1f2230',

        # Accent palette (refined)
        'accent_primary':   '#4f8ff7',   # Brighter blue
        'accent_secondary': '#7c7ff2',   # Softer indigo
        'accent_success':   '#22c997',   # Warmer green
        'accent_warning':   '#f7b731',   # Richer amber
        'accent_error':     '#f25d5d',   # Softer red

        # Text
        'text_primary':   '#f9fafb',
        'text_secondary': '#9ca3af',
        'text_muted':     '#6b7280',

        # Borders — bumped for visibility on new bg_card
        'border':       '#353a4c',
        'border_light': '#414758',

        # Sidebar (always dark — the true darkest element)
        'bg_sidebar':             '#111320',
        'bg_sidebar_item':        '#1c2030',
        'bg_sidebar_item_active': '#1a2f50',
        'bg_sidebar_item_hover':  '#1f2640',
        'sidebar_accent_bar':     '#4f8ff7',
        'bg_hover':               '#1f2640',
        'divider':                '#2a2f3d',

        # Badges
        'badge_bg':   '#1e3a5f',
        'badge_text': '#93c5fd',
    }

    # Light Mode Colors
    LIGHT = {
        # Elevation levels
        'bg_base':    '#f0f2f5',   # App background
        'bg_raised':  '#f8f9fb',   # Elevated panels
        'bg_card':    '#ffffff',   # Cards
        'bg_overlay': '#f3f4f6',   # Hover states
        'bg_input':   '#f5f6f8',   # Input fields

        # Backward-compatible aliases
        'bg_primary':   '#f0f2f5',
        'bg_secondary': '#f8f9fb',

        # Accent palette
        'accent_primary':   '#2563eb',
        'accent_secondary': '#4f46e5',
        'accent_success':   '#059669',
        'accent_warning':   '#d97706',
        'accent_error':     '#dc2626',

        # Text
        'text_primary':   '#111827',
        'text_secondary': '#4b5563',
        'text_muted':     '#9ca3af',

        # Borders
        'border':       '#e5e7eb',
        'border_light': '#d1d5db',

        # Sidebar (light-themed to match light mode)
        'bg_sidebar':             '#eceef4',
        'bg_sidebar_item':        '#e2e5ee',
        'bg_sidebar_item_active': '#dbe1f2',
        'bg_sidebar_item_hover':  '#e5e8f0',
        'sidebar_accent_bar':     '#2563eb',
        'bg_hover':               '#dfe2ea',
        'divider':                '#d0d4de',

        # Badges
        'badge_bg':   '#dbeafe',
        'badge_text': '#1e40af',
    }

    @classmethod
    def get(cls, key):
        """Get color based on current appearance mode."""
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            return cls.DARK.get(key, '#ffffff')
        return cls.LIGHT.get(key, '#000000')

    @classmethod
    def get_mode(cls):
        """Get current mode colors dict."""
        mode = ctk.get_appearance_mode()
        return cls.DARK if mode == "Dark" else cls.LIGHT


class Typography:
    """Elegant, modern typography using Avenir Next (macOS) / Segoe UI (Windows)."""

    HEADING_FAMILY = "Segoe UI" if sys.platform == "win32" else "Avenir Next"
    BODY_FAMILY = "Segoe UI" if sys.platform == "win32" else "Avenir Next"
    MONO_FAMILY = "Cascadia Code" if sys.platform == "win32" else "SF Mono"

    @classmethod
    def _get_font(cls, family, size, weight="normal"):
        try:
            return ctk.CTkFont(family=family, size=size, weight=weight)
        except Exception:
            return ctk.CTkFont(size=size, weight=weight)

    @classmethod
    def heading_xl(cls):
        return cls._get_font(cls.HEADING_FAMILY, 28, "bold")

    @classmethod
    def heading_lg(cls):
        return cls._get_font(cls.HEADING_FAMILY, 22, "bold")

    @classmethod
    def heading_md(cls):
        return cls._get_font(cls.HEADING_FAMILY, 16, "bold")

    @classmethod
    def heading_sm(cls):
        return cls._get_font(cls.HEADING_FAMILY, 14, "bold")

    @classmethod
    def heading_xs(cls):
        """12px bold — card headers, small section titles."""
        return cls._get_font(cls.HEADING_FAMILY, 12, "bold")

    @classmethod
    def body_lg(cls):
        return cls._get_font(cls.BODY_FAMILY, 15, "normal")

    @classmethod
    def body_md(cls):
        return cls._get_font(cls.BODY_FAMILY, 13, "normal")

    @classmethod
    def body_sm(cls):
        return cls._get_font(cls.BODY_FAMILY, 12, "normal")

    @classmethod
    def caption(cls):
        """10px — timestamps, metadata, small labels."""
        return cls._get_font(cls.BODY_FAMILY, 10, "normal")

    @classmethod
    def section_header(cls):
        return cls._get_font(cls.HEADING_FAMILY, 11, "bold")

    @classmethod
    def mono(cls, size=12):
        return cls._get_font(cls.MONO_FAMILY, size, "normal")

    # Redesign-specific
    @classmethod
    def workflow_title(cls):
        return cls._get_font(cls.HEADING_FAMILY, 24, "bold")

    @classmethod
    def sidebar_item(cls):
        return cls._get_font(cls.HEADING_FAMILY, 13, "bold")

    @classmethod
    def sidebar_description(cls):
        return cls._get_font(cls.BODY_FAMILY, 11, "normal")

    @classmethod
    def badge(cls):
        return cls._get_font(cls.HEADING_FAMILY, 11, "bold")

    @classmethod
    def stat_value(cls):
        return cls._get_font(cls.HEADING_FAMILY, 38, "bold")

    @classmethod
    def stat_label(cls):
        return cls._get_font(cls.BODY_FAMILY, 12, "normal")
