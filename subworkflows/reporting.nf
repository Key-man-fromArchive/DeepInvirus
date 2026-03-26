// @TASK T5 - Reporting subworkflow
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// Reporting subworkflow: DASHBOARD + REPORT + MULTIQC

include { DASHBOARD } from '../modules/local/dashboard'
include { REPORT    } from '../modules/local/report'
include { MULTIQC   } from '../modules/local/multiqc'

workflow REPORTING {

    take:
    ch_bigtable          // path(bigtable.tsv)
    ch_counts            // path(sample_counts.tsv)  -- sample_taxon_matrix
    ch_alpha_div         // path(alpha_diversity.tsv)
    ch_beta_div          // path(beta_diversity.tsv)
    ch_pcoa_coords       // path(pcoa_coordinates.tsv)
    ch_contigs           // path(coassembly.contigs.fa)
    ch_qc_stats          // path(qc_stats.tsv) -- aggregated QC statistics
    ch_assembly_stats    // path(assembly_stats.tsv)
    ch_coverage_files    // path(coverage_tsv[]) -- per-sample coverage TSVs
    ch_host_stats_files  // path(host_stats[]) -- host removal stats
    ch_fastp_json        // tuple val(meta), path(json) - for MultiQC
    ch_fastqc_raw        // tuple val(meta), path(zip) - raw FastQC for MultiQC
    ch_fastqc_trimmed    // tuple val(meta), path(zip) - trimmed FastQC for MultiQC
    ch_depth_files       // path(depth.tsv.gz[]) -- per-sample per-base depth

    main:
    // Step 1: Interactive HTML dashboard
    // Requires: bigtable, sample matrix, alpha/beta diversity, PCoA coords
    // Step 2: Automated Word report with figures (runs FIRST to produce figures)
    REPORT(
        ch_bigtable,
        ch_counts,
        ch_alpha_div,
        ch_pcoa_coords,
        ch_qc_stats,
        ch_assembly_stats,
        ch_coverage_files,
        ch_host_stats_files
    )

    // Step 1: Interactive HTML dashboard (runs AFTER report to get figures)
    // Pass the figures/ directory directly -- flatten/filter cannot enumerate
    // files inside a directory path in Nextflow.
    DASHBOARD(
        ch_bigtable,
        ch_counts,
        ch_alpha_div,
        ch_beta_div,
        ch_pcoa_coords,
        ch_contigs,
        ch_coverage_files,
        ch_host_stats_files,
        REPORT.out.figures,
        ch_depth_files
    )

    // Step 3: MultiQC aggregate QC report
    // Raw + trimmed FastQC are separated into subdirectories to avoid filename collision
    ch_fastp_files = ch_fastp_json.map{ meta, f -> f }.collect().ifEmpty( [] )
    ch_raw_fastqc = ch_fastqc_raw.map{ meta, f -> f }.collect().ifEmpty( [] )
    ch_trimmed_fastqc = ch_fastqc_trimmed.map{ meta, f -> f }.collect().ifEmpty( [] )
    MULTIQC( ch_fastp_files, ch_raw_fastqc, ch_trimmed_fastqc )

    emit:
    dashboard_html = DASHBOARD.out.html      // path(dashboard.html)
    report_docx    = REPORT.out.docx         // path(report.docx)
    figures        = REPORT.out.figures       // path(figures/)
    multiqc_html   = MULTIQC.out.html        // path(multiqc_report.html)
}
