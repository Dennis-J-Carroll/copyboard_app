"""Regression checks for the browser extension.

The extension is shipped twice (the standalone ``browser_extension`` folder
and the copy under ``copyboard_extension``), so these tests also keep the two
copies byte-identical.
"""
import base64
import filecmp
import hashlib
import importlib.util
import json
import os
import re
import struct
import subprocess
import sys

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


def load_script_module(name: str, filename: str):
    path = os.path.join(PROJECT_ROOT, "scripts", filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_extension_id() -> str:
    manifest = json.loads(read_extension("manifest.json"))
    digest = hashlib.sha256(base64.b64decode(manifest["key"])).hexdigest()[:32]
    return "".join(chr(ord("a") + int(nibble, 16)) for nibble in digest)


def test_installers_derive_the_extension_id_from_the_manifest_key():
    module = load_script_module("extension_id", "extension_id.py")
    assert module.chrome_extension_id_from_manifest(PROJECT_ROOT) == expected_extension_id()


def test_system_wide_installer_allows_the_derived_origin():
    module = load_script_module("install_system_wide", "install_system_wide.py")
    manifest = module.build_native_host_manifest("/tmp/copyboard-native-host")
    assert manifest["allowed_origins"] == ["chrome-extension://%s/" % expected_extension_id()]


def test_install_paths_do_not_hard_code_an_extension_id():
    hard_coded = re.compile(r"chrome-extension://[a-p]{32}")
    for relative in (
        "config/chrome_manifest.json",
        "scripts/fix_extension.py",
        "scripts/install_system_wide.py",
    ):
        with open(os.path.join(PROJECT_ROOT, relative), encoding="utf-8") as handle:
            assert hard_coded.search(handle.read()) is None, relative


def test_native_host_runs_as_a_script(tmp_path):
    # Chrome launches the host file itself, so it has no package context and
    # must still import copyboard_extension.core.
    config_dir = tmp_path / ".config" / "copyboard"
    config_dir.mkdir(parents=True)
    board = ["alpha item", "beta item"]
    (config_dir / "board.json").write_text(json.dumps(board), encoding="utf-8")

    message = json.dumps({"action": "list"}).encode("utf-8")
    env = dict(os.environ, HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "copyboard_extension", "native_messaging_host.py")],
        input=struct.pack("@I", len(message)) + message,
        capture_output=True,
        env=env,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    length = struct.unpack("@I", result.stdout[:4])[0]
    assert json.loads(result.stdout[4:4 + length]) == {"success": True, "items": board}


def test_chamber_labels_are_one_based_everywhere():
    for name in ("background.js", "content.js", "popup.js"):
        assert "padStart(2, '0')" in read_extension(name), name
    assert "number === 0 ? 9 : number - 1" in read_extension("content.js")
