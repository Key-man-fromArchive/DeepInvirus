#!/usr/bin/env python3
# @TASK B1-B9 - Universal virome report framework (human-researcher-grade)
# @SPEC docs/planning/10-workplan-v2-report-framework.md#Phase-B
# @TEST tests/modules/test_report.py
"""Generate a Word (.docx) analysis report for DeepInvirus.

Reads pipeline output files (bigtable, sample-taxon matrix, diversity
tables, QC/assembly stats, per-sample coverage) and produces a formatted
Word document with data-driven, scientifically hedged conclusions.

Report structure (B1 redesign):
    0. Executive Summary
    1. Methods (auto-generated, no hardcoding)
    2. QC Results (waterfall table)
    3. Host Removal Statistics
    4. Virus Detection (stacked barplot, NOT pie chart)
    5. Per-sample Coverage Analysis
    6. Taxonomic Analysis (universal family descriptions)
    7. Diversity Analysis (conditional on n_samples)
    8. Conclusions (hedged, multi-hypothesis)
    9. Limitations (auto-generated)
    Appendix

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
# @TASK B4 - VIRUS_ORIGIN evidence-tier system
# @SPEC docs/planning/10-workplan-v2-report-framework.md#B4
# ---------------------------------------------------------------------------

VIRUS_ORIGIN: dict[str, dict] = {
    # --- Insect-infecting (high confidence) ---
    "Iflaviridae":      {"origin": "insect", "confidence": "high",
                         "note": "Iflavirus - insect picorna-like virus"},
    "Dicistroviridae":  {"origin": "insect", "confidence": "high"},
    "Baculoviridae":    {"origin": "insect", "confidence": "high"},
    "Sinhaliviridae":   {"origin": "insect", "confidence": "high"},
    "Nudiviridae":      {"origin": "insect", "confidence": "high"},
    "Iridoviridae":     {"origin": "insect", "confidence": "medium",
                         "note": "Some aquatic invertebrate hosts as well"},
    "Parvoviridae":     {"origin": "insect", "confidence": "medium",
                         "note": "Densovirinae only; Parvovirinae are vertebrate viruses"},
    # --- Multi-host (low confidence at family level) ---
    "Nodaviridae":      {"origin": "multi-host", "confidence": "low",
                         "note": "Alphanodavirus=insect, Betanodavirus=fish. Genus-level confirmation needed"},
    "Sedoreoviridae":   {"origin": "multi-host", "confidence": "low",
                         "note": "Cypovirus=insect, Orbivirus=vertebrate"},
    # --- Microbiome phage ---
    "Microviridae":     {"origin": "microbiome_phage", "confidence": "high"},
    "Fiersviridae":     {"origin": "microbiome_phage", "confidence": "medium"},
    # --- Fungal ---
    "Narnaviridae":     {"origin": "fungal", "confidence": "medium"},
    "Mitoviridae":      {"origin": "fungal", "confidence": "medium"},
    "Endornaviridae":   {"origin": "fungal", "confidence": "medium"},
    "Partitiviridae":   {"origin": "fungal_or_plant", "confidence": "low"},
    "Totiviridae":      {"origin": "fungal", "confidence": "medium"},
    # --- Plant ---
    "Bromoviridae":     {"origin": "plant", "confidence": "medium"},
    "Virgaviridae":     {"origin": "plant", "confidence": "medium"},
    # --- Cautious ---
    "Flaviviridae":     {"origin": "cautious", "confidence": "low",
                         "note": "ISF are insect-specific, but pathogenic flaviviruses also included"},
    "Genomoviridae":    {"origin": "cautious", "confidence": "low",
                         "note": "CRESS-DNA. Possibly environmental origin"},
    "Adintoviridae":    {"origin": "cautious", "confidence": "low",
                         "note": "Possible EVE. May be host-genome derived"},
}

# Class-level fallback (when family is unclassified)
VIRUS_ORIGIN_CLASS_FALLBACK: dict[str, dict] = {
    "Caudoviricetes": {"origin": "microbiome_phage", "confidence": "low",
                       "note": "Class-level only. Sub-family not classified"},
}


# ---------------------------------------------------------------------------
# @TASK B9 - Universal FAMILY_DESCRIPTIONS (no insect-specific language)
# @SPEC docs/planning/10-workplan-v2-report-framework.md#B9
# ---------------------------------------------------------------------------

FAMILY_DESCRIPTIONS: dict[str, str] = {
    "Parvoviridae": (
        "Single-stranded DNA viruses (ssDNA). This family includes the subfamily "
        "Densovirinae (densoviruses), which are known pathogens of invertebrates, "
        "as well as Parvovirinae that infect vertebrates. Densoviruses replicate "
        "in host cell nuclei and can cause host mortality."
    ),
    "Iflaviridae": (
        "Positive-sense single-stranded RNA viruses (+ssRNA) in the order "
        "Picornavirales. Members are known to infect arthropods, primarily insects, "
        "and can cause both acute and persistent infections."
    ),
    "Dicistroviridae": (
        "Positive-sense single-stranded RNA viruses (+ssRNA). Members include "
        "well-characterized insect viruses such as Cricket paralysis virus (CrPV) "
        "and Israeli acute paralysis virus (IAPV). They employ an internal ribosome "
        "entry site (IRES) for translation."
    ),
    "Sinhaliviridae": (
        "Positive-sense single-stranded RNA viruses in the order Nodamuvirales. "
        "A relatively recently classified family, primarily associated with "
        "invertebrate hosts."
    ),
    "Baculoviridae": (
        "Double-stranded DNA viruses (dsDNA). Major pathogens of Lepidoptera and "
        "other insect orders; they cause nuclear polyhedrosis disease. Widely used "
        "as biological pest control agents and as protein expression vectors."
    ),
    "Caudoviricetes": (
        "A class comprising tailed bacteriophages. These are among the most abundant "
        "biological entities in environmental samples and infect a wide range of "
        "bacteria. Their detection in metagenomic samples typically reflects the "
        "associated microbial community."
    ),
    "Flaviviridae": (
        "Positive-sense single-stranded RNA viruses. The family includes both "
        "arthropod-borne pathogenic viruses (e.g. Dengue, Zika) and insect-specific "
        "flaviviruses (ISFs) with no known vertebrate host. Classification to "
        "genus/species level is needed to assess pathogenic potential."
    ),
    "Bromoviridae": (
        "Positive-sense single-stranded RNA viruses. Primarily plant pathogens. "
        "Detection in non-plant samples may reflect dietary or environmental "
        "plant-derived RNA."
    ),
    "Narnaviridae": (
        "Positive-sense single-stranded RNA viruses that infect fungi. "
        "Narnaviruses are capsid-less and replicate within fungal cells. "
        "Their presence may reflect the associated fungal community."
    ),
    "Mitoviridae": (
        "Positive-sense single-stranded RNA viruses that replicate within fungal "
        "mitochondria. Detection may indicate the presence of infected fungi "
        "in the sample."
    ),
    "Endornaviridae": (
        "Double-stranded RNA viruses (dsRNA) that infect plants and fungi. "
        "Typically persistent and non-pathogenic to their hosts."
    ),
    "Virgaviridae": (
        "Positive-sense single-stranded RNA viruses. Major plant pathogens "
        "including Tobacco mosaic virus (TMV). Detection in non-plant samples "
        "may reflect environmental contamination or dietary exposure."
    ),
    "Fiersviridae": (
        "Positive-sense single-stranded RNA viruses. RNA phages that infect "
        "bacteria. Their detection reflects the associated bacterial community."
    ),
    "Adintoviridae": (
        "Double-stranded DNA viruses derived from Polinton-like elements. "
        "A relatively newly classified family; members may also be found "
        "integrated into eukaryotic host genomes (endogenous viral elements)."
    ),
    "Nudiviridae": (
        "Double-stranded DNA viruses (dsDNA) related to Baculoviridae. "
        "They infect a broad range of arthropods and do not form occlusion bodies."
    ),
    "Iridoviridae": (
        "Double-stranded DNA viruses (dsDNA). Members infect a wide range of "
        "invertebrates and ectothermic vertebrates, including insects and fish."
    ),
    "Microviridae": (
        "Single-stranded DNA viruses (ssDNA) that infect bacteria (phages). "
        "Among the smallest known DNA phages, they are ubiquitous in microbial "
        "communities."
    ),
    "Nodaviridae": (
        "Positive-sense single-stranded RNA viruses. The family contains two "
        "genera: Alphanodavirus (insect hosts) and Betanodavirus (fish hosts). "
        "Genus-level classification is essential for host attribution."
    ),
    "Sedoreoviridae": (
        "Double-stranded RNA viruses (dsRNA). A diverse family that includes "
        "Cypovirus (insect pathogens) and Orbivirus (arthropod-borne vertebrate "
        "pathogens). Host range is highly genus-dependent."
    ),
    "Totiviridae": (
        "Double-stranded RNA viruses (dsRNA) primarily infecting fungi and "
        "protozoa. They are typically non-pathogenic, persistent infections."
    ),
    "Partitiviridae": (
        "Double-stranded RNA viruses (dsRNA) with a broad host range including "
        "fungi and plants. They maintain persistent, typically asymptomatic infections."
    ),
    "Genomoviridae": (
        "Circular single-stranded DNA viruses (CRESS-DNA). Frequently recovered "
        "from environmental and metagenomic datasets. Host range is poorly "
        "characterized."
    ),
}


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
        sample_name = f.stem.replace("_coverage", "")
        try:
            df = pd.read_csv(f, sep="\t")
            cols = df.columns.tolist()
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


def _pick_first_nonempty(values: pd.Series, default: str = "") -> str:
    """Return the first non-empty string-like value from a Series."""
    for value in values:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return default


def _infer_classification_path(bigtable_path: Path) -> Path | None:
    """Infer coassembly_classified.tsv from a taxonomy/bigtable.tsv path."""
    bigtable_path = Path(bigtable_path)
    candidate = (
        bigtable_path.parent.parent / "classification" / "integration" / "coassembly_classified.tsv"
    )
    if candidate.exists():
        return candidate
    return None


def _load_classification_results(bigtable_path: Path) -> pd.DataFrame:
    """Load contig-level evidence integration results if present."""
    classified_path = _infer_classification_path(bigtable_path)
    if classified_path is None:
        logger.warning("Classification results not found adjacent to %s", bigtable_path)
        return pd.DataFrame()

    try:
        df = pd.read_csv(classified_path, sep="\t")
        logger.info("Loaded classification results from %s (%d rows)", classified_path, len(df))
        return df
    except Exception as exc:
        logger.warning("Failed to load classification results from %s: %s", classified_path, exc)
        return pd.DataFrame()


def _build_top_species_summary(bigtable: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """Summarize RPM by species when available, otherwise by genus."""
    required = {"seq_id", "sample", "rpm"}
    if bigtable.empty or not required.issubset(bigtable.columns):
        return pd.DataFrame()

    bt = bigtable.copy()
    bt["rpm"] = pd.to_numeric(bt["rpm"], errors="coerce").fillna(0)
    for col in ["species", "genus", "family"]:
        if col not in bt.columns:
            bt[col] = ""
        bt[col] = bt[col].fillna("").astype(str).str.strip()

    bt["group_key"] = np.where(
        bt["species"].ne(""),
        "species::" + bt["species"],
        np.where(
            bt["genus"].ne(""),
            "genus::" + bt["genus"],
            np.where(bt["family"].ne(""), "family::" + bt["family"], "unclassified::Unclassified"),
        ),
    )
    bt["group_species"] = np.where(
        bt["species"].ne(""),
        bt["species"],
        np.where(
            bt["genus"].ne(""),
            bt["genus"] + " (genus-level)",
            np.where(bt["family"].ne(""), bt["family"] + " (family-level)", "Unclassified"),
        ),
    )

    summary = (
        bt.groupby("group_key", dropna=False)
        .apply(
            lambda df: pd.Series(
                {
                    "Species": _pick_first_nonempty(df["group_species"], "Unclassified"),
                    "Genus": _pick_first_nonempty(df["genus"], "Unclassified"),
                    "Family": _pick_first_nonempty(df["family"], "Unclassified"),
                    "Total RPM": df["rpm"].sum(),
                    "N Contigs": df["seq_id"].nunique(),
                    "N Samples detected": df.loc[df["rpm"] > 0, "sample"].nunique(),
                }
            )
        )
        .reset_index(drop=True)
    )

    if summary.empty:
        return summary

    summary = summary.sort_values(["Total RPM", "N Contigs"], ascending=[False, False]).head(top_n)
    summary["Total RPM"] = summary["Total RPM"].map(lambda x: f"{x:,.2f}")
    return summary.reset_index(drop=True)


def _build_evidence_summary_table(classified_df: pd.DataFrame) -> pd.DataFrame:
    """Build summary counts for 4-tier evidence integration classes."""
    if classified_df.empty or "classification" not in classified_df.columns:
        return pd.DataFrame()

    ordered = ["strong_viral", "novel_viral_candidate", "ambiguous", "unknown"]
    counts = classified_df["classification"].fillna("unknown").value_counts()
    return pd.DataFrame(
        {
            "Classification": ordered,
            "Contig Count": [int(counts.get(name, 0)) for name in ordered],
        }
    )


def _build_top_strong_viral_table(
    classified_df: pd.DataFrame,
    bigtable: pd.DataFrame,
    top_n: int = 20,
) -> pd.DataFrame:
    """Build top strong_viral contig summary with taxonomy labels."""
    required = {"seq_id", "classification", "classification_score", "best_support_tier"}
    if classified_df.empty or not required.issubset(classified_df.columns):
        return pd.DataFrame()

    strong = classified_df[classified_df["classification"] == "strong_viral"].copy()
    if strong.empty:
        return pd.DataFrame()

    tax_cols = [c for c in ["seq_id", "species", "genus", "family"] if c in bigtable.columns]
    taxonomy = pd.DataFrame()
    if tax_cols:
        taxonomy = bigtable[tax_cols].drop_duplicates(subset=["seq_id"]).copy()
        for col in ["species", "genus", "family"]:
            if col not in taxonomy.columns:
                taxonomy[col] = ""
            taxonomy[col] = taxonomy[col].fillna("").astype(str).str.strip()
        taxonomy["species_label"] = np.where(
            taxonomy["species"].ne(""),
            taxonomy["species"],
            np.where(
                taxonomy["genus"].ne(""),
                taxonomy["genus"] + " (genus-level)",
                np.where(taxonomy["family"].ne(""), taxonomy["family"] + " (family-level)", "Unclassified"),
            ),
        )

    merged = strong.merge(
        taxonomy[["seq_id", "species_label"]] if not taxonomy.empty else pd.DataFrame(columns=["seq_id", "species_label"]),
        on="seq_id",
        how="left",
    )
    merged["species_label"] = merged["species_label"].fillna("Unclassified")
    merged["classification_score"] = pd.to_numeric(merged["classification_score"], errors="coerce").fillna(0)
    merged = merged.sort_values(
        ["classification_score", "best_support_tier", "seq_id"],
        ascending=[False, True, True],
    ).head(top_n)

    result = merged[["seq_id", "species_label", "classification_score", "best_support_tier"]].copy()
    result.columns = ["seq_id", "species", "evidence_score", "best_support_tier"]
    result["evidence_score"] = result["evidence_score"].map(lambda x: f"{x:.2f}")
    return result.reset_index(drop=True)


def _build_per_sample_coverage_table(
    bigtable: pd.DataFrame,
    coverage_data: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Build a contig x sample coverage pivot table.

    The bigtable contains per-sample rows (each contig duplicated once per
    sample).  This function pivots so that each contig appears exactly once
    with one coverage column per sample (<sample>_cov).

    When *coverage_data* (dict of external coverage TSVs) is provided,
    it is used as the coverage source.  Otherwise the bigtable's own
    ``coverage`` and ``sample`` columns are pivoted directly.

    Returns DataFrame with columns:
        contig, family, length, <sample1>_cov, <sample2>_cov, ...
    """
    if bigtable.empty:
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # 1. Unique contig info (deduplicated)
    # ------------------------------------------------------------------
    unique_bt = (
        bigtable
        .drop_duplicates(subset=["seq_id"])[["seq_id", "family", "length"]]
        .copy()
    )
    unique_bt = unique_bt.rename(columns={"seq_id": "contig"})

    # ------------------------------------------------------------------
    # 2a. External coverage files (original path)
    # ------------------------------------------------------------------
    if coverage_data:
        viral_contigs = unique_bt["contig"].tolist()
        result = unique_bt.copy()

        for sample_name, cov_df in sorted(coverage_data.items()):
            cov_subset = (
                cov_df[cov_df["Contig"].isin(viral_contigs)][["Contig", "mean_coverage"]]
                .copy()
            )
            cov_subset = cov_subset.rename(columns={
                "Contig": "contig",
                "mean_coverage": f"{sample_name}_cov",
            })
            result = result.merge(cov_subset, on="contig", how="left")

    # ------------------------------------------------------------------
    # 2b. Pivot from bigtable's own coverage + sample columns
    # ------------------------------------------------------------------
    elif "coverage" in bigtable.columns and "sample" in bigtable.columns:
        cov_pivot = (
            bigtable.pivot_table(
                index="seq_id",
                columns="sample",
                values="coverage",
                aggfunc="first",
            )
            .reset_index()
            .rename(columns={"seq_id": "contig"})
        )

        # Rename sample columns to *_cov
        rename_map = {
            col: f"{col}_cov"
            for col in cov_pivot.columns
            if col != "contig"
        }
        cov_pivot = cov_pivot.rename(columns=rename_map)

        result = unique_bt.merge(cov_pivot, on="contig", how="left")
    else:
        # No coverage information at all
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # 3. Fill NaN and sort by max coverage descending
    # ------------------------------------------------------------------
    cov_cols = [c for c in result.columns if c.endswith("_cov")]
    result[cov_cols] = result[cov_cols].fillna(0)

    if cov_cols:
        result["max_cov"] = result[cov_cols].max(axis=1)
        result = result.sort_values("max_cov", ascending=False)
        result = result.drop(columns=["max_cov"])

    return result


