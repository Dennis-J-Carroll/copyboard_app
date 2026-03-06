"""
Tests for the Snippet Manager (Code Revolver engine).
"""
import os
import json
import pytest
import tempfile

from copyboard_extension.snippet_manager import (
    SnippetManager,
    expand_variables,
    BUILTIN_CHAMBERS,
)


@pytest.fixture()
def fresh_snippets(tmp_path, monkeypatch):
    """Provide a SnippetManager that reads/writes to a temporary directory."""
    snippets_dir = str(tmp_path / "snippets")
    os.makedirs(snippets_dir, exist_ok=True)

    import copyboard_extension.snippet_manager as sm
    monkeypatch.setattr(sm, "SNIPPETS_DIR", snippets_dir)
    monkeypatch.setattr(sm, "USER_CHAMBERS_FILE", os.path.join(snippets_dir, "user_chambers.json"))

    mgr = SnippetManager()
    return mgr


# ── Defaults & Loading ───────────────────────────────────────────────────
class TestDefaults:
    def test_loads_builtin_chambers(self, fresh_snippets):
        """When no user file exists, builtin chambers are loaded."""
        assert fresh_snippets.get_chamber_count() == len(BUILTIN_CHAMBERS)

    def test_chamber_names(self, fresh_snippets):
        names = [c["name"] for c in fresh_snippets.get_chambers()]
        assert "Git" in names
        assert "Docker" in names
        assert "Python" in names

    def test_each_chamber_has_snippets(self, fresh_snippets):
        for ch in fresh_snippets.get_chambers():
            assert len(ch["snippets"]) > 0


# ── Navigation (spin/rotate) ────────────────────────────────────────────
class TestNavigation:
    def test_spin_forward(self, fresh_snippets):
        ch = fresh_snippets.spin_chamber(1)
        assert ch["name"] != BUILTIN_CHAMBERS[0]["name"]
        assert fresh_snippets.get_current_chamber_index() == 1

    def test_spin_wraps_around(self, fresh_snippets):
        n = fresh_snippets.get_chamber_count()
        for _ in range(n):
            fresh_snippets.spin_chamber(1)
        assert fresh_snippets.get_current_chamber_index() == 0

    def test_spin_backward(self, fresh_snippets):
        fresh_snippets.spin_chamber(-1)
        assert fresh_snippets.get_current_chamber_index() == fresh_snippets.get_chamber_count() - 1

    def test_rotate_forward(self, fresh_snippets):
        snip = fresh_snippets.rotate_snippet(1)
        assert snip is not None
        assert fresh_snippets.get_current_snippet_index() == 1

    def test_rotate_wraps(self, fresh_snippets):
        ch = fresh_snippets.get_current_chamber()
        n = len(ch["snippets"])
        for _ in range(n):
            fresh_snippets.rotate_snippet(1)
        assert fresh_snippets.get_current_snippet_index() == 0

    def test_spin_resets_snippet_index(self, fresh_snippets):
        fresh_snippets.rotate_snippet(1)
        fresh_snippets.rotate_snippet(1)
        assert fresh_snippets.get_current_snippet_index() == 2
        fresh_snippets.spin_chamber(1)
        assert fresh_snippets.get_current_snippet_index() == 0


# ── Firing ───────────────────────────────────────────────────────────────
class TestFire:
    def test_fire_returns_text(self, fresh_snippets, mock_clipboard):
        text = fresh_snippets.fire(0, 0, expand=False)
        assert text is not None
        assert len(text) > 0

    def test_fire_copies_to_clipboard(self, fresh_snippets, mock_clipboard):
        text = fresh_snippets.fire(0, 0, expand=False)
        assert mock_clipboard["content"] == text

    def test_fire_invalid_chamber(self, fresh_snippets):
        assert fresh_snippets.fire(99, 0) is None

    def test_fire_invalid_snippet(self, fresh_snippets):
        assert fresh_snippets.fire(0, 99) is None

    def test_fire_by_label(self, fresh_snippets, mock_clipboard):
        text = fresh_snippets.fire_by_label("Commit all", expand=False)
        assert text is not None
        assert "git" in text.lower()

    def test_fire_by_label_case_insensitive(self, fresh_snippets, mock_clipboard):
        text = fresh_snippets.fire_by_label("commit ALL", expand=False)
        assert text is not None

    def test_fire_by_label_not_found(self, fresh_snippets):
        assert fresh_snippets.fire_by_label("nonexistent") is None


