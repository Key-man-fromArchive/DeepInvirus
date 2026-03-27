#!/usr/bin/env python3
"""DeepInvirus reference database installer."""

from __future__ import annotations

import argparse
import datetime
import gzip
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.1"
VIRUS_TAXID = "10239"
APP_CONFIG_DIR = Path.home() / ".deepinvirus"
APP_CONFIG_FILE = APP_CONFIG_DIR / "config.json"

EXCLUSION_KINGDOMS: dict[str, dict[str, int | str]] = {
    "bacteria": {"taxid": 2, "name": "Bacteria"},
    "archaea": {"taxid": 2157, "name": "Archaea"},
    "fungi": {"taxid": 4751, "name": "Fungi"},
    "plant": {"taxid": 33090, "name": "Viridiplantae"},
    "insect": {"taxid": 6960, "name": "Insecta"},
}

DB_SOURCES: dict[str, dict[str, Any]] = {
    "viral_nucleotide": {
        "label": "GenBank viral NT",
        "description": "Primary MMseqs2 nucleotide DB from complete viral genomes.",
        "size_gb": 5.0,
        "required": True,
        "datasets_include": ["genome"],
        "datasets_complete_only": True,
        "legacy_source_name": "GenBank viral complete genomes",
    },
    "viral_protein": {
        "label": "Viral protein Diamond",
        "description": "RefSeq viral protein database with taxonomy mapping.",
        "size_gb": 0.5,
        "required": True,
        "base_url": "https://ftp.ncbi.nlm.nih.gov/refseq/release/viral/",
        "files": [
            "viral.1.protein.faa.gz",
            "viral.2.protein.faa.gz",
            "viral.3.protein.faa.gz",
            "viral.4.protein.faa.gz",
        ],
        "taxid_map": "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/accession2taxid/prot.accession2taxid.gz",
    },
    "uniref50": {
        "label": "UniRef50 Diamond",
        "description": "Optional broad protein verification DB.",
        "size_gb": 24.0,
        "required": False,
        "url": "https://ftp.uniprot.org/pub/databases/uniprot/uniref/uniref50/uniref50.fasta.gz",
    },
    "uniref90_viral": {
        "label": "UniRef90 viral Diamond",
        "description": "Optional viral-focused detection helper DB.",
        "size_gb": 0.5,
        "required": True,
        "legacy_url": "https://ftp.uniprot.org/pub/databases/uniprot/uniref/uniref90/uniref90.fasta.gz",
    },
    "genomad_db": {
        "label": "geNomad DB",
        "description": "geNomad model database.",
        "size_gb": 1.4,
        "required": True,
        "url": "https://zenodo.org/records/8339387/files/genomad_db_v1.7.tar.gz",
        "version": "1.7",
    },
    "checkv_db": {
        "label": "CheckV DB",
        "description": "Optional CheckV reference database.",
        "size_gb": 6.4,
        "required": False,
        "url": "https://portal.nersc.gov/CheckV/checkv-db-v1.5.tar.gz",
        "version": "1.5",
    },
    "taxonomy": {
        "label": "NCBI taxonomy + ICTV",
        "description": "NCBI taxdump and ICTV VMR.",
        "size_gb": 0.6,
        "required": True,
        "ncbi_url": "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz",
        "ictv_url": "https://ictv.global/vmr/current",
    },
    "nucl_gb_accession2taxid": {
        "label": "nucl_gb accession2taxid",
        "description": "GenBank nucleotide accession to taxid mapping.",
        "size_gb": 2.5,
        "required": True,
        "url": "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/accession2taxid/nucl_gb.accession2taxid.gz",
    },
    "exclusion_db": {
        "label": "SwissProt exclusion DB",
        "description": "Curated multi-kingdom non-viral exclusion protein DB.",
        "size_gb": 0.6,
        "required": True,
        "fasta_url": (
            "https://ftp.uniprot.org/pub/databases/uniprot/current_release/"
            "knowledgebase/complete/uniprot_sprot.fasta.gz"
        ),
        "dat_url": (
            "https://ftp.uniprot.org/pub/databases/uniprot/current_release/"
            "knowledgebase/complete/uniprot_sprot.dat.gz"
        ),
        "strategy": "single_swissprot_db_with_taxon_filters",
        "kingdoms": EXCLUSION_KINGDOMS,
    },
    "polymicrobial_nt": {
        "label": "Polymicrobial NT BLAST",
        "description": "Optional polymicrobial nucleotide exclusion BLAST DB.",
        "size_gb": 4.0,
        "required": False,
        "url": "https://ftp.ncbi.nlm.nih.gov/blast/db/ref_prok_rep_genomes.tar.gz",
    },
    "host": {
        "label": "Host genomes",
        "description": "Optional host reference genomes for minimap2.",
        "required": False,
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
    },
}

