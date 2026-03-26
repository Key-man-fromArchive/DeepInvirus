"""Tests for database management CLI scripts (install_databases.py, update_databases.py).

# @TASK T6.2 - DB management CLI tests
# @SPEC docs/planning/02-trd.md#7-DB-관리
# @TEST tests/test_db_cli.py

Tests:
1. --help flag produces usage text without error
2. --dry-run output contains expected plan messages
3. VERSION.json schema validation
4. Component selection logic (all vs individual)
5. Argument parsing correctness
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BIN_DIR = PROJECT_ROOT / "bin"
INSTALL_SCRIPT = BIN_DIR / "install_databases.py"
UPDATE_SCRIPT = BIN_DIR / "update_databases.py"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run_script(script: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a Python script as a subprocess.

    Args:
        script: Path to the Python script.
        args: Command-line arguments to pass.

    Returns:
        CompletedProcess with stdout/stderr captured.
    """
    return subprocess.run(
        [sys.executable, str(script)] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---------------------------------------------------------------------------
# Test: --help flag
# ---------------------------------------------------------------------------
class TestHelpFlag:
    """Tests that --help produces usage information without errors."""

    @pytest.mark.unit
    def test_install_databases_help(self) -> None:
        """install_databases.py --help should exit 0 and show usage."""
        result = _run_script(INSTALL_SCRIPT, ["--help"])
        assert result.returncode == 0, f"Exit code: {result.returncode}\nstderr: {result.stderr}"
        assert "usage:" in result.stdout.lower() or "install" in result.stdout.lower(), (
            "Help output must contain usage information"
        )

    @pytest.mark.unit
    def test_update_databases_help(self) -> None:
        """update_databases.py --help should exit 0 and show usage."""
        result = _run_script(UPDATE_SCRIPT, ["--help"])
        assert result.returncode == 0, f"Exit code: {result.returncode}\nstderr: {result.stderr}"
        assert "usage:" in result.stdout.lower() or "update" in result.stdout.lower(), (
            "Help output must contain usage information"
        )


# ---------------------------------------------------------------------------
# Test: --dry-run output
# ---------------------------------------------------------------------------
class TestDryRun:
    """Tests that --dry-run mode prints planned actions without executing."""

    @pytest.mark.unit
    def test_install_dry_run_outputs_plan(self) -> None:
        """install_databases.py --dry-run should print installation plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run_script(INSTALL_SCRIPT, [
                "--db-dir", tmpdir,
                "--dry-run",
                "--components", "taxonomy",
            ])
            # dry-run should succeed (exit 0)
            assert result.returncode == 0, f"Exit code: {result.returncode}\nstderr: {result.stderr}"
            # Should mention DRY-RUN in output (goes to stderr via logging)
            combined = result.stdout + result.stderr
            assert "DRY-RUN" in combined.upper() or "dry" in combined.lower(), (
                "Dry-run output must indicate it is a plan-only run"
            )

    @pytest.mark.unit
    def test_install_dry_run_does_not_create_files(self) -> None:
        """install_databases.py --dry-run must not create VERSION.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _run_script(INSTALL_SCRIPT, [
                "--db-dir", tmpdir,
                "--dry-run",
                "--components", "taxonomy",
            ])
            version_file = Path(tmpdir) / "VERSION.json"
            assert not version_file.exists(), (
                "VERSION.json must not be created during dry-run"
            )


# ---------------------------------------------------------------------------
# Test: VERSION.json schema validation
# ---------------------------------------------------------------------------
class TestVersionJsonSchema:
    """Tests that VERSION.json follows the expected schema."""

    @pytest.fixture
    def sample_version_json(self) -> dict:
        """Create a sample VERSION.json conforming to the spec.

        Returns:
            Dictionary matching the VERSION.json schema.
        """
        return {
            "schema_version": "1.0",
            "created_at": "2026-03-23T12:00:00Z",
            "updated_at": "2026-03-23T12:00:00Z",
            "databases": {
                "viral_protein": {
                    "source": "UniRef90 viral subset",
                    "version": "2026_03",
                    "downloaded_at": "2026-03-23",
                },
                "taxonomy": {
                    "ncbi_version": "2026-03-23",
                    "ictv_version": "VMR_MSL39_v3",
                    "downloaded_at": "2026-03-23",
                },
            },
        }

    @pytest.mark.unit
    def test_version_json_has_required_keys(self, sample_version_json: dict) -> None:
        """VERSION.json must have schema_version, created_at, updated_at, databases."""
        required_keys = {"schema_version", "created_at", "updated_at", "databases"}
        assert required_keys.issubset(sample_version_json.keys()), (
            f"Missing keys: {required_keys - sample_version_json.keys()}"
        )

    @pytest.mark.unit
    def test_version_json_schema_version_is_string(self, sample_version_json: dict) -> None:
        """schema_version must be a string."""
        assert isinstance(sample_version_json["schema_version"], str)

    @pytest.mark.unit
    def test_version_json_databases_is_dict(self, sample_version_json: dict) -> None:
        """databases field must be a dictionary."""
        assert isinstance(sample_version_json["databases"], dict)

    @pytest.mark.unit
    def test_version_json_database_entries_have_downloaded_at(
        self, sample_version_json: dict
    ) -> None:
        """Each database entry should have a downloaded_at field."""
        for db_name, db_meta in sample_version_json["databases"].items():
            assert "downloaded_at" in db_meta, (
                f"Database '{db_name}' missing 'downloaded_at' field"
            )

    @pytest.mark.unit
    def test_version_json_roundtrip(self, tmp_dir: Path, sample_version_json: dict) -> None:
        """VERSION.json should survive a write/read roundtrip."""
        vfile = tmp_dir / "VERSION.json"
        with open(vfile, "w") as fh:
            json.dump(sample_version_json, fh, indent=2)
        with open(vfile) as fh:
            loaded = json.load(fh)
        assert loaded == sample_version_json


# ---------------------------------------------------------------------------
# Test: Component selection logic
# ---------------------------------------------------------------------------
class TestComponentSelection:
    """Tests for the component resolution logic in install_databases.py."""

    @pytest.mark.unit
    def test_resolve_all_components(self) -> None:
        """'all' should expand to the full list of components."""
        # Import the function directly
        sys.path.insert(0, str(BIN_DIR))
        try:
            from install_databases import _resolve_components
            result = _resolve_components("all")
            expected = ["protein", "nucleotide", "genomad", "taxonomy", "host", "exclusion"]
            assert result == expected, f"Expected {expected}, got {result}"
        finally:
            sys.path.pop(0)

    @pytest.mark.unit
    def test_resolve_single_component(self) -> None:
        """A single component name should return a list with one element."""
        sys.path.insert(0, str(BIN_DIR))
        try:
            from install_databases import _resolve_components
            result = _resolve_components("taxonomy")
            assert result == ["taxonomy"]
        finally:
            sys.path.pop(0)

    @pytest.mark.unit
    def test_resolve_multiple_components(self) -> None:
        """Comma-separated components should be split correctly."""
        sys.path.insert(0, str(BIN_DIR))
        try:
            from install_databases import _resolve_components
            result = _resolve_components("protein,taxonomy")
            assert result == ["protein", "taxonomy"]
        finally:
            sys.path.pop(0)

    @pytest.mark.unit
    def test_resolve_components_with_spaces(self) -> None:
        """Comma-separated components with spaces should be trimmed."""
        sys.path.insert(0, str(BIN_DIR))
        try:
            from install_databases import _resolve_components
            result = _resolve_components("protein , taxonomy")
            assert result == ["protein", "taxonomy"]
        finally:
            sys.path.pop(0)


# ---------------------------------------------------------------------------
# Test: Argument parsing
# ---------------------------------------------------------------------------
class TestArgumentParsing:
    """Tests for CLI argument parsing correctness."""

    @pytest.mark.unit
    def test_install_requires_db_dir(self) -> None:
        """install_databases.py without --db-dir should fail."""
        result = _run_script(INSTALL_SCRIPT, [])
        assert result.returncode != 0, (
            "Should fail without required --db-dir argument"
        )

    @pytest.mark.unit
    def test_update_requires_db_dir(self) -> None:
        """update_databases.py without --db-dir should fail."""
        result = _run_script(UPDATE_SCRIPT, [])
        assert result.returncode != 0, (
            "Should fail without required --db-dir argument"
        )

    @pytest.mark.unit
    def test_update_requires_component(self) -> None:
        """update_databases.py without --component should fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = _run_script(UPDATE_SCRIPT, ["--db-dir", tmpdir])
            assert result.returncode != 0, (
                "Should fail without required --component argument"
            )

    @pytest.mark.unit
    def test_install_accepts_valid_host(self) -> None:
        """install_databases.py should accept valid --host values."""
        result = _run_script(INSTALL_SCRIPT, [
            "--db-dir", "/tmp/test_db",
            "--dry-run",
            "--host", "mouse",
            "--components", "host",
        ])
        assert result.returncode == 0, (
            f"Should accept --host mouse. stderr: {result.stderr}"
        )
