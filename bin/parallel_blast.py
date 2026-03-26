#!/usr/bin/env python3
# @TASK T3.1 - Parallel BLAST/Diamond execution with chunk splitting
# @SPEC docs/planning/02-trd.md#parallel-blast
# @TEST tests/test_parallel_blast.py
"""
Parallel BLAST runner for DeepInvirus.

Ported from Blast_ripper-meta_v4_dmnd.py -- extracts the core parallel
BLAST execution logic (chunk splitting, multiprocessing, RAM disk I/O,
result merging) into a standalone CLI script.

Supports blastn, blastx, and diamond blastx.

Usage::

    python parallel_blast.py \\
        --query contigs.fa \\
        --db viral_nt \\
        --program blastn \\
        --output results.tsv \\
        --num-chunks 16 \\
        --threads-per-chunk 1 \\
        --use-ramdisk \\
        --evalue 1e-10 \\
        --max-target-seqs 5 \\
        --outfmt '6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore staxids'
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool, cpu_count
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging -- stderr only (Nextflow captures stdout for channel piping)
# ---------------------------------------------------------------------------

logger = logging.getLogger("parallel_blast")


def setup_logging(verbosity: int = 0) -> None:
    """Configure logging to stderr.

    Args:
        verbosity: 0 = WARNING, 1 = INFO, 2+ = DEBUG.
    """
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.setLevel(level)
    logger.addHandler(handler)


# ---------------------------------------------------------------------------
# FASTA chunk splitting (no BioPython dependency)
# ---------------------------------------------------------------------------


def count_fasta_records(file_path: str) -> int:
    """Count the number of FASTA records in *file_path*.

    Counts lines starting with ``>``.
    """
    count = 0
    with open(file_path) as fh:
        for line in fh:
            if line.startswith(">"):
                count += 1
    return count


def chunk_fasta(
    file_path: str,
    num_chunks: int,
    temp_dir: str | None = None,
) -> list[str]:
    """Split a FASTA file into *num_chunks* roughly equal temporary files.

    The function reads records one at a time so that memory usage stays
    constant regardless of input size.

    Args:
        file_path: Path to input FASTA.
        num_chunks: Desired number of output chunks.
        temp_dir: Directory for temporary chunk files.  Defaults to the
            system temp directory.

    Returns:
        List of chunk file paths.
    """
    total_records = count_fasta_records(file_path)
    if total_records == 0:
        logger.warning("Input FASTA '%s' contains no records", file_path)
        return []

    # Adjust chunks if fewer records than requested chunks
    actual_chunks = min(num_chunks, total_records)
    records_per_chunk = max(1, total_records // actual_chunks)

    logger.info(
        "Splitting %d records into %d chunks (~%d records each)",
        total_records,
        actual_chunks,
        records_per_chunk,
    )

    chunk_paths: list[str] = []
    current_fh = None
    current_count = 0
    chunk_index = 0

    def _open_new_chunk() -> "tempfile._TemporaryFileWrapper":
        nonlocal chunk_index
        fh = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=f".chunk{chunk_index}.fasta",
            dir=temp_dir,
            delete=False,
        )
        chunk_paths.append(fh.name)
        chunk_index += 1
        return fh

    with open(file_path) as infile:
        for line in infile:
            if line.startswith(">"):
                # Start of a new record -- should we open a new chunk?
                need_new_chunk = (
                    current_fh is None
                    or (
                        current_count >= records_per_chunk
                        and chunk_index < actual_chunks
                    )
                )
                if need_new_chunk:
                    if current_fh is not None:
                        current_fh.close()
                    current_fh = _open_new_chunk()
                    current_count = 0
                current_count += 1
            if current_fh is not None:
                current_fh.write(line)

    if current_fh is not None:
        current_fh.close()

    logger.info("Created %d chunk files", len(chunk_paths))
    return chunk_paths


# ---------------------------------------------------------------------------
# Single-chunk BLAST execution
# ---------------------------------------------------------------------------

# This is a module-level function so that multiprocessing.Pool can pickle it.


def _run_blast_on_chunk(args_tuple: tuple) -> str | None:
    """Run BLAST/Diamond on a single chunk file.

    This is a module-level function (not a closure) because
    ``multiprocessing.Pool.map`` needs picklable callables.

    Args:
        args_tuple: A tuple of
            (chunk_path, db, out_path, program, threads, evalue,
             max_target_seqs, outfmt, use_ramdisk, extra_args)

    Returns:
        The output file path on success, ``None`` on failure.
    """
    (
        chunk_path,
        db,
        out_path,
        program,
        threads,
        evalue,
        max_target_seqs,
        outfmt,
        use_ramdisk,
        extra_args,
    ) = args_tuple

    # --- RAM disk I/O acceleration ---
    if use_ramdisk:
        ramdisk_chunk = os.path.join("/dev/shm", os.path.basename(chunk_path))
        ramdisk_out = os.path.join("/dev/shm", os.path.basename(out_path))
        shutil.copy2(chunk_path, ramdisk_chunk)
        effective_chunk = ramdisk_chunk
        effective_out = ramdisk_out
    else:
        effective_chunk = chunk_path
        effective_out = out_path

    # --- Build command ---
    cmd: list[str] = _build_blast_cmd(
        program=program,
        query=effective_chunk,
        db=db,
        out=effective_out,
        threads=threads,
        evalue=evalue,
        max_target_seqs=max_target_seqs,
        outfmt=outfmt,
        extra_args=extra_args,
    )

    logger.info("Running: %s", " ".join(cmd))
    t0 = time.monotonic()

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=360_000,  # 100 hours -- generous for large DBs
        )
        if result.stderr:
            logger.debug("stderr from %s: %s", program, result.stderr.strip())
    except subprocess.TimeoutExpired:
        logger.error("Timeout for chunk %s", chunk_path)
        _cleanup_ramdisk(use_ramdisk, ramdisk_chunk if use_ramdisk else None, None)
        return None
    except subprocess.CalledProcessError as exc:
        logger.error("BLAST failed for chunk %s: %s", chunk_path, exc.stderr)
        _cleanup_ramdisk(use_ramdisk, ramdisk_chunk if use_ramdisk else None, None)
        return None

    elapsed = time.monotonic() - t0
    logger.info("Chunk %s completed in %.1f s", os.path.basename(chunk_path), elapsed)

    # --- Move results back from RAM disk ---
    if use_ramdisk:
        shutil.move(effective_out, out_path)
        os.remove(ramdisk_chunk)

    return out_path


def _cleanup_ramdisk(
    use_ramdisk: bool,
    chunk: str | None,
    out: str | None,
) -> None:
    """Best-effort cleanup of RAM disk temp files."""
    if not use_ramdisk:
        return
    for path in (chunk, out):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


def _build_blast_cmd(
    program: str,
    query: str,
    db: str,
    out: str,
    threads: int,
    evalue: str,
    max_target_seqs: int,
    outfmt: str,
    extra_args: list[str],
) -> list[str]:
    """Build the BLAST/Diamond command as a list of strings.

    Args:
        program: One of ``blastn``, ``blastx``, ``diamond``.
        query: Query FASTA file path.
        db: Database path.
        out: Output file path.
        threads: Number of threads.
        evalue: E-value threshold as string.
        max_target_seqs: Maximum target sequences.
        outfmt: Output format string (e.g. ``"6 qseqid sseqid ..."``).
        extra_args: Additional CLI arguments passed through verbatim.

    Returns:
        Command as a list of strings suitable for ``subprocess.run``.
    """
    if program in ("blastn", "blastx"):
        cmd = [
            program,
            "-query", query,
            "-db", db,
            "-out", out,
            "-num_threads", str(threads),
            "-evalue", evalue,
            "-max_target_seqs", str(max_target_seqs),
            "-outfmt", outfmt,
        ]
    elif program == "diamond":
        # Diamond uses different flag names
        # Parse outfmt: if it starts with "6 " strip the "6 " prefix
        # and split into individual fields for diamond --outfmt 6 field1 field2 ...
        fmt_parts = outfmt.strip().split()
        cmd = [
            "diamond", "blastx",
            "--query", query,
            "--db", db,
            "--out", out,
            "--threads", str(threads),
            "--evalue", evalue,
            "--max-target-seqs", str(max_target_seqs),
            "--outfmt",
        ] + fmt_parts
    else:
        raise ValueError(f"Unsupported program: {program!r}")

    cmd.extend(extra_args)
    return cmd


# ---------------------------------------------------------------------------
# Parallel orchestration
# ---------------------------------------------------------------------------


def run_parallel_blast(
    query: str,
    db: str,
    output: str,
    program: str = "blastn",
    num_chunks: int = 8,
    threads_per_chunk: int = 1,
    use_ramdisk: bool = False,
    evalue: str = "1e-10",
    max_target_seqs: int = 5,
    outfmt: str = "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore staxids",
    extra_args: list[str] | None = None,
) -> str:
    """Split *query* into chunks, run BLAST in parallel, merge results.

    Args:
        query: Path to input FASTA file.
        db: Path to BLAST/Diamond database.
        output: Path to write merged results.
        program: ``blastn``, ``blastx``, or ``diamond``.
        num_chunks: Number of parallel chunks.
        threads_per_chunk: Threads allocated to each BLAST process.
        use_ramdisk: Copy chunks to ``/dev/shm`` for I/O acceleration.
        evalue: E-value cutoff.
        max_target_seqs: Maximum target sequences per query.
        outfmt: Output format string.
        extra_args: Extra CLI args passed to the BLAST binary.

    Returns:
        Path to the merged output file.

    Raises:
        FileNotFoundError: If *query* does not exist.
        RuntimeError: If all BLAST chunks fail.
    """
    if not os.path.isfile(query):
        raise FileNotFoundError(f"Query file not found: {query}")

    extra = extra_args or []
    out_dir = os.path.dirname(os.path.abspath(output)) or "."
    os.makedirs(out_dir, exist_ok=True)

    # Determine temp directory for chunks
    chunk_temp_dir = "/dev/shm" if use_ramdisk else out_dir

    # 1) Split FASTA into chunks
    t0 = time.monotonic()
    chunks = chunk_fasta(query, num_chunks, temp_dir=chunk_temp_dir)
    if not chunks:
        logger.warning("No chunks created -- writing empty output")
        Path(output).touch()
        return output
    logger.info("Chunking took %.1f s", time.monotonic() - t0)

    # 2) Prepare arguments for each chunk
    pool_args = []
    chunk_outputs: list[str] = []
    for i, chunk_path in enumerate(chunks):
        chunk_out = os.path.join(out_dir, f"_chunk_{i:04d}.blast.tsv")
        chunk_outputs.append(chunk_out)
        pool_args.append((
            chunk_path,
            db,
            chunk_out,
            program,
            threads_per_chunk,
            evalue,
            max_target_seqs,
            outfmt,
            use_ramdisk,
            extra,
        ))

    # 3) Run in parallel
    max_workers = min(len(chunks), cpu_count())
    logger.info(
        "Launching %d BLAST processes (max workers: %d, threads/chunk: %d)",
        len(chunks),
        max_workers,
        threads_per_chunk,
    )

    t0 = time.monotonic()
    with Pool(processes=max_workers) as pool:
        results = pool.map(_run_blast_on_chunk, pool_args)
    elapsed = time.monotonic() - t0

    success_count = sum(1 for r in results if r is not None)
    fail_count = len(results) - success_count
    logger.info(
        "BLAST completed in %.1f s  (success=%d, failed=%d)",
        elapsed,
        success_count,
        fail_count,
    )

    if success_count == 0:
        raise RuntimeError(
            "All BLAST chunks failed. Check logs for details."
        )
    if fail_count > 0:
        logger.warning("%d chunk(s) failed -- partial results will be merged", fail_count)

    # 4) Merge results
    logger.info("Merging %d result files into %s", success_count, output)
    with open(output, "w") as out_fh:
        for result_path in results:
            if result_path and os.path.isfile(result_path):
                with open(result_path) as in_fh:
                    for line in in_fh:
                        out_fh.write(line)

    # 5) Cleanup temp files
    for chunk_path in chunks:
        _safe_remove(chunk_path)
    for chunk_out in chunk_outputs:
        _safe_remove(chunk_out)

    output_size = os.path.getsize(output) if os.path.isfile(output) else 0
    logger.info("Merged output: %s (%.2f MB)", output, output_size / 1024 / 1024)
    return output


def _safe_remove(path: str) -> None:
    """Remove a file, ignoring errors."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        logger.debug("Could not remove %s: %s", path, exc)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="parallel_blast",
        description=(
            "Parallel BLAST/Diamond runner for DeepInvirus. "
            "Splits a FASTA query into chunks, runs BLAST in parallel "
            "using multiprocessing, and merges the results."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # blastn with 16 chunks on RAM disk\n"
            "  %(prog)s --query contigs.fa --db viral_nt --program blastn \\\n"
            "      --output results.tsv --num-chunks 16 --use-ramdisk\n"
            "\n"
            "  # diamond blastx with custom outfmt\n"
            "  %(prog)s --query contigs.fa --db viral_nr.dmnd --program diamond \\\n"
            "      --output results.tsv --num-chunks 8 --threads-per-chunk 4 \\\n"
            "      --outfmt '6 qseqid sseqid pident length evalue bitscore'\n"
        ),
    )

    # Required arguments
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="Input FASTA file (contigs, scaffolds, or reads)",
    )
    parser.add_argument(
        "--db", "-d",
        required=True,
        help="Path to BLAST or Diamond database",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output TSV file for merged BLAST results",
    )

    # BLAST options
    parser.add_argument(
        "--program", "-p",
        default="blastn",
        choices=["blastn", "blastx", "diamond"],
        help="Search program: blastn, blastx, or diamond (default: blastn)",
    )
    parser.add_argument(
        "--evalue", "-e",
        default="1e-10",
        help="E-value threshold (default: 1e-10)",
    )
    parser.add_argument(
        "--max-target-seqs",
        type=int,
        default=5,
        help="Maximum target sequences per query (default: 5)",
    )
    parser.add_argument(
        "--outfmt",
        default=(
            "6 qseqid sseqid pident length mismatch gapopen "
            "qstart qend sstart send evalue bitscore staxids"
        ),
        help=(
            "Output format string (default: tabular format 6 with standard fields). "
            "For Diamond, the format number and field names are passed as-is."
        ),
    )

    # Parallelism options
    parser.add_argument(
        "--num-chunks", "-n",
        type=int,
        default=0,
        help=(
            "Number of chunks to split the query into. "
            "0 = auto-detect (use all available CPUs). Default: 0."
        ),
    )
    parser.add_argument(
        "--threads-per-chunk", "-t",
        type=int,
        default=1,
        help="Threads allocated to each BLAST process (default: 1)",
    )

    # I/O options
    parser.add_argument(
        "--use-ramdisk",
        action="store_true",
        help="Use /dev/shm (RAM disk) for temporary chunk I/O acceleration",
    )

    # Extra args
    parser.add_argument(
        "--blast-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="Additional arguments passed through to the BLAST/Diamond binary",
    )

    # Verbosity
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v = INFO, -vv = DEBUG)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for CLI invocation.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)

    # Auto-detect num_chunks if not specified
    num_chunks = args.num_chunks
    if num_chunks <= 0:
        num_chunks = cpu_count()
        logger.info("Auto-detected %d CPUs for chunk count", num_chunks)

    # Validate RAM disk availability
    if args.use_ramdisk:
        if not os.path.isdir("/dev/shm"):
            logger.error("/dev/shm not available -- cannot use RAM disk")
            return 1
        shm_stat = os.statvfs("/dev/shm")
        free_gb = (shm_stat.f_bavail * shm_stat.f_frsize) / (1024 ** 3)
        logger.info("/dev/shm free space: %.1f GB", free_gb)

    try:
        run_parallel_blast(
            query=args.query,
            db=args.db,
            output=args.output,
            program=args.program,
            num_chunks=num_chunks,
            threads_per_chunk=args.threads_per_chunk,
            use_ramdisk=args.use_ramdisk,
            evalue=args.evalue,
            max_target_seqs=args.max_target_seqs,
            outfmt=args.outfmt,
            extra_args=args.blast_args,
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())
