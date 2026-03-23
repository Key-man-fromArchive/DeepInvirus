#!/usr/bin/env python3
"""Merge all per-sample classification results into a unified bigtable.

# @TASK T4.2 - bigtable generation
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @SPEC docs/planning/04-database-design.md#4.1-bigtable

Usage:
    python merge_results.py \\
        --taxonomy GC_Tm_taxonomy.tsv Inf_NB_Tm_taxonomy.tsv \\
        --lineage GC_Tm_lineage.tsv Inf_NB_Tm_lineage.tsv \\
        --coverage GC_Tm_coverage.tsv Inf_NB_Tm_coverage.tsv \\
        --detection GC_Tm_merged_detection.tsv Inf_NB_Tm_merged_detection.tsv \\
        --sample-map sample_map.tsv \\
        --ictv ictv_vmr.tsv \\
        --out-bigtable bigtable.tsv \\
        --out-matrix sample_taxon_matrix.tsv \\
        --out-counts sample_counts.tsv

Inputs (per-sample files, sample name extracted from filename):
    - taxonomy:  MMseqs2 easy-search output (query, target, pident, evalue, bitscore)
    - lineage:   TaxonKit lineage or pass-through copy of taxonomy
    - coverage:  CoverM coverage (Contig, <sample> Mean, ...)
    - detection: merged detection (seq_id, length, detection_method, detection_score, taxonomy, taxid, subject_id)
    - sample-map: sample group mapping (sample, group) -- optional content
    - ictv:      ICTV VMR (Family, Genus, Species, ICTV_classification) -- optional content

Outputs:
    - bigtable.tsv:           all info merged
    - sample_taxon_matrix.tsv: sample x family pivot (count-based)
    - sample_counts.tsv:       sample x seq_id counts
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------------
# Filename -> sample name extraction
# ---------------------------------------------------------------------------

# Suffixes to strip from filenames to get sample names
_SUFFIX_PATTERNS = [
    r"_merged_detection\.tsv$",
    r"_taxonomy\.tsv$",
    r"_lineage\.tsv$",
    r"_coverage\.tsv$",
]


def extract_sample_name(filepath: str | Path) -> str:
    """Extract sample name from a per-sample filename.

    Examples:
        GC_Tm_merged_detection.tsv  -> GC_Tm
        Inf_NB_Tm_taxonomy.tsv      -> Inf_NB_Tm
    """
    name = Path(filepath).name
    for pat in _SUFFIX_PATTERNS:
        m = re.search(pat, name)
        if m:
            return name[: m.start()]
    # Fallback: strip .tsv
    return name.removesuffix(".tsv")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(
        description="Merge per-sample classification results into bigtable.",
    )
    p.add_argument("--taxonomy", nargs="+", type=Path, required=True,
                    help="Per-sample MMseqs2 taxonomy TSV files")
    p.add_argument("--lineage", nargs="+", type=Path, required=True,
                    help="Per-sample TaxonKit lineage TSV files")
    p.add_argument("--coverage", nargs="+", type=Path, required=True,
                    help="Per-sample CoverM coverage TSV files")
    p.add_argument("--detection", nargs="+", type=Path, required=True,
                    help="Per-sample merged detection TSV files")
    p.add_argument("--sample-map", type=Path, required=True,
                    help="Sample mapping TSV (sample, group)")
    p.add_argument("--ictv", type=Path, required=True,
                    help="ICTV VMR TSV")
    p.add_argument("--out-bigtable", type=Path, required=True)
    p.add_argument("--out-matrix", type=Path, required=True)
    p.add_argument("--out-counts", type=Path, required=True)
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Loaders (per-sample, return list of DataFrames with 'sample' column)
# ---------------------------------------------------------------------------

def load_detection_files(paths: list[Path]) -> pd.DataFrame:
    """Load and concatenate per-sample detection files.

    Expected columns: seq_id, length, detection_method, detection_score, taxonomy, taxid, subject_id
    Adds 'sample' column derived from filename.
    """
    frames = []
    for p in paths:
        sample = extract_sample_name(p)
        try:
            df = pd.read_csv(p, sep="\t", dtype=str)
        except pd.errors.EmptyDataError:
            continue
        df.columns = df.columns.str.strip()
        df["sample"] = sample
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=[
            "seq_id", "length", "detection_method", "detection_score",
            "taxonomy", "taxid", "subject_id", "sample",
        ])
    return pd.concat(frames, ignore_index=True)


def load_taxonomy_files(paths: list[Path]) -> pd.DataFrame:
    """Load and concatenate per-sample taxonomy files (MMseqs2 easy-search format).

    Expected columns: query, target, pident, evalue, bitscore
    Adds 'sample' column.
    """
    frames = []
    for p in paths:
        sample = extract_sample_name(p)
        try:
            df = pd.read_csv(p, sep="\t", dtype=str)
        except pd.errors.EmptyDataError:
            continue
        df.columns = df.columns.str.strip()
        if "query" in df.columns:
            df = df.rename(columns={"query": "seq_id"})
        df["sample"] = sample
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["seq_id", "target", "pident", "evalue", "bitscore", "sample"])
    return pd.concat(frames, ignore_index=True)


def load_coverage_files(paths: list[Path]) -> pd.DataFrame:
    """Load and concatenate per-sample CoverM coverage files.

    CoverM column names are dynamic (include sample-specific path info).
    We take the first column as Contig (seq_id) and the second column as coverage (Mean).
    Adds 'sample' column.
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
        # Use positional columns: 0=Contig, 1=Mean coverage
        cov = pd.DataFrame({
            "seq_id": df.iloc[:, 0].astype(str),
            "coverage": pd.to_numeric(df.iloc[:, 1], errors="coerce").fillna(0.0),
        })
        cov["sample"] = sample
        frames.append(cov)
    if not frames:
        return pd.DataFrame(columns=["seq_id", "coverage", "sample"])
    return pd.concat(frames, ignore_index=True)


