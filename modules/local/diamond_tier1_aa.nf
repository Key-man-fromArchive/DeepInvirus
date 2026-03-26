// @TASK T8.3 - Tier 1 AA viral-first homology search
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#81-new-processes

process DIAMOND_TIER1_AA {
    tag "$meta.id"
    label 'process_diamond'
    publishDir "${params.outdir}/classification/tier1_aa", mode: 'copy'

    input:
    tuple val(meta), path(contigs)
    path(viral_protein_db)

    output:
    tuple val(meta), path("*.tier1_aa.tsv"), emit: hits

    script:
    def prefix = meta.id
    """
    diamond blastx \\
        --query ${contigs} \\
        --db ${viral_protein_db} \\
        --out ${prefix}.tier1_aa.tsv \\
        --outfmt 6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore \\
        --threads ${task.cpus} \\
        --evalue 1e-5 \\
        --max-target-seqs 5 \\
        --ultra-sensitive
    """

    stub:
    def prefix = meta.id
    """
    echo -e "contig_1\\tviral_prot_1\\t82.0\\t280\\t10\\t0\\t1\\t840\\t1\\t280\\t1e-40\\t350\\t10239" > ${prefix}.tier1_aa.tsv
    """
}
