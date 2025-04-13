#!/usr/bin/env python3
"""
Radial Menu for Copyboard

This module implements a radial/pie menu for selecting clipboard items.
The menu appears when the user holds down the right mouse button on the "paste" option.
"""

import math
import os
import json
import tkinter as tk
from typing import List, Callable
import pyperclip

class RadialMenu:
    """
    A radial menu for selecting clipboard items.
    
    The menu appears centered on the cursor position when triggered.
    Each clipboard item is represented as a sector in the circle.
    Moving the cursor in the direction of a sector selects that item.
    """
    
    def __init__(self, 
                 items: List[str] = None, 
                 radius: int = 150, 
                 on_select: Callable[[int], None] = None,
                 on_cancel: Callable[[], None] = None,
                 theme: dict = None):
        """
        Initialize the radial menu.
        
        Args:
            items: List of items to display in the menu
            radius: Radius of the menu in pixels
            on_select: Callback function when an item is selected
            on_cancel: Callback function when the menu is cancelled
        """
        self.items = items or []
        self.radius = radius
        self.on_select = on_select
        self.on_cancel = on_cancel
        self.root = None
        self.canvas = None
        self.center_x = 0
        self.center_y = 0
        self.selected_index = -1
        self.active = False
        
        # Default theme
        self.default_theme = {
            'background': '#F0F0F0',          # Transparent background
            'center_fill': '#222222',         # Dark center
            'center_outline': '#4444FF',      # Blue outline
            'center_text': '#FFFFFF',         # White text
            'arm_color': '#444444',           # Dark gray arms
            'arm_selected': '#0088FF',        # Blue selected arm
            'arm_width': 2,                   # Arm width
            'arm_selected_width': 4,          # Selected arm width
            'node_fill': '#333333',           # Dark node
            'node_selected': '#0088FF',       # Blue selected node
            'node_text': '#FFFFFF',           # White text
            'label_text': '#000000',          # Black label text
            'label_selected': '#0088FF',      # Blue selected label
            'font_family': 'Arial',           # Font family
        }
        
        # Apply custom theme settings
        self.theme = self.default_theme.copy()
        if theme:
            self.theme.update(theme)
        
    def show(self, x: int, y: int) -> None:
        """
        Show the radial menu centered at the given coordinates.
        
        Args:
            x: X coordinate of the center
            y: Y coordinate of the center
        """
        if not self.items:
            return
            
        # Create the window
        self.root = tk.Tk()
        self.root.overrideredirect(True)  # No window decorations
        self.root.attributes('-topmost', True)  # Always on top
        self.root.attributes('-alpha', 0.9)  # Slightly transparent
        
        # Make the window transparent and clickthrough
        try:
            # Try to set transparency color
            self.root.wm_attributes('-transparentcolor', '#F0F0F0')
        except:
            # If not supported, use regular transparency
            pass
        
        # Calculate window size and position
        window_size = self.radius * 2 + 20  # Add some padding
        self.root.geometry(f"{window_size}x{window_size}+{x-self.radius-10}+{y-self.radius-10}")
        
        # Create the canvas with transparent background
        self.canvas = tk.Canvas(self.root, width=window_size, height=window_size, 
                               bg='#F0F0F0', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Set the center coordinates
        self.center_x = window_size // 2
        self.center_y = window_size // 2
        
        # Draw the menu
        self._draw_menu()
        
        # Bind mouse events
        self.canvas.bind('<Motion>', self._on_mouse_move)
        self.canvas.bind('<ButtonRelease-3>', self._on_right_release)
        self.canvas.bind('<Escape>', self._on_cancel)
        
        # Mark as active
        self.active = True
        
        # Start the main loop
        self.root.mainloop()
        
    def _draw_menu(self) -> None:
        """Draw the radial menu on the canvas."""
        if not self.canvas:
            return
            
        # Clear the canvas
        self.canvas.delete("all")
        
        # Draw the center circle
        self.canvas.create_oval(
            self.center_x - 25, self.center_y - 25,
            self.center_x + 25, self.center_y + 25,
            fill=self.theme['center_fill'], 
            outline=self.theme['center_outline'], 
            width=3
        )
        self.canvas.create_text(
            self.center_x, self.center_y,
            text="0", 
            font=(self.theme['font_family'], 14, "bold"),
            fill=self.theme['center_text']
        )
        
        # Draw a semi-transparent preview of the selected item in the center
        if self.selected_index >= 0 and self.selected_index < len(self.items):
            selected_item = self.items[self.selected_index]
            # Format preview
            preview = selected_item[:40] + "..." if len(selected_item) > 40 else selected_item
            preview = preview.replace('\n', ' ↵ ').replace('\t', ' → ')
            
            # Draw the preview background
            self.canvas.create_rectangle(
                self.center_x - 120, self.center_y + 30,
                self.center_x + 120, self.center_y + 80,
                fill="#333333AA",
                outline="#666666",
                width=1
            )
            
            # Draw the preview text
            self.canvas.create_text(
                self.center_x, self.center_y + 55,
                text=preview,
                font=(self.theme['font_family'], 10),
                fill="#FFFFFF",
                width=220  # Wrap text if needed
            )
        
        # Calculate the angle for each sector
        num_items = len(self.items)
        angle_per_item = 360 / num_items
        
        # Draw each sector
        for i, item in enumerate(self.items):
            # Calculate the start and end angles for this sector
            start_angle = i * angle_per_item
            end_angle = (i + 1) * angle_per_item
            
            # Calculate the midpoint of the sector
            mid_angle = math.radians((start_angle + end_angle) / 2)
            
            # Calculate the position for the label
            label_x = self.center_x + (self.radius * 0.7) * math.cos(mid_angle)
            label_y = self.center_y + (self.radius * 0.7) * math.sin(mid_angle)
            
            # Calculate the endpoints of the arm
            arm_end_x = self.center_x + self.radius * math.cos(mid_angle)
            arm_end_y = self.center_y + self.radius * math.sin(mid_angle)
            
            # Draw the arm with a gradient effect for better visibility
            is_selected = (i == self.selected_index)
            line_color = self.theme['arm_selected'] if is_selected else self.theme['arm_color']
            line_width = self.theme['arm_selected_width'] if is_selected else self.theme['arm_width']
            
            # Draw the arm with slightly increased width for better visibility
            self.canvas.create_line(
                self.center_x, self.center_y,
                arm_end_x, arm_end_y,
                fill=line_color,
                width=line_width
            )
            
            # Draw the label
            # Truncate the item text if it's too long
            preview = item[:30] + "..." if len(item) > 30 else item
            preview = preview.replace('\n', ' ↵ ').replace('\t', ' → ')
            
            # Create a background for the text to improve readability
            if is_selected:
                # Create a background for selected text
                text_width = len(f"{i+1}: {preview}") * 5  # Approximate width based on text length
                self.canvas.create_rectangle(
                    label_x - text_width/2, label_y - 10,
                    label_x + text_width/2, label_y + 10,
                    fill="#0088FF44",  # Semi-transparent background
                    outline=""
                )
            
            self.canvas.create_text(
                label_x, label_y,
                text=f"{i+1}: {preview}",
                font=(self.theme['font_family'], 10, "bold" if is_selected else ""),
                fill=self.theme['label_selected'] if is_selected else self.theme['label_text']
            )
            
            # Draw a circle at the end of the arm
            node_size = 12 if is_selected else 10  # Slightly larger for selected node
            self.canvas.create_oval(
                arm_end_x - node_size, arm_end_y - node_size,
                arm_end_x + node_size, arm_end_y + node_size,
                fill=self.theme['node_selected'] if is_selected else self.theme['node_fill'],
                outline=self.theme['arm_selected'] if is_selected else self.theme['arm_color'],
                width=2 if is_selected else 1
            )
            self.canvas.create_text(
                arm_end_x, arm_end_y,
                text=str(i+1),
                font=(self.theme['font_family'], 10, "bold"),
                fill=self.theme['center_text']
            )
    
    def _on_mouse_move(self, event) -> None:
        """
        Handle mouse movement events.
        
        Args:
            event: The mouse event
        """
        # Calculate the angle from the center to the mouse position
        dx = event.x - self.center_x
        dy = event.y - self.center_y
        
        # Calculate the distance from the center
        distance = math.sqrt(dx*dx + dy*dy)
        
        # If the mouse is too close to the center, don't select anything
        if distance < 30:
            self.selected_index = -1
            self._draw_menu()
            return
            
        # Calculate the angle in degrees
        angle = math.degrees(math.atan2(dy, dx))
        if angle < 0:
            angle += 360
            
        # Calculate which sector the mouse is in
        num_items = len(self.items)
        angle_per_item = 360 / num_items
        sector = int(angle / angle_per_item)
        
        # Update the selected index if it changed
        if sector != self.selected_index:
            self.selected_index = sector
            self._draw_menu()
    
    def _on_right_release(self, event) -> None:
        """
        Handle right mouse button release events.
        
        Args:
            event: The mouse event
        """
        if self.selected_index >= 0 and self.selected_index < len(self.items):
            if self.on_select:
                self.on_select(self.selected_index)
        else:
            if self.on_cancel:
                self.on_cancel()
                
        self._close()
    
    def _on_cancel(self, event=None) -> None:
        """
        Handle cancel events.
        
        Args:
            event: The keyboard event
        """
        if self.on_cancel:
            self.on_cancel()
            
        self._close()
    
    def _close(self) -> None:
        """Close the radial menu."""
        if self.root:
            self.active = False
            self.root.destroy()
            self.root = None
            self.canvas = None


def show_radial_menu(x: int, y: int, custom_theme: dict = None) -> None:
    """
    Show the radial menu at the given coordinates.
    
    Args:
        x: X coordinate of the center
        y: Y coordinate of the center
        custom_theme: Optional custom theme for the menu
    """
    # Get clipboard items from core module
    try:
        # First try relative import
        from . import core
        board_items = core.get_board()
    except (ImportError, ValueError):
        # Then try direct import
        try:
            import sys
            import os
            # Try to add parent directory to path
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            import copyboard_extension.core as core
            board_items = core.get_board()
        except ImportError:
            print("Could not import copyboard core module")
            return
    
    # Show the menu
    if board_items:
        # Apply any custom theme
        if not custom_theme:
            custom_theme = load_custom_theme()
        
        # Define the callback function when an item is selected
        def on_item_selected(idx):
            # Paste the selected item
            success = core.paste_from_board(idx)
            if success:
                # Show notification
                try:
                    import subprocess
                    subprocess.run(["notify-send", "Copyboard", f"Pasted item {idx}"], check=False)
                except Exception as e:
                    print(f"Error showing notification: {e}")
            return idx
            
        # Create and show the radial menu
        menu = RadialMenu(board_items, on_select=on_item_selected, theme=custom_theme)
        menu.show(x, y)
    else:
        # Show message if no items in board
        try:
            import subprocess
            subprocess.run(["notify-send", "Copyboard", "No items in clipboard board"], check=False)
        except Exception:
            print("No items in clipboard board")


# Load custom theme from config file if it exists
def load_custom_theme() -> dict:
    """
    Load custom theme from the config file.
    
    Returns:
        Custom theme dictionary or None if not found
    """
    config_dir = os.path.join(os.path.expanduser("~"), ".config", "copyboard")
    theme_file = os.path.join(config_dir, "theme.json")
    
    if os.path.exists(theme_file):
        try:
            with open(theme_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading theme: {e}")
    
    # Return a default enhanced theme if no custom theme was found
    return {
        'background': '#F0F0F0',
        'center_fill': '#222222',
        'center_outline': '#4444FF',
        'center_text': '#FFFFFF',
        'arm_color': '#555555',          # Slightly lighter for better visibility
        'arm_selected': '#0088FF',
        'arm_width': 3,                  # Slightly thicker for better visibility
        'arm_selected_width': 5,
        'node_fill': '#333333',
        'node_selected': '#0088FF',
        'node_text': '#FFFFFF',
        'label_text': '#000000',
        'label_selected': '#0088FF',
        'font_family': 'Arial',
    }


if __name__ == "__main__":
    # Test the radial menu
    import time
    import sys
    import os
    
    # Import the copyboard core module
    try:
        # Try to add parent directory to path if running as standalone script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        # Try to import from copyboard_extension first
        try:
            from copyboard_extension import core
        except ImportError:
            # Then try to import from parent module
            sys.path.insert(0, os.path.dirname(parent_dir))
            import copyboard as core
    except ImportError as e:
        print(f"Could not import copyboard core module: {e}")
        sys.exit(1)
    
    # Add some test items to the clipboard board
    core.clear_board()
    for i in range(5):
        pyperclip.copy(f"Test item {i+1}")
        core.copy_to_board()
        time.sleep(0.1)
    
    # Show the radial menu
    show_radial_menu(400, 300)