OPTIONAL_COMPONENTS = {"uniref50", "polymicrobial", "checkv"}
VALID_HOSTS = ("human", "mouse", "insect")
VALID_COMPONENTS = (
    "all",
    "protein",
    "nucleotide",
    "genomad",
    "taxonomy",
    "host",
    "exclusion",
    "checkv",
    "uniref50",
    "uniref90_viral",
    "uniref90-viral",
    "polymicrobial",
    "accession2taxid",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("install_databases")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.date.today().isoformat()


def _which(tool: str) -> bool:
    return shutil.which(tool) is not None


def _run(
    cmd: list[str],
    *,
    dry_run: bool = False,
    description: str = "",
    env: dict[str, str] | None = None,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str] | None:
    pretty = " ".join(cmd)
    logger.info("%s%s", f"{description}: " if description else "", pretty)
    if dry_run:
        logger.info("  [DRY-RUN] Skipped.")
        return None

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0 and not allow_failure:
        stderr = result.stderr.strip() if result.stderr else ""
        raise RuntimeError(f"Command failed ({result.returncode}): {pretty}\n{stderr}")
    return result


def _ensure_dir(path: Path, *, dry_run: bool = False) -> None:
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)


def _apply_api_key(url: str, api_key: str | None) -> str:
    if not api_key or "ncbi.nlm.nih.gov" not in url:
        return url
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    query["api_key"] = [api_key]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))


def _remote_size(url: str, headers: dict[str, str]) -> int | None:
    req = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        with urllib.request.urlopen(req) as response:
            length = response.headers.get("Content-Length")
            return int(length) if length else None
    except Exception:
        return None


def _download_file(
    url: str,
    dest: Path,
    *,
    dry_run: bool = False,
    api_key: str | None = None,
    label: str | None = None,
) -> Path:
    actual_url = _apply_api_key(url, api_key)
    headers = {"User-Agent": "DeepInvirus/1.1"}
    remote = _remote_size(actual_url, headers)
    existing = dest.stat().st_size if dest.exists() else 0

    logger.info("Downloading %s -> %s", label or actual_url, dest)
    if dry_run:
        logger.info("  [DRY-RUN] Skipped.")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    if remote is not None and existing == remote and remote > 0:
        logger.info("  Already complete, skipping.")
        return dest

    req_headers = dict(headers)
    mode = "wb"
    downloaded = 0
    if existing > 0:
        req_headers["Range"] = f"bytes={existing}-"
        mode = "ab"
        downloaded = existing

    req = urllib.request.Request(actual_url, headers=req_headers)
    try:
        with urllib.request.urlopen(req) as response, open(dest, mode) as out:
            total = remote
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    print(
                        f"\r  Progress: {downloaded / 1e6:.1f} MB / {total / 1e6:.1f} MB ({pct:.0f}%)",
                        end="",
                        flush=True,
                    )
                else:
                    print(
                        f"\r  Downloaded: {downloaded / 1e6:.1f} MB",
                        end="",
                        flush=True,
                    )
            print()
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and remote is not None and dest.exists():
            logger.info("  Already complete, skipping.")
            return dest
        raise RuntimeError(f"Download failed for {actual_url}: {exc}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error downloading {actual_url}: {exc}") from exc
    return dest


def _extract_tarball(archive: Path, out_dir: Path, *, dry_run: bool = False) -> None:
    logger.info("Extracting %s -> %s", archive, out_dir)
    if dry_run:
        logger.info("  [DRY-RUN] Skipped.")
        return
    with tarfile.open(archive, "r:*") as tar:
        tar.extractall(path=out_dir)


def _extract_zip(archive: Path, out_dir: Path, *, dry_run: bool = False) -> None:
    logger.info("Extracting %s -> %s", archive, out_dir)
    if dry_run:
        logger.info("  [DRY-RUN] Skipped.")
        return
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(out_dir)


def _find_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and any(path.name.endswith(suffix) for suffix in suffixes)
    )


def _concat_gzip_files(files: list[Path], dest: Path, *, dry_run: bool = False) -> None:
    logger.info("Merging %d FASTA files -> %s", len(files), dest)
    if dry_run:
        logger.info("  [DRY-RUN] Skipped.")
        return
    with gzip.open(dest, "wb") as out:
        for path in files:
            if path.suffix == ".gz":
                with gzip.open(path, "rb") as src:
                    shutil.copyfileobj(src, out)
            else:
                with open(path, "rb") as src:
                    shutil.copyfileobj(src, out)


