# DeepInvirus Dashboard / Report Upgrade Plan

> 작성일: 2026-03-25
> 대상: `dashboard.html`, `report.docx`, `figures/`, `bigtable.tsv`, `sample_taxon_matrix.tsv`, `coverage/*_coverage.tsv`, Nextflow reporting pipeline
> 목표: 사용자 피드백을 제품 수준 요구사항으로 확장하여, `report.docx`와 `dashboard.html`이 동일한 분석 진실원천(single source of truth)을 공유하도록 재설계

---

## 0. Executive Summary

현재 구조는 `bigtable.tsv`와 `sample_taxon_matrix.tsv`를 중심으로 대시보드와 리포트를 생성하지만, 데이터 모델이 여전히 "contig summary + sample aggregate" 수준에 머물러 있어 다음 요구를 만족하지 못한다.

- 샘플별 taxonomic drill-down
- species-level interactive taxonomy exploration
- contig sequence / ORF / best-hit / coverage profile inspection
- publication-ready figure gallery
- report와 dashboard 간 1:1 분석 대응

v2의 핵심 원칙은 다음 5가지다.

1. `report.docx`와 `dashboard.html`이 동일한 `analysis_bundle` 데이터를 소비해야 한다.
2. taxonomy view는 family 중심 요약에서 contig/species 중심 exploration으로 올라가야 한다.
3. coverage는 "contig x sample heatmap"에서 끝나면 안 되고, `per-base depth profile`까지 내려가야 한다.
4. 모든 정적 figure는 interactive counterpart를 가져야 하며, dashboard에서 바로 publication export가 가능해야 한다.
5. **Co-assembly 기반 per-sample 풍부도 비교가 모든 시각화의 핵심이다.** Co-assembly contigs를 공통 참조로 하여 각 샘플의 coverage/RPM을 정량 비교한다. 샘플별 독립 assembly는 contig이 달라 비교가 불가능하므로, co-assembly + per-sample remapping이 유일한 정량 비교 전략이다.

### 사용자 확정 사항 (2026-03-25)

**Taxonomy Browser 시각화 모드:**
- **Sankey (기본, primary)** — 흐름이 직관적이고 복잡한 taxonomy에서도 가독성 유지
- **Sunburst (toggle)** — 계층 drill-down에 유리하나 복잡할 때 가독성 저하
- **Treemap (toggle)** — 면적으로 크기 비교에 유리

3가지 모두 지원하되, 탭/버튼 전환으로 전환. 각 모드에 동일한 필터/컨트롤 적용:
- 샘플별 드롭다운 (All / GC_Tm / Inf_NB_Tm)
- Rank depth 슬라이더 (Family까지 / Genus까지 / Species까지)
- Family/Genus multi-select 필터

**Per-sample 풍부도의 핵심 원칙:**
Co-assembly contigs가 공통 좌표계 역할을 하므로, 동일 contig에 대한 샘플별 coverage/RPM 비교가 가능하다. 이것이 DeepInvirus의 핵심 분석 전략이며, 모든 시각화(Sankey, heatmap, bar chart)에서 샘플별 비교를 지원해야 한다.

---

## Part 1. Dashboard v2.0 Architecture

### 1.1 Product Direction

Dashboard v2.0은 현재의 단순 6-tab viewer가 아니라, Pavian + Krona + virome QC viewer를 결합한 `interactive analysis workbench`로 정의한다.

- Frontend baseline: 현재의 standalone HTML + Jinja2 + Plotly.js 유지
- Data delivery baseline: TSV direct read가 아니라 `dashboard_data.json` 또는 inline JSON bundle 사용
- Interaction baseline: cross-filtering, drill-down, selected contig state, download/export state 지원
- Design baseline: report figure와 동일한 palette, font scale, axis conventions 사용

권장 정보 구조는 다음과 같다.

1. Overview
2. Taxonomy Browser
3. Coverage
4. Diversity
5. Search
6. Results

### 1.2 Core Data Contract

현재 `generate_dashboard.py`는 tab별로 분산된 JSON 조각을 템플릿에 주입한다. v2에서는 아래 형태의 canonical payload를 정의하는 것이 좋다.

```json
{
  "metadata": {
    "pipeline_version": "DeepInvirus v2.0",
    "analysis_date": "2026-03-25",
    "samples": ["GC_Tm", "Inf_NB_Tm"],
    "reference_files": {
      "bigtable": "taxonomy/bigtable.tsv",
      "contigs_fasta": "assembly/coassembly.contigs.fa"
    }
  },
  "summary": {},
  "taxonomy_tree": [],
  "contigs": [],
  "coverage_profiles": {},
  "diversity": {},
  "figures": [],
  "dictionaries": {},
  "report_sections": {}
}
```

권장 산출물:

- `dashboard.html`: viewer shell
- `dashboard_data.json`: structured analysis payload
- `figure_manifest.tsv` 또는 `figure_manifest.json`: Results tab용 메타데이터
- `report_sections.json`: report와 dashboard 동기화를 위한 섹션 요약

### 1.3 Overview Tab

Overview는 "진입 페이지"이자 "report summary의 interactive 버전"이어야 한다.

필수 KPI cards:

- `n_samples`
- `n_contigs_detected`
- `n_species_detected`
- `n_families_detected`
- `top_family_by_rpm`
- `top_species_by_rpm`
- `high_confidence_contigs` (`breadth >= threshold` and `depth >= threshold`)
- `novel_candidate_contigs` (low taxonomy confidence / no close hit / CheckV low completeness note 포함 가능)

권장 charts:

- `Plotly indicator` cards for major KPIs
- `stacked bar chart`: sample별 high/medium/low detection confidence counts
- `horizontal bar chart`: top viral families by total RPM
- `sample-level lollipop/dot plot`: sample별 viral burden (`sum RPM`, `covered contig count`, `mean breadth`)
- `treemap` or `sunburst summary`: 빠른 taxonomic overview
- `quality strip`: host removal rate, assembled contigs, viral contig fraction

권장 UX:

- sample selector: `All samples`, single-sample, side-by-side compare
- metric selector: `RPM`, `coverage`, `breadth-weighted abundance`, `contig count`
- click-through: 어떤 카드/바를 클릭해도 Taxonomy Browser / Search로 이동

구현 복잡도:

- Frontend: Medium
- Backend/data shaping: Medium

### 1.4 Taxonomy Browser Tab

Composition tab은 폐기하고 `Taxonomy Browser`로 재정의한다. 이 탭은 사용자 피드백의 핵심이다.

#### 1.4.1 Required Views

1. `Sunburst chart`
   - Plotly type: `sunburst`
   - Hierarchy: `domain -> phylum -> class -> order -> family -> genus -> species -> seq_id`
   - Value metric: 기본 `sum_rpm`, 옵션 `contig_count`, `sum_coverage`, `sum_breadth`

2. `Krona-style ring chart`
   - Plotly type: `sunburst` with ring emphasis or `icicle`/`treemap` fallback
   - 목적: 발표/보고용 시각적 밀도 높은 원형 taxonomy view

3. `Taxonomy table/browser`
   - Pavian-style expandable table
   - Columns: `name`, `rank`, `sample_presence`, `sum_rpm`, `mean_breadth`, `n_contigs`, `top_contig`, `baltimore_group`
   - 기능: expand/collapse, sort, filter, breadcrumb navigation

4. `Treemap / Icicle toggle`
   - 큰 샘플 수에서 sunburst label overlap 완화용

#### 1.4.2 Control Panel

필수 controls:

- sample mode
  - `All samples`
  - `Single sample`
  - `Compare 2 samples`
- rank selector
  - `domain`, `phylum`, `class`, `order`, `family`, `genus`, `species`
- metric selector
  - `RPM`
  - `Coverage`
  - `Breadth`
  - `Contig count`
- multi-select filters
  - `family`
  - `genus`
  - `species`
  - `baltimore_group`
  - `detection_method`
- checkbox
  - `Show species-level`
  - `Show unclassified`
  - `Normalize within sample`

#### 1.4.3 Comparison Mode

Single-sample only로 끝나면 안 된다. 최소 두 가지 비교 모드를 제공한다.

- `Split view`: 좌/우 sunburst 두 개
- `Difference mode`: taxon별 delta RPM barplot + changed branches highlight

