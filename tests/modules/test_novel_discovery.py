"""Tests for Novel Virus Discovery: filter, ORF prediction, closest virus search.

# @TASK T6.1 - Novel virus discovery tests
# @SPEC docs/planning/02-trd.md#3.2-pipeline-stages
# @TEST tests/modules/test_novel_discovery.py
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
MODULES_DIR = PROJECT_ROOT / "modules" / "local"

FILTER_SCRIPT = BIN_DIR / "filter_novel_viruses.py"
PREDICT_ORFS_SCRIPT = BIN_DIR / "predict_orfs.py"
FIND_CLOSEST_SCRIPT = BIN_DIR / "find_closest_virus.py"
PRODIGAL_NF = MODULES_DIR / "prodigal.nf"

NOVEL_TSV_COLUMNS = [
    "seq_id",
    "length",
    "detection_score",
    "taxonomy",
    "viral_hallmark_count",
    "novelty_reason",
]

ORF_TSV_COLUMNS = [
    "seq_id",
    "num_orfs",
    "avg_orf_length",
    "longest_orf",
    "coding_density",
]

CLOSEST_TSV_COLUMNS = [
    "seq_id",
    "closest_virus_name",
    "closest_virus_taxid",
    "pident",
    "evalue",
    "bitscore",
    "query_coverage",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_merged_detection_tsv(tmp_dir: Path) -> Path:
    """Create a mock merged detection TSV with mixed detection methods.

    Contains:
    - contig_1: both (geNomad + Diamond, pident=95.0) -> NOT novel
    - contig_2: genomad only, hallmark=3, score=0.82 -> novel (no_protein_hit)
    - contig_3: diamond only -> NOT novel
    - contig_4: genomad only, hallmark=8, score=0.99 -> novel (no_protein_hit)
    - contig_5: both (pident=25.0, low identity) -> novel (low_identity)
    - contig_6: genomad only, hallmark=0, score=0.75 -> filtered out (no hallmarks)
    """
    content = textwrap.dedent("""\
        seq_id\tlength\tdetection_method\tdetection_score\ttaxonomy\ttaxid\tsubject_id\tviral_hallmark_count\tpident
        contig_1\t15000\tboth\t0.95\tViruses;Caudoviricetes;Crassvirales\t12345\tUniRef90_P12345\t5\t95.0
        contig_2\t8000\tgenomad\t0.82\tViruses;Caudoviricetes\t\t\t3\t
        contig_3\t5000\tdiamond\t0.65\t\t99999\tUniRef90_R99999\t0\t88.5
        contig_4\t25000\tgenomad\t0.99\tViruses;Phixviricota\t\t\t8\t
        contig_5\t12000\tboth\t0.88\tViruses;Caudoviricetes\t55555\tUniRef90_X55555\t2\t25.0
        contig_6\t3000\tgenomad\t0.75\tViruses;Unclassified\t\t\t0\t
    """)
    tsv_path = tmp_dir / "merged_detection.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_merged_empty_tsv(tmp_dir: Path) -> Path:
    """Create an empty (header-only) merged detection TSV."""
    content = "seq_id\tlength\tdetection_method\tdetection_score\ttaxonomy\ttaxid\tsubject_id\tviral_hallmark_count\tpident\n"
    tsv_path = tmp_dir / "empty_merged.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_gff(tmp_dir: Path) -> Path:
    """Create a mock Prodigal GFF output for two contigs."""
    content = textwrap.dedent("""\
        ##gff-version 3
        # Sequence Data: seqnum=1;seqlen=8000;seqhdr="contig_2"
        contig_2\tProdigal_v2.6.3\tCDS\t3\t500\t20.5\t+\t0\tID=1_1;partial=00;start_type=ATG
        contig_2\tProdigal_v2.6.3\tCDS\t600\t1400\t35.2\t+\t0\tID=1_2;partial=00;start_type=ATG
        contig_2\tProdigal_v2.6.3\tCDS\t1500\t2800\t45.0\t-\t0\tID=1_3;partial=00;start_type=GTG
        # Sequence Data: seqnum=2;seqlen=25000;seqhdr="contig_4"
        contig_4\tProdigal_v2.6.3\tCDS\t100\t3000\t100.5\t+\t0\tID=2_1;partial=00;start_type=ATG
        contig_4\tProdigal_v2.6.3\tCDS\t3200\t5500\t80.3\t-\t0\tID=2_2;partial=00;start_type=ATG
        contig_4\tProdigal_v2.6.3\tCDS\t5600\t7000\t60.1\t+\t0\tID=2_3;partial=00;start_type=ATG
        contig_4\tProdigal_v2.6.3\tCDS\t7100\t9500\t70.0\t+\t0\tID=2_4;partial=00;start_type=ATG
        contig_4\tProdigal_v2.6.3\tCDS\t10000\t12000\t55.0\t-\t0\tID=2_5;partial=00;start_type=ATG
    """)
    gff_path = tmp_dir / "novel.genes.gff"
    gff_path.write_text(content)
    return gff_path


@pytest.fixture
def mock_gff_empty(tmp_dir: Path) -> Path:
    """Create an empty GFF (header only)."""
    content = "##gff-version 3\n"
    gff_path = tmp_dir / "empty.genes.gff"
    gff_path.write_text(content)
    return gff_path


@pytest.fixture
def mock_blastp_tsv(tmp_dir: Path) -> Path:
    """Create a mock Diamond blastp output (outfmt 6 style).

    Columns: qseqid, sseqid, stitle, staxids, pident, evalue, bitscore, qcovs
    """
    content = textwrap.dedent("""\
        qseqid\tsseqid\tstitle\tstaxids\tpident\tevalue\tbitscore\tqcovs
        contig_2_1\tYP_001234\tPhage tail protein [Caudovirales phage]\t12345\t45.5\t1e-20\t250\t85.0
        contig_2_2\tYP_005678\tHypothetical protein [Unknown virus]\t56789\t32.0\t1e-10\t120\t60.0
        contig_4_1\tYP_009999\tMajor capsid protein [Phixviricota]\t99999\t65.0\t1e-50\t500\t95.0
        contig_4_3\tYP_008888\tTerminase [Caudovirales phage]\t88888\t55.0\t1e-30\t350\t90.0
    """)
    tsv_path = tmp_dir / "blastp_results.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_blastp_empty_tsv(tmp_dir: Path) -> Path:
    """Create an empty blastp result (header only)."""
    content = "qseqid\tsseqid\tstitle\tstaxids\tpident\tevalue\tbitscore\tqcovs\n"
    tsv_path = tmp_dir / "empty_blastp.tsv"
    tsv_path.write_text(content)
    return tsv_path


# ===========================================================================
# Test: filter_novel_viruses.py
# ===========================================================================
class TestFilterNovelVirusesScript:
    """Tests for bin/filter_novel_viruses.py existence and import."""

    @pytest.mark.unit
    def test_script_exists(self) -> None:
        """filter_novel_viruses.py must exist in bin/."""
        assert FILTER_SCRIPT.exists(), (
            f"filter_novel_viruses.py not found at {FILTER_SCRIPT}"
        )

    @pytest.mark.unit
    def test_is_importable(self) -> None:
        """filter_novel_viruses.py must be importable as a Python module."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            if "filter_novel_viruses" in sys.modules:
                del sys.modules["filter_novel_viruses"]
            import filter_novel_viruses  # noqa: F401
        finally:
            sys.path = original_path


