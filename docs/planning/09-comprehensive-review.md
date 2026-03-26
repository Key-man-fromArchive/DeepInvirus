# DeepInvirus 08-workplan-bugfix-report.md 종합 리뷰

> 리뷰 수행: 2026-03-25
> 리뷰어: Codex (gpt-5.4) x2, Claude Opus 4.6 (Sonnet) x5, 총 7개 독립 리뷰 에이전트
> 대상: `docs/planning/08-workplan-bugfix-report.md` + 전체 코드베이스

---

## 종합 평점

| 항목 | Codex #1 | Codex #2 | Scientific | Bug Verify | Trend | Report | R/Doc | **합의** |
|------|----------|----------|------------|------------|-------|--------|-------|----------|
| 작업 계획 완성도 | 5/10 | 5/10 | - | - | - | 8/10 | - | **5/10** |
| Plan Accuracy | - | 7/10 | - | A2 반박됨 | - | - | - | **7/10** |
| Fix Appropriateness | - | 6/10 | - | - | - | - | - | **6/10** |
| Scientific Rigor | - | 5/10 | 3/10 | - | - | 4/10 | - | **4/10** |
| 현재 코드 품질 | 3/10 | - | 3/10 | - | - | - | - | **3/10** |
| 범용성 (Generalizability) | - | - | 2/10 | - | - | - | - | **2/10** |
| 재현성 (Methods) | - | - | 2/10 | - | - | - | - | **2/10** |

---

## Part 1: 버그 검증 결과 (A1-A8)

### 확인된 버그 (CONFIRMED)

| ID | 설명 | 심각도 | 검증 결과 | 핵심 증거 |
|----|------|--------|-----------|----------|
| **A1** | Co-assembly merge sample 이름 불일치 | CRITICAL | **CONFIRMED** | detection sample="coassembly" vs coverage sample="GC_Tm" → merge on ["seq_id","sample"] 실패 → coverage 전부 NaN |
| **A3** | `--skip_ml` 시 Diamond raw outfmt6 스키마 불일치 | CRITICAL | **CONFIRMED** | `detection.nf:37` → raw BLAST6(12col) 직통 → `merge_results.py` merged_detection 스키마(7col) 기대 |
| **A5** | BBDuk 모드에서 MultiQC 데이터 누락 | MEDIUM | **CONFIRMED** | `fastp_json=Channel.empty()` → MultiQC 빈 입력. FastQC zip도 MultiQC에 미합류 |
| **A6** | singularity.config 4개 컨테이너 누락 | CRITICAL* | **CONFIRMED** | `process_bbduk`, `process_fastqc`, `process_multiqc`, `process_prodigal` 누락 |
| **A7** | `params.host='human'` 기본값이나 human DB 미존재 | CRITICAL | **CONFIRMED** | `databases/host_genomes/`에 human 없음 → `checkIfExists:true`에서 즉시 실패 |

### 부분 확인 (PARTIALLY CONFIRMED)

| ID | 설명 | 심각도 | 검증 결과 | 비고 |
|----|------|--------|-----------|------|
| **A4** | MMseqs DB 경로 하드코딩 | MEDIUM | **PARTIALLY** | `params.db_dir` 직접 참조 (채널 미사용). null일 때 fallback "viral_refseq"가 잘못됨 |
| **A8** | samplesheet CSV 미구현 | MEDIUM | **PARTIALLY** | help에 CSV 언급하나 `fromFilePairs()`만 구현. `INPUT_CHECK` 모듈 존재하나 미사용 |

### 반박됨 (NOT CONFIRMED)

| ID | 설명 | 검증 결과 | 근거 |
|----|------|-----------|------|
| **A2** | REPORTING 채널 미스매치 (counts vs matrix) | **NOT CONFIRMED** | 주석이 혼란스럽지만 실제 데이터 흐름은 일관됨. `CLASSIFICATION.out.counts` → `reporting.nf:ch_counts` 정상 작동 |

---

## Part 2: 신규 발견 버그 (작업 계획에 누락된 항목)

