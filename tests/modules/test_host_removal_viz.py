# @TASK T1.2 - Host removal statistics visualization tests
# @SPEC docs/planning/02-trd.md#2.2-분석-도구
# @TEST tests/modules/test_host_removal_viz.py
"""Tests for bin/visualize_host_removal.py - host removal statistics visualization.

Covers:
1. Flagstat parsing via the visualization module's parse_flagstat()
2. Host mapping rate bar chart generation
3. Read flow waterfall chart generation
4. Summary table figure generation
5. CLI --help and CLI end-to-end
6. Edge cases (single sample, empty data)
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
VIZ_SCRIPT = BIN_DIR / "visualize_host_removal.py"

# Mock flagstat outputs
FLAGSTAT_GC_TM = textwrap.dedent("""\
    50000000 + 0 in total (QC-passed reads + QC-failed reads)
    25000000 + 0 primary
    0 + 0 secondary
    0 + 0 supplementary
    0 + 0 duplicates
    0 + 0 primary duplicates
    8250000 + 0 mapped (33.00% : N/A)
    8250000 + 0 primary mapped (33.00% : N/A)
    25000000 + 0 paired in sequencing
    12500000 + 0 read1
    12500000 + 0 read2
    7000000 + 0 properly paired (28.00% : N/A)
    8000000 + 0 with itself and mate mapped
    250000 + 0 singletons (1.00% : N/A)
    0 + 0 with mate mapped to a different chr
    0 + 0 with mate mapped to a different chr (mapQ>=5)
""")

FLAGSTAT_INF_NB_TM = textwrap.dedent("""\
    60000000 + 0 in total (QC-passed reads + QC-failed reads)
    30000000 + 0 primary
    0 + 0 secondary
    0 + 0 supplementary
    0 + 0 duplicates
    0 + 0 primary duplicates
    16500000 + 0 mapped (55.00% : N/A)
    16500000 + 0 primary mapped (55.00% : N/A)
    30000000 + 0 paired in sequencing
    15000000 + 0 read1
    15000000 + 0 read2
    14000000 + 0 properly paired (46.67% : N/A)
    15000000 + 0 with itself and mate mapped
    1500000 + 0 singletons (5.00% : N/A)
    0 + 0 with mate mapped to a different chr
    0 + 0 with mate mapped to a different chr (mapQ>=5)
""")

# Mock BBDuk stats for read flow test
MOCK_BBDUK_STATS = textwrap.dedent("""\
    BBDuk adapter-trimming statistics:
    Input:                  	30000000 reads 		4500000000 bases.
    KTrimmed:               	1500000 reads (5.00%) 	225000000 bases (5.00%)
    Total Removed:          	1000000 reads (3.33%) 	150000000 bases (3.33%)
    Result:                 	29000000 reads (96.67%) 	4350000000 bases (96.67%)

    BBDuk phix-removal statistics:
    Input:                  	29000000 reads 		4350000000 bases.
    Contaminants:           	10000 reads (0.03%) 	1500000 bases (0.03%)
    Total Removed:          	10000 reads (0.03%) 	1500000 bases (0.03%)
    Result:                 	28990000 reads (99.97%) 	4348500000 bases (99.97%)

    BBDuk quality-trimming statistics:
    Input:                  	28990000 reads 		4348500000 bases.
    QTrimmed:               	490000 reads (1.69%) 	73500000 bases (1.69%)
    Low quality discards:   	100000 reads (0.34%) 	15000000 bases (0.34%)
    Total Removed:          	590000 reads (2.04%) 	88500000 bases (2.04%)
    Result:                 	28400000 reads (97.96%) 	4260000000 bases (97.96%)
