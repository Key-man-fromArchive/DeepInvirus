// @TASK T1.1 - BBDuk QC module
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// QC + adapter trimming via BBDuk (BBTools)

process BBDUK {
    tag "$meta.id"
    label 'process_medium'
    label 'process_bbduk'
    publishDir "${params.outdir}/qc", mode: 'copy', pattern: "*.bbduk_stats.txt"

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("*_R{1,2}.trimmed.fastq.gz"), emit: reads
    tuple val(meta), path("*.bbduk_stats.txt"),          emit: stats

    script:
    def prefix = meta.id
    """
    # Single-step BBDuk: adapter removal + PhiX + quality trimming
    # Uses BBTools built-in reference paths (adapters.fa, phix174_ill.ref.fa.gz)
    bbduk.sh -Xmx6g \\
        in1=${reads[0]} in2=${reads[1]} \\
        out1=${prefix}_R1.trimmed.fastq.gz out2=${prefix}_R2.trimmed.fastq.gz \\
        ref=adapters \\
        ktrim=r k=23 mink=11 hdist=1 tpe tbo \\
        qtrim=r trimq=20 minlength=90 maq=20 \\
        threads=${task.cpus} \\
        stats=${prefix}.bbduk_stats.txt
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}_R1.trimmed.fastq.gz ${prefix}_R2.trimmed.fastq.gz
    echo "BBDuk stats (stub)" > ${prefix}.bbduk_stats.txt
    """
}
