// Merge all results into bigtable

process MERGE_RESULTS {
    tag "merge_results"
    label 'process_merge'
    publishDir "${params.outdir}/taxonomy", mode: 'copy'

    input:
    path(taxonomies)
    path(lineages)
    path(coverages)
    path(detection_results)
    path(sample_map)
    path(ictv_vmr)
    path(evidence_classified)
    path(taxonomy_db)

    output:
    path("bigtable.tsv"),              emit: bigtable
    path("sample_taxon_matrix.tsv"),   emit: matrix
    path("sample_counts.tsv"),         emit: counts

    script:
    def ev_arg = evidence_classified.name != 'NO_FILE' ? "--evidence-classified ${evidence_classified}" : ''
    // Resolve NCBI taxonomy files for Diamond taxid -> lineage (dual-taxid taxonomy)
    def nodes_file = taxonomy_db.isDirectory() ? "${taxonomy_db}/nodes.dmp" : ''
    def names_file = taxonomy_db.isDirectory() ? "${taxonomy_db}/names.dmp" : ''
    def tax_args = ''
    if (nodes_file && names_file) {
        tax_args = "--taxonomy-nodes ${nodes_file} --taxonomy-names ${names_file}"
    }
    """
    merge_results.py \\
        --taxonomy ${taxonomies} \\
        --lineage ${lineages} \\
        --coverage ${coverages} \\
        --detection ${detection_results} \\
        --sample-map ${sample_map} \\
        --ictv ${ictv_vmr} \\
        ${ev_arg} \\
        ${tax_args} \\
        --out-bigtable bigtable.tsv \\
        --out-matrix sample_taxon_matrix.tsv \\
        --out-counts sample_counts.tsv
    """

    stub:
    """
    echo -e "seq_id\\tsample\\tseq_type\\tlength\\tdetection_method\\tdetection_score\\ttaxid\\tdomain\\tphylum\\tclass\\torder\\tfamily\\tgenus\\tspecies\\tictv_classification\\tbaltimore_group\\tcount\\trpm\\tcoverage" > bigtable.tsv
    echo -e "viral_contig_001\\tsample1\\tcontig\\t2847\\tboth\\t0.95\\t10239\\tVirus\\tNegarnaviricota\\tPolyploviricetes\\tMononegavirales\\tFiloviridae\\tEbolavirus\\tZaire ebolavirus\\tFiloviridae; Ebolavirus\\tGroup V\\t245\\t1230.5\\t18.7" >> bigtable.tsv
    echo -e "taxon\\ttaxid\\trank\\tsample1" > sample_taxon_matrix.tsv
    echo -e "Ebolavirus\\t40566\\tgenus\\t1230.5" >> sample_taxon_matrix.tsv
    echo -e "sample\\ttaxon\\tcount" > sample_counts.tsv
    echo -e "sample1\\tEbolavirus\\t245" >> sample_counts.tsv
    """
}
