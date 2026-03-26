# DeepInvirus Pipeline v2 Multi-DB Filtering Plan

> 작성일: 2026-03-25
> 배경: 사용자 feedback 반영 + Hecatomb-style filtering 전략 분석
> 범위: virome pipeline filtering 재설계, dashboard v3 기능 정의, 구현 로드맵 수립

---

## 0. Executive Summary

현재 DeepInvirus는 다음 흐름에 가깝다.

```text
Raw reads
  -> Host removal
  -> Assembly
  -> geNomad / Diamond against viral-only DB
  -> Viral report
```

이 구조의 핵심 문제는 `viral-only DB`만으로는 `non-viral false positive`를 제대로 배제할 수 없다는 점이다. geNomad는 viral-like contig를 잘 포착하지만, 그 자체로 bacteria/plant/fungal/eukaryote-derived sequence를 완전히 배제하지는 못한다. 이어지는 Diamond BLASTx도 viral-only DB를 사용하면 "`무엇인지 모름`"과 "`사실은 non-viral`"을 구분할 수 없다. 그 결과 현재 결과에서는 `1473 / 1495 contigs (98.5%)`가 `Unclassified`로 남아, 실제 virome signal보다 오탐 또는 annotation insufficiency가 훨씬 크게 보이는 상태다.

Hecatomb의 핵심 철학은 단순하다.

1. 먼저 `potentially viral`을 넓게 포착한다.
2. 그 후 `multikingdom / transkingdom DB`로 cross-check하여 false-positive viral annotation을 제거한다.
3. 최종 virome report에는 `viral`만 남기고, `non-viral`은 별도로 annotate한 뒤 제외한다.

DeepInvirus v2는 이 철학을 반영하여 `2-tier DB approach`를 도입해야 한다.

- Tier 1: `comprehensive classification`으로 viral vs non-viral vs unknown 분리
- Tier 2: viral 후보만 대상으로 `viral-specific classification` 정밀화

동시에 dashboard는 species-level taxonomy, ICTV fixed color system, contig sequence modal, virus comparison tab을 지원하도록 v3로 확장해야 한다.

---

## 1. Multi-DB Filtering Pipeline Design

### 1.1 Current Pipeline Problems

현재 pipeline의 구조적 한계는 다음과 같다.

- `geNomad`는 viral hallmark 기반으로 `viral-like sequence`를 탐지하지만, host-derived mobile element, plasmid-like fragment, low-complexity region, bacteria/eukaryote-derived gene fragment를 완전히 배제하지 못할 수 있다.
- `Diamond BLASTx against viral-only DB`는 best hit가 없을 때 그것이 truly novel virus인지, 아니면 non-viral contig인지 구분하지 못한다.
- co-assembly contig가 non-viral background를 많이 포함하면, downstream taxonomy tree와 dashboard가 대부분 `Unclassified`로 채워진다.
- 결과적으로 현재 산출물은 `viral discovery pipeline`이라기보다 `viral-like candidate collector`에 가깝고, user-facing virome dashboard에는 너무 많은 noise가 유입된다.

즉, 현재의 문제는 단순히 taxonomy DB coverage가 낮아서가 아니라, **negative filtering layer가 빠져 있다**는 점이다.

### 1.2 Hecatomb Approach: What We Should Borrow

Hecatomb 논문과 구현 설명에서 배울 수 있는 핵심은 다음과 같다.

- Hecatomb는 raw reads/contigs를 바로 `all-vs-NR brute force`로 처리하지 않는다.
- 먼저 작은 `virus-only database`로 `potentially viral` sequence를 포착한다.
- 그다음 `multikingdom / transkingdom reference database`로 재검증하여 false-positive viral hit를 제거한다.
- amino acid search와 nucleotide search를 병행하여 detection sensitivity와 specificity를 함께 확보한다.
- 최종 해석은 "viral이라고 보이는가?"보다 "`viral call`을 뒷받침하는 cross-check evidence가 충분한가?"에 초점을 둔다.

이를 DeepInvirus 관점으로 번역하면 다음과 같다.

```text
Raw reads
  -> Host removal
  -> Assembly
  -> geNomad / viral candidate detection
  -> Tier 1 multikingdom classification
       -> viral
       -> bacterial
       -> archaeal
       -> eukaryotic
       -> unknown
  -> keep: viral + high-confidence unknown
  -> Tier 2 viral-specific classification
  -> virome report
```

