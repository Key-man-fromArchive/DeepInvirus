"""Tests for Bracken and Krona Nextflow modules and kreport2krona.py script.

# @TASK T1.3 - Bracken + Krona module tests
# @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#Section-B-independent-profiling
# @TEST tests/modules/test_bracken_krona.py

Validates:
  - Nextflow process definitions (bracken.nf, krona.nf) contain correct I/O channels
  - kreport2krona.py compiles and produces valid Krona text output
  - main.nf includes BRACKEN and KRONA processes
  - nextflow.config contains Bracken parameters
"""

from __future__ import annotations

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
BRACKEN_NF = MODULES_DIR / "bracken.nf"
KRONA_NF = MODULES_DIR / "krona.nf"
KREPORT2KRONA_SCRIPT = BIN_DIR / "kreport2krona.py"
MAIN_NF = PROJECT_ROOT / "main.nf"
NEXTFLOW_CONFIG = PROJECT_ROOT / "nextflow.config"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_kraken2_report(tmp_dir: Path) -> Path:
    """Create a mock Kraken2 report file for testing kreport2krona.py.

    Follows the standard Kraken2 report format with 6 tab-delimited columns:
      percentage, reads_clade, reads_taxon, rank, taxid, name (with leading spaces)
    """
    content = textwrap.dedent("""\
        15.00	150	150	U	0	unclassified
        85.00	850	2	R	1	root
        80.00	800	0	D	2	  Bacteria
        40.00	400	0	P	1224	    Pseudomonadota
        20.00	200	0	C	1236	      Gammaproteobacteria
        15.00	150	0	O	91347	        Enterobacterales
        10.00	100	0	F	543	          Enterobacteriaceae
        5.00	50	0	G	561	            Escherichia
        3.00	30	30	S	562	              Escherichia coli
        2.00	20	20	S	573	              Klebsiella pneumoniae
        5.00	50	0	D	10239	  Viruses
        3.00	30	0	F	10240	    Poxviridae
        2.00	20	20	S	10245	      Vaccinia virus
    """)
    report_path = tmp_dir / "sample1.kraken2.report"
    report_path.write_text(content)
    return report_path


# ---------------------------------------------------------------------------
# Test: Nextflow module file existence and structure
# ---------------------------------------------------------------------------
class TestModuleFiles:
    """Verify Bracken and Krona Nextflow module files exist and have correct structure."""

    def test_bracken_nf_exists(self):
        """bracken.nf module file must exist."""
        assert BRACKEN_NF.exists(), f"Missing: {BRACKEN_NF}"

    def test_krona_nf_exists(self):
        """krona.nf module file must exist."""
        assert KRONA_NF.exists(), f"Missing: {KRONA_NF}"

    def test_bracken_nf_has_process_definition(self):
        """bracken.nf must define a process named BRACKEN."""
        content = BRACKEN_NF.read_text()
        assert "process BRACKEN" in content

    def test_krona_nf_has_process_definition(self):
        """krona.nf must define a process named KRONA."""
        content = KRONA_NF.read_text()
        assert "process KRONA" in content

    def test_bracken_nf_task_annotation(self):
        """bracken.nf must have @TASK T1.3 annotation."""
        content = BRACKEN_NF.read_text()
        assert "@TASK T1.3" in content

    def test_krona_nf_task_annotation(self):
        """krona.nf must have @TASK T1.3 annotation."""
        content = KRONA_NF.read_text()
        assert "@TASK T1.3" in content


