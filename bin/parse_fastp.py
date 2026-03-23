#!/usr/bin/env python3
"""Parse fastp JSON report(s) and generate a QC summary TSV.

# @TASK T1.1 - fastp JSON 파서
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/modules/test_fastp.py

Usage:
    python parse_fastp.py sample1.fastp.json [sample2.fastp.json ...] --output qc_summary.tsv

Output columns:
    sample, total_reads_before, total_reads_after, q30_rate_before,
    q30_rate_after, gc_content, duplication_rate, adapter_trimmed_rate
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


# Column order for TSV output
TSV_COLUMNS = [
    "sample",
    "total_reads_before",
    "total_reads_after",
    "q30_rate_before",
    "q30_rate_after",
    "gc_content",
    "duplication_rate",
    "adapter_trimmed_rate",
]


def parse_fastp_json(data: dict[str, Any], sample_name: str) -> dict[str, Any]:
    """Extract QC metrics from a fastp JSON report.

    Args:
        data: Parsed fastp JSON as a dictionary.
        sample_name: Sample identifier for the output row.

    Returns:
        Dictionary with keys matching TSV_COLUMNS.

    Raises:
        KeyError: If required JSON fields are missing.
    """
    before = data["summary"]["before_filtering"]
    after = data["summary"]["after_filtering"]

    total_reads_before = before["total_reads"]

    # adapter_cutting section may be absent if adapters were not detected
    adapter_section = data.get("adapter_cutting", {})
    adapter_trimmed_reads = adapter_section.get("adapter_trimmed_reads", 0)

    adapter_trimmed_rate = (
        adapter_trimmed_reads / total_reads_before
        if total_reads_before > 0
        else 0.0
    )

    return {
        "sample": sample_name,
        "total_reads_before": total_reads_before,
        "total_reads_after": after["total_reads"],
        "q30_rate_before": before["q30_rate"],
        "q30_rate_after": after["q30_rate"],
        "gc_content": after["gc_content"],
        "duplication_rate": data["duplication"]["rate"],
        "adapter_trimmed_rate": round(adapter_trimmed_rate, 6),
    }


def infer_sample_name(json_path: Path) -> str:
    """Infer sample name from fastp JSON filename.

    Args:
        json_path: Path to the fastp JSON file.

    Returns:
        Sample name derived from filename (strip '.fastp.json' suffix).

    Examples:
        >>> infer_sample_name(Path("sample1.fastp.json"))
        'sample1'
        >>> infer_sample_name(Path("/path/to/SRR123.fastp.json"))
        'SRR123'
    """
    name = json_path.name
    if name.endswith(".fastp.json"):
        return name[: -len(".fastp.json")]
    return json_path.stem


def write_tsv(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Write parsed QC rows to a TSV file.

    Args:
        rows: List of dictionaries (one per sample).
        output_path: Destination TSV file path.
    """
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TSV_COLUMNS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for parse_fastp.py.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Parse fastp JSON report(s) into a QC summary TSV."
    )
    parser.add_argument(
        "json_files",
        nargs="+",
        type=Path,
        help="One or more fastp JSON report files.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Output TSV file path.",
    )
    args = parser.parse_args(argv)

    rows: list[dict[str, Any]] = []
    for json_path in args.json_files:
        if not json_path.exists():
            print(f"ERROR: File not found: {json_path}", file=sys.stderr)
            return 1

        try:
            with open(json_path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in {json_path}: {e}", file=sys.stderr)
            return 1

        sample_name = infer_sample_name(json_path)
        try:
            row = parse_fastp_json(data, sample_name=sample_name)
        except KeyError as e:
            print(
                f"ERROR: Missing field {e} in {json_path}", file=sys.stderr
            )
            return 1

        rows.append(row)

    write_tsv(rows, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
