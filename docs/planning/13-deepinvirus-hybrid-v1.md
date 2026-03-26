# DeepInvirus Hybrid v1 — Complete Pipeline Redesign

> 작성일: 2026-03-25
> 배경: Hecatomb-style iterative search 전략, Kraken2 triage 철학, geNomad ML detection, dashboard/report 통합 요구 반영
> 범위: DeepInvirus의 detection, classification, evidence integration, visualization, reporting 전면 재설계

---

## 0. Executive Summary

DeepInvirus Hybrid v1은 기존의 "`viral-only hit가 있으면 viral 후보`" 중심 구조를 넘어, **ML detection + homology search + exclusion evidence + read composition evidence**를 하나의 분석 체계로 통합하는 파이프라인이다.

이 설계의 핵심은 다음 5가지다.

1. **Annotate everything, remove nothing**
   모든 contig와 모든 evidence는 저장한다. 자동 삭제는 하지 않는다. virome report에 무엇을 보여줄지는 classification rule과 visualization layer가 결정한다.
2. **Two independent analysis sections**
   - **Section A (Assembly-based Virome)**: geNomad ML + Diamond/BLAST 4-tier → 바이러스 탐지/분류의 핵심
   - **Section B (Read-based Profiling)**: Kraken2 + Bracken → 전체 미생물 프로필 (별도 섹션, virome 판정에 관여하지 않음)
   서로 다른 원리(protein/ML vs k-mer/NT)의 결과를 억지로 통합하지 않고, 나란히 보여준다.
3. **Assembly uses ALL reads (no Kraken2 filtering)**
   전체 host-depleted reads로 assembly. Kraken2에 의한 read 제거 없음. Prophage, integrated virus, novel virus를 놓치지 않는다.
4. **geNomad runs on full assembly before filtering**
   assembly 결과 전체에 대해 geNomad를 먼저 수행하여, homology가 약한 novel viral candidate도 놓치지 않는다.
5. **Hecatomb-style iterative verification**
   viral-first search로 sensitivity를 확보하고, all-kingdom exclusion search로 specificity를 확보한다. 즉, "viral hit 존재"만 보지 않고 "`viral-first evidence`가 `cellular exclusion evidence`를 견디는가"를 본다.

Hybrid v1의 결과물은 단순 TSV 몇 개가 아니라 다음 세 가지를 공유하는 통합 분석 산출물이다.

- `bigtable v2`: 모든 contig x sample evidence를 담는 single source of truth
- `dashboard v4`: per-sample interactive exploration, QA plot, IGV-style contig viewer
- `report v3`: dashboard와 동일 데이터를 재사용하는 Word report

이 문서는 위 구조를 Nextflow DAG, database architecture, evidence model, visualization contract, 구현 단계로 구체화한 definitive plan이다.

---

## 1. Design Philosophy

### 1.1 Annotate Everything, Remove Nothing

Hybrid v1은 Hecatomb 철학을 계승하여, pipeline 내부에서 evidence가 약하거나 상충된 contig를 자동으로 폐기하지 않는다.

- contig는 `strong_viral`, `novel_viral_candidate`, `ambiguous`, `cellular`, `unknown`으로 분류되더라도 모두 bigtable에 남는다.
- Kraken2, geNomad, Diamond, BLAST, CheckV, CoverM 결과는 서로를 덮어쓰지 않고 병렬 evidence로 보존된다.
- 최종 사용자 필터링은 dashboard와 report에서 수행된다.
- 즉, pipeline의 역할은 "`버리기`"가 아니라 "`설명 가능한 annotation graph 만들기`"다.

이 철학이 중요한 이유는 viral discovery에서는 false positive만큼 false negative도 치명적이기 때문이다. early-stage hard filter는 novel virus, divergent virus, fragmented RNA virus를 쉽게 잃게 만든다.

### 1.2 ML + Homology + Evidence Integration

DeepInvirus의 고유성은 geNomad 같은 ML detector와 Hecatomb-style iterative homology search를 한 단계 더 나아가 **evidence integration engine**으로 결합하는 데 있다.

- geNomad는 sequence intrinsic feature 기반의 virus-like signal을 제공한다.
- Tier 1/3 viral-first search는 known viral homology를 제공한다.
- Tier 2/4 exclusion search는 cellular/non-viral alternative explanation을 제공한다.
- Kraken2 read composition은 contig를 지지하는 read population의 taxonomic context를 제공한다.
- CheckV와 coverage profile은 biological plausibility와 reconstruction quality를 보강한다.

결국 Hybrid v1의 최종 classification은 "`하나의 tool 결과`"가 아니라, 여러 evidence의 일관성 여부로 결정된다.

### 1.3 Transparency Through Visualization

Hybrid v1은 내부적으로 복잡한 rule engine을 갖지만, 사용자 경험은 black box가 아니라 transparent investigation workflow여야 한다.

- QA plot에서 alignment length와 percent identity를 직접 본다.
- IGV-style contig viewer에서 coverage, ORF, read composition, sequence를 한 화면에서 본다.
- per-sample tab을 통해 동일 contig가 샘플별로 어떻게 달라지는지 본다.
- evidence chain이 자연어 형태로 제공되어 classification 근거를 추적할 수 있다.

즉, DeepInvirus는 최종 답만 제공하는 도구가 아니라, 사용자가 직접 filtering threshold와 biological plausibility를 판단할 수 있게 만드는 분석 workbench다.

### 1.4 Kraken2 as Independent Profiling, Not Integrated Filter