class TestFilterNovelVirusesLogic:
    """Tests for novel virus filtering logic."""

    def _import(self):
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            if "filter_novel_viruses" in sys.modules:
                del sys.modules["filter_novel_viruses"]
            import filter_novel_viruses
            return filter_novel_viruses
        finally:
            sys.path = original_path

    @pytest.mark.unit
    def test_genomad_only_extracted(self, mock_merged_detection_tsv: Path) -> None:
        """geNomad-only sequences with hallmarks >= 1 must be extracted."""
        mod = self._import()
        rows = mod.filter_novel_viruses(mock_merged_detection_tsv, min_hallmarks=1, min_score=0.7)
        seq_ids = {r["seq_id"] for r in rows}
        # contig_2 (genomad, hallmark=3), contig_4 (genomad, hallmark=8) -> novel
        assert "contig_2" in seq_ids
        assert "contig_4" in seq_ids

    @pytest.mark.unit
    def test_low_identity_extracted(self, mock_merged_detection_tsv: Path) -> None:
        """Sequences with both detection but pident < 30% must be extracted as novel."""
        mod = self._import()
        rows = mod.filter_novel_viruses(mock_merged_detection_tsv, min_hallmarks=1, min_score=0.7)
        seq_ids = {r["seq_id"] for r in rows}
        # contig_5: both, pident=25.0, hallmark=2 -> novel (low_identity)
        assert "contig_5" in seq_ids

    @pytest.mark.unit
    def test_high_identity_excluded(self, mock_merged_detection_tsv: Path) -> None:
        """Sequences with both detection and pident >= 30% must NOT be extracted."""
        mod = self._import()
        rows = mod.filter_novel_viruses(mock_merged_detection_tsv, min_hallmarks=1, min_score=0.7)
        seq_ids = {r["seq_id"] for r in rows}
        # contig_1: both, pident=95.0 -> NOT novel
        assert "contig_1" not in seq_ids

    @pytest.mark.unit
    def test_diamond_only_excluded(self, mock_merged_detection_tsv: Path) -> None:
        """Diamond-only sequences must NOT be extracted as novel."""
        mod = self._import()
        rows = mod.filter_novel_viruses(mock_merged_detection_tsv, min_hallmarks=1, min_score=0.7)
        seq_ids = {r["seq_id"] for r in rows}
        assert "contig_3" not in seq_ids

    @pytest.mark.unit
    def test_hallmark_filter(self, mock_merged_detection_tsv: Path) -> None:
        """Sequences with viral_hallmark_count < min_hallmarks must be excluded."""
        mod = self._import()
        rows = mod.filter_novel_viruses(mock_merged_detection_tsv, min_hallmarks=1, min_score=0.7)
        seq_ids = {r["seq_id"] for r in rows}
        # contig_6: genomad, hallmark=0 -> excluded
        assert "contig_6" not in seq_ids

    @pytest.mark.unit
    def test_score_filter(self, mock_merged_detection_tsv: Path) -> None:
        """Sequences with detection_score < min_score must be excluded."""
        mod = self._import()
        # With min_score=0.9, contig_2 (0.82) should be excluded
        rows = mod.filter_novel_viruses(mock_merged_detection_tsv, min_hallmarks=1, min_score=0.9)
        seq_ids = {r["seq_id"] for r in rows}
        assert "contig_2" not in seq_ids
        # contig_4 (0.99) still included
        assert "contig_4" in seq_ids

    @pytest.mark.unit
    def test_novelty_reason_no_protein_hit(self, mock_merged_detection_tsv: Path) -> None:
        """geNomad-only sequences must have novelty_reason='no_protein_hit'."""
        mod = self._import()
        rows = mod.filter_novel_viruses(mock_merged_detection_tsv, min_hallmarks=1, min_score=0.7)
        by_id = {r["seq_id"]: r for r in rows}
        assert by_id["contig_2"]["novelty_reason"] == "no_protein_hit"
        assert by_id["contig_4"]["novelty_reason"] == "no_protein_hit"

    @pytest.mark.unit
    def test_novelty_reason_low_identity(self, mock_merged_detection_tsv: Path) -> None:
        """Low-identity sequences must have novelty_reason='low_identity'."""
        mod = self._import()
        rows = mod.filter_novel_viruses(mock_merged_detection_tsv, min_hallmarks=1, min_score=0.7)
        by_id = {r["seq_id"]: r for r in rows}
        assert by_id["contig_5"]["novelty_reason"] == "low_identity"

    @pytest.mark.unit
    def test_output_columns(self, mock_merged_detection_tsv: Path) -> None:
        """Output must contain exactly the expected columns."""
        mod = self._import()
        rows = mod.filter_novel_viruses(mock_merged_detection_tsv, min_hallmarks=1, min_score=0.7)
        for row in rows:
            assert list(row.keys()) == NOVEL_TSV_COLUMNS, (
                f"Unexpected columns: {list(row.keys())} != {NOVEL_TSV_COLUMNS}"
            )

    @pytest.mark.unit
    def test_empty_input(self, mock_merged_empty_tsv: Path) -> None:
        """Empty input must produce empty output."""
        mod = self._import()
        rows = mod.filter_novel_viruses(mock_merged_empty_tsv, min_hallmarks=1, min_score=0.7)
        assert rows == []


