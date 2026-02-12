"""
PNPKI Approval Automation - Main GUI Application
Built with CustomTkinter for a modern, cross-platform look.
Enhanced with elegant design, resizable panels, and responsive layout.
"""

import customtkinter as ctk
import threading
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk
import sys
import os
import subprocess
from PIL import Image, ImageTk

# Handle imports for both package and direct execution
try:
    from .logging_handler import LogBuffer, ProgressTracker
    from .core.bot import GovCAApprovalBot, OperationCancelledException
    from .core.browser import check_firefox_installed, check_geckodriver_available, find_firefox_profile
    from .utils.settings import get_default_domain, set_default_domain, DOMAIN_LIST, AUTH_METHODS, get_auth_method, set_auth_method, get_custom_gif, set_custom_gif
    from .utils.resources import get_gif_path, get_logo_path
except ImportError:
    from logging_handler import LogBuffer, ProgressTracker
    from core.bot import GovCAApprovalBot, OperationCancelledException
    from core.browser import check_firefox_installed, check_geckodriver_available, find_firefox_profile
    from utils.settings import get_default_domain, set_default_domain, DOMAIN_LIST, AUTH_METHODS, get_auth_method, set_auth_method, get_custom_gif, set_custom_gif
    from utils.resources import get_gif_path, get_logo_path

# Set appearance mode to system default
ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


# =============================================================================
# DESIGN SYSTEM - Colors, Typography, Components
# =============================================================================

class ColorPalette:
    """Modern color palette for GovCA App - Professional Government Application"""

    # Dark Mode Colors
    DARK = {
        'bg_primary': '#1a1a2e',       # Deep navy background
        'bg_secondary': '#16213e',      # Panel backgrounds
        'bg_card': '#1f2937',           # Card backgrounds
        'bg_input': '#111827',          # Input field backgrounds
        'accent_primary': '#3b82f6',    # Blue accent
        'accent_secondary': '#6366f1',  # Indigo accent
        'accent_success': '#10b981',    # Emerald green
        'accent_warning': '#f59e0b',    # Amber
        'accent_error': '#ef4444',      # Red
        'text_primary': '#f9fafb',      # Primary text
        'text_secondary': '#9ca3af',    # Secondary/muted text
        'text_muted': '#6b7280',        # Disabled/hint text
        'border': '#374151',            # Subtle borders
        'border_light': '#4b5563',      # Lighter borders
        'sash': '#4b5563',              # Resizable divider
        'sash_hover': '#6b7280',        # Divider hover
    }

    # Light Mode Colors
    LIGHT = {
        'bg_primary': '#f3f4f6',        # Light gray background
        'bg_secondary': '#ffffff',       # White panels
        'bg_card': '#ffffff',           # Card backgrounds
        'bg_input': '#f9fafb',          # Input field backgrounds
        'accent_primary': '#2563eb',    # Blue accent
        'accent_secondary': '#4f46e5',  # Indigo accent
        'accent_success': '#059669',    # Emerald green
        'accent_warning': '#d97706',    # Amber
        'accent_error': '#dc2626',      # Red
        'text_primary': '#111827',      # Primary text
        'text_secondary': '#4b5563',    # Secondary text
        'text_muted': '#9ca3af',        # Disabled/hint text
        'border': '#e5e7eb',            # Subtle borders
        'border_light': '#d1d5db',      # Lighter borders
        'sash': '#d1d5db',              # Resizable divider
        'sash_hover': '#9ca3af',        # Divider hover
    }

    @classmethod
    def get(cls, key):
        """Get color based on current appearance mode"""
        mode = ctk.get_appearance_mode()
        if mode == "Dark":
            return cls.DARK.get(key, '#ffffff')
        return cls.LIGHT.get(key, '#000000')

    @classmethod
    def get_mode(cls):
        """Get current mode colors dict"""
        mode = ctk.get_appearance_mode()
        return cls.DARK if mode == "Dark" else cls.LIGHT


class Typography:
    """Font configurations for consistent typography"""

    # Font families with fallbacks
    HEADING_FAMILY = "Segoe UI" if sys.platform == "win32" else "SF Pro Display"
    BODY_FAMILY = "Segoe UI" if sys.platform == "win32" else "SF Pro Text"
    MONO_FAMILY = "Cascadia Code" if sys.platform == "win32" else "SF Mono"

    # Fallback to system fonts if preferred ones unavailable
    @classmethod
    def _get_font(cls, family, size, weight="normal"):
        try:
            return ctk.CTkFont(family=family, size=size, weight=weight)
        except:
            return ctk.CTkFont(size=size, weight=weight)

    @classmethod
    def heading_xl(cls):
        return cls._get_font(cls.HEADING_FAMILY, 26, "bold")

    @classmethod
    def heading_lg(cls):
        return cls._get_font(cls.HEADING_FAMILY, 20, "bold")

    @classmethod
    def heading_md(cls):
        return cls._get_font(cls.HEADING_FAMILY, 16, "bold")

    @classmethod
    def heading_sm(cls):
        return cls._get_font(cls.HEADING_FAMILY, 14, "bold")

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
    def section_header(cls):
        return cls._get_font(cls.BODY_FAMILY, 11, "bold")

    @classmethod
    def mono(cls, size=12):
        return cls._get_font(cls.MONO_FAMILY, size, "normal")


class CardFrame(ctk.CTkFrame):
    """A card-style frame with modern styling and hover glow"""

    @staticmethod
    def _blend_colors(hex1, hex2, ratio):
        """Blend two hex colors. ratio=0 returns hex1, ratio=1 returns hex2."""
        r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
        r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    def __init__(self, parent, **kwargs):
        # Default card styling
        kwargs.setdefault('corner_radius', 12)
        kwargs.setdefault('border_width', 1)
        kwargs.setdefault('border_color', ColorPalette.get('border'))
        kwargs.setdefault('fg_color', ColorPalette.get('bg_card'))

        super().__init__(parent, **kwargs)

        # Compute glow border color (40% blend toward accent)
        self._normal_border = ColorPalette.get('border')
        self._glow_border = self._blend_colors(
            self._normal_border, ColorPalette.get('accent_primary'), 0.4
        )

        # Hover glow bindings
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_enter(self, event):
        self.configure(border_color=self._glow_border)

    def _on_leave(self, event):
        # Check if pointer is still inside (avoids flicker from child widgets)
        x, y = self.winfo_pointerxy()
        widget_x = self.winfo_rootx()
        widget_y = self.winfo_rooty()
        widget_w = self.winfo_width()
        widget_h = self.winfo_height()
        if widget_x <= x <= widget_x + widget_w and widget_y <= y <= widget_y + widget_h:
            return
        self.configure(border_color=self._normal_border)

    def update_colors(self):
        """Update colors based on current theme"""
        self._normal_border = ColorPalette.get('border')
        self._glow_border = self._blend_colors(
            self._normal_border, ColorPalette.get('accent_primary'), 0.4
        )
        self.configure(
            border_color=self._normal_border,
            fg_color=ColorPalette.get('bg_card')
        )


class ToolTip:
    """Hover tooltip for icon buttons"""
    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tooltip_window = None
        self._after_id = None
        widget.bind('<Enter>', self._schedule)
        widget.bind('<Leave>', self._hide)
        widget.bind('<Button-1>', self._hide)

    def _schedule(self, event=None):
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _show(self):
        if self.tooltip_window:
            return
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.wm_attributes("-topmost", True)
        label = tk.Label(tw, text=self.text, bg="#2d2d2d", fg="#f0f0f0",
                        font=("SF Pro Text", 11), padx=8, pady=4)
        label.pack()

    def _hide(self, event=None):
        self._cancel()
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def _cancel(self):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def update_text(self, text):
        self.text = text


class ResizablePanedWindow(tk.PanedWindow):
    """
    A styled PanedWindow that matches CustomTkinter appearance.
    Provides resizable sash (divider) between panes with visible grip indicator.
    """

    def __init__(self, parent, **kwargs):
        # Get orientation
        orient = kwargs.pop('orient', tk.VERTICAL)

        # Configure PanedWindow styling with wider sash for better usability
        super().__init__(
            parent,
            orient=orient,
            sashwidth=12,  # Increased from 8 for better visibility
            sashpad=0,
            bg=ColorPalette.get('bg_primary'),
            sashrelief=tk.FLAT,
            borderwidth=0,
            opaqueresize=True
        )

        # Grip indicator label
        self._grip_label = None
        self._grip_visible = False

        # Create styled sash
        self._setup_sash_styling()

        # Bind for theme changes and layout updates
        self.bind('<Map>', self._on_map)
        self.bind('<Configure>', self._on_configure)

    def _setup_sash_styling(self):
        """Setup cursor change on sash hover"""
        self.bind('<Motion>', self._on_motion)
        self.bind('<Leave>', self._on_leave)
        self.bind('<B1-Motion>', self._on_drag)

    def _create_grip_indicator(self):
        """Create visual grip handle on the sash"""
        if self._grip_label is not None:
            return

        # Create grip label with horizontal dots pattern
        self._grip_label = tk.Label(
            self,
            text="⋯ ⋯ ⋯",  # Three groups of horizontal ellipsis
            font=("Arial", 9),
            fg=ColorPalette.get('text_muted'),
            bg=ColorPalette.get('bg_primary'),
            cursor="sb_v_double_arrow",
            padx=4,
            pady=0
        )

        # Make grip label draggable (passes events to parent)
        self._grip_label.bind('<B1-Motion>', self._on_grip_drag)
        self._grip_label.bind('<Button-1>', self._on_grip_click)
        self._grip_label.bind('<Enter>', self._on_grip_enter)
        self._grip_label.bind('<Leave>', self._on_grip_leave)

    def _on_grip_drag(self, event):
        """Handle drag on grip label"""
        # Convert to parent coordinates and simulate sash drag
        x = event.x + self._grip_label.winfo_x()
        y = event.y + self._grip_label.winfo_y()
        try:
            self.sash_place(0, 0, y)
            self._update_grip_position()
        except:
            pass

    def _on_grip_click(self, event):
        """Handle click on grip label"""
        pass  # Just absorb the click

    def _on_grip_enter(self, event):
        """Highlight grip on hover"""
        if self._grip_label:
            self._grip_label.configure(fg=ColorPalette.get('text_secondary'))

    def _on_grip_leave(self, event):
        """Reset grip on leave"""
        if self._grip_label:
            self._grip_label.configure(fg=ColorPalette.get('text_muted'))

    def _update_grip_position(self, event=None):
        """Position grip indicator centered on sash"""
        if len(self.panes()) < 2:
            return

        # Create grip if not exists
        if self._grip_label is None:
            self._create_grip_indicator()

        try:
            sash_coord = self.sash_coord(0)
            if sash_coord:
                # Center grip horizontally and position on sash vertically
                grip_width = self._grip_label.winfo_reqwidth()
                x = (self.winfo_width() - grip_width) // 2
                y = sash_coord[1] - 6  # Adjust for label height

                # Only place if coordinates are valid
                if x > 0 and y > 0:
                    self._grip_label.place(x=x, y=y)
                    self._grip_visible = True
        except Exception:
            pass

    def _on_map(self, event=None):
        """Handle widget mapping - update colors and grip"""
        self._update_colors()
        # Delay grip creation to ensure panes are added
        self.after(100, self._update_grip_position)

    def _on_configure(self, event=None):
        """Handle resize - update grip position"""
        if self._grip_visible:
            self._update_grip_position()

    def _on_drag(self, event):
        """Update grip position during sash drag"""
        self._update_grip_position()

    def _on_motion(self, event):
        """Change cursor when near sash"""
        try:
            # Check if we're near any sash
            for i in range(len(self.panes()) - 1):
                sash_coord = self.sash_coord(i)
                if sash_coord:
                    sash_y = sash_coord[1]
                    if abs(event.y - sash_y) < 15:  # Increased hit area
                        self.configure(cursor="sb_v_double_arrow")
                        return
            self.configure(cursor="")
        except:
            pass

    def _on_leave(self, event):
        """Reset cursor on leave"""
        self.configure(cursor="")

    def _update_colors(self, event=None):
        """Update colors when theme changes"""
        self.configure(bg=ColorPalette.get('bg_primary'))
        if self._grip_label:
            self._grip_label.configure(
                fg=ColorPalette.get('text_muted'),
                bg=ColorPalette.get('bg_primary')
            )


