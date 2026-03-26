#!/usr/bin/env python3
# @TASK T5.1 - Generate standalone HTML dashboard from analysis TSV files
# @SPEC docs/planning/05-design-system.md#2-대시보드-설계
# @SPEC docs/planning/04-database-design.md#4-핵심-출력-테이블-스키마
# @SPEC docs/planning/02-trd.md#2.3-보고서-시각화
# @TEST tests/modules/test_dashboard.py
"""Generate a standalone interactive HTML dashboard for DeepInvirus results.

Reads five TSV input files, converts them to JSON data structures, and
renders ``assets/dashboard_template.html`` (Jinja2 template) to produce
a single self-contained ``dashboard.html`` file that requires only a
web browser and a network connection for the Plotly.js CDN.

Usage
-----
::

    python generate_dashboard.py \\
        --bigtable  bigtable.tsv \\
        --matrix    sample_taxon_matrix.tsv \\
        --alpha     alpha_diversity.tsv \\
        --beta      beta_diversity.tsv \\
        --pcoa      pcoa_coordinates.tsv \\
        --output    dashboard.html
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Jinja2 (required; listed in requirements.txt)
# ---------------------------------------------------------------------------
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError as exc:  # pragma: no cover
    sys.exit(f"[generate_dashboard] ERROR: Jinja2 is required. Run: pip install jinja2\n{exc}")

logger = logging.getLogger(__name__)

# Template is located relative to this script's package root
_ASSETS_DIR = Path(__file__).parent.parent / "assets"
_TEMPLATE_NAME = "dashboard_template.html"
PLOTLY_VERSION = "2.32.0"

ICTV_FAMILY_COLORS = {
    "Parvoviridae": "#E69F00",
    "Baculoviridae": "#56B4E9",
    "Sinhaliviridae": "#009E73",
    "Bromoviridae": "#F0E442",
    "Picornaviridae": "#0072B2",
    "Flaviviridae": "#D55E00",
    "Narnaviridae": "#CC79A7",
    "Mitoviridae": "#882255",
    "Endornaviridae": "#44AA99",
    "Virgaviridae": "#332288",
    "Fiersviridae": "#DDCC77",
    "Adintoviridae": "#117733",
    "Iflaviridae": "#88CCEE",
    "Dicistroviridae": "#AA4499",
    "Nodaviridae": "#661100",
    "Iridoviridae": "#6699CC",
    "Nudiviridae": "#888888",
    "Genomoviridae": "#AA4466",
    "Unclassified": "#CCCCCC",
}


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def load_bigtable(path: Path) -> pd.DataFrame:
    """Load bigtable.tsv (04-database-design.md section 4.1).

    Returns an empty DataFrame with correct columns if the file is missing
    or empty, so downstream code does not crash.
    """
    if not path.exists():
        logger.warning("bigtable not found: %s", path)
        return pd.DataFrame()
    df = pd.read_csv(path, sep="\t", dtype=str)
    # Ensure numeric columns are cast correctly
    for col in ("count", "rpm", "coverage", "detection_score", "length", "taxid"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_matrix(path: Path) -> pd.DataFrame:
    """Load sample_taxon_matrix.tsv (04-database-design.md section 4.2).

    Rows are taxa; columns are taxon, taxid, rank, then one column per sample.
    """
    if not path.exists():
        logger.warning("Matrix not found: %s", path)
        return pd.DataFrame()
    return pd.read_csv(path, sep="\t")


def load_alpha(path: Path) -> pd.DataFrame:
    """Load alpha_diversity.tsv (04-database-design.md section 4.3)."""
    if not path.exists():
        logger.warning("Alpha diversity not found: %s", path)
        return pd.DataFrame()
    return pd.read_csv(path, sep="\t")


def load_beta(path: Path) -> pd.DataFrame:
    """Load beta_diversity.tsv – square Bray-Curtis distance matrix."""
    if not path.exists():
        logger.warning("Beta diversity not found: %s", path)
        return pd.DataFrame()
    return pd.read_csv(path, sep="\t", index_col=0)


def load_pcoa(path: Path) -> pd.DataFrame:
    """Load pcoa_coordinates.tsv (columns: sample, PC1, PC2, ...).

    Returns an empty DataFrame if the file is missing, empty, or
    cannot be parsed.
    """
    if not path.exists():
        logger.warning("PCoA coordinates not found: %s", path)
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, sep="\t")
        return df
    except Exception as exc:
        logger.warning("Failed to read PCoA coordinates from %s: %s", path, exc)
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Data-to-JSON converters
# ---------------------------------------------------------------------------


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to a finite float, returning *default* on failure."""
    try:
        v = float(value)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def get_family_color(family_name: Any) -> str:
    """Return the canonical color for a family, falling back deterministically per name."""
    family = _safe_str(family_name) or "Unclassified"
    if family.lower() in {"unknown", "review"}:
        family = "Unclassified"
    return ICTV_FAMILY_COLORS.get(
        family,
        "#" + hex(hash(family) % 0xFFFFFF)[2:].zfill(6),
    )


def infer_family_name(row: pd.Series | dict[str, Any]) -> str:
    """Extract a usable family label from a row-like object."""
    family = _safe_str(row.get("family", ""))
    return family or "Unclassified"


def build_host_removal_data(host_stats: pd.DataFrame) -> dict[str, Any]:
    """Build host removal statistics data for the dashboard.

    # @TASK T1.2 - Host removal statistics in dashboard

    Returns a dict with keys:
        samples: list of sample names
        mapped_reads: list of host-mapped read counts
        unmapped_reads: list of non-host read counts
        host_pct: list of host mapping percentages
        total_reads: list of total read counts
    """
    if host_stats.empty:
        return {
            "samples": [],
            "mapped_reads": [],
            "unmapped_reads": [],
            "host_pct": [],
            "total_reads": [],
        }

    samples = host_stats["sample"].tolist() if "sample" in host_stats.columns else []
    mapped = (
        host_stats["mapped_reads"].astype(int).tolist()
        if "mapped_reads" in host_stats.columns else []
    )
    unmapped = (
        host_stats["unmapped_reads"].astype(int).tolist()
        if "unmapped_reads" in host_stats.columns else []
    )
    host_pct = (
        [_safe_float(v) for v in host_stats["host_removal_rate"].tolist()]
        if "host_removal_rate" in host_stats.columns else []
    )
    total = (
        host_stats["total_reads"].astype(int).tolist()
        if "total_reads" in host_stats.columns else []
    )

    return {
        "samples": samples,
        "mapped_reads": mapped,
        "unmapped_reads": unmapped,
        "host_pct": host_pct,
        "total_reads": total,
    }