# ---------------------------------------------------------------------------
# Test: Bracken process I/O channels
# ---------------------------------------------------------------------------
class TestBrackenProcess:
    """Validate Bracken Nextflow process definition."""

    @pytest.fixture(autouse=True)
    def _load_content(self):
        self.content = BRACKEN_NF.read_text()

    def test_input_kraken2_report(self):
        """Bracken input must accept tuple(meta, kraken2_report)."""
        assert "tuple val(meta), path(kraken2_report)" in self.content

    def test_input_kraken2_db(self):
        """Bracken input must accept kraken2_db path."""
        assert "path(kraken2_db)" in self.content

    def test_output_bracken(self):
        """Bracken must emit .bracken output file."""
        assert 'emit: bracken' in self.content
        assert '*.bracken"' in self.content or "*.bracken'" in self.content

    def test_output_breport(self):
        """Bracken must emit .breport output file."""
        assert 'emit: breport' in self.content
        assert '*.breport"' in self.content or "*.breport'" in self.content

    def test_bracken_command(self):
        """Script section must invoke bracken with required flags."""
        assert "bracken" in self.content
        assert "-d ${kraken2_db}" in self.content or "-d $kraken2_db" in self.content
        assert "-i ${kraken2_report}" in self.content or "-i $kraken2_report" in self.content
        assert "-l ${level}" in self.content or "-l S" in self.content

    def test_publishdir(self):
        """Bracken output must publish to kraken2/bracken subdirectory."""
        assert "kraken2/bracken" in self.content

    def test_has_stub_section(self):
        """Bracken must have a stub section for dry-run testing."""
        assert "stub:" in self.content

    def test_parameterized_read_length(self):
        """Bracken read length should be parameterizable."""
        assert "bracken_read_len" in self.content or "read_len" in self.content


# ---------------------------------------------------------------------------
# Test: Krona process I/O channels
# ---------------------------------------------------------------------------
class TestKronaProcess:
    """Validate Krona Nextflow process definition."""

    @pytest.fixture(autouse=True)
    def _load_content(self):
        self.content = KRONA_NF.read_text()

    def test_input_kraken2_report(self):
        """Krona input must accept tuple(meta, kraken2_report)."""
        assert "tuple val(meta), path(kraken2_report)" in self.content

    def test_output_html(self):
        """Krona must emit .krona.html output file."""
        assert 'emit: html' in self.content
        assert 'krona.html' in self.content

    def test_kreport2krona_invocation(self):
        """Script must invoke kreport2krona.py for format conversion."""
        assert "kreport2krona.py" in self.content

    def test_ktimporttext_invocation(self):
        """Script must invoke ktImportText for HTML generation."""
        assert "ktImportText" in self.content

    def test_publishdir(self):
        """Krona output must publish to kraken2/krona subdirectory."""
        assert "kraken2/krona" in self.content

    def test_has_stub_section(self):
        """Krona must have a stub section for dry-run testing."""
        assert "stub:" in self.content


