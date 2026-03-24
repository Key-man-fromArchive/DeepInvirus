// @TASK T6.2 - Prodigal ORF prediction for novel virus contigs
// @SPEC docs/planning/02-trd.md#3.2-pipeline-stages

process PRODIGAL {
    tag "$meta.id"
    label 'process_prodigal'

    input:
    tuple val(meta), path(fasta)

    output:
    tuple val(meta), path("*.proteins.faa"), emit: proteins
    tuple val(meta), path("*.genes.gff"), emit: gff

    script:
    def prefix = meta.id
    """
    prodigal \
        -i ${fasta} \
        -a ${prefix}.proteins.faa \
        -o ${prefix}.genes.gff \
        -f gff \
        -p meta
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}.proteins.faa ${prefix}.genes.gff
    """
}
