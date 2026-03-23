# @TASK T12.2 - E2E integration tests
# @SPEC docs/planning/06-tasks-tui.md#phase-12-t122-통합-테스트--문서-업데이트
# @TEST tests/tui/test_e2e.py
"""
End-to-end integration tests for the DeepInvirus TUI application.

Verifies:
- DeepInVirusApp class can be imported and instantiated
- All Screen classes are registered in SCREENS
- Keyboard bindings are defined (>= 7)
- CLI entrypoint module is importable
- README.md contains TUI and CLI documentation sections
- CHANGELOG.md contains v0.2.0 entry
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BIN_DIR = Path(__file__).resolve().parent.parent.parent / "bin"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestAppImport:
    """Verify DeepInVirusApp can be imported and has correct attributes."""

    def test_app_class_importable(self):
        """DeepInVirusApp should be importable from tui.app."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.app import DeepInVirusApp  # noqa: F401
        finally:
            sys.path[:] = original_path

    def test_app_instantiation(self):
        """DeepInVirusApp should instantiate without errors."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.app import DeepInVirusApp

            app = DeepInVirusApp()
            assert app is not None
            assert app.TITLE == "DeepInvirus"
        finally:
            sys.path[:] = original_path


class TestScreenRegistration:
    """Verify all required screens are registered in SCREENS."""

    REQUIRED_SCREENS = {"main", "run", "db", "host", "config", "history"}

    def test_all_screens_registered(self):
        """SCREENS dict must contain all 6 required screen keys."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.app import DeepInVirusApp

            app = DeepInVirusApp()
            registered = set(app.SCREENS.keys())
            missing = self.REQUIRED_SCREENS - registered
            assert not missing, f"Missing screens in SCREENS: {missing}"
        finally:
            sys.path[:] = original_path

    @pytest.mark.parametrize("screen_name", ["main", "run", "db", "host", "config", "history"])
    def test_individual_screen_registered(self, screen_name):
        """Each screen name must be present in SCREENS."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.app import DeepInVirusApp

            assert screen_name in DeepInVirusApp.SCREENS
        finally:
            sys.path[:] = original_path


class TestScreenImports:
    """Verify each screen class is importable."""

    def test_main_screen_import(self):
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.screens.main_screen import MainScreen  # noqa: F401
        finally:
            sys.path[:] = original_path

    def test_run_screen_import(self):
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.screens.run_screen import RunScreen  # noqa: F401
        finally:
            sys.path[:] = original_path

    def test_db_screen_import(self):
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.screens.db_screen import DbScreen  # noqa: F401
        finally:
            sys.path[:] = original_path

    def test_host_screen_import(self):
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.screens.host_screen import HostScreen  # noqa: F401
        finally:
            sys.path[:] = original_path

    def test_config_screen_import(self):
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.screens.config_screen import ConfigScreen  # noqa: F401
        finally:
            sys.path[:] = original_path

    def test_history_screen_import(self):
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.screens.history_screen import HistoryScreen  # noqa: F401
        finally:
            sys.path[:] = original_path


class TestKeyboardBindings:
    """Verify keyboard bindings are defined."""

    def test_minimum_bindings_count(self):
        """App should have at least 7 keyboard bindings."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.app import DeepInVirusApp

            assert len(DeepInVirusApp.BINDINGS) >= 7, (
                f"Expected >= 7 bindings, got {len(DeepInVirusApp.BINDINGS)}"
            )
        finally:
            sys.path[:] = original_path

    def test_quit_binding_exists(self):
        """There must be a 'q' quit binding."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.app import DeepInVirusApp

            keys = [b[0] for b in DeepInVirusApp.BINDINGS]
            assert "q" in keys, "'q' quit binding not found"
        finally:
            sys.path[:] = original_path

    def test_escape_binding_exists(self):
        """There must be an 'escape' back binding."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.app import DeepInVirusApp

            keys = [b[0] for b in DeepInVirusApp.BINDINGS]
            assert "escape" in keys, "'escape' back binding not found"
        finally:
            sys.path[:] = original_path

    def test_navigation_bindings(self):
        """Navigation bindings for r, d, h, c, i should exist."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from tui.app import DeepInVirusApp

            keys = [b[0] for b in DeepInVirusApp.BINDINGS]
            for key in ("r", "d", "h", "c", "i"):
                assert key in keys, f"Navigation binding '{key}' not found"
        finally:
            sys.path[:] = original_path


class TestCLIEntrypointImport:
    """Verify CLI entrypoint is importable."""

    def test_cli_importable(self):
        """deepinvirus_cli.cli should be importable."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from deepinvirus_cli import cli  # noqa: F401
        finally:
            sys.path[:] = original_path


class TestDocumentation:
    """Verify README.md and CHANGELOG.md have required sections."""

    def test_readme_tui_section(self):
        """README.md must contain a TUI Mode section."""
        readme = PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md not found"
        content = readme.read_text()
        assert "## TUI Mode" in content, "README missing '## TUI Mode' section"

    def test_readme_cli_section(self):
        """README.md must contain a CLI Mode section."""
        readme = PROJECT_ROOT / "README.md"
        content = readme.read_text()
        assert "## CLI Mode" in content, "README missing '## CLI Mode' section"

    def test_readme_keyboard_shortcuts(self):
        """README.md should document keyboard shortcuts."""
        readme = PROJECT_ROOT / "README.md"
        content = readme.read_text().lower()
        # Should mention at least some shortcut keys
        assert "shortcut" in content or "keyboard" in content or "keybinding" in content, (
            "README should document keyboard shortcuts"
        )

    def test_changelog_v020(self):
        """CHANGELOG.md must contain a v0.2.0 entry."""
        changelog = PROJECT_ROOT / "CHANGELOG.md"
        assert changelog.exists(), "CHANGELOG.md not found"
        content = changelog.read_text()
        assert "[0.2.0]" in content, "CHANGELOG missing '[0.2.0]' version entry"

    def test_changelog_tui_entry(self):
        """CHANGELOG v0.2.0 should mention TUI."""
        changelog = PROJECT_ROOT / "CHANGELOG.md"
        content = changelog.read_text()
        assert "TUI" in content, "CHANGELOG v0.2.0 should mention TUI"

    def test_changelog_cli_entry(self):
        """CHANGELOG v0.2.0 should mention CLI entrypoint."""
        changelog = PROJECT_ROOT / "CHANGELOG.md"
        content = changelog.read_text()
        assert "CLI" in content, "CHANGELOG v0.2.0 should mention CLI entrypoint"
