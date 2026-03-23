# @TASK T7.2 - HeaderWidget 구현
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t72-공통-위젯-구현-redgreen
# @TEST tests/tui/test_widgets.py::TestHeaderWidget
"""
Header widget for DeepInvirus TUI.

Displays the application title, version, and DB installation status.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class HeaderWidget(Widget):
    """Application header showing logo, version, and DB status.

    Attributes:
        APP_TITLE: Application name displayed in the header.
        VERSION: Application version string.
    """

    APP_TITLE: str = "DeepInvirus"
    VERSION: str = "v0.1.0"

    DEFAULT_CSS = """
    HeaderWidget {
        height: 3;
        background: $primary;
        color: $text;
        padding: 0 2;
        layout: horizontal;
    }
    HeaderWidget #header-title {
        width: 1fr;
        content-align: left middle;
        text-style: bold;
    }
    HeaderWidget #header-db-status {
        width: auto;
        content-align: right middle;
    }
    """

    def __init__(self, db_status: str = "", **kwargs) -> None:
        """Initialise HeaderWidget.

        Args:
            db_status: Short DB status string, e.g. "DB: 2026-03-23" or
                       "DB: Not installed". Defaults to empty string.
        """
        super().__init__(**kwargs)
        self._db_status = db_status

    def compose(self) -> ComposeResult:
        """Render the header row."""
        title_text = f"{self.APP_TITLE}  {self.VERSION}"
        yield Static(title_text, id="header-title")
        status_text = self._db_status if self._db_status else "DB: unknown"
        yield Static(status_text, id="header-db-status")

    def update_db_status(self, status: str) -> None:
        """Update the DB status label at runtime.

        Args:
            status: New status string to display.
        """
        self._db_status = status
        try:
            self.query_one("#header-db-status", Static).update(status)
        except Exception:
            pass
