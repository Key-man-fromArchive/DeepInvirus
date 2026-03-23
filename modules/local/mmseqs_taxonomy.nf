// @TASK T4.1 - Taxonomic assignment using MMseqs2
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
    mmseqs easy-taxonomy \\
        ${viral_contigs} \\
        ${db_path} \\
        ${prefix}_taxonomy \\
        tmp \\
        --lca-mode 2 \\
        --tax-lineage 1 \\
        --threads ${task.cpus}

    # Rename LCA result to standard name; create empty header if no results
    mv ${prefix}_taxonomy_lca.tsv ${prefix}_taxonomy.tsv || \\
        echo -e "query\\ttaxid\\trank\\tname" > ${prefix}_taxonomy.tsv
    """

    stub:
    def prefix = meta.id
    """
    echo -e "query\\ttaxid\\trank\\tname" > ${prefix}_taxonomy.tsv
    echo -e "contig_1\\t12345\\tspecies\\tTest virus" >> ${prefix}_taxonomy.tsv
    """
}
