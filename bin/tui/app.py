# @TASK T7.4 - DeepInVirusApp 완성 (메인 화면 + 키보드 바인딩)
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t74-메인-화면-구현-redgreen
# @TEST tests/tui/test_main_screen.py
"""
DeepInvirus TUI Application entry point.

This module defines the main Textual App class with:
- MainScreen as the default (initial) screen
- Keyboard bindings for all major screens
- Screen push/pop navigation logic

Keyboard shortcuts:
    r        -> RunScreen (Run Analysis)
    d        -> DbScreen (Database Management)
    h        -> HostScreen (Host Genome)
    c        -> ConfigScreen (Config Presets)
    i        -> HistoryScreen (History)
    q        -> Quit
    escape   -> Pop current screen (or quit if on MainScreen)
"""

from __future__ import annotations

from textual.app import App, ComposeResult

from tui.screens.config_screen import ConfigScreen
from tui.screens.db_screen import DbScreen
from tui.screens.history_screen import HistoryScreen
from tui.screens.host_screen import HostScreen
from tui.screens.main_screen import MainScreen
from tui.screens.run_screen import RunScreen


class DeepInVirusApp(App):
    """DeepInvirus TUI Application.

    A Textual-based terminal user interface for the DeepInvirus
    metagenomic virus detection pipeline.

    The application starts on MainScreen and allows navigation to
    sub-screens via keyboard shortcuts or button clicks.

    Attributes:
        TITLE: Window/tab title.
        CSS_PATH: Path to the Textual CSS stylesheet (relative to this file).
        SCREENS: Named screen registry for quick push_screen() calls.
        BINDINGS: Keyboard shortcut definitions.
    """

    TITLE = "DeepInvirus"
    CSS_PATH = "styles/app.tcss"

    SCREENS = {
        "main": MainScreen,
        "run": RunScreen,
        "db": DbScreen,
        "host": HostScreen,
        "config": ConfigScreen,
        "history": HistoryScreen,
    }

    BINDINGS = [
        ("r", "run", "Run Analysis"),
        ("d", "database", "Database"),
        ("h", "host", "Host Genome"),
        ("c", "config", "Config"),
        ("i", "history", "History"),
        ("q", "quit", "Quit"),
        ("escape", "back", "Back"),
    ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Push MainScreen as the initial (default) screen on startup."""
        self.push_screen("main")

    # ------------------------------------------------------------------
    # Navigation actions — invoked by BINDINGS and button handlers
    # ------------------------------------------------------------------

    def action_run(self) -> None:
        """Push the Run Analysis screen."""
        self.push_screen("run")

    def action_database(self) -> None:
        """Push the Database Management screen."""
        self.push_screen("db")

    def action_host(self) -> None:
        """Push the Host Genome screen."""
        self.push_screen("host")

    def action_config(self) -> None:
        """Push the Config Presets screen."""
        self.push_screen("config")

    def action_history(self) -> None:
        """Push the History screen."""
        self.push_screen("history")

    def action_help(self) -> None:
        """Show a brief help notification (placeholder until Help screen)."""
        self.notify(
            "Keyboard shortcuts: [r]Run  [d]DB  [h]Host  [c]Config  [i]History  [q]Quit",
            title="Help",
            timeout=5,
        )

    def action_back(self) -> None:
        """Pop the current screen; quit if only MainScreen remains."""
        # screen_stack includes the base (blank) screen at index 0
        if len(self.screen_stack) > 1:
            self.pop_screen()
        else:
            self.exit()


if __name__ == "__main__":
    app = DeepInVirusApp()
    app.run()
