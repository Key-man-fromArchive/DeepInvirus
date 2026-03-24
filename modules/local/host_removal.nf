// Host read removal using minimap2 + samtools

/*
 * HOST_INDEX: Build minimap2 index from one or more host genome FASTAs.
 *
 * Accepts multiple host genome FASTA files (collected via .collect()).
 * Concatenates them into a single combined FASTA and builds one minimap2
 * index for efficient multi-host read removal.
 *
 * When only a single host genome is provided, the cat+minimap2 pipeline
 * still works correctly (cat of one file = the file itself).
 */
process HOST_INDEX {
    tag "host_index"
    label 'process_host_removal'

    input:
    path(host_genomes)

    output:
    path("combined_host.mmi"), emit: index

    script:
    """
    # Concatenate all host genomes into a single FASTA
    cat ${host_genomes} > combined_host.fa.gz

    # Build minimap2 index from the combined FASTA
    minimap2 \\
        -t ${task.cpus} \\
        -d combined_host.mmi \\
        combined_host.fa.gz

    # Cleanup intermediate combined FASTA
    rm -f combined_host.fa.gz
    """

    stub:
    """
    touch combined_host.mmi
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
    label 'process_host_removal'
    publishDir "${params.outdir}/qc", mode: 'copy', pattern: "*.host_removal_stats.txt"

    input:
    tuple val(meta), path(reads)
    path(index)

    output:
    tuple val(meta), path("*_R{1,2}.filtered.fastq.gz"), emit: reads
    tuple val(meta), path("*.host_removal_stats.txt"),    emit: stats

    script:
    def prefix = meta.id
    """
    # Single-pipe: minimap2 → tee(flagstat) → filter unmapped → sort → fastq
    # No intermediate BAM file — pure streaming, ~3x faster
    minimap2 \\
        -t ${task.cpus} \\
        -ax sr \\
        ${index} \\
        ${reads[0]} ${reads[1]} \\
    | tee >(samtools flagstat - > ${prefix}.flagstat.txt) \\
    | samtools view -b -f 4 -F 256 - \\
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
