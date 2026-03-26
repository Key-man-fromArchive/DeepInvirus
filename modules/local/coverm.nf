// Read coverage calculation using CoverM (per-sample, legacy - reads+contigs joined)

process COVERM {
    tag "$meta.id"
    label 'process_coverm'
    publishDir "${params.outdir}/coverage", mode: 'copy'

    input:
    tuple val(meta), path(reads), path(contigs)

    output:
    tuple val(meta), path("*_coverage.tsv"), emit: coverage

    script:
    def prefix = meta.id
    """
    # Map reads to contigs and calculate coverage metrics
    coverm contig \\
        -1 ${reads[0]} \\
        -2 ${reads[1]} \\
        -r ${contigs} \\
        -o ${prefix}_coverage.tsv \\
        -t ${task.cpus} \\
        -m mean trimmed_mean covered_bases length
    """

    stub:
    def prefix = meta.id
    """
    echo -e "Contig\\tMean\\tTrimmed Mean\\tCovered Bases\\tLength" > ${prefix}_coverage.tsv
    echo -e "contig_1\\t10.5\\t9.8\\t4500\\t5000" >> ${prefix}_coverage.tsv
    """
}

// Per-sample read mapping to co-assembly contigs
process COVERM_PERSAMPLE {
    tag "$meta.id"
    label 'process_coverm'
    publishDir "${params.outdir}/coverage", mode: 'copy'

    input:
    tuple val(meta), path(reads)
    path(contigs)  // co-assembly contigs (shared reference)

    output:
    tuple val(meta), path("*_coverage.tsv"), emit: coverage
    tuple val(meta), path("*_depth.tsv.gz"), emit: depth

    script:
    def prefix = meta.id
    """
    # Map per-sample reads to co-assembly contigs and calculate coverage
    mkdir -p bam_cache
    coverm contig \\
        -1 ${reads[0]} \\
        -2 ${reads[1]} \\
        -r ${contigs} \\
        -o ${prefix}_coverage.tsv \\
        -t ${task.cpus} \\
        -m mean trimmed_mean covered_bases length \\
        --bam-file-cache-directory bam_cache

    # Extract per-base depth from the cached BAM
    BAM=\$(ls bam_cache/*.bam 2>/dev/null | head -1)
    if [ -n "\$BAM" ]; then
        samtools depth -a "\$BAM" | gzip > ${prefix}_depth.tsv.gz
    else
        # Fallback: map with minimap2 and extract depth
        minimap2 -a -x sr -t ${task.cpus} ${contigs} ${reads[0]} ${reads[1]} | \\
            samtools sort -@ 4 -o ${prefix}.sorted.bam
        samtools index ${prefix}.sorted.bam
        samtools depth -a ${prefix}.sorted.bam | gzip > ${prefix}_depth.tsv.gz
        rm -f ${prefix}.sorted.bam ${prefix}.sorted.bam.bai
    fi
    rm -rf bam_cache
    """

    stub:
    def prefix = meta.id
    """
    echo -e "Contig\\tMean\\tTrimmed Mean\\tCovered Bases\\tLength" > ${prefix}_coverage.tsv
    echo -e "contig_1\\t10.5\\t9.8\\t4500\\t5000" >> ${prefix}_coverage.tsv
    echo -e "contig_1\\t1\\t5" | gzip > ${prefix}_depth.tsv.gz
    """
}
