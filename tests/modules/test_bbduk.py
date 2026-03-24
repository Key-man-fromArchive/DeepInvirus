"""Tests for BBDuk module and trimmer selection logic.

# @TASK T1.1 - BBDuk QC module tests
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/modules/test_bbduk.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
BBDUK_NF = MODULES_DIR / "bbduk.nf"
PREPROCESSING_NF = PROJECT_ROOT / "subworkflows" / "preprocessing.nf"
MAIN_NF = PROJECT_ROOT / "main.nf"
NEXTFLOW_CONFIG = PROJECT_ROOT / "nextflow.config"
DOCKER_CONFIG = PROJECT_ROOT / "conf" / "docker.config"
DOCKERFILE_QC = PROJECT_ROOT / "containers" / "qc" / "Dockerfile"


# ---------------------------------------------------------------------------
# Test: bbduk.nf file structure
# ---------------------------------------------------------------------------
class TestBbdukNextflow:
    """Tests for bbduk.nf Nextflow process definition."""

    @pytest.mark.unit
    def test_bbduk_nf_exists(self) -> None:
        """bbduk.nf file must exist."""
        assert BBDUK_NF.exists(), f"bbduk.nf not found at {BBDUK_NF}"

    @pytest.mark.unit
    def test_bbduk_nf_contains_process(self) -> None:
        """bbduk.nf must define a process named BBDUK."""
        content = BBDUK_NF.read_text()
        assert "process BBDUK" in content

    @pytest.mark.unit
    def test_bbduk_nf_has_three_steps(self) -> None:
        """bbduk.nf must contain 3 separate bbduk.sh invocations."""
        content = BBDUK_NF.read_text()
        bbduk_calls = content.count("bbduk.sh")
        # script block has 3 calls, stub has 0
        assert bbduk_calls >= 3, (
            f"Expected at least 3 bbduk.sh calls, found {bbduk_calls}"
        )

    @pytest.mark.unit
    def test_bbduk_nf_step1_adapter_removal(self) -> None:
        """Step 1 must remove adapters with ref=adapters,artifacts."""
        content = BBDUK_NF.read_text()
        assert "ref=adapters,artifacts" in content, (
            "Missing adapter reference in step 1"
        )
        assert "ktrim=r" in content
        assert "k=23" in content
        assert "mink=11" in content

    @pytest.mark.unit
    def test_bbduk_nf_step2_phix_removal(self) -> None:
        """Step 2 must remove PhiX and sequencing artifacts."""
        content = BBDUK_NF.read_text()
        assert "phix174_ill.ref.fa.gz" in content, (
            "Missing PhiX reference in step 2"
        )
        assert "sequencing_artifacts.fa.gz" in content, (
            "Missing sequencing artifacts reference in step 2"
        )

    @pytest.mark.unit
    def test_bbduk_nf_step3_quality_trimming(self) -> None:
        """Step 3 must perform quality trimming and length filtering."""
        content = BBDUK_NF.read_text()
        assert "qtrim=r" in content, "Missing quality trimming direction"
        assert "trimq=20" in content, "Missing quality threshold"
        assert "minlength=90" in content, "Missing minimum length filter"
        assert "maq=20" in content, "Missing mean quality filter"

    @pytest.mark.unit
    def test_bbduk_nf_output_filenames(self) -> None:
        """bbduk.nf must produce correctly named output files."""
        content = BBDUK_NF.read_text()
        assert "_R1.trimmed.fastq.gz" in content
        assert "_R2.trimmed.fastq.gz" in content
        assert ".bbduk_stats.txt" in content

    @pytest.mark.unit
    def test_bbduk_nf_has_stub_block(self) -> None:
        """bbduk.nf must have a stub block for dry-run testing."""
        content = BBDUK_NF.read_text()
        assert "stub:" in content

    @pytest.mark.unit
    def test_bbduk_nf_has_tag_annotations(self) -> None:
        """bbduk.nf must have @TASK and @SPEC TAG annotations."""
        content = BBDUK_NF.read_text()
        assert "@TASK" in content
        assert "@SPEC" in content

    @pytest.mark.unit
    def test_bbduk_nf_has_process_labels(self) -> None:
        """bbduk.nf must have process_medium and process_bbduk labels."""
        content = BBDUK_NF.read_text()
        assert "label 'process_medium'" in content
        assert "label 'process_bbduk'" in content

    @pytest.mark.unit
    def test_bbduk_nf_uses_task_cpus(self) -> None:
        """bbduk.nf must use task.cpus for thread count."""
        content = BBDUK_NF.read_text()
        assert "threads=${task.cpus}" in content

    @pytest.mark.unit
    def test_bbduk_nf_cleans_intermediates(self) -> None:
        """bbduk.nf must clean up intermediate files."""
        content = BBDUK_NF.read_text()
        assert "rm -f" in content
        assert "_clean" in content
        assert "_nophix" in content

    @pytest.mark.unit
    def test_bbduk_nf_combines_stats(self) -> None:
        """bbduk.nf must combine stats from all 3 steps."""
        content = BBDUK_NF.read_text()
        assert "adapter_stats.txt" in content
        assert "phix_stats.txt" in content
        assert "quality_stats.txt" in content
        assert "bbduk_stats.txt" in content


# ---------------------------------------------------------------------------
# Test: Trimmer selection in preprocessing.nf
# ---------------------------------------------------------------------------
class TestTrimmerSelection:
    """Tests for params.trimmer branching in preprocessing and main configs."""

    @pytest.mark.unit
    def test_preprocessing_includes_bbduk(self) -> None:
        """preprocessing.nf must include the BBDUK module."""
        content = PREPROCESSING_NF.read_text()
        assert "include { BBDUK" in content, (
            "preprocessing.nf does not include BBDUK module"
        )

    @pytest.mark.unit
    def test_preprocessing_includes_fastp(self) -> None:
        """preprocessing.nf must still include the FASTP module."""
        content = PREPROCESSING_NF.read_text()
        assert "include { FASTP" in content, (
            "preprocessing.nf does not include FASTP module"
        )

    @pytest.mark.unit
    def test_preprocessing_has_trimmer_branch(self) -> None:
        """preprocessing.nf must branch on params.trimmer."""
        content = PREPROCESSING_NF.read_text()
        assert "params.trimmer" in content, (
            "preprocessing.nf does not reference params.trimmer"
        )

    @pytest.mark.unit
    def test_preprocessing_bbduk_branch(self) -> None:
        """preprocessing.nf must have a bbduk branch."""
        content = PREPROCESSING_NF.read_text()
        assert "params.trimmer == 'bbduk'" in content, (
            "preprocessing.nf missing bbduk branch condition"
        )

    @pytest.mark.unit
    def test_main_nf_has_trimmer_param(self) -> None:
        """main.nf must define params.trimmer with default 'bbduk'."""
        content = MAIN_NF.read_text()
        assert "params.trimmer" in content, (
            "main.nf does not define params.trimmer"
        )

    @pytest.mark.unit
    def test_main_nf_trimmer_default_bbduk(self) -> None:
        """main.nf params.trimmer default must be 'bbduk'."""
        content = MAIN_NF.read_text()
        assert "params.trimmer    = 'bbduk'" in content or \
               "params.trimmer = 'bbduk'" in content, (
            "main.nf params.trimmer default is not 'bbduk'"
        )

    @pytest.mark.unit
    def test_main_nf_trimmer_validation(self) -> None:
        """main.nf must validate params.trimmer values."""
        content = MAIN_NF.read_text()
        assert "'bbduk'" in content and "'fastp'" in content, (
            "main.nf missing trimmer validation values"
        )
        assert "params.trimmer" in content

    @pytest.mark.unit
    def test_main_nf_help_message_includes_trimmer(self) -> None:
        """main.nf help message must mention --trimmer."""
        content = MAIN_NF.read_text()
        assert "--trimmer" in content, (
            "main.nf help message does not mention --trimmer"
        )

    @pytest.mark.unit
    def test_nextflow_config_has_trimmer(self) -> None:
        """nextflow.config must define trimmer = 'bbduk' in params block."""
        content = NEXTFLOW_CONFIG.read_text()
        assert "trimmer" in content, (
            "nextflow.config does not define trimmer param"
        )
        assert "'bbduk'" in content, (
            "nextflow.config trimmer default is not 'bbduk'"
        )


# ---------------------------------------------------------------------------
# Test: Docker config and Dockerfile
# ---------------------------------------------------------------------------
class TestContainerConfig:
    """Tests for BBDuk container configuration."""

    @pytest.mark.unit
    def test_docker_config_has_bbduk_label(self) -> None:
        """docker.config must map process_bbduk label to a container."""
        content = DOCKER_CONFIG.read_text()
        assert "process_bbduk" in content, (
            "docker.config missing process_bbduk label"
        )

    @pytest.mark.unit
    def test_dockerfile_includes_bbmap(self) -> None:
        """QC Dockerfile must install bbmap (includes bbduk.sh)."""
        content = DOCKERFILE_QC.read_text()
        assert "bbmap" in content, (
            "QC Dockerfile does not install bbmap package"
        )
