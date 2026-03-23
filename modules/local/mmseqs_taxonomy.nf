// @TASK T4.1 - Sequence search + taxonomy using MMseqs2 easy-search
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

process MMSEQS_TAXONOMY {
    tag "$meta.id"
    label 'process_high'
    label 'process_mmseqs'

    input:
    tuple val(meta), path(viral_contigs)

    output:
    tuple val(meta), path("*_taxonomy.tsv"), emit: taxonomy

    script:
    def prefix = meta.id
    def db_path = params.db_dir ? "${params.db_dir}/viral_nucleotide/refseq_viral_db" : "viral_refseq"
    """
    mmseqs easy-search \\
        ${viral_contigs} \\
        ${db_path} \\
        ${prefix}_search_raw.tsv \\
        tmp \\
        --search-type 3 \\
        --threads ${task.cpus} \\
        -e 1e-5

    # Convert to taxonomy format: best hit per query
    if [ -s ${prefix}_search_raw.tsv ]; then
        sort -k1,1 -k11,11g ${prefix}_search_raw.tsv | \\
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
    echo -e "contig_1\\tNC_001422.1\\t95.5\\t1e-50\\t500" >> ${prefix}_taxonomy.tsv
    """
}
