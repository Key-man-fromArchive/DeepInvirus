#!/usr/bin/env python3
"""Find closest known virus for novel virus predicted proteins.

# @TASK T6.3 - Closest known virus search
# @SPEC docs/planning/02-trd.md#3.2-pipeline-stages
# @TEST tests/modules/test_novel_discovery.py

Parses Diamond blastp results to find the closest known virus for each
novel virus contig based on best protein hit (highest bitscore).

Input: Diamond blastp output (outfmt 6 with headers)
Output: closest_viruses.tsv

Usage:
    python find_closest_virus.py --blastp-results blastp.tsv --output closest.tsv \
        [--novel-contigs contig_2,contig_4,contig_99]
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


# Output column order
CLOSEST_TSV_COLUMNS = [
    "seq_id",
    "closest_virus_name",
    "closest_virus_taxid",
    "pident",
    "evalue",
    "bitscore",
    "query_coverage",
]

# Pattern to extract contig name from ORF query ID (e.g., contig_2_1 -> contig_2)
ORF_ID_RE = re.compile(r"^(.+)_\d+$")


def _extract_contig_id(qseqid: str) -> str:
    """Extract contig ID from a Prodigal ORF query ID.

    Prodigal names ORFs as {contig}_{orf_num}, e.g., contig_2_1 -> contig_2.

    Args:
        qseqid: Query sequence ID from blastp results.

    Returns:
        Contig-level ID.
    """
    m = ORF_ID_RE.match(qseqid)
    if m:
        return m.group(1)
    return qseqid


def parse_blastp_results(
    blastp_tsv: Path,
    novel_contigs: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Parse Diamond blastp results and find best hit per contig.

    For each contig, selects the ORF hit with the highest bitscore as the
    "closest known virus".

    Args:
        blastp_tsv: Path to Diamond blastp output TSV.
        novel_contigs: Optional list of novel contig IDs. If provided,
            contigs with no hit will appear with "No significant hit".

    Returns:
        List of closest virus rows with columns matching CLOSEST_TSV_COLUMNS.
    """
    # Collect all hits per contig, keeping the best (highest bitscore)
    best_hits: dict[str, dict[str, Any]] = {}

    with open(blastp_tsv, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for record in reader:
            qseqid = record.get("qseqid", "")
            contig_id = _extract_contig_id(qseqid)
            bitscore = float(record.get("bitscore", "0"))

            if contig_id not in best_hits or bitscore > float(best_hits[contig_id]["bitscore"]):
                best_hits[contig_id] = {
                    "seq_id": contig_id,
                    "closest_virus_name": record.get("stitle", ""),
                    "closest_virus_taxid": record.get("staxids", ""),
                    "pident": record.get("pident", ""),
                    "evalue": record.get("evalue", ""),
                    "bitscore": record.get("bitscore", ""),
                    "query_coverage": record.get("qcovs", ""),
                }

    # Build output rows
    rows: list[dict[str, Any]] = []

    if novel_contigs is not None:
        # Include all novel contigs, marking those with no hit
        for contig_id in sorted(novel_contigs):
            if contig_id in best_hits:
                rows.append(best_hits[contig_id])
            else:
                rows.append({
                    "seq_id": contig_id,
                    "closest_virus_name": "No significant hit",
                    "closest_virus_taxid": "",
                    "pident": "",
                    "evalue": "",
                    "bitscore": "",
                    "query_coverage": "",
                })
    else:
        # Just return contigs that have hits
        for contig_id in sorted(best_hits.keys()):
            rows.append(best_hits[contig_id])

    return rows


def write_tsv(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Write closest virus rows to a TSV file.

    Args:
        rows: List of closest virus dictionaries.
        output_path: Destination TSV file path.
    """
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CLOSEST_TSV_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for find_closest_virus.py.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Find closest known virus for novel virus predicted proteins."
    )
    parser.add_argument(
        "--blastp-results",
        type=Path,
        required=True,
        help="Diamond blastp output TSV.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output closest viruses TSV file path.",
    )
    parser.add_argument(
        "--novel-contigs",
        type=str,
        default=None,
        help="Comma-separated list of novel contig IDs (for no-hit marking).",
    )
    args = parser.parse_args(argv)

    if not args.blastp_results.exists():
        print(f"ERROR: File not found: {args.blastp_results}", file=sys.stderr)
        return 1

    novel_contigs = None
    if args.novel_contigs:
        novel_contigs = [c.strip() for c in args.novel_contigs.split(",")]

    try:
        rows = parse_blastp_results(args.blastp_results, novel_contigs=novel_contigs)
    except (KeyError, ValueError) as e:
        print(f"ERROR: Failed to parse blastp results: {e}", file=sys.stderr)
        return 1

    write_tsv(rows, args.output)
    print(f"Found closest viruses for {len(rows)} contigs.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
