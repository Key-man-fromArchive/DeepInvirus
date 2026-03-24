# @TASK T-DB-INDEX - Database indexer tests
# @SPEC docs/planning/04-database-design.md
# @TEST tests/test_db_indexer.py
"""
Tests for DBIndexer: index status checking and rebuild command generation.

Covers:
  - get_index_status() return structure validation
  - check_index_exists() for each component type
  - rebuild_index() command string generation (diamond, mmseqs2, minimap2, genomad)
  - get_source_file / get_index_file path resolution
  - Host genome inclusion in index status
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure bin/ is importable
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "bin")
)

from db_indexer import DBIndexer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_dir(tmp_path: Path) -> Path:
    """Create a temporary database directory with realistic structure."""
    # viral_protein
    vp = tmp_path / "viral_protein"
    vp.mkdir()
    (vp / "uniref90_viral.fasta.gz").write_bytes(b"\x1f\x8b" + b"\x00" * 20)
    (vp / "uniref90_viral.dmnd").write_bytes(b"DMND" + b"\x00" * 100)

    # viral_nucleotide
    vn = tmp_path / "viral_nucleotide"
    vn.mkdir()
    (vn / "refseq_viral.fna.gz").write_bytes(b"\x1f\x8b" + b"\x00" * 20)
    # mmseqs2 DB files
    mmseqs_db = vn / "refseq_viral_db"
    mmseqs_db.write_bytes(b"\x00" * 50)
    (vn / "refseq_viral_db.index").write_bytes(b"\x00" * 10)
    (vn / "refseq_viral_db.dbtype").write_bytes(b"\x00" * 4)

    # genomad_db (pre-built, directory with marker files)
    gd = tmp_path / "genomad_db"
    gd.mkdir()
    (gd / "genomad_db").write_bytes(b"\x00" * 100)
    (gd / "genomad_db.dbtype").write_bytes(b"\x00" * 4)
    (gd / "genomad_marker_metadata.tsv").write_text("marker\tdata\n")

    # taxonomy
    tx = tmp_path / "taxonomy"
    tx.mkdir()
    (tx / "names.dmp").write_text("1\t|\troot\t|\n")
    (tx / "nodes.dmp").write_text("1\t|\t1\t|\n")

    # host_genomes
    hg = tmp_path / "host_genomes"
    hg.mkdir()

    tmol = hg / "tenebrio_molitor"
    tmol.mkdir()
    (tmol / "genome.fa.gz").write_bytes(b"\x1f\x8b" + b"\x00" * 30)
    (tmol / "genome.mmi").write_bytes(b"\x00" * 200)
    (tmol / "info.json").write_text(json.dumps({
        "dbname": "tenebrio_molitor",
        "species": "Tenebrio molitor",
        "added": "2026-03-20",
    }))

    zmor = hg / "zophobas_morio"
    zmor.mkdir()
    (zmor / "genome.fa.gz").write_bytes(b"\x1f\x8b" + b"\x00" * 40)
    (zmor / "genome.mmi").write_bytes(b"\x00" * 300)
    (zmor / "info.json").write_text(json.dumps({
        "dbname": "zophobas_morio",
        "species": "Zophobas morio",
        "added": "2026-03-21",
    }))

    return tmp_path


@pytest.fixture
def db_dir_missing_index(tmp_path: Path) -> Path:
    """Create a DB dir where viral_protein has source but NO index."""
    vp = tmp_path / "viral_protein"
    vp.mkdir()
    (vp / "uniref90_viral.fasta.gz").write_bytes(b"\x1f\x8b" + b"\x00" * 20)
    # No .dmnd file -> index missing
    return tmp_path


@pytest.fixture
def indexer(db_dir: Path) -> DBIndexer:
    """DBIndexer with a fully populated test DB."""
    return DBIndexer(db_dir)


@pytest.fixture
def indexer_missing(db_dir_missing_index: Path) -> DBIndexer:
    """DBIndexer with missing index files."""
    return DBIndexer(db_dir_missing_index)


# ---------------------------------------------------------------------------
# get_index_status() tests
# ---------------------------------------------------------------------------


class TestGetIndexStatus:
    """Tests for DBIndexer.get_index_status()."""

    def test_returns_list(self, indexer: DBIndexer) -> None:
        """get_index_status() must return a list."""
        result = indexer.get_index_status()
        assert isinstance(result, list)

    def test_each_entry_has_required_keys(self, indexer: DBIndexer) -> None:
        """Each status entry must contain the required fields."""
        required_keys = {
            "component", "source", "index", "indexed", "size_mb", "tool",
            "rebuild_cmd",
        }
        result = indexer.get_index_status()
        assert len(result) > 0, "Expected at least one component"
        for entry in result:
            missing = required_keys - set(entry.keys())
            assert not missing, (
                f"Component '{entry.get('component', '?')}' missing keys: {missing}"
            )

    def test_viral_protein_entry(self, indexer: DBIndexer) -> None:
        """viral_protein must have tool=diamond and indexed=True when .dmnd exists."""
        result = indexer.get_index_status()
        vp = [e for e in result if e["component"] == "viral_protein"]
        assert len(vp) == 1
        entry = vp[0]
        assert entry["tool"] == "diamond"
        assert entry["indexed"] is True
        assert entry["size_mb"] >= 0  # test files are tiny; real DBs are large
        assert "uniref90_viral" in entry["source"]

    def test_viral_nucleotide_entry(self, indexer: DBIndexer) -> None:
        """viral_nucleotide must have tool=mmseqs2."""
        result = indexer.get_index_status()
        vn = [e for e in result if e["component"] == "viral_nucleotide"]
        assert len(vn) == 1
        entry = vn[0]
        assert entry["tool"] == "mmseqs2"
        assert entry["indexed"] is True

    def test_genomad_db_entry(self, indexer: DBIndexer) -> None:
        """genomad_db must have tool=pre-built."""
        result = indexer.get_index_status()
        gd = [e for e in result if e["component"] == "genomad_db"]
        assert len(gd) == 1
        entry = gd[0]
        assert entry["tool"] == "pre-built"
        assert entry["indexed"] is True

    def test_taxonomy_entry(self, indexer: DBIndexer) -> None:
        """taxonomy must have tool=N/A."""
        result = indexer.get_index_status()
        tx = [e for e in result if e["component"] == "taxonomy"]
        assert len(tx) == 1
        entry = tx[0]
        assert entry["tool"] == "N/A"
        assert entry["indexed"] is True

    def test_host_genomes_included(self, indexer: DBIndexer) -> None:
        """Host genomes must be included with host: prefix."""
        result = indexer.get_index_status()
        hosts = [e for e in result if e["component"].startswith("host:")]
        assert len(hosts) >= 2, f"Expected >= 2 host entries, got {len(hosts)}"

        host_names = [e["component"] for e in hosts]
        assert "host:tenebrio_molitor" in host_names
        assert "host:zophobas_morio" in host_names

        for h in hosts:
            assert h["tool"] == "minimap2"
            assert h["indexed"] is True

    def test_missing_index_detected(self, indexer_missing: DBIndexer) -> None:
        """When .dmnd is missing, indexed must be False."""
        result = indexer_missing.get_index_status()
        vp = [e for e in result if e["component"] == "viral_protein"]
        assert len(vp) == 1
        assert vp[0]["indexed"] is False


# ---------------------------------------------------------------------------
# check_index_exists() tests
# ---------------------------------------------------------------------------


class TestCheckIndexExists:
    """Tests for DBIndexer.check_index_exists()."""

    def test_viral_protein_exists(self, indexer: DBIndexer) -> None:
        assert indexer.check_index_exists("viral_protein") is True

    def test_viral_nucleotide_exists(self, indexer: DBIndexer) -> None:
        assert indexer.check_index_exists("viral_nucleotide") is True

    def test_genomad_db_exists(self, indexer: DBIndexer) -> None:
        assert indexer.check_index_exists("genomad_db") is True

    def test_taxonomy_exists(self, indexer: DBIndexer) -> None:
        assert indexer.check_index_exists("taxonomy") is True

    def test_host_exists(self, indexer: DBIndexer) -> None:
        assert indexer.check_index_exists("host:tenebrio_molitor") is True

    def test_missing_index(self, indexer_missing: DBIndexer) -> None:
        assert indexer_missing.check_index_exists("viral_protein") is False

    def test_unknown_component(self, indexer: DBIndexer) -> None:
        assert indexer.check_index_exists("nonexistent_db") is False


# ---------------------------------------------------------------------------
# rebuild_index() tests
# ---------------------------------------------------------------------------


class TestRebuildIndex:
    """Tests for DBIndexer.rebuild_index() command generation."""

    def test_viral_protein_uses_diamond(self, indexer: DBIndexer) -> None:
        """rebuild_index('viral_protein') must produce a diamond makedb command."""
        cmd = indexer.rebuild_index("viral_protein", threads=8)
        assert "diamond" in cmd
        assert "makedb" in cmd
        assert "--threads" in cmd or "-p" in cmd
        assert "8" in cmd

    def test_viral_nucleotide_uses_mmseqs(self, indexer: DBIndexer) -> None:
        """rebuild_index('viral_nucleotide') must produce an mmseqs createdb command."""
        cmd = indexer.rebuild_index("viral_nucleotide", threads=16)
        assert "mmseqs" in cmd
        assert "createdb" in cmd

    def test_host_uses_minimap2(self, indexer: DBIndexer) -> None:
        """rebuild_index('host:...') must produce a minimap2 -d command."""
        cmd = indexer.rebuild_index("host:tenebrio_molitor", threads=4)
        assert "minimap2" in cmd
        assert "-d" in cmd
        assert "-t" in cmd
        assert "4" in cmd

    def test_genomad_returns_download_cmd(self, indexer: DBIndexer) -> None:
        """rebuild_index('genomad_db') returns a genomad download-database command."""
        cmd = indexer.rebuild_index("genomad_db")
        assert "genomad" in cmd.lower() or "download" in cmd.lower()

    def test_taxonomy_returns_none_or_empty(self, indexer: DBIndexer) -> None:
        """taxonomy has no rebuild command (just download files)."""
        cmd = indexer.rebuild_index("taxonomy")
        # taxonomy rebuild is not applicable; returns empty or None-ish
        assert cmd is None or cmd == ""

    def test_unknown_component_raises(self, indexer: DBIndexer) -> None:
        """Unknown component should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown component"):
            indexer.rebuild_index("nonexistent_db")


