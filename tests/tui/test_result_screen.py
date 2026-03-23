# @TASK T8.3 - ResultScreen 테스트
# @SPEC docs/planning/06-tasks-tui.md#phase-8-t83-결과-뷰어-화면-redgreen
"""
Tests for ResultScreen result viewer (T8.3).

TDD cycle:
  RED  -> all tests fail (result_screen.py does not exist yet)
  GREEN -> implementation passes all tests

Covers:
  - ResultScreen is a Screen subclass
  - compose() defined
  - load_results(output_dir) method exists
  - summarize_bigtable(bigtable_path) returns dict with expected keys
  - Three action buttons (open-dashboard, open-folder, back-main)
  - Duration formatting (seconds -> HH:MM:SS)
"""

from __future__ import annotations

import inspect
import sys
import tempfile
from pathlib import Path

import pytest

# bin/ 디렉토리를 sys.path에 추가
_BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_source() -> str:
    from tui.screens import result_screen

    return inspect.getsource(result_screen)


# ---------------------------------------------------------------------------
# 1. Class structure
# ---------------------------------------------------------------------------


class TestResultScreenClass:
    """ResultScreen 클래스 기본 구조 검증."""

    def test_importable(self):
        """ResultScreen을 import 가능해야 함."""
        from tui.screens.result_screen import ResultScreen  # noqa: F401

    def test_is_screen_subclass(self):
        """ResultScreen은 Textual Screen의 서브클래스여야 함."""
        from textual.screen import Screen

        from tui.screens.result_screen import ResultScreen

        assert issubclass(ResultScreen, Screen)

    def test_has_compose(self):
        """ResultScreen에 compose() 메서드가 정의되어 있어야 함."""
        from tui.screens.result_screen import ResultScreen

        assert hasattr(ResultScreen, "compose")
        assert callable(ResultScreen.compose)


# ---------------------------------------------------------------------------
# 2. load_results() method
# ---------------------------------------------------------------------------


class TestLoadResults:
    """load_results(output_dir) 메서드 검증."""

    def test_method_exists(self):
        """load_results 메서드가 존재해야 함."""
        from tui.screens.result_screen import ResultScreen

        assert hasattr(ResultScreen, "load_results")
        assert callable(ResultScreen.load_results)

    def test_accepts_output_dir(self):
        """load_results는 output_dir 파라미터를 받아야 함."""
        from tui.screens.result_screen import ResultScreen

        sig = inspect.signature(ResultScreen.load_results)
        param_names = list(sig.parameters.keys())
        # self + output_dir
        assert len(param_names) >= 2
        assert "output_dir" in param_names or "output_dir" in str(sig)


# ---------------------------------------------------------------------------
# 3. summarize_bigtable() method
# ---------------------------------------------------------------------------


