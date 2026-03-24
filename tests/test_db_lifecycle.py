# @TASK T-DB-LIFECYCLE - Database lifecycle manager tests
# @SPEC docs/planning/04-database-design.md#DB-갱신-전략
# @TEST tests/test_db_lifecycle.py
"""
Tests for DBLifecycleManager: DB age tracking, status labels, backup/restore,
removal, update command generation, backup cleanup, and disk usage.

Also tests CLI `db` subcommand group integration.

Covers:
  - get_db_ages(): VERSION.json parsing, age_days calculation
  - get_status_label(): fresh/ok/stale/outdated boundary values
  - check_updates_available(): age-based update check
  - backup_component(): backup directory creation
  - restore_backup(): restore from backup
  - remove_component(): file deletion + VERSION.json update
  - update_component(): command string generation
  - cleanup_backups(): old backup removal
  - get_disk_usage(): return value structure
  - get_version_history(): update history from VERSION.json
  - CLI `db status --help` / `db update --help`
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure bin/ is importable
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "bin")
)

from db_lifecycle import DBLifecycleManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def version_data_factory():
    """Factory to create VERSION.json data with configurable dates."""

    def _make(
        *,
        viral_protein_date: str = "2026-03-20",
        viral_nucleotide_date: str = "2026-03-20",
        genomad_date: str = "2026-03-20",
        taxonomy_date: str = "2026-03-20",
        host_date: str = "2026-03-20",
    ) -> dict:
        return {
            "schema_version": "1.0",
            "created_at": "2026-03-20T00:00:00Z",
            "updated_at": "2026-03-20T00:00:00Z",
            "databases": {
                "viral_protein": {
                    "source": "UniRef90 viral subset",
                    "version": "2026_03",
                    "downloaded_at": viral_protein_date,
                    "format": "diamond",
                },
                "viral_nucleotide": {
                    "source": "NCBI RefSeq Viral",
                    "version": "release_202603",
                    "downloaded_at": viral_nucleotide_date,
                    "format": "mmseqs2",
                },
                "genomad_db": {
                    "source": "geNomad",
                    "version": "1.9",
                    "downloaded_at": genomad_date,
                },
                "taxonomy": {
                    "ncbi_version": taxonomy_date,
                    "ictv_version": "VMR_MSL39_v3",
                    "downloaded_at": taxonomy_date,
                },
                "host_genomes": {
                    "tmol": {
                        "host": "tmol",
                        "name": "Tenebrio molitor",
                        "downloaded_at": host_date,
                        "format": "minimap2",
                    }
                },
            },
        }

    return _make


@pytest.fixture
def db_dir(tmp_path: Path, version_data_factory) -> Path:
    """Create a temporary database directory with VERSION.json and files."""
    # Write VERSION.json
    version_data = version_data_factory()
    (tmp_path / "VERSION.json").write_text(
        json.dumps(version_data, indent=2)
    )

    # Create component directories with some files
    vp = tmp_path / "viral_protein"
    vp.mkdir()
    (vp / "uniref90_viral.fasta.gz").write_bytes(b"\x1f\x8b" + b"\x00" * 100)
    (vp / "uniref90_viral.dmnd").write_bytes(b"DMND" + b"\x00" * 200)

    vn = tmp_path / "viral_nucleotide"
    vn.mkdir()
    (vn / "refseq_viral.fna.gz").write_bytes(b"\x1f\x8b" + b"\x00" * 50)

    gd = tmp_path / "genomad_db"
    gd.mkdir()
    (gd / "genomad_db").write_bytes(b"\x00" * 150)

    tx = tmp_path / "taxonomy"
    tx.mkdir()
    (tx / "names.dmp").write_text("1\t|\troot\t|\n")
    (tx / "nodes.dmp").write_text("1\t|\t1\t|\n")

    hg = tmp_path / "host_genomes" / "tmol"
    hg.mkdir(parents=True)
    (hg / "genome.fa.gz").write_bytes(b"\x1f\x8b" + b"\x00" * 80)
    (hg / "genome.mmi").write_bytes(b"\x00" * 400)

    return tmp_path


@pytest.fixture
def manager(db_dir: Path) -> DBLifecycleManager:
    """DBLifecycleManager with a fully populated test DB."""
    return DBLifecycleManager(db_dir)


@pytest.fixture
def db_dir_stale(tmp_path: Path, version_data_factory) -> Path:
    """Create a DB directory with stale (120-day-old) components."""
    old_date = (date.today() - timedelta(days=120)).isoformat()
    version_data = version_data_factory(
        viral_protein_date=old_date,
        viral_nucleotide_date=old_date,
        genomad_date=old_date,
        taxonomy_date=old_date,
        host_date=old_date,
    )
    (tmp_path / "VERSION.json").write_text(
        json.dumps(version_data, indent=2)
    )
    # Create minimal dirs
    for d in ("viral_protein", "viral_nucleotide", "genomad_db", "taxonomy"):
        (tmp_path / d).mkdir()
    (tmp_path / "host_genomes" / "tmol").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def db_dir_outdated(tmp_path: Path, version_data_factory) -> Path:
    """Create a DB directory with outdated (200-day-old) components."""
    old_date = (date.today() - timedelta(days=200)).isoformat()
    version_data = version_data_factory(
        viral_protein_date=old_date,
        viral_nucleotide_date=old_date,
        genomad_date=old_date,
        taxonomy_date=old_date,
        host_date=old_date,
    )
    (tmp_path / "VERSION.json").write_text(
        json.dumps(version_data, indent=2)
    )
    for d in ("viral_protein", "viral_nucleotide", "genomad_db", "taxonomy"):
        (tmp_path / d).mkdir()
    (tmp_path / "host_genomes" / "tmol").mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# get_db_ages() tests
# ---------------------------------------------------------------------------


class TestGetDbAges:
    """Tests for DBLifecycleManager.get_db_ages()."""

    def test_returns_list(self, manager: DBLifecycleManager) -> None:
        """get_db_ages() must return a list."""
        result = manager.get_db_ages()
        assert isinstance(result, list)

    def test_each_entry_has_required_keys(self, manager: DBLifecycleManager) -> None:
        """Each entry must have component, version, installed_at, age_days, status."""
        required_keys = {"component", "version", "installed_at", "age_days", "status"}
        result = manager.get_db_ages()
        assert len(result) > 0
        for entry in result:
            missing = required_keys - set(entry.keys())
            assert not missing, (
                f"Component '{entry.get('component', '?')}' missing keys: {missing}"
            )

    def test_age_days_is_non_negative(self, manager: DBLifecycleManager) -> None:
        """age_days must be >= 0."""
        for entry in manager.get_db_ages():
            assert entry["age_days"] >= 0, (
                f"{entry['component']} has negative age_days: {entry['age_days']}"
            )

    def test_includes_all_components(self, manager: DBLifecycleManager) -> None:
        """Should include viral_protein, viral_nucleotide, genomad_db, taxonomy, host."""
        names = [e["component"] for e in manager.get_db_ages()]
        assert "viral_protein" in names
        assert "viral_nucleotide" in names
        assert "genomad_db" in names
        assert "taxonomy" in names
        # host component
        host_entries = [n for n in names if n.startswith("host:")]
        assert len(host_entries) >= 1

    def test_fresh_status_for_recent_db(self, manager: DBLifecycleManager) -> None:
        """Recently installed DB should have status 'fresh' or 'ok'."""
        result = manager.get_db_ages()
        # Our test data has dates from a few days ago, should be fresh
        for entry in result:
            assert entry["status"] in ("fresh", "ok"), (
                f"{entry['component']} unexpected status: {entry['status']}"
            )

    def test_stale_status(self, db_dir_stale: Path) -> None:
        """120-day-old DB should have status 'stale'."""
        mgr = DBLifecycleManager(db_dir_stale)
        for entry in mgr.get_db_ages():
            assert entry["status"] == "stale", (
                f"{entry['component']}: expected 'stale', got '{entry['status']}' "
                f"(age_days={entry['age_days']})"
            )

    def test_outdated_status(self, db_dir_outdated: Path) -> None:
        """200-day-old DB should have status 'outdated'."""
        mgr = DBLifecycleManager(db_dir_outdated)
        for entry in mgr.get_db_ages():
            assert entry["status"] == "outdated", (
                f"{entry['component']}: expected 'outdated', got '{entry['status']}' "
                f"(age_days={entry['age_days']})"
            )

    def test_empty_version_json_returns_empty(self, tmp_path: Path) -> None:
        """If VERSION.json has no databases, return empty list."""
        (tmp_path / "VERSION.json").write_text(json.dumps({
            "schema_version": "1.0",
            "created_at": "2026-03-20T00:00:00Z",
            "updated_at": "2026-03-20T00:00:00Z",
            "databases": {},
        }))
        mgr = DBLifecycleManager(tmp_path)
        assert mgr.get_db_ages() == []

    def test_no_version_json_returns_empty(self, tmp_path: Path) -> None:
        """If VERSION.json does not exist, return empty list."""
        mgr = DBLifecycleManager(tmp_path)
        assert mgr.get_db_ages() == []


# ---------------------------------------------------------------------------
# get_status_label() tests
# ---------------------------------------------------------------------------


class TestGetStatusLabel:
    """Tests for DBLifecycleManager.get_status_label()."""

    def test_fresh_under_30_days(self, manager: DBLifecycleManager) -> None:
        assert manager.get_status_label(0) == "fresh"
        assert manager.get_status_label(1) == "fresh"
        assert manager.get_status_label(29) == "fresh"

    def test_ok_30_to_89_days(self, manager: DBLifecycleManager) -> None:
        assert manager.get_status_label(30) == "ok"
        assert manager.get_status_label(60) == "ok"
        assert manager.get_status_label(89) == "ok"

    def test_stale_90_to_179_days(self, manager: DBLifecycleManager) -> None:
        assert manager.get_status_label(90) == "stale"
        assert manager.get_status_label(120) == "stale"
        assert manager.get_status_label(179) == "stale"

    def test_outdated_180_plus_days(self, manager: DBLifecycleManager) -> None:
        assert manager.get_status_label(180) == "outdated"
        assert manager.get_status_label(365) == "outdated"
        assert manager.get_status_label(1000) == "outdated"


# ---------------------------------------------------------------------------
# check_updates_available() tests
# ---------------------------------------------------------------------------


class TestCheckUpdatesAvailable:
    """Tests for DBLifecycleManager.check_updates_available()."""

    def test_returns_list(self, manager: DBLifecycleManager) -> None:
        result = manager.check_updates_available()
        assert isinstance(result, list)

    def test_entry_has_required_keys(self, manager: DBLifecycleManager) -> None:
        required_keys = {"component", "current", "age_days", "update_recommended"}
        result = manager.check_updates_available()
        for entry in result:
            missing = required_keys - set(entry.keys())
            assert not missing, (
                f"Component '{entry.get('component', '?')}' missing keys: {missing}"
            )

    def test_stale_db_recommends_update(self, db_dir_stale: Path) -> None:
        """Stale DB (90+ days) should recommend update."""
        mgr = DBLifecycleManager(db_dir_stale)
        result = mgr.check_updates_available()
        for entry in result:
            assert entry["update_recommended"] is True, (
                f"{entry['component']}: stale DB should recommend update"
            )

    def test_fresh_db_no_update(self, manager: DBLifecycleManager) -> None:
        """Fresh DB should not recommend update."""
        result = manager.check_updates_available()
        for entry in result:
            assert entry["update_recommended"] is False, (
                f"{entry['component']}: fresh DB should not recommend update"
            )


# ---------------------------------------------------------------------------
# backup_component() tests
# ---------------------------------------------------------------------------


class TestBackupComponent:
    """Tests for DBLifecycleManager.backup_component()."""

    def test_creates_backup_directory(self, manager: DBLifecycleManager) -> None:
        """backup_component() should create a backup directory."""
        backup_path = manager.backup_component("viral_protein")
        assert backup_path is not None
        assert backup_path.is_dir()

    def test_backup_contains_files(self, manager: DBLifecycleManager) -> None:
        """Backup should contain the same files as the original."""
        backup_path = manager.backup_component("viral_protein")
        backup_files = {f.name for f in backup_path.iterdir() if f.is_file()}
        assert "uniref90_viral.fasta.gz" in backup_files or len(backup_files) > 0

    def test_backup_path_under_backup_dir(self, manager: DBLifecycleManager) -> None:
        """Backup path should be under databases/_backup/."""
        backup_path = manager.backup_component("viral_protein")
        assert "_backup" in str(backup_path)

    def test_backup_nonexistent_returns_none(self, manager: DBLifecycleManager) -> None:
        """Backing up a nonexistent component should return None."""
        result = manager.backup_component("nonexistent_component")
        assert result is None

    def test_backup_host_component(self, manager: DBLifecycleManager) -> None:
        """Backup of host component should work."""
        backup_path = manager.backup_component("host:tmol")
        assert backup_path is not None
        assert backup_path.is_dir()


# ---------------------------------------------------------------------------
# restore_backup() tests
# ---------------------------------------------------------------------------


class TestRestoreBackup:
    """Tests for DBLifecycleManager.restore_backup()."""

    def test_restore_replaces_original(self, manager: DBLifecycleManager) -> None:
        """After backup + remove + restore, original directory should exist."""
        backup_path = manager.backup_component("viral_protein")
        comp_dir = manager.db_dir / "viral_protein"

        # Remove original
        import shutil
        shutil.rmtree(comp_dir)
        assert not comp_dir.exists()

        # Restore
        manager.restore_backup("viral_protein", backup_path)
        assert comp_dir.is_dir()

    def test_restore_nonexistent_backup_raises(self, manager: DBLifecycleManager) -> None:
        """Restoring from a nonexistent path should raise."""
        fake_path = manager.db_dir / "_backup" / "nonexistent"
        with pytest.raises((FileNotFoundError, ValueError)):
            manager.restore_backup("viral_protein", fake_path)


# ---------------------------------------------------------------------------
# remove_component() tests
# ---------------------------------------------------------------------------


class TestRemoveComponent:
    """Tests for DBLifecycleManager.remove_component()."""

    def test_removes_directory(self, manager: DBLifecycleManager) -> None:
        """remove_component() should delete the component directory."""
        manager.remove_component("viral_protein", backup=False)
        assert not (manager.db_dir / "viral_protein").exists()

    def test_removes_from_version_json(self, manager: DBLifecycleManager) -> None:
        """remove_component() should remove entry from VERSION.json."""
        manager.remove_component("viral_protein", backup=False)
        with open(manager.version_file) as f:
            data = json.load(f)
        assert "viral_protein" not in data.get("databases", {})

    def test_remove_with_backup(self, manager: DBLifecycleManager) -> None:
        """remove_component(backup=True) should create backup before removing."""
        manager.remove_component("viral_protein", backup=True)
        assert not (manager.db_dir / "viral_protein").exists()
        # Backup should exist
        backup_dir = manager.db_dir / "_backup"
        assert backup_dir.exists()
        backup_entries = list(backup_dir.iterdir())
        assert len(backup_entries) >= 1

    def test_remove_nonexistent_does_not_crash(self, manager: DBLifecycleManager) -> None:
        """Removing a nonexistent component should not raise."""
        # Should not raise
        manager.remove_component("nonexistent_component", backup=False)

    def test_remove_host_component(self, manager: DBLifecycleManager) -> None:
        """Removing a host component should work."""
        manager.remove_component("host:tmol", backup=False)
        assert not (manager.db_dir / "host_genomes" / "tmol").exists()


# ---------------------------------------------------------------------------
# update_component() tests
# ---------------------------------------------------------------------------


class TestUpdateComponent:
    """Tests for DBLifecycleManager.update_component()."""

    def test_returns_command_string(self, manager: DBLifecycleManager) -> None:
        """update_component() should return a shell command string."""
        cmd = manager.update_component("viral_protein", backup=False)
        assert isinstance(cmd, str)
        assert len(cmd) > 0

    def test_viral_protein_uses_install(self, manager: DBLifecycleManager) -> None:
        """Update command for viral_protein should reference install_databases."""
        cmd = manager.update_component("viral_protein")
        assert "install_databases" in cmd or "protein" in cmd

    def test_taxonomy_update_command(self, manager: DBLifecycleManager) -> None:
        """taxonomy update should produce a valid command."""
        cmd = manager.update_component("taxonomy")
        assert isinstance(cmd, str)
        assert len(cmd) > 0

    def test_unknown_component_returns_empty(self, manager: DBLifecycleManager) -> None:
        """Unknown component should return empty string."""
        cmd = manager.update_component("nonexistent")
        assert cmd == "" or cmd is None


# ---------------------------------------------------------------------------
# cleanup_backups() tests
# ---------------------------------------------------------------------------


class TestCleanupBackups:
    """Tests for DBLifecycleManager.cleanup_backups()."""

    def test_returns_list(self, manager: DBLifecycleManager) -> None:
        result = manager.cleanup_backups()
        assert isinstance(result, list)

    def test_no_backups_returns_empty(self, manager: DBLifecycleManager) -> None:
        """If no backups exist, returns empty list."""
        result = manager.cleanup_backups()
        assert result == []

    def test_removes_old_backups(self, manager: DBLifecycleManager) -> None:
        """Backups older than max_age_days should be removed."""
        # Create an old backup
        backup_dir = manager.db_dir / "_backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        old_backup = backup_dir / "viral_protein_20250101_120000"
        old_backup.mkdir()
        (old_backup / "dummy.txt").write_text("old data")

        # Create a recent backup
        today_str = date.today().strftime("%Y%m%d")
        recent_backup = backup_dir / f"viral_protein_{today_str}_120000"
        recent_backup.mkdir()
        (recent_backup / "dummy.txt").write_text("recent data")

        # Cleanup with max_age_days=30
        removed = manager.cleanup_backups(max_age_days=30)

        # Old backup should be removed
        assert not old_backup.exists()
        assert len(removed) >= 1
        assert old_backup in removed

        # Recent backup should still exist
        assert recent_backup.exists()

    def test_keeps_recent_backups(self, manager: DBLifecycleManager) -> None:
        """Backups newer than max_age_days should be kept."""
        backup_dir = manager.db_dir / "_backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        today_str = date.today().strftime("%Y%m%d")
        recent = backup_dir / f"taxonomy_{today_str}_120000"
        recent.mkdir()
        (recent / "data.txt").write_text("keep me")

        removed = manager.cleanup_backups(max_age_days=30)
        assert recent.exists()
        assert recent not in removed


# ---------------------------------------------------------------------------
# get_disk_usage() tests
# ---------------------------------------------------------------------------


class TestGetDiskUsage:
    """Tests for DBLifecycleManager.get_disk_usage()."""

    def test_returns_dict(self, manager: DBLifecycleManager) -> None:
        result = manager.get_disk_usage()
        assert isinstance(result, dict)

    def test_has_required_keys(self, manager: DBLifecycleManager) -> None:
        required_keys = {"total_gb", "per_component", "backups_gb"}
        result = manager.get_disk_usage()
        missing = required_keys - set(result.keys())
        assert not missing, f"Missing keys: {missing}"

    def test_total_gb_is_non_negative(self, manager: DBLifecycleManager) -> None:
        result = manager.get_disk_usage()
        assert result["total_gb"] >= 0

    def test_per_component_is_dict(self, manager: DBLifecycleManager) -> None:
        result = manager.get_disk_usage()
        assert isinstance(result["per_component"], dict)

    def test_per_component_includes_known_dirs(self, manager: DBLifecycleManager) -> None:
        result = manager.get_disk_usage()
        # At least viral_protein should be there
        assert "viral_protein" in result["per_component"]

    def test_backups_gb_zero_when_no_backups(self, manager: DBLifecycleManager) -> None:
        result = manager.get_disk_usage()
        assert result["backups_gb"] == 0.0


# ---------------------------------------------------------------------------
# get_version_history() tests
# ---------------------------------------------------------------------------


class TestGetVersionHistory:
    """Tests for DBLifecycleManager.get_version_history()."""

    def test_returns_list(self, manager: DBLifecycleManager) -> None:
        result = manager.get_version_history()
        assert isinstance(result, list)

    def test_empty_when_no_history(self, tmp_path: Path) -> None:
        """If VERSION.json has no update_history, return empty list."""
        (tmp_path / "VERSION.json").write_text(json.dumps({
            "schema_version": "1.0",
            "created_at": "2026-03-20T00:00:00Z",
            "updated_at": "2026-03-20T00:00:00Z",
            "databases": {},
        }))
        mgr = DBLifecycleManager(tmp_path)
        assert mgr.get_version_history() == []


# ---------------------------------------------------------------------------
# CLI `db` subcommand tests
# ---------------------------------------------------------------------------


class TestCliDbSubcommand:
    """Tests for CLI `db` subcommand group."""

    def test_db_status_help(self) -> None:
        """``db status --help`` should produce help text without error."""
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["db", "status", "--help"])
        assert result.exit_code == 0
        assert "status" in result.output.lower() or "usage" in result.output.lower()

    def test_db_update_help(self) -> None:
        """``db update --help`` should produce help text without error."""
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["db", "update", "--help"])
        assert result.exit_code == 0
        assert "update" in result.output.lower() or "usage" in result.output.lower()

    def test_db_remove_help(self) -> None:
        """``db remove --help`` should produce help text without error."""
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["db", "remove", "--help"])
        assert result.exit_code == 0

    def test_db_disk_usage_help(self) -> None:
        """``db disk-usage --help`` should produce help text without error."""
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["db", "disk-usage", "--help"])
        assert result.exit_code == 0

    def test_db_cleanup_backups_help(self) -> None:
        """``db cleanup-backups --help`` should produce help text without error."""
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["db", "cleanup-backups", "--help"])
        assert result.exit_code == 0

    def test_db_check_updates_help(self) -> None:
        """``db check-updates --help`` should produce help text without error."""
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["db", "check-updates", "--help"])
        assert result.exit_code == 0

    def test_db_status_runs(self, db_dir: Path) -> None:
        """``db status`` should run and show DB info."""
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["db", "status", "--db-dir", str(db_dir)])
        assert result.exit_code == 0
        assert "viral_protein" in result.output.lower() or "component" in result.output.lower()

    def test_db_disk_usage_runs(self, db_dir: Path) -> None:
        """``db disk-usage`` should run and show usage info."""
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["db", "disk-usage", "--db-dir", str(db_dir)])
        assert result.exit_code == 0
