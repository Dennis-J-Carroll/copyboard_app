#!/usr/bin/env python3
"""CopyBoard's revolver-first desktop interface.

The board is represented as a cylinder of 10–16 fixed, visible chambers. New
clipboard entries arrive in chamber 01 and older entries rotate clockwise.
Firing a chamber only *reads* it; the cylinder never changes because
something was pasted.

Responsibilities are split so each stays small:

* ``core`` owns capacity, insertion, ejecting, and persistence.
* ``hotkeys`` turns global shortcuts into commands (on its own thread).
* this module and ``widget_mode`` display the board and send commands.
* ``paste_helper`` restores the previous window and delivers the paste.
"""

import math
import os
import queue
import re
import sys
import tkinter as tk
from tkinter import messagebox
from typing import Dict, Optional, Tuple

import pyperclip

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from . import core, hotkeys, paste_helper
    from .chambers import (
        MAX_CHAMBERS,
        MIN_CHAMBERS,
        ChamberDial,
        chamber_label,
        normalize_chamber_count,
    )
    from .config_manager import config
    from .widget_mode import QuickPasteWidget
except ImportError as exc:
    print(f"Error importing CopyBoard modules: {exc}")
    raise


# A warm, physical-tool palette: dark steel, paper, brass, and signal orange.
INK = "#141512"
PANEL = "#1B1D19"
PANEL_RAISED = "#242620"
PANEL_SOFT = "#2C2E27"
LINE = "#3C3E35"
TEXT = "#F2EEDF"
TEXT_DIM = "#A6A394"
TEXT_FAINT = "#6F7167"
ACCENT = "#FF6B35"
ACCENT_HOVER = "#FF8157"
BRASS = "#C7A86B"
MINT = "#8FB996"
EMPTY = "#20221E"
ERROR = "#E56B6F"

FONT = "DejaVu Sans"
MONO = "DejaVu Sans Mono"

# How long the editor waits after hiding itself before restoring focus and
# synthesising the paste keystroke.
FIRE_FOCUS_DELAY_MS = 90
FIRE_PASTE_DELAY_MS = 140
UI_ACTION_POLL_MS = 40   # how quickly a global shortcut reaches the Tk thread
# Clipboard poll ticks (650 ms each) between foreground-window captures.
TARGET_POLL_TICKS = 3 if paste_helper.get_platform() == "macos" else 1


def focus_fallback_message(index: int, platform_name: str) -> str:
    """Explain why a fire became copy-only, without pasting anywhere wrong."""
    label = chamber_label(index)
    if platform_name == "linux":
        hint = "Automatic paste needs xdotool on X11"
    elif platform_name == "macos":
        hint = "Allow CopyBoard under Accessibility to paste automatically"
    else:
        hint = "The previous window could not be brought back"
    return f"Chamber {label} copied — press Ctrl+V in the target app. {hint}."


def classify_clip(content: str) -> Tuple[str, str]:
    """Return a short content kind and a chamber mark."""
    stripped = content.strip()
    if re.match(r"^https?://\S+$", stripped, re.IGNORECASE):
        return "LINK", "↗"
    if "\n" in content and (
        re.search(r"[{}();=<>]", content)
        or stripped.startswith(("def ", "class ", "import ", "const ", "function "))
    ):
        return "CODE", "{ }"
    if "\n" in content:
        return "MULTILINE", "¶"
    return "TEXT", "T"


def compact_preview(content: str, limit: int = 54) -> str:
    """Create a single-line preview suitable for the chamber readout."""
    preview = " ".join(content.split())
    if not preview:
        return "Empty text"
    return preview if len(preview) <= limit else preview[: limit - 1].rstrip() + "…"


