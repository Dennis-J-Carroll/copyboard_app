"""Release metadata should stay synchronized across packaging surfaces."""

import ast
from pathlib import Path
import re

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9 and 3.10
    import tomli as tomllib

from copyboard_extension import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _setup_version(path: Path) -> str:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "setup":
            for keyword in node.keywords:
                if keyword.arg == "version":
                    return ast.literal_eval(keyword.value)
    raise AssertionError(f"No setup(version=...) found in {path}")


def test_release_versions_are_synchronized():
    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    version = metadata["project"]["version"]

    assert version == "0.5.0"
    assert __version__ == version
    assert _setup_version(PROJECT_ROOT / "setup.py") == version
    assert _setup_version(PROJECT_ROOT / "copyboard_extension" / "setup.py") == version
    assert f"Version {version}" in (PROJECT_ROOT / "CHANGELOG.md").read_text()


def test_linux_desktop_entry_is_portable():
    desktop = (PROJECT_ROOT / "packaging/linux/copyboard.desktop").read_text()

    assert "Exec=copyboard-gui" in desktop
    assert "Icon=copyboard" in desktop
    assert str(PROJECT_ROOT) not in desktop
    assert not re.search(r"/home/[^/]+/", desktop)


def test_distribution_license_exists():
    license_text = (PROJECT_ROOT / "LICENSE").read_text()

    assert license_text.startswith("MIT License")
    assert "Dennis J. Carroll" in license_text
