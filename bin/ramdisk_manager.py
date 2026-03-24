# @TASK T-RAMDISK - RAM disk manager for DeepInvirus
# @SPEC docs/planning/02-trd.md#RAM-disk-work-directory
"""
RAM disk manager for DeepInvirus.

Creates and manages a tmpfs-backed directory (/dev/shm) for the Nextflow
work directory.  Provides massive I/O speedup when data resides on NFS:

    NFS:  ~105 MB/s sequential
    RAM:  ~10+ GB/s (tmpfs on /dev/shm)

/dev/shm is a standard tmpfs mount on Linux, so no root privileges or
explicit mount commands are needed -- we just create a subdirectory.

Usage::

    from ramdisk_manager import RamdiskManager

    mgr = RamdiskManager()
    if mgr.is_available():
        work = mgr.create()       # -> Path("/dev/shm/deepinvirus_work")
        mgr.register_cleanup()    # atexit + SIGTERM handler
        # ... run pipeline with -w <work> ...
        mgr.cleanup()
"""

from __future__ import annotations

import atexit
import os
import shutil
import signal
import sys
from pathlib import Path


class RamdiskManager:
    """Manage a RAM-backed work directory on /dev/shm.

    Attributes:
        mount_point: Absolute path to the RAM disk work directory.
        size_gb: Requested size in GB (informational; /dev/shm is
            sized by the kernel, typically 50% of total RAM).
    """

    DEFAULT_MOUNT = Path("/dev/shm/deepinvirus_work")

    def __init__(
        self,
        mount_point: Path | None = None,
        size_gb: int = 200,
    ) -> None:
        self.mount_point: Path = mount_point or self.DEFAULT_MOUNT
        self.size_gb: int = size_gb

    # ------------------------------------------------------------------
    # RAM information
    # ------------------------------------------------------------------

    def get_available_ram_gb(self) -> int:
        """Return available (free) RAM in whole gigabytes.

        Parses ``/proc/meminfo`` for ``MemAvailable`` (preferred) or
        falls back to ``MemFree + Buffers + Cached``.
        """
        try:
            meminfo: dict[str, int] = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        value_kb = int(parts[1])
                        meminfo[key] = value_kb

            avail_kb = meminfo.get("MemAvailable")
            if avail_kb is None:
                avail_kb = (
                    meminfo.get("MemFree", 0)
                    + meminfo.get("Buffers", 0)
                    + meminfo.get("Cached", 0)
                )
            return max(1, avail_kb // (1024 * 1024))
        except (OSError, ValueError):
            # Fallback: use os.sysconf if available
            try:
                pages = os.sysconf("SC_AVPHYS_PAGES")
                page_size = os.sysconf("SC_PAGE_SIZE")
                return max(1, (pages * page_size) // (1024 ** 3))
            except (ValueError, OSError):
                return 1

    def get_recommended_size_gb(self) -> int:
        """Return recommended RAM disk size in GB.

        Heuristic: 50% of available RAM, clamped to [50, 300].
        """
        avail = self.get_available_ram_gb()
        rec = avail // 2
        return max(50, min(300, rec))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def create(self) -> Path:
        """Create the RAM disk work directory.

        Simply creates the directory under ``self.mount_point``
        (which lives on the /dev/shm tmpfs).  No explicit mount
        command is needed.

        Returns:
            Path to the created work directory.
        """
        self.mount_point.mkdir(parents=True, exist_ok=True)
        return self.mount_point

    def cleanup(self) -> None:
        """Remove the RAM disk work directory and all contents.

        Safe to call even if the directory does not exist.
        """
        if self.mount_point.exists():
            shutil.rmtree(self.mount_point, ignore_errors=True)

    def safe_cleanup_on_error(self) -> None:
        """Best-effort cleanup for use in signal/atexit handlers.

        Identical to :meth:`cleanup` but swallows all exceptions.
        """
        try:
            self.cleanup()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Usage / status
    # ------------------------------------------------------------------

    def get_usage(self) -> dict:
        """Return RAM disk usage information.

        Returns:
            Dict with keys ``total_gb``, ``used_gb``, ``free_gb``,
            ``percent`` (used percentage as float).
            All values are 0 if the mount point does not exist.
        """
        if not self.mount_point.exists():
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0.0}

        try:
            stat = shutil.disk_usage(self.mount_point)
            total_gb = stat.total / (1024 ** 3)
            used_gb = stat.used / (1024 ** 3)
            free_gb = stat.free / (1024 ** 3)
            percent = (stat.used / stat.total * 100) if stat.total > 0 else 0.0
            return {
                "total_gb": round(total_gb, 1),
                "used_gb": round(used_gb, 1),
                "free_gb": round(free_gb, 1),
                "percent": round(percent, 1),
            }
        except OSError:
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0.0}

    def is_available(self) -> bool:
        """Check whether /dev/shm is present and usable."""
        shm = Path("/dev/shm")
        return shm.exists() and shm.is_dir()

    # ------------------------------------------------------------------
    # Signal / atexit registration
    # ------------------------------------------------------------------

    def register_cleanup(self) -> None:
        """Register automatic cleanup via atexit and SIGTERM.

        On normal exit or SIGTERM, the RAM disk directory is removed
        so that memory is returned to the system.
        """
        atexit.register(self.safe_cleanup_on_error)

        prev_handler = signal.getsignal(signal.SIGTERM)

        def _sigterm_handler(signum, frame):
            self.safe_cleanup_on_error()
            # Chain to previous handler if it was callable
            if callable(prev_handler) and prev_handler not in (
                signal.SIG_DFL,
                signal.SIG_IGN,
            ):
                prev_handler(signum, frame)
            sys.exit(1)

        signal.signal(signal.SIGTERM, _sigterm_handler)
