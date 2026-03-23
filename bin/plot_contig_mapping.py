#!/usr/bin/env python3
# @TASK T6.1 - Virus contig mapping visualization
# @SPEC docs/planning/05-design-system.md#6-figure-생성-규격
# @SPEC docs/planning/05-design-system.md#3-컬러-팔레트
# @TEST tests/modules/test_contig_mapping.py
"""Virus contig mapping visualization.

Generates 4 figures showing how viral contigs map to reference genomes:
  1. contig_mapping_overview.png  -- bubble plot (sample x family)
  2. contig_length_distribution.png -- histogram + KDE of contig lengths
  3. coverage_vs_identity.png -- scatter (pident vs coverage)
  4. per_family_contig_map.png -- horizontal bars per family
"""

from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path
from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns

# ---------------------------------------------------------------------------
# Design-system constants (from 05-design-system.md)
# ---------------------------------------------------------------------------

DEEPINVIRUS_PALETTE: list[str] = [
    "#1F77B4",  # Deep Blue
    "#FF7F0E",  # Orange
    "#2CA02C",  # Green
    "#D62728",  # Red
    "#9467BD",  # Purple
    "#8C564B",  # Brown
    "#7F7F7F",  # Gray
]

DEFAULT_DPI = 300
DEFAULT_FIGSIZE = (8, 6)
DEFAULT_BG = "#FFFFFF"

REQUIRED_COLUMNS = {"seq_id", "sample", "length", "family"}

logger = logging.getLogger(__name__)


def setup_matplotlib() -> None:
    """Apply DeepInvirus figure conventions to matplotlib rcParams."""
    matplotlib.use("Agg")
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Helvetica"],
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "figure.figsize": DEFAULT_FIGSIZE,
            "figure.dpi": DEFAULT_DPI,
            "savefig.dpi": DEFAULT_DPI,
            "savefig.bbox": "tight",
            "savefig.facecolor": DEFAULT_BG,
            "figure.facecolor": DEFAULT_BG,
            "axes.facecolor": DEFAULT_BG,
            "axes.edgecolor": "#333333",
            "axes.grid": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _validate_bigtable(bigtable: pd.DataFrame) -> Optional[str]:
    """Return an error message if bigtable is unusable, else None."""
    if bigtable.empty:
        return "bigtable is empty"
    missing = REQUIRED_COLUMNS - set(bigtable.columns)
    if missing:
        return f"Missing required columns: {sorted(missing)}"
    return None


def _get_palette_map(labels: list[str]) -> dict[str, str]:
    """Map unique labels to palette colours (cycling if needed)."""
    unique = sorted(set(labels))
    n = len(DEEPINVIRUS_PALETTE)
    return {label: DEEPINVIRUS_PALETTE[i % n] for i, label in enumerate(unique)}


# ---------------------------------------------------------------------------
# @TASK T6.1.1 - Bubble plot: sample x family
# ---------------------------------------------------------------------------


