// Lineage reformat from MMseqs2 taxonomy results using TaxonKit
// Uses taxid from MMseqs2 easy-taxonomy and reformats to full lineage

process TAXONKIT_REFORMAT {
    tag "$meta.id"
    label 'process_taxonkit'
    publishDir "${params.outdir}/taxonomy", mode: 'copy'

    input:
    tuple val(meta), path(taxonomy)
    path(taxonomy_db)

    output:
    tuple val(meta), path("*_lineage.tsv"), emit: lineage

    script:
    def prefix = meta.id
    """
    # Set up TaxonKit DB from pipeline-provided taxonomy directory
    export TAXONKIT_DB=\$(pwd)/taxonkit_db
    mkdir -p \${TAXONKIT_DB}
    if [ -f "${taxonomy_db}/names.dmp" ]; then
        ln -sf \$(readlink -f ${taxonomy_db}/names.dmp) \${TAXONKIT_DB}/names.dmp
        ln -sf \$(readlink -f ${taxonomy_db}/nodes.dmp) \${TAXONKIT_DB}/nodes.dmp
        if [ -f "${taxonomy_db}/merged.dmp" ]; then
            ln -sf \$(readlink -f ${taxonomy_db}/merged.dmp) \${TAXONKIT_DB}/merged.dmp
        fi
        if [ -f "${taxonomy_db}/delnodes.dmp" ]; then
            ln -sf \$(readlink -f ${taxonomy_db}/delnodes.dmp) \${TAXONKIT_DB}/delnodes.dmp
        fi
    elif [ -f "${taxonomy_db}" ]; then
        # Single file (nodes.dmp) — set parent dir
        export TAXONKIT_DB=\$(dirname \$(readlink -f ${taxonomy_db}))
    fi

    # Extract taxids from MMseqs2 taxonomy output (column 6 = taxid) and reformat with TaxonKit
    # MMseqs2 output: query, target, pident, evalue, bitscore, taxid, taxname, taxlineage

    if command -v taxonkit &>/dev/null && [ -f "\${TAXONKIT_DB}/names.dmp" ]; then
        # Use TaxonKit for authoritative lineage from NCBI taxonomy
        # Column 6 = taxid (1-indexed)
        tail -n+2 ${taxonomy} | awk -F'\\t' '\$6 ~ /^[0-9]+\$/ && \$6 > 0 {print \$1"\\t"\$6}' > ${prefix}_query_taxid.tsv

        if [ -s ${prefix}_query_taxid.tsv ]; then
            cut -f2 ${prefix}_query_taxid.tsv | \\
                taxonkit reformat -I 1 -f '{K};{p};{c};{o};{f};{g};{s}' 2>/dev/null | \\
                paste <(cut -f1 ${prefix}_query_taxid.tsv) - > ${prefix}_lineage_raw.tsv

            echo -e "seq_id\\ttaxid\\tlineage\\tdomain\\tphylum\\tclass\\torder\\tfamily\\tgenus\\tspecies" > ${prefix}_lineage.tsv
            awk -F'\\t' 'BEGIN{OFS="\\t"} {split(\$3,a,";"); print \$1,\$2,\$3,a[1],a[2],a[3],a[4],a[5],a[6],a[7]}' \\
                ${prefix}_lineage_raw.tsv >> ${prefix}_lineage.tsv
        else
            echo -e "seq_id\\ttaxid\\tlineage\\tdomain\\tphylum\\tclass\\torder\\tfamily\\tgenus\\tspecies" > ${prefix}_lineage.tsv
            echo "WARNING: No valid taxids found in MMseqs2 output." >&2
        fi
    else
        echo -e "seq_id\\ttaxid\\tlineage\\tdomain\\tphylum\\tclass\\torder\\tfamily\\tgenus\\tspecies" > ${prefix}_lineage.tsv
        echo "WARNING: TaxonKit or taxonomy DB not available. Lineage file will be header-only." >&2
    fi
    """

    stub:
    def prefix = meta.id
    """
    echo -e "seq_id\\ttaxid\\tlineage\\tdomain\\tphylum\\tclass\\torder\\tfamily\\tgenus\\tspecies" > ${prefix}_lineage.tsv
    echo -e "contig_1\\t10239\\tViruses;Nucleocytoviricota;Megaviricetes;Imitervirales;Poxviridae;Orthopoxvirus;Vaccinia virus\\tViruses\\tNucleocytoviricota\\tMegaviricetes\\tImitervirales\\tPoxviridae\\tOrthopoxvirus\\tVaccinia virus" >> ${prefix}_lineage.tsv
    """
}
