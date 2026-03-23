# @TASK T0.7 - Matplotlib/seaborn visualization utilities
# @SPEC docs/planning/05-design-system.md#3-컬러-팔레트
# @SPEC docs/planning/05-design-system.md#4-타이포그래피
# @SPEC docs/planning/05-design-system.md#6-figure-생성-규격
"""Shared matplotlib/seaborn configuration and plot functions.

All functions apply the DeepInvirus design-system specifications
(05-design-system.md): Arial fonts, 300 DPI, standard colour palette,
and figure sizes per chart type.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.patches import Ellipse
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# @TASK T0.7 - Design-system colour palette (section 3.1)
# ---------------------------------------------------------------------------
DEEPINVIRUS_PALETTE: list[str] = [
    "#1F77B4",  # Deep Blue   - DNA virus / primary
    "#FF7F0E",  # Orange      - RNA virus
    "#2CA02C",  # Green       - dsDNA
    "#D62728",  # Red         - ssRNA
    "#9467BD",  # Purple      - ssDNA
    "#8C564B",  # Brown       - dsRNA
    "#7F7F7F",  # Gray        - Unclassified
]

HEATMAP_CMAP = "YlOrRd"  # abundance heatmap (section 3.2)
DIVERSITY_CMAP = "viridis"  # diversity heatmap
PRESENCE_CMAP = "Blues"  # presence/absence

# Design-system figure defaults (section 6.1)
DEFAULT_DPI = 300
DEFAULT_FIGSIZE = (8, 6)
DEFAULT_BG = "#FFFFFF"


def setup_matplotlib() -> None:
    """Apply DeepInvirus figure conventions to the global matplotlib rcParams.

    Settings applied (from 05-design-system.md section 4.3 & 6.1):
        - Font family: Arial (fallback: DejaVu Sans)
        - Title: 14 pt bold
        - Axis labels: 12 pt
        - Tick labels: 10 pt
        - Legend: 10 pt
        - Resolution: 300 DPI
        - Background: white, no frame border
        - Default figure size: 8 x 6 inches

    This function is idempotent and safe to call multiple times.
    """
    # Use non-interactive backend for pipeline/server environments
    matplotlib.use("Agg")

    plt.rcParams.update(
        {
            # Fonts (section 4.3)
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Helvetica"],
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 12,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            # Figure (section 6.1)
            "figure.figsize": DEFAULT_FIGSIZE,
            "figure.dpi": DEFAULT_DPI,
            "savefig.dpi": DEFAULT_DPI,
            "savefig.bbox": "tight",
            "savefig.facecolor": DEFAULT_BG,
            "figure.facecolor": DEFAULT_BG,
            # Clean style
            "axes.facecolor": DEFAULT_BG,
            "axes.edgecolor": "#333333",
            "axes.grid": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    logger.info("Matplotlib rcParams configured for DeepInvirus design system")


# ---------------------------------------------------------------------------
# @TASK T0.7 - Taxonomic heatmap with clustering
# @SPEC docs/planning/05-design-system.md#6-figure-생성-규격
# ---------------------------------------------------------------------------


def plot_heatmap(
    matrix_df: pd.DataFrame,
    output_path: Path,
    **kwargs: Any,
) -> Path:
    """Generate a taxonomic heatmap with hierarchical clustering.

    The matrix is expected to have taxa as rows and samples as columns,
    with values representing abundance (e.g. RPM).  Values are
    log10-transformed before plotting.

    Args:
        matrix_df: Taxa (rows) x samples (columns) abundance matrix.
        output_path: File path for the saved figure (PNG or SVG).
        **kwargs: Additional keyword arguments forwarded to
            :func:`seaborn.clustermap`.

    Returns:
        The resolved output path.

    Raises:
        ValueError: If the matrix is empty.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    if matrix_df.empty:
        raise ValueError("Cannot plot heatmap: matrix is empty")

    # Ensure taxon column is index, not data
    hm_df = matrix_df.copy()
    if "taxon" in hm_df.columns:
        hm_df = hm_df.set_index("taxon")
    hm_df = hm_df.apply(pd.to_numeric, errors="coerce").fillna(0)

    # Log10 transform (add pseudocount)
    log_matrix = np.log10(hm_df.astype(float) + 1)

    # Figure size scales with matrix dimensions (section 6.2: 10x8 base)
    n_rows, n_cols = log_matrix.shape
    fig_width = max(10, n_cols * 0.6 + 3)
    fig_height = max(8, n_rows * 0.3 + 3)

    clustermap_kwargs: dict[str, Any] = {
        "cmap": HEATMAP_CMAP,
        "figsize": (fig_width, fig_height),
        "linewidths": 0.5,
        "linecolor": "white",
        "dendrogram_ratio": (0.15, 0.15),
        "cbar_kws": {"label": "log10(RPM + 1)"},
        "method": "ward",
        "metric": "euclidean",
    }
    clustermap_kwargs.update(kwargs)

    try:
        g = sns.clustermap(log_matrix, **clustermap_kwargs)
        g.ax_heatmap.set_xlabel("Samples", fontsize=12)
        g.ax_heatmap.set_ylabel("Taxa", fontsize=12)
        g.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
        plt.close(g.fig)
    except Exception:
        logger.exception("Failed to generate heatmap")
        raise

    logger.info("Heatmap saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# @TASK T0.7 - Relative abundance barplot
# ---------------------------------------------------------------------------


def plot_barplot(
    matrix_df: pd.DataFrame,
    output_path: Path,
    top_n: int = 20,
) -> Path:
    """Generate a stacked barplot of relative abundances per sample.

    Shows the top N most abundant taxa across all samples; remaining
    taxa are grouped as "Others".

    Args:
        matrix_df: Taxa (rows) x samples (columns) abundance matrix.
        output_path: File path for the saved figure.
        top_n: Number of top taxa to display (default 20).

    Returns:
        The resolved output path.

    Raises:
        ValueError: If the matrix is empty.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    if matrix_df.empty:
        raise ValueError("Cannot plot barplot: matrix is empty")

    # Ensure taxon/index column is not mixed with numeric data
    df = matrix_df.copy()
    if "taxon" in df.columns:
        df = df.set_index("taxon")
    # Convert all columns to numeric
    df = df.apply(pd.to_numeric, errors="coerce").fillna(0)

    # Compute relative abundance per sample (column-wise)
    rel_abundance = df.div(df.sum(axis=0), axis=1).fillna(0)

    # Select top-N taxa by mean relative abundance
    mean_abundance = rel_abundance.mean(axis=1).sort_values(ascending=False)
    top_taxa = mean_abundance.head(top_n).index.tolist()

    plot_df = rel_abundance.loc[top_taxa].copy()
    others = rel_abundance.drop(index=top_taxa, errors="ignore").sum(axis=0)
    if others.sum() > 0:
        plot_df.loc["Others"] = others

    # Transpose: samples as rows for stacked bar
    plot_df = plot_df.T

    # Build colour list
    n_colours = len(plot_df.columns)
    palette = (DEEPINVIRUS_PALETTE * ((n_colours // len(DEEPINVIRUS_PALETTE)) + 1))[
        :n_colours
    ]

    fig, ax = plt.subplots(figsize=(8, 6))  # section 6.2: 8x6
    plot_df.plot.bar(stacked=True, color=palette, ax=ax, width=0.8)

    ax.set_ylabel("Relative Abundance")
    ax.set_xlabel("Sample")
    ax.set_title("Viral Community Composition")
    ax.legend(
        title="Taxon",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        fontsize=8,
        title_fontsize=9,
    )
    ax.set_ylim(0, 1)

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)

    logger.info("Barplot saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# @TASK T0.7 - PCoA plot with 95% confidence ellipses
# ---------------------------------------------------------------------------


def _confidence_ellipse(
    x: np.ndarray,
    y: np.ndarray,
    ax: matplotlib.axes.Axes,
    n_std: float = 2.0,
    **kwargs: Any,
) -> Ellipse:
    """Draw an ``n_std``-sigma confidence ellipse on *ax*.

    Args:
        x: X-coordinates.
        y: Y-coordinates.
        ax: Matplotlib axes to draw on.
        n_std: Number of standard deviations (2.0 ~ 95% CI).
        **kwargs: Passed to :class:`matplotlib.patches.Ellipse`.

    Returns:
        The Ellipse patch added to the axes.
    """
    if len(x) < 2:
        return Ellipse((0, 0), 0, 0)  # cannot draw for <2 points

    cov = np.cov(x, y)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)

    # Sort eigenvalues descending
    order = eigenvalues.argsort()[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    angle = np.degrees(np.arctan2(*eigenvectors[:, 0][::-1]))
    width, height = 2 * n_std * np.sqrt(np.maximum(eigenvalues, 0))

    ellipse = Ellipse(
        xy=(np.mean(x), np.mean(y)),
        width=width,
        height=height,
        angle=angle,
        **kwargs,
    )
    ax.add_patch(ellipse)
    return ellipse


def plot_pcoa(
    distance_matrix: pd.DataFrame,
    groups: dict[str, list[str]],
    output_path: Path,
) -> Path:
    """Generate a PCoA ordination plot with 95% confidence ellipses.

    Args:
        distance_matrix: Square, symmetric Bray-Curtis distance matrix
            (index and columns are sample names).
        groups: Mapping of group name -> list of sample names belonging
            to that group.
        output_path: File path for the saved figure.

    Returns:
        The resolved output path.

    Raises:
        ValueError: If the distance matrix is not square or is empty.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    if distance_matrix.empty:
        raise ValueError("Cannot plot PCoA: distance matrix is empty")
    if distance_matrix.shape[0] != distance_matrix.shape[1]:
        raise ValueError("Distance matrix must be square")

    # Classical MDS / PCoA via eigendecomposition
    n = distance_matrix.shape[0]
    dist = distance_matrix.values.astype(float)

    # Double-centring
    h = np.eye(n) - np.ones((n, n)) / n
    b = -0.5 * h @ (dist**2) @ h

    eigenvalues, eigenvectors = np.linalg.eigh(b)
    # Take the two largest positive eigenvalues
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # Proportion of variance explained
    pos_eigenvalues = eigenvalues[eigenvalues > 0]
    total_var = pos_eigenvalues.sum()
    pc1_var = eigenvalues[0] / total_var * 100 if total_var > 0 else 0
    pc2_var = eigenvalues[1] / total_var * 100 if total_var > 0 else 0

    coords = eigenvectors[:, :2] * np.sqrt(
        np.maximum(eigenvalues[:2], 0)
    )
    sample_names = list(distance_matrix.index)

    fig, ax = plt.subplots(figsize=(8, 8))  # section 6.2: 8x8 square

    palette = DEEPINVIRUS_PALETTE
    for gi, (group_name, members) in enumerate(groups.items()):
        colour = palette[gi % len(palette)]
        member_idx = [
            i for i, s in enumerate(sample_names) if s in members
        ]
        if not member_idx:
            continue

        xs = coords[member_idx, 0]
        ys = coords[member_idx, 1]

        ax.scatter(
            xs, ys, label=group_name, color=colour, s=60, zorder=3
        )

        # 95% confidence ellipse (n_std=2.0)
        if len(member_idx) >= 3:
            _confidence_ellipse(
                xs,
                ys,
                ax,
                n_std=2.0,
                facecolor=colour,
                alpha=0.15,
                edgecolor=colour,
                linewidth=1.5,
            )

    ax.set_xlabel(f"PC1 ({pc1_var:.1f}%)")
    ax.set_ylabel(f"PC2 ({pc2_var:.1f}%)")
    ax.set_title("PCoA (Bray-Curtis)")
    ax.legend(title="Group")
    ax.set_aspect("equal", adjustable="datalim")

    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)

    logger.info("PCoA plot saved to %s", output_path)
    return output_path


