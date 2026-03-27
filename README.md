# `[DeepInvirus Logo Placeholder]`

# DeepInvirus

[![Nextflow](https://img.shields.io/badge/Nextflow-DSL2-23aa62.svg)](https://www.nextflow.io/)
[![Docker](https://img.shields.io/badge/Container-Docker-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)

DeepInvirus is a **Nextflow DSL2 viral metagenomics pipeline** for end-to-end assembly-based virome analysis, from paired-end FASTQ files to a unified viral bigtable, an interactive HTML dashboard, and a publication-oriented Word report.

It implements a **Hecatomb-inspired 4-tier iterative classification strategy** and follows an **"annotate everything, remove nothing"** philosophy: contigs are not hard-filtered away simply because evidence is weak or conflicting. Instead, all evidence is retained and integrated into an interpretable classification framework.

## Overview

DeepInvirus is designed around two principles:

- **Sensitivity first**: all host-depleted reads are retained for co-assembly, without Kraken2-based pre-filtering.
- **Evidence integration instead of binary filtering**: ML detection, protein homology, nucleotide homology, exclusion evidence, taxonomy, and coverage are merged into one explainable result table.

The current implementation includes:

- Co-assembly of all host-depleted reads with **MEGAHIT** or **metaSPAdes**
- Post-assembly deduplication/clustering with **MMseqs2**
- Viral detection with **geNomad** plus protein homology search
- **4-tier iterative classification**: `AA1 -> AA2 -> NT1 -> NT2`
- Taxonomic assignment with a **GenBank viral NT primary database** and a **RefSeq-derived verified tag**
- Per-sample quantification with **CoverM** and per-base depth profiling with **samtools depth**
- Automated downstream deliverables: `bigtable.tsv`, `dashboard.html`, `report.docx`

## Key Features

- **Co-assembly + post-assembly clustering**: pooled assembly followed by redundancy reduction at the contig level
- **geNomad ML viral detection** on the full contig set before any evidence-based filtering
- **4-tier evidence integration** combining viral-first and exclusion-first searches
- **GenBank viral NT primary reference** for broad coverage, with `refseq_verified` tagging from accession prefixes
- **Per-base depth profiles** from `samtools depth` for contig-level depth visualization
- **Interactive dashboard** with taxonomy exploration and multi-sample comparison views, including Sankey, Sunburst, and Treemap-style hierarchy views
- **Publication-quality report** in Word format, generated directly from pipeline outputs
- **Independent read-based profiling section** with Kraken2, Bracken, and Krona when a Kraken2 database is provided

## Quick Start

### Requirements

- Nextflow `>=23.04`
- Docker or Singularity/Apptainer
- A prepared DeepInvirus database directory

### Run

```bash
nextflow run main.nf \
  --reads 'data/*_R{1,2}.fastq.gz' \
  --host none \
  --db_dir /path/to/DeepInvirus_DB \
  -profile docker
```

### Minimal output

- `results/dashboard.html`
- `results/report.docx`
- `results/taxonomy/bigtable.tsv`

## Pipeline Architecture

```text
Reads -> QC -> Host Removal -> Co-assembly -> Clustering
                                 |
                                 v
                 Detection (geNomad + Diamond)
                                 |
                                 v
                 4-Tier Iterative Classification
                 (AA1 -> AA2 -> NT1 -> NT2 + Evidence Integration)
                                 |
                                 v
                 Taxonomy (MMseqs2 GenBank + TaxonKit)
                                 |
                                 v
                 Per-sample Coverage (CoverM + samtools depth)
                                 |
                                 v
                 Bigtable + Dashboard + Report
```

### Workflow summary

1. Reads are quality-trimmed with `bbduk` or `fastp`.
2. Host reads are removed with `minimap2` unless `--host none` is used.
3. All host-depleted reads are pooled for **co-assembly**.
4. Assembled contigs are clustered to reduce redundancy.
5. Viral candidates are detected on the full contig set using **geNomad** and protein homology search.
6. Iterative classification proceeds through:
   - `AA1`: viral protein search
   - `AA2`: all-kingdom protein verification against UniRef50
   - `NT1`: viral nucleotide search
   - `NT2`: polymicrobial nucleotide exclusion search
7. Contigs are assigned taxonomy with **MMseqs2** and lineage is reformatted by **TaxonKit**.
8. Each sample is remapped to the co-assembly with **CoverM**, and per-base depth is generated with **samtools depth**.
9. Results are merged into `bigtable.tsv`, then rendered into the dashboard and report.

## Database Setup

DeepInvirus Hybrid v1 uses **10 logical databases/resources**. In practice, `bin/install_databases.py` installs the core component groups, and the full production DB layout includes additional tier-specific references documented in `docs/DATABASE_GUIDE.md`.

### Database inventory

| # | Database / Resource | Purpose | Approx. size |
|---|---|---|---:|
| 1 | UniRef50 Diamond | Tier 2 AA all-kingdom verification | 24 GB |
| 2 | Viral Protein Diamond | Tier 1 AA viral-first search | 225 MB |
| 3 | UniRef90 viral Diamond | supplemental viral protein resource | ~400 MB |
| 4 | GenBank Viral NT BLAST | Tier 3 NT viral-first search | 9.3 GB |
| 5 | Kraken2 `core_nt` | independent read-level profiling | 307 GB |
| 6 | Polymicrobial NT BLAST | Tier 4 NT exclusion search | 54 GB |
| 7 | geNomad DB | ML viral detection | 1.4 GB |
| 8 | CheckV DB | viral genome quality assessment | 6.4 GB |
| 9 | Taxonomy + ICTV VMR | TaxonKit lineage + ICTV metadata | 583 MB |
| 10 | Host genomes | host depletion with minimap2 | 4.9 GB |

### Installer usage

```bash
python bin/install_databases.py \
  --db-dir /path/to/DeepInvirus_DB \
  --components all \
  --host human \
  --threads 8
```

Preview only:

```bash
python bin/install_databases.py \
  --db-dir /path/to/DeepInvirus_DB \
  --components all \
  --dry-run
```

### Installer component groups

The installer accepts these component names:

- `all`
- `protein`
- `nucleotide`
- `genomad`
- `taxonomy`
- `host`
- `exclusion`

### Expected database root layout

```text
DeepInvirus_DB/
├── genbank_viral_nt/
├── genbank_viral_protein/
├── genomad_db/
├── kraken2_core_nt/
├── polymicrobial_nt/
├── taxonomy/
├── uniref50/
├── exclusion_db/
└── host_genomes/
```

### Notes

- `--db_dir` is the primary database root flag. The pipeline auto-detects sub-databases from that directory.
- Individual overrides are available for `--kraken2_db`, `--uniref50_db`, `--viral_nt_db`, `--polymicrobial_nt_db`, `--checkv_db`, and `--exclusion_db`.
- If a tier-specific database is missing, the corresponding optional tier is disabled rather than crashing in some cases.

## Output Files

### Primary deliverables

| File | Description |
|---|---|
| `taxonomy/bigtable.tsv` | Master integrated results table; one row per `seq_id x sample` |
| `dashboard.html` | Standalone interactive HTML dashboard |
| `report.docx` | Automated Word report for interpretation and sharing |

### Other important outputs

| Path | Description |
|---|---|
| `assembly/` | co-assembly FASTA and assembly statistics |
| `classification/` | tier-specific iterative classification outputs |
| `coverage/` | per-sample coverage TSVs and per-base depth files |
| `detection/` | geNomad, Diamond, optional CheckV outputs |
| `diversity/` | alpha diversity, beta diversity, and PCoA tables |
| `kraken2/` | optional Kraken2, Bracken, and Krona outputs |
| `qc/` | trimming, host removal, FastQC, and MultiQC outputs |
| `pipeline_info/` | Nextflow report, trace, DAG, timeline, run log |

### `bigtable.tsv` columns

The report generator currently documents the merged bigtable with these core columns. The merged table also carries implementation-level fields such as `taxonomy`, `target`, `pident`, `taxname`, `refseq_verified`, and sample `group`.

| Column | Description |
|---|---|
| `seq_id` | contig identifier from co-assembly |
| `sample` | sample name |
| `length` | contig length in bp |
| `detection_method` | `genomad`, `diamond`, or `both` |
| `detection_score` | normalized detection confidence |
| `family` | viral family label if available |
| `coverage` | mean read depth from CoverM |
| `breadth` | percent of bases covered |
| `detection_confidence` | `high`, `medium`, or `low` from depth/breadth thresholds |
| `rpm` | coverage-normalized relative abundance |
| `count` | mapped read count |
| `taxid` | NCBI taxonomy ID |
| `domain` | normalized domain label |
| `phylum` | taxonomic phylum |
| `class` | taxonomic class |
| `order` | taxonomic order |
| `genus` | taxonomic genus |
| `species` | taxonomic species |
| `evidence_classification` | final 4-tier class |
| `evidence_score` | classification support score |
| `evidence_support_tier` | strongest contributing tier such as `aa1`, `nt2`, or `genomad_only` |
| `ictv_classification` | ICTV annotation |
| `baltimore_group` | Baltimore genome class |

### `dashboard.html`

The standalone dashboard is generated from the merged bigtable and associated summary tables. Current capabilities include:

- Overview summary cards
- Taxonomy Sankey view
- Sunburst and hierarchical taxonomy exploration
- Searchable contig/result tables
- Per-sample comparison views
- Embedded report figures
- Coverage views from per-sample coverage tables
- Per-base depth profiles from `*_depth.tsv.gz`

### `report.docx`

The Word report is generated automatically from pipeline outputs and includes:

- Executive summary
- QC and preprocessing summary
- Assembly summary
- Viral detection and evidence integration summary
- Taxonomy overview
- Diversity and sample comparison figures
- Top strong viral contigs
- Output file dictionary, including a `bigtable.tsv` column dictionary

## Parameters

These are the actual user-facing parameters defined in `nextflow.config` and `main.nf`.

### Core parameters

| Parameter | Default | Description |
|---|---|---|
| `--reads` | `null` | paired-end FASTQ glob or directory path |
| `--host` | `human` in `nextflow.config`, `none` in `main.nf` fallback | comma-separated host genome nicknames or `none` |
| `--outdir` | timestamped results directory in `nextflow.config` | output directory |
| `--db_dir` | `null` | DeepInvirus database root directory |
| `--trimmer` | `bbduk` | trimming/QC tool: `bbduk` or `fastp` |
| `--assembler` | `megahit` | assembler: `megahit` or `metaspades` |
| `--search` | `sensitive` | Diamond search mode: `fast` or `sensitive` |
| `--skip_ml` | `false` | skip geNomad ML detection |
| `--help` | `false` | print usage and exit |

### Detection and classification parameters

| Parameter | Default | Description |
|---|---|---|
| `--min_contig_len` | `500` | minimum contig length retained from assembly |
| `--min_virus_score` | `0.7` | geNomad viral score threshold |
| `--min_bitscore` | `50` | minimum bitscore filter |
| `--checkv_db` | `null` | optional CheckV DB path |
| `--exclusion_db` | `null` | optional exclusion Diamond DB path |
| `--kraken2_db` | `null` | optional Kraken2 DB path |
| `--uniref50_db` | `null` | optional UniRef50 Tier 2 DB path |
| `--viral_nt_db` | `null` | optional viral NT Tier 3 BLAST prefix |
| `--polymicrobial_nt_db` | `null` | optional polymicrobial NT Tier 4 BLAST prefix |
| `--kraken2_confidence` | `0.0` | Kraken2 confidence threshold; `0.0` preserves annotate-everything behavior |
| `--bracken_read_len` | `150` | Bracken read length |
| `--bracken_level` | `S` | Bracken taxonomy level |
| `--bracken_threshold` | `0` | Bracken minimum read threshold |

### Runtime and resource parameters

| Parameter | Default | Description |
|---|---|---|
| `--fastp_args` | `''` | extra arguments passed to `fastp` |
| `--max_cpus` | `32` | max CPUs per process |
| `--max_memory` | `256.GB` | max memory per process |
| `--max_time` | `24.h` | max wall time per process |
| `--use_ramdisk` | `false` | use RAM disk for work directory staging |
| `--ramdisk_path` | `/dev/shm/deepinvirus_work` | RAM disk path |
| `--ramdisk_size` | `0` | RAM disk size in GB, `0` means auto |
| `--work_dir` | `null` | custom work directory |

## Evidence Classification Rules

DeepInvirus integrates geNomad and 4-tier homology evidence into five final labels.

### Tier definitions

- `AA1`: viral-first amino acid search
- `AA2`: all-kingdom amino acid verification
- `NT1`: viral-first nucleotide search
- `NT2`: all-kingdom nucleotide verification

### Rule summary

| Final class | Practical rule |
|---|---|
| `strong_viral` | `geNomad >= 0.7` plus viral-first support (`AA1` or `NT1`), without stronger cellular exclusion evidence |
| `novel_viral_candidate` | `geNomad >= 0.7` with no cellular evidence, but lacking viral-first homology support strong enough for `strong_viral` |
| `ambiguous` | mixed or incomplete evidence, such as viral-first support plus cellular support, or weak partial viral signal |
| `cellular` | strong or consistent non-viral evidence from `AA2` and/or `NT2`, especially when exclusion hits outscore viral-first hits |
| `unknown` | no meaningful ML or homology evidence |

### Current implementation thresholds

From `bin/evidence_integration.py`:

- Viral-first evidence is present when `aa1_bitscore > 0` or `nt1_bitscore > 0`
- Strong viral homology is defined as `aa1_bitscore >= 150` or `nt1_bitscore >= 200`
- Strong cellular evidence is defined when:
  - `AA2` is non-viral and `aa2_bitscore >= max(200, aa1_bitscore + 20)`, or
  - `NT2` is non-viral and `nt2_bitscore >= max(200, nt1_bitscore + 20)`
- `support_tier` is recorded as the best contributing tier: `aa1`, `nt1`, `aa2`, `nt2`, `genomad_only`, or `none`

This rule set is intended to preserve weak or conflicting contigs for review rather than discarding them.

## Running Profiles

```bash
nextflow run main.nf -profile docker
nextflow run main.nf -profile singularity
nextflow run main.nf -profile test,docker
```

## Scientific Notes

- The assembly-based virome section and the Kraken2/Bracken profiling section are intentionally separate.
- Kraken2 is used as an **independent read-level profiling module**, not as an upstream read filter for assembly.
- Taxonomic assignment in the merged viral table is currently driven by **MMseqs2 + TaxonKit**, while the evidence class comes from the iterative rule engine.
- `refseq_verified` is inferred from accession prefixes such as `NC_`, `NZ_`, `NW_`, `AC_`, and `NG_`.

## Citation

Citation placeholder:

```text
DeepInvirus Team. DeepInvirus: a Nextflow DSL2 pipeline for assembly-based viral metagenomics with iterative evidence integration. Placeholder citation.
```

If you use DeepInvirus, also cite the underlying methods where appropriate, including Nextflow, geNomad, DIAMOND, MMseqs2, TaxonKit, CoverM, samtools, CheckV, Kraken2, Bracken, and relevant reference databases.

## License

DeepInvirus is distributed under the **MIT License**.