def load_lineage_files(paths: list[Path]) -> pd.DataFrame:
    """Load lineage files. These may be proper TaxonKit output or just a copy of taxonomy.

    If proper TaxonKit format (taxid, lineage, domain..species), return as-is.
    If it looks like taxonomy (query, target, pident...), return empty lineage.
    """
    frames = []
    for p in paths:
        sample = extract_sample_name(p)
        try:
            df = pd.read_csv(p, sep="\t", dtype=str)
        except pd.errors.EmptyDataError:
            continue
        df.columns = df.columns.str.strip()
        # Check if this is real lineage data (has taxid + domain columns)
        if "taxid" in df.columns and "domain" in df.columns and len(df) > 0:
            df["sample"] = sample
            frames.append(df)
        # Otherwise it is a pass-through copy of taxonomy -- skip
    if not frames:
        return pd.DataFrame(columns=[
            "taxid", "lineage", "domain", "phylum", "class",
            "order", "family", "genus", "species", "sample",
        ])
    return pd.concat(frames, ignore_index=True)


def load_sample_map(path: Path) -> pd.DataFrame:
    """Load sample_map.tsv (sample, group). Returns empty DataFrame if missing/empty."""
    try:
        df = pd.read_csv(path, sep="\t", dtype=str)
        df.columns = df.columns.str.strip()
        if "sample" in df.columns and len(df) > 0:
            return df
    except Exception:
        pass
    return pd.DataFrame(columns=["sample", "group"])


def load_ictv(path: Path) -> pd.DataFrame:
    """Load ICTV VMR. Returns empty DataFrame if missing/empty."""
    try:
        df = pd.read_csv(path, sep="\t", dtype=str)
        df.columns = df.columns.str.strip()
        if len(df) > 0:
            return df
    except Exception:
        pass
    return pd.DataFrame(columns=["Family", "Genus", "Species", "ICTV_classification"])


# ---------------------------------------------------------------------------
# Extract family from detection taxonomy string
# ---------------------------------------------------------------------------

