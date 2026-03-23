# @TASK T11.2 - 실행 이력 화면
# @SPEC docs/planning/06-tasks-tui.md#phase-11-t112-실행-이력-화면-redgreen
# @TEST tests/tui/test_config_history.py
"""
Run History screen for DeepInvirus TUI.

Displays past pipeline runs in a DataTable and provides actions:
View Results, Re-run, Delete, Back.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Header, Static

# Status display mapping
_STATUS_ICONS = {
    "done": "Done",
    "failed": "Failed",
    "running": "Running",
}


class HistoryScreen(Screen):
    """Run History screen.

    Shows a DataTable of past runs (Date, Samples, Viruses, Duration, Status)
    with action buttons: View Results, Re-run, Delete, Back.
    """

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("Run History", classes="section-title"),
            DataTable(id="history-table"),
            Horizontal(
                Button("View Results", id="btn-view", variant="primary"),
                Button("Re-run", id="btn-rerun"),
                Button("Delete", id="btn-delete", classes="danger"),
                Button("Back", id="btn-back"),
                classes="button-row",
            ),
            classes="form-container",
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate the history DataTable on screen mount."""
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Date", "Samples", "Viruses", "Duration", "Status")
        self._refresh_table()

    # ------------------------------------------------------------------
    # Table refresh
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        """Reload history data into the table."""
        try:
            from history_manager import get_history
        except ImportError:
            return

        table = self.query_one("#history-table", DataTable)
        table.clear()

        for run in get_history(limit=50):
            recorded = run.get("recorded_at", "")[:10]  # YYYY-MM-DD
            summary = run.get("summary", {})
            samples = str(summary.get("samples", "-"))
            viruses = str(summary.get("viruses", "-"))
            duration = self._format_duration(run.get("duration", 0))
            status_raw = run.get("status", "unknown")
            status = _STATUS_ICONS.get(status_raw, status_raw)
            table.add_row(
                recorded,
                samples,
                viruses,
                duration,
                status,
                key=run.get("run_id", ""),
            )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        total = int(seconds)
        h, remainder = divmod(total, 3600)
        m, s = divmod(remainder, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "btn-back":
            self.action_back()
        elif btn_id == "btn-delete":
            self._action_delete_run()
        elif btn_id == "btn-view":
            self._action_view_results()
        elif btn_id == "btn-rerun":
            self._action_rerun()

    def action_back(self) -> None:
        """Return to the previous screen."""
        self.app.pop_screen()

    def _get_selected_run_id(self) -> str | None:
        """Return the run_id of the currently selected row, or None."""
        table = self.query_one("#history-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            try:
                row_key = table.get_row_at(table.cursor_row)
                # row_key from DataTable is the row key we passed
                # We need to get the key from the RowKey
                keys = list(table.rows.keys())
                if table.cursor_row < len(keys):
                    return str(keys[table.cursor_row].value)
            except Exception:
                pass
        return None

    def _action_delete_run(self) -> None:
        """Delete the selected history entry."""
        try:
            from history_manager import delete_run
        except ImportError:
            return

        run_id = self._get_selected_run_id()
        if run_id:
            if delete_run(run_id):
                self._refresh_table()
                self.notify(f"Deleted run: {run_id}", severity="information")

    def _action_view_results(self) -> None:
        """Open the result viewer for the selected run."""
        try:
            from history_manager import get_run
        except ImportError:
            return

        run_id = self._get_selected_run_id()
        if run_id:
            run = get_run(run_id)
            if run:
                output_dir = run.get("output_dir", "")
                self.notify(
                    f"Results at: {output_dir}", severity="information"
                )

    def _action_rerun(self) -> None:
        """Store selected run params at app level for RunScreen re-run."""
        try:
            from history_manager import get_run
        except ImportError:
            return

        run_id = self._get_selected_run_id()
        if run_id:
            run = get_run(run_id)
            if run:
                # Store on app for RunScreen to pick up
                self.app._active_preset = run.get("params", {})  # type: ignore[attr-defined]
                self.notify("Parameters loaded for re-run", severity="information")
                self.app.pop_screen()
