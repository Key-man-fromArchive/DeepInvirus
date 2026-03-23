# TRD (기술 요구사항 정의서) - DeepInvirus

---

## MVP 캡슐

| # | 항목 | 내용 |
|---|------|------|
| 1 | 목표 | Raw FASTQ → 논문/보고서급 결과물 자동 출력 바이러스 메타게노믹스 파이프라인 |
| 2 | 페르소나 | 바이러스 메타게노믹스 분석 수탁 서비스 운영자 |
| 3 | 핵심 기능 | FEAT-1: 최신 알고리즘 통합 파이프라인 |
| 4 | 성공 지표 | 수작업 시간 80% 감소 |
| 5 | 입력 지표 | 파이프라인 완주율 ≥ 95% |
| 6 | 비기능 요구 | 모듈식 설계, 도구 교체 가능 |
| 7 | Out-of-scope | 웹 SaaS, GUI, 16S rRNA |
| 8 | Top 리스크 | 도구 간 데이터 포맷 호환성 |
| 9 | 완화/실험 | 표준 중간 포맷 정의 + 단위 테스트 |
| 10 | 다음 단계 | Nextflow 프로젝트 초기화 |

---

## 1. 시스템 아키텍처

### 1.1 고수준 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                      DeepInvirus Pipeline                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   │
│  │   QC     │──▶│ Assembly │──▶│ Detect   │──▶│ Classify │   │
│  │ Module   │   │ Module   │   │ Module   │   │ Module   │   │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   │
│       │                              │              │          │
│       ▼                              ▼              ▼          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│  │Diversity │   │Dashboard │   │ Report   │                  │
│  │ Module   │──▶│ Module   │──▶│ Module   │                  │
│  └──────────┘   └──────────┘   └──────────┘                  │
│                                      │                         │
│                                      ▼                         │
│                          ┌────────────────────┐                │
│                          │  Output Directory  │                │
│                          │  - tables/         │                │
│                          │  - figures/        │                │
│                          │  - dashboard.html  │                │
│                          │  - report.docx     │                │
│                          └────────────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 모듈 설명

| 모듈 | 역할 | 기본 도구 | 대안 도구 | 왜 이 선택? |
|------|------|----------|----------|-------------|
| QC | 읽기 품질 관리 + host 제거 | fastp + minimap2 | Trimmomatic + bowtie2 | fastp가 속도/정확도 최상 |
| Assembly | 메타게놈 조립 | MEGAHIT + metaSPAdes | Flye (long-read) | MEGAHIT 속도 + SPAdes 정확도 |
| Detect | 바이러스 서열 탐지 | geNomad + Diamond blastx | VirSorter2, VIBRANT, DeepVirFinder | geNomad이 ML 통합 최신, Diamond이 단백질 검색 표준 |
| Classify | 분류학적 할당 | MMseqs2 taxonomy + TaxonKit | Kraken2, Kaiju | MMseqs2 LCA가 바이러스 분류에 적합 |
| Diversity | 다양성 분석 | Python (scikit-bio, scipy) | R (vegan, phyloseq) | Python 파이프라인 내 통합 용이 |
| Dashboard | 동적 시각화 | Plotly + Jinja2 → HTML | R Shiny, Streamlit | 단독 HTML 파일 전달 가능 |
| Report | Word 보고서 생성 | python-docx + matplotlib | R Markdown | Python 파이프라인 통합 |

---

## 2. 기술 스택

### 2.1 파이프라인 프레임워크

| 항목 | 선택 | 이유 |
|------|------|------|
| 워크플로우 | Nextflow (DSL2) | nf-core 스타일, Docker 네이티브, HPC 확장성, 재시작 내장 |
| 컨테이너 | Docker / Singularity | 재현성 보장, HPC 환경 Singularity 호환 |
| 패키지 관리 | Conda (컨테이너 내부) | 바이오 도구 설치 편의 |
| 설정 관리 | Nextflow params + nextflow.config | nf-core 표준 |

### 2.2 분석 도구 (컨테이너별)

