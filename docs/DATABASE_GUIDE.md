# DeepInvirus Database Download & Update Guide

> 작성일: 2026-03-25
> 대상: DeepInvirus Hybrid v1 전체 DB

---

## DB 구조 개요

```
databases/
├── uniref50/                    # Tier 2 AA: 다왕국 검증용 (60M seqs)
│   ├── uniref50.fasta.gz       # UniRef50 FASTA (12 GB compressed)
│   ├── uniref50.dmnd           # Diamond DB (24 GB, taxonomy 포함)
│   ├── uniref50_taxonmap.tsv   # Custom accession→taxid 매핑 (60M lines)
│   └── VERSION.json
│
├── genbank_viral_nt/            # Tier 3 NT: 바이러스 뉴클레오타이드 (전체 GenBank)
│   ├── genbank_viral_*.fna     # GenBank viral FASTA
│   ├── genbank_viral_nt.*      # BLAST DB index
│   └── VERSION.json
│
├── genbank_viral_protein/       # Tier 1 AA: 바이러스 단백질
│   ├── viral_protein_refseq.dmnd  # Diamond DB (225 MB)
│   └── VERSION.json
│
├── kraken2_core_nt/             # Read-level profiling (독립 섹션)
│   ├── hash.k2d                # Kraken2 index (~316 GB)
│   ├── opts.k2d
│   ├── taxo.k2d
│   └── VERSION.json
│
├── genomad_db/                  # geNomad ML detection (1.4 GB)
├── host_genomes/                # 숙주 참조 게놈
├── taxonomy/                    # NCBI taxonomy
│   ├── nodes.dmp               # cleaned (비표준 rank → no rank)
│   ├── names.dmp
│   ├── prot.accession2taxid.gz # NCBI accession→taxid (23 GB)
│   └── ictv_vmr.tsv
│
└── polymicrobial_nt/            # Tier 4 NT: 비바이러스 검증용 (~16 GB)
    ├── polymicrobial_nt.fasta   # Merged FASTA (bacteria+archaea+fungi+plant+protozoa)
    ├── polymicrobial_nt.*       # BLAST DB index files
    ├── build_polymicrobial_nt.sh # Build script
    └── VERSION.json
```

---

## 1. UniRef50 Diamond DB (Tier 2 AA)

### 용도
Tier 2 다왕국 검증: viral hit이 진짜 바이러스인지, bacteria/fungi/plant인지 판별

### 다운로드

```bash
cd databases/uniref50/

# 1. UniRef50 FASTA 다운로드 (12 GB compressed, ~60GB uncompressed)
wget -c "https://ftp.uniprot.org/pub/databases/uniprot/uniref/uniref50/uniref50.fasta.gz"

# 2. Custom taxonmap 추출 (UniRef50 헤더에서 TaxID 추출)
#    UniRef50 헤더: >UniRef50_XXXXX ... TaxID=12345
#    NCBI prot.accession2taxid는 매칭 안 됨 (형식 불일치)
zcat uniref50.fasta.gz | grep "^>" | \
  sed -n 's/^>UniRef50_\([^ ]*\).*TaxID=\([0-9]*\).*/\1\t\2/p' \
  > uniref50_taxonmap.tsv
# 헤더 추가 (Diamond 필수)
sed -i '1i accession.version\ttaxid' uniref50_taxonmap.tsv
```

### NCBI taxonomy 정리 (Diamond 호환)

```bash
cd databases/taxonomy/

# Diamond이 인식 못하는 비표준 rank를 "no rank"로 대체
# 필수 수정: domain → superkingdom
# 추가 수정: acellular root, cellular root, realm 등 → no rank
cp nodes.dmp nodes.dmp.original
sed -i 's/\tdomain\t/\tsuperkingdom\t/g' nodes.dmp
sed -i 's/\tacellular root\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tcellular root\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tsubvariety\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tsection\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tsubsection\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tseries\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tmorph\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tbiotype\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tgenotype\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tforma specialis\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tserogroup\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tserotype\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tpathogroup\t/\tno rank\t/g' nodes.dmp
sed -i 's/\tisolate\t/\tno rank\t/g' nodes.dmp
sed -i 's/\trealm\t/\tno rank\t/g' nodes.dmp
```

