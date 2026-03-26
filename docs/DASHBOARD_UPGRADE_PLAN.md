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
