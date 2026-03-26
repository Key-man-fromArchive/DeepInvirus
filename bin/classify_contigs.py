#!/usr/bin/env python3
"""Backward-compatible entrypoint for DeepInvirus contig classification.

# @TASK T8.7 - Hybrid v1 evidence integration wrapper
# @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#25-stage-5-evidence-integration
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from evidence_integration import build_parser as build_v2_parser
from evidence_integration import get_kingdom, load_taxonomy_lineage
from evidence_integration import main as run_v2

KINGDOM_TAXIDS = {
    10239: "viral",
    2: "bacterial",
    2157: "archaeal",
    4751: "fungal",
    33090: "plant",
    33208: "animal",
    6960: "insect",
}

NON_VIRAL_KINGDOMS = frozenset(
    {"bacterial", "archaeal", "fungal", "plant", "animal", "insect"}
)


def legacy_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--exclusion", type=Path)
    parser.add_argument("--detection", type=Path)
    parser.add_argument("--taxonomy-nodes", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--viral-score-threshold", type=float, default=0.7)
    return parser


def parse_args(argv: list[str] | None = None) -> tuple[str, argparse.Namespace]:
    argv = list(sys.argv[1:] if argv is None else argv)
    if any(flag in argv for flag in ["--tier1-aa", "--tier2-aa", "--tier3-nt", "--tier4-nt", "--genomad"]):
        return "v2", build_v2_parser().parse_args(argv)
    parsed, _ = legacy_parser().parse_known_args(argv)
    if parsed.exclusion and parsed.detection and parsed.taxonomy_nodes and parsed.output:
        return "legacy", parsed
    return "v2", build_v2_parser().parse_args(argv)


def legacy_to_v2(parsed: argparse.Namespace) -> list[str]:
    null_file = Path("/dev/null")
    return [
        "--contigs",
        str(null_file),
        "--tier1-aa",
        str(parsed.detection),
        "--tier2-aa",
        str(parsed.exclusion),
        "--tier3-nt",
        str(null_file),
        "--tier4-nt",
        str(null_file),
        "--genomad",
        str(null_file),
        "--kraken2-report",
        str(null_file),
        "--taxonomy-nodes",
        str(parsed.taxonomy_nodes),
        "--output",
        str(parsed.output),
    ]


def _load_exclusion(exclusion_path: Path) -> pd.DataFrame:
    if not exclusion_path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(
            exclusion_path,
            sep="\t",
            header=None,
            names=[
                "seq_id",
                "sseqid",
                "pident",
                "length",
                "mismatch",
                "gapopen",
                "qstart",
                "qend",
                "sstart",
                "send",
                "evalue",
                "bitscore",
                "staxids",
            ],
        )
        if df.empty:
            return df
        df["staxids"] = df["staxids"].astype(str).str.split(";").str[0]
        df["staxids"] = pd.to_numeric(df["staxids"], errors="coerce").fillna(0).astype(int)
        df = df.sort_values("bitscore", ascending=False).drop_duplicates("seq_id", keep="first")
        return df
    except Exception:
        return pd.DataFrame()


def _load_detection(detection_path: Path) -> pd.DataFrame:
    if not detection_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(detection_path, sep="\t")
    except Exception:
        return pd.DataFrame()


def _decide(
    viral_score: float,
    exc_kingdom: str,
    exc_bitscore: float,
    viral_score_threshold: float,
) -> tuple[str, str]:
    if viral_score >= viral_score_threshold:
        if exc_kingdom == "viral" or exc_kingdom == "unknown":
            return "viral", "genomad_high"
        if exc_bitscore > 200 and exc_kingdom in NON_VIRAL_KINGDOMS:
            return "review", f"genomad_high_but_{exc_kingdom}_hit"
        return "viral", "genomad_high_weak_exclusion"
    if viral_score > 0:
        if exc_kingdom in NON_VIRAL_KINGDOMS:
            return exc_kingdom, f"exclusion_{exc_kingdom}"
        return "viral_low", "genomad_low_no_exclusion"
    if exc_kingdom in NON_VIRAL_KINGDOMS:
        return exc_kingdom, f"exclusion_only_{exc_kingdom}"
    return "unknown", "no_evidence"


def classify_contigs(
    exclusion_path: Path,
    detection_path: Path,
    nodes_path: Path,
    output_path: Path,
    viral_score_threshold: float = 0.7,
) -> pd.DataFrame:
    exclusion = _load_exclusion(exclusion_path)
    detection = _load_detection(detection_path)
    parent_map = load_taxonomy_lineage(nodes_path)

    if not exclusion.empty:
        exclusion["kingdom"] = exclusion["staxids"].apply(lambda t: get_kingdom(t, parent_map))

    all_contigs: set[str] = set()
    if not detection.empty and "seq_id" in detection.columns:
        all_contigs.update(detection["seq_id"].unique())
    if not exclusion.empty:
        all_contigs.update(exclusion["seq_id"].unique())

    results: list[dict[str, object]] = []
    for seq_id in sorted(all_contigs):
        det_row = detection[detection["seq_id"] == seq_id] if not detection.empty else pd.DataFrame()
        viral_score = (
            float(det_row["detection_score"].iloc[0])
            if len(det_row) > 0 and "detection_score" in det_row.columns
            else 0.0
        )
        exc_row = exclusion[exclusion["seq_id"] == seq_id] if not exclusion.empty else pd.DataFrame()
        exc_kingdom = exc_row["kingdom"].iloc[0] if len(exc_row) > 0 else "unknown"
        exc_evalue = float(exc_row["evalue"].iloc[0]) if len(exc_row) > 0 else 999.0
        exc_bitscore = float(exc_row["bitscore"].iloc[0]) if len(exc_row) > 0 else 0.0
        classification, evidence = _decide(
            viral_score=viral_score,
            exc_kingdom=exc_kingdom,
            exc_bitscore=exc_bitscore,
            viral_score_threshold=viral_score_threshold,
        )
        results.append(
            {
                "seq_id": seq_id,
                "classification": classification,
                "evidence": evidence,
                "viral_score": round(viral_score, 4),
                "exclusion_evalue": exc_evalue,
                "exclusion_kingdom": exc_kingdom,
            }
        )

    result_df = pd.DataFrame(results)
    result_df.to_csv(output_path, sep="\t", index=False)
    if not result_df.empty:
        summary = result_df["classification"].value_counts()
        print("Classification summary:", file=sys.stderr)
        for cls, count in summary.items():
            print(f"  {cls}: {count}", file=sys.stderr)
    return result_df


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    mode, parsed = parse_args(argv)
    if mode == "legacy":
        classify_contigs(
            exclusion_path=parsed.exclusion,
            detection_path=parsed.detection,
            nodes_path=parsed.taxonomy_nodes,
            output_path=parsed.output,
            viral_score_threshold=parsed.viral_score_threshold,
        )
        return 0
    return run_v2(argv)


if __name__ == "__main__":
    raise SystemExit(main())
