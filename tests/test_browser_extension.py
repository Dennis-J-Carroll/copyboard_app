"""Regression checks for the browser extension.

The extension is shipped twice (the standalone ``browser_extension`` folder
and the copy under ``copyboard_extension``), so these tests also keep the two
copies byte-identical.
"""
import filecmp
import json
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTENSION_DIR = os.path.join(PROJECT_ROOT, "browser_extension")
PACKAGED_DIR = os.path.join(PROJECT_ROOT, "copyboard_extension", "browser_extension")


def read_extension(name: str) -> str:
    with open(os.path.join(EXTENSION_DIR, name), encoding="utf-8") as handle:
        return handle.read()


def test_both_extension_copies_are_identical():
    for name in ("background.js", "content.js", "popup.js", "popup.html", "manifest.json"):
        assert filecmp.cmp(
            os.path.join(EXTENSION_DIR, name),
            os.path.join(PACKAGED_DIR, name),
            shallow=False,
        ), f"{name} differs between the two extension folders"


def test_manifest_is_an_mv3_service_worker():
    manifest = json.loads(read_extension("manifest.json"))
    assert manifest["manifest_version"] == 3
    assert manifest["background"]["service_worker"] == "background.js"


def test_service_worker_never_calls_alert():
    # alert() is undefined in an MV3 service worker; a top-level call aborts
    # listener registration before the extension can do anything.
    assert "alert(" not in read_extension("background.js")


def test_paste_refresh_does_not_wipe_the_whole_menu_tree():
    source = read_extension("background.js")
    assert source.count("contextMenus.removeAll") == 1
    assert 'contextMenus.remove("copyboard-paste"' in source
    menu_click_handler = source.split("chrome.contextMenus.onClicked", 1)[1]
    assert "contextMenus.removeAll" not in menu_click_handler


def test_chamber_labels_are_one_based_everywhere():
    for name in ("background.js", "content.js", "popup.js"):
        assert "padStart(2, '0')" in read_extension(name), name
    assert "number === 0 ? 9 : number - 1" in read_extension("content.js")
