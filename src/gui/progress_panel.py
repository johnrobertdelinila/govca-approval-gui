"""
Progress Panel - Shown during automation runs.
Contains progress bar, GIF animation + live log split, elapsed timer, domain tracker.
"""

import os
import sys
import time
import random
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

from .design_system import ColorPalette, Typography, Spacing, Radius
from .components import CardFrame, AnimatedProgressBar

try:
    from ..utils.resources import get_gif_path
except ImportError:
    from utils.resources import get_gif_path


# Workflow-aware animation messages
_WORKFLOW_MESSAGES = {
    "shared": [
        "Doing the thing...",
        "Hold my coffee...",
        "Trust the process.",
        "You could grab a snack.",
        "Working faster than you think.",
        "This is the fun part, right?",
        "Patience is a virtue, they say.",
        "Still at it. No complaints.",
        "Just vibes and automation.",
        "Let the bot cook.",
    ],
    "1": [
        "Onboarding humans at scale.",
        "Stamping approvals like a boss.",
        "New users incoming!",
        "Approve, approve, approve...",
        "Making accounts happen.",
        "Rolling out the welcome mat.",
        "Batch mode: engaged.",
    ],
    "2": [
        "Revoking with care.",
        "Cleaning up certificates...",
        "One cert at a time.",
        "Saying goodbye to old certs.",
        "Revocation station.",
    ],
    "3": [
        "Sorting users into groups.",
        "Group therapy in progress.",
        "Organizing the roster.",
        "Assigning seats at the table.",
        "Building the dream team.",
    ],
}


class FullLogsDialog(ctk.CTkToplevel):
    """Popup dialog showing the full log history."""

    def __init__(self, parent, log_messages):
        super().__init__(parent)
        self.withdraw()
        self.title("Full Logs")
        self.geometry("800x500")
        self.transient(parent)

        log_text = ctk.CTkTextbox(
            self,
            font=Typography.mono(12),
            wrap="word",
            corner_radius=0,
            fg_color=ColorPalette.get("bg_input"),
        )
        log_text.pack(fill="both", expand=True)

        colors = _get_log_colors()
        for level, color in colors.items():
            log_text._textbox.tag_configure(level, foreground=color)

        for msg in log_messages:
            log_text._textbox.insert("end", f"{msg.formatted}\n", msg.level)

        log_text.configure(state="disabled")
        log_text.see("end")

        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - 800) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - 500) // 2
        self.geometry(f"+{px}+{py}")
        self.deiconify()
        self.grab_set()


def _get_log_colors():
    if ctk.get_appearance_mode() == "Light":
        return {
            "INFO": "#374151",
            "SUCCESS": "#059669",
            "WARNING": "#d97706",
            "ERROR": "#dc2626",
        }
    return {
        "INFO": "#e5e7eb",
        "SUCCESS": "#34d399",
        "WARNING": "#fbbf24",
        "ERROR": "#f87171",
    }


