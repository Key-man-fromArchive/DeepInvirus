// @TASK T8.9 - Hybrid v1 iterative 4-tier classification
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#24-stage-4-iterative-classification-hecatomb-style-4-tier

include { PRODIGAL             } from '../modules/local/prodigal'
include { DIAMOND_TIER1_AA     } from '../modules/local/diamond_tier1_aa'
include { DIAMOND_TIER2_AA     } from '../modules/local/diamond_tier2_aa'
include { BLASTN_TIER3_NT      } from '../modules/local/blastn_tier3_nt'
include { BLASTN_TIER4_NT      } from '../modules/local/blastn_tier4_nt'
include { EVIDENCE_INTEGRATION } from '../modules/local/evidence_integration'

process SELECT_TIER1_HIT_IDS {
    tag "$meta.id"
    label 'process_low'

    input:
    tuple val(meta), path(hits)

    output:
    tuple val(meta), path("*.ids.txt"), emit: ids

    script:
    def prefix = meta.id
    """
    if [ -s ${hits} ]; then
        cut -f1 ${hits} | sort -u > ${prefix}.ids.txt
    else
        : > ${prefix}.ids.txt
    fi
    """

    stub:
    def prefix = meta.id
    """
    echo "contig_1" > ${prefix}.ids.txt
    """
}

process SELECT_TIER1_FASTA_BY_IDS {
    tag "$meta.id"
    label 'process_low'

    input:
    tuple val(meta), path(contigs), path(ids)

    output:
    tuple val(meta), path("*.selected.fa"), emit: fasta

    script:
    def prefix = meta.id
    """
    python - <<'PY'
from pathlib import Path

fasta = Path("${contigs}")
ids = {line.strip() for line in Path("${ids}").read_text().splitlines() if line.strip()}
out = Path("${prefix}.selected.fa")

with fasta.open() as fin, out.open("w") as fout:
    write = False
    for line in fin:
        if line.startswith(">"):
            seq_id = line[1:].split()[0]
            write = seq_id in ids
        if write:
            fout.write(line)
PY
    """

    stub:
    def prefix = meta.id
    """
    echo ">contig_1" > ${prefix}.selected.fa
    echo "ATGC" >> ${prefix}.selected.fa
    """
}

process EXCLUDE_TIER1_FASTA_BY_IDS {
    tag "$meta.id"
    label 'process_low'

    input:
    tuple val(meta), path(contigs), path(ids)

    output:
    tuple val(meta), path("*.excluded.fa"), emit: fasta

    script:
    def prefix = meta.id
    """
    python - <<'PY'
from pathlib import Path

fasta = Path("${contigs}")
ids = {line.strip() for line in Path("${ids}").read_text().splitlines() if line.strip()}
out = Path("${prefix}.excluded.fa")

with fasta.open() as fin, out.open("w") as fout:
    write = False
    for line in fin:
        if line.startswith(">"):
            seq_id = line[1:].split()[0]
            write = seq_id not in ids
        if write:
            fout.write(line)
PY
    """

    stub:
    def prefix = meta.id
    """
    echo ">contig_2" > ${prefix}.excluded.fa
    echo "ATGC" >> ${prefix}.excluded.fa
    """
}

process SELECT_TIER3_HIT_IDS {
    tag "$meta.id"
    label 'process_low'

    input:
    tuple val(meta), path(hits)

    output:
    tuple val(meta), path("*.ids.txt"), emit: ids

    script:
    def prefix = meta.id
    """
    if [ -s ${hits} ]; then
        cut -f1 ${hits} | sort -u > ${prefix}.ids.txt
    else
        : > ${prefix}.ids.txt
    fi
    """

    stub:
    def prefix = meta.id
    """
    echo "contig_1" > ${prefix}.ids.txt
    """
}

