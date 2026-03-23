// @TASK T1.3 - Preprocessing subworkflow: FASTP -> HOST_INDEX -> HOST_REMOVAL
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

include { FASTP        } from '../modules/local/fastp'
include { HOST_INDEX   } from '../modules/local/host_removal'
include { HOST_REMOVAL } from '../modules/local/host_removal'

workflow PREPROCESSING {

    take:
    ch_reads        // tuple val(meta), path(reads)
    ch_host_genome  // path(host_genome_fasta) or Channel.empty() when host='none'

    main:
    // Step 1: QC + adapter trimming
    FASTP( ch_reads )

    ch_trimmed_reads = FASTP.out.reads

    // Step 2: Host read removal (conditional on params.host != 'none')
    if ( params.host != 'none' ) {
        // Build minimap2 index from host genome FASTA
        HOST_INDEX( ch_host_genome )

        // Remove host reads using minimap2 alignment
        HOST_REMOVAL( ch_trimmed_reads, HOST_INDEX.out.index )

        ch_filtered_reads = HOST_REMOVAL.out.reads
        ch_host_stats     = HOST_REMOVAL.out.stats
    } else {
        // Skip host removal: pass trimmed reads directly through
        ch_filtered_reads = ch_trimmed_reads
        ch_host_stats     = Channel.empty()
    }

    emit:
    filtered_reads = ch_filtered_reads  // tuple val(meta), path(reads)
    fastp_json     = FASTP.out.json     // tuple val(meta), path(json)
    fastp_html     = FASTP.out.html     // tuple val(meta), path(html)
    host_stats     = ch_host_stats      // tuple val(meta), path(stats) or empty
}
