#!/usr/bin/env python3
"""
Generate synthetic test data for DeepInvirus unit and integration tests.

This script creates:
1. Synthetic FASTQ files (R1 and R2 paired-end reads)
2. Expected output tables (bigtable, diversity tables, etc.)
3. Mock database files
"""

import gzip
import json
from pathlib import Path
from datetime import datetime


def generate_fastq_reads(output_file: Path, num_reads: int = 15) -> None:
    """
    Generate synthetic FASTQ reads and compress with gzip.

    Args:
        output_file: Output gzip FASTQ file path
        num_reads: Number of reads to generate (default: 15)
    """
    # Create synthetic reads
    reads = []

    for i in range(num_reads):
        # Simulate FASTQ record
        header = f"@read_{i+1}/1 simulation"
        # Synthetic sequence (simulate viral-like sequences)
        sequence = "ATGCGATCGATCGATCGATCGATCGATCGATCGATCG"[: 30 + (i % 10)]
        plus = "+"
        quality = "I" * len(sequence)  # High quality (I = ASCII 73)

        reads.append(f"{header}\n{sequence}\n{plus}\n{quality}\n")

    # Write compressed FASTQ
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(output_file, 'wt') as f:
        f.writelines(reads)

    print(f"Generated {output_file.name} with {num_reads} reads")


def generate_bigtable(output_file: Path) -> None:
    """
    Generate synthetic bigtable.tsv following schema from 04-database-design.md.

    Schema:
    seq_id, sample, seq_type, length, detection_method, detection_score, taxid,
    domain, phylum, class, order, family, genus, species, ictv_classification,
    baltimore_group, count, rpm, coverage
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Header
    header = [
        "seq_id", "sample", "seq_type", "length", "detection_method",
        "detection_score", "taxid", "domain", "phylum", "class", "order",
        "family", "genus", "species", "ictv_classification", "baltimore_group",
        "count", "rpm", "coverage"
    ]

    # Sample data rows
    rows = [
        {
            "seq_id": "viral_contig_001",
            "sample": "sample_A",
            "seq_type": "contig",
            "length": 2847,
            "detection_method": "both",
            "detection_score": 0.95,
            "taxid": 10239,
            "domain": "Virus",
            "phylum": "Negarnaviricota",
            "class": "Polyploviricetes",
            "order": "Mononegavirales",
            "family": "Filoviridae",
            "genus": "Ebolavirus",
            "species": "Zaire ebolavirus",
            "ictv_classification": "Filoviridae; Ebolavirus",
            "baltimore_group": "Group V (-ssRNA)",
            "count": 245,
            "rpm": 1230.5,
            "coverage": 18.7
        },
        {
            "seq_id": "read_contig_002",
            "sample": "sample_A",
            "seq_type": "read",
            "length": 150,
            "detection_method": "diamond",
            "detection_score": 0.87,
            "taxid": 11320,
            "domain": "Virus",
            "phylum": "Pisuviricota",
            "class": "Herviviricetes",
            "order": "Picornavirales",
            "family": "Picornaviridae",
            "genus": "Enterovirus",
            "species": "Enterovirus A",
            "ictv_classification": "Picornaviridae; Enterovirus",
            "baltimore_group": "Group IV (+ssRNA)",
            "count": 128,
            "rpm": 644.2,
            "coverage": 0.0
        },
        {
            "seq_id": "viral_contig_003",
            "sample": "sample_B",
            "seq_type": "contig",
            "length": 1524,
            "detection_method": "genomad",
            "detection_score": 0.92,
            "taxid": 10566,
            "domain": "Virus",
            "phylum": "Nucleocytoviricota",
            "class": "Megaviricetes",
            "order": "Imitervirales",
            "family": "Asfarviridae",
            "genus": "Asfarvirus",
            "species": "African swine fever virus",
            "ictv_classification": "Asfarviridae; Asfarvirus",
            "baltimore_group": "Group I (dsDNA)",
            "count": 89,
            "rpm": 450.3,
            "coverage": 12.2
        },
        {
            "seq_id": "read_contig_004",
            "sample": "sample_B",
            "seq_type": "read",
            "length": 150,
            "detection_method": "diamond",
            "detection_score": 0.85,
            "taxid": 1980410,
            "domain": "Virus",
            "phylum": "Artverviricota",
            "class": "Revtraviricetes",
            "order": "Ortervirales",
            "family": "Retroviridae",
            "genus": "Lentivirus",
            "species": "Human immunodeficiency virus 1",
            "ictv_classification": "Retroviridae; Lentivirus",
            "baltimore_group": "Group VI (ssRNA-RT)",
            "count": 156,
            "rpm": 785.8,
            "coverage": 0.0
        },
        {
            "seq_id": "viral_contig_005",
            "sample": "sample_C",
            "seq_type": "contig",
            "length": 3200,
            "detection_method": "both",
            "detection_score": 0.93,
            "taxid": 11676,
            "domain": "Virus",
            "phylum": "Nucleocytoviricota",
            "class": "Megaviricetes",
            "order": "Megavirales",
            "family": "Poxviridae",
            "genus": "Orthopoxvirus",
            "species": "Vaccinia virus",
            "ictv_classification": "Poxviridae; Orthopoxvirus",
            "baltimore_group": "Group I (dsDNA)",
            "count": 312,
            "rpm": 1567.3,
            "coverage": 25.4
        }
    ]

    # Write TSV
    with open(output_file, 'w') as f:
        f.write('\t'.join(header) + '\n')
        for row in rows:
            values = [str(row[col]) for col in header]
            f.write('\t'.join(values) + '\n')

    print(f"Generated {output_file.name} with {len(rows)} data rows")


def generate_sample_taxon_matrix(output_file: Path) -> None:
    """
    Generate synthetic sample_taxon_matrix.tsv following schema from 04-database-design.md.

    Schema:
    taxon, taxid, rank, sample1, sample2, ...
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Header: taxon, taxid, rank, sample_A, sample_B, sample_C
    header = ["taxon", "taxid", "rank", "sample_A", "sample_B", "sample_C"]

    # Sample data - genus level
    rows = [
        {
            "taxon": "Ebolavirus",
            "taxid": 40566,
            "rank": "genus",
            "sample_A": 1230.5,
            "sample_B": 0.0,
            "sample_C": 0.0
        },
        {
            "taxon": "Enterovirus",
            "taxid": 12059,
            "rank": "genus",
            "sample_A": 644.2,
            "sample_B": 0.0,
            "sample_C": 0.0
        },
        {
            "taxon": "Asfarvirus",
            "taxid": 40359,
            "rank": "genus",
            "sample_A": 0.0,
            "sample_B": 450.3,
            "sample_C": 0.0
        },
        {
            "taxon": "Lentivirus",
            "taxid": 11627,
            "rank": "genus",
            "sample_A": 0.0,
            "sample_B": 785.8,
            "sample_C": 0.0
        },
        {
            "taxon": "Orthopoxvirus",
            "taxid": 10244,
            "rank": "genus",
            "sample_A": 0.0,
            "sample_B": 0.0,
            "sample_C": 1567.3
        }
    ]

    # Write TSV
    with open(output_file, 'w') as f:
        f.write('\t'.join(header) + '\n')
        for row in rows:
            values = [str(row[col]) for col in header]
            f.write('\t'.join(values) + '\n')

    print(f"Generated {output_file.name} with {len(rows)} data rows")


