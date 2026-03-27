# DeepInvirus

[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)](#)
[![Nextflow](https://img.shields.io/badge/Nextflow-DSL2-23aa62.svg)](https://www.nextflow.io/)
[![Docker](https://img.shields.io/badge/Container-Docker-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)

DeepInvirus is a Nextflow DSL2 pipeline for assembly-based viral metagenomics. It takes paired-end FASTQ files through QC, host depletion, co-assembly, post-assembly clustering, viral detection, iterative evidence integration, taxonomy assignment, coverage quantification, and final reporting.

Version `1.1.0` introduces a broader viral nucleotide search space and a stronger reporting workflow. The primary taxonomy/search reference is now the GenBank viral NT collection (~740K sequences) rather than the smaller RefSeq viral NT set, and downstream outputs were expanded to better support manual review, dashboard exploration, and manuscript preparation.

## Overview

DeepInvirus follows two design principles:

- Sensitivity first: host-depleted reads are retained for pooled co-assembly rather than pre-filtered away.
- Explainable evidence integration: ML detection, amino-acid evidence, nucleotide evidence, taxonomy, and coverage are merged into an interpretable final table instead of hard-discarding uncertain contigs.

## Features

- Co-assembly with `MEGAHIT` or `metaSPAdes`
- Post-assembly clustering with `MMseqs2 easy-cluster` at `95%` identity and `98%` coverage
- geNomad ML detection plus DIAMOND protein homology search with `--very-sensitive`
- Four-tier iterative evidence framework: `AA1 -> AA2 -> NT1 -> NT2`
- GenBank viral NT as the primary viral nucleotide reference, with `refseq_verified` carried as a secondary confidence tag
- Per-sample quantification with true contig length from CoverM and per-base depth profiling from `samtools depth`
- Interactive dashboard with Plotly treemap/sunburst auto-coloring, natural-flow Sankey layout, paginated search, grouped headers, and optional hiding of unclassified taxa
- Figure overlay viewer plus contig modal views for per-base depth inspection
- Publication-ready automated `materials_and_methods.txt` and `report.docx`

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
  --search very-sensitive \
  -profile docker
```

### Minimal outputs

- `results/taxonomy/bigtable.tsv`
- `results/dashboard.html`
- `results/report.docx`

## Pipeline Architecture

```text
Reads
  -> QC / trimming
  -> Host removal
  -> Co-assembly
  -> Post-assembly clustering (MMseqs2 95% id, 98% cov)
  -> Detection (geNomad + DIAMOND --very-sensitive)
  -> Iterative evidence integration (AA1 -> AA2 -> NT1 -> NT2)
  -> Taxonomy (MMseqs2 + TaxonKit; GenBank viral NT primary DB)
  -> Coverage / abundance (CoverM + samtools depth)
  -> bigtable.tsv + dashboard.html + report.docx + materials_and_methods.txt
```

## Database Setup

DeepInvirus v1.1.0 uses 10 major databases/resources in the full production layout.

| # | Database / Resource | Role | Approx. size |
|---|---|---|---:|
| 1 | GenBank viral NT | Primary viral nucleotide DB (`NT1`, taxonomy) | 9.3 GB |
| 2 | Viral protein DIAMOND | Tier 1 viral-first AA search | 225 MB |
| 3 | UniRef50 DIAMOND | Tier 2 all-kingdom AA verification | 24 GB |
| 4 | UniRef90 viral DIAMOND | Supplemental viral protein resource | 400 MB |
| 5 | Polymicrobial NT BLAST | Tier 4 non-viral exclusion search | 54 GB |
| 6 | Kraken2 `core_nt` | Optional read-based taxonomy module | 307 GB |
| 7 | geNomad DB | ML viral detection | 1.4 GB |
| 8 | CheckV DB | Viral genome quality assessment | 6.4 GB |
| 9 | Taxonomy + ICTV VMR | TaxonKit lineage + ICTV metadata | 583 MB |
| 10 | Host genomes | Host depletion with minimap2 | 4.9 GB |

### Installer

```bash
python bin/install_databases.py \
  --db-dir /path/to/DeepInvirus_DB \
  --components all \
  --host human \
  --threads 8
```

### Expected layout

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

## Output Files

### Primary deliverables

| File | Description |
|---|---|
| `taxonomy/bigtable.tsv` | Integrated `seq_id x sample` results table with evidence, taxonomy, and abundance |
| `dashboard.html` | Standalone interactive dashboard |
| `report.docx` | Automated Word report |
| `materials_and_methods.txt` | Paper-ready methods text assembled from runtime metadata |

### Important subdirectories

| Path | Description |
|---|---|
| `assembly/` | Co-assembly FASTA, clustering outputs, and assembly metrics |
| `classification/` | Tier-wise AA/NT evidence outputs |
| `coverage/` | CoverM summaries and per-base `samtools depth` files |
| `detection/` | geNomad, DIAMOND, and optional CheckV outputs |
| `diversity/` | Alpha/beta diversity tables and ordinations |
| `kraken2/` | Optional Kraken2, Bracken, and Krona outputs |
| `pipeline_info/` | Run metadata, DAG, trace, timeline, reports |
| `figures/` | Report/dashboard figures and overlay assets |

### `bigtable.tsv` highlights

Key v1.1.0 columns include:

- `length`: true contig length carried from CoverM-aware merging, not alignment span
- `rpm`: coverage-normalized abundance used for dashboard filtering
- `taxname`: primary taxon name used in tables and taxonomy views
- `refseq_verified`: secondary RefSeq-derived verification flag
- `evidence_classification`: final evidence label
- `evidence_support_tier`: strongest supporting tier

## Dashboard Features

- Overview cards and run summaries
- Treemap and sunburst taxonomy views using Plotly auto colorway
- Sankey taxonomy view with natural flow rather than fixed node positioning
- Taxonomy tab filtering with RPM threshold and Top N controls
- Search pagination, grouped headers, and hide-unclassified toggle
- Contig modal with per-base depth plots
- Figure overlay viewer for rapid comparison of embedded report figures

## Parameters

### Core parameters

| Parameter | Default | Description |
|---|---|---|
| `--reads` | `null` | Paired-end FASTQ glob or directory |
| `--host` | `human` in config, `none` fallback in `main.nf` | Comma-separated host nicknames or `none` |
| `--outdir` | Timestamped results directory | Output directory |
| `--db_dir` | `null` | DeepInvirus database root |
| `--trimmer` | `bbduk` | `bbduk` or `fastp` |
| `--assembler` | `megahit` | `megahit` or `metaspades` |
| `--search` | `very-sensitive` | DIAMOND mode: `fast`, `sensitive`, or `very-sensitive` |
| `--skip_ml` | `false` | Skip geNomad ML detection |

### Detection / classification parameters

| Parameter | Default | Description |
|---|---|---|
| `--min_contig_len` | `500` | Minimum assembled contig length |
| `--min_virus_score` | `0.7` | geNomad viral score threshold |
| `--min_bitscore` | `50` | Minimum bitscore filter |
| `--checkv_db` | `null` | Optional CheckV DB |
| `--exclusion_db` | `null` | Optional exclusion DIAMOND DB |
| `--kraken2_db` | `null` | Optional Kraken2 DB |
| `--uniref50_db` | `null` | Tier 2 UniRef50 DB |
| `--viral_nt_db` | `null` | Tier 3 viral NT DB prefix |
| `--polymicrobial_nt_db` | `null` | Tier 4 polymicrobial NT DB prefix |

### Runtime parameters

| Parameter | Default | Description |
|---|---|---|
| `--threads` | Available CPUs | Requested parallel threads |
| `--max_cpus` | `32` | Max CPUs per process |
| `--max_memory` | `256.GB` | Max memory per process |
| `--max_time` | `24.h` | Max wall time per process |
| `--use_ramdisk` | `false` | Use RAM disk for work staging |
| `--ramdisk_size` | `0` | RAM disk size in GB (`0` = auto) |
| `--work_dir` | `null` | Custom Nextflow work directory |

## Evidence Classification Rules

DeepInvirus v1.1.0 surfaces three primary viral review classes in downstream reporting:

| User-facing class | Practical interpretation |
|---|---|
| `strong_viral` | Strong viral-first evidence with no stronger cellular exclusion signal |
| `novel_candidate` | High ML support without enough homology evidence for `strong_viral` |
| `ambiguous` | Mixed, conflicting, or incomplete evidence requiring manual review |

The current implementation also retains non-viral and unresolved states for completeness:

- Internal ML-only label: `novel_viral_candidate`
- Non-viral fallback: `cellular`
- No meaningful evidence: `unknown`

Tier logic summary:

- `AA1`: viral-first amino-acid search
- `AA2`: all-kingdom amino-acid verification
- `NT1`: viral-first nucleotide search against GenBank viral NT
- `NT2`: polymicrobial nucleotide exclusion search

## Test Data

Use the bundled lightweight fixtures for smoke testing:

```bash
nextflow run main.nf -profile test,docker
```

Related assets are available under `tests/data/` for pipeline, DB, and TUI testing.

## Citation

```text
DeepInvirus Team. DeepInvirus: a Nextflow DSL2 pipeline for assembly-based viral metagenomics with iterative evidence integration. Version 1.1.0.
```

Please also cite the underlying tools and databases where appropriate, including Nextflow, geNomad, DIAMOND, MMseqs2, TaxonKit, CoverM, samtools, CheckV, Kraken2, Bracken, and the NCBI/ICTV resources used in your run.

## License

DeepInvirus is distributed under the MIT License.
