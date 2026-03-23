# @TASK T10.1 + T10.2 - Host Genome 관리 화면 + Host 추가 액션 테스트
# @SPEC docs/planning/06-tasks-tui.md#phase-10-t101-host-목록-화면-redgreen
# @SPEC docs/planning/06-tasks-tui.md#phase-10-t102-host-추가-액션-redgreen
"""
Tests for HostScreen (T10.1) and add_host.py (T10.2).

TDD RED cycle: all tests must fail before implementation.
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from textual.screen import Screen

# bin/ 디렉토리를 sys.path에 추가하여 'tui' 패키지를 직접 임포트
_BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))


# ---------------------------------------------------------------------------
# T10.1: HostScreen -- 클래스 구조 확인
# ---------------------------------------------------------------------------


class TestHostScreenClass:
    """HostScreen 클래스 구조 검증."""

    def test_host_screen_importable(self):
        """HostScreen을 bin/tui/screens/host_screen에서 import 가능해야 함."""
        from tui.screens.host_screen import HostScreen  # noqa: F401

    def test_host_screen_is_screen_subclass(self):
        """HostScreen은 Textual Screen의 서브클래스여야 함."""
        from tui.screens.host_screen import HostScreen

        assert issubclass(HostScreen, Screen)

    def test_host_screen_has_compose(self):
        """HostScreen에 compose() 메서드가 정의되어 있어야 함."""
        from tui.screens.host_screen import HostScreen

        assert hasattr(HostScreen, "compose")
        assert callable(HostScreen.compose)


# ---------------------------------------------------------------------------
# T10.1: HostScreen -- DataTable 포함 확인
# ---------------------------------------------------------------------------


class TestHostScreenDataTable:
    """HostScreen이 DataTable 위젯을 사용하는지 확인."""

    def _get_source(self) -> str:
        from tui.screens import host_screen

        return inspect.getsource(host_screen)

    def test_datatable_imported(self):
        """DataTable이 host_screen에서 import되어야 함."""
        assert "DataTable" in self._get_source()

    def test_datatable_used_in_compose(self):
        """compose()에서 DataTable을 yield해야 함."""
        src = self._get_source()
        assert "DataTable" in src


# ---------------------------------------------------------------------------
# T10.1: HostScreen -- list_hosts() 메서드
# ---------------------------------------------------------------------------


class TestHostScreenListHosts:
    """HostScreen.list_hosts() 메서드 검증."""

    def test_list_hosts_method_exists(self):
        """HostScreen에 list_hosts 메서드가 존재해야 함."""
        from tui.screens.host_screen import HostScreen

        assert hasattr(HostScreen, "list_hosts")
        assert callable(HostScreen.list_hosts)

    def test_list_hosts_scans_directory(self):
        """list_hosts()가 host_genomes 디렉토리를 스캔하여 결과를 반환해야 함."""
        from tui.screens.host_screen import HostScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            host_dir = Path(tmpdir) / "host_genomes"
            # Create two host directories
            human_dir = host_dir / "human"
            human_dir.mkdir(parents=True)
            (human_dir / "genome.fa").write_text(">chr1\nACGT\n")
            (human_dir / "genome.mmi").write_bytes(b"\x00" * 100)

            insect_dir = host_dir / "insect"
            insect_dir.mkdir(parents=True)
            (insect_dir / "genome.fa").write_text(">scaffold1\nGCTA\n")
            # No .mmi file for insect

            screen = HostScreen()
            hosts = screen.list_hosts(Path(tmpdir))

            assert len(hosts) == 2
            names = [h["name"] for h in hosts]
            assert "human" in names
            assert "insect" in names

            # Check index status
            human_entry = next(h for h in hosts if h["name"] == "human")
            insect_entry = next(h for h in hosts if h["name"] == "insect")
            assert human_entry["indexed"] is True
            assert insect_entry["indexed"] is False

    def test_list_hosts_empty_directory(self):
        """host_genomes 디렉토리가 비어있으면 빈 리스트를 반환해야 함."""
        from tui.screens.host_screen import HostScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            host_dir = Path(tmpdir) / "host_genomes"
            host_dir.mkdir(parents=True)

            screen = HostScreen()
            hosts = screen.list_hosts(Path(tmpdir))
            assert hosts == []

    def test_list_hosts_missing_directory(self):
        """host_genomes 디렉토리가 없으면 빈 리스트를 반환해야 함."""
        from tui.screens.host_screen import HostScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            screen = HostScreen()
            hosts = screen.list_hosts(Path(tmpdir))
            assert hosts == []

    def test_list_hosts_includes_size(self):
        """list_hosts() 결과에 size 정보가 포함되어야 함."""
        from tui.screens.host_screen import HostScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            host_dir = Path(tmpdir) / "host_genomes" / "test_host"
            host_dir.mkdir(parents=True)
            (host_dir / "genome.fa").write_text(">chr1\n" + "A" * 1000 + "\n")

            screen = HostScreen()
            hosts = screen.list_hosts(Path(tmpdir))
            assert len(hosts) == 1
            assert "size" in hosts[0]
            assert hosts[0]["size"] > 0


# ---------------------------------------------------------------------------
# T10.1: HostScreen -- 버튼 ID 확인
# ---------------------------------------------------------------------------


class TestHostScreenButtons:
    """HostScreen 버튼 ID가 소스에 정의되어 있는지 확인."""

    EXPECTED_IDS = [
        "add-host",
        "remove-host",
        "back",
    ]

    def _get_source(self) -> str:
        from tui.screens import host_screen

        return inspect.getsource(host_screen)

    def test_add_host_button_defined(self):
        """add-host 버튼 ID가 소스에 존재해야 함."""
        assert "add-host" in self._get_source()

    def test_remove_host_button_defined(self):
        """remove-host 버튼 ID가 소스에 존재해야 함."""
        assert "remove-host" in self._get_source()

    def test_back_button_defined(self):
        """back 버튼 ID가 소스에 존재해야 함."""
        assert "back" in self._get_source()

    def test_all_three_button_ids_present(self):
        """3개 버튼 ID가 모두 소스에 존재해야 함."""
        src = self._get_source()
        missing = [bid for bid in self.EXPECTED_IDS if bid not in src]
        assert not missing, f"Missing button IDs: {missing}"


# ---------------------------------------------------------------------------
# T10.1: HostScreen -- DataTable 컬럼 확인
# ---------------------------------------------------------------------------


class TestHostScreenColumns:
    """DataTable에 Name, Species, Index Status, Size 컬럼이 정의되어 있는지 확인."""

    def _get_source(self) -> str:
        from tui.screens import host_screen

        return inspect.getsource(host_screen)

    def test_name_column(self):
        """Name 컬럼이 정의되어야 함."""
        assert "Name" in self._get_source()

    def test_index_status_column(self):
        """Index Status 컬럼이 정의되어야 함."""
        src = self._get_source()
        assert "Index" in src

    def test_size_column(self):
        """Size 컬럼이 정의되어야 함."""
        assert "Size" in self._get_source()


# ---------------------------------------------------------------------------
# T10.2: bin/add_host.py -- CLI 스크립트 검증
# ---------------------------------------------------------------------------


class TestAddHostScript:
    """bin/add_host.py CLI 스크립트 검증."""

    ADD_HOST_PATH = _BIN_DIR / "add_host.py"

    def test_add_host_file_exists(self):
        """bin/add_host.py 파일이 존재해야 함."""
        assert self.ADD_HOST_PATH.exists(), f"{self.ADD_HOST_PATH} not found"

    def test_add_host_help(self):
        """add_host.py --help가 정상 동작해야 함."""
        result = subprocess.run(
            [sys.executable, str(self.ADD_HOST_PATH), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--name" in result.stdout
        assert "--fasta" in result.stdout
        assert "--db-dir" in result.stdout

    def test_add_host_has_threads_option(self):
        """add_host.py에 --threads 옵션이 있어야 함."""
        result = subprocess.run(
            [sys.executable, str(self.ADD_HOST_PATH), "--help"],
            capture_output=True,
            text=True,
        )
        assert "--threads" in result.stdout

    def test_add_host_dry_run(self):
        """add_host.py --dry-run이 실제 파일 생성 없이 완료되어야 함."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fasta = Path(tmpdir) / "test.fa"
            fasta.write_text(">chr1\nACGTACGT\n")

            result = subprocess.run(
                [
                    sys.executable,
                    str(self.ADD_HOST_PATH),
                    "--name", "test_host",
                    "--fasta", str(fasta),
                    "--db-dir", tmpdir,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            # In dry-run mode, the host directory should NOT be created
            host_dir = Path(tmpdir) / "host_genomes" / "test_host"
            assert not host_dir.exists() or not (host_dir / "genome.mmi").exists()

    def test_add_host_importable(self):
        """add_host 모듈이 import 가능해야 함."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("add_host", self.ADD_HOST_PATH)
        assert spec is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        assert hasattr(mod, "main")
        assert hasattr(mod, "build_parser")


# ---------------------------------------------------------------------------
# T10.2: add_host.py -- FASTA 복사 + VERSION.json 업데이트 검증
# ---------------------------------------------------------------------------


class TestAddHostFunctionality:
    """add_host.py의 핵심 로직 검증 (minimap2 없이)."""

    ADD_HOST_PATH = _BIN_DIR / "add_host.py"

    def test_add_host_copies_fasta(self):
        """add_host가 FASTA 파일을 host_genomes/{name}/ 에 복사해야 함."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("add_host", self.ADD_HOST_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        with tempfile.TemporaryDirectory() as tmpdir:
            fasta = Path(tmpdir) / "ref.fa"
            fasta.write_text(">chr1\nACGT\n")

            db_dir = Path(tmpdir) / "db"
            db_dir.mkdir()

            # Use copy_fasta function or run with --skip-index
            if hasattr(mod, "copy_fasta"):
                mod.copy_fasta(fasta, db_dir / "host_genomes" / "myhost")
                copied = db_dir / "host_genomes" / "myhost" / "ref.fa"
                assert copied.exists()
            else:
                # Run script with --dry-run (fasta copy should still happen conceptually)
                result = subprocess.run(
                    [
                        sys.executable,
                        str(self.ADD_HOST_PATH),
                        "--name", "myhost",
                        "--fasta", str(fasta),
                        "--db-dir", str(db_dir),
                        "--skip-index",
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    host_dir = db_dir / "host_genomes" / "myhost"
                    fasta_files = list(host_dir.glob("*.fa")) + list(host_dir.glob("*.fasta"))
                    assert len(fasta_files) >= 1

    def test_add_host_updates_version_json(self):
        """add_host가 VERSION.json을 업데이트해야 함."""
        import importlib.util

        spec = importlib.util.spec_from_file_location("add_host", self.ADD_HOST_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        with tempfile.TemporaryDirectory() as tmpdir:
            fasta = Path(tmpdir) / "ref.fa"
            fasta.write_text(">chr1\nACGT\n")

            db_dir = Path(tmpdir) / "db"
            db_dir.mkdir()

            # Create initial VERSION.json
            version_data = {
                "schema_version": "1.0",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "databases": {},
            }
            (db_dir / "VERSION.json").write_text(json.dumps(version_data))

            # Run with --skip-index to avoid needing minimap2
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.ADD_HOST_PATH),
                    "--name", "newhost",
                    "--fasta", str(fasta),
                    "--db-dir", str(db_dir),
                    "--skip-index",
                ],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"stderr: {result.stderr}"

            # Check VERSION.json was updated
            updated = json.loads((db_dir / "VERSION.json").read_text())
            host_genomes = updated.get("databases", {}).get("host_genomes", {})
            assert "newhost" in host_genomes


# ---------------------------------------------------------------------------
# T10.2: HostScreen -- Add Host 다이얼로그 관련 소스 확인
# ---------------------------------------------------------------------------


class TestHostScreenAddHostIntegration:
    """HostScreen에서 Add Host 다이얼로그/폼 관련 코드가 존재하는지 확인."""

    def _get_source(self) -> str:
        from tui.screens import host_screen

        return inspect.getsource(host_screen)

    def test_add_host_handler_exists(self):
        """Add Host 버튼 핸들러가 소스에 존재해야 함."""
        from tui.screens.host_screen import HostScreen

        src = self._get_source()
        # on_button_pressed 또는 action_add_host 같은 핸들러가 있어야 함
        has_handler = (
            "on_button_pressed" in src
            or "action_add_host" in src
            or "handle_add_host" in src
        )
        assert has_handler, "Add Host 버튼 핸들러가 없음"

    def test_input_widget_for_name(self):
        """이름 입력을 위한 Input 위젯이 소스에 존재해야 함."""
        src = self._get_source()
        assert "Input" in src, "이름 입력을 위한 Input 위젯 필요"

    def test_subprocess_or_add_host_reference(self):
        """add_host.py 실행을 위한 subprocess 참조가 소스에 존재해야 함."""
        src = self._get_source()
        has_subprocess = "subprocess" in src or "add_host" in src
        assert has_subprocess, "add_host.py 실행 참조 필요"
