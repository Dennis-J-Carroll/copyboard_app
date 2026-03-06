"""
Agent API – A clean, JSON-returning Python interface for AI coding agents.

Any agent framework can import this module and interact with Copyboard
programmatically. All functions return plain dicts suitable for JSON
serialisation — no stdout printing, no side effects beyond clipboard ops.

Usage from an agent:
    from copyboard_extension.agent_api import (
        get_profile, fire_snippet, search_snippets,
        get_chambers, add_snippet, get_board, add_to_board,
    )

    profile = get_profile()        # coding fingerprint
    result  = fire_snippet(0, 2)   # fire Git → "Log graph"
    hits    = search_snippets("docker")
"""

from typing import Dict, Any, List, Optional

from .snippet_manager import SnippetManager, snippets as _default_snippets
from .profile_generator import generate_profile, profile_to_markdown
from . import core


def _mgr() -> SnippetManager:
    """Return the module-level singleton (allows test override)."""
    return _default_snippets


# ── Profile ──────────────────────────────────────────────────────────────

def get_profile(as_markdown: bool = False) -> Any:
    """Return the user's coding profile.

    Args:
        as_markdown: If True, return a markdown string. Otherwise a dict.

    Returns:
        A dict (JSON-ready) or a markdown string.
    """
    try:
        from .config_manager import config as cfg
    except Exception:
        cfg = None

    profile = generate_profile(_mgr(), cfg)

    if as_markdown:
        return profile_to_markdown(profile)
    return profile


# ── Snippets ─────────────────────────────────────────────────────────────

def get_chambers() -> List[Dict[str, Any]]:
    """Return all snippet chambers with their snippets.

    Returns:
        List of chamber dicts, each containing name, icon, color, snippets.
    """
    return _mgr().get_chambers()


def get_chamber(index: int) -> Optional[Dict[str, Any]]:
    """Return a single chamber by index."""
    return _mgr().get_chamber(index)


def fire_snippet(chamber: int, snippet: int,
                 expand: bool = True) -> Dict[str, Any]:
    """Fire (paste) a snippet. Copies it to the system clipboard.

    Args:
        chamber: Chamber index.
        snippet: Snippet index within the chamber.
        expand:  Expand template variables (${date}, ${user}, etc.).

    Returns:
        {"ok": True, "text": "...", "label": "..."} on success,
        {"ok": False, "error": "..."} on failure.
    """
    mgr = _mgr()
    ch = mgr.get_chamber(chamber)
    if ch is None:
        return {"ok": False, "error": f"Invalid chamber index: {chamber}"}

    snips = ch.get("snippets", [])
    if snippet < 0 or snippet >= len(snips):
        return {"ok": False, "error": f"Invalid snippet index: {snippet}"}

    text = mgr.fire(chamber, snippet, expand=expand)
    if text is None:
        return {"ok": False, "error": "Failed to fire snippet"}

    return {
        "ok": True,
        "text": text,
        "label": snips[snippet].get("label", ""),
        "chamber": ch["name"],
    }


def fire_by_label(label: str, expand: bool = True) -> Dict[str, Any]:
    """Fire a snippet by searching for its label.

    Args:
        label: Snippet label (case-insensitive match).

    Returns:
        {"ok": True, "text": "..."} on success,
        {"ok": False, "error": "..."} on failure.
    """
    text = _mgr().fire_by_label(label, expand=expand)
    if text is None:
        return {"ok": False, "error": f"No snippet with label '{label}'"}
    return {"ok": True, "text": text, "label": label}


def search_snippets(query: str) -> List[Dict[str, Any]]:
    """Search for snippets across all chambers.

    Args:
        query: Search string (matches labels and text).

    Returns:
        List of matching snippet dicts with chamber info.
    """
    return _mgr().search(query)


def get_top_snippets(count: int = 10) -> List[Dict[str, Any]]:
    """Return the user's most-used snippets (by frecency).

    Returns:
        List of dicts with chamber, label, uses, text.
    """
    return _mgr().get_top_snippets(count)


def add_snippet(chamber: int, label: str, text: str) -> Dict[str, Any]:
    """Add a new snippet to a chamber.

    Args:
        chamber: Chamber index.
        label:   Human-readable label.
        text:    Snippet text (may include ${cursor} etc.).

    Returns:
        {"ok": True} on success, {"ok": False, "error": "..."} on failure.
    """
    if _mgr().add_snippet(chamber, label, text):
        return {"ok": True, "chamber": chamber, "label": label}
    return {"ok": False, "error": f"Invalid chamber index: {chamber}"}


def add_chamber(name: str, icon: str = "⚪",
                snippets: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Add a new snippet chamber.

    Args:
        name: Chamber name.
        icon: Emoji icon.
        snippets: Optional initial snippets [{"label": ..., "text": ...}].

    Returns:
        {"ok": True, "index": <int>}
    """
    idx = _mgr().add_chamber(name, icon, snippets=snippets)
    return {"ok": True, "index": idx, "name": name}


def remove_snippet(chamber: int, snippet: int) -> Dict[str, Any]:
    """Remove a snippet from a chamber."""
    if _mgr().remove_snippet(chamber, snippet):
        return {"ok": True}
    return {"ok": False, "error": "Invalid chamber or snippet index"}


# ── Clipboard Board ─────────────────────────────────────────────────────

def get_board() -> Dict[str, Any]:
    """Return the current clipboard board contents.

    Returns:
        {"items": [...], "count": <int>}
    """
    items = core.get_board()
    return {
        "items": items if isinstance(items, list) else [],
        "count": core.get_board_size(),
    }


def add_to_board(text: str) -> Dict[str, Any]:
    """Add text to the clipboard board.

    Args:
        text: Text to add.

    Returns:
        {"ok": True, "position": 0}
    """
    try:
        import pyperclip
        pyperclip.copy(text)
    except Exception:
        pass
    core.copy_to_board(text)
    return {"ok": True, "position": 0}


# ── Convenience for agents ───────────────────────────────────────────────

def describe() -> Dict[str, Any]:
    """Return a summary of all available Copyboard agent capabilities.

    Useful for agent self-discovery / tool enumeration.
    """
    return {
        "name": "Copyboard",
        "version": "1.0",
        "description": (
            "A multi-clipboard utility with a Code Revolver snippet system. "
            "Agents can read the user's coding profile, fire preloaded "
            "code snippets, search for patterns, and manage the clipboard board."
        ),
        "capabilities": {
            "get_profile": "Get the user's coding fingerprint (inferred from usage)",
            "fire_snippet": "Fire a snippet by chamber/index (copies to clipboard)",
            "fire_by_label": "Fire a snippet by label name",
            "search_snippets": "Search snippets by keyword",
            "get_chambers": "List all snippet chambers",
            "get_top_snippets": "Get most-used snippets",
            "add_snippet": "Add a snippet to a chamber",
            "add_chamber": "Create a new snippet chamber",
            "remove_snippet": "Remove a snippet",
            "get_board": "Get current clipboard board",
            "add_to_board": "Add text to the clipboard board",
        },
        "chamber_count": _mgr().get_chamber_count(),
        "snippet_count": sum(
            len(c.get("snippets", []))
            for c in _mgr().get_chambers()
        ),
    }
