#!/usr/bin/env python3
"""Integrate 4-tier viral evidence into a per-contig classification table.

# @TASK T8.7 - Hybrid v1 evidence integration
# @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#25-stage-5-evidence-integration
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

KINGDOM_TAXIDS: dict[int, str] = {
    0: "unclassified",
    2: "bacterial",
    2157: "archaeal",
    4751: "fungal",
    10239: "viral",
    33090: "plant",
    33208: "animal",
    33634: "protozoal",
}

NON_VIRAL_KINGDOMS = frozenset(
    {"bacterial", "archaeal", "fungal", "plant", "animal", "protozoal"}
)

BLAST_COLUMNS = [
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
]


def load_taxonomy_lineage(nodes_path: Path) -> dict[int, int]:
    parent_map: dict[int, int] = {}
    if not nodes_path.exists() or nodes_path.is_dir():
        return parent_map
    with nodes_path.open() as handle:
        for line in handle:
            parts = line.split("|")
            if len(parts) >= 2:
                try:
                    child = int(parts[0].strip())
                    parent = int(parts[1].strip())
                except ValueError:
                    continue
                parent_map[child] = parent
    return parent_map


def get_kingdom(taxid: int, parent_map: dict[int, int]) -> str:
    visited: set[int] = set()
    current = taxid
    while current not in visited:
        if current in KINGDOM_TAXIDS:
            return KINGDOM_TAXIDS[current]
        visited.add(current)
        current = parent_map.get(current, 0)
        if current == 0:
            break
    return "unknown"


def parse_fasta_lengths(contigs_path: Path) -> pd.DataFrame:
    if not contigs_path.exists() or contigs_path.is_dir():
        return pd.DataFrame(columns=["seq_id", "length"])
    lengths: list[dict[str, int | str]] = []
    current_id: str | None = None
    current_len = 0
    with contigs_path.open() as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_id is not None:
                    lengths.append({"seq_id": current_id, "length": current_len})
                current_id = line[1:].split()[0]
                current_len = 0
            else:
                current_len += len(line)
    if current_id is not None:
        lengths.append({"seq_id": current_id, "length": current_len})
    return pd.DataFrame(lengths)


def load_genomad(genomad_path: Path) -> pd.DataFrame:
    if not genomad_path.exists() or genomad_path.is_dir() or genomad_path.stat().st_size == 0:
        return pd.DataFrame(columns=["seq_id", "genomad_virus_score"])
    df = pd.read_csv(genomad_path, sep="\t")
    rename = {
        "seq_name": "seq_id",
        "virus_score": "genomad_virus_score",
        "plasmid_score": "genomad_plasmid_score",
        "provirus": "genomad_provirus",
        "n_genes": "n_orfs",
        "taxonomy": "genomad_taxonomy",
    }
    df = df.rename(columns=rename)
    for col in [
        "seq_id",
        "genomad_virus_score",
        "genomad_plasmid_score",
        "genomad_provirus",
        "n_orfs",
        "genomad_taxonomy",
    ]:
        if col not in df.columns:
            df[col] = pd.NA
    return df[
        [
            "seq_id",
            "genomad_virus_score",
            "genomad_plasmid_score",
            "genomad_provirus",
            "n_orfs",
            "genomad_taxonomy",
        ]
    ]


def empty_hits_frame(prefix: str, columns: list[str]) -> pd.DataFrame:
    empty = pd.DataFrame(columns=["seq_id", *columns])
    if prefix in {"aa1", "nt1"}:
        empty[f"{prefix}_taxonomy"] = pd.NA
    else:
        empty[f"{prefix}_kingdom"] = pd.NA
    return empty


def load_hits(path: Path, prefix: str, parent_map: dict[int, int], default_taxonomy: str) -> pd.DataFrame:
    columns = [
        f"{prefix}_hit",
        f"{prefix}_pident",
        f"{prefix}_evalue",
        f"{prefix}_bitscore",
        f"{prefix}_alnlen",
        f"{prefix}_taxid",
    ]
    empty = empty_hits_frame(prefix, columns)
    if not path.exists() or path.is_dir() or path.stat().st_size == 0:
        return empty

    first_data_line: str | None = None
    with path.open() as handle:
        for raw in handle:
            line = raw.strip()
            if line and not line.startswith("#"):
                first_data_line = line
                break
    if first_data_line is None:
        return empty

    observed_cols = len(first_data_line.split("\t"))
    if observed_cols < 12:
        return empty

    read_cols = min(observed_cols, len(BLAST_COLUMNS))
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=BLAST_COLUMNS[:read_cols],
        usecols=range(read_cols),
        comment="#",
    )
    if df.empty:
        return empty
    if "staxids" not in df.columns:
        df["staxids"] = "0"

    df["staxids"] = (
        df["staxids"].astype(str).str.split(";").str[0].replace({"nan": "0", "": "0"})
    )
    df["staxids"] = pd.to_numeric(df["staxids"], errors="coerce").fillna(0).astype(int)
    df["bitscore"] = pd.to_numeric(df["bitscore"], errors="coerce").fillna(0.0)
    df["evalue"] = pd.to_numeric(df["evalue"], errors="coerce").fillna(1.0)
    df["pident"] = pd.to_numeric(df["pident"], errors="coerce")
    df["length"] = pd.to_numeric(df["length"], errors="coerce")
    df = df.sort_values(["seq_id", "bitscore", "evalue"], ascending=[True, False, True])
    df = df.drop_duplicates("seq_id", keep="first")

    out = pd.DataFrame(
        {
            "seq_id": df["seq_id"],
            f"{prefix}_hit": df["sseqid"],
            f"{prefix}_pident": df["pident"],
            f"{prefix}_evalue": df["evalue"],
            f"{prefix}_bitscore": df["bitscore"],
            f"{prefix}_alnlen": df["length"],
            f"{prefix}_taxid": df["staxids"],
        }
    )
    if prefix in {"aa1", "nt1"}:
        def _classify_taxid(taxid):
            tid = int(taxid)
            if tid == 0:
                return "viral_db_hit"
            kingdom = get_kingdom(tid, parent_map)
            return default_taxonomy if kingdom == "viral" else "non_viral_hit"
        out[f"{prefix}_taxonomy"] = df["staxids"].map(_classify_taxid)
    else:
        out[f"{prefix}_kingdom"] = df["staxids"].map(lambda taxid: get_kingdom(int(taxid), parent_map))
    return out


def choose_classification(row: pd.Series) -> tuple[str, str, float]:
    genomad = to_float(row.get("genomad_virus_score"))
    aa1_bitscore = to_float(row.get("aa1_bitscore"))
    nt1_bitscore = to_float(row.get("nt1_bitscore"))
    aa2_bitscore = to_float(row.get("aa2_bitscore"))
    nt2_bitscore = to_float(row.get("nt2_bitscore"))
    aa2_kingdom = normalize_text(row.get("aa2_kingdom"))
    nt2_kingdom = normalize_text(row.get("nt2_kingdom"))

    viral_first = aa1_bitscore > 0 or nt1_bitscore > 0
    strong_viral = (aa1_bitscore >= 150) or (nt1_bitscore >= 200)
    strong_cellular = (
        (aa2_kingdom in NON_VIRAL_KINGDOMS and aa2_bitscore >= max(200.0, aa1_bitscore + 20.0))
        or (nt2_kingdom in NON_VIRAL_KINGDOMS and nt2_bitscore >= max(200.0, nt1_bitscore + 20.0))
    )
    any_cellular = (
        aa2_kingdom in NON_VIRAL_KINGDOMS or nt2_kingdom in NON_VIRAL_KINGDOMS
    )

    if strong_cellular and not (genomad >= 0.7 and viral_first):
        return "cellular", support_tier(row, prefer_cellular=True), 0.9
    if genomad >= 0.7 and viral_first and not strong_cellular:
        score = max(genomad, 0.9 if strong_viral else 0.75)
        return "strong_viral", support_tier(row), min(score, 0.99)
    if genomad >= 0.7 and not any_cellular:
        return "novel_viral_candidate", "genomad_only", min(max(genomad, 0.75), 0.95)
    if viral_first and any_cellular:
        return "ambiguous", support_tier(row), 0.5
    if strong_cellular or any_cellular:
        return "cellular", support_tier(row, prefer_cellular=True), 0.8 if strong_cellular else 0.65
    if genomad > 0 or viral_first:
        return "ambiguous", support_tier(row), 0.4
    return "unknown", "none", 0.0


def support_tier(row: pd.Series, prefer_cellular: bool = False) -> str:
    if prefer_cellular:
        if to_float(row.get("nt2_bitscore")) > 0:
            return "nt2"
        if to_float(row.get("aa2_bitscore")) > 0:
            return "aa2"
    if to_float(row.get("aa1_bitscore")) > 0:
        return "aa1"
    if to_float(row.get("nt1_bitscore")) > 0:
        return "nt1"
    if to_float(row.get("aa2_bitscore")) > 0:
        return "aa2"
    if to_float(row.get("nt2_bitscore")) > 0:
        return "nt2"
    if to_float(row.get("genomad_virus_score")) > 0:
        return "genomad_only"
    return "none"


def build_evidence_chain(row: pd.Series) -> str:
    parts = [
        f"geNomad={fmt_num(row.get('genomad_virus_score'))}",
        f"AA1={describe_hit(row, 'aa1', taxonomy_field='aa1_taxonomy')}",
        f"AA2={describe_hit(row, 'aa2', taxonomy_field='aa2_kingdom')}",
        f"NT1={describe_hit(row, 'nt1', taxonomy_field='nt1_taxonomy')}",
        f"NT2={describe_hit(row, 'nt2', taxonomy_field='nt2_kingdom')}",
        f"final={row['classification']}",
    ]
    return "; ".join(parts)


def describe_hit(row: pd.Series, prefix: str, taxonomy_field: str) -> str:
    hit = normalize_text(row.get(f"{prefix}_hit"), default=".")
    if hit == ".":
        return "no_hit"
    return (
        f"{hit} "
        f"(pident {fmt_num(row.get(f'{prefix}_pident'))}, "
        f"aln {fmt_num(row.get(f'{prefix}_alnlen'))}, "
        f"{normalize_text(row.get(taxonomy_field), default='unknown')})"
    )


def fmt_num(value: object) -> str:
    if pd.isna(value):
        return "NA"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def normalize_text(value: object, default: str = "unknown") -> str:
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    return text if text else default


def to_float(value: object) -> float:
    try:
        if pd.isna(value):
            return 0.0
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def integrate_evidence(args: argparse.Namespace) -> pd.DataFrame:
    parent_map = load_taxonomy_lineage(args.taxonomy_nodes)
    contigs = parse_fasta_lengths(args.contigs)
    genomad = load_genomad(args.genomad)
    tier1 = load_hits(args.tier1_aa, "aa1", parent_map, "Viruses")
    tier2 = load_hits(args.tier2_aa, "aa2", parent_map, "all_kingdoms")
    tier3 = load_hits(args.tier3_nt, "nt1", parent_map, "Viruses")
    tier4 = load_hits(args.tier4_nt, "nt2", parent_map, "all_kingdoms")

    frames = [contigs, genomad, tier1, tier2, tier3, tier4]
    merged = None
    for frame in frames:
        merged = frame if merged is None else merged.merge(frame, on="seq_id", how="outer")
    assert merged is not None

    defaults: dict[str, object] = {
        "length": pd.NA,
        "n_orfs": pd.NA,
        "genomad_virus_score": 0.0,
        "genomad_plasmid_score": pd.NA,
        "genomad_provirus": pd.NA,
        "aa1_hit": pd.NA,
        "aa1_pident": pd.NA,
        "aa1_evalue": pd.NA,
        "aa1_bitscore": 0.0,
        "aa1_alnlen": pd.NA,
        "aa1_taxid": pd.NA,
        "aa1_taxonomy": pd.NA,
        "aa2_hit": pd.NA,
        "aa2_pident": pd.NA,
        "aa2_evalue": pd.NA,
        "aa2_bitscore": 0.0,
        "aa2_alnlen": pd.NA,
        "aa2_taxid": pd.NA,
        "aa2_kingdom": pd.NA,
        "nt1_hit": pd.NA,
        "nt1_pident": pd.NA,
        "nt1_evalue": pd.NA,
        "nt1_bitscore": 0.0,
        "nt1_alnlen": pd.NA,
        "nt1_taxid": pd.NA,
        "nt1_taxonomy": pd.NA,
        "nt2_hit": pd.NA,
        "nt2_pident": pd.NA,
        "nt2_evalue": pd.NA,
        "nt2_bitscore": 0.0,
        "nt2_alnlen": pd.NA,
        "nt2_taxid": pd.NA,
        "nt2_kingdom": pd.NA,
    }
    for col, default in defaults.items():
        if col not in merged.columns:
            merged[col] = default
        merged[col] = merged[col].fillna(default)

    class_calls = merged.apply(choose_classification, axis=1, result_type="expand")
    class_calls.columns = ["classification", "best_support_tier", "classification_score"]
    merged = pd.concat([merged, class_calls], axis=1)
    merged["evidence_chain"] = merged.apply(build_evidence_chain, axis=1)
    return merged.sort_values("seq_id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Integrate DeepInvirus Hybrid v1 evidence tiers.")
    parser.add_argument("--contigs", type=Path, required=True, help="Contig FASTA used for evidence integration.")
    parser.add_argument("--tier1-aa", type=Path, required=True, help="Tier 1 viral protein hits TSV.")
    parser.add_argument("--tier2-aa", type=Path, required=True, help="Tier 2 UniRef50 hits TSV.")
    parser.add_argument("--tier3-nt", type=Path, required=True, help="Tier 3 viral nucleotide hits TSV.")
    parser.add_argument("--tier4-nt", type=Path, required=True, help="Tier 4 polymicrobial nucleotide hits TSV.")
    parser.add_argument("--genomad", type=Path, required=True, help="geNomad summary TSV.")
    parser.add_argument("--taxonomy-nodes", type=Path, required=True, help="NCBI nodes.dmp file.")
    parser.add_argument("--output", type=Path, required=True, help="Output classified contigs TSV.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = integrate_evidence(args)
    result.to_csv(args.output, sep="\t", index=False)

    if not result.empty:
        summary = result["classification"].value_counts()
        print("Evidence integration summary:", file=sys.stderr)
        for label, count in summary.items():
            print(f"  {label}: {count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
