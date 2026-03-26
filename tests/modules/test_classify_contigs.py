"""Tests for classify_contigs.py multi-DB contig classification script.

# @TASK T3.6 - Multi-DB contig classification tests
# @SPEC docs/planning/12-pipeline-v2-multidb-filtering.md
# @TEST tests/modules/test_classify_contigs.py
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = PROJECT_ROOT / "bin"
CLASSIFY_SCRIPT = BIN_DIR / "classify_contigs.py"
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
DIAMOND_EXCLUSION_NF = MODULES_DIR / "diamond_exclusion.nf"
CLASSIFY_CONTIGS_NF = MODULES_DIR / "classify_contigs.nf"

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
sys.path.insert(0, str(BIN_DIR))
from classify_contigs import (  # noqa: E402
    KINGDOM_TAXIDS,
    NON_VIRAL_KINGDOMS,
    _decide,
    _load_exclusion,
    _load_detection,
    classify_contigs,
    get_kingdom,
    load_taxonomy_lineage,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_nodes_dmp(tmp_dir: Path) -> Path:
    """Create a minimal NCBI nodes.dmp for testing.

    Taxonomy tree:
        1 (root)
        +-- 2 (Bacteria)
        |   +-- 1224 (Proteobacteria)
        |       +-- 562 (E. coli)
        +-- 10239 (Viruses)
        |   +-- 12345 (some virus family)
        |       +-- 67890 (some virus species)
        +-- 4751 (Fungi)
        |   +-- 5000 (some fungus)
        +-- 33208 (Metazoa)
            +-- 9606 (Homo sapiens)
    """
    content = textwrap.dedent("""\
        1\t|\t1\t|\tno rank\t|
        2\t|\t1\t|\tsuperkingdom\t|
        1224\t|\t2\t|\tphylum\t|
        562\t|\t1224\t|\tspecies\t|
        10239\t|\t1\t|\tsuperkingdom\t|
        12345\t|\t10239\t|\tfamily\t|
        67890\t|\t12345\t|\tspecies\t|
        4751\t|\t1\t|\tkingdom\t|
        5000\t|\t4751\t|\tspecies\t|
        33208\t|\t1\t|\tkingdom\t|
        9606\t|\t33208\t|\tspecies\t|
    """)
    nodes_path = tmp_dir / "nodes.dmp"
    nodes_path.write_text(content)
    return nodes_path


@pytest.fixture
def mock_exclusion_tsv(tmp_dir: Path) -> Path:
    """Create mock Diamond exclusion hits.

    Contains:
        - contig_1: best hit = E. coli (bacterial, taxid 562)
        - contig_2: best hit = virus (taxid 67890)
        - contig_3: best hit = fungal (taxid 5000)
        - contig_4: best hit = human (taxid 9606), high bitscore
    """
    content = textwrap.dedent("""\
        contig_1\tsp|P12345|PROT_ECOLI\t85.0\t300\t45\t0\t1\t900\t1\t300\t1e-30\t500\t562
        contig_2\tsp|Q99999|VP_VIRUS\t92.0\t400\t32\t0\t1\t1200\t1\t400\t1e-60\t700\t67890
        contig_3\tsp|R55555|PROT_FUNGI\t78.0\t250\t55\t0\t1\t750\t1\t250\t1e-20\t350\t5000
        contig_4\tsp|H11111|PROT_HUMAN\t90.0\t500\t50\t0\t1\t1500\t1\t500\t1e-80\t900\t9606
    """)
    tsv_path = tmp_dir / "coassembly.exclusion.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def mock_detection_tsv(tmp_dir: Path) -> Path:
    """Create mock merged detection results.

    Contains:
        - contig_1: high viral score (0.95) - but exclusion says bacterial
        - contig_2: high viral score (0.90) - exclusion confirms viral
        - contig_3: low viral score (0.30) - exclusion says fungal
        - contig_4: high viral score (0.85) - exclusion says animal, high bitscore
        - contig_5: medium viral score (0.50) - no exclusion hit
    """
    content = textwrap.dedent("""\
        seq_id\tlength\tdetection_method\tdetection_score\ttaxonomy\ttaxid\tsubject_id
        contig_1\t5000\tboth\t0.95\tViruses;Caudoviricetes\t12345\tUniRef90_P12345
        contig_2\t8000\tboth\t0.90\tViruses;Caudoviricetes\t67890\tUniRef90_Q99999
        contig_3\t3000\tgenonad\t0.30\tViruses;unknown\t0\tUniRef90_R55555
        contig_4\t10000\tboth\t0.85\tViruses;Megaviricetes\t12345\tUniRef90_V12345
        contig_5\t4000\tgenonad\t0.50\tViruses;unknown\t0\tno_hit
    """)
    tsv_path = tmp_dir / "coassembly_merged_detection.tsv"
    tsv_path.write_text(content)
    return tsv_path


@pytest.fixture
def empty_tsv(tmp_dir: Path) -> Path:
    """Create an empty TSV file."""
    tsv_path = tmp_dir / "empty.tsv"
    tsv_path.write_text("")
    return tsv_path


# ---------------------------------------------------------------------------
# Unit tests: Taxonomy lookup
# ---------------------------------------------------------------------------
class TestTaxonomyLookup:
    """Tests for taxonomy lineage loading and kingdom resolution."""

    @pytest.mark.unit
    def test_load_taxonomy_lineage(self, mock_nodes_dmp: Path):
        """nodes.dmp is parsed into a correct parent mapping."""
        parent_map = load_taxonomy_lineage(mock_nodes_dmp)
        assert parent_map[562] == 1224  # E. coli -> Proteobacteria
        assert parent_map[1224] == 2  # Proteobacteria -> Bacteria
        assert parent_map[2] == 1  # Bacteria -> root
        assert parent_map[67890] == 12345  # virus species -> virus family
        assert parent_map[12345] == 10239  # virus family -> Viruses

    @pytest.mark.unit
    def test_load_taxonomy_lineage_missing_file(self, tmp_dir: Path):
        """Returns empty dict when nodes.dmp does not exist."""
        parent_map = load_taxonomy_lineage(tmp_dir / "nonexistent.dmp")
        assert parent_map == {}

    @pytest.mark.unit
    def test_get_kingdom_bacteria(self, mock_nodes_dmp: Path):
        """E. coli (562) resolves to 'bacterial'."""
        parent_map = load_taxonomy_lineage(mock_nodes_dmp)
        assert get_kingdom(562, parent_map) == "bacterial"

    @pytest.mark.unit
    def test_get_kingdom_virus(self, mock_nodes_dmp: Path):
        """Virus species (67890) resolves to 'viral'."""
        parent_map = load_taxonomy_lineage(mock_nodes_dmp)
        assert get_kingdom(67890, parent_map) == "viral"

    @pytest.mark.unit
    def test_get_kingdom_fungi(self, mock_nodes_dmp: Path):
        """Fungal species (5000) resolves to 'fungal'."""
        parent_map = load_taxonomy_lineage(mock_nodes_dmp)
        assert get_kingdom(5000, parent_map) == "fungal"

    @pytest.mark.unit
    def test_get_kingdom_animal(self, mock_nodes_dmp: Path):
        """Human (9606) resolves to 'animal'."""
        parent_map = load_taxonomy_lineage(mock_nodes_dmp)
        assert get_kingdom(9606, parent_map) == "animal"

    @pytest.mark.unit
    def test_get_kingdom_unknown_taxid(self, mock_nodes_dmp: Path):
        """Unknown taxid resolves to 'unknown'."""
        parent_map = load_taxonomy_lineage(mock_nodes_dmp)
        assert get_kingdom(999999, parent_map) == "unknown"

    @pytest.mark.unit
    def test_get_kingdom_root(self, mock_nodes_dmp: Path):
        """Root taxid (1) itself resolves to 'unknown'."""
        parent_map = load_taxonomy_lineage(mock_nodes_dmp)
        assert get_kingdom(1, parent_map) == "unknown"

    @pytest.mark.unit
    def test_get_kingdom_direct_kingdom_taxid(self, mock_nodes_dmp: Path):
        """Direct kingdom taxid (10239) resolves correctly."""
        parent_map = load_taxonomy_lineage(mock_nodes_dmp)
        assert get_kingdom(10239, parent_map) == "viral"
        assert get_kingdom(2, parent_map) == "bacterial"


# ---------------------------------------------------------------------------
# Unit tests: Decision logic
# ---------------------------------------------------------------------------
class TestDecisionLogic:
    """Tests for the _decide() function."""

    @pytest.mark.unit
    def test_high_viral_no_exclusion(self):
        """High viral score + unknown exclusion -> viral."""
        cls, evidence = _decide(0.95, "unknown", 0, 0.7)
        assert cls == "viral"
        assert evidence == "genomad_high"

    @pytest.mark.unit
    def test_high_viral_viral_exclusion(self):
        """High viral score + viral exclusion -> viral."""
        cls, evidence = _decide(0.90, "viral", 700, 0.7)
        assert cls == "viral"
        assert evidence == "genomad_high"

    @pytest.mark.unit
    def test_high_viral_strong_bacterial_exclusion(self):
        """High viral score + strong bacterial exclusion -> review."""
        cls, evidence = _decide(0.85, "bacterial", 500, 0.7)
        assert cls == "review"
        assert "bacterial" in evidence

    @pytest.mark.unit
    def test_high_viral_weak_bacterial_exclusion(self):
        """High viral score + weak bacterial exclusion (bitscore <= 200) -> viral."""
        cls, evidence = _decide(0.85, "bacterial", 150, 0.7)
        assert cls == "viral"
        assert evidence == "genomad_high_weak_exclusion"

    @pytest.mark.unit
    def test_high_viral_strong_fungal_exclusion(self):
        """High viral score + strong fungal exclusion -> review."""
        cls, evidence = _decide(0.80, "fungal", 350, 0.7)
        assert cls == "review"
        assert "fungal" in evidence

    @pytest.mark.unit
    def test_low_viral_bacterial_exclusion(self):
        """Low viral score + bacterial exclusion -> bacterial."""
        cls, evidence = _decide(0.30, "bacterial", 500, 0.7)
        assert cls == "bacterial"
        assert evidence == "exclusion_bacterial"

    @pytest.mark.unit
    def test_low_viral_no_exclusion(self):
        """Low viral score + no exclusion -> viral_low."""
        cls, evidence = _decide(0.50, "unknown", 0, 0.7)
        assert cls == "viral_low"
        assert evidence == "genomad_low_no_exclusion"

    @pytest.mark.unit
    def test_no_viral_bacterial_exclusion(self):
        """No viral evidence + bacterial exclusion -> bacterial."""
        cls, evidence = _decide(0.0, "bacterial", 500, 0.7)
        assert cls == "bacterial"
        assert evidence == "exclusion_only_bacterial"

    @pytest.mark.unit
    def test_no_evidence_at_all(self):
        """No viral evidence + no exclusion -> unknown."""
        cls, evidence = _decide(0.0, "unknown", 0, 0.7)
        assert cls == "unknown"
        assert evidence == "no_evidence"

    @pytest.mark.unit
    def test_threshold_boundary_exact(self):
        """Score exactly at threshold -> treated as high viral."""
        cls, evidence = _decide(0.7, "unknown", 0, 0.7)
        assert cls == "viral"
        assert evidence == "genomad_high"

    @pytest.mark.unit
    def test_threshold_boundary_below(self):
        """Score just below threshold -> low viral."""
        cls, evidence = _decide(0.69, "unknown", 0, 0.7)
        assert cls == "viral_low"

    @pytest.mark.unit
    def test_custom_threshold(self):
        """Custom threshold of 0.9 changes classification."""
        cls1, _ = _decide(0.85, "unknown", 0, 0.7)
        cls2, _ = _decide(0.85, "unknown", 0, 0.9)
        assert cls1 == "viral"
        assert cls2 == "viral_low"

    @pytest.mark.unit
    def test_all_non_viral_kingdoms(self):
        """All non-viral kingdoms are recognized for exclusion."""
        for kingdom in NON_VIRAL_KINGDOMS:
            cls, evidence = _decide(0.30, kingdom, 500, 0.7)
            assert cls == kingdom, f"Failed for {kingdom}"
            assert evidence == f"exclusion_{kingdom}"


# ---------------------------------------------------------------------------
# Unit tests: Data loading
# ---------------------------------------------------------------------------
class TestDataLoading:
    """Tests for _load_exclusion() and _load_detection()."""

    @pytest.mark.unit
    def test_load_exclusion_valid(self, mock_exclusion_tsv: Path):
        """Loads exclusion hits and keeps best hit per contig."""
        df = _load_exclusion(mock_exclusion_tsv)
        assert not df.empty
        assert len(df) == 4  # 4 unique contigs
        assert set(df["seq_id"]) == {"contig_1", "contig_2", "contig_3", "contig_4"}

    @pytest.mark.unit
    def test_load_exclusion_missing_file(self, tmp_dir: Path):
        """Returns empty DataFrame for missing file."""
        df = _load_exclusion(tmp_dir / "nonexistent.tsv")
        assert df.empty

    @pytest.mark.unit
    def test_load_exclusion_empty_file(self, empty_tsv: Path):
        """Returns empty DataFrame for empty file."""
        df = _load_exclusion(empty_tsv)
        assert df.empty

    @pytest.mark.unit
    def test_load_detection_valid(self, mock_detection_tsv: Path):
        """Loads detection results correctly."""
        df = _load_detection(mock_detection_tsv)
        assert not df.empty
        assert len(df) == 5
        assert "seq_id" in df.columns
        assert "detection_score" in df.columns

    @pytest.mark.unit
    def test_load_detection_missing_file(self, tmp_dir: Path):
        """Returns empty DataFrame for missing file."""
        df = _load_detection(tmp_dir / "nonexistent.tsv")
        assert df.empty

    @pytest.mark.unit
    def test_load_exclusion_best_hit_selection(self, tmp_dir: Path):
        """When multiple hits exist for same contig, keeps highest bitscore."""
        content = textwrap.dedent("""\
            contig_1\thit_A\t80.0\t300\t60\t0\t1\t900\t1\t300\t1e-20\t300\t562
            contig_1\thit_B\t95.0\t500\t25\t0\t1\t1500\t1\t500\t1e-50\t800\t562
        """)
        tsv_path = tmp_dir / "multi_hit.tsv"
        tsv_path.write_text(content)
        df = _load_exclusion(tsv_path)
        assert len(df) == 1
        assert df.iloc[0]["bitscore"] == 800  # Best hit kept

    @pytest.mark.unit
    def test_load_exclusion_semicolon_taxids(self, tmp_dir: Path):
        """Handles semicolon-separated staxids (takes first)."""
        content = textwrap.dedent("""\
            contig_1\thit_A\t80.0\t300\t60\t0\t1\t900\t1\t300\t1e-20\t300\t562;1224;2
        """)
        tsv_path = tmp_dir / "multi_taxid.tsv"
        tsv_path.write_text(content)
        df = _load_exclusion(tsv_path)
        assert len(df) == 1
        assert df.iloc[0]["staxids"] == 562


# ---------------------------------------------------------------------------
# Integration tests: Full classification pipeline
# ---------------------------------------------------------------------------
class TestClassifyContigsFull:
    """Integration tests for the full classify_contigs() function."""

    @pytest.mark.unit
    def test_full_classification(
        self,
        tmp_dir: Path,
        mock_exclusion_tsv: Path,
        mock_detection_tsv: Path,
        mock_nodes_dmp: Path,
    ):
        """Full classification produces expected results for known inputs."""
        output = tmp_dir / "classified.tsv"
        result = classify_contigs(
            exclusion_path=mock_exclusion_tsv,
            detection_path=mock_detection_tsv,
            nodes_path=mock_nodes_dmp,
            output_path=output,
        )

        assert output.exists()
        assert not result.empty

        # Check expected columns
        expected_cols = {
            "seq_id",
            "classification",
            "evidence",
            "viral_score",
            "exclusion_evalue",
            "exclusion_kingdom",
        }
        assert set(result.columns) == expected_cols

        # contig_1: high viral (0.95) + bacterial exclusion (bitscore 500 > 200) -> review
        c1 = result[result["seq_id"] == "contig_1"].iloc[0]
        assert c1["classification"] == "review"
        assert c1["exclusion_kingdom"] == "bacterial"

        # contig_2: high viral (0.90) + viral exclusion -> viral
        c2 = result[result["seq_id"] == "contig_2"].iloc[0]
        assert c2["classification"] == "viral"
        assert c2["exclusion_kingdom"] == "viral"

        # contig_3: low viral (0.30) + fungal exclusion -> fungal
        c3 = result[result["seq_id"] == "contig_3"].iloc[0]
        assert c3["classification"] == "fungal"
        assert c3["exclusion_kingdom"] == "fungal"

        # contig_4: high viral (0.85) + animal exclusion (bitscore 900 > 200) -> review
        c4 = result[result["seq_id"] == "contig_4"].iloc[0]
        assert c4["classification"] == "review"
        assert c4["exclusion_kingdom"] == "animal"

        # contig_5: low viral (0.50) + no exclusion hit -> viral_low
        c5 = result[result["seq_id"] == "contig_5"].iloc[0]
        assert c5["classification"] == "viral_low"
        assert c5["exclusion_kingdom"] == "unknown"

    @pytest.mark.unit
    def test_classification_no_exclusion(
        self,
        tmp_dir: Path,
        mock_detection_tsv: Path,
        mock_nodes_dmp: Path,
    ):
        """Classification works when exclusion file does not exist."""
        output = tmp_dir / "classified.tsv"
        result = classify_contigs(
            exclusion_path=tmp_dir / "nonexistent.tsv",
            detection_path=mock_detection_tsv,
            nodes_path=mock_nodes_dmp,
            output_path=output,
        )

        assert output.exists()
        # All contigs with high viral score -> viral
        high_viral = result[result["viral_score"] >= 0.7]
        assert all(high_viral["classification"] == "viral")

        # Low viral contigs -> viral_low (no exclusion to exclude them)
        low_viral = result[
            (result["viral_score"] > 0) & (result["viral_score"] < 0.7)
        ]
        assert all(low_viral["classification"] == "viral_low")

    @pytest.mark.unit
    def test_classification_no_detection(
        self,
        tmp_dir: Path,
        mock_exclusion_tsv: Path,
        mock_nodes_dmp: Path,
    ):
        """Classification works when detection file does not exist."""
        output = tmp_dir / "classified.tsv"
        result = classify_contigs(
            exclusion_path=mock_exclusion_tsv,
            detection_path=tmp_dir / "nonexistent.tsv",
            nodes_path=mock_nodes_dmp,
            output_path=output,
        )

        assert output.exists()
        # All contigs come from exclusion only with viral_score=0
        assert all(result["viral_score"] == 0.0)

    @pytest.mark.unit
    def test_classification_both_missing(
        self,
        tmp_dir: Path,
        mock_nodes_dmp: Path,
    ):
        """Classification produces empty result when both inputs are missing."""
        output = tmp_dir / "classified.tsv"
        result = classify_contigs(
            exclusion_path=tmp_dir / "no_exc.tsv",
            detection_path=tmp_dir / "no_det.tsv",
            nodes_path=mock_nodes_dmp,
            output_path=output,
        )

        assert output.exists()
        assert result.empty

    @pytest.mark.unit
    def test_output_tsv_format(
        self,
        tmp_dir: Path,
        mock_exclusion_tsv: Path,
        mock_detection_tsv: Path,
        mock_nodes_dmp: Path,
    ):
        """Output TSV is readable by pandas and has correct column types."""
        output = tmp_dir / "classified.tsv"
        classify_contigs(
            exclusion_path=mock_exclusion_tsv,
            detection_path=mock_detection_tsv,
            nodes_path=mock_nodes_dmp,
            output_path=output,
        )

        # Re-read from disk to verify format
        df = pd.read_csv(output, sep="\t")
        assert "seq_id" in df.columns
        assert "classification" in df.columns
        assert df["viral_score"].dtype == float
        assert df["exclusion_evalue"].dtype == float

    @pytest.mark.unit
    def test_custom_threshold(
        self,
        tmp_dir: Path,
        mock_exclusion_tsv: Path,
        mock_detection_tsv: Path,
        mock_nodes_dmp: Path,
    ):
        """Custom viral score threshold changes classification boundaries."""
        output_default = tmp_dir / "classified_default.tsv"
        output_strict = tmp_dir / "classified_strict.tsv"

        result_default = classify_contigs(
            exclusion_path=mock_exclusion_tsv,
            detection_path=mock_detection_tsv,
            nodes_path=mock_nodes_dmp,
            output_path=output_default,
            viral_score_threshold=0.7,
        )

        result_strict = classify_contigs(
            exclusion_path=mock_exclusion_tsv,
            detection_path=mock_detection_tsv,
            nodes_path=mock_nodes_dmp,
            output_path=output_strict,
            viral_score_threshold=0.95,
        )

        # With strict threshold (0.95), contig_2 (score 0.90) should no longer be 'viral'
        c2_default = result_default[result_default["seq_id"] == "contig_2"].iloc[0]
        c2_strict = result_strict[result_strict["seq_id"] == "contig_2"].iloc[0]
        assert c2_default["classification"] == "viral"
        # At 0.95 threshold, 0.90 is below, so it goes to low-viral path
        # exclusion kingdom is viral, so no non-viral kingdom match -> viral_low
        assert c2_strict["classification"] == "viral_low"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------
class TestClassifyContigsCLI:
    """Tests for the command-line interface."""

    @pytest.mark.unit
    def test_cli_basic(
        self,
        tmp_dir: Path,
        mock_exclusion_tsv: Path,
        mock_detection_tsv: Path,
        mock_nodes_dmp: Path,
    ):
        """CLI produces output file successfully."""
        output = tmp_dir / "cli_classified.tsv"
        result = subprocess.run(
            [
                sys.executable,
                str(CLASSIFY_SCRIPT),
                "--exclusion",
                str(mock_exclusion_tsv),
                "--detection",
                str(mock_detection_tsv),
                "--taxonomy-nodes",
                str(mock_nodes_dmp),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"STDERR: {result.stderr}"
        assert output.exists()
        df = pd.read_csv(output, sep="\t")
        assert not df.empty
        assert "seq_id" in df.columns

    @pytest.mark.unit
    def test_cli_custom_threshold(
        self,
        tmp_dir: Path,
        mock_exclusion_tsv: Path,
        mock_detection_tsv: Path,
        mock_nodes_dmp: Path,
    ):
        """CLI accepts --viral-score-threshold parameter."""
        output = tmp_dir / "cli_strict.tsv"
        result = subprocess.run(
            [
                sys.executable,
                str(CLASSIFY_SCRIPT),
                "--exclusion",
                str(mock_exclusion_tsv),
                "--detection",
                str(mock_detection_tsv),
                "--taxonomy-nodes",
                str(mock_nodes_dmp),
                "--output",
                str(output),
                "--viral-score-threshold",
                "0.95",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"STDERR: {result.stderr}"
        assert output.exists()

    @pytest.mark.unit
    def test_cli_stderr_summary(
        self,
        tmp_dir: Path,
        mock_exclusion_tsv: Path,
        mock_detection_tsv: Path,
        mock_nodes_dmp: Path,
    ):
        """CLI prints classification summary to stderr."""
        output = tmp_dir / "cli_summary.tsv"
        result = subprocess.run(
            [
                sys.executable,
                str(CLASSIFY_SCRIPT),
                "--exclusion",
                str(mock_exclusion_tsv),
                "--detection",
                str(mock_detection_tsv),
                "--taxonomy-nodes",
                str(mock_nodes_dmp),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "Classification summary" in result.stderr

    @pytest.mark.unit
    def test_cli_missing_required_args(self):
        """CLI fails with error when required arguments are missing."""
        result = subprocess.run(
            [sys.executable, str(CLASSIFY_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode != 0


# ---------------------------------------------------------------------------
# Nextflow module file existence tests
# ---------------------------------------------------------------------------
class TestNextflowModules:
    """Verify Nextflow module files exist and have expected content."""

    @pytest.mark.module
    def test_diamond_exclusion_nf_exists(self):
        """diamond_exclusion.nf exists in modules/local/."""
        assert DIAMOND_EXCLUSION_NF.exists(), (
            f"Missing: {DIAMOND_EXCLUSION_NF}"
        )

    @pytest.mark.module
    def test_diamond_exclusion_nf_content(self):
        """diamond_exclusion.nf contains expected process definition."""
        content = DIAMOND_EXCLUSION_NF.read_text()
        assert "process DIAMOND_EXCLUSION" in content
        assert "diamond blastx" in content
        assert "exclusion_db" in content
        assert "--max-target-seqs 1" in content
        assert "label 'process_diamond'" in content

    @pytest.mark.module
    def test_classify_contigs_nf_exists(self):
        """classify_contigs.nf exists in modules/local/."""
        assert CLASSIFY_CONTIGS_NF.exists(), (
            f"Missing: {CLASSIFY_CONTIGS_NF}"
        )

    @pytest.mark.module
    def test_classify_contigs_nf_content(self):
        """classify_contigs.nf contains expected process definition."""
        content = CLASSIFY_CONTIGS_NF.read_text()
        assert "process CLASSIFY_CONTIGS" in content
        assert "classify_contigs.py" in content
        assert "--exclusion" in content
        assert "--detection" in content
        assert "--taxonomy-nodes" in content

    @pytest.mark.module
    def test_detection_nf_includes_exclusion(self):
        """detection.nf includes DIAMOND_EXCLUSION and CLASSIFY_CONTIGS modules."""
        detection_nf = PROJECT_ROOT / "subworkflows" / "detection.nf"
        content = detection_nf.read_text()
        assert "DIAMOND_EXCLUSION" in content
        assert "CLASSIFY_CONTIGS" in content

    @pytest.mark.module
    def test_main_nf_has_exclusion_db_channel(self):
        """main.nf references exclusion_db parameter."""
        main_nf = PROJECT_ROOT / "main.nf"
        content = main_nf.read_text()
        assert "exclusion_db" in content

    @pytest.mark.module
    def test_nextflow_config_has_exclusion_db_param(self):
        """nextflow.config defines exclusion_db parameter."""
        config = PROJECT_ROOT / "nextflow.config"
        content = config.read_text()
        assert "exclusion_db" in content
