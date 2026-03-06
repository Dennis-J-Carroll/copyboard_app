#!/usr/bin/env python3
"""
Code Revolver UI – A dual-ring radial selector for snippet chambers.

Outer ring  = chambers (Git, Docker, Python, …)
Inner ring  = snippets within the selected chamber
Centre      = live preview of the hovered snippet

Navigation:
    Mouse       – hover to select, click to fire
    Arrow keys  – ↑↓ spin chambers, ←→ rotate snippets
    Enter       – fire current snippet
    1-6         – quick-fire chamber by number
    Escape      – cancel
"""

import math
import tkinter as tk
import tkinter.font as tkfont
from typing import List, Dict, Any, Callable, Optional

from .snippet_manager import snippets, expand_variables


# ── Theme presets ────────────────────────────────────────────────────────
THEMES = {
    "cyberpunk": {
        "bg": "#0a0a1a",
        "ring_outer": "#1a1a3a",
        "ring_inner": "#11112a",
        "accent": "#ff2d95",
        "accent2": "#00f0ff",
        "text": "#e0e0ff",
        "text_dim": "#555588",
        "node_fill": "#1a1a3a",
        "node_active": "#ff2d95",
        "center_fill": "#0d0d22",
        "center_border": "#ff2d95",
        "arm_color": "#333366",
        "arm_active": "#ff2d95",
        "preview_bg": "#111133",
        "preview_border": "#ff2d95",
        "font": "Consolas",
    },
    "terminal_green": {
        "bg": "#0a0f0a",
        "ring_outer": "#0d1a0d",
        "ring_inner": "#0a120a",
        "accent": "#00ff41",
        "accent2": "#39ff14",
        "text": "#00ff41",
        "text_dim": "#1a5c1a",
        "node_fill": "#0d1a0d",
        "node_active": "#00ff41",
        "center_fill": "#050a05",
        "center_border": "#00ff41",
        "arm_color": "#1a3a1a",
        "arm_active": "#00ff41",
        "preview_bg": "#0a140a",
        "preview_border": "#00ff41",
        "font": "Courier",
    },
    "synthwave": {
        "bg": "#1a0a2e",
        "ring_outer": "#2a1040",
        "ring_inner": "#1e0d35",
        "accent": "#f72585",
        "accent2": "#7209b7",
        "text": "#e0c0ff",
        "text_dim": "#553388",
        "node_fill": "#2a1040",
        "node_active": "#f72585",
        "center_fill": "#120828",
        "center_border": "#7209b7",
        "arm_color": "#442266",
        "arm_active": "#f72585",
        "preview_bg": "#1a0d30",
        "preview_border": "#7209b7",
        "font": "Consolas",
    },
    "dark": {
        "bg": "#1a1a2e",
        "ring_outer": "#16213e",
        "ring_inner": "#0f3460",
        "accent": "#e94560",
        "accent2": "#0088ff",
        "text": "#eaeaea",
        "text_dim": "#555555",
        "node_fill": "#16213e",
        "node_active": "#e94560",
        "center_fill": "#0f0f23",
        "center_border": "#e94560",
        "arm_color": "#2a2a4a",
        "arm_active": "#e94560",
        "preview_bg": "#111133",
        "preview_border": "#e94560",
        "font": "Arial",
    },
}

DEFAULT_THEME = "cyberpunk"


