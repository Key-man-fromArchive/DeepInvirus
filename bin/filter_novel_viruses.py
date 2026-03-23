#!/usr/bin/env python3
"""Novel virus filtering from merged detection results.

# @TASK T6.1 - Novel virus filtering
# @SPEC docs/planning/02-trd.md#3.2-pipeline-stages
# @TEST tests/modules/test_novel_discovery.py

geNomad-only detected sequences (Diamond has no match) = potential novel viruses.
Also includes sequences where Diamond hit exists but pident < 30% (low identity).

Input: merged_detection.tsv (from merge_detection.py)
Output:
  - novel_viruses.tsv: geNomad-only detected sequences (potential novel viruses)
  - novel_summary.txt: summary statistics

Usage:
    python filter_novel_viruses.py --input merged.tsv --output novel.tsv \
        --min-hallmarks 1 --min-score 0.7 [--summary novel_summary.txt]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


# Output column order for novel_viruses.tsv
NOVEL_TSV_COLUMNS = [
    "seq_id",
    "length",
    "detection_score",
    "taxonomy",
    "viral_hallmark_count",
    "novelty_reason",
]

# Identity threshold below which a Diamond hit is considered "low identity"
LOW_IDENTITY_THRESHOLD = 30.0


def filter_novel_viruses(
    merged_tsv: Path,
    min_hallmarks: int = 1,
    min_score: float = 0.7,
) -> list[dict[str, Any]]:
    """Filter potential novel viruses from merged detection results.

    Novel viruses are:
    1. geNomad-only sequences (no Diamond protein hit) -> "no_protein_hit"
    2. Both-detected sequences with pident < 30% -> "low_identity"

    Additional filters:
    - viral_hallmark_count >= min_hallmarks
    - detection_score >= min_score

    Args:
        merged_tsv: Path to merged detection TSV.
        min_hallmarks: Minimum viral hallmark count (default: 1).
        min_score: Minimum detection score (default: 0.7).

    Returns:
        List of novel virus rows with columns matching NOVEL_TSV_COLUMNS.
    """
    rows: list[dict[str, Any]] = []

    with open(merged_tsv, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for record in reader:
            detection_method = record.get("detection_method", "")
            hallmark_count = int(record.get("viral_hallmark_count", "0") or "0")
            detection_score = float(record.get("detection_score", "0") or "0")
            pident_str = record.get("pident", "")

            # Apply quality filters
            if hallmark_count < min_hallmarks:
                continue
            if detection_score < min_score:
                continue

            # Determine novelty reason
            novelty_reason = ""

            if detection_method == "genomad":
                # geNomad-only: no Diamond protein hit
                novelty_reason = "no_protein_hit"
            elif detection_method == "both":
                # Both detected: check if identity is low
                pident = float(pident_str) if pident_str else 100.0
                if pident < LOW_IDENTITY_THRESHOLD:
                    novelty_reason = "low_identity"
                else:
                    # High identity -> known virus, skip
                    continue
            else:
                # diamond-only sequences are not novel candidates
                continue

            row = {
                "seq_id": record["seq_id"],
                "length": record.get("length", ""),
                "detection_score": record.get("detection_score", ""),
                "taxonomy": record.get("taxonomy", ""),
                "viral_hallmark_count": str(hallmark_count),
                "novelty_reason": novelty_reason,
            }
            rows.append(row)

    return rows


def write_tsv(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Write novel virus rows to a TSV file.

    Args:
        rows: List of novel virus dictionaries.
        output_path: Destination TSV file path.
    """
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=NOVEL_TSV_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, Any]], summary_path: Path) -> None:
    """Write a summary of novel virus filtering results.

    Args:
        rows: List of novel virus dictionaries.
        summary_path: Destination summary text file path.
    """
    total = len(rows)
    no_protein_hit = sum(1 for r in rows if r["novelty_reason"] == "no_protein_hit")
    low_identity = sum(1 for r in rows if r["novelty_reason"] == "low_identity")

    with open(summary_path, "w") as f:
        f.write("Novel Virus Filtering Summary\n")
        f.write("=" * 40 + "\n")
        f.write(f"Total novel virus candidates: {total}\n")
        f.write(f"  - No protein hit (geNomad-only): {no_protein_hit}\n")
        f.write(f"  - Low identity (pident < 30%): {low_identity}\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for filter_novel_viruses.py.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Filter potential novel viruses from merged detection results."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Merged detection TSV (from merge_detection.py).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output novel viruses TSV file path.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Output summary text file path (optional).",
    )
    parser.add_argument(
        "--min-hallmarks",
        type=int,
        default=1,
        help="Minimum viral hallmark count (default: 1).",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.7,
        help="Minimum detection score (default: 0.7).",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"ERROR: File not found: {args.input}", file=sys.stderr)
        return 1

    try:
        rows = filter_novel_viruses(
            args.input,
            min_hallmarks=args.min_hallmarks,
            min_score=args.min_score,
        )
    except (KeyError, ValueError) as e:
        print(f"ERROR: Failed to filter: {e}", file=sys.stderr)
        return 1

    write_tsv(rows, args.output)

    if args.summary:
        write_summary(rows, args.summary)

    print(f"Found {len(rows)} novel virus candidates.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