즉, Hecatomb의 본질은 "`viral detector` 하나 더 넣자"가 아니라, **viral-positive evidence와 non-viral exclusion evidence를 분리해서 관리하는 설계**다.

### 1.3 Proposed Solution: 2-Tier DB Approach

DeepInvirus v2의 제안 구조는 다음과 같다.

#### Tier 1: Comprehensive classification

목표는 contig를 먼저 `viral / bacterial / archaeal / eukaryotic / unknown`으로 거칠게 분리하는 것이다.

권장 후보:

- `DIAMOND BLASTx` against `NCBI NR`
- 또는 `DIAMOND BLASTx` against `UniRef100`
- 현실적 대안으로는 curated `multikingdom exclusion DB`

출력 예시:

```text
seq_id
best_hit
best_taxid
best_superkingdom
best_lineage
bitscore
evalue
tier1_label = viral | bacterial | archaeal | eukaryotic | unknown
```

보존 규칙 초안:

- `viral`: keep
- `unknown`: keep only if `geNomad score > threshold` 또는 viral hallmark ORF evidence 존재
- `bacterial / archaeal / eukaryotic`: exclude from virome report

권장 threshold 초안:

- `geNomad score >= 0.90`: high-confidence unknown keep
- `geNomad score 0.70-0.89`: only keep if 추가 evidence 존재
- `geNomad score < 0.70`: 기본 exclude 또는 low-confidence bucket

여기서 중요한 점은 `unknown`을 무조건 버리지 않는 것이다. novel virus 가능성을 남기되, 현재처럼 모든 미분류 contig를 virome dashboard에 올리지는 않는다.

#### Tier 2: Viral-specific classification

Tier 1에서 살아남은 contig만 기존 viral annotation stack으로 넘긴다.

권장 구성:

- `MMseqs2 taxonomy` against viral-specific DB
- `geNomad end-to-end`
- `Diamond` against `UniRef90 viral subset`
- 필요 시 `CheckV`, `Prodigal`, ORF-level best hit annotation

Tier 2의 목적은 `viral 여부 판정`이 아니라 `viral taxonomy refinement`다.

즉:

- Tier 1 = exclusion / gatekeeping
- Tier 2 = detailed virome annotation

### 1.4 Decision Logic for Contig Retention

권장 contig retention policy는 rule-based로 시작하는 것이 안전하다.

#### Keep

- Tier 1에서 `viral`
- Tier 1에서 `unknown`이지만 `geNomad high confidence`
- Tier 1에서 `unknown`이지만 `viral hallmark genes`, `multiple viral ORFs`, `CheckV support` 존재

#### Exclude from virome report

- Tier 1에서 `bacterial`, `archaeal`, `eukaryotic`
- host-associated repeat / transposase-rich contig
- low-complexity / short fragment only

#### Separate review bucket

- `unknown` + borderline geNomad
- viral/non-viral conflicting evidence
- very short but high-scoring ORF fragment

이 `review bucket`은 dashboard 본문이 아니라 별도 TSV 또는 QC appendix로 분리하는 것이 맞다.

### 1.5 Alternative: Hecatomb-style Pre-Assembly Filtering

Hecatomb식 전략을 더 강하게 적용하려면 pre-assembly 단계에서도 non-viral filtering을 수행할 수 있다.

#### Option A: Read-level prefilter before assembly

```text
Raw reads
  -> Host removal
  -> Kraken2 / Kaiju / translated search against nt/nr-lite
  -> remove obvious bacterial/plant/fungal reads
  -> assemble residual reads
  -> contig-level Tier 1 + Tier 2
```

장점:

- assembly 자체가 cleaner해진다
- non-viral contig burden이 줄어든다
- co-assembly chimeric background를 줄일 수 있다

단점:

- novel virus read가 non-viral로 잘못 제거될 리스크가 있다
- read-level classification cost가 커진다
- database 운영 복잡도가 상승한다

#### Option B: Assembly-first multi-DB classification

```text
Raw reads
  -> Host removal
  -> Assembly
  -> Tier 1 multikingdom contig classification
  -> Tier 2 viral-specific annotation
```

장점:

- 현재 구조를 가장 적게 깨뜨린다
- 구현 난이도와 재현성이 높다
- co-assembly workflow와 잘 맞는다

