# Coding Convention & Development Guide - DeepInvirus

---

## MVP 캡슐

| # | 항목 | 내용 |
|---|------|------|
| 1 | 목표 | Raw FASTQ → 논문/보고서급 결과물 자동 출력 |
| 2 | 핵심 기능 | FEAT-1: 통합 파이프라인, FEAT-2: 대시보드, FEAT-3: 보고서 |
| 3 | 프레임워크 | Nextflow DSL2 + Python 보조 스크립트 |

---

## 1. 핵심 원칙

### 1.1 모듈식 설계 (Modular Design)
- 각 분석 단계는 독립된 Nextflow process
- 각 process는 독립된 Docker 컨테이너
- 입출력 포맷만 맞으면 내부 도구를 자유롭게 교체

### 1.2 재현성 우선 (Reproducibility First)
- 모든 도구 버전을 명시적으로 고정
- Docker/Singularity로 실행 환경 통일
- 랜덤 시드 고정 가능

### 1.3 실패 시 재시작 가능 (Resumable)
- Nextflow `-resume` 활용
- 중간 결과를 `work/` 디렉토리에 캐시
- 실패한 단계부터 재시작 가능

---

## 2. 프로젝트 구조

```
DeepInvirus/
├── main.nf                         # Nextflow 메인 파이프라인
├── nextflow.config                 # 기본 설정
├── nextflow_schema.json            # 파라미터 스키마 (nf-core 호환)
│
├── modules/                        # Nextflow 모듈 (process 단위)
│   ├── local/
│   │   ├── input_check.nf
│   │   ├── fastp.nf
│   │   ├── host_removal.nf
│   │   ├── megahit.nf
│   │   ├── metaspades.nf
│   │   ├── genomad.nf
│   │   ├── diamond.nf
│   │   ├── mmseqs_taxonomy.nf
│   │   ├── taxonkit.nf
│   │   ├── coverm.nf
│   │   ├── diversity.nf
│   │   ├── merge_results.nf
│   │   ├── dashboard.nf
│   │   └── report.nf
│   └── nf-core/                    # nf-core에서 가져온 모듈 (있다면)
│
├── subworkflows/                   # 서브워크플로우 (단계 그룹)
│   ├── preprocessing.nf            # QC + host removal
│   ├── assembly.nf                 # 어셈블리
│   ├── detection.nf                # 바이러스 탐지
│   ├── classification.nf           # 분류
│   └── reporting.nf                # 시각화 + 보고서
│
├── bin/                            # Python 보조 스크립트
│   ├── merge_results.py
│   ├── calc_diversity.py
│   ├── generate_dashboard.py
│   ├── generate_report.py
│   ├── parse_genomad.py
│   ├── parse_diamond.py
│   └── utils/
│       ├── __init__.py
│       ├── taxonomy.py
│       ├── visualization.py
│       └── docx_builder.py
│
├── assets/                         # 정적 자원
│   ├── report_template.docx        # Word 보고서 템플릿
│   ├── dashboard_template.html     # 대시보드 HTML 템플릿
│   ├── logo.png
│   └── ictv_vmr.tsv                # ICTV 분류표 (작은 파일)
│
├── conf/                           # 실행 환경별 설정
│   ├── base.config                 # 기본 리소스 설정
│   ├── docker.config               # Docker 설정
│   ├── singularity.config          # Singularity 설정
│   ├── slurm.config                # SLURM HPC 설정
│   └── test.config                 # 테스트 프로필
│
├── containers/                     # Dockerfile 모음
│   ├── qc/Dockerfile
│   ├── assembly/Dockerfile
│   ├── detect/Dockerfile
│   ├── classify/Dockerfile
│   └── reporting/Dockerfile
│
├── tests/                          # 테스트
│   ├── data/                       # 테스트 데이터
│   │   ├── reads/
│   │   └── expected/
│   ├── modules/                    # 모듈별 테스트
│   └── pipeline/                   # 전체 파이프라인 테스트
│
├── docs/
│   └── planning/                   # 기획 문서 (이 문서들)
│
└── CHANGELOG.md
```

---

## 3. 네이밍 규칙

### 3.1 Nextflow

| 대상 | 규칙 | 예시 |
|------|------|------|
| process 이름 | UPPER_SNAKE | `FASTP`, `HOST_REMOVAL`, `GENOMAD_DETECT` |
| workflow 이름 | UPPER_SNAKE | `PREPROCESSING`, `DETECTION` |
| channel 이름 | snake_case | `ch_trimmed_reads`, `ch_contigs` |
| 파라미터 | snake_case | `params.host`, `params.assembler` |
| 모듈 파일 | snake_case.nf | `fastp.nf`, `host_removal.nf` |

### 3.2 Python (bin/ 스크립트)

| 대상 | 규칙 | 예시 |
|------|------|------|
| 파일 | snake_case.py | `merge_results.py` |
| 함수 | snake_case | `parse_bigtable()`, `calc_shannon()` |
| 클래스 | PascalCase | `ReportBuilder`, `DashboardGenerator` |
| 상수 | UPPER_SNAKE | `DEFAULT_MIN_RPM`, `ICTV_RANKS` |
| 변수 | snake_case | `sample_counts`, `taxonomy_df` |

### 3.3 Docker

