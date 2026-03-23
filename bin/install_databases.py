#!/usr/bin/env python3
"""DeepInvirus reference database installer.

# @TASK T0.3 - Reference database installation script
# @SPEC docs/planning/04-database-design.md#참조-데이터베이스-구조
# @SPEC docs/planning/02-trd.md#DB-관리

Downloads and indexes all reference databases required by the DeepInvirus
pipeline. Supports selective installation via --components and a --dry-run
mode that prints the execution plan without downloading anything.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0"

# @TASK T0.3 - DB source URLs
DB_SOURCES: dict[str, dict[str, str]] = {
    "viral_protein": {
        "source": "UniRef90 viral subset",
        "url": "https://ftp.uniprot.org/pub/databases/uniprot/uniref/uniref90/uniref90.fasta.gz",
        "description": "UniRef90 viral protein clusters for Diamond blastx",
    },
    "viral_nucleotide": {
        "source": "NCBI RefSeq Viral",
        "url": "https://ftp.ncbi.nlm.nih.gov/refseq/release/viral/",
        "files": [
            "viral.1.1.genomic.fna.gz",
            "viral.2.1.genomic.fna.gz",
            "viral.3.1.genomic.fna.gz",
        ],
        "description": "NCBI RefSeq viral genomes for MMseqs2 taxonomy",
    },
    "genomad_db": {
        "source": "geNomad",
        "url": "https://zenodo.org/records/8339387/files/genomad_db_v1.7.tar.gz",
        "version": "1.7",
        "description": "geNomad ML model database",
    },
    "taxonomy": {
        "ncbi_url": "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz",
        "ictv_url": "https://ictv.global/vmr/current",
        "description": "NCBI taxonomy dump + ICTV VMR",
    },
    "host": {
        "human": {
            "url": "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/001/405/"
            "GCF_000001405.40_GRCh38.p14/GCF_000001405.40_GRCh38.p14_genomic.fna.gz",
            "name": "GRCh38.p14",
        },
        "mouse": {
            "url": "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/001/635/"
            "GCF_000001635.27_GRCm39/GCF_000001635.27_GRCm39_genomic.fna.gz",
            "name": "GRCm39",
        },
        "insect": {
            "url": "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/002/335/"
            "GCF_000002335.3_Tcas5.2/GCF_000002335.3_Tcas5.2_genomic.fna.gz",
            "name": "Tribolium castaneum Tcas5.2",
        },
        "description": "Host reference genomes for read decontamination (minimap2)",
    },
}

VALID_COMPONENTS = ("all", "protein", "nucleotide", "genomad", "taxonomy", "host")
VALID_HOSTS = ("human", "mouse", "insect")

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("install_databases")


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    """Return today's date as YYYY-MM-DD."""
    return datetime.date.today().isoformat()


def _run(
    cmd: list[str],
    *,
    dry_run: bool = False,
    description: str = "",
) -> subprocess.CompletedProcess[str] | None:
    """Execute a shell command with logging.

    Args:
        cmd: Command tokens.
        dry_run: If True, only log the command without executing.
        description: Human-readable description of the command.

    Returns:
        CompletedProcess on success, None for dry-run.

    Raises:
        SystemExit: If the command returns a non-zero exit code.
    """
    pretty = " ".join(cmd)
    if description:
        logger.info("%s: %s", description, pretty)
    else:
        logger.info("Running: %s", pretty)

    if dry_run:
        logger.info("  [DRY-RUN] Skipped.")
        return None

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.error("Command failed (exit %d): %s", result.returncode, pretty)
        if result.stderr:
            logger.error("stderr: %s", result.stderr.strip())
        sys.exit(1)
    return result