def build_summary(bigtable: pd.DataFrame, matrix: pd.DataFrame) -> dict[str, Any]:
    """Compute overview summary card values.

    Returns a dict with keys:
        n_samples, n_species, n_sequences, top_virus, n_methods
    """
    if bigtable.empty:
        return {
            "n_samples": 0,
            "n_species": 0,
            "n_sequences": 0,
            "top_virus": "N/A",
            "n_methods": 0,
        }

    samples = bigtable["sample"].dropna().unique() if "sample" in bigtable.columns else []
    n_samples = len(samples)

    species_col = "species" if "species" in bigtable.columns else (
        "genus" if "genus" in bigtable.columns else None
    )
    n_species = bigtable[species_col].dropna().nunique() if species_col else 0

    n_sequences = bigtable["seq_id"].nunique()

    # Top virus: most abundant taxon (genus or species with highest RPM)
    top_virus = "N/A"
    if not matrix.empty and "taxon" in matrix.columns:
        sample_cols = [c for c in matrix.columns if c not in ("taxon", "taxid", "rank")]
        if sample_cols:
            matrix_vals = matrix[sample_cols].apply(pd.to_numeric, errors="coerce")
            mean_rpm = matrix_vals.mean(axis=1)
            if not mean_rpm.empty:
                # Skip "Unclassified" if possible
                for idx in mean_rpm.sort_values(ascending=False).index:
                    candidate = str(matrix.loc[idx, "taxon"])
                    if candidate.lower() not in ("unclassified", "nan", ""):
                        top_virus = candidate
                        break
                if top_virus == "N/A" and not mean_rpm.empty:
                    top_virus = str(matrix.loc[mean_rpm.idxmax(), "taxon"])
    # Fallback to most frequent genus in bigtable
    if top_virus in ("N/A", "Unclassified") and "genus" in bigtable.columns:
        genus_counts = bigtable["genus"].dropna().astype(str).str.strip()
        genus_counts = genus_counts[genus_counts != ""].value_counts()
        if not genus_counts.empty:
            top_virus = genus_counts.index[0]

    n_methods = 0
    if "detection_method" in bigtable.columns:
        n_methods = bigtable["detection_method"].dropna().nunique()

    return {
        "n_samples": int(n_samples),
        "n_species": int(n_species),
        "n_sequences": int(n_sequences),
        "top_virus": top_virus,
        "n_methods": int(n_methods),
    }


def build_sankey(bigtable: pd.DataFrame) -> dict[str, Any]:
    """Build Plotly Sankey trace data from bigtable.

    Hierarchy: Domain → Phylum → Class → Order → Family → Genus → Species
    Only ranks with meaningful data are included.

    Returns a dict with keys: nodes, sources, targets, values, node_colors
    """
    empty = {"nodes": [], "sources": [], "targets": [], "values": [], "node_colors": []}
    if bigtable.empty:
        return empty

    all_ranks = ["domain", "phylum", "class", "order", "family", "genus", "species"]
    # Keep only ranks that exist and have non-empty data
    ranks = [r for r in all_ranks if r in bigtable.columns
             and not bigtable[r].dropna().empty
             and not bigtable[r].dropna().astype(str).str.strip().eq("").all()]
    if len(ranks) < 2:
        return empty

    # Use unique contigs only (bigtable has per-sample rows)
    unique_bt = bigtable.drop_duplicates(subset=["seq_id"]) if "seq_id" in bigtable.columns else bigtable

    # Clean rank columns
    bt_clean = unique_bt[ranks].copy()
    for c in ranks:
        bt_clean[c] = bt_clean[c].astype(str).str.strip().replace({"": pd.NA, "nan": pd.NA})

    # Build unique nodes with rank prefix to avoid collision (e.g. "Unclassified" at multiple ranks)
    # node_key = "rank:name", display_label = "name"
    node_keys: list[str] = []
    node_labels: list[str] = []
    node_key_set: set[str] = set()

    for rank in ranks:
        for name in sorted(bt_clean[rank].dropna().unique()):
            key = f"{rank}:{name}"
            if key not in node_key_set:
                node_key_set.add(key)
                node_keys.append(key)
                node_labels.append(name)

    node_idx = {k: i for i, k in enumerate(node_keys)}

    # Colour: family nodes use ICTV colours, descendants inherit, ancestors neutral
    family_of: dict[str, str] = {}  # node_key → family name
    if "family" in ranks:
        for _, row in bt_clean.dropna(subset=["family"]).iterrows():
            fam = str(row["family"])
            for rank in ranks:
                val = row.get(rank)
                if pd.notna(val) and str(val).strip():
                    family_of[f"{rank}:{val}"] = fam

    node_colors = []
    ancestor_ranks = {"domain", "phylum", "class", "order"}
    for key in node_keys:
        rank_name = key.split(":")[0]
        if rank_name in ancestor_ranks and rank_name != "family":
            node_colors.append("#D9D9D9")
        else:
            fam = family_of.get(key, "Unclassified")
            node_colors.append(get_family_color(fam))

    # Build links between adjacent rank pairs
    sources: list[int] = []
    targets: list[int] = []
    values: list[float] = []

    for i in range(len(ranks) - 1):
        parent_rank, child_rank = ranks[i], ranks[i + 1]
        pair = bt_clean[[parent_rank, child_rank]].dropna()
        if pair.empty:
            continue
        link_counts = pair.value_counts().reset_index(name="count")
        for _, row in link_counts.iterrows():
            p_key = f"{parent_rank}:{row[parent_rank]}"
            c_key = f"{child_rank}:{row[child_rank]}"
            if p_key in node_idx and c_key in node_idx and p_key != c_key:
                sources.append(node_idx[p_key])
                targets.append(node_idx[c_key])
                values.append(int(row["count"]))

    return {
        "nodes": node_labels,
        "sources": sources,
        "targets": targets,
        "values": values,
        "node_colors": node_colors,
    }


