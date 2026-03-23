# @TASK T7.2 - StatusBar 구현
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t72-공통-위젯-구현-redgreen
# @TEST tests/tui/test_widgets.py::TestStatusBar
"""
Status bar widget for DeepInvirus TUI.

Reads VERSION.json from db_dir to surface:
- DB directory path
- DB version (or "Not installed" when VERSION.json is absent)
- Available host genomes
- Last run time (from ~/.deepinvirus/history.json, or "No runs yet")
"""

from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

# Default history file location
_DEFAULT_HISTORY = Path.home() / ".deepinvirus" / "history.json"


class StatusBar(Widget):
    """Status bar showing DB version, host genome list, and last run time.

    Args:
        db_dir: Path to the databases directory. When omitted, defaults to
                the current working directory so the widget can still be
                instantiated without configuration.
        history_file: Path to the history JSON file. Defaults to
                      ~/.deepinvirus/history.json.
    """

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
        layout: horizontal;
    }
    StatusBar Static {
        width: auto;
        margin-right: 3;
    }
    """

    def __init__(
        self,
        db_dir: Path | None = None,
        history_file: Path | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.db_dir: Path = db_dir if db_dir is not None else Path.cwd()
        self.history_file: Path = (
            history_file if history_file is not None else _DEFAULT_HISTORY
        )

    # ------------------------------------------------------------------
    # Public helpers (called from compose and from outside the widget)
    # ------------------------------------------------------------------

    def load_db_info(self) -> dict:
        """Read VERSION.json and history.json, return a status dict.

        Returns:
            dict with keys:
                db_dir (str): absolute path of the db directory
                db_version (str): version string or "Not installed"
                hosts (list[str]): available host genome names
                last_run (str): ISO datetime string or "No runs yet"
        """
        info: dict = {
            "db_dir": str(self.db_dir),
            "db_version": "Not installed",
            "hosts": [],
            "last_run": "No runs yet",
        }

        # Read VERSION.json
        version_file = self.db_dir / "VERSION.json"
        if version_file.exists():
            try:
                data = json.loads(version_file.read_text())
                info["db_version"] = data.get("db_version", "Not installed")
                info["hosts"] = data.get("hosts", [])
            except (json.JSONDecodeError, OSError):
                pass

        # Read history.json for last run time
        if self.history_file.exists():
            try:
                history = json.loads(self.history_file.read_text())
                if isinstance(history, list) and history:
                    last = history[-1]
                    info["last_run"] = last.get("timestamp", "No runs yet")
            except (json.JSONDecodeError, OSError):
                pass

        return info

    def compose(self) -> ComposeResult:
        """Render status fields as inline Static labels."""
        info = self.load_db_info()

        hosts_str = ", ".join(info["hosts"]) if info["hosts"] else "none"
        yield Static(f"DB: {info['db_dir']}", id="status-db-dir")
        yield Static(f"Version: {info['db_version']}", id="status-db-version")
        yield Static(f"Hosts: {hosts_str}", id="status-hosts")
        yield Static(f"Last run: {info['last_run']}", id="status-last-run")

    def refresh_status(self) -> None:
        """Re-read VERSION.json and update displayed labels."""
        info = self.load_db_info()
        hosts_str = ", ".join(info["hosts"]) if info["hosts"] else "none"
        try:
            self.query_one("#status-db-dir", Static).update(
                f"DB: {info['db_dir']}"
            )
            self.query_one("#status-db-version", Static).update(
                f"Version: {info['db_version']}"
            )
            self.query_one("#status-hosts", Static).update(
                f"Hosts: {hosts_str}"
            )
            self.query_one("#status-last-run", Static).update(
                f"Last run: {info['last_run']}"
            )
        except Exception:
            pass
