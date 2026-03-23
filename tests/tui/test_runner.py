# @TASK T8.2 - NextflowRunner 테스트
# @SPEC docs/planning/06-tasks-tui.md#phase-8-t82-실시간-진행-표시-redgreen
"""
Tests for NextflowRunner (T8.2).

TDD cycle:
  RED  -> all tests fail (runner.py does not exist yet)
  GREEN -> implementation passes all tests

Covers:
  - build_command() produces correct Nextflow CLI args
  - parse_progress() matches Nextflow log patterns
  - Initial state (is_running=False)
  - cancel() method existence
  - start() method existence (async)
  - get_elapsed() method existence
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

import pytest

# bin/ 디렉토리를 sys.path에 추가하여 'tui' 패키지를 직접 임포트
_BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_source() -> str:
    from tui import runner

    return inspect.getsource(runner)


# ---------------------------------------------------------------------------
# 1. Import & class structure
# ---------------------------------------------------------------------------


class TestNextflowRunnerStructure:
    """NextflowRunner 클래스 기본 구조 검증."""

    def test_importable(self):
        """NextflowRunner를 bin/tui/runner.py에서 import 가능해야 함."""
        from tui.runner import NextflowRunner  # noqa: F401

    def test_is_running_initial_false(self):
        """is_running 초기값은 False여야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        assert runner.is_running is False

    def test_has_process_attribute(self):
        """process 속성이 존재하고 초기값은 None이어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        assert runner.process is None

    def test_has_steps_completed_attribute(self):
        """steps_completed 속성 초기값은 0이어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        assert runner.steps_completed == 0

    def test_has_steps_total_attribute(self):
        """steps_total 속성 초기값은 0이어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        assert runner.steps_total == 0

    def test_has_current_step_attribute(self):
        """current_step 속성 초기값은 빈 문자열이어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        assert runner.current_step == ""

    def test_has_start_time_attribute(self):
        """start_time 속성 초기값은 0이어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        assert runner.start_time == 0


# ---------------------------------------------------------------------------
# 2. build_command()
# ---------------------------------------------------------------------------


class TestBuildCommand:
    """build_command()가 params dict를 올바른 Nextflow CLI 인자 리스트로 변환."""

    def test_build_command_exists(self):
        """build_command 메서드가 존재해야 함."""
        from tui.runner import NextflowRunner

        assert hasattr(NextflowRunner, "build_command")
        assert callable(NextflowRunner.build_command)

    def test_basic_params(self):
        """기본 파라미터가 nextflow run 명령어에 포함되어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        params = {
            "reads": "/data/reads",
            "host": "human",
            "assembler": "megahit",
            "search": "fast",
            "skip_ml": False,
            "outdir": "./results",
            "threads": 8,
        }
        cmd = runner.build_command(params)

        assert isinstance(cmd, list)
        assert "nextflow" in cmd[0]
        assert "run" in cmd
        assert "main.nf" in " ".join(cmd)

    def test_reads_param_included(self):
        """reads 경로가 --reads 인자로 포함되어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        params = {
            "reads": "/data/sample_reads",
            "host": "human",
            "assembler": "megahit",
            "search": "fast",
            "skip_ml": False,
            "outdir": "./results",
            "threads": 4,
        }
        cmd = runner.build_command(params)
        cmd_str = " ".join(cmd)
        assert "--reads" in cmd_str
        assert "/data/sample_reads" in cmd_str

    def test_host_param_included(self):
        """host가 --host 인자로 포함되어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        params = {
            "reads": "/data/reads",
            "host": "insect",
            "assembler": "megahit",
            "search": "fast",
            "skip_ml": False,
            "outdir": "./results",
            "threads": 4,
        }
        cmd = runner.build_command(params)
        cmd_str = " ".join(cmd)
        assert "--host" in cmd_str
        assert "insect" in cmd_str

    def test_skip_ml_true(self):
        """skip_ml=True일 때 --skip_ml 인자가 포함되어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        params = {
            "reads": "/data/reads",
            "host": "human",
            "assembler": "megahit",
            "search": "fast",
            "skip_ml": True,
            "outdir": "./results",
            "threads": 4,
        }
        cmd = runner.build_command(params)
        cmd_str = " ".join(cmd)
        assert "--skip_ml" in cmd_str

    def test_skip_ml_false(self):
        """skip_ml=False일 때 --skip_ml이 포함되지 않아야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        params = {
            "reads": "/data/reads",
            "host": "human",
            "assembler": "megahit",
            "search": "fast",
            "skip_ml": False,
            "outdir": "./results",
            "threads": 4,
        }
        cmd = runner.build_command(params)
        cmd_str = " ".join(cmd)
        assert "--skip_ml" not in cmd_str

    def test_threads_param(self):
        """threads가 Nextflow -process.cpus 또는 파이프라인 인자로 포함되어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        params = {
            "reads": "/data/reads",
            "host": "human",
            "assembler": "megahit",
            "search": "fast",
            "skip_ml": False,
            "outdir": "./results",
            "threads": 16,
        }
        cmd = runner.build_command(params)
        cmd_str = " ".join(cmd)
        assert "16" in cmd_str

    def test_outdir_param(self):
        """outdir이 --outdir 인자로 포함되어야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        params = {
            "reads": "/data/reads",
            "host": "human",
            "assembler": "megahit",
            "search": "fast",
            "skip_ml": False,
            "outdir": "/output/results",
            "threads": 4,
        }
        cmd = runner.build_command(params)
        cmd_str = " ".join(cmd)
        assert "--outdir" in cmd_str
        assert "/output/results" in cmd_str


