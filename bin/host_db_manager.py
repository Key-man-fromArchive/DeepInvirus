#!/usr/bin/env python3
# @TASK T-MULTI-HOST - Host genome DB manager for multi-host selection
# @SPEC docs/planning/02-trd.md#host_genomes
# @TEST tests/test_host_db.py
"""
Host Genome Database Manager for DeepInvirus.

Manages individual host genome registrations with nicknames, supports
selecting multiple hosts by comma-separated nicknames, and builds
combined minimap2 indices for multi-host removal.

DB structure:
    databases/host_genomes/
        tmol/
            genome.fa.gz
            genome.mmi
            info.json   # {"nickname": "tmol", "species": "Tenebrio molitor", "added": "..."}
        zmor/
            genome.fa.gz
            genome.mmi
            info.json
        _index.json     # {"tmol": "Tenebrio molitor", "zmor": "Zophobas morio"}

Usage:
    mgr = HostDBManager(Path("databases"))
    mgr.add_host("tmol", "Tenebrio molitor", Path("ref.fa.gz"))
    mgr.list_hosts()
    mgr.get_host_paths(["tmol", "zmor"])
    mgr.build_combined_index(["tmol", "zmor"], output_dir)
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger("host_db_manager")


# ---------------------------------------------------------------------------
# Public helper: parse comma-separated host string
# ---------------------------------------------------------------------------


def parse_host_string(host_str: str) -> list[str]:
    """Parse a comma-separated host string into a deduplicated list of nicknames.

    Args:
        host_str: Comma-separated host nicknames (e.g., "tmol,zmor,human").
                  "none" or empty string returns an empty list.

    Returns:
        Ordered, deduplicated list of host nicknames.

    Examples:
        >>> parse_host_string("tmol,zmor")
        ['tmol', 'zmor']
        >>> parse_host_string("none")
        []
        >>> parse_host_string("")
        []
        >>> parse_host_string("tmol,tmol,zmor")
        ['tmol', 'zmor']
    """
    if not host_str or host_str.strip().lower() == "none":
        return []

    seen: set[str] = set()
    result: list[str] = []
    for part in host_str.split(","):
        name = part.strip()
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


# ---------------------------------------------------------------------------
# HostDBManager
# ---------------------------------------------------------------------------


class HostDBManager:
    """Manages host genome databases for DeepInvirus.

    Each host genome is stored under db_dir/host_genomes/{nickname}/
    with genome.fa.gz, genome.mmi (optional), and info.json.

    Args:
        db_dir: Root database directory (e.g., Path("databases")).
    """

    def __init__(self, db_dir: Path) -> None:
        self.db_dir = db_dir
        self.host_dir = db_dir / "host_genomes"

    # ------------------------------------------------------------------
    # _index.json management
    # ------------------------------------------------------------------

    def _load_index(self) -> dict[str, str]:
        """Load _index.json (nickname -> species mapping).

        Returns:
            Dictionary mapping nicknames to species names.
        """
        index_path = self.host_dir / "_index.json"
        if index_path.exists():
            return json.loads(index_path.read_text())
        return {}

    def _save_index(self, data: dict[str, str]) -> None:
        """Persist _index.json to disk.

        Args:
            data: nickname -> species mapping.
        """
        self.host_dir.mkdir(parents=True, exist_ok=True)
        index_path = self.host_dir / "_index.json"
        index_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    # ------------------------------------------------------------------
    # list_hosts
    # ------------------------------------------------------------------

    def list_hosts(self) -> list[dict]:
        """List all registered host genomes.

        Returns:
            List of dicts, each containing:
                - nickname (str): Host nickname
                - species (str): Species name
                - indexed (bool): Whether .mmi index exists
                - size_mb (float): Total directory size in MB

        Example:
            [{"nickname": "tmol", "species": "Tenebrio molitor",
              "indexed": True, "size_mb": 84.2}]
        """
        if not self.host_dir.is_dir():
            return []

        hosts: list[dict] = []
        for entry in sorted(self.host_dir.iterdir()):
            if not entry.is_dir():
                continue
            # Skip entries starting with _ (like _index.json directory, though unlikely)
            if entry.name.startswith("_"):
                continue

            # Read info.json if present
            info_path = entry / "info.json"
            if info_path.exists():
                info = json.loads(info_path.read_text())
                nickname = info.get("nickname", entry.name)
                species = info.get("species", "Unknown")
            else:
                nickname = entry.name
                species = "Unknown"

            # Check for .mmi index
            mmi_files = list(entry.glob("*.mmi"))
            indexed = len(mmi_files) > 0

            # Compute directory size in MB
            total_bytes = sum(
                f.stat().st_size for f in entry.iterdir() if f.is_file()
            )
            size_mb = round(total_bytes / (1024 * 1024), 2)

            hosts.append({
                "nickname": nickname,
                "species": species,
                "indexed": indexed,
                "size_mb": size_mb,
            })

        return hosts

    # ------------------------------------------------------------------
    # add_host
    # ------------------------------------------------------------------

    def add_host(
        self,
        nickname: str,
        species: str,
        fasta_path: Path,
        *,
        threads: int = 4,
        skip_index: bool = False,
    ) -> None:
        """Register a new host genome.

        Steps:
            1. Copy FASTA to host_genomes/{nickname}/genome.fa.gz
            2. Build minimap2 index (unless skip_index=True)
            3. Write info.json
            4. Update _index.json

        Args:
            nickname: Short identifier (e.g., "tmol", "human").
            species: Full species name (e.g., "Tenebrio molitor").
            fasta_path: Path to reference FASTA file (.fa, .fa.gz, .fasta, etc).
            threads: Number of threads for minimap2 indexing.
            skip_index: If True, skip minimap2 index build.

        Raises:
            FileNotFoundError: If fasta_path does not exist.
        """
        fasta_path = Path(fasta_path)
        if not fasta_path.exists():
            raise FileNotFoundError(f"FASTA file not found: {fasta_path}")

        host_entry_dir = self.host_dir / nickname
        host_entry_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Copy FASTA as genome.fa.gz
        dest_fasta = host_entry_dir / "genome.fa.gz"
        shutil.copy2(fasta_path, dest_fasta)
        logger.info("Copied FASTA: %s -> %s", fasta_path, dest_fasta)

        # Step 2: Build minimap2 index
        if not skip_index:
            mmi_path = host_entry_dir / "genome.mmi"
            cmd = [
                "minimap2", "-t", str(threads),
                "-d", str(mmi_path), str(dest_fasta),
            ]
            logger.info("Building minimap2 index: %s", " ".join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logger.error(
                    "minimap2 failed (exit %d): %s",
                    result.returncode,
                    result.stderr.strip(),
                )
                raise RuntimeError(
                    f"minimap2 indexing failed for {nickname}: {result.stderr.strip()}"
                )
            logger.info("Index created: %s", mmi_path)

        # Step 3: Write info.json
        info = {
            "nickname": nickname,
            "species": species,
            "added": datetime.date.today().isoformat(),
        }
        (host_entry_dir / "info.json").write_text(
            json.dumps(info, indent=2, ensure_ascii=False)
        )

        # Step 4: Update _index.json
        index_data = self._load_index()
        index_data[nickname] = species
        self._save_index(index_data)

        logger.info("Host genome '%s' (%s) added successfully.", nickname, species)

    # ------------------------------------------------------------------
    # remove_host
    # ------------------------------------------------------------------

    def remove_host(self, nickname: str) -> None:
        """Remove a registered host genome.

        Deletes the host directory and removes the entry from _index.json.

        Args:
            nickname: Host nickname to remove.

        Raises:
            KeyError: If the nickname is not registered.
        """
        host_entry_dir = self.host_dir / nickname
        if not host_entry_dir.is_dir():
            raise KeyError(f"Host genome not found: {nickname}")

        shutil.rmtree(host_entry_dir)
        logger.info("Removed host directory: %s", host_entry_dir)

        # Update _index.json
        index_data = self._load_index()
        index_data.pop(nickname, None)
        self._save_index(index_data)

        logger.info("Host genome '%s' removed.", nickname)

    # ------------------------------------------------------------------
    # get_host_paths
    # ------------------------------------------------------------------

    def get_host_paths(self, nicknames: list[str]) -> list[Path]:
        """Get genome.fa.gz paths for the given host nicknames.

        Args:
            nicknames: List of host nicknames.

        Returns:
            List of paths to genome.fa.gz files.

        Raises:
            KeyError: If any nickname is not registered.
        """
        paths: list[Path] = []
        for nick in nicknames:
            fasta = self.host_dir / nick / "genome.fa.gz"
            if not fasta.exists():
                raise KeyError(f"Host genome not found: {nick}")
            paths.append(fasta)
        return paths

    # ------------------------------------------------------------------
    # build_combined_index
    # ------------------------------------------------------------------

    def build_combined_index(
        self,
        nicknames: list[str],
        output_dir: Path,
        *,
        threads: int = 4,
    ) -> Path:
        """Build a combined minimap2 index from multiple host genomes.

        Concatenates genome.fa.gz files and builds a single .mmi index.
        Uses caching: same combination (order-independent) returns existing index.

        Args:
            nicknames: List of host nicknames to combine.
            output_dir: Directory for the combined index output.
            threads: Number of threads for minimap2.

        Returns:
            Path to the combined .mmi index file.

        Raises:
            KeyError: If any nickname is not registered.
        """
        # Sort for order-independent caching
        sorted_names = sorted(nicknames)
        cache_key = hashlib.md5("_".join(sorted_names).encode()).hexdigest()[:12]
        combined_name = f"combined_{'_'.join(sorted_names)}_{cache_key}"
        mmi_path = output_dir / f"{combined_name}.mmi"

        # Cache hit: return existing index
        if mmi_path.exists():
            logger.info("Using cached combined index: %s", mmi_path)
            return mmi_path

        # Verify all hosts exist
        fasta_paths = self.get_host_paths(sorted_names)

        # Concatenate FASTAs
        combined_fasta = output_dir / f"{combined_name}.fa.gz"
        with open(combined_fasta, "wb") as out_f:
            for fasta in fasta_paths:
                with open(fasta, "rb") as in_f:
                    shutil.copyfileobj(in_f, out_f)
        logger.info("Concatenated %d genomes -> %s", len(fasta_paths), combined_fasta)

        # Build minimap2 index
        cmd = [
            "minimap2", "-t", str(threads),
            "-d", str(mmi_path), str(combined_fasta),
        ]
        logger.info("Building combined minimap2 index: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logger.error(
                "minimap2 failed (exit %d): %s",
                result.returncode,
                result.stderr.strip(),
            )
            raise RuntimeError(
                f"Combined index build failed: {result.stderr.strip()}"
            )

        # Cleanup intermediate FASTA
        combined_fasta.unlink(missing_ok=True)
        logger.info("Combined index created: %s", mmi_path)

        return mmi_path
