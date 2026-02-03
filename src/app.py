"""
GovCA Approval Automation - Main GUI Application
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
from PIL import Image, ImageTk

# Handle imports for both package and direct execution
try:
    from .logging_handler import LogBuffer, ProgressTracker
    from .core.bot import GovCAApprovalBot, OperationCancelledException
    from .core.browser import check_firefox_installed, check_geckodriver_available, find_firefox_profile
    from .utils.settings import get_default_domain, set_default_domain, DOMAIN_LIST
    from .utils.resources import get_gif_path
except ImportError:
    from logging_handler import LogBuffer, ProgressTracker
    from core.bot import GovCAApprovalBot, OperationCancelledException
    from core.browser import check_firefox_installed, check_geckodriver_available, find_firefox_profile
    from utils.settings import get_default_domain, set_default_domain, DOMAIN_LIST
    from utils.resources import get_gif_path

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
    """A card-style frame with modern styling"""

    def __init__(self, parent, **kwargs):
        # Default card styling
        kwargs.setdefault('corner_radius', 12)
        kwargs.setdefault('border_width', 1)
        kwargs.setdefault('border_color', ColorPalette.get('border'))
        kwargs.setdefault('fg_color', ColorPalette.get('bg_card'))

        super().__init__(parent, **kwargs)

    def update_colors(self):
        """Update colors based on current theme"""
        self.configure(
            border_color=ColorPalette.get('border'),
            fg_color=ColorPalette.get('bg_card')
        )


class ResizablePanedWindow(tk.PanedWindow):
    """
    A styled PanedWindow that matches CustomTkinter appearance.
    Provides resizable sash (divider) between panes.
    """

    def __init__(self, parent, **kwargs):
        # Get orientation
        orient = kwargs.pop('orient', tk.VERTICAL)

        # Configure PanedWindow styling
        super().__init__(
            parent,
            orient=orient,
            sashwidth=8,
            sashpad=0,
            bg=ColorPalette.get('bg_primary'),
            sashrelief=tk.FLAT,
            borderwidth=0,
            opaqueresize=True
        )

        # Create styled sash
        self._setup_sash_styling()

        # Bind for theme changes
        self.bind('<Map>', self._update_colors)

    def _setup_sash_styling(self):
        """Setup cursor change on sash hover"""
        self.bind('<Motion>', self._on_motion)
        self.bind('<Leave>', self._on_leave)

    def _on_motion(self, event):
        """Change cursor when near sash"""
        try:
            # Check if we're near any sash
            for i in range(len(self.panes()) - 1):
                sash_coord = self.sash_coord(i)
                if sash_coord:
                    sash_y = sash_coord[1]
                    if abs(event.y - sash_y) < 10:
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
        self.title("GovCA Approval Automation")
        self.geometry("950x800")
        self.minsize(800, 650)

        # State
        self.automation_thread = None
        self.cancel_event = threading.Event()
        self.log_buffer = LogBuffer()
        self.progress_tracker = ProgressTracker()
        self.selected_workflow = ctk.StringVar(value="1")
        self.is_running = False
        self.logs_visible = False  # Animation is default view
        self.animation_running = False
        self.animation_frame_index = 0
        self.animation_after_id = None
        self.gif_frames = []  # GIF animation frames
        self.gif_target_size = (300, 188)

        # Bot persistence - keep browser session open between workflows
        self.bot = None
        self.session_valid = False

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
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title Section
        self._create_title_section(self.main_frame)

        # Workflow Selection Section
        self._create_workflow_section(self.main_frame)

        # Create resizable paned window for config and log sections
        self.main_paned = ResizablePanedWindow(self.main_frame, orient=tk.VERTICAL)
        self.main_paned.pack(fill="both", expand=True, pady=(0, 10))

        # Configuration pane (upper)
        self.config_pane = ctk.CTkFrame(self.main_paned, fg_color=ColorPalette.get('bg_card'), corner_radius=12)
        self._create_config_section(self.config_pane)
        self.main_paned.add(self.config_pane, minsize=120, height=220)

        # Log/Animation pane (lower)
        self.log_pane = ctk.CTkFrame(self.main_paned, fg_color=ColorPalette.get('bg_card'), corner_radius=12)
        self._create_log_section(self.log_pane)
        self.main_paned.add(self.log_pane, minsize=180, height=300)

        # Bottom frame for progress and buttons (fixed at bottom)
        bottom_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        bottom_frame.pack(fill="x", side="bottom", pady=(10, 0))

        # Control Buttons
        self._create_control_buttons(bottom_frame)

        # Progress Section
        self._create_progress_section(bottom_frame)

        # Status Bar
        self._create_status_bar()

    def _create_title_section(self, parent):
        """Create title section with modern styling"""
        title_frame = ctk.CTkFrame(parent, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 15))

        # Main title
        title_label = ctk.CTkLabel(
            title_frame,
            text="GovCA Approval Automation",
            font=Typography.heading_xl(),
            text_color=ColorPalette.get('text_primary')
        )
        title_label.pack()

        # Subtitle
        subtitle_label = ctk.CTkLabel(
            title_frame,
            text="Automated certificate approval workflow",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_muted')
        )
        subtitle_label.pack(pady=(2, 0))

    def _create_workflow_section(self, parent):
        """Create workflow selection section with card-style buttons"""
        section_frame = CardFrame(parent)
        section_frame.pack(fill="x", pady=(0, 10))

        # Header
        header = ctk.CTkLabel(
            section_frame,
            text="SELECT WORKFLOW",
            font=Typography.section_header(),
            text_color=ColorPalette.get('text_muted')
        )
        header.pack(anchor="w", padx=15, pady=(8, 4))

        # Workflow buttons container
        buttons_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=15, pady=(0, 8))
        buttons_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="workflow")

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
            btn_container.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")

            # Inner content
            inner = ctk.CTkFrame(btn_container, fg_color="transparent")
            inner.pack(expand=True, fill="both", padx=8, pady=8)

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
            subtitle_lbl.pack(pady=(2, 0))

            # Make entire frame clickable
            for widget in [btn_container, inner, title_lbl, subtitle_lbl]:
                widget.bind('<Button-1>', lambda e, v=value: self._select_workflow(v))
                widget.bind('<Enter>', lambda e, c=btn_container, v=value: self._on_workflow_hover(c, v, True))
                widget.bind('<Leave>', lambda e, c=btn_container, v=value: self._on_workflow_hover(c, v, False))

            self.workflow_frames[value] = {
                'container': btn_container,
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

    def _create_config_section(self, parent):
        """Create configuration section"""
        # Header
        header = ctk.CTkLabel(
            parent,
            text="CONFIGURATION",
            font=Typography.section_header(),
            text_color=ColorPalette.get('text_muted')
        )
        header.pack(anchor="w", padx=15, pady=(12, 8))

        # Config container (scrollable)
        config_container = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        config_container.pack(fill="both", expand=True, padx=15, pady=(0, 12))

        # Row 1: Domain and Comment
        row1 = ctk.CTkFrame(config_container, fg_color="transparent")
        row1.pack(fill="x", pady=3)

        # Domain (in its own frame for show/hide)
        self.domain_frame = ctk.CTkFrame(row1, fg_color="transparent")
        self.domain_frame.pack(side="left")

        ctk.CTkLabel(
            self.domain_frame,
            text="Domain:",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_secondary'),
            width=80,
            anchor="w"
        ).pack(side="left")

        self.domain_dropdown = ctk.CTkComboBox(
            self.domain_frame,
            width=180,
            height=32,
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
        self.domain_dropdown.set(get_default_domain())
        self.domain_dropdown.pack(side="left", padx=(0, 8))

        # Set as Default button
        self.set_default_btn = ctk.CTkButton(
            self.domain_frame,
            text="Set Default",
            width=90,
            height=32,
            font=Typography.body_sm(),
            fg_color="transparent",
            hover_color=ColorPalette.get('border'),
            border_width=1,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=8,
            command=self._set_default_domain
        )
        self.set_default_btn.pack(side="left", padx=(0, 15))

        # Comment
        self.comment_label = ctk.CTkLabel(
            row1,
            text="Comment:",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_secondary'),
            width=70,
            anchor="w"
        )
        self.comment_label.pack(side="left")

        self.comment_entry = ctk.CTkEntry(
            row1,
            width=250,
            height=32,
            font=Typography.body_md(),
            corner_radius=8,
            border_width=1,
            border_color=ColorPalette.get('border'),
            placeholder_text="Approved via automation"
        )
        self.comment_entry.pack(side="left")
        self.comment_entry.insert(0, "Approved via automation")

        # Domain note/disclaimer
        self.domain_note = ctk.CTkLabel(
            config_container,
            text="Note: Please select only domains for your region. Access depends on your certificate permissions.",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color=ColorPalette.get('text_muted')
        )
        self.domain_note.pack(fill="x", pady=(3, 5))

        # Row 2: Options
        row2 = ctk.CTkFrame(config_container, fg_color="transparent")
        row2.pack(fill="x", pady=4)

        # Counterpart checkbox
        self.counterpart_var = ctk.BooleanVar(value=True)
        self.counterpart_check = ctk.CTkCheckBox(
            row2,
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

        # Row 2.5: All Domains toggle (for workflow 3 only)
        self.all_domains_frame = ctk.CTkFrame(config_container, fg_color="transparent")
        self.all_domains_frame.pack(fill="x", pady=4)

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

        # Row 3: Mode selection (for workflow 1 only)
        self.mode_frame = ctk.CTkFrame(config_container, fg_color="transparent")
        self.mode_frame.pack(fill="x", pady=4)

        ctk.CTkLabel(
            self.mode_frame,
            text="Mode:",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_secondary'),
            width=80,
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
        self.usernames_frame = ctk.CTkFrame(config_container, fg_color="transparent")
        self.usernames_frame.pack(fill="x", pady=4)

        ctk.CTkLabel(
            self.usernames_frame,
            text="Usernames:",
            font=Typography.body_md(),
            text_color=ColorPalette.get('text_secondary'),
            width=80,
            anchor="nw"
        ).pack(side="left", anchor="n")

        self.usernames_text = ctk.CTkTextbox(
            self.usernames_frame,
            width=350,
            height=70,
            font=Typography.mono(12),
            corner_radius=8,
            border_width=1,
            border_color=ColorPalette.get('border'),
            fg_color=ColorPalette.get('bg_input')
        )
        self.usernames_text.pack(side="left")

        # Clear button for usernames
        self.clear_usernames_btn = ctk.CTkButton(
            self.usernames_frame,
            text="Clear",
            width=60,
            height=32,
            font=Typography.body_sm(),
            fg_color="transparent",
            hover_color=ColorPalette.get('border'),
            border_width=1,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=8,
            command=self._clear_usernames
        )
        self.clear_usernames_btn.pack(side="left", padx=(10, 0), anchor="n")

        # Username hint
        ctk.CTkLabel(
            self.usernames_frame,
            text="(one per line,\nwithout suffix)",
            font=ctk.CTkFont(size=10),
            text_color=ColorPalette.get('text_muted'),
            justify="left"
        ).pack(side="left", padx=(10, 0), anchor="n")

        # Initially hide usernames
        self.usernames_frame.pack_forget()

        # Batch Reject Option Frame (only visible when "Specific users only" is selected)
        self.batch_reject_frame = ctk.CTkFrame(config_container, fg_color="transparent")

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
        self.batch_reject_checkbox.pack(side="left", padx=(80, 0))

        # Warning label (shows when batch reject is enabled)
        self.batch_reject_warning = ctk.CTkLabel(
            self.batch_reject_frame,
            text="⚠ WARNING: This will REJECT all specified users!",
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

        # Show/hide domain and comment based on workflow
        if workflow == "3":
            # Assign group - show all_domains toggle
            self.all_domains_frame.pack(fill="x", pady=4)
            self.comment_entry.configure(state="disabled")
            self.mode_frame.pack_forget()
            self.usernames_frame.pack_forget()
            # Update domain/counterpart based on all_domains toggle
            self._toggle_all_domains()
        elif workflow == "2":
            # Revoke cert - show domain, comment, and counterpart
            self.domain_frame.pack(side="left")
            self.domain_dropdown.configure(state="readonly")
            self.comment_entry.configure(state="normal")
            self.counterpart_check.pack(side="left")
            self.mode_frame.pack_forget()
            self.usernames_frame.pack_forget()
        else:
            # Add user - show all
            self.domain_frame.pack(side="left")
            self.domain_dropdown.configure(state="readonly")
            self.comment_entry.configure(state="normal")
            self.counterpart_check.pack(side="left")
            self.mode_frame.pack(fill="x", pady=4)
            self._update_usernames_visibility()

    def _toggle_all_domains(self):
        """Toggle domain input based on All Domains switch"""
        if self.all_domains_var.get():
            # All domains mode - hide domain input and counterpart
            self.domain_frame.pack_forget()
            self.counterpart_check.pack_forget()
        else:
            # Single domain mode - show domain input and counterpart
            self.domain_frame.pack(side="left")
            self.domain_dropdown.configure(state="readonly")
            self.counterpart_check.pack(side="left")

    def _on_batch_reject_toggle(self):
        """Show/hide warning when batch reject is toggled"""
        if self.batch_reject_var.get():
            self.batch_reject_warning.pack(side="left", padx=(10, 0))
        else:
            self.batch_reject_warning.pack_forget()

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

    def _create_log_section(self, parent):
        """Create log output section with animation"""
        # Header with toggle button
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(12, 8))

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
            text="Show Logs",
            width=100,
            height=32,
            font=Typography.body_sm(),
            fg_color=ColorPalette.get('bg_secondary'),
            hover_color=ColorPalette.get('border'),
            border_width=1,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=8,
            command=self._toggle_logs
        )
        self.toggle_logs_btn.pack(side="right", padx=(8, 0))

        # Copy button
        self.copy_logs_btn = ctk.CTkButton(
            header_right,
            text="Copy",
            width=70,
            height=32,
            font=Typography.body_sm(),
            fg_color="transparent",
            hover_color=ColorPalette.get('border'),
            border_width=1,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=8,
            command=self._copy_logs_to_clipboard
        )
        self.copy_logs_btn.pack(side="right", padx=(8, 0))

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
        self.toggle_logs_btn.configure(text="Show Logs")

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
        """Toggle log visibility"""
        if self.logs_visible:
            # Hide logs, show animation if running
            self.log_text.pack_forget()
            self.autoscroll_switch.pack_forget()
            self.copy_logs_btn.pack_forget()
            self.toggle_logs_btn.configure(text="Show Logs")

            if self.is_running:
                self.animation_frame.pack(fill="both", expand=True)
                self._start_animation()
            else:
                self.animation_frame.pack(fill="both", expand=True)

            self.logs_visible = False
        else:
            # Show logs, hide animation
            self._stop_animation()
            self.animation_frame.pack_forget()
            self.autoscroll_switch.pack(side="right")
            self.copy_logs_btn.pack(side="right", padx=(8, 0))
            self.log_text.pack(fill="both", expand=True)
            self.toggle_logs_btn.configure(text="Hide Logs")
            self.logs_visible = True

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

    def _create_progress_section(self, parent):
        """Create progress section with animated progress bar"""
        progress_frame = ctk.CTkFrame(parent, fg_color="transparent")
        progress_frame.pack(fill="x", side="top", pady=(0, 10))

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
            height=44,
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
            height=44,
            font=Typography.heading_sm(),
            fg_color=ColorPalette.get('accent_error'),
            hover_color="#dc2626" if ctk.get_appearance_mode() == "Light" else "#f87171",
            corner_radius=10,
            command=self._stop_automation,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=(0, 10))

        # Clear log button (ghost style)
        clear_button = ctk.CTkButton(
            buttons_frame,
            text="Clear Log",
            width=110,
            height=44,
            font=Typography.body_md(),
            fg_color="transparent",
            hover_color=ColorPalette.get('border'),
            border_width=2,
            border_color=ColorPalette.get('border'),
            text_color=ColorPalette.get('text_secondary'),
            corner_radius=10,
            command=self._clear_log
        )
        clear_button.pack(side="right", padx=(10, 0))

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
            text="Close Browser",
            width=100,
            height=24,
            font=Typography.body_sm(),
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
            # Brief visual feedback
            original_text = self.copy_logs_btn.cget("text")
            self.copy_logs_btn.configure(text="Copied!")
            self.after(1500, lambda: self.copy_logs_btn.configure(text=original_text))

    def _clear_usernames(self):
        """Clear the usernames input"""
        self.usernames_text.delete("1.0", "end")

    def _set_default_domain(self):
        """Set the current domain as default"""
        domain = self.domain_dropdown.get()
        set_default_domain(domain)
        messagebox.showinfo("Default Domain", f"'{domain}' has been set as the default domain.")

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

    def _poll_updates(self):
        """Poll for log and progress updates from automation thread"""
        # Poll log messages
        new_messages = self.log_buffer.poll()
        for msg in new_messages:
            self._log(msg.message, msg.level)

        # Poll progress
        current, total, message, changed = self.progress_tracker.poll()
        if changed:
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
            was_running = self.is_running
            self.is_running = False
            self.automation_thread = None
            self._update_button_states()
            self.progress_bar.set_animated(1 if current > 0 else 0)

            # Stop animation and show result
            if was_running and not self.logs_visible:
                self._stop_animation()
                # Check if there were errors in the log
                has_errors = "ERROR" in self.log_text.get("1.0", "end")
                self._show_result(success=not has_errors)

            # Update session status after workflow completes
            self._update_session_status()

        # Periodic session status check (every 5 seconds = 50 polls at 100ms)
        if not hasattr(self, '_session_check_counter'):
            self._session_check_counter = 0
        self._session_check_counter += 1
        if self._session_check_counter >= 50:
            self._session_check_counter = 0
            if not self.is_running:  # Only check when not running
                self._update_session_status()

        # Schedule next poll
        self.after(100, self._poll_updates)

    def _update_button_states(self):
        """Update button states based on running status"""
        if self.is_running:
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            for v, widgets in self.workflow_frames.items():
                for widget in [widgets['container'], widgets['title'], widgets['subtitle']]:
                    widget.unbind('<Button-1>')
        else:
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            for v, widgets in self.workflow_frames.items():
                for widget in [widgets['container'], widgets['title'], widgets['subtitle']]:
                    widget.bind('<Button-1>', lambda e, val=v: self._select_workflow(val))

    def _start_automation(self):
        """Start the automation process"""
        if self.is_running:
            return

        # Validate inputs
        workflow = self.selected_workflow.get()
        domain = self.domain_dropdown.get() or "NCR00Sign"
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

        # Start animation if logs are hidden
        if not self.logs_visible:
            self.animation_frame.pack(fill="both", expand=True)
            self._start_animation()

        # Reuse existing bot or create new one
        if self.bot is None:
            self.bot = GovCAApprovalBot(
                log_callback=self.log_buffer.get_callback(),
                progress_callback=self.progress_tracker.get_callback(),
                cancel_event=self.cancel_event
            )
        else:
            # Update callbacks on existing bot for this workflow
            self.bot.update_callbacks(
                log_callback=self.log_buffer.get_callback(),
                progress_callback=self.progress_tracker.get_callback(),
                cancel_event=self.cancel_event
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
                self.log_buffer.add(f"Error: {e}", "ERROR")
            # NOTE: Browser is intentionally kept open for session reuse
            # User can close it manually via "Close Browser" button

        self.automation_thread = threading.Thread(target=run_automation, daemon=True)
        self.automation_thread.start()

        workflow_names = {
            "1": "Add User (Batch Reject)" if batch_reject_mode else "Add User (Batch Approve)",
            "2": "Revoke Cert",
            "3": "Assign Group - All Domains" if self.all_domains_var.get() else "Assign Group (Single)"
        }
        self._log(f"Started workflow {workflow}: {workflow_names.get(workflow, 'Unknown')}", "INFO")

    def _stop_automation(self):
        """Stop the automation process"""
        if not self.is_running:
            return

        self._log("Stopping automation...", "WARNING")
        self.cancel_event.set()
        self.status_label.configure(text="Stopping...")

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
