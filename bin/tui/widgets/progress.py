# @TASK T7.2 - ProgressWidget 구현
# @SPEC docs/planning/06-tasks-tui.md#phase-7-t72-공통-위젯-구현-redgreen
# @TEST tests/tui/test_widgets.py::TestProgressWidget
"""
Progress widget for DeepInvirus TUI.

Displays Nextflow pipeline progress:
- A Textual ProgressBar showing step N / M
- Current stage name (e.g. "FASTP", "MEGAHIT")
- Elapsed time (updated externally via update())
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Static


class ProgressWidget(Widget):
    """Nextflow pipeline progress widget.

    Usage:
        widget = ProgressWidget()
        # Later, when the pipeline posts progress:
        widget.update(current=3, total=14, step_name="MEGAHIT")
        # When starting a new run:
        widget.reset()

    Attributes:
        current (int): Steps completed so far.
        total (int): Total number of steps in the pipeline.
        step_name (str): Human-readable name of the currently running step.
    """

    DEFAULT_CSS = """
    ProgressWidget {
        height: 5;
        padding: 1 2;
        background: $surface;
    }
    ProgressWidget #progress-bar {
        width: 1fr;
    }
    ProgressWidget #progress-step {
        margin-top: 1;
        color: $text-muted;
    }
    ProgressWidget #progress-elapsed {
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current: int = 0
        self.total: int = 0
        self.step_name: str = ""

    def compose(self) -> ComposeResult:
        """Render progress bar, step label, and elapsed time label."""
        yield ProgressBar(total=100, show_eta=False, id="progress-bar")
        yield Static("", id="progress-step")
        yield Static("Elapsed: 00:00:00", id="progress-elapsed")

    def update(
        self,
        current: int,
        total: int,
        step_name: str = "",
        elapsed: str = "",
    ) -> None:
        """Update progress state and refresh displayed values.

        Args:
            current: Number of completed steps.
            total: Total number of pipeline steps.
            step_name: Name of the currently running step.
            elapsed: Optional elapsed-time string, e.g. "01:23:45".
        """
        self.current = current
        self.total = total
        self.step_name = step_name

        # Compute percentage for the ProgressBar (0-100)
        pct = int(current / total * 100) if total > 0 else 0

        try:
            bar: ProgressBar = self.query_one("#progress-bar", ProgressBar)
            bar.update(progress=pct)

            step_label = self.query_one("#progress-step", Static)
            if total > 0:
                step_label.update(
                    f"Step {current}/{total}  —  {step_name}" if step_name
                    else f"Step {current}/{total}"
                )
            else:
                step_label.update(step_name)

            if elapsed:
                elapsed_label = self.query_one("#progress-elapsed", Static)
                elapsed_label.update(f"Elapsed: {elapsed}")
        except Exception:
            # Widget may not be mounted yet (unit-test context)
            pass

    def reset(self) -> None:
        """Reset progress to initial state (new pipeline run)."""
        self.current = 0
        self.total = 0
        self.step_name = ""

        try:
            bar: ProgressBar = self.query_one("#progress-bar", ProgressBar)
            bar.update(progress=0)
            self.query_one("#progress-step", Static).update("")
            self.query_one("#progress-elapsed", Static).update(
                "Elapsed: 00:00:00"
            )
        except Exception:
            pass
