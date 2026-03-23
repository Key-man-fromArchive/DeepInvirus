// @TASK T2.1 - De novo assembly using metaSPAdes
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

process METASPADES {
    tag "$meta.id"
    label 'process_high_memory'
    label 'process_metaspades'

    container 'deepinvirus/assembly:1.0.0'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("*.contigs.fa"),         emit: contigs
    tuple val(meta), path("*.assembly_stats.tsv"), emit: stats

    script:
    def prefix = meta.id
    """
    metaspades.py \\
        -1 ${reads[0]} \\
        -2 ${reads[1]} \\
        -o spades_out \\
        -t ${task.cpus} \\
        -m \$(echo ${task.memory} | sed 's/ GB//')

    cp spades_out/contigs.fasta ${prefix}.contigs.fa

    parse_assembly_stats.py \\
        ${prefix}.contigs.fa \\
        --assembler metaspades \\
        --output ${prefix}.assembly_stats.tsv
    """

    stub:
    def prefix = meta.id
    """
    echo ">contig_1" > ${prefix}.contigs.fa
    echo "ATCGATCG" >> ${prefix}.contigs.fa
    printf "sample\\tassembler\\tnum_contigs\\ttotal_length\\tlargest_contig\\tn50\\tgc_content\\n" > ${prefix}.assembly_stats.tsv
    printf "${prefix}\\tmetaspades\\t1\\t8\\t8\\t8\\t0.5\\n" >> ${prefix}.assembly_stats.tsv
    """
}
