// @TASK T1.2 - Host read removal using minimap2 + samtools
// @SPEC docs/planning/02-trd.md#2.2-분석-도구
// @SPEC docs/planning/07-coding-convention.md#4.1-Process-템플릿

/*
 * HOST_INDEX: Build minimap2 index from host genome FASTA.
 *
 * Runs once per host genome. The .mmi index is reused by all samples.
 * minimap2 -d builds a pre-built index that speeds up subsequent alignments.
 */
process HOST_INDEX {
    tag "${host_genome.baseName}"
    label 'process_medium'
    label 'process_host_removal'

    input:
    path(host_genome)

    output:
    path("*.mmi"), emit: index

    script:
    def prefix = host_genome.baseName
    """
    minimap2 \\
        -d ${prefix}.mmi \\
        ${host_genome}
    """

    stub:
    def prefix = host_genome.baseName
    """
    touch ${prefix}.mmi
    """
}

/*
 * HOST_REMOVAL: Remove host reads using minimap2 alignment + samtools filtering.
 *
 * Pipeline:
 *   1. minimap2 -ax sr: align paired-end reads to host index
 *   2. samtools flagstat: generate alignment statistics (before filtering)
 *   3. samtools view -b -f 4 -F 256: keep only unmapped reads, exclude secondary
 *   4. samtools sort -n: sort by read name (required for fastq extraction)
 *   5. samtools fastq: extract paired-end FASTQ from unmapped reads
 *   6. parse_host_removal.py: parse flagstat into structured TSV
 *
 * Outputs:
 *   - {prefix}_R1.filtered.fastq.gz, {prefix}_R2.filtered.fastq.gz
 *   - {prefix}.host_removal_stats.txt (TSV with removal statistics)
 */
process HOST_REMOVAL {
    tag "$meta.id"
    label 'process_high'
    label 'process_host_removal'

    input:
    tuple val(meta), path(reads)
    path(index)

    output:
    tuple val(meta), path("*_R{1,2}.filtered.fastq.gz"), emit: reads
    tuple val(meta), path("*.host_removal_stats.txt"),    emit: stats

    script:
    def prefix = meta.id
    """
    # Step 1: Align reads to host genome and generate BAM
    minimap2 \\
        -t ${task.cpus} \\
        -ax sr \\
        ${index} \\
        ${reads[0]} ${reads[1]} \\
    | samtools view -b -h -o ${prefix}.host_aligned.bam -

    # Step 2: Generate alignment statistics (before filtering)
    samtools flagstat ${prefix}.host_aligned.bam > ${prefix}.flagstat.txt

    # Step 3-5: Filter unmapped reads and extract paired-end FASTQ
    samtools view -b -f 4 -F 256 ${prefix}.host_aligned.bam \\
    | samtools sort -n -@ ${task.cpus} - \\
    | samtools fastq \\
        -1 ${prefix}_R1.filtered.fastq.gz \\
        -2 ${prefix}_R2.filtered.fastq.gz \\
        -0 /dev/null \\
        -s /dev/null \\
        -

    # Step 6: Parse flagstat into structured TSV
    parse_host_removal.py \\
        --sample ${prefix} \\
        --flagstat ${prefix}.flagstat.txt \\
        --output ${prefix}.host_removal_stats.txt

    # Cleanup intermediate BAM
    rm -f ${prefix}.host_aligned.bam
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}_R1.filtered.fastq.gz
    touch ${prefix}_R2.filtered.fastq.gz
    cat <<-EOF > ${prefix}.host_removal_stats.txt
    sample\ttotal_reads\tmapped_reads\tunmapped_reads\thost_removal_rate
    ${prefix}\t0\t0\t0\t0.00
    EOF
    """
}