class SettingsDialog(ctk.CTkToplevel):
    """Modal dialog for application settings"""

    def __init__(self, parent, current_domain, current_auth, on_save):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("400x420")
        self.resizable(False, False)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Store callback
        self.on_save = on_save
        self.custom_gif_path = get_custom_gif() or ""

        # Center on parent
        self.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        dialog_width = 400
        dialog_height = 420
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Build UI
        self._create_widgets(current_domain, current_auth)

    def _create_widgets(self, current_domain, current_auth):
        """Create dialog widgets"""
        # Main container with padding
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Default Domain
        ctk.CTkLabel(
            container,
            text="Default Domain",
            font=Typography.heading_sm(),
            text_color=ColorPalette.get('text_primary')
        ).pack(anchor="w", pady=(0, 8))

        self.domain_dropdown = ctk.CTkComboBox(
            container,
            width=310,
            height=36,
            values=DOMAIN_LIST,
            state="readonly",
            font=Typography.body_md(),
            dropdown_font=Typography.body_md(),
            corner_radius=8,
            border_width=1,
            border_color=ColorPalette.get('border'),
            button_color=ColorPalette.get('accent_primary'),
            button_hover_color=ColorPalette.get('accent_secondary')
        )
        self.domain_dropdown.set(current_domain)
        self.domain_dropdown.pack(pady=(0, 20))

        # Authentication Method
        ctk.CTkLabel(
            container,
            text="Authentication Method",
            font=Typography.heading_sm(),
            text_color=ColorPalette.get('text_primary')
        ).pack(anchor="w", pady=(0, 8))

        self.auth_dropdown = ctk.CTkComboBox(
            container,
            width=310,
            height=36,
            values=AUTH_METHODS,
            state="readonly",
            font=Typography.body_md(),
            dropdown_font=Typography.body_md(),
            corner_radius=8,
            border_width=1,
            border_color=ColorPalette.get('border'),
            button_color=ColorPalette.get('accent_primary'),
            button_hover_color=ColorPalette.get('accent_secondary')
        )
        self.auth_dropdown.set(current_auth)
        self.auth_dropdown.pack(pady=(0, 15))

        # Custom Animation
        ctk.CTkLabel(
            container,
            text="Custom Animation (GIF)",
            font=Typography.heading_sm(),
            text_color=ColorPalette.get('text_primary')
        ).pack(anchor="w", pady=(0, 6))

        gif_row = ctk.CTkFrame(container, fg_color="transparent")
        gif_row.pack(fill="x", pady=(0, 4))

        self.gif_label = ctk.CTkLabel(
            gif_row,
            text=os.path.basename(self.custom_gif_path) if self.custom_gif_path else "Default animation",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('text_secondary'),
            anchor="w",
            width=180
        )
        self.gif_label.pack(side="left", fill="x", expand=True)

        browse_btn = ctk.CTkButton(
            gif_row,
            text="Browse",
            width=70,
            height=30,
            font=Typography.body_sm(),
            fg_color=ColorPalette.get('accent_primary'),
            hover_color=ColorPalette.get('accent_secondary'),
            corner_radius=6,
            command=self._browse_gif
        )
        browse_btn.pack(side="left", padx=(6, 0))

        reset_btn = ctk.CTkButton(
            gif_row,
            text="Reset",
            width=60,
            height=30,
            font=Typography.body_sm(),
            fg_color=ColorPalette.get('border'),
            hover_color=ColorPalette.get('border_light'),
            text_color=ColorPalette.get('text_primary'),
            corner_radius=6,
            command=self._reset_gif
        )
        reset_btn.pack(side="left", padx=(6, 0))

        # Domain note
        note_label = ctk.CTkLabel(
            container,
            text="Note: Select only domains for your region.\nAccess depends on your certificate permissions.",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color=ColorPalette.get('text_muted'),
            justify="left"
        )
        note_label.pack(anchor="w", pady=(0, 15))

        # Save & Close button
        save_btn = ctk.CTkButton(
            container,
            text="Save & Close",
            width=360,
            height=40,
            font=Typography.heading_sm(),
            fg_color=ColorPalette.get('accent_primary'),
            hover_color=ColorPalette.get('accent_secondary'),
            corner_radius=8,
            command=self._save_and_close
        )
        save_btn.pack()

    def _browse_gif(self):
        """Open file dialog to select a custom GIF"""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self,
            title="Select Animation GIF",
            filetypes=[("GIF files", "*.gif"), ("All files", "*.*")]
        )
        if path:
            self.custom_gif_path = path
            self.gif_label.configure(text=os.path.basename(path))

    def _reset_gif(self):
        """Reset to default animation"""
        self.custom_gif_path = ""
        self.gif_label.configure(text="Default animation")

    def _save_and_close(self):
        """Save settings and close dialog"""
        domain = self.domain_dropdown.get()
        auth_method = self.auth_dropdown.get()
        # Save custom GIF setting
        set_custom_gif(self.custom_gif_path)
        self.on_save(domain, auth_method)
        self.destroy()


