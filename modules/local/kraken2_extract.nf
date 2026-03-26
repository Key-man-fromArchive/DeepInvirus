// @TASK T8.2 - Kraken2 discovery/cellular read set extraction
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#81-new-processes
// Splits reads into discovery (viral + unclassified) and cellular complements.

process KRAKEN2_EXTRACT_SETS {
    tag "$meta.id"
    label 'process_kraken2'
    publishDir "${params.outdir}/kraken2/extracted", mode: 'copy'

    input:
    tuple val(meta), path(reads), path(kraken2_output), path(kraken2_report)

    output:
    tuple val(meta), path("${meta.id}.discovery_*.fastq.gz"), emit: discovery
    tuple val(meta), path("${meta.id}.cellular_*.fastq.gz"), emit: cellular

    script:
    def prefix = meta.id
    """
    extract_kraken_reads.py \\
        -k ${kraken2_output} \\
        -r ${kraken2_report} \\
        -s1 ${reads[0]} \\
        -s2 ${reads[1]} \\
        -o ${prefix}.discovery_R1.fastq.gz \\
        -o2 ${prefix}.discovery_R2.fastq.gz \\
        -t 10239 0 \\
        --include-children \\
        --fastq-output

    extract_kraken_reads.py \\
        -k ${kraken2_output} \\
        -r ${kraken2_report} \\
        -s1 ${reads[0]} \\
        -s2 ${reads[1]} \\
        -o ${prefix}.cellular_R1.fastq.gz \\
        -o2 ${prefix}.cellular_R2.fastq.gz \\
        -t 10239 0 \\
        --include-children \\
        --exclude \\
        --fastq-output
    """

    stub:
    def prefix = meta.id
    """
    cp ${reads[0]} ${prefix}.discovery_R1.fastq.gz
    cp ${reads[1]} ${prefix}.discovery_R2.fastq.gz
    cp ${reads[0]} ${prefix}.cellular_R1.fastq.gz
    cp ${reads[1]} ${prefix}.cellular_R2.fastq.gz
    """
}
