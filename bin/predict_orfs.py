#!/usr/bin/env python3
"""Parse Prodigal GFF output and compute ORF statistics per contig.

# @TASK T6.2 - ORF prediction statistics
# @SPEC docs/planning/02-trd.md#3.2-pipeline-stages
# @TEST tests/modules/test_novel_discovery.py

Parses Prodigal GFF3 output to extract CDS features and compute per-contig
ORF statistics: count, average length, longest ORF, and coding density.

Usage:
    python predict_orfs.py --gff novel.genes.gff --output orf_stats.tsv
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
ORF_TSV_COLUMNS = [
    "seq_id",
    "num_orfs",
    "avg_orf_length",
    "longest_orf",
    "coding_density",
]


def parse_gff_stats(gff_path: Path) -> list[dict[str, Any]]:
    """Parse a Prodigal GFF file and compute ORF statistics per contig.

    Reads "# Sequence Data:" comment lines for contig lengths, and CDS
    feature lines for ORF coordinates.

    Args:
        gff_path: Path to Prodigal GFF output file.

    Returns:
        List of ORF statistics rows with columns matching ORF_TSV_COLUMNS.
    """
    # Track ORF lengths per contig and sequence lengths
    contig_orfs: dict[str, list[int]] = defaultdict(list)
    contig_lengths: dict[str, int] = {}

    # Pattern for Sequence Data comment lines
    seqdata_re = re.compile(
        r"#\s*Sequence Data:.*seqlen=(\d+);seqhdr=\"([^\"]+)\""
    )

    with open(gff_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # Parse sequence metadata comments
            m = seqdata_re.match(line)
            if m:
                seqlen = int(m.group(1))
                seqhdr = m.group(2).split()[0]  # take first word as seq_id
                contig_lengths[seqhdr] = seqlen
                continue

            # Skip other comment lines
            if line.startswith("#"):
                continue

            # Parse CDS feature lines (GFF3 tab-separated)
            parts = line.split("\t")
            if len(parts) < 9:
                continue
            if parts[2] != "CDS":
                continue

            seq_id = parts[0]
            start = int(parts[3])
            end = int(parts[4])
            orf_length = end - start + 1
            contig_orfs[seq_id].append(orf_length)

    # Build output rows (only contigs that have ORFs)
    rows: list[dict[str, Any]] = []
    for seq_id in sorted(contig_orfs.keys()):
        lengths = contig_orfs[seq_id]
        num_orfs = len(lengths)
        avg_orf_length = sum(lengths) / num_orfs if num_orfs > 0 else 0.0
        longest_orf = max(lengths) if lengths else 0
        total_cds = sum(lengths)
        seq_len = contig_lengths.get(seq_id, 0)
        coding_density = total_cds / seq_len if seq_len > 0 else 0.0

        row = {
            "seq_id": seq_id,
            "num_orfs": str(num_orfs),
            "avg_orf_length": f"{avg_orf_length:.2f}",
            "longest_orf": str(longest_orf),
            "coding_density": f"{coding_density:.4f}",
        }
        rows.append(row)

    return rows


def write_tsv(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Write ORF statistics rows to a TSV file.

    Args:
        rows: List of ORF statistics dictionaries.
        output_path: Destination TSV file path.
    """
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ORF_TSV_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for predict_orfs.py.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Parse Prodigal GFF output and compute ORF statistics per contig."
    )
    parser.add_argument(
        "--gff",
        type=Path,
        required=True,
        help="Prodigal GFF output file.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output ORF statistics TSV file path.",
    )
    args = parser.parse_args(argv)

    if not args.gff.exists():
        print(f"ERROR: File not found: {args.gff}", file=sys.stderr)
        return 1

    try:
        rows = parse_gff_stats(args.gff)
    except (KeyError, ValueError) as e:
        print(f"ERROR: Failed to parse GFF: {e}", file=sys.stderr)
        return 1

    write_tsv(rows, args.output)
    print(f"Computed ORF stats for {len(rows)} contigs.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