Kraken2는 k-mer(NT) 기반 read-level 분류 도구로, 빠르고 넓은 taxonomy signal을 제공한다. 그러나 novel/divergent virus를 놓치기 쉽고(exact k-mer match 한계), protein-level 유사성이나 ML 기반 탐지와는 원리가 근본적으로 다르다.

**따라서 Hybrid v1에서 Kraken2는 virome 탐지 파이프라인과 통합하지 않고, 독립된 분석 섹션으로 분리한다.**

#### 분리 근거
1. **원리가 다르다**: Kraken2(k-mer/NT) vs Diamond(protein alignment) vs geNomad(ML) — 서로 다른 원리의 결과를 하나의 판정에 억지로 합치면 해석이 혼란스러워진다.
2. **novel virus를 놓친다**: Kraken2는 DB에 없는 서열을 "unclassified"로 처리한다. 이것이 novel virus일 수 있으므로 Kraken2 결과를 contig 판정에 사용하면 안 된다.
3. **역할이 다르다**: virome 파이프라인은 "어떤 바이러스가 있는가" (high specificity), Kraken2는 "전체 시료의 미생물 구성이 어떤가" (broad context).

#### Kraken2의 역할 (독립 섹션)
- **Section A (Assembly-based Virome)**: geNomad + Diamond 4-tier + CheckV + CoverM → viral bigtable → dashboard/report
- **Section B (Read-based Profiling, 별도)**: Kraken2 + Bracken → 전체 미생물 프로필 → Krona plot → 샘플별 비교

#### Assembly 전략
- Assembly에는 **전체 reads를 사용** (Kraken2에 의한 filtering 없음)
- Kraken2 discovery set 분리는 하지 않음 — prophage, integrated viral element를 놓칠 위험 제거
- co-assembly로 모든 reads를 통합하여 최대 sensitivity 확보

#### Dashboard에서의 표현
```
탭: [Overview] [Taxonomy] [Coverage] [Diversity] [Comparison] [Search] [Kraken2 Profiling] [Contig Viewer] [Results]
                                                                        ↑ 독립 섹션
```

`Kraken2 Profiling` 탭에서:
- 전체 시료 미생물 조성 (stacked bar: bacteria/virus/fungi/plant/archaea/unclassified)
- 샘플별 비교
- Bracken species-level abundance
- Krona interactive plot (가능하면 인라인)
- Section A (virome)와의 교차 비교: "virome에서 잡은 바이러스가 Kraken2에서도 보이는가?"

---

## 2. Pipeline Architecture (Nextflow DAG)

Hybrid v1의 전체 흐름은 다음과 같다.

```text
Input reads
  -> Preprocessing
  -> Host removal
  -> Kraken2 annotation
  -> Discovery set extraction
  -> Assembly
  -> geNomad on full assembly
  -> Prodigal ORF prediction
  -> Tier 1 AA viral-first search
  -> Tier 2 AA exclusion search
  -> Tier 3 NT viral-first search
  -> Tier 4 NT exclusion search
  -> Evidence integration
  -> CheckV / coverage quantification / depth profiling
  -> bigtable v2
  -> dashboard v4 / report v3
```

이 DAG는 "후보 생성"과 "후보 검증"을 분리하는 것이 핵심이다.

- 후보 생성: geNomad + viral-first AA/NT search
- 후보 검증: UniRef50 + polymicrobial NT + read composition + CheckV + coverage

### 2.1 Stage 1: Preprocessing

입력 reads는 먼저 quality cleaning과 host depletion을 거치지만, taxonomy 정보는 이 단계에서 제거 용도로 사용하지 않는다.

권장 흐름:

```text
reads
  -> BBDuk or fastp
  -> minimap2 host removal
  -> Kraken2 PlusPFP classification on host-depleted reads
```

핵심 원칙:

- `BBDuk/fastp`: adapter trimming, low-quality tail trimming, minimum length filtering
- `minimap2`: host genome에 매핑되는 read 제거
- `Kraken2 PlusPFP`: host-depleted read 전체에 대해 annotation 수행

Kraken2 출력은 최소 다음 산출물을 만들어야 한다.

- per-read classification
- per-sample kingdom composition summary
- discovery set extraction용 label table
- downstream contig remap annotation용 read-taxid mapping

### 2.2 Stage 2: Assembly

**Assembly에는 전체 host-depleted reads를 사용한다.** Kraken2 기반 read filtering은 수행하지 않는다.

#### 전체 reads를 사용하는 이유

1. **Prophage/integrated virus 보존**: bacterial read를 제거하면 prophage를 포함한 contig이 assembly되지 않는다.
2. **Novel virus 보존**: Kraken2 DB에 없는 novel virus read가 "unclassified"가 아닌 가장 가까운 cellular organism으로 잘못 분류될 수 있다. 제거하면 복구 불가.
3. **Assembly 품질**: 더 많은 reads = 더 높은 coverage = 더 완전한 contig. 특히 저농도 바이러스에 critical.
4. **단순함**: Kraken2 의존성 없이 assembly 가능. Kraken2 DB가 없어도 파이프라인 동작.

#### 구조

```text
host-depleted reads (전체)
  -> MEGAHIT co-assembly (모든 샘플 통합)
  -> contigs
  -> CoverM per-sample remapping (개별 샘플 reads → co-assembly contigs)
```

#### Kraken2와의 관계

Kraken2는 assembly와 무관하게 독립 실행된다:
```text
host-depleted reads → Kraken2 (annotation only) → kraken2_report + kraken2_output
                   → MEGAHIT co-assembly (전체 reads) → contigs → virome analysis
```

두 결과는 최종 dashboard에서 나란히 표시되지만, 서로를 필터링하거나 영향을 주지 않는다.

### 2.3 Stage 3: Detection on Full Assembly, Before Any Filtering

