# @TASK T-MULTI-HOST - Multi-host genome selection tests
# @SPEC docs/planning/02-trd.md#host_genomes
# @TEST tests/test_host_db.py
"""
Tests for multi-host genome DB management.

Covers:
  - HostDBManager: list/add/remove/get_paths/build_combined_index
  - Comma-separated host parsing
  - HOST_INDEX .nf file validation (cat + minimap2 for multiple genomes)
"""

from __future__ import annotations

import gzip
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure bin/ is importable
import sys

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "bin")
)

from host_db_manager import HostDBManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_dir(tmp_path: Path) -> Path:
    """Create a temporary database directory structure."""
    host_dir = tmp_path / "host_genomes"
    host_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def populated_db(db_dir: Path) -> Path:
    """Create a DB with two host genomes (tmol, zmor) pre-registered."""
    host_base = db_dir / "host_genomes"

    for nickname, species in [
        ("tmol", "Tenebrio molitor"),
        ("zmor", "Zophobas morio"),
    ]:
        d = host_base / nickname
        d.mkdir(parents=True)

        # Create a fake gzipped FASTA
        fasta_path = d / "genome.fa.gz"
        with gzip.open(fasta_path, "wt") as f:
            f.write(f">{nickname}_chr1\nACGTACGTACGT\n")

        # Create a fake .mmi index
        (d / "genome.mmi").write_bytes(b"\x00" * 64)

        # Create info.json
        info = {
            "nickname": nickname,
            "species": species,
            "added": "2026-03-24",
        }
        (d / "info.json").write_text(json.dumps(info))

    # Create _index.json
    index_data = {"tmol": "Tenebrio molitor", "zmor": "Zophobas morio"}
    (host_base / "_index.json").write_text(json.dumps(index_data))

    return db_dir


# ---------------------------------------------------------------------------
# HostDBManager.list_hosts
# ---------------------------------------------------------------------------


class TestListHosts:
    """Tests for HostDBManager.list_hosts()."""

    def test_list_hosts_empty_db(self, db_dir: Path) -> None:
        mgr = HostDBManager(db_dir)
        hosts = mgr.list_hosts()
        assert hosts == []

    def test_list_hosts_populated(self, populated_db: Path) -> None:
        mgr = HostDBManager(populated_db)
        hosts = mgr.list_hosts()

        assert len(hosts) == 2

        nicknames = {h["nickname"] for h in hosts}
        assert nicknames == {"tmol", "zmor"}

    def test_list_hosts_contains_expected_keys(self, populated_db: Path) -> None:
        mgr = HostDBManager(populated_db)
        hosts = mgr.list_hosts()

        for host in hosts:
            assert "nickname" in host
            assert "species" in host
            assert "indexed" in host
            assert "size_mb" in host

    def test_list_hosts_indexed_true(self, populated_db: Path) -> None:
        mgr = HostDBManager(populated_db)
        hosts = mgr.list_hosts()

        for host in hosts:
            assert host["indexed"] is True

    def test_list_hosts_no_index(self, db_dir: Path) -> None:
        """Host without .mmi file should show indexed=False."""
        d = db_dir / "host_genomes" / "noindex"
        d.mkdir(parents=True)
        fasta_path = d / "genome.fa.gz"
        with gzip.open(fasta_path, "wt") as f:
            f.write(">chr1\nACGT\n")
        info = {"nickname": "noindex", "species": "Test species", "added": "2026-03-24"}
        (d / "info.json").write_text(json.dumps(info))

        mgr = HostDBManager(db_dir)
        hosts = mgr.list_hosts()
        assert len(hosts) == 1
        assert hosts[0]["indexed"] is False

    def test_list_hosts_no_host_genomes_dir(self, tmp_path: Path) -> None:
        """If host_genomes/ does not exist, return empty list."""
        mgr = HostDBManager(tmp_path)
        assert mgr.list_hosts() == []


# ---------------------------------------------------------------------------
# HostDBManager.add_host
# ---------------------------------------------------------------------------


