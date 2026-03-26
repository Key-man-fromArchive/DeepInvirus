// Lineage reformat from MMseqs2 taxonomy results using TaxonKit
// Uses taxid from MMseqs2 easy-taxonomy and reformats to full lineage

process TAXONKIT_REFORMAT {
    tag "$meta.id"
    label 'process_taxonkit'
    publishDir "${params.outdir}/taxonomy", mode: 'copy'

    input:
    tuple val(meta), path(taxonomy)

    output:
    tuple val(meta), path("*_lineage.tsv"), emit: lineage

    script:
    def prefix = meta.id
    """
    # Extract taxids from MMseqs2 taxonomy output and reformat with TaxonKit
    # Output format: taxid, lineage, domain{k}, phylum{p}, class{c}, order{o}, family{f}, genus{g}, species{s}
    if command -v taxonkit &>/dev/null && [ -d "\${TAXONKIT_DB:-/dev/null}" ]; then
        # Use TaxonKit to reformat taxids into full lineage
        cut -f2 ${taxonomy} | tail -n+2 | \\
            taxonkit reformat -I 1 -f '{k};{p};{c};{o};{f};{g};{s}' | \\
            paste <(tail -n+2 ${taxonomy} | cut -f1) - > ${prefix}_lineage_raw.tsv

        echo -e "seq_id\\ttaxid\\tlineage\\tdomain\\tphylum\\tclass\\torder\\tfamily\\tgenus\\tspecies" > ${prefix}_lineage.tsv
        awk -F'\\t' 'BEGIN{OFS="\\t"} {split(\$3,a,";"); print \$1,\$2,\$3,a[1],a[2],a[3],a[4],a[5],a[6],a[7]}' \\
            ${prefix}_lineage_raw.tsv >> ${prefix}_lineage.tsv
    else
        # Fallback: pass through taxonomy as-is for downstream merge_results.py
        cp ${taxonomy} ${prefix}_lineage.tsv
    fi
    """

    stub:
    def prefix = meta.id
    """
    echo -e "seq_id\\ttaxid\\tlineage\\tdomain\\tphylum\\tclass\\torder\\tfamily\\tgenus\\tspecies" > ${prefix}_lineage.tsv
    echo -e "contig_1\\t10239\\tViruses;Nucleocytoviricota;Megaviricetes;Imitervirales;Poxviridae;Orthopoxvirus;Vaccinia virus\\tViruses\\tNucleocytoviricota\\tMegaviricetes\\tImitervirales\\tPoxviridae\\tOrthopoxvirus\\tVaccinia virus" >> ${prefix}_lineage.tsv
    """
}
