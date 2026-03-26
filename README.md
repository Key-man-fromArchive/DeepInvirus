<p align="center">
  <h1 align="center">DeepInvirus</h1>
  <p align="center">
    <strong>End-to-end viral metagenomics pipeline with interactive TUI</strong><br>
    <em>Raw FASTQ &rarr; Publication-ready results in a single command</em>
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> &bull;
    <a href="#features">Features</a> &bull;
    <a href="#tui-mode">TUI Mode</a> &bull;
    <a href="#cli-mode">CLI Mode</a> &bull;
    <a href="#한국어-가이드">한국어 가이드</a>
  </p>
</p>

---

## Overview

DeepInvirus is a Nextflow DSL2 pipeline that automates the complete viral metagenomics workflow:

```
Raw FASTQ → QC → Host Removal → Assembly → Virus Detection → Classification → Diversity → Dashboard + Report
```

Unlike existing tools that only produce raw tables, DeepInvirus goes **end-to-end** — from sequencing reads to an interactive HTML dashboard and an automated Word report ready for clients or publications.

### Why DeepInvirus?

| Problem | DeepInvirus Solution |
|---------|---------------------|
| Existing tools (e.g., Hecatomb) produce only raw tables | End-to-end: raw FASTQ → dashboard + Word report |
| Outdated algorithms (MMseqs2 v12, ICTV 2019) | Latest tools: geNomad, Diamond, ICTV 2024 |
| No ML-based virus detection | geNomad + Diamond dual detection |
| Manual R/Python post-processing | Automated diversity analysis, heatmaps, PCoA |
| No interactive visualization | Plotly.js-based interactive HTML dashboard |
| Snakemake version conflicts | Nextflow + Docker/Singularity for reproducibility |
| Hard to swap tools | Modular design — each step is independently replaceable |

---

## Features

### Pipeline (v0.1.0)

- **QC & Preprocessing**: fastp + minimap2 host removal
- **Assembly**: MEGAHIT or metaSPAdes (configurable)
- **Virus Detection**: geNomad (ML-based) + Diamond blastx (homology-based)
- **Classification**: MMseqs2 taxonomy + TaxonKit + ICTV 2024
- **Diversity**: Shannon, Simpson, Chao1, Bray-Curtis, PCoA (scikit-bio)
- **Dashboard**: Interactive HTML with 4 tabs (Plotly.js) — heatmap, barplot, Sankey, PCoA
- **Report**: Automated Word document with figures, tables, and interpretation
- **Containers**: 5 Docker/Singularity images for full reproducibility
- **651 tests** passing

### TUI & CLI (v0.2.0)

- **Textual TUI**: 6-screen terminal interface with keyboard shortcuts
- **CLI**: 7 subcommands for batch/scripted use
- **DB Management**: Install, update, and track reference database versions
- **Host Genome**: Add custom host genomes with automatic minimap2 indexing
- **Config Presets**: Save/load pipeline parameter presets (YAML)
- **Run History**: Track past analyses, view results, re-run

---

## Quick Start

