# @TASK T12.1 - Process Resource 관리 화면 테스트
# @SPEC docs/planning/06-tasks-tui.md#process-resources
# @TEST tests/tui/test_resource_screen.py
"""
TDD RED phase: unit tests for ResourceManager and ResourceScreen.

Tests cover:
- ResourceManager: parse base.config, get/set per-process resources,
  get/set max resources, system info
- ResourceScreen: Screen subclass, DataTable, action buttons
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pytest

# bin/ 디렉토리를 sys.path에 추가하여 직접 임포트
BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))


# ===========================================================================
# Fixtures
# ===========================================================================

SAMPLE_BASE_CONFIG = textwrap.dedent("""\
    // DeepInvirus 리소스 설정 (전역)
    // 기본값: 32 cores / 256 GB

    process {

        cpus   = { check_max( 4,    'cpus'   ) }
        memory = { check_max( 8.GB, 'memory' ) }
        time   = { check_max( 1.h,  'time'   ) }
        maxForks = 1

        withLabel: process_low {
            cpus   = { check_max( 4,     'cpus'   ) }
            memory = { check_max( 8.GB,  'memory' ) }
            time   = { check_max( 2.h,   'time'   ) }
        }
        withLabel: process_high {
            cpus   = { check_max( 32,     'cpus'   ) }
            memory = { check_max( 128.GB, 'memory' ) }
            time   = { check_max( 16.h,   'time'   ) }
        }

        // --- QC ---
        withLabel: process_bbduk {
            cpus   = { check_max( 32,     'cpus'   ) }
            memory = { check_max( 128.GB, 'memory' ) }
        }
        withLabel: process_fastp {
            cpus   = { check_max( 16,    'cpus'   ) }
            memory = { check_max( 32.GB, 'memory' ) }
        }
        withLabel: process_host_removal {
            cpus   = { check_max( 32,     'cpus'   ) }
            memory = { check_max( 128.GB, 'memory' ) }
        }

        // --- Assembly ---
        withLabel: process_megahit {
            cpus   = { check_max( 32,     'cpus'   ) }
            memory = { check_max( 128.GB, 'memory' ) }
        }

        // --- Detection ---
        withLabel: process_genomad {
            cpus   = { check_max( 32,     'cpus'   ) }
            memory = { check_max( 128.GB, 'memory' ) }
        }
        withLabel: process_diamond {
            cpus   = { check_max( 32,     'cpus'   ) }
            memory = { check_max( 128.GB, 'memory' ) }
        }

        // --- Classification ---
        withLabel: process_mmseqs {
            cpus   = { check_max( 32,     'cpus'   ) }
            memory = { check_max( 128.GB, 'memory' ) }
        }
        withLabel: process_coverm {
            cpus   = { check_max( 16,    'cpus'   ) }
            memory = { check_max( 64.GB, 'memory' ) }
        }

        // --- Reporting ---
        withLabel: process_merge {
            cpus   = { check_max( 4,     'cpus'   ) }
            memory = { check_max( 16.GB, 'memory' ) }
        }
        withLabel: process_diversity {
            cpus   = { check_max( 4,     'cpus'   ) }
            memory = { check_max( 16.GB, 'memory' ) }
        }
        withLabel: process_dashboard {
            cpus   = { check_max( 4,     'cpus'   ) }
            memory = { check_max( 16.GB, 'memory' ) }
        }
        withLabel: process_report {
            cpus   = { check_max( 4,     'cpus'   ) }
            memory = { check_max( 16.GB, 'memory' ) }
        }
    }

    def check_max(obj, type) {
        // ...
    }
