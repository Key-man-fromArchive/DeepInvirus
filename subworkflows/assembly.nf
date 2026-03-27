// @TASK T2 - Assembly subworkflow
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// Assembly subworkflow: Co-assembly mode
// Pools all samples' reads and runs a single assembly (MEGAHIT or metaSPAdes)

include { MEGAHIT_COASSEMBLY    } from '../modules/local/megahit'
include { METASPADES_COASSEMBLY } from '../modules/local/metaspades'
include { CLUSTER_CONTIGS       } from '../modules/local/cluster_contigs'

workflow ASSEMBLY {

    take:
    ch_reads   // tuple val(meta), path(reads) - per-sample filtered reads

    main:
    // Collect all R1 and R2 files from every sample for co-assembly
    ch_r1 = ch_reads.map { meta, reads -> reads[0] }.collect()
    ch_r2 = ch_reads.map { meta, reads -> reads[1] }.collect()

    ch_raw_contigs = Channel.empty()
    ch_stats       = Channel.empty()

    if ( params.assembler == 'megahit' ) {
        MEGAHIT_COASSEMBLY( ch_r1, ch_r2 )
        ch_raw_contigs = MEGAHIT_COASSEMBLY.out.contigs
        ch_stats       = MEGAHIT_COASSEMBLY.out.stats
    } else if ( params.assembler == 'metaspades' ) {
        METASPADES_COASSEMBLY( ch_r1, ch_r2 )
        ch_raw_contigs = METASPADES_COASSEMBLY.out.contigs
        ch_stats       = METASPADES_COASSEMBLY.out.stats
    }

    // Post-assembly clustering: remove redundant fragments (95% identity, 80% coverage)
    ch_contigs_meta = ch_raw_contigs.map { contigs -> [ [id: 'coassembly'], contigs ] }
    CLUSTER_CONTIGS( ch_contigs_meta )
    ch_contigs = CLUSTER_CONTIGS.out.clustered_contigs.map { meta, contigs -> contigs }

    emit:
    contigs = ch_contigs   // path(coassembly_clustered.fa) - deduplicated contigs
    stats   = ch_stats     // path(coassembly.assembly_stats.tsv)
}