| 단계 | 도구 | 버전 | 컨테이너 |
|------|------|------|----------|
| QC/Trim | fastp | ≥ 0.23 | deepinvirus/qc |
| Host removal | minimap2 + samtools | ≥ 2.26, ≥ 1.18 | deepinvirus/qc |
| Assembly | MEGAHIT | ≥ 1.2.9 | deepinvirus/assembly |
| Assembly (option) | metaSPAdes | ≥ 3.15 | deepinvirus/assembly |
| Virus detection (ML) | geNomad | ≥ 1.7 | deepinvirus/detect |
| Virus detection (homology) | Diamond | ≥ 2.1 | deepinvirus/detect |
| Taxonomy | MMseqs2 | ≥ 15.6 | deepinvirus/classify |
| Taxonomy format | TaxonKit | ≥ 0.15 | deepinvirus/classify |
| Coverage | CoverM | ≥ 0.7 | deepinvirus/coverage |

### 2.3 보고서/시각화

| 항목 | 선택 | 이유 |
|------|------|------|
| 동적 대시보드 | Plotly.js + Jinja2 → standalone HTML | 서버 불필요, 파일 전달 가능 |
| 정적 시각화 | matplotlib + seaborn | Python 생태계 표준 |
| Word 보고서 | python-docx | Python 네이티브, 템플릿 기반 |
| 다양성 통계 | scikit-bio + scipy | Shannon, Simpson, Bray-Curtis, PCoA |

### 2.4 데이터베이스 (참조 DB)

| DB | 소스 | 용도 | 갱신 주기 |
|---|------|------|----------|
| NCBI RefSeq Viral | NCBI FTP | 바이러스 뉴클레오타이드 참조 | 6개월 |
| UniRef90 Viral | UniProt | 바이러스 단백질 참조 | 6개월 |
| geNomad DB | geNomad release | ML 모델 학습 DB | geNomad 업데이트 시 |
| NCBI Taxonomy | NCBI FTP | 분류학 계층 구조 | 매 실행 시 (옵션) |
| ICTV VMR | ICTV website | 최신 바이러스 분류체계 | 연 1회 |

---

## 3. 파이프라인 상세 설계

### 3.1 입력 (Input)

```
params {
    reads      = null        // FASTQ 파일 또는 디렉토리 경로
    host       = 'human'     // host genome: human, mouse, insect, none
    outdir     = './results' // 출력 디렉토리
    assembler  = 'megahit'   // megahit 또는 metaspades
    search     = 'sensitive' // fast 또는 sensitive
    skip_ml    = false       // ML 탐지 건너뛰기
    db_dir     = null        // 커스텀 DB 경로 (null이면 기본 DB 사용)
}
```

### 3.2 파이프라인 단계 (Processes)

```
1. INPUT_CHECK        : 입력 파일 검증, 샘플시트 생성
2. FASTP              : QC + adapter trimming + dedup
3. HOST_REMOVAL       : minimap2로 host read 제거
4. ASSEMBLY           : MEGAHIT 또는 metaSPAdes de novo assembly
5. GENOMAD_DETECT     : geNomad end-to-end (ML 바이러스 탐지)
6. DIAMOND_BLASTX     : Diamond blastx (단백질 상동성 검색)
7. MMSEQS_TAXONOMY    : MMseqs2 taxonomy (분류학적 할당)
8. TAXONKIT_REFORMAT  : TaxonKit (계층적 lineage 변환)
9. COVERAGE           : CoverM (read coverage 계산)
10. DIVERSITY          : Python script (alpha/beta diversity)
11. MERGE_RESULTS      : 모든 결과 통합 → bigtable
12. DASHBOARD          : Plotly → 동적 HTML 대시보드
13. REPORT             : python-docx → Word 보고서
14. MULTIQC            : MultiQC 종합 QC 리포트
```

### 3.3 출력 (Output)

```
results/
├── qc/
│   ├── fastp_reports/          # 샘플별 fastp HTML/JSON
│   └── multiqc_report.html     # 종합 QC
├── assembly/
│   ├── contigs/                # 샘플별 contig FASTA
│   └── stats/                  # 어셈블리 통계
├── detection/
│   ├── genomad/                # geNomad 결과
│   └── diamond/                # Diamond 결과
├── taxonomy/
│   ├── bigtable.tsv            # 통합 분류 테이블
│   ├── viral_taxonomy.tsv      # 바이러스만 필터
│   └── sample_counts.tsv       # 샘플 x 종 매트릭스
├── diversity/
│   ├── alpha_diversity.tsv     # Shannon, Simpson, Chao1
│   └── beta_diversity.tsv      # Bray-Curtis 거리 매트릭스
├── figures/
│   ├── heatmap.png             # 텍소노믹 히트맵
│   ├── barplot.png             # 상대 풍부도 바플롯
│   ├── pcoa.png                # PCoA 플롯
│   └── sankey.png              # Sankey 다이어그램
├── dashboard.html              # 동적 인터랙티브 대시보드
└── report.docx                 # 자동 생성 Word 보고서
```