Assembly 이후의 **full contig set 전체**에 대해 geNomad와 ORF prediction을 수행한다. 이 단계에서는 어떠한 classification filter도 적용하지 않는다.

```text
contigs
  -> geNomad
  -> Prodigal
```

왜 full assembly에 geNomad를 먼저 적용해야 하는가:

- homology 없는 novel viral sequence를 먼저 포착할 수 있다.
- 이후 AA/NT tier에서 miss된 contig도 `novel_viral_candidate`로 남길 수 있다.
- filtering 전에 ML signal을 확보해야 evidence integration에서 bias가 줄어든다.

필수 geNomad 출력:

- virus score
- plasmid score
- provirus flag
- gene-level annotation if available

필수 Prodigal 출력:

- ORF 좌표
- strand/frame
- translated amino acid FASTA
- GFF

### 2.4 Stage 4: Iterative Classification (Hecatomb-style 4-tier)

Hybrid v1의 중심은 4-tier iterative search다. 이 구조는 viral-first sensitivity와 exclusion specificity를 분리한다.

#### Tier 1 AA: Viral Protein Search

입력:

- contig-derived ORFs

검색:

- `Diamond blastx` 또는 ORF 기반 `Diamond blastp/blastx`
- DB: GenBank viral proteins, 99% clustered

목표:

- known viral protein homology를 최대한 민감하게 포착
- broad viral family/genus signal 확보

권장 해석:

- aa1 hit가 존재하면 "`viral-first evidence present`"로 간주
- 단, 이것만으로 final viral call을 하지 않는다

#### Tier 2 AA: UniRef50 Verification

입력:

- Tier 1에서 viral hit가 나온 contig/ORF

검색:

- `Diamond blastx`
- DB: UniRef50 with taxonomy across all kingdoms

목표:

- Tier 1 viral hit가 실제로는 conserved cellular protein인지 확인
- all-kingdom 대안 설명이 있는지 평가

핵심 질문:

- viral protein best hit가 UniRef50에서 여전히 viral lineage로 유지되는가
- 더 높은 bitscore/coverage로 bacterial, fungal, plant, eukaryotic hit가 나오는가

#### Tier 3 NT: Viral Nucleotide Search

입력:

- Tier 1/2 AA에서 명확한 viral support를 받지 못한 contig
- 또는 short ORF-poor contig

검색:

- `blastn`
- DB: GenBank viral nucleotide, 100% deduplicated, all variants retained

목표:

- AA-level에서는 놓치는 divergent/non-coding/small-genome virus를 포착
- strain-level or segment-level nucleotide evidence 확보

Tier 3가 필요한 이유:

- RNA virus의 일부 segment는 protein-level signal이 약할 수 있다.
- non-coding UTR-rich contig는 AA search만으로는 분류가 어렵다.
- exact or near-exact viral nucleotide match는 강력한 known-virus evidence다.

#### Tier 4 NT: Polymicrobial Verification

입력:

- Tier 3에서 viral nucleotide hit를 얻은 contig

검색:

- `blastn`
- DB: polymicrobial NT DB (RefSeq representative bacteria, archaea, fungi, plants, protozoa)

목표:

- viral NT hit가 low-complexity/shared domain/repeat 때문인지 확인
- non-viral genome에 더 적절한 nucleotide explanation이 있는지 확인

핵심 해석:

- nt1 viral hit가 있고 nt2에서 의미 있는 cellular best hit가 없으면 viral support 강화
- nt2에서 긴 정렬 길이와 높은 identity의 cellular hit가 우세하면 ambiguous 또는 cellular로 이동

### 2.5 Stage 5: Evidence Integration

`classify_contigs.py` v2는 Hybrid v1의 decision engine이다.

입력:

- geNomad scores
- Tier 1 AA viral-first results
- Tier 2 AA exclusion results
- Tier 3 NT viral-first results
- Tier 4 NT exclusion results
- Kraken2 read composition
- optional CheckV and coverage signals

출력:

- per-contig final classification
- evidence chain
- best taxonomic assignment
- confidence label

핵심 classification category:

- `strong_viral`
- `novel_viral_candidate`
- `ambiguous`
- `cellular`
- `unknown`

이 단계는 hard-coded one-rule filter가 아니라 score/rule hybrid 방식으로 설계하는 것이 바람직하다.

예시 규칙:

- `strong_viral`
  - `geNomad virus score >= 0.7`
  - AND (`aa1 viral hit` OR `nt1 viral hit`)
  - AND no strong exclusion from `aa2` or `nt2`
- `novel_viral_candidate`
  - `geNomad virus score >= 0.7`
  - AND no convincing cellular evidence
  - AND homology absent or weak
- `ambiguous`
  - viral-first evidence와 cellular exclusion evidence가 모두 존재
  - 또는 sample/read composition/coverage가 혼재된 경우
- `cellular`
  - aa2 또는 nt2에서 cellular explanation이 더 강함
  - geNomad signal이 낮거나 없음
- `unknown`
  - geNomad 약함
  - viral homology 없음
  - cellular evidence도 없음

### 2.6 Stage 6: Quality and Quantification

Final classification 이후에도 contig의 생물학적 신뢰도와 샘플별 존재량을 계량화해야 한다.

구성:

- `CheckV`: completeness, contamination, provirus 여부
- `CoverM`: per-sample coverage depth, breadth, mapped read count, RPM
- `samtools depth`: top contig에 대한 per-base depth profile

분석 목표:

- same contig across samples 비교
- low-depth fragment와 genuinely abundant viral contig 구분
- report/dashboard에서 biological plausibility 제시

