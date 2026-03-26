"""Tests for FastQC module and BBDuk statistics visualization.

# @TASK T1.4 - FastQC module + BBDuk stats visualization tests
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/modules/test_fastqc_bbduk_viz.py
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
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
FASTQC_NF = MODULES_DIR / "fastqc.nf"
PREPROCESSING_NF = PROJECT_ROOT / "subworkflows" / "preprocessing.nf"
REPORTING_NF = PROJECT_ROOT / "subworkflows" / "reporting.nf"
BASE_CONFIG = PROJECT_ROOT / "conf" / "base.config"
DOCKER_CONFIG = PROJECT_ROOT / "conf" / "docker.config"
DOCKERFILE_QC = PROJECT_ROOT / "containers" / "qc" / "Dockerfile"
BIN_DIR = PROJECT_ROOT / "bin"
VIZ_SCRIPT = BIN_DIR / "visualize_bbduk_stats.py"

# Mock BBDuk stats (3-step combined output)
MOCK_BBDUK_STATS = textwrap.dedent("""\
    BBDuk adapter-trimming statistics:
    Input:                  	78354602 reads 		11831544902 bases.
    KTrimmed:               	11853048 reads (15.13%) 	732571902 bases (6.19%)
    Total Removed:          	2089518 reads (2.67%) 	857093744 bases (7.24%)
    Result:                 	76265084 reads (97.33%) 	10974451158 bases (92.76%)

    BBDuk phix-removal statistics:
    Input:                  	76265084 reads 		10974451158 bases.
    Contaminants:           	42318 reads (0.06%) 	6389418 bases (0.06%)
    Total Removed:          	42318 reads (0.06%) 	6389418 bases (0.06%)
    Result:                 	76222766 reads (99.94%) 	10968061740 bases (99.94%)

    BBDuk quality-trimming statistics:
    Input:                  	76222766 reads 		10968061740 bases.
    QTrimmed:               	1587432 reads (2.08%) 	89341284 bases (0.81%)
    Low quality discards:   	234110 reads (0.31%) 	23871840 bases (0.22%)
    Total Removed:          	1821542 reads (2.39%) 	113213124 bases (1.03%)
    Result:                 	74401224 reads (97.61%) 	10854848616 bases (98.97%)
