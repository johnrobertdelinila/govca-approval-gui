"""
Configuration Panel - Workflow-specific configuration forms.
Shows in the content area when the app is idle (config state).
"""

import customtkinter as ctk

from .design_system import ColorPalette, Typography, Spacing, Radius
from .components import CardFrame


class ConfigPanel(ctk.CTkFrame):
    """Content panel showing workflow configuration and START button.

    Call ``set_workflow(workflow_id)`` to rebuild the form for a specific workflow.
    """

    def __init__(self, parent, on_start=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)

        self._on_start = on_start
        self._current_workflow = "1"

        # Shared state variables
        self.counterpart_var = ctk.BooleanVar(value=True)
        self.all_domains_var = ctk.BooleanVar(value=False)
        self.mode_var = ctk.StringVar(value="specific")
        self.batch_reject_var = ctk.BooleanVar(value=False)

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        """Build the full panel layout."""
        # === Header: workflow title + domain badge ===
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=Spacing.PAGE_PAD, pady=(Spacing.SECTION, Spacing.LG))

        self.workflow_title = ctk.CTkLabel(
            header,
            text="Add User",
            font=Typography.workflow_title(),
            text_color=ColorPalette.get("text_primary"),
        )
        self.workflow_title.pack(side="left")

        self.domain_badge = ctk.CTkLabel(
            header,
            text="",
            font=Typography.badge(),
            text_color=ColorPalette.get("badge_text"),
            fg_color=ColorPalette.get("badge_bg"),
            corner_radius=Radius.PILL,
            padx=10,
            pady=2,
        )
        self.domain_badge.pack(side="left", padx=(Spacing.MD, 0))

        self.workflow_subtitle = ctk.CTkLabel(
            self,
            text="Batch approve pending users",
            font=Typography.body_md(),
            text_color=ColorPalette.get("text_muted"),
        )
        self.workflow_subtitle.pack(anchor="w", padx=Spacing.PAGE_PAD, pady=(0, Spacing.LG))

        # === Configuration Card ===
        self.config_card = CardFrame(self, hover_glow=False)
        self.config_card.pack(fill="x", padx=Spacing.PAGE_PAD, pady=(0, Spacing.LG))

        self.config_inner = ctk.CTkFrame(self.config_card, fg_color="transparent")
        self.config_inner.pack(fill="x", padx=Spacing.SECTION, pady=Spacing.CARD_PAD)

        # -- Comment row (workflow 1 & 2) --
        self.comment_frame = ctk.CTkFrame(self.config_inner, fg_color="transparent")

        self.comment_label = ctk.CTkLabel(
            self.comment_frame,
            text="Comment",
            font=Typography.section_header(),
            text_color=ColorPalette.get("text_muted"),
        )
        self.comment_label.pack(anchor="w", pady=(0, Spacing.XS))

        self.comment_entry = ctk.CTkEntry(
            self.comment_frame,
            height=36,
            font=Typography.body_md(),
            corner_radius=Radius.SM,
            border_width=1,
            border_color=ColorPalette.get("border"),
            placeholder_text="Approved via automation",
        )
        self.comment_entry.pack(fill="x")
        self.comment_entry.insert(0, "Approved via automation")

        # Focus ring
        self.comment_entry.bind("<FocusIn>", lambda e: self.comment_entry.configure(
            border_color=ColorPalette.get("accent_primary")))
        self.comment_entry.bind("<FocusOut>", lambda e: self.comment_entry.configure(
            border_color=ColorPalette.get("border")))

        # -- Mode radio (workflow 1) --
        self.mode_frame = ctk.CTkFrame(self.config_inner, fg_color="transparent")

        self.mode_label = ctk.CTkLabel(
            self.mode_frame,
            text="Mode",
            font=Typography.section_header(),
            text_color=ColorPalette.get("text_muted"),
        )
        self.mode_label.pack(anchor="w", pady=(0, Spacing.XS))

        mode_row = ctk.CTkFrame(self.mode_frame, fg_color="transparent")
        mode_row.pack(fill="x")

        self.radio_all = ctk.CTkRadioButton(
            mode_row,
            text="All pending users",
            variable=self.mode_var,
            value="all",
            font=Typography.body_md(),
            fg_color=ColorPalette.get("accent_primary"),
            hover_color=ColorPalette.get("accent_secondary"),
            text_color=ColorPalette.get("text_primary"),
            command=self._on_mode_change,
        )
        self.radio_all.pack(side="left", padx=(0, Spacing.SECTION))

        self.radio_specific = ctk.CTkRadioButton(
            mode_row,
            text="Specific users only",
            variable=self.mode_var,
            value="specific",
            font=Typography.body_md(),
            fg_color=ColorPalette.get("accent_primary"),
            hover_color=ColorPalette.get("accent_secondary"),
            text_color=ColorPalette.get("text_primary"),
            command=self._on_mode_change,
        )
        self.radio_specific.pack(side="left")

        # -- Usernames textbox (workflow 1 specific mode) --
        self.usernames_frame = ctk.CTkFrame(self.config_inner, fg_color="transparent")

        self.usernames_label = ctk.CTkLabel(
            self.usernames_frame,
            text="Usernames (one per line, without suffix)",
            font=Typography.section_header(),
            text_color=ColorPalette.get("text_muted"),
        )
        self.usernames_label.pack(anchor="w", pady=(0, Spacing.XS))

        text_row = ctk.CTkFrame(self.usernames_frame, fg_color="transparent")
        text_row.pack(fill="x")

        self.usernames_text = ctk.CTkTextbox(
            text_row,
            height=70,
            font=Typography.mono(12),
            corner_radius=Radius.SM,
            border_width=1,
            border_color=ColorPalette.get("border"),
            fg_color=ColorPalette.get("bg_input"),
        )
        self.usernames_text.pack(side="left", fill="x", expand=True)

        self.usernames_text.bind("<KeyRelease>", self._update_username_count)
        self.usernames_text.bind("<<Paste>>", lambda e: self.after(10, self._update_username_count))

        self.clear_btn = ctk.CTkButton(
            text_row,
            text="\u2715",
            width=28,
            height=28,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color=ColorPalette.get("border"),
            border_width=1,
            border_color=ColorPalette.get("border"),
            text_color=ColorPalette.get("text_secondary"),
            corner_radius=Radius.SM,
            command=self._clear_usernames,
        )
        self.clear_btn.pack(side="left", padx=(Spacing.SM, 0))

        self.username_count_label = ctk.CTkLabel(
            self.usernames_frame,
            text="0 users entered",
            font=Typography.body_sm(),
            text_color=ColorPalette.get("text_muted"),
        )
        self.username_count_label.pack(anchor="w", pady=(Spacing.XS, 0))

        # -- Batch reject checkbox (workflow 1 specific mode) --
        self.batch_reject_frame = ctk.CTkFrame(self.config_inner, fg_color="transparent")

        self.batch_reject_checkbox = ctk.CTkCheckBox(
            self.batch_reject_frame,
            text="Batch Reject",
            variable=self.batch_reject_var,
            font=Typography.body_md(),
            checkbox_width=20,
            checkbox_height=20,
            corner_radius=4,
            border_width=2,
            fg_color=ColorPalette.get("accent_error"),
            hover_color="#dc2626",
            text_color=ColorPalette.get("text_primary"),
            command=self._on_batch_reject_toggle,
        )
        self.batch_reject_checkbox.pack(side="left")

        self.batch_reject_warning = ctk.CTkLabel(
            self.batch_reject_frame,
            text="WARNING: This will REJECT all specified users!",
            font=Typography.body_sm(),
            text_color="#FF6B6B",
        )

        # -- Counterpart checkbox (workflow 1, 2, 3-single) --
        self.counterpart_frame = ctk.CTkFrame(self.config_inner, fg_color="transparent")

        self.counterpart_check = ctk.CTkCheckBox(
            self.counterpart_frame,
            text="Process counterpart domain (Sign/Auth)",
            variable=self.counterpart_var,
            font=Typography.body_md(),
            checkbox_width=20,
            checkbox_height=20,
            corner_radius=4,
            border_width=2,
            fg_color=ColorPalette.get("accent_primary"),
            hover_color=ColorPalette.get("accent_secondary"),
            text_color=ColorPalette.get("text_primary"),
        )
        self.counterpart_check.pack(side="left")

        # -- All domains toggle (workflow 3) --
        self.all_domains_frame = ctk.CTkFrame(self.config_inner, fg_color="transparent")

        self.all_domains_switch = ctk.CTkSwitch(
            self.all_domains_frame,
            text="Process ALL domains automatically",
            variable=self.all_domains_var,
            font=Typography.body_md(),
            progress_color=ColorPalette.get("accent_primary"),
            button_color=ColorPalette.get("text_primary"),
            button_hover_color=ColorPalette.get("text_secondary"),
            command=self._on_all_domains_toggle,
        )
        self.all_domains_switch.pack(side="left")

        # === Pre-flight card (hidden until START is clicked) ===
        self.preflight_card = CardFrame(
            self, hover_glow=False,
            border_color=ColorPalette.get("accent_primary"),
            fg_color=ColorPalette.get("bg_sidebar_item_active"),  # Tinted background
        )
        # Not packed initially

        self.preflight_inner = ctk.CTkFrame(self.preflight_card, fg_color="transparent")
        self.preflight_inner.pack(fill="x", padx=Spacing.SECTION, pady=Spacing.CARD_PAD)

        # Pre-flight header with icon
        preflight_header = ctk.CTkFrame(self.preflight_inner, fg_color="transparent")
        preflight_header.pack(anchor="w", pady=(0, Spacing.SM))

        self.preflight_icon_label = ctk.CTkLabel(
            preflight_header,
            text="\u2611",
            font=ctk.CTkFont(size=14),
            text_color=ColorPalette.get("accent_primary"),
        )
        self.preflight_icon_label.pack(side="left", padx=(0, Spacing.SM))

        self.preflight_header_label = ctk.CTkLabel(
            preflight_header,
            text="PRE-FLIGHT SUMMARY",
            font=Typography.section_header(),
            text_color=ColorPalette.get("text_secondary"),
        )
        self.preflight_header_label.pack(side="left")

        self.preflight_text = ctk.CTkLabel(
            self.preflight_inner,
            text="",
            font=Typography.body_md(),
            text_color=ColorPalette.get("text_primary"),
            justify="left",
            anchor="w",
        )
        self.preflight_text.pack(fill="x", pady=(0, Spacing.MD))

        preflight_btns = ctk.CTkFrame(self.preflight_inner, fg_color="transparent")
        preflight_btns.pack(fill="x")

        self.preflight_cancel_btn = ctk.CTkButton(
            preflight_btns,
            text="Cancel",
            width=100,
            height=36,
            font=Typography.body_md(),
            fg_color="transparent",
            hover_color=ColorPalette.get("border"),
            border_width=1,
            border_color=ColorPalette.get("border"),
            text_color=ColorPalette.get("text_secondary"),
            corner_radius=Radius.SM,
            command=self._dismiss_preflight,
        )
        self.preflight_cancel_btn.pack(side="left", padx=(0, 10))

        self.preflight_confirm_btn = ctk.CTkButton(
            preflight_btns,
            text="Confirm & Start",
            width=140,
            height=40,
            font=Typography.heading_sm(),
            fg_color=ColorPalette.get("accent_success"),
            hover_color="#059669",
            corner_radius=Radius.LG,
            command=self._confirm_start,
        )
        self.preflight_confirm_btn.pack(side="left")

        # === Control buttons ===
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=Spacing.PAGE_PAD, pady=(Spacing.SM, Spacing.SECTION))

        self.start_button = ctk.CTkButton(
            btn_frame,
            text="START",
            width=160,
            height=44,
            font=Typography.heading_sm(),
            fg_color=ColorPalette.get("accent_success"),
            hover_color="#059669",
            corner_radius=Radius.LG,
            command=self._show_preflight,
        )
        self.start_button.pack(side="left", padx=(0, 10))

        # Apply initial layout
        self.set_workflow("1")

    # ------------------------------------------------------------------
    # Workflow switching
    # ------------------------------------------------------------------

    WORKFLOW_META = {
        "1": ("Add User", "Batch approve pending users"),
        "2": ("Revoke Cert", "Approve revocation requests"),
        "3": ("Assign Group", "Assign users to groups"),
    }

    def set_workflow(self, workflow_id, domain=None):
        """Rebuild form for the given workflow."""
        self._current_workflow = workflow_id
        title, subtitle = self.WORKFLOW_META.get(workflow_id, ("", ""))
        self.workflow_title.configure(text=title)
        self.workflow_subtitle.configure(text=subtitle)

        if domain:
            self.domain_badge.configure(text=domain)

        # Reset
        self.batch_reject_var.set(False)
        self.batch_reject_warning.pack_forget()

        # Forget all optional widgets
        for w in [self.comment_frame, self.mode_frame, self.usernames_frame,
                  self.batch_reject_frame, self.counterpart_frame,
                  self.all_domains_frame]:
            w.pack_forget()

        self._dismiss_preflight()
        self._reset_start_button()

        if workflow_id == "1":
            self.comment_frame.pack(fill="x", pady=(0, Spacing.LG))
            self.mode_frame.pack(fill="x", pady=(0, Spacing.LG))
            self._on_mode_change()
            self.counterpart_frame.pack(fill="x", pady=(0, Spacing.SM))
        elif workflow_id == "2":
            self.comment_frame.pack(fill="x", pady=(0, Spacing.LG))
            self.counterpart_frame.pack(fill="x", pady=(0, Spacing.SM))
        elif workflow_id == "3":
            self.all_domains_frame.pack(fill="x", pady=(0, Spacing.LG))
            self._on_all_domains_toggle()

    def update_domain_badge(self, domain):
        self.domain_badge.configure(text=domain)

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    def _on_mode_change(self):
        if self.mode_var.get() == "specific" and self._current_workflow == "1":
            self.usernames_frame.pack(fill="x", pady=(0, Spacing.LG))
            self.batch_reject_frame.pack(fill="x", pady=(0, Spacing.SM))
        else:
            self.usernames_frame.pack_forget()
            self.batch_reject_frame.pack_forget()
            self.batch_reject_var.set(False)
            self.batch_reject_warning.pack_forget()
            self._reset_start_button()

    def _on_batch_reject_toggle(self):
        if self.batch_reject_var.get():
            self.batch_reject_warning.pack(side="left", padx=(10, 0))
            self.start_button.configure(
                fg_color=ColorPalette.get("accent_warning"),
                hover_color="#d97706",
                text="START (REJECT)",
            )
        else:
            self.batch_reject_warning.pack_forget()
            self._reset_start_button()

    def _on_all_domains_toggle(self):
        if self.all_domains_var.get():
            self.counterpart_frame.pack_forget()
        else:
            self.counterpart_frame.pack(fill="x", pady=(0, Spacing.SM))

    def _reset_start_button(self):
        self.start_button.configure(
            fg_color=ColorPalette.get("accent_success"),
            hover_color="#059669",
            text="START",
        )

    def _clear_usernames(self):
        self.usernames_text.delete("1.0", "end")
        self._update_username_count()

    def _update_username_count(self, event=None):
        text = self.usernames_text.get("1.0", "end").strip()
        count = len([u for u in text.split("\n") if u.strip()]) if text else 0
        if count == 0:
            self.username_count_label.configure(
                text="0 users entered",
                text_color=ColorPalette.get("text_muted"),
            )
        elif count == 1:
            self.username_count_label.configure(
                text="1 user entered",
                text_color=ColorPalette.get("accent_primary"),
            )
        else:
            self.username_count_label.configure(
                text=f"{count} users entered",
                text_color=ColorPalette.get("accent_primary"),
            )

    # ------------------------------------------------------------------
    # Pre-flight
    # ------------------------------------------------------------------

    def _build_preflight_summary(self, domain):
        """Build summary text for pre-flight card."""
        wf = self._current_workflow
        title, _ = self.WORKFLOW_META.get(wf, ("", ""))
        lines = [f"Workflow:  {title}"]
        lines.append(f"Domain:   {domain}")

        if wf == "1":
            mode = "All pending users" if self.mode_var.get() == "all" else "Specific users"
            lines.append(f"Mode:     {mode}")
            if self.batch_reject_var.get():
                lines.append("Action:   BATCH REJECT")
        if wf == "3" and self.all_domains_var.get():
            lines.append("Scope:    All 52 domains")

        if wf != "3" or not self.all_domains_var.get():
            cp = self.counterpart_var.get()
            lines.append(f"Counterpart: {'Yes' if cp else 'No'}")

        return "\n".join(lines)

    def _show_preflight(self):
        """Show pre-flight summary card."""
        domain = self.domain_badge.cget("text") or "NCR00Sign"
        self.preflight_text.configure(text=self._build_preflight_summary(domain))

        # Adjust confirm button for reject mode
        if self.batch_reject_var.get():
            self.preflight_confirm_btn.configure(
                text="Confirm & Reject",
                fg_color=ColorPalette.get("accent_warning"),
                hover_color="#d97706",
            )
        else:
            self.preflight_confirm_btn.configure(
                text="Confirm & Start",
                fg_color=ColorPalette.get("accent_success"),
                hover_color="#059669",
            )

        self.preflight_card.pack(fill="x", padx=Spacing.PAGE_PAD, pady=(0, Spacing.MD))
        self.start_button.configure(state="disabled")

    def _dismiss_preflight(self):
        self.preflight_card.pack_forget()
        self.start_button.configure(state="normal")

    def _confirm_start(self):
        """User confirmed - invoke the on_start callback."""
        self._dismiss_preflight()
        if self._on_start:
            self._on_start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_config(self):
        """Return a dict with all current configuration values."""
        text = self.usernames_text.get("1.0", "end").strip()
        specific_users = [u.strip() for u in text.split("\n") if u.strip()] if text else None
        return {
            "workflow": self._current_workflow,
            "comment": self.comment_entry.get().strip() or "Approved via automation",
            "mode": self.mode_var.get(),
            "specific_users": specific_users if self.mode_var.get() == "specific" else None,
            "counterpart": self.counterpart_var.get(),
            "all_domains": self.all_domains_var.get(),
            "batch_reject": self.batch_reject_var.get(),
        }

    def set_enabled(self, enabled):
        """Enable or disable the panel controls."""
        state = "normal" if enabled else "disabled"
        self.start_button.configure(state=state)
        self.comment_entry.configure(state=state)

    def update_colors(self):
        """Refresh all custom colors on theme change."""
        # Header
        self.workflow_title.configure(text_color=ColorPalette.get("text_primary"))
        self.workflow_subtitle.configure(text_color=ColorPalette.get("text_muted"))
        self.domain_badge.configure(
            text_color=ColorPalette.get("badge_text"),
            fg_color=ColorPalette.get("badge_bg"),
        )

        # Config card
        self.config_card.update_colors()

        # Section labels
        self.comment_label.configure(text_color=ColorPalette.get("text_muted"))
        self.mode_label.configure(text_color=ColorPalette.get("text_muted"))
        self.usernames_label.configure(text_color=ColorPalette.get("text_muted"))
        self.username_count_label.configure(text_color=ColorPalette.get("text_muted"))

        # Inputs
        self.comment_entry.configure(
            border_color=ColorPalette.get("border"),
            fg_color=ColorPalette.get("bg_input"),
            text_color=ColorPalette.get("text_primary"),
        )
        self.usernames_text.configure(
            border_color=ColorPalette.get("border"),
            fg_color=ColorPalette.get("bg_input"),
            text_color=ColorPalette.get("text_primary"),
        )

        # Clear button
        self.clear_btn.configure(
            hover_color=ColorPalette.get("border"),
            border_color=ColorPalette.get("border"),
            text_color=ColorPalette.get("text_secondary"),
        )

        # Radio buttons
        for rb in (self.radio_all, self.radio_specific):
            rb.configure(
                fg_color=ColorPalette.get("accent_primary"),
                hover_color=ColorPalette.get("accent_secondary"),
                text_color=ColorPalette.get("text_primary"),
            )

        # Checkboxes and switches
        self.counterpart_check.configure(
            fg_color=ColorPalette.get("accent_primary"),
            hover_color=ColorPalette.get("accent_secondary"),
            text_color=ColorPalette.get("text_primary"),
        )
        self.batch_reject_checkbox.configure(
            text_color=ColorPalette.get("text_primary"),
        )
        self.all_domains_switch.configure(
            progress_color=ColorPalette.get("accent_primary"),
            button_color=ColorPalette.get("text_primary"),
            button_hover_color=ColorPalette.get("text_secondary"),
            text_color=ColorPalette.get("text_primary"),
        )

        # Buttons
        self._reset_start_button()

        # Pre-flight card
        self.preflight_card.update_colors()
        self.preflight_icon_label.configure(text_color=ColorPalette.get("accent_primary"))
        self.preflight_header_label.configure(text_color=ColorPalette.get("text_secondary"))
        self.preflight_text.configure(text_color=ColorPalette.get("text_primary"))
        self.preflight_cancel_btn.configure(
            hover_color=ColorPalette.get("border"),
            border_color=ColorPalette.get("border"),
            text_color=ColorPalette.get("text_secondary"),
        )