def build_heatmap(matrix: pd.DataFrame) -> dict[str, Any]:
    """Build Plotly heatmap data (log10 RPM + 1) from the taxon matrix.

    Returns a dict with keys: z (2-D list), samples, taxa
    """
    if matrix.empty or "taxon" not in matrix.columns:
        return {"z": [], "samples": [], "taxa": []}

    meta_cols = {"taxon", "taxid", "rank"}
    sample_cols = [c for c in matrix.columns if c not in meta_cols]
    if not sample_cols:
        return {"z": [], "samples": [], "taxa": []}

    taxa = matrix["taxon"].tolist()
    vals = matrix[sample_cols].apply(pd.to_numeric, errors="coerce").fillna(0)

    # log10(RPM + 1) transform
    log_vals = np.log10(vals.values + 1)

    return {
        "z": log_vals.tolist(),
        "samples": sample_cols,
        "taxa": taxa,
    }


def build_barplot(matrix: pd.DataFrame, top_n: int = 20) -> dict[str, Any]:
    """Build stacked barplot data (relative abundance) from the taxon matrix.

    Returns a dict with keys: samples, taxa, values (list of lists)
    """
    if matrix.empty or "taxon" not in matrix.columns:
        return {"samples": [], "taxa": [], "values": [], "colors": []}

    meta_cols = {"taxon", "taxid", "rank"}
    sample_cols = [c for c in matrix.columns if c not in meta_cols]
    if not sample_cols:
        return {"samples": [], "taxa": [], "values": [], "colors": []}

    vals = matrix[sample_cols].apply(pd.to_numeric, errors="coerce").fillna(0)
    taxa = matrix["taxon"].tolist()

    # Relative abundance per sample (column sum normalisation)
    col_sums = vals.sum(axis=0).replace(0, 1)
    rel = vals.div(col_sums, axis=1)

    # Top-N taxa by mean relative abundance
    mean_rel = rel.mean(axis=1)
    top_idx = mean_rel.nlargest(top_n).index.tolist()
    other_idx = [i for i in range(len(taxa)) if i not in top_idx]

    result_taxa: list[str] = [taxa[i] for i in top_idx]
    result_values: list[list[float]] = [
        rel.iloc[i].tolist() for i in top_idx
    ]

    # "Others" row
    if other_idx:
        others = rel.iloc[other_idx].sum(axis=0)
        if others.sum() > 0:
            result_taxa.append("Others")
            result_values.append(others.tolist())

    return {
        "samples": sample_cols,
        "taxa": result_taxa,
        "values": result_values,
        "colors": [get_family_color(taxon) if taxon != "Others" else "#BDBDBD" for taxon in result_taxa],
    }


def build_pcoa_data(pcoa_df: pd.DataFrame, beta_df: pd.DataFrame) -> dict[str, Any]:
    """Build PCoA scatter data for Plotly.

    Prefers pre-computed PCoA coordinates (pcoa_df).  If unavailable,
    falls back to computing classical MDS from beta_df.

    Returns a dict with keys: samples, pc1, pc2, pc1_var, pc2_var
    """
    # ---- Case 1: pre-computed coordinates --------------------------------
    if not pcoa_df.empty and "sample" in pcoa_df.columns:
        pc1_col = next(
            (c for c in pcoa_df.columns if c.upper() in ("PC1", "DIM1")), None
        )
        pc2_col = next(
            (c for c in pcoa_df.columns if c.upper() in ("PC2", "DIM2")), None
        )
        if pc1_col and pc2_col:
            return {
                "samples": pcoa_df["sample"].tolist(),
                "pc1": [_safe_float(v) for v in pcoa_df[pc1_col].tolist()],
                "pc2": [_safe_float(v) for v in pcoa_df[pc2_col].tolist()],
                "pc1_var": None,
                "pc2_var": None,
            }

    # ---- Case 2: compute from beta diversity matrix ----------------------
    if beta_df.empty:
        return {"samples": [], "pc1": [], "pc2": [], "pc1_var": None, "pc2_var": None}

    dist = beta_df.values.astype(float)
    n = dist.shape[0]
    if n < 2:
        return {"samples": [], "pc1": [], "pc2": [], "pc1_var": None, "pc2_var": None}

    # Classical MDS (double centring)
    h = np.eye(n) - np.ones((n, n)) / n
    b = -0.5 * h @ (dist ** 2) @ h

    eigenvalues, eigenvectors = np.linalg.eigh(b)
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    pos_ev = eigenvalues[eigenvalues > 0]
    total_var = pos_ev.sum()
    pc1_var = float(eigenvalues[0] / total_var * 100) if total_var > 0 else 0.0
    pc2_var = float(eigenvalues[1] / total_var * 100) if (total_var > 0 and n > 2) else 0.0

    coords = eigenvectors[:, :2] * np.sqrt(np.maximum(eigenvalues[:2], 0))

    return {
        "samples": list(beta_df.index),
        "pc1": [_safe_float(v) for v in coords[:, 0].tolist()],
        "pc2": [_safe_float(v) for v in coords[:, 1].tolist()],
        "pc1_var": round(pc1_var, 2),
        "pc2_var": round(pc2_var, 2),
    }


def build_alpha_data(alpha_df: pd.DataFrame) -> dict[str, Any]:
    """Build alpha diversity data for Plotly boxplot.

    Returns a dict with keys: samples, shannon, simpson, observed_species,
    chao1, pielou_evenness (each a list of floats).
    """
    if alpha_df.empty:
        return {
            "samples": [], "shannon": [], "simpson": [],
            "observed_species": [], "chao1": [], "pielou_evenness": []
        }

    result: dict[str, Any] = {
        "samples": alpha_df["sample"].tolist() if "sample" in alpha_df.columns else [],
    }
    for metric in ("shannon", "simpson", "observed_species", "chao1", "pielou_evenness"):
        if metric in alpha_df.columns:
            result[metric] = [_safe_float(v) for v in alpha_df[metric].tolist()]
        else:
            result[metric] = []

    return result


