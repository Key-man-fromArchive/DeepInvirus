# @TASK T6.1 - Virus contig mapping visualization tests
# @SPEC docs/planning/05-design-system.md#6-figure-생성-규격
# @TEST bin/plot_contig_mapping.py
"""Unit tests for bin/plot_contig_mapping.py.

Test strategy (TDD):
  - Mock bigtable DataFrames are used (no real files needed for plot functions).
  - Each of the 4 plot functions is tested for normal output and empty-data handling.
  - CLI --help is tested via subprocess.
  - Output PNG file creation is verified.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).parent.parent.parent / "bin" / "plot_contig_mapping.py"

# Add bin/ to path so we can import directly
sys.path.insert(0, str(SCRIPT.parent))
import plot_contig_mapping as pcm  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_bigtable() -> pd.DataFrame:
    """A minimal bigtable DataFrame with all columns used by the 4 plots."""
    return pd.DataFrame(
        {
            "seq_id": [
                "contig_001", "contig_002", "contig_003",
                "contig_004", "contig_005",
            ],
            "sample": [
                "sample_A", "sample_A", "sample_B",
                "sample_B", "sample_C",
            ],
            "length": [2847, 1500, 1524, 3200, 980],
            "family": [
                "Filoviridae", "Filoviridae", "Asfarviridae",
                "Poxviridae", "Poxviridae",
            ],
            "pident": [95.2, 88.1, 92.5, 97.0, 85.3],
            "coverage": [18.7, 5.2, 12.2, 25.4, 3.1],
        }
    )


@pytest.fixture()
def mock_bigtable_minimal() -> pd.DataFrame:
    """A bigtable with only the required columns (no pident/coverage)."""
    return pd.DataFrame(
        {
            "seq_id": ["contig_001", "contig_002"],
            "sample": ["sample_A", "sample_B"],
            "length": [2847, 1524],
            "family": ["Filoviridae", "Asfarviridae"],
        }
    )


@pytest.fixture()
def empty_bigtable() -> pd.DataFrame:
    """An empty DataFrame with correct column names."""
    return pd.DataFrame(
        columns=["seq_id", "sample", "length", "family", "pident", "coverage"]
    )


@pytest.fixture()
def missing_columns_bigtable() -> pd.DataFrame:
    """A DataFrame missing required columns."""
    return pd.DataFrame({"seq_id": ["contig_001"], "length": [100]})


# ---------------------------------------------------------------------------
# Tests: plot_contig_bubble
# ---------------------------------------------------------------------------


class TestPlotContigBubble:
    """Tests for the bubble plot function."""

    def test_generates_png(self, mock_bigtable: pd.DataFrame, tmp_path: Path) -> None:
        out = tmp_path / "bubble.png"
        result = pcm.plot_contig_bubble(mock_bigtable, out)
        assert result is not None
        assert out.exists()
        assert out.stat().st_size > 0

    def test_empty_dataframe_returns_none(
        self, empty_bigtable: pd.DataFrame, tmp_path: Path
    ) -> None:
        out = tmp_path / "bubble.png"
        result = pcm.plot_contig_bubble(empty_bigtable, out)
        assert result is None
        assert not out.exists()

    def test_missing_columns_returns_none(
        self, missing_columns_bigtable: pd.DataFrame, tmp_path: Path
    ) -> None:
        out = tmp_path / "bubble.png"
        result = pcm.plot_contig_bubble(missing_columns_bigtable, out)
        assert result is None

    def test_without_coverage_column(
        self, mock_bigtable_minimal: pd.DataFrame, tmp_path: Path
    ) -> None:
        out = tmp_path / "bubble.png"
        result = pcm.plot_contig_bubble(mock_bigtable_minimal, out)
        assert result is not None
        assert out.exists()


# ---------------------------------------------------------------------------
# Tests: plot_length_distribution
# ---------------------------------------------------------------------------


class TestPlotLengthDistribution:
    """Tests for the contig length histogram + KDE."""

    def test_generates_png(self, mock_bigtable: pd.DataFrame, tmp_path: Path) -> None:
        out = tmp_path / "length.png"
        result = pcm.plot_length_distribution(mock_bigtable, out)
        assert result is not None
        assert out.exists()
        assert out.stat().st_size > 0

    def test_empty_dataframe_returns_none(
        self, empty_bigtable: pd.DataFrame, tmp_path: Path
    ) -> None:
        out = tmp_path / "length.png"
        result = pcm.plot_length_distribution(empty_bigtable, out)
        assert result is None

    def test_single_contig(self, tmp_path: Path) -> None:
        df = pd.DataFrame(
            {
                "seq_id": ["contig_001"],
                "sample": ["sample_A"],
                "length": [2000],
                "family": ["Filoviridae"],
            }
        )
        out = tmp_path / "length.png"
        result = pcm.plot_length_distribution(df, out)
        assert result is not None
        assert out.exists()


# ---------------------------------------------------------------------------
# Tests: plot_coverage_vs_identity
# ---------------------------------------------------------------------------


class TestPlotCoverageVsIdentity:
    """Tests for the coverage vs identity scatter plot."""

    def test_generates_png(self, mock_bigtable: pd.DataFrame, tmp_path: Path) -> None:
        out = tmp_path / "scatter.png"
        result = pcm.plot_coverage_vs_identity(mock_bigtable, out)
        assert result is not None
        assert out.exists()
        assert out.stat().st_size > 0

    def test_empty_dataframe_returns_none(
        self, empty_bigtable: pd.DataFrame, tmp_path: Path
    ) -> None:
        out = tmp_path / "scatter.png"
        result = pcm.plot_coverage_vs_identity(empty_bigtable, out)
        assert result is None

    def test_missing_pident_column_returns_none(
        self, mock_bigtable_minimal: pd.DataFrame, tmp_path: Path
    ) -> None:
        out = tmp_path / "scatter.png"
        result = pcm.plot_coverage_vs_identity(mock_bigtable_minimal, out)
        assert result is None

    def test_missing_columns_returns_none(
        self, missing_columns_bigtable: pd.DataFrame, tmp_path: Path
    ) -> None:
        out = tmp_path / "scatter.png"
        result = pcm.plot_coverage_vs_identity(missing_columns_bigtable, out)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: plot_family_contig_map
# ---------------------------------------------------------------------------


class TestPlotFamilyContigMap:
    """Tests for the per-family horizontal bar chart."""

    def test_generates_png(self, mock_bigtable: pd.DataFrame, tmp_path: Path) -> None:
        out = tmp_path / "family.png"
        result = pcm.plot_family_contig_map(mock_bigtable, out)
        assert result is not None
        assert out.exists()
        assert out.stat().st_size > 0

    def test_empty_dataframe_returns_none(
        self, empty_bigtable: pd.DataFrame, tmp_path: Path
    ) -> None:
        out = tmp_path / "family.png"
        result = pcm.plot_family_contig_map(empty_bigtable, out)
        assert result is None

    def test_missing_columns_returns_none(
        self, missing_columns_bigtable: pd.DataFrame, tmp_path: Path
    ) -> None:
        out = tmp_path / "family.png"
        result = pcm.plot_family_contig_map(missing_columns_bigtable, out)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: CLI
# ---------------------------------------------------------------------------


class TestCLI:
    """Tests for the command-line interface."""

    def test_help_flag(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--bigtable" in result.stdout
        assert "--output-dir" in result.stdout

    def test_main_with_tsv(self, mock_bigtable: pd.DataFrame, tmp_path: Path) -> None:
        tsv_path = tmp_path / "bigtable.tsv"
        mock_bigtable.to_csv(tsv_path, sep="\t", index=False)
        out_dir = tmp_path / "figures"

        ret = pcm.main(["--bigtable", str(tsv_path), "--output-dir", str(out_dir)])
        assert ret == 0
        assert out_dir.exists()
        # At least some plots should be generated
        pngs = list(out_dir.glob("*.png"))
        assert len(pngs) >= 1

    def test_main_missing_file(self, tmp_path: Path) -> None:
        ret = pcm.main([
            "--bigtable", str(tmp_path / "nonexistent.tsv"),
            "--output-dir", str(tmp_path / "out"),
        ])
        assert ret == 1

    def test_main_with_empty_tsv(self, tmp_path: Path) -> None:
        tsv_path = tmp_path / "empty.tsv"
        pd.DataFrame(
            columns=["seq_id", "sample", "length", "family"]
        ).to_csv(tsv_path, sep="\t", index=False)
        out_dir = tmp_path / "figures"

        ret = pcm.main(["--bigtable", str(tsv_path), "--output-dir", str(out_dir)])
        # Should not crash; returns 0 even if no plots generated
        assert ret == 0


# ---------------------------------------------------------------------------
# Tests: helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    """Tests for internal helper functions."""

    def test_validate_bigtable_empty(self, empty_bigtable: pd.DataFrame) -> None:
        assert pcm._validate_bigtable(empty_bigtable) is not None

    def test_validate_bigtable_missing_cols(
        self, missing_columns_bigtable: pd.DataFrame
    ) -> None:
        err = pcm._validate_bigtable(missing_columns_bigtable)
        assert err is not None
        assert "Missing" in err

    def test_validate_bigtable_ok(self, mock_bigtable: pd.DataFrame) -> None:
        assert pcm._validate_bigtable(mock_bigtable) is None

    def test_get_palette_map(self) -> None:
        mapping = pcm._get_palette_map(["a", "b", "c"])
        assert len(mapping) == 3
        assert all(v.startswith("#") for v in mapping.values())
