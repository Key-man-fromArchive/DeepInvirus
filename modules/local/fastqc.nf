// @TASK T2.2 - FastQC quality assessment
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// FastQC quality assessment before/after trimming

process FASTQC {
    tag "$meta.id"
    label 'process_fastqc'
    publishDir "${params.outdir}/qc/fastqc", mode: 'copy'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("*.html"), emit: html
    tuple val(meta), path("*.zip"),  emit: zip

    script:
    def prefix = meta.id
    """
    fastqc --threads ${task.cpus} --outdir . ${reads}
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}_R1_fastqc.html ${prefix}_R1_fastqc.zip
    touch ${prefix}_R2_fastqc.html ${prefix}_R2_fastqc.zip
    """
}
