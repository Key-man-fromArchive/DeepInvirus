// De novo assembly using metaSPAdes (per-sample, legacy)

process METASPADES {
    tag "$meta.id"
    label 'process_metaspades'
    publishDir "${params.outdir}/assembly", mode: 'copy'

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

// Co-assembly: pool all samples' reads into a single metaSPAdes run
process METASPADES_COASSEMBLY {
    tag "coassembly"
    label 'process_metaspades'
    publishDir "${params.outdir}/assembly", mode: 'copy'

    input:
    path(r1_files)  // collected R1 files from all samples
    path(r2_files)  // collected R2 files from all samples

    output:
    path("coassembly.contigs.fa"),         emit: contigs
    path("coassembly.assembly_stats.tsv"), emit: stats

    script:
    """
    # Concatenate all R1 and R2 files for co-assembly
    cat ${r1_files} > pooled_R1.fastq.gz
    cat ${r2_files} > pooled_R2.fastq.gz

    metaspades.py \\
        -1 pooled_R1.fastq.gz \\
        -2 pooled_R2.fastq.gz \\
        -o spades_out \\
        -t ${task.cpus} \\
        -m \$(echo ${task.memory} | sed 's/ GB//')

    cp spades_out/contigs.fasta coassembly.contigs.fa

    parse_assembly_stats.py \\
        coassembly.contigs.fa \\
        --assembler metaspades \\
        --output coassembly.assembly_stats.tsv

    rm -f pooled_R1.fastq.gz pooled_R2.fastq.gz
    """

    stub:
    """
    echo ">contig_1" > coassembly.contigs.fa
    echo "ATCGATCG" >> coassembly.contigs.fa
    printf "sample\\tassembler\\tnum_contigs\\ttotal_length\\tlargest_contig\\tn50\\tgc_content\\n" > coassembly.assembly_stats.tsv
    printf "coassembly\\tmetaspades\\t1\\t8\\t8\\t8\\t0.5\\n" >> coassembly.assembly_stats.tsv
    """
}
