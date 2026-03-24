# @TASK T-DB-LIFECYCLE - Database lifecycle manager for DeepInvirus
# @SPEC docs/planning/04-database-design.md#DB-갱신-전략
# @TEST tests/test_db_lifecycle.py
"""Database lifecycle manager for DeepInvirus.

Tracks DB age, checks for updates, manages backups, and handles removal.

Usage:
    manager = DBLifecycleManager(Path("databases"))
    ages = manager.get_db_ages()
    usage = manager.get_disk_usage()
    manager.backup_component("viral_protein")
    manager.remove_component("taxonomy", backup=True)
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger("db_lifecycle")

# ---------------------------------------------------------------------------
# Component registry: maps VERSION.json key -> directory name
# ---------------------------------------------------------------------------

# @TASK T-DB-LIFECYCLE - Component directory mapping
_COMPONENT_DIR_MAP: dict[str, str] = {
    "viral_protein": "viral_protein",
    "viral_nucleotide": "viral_nucleotide",
    "genomad_db": "genomad_db",
    "taxonomy": "taxonomy",
}

# Maps VERSION.json key -> CLI install component name
_COMPONENT_INSTALL_MAP: dict[str, str] = {
    "viral_protein": "protein",
    "viral_nucleotide": "nucleotide",
    "genomad_db": "genomad",
    "taxonomy": "taxonomy",
}


class DBLifecycleManager:
    """Manages database lifecycle: age tracking, backup, restore, removal.

    Args:
        db_dir: Root database directory (e.g., Path("databases")).
    """

    def __init__(self, db_dir: Path) -> None:
        self.db_dir = Path(db_dir)
        self.version_file = self.db_dir / "VERSION.json"

    # ------------------------------------------------------------------
    # VERSION.json I/O
    # ------------------------------------------------------------------

    def _load_version(self) -> dict[str, Any]:
        """Load VERSION.json or return empty skeleton."""
        if not self.version_file.exists():
            return {}
        try:
            with open(self.version_file) as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_version(self, data: dict[str, Any]) -> None:
        """Persist VERSION.json to disk."""
        data["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        self.version_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.version_file, "w") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_db_ages(self) -> list[dict]:
        """Return age information for each DB component.

        Returns:
            List of dicts with keys: component, version, installed_at,
            age_days, status (fresh/ok/stale/outdated).
            Empty list if VERSION.json is missing or has no databases.
        """
        data = self._load_version()
        databases = data.get("databases", {})
        if not databases:
            return []

        result: list[dict] = []
        today = date.today()

        # Core components
        for comp_key in ("viral_protein", "viral_nucleotide", "genomad_db", "taxonomy"):
            entry = databases.get(comp_key)
            if entry is None:
                continue

            downloaded_at = entry.get("downloaded_at", "")
            version = (
                entry.get("version")
                or entry.get("ncbi_version")
                or entry.get("ictv_version")
                or "-"
            )
            age_days = self._compute_age_days(downloaded_at, today)
            result.append({
                "component": comp_key,
                "version": str(version),
                "installed_at": downloaded_at,
                "age_days": age_days,
                "status": self.get_status_label(age_days),
            })

        # Host genomes
        host_genomes = databases.get("host_genomes", {})
        for host_name, host_info in host_genomes.items():
            downloaded_at = host_info.get("downloaded_at", "")
            version = host_info.get("name", "-")
            age_days = self._compute_age_days(downloaded_at, today)
            result.append({
                "component": f"host:{host_name}",
                "version": str(version),
                "installed_at": downloaded_at,
                "age_days": age_days,
                "status": self.get_status_label(age_days),
            })

        return result

    def check_updates_available(self) -> list[dict]:
        """Check which DB components may need updating (age-based).

        Returns:
            List of dicts with keys: component, current (date),
            age_days, update_recommended (bool).
            update_recommended is True when age >= 90 days.
        """
        ages = self.get_db_ages()
        result: list[dict] = []
        for entry in ages:
            result.append({
                "component": entry["component"],
                "current": entry["installed_at"],
                "age_days": entry["age_days"],
                "update_recommended": entry["age_days"] >= 90,
            })
        return result

    def get_status_label(self, age_days: int) -> str:
        """Return a status label based on age in days.

        Args:
            age_days: Number of days since installation.

        Returns:
            "fresh" (< 30d), "ok" (< 90d), "stale" (< 180d),
            or "outdated" (>= 180d).
        """
        if age_days < 30:
            return "fresh"
        if age_days < 90:
            return "ok"
        if age_days < 180:
            return "stale"
        return "outdated"

    def backup_component(self, component: str) -> Path | None:
        """Create a backup of a DB component.

        Copies the component directory to _backup/{component}_{date}/.

        Args:
            component: Component key (e.g., 'viral_protein', 'host:tmol').

        Returns:
            Path to the backup directory, or None if source does not exist.
        """
        comp_dir = self._resolve_component_dir(component)
        if comp_dir is None or not comp_dir.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = component.replace(":", "_")
        backup_path = self.db_dir / "_backup" / f"{safe_name}_{timestamp}"
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copytree(comp_dir, backup_path)
        logger.info("Backed up %s -> %s", comp_dir, backup_path)
        return backup_path

    def restore_backup(self, component: str, backup_path: Path) -> None:
        """Restore a component from a backup directory.

        Args:
            component: Component key.
            backup_path: Path to the backup directory.

        Raises:
            FileNotFoundError: If backup_path does not exist.
            ValueError: If backup_path is invalid.
        """
        if not backup_path.exists():
            raise FileNotFoundError(
                f"Backup directory does not exist: {backup_path}"
            )

        comp_dir = self._resolve_component_dir(component)
        if comp_dir is None:
            raise ValueError(f"Cannot resolve directory for component: {component}")

        if comp_dir.exists():
            shutil.rmtree(comp_dir)

        shutil.copytree(backup_path, comp_dir)
        logger.info("Restored %s from %s", component, backup_path)

    def remove_component(self, component: str, backup: bool = True) -> None:
        """Remove a DB component.

        Args:
            component: Component key.
            backup: If True, create a backup before removing.
        """
        comp_dir = self._resolve_component_dir(component)

        if backup and comp_dir is not None and comp_dir.exists():
            self.backup_component(component)

        # Remove directory
        if comp_dir is not None and comp_dir.exists():
            shutil.rmtree(comp_dir)
            logger.info("Removed component directory: %s", comp_dir)

        # Update VERSION.json
        data = self._load_version()
        databases = data.get("databases", {})

        if component.startswith("host:"):
            host_name = component.split(":", 1)[1]
            host_genomes = databases.get("host_genomes", {})
            host_genomes.pop(host_name, None)
            if not host_genomes:
                databases.pop("host_genomes", None)
        else:
            databases.pop(component, None)

        if data:
            self._save_version(data)

    def update_component(self, component: str, backup: bool = True) -> str:
        """Generate a shell command to update a DB component.

        Args:
            component: Component key.
            backup: If True, includes backup step.

        Returns:
            Shell command string to execute, or empty string if unknown.
        """
        # Resolve the install component name
        if component.startswith("host:"):
            host_name = component.split(":", 1)[1]
            install_script = Path(__file__).resolve().parent / "install_databases.py"
            cmd = (
                f"{sys.executable} {install_script} "
                f"--db-dir {self.db_dir} "
                f"--components host --host {host_name}"
            )
            return cmd

        install_key = _COMPONENT_INSTALL_MAP.get(component)
        if install_key is None:
            return ""

        install_script = Path(__file__).resolve().parent / "install_databases.py"
        cmd = (
            f"{sys.executable} {install_script} "
            f"--db-dir {self.db_dir} "
            f"--components {install_key}"
        )
        return cmd

    def cleanup_backups(self, max_age_days: int = 30) -> list[Path]:
        """Remove backup directories older than max_age_days.

        Args:
            max_age_days: Maximum age in days for backups to keep.

        Returns:
            List of removed backup directory paths.
        """
        backup_dir = self.db_dir / "_backup"
        if not backup_dir.exists():
            return []

        removed: list[Path] = []
        today = date.today()

        for entry in sorted(backup_dir.iterdir()):
            if not entry.is_dir():
                continue

            # Parse date from directory name: {component}_{YYYYMMDD}_{HHMMSS}
            backup_date = self._parse_backup_date(entry.name)
            if backup_date is None:
                continue

            age_days = (today - backup_date).days
            if age_days > max_age_days:
                shutil.rmtree(entry)
                removed.append(entry)
                logger.info("Removed old backup: %s (age: %d days)", entry, age_days)

        return removed

    def get_disk_usage(self) -> dict:
        """Compute disk usage for the database directory.

        Returns:
            Dict with keys:
                total_gb (float): Total size in GB.
                per_component (dict): Size per component directory in GB.
                backups_gb (float): Size of _backup directory in GB.
        """
        per_component: dict[str, float] = {}

        # Scan known component directories
        for comp_key, dir_name in _COMPONENT_DIR_MAP.items():
            comp_path = self.db_dir / dir_name
            if comp_path.is_dir():
                size_bytes = self._dir_size(comp_path)
                per_component[comp_key] = round(size_bytes / (1024**3), 4)

        # Host genomes
        host_dir = self.db_dir / "host_genomes"
        if host_dir.is_dir():
            for entry in host_dir.iterdir():
                if entry.is_dir() and not entry.name.startswith("_"):
                    size_bytes = self._dir_size(entry)
                    per_component[f"host:{entry.name}"] = round(
                        size_bytes / (1024**3), 4
                    )

        # Backups
        backup_dir = self.db_dir / "_backup"
        backups_bytes = self._dir_size(backup_dir) if backup_dir.is_dir() else 0

        # Total
        total_bytes = self._dir_size(self.db_dir)

        return {
            "total_gb": round(total_bytes / (1024**3), 4),
            "per_component": per_component,
            "backups_gb": round(backups_bytes / (1024**3), 4),
        }

    def get_version_history(self) -> list[dict]:
        """Return update history from VERSION.json (if present).

        Returns:
            List of history entries, or empty list.
        """
        data = self._load_version()
        return data.get("update_history", [])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_component_dir(self, component: str) -> Path | None:
        """Resolve the filesystem directory for a component.

        Args:
            component: Component key (e.g., 'viral_protein', 'host:tmol').

        Returns:
            Path to the component directory, or None if unknown.
        """
        if component.startswith("host:"):
            host_name = component.split(":", 1)[1]
            return self.db_dir / "host_genomes" / host_name

        dir_name = _COMPONENT_DIR_MAP.get(component)
        if dir_name is None:
            return None
        return self.db_dir / dir_name

    @staticmethod
    def _compute_age_days(date_str: str, today: date) -> int:
        """Compute the age in days from a date string.

        Args:
            date_str: ISO date string (YYYY-MM-DD).
            today: Current date.

        Returns:
            Number of days since date_str, or 0 if unparseable.
        """
        if not date_str:
            return 0
        try:
            d = date.fromisoformat(date_str)
            return max(0, (today - d).days)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _parse_backup_date(dir_name: str) -> date | None:
        """Parse the date portion from a backup directory name.

        Expected format: {component}_{YYYYMMDD}_{HHMMSS}

        Args:
            dir_name: Backup directory name.

        Returns:
            date object or None if parsing fails.
        """
        parts = dir_name.rsplit("_", 2)
        if len(parts) < 3:
            return None
        date_part = parts[-2]
        try:
            return datetime.strptime(date_part, "%Y%m%d").date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _dir_size(path: Path) -> int:
        """Compute total size of a directory tree in bytes."""
        if not path.exists():
            return 0
        total = 0
        try:
            for f in path.rglob("*"):
                if f.is_file():
                    try:
                        total += f.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
        return total
