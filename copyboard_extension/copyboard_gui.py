#!/usr/bin/env python3
"""CopyBoard's revolver-first desktop interface.

The board is deliberately represented as ten fixed, visible chambers. New
clipboard entries arrive in chamber 1 and older entries rotate clockwise.
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
CHAMBER_COUNT = 10


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
    """A polished ten-chamber clipboard controller."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CopyBoard — 10 Chamber Clipboard")
        self.root.configure(bg=INK)
        self._app_icon: Optional[tk.PhotoImage] = None
        self._set_app_icon()
        self.root.geometry(self._initial_geometry())
        self.root.minsize(940, 640)

        # This interface is intentionally a ten-round tool, even if an older
        # config file previously allowed a larger generic clipboard history.
        core.set_max_board_size(CHAMBER_COUNT)

        self.selected_index = 0
        self.hovered_index: Optional[int] = None
        self._chamber_centers: Dict[int, Tuple[float, float]] = {}
        self._poll_job: Optional[str] = None
        self._status_job: Optional[str] = None
        self._closing = False
        self._widget: Optional[QuickPasteWidget] = None
        self._widget_target = None
        self._ui_actions: queue.SimpleQueue[str] = queue.SimpleQueue()

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

        try:
            self._last_clipboard = pyperclip.paste()
        except pyperclip.PyperclipException:
            self._last_clipboard = ""

        self._build_ui()
        self._bind_controls()
        self._apply_always_on_top()
        self.refresh()
        self._schedule_clipboard_poll()
        self._schedule_ui_action_poll()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

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
            text="TEN-CHAMBER CLIPBOARD  /  MK II",
            bg=INK,
            fg=BRASS,
            font=(MONO, 9, "bold"),
        ).pack(anchor=tk.W, pady=(1, 0))

        actions = tk.Frame(header, bg=INK)
        actions.pack(side=tk.RIGHT, fill=tk.Y)
        self._make_button(
            actions, "CAPTURE CURRENT", self.capture_current, variant="accent"
        ).pack(side=tk.LEFT, padx=(0, 8), pady=12)
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
            text="CLICK TO SELECT   •   DOUBLE-CLICK TO COPY   •   1–9 / 0 SELECT",
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
        width = max(520, self.canvas.winfo_width())
        height = max(510, self.canvas.winfo_height())
        cx = width / 2
        cy = height / 2 + 4
        radius = min(width, height) * 0.34
        chamber_radius = max(32, min(44, radius * 0.23))
        items = core.get_board()

        self.canvas.create_oval(
            cx - radius - 69,
            cy - radius - 61,
            cx + radius + 69,
            cy + radius + 77,
            fill="#10110F",
            outline="",
        )
        self.canvas.create_oval(
            cx - radius - 66,
            cy - radius - 66,
            cx + radius + 66,
            cy + radius + 66,
            fill=PANEL_RAISED,
            outline=LINE,
            width=2,
        )
        self.canvas.create_oval(
            cx - radius - 40,
            cy - radius - 40,
            cx + radius + 40,
            cy + radius + 40,
            fill="#191B17",
            outline="#30322B",
            width=2,
        )

        self._chamber_centers.clear()
        for index in range(CHAMBER_COUNT):
            angle = math.radians(-90 + index * (360 / CHAMBER_COUNT))
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
            cx, cy + 14, text="/ 10 LOADED", fill=BRASS, font=(MONO, 8, "bold")
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
            y - 13,
            text=f"{index + 1:02d}",
            fill=INK if selected else (BRASS if occupied else TEXT_FAINT),
            font=(MONO, 12, "bold"),
        )
        if occupied:
            kind, mark = classify_clip(items[index])
            self.canvas.create_text(
                x, y + 9, text=mark, fill=TEXT, font=(MONO, 10, "bold")
            )
            self.canvas.create_text(
                x,
                y + radius + 17,
                text=kind,
                fill=ACCENT if selected else TEXT_FAINT,
                font=(MONO, 7, "bold"),
            )
        else:
            self.canvas.create_text(
                x, y + 10, text="—", fill=TEXT_FAINT, font=(MONO, 12)
            )

    def _chamber_at(self, x: int, y: int) -> Optional[int]:
        for index, (cx, cy) in self._chamber_centers.items():
            if math.hypot(x - cx, y - cy) <= 52:
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
                    else f"Chamber {hovered + 1:02d} is empty",
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
        self.selected_index = max(0, min(CHAMBER_COUNT - 1, index))
        self._refresh_detail()
        self.draw_revolver()

    # ------------------------------------------------------------------
    # Board actions
    # ------------------------------------------------------------------
    def refresh(self, select_newest: bool = False) -> None:
        if select_newest:
            self.selected_index = 0
        self.selected_index = min(self.selected_index, CHAMBER_COUNT - 1)
        self._refresh_detail()
        self.draw_revolver()

    def _refresh_detail(self) -> None:
        content = core.get_board_item(self.selected_index)
        slot = self.selected_index + 1
        self.slot_var.set(f"CHAMBER {slot:02d} / {CHAMBER_COUNT:02d}")
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

    def copy_selected(self) -> None:
        content = core.get_board_item(self.selected_index)
        if content is None:
            self._set_status("That chamber is empty", error=True)
            return
        try:
            pyperclip.copy(content)
        except pyperclip.PyperclipException as exc:
            self._set_status(f"Could not reach clipboard: {exc}", error=True)
            return
        self._last_clipboard = content
        self._set_status(f"Chamber {self.selected_index + 1:02d} copied")

    def fire_selected(self) -> None:
        content = core.get_board_item(self.selected_index)
        if content is None:
            self._set_status("That chamber is empty", error=True)
            return
        try:
            pyperclip.copy(content)
        except pyperclip.PyperclipException as exc:
            self._set_status(f"Could not reach clipboard: {exc}", error=True)
            return
        self._last_clipboard = content
        self._set_status(f"Fired chamber {self.selected_index + 1:02d}")
        self.root.iconify()
        self.root.after(220, paste_helper.paste_current_clipboard)

    # ------------------------------------------------------------------
    # Compact quick-paste widget
    # ------------------------------------------------------------------
    def request_widget(self) -> None:
        """Thread-safe entry point used by the global shortcut callback."""
        self._ui_actions.put("widget")

    def _schedule_ui_action_poll(self) -> None:
        if not self._closing:
            self.root.after(90, self._poll_ui_actions)

    def _poll_ui_actions(self) -> None:
        if self._closing:
            return
        try:
            while True:
                action = self._ui_actions.get_nowait()
                if action == "widget":
                    self.open_widget()
        except queue.Empty:
            pass

        if (
            self._widget is not None
            and self._widget.is_visible()
            and self.root.focus_displayof() is None
        ):
            target = paste_helper.capture_active_window()
            if target is not None:
                self._widget_target = target
        self._schedule_ui_action_poll()

    def open_widget(self) -> None:
        """Collapse the editor into the ten-round quick-paste overlay."""
        if self._widget is not None and self._widget.is_visible():
            self._restore_from_widget()
            return

        target = paste_helper.capture_active_window()
        if target is not None:
            self._widget_target = target

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
            )
        self.root.withdraw()
        self._widget.show()

    def _describe_widget_item(self, content: str) -> Tuple[str, str, str]:
        kind, mark = classify_clip(content)
        return kind, mark, compact_preview(content, limit=35)

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
        content = core.get_board_item(index)
        if content is None:
            return
        try:
            pyperclip.copy(content)
        except pyperclip.PyperclipException:
            return

        self.selected_index = index
        self._last_clipboard = content
        self._set_status(f"Fired chamber {index + 1:02d} from widget")
        if self._widget is not None:
            self._widget.hide()
        paste_helper.restore_active_window(self._widget_target)
        self.root.after(180, self._complete_widget_paste)

    def _complete_widget_paste(self) -> None:
        paste_helper.paste_current_clipboard()
        if not self._closing and self._widget is not None:
            self.root.after(280, self._widget.show)

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
            action = f"Saved chamber {self.selected_index + 1:02d}"
        self.refresh()
        self._set_status(action)

    def eject_selected(self) -> None:
        if core.get_board_item(self.selected_index) is None:
            self._set_status("That chamber is already empty", error=True)
            return
        slot = self.selected_index + 1
        if core.drop_item(self.selected_index):
            if self.selected_index >= core.get_board_size() and self.selected_index > 0:
                self.selected_index -= 1
            core.force_save()
            self.refresh()
            self._set_status(f"Ejected chamber {slot:02d}")

    def clear_board(self) -> None:
        if not core.get_board():
            self._set_status("The barrel is already empty")
            return
        if messagebox.askyesno(
            "Clear the barrel?",
            "This ejects all ten clipboard rounds. This cannot be undone.",
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
            if (
                self.auto_capture_var.get()
                and isinstance(current, str)
                and current
                and current != self._last_clipboard
            ):
                self._last_clipboard = current
                core.copy_to_board(current)
                self.refresh(select_newest=True)
                self._set_status("New clipboard text auto-loaded into chamber 01")
            elif isinstance(current, str):
                self._last_clipboard = current
        except pyperclip.PyperclipException:
            pass
        self._schedule_clipboard_poll()

    def _toggle_auto_capture(self) -> None:
        enabled = self.auto_capture_var.get()
        config.set("board", "auto_capture", enabled)
        self._set_status(f"Auto-capture {'armed' if enabled else 'paused'}")

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
        for key in range(1, 10):
            self.root.bind(
                str(key), lambda _event, index=key - 1: self._select_from_key(index)
            )
        self.root.bind("0", lambda _event: self._select_from_key(9))
        self.root.bind("<Up>", lambda _event: self._cycle(-1))
        self.root.bind("<Left>", lambda _event: self._cycle(-1))
        self.root.bind("<Down>", lambda _event: self._cycle(1))
        self.root.bind("<Right>", lambda _event: self._cycle(1))
        self.root.bind("<Return>", self._on_return)
        self.root.bind("<Control-Return>", lambda _event: self.fire_selected())
        self.root.bind("<Delete>", self._on_delete)
        self.root.bind("<Control-s>", lambda _event: self.save_editor())
        self.root.bind("<Control-Shift-C>", lambda _event: self.capture_current())

    def _select_from_key(self, index: int) -> None:
        if self.root.focus_get() != self.editor:
            self.select_chamber(index)

    def _cycle(self, direction: int) -> None:
        if self.root.focus_get() != self.editor:
            self.select_chamber((self.selected_index + direction) % CHAMBER_COUNT)

    def _on_return(self, _event) -> None:
        if self.root.focus_get() == self.editor:
            return
        self.copy_selected()

    def _on_delete(self, _event) -> None:
        if self.root.focus_get() != self.editor:
            self.eject_selected()

    def open_shortcuts(self) -> None:
        ShortcutsDialog(self.root)

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
    """Small, styled reference for the revolver's controls."""

    SHORTCUTS = (
        ("1 – 9, 0", "Select chambers 01 – 10"),
        ("↑ ↓ or ← →", "Cycle around the barrel"),
        ("Enter", "Copy the selected round"),
        ("Ctrl + Enter", "Fire, hide, and paste"),
        ("Ctrl + Shift + C", "Capture the current clipboard"),
        ("Ctrl + S", "Save edits in the content panel"),
        ("Delete", "Eject the selected round"),
        ("Double-click", "Copy a chamber immediately"),
    )

    def __init__(self, parent: tk.Tk):
        self.win = tk.Toplevel(parent)
        self.win.title("CopyBoard Shortcuts")
        self.win.configure(bg=PANEL)
        self.win.geometry("520x470")
        self.win.resizable(False, False)
        self.win.transient(parent)
        self.win.grab_set()
        tk.Label(
            self.win,
            text="QUICK-DRAW CONTROLS",
            bg=PANEL,
            fg=TEXT,
            font=(FONT, 18, "bold"),
        ).pack(anchor=tk.W, padx=28, pady=(28, 4))
        tk.Label(
            self.win,
            text="Keep one hand on the keyboard and one on the work.",
            bg=PANEL,
            fg=TEXT_DIM,
            font=(FONT, 10),
        ).pack(anchor=tk.W, padx=28, pady=(0, 20))

        table = tk.Frame(self.win, bg=PANEL_RAISED)
        table.pack(fill=tk.BOTH, expand=True, padx=28, pady=(0, 18))
        for shortcut, description in self.SHORTCUTS:
            row = tk.Frame(table, bg=PANEL_RAISED)
            row.pack(fill=tk.X, padx=16, pady=7)
            tk.Label(
                row,
                text=shortcut,
                width=18,
                anchor=tk.W,
                bg=PANEL_RAISED,
                fg=BRASS,
                font=(MONO, 9, "bold"),
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=description,
                anchor=tk.W,
                bg=PANEL_RAISED,
                fg=TEXT,
                font=(FONT, 9),
            ).pack(side=tk.LEFT)

        tk.Button(
            self.win,
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
        ).pack(anchor=tk.E, padx=28, pady=(0, 24))


def main() -> None:
    root = tk.Tk(className="CopyBoard")
    gui = CopyboardGUI(root)
    try:
        hotkeys.setup_default_hotkeys(core)
        hotkeys.register_hotkey(
            config.get("hotkeys", "show_gui", "ctrl+alt+c"), gui.request_widget
        )
    except Exception:
        # Global key capture is optional; the in-window controls always work.
        pass
    root.mainloop()


if __name__ == "__main__":
    main()
