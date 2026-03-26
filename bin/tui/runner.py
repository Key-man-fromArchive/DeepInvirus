# @TASK T8.2, T-RAMDISK - NextflowRunner 구현 (RAM disk support)
# @SPEC docs/planning/06-tasks-tui.md#phase-8-t82-실시간-진행-표시-redgreen
# @TEST tests/tui/test_runner.py
"""
Nextflow process runner and monitor for DeepInvirus TUI.

Manages the lifecycle of a Nextflow pipeline execution:
  - Building the CLI command from parameter dict
  - Launching the process asynchronously via asyncio
  - Parsing stdout/stderr for progress updates
  - Cancelling a running process
  - RAM disk work directory support (use_ramdisk / work_dir params)

Key log patterns matched by parse_progress():
  - Process step:  "[ab/cd1234] process > STEP_NAME (sample)"
  - Steps done:    "N of M steps (XX%) done"
"""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

from ramdisk_manager import RamdiskManager

# ---------------------------------------------------------------------------
# Regex patterns for Nextflow log parsing
# ---------------------------------------------------------------------------

# Matches: [ab/cd1234] process > STEP_NAME (sample1)
_RE_PROCESS = re.compile(
    r"\[[0-9a-f]{2}/[0-9a-f]+\]\s+process\s+>\s+(\w+)"
)

# Matches: 5 of 14 steps (36%) done
_RE_STEPS_DONE = re.compile(
    r"(\d+)\s+of\s+(\d+)\s+steps?\s+\(\d+%\)\s+done"
)


