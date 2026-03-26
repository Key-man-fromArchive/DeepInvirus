# Work Plan v2: Universal Virome Report Framework

> 09-comprehensive-review.md 반영 (7개 리뷰 에이전트 합의)
> Code Quality 3/10 → 8/10, Scientific Quality 3/10 → 9/10
> 핵심 원칙: **어떤 virome 프로젝트에든 적용 가능한 human-researcher-grade 자동 보고서**

---

## Phase 0: 실행 차단 버그 긴급 수정 (Day 1)

> 이 버그들이 해결되지 않으면 파이프라인 자체가 실행 불가

### 0.1 Diamond outfmt staxids 누락 (CRITICAL)

**문제**: `diamond.nf:22`가 12컬럼 출력, `parse_diamond.py:29`가 13컬럼(staxids) 기대 → **모든 detection 결과 공백**

**수정**:
```groovy
// diamond.nf - outfmt에 staxids 추가
--outfmt 6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore staxids
```
또는 `parse_diamond.py`를 12컬럼 호환으로 수정 (staxids optional)

**파일**: `modules/local/diamond.nf:22`, `bin/parse_diamond.py:29-32,63`

---

### 0.2 Optional metadata 파일 부재 시 실행 차단 (CRITICAL)

**문제**: `sample_map.tsv`, `ictv_vmr.tsv` 없으면 `Channel.fromPath(..., checkIfExists: false)` → 빈 채널 → `MERGE_RESULTS` 미실행

**수정**:
```groovy
// main.nf - Channel.value + file() 또는 빈 placeholder 생성
ch_sample_map = params.sample_map
    ? Channel.value(file(params.sample_map))
    : Channel.value(file("${projectDir}/assets/empty_sample_map.tsv"))
```

**파일**: `main.nf:184-185`, `assets/empty_sample_map.tsv` (신규)

---

### 0.3 params.host='none' 기본값 (CRITICAL)

**문제**: 기본값 `human`이나 human DB 없음 → 즉시 실패

**수정**: `params.host = 'none'`

**파일**: `main.nf:26`, `nextflow.config`

---

### 0.4 REPORT 모듈 입력 배선 추가 (CRITICAL)

**문제**: `generate_report.py`가 `--coverage-dir`, `--host-stats-dir`를 받아야 하나 Nextflow 모듈이 미전달 → per-sample coverage 보고 불가

**수정**: `report.nf`에 coverage 채널, host_stats 채널 추가. `reporting.nf`에서 수집하여 전달.

**파일**: `modules/local/report.nf`, `subworkflows/reporting.nf`, `main.nf`

---

## Phase A: 데이터 모델 재설계 (Day 2-3)

> merge/diversity/report의 근본적 스키마 문제 해결

### A1. Co-assembly merge 로직 전면 재설계 (CRITICAL)

**문제**: detection/taxonomy sample="coassembly" vs coverage sample="GC_Tm" → merge 실패

**수정 전략**:
```
bigtable 구조 변경:
  - detection/taxonomy: contig 수준 (sample 컬럼 없이)
  - coverage: contig × sample matrix (별도)
  - bigtable: contig 정보 + per-sample coverage wide format

출력:
  bigtable.tsv:
    seq_id | length | family | detection_method | detection_score |
    target | pident | evalue |
    GC_Tm_depth | GC_Tm_breadth | Inf_NB_Tm_depth | Inf_NB_Tm_breadth

  coverage_matrix.tsv:
    seq_id | sample | mean_depth | trimmed_mean | breadth | rpkm
```

**파일**: `bin/merge_results.py`, `subworkflows/classification.nf`

---

### A2. Abundance model 재설계: Coverage 기반 (CRITICAL)

**문제**: `sample_taxon_matrix`가 contig count 피벗 → assembly fragmentation에 민감 → diversity 무의미

**수정**:
```python
# sample_taxon_matrix = family별 RPKM 합산 (contig count 아님)
def build_sample_taxon_matrix(bigtable, coverage_matrix):
    """Family × Sample RPKM abundance matrix."""
    # coverage_matrix에서 per-sample RPKM 산출
    # family별 RPKM 합산 → pivot
    # 결과: taxon | sample_1_rpkm | sample_2_rpkm | ...
```

Diversity 입력이 coverage-based abundance가 되어야 Shannon/Simpson/Bray-Curtis가 의미를 가짐.

**파일**: `bin/merge_results.py`, `bin/calc_diversity.py`

---

### A3. skip_ml Diamond schema 변환 (CRITICAL)

**문제**: skip_ml=true면 raw BLAST6가 직통 → merge 실패