# ---------------------------------------------------------------------------
# @TASK B5 - Top virus auto-detection (breadth-weighted)
# @SPEC docs/planning/10-workplan-v2-report-framework.md#B5
# ---------------------------------------------------------------------------


def detect_top_virus(bigtable: pd.DataFrame) -> pd.Series | None:
    """Detect the top virus by coverage * log10(length) score.

    Returns the top row as a Series, or None if no classified virus found.
    """
    if bigtable.empty or "family" not in bigtable.columns:
        return None
    if "coverage" not in bigtable.columns:
        return None

    bt = bigtable[bigtable["family"] != "Unclassified"].copy()
    if bt.empty:
        return None

    bt["coverage"] = pd.to_numeric(bt["coverage"], errors="coerce").fillna(0)
    bt["length"] = pd.to_numeric(bt["length"], errors="coerce").fillna(0)
    bt["_score"] = bt["coverage"] * np.log10(bt["length"].clip(lower=1))
    if bt["_score"].max() <= 0:
        return None

    top = bt.nlargest(1, "_score").iloc[0]
    return top


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

    n_samples = len(samples)
    fig_width = max(8, n_samples * 1.5)
    fig, ax = plt.subplots(figsize=(fig_width, 5))
    x = np.arange(n_samples)
    width = 0.5

    ax.bar(x, host_pct, width, label="Host RNA (%)", color="#BDBDBD")
    ax.bar(x, nonhost_pct, width, bottom=host_pct,
           label="Non-host (viral + other) (%)", color="#1F77B4")

    # Dynamic annotation fontsize; skip annotation on narrow bars
    annot_fontsize = max(7, min(11, 120 // max(n_samples, 1)))
    for i, (h, nh) in enumerate(zip(host_pct, nonhost_pct)):
        if h > 8:  # only annotate if bar segment is wide enough to read
            ax.text(i, h / 2, f"{h:.1f}%", ha="center", va="center",
                    fontweight="bold", fontsize=annot_fontsize,
                    color="white" if h > 20 else "black")
        if nh > 8:
            ax.text(i, h + nh / 2, f"{nh:.1f}%", ha="center", va="center",
                    fontweight="bold", fontsize=annot_fontsize,
                    color="white" if nh > 20 else "black")

    ax.set_xlabel("Sample", fontsize=12)
    ax.set_ylabel("Proportion (%)", fontsize=12)
    ax.set_title("Host Mapping Rate Comparison", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    # Truncate long sample names and rotate if many samples
    sample_labels = [s[:20] + "..." if len(s) > 20 else s for s in samples]
    tick_fontsize = max(7, min(11, 150 // max(n_samples, 1)))
    if n_samples > 5:
        ax.set_xticklabels(sample_labels, fontsize=tick_fontsize,
                           rotation=45, ha="right")
    else:
        ax.set_xticklabels(sample_labels, fontsize=tick_fontsize)
    ax.set_ylim(0, 105)
    ax.legend(loc="upper right", fontsize=10)

    plt.tight_layout()
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

    plot_df = cov_table.head(top_n).copy()

    labels = []
    for _, row in plot_df.iterrows():
        family = row.get("family", "Unknown")
        contig = row.get("contig", "")
        raw_label = f"{family} ({contig})"
        # Truncate long labels to prevent y-axis overlap
        labels.append(raw_label[:30] + "..." if len(raw_label) > 30 else raw_label)

    matrix = plot_df[cov_cols].values
    matrix_log = np.log10(matrix + 1)

    sample_names = [c.replace("_cov", "") for c in cov_cols]
    # Truncate long sample names
    sample_labels = [s[:20] + "..." if len(s) > 20 else s for s in sample_names]

    n_items = len(labels)
    n_cols = len(cov_cols)
    fig_height = max(8, n_items * 0.4)
    fig_width = max(8, n_cols * 3)
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    im = ax.imshow(matrix_log, aspect="auto", cmap="YlOrRd")

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(sample_labels, fontsize=min(11, max(7, 120 // max(n_cols, 1))),
                       fontweight="bold")
    ax.set_yticks(range(n_items))
    # Scale y-tick fontsize inversely with item count
    ytick_fontsize = max(6, min(9, 300 // max(n_items, 1)))
    ax.set_yticklabels(labels, fontsize=ytick_fontsize)

    # Only add cell annotations if the number of items is manageable
    annot_fontsize = max(5, min(7, 200 // max(n_items, 1)))
    if n_items <= 40:
        for i in range(n_items):
            for j in range(n_cols):
                val = matrix[i, j]
                text_color = "white" if matrix_log[i, j] > matrix_log.max() * 0.6 else "black"
                if val >= 1000:
                    text = f"{val:.0f}"
                elif val >= 1:
                    text = f"{val:.1f}"
                else:
                    text = f"{val:.2f}" if val > 0 else "0"
                ax.text(j, i, text, ha="center", va="center",
                        fontsize=annot_fontsize, color=text_color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("log10(mean coverage + 1)", fontsize=10)

    ax.set_title("Per-sample Viral Contig Coverage", fontsize=14, fontweight="bold")
    ax.set_xlabel("Sample", fontsize=12)

    plt.tight_layout()
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

    counts = bigtable_df.drop_duplicates(subset=["seq_id"])["detection_method"].value_counts()
    fig, ax = plt.subplots(figsize=(max(8, len(counts) * 1.5), 6))
    colours = [DEEPINVIRUS_PALETTE[i % len(DEEPINVIRUS_PALETTE)] for i in range(len(counts))]
    counts.plot.bar(ax=ax, color=colours)
    ax.set_xlabel("Detection Method")
    ax.set_ylabel("Sequence Count")
    ax.set_title("Virus Detection by Method")
    # Rotate x-tick labels with proper alignment to prevent overlap
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")

    plt.tight_layout()
    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Detection bar chart saved to %s", output_path)
    return output_path


# @TASK B1 - Replaced pie chart with stacked barplot (C2)
def _plot_family_composition(bigtable: pd.DataFrame, output_path: Path) -> Path:
    """Generate a horizontal stacked barplot of virus family distribution.

    Replaces the previous pie chart per academic publication standards.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    if "family" not in bigtable.columns:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No family data available",
                ha="center", va="center", transform=ax.transAxes)
        fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(fig)
        return output_path

    family_counts = bigtable.drop_duplicates(subset=["seq_id"])["family"].value_counts()

    n_families = len(family_counts)
    fig_height = max(4, n_families * 0.5)
    fig, ax = plt.subplots(figsize=(10, fig_height))
    colors = [DEEPINVIRUS_PALETTE[i % len(DEEPINVIRUS_PALETTE)]
              for i in range(n_families)]

    y_pos = np.arange(n_families)
    ax.barh(y_pos, family_counts.values, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_yticks(y_pos)
    # Truncate long family names and scale fontsize
    family_labels = [str(f)[:25] + "..." if len(str(f)) > 25 else str(f)
                     for f in family_counts.index]
    ytick_fontsize = max(7, min(10, 200 // max(n_families, 1)))
    ax.set_yticklabels(family_labels, fontsize=ytick_fontsize)
    ax.invert_yaxis()

    # Annotate counts with scaled fontsize
    annot_fontsize = max(6, min(8, 150 // max(n_families, 1)))
    for i, (count, total) in enumerate(
        zip(family_counts.values, [family_counts.sum()] * n_families)
    ):
        pct = count / total * 100
        ax.text(count + 0.3, i, f"{count} ({pct:.1f}%)", va="center",
                fontsize=annot_fontsize)

    ax.set_xlabel("Contig Count", fontsize=12)
    ax.set_title("Virus Family Composition", fontsize=14, fontweight="bold")

    plt.tight_layout()
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
    n_samples = len(samples)
    x = np.arange(n_samples)
    width = 0.35

    fig_width = max(8, n_samples * 2)
    fig, ax = plt.subplots(figsize=(fig_width, 6))
    total_vals = df["total_reads"].values / 1e6
    clean_vals = df["clean_reads"].values / 1e6
    ax.bar(x - width/2, total_vals, width,
           label="Total reads (M)", color=DEEPINVIRUS_PALETTE[0])
    ax.bar(x + width/2, clean_vals, width,
           label="After adapter removal (M)", color=DEEPINVIRUS_PALETTE[2])

    ax.set_xlabel("Sample", fontsize=12)
    ax.set_ylabel("Read Count (millions)", fontsize=12)
    ax.set_title("BBDuk Adapter Removal", fontsize=14, fontweight="bold")
    ax.set_xticks(x)
    # Truncate long sample names and rotate if many samples
    sample_labels = [s[:20] + "..." if len(s) > 20 else s for s in samples]
    tick_fontsize = max(7, min(11, 150 // max(n_samples, 1)))
    if n_samples > 5:
        ax.set_xticklabels(sample_labels, fontsize=tick_fontsize,
                           rotation=45, ha="right")
    else:
        ax.set_xticklabels(sample_labels, fontsize=tick_fontsize)
    ax.legend(fontsize=10)

    # Place annotation above bars with dynamic offset to avoid overlap
    annot_fontsize = max(7, min(9, 120 // max(n_samples, 1)))
    y_max = max(total_vals.max(), clean_vals.max()) if len(total_vals) > 0 else 1
    offset = y_max * 0.03  # 3% of max height
    for i, row in df.iterrows():
        pct = row["adapter_pct"]
        ax.text(i + width/2, row["clean_reads"] / 1e6 + offset,
                f"-{pct:.1f}%", ha="center", fontsize=annot_fontsize, color="red")

    plt.tight_layout()
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

    plt.tight_layout()
    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("PCoA plot saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# @TASK B8 - QC waterfall table builder
# @SPEC docs/planning/10-workplan-v2-report-framework.md#B8
# ---------------------------------------------------------------------------


def _build_qc_waterfall(
    bbduk_stats: list[dict],
    host_stats: pd.DataFrame,
) -> pd.DataFrame:
    """Build a read-flow waterfall table.

    Columns: Sample | Raw Reads | After Adapter (-X.X%) | After Host (-XX.X%) | Final
    """
    if not bbduk_stats:
        return pd.DataFrame()

    rows = []
    for bstat in bbduk_stats:
        sample = bstat["sample"]
        raw = bstat["total_reads"]
        after_adapter = bstat["clean_reads"]
        adapter_loss_pct = bstat["adapter_pct"]

        # Find host removal stats for this sample
        after_host = after_adapter  # default if no host stats
        host_loss_pct = 0.0
        if not host_stats.empty and "sample" in host_stats.columns:
            match = host_stats[host_stats["sample"] == sample]
            if not match.empty:
                hr = match.iloc[0]
                if "unmapped_reads" in hr.index:
                    after_host = int(hr["unmapped_reads"])
                    if after_adapter > 0:
                        host_loss_pct = (1 - after_host / after_adapter) * 100

        rows.append({
            "Sample": sample,
            "Raw Reads": f"{raw:,}",
            "After Adapter": f"{after_adapter:,} (-{adapter_loss_pct:.1f}%)",
            "After Host Removal": f"{after_host:,} (-{host_loss_pct:.1f}%)",
            "Final": f"{after_host:,}",
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# @TASK B3 - Scientific interpretation engine (hedged, multi-hypothesis)
# @SPEC docs/planning/10-workplan-v2-report-framework.md#B3
# ---------------------------------------------------------------------------


def _generate_executive_summary(
    bigtable: pd.DataFrame,
    n_samples: int,
    sample_names: list[str],
    top_virus: pd.Series | None,
) -> list[str]:
    """Generate a concise executive summary (section 0).

    Returns a list of paragraph strings.
    """
    paragraphs = []
    n_contigs = bigtable["seq_id"].nunique()
    families = bigtable.drop_duplicates(subset=["seq_id"])["family"].value_counts() if "family" in bigtable.columns else pd.Series(dtype=int)
    n_families = len(families[families.index != "Unclassified"])

    # 3-line summary
    paragraphs.append(
        f"Co-assembly of {n_samples} sample(s) ({', '.join(sample_names) if sample_names else 'N/A'}) "
        f"yielded {n_contigs} viral contigs assigned to {n_families} classified viral families."
    )

    if top_virus is not None:
        tv_family = top_virus.get("family", "Unknown")
        tv_length = int(top_virus.get("length", 0))
        tv_cov = float(top_virus.get("coverage", 0))
        paragraphs.append(
            f"The highest-scoring viral contig belongs to {tv_family} "
            f"(length: {tv_length:,} bp, coverage: {tv_cov:.1f}x). "
            f"This contig represents the most prominent viral signal in the dataset."
        )

    if not families.empty:
        top3 = families[families.index != "Unclassified"].head(3)
        if not top3.empty:
            top_text = ", ".join([f"{name} ({count} contigs)" for name, count in top3.items()])
            paragraphs.append(
                f"The dominant viral families by contig count are: {top_text}."
            )

    return paragraphs


def _generate_conclusion(
    bigtable: pd.DataFrame,
    host_stats: pd.DataFrame,
    coverage_data: dict[str, pd.DataFrame],
    alpha: pd.DataFrame,
    sample_names: list[str],
    n_samples: int,
) -> list[str]:
    """Generate data-driven, scientifically hedged conclusion paragraphs (B3).

    All assertions use hedged language. No single-cause attribution.
    No "dead/alive sample" language without metadata.
    No Parvoviridae hardcoded highlight.
    """
    paragraphs = []

    n_contigs = bigtable["seq_id"].nunique()
    families = bigtable.drop_duplicates(subset=["seq_id"])["family"].value_counts() if "family" in bigtable.columns else pd.Series(dtype=int)
    classified_families = families[families.index != "Unclassified"]

    # --- Overview ---
    paragraphs.append(
        f"A total of {n_contigs} viral contigs were detected via co-assembly "
        f"of {n_samples} sample(s), encompassing {len(classified_families)} "
        f"classified viral families. These results provide an initial "
        f"characterization of the viral community associated with the samples."
    )

    # --- Host mapping interpretation (hedged, B3) ---
    if not host_stats.empty and len(host_stats) >= 2:
        low_sample = host_stats.loc[host_stats["host_removal_rate"].idxmin()]
        high_sample = host_stats.loc[host_stats["host_removal_rate"].idxmax()]

        paragraphs.append(
            f"Host mapping rates varied across samples: "
            f"{low_sample['sample']} ({low_sample['host_removal_rate']:.1f}%) "
            f"and {high_sample['sample']} ({high_sample['host_removal_rate']:.1f}%). "
            f"Such variation may be attributable to differences in sample RNA integrity, "
            f"library preparation quality, reference genome completeness, or biological "
            f"condition. Without additional sample metadata, a specific cause cannot "
            f"be determined."
        )

    # --- Key virus findings (auto-detected, not hardcoded) ---
    if not classified_families.empty:
        top3 = classified_families.head(3)
        top_text = ", ".join([f"{name} ({count} contigs)" for name, count in top3.items()])
        paragraphs.append(
            f"The most frequently detected viral families were {top_text}."
        )

    # --- Per-sample coverage insights ---
    has_cov_source = bool(coverage_data) or (
        "coverage" in bigtable.columns and "sample" in bigtable.columns
    )
    if has_cov_source and not bigtable.empty:
        cov_table = _build_per_sample_coverage_table(bigtable, coverage_data)
        cov_cols = [c for c in cov_table.columns if c.endswith("_cov")]

        if len(cov_cols) >= 2 and not cov_table.empty:
            for col in cov_cols:
                sample_name = col.replace("_cov", "")
                n_dominant = (cov_table[col] > 10).sum()
                paragraphs.append(
                    f"{sample_name}: {n_dominant} viral contigs with coverage > 10x."
                )

    # --- Diversity (hedged) ---
    if "shannon" in alpha.columns and not alpha.empty:
        mean_shannon = alpha["shannon"].mean()
        paragraphs.append(
            f"The mean Shannon diversity index was {mean_shannon:.3f}, "
            f"suggesting a {'moderate' if 1.0 <= mean_shannon <= 2.5 else 'limited' if mean_shannon < 1.0 else 'relatively high'} "
            f"level of viral diversity in the analyzed samples."
        )

    return paragraphs


# ---------------------------------------------------------------------------
# @TASK B7 - Automatic limitations generator
# @SPEC docs/planning/10-workplan-v2-report-framework.md#B7
# ---------------------------------------------------------------------------


def _generate_limitations(n_samples: int) -> list[str]:
    """Generate context-aware limitations paragraphs."""
    limitations = []

    if n_samples < 3:
        limitations.append(
            f"This analysis was performed on {n_samples} sample(s), which "
            f"limits statistical inference and diversity comparisons."
        )

    # RNA-seq caveat (always relevant for virome metatranscriptomics)
    limitations.append(
        "Detection of DNA viruses in RNA-seq data reflects viral transcripts "
        "rather than genomic DNA abundance. Viral load estimates for DNA viruses "
        "should be interpreted accordingly."
    )

    # Co-assembly caveat
    limitations.append(
        "Co-assembly improves genome recovery but may obscure sample-specific "
        "viral presence/absence. Per-sample read mapping was used to mitigate "
        "this limitation, although chimeric contigs cannot be entirely excluded."
    )

    # DB completeness
    limitations.append(
        "Taxonomic assignments depend on reference database completeness. "
        "A substantial proportion of viral 'dark matter' (uncharacterized viruses) "
        "may remain undetected or unclassified."
    )

    # Assembly-based
    limitations.append(
        "Assembly-based approaches can only recover viruses with sufficient "
        "read coverage. Low-abundance viruses may be missed entirely."
    )

    return limitations


# ---------------------------------------------------------------------------
# @TASK B6 - Conditional diversity section
# @SPEC docs/planning/10-workplan-v2-report-framework.md#B6
# ---------------------------------------------------------------------------


def _build_diversity_section(
    builder: ReportBuilder,
    alpha: pd.DataFrame,
    pcoa: pd.DataFrame,
    n_samples: int,
    alpha_fig_path: Path | None,
    pcoa_fig_path: Path | None,
    fig_counter: int,
    table_counter: int,
) -> tuple[int, int]:
    """Build the diversity analysis section conditionally based on n_samples.

    Returns updated (fig_counter, table_counter).
    """
    builder.add_heading("7. Diversity Analysis", level=1)

    if n_samples >= 3:
        # Full alpha + beta + PCoA
        builder.add_heading("7.1 Alpha Diversity", level=2)
        if alpha_fig_path:
            fig_counter += 1
            builder.add_figure(alpha_fig_path,
                             caption=f"Figure {fig_counter}. Alpha diversity metrics.",
                             width_inches=6.0)
        if not alpha.empty:
            table_counter += 1
            builder.add_table(alpha.copy(), title=f"Table {table_counter}. Alpha Diversity Metrics")

        builder.add_heading("7.2 Beta Diversity", level=2)
        if pcoa_fig_path:
            fig_counter += 1
            builder.add_figure(pcoa_fig_path,
                             caption=f"Figure {fig_counter}. PCoA ordination (Bray-Curtis).",
                             width_inches=6.0)
        else:
            builder.add_paragraph(
                "Beta diversity ordination requires 3 or more samples with "
                "sufficient variation. PCoA results were not available."
            )

    elif n_samples == 2:
        # Comparison mode
        builder.add_heading("7.1 Two-sample Comparison", level=2)
        builder.add_paragraph(
            "With only 2 samples, formal statistical tests (e.g., PERMANOVA) "
            "are not applicable. The following comparison is descriptive only."
        )
        if not alpha.empty:
            table_counter += 1
            builder.add_table(alpha.copy(), title=f"Table {table_counter}. Alpha Diversity Comparison (2 samples)")
        if alpha_fig_path:
            fig_counter += 1
            builder.add_figure(alpha_fig_path,
                             caption=f"Figure {fig_counter}. Alpha diversity comparison.",
                             width_inches=6.0)

    else:
        # Single sample profile
        builder.add_heading("7.1 Single-sample Viral Profile", level=2)
        builder.add_paragraph(
            "With a single sample, diversity comparisons are not applicable. "
            "The viral community profile is presented below."
        )
        if not alpha.empty:
            table_counter += 1
            builder.add_table(alpha.copy(), title=f"Table {table_counter}. Single-sample Diversity Metrics")

    return fig_counter, table_counter


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
    classified_df = _load_classification_results(bigtable_path)

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
        if "sample" in bigtable.columns:
            unique_samples = bigtable["sample"].dropna().unique().tolist()
            sample_names = [s for s in unique_samples if s.lower() != "coassembly"]
    n_samples = len(sample_names) if sample_names else 1

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
    bbduk_stats: list[dict] = []
    qc_dir = Path(host_stats_dir) if host_stats_dir else None
    if qc_dir:
        bbduk_stats = _load_bbduk_stats(qc_dir)

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
    species_summary = _build_top_species_summary(bigtable, top_n=20)
    evidence_summary = _build_evidence_summary_table(classified_df)
    strong_viral_table = _build_top_strong_viral_table(classified_df, bigtable, top_n=20)

    # ------------------------------------------------------------------
    # @TASK B5 - Detect top virus automatically
    # ------------------------------------------------------------------
    top_virus = detect_top_virus(bigtable)

    # ------------------------------------------------------------------
    # Generate figures
    # ------------------------------------------------------------------
    host_fig_path = _plot_host_mapping_comparison(
        host_stats, figures_dir / "host_mapping_comparison.png"
    )
    qc_fig_path = _plot_qc_barchart(bbduk_stats, figures_dir / "qc_bbduk_barchart.png")
    det_fig_path = _plot_detection_barchart(bigtable, figures_dir / "detection_barchart.png")
    # B1/C2: stacked barplot instead of pie chart
    family_fig_path = _plot_family_composition(bigtable, figures_dir / "family_composition.png")
    cov_heatmap_path = _plot_per_sample_coverage_heatmap(
        cov_table, figures_dir / "per_sample_coverage_heatmap.png"
    )

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
        logger.warning("Barplot generation failed: %s", e)

    try:
        heatmap_path = plot_heatmap(viz_matrix, figures_dir / "taxonomic_heatmap.png")
    except Exception as e:
        logger.warning("Heatmap generation failed: %s", e)

    try:
        alpha_fig_path = plot_alpha_diversity(alpha, figures_dir / "alpha_diversity.png")
    except Exception as e:
        logger.warning("Alpha diversity plot failed: %s", e)

    try:
        if not pcoa.empty:
            pcoa_fig_path = _plot_pcoa_from_coords(pcoa, figures_dir / "pcoa_plot.png")
    except Exception as e:
        logger.warning("PCoA plot failed: %s", e)

    # ------------------------------------------------------------------
    # Build report
    # ------------------------------------------------------------------
    builder = ReportBuilder()
    fig_counter = 0
    table_counter = 0

    # ================================================================
    # Table of Contents (with hyperlinks)
    # ================================================================
    builder.add_table_of_contents("Table of Contents")

    # ================================================================
    # 0. Executive Summary (B1 new section)
    # ================================================================
    builder.add_heading("0. Executive Summary", level=1)

    exec_paragraphs = _generate_executive_summary(
        bigtable, n_samples, sample_names, top_virus
    )
    for para in exec_paragraphs:
        builder.add_paragraph(para)

    # ================================================================
    # How to Use This Report (integrated from ANALYSIS_GUIDE.md)
    # ================================================================
    builder.add_heading("How to Use This Report", level=2)
    builder.add_paragraph(
        "This report is auto-generated by DeepInvirus and contains:"
    )
    builder.add_paragraph(
        "- Table of Contents (page 1): right-click -> Update Field for clickable links\n"
        "- Executive Summary: key findings at a glance\n"
        "- Interactive dashboard: open dashboard.html in a web browser for dynamic exploration\n"
        "- Raw data: taxonomy/bigtable.tsv for custom analysis in Excel/R/Python\n"
        "- Figures: figures/ directory contains PNG (300 DPI) and SVG (vector) versions"
    )
    builder.add_paragraph(
        "Detection Confidence Tiers: "
        "'high' = breadth >= 70% and depth >= 10x (strong evidence); "
        "'medium' = breadth >= 30% and depth >= 1x (moderate evidence, may need validation); "
        "'low' = below medium thresholds (weak evidence, possible artifact)."
    )

    # ================================================================
    # 1. Methods (B2 - auto-generated, no hardcoding)
    # ================================================================
    builder.add_heading("1. Methods", level=1)
    builder.add_heading("1.1 Project Information", level=2)

    table_counter += 1
    project_info = pd.DataFrame(
        {
            "Item": [
                "Analysis date",
                "Number of samples",
                "Sample names",
                "Assembly strategy",
                "Viral contigs detected",
                "Pipeline",
            ],
            "Value": [
                datetime.now().strftime("%Y-%m-%d"),
                str(n_samples),
                ", ".join(sample_names) if sample_names else "coassembly",
                "Co-assembly (pooled reads) + per-sample coverage mapping",
                str(bigtable["seq_id"].nunique()),
                "DeepInvirus v1.0",
            ],
        }
    )
    builder.add_table(project_info, title=f"Table {table_counter}. Project Information")

    # @TASK B2 - Methods auto-generated: minimap2 (NOT Bowtie2), scipy (NOT scikit-bio)
    builder.add_heading("1.2 Analysis Pipeline", level=2)
    builder.add_paragraph(
        "The DeepInvirus pipeline performs the following steps sequentially: "
        "(1) Adapter removal and quality control using BBDuk; "
        "(2) Host RNA removal using minimap2; "
        "(3) Co-assembly using MEGAHIT; "
        "(4) Viral sequence detection using geNomad and Diamond BLASTx; "
        "(5) Taxonomic classification using MMseqs2, followed by TaxonKit lineage "
        "reformatting to harmonize family, genus, and species labels; "
        "(6) Four-tier iterative evidence integration using Tier 1 amino acid search, "
        "Tier 2 amino acid search, Tier 3 nucleotide search, and Tier 4 nucleotide search; "
        "(7) Per-sample coverage quantification using CoverM; "
        "(8) Diversity analysis using scipy and numpy."
    )
    builder.add_paragraph(
        "Evidence integration results were classified as strong_viral, "
        "novel_viral_candidate, ambiguous, cellular, or unknown according to the "
        "combined support across geNomad, amino acid homology, and nucleotide homology. "
        "In this report, summary tables focus on the contigs retained in the viral "
        "bigtable and on the contig-level classification output from the 4-tier "
        "integration stage."
    )

    if sample_names and len(sample_names) >= 2:
        builder.add_paragraph(
            "A co-assembly strategy was employed, pooling reads from all samples "
            "for a single assembly. Individual sample reads were then mapped back "
            "to the co-assembly contigs to derive per-sample coverage profiles. "
            "This approach maximizes sensitivity for genome recovery while enabling "
            "quantitative cross-sample comparisons."
        )

    table_counter += 1
    params_table = pd.DataFrame(
        {
            "Parameter": [
                "Adapter removal",
                "Host removal",
                "Assembler",
                "Virus detection",
                "Taxonomy",
                "Evidence integration",
                "Coverage",
                "Diversity",
            ],
            "Value": [
                "BBDuk (Illumina adapters, PCR primers, PhiX)",
                "minimap2 (splice-aware mapping)",
                "MEGAHIT (co-assembly)",
                "geNomad + Diamond BLASTx",
                "MMseqs2 + TaxonKit lineage reformatting",
                "Tier 1 AA -> Tier 2 AA -> Tier 3 NT -> Tier 4 NT",
                "CoverM (mean, trimmed mean, covered bases)",
                "scipy + numpy (Shannon, Simpson, Bray-Curtis)",
            ],
        }
    )
    builder.add_table(params_table, title=f"Table {table_counter}. Analysis Parameters")

    # ================================================================
    # 2. QC Results (B8 - waterfall table)
    # ================================================================
    builder.add_heading("2. QC Results", level=1)

    builder.add_heading("2.1 Adapter Removal (BBDuk)", level=2)
    if bbduk_stats:
        bbduk_df = pd.DataFrame(bbduk_stats)
        display_df = bbduk_df[["sample", "total_reads", "adapter_removed", "adapter_pct", "phix_removed", "clean_reads"]].copy()
        display_df.columns = ["Sample", "Total Reads", "Adapter Removed", "Adapter %", "PhiX Removed", "Clean Reads"]
        for col in ["Total Reads", "Adapter Removed", "PhiX Removed", "Clean Reads"]:
            display_df[col] = display_df[col].apply(lambda x: f"{x:,}")
        display_df["Adapter %"] = display_df["Adapter %"].apply(lambda x: f"{x:.2f}%")
        table_counter += 1
        builder.add_table(display_df, title=f"Table {table_counter}. BBDuk Adapter Removal Statistics")

        if qc_fig_path:
            fig_counter += 1
            builder.add_figure(qc_fig_path,
                             caption=f"Figure {fig_counter}. BBDuk adapter removal statistics.",
                             width_inches=6.0)
    else:
        builder.add_paragraph("BBDuk statistics files were not provided.")

    # @TASK B8 - Read flow waterfall table
    builder.add_heading("2.2 Read Flow Waterfall", level=2)
    waterfall = _build_qc_waterfall(bbduk_stats, host_stats)
    if not waterfall.empty:
        table_counter += 1
        builder.add_table(waterfall, title=f"Table {table_counter}. Read Flow Waterfall")
    else:
        builder.add_paragraph("Insufficient data to build read flow waterfall table.")

    # ================================================================
    # 3. Host Removal Statistics
    # ================================================================
    builder.add_heading("3. Host Removal Statistics", level=1)
    if not host_stats.empty:
        host_display_formatted = pd.DataFrame({
            "Sample": host_stats["sample"],
            "Total Reads": host_stats["total_reads"].apply(lambda x: f"{x:,}"),
            "Host Mapped": host_stats["mapped_reads"].apply(lambda x: f"{x:,}"),
            "Non-host Reads": host_stats["unmapped_reads"].apply(lambda x: f"{x:,}"),
            "Host Mapping Rate (%)": host_stats["host_removal_rate"].apply(lambda x: f"{x:.2f}"),
        })
        table_counter += 1
        builder.add_table(host_display_formatted, title=f"Table {table_counter}. Host Removal Statistics")

        if host_fig_path:
            fig_counter += 1
            builder.add_figure(host_fig_path,
                             caption=f"Figure {fig_counter}. Host mapping rate comparison.",
                             width_inches=6.0)

        # @TASK B3 - Hedged interpretation (no dead/alive language)
        if len(host_stats) >= 2:
            low = host_stats.loc[host_stats["host_removal_rate"].idxmin()]
            high = host_stats.loc[host_stats["host_removal_rate"].idxmax()]
            builder.add_paragraph(
                f"Host mapping rates ranged from {low['host_removal_rate']:.1f}% "
                f"({low['sample']}) to {high['host_removal_rate']:.1f}% "
                f"({high['sample']}). Variation in host mapping rates may reflect "
                f"differences in RNA integrity, library quality, or biological "
                f"sample condition. Causal attribution requires additional metadata "
                f"and is not attempted here."
            )
    else:
        builder.add_paragraph("Host removal statistics were not provided.")

    # ================================================================
    # 4. Virus Detection
    # ================================================================
    builder.add_heading("4. Virus Detection", level=1)

    builder.add_heading("4.1 Detection Method Summary", level=2)
    if "detection_method" in bigtable.columns:
        det_summary = (
            bigtable.drop_duplicates(subset=["seq_id"])
            .groupby("detection_method")
            .agg(sequence_count=("seq_id", "count"))
            .reset_index()
        )
        table_counter += 1
        builder.add_table(det_summary, title=f"Table {table_counter}. Detection Method Summary")

    builder.add_paragraph(
        f"Co-assembly yielded {bigtable['seq_id'].nunique()} viral contigs. "
        f"Contig length range: {bigtable['length'].min():,} bp - {bigtable['length'].max():,} bp "
        f"(median: {bigtable['length'].median():,.0f} bp)."
    )

    if det_fig_path:
        fig_counter += 1
        builder.add_figure(det_fig_path,
                         caption=f"Figure {fig_counter}. Virus detection by method.",
                         width_inches=6.0)

    # 4.2 Family composition (stacked barplot, NOT pie chart - B1/C2)
    builder.add_heading("4.2 Virus Family Composition", level=2)
    if "family" in bigtable.columns:
        family_summary = bigtable.drop_duplicates(subset=["seq_id"])["family"].value_counts().reset_index()
        family_summary.columns = ["Family", "Contig Count"]
        table_counter += 1
        builder.add_table(family_summary, title=f"Table {table_counter}. Virus Family Distribution")

    if family_fig_path:
        fig_counter += 1
        builder.add_figure(family_fig_path,
                         caption=f"Figure {fig_counter}. Virus family composition (by contig count).",
                         width_inches=6.0)

    builder.add_heading("4.3 Top Viral Species", level=2)
    if not species_summary.empty:
        table_counter += 1
        builder.add_table(species_summary, title=f"Table {table_counter}. Top Viral Species by Total RPM")
    else:
        builder.add_paragraph("Species/genus summary could not be generated from the bigtable.")

    builder.add_heading("4.4 Evidence Integration Summary", level=2)
    builder.add_paragraph(
        "Contigs were evaluated using the iterative 4-tier evidence integration workflow: "
        "Tier 1 AA, Tier 2 AA, Tier 3 NT, and Tier 4 NT. The contig-level results below "
        "summarize the final evidence classes from the integration output."
    )
    if not evidence_summary.empty:
        table_counter += 1
        builder.add_table(evidence_summary, title=f"Table {table_counter}. Evidence Integration Classification Summary")
    else:
        builder.add_paragraph("Evidence integration classification output was not found.")

    if not strong_viral_table.empty:
        table_counter += 1
        builder.add_table(strong_viral_table, title=f"Table {table_counter}. Top strong_viral Contigs")
    elif not classified_df.empty:
        builder.add_paragraph("No strong_viral contigs were present in the classification output.")

    # ================================================================
    # 5. Per-sample Coverage Analysis
    # ================================================================
    builder.add_heading("5. Per-sample Coverage Analysis", level=1)
    if not cov_table.empty:
        cov_cols = [c for c in cov_table.columns if c.endswith("_cov")]
        if cov_cols:
            display_cov = cov_table.head(20).copy()
            for col in cov_cols:
                display_cov[col] = display_cov[col].apply(
                    lambda x: f"{x:,.1f}" if x >= 1 else (f"{x:.2f}" if x > 0 else "0")
                )
            display_cov.columns = [c.replace("_cov", " Coverage") if c.endswith("_cov") else c
                                   for c in display_cov.columns]
            table_counter += 1
            builder.add_table(display_cov, title=f"Table {table_counter}. Per-sample Viral Contig Coverage (Top 20)")

            builder.add_paragraph(
                "Coverage values represent the mean read depth when mapping each "
                "sample's reads to the co-assembly contigs. Higher coverage indicates "
                "greater nucleic acid abundance of the corresponding viral sequence "
                "in that sample."
            )

        if cov_heatmap_path:
            fig_counter += 1
            builder.add_figure(cov_heatmap_path,
                             caption=f"Figure {fig_counter}. Per-sample viral contig coverage heatmap (log10 scale).",
                             width_inches=6.5)
    else:
        builder.add_paragraph(
            "Per-sample coverage data was not provided. "
            "Use --coverage-dir to supply per-sample coverage files."
        )

    # ================================================================
    # 6. Taxonomic Analysis (B9 - universal descriptions)
    # ================================================================
    builder.add_heading("6. Taxonomic Analysis", level=1)

    builder.add_heading("6.1 Community Composition", level=2)
    if barplot_path:
        fig_counter += 1
        builder.add_figure(barplot_path,
                         caption=f"Figure {fig_counter}. Viral community composition (relative abundance).",
                         width_inches=6.0)

    builder.add_heading("6.2 Taxonomic Heatmap", level=2)
    if heatmap_path:
        fig_counter += 1
        builder.add_figure(heatmap_path,
                         caption=f"Figure {fig_counter}. Taxonomic heatmap (log10 RPM+1).",
                         width_inches=6.0)

    # 6.3 Family descriptions (B9 - universalized)
    builder.add_heading("6.3 Virus Family Descriptions", level=2)
    if "family" in bigtable.columns:
        _unique_bt = bigtable.drop_duplicates(subset=["seq_id"])
        classified = _unique_bt[_unique_bt["family"] != "Unclassified"]["family"].value_counts()
        for idx, (family_name, count) in enumerate(classified.items()):
            builder.add_heading(f"6.3.{idx+1} {family_name} ({count} contigs)", level=3)

            description = FAMILY_DESCRIPTIONS.get(
                family_name,
                f"No detailed description is currently available for {family_name}."
            )
            builder.add_paragraph(description)

            # Virus origin context (B4)
            origin_info = VIRUS_ORIGIN.get(family_name)
            if origin_info:
                origin_text = (
                    f"Probable origin: {origin_info['origin']} "
                    f"(confidence: {origin_info['confidence']})."
                )
                if origin_info.get("note"):
                    origin_text += f" Note: {origin_info['note']}."
                builder.add_paragraph(origin_text)
            else:
                # Check class-level fallback
                if "class" in bigtable.columns:
                    family_rows = bigtable[bigtable["family"] == family_name]
                    classes = family_rows["class"].dropna().unique()
                    for cls in classes:
                        cls_info = VIRUS_ORIGIN_CLASS_FALLBACK.get(cls)
                        if cls_info:
                            builder.add_paragraph(
                                f"Class-level origin ({cls}): {cls_info['origin']} "
                                f"(confidence: {cls_info['confidence']}). "
                                f"{cls_info.get('note', '')}"
                            )

            # Per-family coverage table
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

    # ================================================================
    # 7. Diversity Analysis (B6 - conditional on n_samples)
    # ================================================================
    fig_counter, table_counter = _build_diversity_section(
        builder, alpha, pcoa, n_samples,
        alpha_fig_path, pcoa_fig_path,
        fig_counter, table_counter,
    )

    # ================================================================
    # 8. Conclusions (B3 - hedged, multi-hypothesis)
    # ================================================================
    builder.add_heading("8. Conclusions", level=1)

    conclusion_paragraphs = _generate_conclusion(
        bigtable, host_stats, coverage_data, alpha, sample_names, n_samples
    )
    for para in conclusion_paragraphs:
        builder.add_paragraph(para)

    # ================================================================
    # 9. Limitations (B7 - auto-generated)
    # ================================================================
    builder.add_heading("9. Limitations", level=1)

    limitations = _generate_limitations(n_samples)
    for lim in limitations:
        builder.add_paragraph(lim)

    # ================================================================
    # Appendix
    # ================================================================
    builder.add_heading("Appendix", level=1)

    builder.add_heading("A. Complete Viral Contig List", level=2)
    builder.add_paragraph(
        "The complete viral contig list with all classification and coverage data "
        "is available in the output file: taxonomy/bigtable.tsv"
    )
    builder.add_paragraph(
        "This TSV file contains columns including seq_id, sample, family, "
        "coverage, breadth, detection_confidence, and RPM for each contig x sample "
        "combination. Open in Excel, R, or Python for custom analysis."
    )
    builder.add_paragraph(
        f"Total: {bigtable['seq_id'].nunique()} unique contigs across "
        f"{bigtable['sample'].nunique() if 'sample' in bigtable.columns else 'N/A'} samples."
    )

    builder.add_heading("B. Software Versions", level=2)
    versions = pd.DataFrame(
        {
            "Software": [
                "DeepInvirus",
                "Nextflow",
                "Python",
                "BBDuk (BBTools)",
                "minimap2",
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
                "2.24+",
                "1.2+",
                "1.7+",
                "2.1+",
                "15+",
                "0.7+",
            ],
        }
    )
    builder.add_table(versions, title="Table B1. Software Versions")

    # ---- Appendix C: Parameter Dictionary ----
    builder.add_heading("C. Parameter Dictionary", level=2)

    param_data = pd.DataFrame({
        "Parameter": [
            "--reads", "--host", "--outdir", "--trimmer", "--assembler",
            "--search", "--skip_ml", "--db_dir", "--checkv_db",
            "--min_contig_len", "--min_virus_score", "--min_bitscore",
        ],
        "Type": [
            "string", "string", "string", "string", "string",
            "string", "boolean", "string", "string",
            "integer", "float", "integer",
        ],
        "Default": [
            "(required)", "none", "./results", "bbduk", "megahit",
            "sensitive", "false", "auto-download", "null (skip)",
            "500", "0.7", "50",
        ],
        "Description": [
            "Path to paired FASTQ files (glob pattern, e.g. '/data/*_R{1,2}.fastq.gz')",
            "Host genome(s) for read removal. Comma-separated: tmol,zmor,human. 'none' = skip.",
            "Output directory path",
            "Read trimming tool: bbduk or fastp",
            "De novo assembler: megahit or metaspades",
            "Diamond search sensitivity: fast or sensitive",
            "Skip ML-based virus detection (geNomad). Diamond-only mode.",
            "Custom database directory. Auto-downloads if not provided.",
            "CheckV database path. Genome quality assessment skipped if null.",
            "Minimum contig length (bp) for assembly output",
            "Minimum geNomad virus score threshold (0-1)",
            "Minimum Diamond bitscore filter",
        ],
    })
    builder.add_table(param_data, title="Table C1. Pipeline Parameters")
    builder.add_paragraph(
        "This information is also available in the output folder's "
        "ANALYSIS_GUIDE.md and README.md files."
    )

    # ---- Appendix D: Results Dictionary ----
    builder.add_heading("D. Results Dictionary", level=2)

    builder.add_heading("D.1 Output Directory Structure", level=3)
    output_structure = pd.DataFrame({
        "Path": [
            "qc/multiqc_report.html",
            "qc/*.bbduk_stats.txt",
            "qc/fastqc/",
            "qc/*.host_removal_stats.txt",
            "assembly/contigs.fa",
            "assembly/assembly_stats.tsv",
            "detection/genomad/",
            "detection/diamond/",
            "detection/checkv/ (optional)",
            "taxonomy/bigtable.tsv",
            "taxonomy/sample_taxon_matrix.tsv",
            "taxonomy/sample_counts.tsv",
            "coverage/*_coverage.tsv",
            "diversity/alpha_diversity.tsv",
            "diversity/beta_diversity.tsv",
            "diversity/pcoa_coordinates.tsv",
            "figures/ (PNG + SVG)",
            "dashboard.html",
            "report.docx",
        ],
        "Description": [
            "MultiQC aggregate QC report",
            "BBDuk adapter removal statistics per sample",
            "FastQC reports (raw + trimmed reads)",
            "Host mapping statistics per sample",
            "Assembled contigs (≥500bp, co-assembly)",
            "Assembly statistics: N50, total length, contig count",
            "geNomad ML-based virus detection results",
            "Diamond BLASTx homology search results",
            "CheckV genome completeness/contamination (when --checkv_db provided)",
            "Master results table (all info merged, see D.2)",
            "Family × Sample RPM abundance matrix for diversity analysis",
            "Per-sample per-taxon read counts",
            "CoverM per-sample read coverage (depth + breadth)",
            "Alpha diversity: Shannon, Simpson, Chao1, Pielou evenness",
            "Bray-Curtis pairwise distance matrix",
            "PCoA ordination coordinates (PC1, PC2)",
            "Publication-quality figures in PNG (300 DPI) and SVG (vector)",
            "Interactive Plotly HTML dashboard (offline-capable)",
            "This automated Word report",
        ],
    })
    builder.add_table(output_structure, title="Table D1. Output File Structure")

    builder.add_heading("D.2 bigtable.tsv Column Dictionary", level=3)
    bigtable_dict = pd.DataFrame({
        "Column": [
            "seq_id", "sample", "length",
            "detection_method", "detection_score",
            "family", "coverage", "breadth",
            "detection_confidence", "rpm", "count",
            "taxid", "domain", "phylum", "class", "order",
            "genus", "species",
            "evidence_classification", "evidence_score", "evidence_support_tier",
            "ictv_classification", "baltimore_group",
        ],
        "Type": [
            "string", "string", "integer",
            "string", "float (0-1)",
            "string", "float", "float (%)",
            "string", "float", "integer",
            "integer", "string", "string", "string", "string",
            "string", "string",
            "string", "float", "string",
            "string", "string",
        ],
        "Description": [
            "Contig identifier from co-assembly",
            "Sample name (from read filename)",
            "Contig length in base pairs",
            "Detection method: genomad, diamond, or both",
            "Detection confidence score (normalized 0-1)",
            "Virus family (e.g. Parvoviridae, Iflaviridae)",
            "Mean read depth (CoverM, per sample)",
            "Genome coverage breadth (% of bases with ≥1x coverage)",
            "Detection tier: high (breadth≥70%, depth≥10x), medium, low",
            "Coverage-normalized relative abundance (contig coverage / total sample coverage * 1e6)",
            "Raw mapped read count",
            "NCBI taxonomy ID",
            "Taxonomic domain (e.g. Viruses)",
            "Taxonomic phylum",
            "Taxonomic class (e.g. Caudoviricetes)",
            "Taxonomic order",
            "Taxonomic genus",
            "Taxonomic species",
            "Final 4-tier evidence class assigned in the merged viral bigtable",
            "Evidence integration score carried into the merged viral bigtable",
            "Best supporting tier from evidence integration (e.g. aa1, genomad_only)",
            "ICTV official classification",
            "Baltimore classification group (e.g. Group I-VII)",
        ],
    })
    builder.add_table(bigtable_dict, title="Table D2. bigtable.tsv Column Dictionary")

    builder.add_heading("D.3 VIRUS_ORIGIN Classification System", level=3)
    origin_data = []
    for family_name, info in VIRUS_ORIGIN.items():
        origin_data.append({
            "Family": family_name,
            "Origin": info["origin"],
            "Confidence": info["confidence"],
            "Note": info.get("note", ""),
        })
    for class_name, info in VIRUS_ORIGIN_CLASS_FALLBACK.items():
        origin_data.append({
            "Family": f"{class_name} (class-level)",
            "Origin": info["origin"],
            "Confidence": info["confidence"],
            "Note": info.get("note", ""),
        })
    if origin_data:
        builder.add_table(
            pd.DataFrame(origin_data),
            title="Table D3. Virus Origin Classification (Evidence-Tier System)"
        )
    builder.add_paragraph(
        "Confidence tiers: high = well-established host association; "
        "medium = generally accepted but exceptions exist; "
        "low = family-level assignment insufficient, genus-level resolution recommended; "
        "none = family spans multiple host kingdoms, classification not possible at this level."
    )

    builder.add_heading("D.4 Report Auto-generation", level=3)
    report_sections = pd.DataFrame({
        "Section": [
            "Executive Summary", "Methods", "QC Results",
            "Host Removal", "Virus Detection", "Coverage Analysis",
            "Evidence Integration",
            "Taxonomic Analysis", "Diversity", "Conclusions", "Limitations",
        ],
        "Content": [
            "Key findings (top virus, contig count, family count)",
            "Tools, versions, parameters (from pipeline metadata)",
            "Read counts, adapter removal rates, quality metrics",
            "Host mapping rates per sample (descriptive, no causal inference)",
            "Detection methods, family distribution, confidence tiers",
            "Per-sample heatmap (log10 RPKM), breadth-weighted top contigs",
            "Top species/genus RPM summary and 4-tier evidence integration tables",
            "Family descriptions, VIRUS_ORIGIN evidence-tier classification",
            "Conditional: n≥3 full diversity, n=2 fold-change, n=1 profile",
            "Data-driven, scientifically hedged (no overclaiming)",
            "Sample size, RNA-seq caveats, co-assembly limits, DB completeness",
        ],
        "Auto-generated": [
            "Yes", "Yes", "Yes", "Yes", "Yes",
            "Yes", "Yes", "Yes", "Yes (conditional)", "Yes", "Yes",
        ],
    })
    builder.add_table(report_sections, title="Table D4. Report Sections")
    builder.add_paragraph(
        "This information is also available in the output folder's "
        "ANALYSIS_GUIDE.md and README.md files."
    )

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    result = builder.save(output_path)
    logger.info("Report generated: %s", result)

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