#### 1.4.4 Data Structure

권장 taxonomy long table:

```tsv
sample
seq_id
domain
phylum
class
order
family
genus
species
taxid
baltimore_group
ictv_classification
rpm
coverage
breadth
detection_confidence
```

권장 precomputed tree node schema:

```json
{
  "node_id": "family:Dicistroviridae",
  "parent_id": "order:Picornavirales",
  "label": "Dicistroviridae",
  "rank": "family",
  "sample": "GC_Tm",
  "metrics": {
    "sum_rpm": 19234.2,
    "sum_coverage": 88.1,
    "mean_breadth": 0.74,
    "contig_count": 12
  }
}
```

#### 1.4.5 Why Sankey Is No Longer Primary

현재 Sankey는 `domain -> family`만 보여 주며, 샘플 구분과 species drill-down이 불가능하다. v2에서는 Sankey를 보조 뷰로 격하하는 것이 맞다.

- 유지 용도: overview-level flow explanation
- 대체 주력: `sunburst`, `treemap`, `expandable taxonomy table`

구현 복잡도:

- Data model: High
- Frontend interaction: High

### 1.5 Coverage Tab

현재 heatmap만으로는 사용자가 "어떤 contig가 어떤 샘플에서 실제로 얼마나 균일하게 덮였는가"를 판단할 수 없다. v2 Coverage 탭은 3층 구조가 필요하다.

#### 1.5.1 Layer A: Contig x Sample Summary Heatmap

- Plotly type: `heatmap`
- z-value options:
  - `log10(mean_depth + 1)`
  - `breadth`
  - `breadth_weighted_depth = mean_depth * breadth`
- clustering:
  - contig clustering: hierarchical clustering (`ward` or `average`)
  - sample clustering: optional if sample count >= 3
- row annotations:
  - family
  - species
  - detection_confidence
  - contig length bin

권장 산출물:

- clustering order를 미리 계산해 JSON에 저장
- dendrogram 자체는 정적 PNG/SVG figure와 dashboard interactive heatmap 양쪽에서 재사용

#### 1.5.2 Layer B: Contig Detail Panel

heatmap row click 또는 Search selection 시 detail panel 업데이트:

- contig ID
- length
- family / genus / species
- best hit
- detection method
- ORF count / coding density
- per-sample summary mini-table

#### 1.5.3 Layer C: Per-contig Read Mapping Profile

필수 신규 기능이다.

- Plotly type: `scattergl` 또는 `bar`
- x-axis: contig position
- y-axis: per-base depth
- traces:
  - selected sample depth line
  - optional multi-sample overlay
  - breadth highlighted region
  - ORF annotation track
  - best-hit alignment region track (가능하면)

권장 보조 panel:

- genome/contig ruler
- low-complexity / uncovered region shading
- tooltip: `position`, `depth`, `ORF`, `GC window`

#### 1.5.4 Required Backend Input

현재 `CoverM` summary만으로는 불충분하다. 최소 다음 파일이 추가되어야 한다.

- `coverage_depth/{sample}.depth.tsv.gz`
  - columns: `seq_id`, `pos`, `depth`
- optional:
  - `coverage_bins/{sample}_10bp.tsv.gz`
  - columns: `seq_id`, `start`, `end`, `mean_depth`

10bp 또는 50bp binning을 권장하는 이유:

- standalone HTML payload 크기 절감
- 브라우저 렌더링 속도 개선
- publication figure용 smoothing과도 일치

구현 복잡도:

- Summary heatmap: Medium
- Per-base profile pipeline: High
- Frontend detail viewer: High

### 1.6 Diversity Tab

현재 Diversity 탭은 alpha/beta/PCoA viewer 수준이다. v2에서는 해석 가능한 비교 도구로 강화해야 한다.

권장 구성:

- `alpha diversity card + box/strip plot`
  - Shannon
  - Simpson
  - Observed taxa
  - optional Chao1은 "approximate" badge 유지 또는 제거 검토
- `beta diversity heatmap`
  - metric selector: `Bray-Curtis`, `Jaccard`
- `PCoA scatter`
  - Plotly type: `scatter`
  - sample group color, confidence ellipse optional
- `pairwise comparison matrix`
  - sample 간 shared taxa count
  - shared species count
  - shared high-confidence contig count

개선 포인트:

- diversity 계산 기준을 `coverage-based abundance`로 고정
- species/family level 전환 지원
- sparse dataset 경고 표시
- `n < 3`일 때는 PCoA보다 pairwise descriptive view를 우선

구현 복잡도:

- Medium

### 1.7 Search Tab v2

Search는 단순 row filter가 아니라 `contig intelligence console`이 되어야 한다.

#### 1.7.1 Table Columns

필수 컬럼:

- `seq_id`
- `sample_presence`
- `family`
- `genus`
- `species`
- `baltimore_group`
- `ICTV_classification`
- `detection_method`
- `detection_score`
- `length`
- `gc_percent`
- `mean_depth_max`
- `breadth_max`
- `rpm_max`
- `best_hit`
- `pident`
- `evalue`
- `orf_count`
- `coding_density`
- `sequence_preview`

#### 1.7.2 Detail Drawer / Modal

행 클릭 시 표시:

- full taxonomy lineage
- contig sequence with copy/download
- FASTA header
- ORF table
- per-sample coverage sparkline
- per-contig depth profile
- BLAST/MMseqs best hit details
- links to results figures where contig is represented

#### 1.7.3 Search / Filter Controls

- free text: `seq_id`, taxonomy name, best hit
- numeric sliders: `length`, `coverage`, `breadth`, `pident`, `rpm`
- categorical filters: `family`, `species`, `baltimore_group`, `group`, `detection_method`
- `only high-confidence`
- `only multi-sample contigs`
- `only novel candidates`

#### 1.7.4 Export Functions

- export selected rows as TSV
- export selected contigs as FASTA
- export coverage profiles as TSV
- export ORF amino acid FASTA

브라우저에서 FASTA export를 하려면 contig sequence를 payload에 포함하거나 on-demand fetch 해야 한다. contig 수가 많다면 전체 base64 inline은 비효율적이므로 다음 중 하나를 권장한다.

1. `contigs_index.tsv + sequences.fa.gz`를 두고 JS에서 indexed fetch
2. `selected contigs only` export를 위해 HTML에 compressed sequence map 포함

standalone HTML을 유지해야 한다면:

- `LZ-string` 또는 gzip-base64 compressed JSON blob
- contig sequence는 1차적으로 detail modal에서 lazy inflate

구현 복잡도:

- High

### 1.8 Results Tab

Results 탭은 비어 있으면 안 된다. 현재 report에서 생성한 PNG를 단순 embedding하는 수준에서 벗어나 `publication figure gallery`로 바꿔야 한다.

필수 요소:

- figure card gallery
- each card:
  - figure title
  - report section mapping
  - interactive twin availability
  - PNG download
  - SVG download
  - original TSV source reference

권장 manifest schema:

```json
{
  "figure_id": "fig_taxonomic_heatmap",
  "title": "Taxonomic Heatmap",
  "report_section": "6.2 Taxonomic Heatmap",
  "png_path": "figures/taxonomic_heatmap.png",
  "svg_path": "figures/taxonomic_heatmap.svg",
  "interactive_view": "taxonomy-browser/heatmap",
  "source_tables": ["taxonomy/sample_taxon_matrix.tsv"]
}
```

추가 기능:

- `View in dashboard` deep-link
- `Use as publication figure` badge for QC-passed figures
- `Figure notes` for interpretation caveats

구현 복잡도:

- Low to Medium

### 1.9 Dashboard-Report Mirror Requirement

사용자 피드백의 핵심은 "dashboard must mirror ALL analysis from report.docx"이다. 이를 만족시키기 위해 section mapping table을 정의해야 한다.

| Report Section | Dashboard Location | Status in v2 |
|---|---|---|
| Executive Summary | Overview | Required |
| Methods summary | Overview / Results metadata | Required |
| QC Results | Overview / Results | Required |
| Host Removal | Overview / Results | Required |
| Virus Detection | Taxonomy Browser / Overview | Required |
| Per-sample Coverage Analysis | Coverage | Required |
| Taxonomic Analysis | Taxonomy Browser | Required |
| Diversity Analysis | Diversity | Required |
| Conclusions / Limitations | Overview info panel | Recommended |
| Appendix dictionaries | Search help / Results dictionary | Required |

