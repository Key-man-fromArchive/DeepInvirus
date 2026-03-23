#!/usr/bin/env python3
# @TASK T5.2 - Automated Word report generation
# @SPEC docs/planning/05-design-system.md#5-word-보고서-템플릿
# @TEST tests/modules/test_report.py
"""Generate a Word (.docx) analysis report for DeepInvirus.

Reads pipeline output files (bigtable, sample-taxon matrix, diversity
tables, QC/assembly stats) and produces a formatted Word document
following the structure defined in 05-design-system.md section 5.1.

Report structure:
    1. 분석 개요
    2. 품질 관리 (QC) 결과
    3. 바이러스 탐지 결과
    4. 분류학적 분석
    5. 다양성 분석
    6. 결론 및 해석
    부록

Usage::

    python generate_report.py \\
        --bigtable bigtable.tsv \\
        --matrix sample_taxon_matrix.tsv \\
        --alpha alpha_diversity.tsv \\
        --pcoa pcoa_coordinates.tsv \\
        --qc-stats qc_stats.tsv \\
        --assembly-stats assembly_stats.tsv \\
        --output report.docx \\
        --figures-dir figures/
"""

from __future__ import annotations

import argparse
import logging
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Ensure bin/ is on the path so utils is importable
_BIN_DIR = Path(__file__).resolve().parent
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))

from utils.docx_builder import ReportBuilder
from utils.visualization import (
    DEEPINVIRUS_PALETTE,
    DEFAULT_DPI,
    HEATMAP_CMAP,
    plot_alpha_diversity,
    plot_barplot,
    plot_heatmap,
    setup_matplotlib,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper: QC read-count bar chart
# ---------------------------------------------------------------------------


def _plot_qc_barchart(qc_df: pd.DataFrame, output_path: Path) -> Path:
    """Generate a grouped bar chart showing read counts at each QC stage.

    Args:
        qc_df: QC stats DataFrame with columns: sample, raw_reads,
            trimmed_reads, host_removed_reads.
        output_path: Destination PNG path.

    Returns:
        The resolved output path.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    stages = []
    if "raw_reads" in qc_df.columns:
        stages.append(("raw_reads", "Raw"))
    if "trimmed_reads" in qc_df.columns:
        stages.append(("trimmed_reads", "Trimmed"))
    if "host_removed_reads" in qc_df.columns:
        stages.append(("host_removed_reads", "Host removed"))

    if not stages:
        # Fallback: just save an empty figure
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No QC read-count data available",
                ha="center", va="center", transform=ax.transAxes)
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return output_path

    samples = qc_df["sample"].tolist()
    x = np.arange(len(samples))
    width = 0.8 / len(stages)

    fig, ax = plt.subplots(figsize=(8, 6))
    for i, (col, label) in enumerate(stages):
        vals = qc_df[col].astype(float).values
        colour = DEEPINVIRUS_PALETTE[i % len(DEEPINVIRUS_PALETTE)]
        ax.bar(x + i * width, vals, width, label=label, color=colour)

    ax.set_xlabel("Sample")
    ax.set_ylabel("Read Count")
    ax.set_title("Read Counts by QC Stage")
    ax.set_xticks(x + width * (len(stages) - 1) / 2)
    ax.set_xticklabels(samples, rotation=45, ha="right")
    ax.legend()

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("QC bar chart saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Helper: Detection method bar chart (replaces Venn for >2 methods)
# ---------------------------------------------------------------------------


def _plot_detection_barchart(bigtable_df: pd.DataFrame, output_path: Path) -> Path:
    """Generate a bar chart of detection counts by method.

    Args:
        bigtable_df: The bigtable DataFrame.
        output_path: Destination PNG path.

    Returns:
        The resolved output path.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    if "detection_method" not in bigtable_df.columns:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No detection method data",
                ha="center", va="center", transform=ax.transAxes)
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return output_path

    counts = bigtable_df["detection_method"].value_counts()
    fig, ax = plt.subplots(figsize=(8, 6))
    colours = [DEEPINVIRUS_PALETTE[i % len(DEEPINVIRUS_PALETTE)] for i in range(len(counts))]
    counts.plot.bar(ax=ax, color=colours)
    ax.set_xlabel("Detection Method")
    ax.set_ylabel("Sequence Count")
    ax.set_title("Virus Detection by Method")
    ax.tick_params(axis="x", rotation=45)

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Detection bar chart saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Helper: PCoA scatter from pre-computed coordinates
# ---------------------------------------------------------------------------