per-sample detection confidence는 다음처럼 rule-based로 파생 가능하다.

- `high`: breadth와 depth 모두 threshold 이상
- `medium`: breadth 또는 depth 중 하나만 충족
- `low`: read count 존재하나 breadth/depth 미약

### 2.7 Stage 7: Reporting

최종 보고 단계는 단순 export가 아니라 **shared data contract 기반의 이중 출력**이어야 한다.

- `merge_results.py`: 모든 분석 결과를 bigtable v2로 통합
- `generate_dashboard.py`: interactive HTML dashboard v4 생성
- `generate_report.py`: Word report v3 생성

원칙:

- report와 dashboard는 동일 bigtable 및 figure manifest를 사용
- static figure는 interactive dashboard view에 대응되어야 함
- sample-specific tab, contig viewer, QA plot, funnel plot이 report에도 반영되어야 함

---

## 3. Bigtable v2 Schema

bigtable은 Hybrid v1의 **single source of truth**다. 파이프라인의 모든 핵심 evidence는 여기에 명시적으로 저장되어야 하며, dashboard/report는 이를 재조합할 뿐 별도 truth table을 가지면 안 된다.

Hybrid v1에서는 개념적으로 `contig master table`과 `contig_sample quant table`을 유지하더라도, 사용자 노출 관점에서는 **one row per contig x sample** 형태의 wide table이 가장 실용적이다.

### 3.1 Core Principles

- 모든 contig는 최소 1행을 가진다.
- 샘플별 정량 지표는 `contig x sample` row에 저장한다.
- contig-level invariant 값은 각 샘플 row에 반복 저장해도 된다.
- NA는 "`미실행`", "`hit 없음`", "`해당 tier 대상 아님`"을 구분할 수 있어야 한다.
- evidence column naming은 tier-aware하고 stable해야 한다.

### 3.2 Required Columns

#### Contig identity

- `seq_id`
- `length`
- `gc_content`
- `n_orfs`

#### Detection evidence

- `genomad_virus_score`
- `genomad_plasmid_score`
- `genomad_provirus`

#### Tier 1 AA (viral protein search)

- `aa1_hit`
- `aa1_pident`
- `aa1_evalue`
- `aa1_bitscore`
- `aa1_alnlen`
- `aa1_taxid`
- `aa1_taxonomy`

#### Tier 2 AA (UniRef50 verification)

- `aa2_hit`
- `aa2_pident`
- `aa2_evalue`
- `aa2_bitscore`
- `aa2_alnlen`
- `aa2_taxid`
- `aa2_kingdom`

#### Tier 3 NT (viral nucleotide search)

- `nt1_hit`
- `nt1_pident`
- `nt1_evalue`
- `nt1_bitscore`
- `nt1_alnlen`
- `nt1_taxid`
- `nt1_taxonomy`

#### Tier 4 NT (polymicrobial verification)

- `nt2_hit`
- `nt2_pident`
- `nt2_evalue`
- `nt2_bitscore`
- `nt2_alnlen`
- `nt2_taxid`
- `nt2_kingdom`

#### Classification

- `classification`
- `evidence_chain`
- `family`
- `genus`
- `species`
- `ictv_classification`
- `baltimore_group`

#### Kraken2 read composition (per-sample)

- `kraken2_viral_pct`
- `kraken2_bacterial_pct`
- `kraken2_fungal_pct`
- `kraken2_unclassified_pct`

#### Per-sample quantification

- `sample`
- `coverage_depth`
- `coverage_breadth`
- `rpm`
- `read_count`
- `detection_confidence`

#### Quality (CheckV)

- `checkv_quality`
- `completeness`
- `contamination`
- `provirus_flag`

### 3.3 Strongly Recommended Additional Columns

운영과 해석 편의를 위해 다음 컬럼도 추가하는 것이 좋다.

- `assembly_source`
  - `discovery_coassembly`, `all_reads_coassembly`, `sample_assembly` 등
- `classification_score`
  - rule engine 내부 점수 또는 normalized confidence
- `best_support_tier`
  - `aa1`, `aa2`, `nt1`, `nt2`, `genomad_only`
- `has_viral_hallmark_orf`
- `orf_density`
- `top_orf_annotation`
- `contig_rank`
  - dashboard depth plot 저장 우선순위용
- `depth_profile_available`
- `orf_track_available`
- `sequence_available`

### 3.4 Evidence Chain Design

`evidence_chain`은 사람이 바로 읽을 수 있는 summary string이어야 한다. 예:

```text
geNomad=0.93; AA1=Dicistroviridae capsid protein (pident 61, aln 284aa); AA2=no stronger cellular hit; NT1=Invertebrate dicistrovirus segment (pident 82, aln 923nt); NT2=no cellular match; Kraken2 reads=viral 46%, unclassified 51%; final=strong_viral
```

이 컬럼은 dashboard hover, report appendix, manual review에서 매우 중요하다.

### 3.5 Storage Model Considerations

bigtable 자체는 TSV/Parquet dual output을 권장한다.

- `TSV`: debugging, quick grep, interoperability
- `Parquet`: dashboard/report ingestion 속도, large dataset scalability

권장 산출물:

- `taxonomy/bigtable.tsv`
- `taxonomy/bigtable.parquet`
- `taxonomy/contig_master.tsv`
- `taxonomy/contig_sample_quant.tsv`

사용자-facing truth는 여전히 `bigtable.tsv`로 유지하되, 내부 성능 최적화는 Parquet를 활용하는 방식이 현실적이다.

---

## 4. Database Architecture

Hybrid v1은 database strategy가 pipeline 품질을 결정한다. DB 구조는 tier 목적이 분명해야 하며, versioning과 update policy가 명시적으로 관리되어야 한다.

