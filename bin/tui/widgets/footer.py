# @TASK T7.2 - FooterWidget 구현
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t72-공통-위젯-구현-redgreen
# @TEST tests/tui/test_widgets.py::TestFooterWidget
"""
Footer widget for DeepInvirus TUI.

Displays keyboard shortcut hints at the bottom of every screen.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class FooterWidget(Widget):
    """Application footer showing keyboard shortcut hints.

    Shortcuts displayed:
        [r] Run  [d] Database  [h] Host  [c] Config  [i] History  [q] Quit

    Attributes:
        SHORTCUT_KEYS: Ordered list of (key, label) pairs shown in the footer.
    """

    SHORTCUT_KEYS: list[tuple[str, str]] = [
        ("r", "Run"),
        ("d", "Database"),
        ("h", "Host"),
        ("c", "Config"),
        ("i", "History"),
        ("q", "Quit"),
    ]

    DEFAULT_CSS = """
    FooterWidget {
        height: 1;
        background: $primary-darken-3;
        color: $text-muted;
        padding: 0 1;
        layout: horizontal;
    }
    FooterWidget Static {
        width: auto;
        margin-right: 2;
    }
    """

    def compose(self) -> ComposeResult:
        """Render one Static label per shortcut key."""
        parts = "  ".join(
            f"[bold][{key}][/bold] {label}"
            for key, label in self.SHORTCUT_KEYS
        )
        yield Static(parts, markup=True)
