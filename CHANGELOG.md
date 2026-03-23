# Changelog

All notable changes to DeepInvirus will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