권장 구현:

- `report_sections.json` 생성
- dashboard 템플릿에서 해당 섹션 설명/해석문을 info drawer로 노출

---

## Part 2. Report v2.0

### 2.1 Report Design Principles

리포트는 단순 문서가 아니라, dashboard와 동일한 분석 결과를 정적 publication artifact로 정제한 버전이어야 한다.

핵심 원칙:

- 동일 데이터 소스 사용
- 동일 figure naming 사용
- 동일 section ordering 사용
- appendix는 길이를 제어하고, dictionary/reference 중심으로 압축

### 2.2 Structural Upgrades

필수 변경:

1. `Table of Contents`
   - 현재 clickable TOC 유지

2. `ANALYSIS_GUIDE.md` 통합
   - Introduction 또는 front matter에 "How to Read This Analysis" 섹션으로 편입
   - Appendix에 dashboard usage 요약 포함

3. `README.md` Parameter/Results Dictionary 통합
   - Appendix에 `Parameter Dictionary`, `Results Dictionary`, `Output Structure`로 편입
   - 현재 `README.md` 복사본을 산출물에 두는 대신 문서 내부 reference 형태로 유지

4. `A. Complete Viral Contig List` 축소
   - 전체 테이블 삽입 제거
   - 다음 형태로 대체:
     - `The complete contig list is provided in taxonomy/bigtable.tsv`
     - `Sequence-level export is available in assembly/coassembly.contigs.fa`

5. `Figure caption modernization`
   - figure마다 data source, metric, caveat를 1줄 포함

### 2.3 Recommended New Report Sections

- `How to Read This Report`
  - guide 문서 통합용
- `Interactive Companion`
  - dashboard path, 주요 탭 설명, 어떤 figure가 interactive인지 명시
- `Data Dictionary`
  - `bigtable`, `coverage depth`, `orf stats`, `figure manifest`

### 2.4 Report-Only Content That Should Be Reduced

보고서에 너무 긴 raw table을 넣는 것은 Word usability를 떨어뜨린다. 아래는 문서 내 full table 대신 reference로 충분하다.

- full contig appendix
- full ORF list
- full per-base depth values
- entire output directory tree if already stable

### 2.5 Figure Quality Improvements

문서 차원에서 반드시 반영할 것:

- long label wrapping
- figure-specific dimension presets
- SVG-first export and DOCX PNG fallback
- caption numbering 자동화는 유지하되 figure title short form 사용

구현 복잡도:

- Medium

---

## Part 3. Figure Quality Checklist

### 3.1 Figure Generation Functions to Audit

현재 코드 기준 주요 figure 생성 함수는 다음과 같다.

#### Report-local functions in `bin/generate_report.py`

- `_plot_host_mapping_comparison`
- `_plot_per_sample_coverage_heatmap`
- `_plot_detection_barchart`
- `_plot_family_composition`
- `_plot_qc_barchart`
- `_plot_pcoa_from_coords`

#### Shared plotting functions in `bin/utils/visualization.py`

- `plot_heatmap`
- `plot_barplot`
- `plot_pcoa`
- `plot_alpha_diversity`

#### Additional figure generators in separate scripts

- `bin/visualize_host_removal.py`
  - `plot_mapping_rate_bar`
  - `plot_read_flow`
  - `plot_summary_table`
- `bin/visualize_bbduk_stats.py`
  - `plot_read_waterfall`
  - `plot_base_composition`
  - `plot_qc_summary_table`
- `bin/plot_contig_mapping.py`
  - `plot_contig_bubble`
  - `plot_length_distribution`
  - `plot_coverage_vs_identity`
  - `plot_family_contig_map`

### 3.2 Global Visual QA Rules

모든 figure에 대해 공통 점검 항목을 적용한다.

- title overlap 여부
- x tick label rotation 필요 여부
- legend overflow 여부
- color palette의 category 수 초과 여부
- font size가 300 DPI 출력에서 readable한지
- SVG에서 text가 outline이 아닌 실제 text로 유지되는지
- aspect ratio가 label 밀도에 맞는지
- `bbox_inches="tight"`로 인한 clipping 여부

### 3.3 Exact Fixes by Figure Type

#### `taxonomic_heatmap`

문제 가능성:

- row 수가 많을 때 y-axis labels 과밀
- clustermap dendrogram + labels + colorbar 충돌

정확한 수정:

- top N taxa + Others default figure 생성
- dashboard interactive heatmap은 full dataset 유지
- static figure는 `max_rows` preset 도입
- `fig_height = max(8, min(24, n_rows * 0.22 + 4))`
- y tick label font를 8~9pt로 축소
- long taxon name 줄바꿈 또는 truncation

#### `composition_barplot` / `family_composition`

문제 가능성:

- legend 항목 과다
- sample 수가 늘면 x labels 겹침

정확한 수정:

- `top_n=12` 또는 `top_n=15`로 제한
- 나머지는 `Others`
- legend는 figure 밖 우측 고정
- sample labels rotation 30-45도
- horizontal variant fallback 제공

#### `alpha_diversity`

문제 가능성:

- metrics 수 증가 시 subplot 폭 부족

정확한 수정:

- `figsize=(4 * n_metrics, 5.5)`로 동적 조절
- `constrained_layout=True`
- `stripplot` alpha 축소

#### `pcoa_plot`

문제 가능성:

- label annotation이 있다면 충돌
- ellipse가 sparse sample에서 misleading

정확한 수정:

- ellipse는 `n >= 3 per group`일 때만 유지
- sample label은 hover-only interactive에서 처리
- static figure는 label annotate 최소화

#### `per_sample_coverage_heatmap`

문제 가능성:

- contig 수가 많으면 unreadable

정확한 수정:

- static figure는 top contigs only
- dashboard는 full heatmap + search linkage
- contig label에 `species|seq_id_short`
- breadth annotation side bar 추가

#### `qc_bbduk_barchart` / host-removal figures

문제 가능성:

- small sample counts에서는 괜찮지만 sample 수 증가 시 labels overlap

정확한 수정:

- horizontal grouped bar 고려
- number annotation은 sample 수가 8개 이하일 때만 표시

#### `plot_coverage_vs_identity`

문제 가능성:

- dense scatter에서 점 과포화

정확한 수정:

- alpha < 0.6
- marginal density optional
- size scale clipping

### 3.4 Visual QA Workflow

권장 절차:

1. 모든 figure를 PNG + SVG로 생성
2. SVG를 브라우저에서 열어 text overlap 검수
3. Word 삽입 후 최종 PDF export까지 검수
4. `figure_qc.tsv` 작성

권장 `figure_qc.tsv` columns:

- `figure_id`
- `source_function`
- `status`
- `issue_type`
- `recommended_fix`
- `owner`

구현 복잡도:

- Audit: Medium
- Fix execution: Medium

---

## Part 4. Data Pipeline Requirements

### 4.1 New Data Artifacts Required for Dashboard v2

현재 산출물만으로는 v2 요구를 충족할 수 없다. 아래 산출물이 추가되어야 한다.

#### Required

1. `contig_metadata.tsv`
   - one row per contig
   - columns:
     - `seq_id`
     - `length`
     - `gc_percent`
     - `taxonomy lineage`
     - `best_hit`
     - `pident`
     - `evalue`
     - `detection_method`
     - `detection_score`
     - `baltimore_group`
     - `ictv_classification`
     - `orf_count`
     - `coding_density`

2. `sample_contig_metrics.tsv`
   - one row per `seq_id x sample`
   - columns:
     - `seq_id`
     - `sample`
     - `mean_depth`
     - `trimmed_mean`
     - `breadth`
     - `rpm`
     - `breadth_weighted_depth`
     - `detection_confidence`

3. `taxonomy_long.tsv`
   - normalized long table for browser/filtering

4. `coverage_depth/*.depth.tsv.gz`
   - per-base or binned depth values

5. `orf_stats.tsv`
   - from `predict_orfs.py`

6. `figure_manifest.json`
   - Results tab source

7. `report_sections.json`
   - report-dashboard mirror metadata

#### Strongly Recommended

