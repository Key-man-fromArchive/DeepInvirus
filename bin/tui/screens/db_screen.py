# @TASK T9.1 + T9.2 - DB 관리 화면 (상태 표시 + 액션)
# @SPEC docs/planning/06-tasks-tui.md#phase-9-t91-db-상태-화면-redgreen
# @SPEC docs/planning/06-tasks-tui.md#phase-9-t92-db-업데이트-액션-redgreen
# @TEST tests/tui/test_db_screen.py
"""
Database Management screen for DeepInvirus TUI.

Layout (ASCII):
  +-- Database Management --------------------------------+
  |                                                       |
  |  DB Directory: /path/to/databases                     |
  |                                                       |
  |  +---------------------------------------------------+|
  |  | Component         Version     Updated   Status    ||
  |  |---------------------------------------------------||
  |  | viral_protein     2026_01     2026-03-23   OK     ||
  |  | viral_nucleotide  release_224 2026-03-23   OK     ||
  |  | genomad_db        1.7         2026-03-23   OK     ||
  |  | taxonomy          2026-03-20  2026-03-23   OK     ||
  |  +---------------------------------------------------+|
  |                                                       |
  |  Total size: 53.2 GB                                  |
  |                                                       |
  |  [Install All] [Update Selected] [Back]               |
  |                                                       |
  |  [ProgressWidget - hidden until install starts]       |
  +-------------------------------------------------------+

T9.1: VERSION.json -> DataTable, disk usage, installed/missing status
T9.2: [Install All] -> subprocess install_databases.py, progress, reload
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static

from tui.widgets.progress import ProgressWidget

# ---------------------------------------------------------------------------
# Known DB components (canonical list matching 04-database-design.md)
# ---------------------------------------------------------------------------

# @TASK T9.1 - DB 컴포넌트 목록
# @SPEC docs/planning/04-database-design.md#VERSION.json-스키마
KNOWN_COMPONENTS: list[str] = [
    "viral_protein",
    "viral_nucleotide",
    "genomad_db",
    "taxonomy",
]

# Human-readable labels for the DataTable
COMPONENT_LABELS: dict[str, str] = {
    "viral_protein": "Viral Protein",
    "viral_nucleotide": "Viral Nucleotide",
    "genomad_db": "geNomad DB",
    "taxonomy": "NCBI Taxonomy",
}

# Default DB directory (relative to project root)
_DEFAULT_DB_DIR = Path(__file__).resolve().parents[3] / "databases"


def _resolve_db_dir() -> Path:
    """Return the database directory path.

    Checks (in order):
    1. DEEPINVIRUS_DB_DIR environment variable
    2. Default: <project_root>/databases/
    """
    import os

    env = os.environ.get("DEEPINVIRUS_DB_DIR")
    if env:
        return Path(env)
    return _DEFAULT_DB_DIR


# ---------------------------------------------------------------------------
# Disk usage helper
# ---------------------------------------------------------------------------


def _get_dir_size(path: Path) -> int:
    """Compute total size of a directory tree in bytes.

    Uses an iterative walk to avoid stack overflow on very deep trees.
    Returns 0 if the path does not exist.
    """
    if not path.exists():
        return 0
    total = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_file():
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _format_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable string (e.g. '53.2 GB')."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    for unit in ("KB", "MB", "GB", "TB"):
        size_bytes /= 1024
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
    return f"{size_bytes:.1f} PB"


# ---------------------------------------------------------------------------
# DbScreen
# ---------------------------------------------------------------------------


class DbScreen(Screen):
    """Database Management screen (T9.1 + T9.2).

    Displays VERSION.json contents in a DataTable, shows disk usage,
    and provides [Install All] / [Update Selected] / [Back] actions.

    Attributes:
        db_dir: Path to the database root directory.
    """

    def __init__(self, db_dir: Path | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.db_dir: Path = db_dir or _resolve_db_dir()

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Compose the database management layout."""
        yield Static(
            f"DB Directory: {self.db_dir}",
            id="db-path",
            classes="section-title",
        )

        table = DataTable(id="db-table")
        table.cursor_type = "row"
        yield table

        yield Static("", id="disk-usage", classes="text-muted")

        yield ProgressWidget(id="db-progress")

        with Static(classes="button-row"):
            yield Button(
                "Install All",
                id="install-all",
                classes="primary",
            )
            yield Button(
                "Update Selected",
                id="update-selected",
                classes="secondary",
            )
            yield Button(
                "Back",
                id="back",
                classes="secondary",
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Populate the DataTable when the screen is mounted."""
        self._setup_table()
        self._populate_table()
        self._update_disk_usage()

    # ------------------------------------------------------------------
    # T9.1: load_db_info() - VERSION.json parsing
    # ------------------------------------------------------------------

    # @TASK T9.1 - VERSION.json 파싱
    # @SPEC docs/planning/04-database-design.md#VERSION.json-스키마

    def load_db_info(self, db_dir: Path | None = None) -> list[dict[str, Any]]:
        """Parse VERSION.json and return a list of component info dicts.

        Each dict contains:
            component (str): Component key (e.g. 'viral_protein').
            version (str): Version string.
            updated (str): Download date.
            installed (bool): Whether the component is present.

        Args:
            db_dir: Override database directory (defaults to self.db_dir).

        Returns:
            List of component info dictionaries.  Empty list if
            VERSION.json does not exist.
        """
        target = db_dir or self.db_dir
        vfile = target / "VERSION.json"

        if not vfile.exists():
            return []

        try:
            with open(vfile) as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return []

        databases: dict[str, Any] = data.get("databases", {})
        result: list[dict[str, Any]] = []

        for comp_key in KNOWN_COMPONENTS:
            if comp_key in databases:
                entry = databases[comp_key]
                version = (
                    entry.get("version")
                    or entry.get("ncbi_version")
                    or entry.get("ictv_version")
                    or "-"
                )
                updated = entry.get("downloaded_at", "-")
                result.append(
                    {
                        "component": comp_key,
                        "version": str(version),
                        "updated": str(updated),
                        "installed": True,
                    }
                )

        # Also include host genomes if present
        host_genomes = databases.get("host_genomes", {})
        for host_name, host_info in host_genomes.items():
            result.append(
                {
                    "component": f"host:{host_name}",
                    "version": host_info.get("name", "-"),
                    "updated": host_info.get("downloaded_at", "-"),
                    "installed": True,
                }
            )

        return result

    # ------------------------------------------------------------------
    # T9.2: reload_db_info() - Refresh table after install/update
    # ------------------------------------------------------------------

    def reload_db_info(self) -> None:
        """Reload VERSION.json and refresh the DataTable.

        Called automatically after install/update completes.
        """
        self._populate_table()
        self._update_disk_usage()

    # ------------------------------------------------------------------
    # T9.2: run_install() - Execute install_databases.py
    # ------------------------------------------------------------------

    # @TASK T9.2 - DB 설치/업데이트 비동기 실행
    # @SPEC docs/planning/06-tasks-tui.md#phase-9-t92-db-업데이트-액션-redgreen

    async def run_install(
        self,
        components: str = "all",
        host: str = "human",
    ) -> None:
        """Run install_databases.py as an async subprocess.

        Updates ProgressWidget during execution and calls
        reload_db_info() on completion.

        Args:
            components: Comma-separated component list or 'all'.
            host: Host genome to install.
        """
        install_script = Path(__file__).resolve().parents[1].parent / "install_databases.py"

        cmd = [
            sys.executable,
            str(install_script),
            "--db-dir",
            str(self.db_dir),
            "--components",
            components,
            "--host",
            host,
        ]

        progress = self.query_one("#db-progress", ProgressWidget)
        progress.update(current=0, total=1, step_name="Starting installation...")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            progress.update(current=0, total=1, step_name="Installing databases...")

            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                progress.update(
                    current=1,
                    total=1,
                    step_name="Installation complete",
                )
                self.notify("Database installation completed successfully.", title="Success")
            else:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                progress.update(
                    current=0,
                    total=1,
                    step_name=f"Installation failed: {error_msg[:80]}",
                )
                self.notify(
                    f"Installation failed (exit {proc.returncode})",
                    title="Error",
                    severity="error",
                )
        except Exception as exc:
            progress.update(
                current=0,
                total=1,
                step_name=f"Error: {exc}",
            )
            self.notify(str(exc), title="Error", severity="error")
        finally:
            self.reload_db_info()

    # ------------------------------------------------------------------
    # T9.2: run_update_selected() - Update specific components
    # ------------------------------------------------------------------

    async def run_update_selected(self) -> None:
        """Update only the component selected in the DataTable.

        Reads the cursor row from the DataTable, extracts the component
        key, and runs install_databases.py with --components <key>.
        """
        try:
            table = self.query_one("#db-table", DataTable)
            row_key = table.cursor_row
            if row_key is None:
                self.notify("No component selected.", title="Warning", severity="warning")
                return

            # Get the component name from the first column of the cursor row
            row_data = table.get_row_at(row_key)
            component_name = str(row_data[0]).strip()

            # Map display name back to install component key
            comp_map = {
                "Viral Protein": "protein",
                "Viral Nucleotide": "nucleotide",
                "geNomad DB": "genomad",
                "NCBI Taxonomy": "taxonomy",
            }

            install_key = comp_map.get(component_name)
            if install_key:
                await self.run_install(components=install_key)
            elif component_name.startswith("Host:"):
                host_name = component_name.split(":")[1].strip()
                await self.run_install(components="host", host=host_name)
            else:
                self.notify(
                    f"Unknown component: {component_name}",
                    title="Warning",
                    severity="warning",
                )
        except Exception as exc:
            self.notify(str(exc), title="Error", severity="error")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "install-all":
            await self.run_install(components="all")
        elif button_id == "update-selected":
            await self.run_update_selected()
        elif button_id == "back":
            self.app.pop_screen()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _setup_table(self) -> None:
        """Configure the DataTable columns."""
        try:
            table = self.query_one("#db-table", DataTable)
            table.add_columns("Component", "Version", "Updated", "Status")
        except Exception:
            pass

    def _populate_table(self) -> None:
        """Fill the DataTable with current DB info."""
        try:
            table = self.query_one("#db-table", DataTable)
            table.clear()

            info = self.load_db_info()

            if info:
                for entry in info:
                    label = COMPONENT_LABELS.get(
                        entry["component"], entry["component"]
                    )
                    # Host genome entries
                    if entry["component"].startswith("host:"):
                        host_name = entry["component"].split(":")[1]
                        label = f"Host: {host_name}"

                    status = "OK" if entry["installed"] else "Missing"
                    table.add_row(
                        label,
                        entry["version"],
                        entry["updated"],
                        status,
                    )

                # Add known components that are NOT installed
                installed_keys = {e["component"] for e in info}
                for comp_key in KNOWN_COMPONENTS:
                    if comp_key not in installed_keys:
                        label = COMPONENT_LABELS.get(comp_key, comp_key)
                        table.add_row(label, "-", "-", "Not installed")
            else:
                # No VERSION.json - show all as not installed
                for comp_key in KNOWN_COMPONENTS:
                    label = COMPONENT_LABELS.get(comp_key, comp_key)
                    table.add_row(label, "-", "-", "Not installed")
        except Exception:
            pass

    def _update_disk_usage(self) -> None:
        """Compute and display total disk usage of the DB directory."""
        try:
            total_size = _get_dir_size(self.db_dir)
            label = self.query_one("#disk-usage", Static)
            label.update(f"Total size: {_format_size(total_size)}")
        except Exception:
            pass
