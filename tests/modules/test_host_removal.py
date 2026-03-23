"""Tests for host removal module: parse_host_removal.py and output validation.

# @TASK T1.2 - Host read removal using minimap2 + samtools
# @SPEC docs/planning/02-trd.md#2.2-분석-도구
# @TEST tests/modules/test_host_removal.py

Tests:
1. samtools flagstat output parsing
2. Host removal statistics calculation (total, mapped, unmapped, removal rate)
3. TSV output format validation
4. Edge cases (zero reads, 100% host, 0% host)
"""

from __future__ import annotations

import csv
import io
import textwrap
from pathlib import Path

import pytest

# We import the module under test; it will be created in bin/
import sys

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "bin"),
)

from parse_host_removal import (
    parse_flagstat,
    calculate_host_removal_stats,
    format_stats_tsv,
)


# ---------------------------------------------------------------------------
# Fixtures: mock samtools flagstat output
# ---------------------------------------------------------------------------

FLAGSTAT_NORMAL = textwrap.dedent("""\
    2000000 + 0 in total (QC-passed reads + QC-failed reads)
    1000000 + 0 primary
    0 + 0 secondary
    0 + 0 supplementary
    0 + 0 duplicates
    0 + 0 primary duplicates
    600000 + 0 mapped (60.00% : N/A)
    600000 + 0 primary mapped (60.00% : N/A)
    1000000 + 0 paired in sequencing
    500000 + 0 read1
    500000 + 0 read2
    400000 + 0 properly paired (40.00% : N/A)
    500000 + 0 with itself and mate mapped
    100000 + 0 singletons (10.00% : N/A)
    0 + 0 with mate mapped to a different chr
    0 + 0 with mate mapped to a different chr (mapQ>=5)
""")

FLAGSTAT_ALL_HOST = textwrap.dedent("""\
    2000000 + 0 in total (QC-passed reads + QC-failed reads)
    1000000 + 0 primary
    0 + 0 secondary
    0 + 0 supplementary
    0 + 0 duplicates
    0 + 0 primary duplicates
    1000000 + 0 mapped (100.00% : N/A)
    1000000 + 0 primary mapped (100.00% : N/A)
    1000000 + 0 paired in sequencing
    500000 + 0 read1
    500000 + 0 read2
    1000000 + 0 properly paired (100.00% : N/A)
    1000000 + 0 with itself and mate mapped
    0 + 0 singletons (0.00% : N/A)
    0 + 0 with mate mapped to a different chr
    0 + 0 with mate mapped to a different chr (mapQ>=5)
""")

FLAGSTAT_NO_HOST = textwrap.dedent("""\
    2000000 + 0 in total (QC-passed reads + QC-failed reads)
    1000000 + 0 primary
    0 + 0 secondary
    0 + 0 supplementary
    0 + 0 duplicates
    0 + 0 primary duplicates
    0 + 0 mapped (0.00% : N/A)
    0 + 0 primary mapped (0.00% : N/A)
    1000000 + 0 paired in sequencing
    500000 + 0 read1
    500000 + 0 read2
    0 + 0 properly paired (0.00% : N/A)
    0 + 0 with itself and mate mapped
    0 + 0 singletons (0.00% : N/A)
    0 + 0 with mate mapped to a different chr
    0 + 0 with mate mapped to a different chr (mapQ>=5)
""")

FLAGSTAT_ZERO_READS = textwrap.dedent("""\
    0 + 0 in total (QC-passed reads + QC-failed reads)
    0 + 0 primary
    0 + 0 secondary
    0 + 0 supplementary
    0 + 0 duplicates
    0 + 0 primary duplicates
    0 + 0 mapped (N/A : N/A)
    0 + 0 primary mapped (N/A : N/A)
    0 + 0 paired in sequencing
    0 + 0 read1
    0 + 0 read2
    0 + 0 properly paired (N/A : N/A)
    0 + 0 with itself and mate mapped
    0 + 0 singletons (N/A : N/A)
    0 + 0 with mate mapped to a different chr
    0 + 0 with mate mapped to a different chr (mapQ>=5)
""")


# ---------------------------------------------------------------------------
# Tests: parse_flagstat
# ---------------------------------------------------------------------------

class TestParseFlagstat:
    """Test suite for samtools flagstat output parsing."""

    @pytest.mark.unit
    def test_parse_normal_flagstat(self):
        """Parse a typical flagstat output with partial host mapping.

        Expected: total=2000000, primary=1000000, mapped=600000,
                  primary_mapped=600000.
        """
        result = parse_flagstat(FLAGSTAT_NORMAL)
        assert result["total"] == 2000000
        assert result["primary"] == 1000000
        assert result["mapped"] == 600000
        assert result["primary_mapped"] == 600000

    @pytest.mark.unit
    def test_parse_all_host_flagstat(self):
        """Parse flagstat where 100% of reads map to host."""
        result = parse_flagstat(FLAGSTAT_ALL_HOST)
        assert result["total"] == 2000000
        assert result["primary"] == 1000000
        assert result["mapped"] == 1000000
        assert result["primary_mapped"] == 1000000

    @pytest.mark.unit
    def test_parse_no_host_flagstat(self):
        """Parse flagstat where 0% of reads map to host."""
        result = parse_flagstat(FLAGSTAT_NO_HOST)
        assert result["total"] == 2000000
        assert result["primary"] == 1000000
        assert result["mapped"] == 0
        assert result["primary_mapped"] == 0

    @pytest.mark.unit
    def test_parse_zero_reads_flagstat(self):
        """Parse flagstat from an empty BAM (zero reads)."""
        result = parse_flagstat(FLAGSTAT_ZERO_READS)
        assert result["total"] == 0
        assert result["primary"] == 0
        assert result["mapped"] == 0
        assert result["primary_mapped"] == 0


