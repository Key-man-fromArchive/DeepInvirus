# @TASK T8.3 - 결과 뷰어 화면
# @SPEC docs/planning/06-tasks-tui.md#phase-8-t83-결과-뷰어-화면-redgreen
# @TEST tests/tui/test_result_screen.py
"""
Result viewer screen for DeepInvirus TUI.

Displayed after the pipeline completes. Shows:
  - Duration (HH:MM:SS)
  - Sample count / list
  - Detected virus species count
  - Top virus (highest RPM)
  - Output file listing (dashboard.html, report.docx, bigtable.tsv, etc.)

Actions:
  [Open Dashboard] -> xdg-open dashboard.html
  [Open Folder]    -> xdg-open results/
  [Back to Main]   -> pop screen
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Static


# ---------------------------------------------------------------------------
# Utility: duration formatting
# ---------------------------------------------------------------------------


def format_duration(seconds: float | int) -> str:
    """Convert seconds to HH:MM:SS string.

    Args:
        seconds: Elapsed time in seconds.

    Returns:
        Formatted string, e.g. "02:15:33".
    """
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# ---------------------------------------------------------------------------
# ResultScreen
# ---------------------------------------------------------------------------


class ResultScreen(Screen):
    """Pipeline result viewer screen.

    Layout::

        +-- Analysis Complete ---------------------+
        |  Duration: 02:15:33                      |
        |  Samples: 2 (GC_Tm, Inf_NB_Tm)          |
        |  Viruses detected: 15 species            |
        |  Top virus: Densovirus (45.2 RPM)        |
        |                                          |
        |  Output files:                           |
        |    dashboard.html                        |
        |    report.docx                           |
        |    bigtable.tsv                          |
        |                                          |
        |  [Open Dashboard] [Open Folder] [Back]   |
        +------------------------------------------+

    Attributes:
        output_dir: Path to the pipeline output directory.
        duration: Elapsed seconds for the run.
        samples: List of sample names.
        bigtable_summary: Dict with virus summary stats.
        output_files: List of output file names found.
    """

    def __init__(
        self,
        output_dir: str | Path | None = None,
        duration: float = 0.0,
        samples: list[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.output_dir: Path = Path(output_dir) if output_dir else Path(".")
        self.duration: float = duration
        self.samples: list[str] = samples or []
        self.bigtable_summary: dict = {
            "total_viruses": 0,
            "top_virus": "",
            "top_rpm": 0.0,
        }
        self.output_files: list[str] = []

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Build the result viewer layout."""
        with ScrollableContainer():
            yield Static(" Analysis Complete", classes="section-title")

            with Vertical(classes="result-container"):
                yield Static("", id="result-duration")
                yield Static("", id="result-samples")
                yield Static("", id="result-viruses")
                yield Static("", id="result-top-virus")
                yield Label("")  # spacer
                yield Static("Output files:", classes="form-label")
                yield Static("", id="result-files")

            with Vertical(classes="button-row"):
                yield Button(
                    "Open Dashboard",
                    id="open-dashboard",
                    classes="primary",
                )
                yield Button(
                    "Open Folder",
                    id="open-folder",
                    classes="secondary",
                )
                yield Button(
                    "Back to Main",
                    id="back-main",
                    classes="secondary",
                )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_results(self, output_dir: str | Path) -> None:
        """Load and display results from the given output directory.

        Scans the directory for known output files, parses bigtable.tsv
        if present, and updates the display labels.

        Args:
            output_dir: Path to the pipeline output directory.
        """
        self.output_dir = Path(output_dir)

        # Scan output files
        known_files = [
            "dashboard.html",
            "report.docx",
            "bigtable.tsv",
            "multiqc_report.html",
        ]
        self.output_files = []
        for fname in known_files:
            if (self.output_dir / fname).exists():
                self.output_files.append(fname)

        # Also add any .tsv / .html / .docx not in the known list
        if self.output_dir.exists():
            for f in sorted(self.output_dir.iterdir()):
                if f.is_file() and f.name not in self.output_files:
                    if f.suffix in (".html", ".docx", ".tsv", ".xlsx", ".pdf"):
                        self.output_files.append(f.name)

        # Parse bigtable
        bigtable_path = self.output_dir / "bigtable.tsv"
        if bigtable_path.exists():
            self.bigtable_summary = self.summarize_bigtable(bigtable_path)

        # Update display
        self._update_display()

    def summarize_bigtable(self, bigtable_path: Path) -> dict:
        """Parse bigtable.tsv and produce summary statistics.

        Reads the TSV file looking for ``species`` and ``rpm`` columns.
        Computes:
          - total_viruses: Number of unique species
          - top_virus: Species with the highest RPM
          - top_rpm: The highest RPM value

        Args:
            bigtable_path: Path to the bigtable.tsv file.

        Returns:
            dict with keys ``total_viruses``, ``top_virus``, ``top_rpm``.
        """
        empty = {"total_viruses": 0, "top_virus": "", "top_rpm": 0.0}

        if not bigtable_path.exists():
            return empty

        try:
            with open(bigtable_path, newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")

                species_rpm: dict[str, float] = {}
                for row in reader:
                    sp = row.get("species", "").strip()
                    rpm_str = row.get("rpm", "0").strip()
                    if not sp:
                        continue
                    try:
                        rpm_val = float(rpm_str)
                    except (ValueError, TypeError):
                        rpm_val = 0.0

                    # Keep the max RPM per species
                    if sp not in species_rpm or rpm_val > species_rpm[sp]:
                        species_rpm[sp] = rpm_val

                if not species_rpm:
                    return empty

                total_viruses = len(species_rpm)
                top_virus = max(species_rpm, key=species_rpm.get)
                top_rpm = species_rpm[top_virus]

                return {
                    "total_viruses": total_viruses,
                    "top_virus": top_virus,
                    "top_rpm": top_rpm,
                }

        except Exception:
            return empty

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        btn_id = event.button.id

        if btn_id == "back-main":
            self.app.pop_screen()

        elif btn_id == "open-dashboard":
            dashboard = self.output_dir / "dashboard.html"
            if dashboard.exists():
                self._open_file(dashboard)
            else:
                self.app.notify(
                    "dashboard.html not found",
                    title="File Not Found",
                    severity="warning",
                )

        elif btn_id == "open-folder":
            if self.output_dir.exists():
                self._open_file(self.output_dir)
            else:
                self.app.notify(
                    f"Directory not found: {self.output_dir}",
                    title="Directory Not Found",
                    severity="warning",
                )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _update_display(self) -> None:
        """Refresh the on-screen labels with current result data."""
        try:
            self.query_one("#result-duration", Static).update(
                f"  Duration: {format_duration(self.duration)}"
            )
            sample_text = (
                f"  Samples: {len(self.samples)} ({', '.join(self.samples)})"
                if self.samples
                else "  Samples: 0"
            )
            self.query_one("#result-samples", Static).update(sample_text)
            self.query_one("#result-viruses", Static).update(
                f"  Viruses detected: {self.bigtable_summary['total_viruses']} species"
            )
            top = self.bigtable_summary
            if top["top_virus"]:
                self.query_one("#result-top-virus", Static).update(
                    f"  Top virus: {top['top_virus']} ({top['top_rpm']:.1f} RPM)"
                )
            else:
                self.query_one("#result-top-virus", Static).update(
                    "  Top virus: N/A"
                )

            file_list = "\n".join(
                f"    {fname}" for fname in self.output_files
            ) or "    (no output files found)"
            self.query_one("#result-files", Static).update(file_list)
        except Exception:
            # Widget not mounted yet
            pass

    @staticmethod
    def _open_file(path: Path) -> None:
        """Open a file or directory with the system default application.

        Uses ``xdg-open`` on Linux, ``open`` on macOS, ``start`` on Windows.
        """
        if sys.platform.startswith("linux"):
            subprocess.Popen(
                ["xdg-open", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif sys.platform == "darwin":
            subprocess.Popen(
                ["open", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif sys.platform == "win32":
            subprocess.Popen(
                ["start", str(path)],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
