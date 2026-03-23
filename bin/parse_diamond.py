#!/usr/bin/env python3
"""Parse Diamond blastx output and generate a standard detection TSV.

# @TASK T3.2 - Diamond blast6 파서
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/modules/test_diamond.py

Usage:
    python parse_diamond.py input.diamond.tsv --output detection.tsv [--min-bitscore 50]

Input:
    Diamond blast6 format TSV (outfmt 6 with 13 columns):
    qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore staxids

Output columns:
    seq_id, subject_id, pident, length, evalue, bitscore, taxid, detection_method
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


# Column names in the Diamond blast6 output (outfmt 6)
BLAST6_COLUMNS = [
    "qseqid", "sseqid", "pident", "length", "mismatch", "gapopen",
    "qstart", "qend", "sstart", "send", "evalue", "bitscore", "staxids",
]

# Column order for standard detection TSV output
TSV_COLUMNS = [
    "seq_id",
    "subject_id",
    "pident",
    "length",
    "evalue",
    "bitscore",
    "taxid",
    "detection_method",
]


def parse_blast6(input_path: Path) -> list[dict[str, str]]:
    """Parse a Diamond blast6 format TSV file.

    Args:
        input_path: Path to the Diamond output file.

    Returns:
        List of dictionaries, one per hit, with blast6 column names as keys.
    """
    hits: list[dict[str, str]] = []
    with open(input_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < len(BLAST6_COLUMNS):
                continue
            row = dict(zip(BLAST6_COLUMNS, fields))
            hits.append(row)
    return hits


def extract_best_hits(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    """Extract the best hit (highest bitscore) per query sequence.

    Args:
        hits: List of parsed blast6 hit dictionaries.

    Returns:
        List of best hits, one per unique qseqid.
    """
    best: dict[str, dict[str, str]] = {}
    for hit in hits:
        qseqid = hit["qseqid"]
        bitscore = float(hit["bitscore"])
        if qseqid not in best or bitscore > float(best[qseqid]["bitscore"]):
            best[qseqid] = hit
    return list(best.values())


def filter_by_bitscore(
    hits: list[dict[str, str]], min_bitscore: float = 50.0
) -> list[dict[str, str]]:
    """Filter hits by minimum bitscore threshold.

    Args:
        hits: List of hit dictionaries.
        min_bitscore: Minimum bitscore to keep a hit.

    Returns:
        Filtered list of hits meeting the threshold.
    """
    return [h for h in hits if float(h["bitscore"]) >= min_bitscore]


def to_detection_tsv(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    """Convert blast6 hits to standard detection TSV format.

    Args:
        hits: List of filtered best-hit dictionaries.

    Returns:
        List of dictionaries with standard detection columns.
    """
    rows: list[dict[str, str]] = []
    for hit in hits:
        # staxids may contain semicolon-separated values; take the first
        staxids = hit.get("staxids", "")
        taxid = staxids.split(";")[0] if staxids else ""

        rows.append({
            "seq_id": hit["qseqid"],
            "subject_id": hit["sseqid"],
            "pident": hit["pident"],
            "length": hit["length"],
            "evalue": hit["evalue"],
            "bitscore": hit["bitscore"],
            "taxid": taxid,
            "detection_method": "diamond",
        })
    return rows


def write_tsv(rows: list[dict[str, str]], output_path: Path) -> None:
    """Write detection rows to a TSV file.

    Args:
        rows: List of detection dictionaries.
        output_path: Destination TSV file path.
    """
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for parse_diamond.py.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Parse Diamond blastx output into a standard detection TSV."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Diamond blast6 format TSV file.",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output TSV file path.",
    )
    parser.add_argument(
        "--min-bitscore",
        type=float,
        default=50.0,
        help="Minimum bitscore threshold (default: 50).",
    )
    args = parser.parse_args(argv)

    if not args.input_file.exists():
        print(f"ERROR: File not found: {args.input_file}", file=sys.stderr)
        return 1

    hits = parse_blast6(args.input_file)
    best = extract_best_hits(hits)
    filtered = filter_by_bitscore(best, min_bitscore=args.min_bitscore)
    rows = to_detection_tsv(filtered)
    write_tsv(rows, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