**수정**: `detection.nf`에서 skip_ml=true일 때도 `parse_diamond.py`를 거쳐 표준 detection format으로 변환

**파일**: `subworkflows/detection.nf:37`, `bin/parse_diamond.py`

---

### A4. Breadth of coverage 추가 (HIGH)

**문제**: CoverM이 breadth를 산출하나 `merge_results.py`가 mean depth만 사용

**수정**: bigtable에 `breadth` 컬럼 추가. breadth >= 70% 기준으로 "confident detection" flag.

```python
# Viral detection confidence tiers
if breadth >= 70 and mean_depth >= 10:
    confidence = "high"
elif breadth >= 30 and mean_depth >= 1:
    confidence = "medium"
else:
    confidence = "low"
```

**파일**: `bin/merge_results.py`

---

### A5. MMseqs DB 채널화 + singularity 완성 (MEDIUM)

- `mmseqs_taxonomy.nf`에서 params 직접참조 → DB 채널로 전달
- singularity.config에 bbduk, fastqc, multiqc, prodigal 컨테이너 추가

**파일**: `modules/local/mmseqs_taxonomy.nf`, `conf/singularity.config`

---

### A6. MultiQC BBDuk + FastQC 통합 (MEDIUM)

- BBDuk stats + FastQC zip을 MultiQC 입력에 합류
- `reporting.nf:46-50` 수정

**파일**: `subworkflows/reporting.nf`, `subworkflows/preprocessing.nf`

---

## Phase B: Report Framework - Human Researcher Grade (Day 4-7)

> 목표: Nature Microbiology / mSystems / Microbiome 저널 수준의 자동 보고서

### B1. 보고서 구조 재설계

```
[Word Report 구조]

0. Executive Summary (1페이지)
   - 핵심 발견 3줄 요약
   - Top virus 하이라이트 (자동 감지)
   - 주요 수치 (contig 수, family 수, 샘플별 특이 사항)

1. Methods (자동 생성)
   - 실제 사용 도구/버전/파라미터 (Nextflow trace에서 추출)
   - Reference DB 버전/날짜
   - Pipeline DAG 이미지

2. QC Results
   - Read flow waterfall (raw → adapter → host → final)
   - BBDuk/fastp 통계 테이블
   - Host mapping 비교 (기술적 서술, 인과 해석 금지)

3. Assembly Statistics (신규)
   - N50, total assembled length, # contigs
   - Viral contig 비율 (geNomad detected / total)
   - Length distribution histogram

4. Virus Detection
   - Detection method summary (geNomad + Diamond)
   - Family composition (stacked barplot, NOT pie chart)
   - Detection confidence tiers (breadth-based)

5. Per-sample Coverage Analysis
   - Contig × Sample heatmap (log10 RPKM)
   - Top contigs by breadth-weighted coverage
   - Cross-contamination flags (breadth < 30% + depth ratio < 0.01)

6. Taxonomic Analysis
   - Virus origin context (dynamic, host-type dependent)
   - Family descriptions (범용, 곤충 특화 표현 제거)
   - ICTV taxonomy alignment

7. Diversity Analysis (조건부)
   - n >= 3: Full alpha + beta + PCoA
   - n = 2: Fold-change comparison + Jaccard similarity
   - n = 1: Profile only

8. Conclusions (자동 생성, hedged)
   - 모든 표현에 scientific hedging 적용
   - 다중 가설 제시 (단일 원인 단정 금지)

9. Limitations (자동 생성)
   - n 기반, data type 기반, method 기반

Appendix
   - 전체 viral contig 목록
   - Software versions
   - Parameter settings
```

**파일**: `bin/generate_report.py` (전면 재작성)

---

### B2. Methods 자동 생성 엔진 (HIGH)

**원칙**: 하드코딩 금지. Nextflow metadata에서 동적 추출.

```python
class MethodsGenerator:
    """Nextflow trace + process config에서 Methods 텍스트 자동 생성."""

    def __init__(self, trace_file, nextflow_config):
        self.tools = self._parse_trace(trace_file)
        self.params = self._parse_config(nextflow_config)

    def generate(self) -> str:
        sections = [
            self._qc_methods(),        # BBDuk OR fastp (실제 사용된 것)
            self._host_methods(),       # minimap2 (NOT Bowtie2)
            self._assembly_methods(),   # MEGAHIT OR metaSPAdes
            self._detection_methods(),  # geNomad + Diamond
            self._taxonomy_methods(),   # MMseqs2 + TaxonKit
            self._coverage_methods(),   # CoverM
            self._diversity_methods(),  # scipy (NOT scikit-bio)
        ]
        return "\n\n".join(sections)
```