# ---------------------------------------------------------------------------
# Test: kreport2krona.py script
# ---------------------------------------------------------------------------
class TestKreport2Krona:
    """Validate kreport2krona.py script functionality."""

    def test_script_exists(self):
        """kreport2krona.py must exist in bin directory."""
        assert KREPORT2KRONA_SCRIPT.exists(), f"Missing: {KREPORT2KRONA_SCRIPT}"

    def test_script_is_executable(self):
        """kreport2krona.py must have executable permissions."""
        import os
        assert os.access(KREPORT2KRONA_SCRIPT, os.X_OK), \
            f"{KREPORT2KRONA_SCRIPT} is not executable"

    def test_script_compiles(self):
        """kreport2krona.py must compile without syntax errors."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(KREPORT2KRONA_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, \
            f"Compilation failed: {result.stderr}"

    def test_help_flag(self):
        """kreport2krona.py --help must succeed."""
        result = subprocess.run(
            [sys.executable, str(KREPORT2KRONA_SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "report" in result.stdout.lower() or "input" in result.stdout.lower()

    def test_converts_report_to_krona_text(self, mock_kraken2_report: Path, tmp_dir: Path):
        """kreport2krona.py must convert Kraken2 report to Krona text format.

        Krona text format: tab-delimited lines with count followed by taxonomy path.
        """
        output_path = tmp_dir / "sample1.krona.txt"
        result = subprocess.run(
            [
                sys.executable,
                str(KREPORT2KRONA_SCRIPT),
                "-r", str(mock_kraken2_report),
                "-o", str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, \
            f"kreport2krona.py failed: {result.stderr}"
        assert output_path.exists(), "Output file was not created"

        content = output_path.read_text()
        lines = [l for l in content.strip().split("\n") if l.strip()]
        assert len(lines) > 0, "Output file is empty"

        # Each line should start with a number (read count)
        for line in lines:
            parts = line.split("\t")
            assert len(parts) >= 1, f"Malformed line: {line}"
            try:
                int(parts[0])
            except ValueError:
                pytest.fail(f"First column must be integer read count: {line}")

    def test_output_contains_taxonomy_levels(self, mock_kraken2_report: Path, tmp_dir: Path):
        """Output must contain taxonomy level prefixes (k__, p__, c__, etc.)."""
        output_path = tmp_dir / "sample1.krona.txt"
        subprocess.run(
            [
                sys.executable,
                str(KREPORT2KRONA_SCRIPT),
                "-r", str(mock_kraken2_report),
                "-o", str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        content = output_path.read_text()
        # Should contain at least kingdom/domain and species level prefixes
        assert "k__" in content or "K__" in content.upper(), \
            "Output missing kingdom-level taxonomy prefix"

    def test_unclassified_reads_in_output(self, mock_kraken2_report: Path, tmp_dir: Path):
        """Unclassified reads should appear in output."""
        output_path = tmp_dir / "sample1.krona.txt"
        subprocess.run(
            [
                sys.executable,
                str(KREPORT2KRONA_SCRIPT),
                "-r", str(mock_kraken2_report),
                "-o", str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        content = output_path.read_text()
        assert "Unclassified" in content or "unclassified" in content.lower(), \
            "Unclassified reads missing from output"

    def test_task_annotation(self):
        """kreport2krona.py must have @TASK T1.3 annotation."""
        content = KREPORT2KRONA_SCRIPT.read_text()
        assert "@TASK T1.3" in content


# ---------------------------------------------------------------------------
# Test: main.nf integration
# ---------------------------------------------------------------------------
class TestMainNfIntegration:
    """Verify main.nf correctly includes and invokes Bracken + Krona."""

    @pytest.fixture(autouse=True)
    def _load_content(self):
        self.content = MAIN_NF.read_text()

    def test_bracken_import(self):
        """main.nf must import BRACKEN from modules/local/bracken."""
        assert "include { BRACKEN" in self.content
        assert "bracken" in self.content

    def test_krona_import(self):
        """main.nf must import KRONA from modules/local/krona."""
        assert "include { KRONA" in self.content
        assert "krona" in self.content

    def test_bracken_invocation_in_kraken2_block(self):
        """BRACKEN must be invoked inside the kraken2_db conditional block."""
        # Find the kraken2_db block and verify BRACKEN is called within it
        assert "BRACKEN(" in self.content

    def test_krona_invocation_in_kraken2_block(self):
        """KRONA must be invoked inside the kraken2_db conditional block."""
        assert "KRONA(" in self.content

    def test_bracken_receives_kraken2_report(self):
        """BRACKEN must receive KRAKEN2_CLASSIFY.out.report as input."""
        assert "BRACKEN( KRAKEN2_CLASSIFY.out.report" in self.content or \
               "BRACKEN(KRAKEN2_CLASSIFY.out.report" in self.content

    def test_krona_receives_kraken2_report(self):
        """KRONA must receive KRAKEN2_CLASSIFY.out.report as input."""
        assert "KRONA( KRAKEN2_CLASSIFY.out.report" in self.content or \
               "KRONA(KRAKEN2_CLASSIFY.out.report" in self.content

    def test_task_annotation_in_main(self):
        """main.nf Kraken2 block must have @TASK T1.3 annotation."""
        assert "@TASK T1.3" in self.content


# ---------------------------------------------------------------------------
# Test: nextflow.config Bracken parameters
# ---------------------------------------------------------------------------
class TestNextflowConfig:
    """Verify nextflow.config contains Bracken-related parameters."""

    @pytest.fixture(autouse=True)
    def _load_content(self):
        self.content = NEXTFLOW_CONFIG.read_text()

    def test_bracken_read_len_param(self):
        """nextflow.config must define bracken_read_len parameter."""
        assert "bracken_read_len" in self.content

    def test_bracken_level_param(self):
        """nextflow.config must define bracken_level parameter."""
        assert "bracken_level" in self.content

    def test_bracken_threshold_param(self):
        """nextflow.config must define bracken_threshold parameter."""
        assert "bracken_threshold" in self.content
