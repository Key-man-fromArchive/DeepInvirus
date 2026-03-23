// @TASK T3.3 - Merge geNomad and Diamond detection results
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// @SPEC docs/planning/04-database-design.md#4.1-bigtable

process MERGE_DETECTION {
    tag "$meta.id"
    label 'process_low'
    label 'process_merge'

    input:
    tuple val(meta), path(genomad_parsed), path(diamond_parsed)

    output:
    tuple val(meta), path("*_merged_detection.tsv"), emit: merged_detection

    script:
    def prefix = meta.id
    """
    parse_genomad.py \\
        ${genomad_parsed} \\
        --output genomad_detection.tsv \\
        --min-score ${params.min_virus_score ?: 0.7}

    parse_diamond.py \\
        ${diamond_parsed} \\
        --output diamond_detection.tsv \\
        --min-bitscore ${params.min_bitscore ?: 50}

    merge_detection.py \\
        --genomad genomad_detection.tsv \\
        --diamond diamond_detection.tsv \\
        --output ${prefix}_merged_detection.tsv
    """

    stub:
    def prefix = meta.id
    """
    echo -e "seq_id\\tlength\\tdetection_method\\tdetection_score\\ttaxonomy\\ttaxid\\tsubject_id" > ${prefix}_merged_detection.tsv
    echo -e "contig_1\\t15000\\tboth\\t0.95\\tViruses;Caudoviricetes\\t12345\\tUniRef90_P12345" >> ${prefix}_merged_detection.tsv
    """
}