**파일**: `bin/methods_generator.py` (신규), `bin/generate_report.py`

---

### B3. 과학적 해석 엔진: Hedged & Multi-hypothesis (HIGH)

**원칙**:
1. 단일 원인 단정 금지 → 다중 가설 제시
2. "demonstrates" → "suggests" / "is consistent with"
3. Coverage → abundance (NOT replication)
4. RNA-seq ↔ DNA virus caveat 자동 삽입
5. 사용자 metadata가 있을 때만 생물학적 해석

```python
class ScientificInterpreter:
    """Data-driven, hedged scientific interpretation generator."""

    HEDGING_RULES = {
        "확인되었습니다": "추정되었습니다",
        "시사합니다": "일치합니다",
        "의미합니다": "반영할 수 있습니다",
        "활발한 바이러스 증식": "높은 바이러스 핵산 풍부도",
        "세포 사멸": "host RNA integrity 저하",
    }

    def interpret_host_mapping(self, host_stats, metadata=None):
        """Host mapping rate 해석 - 다중 가설 제시."""
        if metadata and "sample_condition" in metadata:
            # 사용자 metadata 기반 해석 가능
            ...
        else:
            return (
                f"Host 매핑률에서 샘플 간 차이가 관찰되었습니다. "
                f"이러한 차이는 시료 상태 (RNA integrity), "
                f"시퀀싱 라이브러리 품질, reference genome 완전성 등 "
                f"다양한 요인에 기인할 수 있으며, "
                f"시료에 대한 추가 정보 없이 특정 원인을 단정하기 어렵습니다."
            )

    def interpret_coverage(self, contig_row, data_type="rna-seq"):
        """Coverage 해석 - DNA/RNA virus 구분."""
        if data_type == "rna-seq" and contig_row["genome_type"] == "DNA":
            caveat = ("RNA-seq 데이터에서 DNA 바이러스의 검출은 "
                     "viral transcript를 반영하며, 게놈 존재량과는 구별됩니다.")
        else:
            caveat = ""
        ...
```

**파일**: `bin/scientific_interpreter.py` (신규)

---

### B4. VIRUS_ORIGIN 재설계: Evidence-tier System (HIGH)

```python
# bin/virus_origin_db.py (신규)

VIRUS_ORIGIN = {
    # --- 곤충 직접 감염 (High confidence) ---
    "Iflaviridae":        {"origin": "insect", "confidence": "high",
                           "note": "Iflavirus - 곤충 picorna-like virus"},
    "Dicistroviridae":    {"origin": "insect", "confidence": "high"},
    "Baculoviridae":      {"origin": "insect", "confidence": "high"},
    "Sinhaliviridae":     {"origin": "insect", "confidence": "high"},
    "Nudiviridae":        {"origin": "insect", "confidence": "high"},
    "Iridoviridae":       {"origin": "insect", "confidence": "medium",
                           "note": "일부 수생 무척추동물도 감염"},
    "Parvoviridae":       {"origin": "insect", "confidence": "medium",
                           "note": "Densovirinae만 곤충. Parvovirinae는 척추동물"},

    # --- 다중 숙주 (Low confidence at family level) ---
    "Nodaviridae":        {"origin": "multi-host", "confidence": "low",
                           "note": "Alphanodavirus=곤충, Betanodavirus=어류. Genus 수준 확인 필요"},
    "Sedoreoviridae":     {"origin": "multi-host", "confidence": "low",
                           "note": "Cypovirus=곤충, Orbivirus=척추동물"},
    "Rhabdoviridae":      {"origin": "multi-host", "confidence": "none",
                           "note": "곤충/식물/척추동물 모두 감염. Family 수준 분류 불가"},

    # --- 장내 미생물 파지 ---
    "Microviridae":       {"origin": "microbiome_phage", "confidence": "high"},
    "Fiersviridae":       {"origin": "microbiome_phage", "confidence": "medium"},

    # --- 진균 관련 ---
    "Narnaviridae":       {"origin": "fungal", "confidence": "medium"},
    "Mitoviridae":        {"origin": "fungal", "confidence": "medium"},
    "Endornaviridae":     {"origin": "fungal", "confidence": "medium"},
    "Partitiviridae":     {"origin": "fungal_or_plant", "confidence": "low"},
    "Totiviridae":        {"origin": "fungal", "confidence": "medium"},

    # --- 식물/식이 유래 ---
    "Bromoviridae":       {"origin": "plant", "confidence": "medium"},
    "Virgaviridae":       {"origin": "plant", "confidence": "medium"},
    "Tymoviridae":        {"origin": "plant", "confidence": "medium"},

    # --- 주의 필요 ---
    "Flaviviridae":       {"origin": "cautious", "confidence": "low",
                           "note": "ISF는 곤충 특이적이나, 병원성 flavivirus도 포함"},
    "Genomoviridae":      {"origin": "cautious", "confidence": "low",
                           "note": "CRESS-DNA. 환경 유래 가능"},
    "Adintoviridae":      {"origin": "cautious", "confidence": "low",
                           "note": "EVE 가능성. 숙주 게놈 유래일 수 있음"},
}

# Class-level fallback (family 미분류 시)
VIRUS_ORIGIN_CLASS_FALLBACK = {
    "Caudoviricetes": {"origin": "microbiome_phage", "confidence": "low",
                       "note": "강(class) 수준. 하위 family 미분류"},
}

# Picornaviridae는 의도적으로 제외
# (곤충 특이적 구성원은 Iflaviridae/Dicistroviridae로 분리됨)
```