# ---------------------------------------------------------------------------
# Tests: calculate_host_removal_stats
# ---------------------------------------------------------------------------

class TestCalculateHostRemovalStats:
    """Test suite for host removal statistics calculation."""

    @pytest.mark.unit
    def test_normal_stats(self):
        """Calculate stats for a normal case with partial host removal.

        Using primary reads: primary=1000000, primary_mapped=600000
        Expected: unmapped=400000, removal_rate=60.0%
        """
        flagstat = parse_flagstat(FLAGSTAT_NORMAL)
        stats = calculate_host_removal_stats("sample1", flagstat)

        assert stats["sample"] == "sample1"
        assert stats["total_reads"] == 1000000  # primary reads
        assert stats["mapped_reads"] == 600000   # host reads (primary mapped)
        assert stats["unmapped_reads"] == 400000  # non-host reads
        assert abs(stats["host_removal_rate"] - 60.0) < 0.01

    @pytest.mark.unit
    def test_all_host_stats(self):
        """Calculate stats when all reads are host (100% removal rate)."""
        flagstat = parse_flagstat(FLAGSTAT_ALL_HOST)
        stats = calculate_host_removal_stats("sample_all_host", flagstat)

        assert stats["sample"] == "sample_all_host"
        assert stats["total_reads"] == 1000000
        assert stats["mapped_reads"] == 1000000
        assert stats["unmapped_reads"] == 0
        assert abs(stats["host_removal_rate"] - 100.0) < 0.01

    @pytest.mark.unit
    def test_no_host_stats(self):
        """Calculate stats when no reads map to host (0% removal rate)."""
        flagstat = parse_flagstat(FLAGSTAT_NO_HOST)
        stats = calculate_host_removal_stats("sample_no_host", flagstat)

        assert stats["total_reads"] == 1000000
        assert stats["mapped_reads"] == 0
        assert stats["unmapped_reads"] == 1000000
        assert abs(stats["host_removal_rate"] - 0.0) < 0.01

    @pytest.mark.unit
    def test_zero_reads_stats(self):
        """Calculate stats for zero-read input (edge case, no division by zero)."""
        flagstat = parse_flagstat(FLAGSTAT_ZERO_READS)
        stats = calculate_host_removal_stats("sample_empty", flagstat)

        assert stats["total_reads"] == 0
        assert stats["mapped_reads"] == 0
        assert stats["unmapped_reads"] == 0
        assert stats["host_removal_rate"] == 0.0


# ---------------------------------------------------------------------------
# Tests: format_stats_tsv
# ---------------------------------------------------------------------------

class TestFormatStatsTsv:
    """Test suite for TSV output formatting."""

    @pytest.mark.unit
    def test_tsv_output_columns(self):
        """Verify TSV output has the correct header columns."""
        flagstat = parse_flagstat(FLAGSTAT_NORMAL)
        stats = calculate_host_removal_stats("sample1", flagstat)
        tsv_output = format_stats_tsv([stats])

        reader = csv.DictReader(io.StringIO(tsv_output), delimiter="\t")
        assert reader.fieldnames == [
            "sample",
            "total_reads",
            "mapped_reads",
            "unmapped_reads",
            "host_removal_rate",
        ]

    @pytest.mark.unit
    def test_tsv_output_values(self):
        """Verify TSV output contains correct values."""
        flagstat = parse_flagstat(FLAGSTAT_NORMAL)
        stats = calculate_host_removal_stats("sample1", flagstat)
        tsv_output = format_stats_tsv([stats])

        reader = csv.DictReader(io.StringIO(tsv_output), delimiter="\t")
        rows = list(reader)
        assert len(rows) == 1

        row = rows[0]
        assert row["sample"] == "sample1"
        assert row["total_reads"] == "1000000"
        assert row["mapped_reads"] == "600000"
        assert row["unmapped_reads"] == "400000"
        assert row["host_removal_rate"] == "60.00"

    @pytest.mark.unit
    def test_tsv_multiple_samples(self):
        """Verify TSV output handles multiple samples correctly."""
        stats_list = []
        for name, flagstat_text in [
            ("s1", FLAGSTAT_NORMAL),
            ("s2", FLAGSTAT_NO_HOST),
        ]:
            flagstat = parse_flagstat(flagstat_text)
            stats_list.append(calculate_host_removal_stats(name, flagstat))

        tsv_output = format_stats_tsv(stats_list)
        reader = csv.DictReader(io.StringIO(tsv_output), delimiter="\t")
        rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["sample"] == "s1"
        assert rows[1]["sample"] == "s2"


# ---------------------------------------------------------------------------
# Tests: file-based integration (write/read TSV)
# ---------------------------------------------------------------------------

class TestFileIntegration:
    """Test reading/writing stats files on disk."""

    @pytest.mark.unit
    def test_write_and_read_tsv(self, tmp_dir: Path):
        """Write stats TSV to disk and read it back."""
        flagstat = parse_flagstat(FLAGSTAT_NORMAL)
        stats = calculate_host_removal_stats("sample1", flagstat)
        tsv_output = format_stats_tsv([stats])

        out_path = tmp_dir / "host_removal_stats.tsv"
        out_path.write_text(tsv_output)

        # Read back and verify
        content = out_path.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2  # header + 1 data row
        assert lines[0].startswith("sample\t")

    @pytest.mark.unit
    def test_parse_flagstat_from_file(self, tmp_dir: Path):
        """Parse flagstat content read from a file."""
        flagstat_path = tmp_dir / "flagstat.txt"
        flagstat_path.write_text(FLAGSTAT_NORMAL)

        content = flagstat_path.read_text()
        result = parse_flagstat(content)
        assert result["total"] == 2000000