""")


# ===========================================================================
# Section 1: fastqc.nf Nextflow module structure
# ===========================================================================
class TestFastqcNextflow:
    """Tests for fastqc.nf Nextflow process definition."""

    @pytest.mark.unit
    def test_fastqc_nf_exists(self) -> None:
        """fastqc.nf file must exist."""
        assert FASTQC_NF.exists(), f"fastqc.nf not found at {FASTQC_NF}"

    @pytest.mark.unit
    def test_fastqc_nf_contains_process(self) -> None:
        """fastqc.nf must define a process named FASTQC."""
        content = FASTQC_NF.read_text()
        assert "process FASTQC" in content

    @pytest.mark.unit
    def test_fastqc_nf_has_input_tuple(self) -> None:
        """fastqc.nf input must accept tuple val(meta), path(reads)."""
        content = FASTQC_NF.read_text()
        assert "tuple val(meta), path(reads)" in content

    @pytest.mark.unit
    def test_fastqc_nf_emits_html(self) -> None:
        """fastqc.nf must emit html output."""
        content = FASTQC_NF.read_text()
        assert "emit: html" in content

    @pytest.mark.unit
    def test_fastqc_nf_emits_zip(self) -> None:
        """fastqc.nf must emit zip output."""
        content = FASTQC_NF.read_text()
        assert "emit: zip" in content

    @pytest.mark.unit
    def test_fastqc_nf_uses_task_cpus(self) -> None:
        """fastqc.nf must use task.cpus for thread count."""
        content = FASTQC_NF.read_text()
        assert "task.cpus" in content

    @pytest.mark.unit
    def test_fastqc_nf_has_stub_block(self) -> None:
        """fastqc.nf must have a stub block for dry-run testing."""
        content = FASTQC_NF.read_text()
        assert "stub:" in content

    @pytest.mark.unit
    def test_fastqc_nf_stub_creates_html_and_zip(self) -> None:
        """fastqc.nf stub must create .html and .zip files."""
        content = FASTQC_NF.read_text()
        # Find stub section
        stub_idx = content.index("stub:")
        stub_block = content[stub_idx:]
        assert "fastqc.html" in stub_block
        assert "fastqc.zip" in stub_block

    @pytest.mark.unit
    def test_fastqc_nf_has_tag_annotations(self) -> None:
        """fastqc.nf must have @TASK and @SPEC TAG annotations."""
        content = FASTQC_NF.read_text()
        assert "@TASK" in content
        assert "@SPEC" in content

    @pytest.mark.unit
    def test_fastqc_nf_has_process_label(self) -> None:
        """fastqc.nf must have process_fastqc label."""
        content = FASTQC_NF.read_text()
        assert "process_fastqc" in content


# ===========================================================================
# Section 2: preprocessing.nf includes FastQC before/after trimming
# ===========================================================================
class TestPreprocessingFastqc:
    """Tests for FastQC integration in preprocessing subworkflow."""

    @pytest.mark.unit
    def test_preprocessing_includes_fastqc_raw(self) -> None:
        """preprocessing.nf must include FASTQC as FASTQC_RAW."""
        content = PREPROCESSING_NF.read_text()
        assert "FASTQC_RAW" in content

    @pytest.mark.unit
    def test_preprocessing_includes_fastqc_trimmed(self) -> None:
        """preprocessing.nf must include FASTQC as FASTQC_TRIMMED."""
        content = PREPROCESSING_NF.read_text()
        assert "FASTQC_TRIMMED" in content

    @pytest.mark.unit
    def test_preprocessing_emits_fastqc_raw(self) -> None:
        """preprocessing.nf must emit fastqc_raw channel."""
        content = PREPROCESSING_NF.read_text()
        assert "fastqc_raw" in content

    @pytest.mark.unit
    def test_preprocessing_emits_fastqc_trimmed(self) -> None:
        """preprocessing.nf must emit fastqc_trimmed channel."""
        content = PREPROCESSING_NF.read_text()
        assert "fastqc_trimmed" in content

    @pytest.mark.unit
    def test_preprocessing_includes_fastqc_module(self) -> None:
        """preprocessing.nf must include from fastqc module."""
        content = PREPROCESSING_NF.read_text()
        assert "from '../modules/local/fastqc'" in content


# ===========================================================================
# Section 3: reporting.nf passes FastQC to MultiQC
# ===========================================================================
class TestReportingFastqc:
    """Tests for FastQC results flowing into MultiQC."""

    @pytest.mark.unit
    def test_reporting_takes_fastqc_zip(self) -> None:
        """reporting.nf must accept FastQC zip files."""
        content = REPORTING_NF.read_text()
        assert "ch_fastqc" in content

    @pytest.mark.unit
    def test_reporting_multiqc_includes_fastqc(self) -> None:
        """reporting.nf MultiQC input must include FastQC results."""
        content = REPORTING_NF.read_text()
        assert "ch_fastqc" in content
        assert "MULTIQC" in content


# ===========================================================================
# Section 4: Configuration (base.config, docker.config, Dockerfile)
# ===========================================================================
class TestFastqcConfig:
    """Tests for FastQC resource and container configuration."""

    @pytest.mark.unit
    def test_base_config_has_fastqc_label(self) -> None:
        """base.config must have process_fastqc resource settings."""
        content = BASE_CONFIG.read_text()
        assert "process_fastqc" in content

    @pytest.mark.unit
    def test_docker_config_has_fastqc_label(self) -> None:
        """docker.config must map process_fastqc label to container."""
        content = DOCKER_CONFIG.read_text()
        assert "process_fastqc" in content

    @pytest.mark.unit
    def test_dockerfile_includes_fastqc(self) -> None:
        """QC Dockerfile must install fastqc."""
        content = DOCKERFILE_QC.read_text()
        assert "fastqc" in content.lower()


# ===========================================================================
# Section 5: BBDuk stats parser (visualize_bbduk_stats.py)
# ===========================================================================
class TestBbdukStatsParser:
    """Tests for BBDuk statistics parsing logic."""

    @pytest.fixture(autouse=True)
    def _import_module(self) -> None:
        """Import the visualization module."""
        # Add bin/ to path so we can import
        if str(BIN_DIR) not in sys.path:
            sys.path.insert(0, str(BIN_DIR))
        import visualize_bbduk_stats as mod
        self.mod = mod

    @pytest.mark.unit
    def test_parse_bbduk_stats_returns_dict(self, tmp_path: Path) -> None:
        """parse_bbduk_stats must return a dictionary."""
        stats_file = tmp_path / "sample.bbduk_stats.txt"
        stats_file.write_text(MOCK_BBDUK_STATS)
        result = self.mod.parse_bbduk_stats(stats_file)
        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_parse_bbduk_stats_adapter_step(self, tmp_path: Path) -> None:
        """Parser must extract adapter trimming statistics."""
        stats_file = tmp_path / "sample.bbduk_stats.txt"
        stats_file.write_text(MOCK_BBDUK_STATS)
        result = self.mod.parse_bbduk_stats(stats_file)
        assert "adapter_input_reads" in result
        assert result["adapter_input_reads"] == 78354602
        assert result["adapter_removed_reads"] == 2089518

    @pytest.mark.unit
    def test_parse_bbduk_stats_phix_step(self, tmp_path: Path) -> None:
        """Parser must extract PhiX removal statistics."""
        stats_file = tmp_path / "sample.bbduk_stats.txt"
        stats_file.write_text(MOCK_BBDUK_STATS)
        result = self.mod.parse_bbduk_stats(stats_file)
        assert "phix_input_reads" in result
        assert result["phix_input_reads"] == 76265084
        assert result["phix_removed_reads"] == 42318

    @pytest.mark.unit
    def test_parse_bbduk_stats_quality_step(self, tmp_path: Path) -> None:
        """Parser must extract quality trimming statistics."""
        stats_file = tmp_path / "sample.bbduk_stats.txt"
        stats_file.write_text(MOCK_BBDUK_STATS)
        result = self.mod.parse_bbduk_stats(stats_file)
        assert "quality_input_reads" in result
        assert result["quality_input_reads"] == 76222766
        assert result["quality_removed_reads"] == 1821542

    @pytest.mark.unit
    def test_parse_bbduk_stats_final_result(self, tmp_path: Path) -> None:
        """Parser must extract final result reads."""
        stats_file = tmp_path / "sample.bbduk_stats.txt"
        stats_file.write_text(MOCK_BBDUK_STATS)
        result = self.mod.parse_bbduk_stats(stats_file)
        assert result["quality_result_reads"] == 74401224

    @pytest.mark.unit
    def test_parse_bbduk_stats_has_sample_name(self, tmp_path: Path) -> None:
        """Parser must include sample name derived from filename."""
        stats_file = tmp_path / "GC_Tm.bbduk_stats.txt"
        stats_file.write_text(MOCK_BBDUK_STATS)
        result = self.mod.parse_bbduk_stats(stats_file)
        assert result["sample"] == "GC_Tm"


# ===========================================================================
# Section 6: BBDuk stats visualization functions
# ===========================================================================
class TestBbdukStatsVisualization:
    """Tests for BBDuk statistics visualization functions."""

    @pytest.fixture(autouse=True)
    def _import_and_prepare(self, tmp_path: Path) -> None:
        """Import module and prepare mock data."""
        if str(BIN_DIR) not in sys.path:
            sys.path.insert(0, str(BIN_DIR))
        import visualize_bbduk_stats as mod
        self.mod = mod
        self.tmp_path = tmp_path

        # Create mock stats for two samples
        for name in ("GC_Tm", "Inf_NB_Tm"):
            f = tmp_path / f"{name}.bbduk_stats.txt"
            f.write_text(MOCK_BBDUK_STATS)

        self.stats_list = [
            self.mod.parse_bbduk_stats(tmp_path / "GC_Tm.bbduk_stats.txt"),
            self.mod.parse_bbduk_stats(tmp_path / "Inf_NB_Tm.bbduk_stats.txt"),
        ]

    @pytest.mark.unit
    def test_plot_read_waterfall_creates_file(self) -> None:
        """plot_read_waterfall must create an output figure file."""
        out = self.tmp_path / "waterfall.png"
        self.mod.plot_read_waterfall(self.stats_list, out)
        assert out.exists()
        assert out.stat().st_size > 0

    @pytest.mark.unit
    def test_plot_base_composition_creates_file(self) -> None:
        """plot_base_composition must create an output figure file."""
        out = self.tmp_path / "composition.png"
        self.mod.plot_base_composition(self.stats_list, out)
        assert out.exists()
        assert out.stat().st_size > 0

    @pytest.mark.unit
    def test_plot_qc_summary_table_creates_file(self) -> None:
        """plot_qc_summary_table must create an output figure file."""
        out = self.tmp_path / "summary.png"
        self.mod.plot_qc_summary_table(self.stats_list, out)
        assert out.exists()
        assert out.stat().st_size > 0


# ===========================================================================
# Section 7: CLI interface
# ===========================================================================
class TestBbdukVizCli:
    """Tests for visualize_bbduk_stats.py CLI."""

    @pytest.mark.unit
    def test_cli_help(self) -> None:
        """CLI --help must run without error."""
        result = subprocess.run(
            [sys.executable, str(VIZ_SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--stats" in result.stdout or "usage" in result.stdout.lower()

    @pytest.mark.unit
    def test_cli_generates_figures(self, tmp_path: Path) -> None:
        """CLI must generate all three figure files."""
        stats_file = tmp_path / "sample.bbduk_stats.txt"
        stats_file.write_text(MOCK_BBDUK_STATS)
        out_dir = tmp_path / "figures"

        result = subprocess.run(
            [
                sys.executable,
                str(VIZ_SCRIPT),
                "--stats",
                str(stats_file),
                "--output-dir",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert out_dir.exists()
        # At least one figure should be created
        png_files = list(out_dir.glob("*.png"))
        assert len(png_files) >= 3, f"Expected 3+ figures, got {len(png_files)}: {png_files}"
