#!/usr/bin/env python3
"""
Cross-platform functionality tests for Copyboard

This test suite verifies that Copyboard works correctly across
Linux, macOS, and Windows platforms.
"""

import os
import sys
import unittest
import platform
import tempfile
import json
from pathlib import Path
from unittest import mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from copyboard_extension import core, paste_helper

class TestPlatformDetection(unittest.TestCase):
    """Test platform detection functionality"""
    
    def test_get_platform(self):
        """Test that platform detection returns the correct platform"""
        system = platform.system().lower()
        
        if system == "darwin":
            expected = "macos"
        elif system == "windows":
            expected = "windows"
        else:
            expected = "linux"
            
        self.assertEqual(paste_helper.get_platform(), expected)

class TestCoreFeatures(unittest.TestCase):
    """Test core features across platforms"""
    
    def setUp(self):
        """Set up test environment"""
        # Create a temporary board file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_board_file = os.path.join(self.temp_dir.name, "board.json")
        
        # Save original board file path
        self.original_board_file = core.BOARD_FILE
        
        # Set board file to our temporary file
        core.BOARD_FILE = self.temp_board_file
        
        # Clear the board
        core._board = []
        core._save_board()
    
    def tearDown(self):
        """Clean up after tests"""
        # Restore original board file path
        core.BOARD_FILE = self.original_board_file
        
        # Clean up temporary directory
        self.temp_dir.cleanup()
    
    def test_add_to_board(self):
        """Test adding items to the board"""
        # Add some items
        core.copy_to_board("Test item 1")
        core.copy_to_board("Test item 2")
        
        # Check that they were added
        board = core.get_board()
        self.assertEqual(len(board), 2)
        self.assertEqual(board[0], "Test item 2")  # Most recent should be first
        self.assertEqual(board[1], "Test item 1")
    
    def test_board_persistence(self):
        """Test that the board is saved to disk"""
        # Add some items
        core.copy_to_board("Test persistence")
        
        # Check that the file exists and contains the item
        self.assertTrue(os.path.exists(self.temp_board_file))
        
        with open(self.temp_board_file, 'r') as f:
            saved_board = json.load(f)
        
        self.assertEqual(len(saved_board), 1)
        self.assertEqual(saved_board[0], "Test persistence")
    
    def test_board_max_size(self):
        """Test that the board respects the maximum size"""
        # Add more items than the maximum
        for i in range(core.MAX_BOARD_SIZE + 5):
            core.copy_to_board(f"Test item {i}")
        
        # Check that only MAX_BOARD_SIZE items are kept
        board = core.get_board()
        self.assertEqual(len(board), core.MAX_BOARD_SIZE)
        
        # Check that the most recent items are kept
        self.assertEqual(board[0], f"Test item {core.MAX_BOARD_SIZE + 4}")

class TestPasteHelper(unittest.TestCase):
    """Test paste helper functionality"""
    
    def test_paste_text(self):
        """Test paste_text function with mocked platform-specific functions"""
        test_text = "Test paste text"
        
        # Test Linux paste
        with mock.patch('copyboard_extension.paste_helper.get_platform', return_value='linux'), \
             mock.patch('copyboard_extension.paste_helper.paste_text_linux', return_value=True) as mock_linux:
            result = paste_helper.paste_text(test_text)
            self.assertTrue(result)
            mock_linux.assert_called_once_with(test_text)
        
        # Test macOS paste
        with mock.patch('copyboard_extension.paste_helper.get_platform', return_value='macos'), \
             mock.patch('copyboard_extension.paste_helper.paste_text_macos', return_value=True) as mock_macos:
            result = paste_helper.paste_text(test_text)
            self.assertTrue(result)
            mock_macos.assert_called_once_with(test_text)
        
        # Test Windows paste
        with mock.patch('copyboard_extension.paste_helper.get_platform', return_value='windows'), \
             mock.patch('copyboard_extension.paste_helper.paste_text_windows', return_value=True) as mock_windows:
            result = paste_helper.paste_text(test_text)
            self.assertTrue(result)
            mock_windows.assert_called_once_with(test_text)
    
    @unittest.skipIf(platform.system().lower() != "linux", "Linux-specific test")
    def test_linux_paste(self):
        """Test Linux-specific paste functionality"""
        # This is a basic test that just checks if the function runs without errors
        # We can't fully test the paste functionality in an automated test
        
        # Mock subprocess to avoid actual command execution
        with mock.patch('subprocess.Popen'), \
             mock.patch('subprocess.run'):
            result = paste_helper.paste_text_linux("Test Linux paste")
            # We're just checking it doesn't raise an exception
            self.assertIsNotNone(result)
    
    @unittest.skipIf(platform.system().lower() != "darwin", "macOS-specific test")
    def test_macos_paste(self):
        """Test macOS-specific paste functionality"""
        # Mock subprocess to avoid actual command execution
        with mock.patch('subprocess.run'):
            result = paste_helper.paste_text_macos("Test macOS paste")
            # We're just checking it doesn't raise an exception
            self.assertIsNotNone(result)
    
    @unittest.skipIf(platform.system().lower() != "windows", "Windows-specific test")
    def test_windows_paste(self):
        """Test Windows-specific paste functionality"""
        try:
            # Try to import Windows-specific modules
            import win32clipboard
            import win32con
            import win32api
            
            # Mock Windows API calls
            with mock.patch('win32clipboard.OpenClipboard'), \
                 mock.patch('win32clipboard.EmptyClipboard'), \
                 mock.patch('win32clipboard.SetClipboardText'), \
                 mock.patch('win32clipboard.CloseClipboard'), \
                 mock.patch('win32api.keybd_event'):
                result = paste_helper.paste_text_windows("Test Windows paste")
                # We're just checking it doesn't raise an exception
                self.assertIsNotNone(result)
        except ImportError:
            # Skip test if Windows modules aren't available
            self.skipTest("Windows modules not available")

class TestSystemWideInstaller(unittest.TestCase):
    """Test system-wide installer functionality"""
    
    def test_platform_detection(self):
        """Test that the installer correctly detects the platform"""
        # Import the installer module
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
        from install_system_wide import get_platform
        
        system = platform.system().lower()
        
        if system == "darwin":
            expected = "macos"
        elif system == "windows":
            expected = "windows"
        else:
            expected = "linux"
            
        self.assertEqual(get_platform(), expected)
    
    def test_installer_functions_exist(self):
        """Test that platform-specific installer functions exist"""
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
        from install_system_wide import install_linux, install_macos, install_windows
        
        # Just check that the functions exist
        self.assertTrue(callable(install_linux))
        self.assertTrue(callable(install_macos))
        self.assertTrue(callable(install_windows))

if __name__ == '__main__':
    unittest.main() 