보고서에서 confidence="low" 이하는 경고 표시 포함.

**파일**: `bin/virus_origin_db.py` (신규), `bin/generate_report.py`

---

### B5. Top Virus 자동 감지: Breadth-weighted (HIGH)

```python
def detect_top_virus(bigtable, coverage_matrix):
    """Breadth-weighted coverage 기준 top virus 자동 감지."""
    # Score = mean_depth × (breadth/100) × log10(contig_length)
    bigtable["top_score"] = (
        bigtable["mean_depth"]
        * (bigtable["breadth"] / 100)
        * np.log10(bigtable["length"])
    )
    top = bigtable.nlargest(1, "top_score").iloc[0]
    return {
        "contig": top["seq_id"],
        "family": top["family"],
        "length": top["length"],
        "best_hit": top["target"],
        "per_sample_coverage": ...,
        "confidence": top["detection_confidence"],
    }
```

Executive Summary에 배치. 덴소바이러스 하드코딩 제거.

**파일**: `bin/generate_report.py`

---

### B6. Diversity 조건부 실행 + 개선 (MEDIUM)

```python
def generate_diversity_section(matrix, n_samples):
    if n_samples >= 3:
        # Full: Shannon, Simpson, Chao1(raw count만), Pielou
        # Beta: Bray-Curtis + Jaccard (presence/absence)
        # Ordination: PCoA + NMDS (stress < 0.2 확인)
        ...
    elif n_samples == 2:
        # Comparison only:
        # - Log2 fold-change (sample1 vs sample2)
        # - Jaccard similarity (shared/unique contigs)
        # - Per-sample coverage 비교표
        # - "통계적 검정은 수행하지 않음" 명시
        ...
    else:
        # Profile only: 단일 샘플 바이러스 프로필
        ...
```

Chao1: RPM 데이터 시 비활성화 또는 "참고값" 경고.

**파일**: `bin/calc_diversity.py`, `bin/generate_report.py`

---

### B7. Limitations 자동 생성 엔진 (MEDIUM)

```python
def generate_limitations(metadata):
    limitations = []

    # Sample size
    if metadata["n_samples"] < 3:
        limitations.append(
            f"본 분석은 {metadata['n_samples']}개 샘플로 수행되어 "
            "통계적 추론 및 다양성 비교에 제한이 있습니다."
        )

    # RNA-seq + DNA virus
    if metadata["data_type"] == "rna-seq" and metadata["has_dna_virus"]:
        limitations.append(
            "RNA-seq 데이터에서 DNA 바이러스의 검출은 viral transcript를 "
            "포착한 것이며, 게놈 존재량(viral load)과는 구별됩니다."
        )

    # Co-assembly
    if metadata["assembly_strategy"] == "coassembly":
        limitations.append(
            "Co-assembly는 게놈 복원에 유리하나, 샘플 특이적 바이러스 "
            "존재/부재 판별에 한계가 있습니다. Per-sample read mapping으로 "
            "이를 보완하였으나, chimeric contig 가능성을 배제할 수 없습니다."
        )

    # Reference DB
    limitations.append(
        "분류학적 할당은 참조 데이터베이스의 완전성에 의존하며, "
        "바이러스 dark matter(미등록 바이러스)의 비율이 높을 수 있습니다."
    )

    # Assembly-based only
    limitations.append(
        "Assembly 기반 접근은 충분한 coverage가 있는 바이러스만 복원 가능하며, "
        "저풍부도(low-abundance) 바이러스를 놓칠 수 있습니다."
    )

    return limitations
```

**파일**: `bin/generate_report.py`

---

### B8. QC Waterfall + Assembly Stats 통합 (MEDIUM)

