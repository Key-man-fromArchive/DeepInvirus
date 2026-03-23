// @TASK T2.2 - Assembly subworkflow: MEGAHIT or METASPADES based on params.assembler
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// @TEST tests/modules/test_assembly.py

include { MEGAHIT    } from '../modules/local/megahit'
include { METASPADES } from '../modules/local/metaspades'

workflow ASSEMBLY {

    take:
    ch_reads   // tuple val(meta), path(reads)

    main:
    ch_contigs = Channel.empty()
    ch_stats   = Channel.empty()

    if ( params.assembler == 'megahit' ) {
        MEGAHIT( ch_reads )
        ch_contigs = MEGAHIT.out.contigs
        ch_stats   = MEGAHIT.out.stats
    } else if ( params.assembler == 'metaspades' ) {
        METASPADES( ch_reads )
        ch_contigs = METASPADES.out.contigs
        ch_stats   = METASPADES.out.stats
    }

    emit:
    contigs = ch_contigs   // tuple val(meta), path(contigs)
    stats   = ch_stats     // tuple val(meta), path(assembly_stats.tsv)
}
