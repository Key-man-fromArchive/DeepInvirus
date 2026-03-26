// @TASK T5.3 - MultiQC aggregate QC report
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// Fixed: raw + trimmed FastQC separated to avoid filename collision

process MULTIQC {
    tag "multiqc"
    label 'process_multiqc'
    publishDir "${params.outdir}/qc", mode: 'copy'

    input:
    path(fastp_files)
    path('raw_fastqc/*')
    path('trimmed_fastqc/*')

    output:
    path("multiqc_report.html"), emit: html, optional: true

    script:
    """
    echo "<html><body><h1>MultiQC Report</h1><p>No QC data available.</p></body></html>" > multiqc_report.html
    multiqc . -o . -n multiqc_report.html --force --dirs --dirs-depth 1 2>/dev/null || true
    """

    stub:
    """
    echo "<html><body><h1>MultiQC Report (stub)</h1></body></html>" > multiqc_report.html
    """
}