단점:

- assembly에 이미 non-viral sequence가 포함된 뒤 filtering이 이루어진다

현재 DeepInvirus에는 **Option B를 우선 적용**하는 것이 현실적이다. 이후 Phase 3에서 Option A를 실험적으로 도입하는 것이 좋다.

### 1.6 New Nextflow Modules Needed

v2 pipeline에는 최소 아래 모듈이 필요하다.

#### `DIAMOND_NR`

역할:

- contig FASTA 또는 predicted ORF protein을 `NR / UniRef100 / exclusion DB`에 search
- best hit 및 top-k hit를 산출
- superkingdom / lineage 요약 컬럼 생성

입력:

- `coassembly.contigs.fa`
- optional predicted proteins
- Tier 1 DB path

출력:

- `diamond_nr.tsv`
- `diamond_nr.top_hits.tsv`

#### `CLASSIFY_CONTIGS`

역할:

- Tier 1 result + geNomad score + optional ORF evidence를 결합
- contig를 `viral / non-viral / unknown / review`로 분류
- keep/exclude list 생성

입력:

- `diamond_nr.tsv`
- `genomad_summary.tsv`
- optional `checkv.tsv`, `orf_annotation.tsv`

출력:

- `contig_classification.tsv`
- `viral_keep.list`
- `nonviral_exclude.list`
- `review_bucket.tsv`

#### Filter step between Detection and Classification

현재 Detection 후 Classification으로 바로 넘어가는 지점 사이에 filtering gate가 들어가야 한다.

```text
DETECTION
  -> TIER1_MULTIDB
  -> CLASSIFY_CONTIGS
  -> FILTER_KEEP_CONTIGS
  -> VIRAL_CLASSIFICATION
  -> MERGE_RESULTS
```

즉, dashboard와 report는 `filtered viral set`만 기본 입력으로 사용해야 한다.

### 1.7 Database Requirements

실제 운영 관점에서 DB 선택은 정확도만이 아니라 storage / update cadence / reproducibility의 문제다.

#### Option 1: `NCBI NR` or `UniRef100`

장점:

- 가장 포괄적이다
- contig가 viral이 아닌 이유를 찾기 쉽다
- novel sequence 주변 문맥 해석력이 높다

단점:

- 매우 크다
- build/update 비용이 높다
- HPC I/O 부담이 크다

예상 규모:

- `NCBI NR` 또는 `UniRef100`: 대략 `60-100+ GB` class 이상으로 운영 고려 필요

#### Option 2: Curated exclusion DB

예시:

- bacteria
- fungi
- plants
- common eukaryotic contaminants
- host-adjacent mobile genetic elements

장점:

- 훨씬 가볍다
- 빠르다
- 운영이 쉽다

단점:

- false negative exclusion risk
- taxonomy completeness가 떨어질 수 있다

예상 규모:

- curated `Diamond exclusion DB`: 대략 `~20 GB` 수준 목표 가능

#### Option 3: Read-level `Kraken2 / Kaiju` first

장점:

- 빠른 screening
- 기존 `260319_kraken2_analysis` 자산과 연결 가능

단점:

- k-mer 기반은 divergent virus에 약하다
- contig-level ORF evidence보다 해석력이 떨어질 수 있다

권장 전략:

1. Phase 2에서는 `contig-level DIAMOND_NR` 중심으로 시작
2. storage/compute가 제한되면 curated `exclusion DB`를 fallback으로 제공
3. Phase 3에서 `Kraken2 / Kaiju prefilter`를 optional branch로 추가

### 1.8 Expected Output Schema Changes

기존 `bigtable.tsv`만으로는 filtering provenance를 추적하기 어렵다. 아래 컬럼 추가를 권장한다.

```text
tier1_label
tier1_best_hit
tier1_best_taxid
tier1_superkingdom
tier1_lineage
tier1_bitscore
tier1_evalue
filter_decision
filter_reason
viral_evidence_score
nonviral_evidence_score
review_flag
```

이 메타데이터가 있어야 dashboard에서 `왜 이 contig가 포함/제외되었는지`를 설명할 수 있다.

### 1.9 Why This Should Reduce the 98.5% Unclassified Problem

