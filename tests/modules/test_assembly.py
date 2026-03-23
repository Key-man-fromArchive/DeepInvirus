"""Tests for assembly modules and parse_assembly_stats.py script.

# @TASK T2.1, T2.2 - Assembly module tests (MEGAHIT, metaSPAdes, subworkflow)
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/modules/test_assembly.py
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
PARSE_ASSEMBLY_STATS_SCRIPT = BIN_DIR / "parse_assembly_stats.py"
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
MEGAHIT_NF = MODULES_DIR / "megahit.nf"
METASPADES_NF = MODULES_DIR / "metaspades.nf"
SUBWORKFLOWS_DIR = PROJECT_ROOT / "subworkflows"
ASSEMBLY_NF = SUBWORKFLOWS_DIR / "assembly.nf"

# Expected TSV columns from parse_assembly_stats.py
EXPECTED_COLUMNS = [
    "sample",
    "assembler",
    "num_contigs",
    "total_length",
    "largest_contig",
    "n50",
    "gc_content",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_fasta_single(tmp_dir: Path) -> Path:
    """Create a simple single-contig FASTA file."""
    fasta_path = tmp_dir / "sample1.contigs.fa"
    fasta_path.write_text(
        ">contig_1 length=100\n"
        "ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n"
        "ATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG\n"
        "ATCGATCGATCGATCGATCG\n"
    )
    return fasta_path


@pytest.fixture
def mock_fasta_multiple(tmp_dir: Path) -> Path:
    """Create a multi-contig FASTA file with known statistics.

    Contigs:
        contig_1: 200 bp (100 A + 100 T = 0% GC)
        contig_2: 150 bp (75 G + 75 C = 100% GC)
        contig_3: 100 bp (50 A + 50 G = 50% GC)

    Expected stats:
        num_contigs: 3
        total_length: 450
        largest_contig: 200
        n50: 200 (sorted desc: 200, 150, 100; cumulative 200 >= 225)
        gc_content: (0 + 150 + 50) / 450 = 200/450 ~ 0.4444
    """
    fasta_path = tmp_dir / "sample2.contigs.fa"
    content = (
        ">contig_1\n"
        + "A" * 100 + "\n"
        + "T" * 100 + "\n"
        + ">contig_2\n"
        + "G" * 75 + "\n"
        + "C" * 75 + "\n"
        + ">contig_3\n"
        + "A" * 50 + "\n"
        + "G" * 50 + "\n"
    )
    fasta_path.write_text(content)
    return fasta_path


@pytest.fixture
def mock_fasta_empty(tmp_dir: Path) -> Path:
    """Create an empty FASTA file (no contigs)."""
    fasta_path = tmp_dir / "empty.contigs.fa"
    fasta_path.write_text("")
    return fasta_path


# ---------------------------------------------------------------------------
# Test: megahit.nf file structure
# ---------------------------------------------------------------------------
class TestMegahitNextflow:
    """Tests for megahit.nf Nextflow process definition."""

    @pytest.mark.unit
    def test_megahit_nf_exists(self) -> None:
        """megahit.nf file must exist."""
        assert MEGAHIT_NF.exists(), f"megahit.nf not found at {MEGAHIT_NF}"

    @pytest.mark.unit
    def test_megahit_nf_contains_process(self) -> None:
        """megahit.nf must define a process named MEGAHIT."""
        content = MEGAHIT_NF.read_text()
        assert "process MEGAHIT" in content

    @pytest.mark.unit
    def test_megahit_nf_has_real_command(self) -> None:
        """megahit.nf script block must contain the actual megahit command."""
        content = MEGAHIT_NF.read_text()
        assert "megahit" in content.lower()
        # Must have the paired-end flags
        assert "-1" in content
        assert "-2" in content

    @pytest.mark.unit
    def test_megahit_nf_has_meta_large_preset(self) -> None:
        """megahit.nf must use --presets meta-large for metagenomics."""
        content = MEGAHIT_NF.read_text()
        assert "--presets meta-large" in content

    @pytest.mark.unit
    def test_megahit_nf_has_min_contig_len(self) -> None:
        """megahit.nf must set a minimum contig length filter."""
        content = MEGAHIT_NF.read_text()
        assert "--min-contig-len" in content

    @pytest.mark.unit
    def test_megahit_nf_output_contigs(self) -> None:
        """megahit.nf must emit contigs output channel."""
        content = MEGAHIT_NF.read_text()
        assert "emit: contigs" in content

    @pytest.mark.unit
    def test_megahit_nf_output_stats(self) -> None:
        """megahit.nf must emit stats output channel."""
        content = MEGAHIT_NF.read_text()
        assert "emit: stats" in content

    @pytest.mark.unit
    def test_megahit_nf_calls_parse_assembly_stats(self) -> None:
        """megahit.nf must call parse_assembly_stats.py for statistics."""
        content = MEGAHIT_NF.read_text()
        assert "parse_assembly_stats.py" in content

    @pytest.mark.unit
    def test_megahit_nf_has_stub_block(self) -> None:
        """megahit.nf must retain a stub block for dry-run testing."""
        content = MEGAHIT_NF.read_text()
        assert "stub:" in content

    @pytest.mark.unit
    def test_megahit_nf_has_tag_annotations(self) -> None:
        """megahit.nf must have @TASK and @SPEC TAG annotations."""
        content = MEGAHIT_NF.read_text()
        assert "@TASK" in content
        assert "@SPEC" in content


# ---------------------------------------------------------------------------
# Test: metaspades.nf file structure
# ---------------------------------------------------------------------------
class TestMetaspadesNextflow:
    """Tests for metaspades.nf Nextflow process definition."""

    @pytest.mark.unit
    def test_metaspades_nf_exists(self) -> None:
        """metaspades.nf file must exist."""
        assert METASPADES_NF.exists(), f"metaspades.nf not found at {METASPADES_NF}"

    @pytest.mark.unit
    def test_metaspades_nf_contains_process(self) -> None:
        """metaspades.nf must define a process named METASPADES."""
        content = METASPADES_NF.read_text()
        assert "process METASPADES" in content

    @pytest.mark.unit
    def test_metaspades_nf_has_real_command(self) -> None:
        """metaspades.nf script block must contain the actual metaspades command."""
        content = METASPADES_NF.read_text()
        assert "metaspades.py" in content

    @pytest.mark.unit
    def test_metaspades_nf_has_paired_end_flags(self) -> None:
        """metaspades.nf must specify paired-end input flags."""
        content = METASPADES_NF.read_text()
        assert "-1" in content
        assert "-2" in content

    @pytest.mark.unit
    def test_metaspades_nf_has_memory_limit(self) -> None:
        """metaspades.nf must pass memory limit via -m flag."""
        content = METASPADES_NF.read_text()
        assert "-m" in content

    @pytest.mark.unit
    def test_metaspades_nf_output_contigs(self) -> None:
        """metaspades.nf must emit contigs output channel."""
        content = METASPADES_NF.read_text()
        assert "emit: contigs" in content

    @pytest.mark.unit
    def test_metaspades_nf_output_stats(self) -> None:
        """metaspades.nf must emit stats output channel."""
        content = METASPADES_NF.read_text()
        assert "emit: stats" in content

    @pytest.mark.unit
    def test_metaspades_nf_calls_parse_assembly_stats(self) -> None:
        """metaspades.nf must call parse_assembly_stats.py for statistics."""
        content = METASPADES_NF.read_text()
        assert "parse_assembly_stats.py" in content

    @pytest.mark.unit
    def test_metaspades_nf_has_stub_block(self) -> None:
        """metaspades.nf must retain a stub block for dry-run testing."""
        content = METASPADES_NF.read_text()
        assert "stub:" in content

    @pytest.mark.unit
    def test_metaspades_nf_has_tag_annotations(self) -> None:
        """metaspades.nf must have @TASK and @SPEC TAG annotations."""
        content = METASPADES_NF.read_text()
        assert "@TASK" in content
        assert "@SPEC" in content


# ---------------------------------------------------------------------------
# Test: assembly.nf subworkflow structure
# ---------------------------------------------------------------------------
class TestAssemblySubworkflow:
    """Tests for assembly.nf subworkflow definition."""

    @pytest.mark.unit
    def test_assembly_nf_exists(self) -> None:
        """assembly.nf file must exist."""
        assert ASSEMBLY_NF.exists(), f"assembly.nf not found at {ASSEMBLY_NF}"

    @pytest.mark.unit
    def test_assembly_nf_includes_megahit(self) -> None:
        """assembly.nf must include MEGAHIT module."""
        content = ASSEMBLY_NF.read_text()
        assert "MEGAHIT" in content

    @pytest.mark.unit
    def test_assembly_nf_includes_metaspades(self) -> None:
        """assembly.nf must include METASPADES module."""
        content = ASSEMBLY_NF.read_text()
        assert "METASPADES" in content

    @pytest.mark.unit
    def test_assembly_nf_branching_on_assembler_param(self) -> None:
        """assembly.nf must branch based on params.assembler value."""
        content = ASSEMBLY_NF.read_text()
        assert "params.assembler" in content
        assert "'megahit'" in content
        assert "'metaspades'" in content or "else" in content

    @pytest.mark.unit
    def test_assembly_nf_emits_contigs(self) -> None:
        """assembly.nf must emit a contigs channel."""
        content = ASSEMBLY_NF.read_text()
        assert "emit:" in content
        assert "contigs" in content

    @pytest.mark.unit
    def test_assembly_nf_emits_stats(self) -> None:
        """assembly.nf must emit a stats channel."""
        content = ASSEMBLY_NF.read_text()
        assert "emit:" in content
        assert "stats" in content

    @pytest.mark.unit
    def test_assembly_nf_has_tag_annotations(self) -> None:
        """assembly.nf must have @TASK and @SPEC TAG annotations."""
        content = ASSEMBLY_NF.read_text()
        assert "@TASK" in content
        assert "@SPEC" in content


# ---------------------------------------------------------------------------
# Test: parse_assembly_stats.py exists and is importable
# ---------------------------------------------------------------------------
class TestParseAssemblyStatsScript:
    """Tests for bin/parse_assembly_stats.py script existence."""

    @pytest.mark.unit
    def test_parse_assembly_stats_script_exists(self) -> None:
        """parse_assembly_stats.py must exist in bin/."""
        assert PARSE_ASSEMBLY_STATS_SCRIPT.exists(), (
            f"parse_assembly_stats.py not found at {PARSE_ASSEMBLY_STATS_SCRIPT}"
        )

    @pytest.mark.unit
    def test_parse_assembly_stats_is_importable(self) -> None:
        """parse_assembly_stats.py must be importable as a Python module."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            import parse_assembly_stats  # noqa: F401
        finally:
            sys.path = original_path


