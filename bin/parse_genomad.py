#!/usr/bin/env python3
"""Parse geNomad virus_summary.tsv and generate a standard detection TSV.

# @TASK T3.1 - geNomad output parser
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @SPEC docs/planning/04-database-design.md#4.1-bigtable
# @TEST tests/modules/test_genomad.py

Usage:
    python parse_genomad.py <virus_summary.tsv> --output detection_genomad.tsv [--min-score 0.7]

Input:
    geNomad *_virus_summary.tsv with columns:
        seq_name, length, topology, coordinates, n_genes,
        genetic_code, virus_score, taxonomy, n_hallmarks

Output TSV columns:
    seq_id, length, detection_method, detection_score, taxonomy, viral_hallmark_count
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


# Column order for output TSV
TSV_COLUMNS = [
    "seq_id",
    "length",
    "detection_method",
    "detection_score",
    "taxonomy",
    "viral_hallmark_count",
]


def parse_genomad_tsv(tsv_path: Path) -> list[dict[str, Any]]:
    """Parse a geNomad virus_summary.tsv into standard detection rows.

    Args:
        tsv_path: Path to geNomad *_virus_summary.tsv file.

    Returns:
        List of dictionaries with keys matching TSV_COLUMNS.
        Each row maps geNomad columns to the standard detection format.

    Raises:
        FileNotFoundError: If tsv_path does not exist.
    """
    if not tsv_path.exists():
        raise FileNotFoundError(f"File not found: {tsv_path}")

    rows: list[dict[str, Any]] = []

    with open(tsv_path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for record in reader:
            row = {
                "seq_id": record["seq_name"],
                "length": int(record["length"]),
                "detection_method": "genomad",
                "detection_score": float(record["virus_score"]),
                "taxonomy": record.get("taxonomy", ""),
                "viral_hallmark_count": int(record.get("n_hallmarks", 0)),
            }
            rows.append(row)

    return rows


def filter_by_score(
    rows: list[dict[str, Any]],
    min_score: float = 0.7,
) -> list[dict[str, Any]]:
    """Filter detection rows by minimum virus score.

    Args:
        rows: List of parsed detection rows.
        min_score: Minimum detection_score threshold (inclusive).

    Returns:
        Filtered list containing only rows with detection_score >= min_score.
    """
    return [r for r in rows if r["detection_score"] >= min_score]


def write_tsv(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Write detection rows to a TSV file.

    Args:
        rows: List of dictionaries (one per detected viral sequence).
        output_path: Destination TSV file path.
    """
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for parse_genomad.py.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Parse geNomad virus_summary.tsv into standard detection TSV."
    )
    parser.add_argument(
        "input_tsv",
        type=Path,
        help="geNomad *_virus_summary.tsv file.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output TSV file path.",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.7,
        help="Minimum virus score threshold (default: 0.7).",
    )
    args = parser.parse_args(argv)

    if not args.input_tsv.exists():
        print(f"ERROR: File not found: {args.input_tsv}", file=sys.stderr)
        return 1

    try:
        rows = parse_genomad_tsv(args.input_tsv)
    except (KeyError, ValueError) as e:
        print(f"ERROR: Failed to parse {args.input_tsv}: {e}", file=sys.stderr)
        return 1

    filtered = filter_by_score(rows, min_score=args.min_score)
    write_tsv(filtered, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