### Diamond DB 빌드

```bash
cd databases/uniref50/

diamond makedb \
  --in uniref50.fasta.gz \
  --db uniref50 \
  --taxonmap uniref50_taxonmap.tsv \
  --taxonnodes ../taxonomy/nodes.dmp \
  --taxonnames ../taxonomy/names.dmp \
  --threads 16

# 검증
diamond dbinfo --db uniref50.dmnd
# Expected: Sequences  60,315,044  Letters  17,282,055,793
```

### 업데이트 주기
- UniRef50: **분기별** (UniProt 2주 업데이트이나, 60M 서열 재빌드는 시간 소요)
- taxonmap: UniRef50 업데이트 시 함께 재생성
- taxonomy (nodes.dmp): **월별**

### 알려진 문제
- NCBI `prot.accession2taxid.gz`는 UniRef accession을 매핑하지 못함 → custom taxonmap 필수
- Diamond이 `domain`, `acellular root` 등 비표준 rank를 인식 못함 → nodes.dmp 정리 필수
- `Error: Invalid taxonomic rank: domain` → nodes.dmp에서 `domain` → `superkingdom` 변환

---

## 2. GenBank Viral NT (Tier 3 NT)

### 용도
Tier 3 바이러스 뉴클레오타이드 검색: AA 검색에서 놓친 바이러스 포착

### 다운로드 방법

**방법 A: NCBI Datasets CLI (권장)**

```bash
conda install -y -c conda-forge ncbi-datasets-cli

datasets download virus genome taxon 10239 \
  --complete-only \
  --include genome \
  --filename viral_complete.zip

unzip viral_complete.zip -d viral_datasets
cat viral_datasets/ncbi_dataset/data/genomic.fna > genbank_viral_complete.fna
```

**방법 B: Entrez Direct (대량, 불안정)**

```bash
# 전체 GenBank viral (9.2M 서열) — NCBI API 제한으로 불안정
esearch -db nucleotide -query "txid10239[Organism:exp] AND srcdb_genbank[Properties]" | \
  efetch -format fasta > genbank_viral_full.fna

# 주의: 대량 다운로드 시 SSL 에러, timeout 빈번
# NCBI API key 등록 권장: https://www.ncbi.nlm.nih.gov/account/settings/
```

**방법 C: RefSeq viral (최소, 빠름)**

```bash
wget "https://ftp.ncbi.nlm.nih.gov/refseq/release/viral/viral.1.1.genomic.fna.gz"
# ~19K 서열만. 변이 포괄 부족. 테스트용으로만 사용.
```

### BLAST DB 빌드

```bash
makeblastdb -in genbank_viral_complete.fna -dbtype nucl \
  -out genbank_viral_nt -title "GenBank Viral NT" -parse_seqids
```

### 업데이트 주기
- **월별** (NCBI GenBank는 2개월마다 릴리즈)

### 알려진 문제
- NCBI FTP에서 대량 다운로드 시 503 에러 발생 가능
- datasets CLI로 전체 다운로드 시 zip이 깨질 수 있음 (--complete-only 권장)
- efetch로 9.2M 서열 다운로드는 수시간~수일 소요

---

## 3. Viral Protein Diamond DB (Tier 1 AA)

### 용도
Tier 1 바이러스 단백질 검색: 초기 바이러스 후보 식별

### 다운로드

```bash
cd databases/genbank_viral_protein/

# RefSeq viral protein
wget "https://ftp.ncbi.nlm.nih.gov/refseq/release/viral/viral.1.protein.faa.gz"
zcat viral.1.protein.faa.gz > viral_protein_all.faa

# Diamond DB 빌드
diamond makedb --in viral_protein_all.faa --db viral_protein_refseq --threads 8
```

### 업데이트 주기
- **월별**

---

## 4. Kraken2 core_nt (Read-level Profiling)

### 용도
독립 미생물 프로파일링: 전체 시료의 bacteria/virus/fungi/plant 비율

### 다운로드