def plot_contig_bubble(bigtable: pd.DataFrame, output_path: Path) -> Optional[Path]:
    """Sample x Family bubble plot.

    X-axis: sample, Y-axis: family.
    Bubble size: number of contigs.
    Bubble colour: mean coverage (if available) or mean length.

    Args:
        bigtable: DataFrame with at least seq_id, sample, length, family columns.
        output_path: Path for the output PNG file.

    Returns:
        The output path on success, or None if skipped.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    err = _validate_bigtable(bigtable)
    if err:
        logger.warning("Skipping contig bubble plot: %s", err)
        return None

    has_coverage = "coverage" in bigtable.columns

    # Aggregate: count contigs and mean coverage per (sample, family)
    agg_dict: dict[str, tuple[str, str]] = {"seq_id": ("seq_id", "count")}
    if has_coverage:
        agg_dict["mean_coverage"] = ("coverage", "mean")
    else:
        agg_dict["mean_length"] = ("length", "mean")

    grouped = bigtable.groupby(["sample", "family"], as_index=False).agg(
        num_contigs=("seq_id", "count"),
        colour_val=(("coverage" if has_coverage else "length"), "mean"),
    )

    fig, ax = plt.subplots(figsize=(8, 6))

    samples = sorted(grouped["sample"].unique())
    families = sorted(grouped["family"].unique())
    sample_map = {s: i for i, s in enumerate(samples)}
    family_map = {f: i for i, f in enumerate(families)}

    x = grouped["sample"].map(sample_map)
    y = grouped["family"].map(family_map)
    sizes = grouped["num_contigs"]
    colours = grouped["colour_val"]

    # Scale bubble sizes for visibility
    max_size = sizes.max() if sizes.max() > 0 else 1
    scaled = (sizes / max_size) * 400 + 50

    sc = ax.scatter(
        x, y, s=scaled, c=colours, cmap="YlOrRd", alpha=0.75,
        edgecolors="#333333", linewidths=0.5,
    )
    cbar = fig.colorbar(sc, ax=ax, shrink=0.7)
    cbar.set_label("Mean Coverage" if has_coverage else "Mean Length (bp)")

    ax.set_xticks(range(len(samples)))
    ax.set_xticklabels(samples, rotation=45, ha="right")
    ax.set_yticks(range(len(families)))
    ax.set_yticklabels(families)
    ax.set_xlabel("Sample")
    ax.set_ylabel("Virus Family")
    ax.set_title("Contig Mapping Overview")

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Bubble plot saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# @TASK T6.1.2 - Contig length distribution
# ---------------------------------------------------------------------------


def plot_length_distribution(bigtable: pd.DataFrame, output_path: Path) -> Optional[Path]:
    """Histogram + KDE of contig lengths, coloured by sample.

    Args:
        bigtable: DataFrame with at least seq_id, sample, length, family columns.
        output_path: Path for the output PNG file.

    Returns:
        The output path on success, or None if skipped.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    err = _validate_bigtable(bigtable)
    if err:
        logger.warning("Skipping length distribution plot: %s", err)
        return None

    fig, ax = plt.subplots(figsize=(8, 6))

    samples = sorted(bigtable["sample"].unique())
    palette_map = _get_palette_map(samples)

    for sample in samples:
        subset = bigtable[bigtable["sample"] == sample]["length"].dropna()
        if subset.empty:
            continue
        subset = subset.astype(float)
        ax.hist(
            subset, bins=30, alpha=0.5, label=sample,
            color=palette_map[sample], edgecolor="white",
        )
        # KDE overlay (only if >1 unique value)
        if subset.nunique() > 1 and len(subset) > 1:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    sns.kdeplot(subset, ax=ax, color=palette_map[sample], linewidth=1.5)
            except Exception:
                pass  # graceful skip

    ax.set_xlabel("Contig Length (bp)")
    ax.set_ylabel("Count")
    ax.set_title("Contig Length Distribution")
    if samples:
        ax.legend(title="Sample")

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Length distribution plot saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# @TASK T6.1.3 - Coverage vs Identity scatter
# ---------------------------------------------------------------------------


