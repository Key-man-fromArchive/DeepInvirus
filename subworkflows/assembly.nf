// @TASK T2 - Assembly subworkflow
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// Assembly subworkflow: Co-assembly mode
// Pools all samples' reads and runs a single assembly (MEGAHIT or metaSPAdes)

include { MEGAHIT_COASSEMBLY    } from '../modules/local/megahit'
include { METASPADES_COASSEMBLY } from '../modules/local/metaspades'

workflow ASSEMBLY {

    take:
    ch_reads   // tuple val(meta), path(reads) - per-sample filtered reads

    main:
    // Collect all R1 and R2 files from every sample for co-assembly
    ch_r1 = ch_reads.map { meta, reads -> reads[0] }.collect()
    ch_r2 = ch_reads.map { meta, reads -> reads[1] }.collect()

    ch_contigs = Channel.empty()
    ch_stats   = Channel.empty()

    if ( params.assembler == 'megahit' ) {
        MEGAHIT_COASSEMBLY( ch_r1, ch_r2 )
        ch_contigs = MEGAHIT_COASSEMBLY.out.contigs
        ch_stats   = MEGAHIT_COASSEMBLY.out.stats
    } else if ( params.assembler == 'metaspades' ) {
        METASPADES_COASSEMBLY( ch_r1, ch_r2 )
        ch_contigs = METASPADES_COASSEMBLY.out.contigs
        ch_stats   = METASPADES_COASSEMBLY.out.stats
    }

    emit:
    contigs = ch_contigs   // path(coassembly.contigs.fa) - single file, no meta
    stats   = ch_stats     // path(coassembly.assembly_stats.tsv) - single file, no meta
}