- `checkv_summary.tsv`
- `contig_gc_windows.tsv`
- `blast_hits.tsv` 또는 `taxonomy_best_hits.tsv`
- `contig_sequences.fa.gz`
- `contig_index.tsv` for random access

### 4.2 Contig Sequence Delivery Strategy

질문 포인트인 "Contig sequences: how to pass FASTA to dashboard"에 대한 권장안은 다음과 같다.

#### Option A. Base64-inline FASTA in HTML

장점:

- 완전 standalone

단점:

- HTML payload 급증
- large assembly에서 브라우저 메모리 낭비

권장도:

- Small dataset only

#### Option B. Compressed sequence map JSON

예:

```json
{
  "k127_1130": "ACTG...",
  "k127_1234": "TTGC..."
}
```

gzip-base64 or LZ-string 압축 가능.

권장도:

- Medium dataset

#### Option C. Indexed FASTA sidecar

산출물:

- `coassembly.contigs.fa.gz`
- `coassembly.contigs.fa.gz.fai` 또는 custom index

장점:

- 대규모 contig set에 적합
- dashboard export 기능과 자연스럽게 연결

권장도:

- Preferred

결론:

- v2 기본은 `indexed FASTA sidecar`
- standalone-only 배포가 절대 요구되면 compressed sequence map fallback 제공

### 4.3 Per-contig Coverage Profiles

현재 `coverm contig` summary만으로는 depth plot 생성이 불가하다. 따라서 별도 mapping/depth step이 필요하다.

권장 방법:

1. read mapping BAM 생성
   - `minimap2` 또는 `bwa-mem2`/`bowtie2` 중 기존 stack과 일관성 있는 도구 선택
   - virome contig re-mapping이면 `minimap2 -ax sr`가 무난

2. BAM sort/index

3. `samtools depth`
   - `samtools depth -a sample.bam > sample.depth.tsv`

4. optional binning
   - 10bp / 50bp windows 평균

5. summarized profile JSON/TSV 생성

권장 output schema:

```tsv
sample	seq_id	pos	depth
GC_Tm	k127_1130	1	0
GC_Tm	k127_1130	2	4
```

또는 binned:

```tsv
sample	seq_id	start	end	mean_depth
GC_Tm	k127_1130	1	50	2.4
```

### 4.4 ORF Predictions

현재 `modules/local/prodigal.nf`와 `bin/predict_orfs.py`가 존재하므로 v2에서는 신규 개발보다 `reporting-consumable output`으로 편입하는 작업이 우선이다.

필요 변경:

- viral contigs 전체 또는 selected contigs에 대해 Prodigal 실행
- `predict_orfs.py` 결과를 `orf_stats.tsv`로 publish
- optional:
  - `orf_features.tsv`
  - columns: `seq_id`, `orf_id`, `start`, `end`, `strand`, `aa_length`, `product`

Dashboard 활용:

- Search tab ORF summary
- Coverage tab ORF track overlay

### 4.5 New/Updated Nextflow Modules

권장 신규 모듈:

1. `modules/local/depth_profile.nf`
   - input: reads + coassembly contigs
   - output: `*_depth.tsv.gz`, `*.bam.bai` optional

2. `modules/local/contig_metadata.nf`
   - merge contig FASTA, taxonomy, ORF, GC, best hit metadata

3. `modules/local/figure_manifest.nf`
   - figures + source mapping metadata 생성

4. `modules/local/dashboard_bundle.nf`
   - `dashboard_data.json`, `report_sections.json` 생성

권장 수정 모듈:

- `modules/local/coverm.nf`
  - current summary output 유지
  - optional `bam` publish 또는 reusable mapping intermediate 생성
- `modules/local/prodigal.nf`
  - outputs를 reporting stage까지 연결
- `modules/local/merge_results.nf`
  - `bigtable.tsv` 외에 `sample_contig_metrics.tsv`, `taxonomy_long.tsv` 생성
- `modules/local/report.nf`
  - dictionary/guide integration inputs 추가
- `modules/local/dashboard.nf`
  - TSV direct input에서 `analysis bundle` input 중심으로 변경

### 4.6 Subworkflow Changes

`subworkflows/classification.nf`:

- `COVERM_PERSAMPLE` 이후 `DEPTH_PROFILE_PERSAMPLE` 추가
- `PRODIGAL` outputs 연결
- `MERGE_RESULTS` output 확장

`subworkflows/reporting.nf`:

- REPORT가 figure만 만드는 구조에서 벗어나 `report_sections.json`도 emit
- DASHBOARD는 REPORT output figure + manifest + analysis bundle을 함께 입력
- Results tab의 empty 상태 방지를 위해 `figure_manifest`를 필수 artifact로 간주

### 4.7 Data Model Recommendation

v2에서 추천하는 canonical tables:

| Table | Grain | Purpose |
|---|---|---|
| `contig_metadata.tsv` | contig | Search / taxonomy / report appendix |
| `sample_contig_metrics.tsv` | contig x sample | coverage / abundance / confidence |
| `taxonomy_long.tsv` | contig x sample x rank context | Taxonomy Browser |
| `sample_taxon_matrix.tsv` | taxon x sample | Diversity / heatmap |
| `coverage_depth.tsv.gz` | contig x sample x position | depth profile |
| `orf_stats.tsv` | contig | Search detail |

---

## Part 5. Implementation Phases

### Phase 0. Stabilize Current Reporting Path

목표:

- Results tab empty 문제 해결
- report/doc/dashboard 입력 wiring 안정화

작업:

- `REPORT.out.figures` -> `DASHBOARD` 전달 재검증
- `figure_manifest` 도입
- current dashboard template에 Results gallery 최소 구현

의존성:

- 없음

복잡도:

- Low

### Phase 1. Data Model Expansion

목표:

- v2 interactive 기능을 지탱할 canonical tables 생성

작업:

- `merge_results.py` 확장
- `contig_metadata.tsv` 생성
- `sample_contig_metrics.tsv` 생성
- `taxonomy_long.tsv` 생성
- `orf_stats.tsv` 연결

의존성:

- Phase 0 완료 권장

복잡도:

- High

### Phase 2. Coverage Profile Pipeline

목표:

- per-contig depth visualization 가능하게 만들기

작업:

- BAM/depth module 추가
- `samtools depth` or binned depth outputs
- coverage detail JSON/TSV serializer 작성

의존성:

- Phase 1

복잡도:

- High

### Phase 3. Taxonomy Browser v2

목표:

- Sankey 중심 Composition tab을 Pavian-style browser로 교체

작업:

- `taxonomy_tree` precompute
- sunburst / treemap / browser table 구현
- sample/rank/filter state management 구현

의존성:

- Phase 1

복잡도:

- High

### Phase 4. Search v2 + Contig Detail

목표:

- sequence/ORF/coverage/best-hit 기반 contig inspection

작업:

- detail drawer
- FASTA export
- sparkline / depth profile embed

의존성:

- Phase 1, Phase 2

복잡도:

- High

### Phase 5. Report v2 Content Integration

목표:

- `ANALYSIS_GUIDE.md`와 `README.md` dictionary를 report 내부로 흡수

작업:

- `generate_report.py` appendix 재구성
- contig full list -> file reference 전환
- report section metadata emit

의존성:

- Phase 1

복잡도:

- Medium

### Phase 6. Figure QA and Publication Readiness

목표:

- text overlap 제거
- publication-safe SVG/PNG quality 확보

작업:

- 모든 plotting 함수 audit
- figure-specific sizing presets 도입
- `figure_qc.tsv` 생성

의존성:

- Phases 3-5와 병렬 가능

복잡도:

- Medium

### Phase 7. Dashboard-Report Synchronization

목표:

- report의 모든 주요 분석이 dashboard에서 interactive로 대응되도록 완성

작업:

- `report_sections.json` 기반 linking
- Results tab deep-links
- dashboard info panels에 report text reuse

의존성:

- Phases 3-5

복잡도:

- Medium

---

## 6. Recommended Engineering Decisions

### 6.1 Keep Standalone HTML, but Separate Data Bundle

현재 구조를 완전히 SPA로 재작성할 필요는 없다. 다만 template 안에 모든 계산을 밀어 넣는 구조는 유지보수성이 낮다.

권장:

