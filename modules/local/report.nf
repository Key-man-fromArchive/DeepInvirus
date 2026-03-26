// Automated Word report generation

process REPORT {
    tag "report"
    label 'process_report'
    publishDir "${params.outdir}", mode: 'copy'

    input:
    path(bigtable)
    path(matrix)
    path(alpha_div)
    path(pcoa_coords)
    path(qc_stats)
    path(assembly_stats)
    path(coverage_files)
    path(host_stats_files)

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
        --coverage-dir . \\
        --host-stats-dir . \\
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