def plot_coverage_vs_identity(bigtable: pd.DataFrame, output_path: Path) -> Optional[Path]:
    """Scatter plot: x=pident, y=coverage, colour=sample, size=length.

    If pident or coverage columns are missing, the plot is skipped with a warning.

    Args:
        bigtable: DataFrame with seq_id, sample, length, family and optionally
            pident, coverage columns.
        output_path: Path for the output PNG file.

    Returns:
        The output path on success, or None if skipped.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    err = _validate_bigtable(bigtable)
    if err:
        logger.warning("Skipping coverage vs identity plot: %s", err)
        return None

    if "pident" not in bigtable.columns or "coverage" not in bigtable.columns:
        logger.warning(
            "Skipping coverage vs identity plot: pident and/or coverage column missing"
        )
        return None

    df = bigtable.dropna(subset=["pident", "coverage"]).copy()
    if df.empty:
        logger.warning("Skipping coverage vs identity plot: no valid data after dropna")
        return None

    df["pident"] = pd.to_numeric(df["pident"], errors="coerce")
    df["coverage"] = pd.to_numeric(df["coverage"], errors="coerce")
    df["length"] = pd.to_numeric(df["length"], errors="coerce")
    df = df.dropna(subset=["pident", "coverage", "length"])

    if df.empty:
        logger.warning("Skipping coverage vs identity plot: no numeric data")
        return None

    fig, ax = plt.subplots(figsize=(8, 6))

    samples = sorted(df["sample"].unique())
    palette_map = _get_palette_map(samples)

    # Scale point sizes
    max_len = df["length"].max() if df["length"].max() > 0 else 1
    sizes = (df["length"] / max_len) * 200 + 20

    for sample in samples:
        mask = df["sample"] == sample
        ax.scatter(
            df.loc[mask, "pident"],
            df.loc[mask, "coverage"],
            s=sizes[mask],
            c=palette_map[sample],
            label=sample,
            alpha=0.7,
            edgecolors="#333333",
            linewidths=0.3,
        )

    ax.set_xlabel("Sequence Identity (%)")
    ax.set_ylabel("Coverage Depth")
    ax.set_title("Coverage vs Sequence Identity")
    ax.legend(title="Sample")

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Coverage vs identity plot saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# @TASK T6.1.4 - Per-family contig map (horizontal bar chart)
# ---------------------------------------------------------------------------


def plot_family_contig_map(bigtable: pd.DataFrame, output_path: Path) -> Optional[Path]:
    """Horizontal bars: each contig coloured by sample, grouped by family.

    Args:
        bigtable: DataFrame with seq_id, sample, length, family columns.
        output_path: Path for the output PNG file.

    Returns:
        The output path on success, or None if skipped.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    err = _validate_bigtable(bigtable)
    if err:
        logger.warning("Skipping family contig map: %s", err)
        return None

    df = bigtable[["seq_id", "sample", "length", "family"]].dropna().copy()
    df["length"] = pd.to_numeric(df["length"], errors="coerce")
    df = df.dropna(subset=["length"])

    if df.empty:
        logger.warning("Skipping family contig map: no valid data")
        return None

    families = sorted(df["family"].unique())
    samples = sorted(df["sample"].unique())
    palette_map = _get_palette_map(samples)

    # Build y-positions: contigs grouped by family
    y_labels: list[str] = []
    y_positions: list[float] = []
    bar_widths: list[float] = []
    bar_colours: list[str] = []
    current_y = 0

    for fam in families:
        fam_df = df[df["family"] == fam].sort_values("length", ascending=False)
        for _, row in fam_df.iterrows():
            y_labels.append(f"{row['seq_id']}")
            y_positions.append(current_y)
            bar_widths.append(float(row["length"]))
            bar_colours.append(palette_map.get(row["sample"], "#7F7F7F"))
            current_y += 1
        current_y += 0.5  # gap between families

    n_bars = len(y_positions)
    fig_height = max(4, n_bars * 0.35 + 2)
    fig, ax = plt.subplots(figsize=(10, fig_height))

    ax.barh(y_positions, bar_widths, color=bar_colours, edgecolor="white", height=0.8)

    ax.set_yticks(y_positions)
    ax.set_yticklabels(y_labels, fontsize=8)
    ax.set_xlabel("Contig Length (bp)")
    ax.set_title("Per-Family Contig Map")
    ax.invert_yaxis()

    # Add family group labels on the right
    # Create legend for samples
    handles = [
        mpatches.Patch(color=palette_map[s], label=s)
        for s in samples
    ]
    ax.legend(handles=handles, title="Sample", loc="lower right", fontsize=8)

    # Add family divider annotations
    y_idx = 0
    for fam in families:
        fam_count = len(df[df["family"] == fam])
        if fam_count > 0:
            mid_y = y_positions[y_idx] + (fam_count - 1) / 2
            ax.annotate(
                fam, xy=(1.02, mid_y), xycoords=("axes fraction", "data"),
                fontsize=8, fontweight="bold", va="center",
                annotation_clip=False,
            )
            y_idx += fam_count

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Family contig map saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate virus contig mapping visualizations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python plot_contig_mapping.py --bigtable bigtable.tsv --output-dir figures/\n"
        ),
    )
    parser.add_argument(
        "--bigtable", required=True, type=Path,
        help="Path to bigtable.tsv (tab-separated, with seq_id/sample/length/family columns)",
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path,
        help="Output directory for PNG figures",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point.

    Returns:
        0 on success, 1 on error.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    bigtable_path: Path = args.bigtable
    output_dir: Path = args.output_dir

    if not bigtable_path.exists():
        logger.error("bigtable file not found: %s", bigtable_path)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        bigtable = pd.read_csv(bigtable_path, sep="\t")
    except Exception as exc:
        logger.error("Failed to read bigtable: %s", exc)
        return 1

    # Generate all 4 plots, skipping gracefully on errors
    plots = [
        ("contig_mapping_overview.png", plot_contig_bubble),
        ("contig_length_distribution.png", plot_length_distribution),
        ("coverage_vs_identity.png", plot_coverage_vs_identity),
        ("per_family_contig_map.png", plot_family_contig_map),
    ]

    generated = 0
    for filename, plot_func in plots:
        try:
            result = plot_func(bigtable, output_dir / filename)
            if result is not None:
                generated += 1
        except Exception as exc:
            logger.warning("Failed to generate %s: %s", filename, exc)

    logger.info("Generated %d / %d plots in %s", generated, len(plots), output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
