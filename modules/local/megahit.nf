// De novo assembly using MEGAHIT (per-sample, legacy)

process MEGAHIT {
    tag "$meta.id"
    label 'process_megahit'
    publishDir "${params.outdir}/assembly", mode: 'copy'

    input:
    tuple val(meta), path(reads)

    output:
    tuple val(meta), path("*.contigs.fa"),         emit: contigs
    tuple val(meta), path("*.assembly_stats.tsv"), emit: stats

    script:
    def prefix = meta.id
    """
    megahit \\
        -1 ${reads[0]} \\
        -2 ${reads[1]} \\
        -o megahit_out \\
        -t ${task.cpus} \\
        --presets meta-large \\
        --min-contig-len ${params.min_contig_len ?: 500}

    cp megahit_out/final.contigs.fa ${prefix}.contigs.fa

    parse_assembly_stats.py \\
        ${prefix}.contigs.fa \\
        --assembler megahit \\
        --output ${prefix}.assembly_stats.tsv
    """

    stub:
    def prefix = meta.id
    """
    echo ">contig_1" > ${prefix}.contigs.fa
    echo "ATCGATCG" >> ${prefix}.contigs.fa
    printf "sample\\tassembler\\tnum_contigs\\ttotal_length\\tlargest_contig\\tn50\\tgc_content\\n" > ${prefix}.assembly_stats.tsv
    printf "${prefix}\\tmegahit\\t1\\t8\\t8\\t8\\t0.5\\n" >> ${prefix}.assembly_stats.tsv
    """
}

// Co-assembly: pool all samples' reads into a single MEGAHIT run
process MEGAHIT_COASSEMBLY {
    tag "coassembly"
    label 'process_megahit'
    publishDir "${params.outdir}/assembly", mode: 'copy'

    input:
    path(r1_files)  // collected R1 files from all samples
    path(r2_files)  // collected R2 files from all samples

    output:
    path("coassembly.contigs.fa"),         emit: contigs
    path("coassembly.assembly_stats.tsv"), emit: stats

    script:
    def r1_list = (r1_files instanceof List ? r1_files : [r1_files]).join(',')
    def r2_list = (r2_files instanceof List ? r2_files : [r2_files]).join(',')
    """
    megahit \\
        -1 ${r1_list} \\
        -2 ${r2_list} \\
        -o megahit_out \\
        -t ${task.cpus} \\
        --presets meta-large \\
        --min-contig-len ${params.min_contig_len ?: 500}

    cp megahit_out/final.contigs.fa coassembly.contigs.fa

    parse_assembly_stats.py \\
        coassembly.contigs.fa \\
        --assembler megahit \\
        --output coassembly.assembly_stats.tsv
    """

    stub:
    """
    echo ">contig_1" > coassembly.contigs.fa
    echo "ATCGATCG" >> coassembly.contigs.fa
    printf "sample\\tassembler\\tnum_contigs\\ttotal_length\\tlargest_contig\\tn50\\tgc_content\\n" > coassembly.assembly_stats.tsv
    printf "coassembly\\tmegahit\\t1\\t8\\t8\\t8\\t0.5\\n" >> coassembly.assembly_stats.tsv
    """
}