---

## 4. 비기능 요구사항

### 4.1 성능

| 항목 | 요구사항 | 측정 방법 |
|------|----------|----------|
| 2 샘플 (7.5GB compressed) | < 4시간 | 32 threads, 64GB RAM 기준 |
| 10 샘플 (30GB compressed) | < 12시간 | 동일 환경 기준 |
| 메모리 피크 | ≤ 64GB | Nextflow 리소스 모니터링 |

### 4.2 재현성

| 항목 | 요구사항 |
|------|----------|
| 컨테이너 | 모든 도구를 Docker/Singularity 이미지로 제공 |
| 버전 고정 | 각 도구 버전을 정확히 명시 |
| 시드 | 비결정적 알고리즘에 random seed 고정 옵션 |
| 로그 | 모든 단계의 command + version + exit code 기록 |

### 4.3 확장성

| 항목 | 현재 | 목표 |
|------|------|------|
| 실행 환경 | 로컬 서버 | SLURM/PBS HPC, AWS Batch |
| 동시 샘플 | 2~10 | 100+ |
| DB 크기 | ~50GB | ~200GB (확장 가능) |

---

## 5. 모듈 교체 설계

### 5.1 원칙

각 Nextflow process는 독립적인 Docker 컨테이너에서 실행되며, 입출력 포맷만 맞으면 내부 도구를 자유롭게 교체 가능.

### 5.2 표준 중간 포맷

| 단계 간 | 포맷 | 설명 |
|---------|------|------|
| QC → Assembly | FASTQ.gz | 표준 FASTQ |
| Assembly → Detection | FASTA | contig 서열 |
| Detection → Classification | TSV (seqid, score, label) | 탐지 결과 |
| Classification → Diversity | TSV (sample, taxon, count) | 분류 카운트 |
| Diversity → Dashboard | JSON | 구조화된 분석 결과 |

### 5.3 교체 예시

```nextflow
// nextflow.config
params {
    assembler = 'megahit'  // 'megahit' 또는 'metaspades'
    detector  = 'genomad'  // 'genomad' 또는 'virsorter2'
    searcher  = 'diamond'  // 'diamond' 또는 'mmseqs2'
}
```

---

## 6. 테스트 전략

### 6.1 테스트 피라미드

| 레벨 | 도구 | 대상 | 커버리지 목표 |
|------|------|------|-------------|
| Unit | pytest | Python 스크립트 (파싱, 통계, 보고서) | ≥ 80% |
| Module | Nextflow -stub | 각 process의 입출력 포맷 검증 | 모든 process |
| Integration | Nextflow test profile | 소규모 테스트 데이터로 전체 파이프라인 | 전체 파이프라인 1회 |
| Validation | 벤치마크 데이터셋 | 알려진 바이러스 구성 데이터로 정확도 측정 | 주요 탐지/분류 |

### 6.2 테스트 데이터

```
tests/
├── data/
│   ├── reads/           # 소규모 테스트 FASTQ (< 1MB)
│   ├── expected/        # 예상 출력 파일
│   └── benchmark/       # 벤치마크 데이터셋 (optional)
├── modules/             # 모듈별 테스트
└── pipeline/            # 전체 파이프라인 테스트
```

---

## 7. DB 관리

### 7.1 DB 설치 명령

```bash
deepinvirus install-db --db-dir /path/to/databases
```

### 7.2 DB 업데이트 명령

```bash
deepinvirus update-db --db-dir /path/to/databases --component taxonomy
```

### 7.3 DB 버전 추적

```
databases/
├── VERSION.json          # 각 DB의 버전/다운로드 일시
├── viral_refseq/
├── uniref90_viral/
├── genomad_db/
├── ncbi_taxonomy/
├── ictv_vmr/
└── host_genomes/
```