""")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _import_module():
    """Import the visualization module."""
    if str(BIN_DIR) not in sys.path:
        sys.path.insert(0, str(BIN_DIR))


@pytest.fixture
def flagstat_files(tmp_path: Path) -> dict[str, Path]:
    """Create mock flagstat files on disk."""
    gc_path = tmp_path / "GC_Tm.flagstat.txt"
    gc_path.write_text(FLAGSTAT_GC_TM)
    inf_path = tmp_path / "Inf_NB_Tm.flagstat.txt"
    inf_path.write_text(FLAGSTAT_INF_NB_TM)
    return {"GC_Tm": gc_path, "Inf_NB_Tm": inf_path}


@pytest.fixture
def bbduk_files(tmp_path: Path) -> dict[str, Path]:
    """Create mock bbduk stats files on disk."""
    gc_path = tmp_path / "GC_Tm.bbduk_stats.txt"
    gc_path.write_text(MOCK_BBDUK_STATS)
    inf_path = tmp_path / "Inf_NB_Tm.bbduk_stats.txt"
    inf_path.write_text(MOCK_BBDUK_STATS)
    return {"GC_Tm": gc_path, "Inf_NB_Tm": inf_path}


@pytest.fixture
def two_sample_stats() -> list[dict]:
    """Return parsed flagstat stats for two samples."""
    from visualize_host_removal import parse_flagstat
    return [
        {"sample": "GC_Tm", **parse_flagstat(FLAGSTAT_GC_TM)},
        {"sample": "Inf_NB_Tm", **parse_flagstat(FLAGSTAT_INF_NB_TM)},
    ]


# ===========================================================================
# Section 1: Flagstat parsing
# ===========================================================================
class TestParseFlagstat:
    """Tests for flagstat parsing in visualize_host_removal."""

    @pytest.mark.unit
    def test_parse_flagstat_returns_dict(self):
        """parse_flagstat must return a dict with required keys."""
        from visualize_host_removal import parse_flagstat
        result = parse_flagstat(FLAGSTAT_GC_TM)
        assert isinstance(result, dict)
        assert "total" in result
        assert "mapped" in result
        assert "mapped_pct" in result
        assert "unmapped" in result
        assert "unmapped_pct" in result

    @pytest.mark.unit
    def test_parse_flagstat_gc_tm_values(self):
        """GC_Tm: 33% host mapping (dead sample, degraded host RNA)."""
        from visualize_host_removal import parse_flagstat
        result = parse_flagstat(FLAGSTAT_GC_TM)
        assert result["total"] == 25000000  # primary reads
        assert result["mapped"] == 8250000
        assert abs(result["mapped_pct"] - 33.0) < 0.1
        assert result["unmapped"] == 25000000 - 8250000
        assert abs(result["unmapped_pct"] - 67.0) < 0.1

    @pytest.mark.unit
    def test_parse_flagstat_inf_nb_tm_values(self):
        """Inf_NB_Tm: 55% host mapping (living sample, intact host RNA)."""
        from visualize_host_removal import parse_flagstat
        result = parse_flagstat(FLAGSTAT_INF_NB_TM)
        assert result["total"] == 30000000
        assert result["mapped"] == 16500000
        assert abs(result["mapped_pct"] - 55.0) < 0.1

    @pytest.mark.unit
    def test_parse_flagstat_properly_paired(self):
        """parse_flagstat must return properly_paired count and pct."""
        from visualize_host_removal import parse_flagstat
        result = parse_flagstat(FLAGSTAT_GC_TM)
        assert "properly_paired" in result
        assert "properly_paired_pct" in result
        assert result["properly_paired"] == 7000000


# ===========================================================================
# Section 2: Mapping rate bar chart
# ===========================================================================
class TestPlotMappingRateBar:
    """Tests for host mapping rate stacked bar chart."""

    @pytest.mark.unit
    def test_creates_output_file(self, two_sample_stats, tmp_path: Path):
        """plot_mapping_rate_bar must create a PNG file."""
        from visualize_host_removal import plot_mapping_rate_bar
        out = tmp_path / "mapping_rate.png"
        plot_mapping_rate_bar(two_sample_stats, out)
        assert out.exists()
        assert out.stat().st_size > 0

    @pytest.mark.unit
    def test_single_sample(self, tmp_path: Path):
        """plot_mapping_rate_bar must work with a single sample."""
        from visualize_host_removal import parse_flagstat, plot_mapping_rate_bar
        stats = [{"sample": "GC_Tm", **parse_flagstat(FLAGSTAT_GC_TM)}]
        out = tmp_path / "single.png"
        plot_mapping_rate_bar(stats, out)
        assert out.exists()

    @pytest.mark.unit
    def test_empty_stats_no_crash(self, tmp_path: Path):
        """plot_mapping_rate_bar must handle empty list gracefully."""
        from visualize_host_removal import plot_mapping_rate_bar
        out = tmp_path / "empty.png"
        plot_mapping_rate_bar([], out)
        assert out.exists()


# ===========================================================================
# Section 3: Read flow waterfall chart
# ===========================================================================
class TestPlotReadFlow:
    """Tests for read flow waterfall chart (raw -> QC -> host removal)."""

    @pytest.mark.unit
    def test_creates_output_file(self, tmp_path: Path):
        """plot_read_flow must create a PNG file."""
        from visualize_host_removal import plot_read_flow
        bbduk_stats = [
            {"sample": "GC_Tm", "adapter_input_reads": 30000000,
             "quality_result_reads": 28400000},
            {"sample": "Inf_NB_Tm", "adapter_input_reads": 30000000,
             "quality_result_reads": 28400000},
        ]
        host_stats = [
            {"sample": "GC_Tm", "total": 28400000, "mapped": 9372000,
             "unmapped": 19028000},
            {"sample": "Inf_NB_Tm", "total": 28400000, "mapped": 15620000,
             "unmapped": 12780000},
        ]
        out = tmp_path / "read_flow.png"
        plot_read_flow(bbduk_stats, host_stats, out)
        assert out.exists()
        assert out.stat().st_size > 0

    @pytest.mark.unit
    def test_empty_data_no_crash(self, tmp_path: Path):
        """plot_read_flow must handle empty lists gracefully."""
        from visualize_host_removal import plot_read_flow
        out = tmp_path / "empty_flow.png"
        plot_read_flow([], [], out)
        assert out.exists()


# ===========================================================================
# Section 4: Summary table figure
# ===========================================================================
class TestPlotSummaryTable:
    """Tests for host removal summary table as figure."""

    @pytest.mark.unit
    def test_creates_output_file(self, two_sample_stats, tmp_path: Path):
        """plot_summary_table must create a PNG file."""
        from visualize_host_removal import plot_summary_table
        out = tmp_path / "summary_table.png"
        plot_summary_table(two_sample_stats, out)
        assert out.exists()
        assert out.stat().st_size > 0

    @pytest.mark.unit
    def test_empty_stats_no_crash(self, tmp_path: Path):
        """plot_summary_table must handle empty list gracefully."""
        from visualize_host_removal import plot_summary_table
        out = tmp_path / "empty_table.png"
        plot_summary_table([], out)
        assert out.exists()


# ===========================================================================
# Section 5: CLI interface
# ===========================================================================
class TestCli:
    """Tests for visualize_host_removal.py CLI."""

    @pytest.mark.unit
    def test_cli_help(self):
        """CLI --help must run without error."""
        result = subprocess.run(
            [sys.executable, str(VIZ_SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--flagstat" in result.stdout or "usage" in result.stdout.lower()

    @pytest.mark.unit
    def test_cli_generates_figures(
        self, flagstat_files: dict[str, Path], tmp_path: Path
    ):
        """CLI must generate figure files from flagstat inputs."""
        out_dir = tmp_path / "figures"
        result = subprocess.run(
            [
                sys.executable,
                str(VIZ_SCRIPT),
                "--flagstat",
                str(flagstat_files["GC_Tm"]),
                str(flagstat_files["Inf_NB_Tm"]),
                "--output-dir",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert out_dir.exists()
        png_files = list(out_dir.glob("*.png"))
        assert len(png_files) >= 2, (
            f"Expected at least 2 figures, got {len(png_files)}: {png_files}"
        )


# ===========================================================================
# Section 6: Integration with parse_host_removal
# ===========================================================================
class TestIntegrationWithParser:
    """Tests ensuring visualize_host_removal works with parse_host_removal data."""

    @pytest.mark.unit
    def test_parse_flagstat_compatible_with_parser_module(self):
        """Our parse_flagstat output must be usable by calculate_host_removal_stats."""
        from parse_host_removal import calculate_host_removal_stats
        from parse_host_removal import parse_flagstat as parser_parse

        # Both modules should parse the same flagstat text consistently
        parser_result = parser_parse(FLAGSTAT_GC_TM)
        stats = calculate_host_removal_stats("GC_Tm", parser_result)
        assert stats["total_reads"] == 25000000
        assert stats["mapped_reads"] == 8250000