def generate_alpha_diversity(output_file: Path) -> None:
    """
    Generate synthetic alpha_diversity.tsv following schema from 04-database-design.md.

    Schema:
    sample, observed_species, shannon, simpson, chao1, pielou_evenness
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    header = ["sample", "observed_species", "shannon", "simpson", "chao1", "pielou_evenness"]

    rows = [
        {
            "sample": "sample_A",
            "observed_species": 2,
            "shannon": 0.693,
            "simpson": 0.667,
            "chao1": 2.0,
            "pielou_evenness": 0.500
        },
        {
            "sample": "sample_B",
            "observed_species": 2,
            "shannon": 0.689,
            "simpson": 0.667,
            "chao1": 2.0,
            "pielou_evenness": 0.497
        },
        {
            "sample": "sample_C",
            "observed_species": 1,
            "shannon": 0.000,
            "simpson": 0.000,
            "chao1": 1.0,
            "pielou_evenness": 0.000
        }
    ]

    with open(output_file, 'w') as f:
        f.write('\t'.join(header) + '\n')
        for row in rows:
            values = [str(row[col]) for col in header]
            f.write('\t'.join(values) + '\n')

    print(f"Generated {output_file.name} with {len(rows)} data rows")


def generate_beta_diversity(output_file: Path) -> None:
    """
    Generate synthetic beta_diversity.tsv (Bray-Curtis distance matrix).

    Schema: Symmetric distance matrix with samples as rows and columns
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    samples = ["sample_A", "sample_B", "sample_C"]

    # Bray-Curtis distance matrix (symmetric)
    matrix = [
        [0.0, 0.45, 0.89],
        [0.45, 0.0, 0.72],
        [0.89, 0.72, 0.0]
    ]

    with open(output_file, 'w') as f:
        # Header row
        f.write('\t' + '\t'.join(samples) + '\n')

        # Data rows
        for i, sample in enumerate(samples):
            row_values = [sample] + [str(matrix[i][j]) for j in range(len(samples))]
            f.write('\t'.join(row_values) + '\n')

    print(f"Generated {output_file.name} with {len(samples)}x{len(samples)} distance matrix")