### CRITICAL - 즉시 추가 필요

| ID | 설명 | 파일:라인 | 발견자 |
|----|------|-----------|--------|
| **NEW-1** | **Diamond outfmt 12컬럼 vs parse_diamond.py 13컬럼 (staxids 누락)** | `diamond.nf:22` vs `parse_diamond.py:29-32,63` | Bug Verify, Codex #2 |
| | Diamond 모듈이 12컬럼 출력하나 parser가 13컬럼(staxids 포함) 기대 → **모든 행이 skip** → detection 결과 완전 공백 | | |
| **NEW-2** | **optional metadata 파일 부재 시 MERGE_RESULTS 실행 차단** | `main.nf:184-185` | Codex #1 |
| | `Channel.fromPath(..., checkIfExists: false)` → 파일 없으면 빈 채널 → 필수 `path` 입력으로 들어가면 프로세스 미실행 | | |
| **NEW-3** | **REPORT 모듈에 coverage-dir, host-stats-dir 배선 부재** | `report.nf:22,30` vs `generate_report.py:698,715` | Codex #1 |
| | generate_report.py가 `--coverage-dir`, `--host-stats-dir`를 받아야 하나, Nextflow 모듈이 이를 전달하지 않음 → B1/B6/B7 구현해도 효과 없음 | | |
| **NEW-4** | **Diversity 입력 모델 근본적 오류: contig count 기반** | `merge_results.py:335-344` → `calc_diversity.py:181` | Codex #1, #2, Scientific |
| | `sample_taxon_matrix`가 family별 contig 개수 피벗 → assembly fragmentation에 민감 → virome diversity 지표로 부적절 | | |

### HIGH - 우선 추가 권장

| ID | 설명 | 파일:라인 |
|----|------|-----------|
| **NEW-5** | `merge_results.py`가 lineage/ICTV를 읽지만 bigtable에 미반영 | `merge_results.py:179,218,322` |
| **NEW-6** | 보고서 Methods에 "Bowtie2" 기술하나 실제는 minimap2 사용 | `generate_report.py:839` vs `host_removal.nf:1` |
| **NEW-7** | scikit-bio를 Methods에 기재하나 실제 미사용 (scipy+numpy) | `generate_report.py:1105` |
| **NEW-8** | Taxonomy도 sample="coassembly"로 coverage와 불일치 (A1 확장) | `classification.nf:37` |
| **NEW-9** | CheckV 통합 완전 누락 (2024-2025 virome 분석 필수) | 파이프라인 전체 |

---

## Part 3: VIRUS_ORIGIN 분류 체계 과학적 평가

### 심각한 오류 (3건)

1. **Picornaviridae: "insect" → 부정확**
   - ICTV 2019 이후 곤충 특이적 picorna-like virus는 **Iflaviridae**로 분리됨
   - Picornaviridae에는 Enterovirus, Rhinovirus, Hepatitis A 등 인간 병원체 포함
   - 수정: Picornaviridae 삭제 → **Iflaviridae: "insect"** 추가

2. **Caudoviricetes: class를 family처럼 분류**
   - ICTV 2022 개편으로 Myoviridae/Siphoviridae/Podoviridae 폐지
   - 수천 종을 포함하는 강(class) 수준을 단일 entry로 넣음
   - 수정: rank-aware fallback dict 분리 또는 하위 family 목록 추가

3. **"ANY virome project" 목표와 충돌**
   - 모든 분류가 곤충 virome 맥락을 전제
   - 범용 pipeline이라면 host type parameter 기반 dynamic interpretation 필요

### 누락된 주요 Family (최소 추가 필요)

