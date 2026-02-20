"""
PNPKI Approval Automation - Main GUI Application
Orchestrator that composes sidebar, config, progress, and completion views.
"""

import customtkinter as ctk
import threading
from tkinter import messagebox
import tkinter as tk
import sys
import os
import subprocess

# Handle imports for both package and direct execution
try:
    from .logging_handler import LogBuffer, ProgressTracker
    from .core.bot import GovCAApprovalBot, OperationCancelledException
    from .core.browser import check_firefox_installed, check_geckodriver_available, find_firefox_profile
    from .utils.settings import (
        get_default_domain, set_default_domain, DOMAIN_LIST, AUTH_METHODS,
        get_auth_method, set_auth_method, get_custom_gif, set_custom_gif,
        get_appearance_mode, set_appearance_mode,
    )
    from .utils.resources import get_gif_path, get_logo_path
    from .gui.design_system import ColorPalette, Typography
    from .gui.components import CardFrame, ToolTip
    from .gui.sidebar import SidebarFrame
    from .gui.config_panel import ConfigPanel
    from .gui.progress_panel import ProgressPanel, FullLogsDialog
    from .gui.completion_view import CompletionSummary
except ImportError:
    from logging_handler import LogBuffer, ProgressTracker
    from core.bot import GovCAApprovalBot, OperationCancelledException
    from core.browser import check_firefox_installed, check_geckodriver_available, find_firefox_profile
    from utils.settings import (
        get_default_domain, set_default_domain, DOMAIN_LIST, AUTH_METHODS,
        get_auth_method, set_auth_method, get_custom_gif, set_custom_gif,
        get_appearance_mode, set_appearance_mode,
    )
    from utils.resources import get_gif_path, get_logo_path
    from gui.design_system import ColorPalette, Typography
    from gui.components import CardFrame, ToolTip
    from gui.sidebar import SidebarFrame
    from gui.config_panel import ConfigPanel
    from gui.progress_panel import ProgressPanel, FullLogsDialog
    from gui.completion_view import CompletionSummary

ctk.set_appearance_mode(get_appearance_mode())
ctk.set_default_color_theme("blue")


# =============================================================================
# Settings Dialog (simplified - auth method + custom GIF + theme only)
# =============================================================================

class SettingsDialog(ctk.CTkToplevel):
    """Simplified settings dialog (domain moved to sidebar)."""

    def __init__(self, parent, on_save):
        super().__init__(parent)
        self.withdraw()
        self.title("Settings")
        self.resizable(False, False)
        self.transient(parent)
        self.on_save = on_save
        self.custom_gif_path = get_custom_gif() or ""

        self._build()

        self.update_idletasks()
        w, h = 400, 340
        px = parent.winfo_x() + (parent.winfo_width() - w) // 2
        py = parent.winfo_y() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

        self.attributes("-alpha", 0.0)
        self.deiconify()
        self.grab_set()
        self._fade_in(0.0)

    def _build(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        # Authentication Method
        ctk.CTkLabel(
            container, text="Authentication Method",
            font=Typography.heading_sm(),
            text_color=ColorPalette.get("text_primary"),
        ).pack(anchor="w", pady=(0, 8))

        self.auth_dropdown = ctk.CTkComboBox(
            container, width=310, height=36, values=AUTH_METHODS,
            state="readonly", font=Typography.body_md(),
            dropdown_font=Typography.body_md(), corner_radius=8,
            border_width=1, border_color=ColorPalette.get("border"),
            button_color=ColorPalette.get("accent_primary"),
            button_hover_color=ColorPalette.get("accent_secondary"),
        )
        self.auth_dropdown.set(get_auth_method())
        self.auth_dropdown.pack(pady=(0, 20))

        # Custom Animation
        ctk.CTkLabel(
            container, text="Custom Animation (GIF)",
            font=Typography.heading_sm(),
            text_color=ColorPalette.get("text_primary"),
        ).pack(anchor="w", pady=(0, 6))

        gif_row = ctk.CTkFrame(container, fg_color="transparent")
        gif_row.pack(fill="x", pady=(0, 4))

        self.gif_label = ctk.CTkLabel(
            gif_row,
            text=os.path.basename(self.custom_gif_path) if self.custom_gif_path else "Default animation",
            font=Typography.body_sm(),
            text_color=ColorPalette.get("text_secondary"),
            anchor="w", width=180,
        )
        self.gif_label.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            gif_row, text="Browse", width=70, height=30,
            font=Typography.body_sm(),
            fg_color=ColorPalette.get("accent_primary"),
            hover_color=ColorPalette.get("accent_secondary"),
            corner_radius=6, command=self._browse_gif,
        ).pack(side="left", padx=(6, 0))

        ctk.CTkButton(
            gif_row, text="Reset", width=60, height=30,
            font=Typography.body_sm(),
            fg_color=ColorPalette.get("border"),
            hover_color=ColorPalette.get("border_light"),
            text_color=ColorPalette.get("text_primary"),
            corner_radius=6, command=self._reset_gif,
        ).pack(side="left", padx=(6, 0))

        ctk.CTkLabel(
            container,
            text="Note: Select only domains for your region.\n"
                 "Access depends on your certificate permissions.",
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color=ColorPalette.get("text_muted"),
            justify="left",
        ).pack(anchor="w", pady=(0, 15))

        ctk.CTkButton(
            container, text="Save & Close", width=360, height=40,
            font=Typography.heading_sm(),
            fg_color=ColorPalette.get("accent_primary"),
            hover_color=ColorPalette.get("accent_secondary"),
            corner_radius=8, command=self._save,
        ).pack()

    def _browse_gif(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self, title="Select Animation GIF",
            filetypes=[("GIF files", "*.gif"), ("All files", "*.*")],
        )
        if path:
            self.custom_gif_path = path
            self.gif_label.configure(text=os.path.basename(path))

    def _reset_gif(self):
        self.custom_gif_path = ""
        self.gif_label.configure(text="Default animation")

    def _fade_in(self, alpha):
        alpha = min(alpha + 0.1, 1.0)
        self.attributes("-alpha", alpha)
        if alpha < 1.0:
            self.after(15, self._fade_in, alpha)

    def _save(self):
        set_auth_method(self.auth_dropdown.get())
        set_custom_gif(self.custom_gif_path)
        self.on_save()
        self.destroy()


