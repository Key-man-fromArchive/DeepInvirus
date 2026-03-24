#!/usr/bin/env python3
# @TASK T10.2 - Host genome 추가 CLI 스크립트
# @SPEC docs/planning/06-tasks-tui.md#phase-10-t102-host-추가-액션-redgreen
# @TEST tests/tui/test_host_screen.py::TestAddHostScript
# @TEST tests/tui/test_host_screen.py::TestAddHostFunctionality
"""
Add a custom host reference genome to the DeepInvirus database.

Copies a FASTA file into the database directory, builds a minimap2 index,
creates info.json with dbname/species metadata, and updates both
VERSION.json and _index.json.

Usage:
    python add_host.py --name beetle --dbname btl --species "Beetle sp." --fasta ref.fa --db-dir /data/db
    python add_host.py --name tmol --dbname tmol --species "Tenebrio molitor" --fasta ref.fa --db-dir /data/db --dry-run
    python add_host.py --name beetle --fasta ref.fa --db-dir /data/db --skip-index
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("add_host")

SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    """Return today's date as YYYY-MM-DD."""
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# VERSION.json management
# ---------------------------------------------------------------------------


def _load_version(db_dir: Path) -> dict[str, Any]:
    """Load existing VERSION.json or return a fresh skeleton.

    Args:
        db_dir: Root database directory containing VERSION.json.

    Returns:
        Parsed VERSION.json content as a dictionary.
    """
    vfile = db_dir / "VERSION.json"
    if vfile.exists():
        with open(vfile) as fh:
            return json.load(fh)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "databases": {},
    }


def _save_version(db_dir: Path, data: dict[str, Any]) -> None:
    """Persist VERSION.json to disk.

    Args:
        db_dir: Root database directory.
        data: VERSION data to write.
    """
    data["updated_at"] = _now_iso()
    vfile = db_dir / "VERSION.json"
    vfile.parent.mkdir(parents=True, exist_ok=True)
    with open(vfile, "w") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    logger.info("VERSION.json updated: %s", vfile)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def copy_fasta(fasta: Path, host_dir: Path) -> Path:
    """Copy the FASTA file into the host genome directory.

    Args:
        fasta: Source FASTA file path.
        host_dir: Destination host genome directory.

    Returns:
        Path to the copied FASTA file.
    """
    host_dir.mkdir(parents=True, exist_ok=True)
    dest = host_dir / fasta.name
    shutil.copy2(fasta, dest)
    logger.info("Copied FASTA: %s -> %s", fasta, dest)
    return dest


