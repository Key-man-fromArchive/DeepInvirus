// @TASK T4.1 + T4.2 + T4.3 - Classification subworkflow
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// @SPEC docs/planning/04-database-design.md#4-핵심-출력-테이블-스키마
//
// Pipeline: MMSEQS -> TAXONKIT -> COVERM -> MERGE_RESULTS -> DIVERSITY

include { MMSEQS_TAXONOMY   } from '../modules/local/mmseqs_taxonomy'
include { TAXONKIT_REFORMAT } from '../modules/local/taxonkit'
include { COVERM            } from '../modules/local/coverm'
include { MERGE_RESULTS     } from '../modules/local/merge_results'
include { DIVERSITY         } from '../modules/local/diversity'

workflow CLASSIFICATION {

    take:
    ch_viral_contigs   // tuple val(meta), path(viral_contigs)
    ch_filtered_reads  // tuple val(meta), path(reads)
    ch_contigs         // tuple val(meta), path(contigs)
    ch_detection       // tuple val(meta), path(detection_results)
    ch_sample_map      // path(sample_map.tsv)
    ch_ictv_vmr        // path(ictv_vmr.tsv)

    main:
    // Step 1: Taxonomic assignment with MMseqs2 (--lca-mode 2)
    MMSEQS_TAXONOMY( ch_viral_contigs )

    // Step 2: Lineage reformatting with TaxonKit (7-rank)
    TAXONKIT_REFORMAT( MMSEQS_TAXONOMY.out.taxonomy )

    // Step 3: Read coverage calculation with CoverM
    ch_coverm_input = ch_filtered_reads.join( ch_contigs )
    COVERM( ch_coverm_input )

    // Step 4: Merge all results into bigtable + sample_taxon_matrix + sample_counts
    MERGE_RESULTS(
        MMSEQS_TAXONOMY.out.taxonomy.map{ meta, f -> f }.collect(),
        TAXONKIT_REFORMAT.out.lineage.map{ meta, f -> f }.collect(),
        COVERM.out.coverage.map{ meta, f -> f }.collect(),
        ch_detection.map{ meta, f -> f }.collect(),
        ch_sample_map,
        ch_ictv_vmr
    )

    // Step 5: Diversity analysis from sample_taxon_matrix
    DIVERSITY( MERGE_RESULTS.out.matrix )

    emit:
    bigtable      = MERGE_RESULTS.out.bigtable      // path(bigtable.tsv)
    sample_matrix = MERGE_RESULTS.out.matrix         // path(sample_taxon_matrix.tsv)
    counts        = MERGE_RESULTS.out.counts         // path(sample_counts.tsv)
    alpha_div     = DIVERSITY.out.alpha              // path(alpha_diversity.tsv)
    beta_div      = DIVERSITY.out.beta               // path(beta_diversity.tsv)
    pcoa          = DIVERSITY.out.pcoa               // path(pcoa_coordinates.tsv)
    taxonomy      = MMSEQS_TAXONOMY.out.taxonomy     // tuple val(meta), path(taxonomy)
    lineage       = TAXONKIT_REFORMAT.out.lineage    // tuple val(meta), path(lineage)
    coverage      = COVERM.out.coverage              // tuple val(meta), path(coverage)
}
