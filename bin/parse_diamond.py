#!/usr/bin/env python3
"""Parse Diamond blastx output and generate a standard detection TSV.

# @TASK T3.2 - Diamond blast6 파서
# @TASK A3 - skip_ml Diamond schema 변환
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/modules/test_diamond.py

Usage:
    python parse_diamond.py input.diamond.tsv --output detection.tsv [--min-bitscore 50]
    python parse_diamond.py input.diamond.tsv --output merged.tsv --merged-format [--min-bitscore 50]

Input:
    Diamond blast6 format TSV (outfmt 6 with 12 or 13 columns):
    qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore [staxids]
    When staxids (column 13) is absent, taxid defaults to "0" (unknown).

Output columns (default):
    seq_id, subject_id, pident, length, evalue, bitscore, taxid, detection_method

Output columns (--merged-format, compatible with merge_results.py):
    seq_id, length, detection_method, detection_score, taxonomy, taxid, subject_id
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


# Column names in the Diamond blast6 output (outfmt 6)
# The first 12 columns are mandatory; staxids (column 13) is optional because
# Diamond only emits it when a taxonomy database (--taxonmap/--taxonnodes) is
# available.  When staxids is absent we default to "0" (unknown taxid).
BLAST6_COLUMNS = [
    "qseqid", "sseqid", "pident", "length", "mismatch", "gapopen",
    "qstart", "qend", "sstart", "send", "evalue", "bitscore", "staxids",
]
BLAST6_MIN_COLUMNS = 12  # minimum required (without staxids)

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

# Column order for merged detection TSV output (compatible with merge_results.py)
# Used when --merged-format flag is set (skip_ml=true pathway)
MERGED_TSV_COLUMNS = [
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
            if len(fields) < BLAST6_MIN_COLUMNS:
                continue
            row = dict(zip(BLAST6_COLUMNS, fields))
            # When staxids column is missing (12-column input), default to "0"
            if "staxids" not in row:
                row["staxids"] = "0"
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
        # staxids may contain semicolon-separated values; take the first.
        # Default to "0" (unknown) when staxids is missing or empty.
        staxids = hit.get("staxids", "0")
        taxid = staxids.split(";")[0] if staxids else "0"

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


def to_merged_detection_tsv(hits: list[dict[str, str]]) -> list[dict[str, str]]:
    """Convert blast6 hits to merged detection TSV format.

    This produces output compatible with merge_results.py downstream when
    skip_ml=true (Diamond-only detection without geNomad).

    Output columns: seq_id, length, detection_method, detection_score,
                    taxonomy, taxid, subject_id

    Args:
        hits: List of filtered best-hit dictionaries.

    Returns:
        List of dictionaries with merged detection columns.
    """
    rows: list[dict[str, str]] = []
    for hit in hits:
        staxids = hit.get("staxids", "0")
        taxid = staxids.split(";")[0] if staxids else "0"
        bitscore = float(hit["bitscore"])
        detection_score = normalize_bitscore(bitscore)

        rows.append({
            "seq_id": hit["qseqid"],
            "length": hit["length"],
            "detection_method": "diamond",
            "detection_score": str(round(detection_score, 6)),
            "taxonomy": "",
            "taxid": taxid,
            "subject_id": hit["sseqid"],
        })
    return rows


def write_tsv(
    rows: list[dict[str, str]],
    output_path: Path,
    columns: list[str] | None = None,
) -> None:
    """Write detection rows to a TSV file.

    Args:
        rows: List of detection dictionaries.
        output_path: Destination TSV file path.
        columns: Column order for output. Defaults to TSV_COLUMNS.
    """
    if columns is None:
        columns = TSV_COLUMNS
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter="\t")
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
    parser.add_argument(
        "--merged-format",
        action="store_true",
        default=False,
        help=(
            "Output in merged detection format compatible with merge_results.py. "
            "Columns: seq_id, length, detection_method, detection_score, "
            "taxonomy, taxid, subject_id. "
            "Used when skip_ml=true (Diamond-only detection)."
        ),
    )
    args = parser.parse_args(argv)

    if not args.input_file.exists():
        print(f"ERROR: File not found: {args.input_file}", file=sys.stderr)
        return 1

    hits = parse_blast6(args.input_file)
    best = extract_best_hits(hits)
    filtered = filter_by_bitscore(best, min_bitscore=args.min_bitscore)

    if args.merged_format:
        rows = to_merged_detection_tsv(filtered)
        write_tsv(rows, args.output, columns=MERGED_TSV_COLUMNS)
    else:
        rows = to_detection_tsv(filtered)
        write_tsv(rows, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
