# Work Plan: Bug Fix + Report Framework

> Codex Review 결과 반영: Code Quality 3/10 → 7/10, Scientific Quality 5/10 → 8/10

---

## Phase A: Critical Bug Fix (Code 3/10 → 7/10)

### A1. Co-assembly merge 로직 수정 (CRITICAL)

**문제**: classification에서 taxonomy/detection이 "coassembly"라는 가짜 샘플명으로 나오고, coverage는 "GC_Tm"/"Inf_NB_Tm"으로 나와서 join이 안 됨.

**수정**:
- `merge_results.py`에서 detection/taxonomy는 sample="coassembly"로 유지
- per-sample coverage를 별도 테이블로 출력 (contig × sample matrix)
- bigtable에 per-sample coverage 컬럼 추가: `coverage_GC_Tm`, `coverage_Inf_NB_Tm`
- 또는 bigtable과 coverage_matrix를 분리

**파일**: `bin/merge_results.py`, `subworkflows/classification.nf`

---

### A2. REPORTING 채널 수정 (CRITICAL)

**문제**: `main.nf`에서 `CLASSIFICATION.out.counts`를 전달하지만 dashboard/report는 `sample_taxon_matrix.tsv`를 기대.

**수정**: `CLASSIFICATION.out.sample_matrix`를 전달

**파일**: `main.nf:220`

---

### A3. `--skip_ml` 시 스키마 불일치 (HIGH)

**문제**: skip_ml=true면 Diamond raw output(BLAST outfmt6)이 그대로 emit되는데, merge_results.py는 merged_detection 스키마를 기대.

**수정**: `detection.nf`에서 skip_ml=true일 때도 Diamond 결과를 표준 detection 포맷으로 변환

**파일**: `subworkflows/detection.nf:37`, `bin/parse_diamond.py`

---

### A4. MMseqs DB 경로 채널화 (HIGH)

**문제**: `mmseqs_taxonomy.nf`에서 `params.db_dir`로 하드코딩. DB 채널로 전달해야 함.

**수정**: main.nf에서 DB 채널을 만들어 classification subworkflow로 전달

**파일**: `modules/local/mmseqs_taxonomy.nf`, `subworkflows/classification.nf`, `main.nf`

---

### A5. MultiQC에 BBDuk + FastQC 전달 (MEDIUM)

**문제**: bbduk 모드에서 fastp_json 채널이 비어서 MultiQC에 아무것도 안 들어감.

**수정**:
- BBDuk stats + FastQC zip을 MultiQC로 전달
- FastQC 파일명 충돌 해결 (raw vs trimmed prefix)
- MultiQC `--dirs` 옵션으로 디렉토리별 구분

**파일**: `subworkflows/reporting.nf`, `subworkflows/preprocessing.nf`

---

### A6. singularity.config 완성 (MEDIUM)

**문제**: bbduk, fastqc, multiqc, prodigal 컨테이너 누락.

**수정**: docker.config와 동일한 라벨-컨테이너 매핑 추가

**파일**: `conf/singularity.config`

---

### A7. 기본 host='none' (LOW)

**문제**: 기본값 `--host human`인데 human DB가 없어서 기본 실행 불가.

**수정**: `params.host = 'none'` 기본값

**파일**: `main.nf:29`, `nextflow.config`

---

### A8. samplesheet CSV 문서 정리 (LOW)

**문제**: help에 samplesheet CSV 지원이라 쓰여있지만 `fromFilePairs`만 사용.

**수정**: help 메시지에서 CSV 언급 제거. 향후 구현 시 별도 추가.

**파일**: `main.nf:48`

---

## Phase B: Report Framework (Scientific 5/10 → 8/10)

### B1. Per-sample Coverage 기반 보고서 (CRITICAL)

**현재**: coassembly 1개 프로필로 모든 분석
**수정**: coverage_matrix (contig × sample) 기반 비교

출력 테이블:
```
contig_id | length | family | GC_Tm_depth | Inf_NB_Tm_depth | GC_Tm_breadth | Inf_NB_Tm_breadth
k127_2061 | 6062   | Parvoviridae | 15381 | 874 | 99.8% | 95.2%
```

**파일**: `bin/merge_results.py`, `bin/generate_report.py`

---

### B2. 바이러스 출처 자동 분류 (HIGH)

Family별 출처 분류 데이터베이스:

```python
VIRUS_ORIGIN = {
    # 곤충 직접 감염 (Primary insect virus)
    "Parvoviridae": "insect",      # Densovirus
    "Picornaviridae": "insect",    # Iflaviridae-like
    "Dicistroviridae": "insect",   # Cricket paralysis virus 등
    "Baculoviridae": "insect",     # Nuclear polyhedrosis virus
    "Sinhaliviridae": "insect",

    # 장내 미생물 파지 (Gut microbiome phage)
    "Caudoviricetes": "microbiome_phage",
    "Fiersviridae": "microbiome_phage",

    # 균류/진균 관련 (Fungal-associated)
    "Narnaviridae": "fungal",
    "Mitoviridae": "fungal",
    "Endornaviridae": "fungal",

    # 식물/식이 유래 (Plant/dietary)
    "Bromoviridae": "plant",
    "Virgaviridae": "plant",

    # 주의 필요 (Cautious interpretation)
    "Flaviviridae": "cautious",
    "Adintoviridae": "cautious",
}
```

보고서에 출처별 섹션 구분:
1. **핵심 곤충 바이러스** (Parvoviridae, Picornaviridae 등)
2. **장내 미생물 파지** (Caudoviricetes 등)
3. **환경/식이 유래** (식물 바이러스, 균류 바이러스)
4. **미분류/주의** (Unclassified, 단일 contig)

