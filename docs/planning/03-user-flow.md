# User Flow (사용자 흐름도) - DeepInvirus

---

## MVP 캡슐

| # | 항목 | 내용 |
|---|------|------|
| 1 | 목표 | Raw FASTQ → 논문/보고서급 결과물 자동 출력 |
| 2 | 페르소나 | 바이러스 메타게노믹스 분석 수탁 서비스 운영자 |
| 3 | 핵심 기능 | FEAT-1: 통합 파이프라인, FEAT-2: 대시보드, FEAT-3: 보고서 |
| 4 | 성공 지표 | 수작업 시간 80% 감소 |

---

## 1. 전체 사용자 여정 (Overview)

```mermaid
graph TD
    A[고객 샘플 수령] --> B[데이터 확인]
    B --> C{입력 형식 OK?}
    C -->|No| D[포맷 변환/문의]
    D --> B
    C -->|Yes| E[deepinvirus run 실행]
    E --> F[파이프라인 자동 실행]
    F --> G{성공?}
    G -->|No| H[에러 로그 확인]
    H --> I{재시도 가능?}
    I -->|Yes| J[deepinvirus run -resume]
    J --> F
    I -->|No| K[파라미터 조정]
    K --> E
    G -->|Yes| L[대시보드로 결과 확인]
    L --> M[보고서 미세 조정]
    M --> N[고객 납품]
```

---

## 2. FEAT-1: 파이프라인 실행 흐름

```mermaid
graph TD
    A[deepinvirus run] --> B[INPUT_CHECK]
    B --> C{샘플시트 유효?}
    C -->|No| D[에러: 입력 파일 누락/형식 오류]
    C -->|Yes| E[FASTP: QC + Trimming]
    E --> F[HOST_REMOVAL: minimap2]
    F --> G[ASSEMBLY: MEGAHIT/metaSPAdes]

    G --> H[GENOMAD: ML 바이러스 탐지]
    G --> I[DIAMOND: 단백질 상동성 검색]

    H --> J[MERGE: 탐지 결과 통합]
    I --> J

    J --> K[MMSEQS_TAXONOMY: 분류학적 할당]
    K --> L[TAXONKIT: Lineage 변환]
    L --> M[COVERAGE: CoverM]
    M --> N[MERGE_RESULTS: bigtable 생성]

    N --> O[DIVERSITY: alpha/beta 다양성]
    N --> P[DASHBOARD: HTML 생성]
    N --> Q[REPORT: Word 생성]
    N --> R[MULTIQC: QC 종합]

    O --> S[완료: results/ 디렉토리]
    P --> S
    Q --> S
    R --> S
```

---

## 3. FEAT-2: 대시보드 탐색 흐름

```mermaid
graph TD
    A[dashboard.html 열기] --> B[Overview 탭]
    B --> C{무엇을 보고 싶은가?}

    C -->|종 구성| D[Taxonomic Composition]
    D --> D1[히트맵: 샘플 x 종]
    D --> D2[바플롯: 상대 풍부도]
    D --> D3[Sankey: 분류 계층]

    C -->|샘플 비교| E[Sample Comparison]
    E --> E1[PCoA/NMDS 플롯]
    E --> E2[Alpha diversity 박스플롯]

    C -->|상세 검색| F[Search & Filter]
    F --> F1[종명으로 검색]
    F --> F2[분류 수준 필터]
    F --> F3[풍부도 임계값 필터]

    D1 --> G[클릭: 특정 종 상세]
    G --> G1[해당 종의 contig 목록]
    G --> G2[NCBI 링크]
    G --> G3[커버리지 정보]
```

---

## 4. FEAT-3: 보고서 생성 흐름

```mermaid
graph TD
    A[파이프라인 완료] --> B[report.docx 자동 생성]
    B --> C[보고서 구조]

    C --> C1[1. 분석 개요]
    C --> C2[2. QC 결과 요약]
    C --> C3[3. 바이러스 탐지 결과]
    C --> C4[4. 분류학적 분석]
    C --> C5[5. 다양성 분석]
    C --> C6[6. 결론]
    C --> C7[부록: 상세 테이블]

    C1 --> D[Figure 1: QC 통계 테이블]
    C2 --> E[Figure 2: Read 수 변화 바차트]
    C3 --> F[Figure 3: 바이러스 탐지 벤 다이어그램]
    C4 --> G[Figure 4: 텍소노믹 히트맵]
    C4 --> H[Figure 5: 상대 풍부도 바플롯]
    C5 --> I[Figure 6: Alpha diversity 박스플롯]
    C5 --> J[Figure 7: PCoA 플롯]

    B --> K[사용자: 보고서 검토]
    K --> L{수정 필요?}
    L -->|Yes| M[Word에서 직접 수정]
    M --> N[고객 납품]
    L -->|No| N
```

---

## 5. DB 관리 흐름

```mermaid
graph TD
    A{DB 설치 여부?}
    A -->|미설치| B[deepinvirus install-db]
    B --> C[다운로드 + 인덱싱]
    C --> D[VERSION.json 기록]
    D --> E[사용 준비 완료]

    A -->|설치됨| F{업데이트 필요?}
    F -->|Yes| G[deepinvirus update-db]
    G --> H[변경된 DB만 갱신]
    H --> D
    F -->|No| E
```

---

## 6. CLI 명령어 목록

| 명령어 | 용도 | 예시 |
|--------|------|------|
| `deepinvirus run` | 파이프라인 실행 | `deepinvirus run --reads ./data --host insect` |
| `deepinvirus install-db` | DB 설치 | `deepinvirus install-db --db-dir /db` |
| `deepinvirus update-db` | DB 업데이트 | `deepinvirus update-db --component taxonomy` |
| `deepinvirus test` | 테스트 데이터 실행 | `deepinvirus test --threads 8` |
| `deepinvirus list-hosts` | 사용 가능한 host 목록 | `deepinvirus list-hosts` |
| `deepinvirus add-host` | 커스텀 host 추가 | `deepinvirus add-host --name beetle --fasta ref.fa` |

---

## 7. 에러 처리 흐름

```mermaid
graph TD
    A[에러 발생] --> B{에러 유형?}

    B -->|입력 오류| C[파일 경로/형식 확인 안내]
    B -->|메모리 부족| D[--max_memory 파라미터 조정 안내]
    B -->|도구 실행 실패| E[해당 도구의 로그 파일 경로 표시]
    B -->|DB 누락| F[deepinvirus install-db 안내]

    C --> G[수정 후 재실행]
    D --> H[-resume로 이어서 실행]
    E --> I[로그 확인 후 파라미터 조정]
    F --> J[DB 설치 후 재실행]
```
