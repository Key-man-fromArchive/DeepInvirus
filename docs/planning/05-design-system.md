# Design System (대시보드/보고서 디자인) - DeepInvirus

---

## MVP 캡슐

| # | 항목 | 내용 |
|---|------|------|
| 1 | 목표 | 논문/보고서급 시각화 자동 출력 |
| 2 | 핵심 기능 | FEAT-2: 동적 HTML 대시보드, FEAT-3: Word 보고서 |

---

## 1. 디자인 철학

### 1.1 핵심 가치

| 가치 | 설명 | 구현 방법 |
|------|------|----------|
| 논문 품질 | 학술 논문에 바로 삽입 가능한 수준 | 300 DPI 이미지, 깔끔한 폰트, 명확한 범례 |
| 정보 밀도 | 한 눈에 핵심 정보를 파악 | 적절한 데이터 집계, 불필요한 장식 제거 |
| 인터랙티브 | 동적 탐색으로 심층 분석 가능 | Plotly.js 기반 줌/필터/호버 |

### 1.2 참고 서비스

| 서비스 | 참고할 점 | 참고하지 않을 점 |
|--------|----------|-----------------|
| Pavian | Sankey 다이어그램, 샘플 비교 인터페이스 | R Shiny 서버 의존성 |
| Krona | 계층적 분류 시각화 | 정적, 비율만 표시 |
| MultiQC | 깔끔한 HTML 리포트, 탭 구조 | QC에만 특화 |
| Novogene 보고서 | 체계적인 Word 보고서 구조 | 과도한 장식 |

---

## 2. 대시보드 (dashboard.html) 설계

### 2.1 레이아웃

```
┌──────────────────────────────────────────────────┐
│  DeepInvirus Dashboard              [Export] [?]  │
├──────────────────────────────────────────────────┤
│  [Overview] [Composition] [Diversity] [Search]    │
├──────────────────────────────────────────────────┤
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │            메인 시각화 영역                    │ │
│  │    (탭에 따라 히트맵/바플롯/PCoA 등)          │ │
│  │                                              │ │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   필터 패널   │  │     상세 정보 패널        │  │
│  │  - 분류 수준  │  │  - 선택된 종 정보         │  │
│  │  - 풍부도 임계│  │  - contig 목록           │  │
│  │  - 샘플 선택  │  │  - NCBI 링크            │  │
│  └──────────────┘  └──────────────────────────┘  │
│                                                   │
│  ┌─────────────────────────────────────────────┐ │
│  │            요약 통계 테이블                    │ │
│  └─────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### 2.2 탭별 시각화

| 탭 | 시각화 | 설명 |
|---|--------|------|
| Overview | 요약 카드 + Sankey | 전체 분석 요약, 분류 계층 Sankey |
| Composition | 히트맵 + 바플롯 | 샘플 x 종 히트맵, 상대 풍부도 바플롯 |
| Diversity | PCoA + 박스플롯 | Beta diversity PCoA, Alpha diversity 비교 |
| Search | 검색 + 테이블 | 종명 검색, 필터링, 정렬 가능 테이블 |

---

## 3. 컬러 팔레트

### 3.1 시각화 컬러

| 역할 | 컬러 | Hex | 사용처 |
|------|------|-----|--------|
| Primary 1 | Deep Blue | `#1F77B4` | DNA virus, 주요 차트 |
| Primary 2 | Orange | `#FF7F0E` | RNA virus |
| Primary 3 | Green | `#2CA02C` | dsDNA |
| Primary 4 | Red | `#D62728` | ssRNA |
| Primary 5 | Purple | `#9467BD` | ssDNA |
| Primary 6 | Brown | `#8C564B` | dsRNA |
| Neutral | Gray | `#7F7F7F` | Unclassified |
| Background | White | `#FFFFFF` | 배경 |
| Surface | Light Gray | `#F8F9FA` | 카드 배경 |
| Text | Dark Gray | `#212529` | 본문 텍스트 |

