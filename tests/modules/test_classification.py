"""Tests for Phase 4: classification pipeline modules and Python scripts.

# @TASK T4.1 - MMseqs2 taxonomy + TaxonKit + CoverM module tests
# @TASK T4.2 - bigtable merge script tests
# @TASK T4.3 - Diversity analysis script tests
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @SPEC docs/planning/04-database-design.md#4-핵심-출력-테이블-스키마
# @TEST tests/modules/test_classification.py

Covers:
- merge_results.py: bigtable schema validation, RPM calculation, pivot table
- calc_diversity.py: Shannon/Simpson correctness, Bray-Curtis, PCoA
- Nextflow .nf file structure validation
"""

from __future__ import annotations

import csv
import math
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = PROJECT_ROOT / "bin"
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
SUBWORKFLOWS_DIR = PROJECT_ROOT / "subworkflows"
EXPECTED_DIR = PROJECT_ROOT / "tests" / "data" / "expected"

MERGE_RESULTS_SCRIPT = BIN_DIR / "merge_results.py"
CALC_DIVERSITY_SCRIPT = BIN_DIR / "calc_diversity.py"

MMSEQS_NF = MODULES_DIR / "mmseqs_taxonomy.nf"
TAXONKIT_NF = MODULES_DIR / "taxonkit.nf"
COVERM_NF = MODULES_DIR / "coverm.nf"
MERGE_RESULTS_NF = MODULES_DIR / "merge_results.nf"
DIVERSITY_NF = MODULES_DIR / "diversity.nf"
CLASSIFICATION_NF = SUBWORKFLOWS_DIR / "classification.nf"

# bigtable.tsv expected columns (04-database-design.md section 4.1)
BIGTABLE_COLUMNS = [
    "seq_id",
    "sample",
    "seq_type",
    "length",
    "detection_method",
    "detection_score",
    "taxid",
    "domain",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
    "ictv_classification",
    "baltimore_group",
    "count",
    "rpm",
    "coverage",
]

# alpha_diversity.tsv expected columns (04-database-design.md section 4.3)
ALPHA_COLUMNS = [
    "sample",
    "observed_species",
    "shannon",
    "simpson",
    "chao1",
    "pielou_evenness",
]

# sample_taxon_matrix.tsv header columns (section 4.2)
MATRIX_META_COLUMNS = ["taxon", "taxid", "rank"]


# ---------------------------------------------------------------------------
# Fixtures: mock input data
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_taxonomy_tsv(tmp_dir: Path) -> Path:
    """Mock MMseqs2 taxonomy TSV output."""
    content = textwrap.dedent("""\
        query\ttaxid\trank\tname
        viral_contig_001\t10239\tspecies\tZaire ebolavirus
        read_contig_002\t11320\tspecies\tEnterovirus A
        viral_contig_003\t10566\tspecies\tAfrican swine fever virus
        read_contig_004\t1980410\tspecies\tHuman immunodeficiency virus 1
        viral_contig_005\t11676\tspecies\tVaccinia virus
    """)
    p = tmp_dir / "taxonomy.tsv"
    p.write_text(content)
    return p


@pytest.fixture
def mock_lineage_tsv(tmp_dir: Path) -> Path:
    """Mock TaxonKit lineage output (7-rank TSV)."""
    content = textwrap.dedent("""\
        taxid\tlineage\tdomain\tphylum\tclass\torder\tfamily\tgenus\tspecies
        10239\tViruses;Negarnaviricota;Polyploviricetes;Mononegavirales;Filoviridae;Ebolavirus;Zaire ebolavirus\tVirus\tNegarnaviricota\tPolyploviricetes\tMononegavirales\tFiloviridae\tEbolavirus\tZaire ebolavirus
        11320\tViruses;Pisuviricota;Herviviricetes;Picornavirales;Picornaviridae;Enterovirus;Enterovirus A\tVirus\tPisuviricota\tHerviviricetes\tPicornavirales\tPicornaviridae\tEnterovirus\tEnterovirus A
        10566\tViruses;Nucleocytoviricota;Megaviricetes;Imitervirales;Asfarviridae;Asfarvirus;African swine fever virus\tVirus\tNucleocytoviricota\tMegaviricetes\tImitervirales\tAsfarviridae\tAsfarvirus\tAfrican swine fever virus
        1980410\tViruses;Artverviricota;Revtraviricetes;Ortervirales;Retroviridae;Lentivirus;Human immunodeficiency virus 1\tVirus\tArtverviricota\tRevtraviricetes\tOrtervirales\tRetroviridae\tLentivirus\tHuman immunodeficiency virus 1
        11676\tViruses;Nucleocytoviricota;Megaviricetes;Megavirales;Poxviridae;Orthopoxvirus;Vaccinia virus\tVirus\tNucleocytoviricota\tMegaviricetes\tMegavirales\tPoxviridae\tOrthopoxvirus\tVaccinia virus
    """)
    p = tmp_dir / "lineage.tsv"
    p.write_text(content)
    return p


