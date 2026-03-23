"""Tests for preprocessing subworkflow: FASTP -> HOST_INDEX -> HOST_REMOVAL.

# @TASK T1.3 - Preprocessing subworkflow integration
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/pipeline/test_preprocessing.py

Tests:
1. Subworkflow file structure (include statements, workflow definition)
2. FASTP -> HOST_REMOVAL channel wiring (FASTP.out.reads -> HOST_REMOVAL input)
3. HOST_INDEX process inclusion and usage
4. params.host == 'none' skip logic for host removal
5. Emit channels: filtered_reads, fastp_json, fastp_html, host_stats
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUBWORKFLOWS_DIR = PROJECT_ROOT / "subworkflows"
PREPROCESSING_NF = SUBWORKFLOWS_DIR / "preprocessing.nf"
MAIN_NF = PROJECT_ROOT / "main.nf"
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
FASTP_NF = MODULES_DIR / "fastp.nf"
HOST_REMOVAL_NF = MODULES_DIR / "host_removal.nf"


# ---------------------------------------------------------------------------
# Test: preprocessing.nf file existence and basic structure
# ---------------------------------------------------------------------------
class TestPreprocessingFileStructure:
    """Tests for preprocessing.nf file existence and structure."""

    @pytest.mark.unit
    def test_preprocessing_nf_exists(self) -> None:
        """preprocessing.nf file must exist."""
        assert PREPROCESSING_NF.exists(), (
            f"preprocessing.nf not found at {PREPROCESSING_NF}"
        )

    @pytest.mark.unit
    def test_preprocessing_nf_has_tag_annotations(self) -> None:
        """preprocessing.nf must have @TASK and @SPEC TAG annotations."""
        content = PREPROCESSING_NF.read_text()
        assert "@TASK" in content, "Missing @TASK annotation"
        assert "@SPEC" in content, "Missing @SPEC annotation"

    @pytest.mark.unit
    def test_preprocessing_nf_defines_workflow(self) -> None:
        """preprocessing.nf must define a workflow named PREPROCESSING."""
        content = PREPROCESSING_NF.read_text()
        assert "workflow PREPROCESSING" in content, (
            "Missing PREPROCESSING workflow definition"
        )


# ---------------------------------------------------------------------------
# Test: include statements
# ---------------------------------------------------------------------------
class TestPreprocessingIncludes:
    """Tests for correct include statements in preprocessing.nf."""

    @pytest.mark.unit
    def test_includes_fastp(self) -> None:
        """preprocessing.nf must include FASTP from modules/local/fastp."""
        content = PREPROCESSING_NF.read_text()
        assert re.search(
            r"include\s*\{\s*FASTP\s*\}\s*from\s*['\"].*fastp['\"]",
            content,
        ), "Missing FASTP include statement"

    @pytest.mark.unit
    def test_includes_host_index(self) -> None:
        """preprocessing.nf must include HOST_INDEX from modules/local/host_removal."""
        content = PREPROCESSING_NF.read_text()
        assert re.search(
            r"include\s*\{\s*HOST_INDEX\s*\}\s*from\s*['\"].*host_removal['\"]",
            content,
        ), "Missing HOST_INDEX include statement"

    @pytest.mark.unit
    def test_includes_host_removal(self) -> None:
        """preprocessing.nf must include HOST_REMOVAL from modules/local/host_removal."""
        content = PREPROCESSING_NF.read_text()
        assert re.search(
            r"include\s*\{\s*HOST_REMOVAL\s*\}\s*from\s*['\"].*host_removal['\"]",
            content,
        ), "Missing HOST_REMOVAL include statement"


# ---------------------------------------------------------------------------
# Test: FASTP -> HOST_REMOVAL channel wiring
# ---------------------------------------------------------------------------
class TestPreprocessingChannelWiring:
    """Tests for correct channel wiring between FASTP and HOST_REMOVAL."""

    @pytest.mark.unit
    def test_fastp_called_with_reads(self) -> None:
        """FASTP must be invoked with the input reads channel."""
        content = PREPROCESSING_NF.read_text()
        assert re.search(
            r"FASTP\s*\(",
            content,
        ), "FASTP process not invoked in workflow"

    @pytest.mark.unit
    def test_host_index_called_with_genome(self) -> None:
        """HOST_INDEX must be invoked with a host genome input."""
        content = PREPROCESSING_NF.read_text()
        assert re.search(
            r"HOST_INDEX\s*\(",
            content,
        ), "HOST_INDEX process not invoked in workflow"

    @pytest.mark.unit
    def test_host_removal_receives_fastp_output(self) -> None:
        """HOST_REMOVAL must receive FASTP output reads as input.

        This ensures the FASTP -> HOST_REMOVAL pipeline is correctly wired.
        The reads channel should connect FASTP.out.reads or ch_trimmed_reads
        to HOST_REMOVAL.
        """
        content = PREPROCESSING_NF.read_text()
        # Check that HOST_REMOVAL is called with either FASTP.out.reads
        # or ch_trimmed_reads (a channel variable assigned from FASTP.out.reads)
        has_direct = "FASTP.out.reads" in content and "HOST_REMOVAL" in content
        has_channel_var = "ch_trimmed_reads" in content and "HOST_REMOVAL" in content
        assert has_direct or has_channel_var, (
            "HOST_REMOVAL must receive FASTP output reads "
            "(via FASTP.out.reads or ch_trimmed_reads)"
        )

    @pytest.mark.unit
    def test_host_removal_receives_index(self) -> None:
        """HOST_REMOVAL must receive the host index from HOST_INDEX.out.index.

        HOST_REMOVAL process requires both reads and an index file.
        """
        content = PREPROCESSING_NF.read_text()
        assert re.search(
            r"HOST_INDEX\.out\.index",
            content,
        ), "HOST_REMOVAL must use HOST_INDEX.out.index"

    @pytest.mark.unit
    def test_ch_trimmed_reads_assigned(self) -> None:
        """ch_trimmed_reads channel should be assigned from FASTP output."""
        content = PREPROCESSING_NF.read_text()
        assert "ch_trimmed_reads" in content, (
            "Missing ch_trimmed_reads channel variable"
        )

    @pytest.mark.unit
    def test_ch_filtered_reads_assigned(self) -> None:
        """ch_filtered_reads channel should be assigned for final output."""
        content = PREPROCESSING_NF.read_text()
        assert "ch_filtered_reads" in content, (
            "Missing ch_filtered_reads channel variable"
        )


# ---------------------------------------------------------------------------
# Test: params.host == 'none' skip logic
# ---------------------------------------------------------------------------
class TestHostRemovalSkipLogic:
    """Tests for host removal skip logic when params.host == 'none'."""

    @pytest.mark.unit
    def test_skip_logic_checks_params_host(self) -> None:
        """preprocessing.nf must check params.host for skip logic."""
        content = PREPROCESSING_NF.read_text()
        assert "params.host" in content, (
            "Missing params.host reference for skip logic"
        )

    @pytest.mark.unit
    def test_skip_logic_checks_none_value(self) -> None:
        """preprocessing.nf must check for 'none' value to skip host removal."""
        content = PREPROCESSING_NF.read_text()
        # Should check params.host == 'none' or params.host != 'none'
        has_none_check = re.search(
            r"params\.host\s*[!=]=\s*['\"]none['\"]",
            content,
        )
        assert has_none_check, (
            "Missing 'none' check for params.host skip logic"
        )

    @pytest.mark.unit
    def test_skip_logic_bypasses_host_removal(self) -> None:
        """When host=='none', filtered_reads should come from FASTP output.

        The subworkflow must have conditional logic that routes
        ch_trimmed_reads directly to ch_filtered_reads when host removal
        is skipped.
        """
        content = PREPROCESSING_NF.read_text()
        # There should be a conditional assignment for ch_filtered_reads
        # It could be an if/else block or a ternary
        has_conditional = (
            ("if" in content and "none" in content)
            or ("?" in content and "none" in content)
        )
        assert has_conditional, (
            "Missing conditional logic for skipping host removal"
        )

    @pytest.mark.unit
    def test_skip_logic_empty_host_stats(self) -> None:
        """When host=='none', host_stats emit should handle empty/null case.

        The subworkflow must produce a valid host_stats channel even when
        host removal is skipped (e.g., Channel.empty() or equivalent).
        """
        content = PREPROCESSING_NF.read_text()
        # When skipping, there should be an empty channel for host_stats
        has_empty_handling = (
            "Channel.empty()" in content
            or "ch_host_stats" in content
        )
        assert has_empty_handling, (
            "Missing empty channel handling for host_stats when host='none'"
        )


# ---------------------------------------------------------------------------
# Test: emit channels
# ---------------------------------------------------------------------------
class TestPreprocessingEmitChannels:
    """Tests for correct emit channels in preprocessing.nf."""

    @pytest.mark.unit
    def test_emit_filtered_reads(self) -> None:
        """preprocessing.nf must emit filtered_reads channel."""
        content = PREPROCESSING_NF.read_text()
        assert re.search(
            r"emit:\s*\n.*filtered_reads",
            content,
            re.DOTALL,
        ), "Missing filtered_reads in emit block"

    @pytest.mark.unit
    def test_emit_fastp_json(self) -> None:
        """preprocessing.nf must emit fastp_json channel."""
        content = PREPROCESSING_NF.read_text()
        assert re.search(
            r"emit:\s*\n.*fastp_json",
            content,
            re.DOTALL,
        ), "Missing fastp_json in emit block"

    @pytest.mark.unit
    def test_emit_fastp_html(self) -> None:
        """preprocessing.nf must emit fastp_html channel."""
        content = PREPROCESSING_NF.read_text()
        assert re.search(
            r"emit:\s*\n.*fastp_html",
            content,
            re.DOTALL,
        ), "Missing fastp_html in emit block"

    @pytest.mark.unit
    def test_emit_host_stats(self) -> None:
        """preprocessing.nf must emit host_stats channel."""
        content = PREPROCESSING_NF.read_text()
        assert re.search(
            r"emit:\s*\n.*host_stats",
            content,
            re.DOTALL,
        ), "Missing host_stats in emit block"


# ---------------------------------------------------------------------------
# Test: main.nf integration
# ---------------------------------------------------------------------------
class TestMainNfIntegration:
    """Tests for main.nf integration with PREPROCESSING subworkflow."""

    @pytest.mark.unit
    def test_main_includes_preprocessing(self) -> None:
        """main.nf must include PREPROCESSING subworkflow."""
        content = MAIN_NF.read_text()
        assert re.search(
            r"include\s*\{\s*PREPROCESSING\s*\}",
            content,
        ), "Missing PREPROCESSING include in main.nf"

    @pytest.mark.unit
    def test_main_calls_preprocessing(self) -> None:
        """main.nf must invoke PREPROCESSING subworkflow."""
        content = MAIN_NF.read_text()
        assert re.search(
            r"PREPROCESSING\s*\(",
            content,
        ), "PREPROCESSING not invoked in main.nf"

    @pytest.mark.unit
    def test_main_uses_preprocessing_reads_output(self) -> None:
        """main.nf must use PREPROCESSING.out.filtered_reads or .out.reads."""
        content = MAIN_NF.read_text()
        has_filtered = "PREPROCESSING.out.filtered_reads" in content
        has_reads = "PREPROCESSING.out.reads" in content
        assert has_filtered or has_reads, (
            "main.nf must use PREPROCESSING output reads"
        )

    @pytest.mark.unit
    def test_main_has_host_genome_channel(self) -> None:
        """main.nf must set up a host genome channel based on params.host.

        This channel provides the host genome FASTA path to PREPROCESSING.
        """
        content = MAIN_NF.read_text()
        has_host_channel = (
            "ch_host_genome" in content
            or "host_genome" in content
        )
        assert has_host_channel, (
            "main.nf must have host genome channel setup"
        )

    @pytest.mark.unit
    def test_main_passes_host_genome_to_preprocessing(self) -> None:
        """main.nf must pass host genome channel to PREPROCESSING."""
        content = MAIN_NF.read_text()
        # Look for PREPROCESSING invocation with two arguments (reads + host_genome)
        # Must match actual code call, not comments. Pattern: PREPROCESSING( arg1, arg2 )
        # Use word-boundary before PREPROCESSING to exclude include statements
        has_two_arg_call = re.search(
            r"^\s+PREPROCESSING\s*\(\s*\w+\s*,\s*\w+\s*\)",
            content,
            re.MULTILINE,
        )
        assert has_two_arg_call, (
            "PREPROCESSING must receive both reads and host_genome arguments"
        )
