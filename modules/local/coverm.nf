// @TASK T4.1 - Read coverage calculation using CoverM
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

process COVERM {
    tag "$meta.id"
    label 'process_medium'
    label 'process_coverm'

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
