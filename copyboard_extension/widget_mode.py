"""Compact, always-on-top quick-paste revolver.

The widget deliberately contains no clipboard or persistence logic.  It is a
small presentation surface over the same ten-round board used by the full UI.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import Callable, List, Optional, Sequence, Tuple


Point = Tuple[float, float]
ItemDescription = Tuple[str, str, str]


def radial_centers(
    count: int, center_x: float, center_y: float, radius: float
) -> List[Point]:
    """Return evenly spaced points, starting at twelve o'clock."""
    if count <= 0:
        return []
    return [
        (
            center_x + radius * math.cos(math.radians(-90 + i * 360 / count)),
            center_y + radius * math.sin(math.radians(-90 + i * 360 / count)),
        )
        for i in range(count)
    ]


def is_drag_gesture(start: Point, current: Point, threshold: float = 12) -> bool:
    """Distinguish an intentional drag from normal pointer jitter."""
    return math.hypot(current[0] - start[0], current[1] - start[1]) >= threshold


class QuickPasteWidget:
    """A compact radial view over a fixed collection of clipboard rounds."""

    SIZE = 390
    CHAMBER_RADIUS = 27
    BARREL_RADIUS = 128

    def __init__(
        self,
        parent: tk.Tk,
        get_items: Callable[[], Sequence[str]],
        describe_item: Callable[[str], ItemDescription],
        on_fire: Callable[[int], None],
        on_restore: Callable[[], None],
        initial_position: Point = (80, 80),
        on_move: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        self.parent = parent
        self.get_items = get_items
        self.describe_item = describe_item
        self.on_fire = on_fire
        self.on_restore = on_restore
        self.initial_position = (int(initial_position[0]), int(initial_position[1]))
        self.on_move = on_move

        self.window: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None
        self.preview_var = tk.StringVar(master=parent, value="Choose a loaded round")
        self._centers: List[Point] = []
        self._hovered: Optional[int] = None
        self._pressed: Optional[int] = None
        self._press_point: Point = (0, 0)
        self._dragging_round = False
        self._move_offset: Point = (0, 0)

    def show(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            self._build()
        assert self.window is not None
        self.redraw()
        self.window.deiconify()
        self.window.lift()

    def hide(self) -> None:
        if self.window is not None and self.window.winfo_exists():
            self.window.withdraw()

    def is_visible(self) -> bool:
        return bool(
            self.window is not None
            and self.window.winfo_exists()
            and self.window.state() != "withdrawn"
        )

    def redraw(self) -> None:
        if self.canvas is None or not self.canvas.winfo_exists():
            return

        canvas = self.canvas
        canvas.delete("all")
        items = list(self.get_items())
        cx = self.SIZE / 2
        cy = 204
        self._centers = radial_centers(10, cx, cy, self.BARREL_RADIUS)

        canvas.create_oval(
            cx - 166,
            cy - 166,
            cx + 166,
            cy + 166,
            fill="#242620",
            outline="#3C3E35",
            width=2,
        )
        canvas.create_oval(
            cx - 145,
            cy - 145,
            cx + 145,
            cy + 145,
            fill="#191B17",
            outline="#30322B",
            width=2,
        )

        for index, (x, y) in enumerate(self._centers):
            occupied = index < len(items)
            hovered = index == self._hovered
            pressed = index == self._pressed
            outer = "#FF6B35" if pressed else ("#C7A86B" if hovered else "#3C3E35")
            canvas.create_oval(
                x - self.CHAMBER_RADIUS - 5,
                y - self.CHAMBER_RADIUS - 5,
                x + self.CHAMBER_RADIUS + 5,
                y + self.CHAMBER_RADIUS + 5,
                fill="#2C2E27",
                outline=outer,
                width=3 if hovered or pressed else 2,
            )
            canvas.create_oval(
                x - self.CHAMBER_RADIUS,
                y - self.CHAMBER_RADIUS,
                x + self.CHAMBER_RADIUS,
                y + self.CHAMBER_RADIUS,
                fill="#141512" if occupied else "#20221E",
                outline="#090A08",
                width=2,
            )
            canvas.create_text(
                x,
                y - 8,
                text=f"{index + 1:02d}",
                fill="#C7A86B" if occupied else "#6F7167",
                font=("DejaVu Sans Mono", 9, "bold"),
            )
            if occupied:
                _kind, mark, _preview = self.describe_item(items[index])
                canvas.create_text(
                    x,
                    y + 10,
                    text=mark,
                    fill="#F2EEDF",
                    font=("DejaVu Sans Mono", 8, "bold"),
                )
            else:
                canvas.create_text(
                    x, y + 9, text="—", fill="#6F7167", font=("DejaVu Sans", 10)
                )

        canvas.create_oval(
            cx - 61,
            cy - 61,
            cx + 61,
            cy + 61,
            fill="#141512",
            outline="#C7A86B",
            width=2,
        )
        canvas.create_text(
            cx,
            cy - 12,
            text=f"{len(items):02d}",
            fill="#F2EEDF",
            font=("DejaVu Sans Mono", 22, "bold"),
        )
        canvas.create_text(
            cx,
            cy + 13,
            text="/ 10 LOADED",
            fill="#C7A86B",
            font=("DejaVu Sans Mono", 8, "bold"),
        )
        canvas.create_text(
            cx,
            cy + 34,
            text="CLICK OR DRAG",
            fill="#8FB996",
            font=("DejaVu Sans Mono", 7, "bold"),
        )

    def _build(self) -> None:
        x, y = self.initial_position
        window = tk.Toplevel(self.parent)
        self.window = window
        window.title("CopyBoard Quick Paste")
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        try:
            window.attributes("-alpha", 0.97)
        except tk.TclError:
            pass
        window.configure(bg="#141512")
        window.geometry(f"{self.SIZE}x{self.SIZE + 56}+{x}+{y}")
        window.bind("<Escape>", lambda _event: self.on_restore())
        window.bind("<Button-3>", lambda _event: self.on_restore())

        title = tk.Frame(window, bg="#1B1D19", height=42, cursor="fleur")
        title.pack(fill=tk.X)
        title.pack_propagate(False)
        tk.Label(
            title,
            text="COPYBOARD  /  QUICK PASTE",
            bg="#1B1D19",
            fg="#F2EEDF",
            font=("DejaVu Sans Mono", 9, "bold"),
        ).pack(side=tk.LEFT, padx=14)
        full = tk.Label(
            title,
            text="FULL  ↗",
            bg="#1B1D19",
            fg="#FF6B35",
            cursor="hand2",
            font=("DejaVu Sans Mono", 8, "bold"),
        )
        full.pack(side=tk.RIGHT, padx=14)
        full.bind("<Button-1>", lambda _event: self.on_restore())

        for widget in (title, *title.winfo_children()[:1]):
            widget.bind("<Button-1>", self._begin_move)
            widget.bind("<B1-Motion>", self._move_window)
            widget.bind("<ButtonRelease-1>", self._end_move)

        self.canvas = tk.Canvas(
            window,
            width=self.SIZE,
            height=self.SIZE,
            bg="#1B1D19",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.canvas.pack(fill=tk.X)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_round_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        tk.Label(
            window,
            textvariable=self.preview_var,
            anchor=tk.W,
            bg="#242620",
            fg="#A6A394",
            padx=14,
            font=("DejaVu Sans Mono", 8),
        ).pack(fill=tk.BOTH, expand=True)
        self.redraw()

    def _chamber_at(self, x: float, y: float) -> Optional[int]:
        for index, (cx, cy) in enumerate(self._centers):
            if math.hypot(x - cx, y - cy) <= self.CHAMBER_RADIUS + 8:
                return index
        return None

    def _on_motion(self, event) -> None:
        hovered = self._chamber_at(event.x, event.y)
        if hovered == self._hovered:
            return
        self._hovered = hovered
        items = list(self.get_items())
        if hovered is None:
            self.preview_var.set("Choose a loaded round")
        elif hovered < len(items):
            kind, _mark, preview = self.describe_item(items[hovered])
            self.preview_var.set(f"{hovered + 1:02d}  {kind}  /  {preview}")
        else:
            self.preview_var.set(f"{hovered + 1:02d}  EMPTY CHAMBER")
        self.redraw()

    def _on_leave(self, _event) -> None:
        if self._pressed is None:
            self._hovered = None
            self.preview_var.set("Choose a loaded round")
            self.redraw()

    def _on_press(self, event) -> None:
        self._pressed = self._chamber_at(event.x, event.y)
        self._press_point = (event.x_root, event.y_root)
        self._dragging_round = False
        self.redraw()

    def _on_round_drag(self, event) -> None:
        if self._pressed is None:
            return
        if is_drag_gesture(self._press_point, (event.x_root, event.y_root)):
            self._dragging_round = True
            self.preview_var.set(
                f"ROUND {self._pressed + 1:02d} ARMED  /  RELEASE TO PASTE"
            )
            if self.canvas is not None:
                self.canvas.configure(cursor="target")

    def _on_release(self, _event) -> None:
        index = self._pressed
        self._pressed = None
        self._dragging_round = False
        if self.canvas is not None:
            self.canvas.configure(cursor="hand2")
        if index is not None and index < len(self.get_items()):
            self.on_fire(index)
        self.redraw()

    def _begin_move(self, event) -> None:
        assert self.window is not None
        self._move_offset = (
            event.x_root - self.window.winfo_x(),
            event.y_root - self.window.winfo_y(),
        )

    def _move_window(self, event) -> None:
        assert self.window is not None
        x = int(event.x_root - self._move_offset[0])
        y = int(event.y_root - self._move_offset[1])
        self.window.geometry(f"+{x}+{y}")

    def _end_move(self, _event) -> None:
        if self.window is not None and self.on_move is not None:
            self.on_move(self.window.winfo_x(), self.window.winfo_y())