**파일**: `bin/virus_origin_classifier.py` (신규), `bin/generate_report.py`

---

### B3. Top Virus 자동 감지 + 부각 (HIGH)

- Per-sample coverage 기준 top 1 contig를 자동 감지
- 해당 contig의 상세 분석을 보고서 맨 앞(Executive Summary)에 배치:
  - Contig ID, length, family, best BLAST hit
  - Per-sample coverage (depth + breadth)
  - 게놈 완성도 추정 (reference 대비)
- **덴소바이러스 특화가 아닌 범용 로직**: 어떤 바이러스가 나오든 top hit를 자동 부각

**파일**: `bin/generate_report.py`

---

### B4. 과학적 표현 완화 (HIGH)

| 현재 | 수정 |
|------|------|
| "indicates host RNA degradation" | "consistent with reduced host RNA integrity" |
| "활발한 바이러스 증식을 시사" | "높은 viral nucleic acid 존재량과 일치" |
| "demonstrates" | "suggests" 또는 "is consistent with" |
| "dead sample" / "live sample" | 사용자 제공 metadata만 사용 |

**파일**: `bin/generate_report.py` 전체

---

### B5. 다양성 분석 조건부 (MEDIUM)

```python
if num_samples >= 3:
    # Alpha + Beta diversity 수행
    generate_diversity_section()
elif num_samples == 2:
    # Per-sample coverage 비교만 (diversity 무의미)
    generate_comparison_section()
else:
    # 단일 샘플: 바이러스 프로필만
    generate_profile_section()
```

**파일**: `bin/generate_report.py`, `bin/calc_diversity.py`

---

### B6. 제한사항 자동 생성 (MEDIUM)

데이터 기반 자동 생성:
- `n=2`: "본 분석은 생물학적 반복 없이 2개 샘플로 수행되어 통계적 추론에 제한이 있습니다."
- RNA-seq caveat: "RNA-seq 데이터로 DNA 바이러스(Parvoviridae 등)의 전사체를 감지하였으며, 이는 게놈 존재량이 아닌 전사 활성을 반영합니다."
- co-assembly: "Co-assembly는 게놈 복원에 유리하나, 샘플 특이적 바이러스 존재/부재 판별에 한계가 있습니다."
- host removal: "Host genome 매핑률은 샘플 상태에 영향을 받으며, 비매핑 reads가 모두 바이러스 유래는 아닙니다."

**파일**: `bin/generate_report.py`

---

### B7. QC 통합 리포트 (MEDIUM)

현재 분산된 QC 정보를 통합:
- Raw read counts (from BBDuk input)
- Adapter removal rate
- PhiX removal count
- Quality trimming rate
- Host removal rate (per-sample)
- Final read counts (per-sample)

한 테이블 + waterfall chart로 통합.

**파일**: `bin/generate_report.py`, `bin/visualize_bbduk_stats.py`

---

### B8. Methods 섹션 자동화 (MEDIUM)

실제 사용된 도구/버전/파라미터를 자동 수집:

```
Methods:
  Quality control was performed using BBDuk v39.80 (BBTools) with adapter removal
  (ref=adapters, ktrim=r, k=23, mink=11, hdist=1), PhiX removal (ref=phix174_ill.ref.fa.gz,
  k=31, hdist=1), and quality trimming (qtrim=r, trimq=20, minlength=90).

  Host reads were removed by mapping to Tenebrio molitor (GCF_963966145.1) and
  Zophobas morio (GCF_036711695.1) reference genomes using minimap2 v2.26 (-ax sr).

  Co-assembly was performed using MEGAHIT v1.2.9 (--presets meta-large, --min-contig-len 500).

  Viral sequences were identified using geNomad v1.9 (end-to-end mode) and
  Diamond blastx v2.1.24 (--ultra-sensitive, -e 1e-5) against UniRef90 viral subset
  (1,044,911 sequences).

  Taxonomic classification was performed using MMseqs2 v18.8 (easy-search, --search-type 3).
```

Nextflow trace 파일 + 컨테이너 정보에서 자동 추출.

**파일**: `bin/generate_report.py`

---

## Phase C: Dashboard Fix

### C1. Plotly.js 오프라인 (MEDIUM)

옵션 1: Plotly.js minified를 HTML에 인라인 (3.4MB 증가)
옵션 2: 정적 PNG 이미지 fallback + Plotly 버전은 optional

**추천**: 옵션 2 (정적 이미지 기본 + Plotly는 인터넷 있을 때 enhancement)

### C2. Per-sample coverage 히트맵 (HIGH)

실제 contig × sample coverage 데이터로 인터랙티브 히트맵.

### C3. 절대 경로 제거 (LOW)

모든 파일 참조를 상대 경로로.

---

## 우선순위 실행 순서

```
Round 1: A1 + A2 + A7 + A8 (빠른 critical fix)
Round 2: A3 + A4 + A5 + A6 (나머지 bug fix)
Round 3: B2 + B3 (바이러스 출처 분류 + top virus 부각)
Round 4: B1 + B4 + B6 (per-sample coverage + 표현 완화 + 제한사항)
Round 5: B5 + B7 + B8 (다양성 조건부 + QC 통합 + Methods)
Round 6: C1 + C2 + C3 (Dashboard)
Round 7: 통합 테스트 + Codex re-review
```

---

## 목표

| 항목 | 현재 | 목표 |
|------|------|------|
| Code Quality (Codex) | 3/10 | **7+/10** |
| Scientific Quality (Codex) | 5/10 | **8+/10** |
| 테스트 통과율 | ~80% | **95%+** |
| 보고서 범용성 | 덴소바이러스 특화 | **어떤 virome 프로젝트에든 적용** |
