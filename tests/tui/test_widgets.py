# @TASK T7.2 - 공통 위젯 단위 테스트
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t72-공통-위젯-구현-redgreen
# @TEST tests/tui/test_widgets.py
"""
TDD RED phase: unit tests for T7.2 common widgets.

Tests:
- HeaderWidget, FooterWidget, StatusBar, ProgressWidget, LogViewer
- All must be Textual Widget subclasses with compose() defined
- ProgressWidget must have update(current, total, step_name) method
- LogViewer must have append_log(line) and clear() methods
- StatusBar must accept a db_dir path and read VERSION.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# bin/ 디렉토리를 sys.path에 추가하여 'tui' 패키지를 직접 임포트
BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_widget_class(module_path: str, class_name: str):
    """Import and return a widget class."""
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


# ---------------------------------------------------------------------------
# HeaderWidget
# ---------------------------------------------------------------------------


class TestHeaderWidget:
    """Tests for HeaderWidget."""

    @pytest.mark.unit
    def test_is_widget_subclass(self) -> None:
        """HeaderWidget must be a Textual Widget subclass."""
        from textual.widget import Widget
        cls = _get_widget_class("tui.widgets.header", "HeaderWidget")
        assert issubclass(cls, Widget)

    @pytest.mark.unit
    def test_has_compose_method(self) -> None:
        """HeaderWidget must define a compose() method."""
        cls = _get_widget_class("tui.widgets.header", "HeaderWidget")
        assert callable(getattr(cls, "compose", None))

    @pytest.mark.unit
    def test_instantiates_without_error(self) -> None:
        """HeaderWidget can be instantiated without arguments."""
        cls = _get_widget_class("tui.widgets.header", "HeaderWidget")
        widget = cls()
        assert widget is not None

    @pytest.mark.unit
    def test_has_app_title_attribute(self) -> None:
        """HeaderWidget exposes APP_TITLE or similar title constant."""
        cls = _get_widget_class("tui.widgets.header", "HeaderWidget")
        # Either a class constant or a method that returns title text
        has_title = (
            hasattr(cls, "APP_TITLE")
            or hasattr(cls, "TITLE")
            or hasattr(cls, "app_title")
        )
        assert has_title, "HeaderWidget should expose an app title constant"


# ---------------------------------------------------------------------------
# FooterWidget
# ---------------------------------------------------------------------------


class TestFooterWidget:
    """Tests for FooterWidget."""

    @pytest.mark.unit
    def test_is_widget_subclass(self) -> None:
        """FooterWidget must be a Textual Widget subclass."""
        from textual.widget import Widget
        cls = _get_widget_class("tui.widgets.footer", "FooterWidget")
        assert issubclass(cls, Widget)

    @pytest.mark.unit
    def test_has_compose_method(self) -> None:
        """FooterWidget must define a compose() method."""
        cls = _get_widget_class("tui.widgets.footer", "FooterWidget")
        assert callable(getattr(cls, "compose", None))

    @pytest.mark.unit
    def test_instantiates_without_error(self) -> None:
        """FooterWidget can be instantiated without arguments."""
        cls = _get_widget_class("tui.widgets.footer", "FooterWidget")
        widget = cls()
        assert widget is not None

    @pytest.mark.unit
    def test_has_shortcut_keys_defined(self) -> None:
        """FooterWidget defines SHORTCUT_KEYS or SHORTCUTS constant."""
        cls = _get_widget_class("tui.widgets.footer", "FooterWidget")
        has_shortcuts = (
            hasattr(cls, "SHORTCUT_KEYS")
            or hasattr(cls, "SHORTCUTS")
            or hasattr(cls, "shortcut_keys")
        )
        assert has_shortcuts, "FooterWidget should define shortcut key constants"


# ---------------------------------------------------------------------------
# StatusBar
# ---------------------------------------------------------------------------


class TestStatusBar:
    """Tests for StatusBar."""

    @pytest.mark.unit
    def test_is_widget_subclass(self) -> None:
        """StatusBar must be a Textual Widget subclass."""
        from textual.widget import Widget
        cls = _get_widget_class("tui.widgets.status_bar", "StatusBar")
        assert issubclass(cls, Widget)

    @pytest.mark.unit
    def test_has_compose_method(self) -> None:
        """StatusBar must define a compose() method."""
        cls = _get_widget_class("tui.widgets.status_bar", "StatusBar")
        assert callable(getattr(cls, "compose", None))

    @pytest.mark.unit
    def test_accepts_db_dir_argument(self) -> None:
        """StatusBar can be instantiated with a db_dir Path argument."""
        cls = _get_widget_class("tui.widgets.status_bar", "StatusBar")
        widget = cls(db_dir=Path("/tmp"))
        assert widget is not None

    @pytest.mark.unit
    def test_has_load_db_info_method(self) -> None:
        """StatusBar exposes load_db_info() to read VERSION.json."""
        cls = _get_widget_class("tui.widgets.status_bar", "StatusBar")
        assert callable(getattr(cls, "load_db_info", None)), (
            "StatusBar must have a load_db_info() method"
        )

    @pytest.mark.unit
    def test_load_db_info_returns_not_installed_when_no_version_json(
        self, tmp_path: Path
    ) -> None:
        """load_db_info() returns 'Not installed' when VERSION.json absent."""
        cls = _get_widget_class("tui.widgets.status_bar", "StatusBar")
        widget = cls(db_dir=tmp_path)
        info = widget.load_db_info()
        assert info["db_version"] == "Not installed"

    @pytest.mark.unit
    def test_load_db_info_reads_version_json(self, tmp_path: Path) -> None:
        """load_db_info() reads db_version from VERSION.json."""
        version_data = {
            "db_version": "2026-03-23",
            "hosts": ["human", "insect"],
        }
        version_file = tmp_path / "VERSION.json"
        version_file.write_text(json.dumps(version_data))

        cls = _get_widget_class("tui.widgets.status_bar", "StatusBar")
        widget = cls(db_dir=tmp_path)
        info = widget.load_db_info()
        assert info["db_version"] == "2026-03-23"

    @pytest.mark.unit
    def test_load_db_info_reads_hosts_from_version_json(
        self, tmp_path: Path
    ) -> None:
        """load_db_info() includes hosts list from VERSION.json."""
        version_data = {
            "db_version": "2026-03-23",
            "hosts": ["human", "insect"],
        }
        version_file = tmp_path / "VERSION.json"
        version_file.write_text(json.dumps(version_data))

        cls = _get_widget_class("tui.widgets.status_bar", "StatusBar")
        widget = cls(db_dir=tmp_path)
        info = widget.load_db_info()
        assert info["hosts"] == ["human", "insect"]

    @pytest.mark.unit
    def test_load_db_info_returns_no_runs_yet_when_no_history(
        self, tmp_path: Path
    ) -> None:
        """load_db_info() returns 'No runs yet' when history.json is absent."""
        cls = _get_widget_class("tui.widgets.status_bar", "StatusBar")
        widget = cls(db_dir=tmp_path)
        info = widget.load_db_info()
        assert info["last_run"] == "No runs yet"


# ---------------------------------------------------------------------------
# ProgressWidget
# ---------------------------------------------------------------------------


class TestProgressWidget:
    """Tests for ProgressWidget."""

    @pytest.mark.unit
    def test_is_widget_subclass(self) -> None:
        """ProgressWidget must be a Textual Widget subclass."""
        from textual.widget import Widget
        cls = _get_widget_class("tui.widgets.progress", "ProgressWidget")
        assert issubclass(cls, Widget)

    @pytest.mark.unit
    def test_has_compose_method(self) -> None:
        """ProgressWidget must define a compose() method."""
        cls = _get_widget_class("tui.widgets.progress", "ProgressWidget")
        assert callable(getattr(cls, "compose", None))

    @pytest.mark.unit
    def test_has_update_method(self) -> None:
        """ProgressWidget must define an update() method."""
        cls = _get_widget_class("tui.widgets.progress", "ProgressWidget")
        assert callable(getattr(cls, "update", None)), (
            "ProgressWidget must have an update() method"
        )

    @pytest.mark.unit
    def test_update_method_signature(self) -> None:
        """update() must accept (current, total, step_name) parameters."""
        import inspect
        cls = _get_widget_class("tui.widgets.progress", "ProgressWidget")
        sig = inspect.signature(cls.update)
        params = list(sig.parameters.keys())
        # self + current + total + step_name (at minimum)
        assert "current" in params, "update() must have 'current' parameter"
        assert "total" in params, "update() must have 'total' parameter"
        assert "step_name" in params, "update() must have 'step_name' parameter"

    @pytest.mark.unit
    def test_instantiates_without_error(self) -> None:
        """ProgressWidget can be instantiated without arguments."""
        cls = _get_widget_class("tui.widgets.progress", "ProgressWidget")
        widget = cls()
        assert widget is not None

    @pytest.mark.unit
    def test_update_stores_state(self) -> None:
        """update() updates internal current/total/step_name state."""
        cls = _get_widget_class("tui.widgets.progress", "ProgressWidget")
        widget = cls()
        widget.update(current=3, total=10, step_name="MEGAHIT")
        assert widget.current == 3
        assert widget.total == 10
        assert widget.step_name == "MEGAHIT"

    @pytest.mark.unit
    def test_has_reset_method(self) -> None:
        """ProgressWidget exposes reset() to clear progress state."""
        cls = _get_widget_class("tui.widgets.progress", "ProgressWidget")
        assert callable(getattr(cls, "reset", None)), (
            "ProgressWidget must have a reset() method"
        )

    @pytest.mark.unit
    def test_reset_clears_state(self) -> None:
        """reset() resets current to 0 and step_name to empty string."""
        cls = _get_widget_class("tui.widgets.progress", "ProgressWidget")
        widget = cls()
        widget.update(current=5, total=14, step_name="FASTP")
        widget.reset()
        assert widget.current == 0
        assert widget.step_name == ""


# ---------------------------------------------------------------------------
# LogViewer
# ---------------------------------------------------------------------------


class TestLogViewer:
    """Tests for LogViewer."""

    @pytest.mark.unit
    def test_is_widget_subclass(self) -> None:
        """LogViewer must be a Textual Widget subclass."""
        from textual.widget import Widget
        cls = _get_widget_class("tui.widgets.log_viewer", "LogViewer")
        assert issubclass(cls, Widget)

    @pytest.mark.unit
    def test_has_compose_method(self) -> None:
        """LogViewer must define a compose() method."""
        cls = _get_widget_class("tui.widgets.log_viewer", "LogViewer")
        assert callable(getattr(cls, "compose", None))

    @pytest.mark.unit
    def test_has_append_log_method(self) -> None:
        """LogViewer must define an append_log() method."""
        cls = _get_widget_class("tui.widgets.log_viewer", "LogViewer")
        assert callable(getattr(cls, "append_log", None)), (
            "LogViewer must have an append_log() method"
        )

    @pytest.mark.unit
    def test_has_clear_method(self) -> None:
        """LogViewer must define a clear() method."""
        cls = _get_widget_class("tui.widgets.log_viewer", "LogViewer")
        assert callable(getattr(cls, "clear", None)), (
            "LogViewer must have a clear() method"
        )

    @pytest.mark.unit
    def test_append_log_signature(self) -> None:
        """append_log() must accept a single 'line' string parameter."""
        import inspect
        cls = _get_widget_class("tui.widgets.log_viewer", "LogViewer")
        sig = inspect.signature(cls.append_log)
        params = list(sig.parameters.keys())
        assert "line" in params, "append_log() must have 'line' parameter"

    @pytest.mark.unit
    def test_instantiates_without_error(self) -> None:
        """LogViewer can be instantiated without arguments."""
        cls = _get_widget_class("tui.widgets.log_viewer", "LogViewer")
        widget = cls()
        assert widget is not None

    @pytest.mark.unit
    def test_append_log_stores_lines(self) -> None:
        """append_log() accumulates lines in _log_lines buffer."""
        cls = _get_widget_class("tui.widgets.log_viewer", "LogViewer")
        widget = cls()
        widget.append_log("[12:34:56] FASTP completed")
        widget.append_log("[12:45:12] HOST_REMOVAL completed")
        assert len(widget._log_lines) == 2
        assert "[12:34:56] FASTP completed" in widget._log_lines

    @pytest.mark.unit
    def test_clear_empties_log_lines(self) -> None:
        """clear() empties the _log_lines buffer."""
        cls = _get_widget_class("tui.widgets.log_viewer", "LogViewer")
        widget = cls()
        widget.append_log("[13:00:00] Step started")
        widget.clear()
        assert widget._log_lines == []

    @pytest.mark.unit
    def test_max_lines_attribute_exists(self) -> None:
        """LogViewer defines MAX_LINES to cap buffer size."""
        cls = _get_widget_class("tui.widgets.log_viewer", "LogViewer")
        assert hasattr(cls, "MAX_LINES"), (
            "LogViewer must define MAX_LINES class constant"
        )
        assert isinstance(cls.MAX_LINES, int)
        assert cls.MAX_LINES > 0
