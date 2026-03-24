# @TASK T-DB-INDEX - Database indexer for DeepInvirus
# @SPEC docs/planning/04-database-design.md
# @TEST tests/test_db_indexer.py
"""Database indexer for DeepInvirus.

Manages index building and status checking for all reference databases:
- Diamond: FASTA -> .dmnd (diamond makedb)
- MMseqs2: FASTA -> mmseqs DB (mmseqs createdb)
- minimap2: FASTA -> .mmi (minimap2 -d)
- geNomad: pre-built (download only)
- Taxonomy: flat files (names.dmp, nodes.dmp) -- no indexing needed

Usage:
    indexer = DBIndexer(Path("databases"))
    status = indexer.get_index_status()
    cmd = indexer.rebuild_index("viral_protein", threads=8)
"""

from __future__ import annotations

import json
from pathlib import Path


class DBIndexer:
    """Manages index building for all reference databases.

    Args:
        db_dir: Root database directory (e.g., Path("databases")).
    """

    def __init__(self, db_dir: Path) -> None:
        self.db_dir = Path(db_dir)

    # ------------------------------------------------------------------
    # Internal: component registry
    # ------------------------------------------------------------------

    # Maps component key -> (source_glob, index_glob, tool_name)
    _COMPONENT_DEFS: dict[str, dict[str, str]] = {
        "viral_protein": {
            "source_pattern": "viral_protein/uniref90_viral.fasta.gz",
            "index_pattern": "viral_protein/uniref90_viral.dmnd",
            "tool": "diamond",
        },
        "viral_nucleotide": {
            "source_pattern": "viral_nucleotide/refseq_viral.fna.gz",
            "index_pattern": "viral_nucleotide/refseq_viral_db",
            "tool": "mmseqs2",
        },
        "genomad_db": {
            "source_pattern": "genomad_db/",
            "index_pattern": None,
            "tool": "pre-built",
        },
        "taxonomy": {
            "source_pattern": "taxonomy/",
            "index_pattern": None,
            "tool": "N/A",
        },
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_index_status(self) -> list[dict]:
        """Return index status for all DB components.

        Returns:
            List of dicts with keys:
                component (str): Component identifier.
                source (str): Source file/directory name.
                index (str | None): Index file name or None.
                indexed (bool): Whether the index exists.
                size_mb (float): Size of the component directory in MB.
                tool (str): Indexing tool name.
                rebuild_cmd (str | None): Command to rebuild the index.
        """
        result: list[dict] = []

        # Core components
        for comp_key, comp_def in self._COMPONENT_DEFS.items():
            source_path = self._resolve_source(comp_key)
            index_path = self._resolve_index(comp_key)

            indexed = self.check_index_exists(comp_key)
            size_mb = self._compute_size_mb(comp_key)

            source_name = comp_def["source_pattern"].rstrip("/")
            index_name = (
                comp_def["index_pattern"].rstrip("/")
                if comp_def["index_pattern"]
                else None
            )

            rebuild_cmd = self._build_rebuild_cmd(comp_key, threads=32)

            result.append({
                "component": comp_key,
                "source": source_name,
                "index": index_name,
                "indexed": indexed,
                "size_mb": size_mb,
                "tool": comp_def["tool"],
                "rebuild_cmd": rebuild_cmd,
            })

        # Host genomes
        host_dir = self.db_dir / "host_genomes"
        if host_dir.is_dir():
            for entry in sorted(host_dir.iterdir()):
                if not entry.is_dir() or entry.name.startswith("_"):
                    continue

                comp_name = f"host:{entry.name}"
                fasta = entry / "genome.fa.gz"
                mmi = entry / "genome.mmi"

                size_bytes = sum(
                    f.stat().st_size for f in entry.iterdir() if f.is_file()
                )
                size_mb = round(size_bytes / (1024 * 1024), 2)

                result.append({
                    "component": comp_name,
                    "source": f"host_genomes/{entry.name}/genome.fa.gz",
                    "index": f"host_genomes/{entry.name}/genome.mmi",
                    "indexed": mmi.exists(),
                    "size_mb": size_mb,
                    "tool": "minimap2",
                    "rebuild_cmd": self._build_rebuild_cmd(comp_name, threads=32),
                })

        return result

    def check_index_exists(self, component: str) -> bool:
        """Check whether the index for a component exists.

        Args:
            component: Component key (e.g. 'viral_protein', 'host:tmol').

        Returns:
            True if the index files exist, False otherwise.
        """
        if component.startswith("host:"):
            host_name = component.split(":", 1)[1]
            mmi = self.db_dir / "host_genomes" / host_name / "genome.mmi"
            return mmi.exists()

        if component not in self._COMPONENT_DEFS:
            return False

        comp_def = self._COMPONENT_DEFS[component]

        if component == "genomad_db":
            # Pre-built: check that the directory has content
            gdir = self.db_dir / "genomad_db"
            return gdir.is_dir() and any(gdir.iterdir())

        if component == "taxonomy":
            # Taxonomy: check names.dmp and nodes.dmp exist
            tdir = self.db_dir / "taxonomy"
            return (
                tdir.is_dir()
                and (tdir / "names.dmp").exists()
                and (tdir / "nodes.dmp").exists()
            )

        # For diamond/mmseqs2: check the index file
        index_pattern = comp_def.get("index_pattern")
        if index_pattern is None:
            return False

        index_path = self.db_dir / index_pattern
        return index_path.exists()

    def rebuild_index(self, component: str, threads: int = 32) -> str | None:
        """Generate a shell command to rebuild the index for a component.

        Args:
            component: Component key.
            threads: Number of threads to use.

        Returns:
            Shell command string, or None/empty for components without
            rebuild support.

        Raises:
            ValueError: If the component is unknown.
        """
        if component.startswith("host:"):
            return self._build_rebuild_cmd(component, threads=threads)

        if component not in self._COMPONENT_DEFS:
            raise ValueError(f"Unknown component: {component}")

        return self._build_rebuild_cmd(component, threads=threads)

    def rebuild_all(self, threads: int = 32) -> list[str]:
        """Generate rebuild commands for all components with missing indices.

        Args:
            threads: Number of threads to use.

        Returns:
            List of shell command strings for components needing rebuild.
        """
        commands: list[str] = []
        for entry in self.get_index_status():
            if not entry["indexed"] and entry["rebuild_cmd"]:
                commands.append(entry["rebuild_cmd"])
        return commands

    def get_source_file(self, component: str) -> Path | None:
        """Return the source file/directory path for a component.

        Args:
            component: Component key.

        Returns:
            Path to the source file or directory, or None if unknown.
        """
        if component.startswith("host:"):
            host_name = component.split(":", 1)[1]
            fasta = self.db_dir / "host_genomes" / host_name / "genome.fa.gz"
            return fasta if fasta.exists() else None

        if component not in self._COMPONENT_DEFS:
            return None

        source_pattern = self._COMPONENT_DEFS[component]["source_pattern"]
        path = self.db_dir / source_pattern.rstrip("/")

        # For directory-based sources (genomad_db, taxonomy)
        if source_pattern.endswith("/"):
            return path if path.is_dir() else None

        return path if path.exists() else None

    def get_index_file(self, component: str) -> Path | None:
        """Return the index file path for a component.

        Args:
            component: Component key.

        Returns:
            Path to the index file, or None if not applicable or missing.
        """
        if component.startswith("host:"):
            host_name = component.split(":", 1)[1]
            mmi = self.db_dir / "host_genomes" / host_name / "genome.mmi"
            return mmi if mmi.exists() else None

        if component not in self._COMPONENT_DEFS:
            return None

        index_pattern = self._COMPONENT_DEFS[component].get("index_pattern")
        if index_pattern is None:
            return None

        path = self.db_dir / index_pattern
        return path if path.exists() else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_source(self, component: str) -> Path | None:
        """Resolve the source path for a core component."""
        if component not in self._COMPONENT_DEFS:
            return None
        pattern = self._COMPONENT_DEFS[component]["source_pattern"]
        path = self.db_dir / pattern.rstrip("/")
        return path if path.exists() else None

    def _resolve_index(self, component: str) -> Path | None:
        """Resolve the index path for a core component."""
        if component not in self._COMPONENT_DEFS:
            return None
        pattern = self._COMPONENT_DEFS[component].get("index_pattern")
        if pattern is None:
            return None
        path = self.db_dir / pattern
        return path if path.exists() else None

    def _compute_size_mb(self, component: str) -> float:
        """Compute the total size of a component's directory in MB."""
        if component.startswith("host:"):
            host_name = component.split(":", 1)[1]
            comp_dir = self.db_dir / "host_genomes" / host_name
        elif component in ("genomad_db", "taxonomy"):
            comp_dir = self.db_dir / component
        elif component == "viral_protein":
            comp_dir = self.db_dir / "viral_protein"
        elif component == "viral_nucleotide":
            comp_dir = self.db_dir / "viral_nucleotide"
        else:
            return 0.0

        if not comp_dir.is_dir():
            return 0.0

        total_bytes = 0
        try:
            for f in comp_dir.rglob("*"):
                if f.is_file():
                    try:
                        total_bytes += f.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass

        return round(total_bytes / (1024 * 1024), 2)

    def _build_rebuild_cmd(
        self, component: str, threads: int = 32
    ) -> str | None:
        """Build the shell command string for rebuilding an index.

        Args:
            component: Component key.
            threads: Thread count.

        Returns:
            Command string or None.
        """
        if component == "viral_protein":
            source = self.db_dir / "viral_protein" / "uniref90_viral.fasta.gz"
            index = self.db_dir / "viral_protein" / "uniref90_viral.dmnd"
            return (
                f"diamond makedb --in {source} --db {index} "
                f"--threads {threads}"
            )

        if component == "viral_nucleotide":
            source = self.db_dir / "viral_nucleotide" / "refseq_viral.fna.gz"
            index = self.db_dir / "viral_nucleotide" / "refseq_viral_db"
            return f"mmseqs createdb {source} {index}"

        if component.startswith("host:"):
            host_name = component.split(":", 1)[1]
            host_dir = self.db_dir / "host_genomes" / host_name
            fasta = host_dir / "genome.fa.gz"
            mmi = host_dir / "genome.mmi"
            return f"minimap2 -t {threads} -d {mmi} {fasta}"

        if component == "genomad_db":
            return f"genomad download-database {self.db_dir / 'genomad_db'}"

        if component == "taxonomy":
            # Taxonomy does not have an index rebuild step
            return None

        return None