class ProgressPanel(ctk.CTkFrame):
    """Panel shown during automation with progress, GIF + live logs, domain tracker."""

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)

        self._animation_running = False
        self._animation_frame_index = 0
        self._animation_after_id = None
        self._gif_frames = []
        self._gif_duration = 50
        self._gif_target_size = (260, 163)
        self._elapsed_start = None
        self._elapsed_timer_id = None
        self._current_workflow = "1"

        # Domain tracker state
        self._domain_tracker_visible = False
        self._domain_tracker_domains = []
        self._domain_tracker_statuses = {}
        self._spinner_animation_id = None
        self._spinner_frame_index = 0

        # Metrics
        self.total_processed = 0
        self.errors = 0

        self._build()

    def _build(self):
        # === Progress Card ===
        self.progress_card = CardFrame(self, hover_glow=False)
        self.progress_card.pack(fill="x", padx=Spacing.PAGE_PAD, pady=(Spacing.SECTION, Spacing.MD))

        progress_inner = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        progress_inner.pack(fill="x", padx=Spacing.CARD_PAD, pady=Spacing.MD)

        # Domain tracker frame (shown during counterpart processing)
        self.domain_tracker_frame = ctk.CTkFrame(progress_inner, fg_color="transparent")

        self.domain1_icon = ctk.CTkLabel(
            self.domain_tracker_frame, text="\u25cb",
            font=ctk.CTkFont(size=14),
            text_color=ColorPalette.get("text_muted"), width=20,
        )
        self.domain1_icon.pack(side="left", padx=(0, 2))
        self.domain1_name = ctk.CTkLabel(
            self.domain_tracker_frame, text="",
            font=Typography.body_sm(),
            text_color=ColorPalette.get("text_secondary"),
        )
        self.domain1_name.pack(side="left", padx=(0, Spacing.LG))

        self.domain2_icon = ctk.CTkLabel(
            self.domain_tracker_frame, text="\u25cb",
            font=ctk.CTkFont(size=14),
            text_color=ColorPalette.get("text_muted"), width=20,
        )
        self.domain2_icon.pack(side="left", padx=(0, 2))
        self.domain2_name = ctk.CTkLabel(
            self.domain_tracker_frame, text="",
            font=Typography.body_sm(),
            text_color=ColorPalette.get("text_secondary"),
        )
        self.domain2_name.pack(side="left")

        # Phase label (for multi-domain without tracker)
        self.phase_label = ctk.CTkLabel(
            progress_inner, text="",
            font=Typography.body_sm(),
            text_color=ColorPalette.get("accent_primary"),
        )

        # Progress bar — sleek 6px height
        self.progress_bar = AnimatedProgressBar(
            progress_inner,
            height=6,
            corner_radius=3,
            progress_color=ColorPalette.get("accent_primary"),
            fg_color=ColorPalette.get("bg_overlay"),
        )
        self.progress_bar.pack(fill="x", pady=(Spacing.XS, Spacing.SM))
        self.progress_bar.set(0)

        # Stats row
        stats_row = ctk.CTkFrame(progress_inner, fg_color="transparent")
        stats_row.pack(fill="x")

        self.percentage_label = ctk.CTkLabel(
            stats_row, text="0%",
            font=Typography.heading_sm(),
            text_color=ColorPalette.get("accent_primary"),
        )
        self.percentage_label.pack(side="left")

        self.status_label = ctk.CTkLabel(
            stats_row, text="Starting...",
            font=Typography.body_md(),
            text_color=ColorPalette.get("text_secondary"),
        )
        self.status_label.pack(side="left", padx=(Spacing.MD, 0))

        self.elapsed_label = ctk.CTkLabel(
            stats_row, text="0m 0s",
            font=Typography.body_sm(),
            text_color=ColorPalette.get("text_muted"),
        )
        self.elapsed_label.pack(side="right")

        # === STOP button — ghost danger style ===
        stop_frame = ctk.CTkFrame(self, fg_color="transparent")
        stop_frame.pack(fill="x", padx=Spacing.PAGE_PAD, pady=(0, Spacing.MD))

        self.stop_button = ctk.CTkButton(
            stop_frame,
            text="STOP",
            width=140,
            height=36,
            font=Typography.heading_sm(),
            fg_color="transparent",
            hover_color="#f25d5d20",
            border_width=1,
            border_color=ColorPalette.get("accent_error"),
            text_color=ColorPalette.get("accent_error"),
            corner_radius=Radius.LG,
        )
        self.stop_button.pack(side="left")

        # === Animation + Log Split (fills remaining space) ===
        split_frame = ctk.CTkFrame(self, fg_color="transparent")
        split_frame.pack(fill="both", expand=True, padx=Spacing.PAGE_PAD, pady=(0, Spacing.LG))

        # Left: GIF animation
        self.anim_card = CardFrame(split_frame, hover_glow=False, width=280)
        self.anim_card.pack(side="left", fill="y", padx=(0, Spacing.MD))
        self.anim_card.pack_propagate(False)

        anim_inner = ctk.CTkFrame(self.anim_card, fg_color="transparent")
        anim_inner.pack(fill="both", expand=True)

        self.gif_label = tk.Label(
            anim_inner,
            bg=ColorPalette.get("bg_card"),
            bd=0,
            highlightthickness=0,
        )
        self.gif_label.pack(expand=True, pady=(Spacing.SM, Spacing.XS))

        self.message_label = ctk.CTkLabel(
            anim_inner,
            text="",
            font=Typography.body_md(),
            text_color=ColorPalette.get("text_muted"),
        )
        self.message_label.pack(pady=(Spacing.XS, Spacing.MD))

        # Right: Live log feed
        self.log_card = CardFrame(split_frame, hover_glow=False)
        self.log_card.pack(side="left", fill="both", expand=True)

        log_header = ctk.CTkFrame(self.log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=Spacing.MD, pady=(Spacing.SM, 0))

        ctk.CTkLabel(
            log_header, text="LIVE LOG",
            font=Typography.caption(),
            text_color=ColorPalette.get("text_muted"),
        ).pack(side="left")

        self.view_full_btn = ctk.CTkButton(
            log_header,
            text="View Full Logs",
            width=100,
            height=24,
            font=Typography.body_sm(),
            fg_color="transparent",
            hover_color=ColorPalette.get("border"),
            border_width=1,
            border_color=ColorPalette.get("border"),
            text_color=ColorPalette.get("text_secondary"),
            corner_radius=Radius.SM,
        )
        self.view_full_btn.pack(side="right")

        # Thin separator
        ctk.CTkFrame(
            self.log_card, height=1,
            fg_color=ColorPalette.get("border"),
        ).pack(fill="x", padx=Spacing.SM, pady=(Spacing.XS, 0))

        self.log_text = ctk.CTkTextbox(
            self.log_card,
            font=Typography.mono(10),
            wrap="word",
            corner_radius=0,
            border_width=0,
            fg_color=ColorPalette.get("bg_input"),
        )
        self.log_text.pack(fill="both", expand=True, padx=Spacing.SM, pady=(0, Spacing.SM))
        self.log_text.configure(state="disabled")

        # Configure log colors
        self._update_log_colors()

    # ------------------------------------------------------------------
    # GIF Animation
    # ------------------------------------------------------------------

    def load_gif_frames(self):
        """Load GIF frames from disk."""
        try:
            gif_path = get_gif_path()
            if not os.path.exists(gif_path):
                self._show_gif_placeholder("Animation not available")
                return

            gif = Image.open(gif_path)
            self._gif_frames = []
            try:
                self._gif_duration = gif.info.get("duration", 50)
            except Exception:
                self._gif_duration = 50

            try:
                while True:
                    frame = gif.copy()
                    if frame.mode != "RGBA":
                        frame = frame.convert("RGBA")
                    frame = frame.resize(self._gif_target_size, Image.Resampling.LANCZOS)
                    self._gif_frames.append(ImageTk.PhotoImage(frame))
                    gif.seek(gif.tell() + 1)
            except EOFError:
                pass

            if self._gif_frames:
                self.gif_label.configure(image=self._gif_frames[0])
                self.gif_label.configure(bg=ColorPalette.get("bg_card"))
        except Exception:
            self._gif_frames = []
            self._show_gif_placeholder("Animation unavailable")

    def _show_gif_placeholder(self, text):
        self._gif_frames = []
        self.gif_label.pack_forget()
        self.message_label.configure(text=text)

    def start_animation(self, workflow_id="1"):
        """Begin GIF playback."""
        self._current_workflow = workflow_id
        if self._animation_running:
            return
        if not self._gif_frames:
            return
        self._animation_running = True
        self._animation_frame_index = 0
        # Fix GIF label background for current theme
        self.gif_label.configure(bg=ColorPalette.get("bg_card"))
        self.gif_label.pack(expand=True, pady=(Spacing.SM, Spacing.XS))
        self._animate_gif()

    def stop_animation(self):
        self._animation_running = False
        if self._animation_after_id:
            self.after_cancel(self._animation_after_id)
            self._animation_after_id = None

    def _animate_gif(self):
        if not self._animation_running or not self._gif_frames:
            return
        frame = self._gif_frames[self._animation_frame_index]
        self.gif_label.configure(image=frame)

        if self._animation_frame_index % 10 == 0:
            wf = self._current_workflow
            pool = _WORKFLOW_MESSAGES["shared"] + _WORKFLOW_MESSAGES.get(wf, [])
            self.message_label.configure(text=random.choice(pool))

        self._animation_frame_index = (self._animation_frame_index + 1) % len(self._gif_frames)
        self._animation_after_id = self.after(self._gif_duration, self._animate_gif)

    # ------------------------------------------------------------------
    # Elapsed Timer
    # ------------------------------------------------------------------

    def start_elapsed_timer(self):
        self._elapsed_start = time.time()
        self._tick_elapsed()

    def stop_elapsed_timer(self):
        if self._elapsed_timer_id:
            self.after_cancel(self._elapsed_timer_id)
            self._elapsed_timer_id = None

    def get_elapsed_seconds(self):
        if self._elapsed_start is None:
            return 0
        return int(time.time() - self._elapsed_start)

    def _tick_elapsed(self):
        if self._elapsed_start is None:
            return
        elapsed = int(time.time() - self._elapsed_start)
        m, s = divmod(elapsed, 60)
        self.elapsed_label.configure(text=f"{m}m {s}s")
        self._elapsed_timer_id = self.after(1000, self._tick_elapsed)

    # ------------------------------------------------------------------
    # Progress updates
    # ------------------------------------------------------------------

    def update_progress(self, current, total, message="",
                        phase=None, total_phases=None, phase_label=None):
        """Update progress bar and status from polled data."""
        self.total_processed = current

        # Domain tracker
        if self._domain_tracker_visible:
            self._update_domain_tracker(phase, total_phases, phase_label)
        else:
            if total_phases and total_phases > 1 and phase_label:
                self.phase_label.configure(text=f"Phase {phase}/{total_phases}: {phase_label}")
                self.phase_label.pack(anchor="w", pady=(0, Spacing.XS))
            elif phase_label:
                self.phase_label.configure(text=phase_label)
                self.phase_label.pack(anchor="w", pady=(0, Spacing.XS))
            else:
                self.phase_label.pack_forget()

        if total > 0:
            progress = current / total
            self.progress_bar.set_animated(progress)
            pct = int(progress * 100)
            self.percentage_label.configure(text=f"{pct}%")
            self.status_label.configure(text=f"{message} ({current}/{total})")
        elif total < 0:
            self.progress_bar.set_animated(0.5)
            self.percentage_label.configure(text="...")
            self.status_label.configure(text=message or "Processing...")
        else:
            self.progress_bar.set_animated(0)
            self.percentage_label.configure(text="0%")
            self.status_label.configure(text=message or "Ready")

    def append_log(self, message, level="INFO"):
        """Append a log line to the live log feed."""
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"[{ts}] {message}\n"
        self.log_text.configure(state="normal")
        self.log_text._textbox.insert("end", formatted, level)
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

        if level == "ERROR":
            self.errors += 1

    # ------------------------------------------------------------------
    # Domain Tracker
    # ------------------------------------------------------------------

    def setup_domain_tracker(self, primary_domain):
        counterpart = self._compute_counterpart(primary_domain)
        if not counterpart:
            return
        self._domain_tracker_domains = [primary_domain, counterpart]
        self._domain_tracker_statuses = {
            primary_domain: "processing",
            counterpart: "pending",
        }
        self._domain_tracker_visible = True
        self.domain1_name.configure(text=primary_domain)
        self.domain2_name.configure(text=counterpart)
        self._update_domain_icon(self.domain1_icon, "processing")
        self._update_domain_icon(self.domain2_icon, "pending")
        self.phase_label.pack_forget()
        self.domain_tracker_frame.pack(anchor="w", pady=(0, Spacing.XS))
        self._start_domain_spinner()

    def _compute_counterpart(self, domain):
        if "Sign" in domain:
            return domain.replace("Sign", "Auth")
        elif "Auth" in domain:
            return domain.replace("Auth", "Sign")
        return None

    def _update_domain_icon(self, icon_label, status):
        if status == "pending":
            icon_label.configure(text="\u25cb", text_color=ColorPalette.get("text_muted"))
        elif status == "processing":
            icon_label.configure(text="\u25d0", text_color=ColorPalette.get("accent_primary"))
        elif status == "completed":
            icon_label.configure(text="\u2713", text_color=ColorPalette.get("accent_success"))

    def _start_domain_spinner(self):
        self._spinner_frame_index = 0
        self._tick_domain_spinner()

    def _tick_domain_spinner(self):
        spinner_chars = ["\u25d0", "\u25d3", "\u25d1", "\u25d2"]
        self._spinner_frame_index = (self._spinner_frame_index + 1) % len(spinner_chars)
        char = spinner_chars[self._spinner_frame_index]
        for i, domain in enumerate(self._domain_tracker_domains):
            if self._domain_tracker_statuses.get(domain) == "processing":
                icon = self.domain1_icon if i == 0 else self.domain2_icon
                icon.configure(text=char)
        self._spinner_animation_id = self.after(150, self._tick_domain_spinner)

    def _stop_domain_spinner(self):
        if self._spinner_animation_id is not None:
            self.after_cancel(self._spinner_animation_id)
            self._spinner_animation_id = None

    def _update_domain_tracker(self, phase, total_phases, phase_label):
        if not self._domain_tracker_domains:
            return
        domain1, domain2 = self._domain_tracker_domains
        if phase_label == domain2 and self._domain_tracker_statuses[domain2] != "processing":
            self._domain_tracker_statuses[domain1] = "completed"
            self._domain_tracker_statuses[domain2] = "processing"
            self._update_domain_icon(self.domain1_icon, "completed")
            self._update_domain_icon(self.domain2_icon, "processing")
        elif phase_label == domain1 and self._domain_tracker_statuses[domain1] != "processing":
            self._domain_tracker_statuses[domain1] = "processing"
            self._update_domain_icon(self.domain1_icon, "processing")

    def complete_domain_tracker(self):
        self._stop_domain_spinner()
        for i, domain in enumerate(self._domain_tracker_domains):
            self._domain_tracker_statuses[domain] = "completed"
            icon = self.domain1_icon if i == 0 else self.domain2_icon
            self._update_domain_icon(icon, "completed")

    def hide_domain_tracker(self):
        self._stop_domain_spinner()
        self._domain_tracker_visible = False
        self._domain_tracker_domains = []
        self._domain_tracker_statuses = {}
        self.domain_tracker_frame.pack_forget()

    # ------------------------------------------------------------------
    # Theme update
    # ------------------------------------------------------------------

    def update_colors(self):
        """Refresh all custom colors on theme change."""
        # Progress card
        self.progress_card.update_colors()
        self.progress_bar.configure(
            progress_color=ColorPalette.get("accent_primary"),
            fg_color=ColorPalette.get("bg_overlay"),
        )
        self.percentage_label.configure(text_color=ColorPalette.get("accent_primary"))
        self.status_label.configure(text_color=ColorPalette.get("text_secondary"))
        self.elapsed_label.configure(text_color=ColorPalette.get("text_muted"))
        self.phase_label.configure(text_color=ColorPalette.get("accent_primary"))
        self.message_label.configure(text_color=ColorPalette.get("text_muted"))

        # Animation and log cards
        self.anim_card.update_colors()
        self.log_card.update_colors()
        self.gif_label.configure(bg=ColorPalette.get("bg_card"))
        self.log_text.configure(fg_color=ColorPalette.get("bg_input"))
        self.view_full_btn.configure(
            hover_color=ColorPalette.get("border"),
            border_color=ColorPalette.get("border"),
            text_color=ColorPalette.get("text_secondary"),
        )

        # Stop button
        self.stop_button.configure(
            border_color=ColorPalette.get("accent_error"),
            text_color=ColorPalette.get("accent_error"),
        )

        self._update_log_colors()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def reset(self):
        """Reset panel for a new run."""
        self.stop_animation()
        self.stop_elapsed_timer()
        self.hide_domain_tracker()
        self.progress_bar.set(0)
        self.percentage_label.configure(text="0%")
        self.status_label.configure(text="Starting...")
        self.elapsed_label.configure(text="0m 0s")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.phase_label.pack_forget()
        self.message_label.configure(text="")
        self.total_processed = 0
        self.errors = 0

    def _update_log_colors(self):
        colors = _get_log_colors()
        for level, color in colors.items():
            self.log_text._textbox.tag_configure(level, foreground=color)