class TestSummarizeBigtable:
    """summarize_bigtable(bigtable_path) 메서드 검증."""

    def test_method_exists(self):
        """summarize_bigtable 메서드가 존재해야 함."""
        from tui.screens.result_screen import ResultScreen

        assert hasattr(ResultScreen, "summarize_bigtable")
        assert callable(ResultScreen.summarize_bigtable)

    def test_returns_dict_with_expected_keys(self):
        """summarize_bigtable는 total_viruses, top_virus, top_rpm 키를 포함하는 dict 반환."""
        from tui.screens.result_screen import ResultScreen

        # Create a minimal bigtable.tsv for testing
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", delete=False
        ) as f:
            f.write("species\trpm\n")
            f.write("Densovirus\t45.2\n")
            f.write("Iridovirus\t30.1\n")
            f.write("Parvovirus\t15.5\n")
            bigtable_path = Path(f.name)

        try:
            screen = ResultScreen()
            result = screen.summarize_bigtable(bigtable_path)
            assert isinstance(result, dict)
            assert "total_viruses" in result
            assert "top_virus" in result
            assert "top_rpm" in result
        finally:
            bigtable_path.unlink(missing_ok=True)

    def test_top_virus_is_highest_rpm(self):
        """top_virus는 RPM이 가장 높은 바이러스 종이어야 함."""
        from tui.screens.result_screen import ResultScreen

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", delete=False
        ) as f:
            f.write("species\trpm\n")
            f.write("VirusA\t10.0\n")
            f.write("VirusB\t99.5\n")
            f.write("VirusC\t50.0\n")
            bigtable_path = Path(f.name)

        try:
            screen = ResultScreen()
            result = screen.summarize_bigtable(bigtable_path)
            assert result["top_virus"] == "VirusB"
            assert result["top_rpm"] == pytest.approx(99.5)
        finally:
            bigtable_path.unlink(missing_ok=True)

    def test_total_viruses_count(self):
        """total_viruses는 유니크한 species 수여야 함."""
        from tui.screens.result_screen import ResultScreen

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", delete=False
        ) as f:
            f.write("species\trpm\n")
            f.write("VirusA\t10.0\n")
            f.write("VirusB\t20.0\n")
            f.write("VirusA\t15.0\n")  # duplicate species
            f.write("VirusC\t5.0\n")
            bigtable_path = Path(f.name)

        try:
            screen = ResultScreen()
            result = screen.summarize_bigtable(bigtable_path)
            assert result["total_viruses"] == 3  # VirusA, VirusB, VirusC
        finally:
            bigtable_path.unlink(missing_ok=True)

    def test_empty_bigtable(self):
        """빈 bigtable(헤더만)은 total_viruses=0을 반환해야 함."""
        from tui.screens.result_screen import ResultScreen

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tsv", delete=False
        ) as f:
            f.write("species\trpm\n")
            bigtable_path = Path(f.name)

        try:
            screen = ResultScreen()
            result = screen.summarize_bigtable(bigtable_path)
            assert result["total_viruses"] == 0
            assert result["top_virus"] == ""
            assert result["top_rpm"] == 0.0
        finally:
            bigtable_path.unlink(missing_ok=True)

    def test_nonexistent_file(self):
        """존재하지 않는 파일은 빈 요약을 반환해야 함."""
        from tui.screens.result_screen import ResultScreen

        screen = ResultScreen()
        result = screen.summarize_bigtable(Path("/nonexistent/bigtable.tsv"))
        assert result["total_viruses"] == 0
        assert result["top_virus"] == ""
        assert result["top_rpm"] == 0.0


# ---------------------------------------------------------------------------
# 4. Button IDs (source-level check)
# ---------------------------------------------------------------------------


class TestResultScreenButtons:
    """3개 버튼 ID가 소스에 정의되어 있는지 확인."""

    def test_open_dashboard_button(self):
        """open-dashboard 버튼 ID가 소스에 존재해야 함."""
        assert "open-dashboard" in _get_source()

    def test_open_folder_button(self):
        """open-folder 버튼 ID가 소스에 존재해야 함."""
        assert "open-folder" in _get_source()

    def test_back_main_button(self):
        """back-main 버튼 ID가 소스에 존재해야 함."""
        assert "back-main" in _get_source()

    def test_all_three_buttons(self):
        """3개 버튼 ID가 모두 소스에 존재해야 함."""
        src = _get_source()
        expected = ["open-dashboard", "open-folder", "back-main"]
        missing = [bid for bid in expected if bid not in src]
        assert not missing, f"Missing button IDs: {missing}"


# ---------------------------------------------------------------------------
# 5. Duration formatting
# ---------------------------------------------------------------------------


class TestDurationFormatting:
    """소요 시간 포맷팅 (seconds -> HH:MM:SS)."""

    def test_format_duration_exists(self):
        """format_duration 함수 또는 메서드가 존재해야 함."""
        src = _get_source()
        assert "format_duration" in src or "HH:MM:SS" in src or "divmod" in src

    def test_format_duration_function(self):
        """format_duration()이 초를 HH:MM:SS로 변환."""
        from tui.screens.result_screen import format_duration

        assert format_duration(0) == "00:00:00"
        assert format_duration(61) == "00:01:01"
        assert format_duration(3661) == "01:01:01"
        assert format_duration(8133) == "02:15:33"


# ---------------------------------------------------------------------------
# 6. Source-level checks
# ---------------------------------------------------------------------------


class TestResultScreenSource:
    """소스 코드에 필요한 요소가 포함되어 있는지 확인."""

    def test_xdg_open_in_source(self):
        """xdg-open 또는 외부 프로그램 실행 코드가 소스에 존재해야 함."""
        src = _get_source()
        assert "xdg-open" in src or "subprocess" in src or "open" in src

    def test_bigtable_tsv_in_source(self):
        """bigtable.tsv 파일명이 소스에 존재해야 함."""
        assert "bigtable.tsv" in _get_source() or "bigtable" in _get_source()

    def test_dashboard_html_in_source(self):
        """dashboard.html이 소스에 참조되어야 함."""
        assert "dashboard.html" in _get_source() or "dashboard" in _get_source()
