"""
Profile Generator – Creates a data-driven "coding fingerprint" from
the user's Copyboard usage patterns.

This profile tells AI agents HOW the user codes without the user
needing to write any rules manually.
"""

import datetime
import json
import re
from typing import Dict, Any, List, Optional
from collections import Counter


def generate_profile(snippets_mgr, config_mgr=None) -> Dict[str, Any]:
    """Generate a coding profile from Copyboard usage data.

    Args:
        snippets_mgr: A SnippetManager instance.
        config_mgr:   A ConfigManager instance (optional).

    Returns:
        A structured dict describing the user's coding patterns.
    """
    # Check opt-out
    if config_mgr:
        enabled = config_mgr.get("agent", "profile_enabled", True)
        if not enabled:
            return {"enabled": False, "reason": "Profile generation disabled by user."}

    chambers = snippets_mgr.get_chambers()
    top = snippets_mgr.get_top_snippets(50)
    frecency = getattr(snippets_mgr, "_frecency", {})

    profile: Dict[str, Any] = {
        "version": "1.0",
        "generated_at": datetime.datetime.now().isoformat(),
        "enabled": True,
    }

    # ── Language / Tool preferences ──────────────────────────────────
    profile["preferences"] = _infer_preferences(chambers, top, frecency)

    # ── Top snippets ─────────────────────────────────────────────────
    profile["top_snippets"] = [
        {
            "chamber": t["chamber"],
            "label": t["label"],
            "uses": t["uses"],
        }
        for t in top[:10]
    ]

    # ── Active chambers ──────────────────────────────────────────────
    chamber_uses = Counter()
    for key, count in frecency.items():
        try:
            ci = int(key.split(":")[0])
            if ci < len(chambers):
                chamber_uses[chambers[ci]["name"]] += count
        except (ValueError, IndexError):
            pass

    ranked = chamber_uses.most_common()
    profile["active_chambers"] = [
        {"name": name, "fires": fires} for name, fires in ranked
    ]

    # ── Usage summary ────────────────────────────────────────────────
    total_fires = sum(frecency.values()) if frecency else 0
    profile["usage_summary"] = {
        "total_fires": total_fires,
        "total_chambers": len(chambers),
        "total_snippets": sum(len(c.get("snippets", [])) for c in chambers),
        "custom_chambers": sum(
            1 for c in chambers
            if c["name"] not in {"Git", "Docker", "Python", "Bash", "SQL", "CSS"}
        ),
    }

    # ── Available snippets (for agent tool use) ──────────────────────
    profile["available_snippets"] = []
    for ci, ch in enumerate(chambers):
        for si, snip in enumerate(ch.get("snippets", [])):
            profile["available_snippets"].append({
                "chamber": ch["name"],
                "chamber_idx": ci,
                "snippet_idx": si,
                "label": snip.get("label", ""),
                "text_preview": snip["text"][:80],
            })

    return profile


def _infer_preferences(chambers, top, frecency) -> Dict[str, Any]:
    """Infer coding preferences from usage data."""
    prefs: Dict[str, Any] = {}

    # ── Primary languages (from chamber usage) ───────────────────────
    chamber_fires: Counter = Counter()
    for key, count in frecency.items():
        try:
            ci = int(key.split(":")[0])
            if ci < len(chambers):
                chamber_fires[chambers[ci]["name"]] += count
        except (ValueError, IndexError):
            pass

    if chamber_fires:
        total = sum(chamber_fires.values())
        prefs["primary_tools"] = [
            {"name": name, "percentage": round(fires / total * 100)}
            for name, fires in chamber_fires.most_common(5)
        ]

    # ── Code style signals from snippet text ─────────────────────────
    all_texts = []
    for ch in chambers:
        for snip in ch.get("snippets", []):
            all_texts.append(snip.get("text", ""))
    combined = "\n".join(all_texts)

    style = {}
    style["type_hints"] = "-> " in combined or ": str" in combined or ": int" in combined
    style["docstrings"] = '"""' in combined or "'''" in combined
    style["f_strings"] = "f'" in combined or 'f"' in combined
    style["pytest"] = "pytest" in combined.lower() or "@pytest" in combined
    style["logging"] = "logger." in combined or "logging." in combined
    style["async"] = "async def" in combined or "await " in combined
    prefs["code_style"] = {k: v for k, v in style.items() if v}

    # ── VCS workflow ─────────────────────────────────────────────────
    if any("rebase" in t.get("label", "").lower() or "rebase" in t.get("text", "").lower()
           for ch in chambers for t in ch.get("snippets", []) if isinstance(t, dict)):
        prefs["vcs_workflow"] = "git-rebase"
    elif any("merge" in t.get("text", "").lower()
             for ch in chambers for t in ch.get("snippets", []) if isinstance(t, dict)):
        prefs["vcs_workflow"] = "git-merge"

    # ── Deployment ───────────────────────────────────────────────────
    if any("docker" in ch.get("name", "").lower() for ch in chambers):
        prefs["deployment"] = "docker"
    if any("compose" in t.get("text", "").lower()
           for ch in chambers for t in ch.get("snippets", []) if isinstance(t, dict)):
        prefs["deployment"] = "docker-compose"

    # ── Testing ──────────────────────────────────────────────────────
    if style.get("pytest"):
        prefs["testing_framework"] = "pytest"

    return prefs


