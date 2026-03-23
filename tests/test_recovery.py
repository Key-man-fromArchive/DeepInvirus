# @TASK T13.1 - Abnormal termination auto-recovery tests
# @SPEC docs/planning/06-tasks-tui.md#recovery
# @TEST tests/test_recovery.py
"""
Tests for the crash recovery feature.

Covers:
  - history_manager: get_interrupted_runs, mark_interrupted, get_resume_info
  - runner: build_command with resume flag
  - app: _check_interrupted_runs method existence
  - cli: --resume option existence
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure bin/ is importable
_BIN_DIR = Path(__file__).resolve().parents[1] / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))


# ---------------------------------------------------------------------------
# history_manager tests
# ---------------------------------------------------------------------------


class TestGetInterruptedRuns:
    """Tests for history_manager.get_interrupted_runs()."""

    def test_returns_running_records(self, tmp_dir: Path):
        """Running status records should be returned as interrupted."""
        import history_manager

        hf = tmp_dir / "history.json"
        # Seed with a running record
        history_manager.record_run(
            run_id="run-001",
            params={"reads": "/data/reads"},
            status="running",
            duration=0,
            output_dir="./results",
            summary={},
            work_dir="/tmp/nf-work",
            history_file=hf,
        )
        interrupted = history_manager.get_interrupted_runs(history_file=hf)
        assert len(interrupted) == 1
        assert interrupted[0]["run_id"] == "run-001"
        assert interrupted[0]["status"] == "running"

    def test_excludes_completed_records(self, tmp_dir: Path):
        """Completed records should NOT appear in interrupted list."""
        import history_manager

        hf = tmp_dir / "history.json"
        history_manager.record_run(
            run_id="run-ok",
            params={"reads": "/data"},
            status="completed",
            duration=120.0,
            output_dir="./results",
            summary={},
            work_dir="/tmp/nf-work",
            history_file=hf,
        )
        interrupted = history_manager.get_interrupted_runs(history_file=hf)
        assert len(interrupted) == 0

    def test_excludes_failed_records(self, tmp_dir: Path):
        """Failed records should NOT appear in interrupted list."""
        import history_manager

        hf = tmp_dir / "history.json"
        history_manager.record_run(
            run_id="run-fail",
            params={"reads": "/data"},
            status="failed",
            duration=30.0,
            output_dir="./results",
            summary={},
            work_dir="/tmp/nf-work",
            history_file=hf,
        )
        interrupted = history_manager.get_interrupted_runs(history_file=hf)
        assert len(interrupted) == 0

    def test_excludes_already_interrupted_records(self, tmp_dir: Path):
        """Records already marked 'interrupted' should NOT appear."""
        import history_manager

        hf = tmp_dir / "history.json"
        history_manager.record_run(
            run_id="run-int",
            params={"reads": "/data"},
            status="interrupted",
            duration=0,
            output_dir="./results",
            summary={},
            work_dir="/tmp/nf-work",
            history_file=hf,
        )
        interrupted = history_manager.get_interrupted_runs(history_file=hf)
        assert len(interrupted) == 0

    def test_empty_history_returns_empty_list(self, tmp_dir: Path):
        """Empty history file should return empty list."""
        import history_manager

        hf = tmp_dir / "history.json"
        interrupted = history_manager.get_interrupted_runs(history_file=hf)
        assert interrupted == []

    def test_multiple_running_records(self, tmp_dir: Path):
        """Multiple running records should all be returned."""
        import history_manager

        hf = tmp_dir / "history.json"
        for i in range(3):
            history_manager.record_run(
                run_id=f"run-{i}",
                params={"reads": f"/data/{i}"},
                status="running",
                duration=0,
                output_dir=f"./results-{i}",
                summary={},
                work_dir=f"/tmp/nf-work-{i}",
                history_file=hf,
            )
        interrupted = history_manager.get_interrupted_runs(history_file=hf)
        assert len(interrupted) == 3


class TestMarkInterrupted:
    """Tests for history_manager.mark_interrupted()."""

    def test_changes_status_to_interrupted(self, tmp_dir: Path):
        """mark_interrupted should change status from running to interrupted."""
        import history_manager

        hf = tmp_dir / "history.json"
        history_manager.record_run(
            run_id="run-x",
            params={"reads": "/data"},
            status="running",
            duration=0,
            output_dir="./results",
            summary={},
            work_dir="/tmp/nf-work",
            history_file=hf,
        )
        history_manager.mark_interrupted("run-x", history_file=hf)
        record = history_manager.get_run("run-x", history_file=hf)
        assert record is not None
        assert record["status"] == "interrupted"

    def test_after_marking_not_in_interrupted_list(self, tmp_dir: Path):
        """After mark_interrupted, get_interrupted_runs should exclude it."""
        import history_manager

        hf = tmp_dir / "history.json"
        history_manager.record_run(
            run_id="run-y",
            params={"reads": "/data"},
            status="running",
            duration=0,
            output_dir="./results",
            summary={},
            work_dir="/tmp/nf-work",
            history_file=hf,
        )
        history_manager.mark_interrupted("run-y", history_file=hf)
        interrupted = history_manager.get_interrupted_runs(history_file=hf)
        assert len(interrupted) == 0


class TestGetResumeInfo:
    """Tests for history_manager.get_resume_info()."""

    def test_returns_params_and_work_dir(self, tmp_dir: Path):
        """get_resume_info should return params, output_dir, work_dir."""
        import history_manager

        hf = tmp_dir / "history.json"
        params = {"reads": "/data/reads", "host": "human", "outdir": "./results"}
        history_manager.record_run(
            run_id="run-res",
            params=params,
            status="running",
            duration=0,
            output_dir="./results",
            summary={},
            work_dir="/tmp/nf-work-res",
            history_file=hf,
        )
        info = history_manager.get_resume_info("run-res", history_file=hf)
        assert info is not None
        assert info["params"] == params
        assert info["output_dir"] == "./results"
        assert info["work_dir"] == "/tmp/nf-work-res"

    def test_returns_none_for_nonexistent_run(self, tmp_dir: Path):
        """get_resume_info should return None for unknown run_id."""
        import history_manager

        hf = tmp_dir / "history.json"
        info = history_manager.get_resume_info("nonexistent", history_file=hf)
        assert info is None


class TestRecordRunWorkDir:
    """Test that record_run now stores work_dir field."""

    def test_work_dir_stored_in_record(self, tmp_dir: Path):
        """record_run with work_dir should persist the field."""
        import history_manager

        hf = tmp_dir / "history.json"
        history_manager.record_run(
            run_id="run-wd",
            params={"reads": "/data"},
            status="running",
            duration=0,
            output_dir="./results",
            summary={},
            work_dir="/tmp/nf-work-wd",
            history_file=hf,
        )
        record = history_manager.get_run("run-wd", history_file=hf)
        assert record is not None
        assert record["work_dir"] == "/tmp/nf-work-wd"


class TestUpdateRunStatus:
    """Test history_manager.update_run_status()."""

    def test_update_to_completed(self, tmp_dir: Path):
        """update_run_status should change status and set duration."""
        import history_manager

        hf = tmp_dir / "history.json"
        history_manager.record_run(
            run_id="run-upd",
            params={"reads": "/data"},
            status="running",
            duration=0,
            output_dir="./results",
            summary={},
            work_dir="/tmp/nf-work",
            history_file=hf,
        )
        history_manager.update_run_status(
            "run-upd", status="completed", duration=123.4, history_file=hf
        )
        record = history_manager.get_run("run-upd", history_file=hf)
        assert record["status"] == "completed"
        assert record["duration"] == 123.4


# ---------------------------------------------------------------------------
# runner tests
# ---------------------------------------------------------------------------


class TestRunnerBuildCommandResume:
    """Tests for NextflowRunner.build_command with resume flag."""

    def test_resume_true_includes_flag(self):
        """build_command(resume=True) should include -resume in the command."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/project"))
        params = {"reads": "/data/reads", "host": "human", "outdir": "./results"}
        cmd = runner.build_command(params, resume=True)
        assert "-resume" in cmd

    def test_resume_false_excludes_flag(self):
        """build_command(resume=False) should NOT include -resume."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/project"))
        params = {"reads": "/data/reads", "host": "human", "outdir": "./results"}
        cmd = runner.build_command(params, resume=False)
        assert "-resume" not in cmd

    def test_resume_default_is_false(self):
        """build_command() default should NOT include -resume."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/project"))
        params = {"reads": "/data/reads", "host": "human", "outdir": "./results"}
        cmd = runner.build_command(params)
        assert "-resume" not in cmd