# =============================================================================
# MAIN APPLICATION
# =============================================================================

class GovCAApp(ctk.CTk):
    """Main application window with sidebar + content layout."""

    # Content states
    STATE_CONFIG = "config"
    STATE_RUNNING = "running"
    STATE_COMPLETED = "completed"

    def __init__(self):
        super().__init__()

        self.title("PNPKI Approval Automation")
        self.geometry("1100x850")
        self.minsize(900, 700)

        # Core state
        self.automation_thread = None
        self.cancel_event = threading.Event()
        self.log_buffer = LogBuffer()
        self.progress_tracker = ProgressTracker()
        self.is_running = False
        self._content_state = self.STATE_CONFIG
        self._current_workflow = "1"
        self._current_workflow_name = ""

        # Bot persistence
        self.bot = None
        self.session_valid = False

        # Stop escalation
        self._escalate_timer_id = None
        self._finalize_timer_id = None

        # Run metrics
        self._run_domains_processed = []

        # Build UI
        self._build_layout()
        self._check_prerequisites()

        # Defer GIF loading
        self.after(100, self._load_gifs)

        # Start polling
        self._poll_updates()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self):
        self.configure(fg_color=ColorPalette.get("bg_base"))

        # Root layout: sidebar | divider | content
        root_frame = ctk.CTkFrame(self, fg_color="transparent")
        root_frame.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = SidebarFrame(
            root_frame,
            on_workflow_select=self._on_workflow_select,
            on_domain_change=self._on_domain_change,
            on_settings_click=self._open_settings,
            on_theme_toggle=self._on_theme_toggle,
        )
        self.sidebar.pack(side="left", fill="y")

        # Divider — 1px using bg_base for depth contrast
        ctk.CTkFrame(root_frame, width=1, fg_color=ColorPalette.get("bg_base")).pack(
            side="left", fill="y"
        )

        # Content area — bg_base so cards float visually above it
        self.content_frame = ctk.CTkFrame(root_frame, fg_color=ColorPalette.get("bg_base"))
        self.content_frame.pack(side="left", fill="both", expand=True)

        # Config panel
        self.config_panel = ConfigPanel(
            self.content_frame,
            on_start=self._start_automation,
        )
        self.config_panel.update_domain_badge(get_default_domain())

        # Progress panel
        self.progress_panel = ProgressPanel(self.content_frame)
        self.progress_panel.stop_button.configure(command=self._stop_automation)
        self.progress_panel.view_full_btn.configure(command=self._show_full_logs)

        # Completion view
        self.completion_view = CompletionSummary(
            self.content_frame,
            on_run_again=self._run_again,
            on_new_task=self._new_task,
            on_view_logs=self._show_full_logs,
        )

        # Show initial state
        self._show_config_view()

    # ------------------------------------------------------------------
    # Content State Machine
    # ------------------------------------------------------------------

    def _show_config_view(self):
        self._content_state = self.STATE_CONFIG
        self.progress_panel.pack_forget()
        self.completion_view.pack_forget()
        self.config_panel.pack(fill="both", expand=True)
        self.config_panel.set_enabled(True)

    def _show_running_view(self):
        self._content_state = self.STATE_RUNNING
        self.config_panel.pack_forget()
        self.completion_view.pack_forget()
        self.progress_panel.reset()
        self.progress_panel.pack(fill="both", expand=True)

    def _show_completion_view(self, success, total_processed, errors, elapsed_seconds):
        self._content_state = self.STATE_COMPLETED
        self.config_panel.pack_forget()
        self.progress_panel.pack_forget()
        self.completion_view.pack(fill="both", expand=True)

        domains = self._run_domains_processed if self._run_domains_processed else None
        self.completion_view.show_results(
            success=success,
            total_processed=total_processed,
            domains_processed=domains,
            errors=errors,
            elapsed_seconds=elapsed_seconds,
        )

    # ------------------------------------------------------------------
    # Sidebar Callbacks
    # ------------------------------------------------------------------

    def _on_workflow_select(self, workflow_id):
        if self.is_running:
            return
        self._current_workflow = workflow_id
        self.config_panel.set_workflow(workflow_id, domain=self.sidebar.get_domain())
        if self._content_state != self.STATE_CONFIG:
            self._show_config_view()

    def _on_domain_change(self, domain):
        self.config_panel.update_domain_badge(domain)

    def _on_theme_toggle(self, mode):
        """Handle theme mode change from sidebar toggle."""
        ctk.set_appearance_mode(mode)
        set_appearance_mode(mode)
        # Allow CTk to process the mode change, then refresh custom colors
        self.after(50, self._propagate_theme_change)

    def _propagate_theme_change(self):
        """Refresh all custom-colored components after theme switch."""
        self.configure(fg_color=ColorPalette.get("bg_base"))
        self.content_frame.configure(fg_color=ColorPalette.get("bg_base"))
        self.sidebar.update_colors()
        self.config_panel.update_colors()
        self.progress_panel.update_colors()
        self.completion_view.update_colors()

    def _open_settings(self):
        SettingsDialog(self, on_save=self._on_settings_saved)

    def _on_settings_saved(self):
        # Reload GIF in case custom animation changed
        self._load_gifs()

    # ------------------------------------------------------------------
    # Action buttons (completion view)
    # ------------------------------------------------------------------

    def _run_again(self):
        """Return to config with same workflow pre-filled."""
        self._show_config_view()

    def _new_task(self):
        """Return to clean config view."""
        self.config_panel.set_workflow(self._current_workflow,
                                       domain=self.sidebar.get_domain())
        self._show_config_view()

    def _show_full_logs(self):
        """Open full logs in a popup dialog."""
        FullLogsDialog(self, self.log_buffer.messages)

    # ------------------------------------------------------------------
    # GIF Loading
    # ------------------------------------------------------------------

    def _load_gifs(self):
        self.progress_panel.load_gif_frames()

    # ------------------------------------------------------------------
    # Prerequisites
    # ------------------------------------------------------------------

    def _check_prerequisites(self):
        self.log_buffer.add("Checking prerequisites...", "INFO")
        if check_firefox_installed():
            self.log_buffer.add("Firefox: Found", "SUCCESS")
        else:
            self.log_buffer.add("Firefox: Not found - please install Firefox", "ERROR")

        available, path = check_geckodriver_available()
        if available:
            self.log_buffer.add(f"Geckodriver: Found ({path})", "SUCCESS")
        else:
            self.log_buffer.add(f"Geckodriver: {path}", "WARNING")

        profile = find_firefox_profile()
        if profile:
            self.log_buffer.add("Firefox Profile: Found", "SUCCESS")
        else:
            self.log_buffer.add("Firefox Profile: Not found - certificate auth may fail", "WARNING")

        self.log_buffer.add("Ready to start automation", "INFO")

    # ------------------------------------------------------------------
    # Automation Control
    # ------------------------------------------------------------------

    def _start_automation(self):
        """Start the automation (called after pre-flight confirmation)."""
        if self.is_running:
            return

        config = self.config_panel.get_config()
        workflow = config["workflow"]
        domain = self.sidebar.get_domain()
        comment = config["comment"]
        specific_users = config["specific_users"]

        # Validate specific users
        if workflow == "1" and config["mode"] == "specific" and not specific_users:
            messagebox.showerror("Error", "Please enter at least one username")
            return

        # Confirm batch reject
        batch_reject = config["batch_reject"]
        if batch_reject:
            confirm = messagebox.askyesno(
                "Confirm Batch Reject",
                "WARNING: BATCH REJECTION\n\n"
                "You are about to REJECT all specified users.\n"
                "This action cannot be undone.\n\n"
                "Are you sure you want to continue?",
                icon="warning",
            )
            if not confirm:
                return

        # Reset state
        self.cancel_event.clear()
        self.log_buffer.clear()
        self.progress_tracker.reset()
        self.is_running = True
        self._run_domains_processed = []

        # Disable sidebar
        self.sidebar.set_disabled(True)

        # Switch to running view
        self._show_running_view()
        self.progress_panel.load_gif_frames()
        self.progress_panel.start_animation(workflow)
        self.progress_panel.start_elapsed_timer()

        # Setup domain tracker
        use_counterpart = config["counterpart"]
        if workflow in ("1", "2") and use_counterpart:
            self.progress_panel.setup_domain_tracker(domain)
        elif workflow == "3" and not config["all_domains"] and use_counterpart:
            self.progress_panel.setup_domain_tracker(domain)

        # Bot setup
        auth_method = get_auth_method()
        if self.bot is None:
            self.bot = GovCAApprovalBot(
                log_callback=self.log_buffer.get_callback(),
                progress_callback=self.progress_tracker.get_callback(),
                cancel_event=self.cancel_event,
                auth_method=auth_method,
            )
        else:
            self.bot.update_callbacks(
                log_callback=self.log_buffer.get_callback(),
                progress_callback=self.progress_tracker.get_callback(),
                cancel_event=self.cancel_event,
                auth_method=auth_method,
            )

        bot = self.bot

        def run_automation():
            try:
                if workflow == "1":
                    if batch_reject:
                        bot.run_rejection_process(
                            domain=domain, comment=comment,
                            process_counterpart=use_counterpart,
                            specific_users=specific_users,
                        )
                    else:
                        bot.run_approval_process(
                            domain=domain, comment=comment,
                            process_counterpart=use_counterpart,
                            specific_users=specific_users,
                        )
                elif workflow == "2":
                    bot.run_revoke_certificate_approval(
                        domain=domain, comment=comment,
                        process_counterpart=use_counterpart,
                    )
                elif workflow == "3":
                    if config["all_domains"]:
                        bot.run_assign_user_groups_all_domains()
                    else:
                        bot.run_assign_user_group(domain=domain)
                        if use_counterpart:
                            cp = bot.get_counterpart_domain(domain)
                            if cp:
                                bot.run_assign_user_group(domain=cp)
            except OperationCancelledException:
                self.log_buffer.add("Operation cancelled by user", "WARNING")
            except Exception as e:
                if self.cancel_event.is_set():
                    self.log_buffer.add("Operation cancelled by user", "WARNING")
                else:
                    self.log_buffer.add(f"Error: {e}", "ERROR")

        workflow_names = {
            "1": "Add User (Batch Reject)" if batch_reject else "Add User (Batch Approve)",
            "2": "Revoke Cert",
            "3": "Assign Group - All Domains" if config["all_domains"] else "Assign Group (Single)",
        }
        self._current_workflow_name = workflow_names.get(workflow, "Unknown")

        self.automation_thread = threading.Thread(target=run_automation, daemon=True)
        self.automation_thread.start()

        self.log_buffer.add(f"Started: {self._current_workflow_name}", "INFO")

    def _stop_automation(self):
        if not self.is_running:
            return
        self.log_buffer.add("Stopping automation...", "WARNING")
        self.cancel_event.set()
        self.progress_panel.status_label.configure(text="Stopping...")
        self._cancel_escalation_timers()
        self._escalate_timer_id = self.after(5000, self._escalate_stop)

    def _escalate_stop(self):
        self._escalate_timer_id = None
        if self.automation_thread and self.automation_thread.is_alive():
            self.log_buffer.add("Force-quitting browser...", "WARNING")
            if self.bot and self.bot.driver:
                try:
                    self.bot.driver.quit()
                except Exception:
                    pass
                self.bot.driver = None
            self._finalize_timer_id = self.after(5000, self._finalize_stop)
        elif self.is_running:
            self._finalize_stop()

    def _finalize_stop(self):
        self._finalize_timer_id = None
        if self.is_running:
            self.log_buffer.add("Force-resetting UI state", "WARNING")
            self.is_running = False
            self.automation_thread = None
            self.sidebar.set_disabled(False)
            self.progress_panel.stop_animation()
            self.progress_panel.stop_elapsed_timer()
            elapsed = self.progress_panel.get_elapsed_seconds()
            self._show_completion_view(
                success=False,
                total_processed=self.progress_panel.total_processed,
                errors=self.progress_panel.errors + 1,
                elapsed_seconds=elapsed,
            )
            self._notify_user(success=False)
            self._update_session_status()

    def _cancel_escalation_timers(self):
        if self._escalate_timer_id is not None:
            self.after_cancel(self._escalate_timer_id)
            self._escalate_timer_id = None
        if self._finalize_timer_id is not None:
            self.after_cancel(self._finalize_timer_id)
            self._finalize_timer_id = None

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def _poll_updates(self):
        try:
            # Poll log messages
            new_messages = self.log_buffer.poll()
            if self._content_state == self.STATE_RUNNING:
                for msg in new_messages:
                    self.progress_panel.append_log(msg.message, msg.level)

            # Poll progress
            data = self.progress_tracker.poll()
            current = data["current"]
            total = data["total"]
            if data["changed"] and self._content_state == self.STATE_RUNNING:
                self.progress_panel.update_progress(
                    current, total, data["message"],
                    data["phase"], data["total_phases"], data["phase_label"],
                )

            # Check if thread finished
            if self.automation_thread and not self.automation_thread.is_alive():
                self._cancel_escalation_timers()
                was_running = self.is_running
                self.is_running = False
                self.automation_thread = None

                if was_running:
                    self.sidebar.set_disabled(False)
                    self.progress_panel.stop_animation()
                    self.progress_panel.stop_elapsed_timer()
                    elapsed = self.progress_panel.get_elapsed_seconds()

                    has_errors = self.progress_panel.errors > 0
                    cancelled = self.cancel_event.is_set()

                    # Complete domain tracker
                    if self.progress_panel._domain_tracker_visible:
                        if not has_errors and not cancelled:
                            self.progress_panel.complete_domain_tracker()
                        else:
                            self.progress_panel.hide_domain_tracker()

                    success = not has_errors and not cancelled
                    self._show_completion_view(
                        success=success,
                        total_processed=current,
                        errors=self.progress_panel.errors,
                        elapsed_seconds=elapsed,
                    )
                    self._notify_user(success=success, processed_count=current)
                    self._update_session_status()

            # Periodic session check
            if not hasattr(self, "_session_check_counter"):
                self._session_check_counter = 0
            self._session_check_counter += 1
            if self._session_check_counter >= 50:
                self._session_check_counter = 0
                if not self.is_running:
                    self._update_session_status()

        except Exception:
            pass

        self.after(100, self._poll_updates)

    # ------------------------------------------------------------------
    # Session Management
    # ------------------------------------------------------------------

    def _update_session_status(self):
        active = self.bot is not None and self.bot.is_session_valid()
        self.sidebar.update_session_status(active)

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def _notify_user(self, success=True, processed_count=0):
        try:
            wf_name = self._current_workflow_name or "Workflow"
            if success:
                msg = (f"{wf_name} — Processed {processed_count} item(s)"
                       if processed_count > 0
                       else f"{wf_name} completed successfully!")
            else:
                msg = f"{wf_name} finished with errors."

            if sys.platform == "darwin":
                title = "PNPKI Approval Automation"
                if getattr(sys, "frozen", False):
                    script = (
                        'tell application id "com.govca.approval"\n'
                        f'  display notification "{msg}" with title "{title}" sound name "default"\n'
                        "end tell"
                    )
                else:
                    script = f'display notification "{msg}" with title "{title}" sound name "default"'
                subprocess.Popen(
                    ["osascript", "-e", script],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            elif sys.platform == "win32":
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
                    creationflags=0x08000000,
                )
                try:
                    import ctypes
                    ctypes.windll.user32.FlashWindow(
                        ctypes.windll.kernel32.GetConsoleWindow(), True
                    )
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self.bell()
        except Exception:
            pass
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.after(1000, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Window Close
    # ------------------------------------------------------------------

    def on_closing(self):
        if self.is_running:
            if messagebox.askyesno("Confirm Exit",
                                   "Automation is running. Are you sure you want to exit?"):
                self.cancel_event.set()
                if self.bot:
                    try:
                        self.bot.close_browser()
                    except Exception:
                        pass
                self.destroy()
        else:
            if self.bot:
                try:
                    self.bot.close_browser()
                except Exception:
                    pass
            self.destroy()


def main():
    """Application entry point"""
    app = GovCAApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()


if __name__ == "__main__":
    main()