### 3.2 히트맵 컬러스케일

| 용도 | 스케일 | 설명 |
|------|--------|------|
| 풍부도 | YlOrRd (노랑→빨강) | log10(RPM+1) |
| 다양성 | Viridis (보라→노랑) | Shannon/Simpson |
| 유무 | Binary (흰→파랑) | presence/absence |

---

## 4. 타이포그래피

### 4.1 대시보드 (HTML)

| 용도 | 폰트 | 크기 |
|------|------|------|
| 제목 | Roboto, sans-serif | 24px Bold |
| 섹션 | Roboto, sans-serif | 18px SemiBold |
| 본문 | Roboto, sans-serif | 14px Regular |
| 데이터 | Roboto Mono, monospace | 12px Regular |

### 4.2 보고서 (Word)

| 용도 | 폰트 | 크기 |
|------|------|------|
| 제목 | 맑은 고딕 | 20pt Bold |
| 소제목 | 맑은 고딕 | 14pt Bold |
| 본문 | 맑은 고딕 | 11pt Regular |
| 테이블 | 맑은 고딕 | 9pt Regular |
| Figure 캡션 | 맑은 고딕 | 10pt Italic |

### 4.3 Figure (matplotlib)

| 용도 | 폰트 | 크기 |
|------|------|------|
| Title | Arial | 14pt Bold |
| Axis label | Arial | 12pt |
| Tick label | Arial | 10pt |
| Legend | Arial | 10pt |
| 해상도 | - | 300 DPI |

---

## 5. Word 보고서 템플릿

### 5.1 보고서 구조

```
1. 분석 개요
   1.1 프로젝트 정보 (테이블)
   1.2 분석 파이프라인 요약 (다이어그램)

2. 품질 관리 (QC) 결과
   2.1 Raw data 통계 (Table 1)
   2.2 Trimming 결과 (Table 2)
   2.3 Host removal 결과 (Table 3)

3. 바이러스 탐지 결과
   3.1 탐지 방법별 결과 요약 (Table 4)
   3.2 ML vs 상동성 탐지 비교 (Figure 1: Venn diagram)

4. 분류학적 분석
   4.1 바이러스 구성 개요 (Figure 2: Barplot)
   4.2 샘플별 상세 구성 (Figure 3: Heatmap)
   4.3 주요 바이러스 목록 (Table 5)

5. 다양성 분석
   5.1 Alpha diversity (Figure 4: Boxplot, Table 6)
   5.2 Beta diversity (Figure 5: PCoA)

6. 결론 및 해석

부록
   A. 상세 분류 테이블
   B. 분석 파라미터
   C. 소프트웨어 버전
```

### 5.2 페이지 설정

| 항목 | 값 |
|------|-----|
| 용지 | A4 |
| 여백 | 상하 2.54cm, 좌우 3.17cm |
| 줄간격 | 1.5 |
| 페이지 번호 | 하단 중앙 |
| 머리글 | "DeepInvirus Analysis Report" |

---

## 6. Figure 생성 규격

### 6.1 공통 규격

| 항목 | 값 |
|------|-----|
| 해상도 | 300 DPI |
| 포맷 | PNG (보고서), SVG (대시보드) |
| 기본 크기 | 8 x 6 inches |
| 배경 | 흰색 (#FFFFFF) |
| 테두리 | 없음 |

### 6.2 Figure별 규격

| Figure | 크기 | 특이사항 |
|--------|------|----------|
| 히트맵 | 10 x 8 in (종 수에 따라 조절) | 클러스터링 덴드로그램 포함 |
| 바플롯 | 8 x 6 in | 범례 오른쪽, 상위 N종만 표시 |
| PCoA | 8 x 8 in (정사각) | 그룹별 색상, 95% 신뢰 타원 |
| Sankey | 10 x 8 in | Domain → Family → Genus 3단계 |
| Boxplot | 6 x 6 in | 개별 데이터 포인트 jitter |
