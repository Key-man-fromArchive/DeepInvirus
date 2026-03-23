#!/usr/bin/env python3
"""Parse assembly FASTA files and generate assembly statistics TSV.

# @TASK T2.1 - Assembly statistics parser
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

Reads contig FASTA files produced by MEGAHIT or metaSPAdes and computes:
    - num_contigs: number of contigs
    - total_length: sum of all contig lengths
    - largest_contig: length of the longest contig
    - n50: N50 metric
    - gc_content: fraction of G+C bases

Usage:
    python parse_assembly_stats.py sample1.contigs.fa [sample2.contigs.fa ...] \\
        --assembler megahit --output assembly_stats.tsv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def parse_fasta_sequences(fasta_path: Path) -> list[str]:
    """Read a FASTA file and return a list of sequences (one per contig).

    Args:
        fasta_path: Path to the FASTA file.

    Returns:
        List of nucleotide sequence strings.
    """
    sequences: list[str] = []
    current_seq: list[str] = []

    with open(fasta_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_seq:
                    sequences.append("".join(current_seq))
                    current_seq = []
            else:
                current_seq.append(line.upper())

    if current_seq:
        sequences.append("".join(current_seq))

    return sequences


def calc_n50(lengths: list[int]) -> int:
    """Calculate the N50 metric from a list of contig lengths.

    Args:
        lengths: List of contig lengths (positive integers).

    Returns:
        N50 value. Returns 0 if lengths is empty.
    """
    if not lengths:
        return 0

    sorted_lengths = sorted(lengths, reverse=True)
    total = sum(sorted_lengths)
    half = total / 2.0
    cumulative = 0

    for length in sorted_lengths:
        cumulative += length
        if cumulative >= half:
            return length

    return sorted_lengths[-1]


def calc_gc_content(sequences: list[str]) -> float:
    """Calculate GC content across all sequences.

    Args:
        sequences: List of nucleotide sequence strings.

    Returns:
        Fraction of G+C bases (0.0 to 1.0). Returns 0.0 if no bases.
    """
    if not sequences:
        return 0.0

    total_bases = 0
    gc_bases = 0

    for seq in sequences:
        total_bases += len(seq)
        gc_bases += seq.count("G") + seq.count("C")

    if total_bases == 0:
        return 0.0

    return gc_bases / total_bases


def parse_assembly_fasta(
    fasta_path: Path,
    sample_name: str,
    assembler: str,
) -> dict:
    """Parse a single assembly FASTA file and compute statistics.

    Args:
        fasta_path: Path to the assembly contig FASTA file.
        sample_name: Sample identifier.
        assembler: Assembler name (e.g., 'megahit', 'metaspades').

    Returns:
        Dictionary with keys: sample, assembler, num_contigs, total_length,
        largest_contig, n50, gc_content.
    """
    sequences = parse_fasta_sequences(fasta_path)
    lengths = [len(seq) for seq in sequences]

    return {
        "sample": sample_name,
        "assembler": assembler,
        "num_contigs": len(lengths),
        "total_length": sum(lengths) if lengths else 0,
        "largest_contig": max(lengths) if lengths else 0,
        "n50": calc_n50(lengths),
        "gc_content": round(calc_gc_content(sequences), 6),
    }


def derive_sample_name(fasta_path: Path) -> str:
    """Derive sample name from FASTA filename.

    Args:
        fasta_path: Path to FASTA file.

    Returns:
        Sample name derived by stripping known suffixes.

    Examples:
        sample1.contigs.fa -> sample1
        sampleA.fasta -> sampleA
    """
    name = fasta_path.name
    for suffix in [".contigs.fa", ".contigs.fasta", ".fasta", ".fa"]:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return fasta_path.stem


def main() -> None:
    """CLI entry point for parse_assembly_stats.py."""
    parser = argparse.ArgumentParser(
        description="Parse assembly FASTA files and generate statistics TSV."
    )
    parser.add_argument(
        "fasta_files",
        nargs="+",
        type=Path,
        help="One or more assembly contig FASTA files.",
    )
    parser.add_argument(
        "--assembler",
        type=str,
        default="megahit",
        help="Assembler name (default: megahit).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output TSV file path.",
    )

    args = parser.parse_args()

    columns = [
        "sample",
        "assembler",
        "num_contigs",
        "total_length",
        "largest_contig",
        "n50",
        "gc_content",
    ]

    rows: list[dict] = []
    for fasta_path in args.fasta_files:
        sample_name = derive_sample_name(fasta_path)
        result = parse_assembly_fasta(fasta_path, sample_name, args.assembler)
        rows.append(result)

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