def build_search_rows(bigtable: pd.DataFrame) -> list[dict[str, Any]]:
    """Build a flat list of row dicts for the Search tab table.

    Each dict contains: taxon, rank, family, sample, rpm, detection_method,
    baltimore_group.
    """
    if bigtable.empty:
        return []

    col_map = {
        "taxon": "species",
        "rank": None,          # derived
        "family": "family",
        "sample": "sample",
        "rpm": "rpm",
        "detection_method": "detection_method",
        "baltimore_group": "baltimore_group",
    }

    rows: list[dict[str, Any]] = []
    for _, row in bigtable.iterrows():
        taxon = str(row.get("species", row.get("genus", ""))) if not pd.isna(row.get("species", "")) else str(row.get("genus", ""))
        family = str(row.get("family", "")) if not pd.isna(row.get("family", pd.NA)) else ""
        sample = str(row.get("sample", ""))
        rpm = _safe_float(row.get("rpm", 0))
        det = str(row.get("detection_method", ""))
        baltimore = str(row.get("baltimore_group", "")) if not pd.isna(row.get("baltimore_group", pd.NA)) else ""

        # Infer rank from taxon columns
        rank = "unknown"
        if not pd.isna(row.get("species", pd.NA)) and str(row.get("species", "")).strip():
            rank = "species"
        elif not pd.isna(row.get("genus", pd.NA)) and str(row.get("genus", "")).strip():
            rank = "genus"
        elif not pd.isna(row.get("family", pd.NA)) and str(row.get("family", "")).strip():
            rank = "family"

        rows.append({
            "taxon": taxon,
            "rank": rank,
            "family": family,
            "sample": sample,
            "rpm": rpm,
            "detection_method": det,
            "baltimore_group": baltimore,
        })

    return rows


# ---------------------------------------------------------------------------
# @TASK T5.2 - Dashboard v2 extended data structures
# @SPEC docs/planning/05-design-system.md#Sunburst-Treemap
# ---------------------------------------------------------------------------


def _build_sunburst_tree(bt: pd.DataFrame, ranks: list[str]) -> dict[str, Any]:
    """Build Plotly Sunburst-compatible tree from a (possibly filtered) bigtable.

    Each node gets a unique ``id`` built from its full taxonomic path
    (e.g. ``"Viruses/Uroviricota/Caudoviricetes"``).  Leaf values are the
    summed RPM; if RPM is absent, the row count is used instead.

    Parameters
    ----------
    bt:
        A bigtable-like DataFrame (ideally already deduplicated by seq_id).
    ranks:
        Ordered list of column names forming the hierarchy, e.g.
        ``["domain", "phylum", "class", "order", "family"]``.

    Returns
    -------
    dict
        ``{"ids": [...], "labels": [...], "parents": [...], "values": [...]}``
    """
    node_values: dict[str, float] = {}
    node_parent: dict[str, str] = {}
    node_colors: dict[str, str] = {}

    has_rpm = "rpm" in bt.columns

    for _, row in bt.iterrows():
        rpm = _safe_float(row.get("rpm", 0)) if has_rpm else 1.0
        family_color = get_family_color(infer_family_name(row))
        path_parts: list[str] = []
        for rank in ranks:
            val = str(row.get(rank, "")).strip()
            if val and val.lower() != "nan" and val != "":
                path_parts.append(val)
                node_id = "/".join(path_parts)
                parent_id = "/".join(path_parts[:-1]) if len(path_parts) > 1 else ""
                node_values[node_id] = node_values.get(node_id, 0.0) + rpm
                node_parent[node_id] = parent_id
                node_colors[node_id] = family_color

    ids = list(node_values.keys())
    labels = [nid.split("/")[-1] for nid in ids]
    parents = [node_parent[nid] for nid in ids]
    values = [round(node_values[nid], 2) for nid in ids]
    colors = [node_colors.get(nid, "#CCCCCC") for nid in ids]

    return {"ids": ids, "labels": labels, "parents": parents, "values": values, "colors": colors}


def build_taxonomy_tree(bigtable: pd.DataFrame) -> dict[str, Any]:
    """Build hierarchical taxonomy data for Plotly Sunburst / Treemap.

    # @TASK T5.2.1 - Sunburst/Treemap taxonomy tree
    # @SPEC docs/planning/05-design-system.md#Sunburst-Treemap

    Returns a dict with keys:
        - ``"all"``: combined all-sample tree
        - ``"per_sample"``: ``{sample_name: tree_data}``

    Each *tree_data* dict has Plotly-compatible arrays:
    ``ids``, ``labels``, ``parents``, ``values`` (RPM sum).
    """
    all_ranks = ["domain", "phylum", "class", "order", "family", "genus", "species"]

    if bigtable.empty:
        empty = {"ids": [], "labels": [], "parents": [], "values": []}
        return {"all": empty, "per_sample": {}}

    # Use unique contigs only (bigtable has per-sample rows)
    unique_bt = (
        bigtable.drop_duplicates(subset=["seq_id"])
        if "seq_id" in bigtable.columns
        else bigtable
    )

    # Filter to ranks that exist in DataFrame and have meaningful data
    available_ranks = []
    for r in all_ranks:
        if r in bigtable.columns:
            col = bigtable[r].dropna().astype(str).str.strip()
            if not col.empty and not col.eq("").all():
                available_ranks.append(r)
    if not available_ranks:
        empty = {"ids": [], "labels": [], "parents": [], "values": []}
        return {"all": empty, "per_sample": {}}

    all_tree = _build_sunburst_tree(unique_bt, available_ranks)

    per_sample: dict[str, dict] = {}
    if "sample" in bigtable.columns:
        for sample in sorted(bigtable["sample"].dropna().unique()):
            sample_bt = bigtable[bigtable["sample"] == sample]
            per_sample[str(sample)] = _build_sunburst_tree(sample_bt, available_ranks)

    return {"all": all_tree, "per_sample": per_sample}


def build_per_sample_sankey(bigtable: pd.DataFrame) -> dict[str, Any]:
    """Build per-sample Sankey data by calling ``build_sankey`` per sample.

    # @TASK T5.2.2 - Per-sample Sankey diagrams
    # @SPEC docs/planning/05-design-system.md#Enhanced-Sankey

    Returns a dict ``{sample_name: sankey_data}``.
    """
    if bigtable.empty or "sample" not in bigtable.columns:
        return {}

    result: dict[str, Any] = {}
    for sample in sorted(bigtable["sample"].dropna().unique()):
        sample_bt = bigtable[bigtable["sample"] == sample]
        result[str(sample)] = build_sankey(sample_bt)

    return result


