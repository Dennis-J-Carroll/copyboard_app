#!/usr/bin/env python3
"""
Nautilus extension for Copyboard

This module provides a Nautilus file manager extension for Copyboard,
allowing users to access their clipboard history through the context menu
and a radial widget interface.
"""
import gi
gi.require_version('Nautilus', '3.0')
from gi.repository import Nautilus, GObject, Gdk, Gtk
import subprocess

class CopyboardExtension(GObject.GObject, Nautilus.MenuProvider):
    """Nautilus extension for Copyboard with enhanced context menu and radial widget"""
    
    def __init__(self):
        """Initialize the extension"""
        super().__init__()
        self.right_click_timer = None
        self.right_click_duration = 0.5  # seconds to hold for radial menu
        self.right_click_active = False
        self.mouse_position = (0, 0)
        
    def _get_copyboard_items(self):
        """Get clipboard items from copyboard"""
        try:
            # Import the copyboard module
            from . import core
            return core.get_board()
        except ImportError:
            # Fallback to direct import if relative import fails
            try:
                import copyboard_extension.core as core
                return core.get_board()
            except ImportError:
                print("Failed to import copyboard_extension.core")
                return []
    
    def paste_from_copyboard(self, menu, item_index):
        """Paste the selected item from copyboard"""
        try:
            from . import core
            if core.paste_from_board(item_index):
                print(f"Successfully pasted item {item_index} from copyboard")
            else:
                print(f"Failed to paste item {item_index} from copyboard")
        except ImportError:
            try:
                import copyboard_extension.core as core
                if core.paste_from_board(item_index):
                    print(f"Successfully pasted item {item_index} from copyboard")
                else:
                    print(f"Failed to paste item {item_index} from copyboard")
            except Exception as e:
                print(f"Error pasting from copyboard: {e}")
    
    def show_radial_menu(self, menu_item=None):
        """Show the radial menu for clipboard items"""
        try:
            # Get the current mouse position
            display = Gdk.Display.get_default()
            if display:
                seat = display.get_default_seat()
                if seat:
                    pointer = seat.get_pointer()
                    screen, x, y = pointer.get_position()
                    
                    # Get clipboard items
                    items = self._get_copyboard_items()
                    if not items:
                        print("No items in clipboard board for radial menu")
                        return
                    
                    # Import and show the radial menu
                    try:
                        from . import radial_menu
                        radial_menu.show_radial_menu(x, y)
                    except ImportError:
                        try:
                            import copyboard_extension.radial_menu as radial_menu
                            radial_menu.show_radial_menu(x, y)
                        except ImportError:
                            print("Failed to import radial_menu module")
        except Exception as e:
            print(f"Error showing radial menu: {e}")
    
    def create_menu_widget(self, item):
        """Create a custom widget for a clipboard item in the menu
        
        Args:
            item: The clipboard item text
            
        Returns:
            A Gtk.Box widget containing the item preview
        """
        # Create a box to hold the preview
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_start(4)
        box.set_margin_end(4)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        
        # Format the item preview
        if len(item) > 100:
            preview = f"{item[:100]}..."
        else:
            preview = item
            
        # Replace newlines for display
        preview = preview.replace("\n", " ↵ ")
        
        # Create the label
        label = Gtk.Label(label=preview)
        label.set_ellipsize(True)
        label.set_alignment(0, 0.5)  # Left-aligned
        label.set_line_wrap(True)
        
        box.add(label)
        box.show_all()
        
        return box
    
    def copy_to_copyboard(self, menu):
        """Copy the current selection to copyboard"""
        try:
            from . import core
            core.copy_to_board()
            # Show a notification that the item was copied
            self._show_notification("Copied to Copyboard", "Current selection copied to clipboard board")
        except ImportError:
            try:
                import copyboard_extension.core as core
                core.copy_to_board()
                self._show_notification("Copied to Copyboard", "Current selection copied to clipboard board")
            except Exception as e:
                print(f"Error copying to copyboard: {e}")
    
    def _show_notification(self, title, message):
        """Show a desktop notification
        
        Args:
            title: Notification title
            message: Notification message
        """
        try:
            # Use notify-send if available
            subprocess.run(["notify-send", title, message], check=False)
        except Exception as e:
            print(f"Error showing notification: {e}")
    
    def get_file_items(self, window, files):
        """Add context menu items for files"""
        # Create a submenu for clipboard items
        menu = Nautilus.MenuItem(
            name="CopyboardExtension::Submenu",
            label="Copyboard",
            tip="Access multi-clipboard functionality"
        )
        
        submenu = Nautilus.Menu()
        menu.set_submenu(submenu)
        
        # Add copy to board option
        copy_item = Nautilus.MenuItem(
            name="CopyboardExtension::CopyToBoard",
            label="Copy to Clipboard Board",
            tip="Add selection to clipboard board"
        )
        copy_item.connect('activate', self.copy_to_copyboard)
        submenu.append_item(copy_item)
        
        # Add separator
        separator = Nautilus.MenuItem(
            name="CopyboardExtension::Separator",
            label="-",
            tip=""
        )
        submenu.append_item(separator)
        
        # Add paste options for each item in the board
        board_items = self._get_copyboard_items()
        
        # Add main paste options with radial menu
        if board_items:
            # Add a clearly labeled radial menu option
            radial_paste_item = Nautilus.MenuItem(
                name="CopyboardExtension::RadialPaste",
                label="🔄 Open Paste Widget (Radial Menu)",
                tip="Open the radial menu widget to select an item to paste"
            )
            radial_paste_item.connect('activate', self.show_radial_menu)
            submenu.append_item(radial_paste_item)
            
            # Add separator
            separator2 = Nautilus.MenuItem(
                name="CopyboardExtension::Separator2",
                label="-",
                tip=""
            )
            submenu.append_item(separator2)
            
            # Add heading for paste items
            heading_item = Nautilus.MenuItem(
                name="CopyboardExtension::PasteHeading",
                label="📋 Clipboard History:",
                tip="Select an item to paste"
            )
            submenu.append_item(heading_item)
            
            # Add regular paste items with better previews
            for idx, item in enumerate(board_items):
                # Create a more descriptive preview
                if len(item) > 50:
                    preview = f"{item[:50]}..."
                else:
                    preview = item
                    
                # Replace newlines and tabs for display
                preview = preview.replace("\n", "↵").replace("\t", "→")
                
                # Add item number and preview
                paste_item = Nautilus.MenuItem(
                    name=f"CopyboardExtension::PasteItem{idx}",
                    label=f"{idx}: {preview}",
                    tip=f"Paste clipboard item {idx}"
                )
                paste_item.connect('activate', self.paste_from_copyboard, idx)
                submenu.append_item(paste_item)
        else:
            empty_item = Nautilus.MenuItem(
                name="CopyboardExtension::Empty",
                label="No items in clipboard board",
                tip="Copy items to board first"
            )
            submenu.append_item(empty_item)
            
        return [menu]
    
    def get_background_items(self, window, folder):
        """Add context menu items for folder background"""
        return self.get_file_items(window, [])