| Family | 카테고리 | 중요도 | 근거 |
|--------|---------|--------|------|
| **Iflaviridae** | insect | 매우 높음 | 곤충 virome 핵심. 누락은 치명적 오류 |
| **Nodaviridae** | insect (Alphanodavirus) | 높음 | 곤충 + 어류 이중 숙주 |
| **Iridoviridae** | insect | 높음 | Invertebrate iridescent virus |
| **Nudiviridae** | insect | 높음 | 곤충 dsDNA 바이러스 |
| **Sedoreoviridae** | insect/cautious | 중간 | Cypovirus (구 Reoviridae에서 분리, ICTV 2022) |
| **Genomoviridae** | cautious | 높음 | CRESS-DNA, 환경 virome에서 빈번 |
| **Partitiviridae** | fungal_or_plant | 중간 | 진균/식물 이중 숙주 dsRNA |
| **Totiviridae** | fungal | 중간 | 진균 dsRNA |
| **Microviridae** | microbiome_phage | 중간 | ssDNA phage |

### 구조적 개선 권장

```python
# 현재 (단순 dict - 부적절)
VIRUS_ORIGIN = {"Picornaviridae": "insect"}

# 권장 (다중 host 가능성 + confidence)
VIRUS_ORIGIN = {
    "Iflaviridae": {"primary": "insect", "confidence": "high"},
    "Nodaviridae": {"primary": "insect", "secondary": "fish",
                     "confidence": "low",
                     "note": "Genus-level resolution needed"},
    "Rhabdoviridae": {"primary": "multi-host", "confidence": "none"},
}
```

---

## Part 4: 과학적 언어 및 해석 오류

### CRITICAL - 즉시 수정 필요

| 위치 | 현재 표현 | 문제점 | 권장 수정 |
|------|----------|--------|----------|
| `generate_report.py:600` | "세포 사멸로 인해 host RNA가 분해되어" | 데이터만으로 세포 사멸 단정 불가. 최소 6가지 대안 원인 존재 | "낮은 host 매핑률은 host RNA integrity 저하와 일치하며, 이는 시료 상태 등 다양한 요인에 기인할 수 있습니다" |
| `generate_report.py:634` | "높은 coverage는 활발한 바이러스 증식을 시사" | RNA-seq coverage는 전사 활성 반영, replication과 동치 아님. EVE, persistent infection 가능 | "높은 coverage는 해당 바이러스 핵산의 상대적 풍부도가 높음을 나타냅니다" |
| `generate_report.py:839` | "Bowtie2를 이용한 host RNA 제거" | **사실 오류** - 실제 pipeline은 minimap2 사용 | "minimap2를 이용한 host RNA 제거" |
| `generate_report.py:1105` | "scikit-bio (Shannon, Simpson, Bray-Curtis)" | **사실 오류** - 실제로 scipy+numpy만 사용 | "scipy + numpy" |
| `generate_report.py:628-635` | Parvoviridae 하드코딩 하이라이트 | 덴소바이러스 특화, 범용 프레임워크에 부적합 | B3의 top virus 자동 감지로 대체 |

### HIGH - B4 범위 확장 필요

| 현재 표현 | 위치 | 권장 수정 |
|----------|------|----------|
| "확인되었습니다" | line 577 | "추정되었습니다" 또는 "동정되었습니다" |
| "중간 수준의 바이러스 다양성" | line 642 | Shannon index 절대값의 기준 미정의 → "Shannon diversity index는 X로 산출되었습니다" |
| "풍부하게 존재함을 의미합니다" | line 977 | "상대적으로 높은 abundance를 시사합니다" |
| FAMILY_DESCRIPTIONS 전체 | lines 489-547 | 곤충 특이적 맥락("곤충에서의 검출은...") 제거 필요 |
| Picornaviridae 설명 | line 497-498 | CrPV, DCV는 **Dicistroviridae** 소속 (분류학적 오류) |

---

## Part 5: Diversity 분석 근본적 문제

### 입력 데이터 모델 오류 (CRITICAL)

1. **Contig count ≠ Abundance**: `build_sample_taxon_matrix()`가 family별 contig 개수로 matrix 생성. 이는 assembly fragmentation에 민감하며 생물학적 풍부도를 반영하지 않음
2. **Chao1 on RPM**: `calc_diversity.py:148`에서 RPM을 `round().astype(int)`하여 singleton/doubleton 탐지. Chao1은 정수 count 데이터 전용 → RPM 적용 시 통계적 근거 무효
3. **Co-assembly 단일 프로필**: taxonomy/detection이 모두 sample="coassembly" → 샘플 간 diversity 비교 자체가 의미 없음
4. **scipy.braycurtis import 후 미사용**: 직접 구현 사용 (불일치)

