// MultiQC aggregate QC report

process MULTIQC {
    tag "multiqc"
    label 'process_multiqc'
    publishDir "${params.outdir}/qc", mode: 'copy'

    input:
    path(multiqc_files)

    output:
    path("multiqc_report.html"), emit: html, optional: true

    script:
    """
    echo "<html><body><h1>MultiQC Report</h1><p>No QC data available.</p></body></html>" > multiqc_report.html
    multiqc . -o . -n multiqc_report.html --force 2>/dev/null || true
    """

    stub:
    """
    echo "<html><body><h1>MultiQC Report (stub)</h1></body></html>" > multiqc_report.html
    """
}
