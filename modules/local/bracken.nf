// @TASK T1.3 - Bracken species-level abundance estimation
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#Section-B-independent-profiling
// Re-estimates species-level abundance from Kraken2 report using Bayesian redistribution.
// Bracken requires a pre-built Kraken2 database with k-mer length distributions.

process BRACKEN {
    tag "$meta.id"
    label 'process_low'
    publishDir "${params.outdir}/kraken2/bracken", mode: 'copy'

    input:
    tuple val(meta), path(kraken2_report)
    path(kraken2_db)

    output:
    tuple val(meta), path("*.bracken"),  emit: bracken
    tuple val(meta), path("*.breport"),  emit: breport

    script:
    def prefix = meta.id
    def read_len = params.bracken_read_len ?: 150
    def level    = params.bracken_level    ?: 'S'
    def threshold = params.bracken_threshold ?: 0
    """
    bracken \\
        -d ${kraken2_db} \\
        -i ${kraken2_report} \\
        -o ${prefix}.bracken \\
        -w ${prefix}.breport \\
        -r ${read_len} \\
        -l ${level} \\
        -t ${threshold}
    """

    stub:
    def prefix = meta.id
    """
    cat <<'EOF' > ${prefix}.bracken
name	taxonomy_id	taxonomy_lvl	kraken_assigned_reads	added_reads	new_est_reads	fraction_total_reads
Escherichia coli	562	S	1000	500	1500	0.50
Staphylococcus aureus	1280	S	800	200	1000	0.33
Klebsiella pneumoniae	573	S	300	200	500	0.17
EOF
    cat <<'EOF' > ${prefix}.breport
100.00	3000	0	R	1	root
60.00	1800	0	D	2	  Bacteria
30.00	900	0	P	1224	    Pseudomonadota
20.00	600	0	C	1236	      Gammaproteobacteria
15.00	450	0	O	91347	        Enterobacterales
10.00	300	0	F	543	          Enterobacteriaceae
5.00	150	0	G	561	            Escherichia
5.00	150	150	S	562	              Escherichia coli
EOF
    """
}
