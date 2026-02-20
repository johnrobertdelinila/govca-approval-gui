"""
Sidebar - Fixed-width navigation panel with domain selector and workflow navigation.
"""

import customtkinter as ctk
from PIL import Image, ImageDraw

from .design_system import ColorPalette, Typography, Spacing, Radius
from .components import ToolTip, ColorTransition

try:
    from ..utils.settings import (
        get_default_domain, set_default_domain, DOMAIN_LIST,
        get_appearance_mode, set_appearance_mode,
    )
    from ..utils.resources import get_logo_path
except ImportError:
    from utils.settings import (
        get_default_domain, set_default_domain, DOMAIN_LIST,
        get_appearance_mode, set_appearance_mode,
    )
    from utils.resources import get_logo_path


WORKFLOWS = [
    {
        "id": "1",
        "title": "Add User",
        "description": "Batch Approve",
        "accent": "#22c997",
        "icon_shape": "plus",
    },
    {
        "id": "2",
        "title": "Revoke Cert",
        "description": "One-by-One",
        "accent": "#f7b731",
        "icon_shape": "x_mark",
    },
    {
        "id": "3",
        "title": "Assign Group",
        "description": "User Groups",
        "accent": "#7c7ff2",
        "icon_shape": "bars",
    },
]


# Theme mode cycle and display info
_THEME_MODES = ["system", "Dark", "Light"]
_THEME_DISPLAY = {
    "system": "\u25d0  Auto",
    "Dark":   "\u263e  Dark",
    "Light":  "\u2600  Light",
}