def _download_file(
    url: str,
    dest: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Download a file from *url* to *dest* with progress indication.

    Args:
        url: Remote URL to fetch.
        dest: Local destination path.
        dry_run: If True, log only.
    """
    logger.info("Downloading %s -> %s", url, dest)
    if dry_run:
        logger.info("  [DRY-RUN] Skipped.")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Use urllib for portability (no extra dependencies).
    req = urllib.request.Request(url, headers={"User-Agent": "DeepInvirus/0.1"})
    with urllib.request.urlopen(req) as response, open(dest, "wb") as out:
        total = response.headers.get("Content-Length")
        downloaded = 0
        block_size = 1024 * 1024  # 1 MB
        while True:
            buf = response.read(block_size)
            if not buf:
                break
            out.write(buf)
            downloaded += len(buf)
            if total:
                pct = downloaded / int(total) * 100
                print(
                    f"\r  Progress: {downloaded / 1e6:.1f} MB / "
                    f"{int(total) / 1e6:.1f} MB ({pct:.0f}%)",
                    end="",
                    flush=True,
                )
            else:
                print(
                    f"\r  Downloaded: {downloaded / 1e6:.1f} MB",
                    end="",
                    flush=True,
                )
        print()  # newline after progress


def _which(tool: str) -> bool:
    """Return True if *tool* is on PATH."""
    return shutil.which(tool) is not None


def _count_fasta_records(fasta: Path) -> int:
    """Count '>' headers in a FASTA file (plain or gzipped)."""
    import gzip

    count = 0
    opener = gzip.open if fasta.suffix == ".gz" else open
    with opener(fasta, "rt") as fh:  # type: ignore[call-overload]
        for line in fh:
            if line.startswith(">"):
                count += 1
    return count


# ---------------------------------------------------------------------------
# VERSION.json management
# ---------------------------------------------------------------------------

# @TASK T0.3 - VERSION.json creation/update
# @SPEC docs/planning/04-database-design.md#VERSION.json-스키마


def _load_version(db_dir: Path) -> dict[str, Any]:
    """Load existing VERSION.json or return a fresh skeleton."""
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
    """Persist VERSION.json to disk."""
    data["updated_at"] = _now_iso()
    vfile = db_dir / "VERSION.json"
    vfile.parent.mkdir(parents=True, exist_ok=True)
    with open(vfile, "w") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    logger.info("VERSION.json updated: %s", vfile)


# ---------------------------------------------------------------------------
# Download functions (one per DB component)
# ---------------------------------------------------------------------------


def download_viral_protein(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Download UniRef90 viral subset and build Diamond DB.

    Args:
        db_dir: Root database directory.
        threads: Number of threads for Diamond makedb.
        dry_run: Plan-only mode.

    Returns:
        Metadata dict for VERSION.json.
    """
    # @TASK T0.3 - Viral protein DB (Diamond)
    out = db_dir / "viral_protein"
    fasta = out / "uniref90_viral.fasta.gz"
    dmnd = out / "uniref90_viral.dmnd"

    logger.info("=== Viral Protein Database (Diamond) ===")
    logger.info("  Target directory: %s", out)

    if not dry_run:
        out.mkdir(parents=True, exist_ok=True)

    src = DB_SOURCES["viral_protein"]
    _download_file(src["url"], fasta, dry_run=dry_run)

    # Build Diamond DB
    if not _which("diamond"):
        logger.warning("diamond not found on PATH; skipping makedb")
    else:
        _run(
            ["diamond", "makedb", "--in", str(fasta), "-d", str(dmnd), "-p", str(threads)],
            dry_run=dry_run,
            description="Building Diamond DB",
        )

    record_count = 0
    if not dry_run and fasta.exists():
        logger.info("Counting FASTA records (this may take a while)...")
        record_count = _count_fasta_records(fasta)
        logger.info("  Records: %d", record_count)

    return {
        "source": src["source"],
        "version": datetime.date.today().strftime("%Y_%m"),
        "url": src["url"],
        "downloaded_at": _today(),
        "record_count": record_count,
        "format": "diamond",
    }


def download_viral_nucleotide(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Download NCBI RefSeq viral genomes and build MMseqs2 DB.

    Args:
        db_dir: Root database directory.
        threads: Number of threads for MMseqs2 createdb.
        dry_run: Plan-only mode.

    Returns:
        Metadata dict for VERSION.json.
    """
    # @TASK T0.3 - Viral nucleotide DB (MMseqs2)
    out = db_dir / "viral_nucleotide"
    merged_fasta = out / "refseq_viral.fasta"
    mmseqs_dir = out / "refseq_viral.mmseqs"

    logger.info("=== Viral Nucleotide Database (MMseqs2) ===")
    logger.info("  Target directory: %s", out)

    if not dry_run:
        out.mkdir(parents=True, exist_ok=True)

    src = DB_SOURCES["viral_nucleotide"]
    base_url = src["url"]
    downloaded: list[Path] = []
    for fname in src["files"]:
        dest = out / fname
        _download_file(f"{base_url}{fname}", dest, dry_run=dry_run)
        downloaded.append(dest)

    # Merge and decompress
    if not dry_run and downloaded:
        import gzip

        logger.info("Merging and decompressing FASTA files...")
        with open(merged_fasta, "w") as out_fh:
            for gz in downloaded:
                if gz.exists():
                    with gzip.open(gz, "rt") as in_fh:
                        for line in in_fh:
                            out_fh.write(line)
        logger.info("  Merged FASTA: %s", merged_fasta)

    # Build MMseqs2 DB
    if not _which("mmseqs"):
        logger.warning("mmseqs not found on PATH; skipping createdb")
    else:
        if not dry_run:
            mmseqs_dir.mkdir(parents=True, exist_ok=True)
        mmseqs_db = mmseqs_dir / "refseq_viral"
        _run(
            ["mmseqs", "createdb", str(merged_fasta), str(mmseqs_db), "--threads", str(threads)],
            dry_run=dry_run,
            description="Building MMseqs2 DB",
        )

    record_count = 0
    if not dry_run and merged_fasta.exists():
        record_count = _count_fasta_records(merged_fasta)
        logger.info("  Records: %d", record_count)

    return {
        "source": "NCBI RefSeq Viral",
        "version": f"release_{datetime.date.today().strftime('%Y%m')}",
        "url": base_url,
        "downloaded_at": _today(),
        "record_count": record_count,
        "format": "mmseqs2",
    }


def download_genomad_db(
    db_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Download geNomad ML model database from Zenodo.

    Args:
        db_dir: Root database directory.
        dry_run: Plan-only mode.

    Returns:
        Metadata dict for VERSION.json.
    """
    # @TASK T0.3 - geNomad DB
    out = db_dir / "genomad_db"
    tarball = out / "genomad_db.tar.gz"

    logger.info("=== geNomad Database ===")
    logger.info("  Target directory: %s", out)

    if not dry_run:
        out.mkdir(parents=True, exist_ok=True)

    src = DB_SOURCES["genomad_db"]
    _download_file(src["url"], tarball, dry_run=dry_run)

    # Extract
    if not dry_run and tarball.exists():
        logger.info("Extracting geNomad DB...")
        with tarfile.open(tarball, "r:gz") as tar:
            tar.extractall(path=out)
        logger.info("  Extracted to %s", out)
        # Optionally remove tarball to save space
        tarball.unlink()
        logger.info("  Removed tarball to save space.")

    return {
        "source": "geNomad",
        "version": src["version"],
        "url": src["url"],
        "downloaded_at": _today(),
    }


def download_taxonomy(
    db_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Download NCBI taxdump and ICTV VMR.

    Args:
        db_dir: Root database directory.
        dry_run: Plan-only mode.

    Returns:
        Metadata dict for VERSION.json.
    """
    # @TASK T0.3 - Taxonomy DB (NCBI + ICTV)
    out = db_dir / "taxonomy"
    ncbi_dir = out / "ncbi_taxdump"
    taxdump_tar = out / "taxdump.tar.gz"
    ictv_file = out / "ictv_vmr.tsv"
    taxonkit_dir = out / "taxonkit_data"

    logger.info("=== Taxonomy Database ===")
    logger.info("  Target directory: %s", out)

    if not dry_run:
        out.mkdir(parents=True, exist_ok=True)
        ncbi_dir.mkdir(parents=True, exist_ok=True)
        taxonkit_dir.mkdir(parents=True, exist_ok=True)

    src = DB_SOURCES["taxonomy"]

    # NCBI taxdump
    _download_file(src["ncbi_url"], taxdump_tar, dry_run=dry_run)
    if not dry_run and taxdump_tar.exists():
        logger.info("Extracting NCBI taxdump...")
        with tarfile.open(taxdump_tar, "r:gz") as tar:
            tar.extractall(path=ncbi_dir)
        taxdump_tar.unlink()
        logger.info("  Extracted to %s", ncbi_dir)

    # ICTV VMR (current release)
    _download_file(src["ictv_url"], ictv_file, dry_run=dry_run)

    # Set up TaxonKit data directory (symlink or copy names/nodes.dmp)
    if not dry_run and ncbi_dir.exists():
        for dmp in ("names.dmp", "nodes.dmp", "merged.dmp"):
            src_file = ncbi_dir / dmp
            dst_file = taxonkit_dir / dmp
            if src_file.exists() and not dst_file.exists():
                shutil.copy2(src_file, dst_file)
        logger.info("  TaxonKit data prepared in %s", taxonkit_dir)

    ncbi_version = _today()

    return {
        "ncbi_version": ncbi_version,
        "ictv_version": "VMR_MSL39_v3",
        "downloaded_at": _today(),
    }


def download_host_genome(
    db_dir: Path,
    host: str = "human",
    *,
    threads: int = 4,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Download a host reference genome and build minimap2 index.

    Args:
        db_dir: Root database directory.
        host: Host organism key (human/mouse/insect).
        threads: Number of threads for minimap2 indexing.
        dry_run: Plan-only mode.

    Returns:
        Metadata dict for VERSION.json.
    """
    # @TASK T0.3 - Host genome DB (minimap2)
    out = db_dir / "host_genomes" / host
    genome_gz = out / "genome.fa.gz"
    mmi = out / "genome.mmi"

    logger.info("=== Host Genome: %s ===", host)
    logger.info("  Target directory: %s", out)

    if host not in DB_SOURCES["host"]:
        logger.error("Unknown host: %s. Valid: %s", host, ", ".join(VALID_HOSTS))
        sys.exit(1)

    host_info = DB_SOURCES["host"][host]

    if not dry_run:
        out.mkdir(parents=True, exist_ok=True)

    _download_file(host_info["url"], genome_gz, dry_run=dry_run)

    # Build minimap2 index
    if not _which("minimap2"):
        logger.warning("minimap2 not found on PATH; skipping indexing")
    else:
        _run(
            ["minimap2", "-t", str(threads), "-d", str(mmi), str(genome_gz)],
            dry_run=dry_run,
            description="Building minimap2 index",
        )

    return {
        "host": host,
        "name": host_info["name"],
        "url": host_info["url"],
        "downloaded_at": _today(),
        "format": "minimap2",
    }


# ---------------------------------------------------------------------------
# Contaminant sequences (lightweight, always included)
# ---------------------------------------------------------------------------


def download_contaminants(
    db_dir: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Create placeholder contaminant sequence files.

    Real adapter/PhiX/vector sequences are small and can be bundled
    with the pipeline. This function creates the directory structure
    and placeholder files.

    Args:
        db_dir: Root database directory.
        dry_run: Plan-only mode.
    """
    out = db_dir / "contaminants"
    logger.info("=== Contaminant Sequences ===")
    logger.info("  Target directory: %s", out)

    if dry_run:
        logger.info("  [DRY-RUN] Would create contaminant placeholders.")
        return

    out.mkdir(parents=True, exist_ok=True)

    # Placeholder files (actual sequences should be added from assets/)
    for fname in ("adapters.fa", "phix.fa", "vectors.fa"):
        fpath = out / fname
        if not fpath.exists():
            fpath.touch()
            logger.info("  Created placeholder: %s", fpath)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _resolve_components(components: str) -> list[str]:
    """Expand 'all' into the full component list.

    Args:
        components: Comma-separated component names or 'all'.

    Returns:
        List of individual component names.
    """
    if components == "all":
        return ["protein", "nucleotide", "genomad", "taxonomy", "host"]
    return [c.strip() for c in components.split(",")]


def install(
    db_dir: Path,
    components: str = "all",
    host: str = "human",
    threads: int = 4,
    dry_run: bool = False,
) -> None:
    """Top-level install orchestrator.

    Args:
        db_dir: Root database directory.
        components: Which databases to install.
        host: Host genome to download.
        threads: Thread count for indexing tools.
        dry_run: If True, print plan without executing.
    """
    logger.info("=" * 60)
    logger.info("DeepInvirus Database Installer")
    logger.info("=" * 60)
    logger.info("  DB directory : %s", db_dir)
    logger.info("  Components   : %s", components)
    logger.info("  Host         : %s", host)
    logger.info("  Threads      : %d", threads)
    logger.info("  Dry-run      : %s", dry_run)
    logger.info("=" * 60)

    active = _resolve_components(components)
    version_data = _load_version(db_dir)

    if "protein" in active:
        meta = download_viral_protein(db_dir, threads=threads, dry_run=dry_run)
        if not dry_run:
            version_data["databases"]["viral_protein"] = meta

    if "nucleotide" in active:
        meta = download_viral_nucleotide(db_dir, threads=threads, dry_run=dry_run)
        if not dry_run:
            version_data["databases"]["viral_nucleotide"] = meta

    if "genomad" in active:
        meta = download_genomad_db(db_dir, dry_run=dry_run)
        if not dry_run:
            version_data["databases"]["genomad_db"] = meta

    if "taxonomy" in active:
        meta = download_taxonomy(db_dir, dry_run=dry_run)
        if not dry_run:
            version_data["databases"]["taxonomy"] = meta

    if "host" in active:
        meta = download_host_genome(db_dir, host=host, threads=threads, dry_run=dry_run)
        if not dry_run:
            version_data["databases"].setdefault("host_genomes", {})[host] = meta

    # Contaminants are always set up
    download_contaminants(db_dir, dry_run=dry_run)

    if not dry_run:
        _save_version(db_dir, version_data)

    logger.info("")
    logger.info("Installation %s.", "plan complete" if dry_run else "complete")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for install_databases.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="install_databases",
        description=(
            "Download and index all reference databases required by "
            "the DeepInvirus pipeline."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Install everything (dry-run)\n"
            "  python install_databases.py --db-dir /data/deepinvirus_db --dry-run\n"
            "\n"
            "  # Install only taxonomy and nucleotide DBs\n"
            "  python install_databases.py --db-dir /data/db --components taxonomy,nucleotide\n"
            "\n"
            "  # Install with mouse host genome\n"
            "  python install_databases.py --db-dir /data/db --host mouse\n"
        ),
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        required=True,
        help="Root directory where databases will be stored.",
    )
    parser.add_argument(
        "--components",
        type=str,
        default="all",
        help=(
            "Comma-separated list of components to install. "
            f"Choices: {', '.join(VALID_COMPONENTS)}. Default: all."
        ),
    )
    parser.add_argument(
        "--host",
        type=str,
        default="human",
        choices=VALID_HOSTS,
        help="Host genome to download for read decontamination. Default: human.",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
        help="Number of threads for indexing tools (Diamond, MMseqs2, minimap2). Default: 4.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print the installation plan without downloading anything.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug-level logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for the database installer.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate components
    active = _resolve_components(args.components)
    for comp in active:
        if comp not in VALID_COMPONENTS:
            parser.error(f"Unknown component: {comp}. Valid: {', '.join(VALID_COMPONENTS)}")

    install(
        db_dir=args.db_dir,
        components=args.components,
        host=args.host,
        threads=args.threads,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
