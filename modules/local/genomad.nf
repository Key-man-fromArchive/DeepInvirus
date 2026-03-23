// @TASK T3.1 - ML-based virus detection using geNomad
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

process GENOMAD_DETECT {
    tag "$meta.id"
    label 'process_high'
    label 'process_genomad'

    input:
    tuple val(meta), path(contigs)
    path(db)

    output:
    tuple val(meta), path("*_virus_summary.tsv"), emit: summary
    tuple val(meta), path("*_virus.fna"),          emit: fasta

    script:
    def prefix = meta.id
    """
    genomad end-to-end \\
        ${contigs} \\
        genomad_out \\
        ${db} \\
        --threads ${task.cpus} \\
        --cleanup

    cp genomad_out/*_summary/*_virus_summary.tsv ${prefix}_virus_summary.tsv
    cp genomad_out/*_summary/*_virus.fna ${prefix}_virus.fna || touch ${prefix}_virus.fna
    """

    stub:
    def prefix = meta.id
    """
    echo -e "seq_name\\tlength\\ttopology\\tcoordinates\\tn_genes\\tgenetic_code\\tvirus_score\\ttaxonomy\\tn_hallmarks" > ${prefix}_virus_summary.tsv
    echo -e "contig_1\\t5000\\tlinear\\t1-5000\\t5\\t11\\t0.95\\tViruses;Caudoviricetes\\t3" >> ${prefix}_virus_summary.tsv
    echo ">contig_1" > ${prefix}_virus.fna
    echo "ATCGATCG" >> ${prefix}_virus.fna
    """
}
