// Detection subworkflow: GENOMAD + DIAMOND -> MERGE_DETECTION
// Runs once on co-assembly contigs (not per-sample)

include { GENOMAD_DETECT  } from '../modules/local/genomad'
include { DIAMOND_BLASTX  } from '../modules/local/diamond'
include { MERGE_DETECTION } from '../modules/local/merge_detection'

workflow DETECTION {

    take:
    ch_contigs       // path(contigs.fa) - co-assembly (single file, no meta)
    ch_genomad_db    // path: geNomad database directory
    ch_diamond_db    // path: Diamond database file

    main:
    // Wrap co-assembly contigs with a meta map for module compatibility
    ch_contigs_meta = ch_contigs.map { contigs ->
        [ [id: 'coassembly'], contigs ]
    }

    // Step 1: Virus detection on co-assembly contigs (runs once)
    // geNomad (ML-based) - skippable via params.skip_ml
    if ( !params.skip_ml ) {
        GENOMAD_DETECT( ch_contigs_meta, ch_genomad_db )
    }

    // Diamond blastx (homology-based) - always runs
    DIAMOND_BLASTX( ch_contigs_meta, ch_diamond_db )

    // Step 2: Merge detection results
    if ( !params.skip_ml ) {
        ch_merge_input = GENOMAD_DETECT.out.summary
            .join( DIAMOND_BLASTX.out.hits )
        MERGE_DETECTION( ch_merge_input )
        ch_detected_seqs = MERGE_DETECTION.out.merged_detection
    } else {
        ch_detected_seqs = DIAMOND_BLASTX.out.hits
    }

    emit:
    detected_seqs = ch_detected_seqs   // tuple val(meta), path(merged_detection_tsv) - meta.id='coassembly'
    diamond_hits  = DIAMOND_BLASTX.out.hits
}