@pytest.fixture
def mock_coverage_tsv(tmp_dir: Path) -> Path:
    """Mock CoverM coverage output."""
    content = textwrap.dedent("""\
        Contig\tMean\tTrimmed Mean\tCovered Bases\tLength
        viral_contig_001\t18.7\t17.2\t2500\t2847
        viral_contig_003\t12.2\t11.5\t1400\t1524
        viral_contig_005\t25.4\t24.1\t3100\t3200
    """)
    p = tmp_dir / "coverage.tsv"
    p.write_text(content)
    return p


@pytest.fixture
def mock_detection_tsv(tmp_dir: Path) -> Path:
    """Mock merged detection results (output of merge_detection.py)."""
    content = textwrap.dedent("""\
        seq_id\tlength\tdetection_method\tdetection_score\ttaxonomy\ttaxid\tsubject_id
        viral_contig_001\t2847\tboth\t0.95\tViruses;Filoviridae\t10239\tYP_003815426.1
        read_contig_002\t150\tdiamond\t0.87\tViruses;Picornaviridae\t11320\tYP_009506388.1
        viral_contig_003\t1524\tgenomad\t0.92\tViruses;Asfarviridae\t10566\t
        read_contig_004\t150\tdiamond\t0.85\tViruses;Retroviridae\t1980410\tNP_057856.1
        viral_contig_005\t3200\tboth\t0.93\tViruses;Poxviridae\t11676\tYP_233017.1
    """)
    p = tmp_dir / "detection.tsv"
    p.write_text(content)
    return p


@pytest.fixture
def mock_sample_map_tsv(tmp_dir: Path) -> Path:
    """Mock sample mapping file: seq_id -> sample + seq_type + total_reads."""
    content = textwrap.dedent("""\
        seq_id\tsample\tseq_type\ttotal_reads\tcount
        viral_contig_001\tsample_A\tcontig\t199144\t245
        read_contig_002\tsample_A\tread\t199144\t128
        viral_contig_003\tsample_B\tcontig\t197603\t89
        read_contig_004\tsample_B\tread\t197603\t156
        viral_contig_005\tsample_C\tcontig\t199142\t312
    """)
    p = tmp_dir / "sample_map.tsv"
    p.write_text(content)
    return p


