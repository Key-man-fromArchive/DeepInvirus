#!/usr/bin/env python3
# @TASK T1.4 - BBDuk QC statistics visualization
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/modules/test_fastqc_bbduk_viz.py
"""Visualize BBDuk QC statistics.

Parses BBDuk stats output (3-step: adapter, PhiX, quality) and generates
publication-quality figures:
1. Read count waterfall chart (raw -> adapter -> phix -> quality -> final)
2. Stacked bar: reads kept vs adapter-trimmed vs PhiX-removed vs quality-filtered
3. QC summary table as figure (matplotlib table)

Figure specs: 300 DPI, Arial, 8x6 inches, DEEPINVIRUS_PALETTE.
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
# Parser
# ---------------------------------------------------------------------------
def _parse_int(text: str) -> int:
    """Extract integer from a string, removing whitespace/commas."""
    cleaned = re.sub(r"[,\s]", "", text.strip())
    return int(cleaned)


def _parse_float(text: str) -> float:
    """Extract float from a string like '15.13%'."""
    cleaned = text.strip().rstrip("%")
    return float(cleaned)


def parse_bbduk_stats(stats_path: Path) -> dict[str, Any]:
    """Parse a BBDuk combined stats file (3-step: adapter, phix, quality).

    The file contains three sections separated by headers like:
        'BBDuk adapter-trimming statistics:'
        'BBDuk phix-removal statistics:'
        'BBDuk quality-trimming statistics:'

    Each section has lines like:
        Input:          78354602 reads   11831544902 bases.
        Total Removed:  2089518 reads (2.67%)  857093744 bases (7.24%)
        Result:         76265084 reads (97.33%)  10974451158 bases (92.76%)

    Parameters
    ----------
    stats_path : Path
        Path to the combined BBDuk stats text file.

    Returns
    -------
    dict
        Parsed statistics with keys like:
        - sample: str (derived from filename)
        - adapter_input_reads, adapter_removed_reads, adapter_result_reads
        - phix_input_reads, phix_removed_reads, phix_result_reads
        - quality_input_reads, quality_removed_reads, quality_result_reads
    """
    content = stats_path.read_text()

    # Derive sample name from filename: "GC_Tm.bbduk_stats.txt" -> "GC_Tm"
    sample = stats_path.stem.replace(".bbduk_stats", "")

    result: dict[str, Any] = {"sample": sample}

    # Split into sections by BBDuk header lines
    sections = re.split(r"BBDuk\s+(\w[\w-]*)\s+statistics:", content)
    # sections[0] = empty/preamble, sections[1] = 'adapter-trimming', sections[2] = text, etc.

    step_mapping = {
        "adapter-trimming": "adapter",
        "phix-removal": "phix",
        "quality-trimming": "quality",
    }

    for i in range(1, len(sections), 2):
        header_key = sections[i].strip()
        body = sections[i + 1] if i + 1 < len(sections) else ""
        prefix = step_mapping.get(header_key, header_key)

        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue

            # Parse "Input:" line
            m = re.match(
                r"Input:\s+([\d,]+)\s+reads\s+([\d,]+)\s+bases",
                line,
            )
            if m:
                result[f"{prefix}_input_reads"] = _parse_int(m.group(1))
                result[f"{prefix}_input_bases"] = _parse_int(m.group(2))
                continue

            # Parse "Total Removed:" line
            m = re.match(
                r"Total Removed:\s+([\d,]+)\s+reads\s+\(([\d.]+)%\)\s+([\d,]+)\s+bases\s+\(([\d.]+)%\)",
                line,
            )
            if m:
                result[f"{prefix}_removed_reads"] = _parse_int(m.group(1))
                result[f"{prefix}_removed_pct"] = _parse_float(m.group(2))
                result[f"{prefix}_removed_bases"] = _parse_int(m.group(3))
                continue

            # Parse "Result:" line
            m = re.match(
                r"Result:\s+([\d,]+)\s+reads\s+\(([\d.]+)%\)\s+([\d,]+)\s+bases\s+\(([\d.]+)%\)",
                line,
            )
            if m:
                result[f"{prefix}_result_reads"] = _parse_int(m.group(1))
                result[f"{prefix}_result_pct"] = _parse_float(m.group(2))
                result[f"{prefix}_result_bases"] = _parse_int(m.group(3))
                continue

    return result


# ---------------------------------------------------------------------------
# Visualization functions
# ---------------------------------------------------------------------------
def plot_read_waterfall(
    stats_list: list[dict[str, Any]], output_path: Path
) -> None:
    """Read count waterfall chart across QC steps.

    Shows: Raw -> After Adapter -> After PhiX -> After Quality (Final)
    Each bar shows reads remaining, with reduction amount annotated.
    Grouped by sample (side by side).

    Parameters
    ----------
    stats_list : list[dict]
        List of parsed BBDuk stats dictionaries.
    output_path : Path
        Output PNG file path.
    """
    steps = ["Raw", "After Adapter", "After PhiX", "Final"]
    n_samples = len(stats_list)

    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    bar_width = 0.8 / max(n_samples, 1)
    x = np.arange(len(steps))

    for i, stats in enumerate(stats_list):
        values = [
            stats.get("adapter_input_reads", 0),
            stats.get("adapter_result_reads", 0),
            stats.get("phix_result_reads", 0),
            stats.get("quality_result_reads", 0),
        ]
        offset = (i - n_samples / 2 + 0.5) * bar_width
        bars = ax.bar(
            x + offset,
            values,
            bar_width,
            label=stats.get("sample", f"Sample {i+1}"),
            color=DEEPINVIRUS_PALETTE[i % len(DEEPINVIRUS_PALETTE)],
            edgecolor="white",
            linewidth=0.5,
        )
        # Annotate read counts
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{val/1e6:.1f}M",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.set_xlabel("QC Step")
    ax.set_ylabel("Read Count")
    ax.set_title("BBDuk Read Count Waterfall")
    ax.set_xticks(x)
    ax.set_xticklabels(steps)
    ax.legend(loc="upper right", framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved waterfall chart: %s", output_path)


def plot_base_composition(
    stats_list: list[dict[str, Any]], output_path: Path
) -> None:
    """Stacked bar: reads kept vs adapter-trimmed vs PhiX-removed vs quality-filtered.

    Per sample stacked bars showing breakdown of where reads went.

    Parameters
    ----------
    stats_list : list[dict]
        List of parsed BBDuk stats dictionaries.
    output_path : Path
        Output PNG file path.
    """
    samples = [s.get("sample", f"S{i}") for i, s in enumerate(stats_list)]

    # Breakdown per sample
    adapter_removed = [s.get("adapter_removed_reads", 0) for s in stats_list]
    phix_removed = [s.get("phix_removed_reads", 0) for s in stats_list]
    quality_removed = [s.get("quality_removed_reads", 0) for s in stats_list]
    kept = [s.get("quality_result_reads", 0) for s in stats_list]

    fig, ax = plt.subplots(figsize=DEFAULT_FIGSIZE)
    x = np.arange(len(samples))
    bar_width = 0.6

    # Stacked bars (bottom-up: kept, adapter, phix, quality)
    ax.bar(
        x, kept, bar_width,
        label="Kept", color=DEEPINVIRUS_PALETTE[0],
    )
    ax.bar(
        x, adapter_removed, bar_width, bottom=kept,
        label="Adapter Removed", color=DEEPINVIRUS_PALETTE[1],
    )
    bottom2 = [k + a for k, a in zip(kept, adapter_removed)]
    ax.bar(
        x, phix_removed, bar_width, bottom=bottom2,
        label="PhiX Removed", color=DEEPINVIRUS_PALETTE[3],
    )
    bottom3 = [b + p for b, p in zip(bottom2, phix_removed)]
    ax.bar(
        x, quality_removed, bar_width, bottom=bottom3,
        label="Quality Filtered", color=DEEPINVIRUS_PALETTE[4],
    )

    ax.set_xlabel("Sample")
    ax.set_ylabel("Read Count")
    ax.set_title("BBDuk Read Disposition by Sample")
    ax.set_xticks(x)
    ax.set_xticklabels(samples, rotation=45, ha="right")
    ax.legend(loc="upper right", framealpha=0.9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved composition chart: %s", output_path)


def plot_qc_summary_table(
    stats_list: list[dict[str, Any]], output_path: Path
) -> None:
    """QC summary table as figure (matplotlib table).

    Columns: Sample, Raw Reads, After Adapter, After PhiX, Final, % Kept

    Parameters
    ----------
    stats_list : list[dict]
        List of parsed BBDuk stats dictionaries.
    output_path : Path
        Output PNG file path.
    """
    columns = [
        "Sample", "Raw Reads", "After Adapter",
        "After PhiX", "Final", "% Kept",
    ]

    cell_text = []
    for s in stats_list:
        raw = s.get("adapter_input_reads", 0)
        after_adapter = s.get("adapter_result_reads", 0)
        after_phix = s.get("phix_result_reads", 0)
        final = s.get("quality_result_reads", 0)
        pct_kept = (final / raw * 100) if raw > 0 else 0.0
        cell_text.append([
            s.get("sample", "?"),
            f"{raw:,}",
            f"{after_adapter:,}",
            f"{after_phix:,}",
            f"{final:,}",
            f"{pct_kept:.1f}%",
        ])

    fig, ax = plt.subplots(
        figsize=(max(10, len(columns) * 1.5), max(2, len(stats_list) * 0.6 + 1.5))
    )
    ax.axis("off")
    ax.set_title("BBDuk QC Summary", fontsize=14, fontweight="bold", pad=20)

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
    for j, col in enumerate(columns):
        cell = table[0, j]
        cell.set_facecolor(DEEPINVIRUS_PALETTE[0])
        cell.set_text_props(color="white", fontweight="bold")

    # Alternate row colors
    for i in range(len(stats_list)):
        bg = "#F0F0F0" if i % 2 == 0 else "#FFFFFF"
        for j in range(len(columns)):
            table[i + 1, j].set_facecolor(bg)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved QC summary table: %s", output_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    """CLI entry point for BBDuk stats visualization."""
    parser = argparse.ArgumentParser(
        description="Visualize BBDuk QC statistics from combined stats files.",
    )
    parser.add_argument(
        "--stats",
        nargs="+",
        required=True,
        type=Path,
        help="BBDuk combined stats file(s), e.g. GC_Tm.bbduk_stats.txt",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for output figures",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Parse all stats files
    stats_list = [parse_bbduk_stats(p) for p in args.stats]

    # Generate all figures
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    plot_read_waterfall(stats_list, out / "bbduk_read_waterfall.png")
    plot_base_composition(stats_list, out / "bbduk_base_composition.png")
    plot_qc_summary_table(stats_list, out / "bbduk_qc_summary_table.png")

    logger.info("All figures saved to %s", out)


if __name__ == "__main__":
    main()
