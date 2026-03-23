"""End-to-end structural tests for the DeepInvirus pipeline.

# @TASK T6.3 - E2E structural validation tests
# @SPEC docs/planning/02-trd.md#3-파이프라인-상세-설계
# @SPEC docs/planning/02-trd.md#3.3-출력
# @TEST tests/pipeline/test_e2e.py

Tests:
1. main.nf includes all 5 subworkflows
2. All subworkflow files exist and define the correct workflow name
3. Expected output directory structure matches TRD section 3.3
4. All Python bin/ scripts support --help flag
5. Pipeline parameters are defined correctly
6. workflow.onComplete and workflow.onError blocks exist
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_NF = PROJECT_ROOT / "main.nf"
SUBWORKFLOWS_DIR = PROJECT_ROOT / "subworkflows"
MODULES_DIR = PROJECT_ROOT / "modules" / "local"
BIN_DIR = PROJECT_ROOT / "bin"

# All 5 subworkflows that main.nf must include
REQUIRED_SUBWORKFLOWS = [
    "PREPROCESSING",
    "ASSEMBLY",
    "DETECTION",
    "CLASSIFICATION",
    "REPORTING",
]

# Subworkflow file mapping
SUBWORKFLOW_FILES = {
    "PREPROCESSING": SUBWORKFLOWS_DIR / "preprocessing.nf",
    "ASSEMBLY": SUBWORKFLOWS_DIR / "assembly.nf",
    "DETECTION": SUBWORKFLOWS_DIR / "detection.nf",
    "CLASSIFICATION": SUBWORKFLOWS_DIR / "classification.nf",
    "REPORTING": SUBWORKFLOWS_DIR / "reporting.nf",
}

# Expected output directory structure from TRD section 3.3
# Each entry is a relative path that should appear under results/
EXPECTED_OUTPUT_DIRS = [
    "qc/",
    "assembly/",
    "detection/",
    "taxonomy/",
    "diversity/",
    "figures/",
]

EXPECTED_OUTPUT_FILES = [
    "dashboard.html",
    "report.docx",
]


# ---------------------------------------------------------------------------
# Test: main.nf includes all subworkflows
# ---------------------------------------------------------------------------
class TestMainNfSubworkflowIncludes:
    """Verify main.nf includes all 5 required subworkflows."""

    @pytest.mark.unit
    def test_main_nf_exists(self) -> None:
        """main.nf must exist at project root."""
        assert MAIN_NF.exists(), f"main.nf not found at {MAIN_NF}"

    @pytest.mark.unit
    @pytest.mark.parametrize("subworkflow", REQUIRED_SUBWORKFLOWS)
    def test_main_includes_subworkflow(self, subworkflow: str) -> None:
        """main.nf must include each required subworkflow."""
        content = MAIN_NF.read_text()
        pattern = rf"include\s*\{{\s*{subworkflow}\s*\}}\s*from"
        assert re.search(pattern, content), (
            f"main.nf missing include statement for {subworkflow}"
        )

    @pytest.mark.unit
    @pytest.mark.parametrize("subworkflow", REQUIRED_SUBWORKFLOWS)
    def test_main_invokes_subworkflow(self, subworkflow: str) -> None:
        """main.nf must invoke each required subworkflow in the workflow block."""
        content = MAIN_NF.read_text()
        # Match invocation like SUBWORKFLOW( ... ) but not inside include/comment
        pattern = rf"^\s+{subworkflow}\s*\("
        assert re.search(pattern, content, re.MULTILINE), (
            f"main.nf does not invoke {subworkflow}"
        )

    @pytest.mark.unit
    def test_all_five_subworkflows_included(self) -> None:
        """main.nf must include exactly all 5 subworkflows."""
        content = MAIN_NF.read_text()
        found = []
        for sw in REQUIRED_SUBWORKFLOWS:
            if re.search(rf"include\s*\{{\s*{sw}\s*\}}", content):
                found.append(sw)
        assert len(found) == 5, (
            f"Expected 5 subworkflows, found {len(found)}: {found}"
        )


# ---------------------------------------------------------------------------
# Test: All subworkflow files exist and define correct workflow
# ---------------------------------------------------------------------------
class TestSubworkflowFiles:
    """Verify each subworkflow .nf file exists and defines the expected workflow."""

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "name,filepath",
        list(SUBWORKFLOW_FILES.items()),
    )
    def test_subworkflow_file_exists(self, name: str, filepath: Path) -> None:
        """Each subworkflow .nf file must exist."""
        assert filepath.exists(), f"{name} subworkflow file not found at {filepath}"

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "name,filepath",
        list(SUBWORKFLOW_FILES.items()),
    )
    def test_subworkflow_defines_workflow(self, name: str, filepath: Path) -> None:
        """Each subworkflow must define a workflow with the correct name."""
        content = filepath.read_text()
        assert f"workflow {name}" in content, (
            f"{filepath.name} must define 'workflow {name}'"
        )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "name,filepath",
        list(SUBWORKFLOW_FILES.items()),
    )
    def test_subworkflow_has_take_block(self, name: str, filepath: Path) -> None:
        """Each subworkflow must have a 'take:' input block."""
        content = filepath.read_text()
        assert "take:" in content, f"{filepath.name} missing 'take:' block"

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "name,filepath",
        list(SUBWORKFLOW_FILES.items()),
    )
    def test_subworkflow_has_emit_block(self, name: str, filepath: Path) -> None:
        """Each subworkflow must have an 'emit:' output block."""
        content = filepath.read_text()
        assert "emit:" in content, f"{filepath.name} missing 'emit:' block"

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "name,filepath",
        list(SUBWORKFLOW_FILES.items()),
    )
    def test_subworkflow_has_tag_annotations(self, name: str, filepath: Path) -> None:
        """Each subworkflow must have @TASK TAG annotations."""
        content = filepath.read_text()
        assert "@TASK" in content, f"{filepath.name} missing @TASK annotation"


# ---------------------------------------------------------------------------
# Test: Expected output directory structure (TRD 3.3)
# ---------------------------------------------------------------------------
class TestOutputStructure:
    """Verify pipeline output structure matches TRD specification."""

    @pytest.mark.unit
    def test_main_nf_references_outdir(self) -> None:
        """main.nf must reference params.outdir for output placement."""
        content = MAIN_NF.read_text()
        assert "params.outdir" in content, (
            "main.nf must use params.outdir"
        )

    @pytest.mark.unit
    @pytest.mark.parametrize("output_dir", EXPECTED_OUTPUT_DIRS)
    def test_output_dir_mentioned_in_trd(self, output_dir: str) -> None:
        """Each expected output directory should be documented in the TRD.

        This test validates the expected directory names against
        the TRD specification (02-trd.md section 3.3).
        """
        trd_path = PROJECT_ROOT / "docs" / "planning" / "02-trd.md"
        if not trd_path.exists():
            pytest.skip("TRD document not found")
        trd_content = trd_path.read_text()
        dir_name = output_dir.rstrip("/")
        assert dir_name in trd_content, (
            f"Output directory '{dir_name}' not documented in TRD"
        )

    @pytest.mark.unit
    @pytest.mark.parametrize("output_file", EXPECTED_OUTPUT_FILES)
    def test_output_file_mentioned_in_trd(self, output_file: str) -> None:
        """Each expected output file should be documented in the TRD."""
        trd_path = PROJECT_ROOT / "docs" / "planning" / "02-trd.md"
        if not trd_path.exists():
            pytest.skip("TRD document not found")
        trd_content = trd_path.read_text()
        assert output_file in trd_content, (
            f"Output file '{output_file}' not documented in TRD"
        )


# ---------------------------------------------------------------------------
# Test: All bin/*.py scripts support --help
# ---------------------------------------------------------------------------
class TestBinScriptsHelp:
    """Verify all Python scripts in bin/ support the --help flag."""

    @staticmethod
    def _get_bin_scripts() -> list[Path]:
        """Collect all .py files in the bin/ directory."""
        if not BIN_DIR.exists():
            return []
        return sorted(BIN_DIR.glob("*.py"))

    @pytest.mark.unit
    def test_bin_directory_exists(self) -> None:
        """bin/ directory must exist."""
        assert BIN_DIR.exists(), f"bin/ directory not found at {BIN_DIR}"

    @pytest.mark.unit
    def test_bin_has_python_scripts(self) -> None:
        """bin/ must contain at least one Python script."""
        scripts = self._get_bin_scripts()
        assert len(scripts) > 0, "No Python scripts found in bin/"

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "script",
        [
            pytest.param(s, id=s.name)
            for s in sorted((PROJECT_ROOT / "bin").glob("*.py"))
            if s.is_file()
        ] if (PROJECT_ROOT / "bin").exists() else [],
    )
    def test_bin_script_supports_help(self, script: Path) -> None:
        """Each bin/*.py script must support --help and exit 0."""
        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, (
            f"{script.name} --help failed with exit code {result.returncode}\n"
            f"stderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Test: Pipeline parameters
# ---------------------------------------------------------------------------
class TestPipelineParameters:
    """Verify required pipeline parameters are defined in main.nf."""

    REQUIRED_PARAMS = [
        "params.reads",
        "params.host",
        "params.outdir",
        "params.assembler",
        "params.search",
        "params.skip_ml",
        "params.db_dir",
    ]

    @pytest.mark.unit
    @pytest.mark.parametrize("param", REQUIRED_PARAMS)
    def test_parameter_defined(self, param: str) -> None:
        """Each required parameter must be defined in main.nf."""
        content = MAIN_NF.read_text()
        assert param in content, f"Missing parameter: {param}"


# ---------------------------------------------------------------------------
# Test: Lifecycle hooks
# ---------------------------------------------------------------------------
class TestLifecycleHooks:
    """Verify main.nf has workflow.onComplete and workflow.onError blocks."""

    @pytest.mark.unit
    def test_on_complete_block(self) -> None:
        """main.nf must have a workflow.onComplete block."""
        content = MAIN_NF.read_text()
        assert "workflow.onComplete" in content, (
            "Missing workflow.onComplete block"
        )

    @pytest.mark.unit
    def test_on_error_block(self) -> None:
        """main.nf must have a workflow.onError block."""
        content = MAIN_NF.read_text()
        assert "workflow.onError" in content, (
            "Missing workflow.onError block"
        )

    @pytest.mark.unit
    def test_on_complete_shows_output_dir(self) -> None:
        """workflow.onComplete should reference the output directory."""
        content = MAIN_NF.read_text()
        # Find the onComplete block content
        on_complete_match = re.search(
            r"workflow\.onComplete\s*\{(.+?)\n\}",
            content,
            re.DOTALL,
        )
        assert on_complete_match, "Cannot parse workflow.onComplete block"
        block = on_complete_match.group(1)
        assert "outdir" in block or "output" in block.lower(), (
            "onComplete should mention output directory"
        )

    @pytest.mark.unit
    def test_on_error_shows_work_dir(self) -> None:
        """workflow.onError should reference the work directory for debugging."""
        content = MAIN_NF.read_text()
        on_error_match = re.search(
            r"workflow\.onError\s*\{(.+?)\n\}",
            content,
            re.DOTALL,
        )
        assert on_error_match, "Cannot parse workflow.onError block"
        block = on_error_match.group(1)
        assert "workDir" in block or "work" in block.lower(), (
            "onError should reference work directory"
        )


# ---------------------------------------------------------------------------
# Test: Subworkflow channel flow (integration check)
# ---------------------------------------------------------------------------
class TestChannelFlow:
    """Verify correct channel connections between subworkflows in main.nf."""

    @pytest.mark.unit
    def test_preprocessing_feeds_assembly(self) -> None:
        """ASSEMBLY must receive PREPROCESSING output."""
        content = MAIN_NF.read_text()
        assert "PREPROCESSING.out.filtered_reads" in content, (
            "ASSEMBLY must receive PREPROCESSING.out.filtered_reads"
        )

    @pytest.mark.unit
    def test_assembly_feeds_detection(self) -> None:
        """DETECTION must receive ASSEMBLY output."""
        content = MAIN_NF.read_text()
        assert "ASSEMBLY.out.contigs" in content, (
            "DETECTION must receive ASSEMBLY.out.contigs"
        )

    @pytest.mark.unit
    def test_detection_feeds_classification(self) -> None:
        """CLASSIFICATION must receive DETECTION output."""
        content = MAIN_NF.read_text()
        assert "DETECTION.out." in content, (
            "CLASSIFICATION must receive DETECTION output"
        )

    @pytest.mark.unit
    def test_classification_feeds_reporting(self) -> None:
        """REPORTING must receive CLASSIFICATION output."""
        content = MAIN_NF.read_text()
        assert "CLASSIFICATION.out." in content, (
            "REPORTING must receive CLASSIFICATION output"
        )
