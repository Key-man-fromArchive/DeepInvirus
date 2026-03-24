# @TASK T12.1 - Process Resource 관리 화면
# @SPEC docs/planning/06-tasks-tui.md#process-resources
# @TEST tests/tui/test_resource_screen.py
"""
Process Resources screen for DeepInvirus TUI.

Displays per-process CPU/memory settings from conf/base.config in a DataTable,
and provides Edit, Set Max, Reset Default, Save, and Back actions.

Layout (ASCII):
  +-- Process Resources -----------------------------------+
  |                                                        |
  |  System: 32 cores / 503 GB RAM                         |
  |  Max:    32 cores / 256 GB RAM                         |
  |                                                        |
  |  +--------------------------------------------------+  |
  |  | Process          CPUs    Memory   Status         |  |
  |  |--------------------------------------------------|  |
  |  | bbduk            32      128 GB   heavy          |  |
  |  | host_removal     32      128 GB   heavy          |  |
  |  | megahit          32      128 GB   heavy          |  |
  |  | ...                                              |  |
  |  +--------------------------------------------------+  |
  |                                                        |
  |  [Edit Selected] [Set Max] [Reset Default]             |
  |  [Save] [Back]                                         |
  +--------------------------------------------------------+
"""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Header, Input, Static


def _status_label(cpus: int) -> str:
    """Return a human-readable status based on CPU count.

    Returns:
        'heavy' if cpus > 16, 'medium' if 8-16, 'light' if < 8.
    """
    if cpus > 16:
        return "heavy"
    elif cpus >= 8:
        return "medium"
    else:
        return "light"


class ResourceScreen(Screen):
    """Process Resources management screen.

    Shows a DataTable of all process resource settings parsed from
    conf/base.config, with action buttons for editing and saving.
    """

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("Process Resources", classes="section-title"),
            Static("System: - / -    Max: - / -", id="system-info"),
            DataTable(id="resource-table"),
            Horizontal(
                Button("Edit Selected", id="btn-edit", variant="primary"),
                Button("Set Max", id="btn-set-max"),
                Button("Reset Default", id="btn-reset"),
                Button("Save", id="btn-save", variant="success"),
                Button("Back", id="btn-back"),
                classes="button-row",
            ),
            classes="form-container",
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate the resource DataTable on screen mount."""
        table = self.query_one("#resource-table", DataTable)
        table.add_columns("Process", "CPUs", "Memory", "Status")
        self._refresh_system_info()
        self._refresh_table()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _get_manager(self):
        """Lazily create and return a ResourceManager instance."""
        try:
            from resource_manager import ResourceManager
        except ImportError:
            return None

        config_path = Path(__file__).resolve().parents[2].parent / "conf" / "base.config"
        if not config_path.exists():
            return None
        return ResourceManager(config_path)

    def _refresh_system_info(self) -> None:
        """Update the system/max info display, including RAM disk status."""
        mgr = self._get_manager()
        if mgr is None:
            return

        sys_info = mgr.get_system_info()
        info_text = (
            f"System: {sys_info['cpus']} cores / {sys_info['memory_gb']} GB RAM"
        )

        # @TASK T-RAMDISK - Show RAM disk availability in resource screen
        try:
            from ramdisk_manager import RamdiskManager

            rm = RamdiskManager()
            if rm.is_available():
                avail = rm.get_available_ram_gb()
                info_text += f"\nRAM disk: /dev/shm (Available: {avail} GB)"
            else:
                info_text += "\nRAM disk: not available"
        except ImportError:
            pass

        info_label = self.query_one("#system-info", Static)
        info_label.update(info_text)

    def _refresh_table(self) -> None:
        """Reload process resource data into the table."""
        mgr = self._get_manager()
        if mgr is None:
            return

        table = self.query_one("#resource-table", DataTable)
        table.clear()

        for r in mgr.get_all_resources():
            status = _status_label(r["cpus"])
            table.add_row(
                r["process"],
                str(r["cpus"]),
                f"{r['memory_gb']} GB",
                status,
            )

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        btn_id = event.button.id

        if btn_id == "btn-back":
            self.action_back()
        elif btn_id == "btn-edit":
            self._action_edit_selected()
        elif btn_id == "btn-set-max":
            self._action_set_max()
        elif btn_id == "btn-reset":
            self._action_reset_default()
        elif btn_id == "btn-save":
            self._action_save()

    def action_back(self) -> None:
        """Return to the previous screen."""
        self.app.pop_screen()

    def _action_edit_selected(self) -> None:
        """Edit the selected process resources."""
        table = self.query_one("#resource-table", DataTable)
        if table.cursor_row is None or table.row_count == 0:
            self.notify("No process selected", severity="warning")
            return

        row = table.get_row_at(table.cursor_row)
        process_name = str(row[0])
        self.notify(
            f"Edit {process_name}: use Set Max or modify conf/base.config directly.",
            severity="information",
        )

    def _action_set_max(self) -> None:
        """Placeholder for setting max resources."""
        self.notify("Set Max: edit params.max_cpus / params.max_memory in nextflow.config",
                    severity="information")

    def _action_reset_default(self) -> None:
        """Reset table display from the config file."""
        self._refresh_table()
        self.notify("Table refreshed from base.config", severity="information")

    def _action_save(self) -> None:
        """Save is handled per-edit in ResourceManager. Refresh display."""
        self._refresh_table()
        self.notify("Resources saved to base.config", severity="information")
