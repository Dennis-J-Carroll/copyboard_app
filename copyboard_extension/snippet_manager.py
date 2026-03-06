"""
Snippet Manager – The engine behind the Code Revolver.

Manages "chambers" of categorised code snippets that can be spun through
and fired (pasted) via hotkeys, the radial UI, or the CLI.

Storage layout:
    ~/.config/copyboard/snippets/
        default_chambers.json   – ships with preloaded packs (read-only fallback)
        user_chambers.json      – user customisations (auto-created on first edit)
"""

import os
import json
import copy
import datetime
import getpass
from typing import List, Dict, Optional, Any, Tuple


# ── Paths ────────────────────────────────────────────────────────────────
USER_HOME = os.path.expanduser("~")
SNIPPETS_DIR = os.path.join(USER_HOME, ".config", "copyboard", "snippets")
USER_CHAMBERS_FILE = os.path.join(SNIPPETS_DIR, "user_chambers.json")
DEFAULT_CHAMBERS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "snippets", "default_chambers.json"
)

# ── Built-in default chambers (embedded fallback) ────────────────────────
BUILTIN_CHAMBERS: List[Dict[str, Any]] = [
    {
        "name": "Git",
        "icon": "🔹",
        "color": "#f05033",
        "snippets": [
            {"label": "Commit all", "text": 'git add -A && git commit -m "${cursor}"'},
            {"label": "Stash pull pop", "text": "git stash && git pull --rebase && git stash pop"},
            {"label": "Log graph", "text": "git log --oneline --graph --all -20"},
            {"label": "Diff cached", "text": "git diff --cached --stat"},
            {"label": "Soft reset", "text": "git reset --soft HEAD~1"},
            {"label": "Cherry pick", "text": "git cherry-pick ${cursor}"},
        ],
    },
    {
        "name": "Docker",
        "icon": "🔸",
        "color": "#2496ed",
        "snippets": [
            {"label": "Compose up", "text": "docker compose up -d --build"},
            {"label": "PS table", "text": "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'"},
            {"label": "Exec bash", "text": "docker exec -it ${cursor} /bin/bash"},
            {"label": "Prune all", "text": "docker system prune -af --volumes"},
            {"label": "Logs follow", "text": "docker logs -f --tail 100 ${cursor}"},
        ],
    },
    {
        "name": "Python",
        "icon": "🟢",
        "color": "#3776ab",
        "snippets": [
            {"label": "Main guard", "text": "if __name__ == '__main__':\n    main()"},
            {"label": "Type imports", "text": "from typing import List, Dict, Optional, Tuple"},
            {"label": "Try/except", "text": "try:\n    ${cursor}\nexcept Exception as e:\n    logger.error(f'Error: {e}')"},
            {"label": "Function stub", "text": "def ${cursor}(self) -> None:\n    \"\"\"${cursor}\"\"\"\n    pass"},
            {"label": "Pytest fixture", "text": "@pytest.fixture\ndef ${cursor}():\n    yield"},
            {"label": "List comp", "text": "[${cursor} for item in ${cursor} if ${cursor}]"},
        ],
    },
    {
        "name": "Bash",
        "icon": "🔵",
        "color": "#4eaa25",
        "snippets": [
            {"label": "Find grep", "text": "find . -name '*.py' -exec grep -l '${cursor}' {} +"},
            {"label": "Curl jq", "text": "curl -s https://${cursor} | jq ."},
            {"label": "Tar compress", "text": "tar -czvf archive.tar.gz ${cursor}"},
            {"label": "SSH tunnel", "text": "ssh -L 8080:localhost:80 ${cursor}"},
            {"label": "Watch procs", "text": "watch -n 2 'ps aux | sort -nrk 3 | head -10'"},
            {"label": "For loop", "text": "for f in *.${cursor}; do\n    echo \"$f\"\ndone"},
        ],
    },
    {
        "name": "SQL",
        "icon": "🟡",
        "color": "#e38c00",
        "snippets": [
            {"label": "Select", "text": "SELECT * FROM ${cursor} WHERE 1=1 LIMIT 100;"},
            {"label": "Insert", "text": "INSERT INTO ${cursor} (col1, col2) VALUES (val1, val2);"},
            {"label": "Create table", "text": "CREATE TABLE ${cursor} (\n  id SERIAL PRIMARY KEY,\n  created_at TIMESTAMP DEFAULT NOW()\n);"},
            {"label": "Alter add col", "text": "ALTER TABLE ${cursor} ADD COLUMN ${cursor} TEXT;"},
            {"label": "Explain", "text": "EXPLAIN ANALYZE SELECT ${cursor};"},
        ],
    },
    {
        "name": "CSS",
        "icon": "🟣",
        "color": "#a259ff",
        "snippets": [
            {"label": "Flex center", "text": "display: flex;\njustify-content: center;\nalign-items: center;"},
            {"label": "Media query", "text": "@media (max-width: 768px) {\n  ${cursor}\n}"},
            {"label": "Gradient", "text": "background: linear-gradient(135deg, ${cursor}, ${cursor});"},
            {"label": "Hover scale", "text": "transition: all 0.3s ease;\n&:hover {\n  transform: scale(1.05);\n}"},
            {"label": "Sticky top", "text": "position: sticky;\ntop: 0;\nz-index: 100;"},
        ],
    },
]


