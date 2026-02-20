"""
Completion View - Summary shown after automation finishes.
Displays stats, domain results, and action buttons.
"""

import customtkinter as ctk

from .design_system import ColorPalette, Typography, Spacing, Radius
from .components import CardFrame


# Stat card icon map
_STAT_ICONS = {
    "processed": "\u2211",   # Summation
    "domains":   "\u2302",   # House/domain
    "errors":    "\u26A0",   # Warning
    "time":      "\u23F1",   # Timer
}


class CompletionSummary(ctk.CTkFrame):
    """View shown after automation completes with stats and actions."""

    def __init__(self, parent, on_run_again=None, on_new_task=None,
                 on_view_logs=None, **kwargs):
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(parent, **kwargs)

        self._on_run_again = on_run_again
        self._on_new_task = on_new_task
        self._on_view_logs = on_view_logs

        self._build()

    def _build(self):
        # === Header with colored icon circle ===
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=Spacing.PAGE_PAD, pady=(Spacing.XXL, Spacing.LG))

        # Status icon in colored circle
        self.icon_circle = ctk.CTkFrame(
            header, width=44, height=44, corner_radius=22,
            fg_color=ColorPalette.get("accent_success"),
        )
        self.icon_circle.pack(side="left", padx=(0, Spacing.MD))
        self.icon_circle.pack_propagate(False)

        self.status_icon = ctk.CTkLabel(
            self.icon_circle,
            text="\u2713",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#ffffff",
        )
        self.status_icon.place(relx=0.5, rely=0.5, anchor="center")

        self.status_title = ctk.CTkLabel(
            header,
            text="Workflow Completed Successfully",
            font=Typography.workflow_title(),
            text_color=ColorPalette.get("text_primary"),
        )
        self.status_title.pack(side="left")

        # === Stats Grid (4 cards) ===
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=Spacing.PAGE_PAD, pady=(0, Spacing.SECTION))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stat")

        self.stat_cards = {}       # value labels
        self._stat_card_frames = {}  # CardFrame instances
        self._stat_icon_labels = {}  # icon labels
        self._stat_desc_labels = {}  # description labels

        stat_defs = [
            ("processed", "Total Processed", "0", "accent_primary"),
            ("domains", "Domains", "0", "accent_secondary"),
            ("errors", "Errors", "0", "accent_error"),
            ("time", "Time", "0m 0s", "accent_warning"),
        ]

        for col, (key, label, default, accent_key) in enumerate(stat_defs):
            card = CardFrame(stats_frame, hover_glow=False)
            card.grid(row=0, column=col, padx=Spacing.SM, pady=Spacing.XS, sticky="nsew")
            self._stat_card_frames[key] = card

            icon_label = ctk.CTkLabel(
                card,
                text=_STAT_ICONS.get(key, ""),
                font=ctk.CTkFont(size=16),
                text_color=ColorPalette.get("text_muted"),
            )
            icon_label.pack(pady=(Spacing.CARD_PAD, Spacing.XS))
            self._stat_icon_labels[key] = icon_label

            value_label = ctk.CTkLabel(
                card,
                text=default,
                font=Typography.stat_value(),
                text_color=ColorPalette.get(accent_key),
            )
            value_label.pack(pady=(0, 2))
            self.stat_cards[key] = value_label

            desc_label = ctk.CTkLabel(
                card,
                text=label,
                font=Typography.stat_label(),
                text_color=ColorPalette.get("text_muted"),
            )
            desc_label.pack(pady=(0, Spacing.CARD_PAD))
            self._stat_desc_labels[key] = desc_label

        # === Domain results list ===
        self.results_card = CardFrame(self, hover_glow=False)
        self.results_card.pack(fill="x", padx=Spacing.PAGE_PAD, pady=(0, Spacing.SECTION))

        results_inner = ctk.CTkFrame(self.results_card, fg_color="transparent")
        results_inner.pack(fill="x", padx=Spacing.CARD_PAD, pady=Spacing.MD)

        self.results_header_label = ctk.CTkLabel(
            results_inner,
            text="DOMAIN RESULTS",
            font=Typography.section_header(),
            text_color=ColorPalette.get("text_muted"),
        )
        self.results_header_label.pack(anchor="w", pady=(0, Spacing.SM))

        self.results_container = ctk.CTkFrame(results_inner, fg_color="transparent")
        self.results_container.pack(fill="x")

        # === Action buttons ===
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=Spacing.PAGE_PAD, pady=(0, Spacing.PAGE_PAD))

        # View Logs (tertiary — text-only)
        self.view_logs_btn = ctk.CTkButton(
            btn_frame,
            text="View Logs",
            width=120,
            height=36,
            font=Typography.body_md(),
            fg_color="transparent",
            hover_color=ColorPalette.get("border"),
            text_color=ColorPalette.get("text_secondary"),
            corner_radius=Radius.LG,
            command=self._handle_view_logs,
        )
        self.view_logs_btn.pack(side="left", padx=(0, Spacing.SM))

        # Run Again (secondary — outlined)
        self.run_again_btn = ctk.CTkButton(
            btn_frame,
            text="Run Again",
            width=120,
            height=38,
            font=Typography.body_md(),
            fg_color="transparent",
            hover_color=ColorPalette.get("bg_overlay"),
            border_width=1,
            border_color=ColorPalette.get("border"),
            text_color=ColorPalette.get("text_primary"),
            corner_radius=Radius.LG,
            command=self._handle_run_again,
        )
        self.run_again_btn.pack(side="left", padx=(0, Spacing.SM))

        # New Task (primary — filled)
        self.new_task_btn = ctk.CTkButton(
            btn_frame,
            text="New Task",
            width=120,
            height=40,
            font=Typography.heading_sm(),
            fg_color=ColorPalette.get("accent_primary"),
            hover_color=ColorPalette.get("accent_secondary"),
            corner_radius=Radius.LG,
            command=self._handle_new_task,
        )
        self.new_task_btn.pack(side="left")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_results(self, success=True, total_processed=0, domains_processed=None,
                     errors=0, elapsed_seconds=0, domain_results=None):
        """Populate the summary with run results."""
        if success:
            self.icon_circle.configure(fg_color=ColorPalette.get("accent_success"))
            self.status_icon.configure(text="\u2713")
            self.status_title.configure(text="Workflow Completed Successfully")
        else:
            self.icon_circle.configure(fg_color=ColorPalette.get("accent_error"))
            self.status_icon.configure(text="\u2717")
            self.status_title.configure(text="Completed with Errors")

        # Stats
        self.stat_cards["processed"].configure(text=str(total_processed))

        domain_count = len(domains_processed) if domains_processed else 1
        self.stat_cards["domains"].configure(text=str(domain_count))

        self.stat_cards["errors"].configure(text=str(errors))
        if errors > 0:
            self.stat_cards["errors"].configure(
                text_color=ColorPalette.get("accent_error")
            )

        m, s = divmod(elapsed_seconds, 60)
        self.stat_cards["time"].configure(text=f"{m}m {s}s")

        # Domain results
        for child in self.results_container.winfo_children():
            child.destroy()

        if domain_results:
            for idx, result in enumerate(domain_results):
                self._add_domain_result(
                    result.get("name", ""), result.get("status", "done"), idx
                )
        elif domains_processed:
            for idx, d in enumerate(domains_processed):
                self._add_domain_result(d, "completed", idx)
        else:
            self._add_domain_result("(single domain)", "completed", 0)

    def _add_domain_result(self, name, status, idx=0):
        # Alternating row background
        bg = ColorPalette.get("bg_overlay") if idx % 2 == 0 else "transparent"
        row = ctk.CTkFrame(self.results_container, fg_color=bg, corner_radius=4)
        row.pack(fill="x", pady=1)

        row_inner = ctk.CTkFrame(row, fg_color="transparent")
        row_inner.pack(fill="x", padx=Spacing.SM, pady=Spacing.XS)

        if status == "completed":
            icon = "\u2713"
            color = ColorPalette.get("accent_success")
        elif status == "error":
            icon = "\u2717"
            color = ColorPalette.get("accent_error")
        elif status == "skipped":
            icon = "\u2014"
            color = ColorPalette.get("text_muted")
        else:
            icon = "\u2713"
            color = ColorPalette.get("accent_success")

        ctk.CTkLabel(
            row_inner, text=icon,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=color,
            width=24,
        ).pack(side="left")

        ctk.CTkLabel(
            row_inner, text=name,
            font=Typography.body_md(),
            text_color=ColorPalette.get("text_primary"),
        ).pack(side="left", padx=(Spacing.XS, 0))

        ctk.CTkLabel(
            row_inner, text=status.capitalize(),
            font=Typography.body_sm(),
            text_color=color,
        ).pack(side="right")

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _handle_view_logs(self):
        if self._on_view_logs:
            self._on_view_logs()

    def _handle_run_again(self):
        if self._on_run_again:
            self._on_run_again()

    def _handle_new_task(self):
        if self._on_new_task:
            self._on_new_task()

    # ------------------------------------------------------------------
    # Theme update
    # ------------------------------------------------------------------

    def update_colors(self):
        """Refresh all custom colors on theme change."""
        self.status_title.configure(text_color=ColorPalette.get("text_primary"))

        # Stat cards
        accent_keys = {
            "processed": "accent_primary",
            "domains": "accent_secondary",
            "errors": "accent_error",
            "time": "accent_warning",
        }
        for key in self._stat_card_frames:
            self._stat_card_frames[key].update_colors()
            self._stat_icon_labels[key].configure(text_color=ColorPalette.get("text_muted"))
            self.stat_cards[key].configure(text_color=ColorPalette.get(accent_keys[key]))
            self._stat_desc_labels[key].configure(text_color=ColorPalette.get("text_muted"))

        # Results card
        self.results_card.update_colors()
        self.results_header_label.configure(text_color=ColorPalette.get("text_muted"))

        # Action buttons
        self.view_logs_btn.configure(
            hover_color=ColorPalette.get("border"),
            text_color=ColorPalette.get("text_secondary"),
        )
        self.run_again_btn.configure(
            hover_color=ColorPalette.get("bg_overlay"),
            border_color=ColorPalette.get("border"),
            text_color=ColorPalette.get("text_primary"),
        )
        self.new_task_btn.configure(
            fg_color=ColorPalette.get("accent_primary"),
            hover_color=ColorPalette.get("accent_secondary"),
        )
