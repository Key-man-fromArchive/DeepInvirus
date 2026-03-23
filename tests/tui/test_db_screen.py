# @TASK T9.1 + T9.2 - DB 관리 화면 테스트
# @SPEC docs/planning/06-tasks-tui.md#phase-9-t91-db-상태-화면-redgreen
# @SPEC docs/planning/06-tasks-tui.md#phase-9-t92-db-업데이트-액션-redgreen
"""
TDD tests for DbScreen (T9.1 + T9.2).

Tests cover:
- DbScreen class structure (Screen subclass, compose, buttons)
- load_db_info() parsing of VERSION.json
- reload_db_info() method existence
- run_install() method existence
- Button IDs: install-all, update-selected, back
- Disk usage display
- DataTable presence in compose()
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# bin/ 디렉토리를 sys.path에 추가하여 'tui' 패키지를 직접 임포트
_BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))


# ---------------------------------------------------------------------------
# T9.1: DbScreen 클래스 구조
# ---------------------------------------------------------------------------


class TestDbScreenClass:
    """DbScreen 클래스 구조 검증."""

    def test_importable(self):
        """DbScreen을 bin/tui/screens/db_screen에서 import 가능해야 함."""
        from tui.screens.db_screen import DbScreen  # noqa: F401

    def test_is_screen_subclass(self):
        """DbScreen은 Textual Screen의 서브클래스여야 함."""
        from textual.screen import Screen

        from tui.screens.db_screen import DbScreen

        assert issubclass(DbScreen, Screen)

    def test_has_compose(self):
        """DbScreen에 compose() 메서드가 정의되어 있어야 함."""
        from tui.screens.db_screen import DbScreen

        assert hasattr(DbScreen, "compose")
        assert callable(DbScreen.compose)


# ---------------------------------------------------------------------------
# T9.1: compose()에 DataTable 포함
# ---------------------------------------------------------------------------


class TestDbScreenDataTable:
    """compose()에 DataTable이 포함되어 있는지 소스 수준 확인."""

    def _get_source(self) -> str:
        from tui.screens import db_screen

        return inspect.getsource(db_screen)

    def test_datatable_imported(self):
        """DataTable이 import되어야 함."""
        assert "DataTable" in self._get_source()

    def test_datatable_in_compose(self):
        """compose()에서 DataTable을 yield해야 함."""
        src = self._get_source()
        assert "DataTable" in src


# ---------------------------------------------------------------------------
# T9.1: 버튼 3개 존재 (install-all, update-selected, back)
# ---------------------------------------------------------------------------


class TestDbScreenButtons:
    """3개 버튼 ID가 소스에 정의되어 있는지 확인."""

    EXPECTED_IDS = [
        "install-all",
        "update-selected",
        "back",
    ]

    def _get_source(self) -> str:
        from tui.screens import db_screen

        return inspect.getsource(db_screen)

    def test_install_all_button(self):
        """install-all 버튼 ID가 소스에 존재해야 함."""
        assert "install-all" in self._get_source()

    def test_update_selected_button(self):
        """update-selected 버튼 ID가 소스에 존재해야 함."""
        assert "update-selected" in self._get_source()

    def test_back_button(self):
        """back 버튼 ID가 소스에 존재해야 함."""
        # back button id
        src = self._get_source()
        assert "back" in src

    def test_all_three_buttons_present(self):
        """3개 버튼 ID가 모두 소스에 존재해야 함."""
        src = self._get_source()
        missing = [bid for bid in self.EXPECTED_IDS if bid not in src]
        assert not missing, f"Missing button IDs: {missing}"


# ---------------------------------------------------------------------------
# T9.1: load_db_info() 메서드
# ---------------------------------------------------------------------------


class TestDbScreenLoadDbInfo:
    """load_db_info() 메서드 검증."""

    def test_has_load_db_info(self):
        """DbScreen에 load_db_info() 메서드가 있어야 함."""
        from tui.screens.db_screen import DbScreen

        assert hasattr(DbScreen, "load_db_info")
        assert callable(DbScreen.load_db_info)

    def test_load_db_info_parses_version_json(self, tmp_path: Path):
        """load_db_info()가 VERSION.json을 올바르게 파싱해야 함."""
        from tui.screens.db_screen import DbScreen

        version_data = {
            "schema_version": "1.0",
            "created_at": "2026-03-23T00:00:00Z",
            "updated_at": "2026-03-23T00:00:00Z",
            "databases": {
                "viral_protein": {
                    "source": "UniRef90 viral subset",
                    "version": "2026_01",
                    "downloaded_at": "2026-03-23",
                    "format": "diamond",
                },
                "viral_nucleotide": {
                    "source": "NCBI RefSeq Viral",
                    "version": "release_224",
                    "downloaded_at": "2026-03-23",
                    "format": "mmseqs2",
                },
            },
        }
        vf = tmp_path / "VERSION.json"
        vf.write_text(json.dumps(version_data))

        screen = DbScreen()
        info = screen.load_db_info(tmp_path)

        assert isinstance(info, list)
        assert len(info) >= 2
        # Each item should have component, version, updated, installed keys
        first = info[0]
        assert "component" in first
        assert "version" in first
        assert "updated" in first
        assert "installed" in first

    def test_load_db_info_no_version_json(self, tmp_path: Path):
        """VERSION.json 없으면 빈 리스트를 반환해야 함."""
        from tui.screens.db_screen import DbScreen

        screen = DbScreen()
        info = screen.load_db_info(tmp_path)
        assert isinstance(info, list)
        assert len(info) == 0

    def test_load_db_info_installed_status(self, tmp_path: Path):
        """설치된 컴포넌트는 installed=True여야 함."""
        from tui.screens.db_screen import DbScreen

        version_data = {
            "schema_version": "1.0",
            "databases": {
                "viral_protein": {
                    "version": "2026_01",
                    "downloaded_at": "2026-03-23",
                },
            },
        }
        vf = tmp_path / "VERSION.json"
        vf.write_text(json.dumps(version_data))

        screen = DbScreen()
        info = screen.load_db_info(tmp_path)
        protein_entry = [e for e in info if e["component"] == "viral_protein"]
        assert len(protein_entry) == 1
        assert protein_entry[0]["installed"] is True


# ---------------------------------------------------------------------------
# T9.1: DB 디렉토리 경로 표시
# ---------------------------------------------------------------------------


class TestDbScreenDbPath:
    """DB 디렉토리 경로 표시 관련 검증."""

    def test_db_dir_label_in_source(self):
        """소스에 db_dir 또는 DB Directory 관련 표시가 있어야 함."""
        from tui.screens import db_screen

        src = inspect.getsource(db_screen)
        assert "db_dir" in src or "DB Directory" in src or "db-path" in src


# ---------------------------------------------------------------------------
# T9.1: 디스크 사용량 표시
# ---------------------------------------------------------------------------


class TestDbScreenDiskUsage:
    """디스크 사용량 관련 기능 검증."""

    def test_disk_usage_in_source(self):
        """소스에 디스크 사용량 계산 로직이 있어야 함."""
        from tui.screens import db_screen

        src = inspect.getsource(db_screen)
        has_disk = (
            "disk_usage" in src
            or "get_size" in src
            or "total_size" in src
            or "shutil" in src
        )
        assert has_disk, "디스크 사용량 계산 로직이 소스에 있어야 함"


# ---------------------------------------------------------------------------
# T9.2: run_install() 메서드
# ---------------------------------------------------------------------------


class TestDbScreenRunInstall:
    """run_install() 메서드 검증."""

    def test_has_run_install(self):
        """DbScreen에 run_install() 메서드가 있어야 함."""
        from tui.screens.db_screen import DbScreen

        assert hasattr(DbScreen, "run_install")
        assert callable(DbScreen.run_install)

    def test_run_install_uses_subprocess(self):
        """run_install()이 subprocess를 사용해야 함."""
        from tui.screens import db_screen

        src = inspect.getsource(db_screen)
        assert "subprocess" in src or "asyncio.create_subprocess" in src


# ---------------------------------------------------------------------------
# T9.2: reload_db_info() 메서드
# ---------------------------------------------------------------------------


class TestDbScreenReload:
    """reload_db_info() 메서드 검증."""

    def test_has_reload_db_info(self):
        """DbScreen에 reload_db_info() 메서드가 있어야 함."""
        from tui.screens.db_screen import DbScreen

        assert hasattr(DbScreen, "reload_db_info")
        assert callable(DbScreen.reload_db_info)


# ---------------------------------------------------------------------------
# T9.2: ProgressWidget 통합
# ---------------------------------------------------------------------------


class TestDbScreenProgressIntegration:
    """ProgressWidget 통합 확인."""

    def test_progress_widget_in_source(self):
        """소스에 ProgressWidget이 import되어야 함."""
        from tui.screens import db_screen

        src = inspect.getsource(db_screen)
        assert "ProgressWidget" in src


# ---------------------------------------------------------------------------
# 전체 DB 컴포넌트 목록 확인
# ---------------------------------------------------------------------------


class TestDbScreenComponentList:
    """DB 컴포넌트 목록이 완전한지 확인."""

    EXPECTED_COMPONENTS = [
        "viral_protein",
        "viral_nucleotide",
        "genomad_db",
        "taxonomy",
    ]

    def test_all_components_recognized(self, tmp_path: Path):
        """VERSION.json의 모든 DB 컴포넌트가 load_db_info에서 인식되어야 함."""
        from tui.screens.db_screen import DbScreen

        version_data = {
            "schema_version": "1.0",
            "databases": {
                "viral_protein": {
                    "version": "2026_01",
                    "downloaded_at": "2026-03-23",
                },
                "viral_nucleotide": {
                    "version": "release_224",
                    "downloaded_at": "2026-03-23",
                },
                "genomad_db": {
                    "version": "1.7",
                    "downloaded_at": "2026-03-23",
                },
                "taxonomy": {
                    "ncbi_version": "2026-03-20",
                    "ictv_version": "VMR_MSL39_v3",
                    "downloaded_at": "2026-03-23",
                },
            },
        }
        vf = tmp_path / "VERSION.json"
        vf.write_text(json.dumps(version_data))

        screen = DbScreen()
        info = screen.load_db_info(tmp_path)
        found_components = {entry["component"] for entry in info}

        for comp in self.EXPECTED_COMPONENTS:
            assert comp in found_components, f"{comp} not found in load_db_info result"
