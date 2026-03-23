#!/usr/bin/env python3
"""Merge geNomad and Diamond parsed detection results into a unified TSV.

# @TASK T3.3 - Detection result merger
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @SPEC docs/planning/04-database-design.md#4.1-bigtable
# @TEST tests/modules/test_merge_detection.py

Usage:
    python merge_detection.py --genomad detection_genomad.tsv --diamond detection_diamond.tsv --output merged_detection.tsv

Input:
    - geNomad parsed TSV (from parse_genomad.py):
        seq_id, length, detection_method, detection_score, taxonomy, viral_hallmark_count
    - Diamond parsed TSV (from parse_diamond.py):
        seq_id, subject_id, pident, length, evalue, bitscore, taxid, detection_method

Output TSV columns:
    seq_id, length, detection_method, detection_score, taxonomy, taxid, subject_id

Merge logic:
    - Outer join on seq_id
    - detection_method: 'genomad' / 'diamond' / 'both'
    - detection_score: geNomad score prioritized; Diamond bitscore normalized to [0,1] as fallback
    - taxonomy: from geNomad
    - taxid, subject_id: from Diamond
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


# Column order for merged output TSV
TSV_COLUMNS = [
    "seq_id",
    "length",
    "detection_method",
    "detection_score",
    "taxonomy",
    "taxid",
    "subject_id",
]

# Maximum bitscore used for normalization (typical high Diamond bitscore)
MAX_BITSCORE = 1000.0


def read_genomad_tsv(tsv_path: Path) -> dict[str, dict[str, Any]]:
    """Read parsed geNomad detection TSV into a dict keyed by seq_id.

    Args:
        tsv_path: Path to parsed geNomad TSV file.

    Returns:
        Dictionary mapping seq_id to row data.
    """
    records: dict[str, dict[str, Any]] = {}
    with open(tsv_path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            records[row["seq_id"]] = row
    return records


def read_diamond_tsv(tsv_path: Path) -> dict[str, dict[str, Any]]:
    """Read parsed Diamond detection TSV into a dict keyed by seq_id.

    Args:
        tsv_path: Path to parsed Diamond TSV file.

    Returns:
        Dictionary mapping seq_id to row data.
    """
    records: dict[str, dict[str, Any]] = {}
    with open(tsv_path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            records[row["seq_id"]] = row
    return records


def normalize_bitscore(bitscore: float, max_bitscore: float = MAX_BITSCORE) -> float:
    """Normalize a Diamond bitscore to a [0, 1] range.

    Uses min(bitscore / max_bitscore, 1.0) to cap at 1.0 for very high scores.

    Args:
        bitscore: Raw Diamond bitscore value.
        max_bitscore: Maximum expected bitscore for normalization.

    Returns:
        Normalized score in [0.0, 1.0].
    """
    if max_bitscore <= 0:
        return 0.0
    return min(bitscore / max_bitscore, 1.0)


def merge_detections(
    genomad_tsv: Path,
    diamond_tsv: Path,
) -> list[dict[str, Any]]:
    """Merge geNomad and Diamond parsed detection results via outer join on seq_id.

    Args:
        genomad_tsv: Path to parsed geNomad detection TSV.
        diamond_tsv: Path to parsed Diamond detection TSV.

    Returns:
        List of merged detection rows with columns matching TSV_COLUMNS.
    """
    genomad_data = read_genomad_tsv(genomad_tsv)
    diamond_data = read_diamond_tsv(diamond_tsv)

    # Collect all unique seq_ids (outer join)
    all_seq_ids = set(genomad_data.keys()) | set(diamond_data.keys())

    rows: list[dict[str, Any]] = []
    for seq_id in sorted(all_seq_ids):
        g = genomad_data.get(seq_id)
        d = diamond_data.get(seq_id)

        # Determine detection_method
        if g and d:
            detection_method = "both"
        elif g:
            detection_method = "genomad"
        else:
            detection_method = "diamond"

        # Determine detection_score: geNomad score prioritized
        if g:
            detection_score = float(g["detection_score"])
        else:
            # Diamond-only: normalize bitscore
            bitscore = float(d["bitscore"]) if d else 0.0
            detection_score = normalize_bitscore(bitscore)

        # Determine length: geNomad preferred, then Diamond
        if g:
            length = g["length"]
        elif d:
            length = d["length"]
        else:
            length = ""

        # taxonomy from geNomad, taxid and subject_id from Diamond
        taxonomy = g.get("taxonomy", "") if g else ""
        taxid = d.get("taxid", "") if d else ""
        subject_id = d.get("subject_id", "") if d else ""

        row = {
            "seq_id": seq_id,
            "length": length,
            "detection_method": detection_method,
            "detection_score": round(detection_score, 6),
            "taxonomy": taxonomy,
            "taxid": taxid,
            "subject_id": subject_id,
        }
        rows.append(row)

    return rows


def write_tsv(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Write merged detection rows to a TSV file.

    Args:
        rows: List of merged detection dictionaries.
        output_path: Destination TSV file path.
    """
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for merge_detection.py.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Merge geNomad and Diamond detection results into unified TSV."
    )
    parser.add_argument(
        "--genomad",
        type=Path,
        required=True,
        help="Parsed geNomad detection TSV (from parse_genomad.py).",
    )
    parser.add_argument(
        "--diamond",
        type=Path,
        required=True,
        help="Parsed Diamond detection TSV (from parse_diamond.py).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output merged detection TSV file path.",
    )
    args = parser.parse_args(argv)

    if not args.genomad.exists():
        print(f"ERROR: File not found: {args.genomad}", file=sys.stderr)
        return 1
    if not args.diamond.exists():
        print(f"ERROR: File not found: {args.diamond}", file=sys.stderr)
        return 1

    try:
        rows = merge_detections(args.genomad, args.diamond)
    except (KeyError, ValueError) as e:
        print(f"ERROR: Failed to merge: {e}", file=sys.stderr)
        return 1

    write_tsv(rows, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
