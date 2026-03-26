#!/usr/bin/env python3
"""Calculate alpha and beta diversity from a sample-taxon matrix.

# @TASK T4.3 - Diversity analysis
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @SPEC docs/planning/04-database-design.md#4.3-alpha_diversity
# @SPEC docs/planning/04-database-design.md#4.4-beta_diversity
# @TEST tests/modules/test_classification.py

Usage:
    python calc_diversity.py \\
        --matrix sample_taxon_matrix.tsv \\
        --out-alpha alpha_diversity.tsv \\
        --out-beta beta_diversity.tsv \\
        --out-pcoa pcoa_coordinates.tsv

Input:
    - sample_taxon_matrix.tsv: taxon, taxid, rank, {sample_1}, {sample_2}, ...
      (RPM abundance values)

Outputs:
    - alpha_diversity.tsv: sample, observed_species, shannon, simpson, chao1, pielou_evenness
    - beta_diversity.tsv: Bray-Curtis distance matrix (symmetric)
    - pcoa_coordinates.tsv: sample, PC1, PC2, ...
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)
import pandas as pd
from scipy.spatial.distance import braycurtis, squareform


# @TASK T4.3 - Alpha diversity column order (04-database-design.md 4.3)
ALPHA_COLUMNS = [
    "sample",
    "observed_species",
    "shannon",
    "simpson",
    "chao1",
    "pielou_evenness",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Calculate alpha and beta diversity from sample-taxon matrix.",
    )
    parser.add_argument(
        "--matrix",
        required=True,
        type=Path,
        help="Sample-taxon matrix TSV (taxon, taxid, rank, sample_1, ...)",
    )
    parser.add_argument(
        "--out-alpha",
        required=True,
        type=Path,
        help="Output alpha diversity TSV",
    )
    parser.add_argument(
        "--out-beta",
        required=True,
        type=Path,
        help="Output beta diversity (Bray-Curtis) distance matrix TSV",
    )
    parser.add_argument(
        "--out-pcoa",
        required=True,
        type=Path,
        help="Output PCoA coordinates TSV",
    )
    return parser.parse_args(argv)


def shannon_diversity(abundances: np.ndarray) -> float:
    """Calculate Shannon diversity index.

    H' = -sum(pi * ln(pi))

    where pi is the proportional abundance of species i.

    Args:
        abundances: Array of abundance values (non-negative).

    Returns:
        Shannon diversity index. 0.0 for empty or single-species samples.
    """
    # Filter out zeros
    a = abundances[abundances > 0]
    if len(a) <= 1:
        return 0.0
    total = a.sum()
    if total == 0:
        return 0.0
    props = a / total
    return float(-np.sum(props * np.log(props)))


def simpson_diversity(abundances: np.ndarray) -> float:
    """Calculate Simpson diversity index.

    D = 1 - sum(pi^2)

    Args:
        abundances: Array of abundance values (non-negative).

    Returns:
        Simpson diversity index. 0.0 for single-species samples.
    """
    a = abundances[abundances > 0]
    if len(a) <= 1:
        return 0.0
    total = a.sum()
    if total == 0:
        return 0.0
    props = a / total
    return float(1.0 - np.sum(props ** 2))


def chao1_estimator(abundances: np.ndarray) -> float:
    """Calculate Chao1 richness estimator.

    Chao1 = S_obs + (f1^2 / (2 * f2))

    where f1 = number of singletons, f2 = number of doubletons.
    For abundance data (non-integer), we treat observed species count
    as the base estimate. When f2=0, use Chao1 = S_obs + f1*(f1-1)/2.

    .. warning::

        Chao1 is designed for **integer count data** (raw read/contig counts).
        When applied to normalised abundance values (RPM, RPKM, TPM) the
        singleton/doubleton detection relies on rounding and the resulting
        richness estimate is only approximate.  Prefer raw counts whenever
        possible.

    Args:
        abundances: Array of abundance values.

    Returns:
        Chao1 richness estimate.
    """
    a = abundances[abundances > 0]
    s_obs = len(a)
    if s_obs == 0:
        return 0.0

    # For count data: singletons = species with count 1, doubletons = count 2
    # For RPM/abundance data: round to nearest integer for singleton/doubleton detection
    counts = np.round(a).astype(int)
    f1 = np.sum(counts == 1)
    f2 = np.sum(counts == 2)

    if f2 > 0:
        return float(s_obs + (f1 ** 2) / (2 * f2))
    elif f1 > 0:
        return float(s_obs + f1 * (f1 - 1) / 2)
    else:
        return float(s_obs)


def pielou_evenness(abundances: np.ndarray) -> float:
    """Calculate Pielou's evenness index.

    J = H' / ln(S)

    where H' is Shannon diversity and S is the number of observed species.

    Args:
        abundances: Array of abundance values.

    Returns:
        Pielou's evenness. 0.0 for single-species or empty samples.
    """
    a = abundances[abundances > 0]
    s = len(a)
    if s <= 1:
        return 0.0
    h = shannon_diversity(abundances)
    return float(h / np.log(s))


def compute_alpha_diversity(matrix: pd.DataFrame, sample_cols: list[str]) -> pd.DataFrame:
    """Compute alpha diversity metrics for each sample.

    Args:
        matrix: DataFrame with taxon rows and sample columns (RPM values).
        sample_cols: List of sample column names.

    Returns:
        DataFrame with columns matching ALPHA_COLUMNS.
    """
    _rpm_warned = False
    rows = []
    for sample in sample_cols:
        abundances = matrix[sample].values.astype(float)

        # Detect non-integer abundance values (likely RPM/RPKM) and warn once
        if not _rpm_warned:
            positives = abundances[abundances > 0]
            if len(positives) > 0 and any(not float(x).is_integer() for x in positives):
                logger.warning(
                    "Chao1 on non-integer data (likely RPM/RPKM). "
                    "Richness estimates are approximate."
                )
                _rpm_warned = True

        obs = int(np.sum(abundances > 0))
        h = shannon_diversity(abundances)
        d = simpson_diversity(abundances)
        c1 = chao1_estimator(abundances)
        j = pielou_evenness(abundances)
        rows.append({
            "sample": sample,
            "observed_species": obs,
            "shannon": round(h, 3),
            "simpson": round(d, 3),
            "chao1": round(c1, 1),
            "pielou_evenness": round(j, 3),
        })
    return pd.DataFrame(rows, columns=ALPHA_COLUMNS)


def compute_bray_curtis_matrix(
    matrix: pd.DataFrame, sample_cols: list[str]
) -> pd.DataFrame:
    """Compute Bray-Curtis distance matrix.

    BC(x, y) = 1 - 2 * sum(min(xi, yi)) / (sum(xi) + sum(yi))

    Args:
        matrix: DataFrame with taxon rows and sample columns.
        sample_cols: List of sample column names.

    Returns:
        Symmetric distance matrix as DataFrame.
    """
    n = len(sample_cols)
    if n == 0:
        return pd.DataFrame()
    dist_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(i + 1, n):
            x = matrix[sample_cols[i]].values.astype(float)
            y = matrix[sample_cols[j]].values.astype(float)
            # Handle edge case: both zero vectors
            sx, sy = x.sum(), y.sum()
            if sx + sy == 0:
                bc = 0.0
            else:
                bc = 1.0 - 2.0 * np.sum(np.minimum(x, y)) / (sx + sy)
            dist_matrix[i, j] = round(bc, 2)
            dist_matrix[j, i] = round(bc, 2)

    df = pd.DataFrame(dist_matrix, index=sample_cols, columns=sample_cols)
    return df


def compute_pcoa(dist_matrix: pd.DataFrame, n_components: int = 2) -> pd.DataFrame:
    """Compute Principal Coordinates Analysis (PCoA) from a distance matrix.

    Uses classical multidimensional scaling (Torgerson's method).

    Args:
        dist_matrix: Symmetric distance matrix.
        n_components: Number of principal coordinates to return.

    Returns:
        DataFrame with columns: sample, PC1, PC2, ...
    """
    samples = list(dist_matrix.index)
    n = len(samples)

    if n < 2:
        # Cannot do PCoA with less than 2 samples
        result = pd.DataFrame({"sample": samples})
        for i in range(1, n_components + 1):
            result[f"PC{i}"] = 0.0
        return result

    D = dist_matrix.values.astype(float)

    # Classical MDS (Torgerson's method)
    # 1. Square the distances
    D_sq = D ** 2

    # 2. Double-centering
    n = D_sq.shape[0]
    H = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * H @ D_sq @ H

    # 3. Eigendecomposition
    eigenvalues, eigenvectors = np.linalg.eigh(B)

    # Sort by descending eigenvalue
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # Take top n_components (clip negative eigenvalues to 0)
    k = min(n_components, len(eigenvalues))
    coords = np.zeros((len(samples), n_components))
    for i in range(k):
        if eigenvalues[i] > 0:
            coords[:, i] = eigenvectors[:, i] * np.sqrt(eigenvalues[i])

    result = pd.DataFrame({"sample": samples})
    for i in range(n_components):
        result[f"PC{i + 1}"] = np.round(coords[:, i], 6)

    return result


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    # Load matrix
    matrix = pd.read_csv(args.matrix, sep="\t")
    matrix.columns = matrix.columns.str.strip()

    # Identify sample columns (everything after taxon, taxid, rank)
    meta_cols = ["taxon", "taxid", "rank"]
    sample_cols = [c for c in matrix.columns if c not in meta_cols]

    if not sample_cols:
        print("WARNING: No sample columns found in matrix. Generating empty outputs.", file=sys.stderr)
        pd.DataFrame(columns=["sample", "observed_species", "shannon", "simpson", "chao1", "pielou_evenness"]).to_csv(args.out_alpha, sep="\t", index=False)
        pd.DataFrame().to_csv(args.out_beta, sep="\t", index=True)
        pd.DataFrame(columns=["sample", "PC1", "PC2"]).to_csv(args.out_pcoa, sep="\t", index=False)
        return 0

    # Ensure numeric values
    for col in sample_cols:
        matrix[col] = pd.to_numeric(matrix[col], errors="coerce").fillna(0.0)

    # Compute alpha diversity
    alpha = compute_alpha_diversity(matrix, sample_cols)

    # Compute beta diversity (Bray-Curtis)
    beta = compute_bray_curtis_matrix(matrix, sample_cols)

    # Compute PCoA
    pcoa = compute_pcoa(beta)

    # Write outputs
    alpha.to_csv(args.out_alpha, sep="\t", index=False)
    beta.to_csv(args.out_beta, sep="\t", index=True)
    pcoa.to_csv(args.out_pcoa, sep="\t", index=False)

    print(
        f"Alpha diversity: {len(alpha)} samples, "
        f"Beta diversity: {beta.shape[0]}x{beta.shape[1]}, "
        f"PCoA: {len(pcoa)} samples",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