하나의 통합 QC 테이블:

```
Sample | Raw Reads | After Adapter | After PhiX | After Host | Final |
       |           | (-X.X%)       | (-X reads) | (-XX.X%)   |       |
```

Assembly stats:
```
Metric              | Value
Total contigs       | 12,345
N50                 | 4,521 bp
Longest contig      | 15,382 bp
Viral contigs       | 87 (0.7%)
Total assembled bp  | 23.4 Mbp
```

**파일**: `bin/generate_report.py`

---

### B9. FAMILY_DESCRIPTIONS 범용화 (MEDIUM)

- 모든 곤충 특이적 표현 제거 ("곤충에서의 검출은...", "곤충 장내...")
- Host-type parameter 기반 동적 문맥 생성:

```python
def get_family_description(family, host_type="general"):
    base = FAMILY_BASE_DESCRIPTIONS[family]  # 범용 설명
    if host_type in FAMILY_CONTEXT:
        context = FAMILY_CONTEXT[host_type].get(family, "")
        return f"{base} {context}"
    return base
```

- Picornaviridae 설명에서 CrPV/DCV 제거 (Dicistroviridae 소속)

**파일**: `bin/generate_report.py`

---

## Phase C: 시각화 품질 강화 (Day 8)

### C1. 색맹 친화적 팔레트 전환

```python
# Okabe-Ito 기반
DEEPINVIRUS_PALETTE = [
    "#0072B2", "#E69F00", "#009E73", "#CC79A7",
    "#56B4E9", "#D55E00", "#F0E442", "#999999"
]
```

### C2. Pie chart → Stacked barplot

학술 논문에서 pie chart는 기피됨. `_plot_family_composition()`을 horizontal stacked barplot으로 교체.

### C3. SVG/PDF 벡터 출력 추가

```python
fig.savefig(output_path, dpi=300, bbox_inches="tight")
fig.savefig(output_path.with_suffix(".svg"), bbox_inches="tight")  # 벡터
```

### C4. Dashboard Plotly.js 오프라인 (정적 PNG fallback)

### C5. Coverage 히트맵 annotation 강화

detection confidence tier (색상 바), family 정보, breadth 표시를 히트맵에 추가.

---

## Phase D: CheckV 통합 (선택적, Day 9)

> 2024-2025 virome 분석 사실상 필수. 가능하면 포함.

### D1. CheckV 프로세스 추가

```groovy
process CHECKV {
    input: tuple val(meta), path(viral_contigs)
    output: tuple val(meta), path("quality_summary.tsv"), emit: quality
    script: "checkv end_to_end ${viral_contigs} checkv_out -d ${checkv_db}"
}
```

### D2. bigtable에 CheckV 컬럼 추가

```
checkv_quality | completeness | contamination | provirus
high-quality   | 95.2%        | 0.0%          | No
```

### D3. 보고서에 Quality Tier 분포 차트

Complete / High-quality / Medium-quality / Low-quality / Not-determined 분포.

---

## 실행 순서 요약

```
Phase 0 (Day 1): 실행 차단 긴급 수정
  0.1 Diamond staxids + 0.2 Optional channel + 0.3 host default + 0.4 Report wiring

Phase A (Day 2-3): 데이터 모델 재설계
  A1 Merge 재설계 → A2 Abundance model → A3 skip_ml → A4 Breadth → A5 DB/container → A6 MultiQC

Phase B (Day 4-7): Report Framework
  B1 구조 재설계 → B2 Methods 엔진 → B3 해석 엔진 → B4 VIRUS_ORIGIN →
  B5 Top virus → B6 Diversity 조건부 → B7 Limitations → B8 QC 통합 → B9 Family 범용화

Phase C (Day 8): 시각화
  C1 팔레트 → C2 Barplot → C3 SVG → C4 Dashboard → C5 Heatmap

Phase D (Day 9, 선택): CheckV 통합
  D1 프로세스 → D2 bigtable → D3 보고서

Day 10: 통합 테스트 + Re-review
```

---

## 목표

| 항목 | 현재 | 목표 | 달성 방법 |
|------|------|------|----------|
| Code Quality | 3/10 | **8+/10** | Phase 0 + A |
| Scientific Quality | 3/10 | **9/10** | B3 + B4 + B7 + B9 |
| 테스트 통과율 | ~80% | **95%+** | Phase 0 긴급 수정 |
| 보고서 범용성 | 2/10 | **9/10** | B1-B9 전체 |
| 재현성 (Methods) | 2/10 | **9/10** | B2 Methods 엔진 |
| 출판 적합성 | 4/10 | **8/10** | C1-C5 + B1 구조 |
