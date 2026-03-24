// Read coverage calculation using CoverM (per-sample, legacy - reads+contigs joined)

process COVERM {
    tag "$meta.id"
    label 'process_coverm'
    publishDir "${params.outdir}/coverage", mode: 'copy'

    input:
    tuple val(meta), path(reads), path(contigs)

    output:
    tuple val(meta), path("*_coverage.tsv"), emit: coverage

    script:
    def prefix = meta.id
    """
    # Map reads to contigs and calculate coverage metrics
    coverm contig \\
        -1 ${reads[0]} \\
        -2 ${reads[1]} \\
        -r ${contigs} \\
        -o ${prefix}_coverage.tsv \\
        -t ${task.cpus} \\
        -m mean trimmed_mean covered_bases length
    """

    stub:
    def prefix = meta.id
    """
    echo -e "Contig\\tMean\\tTrimmed Mean\\tCovered Bases\\tLength" > ${prefix}_coverage.tsv
    echo -e "contig_1\\t10.5\\t9.8\\t4500\\t5000" >> ${prefix}_coverage.tsv
    """
}

// Per-sample read mapping to co-assembly contigs
process COVERM_PERSAMPLE {
    tag "$meta.id"
    label 'process_coverm'
    publishDir "${params.outdir}/coverage", mode: 'copy'

    input:
    tuple val(meta), path(reads)
    path(contigs)  // co-assembly contigs (shared reference)

    output:
    tuple val(meta), path("*_coverage.tsv"), emit: coverage

    script:
    def prefix = meta.id
    """
    # Map per-sample reads to co-assembly contigs and calculate coverage
    coverm contig \\
        -1 ${reads[0]} \\
        -2 ${reads[1]} \\
        -r ${contigs} \\
        -o ${prefix}_coverage.tsv \\
        -t ${task.cpus} \\
        -m mean trimmed_mean covered_bases length
    """

    stub:
    def prefix = meta.id
    """
    echo -e "Contig\\tMean\\tTrimmed Mean\\tCovered Bases\\tLength" > ${prefix}_coverage.tsv
    echo -e "contig_1\\t10.5\\t9.8\\t4500\\t5000" >> ${prefix}_coverage.tsv
    """
}
