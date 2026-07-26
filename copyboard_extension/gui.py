"""Compatibility entry point for the revolver-first CopyBoard desktop app."""

from .copyboard_gui import CopyboardGUI, main


def run_gui():
    """Launch the primary CopyBoard interface."""
    main()


if __name__ == "__main__":
    run_gui()
