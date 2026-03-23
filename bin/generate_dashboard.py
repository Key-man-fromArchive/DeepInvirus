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

    n_sequences = len(bigtable)

    # Top virus: highest mean RPM across samples from the matrix
    top_virus = "N/A"
    if not matrix.empty and "taxon" in matrix.columns:
        sample_cols = [c for c in matrix.columns if c not in ("taxon", "taxid", "rank")]
        if sample_cols:
            matrix_vals = matrix[sample_cols].apply(pd.to_numeric, errors="coerce")
            mean_rpm = matrix_vals.mean(axis=1)
            if not mean_rpm.empty:
                top_idx = mean_rpm.idxmax()
                top_virus = str(matrix.loc[top_idx, "taxon"])

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

    Hierarchy: Domain → Family → Genus (05-design-system.md section 6.2)

    Returns a dict with keys: nodes, sources, targets, values, node_colors
    """
    PALETTE = [
        "#1F77B4", "#FF7F0E", "#2CA02C", "#D62728",
        "#9467BD", "#8C564B", "#7F7F7F",
    ]

    if bigtable.empty:
        return {"nodes": [], "sources": [], "targets": [], "values": [], "node_colors": []}

    required = {"domain", "family", "genus"}
    if not required.issubset(bigtable.columns):
        return {"nodes": [], "sources": [], "targets": [], "values": [], "node_colors": []}

    # Aggregate total count by (domain, family, genus)
    count_col = "count" if "count" in bigtable.columns else None
    grp_cols = ["domain", "family", "genus"]
    if count_col:
        agg = (
            bigtable[grp_cols + [count_col]]
            .dropna(subset=grp_cols)
            .groupby(grp_cols, as_index=False)[count_col]
            .sum()
        )
    else:
        agg = (
            bigtable[grp_cols]
            .dropna()
            .value_counts()
            .reset_index(name="count")
        )

    # Build unique node list  (domain nodes, then family, then genus)
    domains = sorted(agg["domain"].unique())
    families = sorted(agg["family"].unique())
    genera = sorted(agg["genus"].unique())

    nodes = domains + families + genera
    node_idx = {n: i for i, n in enumerate(nodes)}

    # Colour: cycle palette over node slots
    node_colors = [
        PALETTE[i % len(PALETTE)] for i in range(len(nodes))
    ]

    sources: list[int] = []
    targets: list[int] = []
    values: list[float] = []

    # Domain → Family links
    df_links = agg.groupby(["domain", "family"], as_index=False)["count"].sum()
    for _, row in df_links.iterrows():
        if row["domain"] in node_idx and row["family"] in node_idx:
            sources.append(node_idx[row["domain"]])
            targets.append(node_idx[row["family"]])
            values.append(_safe_float(row["count"], 1))

    # Family → Genus links
    fg_links = agg.groupby(["family", "genus"], as_index=False)["count"].sum()
    for _, row in fg_links.iterrows():
        if row["family"] in node_idx and row["genus"] in node_idx:
            sources.append(node_idx[row["family"]])
            targets.append(node_idx[row["genus"]])
            values.append(_safe_float(row["count"], 1))

    return {
        "nodes": nodes,
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
        return {"samples": [], "taxa": [], "values": []}

    meta_cols = {"taxon", "taxid", "rank"}
    sample_cols = [c for c in matrix.columns if c not in meta_cols]
    if not sample_cols:
        return {"samples": [], "taxa": [], "values": []}

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
# Main render function
# ---------------------------------------------------------------------------


def build_dashboard_data(
    bigtable: pd.DataFrame,
    matrix: pd.DataFrame,
    alpha: pd.DataFrame,
    beta: pd.DataFrame,
    pcoa: pd.DataFrame,
) -> dict[str, Any]:
    """Assemble the full data dict injected as ``window.__DASHBOARD_DATA__``."""
    return {
        "summary": build_summary(bigtable, matrix),
        "sankey": build_sankey(bigtable),
        "heatmap": build_heatmap(matrix),
        "barplot": build_barplot(matrix),
        "pcoa": build_pcoa_data(pcoa, beta),
        "alpha": build_alpha_data(alpha),
        "search_rows": build_search_rows(bigtable),
        "samples": list(bigtable["sample"].dropna().unique()) if not bigtable.empty and "sample" in bigtable.columns else [],
    }


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
        return json.dumps(value, ensure_ascii=False, default=str)

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

        data = build_dashboard_data(bigtable, matrix, alpha, beta, pcoa)
        render_dashboard(data, Path(args.output))
    except Exception:
        logger.exception("Dashboard generation failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
