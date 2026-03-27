#!/usr/bin/env python3
"""Interactive first-time setup wizard for DeepInvirus."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from add_host import add_host
from install_databases import (
    APP_CONFIG_FILE,
    DB_SOURCES,
    INSTALLERS,
    VALID_HOSTS,
    VERSION_KEYS,
    _load_version,
    _now_iso,
    _resolve_components,
    _save_db_config,
    _save_version,
    download_contaminants,
    estimate_disk_usage,
    save_app_config,
    verify_database,
)

DEFAULT_DB_DIR = Path.home() / "Database" / "DeepInvirus"


def _prompt(text: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{text}{suffix}: ").strip()
    return value or (default or "")


def _confirm(text: str, default: bool = True) -> bool:
    default_label = "Y/n" if default else "y/N"
    while True:
        value = input(f"{text} [{default_label}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please answer y or n.")


def _check_java() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["java", "-version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, "missing"

    output = result.stderr or result.stdout
    version = "unknown"
    if '"' in output:
        version = output.split('"')[1]
    major = version.split(".", 1)[0]
    if major == "1":
        major = version.split(".")[1]
    try:
        ok = int(major) >= 17
    except ValueError:
        ok = False
    return ok, version


def _system_requirements(db_dir: Path, required_gb: float) -> list[str]:
    messages: list[str] = []
    tools = {
        "docker": shutil.which("docker") is not None,
        "nextflow": shutil.which("nextflow") is not None,
        "mmseqs": shutil.which("mmseqs") is not None,
        "diamond": shutil.which("diamond") is not None,
    }
    for name, ok in tools.items():
        messages.append(f"{name:<10} {'OK' if ok else 'MISSING'}")

    java_ok, java_version = _check_java()
    messages.append(f"{'java':<10} {'OK' if java_ok else 'MISSING'} ({java_version})")

    target = db_dir.expanduser()
    probe = target if target.exists() else target.parent
    disk = shutil.disk_usage(probe)
    free_gb = disk.free / (1024 ** 3)
    enough = free_gb >= required_gb
    messages.append(f"{'disk':<10} {'OK' if enough else 'LOW'} ({free_gb:.1f} GB free)")
    return messages


def _component_plan(minimal: bool) -> list[str]:
    return _resolve_components("all", minimal=minimal)


def _print_component_summary(components: list[str]) -> None:
    print("\nPlanned databases:")
    for component in components:
        info = {
            "protein": DB_SOURCES["viral_protein"],
            "nucleotide": DB_SOURCES["viral_nucleotide"],
            "genomad": DB_SOURCES["genomad_db"],
            "taxonomy": DB_SOURCES["taxonomy"],
            "exclusion": DB_SOURCES["exclusion_db"],
            "checkv": DB_SOURCES["checkv_db"],
            "uniref50": DB_SOURCES["uniref50"],
            "uniref90_viral": DB_SOURCES["uniref90_viral"],
            "polymicrobial": DB_SOURCES["polymicrobial_nt"],
            "accession2taxid": DB_SOURCES["nucl_gb_accession2taxid"],
            "host": DB_SOURCES["host"],
        }[component]
        size = info.get("size_gb", 3.0)
        print(f"  - {component:<16} ~{size} GB")


def _write_wizard_state(db_dir: Path, selected_host: str | None, minimal: bool) -> None:
    state_path = db_dir / "setup_wizard.json"
    payload = {
        "db_dir": str(db_dir),
        "host": selected_host,
        "minimal": minimal,
        "updated_at": _now_iso(),
    }
    with open(state_path, "w") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def _configure_host(db_dir: Path, threads: int) -> str | None:
    if not _confirm("Configure a host genome now?", default=False):
        return None

    choice = _prompt("Choose host mode (download/custom/skip)", "download").lower()
    if choice == "skip":
        return None
    if choice == "download":
        host = _prompt(f"Host name ({', '.join(VALID_HOSTS)})", "human")
        if host not in VALID_HOSTS:
            print(f"Unknown host '{host}', skipping host setup.")
            return None
        return host
    if choice == "custom":
        name = _prompt("Custom host name", "custom")
        fasta = Path(_prompt("Path to FASTA file"))
        if not fasta.exists():
            print(f"FASTA not found: {fasta}")
            return None
        print(f"Adding custom host '{name}' from {fasta}")
        add_host(name=name, fasta=fasta, db_dir=db_dir, threads=threads)
        return name

    print("Unknown choice, skipping host setup.")
    return None


def run_wizard(
    *,
    db_dir: Path,
    minimal: bool = False,
    api_key: str | None = None,
    threads: int = 4,
) -> int:
    components = _component_plan(minimal)
    required_gb = estimate_disk_usage([component for component in components if component != "host"])

    print("DeepInvirus setup wizard\n")
    print("This will check your environment, download reference databases,")
    print("write the default DB config, and leave a suggested test command.\n")

    print("System requirements:")
    for line in _system_requirements(db_dir, required_gb):
        print(f"  {line}")

    selected_dir = Path(_prompt("Database directory", str(db_dir))).expanduser()
    selected_dir.mkdir(parents=True, exist_ok=True)

    components = _component_plan(minimal)
    _print_component_summary([component for component in components if component != "host"])
    print(f"\nEstimated required space: ~{required_gb:.1f} GB")
    if not _confirm("Continue with these database components?"):
        print("Setup cancelled.")
        return 1

    selected_host = _configure_host(selected_dir, threads)
    version_data = _load_version(selected_dir)

    failures: list[str] = []
    for component in components:
        if component == "host":
            if not selected_host:
                continue
            ok, _ = verify_database(selected_dir, "host", host=selected_host)
            if ok and _confirm(f"Host genome '{selected_host}' already exists. Skip?", default=True):
                continue
            print(f"\n[host] Installing host genome '{selected_host}'")
            try:
                from install_databases import download_host_genome

                meta = download_host_genome(
                    selected_dir,
                    host=selected_host,
                    threads=threads,
                    dry_run=False,
                    api_key=api_key,
                )
                version_data["databases"].setdefault("host_genomes", {})[selected_host] = meta
            except RuntimeError as exc:
                print(f"  Failed: {exc}")
                failures.append(f"host: {exc}")
                if not _confirm("Continue with the remaining steps?", default=False):
                    break
            continue

        ok, _ = verify_database(selected_dir, component, host=selected_host or "human")
        if ok and _confirm(f"{component} is already present. Skip re-installation?", default=True):
            print(f"  Skipping {component}")
            continue

        installer = INSTALLERS[component]
        print(f"\n[{component}] {installer.__name__}")
        try:
            meta = installer(
                selected_dir,
                threads=threads,
                dry_run=False,
                api_key=api_key,
            )  # type: ignore[misc]
            version_data["databases"][VERSION_KEYS[component]] = meta
            check_ok, msg = verify_database(selected_dir, component, host=selected_host or "human")
            print(f"  Verify: {'OK' if check_ok else 'FAILED'} ({msg})")
        except RuntimeError as exc:
            print(f"  Failed: {exc}")
            failures.append(f"{component}: {exc}")
            if not _confirm("Continue with the remaining steps?", default=False):
                break

    download_contaminants(selected_dir, dry_run=False)
    _save_db_config(selected_dir, version_data, dry_run=False)
    _save_version(selected_dir, version_data)
    save_app_config(selected_dir)
    _write_wizard_state(selected_dir, selected_host, minimal)

    print(f"\nConfig file written: {APP_CONFIG_FILE}")
    print(f"Database root: {selected_dir}")

    print("\nVerification summary:")
    for component in components:
        if component == "host" and not selected_host:
            continue
        host_name = selected_host or "human"
        ok, msg = verify_database(selected_dir, component, host=host_name)
        print(f"  {component:<16} {'OK' if ok else 'MISSING'} ({msg})")

    if failures:
        print("\nSetup completed with failures:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nSuggested test run:")
    print(f"  deepinvirus run --reads ./test_input --db-dir {selected_dir} --host none --outdir ./test_run")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive DeepInvirus setup wizard.")
    parser.add_argument("--minimal", action="store_true", default=False)
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    parser.add_argument("--api-key", default=None, help="NCBI API key for faster downloads.")
    parser.add_argument("--threads", type=int, default=4)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = run_wizard(
            db_dir=args.db_dir,
            minimal=args.minimal,
            api_key=args.api_key,
            threads=args.threads,
        )
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
