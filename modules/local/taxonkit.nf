// @TASK T4.1 - Hierarchical lineage reformatting using TaxonKit
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계

process TAXONKIT_REFORMAT {
    tag "$meta.id"
    label 'process_low'
    label 'process_taxonkit'

    input:
    tuple val(meta), path(taxonomy)

    output:
    tuple val(meta), path("*_lineage.tsv"), emit: lineage

    script:
    def prefix = meta.id
    def taxdb = params.db_dir ? "${params.db_dir}/taxonomy/taxonkit_data" : "\${TAXONKIT_DB:-/dev/null}"
    """
    # Extract taxids (column 2), skip header, resolve lineage + 7-rank reformat
    echo -e "taxid\\tlineage\\tdomain\\tphylum\\tclass\\torder\\tfamily\\tgenus\\tspecies" \\
        > ${prefix}_lineage.tsv

    cut -f2 ${taxonomy} | tail -n +2 | \\
        taxonkit lineage --data-dir ${taxdb} | \\
        taxonkit reformat --data-dir ${taxdb} \\
            -I 1 \\
            -f "{k}\\t{p}\\t{c}\\t{o}\\t{f}\\t{g}\\t{s}" \\
        >> ${prefix}_lineage.tsv
    """

    stub:
    def prefix = meta.id
    """
    echo -e "taxid\\tlineage\\tdomain\\tphylum\\tclass\\torder\\tfamily\\tgenus\\tspecies" > ${prefix}_lineage.tsv
    echo -e "12345\\tViruses;Uroviricota\\tViruses\\tUroviricota\\tCaudoviricetes\\tCaudovirales\\tMyoviridae\\tTevenvirinae\\tTest virus" >> ${prefix}_lineage.tsv
    """
}