| 대상 | 규칙 | 예시 |
|------|------|------|
| 이미지 이름 | deepinvirus/{module} | `deepinvirus/qc:1.0.0` |
| 태그 | 시맨틱 버저닝 | `1.0.0`, `latest` |

---

## 4. Nextflow 코딩 규칙

### 4.1 Process 템플릿

```nextflow
process FASTP {
    tag "$meta.id"
    label 'process_medium'

    container 'deepinvirus/qc:1.0.0'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("*.trimmed.fastq.gz"), emit: reads
    tuple val(meta), path("*.json"),              emit: json
    tuple val(meta), path("*.html"),              emit: html

    script:
    def prefix = meta.id
    """
    fastp \\
        -i ${reads[0]} \\
        -I ${reads[1]} \\
        -o ${prefix}_R1.trimmed.fastq.gz \\
        -O ${prefix}_R2.trimmed.fastq.gz \\
        -j ${prefix}.fastp.json \\
        -h ${prefix}.fastp.html \\
        --thread ${task.cpus} \\
        ${params.fastp_args}
    """
}
```

### 4.2 리소스 라벨

| 라벨 | CPUs | Memory | Time |
|------|------|--------|------|
| `process_low` | 2 | 4 GB | 1h |
| `process_medium` | 8 | 16 GB | 4h |
| `process_high` | 16 | 32 GB | 8h |
| `process_high_memory` | 32 | 64 GB | 24h |

### 4.3 채널 네이밍

```nextflow
// 입력 채널
ch_reads           // raw reads
ch_host_genome     // host genome reference

// 중간 채널
ch_trimmed_reads   // QC 후
ch_filtered_reads  // host removal 후
ch_contigs         // assembly 후
ch_viral_hits      // detection 후

// 출력 채널
ch_bigtable        // 최종 통합 테이블
ch_dashboard       // HTML 대시보드
ch_report          // Word 보고서
```

---

## 5. Python 코딩 규칙

### 5.1 스타일

| 항목 | 규칙 |
|------|------|
| 포매터 | Black (line-length 88) |
| 린터 | Ruff |
| 타입 힌트 | 모든 함수에 필수 |
| Docstring | Google style |

### 5.2 함수 템플릿

```python
def calc_shannon_diversity(counts: pd.Series) -> float:
    """Calculate Shannon diversity index.

    Args:
        counts: Species abundance counts (non-negative integers).

    Returns:
        Shannon diversity index (H').

    Raises:
        ValueError: If counts contain negative values.
    """
    if (counts < 0).any():
        raise ValueError("Counts must be non-negative")

    proportions = counts / counts.sum()
    proportions = proportions[proportions > 0]
    return -np.sum(proportions * np.log(proportions))
```

### 5.3 의존성 관리

```
# bin/requirements.txt
pandas>=2.0
numpy>=1.24
scipy>=1.11
scikit-bio>=0.6
matplotlib>=3.8
seaborn>=0.13
plotly>=5.18
python-docx>=1.1
jinja2>=3.1
```

---

## 6. 테스트 규칙

### 6.1 Python 스크립트 테스트

```bash
# 실행
cd bin && pytest tests/ -v --cov=. --cov-report=term-missing

# 커버리지 목표: ≥ 80%
```

### 6.2 Nextflow 모듈 테스트

```bash
# 개별 모듈 테스트 (stub)
nextflow run modules/local/fastp.nf -stub -profile test

# 전체 파이프라인 테스트
nextflow run main.nf -profile test,docker
```

### 6.3 테스트 데이터

- `tests/data/reads/`: 소규모 FASTQ (< 1MB per file)
- `tests/data/expected/`: 예상 출력 파일 (bigtable 포맷 등)
- 테스트 프로필에서 경량 DB 사용

---

## 7. Git 워크플로우

### 7.1 브랜치 전략

```
main              # 안정 릴리즈
├── develop       # 개발 통합
│   ├── feature/qc-module
│   ├── feature/detection-module
│   ├── feature/dashboard
│   └── fix/fastp-params
```

### 7.2 커밋 메시지

```
<type>(<scope>): <subject>

<body>
```

| 타입 | 설명 |
|------|------|
| `feat` | 새 모듈/기능 |
| `fix` | 버그 수정 |
| `refactor` | 리팩토링 |
| `docs` | 문서 |
| `test` | 테스트 |
| `ci` | CI/CD |
| `chore` | 기타 |

```
feat(detect): add geNomad virus detection module

- geNomad end-to-end mode
- Parse geNomad output to standard TSV
- Docker container: deepinvirus/detect:1.0.0
```

---

## 8. 버전 관리

### 8.1 시맨틱 버저닝

```
MAJOR.MINOR.PATCH

1.0.0  : 첫 안정 릴리즈
1.1.0  : 새 기능 추가 (예: long-read 지원)
1.0.1  : 버그 수정
2.0.0  : 호환성 깨지는 변경 (예: 출력 포맷 변경)
```

### 8.2 CHANGELOG 관리

모든 변경사항을 CHANGELOG.md에 기록:

```markdown
## [1.0.0] - 2026-XX-XX
### Added
- Initial release
- QC module (fastp + minimap2)
- Assembly module (MEGAHIT/metaSPAdes)
- Detection module (geNomad + Diamond)
- Classification module (MMseqs2 + TaxonKit)
- Diversity analysis (alpha/beta)
- Interactive HTML dashboard
- Automated Word report generation
```