```bash
cd databases/kraken2_core_nt/

# Pre-built index from Ben Langmead's collection (최신: Oct 2025)
wget -c "https://genome-idx.s3.amazonaws.com/kraken/k2_core_nt_20251015.tar.gz"

# 압축 해제 (~316 GB index)
tar -xzf k2_core_nt.tar.gz
```

### /dev/shm 로드 (고속 실행)

```bash
# 서버 RAM이 500GB 이상이면 /dev/shm에 로드 가능
cp -r databases/kraken2_core_nt/ /dev/shm/kraken2_db/
# 또는 Metaquant SHM 방식 사용 (bin/tui/runner.py 참조)

# Kraken2 실행 시
kraken2 --db /dev/shm/kraken2_db/ --memory-mapping ...
```

### 업데이트 주기
- **분기별** (Ben Langmead 인덱스 업데이트 주기)
- 대안: PlusPFP (bacteria+archaea+virus+protozoa+fungi+plant, 222GB)

### 시스템 요구사항
- RAM: core_nt index 316GB → **최소 320GB RAM** (+ OS + 다른 프로세스)
- 현재 서버: 503GB RAM → **가능** (여유 187GB)

---

## 5. Taxonomy DB

### 다운로드

```bash
cd databases/taxonomy/

# NCBI taxdump
wget "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz"
tar -xzf taxdump.tar.gz  # → nodes.dmp, names.dmp, merged.dmp 등

# Accession→TaxID 매핑 (UniRef50 빌드에 필요하지 않음, 참고용)
wget "https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/accession2taxid/prot.accession2taxid.FULL.gz"

# ICTV VMR
wget "https://ictv.global/vmr/current" -O ictv_vmr.tsv

# TaxonKit 데이터
taxonkit --data-dir . list --ids 1 > /dev/null  # 초기화
```

### 업데이트 주기
- taxdump: **월별**
- ICTV VMR: **연 1-2회** (ICTV 릴리즈)

---

## 6. geNomad DB

### 다운로드

```bash
# geNomad 자체 다운로드 명령
genomad download-database databases/
```

### 업데이트 주기
- geNomad 버전 업데이트 시

---

## 7. Polymicrobial NT BLAST DB (Tier 4 NT)

### 용도
Tier 4 NT 검증: Tier 1-3에서 "viral"로 분류된 contig이 실제 bacteria/archaea/fungi/plant/protozoa 게놈과 유사한지 최종 확인.
Hecatomb 방식의 비바이러스 필터링.

### 구성

| 생물군 | Taxon ID | Filter | Genomes | FASTA Size |
|--------|----------|--------|---------|------------|
| Bacteria | 2 | RefSeq reference + complete | ~6,367 | ~7 GB |
| Archaea | 2157 | RefSeq reference | ~809 | ~700 MB |
| Fungi | 4751 | RefSeq reference | ~661 | ~6.4 GB |
| Plant | 33090 | RefSeq reference + complete | ~8 | ~1.5 GB |
| Protozoa | 5794 | RefSeq reference | ~47 | ~360 MB |
| **Total** | | | **~7,892** | **~16 GB** |

### 빌드 (자동화 스크립트)

```bash
cd databases/polymicrobial_nt/

# 전체 빌드 (다운로드 + FASTA 추출 + BLAST DB 빌드)
bash build_polymicrobial_nt.sh --threads 8

# 다운로드 건너뛰기 (FASTA 이미 있을 때)
bash build_polymicrobial_nt.sh --skip-download --threads 8
```

스크립트가 자동으로:
1. NCBI datasets CLI로 각 생물군 다운로드
2. ZIP에서 FASTA 추출 및 그룹별 병합
3. 전체 통합 FASTA 생성
4. makeblastdb로 BLAST DB 빌드
5. VERSION.json 작성

### 수동 빌드

