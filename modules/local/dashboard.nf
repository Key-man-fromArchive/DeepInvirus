// @TASK T0.4 - Interactive HTML dashboard generation
// @TASK T5.1 - Updated: added --matrix / --pcoa arguments, aligned with generate_dashboard.py CLI
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// @SPEC docs/planning/05-design-system.md#2-대시보드-설계

process DASHBOARD {
    tag "dashboard"
    label 'process_low'
    label 'process_dashboard'

    input:
    path(bigtable)          // bigtable.tsv
    path(matrix)            // sample_taxon_matrix.tsv
    path(alpha_div)         // alpha_diversity.tsv
    path(beta_div)          // beta_diversity.tsv
    path(pcoa_coords)       // pcoa_coordinates.tsv

    output:
    path("dashboard.html"), emit: html

    script:
    """
    generate_dashboard.py \\
        --bigtable ${bigtable} \\
        --matrix   ${matrix} \\
        --alpha    ${alpha_div} \\
        --beta     ${beta_div} \\
        --pcoa     ${pcoa_coords} \\
        --output   dashboard.html
    """

    stub:
    """
    echo "<!doctype html><html><body><h1>DeepInvirus Dashboard (stub)</h1></body></html>" > dashboard.html
    """
}