class AnimatedProgressBar(ctk.CTkProgressBar):
    """Progress bar with smooth animated transitions"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._target_value = 0
        self._current_value = 0
        self._animation_id = None
        self._animation_steps = 15
        self._animation_duration = 200  # ms

    def set_animated(self, value):
        """Set value with smooth animation"""
        self._target_value = max(0, min(1, value))
        if self._animation_id:
            self.after_cancel(self._animation_id)
        self._animate_step(0)

    def _ease_out_cubic(self, t):
        """Cubic ease-out for smooth deceleration"""
        return 1 - pow(1 - t, 3)

    def _animate_step(self, step):
        """Animate progress bar to target value"""
        if step >= self._animation_steps:
            self._current_value = self._target_value
            self.set(self._target_value)
            return

        t = step / self._animation_steps
        eased_t = self._ease_out_cubic(t)

        start_value = self._current_value
        diff = self._target_value - start_value
        new_value = start_value + (diff * eased_t)

        self.set(new_value)

        delay = self._animation_duration // self._animation_steps
        self._animation_id = self.after(delay, lambda: self._animate_step(step + 1))


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class GovCAApp(ctk.CTk):
    """Main application window with modern design"""

    def __init__(self):
        super().__init__()

        # Window setup
        self.title("PNPKI Approval Automation")
        self.geometry("950x800")
        self.minsize(800, 700)

        # State
        self.automation_thread = None
        self.cancel_event = threading.Event()
        self.log_buffer = LogBuffer()
        self.progress_tracker = ProgressTracker()
        self.selected_workflow = ctk.StringVar(value="1")
        self.is_running = False
        self.workflow_collapsed = False
        self.log_view_mode = "animation"  # "animation" | "split" | "logs"
        self.animation_running = False
        self.animation_frame_index = 0
        self.animation_after_id = None
        self.gif_frames = []  # GIF animation frames
        self.gif_target_size = (300, 188)

        # Bot persistence - keep browser session open between workflows
        self.bot = None
        self.session_valid = False

        # Stop escalation timers
        self._escalate_timer_id = None
        self._finalize_timer_id = None

        # Domain tracker state (for counterpart processing)
        self._domain_tracker_visible = False
        self._domain_tracker_domains = []       # ["NCR00Sign", "NCR00Auth"]
        self._domain_tracker_statuses = {}      # {"NCR00Sign": "processing", "NCR00Auth": "pending"}
        self._spinner_animation_id = None
        self._spinner_frame_index = 0

        # Track window size for responsive layout
        self._last_width = 950
        self._last_height = 800

        # Build UI
        self._create_widgets()
        self._check_prerequisites()

        # Defer GIF loading until after mainloop starts (ImageTk needs root window)
        self.after(100, self._load_gif_frames)

        # Start polling for log updates
        self._poll_updates()

        # Bind resize event
        self.bind('<Configure>', self._on_window_resize)

    def _get_log_colors(self):
        """Get log colors based on current appearance mode"""
        if ctk.get_appearance_mode() == "Light":
            return {
                "INFO": "#374151",
                "SUCCESS": "#059669",
                "WARNING": "#d97706",
                "ERROR": "#dc2626"
            }
        else:
            return {
                "INFO": "#e5e7eb",
                "SUCCESS": "#34d399",
                "WARNING": "#fbbf24",
                "ERROR": "#f87171"
            }

    def _update_log_colors(self):
        """Update log text colors based on current theme"""
        colors = self._get_log_colors()
        for level, color in colors.items():
            self.log_text._textbox.tag_configure(level, foreground=color)

    def _on_window_resize(self, event):
        """Handle window resize for responsive layout"""
        if event.widget != self:
            return

        new_width = event.width
        new_height = event.height

        # Debounce - only act on significant changes
        if abs(new_width - self._last_width) < 20 and abs(new_height - self._last_height) < 20:
            return

        self._last_width = new_width
        self._last_height = new_height

        # Adjust GIF size based on height
        if new_height < 700:
            new_size = (240, 150)
        else:
            new_size = (300, 188)

        if new_size != self.gif_target_size:
            self.gif_target_size = new_size
            # Reload GIF with new size
            self.after(100, self._load_gif_frames)

    def _create_widgets(self):
        """Create all UI widgets with modern design"""
        # Configure window background
        self.configure(fg_color=ColorPalette.get('bg_primary'))

        # Main container with padding
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=16, pady=8)

        # Title Section
        self._create_title_section(self.main_frame)

        # Workflow Selection Section
        self._create_workflow_section(self.main_frame)

        # Bottom frame FIRST (so it reserves space at bottom for buttons)
        bottom_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        bottom_frame.pack(fill="x", side="bottom", pady=(6, 0))

        # Control Buttons and Progress (inside bottom_frame)
        self._create_control_buttons(bottom_frame)
        self._create_progress_section(bottom_frame)

        # THEN the resizable paned window (fills remaining space)
        self.main_paned = ResizablePanedWindow(self.main_frame, orient=tk.VERTICAL)
        self.main_paned.pack(fill="both", expand=True, pady=(0, 6))

        # Configuration pane (upper)
        self.config_pane = CardFrame(self.main_paned)
        self._create_config_section(self.config_pane)
        self.main_paned.add(self.config_pane, minsize=80, height=180)

        # Log/Animation pane (lower)
        self.log_pane = CardFrame(self.main_paned)
        self._create_log_section(self.log_pane)
        self.main_paned.add(self.log_pane, minsize=120, height=250)

        # Status Bar
        self._create_status_bar()

    def _create_title_section(self, parent):
        """Create title section with domain indicator and settings button"""
        title_frame = ctk.CTkFrame(parent, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 6))

        # LEFT: Domain indicator
        left_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        left_frame.pack(side="left", anchor="w")

        ctk.CTkLabel(
            left_frame,
            text="Domain:",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_muted')
        ).pack(side="left")

        self.domain_indicator = ctk.CTkLabel(
            left_frame,
            text=get_default_domain(),
            font=Typography.heading_sm(),
            text_color=ColorPalette.get('accent_primary')
        )
        self.domain_indicator.pack(side="left", padx=(4, 0))

        # CENTER: Title and subtitle
        center_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        center_frame.pack(side="left", expand=True)

        # Logo + Title together
        logo_title_frame = ctk.CTkFrame(center_frame, fg_color="transparent")
        logo_title_frame.pack()

        # Load PNPKI logo
        try:
            logo_path = get_logo_path()
            logo_img = Image.open(logo_path)
            # Scale to 40px height, maintain aspect ratio
            aspect = logo_img.width / logo_img.height
            logo_size = (int(40 * aspect), 40)
            self.logo_image = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=logo_size)
            logo_label = ctk.CTkLabel(logo_title_frame, image=self.logo_image, text="")
            logo_label.pack(side="left", padx=(0, 8))
        except Exception:
            pass  # No logo if file missing

        # Main title
        title_label = ctk.CTkLabel(
            logo_title_frame,
            text="PNPKI Approval Automation",
            font=Typography.heading_xl(),
            text_color=ColorPalette.get('text_primary')
        )
        title_label.pack(side="left")

        # Subtitle
        subtitle_label = ctk.CTkLabel(
            center_frame,
            text="Automated certificate approval workflow",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_muted')
        )
        subtitle_label.pack(pady=(2, 0))

        # RIGHT: Settings button
        right_frame = ctk.CTkFrame(title_frame, fg_color="transparent")
        right_frame.pack(side="right", anchor="e")

        self.settings_btn = ctk.CTkButton(
            right_frame,
            text="\u2699",
            width=32,
            height=28,
            font=ctk.CTkFont(size=16),
            fg_color="transparent",
            hover_color=ColorPalette.get('border'),
            border_width=1,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=8,
            command=self._open_settings
        )
        self.settings_btn.pack()
        ToolTip(self.settings_btn, "Settings")

    def _create_workflow_section(self, parent):
        """Create workflow selection section with card-style buttons"""
        section_frame = CardFrame(parent)
        section_frame.pack(fill="x", pady=(0, 4))

        # Clickable header row with chevron
        header_row = ctk.CTkFrame(section_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=15, pady=(3, 1))

        self.workflow_chevron = ctk.CTkLabel(
            header_row,
            text="▼",
            font=Typography.section_header(),
            text_color=ColorPalette.get('text_muted'),
            width=16
        )
        self.workflow_chevron.pack(side="left")

        header_label = ctk.CTkLabel(
            header_row,
            text="SELECT WORKFLOW",
            font=Typography.section_header(),
            text_color=ColorPalette.get('text_muted')
        )
        header_label.pack(side="left", padx=(4, 0))

        # Make header row clickable
        for widget in [header_row, self.workflow_chevron, header_label]:
            widget.bind('<Button-1>', lambda e: self._toggle_workflow_section())
            widget.configure(cursor="hand2")

        # Collapsed summary label (hidden by default)
        self.workflow_summary_label = ctk.CTkLabel(
            section_frame,
            text="",
            font=Typography.heading_sm(),
            text_color=ColorPalette.get('text_primary'),
            anchor="w"
        )
        # Not packed yet — shown only when collapsed

        # Workflow buttons container
        self.workflow_buttons_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        self.workflow_buttons_frame.pack(fill="x", padx=15, pady=(0, 3))
        self.workflow_buttons_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="workflow")
        buttons_frame = self.workflow_buttons_frame

        workflows = [
            ("1", "Add User", "Batch Approve", "Batch approve pending users"),
            ("2", "Revoke Cert", "One-by-One", "Approve revoke requests"),
            ("3", "Assign Group", "User Groups", "Assign users to groups"),
        ]

        self.workflow_buttons = {}
        self.workflow_frames = {}

        for i, (value, title, subtitle, tooltip) in enumerate(workflows):
            # Card-style button container
            btn_container = ctk.CTkFrame(
                buttons_frame,
                fg_color=ColorPalette.get('accent_primary') if value == "1" else ColorPalette.get('bg_secondary'),
                corner_radius=10,
                border_width=2,
                border_color=ColorPalette.get('accent_primary') if value == "1" else ColorPalette.get('border')
            )
            btn_container.grid(row=0, column=i, padx=4, pady=2, sticky="nsew")

            # Inner content
            inner = ctk.CTkFrame(btn_container, fg_color="transparent")
            inner.pack(expand=True, fill="both", padx=6, pady=3)

            # Title
            title_lbl = ctk.CTkLabel(
                inner,
                text=title,
                font=Typography.heading_sm(),
                text_color="#ffffff" if value == "1" else ColorPalette.get('text_primary')
            )
            title_lbl.pack()

            # Subtitle
            subtitle_lbl = ctk.CTkLabel(
                inner,
                text=subtitle,
                font=Typography.body_sm(),
                text_color="#e5e7eb" if value == "1" else ColorPalette.get('text_secondary')
            )
            subtitle_lbl.pack(pady=(0, 0))

            # Make entire frame clickable
            for widget in [btn_container, inner, title_lbl, subtitle_lbl]:
                widget.bind('<Button-1>', lambda e, v=value: self._select_workflow(v))
                widget.bind('<Enter>', lambda e, c=btn_container, v=value: self._on_workflow_hover(c, v, True))
                widget.bind('<Leave>', lambda e, c=btn_container, v=value: self._on_workflow_hover(c, v, False))

            self.workflow_frames[value] = {
                'container': btn_container,
                'inner': inner,
                'title': title_lbl,
                'subtitle': subtitle_lbl
            }

    def _on_workflow_hover(self, container, value, entering):
        """Handle hover effect on workflow buttons"""
        if self.selected_workflow.get() == value:
            return  # Don't change selected button

        if entering:
            container.configure(border_color=ColorPalette.get('accent_secondary'))
        else:
            container.configure(border_color=ColorPalette.get('border'))

    def _toggle_workflow_section(self):
        """Toggle workflow section between expanded and collapsed states"""
        self.workflow_collapsed = not self.workflow_collapsed
        if self.workflow_collapsed:
            self.workflow_buttons_frame.pack_forget()
            self._update_workflow_summary()
            self.workflow_summary_label.pack(fill="x", padx=15, pady=(0, 6))
            self.workflow_chevron.configure(text="▶")
        else:
            self.workflow_summary_label.pack_forget()
            self.workflow_buttons_frame.pack(fill="x", padx=15, pady=(0, 3))
            self.workflow_chevron.configure(text="▼")

    def _update_workflow_summary(self):
        """Update the collapsed workflow summary text"""
        workflow_labels = {
            "1": ("Add User", "Batch Approve"),
            "2": ("Revoke Cert", "One-by-One"),
            "3": ("Assign Group", "User Groups"),
        }
        value = self.selected_workflow.get()
        title, subtitle = workflow_labels.get(value, ("Unknown", ""))
        self.workflow_summary_label.configure(text=f"{title}  ·  {subtitle}")

    def _select_workflow(self, value):
        """Handle workflow selection"""
        old_value = self.selected_workflow.get()
        self.selected_workflow.set(value)

        # Update all button styles
        for v, widgets in self.workflow_frames.items():
            if v == value:
                # Selected state
                widgets['container'].configure(
                    fg_color=ColorPalette.get('accent_primary'),
                    border_color=ColorPalette.get('accent_primary')
                )
                widgets['title'].configure(text_color="#ffffff")
                widgets['subtitle'].configure(text_color="#e5e7eb")
            else:
                # Unselected state
                widgets['container'].configure(
                    fg_color=ColorPalette.get('bg_secondary'),
                    border_color=ColorPalette.get('border')
                )
                widgets['title'].configure(text_color=ColorPalette.get('text_primary'))
                widgets['subtitle'].configure(text_color=ColorPalette.get('text_secondary'))

        # Update config visibility
        self._update_config_visibility()

        # Refresh summary if collapsed
        if self.workflow_collapsed:
            self._update_workflow_summary()

    def _create_config_section(self, parent):
        """Create configuration section with OPTIONS only (settings moved to dialog)"""
        # Config container (scrollable)
        config_container = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        config_container.pack(fill="both", expand=True, padx=10, pady=(4, 4))

        # ============ OPTIONS SECTION ============
        options_frame = ctk.CTkFrame(config_container, fg_color=ColorPalette.get('bg_secondary'), corner_radius=8)
        options_frame.pack(fill="x", pady=(0, 6))

        # Options header
        ctk.CTkLabel(
            options_frame,
            text="OPTIONS",
            font=Typography.section_header(),
            text_color=ColorPalette.get('text_muted')
        ).pack(anchor="w", padx=12, pady=(6, 4))

        # Options content
        options_content = ctk.CTkFrame(options_frame, fg_color="transparent")
        options_content.pack(fill="x", padx=12, pady=(0, 6))

        # Row 1: Counterpart checkbox + All Domains toggle
        options_row1 = ctk.CTkFrame(options_content, fg_color="transparent")
        options_row1.pack(fill="x", pady=4)

        # Counterpart checkbox
        self.counterpart_var = ctk.BooleanVar(value=True)
        self.counterpart_check = ctk.CTkCheckBox(
            options_row1,
            text="Process counterpart domain (Sign/Auth)",
            variable=self.counterpart_var,
            font=Typography.body_md(),
            checkbox_width=20,
            checkbox_height=20,
            corner_radius=4,
            border_width=2,
            fg_color=ColorPalette.get('accent_primary'),
            hover_color=ColorPalette.get('accent_secondary'),
            text_color=ColorPalette.get('text_primary')
        )
        self.counterpart_check.pack(side="left")

        # All Domains toggle (for workflow 3 only) - in same row
        self.all_domains_frame = ctk.CTkFrame(options_row1, fg_color="transparent")

        self.all_domains_var = ctk.BooleanVar(value=False)
        self.all_domains_switch = ctk.CTkSwitch(
            self.all_domains_frame,
            text="Process ALL domains automatically",
            variable=self.all_domains_var,
            font=Typography.body_md(),
            progress_color=ColorPalette.get('accent_primary'),
            button_color=ColorPalette.get('text_primary'),
            button_hover_color=ColorPalette.get('text_secondary'),
            command=self._toggle_all_domains
        )
        self.all_domains_switch.pack(side="left")
        # Initially hide all domains toggle
        self.all_domains_frame.pack_forget()

        # ============ WORKFLOW OPTIONS SECTION ============
        self.workflow_options_frame = ctk.CTkFrame(config_container, fg_color=ColorPalette.get('bg_secondary'), corner_radius=8)
        self.workflow_options_frame.pack(fill="x", pady=(0, 0))

        # Workflow Options header
        ctk.CTkLabel(
            self.workflow_options_frame,
            text="WORKFLOW OPTIONS",
            font=Typography.section_header(),
            text_color=ColorPalette.get('text_muted')
        ).pack(anchor="w", padx=12, pady=(6, 4))

        # Workflow options content
        workflow_content = ctk.CTkFrame(self.workflow_options_frame, fg_color="transparent")
        workflow_content.pack(fill="x", padx=12, pady=(0, 6))

        # Comment row
        self.comment_row = ctk.CTkFrame(workflow_content, fg_color="transparent")
        self.comment_row.pack(fill="x", pady=2)

        self.comment_label = ctk.CTkLabel(
            self.comment_row,
            text="Comment:",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_secondary'),
            width=70,
            anchor="w"
        )
        self.comment_label.pack(side="left")

        self.comment_entry = ctk.CTkEntry(
            self.comment_row,
            width=350,
            height=32,
            font=Typography.body_md(),
            corner_radius=8,
            border_width=1,
            border_color=ColorPalette.get('border'),
            placeholder_text="Approved via automation"
        )
        self.comment_entry.pack(side="left")
        self.comment_entry.insert(0, "Approved via automation")

        # Row 3: Mode selection (for workflow 1 only)
        self.mode_frame = ctk.CTkFrame(workflow_content, fg_color="transparent")
        self.mode_frame.pack(fill="x", pady=4)

        ctk.CTkLabel(
            self.mode_frame,
            text="Mode:",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_secondary'),
            width=70,
            anchor="w"
        ).pack(side="left")

        self.mode_var = ctk.StringVar(value="specific")
        mode_all = ctk.CTkRadioButton(
            self.mode_frame,
            text="All pending users",
            variable=self.mode_var,
            value="all",
            font=Typography.body_md(),
            fg_color=ColorPalette.get('accent_primary'),
            hover_color=ColorPalette.get('accent_secondary'),
            text_color=ColorPalette.get('text_primary'),
            command=self._update_usernames_visibility
        )
        mode_all.pack(side="left", padx=(0, 20))

        mode_specific = ctk.CTkRadioButton(
            self.mode_frame,
            text="Specific users only",
            variable=self.mode_var,
            value="specific",
            font=Typography.body_md(),
            fg_color=ColorPalette.get('accent_primary'),
            hover_color=ColorPalette.get('accent_secondary'),
            text_color=ColorPalette.get('text_primary'),
            command=self._update_usernames_visibility
        )
        mode_specific.pack(side="left")

        # Row 4: Usernames input (for specific mode)
        self.usernames_frame = ctk.CTkFrame(workflow_content, fg_color="transparent")
        self.usernames_frame.pack(fill="x", pady=4)

        ctk.CTkLabel(
            self.usernames_frame,
            text="Usernames:",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_secondary'),
            width=70,
            anchor="nw"
        ).pack(side="left", anchor="n")

        self.usernames_text = ctk.CTkTextbox(
            self.usernames_frame,
            width=350,
            height=60,
            font=Typography.mono(12),
            corner_radius=8,
            border_width=1,
            border_color=ColorPalette.get('border'),
            fg_color=ColorPalette.get('bg_input')
        )
        self.usernames_text.pack(side="left")

        # Bind to update count on text change
        self.usernames_text.bind('<KeyRelease>', self._update_username_count)
        self.usernames_text.bind('<<Paste>>', lambda e: self.after(10, self._update_username_count))

        # Clear button for usernames
        self.clear_usernames_btn = ctk.CTkButton(
            self.usernames_frame,
            text="\u2715",
            width=28,
            height=28,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color=ColorPalette.get('border'),
            border_width=1,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=8,
            command=self._clear_usernames
        )
        self.clear_usernames_btn.pack(side="left", padx=(10, 0), anchor="n")
        ToolTip(self.clear_usernames_btn, "Clear usernames")

        # Username hint
        ctk.CTkLabel(
            self.usernames_frame,
            text="(one per line,\nwithout suffix)",
            font=ctk.CTkFont(size=10),
            text_color=ColorPalette.get('text_muted'),
            justify="left"
        ).pack(side="left", padx=(10, 0), anchor="n")

        # Username count indicator
        self.username_count_label = ctk.CTkLabel(
            self.usernames_frame,
            text="0 users entered",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('text_muted')
        )
        self.username_count_label.pack(side="left", padx=(10, 0), anchor="n")

        # Initially hide usernames
        self.usernames_frame.pack_forget()

        # Batch Reject Option Frame (only visible when "Specific users only" is selected)
        self.batch_reject_frame = ctk.CTkFrame(workflow_content, fg_color="transparent")

        self.batch_reject_var = ctk.BooleanVar(value=False)
        self.batch_reject_checkbox = ctk.CTkCheckBox(
            self.batch_reject_frame,
            text="Batch Reject",
            variable=self.batch_reject_var,
            font=Typography.body_md(),
            checkbox_width=20,
            checkbox_height=20,
            corner_radius=4,
            border_width=2,
            fg_color=ColorPalette.get('accent_error'),
            hover_color="#dc2626",
            text_color=ColorPalette.get('text_primary'),
            command=self._on_batch_reject_toggle
        )
        self.batch_reject_checkbox.pack(side="left", padx=(70, 0))

        # Warning label (shows when batch reject is enabled)
        self.batch_reject_warning = ctk.CTkLabel(
            self.batch_reject_frame,
            text="WARNING: This will REJECT all specified users!",
            font=Typography.body_sm(),
            text_color="#FF6B6B"
        )
        # Initially hidden - will be shown when checkbox is toggled

        # Initially hide batch reject frame
        self.batch_reject_frame.pack_forget()

        # Update visibility based on initial workflow
        self._update_config_visibility()

    def _update_config_visibility(self):
        """Update config visibility based on selected workflow"""
        workflow = self.selected_workflow.get()

        # Hide all_domains toggle by default
        self.all_domains_frame.pack_forget()

        # Show/hide elements based on workflow
        if workflow == "3":
            # Assign group - show all_domains toggle, hide workflow options
            self.all_domains_frame.pack(side="left", padx=(20, 0))
            self.comment_row.pack_forget()
            self.mode_frame.pack_forget()
            self.usernames_frame.pack_forget()
            # Hide batch reject (only for Add User workflow)
            self.batch_reject_frame.pack_forget()
            self.batch_reject_var.set(False)
            self.batch_reject_warning.pack_forget()
            self._reset_start_button()
            # Hide workflow options section for assign group
            self.workflow_options_frame.pack_forget()
            # Update counterpart based on all_domains toggle
            self._toggle_all_domains()
        elif workflow == "2":
            # Revoke cert - show counterpart and comment
            self.counterpart_check.pack(side="left")
            # Show workflow options section with comment only
            self.workflow_options_frame.pack(fill="x", pady=(0, 0))
            self.comment_row.pack(fill="x", pady=2)
            self.comment_entry.configure(state="normal")
            self.mode_frame.pack_forget()
            self.usernames_frame.pack_forget()
            # Hide batch reject (only for Add User workflow)
            self.batch_reject_frame.pack_forget()
            self.batch_reject_var.set(False)
            self.batch_reject_warning.pack_forget()
            self._reset_start_button()
        else:
            # Add user - show all workflow options
            self.counterpart_check.pack(side="left")
            # Show workflow options section
            self.workflow_options_frame.pack(fill="x", pady=(0, 0))
            self.comment_row.pack(fill="x", pady=2)
            self.comment_entry.configure(state="normal")
            self.mode_frame.pack(fill="x", pady=4)
            self._update_usernames_visibility()

    def _toggle_all_domains(self):
        """Toggle counterpart option based on All Domains switch"""
        if self.all_domains_var.get():
            # All domains mode - hide counterpart (not applicable)
            self.counterpart_check.pack_forget()
        else:
            # Single domain mode - show counterpart
            self.counterpart_check.pack(side="left")

    def _on_batch_reject_toggle(self):
        """Show/hide warning when batch reject is toggled and change START button color"""
        if self.batch_reject_var.get():
            self.batch_reject_warning.pack(side="left", padx=(10, 0))
            # Change START button to warning color (orange)
            self.start_button.configure(
                fg_color=ColorPalette.get('accent_warning'),
                hover_color="#d97706" if ctk.get_appearance_mode() == "Light" else "#fbbf24",
                text="START (REJECT)"
            )
        else:
            self.batch_reject_warning.pack_forget()
            # Restore START button to normal color (green)
            self._reset_start_button()

    def _open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(
            self,
            current_domain=get_default_domain(),
            current_auth=get_auth_method(),
            on_save=self._on_settings_saved
        )
        dialog.focus()

    def _on_settings_saved(self, domain, auth_method):
        """Handle settings save from dialog"""
        set_default_domain(domain)
        set_auth_method(auth_method)
        self._update_domain_indicator()
        # Reload GIF in case custom animation changed
        self._load_gif_frames()

    def _update_domain_indicator(self):
        """Update domain indicator label"""
        self.domain_indicator.configure(text=get_default_domain())

    def _reset_start_button(self):
        """Reset START button to normal green state"""
        self.start_button.configure(
            fg_color=ColorPalette.get('accent_success'),
            hover_color="#059669" if ctk.get_appearance_mode() == "Light" else "#34d399",
            text="START"
        )

    def _update_usernames_visibility(self):
        """Show/hide usernames input and batch reject option based on mode"""
        if self.mode_var.get() == "specific" and self.selected_workflow.get() == "1":
            self.usernames_frame.pack(fill="x", pady=4)
            self.batch_reject_frame.pack(fill="x", pady=4)
        else:
            self.usernames_frame.pack_forget()
            self.batch_reject_frame.pack_forget()
            self.batch_reject_var.set(False)
            self.batch_reject_warning.pack_forget()
            # Reset START button to normal color (green)
            self._reset_start_button()

    def _create_log_section(self, parent):
        """Create log output section with animation"""
        # Header with toggle button
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(8, 6))

        # Header left
        header_left = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_left.pack(side="left")

        ctk.CTkLabel(
            header_left,
            text="LOG OUTPUT",
            font=Typography.section_header(),
            text_color=ColorPalette.get('text_muted')
        ).pack(side="left")

        # Live indicator dot
        self.live_indicator = ctk.CTkLabel(
            header_left,
            text="",
            font=ctk.CTkFont(size=14)
        )
        self.live_indicator.pack(side="left", padx=(8, 0))

        # Header right - buttons
        header_right = ctk.CTkFrame(header_frame, fg_color="transparent")
        header_right.pack(side="right")

        # Toggle button
        self.toggle_logs_btn = ctk.CTkButton(
            header_right,
            text="\u2261",
            width=28,
            height=28,
            font=ctk.CTkFont(size=16),
            fg_color=ColorPalette.get('bg_secondary'),
            hover_color=ColorPalette.get('border'),
            border_width=1,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=8,
            command=self._toggle_logs
        )
        self.toggle_logs_btn.pack(side="right", padx=(8, 0))
        self.toggle_logs_tooltip = ToolTip(self.toggle_logs_btn, "Show Split View")

        # Copy button
        self.copy_logs_btn = ctk.CTkButton(
            header_right,
            text="\u2398",
            width=28,
            height=28,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color=ColorPalette.get('border'),
            border_width=1,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=8,
            command=self._copy_logs_to_clipboard
        )
        self.copy_logs_btn.pack(side="right", padx=(8, 0))
        self.copy_logs_tooltip = ToolTip(self.copy_logs_btn, "Copy to clipboard")

        # Auto-scroll switch
        self.autoscroll_var = ctk.BooleanVar(value=True)
        self.autoscroll_switch = ctk.CTkSwitch(
            header_right,
            text="Auto-scroll",
            variable=self.autoscroll_var,
            font=Typography.body_sm(),
            progress_color=ColorPalette.get('accent_primary'),
            button_color=ColorPalette.get('text_primary'),
            button_hover_color=ColorPalette.get('text_secondary')
        )
        self.autoscroll_switch.pack(side="right")

        # Content area
        self.log_content_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.log_content_frame.pack(fill="both", expand=True, padx=15, pady=(0, 12))

        # Log textbox
        self.log_text = ctk.CTkTextbox(
            self.log_content_frame,
            font=Typography.mono(12),
            wrap="word",
            corner_radius=8,
            border_width=1,
            border_color=ColorPalette.get('border'),
            fg_color=ColorPalette.get('bg_input')
        )

        # Configure text tags for colors based on theme
        self._update_log_colors()

        # Animation frame (shown by default)
        self.animation_frame = ctk.CTkFrame(self.log_content_frame, fg_color="transparent")
        self.animation_frame.pack(fill="both", expand=True)

        # Initially hide logs, show animation
        self.log_text.pack_forget()
        self.autoscroll_switch.pack_forget()
        self.copy_logs_btn.pack_forget()

        # GIF label
        self.gif_label = tk.Label(
            self.animation_frame,
            bg=ColorPalette.get('bg_card'),
            bd=0,
            highlightthickness=0
        )
        self.gif_label.pack(expand=True, pady=(30, 15))

        # Fun messages that cycle
        self.fun_messages = [
            "Approving users like a boss...",
            "Making GovCA magic happen...",
            "Almost there, hang tight!",
            "Processing at robot speed...",
            "Beep boop, working hard!",
            "Certificate automation in progress...",
        ]

        self.message_label = ctk.CTkLabel(
            self.animation_frame,
            text="Ready to start",
            font=Typography.body_lg(),
            text_color=ColorPalette.get('text_muted')
        )
        self.message_label.pack(pady=(15, 30))

    def _toggle_logs(self):
        """Cycle log view: animation -> split -> logs -> animation"""
        cycle = {"animation": "split", "split": "logs", "logs": "animation"}
        self._set_log_view(cycle[self.log_view_mode])

    def _set_log_view(self, mode):
        """Set the log view layout to the given mode."""
        self.log_view_mode = mode

        # Reset: forget both widgets and restore propagation
        self.animation_frame.pack_forget()
        self.log_text.pack_forget()
        self.animation_frame.pack_propagate(True)

        if mode == "animation":
            # Animation fills all space, hide log controls
            self.autoscroll_switch.pack_forget()
            self.copy_logs_btn.pack_forget()
            self.animation_frame.pack(fill="both", expand=True)
            if self.is_running:
                self._start_animation()
            self.toggle_logs_tooltip.update_text("Show Split View")

        elif mode == "split":
            # GIF on left (fixed 320px), logs on right
            self.autoscroll_switch.pack(side="right")
            self.copy_logs_btn.pack(side="right", padx=(8, 0))
            self.animation_frame.configure(width=320)
            self.animation_frame.pack_propagate(False)
            self.animation_frame.pack(side="left", fill="y")
            self.log_text.pack(side="left", fill="both", expand=True)
            if self.is_running:
                self._start_animation()
            self.toggle_logs_tooltip.update_text("Show Logs Only")

        elif mode == "logs":
            # Logs fill all space, hide animation
            self._stop_animation()
            self.autoscroll_switch.pack(side="right")
            self.copy_logs_btn.pack(side="right", padx=(8, 0))
            self.log_text.pack(fill="both", expand=True)
            self.toggle_logs_tooltip.update_text("Show Animation")

    def _load_gif_frames(self):
        """Load all frames from the GIF with robust error handling"""
        try:
            gif_path = get_gif_path()

            # Verify file exists
            if not os.path.exists(gif_path):
                self._log_internal(f"GIF not found at: {gif_path}")
                self._show_gif_placeholder("Animation not available")
                return

            gif = Image.open(gif_path)
            self.gif_frames = []

            # Get GIF duration (default to 50ms if not available)
            try:
                self.gif_duration = gif.info.get('duration', 50)
            except Exception:
                self.gif_duration = 50

            # Extract all frames
            try:
                frame_count = 0
                while True:
                    frame = gif.copy()
                    # Convert to RGBA if needed for transparency support
                    if frame.mode != 'RGBA':
                        frame = frame.convert('RGBA')
                    # Resize to fit nicely in the UI
                    frame = frame.resize(self.gif_target_size, Image.Resampling.LANCZOS)
                    self.gif_frames.append(ImageTk.PhotoImage(frame))
                    frame_count += 1
                    gif.seek(gif.tell() + 1)
            except EOFError:
                pass

            if self.gif_frames:
                self._log_internal(f"Loaded {len(self.gif_frames)} GIF frames")
                # Show first frame immediately after loading
                self.gif_label.configure(image=self.gif_frames[0])
                # Update label background to match theme
                self.gif_label.configure(bg=ColorPalette.get('bg_card'))
            else:
                self._show_gif_placeholder("No frames loaded")

        except FileNotFoundError as e:
            self._log_internal(f"GIF file not found: {e}")
            self._show_gif_placeholder("Animation file missing")
        except Exception as e:
            self._log_internal(f"Failed to load GIF: {type(e).__name__}: {e}")
            self._show_gif_placeholder("Animation unavailable")
            self.gif_frames = []

    def _show_gif_placeholder(self, message):
        """Show a placeholder when GIF cannot be loaded"""
        self.gif_frames = []
        # Hide the gif_label and show message instead
        self.gif_label.pack_forget()

        if hasattr(self, 'gif_placeholder_label'):
            self.gif_placeholder_label.configure(text=message)
            self.gif_placeholder_label.pack(expand=True, pady=30)
        else:
            self.gif_placeholder_label = ctk.CTkLabel(
                self.animation_frame,
                text=message,
                font=Typography.body_lg(),
                text_color=ColorPalette.get('text_muted')
            )
            self.gif_placeholder_label.pack(expand=True, pady=30)

    def _log_internal(self, message):
        """Internal logging for debugging (only prints to console in dev)"""
        if not getattr(sys, 'frozen', False):
            print(f"[DEBUG] {message}")

    def _start_animation(self):
        """Start the GIF animation"""
        if self.animation_running:
            return
        if not self.gif_frames:
            return
        self.animation_running = True
        self.animation_frame_index = 0

        # Make sure GIF label is visible
        if hasattr(self, 'gif_placeholder_label'):
            self.gif_placeholder_label.pack_forget()
        self.gif_label.pack(expand=True, pady=(30, 15))

        # Update live indicator
        self.live_indicator.configure(text="", text_color=ColorPalette.get('accent_success'))

        # Reset message label
        self.message_label.configure(
            text="",
            text_color=ColorPalette.get('text_muted'),
            font=Typography.body_lg()
        )
        self._animate_gif()

    def _stop_animation(self):
        """Stop the GIF animation"""
        self.animation_running = False
        if self.animation_after_id:
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None

        # Hide live indicator
        self.live_indicator.configure(text="")

    def _animate_gif(self):
        """Cycle through GIF animation frames"""
        if not self.animation_running or not self.gif_frames:
            return

        # Update GIF frame
        frame = self.gif_frames[self.animation_frame_index]
        self.gif_label.configure(image=frame)

        # Update fun message every 10 frames
        if self.animation_frame_index % 10 == 0:
            import random
            self.message_label.configure(text=random.choice(self.fun_messages))

        # Next frame
        self.animation_frame_index = (self.animation_frame_index + 1) % len(self.gif_frames)

        # Schedule next animation frame (use GIF duration or default 50ms)
        delay = getattr(self, 'gif_duration', 50)
        self.animation_after_id = self.after(delay, self._animate_gif)

    def _show_result(self, success=True):
        """Stop GIF and show completion text"""
        self._stop_animation()
        # Hide GIF label
        self.gif_label.pack_forget()
        if hasattr(self, 'gif_placeholder_label'):
            self.gif_placeholder_label.pack_forget()

        # Show result message
        if success:
            self.message_label.configure(
                text="Mission Complete!",
                text_color=ColorPalette.get('accent_success'),
                font=Typography.heading_md()
            )
        else:
            self.message_label.configure(
                text="Error occurred - check logs",
                text_color=ColorPalette.get('accent_error'),
                font=Typography.heading_md()
            )

    # =========================================================================
    # DOMAIN TRACKER — visual status for counterpart processing
    # =========================================================================

    def _compute_counterpart_domain(self, domain):
        """Sign↔Auth string swap (replicates bot logic)"""
        if "Sign" in domain:
            return domain.replace("Sign", "Auth")
        elif "Auth" in domain:
            return domain.replace("Auth", "Sign")
        return None

    def _setup_domain_tracker(self, primary_domain):
        """Initialize tracker: set domain names, show frame, hide phase_label"""
        counterpart = self._compute_counterpart_domain(primary_domain)
        if not counterpart:
            return

        self._domain_tracker_domains = [primary_domain, counterpart]
        self._domain_tracker_statuses = {
            primary_domain: "processing",
            counterpart: "pending",
        }
        self._domain_tracker_visible = True

        # Set domain labels
        self.domain1_name.configure(text=primary_domain)
        self.domain2_name.configure(text=counterpart)

        # Set initial icons
        self._update_domain_icon(self.domain1_icon, "processing")
        self._update_domain_icon(self.domain2_icon, "pending")

        # Show tracker, hide plain phase_label
        self.phase_label.pack_forget()
        self.domain_tracker_frame.pack(anchor="w", pady=(0, 4))

        # Start spinner animation
        self._start_domain_spinner()

    def _update_domain_icon(self, icon_label, status):
        """Set icon text + color based on status"""
        if status == "pending":
            icon_label.configure(
                text="○",
                text_color=ColorPalette.get('text_muted')
            )
        elif status == "processing":
            # Spinner will be animated via _tick_domain_spinner
            icon_label.configure(
                text="◐",
                text_color=ColorPalette.get('accent_primary')
            )
        elif status == "completed":
            icon_label.configure(
                text="✓",
                text_color=ColorPalette.get('accent_success')
            )

    def _start_domain_spinner(self):
        """Start after() loop cycling spinner characters"""
        self._spinner_frame_index = 0
        self._tick_domain_spinner()

    def _tick_domain_spinner(self):
        """Advance spinner frame on the currently-processing icon"""
        spinner_chars = ["◐", "◓", "◑", "◒"]
        self._spinner_frame_index = (self._spinner_frame_index + 1) % len(spinner_chars)
        char = spinner_chars[self._spinner_frame_index]

        # Update the icon of whichever domain is currently processing
        for i, domain in enumerate(self._domain_tracker_domains):
            if self._domain_tracker_statuses.get(domain) == "processing":
                icon_label = self.domain1_icon if i == 0 else self.domain2_icon
                icon_label.configure(text=char)

        self._spinner_animation_id = self.after(150, self._tick_domain_spinner)

    def _stop_domain_spinner(self):
        """Cancel the after() timer"""
        if self._spinner_animation_id is not None:
            self.after_cancel(self._spinner_animation_id)
            self._spinner_animation_id = None

    def _update_domain_tracker(self, phase, total_phases, phase_label):
        """Main logic: compare phase_label to domain names, transition statuses"""
        if not self._domain_tracker_domains:
            return

        domain1, domain2 = self._domain_tracker_domains

        # Determine which domain is now active based on phase_label
        if phase_label == domain2 and self._domain_tracker_statuses[domain2] != "processing":
            # Switching to domain2 — mark domain1 as completed
            self._domain_tracker_statuses[domain1] = "completed"
            self._domain_tracker_statuses[domain2] = "processing"
            self._update_domain_icon(self.domain1_icon, "completed")
            self._update_domain_icon(self.domain2_icon, "processing")

        elif phase_label == domain1 and self._domain_tracker_statuses[domain1] != "processing":
            # Re-entering domain1 (unlikely but handled)
            self._domain_tracker_statuses[domain1] = "processing"
            self._update_domain_icon(self.domain1_icon, "processing")

    def _hide_domain_tracker(self):
        """Stop spinner, hide frame, reset state"""
        self._stop_domain_spinner()
        self._domain_tracker_visible = False
        self._domain_tracker_domains = []
        self._domain_tracker_statuses = {}
        self.domain_tracker_frame.pack_forget()

    def _complete_domain_tracker(self):
        """Mark all domains as completed (green checks), stop spinner"""
        self._stop_domain_spinner()
        for i, domain in enumerate(self._domain_tracker_domains):
            self._domain_tracker_statuses[domain] = "completed"
            icon_label = self.domain1_icon if i == 0 else self.domain2_icon
            self._update_domain_icon(icon_label, "completed")

    def _create_progress_section(self, parent):
        """Create progress section with animated progress bar and phase indicator"""
        progress_frame = ctk.CTkFrame(parent, fg_color="transparent")
        progress_frame.pack(fill="x", side="top", pady=(0, 6))

        # Phase indicator label (shown when processing multiple domains)
        self.phase_label = ctk.CTkLabel(
            progress_frame,
            text="",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('accent_primary')
        )
        # Initially hidden - will be shown when phase info is available

        # Domain tracker frame (shown during counterpart processing)
        self.domain_tracker_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        # Initially hidden - packed when counterpart processing starts

        # Domain 1 widgets
        self.domain1_icon = ctk.CTkLabel(
            self.domain_tracker_frame,
            text="○",
            font=ctk.CTkFont(size=14),
            text_color=ColorPalette.get('text_muted'),
            width=20
        )
        self.domain1_icon.pack(side="left", padx=(0, 2))
        self.domain1_name = ctk.CTkLabel(
            self.domain_tracker_frame,
            text="",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('text_secondary')
        )
        self.domain1_name.pack(side="left", padx=(0, 16))

        # Domain 2 widgets
        self.domain2_icon = ctk.CTkLabel(
            self.domain_tracker_frame,
            text="○",
            font=ctk.CTkFont(size=14),
            text_color=ColorPalette.get('text_muted'),
            width=20
        )
        self.domain2_icon.pack(side="left", padx=(0, 2))
        self.domain2_name = ctk.CTkLabel(
            self.domain_tracker_frame,
            text="",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('text_secondary')
        )
        self.domain2_name.pack(side="left")

        # Use animated progress bar
        self.progress_bar = AnimatedProgressBar(
            progress_frame,
            height=8,
            corner_radius=4,
            progress_color=ColorPalette.get('accent_primary'),
            fg_color=ColorPalette.get('border')
        )
        self.progress_bar.pack(fill="x", pady=(0, 6))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Ready",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_secondary')
        )
        self.status_label.pack(anchor="w")

    def _create_control_buttons(self, parent):
        """Create control buttons with modern styling"""
        buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
        buttons_frame.pack(fill="x", side="bottom")

        # Start button
        self.start_button = ctk.CTkButton(
            buttons_frame,
            text="START",
            width=150,
            height=34,
            font=Typography.heading_sm(),
            fg_color=ColorPalette.get('accent_success'),
            hover_color="#059669" if ctk.get_appearance_mode() == "Light" else "#34d399",
            corner_radius=10,
            command=self._start_automation
        )
        self.start_button.pack(side="left", padx=(0, 10))

        # Stop button
        self.stop_button = ctk.CTkButton(
            buttons_frame,
            text="STOP",
            width=150,
            height=34,
            font=Typography.heading_sm(),
            fg_color=ColorPalette.get('accent_error'),
            hover_color="#dc2626" if ctk.get_appearance_mode() == "Light" else "#f87171",
            corner_radius=10,
            command=self._stop_automation,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=(0, 10))

        # Clear log button (icon style)
        clear_button = ctk.CTkButton(
            buttons_frame,
            text="\u2715",
            width=32,
            height=32,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color=ColorPalette.get('border'),
            border_width=1,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=10,
            command=self._clear_log
        )
        clear_button.pack(side="right", padx=(10, 0))
        ToolTip(clear_button, "Clear log")

    def _create_status_bar(self):
        """Create status bar at bottom of window"""
        status_bar = ctk.CTkFrame(
            self,
            height=32,
            corner_radius=0,
            fg_color=ColorPalette.get('bg_secondary'),
            border_width=1,
            border_color=ColorPalette.get('border')
        )
        status_bar.pack(fill="x", side="bottom")

        # Version
        version_label = ctk.CTkLabel(
            status_bar,
            text="v1.0.0",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('text_muted')
        )
        version_label.pack(side="left", padx=12, pady=4)

        # Session status indicator
        self.session_frame = ctk.CTkFrame(status_bar, fg_color="transparent")
        self.session_frame.pack(side="left", padx=(20, 0), pady=4)

        self.session_dot = ctk.CTkLabel(
            self.session_frame,
            text="●",
            font=ctk.CTkFont(size=10),
            text_color=ColorPalette.get('text_muted')
        )
        self.session_dot.pack(side="left", padx=(0, 4))

        self.session_status_label = ctk.CTkLabel(
            self.session_frame,
            text="No Session",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('text_muted')
        )
        self.session_status_label.pack(side="left")

        # Close Browser button
        self.close_browser_btn = ctk.CTkButton(
            status_bar,
            text="\u2715",
            width=22,
            height=22,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color=ColorPalette.get('border'),
            border_width=1,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=6,
            command=self._close_browser_session,
            state="disabled"
        )
        self.close_browser_btn.pack(side="left", padx=(15, 0), pady=4)
        ToolTip(self.close_browser_btn, "Close browser")

        # Sleep prevention indicator
        self.sleep_label = ctk.CTkLabel(
            status_bar,
            text="Sleep Prevention: Available" if self._check_wakepy() else "Sleep Prevention: N/A",
            font=Typography.body_sm(),
            text_color=ColorPalette.get('text_muted')
        )
        self.sleep_label.pack(side="right", padx=12, pady=4)

    def _check_prerequisites(self):
        """Check system prerequisites"""
        self._log("Checking prerequisites...", "INFO")

        # Check Firefox
        if check_firefox_installed():
            self._log("Firefox: Found", "SUCCESS")
        else:
            self._log("Firefox: Not found - please install Firefox", "ERROR")

        # Check geckodriver
        available, path = check_geckodriver_available()
        if available:
            self._log(f"Geckodriver: Found ({path})", "SUCCESS")
        else:
            self._log(f"Geckodriver: {path}", "WARNING")

        # Check Firefox profile
        profile = find_firefox_profile()
        if profile:
            self._log("Firefox Profile: Found", "SUCCESS")
        else:
            self._log("Firefox Profile: Not found - certificate auth may fail", "WARNING")

        self._log("Ready to start automation", "INFO")

    def _check_wakepy(self):
        """Check if wakepy is available"""
        try:
            from wakepy import keep
            return True
        except ImportError:
            return False

    def _close_browser_session(self):
        """Manually close the browser session"""
        if self.is_running:
            messagebox.showwarning("Cannot Close", "Cannot close browser while automation is running.")
            return

        if self.bot is None:
            return

        confirm = messagebox.askyesno(
            "Close Browser",
            "Are you sure you want to close the browser?\n\n"
            "You will need to enter your Token PIN again on the next workflow.",
            icon="question"
        )

        if confirm:
            try:
                self.bot.close_browser()
                self._log("Browser session closed manually", "INFO")
            except Exception as e:
                self._log(f"Error closing browser: {e}", "WARNING")
            finally:
                self.bot = None
                self.session_valid = False
                self._update_session_status()

    def _update_session_status(self):
        """Update the session status indicator in the status bar"""
        if self.bot and self.bot.is_session_valid():
            self.session_valid = True
            self.session_dot.configure(text_color=ColorPalette.get('accent_success'))
            self.session_status_label.configure(
                text="Session Active",
                text_color=ColorPalette.get('accent_success')
            )
            self.close_browser_btn.configure(state="normal" if not self.is_running else "disabled")
        else:
            self.session_valid = False
            self.session_dot.configure(text_color=ColorPalette.get('text_muted'))
            self.session_status_label.configure(
                text="No Session",
                text_color=ColorPalette.get('text_muted')
            )
            self.close_browser_btn.configure(state="disabled")

    def _log(self, message, level="INFO"):
        """Add message to log output"""
        # Update colors in case theme changed
        self._update_log_colors()

        timestamp = __import__('datetime').datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"

        self.log_text.configure(state="normal")
        self.log_text._textbox.insert("end", formatted, level)
        self.log_text.configure(state="disabled")

        if self.autoscroll_var.get():
            self.log_text.see("end")

    def _copy_logs_to_clipboard(self):
        """Copy all log text to clipboard"""
        log_content = self.log_text.get("1.0", "end").strip()
        if log_content:
            self.clipboard_clear()
            self.clipboard_append(log_content)
            # Brief visual feedback with checkmark
            self.copy_logs_btn.configure(text="\u2713")
            self.after(1500, lambda: self.copy_logs_btn.configure(text="\u2398"))

    def _clear_usernames(self):
        """Clear the usernames input"""
        self.usernames_text.delete("1.0", "end")
        self._update_username_count()

    def _update_username_count(self, event=None):
        """Update the username count indicator"""
        text = self.usernames_text.get("1.0", "end").strip()
        if text:
            count = len([u for u in text.split("\n") if u.strip()])
        else:
            count = 0

        # Update label text and color
        if count == 0:
            self.username_count_label.configure(
                text="0 users entered",
                text_color=ColorPalette.get('text_muted')
            )
        elif count == 1:
            self.username_count_label.configure(
                text="1 user entered",
                text_color=ColorPalette.get('accent_primary')
            )
        else:
            self.username_count_label.configure(
                text=f"{count} users entered",
                text_color=ColorPalette.get('accent_primary')
            )

    def _clear_log(self):
        """Clear log output with confirmation"""
        confirm = messagebox.askyesno(
            "Clear Logs",
            "Are you sure you want to clear the logs?\n\n"
            "Note: Logs may be needed by system administrators for troubleshooting or improving the application.",
            icon="warning"
        )

        if confirm:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
            self.log_buffer.clear()

    def _notify_user(self, success=True, processed_count=0):
        """Send system notification and request attention when automation finishes"""
        try:
            workflow_name = getattr(self, '_current_workflow_name', 'Workflow')
            if success:
                if processed_count > 0:
                    msg = f"{workflow_name} — Processed {processed_count} item(s)"
                else:
                    msg = f"{workflow_name} completed successfully!"
            else:
                msg = f"{workflow_name} finished with errors."

            if sys.platform == "darwin":
                # macOS: system notification with app icon
                title = "PNPKI Approval Automation"
                if getattr(sys, 'frozen', False):
                    # Bundled .app — use bundle identifier so macOS shows our app icon
                    script = (
                        'tell application id "com.govca.approval"\n'
                        f'  display notification "{msg}" with title "{title}" sound name "default"\n'
                        'end tell'
                    )
                else:
                    # Development — fall back to plain osascript (shows Script Editor icon)
                    script = f'display notification "{msg}" with title "{title}" sound name "default"'
                subprocess.Popen(
                    ["osascript", "-e", script],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                # Bounce dock icon (request user attention)
                subprocess.Popen([
                    "osascript", "-e",
                    'tell application "System Events" to set frontmost of the first process '
                    'whose unix id is (do shell script "echo $PPID") to false'
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "win32":
                # Windows: toast notification via PowerShell
                title = "PNPKI Approval Automation"
                ps_script = (
                    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                    "ContentType = WindowsRuntime] > $null; "
                    "$template = [Windows.UI.Notifications.ToastNotificationManager]::"
                    "GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                    "$textNodes = $template.GetElementsByTagName('text'); "
                    f"$textNodes.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null; "
                    f"$textNodes.Item(1).AppendChild($template.CreateTextNode('{msg}')) > $null; "
                    "$toast = [Windows.UI.Notifications.ToastNotification]::new($template); "
                    "[Windows.UI.Notifications.ToastNotificationManager]::"
                    "CreateToastNotifier('PNPKI Approval').Show($toast)"
                )
                subprocess.Popen(
                    ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=0x08000000  # CREATE_NO_WINDOW
                )
                # Flash taskbar
                try:
                    import ctypes
                    ctypes.windll.user32.FlashWindow(
                        ctypes.windll.kernel32.GetConsoleWindow(), True
                    )
                except Exception:
                    pass
        except Exception:
            pass
        # Cross-platform: system bell as fallback
        try:
            self.bell()
        except Exception:
            pass
        # Bring window to front
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(1000, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def _poll_updates(self):
        """Poll for log and progress updates from automation thread"""
        try:
            # Poll log messages
            new_messages = self.log_buffer.poll()
            for msg in new_messages:
                self._log(msg.message, msg.level)

            # Poll progress (now returns dict)
            data = self.progress_tracker.poll()
            current = data['current']
            total = data['total']
            if data['changed']:
                message = data['message']
                phase = data['phase']
                total_phases = data['total_phases']
                phase_label = data['phase_label']

                # Update phase indicator
                if self._domain_tracker_visible:
                    # Use visual domain tracker instead of plain text
                    self._update_domain_tracker(phase, total_phases, phase_label)
                else:
                    if total_phases > 1 and phase_label:
                        self.phase_label.configure(text=f"Phase {phase}/{total_phases}: {phase_label}")
                        self.phase_label.pack(anchor="w", pady=(0, 4))
                    elif phase_label:
                        self.phase_label.configure(text=phase_label)
                        self.phase_label.pack(anchor="w", pady=(0, 4))
                    else:
                        self.phase_label.pack_forget()

                # Update progress bar
                if total > 0:
                    progress = current / total
                    self.progress_bar.set_animated(progress)
                    self.status_label.configure(text=f"{message} ({current}/{total})")
                elif total < 0:
                    # Indeterminate
                    self.progress_bar.set_animated(0.5)
                    self.status_label.configure(text=message if message else "Processing...")
                else:
                    self.progress_bar.set_animated(0)
                    self.status_label.configure(text=message if message else "Ready")

            # Check if thread finished
            if self.automation_thread and not self.automation_thread.is_alive():
                self._cancel_escalation_timers()
                was_running = self.is_running
                self.is_running = False
                self.automation_thread = None
                self._update_button_states()
                self.progress_bar.set_animated(1 if current > 0 else 0)

                # Check if there were errors in the log
                has_errors = "ERROR" in self.log_text.get("1.0", "end")

                # Update domain tracker on completion
                if self._domain_tracker_visible:
                    if was_running and not has_errors and not self.cancel_event.is_set():
                        self._complete_domain_tracker()
                    else:
                        self._hide_domain_tracker()

                # Stop animation and show result
                if was_running and self.log_view_mode != "logs":
                    self._stop_animation()
                    self._show_result(success=not has_errors)

                # Notify user (system notification + dock bounce / taskbar flash)
                if was_running:
                    self._notify_user(success=not has_errors, processed_count=current)

                # Update session status after workflow completes
                self._update_session_status()

                # Reset status if thread died before any progress (e.g., Firefox failed to start)
                if current == 0:
                    self.status_label.configure(text="Ready")
                    self.phase_label.pack_forget()
                    if self._domain_tracker_visible:
                        self._hide_domain_tracker()

            # Periodic session status check (every 5 seconds = 50 polls at 100ms)
            if not hasattr(self, '_session_check_counter'):
                self._session_check_counter = 0
            self._session_check_counter += 1
            if self._session_check_counter >= 50:
                self._session_check_counter = 0
                if not self.is_running:  # Only check when not running
                    self._update_session_status()

        except Exception as e:
            # Log error but never let polling die
            try:
                self._log(f"Polling error: {e}", "ERROR")
            except:
                pass

        # ALWAYS reschedule — outside try/except so polling never dies
        self.after(100, self._poll_updates)

    def _update_button_states(self):
        """Update button states based on running status"""
        if self.is_running:
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            for v, widgets in self.workflow_frames.items():
                for widget in [widgets['container'], widgets['inner'], widgets['title'], widgets['subtitle']]:
                    widget.unbind('<Button-1>')
        else:
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            for v, widgets in self.workflow_frames.items():
                for widget in [widgets['container'], widgets['inner'], widgets['title'], widgets['subtitle']]:
                    widget.bind('<Button-1>', lambda e, val=v: self._select_workflow(val))

    def _start_automation(self):
        """Start the automation process"""
        if self.is_running:
            return

        # Validate inputs
        workflow = self.selected_workflow.get()
        domain = get_default_domain()
        comment = self.comment_entry.get().strip() or "Approved via automation"

        # Get specific users if applicable
        specific_users = None
        if workflow == "1" and self.mode_var.get() == "specific":
            usernames_text = self.usernames_text.get("1.0", "end").strip()
            if usernames_text:
                specific_users = [u.strip() for u in usernames_text.split("\n") if u.strip()]
            if not specific_users:
                messagebox.showerror("Error", "Please enter at least one username")
                return

        # Confirmation dialog for batch reject
        batch_reject_mode = workflow == "1" and self.batch_reject_var.get()
        if batch_reject_mode:
            confirm = messagebox.askyesno(
                "Confirm Batch Reject",
                "⚠ BATCH REJECTION\n\n"
                "You are about to REJECT all specified users.\n\n"
                "This action cannot be undone.\n\n"
                "Are you sure you want to continue?",
                icon='warning'
            )
            if not confirm:
                return

        # Reset state
        self.cancel_event.clear()
        self.log_buffer.clear()
        self.progress_tracker.reset()
        self.progress_bar.set(0)
        self.is_running = True
        self._update_button_states()

        # Setup domain tracker for counterpart processing
        use_counterpart = self.counterpart_var.get()
        if workflow in ("1", "2") and use_counterpart:
            self._setup_domain_tracker(domain)
        elif workflow == "3" and not self.all_domains_var.get() and use_counterpart:
            self._setup_domain_tracker(domain)
        else:
            self._hide_domain_tracker()

        # Start animation if animation is visible (animation or split mode)
        if self.log_view_mode != "logs":
            self._set_log_view(self.log_view_mode)  # Re-apply layout to ensure animation is packed
            self._start_animation()

        # Reuse existing bot or create new one
        # Get auth method from saved settings
        auth_method = get_auth_method()

        if self.bot is None:
            self.bot = GovCAApprovalBot(
                log_callback=self.log_buffer.get_callback(),
                progress_callback=self.progress_tracker.get_callback(),
                cancel_event=self.cancel_event,
                auth_method=auth_method
            )
        else:
            # Update callbacks on existing bot for this workflow
            self.bot.update_callbacks(
                log_callback=self.log_buffer.get_callback(),
                progress_callback=self.progress_tracker.get_callback(),
                cancel_event=self.cancel_event,
                auth_method=auth_method
            )

        bot = self.bot  # Local reference for thread

        # Start automation thread
        def run_automation():
            try:
                if workflow == "1":
                    if batch_reject_mode:
                        # Batch Reject mode
                        bot.run_rejection_process(
                            domain=domain,
                            comment=comment,
                            process_counterpart=self.counterpart_var.get(),
                            specific_users=specific_users
                        )
                    else:
                        # Normal approval
                        bot.run_approval_process(
                            domain=domain,
                            comment=comment,
                            process_counterpart=self.counterpart_var.get(),
                            specific_users=specific_users
                        )
                elif workflow == "2":
                    bot.run_revoke_certificate_approval(
                        domain=domain,
                        comment=comment,
                        process_counterpart=self.counterpart_var.get()
                    )
                elif workflow == "3":
                    if self.all_domains_var.get():
                        # All domains mode
                        bot.run_assign_user_groups_all_domains()
                    else:
                        # Single domain mode
                        bot.run_assign_user_group(domain=domain)
                        if self.counterpart_var.get():
                            counterpart = bot.get_counterpart_domain(domain)
                            if counterpart:
                                bot.run_assign_user_group(domain=counterpart)

            except OperationCancelledException:
                self.log_buffer.add("Operation cancelled by user", "WARNING")
            except Exception as e:
                if self.cancel_event.is_set():
                    self.log_buffer.add("Operation cancelled by user", "WARNING")
                else:
                    self.log_buffer.add(f"Error: {e}", "ERROR")
            # NOTE: Browser is intentionally kept open for session reuse
            # User can close it manually via "Close Browser" button

        workflow_names = {
            "1": "Add User (Batch Reject)" if batch_reject_mode else "Add User (Batch Approve)",
            "2": "Revoke Cert",
            "3": "Assign Group - All Domains" if self.all_domains_var.get() else "Assign Group (Single)"
        }
        self._current_workflow = workflow
        self._current_workflow_name = workflow_names.get(workflow, "Unknown")

        self.automation_thread = threading.Thread(target=run_automation, daemon=True)
        self.automation_thread.start()

        self._log(f"Started workflow {workflow}: {self._current_workflow_name}", "INFO")

    def _stop_automation(self):
        """Stop the automation process with escalation."""
        if not self.is_running:
            return

        self._log("Stopping automation...", "WARNING")
        self.cancel_event.set()
        self.status_label.configure(text="Stopping...")

        # Cancel any existing escalation timers before scheduling new ones
        self._cancel_escalation_timers()
        # Schedule escalation: force-quit browser after 5s if thread still alive
        self._escalate_timer_id = self.after(5000, self._escalate_stop)

    def _escalate_stop(self):
        """Escalate stop by force-quitting the browser driver."""
        self._escalate_timer_id = None
        if self.automation_thread and self.automation_thread.is_alive():
            self._log("Cooperative stop timed out, force-quitting browser...", "WARNING")
            if self.bot and self.bot.driver:
                try:
                    self.bot.driver.quit()
                except Exception:
                    pass
                self.bot.driver = None
            # Schedule final cleanup after another 5s
            self._finalize_timer_id = self.after(5000, self._finalize_stop)
        elif self.is_running:
            # Thread already dead but UI wasn't cleaned up (polling may have failed)
            self._log("Thread already stopped, cleaning up...", "WARNING")
            self._finalize_stop()

    def _finalize_stop(self):
        """Final cleanup: force-reset UI state regardless of thread status."""
        self._finalize_timer_id = None
        if self.is_running:
            self._log("Force-resetting UI state", "WARNING")
            self.is_running = False
            self.automation_thread = None
            self._update_button_states()
            self.status_label.configure(text="Stopped (force)")
            if self.log_view_mode != "logs":
                self._stop_animation()
                self._show_result(success=False)
            self._notify_user(success=False)
            self._update_session_status()

    def _cancel_escalation_timers(self):
        """Cancel any pending escalation timers."""
        if self._escalate_timer_id is not None:
            self.after_cancel(self._escalate_timer_id)
            self._escalate_timer_id = None
        if self._finalize_timer_id is not None:
            self.after_cancel(self._finalize_timer_id)
            self._finalize_timer_id = None

    def on_closing(self):
        """Handle window close"""
        if self.is_running:
            if messagebox.askyesno("Confirm Exit", "Automation is running. Are you sure you want to exit?"):
                self.cancel_event.set()
                # Close browser when app exits
                if self.bot:
                    try:
                        self.bot.close_browser()
                    except:
                        pass
                self.destroy()
        else:
            # Close browser when app exits
            if self.bot:
                try:
                    self.bot.close_browser()
                except:
                    pass
            self.destroy()


def main():
    """Application entry point"""
    app = GovCAApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
