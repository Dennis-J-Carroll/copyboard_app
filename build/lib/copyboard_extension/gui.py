"""
Copyboard GUI - A graphical user interface for the multi-clipboard utility
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from typing import Dict, Any, Optional

from . import core

class CopyboardGUI:
    """Main GUI application for Copyboard"""
    
    def __init__(self, root: Optional[tk.Tk] = None):
        """Initialize the GUI"""
        self.root = root or tk.Tk()
        self.root.title("Copyboard - Multi-Clipboard")
        self.root.geometry("500x400")
        self.root.minsize(400, 300)
        
        self.setup_ui()
        self.monitoring = False
        self.monitor_thread = None
        self.last_clipboard_content = ""
        
    def setup_ui(self):
        """Set up the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Clipboard board frame
        board_frame = ttk.LabelFrame(main_frame, text="Clipboard Board", padding="5")
        board_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Clipboard items listbox with scrollbar
        list_frame = ttk.Frame(board_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.board_listbox = tk.Listbox(
            list_frame, 
            selectmode=tk.SINGLE,
            font=("Courier", 10),
            yscrollcommand=scrollbar.set
        )
        self.board_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.board_listbox.yview)
        
        # Action buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        # Monitoring toggle
        self.monitor_var = tk.BooleanVar(value=False)
        self.monitor_checkbox = ttk.Checkbutton(
            buttons_frame,
            text="Monitor Clipboard",
            variable=self.monitor_var,
            command=self.toggle_monitoring
        )
        self.monitor_checkbox.pack(side=tk.LEFT, padx=5)
        
        # Action buttons
        ttk.Button(
            buttons_frame, 
            text="Copy Selected",
            command=self.copy_selected
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            buttons_frame, 
            text="Copy All",
            command=self.copy_all
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            buttons_frame, 
            text="Remove Selected",
            command=self.remove_selected
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            buttons_frame, 
            text="Clear Board",
            command=self.clear_board
        ).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root, 
            textvariable=self.status_var, 
            relief=tk.SUNKEN, 
            anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Update the board display
        self.update_board_display()
    
    def update_board_display(self):
        """Update the listbox with the current clipboard board"""
        self.board_listbox.delete(0, tk.END)
        board_previews = core.get_board_preview(40)
        
        for idx in range(core.get_board_size()):
            self.board_listbox.insert(tk.END, board_previews[idx])
            
        if core.get_board_size() == 0:
            self.board_listbox.insert(tk.END, "Clipboard board is empty")
            
        self.status_var.set(f"Board size: {core.get_board_size()}")
    
    def copy_selected(self):
        """Copy the selected item to the clipboard"""
        selection = self.board_listbox.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select an item from the board.")
            return
        
        index = selection[0]
        if index >= core.get_board_size():
            return  # Empty board message selected
            
        if core.paste_from_board(index):
            self.status_var.set(f"Copied item {index} to clipboard")
        else:
            self.status_var.set("Failed to copy item")
    
    def copy_all(self):
        """Copy all items to the clipboard, concatenated with newlines"""
        if core.paste_all():
            self.status_var.set("Copied all items to clipboard")
        else:
            self.status_var.set("No items to copy")
    
    def remove_selected(self):
        """Remove the selected item from the board"""
        selection = self.board_listbox.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select an item to remove.")
            return
            
        index = selection[0]
        if index >= core.get_board_size():
            return  # Empty board message selected
            
        if core.drop_item(index):
            self.update_board_display()
            self.status_var.set(f"Removed item {index}")
        else:
            self.status_var.set("Failed to remove item")
    
    def clear_board(self):
        """Clear all items from the board"""
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear the clipboard board?"):
            core.clear_board()
            self.update_board_display()
            self.status_var.set("Clipboard board cleared")
    
    def toggle_monitoring(self):
        """Toggle clipboard monitoring on/off"""
        if self.monitor_var.get():
            self.start_monitoring()
        else:
            self.stop_monitoring()
    
    def start_monitoring(self):
        """Start monitoring the clipboard for changes"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.last_clipboard_content = ""
        
        # Start monitoring in a separate thread
        self.monitor_thread = threading.Thread(
            target=self.monitor_clipboard,
            daemon=True
        )
        self.monitor_thread.start()
        
        self.status_var.set("Monitoring clipboard...")
    
    def stop_monitoring(self):
        """Stop monitoring the clipboard"""
        self.monitoring = False
        self.status_var.set("Monitoring stopped")
    
    def monitor_clipboard(self):
        """Monitor the clipboard for changes and add to board"""
        while self.monitoring:
            try:
                current_content = ""
                try:
                    current_content = self.root.clipboard_get()
                except tk.TclError:
                    # Clipboard might be empty or contain non-text content
                    pass
                    
                if current_content and current_content != self.last_clipboard_content:
                    self.last_clipboard_content = current_content
                    core.copy_to_board()
                    
                    # Update the UI from the main thread
                    self.root.after(0, self.update_board_display)
            except Exception as e:
                print(f"Error monitoring clipboard: {e}")
                
            # Check every half second
            time.sleep(0.5)
    
    def run(self):
        """Run the main event loop"""
        self.root.mainloop()


def run_gui():
    """Run the Copyboard GUI application"""
    root = tk.Tk()
    app = CopyboardGUI(root)
    app.run()


if __name__ == "__main__":
    run_gui()