""")


@pytest.fixture()
def config_path(tmp_path: Path) -> Path:
    """Write a sample base.config to a temp directory and return its path."""
    p = tmp_path / "base.config"
    p.write_text(SAMPLE_BASE_CONFIG)
    return p


# ===========================================================================
# ResourceManager tests
# ===========================================================================


class TestResourceManagerGetAll:
    """Test get_all_resources() parsing of base.config."""

    @pytest.mark.unit
    def test_returns_list(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        result = rm.get_all_resources()
        assert isinstance(result, list)

    @pytest.mark.unit
    def test_contains_known_processes(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        result = rm.get_all_resources()
        names = {r["process"] for r in result}
        for expected in ("bbduk", "fastp", "host_removal", "megahit",
                         "genomad", "diamond", "mmseqs", "coverm",
                         "merge", "diversity", "dashboard", "report"):
            assert expected in names, f"Missing process: {expected}"

    @pytest.mark.unit
    def test_excludes_size_labels(self, config_path: Path) -> None:
        """Size labels like process_low/high should not appear as named processes."""
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        result = rm.get_all_resources()
        names = {r["process"] for r in result}
        assert "low" not in names
        assert "high" not in names
        assert "medium" not in names
        assert "high_memory" not in names

    @pytest.mark.unit
    def test_bbduk_resources(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        result = rm.get_all_resources()
        bbduk = next(r for r in result if r["process"] == "bbduk")
        assert bbduk["cpus"] == 32
        assert bbduk["memory_gb"] == 128

    @pytest.mark.unit
    def test_fastp_resources(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        result = rm.get_all_resources()
        fastp = next(r for r in result if r["process"] == "fastp")
        assert fastp["cpus"] == 16
        assert fastp["memory_gb"] == 32

    @pytest.mark.unit
    def test_merge_resources(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        result = rm.get_all_resources()
        merge = next(r for r in result if r["process"] == "merge")
        assert merge["cpus"] == 4
        assert merge["memory_gb"] == 16


class TestResourceManagerGetOne:
    """Test get_resource() for a single process."""

    @pytest.mark.unit
    def test_returns_dict(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        result = rm.get_resource("bbduk")
        assert isinstance(result, dict)
        assert result["process"] == "bbduk"

    @pytest.mark.unit
    def test_nonexistent_raises(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        with pytest.raises(KeyError):
            rm.get_resource("nonexistent_process")


class TestResourceManagerSetResource:
    """Test set_resource() modifies config file."""

    @pytest.mark.unit
    def test_set_cpus(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        rm.set_resource("bbduk", cpus=8)
        # Re-parse to confirm
        rm2 = ResourceManager(config_path)
        result = rm2.get_resource("bbduk")
        assert result["cpus"] == 8

    @pytest.mark.unit
    def test_set_memory(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        rm.set_resource("fastp", memory_gb=64)
        rm2 = ResourceManager(config_path)
        result = rm2.get_resource("fastp")
        assert result["memory_gb"] == 64

    @pytest.mark.unit
    def test_set_both(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        rm.set_resource("merge", cpus=8, memory_gb=32)
        rm2 = ResourceManager(config_path)
        result = rm2.get_resource("merge")
        assert result["cpus"] == 8
        assert result["memory_gb"] == 32

    @pytest.mark.unit
    def test_set_resource_nonexistent_raises(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        with pytest.raises(KeyError):
            rm.set_resource("nonexistent", cpus=4)

    @pytest.mark.unit
    def test_set_preserves_other_processes(self, config_path: Path) -> None:
        """Modifying one process must not alter others."""
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        rm.set_resource("bbduk", cpus=2)
        rm2 = ResourceManager(config_path)
        fastp = rm2.get_resource("fastp")
        assert fastp["cpus"] == 16
        assert fastp["memory_gb"] == 32


class TestResourceManagerSystemInfo:
    """Test get_system_info() returns real system data."""

    @pytest.mark.unit
    def test_returns_dict_with_keys(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        info = rm.get_system_info()
        assert isinstance(info, dict)
        assert "cpus" in info
        assert "memory_gb" in info

    @pytest.mark.unit
    def test_cpus_positive(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        info = rm.get_system_info()
        assert info["cpus"] > 0

    @pytest.mark.unit
    def test_memory_positive(self, config_path: Path) -> None:
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        info = rm.get_system_info()
        assert info["memory_gb"] > 0


class TestResourceManagerParsing:
    """Edge-case parsing tests."""

    @pytest.mark.unit
    def test_integer_memory_values(self, config_path: Path) -> None:
        """All memory_gb values should be integers."""
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        for r in rm.get_all_resources():
            assert isinstance(r["memory_gb"], int), (
                f"Process {r['process']} memory_gb is {type(r['memory_gb'])}"
            )

    @pytest.mark.unit
    def test_integer_cpu_values(self, config_path: Path) -> None:
        """All cpus values should be integers."""
        from resource_manager import ResourceManager

        rm = ResourceManager(config_path)
        for r in rm.get_all_resources():
            assert isinstance(r["cpus"], int), (
                f"Process {r['process']} cpus is {type(r['cpus'])}"
            )


# ===========================================================================
# ResourceScreen UI tests
# ===========================================================================


class TestResourceScreenUI:
    """Tests for ResourceScreen Textual Screen subclass."""

    @pytest.mark.unit
    def test_is_screen_subclass(self) -> None:
        from textual.screen import Screen

        from tui.screens.resource_screen import ResourceScreen

        assert issubclass(ResourceScreen, Screen)

    @pytest.mark.unit
    def test_compose_contains_datatable(self) -> None:
        from textual.widgets import DataTable

        from tui.screens.resource_screen import ResourceScreen

        screen = ResourceScreen()
        widgets = list(_flatten_compose(screen.compose()))
        has_datatable = any(isinstance(w, DataTable) for w in widgets)
        assert has_datatable, "DataTable not found in ResourceScreen"

    @pytest.mark.unit
    def test_compose_contains_required_buttons(self) -> None:
        from textual.widgets import Button

        from tui.screens.resource_screen import ResourceScreen

        screen = ResourceScreen()
        widgets = list(_flatten_compose(screen.compose()))
        buttons = [w for w in widgets if isinstance(w, Button)]
        button_ids = {b.id for b in buttons if b.id}
        for expected_id in ("btn-edit", "btn-set-max", "btn-reset",
                            "btn-save", "btn-back"):
            assert expected_id in button_ids, (
                f"Missing button id: {expected_id}, found: {button_ids}"
            )

    @pytest.mark.unit
    def test_has_system_info_static(self) -> None:
        """Screen should have a Static widget for system/max info display."""
        from textual.widgets import Static

        from tui.screens.resource_screen import ResourceScreen

        screen = ResourceScreen()
        widgets = list(_flatten_compose(screen.compose()))
        statics = [w for w in widgets if isinstance(w, Static)]
        static_ids = {s.id for s in statics if s.id}
        assert "system-info" in static_ids, (
            f"Missing #system-info Static, found: {static_ids}"
        )


# ===========================================================================
# Helpers
# ===========================================================================


def _flatten_compose(widgets):
    """Recursively yield leaf widgets from compose() output."""
    from textual.widget import Widget

    for w in widgets:
        yield w
        if isinstance(w, Widget):
            pending = getattr(w, "_pending_children", None)
            if pending:
                yield from _flatten_compose(pending)
                continue
            try:
                children = list(w.compose())
                if children:
                    yield from _flatten_compose(children)
            except Exception:
                pass
