# Workplan: Dashboard v5 + Pipeline Data Quality

> 작성: 2026-03-26 (Codex 리뷰 반영 v2)
> 기준 데이터: Hecatomb 10-sample test (`../8.hecatomb_test/`)
> bigtable: 3,624 contigs, 36,240 rows, 10 samples
> Codex 리뷰 점수: 4/10 → 수정 반영

---

## 근본 원인 분석

### 1. JS IIFE 스코프 문제
- `assets/dashboard_template.html:863` — `(function () {` IIFE
- 일부 함수만 `window.*`에 노출됨, 나머지는 IIFE에 갇혀있음

**이미 노출된 함수** (정상 작동):
`switchTab`(L909), `sortComparisonTable`(L1401), `filterSearchV2`(L1537),
`clearSearchFilters`(L1561), `sortTableV2`(L1573), `closeContigModal`(L1738),
`copyContigSequence`(L1732), `showHelp`(L1773)

**노출 안 된 함수** (inline handler에서 호출하지만 접근 불가 → 버그):
| 함수 | inline 사용 위치 | 정의 위치 |
|------|------------------|-----------|
| `resizeSankey` | L592, L646 (Apply 버튼) | L963 |
| `openFigureViewer` | L808 (Results 이미지 클릭) | L971 |
| `closeFigureViewer` | L825, L826 (오버레이 닫기) | L978 |
| `renderComparisonView` | L719 (rank 드롭다운 onchange) | L1394 |

**`openContigModal`은 inline handler가 아님** — delegated click(L1745)으로 작동하므로 노출 불필요.

### 2. 데이터 품질 (실측, Hecatomb 8.hecatomb_test 기준)
| 항목 | 실측값 | 비고 |
|------|--------|------|
| domain | 30.5% (1,106/3,624) | 값이 혼재: Viruses(559), Heunggongvirae(439), Bamfordvirae(38) 등 — **realm과 domain이 섞임** |
| family | **100%** (전부 채움, 단 Unclassified=3,435) | 실제 분류된 family는 189개 contig(5.2%) |
| genus | 12.5% (454/3,624) | TaxonKit lineage에서 genus 있는 contigs만 |
| species | 15.2% (550/3,624) | 동일 |
| target/pident | 15.2% (550/3,624) | MMseqs2 best hit 있는 contigs만 |
| taxonomy | **21.9%** (795/3,624) | geNomad detection taxonomy |
| evidence_classification | 100% | 전부 채움 |

### 3. domain 값 혼재 문제
TaxonKit `{K}` (superkingdom)이 NCBI taxonomy의 실제 superkingdom을 반환하는데:
- `Viruses` → 이것이 맞음 (NCBI superkingdom)
- `Heunggongvirae`, `Orthornavirae` 등 → 이것은 **realm** (superkingdom 아래 rank)

TaxonKit reformat의 `{K}`가 일부 taxid에서 realm을 반환하는 것이 원인.

---

## Phase 1: JS 인라인 핸들러 수정 (CRITICAL)

### T1.1: 미노출 함수 4개를 window에 노출
파일: `assets/dashboard_template.html`
IIFE 닫는 `})();` 직전에 추가:
```javascript
window.resizeSankey = resizeSankey;
window.openFigureViewer = openFigureViewer;
window.closeFigureViewer = closeFigureViewer;
window.renderComparisonView = renderComparisonView;
```

### T1.2: 슬라이더 기본값을 동적 높이와 동기화
- `renderSankey()`의 동적 높이 계산값을 슬라이더 `value`와 label에 반영
- Overview와 Taxonomy 탭 모두 적용

### T1.3: Playwright 전수 검증
- 모든 inline `onclick`/`onchange` 핸들러가 에러 없이 실행되는지 확인
- 체크리스트:
  - [ ] Apply 버튼 → Sankey 높이 변경
  - [ ] Figure 클릭 → overlay 뷰어 열림/닫힘
  - [ ] Comparison rank 드롭다운 → 테이블 갱신
  - [ ] Search contig 클릭 → 모달 열림
  - [ ] Coverage chart → coverage > 0인 contig에서 bar chart 렌더링
- 브라우저 콘솔에 `ReferenceError` 0건 확인

---

## Phase 2: Dashboard 시각화 검증 및 마무리

### T2.1: Contig coverage bar chart 검증
- coverage > 0인 contig 모달에서 Plotly bar chart 확인
- Mean Depth (bar) + RPM (marker) dual-axis
- Phase 1 수정 후 자동으로 작동할 가능성 높음

### T2.2: Search 모달 evidence classification 표시 추가
- 현재 모달에 evidence_classification/score/support_tier 미표시
- `openContigModal()` HTML에 evidence 필드 추가

