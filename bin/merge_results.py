#!/usr/bin/env python3
"""Merge co-assembly classification results into a unified bigtable.

# @TASK A1+A2 - Co-assembly aware merge + RPM abundance model
# @SPEC docs/planning/10-workplan-v2-report-framework.md#Phase-A

Co-assembly pipeline: detection/taxonomy run once on co-assembled contigs,
while coverage is computed per-sample. This script creates one bigtable row
per seq_id per sample using coverage rows and computes a coverage-based
relative abundance metric (contig_depth / sum(depths) * 1e6; labelled
'rpm' for column compatibility but NOT read-count RPM).

Usage:
    python merge_results.py \\
        --taxonomy coassembly_taxonomy.tsv \\
        --lineage coassembly_lineage.tsv \\
        --coverage GC_Tm_coverage.tsv Inf_NB_Tm_coverage.tsv \\
        --detection coassembly_merged_detection.tsv \\
        --sample-map sample_map.tsv \\
        --ictv ictv_vmr.tsv \\
        --out-bigtable bigtable.tsv \\
        --out-matrix sample_taxon_matrix.tsv \\
        --out-counts sample_counts.tsv

Outputs:
    - bigtable.tsv:           one row per seq_id per sample with coverage, breadth, RPM
    - sample_taxon_matrix.tsv: taxon x sample RPM abundance matrix (taxon, taxid, rank + samples)
    - sample_counts.tsv:       per-sample per-taxon count summary
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Filename -> sample name extraction
# ---------------------------------------------------------------------------

_SUFFIX_PATTERNS = [
    r"_merged_detection\.tsv$",
    r"_taxonomy\.tsv$",
    r"_lineage\.tsv$",
    r"_coverage\.tsv$",
]


def extract_sample_name(filepath: str | Path) -> str:
    """Extract sample name from a per-sample filename."""
    name = Path(filepath).name
    for pat in _SUFFIX_PATTERNS:
        m = re.search(pat, name)
        if m:
            return name[: m.start()]
    return name.removesuffix(".tsv")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merge classification results into bigtable.")
    p.add_argument("--taxonomy", nargs="+", type=Path, required=True)
    p.add_argument("--lineage", nargs="+", type=Path, required=True)
    p.add_argument("--coverage", nargs="+", type=Path, required=True)
    p.add_argument("--detection", nargs="+", type=Path, required=True)
    p.add_argument("--sample-map", type=Path, required=True)
    p.add_argument("--ictv", type=Path, required=True)
    p.add_argument("--out-bigtable", type=Path, required=True)
    p.add_argument("--out-matrix", type=Path, required=True)
    p.add_argument("--out-counts", type=Path, required=True)
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_detection_files(paths: list[Path]) -> pd.DataFrame:
    """Load detection files. Returns contig-level data (no per-sample split)."""
    frames = []
    for p in paths:
        try:
            df = pd.read_csv(p, sep="\t", dtype=str)
        except pd.errors.EmptyDataError:
            continue
        df.columns = df.columns.str.strip()
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=[
            "seq_id", "length", "detection_method", "detection_score",
            "taxonomy", "taxid", "subject_id",
        ])
    result = pd.concat(frames, ignore_index=True)
    # Deduplicate on seq_id (co-assembly produces one detection per contig)
    result = result.drop_duplicates(subset=["seq_id"], keep="first")
    return result


def load_taxonomy_files(paths: list[Path]) -> pd.DataFrame:
    """Load MMseqs2 taxonomy. Returns contig-level best hit."""
    frames = []
    for p in paths:
        try:
            df = pd.read_csv(p, sep="\t", dtype=str)
        except pd.errors.EmptyDataError:
            continue
        df.columns = df.columns.str.strip()
        if "query" in df.columns:
            df = df.rename(columns={"query": "seq_id"})
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["seq_id", "target", "pident", "evalue", "bitscore"])
    result = pd.concat(frames, ignore_index=True)
    # Best hit per seq_id
    if "bitscore" in result.columns:
        result["bitscore"] = pd.to_numeric(result["bitscore"], errors="coerce").fillna(0)
        result = result.sort_values("bitscore", ascending=False).drop_duplicates(
            subset=["seq_id"], keep="first"
        )
    else:
        result = result.drop_duplicates(subset=["seq_id"], keep="first")
    return result


def load_coverage_files(paths: list[Path]) -> pd.DataFrame:
    """Load per-sample CoverM coverage. Returns long-format with sample column.

    CoverM columns: 0=Contig, 1=Mean, 2=Trimmed Mean, 3=Covered Bases, 4=Length
    """
    frames = []
    for p in paths:
        sample = extract_sample_name(p)
        try:
            df = pd.read_csv(p, sep="\t")
        except pd.errors.EmptyDataError:
            continue
        if len(df.columns) < 2:
            continue
        cov = pd.DataFrame({
            "seq_id": df.iloc[:, 0].astype(str),
            "coverage": pd.to_numeric(df.iloc[:, 1], errors="coerce").fillna(0.0),
        })
        # Breadth: covered_bases / length
        if len(df.columns) >= 5:
            covered = pd.to_numeric(df.iloc[:, 3], errors="coerce").fillna(0.0)
            length = pd.to_numeric(df.iloc[:, 4], errors="coerce").fillna(0.0)
            cov["breadth"] = (covered / length.replace(0, float("nan"))).fillna(0.0)
        else:
            cov["breadth"] = 0.0
        cov["sample"] = sample
        frames.append(cov)
    if not frames:
        return pd.DataFrame(columns=["seq_id", "coverage", "breadth", "sample"])
    return pd.concat(frames, ignore_index=True)


def load_lineage_files(paths: list[Path]) -> pd.DataFrame:
    """Load TaxonKit lineage files. Returns contig-level taxonomy ranks."""
    frames = []
    for p in paths:
        try:
            df = pd.read_csv(p, sep="\t", dtype=str)
        except pd.errors.EmptyDataError:
            continue
        df.columns = df.columns.str.strip()
        if "taxid" in df.columns and "domain" in df.columns and len(df) > 0:
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=[
            "taxid", "lineage", "domain", "phylum", "class",
            "order", "family", "genus", "species",
        ])
    result = pd.concat(frames, ignore_index=True)
    # Need seq_id for joining; check if 'query' or 'seq_id' column exists
    if "query" in result.columns and "seq_id" not in result.columns:
        result = result.rename(columns={"query": "seq_id"})
    return result


def load_sample_map(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, sep="\t", dtype=str)
        df.columns = df.columns.str.strip()
        keep = [c for c in ["sample", "group"] if c in df.columns]
        if keep:
            return df[keep].drop_duplicates(subset=["sample"], keep="first")
    except Exception:
        pass
    return pd.DataFrame(columns=["sample", "group"])


def load_ictv(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, sep="\t", dtype=str)
        df.columns = df.columns.str.strip()
        if len(df) > 0:
            return df
    except Exception:
        pass
    return pd.DataFrame(columns=["family", "genus", "species", "baltimore_group", "ictv_classification"])


# ---------------------------------------------------------------------------
# Helper: extract family from taxonomy string
# ---------------------------------------------------------------------------

def parse_taxonomy_string_to_ranks(tax_str: str) -> dict:
    """Parse geNomad/ICTV semicolon-separated taxonomy into rank columns.

    # @TASK A2-fix - Fallback lineage parsing from detection taxonomy
    # @SPEC docs/planning/10-workplan-v2-report-framework.md#Phase-A

    geNomad ICTV format (7 fields):
        Domain(0); Kingdom(1); Realm(2); Phylum(3); Class(4); Order(5); Family(6)
    Example:
        Viruses; Riboviria; Orthornavirae; Kitrinoviricota; Flasuviricetes; Amarillovirales; Flaviviridae
        0=Viruses  1=Riboviria  2=Orthornavirae  3=Kitrinoviricota  4=Flasuviricetes  5=Amarillovirales  6=Flaviviridae
    """
    ranks = {"domain": "", "phylum": "", "class": "", "order": "", "genus": "", "species": ""}
    if not isinstance(tax_str, str) or tax_str.strip() == "":
        return ranks
    parts = [x.strip() for x in tax_str.split(";")]
    if len(parts) > 0:
        ranks["domain"] = parts[0]        # Viruses
    if len(parts) > 3:
        ranks["phylum"] = parts[3]        # e.g. Kitrinoviricota
    if len(parts) > 4:
        ranks["class"] = parts[4]         # e.g. Flasuviricetes
    if len(parts) > 5:
        ranks["order"] = parts[5]         # e.g. Amarillovirales
    # Family (index 6) is extracted separately by extract_family_from_lineage_str
    # genus/species are not in geNomad output at this level
    return ranks


def extract_family_from_lineage_str(tax_str: str) -> str:
    """Extract family-level name from semicolon-separated taxonomy string."""
    if not isinstance(tax_str, str) or tax_str.strip() == "":
        return "Unclassified"
    parts = [x.strip() for x in tax_str.split(";")]
    for part in parts:
        if part.lower().endswith("viridae"):
            return part
    # If no family-level token found, return "Unclassified"
    # (do NOT fall back to class/order/phylum names)
    return "Unclassified"


def compute_detection_confidence(depth: float, breadth: float) -> str:
    breadth_pct = breadth * 100 if breadth <= 1.0 else breadth
    if breadth_pct >= 70 and depth >= 10:
        return "high"
    elif breadth_pct >= 30 and depth >= 1:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Build outputs
# ---------------------------------------------------------------------------

def build_bigtable(
    detection: pd.DataFrame,
    taxonomy: pd.DataFrame,  # NOTE: MMseqs2 best-hit; kept for API compat but lineage already provides ranks
    coverage: pd.DataFrame,
    lineage: pd.DataFrame,
    sample_map: pd.DataFrame,
    ictv: pd.DataFrame,
) -> pd.DataFrame:
    """Build the master bigtable with one row per seq_id per sample.

    Strategy:
    1. Start from detection results (one row per seq_id).
    2. Expand to per-sample rows from coverage data.
    3. Merge taxonomy and lineage for rank columns.
    4. Merge ICTV for classification/baltimore group.
    5. Attach sample metadata from sample_map (sample -> group).
    6. Compute relative abundance: contig_depth / sum(depths) * 1e6
       (coverage-based, not read-count RPM).
    """
    # --- Contig-level base from detection ---
    bt = detection.copy()
    bt["length"] = pd.to_numeric(bt.get("length", 0), errors="coerce").fillna(0).astype(int)
    bt["detection_score"] = pd.to_numeric(bt.get("detection_score", 0), errors="coerce")
    bt["seq_id"] = bt["seq_id"].astype(str)

    # Extract family from detection taxonomy string
    if "taxonomy" in bt.columns:
        bt["family"] = bt["taxonomy"].apply(extract_family_from_lineage_str)
    else:
        bt["family"] = "Unclassified"
        bt["taxonomy"] = ""

    # --- Merge lineage (contig-level, seq_id or taxid) ---
    rank_cols = ["domain", "phylum", "class", "order", "genus", "species"]
    if not lineage.empty and "seq_id" in lineage.columns:
        lin_cols = ["seq_id"] + [c for c in rank_cols if c in lineage.columns]
        if "taxid" in lineage.columns:
            lin_cols.append("taxid")
        lin = lineage[lin_cols].drop_duplicates(subset=["seq_id"], keep="first")
        bt = bt.merge(lin, on="seq_id", how="left", suffixes=("", "_lin"))
        # Prefer lineage values over detection values
        for col in rank_cols:
            if f"{col}_lin" in bt.columns:
                bt[col] = bt[f"{col}_lin"].fillna(bt.get(col, pd.NA))
                bt = bt.drop(columns=[f"{col}_lin"])
    elif not lineage.empty and "taxid" in lineage.columns and "taxid" in bt.columns:
        lin_cols = ["taxid"] + [c for c in rank_cols if c in lineage.columns]
        lin = lineage[lin_cols].drop_duplicates(subset=["taxid"], keep="first")
        bt = bt.merge(lin, on="taxid", how="left", suffixes=("", "_lin"))
        for col in rank_cols:
            if f"{col}_lin" in bt.columns:
                bt[col] = bt[f"{col}_lin"].fillna(bt.get(col, pd.NA))
                bt = bt.drop(columns=[f"{col}_lin"])

    for col in rank_cols + ["taxid"]:
        if col not in bt.columns:
            bt[col] = pd.NA

    # --- Fallback: fill empty rank columns from detection taxonomy string ---
    if "taxonomy" in bt.columns:
        for col in rank_cols:
            if col in bt.columns:
                col_empty = bt[col].isna() | (bt[col].astype(str).str.strip() == "")
                if col_empty.any():
                    fallback_vals = bt.loc[col_empty, "taxonomy"].apply(
                        lambda x, _c=col: parse_taxonomy_string_to_ranks(x).get(_c, "")
                    )
                    bt.loc[col_empty, col] = fallback_vals
                    filled = (fallback_vals.astype(str).str.strip() != "").sum()
                    if filled > 0:
                        print(f"  Fallback: filled {filled} rows for '{col}' from taxonomy string", file=sys.stderr)

    # --- Merge ICTV (on family + genus + species) ---
    if not ictv.empty:
        # Normalize ICTV column names to lowercase
        ictv_norm = ictv.copy()
        ictv_norm.columns = ictv_norm.columns.str.lower()
        if "family" in ictv_norm.columns:
            ictv_cols = ["family"]
            if "ictv_classification" in ictv_norm.columns:
                ictv_cols.append("ictv_classification")
            if "baltimore_group" in ictv_norm.columns:
                ictv_cols.append("baltimore_group")
            if len(ictv_cols) > 1:
                ictv_dedup = ictv_norm[ictv_cols].drop_duplicates(subset=["family"], keep="first")
                bt = bt.merge(ictv_dedup, on="family", how="left")

    for col in ["ictv_classification", "baltimore_group"]:
        if col not in bt.columns:
            bt[col] = pd.NA

    # --- Expand to per-sample rows from coverage ---
    if not coverage.empty and {"seq_id", "sample"}.issubset(coverage.columns):
        cov = coverage.copy()
        cov["seq_id"] = cov["seq_id"].astype(str)
        cov["sample"] = cov["sample"].astype(str)
        cov["coverage"] = pd.to_numeric(cov.get("coverage", 0.0), errors="coerce").fillna(0.0)
        cov["breadth"] = pd.to_numeric(cov.get("breadth", 0.0), errors="coerce").fillna(0.0)
        bt = bt.merge(cov[["seq_id", "sample", "coverage", "breadth"]], on="seq_id", how="inner")
    else:
        bt["sample"] = "coassembly"
        bt["coverage"] = 0.0
        bt["breadth"] = 0.0

    # --- Merge sample metadata (sample -> group) ---
    if not sample_map.empty and "sample" in sample_map.columns:
        meta_cols = [c for c in ["sample", "group"] if c in sample_map.columns]
        bt = bt.merge(
            sample_map[meta_cols].drop_duplicates(subset=["sample"], keep="first"),
            on="sample",
            how="left",
        )
    if "group" not in bt.columns:
        bt["group"] = pd.NA

    bt["coverage"] = pd.to_numeric(bt.get("coverage", 0.0), errors="coerce").fillna(0.0)
    bt["breadth"] = pd.to_numeric(bt.get("breadth", 0.0), errors="coerce").fillna(0.0)

    # --- Coverage-based relative abundance (depth / sum_depths * 1e6, not read-count RPM) ---
    sample_totals = bt.groupby("sample")["coverage"].transform("sum")
    bt["rpm"] = 0.0
    valid_mask = sample_totals > 0
    bt.loc[valid_mask, "rpm"] = (
        bt.loc[valid_mask, "coverage"] / sample_totals.loc[valid_mask] * 1e6
    ).round(2)

    # --- Detection confidence from coverage depth + breadth ---
    bt["detection_confidence"] = [
        compute_detection_confidence(depth, breadth)
        for depth, breadth in zip(bt["coverage"], bt["breadth"])
    ]

    # --- Final column selection ---
    output_cols = [
        "seq_id", "sample", "length", "detection_method", "detection_score",
        "taxonomy", "family", "coverage", "breadth", "detection_confidence", "rpm",
        "taxid", "domain", "phylum", "class", "order", "genus", "species",
        "ictv_classification", "baltimore_group", "group",
    ]
    for col in output_cols:
        if col not in bt.columns:
            bt[col] = pd.NA
    bt = bt[output_cols]

    return bt


def build_sample_taxon_matrix(bigtable: pd.DataFrame) -> pd.DataFrame:
    """Build taxon x sample RPM abundance matrix.

    Output columns: taxon, taxid, rank, <sample_A>, <sample_B>, ...
    Values = sum of RPM for all contigs in each family per sample.
    Falls back to contig rows when RPM is all zero.
    """
    bt = bigtable.copy()
    bt["family"] = bt["family"].fillna("Unclassified")
    bt["rpm"] = pd.to_numeric(bt.get("rpm", 0), errors="coerce").fillna(0.0)
    bt["taxid"] = bt.get("taxid", pd.NA)

    # Use RPM if available, otherwise fall back to per-row contig counts
    use_rpm = bt["rpm"].sum() > 0
    value_col = "rpm" if use_rpm else "row_count"

    if value_col not in bt.columns:
        bt[value_col] = 1 if value_col == "row_count" else 0

    grouped = bt.groupby(["family", "sample"]).agg(
        value=(value_col, "sum"),
        taxid=("taxid", "first"),
    ).reset_index()

    pivot = grouped.pivot_table(
        index=["family", "taxid"], columns="sample", values="value",
        fill_value=0, aggfunc="sum",
    ).reset_index().rename(columns={"family": "taxon"})

    # Add rank column
    pivot["rank"] = "family"

    # Reorder: taxon, taxid, rank, then sample columns
    sample_cols = sorted([c for c in pivot.columns if c not in ("taxon", "taxid", "rank")])
    pivot = pivot[["taxon", "taxid", "rank"] + sample_cols]
    return pivot


def build_sample_counts(bigtable: pd.DataFrame) -> pd.DataFrame:
    """Per-sample per-taxon count summary.

    Output columns: sample, taxon, count
    """
    bt = bigtable.copy()
    bt["family"] = bt["family"].fillna("Unclassified")
    bt["count"] = 1

    counts = bt.groupby(["sample", "family"]).agg(
        count=("count", "sum"),
    ).reset_index().rename(columns={"family": "taxon"})

    counts["count"] = counts["count"].astype(int)
    return counts[["sample", "taxon", "count"]]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    detection = load_detection_files(args.detection)
    taxonomy = load_taxonomy_files(args.taxonomy)
    coverage = load_coverage_files(args.coverage)
    lineage = load_lineage_files(args.lineage)
    sample_map = load_sample_map(args.sample_map)
    ictv = load_ictv(args.ictv)

    print(f"Loaded detection: {len(detection)} contigs from {len(args.detection)} files", file=sys.stderr)
    print(f"Loaded taxonomy:  {len(taxonomy)} hits from {len(args.taxonomy)} files", file=sys.stderr)
    print(f"Loaded coverage:  {len(coverage)} rows from {len(args.coverage)} files "
          f"({coverage['sample'].nunique() if not coverage.empty else 0} samples)", file=sys.stderr)
    print(f"Loaded lineage:   {len(lineage)} rows from {len(args.lineage)} files", file=sys.stderr)
    print(f"Sample map:       {len(sample_map)} entries", file=sys.stderr)
    print(f"ICTV VMR:         {len(ictv)} entries", file=sys.stderr)

    if detection.empty:
        print("WARNING: No detection results. Generating empty outputs.", file=sys.stderr)

    bigtable = build_bigtable(detection, taxonomy, coverage, lineage, sample_map, ictv)
    matrix = build_sample_taxon_matrix(bigtable)
    counts = build_sample_counts(bigtable)

    bigtable.to_csv(args.out_bigtable, sep="\t", index=False)
    matrix.to_csv(args.out_matrix, sep="\t", index=False)
    counts.to_csv(args.out_counts, sep="\t", index=False)

    n_samples = bigtable["sample"].nunique() if not bigtable.empty else 0
    print(
        f"Wrote bigtable ({len(bigtable)} rows, {n_samples} samples), "
        f"matrix ({len(matrix)} taxa x {len(matrix.columns) - 3} samples), "
        f"counts ({len(counts)} entries)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
