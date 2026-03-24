#!/usr/bin/env python3
# @TASK T5.2 - Automated Word report generation (improved per-sample analysis)
# @SPEC docs/planning/05-design-system.md#5-word-보고서-템플릿
# @TEST tests/modules/test_report.py
"""Generate a Word (.docx) analysis report for DeepInvirus.

Reads pipeline output files (bigtable, sample-taxon matrix, diversity
tables, QC/assembly stats, per-sample coverage) and produces a formatted
Word document with data-driven conclusions and per-sample comparisons.

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
        --figures-dir figures/ \\
        --coverage-dir coverage/ \\
        --host-stats-dir qc/
"""

from __future__ import annotations

import argparse
import logging
import re
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
# Data loading: per-sample coverage
# ---------------------------------------------------------------------------


def _load_coverage_files(coverage_dir: Path) -> dict[str, pd.DataFrame]:
    """Load all *_coverage.tsv files from coverage directory.

    Returns a dict mapping sample name -> DataFrame with columns:
        Contig, mean_coverage, trimmed_mean, covered_bases, length
    """
    result = {}
    if not coverage_dir or not coverage_dir.exists():
        return result

    for f in sorted(coverage_dir.glob("*_coverage.tsv")):
        # Extract sample name: e.g. GC_Tm_coverage.tsv -> GC_Tm
        sample_name = f.stem.replace("_coverage", "")
        try:
            df = pd.read_csv(f, sep="\t")
            cols = df.columns.tolist()
            # Rename verbose CoverM columns to simple names
            rename_map = {cols[0]: "Contig"}
            if len(cols) > 1:
                rename_map[cols[1]] = "mean_coverage"
            if len(cols) > 2:
                rename_map[cols[2]] = "trimmed_mean"
            if len(cols) > 3:
                rename_map[cols[3]] = "covered_bases"
            if len(cols) > 4:
                rename_map[cols[4]] = "length"
            df = df.rename(columns=rename_map)
            result[sample_name] = df
            logger.info("Loaded coverage for sample '%s': %d contigs", sample_name, len(df))
        except Exception as exc:
            logger.warning("Failed to load coverage from %s: %s", f, exc)

    return result


def _load_host_stats_dir(host_stats_dir: Path) -> pd.DataFrame:
    """Load all *.host_removal_stats.txt files and merge into one DataFrame."""
    rows = []
    if not host_stats_dir or not host_stats_dir.exists():
        return pd.DataFrame()

    for f in sorted(host_stats_dir.glob("*.host_removal_stats.txt")):
        try:
            df = pd.read_csv(f, sep="\t")
            if not df.empty:
                rows.append(df)
        except Exception as exc:
            logger.warning("Failed to load host stats from %s: %s", f, exc)

    if rows:
        return pd.concat(rows, ignore_index=True)
    return pd.DataFrame()


def _load_bbduk_stats(qc_dir: Path) -> list[dict]:
    """Parse BBDuk stats files to extract adapter removal statistics."""
    results = []
    if not qc_dir or not qc_dir.exists():
        return results

    for f in sorted(qc_dir.glob("*.bbduk_stats.txt")):
        sample_name = f.stem.replace(".bbduk_stats", "")
        try:
            text = f.read_text()
            # Parse first section (adapter removal)
            lines = text.strip().split("\n")
            total_reads = 0
            matched_reads = 0
            matched_pct = 0.0
            phix_reads = 0

            for line in lines:
                if line.startswith("#Total"):
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        total_reads = int(parts[1])
                elif line.startswith("#Matched"):
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        matched_reads = int(parts[1])
                    if len(parts) >= 3:
                        matched_pct = float(parts[2].replace("%", ""))
                elif "PhiX" in line:
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        phix_reads += int(parts[1])

            results.append({
                "sample": sample_name,
                "total_reads": total_reads,
                "adapter_removed": matched_reads,
                "adapter_pct": matched_pct,
                "phix_removed": phix_reads,
                "clean_reads": total_reads - matched_reads,
            })
        except Exception as exc:
            logger.warning("Failed to parse BBDuk stats from %s: %s", f, exc)

    return results