현재의 `98.5% Unclassified`는 모두 taxonomy depth 부족 때문이 아니다. 상당수는 실제로 virome report에 들어오면 안 되는 contig일 가능성이 높다.

v2에서는 다음 변화가 기대된다.

- `non-viral contig`가 report에서 제거된다
- 남는 `unknown`은 더 작지만 더 biologically plausible한 집합이 된다
- sunburst와 comparison tab은 viral signal 중심으로 정리된다
- user가 보는 `Unclassified`는 "미지의 바이러스 후보"에 가까워지고, "분류 실패한 전체 잡음"이 아니게 된다

즉, 목표는 `Unclassified를 0으로 만드는 것`이 아니라, **Unclassified의 의미를 정제하는 것**이다.

---

## 2. Dashboard v3 Features

### 2.1 ICTV Color Scheme

현재 dashboard 색상은 generic palette 기반이며, sample마다 동일 family가 동일 색으로 보인다는 보장이 약하다. v3에서는 `ICTV-based fixed family color mapping`을 canonical rule로 채택해야 한다.

핵심 원칙:

- 동일한 `family`는 모든 sample, 모든 tab, 모든 chart에서 항상 같은 색을 사용한다.
- `Viruses` 아래에서 drilling할 때 `phylum` 또는 `family` branch는 서로 구분 가능한 distinct color를 가져야 한다.
- `family` 아래 rank (`genus`, `species`, `contig`)는 새로운 색을 만들지 않고 **해당 family의 base color를 상속**한다.
- `Unclassified`, `Unknown`, `Review`는 별도 neutral gray 계열로 고정한다.

권장 구현 규칙:

1. `assets/ictv_family_colors.json` 또는 Python dict로 canonical palette 정의
2. family가 color mapping에 없으면 deterministic fallback color 생성
3. phylum-level node는 family palette를 cluster-aware하게 배정하거나 phylum anchor color 사용
4. genus/species/contig는 family color의 동일 색상 사용 또는 lightness만 미세 조정

권장 데이터 구조:

```json
{
  "Dicistroviridae": "#D95F02",
  "Iflaviridae": "#1B9E77",
  "Parvoviridae": "#7570B3",
  "Baculoviridae": "#E7298A",
  "Unknown": "#9CA3AF",
  "Unclassified": "#6B7280"
}
```

적용 대상:

- Sunburst
- Treemap
- Sankey
- Comparison tab bar/line chart
- Search table badges
- Contig detail modal taxonomy chips

추가 메모:

- ICTV가 family마다 공식 색상을 제공하는 것은 아니므로, 여기서 말하는 `ICTV-based`는 `ICTV taxonomy anchored fixed color system`으로 해석하는 것이 맞다.
- 즉, ICTV classification을 기준으로 family identity를 고정하고, 그 family identity에 프로젝트 고정 색상을 부여하는 방식이다.

### 2.2 Comparison Tab Design

새 `Comparison` tab은 "sample 간 virome signal 차이"를 빠르게 보는 핵심 화면이어야 한다.

핵심 기능:

- 특정 virus 또는 taxon 검색
- family / genus / species / contig 단위 전환
- sample 간 `RPM` 비교
- 검색 대상이 없는 sample도 `0 RPM`으로 명시
- co-assembly contig 기준으로 동일 바이러스의 sample별 abundance 비교

권장 UI 구성:

#### Top control bar

- `Taxon search box`
- `Rank selector`: family / genus / species / contig
- `Metric selector`: RPM / coverage / breadth
- `Sample multi-select`
- `Show only detected`
- `Log scale toggle`

#### Main panels

1. `Search result comparison chart`
   - 선택한 virus/taxon의 sample별 RPM bar chart
   - sample 수가 많으면 dot plot 또는 lollipop plot 지원

2. `Top differential taxa table`
   - sample A vs B에서 fold-change가 큰 taxon 목록
   - 컬럼: taxon, rank, rpm_A, rpm_B, log2FC, prevalence

3. `Contig drill-down`
   - taxon 클릭 시 해당 taxon을 구성하는 contig 목록
   - contig별 per-sample depth/breadth/RPM 표시

4. `Presence/absence heatmap`
   - 검색 taxon 관련 contig의 sample별 detection 패턴

권장 데이터 전처리:

- `comparison_rows.json` 또는 equivalent payload 생성
- row 단위는 `taxon x sample`
- summary view와 contig drill-down view를 분리

