"""Tests for merge_detection.py - merging geNomad and Diamond detection results.

# @TASK T3.3 - Detection result merger tests
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @SPEC docs/planning/04-database-design.md#4.1-bigtable
# @TEST tests/modules/test_merge_detection.py
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
MERGE_DETECTION_SCRIPT = BIN_DIR / "merge_detection.py"
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
MERGE_DETECTION_NF = MODULES_DIR / "merge_detection.nf"

# Expected output columns from merge_detection.py
EXPECTED_COLUMNS = [
    "seq_id",
    "length",
    "detection_method",
    "detection_score",
    "taxonomy",
    "taxid",
    "subject_id",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_genomad_parsed_tsv(tmp_dir: Path) -> Path:
    """Create a mock parsed geNomad detection TSV (output of parse_genomad.py).

    Columns: seq_id, length, detection_method, detection_score, taxonomy,
             viral_hallmark_count
    """
    content = textwrap.dedent("""\
        seq_id\tlength\tdetection_method\tdetection_score\ttaxonomy\tviral_hallmark_count
        contig_1\t15000\tgenomad\t0.95\tViruses;Caudoviricetes;Crassvirales\t5
        contig_2\t8000\tgenomad\t0.82\tViruses;Caudoviricetes\t3
        contig_4\t25000\tgenomad\t0.99\tViruses;Phixviricota\t8
    """)
    tsv_path = tmp_dir / "detection_genomad.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_diamond_parsed_tsv(tmp_dir: Path) -> Path:
    """Create a mock parsed Diamond detection TSV (output of parse_diamond.py).

    Columns: seq_id, subject_id, pident, length, evalue, bitscore, taxid,
             detection_method
    """
    content = textwrap.dedent("""\
        seq_id\tsubject_id\tpident\tlength\tevalue\tbitscore\ttaxid\tdetection_method
        contig_1\tUniRef90_P12345\t95.0\t500\t1e-50\t800\t12345\tdiamond
        contig_3\tUniRef90_R99999\t88.5\t400\t1e-40\t650\t99999\tdiamond
    """)
    tsv_path = tmp_dir / "detection_diamond.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_genomad_empty_tsv(tmp_dir: Path) -> Path:
    """Create an empty (header-only) parsed geNomad TSV."""
    content = "seq_id\tlength\tdetection_method\tdetection_score\ttaxonomy\tviral_hallmark_count\n"
    tsv_path = tmp_dir / "empty_genomad.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_diamond_empty_tsv(tmp_dir: Path) -> Path:
    """Create an empty (header-only) parsed Diamond TSV."""
    content = "seq_id\tsubject_id\tpident\tlength\tevalue\tbitscore\ttaxid\tdetection_method\n"
    tsv_path = tmp_dir / "empty_diamond.tsv"
    tsv_path.write_text(content)
    return tsv_path


# ---------------------------------------------------------------------------
# Test: merge_detection.nf file structure
# ---------------------------------------------------------------------------
class TestMergeDetectionNextflow:
    """Tests for merge_detection.nf Nextflow process definition."""

    @pytest.mark.unit
    def test_merge_detection_nf_exists(self) -> None:
        """merge_detection.nf file must exist."""
        assert MERGE_DETECTION_NF.exists(), (
            f"merge_detection.nf not found at {MERGE_DETECTION_NF}"
        )

    @pytest.mark.unit
    def test_merge_detection_nf_contains_process(self) -> None:
        """merge_detection.nf must define a process named MERGE_DETECTION."""
        content = MERGE_DETECTION_NF.read_text()
        assert "process MERGE_DETECTION" in content

    @pytest.mark.unit
    def test_merge_detection_nf_calls_merge_script(self) -> None:
        """merge_detection.nf script block must call merge_detection.py."""
        content = MERGE_DETECTION_NF.read_text()
        assert "merge_detection.py" in content

    @pytest.mark.unit
    def test_merge_detection_nf_has_stub_block(self) -> None:
        """merge_detection.nf must retain a stub block for dry-run testing."""
        content = MERGE_DETECTION_NF.read_text()
        assert "stub:" in content

    @pytest.mark.unit
    def test_merge_detection_nf_has_tag_annotations(self) -> None:
        """merge_detection.nf must have @TASK and @SPEC TAG annotations."""
        content = MERGE_DETECTION_NF.read_text()
        assert "@TASK" in content
        assert "@SPEC" in content

    @pytest.mark.unit
    def test_merge_detection_nf_emits_merged_tsv(self) -> None:
        """merge_detection.nf must emit merged detection TSV."""
        content = MERGE_DETECTION_NF.read_text()
        assert "merged_detection.tsv" in content or "_merged_detection.tsv" in content


# ---------------------------------------------------------------------------
# Test: merge_detection.py exists and is importable
# ---------------------------------------------------------------------------
class TestMergeDetectionScript:
    """Tests for bin/merge_detection.py script existence."""

    @pytest.mark.unit
    def test_merge_detection_script_exists(self) -> None:
        """merge_detection.py must exist in bin/."""
        assert MERGE_DETECTION_SCRIPT.exists(), (
            f"merge_detection.py not found at {MERGE_DETECTION_SCRIPT}"
        )

    @pytest.mark.unit
    def test_merge_detection_is_importable(self) -> None:
        """merge_detection.py must be importable as a Python module."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            if "merge_detection" in sys.modules:
                del sys.modules["merge_detection"]
            import merge_detection  # noqa: F401
        finally:
            sys.path = original_path