### 4.1 Directory Layout

```text
databases/
├── viral_protein/           # Tier 1 AA: GenBank viral proteins (99% clustered)
│   ├── viral_protein.dmnd
│   └── VERSION.json
├── uniref50/                # Tier 2 AA: UniRef50 (all kingdoms, with taxonomy)
│   ├── uniref50.dmnd
│   ├── taxonmap.gz
│   └── VERSION.json
├── viral_nucleotide/        # Tier 3 NT: GenBank viral (100% dedup, ALL variants)
│   ├── viral_nt.fna
│   ├── viral_nt.nsq
│   └── VERSION.json
├── polymicrobial_nt/        # Tier 4 NT: RefSeq representative genomes
│   ├── polymicrobial.fna
│   ├── polymicrobial.nsq
│   └── VERSION.json
├── kraken2_plusfp/          # Kraken2 PlusPFP index
│   ├── hash.k2d
│   ├── opts.k2d
│   ├── taxo.k2d
│   └── VERSION.json
├── genomad_db/              # geNomad database
├── host_genomes/            # Host genomes
├── taxonomy/
│   ├── nodes.dmp
│   ├── names.dmp
│   ├── taxonkit_data/
│   └── ictv_vmr.tsv
└── db_config.json
```

### 4.2 Tier-Specific Rationale

#### viral_protein

목적:

- Tier 1 AA viral-first detection
- broad sensitivity 확보

권장 특징:

- GenBank viral proteins 기반
- near-identical redundancy는 99% clustering으로 감소
- accession-to-taxonomy mapping 포함

#### uniref50

목적:

- Tier 2 AA all-kingdom verification
- conserved protein false positive 제거

장점:

- broad kingdom coverage
- computationally NR보다 현실적
- clustered DB라 운영 가능성 높음

제약:

- taxonomic resolution이 완전하지 않을 수 있음
- 일부 viral lineage는 cluster collapse 영향 가능

그래도 Hybrid v1의 exclusion layer로는 현실적인 최적점이다.

#### viral_nucleotide

목적:

- Tier 3 NT viral-first exact/near-exact search

권장 원칙:

- viral-only nucleotide DB
- strain/variant diversity 유지
- dedup는 identical sequence 수준에서만 수행

이 DB는 sensitivity 확보가 중요하므로 aggressive clustering은 피해야 한다.

#### polymicrobial_nt

목적:

- Tier 4 NT exclusion verification

권장 포함군:

- representative bacteria
- archaea
- fungi
- plants
- protozoa

필요 시 향후 metazoan contamination subset을 추가할 수 있지만, v1에서는 host depletion과 host genome DB가 이미 있으므로 우선순위는 낮다.

### 4.3 Version Registry and Update Strategy

`db_config.json`은 DB 운영의 중앙 registry다.

필수 필드:

- `db_name`
- `version`
- `download_date`
- `source_url`
- `build_command`
- `update_frequency`
- `last_checked`
- `status`

권장 update frequency:

- viral DBs: monthly
- taxonomy: monthly
- UniRef50: quarterly
- Kraken2 PlusPFP: quarterly
- host genomes: project-specific

필수 운영 명령:

- `install_databases.py --check-updates`
- `install_databases.py --install <db>`
- `install_databases.py --rebuild <db>`
- `install_databases.py --manifest`

### 4.4 Reproducibility Requirements

모든 run은 DB fingerprint를 output metadata에 기록해야 한다.

최소 기록 항목:

- DB version
- build date
- source snapshot date
- MD5/SHA256

report와 dashboard metadata panel에도 해당 run의 DB versions가 표시되어야 한다.

---

## 5. Dashboard v4 — IGV-style Contig Viewer

Hybrid v1 dashboard는 결과 요약 도구가 아니라 **contig investigation interface**여야 한다. 그 중심이 `IGV-style Contig Viewer`다.

### 5.1 Product Goal

사용자는 하나의 contig를 선택했을 때 최소 다음 질문에 즉시 답할 수 있어야 한다.

- coverage가 contig 전체에 고르게 분포하는가
- 특정 샘플에서만 존재하는가
- ORF 구조가 viral genome처럼 보이는가
- geNomad와 AA/NT evidence가 일관적인가
- Kraken2-mapped reads가 viral인지, mixed인지
- sequence composition이 비정상적인가

### 5.2 New Tab: Contig Viewer

필수 controls:

- contig selector: dropdown + search
- sample tabs: `[All] [sample1] [sample2] ...`
- metric toggle: depth/raw/binned
- evidence toggle: AA/NT summary expanded/collapsed

### 5.3 Panel Layout

패널은 IGV처럼 shared x-axis를 가진 stacked view로 구현한다.

#### 1. Coverage Track

- 데이터: `samtools depth` 기반 per-base 또는 100bp binned depth
- X축: contig position
- Y축: read depth
- 표시: Plotly scatter/area chart
- All sample 모드에서는 overlay, single sample 모드에서는 강조

표현 원칙:

- fill=`tozeroy`
- 툴팁에 position, depth, sample 표시
- 과도한 HTML size 방지를 위해 top N contig만 depth profile 포함

#### 2. Gene Track

- 데이터: Prodigal GFF
- ORF를 horizontal arrow 또는 rectangle로 표시
- 색상: 기능 annotation 가능하면 기능 기반, 아니면 reading frame 기반
- strand 방향을 시각적으로 구분

#### 3. Read Classification Track

- 데이터: contig에 remap된 reads의 Kraken2 label composition
- 표시: stacked bar 또는 compact pie
- 항목: viral, bacterial, fungal, unclassified, other

