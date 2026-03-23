"""Tests for geNomad module outputs and parse_genomad.py script.

# @TASK T3.1 - geNomad ML virus detection module tests
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/modules/test_genomad.py
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = PROJECT_ROOT / "bin"
PARSE_GENOMAD_SCRIPT = BIN_DIR / "parse_genomad.py"
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
GENOMAD_NF = MODULES_DIR / "genomad.nf"

# Expected TSV columns from parse_genomad.py
EXPECTED_COLUMNS = [
    "seq_id",
    "length",
    "detection_method",
    "detection_score",
    "taxonomy",
    "viral_hallmark_count",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_genomad_virus_summary_tsv(tmp_dir: Path) -> Path:
    """Create a realistic mock geNomad *_virus_summary.tsv file.

    Based on geNomad end-to-end output format.
    Columns: seq_name, length, topology, coordinates, n_genes,
             genetic_code, virus_score, taxonomy, n_hallmarks
    """
    tsv_path = tmp_dir / "sample1_virus_summary.tsv"
    header = (
        "seq_name\tlength\ttopology\tcoordinates\tn_genes\t"
        "genetic_code\tvirus_score\ttaxonomy\tn_hallmarks"
    )
    rows = [
        "contig_1\t15000\tlinear\t1-15000\t12\t11\t0.95\tViruses;Caudoviricetes;Crassvirales\t5",
        "contig_2\t8000\tlinear\t1-8000\t6\t11\t0.82\tViruses;Caudoviricetes\t3",
        "contig_3\t3000\tlinear\t1-3000\t3\t11\t0.55\tUnclassified\t0",
        "contig_4\t25000\tcircular\t1-25000\t20\t11\t0.99\tViruses;Phixviricota\t8",
        "contig_5\t5000\tlinear\t1-5000\t4\t11\t0.71\tViruses;Caudoviricetes;Crassvirales;Intestiviridae\t2",
    ]
    content = header + "\n" + "\n".join(rows) + "\n"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_genomad_empty_tsv(tmp_dir: Path) -> Path:
    """Create an empty (header-only) geNomad virus_summary.tsv."""
    tsv_path = tmp_dir / "empty_virus_summary.tsv"
    header = (
        "seq_name\tlength\ttopology\tcoordinates\tn_genes\t"
        "genetic_code\tvirus_score\ttaxonomy\tn_hallmarks"
    )
    tsv_path.write_text(header + "\n")
    return tsv_path


# ---------------------------------------------------------------------------
# Test: genomad.nf file structure
# ---------------------------------------------------------------------------
class TestGenomadNextflow:
    """Tests for genomad.nf Nextflow process definition."""

    @pytest.mark.unit
    def test_genomad_nf_exists(self) -> None:
        """genomad.nf file must exist."""
        assert GENOMAD_NF.exists(), f"genomad.nf not found at {GENOMAD_NF}"

    @pytest.mark.unit
    def test_genomad_nf_contains_process(self) -> None:
        """genomad.nf must define a process named GENOMAD_DETECT."""
        content = GENOMAD_NF.read_text()
        assert "process GENOMAD_DETECT" in content

    @pytest.mark.unit
    def test_genomad_nf_has_end_to_end_command(self) -> None:
        """genomad.nf script block must contain 'genomad end-to-end' command."""
        content = GENOMAD_NF.read_text()
        assert "genomad end-to-end" in content

    @pytest.mark.unit
    def test_genomad_nf_has_db_input(self) -> None:
        """genomad.nf must accept a database path as input."""
        content = GENOMAD_NF.read_text()
        assert "path(db)" in content or "path(genomad_db)" in content

    @pytest.mark.unit
    def test_genomad_nf_has_cleanup_flag(self) -> None:
        """genomad.nf must use --cleanup flag to save disk space."""
        content = GENOMAD_NF.read_text()
        assert "--cleanup" in content

    @pytest.mark.unit
    def test_genomad_nf_has_threads_param(self) -> None:
        """genomad.nf must pass thread count to geNomad."""
        content = GENOMAD_NF.read_text()
        assert "task.cpus" in content

    @pytest.mark.unit
    def test_genomad_nf_has_stub_block(self) -> None:
        """genomad.nf must retain a stub block for dry-run testing."""
        content = GENOMAD_NF.read_text()
        assert "stub:" in content

    @pytest.mark.unit
    def test_genomad_nf_has_tag_annotations(self) -> None:
        """genomad.nf must have @TASK and @SPEC TAG annotations."""
        content = GENOMAD_NF.read_text()
        assert "@TASK" in content
        assert "@SPEC" in content

    @pytest.mark.unit
    def test_genomad_nf_outputs_summary_and_fasta(self) -> None:
        """genomad.nf must emit virus_summary.tsv and virus.fna outputs."""
        content = GENOMAD_NF.read_text()
        assert "_virus_summary.tsv" in content
        assert "_virus.fna" in content


# ---------------------------------------------------------------------------
# Test: parse_genomad.py exists and is importable
# ---------------------------------------------------------------------------
class TestParseGenomadScript:
    """Tests for bin/parse_genomad.py script existence."""

    @pytest.mark.unit
    def test_parse_genomad_script_exists(self) -> None:
        """parse_genomad.py must exist in bin/."""
        assert PARSE_GENOMAD_SCRIPT.exists(), (
            f"parse_genomad.py not found at {PARSE_GENOMAD_SCRIPT}"
        )

    @pytest.mark.unit
    def test_parse_genomad_is_importable(self) -> None:
        """parse_genomad.py must be importable as a Python module."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            import parse_genomad  # noqa: F401
        finally:
            sys.path = original_path


