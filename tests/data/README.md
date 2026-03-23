# Test Data for DeepInvirus

This directory contains synthetic test data for unit and integration tests of the DeepInvirus pipeline.

## Directory Structure

```
tests/data/
├── reads/                          # Input FASTQ files
│   ├── test_R1.fastq.gz           # Synthetic paired-end reads (R1)
│   └── test_R2.fastq.gz           # Synthetic paired-end reads (R2)
├── expected/                       # Expected output files for validation
│   ├── bigtable.tsv               # Integrated classification table
│   ├── sample_taxon_matrix.tsv    # Sample x taxon abundance matrix
│   ├── alpha_diversity.tsv        # Alpha diversity metrics
│   └── beta_diversity.tsv         # Beta diversity (Bray-Curtis) distance matrix
├── db/                            # Mock reference databases
│   ├── taxonomy/
│   │   ├── names.dmp              # NCBI taxonomy names
│   │   └── nodes.dmp              # NCBI taxonomy hierarchy
│   └── VERSION.json               # Database version metadata
└── generate_test_data.py          # Script to generate all test data
```

## Test Data Overview

### 1. Input FASTQ Files (`reads/`)

Generated synthetic paired-end reads with:
- 15 reads per file
- Valid FASTQ format (@ header, sequence, +, quality)
- gzip compression
- File size < 1KB

**Format Validation:**
```bash
gzip -t tests/data/reads/test_R1.fastq.gz
gzip -t tests/data/reads/test_R2.fastq.gz
```

### 2. Expected Output Tables (`expected/`)

#### bigtable.tsv (19 columns)
Integrated classification table with:
- **seq_id**: Sequence identifier
- **sample**: Sample name (sample_A, sample_B, sample_C)
- **seq_type**: read or contig
- **length**: Sequence length (bp)
- **detection_method**: genomad / diamond / both
- **detection_score**: Detection confidence (0.0-1.0)
- **taxid**: NCBI Taxonomy ID
- **domain, phylum, class, order, family, genus, species**: Taxonomic ranks
- **ictv_classification**: ICTV 2024 classification
- **baltimore_group**: Baltimore classification (Group I-VII)
- **count**: Number of reads
- **rpm**: Reads Per Million
- **coverage**: Genome coverage (0.0 for reads)

**Data:** 5 example rows covering different virus families and detection methods

#### sample_taxon_matrix.tsv (6 columns)
Sample x taxon abundance matrix at genus level:
- **taxon**: Taxonomic name
- **taxid**: NCBI Taxonomy ID
- **rank**: Classification rank (genus)
- **sample_A, sample_B, sample_C**: RPM values for each sample

**Data:** 5 virus genera with varying abundance patterns

#### alpha_diversity.tsv (6 columns)
Alpha diversity indices for each sample:
- **sample**: Sample name
- **observed_species**: Number of detected species
- **shannon**: Shannon diversity index
- **simpson**: Simpson diversity index
- **chao1**: Chao1 richness estimator
- **pielou_evenness**: Pielou's evenness index

**Data:** 3 samples with realistic diversity metrics

#### beta_diversity.tsv
Bray-Curtis distance matrix (3x3 symmetric matrix):
- Row/column headers: sample_A, sample_B, sample_C
- Diagonal: 0.0 (same sample)
- Off-diagonal: distances 0.0-1.0

**Data:** 3 samples with distance values

### 3. Mock Database Files (`db/`)

#### taxonomy/names.dmp
NCBI taxonomy names in NCBI format:
```
tax_id | name_txt | unique_name | name_class |
```

Contains 7 records: root, Virus, and 5 virus genera

#### taxonomy/nodes.dmp
NCBI taxonomy hierarchy in NCBI format:
```
tax_id | parent_tax_id | rank | ... |
```

Defines parent-child relationships for taxonomy

#### VERSION.json
Database version metadata following schema from `docs/planning/04-database-design.md`:
```json
{
  "schema_version": "1.0",
  "created_at": "2026-03-23T00:00:00Z",
  "updated_at": "2026-03-23T00:00:00Z",
  "databases": {
    "viral_protein": {...},
    "viral_nucleotide": {...},
    "genomad_db": {...},
    "taxonomy": {...}
  }
}
```

## Generating/Regenerating Test Data

Run the generation script:

```bash
cd tests/data
python3 generate_test_data.py
```

This will create/overwrite all test data files.

## Usage in Tests

Example pytest integration:

```python
import gzip
from pathlib import Path

def test_with_fastq():
    fastq_file = Path("tests/data/reads/test_R1.fastq.gz")
    with gzip.open(fastq_file, 'rt') as f:
        records = [lines.split('\n') for lines in f.readlines()]
    assert len(records) > 0

def test_bigtable_schema():
    bigtable = Path("tests/data/expected/bigtable.tsv")
    with open(bigtable) as f:
        header = f.readline().strip().split('\t')
        assert len(header) == 19  # 19 columns
        assert header[0] == "seq_id"
```

## Quality Assurance

All generated files are validated against:

✓ FASTQ files pass gzip integrity check (`gzip -t`)
✓ TSV headers match schema specifications
✓ All required columns present
✓ Data type consistency (int, float, string)
✓ VERSION.json matches database design schema
✓ Taxonomy files follow NCBI dump format

## References

- Schema specifications: `docs/planning/04-database-design.md` (Section 4)
- Database design: `docs/planning/04-database-design.md` (Section 2)
- Technical requirements: `docs/planning/02-trd.md` (Section 3.3)

## Notes

- Test data is intentionally minimal to keep tests fast
- Files are <1KB to facilitate version control
- Data represents realistic virus detection scenarios
- Samples demonstrate different diversity and abundance patterns
- TaxID values match real NCBI taxonomy (where possible)
