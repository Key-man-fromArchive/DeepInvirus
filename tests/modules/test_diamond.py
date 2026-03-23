"""Tests for Diamond blastx module and parse_diamond.py script.

# @TASK T3.2 - Diamond blastx 모듈 테스트
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/modules/test_diamond.py
"""

from __future__ import annotations

import csv
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = PROJECT_ROOT / "bin"
PARSE_DIAMOND_SCRIPT = BIN_DIR / "parse_diamond.py"
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
DIAMOND_NF = MODULES_DIR / "diamond.nf"

# Expected TSV columns from parse_diamond.py
EXPECTED_COLUMNS = [
    "seq_id",
    "subject_id",
    "pident",
    "length",
    "evalue",
    "bitscore",
    "taxid",
    "detection_method",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_blast6_tsv(tmp_dir: Path) -> Path:
    """Create a mock Diamond blast6 output TSV file.

    Contains multiple hits for the same query to test best-hit extraction.
    Format: qseqid sseqid pident length mismatch gapopen qstart qend
            sstart send evalue bitscore staxids
    """
    content = textwrap.dedent("""\
        contig_1\tUniRef90_P12345\t95.0\t500\t25\t0\t1\t1500\t1\t500\t1e-50\t800\t12345
        contig_1\tUniRef90_P67890\t80.0\t450\t90\t2\t1\t1350\t1\t450\t1e-30\t500\t67890
        contig_2\tUniRef90_Q11111\t70.0\t300\t90\t1\t1\t900\t1\t300\t1e-10\t200\t11111
        contig_2\tUniRef90_Q22222\t88.5\t400\t46\t0\t1\t1200\t1\t400\t1e-40\t650\t22222
        contig_3\tUniRef90_R99999\t60.0\t100\t40\t0\t1\t300\t1\t100\t1e-3\t40\t99999
    """)
    tsv_path = tmp_dir / "sample1.diamond.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_blast6_single_hit(tmp_dir: Path) -> Path:
    """Create a blast6 TSV with a single hit per query."""
    content = textwrap.dedent("""\
        contig_A\tUniRef90_X00001\t99.0\t600\t6\t0\t1\t1800\t1\t600\t1e-100\t1200\t54321
    """)
    tsv_path = tmp_dir / "single.diamond.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_blast6_multi_taxid(tmp_dir: Path) -> Path:
    """Create a blast6 TSV where staxids has semicolon-separated taxids."""
    content = textwrap.dedent("""\
        contig_M\tUniRef90_M00001\t90.0\t400\t40\t0\t1\t1200\t1\t400\t1e-60\t900\t111;222;333
    """)
    tsv_path = tmp_dir / "multi_taxid.diamond.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_blast6_empty(tmp_dir: Path) -> Path:
    """Create an empty Diamond output file (no hits)."""
    tsv_path = tmp_dir / "empty.diamond.tsv"
    tsv_path.write_text("")
    return tsv_path


# ---------------------------------------------------------------------------
# Test: diamond.nf file structure
# ---------------------------------------------------------------------------
class TestDiamondNextflow:
    """Tests for diamond.nf Nextflow process definition."""

    @pytest.mark.unit
    def test_diamond_nf_exists(self) -> None:
        """diamond.nf file must exist."""
        assert DIAMOND_NF.exists(), f"diamond.nf not found at {DIAMOND_NF}"

    @pytest.mark.unit
    def test_diamond_nf_contains_process(self) -> None:
        """diamond.nf must define a process named DIAMOND_BLASTX."""
        content = DIAMOND_NF.read_text()
        assert "process DIAMOND_BLASTX" in content

    @pytest.mark.unit
    def test_diamond_nf_has_real_command(self) -> None:
        """diamond.nf script block must contain the actual diamond blastx command."""
        content = DIAMOND_NF.read_text()
        assert "diamond blastx" in content

    @pytest.mark.unit
    def test_diamond_nf_has_db_input(self) -> None:
        """diamond.nf must accept a database path as input."""
        content = DIAMOND_NF.read_text()
        assert "path(db)" in content or "params.db_dir" in content

    @pytest.mark.unit
    def test_diamond_nf_has_required_outfmt_fields(self) -> None:
        """diamond.nf must specify outfmt 6 with required fields."""
        content = DIAMOND_NF.read_text()
        required_fields = [
            "qseqid", "sseqid", "pident", "length",
            "mismatch", "gapopen", "qstart", "qend",
            "sstart", "send", "evalue", "bitscore", "staxids",
        ]
        for field in required_fields:
            assert field in content, f"Missing outfmt field: {field}"

    @pytest.mark.unit
    def test_diamond_nf_has_evalue_threshold(self) -> None:
        """diamond.nf must set an evalue threshold."""
        content = DIAMOND_NF.read_text()
        assert "--evalue" in content

    @pytest.mark.unit
    def test_diamond_nf_has_max_target_seqs(self) -> None:
        """diamond.nf must set max-target-seqs."""
        content = DIAMOND_NF.read_text()
        assert "--max-target-seqs" in content

    @pytest.mark.unit
    def test_diamond_nf_has_ultra_sensitive(self) -> None:
        """diamond.nf must support ultra-sensitive mode."""
        content = DIAMOND_NF.read_text()
        assert "--ultra-sensitive" in content

    @pytest.mark.unit
    def test_diamond_nf_has_threads(self) -> None:
        """diamond.nf must use task.cpus for threading."""
        content = DIAMOND_NF.read_text()
        assert "--threads" in content or "task.cpus" in content

    @pytest.mark.unit
    def test_diamond_nf_has_stub_block(self) -> None:
        """diamond.nf must retain a stub block for dry-run testing."""
        content = DIAMOND_NF.read_text()
        assert "stub:" in content

    @pytest.mark.unit
    def test_diamond_nf_has_tag_annotations(self) -> None:
        """diamond.nf must have @TASK and @SPEC TAG annotations."""
        content = DIAMOND_NF.read_text()
        assert "@TASK" in content
        assert "@SPEC" in content


# ---------------------------------------------------------------------------
# Test: parse_diamond.py exists and is importable
# ---------------------------------------------------------------------------
class TestParseDiamondScript:
    """Tests for bin/parse_diamond.py script."""

    @pytest.mark.unit
    def test_parse_diamond_script_exists(self) -> None:
        """parse_diamond.py must exist in bin/."""
        assert PARSE_DIAMOND_SCRIPT.exists(), (
            f"parse_diamond.py not found at {PARSE_DIAMOND_SCRIPT}"
        )

    @pytest.mark.unit
    def test_parse_diamond_is_importable(self) -> None:
        """parse_diamond.py must be importable as a Python module."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            import parse_diamond  # noqa: F401
        finally:
            sys.path = original_path


# ---------------------------------------------------------------------------
# Test: parse_diamond.py parsing logic
# ---------------------------------------------------------------------------
class TestParseDiamondParsing:
    """Tests for Diamond blast6 parsing and TSV generation."""

    def _import_parse_diamond(self):
        """Helper to import parse_diamond module."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            # Force reimport to avoid caching issues
            if "parse_diamond" in sys.modules:
                del sys.modules["parse_diamond"]
            import parse_diamond
            return parse_diamond
        finally:
            sys.path = original_path

    @pytest.mark.unit
    def test_parse_blast6_basic(self, mock_blast6_tsv: Path) -> None:
        """parse_blast6() must correctly parse blast6 format rows."""
        mod = self._import_parse_diamond()
        hits = mod.parse_blast6(mock_blast6_tsv)

        assert len(hits) == 5
        assert hits[0]["qseqid"] == "contig_1"
        assert hits[0]["sseqid"] == "UniRef90_P12345"
        assert float(hits[0]["pident"]) == 95.0
        assert float(hits[0]["bitscore"]) == 800.0

    @pytest.mark.unit
    def test_best_hit_extraction(self, mock_blast6_tsv: Path) -> None:
        """extract_best_hits() must keep only the hit with highest bitscore per query."""
        mod = self._import_parse_diamond()
        hits = mod.parse_blast6(mock_blast6_tsv)
        best = mod.extract_best_hits(hits)

        # contig_1: best bitscore=800 (P12345), contig_2: best=650 (Q22222),
        # contig_3: best=40 (R99999)
        assert len(best) == 3

        best_by_query = {h["qseqid"]: h for h in best}
        assert best_by_query["contig_1"]["sseqid"] == "UniRef90_P12345"
        assert float(best_by_query["contig_1"]["bitscore"]) == 800.0
        assert best_by_query["contig_2"]["sseqid"] == "UniRef90_Q22222"
        assert float(best_by_query["contig_2"]["bitscore"]) == 650.0
        assert best_by_query["contig_3"]["sseqid"] == "UniRef90_R99999"

    @pytest.mark.unit
    def test_bitscore_filtering_default(self, mock_blast6_tsv: Path) -> None:
        """Hits with bitscore < 50 (default) must be filtered out."""
        mod = self._import_parse_diamond()
        hits = mod.parse_blast6(mock_blast6_tsv)
        best = mod.extract_best_hits(hits)
        filtered = mod.filter_by_bitscore(best, min_bitscore=50)

        # contig_3 has bitscore=40, should be filtered out
        query_ids = [h["qseqid"] for h in filtered]
        assert "contig_1" in query_ids
        assert "contig_2" in query_ids
        assert "contig_3" not in query_ids

    @pytest.mark.unit
    def test_bitscore_filtering_custom(self, mock_blast6_tsv: Path) -> None:
        """Custom bitscore threshold must work correctly."""
        mod = self._import_parse_diamond()
        hits = mod.parse_blast6(mock_blast6_tsv)
        best = mod.extract_best_hits(hits)
        filtered = mod.filter_by_bitscore(best, min_bitscore=700)

        # Only contig_1 (800) passes threshold 700
        assert len(filtered) == 1
        assert filtered[0]["qseqid"] == "contig_1"

    @pytest.mark.unit
    def test_output_format(self, mock_blast6_tsv: Path) -> None:
        """to_detection_tsv() must produce rows with standard detection columns."""
        mod = self._import_parse_diamond()
        hits = mod.parse_blast6(mock_blast6_tsv)
        best = mod.extract_best_hits(hits)
        filtered = mod.filter_by_bitscore(best, min_bitscore=50)
        rows = mod.to_detection_tsv(filtered)

        assert len(rows) == 2  # contig_1 and contig_2

        for row in rows:
            for col in EXPECTED_COLUMNS:
                assert col in row, f"Missing column: {col}"
            assert row["detection_method"] == "diamond"

        # Check specific values
        row1 = [r for r in rows if r["seq_id"] == "contig_1"][0]
        assert row1["subject_id"] == "UniRef90_P12345"
        assert float(row1["pident"]) == 95.0
        assert float(row1["bitscore"]) == 800.0
        assert row1["taxid"] == "12345"

    @pytest.mark.unit
    def test_multi_taxid_takes_first(self, mock_blast6_multi_taxid: Path) -> None:
        """When staxids has semicolon-separated values, take the first taxid."""
        mod = self._import_parse_diamond()
        hits = mod.parse_blast6(mock_blast6_multi_taxid)
        best = mod.extract_best_hits(hits)
        filtered = mod.filter_by_bitscore(best, min_bitscore=50)
        rows = mod.to_detection_tsv(filtered)

        assert len(rows) == 1
        assert rows[0]["taxid"] == "111"

    @pytest.mark.unit
    def test_empty_input(self, mock_blast6_empty: Path) -> None:
        """Empty Diamond output must produce an empty result (no errors)."""
        mod = self._import_parse_diamond()
        hits = mod.parse_blast6(mock_blast6_empty)
        assert len(hits) == 0

        best = mod.extract_best_hits(hits)
        assert len(best) == 0

    @pytest.mark.unit
    def test_single_hit_per_query(self, mock_blast6_single_hit: Path) -> None:
        """Single hit per query should be retained as best hit."""
        mod = self._import_parse_diamond()
        hits = mod.parse_blast6(mock_blast6_single_hit)
        best = mod.extract_best_hits(hits)

        assert len(best) == 1
        assert best[0]["qseqid"] == "contig_A"
        assert float(best[0]["bitscore"]) == 1200.0

    @pytest.mark.unit
    def test_cli_output_tsv(
        self, tmp_dir: Path, mock_blast6_tsv: Path
    ) -> None:
        """CLI invocation must produce a valid TSV with correct header."""
        output_tsv = tmp_dir / "diamond_detection.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_DIAMOND_SCRIPT),
                str(mock_blast6_tsv),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"parse_diamond.py failed: {result.stderr}"
        )
        assert output_tsv.exists(), "Output TSV not created"

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        # contig_3 filtered out (bitscore 40 < 50 default)
        assert len(rows) == 2
        assert list(rows[0].keys()) == EXPECTED_COLUMNS

    @pytest.mark.unit
    def test_cli_custom_bitscore(
        self, tmp_dir: Path, mock_blast6_tsv: Path
    ) -> None:
        """CLI --min-bitscore flag must be respected."""
        output_tsv = tmp_dir / "diamond_filtered.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_DIAMOND_SCRIPT),
                str(mock_blast6_tsv),
                "--output",
                str(output_tsv),
                "--min-bitscore",
                "700",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"parse_diamond.py failed: {result.stderr}"
        )

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        # Only contig_1 (800) passes 700 threshold
        assert len(rows) == 1
        assert rows[0]["seq_id"] == "contig_1"

    @pytest.mark.unit
    def test_cli_empty_input(
        self, tmp_dir: Path, mock_blast6_empty: Path
    ) -> None:
        """CLI must handle empty input gracefully (produce header-only TSV)."""
        output_tsv = tmp_dir / "empty_output.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_DIAMOND_SCRIPT),
                str(mock_blast6_empty),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert output_tsv.exists()

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        assert len(rows) == 0

    @pytest.mark.unit
    def test_output_values_are_correct_types(
        self, tmp_dir: Path, mock_blast6_tsv: Path
    ) -> None:
        """Numeric columns in output TSV must be parseable as numbers."""
        output_tsv = tmp_dir / "types_check.tsv"

        subprocess.run(
            [
                sys.executable,
                str(PARSE_DIAMOND_SCRIPT),
                str(mock_blast6_tsv),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                # pident, length, evalue, bitscore should be numeric
                for col in ["pident", "length", "evalue", "bitscore"]:
                    try:
                        float(row[col])
                    except ValueError:
                        pytest.fail(
                            f"Column '{col}' value '{row[col]}' is not numeric"
                        )
                # detection_method must be 'diamond'
                assert row["detection_method"] == "diamond"
