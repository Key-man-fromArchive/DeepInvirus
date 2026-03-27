# @TASK T12.1 - CLI entrypoint tests
# @SPEC docs/planning/06-tasks-tui.md#phase-12-t121-cli-엔트리포인트-redgreen
# @TEST tests/test_cli.py
"""
Tests for the Click-based CLI entrypoint (bin/deepinvirus_cli.py).

Verifies:
- CLI module is importable
- `--help` shows subcommand list
- Each subcommand `--help` exits 0
- run subcommand has the expected options
- TUI mode is triggered when no subcommand is given
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
CLI_SCRIPT = BIN_DIR / "deepinvirus_cli.py"


class TestCLIImport:
    """Verify the CLI module can be imported."""

    def test_cli_script_exists(self):
        """deepinvirus_cli.py must exist in bin/."""
        assert CLI_SCRIPT.exists(), f"CLI script not found: {CLI_SCRIPT}"

    def test_cli_module_importable(self):
        """The cli group should be importable."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from deepinvirus_cli import cli  # noqa: F401
        finally:
            sys.path[:] = original_path

    def test_cli_is_click_group(self):
        """cli must be a click.Group instance."""
        import click

        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from deepinvirus_cli import cli

            assert isinstance(cli, click.Group)
        finally:
            sys.path[:] = original_path


class TestCLIHelp:
    """Verify --help output for main CLI and each subcommand."""

    def test_main_help(self):
        """deepinvirus_cli.py --help should exit 0 and list subcommands."""
        result = subprocess.run(
            [sys.executable, str(CLI_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"--help failed: {result.stderr}"
        output = result.stdout.lower()
        # All subcommands should be listed
        for cmd in ("run", "install-db", "update-db", "add-host", "list-hosts", "config", "history"):
            assert cmd in output, f"Subcommand '{cmd}' not found in --help output"

    @pytest.mark.parametrize(
        "subcommand",
        ["run", "install-db", "update-db", "add-host", "list-hosts", "config", "history"],
    )
    def test_subcommand_help(self, subcommand):
        """Each subcommand --help should exit 0."""
        result = subprocess.run(
            [sys.executable, str(CLI_SCRIPT), subcommand, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"{subcommand} --help failed (exit {result.returncode}): {result.stderr}"
        )


class TestRunSubcommandOptions:
    """Verify 'run' subcommand has the expected options."""

    def test_run_help_contains_options(self):
        """run --help should list --reads, --host, --outdir, --assembler, etc."""
        result = subprocess.run(
            [sys.executable, str(CLI_SCRIPT), "run", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        output = result.stdout.lower()
        for opt in ("--reads", "--host", "--outdir", "--assembler", "--search", "--skip-ml", "--threads"):
            assert opt in output, f"Option '{opt}' not found in 'run --help' output"

    def test_run_assembler_choices(self):
        """--assembler should accept megahit and metaspades."""
        result = subprocess.run(
            [sys.executable, str(CLI_SCRIPT), "run", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.lower()
        assert "megahit" in output
        assert "metaspades" in output

    def test_run_search_choices(self):
        """--search should accept fast, sensitive, and very-sensitive."""
        result = subprocess.run(
            [sys.executable, str(CLI_SCRIPT), "run", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.lower()
        assert "fast" in output
        assert "sensitive" in output
        assert "very-sensitive" in output


class TestInstallDbOptions:
    """Verify 'install-db' subcommand has expected options."""

    def test_install_db_help_options(self):
        """install-db --help should list --db-dir, --components, --host, --dry-run."""
        result = subprocess.run(
            [sys.executable, str(CLI_SCRIPT), "install-db", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        output = result.stdout.lower()
        for opt in ("--db-dir", "--components", "--host", "--dry-run"):
            assert opt in output, f"Option '{opt}' not in install-db --help"


class TestUpdateDbOptions:
    """Verify 'update-db' subcommand has expected options."""

    def test_update_db_help_options(self):
        """update-db --help should list --db-dir, --component."""
        result = subprocess.run(
            [sys.executable, str(CLI_SCRIPT), "update-db", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        output = result.stdout.lower()
        for opt in ("--db-dir", "--component"):
            assert opt in output, f"Option '{opt}' not in update-db --help"


class TestAddHostOptions:
    """Verify 'add-host' subcommand has expected options."""

    def test_add_host_help_options(self):
        """add-host --help should list --name, --fasta, --db-dir."""
        result = subprocess.run(
            [sys.executable, str(CLI_SCRIPT), "add-host", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        output = result.stdout.lower()
        for opt in ("--name", "--fasta", "--db-dir"):
            assert opt in output, f"Option '{opt}' not in add-host --help"
