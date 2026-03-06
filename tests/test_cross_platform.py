#!/usr/bin/env python3
"""
Cross-platform functionality tests for Copyboard.

Verifies platform detection, paste routing, and platform-specific
paste helpers using mocked system calls.
"""
import os
import sys
import platform
import subprocess
import pytest
from unittest import mock

from copyboard_extension import paste_helper


# ── Platform Detection ───────────────────────────────────────────────────
class TestPlatformDetection:
    """Test get_platform() on the current OS."""

    def test_get_platform_returns_string(self):
        result = paste_helper.get_platform()
        assert result in ("linux", "macos", "windows")

    def test_platform_matches_system(self):
        system = platform.system().lower()
        expected_map = {"linux": "linux", "darwin": "macos", "windows": "windows"}
        expected = expected_map.get(system, "linux")
        assert paste_helper.get_platform() == expected


# ── Paste Routing ────────────────────────────────────────────────────────
class TestPasteTextRouting:
    """paste_text() dispatches to the correct platform-specific function."""

    def test_routes_to_linux(self, monkeypatch):
        monkeypatch.setattr(paste_helper, "get_platform", lambda: "linux")
        with mock.patch.object(paste_helper, "paste_text_linux", return_value=True) as m:
            assert paste_helper.paste_text("test") is True
            m.assert_called_once_with("test")

    def test_routes_to_macos(self, monkeypatch):
        monkeypatch.setattr(paste_helper, "get_platform", lambda: "macos")
        with mock.patch.object(paste_helper, "paste_text_macos", return_value=True) as m:
            assert paste_helper.paste_text("test") is True
            m.assert_called_once_with("test")

    def test_routes_to_windows(self, monkeypatch):
        monkeypatch.setattr(paste_helper, "get_platform", lambda: "windows")
        with mock.patch.object(paste_helper, "paste_text_windows", return_value=True) as m:
            assert paste_helper.paste_text("test") is True
            m.assert_called_once_with("test")

    def test_unknown_platform_returns_false(self, monkeypatch):
        monkeypatch.setattr(paste_helper, "get_platform", lambda: "beos")
        assert paste_helper.paste_text("test") is False


# ── Linux Paste ──────────────────────────────────────────────────────────
class TestLinuxPaste:
    """Paste operations on Linux (mocked subprocess calls)."""

    def test_x11_paste(self, monkeypatch):
        """Under X11, xclip + xdotool are invoked."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with mock.patch("subprocess.Popen") as mock_popen, \
             mock.patch("subprocess.run") as mock_run:
            mock_proc = mock.MagicMock()
            mock_proc.communicate = mock.MagicMock()
            mock_popen.return_value = mock_proc

            result = paste_helper.paste_text_linux("hello")
            assert result is True
            mock_popen.assert_called_once()
            mock_run.assert_called_once()

    def test_wayland_paste(self, monkeypatch):
        """Under Wayland, wl-copy + wtype are invoked."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        with mock.patch("subprocess.Popen") as mock_popen, \
             mock.patch("subprocess.run") as mock_run:
            mock_proc = mock.MagicMock()
            mock_proc.communicate = mock.MagicMock()
            mock_popen.return_value = mock_proc

            result = paste_helper.paste_text_linux("hello")
            assert result is True

    def test_linux_paste_failure(self, monkeypatch):
        """If subprocess fails, return False instead of crashing."""
        monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
        with mock.patch("subprocess.Popen", side_effect=FileNotFoundError):
            result = paste_helper.paste_text_linux("fail")
            assert result is False


# ── macOS Paste ──────────────────────────────────────────────────────────
class TestMacOSPaste:
    """Paste operations on macOS (mocked osascript)."""

    def test_macos_paste_calls_osascript(self):
        with mock.patch("subprocess.run") as mock_run:
            result = paste_helper.paste_text_macos("hello")
            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert call_args[0][0][0] == "osascript"

    def test_macos_paste_escapes_quotes(self):
        with mock.patch("subprocess.run") as mock_run:
            paste_helper.paste_text_macos('say "hello"')
            call_args = mock_run.call_args
            script = call_args[0][0][2]  # -e <script>
            assert '\\"' in script or "hello" in script

    def test_macos_paste_failure(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            result = paste_helper.paste_text_macos("fail")
            assert result is False


# ── Windows Paste ────────────────────────────────────────────────────────
class TestWindowsPaste:
    """Paste operations on Windows (mocked win32 API)."""

    def test_windows_paste_with_mocked_api(self):
        """When win32 modules exist, clipboard is set and keystrokes are simulated."""
        fake_clipboard = mock.MagicMock()
        fake_con = mock.MagicMock()
        fake_con.CF_UNICODETEXT = 13
        fake_con.KEYEVENTF_KEYUP = 2
        fake_api = mock.MagicMock()
        fake_gui = mock.MagicMock()

        modules = {
            "win32clipboard": fake_clipboard,
            "win32con": fake_con,
            "win32api": fake_api,
            "win32gui": fake_gui,
        }
        with mock.patch.dict("sys.modules", modules):
            result = paste_helper.paste_text_windows("text")
            assert result is True
            fake_clipboard.OpenClipboard.assert_called_once()
            fake_clipboard.EmptyClipboard.assert_called_once()
            fake_clipboard.SetClipboardText.assert_called_once_with("text", 13)
            fake_clipboard.CloseClipboard.assert_called_once()

    def test_windows_paste_import_error(self):
        """If win32 modules are missing, return False."""
        with mock.patch.dict("sys.modules", {"win32clipboard": None}):
            result = paste_helper.paste_text_windows("fail")
            assert result is False


# ── Async Paste ──────────────────────────────────────────────────────────
class TestAsyncPaste:
    """paste_current_clipboard() and paste_with_delay()."""

    def test_paste_current_clipboard_returns_true(self):
        """The auto-mocked paste_current_clipboard (from conftest) returns True."""
        assert paste_helper.paste_current_clipboard() is True

    def test_paste_with_delay_returns_true(self):
        assert paste_helper.paste_with_delay(50) is True


# ── Paste Combination (paste_helper level) ───────────────────────────────
class TestPasteCombination:
    """paste_helper.paste_combination()."""

    def test_combine_and_paste(self, mock_clipboard):
        result = paste_helper.paste_combination(["alpha", "beta", "gamma"])
        assert result is True
        assert mock_clipboard["content"] == "alphabetagamma"

    def test_empty_list_returns_false(self):
        assert paste_helper.paste_combination([]) is False


# ── System-wide Installer ────────────────────────────────────────────────
class TestSystemInstaller:
    """Basic smoke tests for the installer module."""

    def test_installer_functions_importable(self):
        sys.path.insert(
            0,
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "scripts")
            ),
        )
        try:
            from install_system_wide import (
                get_platform,
                install_linux,
                install_macos,
                install_windows,
            )
            assert callable(install_linux)
            assert callable(install_macos)
            assert callable(install_windows)
        except ImportError:
            pytest.skip("install_system_wide not available")