class CopyboardGUI:
    """A polished 10–16 chamber clipboard controller."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.configure(bg=INK)
        self._app_icon: Optional[tk.PhotoImage] = None
        self._set_app_icon()
        self.root.geometry(self._initial_geometry())
        self.root.minsize(940, 640)

        # Capacity has one source of truth: core, seeded from config.json.
        # A legacy config outside 10–16 is normalised once and written back.
        raw_capacity = config.get("board", "max_items", MIN_CHAMBERS)
        capacity = normalize_chamber_count(raw_capacity)
        core.set_chamber_count(capacity, persist=raw_capacity != capacity)

        self.selected_index = 0
        self.hovered_index: Optional[int] = None
        self._chamber_centers: Dict[int, Tuple[float, float]] = {}
        self._hit_radius = 52.0
        self._show_kind_labels = True
        self._applying_capacity = False
        self._target_poll_tick = 0
        self._poll_job: Optional[str] = None
        self._status_job: Optional[str] = None
        self._closing = False
        self._widget: Optional[QuickPasteWidget] = None
        # The window that should receive the next fire.  Refreshed whenever
        # CopyBoard itself is not the focused application.
        self._paste_target = None
        self._ui_actions: queue.SimpleQueue = queue.SimpleQueue()
        self._dial = ChamberDial(core.get_chamber_count)
        self._hotkey_report: Dict[str, str] = {}

        self.auto_capture_var = tk.BooleanVar(
            value=config.get("board", "auto_capture", True)
        )
        self.always_on_top_var = tk.BooleanVar(
            value=config.get("window", "always_on_top", True)
        )
        self.status_var = tk.StringVar(value="Ready")
        self.slot_var = tk.StringVar()
        self.kind_var = tk.StringVar()
        self.meta_var = tk.StringVar()
        self.subtitle_var = tk.StringVar()
        self.hub_hint_var = tk.StringVar()
        self.capacity_var = tk.StringVar(value=str(core.get_chamber_count()))
        self.hotkey_state_var = tk.StringVar(value="GLOBAL KEYS OFF")
        self.capture_state_var = tk.StringVar()
        self._update_capacity_labels()

        try:
            self._last_clipboard = pyperclip.paste()
        except pyperclip.PyperclipException:
            self._last_clipboard = ""

        self._build_ui()
        self._bind_controls()
        self._apply_always_on_top()
        self.refresh()
        self._update_capture_state()
        self._schedule_clipboard_poll()
        self._schedule_ui_action_poll()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        # Build the quick-paste plate once the editor is up so the first
        # shortcut press shows it with no construction stall.
        self.root.after(250, self._prebuild_widget)

    # ------------------------------------------------------------------
    # Capacity
    # ------------------------------------------------------------------
    @staticmethod
    def chamber_count() -> int:
        return core.get_chamber_count()

    def _update_capacity_labels(self) -> None:
        count = self.chamber_count()
        self.root.title(f"CopyBoard — {count} Chamber Clipboard")
        self.subtitle_var.set(f"{count}-CHAMBER CLIPBOARD  /  MK II")
        self.hub_hint_var.set(
            f"CLICK TO SELECT   •   DOUBLE-CLICK TO COPY   •   TYPE 1–{count} TO SELECT"
        )
        self.capacity_var.set(str(count))

    def _on_capacity_spin(self) -> None:
        self._apply_capacity(self.capacity_var.get())

    def _apply_capacity(self, requested) -> None:
        """Resize the cylinder after an explicit, confirmed user action."""
        if self._applying_capacity:
            return  # the confirm dialog itself triggers a FocusOut on the spinner
        self._applying_capacity = True
        try:
            self._apply_capacity_inner(requested)
        finally:
            self._applying_capacity = False

    def _apply_capacity_inner(self, requested) -> None:
        current = self.chamber_count()
        try:
            wanted = int(str(requested).strip())
        except ValueError:
            self.capacity_var.set(str(current))
            self._set_status(
                f"Chamber count must be a number from {MIN_CHAMBERS} to {MAX_CHAMBERS}",
                error=True,
            )
            return
        target = normalize_chamber_count(wanted)
        if target != wanted:
            self._set_status(
                f"Chamber count clamped to {target} (allowed: {MIN_CHAMBERS}–{MAX_CHAMBERS})",
                error=True,
            )
        if target == current:
            self.capacity_var.set(str(current))
            return

        lost = core.rounds_lost_when_resized(target)
        if lost:
            rounds = "round" if lost == 1 else "rounds"
            if not messagebox.askyesno(
                "Shrink the cylinder?",
                f"Reducing to {target} chambers ejects the {lost} oldest {rounds} "
                f"(chambers {chamber_label(target)}–{chamber_label(current - 1)}). "
                "The newest rounds keep their chambers. Continue?",
                parent=self.root,
            ):
                self.capacity_var.set(str(current))
                return

        applied = core.set_chamber_count(target)
        core.force_save()
        self.selected_index = min(self.selected_index, applied - 1)
        self._update_capacity_labels()
        self.refresh()
        self._register_global_hotkeys()
        if self._widget is not None and self._widget.is_visible():
            self._widget.show()
        if lost:
            self._set_status(f"Cylinder set to {applied} chambers — {lost} oldest ejected")
        else:
            self._set_status(f"Cylinder set to {applied} chambers")

    def _set_app_icon(self) -> None:
        """Use CopyBoard's bundled icon without making startup depend on it."""
        icon_path = os.path.join(current_dir, "assets", "copyboard-icon.png")
        try:
            self._app_icon = tk.PhotoImage(file=icon_path)
            self.root.iconphoto(True, self._app_icon)
        except (OSError, tk.TclError):
            self._app_icon = None

    def _initial_geometry(self) -> str:
        width = max(1040, config.get("window", "width", 1040))
        height = max(680, config.get("window", "height", 680))
        x = config.get("window", "x", 100)
        y = config.get("window", "y", 100)
        return f"{width}x{height}+{x}+{y}"

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=INK)
        shell.pack(fill=tk.BOTH, expand=True)
        self._build_header(shell)
        self._build_footer(shell)

        body = tk.Frame(shell, bg=INK)
        body.pack(fill=tk.BOTH, expand=True, padx=22, pady=(10, 14))
        body.grid_columnconfigure(0, weight=3, uniform="body")
        body.grid_columnconfigure(1, weight=2, uniform="body")
        body.grid_rowconfigure(0, weight=1)

        self._build_revolver_panel(body)
        self._build_detail_panel(body)

    def _build_header(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg=INK, height=84)
        header.pack(fill=tk.X, padx=24, pady=(18, 2))
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=INK)
        brand.pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(
            brand, text="COPYBOARD", bg=INK, fg=TEXT, font=(FONT, 22, "bold")
        ).pack(anchor=tk.W)
        tk.Label(
            brand,
            textvariable=self.subtitle_var,
            bg=INK,
            fg=BRASS,
            font=(MONO, 9, "bold"),
        ).pack(anchor=tk.W, pady=(1, 0))

        actions = tk.Frame(header, bg=INK)
        actions.pack(side=tk.RIGHT, fill=tk.Y)
        self._make_button(
            actions, "CAPTURE CURRENT", self.capture_current, variant="accent"
        ).pack(side=tk.LEFT, padx=(0, 8), pady=12)

        capacity = tk.Frame(actions, bg=INK)
        capacity.pack(side=tk.LEFT, padx=(0, 12), pady=12)
        tk.Label(
            capacity, text="CHAMBERS", bg=INK, fg=TEXT_FAINT, font=(MONO, 8, "bold")
        ).pack(side=tk.LEFT, padx=(0, 6))
        self.capacity_spin = tk.Spinbox(
            capacity,
            from_=MIN_CHAMBERS,
            to=MAX_CHAMBERS,
            width=3,
            textvariable=self.capacity_var,
            command=self._on_capacity_spin,
            bg=PANEL_SOFT,
            fg=TEXT,
            buttonbackground=PANEL_SOFT,
            insertbackground=ACCENT,
            relief=tk.FLAT,
            bd=0,
            font=(MONO, 10, "bold"),
            justify=tk.CENTER,
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=ACCENT,
        )
        self.capacity_spin.pack(side=tk.LEFT, ipady=4)
        self.capacity_spin.bind(
            "<Return>", lambda _event: self._apply_capacity(self.capacity_var.get())
        )
        self.capacity_spin.bind(
            "<FocusOut>", lambda _event: self._apply_capacity(self.capacity_var.get())
        )
        self._make_button(
            actions, "SHORTCUTS", self.open_shortcuts, variant="quiet"
        ).pack(side=tk.LEFT, padx=(0, 12), pady=12)
        self._make_button(
            actions, "WIDGET MODE", self.open_widget, variant="quiet"
        ).pack(side=tk.LEFT, padx=(0, 12), pady=12)

        tk.Checkbutton(
            actions,
            text="AUTO-CAPTURE",
            variable=self.auto_capture_var,
            command=self._toggle_auto_capture,
            bg=INK,
            activebackground=INK,
            fg=MINT,
            activeforeground=MINT,
            selectcolor=PANEL_RAISED,
            font=(MONO, 9, "bold"),
            cursor="hand2",
            highlightthickness=0,
            bd=0,
        ).pack(side=tk.LEFT, pady=12)

    def _build_revolver_panel(self, parent: tk.Widget) -> None:
        left = tk.Frame(
            parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1
        )
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 9))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        label_row = tk.Frame(left, bg=PANEL)
        label_row.grid(row=0, column=0, sticky="ew", padx=18, pady=(15, 0))
        tk.Label(
            label_row, text="THE BARREL", bg=PANEL, fg=TEXT, font=(MONO, 10, "bold")
        ).pack(side=tk.LEFT)
        tk.Label(
            label_row,
            text="NEWEST ROUND LOADS AT 01",
            bg=PANEL,
            fg=TEXT_FAINT,
            font=(MONO, 8),
        ).pack(side=tk.RIGHT)

        self.canvas = tk.Canvas(
            left, bg=PANEL, bd=0, highlightthickness=0, cursor="hand2"
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=8, pady=5)
        self.canvas.bind("<Configure>", lambda _event: self.draw_revolver())
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<Leave>", self._on_canvas_leave)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)

        tk.Label(
            left,
            textvariable=self.hub_hint_var,
            bg=PANEL,
            fg=TEXT_FAINT,
            font=(MONO, 8),
        ).grid(row=2, column=0, sticky="ew", pady=(0, 13))

    def _build_detail_panel(self, parent: tk.Widget) -> None:
        right = tk.Frame(
            parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1
        )
        right.grid(row=0, column=1, sticky="nsew", padx=(9, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        heading = tk.Frame(right, bg=PANEL)
        heading.grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 12))
        tk.Label(
            heading,
            textvariable=self.slot_var,
            bg=PANEL,
            fg=ACCENT,
            font=(MONO, 10, "bold"),
        ).pack(anchor=tk.W)
        tk.Label(
            heading,
            textvariable=self.kind_var,
            bg=PANEL,
            fg=TEXT,
            font=(FONT, 22, "bold"),
        ).pack(anchor=tk.W, pady=(4, 0))
        tk.Label(
            heading,
            textvariable=self.meta_var,
            bg=PANEL,
            fg=TEXT_DIM,
            font=(MONO, 9),
        ).pack(anchor=tk.W, pady=(3, 0))

        tk.Frame(right, bg=LINE, height=1).grid(
            row=1, column=0, sticky="ew", padx=22
        )
        editor_frame = tk.Frame(right, bg=PANEL)
        editor_frame.grid(row=2, column=0, sticky="nsew", padx=22, pady=18)
        editor_frame.grid_columnconfigure(0, weight=1)
        editor_frame.grid_rowconfigure(1, weight=1)
        tk.Label(
            editor_frame,
            text="ROUND CONTENT",
            bg=PANEL,
            fg=TEXT_FAINT,
            font=(MONO, 8, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        text_shell = tk.Frame(
            editor_frame,
            bg=PANEL_RAISED,
            highlightbackground=LINE,
            highlightthickness=1,
        )
        text_shell.grid(row=1, column=0, sticky="nsew")
        text_shell.grid_columnconfigure(0, weight=1)
        text_shell.grid_rowconfigure(0, weight=1)
        self.editor = tk.Text(
            text_shell,
            wrap=tk.WORD,
            bg=PANEL_RAISED,
            fg=TEXT,
            insertbackground=ACCENT,
            selectbackground=ACCENT,
            selectforeground=INK,
            font=(MONO, 10),
            relief=tk.FLAT,
            bd=0,
            padx=15,
            pady=14,
            undo=True,
        )
        self.editor.grid(row=0, column=0, sticky="nsew")
        scrollbar = tk.Scrollbar(
            text_shell,
            command=self.editor.yview,
            bg=PANEL_RAISED,
            troughcolor=PANEL,
            activebackground=ACCENT,
            relief=tk.FLAT,
            bd=0,
            width=10,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.editor.configure(yscrollcommand=scrollbar.set)

        controls = tk.Frame(right, bg=PANEL)
        controls.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 12))
        controls.grid_columnconfigure((0, 1), weight=1)
        self.fire_button = self._make_button(
            controls, "FIRE & HIDE", self.fire_selected, variant="accent"
        )
        self.fire_button.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.copy_button = self._make_button(
            controls, "COPY ONLY", self.copy_selected, variant="light"
        )
        self.copy_button.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        self.save_button = self._make_button(
            controls, "SAVE EDIT", self.save_editor, variant="quiet"
        )
        self.save_button.grid(row=1, column=1, sticky="ew", padx=(4, 0))

        utility = tk.Frame(right, bg=PANEL)
        utility.grid(row=4, column=0, sticky="ew", padx=22, pady=(0, 18))
        self._make_text_action(
            utility, "EJECT ROUND", self.eject_selected, ERROR
        ).pack(side=tk.LEFT)
        self._make_text_action(
            utility, "CLEAR BARREL", self.clear_board, TEXT_FAINT
        ).pack(side=tk.RIGHT)

    def _build_footer(self, parent: tk.Widget) -> None:
        footer = tk.Frame(parent, bg=PANEL_RAISED, height=34)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)
        self.status_dot = tk.Canvas(
            footer, width=22, height=22, bg=PANEL_RAISED, highlightthickness=0
        )
        self.status_dot.pack(side=tk.LEFT, padx=(20, 0), pady=6)
        self.status_dot.create_oval(7, 7, 15, 15, fill=MINT, outline="")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=PANEL_RAISED,
            fg=TEXT_DIM,
            font=(MONO, 8),
        ).pack(side=tk.LEFT, padx=(0, 12))
        self.capture_state_label = tk.Label(
            footer,
            textvariable=self.capture_state_var,
            bg=PANEL_RAISED,
            fg=MINT,
            font=(MONO, 8, "bold"),
        )
        self.capture_state_label.pack(side=tk.LEFT, padx=(0, 12))
        self.hotkey_state_label = tk.Label(
            footer,
            textvariable=self.hotkey_state_var,
            bg=PANEL_RAISED,
            fg=TEXT_FAINT,
            font=(MONO, 8, "bold"),
            cursor="hand2",
        )
        self.hotkey_state_label.pack(side=tk.LEFT)
        self.hotkey_state_label.bind("<Button-1>", lambda _event: self.open_shortcuts())
        tk.Checkbutton(
            footer,
            text="PIN WINDOW",
            variable=self.always_on_top_var,
            command=self._toggle_always_on_top,
            bg=PANEL_RAISED,
            activebackground=PANEL_RAISED,
            fg=TEXT_FAINT,
            activeforeground=TEXT,
            selectcolor=PANEL,
            font=(MONO, 8),
            cursor="hand2",
            highlightthickness=0,
            bd=0,
        ).pack(side=tk.RIGHT, padx=18)
        tk.Label(
            footer,
            text="↑ ↓ CYCLE   ENTER COPY   CTRL+ENTER FIRE   DEL EJECT",
            bg=PANEL_RAISED,
            fg=TEXT_FAINT,
            font=(MONO, 8),
        ).pack(side=tk.RIGHT, padx=10)

    def _make_button(
        self, parent: tk.Widget, text: str, command, variant: str = "quiet"
    ) -> tk.Button:
        colors = {
            "accent": (ACCENT, INK, ACCENT_HOVER, INK),
            "light": (TEXT, INK, "#FFFFFF", INK),
            "quiet": (PANEL_SOFT, TEXT, LINE, TEXT),
        }
        bg, fg, active_bg, active_fg = colors[variant]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=active_fg,
            disabledforeground=TEXT_FAINT,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=10,
            cursor="hand2",
            font=(MONO, 9, "bold"),
            highlightthickness=0,
        )

    def _make_text_action(
        self, parent: tk.Widget, text: str, command, color: str
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=PANEL,
            fg=color,
            activebackground=PANEL,
            activeforeground=TEXT,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            font=(MONO, 8, "bold"),
            highlightthickness=0,
        )

    # ------------------------------------------------------------------
    # Revolver drawing and input
    # ------------------------------------------------------------------
    def draw_revolver(self) -> None:
        if not self.canvas.winfo_exists():
            return
        self.canvas.delete("all")
        width = max(320, self.canvas.winfo_width())
        height = max(320, self.canvas.winfo_height())
        cx = width / 2
        cy = height / 2 + 4
        count = self.chamber_count()
        # Fit the whole cylinder (plus its outer rim) inside the canvas, then
        # size each chamber from the arc length between neighbours so 16
        # chambers never overlap and 10 chambers stay generous.
        radius = max(90.0, min(width, height) / 2 - 62)
        spacing = 2 * math.pi * radius / count
        chamber_radius = max(18.0, min(44.0, spacing / 2 - 9))
        self._hit_radius = chamber_radius + 8
        # The content-kind caption fits inside a roomy chamber; on a crowded
        # cylinder the mark alone carries that information.
        self._show_kind_labels = chamber_radius >= 34
        items = core.get_board()

        self.canvas.create_oval(
            cx - radius - 58,
            cy - radius - 52,
            cx + radius + 58,
            cy + radius + 60,
            fill="#10110F",
            outline="",
        )
        self.canvas.create_oval(
            cx - radius - 56,
            cy - radius - 56,
            cx + radius + 56,
            cy + radius + 56,
            fill=PANEL_RAISED,
            outline=LINE,
            width=2,
        )
        self.canvas.create_oval(
            cx - radius - 34,
            cy - radius - 34,
            cx + radius + 34,
            cy + radius + 34,
            fill="#191B17",
            outline="#30322B",
            width=2,
        )

        self._chamber_centers.clear()
        for index in range(count):
            angle = math.radians(-90 + index * (360 / count))
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            self._chamber_centers[index] = (x, y)
            self._draw_chamber(index, x, y, chamber_radius, items)

        hub_radius = max(58, chamber_radius * 1.38)
        self.canvas.create_oval(
            cx - hub_radius - 5,
            cy - hub_radius - 5,
            cx + hub_radius + 5,
            cy + hub_radius + 5,
            fill=INK,
            outline=BRASS,
            width=2,
        )
        self.canvas.create_oval(
            cx - hub_radius + 8,
            cy - hub_radius + 8,
            cx + hub_radius - 8,
            cy + hub_radius - 8,
            fill=PANEL,
            outline=LINE,
            width=1,
        )
        self.canvas.create_text(
            cx, cy - 17, text=f"{len(items):02d}", fill=TEXT, font=(MONO, 26, "bold")
        )
        self.canvas.create_text(
            cx,
            cy + 14,
            text=f"/ {count:02d} LOADED",
            fill=BRASS,
            font=(MONO, 8, "bold"),
        )
        self.canvas.create_text(
            cx,
            cy + 35,
            text="READY" if items else "EMPTY",
            fill=MINT if items else TEXT_FAINT,
            font=(MONO, 8, "bold"),
        )

    def _draw_chamber(self, index, x, y, radius, items) -> None:
        occupied = index < len(items)
        selected = index == self.selected_index
        hovered = index == self.hovered_index
        large = radius >= 30
        number_font = (MONO, 12 if large else 10, "bold")
        mark_font = (MONO, 10 if large else 8, "bold")
        number_y = y - radius * (0.38 if self._show_kind_labels else 0.32)
        mark_y = y + radius * (0.08 if self._show_kind_labels else 0.26)
        if selected:
            outer_fill, outline, width = ACCENT, ACCENT, 3
        elif hovered:
            outer_fill, outline, width = PANEL_SOFT, BRASS, 2
        else:
            outer_fill, outline, width = PANEL_SOFT, LINE, 2

        self.canvas.create_oval(
            x - radius - 6,
            y - radius - 6,
            x + radius + 6,
            y + radius + 6,
            fill=outer_fill,
            outline=outline,
            width=width,
        )
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=INK if occupied else EMPTY,
            outline="#090A08",
            width=2,
        )
        self.canvas.create_text(
            x,
            number_y,
            text=chamber_label(index),
            fill=INK if selected else (BRASS if occupied else TEXT_FAINT),
            font=number_font,
        )
        if occupied:
            kind, mark = classify_clip(items[index])
            self.canvas.create_text(
                x, mark_y, text=mark, fill=TEXT, font=mark_font
            )
            if self._show_kind_labels:
                self.canvas.create_text(
                    x,
                    y + radius * 0.55,
                    text=kind,
                    fill=INK if selected else (ACCENT if hovered else TEXT_FAINT),
                    font=(MONO, 6, "bold"),
                )
        else:
            self.canvas.create_text(
                x, mark_y, text="—", fill=TEXT_FAINT, font=(MONO, 12 if large else 10)
            )

    def _chamber_at(self, x: int, y: int) -> Optional[int]:
        for index, (cx, cy) in self._chamber_centers.items():
            if math.hypot(x - cx, y - cy) <= self._hit_radius:
                return index
        return None

    def _on_canvas_motion(self, event) -> None:
        hovered = self._chamber_at(event.x, event.y)
        if hovered != self.hovered_index:
            self.hovered_index = hovered
            self.draw_revolver()
            if hovered is not None:
                item = core.get_board_item(hovered)
                self._set_status(
                    compact_preview(item)
                    if item is not None
                    else f"Chamber {chamber_label(hovered)} is empty",
                    temporary=False,
                )

    def _on_canvas_leave(self, _event) -> None:
        if self.hovered_index is not None:
            self.hovered_index = None
            self.draw_revolver()
        self._set_status("Ready", temporary=False)

    def _on_canvas_click(self, event) -> None:
        index = self._chamber_at(event.x, event.y)
        if index is not None:
            self.select_chamber(index)

    def _on_canvas_double_click(self, event) -> None:
        index = self._chamber_at(event.x, event.y)
        if index is not None:
            self.select_chamber(index)
            self.copy_selected()

    def select_chamber(self, index: int) -> None:
        self.selected_index = max(0, min(self.chamber_count() - 1, index))
        self._refresh_detail()
        self.draw_revolver()

    # ------------------------------------------------------------------
    # Board actions
    # ------------------------------------------------------------------
    def refresh(self, select_newest: bool = False) -> None:
        if select_newest:
            self.selected_index = 0
        self.selected_index = min(self.selected_index, self.chamber_count() - 1)
        self._refresh_detail()
        self.draw_revolver()

    def _refresh_detail(self) -> None:
        content = core.get_chamber(self.selected_index)
        self.slot_var.set(
            f"CHAMBER {chamber_label(self.selected_index)} / {self.chamber_count():02d}"
        )
        self.editor.configure(state=tk.NORMAL)
        self.editor.delete("1.0", tk.END)

        if content is None:
            self.kind_var.set("Empty chamber")
            self.meta_var.set("AVAILABLE  •  PASTE OR TYPE A NEW ROUND")
            self.fire_button.configure(state=tk.DISABLED)
            self.copy_button.configure(state=tk.DISABLED)
            self.save_button.configure(text="LOAD TEXT")
        else:
            kind, _mark = classify_clip(content)
            line_count = max(1, content.count("\n") + 1)
            self.kind_var.set(f"{kind.title()} round")
            self.meta_var.set(
                f"{kind}  •  {len(content):,} CHARACTERS  •  {line_count} "
                f"{'LINE' if line_count == 1 else 'LINES'}"
            )
            self.editor.insert("1.0", content)
            self.fire_button.configure(state=tk.NORMAL)
            self.copy_button.configure(state=tk.NORMAL)
            self.save_button.configure(text="SAVE EDIT")
        self.editor.edit_reset()

    def capture_current(self) -> None:
        try:
            content = pyperclip.paste()
        except pyperclip.PyperclipException as exc:
            self._set_status(f"Clipboard unavailable: {exc}", error=True)
            return
        if not isinstance(content, str) or not content:
            self._set_status("Clipboard has no text to capture", error=True)
            return
        self._last_clipboard = content
        core.copy_to_board(content)
        self.refresh(select_newest=True)
        self._set_status("Current clipboard loaded into chamber 01")

    def _load_chamber_into_clipboard(self, index: int) -> Optional[str]:
        """Read one chamber and place its exact text on the clipboard.

        Returns the text, or None (with a status message) when the chamber
        is empty or the clipboard is unreachable.  The board is not touched.
        """
        content = core.get_chamber(index)
        if content is None:
            self._set_status(f"Chamber {chamber_label(index)} is empty", error=True)
            return None
        try:
            core.set_clipboard_text(content)
        except pyperclip.PyperclipException as exc:
            self._set_status(f"Could not reach clipboard: {exc}", error=True)
            return None
        self._last_clipboard = content
        return content

    def copy_selected(self) -> None:
        if self._load_chamber_into_clipboard(self.selected_index) is None:
            return
        self._set_status(f"Chamber {chamber_label(self.selected_index)} copied")

    def fire_selected(self) -> None:
        """Fire & Hide: hide the editor, return focus to the previous app, paste."""
        index = self.selected_index
        if self._load_chamber_into_clipboard(index) is None:
            return
        target = self._paste_target
        self._set_status(f"Firing chamber {chamber_label(index)}")
        self.root.iconify()
        self.root.after(
            FIRE_FOCUS_DELAY_MS, lambda: self._deliver_fire(index, target, from_widget=False)
        )

    def _deliver_fire(self, index: int, target, from_widget: bool) -> None:
        """Restore the previous window and paste, or fall back visibly.

        A paste is only synthesised when focus provably returned to the
        window captured earlier.  Otherwise the round stays on the clipboard
        and the user is told to paste manually — never a silent paste into
        CopyBoard or an unrelated window.
        """
        if self._closing:
            return
        if target is not None and paste_helper.restore_active_window(target):
            self.root.after(FIRE_PASTE_DELAY_MS, paste_helper.paste_current_clipboard)
            self._set_status(f"Fired chamber {chamber_label(index)}")
            if from_widget and self._widget is not None and self._widget_should_reopen():
                self.root.after(FIRE_PASTE_DELAY_MS + 280, self._reshow_widget)
            return

        message = focus_fallback_message(index, paste_helper.get_platform())
        if from_widget and self._widget is not None:
            self._widget.show()
            self._widget.flash_message(message, error=True, hold_ms=5000)
        else:
            self.root.deiconify()
            self.root.lift()
        self._set_status(message, error=True)

    def _widget_should_reopen(self) -> bool:
        """Let go and it's gone — unless nothing else could bring it back.

        The widget stays hidden after a fire so it never lingers over the
        target app.  If the open-widget shortcut is not registered (no
        ``keyboard`` backend, no permission) the widget reappears instead, so
        the app can never become unreachable.
        """
        if config.get("window", "widget_reopen_after_fire", False):
            return True
        return self._hotkey_report.get("show_gui") != hotkeys.STATUS_REGISTERED

    def _reshow_widget(self) -> None:
        if not self._closing and self._widget is not None:
            self._widget.show()

    def _capture_from_widget(self) -> None:
        """COPY tab on the widget: load the current clipboard into chamber 01."""
        self.capture_current()
        if self._widget is not None:
            self._widget.flash_message(self.status_var.get(), error="Clipboard" in self.status_var.get())

    # ------------------------------------------------------------------
    # Compact quick-paste widget
    # ------------------------------------------------------------------
    def request_widget(self) -> None:
        """Thread-safe entry point used by the global shortcut callback."""
        self._ui_actions.put(("widget",))

    def notify_quick_paste(self, index: int, success: bool) -> None:
        """Called on the hotkey thread after a direct chamber paste.

        Only a small command is queued here; the Tk thread does the drawing.
        """
        self._ui_actions.put(("fired", int(index), bool(success)))

    def _schedule_ui_action_poll(self) -> None:
        if not self._closing:
            self.root.after(UI_ACTION_POLL_MS, self._poll_ui_actions)

    def _poll_ui_actions(self) -> None:
        if self._closing:
            return
        try:
            while True:
                action = self._ui_actions.get_nowait()
                self._handle_ui_action(action)
        except queue.Empty:
            pass

        if (
            self._widget is not None
            and self._widget.is_visible()
            and self._copyboard_unfocused()
        ):
            self._capture_paste_target()
        self._schedule_ui_action_poll()

    def _handle_ui_action(self, action) -> None:
        if action == "widget" or action == ("widget",):
            self.open_widget()
        elif isinstance(action, tuple) and action and action[0] == "fired":
            _tag, index, success = action
            if success:
                self.selected_index = index
                self._refresh_detail()
                self.draw_revolver()
                if self._widget is not None and self._widget.is_visible():
                    self._widget.select(index)
                self._set_status(f"Fired chamber {chamber_label(index)} by shortcut")
            else:
                self._set_status(
                    f"Chamber {chamber_label(index)} is empty — nothing to fire",
                    error=True,
                )

    def _copyboard_unfocused(self) -> bool:
        try:
            return self.root.focus_displayof() is None
        except tk.TclError:
            return True

    def _capture_paste_target(self) -> None:
        target = paste_helper.capture_active_window()
        if target is not None:
            self._paste_target = target

    def _ensure_widget(self) -> QuickPasteWidget:
        if self._widget is None:
            self._widget = QuickPasteWidget(
                parent=self.root,
                get_items=core.get_board,
                describe_item=self._describe_widget_item,
                on_fire=self._fire_from_widget,
                on_restore=self._restore_from_widget,
                initial_position=(
                    config.get("window", "widget_x", 80),
                    config.get("window", "widget_y", 80),
                ),
                on_move=self._save_widget_position,
                get_count=core.get_chamber_count,
                on_eject=self._eject_from_widget,
                on_capture=self._capture_from_widget,
                on_dismiss=self._dismiss_widget,
            )
        return self._widget

    def _prebuild_widget(self) -> None:
        if not self._closing:
            try:
                self._ensure_widget().prebuild()
            except tk.TclError:
                pass

    def open_widget(self) -> None:
        """Collapse the editor into the compact quick-paste plate."""
        if self._widget is not None and self._widget.is_visible():
            self._dismiss_widget()
            return

        self._capture_paste_target()
        widget = self._ensure_widget()
        self.root.withdraw()
        widget.select(self.selected_index)
        at = None
        if config.get("window", "widget_at_pointer", True):
            try:
                at = self.root.winfo_pointerxy()
            except tk.TclError:
                at = None
        widget.show(at=at)

    def _dismiss_widget(self) -> None:
        """Escape or a second shortcut press: hide the plate and stay hidden.

        If no shortcut can bring the plate back, fall through to the editor
        so the app never disappears entirely.
        """
        if self._widget is not None:
            self._widget.hide()
        if self._widget_should_reopen():
            self._restore_from_widget()

    def _describe_widget_item(self, content: str) -> Tuple[str, str, str]:
        kind, mark = classify_clip(content)
        return kind, mark, compact_preview(content, limit=40)

    def _save_widget_position(self, x: int, y: int) -> None:
        config.set("window", "widget_x", x)
        config.set("window", "widget_y", y)

    def _restore_from_widget(self) -> None:
        if self._widget is not None:
            self._widget.hide()
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _fire_from_widget(self, index: int) -> None:
        """Widget command: paste chamber ``index`` into the previous app."""
        if self._load_chamber_into_clipboard(index) is None:
            if self._widget is not None:
                self._widget.flash_message(self.status_var.get(), error=True)
            return
        self.selected_index = index
        self._refresh_detail()
        self._set_status(f"Firing chamber {chamber_label(index)} from widget")
        target = self._paste_target
        if self._widget is not None:
            self._widget.hide()
        self._deliver_fire(index, target, from_widget=True)

    def _eject_from_widget(self, index: int) -> bool:
        """Widget command: eject ``index`` after the widget's double-Delete."""
        if core.get_chamber(index) is None:
            return False
        if not core.drop_item(index):
            return False
        core.force_save()
        self.selected_index = min(index, max(0, core.get_board_size() - 1))
        self.refresh()
        self._set_status(f"Ejected chamber {chamber_label(index)} from widget")
        return True

    def save_editor(self) -> None:
        content = self.editor.get("1.0", "end-1c")
        existing = core.get_board_item(self.selected_index)
        if existing is None:
            if not content:
                self._set_status("Type or paste some text before loading", error=True)
                return
            core.copy_to_board(content)
            self.selected_index = 0
            self._last_clipboard = content
            action = "Loaded a new round into chamber 01"
        else:
            if not core.update_board_item(self.selected_index, content):
                self._set_status("Could not save this chamber", error=True)
                return
            action = f"Saved chamber {chamber_label(self.selected_index)}"
        self.refresh()
        self._set_status(action)

    def eject_selected(self) -> None:
        if core.get_chamber(self.selected_index) is None:
            self._set_status("That chamber is already empty", error=True)
            return
        label = chamber_label(self.selected_index)
        if core.drop_item(self.selected_index):
            if self.selected_index >= core.get_board_size() and self.selected_index > 0:
                self.selected_index -= 1
            core.force_save()
            self.refresh()
            self._set_status(f"Ejected chamber {label}")

    def clear_board(self) -> None:
        loaded = core.get_board_size()
        if not loaded:
            self._set_status("The barrel is already empty")
            return
        rounds = "round" if loaded == 1 else "rounds"
        if messagebox.askyesno(
            "Clear the barrel?",
            f"This ejects all {loaded} loaded clipboard {rounds}. This cannot be undone.",
            parent=self.root,
        ):
            core.clear_board()
            self.selected_index = 0
            self.refresh()
            self._set_status("All chambers cleared")

    # ------------------------------------------------------------------
    # Monitoring, settings, and keyboard
    # ------------------------------------------------------------------
    def _schedule_clipboard_poll(self) -> None:
        self._poll_job = self.root.after(650, self._poll_clipboard)

    def _poll_clipboard(self) -> None:
        if self._closing:
            return
        try:
            current = pyperclip.paste()
            self._observe_clipboard(current)
        except pyperclip.PyperclipException:
            pass
        if self._copyboard_unfocused():
            # Remember where a later fire should land.  Done on this slower
            # tick so we do not spawn a window-query process every 90 ms; on
            # macOS the query is an osascript call, so it runs every third tick.
            self._target_poll_tick += 1
            if self._target_poll_tick >= TARGET_POLL_TICKS:
                self._target_poll_tick = 0
                self._capture_paste_target()
        self._schedule_clipboard_poll()

    def _observe_clipboard(self, current) -> bool:
        """Handle one clipboard reading.  Returns True when a round was captured.

        Only *external* copies load chamber 01.  Text CopyBoard itself placed
        on the clipboard (firing, copying, cycling by shortcut) is recognised
        via ``core.is_app_clipboard_write`` and skipped, so firing chamber 07
        never moves that round to chamber 01.
        """
        if not isinstance(current, str):
            return False
        if current == self._last_clipboard:
            return False
        self._last_clipboard = current
        if not current:
            return False
        if core.is_app_clipboard_write(current):
            return False
        if not self.auto_capture_var.get():
            return False
        core.copy_to_board(current)
        self.refresh(select_newest=True)
        self._set_status("New clipboard text auto-loaded into chamber 01")
        return True

    def _toggle_auto_capture(self) -> None:
        enabled = self.auto_capture_var.get()
        config.set("board", "auto_capture", enabled)
        self._update_capture_state()
        self._set_status(f"Auto-capture {'armed' if enabled else 'paused'}")

    def _update_capture_state(self) -> None:
        enabled = self.auto_capture_var.get()
        self.capture_state_var.set("CAPTURE ARMED" if enabled else "CAPTURE PAUSED")
        if hasattr(self, "capture_state_label"):
            self.capture_state_label.configure(fg=MINT if enabled else ACCENT)

    def _apply_always_on_top(self) -> None:
        try:
            self.root.attributes("-topmost", self.always_on_top_var.get())
        except tk.TclError:
            pass

    def _toggle_always_on_top(self) -> None:
        enabled = self.always_on_top_var.get()
        config.set("window", "always_on_top", enabled)
        self._apply_always_on_top()
        self._set_status(f"Window pin {'enabled' if enabled else 'disabled'}")

    def _bind_controls(self) -> None:
        # Digits select chambers through the shared dial: "7" selects 07,
        # "0" selects 10, and "1" then "4" selects 14 on a big enough cylinder.
        for key in range(10):
            self.root.bind(str(key), self._on_digit)
        self.root.bind("<Up>", lambda _event: self._cycle(-1))
        self.root.bind("<Left>", lambda _event: self._cycle(-1))
        self.root.bind("<Down>", lambda _event: self._cycle(1))
        self.root.bind("<Right>", lambda _event: self._cycle(1))
        self.root.bind("<Return>", self._on_return)
        self.root.bind("<Control-Return>", lambda _event: self.fire_selected())
        self.root.bind("<Delete>", self._on_delete)
        self.root.bind("<Control-s>", lambda _event: self.save_editor())
        self.root.bind("<Control-Shift-C>", lambda _event: self.capture_current())

    def _editing_text(self) -> bool:
        focused = self.root.focus_get()
        return focused == self.editor or focused == getattr(self, "capacity_spin", None)

    def _on_digit(self, event) -> None:
        if self._editing_text():
            return
        index = self._dial.press(event.char)
        if index is not None:
            self.select_chamber(index)

    def _cycle(self, direction: int) -> None:
        if not self._editing_text():
            self.select_chamber(
                (self.selected_index + direction) % self.chamber_count()
            )

    def _on_return(self, _event) -> None:
        if self._editing_text():
            return
        self.copy_selected()

    def _on_delete(self, _event) -> None:
        if not self._editing_text():
            self.eject_selected()

    def open_shortcuts(self) -> None:
        ShortcutsDialog(self.root, self)

    # ------------------------------------------------------------------
    # Global shortcuts
    # ------------------------------------------------------------------
    def _register_global_hotkeys(self) -> Dict[str, str]:
        """(Re)register every global shortcut for the current cylinder size."""
        try:
            report = hotkeys.setup_default_hotkeys(core)
            hotkeys.set_quick_paste_listener(self.notify_quick_paste)
            report["show_gui"] = hotkeys.register_action("show_gui", self.request_widget)
        except Exception:
            # Global key capture is optional; the in-window controls always work.
            report = {}
        self._hotkey_report = report
        self._update_hotkey_state()
        return report

    def _update_hotkey_state(self) -> None:
        report = self._hotkey_report
        active = sum(1 for status in report.values() if status == hotkeys.STATUS_REGISTERED)
        problems = sum(
            1
            for status in report.values()
            if status in (hotkeys.STATUS_FAILED, hotkeys.STATUS_DUPLICATE)
        )
        if not hotkeys.KEYBOARD_AVAILABLE or not report:
            self.hotkey_state_var.set("GLOBAL KEYS OFF")
            color = TEXT_FAINT
        elif problems:
            self.hotkey_state_var.set(f"GLOBAL KEYS: {active} ON · {problems} CONFLICT")
            color = ACCENT
        else:
            self.hotkey_state_var.set(f"GLOBAL KEYS: {active} ON")
            color = MINT
        if hasattr(self, "hotkey_state_label"):
            self.hotkey_state_label.configure(fg=color)

    def _set_status(
        self, message: str, error: bool = False, temporary: bool = True
    ) -> None:
        self.status_var.set(message)
        self.status_dot.delete("all")
        self.status_dot.create_oval(
            7, 7, 15, 15, fill=ERROR if error else MINT, outline=""
        )
        if self._status_job:
            try:
                self.root.after_cancel(self._status_job)
            except tk.TclError:
                pass
            self._status_job = None
        if temporary:
            self._status_job = self.root.after(
                3200, lambda: self._set_status("Ready", temporary=False)
            )

    def on_close(self) -> None:
        self._closing = True
        if self._poll_job:
            try:
                self.root.after_cancel(self._poll_job)
            except tk.TclError:
                pass
        config.set("window", "x", self.root.winfo_x())
        config.set("window", "y", self.root.winfo_y())
        config.set("window", "width", self.root.winfo_width())
        config.set("window", "height", self.root.winfo_height())
        core.force_save()
        hotkeys.unregister_all_hotkeys()
        self.root.destroy()


