# Contributing to CopyBoard

CopyBoard is an early desktop tool. Reports from actual copy and paste workflows
are useful, especially when a gesture, focus handoff, or shortcut breaks.

## Report a problem

Open an [issue](https://github.com/Dennis-J-Carroll/copyboard_app/issues/new/choose)
with:

- OS and desktop session (X11 or Wayland)
- Installation method and CopyBoard commit or version
- Steps to reproduce, expected result, and actual result
- Whether **Copy only** works when automatic paste fails
- Relevant error output, with copied text and personal paths removed

For design feedback, say where the widget sits, which mode you use, and what
slows your hand down. A short recording or sequence of screenshots helps.

## Work on the code

Use Python 3.9 or newer. On Ubuntu or Pop!_OS, install the X11 dependencies
listed in the [README](README.md#try-it), then:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
```

GUI tests need a display. In a headless Linux session, use `xvfb-run -a pytest -q`.
For a widget change, describe the copy → aim → paste → focus cycle you tested.
Keep changes scoped and update controls in [the user guide](docs/USER_GUIDE.md)
when behavior changes.

## Pull requests

Explain the user problem, the change, and how you verified it. Include a
screenshot or short recording for visible widget changes. Never include real
clipboard content, account names, or browser tabs in public demo media.
