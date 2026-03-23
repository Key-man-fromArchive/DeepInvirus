// @TASK T0.4 - MultiQC aggregate QC report
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

process MULTIQC {
    tag "multiqc"
    label 'process_low'
    label 'process_multiqc'

    input:
    path(multiqc_files)

    output:
    path("multiqc_report.html"), emit: html

    script:
    """
    multiqc . \\
        -o . \\
        -n multiqc_report.html \\
        --force
    """

    stub:
    """
    echo "<html><body><h1>MultiQC Report (stub)</h1></body></html>" > multiqc_report.html
    """
}
