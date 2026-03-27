// Protein homology search using Diamond blastx
// @TASK T3.2 - Diamond blastx protein homology search
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

process DIAMOND_BLASTX {
    tag "$meta.id"
    label 'process_diamond'
    publishDir "${params.outdir}/detection/diamond", mode: 'copy'

    input:
    tuple val(meta), path(contigs)
    path(db)

    output:
    tuple val(meta), path("*.diamond.tsv"), emit: hits

    script:
    def prefix = meta.id
    """
    diamond blastx \\
        --query ${contigs} \\
        --db ${db} \\
        --out ${prefix}.diamond.tsv \\
        --outfmt 6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore staxids \\
        --threads ${task.cpus} \\
        --evalue 1e-5 \\
        --max-target-seqs 5 \\
        --very-sensitive
    """

    stub:
    def prefix = meta.id
    """
    echo -e "contig_1\\tUniRef90_P12345\\t95.0\\t500\\t25\\t0\\t1\\t1500\\t1\\t500\\t1e-50\\t800\\t12345" > ${prefix}.diamond.tsv
    """
}
