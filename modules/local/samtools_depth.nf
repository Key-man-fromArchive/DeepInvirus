// @TASK T8.8 - Per-base and binned contig depth profiles
// @SPEC docs/planning/13-deepinvirus-hybrid-v1.md#81-new-processes

process SAMTOOLS_DEPTH {
    tag "$meta.id"
    label 'process_samtools'
    publishDir "${params.outdir}/coverage/depth", mode: 'copy'

    input:
    tuple val(meta), path(bam), path(contigs)

    output:
    tuple val(meta), path("*.depth.tsv"), emit: depth

    script:
    def prefix = meta.id
    """
    samtools depth -aa ${bam} | \\
        awk 'BEGIN{OFS="\\t"; print "contig","window_start","window_end","mean_depth"} \\
             {bin=int((\$2-1)/100); key=\$1 FS bin; sum[key]+=\$3; count[key]++} \\
             END{for (k in sum) {split(k,a,FS); start=(a[2]*100)+1; end=start+99; print a[1], start, end, sum[k]/count[k]}}' | \\
        sort -k1,1 -k2,2n > ${prefix}.depth.tsv
    """

    stub:
    def prefix = meta.id
    """
    echo -e "contig\\twindow_start\\twindow_end\\tmean_depth" > ${prefix}.depth.tsv
    echo -e "contig_1\\t1\\t100\\t12.0" >> ${prefix}.depth.tsv
    """
}