권장 schema:

```text
taxon_id
taxon_name
rank
family
sample
rpm
coverage
breadth
n_contigs
top_contig
```

검색 동작:

- exact match + contains match 지원
- family/genus/species alias normalization 지원
- best hit string 기반 contig 검색도 optional 지원

이 탭은 사실상 사용자가 원한 "`filter/search specific virus, compare RPM across samples`"의 전용 구현이다.

### 2.3 Contig Sequence Embedding

현재 contig detail modal은 구조는 있지만 실제 sequence data가 비어 있다. v3에서는 최소 top contig에 대해 실제 서열을 embed해야 한다.

권장 구현:

- `generate_dashboard.py`에서 `co-assembly FASTA`를 직접 읽는다
- `top 200 contigs by RPM` 또는 `top N configurable`만 JSON에 포함한다
- sequence 길이가 매우 길면 modal에서는 preview + expand 제공
- 필요 시 JSON payload size를 줄이기 위해 `base64 encoding` 또는 gzip precompression 고려

modal 표시 항목:

- contig sequence (monospace)
- length
- GC%
- ORF count
- best hit
- family / genus / species
- per-sample RPM / coverage / breadth

권장 안전장치:

- full FASTA 전체를 무제한 embed하지 않는다
- 기본값은 top 200 contigs
- 나머지는 "sequence unavailable in embedded dashboard"로 처리

추가 구현 포인트:

- ORF count는 Prodigal 결과 또는 existing annotation table에서 가져온다
- GC%는 FASTA 로딩 시 계산 가능
- 검색 테이블에서 contig 클릭 시 modal open

### 2.4 Species-level Sunburst

현재 코드 기준으로 `taxonomy_tree`는 `domain -> phylum -> class -> order -> family`까지만 기본 지원하고, genus는 일부 조건부로만 확장된다. user feedback에 맞추려면 species-level을 명시적으로 canonical hierarchy에 포함해야 한다.

목표 hierarchy:

```text
domain -> phylum -> class -> order -> family -> genus -> species
```

구현 원칙:

- `MMseqs2 / Diamond best hit`에서 species가 있으면 species node 생성
- genus는 있으나 species가 없으면 `Genus sp.` placeholder 생성
- family 이하 정보가 부족한 contig는 가능한 가장 낮은 known rank에 연결
- contig 자체를 leaf로 넣을지는 toggle 옵션으로 분리

권장 수정 포인트:

- `generate_dashboard.py`의 `build_taxonomy_tree()` ranks 확장
- search row와 taxonomy payload 모두 `species`를 first-class field로 처리
- template의 `sunburst maxdepth`를 rank depth selector와 연동

UX 원칙:

- 기본 뷰는 family 또는 genus depth
- 사용자가 `Show species-level` 또는 `Rank depth = species`를 선택할 때만 species ring 표시
- 너무 촘촘하면 label overlap을 피하기 위해 tooltip 중심으로 표시

이 기능은 단순히 chart level 변경이 아니라, downstream taxonomy parsing과 placeholder policy를 함께 정의해야 한다.

---

## 3. Implementation Roadmap

### Phase 1: Dashboard-first Upgrade (no pipeline change)

목표는 현재 산출물 위에서 빠르게 user-visible value를 만드는 것이다.

범위:

- ICTV fixed family color scheme
- Comparison tab
- Species in sunburst
- Contig sequence embedding

세부 작업:

1. `generate_dashboard.py`
   - taxonomy tree ranks를 species까지 확장
   - comparison payload 생성
   - contig FASTA 로딩 및 top-N sequence embed
   - family color map payload 생성

2. `assets/dashboard_template.html`
   - taxonomy chart color rule 일원화
   - `Comparison` tab 추가
   - contig modal sequence/GC/ORF display 추가
   - rank depth / virus search controls 추가

3. Supporting assets
   - `ictv_family_colors.json` 또는 equivalent static mapping 정의

산출물:

- dashboard v3 prototype
- 기존 데이터로도 동작 가능한 UI/UX upgrade

제한:

- pipeline filtering이 바뀌지 않으므로 `Unclassified` burden 자체는 크게 줄지 않을 수 있다

### Phase 2: Pipeline Enhancement

목표는 virome report input 자체를 정제하는 것이다.

