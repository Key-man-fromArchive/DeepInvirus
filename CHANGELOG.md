# Changelog

All notable changes to DeepInvirus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-03-25

### Added
- **CheckV integration** (optional): genome completeness/contamination assessment via `--checkv_db`
- **Table of Contents** in Word report with hyperlinks
- **Executive Summary** section in report (auto-generated top virus highlight)
- **Results tab** in dashboard with inline PNG figures (base64 embedded)
- **VIRUS_ORIGIN evidence-tier system**: 22 families with confidence levels (high/medium/low)
- **Limitations section**: auto-generated from sample size, data type, and assembly strategy
- **Methods section**: auto-generated from pipeline metadata (no hardcoded tool names)
- **Per-sample coverage analysis**: cross-join merge for co-assembly pipeline
- **Breadth of coverage**: CoverM breadth column + detection confidence tiers (high/medium/low)
- **Coverage-normalized abundance (RPM)**: replaces contig-count-based diversity input
- **Appendix C/D**: Parameter Dictionary + Results Dictionary in report
- **SVG vector output**: all figures saved as both PNG (300 DPI) and SVG
- **Okabe-Ito colorblind-safe palette**: replaces tab10 palette
- **Sankey diagram**: domain->family 2-level with collision-safe node labels
- **PARSE_DIAMOND_ONLY process**: skip_ml=true path now produces standard detection schema
- **README.md in output folder**: Parameter + Results Dictionary included with results
- **Singularity containers**: bbduk, fastqc, multiqc, prodigal labels added

### Changed
- **merge_results.py**: complete rewrite -- co-assembly aware cross-join, RPM abundance, lineage parsing from taxonomy string, ICTV merge
- **generate_report.py**: complete rewrite -- 10-section structure, scientific hedging, no overclaiming
- **generate_dashboard.py**: unique-contig deduplication, Sankey genus fallback, coverage wiring
- **detection.nf**: PARSE_DIAMOND_ONLY for skip_ml, optional CheckV
- **classification.nf**: MMseqs2 DB channelized (was params.db_dir direct reference)
- **reporting.nf**: coverage/host-stats channels, REPORT->DASHBOARD order for figure passing
- **main.nf**: Channel.value for optional metadata, params.host='none' default, coverage/host-stats wiring, sample_matrix channel fix
- **parse_diamond.py**: 12/13 column compatibility, --merged-format flag
- **visualization.py**: Okabe-Ito palette, SVG output at 5 locations
- **docx_builder.py**: add_table_of_contents() method

### Fixed
- **Diamond staxids**: diamond.nf no longer requests staxids (DB may lack taxonomy); parse_diamond.py handles 12 or 13 columns
- **Optional channel blocking**: sample_map.tsv/ictv_vmr.tsv missing no longer blocks MERGE_RESULTS
- **skip_ml schema mismatch**: Diamond-only path now produces correct merged_detection schema
- **Contig double-counting**: all report/dashboard aggregations use unique seq_id
- **Family column contamination**: extract_family only returns *viridae or "Unclassified" (no class/order/phylum leakage)
- **Sankey self-loop**: "Unclassified" domain/family collision prevented via label disambiguation
- **Bowtie2->minimap2**: report Methods corrected to actual pipeline tool
- **scikit-bio->scipy+numpy**: report Methods corrected to actual libraries
- **RPM definition**: consistently documented as coverage-normalized (not reads-based)
- **Samplesheet CSV**: help message no longer advertises unimplemented CSV support
- **MultiQC BBDuk**: FastQC zips now included in MultiQC input when trimmer=bbduk

### Removed
- **Picornaviridae** from VIRUS_ORIGIN (replaced by Iflaviridae)
- **Parvoviridae hardcoded highlight** in conclusions
- **"dead sample/live sample"** causal language
- **"active replication"** claims from coverage interpretation

## [0.2.0] - 2026-03-23

