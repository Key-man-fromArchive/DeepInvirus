// @TASK T4 - Classification subworkflow
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// Classification subworkflow: MMSEQS -> TAXONKIT -> COVERM_PERSAMPLE -> MERGE_RESULTS -> DIVERSITY
// MMseqs2 and TaxonKit run once on co-assembly contigs
// CoverM runs per-sample (each sample's reads mapped to co-assembly contigs)

include { MMSEQS_TAXONOMY   } from '../modules/local/mmseqs_taxonomy'
include { TAXONKIT_REFORMAT } from '../modules/local/taxonkit'
include { COVERM_PERSAMPLE  } from '../modules/local/coverm'
include { MERGE_RESULTS     } from '../modules/local/merge_results'
include { DIVERSITY         } from '../modules/local/diversity'

workflow CLASSIFICATION {

    take:
    ch_contigs         // path(contigs.fa) - co-assembly (single file, no meta)
    ch_filtered_reads  // tuple val(meta), path(reads) - per-sample
    ch_detection       // tuple val(meta), path(detection_results) - meta.id='coassembly'
    ch_sample_map      // path(sample_map.tsv)
    ch_ictv_vmr        // path(ictv_vmr.tsv)
    ch_mmseqs_db       // path(mmseqs_db) - MMseqs2 viral nucleotide DB directory

    main:
    // Step 1: Wrap co-assembly contigs with meta for module compatibility
    ch_contigs_meta = ch_contigs.map { contigs ->
        [ [id: 'coassembly'], contigs ]
    }

    // Step 2: Taxonomic assignment with MMseqs2 (runs once on co-assembly)
    MMSEQS_TAXONOMY( ch_contigs_meta, ch_mmseqs_db )

    // Step 3: Lineage reformatting with TaxonKit (runs once)
    TAXONKIT_REFORMAT( MMSEQS_TAXONOMY.out.taxonomy )

    // Step 4: Per-sample read coverage (each sample's reads -> co-assembly contigs)
    COVERM_PERSAMPLE( ch_filtered_reads, ch_contigs.collect() )

    // Step 5: Merge all results into bigtable + sample_taxon_matrix + sample_counts
    MERGE_RESULTS(
        MMSEQS_TAXONOMY.out.taxonomy.map{ meta, f -> f }.collect(),
        TAXONKIT_REFORMAT.out.lineage.map{ meta, f -> f }.collect(),
        COVERM_PERSAMPLE.out.coverage.map{ meta, f -> f }.collect(),
        ch_detection.map{ meta, f -> f }.collect(),
        ch_sample_map,
        ch_ictv_vmr
    )

    // Step 6: Diversity analysis from sample_taxon_matrix
    DIVERSITY( MERGE_RESULTS.out.matrix )

    emit:
    bigtable      = MERGE_RESULTS.out.bigtable      // path(bigtable.tsv)
    sample_matrix = MERGE_RESULTS.out.matrix         // path(sample_taxon_matrix.tsv)
    counts        = MERGE_RESULTS.out.counts         // path(sample_counts.tsv)
    alpha_div     = DIVERSITY.out.alpha              // path(alpha_diversity.tsv)
    beta_div      = DIVERSITY.out.beta               // path(beta_diversity.tsv)
    pcoa          = DIVERSITY.out.pcoa               // path(pcoa_coordinates.tsv)
    taxonomy      = MMSEQS_TAXONOMY.out.taxonomy     // tuple val(meta), path(taxonomy) - coassembly
    lineage       = TAXONKIT_REFORMAT.out.lineage    // tuple val(meta), path(lineage) - coassembly
    coverage      = COVERM_PERSAMPLE.out.coverage    // tuple val(meta), path(coverage) - per-sample
}