- HTML shell + generated JSON bundle
- build-time precomputation 강화
- browser에서는 filtering/rendering 중심

### 6.2 Use Plotly Strategically

Plotly.js로 충분한 영역:

- sunburst
- treemap
- heatmap
- scatter / PCoA
- sparkline
- gallery thumbnails

Plotly 단독으로 불편한 영역:

- very large expandable tables
- genome browser-like ORF/depth track

해결:

- lightweight custom JS table + virtual scrolling
- depth profile는 Plotly, ORF track는 SVG overlay 또는 secondary subplot

### 6.3 Separate Static Figure Logic from Interactive Logic

정적 figure와 interactive chart가 동일 데이터를 쓰되, 동일 렌더러를 강제할 필요는 없다.

- static figure: matplotlib/seaborn optimized for publication
- interactive figure: Plotly optimized for exploration

중요한 것은 `same metric`, `same color semantics`, `same taxonomy aggregation`이다.

---

## 7. Acceptance Criteria

v2 완료 기준은 다음과 같다.

1. Taxonomy Browser에서 sample별 species-level drill-down 가능
2. family/genus/species multi-select filter 가능
3. Search tab에서 contig sequence, ORF stats, best hit, per-sample coverage를 확인 가능
4. Coverage tab에서 contig 클릭 시 per-base or binned depth plot 확인 가능
5. Results tab에서 report figures가 모두 gallery 형태로 노출되고 PNG/SVG 다운로드 가능
6. report에 `ANALYSIS_GUIDE`와 `README` dictionary 내용이 통합됨
7. report appendix는 full contig table 대신 file reference로 축소됨
8. 모든 핵심 figures에 대해 text overlap QA 완료
9. report의 각 핵심 분석이 dashboard에서 interactive counterpart를 가짐

---

## 8. Immediate Next Actions

가장 먼저 착수할 작업은 다음 순서가 적절하다.

1. `figure_manifest`와 Results tab wiring 복구
2. `contig_metadata.tsv` + `sample_contig_metrics.tsv` 설계 및 `merge_results.py` 확장
3. `depth_profile.nf` 추가로 per-contig coverage profile 생산
4. Taxonomy Browser v2 구현
5. Report appendix/dictionary 통합

이 순서는 사용자의 가장 큰 불만인 "빈 Results tab", "species-level 부재", "coverage detail 부재", "report/dashboard 불일치"를 가장 빠르게 줄인다.

---

## Supplementary: Competitive Analysis & Technology Research

> Source: Claude Research Agent (Pavian, Krona, CosmosID, Plotly.js 조사)

# DeepInvirus 대시보드 및 리포트 종합 업그레이드 계획서

> 작성일: 2026-03-25
> 대상: `assets/dashboard_template.html`, `bin/generate_dashboard.py`, `bin/generate_report.py`
> 현재 스택: Plotly.js 2.32.0, Jinja2 템플릿, python-docx

---

## 목차

