#!/usr/bin/env python3
"""DeepInvirus reference database updater.

# @TASK T0.3 - Reference database update script
# @SPEC docs/planning/04-database-design.md#DB-갱신-전략
# @SPEC docs/planning/02-trd.md#DB-관리

Selectively updates individual database components while preserving
existing data through a backup-before-update strategy. Reads the
existing VERSION.json to determine what is currently installed and
only refreshes the requested component(s).
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import shutil
import sys
from pathlib import Path

# Re-use download functions from the installer
from install_databases import (
    VALID_HOSTS,
    _load_version,
    _save_version,
    download_genomad_db,
    download_host_genome,
    download_taxonomy,
    download_viral_nucleotide,
    download_viral_protein,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("update_databases")


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------


def _backup_component(db_dir: Path, component_dir: str) -> Path | None:
    """Create a timestamped backup of a component directory.

    Args:
        db_dir: Root database directory.
        component_dir: Subdirectory name of the component (e.g. 'viral_protein').

    Returns:
        Path to the backup directory, or None if the source doesn't exist.
    """
    src = db_dir / component_dir
    if not src.exists():
        logger.info("  No existing %s to back up.", component_dir)
        return None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_dir / "backups" / f"{component_dir}_{timestamp}"
    backup.parent.mkdir(parents=True, exist_ok=True)

    logger.info("  Backing up %s -> %s", src, backup)
    shutil.copytree(src, backup)
    return backup


def _restore_backup(backup: Path, target: Path) -> None:
    """Restore a backup directory to its original location.

    Args:
        backup: Backup directory path.
        target: Original directory path to restore to.
    """
    if backup and backup.exists():
        logger.warning("Restoring backup %s -> %s", backup, target)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(backup, target)


def _remove_backup(backup: Path | None) -> None:
    """Remove a backup directory after successful update.

    Args:
        backup: Backup directory path, or None.
    """
    if backup and backup.exists():
        shutil.rmtree(backup)
        logger.info("  Removed backup: %s", backup)


# ---------------------------------------------------------------------------
# Component-level update functions
# ---------------------------------------------------------------------------

# Mapping from CLI component name to (VERSION.json key, directory name)
COMPONENT_MAP: dict[str, tuple[str, str]] = {
    "protein": ("viral_protein", "viral_protein"),
    "nucleotide": ("viral_nucleotide", "viral_nucleotide"),
    "genomad": ("genomad_db", "genomad_db"),
    "taxonomy": ("taxonomy", "taxonomy"),
    "host": ("host_genomes", "host_genomes"),
}


def update_component(
    db_dir: Path,
    component: str,
    *,
    host: str = "human",
    threads: int = 4,
    dry_run: bool = False,
    force: bool = False,
) -> bool:
    """Update a single database component.

    Performs backup-before-update: if the download/indexing fails the
    original data is restored automatically.

    Args:
        db_dir: Root database directory.
        component: Component name (protein/nucleotide/genomad/taxonomy/host).
        host: Host genome key (only relevant when component == 'host').
        threads: Thread count for indexing tools.
        dry_run: Plan-only mode.
        force: If True, update even if the component appears up-to-date.

    Returns:
        True on success, False on failure.
    """
    if component not in COMPONENT_MAP:
        logger.error("Unknown component: %s", component)
        return False

    version_key, dir_name = COMPONENT_MAP[component]
    version_data = _load_version(db_dir)
    existing = version_data.get("databases", {}).get(version_key)

    if existing and not force and not dry_run:
        logger.info(
            "  Current %s version: downloaded_at=%s",
            component,
            existing.get("downloaded_at", "unknown"),
        )

    logger.info("")
    logger.info(">>> Updating component: %s", component)

    # Backup
    backup_dir = dir_name if component != "host" else f"host_genomes/{host}"
    backup = _backup_component(db_dir, backup_dir) if not dry_run else None

    try:
        if component == "protein":
            meta = download_viral_protein(db_dir, threads=threads, dry_run=dry_run)
        elif component == "nucleotide":
            meta = download_viral_nucleotide(db_dir, threads=threads, dry_run=dry_run)
        elif component == "genomad":
            meta = download_genomad_db(db_dir, dry_run=dry_run)
        elif component == "taxonomy":
            meta = download_taxonomy(db_dir, dry_run=dry_run)
        elif component == "host":
            meta = download_host_genome(db_dir, host=host, threads=threads, dry_run=dry_run)
        else:
            logger.error("Unhandled component: %s", component)
            return False

        if not dry_run:
            if component == "host":
                version_data["databases"].setdefault("host_genomes", {})[host] = meta
            else:
                version_data["databases"][version_key] = meta
            _save_version(db_dir, version_data)
            _remove_backup(backup)

        logger.info("  Component %s updated successfully.", component)
        return True

    except Exception:
        logger.exception("Failed to update %s.", component)
        if backup:
            target = db_dir / backup_dir
            _restore_backup(backup, target)
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for update_databases.

    Returns:
        Configured ArgumentParser instance.
    """
    updatable = ("protein", "nucleotide", "genomad", "taxonomy", "host")
    parser = argparse.ArgumentParser(
        prog="update_databases",
        description=(
            "Selectively update DeepInvirus reference databases. "
            "Reads the existing VERSION.json and refreshes only the "
            "requested component(s) with automatic backup/rollback."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Update taxonomy DB only\n"
            "  python update_databases.py --db-dir /data/db --component taxonomy\n"
            "\n"
            "  # Update protein + nucleotide\n"
            "  python update_databases.py --db-dir /data/db --component protein,nucleotide\n"
            "\n"
            "  # Dry-run check\n"
            "  python update_databases.py --db-dir /data/db --component all --dry-run\n"
        ),
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        required=True,
        help="Root directory where databases are stored.",
    )
    parser.add_argument(
        "--component",
        type=str,
        required=True,
        help=(
            "Comma-separated list of components to update. "
            f"Choices: all, {', '.join(updatable)}."
        ),
    )
    parser.add_argument(
        "--host",
        type=str,
        default="human",
        choices=VALID_HOSTS,
        help="Host genome key (used when component includes 'host'). Default: human.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
        help="Number of threads for indexing tools. Default: 4.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print the update plan without modifying anything.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force update even if the component appears up-to-date.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug-level logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for the database updater.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate db-dir exists
    if not args.db_dir.exists():
        parser.error(f"Database directory does not exist: {args.db_dir}")

    version_file = args.db_dir / "VERSION.json"
    if not version_file.exists():
        logger.warning(
            "No VERSION.json found in %s. Run install_databases.py first.",
            args.db_dir,
        )

    # Resolve components
    if args.component == "all":
        components = ["protein", "nucleotide", "genomad", "taxonomy", "host"]
    else:
        components = [c.strip() for c in args.component.split(",")]

    for comp in components:
        if comp not in COMPONENT_MAP:
            parser.error(
                f"Unknown component: {comp}. "
                f"Valid: all, {', '.join(COMPONENT_MAP.keys())}"
            )

    logger.info("=" * 60)
    logger.info("DeepInvirus Database Updater")
    logger.info("=" * 60)
    logger.info("  DB directory : %s", args.db_dir)
    logger.info("  Components   : %s", ", ".join(components))
    logger.info("  Dry-run      : %s", args.dry_run)
    logger.info("  Force        : %s", args.force)
    logger.info("=" * 60)

    # Show current state
    if version_file.exists():
        with open(version_file) as fh:
            current = json.load(fh)
        logger.info("Current VERSION.json:")
        for db_key, db_meta in current.get("databases", {}).items():
            if isinstance(db_meta, dict) and "downloaded_at" in db_meta:
                logger.info("  %s: downloaded_at=%s", db_key, db_meta["downloaded_at"])
            elif isinstance(db_meta, dict):
                for sub_key, sub_meta in db_meta.items():
                    if isinstance(sub_meta, dict):
                        logger.info(
                            "  %s/%s: downloaded_at=%s",
                            db_key,
                            sub_key,
                            sub_meta.get("downloaded_at", "?"),
                        )
        logger.info("")

    results: dict[str, bool] = {}
    for comp in components:
        ok = update_component(
            args.db_dir,
            comp,
            host=args.host,
            threads=args.threads,
            dry_run=args.dry_run,
            force=args.force,
        )
        results[comp] = ok

    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Update Summary:")
    for comp, ok in results.items():
        status = "OK" if ok else "FAILED"
        logger.info("  %-15s %s", comp, status)
    logger.info("=" * 60)

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
