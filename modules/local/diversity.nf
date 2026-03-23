// @TASK T4.3 - Alpha/beta diversity analysis
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// @SPEC docs/planning/04-database-design.md#4.3-alpha_diversity
// @SPEC docs/planning/04-database-design.md#4.4-beta_diversity

process DIVERSITY {
    tag "diversity"
    label 'process_low'
    label 'process_diversity'

    input:
    path(sample_taxon_matrix)

    output:
    path("alpha_diversity.tsv"),   emit: alpha
    path("beta_diversity.tsv"),    emit: beta
    path("pcoa_coordinates.tsv"),  emit: pcoa

    script:
    """
    calc_diversity.py \\
        --matrix ${sample_taxon_matrix} \\
        --out-alpha alpha_diversity.tsv \\
        --out-beta beta_diversity.tsv \\
        --out-pcoa pcoa_coordinates.tsv
    """

    stub:
    """
    echo -e "sample\\tobserved_species\\tshannon\\tsimpson\\tchao1\\tpielou_evenness" > alpha_diversity.tsv
    echo -e "sample1\\t2\\t0.693\\t0.5\\t2.0\\t1.0" >> alpha_diversity.tsv
    echo -e "\\tsample1" > beta_diversity.tsv
    echo -e "sample1\\t0.0" >> beta_diversity.tsv
    echo -e "sample\\tPC1\\tPC2" > pcoa_coordinates.tsv
    echo -e "sample1\\t0.0\\t0.0" >> pcoa_coordinates.tsv
    """
}
