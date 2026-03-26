// @TASK T8.4 - Tier 2 AA all-kingdom verification
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#81-new-processes

process DIAMOND_TIER2_AA {
    tag "$meta.id"
    label 'process_diamond'
    publishDir "${params.outdir}/classification/tier2_aa", mode: 'copy'

    input:
    tuple val(meta), path(contigs)
    path(uniref50_db)

    output:
    tuple val(meta), path("*.tier2_aa.tsv"), emit: hits

    script:
    def prefix = meta.id
    """
    diamond blastx \\
        --query ${contigs} \\
        --db ${uniref50_db} \\
        --out ${prefix}.tier2_aa.tsv \\
        --outfmt 6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore staxids \\
        --threads ${task.cpus} \\
        --evalue 1e-3 \\
        --max-target-seqs 1 \\
        --sensitive
    """

    stub:
    def prefix = meta.id
    """
    echo -e "contig_1\\tUniRef50_Q12345\\t61.0\\t240\\t20\\t1\\t10\\t729\\t5\\t244\\t1e-12\\t180\\t2" > ${prefix}.tier2_aa.tsv
    """
}
