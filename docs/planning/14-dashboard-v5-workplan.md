# Workplan: Dashboard v5 + Pipeline Data Quality

> 작성: 2026-03-26
> 기준 데이터: Hecatomb 10-sample test (8.hecatomb_test/)
> 현재 bigtable: 3,624 contigs, 36,240 rows, 10 samples

---

## 근본 원인 분석

### JS 스코프 문제 (모든 인터랙션 버그의 원인)
- `assets/dashboard_template.html` line 863: `(function () {` IIFE
- 모든 함수가 IIFE 내부에서 정의됨 → 전역 스코프에 노출 안 됨
- HTML `onclick="resizeSankey(...)"`, `onclick="openFigureViewer(...)"` 등이 전부 작동 불가
- **해결**: IIFE 내부에서 `window.resizeSankey = resizeSankey;` 등으로 명시 노출

### 데이터 품질 (bigtable fill rates)
| rank | fill rate | 원인 |
|------|-----------|------|
| domain | 30.5% | TaxonKit `{K}` 적용됨, MMseqs2 hit 없는 contigs는 빈값 |
| family | 5.2% | NCBI taxonomy에서 family rank 미할당 서열 다수 |
| genus | 12.5% | TaxonKit lineage에서 genus 채워진 contigs만 |
| species | 15.2% | 동일 |
| target/pident | 15.2% | MMseqs2 hit가 있는 contigs만 |

---

## Phase 1: Dashboard JS 스코프 수정 (CRITICAL)

**이것만 고치면 Apply 버튼, 모달, figure viewer 전부 작동함**

### T1.1: IIFE 내부 함수를 window에 노출
- 파일: `assets/dashboard_template.html`
- 위치: IIFE 끝부분 (closing `})();` 직전)
- 추가:
```javascript
// Expose functions for inline onclick handlers
window.resizeSankey = resizeSankey;
window.openFigureViewer = openFigureViewer;
window.closeFigureViewer = closeFigureViewer;
window.openContigModal = openContigModal;
window.closeContigModal = closeContigModal;
window.switchTab = switchTab;
window.sortComparison = sortComparison;
```

### T1.2: 검증
- Playwright로 Apply 버튼 클릭 → Sankey 높이 변경 확인
- Playwright로 contig 클릭 → 모달 열림 + coverage chart 확인
- Playwright로 figure 클릭 → overlay 뷰어 확인

---

## Phase 2: Dashboard 시각화 개선

### T2.1: Contig coverage bar chart 검증
- 모달의 `#contig-coverage-chart`에 Plotly bar chart 렌더링 확인
- coverage > 0인 contig에서 bar chart 표시 확인
- Mean Depth (bar) + RPM (marker) dual-axis

### T2.2: Comparison rank 선택기 Apply 연동
- 현재: `onchange="renderComparisonView()"` — 자동 갱신
- 확인: rank 변경 시 테이블+차트 정상 갱신

### T2.3: Search 모달 정보 완성
- Best Hit: bigtable `target` 컬럼 → 이미 구현
- pident: bigtable `pident` 컬럼 → 이미 구현
- GC Content: `contig_sequences`에서 계산 → 이미 구현
- Evidence Classification: `evidence_classification` → 모달에 표시 추가

### T2.4: Sankey 높이 적정값 설정
- 기본값을 노드 수 기반으로 동적 계산
- 슬라이더 기본값을 동적 높이로 설정

---

## Phase 3: 파이프라인 데이터 품질 개선

### T3.1: domain fill rate 개선
- 현재 30.5% — MMseqs2 hit 없는 contigs는 domain 비어있음
- 해결: geNomad taxonomy에서 domain 추출 (geNomad는 "Viruses;..." 형태로 항상 domain 포함)
- 위치: `bin/merge_results.py` fallback logic

### T3.2: family fill rate 개선
- 현재 5.2% — NCBI taxonomy tree에서 family rank가 할당 안 된 서열 많음
- 해결: geNomad taxonomy의 7번째 필드가 family (세미콜론 구분)
- 위치: `bin/merge_results.py` `parse_taxonomy_string_to_ranks()` 이미 구현됨
- 문제: 현재 fallback이 `col_empty.any()`로 변경되었지만 geNomad taxonomy 자체가 bigtable의 `taxonomy` 컬럼에 있어야 함

### T3.3: geNomad taxonomy → bigtable `taxonomy` 컬럼 보강
- 현재: bigtable `taxonomy` 컬럼이 geNomad detection 결과에서만 채워짐 (49개)
- 해결: evidence_classified.tsv의 `genomad_taxonomy` 컬럼을 bigtable에 merge
- 위치: `bin/merge_results.py` evidence classified merge 로직 확장

---

## Phase 4: test_input 프로젝트 포함 + 테스트 파이프라인

### T4.1: test_input 디렉토리 git 추가
- `test_input/*.fastq.gz` (94MB, 10 samples) → git LFS 또는 직접 포함
- `.gitignore`에서 `test_input/` 제거
- `test_input/sample_map.tsv` 생성 (sample→group 매핑)

### T4.2: 테스트 실행 스크립트
```bash
# test_run.sh
./nextflow run main.nf \
  --reads 'test_input/*_R{1,2}.fastq.gz' \
  --host none \
  --db_dir /media/bio3/Database/DeepInvirus \
  --outdir ../test_output \
  -profile docker
```

### T4.3: 파이프라인 재실행 + dashboard 재생성
- Phase 1-3 수정 후 Hecatomb 데이터로 재실행
- 결과 검증 (Playwright 전체 탭 스크린샷)

---

## Phase 5: Report v3 업그레이드

### T5.1: generate_report.py에 genus/species 테이블 추가
### T5.2: Evidence integration 요약 섹션 추가
### T5.3: Materials & Methods에 TaxonKit, evidence integration 단계 추가

---

## 실행 순서

```
Phase 1 (T1.1-T1.2) → JS 스코프 수정 (30분)
  ↓
Phase 2 (T2.1-T2.4) → 시각화 검증/개선 (1시간)
  ↓
Phase 3 (T3.1-T3.3) → 데이터 품질 개선 (1시간)
  ↓
Phase 4 (T4.1-T4.3) → test_input + 재실행 (30분)
  ↓
Phase 5 (T5.1-T5.3) → Report 업그레이드 (1시간)
```

## 우선순위

| Phase | 임팩트 | 이유 |
|-------|--------|------|
| **Phase 1** | CRITICAL | 이것만 고치면 Apply, 모달, figure viewer 전부 작동 |
| **Phase 3** | HIGH | 데이터가 좋아야 시각화가 의미 있음 |
| **Phase 2** | MEDIUM | Phase 1 후 자동으로 대부분 해결 |
| **Phase 4** | MEDIUM | 재현 가능한 테스트 환경 |
| **Phase 5** | LOW | 보고서는 dashboard 이후 |