def _plot_pcoa_from_coords(pcoa_df: pd.DataFrame, output_path: Path) -> Path:
    """Plot PCoA from pre-computed coordinates.

    Args:
        pcoa_df: DataFrame with columns sample, PC1, PC2 (and optionally PC3).
        output_path: Destination PNG path.

    Returns:
        The resolved output path.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(
        pcoa_df["PC1"], pcoa_df["PC2"],
        s=80, color=DEEPINVIRUS_PALETTE[0], zorder=3,
    )
    for _, row in pcoa_df.iterrows():
        ax.annotate(
            row["sample"],
            (row["PC1"], row["PC2"]),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=9,
        )

    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title("PCoA Ordination")
    ax.set_aspect("equal", adjustable="datalim")

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("PCoA plot saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# Main report builder
# ---------------------------------------------------------------------------


def generate_report(
    bigtable_path: Path,
    matrix_path: Path,
    alpha_path: Path,
    pcoa_path: Path,
    qc_stats_path: Path,
    assembly_stats_path: Path,
    output_path: Path,
    figures_dir: Path | None = None,
) -> Path:
    """Build the Word report and save to *output_path*.

    Args:
        bigtable_path: Path to bigtable.tsv.
        matrix_path: Path to sample_taxon_matrix.tsv.
        alpha_path: Path to alpha_diversity.tsv.
        pcoa_path: Path to pcoa_coordinates.tsv.
        qc_stats_path: Path to QC stats TSV.
        assembly_stats_path: Path to assembly stats TSV.
        output_path: Destination .docx file.
        figures_dir: Optional directory to persist figure PNGs.
            Defaults to a temp directory (cleaned on exit).

    Returns:
        The resolved output path.
    """
    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    bigtable = pd.read_csv(bigtable_path, sep="\t")
    matrix = pd.read_csv(matrix_path, sep="\t")
    alpha = pd.read_csv(alpha_path, sep="\t")
    pcoa = pd.read_csv(pcoa_path, sep="\t")
    # Load QC stats - handle both TSV and fastp JSON formats
    try:
        if qc_stats_path and qc_stats_path.suffix == ".json":
            import json
            with open(qc_stats_path) as f:
                jdata = json.load(f)
            qc_stats = pd.DataFrame([{
                "sample": qc_stats_path.stem.replace(".fastp", ""),
                "total_reads_before": jdata.get("summary", {}).get("before_filtering", {}).get("total_reads", 0),
                "total_reads_after": jdata.get("summary", {}).get("after_filtering", {}).get("total_reads", 0),
            }])
        elif qc_stats_path:
            qc_stats = pd.read_csv(qc_stats_path, sep="\t")
        else:
            qc_stats = pd.DataFrame()
    except Exception:
        qc_stats = pd.DataFrame()

    # Load assembly stats
    try:
        if assembly_stats_path:
            assembly_stats = pd.read_csv(assembly_stats_path, sep="\t")
        else:
            assembly_stats = pd.DataFrame()
    except Exception:
        assembly_stats = pd.DataFrame()

    # ------------------------------------------------------------------
    # Prepare figures directory
    # ------------------------------------------------------------------
    _tmp_handle = None
    if figures_dir is None:
        _tmp_handle = tempfile.TemporaryDirectory()
        figures_dir = Path(_tmp_handle.name)
    else:
        figures_dir = Path(figures_dir)
    figures_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Generate figures
    # ------------------------------------------------------------------
    # Figure: QC read counts bar chart
    qc_fig_path = _plot_qc_barchart(qc_stats, figures_dir / "qc_reads_barchart.png")

    # Figure: Detection method bar chart
    det_fig_path = _plot_detection_barchart(bigtable, figures_dir / "detection_barchart.png")

    # Figure: Taxonomic barplot (relative abundance)
    # Prepare matrix for visualization functions: taxa as rows, samples as columns
    meta_cols = [c for c in ["taxon", "taxid", "rank"] if c in matrix.columns]
    sample_cols = [c for c in matrix.columns if c not in meta_cols]
    viz_matrix = matrix.set_index("taxon")[sample_cols] if "taxon" in matrix.columns else matrix[sample_cols]

    barplot_path = plot_barplot(viz_matrix, figures_dir / "composition_barplot.png")

    # Figure: Heatmap
    heatmap_path = plot_heatmap(viz_matrix, figures_dir / "taxonomic_heatmap.png")

    # Figure: Alpha diversity boxplot
    alpha_fig_path = plot_alpha_diversity(alpha, figures_dir / "alpha_diversity.png")

    # Figure: PCoA
    pcoa_fig_path = _plot_pcoa_from_coords(pcoa, figures_dir / "pcoa_plot.png")

    # ------------------------------------------------------------------
    # Build report
    # ------------------------------------------------------------------
    builder = ReportBuilder()

    # ---- 1. 분석 개요 ----
    builder.add_heading("1. 분석 개요", level=1)
    builder.add_heading("1.1 프로젝트 정보", level=2)

    project_info = pd.DataFrame(
        {
            "항목": [
                "분석 날짜",
                "샘플 수",
                "Total sequences analysed",
                "파이프라인",
            ],
            "값": [
                datetime.now().strftime("%Y-%m-%d"),
                str(len(qc_stats)),
                str(len(bigtable)),
                "DeepInvirus v1.0",
            ],
        }
    )
    builder.add_table(project_info, title="Table. Project Information")

    builder.add_heading("1.2 분석 파이프라인 요약", level=2)
    builder.add_paragraph(
        "DeepInvirus 파이프라인은 Raw FASTQ 데이터로부터 품질 관리, "
        "어셈블리, 바이러스 탐지 (geNomad + Diamond), 분류학적 분석 "
        "(MMseqs2 + TaxonKit), 다양성 분석까지 자동 수행합니다."
    )

    # ---- 2. 품질 관리 결과 ----
    builder.add_heading("2. 품질 관리 (QC) 결과", level=1)

    builder.add_heading("2.1 Raw data 통계", level=2)
    if "raw_reads" in qc_stats.columns:
        raw_table = qc_stats[["sample", "raw_reads", "raw_bases"]].copy() if "raw_bases" in qc_stats.columns else qc_stats[["sample", "raw_reads"]].copy()
        builder.add_table(raw_table, title="Table 1. Raw Data Statistics")

    builder.add_heading("2.2 Trimming 결과", level=2)
    if "trimmed_reads" in qc_stats.columns:
        trim_cols = ["sample", "trimmed_reads"]
        if "trimmed_bases" in qc_stats.columns:
            trim_cols.append("trimmed_bases")
        if "q30_rate" in qc_stats.columns:
            trim_cols.append("q30_rate")
        builder.add_table(qc_stats[trim_cols].copy(), title="Table 2. Trimming Results")

    builder.add_heading("2.3 Host removal 결과", level=2)
    if "host_removed_reads" in qc_stats.columns:
        host_table = qc_stats[["sample", "host_removed_reads"]].copy()
        builder.add_table(host_table, title="Table 3. Host Removal Results")

    builder.add_figure(qc_fig_path, caption="Figure. Read count changes across QC stages", width_inches=6.0)

    # ---- 3. 바이러스 탐지 결과 ----
    builder.add_heading("3. 바이러스 탐지 결과", level=1)

    builder.add_heading("3.1 탐지 방법별 결과 요약", level=2)
    if "detection_method" in bigtable.columns:
        det_summary = (
            bigtable.groupby("detection_method")
            .agg(sequence_count=("seq_id", "count"))
            .reset_index()
        )
        builder.add_table(det_summary, title="Table 4. Detection Method Summary")

    builder.add_heading("3.2 탐지 방법 비교", level=2)
    builder.add_figure(det_fig_path, caption="Figure 1. Virus detection by method", width_inches=6.0)

    # ---- 4. 분류학적 분석 ----
    builder.add_heading("4. 분류학적 분석", level=1)

    builder.add_heading("4.1 바이러스 구성 개요", level=2)
    builder.add_figure(barplot_path, caption="Figure 2. Viral community composition (relative abundance)", width_inches=6.0)

    builder.add_heading("4.2 샘플별 상세 구성", level=2)
    builder.add_figure(heatmap_path, caption="Figure 3. Taxonomic heatmap (log10 RPM+1)", width_inches=6.0)

    builder.add_heading("4.3 주요 바이러스 목록", level=2)
    if "taxon" in matrix.columns:
        top_taxa = matrix.copy()
        top_taxa["mean_abundance"] = viz_matrix.mean(axis=1).values
        top_taxa = top_taxa.sort_values("mean_abundance", ascending=False).head(20)
        display_cols = ["taxon"]
        if "rank" in top_taxa.columns:
            display_cols.append("rank")
        display_cols.append("mean_abundance")
        for sc in sample_cols:
            display_cols.append(sc)
        available_cols = [c for c in display_cols if c in top_taxa.columns]
        builder.add_table(
            top_taxa[available_cols].reset_index(drop=True),
            title="Table 5. Top Viral Taxa",
        )

    # ---- 5. 다양성 분석 ----
    builder.add_heading("5. 다양성 분석", level=1)

    builder.add_heading("5.1 Alpha diversity", level=2)
    builder.add_figure(alpha_fig_path, caption="Figure 4. Alpha diversity boxplot", width_inches=6.0)

    # Alpha diversity table
    builder.add_table(alpha.copy(), title="Table 6. Alpha Diversity Metrics")

    builder.add_heading("5.2 Beta diversity", level=2)
    builder.add_figure(pcoa_fig_path, caption="Figure 5. PCoA ordination (Bray-Curtis)", width_inches=6.0)

    # ---- 6. 결론 및 해석 ----
    builder.add_heading("6. 결론 및 해석", level=1)

    n_samples = len(qc_stats)
    n_viral_seqs = len(bigtable)
    n_taxa = len(viz_matrix)
    mean_shannon = alpha["shannon"].mean() if "shannon" in alpha.columns else 0.0

    builder.add_paragraph(
        f"본 분석에서는 {n_samples}개 샘플로부터 총 {n_viral_seqs}개의 바이러스 "
        f"서열이 탐지되었으며, {n_taxa}개의 바이러스 분류군이 확인되었습니다. "
        f"평균 Shannon diversity index는 {mean_shannon:.2f}로 나타났습니다."
    )
    builder.add_paragraph(
        "상세한 분류학적 정보 및 분석 파라미터는 부록을 참조하시기 바랍니다."
    )

    # ---- 부록 ----
    builder.add_heading("부록", level=1)

    builder.add_heading("A. 상세 분류 테이블", level=2)
    # Show a subset of the bigtable (first 50 rows max)
    bt_display = bigtable.head(50).copy()
    display_bt_cols = [c for c in ["seq_id", "sample", "family", "genus", "species", "rpm", "detection_method"] if c in bt_display.columns]
    if display_bt_cols:
        builder.add_table(bt_display[display_bt_cols], title="Table A1. Detailed Classification (first 50 rows)")

    builder.add_heading("B. 분석 파라미터", level=2)
    params = pd.DataFrame(
        {
            "Parameter": [
                "QC tool",
                "Assembler",
                "Virus detection",
                "Taxonomy",
                "Diversity",
            ],
            "Value": [
                "fastp (default parameters)",
                "MEGAHIT / SPAdes",
                "geNomad + Diamond BLASTx",
                "MMseqs2 + TaxonKit",
                "scikit-bio (Shannon, Simpson, Bray-Curtis)",
            ],
        }
    )
    builder.add_table(params, title="Table B1. Analysis Parameters")

    builder.add_heading("C. 소프트웨어 버전", level=2)
    versions = pd.DataFrame(
        {
            "Software": [
                "DeepInvirus",
                "Nextflow",
                "Python",
                "fastp",
                "geNomad",
                "Diamond",
                "MMseqs2",
            ],
            "Version": [
                "1.0.0",
                ">=23.10",
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "0.23+",
                "1.7+",
                "2.1+",
                "15+",
            ],
        }
    )
    builder.add_table(versions, title="Table C1. Software Versions")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    result = builder.save(output_path)
    logger.info("Report generated: %s", result)

    # Clean up temp dir if we created one
    if _tmp_handle is not None:
        _tmp_handle.cleanup()

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate DeepInvirus Word analysis report",
    )
    parser.add_argument(
        "--bigtable", required=True, type=Path,
        help="Path to bigtable.tsv",
    )
    parser.add_argument(
        "--matrix", required=True, type=Path,
        help="Path to sample_taxon_matrix.tsv",
    )
    parser.add_argument(
        "--alpha", required=True, type=Path,
        help="Path to alpha_diversity.tsv",
    )
    parser.add_argument(
        "--pcoa", required=True, type=Path,
        help="Path to pcoa_coordinates.tsv",
    )
    parser.add_argument(
        "--qc-stats", required=True, type=Path, nargs="+",
        help="Path(s) to QC stats files (fastp JSON or TSV)",
    )
    parser.add_argument(
        "--assembly-stats", required=True, type=Path, nargs="+",
        help="Path(s) to assembly stats TSV files",
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Output .docx file path",
    )
    parser.add_argument(
        "--figures-dir", type=Path, default=None,
        help="Directory to save figure PNGs (default: temp dir)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    args = parse_args(argv)
    # Use first file from multi-file args (or merge if needed later)
    qc_path = args.qc_stats[0] if args.qc_stats else None
    asm_path = args.assembly_stats[0] if args.assembly_stats else None
    generate_report(
        bigtable_path=args.bigtable,
        matrix_path=args.matrix,
        alpha_path=args.alpha,
        pcoa_path=args.pcoa,
        qc_stats_path=qc_path,
        assembly_stats_path=asm_path,
        output_path=args.output,
        figures_dir=args.figures_dir,
    )


if __name__ == "__main__":
    main()