### 1. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [Nextflow](https://www.nextflow.io/) | >= 23.04 | Workflow orchestration |
| [Docker](https://www.docker.com/) or [Singularity](https://sylabs.io/singularity/) | latest / >= 3.8 | Container runtime |
| Python | >= 3.11 | Helper scripts & TUI |

### 2. Clone & Install

```bash
git clone https://github.com/Key-man-fromArchive/DeepInvirus.git
cd DeepInvirus
pip install -r bin/requirements.txt
```

### 3. Install Reference Databases

```bash
# Install all databases (~50 GB)
python bin/install_databases.py \
    --db-dir /path/to/databases \
    --host human \
    --threads 8

# Preview without downloading
python bin/install_databases.py --db-dir /path/to/databases --dry-run
```

### 4. Run the Pipeline

```bash
# Using Nextflow directly
nextflow run main.nf \
    --reads '/data/samples/*_R{1,2}.fastq.gz' \
    --host human \
    --db_dir /path/to/databases \
    --outdir ./results \
    -profile docker

# Or use the CLI wrapper
python bin/deepinvirus_cli.py run \
    --reads ./raw_data \
    --host insect \
    --outdir ./results
```

### 5. View Results

- Open `results/dashboard.html` in a web browser for the interactive dashboard
- Open `results/report.docx` for the automated Word report
- Check `results/qc/multiqc_report.html` for QC summary

---

## TUI Mode

Launch the interactive terminal user interface:

```bash
python bin/deepinvirus_cli.py
# or simply: deepinvirus (if installed via pip)
```

```
┌──────────────────────────────────────────────┐
│  DeepInvirus v0.2.0        DB: 2026-03-23    │
├──────────────────────────────────────────────┤
│                                              │
│   ┌──────────────┐  ┌──────────────┐        │
│   │ [R]un        │  │ [D]atabase   │        │
│   │ Analysis     │  │ Management   │        │
│   └──────────────┘  └──────────────┘        │
│                                              │
│   ┌──────────────┐  ┌──────────────┐        │
│   │ [H]ost       │  │ [C]onfig     │        │
│   │ Genome       │  │ Presets      │        │
│   └──────────────┘  └──────────────┘        │
│                                              │
│   ┌──────────────┐  ┌──────────────┐        │
│   │ [I] History  │  │ [?] Help     │        │
│   └──────────────┘  └──────────────┘        │
│                                              │
├──────────────────────────────────────────────┤
│  [r]Run [d]DB [h]Host [c]Config [q]Quit      │
└──────────────────────────────────────────────┘
```

### Screens

| Screen | Key | Description |
|--------|-----|-------------|
| Run Analysis | `r` | Configure parameters, launch pipeline with real-time progress |
| Database | `d` | View DB versions, install/update components |
| Host Genome | `h` | List hosts, add custom host genomes |
| Config Presets | `c` | Save/load/manage parameter presets |
| History | `i` | Browse past runs, view results, re-run |
| Help | `?` | Keyboard shortcut reference |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `r` | Run Analysis |
| `d` | Database Management |
| `h` | Host Genome |
| `c` | Config Presets |
| `i` | History |
| `Escape` | Back |
| `q` | Quit |

---

## CLI Mode

For batch processing and scripting:

```bash
# Run pipeline
deepinvirus run --reads ./data --host insect --outdir ./results

# Database management
deepinvirus install-db --db-dir /path/to/db --host human
deepinvirus update-db --db-dir /path/to/db --component taxonomy

# Host genome management
deepinvirus add-host --name beetle --fasta beetle_ref.fa --db-dir /path/to/db
deepinvirus list-hosts --db-dir /path/to/db

# Config & History
deepinvirus config --list
deepinvirus history --limit 10

# Help
deepinvirus --help
deepinvirus run --help
```

---

## Parameter Dictionary

### Required Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--reads` | string | null | Path to paired FASTQ files (glob pattern). Example: `'/data/*_R{1,2}.fastq.gz'` |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--host` | string | `none` | Host genome(s) for read removal. Comma-separated nicknames: `tmol,zmor,human`. Use `none` to skip. |
| `--outdir` | string | `./results` | Output directory path |
| `--trimmer` | string | `bbduk` | Read trimming tool: `bbduk` or `fastp` |
| `--assembler` | string | `megahit` | De novo assembler: `megahit` or `metaspades` |
| `--search` | string | `sensitive` | Diamond search sensitivity: `fast` or `sensitive` |
| `--skip_ml` | boolean | `false` | Skip ML-based virus detection (geNomad). Uses Diamond-only. |
| `--db_dir` | string | `null` | Custom database directory. Auto-downloads if null. |
| `--checkv_db` | string | `null` | CheckV database path. Skips CheckV if null. |
| `--min_contig_len` | integer | `500` | Minimum contig length for assembly output |
| `--min_virus_score` | float | `0.7` | Minimum geNomad virus score threshold |
| `--min_bitscore` | integer | `50` | Minimum Diamond bitscore filter |

### Resource Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--max_cpus` | integer | `32` | Maximum CPUs per process |
| `--max_memory` | string | `256.GB` | Maximum memory per process |

---

## Results Dictionary

### Output Directory Structure

```
results/
├── qc/                          # Quality control results
│   ├── multiqc_report.html      # MultiQC aggregate report
│   ├── *.bbduk_stats.txt        # BBDuk adapter removal statistics
│   ├── fastqc/                  # FastQC reports (raw + trimmed)
│   └── *.host_removal_stats.txt # Host mapping statistics
├── assembly/                    # Co-assembly results
│   ├── contigs.fa               # Assembled contigs (>=500bp)
│   └── assembly_stats.tsv       # N50, total length, contig count
├── detection/                   # Virus detection results
│   ├── genomad/                 # geNomad ML-based detection
│   ├── diamond/                 # Diamond BLASTx homology search
│   └── checkv/                  # CheckV genome quality (optional)
├── taxonomy/                    # Classification results
│   ├── bigtable.tsv             # Master results table (see below)
│   ├── sample_taxon_matrix.tsv  # Family x Sample RPM abundance
│   └── sample_counts.tsv        # Per-sample contig counts
├── coverage/                    # Per-sample read coverage
│   └── *_coverage.tsv           # CoverM coverage per sample
├── diversity/                   # Diversity analysis
│   ├── alpha_diversity.tsv      # Shannon, Simpson, Chao1, Pielou
│   ├── beta_diversity.tsv       # Bray-Curtis distance matrix
│   └── pcoa_coordinates.tsv     # PCoA ordination coordinates
├── figures/                     # Publication-quality figures (PNG + SVG)
├── dashboard.html               # Interactive Plotly dashboard
└── report.docx                  # Automated Word report
```

### bigtable.tsv Column Dictionary

| Column | Type | Description |
|--------|------|-------------|
| `seq_id` | string | Contig identifier from assembly |
| `sample` | string | Sample name (from read filename) |
| `seq_type` | string | Sequence type: `contig` or `read` |
| `length` | integer | Contig length in base pairs |
| `detection_method` | string | How the virus was detected: `genomad`, `diamond`, `both` |
| `detection_score` | float | Detection confidence score (0-1) |
| `taxid` | integer | NCBI taxonomy ID |
| `domain` | string | Taxonomic domain (e.g., Viruses) |
| `phylum` | string | Taxonomic phylum |
| `class` | string | Taxonomic class |
| `order` | string | Taxonomic order |
| `family` | string | Taxonomic family (e.g., Parvoviridae) |
| `genus` | string | Taxonomic genus |
| `species` | string | Taxonomic species |
| `ictv_classification` | string | ICTV official classification |
| `baltimore_group` | string | Baltimore classification group |
| `count` | integer | Raw mapped read count |
| `rpm` | float | Coverage-normalized relative abundance (contig coverage / total sample coverage × 1e6) |
| `coverage` | float | Mean read depth (CoverM) |

### sample_taxon_matrix.tsv

RPM-based abundance matrix for diversity analysis:
- Rows: virus families (taxon)
- Columns: `taxon`, `taxid`, `rank`, then one column per sample
- Values: sum of RPM for all contigs in that family per sample

### Report Sections

| Section | Content | Auto-generated |
|---------|---------|----------------|
| Executive Summary | Key findings, top virus | Yes |
| Methods | Tools, versions, parameters | Yes (from pipeline metadata) |
| QC Results | Read counts, adapter removal rates | Yes |
| Host Removal | Mapping rates per sample | Yes |
| Virus Detection | Detection methods, family distribution | Yes |
| Coverage Analysis | Per-sample heatmap, top contigs | Yes |
| Taxonomic Analysis | Family descriptions, classification | Yes |
| Diversity | Alpha/Beta diversity (conditional on n>=3) | Yes |
| Conclusions | Data-driven, scientifically hedged | Yes |
| Limitations | Sample size, RNA-seq caveats, co-assembly limits | Yes |

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `ERROR: Cannot find Java` | Install Java 17+: `sudo apt install openjdk-21-jdk` or set `JAVA_HOME` |
| `checkIfExists` failure on host genome | Use `--host none` to skip host removal, or install host DB first |
| Empty MultiQC report | When using `--trimmer bbduk`, MultiQC uses FastQC results (BBDuk stats go to Word report) |
| `CLASSIFICATION` channel mismatch | Ensure `--db_dir` points to correct database directory with `viral_nucleotide/` subdirectory |
| Dashboard coverage panel empty | Coverage files must be in `--coverage-dir` or pipeline must complete CoverM step |
| Diversity analysis shows only 1 sample | With n<3 samples, diversity comparison is limited. n>=3 needed for statistical tests |

### Resume a Failed Run

```bash
# Nextflow caches completed steps. Just add -resume:
nextflow run main.nf --reads '...' -resume -profile docker
```

### Memory Issues

```bash
# Reduce memory for MEGAHIT:
nextflow run main.nf --reads '...' --max_memory '64.GB' --max_cpus 16
```

---

## Scientific Notes

### Co-assembly Strategy
DeepInvirus uses co-assembly: all samples are pooled for a single MEGAHIT assembly, then per-sample reads are mapped back to measure coverage. This maximizes sensitivity for low-abundance viruses but may produce chimeric contigs. Per-sample coverage (depth + breadth) distinguishes genuine per-sample virus presence.

### Coverage Interpretation
- **Mean depth**: Average read depth across the contig. Higher = more abundant in that sample.
- **Breadth**: Fraction of the contig covered by at least 1 read. Higher = more complete detection.
- **Detection confidence**: high (breadth>=70%, depth>=10x), medium (breadth>=30%, depth>=1x), low (otherwise).
- RNA-seq data: DNA virus coverage reflects transcription activity, not genome copy number.

### RPM (Relative Abundance)
RPM in DeepInvirus is **coverage-normalized**: `(contig_coverage / total_sample_coverage) * 1e6`. This is analogous to reads-per-million but uses mean depth as the abundance proxy. It normalizes for sequencing depth differences between samples.

### VIRUS_ORIGIN Classification
Virus families are classified by likely ecological origin with confidence tiers:
- **high**: Well-established host association (e.g., Iflaviridae -> insect)
- **medium**: Generally accepted but exceptions exist (e.g., Parvoviridae -> insect, but Parvovirinae are vertebrate)
- **low**: Family-level classification insufficient; genus-level resolution recommended
- Families not ending in *-viridae* are assigned "Unclassified" to prevent rank contamination.

### Diversity Analysis
- n>=3 samples: Full alpha diversity (Shannon, Simpson, Chao1) + beta diversity (Bray-Curtis, PCoA)
- n=2 samples: Descriptive comparison only (fold-change, Jaccard similarity). No statistical tests.
- n=1 sample: Viral profile only.
- Chao1 estimates use coverage-normalized values and should be interpreted as approximate.

---

## Pipeline Architecture

```
                        ┌─────────────────┐
                        │   Raw FASTQ     │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   FASTP (QC)    │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │  HOST REMOVAL   │
                        │  (minimap2)     │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   ASSEMBLY      │
                        │ MEGAHIT/SPAdes  │
                        └────────┬────────┘
                                 │
                    ┌────────────┼────────────┐
                    │                         │
           ┌────────▼────────┐     ┌─────────▼────────┐
           │    geNomad      │     │     Diamond       │
           │  (ML detect)    │     │   (blastx)        │
           └────────┬────────┘     └─────────┬─────────┘
                    │                         │
                    └────────────┬─────────────┘
                                 │
                        ┌────────▼────────┐
                        │  CLASSIFICATION │
                        │ MMseqs2+TaxonKit│
                        └────────┬────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               │                 │                  │
      ┌────────▼───────┐ ┌──────▼──────┐ ┌────────▼───────┐
      │   DIVERSITY    │ │  DASHBOARD  │ │    REPORT      │
      │ alpha + beta   │ │  HTML+Plotly│ │  Word (.docx)  │
      └────────────────┘ └─────────────┘ └────────────────┘
```

### Tools & Versions

| Step | Tool | Version | Container |
|------|------|---------|-----------|
| QC | fastp | >= 0.23 | deepinvirus/qc |
| Host removal | minimap2 + samtools | >= 2.26, >= 1.18 | deepinvirus/qc |
| Assembly | MEGAHIT / metaSPAdes | >= 1.2.9 / >= 3.15 | deepinvirus/assembly |
| Virus detection (ML) | geNomad | >= 1.7 | deepinvirus/detect |
| Virus detection (homology) | Diamond | >= 2.1 | deepinvirus/detect |
| Classification | MMseqs2 + TaxonKit | >= 15.6, >= 0.15 | deepinvirus/classify |
| Coverage | CoverM | >= 0.7 | deepinvirus/classify |
| Dashboard | Plotly.js + Jinja2 | - | deepinvirus/reporting |
| Report | python-docx + matplotlib | - | deepinvirus/reporting |
| QC aggregate | MultiQC | >= 1.14 | deepinvirus/reporting |

---

## Database Management

### Reference Databases (~50 GB total)

| Database | Source | Purpose |
|----------|--------|---------|
| Viral Protein | UniRef90 viral | Diamond blastx reference |
| Viral Nucleotide | NCBI RefSeq Viral | MMseqs2 nucleotide search |
| geNomad DB | Zenodo | ML virus detection model |
| NCBI Taxonomy | NCBI FTP | Taxonomic lineage resolution |
| ICTV VMR | ICTV website | ICTV 2024 classification |
| Host Genomes | Various | Host read decontamination |

### Install

```bash
# All databases
python bin/install_databases.py --db-dir /path/to/db

# Specific components only
python bin/install_databases.py --db-dir /path/to/db --components taxonomy,protein
```

### Update

```bash
# Update specific component
python bin/update_databases.py --db-dir /path/to/db --component taxonomy

# Force update all
python bin/update_databases.py --db-dir /path/to/db --component all --force
```

### Add Custom Host Genome

```bash
python bin/add_host.py \
    --name beetle \
    --fasta /path/to/Tenebrio_molitor_genome.fa \
    --db-dir /path/to/db \
    --threads 8
```

---

## Execution Profiles

| Profile | Description |
|---------|-------------|
| `docker` | Run with Docker containers (local) |
| `singularity` | Run with Singularity containers (HPC) |
| `test` | Minimal test data, reduced resources |

### Resume after failure

```bash
nextflow run main.nf -resume [same parameters]
```

### HPC (SLURM)

```bash
nextflow run main.nf \
    --reads ./data \
    -profile singularity \
    -process.executor slurm \
    -process.queue normal
```

---

## Development

### Run Tests

```bash
cd DeepInvirus
pip install -r bin/requirements.txt
python -m pytest tests/ -v          # 651 tests
python -m pytest tests/ -v --tb=short -q  # Quick summary
```

### Code Quality

```bash
ruff check bin/       # Linting
black bin/ --check    # Formatting
```

### Project Structure

```
DeepInvirus/
├── main.nf                    # Nextflow pipeline entrypoint
├── nextflow.config            # Default configuration
├── modules/local/             # 16 Nextflow process modules
├── subworkflows/              # 5 subworkflow definitions
├── bin/                       # 15+ Python helper scripts
│   ├── tui/                   # Textual TUI application
│   │   ├── app.py             # Main App class
│   │   ├── screens/           # 6 TUI screens
│   │   ├── widgets/           # 5 custom widgets
│   │   └── styles/            # Textual CSS
│   └── utils/                 # Shared utilities
├── conf/                      # Environment-specific configs
├── containers/                # 5 Dockerfiles
├── assets/                    # Dashboard template, report template
├── tests/                     # 651 pytest tests
└── docs/planning/             # 9 design documents
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

---

# 한국어 가이드

## 개요

DeepInvirus는 바이러스 메타게노믹스 분석을 위한 Nextflow 기반 통합 파이프라인입니다.

기존 도구들(Hecatomb 등)은 raw 테이블만 생성하는 "데이터 생성기"에 불과했습니다. DeepInvirus는 **Raw FASTQ에서 논문/보고서급 결과물까지** 끊김 없이 자동화합니다.

```
Raw FASTQ → QC → Host 제거 → 어셈블리 → 바이러스 탐지 → 분류 → 다양성 분석 → 대시보드 + 보고서
```

### 왜 DeepInvirus인가?

| 기존 도구의 문제 | DeepInvirus 해결책 |
|-----------------|-------------------|
| raw 테이블만 출력 (수작업 후처리 필요) | end-to-end: FASTQ → 대시보드 + Word 보고서 |
| 구버전 알고리즘 (MMseqs2 v12, ICTV 2019) | 최신 도구: geNomad, Diamond, ICTV 2024 |
| ML 기반 바이러스 탐지 없음 | geNomad (ML) + Diamond (상동성) 이중 탐지 |
| 시각화/통계 수동 | 자동 다양성 분석, 히트맵, PCoA, Sankey |
| Snakemake 버전 호환성 문제 | Nextflow + Docker/Singularity 재현성 보장 |
| 도구 교체 어려움 | 모듈식 설계 — 각 단계를 독립적으로 교체 가능 |

---

## 주요 기능

### 파이프라인 (v0.1.0)

- **QC 및 전처리**: fastp + minimap2 host read 제거
- **어셈블리**: MEGAHIT 또는 metaSPAdes (선택 가능)
- **바이러스 탐지**: geNomad (ML 기반) + Diamond blastx (상동성 기반)
- **분류**: MMseqs2 taxonomy + TaxonKit + ICTV 2024
- **다양성 분석**: Shannon, Simpson, Chao1, Bray-Curtis, PCoA
- **대시보드**: 인터랙티브 HTML (Plotly.js) — 히트맵, 바플롯, Sankey, PCoA
- **보고서**: Word 문서 자동 생성 (그림 + 테이블 + 해석)
- **컨테이너**: Docker/Singularity 5종 제공
- **테스트**: 651개 통과

### TUI 및 CLI (v0.2.0)

- **터미널 UI**: Textual 기반 6개 화면, 키보드 단축키
- **CLI**: 7개 서브커맨드 (배치/스크립트 용도)
- **DB 관리**: 참조 데이터베이스 설치/업데이트/상태 확인
- **Host Genome 추가**: 커스텀 host 게놈 등록 + minimap2 자동 인덱싱
- **Config 프리셋**: 파이프라인 파라미터 YAML로 저장/로드
- **실행 이력**: 과거 분석 기록, 결과 보기, 재실행

---

## 빠른 시작

### 1. 사전 요구사항

| 도구 | 버전 | 용도 |
|------|------|------|
| [Nextflow](https://www.nextflow.io/) | >= 23.04 | 워크플로우 관리 |
| [Docker](https://www.docker.com/) 또는 [Singularity](https://sylabs.io/singularity/) | latest / >= 3.8 | 컨테이너 런타임 |
| Python | >= 3.11 | 보조 스크립트 및 TUI |

### 2. 설치

```bash
git clone https://github.com/Key-man-fromArchive/DeepInvirus.git
cd DeepInvirus
pip install -r bin/requirements.txt
```

### 3. 참조 데이터베이스 설치

```bash
# 전체 DB 설치 (~50 GB)
python bin/install_databases.py \
    --db-dir /path/to/databases \
    --host human \
    --threads 8

# 다운로드 없이 계획만 확인
python bin/install_databases.py --db-dir /path/to/databases --dry-run
```

### 4. 파이프라인 실행

```bash
# Nextflow 직접 실행
nextflow run main.nf \
    --reads '/data/samples/*_R{1,2}.fastq.gz' \
    --host human \
    --db_dir /path/to/databases \
    --outdir ./results \
    -profile docker

# 또는 CLI 래퍼 사용
python bin/deepinvirus_cli.py run \
    --reads ./raw_data \
    --host insect \
    --outdir ./results

# 또는 TUI 모드 (인터랙티브)
python bin/deepinvirus_cli.py
```

### 5. 결과 확인

- `results/dashboard.html` → 웹 브라우저에서 인터랙티브 대시보드
- `results/report.docx` → 자동 생성된 Word 보고서
- `results/taxonomy/bigtable.tsv` → 통합 분류 테이블 (19개 컬럼)
- `results/diversity/alpha_diversity.tsv` → 다양성 지수

---

## TUI 모드

```bash
python bin/deepinvirus_cli.py   # 인자 없이 실행하면 TUI 진입
```

### 화면 구성

| 화면 | 단축키 | 설명 |
|------|--------|------|
| Run Analysis | `r` | 파라미터 설정 + 실시간 진행 표시로 파이프라인 실행 |
| Database | `d` | 설치된 DB 버전 확인, 설치/업데이트 |
| Host Genome | `h` | host 목록 확인, 커스텀 host 추가 |
| Config Presets | `c` | 파라미터 프리셋 저장/로드/관리 |
| History | `i` | 과거 실행 기록, 결과 보기, 재실행 |
| Help | `?` | 단축키 도움말 |

---

## CLI 모드

배치 처리 및 스크립트 용도:

```bash
# 파이프라인 실행
deepinvirus run --reads ./data --host insect --outdir ./results

# DB 관리
deepinvirus install-db --db-dir /path/to/db --host human
deepinvirus update-db --db-dir /path/to/db --component taxonomy

# Host genome 관리
deepinvirus add-host --name beetle --fasta beetle_ref.fa --db-dir /path/to/db
deepinvirus list-hosts --db-dir /path/to/db

# 설정 및 이력
deepinvirus config --list
deepinvirus history --limit 10
```

---

## 파라미터 사전

### 필수 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `--reads` | string | null | Paired FASTQ 파일 경로 (glob 패턴). 예: `'/data/*_R{1,2}.fastq.gz'` |

### 선택 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `--host` | string | `none` | Host genome 제거용. 쉼표 구분: `tmol,zmor,human`. 건너뛰려면 `none`. |
| `--outdir` | string | `./results` | 출력 디렉토리 경로 |
| `--trimmer` | string | `bbduk` | Read trimming 도구: `bbduk` 또는 `fastp` |
| `--assembler` | string | `megahit` | De novo 어셈블러: `megahit` 또는 `metaspades` |
| `--search` | string | `sensitive` | Diamond 검색 감도: `fast` 또는 `sensitive` |
| `--skip_ml` | boolean | `false` | ML 기반 바이러스 탐지(geNomad) 건너뛰기. Diamond만 사용. |
| `--db_dir` | string | `null` | 커스텀 데이터베이스 디렉토리. null이면 자동 다운로드. |
| `--checkv_db` | string | `null` | CheckV 데이터베이스 경로. null이면 CheckV 건너뛰기. |
| `--min_contig_len` | integer | `500` | 어셈블리 출력 최소 contig 길이 |
| `--min_virus_score` | float | `0.7` | geNomad 최소 바이러스 점수 임계값 |
| `--min_bitscore` | integer | `50` | Diamond 최소 bitscore 필터 |

### 리소스 파라미터

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `--max_cpus` | integer | `32` | 프로세스당 최대 CPU 수 |
| `--max_memory` | string | `256.GB` | 프로세스당 최대 메모리 |

---

## 결과 사전

### 출력 디렉토리 구조

```
results/
├── qc/                          # 품질 관리 결과
│   ├── multiqc_report.html      # MultiQC 종합 리포트
│   ├── *.bbduk_stats.txt        # BBDuk 어댑터 제거 통계
│   ├── fastqc/                  # FastQC 리포트 (원본 + 트리밍)
│   └── *.host_removal_stats.txt # Host 매핑 통계
├── assembly/                    # Co-assembly 결과
│   ├── contigs.fa               # 조립된 contig (>=500bp)
│   └── assembly_stats.tsv       # N50, 총 길이, contig 수
├── detection/                   # 바이러스 탐지 결과
│   ├── genomad/                 # geNomad ML 기반 탐지
│   ├── diamond/                 # Diamond BLASTx 상동성 검색
│   └── checkv/                  # CheckV 게놈 품질 (선택)
├── taxonomy/                    # 분류 결과
│   ├── bigtable.tsv             # 통합 결과 테이블 (아래 참조)
│   ├── sample_taxon_matrix.tsv  # Family x Sample RPM 풍부도
│   └── sample_counts.tsv        # 샘플별 contig 카운트
├── coverage/                    # 샘플별 리드 커버리지
│   └── *_coverage.tsv           # CoverM 샘플별 커버리지
├── diversity/                   # 다양성 분석
│   ├── alpha_diversity.tsv      # Shannon, Simpson, Chao1, Pielou
│   ├── beta_diversity.tsv       # Bray-Curtis 거리 매트릭스
│   └── pcoa_coordinates.tsv     # PCoA 좌표
├── figures/                     # 논문 품질 그림 (PNG + SVG)
├── dashboard.html               # 인터랙티브 Plotly 대시보드
└── report.docx                  # 자동 생성 Word 보고서
```

### bigtable.tsv 컬럼 사전

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `seq_id` | string | 어셈블리에서 생성된 contig ID |
| `sample` | string | 샘플 이름 (리드 파일명에서 추출) |
| `seq_type` | string | 시퀀스 유형: `contig` 또는 `read` |
| `length` | integer | Contig 길이 (bp) |
| `detection_method` | string | 바이러스 탐지 방법: `genomad`, `diamond`, `both` |
| `detection_score` | float | 탐지 신뢰도 점수 (0-1) |
| `taxid` | integer | NCBI taxonomy ID |
| `domain` | string | 분류학적 도메인 (예: Viruses) |
| `phylum` | string | 분류학적 문(phylum) |
| `class` | string | 분류학적 강(class) |
| `order` | string | 분류학적 목(order) |
| `family` | string | 분류학적 과(family, 예: Parvoviridae) |
| `genus` | string | 분류학적 속(genus) |
| `species` | string | 분류학적 종(species) |
| `ictv_classification` | string | ICTV 공식 분류 |
| `baltimore_group` | string | Baltimore 분류 그룹 |
| `count` | integer | 원시 매핑 리드 수 |
| `rpm` | float | Coverage-normalized relative abundance (contig coverage / total sample coverage × 1e6) |
| `coverage` | float | 평균 리드 깊이 (CoverM) |

### sample_taxon_matrix.tsv

다양성 분석을 위한 RPM 기반 풍부도 매트릭스:
- 행: 바이러스 과(family)
- 열: `taxon`, `taxid`, `rank`, 그리고 샘플별 1개 열
- 값: 해당 과의 모든 contig RPM 합산

### 보고서 섹션

| 섹션 | 내용 | 자동 생성 |
|------|------|----------|
| Executive Summary | 핵심 발견, 상위 바이러스 | Yes |
| Methods | 도구, 버전, 파라미터 | Yes (파이프라인 메타데이터) |
| QC Results | 리드 수, 어댑터 제거율 | Yes |
| Host Removal | 샘플별 매핑률 | Yes |
| Virus Detection | 탐지 방법, 과 분포 | Yes |
| Coverage Analysis | 샘플별 히트맵, 상위 contig | Yes |
| Taxonomic Analysis | 과 설명, 분류 | Yes |
| Diversity | Alpha/Beta 다양성 (n>=3 조건) | Yes |
| Conclusions | 데이터 기반, 과학적으로 신중한 결론 | Yes |
| Limitations | 샘플 크기, RNA-seq 주의사항, co-assembly 제한 | Yes |

---

## 문제 해결

### 자주 발생하는 문제

| 문제 | 해결 방법 |
|------|----------|
| `ERROR: Cannot find Java` | Java 17+ 설치: `sudo apt install openjdk-21-jdk` 또는 `JAVA_HOME` 설정 |
| `checkIfExists` host genome 오류 | `--host none`으로 host 제거 건너뛰기, 또는 host DB 먼저 설치 |
| MultiQC 보고서 비어있음 | `--trimmer bbduk` 사용 시, MultiQC는 FastQC 결과 사용 (BBDuk 통계는 Word 보고서에 포함) |
| `CLASSIFICATION` 채널 불일치 | `--db_dir`이 `viral_nucleotide/` 하위 디렉토리가 있는 올바른 경로인지 확인 |
| 대시보드 커버리지 패널 비어있음 | 커버리지 파일이 `--coverage-dir`에 있거나 CoverM 단계가 완료되어야 함 |
| 다양성 분석에 샘플 1개만 표시 | n<3 샘플에서는 다양성 비교 제한적. 통계 검정에는 n>=3 필요 |

### 실패한 실행 재시작

```bash
# Nextflow는 완료된 단계를 캐시합니다. -resume만 추가:
nextflow run main.nf --reads '...' -resume -profile docker
```

### 메모리 문제

```bash
# MEGAHIT 메모리 줄이기:
nextflow run main.nf --reads '...' --max_memory '64.GB' --max_cpus 16
```

---

## 과학적 참고사항

### Co-assembly 전략
DeepInvirus는 co-assembly를 사용합니다: 모든 샘플을 하나의 MEGAHIT 어셈블리로 통합한 후, 샘플별 리드를 다시 매핑하여 커버리지를 측정합니다. 이는 저풍부도 바이러스의 감도를 극대화하지만, chimeric contig이 발생할 수 있습니다. 샘플별 커버리지(depth + breadth)로 실제 바이러스 존재 여부를 구분합니다.

### 커버리지 해석
- **Mean depth**: contig 전체의 평균 리드 깊이. 높을수록 해당 샘플에서 풍부함.
- **Breadth**: 최소 1개 리드가 커버하는 contig 비율. 높을수록 완전한 탐지.
- **Detection confidence**: high (breadth>=70%, depth>=10x), medium (breadth>=30%, depth>=1x), low (그 외).
- RNA-seq 데이터: DNA 바이러스 커버리지는 전사 활성을 반영하며, 게놈 복제 수가 아님.

### RPM (상대 풍부도)
DeepInvirus의 RPM은 **커버리지 정규화** 방식: `(contig_coverage / total_sample_coverage) * 1e6`. 이는 reads-per-million과 유사하지만 mean depth를 풍부도 대리 지표로 사용합니다. 샘플 간 시퀀싱 깊이 차이를 정규화합니다.

### VIRUS_ORIGIN 분류
바이러스 과(family)를 생태학적 기원에 따라 신뢰도 등급으로 분류:
- **high**: 잘 확립된 숙주 연관성 (예: Iflaviridae -> 곤충)
- **medium**: 일반적으로 인정되지만 예외 존재 (예: Parvoviridae -> 곤충, 그러나 Parvovirinae는 척추동물)
- **low**: 과 수준 분류 불충분; 속(genus) 수준 해상도 권장
- *-viridae*로 끝나지 않는 과는 "Unclassified"로 분류하여 분류 등급 오염 방지.

### 다양성 분석
- n>=3 샘플: 전체 알파 다양성 (Shannon, Simpson, Chao1) + 베타 다양성 (Bray-Curtis, PCoA)
- n=2 샘플: 기술적 비교만 (배수 변화, Jaccard 유사도). 통계 검정 없음.
- n=1 샘플: 바이러스 프로파일만.
- Chao1 추정치는 커버리지 정규화 값을 사용하며 근사값으로 해석해야 함.

---

## 참조 데이터베이스

### DB 목록 (~50 GB)

| 데이터베이스 | 소스 | 용도 |
|-------------|------|------|
| Viral Protein | UniRef90 바이러스 서브셋 | Diamond blastx 참조 |
| Viral Nucleotide | NCBI RefSeq Viral | MMseqs2 뉴클레오타이드 검색 |
| geNomad DB | Zenodo | ML 바이러스 탐지 모델 |
| NCBI Taxonomy | NCBI FTP | 분류학적 계층 구조 |
| ICTV VMR | ICTV 웹사이트 | ICTV 2024 바이러스 분류체계 |
| Host Genomes | 다양 | Host read 오염 제거 |

### Host Genome 추가

```bash
# 커스텀 host genome 등록 (예: 갈색거저리)
python bin/add_host.py \
    --name beetle \
    --fasta /path/to/Tenebrio_molitor_genome.fa \
    --db-dir /path/to/db \
    --threads 8
```

---

## 실행 프로필

| 프로필 | 설명 |
|--------|------|
| `docker` | Docker 컨테이너로 실행 (로컬) |
| `singularity` | Singularity 컨테이너로 실행 (HPC) |
| `test` | 소규모 테스트 데이터, 최소 리소스 |

### 실패 후 재시작

```bash
nextflow run main.nf -resume [동일 파라미터]
```

---

## 개발

### 테스트 실행

```bash
cd DeepInvirus
pip install -r bin/requirements.txt
python -m pytest tests/ -v          # 651개 테스트
```

### 코드 품질

```bash
ruff check bin/       # 린팅
black bin/ --check    # 포매팅
```

---

## 라이선스

MIT License