def build_search_rows_v2(bigtable: pd.DataFrame) -> list[dict[str, Any]]:
    """Build enhanced search table data with all taxonomy ranks and per-sample metrics.

    # @TASK T5.2.3 - Enhanced search table (v2)
    # @SPEC docs/planning/05-design-system.md#Search-v2

    Uses a pivot approach for efficient per-sample metric lookup instead of
    repeated DataFrame filtering.

    Returns a list of dicts, one per unique contig (seq_id).  Each dict
    includes taxonomy fields plus a ``coverage_per_sample`` nested dict.
    """
    if bigtable.empty:
        return []

    # Deduplicate for contig-level attributes
    unique_bt = (
        bigtable.drop_duplicates(subset=["seq_id"])
        if "seq_id" in bigtable.columns
        else bigtable
    )

    samples = sorted(bigtable["sample"].dropna().unique()) if "sample" in bigtable.columns else []

    # Pre-pivot per-sample metrics for efficient lookup
    # Build: {seq_id: {sample: {coverage, rpm, breadth}}}
    per_sample_lookup: dict[str, dict[str, dict[str, float]]] = {}
    if "seq_id" in bigtable.columns and samples:
        metric_cols = []
        for col in ("coverage", "rpm", "breadth"):
            if col in bigtable.columns:
                metric_cols.append(col)

        if metric_cols:
            for _, row in bigtable.iterrows():
                sid = str(row.get("seq_id", ""))
                sample = str(row.get("sample", ""))
                if not sid or not sample:
                    continue
                if sid not in per_sample_lookup:
                    per_sample_lookup[sid] = {}
                metrics: dict[str, float] = {}
                for col in metric_cols:
                    metrics[col] = round(_safe_float(row.get(col, 0)), 4)
                per_sample_lookup[sid][sample] = metrics

    rows: list[dict[str, Any]] = []
    for _, row in unique_bt.iterrows():
        seq_id = str(row.get("seq_id", ""))

        # Build per-sample coverage dict from pre-built lookup
        coverage_per_sample: dict[str, dict[str, float]] = {}
        seq_lookup = per_sample_lookup.get(seq_id, {})
        for s in samples:
            coverage_per_sample[s] = seq_lookup.get(s, {
                "coverage": 0.0, "rpm": 0.0, "breadth": 0.0,
            })

        # Build full taxonomy string from rank columns if taxonomy field is empty
        taxonomy_str = _safe_str(row.get("taxonomy", ""))
        if not taxonomy_str:
            ranks_list = [_safe_str(row.get(r, "")) for r in
                          ["domain", "phylum", "class", "order", "family", "genus", "species"]]
            taxonomy_str = "; ".join(r for r in ranks_list if r)

        # Use lineage family if geNomad family is Unclassified
        family = _safe_str(row.get("family", ""))
        if family in ("Unclassified", ""):
            for r in ["family", "order", "class", "phylum"]:
                val = _safe_str(row.get(r, ""))
                if val and val != "Unclassified":
                    family = val
                    break

        entry: dict[str, Any] = {
            "seq_id": seq_id,
            "length": int(_safe_float(row.get("length", 0))),
            "family": family,
            "genus": _safe_str(row.get("genus", "")),
            "species": _safe_str(row.get("species", "")),
            "domain": _safe_str(row.get("domain", "")),
            "phylum": _safe_str(row.get("phylum", "")),
            "class": _safe_str(row.get("class", "")),
            "order": _safe_str(row.get("order", "")),
            "family_color": get_family_color(family),
            "detection_method": _safe_str(row.get("detection_method", "")),
            "detection_score": round(_safe_float(row.get("detection_score", 0)), 3),
            "detection_confidence": _safe_str(row.get("detection_confidence", "")),
            "best_hit": _safe_str(row.get("subject_id", row.get("target", ""))),
            "pident": _safe_str(row.get("pident", "")),
            "taxonomy": taxonomy_str,
            "taxid": _safe_str(row.get("taxid", "")),
            "evidence_classification": _safe_str(row.get("evidence_classification", "")),
            "evidence_score": _safe_str(row.get("evidence_score", "")),
            "evidence_support_tier": _safe_str(row.get("evidence_support_tier", "")),
            "coverage_per_sample": coverage_per_sample,
        }
        rows.append(entry)

    return rows


