# @TASK T11.1 - Config 프리셋 화면
# @SPEC docs/planning/06-tasks-tui.md#phase-11-t111-config-프리셋-화면-redgreen
# @TEST tests/tui/test_config_history.py
"""
Config Presets screen for DeepInvirus TUI.

Displays saved pipeline presets in a DataTable and provides
CRUD operations: New, Edit, Delete, Apply to Run, Back.
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Header, Static


class ConfigScreen(Screen):
    """Config Presets management screen.

    Shows a DataTable of saved presets (Name, Host, Assembler, ML, Search)
    with action buttons: New, Edit, Delete, Apply to Run, Back.
    """

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("Config Presets", classes="section-title"),
            DataTable(id="preset-table"),
            Horizontal(
                Button("New", id="btn-new", variant="primary"),
                Button("Edit", id="btn-edit"),
                Button("Delete", id="btn-delete", classes="danger"),
                Button("Apply to Run", id="btn-apply", variant="success"),
                Button("Back", id="btn-back"),
                classes="button-row",
            ),
            classes="form-container",
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate the preset DataTable on screen mount."""
        table = self.query_one("#preset-table", DataTable)
        table.add_columns("Name", "Host", "Assembler", "ML", "Search")
        self._refresh_table()

    # ------------------------------------------------------------------
    # Table refresh
    # ------------------------------------------------------------------

    def _refresh_table(self) -> None:
        """Reload preset data into the table."""
        try:
            from config_manager import get_preset_details, list_presets
        except ImportError:
            return

        table = self.query_one("#preset-table", DataTable)
        table.clear()

        for name in list_presets():
            try:
                details = get_preset_details(name)
                params = details.get("params", {})
                table.add_row(
                    name,
                    params.get("host", "-"),
                    params.get("assembler", "-"),
                    "Yes" if params.get("ml_detection") else "No",
                    params.get("search_mode", "-"),
                )
            except Exception:
                table.add_row(name, "-", "-", "-", "-")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        btn_id = event.button.id

        if btn_id == "btn-back":
            self.action_back()
        elif btn_id == "btn-new":
            self._action_new_preset()
        elif btn_id == "btn-delete":
            self._action_delete_preset()
        elif btn_id == "btn-apply":
            self._action_apply_to_run()
        elif btn_id == "btn-edit":
            self._action_edit_preset()

    def action_back(self) -> None:
        """Return to the previous screen."""
        self.app.pop_screen()

    def _action_new_preset(self) -> None:
        """Save current default parameters as a new preset."""
        try:
            from config_manager import save_preset
        except ImportError:
            self.notify("config_manager not available", severity="error")
            return

        default_params = {
            "host": "none",
            "assembler": "megahit",
            "ml_detection": True,
            "search_mode": "fast",
            "threads": 8,
        }
        # Prompt for a name via the app's input dialog
        self.app.push_screen(
            _PresetNameDialog(default_params, callback=self._on_preset_saved)
        )

    def _on_preset_saved(self) -> None:
        """Callback after a preset has been saved."""
        self._refresh_table()
        self.notify("Preset saved", severity="information")

    def _action_delete_preset(self) -> None:
        """Delete the currently selected preset."""
        try:
            from config_manager import delete_preset
        except ImportError:
            return

        table = self.query_one("#preset-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            row = table.get_row_at(table.cursor_row)
            name = str(row[0])
            if delete_preset(name):
                self._refresh_table()
                self.notify(f"Deleted preset: {name}", severity="information")

    def _action_apply_to_run(self) -> None:
        """Store selected preset params at app level for RunScreen."""
        try:
            from config_manager import load_preset
        except ImportError:
            return

        table = self.query_one("#preset-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            row = table.get_row_at(table.cursor_row)
            name = str(row[0])
            try:
                params = load_preset(name)
                # Store on app for RunScreen to pick up
                self.app._active_preset = params  # type: ignore[attr-defined]
                self.notify(f"Preset '{name}' applied", severity="information")
                self.app.pop_screen()
            except FileNotFoundError:
                self.notify(f"Preset '{name}' not found", severity="error")

    def _action_edit_preset(self) -> None:
        """Placeholder for edit functionality."""
        self.notify("Edit feature coming soon", severity="warning")


# ---------------------------------------------------------------------------
# Internal dialog for new preset name
# ---------------------------------------------------------------------------


class _PresetNameDialog(Screen):
    """Simple dialog to capture a preset name."""

    def __init__(
        self, params: dict, callback: callable | None = None, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._params = params
        self._callback = callback

    def compose(self) -> ComposeResult:
        from textual.widgets import Input

        yield Vertical(
            Static("Enter preset name:", classes="section-title"),
            Input(id="preset-name-input", placeholder="my_preset"),
            Horizontal(
                Button("Save", id="btn-save", variant="primary"),
                Button("Cancel", id="btn-cancel"),
                classes="button-row",
            ),
            classes="form-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            from textual.widgets import Input

            try:
                from config_manager import save_preset
            except ImportError:
                self.app.pop_screen()
                return

            inp = self.query_one("#preset-name-input", Input)
            name = inp.value.strip()
            if name:
                save_preset(name, self._params)
                self.app.pop_screen()
                if self._callback:
                    self._callback()
        elif event.button.id == "btn-cancel":
            self.app.pop_screen()
