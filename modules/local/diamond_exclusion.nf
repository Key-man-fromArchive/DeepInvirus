// @TASK T3.5 - Diamond exclusion search against SwissProt
// @SPEC docs/planning/12-pipeline-v2-multidb-filtering.md
// Multi-kingdom DIAMOND blastx for non-viral false-positive exclusion.
// Searches contigs against a broad DB (e.g. SwissProt all organisms)
// to determine whether the best hit is viral or non-viral.

process DIAMOND_EXCLUSION {
    tag "$meta.id"
    label 'process_diamond'
    publishDir "${params.outdir}/detection/exclusion", mode: 'copy'

    input:
    tuple val(meta), path(contigs)
    path(exclusion_db)

    output:
    tuple val(meta), path("*.exclusion.tsv"), emit: hits

    script:
    def prefix = meta.id
    """
    diamond blastx \\
        --query ${contigs} \\
        --db ${exclusion_db} \\
        --out ${prefix}.exclusion.tsv \\
        --outfmt 6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore staxids \\
        --threads ${task.cpus} \\
        --evalue 1e-3 \\
        --max-target-seqs 1 \\
        --sensitive
    """

    stub:
    def prefix = meta.id
    """
    echo -e "contig_1\\tsp|P12345|PROT_ECOLI\\t85.0\\t300\\t45\\t0\\t1\\t900\\t1\\t300\\t1e-30\\t500\\t562" > ${prefix}.exclusion.tsv
    """
}
