"""Tests for fastp module outputs and parse_fastp.py script.

# @TASK T1.1 - fastp QC 모듈 테스트
# @SPEC docs/planning/02-trd.md#3.2-파이프라인-단계
# @TEST tests/modules/test_fastp.py
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = PROJECT_ROOT / "bin"
PARSE_FASTP_SCRIPT = BIN_DIR / "parse_fastp.py"
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
FASTP_NF = MODULES_DIR / "fastp.nf"

# Expected TSV columns from parse_fastp.py
EXPECTED_COLUMNS = [
    "sample",
    "total_reads_before",
    "total_reads_after",
    "q30_rate_before",
    "q30_rate_after",
    "gc_content",
    "duplication_rate",
    "adapter_trimmed_rate",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_fastp_json() -> dict:
    """Return a realistic mock fastp JSON structure.

    Based on the actual fastp JSON output specification.
    """
    return {
        "summary": {
            "before_filtering": {
                "total_reads": 1000000,
                "total_bases": 150000000,
                "q20_bases": 140000000,
                "q30_bases": 130000000,
                "q20_rate": 0.9333,
                "q30_rate": 0.8667,
                "gc_content": 0.45,
            },
            "after_filtering": {
                "total_reads": 950000,
                "total_bases": 142500000,
                "q20_bases": 138000000,
                "q30_bases": 128000000,
                "q20_rate": 0.9684,
                "q30_rate": 0.8982,
                "gc_content": 0.44,
            },
        },
        "duplication": {
            "rate": 0.123,
        },
        "adapter_cutting": {
            "adapter_trimmed_reads": 50000,
            "adapter_trimmed_bases": 750000,
        },
        "filtering_result": {
            "passed_filter_reads": 950000,
            "low_quality_reads": 40000,
            "too_many_N_reads": 0,
            "too_short_reads": 10000,
            "too_long_reads": 0,
        },
    }


@pytest.fixture
def mock_fastp_json_file(tmp_dir: Path, mock_fastp_json: dict) -> Path:
    """Write mock fastp JSON to a temp file and return its path."""
    json_path = tmp_dir / "sample1.fastp.json"
    json_path.write_text(json.dumps(mock_fastp_json, indent=2))
    return json_path


@pytest.fixture
def mock_fastp_json_no_adapter() -> dict:
    """Return a fastp JSON without adapter_cutting section.

    This can happen when adapter detection is disabled.
    """
    return {
        "summary": {
            "before_filtering": {
                "total_reads": 500000,
                "total_bases": 75000000,
                "q20_bases": 70000000,
                "q30_bases": 65000000,
                "q20_rate": 0.9333,
                "q30_rate": 0.8667,
                "gc_content": 0.50,
            },
            "after_filtering": {
                "total_reads": 480000,
                "total_bases": 72000000,
                "q20_bases": 69000000,
                "q30_bases": 64000000,
                "q20_rate": 0.9583,
                "q30_rate": 0.8889,
                "gc_content": 0.49,
            },
        },
        "duplication": {
            "rate": 0.05,
        },
        "filtering_result": {
            "passed_filter_reads": 480000,
            "low_quality_reads": 15000,
            "too_many_N_reads": 0,
            "too_short_reads": 5000,
            "too_long_reads": 0,
        },
    }


# ---------------------------------------------------------------------------
# Test: fastp.nf file structure
# ---------------------------------------------------------------------------
class TestFastpNextflow:
    """Tests for fastp.nf Nextflow process definition."""

    @pytest.mark.unit
    def test_fastp_nf_exists(self) -> None:
        """fastp.nf file must exist."""
        assert FASTP_NF.exists(), f"fastp.nf not found at {FASTP_NF}"

    @pytest.mark.unit
    def test_fastp_nf_contains_process(self) -> None:
        """fastp.nf must define a process named FASTP."""
        content = FASTP_NF.read_text()
        assert "process FASTP" in content

    @pytest.mark.unit
    def test_fastp_nf_has_real_command(self) -> None:
        """fastp.nf script block must contain the actual fastp command."""
        content = FASTP_NF.read_text()
        assert "fastp \\\\" in content or "fastp \\" in content

    @pytest.mark.unit
    def test_fastp_nf_has_required_params(self) -> None:
        """fastp.nf must include required QC parameters."""
        content = FASTP_NF.read_text()
        required_params = [
            "--qualified_quality_phred",
            "--length_required",
            "--cut_tail",
            "--dedup",
            "--trim_poly_x",
            "--detect_adapter_for_pe",
        ]
        for param in required_params:
            assert param in content, f"Missing required param: {param}"

    @pytest.mark.unit
    def test_fastp_nf_output_filenames(self) -> None:
        """fastp.nf must produce correctly named output files."""
        content = FASTP_NF.read_text()
        assert "_R1.trimmed.fastq.gz" in content
        assert "_R2.trimmed.fastq.gz" in content
        assert ".fastp.json" in content
        assert ".fastp.html" in content

    @pytest.mark.unit
    def test_fastp_nf_has_stub_block(self) -> None:
        """fastp.nf must retain a stub block for dry-run testing."""
        content = FASTP_NF.read_text()
        assert "stub:" in content

    @pytest.mark.unit
    def test_fastp_nf_has_tag_annotations(self) -> None:
        """fastp.nf must have @TASK and @SPEC TAG annotations."""
        content = FASTP_NF.read_text()
        assert "@TASK" in content
        assert "@SPEC" in content


# ---------------------------------------------------------------------------
# Test: parse_fastp.py exists and is executable
# ---------------------------------------------------------------------------
class TestParseFastpScript:
    """Tests for bin/parse_fastp.py script."""

    @pytest.mark.unit
    def test_parse_fastp_script_exists(self) -> None:
        """parse_fastp.py must exist in bin/."""
        assert PARSE_FASTP_SCRIPT.exists(), (
            f"parse_fastp.py not found at {PARSE_FASTP_SCRIPT}"
        )

    @pytest.mark.unit
    def test_parse_fastp_is_importable(self) -> None:
        """parse_fastp.py must be importable as a Python module."""
        # Temporarily add bin/ to sys.path
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            import parse_fastp  # noqa: F401
        finally:
            sys.path = original_path


# ---------------------------------------------------------------------------
# Test: parse_fastp.py JSON parsing logic
# ---------------------------------------------------------------------------
class TestParseFastpParsing:
    """Tests for fastp JSON parsing and TSV generation."""

    @pytest.mark.unit
    def test_parse_single_json(self, mock_fastp_json: dict) -> None:
        """parse_fastp_json() extracts correct metrics from a single JSON."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from parse_fastp import parse_fastp_json

            result = parse_fastp_json(mock_fastp_json, sample_name="sample1")
        finally:
            sys.path = original_path

        assert result["sample"] == "sample1"
        assert result["total_reads_before"] == 1000000
        assert result["total_reads_after"] == 950000
        assert abs(result["q30_rate_before"] - 0.8667) < 1e-4
        assert abs(result["q30_rate_after"] - 0.8982) < 1e-4
        assert abs(result["gc_content"] - 0.44) < 1e-4
        assert abs(result["duplication_rate"] - 0.123) < 1e-4
        # adapter_trimmed_rate = adapter_trimmed_reads / total_reads_before
        expected_adapter_rate = 50000 / 1000000
        assert abs(result["adapter_trimmed_rate"] - expected_adapter_rate) < 1e-4

    @pytest.mark.unit
    def test_parse_json_no_adapter(self, mock_fastp_json_no_adapter: dict) -> None:
        """parse_fastp_json() handles missing adapter_cutting gracefully."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from parse_fastp import parse_fastp_json

            result = parse_fastp_json(
                mock_fastp_json_no_adapter, sample_name="sample2"
            )
        finally:
            sys.path = original_path

        assert result["sample"] == "sample2"
        assert result["total_reads_before"] == 500000
        assert result["adapter_trimmed_rate"] == 0.0

    @pytest.mark.unit
    def test_parse_json_has_all_columns(self, mock_fastp_json: dict) -> None:
        """Parsed result must contain all expected columns."""
        original_path = sys.path.copy()
        try:
            sys.path.insert(0, str(BIN_DIR))
            from parse_fastp import parse_fastp_json

            result = parse_fastp_json(mock_fastp_json, sample_name="test")
        finally:
            sys.path = original_path

        for col in EXPECTED_COLUMNS:
            assert col in result, f"Missing column: {col}"

    @pytest.mark.unit
    def test_output_tsv_format(
        self, tmp_dir: Path, mock_fastp_json_file: Path
    ) -> None:
        """CLI invocation must produce a valid TSV with correct header."""
        output_tsv = tmp_dir / "qc_summary.tsv"

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_FASTP_SCRIPT),
                str(mock_fastp_json_file),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"parse_fastp.py failed: {result.stderr}"
        )
        assert output_tsv.exists(), "Output TSV not created"

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        assert len(rows) == 1
        assert list(rows[0].keys()) == EXPECTED_COLUMNS

    @pytest.mark.unit
    def test_output_tsv_multiple_samples(self, tmp_dir: Path) -> None:
        """CLI must handle multiple JSON files and produce multi-row TSV."""
        # Create two mock JSON files
        for i, name in enumerate(["sampleA", "sampleB"], start=1):
            data = {
                "summary": {
                    "before_filtering": {
                        "total_reads": 100000 * i,
                        "total_bases": 15000000 * i,
                        "q20_bases": 14000000 * i,
                        "q30_bases": 13000000 * i,
                        "q20_rate": 0.93,
                        "q30_rate": 0.87,
                        "gc_content": 0.45,
                    },
                    "after_filtering": {
                        "total_reads": 95000 * i,
                        "total_bases": 14250000 * i,
                        "q20_bases": 13800000 * i,
                        "q30_bases": 12800000 * i,
                        "q20_rate": 0.97,
                        "q30_rate": 0.90,
                        "gc_content": 0.44,
                    },
                },
                "duplication": {"rate": 0.1},
                "adapter_cutting": {
                    "adapter_trimmed_reads": 5000 * i,
                    "adapter_trimmed_bases": 75000 * i,
                },
                "filtering_result": {
                    "passed_filter_reads": 95000 * i,
                    "low_quality_reads": 4000 * i,
                    "too_many_N_reads": 0,
                    "too_short_reads": 1000 * i,
                    "too_long_reads": 0,
                },
            }
            json_path = tmp_dir / f"{name}.fastp.json"
            json_path.write_text(json.dumps(data))

        output_tsv = tmp_dir / "qc_summary.tsv"
        json_files = sorted(tmp_dir.glob("*.fastp.json"))

        result = subprocess.run(
            [
                sys.executable,
                str(PARSE_FASTP_SCRIPT),
                *[str(f) for f in json_files],
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"parse_fastp.py failed: {result.stderr}"

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            rows = list(reader)

        assert len(rows) == 2
        sample_names = [r["sample"] for r in rows]
        assert "sampleA" in sample_names
        assert "sampleB" in sample_names

    @pytest.mark.unit
    def test_output_values_are_numeric(
        self, tmp_dir: Path, mock_fastp_json_file: Path
    ) -> None:
        """All numeric columns in TSV must be parseable as numbers."""
        output_tsv = tmp_dir / "qc_summary.tsv"

        subprocess.run(
            [
                sys.executable,
                str(PARSE_FASTP_SCRIPT),
                str(mock_fastp_json_file),
                "--output",
                str(output_tsv),
            ],
            capture_output=True,
            text=True,
        )

        with open(output_tsv) as f:
            reader = csv.DictReader(f, delimiter="\t")
            row = next(reader)

        numeric_cols = [c for c in EXPECTED_COLUMNS if c != "sample"]
        for col in numeric_cols:
            try:
                float(row[col])
            except ValueError:
                pytest.fail(f"Column '{col}' value '{row[col]}' is not numeric")
