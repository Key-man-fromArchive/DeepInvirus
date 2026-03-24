# @TASK T12.1 - Process resource manager for DeepInvirus
# @SPEC docs/planning/06-tasks-tui.md#process-resources
# @TEST tests/tui/test_resource_screen.py
"""
Process resource manager for DeepInvirus.

Reads and writes conf/base.config to manage per-process CPU/memory settings.
Parses Nextflow-style configuration blocks using regex, and rewrites only
the numeric values when modifications are requested.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Size-label names that should be excluded from per-process listings.
# These are generic resource tiers, not individual pipeline processes.
_SIZE_LABELS = frozenset({"low", "medium", "high", "high_memory"})

# Regex to match a withLabel block header:
#   withLabel: process_<name> {
_LABEL_RE = re.compile(
    r"withLabel:\s*process_(\w+)\s*\{",
)

# Regex to extract CPU value from a check_max call:
#   cpus = { check_max( 32, 'cpus' ) }
_CPUS_RE = re.compile(
    r"cpus\s*=\s*\{\s*check_max\(\s*(\d+)",
)

# Regex to extract memory GB value:
#   memory = { check_max( 128.GB, 'memory' ) }
_MEMORY_RE = re.compile(
    r"memory\s*=\s*\{\s*check_max\(\s*(\d+)\.GB",
)


class ResourceManager:
    """Manage per-process resource settings in conf/base.config.

    Args:
        base_config_path: Absolute path to the base.config file.
    """

    def __init__(self, base_config_path: Path) -> None:
        self._path = Path(base_config_path)
        self._text = self._path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API — read
    # ------------------------------------------------------------------

    def get_all_resources(self) -> list[dict]:
        """Return resource settings for all named processes.

        Returns:
            A list of dicts, each with keys: process, cpus, memory_gb.
            Generic size labels (low/medium/high/high_memory) are excluded.
        """
        results: list[dict] = []
        for name, block in self._iter_process_blocks():
            if name in _SIZE_LABELS:
                continue
            cpus = self._parse_cpus(block)
            mem = self._parse_memory(block)
            if cpus is not None and mem is not None:
                results.append({
                    "process": name,
                    "cpus": cpus,
                    "memory_gb": mem,
                })
        return results

    def get_resource(self, process_name: str) -> dict:
        """Return resource settings for a single process.

        Args:
            process_name: The process label name (e.g. "bbduk").

        Returns:
            Dict with keys: process, cpus, memory_gb.

        Raises:
            KeyError: If the process is not found in base.config.
        """
        for name, block in self._iter_process_blocks():
            if name == process_name:
                cpus = self._parse_cpus(block)
                mem = self._parse_memory(block)
                if cpus is not None and mem is not None:
                    return {
                        "process": name,
                        "cpus": cpus,
                        "memory_gb": mem,
                    }
        raise KeyError(f"Process not found: {process_name}")

    def get_system_info(self) -> dict:
        """Return actual system resources (CPU count and total RAM in GB).

        Returns:
            Dict with keys: cpus, memory_gb.
        """
        cpus = os.cpu_count() or 1
        memory_gb = self._read_system_memory_gb()
        return {"cpus": cpus, "memory_gb": memory_gb}

    # ------------------------------------------------------------------
    # Public API — write
    # ------------------------------------------------------------------

    def set_resource(
        self,
        process_name: str,
        cpus: int | None = None,
        memory_gb: int | None = None,
    ) -> None:
        """Modify resource settings for a specific process and save.

        Args:
            process_name: The process label name (e.g. "bbduk").
            cpus: New CPU count (or None to leave unchanged).
            memory_gb: New memory in GB (or None to leave unchanged).

        Raises:
            KeyError: If the process is not found in base.config.
        """
        if cpus is None and memory_gb is None:
            return

        # Verify the process exists
        block_span = self._find_block_span(process_name)
        if block_span is None:
            raise KeyError(f"Process not found: {process_name}")

        start, end = block_span
        block_text = self._text[start:end]

        if cpus is not None:
            block_text = _CPUS_RE.sub(
                lambda m: f"cpus   = {{ check_max( {cpus}",
                block_text,
                count=1,
            )

        if memory_gb is not None:
            block_text = _MEMORY_RE.sub(
                lambda m: f"memory = {{ check_max( {memory_gb}.GB",
                block_text,
                count=1,
            )

        self._text = self._text[:start] + block_text + self._text[end:]
        self._path.write_text(self._text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_process_blocks(self):
        """Yield (name, block_text) for each withLabel: process_<name> block."""
        for match in _LABEL_RE.finditer(self._text):
            name = match.group(1)
            # Find the matching closing brace
            block_start = match.start()
            brace_start = match.end() - 1  # points to '{'
            block_end = self._find_closing_brace(brace_start)
            if block_end is not None:
                yield name, self._text[block_start:block_end + 1]

    def _find_block_span(self, process_name: str) -> tuple[int, int] | None:
        """Return (start, end) indices of the block for the given process."""
        for match in _LABEL_RE.finditer(self._text):
            if match.group(1) == process_name:
                brace_start = match.end() - 1
                block_end = self._find_closing_brace(brace_start)
                if block_end is not None:
                    return (match.start(), block_end + 1)
        return None

    def _find_closing_brace(self, open_pos: int) -> int | None:
        """Find the position of the closing '}' matching the '{' at open_pos."""
        depth = 0
        for i in range(open_pos, len(self._text)):
            if self._text[i] == "{":
                depth += 1
            elif self._text[i] == "}":
                depth -= 1
                if depth == 0:
                    return i
        return None

    @staticmethod
    def _parse_cpus(block: str) -> int | None:
        """Extract CPU count from a config block."""
        m = _CPUS_RE.search(block)
        return int(m.group(1)) if m else None

    @staticmethod
    def _parse_memory(block: str) -> int | None:
        """Extract memory in GB from a config block."""
        m = _MEMORY_RE.search(block)
        return int(m.group(1)) if m else None

    @staticmethod
    def _read_system_memory_gb() -> int:
        """Read total system memory from /proc/meminfo (Linux).

        Falls back to psutil if available, or returns 0.
        """
        try:
            meminfo = Path("/proc/meminfo").read_text()
            for line in meminfo.splitlines():
                if line.startswith("MemTotal:"):
                    # Value is in kB
                    kb = int(line.split()[1])
                    return kb // (1024 * 1024)
        except (OSError, ValueError, IndexError):
            pass

        try:
            import psutil
            return int(psutil.virtual_memory().total / (1024 ** 3))
        except ImportError:
            pass

        return 0
