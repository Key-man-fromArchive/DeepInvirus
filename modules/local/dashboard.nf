// Interactive HTML dashboard generation

process DASHBOARD {
    tag "dashboard"
    label 'process_dashboard'
    publishDir "${params.outdir}", mode: 'copy'

    input:
    path(bigtable)          // bigtable.tsv
    path(matrix)            // sample_taxon_matrix.tsv
    path(alpha_div)         // alpha_diversity.tsv
    path(beta_div)          // beta_diversity.tsv
    path(pcoa_coords)       // pcoa_coordinates.tsv
    path(contigs)           // co-assembly FASTA
    path(coverage_files)    // per-sample *_coverage.tsv files
    path(host_stats_files)  // per-sample *.host_removal_stats.txt files
    path(figures_dir)       // figures/ directory from REPORT (contains PNGs)
    path(depth_files)       // per-sample *_depth.tsv.gz files

    output:
    path("dashboard.html"), emit: html

    script:
    """
    mkdir -p figures_in depth_dir
    cp ${figures_dir}/*.png figures_in/ 2>/dev/null || true
    # Stage depth files into a directory for generate_dashboard.py
    for f in *_depth.tsv.gz; do
        [ -f "\$f" ] && cp "\$f" depth_dir/ 2>/dev/null || true
    done
    generate_dashboard.py \\
        --bigtable ${bigtable} \\
        --matrix   ${matrix} \\
        --alpha    ${alpha_div} \\
        --beta     ${beta_div} \\
        --pcoa     ${pcoa_coords} \\
        --contigs  ${contigs} \\
        --coverage-dir . \\
        --host-stats-dir . \\
        --figures-dir figures_in \\
        --depth-dir depth_dir \\
        --output   dashboard.html
    """

    stub:
    """
    echo "<!doctype html><html><body><h1>DeepInvirus Dashboard (stub)</h1></body></html>" > dashboard.html
    """
}
