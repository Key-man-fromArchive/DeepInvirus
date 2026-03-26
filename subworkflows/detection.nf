// @TASK T3 - Detection subworkflow
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// @SPEC docs/planning/12-pipeline-v2-multidb-filtering.md
// Detection subworkflow: GENOMAD + DIAMOND -> MERGE_DETECTION -> (optional) CHECKV
//                        -> (optional) DIAMOND_EXCLUSION -> CLASSIFY_CONTIGS
// Runs once on co-assembly contigs (not per-sample)

include { GENOMAD_DETECT    } from '../modules/local/genomad'
include { DIAMOND_BLASTX    } from '../modules/local/diamond'
include { MERGE_DETECTION   } from '../modules/local/merge_detection'
include { CHECKV            } from '../modules/local/checkv'
include { DIAMOND_EXCLUSION } from '../modules/local/diamond_exclusion'
include { CLASSIFY_CONTIGS  } from '../modules/local/classify_contigs'

// @TASK A3 - skip_ml Diamond schema conversion to merged detection format
process PARSE_DIAMOND_ONLY {
    tag "$meta.id"
    label 'process_low'

    input:
    tuple val(meta), path(diamond_hits)

    output:
    tuple val(meta), path("*_merged_detection.tsv"), emit: detection

    script:
    def prefix = meta.id
    """
    parse_diamond.py \\
        --input ${diamond_hits} \\
        --output ${prefix}_merged_detection.tsv \\
        --merged-format
    """

    stub:
    def prefix = meta.id
    """
    echo -e "seq_id\\tlength\\tdetection_method\\tdetection_score\\ttaxonomy\\ttaxid\\tsubject_id" > ${prefix}_merged_detection.tsv
    echo -e "contig_1\\t5000\\tdiamond\\t0.90\\tViruses;Caudoviricetes\\t0\\tUniRef90_P12345" >> ${prefix}_merged_detection.tsv
    """
}

workflow DETECTION {

    take:
    ch_contigs       // path(contigs.fa) - co-assembly (single file, no meta)
    ch_genomad_db    // path: geNomad database directory
    ch_diamond_db    // path: Diamond database file
    ch_checkv_db     // path: CheckV database directory (Channel.empty() when not provided)
    ch_exclusion_db  // path: SwissProt/multi-kingdom Diamond DB (Channel.empty() when not provided)

    main:
    def nullMetaFile = Channel.value([ [id: 'coassembly'], file('/dev/null') ])

    // Wrap co-assembly contigs with a meta map for module compatibility
    ch_contigs_meta = ch_contigs.map { contigs ->
        [ [id: 'coassembly'], contigs ]
    }

    // Step 1: Virus detection on co-assembly contigs (runs once)
    // geNomad (ML-based) - skippable via params.skip_ml
    if ( !params.skip_ml ) {
        GENOMAD_DETECT( ch_contigs_meta, ch_genomad_db )
        ch_genomad_summary = GENOMAD_DETECT.out.summary
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
        // When ML is skipped, convert Diamond hits to merged detection format
        PARSE_DIAMOND_ONLY( DIAMOND_BLASTX.out.hits )
        ch_detected_seqs = PARSE_DIAMOND_ONLY.out.detection
        ch_genomad_summary = nullMetaFile
    }

    // Step 3: CheckV quality assessment (optional)
    // Only runs when params.checkv_db is provided.
    // Uses viral contig FASTA from geNomad if available.
    if ( params.checkv_db && !params.skip_ml ) {
        CHECKV( GENOMAD_DETECT.out.fasta, ch_checkv_db )
        ch_checkv_quality = CHECKV.out.quality
    } else {
        ch_checkv_quality = Channel.empty()
    }

    // Step 4: Multi-kingdom exclusion filtering (optional)
    // @TASK T3.5 - Diamond exclusion against SwissProt / multi-kingdom DB
    // @TASK T3.6 - Multi-DB contig classification
    // Only runs when params.exclusion_db is provided.
    // When skipped, ch_detected_seqs passes through unmodified.
    if ( params.exclusion_db ) {
        // 4a. DIAMOND_EXCLUSION: search contigs against multi-kingdom DB
        DIAMOND_EXCLUSION( ch_contigs_meta, ch_exclusion_db )

        // 4b. CLASSIFY_CONTIGS: combine exclusion + detection evidence
        def db_base = params.db_dir ?: 'databases'
        def nodes_file = file("${db_base}/taxonomy/nodes.dmp")
        ch_taxonomy_nodes = Channel.value(nodes_file)

        CLASSIFY_CONTIGS(
            DIAMOND_EXCLUSION.out.hits,
            ch_detected_seqs,
            ch_taxonomy_nodes
        )

        ch_classified = CLASSIFY_CONTIGS.out.classified
    } else {
        ch_classified = Channel.empty()
    }

    emit:
    detected_seqs   = ch_detected_seqs    // tuple val(meta), path(merged_detection_tsv) - meta.id='coassembly'
    diamond_hits    = DIAMOND_BLASTX.out.hits
    genomad_summary = ch_genomad_summary    // tuple val(meta), path(genomad_summary_tsv) - /dev/null when ML skipped
    checkv_quality  = ch_checkv_quality    // tuple val(meta), path(quality_summary.tsv) - empty when CheckV skipped
    classified      = ch_classified        // tuple val(meta), path(classified_contigs.tsv) - empty when exclusion skipped
}
