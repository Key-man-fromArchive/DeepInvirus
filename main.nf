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
include { ITERATIVE_CLASSIFICATION } from './subworkflows/iterative_classification'
include { REPORTING      } from './subworkflows/reporting'
include { KRAKEN2_CLASSIFY } from './modules/local/kraken2'
include { BRACKEN          } from './modules/local/bracken'
include { KRONA            } from './modules/local/krona'

// -----------------------------------------------------------------------
// Pipeline parameters
// -----------------------------------------------------------------------
params.reads      = null          // FASTQ files or directory path
params.host       = 'none'       // Host genome(s): comma-separated nicknames or 'none'
params.outdir     = './results'   // Output directory
params.trimmer    = 'bbduk'      // bbduk or fastp
params.assembler  = 'megahit'    // megahit or metaspades
params.search     = 'very-sensitive'  // fast, sensitive, or very-sensitive
params.skip_ml    = false        // Skip ML-based virus detection
params.db_dir     = null         // Custom DB path (null = use default DB)
params.kraken2_db = null         // Kraken2 database directory (optional)
params.uniref50_db = null        // UniRef50 Diamond DB (optional)
params.viral_nt_db = null        // Viral nucleotide BLAST DB (optional)
params.polymicrobial_nt_db = null // Polymicrobial nucleotide BLAST DB (optional)
params.kraken2_confidence = 0.0  // Kraken2 confidence threshold (annotation only)
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
        --reads       Path to paired FASTQ files (glob pattern)
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
                      Options: fast, sensitive, very-sensitive
                      [default: ${params.search}]

        --skip_ml     Skip ML-based virus detection (geNomad)
                      [default: ${params.skip_ml}]

        --db_dir      Path to pre-built reference databases
                      [default: auto-download]

        --kraken2_db  Kraken2 database directory for read annotation
                      [default: ${params.kraken2_db}]

        --uniref50_db UniRef50 Diamond DB for Tier 2 verification
                      [default: ${params.uniref50_db}]

        --viral_nt_db Viral nucleotide BLAST DB for Tier 3
                      [default: ${params.viral_nt_db}]

        --polymicrobial_nt_db
                      Polymicrobial nucleotide BLAST DB for Tier 4
                      [default: ${params.polymicrobial_nt_db}]

        --help        Show this help message

    Profiles:
        -profile docker        Run with Docker containers
        -profile singularity   Run with Singularity containers
        -profile test          Run with minimal test data

    Examples:
        nextflow run main.nf --reads '/data/*_R{1,2}.fastq.gz' -profile docker
        nextflow run main.nf --reads '/data/*_R{1,2}.fastq.gz' --host human --assembler metaspades -profile singularity
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