### T2.3: Comparison 차트 검증
- rank 드롭다운 변경 시 테이블+차트 갱신 확인
- 10개 샘플에서 차트가 너무 넓어지지 않는지 확인

---

## Phase 3: 데이터 품질 정규화

### T3.1: domain 값 정규화 (realm→domain)
- 문제: `Heunggongvirae`(realm)이 domain에 들어감
- 원인: TaxonKit `{K}` (superkingdom)이 일부 taxid에서 realm 반환
- 해결 방안:
  - (A) `merge_results.py`에서 domain이 "Viruses"가 아닌 값을 "Viruses"로 교정
  - (B) TaxonKit format을 `{K}`에서 직접 superkingdom만 추출하도록 변경
  - (C) 별도 lookup: taxid → is_viral 판정 → domain="Viruses" 강제
- **권장: (A)** — viral metagenomics 파이프라인이므로 모든 contig의 domain은 "Viruses"

### T3.2: taxonomy 컬럼 보강 (geNomad → evidence classified)
- 현재 21.9% (795 contigs) — geNomad detection에서만
- `evidence_classified.tsv`의 `genomad_taxonomy` 컬럼을 bigtable `taxonomy`에 merge
- 795→795 (변화 없을 수 있음, 이미 같은 소스일 수 있으므로 확인 필요)

### T3.3: family "Unclassified" 개선
- family는 100% 채워져 있지만 3,435/3,624가 "Unclassified"
- geNomad taxonomy의 7번째 필드(family)를 fallback으로 사용
- `parse_taxonomy_string_to_ranks()`에서 family 추출 로직 이미 구현됨
- 현재 fallback이 `col_empty.any()`로 적용되는지 확인

---

## Phase 4: 재실행 + 검증

### T4.1: sample_map.tsv 생성
```tsv
sample	group
A13-04-182-06_TAGCTT	hecatomb
A13-12-250-06_GGCTAC	hecatomb
...
```

### T4.2: 파이프라인 재실행
```bash
./nextflow run main.nf \
  --reads 'test_input/*_R{1,2}.fastq.gz' \
  --host none \
  --db_dir /media/bio3/Database/DeepInvirus \
  --outdir /mnt/ivt-ngs1/3.university/yjs-jbu/260319_kraken2_analysis/9.hecatomb_v5 \
  -profile docker
```

### T4.3: Dashboard 수동 재생성 + Playwright 전체 탭 스크린샷
- 7개 탭 전부 스크린샷
- 모달 coverage chart 스크린샷
- 콘솔 에러 0건 확인

---

## Phase 5: Report v3 업그레이드

### T5.1: genus/species 수준 요약 테이블 추가
### T5.2: Evidence integration 4-tier 분류 요약 섹션 추가
### T5.3: Materials & Methods에 TaxonKit, evidence integration 단계 추가

---

## 실행 순서 (우선순위 = 실행 순서)

```
Phase 1 (T1.1-T1.3) → JS 핸들러 수정 + 검증 (CRITICAL)
  ↓
Phase 2 (T2.1-T2.3) → 시각화 검증 (Phase 1 후 대부분 자동 해결)
  ↓
Phase 3 (T3.1-T3.3) → 데이터 정규화 (domain/family/taxonomy)
  ↓
Phase 4 (T4.1-T4.3) → 재실행 + 최종 검증
  ↓
Phase 5 (T5.1-T5.3) → Report 업그레이드
```

| Phase | 임팩트 | 이유 |
|-------|--------|------|
| **Phase 1** | CRITICAL | 4개 함수 노출로 Apply, figure viewer, comparison 드롭다운 전부 해결 |
| **Phase 2** | HIGH | Phase 1 후 자동 해결 확인 + evidence 표시 추가 |
| **Phase 3** | HIGH | domain realm 혼재, family Unclassified 95% — 과학적 정확성 |
| **Phase 4** | MEDIUM | 수정 반영 후 재현 가능한 검증 |
| **Phase 5** | LOW | dashboard 안정화 후 |

---

## Done-When 체크리스트

- [ ] 브라우저 콘솔 `ReferenceError` 0건
- [ ] Apply 버튼으로 Sankey 높이 변경 가능
- [ ] Figure 클릭 → 오버레이 뷰어 작동
- [ ] Comparison rank 드롭다운 → genus/species 수준 테이블 표시
- [ ] Contig 모달에서 coverage > 0일 때 Plotly bar chart 표시
- [ ] domain 컬럼이 "Viruses"로 정규화 (realm 값 제거)
- [ ] Playwright 7탭 스크린샷 정상
