# @TASK T0.7 - NCBI taxonomy processing utilities
# @SPEC docs/planning/02-trd.md#4-핵심-출력-테이블-스키마
# @SPEC docs/planning/04-database-design.md#1-참조-데이터베이스-구조
"""NCBI taxonomy and ICTV classification utilities.

Provides functions to load NCBI taxdump files, resolve full lineages,
and map virus families/genera to ICTV classification.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# @TASK T0.7 - Standard 7-rank lineage used throughout the pipeline
ICTV_RANKS: list[str] = [
    "domain",
    "phylum",
    "class",
    "order",
    "family",
    "genus",
    "species",
]

# NCBI rank name -> canonical rank mapping
_NCBI_RANK_MAP: dict[str, str] = {
    "superkingdom": "domain",
    "kingdom": "domain",
    "phylum": "phylum",
    "class": "class",
    "order": "order",
    "family": "family",
    "genus": "genus",
    "species": "species",
}


def load_taxdump(taxdump_dir: Path) -> dict[str, Any]:
    """Load NCBI taxdump (names.dmp + nodes.dmp) into memory.

    Args:
        taxdump_dir: Path to the directory containing names.dmp and
            nodes.dmp files (typically ncbi_taxdump/).

    Returns:
        Dictionary with two keys:
            - ``names``: dict mapping taxid (int) -> scientific name (str)
            - ``nodes``: dict mapping taxid (int) -> (parent_taxid, rank)

    Raises:
        FileNotFoundError: If names.dmp or nodes.dmp is missing.
        ValueError: If a .dmp file has unexpected format.
    """
    names_path = Path(taxdump_dir) / "names.dmp"
    nodes_path = Path(taxdump_dir) / "nodes.dmp"

    if not names_path.exists():
        raise FileNotFoundError(f"names.dmp not found in {taxdump_dir}")
    if not nodes_path.exists():
        raise FileNotFoundError(f"nodes.dmp not found in {taxdump_dir}")

    # Parse names.dmp  --  keep only scientific names
    names: dict[int, str] = {}
    logger.info("Loading names.dmp from %s", names_path)
    with open(names_path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 4:
                raise ValueError(
                    f"names.dmp line {lineno}: expected >=4 fields, "
                    f"got {len(parts)}"
                )
            name_class = parts[3]
            if name_class == "scientific name":
                taxid = int(parts[0])
                names[taxid] = parts[1]

    # Parse nodes.dmp
    nodes: dict[int, tuple[int, str]] = {}
    logger.info("Loading nodes.dmp from %s", nodes_path)
    with open(nodes_path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3:
                raise ValueError(
                    f"nodes.dmp line {lineno}: expected >=3 fields, "
                    f"got {len(parts)}"
                )
            taxid = int(parts[0])
            parent_taxid = int(parts[1])
            rank = parts[2]
            nodes[taxid] = (parent_taxid, rank)

    logger.info(
        "Loaded %d names and %d nodes from taxdump", len(names), len(nodes)
    )
    return {"names": names, "nodes": nodes}


def get_lineage(taxid: int, tax_db: dict[str, Any]) -> dict[str, str]:
    """Resolve a taxid to a 7-rank lineage dictionary.

    Walks up the NCBI taxonomy tree from the given taxid to the root,
    collecting ranks that belong to the standard 7 levels
    (domain, phylum, class, order, family, genus, species).

    Args:
        taxid: NCBI Taxonomy ID to resolve.
        tax_db: Taxonomy database dict returned by :func:`load_taxdump`.

    Returns:
        Dictionary with keys from :data:`ICTV_RANKS`. Missing ranks
        are set to ``"Unclassified"``.

    Raises:
        KeyError: If the taxid is not found in the taxonomy database.
    """
    names: dict[int, str] = tax_db["names"]
    nodes: dict[int, tuple[int, str]] = tax_db["nodes"]

    if taxid not in nodes:
        raise KeyError(f"taxid {taxid} not found in taxonomy database")

    lineage: dict[str, str] = {rank: "Unclassified" for rank in ICTV_RANKS}

    current = taxid
    visited: set[int] = set()
    max_depth = 100  # safety guard against circular references

    for _ in range(max_depth):
        if current in visited:
            logger.warning("Circular reference detected at taxid %d", current)
            break
        visited.add(current)

        parent, ncbi_rank = nodes.get(current, (1, "no rank"))
        canonical = _NCBI_RANK_MAP.get(ncbi_rank)
        if canonical and current in names:
            lineage[canonical] = names[current]

        # root node points to itself
        if current == parent or current == 1:
            break
        current = parent

    return lineage


def load_ictv_vmr(vmr_path: Path) -> pd.DataFrame:
    """Load ICTV Virus Metadata Resource (VMR) from a TSV file.

    The VMR file is expected to be tab-separated with at minimum the
    columns: Family, Genus, Species, and optionally higher ranks.

    Args:
        vmr_path: Path to the ICTV VMR TSV file.

    Returns:
        DataFrame with VMR contents (columns preserved as-is).

    Raises:
        FileNotFoundError: If the VMR file does not exist.
        ValueError: If required columns are missing.
    """
    vmr_path = Path(vmr_path)
    if not vmr_path.exists():
        raise FileNotFoundError(f"ICTV VMR file not found: {vmr_path}")

    logger.info("Loading ICTV VMR from %s", vmr_path)
    df = pd.read_csv(vmr_path, sep="\t", dtype=str)
    df.columns = df.columns.str.strip()

    # Validate required columns (case-insensitive check)
    col_lower = {c.lower(): c for c in df.columns}
    required = ["family", "genus", "species"]
    missing = [r for r in required if r not in col_lower]
    if missing:
        raise ValueError(
            f"ICTV VMR missing required columns: {missing}. "
            f"Available: {list(df.columns)}"
        )

    logger.info("Loaded %d records from ICTV VMR", len(df))
    return df


def map_ictv_classification(
    family: str,
    genus: str,
    vmr_df: pd.DataFrame,
) -> str:
    """Map a virus family/genus pair to its ICTV classification string.

    Tries to match on genus first (more specific), then falls back to
    family-level matching.  Returns the ICTV species name or a
    family-level label when no genus match is found.

    Args:
        family: Virus family name (e.g. ``"Coronaviridae"``).
        genus: Virus genus name (e.g. ``"Betacoronavirus"``).
        vmr_df: DataFrame returned by :func:`load_ictv_vmr`.

    Returns:
        ICTV classification string.  ``"Unclassified"`` if no match.
    """
    if vmr_df.empty:
        return "Unclassified"

    # Normalise column access (case-insensitive)
    col_lower = {c.lower(): c for c in vmr_df.columns}
    family_col = col_lower.get("family", "Family")
    genus_col = col_lower.get("genus", "Genus")
    species_col = col_lower.get("species", "Species")

    # Try genus-level match first
    if genus and genus != "Unclassified":
        mask = vmr_df[genus_col].str.lower() == genus.lower()
        matches = vmr_df.loc[mask]
        if not matches.empty:
            species_val = matches.iloc[0][species_col]
            if pd.notna(species_val) and str(species_val).strip():
                return str(species_val).strip()

    # Fall back to family-level match
    if family and family != "Unclassified":
        mask = vmr_df[family_col].str.lower() == family.lower()
        matches = vmr_df.loc[mask]
        if not matches.empty:
            return f"{family} (family-level match)"

    return "Unclassified"
