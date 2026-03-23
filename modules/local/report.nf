// @TASK T5.2 - Automated Word report generation
// @SPEC docs/planning/05-design-system.md#5-word-보고서-템플릿
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

process REPORT {
    tag "report"
    label 'process_low'
    label 'process_report'

    input:
    path(bigtable)
    path(matrix)
    path(alpha_div)
    path(pcoa_coords)
    path(qc_stats)
    path(assembly_stats)

    output:
    path("report.docx")  , emit: docx
    path("figures/")      , emit: figures

    script:
    """
    generate_report.py \\
        --bigtable ${bigtable} \\
        --matrix ${matrix} \\
        --alpha ${alpha_div} \\
        --pcoa ${pcoa_coords} \\
        --qc-stats ${qc_stats} \\
        --assembly-stats ${assembly_stats} \\
        --output report.docx \\
        --figures-dir figures/
    """

    stub:
    """
    touch report.docx
    mkdir -p figures
    touch figures/placeholder.png
    """
}
