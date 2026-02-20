"""
Shared UI Components - ColorTransition, CardFrame, ToolTip, AnimatedProgressBar
Extracted from app.py for reuse across the redesigned GUI.
"""

import tkinter as tk
import customtkinter as ctk

from .design_system import ColorPalette, Typography, Radius


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

def _blend_colors(hex1, hex2, ratio):
    """Blend two hex colors. ratio=0 returns hex1, ratio=1 returns hex2."""
    r1, g1, b1 = int(hex1[1:3], 16), int(hex1[3:5], 16), int(hex1[5:7], 16)
    r2, g2, b2 = int(hex2[1:3], 16), int(hex2[3:5], 16), int(hex2[5:7], 16)
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------
# ColorTransition — smooth after()-based color animation
# ---------------------------------------------------------------------------

class ColorTransition:
    """Smooth color transitions using after() scheduling."""

    def __init__(self, widget, property_name, duration_ms=150, steps=8):
        self.widget = widget
        self.property = property_name
        self.duration = duration_ms
        self.steps = steps
        self._after_id = None
        self._current_step = 0
        self._from = None
        self._to = None

    def transition_to(self, target_color, from_color=None):
        """Animate from current/specified color to target."""
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

        if from_color is None:
            try:
                from_color = self.widget.cget(self.property)
            except Exception:
                from_color = target_color

        # Resolve "transparent" to a concrete hex color
        if from_color == "transparent":
            from_color = self._resolve_transparent()
        if target_color == "transparent":
            target_color = self._resolve_transparent()

        self._from = from_color
        self._to = target_color
        self._current_step = 0
        self._tick()

    def _resolve_transparent(self):
        """Best-effort resolve for transparent bg."""
        try:
            parent = self.widget.master
            if parent:
                bg = parent.cget("fg_color")
                if isinstance(bg, (list, tuple)):
                    bg = bg[0]
                if bg and bg != "transparent":
                    return bg
        except Exception:
            pass
        return ColorPalette.get("bg_sidebar")

    def _tick(self):
        if self._current_step >= self.steps:
            try:
                self.widget.configure(**{self.property: self._to})
            except Exception:
                pass
            self._after_id = None
            return

        t = self._current_step / self.steps
        eased = t * (2 - t)  # ease-out quadratic
        try:
            color = _blend_colors(self._from, self._to, eased)
            self.widget.configure(**{self.property: color})
        except Exception:
            pass

        self._current_step += 1
        delay = max(1, self.duration // self.steps)
        self._after_id = self.widget.after(delay, self._tick)

    def cancel(self):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None


# ---------------------------------------------------------------------------
# CardFrame
# ---------------------------------------------------------------------------

class CardFrame(ctk.CTkFrame):
    """A card-style frame with modern styling and smooth hover glow."""

    def __init__(self, parent, hover_glow=True, **kwargs):
        kwargs.setdefault('corner_radius', Radius.MD + 2)  # 10
        kwargs.setdefault('border_width', 1)
        kwargs.setdefault('border_color', ColorPalette.get('border'))
        kwargs.setdefault('fg_color', ColorPalette.get('bg_card'))

        super().__init__(parent, **kwargs)

        self._hover_glow = hover_glow
        self._normal_border = ColorPalette.get('border')
        self._glow_border = _blend_colors(
            self._normal_border, ColorPalette.get('accent_primary'), 0.4
        )
        self._normal_bg = ColorPalette.get('bg_card')
        self._hover_bg = _blend_colors(
            self._normal_bg, ColorPalette.get('bg_overlay'), 0.5
        )

        if hover_glow:
            self._border_transition = ColorTransition(self, 'border_color', 150, 8)
            self._bg_transition = ColorTransition(self, 'fg_color', 150, 8)
            self.bind('<Enter>', self._on_enter)
            self.bind('<Leave>', self._on_leave)

    def _on_enter(self, event):
        self._border_transition.transition_to(self._glow_border, self._normal_border)
        self._bg_transition.transition_to(self._hover_bg, self._normal_bg)

    def _on_leave(self, event):
        x, y = self.winfo_pointerxy()
        widget_x = self.winfo_rootx()
        widget_y = self.winfo_rooty()
        widget_w = self.winfo_width()
        widget_h = self.winfo_height()
        if widget_x <= x <= widget_x + widget_w and widget_y <= y <= widget_y + widget_h:
            return
        self._border_transition.transition_to(self._normal_border)
        self._bg_transition.transition_to(self._normal_bg)

    def update_colors(self):
        """Update colors based on current theme."""
        self._normal_border = ColorPalette.get('border')
        self._glow_border = _blend_colors(
            self._normal_border, ColorPalette.get('accent_primary'), 0.4
        )
        self._normal_bg = ColorPalette.get('bg_card')
        self._hover_bg = _blend_colors(
            self._normal_bg, ColorPalette.get('bg_overlay'), 0.5
        )
        self.configure(
            border_color=self._normal_border,
            fg_color=self._normal_bg,
        )


# ---------------------------------------------------------------------------
# ToolTip
# ---------------------------------------------------------------------------

class ToolTip:
    """Hover tooltip with rounded appearance."""

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
        # Rounded look via padding
        frame = tk.Frame(tw, bg="#222632", bd=0, highlightthickness=0)
        frame.pack()
        label = tk.Label(
            frame, text=self.text, bg="#222632", fg="#f0f0f0",
            font=("SF Pro Text", 11), padx=10, pady=5,
        )
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


# ---------------------------------------------------------------------------
# AnimatedProgressBar
# ---------------------------------------------------------------------------

class AnimatedProgressBar(ctk.CTkProgressBar):
    """Progress bar with smooth animated transitions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._target_value = 0
        self._current_value = 0
        self._animation_id = None
        self._animation_steps = 15
        self._animation_duration = 200

    def set_animated(self, value):
        """Set value with smooth animation."""
        self._target_value = max(0, min(1, value))
        if self._animation_id:
            self.after_cancel(self._animation_id)
        self._animate_step(0)

    def _ease_out_cubic(self, t):
        return 1 - pow(1 - t, 3)

    def _animate_step(self, step):
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
