// @TASK T1.1 - QC + adapter trimming via BBDuk (BBTools)
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// @SPEC docs/planning/02-trd.md#2.2-분석-도구
// @TEST tests/modules/test_bbduk.py

process BBDUK {
    tag "$meta.id"
    label 'process_high'
    label 'process_bbduk'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("*_R{1,2}.trimmed.fastq.gz"), emit: reads
    tuple val(meta), path("*.bbduk_stats.txt"),          emit: stats

    script:
    def prefix = meta.id
    """
    # Step 1: Remove adapters
    bbduk.sh \\
        in1=${reads[0]} in2=${reads[1]} \\
        out1=${prefix}_clean1.fastq.gz out2=${prefix}_clean2.fastq.gz \\
        ref=adapters,artifacts \\
        ktrim=r k=23 mink=11 hdist=1 tpe tbo \\
        threads=${task.cpus} \\
        stats=${prefix}.adapter_stats.txt

    # Step 2: Remove PhiX and vector contaminants
    bbduk.sh \\
        in1=${prefix}_clean1.fastq.gz in2=${prefix}_clean2.fastq.gz \\
        out1=${prefix}_nophix1.fastq.gz out2=${prefix}_nophix2.fastq.gz \\
        ref=/opt/conda/opt/bbmap-39.80-0/resources/phix174_ill.ref.fa.gz \\
        k=31 hdist=1 \\
        threads=${task.cpus} \\
        stats=${prefix}.phix_stats.txt

    # Step 3: Quality trimming + length filtering
    bbduk.sh \\
        in1=${prefix}_nophix1.fastq.gz in2=${prefix}_nophix2.fastq.gz \\
        out1=${prefix}_R1.trimmed.fastq.gz out2=${prefix}_R2.trimmed.fastq.gz \\
        qtrim=r trimq=20 minlength=90 \\
        maq=20 \\
        threads=${task.cpus} \\
        stats=${prefix}.quality_stats.txt

    # Combine stats
    cat ${prefix}.adapter_stats.txt ${prefix}.phix_stats.txt ${prefix}.quality_stats.txt > ${prefix}.bbduk_stats.txt

    # Cleanup intermediate files
    rm -f ${prefix}_clean*.fastq.gz ${prefix}_nophix*.fastq.gz
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}_R1.trimmed.fastq.gz ${prefix}_R2.trimmed.fastq.gz
    echo "BBDuk stats (stub)" > ${prefix}.bbduk_stats.txt
    """
}