```bash
cd databases/polymicrobial_nt/

# 1. 각 생물군 다운로드
datasets download genome taxon 2 --assembly-source refseq --reference --assembly-level complete --include genome --filename bacteria_ref.zip
datasets download genome taxon 2157 --assembly-source refseq --reference --include genome --filename archaea_ref.zip
datasets download genome taxon 4751 --assembly-source refseq --reference --include genome --filename fungi_ref.zip
datasets download genome taxon 33090 --assembly-source refseq --reference --assembly-level complete --include genome --filename plant_ref.zip
datasets download genome taxon 5794 --assembly-source refseq --reference --include genome --filename protozoa_ref.zip

# 2. ZIP 해제 및 FASTA 추출
for g in bacteria archaea fungi plant protozoa; do
    unzip -q ${g}_ref.zip -d ${g}_extracted
    find ${g}_extracted -name "*.fna" -exec cat {} + > ${g}.fasta
    rm -rf ${g}_extracted
done

# 3. 통합
cat bacteria.fasta archaea.fasta fungi.fasta plant.fasta protozoa.fasta > polymicrobial_nt.fasta

# 4. BLAST DB 빌드
makeblastdb -in polymicrobial_nt.fasta -dbtype nucl -out polymicrobial_nt -title "Polymicrobial NT" -parse_seqids
```

### 파이프라인 연동

```bash
# Nextflow 실행 시
nextflow run main.nf --polymicrobial_nt_db databases/polymicrobial_nt/polymicrobial_nt ...
```

### 업데이트 주기
- **반기별** (RefSeq representative genome은 안정적)
- 새 병원체 outbreak 시 수동 업데이트 고려

### 알려진 문제
- Plant reference genome (200개)은 62GB로 매우 큼 → complete genome (8개, 1.5GB)만 사용
- Bacteria reference도 22K+ → complete genome 필터로 6.3K로 축소
- NFS에서 BLAST 실행 시 I/O 병목 → local SSD 또는 /dev/shm 복사 권장

---

## 전체 DB 한 번에 설치

```bash
# install_databases.py 사용
python bin/install_databases.py --db-dir databases --components all --dry-run  # 미리보기
python bin/install_databases.py --db-dir databases --components all             # 실행
```

---

## DB 버전 관리

### db_config.json

```json
{
  "schema_version": "2.0",
  "databases": {
    "uniref50": {
      "version": "2026_01",
      "download_date": "2026-03-25",
      "source": "UniProt",
      "sequences": 60315044,
      "size_gb": 24,
      "update_frequency": "quarterly"
    },
    "kraken2_core_nt": {
      "version": "20251015",
      "download_date": "2026-03-25",
      "source": "genome-idx.s3.amazonaws.com",
      "size_gb": 316,
      "update_frequency": "quarterly"
    }
  }
}
```

### 업데이트 확인

```bash
python bin/install_databases.py --check-updates --db-dir databases
```

---

## 트러블슈팅

### Diamond makedb 에러

| 에러 | 원인 | 해결 |
|------|------|------|
| `Error: Invalid taxonomic rank: domain` | nodes.dmp에 비표준 rank | `sed -i 's/\tdomain\t/\tsuperkingdom\t/g' nodes.dmp` |
| `Error: Invalid taxonomic rank: acellular root` | 동일 | 비표준 rank → no rank 변환 |
| `Error: Accession mapping file header` | taxonmap 헤더 없음 | 첫 줄에 `accession.version\ttaxid` 추가 |
| `Sequences: 0` (빌드 중간 체크) | 빌드 미완료 | diamond 프로세스 완료 대기 |

### NCBI 다운로드 에러

| 에러 | 원인 | 해결 |
|------|------|------|
| `503 Service Unavailable` | NCBI FTP 일시적 과부하 | 재시도 또는 datasets CLI 사용 |
| `SSL_read: unexpected eof` | 대량 efetch 시 연결 끊김 | 배치 분할 또는 NCBI API key 등록 |
| `zip: not a zipfile` | datasets CLI 다운로드 불완전 | --complete-only 옵션 또는 재시도 |

### Kraken2 메모리 문제

| 상황 | 해결 |
|------|------|
| core_nt index (316GB) 로드 실패 | /dev/shm 용량 확인: `df -h /dev/shm` |
| OOM killer | PlusPFP-16 (15GB) 사용하여 테스트 먼저 |
| NFS에서 느림 | /dev/shm으로 복사 후 --memory-mapping |