이 패널은 contig가 pure viral population인지 mixed population인지 직관적으로 보여준다.

#### 4. Detection Evidence Panel

- geNomad score bar
- aa1 / aa2 hit summary
- nt1 / nt2 hit summary
- final classification badge
- evidence chain text

사용자는 여기서 왜 `strong_viral`인지, 왜 `ambiguous`인지 즉시 이해할 수 있어야 한다.

#### 5. Sequence Panel

- full nucleotide sequence
- monospace scrollable display
- GC content sliding window
- copy-to-clipboard button

필요 시 future phase에서 motif search, ORF translation preview를 추가할 수 있다.

### 5.4 Data Requirements

IGV-style viewer를 위해 다음 데이터 contract가 필요하다.

- `depth_profiles.json`
  - contig별 per-base or binned depth array
- `orfs.json`
  - contig별 ORF coordinates, strand, annotation
- `contig_evidence.json`
  - geNomad + AA/NT + classification summary
- `contig_sequence.json`
  - sequence string 또는 compressed representation
- `contig_read_composition.json`
  - sample별 Kraken2 composition

대용량 HTML 문제를 줄이기 위한 권장 전략:

- top 100 contig만 inline preload
- 나머지는 lazy-load JSON chunk 또는 compressed bundle
- dashboard generation 단계에서 contig rank 기반 inclusion

### 5.5 Implementation Notes

- frontend baseline: standalone HTML + Plotly.js 유지
- ORF track은 Plotly shapes 또는 SVG overlay 활용
- lazy rendering: contig 선택 전에는 placeholder만 표시
- sample tab 변경 시 shared x-range 유지

---

## 6. Dashboard Improvements

IGV viewer 외에도 Hybrid v1은 해석 가능성을 크게 높이는 시각화 계층이 필요하다.

### 6.1 4-Quadrant QA Plot (Hecatomb-style)

이 plot은 Hecatomb의 가장 실용적인 quality view 중 하나이며, Hybrid v1에도 핵심적으로 포함되어야 한다.

- X축: alignment length (`alnlen`)
- Y축: percent identity (`pident`)
- color: kingdom (`viral`, `bacterial`, `fungal`, `plant`, `other`)
- size: `RPM` 또는 `read_count`

필수 기능:

- threshold line: `alnlen=150`, `pident=75`
- slider로 threshold 조정
- AA1, AA2, NT1, NT2 별도 패널 또는 tab
- hover에 seq_id, hit name, evalue, classification 표시

해석 의의:

- short high-identity fragment와 long moderate-identity hit를 구분
- exclusion hit의 품질을 직관적으로 확인
- novel candidate가 왜 homology-poor인지 설명 가능

### 6.2 Taxonomy Browser Enhancement

기존 taxonomy browser는 Hybrid v1에서 tier-aware하게 진화해야 한다.

필수 개선:

- Sankey / Sunburst / Treemap 유지
- tier source 표시
  - `AA1 viral hit`
  - `AA2 reclassified`
  - `NT1 viral hit`
  - `geNomad-only candidate`
- contig survival funnel 연결
- sample별 metric 전환

중요한 추가 지표:

- 각 tier를 통과한 contig 수
- viral-first hit 후 exclusion에서 탈락한 contig 수
- final classification별 contig 수

### 6.3 Comparison Tab Enhancement

co-assembly 기반 분석의 강점은 sample comparison이다.

추가 기능:

- paired dot plot: sample1 vs sample2 RPM
- volcano-style plot: `log2FC` vs abundance/significance proxy
- classification-stratified comparison
- contig-specific linked selection

이 비교 모드는 infection 상태 간 virome shift를 보는 데 매우 유용하다.

### 6.4 Per-Sample Tabs Everywhere

사용자 요구사항대로 모든 시각화는 per-sample tab을 가져야 한다.

적용 범위:

- overview cards
- taxonomy browser
- QA plot
- contig viewer
- abundance comparison
- figure gallery

기본 UX:

- `[All]` 탭은 overlay 또는 aggregate
- 각 sample 탭은 독립 scale 또는 shared scale 선택 가능

---

## 7. Report v3

Word report는 standalone artifact여야 하지만, dashboard와 정보가 어긋나면 안 된다. 따라서 report v3는 dashboard figure의 static companion으로 설계해야 한다.

### 7.1 Mandatory Additions

- 4-quadrant QA figure
- tier filtering funnel
- IGV-style figure for top 5 viral contigs
- sample comparison dot plot
- classification summary table
- database version manifest appendix

### 7.2 Suggested Report Structure

1. Analysis overview
2. Sample summary and preprocessing metrics
3. Viral detection summary
4. Tier-wise evidence funnel
5. Taxonomic composition
6. Top viral contigs with IGV-style figures
7. Novel/ambiguous candidate review
8. Methods and database versions

### 7.3 Dashboard-Report Synchronization

동기화 원칙:

- 동일 bigtable 사용
- 동일 contig ranking 사용
- 동일 color palette와 threshold 사용
- figure caption이 evidence chain과 일치해야 함

즉, report는 dashboard의 screenshot 모음이 아니라, **같은 분석 모델의 정적 표현**이어야 한다.

---

## 8. New Nextflow Modules Required

Hybrid v1 구현에는 새로운 process와 기존 process 확장이 모두 필요하다.

### 8.1 New Processes

#### `KRAKEN2_CLASSIFY` (독립 프로파일링 섹션)

역할:

- host-depleted read 전체를 Kraken2로 분류 (annotation only)
- **virome 탐지 파이프라인과 완전히 독립** — assembly나 contig 판정에 관여하지 않음
- Section B (Read-based Profiling)의 핵심 모듈

