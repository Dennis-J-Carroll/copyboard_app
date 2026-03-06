#!/usr/bin/env python3
"""
Copyboard GUI - Graphical interface with full mode and compact mini mode.
Includes runtime-configurable hotkeys dialog.
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import pyperclip
import threading
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from . import core, paste_helper, hotkeys
    from .config_manager import config
except ImportError as e:
    print(f"Error importing copyboard modules: {e}")
    sys.exit(1)

# ── Color constants for mini mode ──────────────────────────────────────
BG_DARK = "#1e1e2e"
CARD_BG = "#2a2a3e"
CARD_HOVER = "#353550"
ACCENT = "#7c3aed"
TEXT_PRIMARY = "#e0e0e0"
TEXT_SECONDARY = "#a0a0b0"
HEADER_BG = "#16162a"
CLOSE_HOVER = "#e74c3c"

# System-reserved combos that users should be warned about
SYSTEM_RESERVED = {
    "ctrl+c", "ctrl+v", "ctrl+x", "ctrl+z", "ctrl+y",
    "ctrl+a", "ctrl+s", "ctrl+w", "ctrl+q", "ctrl+f",
    "alt+f4", "alt+tab",
}


class CopyboardGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Copyboard")

        # ── State from config ──────────────────────────────────────
        self.is_mini_mode = config.get("window", "mini_mode", False)
        self._save_position_timer = None
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        # ── Containers ─────────────────────────────────────────────
        self.full_frame = ttk.Frame(self.root)
        self.mini_frame = tk.Frame(self.root, bg=BG_DARK)

        # Build both layouts
        self._build_full_mode()
        self._build_mini_mode()

        # Restore window geometry from config
        self._restore_geometry()

        # Start in the correct mode
        if self.is_mini_mode:
            self.switch_to_mini()
        else:
            self.switch_to_full()

        # ── Clipboard monitoring ───────────────────────────────────
        self.monitor_active = config.get("board", "auto_capture", True)
        self.monitor_thread = threading.Thread(target=self.monitor_clipboard, daemon=True)
        self.monitor_thread.start()

        # ── Window events ──────────────────────────────────────────
        self.root.bind("<Configure>", self._on_window_configure)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ══════════════════════════════════════════════════════════════════
    #  FULL MODE
    # ══════════════════════════════════════════════════════════════════

    def _build_full_mode(self):
        frame = self.full_frame
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        # Header
        header = ttk.Frame(frame)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        ttk.Label(header, text="Copyboard", font=("Arial", 16, "bold")).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(header)
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(btn_frame, text="Mini Mode", command=self.toggle_mini_mode).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Hotkeys", command=self.open_hotkey_settings).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Copy Current", command=self.copy_to_board).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Clear All", command=self.clear_board).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_list).pack(side=tk.LEFT, padx=3)

        # Items area
        items_frame = ttk.Frame(frame)
        items_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        items_frame.columnconfigure(0, weight=1)
        items_frame.rowconfigure(0, weight=1)

        listbox_frame = ttk.Frame(items_frame)
        listbox_frame.grid(row=0, column=0, sticky="nsew")
        listbox_frame.columnconfigure(0, weight=1)
        listbox_frame.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            listbox_frame, selectmode=tk.EXTENDED, font=("Arial", 10),
            relief=tk.FLAT, bd=0, highlightthickness=0
        )
        self.listbox.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.config(yscrollcommand=scrollbar.set)

        # Action buttons
        action_frame = ttk.Frame(items_frame)
        action_frame.grid(row=0, column=1, sticky="ns", padx=(10, 0))

        for text, cmd in [
            ("Paste Selected", self.paste_selected),
            ("Combine & Paste", self.combine_and_paste),
            ("Remove", self.remove_selected),
            ("Edit", self.edit_selected),
        ]:
            ttk.Button(action_frame, text=text, command=cmd).pack(fill=tk.X, pady=3)

        # Always-on-top checkbox
        self._aot_var = tk.BooleanVar(value=config.get("window", "always_on_top", True))
        ttk.Checkbutton(
            action_frame, text="Always on top",
            variable=self._aot_var, command=self._toggle_always_on_top
        ).pack(fill=tk.X, pady=(10, 3))

        # Status bar
        self.status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).grid(
            row=2, column=0, sticky="ew", padx=10, pady=(0, 5)
        )

    # ══════════════════════════════════════════════════════════════════
    #  MINI MODE
    # ══════════════════════════════════════════════════════════════════

    def _build_mini_mode(self):
        frame = self.mini_frame

        # Header bar for dragging
        header = tk.Frame(frame, bg=HEADER_BG, height=28)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # Drag bindings on header
        header.bind("<Button-1>", self._on_drag_start)
        header.bind("<B1-Motion>", self._on_drag_motion)

        title = tk.Label(header, text="Copyboard", fg=TEXT_PRIMARY, bg=HEADER_BG,
                         font=("Arial", 9, "bold"))
        title.pack(side=tk.LEFT, padx=8)
        title.bind("<Button-1>", self._on_drag_start)
        title.bind("<B1-Motion>", self._on_drag_motion)

        # Close button
        close_btn = tk.Label(header, text="\u00d7", fg=TEXT_SECONDARY, bg=HEADER_BG,
                             font=("Arial", 14), cursor="hand2")
        close_btn.pack(side=tk.RIGHT, padx=(0, 6))
        close_btn.bind("<Button-1>", lambda e: self.on_close())
        close_btn.bind("<Enter>", lambda e: close_btn.config(fg=CLOSE_HOVER))
        close_btn.bind("<Leave>", lambda e: close_btn.config(fg=TEXT_SECONDARY))

        # Expand button
        expand_btn = tk.Label(header, text="\u2197", fg=TEXT_SECONDARY, bg=HEADER_BG,
                              font=("Arial", 12), cursor="hand2")
        expand_btn.pack(side=tk.RIGHT, padx=2)
        expand_btn.bind("<Button-1>", lambda e: self.toggle_mini_mode())
        expand_btn.bind("<Enter>", lambda e: expand_btn.config(fg=ACCENT))
        expand_btn.bind("<Leave>", lambda e: expand_btn.config(fg=TEXT_SECONDARY))

        # Items container
        self.mini_items_frame = tk.Frame(frame, bg=BG_DARK)
        self.mini_items_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Right-click menu for mini mode header
        self._mini_ctx_menu = tk.Menu(header, tearoff=0)
        self._mini_ctx_menu.add_checkbutton(
            label="Always on top",
            command=self._toggle_always_on_top_mini
        )
        header.bind("<Button-3>", self._show_mini_context)

    def _show_mini_context(self, event):
        self._mini_ctx_menu.tk_popup(event.x_root, event.y_root)

    def _toggle_always_on_top_mini(self):
        current = config.get("window", "always_on_top", True)
        new_val = not current
        config.set("window", "always_on_top", new_val)
        self.root.attributes("-topmost", new_val)

    def _refresh_mini_items(self):
        """Rebuild compact cards in mini mode."""
        for widget in self.mini_items_frame.winfo_children():
            widget.destroy()

        items = core.get_board()
        max_show = 8
        preview_len = config.get("board", "preview_length", 50)

        for idx, item in enumerate(items[:max_show]):
            preview = item.replace("\n", "\u21b5 ")
            if len(preview) > preview_len:
                preview = preview[:preview_len - 3] + "..."

            card = tk.Frame(self.mini_items_frame, bg=CARD_BG, cursor="hand2")
            card.pack(fill=tk.X, pady=2)

            badge = tk.Label(card, text=str(idx), fg="#fff", bg=ACCENT,
                             font=("Arial", 8, "bold"), width=2)
            badge.pack(side=tk.LEFT, padx=(4, 6), pady=4)

            text_lbl = tk.Label(card, text=preview, fg=TEXT_PRIMARY, bg=CARD_BG,
                                font=("Arial", 9), anchor=tk.W)
            text_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4), pady=4)

            # Click-to-copy
            for widget in (card, badge, text_lbl):
                widget.bind("<Button-1>", lambda e, i=idx: self._mini_click_copy(i))
                widget.bind("<Enter>", lambda e, c=card: c.config(bg=CARD_HOVER) or
                            [w.config(bg=CARD_HOVER) for w in c.winfo_children()
                             if isinstance(w, tk.Label) and w.cget("bg") != ACCENT])
                widget.bind("<Leave>", lambda e, c=card: c.config(bg=CARD_BG) or
                            [w.config(bg=CARD_BG) for w in c.winfo_children()
                             if isinstance(w, tk.Label) and w.cget("bg") != ACCENT])

        overflow = len(items) - max_show
        if overflow > 0:
            tk.Label(self.mini_items_frame, text=f"...and {overflow} more",
                     fg=TEXT_SECONDARY, bg=BG_DARK, font=("Arial", 8)).pack(pady=(2, 0))

    def _mini_click_copy(self, index):
        item = core.get_board_item(index)
        if item:
            pyperclip.copy(item)

    # ══════════════════════════════════════════════════════════════════
    #  MODE TOGGLING
    # ══════════════════════════════════════════════════════════════════

    def toggle_mini_mode(self):
        self.is_mini_mode = not self.is_mini_mode
        config.set("window", "mini_mode", self.is_mini_mode)
        if self.is_mini_mode:
            self.switch_to_mini()
        else:
            self.switch_to_full()

    def switch_to_mini(self):
        # Save full-mode geometry
        self._save_window_position()
        self.full_frame.pack_forget()

        self.root.overrideredirect(True)
        self.root.attributes("-topmost", config.get("window", "always_on_top", True))

        # Apply mini dimensions
        w, h = 280, 40 + min(core.get_board_size(), 8) * 34 + 8
        x = config.get("window", "x", 100)
        y = config.get("window", "y", 100)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.mini_frame.pack(fill=tk.BOTH, expand=True)
        self._refresh_mini_items()

    def switch_to_full(self):
        self._save_window_position()
        self.mini_frame.pack_forget()

        self.root.overrideredirect(False)
        self.root.title("Copyboard")

        w = config.get("window", "width", 600)
        h = config.get("window", "height", 400)
        x = config.get("window", "x", 100)
        y = config.get("window", "y", 100)
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(500, 300)

        aot = config.get("window", "always_on_top", True)
        self.root.attributes("-topmost", aot)

        self.full_frame.pack(fill=tk.BOTH, expand=True)
        self.refresh_list()

    # ══════════════════════════════════════════════════════════════════
    #  WINDOW POSITION PERSISTENCE
    # ══════════════════════════════════════════════════════════════════

    def _restore_geometry(self):
        w = config.get("window", "width", 600)
        h = config.get("window", "height", 400)
        x = config.get("window", "x", 100)
        y = config.get("window", "y", 100)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _on_window_configure(self, event):
        if event.widget != self.root:
            return
        if self._save_position_timer:
            self.root.after_cancel(self._save_position_timer)
        self._save_position_timer = self.root.after(500, self._save_window_position)

    def _save_window_position(self):
        config.set("window", "x", self.root.winfo_x())
        config.set("window", "y", self.root.winfo_y())
        if not self.is_mini_mode:
            config.set("window", "width", self.root.winfo_width())
            config.set("window", "height", self.root.winfo_height())

    # ══════════════════════════════════════════════════════════════════
    #  DRAGGING (mini mode borderless window)
    # ══════════════════════════════════════════════════════════════════

    def _on_drag_start(self, event):
        self.drag_offset_x = event.x
        self.drag_offset_y = event.y

    def _on_drag_motion(self, event):
        x = self.root.winfo_pointerx() - self.drag_offset_x
        y = self.root.winfo_pointery() - self.drag_offset_y
        self.root.geometry(f"+{x}+{y}")

    # ══════════════════════════════════════════════════════════════════
    #  ALWAYS ON TOP
    # ══════════════════════════════════════════════════════════════════

    def _toggle_always_on_top(self):
        val = self._aot_var.get()
        config.set("window", "always_on_top", val)
        self.root.attributes("-topmost", val)

    # ══════════════════════════════════════════════════════════════════
    #  FULL MODE ACTIONS (same as before)
    # ══════════════════════════════════════════════════════════════════

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        items = core.get_board()
        preview_len = config.get("board", "preview_length", 50)
        for idx, item in enumerate(items):
            preview = item[:preview_len - 3] + "..." if len(item) > preview_len else item
            preview = preview.replace("\n", "\u21b5 ")
            self.listbox.insert(tk.END, f"{idx}: {preview}")
        self.status_var.set(f"Clipboard items: {len(items)}")

        # Also refresh mini items if visible
        if self.is_mini_mode:
            self._refresh_mini_items()

    def copy_to_board(self):
        core.copy_to_board()
        self.refresh_list()
        self.status_var.set("Copied current clipboard to board")

    def paste_selected(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Copyboard", "Please select an item to paste")
            return
        item_idx = int(self.listbox.get(selection[0]).split(":")[0])
        if core.paste_from_board(item_idx):
            self.status_var.set(f"Pasted item {item_idx}")
        else:
            self.status_var.set("Failed to paste item")

    def combine_and_paste(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Copyboard", "Please select items to combine")
            return
        indices = [int(self.listbox.get(s).split(":")[0]) for s in selection]
        if core.paste_combination(indices):
            self.status_var.set(f"Pasted combined items: {', '.join(map(str, indices))}")
        else:
            self.status_var.set("Failed to paste combined items")

    def remove_selected(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Copyboard", "Please select items to remove")
            return
        indices = sorted(
            [int(self.listbox.get(s).split(":")[0]) for s in selection],
            reverse=True
        )
        for idx in indices:
            core.drop_item(idx)
        self.refresh_list()
        self.status_var.set(f"Removed {len(indices)} item(s)")

    def edit_selected(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Copyboard", "Please select an item to edit")
            return
        item_idx = int(self.listbox.get(selection[0]).split(":")[0])
        item_content = core.get_board_item(item_idx)

        edit_win = tk.Toplevel(self.root)
        edit_win.title(f"Edit Clipboard Item {item_idx}")
        edit_win.geometry("500x300")
        edit_win.minsize(400, 200)
        edit_win.transient(self.root)
        edit_win.grab_set()

        text_frame = ttk.Frame(edit_win, padding=10)
        text_frame.pack(fill=tk.BOTH, expand=True)

        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Arial", 10))
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.config(yscrollcommand=sb.set)
        text_widget.insert("1.0", item_content or "")

        btn_frame = ttk.Frame(edit_win, padding=10)
        btn_frame.pack(fill=tk.X)

        def save_changes():
            new_content = text_widget.get("1.0", tk.END).rstrip("\n")
            board = core.get_board()
            if item_idx < len(board):
                core._board[item_idx] = new_content
                core._mark_modified()
                core._save_board(force=True)
            edit_win.destroy()
            self.refresh_list()
            self.status_var.set(f"Updated item {item_idx}")

        ttk.Button(btn_frame, text="Save", command=save_changes).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=edit_win.destroy).pack(side=tk.RIGHT, padx=5)
        text_widget.focus_set()

    def clear_board(self):
        if messagebox.askyesno("Copyboard", "Clear all clipboard items?"):
            core.clear_board()
            self.refresh_list()
            self.status_var.set("Cleared all clipboard items")

    # ══════════════════════════════════════════════════════════════════
    #  CLIPBOARD MONITORING
    # ══════════════════════════════════════════════════════════════════

    def monitor_clipboard(self):
        last_content = pyperclip.paste()
        while self.monitor_active:
            try:
                current = pyperclip.paste()
                if current != last_content:
                    last_content = current
                    if config.get("board", "auto_capture", True):
                        core.copy_to_board()
                        self.root.after(0, self.refresh_list)
            except Exception:
                pass
            time.sleep(0.5)

    # ══════════════════════════════════════════════════════════════════
    #  HOTKEY SETTINGS DIALOG (Phase 3)
    # ══════════════════════════════════════════════════════════════════

    def open_hotkey_settings(self):
        HotkeySettingsDialog(self.root)

    # ══════════════════════════════════════════════════════════════════
    #  CLOSE
    # ══════════════════════════════════════════════════════════════════

    def on_close(self):
        self.monitor_active = False
        self._save_window_position()
        core.force_save()
        self.root.destroy()


# ══════════════════════════════════════════════════════════════════════
#  HOTKEY SETTINGS DIALOG
# ══════════════════════════════════════════════════════════════════════

class HotkeySettingsDialog:
    """Toplevel dialog for viewing and recording new hotkey bindings."""

    # Human-readable labels for each action
    ACTION_LABELS = {
        "show_gui": "Show GUI",
        "copy_to_board": "Copy to Board",
        "paste_recent": "Paste Recent",
        "paste_all": "Paste All",
        "paste_combo": "Paste Combo",
        "cycle_forward": "Cycle Forward",
        "cycle_backward": "Cycle Backward",
        "quick_paste_1": "Quick Paste 1",
        "quick_paste_2": "Quick Paste 2",
        "quick_paste_3": "Quick Paste 3",
        "quick_paste_4": "Quick Paste 4",
        "quick_paste_5": "Quick Paste 5",
    }

    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title("Hotkey Settings")
        self.win.geometry("480x520")
        self.win.minsize(400, 400)
        self.win.transient(parent)
        self.win.grab_set()

        self.capturing_for = None
        self.pending_hotkeys: dict = {}  # action -> new combo
        self.display_labels: dict = {}   # action -> Label widget
        self.record_buttons: dict = {}   # action -> Button widget

        # Load current config
        self.current_hotkeys = config.get_section("hotkeys")
        self.pending_hotkeys = dict(self.current_hotkeys)

        # ── Build UI ───────────────────────────────────────────────
        ttk.Label(self.win, text="Hotkey Configuration",
                  font=("Arial", 14, "bold")).pack(pady=(10, 5))
        ttk.Label(self.win, text="Click Record, then press your key combination.",
                  font=("Arial", 9)).pack(pady=(0, 10))

        # Scrollable frame
        canvas = tk.Canvas(self.win, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.win, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)

        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for action in self.ACTION_LABELS:
            self._add_hotkey_row(action)

        # Hidden entry for key capture
        self._capture_entry = tk.Entry(self.win, width=1)
        self._capture_entry.place(x=-100, y=-100)  # offscreen
        self._capture_entry.bind("<KeyPress>", self._on_key_capture)

        # Buttons
        btn_frame = ttk.Frame(self.win)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        self._status_var = tk.StringVar()
        ttk.Label(btn_frame, textvariable=self._status_var,
                  foreground="red").pack(side=tk.LEFT)

        ttk.Button(btn_frame, text="Reset Defaults",
                   command=self._reset_defaults).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel",
                   command=self.win.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Save",
                   command=self._save).pack(side=tk.RIGHT, padx=5)

    def _add_hotkey_row(self, action):
        row = ttk.Frame(self.scroll_frame)
        row.pack(fill=tk.X, pady=2)

        label_text = self.ACTION_LABELS.get(action, action)
        ttk.Label(row, text=label_text, width=18, anchor=tk.W).pack(side=tk.LEFT, padx=(0, 5))

        combo_lbl = ttk.Label(row, text=self.pending_hotkeys.get(action, "") or "",
                              width=22, anchor=tk.W, relief=tk.SUNKEN)
        combo_lbl.pack(side=tk.LEFT, padx=5)
        self.display_labels[action] = combo_lbl

        btn = ttk.Button(row, text="Record", width=8,
                         command=lambda a=action: self._start_capture(a))
        btn.pack(side=tk.LEFT, padx=5)
        self.record_buttons[action] = btn

    def _start_capture(self, action):
        self.capturing_for = action
        self._capture_entry.focus_set()
        self.record_buttons[action].config(text="Press...")
        self._status_var.set("")

    def _on_key_capture(self, event):
        if not self.capturing_for:
            return

        modifiers = []
        if event.state & 0x4:
            modifiers.append("ctrl")
        if event.state & 0x1:
            modifiers.append("shift")
        if event.state & 0x20000:
            modifiers.append("alt")

        key = event.keysym.lower()
        # Ignore lone modifier presses
        if key in ("control_l", "control_r", "shift_l", "shift_r",
                    "alt_l", "alt_r", "meta_l", "meta_r"):
            return

        combo = "+".join(modifiers + [key])
        action = self.capturing_for
        self.pending_hotkeys[action] = combo
        self.display_labels[action].config(text=combo)
        self.record_buttons[action].config(text="Record")
        self.capturing_for = None

        # Check for system-reserved warning
        if combo.lower() in SYSTEM_RESERVED:
            self._status_var.set(f"Warning: {combo} is a system shortcut")

    def _find_conflicts(self) -> list:
        """Return list of (action1, action2, combo) triples that conflict."""
        seen: dict = {}  # combo -> action
        conflicts = []
        for action, combo in self.pending_hotkeys.items():
            if not combo:
                continue
            if combo in seen:
                conflicts.append((seen[combo], action, combo))
            else:
                seen[combo] = action
        return conflicts

    def _save(self):
        conflicts = self._find_conflicts()
        if conflicts:
            names = []
            for a1, a2, combo in conflicts:
                l1 = self.ACTION_LABELS.get(a1, a1)
                l2 = self.ACTION_LABELS.get(a2, a2)
                names.append(f"{l1} & {l2} ({combo})")
                # Highlight in red
                self.display_labels[a1].config(foreground="red")
                self.display_labels[a2].config(foreground="red")
            self._status_var.set(f"Conflicts: {'; '.join(names)}")
            return

        # Apply changes
        old_config = config.get_section("hotkeys")
        for action, new_combo in self.pending_hotkeys.items():
            old_combo = old_config.get(action, "")
            if new_combo != old_combo:
                hotkeys.apply_hotkey_change(action, old_combo, new_combo)

        self.win.destroy()

    def _reset_defaults(self):
        config.reset_section("hotkeys")
        self.pending_hotkeys = config.get_section("hotkeys")
        for action, lbl in self.display_labels.items():
            lbl.config(text=self.pending_hotkeys.get(action, ""), foreground="")
        self._status_var.set("Reset to defaults")


# ══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

def main():
    root = tk.Tk()
    app = CopyboardGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
