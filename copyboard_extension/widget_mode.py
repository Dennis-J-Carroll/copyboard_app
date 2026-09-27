"""Compact, always-on-top quick-paste revolver.

The widget deliberately contains no clipboard or persistence logic.  It is a
small presentation surface over the same board used by the full UI: it reads
chambers through ``get_items`` and asks the host to fire, eject, or restore
through callbacks.  It never mutates the board itself.

Input it understands while visible and under the pointer:

* hover / click / hold-and-drag a chamber  – preview, fire
* mouse wheel (``<MouseWheel>`` and X11 Button-4/5) – move the highlight only
* ``1``–``9``, ``0`` and two-digit entry (``1`` then ``2``)  – select a chamber
* arrow keys                                          – move the highlight
* Return / space                                      – fire the highlighted chamber
* Delete twice                                        – eject the highlighted chamber
* Escape / right-click / "FULL"                       – restore the editor
"""

from __future__ import annotations

import math
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from .chambers import (
    DEFAULT_CHAMBERS,
    ChamberDial,
    chamber_label,
    normalize_chamber_count,
)

Point = Tuple[float, float]
ItemDescription = Tuple[str, str, str]

# Palette shared with the editor (kept literal here so the widget stays
# importable without the editor module).
INK = "#141512"
PANEL = "#1B1D19"
PANEL_RAISED = "#242620"
PANEL_SOFT = "#2C2E27"
LINE = "#3C3E35"
LINE_DEEP = "#30322B"
TEXT = "#F2EEDF"
TEXT_DIM = "#A6A394"
TEXT_FAINT = "#6F7167"
ACCENT = "#FF6B35"
BRASS = "#C7A86B"
MINT = "#8FB996"
EMPTY = "#20221E"
ERROR = "#E56B6F"
MONO = "DejaVu Sans Mono"
SANS = "DejaVu Sans"

IDLE_PROMPT = "WHEEL OR ↑↓ TO AIM   •   ENTER OR CLICK TO FIRE"
CHAMBER_HIT_PADDING = 8  # extra pixels of forgiveness around each chamber
FIRE_FLASH_MS = 70        # brief accent flash before the host hides the widget
EJECT_CONFIRM_MS = 2500   # second Delete must arrive within this window


@dataclass(frozen=True)
class WidgetLayout:
    """Geometry for a cylinder of ``count`` chambers.

    Ten chambers reproduce the original 390 px widget exactly; larger
    cylinders widen the ring and shrink the chambers just enough that
    neighbouring hit targets never overlap.
    """

    count: int
    size: int
    ring_radius: float
    chamber_radius: float
    hub_radius: float
    center_y: float

    @property
    def center_x(self) -> float:
        return self.size / 2

    @property
    def hit_radius(self) -> float:
        return self.chamber_radius + CHAMBER_HIT_PADDING

    @property
    def neighbour_spacing(self) -> float:
        """Distance between the centres of two adjacent chambers."""
        return 2 * self.ring_radius * math.sin(math.pi / self.count)


def widget_layout(count: object) -> WidgetLayout:
    """Return the geometry used to draw ``count`` chambers (10–16)."""
    count = normalize_chamber_count(count)
    extra = count - DEFAULT_CHAMBERS
    ring_radius = 128.0 + extra * 4.7
    chamber_radius = max(21.0, 27.0 - extra * 0.85)
    size = int(math.ceil(2 * (ring_radius + chamber_radius + 5) + 70))
    size += size % 2  # keep the canvas centre on a whole pixel
    return WidgetLayout(
        count=count,
        size=size,
        ring_radius=ring_radius,
        chamber_radius=chamber_radius,
        hub_radius=61.0,
        center_y=size / 2 + 9,
    )


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