입력:

- cleaned non-host reads
- Kraken2 DB (core_nt)

출력:

- `*.kraken2.report`: 분류학적 요약 (kreport 형식)
- `*.kraken2.output`: read별 분류 결과 (C/U + taxid)

후속 처리:

- `Bracken`: species-level abundance 재추정 (optional)
- `kreport2krona.py`: Krona interactive HTML 생성
- Dashboard `Kraken2 Profiling` 탭에 표시

**참고:** `KRAKEN2_EXTRACT_SETS` (discovery/cellular set 분리) 모듈은 더 이상 사용하지 않음.
Assembly는 전체 reads를 사용하므로, Kraken2에 의한 read 분리가 불필요하다.
해당 모듈은 코드에 남겨두되 main.nf에서 호출하지 않는다.

#### `DIAMOND_TIER1_AA`

역할:

- viral protein DB against ORFs/contigs

출력:

- parsed AA1 result table

#### `DIAMOND_TIER2_AA`

역할:

- UniRef50 verification

출력:

- parsed AA2 result table

#### `BLASTN_TIER3_NT` + `BLASTN_TIER4_NT`

역할:

- Tier 3: viral nucleotide search (GenBank viral NT)
- Tier 4: polymicrobial exclusion search (RefSeq representative genomes)

출력:

- parsed NT result tables (alnlen, pident, evalue, bitscore, taxid 포함)

#### Parallel BLAST 가속화 (Blast Ripper 방식 이식)

Tier 3/4 NT blastn은 contig 수가 많을 때 병목이 된다. `/mnt/ivt-ngs1/script/metagenome/Blast_ripper-meta_v4_dmnd.py`의 Parallel BLAST 알고리즘을 이식하여 가속화한다.

**핵심 알고리즘:**

```python
# 1. 입력 FASTA를 CPU 수만큼 chunk로 분할
chunks = chunk_file(input_fasta, num_chunks=cpu_count())
# 예: 1,500 contigs → 16 chunks (16 cores) → chunk당 ~94 contigs

# 2. 각 chunk를 Python multiprocessing.Pool로 병렬 BLAST
with Pool(processes=max_processes) as p:
    p.starmap(run_blast, [
        (chunk, db, out_file, use_ramdisk, threads_per_chunk, taxids, logger, program)
        for chunk in chunks
    ])

# 3. /dev/shm RAM disk 활용 (optional, I/O 병목 제거)
if use_ramdisk:
    temp_chunk = os.path.join('/dev/shm', os.path.basename(chunk))
    shutil.copy(chunk, temp_chunk)  # chunk를 RAM에 복사하여 BLAST 실행
    # 완료 후 결과를 NFS로 복사, temp 삭제

# 4. 모든 chunk 결과를 병합
merge_blast_results(chunk_outputs, final_output)
```

**구현 방법:**

`bin/parallel_blast.py` (신규) 또는 기존 Nextflow 프로세스 내에서:

```groovy
// blastn_tier3_nt.nf — Parallel BLAST 적용
process BLASTN_TIER3_NT {
    script:
    """
    # FASTA를 chunk로 분할
    parallel_blast.py \\
        --query ${contigs} \\
        --db ${viral_nt_db} \\
        --program blastn \\
        --output ${prefix}.tier3_nt.tsv \\
        --num-chunks ${task.cpus} \\
        --threads-per-chunk 1 \\
        --use-ramdisk \\
        --evalue 1e-10 \\
        --max-target-seqs 5 \\
        --outfmt '6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore staxids'
    """
}
```

**성능 예상:**
- 기존: 1,500 contigs × 1 thread blastn → ~30분
- Parallel (16 chunks × 1 thread): ~2분 (15x 가속)
- /dev/shm 사용 시: NFS I/O 제거로 추가 2-3x 가속

**지원 프로그램:**
- `blastn` (Tier 3/4 NT)
- `blastx` (대안)
- `diamond blastx` (Tier 1/2 AA — Diamond은 자체 멀티스레딩이 있으므로 chunk 분할 불필요)

**참고:** `/mnt/ivt-ngs1/script/metagenome/Blast_ripper-meta_v4_dmnd.py`에서 이식. 이 스크립트는 blastn/blastx/diamond 모두 지원하며, /dev/shm RAM disk, chunk 분할, 결과 병합, 성능 모니터링(psutil)을 포함한다.

#### `EVIDENCE_INTEGRATION`

역할:

- classify_contigs.py v2 실행
- final classification, evidence chain 산출

#### `SAMTOOLS_DEPTH`

역할:

- top contig per-base depth profile 생성

#### `PRODIGAL_ORFS`

역할:

- ORF prediction

비고:

- 이미 존재하더라도 Hybrid v1 data contract에 맞게 출력 표준화 필요

### 8.2 Modified Processes

- `MERGE_RESULTS`
  - bigtable v2 schema 확장
- `GENERATE_REPORT`
  - report v3 figure set 및 appendix 반영
- `GENERATE_DASHBOARD`
  - dashboard v4, IGV viewer, QA plot, lazy-loading 반영

### 8.3 Suggested Subworkflow Grouping

권장 subworkflow 재구성:

- `preprocessing`
  - QC, host removal, Kraken2
- `assembly`
  - discovery set extraction, MEGAHIT
- `detection`
  - geNomad, Prodigal
- `classification`
  - AA1, AA2, NT1, NT2, evidence integration
- `quantification`
  - CoverM, CheckV, samtools depth
- `reporting`
  - merge, dashboard, report

이 구조가 DAG 가독성과 maintenance 측면에서 가장 명확하다.