### Added
- **Textual TUI interface**: interactive terminal UI for all pipeline operations
  - Main menu with 6 navigable screens and keyboard shortcuts
  - Run Analysis screen with parameter form, real-time progress bar, and log streaming
  - Database Management screen (view status, install/update components)
  - Host Genome screen (list installed hosts, add custom genomes)
  - Config Presets screen (save/load/delete pipeline parameter presets as YAML)
  - Run History screen (browse past runs, view results, re-run with same parameters)
- **Custom widgets**: HeaderWidget, FooterWidget, StatusBar, ProgressWidget, LogViewer
- **Theming**: Textual CSS stylesheet with design-system color palette
- **CLI entrypoint** (`deepinvirus` command) with Click-based subcommands:
  - `deepinvirus` (no args) launches TUI mode
  - `deepinvirus run` runs the Nextflow pipeline directly
  - `deepinvirus install-db` installs reference databases
  - `deepinvirus update-db` updates specific database components
  - `deepinvirus add-host` adds custom host reference genomes
  - `deepinvirus list-hosts` lists available host genomes
  - `deepinvirus config` manages configuration presets
  - `deepinvirus history` views run history
- **Config manager** (`bin/config_manager.py`): YAML preset save/load/delete
- **History manager** (`bin/history_manager.py`): JSON run history recording
- **Nextflow runner** (`bin/tui/runner.py`): async subprocess management for Nextflow
- **E2E test suite** for TUI screens and CLI entrypoint
- **pyproject.toml** updated with `[project.scripts]` entrypoint and new dependencies

## [0.1.0] - 2026-03-23

### Added
- **Pipeline framework**: Nextflow DSL2 main.nf with 5 subworkflows
  - PREPROCESSING: fastp QC + minimap2 host read removal
  - ASSEMBLY: MEGAHIT / metaSPAdes de novo assembly
  - DETECTION: geNomad ML detection + Diamond blastx homology search
  - CLASSIFICATION: MMseqs2 taxonomy + TaxonKit lineage + CoverM coverage + diversity analysis
  - REPORTING: interactive HTML dashboard + automated Word report + MultiQC
- **Nextflow process modules** (modules/local/):
  - input_check, fastp, host_removal, megahit, metaspades
  - genomad, diamond, merge_detection
  - mmseqs_taxonomy, taxonkit, coverm, merge_results, diversity
  - dashboard, report, multiqc
- **Python helper scripts** (bin/):
  - merge_results.py, calc_diversity.py, generate_dashboard.py, generate_report.py
  - parse_genomad.py, parse_diamond.py, parse_fastp.py, parse_host_removal.py
  - parse_assembly_stats.py, merge_detection.py
  - install_databases.py, update_databases.py
- **Database management CLI**:
  - install_databases.py with --dry-run, --components, --host options
  - update_databases.py with backup/rollback, --component, --force options
  - VERSION.json tracking for all database components
- **Configuration**:
  - nextflow.config with docker, singularity, test profiles
  - conf/base.config with resource labels (process_low/medium/high/high_memory)
  - conf/test.config for minimal test runs
- **Test suite** (pytest):
  - Module-level tests for all process modules
  - Subworkflow integration tests (preprocessing, assembly, detection, classification)
  - E2E structural validation (main.nf subworkflow includes, channel flow)
  - DB CLI tests (--help, --dry-run, VERSION.json schema, component selection)
- **Documentation**:
  - README.md with Quick Start, parameters, output description
  - TRD (Technical Requirements Document)
  - User flow diagrams
  - Coding conventions and development guide
  - Database design specification
- **Pipeline features**:
  - `workflow.onComplete` summary with output paths
  - `workflow.onError` troubleshooting guide
  - `--help` flag with full usage documentation
  - Input validation for all parameters
  - Conditional host removal (--host none to skip)
  - Conditional ML detection (--skip_ml to skip geNomad)
  - Assembler selection (--assembler megahit/metaspades)

## [Unreleased]

### Added
- Initial project structure (T0.1)
- main.nf skeleton with DSL2, params, help message
- nextflow.config with profiles (docker, singularity, test)
- conf/base.config with resource labels
- conf/test.config with minimal resources
- bin/requirements.txt Python dependencies