범위:

- `DIAMOND_NR` module 추가
- `CLASSIFY_CONTIGS` script 추가
- Detection과 Classification 사이 filtering gate 추가
- non-viral contig 제거 후 전체 분석 재실행

세부 작업:

1. Nextflow
   - `modules/local/diamond_nr.nf` 신규
   - `subworkflows/classification.nf` 또는 detection/classification bridge 수정
   - parameter: `--tier1_db`, `--tier1_mode`, `--keep_unknown_genomad_threshold`

2. Python scripts
   - `bin/classify_contigs.py` 신규
   - `bin/merge_results.py`에 Tier 1 provenance 컬럼 통합

3. Output contract
   - `contig_classification.tsv`
   - `viral_keep.list`
   - `review_bucket.tsv`
   - filtered `bigtable.tsv`

4. Validation
   - 현재 dataset 재실행
   - `Unclassified fraction before vs after`
   - retained viral contig count
   - family/species composition 변화 확인

성공 기준:

- virome dashboard에서 non-viral background가 유의하게 감소
- `Unclassified`가 줄거나, 남더라도 biologically plausible unknown candidate 중심으로 정리

### Phase 3: Advanced Filtering and Cross-validation

목표는 Hecatomb에 더 가까운 robust multi-layer filtering으로 확장하는 것이다.

범위:

- read-level `Kraken2` classification prefilter
- 기존 `260319_kraken2_analysis` 결과와 통합
- cross-method validation report 작성

세부 작업:

1. Pre-assembly filter branch
   - `Kraken2 / Kaiju` optional module
   - bacterial/plant/fungal abundant read 제거

2. Existing asset reuse
   - 현재 `260319_kraken2_analysis` 결과를 contamination prior로 사용
   - sample-specific background profile 구축

3. Cross-method validation
   - geNomad vs Tier 1 NR vs Kraken2 concordance table
   - retained viral contig evidence summary
   - excluded contig 이유 분포

4. Advanced reporting
   - `why excluded?` appendix
   - `unknown but kept` candidate report
   - method agreement/conflict heatmap

---

## 4. Recommended Execution Order

실행 우선순위는 다음이 가장 합리적이다.

1. Dashboard v3 feature를 먼저 구현한다.
2. 동시에 Tier 1 filtering 설계를 코드 레벨로 넣는다.
3. 현재 dataset에 대해 Phase 2 재실행을 수행한다.
4. 결과를 기반으로 threshold와 keep/exclude rule을 재조정한다.
5. 그 다음에 read-level prefilter를 optional branch로 실험한다.

이 순서를 권장하는 이유는 다음과 같다.

- user feedback 중 절반은 dashboard issue이므로 즉시 개선 가능하다
- multi-DB filtering은 compute cost가 크므로 UI/contract를 먼저 안정화하는 편이 낫다
- filtering rule은 실제 재실행 결과를 보면서 조정해야 한다

---

## 5. Risks and Design Decisions

### 주요 리스크

- `NR / UniRef100` 운영 비용이 생각보다 크다
- novel virus가 Tier 1에서 `unknown` 또는 심지어 non-viral로 잘못 떨어질 수 있다
- exclusion rule이 너무 공격적이면 실제 viral dark matter를 잃을 수 있다
- dashboard JSON에 sequence embedding을 과도하게 넣으면 HTML size가 커진다

### 대응 전략

- unknown keep rule을 명시적으로 둔다
- Phase 2에서는 contig-level filtering만 먼저 적용한다
- review bucket을 유지하여 hard discard를 최소화한다
- dashboard는 top-N contig sequence만 embed한다

### 핵심 설계 결정

- DeepInvirus v2는 `viral-only classification pipeline`에서 `multi-DB evidence pipeline`으로 전환한다.
- report의 기본 대상은 `all candidate contigs`가 아니라 `filtered viral set`이다.
- `Unclassified`는 남을 수 있지만, 그 의미는 `noise`가 아니라 `unknown viral candidate`가 되어야 한다.

---

## 6. References

- Hecatomb paper: Wood et al., *Hecatomb: an integrated software platform for viral metagenomics*, 2024, PMC11148595
- 핵심 개념:
  - tiered alignment-based taxonomic assignment
  - virus-first capture + multikingdom cross-check
  - false-positive viral annotation reduction