@pytest.fixture
def mock_ictv_tsv(tmp_dir: Path) -> Path:
    """Mock ICTV VMR classification mapping."""
    content = textwrap.dedent("""\
        family\tgenus\tspecies\tbaltimore_group\tictv_classification
        Filoviridae\tEbolavirus\tZaire ebolavirus\tGroup V (-ssRNA)\tFiloviridae; Ebolavirus
        Picornaviridae\tEnterovirus\tEnterovirus A\tGroup IV (+ssRNA)\tPicornaviridae; Enterovirus
        Asfarviridae\tAsfarvirus\tAfrican swine fever virus\tGroup I (dsDNA)\tAsfarviridae; Asfarvirus
        Retroviridae\tLentivirus\tHuman immunodeficiency virus 1\tGroup VI (ssRNA-RT)\tRetroviridae; Lentivirus
        Poxviridae\tOrthopoxvirus\tVaccinia virus\tGroup I (dsDNA)\tPoxviridae; Orthopoxvirus
    """)
    p = tmp_dir / "ictv_vmr.tsv"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Fixtures: sample_taxon_matrix for diversity tests
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_sample_taxon_matrix_tsv(tmp_dir: Path) -> Path:
    """Create a sample-taxon matrix for diversity calculation tests.

    Uses the same data as the expected sample_taxon_matrix.tsv.
    """
    content = textwrap.dedent("""\
        taxon\ttaxid\trank\tsample_A\tsample_B\tsample_C
        Ebolavirus\t40566\tgenus\t1230.5\t0.0\t0.0
        Enterovirus\t12059\tgenus\t644.2\t0.0\t0.0
        Asfarvirus\t40359\tgenus\t0.0\t450.3\t0.0
        Lentivirus\t11627\tgenus\t0.0\t785.8\t0.0
        Orthopoxvirus\t10244\tgenus\t0.0\t0.0\t1567.3
    """)
    p = tmp_dir / "sample_taxon_matrix.tsv"
    p.write_text(content)
    return p


