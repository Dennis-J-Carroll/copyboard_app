"""
Rapid Clipboard - Fast copy-paste operations integrated module
"""
import threading
import time
from typing import List, Optional, Dict

from . import core
from . import hotkeys
from . import paste_helper

# Initialize hotkeys if available
try:
    hotkeys.setup_default_hotkeys(core)
    HOTKEYS_ENABLED = True
except Exception:
    HOTKEYS_ENABLED = False

class RapidClipboard:
    """
    Rapid Clipboard class for fast copy-paste operations
    Provides a simplified interface to the core functionality
    """
    
    @staticmethod
    def copy(content: Optional[str] = None) -> str:
        """
        Copy content to clipboard and board
        
        Args:
            content: Content to copy. If None, uses current clipboard.
            
        Returns:
            The copied content
        """
        return core.copy_to_board(content)
    
    @staticmethod
    def paste(index: int = 0) -> bool:
        """
        Paste content from board at index
        
        Args:
            index: Board index to paste from
            
        Returns:
            True if successful
        """
        return core.paste_from_board(index)
    
    @staticmethod
    def copy_paste(content: str) -> bool:
        """
        One-step copy and paste operation (fastest)
        
        Args:
            content: Content to copy and paste
            
        Returns:
            True if successful
        """
        return core.quick_copy_paste(content)
    
    @staticmethod
    def get_items() -> List[str]:
        """Get all clipboard items"""
        return core.get_board()
    
    @staticmethod
    def get_item(index: int) -> Optional[str]:
        """Get specific clipboard item"""
        return core.get_board_item(index)
    
    @staticmethod
    def clear() -> None:
        """Clear clipboard board"""
        core.clear_board()
    
    @staticmethod
    def remove(index: Optional[int] = None) -> bool:
        """
        Remove item from board
        
        Args:
            index: Index to remove. If None, removes oldest.
            
        Returns:
            True if successful
        """
        return core.drop_item(index)
    
    @staticmethod
    def paste_all() -> bool:
        """
        Paste all items concatenated
        
        Returns:
            True if successful
        """
        return core.paste_all()
    
    @staticmethod
    def set_max_items(count: int) -> None:
        """Set maximum number of items to store"""
        core.set_max_board_size(count)
    
    @staticmethod
    def preview_items(max_length: int = 30) -> Dict[int, str]:
        """Get preview of all clipboard items"""
        return core.get_board_preview(max_length)
    
    @staticmethod
    def delayed_paste(index: int = 0, delay_ms: int = 100) -> bool:
        """
        Paste with delay (useful for some applications)
        
        Args:
            index: Board index to paste from
            delay_ms: Delay in milliseconds
            
        Returns:
            True if scheduled
        """
        # Get content from board
        content = core.get_board_item(index)
        if content is None:
            return False
            
        # Copy to clipboard
        import pyperclip
        pyperclip.copy(content)
        
        # Schedule delayed paste
        return paste_helper.paste_with_delay(delay_ms)

# Setup background save thread to ensure changes are saved periodically
def _background_save_thread():
    while True:
        time.sleep(5)  # Check every 5 seconds
        core.force_save()

# Start background save thread
_save_thread = threading.Thread(target=_background_save_thread, daemon=True)
_save_thread.start()

# Convenience functions at module level
copy = RapidClipboard.copy
paste = RapidClipboard.paste
copy_paste = RapidClipboard.copy_paste
get_items = RapidClipboard.get_items
clear = RapidClipboard.clear 