def generate_taxonomy_dmp_files(names_file: Path, nodes_file: Path) -> None:
    """
    Generate minimal NCBI taxonomy dump files for mock database.

    Format:
    - names.dmp: tax_id | name_txt | unique_name | name_class
    - nodes.dmp: tax_id | parent_tax_id | rank | ... (simplified)
    """
    names_file.parent.mkdir(parents=True, exist_ok=True)

    # Minimal names.dmp with common taxids
    names_data = [
        "1\t|\troot\t|\t\t|\tscientific name\t|",
        "10239\t|\tVirus\t|\t\t|\tscientific name\t|",
        "40566\t|\tEbolavirus\t|\t\t|\tscientific name\t|",
        "12059\t|\tEnterovirus\t|\t\t|\tscientific name\t|",
        "40359\t|\tAsfarvirus\t|\t\t|\tscientific name\t|",
        "11627\t|\tLentivirus\t|\t\t|\tscientific name\t|",
        "10244\t|\tOrthopoxvirus\t|\t\t|\tscientific name\t|",
    ]

    with open(names_file, 'w') as f:
        f.write('\n'.join(names_data) + '\n')

    # Minimal nodes.dmp with parent relationships
    nodes_data = [
        "1\t|\t1\t|\tno rank\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t0\t|\t0\t|",
        "10239\t|\t1\t|\tsuperkingdom\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t0\t|\t0\t|",
        "40566\t|\t10239\t|\tgenus\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t0\t|\t0\t|",
        "12059\t|\t10239\t|\tgenus\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t0\t|\t0\t|",
        "40359\t|\t10239\t|\tgenus\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t0\t|\t0\t|",
        "11627\t|\t10239\t|\tgenus\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t0\t|\t0\t|",
        "10244\t|\t10239\t|\tgenus\t|\t\t|\t0\t|\t0\t|\t11\t|\t0\t|\t0\t|\t0\t|\t0\t|\t0\t|",
    ]

    with open(nodes_file, 'w') as f:
        f.write('\n'.join(nodes_data) + '\n')

    print(f"Generated taxonomy dump files (names.dmp, nodes.dmp)")


def generate_version_json(output_file: Path) -> None:
    """
    Generate VERSION.json following schema from 04-database-design.md section 2.
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    version_data = {
        "schema_version": "1.0",
        "created_at": "2026-03-23T00:00:00Z",
        "updated_at": "2026-03-23T00:00:00Z",
        "databases": {
            "viral_protein": {
                "source": "UniRef90 viral subset",
                "version": "2026_01",
                "url": "https://ftp.uniprot.org/pub/databases/uniprot/uniref/uniref90/",
                "downloaded_at": "2026-03-23",
                "record_count": 2500000,
                "format": "diamond"
            },
            "viral_nucleotide": {
                "source": "NCBI RefSeq Viral",
                "version": "release_224",
                "url": "https://ftp.ncbi.nlm.nih.gov/refseq/release/viral/",
                "downloaded_at": "2026-03-23",
                "record_count": 15000,
                "format": "mmseqs2"
            },
            "genomad_db": {
                "source": "geNomad",
                "version": "1.7",
                "url": "https://zenodo.org/records/...",
                "downloaded_at": "2026-03-23"
            },
            "taxonomy": {
                "ncbi_version": "2026-03-20",
                "ictv_version": "VMR_MSL39_v3",
                "downloaded_at": "2026-03-23"
            }
        }
    }

    with open(output_file, 'w') as f:
        json.dump(version_data, f, indent=2)

    print(f"Generated {output_file.name}")


def main():
    """Generate all test data files."""
    base_dir = Path(__file__).parent

    print("Generating test data for DeepInvirus...\n")

    # 1. Generate FASTQ files
    reads_dir = base_dir / "reads"
    reads_dir.mkdir(exist_ok=True)

    generate_fastq_reads(reads_dir / "test_R1.fastq.gz", num_reads=15)
    generate_fastq_reads(reads_dir / "test_R2.fastq.gz", num_reads=15)

    # 2. Generate expected output tables
    expected_dir = base_dir / "expected"
    expected_dir.mkdir(exist_ok=True)

    generate_bigtable(expected_dir / "bigtable.tsv")
    generate_sample_taxon_matrix(expected_dir / "sample_taxon_matrix.tsv")
    generate_alpha_diversity(expected_dir / "alpha_diversity.tsv")
    generate_beta_diversity(expected_dir / "beta_diversity.tsv")

    # 3. Generate mock database files
    db_dir = base_dir / "db"
    taxonomy_dir = db_dir / "taxonomy"
    taxonomy_dir.mkdir(parents=True, exist_ok=True)

    generate_taxonomy_dmp_files(
        taxonomy_dir / "names.dmp",
        taxonomy_dir / "nodes.dmp"
    )
    generate_version_json(db_dir / "VERSION.json")

    print("\nAll test data generated successfully!")


if __name__ == "__main__":
    main()