def extract_family_from_lineage_str(tax_str: str) -> str:
    """Extract family-level name from semicolon-separated taxonomy string.

    The detection 'taxonomy' column has format like:
        Viruses;Duplodnaviria;Heunggongvirae;Uroviricota;Caudoviricetes;;
        Viruses;Riboviria;Orthornavirae;Kitrinoviricota;Magsaviricetes;Nodamuvirales;Sinhaliviridae

    Standard ICTV ranks: Domain;Kingdom;Phylum;Class;Order;Family;...
    We attempt to find a token ending in 'viridae' (family suffix) or use
    the 6th field (0-indexed 5) if available.
    """
    if not isinstance(tax_str, str) or tax_str.strip() == "":
        return "Unclassified"
    parts = [x.strip() for x in tax_str.split(";")]
    # First try: find token ending in 'viridae' (standard family suffix)
    for part in parts:
        if part.lower().endswith("viridae"):
            return part
    # Fallback: 6th field (family position in ICTV 7-rank lineage)
    # Domain(0);Kingdom(1);Phylum(2);Class(3);Order(4);Family(5);Subfamily/Genus(6)
    if len(parts) > 5 and parts[5].strip():
        return parts[5]
    # Last resort: deepest non-empty rank
    for part in reversed(parts):
        if part.strip():
            return part
    return "Unclassified"


# ---------------------------------------------------------------------------
# Build outputs
# ---------------------------------------------------------------------------

def build_bigtable(
    detection: pd.DataFrame,
    taxonomy: pd.DataFrame,
    coverage: pd.DataFrame,
    lineage: pd.DataFrame,
    sample_map: pd.DataFrame,
    ictv: pd.DataFrame,
) -> pd.DataFrame:
    """Merge all data sources into the bigtable.

    Output columns:
        seq_id, sample, length, detection_method, detection_score,
        taxonomy (lineage string), target, pident, evalue, coverage, group, family
    """
    # --- Base: detection (one row per seq_id per sample) ---
    bt = detection.copy()
    bt["length"] = pd.to_numeric(bt["length"], errors="coerce").fillna(0).astype(int)
    bt["detection_score"] = pd.to_numeric(bt["detection_score"], errors="coerce")

    # --- Extract family from detection taxonomy string ---
    if "taxonomy" in bt.columns:
        bt["family"] = bt["taxonomy"].apply(extract_family_from_lineage_str)
    else:
        bt["family"] = "Unclassified"

    # --- Merge taxonomy (MMseqs2 hits) ---
    if not taxonomy.empty:
        # Keep best hit per (seq_id, sample)
        tax = taxonomy.copy()
        tax["bitscore"] = pd.to_numeric(tax["bitscore"], errors="coerce").fillna(0)
        tax = tax.sort_values("bitscore", ascending=False).drop_duplicates(
            subset=["seq_id", "sample"], keep="first"
        )
        tax_cols = ["seq_id", "sample", "target", "pident", "evalue"]
        available = [c for c in tax_cols if c in tax.columns]
        bt = bt.merge(tax[available], on=["seq_id", "sample"], how="left")
    else:
        for col in ["target", "pident", "evalue"]:
            bt[col] = pd.NA

    # --- Merge coverage ---
    if not coverage.empty:
        cov = coverage.drop_duplicates(subset=["seq_id", "sample"], keep="first")
        bt = bt.merge(cov[["seq_id", "sample", "coverage"]], on=["seq_id", "sample"], how="left")
    if "coverage" not in bt.columns:
        bt["coverage"] = 0.0
    bt["coverage"] = pd.to_numeric(bt["coverage"], errors="coerce").fillna(0.0)

    # --- Merge sample_map (group info) ---
    if not sample_map.empty and "group" in sample_map.columns:
        bt = bt.merge(sample_map[["sample", "group"]], on="sample", how="left")
    if "group" not in bt.columns:
        bt["group"] = "unknown"
    bt["group"] = bt["group"].fillna("unknown")

    # --- Select and order final columns ---
    output_cols = [
        "seq_id", "sample", "length", "detection_method", "detection_score",
        "taxonomy", "family", "target", "pident", "evalue", "coverage", "group",
    ]
    for col in output_cols:
        if col not in bt.columns:
            bt[col] = pd.NA
    bt = bt[output_cols]

    return bt


