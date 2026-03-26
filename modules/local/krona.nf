// @TASK T1.3 - Krona interactive HTML visualization from Kraken2 report
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#Section-B-independent-profiling
// Converts Kraken2 report to Krona-compatible text format and generates interactive HTML.
// Uses kreport2krona.py (KrakenTools) for format conversion, ktImportText for HTML generation.

process KRONA {
    tag "$meta.id"
    label 'process_low'
    publishDir "${params.outdir}/kraken2/krona", mode: 'copy'

    input:
    tuple val(meta), path(kraken2_report)

    output:
    tuple val(meta), path("*.krona.html"), emit: html

    script:
    def prefix = meta.id
    """
    kreport2krona.py -r ${kraken2_report} -o ${prefix}.krona.txt
    ktImportText ${prefix}.krona.txt -o ${prefix}.krona.html
    """

    stub:
    def prefix = meta.id
    """
    echo '<html><head><title>Krona - ${prefix}</title></head><body><h1>Krona stub for ${prefix}</h1></body></html>' > ${prefix}.krona.html
    """
}
