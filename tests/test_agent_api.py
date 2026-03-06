"""
Tests for the Agent API, Profile Generator, and Context Generator.
"""
import os
import json
import pytest
import datetime

from copyboard_extension.agent_api import (
    get_profile,
    fire_snippet,
    fire_by_label,
    search_snippets,
    get_chambers,
    get_top_snippets,
    add_snippet,
    add_chamber,
    remove_snippet,
    get_board,
    add_to_board,
    describe,
)
from copyboard_extension.profile_generator import (
    generate_profile,
    profile_to_markdown,
)
from copyboard_extension.context_generator import generate_context_file
from copyboard_extension.snippet_manager import SnippetManager


@pytest.fixture()
def agent_snippets(tmp_path, monkeypatch):
    """Provide an isolated SnippetManager for agent API tests."""
    snippets_dir = str(tmp_path / "snippets")
    os.makedirs(snippets_dir, exist_ok=True)

    import copyboard_extension.snippet_manager as sm
    monkeypatch.setattr(sm, "SNIPPETS_DIR", snippets_dir)
    monkeypatch.setattr(sm, "USER_CHAMBERS_FILE", os.path.join(snippets_dir, "user.json"))

    mgr = SnippetManager()
    # Patch the module-level singleton used by agent_api
    monkeypatch.setattr(sm, "snippets", mgr)
    return mgr


# ── Agent API Tests ──────────────────────────────────────────────────────
class TestAgentAPI:
    def test_describe(self, agent_snippets):
        desc = describe()
        assert desc["name"] == "Copyboard"
        assert "capabilities" in desc
        assert desc["chamber_count"] > 0

    def test_get_chambers(self, agent_snippets):
        chambers = get_chambers()
        assert isinstance(chambers, list)
        assert len(chambers) > 0
        assert "name" in chambers[0]
        assert "snippets" in chambers[0]

    def test_fire_snippet_success(self, agent_snippets, mock_clipboard):
        result = fire_snippet(0, 0, expand=False)
        assert result["ok"] is True
        assert "text" in result
        assert "label" in result
        assert "chamber" in result

    def test_fire_snippet_invalid(self, agent_snippets):
        result = fire_snippet(99, 0)
        assert result["ok"] is False
        assert "error" in result

    def test_fire_by_label(self, agent_snippets, mock_clipboard):
        result = fire_by_label("Commit all", expand=False)
        assert result["ok"] is True
        assert "git" in result["text"].lower()

    def test_fire_by_label_not_found(self, agent_snippets):
        result = fire_by_label("nonexistent_label_xyz")
        assert result["ok"] is False

    def test_search_snippets(self, agent_snippets):
        results = search_snippets("docker")
        assert isinstance(results, list)
        assert len(results) > 0
        assert all("chamber" in r for r in results)

    def test_search_no_results(self, agent_snippets):
        results = search_snippets("xyzzy_nonexistent_12345")
        assert results == []

    def test_add_snippet_success(self, agent_snippets):
        result = add_snippet(0, "Test snippet", "echo test")
        assert result["ok"] is True

    def test_add_snippet_invalid_chamber(self, agent_snippets):
        result = add_snippet(99, "Bad", "text")
        assert result["ok"] is False

    def test_add_chamber(self, agent_snippets):
        result = add_chamber("NewChamber", icon="🆕")
        assert result["ok"] is True
        assert "index" in result

    def test_remove_snippet(self, agent_snippets):
        result = remove_snippet(0, 0)
        assert result["ok"] is True

    def test_get_board(self, agent_snippets, isolated_board):
        board = get_board()
        assert "items" in board
        assert "count" in board
        assert isinstance(board["items"], list)

    def test_add_to_board(self, agent_snippets, isolated_board, mock_clipboard):
        result = add_to_board("test text")
        assert result["ok"] is True
        assert result["position"] == 0

    def test_get_top_snippets_returns_list(self, agent_snippets):
        top = get_top_snippets()
        assert isinstance(top, list)


