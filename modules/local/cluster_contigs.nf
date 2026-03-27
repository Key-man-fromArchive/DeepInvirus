// Post-assembly contig clustering/deduplication using MMseqs2
// Removes redundant short fragments that belong to the same viral genome

process CLUSTER_CONTIGS {
    tag "$meta.id"
    label 'process_mmseqs'
    publishDir "${params.outdir}/assembly", mode: 'copy'

    input:
    tuple val(meta), path(contigs)

    output:
    tuple val(meta), path("*_clustered.fa"), emit: clustered_contigs
    tuple val(meta), path("*_cluster.tsv"),  emit: cluster_map

    script:
    def prefix = meta.id ?: "coassembly"
    """
    # Cluster contigs at 95% identity, 98% coverage (strict dedup only)
    mmseqs easy-cluster \\
        ${contigs} \\
        ${prefix}_clust \\
        tmp \\
        --min-seq-id 0.95 \\
        -c 0.98 \\
        --cov-mode 1 \\
        --cluster-mode 2 \\
        --cluster-reassign \\
        --threads ${task.cpus}

    # Representative sequences = clustered contigs
    mv ${prefix}_clust_rep_seq.fasta ${prefix}_clustered.fa

    # Cluster membership map (representative -> member)
    mv ${prefix}_clust_cluster.tsv ${prefix}_cluster.tsv

    # Stats
    BEFORE=\$(grep -c "^>" ${contigs})
    AFTER=\$(grep -c "^>" ${prefix}_clustered.fa)
    echo "Clustering: \${BEFORE} -> \${AFTER} contigs (removed \$((BEFORE - AFTER)) redundant)" >&2

    rm -rf tmp
    """

    stub:
    def prefix = meta.id ?: "coassembly"
    """
    cp ${contigs} ${prefix}_clustered.fa
    echo -e "contig_1\\tcontig_1" > ${prefix}_cluster.tsv
    """
}
