#!/usr/bin/env python3
# @TASK T1.2 - Host removal statistics visualization
# @SPEC docs/planning/02-trd.md#2.2-분석-도구
# @TEST tests/modules/test_host_removal_viz.py
"""Visualize host removal statistics from samtools flagstat output.

Generates:
1. Host mapping rate bar chart (per sample)
   - Stacked bar: mapped (host) vs unmapped (non-host)
   - Colours: host=grey, non-host(viral+other)=blue

2. Read flow waterfall chart
   - Raw reads -> After QC -> After host removal -> Final
   - Per sample, side by side

3. Summary table as figure
   - Sample, Total reads, Host mapped(%), Unmapped(%), Host removal rate

Usage::

    python visualize_host_removal.py \\
        --flagstat GC_Tm.flagstat.txt Inf_NB_Tm.flagstat.txt \\
        --output-dir figures/

    # With BBDuk stats for read flow chart:
    python visualize_host_removal.py \\
        --flagstat GC_Tm.flagstat.txt Inf_NB_Tm.flagstat.txt \\
        --bbduk-stats GC_Tm.bbduk_stats.txt Inf_NB_Tm.bbduk_stats.txt \\
        --output-dir figures/
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DeepInvirus design-system constants
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


def _setup_matplotlib() -> None:
    """Apply DeepInvirus figure conventions."""
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
            "figure.dpi": DEFAULT_DPI,
            "figure.figsize": DEFAULT_FIGSIZE,
            "figure.facecolor": "#FFFFFF",
            "savefig.dpi": DEFAULT_DPI,
            "savefig.bbox": "tight",
        }
    )


_setup_matplotlib()


# ---------------------------------------------------------------------------
# Flagstat parser
# ---------------------------------------------------------------------------


def parse_flagstat(flagstat_text: str) -> dict[str, Any]:
    """Parse samtools flagstat output into a statistics dictionary.

    Uses primary reads as the basis for mapping rate calculation.

    Args:
        flagstat_text: Full text of samtools flagstat output.

    Returns:
        Dictionary with keys:
            - total: Primary read count
            - mapped: Primary mapped reads (host reads)
            - mapped_pct: Percentage of primary reads mapped to host
            - unmapped: Primary unmapped reads (non-host)
            - unmapped_pct: Percentage of primary reads unmapped
            - properly_paired: Properly paired read count
            - properly_paired_pct: Properly paired percentage
    """
    raw: dict[str, int] = {
        "total_all": 0,
        "primary": 0,
        "mapped_all": 0,
        "primary_mapped": 0,
        "secondary": 0,
        "supplementary": 0,
        "properly_paired": 0,
    }

    lines = flagstat_text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        match = re.match(r"(\d+)\s+\+\s+\d+", line)
        if not match:
            continue

        count = int(match.group(1))

        if "in total" in line:
            raw["total_all"] = count
        elif "primary mapped" in line:
            raw["primary_mapped"] = count
        elif "primary" in line and "duplicates" not in line:
            raw["primary"] = count
        elif "secondary" in line:
            raw["secondary"] = count
        elif "supplementary" in line:
            raw["supplementary"] = count
        elif "properly paired" in line:
            raw["properly_paired"] = count
        elif (
            "mapped" in line
            and "primary" not in line
            and "mate" not in line
            and "with itself" not in line
        ):
            raw["mapped_all"] = count

    total = raw["primary"]
    mapped = raw["primary_mapped"]
    unmapped = total - mapped

    if total > 0:
        mapped_pct = (mapped / total) * 100.0
        unmapped_pct = (unmapped / total) * 100.0
        pp_pct = (raw["properly_paired"] / total) * 100.0
    else:
        mapped_pct = 0.0
        unmapped_pct = 0.0
        pp_pct = 0.0

    return {
        "total": total,
        "mapped": mapped,
        "mapped_pct": round(mapped_pct, 2),
        "unmapped": unmapped,
        "unmapped_pct": round(unmapped_pct, 2),
        "properly_paired": raw["properly_paired"],
        "properly_paired_pct": round(pp_pct, 2),
    }


# ---------------------------------------------------------------------------
# Visualization functions
# ---------------------------------------------------------------------------


def plot_mapping_rate_bar(
    stats_list: list[dict[str, Any]], output_path: Path
) -> None:
    """Stacked bar chart: host-mapped vs unmapped per sample.

    Parameters
    ----------
    stats_list : list[dict]
        List of dicts with keys: sample, total, mapped, unmapped,
        mapped_pct, unmapped_pct.
    output_path : Path
        Output PNG file path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)

    if not stats_list:
        ax.text(
            0.5, 0.5, "No host removal data available",
            ha="center", va="center", transform=ax.transAxes,
        )
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return

    samples = [s.get("sample", f"S{i}") for i, s in enumerate(stats_list)]
    mapped = [s.get("mapped", 0) for s in stats_list]
    unmapped = [s.get("unmapped", 0) for s in stats_list]

    x = np.arange(len(samples))
    bar_width = 0.6

    # Stacked: unmapped (non-host, blue) on bottom, mapped (host, grey) on top
    ax.bar(
        x, unmapped, bar_width,
        label="Non-host (unmapped)", color=DEEPINVIRUS_PALETTE[0],
    )
    ax.bar(
        x, mapped, bar_width, bottom=unmapped,
        label="Host (mapped)", color=DEEPINVIRUS_PALETTE[6],
    )

    # Annotate percentages
    for i, s in enumerate(stats_list):
        total = s.get("total", 0)
        if total > 0:
            mp = s.get("mapped_pct", 0)
            ax.text(
                x[i], total * 1.02,
                f"{mp:.1f}% host",
                ha="center", va="bottom", fontsize=9, fontweight="bold",
            )

    ax.set_xlabel("Sample")
    ax.set_ylabel("Read Count")
    ax.set_title("Host Mapping Rate by Sample")
    ax.set_xticks(x)
    ax.set_xticklabels(samples, rotation=45, ha="right")
    ax.legend(loc="upper right", framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved mapping rate bar chart: %s", output_path)


def plot_read_flow(
    bbduk_stats: list[dict[str, Any]],
    host_stats: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Waterfall chart: raw -> QC -> host removal per sample.

    Parameters
    ----------
    bbduk_stats : list[dict]
        BBDuk parsed stats (from visualize_bbduk_stats.parse_bbduk_stats).
        Keys used: sample, adapter_input_reads, quality_result_reads.
    host_stats : list[dict]
        Host removal parsed stats. Keys used: sample, total, unmapped.
    output_path : Path
        Output PNG file path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    if not bbduk_stats and not host_stats:
        ax.text(
            0.5, 0.5, "No read flow data available",
            ha="center", va="center", transform=ax.transAxes,
        )
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return

    # Match samples between bbduk and host stats
    bbduk_by_sample = {s.get("sample", ""): s for s in bbduk_stats}
    host_by_sample = {s.get("sample", ""): s for s in host_stats}
    all_samples = list(
        dict.fromkeys(
            [s.get("sample", "") for s in bbduk_stats]
            + [s.get("sample", "") for s in host_stats]
        )
    )

    steps = ["Raw", "After QC", "After Host\nRemoval"]
    n_samples = len(all_samples)
    x = np.arange(len(steps))
    bar_width = 0.8 / max(n_samples, 1)

    for i, sample in enumerate(all_samples):
        bb = bbduk_by_sample.get(sample, {})
        hs = host_by_sample.get(sample, {})

        raw_reads = bb.get("adapter_input_reads", hs.get("total", 0))
        after_qc = bb.get("quality_result_reads", hs.get("total", 0))
        after_host = hs.get("unmapped", 0)

        values = [raw_reads, after_qc, after_host]
        offset = (i - n_samples / 2 + 0.5) * bar_width

        bars = ax.bar(
            x + offset, values, bar_width,
            label=sample,
            color=DEEPINVIRUS_PALETTE[i % len(DEEPINVIRUS_PALETTE)],
            edgecolor="white", linewidth=0.5,
        )

        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{val / 1e6:.1f}M",
                    ha="center", va="bottom", fontsize=8,
                )

    ax.set_xlabel("Processing Stage")
    ax.set_ylabel("Read Count")
    ax.set_title("Read Flow: Raw -> QC -> Host Removal")
    ax.set_xticks(x)
    ax.set_xticklabels(steps)
    ax.legend(loc="upper right", framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved read flow chart: %s", output_path)


def plot_summary_table(
    stats_list: list[dict[str, Any]], output_path: Path
) -> None:
    """Host removal summary table rendered as a matplotlib figure.

    Columns: Sample, Total Reads, Host Mapped, Host Mapped %, Unmapped,
             Unmapped %

    Parameters
    ----------
    stats_list : list[dict]
        List of dicts from parse_flagstat (with 'sample' key added).
    output_path : Path
        Output PNG file path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    columns = [
        "Sample", "Total Reads", "Host Mapped",
        "Mapped %", "Unmapped", "Unmapped %",
    ]

    cell_text = []
    for s in stats_list:
        cell_text.append([
            s.get("sample", "?"),
            f"{s.get('total', 0):,}",
            f"{s.get('mapped', 0):,}",
            f"{s.get('mapped_pct', 0):.1f}%",
            f"{s.get('unmapped', 0):,}",
            f"{s.get('unmapped_pct', 0):.1f}%",
        ])

    fig, ax = plt.subplots(
        figsize=(max(10, len(columns) * 1.5),
                 max(2, len(stats_list) * 0.6 + 1.5))
    )
    ax.axis("off")
    ax.set_title(
        "Host Removal Summary", fontsize=14, fontweight="bold", pad=20
    )

    if not cell_text:
        ax.text(
            0.5, 0.5, "No host removal data available",
            ha="center", va="center", transform=ax.transAxes,
        )
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return

    table = ax.table(
        cellText=cell_text,
        colLabels=columns,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.5)

    # Style header row
    for j in range(len(columns)):
        cell = table[0, j]
        cell.set_facecolor(DEEPINVIRUS_PALETTE[0])
        cell.set_text_props(color="white", fontweight="bold")

    # Alternate row colours
    for i in range(len(stats_list)):
        bg = "#F0F0F0" if i % 2 == 0 else "#FFFFFF"
        for j in range(len(columns)):
            table[i + 1, j].set_facecolor(bg)

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved summary table: %s", output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for host removal statistics visualization."""
    parser = argparse.ArgumentParser(
        description=(
            "Visualize host removal statistics from samtools flagstat output."
        ),
    )
    parser.add_argument(
        "--flagstat",
        nargs="+",
        required=True,
        type=Path,
        help="Samtools flagstat output file(s), e.g. GC_Tm.flagstat.txt",
    )
    parser.add_argument(
        "--bbduk-stats",
        nargs="*",
        type=Path,
        default=None,
        help="BBDuk combined stats file(s) for read flow chart (optional)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for output figures",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s: %(message)s"
    )

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    # Parse flagstat files
    host_stats_list: list[dict[str, Any]] = []
    for fpath in args.flagstat:
        text = fpath.read_text()
        stats = parse_flagstat(text)
        # Derive sample name from filename
        sample = fpath.stem.replace(".flagstat", "")
        stats["sample"] = sample
        host_stats_list.append(stats)

    # Generate mapping rate bar chart
    plot_mapping_rate_bar(host_stats_list, out / "host_mapping_rate.png")

    # Generate summary table
    plot_summary_table(host_stats_list, out / "host_removal_summary_table.png")

    # Generate read flow chart if bbduk stats provided
    if args.bbduk_stats:
        # Import bbduk parser
        _bin_dir = Path(__file__).resolve().parent
        if str(_bin_dir) not in sys.path:
            sys.path.insert(0, str(_bin_dir))
        from visualize_bbduk_stats import parse_bbduk_stats

        bbduk_stats_list = [parse_bbduk_stats(p) for p in args.bbduk_stats]
        plot_read_flow(
            bbduk_stats_list, host_stats_list,
            out / "host_read_flow.png",
        )

    logger.info("All host removal figures saved to %s", out)


if __name__ == "__main__":
    main()
