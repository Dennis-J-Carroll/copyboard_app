#!/usr/bin/env python3
"""
Copyboard GUI - A standalone graphical user interface for Copyboard
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import pyperclip
import threading
import time

# Add the parent directory to the path to ensure imports work correctly
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from . import core, paste_helper
except ImportError as e:
    print(f"Error importing copyboard modules: {e}")
    sys.exit(1)

class CopyboardGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Copyboard")
        self.root.geometry("600x400")
        self.root.minsize(500, 300)
        
        # Set icon if available
        try:
            self.root.iconbitmap("clipboard.ico")
        except:
            pass
            
        # Configure style
        self.style = ttk.Style()
        self.style.configure("TButton", padding=6, relief="flat", background="#2196F3")
        self.style.configure("Clipboard.TFrame", background="#f5f5f5")
        
        # Create frame
        self.main_frame = ttk.Frame(self.root, padding="10", style="Clipboard.TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create header
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="Copyboard", font=("Arial", 16, "bold")).pack(side=tk.LEFT)
        
        # Create buttons frame
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT)
        
        ttk.Button(button_frame, text="Copy Current", command=self.copy_to_board).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear All", command=self.clear_board).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.refresh_list).pack(side=tk.LEFT, padx=5)
        
        # Create clipboard items frame
        self.items_frame = ttk.Frame(self.main_frame)
        self.items_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollable listbox
        self.listbox_frame = ttk.Frame(self.items_frame)
        self.listbox_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.listbox = tk.Listbox(self.listbox_frame, selectmode=tk.EXTENDED, font=("Arial", 10), 
                              relief=tk.FLAT, bd=0, highlightthickness=0)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar for listbox
        scrollbar = ttk.Scrollbar(self.listbox_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # Create action buttons frame
        action_frame = ttk.Frame(self.items_frame)
        action_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        ttk.Button(action_frame, text="Paste Selected", command=self.paste_selected).pack(fill=tk.X, pady=5)
        ttk.Button(action_frame, text="Combine & Paste", command=self.combine_and_paste).pack(fill=tk.X, pady=5)
        ttk.Button(action_frame, text="Remove", command=self.remove_selected).pack(fill=tk.X, pady=5)
        ttk.Button(action_frame, text="Edit", command=self.edit_selected).pack(fill=tk.X, pady=5)
        
        # Status bar
        self.status_var = tk.StringVar()
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Populate listbox
        self.refresh_list()
        
        # Set up clipboard monitoring
        self.monitor_active = True
        self.monitor_thread = threading.Thread(target=self.monitor_clipboard)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def refresh_list(self):
        """Refresh the clipboard items in the listbox"""
        self.listbox.delete(0, tk.END)
        
        # Get items from clipboard board
        items = core.get_board()
        
        # Add items to listbox
        for idx, item in enumerate(items):
            # Create a preview (truncate if too long)
            preview = item
            if len(preview) > 50:
                preview = preview[:47] + "..."
                
            # Replace newlines for display
            preview = preview.replace("\n", "↵ ")
            
            # Add to listbox with index
            self.listbox.insert(tk.END, f"{idx}: {preview}")
        
        # Update status
        self.status_var.set(f"Clipboard items: {len(items)}")
    
    def copy_to_board(self):
        """Copy current clipboard to board"""
        core.copy_to_board()
        self.refresh_list()
        self.status_var.set("Copied current clipboard to board")
    
    def paste_selected(self):
        """Paste the selected item"""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Copyboard", "Please select an item to paste")
            return
            
        # Get the first selected item index
        selected_idx = selection[0]
        
        # Extract the item index from the listbox text (format: "0: text")
        item_idx = int(self.listbox.get(selected_idx).split(":")[0])
        
        # Paste the item
        if core.paste_from_board(item_idx):
            self.status_var.set(f"Pasted item {item_idx}")
        else:
            self.status_var.set("Failed to paste item")
    
    def combine_and_paste(self):
        """Combine selected items and paste them"""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Copyboard", "Please select items to combine")
            return
            
        # Get all selected item indices
        indices = []
        for selected_idx in selection:
            # Extract the item index from the listbox text (format: "0: text")
            item_idx = int(self.listbox.get(selected_idx).split(":")[0])
            indices.append(item_idx)
            
        # Paste the combined items
        if core.paste_combination(indices):
            self.status_var.set(f"Pasted combined items: {', '.join(map(str, indices))}")
        else:
            self.status_var.set("Failed to paste combined items")
    
    def remove_selected(self):
        """Remove selected items from the board"""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Copyboard", "Please select items to remove")
            return
            
        # Get all selected item indices (in reverse order to avoid reindexing issues)
        indices = sorted([
            int(self.listbox.get(selected_idx).split(":")[0])
            for selected_idx in selection
        ], reverse=True)
            
        # Remove all selected items
        for idx in indices:
            core.drop_item(idx)
            
        self.refresh_list()
        self.status_var.set(f"Removed {len(indices)} item(s)")
    
    def edit_selected(self):
        """Edit the selected item"""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("Copyboard", "Please select an item to edit")
            return
            
        # Get the first selected item index
        selected_idx = selection[0]
        
        # Extract the item index from the listbox text (format: "0: text")
        item_idx = int(self.listbox.get(selected_idx).split(":")[0])
        
        # Get the item content
        item_content = core.get_board_item(item_idx)
        
        # Create edit dialog
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Edit Clipboard Item {item_idx}")
        edit_window.geometry("500x300")
        edit_window.minsize(400, 200)
        
        # Make dialog modal
        edit_window.transient(self.root)
        edit_window.grab_set()
        
        # Create text field
        text_frame = ttk.Frame(edit_window, padding=10)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Arial", 10))
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.config(yscrollcommand=scrollbar.set)
        
        # Set initial content
        text_widget.insert("1.0", item_content)
        
        # Create buttons
        button_frame = ttk.Frame(edit_window, padding=10)
        button_frame.pack(fill=tk.X)
        
        def save_changes():
            # Get the edited text
            new_content = text_widget.get("1.0", tk.END)
            
            # Update the board
            board = core.get_board()
            if item_idx < len(board):
                board[item_idx] = new_content
            
            # Close dialog
            edit_window.destroy()
            
            # Refresh list
            self.refresh_list()
            self.status_var.set(f"Updated item {item_idx}")
        
        ttk.Button(button_frame, text="Save", command=save_changes).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=edit_window.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Focus text widget
        text_widget.focus_set()
    
    def clear_board(self):
        """Clear all items from the board"""
        if messagebox.askyesno("Copyboard", "Are you sure you want to clear all clipboard items?"):
            core.clear_board()
            self.refresh_list()
            self.status_var.set("Cleared all clipboard items")
    
    def monitor_clipboard(self):
        """Monitor system clipboard for changes"""
        last_content = pyperclip.paste()
        
        while self.monitor_active:
            try:
                current_content = pyperclip.paste()
                
                # If clipboard content changed, add to board and refresh list
                if current_content != last_content:
                    last_content = current_content
                    core.copy_to_board()
                    
                    # Update UI in main thread
                    self.root.after(0, self.refresh_list)
            except:
                pass
                
            # Sleep briefly to reduce CPU usage
            time.sleep(0.5)
    
    def on_close(self):
        """Handle window close event"""
        self.monitor_active = False
        self.root.destroy()

def main():
    root = tk.Tk()
    app = CopyboardGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
