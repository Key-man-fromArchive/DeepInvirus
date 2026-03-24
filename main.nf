#!/usr/bin/env nextflow

nextflow.enable.dsl = 2

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    DeepInvirus v0.3.0 - Viral Metagenomics Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Raw FASTQ -> QC -> Co-Assembly -> Virus Detection -> Classification -> Report
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

// -----------------------------------------------------------------------
// Include subworkflows
// -----------------------------------------------------------------------
include { PREPROCESSING  } from './subworkflows/preprocessing'
include { ASSEMBLY       } from './subworkflows/assembly'
include { DETECTION      } from './subworkflows/detection'
include { CLASSIFICATION } from './subworkflows/classification'
include { REPORTING      } from './subworkflows/reporting'

// -----------------------------------------------------------------------
// Pipeline parameters
// -----------------------------------------------------------------------
params.reads      = null          // FASTQ files or directory path
params.host       = 'human'      // Host genome(s): comma-separated nicknames or 'none'
params.outdir     = './results'   // Output directory
params.trimmer    = 'bbduk'      // bbduk or fastp
params.assembler  = 'megahit'    // megahit or metaspades
params.search     = 'sensitive'  // fast or sensitive
params.skip_ml    = false        // Skip ML-based virus detection
params.db_dir     = null         // Custom DB path (null = use default DB)
params.help       = false        // Show help message

// -----------------------------------------------------------------------
// Help message
// -----------------------------------------------------------------------
def helpMessage() {
    log.info """
    =========================================================
     DeepInvirus v0.3.0 - Viral Metagenomics Pipeline
    =========================================================

    Usage:
        nextflow run main.nf --reads <path> [options]

    Required:
        --reads       Path to FASTQ files or samplesheet CSV
                      (e.g., '/data/*_R{1,2}.fastq.gz')

    Optional:
        --host        Host genome(s) for read removal
                      Comma-separated nicknames: tmol,zmor,human
                      Use 'none' to skip host removal
                      [default: ${params.host}]

        --outdir      Output directory
                      [default: ${params.outdir}]

        --trimmer     Read trimming/QC tool to use
                      Options: bbduk, fastp
                      [default: ${params.trimmer}]

        --assembler   De novo assembler to use
                      Options: megahit, metaspades
                      [default: ${params.assembler}]

        --search      Diamond search sensitivity
                      Options: fast, sensitive
                      [default: ${params.search}]

        --skip_ml     Skip ML-based virus detection (geNomad)
                      [default: ${params.skip_ml}]

        --db_dir      Path to pre-built reference databases
                      [default: auto-download]

        --help        Show this help message

    Profiles:
        -profile docker        Run with Docker containers
        -profile singularity   Run with Singularity containers
        -profile test          Run with minimal test data

    Examples:
        nextflow run main.nf --reads '/data/*_R{1,2}.fastq.gz' -profile docker
        nextflow run main.nf --reads samplesheet.csv --assembler metaspades -profile singularity
        nextflow run main.nf -profile test,docker

    =========================================================
    """.stripIndent()
}

// Show help message and exit
if (params.help) {
    helpMessage()
    exit 0
}

// -----------------------------------------------------------------------
// Input validation
// -----------------------------------------------------------------------
if (!params.reads) {
    helpMessage()
    log.error "ERROR: --reads parameter is required."
    exit 1
}

if (!(params.trimmer in ['bbduk', 'fastp'])) {
    log.error "ERROR: --trimmer must be 'bbduk' or 'fastp'. Got: '${params.trimmer}'"
    exit 1
}

if (!(params.assembler in ['megahit', 'metaspades'])) {
    log.error "ERROR: --assembler must be 'megahit' or 'metaspades'. Got: '${params.assembler}'"
    exit 1
}

if (!(params.search in ['fast', 'sensitive'])) {
    log.error "ERROR: --search must be 'fast' or 'sensitive'. Got: '${params.search}'"
    exit 1
}

// Validate host genome directories
if (params.host != 'none') {
    def host_list = params.host.tokenize(',').collect { it.trim() }
    host_list.each { name ->
        def host_dir = "${params.db_dir ?: 'databases'}/host_genomes/${name}"
        log.info "Host genome: ${name} (${host_dir})"
    }
}

// -----------------------------------------------------------------------
// Log pipeline info
// -----------------------------------------------------------------------
if (params.use_ramdisk) {
    log.info "RAM disk enabled: work directory -> ${params.ramdisk_path}"
    log.info "  (pass -w ${params.ramdisk_path} via CLI runner for actual effect)"
}

log.info """
=========================================================
 DeepInvirus v0.3.0
=========================================================
 reads      : ${params.reads}
 host       : ${params.host}
 trimmer    : ${params.trimmer}
 assembler  : ${params.assembler}
 search     : ${params.search}
 skip_ml    : ${params.skip_ml}
 db_dir     : ${params.db_dir ?: 'auto-download'}
 outdir     : ${params.outdir}
 use_ramdisk: ${params.use_ramdisk}
 work_dir   : ${params.work_dir ?: 'default (./work)'}
=========================================================
""".stripIndent()

