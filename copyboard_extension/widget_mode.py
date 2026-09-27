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

# The compact widget is a brushed-steel plate: a light squircle, a blue glow
# ring, dark recessed chambers, and COPY / PASTE tabs cut into the rim.  The
# palette is kept literal here so the widget stays importable on its own.
BACKDROP = "#0B0C0F"        # what shows around the plate's rounded corners
PLATE = "#D6D8DE"
PLATE_EDGE = "#F4F5F7"
PLATE_SHADOW = "#A9ADB6"
DIAL = "#C9CCD3"
DIAL_EDGE = "#EDEEF1"
STEEL_DARK = "#8E939D"
GLOW_OUTER = "#2B6FC4"
GLOW = "#3FA9FF"
GLOW_CORE = "#BFEBFF"
CHAMBER_TOP = "#3D2A55"     # violet at the top of the cylinder …
CHAMBER_BOTTOM = "#121B33"  # … fading to navy at the bottom
CHAMBER_RING = "#7A6797"
EMPTY_FILL = "#B3B7BF"
EMPTY_RING = "#9DA2AB"
TEXT = "#F2F4F8"
TEXT_DIM = "#AEB3BD"
TEXT_FAINT = "#7C8290"
LABEL_ON_STEEL = "#3A3F4A"
HOVER = "#7FC6FF"
FIRE = "#4DB8FF"
ERROR = "#E56B6F"
MONO = "DejaVu Sans Mono"
SANS = "DejaVu Sans"

IDLE_PROMPT = "WHEEL OR ↑↓ TO AIM   •   HOLD, DRAG, LET GO TO PASTE"
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
    def glow_radius(self) -> float:
        """Radius of the blue ring that frames the cylinder."""
        return self.ring_radius + self.chamber_radius + 20

    @property
    def plate_margin(self) -> float:
        return 12.0

    @property
    def tab_width(self) -> float:
        return max(120.0, self.size * 0.30)

    @property
    def tab_height(self) -> float:
        return 28.0

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
    # 100 px of plate around the cylinder leaves room for the glow ring and
    # the COPY / PASTE tabs without crowding chambers 01 and the bottom one.
    size = int(math.ceil(2 * (ring_radius + chamber_radius + 5) + 100))
    size += size % 2  # keep the canvas centre on a whole pixel
    return WidgetLayout(
        count=count,
        size=size,
        ring_radius=ring_radius,
        chamber_radius=chamber_radius,
        hub_radius=max(52.0, ring_radius - chamber_radius - 34),
        center_y=size / 2,
    )


