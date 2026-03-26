// @TASK T8.5 - Tier 3 NT viral-first nucleotide search
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#81-new-processes

process BLASTN_TIER3_NT {
    tag "$meta.id"
    label 'process_blastn'
    publishDir "${params.outdir}/classification/tier3_nt", mode: 'copy'

    input:
    tuple val(meta), path(contigs)
    val(viral_nt_db)

    output:
    tuple val(meta), path("*.tier3_nt.tsv"), emit: hits

    script:
    def prefix = meta.id
    """
    blastn \\
        -query ${contigs} \\
        -db ${viral_nt_db} \\
        -out ${prefix}.tier3_nt.tsv \\
        -outfmt '6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore staxids' \\
        -num_threads ${task.cpus} \\
        -evalue 1e-10 \\
        -max_target_seqs 5
    """

    stub:
    def prefix = meta.id
    """
    echo -e "contig_1\\tviral_nt_1\\t91.5\\t900\\t12\\t0\\t1\\t900\\t10\\t909\\t1e-70\\t400\\t10239" > ${prefix}.tier3_nt.tsv
    """
}
