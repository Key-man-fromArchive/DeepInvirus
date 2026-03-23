#!/usr/bin/env python3
"""Parse samtools flagstat output and generate host removal statistics TSV.

# @TASK T1.2 - Host removal statistics parser
# @SPEC docs/planning/02-trd.md#2.2-분석-도구

Usage:
    parse_host_removal.py --sample <name> --flagstat <file> [--output <file>]

Output columns:
    sample, total_reads, mapped_reads, unmapped_reads, host_removal_rate
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path


# Column order for the output TSV
TSV_COLUMNS = [
    "sample",
    "total_reads",
    "mapped_reads",
    "unmapped_reads",
    "host_removal_rate",
]


def parse_flagstat(flagstat_text: str) -> dict[str, int]:
    """Parse samtools flagstat output into a dictionary.

    Args:
        flagstat_text: Full text of samtools flagstat output.

    Returns:
        Dictionary with keys:
            - total: Total QC-passed reads (including secondary/supplementary)
            - primary: Primary reads count
            - mapped: Total mapped reads
            - primary_mapped: Primary mapped reads
            - secondary: Secondary alignment count
            - supplementary: Supplementary alignment count

    Raises:
        ValueError: If required lines are missing from flagstat output.
    """
    result: dict[str, int] = {
        "total": 0,
        "primary": 0,
        "mapped": 0,
        "primary_mapped": 0,
        "secondary": 0,
        "supplementary": 0,
    }

    lines = flagstat_text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Extract the first number (QC-passed count)
        match = re.match(r"(\d+)\s+\+\s+\d+", line)
        if not match:
            continue

        count = int(match.group(1))

        if "in total" in line:
            result["total"] = count
        elif "primary mapped" in line:
            result["primary_mapped"] = count
        elif "primary" in line and "duplicates" not in line:
            result["primary"] = count
        elif "secondary" in line:
            result["secondary"] = count
        elif "supplementary" in line:
            result["supplementary"] = count
        elif "mapped" in line and "primary" not in line and "mate" not in line and "with itself" not in line:
            result["mapped"] = count

    return result


def calculate_host_removal_stats(
    sample_name: str,
    flagstat: dict[str, int],
) -> dict[str, str | int | float]:
    """Calculate host removal statistics from parsed flagstat data.

    Uses primary reads as the denominator (excludes secondary/supplementary).
    Mapped primary reads are considered host reads.

    Args:
        sample_name: Sample identifier.
        flagstat: Parsed flagstat dictionary from parse_flagstat().

    Returns:
        Dictionary with keys matching TSV_COLUMNS:
            - sample: Sample name
            - total_reads: Primary read count
            - mapped_reads: Host reads (primary mapped)
            - unmapped_reads: Non-host reads (primary - primary_mapped)
            - host_removal_rate: Percentage of host reads (0.0-100.0)
    """
    total_reads = flagstat["primary"]
    mapped_reads = flagstat["primary_mapped"]
    unmapped_reads = total_reads - mapped_reads

    if total_reads > 0:
        host_removal_rate = (mapped_reads / total_reads) * 100.0
    else:
        host_removal_rate = 0.0

    return {
        "sample": sample_name,
        "total_reads": total_reads,
        "mapped_reads": mapped_reads,
        "unmapped_reads": unmapped_reads,
        "host_removal_rate": host_removal_rate,
    }


def format_stats_tsv(stats_list: list[dict]) -> str:
    """Format a list of stats dictionaries into TSV string.

    Args:
        stats_list: List of dictionaries from calculate_host_removal_stats().

    Returns:
        TSV-formatted string with header and data rows.
    """
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=TSV_COLUMNS,
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()

    for stats in stats_list:
        row = {
            "sample": stats["sample"],
            "total_reads": str(stats["total_reads"]),
            "mapped_reads": str(stats["mapped_reads"]),
            "unmapped_reads": str(stats["unmapped_reads"]),
            "host_removal_rate": f"{stats['host_removal_rate']:.2f}",
        }
        writer.writerow(row)

    return output.getvalue()


def main() -> None:
    """CLI entry point for parse_host_removal.py."""
    parser = argparse.ArgumentParser(
        description="Parse samtools flagstat output for host removal statistics."
    )
    parser.add_argument(
        "--sample",
        required=True,
        help="Sample name/identifier.",
    )
    parser.add_argument(
        "--flagstat",
        required=True,
        type=Path,
        help="Path to samtools flagstat output file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output TSV file path (default: stdout).",
    )

    args = parser.parse_args()

    # Read flagstat file
    flagstat_text = args.flagstat.read_text()
    flagstat = parse_flagstat(flagstat_text)
    stats = calculate_host_removal_stats(args.sample, flagstat)
    tsv_output = format_stats_tsv([stats])

    if args.output:
        args.output.write_text(tsv_output)
    else:
        sys.stdout.write(tsv_output)


if __name__ == "__main__":
    main()