### 권장 해결 방안

```
[수정 우선순위]
1. sample_taxon_matrix를 coverage 기반 abundance matrix로 재설계
   → CoverM per-sample mean depth (RPKM 정규화) 사용
2. Chao1을 RPM context에서 제거하거나 "참고값" 경고 추가
3. B5 조건부 분석 + 입력 모델 재설계를 함께 구현
4. Jaccard distance 추가 (presence/absence 기반, sparse virome data에 더 robust)
```

---

## Part 6: 누락된 핵심 기능 (워크플랜에 추가 필요)

### 반드시 추가 (Phase A/B에 통합)

| 항목 | 중요도 | 근거 | 모든 리뷰어 합의 |
|------|--------|------|-----------------|
| **CheckV** (게놈 완성도) | CRITICAL | 2024-2025 virome 분석 사실상 필수. completeness, contamination, quality tier | 5/5 리뷰어 일치 |
| **Assembly QC 통계** | HIGH | N50, L50, total length, viral contig 비율 → 보고서에 미포함 | 4/5 리뷰어 |
| **Coverage 정규화 (RPKM/RPM)** | HIGH | raw mean depth만 사용 중. breadth도 bigtable에 추가 필요 | 5/5 리뷰어 |
| **Executive Summary** | HIGH | 보고서 첫 페이지에 핵심 발견 요약. 현재 누락 | 3/5 리뷰어 |
| **SVG/PDF 벡터 출력** | MEDIUM | 현재 PNG 300DPI만. 출판용 벡터 형식 필요 | 2/5 리뷰어 |

### 강력 권장 (Phase D 신설 고려)

| 항목 | 중요도 | 근거 |
|------|--------|------|
| vOTU clustering (95% ANI / 85% AF) | HIGH | MIUViG guidelines 표준 |
| vConTACT2/3 (viral genus clustering) | MEDIUM | novel virus 맥락화에 필수 |
| AMG 분석 (DRAM-v) | LOW-MEDIUM | phage 포함 virome에서 기대 |
| 색맹 친화적 팔레트 (Okabe-Ito) | MEDIUM | 현재 Red/Green 구분 어려움 |
| Quarto 기반 보고서 (장기) | LOW | Word/HTML/PDF 단일 소스 생성 |

---

## Part 7: 실행 순서 최적화

### 현재 계획의 문제점

1. Round 1에 A7/A8(LOW) 포함 → 치명적 버그(NEW-1~4)가 빠져 있음
2. B2/B3가 B1보다 먼저 → B1의 per-sample coverage 정비 없이는 B2/B3 신뢰도 없음
3. A2가 NOT CONFIRMED → 실행 시간 낭비

### 권장 실행 순서 (모든 리뷰어 합의 기반)

```
Round 0: NEW 버그 긴급 수정
  - NEW-1: Diamond outfmt에 staxids 추가 (또는 parse_diamond.py 수정)
  - NEW-2: optional metadata 파일 Channel.value(file(...)) 처리
  - NEW-3: REPORT 모듈에 coverage-dir/host-stats-dir 배선

Round 1: Critical Bug Fix (실행 차단 해결)
  - A1: Co-assembly merge 로직 재설계
  - A3: skip_ml Diamond schema 변환
  - A7: params.host='none' 기본값

Round 2: 데이터 모델 재설계
  - NEW-4: Abundance model → coverage 기반 matrix
  - A4 + A6: MMseqs DB 채널화 + singularity 컨테이너

Round 3: 보고서 기반 정비
  - B1: Per-sample coverage (breadth + depth + RPKM)
  - B5: 조건부 diversity (새 abundance model 기반)
  - B8: Methods 자동화 (Bowtie2→minimap2 사실 오류 수정 포함)

Round 4: 과학적 품질 강화
  - B4: 과학적 표현 완화 (확장된 목록)
  - B6: 제한사항 자동 생성
  - NEW-6,7: Methods 사실 오류 수정
  - CheckV 통합 (가능하면)

Round 5: 보고서 기능 추가
  - B2: VIRUS_ORIGIN 재설계 (Iflaviridae 추가, Picornaviridae 제거/수정)
  - B3: Top virus 자동 감지 (breadth-weighted coverage 기준)
  - B7: QC 통합 리포트
  - A5: MultiQC 수정

Round 6: Dashboard + 마무리
  - C1 + C2 + C3
  - A8: help 메시지 정리
  - 색맹 친화적 팔레트

Round 7: 통합 테스트 + Re-review
```