---

## 9. Implementation Phases

Hybrid v1은 한 번에 완성하기보다, DB 확보와 핵심 evidence engine부터 단계적으로 구축해야 한다.

### Phase 0: DB Download and Build

즉시 시작 가능하며 background 작업으로 운영 가능하다.

우선순위:

- Kraken2 PlusPFP
- UniRef50
- GenBank viral proteins
- GenBank viral nucleotide
- taxonomy registry

예상 이슈:

- 대용량 download
- Diamond/BLAST build 시간
- 디스크 확보

### Phase 1: Core Pipeline

첫 번째 목표는 Hybrid v1의 과학적 핵심을 동작시키는 것이다.

포함 범위:

- Kraken2 annotation
- 4-tier AA/NT search
- evidence integration v2
- expanded bigtable

이 단계가 끝나면 dashboard가 단순하더라도, 최소한 classification model은 완성되어야 한다.

### Phase 2: Visualization

classification 결과를 해석 가능한 형태로 끌어올린다.

포함 범위:

- SAMTOOLS_DEPTH
- IGV-style contig viewer
- 4-quadrant QA plots
- tier funnel

### Phase 3: Report and Dashboard Sync

제품 완성도를 맞추는 단계다.

포함 범위:

- report v3
- dashboard v4 complete
- figure/report parity
- publication-ready export

### Phase 4: Read-level Rescue (Optional)

고급 sensitivity 향상을 위한 실험 단계다.

후보 기능:

- unmapped/unassembled read translated viral search
- low-abundance RNA virus rescue
- assembly miss segment recovery

이 단계는 유용하지만 v1 release blocker는 아니다.

---

## 10. Estimated Resource Requirements

Hybrid v1은 DB와 search tier가 늘어나므로 자원 계획을 명확히 해야 한다.

| Resource | Estimate |
|----------|----------|
| Disk (DBs) | ~300 GB additional |
| Disk (results) | ~10 GB per run |
| RAM (Kraken2) | 128 GB recommended |
| RAM (Diamond UniRef50) | 64 GB |
| CPU time (typical 2-sample insect RNA-seq) | 6-12 hours |
| Dashboard HTML size | ~10-20 MB |

### 10.1 Practical Notes

- Kraken2 PlusPFP는 메모리 요구량이 높으므로 shared HPC node 또는 high-memory workstation이 필요하다.
- UniRef50 Diamond search는 CPU parallelism을 잘 활용하지만 I/O 병목 가능성이 있다.
- per-base depth를 모든 contig에 저장하면 dashboard가 비대해지므로 top N 제한이 필요하다.
- Parquet 병행 출력은 large run scalability에 유리하다.

---

## 11. Classification Logic Recommendations

Hybrid v1의 success는 evidence integration의 설명 가능성에 달려 있다. 따라서 초기 버전은 지나치게 복잡한 ML classifier보다 **명시적 rule engine + score annotation**이 더 적합하다.

### 11.1 Recommended Priority Order

1. 강한 exclusion evidence가 있는지 확인
2. 강한 viral-first evidence가 있는지 확인
3. geNomad가 novel candidate를 지지하는지 확인
4. read composition과 coverage가 plausibility를 높이는지 확인
5. 최종 label과 evidence chain 생성

### 11.2 Example Strong Evidence Heuristics

강한 viral evidence 예시:

- `geNomad >= 0.9`
- 긴 `aa1` 또는 `nt1` alignment
- `aa2/nt2`에서 stronger cellular alternative 부재
- sample breadth/depth 양호

강한 cellular evidence 예시:

- `aa2`에서 high bitscore bacterial/eukaryotic conserved protein
- `nt2`에서 긴 고일치 cellular genome match
- geNomad 낮음
- Kraken2 mapped reads 다수가 bacterial/fungal

모호한 사례 예시:

- geNomad 높지만 exclusion hit도 강함
- viral hit는 짧은 fragment 하나뿐
- coverage가 spike 형태로 국소적

### 11.3 Why Rule-Based First

- 해석 가능하다.
- dashboard/report에서 설명하기 쉽다.
- threshold tuning이 가능하다.
- 실제 benchmark 후 ML meta-classifier로 확장하기 쉽다.

v1에서는 black-box ensemble보다 reproducible rule system이 맞다.

---

## 12. Key Deliverables

Hybrid v1 완료 시점의 필수 deliverable은 다음과 같다.

- Nextflow pipeline with 4-tier iterative search
- Kraken2 triage module
- geNomad full-assembly detection
- bigtable v2 single source of truth
- classify_contigs.py v2 evidence engine
- dashboard v4 with IGV-style contig viewer and QA plots
- report v3 synchronized with dashboard
- database registry and update checker

---

## 13. Final Recommendation

DeepInvirus Hybrid v1은 단순한 pipeline upgrade가 아니라, DeepInvirus를 **virus candidate collector**에서 **evidence-driven virome analysis platform**으로 전환하는 설계다.

이 설계에서 절대 흔들리면 안 되는 원칙은 다음 세 가지다.

1. `Kraken2는 triage이지 filter가 아니다.`
2. `geNomad는 full assembly에 먼저 적용한다.`
3. `모든 evidence는 bigtable에 남기고, 최종 해석은 시각화와 명시적 classification rule이 담당한다.`

구현 우선순위는 분명하다.

1. DB 구축
2. 4-tier search + evidence integration
3. bigtable 확장
4. QA/IGV visualization
5. report/dashboard 동기화

이 순서로 진행하면 Hybrid v1은 연구용 prototype 수준을 넘어서, 실제 publication-grade virome discovery workflow로 발전할 수 있다.
