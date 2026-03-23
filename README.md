# DeepInvirus

A Nextflow DSL2 pipeline for viral metagenomics analysis. DeepInvirus automates the complete workflow from raw FASTQ reads to publication-ready results, including virus detection (geNomad + Diamond), taxonomic classification (MMseqs2 + TaxonKit), diversity analysis, an interactive HTML dashboard, and an automated Word report.

## TUI Mode

Launch the interactive terminal user interface by running `deepinvirus` without any subcommand:

```bash
deepinvirus
```

### Main Menu

```
+----------------------------------------------+
|  DeepInvirus v0.2.0        DB: 2026-03-23    |
+----------------------------------------------+
|                                               |
|   +----------------+  +----------------+     |
|   | [R]un          |  | [D]atabase     |     |
|   | Analysis       |  | Management     |     |
|   +----------------+  +----------------+     |
|                                               |
|   +----------------+  +----------------+     |
|   | [H]ost         |  | [C]onfig       |     |
|   | Genome         |  | Presets        |     |
|   +----------------+  +----------------+     |
|                                               |
|   +----------------+  +----------------+     |
|   | [I] History    |  | [?] Help       |     |
|   |                |  |                |     |
|   +----------------+  +----------------+     |
|                                               |
+----------------------------------------------+
|  [r]Run [d]Database [h]Host [c]Config [q]Quit |
+----------------------------------------------+
```

The TUI provides 6 screens:

| Screen | Description |
|--------|-------------|
| Run Analysis | Configure and launch pipeline runs with real-time progress |
| Database Management | View installed databases, install/update components |
| Host Genome | List and add custom host reference genomes |
| Config Presets | Save/load pipeline parameter presets |
| History | Browse past runs, view results, re-run |
| Help | Keyboard shortcut reference |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `r` | Open Run Analysis screen |
| `d` | Open Database Management screen |
| `h` | Open Host Genome screen |
| `c` | Open Config Presets screen |
| `i` | Open History screen |
| `Escape` | Go back to previous screen |
| `q` | Quit the application |

## CLI Mode

For batch processing and scripting, use subcommands directly:

```bash
# Run the pipeline
deepinvirus run --reads ./data --host insect --outdir ./results

# Install all databases
deepinvirus install-db --db-dir /path/to/db --host human

# Update a specific database component
deepinvirus update-db --db-dir /path/to/db --component taxonomy

# Add a custom host genome
deepinvirus add-host --name beetle --fasta beetle_ref.fa --db-dir /path/to/db

# List installed host genomes
deepinvirus list-hosts --db-dir /path/to/db

# Manage config presets
deepinvirus config --list

# View run history
deepinvirus history --limit 10
```

Run `deepinvirus --help` or `deepinvirus <subcommand> --help` for full option details.

## Quick Start

### 1. Prerequisites

- [Nextflow](https://www.nextflow.io/) >= 23.04
- [Docker](https://www.docker.com/) or [Singularity](https://sylabs.io/singularity/) >= 3.8
- Python >= 3.11 (for bin/ helper scripts)

### 2. Install reference databases

```bash
python bin/install_databases.py \
    --db-dir /path/to/databases \
    --host human \
    --threads 8

# Preview the plan without downloading
python bin/install_databases.py --db-dir /path/to/databases --dry-run
```

### 3. Run the pipeline

```bash
nextflow run main.nf \
    --reads '/data/samples/*_R{1,2}.fastq.gz' \
    --host human \
    --db_dir /path/to/databases \
    --outdir ./results \
    -profile docker
```

### 4. Check results

Open `results/dashboard.html` in a web browser for an interactive overview.
The Word report is at `results/report.docx` and the comprehensive QC summary
is at `results/qc/multiqc_report.html`.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--reads` | *required* | Path to paired-end FASTQ files (glob pattern) or a samplesheet CSV |
| `--host` | `human` | Host genome for read decontamination (`human`, `mouse`, `insect`, `none`) |
| `--outdir` | `./results` | Output directory |
| `--assembler` | `megahit` | De novo assembler (`megahit` or `metaspades`) |
| `--search` | `sensitive` | Diamond search sensitivity (`fast` or `sensitive`) |
| `--skip_ml` | `false` | Skip ML-based virus detection (geNomad) |
| `--db_dir` | `null` | Path to pre-built reference databases |

## Output Files

```
results/
  qc/
    fastp_reports/          # Per-sample fastp HTML/JSON reports
    multiqc_report.html     # Aggregate QC summary
  assembly/
    contigs/                # Per-sample assembled contigs (FASTA)
    stats/                  # Assembly statistics
  detection/
    genomad/                # geNomad ML detection results
    diamond/                # Diamond blastx results
  taxonomy/
    bigtable.tsv            # Unified results table (all contigs, all annotations)
    viral_taxonomy.tsv      # Virus-only filtered taxonomy
    sample_counts.tsv       # Sample x species count matrix
  diversity/
    alpha_diversity.tsv     # Shannon, Simpson, Chao1 per sample
    beta_diversity.tsv      # Bray-Curtis distance matrix
  figures/
    heatmap.png             # Taxonomic heatmap
    barplot.png             # Relative abundance bar plot
    pcoa.png                # PCoA ordination plot
    sankey.png              # Sankey diagram (classification hierarchy)
  dashboard.html            # Interactive HTML dashboard (Plotly)
  report.docx               # Automated Word report with figures
```

## Database Management

### Install databases

```bash
# Install all databases
python bin/install_databases.py --db-dir /path/to/databases

# Install only specific components
python bin/install_databases.py --db-dir /path/to/databases --components taxonomy,protein
```

### Update databases

```bash
# Update a specific component
python bin/update_databases.py --db-dir /path/to/databases --component taxonomy

# Update all components
python bin/update_databases.py --db-dir /path/to/databases --component all --force
```

## Execution Profiles

| Profile | Description |
|---------|-------------|
| `docker` | Run with Docker containers |
| `singularity` | Run with Singularity containers (HPC) |
| `test` | Run with minimal test data and reduced resources |

### Resume after failure

```bash
nextflow run main.nf -resume [same parameters]
```

## Development

### Run tests

```bash
cd DeepInvirus
python -m pytest tests/ -v
```

### Project structure

```
DeepInvirus/
  main.nf                  # Pipeline entrypoint
  nextflow.config           # Configuration
  subworkflows/             # Subworkflow definitions
  modules/local/            # Nextflow process modules
  bin/                      # Python helper scripts
  conf/                     # Environment-specific configs
  containers/               # Dockerfiles
  tests/                    # pytest test suite
  docs/planning/            # Design documents
```

## Requirements

| Tool | Version | Purpose |
|------|---------|---------|
| Nextflow | >= 23.04 | Workflow orchestration |
| Docker / Singularity | latest / >= 3.8 | Container runtime |
| Python | >= 3.11 | Helper scripts |
| fastp | >= 0.23 | QC and adapter trimming |
| minimap2 | >= 2.26 | Host read removal |
| MEGAHIT | >= 1.2.9 | De novo assembly |
| geNomad | >= 1.7 | ML-based virus detection |
| Diamond | >= 2.1 | Protein homology search |
| MMseqs2 | >= 15.6 | Taxonomic classification |
| TaxonKit | >= 0.15 | Lineage reformatting |
| CoverM | >= 0.7 | Read coverage calculation |
| MultiQC | >= 1.14 | Aggregate QC reporting |

## License

This project is for internal use. See the project documentation for details.