class ShortcutsDialog:
    """In-window controls plus the editable global shortcut map."""

    SHORTCUTS = (
        ("1 – 9, 0", "Select chambers 01 – 10"),
        ("1 then 2 … 6", "Chambers 11 – 16: two quick digits"),
        ("↑ ↓ or ← →", "Cycle around the cylinder"),
        ("Enter", "Copy the selected round"),
        ("Ctrl + Enter", "Fire, hide, and paste"),
        ("Ctrl + Shift + C", "Capture the current clipboard"),
        ("Ctrl + S", "Save edits in the content panel"),
        ("Delete", "Eject the selected round"),
        ("Double-click", "Copy a chamber immediately"),
        ("Widget: wheel, ↑ ↓", "Aim at a round (never fires)"),
        ("Widget: Enter, click", "Fire the aimed round"),
        ("Widget: Delete ×2", "Eject the aimed round"),
        ("Widget: Esc", "Back to this editor"),
    )

    STATUS_TEXT = {
        hotkeys.STATUS_REGISTERED: ("ACTIVE", MINT),
        hotkeys.STATUS_FAILED: ("REJECTED", ERROR),
        hotkeys.STATUS_DUPLICATE: ("DUPLICATE", ERROR),
        hotkeys.STATUS_UNAVAILABLE: ("NO BACKEND", TEXT_FAINT),
        hotkeys.STATUS_DISABLED: ("OFF", TEXT_FAINT),
        hotkeys.STATUS_INACTIVE: ("UNUSED", TEXT_FAINT),
    }

    def __init__(self, parent: tk.Tk, gui: Optional["CopyboardGUI"] = None):
        self.gui = gui
        self.win = tk.Toplevel(parent)
        self.win.title("CopyBoard Shortcuts")
        self.win.configure(bg=PANEL)
        self.win.geometry("1000x660")
        self.win.minsize(860, 520)
        self.win.transient(parent)
        self.win.grab_set()
        self._entries: Dict[str, tk.Entry] = {}
        self._status_labels: Dict[str, tk.Label] = {}
        self.note_var = tk.StringVar(master=self.win)

        tk.Label(
            self.win,
            text="QUICK-DRAW CONTROLS",
            bg=PANEL,
            fg=TEXT,
            font=(FONT, 18, "bold"),
        ).pack(anchor=tk.W, padx=28, pady=(24, 2))
        tk.Label(
            self.win,
            text="Keep one hand on the keyboard and one on the work.",
            bg=PANEL,
            fg=TEXT_DIM,
            font=(FONT, 10),
        ).pack(anchor=tk.W, padx=28, pady=(0, 14))

        columns = tk.Frame(self.win, bg=PANEL)
        columns.pack(fill=tk.BOTH, expand=True, padx=28)
        columns.grid_columnconfigure(0, weight=4, uniform="cols")
        columns.grid_columnconfigure(1, weight=5, uniform="cols")
        columns.grid_rowconfigure(1, weight=1)

        self._build_local_column(columns)
        self._build_global_column(columns)

        footer = tk.Frame(self.win, bg=PANEL)
        footer.pack(fill=tk.X, padx=28, pady=(10, 20))
        tk.Label(
            footer,
            textvariable=self.note_var,
            bg=PANEL,
            fg=TEXT_DIM,
            font=(MONO, 8),
            justify=tk.LEFT,
            anchor=tk.W,
            wraplength=700,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(
            footer,
            text="GOT IT",
            command=self.win.destroy,
            bg=ACCENT,
            fg=INK,
            activebackground=ACCENT_HOVER,
            activeforeground=INK,
            relief=tk.FLAT,
            bd=0,
            padx=22,
            pady=9,
            cursor="hand2",
            font=(MONO, 9, "bold"),
        ).pack(side=tk.RIGHT)
        self._refresh_statuses()

    def _build_local_column(self, parent: tk.Widget) -> None:
        tk.Label(
            parent, text="IN THIS WINDOW", bg=PANEL, fg=BRASS, font=(MONO, 9, "bold")
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        table = tk.Frame(parent, bg=PANEL_RAISED)
        table.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        for shortcut, description in self.SHORTCUTS:
            row = tk.Frame(table, bg=PANEL_RAISED)
            row.pack(fill=tk.X, padx=14, pady=5)
            tk.Label(
                row,
                text=shortcut,
                width=20,
                anchor=tk.W,
                bg=PANEL_RAISED,
                fg=BRASS,
                font=(MONO, 8, "bold"),
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=description,
                anchor=tk.W,
                bg=PANEL_RAISED,
                fg=TEXT,
                font=(FONT, 9),
            ).pack(side=tk.LEFT)

    def _build_global_column(self, parent: tk.Widget) -> None:
        heading = tk.Frame(parent, bg=PANEL)
        heading.grid(row=0, column=1, sticky="ew", pady=(0, 6))
        tk.Label(
            heading, text="ANYWHERE ON THE DESKTOP", bg=PANEL, fg=BRASS,
            font=(MONO, 9, "bold"),
        ).pack(side=tk.LEFT)
        tk.Label(
            heading,
            text="edit a combo, then APPLY",
            bg=PANEL,
            fg=TEXT_FAINT,
            font=(MONO, 8),
        ).pack(side=tk.RIGHT)

        shell = tk.Frame(parent, bg=PANEL_RAISED)
        shell.grid(row=1, column=1, sticky="nsew")
        shell.grid_rowconfigure(0, weight=1)
        shell.grid_columnconfigure(0, weight=1)
        scroller = tk.Canvas(shell, bg=PANEL_RAISED, bd=0, highlightthickness=0)
        scroller.grid(row=0, column=0, sticky="nsew")
        bar = tk.Scrollbar(
            shell, command=scroller.yview, bg=PANEL_RAISED, troughcolor=PANEL,
            activebackground=ACCENT, relief=tk.FLAT, bd=0, width=10,
        )
        bar.grid(row=0, column=1, sticky="ns")
        scroller.configure(yscrollcommand=bar.set)
        table = tk.Frame(scroller, bg=PANEL_RAISED)
        table_id = scroller.create_window((0, 0), window=table, anchor="nw")
        table.bind(
            "<Configure>",
            lambda _event: scroller.configure(scrollregion=scroller.bbox("all")),
        )
        scroller.bind(
            "<Configure>",
            lambda event: scroller.itemconfigure(table_id, width=event.width),
        )

        def _scroll(event):
            step = -1 if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0 else 1
            scroller.yview_scroll(step, "units")
            return "break"

        for widget in (scroller, table):
            widget.bind("<MouseWheel>", _scroll)
            widget.bind("<Button-4>", _scroll)
            widget.bind("<Button-5>", _scroll)
        self._scroll_table = _scroll
        count = self.gui.chamber_count() if self.gui is not None else MAX_CHAMBERS
        for action, label, combo, _status in hotkeys.describe_hotkeys(count):
            row = tk.Frame(table, bg=PANEL_RAISED)
            row.pack(fill=tk.X, padx=12, pady=2)
            for widget in (row,):
                widget.bind("<MouseWheel>", _scroll)
                widget.bind("<Button-4>", _scroll)
                widget.bind("<Button-5>", _scroll)
            name = tk.Label(
                row, text=label, width=32, anchor=tk.W, bg=PANEL_RAISED, fg=TEXT,
                font=(FONT, 9),
            )
            name.pack(side=tk.LEFT)
            name.bind("<MouseWheel>", _scroll)
            name.bind("<Button-4>", _scroll)
            name.bind("<Button-5>", _scroll)
            entry = tk.Entry(
                row,
                width=20,
                bg=PANEL_SOFT,
                fg=BRASS,
                insertbackground=ACCENT,
                relief=tk.FLAT,
                bd=0,
                font=(MONO, 8, "bold"),
                highlightthickness=1,
                highlightbackground=LINE,
                highlightcolor=ACCENT,
            )
            entry.insert(0, combo)
            entry.pack(side=tk.LEFT, ipady=3, padx=(0, 10))
            entry.bind("<Return>", lambda _event: self.apply())
            self._entries[action] = entry
            status = tk.Label(
                row, text="", width=11, anchor=tk.W, bg=PANEL_RAISED, fg=TEXT_FAINT,
                font=(MONO, 7, "bold"),
            )
            status.pack(side=tk.LEFT)
            self._status_labels[action] = status

        buttons = tk.Frame(parent, bg=PANEL)
        buttons.grid(row=2, column=1, sticky="e", pady=(8, 0))
        for text, command in (("RESET DEFAULTS", self.reset_defaults), ("APPLY", self.apply)):
            tk.Button(
                buttons,
                text=text,
                command=command,
                bg=PANEL_SOFT if text != "APPLY" else TEXT,
                fg=TEXT if text != "APPLY" else INK,
                activebackground=LINE,
                activeforeground=TEXT,
                relief=tk.FLAT,
                bd=0,
                padx=14,
                pady=6,
                cursor="hand2",
                font=(MONO, 8, "bold"),
            ).pack(side=tk.LEFT, padx=(8, 0))

    def _refresh_statuses(self) -> None:
        report = hotkeys.get_registration_report()
        count = self.gui.chamber_count() if self.gui is not None else MAX_CHAMBERS
        for action, _label, _combo, status in hotkeys.describe_hotkeys(count):
            status = report.get(action, status)
            text, color = self.STATUS_TEXT.get(status, (status.upper(), TEXT_FAINT))
            label = self._status_labels.get(action)
            if label is not None:
                label.configure(text=text, fg=color)
        if not hotkeys.KEYBOARD_AVAILABLE:
            self.note_var.set(
                "Global shortcuts need the optional 'keyboard' package "
                "(pip install 'copyboard-extension[hotkeys]'; needs root on Linux). "
                "Edited combos are saved and used once it is available."
            )
        else:
            duplicates = hotkeys.find_duplicate_combos(hotkeys.load_hotkey_config())
            if duplicates:
                combos = ", ".join(sorted(duplicates))
                self.note_var.set(f"Duplicate combos are not registered: {combos}")
            else:
                self.note_var.set("Chambers 11–16 default to Ctrl+Alt+Shift+1…6.")

    def apply(self) -> None:
        new_config = {
            action: hotkeys.normalize_combo(entry.get()) for action, entry in self._entries.items()
        }
        hotkeys.save_hotkey_config(new_config)
        for action, entry in self._entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, new_config[action])
        if self.gui is not None:
            self.gui._register_global_hotkeys()
        self._refresh_statuses()

    def reset_defaults(self) -> None:
        for action, entry in self._entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, hotkeys.default_combo(action))
        self.apply()


def main() -> None:
    root = tk.Tk(className="CopyBoard")
    gui = CopyboardGUI(root)
    gui._register_global_hotkeys()
    root.mainloop()


if __name__ == "__main__":
    main()
