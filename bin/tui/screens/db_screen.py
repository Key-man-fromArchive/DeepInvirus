# @TASK T9.1 + T9.2 + T-DB-INDEX - DB 관리 화면 (상태 + 인덱싱 + 액션)
# @SPEC docs/planning/06-tasks-tui.md#phase-9-t91-db-상태-화면-redgreen
# @SPEC docs/planning/06-tasks-tui.md#phase-9-t92-db-업데이트-액션-redgreen
# @TEST tests/tui/test_db_screen.py
# @TEST tests/test_db_indexer.py
"""
Database Management screen for DeepInvirus TUI.

Layout (ASCII):
  +-- Database Management ----------------------------------------+
  |                                                               |
  |  DB Directory: /path/to/databases                             |
  |  Total size: 8.2 GB                                           |
  |                                                               |
  |  +-----------------------------------------------------------+|
  |  | Component        Tool      Index  Version  Updated Status ||
  |  |-----------------------------------------------------------||
  |  | Viral Protein    Diamond   OK     2026_01  03-23   OK     ||
  |  | Viral Nucleotide MMseqs2   OK     rel_224  03-23   OK     ||
  |  | geNomad DB       Built-in  OK     1.7      03-23   OK     ||
  |  | NCBI Taxonomy    N/A       OK     03-20    03-23   OK     ||
  |  | Host: tmol       minimap2  OK     -        03-23   OK     ||
  |  | Host: zmor       minimap2  OK     -        03-23   OK     ||
  |  +-----------------------------------------------------------+|
  |                                                               |
  |  [Install All] [Update] [Rebuild Index] [Rebuild All] [Back] |
  |                                                               |
  |  [ProgressWidget - hidden until install starts]               |
  +---------------------------------------------------------------+

T9.1: VERSION.json -> DataTable, disk usage, installed/missing status
T9.2: [Install All] -> subprocess install_databases.py, progress, reload
T-DB-INDEX: Index status display + rebuild actions via DBIndexer
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

from db_indexer import DBIndexer
from db_lifecycle import DBLifecycleManager
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
    "exclusion_db",
]

# Human-readable labels for the DataTable
COMPONENT_LABELS: dict[str, str] = {
    "viral_protein": "RefSeq Viral Protein (Secondary)",
    "viral_nucleotide": "GenBank Viral NT (Primary, 740K)",
    "genomad_db": "geNomad DB",
    "taxonomy": "NCBI Taxonomy",
    "exclusion_db": "Exclusion DB (SwissProt)",
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
        yield Static(
            "Primary viral nucleotide DB: GenBank viral NT (~740K sequences). RefSeq-derived evidence is retained as secondary verification.",
            classes="text-muted",
        )

        table = DataTable(id="db-table")
        table.cursor_type = "row"
        yield table

        yield Static("", id="disk-usage", classes="text-muted")

        yield ProgressWidget(id="db-progress")

        with Static(classes="button-row"):
            yield Button(
                "Install",
                id="install-all",
                classes="primary",
            )
            yield Button(
                "Update",
                id="update-selected",
                classes="secondary",
            )
            yield Button(
                "Rebuild Index",
                id="rebuild-index",
                classes="secondary",
            )
            yield Button(
                "Remove",
                id="remove-selected",
                classes="secondary",
            )
            yield Button(
                "Cleanup Backups",
                id="cleanup-backups",
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

            row_data = table.get_row_at(row_key)
            component_name = str(row_data[0]).strip()
            comp_key = self._display_to_component_key(component_name)
            comp_map = {
                "viral_protein": "protein",
                "viral_nucleotide": "nucleotide",
                "genomad_db": "genomad",
                "taxonomy": "taxonomy",
                "exclusion_db": "exclusion",
            }

            install_key = comp_map.get(comp_key or "")
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
        elif button_id == "rebuild-index":
            await self.run_rebuild_index()
        elif button_id == "remove-selected":
            await self.run_remove_selected()
        elif button_id == "cleanup-backups":
            await self.run_cleanup_backups()
        elif button_id == "back":
            self.app.pop_screen()

    # ------------------------------------------------------------------
    # T-DB-INDEX: Rebuild index actions
    # ------------------------------------------------------------------

    # @TASK T-DB-INDEX - 인덱스 재빌드 액션
    # @SPEC docs/planning/04-database-design.md

    async def run_rebuild_index(self) -> None:
        """Rebuild the index for the component selected in the DataTable.

        Reads the cursor row, maps the display name back to a component key,
        and runs the rebuild command via an async subprocess.
        """
        try:
            table = self.query_one("#db-table", DataTable)
            row_key = table.cursor_row
            if row_key is None:
                self.notify(
                    "No component selected.",
                    title="Warning",
                    severity="warning",
                )
                return

            row_data = table.get_row_at(row_key)
            component_name = str(row_data[0]).strip()

            # Map display name back to component key
            comp_key = self._display_to_component_key(component_name)
            if comp_key is None:
                self.notify(
                    f"Unknown component: {component_name}",
                    title="Warning",
                    severity="warning",
                )
                return

            indexer = DBIndexer(self.db_dir)
            cmd_str = indexer.rebuild_index(comp_key)
            if not cmd_str:
                self.notify(
                    f"No rebuild available for {component_name}",
                    title="Info",
                )
                return

            await self._run_shell_command(cmd_str, label=f"Rebuilding {component_name}")

        except Exception as exc:
            self.notify(str(exc), title="Error", severity="error")

    async def run_rebuild_all(self) -> None:
        """Rebuild indices for all components that are missing them."""
        try:
            indexer = DBIndexer(self.db_dir)
            commands = indexer.rebuild_all()
            if not commands:
                self.notify(
                    "All indices are up to date.",
                    title="Info",
                )
                return

            for i, cmd_str in enumerate(commands, 1):
                await self._run_shell_command(
                    cmd_str,
                    label=f"Rebuild ({i}/{len(commands)})",
                )

        except Exception as exc:
            self.notify(str(exc), title="Error", severity="error")

    # ------------------------------------------------------------------
    # T-DB-LIFECYCLE: Remove and cleanup actions
    # ------------------------------------------------------------------

    # @TASK T-DB-LIFECYCLE - Remove selected component
    # @SPEC docs/planning/04-database-design.md#DB-갱신-전략

    async def run_remove_selected(self) -> None:
        """Remove the component selected in the DataTable (with backup)."""
        try:
            table = self.query_one("#db-table", DataTable)
            row_key = table.cursor_row
            if row_key is None:
                self.notify(
                    "No component selected.",
                    title="Warning",
                    severity="warning",
                )
                return

            row_data = table.get_row_at(row_key)
            component_name = str(row_data[0]).strip()
            comp_key = self._display_to_component_key(component_name)

            if comp_key is None:
                self.notify(
                    f"Unknown component: {component_name}",
                    title="Warning",
                    severity="warning",
                )
                return

            lifecycle = DBLifecycleManager(self.db_dir)
            lifecycle.remove_component(comp_key, backup=True)
            self.notify(
                f"Removed {component_name} (backup created).",
                title="Success",
            )
            self.reload_db_info()

        except Exception as exc:
            self.notify(str(exc), title="Error", severity="error")

    async def run_cleanup_backups(self) -> None:
        """Clean up old database backups (older than 30 days)."""
        try:
            lifecycle = DBLifecycleManager(self.db_dir)
            removed = lifecycle.cleanup_backups(max_age_days=30)

            if not removed:
                self.notify("No old backups to clean up.", title="Info")
            else:
                self.notify(
                    f"Removed {len(removed)} old backup(s).",
                    title="Success",
                )
            self.reload_db_info()

        except Exception as exc:
            self.notify(str(exc), title="Error", severity="error")

    async def _run_shell_command(self, cmd_str: str, label: str = "") -> None:
        """Execute a shell command asynchronously with progress display.

        Args:
            cmd_str: Shell command string to execute.
            label: Human-readable label for progress display.
        """
        progress = self.query_one("#db-progress", ProgressWidget)
        progress.update(current=0, total=1, step_name=label or cmd_str[:80])

        try:
            proc = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                progress.update(current=1, total=1, step_name=f"{label} complete")
                self.notify(f"{label} completed.", title="Success")
            else:
                error_msg = stderr.decode().strip() if stderr else "Unknown error"
                progress.update(
                    current=0, total=1,
                    step_name=f"{label} failed: {error_msg[:80]}",
                )
                self.notify(
                    f"{label} failed (exit {proc.returncode})",
                    title="Error",
                    severity="error",
                )
        except Exception as exc:
            progress.update(current=0, total=1, step_name=f"Error: {exc}")
            self.notify(str(exc), title="Error", severity="error")
        finally:
            self.reload_db_info()

    @staticmethod
    def _display_to_component_key(display_name: str) -> str | None:
        """Map a DataTable display name back to a component key.

        Args:
            display_name: Human-readable label from the table row.

        Returns:
            Component key string, or None if unrecognized.
        """
        reverse_map = {v: k for k, v in COMPONENT_LABELS.items()}
        if display_name in reverse_map:
            return reverse_map[display_name]
        if display_name.startswith("Host:"):
            host_name = display_name.split(":")[1].strip()
            return f"host:{host_name}"
        return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _setup_table(self) -> None:
        """Configure the DataTable columns (includes Tool, Index, Age, Status)."""
        try:
            table = self.query_one("#db-table", DataTable)
            table.add_columns(
                "Component", "Tool", "Index", "Version", "Age", "Status", "Size",
            )
        except Exception:
            pass

    def _populate_table(self) -> None:
        """Fill the DataTable with current DB info (includes Tool/Index/Age/Status)."""
        try:
            table = self.query_one("#db-table", DataTable)
            table.clear()

            # Build index status lookup from DBIndexer
            indexer = DBIndexer(self.db_dir)
            index_status = indexer.get_index_status()
            index_map: dict[str, dict] = {
                e["component"]: e for e in index_status
            }

            # Build age/status lookup from DBLifecycleManager
            lifecycle = DBLifecycleManager(self.db_dir)
            age_entries = lifecycle.get_db_ages()
            age_map: dict[str, dict] = {
                e["component"]: e for e in age_entries
            }

            # Status label -> display string with indicator
            status_display = {
                "fresh": "Fresh",
                "ok": "OK",
                "stale": "Stale",
                "outdated": "Outdated",
            }

            info = self.load_db_info()

            if info:
                for entry in info:
                    comp_key = entry["component"]
                    label = COMPONENT_LABELS.get(comp_key, comp_key)
                    if comp_key.startswith("host:"):
                        host_name = comp_key.split(":")[1]
                        label = f"Host: {host_name}"

                    # Fetch tool/index info from DBIndexer
                    idx_info = index_map.get(comp_key, {})
                    tool = idx_info.get("tool", "-")
                    indexed = idx_info.get("indexed", False)
                    index_str = "OK" if indexed else "Missing"

                    # Fetch age/status from lifecycle manager
                    age_info = age_map.get(comp_key, {})
                    age_days = age_info.get("age_days", "-")
                    age_str = f"{age_days}d" if isinstance(age_days, int) else "-"
                    status_key = age_info.get("status", "")
                    status_str = status_display.get(status_key, "-")

                    # Size from indexer
                    size_mb = idx_info.get("size_mb", 0)
                    size_str = (
                        f"{size_mb:.0f}MB" if size_mb >= 1
                        else f"{size_mb:.1f}MB" if size_mb > 0
                        else "-"
                    )

                    table.add_row(
                        label, tool, index_str, entry["version"],
                        age_str, status_str, size_str,
                    )

                # Add known components that are NOT installed
                installed_keys = {e["component"] for e in info}
                for comp_key in KNOWN_COMPONENTS:
                    if comp_key not in installed_keys:
                        label = COMPONENT_LABELS.get(comp_key, comp_key)
                        idx_info = index_map.get(comp_key, {})
                        tool = idx_info.get("tool", "-")
                        table.add_row(
                            label, tool, "-", "-", "-", "Not installed", "-",
                        )
            else:
                # No VERSION.json - show all as not installed
                for comp_key in KNOWN_COMPONENTS:
                    label = COMPONENT_LABELS.get(comp_key, comp_key)
                    idx_info = index_map.get(comp_key, {})
                    tool = idx_info.get("tool", "-")
                    indexed = idx_info.get("indexed", False)
                    index_str = "OK" if indexed else "-"
                    table.add_row(
                        label, tool, index_str, "-", "-", "Not installed", "-",
                    )

            # Show warnings for stale/outdated DBs
            self._show_age_warnings(age_entries)
        except Exception:
            pass

    def _show_age_warnings(self, age_entries: list[dict]) -> None:
        """Display warning messages for stale/outdated DB components."""
        warnings: list[str] = []
        for entry in age_entries:
            if entry["status"] == "stale":
                warnings.append(
                    f"[yellow]Warning: {entry['component']}: "
                    f"update recommended ({entry['age_days']} days old)[/yellow]"
                )
            elif entry["status"] == "outdated":
                warnings.append(
                    f"[red]Error: {entry['component']}: "
                    f"update required ({entry['age_days']} days old)[/red]"
                )

        if warnings:
            try:
                label = self.query_one("#disk-usage", Static)
                current_text = str(label.renderable) if hasattr(label, "renderable") else ""
                warning_text = "\n".join(warnings)
                label.update(f"{current_text}\n{warning_text}")
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