# ===========================================================================
# Section 1: merge_results.py tests (T4.2)
# ===========================================================================
class TestMergeResultsScript:
    """Tests for bin/merge_results.py."""

    def test_script_exists(self) -> None:
        assert MERGE_RESULTS_SCRIPT.exists(), (
            f"merge_results.py not found at {MERGE_RESULTS_SCRIPT}"
        )

    def test_script_has_help(self) -> None:
        result = subprocess.run(
            [sys.executable, str(MERGE_RESULTS_SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "bigtable" in result.stdout.lower() or "merge" in result.stdout.lower()

    def test_bigtable_schema_matches_spec(
        self,
        tmp_dir: Path,
        mock_taxonomy_tsv: Path,
        mock_lineage_tsv: Path,
        mock_coverage_tsv: Path,
        mock_detection_tsv: Path,
        mock_sample_map_tsv: Path,
        mock_ictv_tsv: Path,
    ) -> None:
        """bigtable.tsv must have exactly the columns from 04-database-design.md 4.1."""
        bigtable_out = tmp_dir / "bigtable.tsv"
        matrix_out = tmp_dir / "sample_taxon_matrix.tsv"
        counts_out = tmp_dir / "sample_counts.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(MERGE_RESULTS_SCRIPT),
                "--taxonomy", str(mock_taxonomy_tsv),
                "--lineage", str(mock_lineage_tsv),
                "--coverage", str(mock_coverage_tsv),
                "--detection", str(mock_detection_tsv),
                "--sample-map", str(mock_sample_map_tsv),
                "--ictv", str(mock_ictv_tsv),
                "--out-bigtable", str(bigtable_out),
                "--out-matrix", str(matrix_out),
                "--out-counts", str(counts_out),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"merge_results.py failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        assert bigtable_out.exists()

        with open(bigtable_out) as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)

        assert header == BIGTABLE_COLUMNS, (
            f"bigtable columns mismatch.\n"
            f"Expected: {BIGTABLE_COLUMNS}\n"
            f"Got:      {header}"
        )

    def test_bigtable_row_count(
        self,
        tmp_dir: Path,
        mock_taxonomy_tsv: Path,
        mock_lineage_tsv: Path,
        mock_coverage_tsv: Path,
        mock_detection_tsv: Path,
        mock_sample_map_tsv: Path,
        mock_ictv_tsv: Path,
    ) -> None:
        """bigtable should have one row per sequence."""
        bigtable_out = tmp_dir / "bigtable.tsv"
        matrix_out = tmp_dir / "sample_taxon_matrix.tsv"
        counts_out = tmp_dir / "sample_counts.tsv"

        subprocess.run(
            [
                sys.executable,
                str(MERGE_RESULTS_SCRIPT),
                "--taxonomy", str(mock_taxonomy_tsv),
                "--lineage", str(mock_lineage_tsv),
                "--coverage", str(mock_coverage_tsv),
                "--detection", str(mock_detection_tsv),
                "--sample-map", str(mock_sample_map_tsv),
                "--ictv", str(mock_ictv_tsv),
                "--out-bigtable", str(bigtable_out),
                "--out-matrix", str(matrix_out),
                "--out-counts", str(counts_out),
            ],
            capture_output=True,
            text=True,
        )
        with open(bigtable_out) as f:
            lines = f.readlines()
        # header + 5 data rows
        assert len(lines) == 6, f"Expected 6 lines (1 header + 5 data), got {len(lines)}"

    def test_rpm_calculation(
        self,
        tmp_dir: Path,
        mock_taxonomy_tsv: Path,
        mock_lineage_tsv: Path,
        mock_coverage_tsv: Path,
        mock_detection_tsv: Path,
        mock_sample_map_tsv: Path,
        mock_ictv_tsv: Path,
    ) -> None:
        """RPM = count / total_reads * 1e6. Verify for first row."""
        bigtable_out = tmp_dir / "bigtable.tsv"
        matrix_out = tmp_dir / "sample_taxon_matrix.tsv"
        counts_out = tmp_dir / "sample_counts.tsv"

        subprocess.run(
            [
                sys.executable,
                str(MERGE_RESULTS_SCRIPT),
                "--taxonomy", str(mock_taxonomy_tsv),
                "--lineage", str(mock_lineage_tsv),
                "--coverage", str(mock_coverage_tsv),
                "--detection", str(mock_detection_tsv),
                "--sample-map", str(mock_sample_map_tsv),
                "--ictv", str(mock_ictv_tsv),
                "--out-bigtable", str(bigtable_out),
                "--out-matrix", str(matrix_out),
                "--out-counts", str(counts_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(bigtable_out, sep="\t")

        # viral_contig_001: count=245, total_reads=199144
        row = df[df["seq_id"] == "viral_contig_001"].iloc[0]
        expected_rpm = 245 / 199144 * 1e6
        assert abs(float(row["rpm"]) - expected_rpm) < 0.5, (
            f"RPM mismatch: expected ~{expected_rpm:.1f}, got {row['rpm']}"
        )

    def test_sample_taxon_matrix_output(
        self,
        tmp_dir: Path,
        mock_taxonomy_tsv: Path,
        mock_lineage_tsv: Path,
        mock_coverage_tsv: Path,
        mock_detection_tsv: Path,
        mock_sample_map_tsv: Path,
        mock_ictv_tsv: Path,
    ) -> None:
        """sample_taxon_matrix.tsv must have taxon, taxid, rank + sample columns."""
        bigtable_out = tmp_dir / "bigtable.tsv"
        matrix_out = tmp_dir / "sample_taxon_matrix.tsv"
        counts_out = tmp_dir / "sample_counts.tsv"

        subprocess.run(
            [
                sys.executable,
                str(MERGE_RESULTS_SCRIPT),
                "--taxonomy", str(mock_taxonomy_tsv),
                "--lineage", str(mock_lineage_tsv),
                "--coverage", str(mock_coverage_tsv),
                "--detection", str(mock_detection_tsv),
                "--sample-map", str(mock_sample_map_tsv),
                "--ictv", str(mock_ictv_tsv),
                "--out-bigtable", str(bigtable_out),
                "--out-matrix", str(matrix_out),
                "--out-counts", str(counts_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(matrix_out, sep="\t")
        # Must have taxon, taxid, rank as first 3 columns
        assert list(df.columns[:3]) == MATRIX_META_COLUMNS
        # Must have sample columns
        sample_cols = list(df.columns[3:])
        assert "sample_A" in sample_cols
        assert "sample_B" in sample_cols
        assert "sample_C" in sample_cols

    def test_coverage_zero_for_reads(
        self,
        tmp_dir: Path,
        mock_taxonomy_tsv: Path,
        mock_lineage_tsv: Path,
        mock_coverage_tsv: Path,
        mock_detection_tsv: Path,
        mock_sample_map_tsv: Path,
        mock_ictv_tsv: Path,
    ) -> None:
        """Reads (seq_type=read) should have coverage=0.0."""
        bigtable_out = tmp_dir / "bigtable.tsv"
        matrix_out = tmp_dir / "sample_taxon_matrix.tsv"
        counts_out = tmp_dir / "sample_counts.tsv"

        subprocess.run(
            [
                sys.executable,
                str(MERGE_RESULTS_SCRIPT),
                "--taxonomy", str(mock_taxonomy_tsv),
                "--lineage", str(mock_lineage_tsv),
                "--coverage", str(mock_coverage_tsv),
                "--detection", str(mock_detection_tsv),
                "--sample-map", str(mock_sample_map_tsv),
                "--ictv", str(mock_ictv_tsv),
                "--out-bigtable", str(bigtable_out),
                "--out-matrix", str(matrix_out),
                "--out-counts", str(counts_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(bigtable_out, sep="\t")
        reads = df[df["seq_type"] == "read"]
        for _, row in reads.iterrows():
            assert float(row["coverage"]) == 0.0, (
                f"Read {row['seq_id']} should have coverage=0.0, got {row['coverage']}"
            )

    def test_sample_counts_output(
        self,
        tmp_dir: Path,
        mock_taxonomy_tsv: Path,
        mock_lineage_tsv: Path,
        mock_coverage_tsv: Path,
        mock_detection_tsv: Path,
        mock_sample_map_tsv: Path,
        mock_ictv_tsv: Path,
    ) -> None:
        """sample_counts.tsv must have sample, taxon, count columns."""
        bigtable_out = tmp_dir / "bigtable.tsv"
        matrix_out = tmp_dir / "sample_taxon_matrix.tsv"
        counts_out = tmp_dir / "sample_counts.tsv"

        subprocess.run(
            [
                sys.executable,
                str(MERGE_RESULTS_SCRIPT),
                "--taxonomy", str(mock_taxonomy_tsv),
                "--lineage", str(mock_lineage_tsv),
                "--coverage", str(mock_coverage_tsv),
                "--detection", str(mock_detection_tsv),
                "--sample-map", str(mock_sample_map_tsv),
                "--ictv", str(mock_ictv_tsv),
                "--out-bigtable", str(bigtable_out),
                "--out-matrix", str(matrix_out),
                "--out-counts", str(counts_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(counts_out, sep="\t")
        assert "sample" in df.columns
        assert "taxon" in df.columns
        assert "count" in df.columns


# ===========================================================================
# Section 2: calc_diversity.py tests (T4.3)
# ===========================================================================
class TestCalcDiversityScript:
    """Tests for bin/calc_diversity.py."""

    def test_script_exists(self) -> None:
        assert CALC_DIVERSITY_SCRIPT.exists(), (
            f"calc_diversity.py not found at {CALC_DIVERSITY_SCRIPT}"
        )

    def test_script_has_help(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CALC_DIVERSITY_SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "diversity" in result.stdout.lower() or "alpha" in result.stdout.lower()

    def test_alpha_diversity_schema(
        self,
        tmp_dir: Path,
        mock_sample_taxon_matrix_tsv: Path,
    ) -> None:
        """alpha_diversity.tsv must have exactly the columns from 04-database-design.md 4.3."""
        alpha_out = tmp_dir / "alpha_diversity.tsv"
        beta_out = tmp_dir / "beta_diversity.tsv"
        pcoa_out = tmp_dir / "pcoa_coordinates.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(CALC_DIVERSITY_SCRIPT),
                "--matrix", str(mock_sample_taxon_matrix_tsv),
                "--out-alpha", str(alpha_out),
                "--out-beta", str(beta_out),
                "--out-pcoa", str(pcoa_out),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"calc_diversity.py failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        with open(alpha_out) as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)

        assert header == ALPHA_COLUMNS, (
            f"alpha_diversity columns mismatch.\n"
            f"Expected: {ALPHA_COLUMNS}\n"
            f"Got:      {header}"
        )

    def test_shannon_diversity_calculation(
        self,
        tmp_dir: Path,
        mock_sample_taxon_matrix_tsv: Path,
    ) -> None:
        """Shannon diversity: H' = -sum(pi * ln(pi)).

        For sample_A with RPM values [1230.5, 644.2]:
          total = 1874.7
          p1 = 1230.5/1874.7, p2 = 644.2/1874.7
          H' = -(p1*ln(p1) + p2*ln(p2))
        """
        alpha_out = tmp_dir / "alpha_diversity.tsv"
        beta_out = tmp_dir / "beta_diversity.tsv"
        pcoa_out = tmp_dir / "pcoa_coordinates.tsv"

        subprocess.run(
            [
                sys.executable,
                str(CALC_DIVERSITY_SCRIPT),
                "--matrix", str(mock_sample_taxon_matrix_tsv),
                "--out-alpha", str(alpha_out),
                "--out-beta", str(beta_out),
                "--out-pcoa", str(pcoa_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(alpha_out, sep="\t")
        row_a = df[df["sample"] == "sample_A"].iloc[0]

        # Manual calculation
        vals = np.array([1230.5, 644.2])
        total = vals.sum()
        props = vals / total
        expected_shannon = -np.sum(props * np.log(props))

        assert abs(float(row_a["shannon"]) - expected_shannon) < 0.01, (
            f"Shannon mismatch for sample_A: "
            f"expected {expected_shannon:.3f}, got {row_a['shannon']}"
        )

    def test_simpson_diversity_calculation(
        self,
        tmp_dir: Path,
        mock_sample_taxon_matrix_tsv: Path,
    ) -> None:
        """Simpson diversity: D = 1 - sum(pi^2)."""
        alpha_out = tmp_dir / "alpha_diversity.tsv"
        beta_out = tmp_dir / "beta_diversity.tsv"
        pcoa_out = tmp_dir / "pcoa_coordinates.tsv"

        subprocess.run(
            [
                sys.executable,
                str(CALC_DIVERSITY_SCRIPT),
                "--matrix", str(mock_sample_taxon_matrix_tsv),
                "--out-alpha", str(alpha_out),
                "--out-beta", str(beta_out),
                "--out-pcoa", str(pcoa_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(alpha_out, sep="\t")
        row_a = df[df["sample"] == "sample_A"].iloc[0]

        vals = np.array([1230.5, 644.2])
        total = vals.sum()
        props = vals / total
        expected_simpson = 1.0 - np.sum(props ** 2)

        assert abs(float(row_a["simpson"]) - expected_simpson) < 0.01, (
            f"Simpson mismatch for sample_A: "
            f"expected {expected_simpson:.3f}, got {row_a['simpson']}"
        )

    def test_single_species_diversity_zero(
        self,
        tmp_dir: Path,
        mock_sample_taxon_matrix_tsv: Path,
    ) -> None:
        """A sample with only one species should have Shannon=0, Simpson=0."""
        alpha_out = tmp_dir / "alpha_diversity.tsv"
        beta_out = tmp_dir / "beta_diversity.tsv"
        pcoa_out = tmp_dir / "pcoa_coordinates.tsv"

        subprocess.run(
            [
                sys.executable,
                str(CALC_DIVERSITY_SCRIPT),
                "--matrix", str(mock_sample_taxon_matrix_tsv),
                "--out-alpha", str(alpha_out),
                "--out-beta", str(beta_out),
                "--out-pcoa", str(pcoa_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(alpha_out, sep="\t")
        row_c = df[df["sample"] == "sample_C"].iloc[0]

        assert float(row_c["shannon"]) == 0.0
        assert float(row_c["simpson"]) == 0.0
        assert int(row_c["observed_species"]) == 1

    def test_chao1_calculation(
        self,
        tmp_dir: Path,
        mock_sample_taxon_matrix_tsv: Path,
    ) -> None:
        """Chao1: when no singletons/doubletons exist, Chao1 = observed species."""
        alpha_out = tmp_dir / "alpha_diversity.tsv"
        beta_out = tmp_dir / "beta_diversity.tsv"
        pcoa_out = tmp_dir / "pcoa_coordinates.tsv"

        subprocess.run(
            [
                sys.executable,
                str(CALC_DIVERSITY_SCRIPT),
                "--matrix", str(mock_sample_taxon_matrix_tsv),
                "--out-alpha", str(alpha_out),
                "--out-beta", str(beta_out),
                "--out-pcoa", str(pcoa_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(alpha_out, sep="\t")
        # For RPM abundance data (no true integer singletons), Chao1 ~ observed
        for _, row in df.iterrows():
            obs = int(row["observed_species"])
            chao1 = float(row["chao1"])
            # Chao1 should be >= observed species
            assert chao1 >= obs, (
                f"Chao1 ({chao1}) should be >= observed ({obs}) for {row['sample']}"
            )

    def test_pielou_evenness(
        self,
        tmp_dir: Path,
        mock_sample_taxon_matrix_tsv: Path,
    ) -> None:
        """Pielou's evenness: J = H'/ln(S). Single species -> 0."""
        alpha_out = tmp_dir / "alpha_diversity.tsv"
        beta_out = tmp_dir / "beta_diversity.tsv"
        pcoa_out = tmp_dir / "pcoa_coordinates.tsv"

        subprocess.run(
            [
                sys.executable,
                str(CALC_DIVERSITY_SCRIPT),
                "--matrix", str(mock_sample_taxon_matrix_tsv),
                "--out-alpha", str(alpha_out),
                "--out-beta", str(beta_out),
                "--out-pcoa", str(pcoa_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(alpha_out, sep="\t")
        row_c = df[df["sample"] == "sample_C"].iloc[0]
        assert float(row_c["pielou_evenness"]) == 0.0

        row_a = df[df["sample"] == "sample_A"].iloc[0]
        # With 2 species, max evenness = 1.0 (equal proportions)
        assert 0.0 < float(row_a["pielou_evenness"]) <= 1.0

    def test_beta_diversity_symmetric_matrix(
        self,
        tmp_dir: Path,
        mock_sample_taxon_matrix_tsv: Path,
    ) -> None:
        """Beta diversity matrix must be symmetric with diagonal = 0."""
        alpha_out = tmp_dir / "alpha_diversity.tsv"
        beta_out = tmp_dir / "beta_diversity.tsv"
        pcoa_out = tmp_dir / "pcoa_coordinates.tsv"

        subprocess.run(
            [
                sys.executable,
                str(CALC_DIVERSITY_SCRIPT),
                "--matrix", str(mock_sample_taxon_matrix_tsv),
                "--out-alpha", str(alpha_out),
                "--out-beta", str(beta_out),
                "--out-pcoa", str(pcoa_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(beta_out, sep="\t", index_col=0)
        matrix = df.values.astype(float)
        n = matrix.shape[0]
        assert matrix.shape == (n, n), "Beta diversity must be square"

        # Diagonal = 0
        for i in range(n):
            assert matrix[i, i] == 0.0, f"Diagonal [{i},{i}] should be 0"

        # Symmetric
        for i in range(n):
            for j in range(i + 1, n):
                assert abs(matrix[i, j] - matrix[j, i]) < 1e-10, (
                    f"Matrix not symmetric at [{i},{j}]: "
                    f"{matrix[i, j]} vs {matrix[j, i]}"
                )

    def test_bray_curtis_known_values(
        self,
        tmp_dir: Path,
        mock_sample_taxon_matrix_tsv: Path,
    ) -> None:
        """Bray-Curtis: BC = 1 - 2*sum(min(xi,yi)) / (sum(xi)+sum(yi)).

        sample_A has non-overlapping taxa with sample_C,
        so BC(A,C) should be 1.0 (completely dissimilar).
        """
        alpha_out = tmp_dir / "alpha_diversity.tsv"
        beta_out = tmp_dir / "beta_diversity.tsv"
        pcoa_out = tmp_dir / "pcoa_coordinates.tsv"

        subprocess.run(
            [
                sys.executable,
                str(CALC_DIVERSITY_SCRIPT),
                "--matrix", str(mock_sample_taxon_matrix_tsv),
                "--out-alpha", str(alpha_out),
                "--out-beta", str(beta_out),
                "--out-pcoa", str(pcoa_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(beta_out, sep="\t", index_col=0)

        # A and C have completely non-overlapping taxa
        bc_ac = float(df.loc["sample_A", "sample_C"])
        assert abs(bc_ac - 1.0) < 0.01, (
            f"BC(A,C) should be ~1.0 (no overlap), got {bc_ac}"
        )

        # B and C have completely non-overlapping taxa
        bc_bc = float(df.loc["sample_B", "sample_C"])
        assert abs(bc_bc - 1.0) < 0.01, (
            f"BC(B,C) should be ~1.0, got {bc_bc}"
        )

        # A and B also non-overlapping
        bc_ab = float(df.loc["sample_A", "sample_B"])
        assert abs(bc_ab - 1.0) < 0.01, (
            f"BC(A,B) should be ~1.0, got {bc_ab}"
        )

    def test_pcoa_coordinates_output(
        self,
        tmp_dir: Path,
        mock_sample_taxon_matrix_tsv: Path,
    ) -> None:
        """PCoA coordinates file must have sample, PC1, PC2 columns."""
        alpha_out = tmp_dir / "alpha_diversity.tsv"
        beta_out = tmp_dir / "beta_diversity.tsv"
        pcoa_out = tmp_dir / "pcoa_coordinates.tsv"

        subprocess.run(
            [
                sys.executable,
                str(CALC_DIVERSITY_SCRIPT),
                "--matrix", str(mock_sample_taxon_matrix_tsv),
                "--out-alpha", str(alpha_out),
                "--out-beta", str(beta_out),
                "--out-pcoa", str(pcoa_out),
            ],
            capture_output=True,
            text=True,
        )
        import pandas as pd

        df = pd.read_csv(pcoa_out, sep="\t")
        assert "sample" in df.columns
        assert "PC1" in df.columns
        assert "PC2" in df.columns
        assert len(df) == 3  # 3 samples


# ===========================================================================
# Section 3: Nextflow .nf file structure tests
# ===========================================================================
class TestNextflowModuleStructure:
    """Validate Nextflow module file structure and content."""

    def test_mmseqs_taxonomy_nf_has_lca_mode(self) -> None:
        content = MMSEQS_NF.read_text()
        assert "lca-mode" in content or "lca_mode" in content, (
            "mmseqs_taxonomy.nf should use --lca-mode"
        )
        assert "easy-taxonomy" in content

    def test_taxonkit_nf_has_reformat(self) -> None:
        content = TAXONKIT_NF.read_text()
        assert "reformat" in content
        assert "{k}" in content or "{s}" in content, (
            "taxonkit.nf should use format placeholders"
        )

    def test_coverm_nf_has_methods(self) -> None:
        content = COVERM_NF.read_text()
        assert "mean" in content
        assert "trimmed_mean" in content
        assert "covered_bases" in content

    def test_merge_results_nf_outputs(self) -> None:
        content = MERGE_RESULTS_NF.read_text()
        assert "bigtable.tsv" in content
        assert "sample_taxon_matrix.tsv" in content
        assert "sample_counts.tsv" in content

    def test_diversity_nf_outputs(self) -> None:
        content = DIVERSITY_NF.read_text()
        assert "alpha_diversity.tsv" in content
        assert "beta_diversity.tsv" in content
        assert "pcoa_coordinates.tsv" in content

    def test_classification_subworkflow_structure(self) -> None:
        content = CLASSIFICATION_NF.read_text()
        assert "MMSEQS_TAXONOMY" in content
        assert "TAXONKIT_REFORMAT" in content
        assert "COVERM" in content
        assert "MERGE_RESULTS" in content
        assert "DIVERSITY" in content
        # Must emit bigtable and diversity
        assert "bigtable" in content
        assert "alpha" in content
        assert "beta" in content
        assert "sample_matrix" in content or "matrix" in content

    def test_merge_results_nf_has_matrix_output(self) -> None:
        """merge_results.nf must emit sample_taxon_matrix."""
        content = MERGE_RESULTS_NF.read_text()
        assert "emit:" not in content or "matrix" in content, (
            "merge_results.nf should emit sample_taxon_matrix"
        )

    def test_mmseqs_taxonomy_nf_has_threads(self) -> None:
        content = MMSEQS_NF.read_text()
        assert "threads" in content.lower() or "task.cpus" in content