# ---------------------------------------------------------------------------
# 3. parse_progress()
# ---------------------------------------------------------------------------


class TestParseProgress:
    """parse_progress()가 Nextflow 로그 패턴을 올바르게 매칭."""

    def test_parse_progress_exists(self):
        """parse_progress 메서드가 존재해야 함."""
        from tui.runner import NextflowRunner

        assert hasattr(NextflowRunner, "parse_progress")
        assert callable(NextflowRunner.parse_progress)

    def test_process_line_pattern(self):
        """'[ab/cd1234] process > FASTP (sample1)' 패턴에서 step_name 추출."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        result = runner.parse_progress(
            "[ab/cd1234] process > FASTP (sample1)"
        )
        completed, total, step_name = result
        assert step_name == "FASTP"

    def test_process_line_complex_name(self):
        """'[3f/a1b2c3] process > DIAMOND_BLASTX (GC_Tm)' 패턴."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        result = runner.parse_progress(
            "[3f/a1b2c3] process > DIAMOND_BLASTX (GC_Tm)"
        )
        _, _, step_name = result
        assert step_name == "DIAMOND_BLASTX"

    def test_steps_done_pattern(self):
        """'5 of 14 steps (36%) done' 패턴에서 (5, 14) 추출."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        result = runner.parse_progress("5 of 14 steps (36%) done")
        completed, total, step_name = result
        assert completed == 5
        assert total == 14

    def test_steps_done_100_percent(self):
        """'14 of 14 steps (100%) done' 패턴."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        result = runner.parse_progress("14 of 14 steps (100%) done")
        completed, total, step_name = result
        assert completed == 14
        assert total == 14

    def test_unrecognized_line(self):
        """매칭되지 않는 라인은 (0, 0, '') 또는 이전 값 유지."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        result = runner.parse_progress("Some random log output")
        completed, total, step_name = result
        assert completed == 0
        assert total == 0
        assert step_name == ""

    def test_returns_tuple_of_three(self):
        """parse_progress는 항상 3-tuple을 반환해야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        result = runner.parse_progress("anything")
        assert isinstance(result, tuple)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# 4. Async methods
# ---------------------------------------------------------------------------


class TestAsyncMethods:
    """비동기 메서드 존재 및 시그니처 확인."""

    def test_start_is_coroutine(self):
        """start()가 코루틴(async)이어야 함."""
        from tui.runner import NextflowRunner

        assert asyncio.iscoroutinefunction(NextflowRunner.start)

    def test_cancel_is_coroutine(self):
        """cancel()이 코루틴(async)이어야 함."""
        from tui.runner import NextflowRunner

        assert asyncio.iscoroutinefunction(NextflowRunner.cancel)

    def test_get_elapsed_exists(self):
        """get_elapsed() 메서드가 존재해야 함."""
        from tui.runner import NextflowRunner

        assert hasattr(NextflowRunner, "get_elapsed")
        assert callable(NextflowRunner.get_elapsed)

    def test_get_elapsed_returns_float(self):
        """get_elapsed()는 float을 반환해야 함."""
        from tui.runner import NextflowRunner

        runner = NextflowRunner(work_dir=Path("/tmp"))
        result = runner.get_elapsed()
        assert isinstance(result, float)
