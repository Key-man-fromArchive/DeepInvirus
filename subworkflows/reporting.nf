// @TASK T5.3 - Reporting subworkflow: DASHBOARD + REPORT + MULTIQC
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// @SPEC docs/planning/02-trd.md#3.3-출력

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
    ch_qc_stats          // path(qc_stats.tsv) -- aggregated QC statistics
    ch_assembly_stats    // path(assembly_stats.tsv)
    ch_fastp_json        // tuple val(meta), path(json) - for MultiQC

    main:
    // Step 1: Interactive HTML dashboard
    // Requires: bigtable, sample matrix, alpha/beta diversity, PCoA coords
    DASHBOARD(
        ch_bigtable,
        ch_counts,
        ch_alpha_div,
        ch_beta_div,
        ch_pcoa_coords
    )

    // Step 2: Automated Word report with figures
    // Requires: bigtable, sample matrix, alpha diversity, PCoA, QC stats, assembly stats
    REPORT(
        ch_bigtable,
        ch_counts,
        ch_alpha_div,
        ch_pcoa_coords,
        ch_qc_stats,
        ch_assembly_stats
    )

    // Step 3: MultiQC aggregate QC report from fastp JSONs
    ch_multiqc_files = ch_fastp_json.map{ meta, f -> f }.collect()
    MULTIQC( ch_multiqc_files )

    emit:
    dashboard_html = DASHBOARD.out.html      // path(dashboard.html)
    report_docx    = REPORT.out.docx         // path(report.docx)
    figures        = REPORT.out.figures       // path(figures/)
    multiqc_html   = MULTIQC.out.html        // path(multiqc_report.html)
}