class TestRunnerGetWorkDir:
    """Tests for NextflowRunner._get_work_dir()."""

    def test_returns_work_dir_path(self):
        """_get_work_dir should return a Path under the project root."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/project"))
        params = {"outdir": "./results"}
        work_dir = runner._get_work_dir(params)
        assert isinstance(work_dir, Path)
        assert "work" in str(work_dir)


# ---------------------------------------------------------------------------
# app.py tests
# ---------------------------------------------------------------------------


class TestAppCheckInterruptedRuns:
    """Test that DeepInVirusApp has _check_interrupted_runs method."""

    def test_method_exists(self):
        """DeepInVirusApp should have _check_interrupted_runs method."""
        from tui.app import DeepInVirusApp

        assert hasattr(DeepInVirusApp, "_check_interrupted_runs")
        assert callable(getattr(DeepInVirusApp, "_check_interrupted_runs"))


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLIResumeOption:
    """Test that the CLI run command has --resume option."""

    def test_resume_flag_exists(self):
        """CLI 'run' command should have a --resume flag."""
        from click.testing import CliRunner

        # Import is done at module level via sys.path
        import deepinvirus_cli

        runner = CliRunner()
        result = runner.invoke(deepinvirus_cli.run, ["--help"])
        assert "--resume" in result.output