def build_sample_taxon_matrix(bigtable: pd.DataFrame) -> pd.DataFrame:
    """Build sample x family pivot table (count-based).

    Rows = family, Columns = samples, Values = number of contigs.
    """
    bt = bigtable.copy()
    bt["family"] = bt["family"].fillna("Unclassified")

    # Count contigs per family per sample
    grouped = bt.groupby(["family", "sample"]).size().reset_index(name="count")

    pivot = grouped.pivot_table(
        index="family",
        columns="sample",
        values="count",
        fill_value=0,
        aggfunc="sum",
    )
    pivot = pivot.reset_index()
    pivot = pivot.rename(columns={"family": "taxon"})

    # Sort sample columns
    sample_cols = sorted([c for c in pivot.columns if c != "taxon"])
    pivot = pivot[["taxon"] + sample_cols]

    return pivot


def build_sample_counts(bigtable: pd.DataFrame) -> pd.DataFrame:
    """Build sample-level contig counts.

    Output: sample, total_contigs, mean_detection_score, mean_coverage
    """
    bt = bigtable.copy()
    bt["detection_score"] = pd.to_numeric(bt["detection_score"], errors="coerce")
    bt["coverage"] = pd.to_numeric(bt["coverage"], errors="coerce")

    counts = bt.groupby("sample").agg(
        total_contigs=("seq_id", "count"),
        mean_detection_score=("detection_score", "mean"),
        mean_coverage=("coverage", "mean"),
    ).reset_index()
    counts["mean_detection_score"] = counts["mean_detection_score"].round(4)
    counts["mean_coverage"] = counts["mean_coverage"].round(4)

    return counts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    # Load all per-sample inputs
    detection = load_detection_files(args.detection)
    taxonomy = load_taxonomy_files(args.taxonomy)
    coverage = load_coverage_files(args.coverage)
    lineage = load_lineage_files(args.lineage)
    sample_map = load_sample_map(args.sample_map)
    ictv = load_ictv(args.ictv)

    print(f"Loaded detection: {len(detection)} rows from {len(args.detection)} files", file=sys.stderr)
    print(f"Loaded taxonomy:  {len(taxonomy)} rows from {len(args.taxonomy)} files", file=sys.stderr)
    print(f"Loaded coverage:  {len(coverage)} rows from {len(args.coverage)} files", file=sys.stderr)
    print(f"Loaded lineage:   {len(lineage)} rows from {len(args.lineage)} files", file=sys.stderr)
    print(f"Sample map:       {len(sample_map)} entries", file=sys.stderr)
    print(f"ICTV VMR:         {len(ictv)} entries", file=sys.stderr)

    if detection.empty:
        print("WARNING: No detection results found. Generating empty outputs.", file=sys.stderr)

    # Build outputs
    bigtable = build_bigtable(
        detection=detection,
        taxonomy=taxonomy,
        coverage=coverage,
        lineage=lineage,
        sample_map=sample_map,
        ictv=ictv,
    )
    matrix = build_sample_taxon_matrix(bigtable)
    counts = build_sample_counts(bigtable)

    # Write outputs
    bigtable.to_csv(args.out_bigtable, sep="\t", index=False)
    matrix.to_csv(args.out_matrix, sep="\t", index=False)
    counts.to_csv(args.out_counts, sep="\t", index=False)

    n_samples = bigtable["sample"].nunique() if not bigtable.empty else 0
    print(
        f"Wrote bigtable ({len(bigtable)} rows, {n_samples} samples), "
        f"matrix ({len(matrix)} taxa x {len(matrix.columns) - 1} samples), "
        f"counts ({len(counts)} samples)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
