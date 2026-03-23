# @TASK T7.1 - DeepInVirusApp 기본 테스트
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t71-textual-프레임워크-셋업
"""
Basic smoke tests for T7.1: Textual framework setup.

Verifies:
- DeepInVirusApp can be imported from the tui package
- An App instance can be created without raising exceptions
- All screen skeleton modules are importable
- All widget skeleton modules are importable
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# bin/ 디렉토리를 sys.path에 추가하여 'tui' 패키지를 직접 임포트
BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))


# ---------------------------------------------------------------------------
# Import tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_import_deepinvirus_app() -> None:
    """DeepInVirusApp can be imported from tui.app."""
    from tui.app import DeepInVirusApp  # noqa: F401 (import-only check)


@pytest.mark.unit
def test_app_instantiation() -> None:
    """DeepInVirusApp instance can be created without error."""
    from tui.app import DeepInVirusApp

    app = DeepInVirusApp()
    assert app is not None


@pytest.mark.unit
def test_app_title_attribute() -> None:
    """App TITLE class attribute is set to 'DeepInvirus'."""
    from tui.app import DeepInVirusApp

    assert DeepInVirusApp.TITLE == "DeepInvirus"


@pytest.mark.unit
def test_app_css_path_attribute() -> None:
    """App CSS_PATH class attribute points to styles/app.tcss."""
    from tui.app import DeepInVirusApp

    assert DeepInVirusApp.CSS_PATH == "styles/app.tcss"


@pytest.mark.unit
def test_app_quit_binding_present() -> None:
    """App BINDINGS contains a 'q' -> quit binding."""
    from tui.app import DeepInVirusApp

    keys = [b[0] for b in DeepInVirusApp.BINDINGS]
    assert "q" in keys


# ---------------------------------------------------------------------------
# Screen skeleton import tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "module_path, class_name",
    [
        ("tui.screens.main_screen", "MainScreen"),
        ("tui.screens.run_screen", "RunScreen"),
        ("tui.screens.db_screen", "DbScreen"),
        ("tui.screens.host_screen", "HostScreen"),
        ("tui.screens.config_screen", "ConfigScreen"),
        ("tui.screens.history_screen", "HistoryScreen"),
    ],
)
def test_screen_module_importable(module_path: str, class_name: str) -> None:
    """Each screen module is importable and exposes its Screen subclass."""
    from textual.screen import Screen

    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    assert issubclass(cls, Screen), (
        f"{class_name} must be a subclass of textual.screen.Screen"
    )


# ---------------------------------------------------------------------------
# Widget skeleton import tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "module_path, class_name",
    [
        ("tui.widgets.header", "HeaderWidget"),
        ("tui.widgets.footer", "FooterWidget"),
        ("tui.widgets.status_bar", "StatusBar"),
        ("tui.widgets.progress", "ProgressWidget"),
        ("tui.widgets.log_viewer", "LogViewer"),
    ],
)
def test_widget_module_importable(module_path: str, class_name: str) -> None:
    """Each widget module is importable and exposes its Widget subclass."""
    from textual.widget import Widget

    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    assert issubclass(cls, Widget), (
        f"{class_name} must be a subclass of textual.widget.Widget"
    )