---

## Part 8: R 패키지 및 문서 스타일 권장

### Python 유지 + R 선택적 보완 (합의)

현재 Python(matplotlib/seaborn/python-docx) 기반을 유지하되:

| 영역 | 현재 (Python) | 개선 방안 |
|------|--------------|----------|
| 통계 분석 | scipy, numpy | R vegan (subprocess 호출) 장기 고려 |
| 시각화 | matplotlib/seaborn | SVG/PDF 출력 추가, 색맹 친화 팔레트 전환 |
| 보고서 | python-docx | 장기적으로 Quarto 검토 |
| 다양성 | 자체 구현 | scipy 정합성 확인, Chao1 RPM 경고 추가 |
| 히트맵 | seaborn | ComplexHeatmap 수준 달성을 위해 annotation 강화 |

### 핵심 R 패키지 (향후 참조용)

- **vegan**: diversity, PERMANOVA, NMDS
- **phyloseq + microViz**: 통합 virome 분석/시각화
- **ComplexHeatmap**: 다중 annotation 히트맵
- **microshades**: 계층적 분류군 색상 체계
- **ggtree/ggtreeExtra**: 바이러스 계통수

### 색상 팔레트 개선

```python
# 현재 (적녹색맹 문제 있음)
DEEPINVIRUS_PALETTE = ["#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", ...]

# 권장 (Okabe-Ito 기반 색맹 친화적)
DEEPINVIRUS_PALETTE_V2 = [
    "#0072B2", "#E69F00", "#009E73", "#CC79A7",
    "#56B4E9", "#D55E00", "#F0E442", "#999999"
]
```

---

## Part 9: 목표 달성 가능성 평가

| 목표 | 현재 | 워크플랜만 | 워크플랜 + 이 리뷰 반영 |
|------|------|-----------|----------------------|
| Code Quality | 3/10 | 6/10 (NEW 버그 미반영) | **7+/10** |
| Scientific Quality | 3/10 | 6/10 (VIRUS_ORIGIN 오류, 사실 오류 존재) | **8/10** |
| 테스트 통과율 | ~80% | ~90% | **95%+** |
| 보고서 범용성 | 2/10 | 5/10 (곤충 특화 잔존) | **8/10** |

**결론**: 현재 워크플랜(08)만으로는 목표(Code 7+, Scientific 8+) 달성이 어렵습니다. 이 리뷰에서 발견된 NEW 버그 4건, 과학적 오류 5건, VIRUS_ORIGIN 재설계, CheckV 통합을 반영해야 목표에 도달할 수 있습니다.

---

## 참고 문헌

- Camargo AP et al. (2024) geNomad. *Nature Biotechnology* 42:1303-1312.
- Nayfach S et al. (2021) CheckV. *Nature Biotechnology* 39:578-585.
- Turner D et al. (2023) ICTV 2022 taxonomy update. *Archives of Virology* 168:263.
- Valles SM et al. (2017) ICTV: Iflaviridae. *Journal of General Virology* 98:527-528.
- Bin Jang H et al. (2019) vConTACT2. *Nature Biotechnology* 37:632-639.
- Roux S et al. (2021) MIUViG. *Nature Biotechnology* 37:29-37.
- Wong B (2011) Color blindness. *Nature Methods* 8:441.
