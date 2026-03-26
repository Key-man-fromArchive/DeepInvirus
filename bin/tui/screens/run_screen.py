# @TASK T8.1, T8.2 - Run 파라미터 입력 폼 + 실시간 진행 표시
# @SPEC docs/planning/06-tasks-tui.md#phase-8-t81-파라미터-입력-폼-redgreen
# @SPEC docs/planning/06-tasks-tui.md#phase-8-t82-실시간-진행-표시-redgreen
# @SPEC docs/planning/02-trd.md#31-입력-input
# @TEST tests/tui/test_run_screen.py
"""
Run Analysis screen — parameter input form + real-time progress.

Provides all pipeline parameters defined in 02-trd.md S3.1:

  reads      - FASTQ file or directory path
  host       - host genome for removal (human/mouse/insect/none + custom)
  assembler  - megahit | metaspades  (RadioSet)
  search     - fast | sensitive      (RadioSet)
  skip_ml    - geNomad on/off        (Checkbox, default ON)
  outdir     - output directory      (Input, default ./results)
  threads    - parallel threads      (Input, default os.cpu_count())

Validation:
  - reads path must exist on the filesystem
  - threads must be a positive integer

Navigation:
  [Start Analysis]  → launches NextflowRunner, shows progress (T8.2)
  [Cancel]          → terminates the running pipeline
  [Back]            → pops current screen

On completion, records the run in history_manager and transitions
to ResultScreen (T8.3).
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Select,
    Static,
)

from ramdisk_manager import RamdiskManager
from tui.runner import NextflowRunner
from tui.screens.result_screen import ResultScreen, format_duration
from tui.widgets.log_viewer import LogViewer
from tui.widgets.progress import ProgressWidget

# ---------------------------------------------------------------------------
# Host genome options (dynamic loading from DB)
# ---------------------------------------------------------------------------


def _load_host_options(db_dir: Path | None = None) -> list[tuple[str, str]]:
    """Load available host genomes from the database directory.

    Scans databases/host_genomes/ for registered hosts and returns
    a list of (display_label, dbname) tuples for use in checkboxes.

    Args:
        db_dir: Root database directory. If None, uses 'databases'.

    Returns:
        List of (label, dbname) tuples. Always includes "None" option.
    """
    import json

    options: list[tuple[str, str]] = []
    host_base = (db_dir or Path("databases")) / "host_genomes"

    if host_base.is_dir():
        for entry in sorted(host_base.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            info_path = entry / "info.json"
            if info_path.exists():
                try:
                    info = json.loads(info_path.read_text())
                    dbname = info.get("dbname", entry.name)
                    species = info.get("species", "Unknown")
                    options.append((f"{dbname} ({species})", dbname))
                except (json.JSONDecodeError, OSError):
                    options.append((entry.name, entry.name))
            else:
                options.append((entry.name, entry.name))

    # Fallback: include common built-in options if nothing found
    if not options:
        options = [
            ("human (Homo sapiens)", "human"),
            ("mouse (Mus musculus)", "mouse"),
        ]

    return options


# Legacy static options (used when DB scanning is not available)
_HOST_OPTIONS: list[tuple[str, str]] = [
    ("Human (Homo sapiens)", "human"),
    ("Mouse (Mus musculus)", "mouse"),
    ("Insect (Tenebrio molitor)", "insect"),
    ("None (no host removal)", "none"),
]

# ---------------------------------------------------------------------------
# RunScreen
# ---------------------------------------------------------------------------


class RunScreen(Screen):
    """Run Analysis parameter form screen.

    Layout (vertical scroll):
    ┌─ Run Analysis ─────────────────────────────────────────────┐
    │  Reads path    : [input-reads          ]                   │
    │  Host genome   : [select-host          ▼]                  │
    │  Assembler     : (●) megahit  ( ) metaspades               │
    │  Search mode   : (●) fast     ( ) sensitive                │
    │  ML detection  : [x] Enable geNomad (default: on)          │
    │  Output dir    : [input-outdir         ]                   │
    │  Threads       : [input-threads        ]                   │
    │                                                            │
    │                         [Back]  [Start Analysis]           │
    └────────────────────────────────────────────────────────────┘
    """

    # ------------------------------------------------------------------
    # Message: emitted when the user clicks [Start Analysis]
    # ------------------------------------------------------------------

    class RunRequested(Message):
        """Emitted by RunScreen when [Start Analysis] is pressed.

        Attributes:
            params: Validated pipeline parameter dict.
        """

        def __init__(self, params: dict) -> None:
            super().__init__()
            self.params = params

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Build the parameter form layout."""
        default_threads = str(os.cpu_count() or 1)

        # Load dynamic host options from DB
        host_options = _load_host_options()

        with ScrollableContainer():
            yield Static(" Run Analysis", classes="section-title")

            with Vertical(classes="form-container"):
                # ---- Reads path ----------------------------------------
                yield Label("Reads path", classes="form-label")
                yield Input(
                    placeholder="Directory or FASTQ file path…",
                    id="input-reads",
                    classes="form-field",
                )
                yield Static("", id="error-reads", classes="text-error")

                # ---- Host genome (multi-select checkboxes) ---------------
                # @TASK T-MULTI-HOST - Checkbox-based multi-host selection
                yield Label("Host genome(s)", classes="form-label")
                yield Static(
                    "Select one or more hosts (uncheck all for no host removal):",
                    classes="form-hint",
                )
                with Vertical(id="host-checkboxes", classes="form-field"):
                    for label, dbname in host_options:
                        yield Checkbox(
                            label,
                            value=False,
                            id=f"host-cb-{dbname}",
                            classes="host-checkbox",
                        )

                # ---- Assembler -----------------------------------------
                yield Label("Assembler", classes="form-label")
                with RadioSet(id="radioset-assembler", classes="form-field"):
                    yield RadioButton("megahit", value=True)
                    yield RadioButton("metaspades")

                # ---- Search mode ---------------------------------------
                yield Label("Search mode", classes="form-label")
                with RadioSet(id="radioset-search", classes="form-field"):
                    yield RadioButton("fast", value=True)
                    yield RadioButton("sensitive")

                # ---- ML detection (geNomad) ----------------------------
                yield Label("ML detection", classes="form-label")
                yield Checkbox(
                    "Enable geNomad (ML-based virus detection)",
                    value=True,
                    id="checkbox-ml",
                    classes="form-field",
                )

                # ---- RAM disk (T-RAMDISK) ------------------------------
                # @TASK T-RAMDISK - RAM disk checkbox for I/O speedup
                yield Label("Work directory", classes="form-label")
                yield Checkbox(
                    "Use RAM disk (recommended for NFS data)",
                    value=False,
                    id="checkbox-ramdisk",
                    classes="form-field",
                )
                yield Static("", id="ramdisk-info", classes="form-hint")

                # ---- CheckV database (optional) -----------------------
                yield Label("CheckV database (optional)", classes="form-label")
                yield Input(
                    placeholder="Path to CheckV DB (leave empty to skip)",
                    id="input-checkv-db",
                    classes="form-field",
                )

                # ---- Exclusion database (optional) --------------------
                yield Label("Exclusion database (optional)", classes="form-label")
                yield Input(
                    placeholder="Path to SwissProt Diamond DB for non-viral exclusion",
                    id="input-exclusion-db",
                    classes="form-field",
                )

                # ---- Output directory ----------------------------------
                yield Label("Output directory", classes="form-label")
                yield Input(
                    placeholder="./results",
                    value="./results",
                    id="input-outdir",
                    classes="form-field",
                )
                yield Static("", id="error-outdir", classes="text-error")

                # ---- Threads -------------------------------------------
                yield Label("Threads", classes="form-label")
                yield Input(
                    placeholder=default_threads,
                    value=default_threads,
                    id="input-threads",
                    classes="form-field",
                )
                yield Static("", id="error-threads", classes="text-error")

                # ---- Action buttons ------------------------------------
                with Vertical(classes="button-row"):
                    yield Button(
                        "Back",
                        id="btn-back",
                        classes="secondary",
                    )
                    yield Button(
                        "Start Analysis",
                        id="btn-start",
                        classes="primary",
                    )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Update RAM disk info label on screen mount."""
        self._update_ramdisk_info()

    def _update_ramdisk_info(self) -> None:
        """Refresh the RAM disk availability/status label."""
        try:
            info_label = self.query_one("#ramdisk-info", Static)
            mgr = RamdiskManager()
            if mgr.is_available():
                avail = mgr.get_available_ram_gb()
                rec = mgr.get_recommended_size_gb()
                info_label.update(
                    f"Available: {avail} GB / Recommended: {rec} GB"
                )
            else:
                info_label.update("/dev/shm not available on this system")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_params(self) -> dict:
        """Return the current form values as a pipeline parameter dict.

        Mirrors the Nextflow params block from 02-trd.md §3.1::

            params {
                reads     = null
                host      = 'human'
                outdir    = './results'
                assembler = 'megahit'
                search    = 'sensitive'
                skip_ml   = false
                db_dir    = null
            }

        Returns:
            dict with keys: reads, host, assembler, search,
                            skip_ml, outdir, threads.
        """
        reads_val = self.query_one("#input-reads", Input).value.strip()

        # Collect selected host dbnames from checkboxes
        # @TASK T-MULTI-HOST - Read multi-host checkbox selections
        selected_hosts = []
        try:
            host_container = self.query_one("#host-checkboxes")
            for cb in host_container.query(Checkbox):
                if cb.value and cb.id and cb.id.startswith("host-cb-"):
                    dbname = cb.id.replace("host-cb-", "")
                    selected_hosts.append(dbname)
        except Exception:
            pass

        host_val = ",".join(selected_hosts) if selected_hosts else "none"

        assembler_widget = self.query_one("#radioset-assembler", RadioSet)
        assembler_val = (
            str(assembler_widget.pressed_button.label)
            if assembler_widget.pressed_button
            else "megahit"
        )

        search_widget = self.query_one("#radioset-search", RadioSet)
        search_val = (
            str(search_widget.pressed_button.label)
            if search_widget.pressed_button
            else "fast"
        )

        ml_val = self.query_one("#checkbox-ml", Checkbox).value
        outdir_val = self.query_one("#input-outdir", Input).value.strip() or "./results"
        threads_raw = self.query_one("#input-threads", Input).value.strip()

        try:
            threads_val = int(threads_raw)
        except (ValueError, TypeError):
            threads_val = os.cpu_count() or 1

        # @TASK T-RAMDISK - Read RAM disk checkbox state
        use_ramdisk = False
        try:
            use_ramdisk = self.query_one("#checkbox-ramdisk", Checkbox).value
        except Exception:
            pass

        # Optional database paths
        checkv_db_val = ""
        try:
            checkv_db_val = self.query_one("#input-checkv-db", Input).value.strip()
        except Exception:
            pass

        exclusion_db_val = ""
        try:
            exclusion_db_val = self.query_one("#input-exclusion-db", Input).value.strip()
        except Exception:
            pass

        params = {
            "reads": reads_val,
            "host": host_val,
            "assembler": assembler_val,
            "search": search_val,
            "skip_ml": not ml_val,   # Nextflow param: skip_ml=false means ML ON
            "outdir": outdir_val,
            "threads": threads_val,
            "use_ramdisk": use_ramdisk,
        }

        # Only include optional DB paths when provided
        if checkv_db_val:
            params["checkv_db"] = checkv_db_val
        if exclusion_db_val:
            params["exclusion_db"] = exclusion_db_val

        return params

    def validate_params(self) -> list[str]:
        """Validate current form inputs.

        Checks:
          1. reads path is not empty and exists on the filesystem.
          2. threads is a positive integer.

        Returns:
            list[str]: List of human-readable error messages.
                       Empty list means validation passed.
        """
        errors: list[str] = []

        # ---- reads path validation ----
        reads_val = self.query_one("#input-reads", Input).value.strip()
        if not reads_val:
            errors.append("Reads path is required.")
        elif not Path(reads_val).exists():
            errors.append(f"Reads path does not exist: {reads_val}")

        # ---- threads validation (positive integer) ----
        threads_raw = self.query_one("#input-threads", Input).value.strip()
        try:
            threads_int = int(threads_raw)
            if threads_int <= 0:
                errors.append("Threads must be a positive integer (> 0).")
        except (ValueError, TypeError):
            errors.append(f"Threads must be a valid integer, got: '{threads_raw}'")

        return errors

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        - btn-back  → pop screen
        - btn-start → validate, then post RunRequested or show errors
        """
        btn_id = event.button.id

        if btn_id == "btn-back":
            self.app.pop_screen()
            return

        if btn_id == "btn-start":
            self._clear_errors()
            errors = self.validate_params()

            if errors:
                self._display_errors(errors)
            else:
                params = self.get_params()
                self.post_message(self.RunRequested(params))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _clear_errors(self) -> None:
        """Clear all error message labels."""
        for error_id in ("error-reads", "error-outdir", "error-threads"):
            try:
                self.query_one(f"#{error_id}", Static).update("")
            except Exception:
                pass

    def _display_errors(self, errors: list[str]) -> None:
        """Display validation errors via notifications and inline labels.

        Inline labels are updated for field-specific errors;
        a summary notification is also shown.
        """
        reads_val = self.query_one("#input-reads", Input).value.strip()

        for error in errors:
            if "Reads" in error or "reads" in error:
                try:
                    self.query_one("#error-reads", Static).update(error)
                except Exception:
                    pass
            elif "hread" in error:  # Threads
                try:
                    self.query_one("#error-threads", Static).update(error)
                except Exception:
                    pass

        # Summary notification
        summary = "; ".join(errors)
        self.app.notify(
            summary,
            title="Validation Error",
            severity="error",
            timeout=6,
        )

    # ------------------------------------------------------------------
    # T8.2: Pipeline execution with real-time progress
    # ------------------------------------------------------------------

    async def _run_pipeline(self, params: dict, resume: bool = False) -> None:
        """Launch NextflowRunner and stream progress to widgets.

        This coroutine:
        1. Creates a NextflowRunner pointed at the project root.
        2. Starts the Nextflow subprocess (with optional -resume).
        3. Reads output lines, forwarding to LogViewer and ProgressWidget.
        4. On completion, records the run in history and pushes ResultScreen.

        Args:
            params: Validated pipeline parameter dict.
            resume: If True, pass -resume to Nextflow for cache-based resume.
        """
        # Resolve project root (one level up from bin/)
        project_root = Path(__file__).resolve().parents[2]
        runner = NextflowRunner(work_dir=project_root)

        # Record run as 'running' before starting
        run_id = str(uuid.uuid4())[:8]
        try:
            import history_manager

            history_manager.record_run(
                run_id=run_id,
                params=params,
                status="running",
                duration=0,
                output_dir=params.get("outdir", "./results"),
                summary={},
                work_dir=str(runner._get_work_dir(params)),
            )
        except Exception:
            pass

        try:
            await runner.start(params, resume=resume)
        except Exception as exc:
            self.app.notify(
                f"Failed to start pipeline: {exc}",
                title="Launch Error",
                severity="error",
            )
            return

        # Set up a periodic timer to refresh the progress widget
        async def _update_progress():
            while runner.is_running:
                elapsed_str = format_duration(runner.get_elapsed())
                try:
                    pw = self.query_one(ProgressWidget)
                    pw.update(
                        current=runner.steps_completed,
                        total=runner.steps_total,
                        step_name=runner.current_step,
                        elapsed=elapsed_str,
                    )
                except Exception:
                    pass
                await asyncio.sleep(1)

        def _on_line(line: str) -> None:
            try:
                lv = self.query_one(LogViewer)
                lv.append_log(line)
            except Exception:
                pass

        # Run output reading and progress updates concurrently
        await asyncio.gather(
            runner.read_output(on_line=_on_line),
            _update_progress(),
        )

        # Pipeline finished -- determine status
        status = "completed" if runner.process and runner.process.returncode == 0 else "failed"
        duration = runner.get_elapsed()

        # Update the existing history record with final status
        try:
            import history_manager

            history_manager.update_run_status(
                run_id,
                status=status,
                duration=duration,
            )
        except Exception:
            pass

        # Transition to result screen
        if status == "done":
            result_screen = ResultScreen(
                output_dir=params.get("outdir", "./results"),
                duration=duration,
            )
            self.app.push_screen(result_screen)
        else:
            self.app.notify(
                "Pipeline failed. Check logs for details.",
                title="Pipeline Failed",
                severity="error",
                timeout=10,
            )