# ---------------------------------------------------------------------------
# Test: parse_assembly_stats.py FASTA parsing logic
# ---------------------------------------------------------------------------
class TestParseAssemblyStatsParsing:
    """Tests for FASTA parsing and assembly statistics calculation."""

    def _import_module(self):
        """Helper to import parse_assembly_stats from bin/."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            # Force reimport if already cached
            if "parse_assembly_stats" in sys.modules:
                del sys.modules["parse_assembly_stats"]
            import parse_assembly_stats
            return parse_assembly_stats
        finally:
            sys.path = original_path

    @pytest.mark.unit
    def test_parse_single_contig(self, mock_fasta_single: Path) -> None:
        """parse_assembly_fasta() correctly handles a single-contig FASTA."""
        mod = self._import_module()
        result = mod.parse_assembly_fasta(
            mock_fasta_single, sample_name="sample1", assembler="megahit"
        )

        assert result["sample"] == "sample1"
        assert result["assembler"] == "megahit"
        assert result["num_contigs"] == 1
        assert result["total_length"] == 100
        assert result["largest_contig"] == 100
        assert result["n50"] == 100

    @pytest.mark.unit
    def test_parse_multiple_contigs(self, mock_fasta_multiple: Path) -> None:
        """parse_assembly_fasta() computes correct stats for multiple contigs.

        Expected:
            num_contigs: 3
            total_length: 450
            largest_contig: 200
            n50: 150 (sorted desc: 200,150,100; cumulative 200<225, 200+150=350>=225)
            gc_content: 200/450 ~ 0.4444
        """
        mod = self._import_module()
        result = mod.parse_assembly_fasta(
            mock_fasta_multiple, sample_name="sample2", assembler="metaspades"
        )

        assert result["sample"] == "sample2"
        assert result["assembler"] == "metaspades"
        assert result["num_contigs"] == 3
        assert result["total_length"] == 450
        assert result["largest_contig"] == 200
        assert result["n50"] == 150
        assert abs(result["gc_content"] - 200 / 450) < 1e-4

    @pytest.mark.unit
    def test_parse_empty_fasta(self, mock_fasta_empty: Path) -> None:
        """parse_assembly_fasta() handles an empty FASTA gracefully."""
        mod = self._import_module()
        result = mod.parse_assembly_fasta(
            mock_fasta_empty, sample_name="empty", assembler="megahit"
        )

        assert result["sample"] == "empty"
        assert result["assembler"] == "megahit"
        assert result["num_contigs"] == 0
        assert result["total_length"] == 0
        assert result["largest_contig"] == 0
        assert result["n50"] == 0
        assert result["gc_content"] == 0.0

    @pytest.mark.unit
    def test_result_has_all_expected_columns(self, mock_fasta_single: Path) -> None:
        """Parsed result must contain all expected columns."""
        mod = self._import_module()
        result = mod.parse_assembly_fasta(
            mock_fasta_single, sample_name="test", assembler="megahit"
        )

        for col in EXPECTED_COLUMNS:
            assert col in result, f"Missing column: {col}"

    @pytest.mark.unit
    def test_gc_content_range(self, mock_fasta_multiple: Path) -> None:
        """GC content must be between 0.0 and 1.0."""
        mod = self._import_module()
        result = mod.parse_assembly_fasta(
            mock_fasta_multiple, sample_name="test", assembler="megahit"
        )

        assert 0.0 <= result["gc_content"] <= 1.0

    @pytest.mark.unit
    def test_n50_calculation_correctness(self, tmp_dir: Path) -> None:
        """N50 calculation: smallest contig length where cumulative >= 50% total.

        Contigs: 500, 300, 200, 100 (total=1100, half=550)
        Sorted desc: 500, 300, 200, 100
        Cumulative: 500 < 550, 500+300=800 >= 550 -> N50 = 300
        """
        fasta_path = tmp_dir / "n50test.contigs.fa"
        content = (
            ">c1\n" + "A" * 500 + "\n"
            + ">c2\n" + "A" * 300 + "\n"
            + ">c3\n" + "A" * 200 + "\n"
            + ">c4\n" + "A" * 100 + "\n"
        )
        fasta_path.write_text(content)

        mod = self._import_module()
        result = mod.parse_assembly_fasta(
            fasta_path, sample_name="n50test", assembler="megahit"
        )

        assert result["n50"] == 300

    @pytest.mark.unit
    def test_cli_output_tsv(self, tmp_dir: Path, mock_fasta_multiple: Path) -> None:
        """CLI invocation must produce a valid TSV with correct header."""
        output_tsv = tmp_dir / "assembly_stats.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_ASSEMBLY_STATS_SCRIPT),
                str(mock_fasta_multiple),
                "--assembler", "megahit",
                "--output", str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"parse_assembly_stats.py failed: {result.stderr}"
        )
        assert output_tsv.exists(), "Output TSV not created"

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        assert len(rows) == 1
        assert list(rows[0].keys()) == EXPECTED_COLUMNS

    @pytest.mark.unit
    def test_cli_output_values_numeric(
        self, tmp_dir: Path, mock_fasta_multiple: Path
    ) -> None:
        """All numeric columns in CLI TSV output must be parseable as numbers."""
        output_tsv = tmp_dir / "assembly_stats.tsv"

        subprocess.run(
            [
                sys.executable,
                str(PARSE_ASSEMBLY_STATS_SCRIPT),
                str(mock_fasta_multiple),
                "--assembler", "megahit",
                "--output", str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            row = next(reader)

        numeric_cols = [c for c in EXPECTED_COLUMNS if c not in ("sample", "assembler")]
        for col in numeric_cols:
            try:
                float(row[col])
            except ValueError:
                pytest.fail(f"Column '{col}' value '{row[col]}' is not numeric")

    @pytest.mark.unit
    def test_cli_multiple_fasta_files(self, tmp_dir: Path) -> None:
        """CLI must handle multiple FASTA files and produce multi-row TSV."""
        for name in ["sA", "sB"]:
            fasta = tmp_dir / f"{name}.contigs.fa"
            fasta.write_text(f">c1\n{'ATCG' * 25}\n")

        output_tsv = tmp_dir / "assembly_stats.tsv"
        fasta_files = sorted(tmp_dir.glob("*.contigs.fa"))

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_ASSEMBLY_STATS_SCRIPT),
                *[str(f) for f in fasta_files],
                "--assembler", "megahit",
                "--output", str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        assert len(rows) == 2
        sample_names = [r["sample"] for r in rows]
        assert "sA" in sample_names
        assert "sB" in sample_names
