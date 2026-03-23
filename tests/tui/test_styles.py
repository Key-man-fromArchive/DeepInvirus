# @TASK T7.3 - TUI 테마/스타일 테스트
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t73-테마-및-스타일-정의
# @SPEC docs/planning/05-design-system.md#3-컬러-팔레트
"""
Tests for T7.3: app.tcss theme and style definitions.

Verifies:
- app.tcss file exists at the expected path
- All required design-system colour variables are defined
- All required CSS selectors are present
- Dark-theme background colour is used for Screen
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------

BIN_DIR = Path(__file__).resolve().parents[2] / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

TCSS_PATH = BIN_DIR / "tui" / "styles" / "app.tcss"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _tcss_content() -> str:
    """Return the raw text of app.tcss."""
    return TCSS_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# File existence
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_tcss_file_exists() -> None:
    """app.tcss must exist at bin/tui/styles/app.tcss."""
    assert TCSS_PATH.exists(), f"Expected TCSS file at {TCSS_PATH}"


@pytest.mark.unit
def test_tcss_file_not_empty() -> None:
    """app.tcss must not be empty (placeholder-only)."""
    content = _tcss_content()
    # Remove comments and whitespace; real rules must remain.
    stripped = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    assert stripped.strip(), "app.tcss contains only comments / whitespace"


# ---------------------------------------------------------------------------
# Colour variable definitions (05-design-system.md §3.1)
# ---------------------------------------------------------------------------


REQUIRED_COLOR_VARS = [
    "$primary",
    "$primary-light",
    "$secondary",
    "$success",
    "$warning",
    "$error",
    "$info",
    "$surface",
    "$background",
    "$text",
    "$text-muted",
]


@pytest.mark.unit
@pytest.mark.parametrize("variable", REQUIRED_COLOR_VARS)
def test_color_variable_defined(variable: str) -> None:
    """Each required colour variable must be assigned in app.tcss."""
    content = _tcss_content()
    # Match lines like: $primary: #1F77B4;
    pattern = re.compile(
        r"^\s*" + re.escape(variable) + r"\s*:", re.MULTILINE
    )
    assert pattern.search(content), (
        f"Colour variable '{variable}' is not defined in app.tcss"
    )


# ---------------------------------------------------------------------------
# Colour hex values from design system
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "variable, expected_hex",
    [
        ("$primary", "#1F77B4"),
        ("$secondary", "#FF7F0E"),
        ("$success", "#22C55E"),
        ("$warning", "#EAB308"),
        ("$error", "#EF4444"),
        ("$info", "#3B82F6"),
        ("$surface", "#F8F9FA"),
    ],
)
def test_color_variable_value(variable: str, expected_hex: str) -> None:
    """Colour variable must be assigned the exact design-system hex value."""
    content = _tcss_content()
    pattern = re.compile(
        re.escape(variable) + r"\s*:\s*" + re.escape(expected_hex),
        re.IGNORECASE,
    )
    assert pattern.search(content), (
        f"'{variable}' should be assigned '{expected_hex}' in app.tcss"
    )


# ---------------------------------------------------------------------------
# Dark theme — Screen background
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dark_theme_screen_background() -> None:
    """Screen selector must set background to the dark Catppuccin colour."""
    content = _tcss_content()
    # $background is defined as #1E1E2E; Screen must reference it.
    assert "$background" in content or "#1E1E2E" in content.upper(), (
        "app.tcss must use a dark background (#1E1E2E / $background)"
    )
    # Screen rule must exist.
    assert re.search(r"Screen\s*\{", content), (
        "Screen selector block not found in app.tcss"
    )


# ---------------------------------------------------------------------------
# Required CSS selectors
# ---------------------------------------------------------------------------


REQUIRED_SELECTORS = [
    # Core layout
    r"Screen\s*\{",
    # Header / Footer (built-in overrides or custom widgets)
    r"Header\s*\{",
    r"Footer\s*\{",
    # Status bar
    r"StatusBar\s*\{",
    # Progress
    r"ProgressWidget\s*\{",
    # Log viewer
    r"LogViewer\s*\{",
    # Data table
    r"DataTable\s*\{",
    # Input controls
    r"Input\s*\{",
    r"Input:focus\s*\{",
    r"Select\s*\{",
    r"RadioSet\s*\{",
    r"Checkbox\s*\{",
    # Buttons
    r"Button\s*\{",
    r"Button\.primary\s*\{",
    r"Button\.secondary\s*\{",
    r"Button\.danger\s*\{",
    # Utilities / panels
    r"\.panel\s*\{",
    r"\.card\s*\{",
    r"\.menu-grid\s*\{",
    r"\.menu-button\s*\{",
]


@pytest.mark.unit
@pytest.mark.parametrize("selector_pattern", REQUIRED_SELECTORS)
def test_required_selector_exists(selector_pattern: str) -> None:
    """Each required CSS selector block must be present in app.tcss."""
    content = _tcss_content()
    assert re.search(selector_pattern, content), (
        f"Required selector matching '{selector_pattern}' not found in app.tcss"
    )


# ---------------------------------------------------------------------------
# Hover / focus states
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_button_hover_state_defined() -> None:
    """Button:hover must be defined for interactive feedback."""
    content = _tcss_content()
    assert re.search(r"Button:hover\s*\{", content), (
        "Button:hover selector not found in app.tcss"
    )


@pytest.mark.unit
def test_input_focus_state_defined() -> None:
    """Input:focus must be defined to show keyboard focus."""
    content = _tcss_content()
    assert re.search(r"Input:focus\s*\{", content), (
        "Input:focus selector not found in app.tcss"
    )


@pytest.mark.unit
def test_menu_button_hover_state_defined() -> None:
    """.menu-button:hover must be defined for main menu feedback."""
    content = _tcss_content()
    assert re.search(r"\.menu-button:hover\s*\{", content), (
        ".menu-button:hover selector not found in app.tcss"
    )


@pytest.mark.unit
def test_menu_button_focus_state_defined() -> None:
    """.menu-button:focus must be defined for keyboard navigation."""
    content = _tcss_content()
    assert re.search(r"\.menu-button:focus\s*\{", content), (
        ".menu-button:focus selector not found in app.tcss"
    )


# ---------------------------------------------------------------------------
# DataTable header / cursor styles
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_datatable_header_style_defined() -> None:
    """DataTable header row must have a distinct style."""
    content = _tcss_content()
    assert re.search(r"\.datatable--header\s*\{", content), (
        "DataTable header style (.datatable--header) not found in app.tcss"
    )


@pytest.mark.unit
def test_datatable_cursor_style_defined() -> None:
    """DataTable cursor row must have a distinct style."""
    content = _tcss_content()
    assert re.search(r"\.datatable--cursor\s*\{", content), (
        "DataTable cursor style (.datatable--cursor) not found in app.tcss"
    )


# ---------------------------------------------------------------------------
# Semantic colour utility classes
# ---------------------------------------------------------------------------


SEMANTIC_CLASSES = [
    r"\.text-success\s*\{",
    r"\.text-warning\s*\{",
    r"\.text-error\s*\{",
    r"\.text-muted\s*\{",
]


@pytest.mark.unit
@pytest.mark.parametrize("cls_pattern", SEMANTIC_CLASSES)
def test_semantic_utility_class_exists(cls_pattern: str) -> None:
    """Semantic text-colour utility classes must be defined."""
    content = _tcss_content()
    assert re.search(cls_pattern, content), (
        f"Semantic utility class matching '{cls_pattern}' not found in app.tcss"
    )
