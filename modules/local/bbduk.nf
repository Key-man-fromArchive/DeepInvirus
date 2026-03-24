// QC + adapter trimming via BBDuk (BBTools)

process BBDUK {
    tag "$meta.id"
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
    # Step 1: Adapter removal + quality trimming (merged)
    # ktrim=r applies to adapter refs; qtrim/minlength/maq are independent filters
    bbduk.sh -Xmx6g \\
        in1=${reads[0]} in2=${reads[1]} \\
        out1=${prefix}_clean_R1.fastq.gz out2=${prefix}_clean_R2.fastq.gz \\
        ref=adapters,artifacts \\
        ktrim=r k=23 mink=11 hdist=1 tpe tbo \\
        qtrim=r trimq=20 minlength=90 maq=20 \\
        threads=${task.cpus} \\
        stats=${prefix}.adapter_quality_stats.txt

    # Step 2: PhiX removal only (no ktrim, filter mode)
    bbduk.sh -Xmx6g \\
        in1=${prefix}_clean_R1.fastq.gz in2=${prefix}_clean_R2.fastq.gz \\
        out1=${prefix}_R1.trimmed.fastq.gz out2=${prefix}_R2.trimmed.fastq.gz \\
        ref=/opt/conda/opt/bbmap-39.80-0/resources/phix174_ill.ref.fa.gz \\
        k=31 hdist=1 \\
        threads=${task.cpus} \\
        stats=${prefix}.phix_stats.txt

    # Combine stats
    cat ${prefix}.adapter_quality_stats.txt ${prefix}.phix_stats.txt > ${prefix}.bbduk_stats.txt

    # Cleanup intermediate files
    rm -f ${prefix}_clean_R1.fastq.gz ${prefix}_clean_R2.fastq.gz
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}_R1.trimmed.fastq.gz ${prefix}_R2.trimmed.fastq.gz
    echo "BBDuk stats (stub)" > ${prefix}.bbduk_stats.txt
    """
}