class SidebarFrame(ctk.CTkFrame):
    """Fixed 220px sidebar with domain selector, workflow navigation, and settings."""

    SIDEBAR_WIDTH = 220

    def __init__(self, parent, on_workflow_select=None, on_domain_change=None,
                 on_settings_click=None, on_theme_toggle=None, **kwargs):
        kwargs['width'] = self.SIDEBAR_WIDTH
        kwargs['corner_radius'] = 0
        kwargs['fg_color'] = ColorPalette.get('bg_sidebar')
        super().__init__(parent, **kwargs)

        self.pack_propagate(False)

        self._on_workflow_select = on_workflow_select
        self._on_domain_change = on_domain_change
        self._on_settings_click = on_settings_click
        self._on_theme_toggle = on_theme_toggle

        self._selected_workflow = "1"
        self._workflow_items = {}
        self._icon_images = {}  # Keep references to CTkImage objects
        self._disabled = False
        self._current_theme_mode = get_appearance_mode()

        self._build()

    def _create_logo_badge(self, logo_img, display_width=140):
        """Create a white rounded-corner badge from the logo image."""
        if logo_img.mode != "RGBA":
            logo_img = logo_img.convert("RGBA")

        scale = 2  # Retina
        badge_w = display_width * scale
        aspect = logo_img.width / logo_img.height
        badge_h = int(badge_w / aspect)

        # Add padding inside badge
        pad = 12 * scale
        total_w = badge_w + pad
        total_h = badge_h + pad

        # White canvas + resize logo onto it
        badge = Image.new("RGBA", (total_w, total_h), (255, 255, 255, 255))
        logo_resized = logo_img.resize((badge_w, badge_h), Image.Resampling.LANCZOS)
        badge.paste(logo_resized, (pad // 2, pad // 2))

        # Apply rounded corner mask
        radius = 12 * scale
        mask = Image.new("L", badge.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle(
            [0, 0, total_w - 1, total_h - 1],
            radius=radius, fill=255,
        )
        badge.putalpha(mask)

        return badge, (total_w // scale, total_h // scale)

    def _build(self):
        """Build sidebar layout."""
        # === Hero Logo Section ===
        logo_section = ctk.CTkFrame(self, fg_color="transparent")
        logo_section.pack(fill="x", padx=Spacing.LG, pady=(Spacing.LG, Spacing.SM))

        try:
            logo_path = get_logo_path()
            logo_img = Image.open(logo_path)
            badge_img, (disp_w, disp_h) = self._create_logo_badge(logo_img)
            self._logo_image = ctk.CTkImage(
                light_image=badge_img, dark_image=badge_img,
                size=(disp_w, disp_h),
            )
            ctk.CTkLabel(
                logo_section, image=self._logo_image, text="",
                fg_color="transparent",
            ).pack(anchor="center")
        except Exception:
            pass

        # App name — centered
        ctk.CTkLabel(
            logo_section,
            text="PNPKI",
            font=Typography.heading_lg(),
            text_color="#ffffff",
        ).pack(anchor="center", pady=(Spacing.SM, 0))

        # Subtitle — centered
        ctk.CTkLabel(
            logo_section,
            text="Approval Automation",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('text_muted'),
        ).pack(anchor="center", pady=(2, 0))

        # === Divider after logo ===
        ctk.CTkFrame(
            self, height=1, fg_color=ColorPalette.get('divider')
        ).pack(fill="x", padx=Spacing.LG, pady=(Spacing.MD, Spacing.MD))

        # === Domain Section ===
        ctk.CTkLabel(
            self,
            text="DOMAIN",
            font=Typography.section_header(),
            text_color=ColorPalette.get('text_muted'),
        ).pack(anchor="w", padx=Spacing.LG, pady=(0, Spacing.SM))

        self.domain_dropdown = ctk.CTkComboBox(
            self,
            width=self.SIDEBAR_WIDTH - 32,
            height=32,
            values=DOMAIN_LIST,
            state="readonly",
            font=Typography.body_sm(),
            dropdown_font=Typography.body_sm(),
            corner_radius=Radius.SM,
            border_width=1,
            border_color=ColorPalette.get('divider'),
            fg_color=ColorPalette.get('bg_sidebar_item'),
            button_color=ColorPalette.get('accent_primary'),
            button_hover_color=ColorPalette.get('accent_secondary'),
            text_color="#ffffff",
            command=self._handle_domain_change,
        )
        self.domain_dropdown.set(get_default_domain())
        self.domain_dropdown.pack(padx=Spacing.LG, pady=(0, Spacing.XS))

        # Counterpart indicator
        self.counterpart_label = ctk.CTkLabel(
            self,
            text="",
            font=Typography.sidebar_description(),
            text_color=ColorPalette.get('text_muted'),
        )
        self.counterpart_label.pack(anchor="w", padx=18, pady=(0, Spacing.MD))
        self._update_counterpart_indicator()

        # === Divider ===
        ctk.CTkFrame(
            self, height=1, fg_color=ColorPalette.get('divider')
        ).pack(fill="x", padx=Spacing.LG, pady=(0, Spacing.MD))

        # === Workflow Section Label ===
        ctk.CTkLabel(
            self,
            text="WORKFLOWS",
            font=Typography.section_header(),
            text_color=ColorPalette.get('text_muted'),
        ).pack(anchor="w", padx=Spacing.LG, pady=(0, Spacing.SM))

        # === Workflow Navigation ===
        self._workflow_container = ctk.CTkFrame(self, fg_color="transparent")
        self._workflow_container.pack(fill="x", padx=10)

        for wf in WORKFLOWS:
            self._create_workflow_item(wf)

        # === Spacer ===
        spacer = ctk.CTkFrame(self, fg_color="transparent")
        spacer.pack(fill="both", expand=True)

        # === Bottom Section ===
        ctk.CTkFrame(
            self, height=1, fg_color=ColorPalette.get('divider')
        ).pack(fill="x", padx=Spacing.LG, pady=(0, Spacing.SM))

        # Settings button
        self.settings_btn = ctk.CTkButton(
            self,
            text="\u2699  Settings",
            width=self.SIDEBAR_WIDTH - 32,
            height=32,
            font=Typography.body_sm(),
            fg_color="transparent",
            hover_color=ColorPalette.get('bg_hover'),
            text_color=ColorPalette.get('text_secondary'),
            anchor="w",
            corner_radius=Radius.SM,
            command=self._handle_settings_click,
        )
        self.settings_btn.pack(padx=Spacing.LG, pady=(0, Spacing.XS))

        # Theme toggle button
        self.theme_btn = ctk.CTkButton(
            self,
            text=_THEME_DISPLAY.get(self._current_theme_mode, "\u25d0  Auto"),
            width=self.SIDEBAR_WIDTH - 32,
            height=32,
            font=Typography.body_sm(),
            fg_color="transparent",
            hover_color=ColorPalette.get('bg_hover'),
            text_color=ColorPalette.get('text_secondary'),
            anchor="w",
            corner_radius=Radius.SM,
            command=self._cycle_theme,
        )
        self.theme_btn.pack(padx=Spacing.LG, pady=(0, Spacing.SM))

        # Session indicator with CTkFrame dot
        self.session_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.session_frame.pack(fill="x", padx=18, pady=(0, Spacing.XS))

        self.session_dot = ctk.CTkFrame(
            self.session_frame,
            width=6, height=6,
            corner_radius=3,
            fg_color=ColorPalette.get('text_muted'),
        )
        self.session_dot.pack(side="left", padx=(0, Spacing.SM))

        self.session_label = ctk.CTkLabel(
            self.session_frame,
            text="No Session",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('text_muted'),
        )
        self.session_label.pack(side="left")

        # Version
        ctk.CTkLabel(
            self,
            text="v1.0.0",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('text_muted'),
        ).pack(anchor="w", padx=18, pady=(2, Spacing.MD))

        # Apply initial selection
        self._apply_selection("1")

    @staticmethod
    def _draw_workflow_icon(shape, size=56):
        """Draw a clean geometric icon using PIL at 2x resolution."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pad = size // 5       # ~11px padding
        bar_h = size // 9     # ~6px bar thickness
        cx, cy = size // 2, size // 2

        white = (255, 255, 255)

        if shape == "plus":
            # Horizontal bar
            draw.rounded_rectangle(
                [pad, cy - bar_h // 2, size - pad, cy + bar_h // 2],
                radius=bar_h // 2, fill=white,
            )
            # Vertical bar
            draw.rounded_rectangle(
                [cx - bar_h // 2, pad, cx + bar_h // 2, size - pad],
                radius=bar_h // 2, fill=white,
            )
        elif shape == "x_mark":
            # Two diagonal thick lines as polygons
            w = bar_h * 0.7  # half-width of stroke
            # Top-left to bottom-right
            draw.polygon([
                (pad + w, pad), (pad, pad + w),
                (size - pad - w, size - pad), (size - pad, size - pad - w),
            ], fill=white)
            # Top-right to bottom-left
            draw.polygon([
                (size - pad - w, pad), (size - pad, pad + w),
                (pad + w, size - pad), (pad, size - pad - w),
            ], fill=white)
        elif shape == "bars":
            # Three horizontal bars evenly spaced
            total_gap = size - 2 * pad
            spacing = total_gap // 4
            for i in range(3):
                y = pad + spacing * (i + 1) - bar_h // 2
                draw.rounded_rectangle(
                    [pad, y, size - pad, y + bar_h],
                    radius=bar_h // 2, fill=white,
                )
        return img

    def _create_workflow_item(self, wf):
        """Create a single workflow navigation item."""
        item_frame = ctk.CTkFrame(
            self._workflow_container,
            fg_color="transparent",
            corner_radius=Radius.MD,
            height=60,
        )
        item_frame.pack(fill="x", pady=2)
        item_frame.pack_propagate(False)

        # Accent bar (3px, left edge)
        accent_bar = ctk.CTkFrame(
            item_frame, width=3, corner_radius=2,
            fg_color="transparent",
        )
        accent_bar.place(x=0, rely=0.15, relheight=0.7)

        inner = ctk.CTkFrame(item_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=Spacing.SM, pady=Spacing.SM)

        # Colored icon circle
        icon_circle = ctk.CTkFrame(
            inner,
            width=28,
            height=28,
            corner_radius=Radius.XL,
            fg_color=wf["accent"],
        )
        icon_circle.pack(side="left", padx=(0, 10))
        icon_circle.pack_propagate(False)

        # PIL-drawn geometric icon
        icon_img = self._draw_workflow_icon(wf["icon_shape"])
        icon_ctk = ctk.CTkImage(light_image=icon_img, dark_image=icon_img, size=(14, 14))
        self._icon_images[wf["id"]] = icon_ctk  # prevent GC
        icon_label = ctk.CTkLabel(
            icon_circle, image=icon_ctk, text="",
            fg_color="transparent", width=0, height=0,
        )
        icon_label.place(relx=0.5, rely=0.5, anchor="center")

        # Title + description
        text_frame = ctk.CTkFrame(inner, fg_color="transparent")
        text_frame.pack(side="left", fill="x", expand=True)

        title_label = ctk.CTkLabel(
            text_frame,
            text=wf["title"],
            font=Typography.sidebar_item(),
            text_color="#ffffff",
            anchor="w",
        )
        title_label.pack(anchor="w")

        desc_label = ctk.CTkLabel(
            text_frame,
            text=wf["description"],
            font=Typography.sidebar_description(),
            text_color=ColorPalette.get('text_muted'),
            anchor="w",
        )
        desc_label.pack(anchor="w")

        # Hover transition
        hover_transition = ColorTransition(item_frame, "fg_color", 150, 8)

        # Store references
        self._workflow_items[wf["id"]] = {
            "frame": item_frame,
            "inner": inner,
            "icon_circle": icon_circle,
            "icon_label": icon_label,
            "title": title_label,
            "description": desc_label,
            "accent": wf["accent"],
            "accent_bar": accent_bar,
            "hover_transition": hover_transition,
        }

        # Bind click + hover to all widgets in the item
        clickable = [item_frame, inner, icon_circle, icon_label, text_frame,
                     title_label, desc_label]
        for w in clickable:
            w.bind("<Button-1>", lambda e, wid=wf["id"]: self._handle_workflow_click(wid))
            w.bind("<Enter>", lambda e, wid=wf["id"]: self._on_hover(wid, True))
            w.bind("<Leave>", lambda e, wid=wf["id"]: self._on_hover(wid, False))
            w.configure(cursor="hand2")

    def _apply_selection(self, workflow_id):
        """Update visual state for the selected workflow."""
        for wid, widgets in self._workflow_items.items():
            if wid == workflow_id:
                widgets["frame"].configure(fg_color=ColorPalette.get('bg_sidebar_item_active'))
                widgets["title"].configure(text_color=ColorPalette.get('accent_primary'))
                widgets["accent_bar"].configure(fg_color=ColorPalette.get('sidebar_accent_bar'))
            else:
                widgets["frame"].configure(fg_color="transparent")
                widgets["title"].configure(text_color="#ffffff")
                widgets["accent_bar"].configure(fg_color="transparent")

    def _on_hover(self, workflow_id, entering):
        """Smooth hover highlight for non-selected items."""
        if self._disabled:
            return
        if workflow_id == self._selected_workflow:
            return
        widgets = self._workflow_items[workflow_id]
        if entering:
            widgets["hover_transition"].transition_to(
                ColorPalette.get('bg_sidebar_item_hover'),
            )
        else:
            widgets["hover_transition"].transition_to(
                ColorPalette.get('bg_sidebar'),
            )

    def _handle_workflow_click(self, workflow_id):
        if self._disabled:
            return
        if workflow_id == self._selected_workflow:
            return
        self._selected_workflow = workflow_id
        self._apply_selection(workflow_id)
        if self._on_workflow_select:
            self._on_workflow_select(workflow_id)

    def _handle_domain_change(self, domain):
        set_default_domain(domain)
        self._update_counterpart_indicator()
        if self._on_domain_change:
            self._on_domain_change(domain)

    def _handle_settings_click(self):
        if self._on_settings_click:
            self._on_settings_click()

    def _cycle_theme(self):
        """Cycle through system -> Dark -> Light -> system."""
        idx = _THEME_MODES.index(self._current_theme_mode) if self._current_theme_mode in _THEME_MODES else 0
        self._current_theme_mode = _THEME_MODES[(idx + 1) % len(_THEME_MODES)]
        self.theme_btn.configure(text=_THEME_DISPLAY.get(self._current_theme_mode, "\u25d0  Auto"))
        if self._on_theme_toggle:
            self._on_theme_toggle(self._current_theme_mode)

    def _update_counterpart_indicator(self):
        domain = self.domain_dropdown.get()
        cp = self._compute_counterpart(domain)
        if cp:
            self.counterpart_label.configure(text=f"+ {cp}")
        else:
            self.counterpart_label.configure(text="")

    @staticmethod
    def _compute_counterpart(domain):
        if "Sign" in domain:
            return domain.replace("Sign", "Auth")
        elif "Auth" in domain:
            return domain.replace("Auth", "Sign")
        return None

    # --- Public API ---

    def get_selected_workflow(self):
        return self._selected_workflow

    def get_domain(self):
        return self.domain_dropdown.get()

    def set_disabled(self, disabled):
        """Dim sidebar during automation."""
        self._disabled = disabled
        state = "disabled" if disabled else "readonly"
        self.domain_dropdown.configure(state=state)
        for wid, widgets in self._workflow_items.items():
            opacity_color = ColorPalette.get('text_muted') if disabled else "#ffffff"
            if wid != self._selected_workflow:
                widgets["title"].configure(text_color=opacity_color)

    def update_session_status(self, active):
        """Update session indicator."""
        if active:
            self.session_dot.configure(fg_color=ColorPalette.get('accent_success'))
            self.session_label.configure(
                text="Session Active",
                text_color=ColorPalette.get('accent_success'),
            )
        else:
            self.session_dot.configure(fg_color=ColorPalette.get('text_muted'))
            self.session_label.configure(
                text="No Session",
                text_color=ColorPalette.get('text_muted'),
            )

    def update_colors(self):
        """Refresh colors on theme change."""
        self.configure(fg_color=ColorPalette.get('bg_sidebar'))
        self.domain_dropdown.configure(
            border_color=ColorPalette.get('divider'),
            fg_color=ColorPalette.get('bg_sidebar_item'),
            button_color=ColorPalette.get('accent_primary'),
            button_hover_color=ColorPalette.get('accent_secondary'),
        )
        self.settings_btn.configure(
            hover_color=ColorPalette.get('bg_hover'),
            text_color=ColorPalette.get('text_secondary'),
        )
        self.theme_btn.configure(
            hover_color=ColorPalette.get('bg_hover'),
            text_color=ColorPalette.get('text_secondary'),
        )
        self._apply_selection(self._selected_workflow)
        self._update_counterpart_indicator()