class NextflowRunner:
    """Nextflow process runner and real-time progress monitor.

    Usage::

        runner = NextflowRunner(work_dir=Path("/project"))
        await runner.start(params)   # launches nextflow subprocess
        # ... poll runner.steps_completed / runner.current_step
        await runner.cancel()        # terminate if needed

    Attributes:
        process: The asyncio subprocess, or None if not started.
        work_dir: Working directory for the Nextflow process.
        is_running: Whether the pipeline subprocess is currently active.
        current_step: Name of the currently executing pipeline step.
        steps_completed: Number of completed steps.
        steps_total: Total number of pipeline steps.
        start_time: Epoch timestamp when the run was started.
    """

    def __init__(self, work_dir: Path) -> None:
        self.process: asyncio.subprocess.Process | None = None
        self.work_dir: Path = work_dir
        self.is_running: bool = False
        self.current_step: str = ""
        self.steps_completed: int = 0
        self.steps_total: int = 0
        self.start_time: float = 0
        self._log_lines: list[str] = []
        self._use_ramdisk: bool = False
        self._ramdisk_manager: RamdiskManager | None = None

    # ------------------------------------------------------------------
    # Command building
    # ------------------------------------------------------------------

    def build_command(self, params: dict, resume: bool = False) -> list[str]:
        """Convert a pipeline parameter dict into a Nextflow CLI argument list.

        The generated command has the form::

            nextflow run main.nf --reads X --host Y --assembler Z ...

        Boolean flags (``skip_ml``) are only included when *True*.
        Numeric values (``threads``) are forwarded as
        ``-process.cpus`` for Nextflow's executor.

        Args:
            params: Pipeline parameters as returned by
                :meth:`RunScreen.get_params`.
            resume: If True, append ``-resume`` to enable Nextflow
                cache-based resume from the last successful step.

        Returns:
            list[str]: Command tokens suitable for
                ``asyncio.create_subprocess_exec(*cmd)``.
        """
        cmd: list[str] = [
            "nextflow",
            "run",
            str(self.work_dir / "main.nf"),
        ]

        # Pipeline-level parameters (--key value)
        for key in ("reads", "host", "assembler", "search", "outdir"):
            if key in params and params[key]:
                cmd.extend([f"--{key}", str(params[key])])

        # Optional database path parameters
        for key in ("checkv_db", "exclusion_db"):
            if params.get(key):
                cmd.extend([f"--{key}", str(params[key])])

        # Boolean flag: only emit when True
        if params.get("skip_ml"):
            cmd.append("--skip_ml")

        # Threads → Nextflow process.cpus
        threads = params.get("threads")
        if threads:
            cmd.extend(["-process.cpus", str(threads)])

        # @TASK T-RAMDISK - RAM disk or custom work directory
        if params.get("use_ramdisk"):
            ramdisk = RamdiskManager()
            nf_work = ramdisk.create()
            cmd.extend(["-w", str(nf_work)])
            self._use_ramdisk = True
            self._ramdisk_manager = ramdisk
        elif params.get("work_dir"):
            cmd.extend(["-w", str(params["work_dir"])])

        # Resume from last cached step
        if resume:
            cmd.append("-resume")

        return cmd

    # ------------------------------------------------------------------
    # Progress parsing
    # ------------------------------------------------------------------

    def parse_progress(self, line: str) -> tuple[int, int, str]:
        """Parse a Nextflow log line for progress information.

        Two patterns are recognised:

        1. **Process step** —
           ``[ab/cd1234] process > STEP_NAME (sample)``
           Updates ``current_step`` only; completed/total are taken
           from the runner's current state.

        2. **Steps done** —
           ``N of M steps (XX%) done``
           Updates ``steps_completed`` and ``steps_total``.

        Unrecognised lines return ``(0, 0, "")``.

        Args:
            line: A single log line from Nextflow stdout/stderr.

        Returns:
            Tuple of (completed, total, step_name).
        """
        # Try "N of M steps" pattern first
        m_steps = _RE_STEPS_DONE.search(line)
        if m_steps:
            completed = int(m_steps.group(1))
            total = int(m_steps.group(2))
            self.steps_completed = completed
            self.steps_total = total
            return (completed, total, "")

        # Try process step pattern
        m_proc = _RE_PROCESS.search(line)
        if m_proc:
            step_name = m_proc.group(1)
            self.current_step = step_name
            return (self.steps_completed, self.steps_total, step_name)

        # Unrecognised
        return (0, 0, "")

    # ------------------------------------------------------------------
    # Async lifecycle
    # ------------------------------------------------------------------

    def _get_work_dir(self, params: dict) -> Path:
        """Return the Nextflow work/ directory path for a given run.

        Priority:
          1. use_ramdisk → /dev/shm/deepinvirus_work
          2. work_dir param → custom path
          3. default → <project_root>/work

        Args:
            params: Pipeline parameters dict.

        Returns:
            Path to the Nextflow work directory.
        """
        if params.get("use_ramdisk"):
            return RamdiskManager.DEFAULT_MOUNT
        if params.get("work_dir"):
            return Path(params["work_dir"])
        return self.work_dir / "work"

    async def start(self, params: dict, resume: bool = False) -> None:
        """Launch the Nextflow pipeline as an async subprocess.

        Builds the command via :meth:`build_command`, then spawns it
        with ``asyncio.create_subprocess_exec``.  Stdout and stderr
        are captured via pipes for real-time log parsing.

        Args:
            params: Pipeline parameters dict.
            resume: If True, pass ``-resume`` to Nextflow.
        """
        cmd = self.build_command(params, resume=resume)
        self.start_time = time.time()
        self.is_running = True
        self.steps_completed = 0
        self.steps_total = 0
        self.current_step = ""
        self._log_lines = []

        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.work_dir),
        )

    async def read_output(self, on_line=None) -> None:
        """Read stdout/stderr lines and parse progress.

        This coroutine reads lines from both stdout and stderr of the
        running Nextflow process.  Each line is parsed for progress
        updates and optionally forwarded to a callback.

        Args:
            on_line: Optional callback ``(line: str) -> None`` invoked
                for every log line (used to feed :class:`LogViewer`).
        """
        if self.process is None:
            return

        async def _read_stream(stream):
            while True:
                raw = await stream.readline()
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").rstrip()
                self._log_lines.append(line)
                self.parse_progress(line)
                if on_line:
                    on_line(line)

        tasks = []
        if self.process.stdout:
            tasks.append(_read_stream(self.process.stdout))
        if self.process.stderr:
            tasks.append(_read_stream(self.process.stderr))

        if tasks:
            await asyncio.gather(*tasks)

        await self.process.wait()
        self.is_running = False

        # @TASK T-RAMDISK - Cleanup RAM disk after pipeline completion
        if self._use_ramdisk and self._ramdisk_manager is not None:
            self._ramdisk_manager.cleanup()
            self._use_ramdisk = False

    async def cancel(self) -> None:
        """Terminate the running Nextflow process.

        Sends SIGTERM first; if the process does not exit within 5
        seconds, SIGKILL is sent.
        """
        if self.process is None:
            return

        try:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
        except ProcessLookupError:
            pass
        finally:
            self.is_running = False
            # @TASK T-RAMDISK - Cleanup RAM disk on cancel
            if self._use_ramdisk and self._ramdisk_manager is not None:
                self._ramdisk_manager.cleanup()
                self._use_ramdisk = False

    # ------------------------------------------------------------------
    # Elapsed time
    # ------------------------------------------------------------------

    def get_elapsed(self) -> float:
        """Return elapsed wall-clock seconds since :meth:`start`.

        Returns:
            float: Seconds elapsed, or 0.0 if not started.
        """
        if self.start_time == 0:
            return 0.0
        return time.time() - self.start_time