# ---------------------------------------------------------------------------
# @TASK T0.7 - Alpha diversity boxplot
# ---------------------------------------------------------------------------


def plot_alpha_diversity(
    alpha_df: pd.DataFrame,
    output_path: Path,
) -> Path:
    """Generate boxplots for alpha diversity metrics.

    Expects a DataFrame with columns: ``sample``, ``shannon``,
    ``simpson``, ``observed_species``, and optionally ``group``.
    Each metric gets its own subplot.

    Args:
        alpha_df: Alpha diversity table (one row per sample).
        output_path: File path for the saved figure.

    Returns:
        The resolved output path.

    Raises:
        ValueError: If the DataFrame is empty or missing required columns.
    """
    setup_matplotlib()
    output_path = Path(output_path)

    if alpha_df.empty:
        raise ValueError("Cannot plot alpha diversity: DataFrame is empty")

    required_cols = {"sample"}
    missing = required_cols - set(alpha_df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Determine metrics present in the DataFrame
    metric_cols = [
        c
        for c in ["shannon", "simpson", "observed_species", "chao1", "pielou_evenness"]
        if c in alpha_df.columns
    ]
    if not metric_cols:
        raise ValueError(
            "No recognised diversity metric columns found. "
            "Expected one or more of: shannon, simpson, observed_species, "
            "chao1, pielou_evenness"
        )

    has_groups = "group" in alpha_df.columns

    n_metrics = len(metric_cols)
    fig, axes = plt.subplots(
        1, n_metrics, figsize=(6, 6), squeeze=False  # section 6.2: 6x6
    )
    axes = axes.flatten()

    metric_labels = {
        "shannon": "Shannon (H')",
        "simpson": "Simpson (1-D)",
        "observed_species": "Observed Species",
        "chao1": "Chao1",
        "pielou_evenness": "Pielou Evenness",
    }

    for i, metric in enumerate(metric_cols):
        ax = axes[i]
        if has_groups:
            sns.boxplot(
                data=alpha_df,
                x="group",
                y=metric,
                palette=DEEPINVIRUS_PALETTE,
                ax=ax,
            )
            sns.stripplot(
                data=alpha_df,
                x="group",
                y=metric,
                color="black",
                size=4,
                alpha=0.6,
                jitter=True,
                ax=ax,
            )
        else:
            sns.boxplot(
                data=alpha_df,
                y=metric,
                color=DEEPINVIRUS_PALETTE[0],
                ax=ax,
            )
            sns.stripplot(
                data=alpha_df,
                y=metric,
                color="black",
                size=4,
                alpha=0.6,
                jitter=True,
                ax=ax,
            )

        ax.set_title(metric_labels.get(metric, metric))
        ax.set_ylabel(metric_labels.get(metric, metric))

    fig.suptitle("Alpha Diversity", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)

    logger.info("Alpha diversity plot saved to %s", output_path)
    return output_path
