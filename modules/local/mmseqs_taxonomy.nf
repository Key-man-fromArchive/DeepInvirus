// @TASK T4.1 - MMseqs2 taxonomy assignment
// @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
// Sequence search using MMseqs2 easy-search (not easy-taxonomy — avoids missing taxonomy DB files)

process MMSEQS_TAXONOMY {
    tag "$meta.id"
    label 'process_mmseqs'
    publishDir "${params.outdir}/taxonomy", mode: 'copy'

    input:
    tuple val(meta), path(viral_contigs)
    path mmseqs_db

    output:
    tuple val(meta), path("*_taxonomy.tsv"), emit: taxonomy

    script:
    def prefix = meta.id
    def db_path = "${mmseqs_db}/genbank_viral_db"
    """
    mmseqs easy-search \\
        ${viral_contigs} \\
        ${db_path} \\
        ${prefix}_search_out.tsv \\
        tmp \\
        --search-type 3 \\
        --threads ${task.cpus} \\
        -e 1e-5 \\
        --format-output query,target,pident,alnlen,mismatch,gapopen,qstart,qend,tstart,tend,evalue,bits,taxid,taxname,taxlineage

    # Convert to taxonomy format: best hit per query
    # Columns: 1=query 2=target 3=pident 11=evalue 12=bits 13=taxid 14=taxname 15=taxlineage
    if [ -s ${prefix}_search_out.tsv ]; then
        sort -k1,1 -k11,11g ${prefix}_search_out.tsv | \\
            awk -F'\\t' '!seen[\$1]++' | \\
            awk -F'\\t' 'BEGIN{OFS="\\t"; print "query","target","pident","evalue","bitscore","taxid","taxname","taxlineage"} {print \$1,\$2,\$3,\$11,\$12,\$13,\$14,\$15}' \\
            > ${prefix}_taxonomy.tsv
    else
        echo -e "query\\ttarget\\tpident\\tevalue\\tbitscore\\ttaxid\\ttaxname\\ttaxlineage" > ${prefix}_taxonomy.tsv
    fi

    rm -rf tmp
    """

    stub:
    def prefix = meta.id
    """
    echo -e "query\\ttarget\\tpident\\tevalue\\tbitscore\\ttaxid\\ttaxname\\ttaxlineage" > ${prefix}_taxonomy.tsv
    echo -e "contig_1\\tNC_001405.1\\t95.0\\t1e-50\\t800\\t129951\\tHuman adenovirus C\\tViruses;Preplasmiviricota;Tectiliviricetes;Rowavirales;Adenoviridae;Mastadenovirus;Human mastadenovirus C" >> ${prefix}_taxonomy.tsv
    """
}