# ---------------------------------------------------------------------------
# Test: merge_detection.py merging logic
# ---------------------------------------------------------------------------
class TestMergeDetectionLogic:
    """Tests for detection result merging logic."""

    def _import_merge_detection(self):
        """Helper to import merge_detection from bin/."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            if "merge_detection" in sys.modules:
                del sys.modules["merge_detection"]
            import merge_detection
            return merge_detection
        finally:
            sys.path = original_path

    @pytest.mark.unit
    def test_both_detection_method(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """Sequences detected by both geNomad and Diamond must have detection_method='both'."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        by_id = {r["seq_id"]: r for r in rows}

        # contig_1 is in both geNomad and Diamond
        assert "contig_1" in by_id
        assert by_id["contig_1"]["detection_method"] == "both"

    @pytest.mark.unit
    def test_genomad_only_detection_method(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """Sequences only in geNomad must have detection_method='genomad'."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        by_id = {r["seq_id"]: r for r in rows}

        # contig_2 and contig_4 are only in geNomad
        assert by_id["contig_2"]["detection_method"] == "genomad"
        assert by_id["contig_4"]["detection_method"] == "genomad"

    @pytest.mark.unit
    def test_diamond_only_detection_method(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """Sequences only in Diamond must have detection_method='diamond'."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        by_id = {r["seq_id"]: r for r in rows}

        # contig_3 is only in Diamond
        assert "contig_3" in by_id
        assert by_id["contig_3"]["detection_method"] == "diamond"

    @pytest.mark.unit
    def test_all_sequences_present(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """Outer join must include all unique seq_ids from both inputs."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        seq_ids = {r["seq_id"] for r in rows}
        # contig_1 (both), contig_2 (genomad), contig_3 (diamond), contig_4 (genomad)
        assert seq_ids == {"contig_1", "contig_2", "contig_3", "contig_4"}

    @pytest.mark.unit
    def test_detection_score_genomad_priority(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """For 'both' sequences, detection_score must use geNomad score (priority)."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        by_id = {r["seq_id"]: r for r in rows}

        # contig_1: geNomad score = 0.95, Diamond bitscore = 800
        # Should use geNomad score
        assert abs(float(by_id["contig_1"]["detection_score"]) - 0.95) < 1e-4

    @pytest.mark.unit
    def test_detection_score_diamond_normalized(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """For diamond-only sequences, detection_score must be normalized bitscore."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        by_id = {r["seq_id"]: r for r in rows}

        # contig_3 is diamond-only; its bitscore=650 should be normalized
        score = float(by_id["contig_3"]["detection_score"])
        assert 0.0 <= score <= 1.0, (
            f"Normalized Diamond score must be in [0, 1], got {score}"
        )

    @pytest.mark.unit
    def test_output_columns(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """Merged output must contain exactly the expected columns."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        for row in rows:
            assert set(row.keys()) == set(EXPECTED_COLUMNS), (
                f"Unexpected columns: {set(row.keys())} != {set(EXPECTED_COLUMNS)}"
            )

    @pytest.mark.unit
    def test_taxonomy_from_genomad(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """taxonomy column must come from geNomad data."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        by_id = {r["seq_id"]: r for r in rows}

        # contig_1 (both): taxonomy from geNomad
        assert by_id["contig_1"]["taxonomy"] == "Viruses;Caudoviricetes;Crassvirales"
        # contig_2 (genomad-only): has taxonomy
        assert by_id["contig_2"]["taxonomy"] == "Viruses;Caudoviricetes"
        # contig_3 (diamond-only): no geNomad taxonomy -> empty
        assert by_id["contig_3"]["taxonomy"] == ""

    @pytest.mark.unit
    def test_taxid_from_diamond(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """taxid column must come from Diamond data."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        by_id = {r["seq_id"]: r for r in rows}

        # contig_1 (both): taxid from Diamond
        assert by_id["contig_1"]["taxid"] == "12345"
        # contig_3 (diamond-only): taxid from Diamond
        assert by_id["contig_3"]["taxid"] == "99999"
        # contig_2 (genomad-only): no Diamond taxid -> empty
        assert by_id["contig_2"]["taxid"] == ""

    @pytest.mark.unit
    def test_subject_id_from_diamond(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """subject_id column must come from Diamond data."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        by_id = {r["seq_id"]: r for r in rows}

        assert by_id["contig_1"]["subject_id"] == "UniRef90_P12345"
        assert by_id["contig_3"]["subject_id"] == "UniRef90_R99999"
        assert by_id["contig_2"]["subject_id"] == ""

    @pytest.mark.unit
    def test_empty_genomad_input(
        self,
        mock_genomad_empty_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """When geNomad input is empty, all sequences come from Diamond only."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_empty_tsv, mock_diamond_parsed_tsv)

        assert len(rows) == 2
        for row in rows:
            assert row["detection_method"] == "diamond"

    @pytest.mark.unit
    def test_empty_diamond_input(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_empty_tsv: Path,
    ) -> None:
        """When Diamond input is empty, all sequences come from geNomad only."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_empty_tsv)

        assert len(rows) == 3
        for row in rows:
            assert row["detection_method"] == "genomad"

    @pytest.mark.unit
    def test_both_inputs_empty(
        self,
        mock_genomad_empty_tsv: Path,
        mock_diamond_empty_tsv: Path,
    ) -> None:
        """When both inputs are empty, output must be an empty list."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_empty_tsv, mock_diamond_empty_tsv)

        assert rows == []

    @pytest.mark.unit
    def test_length_from_genomad_when_available(
        self,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """length column must come from geNomad when available, Diamond otherwise."""
        mod = self._import_merge_detection()
        rows = mod.merge_detections(mock_genomad_parsed_tsv, mock_diamond_parsed_tsv)

        by_id = {r["seq_id"]: r for r in rows}

        # contig_1 (both): length from geNomad = 15000
        assert int(by_id["contig_1"]["length"]) == 15000
        # contig_3 (diamond-only): length from Diamond = 400
        assert int(by_id["contig_3"]["length"]) == 400


# ---------------------------------------------------------------------------
# Test: merge_detection.py CLI
# ---------------------------------------------------------------------------
class TestMergeDetectionCLI:
    """Tests for merge_detection.py command-line interface."""

    @pytest.mark.unit
    def test_cli_produces_tsv(
        self,
        tmp_dir: Path,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """CLI produces a valid TSV with correct header and rows."""
        output_tsv = tmp_dir / "merged_detection.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(MERGE_DETECTION_SCRIPT),
                "--genomad",
                str(mock_genomad_parsed_tsv),
                "--diamond",
                str(mock_diamond_parsed_tsv),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"merge_detection.py failed: {result.stderr}"
        )
        assert output_tsv.exists(), "Output TSV not created"

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        assert list(rows[0].keys()) == EXPECTED_COLUMNS
        assert len(rows) == 4  # contig_1 (both), contig_2, contig_4, contig_3

    @pytest.mark.unit
    def test_cli_empty_inputs(
        self,
        tmp_dir: Path,
        mock_genomad_empty_tsv: Path,
        mock_diamond_empty_tsv: Path,
    ) -> None:
        """CLI handles empty inputs gracefully (header-only output)."""
        output_tsv = tmp_dir / "merged_empty.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(MERGE_DETECTION_SCRIPT),
                "--genomad",
                str(mock_genomad_empty_tsv),
                "--diamond",
                str(mock_diamond_empty_tsv),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"merge_detection.py failed: {result.stderr}"
        )
        assert output_tsv.exists()

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        assert len(rows) == 0

    @pytest.mark.unit
    def test_cli_detection_method_values(
        self,
        tmp_dir: Path,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """CLI output must contain correct detection_method for each sequence."""
        output_tsv = tmp_dir / "merged_methods.tsv"

        subprocess.run(
            [
                sys.executable,
                str(MERGE_DETECTION_SCRIPT),
                "--genomad",
                str(mock_genomad_parsed_tsv),
                "--diamond",
                str(mock_diamond_parsed_tsv),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            by_id = {row["seq_id"]: row for row in reader}

        assert by_id["contig_1"]["detection_method"] == "both"
        assert by_id["contig_2"]["detection_method"] == "genomad"
        assert by_id["contig_3"]["detection_method"] == "diamond"
        assert by_id["contig_4"]["detection_method"] == "genomad"

    @pytest.mark.unit
    def test_cli_nonexistent_file(self, tmp_dir: Path) -> None:
        """CLI returns non-zero exit code for missing input file."""
        output_tsv = tmp_dir / "out.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(MERGE_DETECTION_SCRIPT),
                "--genomad",
                "/nonexistent/genomad.tsv",
                "--diamond",
                "/nonexistent/diamond.tsv",
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0

    @pytest.mark.unit
    def test_cli_output_numeric_columns(
        self,
        tmp_dir: Path,
        mock_genomad_parsed_tsv: Path,
        mock_diamond_parsed_tsv: Path,
    ) -> None:
        """Numeric columns in CLI output must be parseable as numbers."""
        output_tsv = tmp_dir / "merged_numeric.tsv"

        subprocess.run(
            [
                sys.executable,
                str(MERGE_DETECTION_SCRIPT),
                "--genomad",
                str(mock_genomad_parsed_tsv),
                "--diamond",
                str(mock_diamond_parsed_tsv),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                # length must be numeric (may be empty string for some edge cases)
                if row["length"]:
                    int(row["length"])
                # detection_score must be numeric
                float(row["detection_score"])
