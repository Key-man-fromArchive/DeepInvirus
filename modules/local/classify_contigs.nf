// @TASK T3.6 - Multi-DB contig classification
// @SPEC docs/planning/12-pipeline-v2-multidb-filtering.md
// Combines Diamond exclusion results with geNomad/Diamond viral detection
// to classify contigs as viral / non-viral / unknown / review.

process CLASSIFY_CONTIGS {
    tag "$meta.id"
    label 'process_merge'
    publishDir "${params.outdir}/detection/classification", mode: 'copy'

    input:
    tuple val(meta), path(exclusion_hits)
    tuple val(meta2), path(detection_results)
    path(taxonomy_nodes)

    output:
    tuple val(meta), path("*_classified.tsv"), emit: classified

    script:
    def prefix = meta.id
    """
    classify_contigs.py \\
        --exclusion ${exclusion_hits} \\
        --detection ${detection_results} \\
        --taxonomy-nodes ${taxonomy_nodes} \\
        --output ${prefix}_classified.tsv
    """

    stub:
    def prefix = meta.id
    """
    echo -e "seq_id\\tclassification\\tevidence\\tviral_score\\texclusion_evalue\\texclusion_kingdom" > ${prefix}_classified.tsv
    echo -e "contig_1\\tviral\\tgenomad_high\\t0.95\\t999\\tunknown" >> ${prefix}_classified.tsv
    """
}
