# @TASK T-RAMDISK - RAM disk manager tests
# @SPEC docs/planning/02-trd.md#RAM-disk-work-directory
# @TEST tests/test_ramdisk.py
"""
Tests for RamdiskManager and RAM disk integration in runner/CLI.

Covers:
  - RamdiskManager core operations (create, cleanup, usage, availability)
  - NextflowRunner build_command with use_ramdisk / work_dir options
  - CLI --use-ramdisk / --work-dir options
  - Signal-based cleanup (atexit / SIGTERM)
"""

from __future__ import annotations

import os
import sys
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure bin/ is importable
_BIN_DIR = Path(__file__).resolve().parents[1] / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))


# =========================================================================
# RamdiskManager unit tests
# =========================================================================


class TestRamdiskManagerAvailability:
    """Test /dev/shm availability checks."""

    def test_is_available_on_linux(self):
        """On Linux, /dev/shm should exist and be a directory."""
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager()
        # On a real Linux system, /dev/shm always exists
        if Path("/dev/shm").exists():
            assert mgr.is_available() is True
        else:
            # Non-Linux or restricted env
            assert mgr.is_available() is False

    def test_is_available_returns_bool(self):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager()
        result = mgr.is_available()
        assert isinstance(result, bool)


class TestRamdiskManagerGetRam:
    """Test RAM info methods."""

    def test_get_available_ram_gb_positive(self):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager()
        ram = mgr.get_available_ram_gb()
        assert isinstance(ram, int)
        assert ram > 0

    def test_get_recommended_size_gb_range(self):
        """Recommended size should be between 50 and 300 GB."""
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager()
        rec = mgr.get_recommended_size_gb()
        assert isinstance(rec, int)
        assert 50 <= rec <= 300


class TestRamdiskManagerCreateCleanup:
    """Test RAM disk directory creation and cleanup."""

    @pytest.fixture
    def tmp_mount(self, tmp_path):
        """Use a temp directory as a mock mount point."""
        mount = tmp_path / "deepinvirus_work"
        return mount

    def test_create_makes_directory(self, tmp_mount):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager(mount_point=tmp_mount)
        result = mgr.create()
        assert result == tmp_mount
        assert tmp_mount.is_dir()

    def test_create_idempotent(self, tmp_mount):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager(mount_point=tmp_mount)
        mgr.create()
        mgr.create()  # should not raise
        assert tmp_mount.is_dir()

    def test_cleanup_removes_directory(self, tmp_mount):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager(mount_point=tmp_mount)
        mgr.create()
        # Create some files inside
        (tmp_mount / "test_file.txt").write_text("hello")
        (tmp_mount / "subdir").mkdir()
        (tmp_mount / "subdir" / "nested.txt").write_text("world")

        mgr.cleanup()
        assert not tmp_mount.exists()

    def test_cleanup_nonexistent_no_error(self, tmp_mount):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager(mount_point=tmp_mount)
        # Should not raise even if directory doesn't exist
        mgr.cleanup()

    def test_safe_cleanup_on_error(self, tmp_mount):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager(mount_point=tmp_mount)
        mgr.create()
        (tmp_mount / "data.bin").write_bytes(b"\x00" * 1024)
        mgr.safe_cleanup_on_error()
        assert not tmp_mount.exists()


class TestRamdiskManagerUsage:
    """Test usage reporting."""

    def test_get_usage_structure(self, tmp_path):
        from ramdisk_manager import RamdiskManager

        mount = tmp_path / "deepinvirus_work"
        mgr = RamdiskManager(mount_point=mount)
        mgr.create()

        usage = mgr.get_usage()
        assert isinstance(usage, dict)
        assert "total_gb" in usage
        assert "used_gb" in usage
        assert "free_gb" in usage
        assert "percent" in usage

    def test_get_usage_nonexistent_returns_zeros(self, tmp_path):
        from ramdisk_manager import RamdiskManager

        mount = tmp_path / "nonexistent_work"
        mgr = RamdiskManager(mount_point=mount)

        usage = mgr.get_usage()
        assert usage["total_gb"] == 0
        assert usage["used_gb"] == 0
        assert usage["free_gb"] == 0
        assert usage["percent"] == 0.0


class TestRamdiskManagerCustomSize:
    """Test custom size_gb parameter."""

    def test_custom_size(self):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager(size_gb=100)
        assert mgr.size_gb == 100

    def test_default_size(self):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager()
        assert mgr.size_gb == 200


