# @TASK T10.1 + T10.2 - Host Genome 관리 화면 + Host 추가 액션
# @SPEC docs/planning/06-tasks-tui.md#phase-10-t101-host-목록-화면-redgreen
# @SPEC docs/planning/06-tasks-tui.md#phase-10-t102-host-추가-액션-redgreen
# @TEST tests/tui/test_host_screen.py
"""
Host Genome Management screen for DeepInvirus TUI.

Displays installed host genomes in a DataTable with Name, Index Status,
and Size columns. Provides actions to add new host genomes (via
bin/add_host.py) and remove selected hosts.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input, Static


# ---------------------------------------------------------------------------
# Helper: format file size
# ---------------------------------------------------------------------------


def _format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable size string (e.g., "3.1 GB", "420 MB").
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.1f} MB"
    else:
        return f"{size_bytes / 1024**3:.1f} GB"


def _dir_size(path: Path) -> int:
    """Compute total size of all files in a directory (non-recursive is enough).

    Args:
        path: Directory path.

    Returns:
        Total size in bytes.
    """
    total = 0
    if path.is_dir():
        for f in path.iterdir():
            if f.is_file():
                total += f.stat().st_size
    return total


# ---------------------------------------------------------------------------
# HostScreen
# ---------------------------------------------------------------------------


class HostScreen(Screen):
    """Host Genome Management screen.

    Scans databases/host_genomes/ for installed host genomes and displays
    them in a DataTable. Supports adding new hosts via an inline form
    that invokes bin/add_host.py as a subprocess.

    Attributes:
        db_dir: Root database directory (set via constructor or detected).
    """

    DEFAULT_CSS = """
    HostScreen {
        layout: vertical;
    }

    HostScreen .screen-title {
        text-style: bold;
        padding: 1 2;
        height: 3;
        content-align: center middle;
    }

    HostScreen #host-table {
        height: 1fr;
        margin: 0 2;
    }

    HostScreen .button-row {
        layout: horizontal;
        height: 3;
        align: center middle;
        padding: 1 0;
    }

    HostScreen .button-row Button {
        margin: 0 1;
    }

    HostScreen #add-host-form {
        layout: vertical;
        padding: 1 2;
        height: auto;
        display: none;
    }

    HostScreen #add-host-form.visible {
        display: block;
    }

    HostScreen .form-row {
        layout: horizontal;
        height: 3;
        margin-bottom: 1;
    }

    HostScreen .form-label {
        width: 16;
        content-align: left middle;
    }

    HostScreen .form-field {
        width: 1fr;
    }
    """

    def __init__(
        self,
        db_dir: Path | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialise HostScreen.

        Args:
            db_dir: Root database directory. If None, will attempt to detect
                from environment or use a default path.
            name: Screen name for Textual navigation.
            id: CSS id.
            classes: CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self.db_dir = db_dir

    # ------------------------------------------------------------------
    # Compose UI
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Build the Host Genome Management UI layout."""
        yield Static("Host Genome Management", classes="screen-title")

        table = DataTable(id="host-table")
        table.cursor_type = "row"
        yield table

        # Add Host inline form (hidden by default)
        with Vertical(id="add-host-form"):
            with Horizontal(classes="form-row"):
                yield Static("Name:", classes="form-label")
                yield Input(
                    placeholder="e.g. beetle",
                    id="input-host-name",
                    classes="form-field",
                )
            with Horizontal(classes="form-row"):
                yield Static("FASTA path:", classes="form-label")
                yield Input(
                    placeholder="/path/to/reference.fa",
                    id="input-fasta-path",
                    classes="form-field",
                )
            with Horizontal(classes="button-row"):
                yield Button("Confirm Add", id="confirm-add-host", variant="primary")
                yield Button("Cancel", id="cancel-add-host", variant="default")

        # Action buttons
        with Horizontal(classes="button-row"):
            yield Button("Add Host", id="add-host", variant="primary")
            yield Button("Remove Selected", id="remove-host", variant="error")
            yield Button("Back", id="back", variant="default")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate the DataTable when the screen is mounted."""
        self._setup_table()
        self._refresh_table()

    def _setup_table(self) -> None:
        """Add columns to the DataTable."""
        table = self.query_one("#host-table", DataTable)
        table.add_columns("Name", "Index Status", "Size")

    def _refresh_table(self) -> None:
        """Clear and re-populate the host genome table."""
        table = self.query_one("#host-table", DataTable)
        table.clear()

        if self.db_dir is None:
            return

        hosts = self.list_hosts(self.db_dir)
        for host in hosts:
            index_icon = "YES" if host["indexed"] else "NO"
            size_str = _format_size(host["size"])
            table.add_row(host["name"], index_icon, size_str)

    # ------------------------------------------------------------------
    # list_hosts: directory scanner
    # ------------------------------------------------------------------

    def list_hosts(self, db_dir: Path) -> list[dict[str, Any]]:
        """Scan databases/host_genomes/ and return a list of host info dicts.

        Each dict contains:
            - name (str): directory name (e.g. "human")
            - indexed (bool): True if any .mmi file exists
            - size (int): total file size in bytes

        Args:
            db_dir: Root database directory.

        Returns:
            List of host genome info dictionaries, sorted by name.
        """
        host_genomes_dir = db_dir / "host_genomes"

        if not host_genomes_dir.is_dir():
            return []

        hosts: list[dict[str, Any]] = []
        for entry in sorted(host_genomes_dir.iterdir()):
            if not entry.is_dir():
                continue

            # Check for .mmi index files
            mmi_files = list(entry.glob("*.mmi"))
            indexed = len(mmi_files) > 0

            # Compute directory size
            size = _dir_size(entry)

            hosts.append({
                "name": entry.name,
                "indexed": indexed,
                "size": size,
            })

        return hosts

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: The button pressed event.
        """
        button_id = event.button.id

        if button_id == "back":
            self.app.pop_screen()

        elif button_id == "add-host":
            self._show_add_form()

        elif button_id == "cancel-add-host":
            self._hide_add_form()

        elif button_id == "confirm-add-host":
            self._execute_add_host()

        elif button_id == "remove-host":
            self._remove_selected_host()

    def _show_add_form(self) -> None:
        """Show the Add Host inline form."""
        form = self.query_one("#add-host-form")
        form.add_class("visible")

    def _hide_add_form(self) -> None:
        """Hide the Add Host inline form and clear inputs."""
        form = self.query_one("#add-host-form")
        form.remove_class("visible")
        self.query_one("#input-host-name", Input).value = ""
        self.query_one("#input-fasta-path", Input).value = ""

    def _execute_add_host(self) -> None:
        """Run bin/add_host.py as subprocess with form values."""
        name = self.query_one("#input-host-name", Input).value.strip()
        fasta_path = self.query_one("#input-fasta-path", Input).value.strip()

        if not name:
            self.notify("Host name is required.", severity="error")
            return
        if not fasta_path:
            self.notify("FASTA path is required.", severity="error")
            return

        fasta = Path(fasta_path)
        if not fasta.exists():
            self.notify(f"FASTA file not found: {fasta}", severity="error")
            return

        # Locate add_host.py relative to this file
        add_host_script = Path(__file__).resolve().parents[1].parent / "add_host.py"

        if not add_host_script.exists():
            self.notify(f"add_host.py not found: {add_host_script}", severity="error")
            return

        cmd = [
            sys.executable,
            str(add_host_script),
            "--name", name,
            "--fasta", str(fasta),
            "--db-dir", str(self.db_dir),
        ]

        self.notify(f"Adding host genome '{name}'...", severity="information")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                self.notify(f"Host '{name}' added successfully.", severity="information")
                self._hide_add_form()
                self._refresh_table()
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                self.notify(f"Failed to add host: {error_msg}", severity="error")
        except Exception as exc:
            self.notify(f"Error running add_host.py: {exc}", severity="error")

    def _remove_selected_host(self) -> None:
        """Remove the currently selected host genome (placeholder)."""
        table = self.query_one("#host-table", DataTable)
        if table.cursor_row is not None and table.row_count > 0:
            self.notify(
                "Host removal is not yet implemented.",
                severity="warning",
            )
        else:
            self.notify("No host selected.", severity="warning")