def _safe_str(value: Any) -> str:
    """Convert a value to a non-NaN string, returning empty string on failure."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


def build_filter_options(bigtable: pd.DataFrame) -> dict[str, Any]:
    """Build dropdown filter option lists for the dashboard UI.

    # @TASK T5.2.4 - Dashboard filter options
    # @SPEC docs/planning/05-design-system.md#Filters

    Returns a dict with sorted unique values for each filterable dimension.
    """
    if bigtable.empty:
        return {
            "samples": [],
            "families": [],
            "genera": [],
            "detection_methods": [],
            "confidence_tiers": ["high", "medium", "low"],
        }

    samples = (
        sorted(bigtable["sample"].dropna().unique().tolist())
        if "sample" in bigtable.columns else []
    )

    families = []
    if "family" in bigtable.columns:
        families = sorted([
            f for f in bigtable["family"].dropna().unique()
            if str(f).strip() and str(f).strip().lower() not in ("unclassified", "nan")
        ])

    genera = []
    if "genus" in bigtable.columns:
        genera = sorted([
            str(g) for g in bigtable["genus"].dropna().unique()
            if str(g).strip() and str(g).strip().lower() != "nan"
        ])

    detection_methods = (
        sorted(bigtable["detection_method"].dropna().unique().tolist())
        if "detection_method" in bigtable.columns else []
    )

    return {
        "samples": [str(s) for s in samples],
        "families": [str(f) for f in families],
        "genera": genera,
        "detection_methods": [str(d) for d in detection_methods],
        "confidence_tiers": ["high", "medium", "low"],
    }


def build_comparison_data(bigtable: pd.DataFrame) -> dict[str, Any]:
    """Build sample comparison payload for family- and contig-level views."""
    if bigtable.empty or "sample" not in bigtable.columns:
        return {"family": [], "contig": [], "samples": []}

    samples = sorted(bigtable["sample"].dropna().unique())
    unique_bt = bigtable.drop_duplicates(subset=["seq_id"]) if "seq_id" in bigtable.columns else bigtable

    family_data: list[dict[str, Any]] = []
    if "family" in unique_bt.columns:
        for family in sorted(unique_bt["family"].dropna().astype(str).unique()):
            family_name = _safe_str(family) or "Unclassified"
            row: dict[str, Any] = {
                "name": family_name,
                "type": "family",
                "family": family_name,
                "color": get_family_color(family_name),
                "count": int(len(unique_bt[unique_bt["family"] == family])),
            }
            for sample in samples:
                sample_bt = bigtable[
                    (bigtable["family"] == family) & (bigtable["sample"] == sample)
                ]
                row[f"{sample}_rpm"] = round(sample_bt["rpm"].sum(), 2) if "rpm" in sample_bt.columns else 0.0
                row[f"{sample}_count"] = int(len(sample_bt))
            if len(samples) == 2:
                v1 = row.get(f"{samples[0]}_rpm", 0)
                v2 = row.get(f"{samples[1]}_rpm", 0)
                row["log2fc"] = round(math.log2(v2 / v1), 2) if v1 > 0 and v2 > 0 else None
            family_data.append(row)

    contig_data: list[dict[str, Any]] = []
    if "seq_id" in unique_bt.columns:
        for seq_id in unique_bt["seq_id"].dropna().astype(str).unique():
            contig_rows = bigtable[bigtable["seq_id"] == seq_id]
            if contig_rows.empty:
                continue
            first = contig_rows.iloc[0]
            family_name = infer_family_name(first)
            row = {
                "name": seq_id,
                "type": "contig",
                "family": family_name,
                "color": get_family_color(family_name),
                "length": int(_safe_float(first.get("length", 0))),
            }
            for sample in samples:
                sr = contig_rows[contig_rows["sample"] == sample]
                row[f"{sample}_rpm"] = round(_safe_float(sr["rpm"].iloc[0]), 2) if len(sr) > 0 and "rpm" in sr.columns else 0.0
                row[f"{sample}_cov"] = round(_safe_float(sr["coverage"].iloc[0]), 2) if len(sr) > 0 and "coverage" in sr.columns else 0.0
            if len(samples) == 2:
                v1 = row.get(f"{samples[0]}_rpm", 0)
                v2 = row.get(f"{samples[1]}_rpm", 0)
                row["log2fc"] = round(math.log2(v2 / v1), 2) if v1 > 0 and v2 > 0 else None
            contig_data.append(row)

    return {"family": family_data, "contig": contig_data, "samples": [str(s) for s in samples]}


def load_contig_sequences(contigs_path: Path | None, bigtable: pd.DataFrame, top_n: int = 0) -> dict[str, str]:
    """Load contig sequences from FASTA. top_n=0 means all contigs in bigtable."""
    if not contigs_path or not contigs_path.exists() or bigtable.empty or "seq_id" not in bigtable.columns:
        return {}

    all_ids = bigtable["seq_id"].dropna().astype(str).unique().tolist()
    if top_n > 0 and "rpm" in bigtable.columns:
        top_ids = (
            bigtable.groupby("seq_id", as_index=False)["rpm"]
            .sum()
            .sort_values("rpm", ascending=False)["seq_id"]
            .head(top_n)
            .astype(str)
            .tolist()
        )
    elif top_n > 0:
        top_ids = all_ids[:top_n]
    else:
        top_ids = all_ids
    top_id_set = set(top_ids)
    if not top_id_set:
        return {}

    sequences: dict[str, str] = {}
    current_id: str | None = None
    current_seq: list[str] = []

    with contigs_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_id in top_id_set and current_seq:
                    sequences[current_id] = "".join(current_seq)
                    if len(sequences) >= len(top_id_set):
                        break
                current_id = line[1:].split()[0]
                current_seq = []
            elif current_id in top_id_set:
                current_seq.append(line)

    if current_id in top_id_set and current_seq and current_id not in sequences:
        sequences[current_id] = "".join(current_seq)

    ordered_sequences: dict[str, str] = {}
    for seq_id in top_ids:
        if seq_id in sequences:
            ordered_sequences[seq_id] = sequences[seq_id]
    return ordered_sequences


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively replace NaN / Infinity with None for JSON serialization.

    Python's ``json.dumps`` outputs ``NaN`` / ``Infinity`` literals which
    are invalid JSON.  This helper walks a nested structure and converts
    them to ``None`` (which becomes ``null`` in JSON).
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(v) for v in obj]
    # Handle numpy types
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.ndarray):
        return _sanitize_for_json(obj.tolist())
    return obj


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------


def build_coverage_data(
    bigtable: pd.DataFrame,
    coverage_data: dict[str, pd.DataFrame],
) -> dict[str, Any]:
    """Build per-sample coverage data for the dashboard coverage tab.

    Returns a dict with keys:
        contigs: list of contig IDs
        families: list of family names
        lengths: list of contig lengths
        samples: list of sample names
        z: 2D list of log10(coverage + 1) values
        raw_values: 2D list of raw coverage values
        labels: list of "family (contig)" labels for heatmap y-axis
    """
    if bigtable.empty or not coverage_data:
        return {
            "contigs": [], "families": [], "lengths": [], "samples": [],
            "z": [], "raw_values": [], "labels": [],
        }

    # Use unique contigs only (bigtable may have one row per seq_id x sample)
    unique_bt = bigtable.drop_duplicates(subset=["seq_id"])
    viral_contigs = unique_bt["seq_id"].tolist()
    families = unique_bt.set_index("seq_id")["family"].to_dict() if "family" in unique_bt.columns else {}
    lengths = unique_bt.set_index("seq_id")["length"].to_dict() if "length" in unique_bt.columns else {}

    sample_names = sorted(coverage_data.keys())

    # Build coverage matrix: contigs x samples
    rows = []
    for contig in viral_contigs:
        row = []
        for sample in sample_names:
            cov_df = coverage_data.get(sample, pd.DataFrame())
            if not cov_df.empty and "Contig" in cov_df.columns:
                match = cov_df[cov_df["Contig"] == contig]
                if not match.empty:
                    row.append(_safe_float(match.iloc[0].get("mean_coverage", 0)))
                else:
                    row.append(0.0)
            else:
                row.append(0.0)
        rows.append(row)

    # Sort by max coverage descending
    max_covs = [max(row) if row else 0 for row in rows]
    sorted_indices = sorted(range(len(viral_contigs)), key=lambda i: max_covs[i], reverse=True)

    sorted_contigs = [viral_contigs[i] for i in sorted_indices]
    sorted_families = [families.get(viral_contigs[i], "Unknown") for i in sorted_indices]
    sorted_lengths = [int(lengths.get(viral_contigs[i], 0)) for i in sorted_indices]
    sorted_rows = [rows[i] for i in sorted_indices]

    # Log transform for heatmap
    z = []
    for row in sorted_rows:
        z.append([round(float(np.log10(v + 1)), 3) for v in row])

    # Labels for y-axis
    labels = [f"{f} ({c})" for f, c in zip(sorted_families, sorted_contigs)]

    return {
        "contigs": sorted_contigs,
        "families": sorted_families,
        "lengths": sorted_lengths,
        "samples": sample_names,
        "z": z,
        "raw_values": [[round(v, 2) for v in row] for row in sorted_rows],
        "labels": labels,
    }


def build_dashboard_data(
    bigtable: pd.DataFrame,
    matrix: pd.DataFrame,
    alpha: pd.DataFrame,
    beta: pd.DataFrame,
    pcoa: pd.DataFrame,
    host_stats: pd.DataFrame | None = None,
    coverage_data: dict[str, pd.DataFrame] | None = None,
    contig_sequences: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Assemble the full data dict injected as ``window.__DASHBOARD_DATA__``.

    Parameters
    ----------
    host_stats:
        Optional host removal stats DataFrame (from parse_host_removal.py).
        If provided, host removal data is included in the dashboard.
    coverage_data:
        Optional dict mapping sample name -> coverage DataFrame.
        If provided, per-sample coverage data is included.
    """
    # Fix n_samples: use coverage data or host stats for actual sample count
    summary = build_summary(bigtable, matrix)
    actual_samples = []
    if coverage_data:
        actual_samples = sorted(coverage_data.keys())
    elif host_stats is not None and not host_stats.empty and "sample" in host_stats.columns:
        actual_samples = host_stats["sample"].tolist()
    if actual_samples:
        summary["n_samples"] = len(actual_samples)
        summary["sample_names"] = actual_samples

    samples_list = actual_samples if actual_samples else (
        sorted(bigtable["sample"].dropna().unique().tolist())
        if not bigtable.empty and "sample" in bigtable.columns else []
    )

    data = {
        "summary": summary,
        # Existing keys (backward-compatible)
        "sankey": build_sankey(bigtable),
        "heatmap": build_heatmap(matrix),
        "barplot": build_barplot(matrix),
        "pcoa": build_pcoa_data(pcoa, beta),
        "alpha": build_alpha_data(alpha),
        "search_rows": build_search_rows(bigtable),
        "samples": samples_list,
        "ictv_family_colors": dict(sorted(ICTV_FAMILY_COLORS.items())),
    }

    # @TASK T5.2 - Dashboard v2 extended data structures
    # Sankey: rename existing to sankey_all, add per-sample
    data["sankey_all"] = data["sankey"]  # alias (keep "sankey" for backward compat)
    data["sankey_per_sample"] = build_per_sample_sankey(bigtable)

    # Taxonomy tree for Sunburst / Treemap
    data["taxonomy_tree"] = build_taxonomy_tree(bigtable)

    # Enhanced search table (v2)
    data["search_rows_v2"] = build_search_rows_v2(bigtable)

    # Filter dropdown options
    data["filter_options"] = build_filter_options(bigtable)
    data["comparison"] = build_comparison_data(bigtable)
    data["contig_sequences"] = contig_sequences or {}

    # @TASK T1.2 - Host removal statistics in dashboard
    if host_stats is not None:
        data["host_removal"] = build_host_removal_data(host_stats)
    else:
        data["host_removal"] = build_host_removal_data(pd.DataFrame())

    # Per-sample coverage data
    if coverage_data:
        data["coverage"] = build_coverage_data(bigtable, coverage_data)
    else:
        data["coverage"] = {
            "contigs": [], "families": [], "lengths": [], "samples": [],
            "z": [], "raw_values": [], "labels": [],
        }

    return data


