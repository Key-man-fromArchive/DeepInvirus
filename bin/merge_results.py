#!/usr/bin/env python3
"""Merge all classification results into a unified bigtable.

# @TASK T4.2 - bigtable generation
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @SPEC docs/planning/04-database-design.md#4.1-bigtable
# @TEST tests/modules/test_classification.py

Usage:
    python merge_results.py \\
        --taxonomy taxonomy.tsv \\
        --lineage lineage.tsv \\
        --coverage coverage.tsv \\
        --detection detection.tsv \\
        --sample-map sample_map.tsv \\
        --ictv ictv_vmr.tsv \\
        --out-bigtable bigtable.tsv \\
        --out-matrix sample_taxon_matrix.tsv \\
        --out-counts sample_counts.tsv

Inputs:
    - taxonomy: MMseqs2 taxonomy output (query, taxid, rank, name)
    - lineage:  TaxonKit 7-rank lineage (taxid, lineage, domain..species)
    - coverage: CoverM coverage (Contig, Mean, Trimmed Mean, Covered Bases, Length)
    - detection: merged detection results (seq_id, length, detection_method, detection_score, taxonomy, taxid, subject_id)
    - sample-map: seq_id -> sample, seq_type, total_reads, count mapping
    - ictv: ICTV VMR (family, genus, species, baltimore_group, ictv_classification)

Outputs:
    - bigtable.tsv: 04-database-design.md section 4.1 schema
    - sample_taxon_matrix.tsv: section 4.2 schema (pivot table, RPM values)
    - sample_counts.tsv: sample x taxon raw counts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


# @TASK T4.2 - bigtable column order (must match 04-database-design.md 4.1)
BIGTABLE_COLUMNS = [
    "seq_id",
    "sample",
    "seq_type",
    "length",
    "detection_method",
    "detection_score",
    "taxid",
    "domain",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
    "ictv_classification",
    "baltimore_group",
    "count",
    "rpm",
    "coverage",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Merge classification results into bigtable and pivot tables.",
    )
    parser.add_argument(
        "--taxonomy",
        required=True,
        type=Path,
        help="MMseqs2 taxonomy TSV (query, taxid, rank, name)",
    )
    parser.add_argument(
        "--lineage",
        required=True,
        type=Path,
        help="TaxonKit lineage TSV (taxid, lineage, domain..species)",
    )
    parser.add_argument(
        "--coverage",
        required=True,
        type=Path,
        help="CoverM coverage TSV (Contig, Mean, ...)",
    )
    parser.add_argument(
        "--detection",
        required=True,
        type=Path,
        help="Merged detection TSV (seq_id, length, detection_method, ...)",
    )
    parser.add_argument(
        "--sample-map",
        required=True,
        type=Path,
        help="Sample mapping TSV (seq_id, sample, seq_type, total_reads, count)",
    )
    parser.add_argument(
        "--ictv",
        required=True,
        type=Path,
        help="ICTV VMR TSV (family, genus, species, baltimore_group, ictv_classification)",
    )
    parser.add_argument(
        "--out-bigtable",
        required=True,
        type=Path,
        help="Output bigtable TSV path",
    )
    parser.add_argument(
        "--out-matrix",
        required=True,
        type=Path,
        help="Output sample-taxon matrix TSV path",
    )
    parser.add_argument(
        "--out-counts",
        required=True,
        type=Path,
        help="Output sample counts TSV path",
    )
    return parser.parse_args(argv)


def load_taxonomy(path: Path) -> pd.DataFrame:
    """Load MMseqs2 taxonomy output."""
    df = pd.read_csv(path, sep="\t", dtype=str)
    df.columns = df.columns.str.strip()
    # Rename 'query' to 'seq_id' for joining
    if "query" in df.columns:
        df = df.rename(columns={"query": "seq_id"})
    return df


def load_lineage(path: Path) -> pd.DataFrame:
    """Load TaxonKit lineage output with 7-rank columns."""
    df = pd.read_csv(path, sep="\t", dtype=str)
    df.columns = df.columns.str.strip()
    return df


def load_coverage(path: Path) -> pd.DataFrame:
    """Load CoverM coverage output."""
    df = pd.read_csv(path, sep="\t")
    df.columns = df.columns.str.strip()
    # Rename Contig -> seq_id, Mean -> coverage
    rename_map = {}
    if "Contig" in df.columns:
        rename_map["Contig"] = "seq_id"
    if "Mean" in df.columns:
        rename_map["Mean"] = "coverage"
    df = df.rename(columns=rename_map)
    # Keep only seq_id and coverage
    if "seq_id" in df.columns and "coverage" in df.columns:
        df = df[["seq_id", "coverage"]]
    return df


def load_detection(path: Path) -> pd.DataFrame:
    """Load merged detection results."""
    df = pd.read_csv(path, sep="\t", dtype=str)
    df.columns = df.columns.str.strip()
    return df


def load_sample_map(path: Path) -> pd.DataFrame:
    """Load sample mapping file. Returns empty DataFrame if file is missing or malformed."""
    try:
        df = pd.read_csv(path, sep="\t")
        df.columns = df.columns.str.strip()
        if "seq_id" in df.columns:
            df["seq_id"] = df["seq_id"].astype(str)
            df["sample"] = df["sample"].astype(str)
            df["seq_type"] = df["seq_type"].astype(str) if "seq_type" in df.columns else "contig"
            return df
    except Exception:
        pass
    # Return empty DataFrame with expected columns
    return pd.DataFrame(columns=["seq_id", "sample", "seq_type", "total_reads", "count"])


def load_ictv(path: Path) -> pd.DataFrame:
    """Load ICTV VMR classification mapping. Returns empty DataFrame if unavailable."""
    try:
        df = pd.read_csv(path, sep="\t", dtype=str)
        df.columns = df.columns.str.strip()
        if len(df) > 0:
            return df
    except Exception:
        pass
    return pd.DataFrame(columns=["Family", "Genus", "Species", "ICTV_classification"])


def build_bigtable(
    detection: pd.DataFrame,
    taxonomy: pd.DataFrame,
    lineage: pd.DataFrame,
    coverage: pd.DataFrame,
    sample_map: pd.DataFrame,
    ictv: pd.DataFrame,
) -> pd.DataFrame:
    """Merge all data sources into the bigtable.

    Returns:
        DataFrame with columns matching BIGTABLE_COLUMNS.
    """
    # Start from detection results (one row per seq_id)
    bt = detection[["seq_id", "detection_method", "detection_score"]].copy()
    bt["detection_score"] = pd.to_numeric(bt["detection_score"], errors="coerce")

    # Merge sample info
    bt = bt.merge(sample_map, on="seq_id", how="left")

    # Merge length from detection
    if "length" in detection.columns:
        bt = bt.merge(
            detection[["seq_id", "length"]].drop_duplicates(),
            on="seq_id",
            how="left",
            suffixes=("", "_det"),
        )
        # Use detection length if not from sample_map
        if "length_det" in bt.columns:
            bt["length"] = bt["length"].fillna(bt["length_det"])
            bt.drop(columns=["length_det"], inplace=True)

    # Merge taxonomy (get taxid from taxonomy output)
    if "taxid" in taxonomy.columns:
        tax_cols = ["seq_id", "taxid"]
        bt = bt.merge(
            taxonomy[tax_cols].drop_duplicates(),
            on="seq_id",
            how="left",
            suffixes=("", "_tax"),
        )
        if "taxid_tax" in bt.columns:
            bt["taxid"] = bt["taxid"].fillna(bt["taxid_tax"])
            bt.drop(columns=["taxid_tax"], inplace=True)
    elif "taxid" not in bt.columns:
        # Try from detection
        if "taxid" in detection.columns:
            bt = bt.merge(
                detection[["seq_id", "taxid"]].drop_duplicates(),
                on="seq_id",
                how="left",
            )

    bt["taxid"] = pd.to_numeric(bt["taxid"], errors="coerce").fillna(0).astype(int)

    # Merge lineage (7-rank)
    lineage_cols = ["taxid", "domain", "phylum", "class", "order", "family", "genus", "species"]
    available_lineage_cols = [c for c in lineage_cols if c in lineage.columns]
    if available_lineage_cols:
        lineage_sub = lineage[available_lineage_cols].copy()
        lineage_sub["taxid"] = pd.to_numeric(lineage_sub["taxid"], errors="coerce").fillna(0).astype(int)
        lineage_sub = lineage_sub.drop_duplicates(subset=["taxid"])
        bt = bt.merge(lineage_sub, on="taxid", how="left", suffixes=("", "_lin"))
        # Clean up duplicate columns
        for col in ["domain", "phylum", "class", "order", "family", "genus", "species"]:
            lin_col = f"{col}_lin"
            if lin_col in bt.columns:
                bt[col] = bt[col].fillna(bt[lin_col])
                bt.drop(columns=[lin_col], inplace=True)

    # Fill missing lineage columns
    for rank in ["domain", "phylum", "class", "order", "family", "genus", "species"]:
        if rank not in bt.columns:
            bt[rank] = "Unclassified"
        bt[rank] = bt[rank].fillna("Unclassified")

    # Merge ICTV classification
    if not ictv.empty and "genus" in ictv.columns:
        ictv_sub = ictv[["genus", "ictv_classification", "baltimore_group"]].copy()
        ictv_sub = ictv_sub.drop_duplicates(subset=["genus"])
        bt = bt.merge(ictv_sub, on="genus", how="left", suffixes=("", "_ictv"))
        if "ictv_classification_ictv" in bt.columns:
            bt["ictv_classification"] = bt["ictv_classification"].fillna(
                bt["ictv_classification_ictv"]
            )
            bt.drop(columns=["ictv_classification_ictv"], inplace=True)
        if "baltimore_group_ictv" in bt.columns:
            bt["baltimore_group"] = bt["baltimore_group"].fillna(
                bt["baltimore_group_ictv"]
            )
            bt.drop(columns=["baltimore_group_ictv"], inplace=True)

    for col in ["ictv_classification", "baltimore_group"]:
        if col not in bt.columns:
            bt[col] = "Unclassified"
        bt[col] = bt[col].fillna("Unclassified")

    # Merge coverage
    if not coverage.empty:
        bt = bt.merge(coverage, on="seq_id", how="left", suffixes=("", "_cov"))
        if "coverage_cov" in bt.columns:
            bt["coverage"] = bt["coverage"].fillna(bt["coverage_cov"])
            bt.drop(columns=["coverage_cov"], inplace=True)
    if "coverage" not in bt.columns:
        bt["coverage"] = 0.0

    # Reads (seq_type=read) should have coverage=0
    bt["coverage"] = pd.to_numeric(bt["coverage"], errors="coerce").fillna(0.0)
    bt.loc[bt["seq_type"] == "read", "coverage"] = 0.0

    # Calculate RPM: count / total_reads * 1e6
    bt["count"] = pd.to_numeric(bt["count"], errors="coerce").fillna(0).astype(int)
    bt["total_reads"] = pd.to_numeric(bt["total_reads"], errors="coerce").fillna(1)
    bt["rpm"] = (bt["count"] / bt["total_reads"] * 1e6).round(1)

    # Ensure length is numeric
    bt["length"] = pd.to_numeric(bt["length"], errors="coerce").fillna(0).astype(int)

    # Select and order columns
    bt = bt[BIGTABLE_COLUMNS]

    return bt


def build_sample_taxon_matrix(bigtable: pd.DataFrame) -> pd.DataFrame:
    """Build sample x taxon pivot table with RPM values.

    Returns:
        DataFrame with columns: taxon, taxid, rank, {sample_1}, {sample_2}, ...
    """
    # Use genus as the taxonomic unit for the matrix
    bt = bigtable.copy()

    # Group by genus, aggregate RPM per sample
    grouped = bt.groupby(["genus", "sample"])["rpm"].sum().reset_index()

    # Pivot: rows=genus, columns=sample, values=RPM
    pivot = grouped.pivot_table(
        index="genus",
        columns="sample",
        values="rpm",
        fill_value=0.0,
    )
    pivot = pivot.reset_index()
    pivot = pivot.rename(columns={"genus": "taxon"})

    # Add taxid and rank columns
    # Get first taxid per genus from the bigtable
    genus_taxid = bt.drop_duplicates(subset=["genus"])[["genus", "taxid"]].copy()
    genus_taxid = genus_taxid.rename(columns={"genus": "taxon"})

    pivot = pivot.merge(genus_taxid, on="taxon", how="left")
    pivot["rank"] = "genus"

    # Reorder: taxon, taxid, rank, then sample columns
    sample_cols = sorted([c for c in pivot.columns if c not in ["taxon", "taxid", "rank"]])
    pivot = pivot[["taxon", "taxid", "rank"] + sample_cols]

    return pivot


def build_sample_counts(bigtable: pd.DataFrame) -> pd.DataFrame:
    """Build sample x taxon raw count table.

    Returns:
        DataFrame with columns: sample, taxon, count
    """
    bt = bigtable.copy()
    counts = bt.groupby(["sample", "genus"])["count"].sum().reset_index()
    counts = counts.rename(columns={"genus": "taxon"})
    counts = counts[["sample", "taxon", "count"]]
    return counts


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    # Load all inputs
    taxonomy = load_taxonomy(args.taxonomy)
    lineage = load_lineage(args.lineage)
    coverage = load_coverage(args.coverage)
    detection = load_detection(args.detection)
    sample_map = load_sample_map(args.sample_map)
    ictv = load_ictv(args.ictv)

    # Build bigtable
    bigtable = build_bigtable(
        detection=detection,
        taxonomy=taxonomy,
        lineage=lineage,
        coverage=coverage,
        sample_map=sample_map,
        ictv=ictv,
    )

    # Build sample-taxon matrix
    matrix = build_sample_taxon_matrix(bigtable)

    # Build sample counts
    counts = build_sample_counts(bigtable)

    # Write outputs
    bigtable.to_csv(args.out_bigtable, sep="\t", index=False)
    matrix.to_csv(args.out_matrix, sep="\t", index=False)
    counts.to_csv(args.out_counts, sep="\t", index=False)

    print(
        f"Wrote bigtable ({len(bigtable)} rows), "
        f"matrix ({len(matrix)} taxa x {len(matrix.columns) - 3} samples), "
        f"counts ({len(counts)} entries)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
