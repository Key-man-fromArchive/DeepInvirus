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

## Pipeline Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--reads` | *required* | Path to paired-end FASTQ files (glob) or samplesheet |
| `--host` | `human` | Host genome: `human`, `mouse`, `insect`, `none` |
| `--outdir` | `./results` | Output directory |
| `--assembler` | `megahit` | Assembler: `megahit` or `metaspades` |
| `--search` | `sensitive` | Diamond sensitivity: `fast` or `sensitive` |
| `--skip_ml` | `false` | Skip geNomad ML detection |
| `--db_dir` | `null` | Reference database directory |
| `--threads` | System CPUs | Number of threads |

---

## Output Structure

```
results/
├── qc/
│   ├── fastp_reports/           # Per-sample QC reports (HTML/JSON)
│   └── multiqc_report.html      # Aggregate QC summary
├── assembly/
│   ├── contigs/                 # Assembled contigs (FASTA)
│   └── stats/                   # Assembly statistics (N50, etc.)
├── detection/
│   ├── genomad/                 # geNomad ML detection results
│   └── diamond/                 # Diamond blastx results
├── taxonomy/
│   ├── bigtable.tsv             # Unified annotation table (19 columns)
│   ├── viral_taxonomy.tsv       # Virus-only filtered results
│   └── sample_counts.tsv        # Sample x species count matrix
├── diversity/
│   ├── alpha_diversity.tsv      # Shannon, Simpson, Chao1, Pielou
│   └── beta_diversity.tsv       # Bray-Curtis distance matrix
├── figures/
│   ├── heatmap.png              # Taxonomic heatmap (clustered)
│   ├── barplot.png              # Relative abundance stacked bar
│   ├── pcoa.png                 # PCoA ordination (95% CI ellipse)
│   └── sankey.png               # Classification hierarchy Sankey
├── dashboard.html               # Interactive HTML dashboard (Plotly.js)
└── report.docx                  # Automated Word report with figures
```

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

## 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `--reads` | *필수* | Paired-end FASTQ 파일 경로 (glob 패턴) |
| `--host` | `human` | Host genome: `human`, `mouse`, `insect`, `none` |
| `--outdir` | `./results` | 출력 디렉토리 |
| `--assembler` | `megahit` | 어셈블러: `megahit` 또는 `metaspades` |
| `--search` | `sensitive` | Diamond 검색 감도: `fast` 또는 `sensitive` |
| `--skip_ml` | `false` | geNomad ML 탐지 건너뛰기 |
| `--db_dir` | `null` | 참조 데이터베이스 경로 |

---

## 출력 파일 구조

```
results/
├── qc/
│   ├── fastp_reports/           # 샘플별 QC 리포트 (HTML/JSON)
│   └── multiqc_report.html      # 종합 QC 요약
├── assembly/
│   ├── contigs/                 # 조립된 contig (FASTA)
│   └── stats/                   # 어셈블리 통계 (N50 등)
├── detection/
│   ├── genomad/                 # geNomad ML 탐지 결과
│   └── diamond/                 # Diamond blastx 결과
├── taxonomy/
│   ├── bigtable.tsv             # 통합 분류 테이블 (19개 컬럼)
│   ├── viral_taxonomy.tsv       # 바이러스만 필터링
│   └── sample_counts.tsv        # 샘플 x 종 카운트 매트릭스
├── diversity/
│   ├── alpha_diversity.tsv      # Shannon, Simpson, Chao1, Pielou
│   └── beta_diversity.tsv       # Bray-Curtis 거리 매트릭스
├── figures/
│   ├── heatmap.png              # 텍소노믹 히트맵 (클러스터링)
│   ├── barplot.png              # 상대 풍부도 바플롯
│   ├── pcoa.png                 # PCoA 플롯 (95% 신뢰 타원)
│   └── sankey.png               # 분류 계층 Sankey 다이어그램
├── dashboard.html               # 인터랙티브 HTML 대시보드
└── report.docx                  # 자동 생성 Word 보고서
```

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
