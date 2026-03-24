# @TASK T7.4 - 메인 메뉴 화면 구현
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t74-메인-화면-구현-redgreen
# @TEST tests/tui/test_main_screen.py
"""
Main menu screen for DeepInvirus TUI.

Layout (ASCII):
  ┌──────────────────────────────────────────────┐
  │  DeepInvirus v0.1.0        DB: 2026-03-23    │  <- HeaderWidget
  ├──────────────────────────────────────────────┤
  │  [DB status bar]                             │  <- StatusBar
  ├──────────────────────────────────────────────┤
  │  ┌────────────┐  ┌────────────┐              │
  │  │ Run        │  │ Database   │              │
  │  │ Analysis   │  │ Management │              │
  │  └────────────┘  └────────────┘              │
  │  ┌────────────┐  ┌────────────┐              │  <- .menu-grid (2x3)
  │  │ Host       │  │ Config     │              │
  │  │ Genome     │  │ Presets    │              │
  │  └────────────┘  └────────────┘              │
  │  ┌────────────┐  ┌────────────┐              │
  │  │ History    │  │ Help       │              │
  │  └────────────┘  └────────────┘              │
  ├──────────────────────────────────────────────┤
  │  [r]Run [d]Database [h]Host [c]Config [q]Quit│  <- FooterWidget
  └──────────────────────────────────────────────┘
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Static

from tui.widgets.footer import FooterWidget
from tui.widgets.header import HeaderWidget
from tui.widgets.status_bar import StatusBar


class MainScreen(Screen):
    """Main menu screen with 6 navigation buttons.

    Composes:
        - HeaderWidget: logo, version, DB status
        - StatusBar: DB path, version, hosts, last run
        - .menu-grid: 2x3 grid of .menu-button widgets
        - FooterWidget: keyboard shortcut hints

    Button IDs and their target screens:
        btn-run      -> RunScreen
        btn-db       -> DbScreen
        btn-host     -> HostScreen
        btn-config   -> ConfigScreen
        btn-history  -> HistoryScreen
        btn-resource -> ResourceScreen
        btn-help     -> (placeholder message)
    """

    def compose(self) -> ComposeResult:
        """Compose the main menu layout."""
        yield HeaderWidget()
        yield StatusBar()

        with Static(classes="menu-grid"):
            yield Button(
                "Run Analysis",
                id="btn-run",
                classes="menu-button",
            )
            yield Button(
                "Database",
                id="btn-db",
                classes="menu-button",
            )
            yield Button(
                "Host Genome",
                id="btn-host",
                classes="menu-button",
            )
            yield Button(
                "Config Presets",
                id="btn-config",
                classes="menu-button",
            )
            yield Button(
                "History",
                id="btn-history",
                classes="menu-button",
            )
            yield Button(
                "Process Resources",
                id="btn-resource",
                classes="menu-button",
            )
            yield Button(
                "Help",
                id="btn-help",
                classes="menu-button",
            )

        yield FooterWidget()

    # ------------------------------------------------------------------
    # Button press handlers — delegate to app-level actions
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route button presses to the appropriate screen transition."""
        button_id = event.button.id
        action_map = {
            "btn-run": "run",
            "btn-db": "database",
            "btn-host": "host",
            "btn-config": "config",
            "btn-history": "history",
            "btn-resource": "resource",
            "btn-help": "help",
        }
        if button_id in action_map:
            self.app.call_action(f"action_{action_map[button_id]}")
