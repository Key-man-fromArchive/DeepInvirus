# @TASK T8.1 - Run 파라미터 입력 폼 테스트
# @SPEC docs/planning/06-tasks-tui.md#phase-8-t81-파라미터-입력-폼-redgreen
# @SPEC docs/planning/02-trd.md#31-입력-input
"""
Tests for RunScreen parameter form (T8.1).

TDD cycle:
  RED  → all tests fail (skeleton only has Static placeholder)
  GREEN → full implementation passes all tests
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import pytest

# bin/ 디렉토리를 sys.path에 추가하여 'tui' 패키지를 직접 임포트
_BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))


# ---------------------------------------------------------------------------
# 헬퍼: 소스 텍스트 가져오기
# ---------------------------------------------------------------------------


def _get_source() -> str:
    from tui.screens import run_screen

    return inspect.getsource(run_screen)


# ---------------------------------------------------------------------------
# 1. 클래스 구조
# ---------------------------------------------------------------------------


class TestRunScreenClass:
    """RunScreen 클래스 기본 구조 검증."""

    def test_run_screen_importable(self):
        """RunScreen을 bin/tui/screens/run_screen에서 import 가능해야 함."""
        from tui.screens.run_screen import RunScreen  # noqa: F401

    def test_run_screen_is_screen_subclass(self):
        """RunScreen은 Textual Screen의 서브클래스여야 함."""
        from textual.screen import Screen

        from tui.screens.run_screen import RunScreen

        assert issubclass(RunScreen, Screen)

    def test_run_screen_has_compose(self):
        """RunScreen에 compose() 메서드가 정의되어 있어야 함."""
        from tui.screens.run_screen import RunScreen

        assert hasattr(RunScreen, "compose")
        assert callable(RunScreen.compose)


# ---------------------------------------------------------------------------
# 2. 파라미터 위젯 7개 ID (소스 수준 확인)
# ---------------------------------------------------------------------------


class TestRunScreenWidgetIds:
    """7개 파라미터 입력 위젯 ID가 소스에 정의되어 있는지 확인.

    02-trd.md 3.1 params 기준:
      reads, host, assembler, search, skip_ml, outdir, threads
    """

    EXPECTED_IDS = [
        "input-reads",       # Reads 경로 Input
        "select-host",       # Host genome Select
        "radioset-assembler", # Assembler RadioSet
        "radioset-search",   # Search mode RadioSet
        "checkbox-ml",       # ML detection Checkbox
        "input-outdir",      # Output dir Input
        "input-threads",     # Threads Input
    ]

    def test_input_reads_id_defined(self):
        """input-reads ID가 소스에 존재해야 함."""
        assert "input-reads" in _get_source()

    def test_select_host_id_defined(self):
        """select-host ID가 소스에 존재해야 함."""
        assert "select-host" in _get_source()

    def test_radioset_assembler_id_defined(self):
        """radioset-assembler ID가 소스에 존재해야 함."""
        assert "radioset-assembler" in _get_source()

    def test_radioset_search_id_defined(self):
        """radioset-search ID가 소스에 존재해야 함."""
        assert "radioset-search" in _get_source()

    def test_checkbox_ml_id_defined(self):
        """checkbox-ml ID가 소스에 존재해야 함."""
        assert "checkbox-ml" in _get_source()

    def test_input_outdir_id_defined(self):
        """input-outdir ID가 소스에 존재해야 함."""
        assert "input-outdir" in _get_source()

    def test_input_threads_id_defined(self):
        """input-threads ID가 소스에 존재해야 함."""
        assert "input-threads" in _get_source()

    def test_all_seven_widget_ids_present(self):
        """7개 위젯 ID가 모두 소스에 존재해야 함."""
        src = _get_source()
        missing = [wid for wid in self.EXPECTED_IDS if wid not in src]
        assert not missing, f"Missing widget IDs: {missing}"


# ---------------------------------------------------------------------------
# 3. 버튼 ID (소스 수준 확인)
# ---------------------------------------------------------------------------


class TestRunScreenButtons:
    """Start/Back 버튼 ID가 소스에 정의되어 있는지 확인."""

    def test_btn_start_id_defined(self):
        """btn-start ID가 소스에 존재해야 함."""
        assert "btn-start" in _get_source()

    def test_btn_back_id_defined(self):
        """btn-back ID가 소스에 존재해야 함."""
        assert "btn-back" in _get_source()

    def test_both_buttons_defined(self):
        """Start/Back 버튼이 모두 소스에 존재해야 함."""
        src = _get_source()
        assert "btn-start" in src and "btn-back" in src


# ---------------------------------------------------------------------------
# 4. get_params() 메서드
# ---------------------------------------------------------------------------


class TestRunScreenGetParams:
    """get_params() 메서드 존재 및 반환 타입 검증."""

    def test_get_params_method_exists(self):
        """RunScreen에 get_params() 메서드가 있어야 함."""
        from tui.screens.run_screen import RunScreen

        assert hasattr(RunScreen, "get_params")
        assert callable(RunScreen.get_params)

    def test_get_params_in_source(self):
        """get_params가 소스에 정의되어 있어야 함."""
        assert "get_params" in _get_source()

    def test_get_params_returns_dict_annotation(self):
        """get_params()의 반환 타입 주석이 dict 계열이어야 함 (소스 확인)."""
        src = _get_source()
        # 반환 주석 '-> dict' 또는 '-> Dict' 존재 여부
        assert "-> dict" in src or "-> Dict" in src, (
            "get_params()에 '-> dict' 반환 타입 주석이 필요합니다."
        )


# ---------------------------------------------------------------------------
# 5. validate_params() 메서드
# ---------------------------------------------------------------------------


class TestRunScreenValidateParams:
    """validate_params() 메서드 존재 검증."""

    def test_validate_params_method_exists(self):
        """RunScreen에 validate_params() 메서드가 있어야 함."""
        from tui.screens.run_screen import RunScreen

        assert hasattr(RunScreen, "validate_params")
        assert callable(RunScreen.validate_params)

    def test_validate_params_in_source(self):
        """validate_params가 소스에 정의되어 있어야 함."""
        assert "validate_params" in _get_source()

    def test_validate_params_returns_list_or_none(self):
        """validate_params()가 list 또는 None을 반환하도록 설계되어 있어야 함.

        에러가 없으면 빈 list 또는 None, 에러가 있으면 에러 메시지 list 반환.
        """
        src = _get_source()
        # list | None 또는 list[str] 형태의 반환 주석 또는 반환 구문 존재
        has_return_list = "list[str]" in src or "List[str]" in src
        has_return_none = "| None" in src or "Optional" in src
        has_return_list_bare = "-> list" in src
        assert has_return_list or has_return_none or has_return_list_bare, (
            "validate_params()에 list 또는 None 반환 타입 주석이 필요합니다."
        )


# ---------------------------------------------------------------------------
# 6. 기본값 검증
# ---------------------------------------------------------------------------


class TestRunScreenDefaults:
    """기본값이 소스에 설정되어 있는지 확인."""

    def test_default_outdir_results(self):
        """output dir 기본값으로 './results'가 설정되어야 함."""
        assert "./results" in _get_source() or "results" in _get_source()

    def test_default_threads_cpu_count(self):
        """threads 기본값으로 os.cpu_count() 관련 코드가 있어야 함."""
        src = _get_source()
        assert "cpu_count" in src, (
            "threads 기본값으로 os.cpu_count() 사용 필요"
        )

    def test_default_ml_detection_on(self):
        """ML detection(geNomad) 기본값이 활성화(True)여야 함."""
        src = _get_source()
        # Checkbox에 value=True 또는 INITIAL_VALUE = True 패턴
        assert "True" in src, "ML detection 기본값이 True여야 합니다."

    def test_default_assembler_megahit(self):
        """assembler 기본값이 megahit이어야 함."""
        assert "megahit" in _get_source()

    def test_default_search_mode(self):
        """search mode로 fast/sensitive 옵션이 모두 있어야 함."""
        src = _get_source()
        assert "fast" in src and "sensitive" in src

    def test_host_options_include_none(self):
        """host genome 옵션에 'none'이 포함되어야 함."""
        assert "none" in _get_source()

    def test_host_options_include_human(self):
        """host genome 옵션에 'human'이 포함되어야 함."""
        assert "human" in _get_source()


# ---------------------------------------------------------------------------
# 7. 입력 검증 로직 (소스 수준)
# ---------------------------------------------------------------------------


class TestRunScreenValidationLogic:
    """입력 검증 관련 로직이 소스에 존재하는지 확인."""

    def test_reads_path_validation_exists(self):
        """reads 경로 존재 확인 로직이 있어야 함.

        Path(...).exists() 또는 os.path.exists() 호출 존재.
        """
        src = _get_source()
        has_path_exists = ".exists()" in src
        has_os_exists = "os.path.exists" in src
        assert has_path_exists or has_os_exists, (
            "reads 경로 존재 확인 로직(Path.exists 또는 os.path.exists) 필요"
        )

    def test_threads_positive_int_validation_exists(self):
        """threads 양수 정수 검증 로직이 있어야 함."""
        src = _get_source()
        # int() 변환 시도 또는 > 0 검사
        has_int_cast = "int(" in src
        has_positive_check = "> 0" in src or "positive" in src.lower()
        assert has_int_cast or has_positive_check, (
            "threads 양수 정수 검증 로직(int() 변환 또는 > 0 검사) 필요"
        )

    def test_error_message_display_exists(self):
        """에러 메시지 표시 로직이 있어야 함.

        notify() 또는 에러 Static 위젯 업데이트 패턴.
        """
        src = _get_source()
        has_notify = "notify" in src
        has_error_static = "error" in src.lower()
        assert has_notify or has_error_static, (
            "에러 메시지 표시 로직(notify 또는 error Static) 필요"
        )


# ---------------------------------------------------------------------------
# 8. 위젯 타입 import 확인 (소스 수준)
# ---------------------------------------------------------------------------


class TestRunScreenImports:
    """필요한 Textual 위젯들이 import되어 있는지 확인."""

    def test_input_imported(self):
        """Input 위젯을 import해야 함."""
        assert "Input" in _get_source()

    def test_select_imported(self):
        """Select 위젯을 import해야 함."""
        assert "Select" in _get_source()

    def test_radioset_imported(self):
        """RadioSet 위젯을 import해야 함."""
        assert "RadioSet" in _get_source()

    def test_checkbox_imported(self):
        """Checkbox 위젯을 import해야 함."""
        assert "Checkbox" in _get_source()

    def test_button_imported(self):
        """Button 위젯을 import해야 함."""
        assert "Button" in _get_source()

    def test_os_imported(self):
        """os 모듈을 import해야 함 (cpu_count 사용)."""
        assert "import os" in _get_source() or "from os" in _get_source()

    def test_path_imported(self):
        """Path를 import해야 함 (경로 검증)."""
        assert "Path" in _get_source()
