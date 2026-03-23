# @TASK T11.1 - Config 프리셋 관리자
# @SPEC docs/planning/06-tasks-tui.md#phase-11-t111-config-프리셋-화면-redgreen
# @TEST tests/tui/test_config_history.py
"""
Config preset manager for DeepInvirus.

Presets are stored as individual YAML files under ``~/.deepinvirus/presets/``.
Each file contains:
  - name: preset name (also the filename stem)
  - created_at: ISO-8601 timestamp
  - params: dict of pipeline parameters

Public API:
    save_preset(name, params, preset_dir=None) -> Path
    load_preset(name, preset_dir=None) -> dict
    list_presets(preset_dir=None) -> list[str]
    delete_preset(name, preset_dir=None) -> bool
    get_preset_details(name, preset_dir=None) -> dict
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Default preset directory
# ---------------------------------------------------------------------------

_DEFAULT_PRESET_DIR = Path.home() / ".deepinvirus" / "presets"


def _resolve_dir(preset_dir: Path | None) -> Path:
    """Return the preset directory, creating it if needed."""
    d = preset_dir if preset_dir is not None else _DEFAULT_PRESET_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _preset_path(name: str, preset_dir: Path) -> Path:
    return preset_dir / f"{name}.yaml"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def save_preset(
    name: str,
    params: dict,
    *,
    preset_dir: Path | None = None,
) -> Path:
    """Save a preset as a YAML file.

    Parameters
    ----------
    name:
        Preset name (used as filename stem).
    params:
        Pipeline parameter dictionary.
    preset_dir:
        Override preset directory (for testing with tmpdir).

    Returns
    -------
    Path to the created YAML file.
    """
    d = _resolve_dir(preset_dir)
    path = _preset_path(name, d)
    data = {
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "params": params,
    }
    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
    return path


def load_preset(
    name: str,
    *,
    preset_dir: Path | None = None,
) -> dict:
    """Load a preset by name and return its params dict.

    Raises
    ------
    FileNotFoundError
        If the preset YAML does not exist.
    """
    d = _resolve_dir(preset_dir)
    path = _preset_path(name, d)
    if not path.exists():
        raise FileNotFoundError(f"Preset not found: {name} (looked at {path})")
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["params"]


def list_presets(
    *,
    preset_dir: Path | None = None,
) -> list[str]:
    """Return a sorted list of preset names."""
    d = _resolve_dir(preset_dir)
    return sorted(p.stem for p in d.glob("*.yaml"))


def delete_preset(
    name: str,
    *,
    preset_dir: Path | None = None,
) -> bool:
    """Delete a preset by name. Returns True if deleted, False if not found."""
    d = _resolve_dir(preset_dir)
    path = _preset_path(name, d)
    if not path.exists():
        return False
    path.unlink()
    return True


def get_preset_details(
    name: str,
    *,
    preset_dir: Path | None = None,
) -> dict:
    """Return the full preset metadata (name, created_at, params).

    Raises
    ------
    FileNotFoundError
        If the preset YAML does not exist.
    """
    d = _resolve_dir(preset_dir)
    path = _preset_path(name, d)
    if not path.exists():
        raise FileNotFoundError(f"Preset not found: {name} (looked at {path})")
    with open(path) as f:
        data = yaml.safe_load(f)
    return data
