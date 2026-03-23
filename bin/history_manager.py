# @TASK T11.2 - 실행 이력 관리자
# @SPEC docs/planning/06-tasks-tui.md#phase-11-t112-실행-이력-화면-redgreen
# @TEST tests/tui/test_config_history.py
"""
Run history manager for DeepInvirus.

History is stored as a JSON array in ``~/.deepinvirus/history.json``.
Each entry contains:
  - run_id: unique identifier (UUID or timestamp-based)
  - params: pipeline parameters dict
  - status: "done" | "failed" | "running"
  - duration: elapsed seconds (float)
  - output_dir: path to results directory
  - summary: dict with sample count, virus count, etc.
  - recorded_at: ISO-8601 timestamp

Public API:
    record_run(run_id, params, status, duration, output_dir, summary, history_file=None)
    get_history(limit=50, history_file=None) -> list[dict]
    get_run(run_id, history_file=None) -> dict | None
    delete_run(run_id, history_file=None) -> bool
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Default history file
# ---------------------------------------------------------------------------

_DEFAULT_HISTORY_FILE = Path.home() / ".deepinvirus" / "history.json"


def _resolve_file(history_file: Path | None) -> Path:
    """Return the history JSON path, ensuring parent exists."""
    f = history_file if history_file is not None else _DEFAULT_HISTORY_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    return f


def _read_history(path: Path) -> list[dict]:
    """Read and return the history list from disk, or empty list."""
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return data


def _write_history(path: Path, data: list[dict]) -> None:
    """Write the history list to disk as pretty JSON."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_run(
    run_id: str,
    params: dict,
    status: str,
    duration: float,
    output_dir: str,
    summary: dict,
    *,
    work_dir: str | None = None,
    history_file: Path | None = None,
) -> None:
    """Append a run record to the history file.

    Parameters
    ----------
    run_id:
        Unique run identifier.
    params:
        Pipeline parameters used for this run.
    status:
        Run outcome: "running", "completed", "failed", or "interrupted".
    duration:
        Elapsed wall-clock time in seconds.
    output_dir:
        Absolute path to the output directory.
    summary:
        Result summary dict (samples, viruses, etc.).
    work_dir:
        Nextflow work/ directory path for resume support.
    history_file:
        Override path for testing with tmpdir.
    """
    path = _resolve_file(history_file)
    records = _read_history(path)
    entry = {
        "run_id": run_id,
        "params": params,
        "status": status,
        "duration": duration,
        "output_dir": output_dir,
        "summary": summary,
        "work_dir": work_dir or "",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    records.append(entry)
    _write_history(path, records)


def get_history(
    limit: int = 50,
    *,
    history_file: Path | None = None,
) -> list[dict]:
    """Return run history sorted by most-recent first.

    Parameters
    ----------
    limit:
        Maximum number of entries to return.
    history_file:
        Override path for testing.
    """
    path = _resolve_file(history_file)
    records = _read_history(path)
    # Sort by recorded_at descending (most recent first)
    records.sort(key=lambda r: r.get("recorded_at", ""), reverse=True)
    return records[:limit]


def get_run(
    run_id: str,
    *,
    history_file: Path | None = None,
) -> dict | None:
    """Return a single run record by run_id, or None if not found."""
    path = _resolve_file(history_file)
    records = _read_history(path)
    for r in records:
        if r["run_id"] == run_id:
            return r
    return None


def delete_run(
    run_id: str,
    *,
    history_file: Path | None = None,
) -> bool:
    """Delete a run record by run_id. Returns True if deleted, False otherwise."""
    path = _resolve_file(history_file)
    records = _read_history(path)
    new_records = [r for r in records if r["run_id"] != run_id]
    if len(new_records) == len(records):
        return False
    _write_history(path, new_records)
    return True


def update_run_status(
    run_id: str,
    *,
    status: str,
    duration: float | None = None,
    history_file: Path | None = None,
) -> bool:
    """Update the status (and optionally duration) of an existing run record.

    Parameters
    ----------
    run_id:
        The run to update.
    status:
        New status value ("completed", "failed", "interrupted").
    duration:
        If provided, also update the duration field.
    history_file:
        Override path for testing.

    Returns
    -------
    bool: True if a matching record was found and updated.
    """
    path = _resolve_file(history_file)
    records = _read_history(path)
    for r in records:
        if r["run_id"] == run_id:
            r["status"] = status
            if duration is not None:
                r["duration"] = duration
            _write_history(path, records)
            return True
    return False


def get_interrupted_runs(
    *,
    history_file: Path | None = None,
) -> list[dict]:
    """Return records whose status is 'running' (likely from abnormal termination).

    These are runs that were never marked as completed, failed, or interrupted,
    indicating the process was killed before it could update the status.

    Returns
    -------
    list[dict]: Matching history records, most recent first.
    """
    path = _resolve_file(history_file)
    records = _read_history(path)
    running = [r for r in records if r.get("status") == "running"]
    running.sort(key=lambda r: r.get("recorded_at", ""), reverse=True)
    return running


def mark_interrupted(
    run_id: str,
    *,
    history_file: Path | None = None,
) -> bool:
    """Change a run's status to 'interrupted'.

    Parameters
    ----------
    run_id:
        The run to mark.
    history_file:
        Override path for testing.

    Returns
    -------
    bool: True if a matching record was found and updated.
    """
    return update_run_status(run_id, status="interrupted", history_file=history_file)


def get_resume_info(
    run_id: str,
    *,
    history_file: Path | None = None,
) -> dict | None:
    """Return the information needed to resume a run.

    Returns a dict with keys: params, output_dir, work_dir.
    Returns None if run_id is not found.
    """
    record = get_run(run_id, history_file=history_file)
    if record is None:
        return None
    return {
        "params": record.get("params", {}),
        "output_dir": record.get("output_dir", ""),
        "work_dir": record.get("work_dir", ""),
    }
