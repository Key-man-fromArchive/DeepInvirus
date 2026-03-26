// @TASK TB.1 - CheckV viral genome quality assessment
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
//
// CheckV evaluates genome completeness and contamination of viral contigs.
// Runs after geNomad detection. Completely optional -- skipped when
// params.checkv_db is null.

process CHECKV {
    tag "$meta.id"
    label 'process_detect'
    publishDir "${params.outdir}/detection/checkv", mode: 'copy'

    input:
    tuple val(meta), path(viral_contigs)
    path(checkv_db)

    output:
    tuple val(meta), path("checkv_out/quality_summary.tsv"), emit: quality
    tuple val(meta), path("checkv_out/completeness.tsv"),    emit: completeness, optional: true
    tuple val(meta), path("checkv_out/contamination.tsv"),   emit: contamination, optional: true

    script:
    """
    checkv end_to_end ${viral_contigs} checkv_out -d ${checkv_db} -t ${task.cpus}
    """

    stub:
    """
    mkdir -p checkv_out
    echo -e "contig_id\\tcontig_length\\tcheckv_quality\\tcompleteness\\tcontamination" > checkv_out/quality_summary.tsv
    echo -e "k127_1\\t5000\\tMedium-quality\\t65.2\\t0.0" >> checkv_out/quality_summary.tsv
    touch checkv_out/completeness.tsv
    touch checkv_out/contamination.tsv
    """
}