# ---------------------------------------------------------------------------
# get_source_file / get_index_file tests
# ---------------------------------------------------------------------------


class TestSourceAndIndexFiles:
    """Tests for get_source_file() and get_index_file()."""

    def test_viral_protein_source(self, indexer: DBIndexer) -> None:
        src = indexer.get_source_file("viral_protein")
        assert src is not None
        assert "uniref90_viral" in src.name
        assert src.exists()

    def test_viral_protein_index(self, indexer: DBIndexer) -> None:
        idx = indexer.get_index_file("viral_protein")
        assert idx is not None
        assert idx.suffix == ".dmnd"
        assert idx.exists()

    def test_viral_nucleotide_source(self, indexer: DBIndexer) -> None:
        src = indexer.get_source_file("viral_nucleotide")
        assert src is not None
        assert src.exists()

    def test_viral_nucleotide_index(self, indexer: DBIndexer) -> None:
        idx = indexer.get_index_file("viral_nucleotide")
        assert idx is not None
        assert idx.exists()

    def test_host_source(self, indexer: DBIndexer) -> None:
        src = indexer.get_source_file("host:tenebrio_molitor")
        assert src is not None
        assert "genome.fa.gz" in src.name

    def test_host_index(self, indexer: DBIndexer) -> None:
        idx = indexer.get_index_file("host:tenebrio_molitor")
        assert idx is not None
        assert idx.suffix == ".mmi"

    def test_genomad_source_is_directory(self, indexer: DBIndexer) -> None:
        src = indexer.get_source_file("genomad_db")
        assert src is not None
        assert src.is_dir()

    def test_genomad_index_is_none(self, indexer: DBIndexer) -> None:
        """genomad has no separate index file (pre-built)."""
        idx = indexer.get_index_file("genomad_db")
        assert idx is None

    def test_taxonomy_source(self, indexer: DBIndexer) -> None:
        src = indexer.get_source_file("taxonomy")
        assert src is not None

    def test_taxonomy_index_is_none(self, indexer: DBIndexer) -> None:
        idx = indexer.get_index_file("taxonomy")
        assert idx is None

    def test_unknown_component_returns_none(self, indexer: DBIndexer) -> None:
        assert indexer.get_source_file("nonexistent") is None
        assert indexer.get_index_file("nonexistent") is None


