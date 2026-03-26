// @TASK T8.1 - Kraken2 read-level taxonomy annotation
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#81-new-processes
// Classifies all host-depleted reads with Kraken2. This is annotation only.

process KRAKEN2_CLASSIFY {
    tag "$meta.id"
    label 'process_kraken2'
    publishDir "${params.outdir}/kraken2", mode: 'copy'

    input:
    tuple val(meta), path(reads)
    path(kraken2_db)

    output:
    tuple val(meta), path("*.kraken2.report"), emit: report
    tuple val(meta), path("*.kraken2.output"), emit: output

    script:
    def prefix = meta.id
    def memoryMapping = kraken2_db.toString().startsWith('/dev/shm') ? '--memory-mapping' : ''
    """
    kraken2 \\
        --db ${kraken2_db} \\
        --threads ${task.cpus} \\
        --paired ${reads[0]} ${reads[1]} \\
        --report ${prefix}.kraken2.report \\
        --output ${prefix}.kraken2.output \\
        --confidence ${params.kraken2_confidence ?: 0.0} \\
        ${memoryMapping}
    """

    stub:
    def prefix = meta.id
    """
    cat <<'EOF' > ${prefix}.kraken2.report
100.00	1000	1000	R	1	root
60.00	600	600	D	2	Bacteria
25.00	250	250	K	10239	Viruses
15.00	150	150	U	0	unclassified
EOF
    cat <<'EOF' > ${prefix}.kraken2.output
C	read1/1	10239	100|100	A:1
C	read1/2	10239	100|100	A:1
U	read2/1	0	0:0	A:0
U	read2/2	0	0:0	A:0
EOF
    """
}