def _symlink_or_copy(src: Path, dest: Path, *, dry_run: bool = False) -> None:
    if dry_run:
        return
    if dest.exists() or dest.is_symlink():
        return
    try:
        dest.symlink_to(src.name)
    except OSError:
        shutil.copy2(src, dest)


def _count_fasta_records(fasta: Path) -> int:
    opener = gzip.open if fasta.suffix == ".gz" else open
    count = 0
    with opener(fasta, "rt") as handle:  # type: ignore[call-overload]
        for line in handle:
            if line.startswith(">"):
                count += 1
    return count


def _load_version(db_dir: Path) -> dict[str, Any]:
    version_path = db_dir / "VERSION.json"
    if version_path.exists():
        with open(version_path) as handle:
            return json.load(handle)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "databases": {},
    }


def _save_version(db_dir: Path, version_data: dict[str, Any]) -> None:
    version_data["updated_at"] = _now_iso()
    version_path = db_dir / "VERSION.json"
    version_path.parent.mkdir(parents=True, exist_ok=True)
    with open(version_path, "w") as handle:
        json.dump(version_data, handle, indent=2, ensure_ascii=False)
    logger.info("VERSION.json updated: %s", version_path)


def _build_db_config(version_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": _now_iso(),
        "layout": {
            "viral_nucleotide": "viral_nucleotide/",
            "viral_protein": "viral_protein/",
            "uniref50": "uniref50/",
            "genomad_db": "genomad_db/",
            "checkv_db": "checkv_db/",
            "polymicrobial_nt": "polymicrobial_nt/",
            "exclusion_db": "exclusion_db/",
            "host_genomes": "host_genomes/",
            "taxonomy": "taxonomy/",
        },
        "pipeline": {
            "tier1": {
                "component": "viral_protein",
                "diamond_db": "viral_protein/viral_protein.dmnd",
                "detection_helper": "viral_protein/uniref90_viral.dmnd",
            },
            "tier2": {
                "component": "uniref50",
                "diamond_db": "uniref50/uniref50.dmnd",
            },
            "tier3": {
                "component": "viral_nucleotide",
                "mmseqs_db": "viral_nucleotide/refseq_viral_db",
                "source_fasta": "viral_nucleotide/genbank_viral_nt.fna.gz",
            },
            "tier4": {
                "component": "polymicrobial_nt",
                "blast_db": "polymicrobial_nt/",
            },
            "taxonomy": {
                "taxdump_dir": "taxonomy/",
                "ictv_vmr": "taxonomy/ictv_vmr.tsv",
                "nucl_accession_map": "taxonomy/nucl_gb.accession2taxid.gz",
            },
            "exclusion": {
                "component": "exclusion_db",
                "strategy": DB_SOURCES["exclusion_db"]["strategy"],
                "diamond_db": "exclusion_db/swissprot.dmnd",
                "taxid_map": "exclusion_db/swissprot.taxids.tsv",
            },
        },
        "versions": version_data.get("databases", {}),
    }


def _save_db_config(db_dir: Path, version_data: dict[str, Any], *, dry_run: bool = False) -> None:
    path = db_dir / "db_config.json"
    if dry_run:
        logger.info("db_config.json would be updated: %s", path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(_build_db_config(version_data), handle, indent=2, ensure_ascii=False)
    logger.info("db_config.json updated: %s", path)


def save_app_config(db_dir: Path, *, dry_run: bool = False) -> Path:
    if dry_run:
        return APP_CONFIG_FILE
    APP_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"db_dir": str(db_dir), "updated_at": _now_iso()}
    with open(APP_CONFIG_FILE, "w") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
    return APP_CONFIG_FILE


def load_app_config() -> dict[str, Any]:
    if not APP_CONFIG_FILE.exists():
        return {}
    with open(APP_CONFIG_FILE) as handle:
        return json.load(handle)


def _datasets_env(api_key: str | None) -> dict[str, str]:
    env = dict(os.environ)
    if api_key:
        env["NCBI_API_KEY"] = api_key
    return env


def _download_virus_datasets_package(
    db_dir: Path,
    package_name: str,
    *,
    include: list[str],
    api_key: str | None,
    dry_run: bool,
    refseq: bool = False,
    complete_only: bool = False,
) -> Path:
    archive = db_dir / "_downloads" / f"{package_name}.zip"
    _ensure_dir(archive.parent, dry_run=dry_run)
    if not _which("datasets"):
        raise RuntimeError(
            "NCBI Datasets CLI not found on PATH. Install 'datasets' or use the wizard "
            "on a system where NCBI Datasets is available."
        )

    cmd = [
        "datasets", "download", "virus", "genome", "taxon", VIRUS_TAXID,
        "--filename", str(archive),
        "--include", ",".join(include),
        "--no-progressbar",
    ]
    if api_key:
        cmd += ["--api-key", api_key]
    if refseq:
        cmd.append("--refseq")
    if complete_only:
        cmd.append("--complete-only")

    _run(
        cmd,
        dry_run=dry_run,
        description=f"Downloading NCBI Virus package ({package_name})",
        env=_datasets_env(api_key),
    )
    return archive