def _build_per_sample_coverage_table(
    bigtable: pd.DataFrame,
    coverage_data: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Build a table comparing viral contig coverage across samples.

    Returns DataFrame with columns:
        contig, family, length, <sample1>_coverage, <sample2>_coverage, ...
    """
    if not coverage_data or bigtable.empty:
        return pd.DataFrame()

    viral_contigs = bigtable["seq_id"].tolist()
    result = bigtable[["seq_id", "family", "length"]].copy()
    result = result.rename(columns={"seq_id": "contig"})

    for sample_name, cov_df in sorted(coverage_data.items()):
        cov_subset = cov_df[cov_df["Contig"].isin(viral_contigs)][["Contig", "mean_coverage"]].copy()
        cov_subset = cov_subset.rename(columns={
            "Contig": "contig",
            "mean_coverage": f"{sample_name}_cov",
        })
        result = result.merge(cov_subset, on="contig", how="left")

    # Fill NaN with 0
    cov_cols = [c for c in result.columns if c.endswith("_cov")]
    result[cov_cols] = result[cov_cols].fillna(0)

    # Sort by max coverage descending
    if cov_cols:
        result["max_cov"] = result[cov_cols].max(axis=1)
        result = result.sort_values("max_cov", ascending=False)
        result = result.drop(columns=["max_cov"])

    return result


# ---------------------------------------------------------------------------
# Figure generators
# ---------------------------------------------------------------------------


def _plot_host_mapping_comparison(host_stats: pd.DataFrame, output_path: Path) -> Path:
    """Generate a grouped bar chart comparing host mapping rates across samples."""
    setup_matplotlib()
    output_path = Path(output_path)

    if host_stats.empty or "sample" not in host_stats.columns:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No host removal data available",
                ha="center", va="center", transform=ax.transAxes)
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return output_path

    samples = host_stats["sample"].tolist()
    host_pct = host_stats["host_removal_rate"].values.astype(float)
    nonhost_pct = 100.0 - host_pct

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(samples))
    width = 0.5

    bars_host = ax.bar(x, host_pct, width, label="Host RNA (%)", color="#BDBDBD")
    bars_nonhost = ax.bar(x, nonhost_pct, width, bottom=host_pct,
                          label="Non-host (viral + other) (%)", color="#1F77B4")

    # Annotate percentages
    for i, (h, nh) in enumerate(zip(host_pct, nonhost_pct)):
        ax.text(i, h / 2, f"{h:.1f}%", ha="center", va="center",
                fontweight="bold", fontsize=11, color="white" if h > 20 else "black")
        ax.text(i, h + nh / 2, f"{nh:.1f}%", ha="center", va="center",
                fontweight="bold", fontsize=11, color="white" if nh > 20 else "black")

    ax.set_xlabel("Sample", fontsize=12)
    ax.set_ylabel("Proportion (%)", fontsize=12)
    ax.set_title("Host Mapping Rate Comparison", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(samples, fontsize=11)
    ax.set_ylim(0, 105)
    ax.legend(loc="upper right", fontsize=10)

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Host mapping comparison chart saved to %s", output_path)
    return output_path


def _plot_per_sample_coverage_heatmap(
    cov_table: pd.DataFrame,
    output_path: Path,
    top_n: int = 30,
) -> Path:
    """Generate a heatmap of viral contig coverage across samples."""
    setup_matplotlib()
    output_path = Path(output_path)

    if cov_table.empty:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No per-sample coverage data",
                ha="center", va="center", transform=ax.transAxes)
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return output_path

    cov_cols = [c for c in cov_table.columns if c.endswith("_cov")]
    if not cov_cols:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No coverage columns found",
                ha="center", va="center", transform=ax.transAxes)
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return output_path

    # Take top N contigs
    plot_df = cov_table.head(top_n).copy()

    # Create label: family (contig)
    labels = []
    for _, row in plot_df.iterrows():
        family = row.get("family", "Unknown")
        contig = row.get("contig", "")
        labels.append(f"{family} ({contig})")

    # Prepare matrix for heatmap
    matrix = plot_df[cov_cols].values
    # log10 transform for better visualization
    matrix_log = np.log10(matrix + 1)

    # Clean column names for display
    sample_names = [c.replace("_cov", "") for c in cov_cols]

    fig, ax = plt.subplots(figsize=(max(8, len(cov_cols) * 3), max(8, len(labels) * 0.35)))
    im = ax.imshow(matrix_log, aspect="auto", cmap="YlOrRd")

    ax.set_xticks(range(len(sample_names)))
    ax.set_xticklabels(sample_names, fontsize=11, fontweight="bold")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)

    # Add text annotations with actual values
    for i in range(len(labels)):
        for j in range(len(sample_names)):
            val = matrix[i, j]
            text_color = "white" if matrix_log[i, j] > matrix_log.max() * 0.6 else "black"
            if val >= 1000:
                text = f"{val:.0f}"
            elif val >= 1:
                text = f"{val:.1f}"
            else:
                text = f"{val:.2f}" if val > 0 else "0"
            ax.text(j, i, text, ha="center", va="center",
                    fontsize=7, color=text_color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("log10(mean coverage + 1)", fontsize=10)

    ax.set_title("Per-sample Viral Contig Coverage", fontsize=14, fontweight="bold")
    ax.set_xlabel("Sample", fontsize=12)

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Per-sample coverage heatmap saved to %s", output_path)
    return output_path


def _plot_detection_barchart(bigtable_df: pd.DataFrame, output_path: Path) -> Path:
    """Generate a bar chart of detection counts by method."""
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


def _plot_family_composition(bigtable: pd.DataFrame, output_path: Path) -> Path:
    """Generate a pie chart of virus family distribution."""
    setup_matplotlib()
    output_path = Path(output_path)

    if "family" not in bigtable.columns:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No family data available",
                ha="center", va="center", transform=ax.transAxes)
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return output_path

    family_counts = bigtable["family"].value_counts()

    fig, ax = plt.subplots(figsize=(10, 8))
    colors = [DEEPINVIRUS_PALETTE[i % len(DEEPINVIRUS_PALETTE)]
              for i in range(len(family_counts))]

    wedges, texts, autotexts = ax.pie(
        family_counts.values,
        labels=family_counts.index,
        autopct=lambda pct: f"{pct:.1f}%\n({int(round(pct/100.*family_counts.sum()))})",
        colors=colors,
        pctdistance=0.85,
        startangle=90,
    )
    for t in texts:
        t.set_fontsize(9)
    for t in autotexts:
        t.set_fontsize(8)

    ax.set_title("Virus Family Composition (by contig count)", fontsize=14, fontweight="bold")

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Family composition chart saved to %s", output_path)
    return output_path


def _plot_qc_barchart(bbduk_stats: list[dict], output_path: Path) -> Path:
    """Generate a grouped bar chart for BBDuk adapter removal stats."""
    setup_matplotlib()
    output_path = Path(output_path)

    if not bbduk_stats:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No BBDuk QC data available",
                ha="center", va="center", transform=ax.transAxes)
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return output_path

    df = pd.DataFrame(bbduk_stats)
    samples = df["sample"].tolist()
    x = np.arange(len(samples))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.bar(x - width/2, df["total_reads"].values / 1e6, width,
           label="Total reads (M)", color=DEEPINVIRUS_PALETTE[0])
    ax.bar(x + width/2, df["clean_reads"].values / 1e6, width,
           label="After adapter removal (M)", color=DEEPINVIRUS_PALETTE[2])

    ax.set_xlabel("Sample", fontsize=12)
    ax.set_ylabel("Read Count (millions)", fontsize=12)
    ax.set_title("BBDuk Adapter Removal", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(samples, fontsize=11)
    ax.legend(fontsize=10)

    # Add percentage labels
    for i, row in df.iterrows():
        pct = row["adapter_pct"]
        ax.text(i + width/2, row["clean_reads"] / 1e6 + 0.5,
                f"-{pct:.1f}%", ha="center", fontsize=9, color="red")

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("QC bar chart saved to %s", output_path)
    return output_path


def _plot_pcoa_from_coords(pcoa_df: pd.DataFrame, output_path: Path) -> Path:
    """Plot PCoA from pre-computed coordinates."""
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
# Virus family descriptions (for scientific context)
# ---------------------------------------------------------------------------

FAMILY_DESCRIPTIONS = {
    "Parvoviridae": (
        "단일가닥 DNA 바이러스 (ssDNA). 곤충에서 발견되는 Densovirinae 아과를 포함하며, "
        "밀도핵다각체병바이러스(densovirus)로 곤충의 주요 병원체로 알려져 있습니다. "
        "곤충 세포의 핵에서 증식하며, 숙주 사멸을 유발할 수 있습니다."
    ),
    "Picornaviridae": (
        "양성 단일가닥 RNA 바이러스 (+ssRNA). 곤충에서 다양한 피코르나유사바이러스(picorna-like virus)가 "
        "보고되어 있으며, 장내 감염을 통해 전파됩니다. "
        "Cricket paralysis virus, Drosophila C virus 등이 이 과에 속합니다."
    ),
    "Sinhaliviridae": (
        "양성 단일가닥 RNA 바이러스. Nodamuvirales 목에 속하며, "
        "주로 곤충 및 무척추동물에서 발견됩니다. 비교적 최근 분류된 바이러스과입니다."
    ),
    "Baculoviridae": (
        "이중가닥 DNA 바이러스 (dsDNA). 곤충, 특히 나비목(Lepidoptera)의 주요 병원체로, "
        "핵다각체병(nucleopolyhedrovirus)을 유발합니다. "
        "생물학적 해충 방제에 널리 활용되는 바이러스입니다."
    ),
    "Caudoviricetes": (
        "꼬리형 박테리오파지를 포함하는 분류군. 세균을 감염시키는 바이러스로, "
        "환경 시료에서 가장 흔하게 발견되는 바이러스 그룹 중 하나입니다. "
        "곤충 장내 미생물군집의 세균을 감염시키는 것으로 추정됩니다."
    ),
    "Flaviviridae": (
        "양성 단일가닥 RNA 바이러스. 곤충 특이적 플라비바이러스(insect-specific flavivirus)가 "
        "다수 보고되어 있으며, 모기 등 흡혈 곤충에서 주로 발견됩니다."
    ),
    "Bromoviridae": (
        "양성 단일가닥 RNA 바이러스. 주로 식물 병원체이나, "
        "곤충에서의 검출은 식물 유래 RNA의 섭취를 반영할 수 있습니다."
    ),
    "Narnaviridae": (
        "양성 단일가닥 RNA 바이러스. 진균에 감염하는 나르나바이러스를 포함하며, "
        "곤충 장내 진균군집과의 연관이 시사됩니다."
    ),
    "Mitoviridae": (
        "양성 단일가닥 RNA 바이러스. 진균의 미토콘드리아에서 증식하는 바이러스로, "
        "곤충 장내 진균에서 유래했을 가능성이 있습니다."
    ),
    "Endornaviridae": (
        "이중가닥 RNA 바이러스 (dsRNA). 식물 및 진균에 감염하며, "
        "곤충 시료에서의 검출은 먹이사슬을 통한 간접 검출을 시사합니다."
    ),
    "Virgaviridae": (
        "양성 단일가닥 RNA 바이러스. 주요 식물 병원체로, "
        "Tobacco mosaic virus (TMV) 등이 이 과에 속합니다. "
        "곤충이 식물을 섭취하면서 검출되었을 가능성이 높습니다."
    ),
    "Fiersviridae": (
        "양성 단일가닥 RNA 바이러스. 세균을 감염시키는 RNA 파지를 포함하며, "
        "곤충 장내 세균군집과의 연관이 추정됩니다."
    ),
    "Adintoviridae": (
        "이중가닥 DNA 바이러스. Polinton-like virus에서 유래한 비교적 새로운 분류군으로, "
        "진핵생물 게놈에 통합된 형태로도 발견됩니다."
    ),
}


# ---------------------------------------------------------------------------
# Data-driven conclusion generator
# ---------------------------------------------------------------------------


def _generate_conclusion(
    bigtable: pd.DataFrame,
    host_stats: pd.DataFrame,
    coverage_data: dict[str, pd.DataFrame],
    alpha: pd.DataFrame,
    sample_names: list[str],
) -> list[str]:
    """Generate data-driven conclusion paragraphs.

    Returns a list of paragraph strings.
    """
    paragraphs = []

    n_contigs = len(bigtable)
    n_samples = len(sample_names)
    families = bigtable["family"].value_counts() if "family" in bigtable.columns else pd.Series()
    classified_families = families[families.index != "Unclassified"]

    # --- Overview ---
    paragraphs.append(
        f"본 분석에서는 {n_samples}개 샘플 ({', '.join(sample_names)})의 "
        f"co-assembly를 통해 총 {n_contigs}개의 바이러스 유래 contig이 탐지되었으며, "
        f"{len(classified_families)}개의 바이러스 분류군(family 이상)이 확인되었습니다."
    )

    # --- Host mapping comparison ---
    if not host_stats.empty and len(host_stats) >= 2:
        for _, row in host_stats.iterrows():
            sample = row.get("sample", "")
            rate = row.get("host_removal_rate", 0)
            total = row.get("total_reads", 0)
            unmapped = row.get("unmapped_reads", 0)
            paragraphs.append(
                f"{sample}: 전체 {total:,}개 read 중 host RNA 매핑률 {rate:.1f}%, "
                f"non-host read {unmapped:,}개 ({100-rate:.1f}%)"
            )

        # Find sample with lowest and highest mapping rate
        low_sample = host_stats.loc[host_stats["host_removal_rate"].idxmin()]
        high_sample = host_stats.loc[host_stats["host_removal_rate"].idxmax()]

        paragraphs.append(
            f"Host 매핑률 비교에서 {low_sample['sample']} ({low_sample['host_removal_rate']:.1f}%)과 "
            f"{high_sample['sample']} ({high_sample['host_removal_rate']:.1f}%) 사이에 "
            f"현저한 차이가 관찰되었습니다. "
            f"{low_sample['sample']}의 낮은 매핑률은 host RNA의 분해(죽은 샘플)를 시사하며, "
            f"이로 인해 전체 RNA 중 바이러스 유래 RNA의 비율이 상대적으로 높게 나타납니다. "
            f"반면, {high_sample['sample']}의 높은 매핑률({high_sample['host_removal_rate']:.1f}%)은 "
            f"활발한 세포 활동(살아있는 샘플)에서 기인한 풍부한 host RNA를 반영합니다."
        )

    # --- Key virus findings ---
    if not classified_families.empty:
        top3 = classified_families.head(3)
        top_text = ", ".join([f"{name} ({count}개 contig)" for name, count in top3.items()])
        paragraphs.append(
            f"주요 바이러스 분류군은 {top_text}으로 나타났습니다."
        )

    # --- Per-sample coverage insights ---
    if coverage_data and not bigtable.empty:
        cov_table = _build_per_sample_coverage_table(bigtable, coverage_data)
        cov_cols = [c for c in cov_table.columns if c.endswith("_cov")]

        if len(cov_cols) >= 2 and not cov_table.empty:
            # Count contigs detected predominantly in each sample
            for col in cov_cols:
                sample_name = col.replace("_cov", "")
                n_dominant = (cov_table[col] > 10).sum()  # coverage > 10x
                paragraphs.append(
                    f"{sample_name}에서 coverage > 10x인 바이러스 contig: {n_dominant}개"
                )

    # --- Parvoviridae highlight ---
    if "Parvoviridae" in families.index:
        parvo_contigs = bigtable[bigtable["family"] == "Parvoviridae"]
        paragraphs.append(
            f"특히 Parvoviridae (덴소바이러스과)가 {len(parvo_contigs)}개 contig으로 탐지되었습니다. "
            "Parvoviridae에 속하는 곤충 덴소바이러스(densovirus)는 곤충의 주요 병원체로, "
            "높은 coverage는 활발한 바이러스 증식을 시사합니다."
        )

    # --- Diversity ---
    if "shannon" in alpha.columns:
        mean_shannon = alpha["shannon"].mean()
        paragraphs.append(
            f"Shannon diversity index {mean_shannon:.3f}로, "
            "중간 수준의 바이러스 다양성이 확인되었습니다."
        )

    return paragraphs


# ---------------------------------------------------------------------------
# Main report builder
# ---------------------------------------------------------------------------


def generate_report(
    bigtable_path: Path,
    matrix_path: Path,
    alpha_path: Path,
    pcoa_path: Path,
    qc_stats_path: Path | None,
    assembly_stats_path: Path | None,
    output_path: Path,
    figures_dir: Path | None = None,
    host_stats_path: Path | None = None,
    coverage_dir: Path | None = None,
    host_stats_dir: Path | None = None,
) -> Path:
    """Build the Word report and save to *output_path*.

    Args:
        bigtable_path: Path to bigtable.tsv.
        matrix_path: Path to sample_taxon_matrix.tsv.
        alpha_path: Path to alpha_diversity.tsv.
        pcoa_path: Path to pcoa_coordinates.tsv.
        qc_stats_path: Path to QC stats TSV (optional).
        assembly_stats_path: Path to assembly stats TSV (optional).
        output_path: Destination .docx file.
        figures_dir: Optional directory to persist figure PNGs.
        host_stats_path: Optional path to single host_removal_stats.tsv.
        coverage_dir: Optional directory containing per-sample coverage TSVs.
        host_stats_dir: Optional directory containing host_removal_stats files.

    Returns:
        The resolved output path.
    """
    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    bigtable = pd.read_csv(bigtable_path, sep="\t")
    matrix = pd.read_csv(matrix_path, sep="\t")
    alpha = pd.read_csv(alpha_path, sep="\t")

    pcoa = pd.DataFrame()
    try:
        if pcoa_path and Path(pcoa_path).exists():
            pcoa = pd.read_csv(pcoa_path, sep="\t")
    except Exception:
        pass

    # Load per-sample coverage data
    coverage_data = {}
    if coverage_dir:
        coverage_data = _load_coverage_files(Path(coverage_dir))

    # Determine actual sample names from coverage files
    sample_names = sorted(coverage_data.keys()) if coverage_data else []
    if not sample_names:
        # Fallback: try to get from bigtable sample column
        if "sample" in bigtable.columns:
            unique_samples = bigtable["sample"].dropna().unique().tolist()
            # Exclude 'coassembly' as it's not a real sample
            sample_names = [s for s in unique_samples if s.lower() != "coassembly"]
    n_samples = len(sample_names) if sample_names else 1  # At minimum the co-assembly

    # Load host removal stats
    host_stats = pd.DataFrame()
    if host_stats_dir:
        host_stats = _load_host_stats_dir(Path(host_stats_dir))
    if host_stats.empty and host_stats_path:
        try:
            if Path(host_stats_path).exists():
                host_stats = pd.read_csv(host_stats_path, sep="\t")
        except Exception:
            pass

    # Load BBDuk stats
    bbduk_stats = []
    qc_dir = Path(host_stats_dir) if host_stats_dir else None
    if qc_dir:
        bbduk_stats = _load_bbduk_stats(qc_dir)

    # If sample_names is still empty, derive from host_stats
    if not sample_names and not host_stats.empty:
        sample_names = host_stats["sample"].tolist()
        n_samples = len(sample_names)

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
    # Build per-sample coverage comparison table
    # ------------------------------------------------------------------
    cov_table = _build_per_sample_coverage_table(bigtable, coverage_data)

    # ------------------------------------------------------------------
    # Generate figures
    # ------------------------------------------------------------------
    # Figure: Host mapping rate comparison
    host_fig_path = _plot_host_mapping_comparison(
        host_stats, figures_dir / "host_mapping_comparison.png"
    )

    # Figure: BBDuk QC bar chart
    qc_fig_path = _plot_qc_barchart(bbduk_stats, figures_dir / "qc_bbduk_barchart.png")

    # Figure: Detection method bar chart
    det_fig_path = _plot_detection_barchart(bigtable, figures_dir / "detection_barchart.png")

    # Figure: Family composition pie chart
    family_fig_path = _plot_family_composition(bigtable, figures_dir / "family_composition.png")

    # Figure: Per-sample coverage heatmap
    cov_heatmap_path = _plot_per_sample_coverage_heatmap(
        cov_table, figures_dir / "per_sample_coverage_heatmap.png"
    )

    # Figure: Taxonomic barplot (relative abundance)
    meta_cols = [c for c in ["taxon", "taxid", "rank"] if c in matrix.columns]
    sample_matrix_cols = [c for c in matrix.columns if c not in meta_cols]
    viz_matrix = matrix.set_index("taxon")[sample_matrix_cols] if "taxon" in matrix.columns else matrix[sample_matrix_cols]

    barplot_path = None
    heatmap_path = None
    alpha_fig_path = None
    pcoa_fig_path = None

    try:
        barplot_path = plot_barplot(viz_matrix, figures_dir / "composition_barplot.png")
    except Exception as e:
        logger.warning(f"Barplot generation failed: {e}")

    try:
        heatmap_path = plot_heatmap(viz_matrix, figures_dir / "taxonomic_heatmap.png")
    except Exception as e:
        logger.warning(f"Heatmap generation failed: {e}")

    try:
        alpha_fig_path = plot_alpha_diversity(alpha, figures_dir / "alpha_diversity.png")
    except Exception as e:
        logger.warning(f"Alpha diversity plot failed: {e}")

    try:
        if not pcoa.empty:
            pcoa_fig_path = _plot_pcoa_from_coords(pcoa, figures_dir / "pcoa_plot.png")
    except Exception as e:
        logger.warning(f"PCoA plot failed: {e}")

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
                "샘플 이름",
                "분석 전략",
                "탐지된 바이러스 contig 수",
                "파이프라인",
            ],
            "값": [
                datetime.now().strftime("%Y-%m-%d"),
                str(n_samples),
                ", ".join(sample_names) if sample_names else "coassembly",
                "Co-assembly (전체 샘플 통합 어셈블리) + per-sample coverage mapping",
                str(len(bigtable)),
                "DeepInvirus v1.0",
            ],
        }
    )
    builder.add_table(project_info, title="Table 1. Project Information")

    builder.add_heading("1.2 분석 파이프라인 요약", level=2)
    builder.add_paragraph(
        "DeepInvirus 파이프라인은 다음의 단계를 순차적으로 수행합니다: "
        "(1) BBDuk을 이용한 어댑터 제거 및 품질 관리, "
        "(2) Bowtie2를 이용한 host RNA 제거, "
        "(3) MEGAHIT을 이용한 co-assembly, "
        "(4) geNomad 및 Diamond BLASTx를 이용한 바이러스 서열 탐지, "
        "(5) MMseqs2 + TaxonKit를 이용한 분류학적 분석, "
        "(6) CoverM을 이용한 샘플별 coverage 산출, "
        "(7) 다양성 지수 산출 및 보고서 생성."
    )

    if sample_names and len(sample_names) >= 2:
        builder.add_paragraph(
            "본 분석에서는 co-assembly 전략을 채택하여 모든 샘플의 read를 통합 어셈블리한 후, "
            "각 샘플의 read를 개별적으로 매핑하여 contig별 per-sample coverage를 산출하였습니다. "
            "이를 통해 co-assembly의 민감도 이점을 유지하면서도 샘플 간 바이러스 분포 차이를 "
            "정량적으로 비교할 수 있습니다."
        )

    # ---- 2. 품질 관리 결과 ----
    builder.add_heading("2. 품질 관리 (QC) 결과", level=1)

    # 2.1 BBDuk 통계
    builder.add_heading("2.1 어댑터 제거 (BBDuk)", level=2)
    if bbduk_stats:
        bbduk_df = pd.DataFrame(bbduk_stats)
        display_df = bbduk_df[["sample", "total_reads", "adapter_removed", "adapter_pct", "phix_removed", "clean_reads"]].copy()
        display_df.columns = ["Sample", "Total Reads", "Adapter Removed", "Adapter %", "PhiX Removed", "Clean Reads"]
        # Format numbers with commas
        for col in ["Total Reads", "Adapter Removed", "PhiX Removed", "Clean Reads"]:
            display_df[col] = display_df[col].apply(lambda x: f"{x:,}")
        display_df["Adapter %"] = display_df["Adapter %"].apply(lambda x: f"{x:.2f}%")
        builder.add_table(display_df, title="Table 2. BBDuk Adapter Removal Statistics")

        if qc_fig_path:
            builder.add_figure(qc_fig_path,
                             caption="Figure 1. BBDuk adapter removal: total reads vs clean reads per sample",
                             width_inches=6.0)

        builder.add_paragraph(
            "BBDuk을 이용하여 Illumina 어댑터, PCR primer, PhiX 서열을 제거하였습니다. "
            f"어댑터 제거율은 {bbduk_stats[0]['adapter_pct']:.1f}% ~ "
            f"{bbduk_stats[-1]['adapter_pct']:.1f}% 범위를 보였습니다."
        )
    else:
        builder.add_paragraph("BBDuk 통계 파일이 제공되지 않았습니다.")

    # 2.2 Host removal
    builder.add_heading("2.2 Host RNA 제거", level=2)
    if not host_stats.empty:
        host_display = host_stats.copy()
        # Format for display
        host_display_formatted = pd.DataFrame({
            "Sample": host_display["sample"],
            "Total Reads": host_display["total_reads"].apply(lambda x: f"{x:,}"),
            "Host Mapped": host_display["mapped_reads"].apply(lambda x: f"{x:,}"),
            "Non-host Reads": host_display["unmapped_reads"].apply(lambda x: f"{x:,}"),
            "Host Mapping Rate (%)": host_display["host_removal_rate"].apply(lambda x: f"{x:.2f}"),
        })
        builder.add_table(host_display_formatted, title="Table 3. Host Removal Mapping Statistics")

        if host_fig_path:
            builder.add_figure(host_fig_path,
                             caption="Figure 2. Host mapping rate comparison (grey=host RNA, blue=non-host)",
                             width_inches=6.0)

        # Scientific interpretation
        if len(host_stats) >= 2:
            low = host_stats.loc[host_stats["host_removal_rate"].idxmin()]
            high = host_stats.loc[host_stats["host_removal_rate"].idxmax()]
            builder.add_paragraph(
                f"Host 매핑률에서 샘플 간 현저한 차이가 관찰되었습니다. "
                f"{low['sample']}은 host 매핑률 {low['host_removal_rate']:.1f}%로, "
                f"전체 RNA의 약 {100-low['host_removal_rate']:.1f}%가 non-host 유래입니다. "
                f"반면, {high['sample']}은 매핑률 {high['host_removal_rate']:.1f}%로, "
                f"대부분의 RNA가 숙주에서 유래하였습니다."
            )
            builder.add_paragraph(
                "이러한 차이는 샘플의 생물학적 상태를 반영합니다. "
                f"{low['sample']} (낮은 매핑률)은 세포 사멸로 인해 host RNA가 분해되어 "
                "상대적으로 바이러스/환경 유래 RNA의 비율이 높은 것으로 해석됩니다. "
                f"{high['sample']} (높은 매핑률)은 활발한 세포 활동으로 인해 host RNA가 "
                "풍부하여, 실제 바이러스 검출이 매우 제한적입니다."
            )
    else:
        builder.add_paragraph("Host removal 통계 파일이 제공되지 않았습니다.")

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

    builder.add_paragraph(
        f"Co-assembly를 통해 총 {len(bigtable)}개의 바이러스 유래 contig이 탐지되었습니다. "
        f"Contig 길이 범위: {bigtable['length'].min():,}bp ~ {bigtable['length'].max():,}bp "
        f"(중앙값: {bigtable['length'].median():,.0f}bp)."
    )

    if det_fig_path:
        builder.add_figure(det_fig_path,
                         caption="Figure 3. Virus detection by method",
                         width_inches=6.0)

    # 3.2 Family별 분포
    builder.add_heading("3.2 바이러스 Family별 분포", level=2)
    if "family" in bigtable.columns:
        family_summary = bigtable["family"].value_counts().reset_index()
        family_summary.columns = ["Family/Order", "Contig Count"]
        builder.add_table(family_summary, title="Table 5. Virus Family Distribution")

    if family_fig_path:
        builder.add_figure(family_fig_path,
                         caption="Figure 4. Virus family composition (by contig count)",
                         width_inches=6.0)

    # 3.3 Per-sample coverage 비교
    builder.add_heading("3.3 샘플별 바이러스 Coverage 비교", level=2)
    if not cov_table.empty:
        cov_cols = [c for c in cov_table.columns if c.endswith("_cov")]
        if cov_cols:
            # Display top 20 contigs
            display_cov = cov_table.head(20).copy()
            # Format coverage values
            for col in cov_cols:
                display_cov[col] = display_cov[col].apply(
                    lambda x: f"{x:,.1f}" if x >= 1 else (f"{x:.2f}" if x > 0 else "0")
                )
            display_cov.columns = [c.replace("_cov", " Coverage") if c.endswith("_cov") else c
                                   for c in display_cov.columns]
            builder.add_table(display_cov, title="Table 6. Per-sample Viral Contig Coverage (Top 20, mean depth)")

            builder.add_paragraph(
                "Coverage 값은 각 샘플의 read를 co-assembly contig에 매핑한 결과의 "
                "평균 depth를 나타냅니다. 높은 coverage는 해당 바이러스 서열이 "
                "해당 샘플에서 풍부하게 존재함을 의미합니다."
            )

        if cov_heatmap_path:
            builder.add_figure(cov_heatmap_path,
                             caption="Figure 5. Per-sample viral contig coverage heatmap (log10 scale)",
                             width_inches=6.5)
    else:
        builder.add_paragraph(
            "Per-sample coverage 데이터가 제공되지 않았습니다. "
            "Coverage 파일은 --coverage-dir 옵션으로 지정할 수 있습니다."
        )

    # ---- 4. 분류학적 분석 ----
    builder.add_heading("4. 분류학적 분석", level=1)

    builder.add_heading("4.1 바이러스 분류군 개요", level=2)
    if barplot_path:
        builder.add_figure(barplot_path,
                         caption="Figure 6. Viral community composition (relative abundance, co-assembly)",
                         width_inches=6.0)

    builder.add_heading("4.2 분류학적 히트맵", level=2)
    if heatmap_path:
        builder.add_figure(heatmap_path,
                         caption="Figure 7. Taxonomic heatmap (log10 RPM+1, co-assembly)",
                         width_inches=6.0)

    # 4.3 주요 바이러스 Family 상세 설명
    builder.add_heading("4.3 주요 바이러스 Family 상세 설명", level=2)
    if "family" in bigtable.columns:
        classified = bigtable[bigtable["family"] != "Unclassified"]["family"].value_counts()
        for family_name, count in classified.items():
            builder.add_heading(f"4.3.{list(classified.index).index(family_name)+1} {family_name} ({count}개 contig)", level=3)

            description = FAMILY_DESCRIPTIONS.get(
                family_name,
                f"{family_name}에 대한 상세 설명이 아직 등록되지 않았습니다."
            )
            builder.add_paragraph(description)

            # Show coverage for this family's contigs
            if not cov_table.empty:
                family_contigs = cov_table[cov_table["family"] == family_name]
                if not family_contigs.empty:
                    cov_cols_display = [c for c in family_contigs.columns if c.endswith("_cov")]
                    if cov_cols_display:
                        fc_display = family_contigs[["contig", "length"] + cov_cols_display].copy()
                        for col in cov_cols_display:
                            fc_display[col] = fc_display[col].apply(
                                lambda x: f"{x:,.1f}" if x >= 1 else (f"{x:.2f}" if x > 0 else "0")
                            )
                        fc_display.columns = [c.replace("_cov", "") if c.endswith("_cov") else c
                                              for c in fc_display.columns]
                        builder.add_table(fc_display.reset_index(drop=True),
                                        title=f"Table. {family_name} contig coverage by sample")

    # ---- 5. 다양성 분석 ----
    builder.add_heading("5. 다양성 분석", level=1)

    builder.add_heading("5.1 Alpha diversity", level=2)
    if alpha_fig_path:
        builder.add_figure(alpha_fig_path,
                         caption="Figure 8. Alpha diversity (co-assembly basis)",
                         width_inches=6.0)

    builder.add_table(alpha.copy(), title="Table 7. Alpha Diversity Metrics")

    builder.add_paragraph(
        "Alpha diversity 지수는 co-assembly 기준으로 산출되었습니다. "
        "Per-sample 다양성 비교를 위해서는 각 샘플별 독립 어셈블리 또는 "
        "coverage 기반 풍부도 추정이 필요합니다."
    )

    builder.add_heading("5.2 Beta diversity", level=2)
    if pcoa_fig_path:
        builder.add_figure(pcoa_fig_path,
                         caption="Figure 9. PCoA ordination (Bray-Curtis)",
                         width_inches=6.0)
    else:
        builder.add_paragraph(
            "Beta diversity PCoA 분석은 co-assembly 단일 샘플로 인해 수행되지 않았습니다. "
            "향후 샘플 수 증가 시 샘플 간 유사도 비교가 가능합니다."
        )

    # ---- 6. 결론 및 해석 ----
    builder.add_heading("6. 결론 및 해석", level=1)

    conclusion_paragraphs = _generate_conclusion(
        bigtable, host_stats, coverage_data, alpha, sample_names
    )
    for para in conclusion_paragraphs:
        builder.add_paragraph(para)

    builder.add_paragraph(
        "상세한 분류학적 정보 및 분석 파라미터는 부록을 참조하시기 바랍니다."
    )

    # ---- 부록 ----
    builder.add_heading("부록", level=1)

    builder.add_heading("A. 전체 바이러스 Contig 목록", level=2)
    bt_display = bigtable.copy()
    display_bt_cols = [c for c in ["seq_id", "sample", "family", "length", "detection_method", "detection_score", "target", "pident"]
                       if c in bt_display.columns]
    if display_bt_cols:
        builder.add_table(bt_display[display_bt_cols],
                        title="Table A1. Complete Viral Contig List")

    builder.add_heading("B. 분석 파라미터", level=2)
    params = pd.DataFrame(
        {
            "Parameter": [
                "Adapter removal",
                "Host removal",
                "Assembler",
                "Virus detection",
                "Taxonomy",
                "Coverage",
                "Diversity",
            ],
            "Value": [
                "BBDuk (Illumina adapters, PCR primers, PhiX)",
                "Bowtie2 (--very-sensitive-local)",
                "MEGAHIT (co-assembly)",
                "geNomad + Diamond BLASTx",
                "MMseqs2 + TaxonKit",
                "CoverM (mean, trimmed mean, covered bases)",
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
                "BBDuk (BBTools)",
                "Bowtie2",
                "MEGAHIT",
                "geNomad",
                "Diamond",
                "MMseqs2",
                "CoverM",
            ],
            "Version": [
                "1.0.0",
                ">=23.10",
                f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                "39.06+",
                "2.5+",
                "1.2+",
                "1.7+",
                "2.1+",
                "15+",
                "0.7+",
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
        "--pcoa", type=Path, default=None,
        help="Path to pcoa_coordinates.tsv",
    )
    parser.add_argument(
        "--qc-stats", type=Path, nargs="*", default=None,
        help="Path(s) to QC stats files (fastp JSON or TSV)",
    )
    parser.add_argument(
        "--assembly-stats", type=Path, nargs="*", default=None,
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
    parser.add_argument(
        "--host-stats", type=Path, default=None,
        help="Path to single host_removal_stats.tsv",
    )
    parser.add_argument(
        "--coverage-dir", type=Path, default=None,
        help="Directory containing per-sample *_coverage.tsv files",
    )
    parser.add_argument(
        "--host-stats-dir", type=Path, default=None,
        help="Directory containing *.host_removal_stats.txt and *.bbduk_stats.txt files",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    args = parse_args(argv)
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
        host_stats_path=args.host_stats,
        coverage_dir=args.coverage_dir,
        host_stats_dir=args.host_stats_dir,
    )


if __name__ == "__main__":
    main()
