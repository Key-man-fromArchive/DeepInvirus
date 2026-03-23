# @TASK T5.2 - Word report generation tests
# @SPEC docs/planning/05-design-system.md#5-word-보고서-템플릿
# @TEST tests/modules/test_report.py
"""Tests for bin/generate_report.py - automated Word report generation.

Covers:
- Valid .docx file generation from mock input data
- Report structure validation (section headings match design-system 5.1)
- Figure insertion into the Word document
- Table insertion into the Word document
- CLI argument parsing
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from docx import Document

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = PROJECT_ROOT / "bin"
GENERATE_REPORT_SCRIPT = BIN_DIR / "generate_report.py"


# ---------------------------------------------------------------------------
# Fixtures: mock input data
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_bigtable_tsv(tmp_path: Path) -> Path:
    """Create a mock bigtable.tsv file."""
    df = pd.DataFrame(
        {
            "seq_id": [f"seq_{i}" for i in range(12)],
            "sample": ["S1"] * 4 + ["S2"] * 4 + ["S3"] * 4,
            "seq_type": ["contig"] * 12,
            "length": [5000, 3500, 4200, 2800, 5100, 3400, 4100, 2900, 4800, 3600, 4300, 3000],
            "detection_method": ["genomad", "diamond", "both", "genomad"] * 3,
            "detection_score": [0.95, 0.87, 0.92, 0.78, 0.93, 0.85, 0.91, 0.80, 0.94, 0.86, 0.90, 0.79],
            "taxid": [10001, 10002, 10003, 10004] * 3,
            "domain": ["Viruses"] * 12,
            "phylum": ["Nucleocytoviricota", "Leviviricota", "Nucleocytoviricota", "Pisuviricota"] * 3,
            "class": ["Megaviricetes", "Leviviricetes", "Megaviricetes", "Pisoniviricetes"] * 3,
            "order": ["Imitervirales", "Norzivirales", "Imitervirales", "Picornavirales"] * 3,
            "family": ["Mimiviridae", "Leviviridae", "Phycodnaviridae", "Picornaviridae"] * 3,
            "genus": ["Mimivirus", "Levivirus", "Chlorovirus", "Enterovirus"] * 3,
            "species": ["Mimivirus sp.", "Levivirus sp.", "Chlorovirus sp.", "Enterovirus sp."] * 3,
            "ictv_classification": ["ICTV_A", "ICTV_B", "ICTV_C", "ICTV_D"] * 3,
            "baltimore_group": ["dsDNA", "ssRNA(+)", "dsDNA", "ssRNA(+)"] * 3,
            "count": [150, 120, 130, 90, 160, 110, 140, 95, 155, 115, 135, 85],
            "rpm": [150.5, 120.3, 130.2, 90.1, 160.0, 110.5, 140.3, 95.2, 155.1, 115.4, 135.0, 85.3],
            "coverage": [0.85, 0.72, 0.68, 0.55, 0.88, 0.70, 0.66, 0.58, 0.83, 0.74, 0.69, 0.53],
        }
    )
    path = tmp_path / "bigtable.tsv"
    df.to_csv(path, sep="\t", index=False)
    return path


@pytest.fixture
def mock_matrix_tsv(tmp_path: Path) -> Path:
    """Create a mock sample_taxon_matrix.tsv file."""
    df = pd.DataFrame(
        {
            "taxon": ["Mimivirus", "Levivirus", "Chlorovirus", "Enterovirus"],
            "taxid": [10001, 10002, 10003, 10004],
            "rank": ["genus"] * 4,
            "S1": [150.5, 120.3, 130.2, 90.1],
            "S2": [160.0, 110.5, 140.3, 95.2],
            "S3": [155.1, 115.4, 135.0, 85.3],
        }
    )
    path = tmp_path / "sample_taxon_matrix.tsv"
    df.to_csv(path, sep="\t", index=False)
    return path


@pytest.fixture
def mock_alpha_tsv(tmp_path: Path) -> Path:
    """Create a mock alpha_diversity.tsv file."""
    df = pd.DataFrame(
        {
            "sample": ["S1", "S2", "S3"],
            "observed_species": [4, 4, 4],
            "shannon": [1.35, 1.32, 1.34],
            "simpson": [0.74, 0.73, 0.74],
            "chao1": [4.0, 4.0, 4.0],
            "pielou_evenness": [0.97, 0.95, 0.96],
        }
    )
    path = tmp_path / "alpha_diversity.tsv"
    df.to_csv(path, sep="\t", index=False)
    return path


@pytest.fixture
def mock_pcoa_tsv(tmp_path: Path) -> Path:
    """Create a mock pcoa_coordinates.tsv file."""
    df = pd.DataFrame(
        {
            "sample": ["S1", "S2", "S3"],
            "PC1": [0.25, -0.15, -0.10],
            "PC2": [0.10, -0.20, 0.10],
            "PC3": [0.05, 0.03, -0.08],
        }
    )
    path = tmp_path / "pcoa_coordinates.tsv"
    df.to_csv(path, sep="\t", index=False)
    return path


@pytest.fixture
def mock_qc_stats_tsv(tmp_path: Path) -> Path:
    """Create a mock fastp QC stats file."""
    df = pd.DataFrame(
        {
            "sample": ["S1", "S2", "S3"],
            "raw_reads": [10000000, 12000000, 11000000],
            "raw_bases": [1500000000, 1800000000, 1650000000],
            "trimmed_reads": [9500000, 11400000, 10450000],
            "trimmed_bases": [1425000000, 1710000000, 1567500000],
            "q30_rate": [0.95, 0.94, 0.95],
            "gc_content": [0.42, 0.43, 0.42],
            "host_removed_reads": [8000000, 9600000, 8800000],
        }
    )
    path = tmp_path / "qc_stats.tsv"
    df.to_csv(path, sep="\t", index=False)
    return path


@pytest.fixture
def mock_assembly_stats_tsv(tmp_path: Path) -> Path:
    """Create a mock assembly stats file."""
    df = pd.DataFrame(
        {
            "sample": ["S1", "S2", "S3"],
            "total_contigs": [1500, 1800, 1650],
            "total_length": [3000000, 3600000, 3300000],
            "n50": [5000, 4500, 4800],
            "largest_contig": [25000, 22000, 23000],
            "gc_percent": [42.1, 43.2, 42.5],
        }
    )
    path = tmp_path / "assembly_stats.tsv"
    df.to_csv(path, sep="\t", index=False)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGenerateReportScript:
    """Test the generate_report.py script exists and is importable."""

    def test_script_exists(self) -> None:
        """generate_report.py must exist in bin/."""
        assert GENERATE_REPORT_SCRIPT.exists(), (
            f"Script not found: {GENERATE_REPORT_SCRIPT}"
        )

    def test_script_importable(self) -> None:
        """The script module must be importable without errors."""
        result = subprocess.run(
            [sys.executable, "-c", f"import importlib.util; spec = importlib.util.spec_from_file_location('generate_report', '{GENERATE_REPORT_SCRIPT}'); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"


@pytest.mark.unit
class TestDocxGeneration:
    """Test that a valid .docx file is generated with correct structure."""

    def test_generates_valid_docx(
        self,
        tmp_path: Path,
        mock_bigtable_tsv: Path,
        mock_matrix_tsv: Path,
        mock_alpha_tsv: Path,
        mock_pcoa_tsv: Path,
        mock_qc_stats_tsv: Path,
        mock_assembly_stats_tsv: Path,
    ) -> None:
        """Running generate_report.py must produce a valid .docx file."""
        output = tmp_path / "report.docx"
        result = subprocess.run(
            [
                sys.executable,
                str(GENERATE_REPORT_SCRIPT),
                "--bigtable", str(mock_bigtable_tsv),
                "--matrix", str(mock_matrix_tsv),
                "--alpha", str(mock_alpha_tsv),
                "--pcoa", str(mock_pcoa_tsv),
                "--qc-stats", str(mock_qc_stats_tsv),
                "--assembly-stats", str(mock_assembly_stats_tsv),
                "--output", str(output),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        assert output.exists(), "Output .docx file was not created"
        assert output.stat().st_size > 0, "Output .docx file is empty"

        # Verify it is a valid Word document
        doc = Document(str(output))
        assert doc is not None, "Failed to open .docx with python-docx"

    def test_report_section_headings(
        self,
        tmp_path: Path,
        mock_bigtable_tsv: Path,
        mock_matrix_tsv: Path,
        mock_alpha_tsv: Path,
        mock_pcoa_tsv: Path,
        mock_qc_stats_tsv: Path,
        mock_assembly_stats_tsv: Path,
    ) -> None:
        """Report must contain all section headings from design-system 5.1."""
        output = tmp_path / "report.docx"
        subprocess.run(
            [
                sys.executable,
                str(GENERATE_REPORT_SCRIPT),
                "--bigtable", str(mock_bigtable_tsv),
                "--matrix", str(mock_matrix_tsv),
                "--alpha", str(mock_alpha_tsv),
                "--pcoa", str(mock_pcoa_tsv),
                "--qc-stats", str(mock_qc_stats_tsv),
                "--assembly-stats", str(mock_assembly_stats_tsv),
                "--output", str(output),
            ],
            capture_output=True,
            text=True,
        )
        doc = Document(str(output))

        # Extract all heading texts
        headings = []
        for para in doc.paragraphs:
            if para.style and para.style.name and para.style.name.startswith("Heading"):
                headings.append(para.text)

        heading_text = " | ".join(headings)

        # Expected top-level sections (design-system 5.1)
        expected_sections = [
            "분석 개요",
            "품질 관리",
            "바이러스 탐지 결과",
            "분류학적 분석",
            "다양성 분석",
            "결론",
        ]

        for section in expected_sections:
            found = any(section in h for h in headings)
            assert found, (
                f"Section heading containing '{section}' not found. "
                f"Found headings: {heading_text}"
            )

    def test_report_contains_tables(
        self,
        tmp_path: Path,
        mock_bigtable_tsv: Path,
        mock_matrix_tsv: Path,
        mock_alpha_tsv: Path,
        mock_pcoa_tsv: Path,
        mock_qc_stats_tsv: Path,
        mock_assembly_stats_tsv: Path,
    ) -> None:
        """Report must contain tables (at least project info, QC, detection summary)."""
        output = tmp_path / "report.docx"
        subprocess.run(
            [
                sys.executable,
                str(GENERATE_REPORT_SCRIPT),
                "--bigtable", str(mock_bigtable_tsv),
                "--matrix", str(mock_matrix_tsv),
                "--alpha", str(mock_alpha_tsv),
                "--pcoa", str(mock_pcoa_tsv),
                "--qc-stats", str(mock_qc_stats_tsv),
                "--assembly-stats", str(mock_assembly_stats_tsv),
                "--output", str(output),
            ],
            capture_output=True,
            text=True,
        )
        doc = Document(str(output))
        # Expect at least 3 tables (project info, QC, detection summary)
        assert len(doc.tables) >= 3, (
            f"Expected at least 3 tables in report, found {len(doc.tables)}"
        )

    def test_report_contains_figures(
        self,
        tmp_path: Path,
        mock_bigtable_tsv: Path,
        mock_matrix_tsv: Path,
        mock_alpha_tsv: Path,
        mock_pcoa_tsv: Path,
        mock_qc_stats_tsv: Path,
        mock_assembly_stats_tsv: Path,
    ) -> None:
        """Report must contain inline images (figures)."""
        output = tmp_path / "report.docx"
        subprocess.run(
            [
                sys.executable,
                str(GENERATE_REPORT_SCRIPT),
                "--bigtable", str(mock_bigtable_tsv),
                "--matrix", str(mock_matrix_tsv),
                "--alpha", str(mock_alpha_tsv),
                "--pcoa", str(mock_pcoa_tsv),
                "--qc-stats", str(mock_qc_stats_tsv),
                "--assembly-stats", str(mock_assembly_stats_tsv),
                "--output", str(output),
            ],
            capture_output=True,
            text=True,
        )
        doc = Document(str(output))

        # Count inline images across all paragraphs
        image_count = 0
        for para in doc.paragraphs:
            for run in para.runs:
                # Check for inline images in run XML
                inline_shapes = run._r.findall(
                    ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline"
                )
                image_count += len(inline_shapes)

        assert image_count >= 2, (
            f"Expected at least 2 figures in report, found {image_count}"
        )

    def test_figures_directory_created(
        self,
        tmp_path: Path,
        mock_bigtable_tsv: Path,
        mock_matrix_tsv: Path,
        mock_alpha_tsv: Path,
        mock_pcoa_tsv: Path,
        mock_qc_stats_tsv: Path,
        mock_assembly_stats_tsv: Path,
    ) -> None:
        """Figures should also be saved to a figures/ directory."""
        output = tmp_path / "report.docx"
        figures_dir = tmp_path / "figures"
        result = subprocess.run(
            [
                sys.executable,
                str(GENERATE_REPORT_SCRIPT),
                "--bigtable", str(mock_bigtable_tsv),
                "--matrix", str(mock_matrix_tsv),
                "--alpha", str(mock_alpha_tsv),
                "--pcoa", str(mock_pcoa_tsv),
                "--qc-stats", str(mock_qc_stats_tsv),
                "--assembly-stats", str(mock_assembly_stats_tsv),
                "--output", str(output),
                "--figures-dir", str(figures_dir),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"
        assert figures_dir.exists(), "figures/ directory not created"

        png_files = list(figures_dir.glob("*.png"))
        assert len(png_files) >= 2, (
            f"Expected at least 2 PNG figures, found {len(png_files)}"
        )


@pytest.mark.unit
class TestReportAppendix:
    """Test that the report appendix sections are present."""

    def test_appendix_present(
        self,
        tmp_path: Path,
        mock_bigtable_tsv: Path,
        mock_matrix_tsv: Path,
        mock_alpha_tsv: Path,
        mock_pcoa_tsv: Path,
        mock_qc_stats_tsv: Path,
        mock_assembly_stats_tsv: Path,
    ) -> None:
        """Report must contain appendix section."""
        output = tmp_path / "report.docx"
        subprocess.run(
            [
                sys.executable,
                str(GENERATE_REPORT_SCRIPT),
                "--bigtable", str(mock_bigtable_tsv),
                "--matrix", str(mock_matrix_tsv),
                "--alpha", str(mock_alpha_tsv),
                "--pcoa", str(mock_pcoa_tsv),
                "--qc-stats", str(mock_qc_stats_tsv),
                "--assembly-stats", str(mock_assembly_stats_tsv),
                "--output", str(output),
            ],
            capture_output=True,
            text=True,
        )
        doc = Document(str(output))
        headings = [p.text for p in doc.paragraphs if p.style and p.style.name and p.style.name.startswith("Heading")]

        # Check for appendix-related headings
        found_appendix = any("부록" in h or "Appendix" in h or "부록" in h for h in headings)
        assert found_appendix, (
            f"Appendix heading not found. Headings: {headings}"
        )