def download_viral_nucleotide(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    out = db_dir / "viral_nucleotide"
    dataset_dir = out / "ncbi_dataset"
    fasta = out / "genbank_viral_nt.fna.gz"
    legacy_fasta = out / "refseq_viral.fna.gz"
    mmseqs_db = out / "refseq_viral_db"

    logger.info("=== GenBank Viral NT (primary MMseqs2 DB) ===")
    _ensure_dir(out, dry_run=dry_run)
    archive = _download_virus_datasets_package(
        db_dir,
        "genbank_viral_nt",
        include=["genome"],
        api_key=api_key,
        dry_run=dry_run,
        complete_only=True,
    )
    _extract_zip(archive, out, dry_run=dry_run)

    if not dry_run:
        genome_files = _find_files(dataset_dir, (".fna", ".fna.gz", ".fa", ".fa.gz"))
        if not genome_files:
            raise RuntimeError("No genome FASTA files found in downloaded NCBI virus package.")
        _concat_gzip_files(genome_files, fasta, dry_run=False)
        _symlink_or_copy(fasta, legacy_fasta)

    if not _which("mmseqs"):
        logger.warning("mmseqs not found on PATH; skipping MMseqs2 DB build")
    else:
        _run(
            ["mmseqs", "createdb", str(fasta), str(mmseqs_db), "--threads", str(threads)],
            dry_run=dry_run,
            description="Building MMseqs2 DB",
        )

        taxdump_dir = db_dir / "taxonomy"
        nucl_taxmap = taxdump_dir / "nucl_gb.accession2taxid.gz"
        tmp_dir = out / "tmp"
        if taxdump_dir.exists() and nucl_taxmap.exists():
            _ensure_dir(tmp_dir, dry_run=dry_run)
            _run(
                [
                    "mmseqs",
                    "createtaxdb",
                    str(mmseqs_db),
                    str(tmp_dir),
                    "--threads", str(threads),
                    "--tax-mapping-file", str(nucl_taxmap),
                    "--ncbi-tax-dump", str(taxdump_dir),
                ],
                dry_run=dry_run,
                description="Adding MMseqs2 taxonomy",
                allow_failure=True,
            )

    record_count = 0 if dry_run or not fasta.exists() else _count_fasta_records(fasta)
    return {
        "source": DB_SOURCES["viral_nucleotide"]["legacy_source_name"],
        "version": _today(),
        "downloaded_at": _today(),
        "record_count": record_count,
        "format": "mmseqs2",
        "source_fasta": str(fasta.relative_to(db_dir)),
        "index_basename": str(mmseqs_db.relative_to(db_dir)),
    }


def download_viral_protein(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    del api_key
    out = db_dir / "viral_protein"
    fasta = out / "viral_protein_refseq.faa.gz"
    legacy_fasta = out / "viral_protein.faa.gz"
    dmnd = out / "viral_protein.dmnd"
    taxid_map = out / "prot.accession2taxid.gz"

    logger.info("=== Viral Protein Database (RefSeq proteins) ===")
    _ensure_dir(out, dry_run=dry_run)

    src = DB_SOURCES["viral_protein"]
    downloaded = [
        _download_file(f"{src['base_url']}{name}", out / name, dry_run=dry_run, label=name)
        for name in src["files"]
    ]
    _download_file(src["taxid_map"], taxid_map, dry_run=dry_run, label="prot.accession2taxid.gz")

    if not dry_run:
        available = [path for path in downloaded if path.exists()]
        if not available:
            raise RuntimeError("No viral protein FASTA chunks were downloaded.")
        _concat_gzip_files(available, fasta, dry_run=False)
        _symlink_or_copy(fasta, legacy_fasta)

    if _which("diamond"):
        _run(
            ["diamond", "makedb", "--in", str(fasta), "-d", str(dmnd), "-p", str(threads)],
            dry_run=dry_run,
            description="Building viral protein Diamond DB",
        )
    else:
        logger.warning("diamond not found on PATH; skipping Diamond build")

    record_count = 0 if dry_run or not fasta.exists() else _count_fasta_records(fasta)
    return {
        "source": "NCBI RefSeq Viral proteins",
        "version": _today(),
        "downloaded_at": _today(),
        "record_count": record_count,
        "format": "diamond",
        "source_fasta": str(fasta.relative_to(db_dir)),
        "index_file": str(dmnd.relative_to(db_dir)),
        "taxid_map": str(taxid_map.relative_to(db_dir)),
    }


def download_uniref90_viral_db(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    out = db_dir / "viral_protein"
    fasta = out / "uniref90_viral.fasta.gz"
    dmnd = out / "uniref90_viral.dmnd"

    logger.info("=== UniRef90 Viral Detection Helper DB ===")
    _ensure_dir(out, dry_run=dry_run)

    if _which("datasets"):
        archive = _download_virus_datasets_package(
            db_dir,
            "uniref90_viral_helper",
            include=["protein"],
            api_key=api_key,
            dry_run=dry_run,
            refseq=True,
        )
        _extract_zip(archive, out, dry_run=dry_run)
        if not dry_run:
            proteins = _find_files(out / "ncbi_dataset", (".faa", ".faa.gz", ".protein.faa", ".protein.faa.gz"))
            if not proteins:
                raise RuntimeError("No protein FASTA files found in NCBI datasets package.")
            _concat_gzip_files(proteins, fasta, dry_run=False)
    else:
        _download_file(
            DB_SOURCES["uniref90_viral"]["legacy_url"],
            fasta,
            dry_run=dry_run,
            label="legacy UniRef90 FASTA",
        )

    if _which("diamond"):
        _run(
            ["diamond", "makedb", "--in", str(fasta), "-d", str(dmnd), "-p", str(threads)],
            dry_run=dry_run,
            description="Building UniRef90 viral helper DB",
        )
    else:
        logger.warning("diamond not found on PATH; skipping Diamond build")

    record_count = 0 if dry_run or not fasta.exists() else _count_fasta_records(fasta)
    return {
        "source": "NCBI RefSeq viral proteins helper set",
        "version": _today(),
        "downloaded_at": _today(),
        "record_count": record_count,
        "format": "diamond",
        "source_fasta": str(fasta.relative_to(db_dir)),
        "index_file": str(dmnd.relative_to(db_dir)),
    }


def download_uniref50_db(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    del api_key
    out = db_dir / "uniref50"
    fasta = out / "uniref50.fasta.gz"
    dmnd = out / "uniref50.dmnd"

    logger.info("=== UniRef50 Database ===")
    _ensure_dir(out, dry_run=dry_run)
    _download_file(DB_SOURCES["uniref50"]["url"], fasta, dry_run=dry_run)

    if _which("diamond"):
        _run(
            ["diamond", "makedb", "--in", str(fasta), "-d", str(dmnd), "-p", str(threads)],
            dry_run=dry_run,
            description="Building UniRef50 Diamond DB",
        )
    else:
        logger.warning("diamond not found on PATH; skipping Diamond build")

    record_count = 0 if dry_run or not fasta.exists() else _count_fasta_records(fasta)
    return {
        "source": "UniRef50",
        "version": _today(),
        "downloaded_at": _today(),
        "record_count": record_count,
        "format": "diamond",
    }


def download_genomad_db(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    del threads
    del api_key
    out = db_dir / "genomad_db"
    archive = out / "genomad_db.tar.gz"

    logger.info("=== geNomad Database ===")
    _ensure_dir(out, dry_run=dry_run)
    _download_file(DB_SOURCES["genomad_db"]["url"], archive, dry_run=dry_run)
    _extract_tarball(archive, out, dry_run=dry_run)
    if not dry_run and archive.exists():
        archive.unlink()
    return {
        "source": "geNomad",
        "version": DB_SOURCES["genomad_db"]["version"],
        "downloaded_at": _today(),
    }


def download_checkv_db(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    del threads
    del api_key
    out = db_dir / "checkv_db"
    archive = out / "checkv_db.tar.gz"

    logger.info("=== CheckV Database ===")
    _ensure_dir(out, dry_run=dry_run)
    _download_file(DB_SOURCES["checkv_db"]["url"], archive, dry_run=dry_run)
    _extract_tarball(archive, out, dry_run=dry_run)
    if not dry_run and archive.exists():
        archive.unlink()
    return {
        "source": "CheckV",
        "version": DB_SOURCES["checkv_db"]["version"],
        "downloaded_at": _today(),
    }


def _extract_swissprot_taxids(dat_gz: Path, out_tsv: Path, *, dry_run: bool = False) -> int:
    logger.info("Extracting SwissProt accession -> taxid map: %s", out_tsv)
    if dry_run:
        logger.info("  [DRY-RUN] Skipped.")
        return 0

    accession = ""
    taxid = ""
    count = 0
    with gzip.open(dat_gz, "rt") as in_handle, open(out_tsv, "w") as out_handle:
        out_handle.write("accession\ttaxid\n")
        for line in in_handle:
            if line.startswith("AC   "):
                accession = line[5:].split(";")[0].strip()
            elif line.startswith("OX   NCBI_TaxID="):
                taxid = line.split("NCBI_TaxID=", 1)[1].split(";", 1)[0].strip()
            elif line.startswith("//"):
                if accession and taxid:
                    out_handle.write(f"{accession}\t{taxid}\n")
                    count += 1
                accession = ""
                taxid = ""
    return count


def download_exclusion_db(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
    kingdoms: list[str] | None = None,
) -> dict[str, Any]:
    del api_key
    out = db_dir / "exclusion_db"
    fasta = out / "swissprot.fasta.gz"
    dat_gz = out / "swissprot.dat.gz"
    dmnd = out / "swissprot.dmnd"
    taxids_tsv = out / "swissprot.taxids.tsv"
    selected = kingdoms or list(EXCLUSION_KINGDOMS)

    invalid = [name for name in selected if name not in EXCLUSION_KINGDOMS]
    if invalid:
        raise RuntimeError(f"Unknown exclusion kingdoms: {', '.join(invalid)}")

    logger.info("=== Exclusion DB ===")
    _ensure_dir(out, dry_run=dry_run)
    src = DB_SOURCES["exclusion_db"]
    _download_file(src["fasta_url"], fasta, dry_run=dry_run)
    _download_file(src["dat_url"], dat_gz, dry_run=dry_run)

    if _which("diamond"):
        _run(
            ["diamond", "makedb", "--in", str(fasta), "-d", str(dmnd), "-p", str(threads)],
            dry_run=dry_run,
            description="Building SwissProt Diamond DB",
        )
    else:
        logger.warning("diamond not found on PATH; skipping Diamond build")

    taxid_record_count = _extract_swissprot_taxids(dat_gz, taxids_tsv, dry_run=dry_run)
    record_count = 0 if dry_run or not fasta.exists() else _count_fasta_records(fasta)
    return {
        "source": "UniProt Swiss-Prot",
        "strategy": src["strategy"],
        "downloaded_at": _today(),
        "record_count": record_count,
        "taxid_record_count": taxid_record_count,
        "format": "diamond",
        "target_kingdoms": {name: EXCLUSION_KINGDOMS[name] for name in selected},
    }


def download_taxonomy(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    del threads
    out = db_dir / "taxonomy"
    archive = out / "taxdump.tar.gz"
    ictv = out / "ictv_vmr.tsv"
    logger.info("=== Taxonomy Database ===")
    _ensure_dir(out, dry_run=dry_run)

    src = DB_SOURCES["taxonomy"]
    _download_file(src["ncbi_url"], archive, dry_run=dry_run, api_key=api_key)
    if not dry_run:
        with tarfile.open(archive, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.name.endswith(".dmp")]
            tar.extractall(path=out, members=members)
        archive.unlink()

    _download_file(src["ictv_url"], ictv, dry_run=dry_run)

    taxonkit_dir = out / "taxonkit_data"
    _ensure_dir(taxonkit_dir, dry_run=dry_run)
    if not dry_run:
        for name in ("nodes.dmp", "names.dmp", "merged.dmp", "delnodes.dmp"):
            source = out / name
            if source.exists():
                shutil.copy2(source, taxonkit_dir / name)

    return {
        "source": "NCBI taxonomy + ICTV",
        "ncbi_version": _today(),
        "ictv_version": _today(),
        "downloaded_at": _today(),
    }


def download_nucl_gb_accession2taxid(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    del threads
    out = db_dir / "taxonomy"
    target = out / "nucl_gb.accession2taxid.gz"
    logger.info("=== GenBank accession->taxid map ===")
    _ensure_dir(out, dry_run=dry_run)
    _download_file(DB_SOURCES["nucl_gb_accession2taxid"]["url"], target, dry_run=dry_run, api_key=api_key)
    return {
        "source": "NCBI accession2taxid",
        "downloaded_at": _today(),
        "path": str(target.relative_to(db_dir)),
    }


def download_polymicrobial_nt(
    db_dir: Path,
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    del threads
    del api_key
    out = db_dir / "polymicrobial_nt"
    archive = out / "polymicrobial_nt.tar.gz"
    logger.info("=== Polymicrobial NT BLAST DB ===")
    _ensure_dir(out, dry_run=dry_run)
    _download_file(DB_SOURCES["polymicrobial_nt"]["url"], archive, dry_run=dry_run)
    _extract_tarball(archive, out, dry_run=dry_run)
    return {
        "source": "NCBI BLAST representative prokaryotic genomes",
        "downloaded_at": _today(),
    }


def download_host_genome(
    db_dir: Path,
    host: str = "human",
    *,
    threads: int = 4,
    dry_run: bool = False,
    api_key: str | None = None,
) -> dict[str, Any]:
    del api_key
    if host not in DB_SOURCES["host"]:
        raise RuntimeError(f"Unknown host: {host}")
    out = db_dir / "host_genomes" / host
    genome = out / "genome.fa.gz"
    mmi = out / "genome.mmi"
    info = DB_SOURCES["host"][host]

    logger.info("=== Host Genome: %s ===", host)
    _ensure_dir(out, dry_run=dry_run)
    _download_file(info["url"], genome, dry_run=dry_run)

    if _which("minimap2"):
        _run(
            ["minimap2", "-t", str(threads), "-d", str(mmi), str(genome)],
            dry_run=dry_run,
            description="Building minimap2 index",
        )
    else:
        logger.warning("minimap2 not found on PATH; skipping minimap2 index")

    return {
        "host": host,
        "name": info["name"],
        "url": info["url"],
        "downloaded_at": _today(),
        "format": "minimap2",
    }


def download_contaminants(db_dir: Path, *, dry_run: bool = False) -> None:
    out = db_dir / "contaminants"
    logger.info("=== Contaminants ===")
    if dry_run:
        logger.info("  [DRY-RUN] Would create placeholder contaminant files.")
        return
    out.mkdir(parents=True, exist_ok=True)
    for name in ("adapters.fa", "phix.fa", "vectors.fa"):
        path = out / name
        if not path.exists():
            path.touch()


def _canonical_component(component: str) -> str:
    aliases = {
        "protein": "protein",
        "nucleotide": "nucleotide",
        "genomad": "genomad",
        "taxonomy": "taxonomy",
        "host": "host",
        "exclusion": "exclusion",
        "checkv": "checkv",
        "uniref50": "uniref50",
        "uniref90_viral": "uniref90_viral",
        "uniref90-viral": "uniref90_viral",
        "polymicrobial": "polymicrobial",
        "accession2taxid": "accession2taxid",
    }
    return aliases.get(component.strip(), component.strip())


def _resolve_components(components: str, *, minimal: bool = False) -> list[str]:
    if components == "all":
        resolved = [
            "protein",
            "nucleotide",
            "genomad",
            "taxonomy",
            "host",
            "exclusion",
            "accession2taxid",
            "uniref90_viral",
        ]
        if not minimal:
            resolved.extend(["uniref50", "checkv", "polymicrobial"])
        return resolved

    result: list[str] = []
    for item in components.split(","):
        canonical = _canonical_component(item)
        if canonical:
            result.append(canonical)
    return result


def estimate_disk_usage(components: list[str]) -> float:
    mapping = {
        "nucleotide": DB_SOURCES["viral_nucleotide"]["size_gb"],
        "protein": DB_SOURCES["viral_protein"]["size_gb"],
        "genomad": DB_SOURCES["genomad_db"]["size_gb"],
        "taxonomy": DB_SOURCES["taxonomy"]["size_gb"],
        "host": 3.0,
        "exclusion": DB_SOURCES["exclusion_db"]["size_gb"],
        "accession2taxid": DB_SOURCES["nucl_gb_accession2taxid"]["size_gb"],
        "uniref90_viral": DB_SOURCES["uniref90_viral"]["size_gb"],
        "uniref50": DB_SOURCES["uniref50"]["size_gb"],
        "checkv": DB_SOURCES["checkv_db"]["size_gb"],
        "polymicrobial": DB_SOURCES["polymicrobial_nt"]["size_gb"],
    }
    return round(sum(mapping.get(component, 0.0) for component in components), 1)


def verify_database(db_dir: Path, component: str, *, host: str = "human") -> tuple[bool, str]:
    checks: dict[str, Callable[[], bool]] = {
        "protein": lambda: (db_dir / "viral_protein" / "viral_protein.dmnd").exists(),
        "nucleotide": lambda: (db_dir / "viral_nucleotide" / "refseq_viral_db").exists()
        or (db_dir / "viral_nucleotide" / "genbank_viral_nt.fna.gz").exists(),
        "genomad": lambda: (db_dir / "genomad_db").exists() and any((db_dir / "genomad_db").iterdir()),
        "taxonomy": lambda: (db_dir / "taxonomy" / "names.dmp").exists()
        and (db_dir / "taxonomy" / "nodes.dmp").exists()
        and (db_dir / "taxonomy" / "ictv_vmr.tsv").exists(),
        "host": lambda: (db_dir / "host_genomes" / host / "genome.fa.gz").exists(),
        "exclusion": lambda: (db_dir / "exclusion_db" / "swissprot.dmnd").exists(),
        "accession2taxid": lambda: (db_dir / "taxonomy" / "nucl_gb.accession2taxid.gz").exists(),
        "uniref90_viral": lambda: (db_dir / "viral_protein" / "uniref90_viral.dmnd").exists(),
        "uniref50": lambda: (db_dir / "uniref50" / "uniref50.dmnd").exists(),
        "checkv": lambda: (db_dir / "checkv_db").exists() and any((db_dir / "checkv_db").iterdir()),
        "polymicrobial": lambda: (db_dir / "polymicrobial_nt").exists()
        and any((db_dir / "polymicrobial_nt").iterdir()),
    }
    if component not in checks:
        return False, f"Unknown component: {component}"
    ok = checks[component]()
    return ok, "ok" if ok else "missing expected files"


INSTALLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "protein": download_viral_protein,
    "nucleotide": download_viral_nucleotide,
    "genomad": download_genomad_db,
    "taxonomy": download_taxonomy,
    "exclusion": download_exclusion_db,
    "checkv": download_checkv_db,
    "uniref50": download_uniref50_db,
    "uniref90_viral": download_uniref90_viral_db,
    "polymicrobial": download_polymicrobial_nt,
    "accession2taxid": download_nucl_gb_accession2taxid,
}

VERSION_KEYS = {
    "protein": "viral_protein",
    "nucleotide": "viral_nucleotide",
    "genomad": "genomad_db",
    "taxonomy": "taxonomy",
    "exclusion": "exclusion_db",
    "checkv": "checkv_db",
    "uniref50": "uniref50",
    "uniref90_viral": "uniref90_viral",
    "polymicrobial": "polymicrobial_nt",
    "accession2taxid": "nucl_gb_accession2taxid",
}


def install(
    db_dir: Path,
    components: str = "all",
    host: str = "human",
    threads: int = 4,
    dry_run: bool = False,
    minimal: bool = False,
    api_key: str | None = None,
) -> None:
    active = _resolve_components(components, minimal=minimal)
    for component in active:
        if component not in {*INSTALLERS.keys(), "host"}:
            raise RuntimeError(f"Unknown component: {component}")

    logger.info("=" * 60)
    logger.info("DeepInvirus Database Installer")
    logger.info("  DB directory : %s", db_dir)
    logger.info("  Components   : %s", ", ".join(active))
    logger.info("  Host         : %s", host)
    logger.info("  Threads      : %d", threads)
    logger.info("  Minimal      : %s", minimal)
    logger.info("  Dry-run      : %s", dry_run)
    logger.info("  Disk est.    : %.1f GB", estimate_disk_usage(active))
    logger.info("=" * 60)

    version_data = _load_version(db_dir)

    for component in active:
        if component == "host":
            meta = download_host_genome(
                db_dir,
                host=host,
                threads=threads,
                dry_run=dry_run,
                api_key=api_key,
            )
            if not dry_run:
                version_data["databases"].setdefault("host_genomes", {})[host] = meta
            continue

        installer = INSTALLERS[component]
        meta = installer(
            db_dir,
            threads=threads,  # type: ignore[misc]
            dry_run=dry_run,
            api_key=api_key,
        )
        if not dry_run:
            version_data["databases"][VERSION_KEYS[component]] = meta

    download_contaminants(db_dir, dry_run=dry_run)
    _save_db_config(db_dir, version_data, dry_run=dry_run)

    if not dry_run:
        _save_version(db_dir, version_data)
        save_app_config(db_dir, dry_run=False)

    logger.info("Installation %s.", "plan complete" if dry_run else "complete")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install_databases",
        description="Download and index reference databases required by DeepInvirus.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db-dir", type=Path, required=True, help="Root database directory.")
    parser.add_argument(
        "--components",
        type=str,
        default="all",
        help=f"Comma-separated components. Choices: {', '.join(VALID_COMPONENTS)}.",
    )
    parser.add_argument("--host", type=str, default="human", choices=VALID_HOSTS)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--minimal", action="store_true", default=False)
    parser.add_argument("--api-key", default=None, help="NCBI API key for faster downloads.")
    parser.add_argument("--verbose", action="store_true", default=False)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    active = _resolve_components(args.components, minimal=args.minimal)
    invalid = [component for component in active if component not in {*INSTALLERS.keys(), "host"}]
    if invalid:
        parser.error(f"Unknown component(s): {', '.join(invalid)}")

    try:
        install(
            db_dir=args.db_dir,
            components=args.components,
            host=args.host,
            threads=args.threads,
            dry_run=args.dry_run,
            minimal=args.minimal,
            api_key=args.api_key,
        )
    except RuntimeError as exc:
        logger.error(str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