# ── Template Expansion ───────────────────────────────────────────────────
class TestExpansion:
    def test_date_expanded(self):
        result = expand_variables("today is ${date}")
        assert "${date}" not in result
        assert len(result) > len("today is ")

    def test_user_expanded(self):
        result = expand_variables("hi ${user}")
        assert "${user}" not in result

    def test_project_expanded(self):
        result = expand_variables("project: ${project}")
        assert "${project}" not in result

    def test_cursor_not_expanded(self):
        """${cursor} should remain as-is (handled by UI/editor)."""
        result = expand_variables("def ${cursor}():")
        assert "${cursor}" in result

    def test_extra_vars(self):
        result = expand_variables("hello ${custom}", {"custom": "world"})
        assert result == "hello world"


# ── CRUD ─────────────────────────────────────────────────────────────────
class TestCRUD:
    def test_add_chamber(self, fresh_snippets):
        idx = fresh_snippets.add_chamber("MyLang", icon="🆕")
        assert idx == fresh_snippets.get_chamber_count() - 1
        ch = fresh_snippets.get_chamber(idx)
        assert ch["name"] == "MyLang"
        assert ch["icon"] == "🆕"

    def test_remove_chamber(self, fresh_snippets):
        original_count = fresh_snippets.get_chamber_count()
        fresh_snippets.remove_chamber(0)
        assert fresh_snippets.get_chamber_count() == original_count - 1

    def test_remove_invalid_chamber(self, fresh_snippets):
        assert fresh_snippets.remove_chamber(99) is False

    def test_add_snippet(self, fresh_snippets):
        original = len(fresh_snippets.get_chamber(0)["snippets"])
        assert fresh_snippets.add_snippet(0, "New one", "echo hello") is True
        assert len(fresh_snippets.get_chamber(0)["snippets"]) == original + 1

    def test_remove_snippet(self, fresh_snippets):
        original = len(fresh_snippets.get_chamber(0)["snippets"])
        assert fresh_snippets.remove_snippet(0, 0) is True
        assert len(fresh_snippets.get_chamber(0)["snippets"]) == original - 1

    def test_edit_snippet(self, fresh_snippets):
        assert fresh_snippets.edit_snippet(0, 0, label="Renamed") is True
        assert fresh_snippets.get_chamber(0)["snippets"][0]["label"] == "Renamed"

    def test_edit_snippet_text(self, fresh_snippets):
        assert fresh_snippets.edit_snippet(0, 0, text="new text") is True
        assert fresh_snippets.get_chamber(0)["snippets"][0]["text"] == "new text"


# ── Persistence ──────────────────────────────────────────────────────────
class TestPersistence:
    def test_save_and_reload(self, fresh_snippets, tmp_path, monkeypatch):
        fresh_snippets.add_chamber("Saved", icon="💾")
        fresh_snippets.save()

        # Create a new manager that reads from the same dir
        import copyboard_extension.snippet_manager as sm
        mgr2 = SnippetManager()
        names = [c["name"] for c in mgr2.get_chambers()]
        assert "Saved" in names

    def test_corrupt_user_file_falls_back(self, fresh_snippets, monkeypatch):
        import copyboard_extension.snippet_manager as sm
        with open(sm.USER_CHAMBERS_FILE, "w") as f:
            f.write("NOT JSON AT ALL")
        mgr = SnippetManager()
        assert mgr.get_chamber_count() > 0  # fell back to defaults