1. [현행 시스템 분석](#1-현행-시스템-분석)
2. [경쟁 도구 비교 분석](#2-경쟁-도구-비교-분석)
3. [기능 매트릭스: Pavian vs Krona vs CosmosID vs DeepInvirus](#3-기능-매트릭스)
4. [업그레이드 상세 설계](#4-업그레이드-상세-설계)
   - 4.1 Taxonomy Browser (Sunburst/Treemap)
   - 4.2 검색 기능 강화
   - 4.3 Results 탭 인라인 피겨
   - 4.4 Per-contig Coverage 시각화
   - 4.5 Contig 서열 표시
   - 4.6 리포트 통합 (ANALYSIS_GUIDE + README)
   - 4.7 Publication-ready 피겨 내보내기
   - 4.8 텍스트 겹침 문제 해결
5. [구현 우선순위 및 로드맵](#5-구현-우선순위-및-로드맵)
6. [기술 참고 자료](#6-기술-참고-자료)

---

## 1. 현행 시스템 분석

### 1.1 대시보드 (`dashboard_template.html`, 1007줄)

| 탭 | 현재 기능 | 한계점 |
|----|-----------|--------|
| **Overview** | 요약 카드 5개 + Sankey (Domain->Family->Genus) | Species 레벨 없음, 샘플별 필터 없음 |
| **Composition** | Heatmap (log10 RPM) + Stacked Barplot | 계층 drill-down 없음 |
| **Coverage** | Per-sample coverage heatmap + Host removal 비교 | Per-contig 깊이 프로파일 없음, 테이블 30행 제한 |
| **Diversity** | PCoA (Bray-Curtis) + Alpha boxplot | 정상 작동 |
| **Search** | 텍스트 검색 + rank/method 필터 | species 필터 없음, contig 시퀀스 없음, read mapping 없음 |
| **Results** | inline_figures (data_uri 이미지) | 현재 비어있음 (빈 상태 메시지만 표시) |

### 1.2 리포트 (`generate_report.py`, ~1000줄)

- 10개 섹션 + Appendix 구조
- VIRUS_ORIGIN 증거 등급 시스템 (B4)
- FAMILY_DESCRIPTIONS 자동 생성 (B9)
- 과학적 hedged language (B3)
- matplotlib/seaborn 기반 정적 피겨 (300 DPI)

### 1.3 데이터 포맷

- `bigtable.tsv`: 12개 컬럼 (seq_id, sample, length, detection_method, detection_score, taxonomy, family, target, pident, evalue, coverage, group)
- `*_coverage.tsv`: Contig, Mean, Trimmed Mean, Covered Bases, Length
- `sample_taxon_matrix.tsv`: taxon x sample RPM 매트릭스

---

## 2. 경쟁 도구 비교 분석

### 2.1 Pavian

**핵심 기능:**
- Sankey 다이어그램 (D3.js + networkD3 기반): Root에서 말단 taxonomic rank까지 read flow 시각화
- 다중 분류기 지원 (Kraken, Centrifuge, MetaPhlAn)
- 샘플 간 비교 테이블 (interactive JS data table)
- Alignment coverage viewer로 특정 게놈 매칭 검증
- R Shiny 기반 웹 앱

**DeepInvirus 적용 가능 요소:**
- Sankey 다이어그램: 이미 구현됨 (Plotly.js 기반). Species 레벨까지 확장 필요
- 샘플 간 비교: dropdown selector로 샘플별 Sankey 필터링 추가
- Read flow 비율 표시: link 폭에 read count/RPM 비례 표시

### 2.2 KronaTools

**핵심 기능:**
- Radial space-filling 다이어그램 (다층 파이 차트)
- HTML5 + JavaScript 순수 구현 (외부 의존성 없음)
- XHTML 내 XML로 계층 데이터 저장
- Polar-coordinate 줌 (클릭으로 drill-down)
- Parametric coloring (속성별 색상 변경)
- 완전한 standalone HTML

**DeepInvirus 적용 가능 요소:**
- Krona 스타일의 radial chart는 Plotly.js **Sunburst chart**로 대체 구현 가능
- 동일한 drill-down 경험 제공 (클릭으로 하위 계층 확대)
- 장점: Plotly.js 에코시스템 내 통일성 유지, 추가 라이브러리 불필요

### 2.3 CosmosID

**핵심 기능:**
- Sunburst, bubble chart, stacked bar graph
- Heatmap, 3D PCA, alpha/beta diversity
- 가상 코호트 생성 및 비교 분석
- Differential abundance 분석
- 메타데이터 대시보드
- AMR/virulence marker 탐지

**DeepInvirus 적용 가능 요소:**
- Sunburst chart 채택 (Plotly.js native)
- 다이나믹 필터링 UI 패턴 참고
- 비교 분석 모듈 구조 참고

### 2.4 anvi'o

**핵심 기능:**
- SVG 기반 인터랙티브 시각화 (JavaScript 자체 구현)
- Coverage plot 실시간 inspect
- SNV 뷰어
- GC content, relative abundance, contig length 다차원 탐색
- Genome binning 인터랙티브 인터페이스

**DeepInvirus 적용 가능 요소:**
- Per-contig coverage profile 개념 (Plotly.js line chart로 구현)
- 다차원 contig 속성 탐색 UI

---

## 3. 기능 매트릭스

| 기능 | Pavian | Krona | CosmosID | anvi'o | DeepInvirus (현재) | DeepInvirus (계획) |
|------|--------|-------|----------|--------|-------------------|--------------------|
| **Taxonomy 계층 시각화** | Sankey (D3) | Radial pie | Sunburst | SVG circular | Sankey (Plotly) | Sunburst + Sankey |
| **Drill-down 탐색** | 제한적 | 우수 (polar zoom) | 우수 | 우수 | 없음 | Sunburst 클릭 drill-down |
| **Species 레벨 표시** | 가능 | 가능 | 가능 | 가능 | 없음 (Genus까지) | 가능 |
| **샘플별 필터** | 드롭다운 | 별도 파일 | 코호트 | 프로파일별 | 없음 | 드롭다운 필터 |
| **다중 샘플 비교** | 테이블 + heatmap | 불가 | heatmap + PCA | 우수 | Heatmap만 | Heatmap + 필터 |
| **Heatmap** | 있음 | 없음 | 있음 | 있음 | 있음 | 유지 + 개선 |
| **Per-contig coverage** | 없음 | 없음 | 없음 | 우수 (inspect) | Heatmap만 | Line chart + heatmap |
| **Contig 서열 표시** | 없음 | 없음 | 없음 | BLAST link | 없음 | 접이식 서열 뷰어 |
| **Read mapping viz** | alignment viewer | 없음 | 없음 | coverage plot | 없음 | Per-contig depth plot |
| **다양성 분석** | 없음 | 없음 | alpha/beta + PCA | 없음 | PCoA + alpha | 유지 |
| **피겨 내보내기** | 없음 (screenshot) | PNG | 다운로드 | SVG | window.print() | SVG/PNG (Plotly.toImage) |
| **Standalone HTML** | 아니오 (Shiny 서버) | 예 | 아니오 (클라우드) | 아니오 (서버) | **예** | **예** (핵심 장점) |
| **검색/필터** | 테이블 필터 | 없음 | 메타데이터 필터 | 검색/BLAST | 기본 텍스트 검색 | 강화된 다중 필터 |
| **보고서 생성** | 없음 | 없음 | PDF 내보내기 | 없음 | Word (.docx) | Word + 대시보드 연동 |

---

## 4. 업그레이드 상세 설계

### 4.1 Taxonomy Browser (Pavian/Krona 스타일)

#### 구현 방식: Plotly.js Sunburst Chart

Krona의 radial hierarchical pie chart를 Plotly.js의 **Sunburst chart**로 구현한다. 동일한 `labels`/`parents` 데이터 구조를 사용하며, 클릭으로 drill-down이 가능하다.

**데이터 흐름:**
```
bigtable.tsv taxonomy 컬럼
  "Viruses;Duplodnaviria;Heunggongvirae;Uroviricota;Caudoviricetes;;"
  → 파싱 → {id, label, parent, value} 배열
  → Plotly.js sunburst trace
```

**Python 변환 함수 설계 (`generate_dashboard.py` 추가):**
```python
def build_sunburst(bigtable: pd.DataFrame) -> dict:
    """Build Plotly sunburst data from taxonomy hierarchy.

    Parses semicolon-delimited taxonomy strings into:
    - ids: unique path identifiers
    - labels: display names (rank-level)
    - parents: parent path identifiers
    - values: contig counts at each node

    Returns: {"ids": [...], "labels": [...], "parents": [...], "values": [...]}
    """
```

**JavaScript 렌더링 (`dashboard_template.html` 추가):**
```javascript
function renderSunburst() {
    var sb = D.sunburst;
    var trace = {
        type: "sunburst",
        ids: sb.ids,
        labels: sb.labels,
        parents: sb.parents,
        values: sb.values,
        branchvalues: "total",
        hovertemplate: "%{label}<br>Contigs: %{value}<extra></extra>",
        maxdepth: 3  // 초기 3레벨만 표시, 클릭으로 확장
    };
    Plotly.newPlot("sunburst-plot", [trace], layout, PLOTLY_CONFIG);
}
```

**UI 설계:**
- Overview 탭에 Sankey와 나란히 배치 (2열 그리드)
- 좌: Sunburst (Krona 스타일 drill-down), 우: Sankey (flow 시각화)
- 샘플 필터 드롭다운: `<select id="sample-filter">` 추가
  - "All Samples" (기본) / 개별 샘플 선택
  - 선택 시 해당 샘플의 contig만 필터링하여 Sunburst/Sankey 재렌더링

**대안: Treemap**
- Sunburst와 동일한 데이터 구조 사용 (코드 변경 최소)
- 직사각형 레이아웃으로 텍스트 겹침 문제가 적음
- "차트 유형 전환" 버튼으로 Sunburst ↔ Treemap 토글 가능

**Multi-select 필터 구현:**
```javascript
// 샘플 다중 선택
<select id="sample-filter" multiple>
  <option value="all" selected>All Samples</option>
  {% for s in data.samples %}
  <option value="{{ s }}">{{ s }}</option>
  {% endfor %}
</select>

// Family 필터
<select id="family-filter" multiple>
  {% for f in data.families %}
  <option value="{{ f }}">{{ f }}</option>
  {% endfor %}
</select>
```

---

### 4.2 검색 기능 강화

#### 4.2.1 Species 레벨 검색

**현재 한계:** Search 탭에 taxon, rank, family, sample, RPM, detection, baltimore_group 7개 컬럼만 표시. Species 컬럼 없음.

**해결:**
1. `bigtable.tsv`의 `taxonomy` 컬럼에서 species 파싱 (세미콜론 구분 마지막 비어있지 않은 레벨)
2. `generate_dashboard.py`의 `build_search_rows()`에 `species` 필드 추가
3. Search 테이블에 Species 컬럼 추가
4. rank-filter에 `species` 옵션 이미 존재 → 데이터만 채우면 됨

#### 4.2.2 Contig 서열 검색 및 표시

**접근 방식: On-demand 접이식 표시**

FASTA를 전부 base64로 embedding하면 HTML 크기 폭증 (1495 contigs x 평균 5KB = ~7.5MB). 대신:

```
전략 A (권장): 서열 요약 + 접이식 표시
- 각 contig의 처음 200bp만 저장 (preview)
- 전체 서열은 별도 JSON 파일로 분리
- "Show sequence" 버튼 클릭 시 접이식 div 펼침
- 총 추가 용량: ~300KB (200bp x 1495 contigs)

전략 B: 전체 서열 임베딩
- gzip + base64 인코딩으로 압축 (~2-3MB)
- JavaScript에서 pako.js로 클라이언트 측 압축 해제
- 단점: CDN 의존성 추가 또는 pako 번들링 필요
```

**서열 뷰어 라이브러리 옵션:**

| 라이브러리 | 크기 | 기능 | 적합성 |
|-----------|------|------|--------|
| **SeqViz** | ~200KB | linear/circular viewer, 주석, React 기반 | 과도함 (React 의존성) |
| **커스텀 HTML** | ~2KB | monospace `<pre>` + 줄번호 + 검색 | **최적** (의존성 없음) |
| **MSAViewer** | ~150KB | MSA 시각화 | 과도함 (MSA 불필요) |

**권장:** 외부 라이브러리 없이 커스텀 monospace `<pre>` 블록으로 구현.

```html
<!-- 서열 표시 템플릿 -->
<tr class="sequence-row" style="display:none">
  <td colspan="8">
    <pre class="sequence-display" style="
      font-family: var(--font-mono);
      font-size: 11px;
      background: #f8f9fa;
      padding: 12px;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-all;
      max-height: 200px;
      overflow-y: auto;
    ">ATGCGATCGATCG...</pre>
  </td>
</tr>
```

#### 4.2.3 Per-contig Read Mapping 시각화

**데이터 요구사항:**
현재 `*_coverage.tsv`는 contig별 mean/trimmed_mean만 제공. Position-level depth가 필요함.

```bash
# 필요한 추가 데이터 생성 (파이프라인에 추가)
samtools depth -a -d 0 sample.sorted.bam | \
  awk '{print $1, $2, $3}' > sample_depth.tsv
# 결과: Contig Position Depth (position-level)
```

**시각화 구현: Plotly.js Line Chart**

```javascript
function renderContigCoverage(contigId) {
    // D.contig_depth[contigId] = {positions: [...], depths: {...sample: [...]}}
    var cd = D.contig_depth[contigId];
    var traces = [];
    for (var sample in cd.depths) {
        traces.push({
            type: "scatter",  // scattergl for performance
            mode: "lines",
            name: sample,
            x: cd.positions,
            y: cd.depths[sample],
            fill: "tozeroy",
            opacity: 0.6
        });
    }
    Plotly.newPlot("contig-coverage-detail", traces, {
        xaxis: {title: "Position (bp)"},
        yaxis: {title: "Read Depth"},
        title: contigId + " Coverage Profile"
    }, PLOTLY_CONFIG);
}
```

**데이터 크기 최적화:**
- 1495 contigs x 평균 2000bp = ~3M data points (너무 큼)
- **해결:** 구간 평균화 (binning) - 100bp 윈도우 평균 → ~30K points
- 또는 상위 30 contigs만 position-level 데이터 임베딩
- 나머지는 mean coverage만 표시 (현행 유지)

**실현 가능성 평가:**
- 상위 30 contigs의 binned depth 데이터: ~100KB
- Plotly.js scattergl로 성능 문제 없음
- Standalone HTML 유지 가능

---

### 4.3 Results 탭 인라인 피겨

**현재 상태:** `{% if data.inline_figures %}` 조건부 렌더링이지만, `inline_figures`가 비어있어 빈 메시지만 표시.

**해결:** `generate_dashboard.py`에서 `figures_dir` 경로의 PNG 파일들을 base64 data URI로 변환하여 삽입.

```python
def build_inline_figures(figures_dir: Path) -> list[dict]:
    """Convert figure PNGs to base64 data URIs for inline display."""
    figures = []
    if not figures_dir or not figures_dir.exists():
        return figures

    FIGURE_ORDER = [
        ("qc_bbduk_barchart.png", "QC: Adapter Removal Statistics"),
        ("host_mapping_comparison.png", "Host RNA Mapping Rate"),
        ("detection_barchart.png", "Virus Detection by Method"),
        ("family_composition.png", "Virus Family Composition"),
        ("taxonomic_heatmap.png", "Taxonomic Abundance Heatmap"),
        ("per_sample_coverage_heatmap.png", "Per-sample Coverage Heatmap"),
        ("composition_barplot.png", "Relative Abundance Barplot"),
        ("alpha_diversity.png", "Alpha Diversity Metrics"),
        ("pcoa_plot.png", "PCoA Ordination (Bray-Curtis)"),
    ]

    for filename, label in FIGURE_ORDER:
        path = figures_dir / filename
        if path.exists():
            import base64
            data = base64.b64encode(path.read_bytes()).decode()
            figures.append({
                "name": filename,
                "label": label,
                "data_uri": f"data:image/png;base64,{data}"
            })
    return figures
```

**CLI 인자 추가:**
```
--figures-dir  figures/  # 이미 generate_report.py에서 생성된 PNG 경로
```

---

### 4.4 Per-contig Coverage 시각화 상세

#### Phase 1: Coverage Heatmap 개선 (즉시 구현 가능)

현재 coverage heatmap은 contigs x samples 매트릭스만 표시. 개선:
- 클릭 가능한 contig 행: 클릭 시 하단에 상세 정보 패널 표시
- 상세 패널: contig 길이, family, detection method, coverage per sample (bar chart)

#### Phase 2: Position-level Coverage (파이프라인 변경 필요)

Nextflow 파이프라인에 `samtools depth` 스텝 추가:
```groovy
process SAMTOOLS_DEPTH {
    input: path(bam), path(bai)
    output: path("*_depth.tsv.gz")
    script:
    """
    samtools depth -a -d 0 ${bam} | \
      awk 'BEGIN{OFS="\\t"} {
        bin=int(\$2/100)*100;
        sum[\\$1][bin]+=\\$3;
        cnt[\\$1][bin]++
      } END {
        for(c in sum) for(b in sum[c])
          print c, b, sum[c][b]/cnt[c][b]
      }' | sort -k1,1 -k2,2n | gzip > \${prefix}_depth.tsv.gz
    """
}
```

---

### 4.5 리포트 통합

#### 4.5.1 ANALYSIS_GUIDE + README 통합

`generate_report.py`에 새로운 섹션 추가:

```python
def _build_analysis_guide_section(builder: ReportBuilder):
    """Append condensed analysis guide as Appendix B."""
    builder.add_heading("Appendix B. Analysis Guide", level=1)
    builder.add_heading("B.1 Pipeline Overview", level=2)
    builder.add_paragraph(
        "DeepInvirus is a Nextflow-based virome analysis pipeline that performs: "
        "quality control (BBDuk + FastP), host RNA removal (Bowtie2), "
        "de novo assembly (MEGAHIT co-assembly), virus detection (geNomad + DIAMOND), "
        "and taxonomic classification with per-sample read mapping."
    )
    # ... 추가 섹션들
```

#### 4.5.2 Contig 목록 → 파일 참조

현재: 리포트에 전체 contig 목록 포함 (1495줄 가능)
변경: "Appendix A에 전체 목록 파일 참조" + 상위 20개만 본문 테이블로 표시

```python
# 기존: bigtable 전체를 Appendix에 포함
# 변경:
builder.add_paragraph(
    f"The complete viral contig table ({n_contigs} entries) is available "
    f"in the accompanying file: taxonomy/bigtable.tsv"
)
# 상위 20개만 테이블로
top_20 = bigtable.nlargest(20, "coverage")
builder.add_table(top_20, title=f"Table X. Top 20 Viral Contigs by Coverage")
```

---

### 4.6 Publication-ready 피겨 내보내기

#### Plotly.js 내보내기 구현

```javascript
// 헤더에 Export 버튼 기능 교체
function exportAllFigures() {
    var plots = [
        {id: "sankey-plot", name: "sankey"},
        {id: "sunburst-plot", name: "taxonomy_sunburst"},
        {id: "heatmap-plot", name: "heatmap"},
        {id: "barplot-plot", name: "barplot"},
        {id: "coverage-heatmap-plot", name: "coverage"},
        {id: "pcoa-plot", name: "pcoa"},
        {id: "alpha-plot", name: "alpha_diversity"},
    ];

    plots.forEach(function(p) {
        var el = document.getElementById(p.id);
        if (!el || !el.data) return;

        // SVG export (vector, publication-ready)
        Plotly.toImage(el, {
            format: "svg",
            width: 1200,
            height: 800
        }).then(function(url) {
            var a = document.createElement("a");
            a.href = url;
            a.download = "DeepInvirus_" + p.name + ".svg";
            a.click();
        });
    });
}

// PNG export with scale factor for high DPI
function exportPNG(plotId, name) {
    Plotly.toImage(document.getElementById(plotId), {
        format: "png",
        width: 2400,   // 8 inches x 300 DPI
        height: 1800,  // 6 inches x 300 DPI
        scale: 1        // scale=1 at 2400px = 300 DPI at 8"
    }).then(function(url) {
        var a = document.createElement("a");
        a.href = url;
        a.download = "DeepInvirus_" + name + "_300dpi.png";
        a.click();
    });
}
```

#### Publication Figure 규격

| 저널 요구사항 | 설정값 |
|--------------|--------|
| 해상도 | 300 DPI (PNG), Vector (SVG) |
| 폰트 | Arial/Helvetica, 8-12pt |
| 선 두께 | 0.5-1.5pt |
| 컬러 | Okabe-Ito colorblind-safe (현재 적용됨) |
| 크기 | Single column: 3.5" / Double: 7" / Full page: 7x9.5" |

**Plotly.js layout 설정 업데이트:**
```javascript
function publicationLayout(title) {
    return {
        title: { text: title, font: { family: "Arial", size: 14, color: "#000" } },
        font: { family: "Arial, Helvetica, sans-serif", size: 10, color: "#000" },
        paper_bgcolor: "#FFFFFF",
        plot_bgcolor: "#FFFFFF",
        margin: { t: 50, r: 30, b: 70, l: 70 },
        // 축 스타일
        xaxis: {
            showline: true, linewidth: 1, linecolor: "#000",
            ticks: "outside", tickwidth: 1, ticklen: 5,
            title: { font: { size: 12 } },
            tickfont: { size: 10 }
        },
        yaxis: {
            showline: true, linewidth: 1, linecolor: "#000",
            ticks: "outside", tickwidth: 1, ticklen: 5,
            title: { font: { size: 12 } },
            tickfont: { size: 10 }
        }
    };
}
```

---

### 4.7 텍스트 겹침 문제 해결

**원인 분석:**
1. Sankey 노드 라벨이 좁은 공간에 배치
2. Heatmap y축 contig 이름 (예: `Parvoviridae (k127_1130)`)이 긴 경우 겹침
3. Coverage heatmap의 셀 내 숫자 (fontsize: 7)가 셀보다 큼

**해결 전략:**

```javascript
// 1. Sankey: 노드 패딩 증가 + 최소 폭 보장
node: { pad: 30, thickness: 25 }  // 현재: pad: 20, thickness: 20

// 2. Heatmap y축: 라벨 길이 제한 + 툴팁으로 전체 표시
yaxis: {
    automargin: true,
    tickfont: { size: 8 },
    // 라벨 truncation
}
// Python 측에서 라벨 truncation:
labels = [f"{family[:15]}... ({contig})" if len(family) > 15 else f"{family} ({contig})"
          for family, contig in ...]

// 3. Coverage heatmap 셀 텍스트: 조건부 표시
//    - 셀 크기가 충분할 때만 숫자 표시
//    - matplotlib: fontsize를 셀 수에 비례하여 조정
fontsize = max(5, min(9, 300 // len(labels)))

// 4. Plotly 레이아웃: 자동 마진 활용
layout.yaxis.automargin = true;
layout.xaxis.automargin = true;

// 5. 반응형 텍스트 크기 (Plotly config)
config: { responsive: true }
// + CSS로 plot-card min-width 설정
```

**matplotlib 측 (generate_report.py) 개선:**
```python
# 현재 문제: fig.savefig(output_path, dpi=DEFAULT_DPI, bbox_inches="tight")
# bbox_inches="tight"가 있지만 텍스트가 여전히 겹침

# 해결: tight_layout + constrained_layout 사용
fig, ax = plt.subplots(figsize=(max(8, n_items * 0.5), max(6, n_items * 0.35)),
                        layout="constrained")

# Y축 라벨 자동 줄바꿈
import textwrap
wrapped_labels = [textwrap.fill(label, width=25) for label in labels]

# 폰트 크기 동적 조정
tick_fontsize = max(6, min(10, 200 // max(len(labels), 1)))
ax.tick_params(axis='y', labelsize=tick_fontsize)
```

---

## 5. 구현 우선순위 및 로드맵

### Phase 1: 즉시 구현 가능 (코드 변경만, 파이프라인 변경 없음)

| 우선순위 | 작업 | 예상 시간 | 파일 |
|---------|------|----------|------|
| **P0** | Results 탭 인라인 피겨 활성화 | 2시간 | `generate_dashboard.py` |
| **P0** | 텍스트 겹침 해결 (matplotlib + Plotly) | 3시간 | `generate_report.py`, `dashboard_template.html` |
| **P1** | Sunburst chart 추가 (Overview 탭) | 4시간 | `generate_dashboard.py`, `dashboard_template.html` |
| **P1** | 샘플별 필터 드롭다운 | 3시간 | `dashboard_template.html` |
| **P1** | Publication-ready 내보내기 버튼 | 2시간 | `dashboard_template.html` |
| **P2** | Search 탭에 species 컬럼 추가 | 1시간 | `generate_dashboard.py`, `dashboard_template.html` |
| **P2** | 리포트 contig 목록 → 파일 참조 | 1시간 | `generate_report.py` |

### Phase 2: 중기 구현 (데이터 가공 추가 필요)

| 우선순위 | 작업 | 예상 시간 | 의존성 |
|---------|------|----------|--------|
| **P1** | Contig 서열 preview (200bp) 임베딩 | 3시간 | FASTA 파일 접근 |
| **P2** | Multi-select 필터 (family, method) | 3시간 | 없음 |
| **P2** | ANALYSIS_GUIDE 리포트 통합 | 4시간 | 문서 콘텐츠 |
| **P2** | Treemap ↔ Sunburst 토글 | 2시간 | Phase 1 Sunburst 완료 |

### Phase 3: 장기 구현 (파이프라인 변경 필요)

| 우선순위 | 작업 | 예상 시간 | 의존성 |
|---------|------|----------|--------|
| **P2** | Per-contig position-level coverage | 8시간 | `samtools depth` 스텝 추가 |
| **P3** | Coverage depth binning 최적화 | 4시간 | Phase 3 coverage |
| **P3** | IGV-lite contig viewer | 8시간 | BAM 인덱스 접근 |

---

## 6. 기술 참고 자료

### Plotly.js Sunburst/Treemap 핵심 API

```javascript
// Sunburst trace 구조
{
    type: "sunburst",
    ids: ["root", "root-Viruses", "root-Viruses-Parvoviridae", ...],
    labels: ["All", "Viruses", "Parvoviridae", ...],
    parents: ["", "root", "root-Viruses", ...],
    values: [1495, 1200, 45, ...],
    branchvalues: "total",  // 부모 값 = 자식 합계
    maxdepth: 3,            // 초기 표시 깊이
    insidetextorientation: "radial",
    textinfo: "label+percent entry"
}

// Treemap trace (동일 데이터 구조)
{
    type: "treemap",
    ids: [...],  // sunburst와 동일
    labels: [...],
    parents: [...],
    values: [...],
    branchvalues: "total",
    pathbar: { visible: true },
    tiling: { packing: "squarify" }
}
```

### 데이터 크기 추정 (Standalone HTML)

| 데이터 | 현재 크기 | 추가 후 예상 |
|--------|----------|-------------|
| 기본 데이터 (JSON) | ~500KB | ~500KB |
| Sunburst 데이터 | 0 | ~50KB |
| 인라인 피겨 (9개 PNG base64) | 0 | ~3MB |
| Contig 서열 preview (200bp x 1495) | 0 | ~300KB |
| Per-contig depth (top 30, binned) | 0 | ~100KB |
| **합계** | ~500KB | **~4MB** |

4MB는 standalone HTML로 충분히 관리 가능한 크기이다.

### Plotly.js 성능 가이드라인

- Scatter: ~10K points 문제없음, >100K는 `scattergl` (WebGL) 사용
- Heatmap: 1000x1000 셀까지 성능 양호
- Sunburst: ~5000 노드까지 문제없음 (taxonomy 노드 수 ~200개로 충분)
- Sankey: 노드 500개 이상 시 성능 저하 → 현재 수준에서 문제없음

### References

- [Pavian: Interactive analysis of metagenomics data](https://pmc.ncbi.nlm.nih.gov/articles/PMC8215911/)
- [Pavian GitHub](https://github.com/fbreitwieser/pavian)
- [Krona: Interactive Metagenomic Visualization](https://pmc.ncbi.nlm.nih.gov/articles/PMC3190407/)
- [KronaTools GitHub Wiki](https://github.com/marbl/krona/wiki)
- [Plotly.js Sunburst Reference](https://plotly.com/javascript/reference/sunburst/)
- [Plotly.js Treemaps](https://plotly.com/javascript/treemaps/)
- [Plotly.js Static Image Export](https://plotly.com/javascript/static-image-export/)
- [CosmosID-HUB Platform](https://www.cosmosid.com/)
- [anvi'o Platform](https://anvio.org/)
- [SeqViz - JavaScript Sequence Viewer](https://github.com/Lattice-Automation/seqviz)
- [Improving the reporting of metagenomic virome-scale data (2024)](https://www.nature.com/articles/s42003-024-07212-3)
- [Plotly Hierarchical Data Visualization](https://towardsdatascience.com/plotly-for-hierarchical-data-visualization-treemaps-and-more-47b36c5db3eb/)

---

> **요약:** DeepInvirus의 최대 장점인 **standalone HTML** 아키텍처를 유지하면서, Plotly.js Sunburst chart로 Krona/Pavian급 taxonomy 탐색 경험을 제공하고, publication-ready 내보내기와 인라인 피겨 활성화를 통해 "대시보드 = 리포트의 인터랙티브 버전" 목표를 달성한다. Phase 1의 6개 작업만으로도 사용자 요구사항의 80%를 충족할 수 있다.
