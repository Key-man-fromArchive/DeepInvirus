// @TASK T3.3 - Detection subworkflow: GENOMAD + DIAMOND -> MERGE_DETECTION
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

include { GENOMAD_DETECT  } from '../modules/local/genomad'
include { DIAMOND_BLASTX  } from '../modules/local/diamond'
include { MERGE_DETECTION } from '../modules/local/merge_detection'

workflow DETECTION {

    take:
    ch_contigs   // tuple val(meta), path(contigs)

    main:
    // Step 1: Parallel virus detection
    // geNomad (ML-based) - skippable via params.skip_ml
    if ( !params.skip_ml ) {
        GENOMAD_DETECT( ch_contigs )
    }

    // Diamond blastx (homology-based) - always runs
    DIAMOND_BLASTX( ch_contigs )

    // Step 2: Merge detection results
    if ( !params.skip_ml ) {
        // Both geNomad and Diamond available:
        // join raw outputs by sample meta, then pass to MERGE_DETECTION
        // which internally calls parse_genomad.py, parse_diamond.py, merge_detection.py
        ch_merge_input = GENOMAD_DETECT.out.summary
            .join( DIAMOND_BLASTX.out.hits )
        MERGE_DETECTION( ch_merge_input )
        ch_detected_seqs = MERGE_DETECTION.out.merged_detection
    } else {
        // When ML is skipped, use Diamond results directly
        // Diamond hits are passed through as detected sequences
        ch_detected_seqs = DIAMOND_BLASTX.out.hits
    }

    emit:
    detected_seqs = ch_detected_seqs   // tuple val(meta), path(merged_detection_tsv)
    diamond_hits  = DIAMOND_BLASTX.out.hits
}