def wheel_step(num: object = None, delta: object = 0) -> int:
    """Translate a Tk wheel event into -1 (previous), +1 (next), or 0.

    X11 reports the wheel as Button-4 (up) / Button-5 (down) with no delta;
    Windows and macOS report ``<MouseWheel>`` with a signed ``delta`` (positive
    when scrolling up).  Scrolling up moves towards chamber 01.
    """
    if num == 4:
        return -1
    if num == 5:
        return 1
    try:
        value = float(delta or 0)
    except (TypeError, ValueError):
        return 0
    if value > 0:
        return -1
    if value < 0:
        return 1
    return 0


def next_loaded_index(current: Optional[int], loaded: int, step: int) -> Optional[int]:
    """Walk the highlight through loaded chambers only, wrapping at the ends."""
    if loaded <= 0:
        return None
    if current is None or not 0 <= current < loaded:
        return 0 if step >= 0 else loaded - 1
    return (current + step) % loaded


class QuickPasteWidget:
    """A compact radial view over a fixed collection of clipboard rounds."""

    def __init__(
        self,
        parent: tk.Tk,
        get_items: Callable[[], Sequence[str]],
        describe_item: Callable[[str], ItemDescription],
        on_fire: Callable[[int], None],
        on_restore: Callable[[], None],
        initial_position: Point = (80, 80),
        on_move: Optional[Callable[[int, int], None]] = None,
        get_count: Optional[Callable[[], int]] = None,
        on_eject: Optional[Callable[[int], bool]] = None,
    ) -> None:
        self.parent = parent
        self.get_items = get_items
        self.describe_item = describe_item
        self.on_fire = on_fire
        self.on_restore = on_restore
        self.on_eject = on_eject
        self.get_count = get_count or (lambda: DEFAULT_CHAMBERS)
        self.initial_position = (int(initial_position[0]), int(initial_position[1]))
        self.on_move = on_move

        self.window: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None
        self.preview_label: Optional[tk.Label] = None
        self.preview_var = tk.StringVar(master=parent, value=IDLE_PROMPT)
        self.layout = widget_layout(self.get_count())
        self._centers: List[Point] = []
        self._hovered: Optional[int] = None
        self._pressed: Optional[int] = None
        self._selected: int = 0
        self._flashing: Optional[int] = None
        self._eject_armed: Optional[int] = None
        self._eject_job: Optional[str] = None
        self._message_job: Optional[str] = None
        self._press_point: Point = (0, 0)
        self._dragging_round = False
        self._move_offset: Point = (0, 0)
        self._dial = ChamberDial(self.get_count)

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------
    def show(self) -> None:
        if self.window is None or not self.window.winfo_exists():
            self._build()
        assert self.window is not None
        self._sync_layout()
        self.redraw()
        self._show_selected_preview()
        self.window.deiconify()
        self.window.lift()

    def hide(self) -> None:
        self._disarm_eject()
        if self.window is not None and self.window.winfo_exists():
            self.window.withdraw()

    def is_visible(self) -> bool:
        return bool(
            self.window is not None
            and self.window.winfo_exists()
            and self.window.state() != "withdrawn"
        )

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    @property
    def selected_index(self) -> int:
        return self._selected

    def select(self, index: Optional[int]) -> None:
        """Move the highlight (never fires)."""
        if index is None:
            return
        count = self.layout.count
        self._selected = max(0, min(count - 1, int(index)))
        self._disarm_eject()
        self._show_selected_preview()
        self.redraw()

    def select_relative(self, step: int) -> None:
        loaded = len(self.get_items())
        target = next_loaded_index(self._selected, loaded, step)
        if target is None:
            self.flash_message("No rounds loaded yet", error=True)
            return
        self.select(target)

    def flash_message(self, text: str, error: bool = False, hold_ms: int = 2600) -> None:
        """Show a short status line in the preview strip, then return to idle."""
        self._set_preview(text, error=error)
        if self.window is None or not self.window.winfo_exists():
            return
        if self._message_job is not None:
            try:
                self.window.after_cancel(self._message_job)
            except tk.TclError:
                pass
        self._message_job = self.window.after(hold_ms, self._show_selected_preview)

    def _set_preview(self, text: str, error: bool = False) -> None:
        self.preview_var.set(text)
        if self.preview_label is not None and self.preview_label.winfo_exists():
            self.preview_label.configure(fg=ERROR if error else TEXT_DIM)

    def _describe(self, index: int) -> str:
        items = self.get_items()
        if 0 <= index < len(items):
            kind, _mark, preview = self.describe_item(items[index])
            return f"{chamber_label(index)}  {kind}  /  {preview}"
        return f"{chamber_label(index)}  EMPTY CHAMBER"

    def _show_selected_preview(self) -> None:
        self._message_job = None
        if self._eject_armed is not None:
            return
        items = self.get_items()
        if not items:
            self._set_preview("EMPTY CYLINDER  /  COPY SOMETHING TO LOAD CHAMBER 01")
        elif self._selected < len(items):
            self._set_preview(self._describe(self._selected))
        else:
            self._set_preview(IDLE_PROMPT)

    def _sync_layout(self) -> None:
        layout = widget_layout(self.get_count())
        if layout != self.layout or not self._centers:
            self.layout = layout
            if self.window is not None and self.window.winfo_exists():
                self.window.geometry(f"{layout.size}x{layout.size + 56}")
            if self.canvas is not None and self.canvas.winfo_exists():
                self.canvas.configure(width=layout.size, height=layout.size)
        self._selected = max(0, min(layout.count - 1, self._selected))

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def redraw(self) -> None:
        if self.canvas is None or not self.canvas.winfo_exists():
            return

        canvas = self.canvas
        canvas.delete("all")
        items = list(self.get_items())
        layout = self.layout
        cx, cy = layout.center_x, layout.center_y
        ring = layout.ring_radius
        radius = layout.chamber_radius
        self._centers = radial_centers(layout.count, cx, cy, ring)

        canvas.create_oval(
            cx - ring - 38, cy - ring - 38, cx + ring + 38, cy + ring + 38,
            fill=PANEL_RAISED, outline=LINE, width=2,
        )
        canvas.create_oval(
            cx - ring - 17, cy - ring - 17, cx + ring + 17, cy + ring + 17,
            fill="#191B17", outline=LINE_DEEP, width=2,
        )

        for index, (x, y) in enumerate(self._centers):
            occupied = index < len(items)
            hovered = index == self._hovered
            pressed = index == self._pressed or index == self._flashing
            selected = index == self._selected
            armed = index == self._eject_armed
            if armed:
                outer_fill, outline, width = ERROR, ERROR, 3
            elif pressed:
                outer_fill, outline, width = ACCENT, ACCENT, 3
            elif selected:
                outer_fill, outline, width = PANEL_SOFT, ACCENT, 3
            elif hovered:
                outer_fill, outline, width = PANEL_SOFT, BRASS, 3
            else:
                outer_fill, outline, width = PANEL_SOFT, LINE, 2
            canvas.create_oval(
                x - radius - 5, y - radius - 5, x + radius + 5, y + radius + 5,
                fill=outer_fill, outline=outline, width=width,
            )
            canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill=INK if occupied else EMPTY, outline="#090A08", width=2,
            )
            number_color = ACCENT if selected and occupied else (
                BRASS if occupied else TEXT_FAINT
            )
            canvas.create_text(
                x, y - 8, text=chamber_label(index), fill=number_color,
                font=(MONO, 9, "bold"),
            )
            if occupied:
                _kind, mark, _preview = self.describe_item(items[index])
                canvas.create_text(
                    x, y + 10, text=mark, fill=TEXT, font=(MONO, 8, "bold")
                )
            else:
                canvas.create_text(
                    x, y + 9, text="—", fill=TEXT_FAINT, font=(SANS, 10)
                )

        hub = layout.hub_radius
        canvas.create_oval(
            cx - hub, cy - hub, cx + hub, cy + hub,
            fill=INK, outline=BRASS, width=2,
        )
        canvas.create_text(
            cx, cy - 12, text=f"{len(items):02d}", fill=TEXT, font=(MONO, 22, "bold")
        )
        canvas.create_text(
            cx, cy + 13, text=f"/ {layout.count:02d} LOADED", fill=BRASS,
            font=(MONO, 8, "bold"),
        )
        canvas.create_text(
            cx, cy + 34, text="WHEEL · CLICK", fill=MINT,
            font=(MONO, 7, "bold"),
        )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self) -> None:
        x, y = self.initial_position
        layout = widget_layout(self.get_count())
        self.layout = layout
        window = tk.Toplevel(self.parent)
        self.window = window
        window.title("CopyBoard Quick Paste")
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        try:
            window.attributes("-alpha", 0.97)
        except tk.TclError:
            pass
        window.configure(bg=INK)
        window.geometry(f"{layout.size}x{layout.size + 56}+{x}+{y}")
        window.bind("<Escape>", lambda _event: self.on_restore())
        window.bind("<Button-3>", lambda _event: self.on_restore())
        window.bind("<Return>", lambda _event: self.fire_selected())
        window.bind("<KP_Enter>", lambda _event: self.fire_selected())
        window.bind("<space>", lambda _event: self.fire_selected())
        window.bind("<Up>", lambda _event: self.select_relative(-1))
        window.bind("<Left>", lambda _event: self.select_relative(-1))
        window.bind("<Down>", lambda _event: self.select_relative(1))
        window.bind("<Right>", lambda _event: self.select_relative(1))
        window.bind("<Delete>", lambda _event: self.request_eject())
        window.bind("<BackSpace>", lambda _event: self.request_eject())
        window.bind("<Key>", self._on_key)

        title = tk.Frame(window, bg=PANEL, height=42, cursor="fleur")
        title.pack(fill=tk.X)
        title.pack_propagate(False)
        tk.Label(
            title, text="COPYBOARD  /  QUICK PASTE", bg=PANEL, fg=TEXT,
            font=(MONO, 9, "bold"),
        ).pack(side=tk.LEFT, padx=14)
        full = tk.Label(
            title, text="FULL  ↗", bg=PANEL, fg=ACCENT, cursor="hand2",
            font=(MONO, 8, "bold"),
        )
        full.pack(side=tk.RIGHT, padx=14)
        full.bind("<Button-1>", lambda _event: self.on_restore())

        for widget in (title, *title.winfo_children()[:1]):
            widget.bind("<Button-1>", self._begin_move)
            widget.bind("<B1-Motion>", self._move_window)
            widget.bind("<ButtonRelease-1>", self._end_move)

        self.canvas = tk.Canvas(
            window, width=layout.size, height=layout.size, bg=PANEL, bd=0,
            highlightthickness=0, cursor="hand2",
        )
        self.canvas.pack(fill=tk.X)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_round_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        # Wheel selection is bound to the canvas only: it works while the
        # pointer is over the widget and never touches other applications.
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", self._on_wheel)
        self.canvas.bind("<Button-5>", self._on_wheel)

        self.preview_label = tk.Label(
            window, textvariable=self.preview_var, anchor=tk.W, bg=PANEL_RAISED,
            fg=TEXT_DIM, padx=14, font=(MONO, 8),
        )
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        self.redraw()

    # ------------------------------------------------------------------
    # Pointer input
    # ------------------------------------------------------------------
    def _chamber_at(self, x: float, y: float) -> Optional[int]:
        for index, (cx, cy) in enumerate(self._centers):
            if math.hypot(x - cx, y - cy) <= self.layout.hit_radius:
                return index
        return None

    def _on_motion(self, event) -> None:
        hovered = self._chamber_at(event.x, event.y)
        if hovered == self._hovered:
            return
        self._hovered = hovered
        if self._eject_armed is None:
            if hovered is None:
                self._show_selected_preview()
            else:
                self._set_preview(self._describe(hovered))
        self.redraw()

    def _on_leave(self, _event) -> None:
        if self._pressed is None:
            self._hovered = None
            if self._eject_armed is None:
                self._show_selected_preview()
            self.redraw()

    def _on_press(self, event) -> None:
        if self.window is not None and self.window.winfo_exists():
            # Override-redirect windows do not receive focus from the window
            # manager; take it explicitly so the keyboard controls work.
            try:
                self.window.focus_force()
            except tk.TclError:
                pass
        self._pressed = self._chamber_at(event.x, event.y)
        self._press_point = (event.x_root, event.y_root)
        self._dragging_round = False
        if self._pressed is not None:
            self._disarm_eject()
        self.redraw()

    def _on_round_drag(self, event) -> None:
        if self._pressed is None:
            return
        if is_drag_gesture(self._press_point, (event.x_root, event.y_root)):
            self._dragging_round = True
            self._set_preview(
                f"ROUND {chamber_label(self._pressed)} ARMED  /  RELEASE TO PASTE"
            )
            if self.canvas is not None:
                self.canvas.configure(cursor="target")

    def _on_release(self, _event) -> None:
        index = self._pressed
        self._pressed = None
        self._dragging_round = False
        if self.canvas is not None:
            self.canvas.configure(cursor="hand2")
        if index is None:
            self.redraw()
            return
        if index < len(self.get_items()):
            self._selected = index
            self._fire(index)
        else:
            self.select(index)
            self.flash_message(f"Chamber {chamber_label(index)} is empty", error=True)

    def _on_wheel(self, event) -> str:
        """Rotate the highlight one chamber per notch.  Never fires."""
        step = wheel_step(getattr(event, "num", None), getattr(event, "delta", 0))
        if step:
            self.select_relative(step)
        return "break"

    # ------------------------------------------------------------------
    # Keyboard input
    # ------------------------------------------------------------------
    def _on_key(self, event) -> None:
        char = getattr(event, "char", "") or ""
        if len(char) == 1 and char.isdigit():
            index = self._dial.press(char)
            if index is not None:
                self.select(index)

    def fire_selected(self) -> None:
        """Fire the highlighted chamber (keyboard path)."""
        index = self._selected
        if index >= len(self.get_items()):
            self.flash_message(f"Chamber {chamber_label(index)} is empty", error=True)
            return
        self._fire(index)

    def _fire(self, index: int) -> None:
        """Flash the chamber briefly, then hand the paste to the host."""
        self._disarm_eject()
        self._flashing = index
        self._set_preview(f"FIRING {chamber_label(index)}")
        self.redraw()
        if self.window is not None and self.window.winfo_exists():
            self.window.after(FIRE_FLASH_MS, lambda: self._finish_fire(index))
        else:
            self._finish_fire(index)

    def _finish_fire(self, index: int) -> None:
        self._flashing = None
        self.on_fire(index)
        self.redraw()

    def request_eject(self) -> None:
        """Two deliberate presses eject the highlighted round."""
        index = self._selected
        if self.on_eject is None:
            return
        if index >= len(self.get_items()):
            self.flash_message(f"Chamber {chamber_label(index)} is already empty", error=True)
            return
        if self._eject_armed == index:
            self._disarm_eject()
            ejected = bool(self.on_eject(index))
            self._selected = min(self._selected, max(0, len(self.get_items()) - 1))
            self.redraw()
            if ejected:
                self.flash_message(f"Ejected chamber {chamber_label(index)}")
            else:
                self.flash_message("Could not eject that round", error=True)
            return
        self._eject_armed = index
        self._set_preview(
            f"EJECT {chamber_label(index)}?  /  PRESS DELETE AGAIN TO CONFIRM",
            error=True,
        )
        self.redraw()
        if self.window is not None and self.window.winfo_exists():
            self._eject_job = self.window.after(EJECT_CONFIRM_MS, self._disarm_eject)

    def _disarm_eject(self) -> None:
        if self._eject_job is not None and self.window is not None:
            try:
                self.window.after_cancel(self._eject_job)
            except tk.TclError:
                pass
        self._eject_job = None
        if self._eject_armed is not None:
            self._eject_armed = None
            self._show_selected_preview()
            self.redraw()

    # ------------------------------------------------------------------
    # Window dragging
    # ------------------------------------------------------------------
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
