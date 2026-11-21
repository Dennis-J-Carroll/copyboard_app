#!/usr/bin/env python3
"""Chrome extension ID helpers for the install scripts.

An unpacked extension keeps a stable ID only when its manifest pins a "key".
Hard-coding that ID in an installer drifts as soon as the key changes, and
Chrome then refuses every native message from the extension.
"""

import base64
import hashlib
import json
import os


def chrome_extension_id_from_key(key: str) -> str:
    """Derive the Chrome extension ID from a manifest's base64 public key."""
    digest = hashlib.sha256(base64.b64decode(key)).hexdigest()[:32]
    return "".join(chr(ord("a") + int(nibble, 16)) for nibble in digest)


def extension_manifest_path(project_root: str) -> str:
    """Return the unpacked extension manifest that pins the ID."""
    candidates = [
        os.path.join(project_root, "browser_extension", "manifest.json"),
        os.path.join(project_root, "copyboard_extension", "browser_extension", "manifest.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("No browser_extension/manifest.json under %s" % project_root)


def chrome_extension_id_from_manifest(project_root: str) -> str:
    """Read the extension key and derive the ID the browser will assign."""
    path = extension_manifest_path(project_root)
    with open(path, encoding="utf-8") as handle:
        key = json.load(handle).get("key")
    if not key:
        raise ValueError("%s has no key, so its extension ID is not stable" % path)
    return chrome_extension_id_from_key(key)


def chrome_extension_origin(project_root: str) -> str:
    """Return the allowed_origins entry for the unpacked extension."""
    return "chrome-extension://%s/" % chrome_extension_id_from_manifest(project_root)