# ---------------------------------------------------------------------------
# Test: parse_genomad.py parsing logic
# ---------------------------------------------------------------------------
class TestParseGenomadParsing:
    """Tests for geNomad TSV parsing and standard detection TSV generation."""

    def _import_parse_genomad(self):
        """Helper to import parse_genomad from bin/."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            # Force reimport to avoid stale module cache
            if "parse_genomad" in sys.modules:
                del sys.modules["parse_genomad"]
            import parse_genomad
            return parse_genomad
        finally:
            sys.path = original_path

    @pytest.mark.unit
    def test_parse_virus_summary(
        self, mock_genomad_virus_summary_tsv: Path,
    ) -> None:
        """parse_genomad_tsv() correctly parses geNomad virus_summary.tsv."""
        mod = self._import_parse_genomad()
        rows = mod.parse_genomad_tsv(mock_genomad_virus_summary_tsv)

        # Should return all 5 rows (no score filtering by default in parse fn)
        assert len(rows) == 5

        first = rows[0]
        assert first["seq_id"] == "contig_1"
        assert first["length"] == 15000
        assert first["detection_method"] == "genomad"
        assert abs(first["detection_score"] - 0.95) < 1e-4
        assert first["taxonomy"] == "Viruses;Caudoviricetes;Crassvirales"
        assert first["viral_hallmark_count"] == 5

    @pytest.mark.unit
    def test_score_filtering_default(
        self, mock_genomad_virus_summary_tsv: Path,
    ) -> None:
        """filter_by_score() with default min_score=0.7 filters low-score entries."""
        mod = self._import_parse_genomad()
        rows = mod.parse_genomad_tsv(mock_genomad_virus_summary_tsv)
        filtered = mod.filter_by_score(rows, min_score=0.7)

        # contig_3 has score 0.55, should be excluded
        # Remaining: contig_1 (0.95), contig_2 (0.82), contig_4 (0.99), contig_5 (0.71)
        assert len(filtered) == 4
        seq_ids = [r["seq_id"] for r in filtered]
        assert "contig_3" not in seq_ids
        assert "contig_1" in seq_ids
        assert "contig_5" in seq_ids

    @pytest.mark.unit
    def test_score_filtering_strict(
        self, mock_genomad_virus_summary_tsv: Path,
    ) -> None:
        """filter_by_score() with min_score=0.9 keeps only high-confidence hits."""
        mod = self._import_parse_genomad()
        rows = mod.parse_genomad_tsv(mock_genomad_virus_summary_tsv)
        filtered = mod.filter_by_score(rows, min_score=0.9)

        # Only contig_1 (0.95) and contig_4 (0.99)
        assert len(filtered) == 2
        seq_ids = [r["seq_id"] for r in filtered]
        assert "contig_1" in seq_ids
        assert "contig_4" in seq_ids

    @pytest.mark.unit
    def test_output_columns_format(
        self, mock_genomad_virus_summary_tsv: Path,
    ) -> None:
        """Parsed rows must contain exactly the expected columns."""
        mod = self._import_parse_genomad()
        rows = mod.parse_genomad_tsv(mock_genomad_virus_summary_tsv)

        for row in rows:
            assert set(row.keys()) == set(EXPECTED_COLUMNS), (
                f"Unexpected columns: {set(row.keys())} != {set(EXPECTED_COLUMNS)}"
            )

    @pytest.mark.unit
    def test_empty_input_returns_empty_list(
        self, mock_genomad_empty_tsv: Path,
    ) -> None:
        """parse_genomad_tsv() returns empty list for header-only TSV."""
        mod = self._import_parse_genomad()
        rows = mod.parse_genomad_tsv(mock_genomad_empty_tsv)

        assert rows == []

    @pytest.mark.unit
    def test_length_is_integer(
        self, mock_genomad_virus_summary_tsv: Path,
    ) -> None:
        """length column must be an integer."""
        mod = self._import_parse_genomad()
        rows = mod.parse_genomad_tsv(mock_genomad_virus_summary_tsv)

        for row in rows:
            assert isinstance(row["length"], int)

    @pytest.mark.unit
    def test_viral_hallmark_count_is_integer(
        self, mock_genomad_virus_summary_tsv: Path,
    ) -> None:
        """viral_hallmark_count must be an integer."""
        mod = self._import_parse_genomad()
        rows = mod.parse_genomad_tsv(mock_genomad_virus_summary_tsv)

        for row in rows:
            assert isinstance(row["viral_hallmark_count"], int)


# ---------------------------------------------------------------------------
# Test: parse_genomad.py CLI
# ---------------------------------------------------------------------------
class TestParseGenomadCLI:
    """Tests for parse_genomad.py command-line interface."""

    @pytest.mark.unit
    def test_cli_produces_tsv(
        self,
        tmp_dir: Path,
        mock_genomad_virus_summary_tsv: Path,
    ) -> None:
        """CLI produces a valid TSV with correct header and filtered rows."""
        output_tsv = tmp_dir / "detection_genomad.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_GENOMAD_SCRIPT),
                str(mock_genomad_virus_summary_tsv),
                "--output",
                str(output_tsv),
                "--min-score",
                "0.7",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"parse_genomad.py failed: {result.stderr}"
        )
        assert output_tsv.exists(), "Output TSV not created"

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        # Header columns check
        assert list(rows[0].keys()) == EXPECTED_COLUMNS

        # contig_3 (score=0.55) should be filtered out
        assert len(rows) == 4
        seq_ids = [r["seq_id"] for r in rows]
        assert "contig_3" not in seq_ids

    @pytest.mark.unit
    def test_cli_empty_input(
        self,
        tmp_dir: Path,
        mock_genomad_empty_tsv: Path,
    ) -> None:
        """CLI handles empty input gracefully, producing header-only TSV."""
        output_tsv = tmp_dir / "detection_genomad_empty.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_GENOMAD_SCRIPT),
                str(mock_genomad_empty_tsv),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"parse_genomad.py failed: {result.stderr}"
        )
        assert output_tsv.exists()

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        assert len(rows) == 0

    @pytest.mark.unit
    def test_cli_default_min_score(
        self,
        tmp_dir: Path,
        mock_genomad_virus_summary_tsv: Path,
    ) -> None:
        """CLI uses default --min-score 0.7 when not specified."""
        output_tsv = tmp_dir / "detection_genomad_default.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_GENOMAD_SCRIPT),
                str(mock_genomad_virus_summary_tsv),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        # Default 0.7 filter: contig_3 (0.55) excluded
        assert len(rows) == 4

    @pytest.mark.unit
    def test_cli_nonexistent_file(self, tmp_dir: Path) -> None:
        """CLI returns non-zero exit code for missing input file."""
        output_tsv = tmp_dir / "out.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_GENOMAD_SCRIPT),
                "/nonexistent/path.tsv",
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0

    @pytest.mark.unit
    def test_cli_output_values_numeric(
        self,
        tmp_dir: Path,
        mock_genomad_virus_summary_tsv: Path,
    ) -> None:
        """Numeric columns in CLI output must be parseable as numbers."""
        output_tsv = tmp_dir / "detection_genomad_numeric.tsv"

        subprocess.run(
            [
                sys.executable,
                str(PARSE_GENOMAD_SCRIPT),
                str(mock_genomad_virus_summary_tsv),
                "--output",
                str(output_tsv),
                "--min-score",
                "0.0",
            ],
            capture_output=True,
            text=True,
        )

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                float(row["length"])
                float(row["detection_score"])
                int(row["viral_hallmark_count"])
