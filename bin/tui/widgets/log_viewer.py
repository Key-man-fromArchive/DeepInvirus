# @TASK T7.2 - LogViewer 구현
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t72-공통-위젯-구현-redgreen
# @TEST tests/tui/test_widgets.py::TestLogViewer
"""
Log viewer widget for DeepInvirus TUI.

Provides a scrollable, auto-scrolling log pane that streams Nextflow
stdout/stderr lines in real time (tail -f style).

Key API:
    append_log(line: str) — add a new log line and scroll to bottom
    clear()               — erase all log lines
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog


class LogViewer(Widget):
    """Real-time log streaming widget.

    Internally buffers lines in ``_log_lines`` (up to ``MAX_LINES``).
    When mounted, a ``RichLog`` child handles the visual rendering and
    auto-scroll.

    Attributes:
        MAX_LINES (int): Maximum number of log lines kept in the buffer.
            Oldest lines are discarded when the limit is reached.
    """

    MAX_LINES: int = 1000

    DEFAULT_CSS = """
    LogViewer {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }
    LogViewer RichLog {
        height: 1fr;
        scrollbar-gutter: stable;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._log_lines: list[str] = []

    def compose(self) -> ComposeResult:
        """Render the scrollable RichLog pane."""
        yield RichLog(
            highlight=False,
            markup=False,
            auto_scroll=True,
            id="log-rich-log",
        )

    def append_log(self, line: str) -> None:
        """Append a log line and scroll to the bottom.

        If the buffer exceeds MAX_LINES, the oldest line is evicted.

        Args:
            line: Single log line string (without trailing newline).
        """
        self._log_lines.append(line)
        if len(self._log_lines) > self.MAX_LINES:
            self._log_lines.pop(0)

        try:
            rich_log: RichLog = self.query_one("#log-rich-log", RichLog)
            rich_log.write(line)
        except Exception:
            # Not yet mounted (unit-test context) — buffer-only mode.
            pass

    def clear(self) -> None:
        """Clear all log lines from the buffer and the visual pane."""
        self._log_lines = []
        try:
            rich_log: RichLog = self.query_one("#log-rich-log", RichLog)
            rich_log.clear()
        except Exception:
            pass