def build_minimap2_index(
    fasta: Path,
    host_dir: Path,
    *,
    name: str,
    threads: int = 4,
) -> Path | None:
    """Build a minimap2 index from the FASTA file.

    Args:
        fasta: Path to the FASTA file (in the host directory).
        host_dir: Host genome directory.
        name: Host name (used for the .mmi filename).
        threads: Number of threads for minimap2.

    Returns:
        Path to the generated .mmi file, or None if minimap2 is unavailable.
    """
    mmi = host_dir / f"{name}.mmi"

    if not shutil.which("minimap2"):
        logger.warning("minimap2 not found on PATH; skipping index build")
        return None

    cmd = ["minimap2", "-t", str(threads), "-d", str(mmi), str(fasta)]
    logger.info("Building minimap2 index: %s", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.error("minimap2 failed (exit %d)", result.returncode)
        if result.stderr:
            logger.error("stderr: %s", result.stderr.strip())
        sys.exit(1)

    logger.info("Index created: %s", mmi)
    return mmi


def add_host(
    name: str,
    fasta: Path,
    db_dir: Path,
    *,
    dbname: str | None = None,
    species: str = "Unknown",
    threads: int = 4,
    dry_run: bool = False,
    skip_index: bool = False,
) -> None:
    """Add a host reference genome to the database.

    Steps:
        1. Copy FASTA to db_dir/host_genomes/{dbname}/genome.fa.gz
        2. Build minimap2 index (.mmi)
        3. Create info.json with dbname/species metadata
        4. Update _index.json (dbname -> species mapping)
        5. Update VERSION.json

    Args:
        name: Host genome name (e.g., "beetle", "human").
        fasta: Path to the reference genome FASTA file.
        db_dir: Root database directory.
        dbname: Short identifier for multi-host selection (e.g., "tmol").
                  If None, uses the name as dbname.
        species: Full species name (e.g., "Tenebrio molitor").
        threads: Number of threads for minimap2 indexing.
        dry_run: If True, print plan without executing.
        skip_index: If True, skip minimap2 indexing (copy FASTA + update VERSION only).
    """
    # Use name as dbname if not provided (backward compatibility)
    if dbname is None:
        dbname = name

    host_dir = db_dir / "host_genomes" / dbname

    logger.info("=" * 50)
    logger.info("Add Host Genome: %s", name)
    logger.info("=" * 50)
    logger.info("  Dbname   : %s", dbname)
    logger.info("  Species    : %s", species)
    logger.info("  FASTA      : %s", fasta)
    logger.info("  DB dir     : %s", db_dir)
    logger.info("  Host dir   : %s", host_dir)
    logger.info("  Threads    : %d", threads)
    logger.info("  Dry-run    : %s", dry_run)
    logger.info("  Skip-index : %s", skip_index)

    # Validate FASTA exists
    if not fasta.exists():
        logger.error("FASTA file not found: %s", fasta)
        sys.exit(1)

    if dry_run:
        logger.info("[DRY-RUN] Would copy %s to %s", fasta, host_dir)
        logger.info("[DRY-RUN] Would build minimap2 index")
        logger.info("[DRY-RUN] Would create info.json and update _index.json")
        logger.info("[DRY-RUN] Would update VERSION.json")
        logger.info("Dry-run complete.")
        return

    # Step 1: Copy FASTA as genome.fa.gz
    copied_fasta = copy_fasta(fasta, host_dir)

    # Step 2: Build minimap2 index (optional)
    if not skip_index:
        build_minimap2_index(
            copied_fasta, host_dir, name=dbname, threads=threads,
        )

    # Step 3: Create info.json with dbname/species metadata
    info = {
        "dbname": dbname,
        "species": species,
        "name": name,
        "added": _today(),
    }
    info_path = host_dir / "info.json"
    with open(info_path, "w") as fh:
        json.dump(info, fh, indent=2, ensure_ascii=False)
    logger.info("info.json created: %s", info_path)

    # Step 4: Update _index.json (dbname -> species mapping)
    index_path = db_dir / "host_genomes" / "_index.json"
    if index_path.exists():
        with open(index_path) as fh:
            index_data = json.load(fh)
    else:
        index_data = {}
    index_data[dbname] = species
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "w") as fh:
        json.dump(index_data, fh, indent=2, ensure_ascii=False)
    logger.info("_index.json updated: %s", index_path)

    # Step 5: Update VERSION.json
    version_data = _load_version(db_dir)
    host_genomes = version_data["databases"].setdefault("host_genomes", {})
    host_genomes[dbname] = {
        "host": name,
        "dbname": dbname,
        "species": species,
        "fasta": str(copied_fasta.name),
        "downloaded_at": _today(),
        "format": "minimap2",
    }
    _save_version(db_dir, version_data)

    logger.info("Host genome '%s' (dbname: %s) added successfully.", name, dbname)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for add_host.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="add_host",
        description=(
            "Add a custom host reference genome to the DeepInvirus database. "
            "Copies FASTA, builds minimap2 index, creates info.json, "
            "and updates VERSION.json and _index.json."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python add_host.py --name beetle --dbname btl --species 'Beetle sp.' --fasta ref.fa --db-dir /data/db\n"
            "  python add_host.py --name tmol --dbname tmol --species 'Tenebrio molitor' --fasta ref.fa --db-dir /data/db\n"
            "  python add_host.py --name beetle --fasta beetle_ref.fa --db-dir /data/db --dry-run\n"
            "  python add_host.py --name beetle --fasta beetle_ref.fa --db-dir /data/db --skip-index\n"
        ),
    )
    parser.add_argument(
        "--name",
        type=str,
        required=True,
        help="Host genome name (e.g., beetle, chicken).",
    )
    parser.add_argument(
        "--dbname",
        type=str,
        default=None,
        help="Short identifier for multi-host selection (e.g., tmol, zmor). Defaults to --name.",
    )
    parser.add_argument(
        "--species",
        type=str,
        default="Unknown",
        help="Full species name (e.g., 'Tenebrio molitor'). Default: 'Unknown'.",
    )
    parser.add_argument(
        "--fasta",
        type=Path,
        required=True,
        help="Path to the reference genome FASTA file.",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        required=True,
        help="Root database directory.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
        help="Number of threads for minimap2 indexing. Default: 4.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print the execution plan without making changes.",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        default=False,
        help="Skip minimap2 index build (copy FASTA and update VERSION.json only).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug-level logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for the add_host CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    add_host(
        name=args.name,
        fasta=args.fasta,
        db_dir=args.db_dir,
        dbname=args.dbname,
        species=args.species,
        threads=args.threads,
        dry_run=args.dry_run,
        skip_index=args.skip_index,
    )


if __name__ == "__main__":
    main()