def profile_to_markdown(profile: Dict[str, Any]) -> str:
    """Convert a profile dict to a readable markdown document.

    This is used for .copyboard-context.md and the `copyboard profile` CLI.
    """
    if not profile.get("enabled", True):
        return "# Copyboard Agent Profile\n\n> Profile generation is disabled.\n"

    lines = [
        "# Copyboard Agent Profile",
        "",
        f"> Auto-generated on {profile.get('generated_at', 'unknown')}",
        "> This file helps AI coding agents understand your coding patterns.",
        "> It is derived from your Copyboard snippet usage data.",
        "",
    ]

    # Preferences
    prefs = profile.get("preferences", {})
    if prefs:
        lines.append("## Coding Preferences")
        lines.append("")

        tools = prefs.get("primary_tools", [])
        if tools:
            lines.append("**Primary tools/languages** (by snippet usage):")
            for t in tools:
                lines.append(f"- {t['name']} ({t['percentage']}%)")
            lines.append("")

        style = prefs.get("code_style", {})
        if style:
            lines.append("**Code style signals:**")
            style_labels = {
                "type_hints": "Uses type hints",
                "docstrings": "Uses docstrings",
                "f_strings": "Uses f-strings",
                "pytest": "Uses pytest",
                "logging": "Uses structured logging",
                "async": "Uses async/await",
            }
            for key in style:
                lines.append(f"- {style_labels.get(key, key)}")
            lines.append("")

        if prefs.get("vcs_workflow"):
            lines.append(f"**Version control**: {prefs['vcs_workflow']}")
        if prefs.get("deployment"):
            lines.append(f"**Deployment**: {prefs['deployment']}")
        if prefs.get("testing_framework"):
            lines.append(f"**Testing**: {prefs['testing_framework']}")
        lines.append("")

    # Top snippets
    top = profile.get("top_snippets", [])
    if top:
        lines.append("## Most-Used Snippets")
        lines.append("")
        for i, s in enumerate(top[:5], 1):
            lines.append(f"{i}. **{s['chamber']}/{s['label']}** ({s['uses']} uses)")
        lines.append("")

    # Available snippets for agent
    avail = profile.get("available_snippets", [])
    if avail:
        lines.append("## Available Snippets")
        lines.append("")
        lines.append("Agents can fire these via `copyboard snippet fire <chamber> <snippet>`:")
        lines.append("")
        current_ch = None
        for s in avail:
            if s["chamber"] != current_ch:
                current_ch = s["chamber"]
                lines.append(f"\n### {current_ch}")
            preview = s["text_preview"].replace("\n", " ↵ ")
            lines.append(f"- `[{s['chamber_idx']}:{s['snippet_idx']}]` **{s['label']}**: `{preview}`")
        lines.append("")

    # Usage summary
    usage = profile.get("usage_summary", {})
    if usage:
        lines.append("## Usage Summary")
        lines.append("")
        lines.append(f"- Total snippet fires: {usage.get('total_fires', 0)}")
        lines.append(f"- Chambers: {usage.get('total_chambers', 0)} ({usage.get('custom_chambers', 0)} custom)")
        lines.append(f"- Total snippets: {usage.get('total_snippets', 0)}")
        lines.append("")

    return "\n".join(lines)