if (!(params.search in ['fast', 'sensitive', 'very-sensitive'])) {
    log.error "ERROR: --search must be 'fast', 'sensitive', or 'very-sensitive'. Got: '${params.search}'"
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
 kraken2_db : ${params.kraken2_db ?: 'disabled'}
 uniref50_db: ${params.uniref50_db ?: 'disabled'}
 viral_nt_db: ${params.viral_nt_db ?: 'disabled'}
 poly_nt_db : ${params.polymicrobial_nt_db ?: 'disabled'}
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
    // Use Channel.value (not fromPath) so empty/missing files don't block MERGE_RESULTS
    def sample_map_file = file("${db_base}/sample_map.tsv")
    if (!sample_map_file.exists()) {
        sample_map_file = file("${projectDir}/assets/empty_sample_map.tsv")
    }
    ch_sample_map = Channel.value(sample_map_file)

    def ictv_file = file("${db_base}/taxonomy/ictv_vmr.tsv")
    if (!ictv_file.exists()) {
        ictv_file = file("${projectDir}/assets/empty_ictv_vmr.tsv")
    }
    ch_ictv_vmr = Channel.value(ictv_file)

    // geNomad DB — may be genomad_db/ or genomad_db/checkv-db-v1.5/ etc.
    def genomad_path = file("${db_base}/genomad_db")
    if (!genomad_path.exists()) {
        log.error "geNomad DB not found: ${db_base}/genomad_db"
        exit 1
    }
    ch_genomad_db = Channel.value(genomad_path)
    // Auto-detect viral protein Diamond DB (try multiple names)
    def diamond_candidates = [
        "${db_base}/viral_protein/uniref90_viral.dmnd",
        "${db_base}/viral_protein/viral_protein.dmnd",
        "${db_base}/genbank_viral_protein/viral_protein_refseq.dmnd",
    ]
    def diamond_path = diamond_candidates.find { file(it).exists() }
    if (!diamond_path) {
        log.error "Viral protein Diamond DB not found in: ${diamond_candidates}"
        exit 1
    }
    ch_diamond_db = Channel.value(file(diamond_path))
    log.info "Viral protein DB: ${diamond_path}"
    ch_mmseqs_db = Channel.value(
        file("${db_base}/viral_nucleotide", checkIfExists: true)
    )

    // --- Auto-detect all DBs from db_base directory ---
    // All DBs are resolved from --db_dir (single flag). Explicit params override auto-detection.
    // Usage: nextflow run main.nf --db_dir ~/Database/DeepInvirus

    // CheckV (optional)
    def checkv_path = params.checkv_db ?: "${db_base}/checkv_db"
    if ( file(checkv_path).exists() ) {
        ch_checkv_db = Channel.value(file(checkv_path))
    } else {
        ch_checkv_db = Channel.empty()
    }

    // Exclusion DB (optional)
    def exclusion_path = params.exclusion_db ?: "${db_base}/exclusion_db"
    if ( file(exclusion_path).exists() ) {
        ch_exclusion_db = Channel.value(file(exclusion_path))
    } else {
        ch_exclusion_db = Channel.empty()
    }

    // Kraken2 (optional — independent profiling section)
    def kraken2_path = params.kraken2_db ?: "${db_base}/kraken2_core_nt"
    if ( file("${kraken2_path}/hash.k2d").exists() ) {
        ch_kraken2_db = Channel.value(file(kraken2_path))
        log.info "Kraken2 DB detected: ${kraken2_path}"
    } else {
        ch_kraken2_db = Channel.empty()
        log.info "Kraken2 DB not found — read profiling disabled"
    }

    // UniRef50 Diamond (Tier 2 AA)
    def uniref50_path = params.uniref50_db ?: "${db_base}/uniref50/uniref50.dmnd"
    if ( file(uniref50_path).exists() ) {
        ch_uniref50_db = Channel.value(file(uniref50_path))
        log.info "UniRef50 DB detected: ${uniref50_path}"
    } else {
        ch_uniref50_db = Channel.value(file('/dev/null'))
        log.info "UniRef50 DB not found — Tier 2 AA disabled"
    }

    // Viral NT BLAST (Tier 3 NT) — prefix path
    def viral_nt_prefix = params.viral_nt_db ?: "${db_base}/genbank_viral_nt/viral_nt"
    if ( file("${viral_nt_prefix}.nsq").exists() || file("${viral_nt_prefix}.00.nsq").exists() ) {
        ch_viral_nt_db = Channel.value(viral_nt_prefix)
        log.info "Viral NT DB detected: ${viral_nt_prefix}"
    } else {
        ch_viral_nt_db = Channel.value('/dev/null')
        log.info "Viral NT DB not found — Tier 3 NT disabled"
    }

    // Polymicrobial NT BLAST (Tier 4 NT) — prefix path
    def poly_nt_prefix = params.polymicrobial_nt_db ?: "${db_base}/polymicrobial_nt/polymicrobial_nt"
    if ( file("${poly_nt_prefix}.nsq").exists() || file("${poly_nt_prefix}.00.nsq").exists() ) {
        ch_polymicrobial_nt_db = Channel.value(poly_nt_prefix)
        log.info "Polymicrobial NT DB detected: ${poly_nt_prefix}"
    } else {
        ch_polymicrobial_nt_db = Channel.value('/dev/null')
        log.info "Polymicrobial NT DB not found — Tier 4 NT disabled"
    }

    def nodes_file = file("${db_base}/taxonomy/nodes.dmp")
    if (!nodes_file.exists()) {
        nodes_file = file('/dev/null')
    }
    ch_taxonomy_nodes = Channel.value(nodes_file)

    // Taxonomy directory for TaxonKit (contains names.dmp, nodes.dmp)
    def taxonomy_dir = file("${db_base}/taxonomy")
    ch_taxonomy_db = Channel.value(taxonomy_dir)

    // --- Step 1: PREPROCESSING ---
    PREPROCESSING( ch_reads, ch_host_genome )

    // --- Step 1b: Kraken2 read-level profiling (optional, independent) ---
    // @TASK T1.3 - Bracken + Krona downstream of Kraken2 (Section B)
    if ( params.kraken2_db ) {
        KRAKEN2_CLASSIFY( PREPROCESSING.out.filtered_reads, ch_kraken2_db )
        ch_kraken2_reports = KRAKEN2_CLASSIFY.out.report.map { meta, f -> f }.collect()

        // Bracken: species-level abundance re-estimation from Kraken2 report
        BRACKEN( KRAKEN2_CLASSIFY.out.report, ch_kraken2_db )

        // Krona: interactive HTML visualization from Kraken2 report
        KRONA( KRAKEN2_CLASSIFY.out.report )
    } else {
        ch_kraken2_reports = Channel.value([ file('/dev/null') ])
    }

    // --- Step 2: CO-ASSEMBLY (ALL reads, no Kraken2 filtering) ---
    ASSEMBLY( PREPROCESSING.out.filtered_reads )

    // --- Step 3: DETECTION (geNomad + Diamond on co-assembly contigs, runs once) ---
    //     Optional CheckV quality assessment when params.checkv_db is set.
    //     Optional multi-kingdom exclusion when params.exclusion_db is set.
    DETECTION( ASSEMBLY.out.contigs, ch_genomad_db, ch_diamond_db, ch_checkv_db, ch_exclusion_db )

    // --- Step 3b: Hybrid v1 iterative evidence integration (optional tiers, always emits classification table) ---
    ITERATIVE_CLASSIFICATION(
        ASSEMBLY.out.contigs,
        DETECTION.out.genomad_summary,
        ch_taxonomy_nodes,
        ch_diamond_db,
        ch_uniref50_db,
        ch_viral_nt_db,
        ch_polymicrobial_nt_db
    )

    // --- Step 4: CLASSIFICATION (MMseqs2 + TaxonKit on co-assembly, CoverM per-sample) ---
    // Pass evidence integration results to enrich bigtable with 4-tier classification
    ch_evidence_classified = ITERATIVE_CLASSIFICATION.out.classified
        .map { meta, f -> f }
        .ifEmpty( file("${projectDir}/assets/NO_FILE") )

    CLASSIFICATION(
        ASSEMBLY.out.contigs,           // co-assembly contigs (single file)
        PREPROCESSING.out.filtered_reads, // per-sample reads for coverage mapping
        DETECTION.out.detected_seqs,    // detection results (coassembly)
        ch_sample_map,
        ch_ictv_vmr,
        ch_mmseqs_db,                   // MMseqs2 database directory
        ch_evidence_classified,         // 4-tier evidence integration classified contigs
        ch_taxonomy_db                  // NCBI taxonomy for TaxonKit lineage
    )

    // --- Step 5: REPORTING (Dashboard + Report + MultiQC) ---
    ch_qc_stats = PREPROCESSING.out.trim_stats
        .map { meta, stats -> stats }
        .collect()

    // Assembly stats is now a single file (co-assembly), wrap in list for collect
    ch_assembly_stats = ASSEMBLY.out.stats.collect()

    // Per-sample coverage files (strip meta, collect into flat list)
    ch_coverage_files = CLASSIFICATION.out.coverage
        .map { meta, f -> f }
        .collect()
        .ifEmpty( [] )

    // Per-base depth files (for contig coverage depth visualization)
    ch_depth_files = CLASSIFICATION.out.depth
        .map { meta, f -> f }
        .collect()
        .ifEmpty( [] )

    // Host removal stats (strip meta, collect; empty when host='none')
    ch_host_stats = PREPROCESSING.out.host_stats
        .map { meta, f -> f }
        .collect()
        .ifEmpty( [] )

    REPORTING(
        CLASSIFICATION.out.bigtable,
        CLASSIFICATION.out.sample_matrix,
        CLASSIFICATION.out.alpha_div,
        CLASSIFICATION.out.beta_div,
        CLASSIFICATION.out.pcoa,
        ASSEMBLY.out.contigs,
        ch_qc_stats,
        ch_assembly_stats,
        ch_coverage_files,
        ch_host_stats,
        PREPROCESSING.out.fastp_json,
        PREPROCESSING.out.fastqc_raw,
        PREPROCESSING.out.fastqc_trimmed,
        ch_depth_files
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

    // Copy Nextflow log to output directory for traceability
    try {
        def logFile = file(".nextflow.log")
        def outLog = file("${params.outdir}/pipeline_info/nextflow.log")
        outLog.parent.mkdirs()
        if (logFile.exists()) {
            logFile.copyTo(outLog)
        }

        // Save a run summary
        def summary = file("${params.outdir}/pipeline_info/run_summary.txt")
        summary.text = """
DeepInvirus Pipeline Run Summary
================================
Completed at : ${workflow.complete}
Duration     : ${workflow.duration}
Success      : ${workflow.success}
Work dir     : ${workflow.workDir}
Output dir   : ${params.outdir}
Command line : ${workflow.commandLine}
Nextflow ver : ${workflow.nextflow.version}
"""

        // Generate Materials and Methods section
        def methods = file("${params.outdir}/materials_and_methods.txt")
        def hostText = params.host != 'none' ? "Host reads were removed by mapping to ${params.host} reference genome(s) using minimap2 (Li, 2018) with -ax sr preset." : "Host read removal was not performed."
        def mlText = !params.skip_ml ? "Viral sequences were identified using geNomad (Camargo et al., 2024) in end-to-end mode on co-assembled contigs." : "ML-based virus detection (geNomad) was skipped; Diamond BLASTx was used as the sole detection method."
        def kraken2Text = params.kraken2_db ? "Independent read-level taxonomic profiling was performed using Kraken2 (Wood et al., 2019) with the core_nt database, followed by Bracken (Lu et al., 2017) for species-level abundance re-estimation and Krona (Ondov et al., 2011) for interactive visualization." : ""
        def tier2Text = params.uniref50_db ? "Tier 2 verification was performed by searching viral candidate ORFs against UniRef50 (Suzek et al., 2015; 60.3M clusters) using Diamond BLASTx (--sensitive, e-value 1e-3) to identify stronger non-viral homologs." : ""
        def tier3Text = params.viral_nt_db ? "Tier 3 nucleotide search was performed using BLASTn against GenBank viral nucleotide sequences to capture viruses missed by protein-level searches." : ""
        def tier4Text = params.polymicrobial_nt_db ? "Tier 4 polymicrobial verification was performed using BLASTn against RefSeq representative genomes of bacteria, archaea, fungi, plants, and protozoa to identify false-positive viral assignments." : ""
        def checkVText = params.checkv_db ? "Genome completeness and contamination were assessed using CheckV (Nayfach et al., 2021)." : ""

        methods.text = """Materials and Methods
=====================

Viral Metagenomics Analysis (DeepInvirus Hybrid v1)
----------------------------------------------------

Raw paired-end sequencing reads were processed using the DeepInvirus pipeline v0.3.0 (https://github.com/deepinvirus) implemented in Nextflow (Di Tommaso et al., 2017).

Quality Control and Preprocessing
Quality control was performed using ${params.trimmer == 'bbduk' ? 'BBDuk v39.06+ (BBTools suite; Bushnell, 2014)' : 'fastp (Chen et al., 2018)'} for adapter removal, quality trimming (Q≥20), and PhiX/contaminant filtering. ${hostText} Read quality was assessed using FastQC before and after trimming.

De Novo Assembly
Cleaned reads from all samples were pooled for co-assembly using ${params.assembler == 'megahit' ? 'MEGAHIT v1.2.9 (Li et al., 2015) with --presets meta-large and --min-contig-len ' + params.min_contig_len : 'metaSPAdes (Nurk et al., 2017)'}. Co-assembly maximizes sensitivity for low-abundance viruses by leveraging reads across all samples. Post-assembly redundancy reduction was then performed with MMseqs2 easy-cluster at 95% sequence identity and 98% coverage to collapse near-identical contigs before downstream evidence integration.

Virus Detection (Section A: Assembly-based Virome)
${mlText} Protein homology search was performed using Diamond BLASTx v2.1+ (Buchfink et al., 2021) in ${params.search} mode (e-value ≤ 1e-5) against a viral protein database. Detection results from both methods were merged, with contigs identified by either method retained as viral candidates.

Iterative Taxonomic Verification (Hecatomb-style 4-Tier)
Following initial detection, viral candidates underwent iterative verification inspired by the Hecatomb pipeline (Roach et al., 2024):
- Tier 1 (AA): Diamond BLASTx against viral protein database (--very-sensitive, e-value 1e-5) for initial viral protein homology.
${tier2Text}
${tier3Text}
${tier4Text}
Evidence from all tiers was integrated using a rule-based classification system assigning each contig as: strong_viral, novel_viral_candidate, ambiguous, cellular, or unknown.

${checkVText}

Taxonomic Classification
Taxonomic assignment was performed using MMseqs2 (Steinegger & Söding, 2017) easy-search with the GenBank viral nucleotide database as the primary reference, followed by lineage reformatting with TaxonKit (Shen & Ren, 2021). RefSeq-derived accession patterns were retained as a secondary `refseq_verified` confidence tag.

Per-sample Quantification
Per-sample read coverage was calculated by mapping each sample's reads back to the co-assembled contigs using CoverM (https://github.com/wwood/CoverM). Mean depth, trimmed mean, breadth of coverage, and true contig length were computed for each contig in each sample. Per-base depth profiles were generated with samtools depth for contig-level inspection. Coverage-normalized relative abundance (RPM) was calculated as (contig coverage / total sample coverage) × 10^6.

${kraken2Text}

Diversity Analysis
Alpha diversity (Shannon, Simpson, Chao1, Pielou evenness) and beta diversity (Bray-Curtis dissimilarity) were calculated from the RPM-based sample-taxon abundance matrix. Principal Coordinates Analysis (PCoA) was performed using classical multidimensional scaling on the Bray-Curtis distance matrix. Diversity analyses were conditional on sample count: full analysis for n≥3 samples, descriptive comparison for n=2, and profile-only for n=1.

Visualization and Reporting
Results were visualized in an interactive HTML dashboard (Plotly.js) and a formatted Word report, both generated automatically from the unified bigtable. All figures were produced in both PNG (300 DPI) and SVG (vector) formats using a colorblind-safe Okabe-Ito palette.

Parameters Used
- Trimmer: ${params.trimmer}
- Assembler: ${params.assembler}
- Min contig length: ${params.min_contig_len} bp
- Min virus score: ${params.min_virus_score}
- Min bitscore: ${params.min_bitscore}
- Search sensitivity: ${params.search}
- Host: ${params.host}
- Kraken2 DB: ${params.kraken2_db ?: 'not used'}
- UniRef50 DB: ${params.uniref50_db ?: 'not used'}

Software Versions
- Nextflow: ${workflow.nextflow.version}
- DeepInvirus: v0.3.0
- Python: 3.10+

References
- Buchfink B et al. (2021) Sensitive protein alignments at tree-of-life scale using DIAMOND. Nature Methods 18:366-368.
- Bushnell B (2014) BBTools software package. https://sourceforge.net/projects/bbmap/
- Camargo AP et al. (2024) Identification of mobile genetic elements with geNomad. Nature Biotechnology 42:1303-1312.
- Chen S et al. (2018) fastp: an ultra-fast all-in-one FASTQ preprocessor. Bioinformatics 34:i884-i890.
- Di Tommaso P et al. (2017) Nextflow enables reproducible computational workflows. Nature Biotechnology 35:316-319.
- Li D et al. (2015) MEGAHIT: An ultra-fast single-node solution for large and complex metagenomics assembly. Bioinformatics 31:1674-1676.
- Li H (2018) Minimap2: pairwise alignment for nucleotide sequences. Bioinformatics 34:3094-3100.
- Lu J et al. (2017) Bracken: estimating species abundance in metagenomics data. PeerJ Computer Science 3:e104.
- Nayfach S et al. (2021) CheckV assesses the quality and completeness of metagenome-assembled viral genomes. Nature Biotechnology 39:578-585.
- Ondov BD et al. (2011) Interactive metagenomic visualization in a Web browser. BMC Bioinformatics 12:385.
- Roach MJ et al. (2024) Hecatomb: an integrated software platform for viral metagenomics. GigaScience 13:giae020.
- Shen W & Ren H (2021) TaxonKit: a practical and efficient NCBI taxonomy toolkit. Journal of Genetics and Genomics 48:844-850.
- Steinegger M & Söding J (2017) MMseqs2 enables sensitive protein sequence searching. Nature Biotechnology 35:1026-1028.
- Suzek BE et al. (2015) UniRef clusters: a comprehensive and scalable alternative for improving sequence similarity searches. Bioinformatics 31:926-932.
- Wood DE et al. (2019) Improved metagenomic analysis with Kraken 2. Genome Biology 20:257.
"""
    } catch (Exception e) {
        log.warn "Could not copy pipeline log: ${e.message}"
    }

    if (workflow.success) {
        log.info "Results are available in: ${params.outdir}"
        log.info "  - Dashboard : ${params.outdir}/dashboard.html"
        log.info "  - Report    : ${params.outdir}/report.docx"
        log.info "  - MultiQC   : ${params.outdir}/qc/multiqc_report.html"
        log.info "  - Bigtable  : ${params.outdir}/taxonomy/bigtable.tsv"
        log.info "  - Run log   : ${params.outdir}/pipeline_info/nextflow.log"
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
