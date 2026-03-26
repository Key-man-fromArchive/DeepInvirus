// @TASK T1 - Preprocessing subworkflow
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// Preprocessing subworkflow: (FASTP|BBDUK) -> FastQC -> HOST_INDEX -> HOST_REMOVAL

include { FASTP        } from '../modules/local/fastp'
include { BBDUK        } from '../modules/local/bbduk'
include { FASTQC as FASTQC_RAW     } from '../modules/local/fastqc'
include { FASTQC as FASTQC_TRIMMED } from '../modules/local/fastqc'
include { HOST_INDEX   } from '../modules/local/host_removal'
include { HOST_REMOVAL } from '../modules/local/host_removal'

workflow PREPROCESSING {

    take:
    ch_reads        // tuple val(meta), path(reads)
    ch_host_genome  // path(host_genome_fasta) or Channel.empty() when host='none'

    main:
    // Step 0: FastQC on raw reads (before trimming)
    FASTQC_RAW( ch_reads )

    // Step 1: QC + adapter trimming (trimmer selection via params.trimmer)
    if ( params.trimmer == 'bbduk' ) {
        BBDUK( ch_reads )
        ch_trimmed_reads = BBDUK.out.reads
        ch_trim_stats    = BBDUK.out.stats
    } else {
        FASTP( ch_reads )
        ch_trimmed_reads = FASTP.out.reads
        ch_trim_stats    = FASTP.out.json
    }

    // Step 1b: FastQC on trimmed reads (after trimming)
    FASTQC_TRIMMED( ch_trimmed_reads )

    // Step 2: Host read removal (conditional on params.host != 'none')
    if ( params.host != 'none' ) {
        // Collect all host genome FASTAs and build a single combined index
        HOST_INDEX( ch_host_genome.collect() )

        // Collect index so it can be reused for all samples
        ch_index = HOST_INDEX.out.index.collect()

        // Remove host reads using minimap2 alignment
        HOST_REMOVAL( ch_trimmed_reads, ch_index )

        ch_filtered_reads = HOST_REMOVAL.out.reads
        ch_host_stats     = HOST_REMOVAL.out.stats
    } else {
        // Skip host removal: pass trimmed reads directly through
        ch_filtered_reads = ch_trimmed_reads
        ch_host_stats     = Channel.empty()
    }

    emit:
    filtered_reads  = ch_filtered_reads  // tuple val(meta), path(reads)
    trim_stats      = ch_trim_stats      // tuple val(meta), path(stats) - fastp JSON or bbduk stats
    fastp_json      = params.trimmer == 'fastp' ? FASTP.out.json : Channel.empty()
    fastp_html      = params.trimmer == 'fastp' ? FASTP.out.html : Channel.empty()
    fastqc_raw      = FASTQC_RAW.out.zip       // tuple val(meta), path(zip) - raw FastQC
    fastqc_trimmed  = FASTQC_TRIMMED.out.zip   // tuple val(meta), path(zip) - trimmed FastQC
    host_stats      = ch_host_stats      // tuple val(meta), path(stats) or empty
}
