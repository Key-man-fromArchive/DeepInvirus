# TASKS: DeepInvirus Hybrid v1

> 최종 업데이트: 2026-03-26 16:00 KST
> 테스트: 1,183 passed / 0 failed
> DB: 10/10 완료 (로컬 NVMe 177GB)
> Full run: ✅ 완료 (2min 4s, 27 processes)

---

## DB 상태 (실측, /media/bio3/Database/DeepInvirus/)

| # | DB | Sequences | Size | Status |
|---|-----|-----------|------|--------|
| 1 | UniRef50 Diamond | 60,315,044 | 24 GB | ✅ taxonomy 포함 |
| 2 | Viral Protein Diamond | 713,379 | 225 MB | ✅ taxonomy 재빌드 (99.98%) |
| 2b | UniRef90 Viral Diamond | 1,044,911 | ~400 MB | ✅ 999,234 매핑 (95.6%) |
| 3 | GenBank Viral NT BLAST | 740,393 (dedup) | 9.3 GB | ✅ |
| 4 | Kraken2 core_nt | 3 k2d files | 307 GB | ✅ (2025.09) |
| 5 | Polymicrobial NT BLAST | 180,366 | 54 GB | ✅ |
| 6 | geNomad | 35 files | 1.4 GB | ✅ |
| 7 | CheckV | genome_db + hmm_db | 6.4 GB | ✅ |
| 8 | ICTV VMR | 19,272 isolates | MSL41 | ✅ |
| 9 | Taxonomy | nodes.dmp (cleaned) | 583 MB | ✅ |
| 10 | Host genomes | 3 species | 4.9 GB | ✅ |

## 코드 상태

| 항목 | 상태 |
|------|------|
| Tests | 1,183 passed / 0 failed ✅ |
| Stub run | ✅ 전체 배선 통과 |
| Kraken2 독립 분리 | ✅ main.nf 수정 완료 |
| Assembly 전체 reads | ✅ |
| iterative_classification.nf | ✅ 7 take / 7 args 매칭 |
| BLAST DB val() 수정 | ✅ |
| MultiQC 파일명 충돌 수정 | ✅ |
| Nextflow report overwrite | ✅ |
| DB auto-detect (--db_dir) | ✅ |
| materials_and_methods.txt | ✅ 자동 생성 |
| Diamond staxids 복원 | ✅ 모든 모듈 13컬럼 통일 |
| evidence_integration.py | ✅ 3-state taxonomy 라벨링 |
| **Full run** | ✅ 완료 (4,147 contigs 분류) |

## 마일스톤 상태

| M | 설명 | 상태 |
|---|------|------|
| M0 | DB 구축 | ✅ **10/10 완료** |
| M1 | 파이프라인 재구성 | ✅ Kraken2 독립 + 전체 reads assembly |
| M2 | 4-Tier 배선 | ✅ Stub run 통과 |
| M3 | Parallel BLAST | ✅ parallel_blast.py 구현 (29 tests) |
| M4 | Bigtable v2 | ✅ 실행 검증 완료 (bigtable.tsv 2,937행) |
| M5 | Dashboard v4 | ⚠️ 기본 기능 작동 (evidence integration 연동 필요) |
| M6 | Report v3 | ⚠️ 기본 기능 작동 |
| **M7** | **Full Run** | **✅ 완료** |
| M8 | Rescue | ❌ optional |

## 마지막 실행 결과 (2026-03-26 15:55)

```bash
nextflow run main.nf \
  --reads 'input_data/*_R{1,2}.fq.gz' \
  --host insect_combined \
  --db_dir /media/bio3/Database/DeepInvirus \
  --outdir 7.deepinvirus_hybrid_v1 \
  -profile docker -resume

# 결과: 4,147 contigs 분류 완료
# 소요 시간: 4분 2초 (27 processes)
# Output: 7.deepinvirus_hybrid_v1/bigtable.tsv (2,937 rows)
```

## 완료 후 할 것

1. ✅ Full run 결과 검증 (bigtable 2,937행, dashboard/report 기본 작동)
2. ✅ 4-tier evidence integration 결과 확인 (4,147 contigs: strong_viral 42, novel_viral_candidate 7, ambiguous 1,435, unknown 2,663)
3. ✅ UniRef90 추가 검증 (999,234 매핑, 95.6% 성공률)
4. ✅ TASKS.md 최종 업데이트
5. ⏳ Dashboard v4 + Report v3 evidence integration 연동
6. ⏳ Codex final audit
