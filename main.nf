#!/usr/bin/env nextflow

// @TASK T0.1, T0.4, T6.1 - DeepInvirus main pipeline entrypoint (final integration)
// @SPEC docs/planning/02-trd.md#3-파이프라인-상세-설계

nextflow.enable.dsl = 2

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    DeepInvirus - Viral Metagenomics Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Raw FASTQ -> Virus Detection -> Classification -> Report
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
// Pipeline parameters (see: docs/planning/02-trd.md Section 3.1)
// -----------------------------------------------------------------------
params.reads      = null          // FASTQ files or directory path
params.host       = 'human'      // Host genome(s): comma-separated nicknames (e.g., 'tmol,zmor') or 'none'
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
     DeepInvirus v0.1.0 - Viral Metagenomics Pipeline
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

// host validation: parse comma-separated nicknames and verify each host directory exists
// @TASK T-MULTI-HOST - Multi-host genome selection support
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
// @TASK T-RAMDISK - Log RAM disk status if enabled
if (params.use_ramdisk) {
    log.info "RAM disk enabled: work directory → ${params.ramdisk_path}"
    log.info "  (pass -w ${params.ramdisk_path} via CLI runner for actual effect)"
}

log.info """
=========================================================
 DeepInvirus v0.1.0
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

    // --- INPUT_CHECK: Build sample channel from reads parameter ---
    // Create channel of [meta, [R1, R2]] tuples from glob pattern
    ch_reads = Channel
        .fromFilePairs( params.reads, checkIfExists: true )
        .map { sample_id, reads ->
            def meta = [id: sample_id]
            [ meta, reads ]
        }

    // --- Host genome channel setup ---
    // @TASK T1.3, T-MULTI-HOST - Set host genome paths from comma-separated nicknames
    // @SPEC docs/planning/04-database-design.md#host_genomes
    // Host genome: parse comma-separated nicknames, collect all genome.fa.gz files
    if ( params.host != 'none' ) {
        def host_list = params.host.tokenize(',').collect { it.trim() }
        def host_fastas = host_list.collect { name ->
            file("${params.db_dir ?: 'databases'}/host_genomes/${name}/genome.fa.gz", checkIfExists: true)
        }
        ch_host_genome = Channel.fromList(host_fastas)
    } else {
        ch_host_genome = Channel.empty()
    }

    // --- DB path channels ---
    // @TASK T6.1 - Database directory channels for classification tools
    def db_base = params.db_dir ?: 'databases'
    ch_sample_map = Channel.fromPath("${db_base}/sample_map.tsv", checkIfExists: false)
    ch_ictv_vmr   = Channel.fromPath("${db_base}/taxonomy/ictv_vmr.tsv", checkIfExists: false)

    // --- Step 1: PREPROCESSING (FASTP + HOST_REMOVAL) ---
    PREPROCESSING( ch_reads, ch_host_genome )

    // --- Step 2: ASSEMBLY (MEGAHIT or METASPADES) ---
    ASSEMBLY( PREPROCESSING.out.filtered_reads )

    // --- Step 3: DETECTION (GENOMAD + DIAMOND -> MERGE) ---
    // DB channels for detection tools
    ch_genomad_db = Channel.value(
        file("${params.db_dir ?: 'databases'}/genomad_db", checkIfExists: true)
    )
    ch_diamond_db = Channel.value(
        file("${params.db_dir ?: 'databases'}/viral_protein/uniref90_viral.dmnd", checkIfExists: true)
    )

    DETECTION( ASSEMBLY.out.contigs, ch_genomad_db, ch_diamond_db )

    // --- Step 4: CLASSIFICATION (MMSEQS -> TAXONKIT -> COVERM -> MERGE_RESULTS -> DIVERSITY) ---
    CLASSIFICATION(
        ASSEMBLY.out.contigs,
        PREPROCESSING.out.filtered_reads,
        ASSEMBLY.out.contigs,
        DETECTION.out.detected_seqs,
        ch_sample_map,
        ch_ictv_vmr
    )

    // --- Step 5: REPORTING (DASHBOARD + REPORT + MULTIQC) ---
    // Collect per-sample stats into aggregated channels for reporting
    ch_qc_stats = PREPROCESSING.out.fastp_json,
        PREPROCESSING.out.fastqc_raw,
        PREPROCESSING.out.fastqc_trimmed
        .map { meta, json -> json }
        .collect()

    ch_assembly_stats = ASSEMBLY.out.stats
        .map { meta, stats -> stats }
        .collect()

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
// @TASK T6.1 - Pipeline completion summary
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

    // @TASK T-RAMDISK - Reminder about RAM disk cleanup
    if (params.use_ramdisk) {
        log.info "Note: RAM disk cleanup is handled by the CLI runner (ramdisk_manager.py)."
        log.info "  If running Nextflow directly, clean up manually: rm -rf ${params.ramdisk_path}"
    }
}

// -----------------------------------------------------------------------
// Error handler
// @TASK T6.1 - Pipeline error reporting
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
