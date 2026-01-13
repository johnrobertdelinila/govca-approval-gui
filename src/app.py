"""
GovCA Approval Automation - Main GUI Application
Built with CustomTkinter for a modern, cross-platform look.
"""

import customtkinter as ctk
import threading
from tkinter import messagebox
import tkinter as tk
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


class GovCAApp(ctk.CTk):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Window setup
        self.title("GovCA Approval Automation")
        self.geometry("900x750")
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

        # Build UI
        self._create_widgets()
        self._check_prerequisites()

        # Defer GIF loading until after mainloop starts (ImageTk needs root window)
        self.after(100, self._load_gif_frames)

        # Start polling for log updates
        self._poll_updates()

    def _get_log_colors(self):
        """Get log colors based on current appearance mode"""
        if ctk.get_appearance_mode() == "Light":
            return {
                "INFO": "#333333",      # Dark gray for light mode
                "SUCCESS": "#228B22",   # Forest green
                "WARNING": "#CC7000",   # Dark orange
                "ERROR": "#CC0000"      # Dark red
            }
        else:
            return {
                "INFO": "#ffffff",      # White for dark mode
                "SUCCESS": "#00ff00",   # Bright green
                "WARNING": "#ffaa00",   # Orange
                "ERROR": "#ff4444"      # Red
            }

    def _update_log_colors(self):
        """Update log text colors based on current theme"""
        colors = self._get_log_colors()
        for level, color in colors.items():
            self.log_text._textbox.tag_configure(level, foreground=color)

    def _create_widgets(self):
        """Create all UI widgets"""
        # Main container with padding
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ctk.CTkLabel(
            main_frame,
            text="GovCA Approval Automation",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(0, 15))

        # Workflow Selection Section
        self._create_workflow_section(main_frame)

        # Configuration Section
        self._create_config_section(main_frame)

        # Create a bottom frame for progress and buttons (pack these BEFORE log so they stay visible)
        bottom_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        bottom_frame.pack(fill="x", side="bottom", pady=(10, 0))

        # Control Buttons (in bottom frame)
        self._create_control_buttons(bottom_frame)

        # Progress Section (in bottom frame, above buttons)
        self._create_progress_section(bottom_frame)

        # Log Output Section (expands to fill remaining space)
        self._create_log_section(main_frame)

        # Status Bar
        self._create_status_bar()

    def _create_workflow_section(self, parent):
        """Create workflow selection section"""
        section_frame = ctk.CTkFrame(parent)
        section_frame.pack(fill="x", pady=(0, 10))

        header = ctk.CTkLabel(
            section_frame,
            text="SELECT WORKFLOW",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray"
        )
        header.pack(anchor="w", padx=10, pady=(10, 5))

        # Workflow buttons container
        buttons_frame = ctk.CTkFrame(section_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=10, pady=(0, 10))

        # Configure grid (3 buttons now)
        buttons_frame.grid_columnconfigure((0, 1, 2), weight=1)

        workflows = [
            ("1", "Add User\n(Batch)", "Batch approve pending users"),
            ("2", "Revoke Cert\n(One-by-One)", "Approve revoke requests"),
            ("3", "Assign User\nGroup", "Assign users to groups"),
        ]

        self.workflow_buttons = {}
        for i, (value, text, tooltip) in enumerate(workflows):
            btn = ctk.CTkButton(
                buttons_frame,
                text=text,
                width=180,
                height=60,
                font=ctk.CTkFont(size=13),
                command=lambda v=value: self._select_workflow(v),
                fg_color="#2B5F91" if value == "1" else "gray40",
                hover_color="#3A7FC2"
            )
            btn.grid(row=0, column=i, padx=5, pady=5, sticky="ew")
            self.workflow_buttons[value] = btn

    def _select_workflow(self, value):
        """Handle workflow selection"""
        self.selected_workflow.set(value)

        # Update button colors
        for v, btn in self.workflow_buttons.items():
            if v == value:
                btn.configure(fg_color="#2B5F91")
            else:
                btn.configure(fg_color="gray40")

        # Update config visibility
        self._update_config_visibility()

    def _create_config_section(self, parent):
        """Create configuration section"""
        self.config_frame = ctk.CTkFrame(parent)
        self.config_frame.pack(fill="x", pady=(0, 10))

        header = ctk.CTkLabel(
            self.config_frame,
            text="CONFIGURATION",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray"
        )
        header.pack(anchor="w", padx=10, pady=(10, 5))

        # Config container
        config_container = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        config_container.pack(fill="x", padx=10, pady=(0, 10))

        # Row 1: Domain and Comment
        row1 = ctk.CTkFrame(config_container, fg_color="transparent")
        row1.pack(fill="x", pady=2)

        # Domain (in its own frame for show/hide)
        self.domain_frame = ctk.CTkFrame(row1, fg_color="transparent")
        self.domain_frame.pack(side="left")
        ctk.CTkLabel(self.domain_frame, text="Domain:", width=100, anchor="w").pack(side="left")
        self.domain_dropdown = ctk.CTkComboBox(
            self.domain_frame,
            width=200,
            values=DOMAIN_LIST,
            state="readonly"
        )
        self.domain_dropdown.set(get_default_domain())
        self.domain_dropdown.pack(side="left", padx=(0, 10))

        # Set as Default button
        self.set_default_btn = ctk.CTkButton(
            self.domain_frame,
            text="Set Default",
            width=90,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="gray50",
            hover_color="gray40",
            command=self._set_default_domain
        )
        self.set_default_btn.pack(side="left", padx=(0, 20))

        # Domain note/disclaimer
        self.domain_note = ctk.CTkLabel(
            config_container,
            text="Note: Please select only domains for your region. Access depends on your certificate permissions.",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="gray"
        )
        self.domain_note.pack(fill="x", pady=(2, 5))

        # Comment
        self.comment_label = ctk.CTkLabel(row1, text="Comment:", width=80, anchor="w")
        self.comment_label.pack(side="left")
        self.comment_entry = ctk.CTkEntry(row1, width=300, placeholder_text="Approved via automation")
        self.comment_entry.pack(side="left")
        self.comment_entry.insert(0, "Approved via automation")

        # Row 2: Options
        row2 = ctk.CTkFrame(config_container, fg_color="transparent")
        row2.pack(fill="x", pady=5)

        # Counterpart checkbox
        self.counterpart_var = ctk.BooleanVar(value=True)
        self.counterpart_check = ctk.CTkCheckBox(
            row2,
            text="Process counterpart domain (Sign/Auth)",
            variable=self.counterpart_var
        )
        self.counterpart_check.pack(side="left")

        # Row 2.5: All Domains toggle (for workflow 3 only)
        self.all_domains_frame = ctk.CTkFrame(config_container, fg_color="transparent")
        self.all_domains_frame.pack(fill="x", pady=5)

        self.all_domains_var = ctk.BooleanVar(value=False)
        self.all_domains_switch = ctk.CTkSwitch(
            self.all_domains_frame,
            text="Process ALL domains automatically",
            variable=self.all_domains_var,
            command=self._toggle_all_domains
        )
        self.all_domains_switch.pack(side="left")

        # Initially hide all domains toggle
        self.all_domains_frame.pack_forget()

        # Row 3: Mode selection (for workflow 1 only)
        self.mode_frame = ctk.CTkFrame(config_container, fg_color="transparent")
        self.mode_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(self.mode_frame, text="Mode:", width=100, anchor="w").pack(side="left")

        self.mode_var = ctk.StringVar(value="specific")
        mode_all = ctk.CTkRadioButton(
            self.mode_frame,
            text="All pending users",
            variable=self.mode_var,
            value="all",
            command=self._update_usernames_visibility
        )
        mode_all.pack(side="left", padx=(0, 20))

        mode_specific = ctk.CTkRadioButton(
            self.mode_frame,
            text="Specific users only",
            variable=self.mode_var,
            value="specific",
            command=self._update_usernames_visibility
        )
        mode_specific.pack(side="left")

        # Row 4: Usernames input (for specific mode)
        self.usernames_frame = ctk.CTkFrame(config_container, fg_color="transparent")
        self.usernames_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(
            self.usernames_frame,
            text="Usernames\n(one per line,\nwithout suffix):",
            width=100,
            anchor="nw"
        ).pack(side="left", anchor="n")

        self.usernames_text = ctk.CTkTextbox(self.usernames_frame, width=400, height=80)
        self.usernames_text.pack(side="left")

        # Clear button for usernames
        self.clear_usernames_btn = ctk.CTkButton(
            self.usernames_frame,
            text="Clear",
            width=60,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="gray50",
            hover_color="gray40",
            command=self._clear_usernames
        )
        self.clear_usernames_btn.pack(side="left", padx=(10, 0), anchor="n")

        # Initially hide usernames
        self.usernames_frame.pack_forget()

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
            self.all_domains_frame.pack(fill="x", pady=5)
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
            self.mode_frame.pack(fill="x", pady=5)
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

    def _update_usernames_visibility(self):
        """Show/hide usernames input based on mode"""
        if self.mode_var.get() == "specific" and self.selected_workflow.get() == "1":
            self.usernames_frame.pack(fill="x", pady=5)
        else:
            self.usernames_frame.pack_forget()

    def _create_log_section(self, parent):
        """Create log output section with collapsible feature and robot animation"""
        # Main log container
        self.log_container = ctk.CTkFrame(parent)
        self.log_container.pack(fill="both", expand=True, pady=(0, 10))

        # Header with toggle button
        header_frame = ctk.CTkFrame(self.log_container, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            header_frame,
            text="LOG OUTPUT",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray"
        ).pack(side="left")

        # Toggle button for show/hide logs
        self.toggle_logs_btn = ctk.CTkButton(
            header_frame,
            text="Hide Logs",
            width=100,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="gray50",
            hover_color="gray40",
            command=self._toggle_logs
        )
        self.toggle_logs_btn.pack(side="right", padx=(10, 0))

        # Copy to clipboard button
        self.copy_logs_btn = ctk.CTkButton(
            header_frame,
            text="Copy",
            width=80,
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="gray50",
            hover_color="gray40",
            command=self._copy_logs_to_clipboard
        )
        self.copy_logs_btn.pack(side="right", padx=(5, 0))

        # Auto-scroll toggle
        self.autoscroll_var = ctk.BooleanVar(value=True)
        self.autoscroll_check = ctk.CTkCheckBox(
            header_frame,
            text="Auto-scroll",
            variable=self.autoscroll_var,
            width=100
        )
        self.autoscroll_check.pack(side="right")

        # Log textbox frame
        self.log_text_frame = ctk.CTkFrame(self.log_container, fg_color="transparent")
        self.log_text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Log textbox
        self.log_text = ctk.CTkTextbox(
            self.log_text_frame,
            font=ctk.CTkFont(family="Consolas" if sys.platform == "win32" else "Monaco", size=12),
            wrap="word"
        )
        self.log_text.pack(fill="both", expand=True)

        # Configure text tags for colors based on theme
        self._update_log_colors()

        # Animation frame (shown by default)
        self.animation_frame = ctk.CTkFrame(self.log_container, fg_color="transparent")

        # Initially hide logs, show animation
        self.log_text_frame.pack_forget()
        self.autoscroll_check.pack_forget()
        self.copy_logs_btn.pack_forget()
        self.toggle_logs_btn.configure(text="Show Logs")
        self.animation_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # GIF label using tkinter Label (not CTkLabel) for better image support
        # GIF will be loaded after mainloop starts via deferred _load_gif_frames()
        self.gif_label = tk.Label(self.animation_frame)
        self.gif_label.pack(expand=True, pady=(20, 10))

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
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.message_label.pack(pady=(10, 0))

    def _toggle_logs(self):
        """Toggle log visibility"""
        if self.logs_visible:
            # Hide logs, show animation if running
            self.log_text_frame.pack_forget()
            self.autoscroll_check.pack_forget()
            self.copy_logs_btn.pack_forget()
            self.toggle_logs_btn.configure(text="Show Logs")

            if self.is_running:
                self.animation_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
                self._start_animation()

            self.logs_visible = False
        else:
            # Show logs, hide animation
            self._stop_animation()
            self.animation_frame.pack_forget()
            self.autoscroll_check.pack(side="right")
            self.copy_logs_btn.pack(side="right", padx=(5, 0))
            self.log_text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self.toggle_logs_btn.configure(text="Hide Logs")
            self.logs_visible = True

    def _load_gif_frames(self):
        """Load all frames from the GIF"""
        try:
            gif_path = get_gif_path()
            gif = Image.open(gif_path)
            self.gif_frames = []

            # Get GIF duration (default to 50ms if not available)
            try:
                self.gif_duration = gif.info.get('duration', 50)
            except Exception:
                self.gif_duration = 50

            # Extract all frames
            try:
                while True:
                    frame = gif.copy()
                    # Resize to fit nicely in the UI
                    frame = frame.resize((300, 188), Image.Resampling.LANCZOS)
                    self.gif_frames.append(ImageTk.PhotoImage(frame))
                    gif.seek(gif.tell() + 1)
            except EOFError:
                pass

            if self.gif_frames:
                self._log_internal(f"Loaded {len(self.gif_frames)} GIF frames")
                # Show first frame immediately after loading
                self.gif_label.configure(image=self.gif_frames[0])
        except Exception as e:
            self._log_internal(f"Failed to load GIF: {e}")
            self.gif_frames = []

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
        self.gif_label.pack(expand=True, pady=(20, 10))
        # Reset message label to normal style
        self.message_label.configure(
            text="",
            text_color="gray",
            font=ctk.CTkFont(size=14)
        )
        self._animate_gif()

    def _stop_animation(self):
        """Stop the GIF animation"""
        self.animation_running = False
        if self.animation_after_id:
            self.after_cancel(self.animation_after_id)
            self.animation_after_id = None

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
        # Show result message
        if success:
            self.message_label.configure(
                text="Mission Complete!",
                text_color="green",
                font=ctk.CTkFont(size=18, weight="bold")
            )
        else:
            self.message_label.configure(
                text="Error occurred",
                text_color="red",
                font=ctk.CTkFont(size=18, weight="bold")
            )

    def _create_progress_section(self, parent):
        """Create progress section"""
        progress_frame = ctk.CTkFrame(parent, fg_color="transparent")
        progress_frame.pack(fill="x", side="top", pady=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Ready",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(anchor="w")

    def _create_control_buttons(self, parent):
        """Create control buttons"""
        buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
        buttons_frame.pack(fill="x", side="bottom")

        # Start button
        self.start_button = ctk.CTkButton(
            buttons_frame,
            text="START",
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#28a745",
            hover_color="#218838",
            command=self._start_automation
        )
        self.start_button.pack(side="left", padx=5)

        # Stop button
        self.stop_button = ctk.CTkButton(
            buttons_frame,
            text="STOP",
            width=150,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#dc3545",
            hover_color="#c82333",
            command=self._stop_automation,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=5)

        # Clear log button
        clear_button = ctk.CTkButton(
            buttons_frame,
            text="CLEAR LOG",
            width=120,
            height=40,
            font=ctk.CTkFont(size=14),
            fg_color="gray50",
            hover_color="gray40",
            command=self._clear_log
        )
        clear_button.pack(side="right", padx=5)

    def _create_status_bar(self):
        """Create status bar at bottom of window"""
        status_bar = ctk.CTkFrame(self, height=30, corner_radius=0)
        status_bar.pack(fill="x", side="bottom")

        # Version
        version_label = ctk.CTkLabel(
            status_bar,
            text="v1.0.0",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        version_label.pack(side="left", padx=10)

        # Sleep prevention indicator
        self.sleep_label = ctk.CTkLabel(
            status_bar,
            text="Sleep Prevention: Available" if self._check_wakepy() else "Sleep Prevention: N/A",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.sleep_label.pack(side="right", padx=10)

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
            self._log(f"Firefox Profile: Found", "SUCCESS")
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
        # Show confirmation dialog
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
                self.progress_bar.set(progress)
                self.status_label.configure(text=f"{message} ({current}/{total})")
            elif total < 0:
                # Indeterminate
                self.progress_bar.set(0.5)  # Show some progress
                self.status_label.configure(text=message if message else "Processing...")
            else:
                self.progress_bar.set(0)
                self.status_label.configure(text=message if message else "Ready")

        # Check if thread finished
        if self.automation_thread and not self.automation_thread.is_alive():
            was_running = self.is_running
            self.is_running = False
            self.automation_thread = None
            self._update_button_states()
            self.progress_bar.set(1 if current > 0 else 0)

            # Stop animation and show result
            if was_running and not self.logs_visible:
                self._stop_animation()
                # Check if there were errors in the log
                has_errors = "ERROR" in self.log_text.get("1.0", "end")
                self._show_result(success=not has_errors)

        # Schedule next poll
        self.after(100, self._poll_updates)

    def _update_button_states(self):
        """Update button states based on running status"""
        if self.is_running:
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            for btn in self.workflow_buttons.values():
                btn.configure(state="disabled")
        else:
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            for btn in self.workflow_buttons.values():
                btn.configure(state="normal")

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

        # Reset state
        self.cancel_event.clear()
        self.log_buffer.clear()
        self.progress_tracker.reset()
        self.progress_bar.set(0)
        self.is_running = True
        self._update_button_states()

        # Start animation if logs are hidden
        if not self.logs_visible:
            self.animation_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self._start_animation()

        # Create bot with callbacks
        bot = GovCAApprovalBot(
            log_callback=self.log_buffer.get_callback(),
            progress_callback=self.progress_tracker.get_callback(),
            cancel_event=self.cancel_event
        )

        # Start automation thread
        def run_automation():
            try:
                if workflow == "1":
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
            finally:
                try:
                    bot.close_browser()
                except:
                    pass

        self.automation_thread = threading.Thread(target=run_automation, daemon=True)
        self.automation_thread.start()

        workflow_names = {
            "1": "Add User (Batch)",
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
                self.destroy()
        else:
            self.destroy()


def main():
    """Application entry point"""
    app = GovCAApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
