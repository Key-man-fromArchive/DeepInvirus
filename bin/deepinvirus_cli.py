#!/usr/bin/env python3
# @TASK T12.1 - CLI entrypoint (Click-based)
# @SPEC docs/planning/06-tasks-tui.md#phase-12-t121-cli-엔트리포인트-redgreen
# @SPEC docs/planning/03-user-flow.md#6-CLI-명령어-목록
# @TEST tests/test_cli.py
"""
DeepInvirus CLI entrypoint.

Provides both TUI (interactive) and CLI (batch) modes:

    # TUI mode (no subcommand)
    deepinvirus

    # CLI mode (subcommands)
    deepinvirus run --reads ./data --host insect --outdir ./results
    deepinvirus install-db --db-dir /path/to/db
    deepinvirus update-db --db-dir /path/to/db --component taxonomy
    deepinvirus add-host --name beetle --fasta ref.fa --db-dir /path/to/db
    deepinvirus list-hosts --db-dir /path/to/db
    deepinvirus config
    deepinvirus history
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

import click

# Ensure bin/ is on sys.path so that sibling modules can be imported
_BIN_DIR = Path(__file__).resolve().parent
if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))


# ---------------------------------------------------------------------------
# Main CLI group
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.version_option(version="1.1.0", prog_name="DeepInvirus")
@click.pass_context
def cli(ctx):
    """DeepInvirus v1.1.0 - Viral metagenomics pipeline with TUI.

    Run without a subcommand to launch the interactive TUI.
    Use a subcommand for batch/scripting usage.
    """
    if ctx.invoked_subcommand is None:
        # No subcommand -> launch TUI
        try:
            from tui.app import DeepInVirusApp

            app = DeepInVirusApp()
            app.run()
        except ImportError as exc:
            click.echo(
                f"Error: Could not import TUI components: {exc}\n"
                "Make sure 'textual' is installed: pip install textual",
                err=True,
            )
            ctx.exit(1)


# ---------------------------------------------------------------------------
# run: Execute the DeepInvirus analysis pipeline
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--reads", required=True, help="Input FASTQ directory or file (glob pattern).")
@click.option("--host", default="none", help="Host genome name for read decontamination (use 'none' to skip).")
@click.option("--outdir", default=None, help="Output directory. Auto-generates timestamped name if not specified.")
@click.option(
    "--assembler",
    default="megahit",
    type=click.Choice(["megahit", "metaspades"], case_sensitive=False),
    help="De novo assembler to use.",
)
@click.option(
    "--search",
    default="very-sensitive",
    type=click.Choice(["fast", "sensitive", "very-sensitive"], case_sensitive=False),
    help="DIAMOND search sensitivity (default: very-sensitive in v1.1.0).",
)
@click.option("--skip-ml", is_flag=True, default=False, help="Skip geNomad ML detection.")
@click.option("--threads", default=None, type=int, help="Number of threads (default: all available).")
@click.option(
    "--db-dir",
    default=None,
    type=click.Path(),
    help="Path to reference databases (GenBank viral NT primary DB root).",
)
@click.option("--resume", is_flag=True, default=False, help="Resume a previous run with -resume.")
@click.option(
    "--use-ramdisk",
    is_flag=True,
    default=False,
    help="Use RAM disk (/dev/shm) for Nextflow work directory. Recommended for NFS data.",
)
@click.option(
    "--ramdisk-size",
    default=0,
    type=int,
    help="RAM disk size in GB (0=auto, recommended: 50-300).",
)
@click.option(
    "--work-dir",
    default=None,
    type=click.Path(),
    help="Custom Nextflow work directory path.",
)
@click.option(
    "--checkv-db",
    default=None,
    type=click.Path(),
    help="CheckV database path for genome quality assessment (optional).",
)
@click.option(
    "--exclusion-db",
    default=None,
    type=click.Path(),
    help="SwissProt Diamond DB for non-viral contig exclusion (optional).",
)
def run(reads, host, outdir, assembler, search, skip_ml, threads, db_dir, resume, use_ramdisk, ramdisk_size, work_dir, checkv_db, exclusion_db):
    """Run the DeepInvirus v1.1.0 analysis pipeline.

    Launches the Nextflow pipeline (main.nf) with the specified parameters.
    Use --use-ramdisk for massive I/O speedup when data is on NFS.

    If --outdir is not specified, a timestamped directory name is generated
    automatically (e.g., ./20260325_143022_deepinvirus_results).
    """
    from ramdisk_manager import RamdiskManager

    ramdisk = None

    # Auto-generate timestamped output directory if not specified
    if outdir is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = f"./{timestamp}_deepinvirus_results"
        click.echo(f"Output directory (auto): {outdir}")

    # Build Nextflow command
    cmd = ["nextflow", "run", str(_BIN_DIR.parent / "main.nf")]
    cmd += ["--reads", reads]
    cmd += ["--host", host]
    cmd += ["--outdir", outdir]
    cmd += ["--assembler", assembler]
    cmd += ["--search", search]

    if skip_ml:
        cmd += ["--skip_ml", "true"]
    if threads is not None:
        cmd += ["--threads", str(threads)]
    if db_dir is not None:
        cmd += ["--db_dir", db_dir]
    if checkv_db is not None:
        cmd += ["--checkv_db", checkv_db]
    if exclusion_db is not None:
        cmd += ["--exclusion_db", exclusion_db]

    # @TASK T-RAMDISK - RAM disk or custom work directory
    if use_ramdisk:
        size = ramdisk_size if ramdisk_size > 0 else None
        ramdisk = RamdiskManager(size_gb=size or 200)
        if not ramdisk.is_available():
            click.echo("Error: /dev/shm is not available on this system.", err=True)
            sys.exit(1)
        click.echo(f"RAM disk: {ramdisk.size_gb} GB (available: {ramdisk.get_available_ram_gb()} GB)")
        nf_work = ramdisk.create()
        ramdisk.register_cleanup()
        cmd += ["-w", str(nf_work)]
        avail = ramdisk.get_available_ram_gb()
        click.echo(f"RAM disk enabled: {nf_work} (available: {avail} GB)")
    elif work_dir:
        cmd += ["-w", work_dir]

    if resume:
        cmd += ["-resume"]

    click.echo(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=False)
        # Cleanup RAM disk after pipeline finishes
        if ramdisk is not None:
            click.echo("Cleaning up RAM disk...")
            ramdisk.cleanup()
        sys.exit(result.returncode)
    except FileNotFoundError:
        # Cleanup RAM disk on error
        if ramdisk is not None:
            ramdisk.cleanup()
        click.echo(
            "Error: 'nextflow' not found. Please install Nextflow first.\n"
            "See: https://www.nextflow.io/docs/latest/getstarted.html",
            err=True,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# install-db: Install reference databases
# ---------------------------------------------------------------------------


@cli.command("install-db")
@click.option("--db-dir", required=True, type=click.Path(), help="Database directory.")
@click.option("--components", default="all", help="Components to install (comma-separated or 'all').")
@click.option("--host", default="human", help="Host genome to download.")
@click.option("--threads", default=4, type=int, help="Number of threads for indexing.")
@click.option("--dry-run", is_flag=True, default=False, help="Preview without downloading.")
def install_db(db_dir, components, host, threads, dry_run):
    """Install reference databases.

    Downloads and indexes all reference databases required by the pipeline.
    """
    from install_databases import install

    install(
        db_dir=Path(db_dir),
        components=components,
        host=host,
        threads=threads,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# update-db: Update specific database component
# ---------------------------------------------------------------------------


@cli.command("update-db")
@click.option("--db-dir", required=True, type=click.Path(exists=True), help="Database directory.")
@click.option("--component", required=True, help="Component(s) to update (comma-separated or 'all').")
@click.option("--host", default="human", help="Host genome key (when updating host).")
@click.option("--threads", default=4, type=int, help="Number of threads for indexing.")
@click.option("--dry-run", is_flag=True, default=False, help="Preview without modifying.")
@click.option("--force", is_flag=True, default=False, help="Force update even if up-to-date.")
def update_db(db_dir, component, host, threads, dry_run, force):
    """Update specific database component.

    Selectively updates individual database components with automatic
    backup/rollback.
    """
    from update_databases import COMPONENT_MAP, update_component

    if component == "all":
        components = list(COMPONENT_MAP.keys())
    else:
        components = [c.strip() for c in component.split(",")]

    for comp in components:
        update_component(
            db_dir=Path(db_dir),
            component=comp,
            host=host,
            threads=threads,
            dry_run=dry_run,
            force=force,
        )


# ---------------------------------------------------------------------------
# add-host: Add a custom host genome
# ---------------------------------------------------------------------------


@cli.command("add-host")
@click.option("--name", required=True, help="Host genome name (e.g., beetle, chicken).")
@click.option("--fasta", required=True, type=click.Path(exists=True), help="Reference genome FASTA file.")
@click.option("--db-dir", required=True, type=click.Path(), help="Root database directory.")
@click.option("--threads", default=4, type=int, help="Threads for minimap2 indexing.")
@click.option("--skip-index", is_flag=True, default=False, help="Skip minimap2 index build.")
def add_host_cmd(name, fasta, db_dir, threads, skip_index):
    """Add a custom host genome.

    Copies FASTA, builds minimap2 index, and updates VERSION.json.
    """
    from add_host import add_host

    add_host(
        name=name,
        fasta=Path(fasta),
        db_dir=Path(db_dir),
        threads=threads,
        skip_index=skip_index,
    )


# ---------------------------------------------------------------------------
# list-hosts: List available host genomes
# ---------------------------------------------------------------------------


@cli.command("list-hosts")
@click.option("--db-dir", required=True, type=click.Path(exists=True), help="Root database directory.")
def list_hosts(db_dir):
    """List available host genomes.

    Reads VERSION.json and shows installed host genomes with their metadata.
    """
    version_file = Path(db_dir) / "VERSION.json"
    if not version_file.exists():
        click.echo("No VERSION.json found. Run 'install-db' first.")
        return

    with open(version_file) as f:
        data = json.load(f)

    hosts = data.get("databases", {}).get("host_genomes", {})
    if not hosts:
        click.echo("No host genomes installed.")
        return

    click.echo(f"{'Name':<15} {'Downloaded':<12} {'Format':<10}")
    click.echo("-" * 37)
    for name, meta in sorted(hosts.items()):
        downloaded = meta.get("downloaded_at", "unknown")
        fmt = meta.get("format", "unknown")
        click.echo(f"{name:<15} {downloaded:<12} {fmt:<10}")


# ---------------------------------------------------------------------------
# config: Manage configuration presets
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--list", "list_presets_flag", is_flag=True, default=False, help="List saved presets.")
@click.option("--show", default=None, help="Show details of a preset.")
@click.option("--delete", default=None, help="Delete a preset.")
def config(list_presets_flag, show, delete):
    """Manage configuration presets.

    View, inspect, or delete saved pipeline parameter presets.
    """
    from config_manager import delete_preset, get_preset_details, list_presets

    if delete:
        ok = delete_preset(delete)
        if ok:
            click.echo(f"Preset '{delete}' deleted.")
        else:
            click.echo(f"Preset '{delete}' not found.")
        return

    if show:
        try:
            details = get_preset_details(show)
            click.echo(json.dumps(details, indent=2, ensure_ascii=False))
        except FileNotFoundError:
            click.echo(f"Preset '{show}' not found.")
        return

    # Default: list presets
    presets = list_presets()
    if not presets:
        click.echo("No presets saved. Use the TUI to create presets.")
        return

    click.echo("Saved presets:")
    for name in presets:
        click.echo(f"  - {name}")


# ---------------------------------------------------------------------------
# history: View run history
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--list", "list_flag", is_flag=True, default=False, help="List run history.")
@click.option("--show", default=None, help="Show details of a specific run by ID.")
@click.option("--limit", default=20, type=int, help="Maximum entries to display.")
def history(list_flag, show, limit):
    """View run history.

    Display past pipeline runs with their status, duration, and parameters.
    """
    from history_manager import get_history, get_run

    if show:
        record = get_run(show)
        if record:
            click.echo(json.dumps(record, indent=2, ensure_ascii=False))
        else:
            click.echo(f"Run '{show}' not found.")
        return

    # Default: list history
    records = get_history(limit=limit)
    if not records:
        click.echo("No run history found.")
        return

    click.echo(f"{'Run ID':<20} {'Status':<10} {'Date':<22} {'Duration':<10}")
    click.echo("-" * 62)
    for r in records:
        run_id = r.get("run_id", "?")[:18]
        status = r.get("status", "?")
        recorded = r.get("recorded_at", "?")[:19]
        dur = r.get("duration", 0)
        dur_str = f"{dur:.0f}s" if isinstance(dur, (int, float)) else str(dur)
        click.echo(f"{run_id:<20} {status:<10} {recorded:<22} {dur_str:<10}")


# ---------------------------------------------------------------------------
# db: Database lifecycle management subcommand group
# ---------------------------------------------------------------------------

# @TASK T-DB-LIFECYCLE - CLI db subcommand group
# @SPEC docs/planning/04-database-design.md#DB-갱신-전략


@cli.group()
def db():
    """Database lifecycle management.

    View status, check for updates, update/remove components,
    manage backups, and check disk usage.
    """
    pass


@db.command("status")
@click.option("--db-dir", required=True, type=click.Path(), help="Root database directory.")
def db_status(db_dir):
    """Show DB status with age and freshness info."""
    from db_lifecycle import DBLifecycleManager

    mgr = DBLifecycleManager(Path(db_dir))
    ages = mgr.get_db_ages()

    if not ages:
        click.echo("No databases found. Run 'install-db' first.")
        return

    # Header
    click.echo(
        f"{'Component':<22} {'Version':<16} {'Installed':<12} "
        f"{'Age (days)':<12} {'Status':<10}"
    )
    click.echo("-" * 72)

    for entry in ages:
        click.echo(
            f"{entry['component']:<22} {entry['version']:<16} "
            f"{entry['installed_at']:<12} {entry['age_days']:<12} "
            f"{entry['status']:<10}"
        )


@db.command("check-updates")
@click.option("--db-dir", required=True, type=click.Path(), help="Root database directory.")
def db_check_updates(db_dir):
    """Check which databases may need updating."""
    from db_lifecycle import DBLifecycleManager

    mgr = DBLifecycleManager(Path(db_dir))
    updates = mgr.check_updates_available()

    if not updates:
        click.echo("No databases found.")
        return

    click.echo(f"{'Component':<22} {'Current':<12} {'Age':<8} {'Update?':<10}")
    click.echo("-" * 52)

    for entry in updates:
        rec = "YES" if entry["update_recommended"] else "no"
        click.echo(
            f"{entry['component']:<22} {entry['current']:<12} "
            f"{entry['age_days']:<8} {rec:<10}"
        )


@db.command("update")
@click.option("--db-dir", required=True, type=click.Path(), help="Root database directory.")
@click.option("--component", required=True, help="Component to update.")
@click.option("--no-backup", is_flag=True, default=False, help="Skip backup before update.")
def db_update(db_dir, component, no_backup):
    """Update a specific database component."""
    from db_lifecycle import DBLifecycleManager

    mgr = DBLifecycleManager(Path(db_dir))
    cmd = mgr.update_component(component, backup=not no_backup)

    if not cmd:
        click.echo(f"Unknown component: {component}")
        return

    click.echo(f"Update command for {component}:")
    click.echo(f"  {cmd}")
    click.echo("\nRun this command to perform the update.")


@db.command("remove")
@click.option("--db-dir", required=True, type=click.Path(), help="Root database directory.")
@click.option("--component", required=True, help="Component to remove.")
@click.option("--no-backup", is_flag=True, default=False, help="Skip backup before removal.")
@click.option("--yes", is_flag=True, default=False, help="Skip confirmation prompt.")
def db_remove(db_dir, component, no_backup, yes):
    """Remove a database component."""
    from db_lifecycle import DBLifecycleManager

    if not yes:
        click.confirm(
            f"Remove component '{component}'? This cannot be undone "
            f"{'(no backup)' if no_backup else '(backup will be created)'}.",
            abort=True,
        )

    mgr = DBLifecycleManager(Path(db_dir))
    mgr.remove_component(component, backup=not no_backup)
    click.echo(f"Component '{component}' removed.")


@db.command("cleanup-backups")
@click.option("--db-dir", required=True, type=click.Path(), help="Root database directory.")
@click.option("--max-age-days", default=30, type=int, help="Max backup age in days. Default: 30.")
def db_cleanup_backups(db_dir, max_age_days):
    """Remove old database backups."""
    from db_lifecycle import DBLifecycleManager

    mgr = DBLifecycleManager(Path(db_dir))
    removed = mgr.cleanup_backups(max_age_days=max_age_days)

    if not removed:
        click.echo("No old backups to clean up.")
    else:
        click.echo(f"Removed {len(removed)} old backup(s):")
        for p in removed:
            click.echo(f"  - {p.name}")


@db.command("disk-usage")
@click.option("--db-dir", required=True, type=click.Path(), help="Root database directory.")
def db_disk_usage(db_dir):
    """Show database disk usage."""
    from db_lifecycle import DBLifecycleManager

    mgr = DBLifecycleManager(Path(db_dir))
    usage = mgr.get_disk_usage()

    click.echo(f"Total: {usage['total_gb']:.2f} GB")
    click.echo(f"Backups: {usage['backups_gb']:.2f} GB")
    click.echo()
    click.echo(f"{'Component':<25} {'Size (GB)':<12}")
    click.echo("-" * 37)

    for comp, size in sorted(usage["per_component"].items()):
        click.echo(f"{comp:<25} {size:.4f}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