# =========================================================================
# NextflowRunner integration tests
# =========================================================================


class TestRunnerRamdiskCommand:
    """Test that runner.build_command handles RAM disk options."""

    def test_use_ramdisk_adds_w_option(self):
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/project"))
        params = {
            "reads": "/data/reads",
            "host": "human",
            "assembler": "megahit",
            "search": "fast",
            "outdir": "./results",
            "use_ramdisk": True,
        }

        with patch("tui.runner.RamdiskManager") as MockRM:
            mock_instance = MockRM.return_value
            mock_instance.create.return_value = Path("/dev/shm/deepinvirus_work")
            cmd = runner.build_command(params)

        assert "-w" in cmd
        idx = cmd.index("-w")
        assert cmd[idx + 1] == "/dev/shm/deepinvirus_work"

    def test_no_ramdisk_no_w_option(self):
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/project"))
        params = {
            "reads": "/data/reads",
            "host": "human",
            "assembler": "megahit",
            "search": "fast",
            "outdir": "./results",
        }
        cmd = runner.build_command(params)
        assert "-w" not in cmd

    def test_custom_work_dir_adds_w_option(self):
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/project"))
        params = {
            "reads": "/data/reads",
            "host": "human",
            "assembler": "megahit",
            "search": "fast",
            "outdir": "./results",
            "work_dir": "/tmp/my_custom_work",
        }
        cmd = runner.build_command(params)
        assert "-w" in cmd
        idx = cmd.index("-w")
        assert cmd[idx + 1] == "/tmp/my_custom_work"

    def test_ramdisk_takes_precedence_over_work_dir(self):
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/project"))
        params = {
            "reads": "/data/reads",
            "host": "human",
            "assembler": "megahit",
            "search": "fast",
            "outdir": "./results",
            "use_ramdisk": True,
            "work_dir": "/tmp/should_not_be_used",
        }

        with patch("tui.runner.RamdiskManager") as MockRM:
            mock_instance = MockRM.return_value
            mock_instance.create.return_value = Path("/dev/shm/deepinvirus_work")
            cmd = runner.build_command(params)

        idx = cmd.index("-w")
        assert cmd[idx + 1] == "/dev/shm/deepinvirus_work"


# =========================================================================
# CLI option tests
# =========================================================================


class TestCLIRamdiskOptions:
    """Test CLI --use-ramdisk and --work-dir options."""

    def test_use_ramdisk_option_exists(self):
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert "--use-ramdisk" in result.output

    def test_work_dir_option_exists(self):
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert "--work-dir" in result.output

    def test_use_ramdisk_flag_parsed(self):
        """Ensure --use-ramdisk is a boolean flag that can be passed."""
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        # RamdiskManager is imported inside the run() function via
        # "from ramdisk_manager import RamdiskManager", so we patch
        # at the ramdisk_manager module level.
        with patch("deepinvirus_cli.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            with patch("ramdisk_manager.RamdiskManager") as MockRM:
                mock_instance = MockRM.return_value
                mock_instance.is_available.return_value = True
                mock_instance.create.return_value = Path("/dev/shm/deepinvirus_work")
                mock_instance.cleanup.return_value = None
                mock_instance.get_available_ram_gb.return_value = 200
                mock_instance.register_cleanup.return_value = None
                result = runner.invoke(
                    cli,
                    ["run", "--reads", "/data/test", "--use-ramdisk"],
                )
        # Should not fail with "no such option"
        assert "no such option" not in (result.output or "").lower()

    def test_work_dir_option_parsed(self):
        from click.testing import CliRunner
        from deepinvirus_cli import cli

        runner = CliRunner()
        with patch("deepinvirus_cli.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(
                cli,
                ["run", "--reads", "/data/test", "--work-dir", "/tmp/mywork"],
            )
        assert "no such option" not in (result.output or "").lower()


# =========================================================================
# Signal handler / cleanup tests
# =========================================================================


class TestRamdiskCleanupRegistration:
    """Test that cleanup is properly registered via atexit/signal."""

    def test_register_cleanup_creates_handler(self):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager(mount_point=Path("/tmp/test_cleanup_reg"))
        # register_cleanup should not raise
        mgr.register_cleanup()

    def test_safe_cleanup_on_error_handles_missing_dir(self):
        from ramdisk_manager import RamdiskManager

        mgr = RamdiskManager(mount_point=Path("/tmp/nonexistent_ramdisk_xyz"))
        # Should not raise
        mgr.safe_cleanup_on_error()
