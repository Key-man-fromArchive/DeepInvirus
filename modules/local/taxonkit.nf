// @TASK T4.1 - Lineage extraction from MMseqs2 search results
// Uses RefSeq target headers which contain species information

process TAXONKIT_REFORMAT {
    tag "$meta.id"
    label 'process_taxonkit'

    input:
    tuple val(meta), path(taxonomy)

    output:
    tuple val(meta), path("*_lineage.tsv"), emit: lineage

    script:
    def prefix = meta.id
    """
    # The taxonomy TSV from MMseqs2 easy-search has columns:
    # query, target, pident, evalue, bitscore
    # Target names from RefSeq contain accession like NC_001422.1
    # We pass through the search results as-is for downstream merge_results.py
    # which handles taxonomy assignment from RefSeq headers

    cp ${taxonomy} ${prefix}_lineage.tsv
    """

    stub:
    def prefix = meta.id
    """
    echo -e "query\\ttarget\\tpident\\tevalue\\tbitscore" > ${prefix}_lineage.tsv
    echo -e "contig_1\\tNC_001422.1 Enterobacteria phage phiX174\\t95.5\\t1e-50\\t500" >> ${prefix}_lineage.tsv
    """
}
