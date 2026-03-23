# @TASK T7.4 - 메인 화면 구현 테스트
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t74-메인-화면-구현-redgreen
"""
Tests for MainScreen and DeepInVirusApp (T7.4).

TDD RED cycle: all tests must fail before implementation.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest
from textual.screen import Screen
from textual.widgets import Button

# bin/ 디렉토리를 sys.path에 추가하여 'tui' 패키지를 직접 임포트
_BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))


# ---------------------------------------------------------------------------
# MainScreen — 클래스 구조 확인
# ---------------------------------------------------------------------------


class TestMainScreenClass:
    """MainScreen 클래스 구조 검증."""

    def test_main_screen_importable(self):
        """MainScreen을 bin/tui/screens/main_screen에서 import 가능해야 함."""
        from tui.screens.main_screen import MainScreen  # noqa: F401

    def test_main_screen_is_screen_subclass(self):
        """MainScreen은 Textual Screen의 서브클래스여야 함."""
        from tui.screens.main_screen import MainScreen

        assert issubclass(MainScreen, Screen)

    def test_main_screen_has_compose(self):
        """MainScreen에 compose() 메서드가 정의되어 있어야 함."""
        from tui.screens.main_screen import MainScreen

        assert hasattr(MainScreen, "compose")
        assert callable(MainScreen.compose)


# ---------------------------------------------------------------------------
# MainScreen — 6개 메뉴 버튼 ID 확인 (소스 수준)
# ---------------------------------------------------------------------------


class TestMainScreenButtonIds:
    """6개 메뉴 버튼 ID가 소스에 정의되어 있는지 확인."""

    EXPECTED_IDS = [
        "btn-run",
        "btn-db",
        "btn-host",
        "btn-config",
        "btn-history",
        "btn-help",
    ]

    def _get_source(self) -> str:
        from tui.screens import main_screen

        return inspect.getsource(main_screen)

    def test_btn_run_id_defined(self):
        """btn-run ID가 소스에 존재해야 함."""
        assert "btn-run" in self._get_source()

    def test_btn_db_id_defined(self):
        """btn-db ID가 소스에 존재해야 함."""
        assert "btn-db" in self._get_source()

    def test_btn_host_id_defined(self):
        """btn-host ID가 소스에 존재해야 함."""
        assert "btn-host" in self._get_source()

    def test_btn_config_id_defined(self):
        """btn-config ID가 소스에 존재해야 함."""
        assert "btn-config" in self._get_source()

    def test_btn_history_id_defined(self):
        """btn-history ID가 소스에 존재해야 함."""
        assert "btn-history" in self._get_source()

    def test_btn_help_id_defined(self):
        """btn-help ID가 소스에 존재해야 함."""
        assert "btn-help" in self._get_source()

    def test_all_six_button_ids_present(self):
        """6개 버튼 ID가 모두 소스에 존재해야 함."""
        src = self._get_source()
        missing = [bid for bid in self.EXPECTED_IDS if bid not in src]
        assert not missing, f"Missing button IDs: {missing}"


# ---------------------------------------------------------------------------
# MainScreen — CSS 클래스 참조 확인
# ---------------------------------------------------------------------------


class TestMainScreenCssClasses:
    """메뉴 그리드 및 버튼 CSS 클래스 참조 확인."""

    def _get_source(self) -> str:
        from tui.screens import main_screen

        return inspect.getsource(main_screen)

    def test_menu_grid_class_used(self):
        """compose()에서 .menu-grid CSS 클래스를 사용해야 함."""
        assert "menu-grid" in self._get_source()

    def test_menu_button_class_used(self):
        """compose()에서 .menu-button CSS 클래스를 사용해야 함."""
        assert "menu-button" in self._get_source()


# ---------------------------------------------------------------------------
# MainScreen — 위젯 통합 확인
# ---------------------------------------------------------------------------


class TestMainScreenWidgetIntegration:
    """HeaderWidget, StatusBar, FooterWidget 통합 확인."""

    def _get_source(self) -> str:
        from tui.screens import main_screen

        return inspect.getsource(main_screen)

    def test_header_widget_imported(self):
        """HeaderWidget을 import해야 함."""
        assert "HeaderWidget" in self._get_source()

    def test_status_bar_imported(self):
        """StatusBar를 import해야 함."""
        assert "StatusBar" in self._get_source()

    def test_footer_widget_imported(self):
        """FooterWidget을 import해야 함."""
        assert "FooterWidget" in self._get_source()


# ---------------------------------------------------------------------------
# app.py — BINDINGS 및 action 메서드 확인
# ---------------------------------------------------------------------------


class TestAppBindings:
    """DeepInVirusApp에 필요한 BINDINGS와 action 메서드가 정의되어 있는지 확인."""

    EXPECTED_KEYS = {"r", "d", "h", "c", "i", "q"}
    EXPECTED_ACTIONS = [
        "action_run",
        "action_database",
        "action_host",
        "action_config",
        "action_history",
    ]

    def _get_app_source(self) -> str:
        from tui import app as app_module

        return inspect.getsource(app_module)

    def _get_app_class(self):
        from tui.app import DeepInVirusApp

        return DeepInVirusApp

    def test_app_has_bindings(self):
        """DeepInVirusApp.BINDINGS가 정의되어 있어야 함."""
        App = self._get_app_class()
        assert hasattr(App, "BINDINGS")
        assert len(App.BINDINGS) >= 6, (
            f"BINDINGS에 6개 이상 정의 필요, 현재: {len(App.BINDINGS)}"
        )

    def test_binding_r_for_run(self):
        """'r' 바인딩이 BINDINGS에 존재해야 함."""
        src = self._get_app_source()
        assert '"r"' in src or "'r'" in src

    def test_binding_d_for_database(self):
        """'d' 바인딩이 BINDINGS에 존재해야 함."""
        src = self._get_app_source()
        assert '"d"' in src or "'d'" in src

    def test_binding_h_for_host(self):
        """'h' 바인딩이 BINDINGS에 존재해야 함."""
        src = self._get_app_source()
        assert '"h"' in src or "'h'" in src

    def test_binding_c_for_config(self):
        """'c' 바인딩이 BINDINGS에 존재해야 함."""
        src = self._get_app_source()
        assert '"c"' in src or "'c'" in src

    def test_binding_i_for_history(self):
        """'i' 바인딩이 BINDINGS에 존재해야 함."""
        src = self._get_app_source()
        assert '"i"' in src or "'i'" in src

    def test_binding_q_for_quit(self):
        """'q' 바인딩이 BINDINGS에 존재해야 함."""
        src = self._get_app_source()
        assert '"q"' in src or "'q'" in src

    def test_binding_escape_defined(self):
        """'escape' 바인딩이 정의되어 있어야 함."""
        src = self._get_app_source()
        assert "escape" in src

    def test_action_run_defined(self):
        """action_run 메서드가 DeepInVirusApp에 있어야 함."""
        App = self._get_app_class()
        assert hasattr(App, "action_run"), "action_run 메서드 없음"

    def test_action_database_defined(self):
        """action_database 메서드가 DeepInVirusApp에 있어야 함."""
        App = self._get_app_class()
        assert hasattr(App, "action_database"), "action_database 메서드 없음"

    def test_action_host_defined(self):
        """action_host 메서드가 DeepInVirusApp에 있어야 함."""
        App = self._get_app_class()
        assert hasattr(App, "action_host"), "action_host 메서드 없음"

    def test_action_config_defined(self):
        """action_config 메서드가 DeepInVirusApp에 있어야 함."""
        App = self._get_app_class()
        assert hasattr(App, "action_config"), "action_config 메서드 없음"

    def test_action_history_defined(self):
        """action_history 메서드가 DeepInVirusApp에 있어야 함."""
        App = self._get_app_class()
        assert hasattr(App, "action_history"), "action_history 메서드 없음"


# ---------------------------------------------------------------------------
# app.py — MainScreen을 기본 화면으로 사용
# ---------------------------------------------------------------------------


class TestAppMainScreen:
    """DeepInVirusApp이 MainScreen을 기본 화면으로 사용하는지 확인."""

    def test_main_screen_imported_in_app(self):
        """app.py에서 MainScreen을 import해야 함."""
        from tui import app as app_module

        src = inspect.getsource(app_module)
        assert "MainScreen" in src

    def test_app_uses_screens_dict_or_install(self):
        """App에 SCREENS 또는 install_screen 패턴으로 MainScreen 등록해야 함."""
        from tui import app as app_module

        src = inspect.getsource(app_module)
        # SCREENS dict 또는 push_screen/install_screen 사용
        has_screens_attr = "SCREENS" in src
        has_push = "push_screen" in src
        has_install = "install_screen" in src
        assert has_screens_attr or has_push or has_install, (
            "SCREENS dict 또는 push_screen/install_screen 사용 필요"
        )

    def test_main_screen_as_default(self):
        """app.py에 MainScreen을 기본(initial) 화면으로 지정해야 함."""
        from tui import app as app_module

        src = inspect.getsource(app_module)
        # MainScreen이 SCREENS의 첫 번째 키이거나 on_mount에서 push
        # 또는 App.SCREENS = {"main": MainScreen, ...} 형식
        assert "MainScreen" in src
        # 최소한 "main" 키 또는 on_mount에서 push_screen(MainScreen) 호출
        has_main_key = '"main"' in src or "'main'" in src
        has_on_mount_push = "on_mount" in src
        assert has_main_key or has_on_mount_push, (
            "MainScreen을 기본 화면으로 등록 필요 (SCREENS 또는 on_mount)"
        )