# ── Template variable expansion ──────────────────────────────────────────
def expand_variables(text: str, extra_vars: Optional[Dict[str, str]] = None) -> str:
    """Expand template variables in a snippet string.

    Supported variables:
        ${date}      – Today's date (YYYY-MM-DD)
        ${time}      – Current time (HH:MM)
        ${datetime}  – Full datetime
        ${user}      – System username
        ${project}   – basename of CWD
        ${clipboard} – Current clipboard content
        ${cursor}    – Left as-is (handled by the UI/editor)

    Args:
        text: The snippet text containing ${variable} placeholders.
        extra_vars: Optional dict of additional variables.

    Returns:
        The expanded text.
    """
    now = datetime.datetime.now()
    variables = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "user": getpass.getuser(),
        "project": os.path.basename(os.getcwd()),
    }

    # Clipboard expansion (lazy import to avoid circular deps)
    try:
        import pyperclip
        variables["clipboard"] = pyperclip.paste()
    except Exception:
        variables["clipboard"] = ""

    if extra_vars:
        variables.update(extra_vars)

    result = text
    for key, value in variables.items():
        result = result.replace(f"${{{key}}}", value)

    return result


# ── Snippet Manager class ────────────────────────────────────────────────
class SnippetManager:
    """Manages snippet chambers – load, save, add, remove, reorder."""

    def __init__(self):
        self._chambers: List[Dict[str, Any]] = []
        self._current_chamber: int = 0
        self._current_snippet: int = 0
        self._frecency: Dict[str, int] = {}  # "chamber:snippet" -> use count
        self.load()

    # ── Persistence ──────────────────────────────────────────────────
    def load(self) -> None:
        """Load chambers from user file, falling back to defaults."""
        # Ensure directory exists
        os.makedirs(SNIPPETS_DIR, exist_ok=True)

        # Try user file first
        if os.path.exists(USER_CHAMBERS_FILE):
            try:
                with open(USER_CHAMBERS_FILE, "r") as f:
                    data = json.load(f)
                self._chambers = data.get("chambers", [])
                self._frecency = data.get("frecency", {})
                if self._chambers:
                    return
            except (json.JSONDecodeError, IOError, OSError):
                pass

        # Try packaged default file
        if os.path.exists(DEFAULT_CHAMBERS_FILE):
            try:
                with open(DEFAULT_CHAMBERS_FILE, "r") as f:
                    data = json.load(f)
                self._chambers = data.get("chambers", [])
                return
            except (json.JSONDecodeError, IOError, OSError):
                pass

        # Fall back to built-in chambers
        self._chambers = copy.deepcopy(BUILTIN_CHAMBERS)

    def save(self) -> None:
        """Persist current chambers and frecency to user file."""
        os.makedirs(SNIPPETS_DIR, exist_ok=True)
        data = {
            "version": "1.0",
            "chambers": self._chambers,
            "frecency": self._frecency,
        }
        try:
            with open(USER_CHAMBERS_FILE, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            print(f"Error saving snippets: {e}")

    # ── Chamber navigation ───────────────────────────────────────────
    def get_chambers(self) -> List[Dict[str, Any]]:
        """Return a copy of all chambers."""
        return copy.deepcopy(self._chambers)

    def get_chamber(self, index: int) -> Optional[Dict[str, Any]]:
        """Return a single chamber by index."""
        if 0 <= index < len(self._chambers):
            return copy.deepcopy(self._chambers[index])
        return None

    def get_chamber_count(self) -> int:
        return len(self._chambers)

    def get_current_chamber_index(self) -> int:
        return self._current_chamber

    def get_current_snippet_index(self) -> int:
        return self._current_snippet

    def spin_chamber(self, direction: int = 1) -> Dict[str, Any]:
        """Spin to next (+1) or previous (-1) chamber.

        Returns the newly selected chamber.
        """
        if not self._chambers:
            return {}
        self._current_chamber = (self._current_chamber + direction) % len(self._chambers)
        self._current_snippet = 0  # reset snippet position
        return copy.deepcopy(self._chambers[self._current_chamber])

    def rotate_snippet(self, direction: int = 1) -> Optional[Dict[str, str]]:
        """Rotate to next (+1) or previous (-1) snippet within current chamber.

        Returns the newly selected snippet dict.
        """
        if not self._chambers:
            return None
        chamber = self._chambers[self._current_chamber]
        snippets = chamber.get("snippets", [])
        if not snippets:
            return None
        self._current_snippet = (self._current_snippet + direction) % len(snippets)
        return copy.deepcopy(snippets[self._current_snippet])

    def get_current_snippet(self) -> Optional[Dict[str, str]]:
        """Return the currently selected snippet."""
        if not self._chambers:
            return None
        chamber = self._chambers[self._current_chamber]
        snippets = chamber.get("snippets", [])
        if not snippets or self._current_snippet >= len(snippets):
            return None
        return copy.deepcopy(snippets[self._current_snippet])

    def get_current_chamber(self) -> Optional[Dict[str, Any]]:
        """Return the currently selected chamber."""
        if not self._chambers:
            return None
        return copy.deepcopy(self._chambers[self._current_chamber])

    # ── Fire (paste) ─────────────────────────────────────────────────
    def fire(self, chamber_idx: Optional[int] = None,
             snippet_idx: Optional[int] = None,
             expand: bool = True) -> Optional[str]:
        """Fire (paste) a snippet.

        Args:
            chamber_idx: Chamber index. None = current.
            snippet_idx: Snippet index within chamber. None = current.
            expand: Whether to expand template variables.

        Returns:
            The expanded snippet text, or None if invalid.
        """
        ci = chamber_idx if chamber_idx is not None else self._current_chamber
        si = snippet_idx if snippet_idx is not None else self._current_snippet

        if ci < 0 or ci >= len(self._chambers):
            return None

        chamber = self._chambers[ci]
        snippets = chamber.get("snippets", [])
        if si < 0 or si >= len(snippets):
            return None

        text = snippets[si]["text"]
        if expand:
            text = expand_variables(text)

        # Record frecency
        key = f"{ci}:{si}"
        self._frecency[key] = self._frecency.get(key, 0) + 1

        # Copy to clipboard
        try:
            import pyperclip
            pyperclip.copy(text)
        except Exception:
            pass

        # Auto-save frecency periodically (every 5 uses)
        total = sum(self._frecency.values())
        if total % 5 == 0:
            self.save()

        return text

    def fire_by_label(self, label: str, expand: bool = True) -> Optional[str]:
        """Fire a snippet by searching for its label across all chambers.

        Args:
            label: The snippet label to search for (case-insensitive).

        Returns:
            The expanded text, or None if not found.
        """
        label_lower = label.lower()
        for ci, chamber in enumerate(self._chambers):
            for si, snippet in enumerate(chamber.get("snippets", [])):
                if snippet.get("label", "").lower() == label_lower:
                    return self.fire(ci, si, expand)
        return None

    # ── CRUD for chambers and snippets ───────────────────────────────
    def add_chamber(self, name: str, icon: str = "⚪",
                    color: str = "#888888",
                    snippets: Optional[List[Dict[str, str]]] = None) -> int:
        """Add a new chamber. Returns its index."""
        chamber = {
            "name": name,
            "icon": icon,
            "color": color,
            "snippets": snippets or [],
        }
        self._chambers.append(chamber)
        self.save()
        return len(self._chambers) - 1

    def remove_chamber(self, index: int) -> bool:
        """Remove a chamber by index."""
        if 0 <= index < len(self._chambers):
            self._chambers.pop(index)
            # Adjust current position
            if self._current_chamber >= len(self._chambers):
                self._current_chamber = max(0, len(self._chambers) - 1)
            self.save()
            return True
        return False

    def add_snippet(self, chamber_idx: int, label: str, text: str) -> bool:
        """Add a snippet to a chamber."""
        if 0 <= chamber_idx < len(self._chambers):
            self._chambers[chamber_idx].setdefault("snippets", []).append(
                {"label": label, "text": text}
            )
            self.save()
            return True
        return False

    def remove_snippet(self, chamber_idx: int, snippet_idx: int) -> bool:
        """Remove a snippet from a chamber."""
        if 0 <= chamber_idx < len(self._chambers):
            snippets = self._chambers[chamber_idx].get("snippets", [])
            if 0 <= snippet_idx < len(snippets):
                snippets.pop(snippet_idx)
                self.save()
                return True
        return False

    def edit_snippet(self, chamber_idx: int, snippet_idx: int,
                     label: Optional[str] = None,
                     text: Optional[str] = None) -> bool:
        """Edit a snippet's label and/or text."""
        if 0 <= chamber_idx < len(self._chambers):
            snippets = self._chambers[chamber_idx].get("snippets", [])
            if 0 <= snippet_idx < len(snippets):
                if label is not None:
                    snippets[snippet_idx]["label"] = label
                if text is not None:
                    snippets[snippet_idx]["text"] = text
                self.save()
                return True
        return False

    # ── Import / Export ──────────────────────────────────────────────
    def export_chambers(self, filepath: str,
                        indices: Optional[List[int]] = None) -> bool:
        """Export chambers to a .copyboard file.

        Args:
            filepath: Destination path.
            indices: Specific chamber indices to export. None = all.
        """
        chambers = []
        if indices:
            for i in indices:
                if 0 <= i < len(self._chambers):
                    chambers.append(self._chambers[i])
        else:
            chambers = self._chambers

        data = {
            "version": "1.0",
            "type": "copyboard_snippet_pack",
            "chambers": chambers,
        }
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except (IOError, OSError):
            return False

    def import_chambers(self, filepath: str, merge: bool = True) -> Tuple[bool, str]:
        """Import chambers from a .copyboard file.

        Args:
            filepath: Source path.
            merge: If True, add new chambers. If False, replace all.

        Returns:
            (success, message)
        """
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError, OSError) as e:
            return False, f"Failed to read file: {e}"

        if not isinstance(data, dict) or "chambers" not in data:
            return False, "Invalid snippet pack format"

        new_chambers = data["chambers"]
        if not isinstance(new_chambers, list):
            return False, "Invalid chambers data"

        if merge:
            existing_names = {c["name"] for c in self._chambers}
            added = 0
            for chamber in new_chambers:
                if chamber.get("name") not in existing_names:
                    self._chambers.append(chamber)
                    added += 1
            self.save()
            return True, f"Imported {added} new chamber(s)"
        else:
            self._chambers = new_chambers
            self._current_chamber = 0
            self._current_snippet = 0
            self.save()
            return True, f"Replaced with {len(new_chambers)} chamber(s)"

    # ── Frecency helpers ─────────────────────────────────────────────
    def get_top_snippets(self, count: int = 10) -> List[Dict[str, Any]]:
        """Return the most frequently used snippets across all chambers."""
        ranked = sorted(self._frecency.items(), key=lambda x: x[1], reverse=True)
        results = []
        for key, uses in ranked[:count]:
            try:
                ci, si = map(int, key.split(":"))
                chamber = self._chambers[ci]
                snippet = chamber["snippets"][si]
                results.append({
                    "chamber": chamber["name"],
                    "chamber_icon": chamber.get("icon", ""),
                    "label": snippet["label"],
                    "text": snippet["text"],
                    "uses": uses,
                    "chamber_idx": ci,
                    "snippet_idx": si,
                })
            except (IndexError, ValueError, KeyError):
                continue
        return results

    def reset_to_defaults(self) -> None:
        """Reset chambers to the built-in defaults."""
        self._chambers = copy.deepcopy(BUILTIN_CHAMBERS)
        self._frecency = {}
        self._current_chamber = 0
        self._current_snippet = 0
        self.save()

    # ── Search ───────────────────────────────────────────────────────
    def search(self, query: str) -> List[Dict[str, Any]]:
        """Fuzzy search across all chambers and snippets.

        Returns list of dicts with chamber/snippet info for matches.
        """
        query_lower = query.lower()
        results = []
        for ci, chamber in enumerate(self._chambers):
            for si, snippet in enumerate(chamber.get("snippets", [])):
                label = snippet.get("label", "")
                text = snippet.get("text", "")
                if query_lower in label.lower() or query_lower in text.lower():
                    results.append({
                        "chamber": chamber["name"],
                        "chamber_icon": chamber.get("icon", ""),
                        "label": label,
                        "text": text,
                        "chamber_idx": ci,
                        "snippet_idx": si,
                    })
        return results


# ── Module-level singleton ───────────────────────────────────────────────
snippets = SnippetManager()