class RevolverUI:
    """A dual-ring radial menu for the Code Revolver."""

    OUTER_RADIUS = 200
    INNER_RADIUS = 120
    CENTER_RADIUS = 45
    WINDOW_PAD = 60

    def __init__(self,
                 on_fire: Optional[Callable[[str], None]] = None,
                 on_cancel: Optional[Callable[[], None]] = None,
                 theme_name: str = DEFAULT_THEME):
        self.on_fire = on_fire
        self.on_cancel = on_cancel
        self.theme = THEMES.get(theme_name, THEMES[DEFAULT_THEME])
        self.root: Optional[tk.Tk] = None
        self.canvas: Optional[tk.Canvas] = None

        # State
        self._hover_chamber: int = -1
        self._hover_snippet: int = -1
        self._selected_chamber: int = snippets.get_current_chamber_index()

        # Window geometry
        self._win_size = self.OUTER_RADIUS * 2 + self.WINDOW_PAD * 2
        self._cx = self._win_size // 2
        self._cy = self._win_size // 2

    # ── Public API ───────────────────────────────────────────────────
    def show(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        """Show the revolver UI, centred at (x, y) or screen centre."""
        self.root = tk.Tk()
        self.root.title("Code Revolver")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)

        # Try transparency
        try:
            self.root.attributes("-alpha", 0.95)
        except tk.TclError:
            pass

        # Position
        if x is None or y is None:
            sx = self.root.winfo_screenwidth() // 2
            sy = self.root.winfo_screenheight() // 2
        else:
            sx, sy = x, y

        wx = sx - self._win_size // 2
        wy = sy - self._win_size // 2
        self.root.geometry(f"{self._win_size}x{self._win_size}+{wx}+{wy}")

        self.canvas = tk.Canvas(
            self.root,
            width=self._win_size,
            height=self._win_size,
            bg=self.theme["bg"],
            highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bindings
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.root.bind("<Escape>", lambda e: self._close(cancelled=True))
        self.root.bind("<Return>", lambda e: self._fire_current())
        self.root.bind("<Up>", lambda e: self._key_spin(-1))
        self.root.bind("<Down>", lambda e: self._key_spin(1))
        self.root.bind("<Left>", lambda e: self._key_rotate(-1))
        self.root.bind("<Right>", lambda e: self._key_rotate(1))

        # Number keys 1-9 for quick-fire
        for n in range(1, 10):
            self.root.bind(str(n), lambda e, idx=n - 1: self._quick_fire(idx))

        self.root.focus_force()
        self._draw()
        self.root.mainloop()

    # ── Drawing ──────────────────────────────────────────────────────
    def _draw(self) -> None:
        if not self.canvas:
            return
        self.canvas.delete("all")

        chambers = snippets.get_chambers()
        if not chambers:
            self._draw_empty()
            return

        self._draw_background_rings()
        self._draw_outer_ring(chambers)
        self._draw_inner_ring(chambers)
        self._draw_center(chambers)

    def _draw_background_rings(self) -> None:
        """Draw subtle concentric ring backgrounds."""
        # Outer ring background
        self.canvas.create_oval(
            self._cx - self.OUTER_RADIUS, self._cy - self.OUTER_RADIUS,
            self._cx + self.OUTER_RADIUS, self._cy + self.OUTER_RADIUS,
            fill=self.theme["ring_outer"], outline=self.theme["arm_color"], width=2,
        )
        # Inner ring background
        self.canvas.create_oval(
            self._cx - self.INNER_RADIUS, self._cy - self.INNER_RADIUS,
            self._cx + self.INNER_RADIUS, self._cy + self.INNER_RADIUS,
            fill=self.theme["ring_inner"], outline=self.theme["arm_color"], width=1,
        )

    def _draw_outer_ring(self, chambers: List[Dict]) -> None:
        """Draw the chamber nodes on the outer ring."""
        n = len(chambers)
        if n == 0:
            return

        angle_step = 360 / n
        mid_r = (self.OUTER_RADIUS + self.INNER_RADIUS) / 2 + 15

        for i, ch in enumerate(chambers):
            angle_deg = -90 + i * angle_step  # start from top
            angle_rad = math.radians(angle_deg)

            nx = self._cx + mid_r * math.cos(angle_rad)
            ny = self._cy + mid_r * math.sin(angle_rad)

            is_active = (i == self._selected_chamber)
            is_hover = (i == self._hover_chamber)

            # Node circle
            node_r = 28 if is_active else (24 if is_hover else 20)
            fill = ch.get("color", self.theme["accent"]) if is_active else (
                self.theme["node_active"] if is_hover else self.theme["node_fill"]
            )
            outline = self.theme["accent"] if is_active else self.theme["arm_color"]
            width = 3 if is_active else (2 if is_hover else 1)

            self.canvas.create_oval(
                nx - node_r, ny - node_r, nx + node_r, ny + node_r,
                fill=fill, outline=outline, width=width,
            )

            # Icon
            self.canvas.create_text(
                nx, ny - 2,
                text=ch.get("icon", "⚪"),
                font=(self.theme["font"], 14),
            )

            # Label below node
            label_y = ny + node_r + 12
            self.canvas.create_text(
                nx, label_y,
                text=ch["name"],
                font=(self.theme["font"], 9, "bold" if is_active else ""),
                fill=self.theme["accent"] if is_active else self.theme["text_dim"],
            )

            # Arm from center to node
            arm_color = self.theme["arm_active"] if is_active else self.theme["arm_color"]
            arm_width = 3 if is_active else 1
            self.canvas.create_line(
                self._cx, self._cy, nx, ny,
                fill=arm_color, width=arm_width, dash=(4, 4) if not is_active else (),
            )

    def _draw_inner_ring(self, chambers: List[Dict]) -> None:
        """Draw snippets for the selected chamber on the inner ring."""
        if self._selected_chamber < 0 or self._selected_chamber >= len(chambers):
            return
        ch = chambers[self._selected_chamber]
        snips = ch.get("snippets", [])
        if not snips:
            return

        n = len(snips)
        angle_step = 360 / n
        r = self.INNER_RADIUS - 25

        for i, snip in enumerate(snips):
            angle_deg = -90 + i * angle_step
            angle_rad = math.radians(angle_deg)

            sx = self._cx + r * math.cos(angle_rad)
            sy = self._cy + r * math.sin(angle_rad)

            is_hover = (i == self._hover_snippet)
            is_current = (i == snippets.get_current_snippet_index() and
                          self._selected_chamber == snippets.get_current_chamber_index())

            # Snippet node
            nr = 18 if is_hover else (16 if is_current else 14)
            fill = self.theme["accent"] if is_hover else (
                self.theme["accent2"] if is_current else self.theme["node_fill"]
            )
            outline = self.theme["accent"] if is_hover else self.theme["arm_color"]

            self.canvas.create_oval(
                sx - nr, sy - nr, sx + nr, sy + nr,
                fill=fill, outline=outline, width=2 if is_hover else 1,
            )

            # Snippet number
            self.canvas.create_text(
                sx, sy,
                text=str(i + 1),
                font=(self.theme["font"], 10, "bold"),
                fill="#ffffff" if is_hover else self.theme["text"],
            )

            # Label
            label = snip.get("label", f"Snippet {i+1}")
            if len(label) > 16:
                label = label[:14] + "…"
            label_angle = angle_rad
            lx = self._cx + (r - 28) * math.cos(label_angle)
            ly = self._cy + (r - 28) * math.sin(label_angle)

            self.canvas.create_text(
                lx, ly,
                text=label,
                font=(self.theme["font"], 8),
                fill=self.theme["accent"] if is_hover else self.theme["text_dim"],
                angle=-angle_deg - 90 if abs(angle_deg + 90) > 90 else 0,
            )

    def _draw_center(self, chambers: List[Dict]) -> None:
        """Draw the center circle with preview."""
        # Center circle
        self.canvas.create_oval(
            self._cx - self.CENTER_RADIUS, self._cy - self.CENTER_RADIUS,
            self._cx + self.CENTER_RADIUS, self._cy + self.CENTER_RADIUS,
            fill=self.theme["center_fill"],
            outline=self.theme["center_border"],
            width=3,
        )

        # Revolver icon
        self.canvas.create_text(
            self._cx, self._cy - 8,
            text="🔫",
            font=(self.theme["font"], 18),
        )

        # Current chamber name
        ch = snippets.get_current_chamber()
        if ch:
            self.canvas.create_text(
                self._cx, self._cy + 18,
                text=ch["name"],
                font=(self.theme["font"], 9, "bold"),
                fill=self.theme["text"],
            )

        # Preview box below center (if hovering a snippet)
        if self._hover_snippet >= 0 and self._selected_chamber >= 0:
            ch_data = chambers[self._selected_chamber] if self._selected_chamber < len(chambers) else None
            if ch_data:
                snips = ch_data.get("snippets", [])
                if 0 <= self._hover_snippet < len(snips):
                    snip = snips[self._hover_snippet]
                    preview = snip["text"][:120]
                    preview = preview.replace("\n", " ↵ ").replace("\t", " → ")

                    box_w, box_h = 260, 60
                    bx = self._cx - box_w // 2
                    by = self._cy + self.CENTER_RADIUS + 15

                    # Preview background
                    self.canvas.create_rectangle(
                        bx, by, bx + box_w, by + box_h,
                        fill=self.theme["preview_bg"],
                        outline=self.theme["preview_border"],
                        width=2,
                    )

                    # Preview label
                    self.canvas.create_text(
                        bx + 8, by + 10,
                        text=f"⚡ {snip.get('label', 'Snippet')}",
                        font=(self.theme["font"], 9, "bold"),
                        fill=self.theme["accent"],
                        anchor="w",
                    )

                    # Preview text
                    self.canvas.create_text(
                        bx + 8, by + 30,
                        text=preview,
                        font=(self.theme["font"], 8),
                        fill=self.theme["text"],
                        anchor="nw",
                        width=box_w - 16,
                    )

    def _draw_empty(self) -> None:
        """Draw placeholder when no chambers exist."""
        self.canvas.create_text(
            self._cx, self._cy,
            text="No chambers loaded\nPress Escape to close",
            font=(self.theme["font"], 12),
            fill=self.theme["text_dim"],
            justify="center",
        )

    # ── Mouse events ─────────────────────────────────────────────────
    def _on_motion(self, event) -> None:
        dx = event.x - self._cx
        dy = event.y - self._cy
        dist = math.sqrt(dx * dx + dy * dy)

        old_hc, old_hs = self._hover_chamber, self._hover_snippet

        if dist < self.CENTER_RADIUS:
            self._hover_chamber = -1
            self._hover_snippet = -1
        elif dist < self.INNER_RADIUS:
            # Inner ring → snippet hover
            self._hover_chamber = -1
            ch = snippets.get_current_chamber()
            if ch:
                snips = ch.get("snippets", [])
                if snips:
                    angle = math.degrees(math.atan2(dy, dx)) + 90
                    if angle < 0:
                        angle += 360
                    self._hover_snippet = int(angle / (360 / len(snips))) % len(snips)
        else:
            # Outer ring → chamber hover
            self._hover_snippet = -1
            chambers = snippets.get_chambers()
            if chambers:
                angle = math.degrees(math.atan2(dy, dx)) + 90
                if angle < 0:
                    angle += 360
                self._hover_chamber = int(angle / (360 / len(chambers))) % len(chambers)

        if self._hover_chamber != old_hc or self._hover_snippet != old_hs:
            self._draw()

    def _on_click(self, event) -> None:
        dx = event.x - self._cx
        dy = event.y - self._cy
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < self.CENTER_RADIUS:
            # Click centre → fire current
            self._fire_current()
        elif dist < self.INNER_RADIUS:
            # Click inner ring → fire hovered snippet
            if self._hover_snippet >= 0:
                text = snippets.fire(self._selected_chamber, self._hover_snippet)
                if text and self.on_fire:
                    self.on_fire(text)
                self._close()
        elif self._hover_chamber >= 0:
            # Click outer ring → select chamber
            self._selected_chamber = self._hover_chamber
            snippets._current_chamber = self._selected_chamber
            snippets._current_snippet = 0
            self._hover_snippet = -1
            self._draw()

    def _on_right_click(self, event) -> None:
        self._close(cancelled=True)

    # ── Keyboard events ──────────────────────────────────────────────
    def _key_spin(self, direction: int) -> None:
        snippets.spin_chamber(direction)
        self._selected_chamber = snippets.get_current_chamber_index()
        self._hover_snippet = -1
        self._draw()

    def _key_rotate(self, direction: int) -> None:
        snippets.rotate_snippet(direction)
        self._draw()

    def _fire_current(self) -> None:
        text = snippets.fire()
        if text and self.on_fire:
            self.on_fire(text)
        self._close()

    def _quick_fire(self, chamber_idx: int) -> None:
        """Quick-fire the first snippet of a chamber by number."""
        chambers = snippets.get_chambers()
        if 0 <= chamber_idx < len(chambers):
            text = snippets.fire(chamber_idx, 0)
            if text and self.on_fire:
                self.on_fire(text)
            self._close()

    # ── Lifecycle ────────────────────────────────────────────────────
    def _close(self, cancelled: bool = False) -> None:
        if cancelled and self.on_cancel:
            self.on_cancel()
        if self.root:
            self.root.destroy()
            self.root = None
            self.canvas = None


# ── Convenience launcher ─────────────────────────────────────────────────
def show_revolver(x: int = None, y: int = None,
                  theme: str = DEFAULT_THEME,
                  on_fire: Callable = None) -> None:
    """Launch the Code Revolver UI.

    Args:
        x, y: Screen position (defaults to centre).
        theme: Theme name ('cyberpunk', 'terminal_green', 'synthwave', 'dark').
        on_fire: Callback receiving the expanded snippet text.
    """
    def default_fire(text):
        try:
            from . import paste_helper
            paste_helper.paste_current_clipboard()
        except Exception:
            pass

    ui = RevolverUI(
        on_fire=on_fire or default_fire,
        theme_name=theme,
    )
    ui.show(x, y)


if __name__ == "__main__":
    show_revolver()
