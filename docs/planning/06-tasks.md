# TASKS: DeepInvirus Hybrid v1

> 최종 업데이트: 2026-03-26 07:00 KST
> 테스트: 1,183 passed / 0 failed
> DB: 10/10 완료 (로컬 NVMe 177GB)
> Full run: 실행 중

---

## DB 상태 (실측, /media/bio3/Database/DeepInvirus/)

| # | DB | Sequences | Size | Status |
|---|-----|-----------|------|--------|
| 1 | UniRef50 Diamond | 60,315,044 | 24 GB | ✅ taxonomy 포함 |
| 2 | Viral Protein Diamond | 713,487 | 225 MB | ✅ |
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
| **Full run** | ⏳ 실행 중 |

## 마일스톤 상태

| M | 설명 | 상태 |
|---|------|------|
| M0 | DB 구축 | ✅ **10/10 완료** |
| M1 | 파이프라인 재구성 | ✅ Kraken2 독립 + 전체 reads assembly |
| M2 | 4-Tier 배선 | ✅ Stub run 통과 |
| M3 | Parallel BLAST | ✅ parallel_blast.py 구현 (29 tests) |
| M4 | Bigtable v2 | ⚠️ merge_results.py 수정됨 (실행 검증 중) |
| M5 | Dashboard v4 | ⚠️ 이전 버전, bigtable v2 반영 필요 |
| M6 | Report v3 | ⚠️ 이전 버전 |
| **M7** | **Full Run** | **⏳ 실행 중** |
| M8 | Rescue | ❌ optional |

## 현재 실행 중

```bash
nextflow run main.nf \
  --reads 'input_data/*_R{1,2}.fq.gz' \
  --host insect_combined \
  --db_dir /media/bio3/Database/DeepInvirus \
  --outdir 7.deepinvirus_hybrid_v1 \
  -profile docker -resume
```

## 완료 후 할 것

1. Full run 결과 검증 (bigtable, dashboard, report)
2. 4-tier evidence integration 결과 확인
3. Unclassified 비율 변화 확인
4. TASKS.md 최종 업데이트
5. Codex final audit
