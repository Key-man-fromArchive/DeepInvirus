// @TASK T8.7 - 4-tier evidence integration
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#25-stage-5-evidence-integration

process EVIDENCE_INTEGRATION {
    tag "$meta.id"
    label 'process_merge'
    publishDir "${params.outdir}/classification/integration", mode: 'copy'

    input:
    tuple val(meta), path(contigs)
    path(tier1_aa)
    path(tier2_aa)
    path(tier3_nt)
    path(tier4_nt)
    path(genomad_summary)
    path(taxonomy_nodes)

    output:
    tuple val(meta), path("*_classified.tsv"), emit: classified

    script:
    def prefix = meta.id
    """
    evidence_integration.py \\
        --contigs ${contigs} \\
        --tier1-aa ${tier1_aa} \\
        --tier2-aa ${tier2_aa} \\
        --tier3-nt ${tier3_nt} \\
        --tier4-nt ${tier4_nt} \\
        --genomad ${genomad_summary} \\
        --taxonomy-nodes ${taxonomy_nodes} \\
        --output ${prefix}_classified.tsv
    """

    stub:
    def prefix = meta.id
    """
    cat <<'EOF' > ${prefix}_classified.tsv
seq_id	length	genomad_virus_score	genomad_plasmid_score	genomad_provirus	aa1_hit	aa1_pident	aa1_evalue	aa1_bitscore	aa1_alnlen	aa1_taxid	aa1_taxonomy	aa2_hit	aa2_pident	aa2_evalue	aa2_bitscore	aa2_alnlen	aa2_taxid	aa2_kingdom	nt1_hit	nt1_pident	nt1_evalue	nt1_bitscore	nt1_alnlen	nt1_taxid	nt1_taxonomy	nt2_hit	nt2_pident	nt2_evalue	nt2_bitscore	nt2_alnlen	nt2_taxid	nt2_kingdom	classification	best_support_tier	classification_score	evidence_chain
contig_1	5000	0.95	0.01	False	viral_prot_1	82.0	1e-40	350.0	280	10239	Viruses	.	.	.	.	.	.	unknown	.	.	.	.	.	.	.	.	.	.	.	.	.	unknown	strong_viral	aa1	0.95	geNomad=0.95; AA1=viral_prot_1; AA2=no_hit; NT1=no_hit; NT2=no_hit; final=strong_viral
EOF
    """
}