def load_coverage_files(coverage_dir: Path) -> dict[str, pd.DataFrame]:
    """Load all *_coverage.tsv files from coverage directory.

    Returns a dict mapping sample name -> DataFrame with columns:
        Contig, mean_coverage, trimmed_mean, covered_bases, length
    """
    result = {}
    if not coverage_dir or not coverage_dir.exists():
        return result

    for f in sorted(coverage_dir.glob("*_coverage.tsv")):
        sample_name = f.stem.replace("_coverage", "")
        try:
            df = pd.read_csv(f, sep="\t")
            cols = df.columns.tolist()
            rename_map = {cols[0]: "Contig"}
            if len(cols) > 1:
                rename_map[cols[1]] = "mean_coverage"
            if len(cols) > 2:
                rename_map[cols[2]] = "trimmed_mean"
            if len(cols) > 3:
                rename_map[cols[3]] = "covered_bases"
            if len(cols) > 4:
                rename_map[cols[4]] = "length"
            df = df.rename(columns=rename_map)
            result[sample_name] = df
            logger.info("Loaded coverage for sample '%s': %d contigs", sample_name, len(df))
        except Exception as exc:
            logger.warning("Failed to load coverage from %s: %s", f, exc)

    return result


def load_host_stats_dir(host_stats_dir: Path) -> pd.DataFrame:
    """Load all *.host_removal_stats.txt files and merge."""
    rows = []
    if not host_stats_dir or not host_stats_dir.exists():
        return pd.DataFrame()

    for f in sorted(host_stats_dir.glob("*.host_removal_stats.txt")):
        try:
            df = pd.read_csv(f, sep="\t")
            if not df.empty:
                rows.append(df)
        except Exception as exc:
            logger.warning("Failed to load host stats from %s: %s", f, exc)

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def build_inline_figures(figures_dir: Path | None) -> list[dict[str, str]]:
    """Load PNG figures from *figures_dir* and encode as base64 data URIs.

    Returns a list of dicts: [{"name": "heatmap.png", "data_uri": "data:image/png;base64,..."}]
    """
    import base64

    result = []
    if not figures_dir or not figures_dir.exists():
        return result
    for f in sorted(figures_dir.glob("*.png")):
        try:
            b64 = base64.b64encode(f.read_bytes()).decode("ascii")
            label = f.stem.replace("_", " ").title()
            result.append({
                "name": f.name,
                "label": label,
                "data_uri": f"data:image/png;base64,{b64}",
            })
            logger.info("Embedded figure: %s (%d KB)", f.name, f.stat().st_size // 1024)
        except Exception as exc:
            logger.warning("Failed to embed figure %s: %s", f.name, exc)
    return result


def render_dashboard(
    data: dict[str, Any],
    output_path: Path,
    assets_dir: Path = _ASSETS_DIR,
    template_name: str = _TEMPLATE_NAME,
) -> Path:
    """Render the Jinja2 template and write the standalone HTML file.

    Parameters
    ----------
    data:
        Data dict produced by :func:`build_dashboard_data`.
    output_path:
        Destination path for ``dashboard.html``.
    assets_dir:
        Directory containing *template_name*.
    template_name:
        Jinja2 template file name.

    Returns
    -------
    Path
        Resolved path of the written file.
    """
    env = Environment(
        loader=FileSystemLoader(str(assets_dir)),
        autoescape=select_autoescape(["html"]),
    )

    # Custom tojson filter that handles NaN / Infinity safely
    def _tojson_filter(value: Any) -> str:
        sanitized = _sanitize_for_json(value)
        return json.dumps(sanitized, ensure_ascii=False, default=str)

    env.filters["tojson"] = _tojson_filter

    template = env.get_template(template_name)

    summary = data.get("summary", {})
    rendered = template.render(
        data=data,
        summary=summary,
        generated_at=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        plotly_version=PLOTLY_VERSION,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    logger.info("Dashboard written to %s (%d bytes)", output_path, output_path.stat().st_size)
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="generate_dashboard.py",
        description="Generate a standalone DeepInvirus HTML dashboard.",
    )
    parser.add_argument(
        "--bigtable",
        required=True,
        metavar="TSV",
        help="Path to bigtable.tsv (integrated classification table)",
    )
    parser.add_argument(
        "--matrix",
        required=True,
        metavar="TSV",
        help="Path to sample_taxon_matrix.tsv (sample x taxon RPM matrix)",
    )
    parser.add_argument(
        "--alpha",
        required=True,
        metavar="TSV",
        help="Path to alpha_diversity.tsv (Shannon, Simpson, etc.)",
    )
    parser.add_argument(
        "--beta",
        required=True,
        metavar="TSV",
        help="Path to beta_diversity.tsv (Bray-Curtis distance matrix)",
    )
    parser.add_argument(
        "--pcoa",
        required=True,
        metavar="TSV",
        help="Path to pcoa_coordinates.tsv (pre-computed PCoA coordinates)",
    )
    parser.add_argument(
        "--output",
        required=True,
        metavar="HTML",
        default="dashboard.html",
        help="Output path for the standalone dashboard.html",
    )
    parser.add_argument(
        "--host-stats",
        metavar="TSV",
        default=None,
        help="Path to host_removal_stats.tsv (from parse_host_removal.py)",
    )
    parser.add_argument(
        "--coverage-dir",
        metavar="DIR",
        default=None,
        help="Directory containing per-sample *_coverage.tsv files",
    )
    parser.add_argument(
        "--host-stats-dir",
        metavar="DIR",
        default=None,
        help="Directory containing *.host_removal_stats.txt files",
    )
    parser.add_argument(
        "--figures-dir",
        metavar="DIR",
        default=None,
        help="Directory containing result figure PNGs to embed as inline images",
    )
    parser.add_argument(
        "--contigs",
        metavar="FASTA",
        default=None,
        help="Path to the co-assembly contig FASTA for embedding top contig sequences",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging verbosity (default: INFO)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point for CLI invocation.

    Returns
    -------
    int
        Exit code (0 = success, 1 = error).
    """
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        bigtable = load_bigtable(Path(args.bigtable))
        matrix = load_matrix(Path(args.matrix))
        alpha = load_alpha(Path(args.alpha))
        beta = load_beta(Path(args.beta))
        pcoa = load_pcoa(Path(args.pcoa))

        # Load host removal stats if provided
        host_stats = None
        if args.host_stats_dir:
            host_stats = load_host_stats_dir(Path(args.host_stats_dir))
            if not host_stats.empty:
                logger.info("Loaded host removal stats from dir: %d samples", len(host_stats))
        if (host_stats is None or host_stats.empty) and args.host_stats:
            host_path = Path(args.host_stats)
            if host_path.exists():
                host_stats = pd.read_csv(host_path, sep="\t")
                logger.info("Loaded host removal stats: %d samples", len(host_stats))
            else:
                logger.warning("Host stats file not found: %s", host_path)

        # Load per-sample coverage data
        coverage_data = None
        if args.coverage_dir:
            coverage_data = load_coverage_files(Path(args.coverage_dir))
            if coverage_data:
                logger.info("Loaded coverage for %d samples", len(coverage_data))

        contig_sequences = {}
        if args.contigs:
            contig_sequences = load_contig_sequences(Path(args.contigs), bigtable)
            if contig_sequences:
                logger.info("Embedded %d contig sequences from %s", len(contig_sequences), args.contigs)

        data = build_dashboard_data(
            bigtable,
            matrix,
            alpha,
            beta,
            pcoa,
            host_stats,
            coverage_data,
            contig_sequences,
        )

        # Embed result figures as inline base64 images
        figures_dir = Path(args.figures_dir) if args.figures_dir else None
        data["inline_figures"] = build_inline_figures(figures_dir)

        render_dashboard(data, Path(args.output))
    except Exception:
        logger.exception("Dashboard generation failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