class TestAddHost:
    """Tests for HostDBManager.add_host()."""

    def test_add_host_creates_directory(self, db_dir: Path, tmp_path: Path) -> None:
        fasta = tmp_path / "ref.fa.gz"
        with gzip.open(fasta, "wt") as f:
            f.write(">chr1\nACGTACGT\n")

        mgr = HostDBManager(db_dir)
        with patch("host_db_manager.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            mock_sub.which = MagicMock(return_value="/usr/bin/minimap2")
            mgr.add_host("human", "Homo sapiens", fasta, threads=4)

        host_dir = db_dir / "host_genomes" / "human"
        assert host_dir.is_dir()
        assert (host_dir / "genome.fa.gz").exists()
        assert (host_dir / "info.json").exists()

    def test_add_host_info_json_content(self, db_dir: Path, tmp_path: Path) -> None:
        fasta = tmp_path / "ref.fa.gz"
        with gzip.open(fasta, "wt") as f:
            f.write(">chr1\nACGT\n")

        mgr = HostDBManager(db_dir)
        with patch("host_db_manager.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            mock_sub.which = MagicMock(return_value="/usr/bin/minimap2")
            mgr.add_host("human", "Homo sapiens", fasta)

        info = json.loads((db_dir / "host_genomes" / "human" / "info.json").read_text())
        assert info["nickname"] == "human"
        assert info["species"] == "Homo sapiens"
        assert "added" in info

    def test_add_host_updates_index_json(self, db_dir: Path, tmp_path: Path) -> None:
        fasta = tmp_path / "ref.fa.gz"
        with gzip.open(fasta, "wt") as f:
            f.write(">chr1\nACGT\n")

        mgr = HostDBManager(db_dir)
        with patch("host_db_manager.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            mock_sub.which = MagicMock(return_value="/usr/bin/minimap2")
            mgr.add_host("human", "Homo sapiens", fasta)

        idx = json.loads((db_dir / "host_genomes" / "_index.json").read_text())
        assert idx["human"] == "Homo sapiens"

    def test_add_host_fasta_not_found(self, db_dir: Path) -> None:
        mgr = HostDBManager(db_dir)
        with pytest.raises(FileNotFoundError):
            mgr.add_host("bad", "Bad Species", Path("/nonexistent/ref.fa.gz"))

    def test_add_host_skip_index(self, db_dir: Path, tmp_path: Path) -> None:
        fasta = tmp_path / "ref.fa.gz"
        with gzip.open(fasta, "wt") as f:
            f.write(">chr1\nACGT\n")

        mgr = HostDBManager(db_dir)
        with patch("host_db_manager.subprocess") as mock_sub:
            mgr.add_host("human", "Homo sapiens", fasta, skip_index=True)
            # subprocess.run should NOT be called for minimap2
            mock_sub.run.assert_not_called()


# ---------------------------------------------------------------------------
# HostDBManager.remove_host
# ---------------------------------------------------------------------------


class TestRemoveHost:
    """Tests for HostDBManager.remove_host()."""

    def test_remove_existing_host(self, populated_db: Path) -> None:
        mgr = HostDBManager(populated_db)
        mgr.remove_host("tmol")

        assert not (populated_db / "host_genomes" / "tmol").exists()

        idx = json.loads(
            (populated_db / "host_genomes" / "_index.json").read_text()
        )
        assert "tmol" not in idx

    def test_remove_nonexistent_host(self, populated_db: Path) -> None:
        mgr = HostDBManager(populated_db)
        with pytest.raises(KeyError):
            mgr.remove_host("nonexistent")

    def test_remove_updates_list(self, populated_db: Path) -> None:
        mgr = HostDBManager(populated_db)
        mgr.remove_host("zmor")

        hosts = mgr.list_hosts()
        assert len(hosts) == 1
        assert hosts[0]["nickname"] == "tmol"


# ---------------------------------------------------------------------------
# HostDBManager.get_host_paths
# ---------------------------------------------------------------------------


class TestGetHostPaths:
    """Tests for HostDBManager.get_host_paths()."""

    def test_get_single_host_path(self, populated_db: Path) -> None:
        mgr = HostDBManager(populated_db)
        paths = mgr.get_host_paths(["tmol"])

        assert len(paths) == 1
        assert paths[0].name == "genome.fa.gz"
        assert paths[0].exists()

    def test_get_multiple_host_paths(self, populated_db: Path) -> None:
        mgr = HostDBManager(populated_db)
        paths = mgr.get_host_paths(["tmol", "zmor"])

        assert len(paths) == 2
        for p in paths:
            assert p.name == "genome.fa.gz"
            assert p.exists()

    def test_get_host_paths_unknown(self, populated_db: Path) -> None:
        mgr = HostDBManager(populated_db)
        with pytest.raises(KeyError):
            mgr.get_host_paths(["nonexistent"])


# ---------------------------------------------------------------------------
# HostDBManager.build_combined_index
# ---------------------------------------------------------------------------


class TestBuildCombinedIndex:
    """Tests for HostDBManager.build_combined_index()."""

    def test_combined_index_creates_fasta(self, populated_db: Path, tmp_path: Path) -> None:
        mgr = HostDBManager(populated_db)
        output_dir = tmp_path / "combined"
        output_dir.mkdir()

        with patch("host_db_manager.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            mock_sub.which = MagicMock(return_value="/usr/bin/minimap2")
            result = mgr.build_combined_index(["tmol", "zmor"], output_dir)

        # Should return path to combined .mmi
        assert result.suffix == ".mmi"

    def test_combined_index_cache_reuse(self, populated_db: Path, tmp_path: Path) -> None:
        """Same combination should reuse cached index."""
        mgr = HostDBManager(populated_db)
        output_dir = tmp_path / "combined"
        output_dir.mkdir()

        # First call: builds index
        with patch("host_db_manager.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            mock_sub.which = MagicMock(return_value="/usr/bin/minimap2")
            result1 = mgr.build_combined_index(["tmol", "zmor"], output_dir)
            first_call_count = mock_sub.run.call_count

        # Create fake .mmi so cache detects it
        result1.touch()

        # Second call: should reuse
        with patch("host_db_manager.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            mock_sub.which = MagicMock(return_value="/usr/bin/minimap2")
            result2 = mgr.build_combined_index(["tmol", "zmor"], output_dir)
            # Should NOT call minimap2 again
            mock_sub.run.assert_not_called()

        assert result1 == result2

    def test_combined_index_different_order_same_cache(
        self, populated_db: Path, tmp_path: Path
    ) -> None:
        """Order of nicknames should not matter for caching."""
        mgr = HostDBManager(populated_db)
        output_dir = tmp_path / "combined"
        output_dir.mkdir()

        with patch("host_db_manager.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            mock_sub.which = MagicMock(return_value="/usr/bin/minimap2")
            r1 = mgr.build_combined_index(["tmol", "zmor"], output_dir)

        r1.touch()

        with patch("host_db_manager.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stderr="")
            mock_sub.which = MagicMock(return_value="/usr/bin/minimap2")
            r2 = mgr.build_combined_index(["zmor", "tmol"], output_dir)
            mock_sub.run.assert_not_called()

        assert r1 == r2


# ---------------------------------------------------------------------------
# Comma-separated host parsing
# ---------------------------------------------------------------------------


class TestCommaHostParsing:
    """Test parsing of comma-separated host strings."""

    def test_single_host(self) -> None:
        from host_db_manager import parse_host_string

        result = parse_host_string("tmol")
        assert result == ["tmol"]

    def test_multiple_hosts_comma(self) -> None:
        from host_db_manager import parse_host_string

        result = parse_host_string("tmol,zmor")
        assert result == ["tmol", "zmor"]

    def test_multiple_hosts_with_spaces(self) -> None:
        from host_db_manager import parse_host_string

        result = parse_host_string("tmol, zmor , human")
        assert result == ["tmol", "zmor", "human"]

    def test_none_returns_empty(self) -> None:
        from host_db_manager import parse_host_string

        result = parse_host_string("none")
        assert result == []

    def test_empty_string_returns_empty(self) -> None:
        from host_db_manager import parse_host_string

        result = parse_host_string("")
        assert result == []

    def test_deduplication(self) -> None:
        from host_db_manager import parse_host_string

        result = parse_host_string("tmol,tmol,zmor")
        assert result == ["tmol", "zmor"]


# ---------------------------------------------------------------------------
# HOST_INDEX .nf file validation
# ---------------------------------------------------------------------------


class TestHostRemovalNf:
    """Validate that host_removal.nf contains correct multi-genome logic."""

    @pytest.fixture
    def nf_content(self) -> str:
        nf_path = Path(__file__).resolve().parents[1] / "modules" / "local" / "host_removal.nf"
        return nf_path.read_text()

    def test_host_index_accepts_multiple_genomes(self, nf_content: str) -> None:
        """HOST_INDEX input should accept multiple genome files."""
        assert "path(host_genomes)" in nf_content or "path host_genomes" in nf_content

    def test_host_index_cat_command(self, nf_content: str) -> None:
        """HOST_INDEX should concatenate multiple genomes with cat."""
        assert "cat" in nf_content

    def test_host_index_minimap2_combined(self, nf_content: str) -> None:
        """HOST_INDEX should build combined minimap2 index."""
        assert "minimap2" in nf_content
        assert "combined_host" in nf_content

    def test_host_index_output_combined_mmi(self, nf_content: str) -> None:
        """HOST_INDEX output should be combined_host.mmi."""
        assert "combined_host.mmi" in nf_content


# ---------------------------------------------------------------------------
# main.nf host parsing validation
# ---------------------------------------------------------------------------


class TestMainNfHostParsing:
    """Validate that main.nf correctly parses comma-separated hosts."""

    @pytest.fixture
    def main_nf_content(self) -> str:
        nf_path = Path(__file__).resolve().parents[1] / "main.nf"
        return nf_path.read_text()

    def test_main_nf_tokenize_host(self, main_nf_content: str) -> None:
        """main.nf should tokenize params.host by comma."""
        assert "tokenize" in main_nf_content or "split" in main_nf_content

    def test_main_nf_collect_host_fastas(self, main_nf_content: str) -> None:
        """main.nf should collect host genome paths."""
        assert "collect" in main_nf_content