def lerp_color(start: str, end: str, t: float) -> str:
    """Blend two ``#rrggbb`` colours; ``t`` is clamped to 0–1."""
    t = max(0.0, min(1.0, float(t)))
    a = [int(start[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(end[i : i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def chamber_fill(index: int, count: int) -> str:
    """Violet at twelve o'clock fading to navy at six, like a lit cylinder."""
    angle = -math.pi / 2 + index * 2 * math.pi / max(1, count)
    return lerp_color(CHAMBER_TOP, CHAMBER_BOTTOM, (math.sin(angle) + 1) / 2)


def rounded_rect_points(x0: float, y0: float, x1: float, y1: float, r: float) -> List[float]:
    """Control points for a smooth Tk polygon approximating a rounded rect."""
    return [
        x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
        x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
        x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
    ]


def tab_points(cx: float, top: float, width: float, height: float, flip: bool) -> List[float]:
    """A trapezoid tab centred on ``cx`` whose wide edge sits on the plate rim."""
    half, inset = width / 2, height * 0.55
    if not flip:  # hangs from the top rim
        return [cx - half, top, cx + half, top, cx + half - inset, top + height, cx - half + inset, top + height]
    return [cx - half + inset, top, cx + half - inset, top, cx + half, top + height, cx - half, top + height]


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
        on_capture: Optional[Callable[[], None]] = None,
    ) -> None:
        self.parent = parent
        self.get_items = get_items
        self.describe_item = describe_item
        self.on_fire = on_fire
        self.on_restore = on_restore
        self.on_eject = on_eject
        self.on_capture = on_capture
        self._tabs: dict = {}          # "copy" / "paste" -> (x0, y0, x1, y1)
        self._hovered_tab: Optional[str] = None
        self._plate_drag: Optional[Point] = None
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
                self.window.geometry(f"{layout.size}x{layout.size + 24}")
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
        size = layout.size
        cx, cy = layout.center_x, layout.center_y
        ring = layout.ring_radius
        radius = layout.chamber_radius
        self._centers = radial_centers(layout.count, cx, cy, ring)

        # Plate: a steel squircle with a bright top edge and a shadowed base.
        m = layout.plate_margin
        corner = size * 0.19
        canvas.create_polygon(
            rounded_rect_points(m + 1, m + 3, size - m + 1, size - m + 3, corner),
            smooth=True, fill=PLATE_SHADOW, outline="",
        )
        canvas.create_polygon(
            rounded_rect_points(m, m, size - m, size - m, corner),
            smooth=True, fill=PLATE, outline=PLATE_EDGE, width=2,
        )

        # Glow ring, drawn as stepped bands since Tk cannot blur.
        glow = layout.glow_radius
        for offset, color, width in ((0, GLOW_OUTER, 9), (0, GLOW, 5), (0, GLOW_CORE, 2)):
            canvas.create_oval(
                cx - glow + offset, cy - glow + offset, cx + glow - offset, cy + glow - offset,
                outline=color, width=width,
            )
        dial = glow - 8
        canvas.create_oval(
            cx - dial, cy - dial, cx + dial, cy + dial,
            fill=DIAL, outline=DIAL_EDGE, width=2,
        )

        for index, (x, y) in enumerate(self._centers):
            self._draw_chamber(index, x, y, radius, items)

        self._draw_hub(cx, cy, layout.hub_radius, items)
        self._draw_tabs(cx, size, layout)

        # Corner affordance back to the full editor.
        canvas.create_text(
            size - m - 16, m + 16, text="↗", fill=LABEL_ON_STEEL,
            font=(MONO, 13, "bold"), tags=("restore",),
        )

    def _draw_chamber(self, index: int, x: float, y: float, radius: float, items) -> None:
        canvas = self.canvas
        assert canvas is not None
        occupied = index < len(items)
        hovered = index == self._hovered
        pressed = index == self._pressed or index == self._flashing
        selected = index == self._selected
        armed = index == self._eject_armed

        # Bevel: a light rim offset up-left, a dark rim offset down-right.
        canvas.create_oval(
            x - radius - 4, y - radius - 4, x + radius + 4, y + radius + 4,
            fill=PLATE_EDGE, outline="",
        )
        canvas.create_oval(
            x - radius - 2, y - radius - 1, x + radius + 4, y + radius + 5,
            fill=STEEL_DARK, outline="",
        )
        if occupied:
            fill = chamber_fill(index, self.layout.count)
            inner_ring = CHAMBER_RING
        else:
            fill, inner_ring = EMPTY_FILL, EMPTY_RING
        if pressed:
            fill = FIRE
        canvas.create_oval(
            x - radius, y - radius, x + radius, y + radius,
            fill=fill, outline="#0E0F14" if occupied else STEEL_DARK, width=1,
        )
        inset = radius * 0.72
        canvas.create_oval(
            x - inset, y - inset, x + inset, y + inset,
            outline=inner_ring, width=1,
        )
        if armed:
            ring_color, ring_width = ERROR, 4
        elif selected:
            ring_color, ring_width = GLOW, 3
        elif hovered:
            ring_color, ring_width = HOVER, 2
        else:
            ring_color, ring_width = None, 0
        if ring_color:
            canvas.create_oval(
                x - radius - 6, y - radius - 6, x + radius + 6, y + radius + 6,
                outline=ring_color, width=ring_width,
            )

        number_color = TEXT if occupied else LABEL_ON_STEEL
        canvas.create_text(
            x, y - 7, text=chamber_label(index), fill=number_color,
            font=(MONO, 9, "bold"),
        )
        if occupied:
            _kind, mark, _preview = self.describe_item(items[index])
            canvas.create_text(
                x, y + 9, text=mark, fill=TEXT_DIM, font=(MONO, 8, "bold")
            )

    def _draw_hub(self, cx: float, cy: float, hub: float, items) -> None:
        canvas = self.canvas
        assert canvas is not None
        canvas.create_oval(
            cx - hub - 3, cy - hub - 1, cx + hub + 3, cy + hub + 5,
            fill=STEEL_DARK, outline="",
        )
        canvas.create_oval(
            cx - hub, cy - hub, cx + hub, cy + hub,
            fill=DIAL, outline=PLATE_EDGE, width=2,
        )
        # Eight bolt holes, purely for the machined look.
        bolt_ring = hub * 0.72
        for i in range(8):
            angle = -math.pi / 2 + i * math.pi / 4
            bx = cx + bolt_ring * math.cos(angle)
            by = cy + bolt_ring * math.sin(angle)
            canvas.create_oval(bx - 5, by - 5, bx + 5, by + 5, fill=CHAMBER_BOTTOM, outline=STEEL_DARK)
        core = hub * 0.42
        canvas.create_oval(
            cx - core - 5, cy - core - 5, cx + core + 5, cy + core + 5,
            fill=PLATE_EDGE, outline=STEEL_DARK, width=1,
        )
        canvas.create_oval(
            cx - core, cy - core, cx + core, cy + core,
            fill="#1A1430", outline="#0E0F14", width=1,
        )
        canvas.create_text(
            cx, cy - 6, text=f"{len(items):02d}", fill=TEXT, font=(MONO, 12, "bold")
        )
        canvas.create_text(
            cx, cy + 9, text=f"of {self.layout.count}", fill=TEXT_DIM, font=(MONO, 6, "bold")
        )

    def _draw_tabs(self, cx: float, size: float, layout: WidgetLayout) -> None:
        """COPY hangs from the top rim, PASTE rises from the bottom rim."""
        canvas = self.canvas
        assert canvas is not None
        m = layout.plate_margin
        width, height = layout.tab_width, layout.tab_height
        self._tabs = {
            "copy": (cx - width / 2, m, cx + width / 2, m + height),
            "paste": (cx - width / 2, size - m - height, cx + width / 2, size - m),
        }
        for name, flip in (("copy", False), ("paste", True)):
            x0, y0, _x1, _y1 = self._tabs[name]
            hovered = name == self._hovered_tab
            points = tab_points(cx, y0, width, height, flip)
            canvas.create_polygon(points, fill=STEEL_DARK, outline="")
            shifted = [v - (0 if i % 2 == 0 else 2) for i, v in enumerate(points)]
            canvas.create_polygon(
                shifted, fill=PLATE_EDGE if hovered else PLATE,
                outline=HOVER if hovered else PLATE_EDGE, width=2,
            )
            canvas.create_text(
                cx, y0 + height / 2 - 1, text=name.upper(),
                fill=GLOW_OUTER if hovered else LABEL_ON_STEEL, font=(SANS, 11, "bold"),
            )

    def _tab_at(self, x: float, y: float) -> Optional[str]:
        for name, (x0, y0, x1, y1) in self._tabs.items():
            if x0 <= x <= x1 and y0 <= y <= y1:
                return name
        return None

    def _restore_glyph_at(self, x: float, y: float) -> bool:
        size, m = self.layout.size, self.layout.plate_margin
        return abs(x - (size - m - 16)) <= 14 and abs(y - (m + 16)) <= 14

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
        window.configure(bg=BACKDROP)
        window.geometry(f"{layout.size}x{layout.size + 24}+{x}+{y}")
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

        self.canvas = tk.Canvas(
            window, width=layout.size, height=layout.size, bg=BACKDROP, bd=0,
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
            window, textvariable=self.preview_var, anchor=tk.CENTER, bg=BACKDROP,
            fg=TEXT_DIM, padx=10, font=(MONO, 8),
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
        tab = self._tab_at(event.x, event.y)
        if hovered == self._hovered and tab == self._hovered_tab:
            return
        self._hovered = hovered
        self._hovered_tab = tab
        if tab is not None and self._eject_armed is None:
            self._set_preview(
                "COPY: LOAD THE CURRENT CLIPBOARD INTO CHAMBER 01"
                if tab == "copy"
                else f"PASTE: FIRE CHAMBER {chamber_label(self._selected)} INTO THE PREVIOUS APP"
            )
            self.redraw()
            return
        if self._eject_armed is None:
            if hovered is None:
                self._show_selected_preview()
            else:
                self._set_preview(self._describe(hovered))
        self.redraw()

    def _on_leave(self, _event) -> None:
        if self._pressed is None:
            self._hovered = None
            self._hovered_tab = None
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
        self._plate_drag = None
        if self._pressed is not None:
            self._disarm_eject()
        elif self._tab_at(event.x, event.y) is None and not self._restore_glyph_at(event.x, event.y):
            # Pressing bare steel drags the whole plate around the screen.
            self._plate_drag = (event.x, event.y)
        self.redraw()

    def _on_round_drag(self, event) -> None:
        if self._plate_drag is not None and self.window is not None:
            self.window.geometry(
                f"+{int(event.x_root - self._plate_drag[0])}+{int(event.y_root - self._plate_drag[1])}"
            )
            return
        if self._pressed is None:
            return
        if is_drag_gesture(self._press_point, (event.x_root, event.y_root)):
            self._dragging_round = True
            self._set_preview(
                f"ROUND {chamber_label(self._pressed)} ARMED  /  RELEASE TO PASTE"
            )
            if self.canvas is not None:
                self.canvas.configure(cursor="target")

    def _on_release(self, event) -> None:
        index = self._pressed
        self._pressed = None
        self._dragging_round = False
        if self.canvas is not None:
            self.canvas.configure(cursor="hand2")
        if self._plate_drag is not None:
            self._plate_drag = None
            if self.window is not None and self.on_move is not None:
                self.on_move(self.window.winfo_x(), self.window.winfo_y())
            self.redraw()
            return
        if index is None:
            tab = self._tab_at(event.x, event.y)
            if tab == "copy":
                self.capture_clipboard()
            elif tab == "paste":
                self.fire_selected()
            elif self._restore_glyph_at(event.x, event.y):
                self.on_restore()
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

    def capture_clipboard(self) -> None:
        """COPY tab: ask the host to load the current clipboard into chamber 01."""
        if self.on_capture is None:
            self.flash_message("Capture is not available here", error=True)
            return
        self.on_capture()
        self._selected = 0
        self.redraw()

    def fire_selected(self) -> None:
        """Fire the highlighted chamber (keyboard path or PASTE tab)."""
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