process SELECT_TIER3_FASTA_BY_IDS {
    tag "$meta.id"
    label 'process_low'

    input:
    tuple val(meta), path(contigs), path(ids)

    output:
    tuple val(meta), path("*.selected.fa"), emit: fasta

    script:
    def prefix = meta.id
    """
    python - <<'PY'
from pathlib import Path

fasta = Path("${contigs}")
ids = {line.strip() for line in Path("${ids}").read_text().splitlines() if line.strip()}
out = Path("${prefix}.selected.fa")

with fasta.open() as fin, out.open("w") as fout:
    write = False
    for line in fin:
        if line.startswith(">"):
            seq_id = line[1:].split()[0]
            write = seq_id in ids
        if write:
            fout.write(line)
PY
    """

    stub:
    def prefix = meta.id
    """
    echo ">contig_1" > ${prefix}.selected.fa
    echo "ATGC" >> ${prefix}.selected.fa
    """
}

workflow ITERATIVE_CLASSIFICATION {

    take:
    ch_contigs
    ch_genomad_summary
    ch_taxonomy_nodes
    ch_viral_protein_db
    ch_uniref50_db
    ch_viral_nt_db
    ch_polymicrobial_nt_db

    main:
    ch_contigs_meta = ch_contigs.map { contigs -> [ [id: 'coassembly'], contigs ] }
    PRODIGAL( ch_contigs_meta )

    // Use unique empty file names to avoid Nextflow input file name collision
    def nullTier2 = Channel.value([ [id: 'coassembly'], file("${projectDir}/assets/empty_tier2.tsv") ])
    def nullTier3 = Channel.value([ [id: 'coassembly'], file("${projectDir}/assets/empty_tier3.tsv") ])
    def nullTier4 = Channel.value([ [id: 'coassembly'], file("${projectDir}/assets/empty_tier4.tsv") ])

    DIAMOND_TIER1_AA( ch_contigs_meta, ch_viral_protein_db )
    ch_tier1_hits = DIAMOND_TIER1_AA.out.hits

    SELECT_TIER1_HIT_IDS( ch_tier1_hits )
    ch_tier1_ids = SELECT_TIER1_HIT_IDS.out.ids

    if ( params.uniref50_db ) {
        SELECT_TIER1_FASTA_BY_IDS( ch_contigs_meta.join(ch_tier1_ids) )
        DIAMOND_TIER2_AA( SELECT_TIER1_FASTA_BY_IDS.out.fasta, ch_uniref50_db )
        ch_tier2_hits = DIAMOND_TIER2_AA.out.hits
    } else {
        ch_tier2_hits = nullTier2
    }

    if ( params.viral_nt_db ) {
        EXCLUDE_TIER1_FASTA_BY_IDS( ch_contigs_meta.join(ch_tier1_ids) )
        ch_tier3_input = EXCLUDE_TIER1_FASTA_BY_IDS.out.fasta
        BLASTN_TIER3_NT( ch_tier3_input, ch_viral_nt_db )
        ch_tier3_hits = BLASTN_TIER3_NT.out.hits
    } else {
        ch_tier3_hits = nullTier3
    }

    SELECT_TIER3_HIT_IDS( ch_tier3_hits )
    ch_tier3_ids = SELECT_TIER3_HIT_IDS.out.ids

    if ( params.polymicrobial_nt_db && params.viral_nt_db ) {
        SELECT_TIER3_FASTA_BY_IDS( ch_contigs_meta.join(ch_tier3_ids) )
        BLASTN_TIER4_NT( SELECT_TIER3_FASTA_BY_IDS.out.fasta, ch_polymicrobial_nt_db )
        ch_tier4_hits = BLASTN_TIER4_NT.out.hits
    } else {
        ch_tier4_hits = nullTier4
    }

    EVIDENCE_INTEGRATION(
        ch_contigs_meta,
        ch_tier1_hits.map { meta, f -> f },
        ch_tier2_hits.map { meta, f -> f },
        ch_tier3_hits.map { meta, f -> f },
        ch_tier4_hits.map { meta, f -> f },
        ch_genomad_summary.map { meta, f -> f },
        ch_taxonomy_nodes
    )

    emit:
    proteins   = PRODIGAL.out.proteins
    gff        = PRODIGAL.out.gff
    tier1_hits = ch_tier1_hits
    tier2_hits = ch_tier2_hits
    tier3_hits = ch_tier3_hits
    tier4_hits = ch_tier4_hits
    classified = EVIDENCE_INTEGRATION.out.classified
}