# ---------------------------------------------------------------------------
# rebuild_all() tests
# ---------------------------------------------------------------------------


class TestRebuildAll:
    """Tests for DBIndexer.rebuild_all()."""

    def test_returns_list(self, indexer: DBIndexer) -> None:
        cmds = indexer.rebuild_all()
        assert isinstance(cmds, list)

    def test_fully_indexed_returns_empty(self, indexer: DBIndexer) -> None:
        """When all DBs are indexed, rebuild_all should return empty list."""
        cmds = indexer.rebuild_all()
        assert len(cmds) == 0

    def test_missing_index_included(self, indexer_missing: DBIndexer) -> None:
        """When viral_protein index is missing, rebuild_all should include it."""
        cmds = indexer_missing.rebuild_all()
        assert len(cmds) >= 1
        assert any("diamond" in c for c in cmds)


# ---------------------------------------------------------------------------
# DbScreen integration: column and button checks
# ---------------------------------------------------------------------------


class TestDbScreenIndexColumns:
    """Verify db_screen.py has the required index-related UI elements."""

    def test_db_screen_has_tool_column(self) -> None:
        """DataTable setup must include a 'Tool' column."""
        from tui.screens.db_screen import DbScreen

        screen = DbScreen.__new__(DbScreen)
        # Check the _setup_table method source or just instantiate
        import inspect
        source = inspect.getsource(DbScreen._setup_table)
        assert "Tool" in source, "_setup_table must add a 'Tool' column"

    def test_db_screen_has_index_column(self) -> None:
        """DataTable setup must include an 'Index' column."""
        from tui.screens.db_screen import DbScreen

        import inspect
        source = inspect.getsource(DbScreen._setup_table)
        assert "Index" in source, "_setup_table must add an 'Index' column"

    def test_db_screen_has_rebuild_index_button(self) -> None:
        """compose() must yield a Rebuild Index button."""
        from tui.screens.db_screen import DbScreen

        import inspect
        source = inspect.getsource(DbScreen.compose)
        assert "rebuild-index" in source or "Rebuild Index" in source

    def test_db_screen_has_rebuild_all_button(self) -> None:
        """compose() must yield a Rebuild All button."""
        from tui.screens.db_screen import DbScreen

        import inspect
        source = inspect.getsource(DbScreen.compose)
        assert "rebuild-all" in source or "Rebuild All" in source
