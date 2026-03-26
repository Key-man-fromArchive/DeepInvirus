// @TASK T4.1 - MMseqs2 taxonomy assignment
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// Sequence search using MMseqs2 easy-search (not easy-taxonomy — avoids missing taxonomy DB files)

process MMSEQS_TAXONOMY {
    tag "$meta.id"
    label 'process_mmseqs'
    publishDir "${params.outdir}/taxonomy", mode: 'copy'

    input:
    tuple val(meta), path(viral_contigs)
    path mmseqs_db

    output:
    tuple val(meta), path("*_taxonomy.tsv"), emit: taxonomy

    script:
    def prefix = meta.id
    def db_path = "${mmseqs_db}/refseq_viral_db"
    """
    mmseqs easy-search \\
        ${viral_contigs} \\
        ${db_path} \\
        ${prefix}_search_out.tsv \\
        tmp \\
        --search-type 3 \\
        --threads ${task.cpus} \\
        -e 1e-5

    # Convert to taxonomy format: best hit per query
    if [ -s ${prefix}_search_out.tsv ]; then
        sort -k1,1 -k11,11g ${prefix}_search_out.tsv | \\
            awk -F'\\t' '!seen[\$1]++' | \\
            awk -F'\\t' 'BEGIN{OFS="\\t"; print "query","target","pident","evalue","bitscore"} {print \$1,\$2,\$3,\$11,\$12}' \\
            > ${prefix}_taxonomy.tsv
    else
        echo -e "query\\ttarget\\tpident\\tevalue\\tbitscore" > ${prefix}_taxonomy.tsv
    fi

    rm -rf tmp
    """

    stub:
    def prefix = meta.id
    """
    echo -e "query\\ttarget\\tpident\\tevalue\\tbitscore" > ${prefix}_taxonomy.tsv
    echo -e "contig_1\\tNC_001405.1\\t95.0\\t1e-50\\t800" >> ${prefix}_taxonomy.tsv
    """
}