class TestFilterNovelVirusesCLI:
    """Tests for filter_novel_viruses.py CLI."""

    @pytest.mark.unit
    def test_cli_help(self) -> None:
        """CLI --help must work."""
        result = subprocess.run(
            [sys.executable, str(FILTER_SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "novel" in result.stdout.lower() or "filter" in result.stdout.lower()

    @pytest.mark.unit
    def test_cli_produces_tsv(
        self, tmp_dir: Path, mock_merged_detection_tsv: Path,
    ) -> None:
        """CLI produces a valid novel_viruses.tsv."""
        output_tsv = tmp_dir / "novel_viruses.tsv"
        result = subprocess.run(
            [
                sys.executable, str(FILTER_SCRIPT),
                "--input", str(mock_merged_detection_tsv),
                "--output", str(output_tsv),
                "--min-hallmarks", "1",
                "--min-score", "0.7",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_tsv.exists()

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)
        assert len(rows) == 3  # contig_2, contig_4, contig_5
        assert list(rows[0].keys()) == NOVEL_TSV_COLUMNS

    @pytest.mark.unit
    def test_cli_empty_input(
        self, tmp_dir: Path, mock_merged_empty_tsv: Path,
    ) -> None:
        """CLI handles empty input gracefully."""
        output_tsv = tmp_dir / "novel_empty.tsv"
        result = subprocess.run(
            [
                sys.executable, str(FILTER_SCRIPT),
                "--input", str(mock_merged_empty_tsv),
                "--output", str(output_tsv),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)
        assert len(rows) == 0

    @pytest.mark.unit
    def test_cli_summary_output(
        self, tmp_dir: Path, mock_merged_detection_tsv: Path,
    ) -> None:
        """CLI must produce a summary file when --summary is given."""
        output_tsv = tmp_dir / "novel_viruses.tsv"
        summary_path = tmp_dir / "novel_summary.txt"
        result = subprocess.run(
            [
                sys.executable, str(FILTER_SCRIPT),
                "--input", str(mock_merged_detection_tsv),
                "--output", str(output_tsv),
                "--summary", str(summary_path),
                "--min-hallmarks", "1",
                "--min-score", "0.7",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert summary_path.exists()
        summary_text = summary_path.read_text()
        assert "novel" in summary_text.lower()


# ===========================================================================
# Test: predict_orfs.py
# ===========================================================================
class TestPredictOrfsScript:
    """Tests for bin/predict_orfs.py existence and import."""

    @pytest.mark.unit
    def test_script_exists(self) -> None:
        """predict_orfs.py must exist in bin/."""
        assert PREDICT_ORFS_SCRIPT.exists(), (
            f"predict_orfs.py not found at {PREDICT_ORFS_SCRIPT}"
        )

    @pytest.mark.unit
    def test_is_importable(self) -> None:
        """predict_orfs.py must be importable as a Python module."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            if "predict_orfs" in sys.modules:
                del sys.modules["predict_orfs"]
            import predict_orfs  # noqa: F401
        finally:
            sys.path = original_path


class TestPredictOrfsLogic:
    """Tests for ORF prediction parsing logic."""

    def _import(self):
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            if "predict_orfs" in sys.modules:
                del sys.modules["predict_orfs"]
            import predict_orfs
            return predict_orfs
        finally:
            sys.path = original_path

    @pytest.mark.unit
    def test_parse_gff_contig_counts(self, mock_gff: Path) -> None:
        """Must correctly count ORFs per contig."""
        mod = self._import()
        rows = mod.parse_gff_stats(mock_gff)
        by_id = {r["seq_id"]: r for r in rows}
        assert int(by_id["contig_2"]["num_orfs"]) == 3
        assert int(by_id["contig_4"]["num_orfs"]) == 5

    @pytest.mark.unit
    def test_parse_gff_avg_orf_length(self, mock_gff: Path) -> None:
        """Must correctly calculate average ORF length per contig."""
        mod = self._import()
        rows = mod.parse_gff_stats(mock_gff)
        by_id = {r["seq_id"]: r for r in rows}
        # contig_2: ORFs lengths = (500-3+1)=498, (1400-600+1)=801, (2800-1500+1)=1301
        # avg = (498+801+1301)/3 = 866.67
        avg_len = float(by_id["contig_2"]["avg_orf_length"])
        assert 860 < avg_len < 870

    @pytest.mark.unit
    def test_parse_gff_longest_orf(self, mock_gff: Path) -> None:
        """Must correctly identify the longest ORF per contig."""
        mod = self._import()
        rows = mod.parse_gff_stats(mock_gff)
        by_id = {r["seq_id"]: r for r in rows}
        # contig_4: ORFs = (3000-100+1)=2901, (5500-3200+1)=2301, (7000-5600+1)=1401,
        #           (9500-7100+1)=2401, (12000-10000+1)=2001
        # longest = 2901
        assert int(by_id["contig_4"]["longest_orf"]) == 2901

    @pytest.mark.unit
    def test_parse_gff_coding_density(self, mock_gff: Path) -> None:
        """Must correctly calculate coding density (total CDS / seq length)."""
        mod = self._import()
        rows = mod.parse_gff_stats(mock_gff)
        by_id = {r["seq_id"]: r for r in rows}
        # contig_2: total CDS = 498+801+1301 = 2600, seqlen=8000
        # coding_density = 2600/8000 = 0.325
        density = float(by_id["contig_2"]["coding_density"])
        assert 0.32 < density < 0.33

    @pytest.mark.unit
    def test_parse_gff_empty(self, mock_gff_empty: Path) -> None:
        """Empty GFF must produce empty output."""
        mod = self._import()
        rows = mod.parse_gff_stats(mock_gff_empty)
        assert rows == []

    @pytest.mark.unit
    def test_output_columns(self, mock_gff: Path) -> None:
        """Output must contain the expected columns."""
        mod = self._import()
        rows = mod.parse_gff_stats(mock_gff)
        for row in rows:
            assert list(row.keys()) == ORF_TSV_COLUMNS


class TestPredictOrfsCLI:
    """Tests for predict_orfs.py CLI."""

    @pytest.mark.unit
    def test_cli_help(self) -> None:
        """CLI --help must work."""
        result = subprocess.run(
            [sys.executable, str(PREDICT_ORFS_SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    @pytest.mark.unit
    def test_cli_produces_tsv(self, tmp_dir: Path, mock_gff: Path) -> None:
        """CLI produces a valid ORF stats TSV."""
        output_tsv = tmp_dir / "orf_stats.tsv"
        result = subprocess.run(
            [
                sys.executable, str(PREDICT_ORFS_SCRIPT),
                "--gff", str(mock_gff),
                "--output", str(output_tsv),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_tsv.exists()
        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)
        assert len(rows) == 2
        assert list(rows[0].keys()) == ORF_TSV_COLUMNS


# ===========================================================================
# Test: find_closest_virus.py
# ===========================================================================
class TestFindClosestVirusScript:
    """Tests for bin/find_closest_virus.py existence and import."""

    @pytest.mark.unit
    def test_script_exists(self) -> None:
        """find_closest_virus.py must exist in bin/."""
        assert FIND_CLOSEST_SCRIPT.exists(), (
            f"find_closest_virus.py not found at {FIND_CLOSEST_SCRIPT}"
        )

    @pytest.mark.unit
    def test_is_importable(self) -> None:
        """find_closest_virus.py must be importable as a Python module."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            if "find_closest_virus" in sys.modules:
                del sys.modules["find_closest_virus"]
            import find_closest_virus  # noqa: F401
        finally:
            sys.path = original_path


class TestFindClosestVirusLogic:
    """Tests for closest virus search logic."""

    def _import(self):
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            if "find_closest_virus" in sys.modules:
                del sys.modules["find_closest_virus"]
            import find_closest_virus
            return find_closest_virus
        finally:
            sys.path = original_path

    @pytest.mark.unit
    def test_parse_blastp_results(self, mock_blastp_tsv: Path) -> None:
        """Must correctly parse blastp results and extract best hit per contig."""
        mod = self._import()
        rows = mod.parse_blastp_results(mock_blastp_tsv)
        # Should have one best hit per source contig (contig_2 and contig_4)
        seq_ids = {r["seq_id"] for r in rows}
        assert "contig_2" in seq_ids
        assert "contig_4" in seq_ids

    @pytest.mark.unit
    def test_best_hit_selection(self, mock_blastp_tsv: Path) -> None:
        """Must select the best hit (highest bitscore) per contig."""
        mod = self._import()
        rows = mod.parse_blastp_results(mock_blastp_tsv)
        by_id = {r["seq_id"]: r for r in rows}
        # contig_2: best hit = contig_2_1 with bitscore=250
        assert "Phage tail protein" in by_id["contig_2"]["closest_virus_name"]
        assert float(by_id["contig_2"]["bitscore"]) == 250.0
        # contig_4: best hit = contig_4_1 with bitscore=500
        assert "Major capsid protein" in by_id["contig_4"]["closest_virus_name"]
        assert float(by_id["contig_4"]["bitscore"]) == 500.0

    @pytest.mark.unit
    def test_output_columns(self, mock_blastp_tsv: Path) -> None:
        """Output must contain the expected columns."""
        mod = self._import()
        rows = mod.parse_blastp_results(mock_blastp_tsv)
        for row in rows:
            assert list(row.keys()) == CLOSEST_TSV_COLUMNS

    @pytest.mark.unit
    def test_empty_input(self, mock_blastp_empty_tsv: Path) -> None:
        """Empty blastp input must produce empty output."""
        mod = self._import()
        rows = mod.parse_blastp_results(mock_blastp_empty_tsv)
        assert rows == []

    @pytest.mark.unit
    def test_no_hit_contigs(self, tmp_dir: Path, mock_blastp_tsv: Path) -> None:
        """Contigs with no blastp hit must show 'No significant hit'."""
        mod = self._import()
        # Provide a list of novel contigs that includes one with no hits
        novel_contigs = ["contig_2", "contig_4", "contig_99"]
        rows = mod.parse_blastp_results(mock_blastp_tsv, novel_contigs=novel_contigs)
        by_id = {r["seq_id"]: r for r in rows}
        assert "contig_99" in by_id
        assert by_id["contig_99"]["closest_virus_name"] == "No significant hit"


class TestFindClosestVirusCLI:
    """Tests for find_closest_virus.py CLI."""

    @pytest.mark.unit
    def test_cli_help(self) -> None:
        """CLI --help must work."""
        result = subprocess.run(
            [sys.executable, str(FIND_CLOSEST_SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    @pytest.mark.unit
    def test_cli_produces_tsv(self, tmp_dir: Path, mock_blastp_tsv: Path) -> None:
        """CLI produces a valid closest virus TSV."""
        output_tsv = tmp_dir / "closest_viruses.tsv"
        result = subprocess.run(
            [
                sys.executable, str(FIND_CLOSEST_SCRIPT),
                "--blastp-results", str(mock_blastp_tsv),
                "--output", str(output_tsv),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert output_tsv.exists()
        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)
        assert len(rows) >= 2
        assert list(rows[0].keys()) == CLOSEST_TSV_COLUMNS


# ===========================================================================
# Test: prodigal.nf
# ===========================================================================
class TestProdigalNextflow:
    """Tests for prodigal.nf Nextflow process definition."""

    @pytest.mark.unit
    def test_prodigal_nf_exists(self) -> None:
        """prodigal.nf must exist in modules/local/."""
        assert PRODIGAL_NF.exists(), f"prodigal.nf not found at {PRODIGAL_NF}"

    @pytest.mark.unit
    def test_prodigal_nf_contains_process(self) -> None:
        """prodigal.nf must define a process named PRODIGAL."""
        content = PRODIGAL_NF.read_text()
        assert "process PRODIGAL" in content

    @pytest.mark.unit
    def test_prodigal_nf_has_stub_block(self) -> None:
        """prodigal.nf must have a stub block."""
        content = PRODIGAL_NF.read_text()
        assert "stub:" in content

    @pytest.mark.unit
    def test_prodigal_nf_meta_mode(self) -> None:
        """prodigal.nf must run prodigal with -p meta flag."""
        content = PRODIGAL_NF.read_text()
        assert "-p meta" in content

    @pytest.mark.unit
    def test_prodigal_nf_emits_proteins(self) -> None:
        """prodigal.nf must emit protein FASTA."""
        content = PRODIGAL_NF.read_text()
        assert "proteins" in content
        assert ".faa" in content

    @pytest.mark.unit
    def test_prodigal_nf_emits_gff(self) -> None:
        """prodigal.nf must emit GFF."""
        content = PRODIGAL_NF.read_text()
        assert "gff" in content.lower()

    @pytest.mark.unit
    def test_prodigal_nf_has_tag_annotations(self) -> None:
        """prodigal.nf must have @TASK and @SPEC TAG annotations."""
        content = PRODIGAL_NF.read_text()
        assert "@TASK" in content
        assert "@SPEC" in content
