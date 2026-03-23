# @TASK T11.1, T11.2, T11.3 - Config Preset + History 통합 테스트
# @SPEC docs/planning/06-tasks-tui.md#m11-config-프리셋--history
# @TEST tests/tui/test_config_history.py
"""
TDD RED phase: unit tests for T11.1 (ConfigManager), T11.2 (HistoryManager),
and T11.3 (ConfigScreen / HistoryScreen UI).

Tests cover:
- config_manager: save/load/list/delete/get_preset_details (YAML)
- history_manager: record_run/get_history/get_run/delete_run (JSON)
- ConfigScreen: Screen subclass, DataTable, buttons
- HistoryScreen: Screen subclass, DataTable, buttons
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# bin/ 디렉토리를 sys.path에 추가하여 직접 임포트
BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))


# ===========================================================================
# config_manager tests (T11.1)
# ===========================================================================


class TestConfigManagerSaveLoad:
    """CRUD tests for config_manager preset operations."""

    @pytest.fixture()
    def preset_dir(self, tmp_path: Path) -> Path:
        """Return a temporary presets directory."""
        d = tmp_path / "presets"
        d.mkdir()
        return d

    @pytest.fixture()
    def sample_params(self) -> dict:
        return {
            "host": "insect",
            "assembler": "megahit",
            "ml_detection": True,
            "search_mode": "fast",
            "threads": 8,
        }

    @pytest.mark.unit
    def test_save_preset_creates_yaml_file(
        self, preset_dir: Path, sample_params: dict
    ) -> None:
        from config_manager import save_preset

        path = save_preset("test_preset", sample_params, preset_dir=preset_dir)
        assert path.exists()
        assert path.suffix == ".yaml"

    @pytest.mark.unit
    def test_load_preset_returns_dict(
        self, preset_dir: Path, sample_params: dict
    ) -> None:
        from config_manager import load_preset, save_preset

        save_preset("roundtrip", sample_params, preset_dir=preset_dir)
        loaded = load_preset("roundtrip", preset_dir=preset_dir)
        assert loaded == sample_params

    @pytest.mark.unit
    def test_list_presets_returns_names(
        self, preset_dir: Path, sample_params: dict
    ) -> None:
        from config_manager import list_presets, save_preset

        save_preset("alpha", sample_params, preset_dir=preset_dir)
        save_preset("beta", sample_params, preset_dir=preset_dir)
        names = list_presets(preset_dir=preset_dir)
        assert set(names) == {"alpha", "beta"}

    @pytest.mark.unit
    def test_delete_preset(
        self, preset_dir: Path, sample_params: dict
    ) -> None:
        from config_manager import delete_preset, list_presets, save_preset

        save_preset("to_delete", sample_params, preset_dir=preset_dir)
        result = delete_preset("to_delete", preset_dir=preset_dir)
        assert result is True
        assert "to_delete" not in list_presets(preset_dir=preset_dir)

    @pytest.mark.unit
    def test_delete_nonexistent_preset_returns_false(
        self, preset_dir: Path
    ) -> None:
        from config_manager import delete_preset

        result = delete_preset("nonexistent", preset_dir=preset_dir)
        assert result is False

    @pytest.mark.unit
    def test_load_nonexistent_preset_raises(self, preset_dir: Path) -> None:
        from config_manager import load_preset

        with pytest.raises(FileNotFoundError):
            load_preset("nonexistent", preset_dir=preset_dir)

    @pytest.mark.unit
    def test_get_preset_details_includes_metadata(
        self, preset_dir: Path, sample_params: dict
    ) -> None:
        from config_manager import get_preset_details, save_preset

        save_preset("detailed", sample_params, preset_dir=preset_dir)
        details = get_preset_details("detailed", preset_dir=preset_dir)
        assert details["name"] == "detailed"
        assert details["params"] == sample_params
        assert "created_at" in details

    @pytest.mark.unit
    def test_yaml_format_valid(
        self, preset_dir: Path, sample_params: dict
    ) -> None:
        """Saved file must be valid YAML that round-trips correctly."""
        import yaml

        from config_manager import save_preset

        path = save_preset("yaml_check", sample_params, preset_dir=preset_dir)
        with open(path) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict)
        assert data["params"] == sample_params


# ===========================================================================
# history_manager tests (T11.2)
# ===========================================================================


class TestHistoryManager:
    """CRUD tests for history_manager run history operations."""

    @pytest.fixture()
    def history_file(self, tmp_path: Path) -> Path:
        return tmp_path / "history.json"

    @pytest.fixture()
    def sample_run(self) -> dict:
        return {
            "run_id": "run-001",
            "params": {"host": "insect", "assembler": "megahit"},
            "status": "done",
            "duration": 123.4,
            "output_dir": "/tmp/results",
            "summary": {"samples": 2, "viruses": 15},
        }

    @pytest.mark.unit
    def test_record_run_creates_file(
        self, history_file: Path, sample_run: dict
    ) -> None:
        from history_manager import record_run

        record_run(**sample_run, history_file=history_file)
        assert history_file.exists()

    @pytest.mark.unit
    def test_get_history_returns_list(
        self, history_file: Path, sample_run: dict
    ) -> None:
        from history_manager import get_history, record_run

        record_run(**sample_run, history_file=history_file)
        history = get_history(history_file=history_file)
        assert isinstance(history, list)
        assert len(history) == 1
        assert history[0]["run_id"] == "run-001"

    @pytest.mark.unit
    def test_get_history_most_recent_first(
        self, history_file: Path
    ) -> None:
        from history_manager import get_history, record_run

        record_run(
            run_id="old",
            params={},
            status="done",
            duration=10.0,
            output_dir="/tmp/a",
            summary={},
            history_file=history_file,
        )
        record_run(
            run_id="new",
            params={},
            status="done",
            duration=20.0,
            output_dir="/tmp/b",
            summary={},
            history_file=history_file,
        )
        history = get_history(history_file=history_file)
        assert history[0]["run_id"] == "new"
        assert history[1]["run_id"] == "old"

    @pytest.mark.unit
    def test_get_history_respects_limit(
        self, history_file: Path
    ) -> None:
        from history_manager import get_history, record_run

        for i in range(5):
            record_run(
                run_id=f"run-{i}",
                params={},
                status="done",
                duration=float(i),
                output_dir=f"/tmp/{i}",
                summary={},
                history_file=history_file,
            )
        history = get_history(limit=3, history_file=history_file)
        assert len(history) == 3

    @pytest.mark.unit
    def test_get_run_returns_matching(
        self, history_file: Path, sample_run: dict
    ) -> None:
        from history_manager import get_run, record_run

        record_run(**sample_run, history_file=history_file)
        run = get_run("run-001", history_file=history_file)
        assert run is not None
        assert run["run_id"] == "run-001"

    @pytest.mark.unit
    def test_get_run_returns_none_for_missing(
        self, history_file: Path
    ) -> None:
        from history_manager import get_run

        run = get_run("nonexistent", history_file=history_file)
        assert run is None

    @pytest.mark.unit
    def test_delete_run(
        self, history_file: Path, sample_run: dict
    ) -> None:
        from history_manager import delete_run, get_run, record_run

        record_run(**sample_run, history_file=history_file)
        result = delete_run("run-001", history_file=history_file)
        assert result is True
        assert get_run("run-001", history_file=history_file) is None

    @pytest.mark.unit
    def test_delete_nonexistent_run_returns_false(
        self, history_file: Path
    ) -> None:
        from history_manager import delete_run

        result = delete_run("nonexistent", history_file=history_file)
        assert result is False

    @pytest.mark.unit
    def test_json_format_valid(
        self, history_file: Path, sample_run: dict
    ) -> None:
        from history_manager import record_run

        record_run(**sample_run, history_file=history_file)
        with open(history_file) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert data[0]["run_id"] == "run-001"


# ===========================================================================
# ConfigScreen UI tests (T11.1)
# ===========================================================================


class TestConfigScreenUI:
    """Tests for ConfigScreen Textual Screen subclass."""

    @pytest.mark.unit
    def test_is_screen_subclass(self) -> None:
        from textual.screen import Screen

        from tui.screens.config_screen import ConfigScreen

        assert issubclass(ConfigScreen, Screen)

    @pytest.mark.unit
    def test_compose_contains_datatable(self) -> None:
        from textual.widgets import DataTable

        from tui.screens.config_screen import ConfigScreen

        screen = ConfigScreen()
        widgets = list(screen.compose())
        widget_types = [type(w).__name__ for w in widgets]
        # DataTable may be nested in a container
        has_datatable = any(
            isinstance(w, DataTable) or "DataTable" in str(type(w))
            for w in _flatten_compose(widgets)
        )
        assert has_datatable, f"DataTable not found in: {widget_types}"

    @pytest.mark.unit
    def test_compose_contains_buttons(self) -> None:
        from textual.widgets import Button

        from tui.screens.config_screen import ConfigScreen

        screen = ConfigScreen()
        widgets = list(_flatten_compose(screen.compose()))
        buttons = [w for w in widgets if isinstance(w, Button)]
        button_labels = {str(b.label).lower() for b in buttons}
        for expected in ("new", "delete", "back"):
            assert any(
                expected in lbl for lbl in button_labels
            ), f"Missing button: {expected}"


# ===========================================================================
# HistoryScreen UI tests (T11.2)
# ===========================================================================


class TestHistoryScreenUI:
    """Tests for HistoryScreen Textual Screen subclass."""

    @pytest.mark.unit
    def test_is_screen_subclass(self) -> None:
        from textual.screen import Screen

        from tui.screens.history_screen import HistoryScreen

        assert issubclass(HistoryScreen, Screen)

    @pytest.mark.unit
    def test_compose_contains_datatable(self) -> None:
        from textual.widgets import DataTable

        from tui.screens.history_screen import HistoryScreen

        screen = HistoryScreen()
        widgets = list(_flatten_compose(screen.compose()))
        has_datatable = any(isinstance(w, DataTable) for w in widgets)
        assert has_datatable, "DataTable not found in HistoryScreen"

    @pytest.mark.unit
    def test_compose_contains_buttons(self) -> None:
        from textual.widgets import Button

        from tui.screens.history_screen import HistoryScreen

        screen = HistoryScreen()
        widgets = list(_flatten_compose(screen.compose()))
        buttons = [w for w in widgets if isinstance(w, Button)]
        button_labels = {str(b.label).lower() for b in buttons}
        for expected in ("delete", "back"):
            assert any(
                expected in lbl for lbl in button_labels
            ), f"Missing button: {expected}"


# ===========================================================================
# Helpers
# ===========================================================================


def _flatten_compose(widgets):
    """Recursively yield leaf widgets from compose() output.

    Handles both compose()-based children and container positional
    children (Vertical, Horizontal, etc. store children in
    ``_pending_children``).
    """
    from textual.widget import Widget

    for w in widgets:
        yield w
        if isinstance(w, Widget):
            # Containers store __init__ children in _pending_children
            pending = getattr(w, "_pending_children", None)
            if pending:
                yield from _flatten_compose(pending)
                continue
            # Fallback: try compose()
            try:
                children = list(w.compose())
                if children:
                    yield from _flatten_compose(children)
            except Exception:
                pass