# ── Import / Export ──────────────────────────────────────────────────────
class TestImportExport:
    def test_export_creates_file(self, fresh_snippets, tmp_path):
        out = str(tmp_path / "export.copyboard")
        assert fresh_snippets.export_chambers(out) is True
        assert os.path.exists(out)

    def test_export_is_valid_json(self, fresh_snippets, tmp_path):
        out = str(tmp_path / "export.copyboard")
        fresh_snippets.export_chambers(out)
        with open(out) as f:
            data = json.load(f)
        assert "chambers" in data
        assert data["type"] == "copyboard_snippet_pack"

    def test_import_merge(self, fresh_snippets, tmp_path):
        # Export, add a new chamber, export again, then import merge
        pack = str(tmp_path / "pack.copyboard")
        data = {
            "version": "1.0",
            "type": "copyboard_snippet_pack",
            "chambers": [{"name": "NewLang", "icon": "🆕", "color": "#fff", "snippets": []}],
        }
        with open(pack, "w") as f:
            json.dump(data, f)

        success, msg = fresh_snippets.import_chambers(pack, merge=True)
        assert success
        names = [c["name"] for c in fresh_snippets.get_chambers()]
        assert "NewLang" in names

    def test_import_replace(self, fresh_snippets, tmp_path):
        pack = str(tmp_path / "pack.copyboard")
        data = {
            "version": "1.0",
            "type": "copyboard_snippet_pack",
            "chambers": [{"name": "Only", "icon": "1️⃣", "color": "#000", "snippets": []}],
        }
        with open(pack, "w") as f:
            json.dump(data, f)

        success, msg = fresh_snippets.import_chambers(pack, merge=False)
        assert success
        assert fresh_snippets.get_chamber_count() == 1
        assert fresh_snippets.get_chambers()[0]["name"] == "Only"

    def test_import_invalid_file(self, fresh_snippets, tmp_path):
        bad = str(tmp_path / "bad.copyboard")
        with open(bad, "w") as f:
            f.write("garbage")
        success, msg = fresh_snippets.import_chambers(bad)
        assert not success


# ── Search ───────────────────────────────────────────────────────────────
class TestSearch:
    def test_search_by_label(self, fresh_snippets):
        results = fresh_snippets.search("commit")
        assert len(results) > 0
        assert any("commit" in r["label"].lower() for r in results)

    def test_search_by_text(self, fresh_snippets):
        results = fresh_snippets.search("docker compose")
        assert len(results) > 0

    def test_search_no_results(self, fresh_snippets):
        results = fresh_snippets.search("xyzzy_nonexistent_12345")
        assert len(results) == 0


# ── Frecency ─────────────────────────────────────────────────────────────
class TestFrecency:
    def test_fire_increments_count(self, fresh_snippets, mock_clipboard):
        fresh_snippets.fire(0, 0, expand=False)
        fresh_snippets.fire(0, 0, expand=False)
        top = fresh_snippets.get_top_snippets(1)
        assert len(top) > 0
        assert top[0]["uses"] >= 2

    def test_top_snippets_empty_initially(self, fresh_snippets):
        assert fresh_snippets.get_top_snippets() == []


# ── Reset ────────────────────────────────────────────────────────────────
class TestReset:
    def test_reset_restores_defaults(self, fresh_snippets):
        fresh_snippets.add_chamber("Custom")
        fresh_snippets.reset_to_defaults()
        names = [c["name"] for c in fresh_snippets.get_chambers()]
        assert "Custom" not in names
        assert "Git" in names

    def test_reset_clears_frecency(self, fresh_snippets, mock_clipboard):
        fresh_snippets.fire(0, 0, expand=False)
        fresh_snippets.reset_to_defaults()
        assert fresh_snippets.get_top_snippets() == []