// -----------------------------------------------------------------------
// Main workflow
// -----------------------------------------------------------------------
workflow {

    // --- Build sample channel from reads parameter ---
    ch_reads = Channel
        .fromFilePairs( params.reads, checkIfExists: true )
        .map { sample_id, reads ->
            def meta = [id: sample_id]
            [ meta, reads ]
        }

    // --- Host genome channel ---
    if ( params.host != 'none' ) {
        def host_list = params.host.tokenize(',').collect { it.trim() }
        def host_fastas = host_list.collect { name ->
            file("${params.db_dir ?: 'databases'}/host_genomes/${name}/genome.fa.gz", checkIfExists: true)
        }
        ch_host_genome = Channel.fromList(host_fastas)
    } else {
        ch_host_genome = Channel.empty()
    }

    // --- Database path channels ---
    def db_base = params.db_dir ?: 'databases'
    ch_sample_map = Channel.fromPath("${db_base}/sample_map.tsv", checkIfExists: false)
    ch_ictv_vmr   = Channel.fromPath("${db_base}/taxonomy/ictv_vmr.tsv", checkIfExists: false)

    ch_genomad_db = Channel.value(
        file("${db_base}/genomad_db", checkIfExists: true)
    )
    ch_diamond_db = Channel.value(
        file("${db_base}/viral_protein/uniref90_viral.dmnd", checkIfExists: true)
    )

    // --- Step 1: PREPROCESSING ---
    PREPROCESSING( ch_reads, ch_host_genome )

    // --- Step 2: CO-ASSEMBLY (all reads pooled -> single MEGAHIT/metaSPAdes run) ---
    ASSEMBLY( PREPROCESSING.out.filtered_reads )

    // --- Step 3: DETECTION (geNomad + Diamond on co-assembly contigs, runs once) ---
    DETECTION( ASSEMBLY.out.contigs, ch_genomad_db, ch_diamond_db )

    // --- Step 4: CLASSIFICATION (MMseqs2 + TaxonKit on co-assembly, CoverM per-sample) ---
    CLASSIFICATION(
        ASSEMBLY.out.contigs,           // co-assembly contigs (single file)
        PREPROCESSING.out.filtered_reads, // per-sample reads for coverage mapping
        DETECTION.out.detected_seqs,    // detection results (coassembly)
        ch_sample_map,
        ch_ictv_vmr
    )

    // --- Step 5: REPORTING (Dashboard + Report + MultiQC) ---
    ch_qc_stats = PREPROCESSING.out.trim_stats
        .map { meta, stats -> stats }
        .collect()

    // Assembly stats is now a single file (co-assembly), wrap in list for collect
    ch_assembly_stats = ASSEMBLY.out.stats.collect()

    REPORTING(
        CLASSIFICATION.out.bigtable,
        CLASSIFICATION.out.counts,
        CLASSIFICATION.out.alpha_div,
        CLASSIFICATION.out.beta_div,
        CLASSIFICATION.out.pcoa,
        ch_qc_stats,
        ch_assembly_stats,
        PREPROCESSING.out.fastp_json,
        PREPROCESSING.out.fastqc_raw,
        PREPROCESSING.out.fastqc_trimmed
    )
}

// -----------------------------------------------------------------------
// Completion handler
// -----------------------------------------------------------------------
workflow.onComplete {
    log.info """
    =========================================================
     DeepInvirus Pipeline - Execution Summary
    =========================================================
     Pipeline completed at : ${workflow.complete}
     Duration              : ${workflow.duration}
     Success               : ${workflow.success}
     Work directory        : ${workflow.workDir}
     Output directory      : ${params.outdir}
     Exit status           : ${workflow.exitStatus}
    =========================================================
    """.stripIndent()

    if (workflow.success) {
        log.info "Results are available in: ${params.outdir}"
        log.info "  - Dashboard : ${params.outdir}/dashboard.html"
        log.info "  - Report    : ${params.outdir}/report.docx"
        log.info "  - MultiQC   : ${params.outdir}/qc/multiqc_report.html"
        log.info "  - Bigtable  : ${params.outdir}/taxonomy/bigtable.tsv"
    }

    if (params.use_ramdisk) {
        log.info "Note: RAM disk cleanup is handled by the CLI runner (ramdisk_manager.py)."
        log.info "  If running Nextflow directly, clean up manually: rm -rf ${params.ramdisk_path}"
    }
}

// -----------------------------------------------------------------------
// Error handler
// -----------------------------------------------------------------------
workflow.onError {
    log.error """
    =========================================================
     DeepInvirus Pipeline - ERROR
    =========================================================
     Error message : ${workflow.errorMessage}
     Exit status   : ${workflow.exitStatus}
     Work directory: ${workflow.workDir}
    =========================================================

     Troubleshooting:
       1. Check the error message above for details.
       2. Examine process-level logs in: ${workflow.workDir}
       3. Common issues:
          - Missing databases: run 'install_databases.py --db-dir <path>'
          - Insufficient memory: adjust --max_memory in nextflow.config
          - Missing input files: verify --reads path exists
       4. Resume from the last successful step:
          nextflow run main.nf -resume [same parameters]

    =========================================================
    """.stripIndent()
}
