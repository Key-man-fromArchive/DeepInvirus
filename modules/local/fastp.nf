// @TASK T2.1 - Fastp quality trimming
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// QC + adapter trimming + deduplication via fastp

process FASTP {
    tag "$meta.id"
    label 'process_fastp'
    publishDir "${params.outdir}/qc", mode: 'copy', pattern: "*.fastp.{json,html}"

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("*.trimmed.fastq.gz"), emit: reads
    tuple val(meta), path("*.fastp.json"),       emit: json
    tuple val(meta), path("*.fastp.html"),       emit: html

    script:
    def prefix = meta.id
    """
    fastp \\
        -i ${reads[0]} \\
        -I ${reads[1]} \\
        -o ${prefix}_R1.trimmed.fastq.gz \\
        -O ${prefix}_R2.trimmed.fastq.gz \\
        -j ${prefix}.fastp.json \\
        -h ${prefix}.fastp.html \\
        --thread ${task.cpus} \\
        --qualified_quality_phred 15 \\
        --length_required 90 \\
        --cut_tail \\
        --dedup \\
        --trim_poly_x \\
        --detect_adapter_for_pe
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}_R1.trimmed.fastq.gz
    touch ${prefix}_R2.trimmed.fastq.gz
    echo '{}' > ${prefix}.fastp.json
    echo '<html></html>' > ${prefix}.fastp.html
    """
}
