// @TASK T8.6 - Tier 4 NT polymicrobial verification
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#81-new-processes

process BLASTN_TIER4_NT {
    tag "$meta.id"
    label 'process_blastn'
    publishDir "${params.outdir}/classification/tier4_nt", mode: 'copy'

    input:
    tuple val(meta), path(contigs)
    val(polymicrobial_nt_db)

    output:
    tuple val(meta), path("*.tier4_nt.tsv"), emit: hits

    script:
    def prefix = meta.id
    """
    blastn \\
        -query ${contigs} \\
        -db ${polymicrobial_nt_db} \\
        -out ${prefix}.tier4_nt.tsv \\
        -outfmt '6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore staxids' \\
        -num_threads ${task.cpus} \\
        -evalue 1e-10 \\
        -max_target_seqs 5
    """

    stub:
    def prefix = meta.id
    """
    echo -e "contig_1\\tcellular_nt_1\\t88.0\\t750\\t18\\t1\\t5\\t754\\t20\\t769\\t1e-20\\t150\\t2" > ${prefix}.tier4_nt.tsv
    """
}