# ── Profile Generator Tests ──────────────────────────────────────────────
class TestProfileGenerator:
    def test_profile_structure(self, agent_snippets):
        profile = generate_profile(agent_snippets)
        assert profile["version"] == "1.0"
        assert profile["enabled"] is True
        assert "preferences" in profile
        assert "usage_summary" in profile
        assert "available_snippets" in profile

    def test_profile_has_generated_at(self, agent_snippets):
        profile = generate_profile(agent_snippets)
        assert "generated_at" in profile
        # Should be a valid ISO datetime
        datetime.datetime.fromisoformat(profile["generated_at"])

    def test_profile_available_snippets_populated(self, agent_snippets):
        profile = generate_profile(agent_snippets)
        avail = profile["available_snippets"]
        assert len(avail) > 0
        assert "chamber" in avail[0]
        assert "label" in avail[0]

    def test_profile_infers_code_style(self, agent_snippets):
        profile = generate_profile(agent_snippets)
        style = profile["preferences"].get("code_style", {})
        # Default chambers include Python snippets with type hints
        assert style.get("type_hints") is True

    def test_profile_infers_deployment(self, agent_snippets):
        profile = generate_profile(agent_snippets)
        prefs = profile["preferences"]
        assert prefs.get("deployment") == "docker-compose"

    def test_profile_infers_pytest(self, agent_snippets):
        profile = generate_profile(agent_snippets)
        prefs = profile["preferences"]
        assert prefs.get("testing_framework") == "pytest"

    def test_profile_with_frecency(self, agent_snippets, mock_clipboard):
        # Fire some snippets to build frecency
        agent_snippets.fire(0, 0, expand=False)
        agent_snippets.fire(0, 0, expand=False)
        agent_snippets.fire(2, 0, expand=False)

        profile = generate_profile(agent_snippets)
        assert profile["usage_summary"]["total_fires"] == 3
        assert len(profile.get("active_chambers", [])) > 0

    def test_profile_opt_out(self, agent_snippets, monkeypatch):
        """When profile_enabled is False, generate_profile returns disabled."""
        from unittest.mock import MagicMock
        mock_config = MagicMock()
        mock_config.get.return_value = False

        profile = generate_profile(agent_snippets, mock_config)
        assert profile["enabled"] is False

    def test_to_markdown(self, agent_snippets):
        profile = generate_profile(agent_snippets)
        md = profile_to_markdown(profile)
        assert isinstance(md, str)
        assert "# Copyboard Agent Profile" in md
        assert "Available Snippets" in md

    def test_to_markdown_disabled(self):
        md = profile_to_markdown({"enabled": False})
        assert "disabled" in md.lower()


# ── Agent API get_profile ────────────────────────────────────────────────
class TestGetProfile:
    def test_json_format(self, agent_snippets):
        profile = get_profile(as_markdown=False)
        assert isinstance(profile, dict)
        assert "version" in profile

    def test_markdown_format(self, agent_snippets):
        md = get_profile(as_markdown=True)
        assert isinstance(md, str)
        assert "# Copyboard Agent Profile" in md

    def test_json_is_serializable(self, agent_snippets):
        profile = get_profile(as_markdown=False)
        # Must be JSON-serializable
        s = json.dumps(profile)
        assert len(s) > 0


# ── Context Generator Tests ─────────────────────────────────────────────
class TestContextGenerator:
    def test_generates_file(self, agent_snippets, tmp_path):
        filepath = generate_context_file(
            output_dir=str(tmp_path),
            snippets_mgr=agent_snippets,
        )
        assert filepath != ""
        assert os.path.exists(filepath)

    def test_file_is_markdown(self, agent_snippets, tmp_path):
        filepath = generate_context_file(
            output_dir=str(tmp_path),
            snippets_mgr=agent_snippets,
        )
        with open(filepath) as f:
            content = f.read()
        assert "# Copyboard Agent Profile" in content
        assert "copyboard snippet fire" in content

    def test_file_has_mcp_config(self, agent_snippets, tmp_path):
        filepath = generate_context_file(
            output_dir=str(tmp_path),
            snippets_mgr=agent_snippets,
        )
        with open(filepath) as f:
            content = f.read()
        assert "mcp_server" in content

    def test_default_filename(self, agent_snippets, tmp_path):
        filepath = generate_context_file(
            output_dir=str(tmp_path),
            snippets_mgr=agent_snippets,
        )
        assert filepath.endswith(".copyboard-context.md")

    def test_disabled_returns_empty(self, agent_snippets, tmp_path):
        from unittest.mock import MagicMock
        mock_config = MagicMock()
        mock_config.get.return_value = False

        filepath = generate_context_file(
            output_dir=str(tmp_path),
            snippets_mgr=agent_snippets,
            config_mgr=mock_config,
        )
        assert filepath == ""
