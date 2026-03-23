# @TASK T5.1 - Dashboard generation unit tests
# @SPEC docs/planning/05-design-system.md#2-대시보드-설계
# @SPEC docs/planning/02-trd.md#2.3-보고서-시각화
"""Unit tests for bin/generate_dashboard.py.

Test strategy (TDD):
  - Tests are written BEFORE implementation.
  - Each test asserts a specific contract of generate_dashboard.py.
  - Mock TSV input data is written to tmp files; real HTML output is parsed.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT = (
    Path(__file__).parent.parent.parent / "bin" / "generate_dashboard.py"
)
TEMPLATE = (
    Path(__file__).parent.parent.parent / "assets" / "dashboard_template.html"
)

# Minimal mock TSV fixtures -----------------------------------------------

BIGTABLE_TSV = textwrap.dedent("""\
    seq_id\tsample\tseq_type\tlength\tdetection_method\tdetection_score\ttaxid\tdomain\tphylum\tclass\torder\tfamily\tgenus\tspecies\tictv_classification\tbaltimore_group\tcount\trpm\tcoverage
    viral_contig_001\tsample_A\tcontig\t2847\tboth\t0.95\t10239\tVirus\tNegarnaviricota\tPolyploviricetes\tMononegavirales\tFiloviridae\tEbolavirus\tZaire ebolavirus\tFiloviridae; Ebolavirus\tGroup V (-ssRNA)\t245\t1230.5\t18.7
    read_contig_002\tsample_A\tread\t150\tdiamond\t0.87\t11320\tVirus\tPisuviricota\tHerviviricetes\tPicornavirales\tPicornaviridae\tEnterovirus\tEnterovirus A\tPicornaviridae; Enterovirus\tGroup IV (+ssRNA)\t128\t644.2\t0.0
    viral_contig_003\tsample_B\tcontig\t1524\tgenomaD\t0.92\t10566\tVirus\tNucleocytoviricota\tMegaviricetes\tImitervirales\tAsfarviridae\tAsfarvirus\tAfrican swine fever virus\tAsfarviridae; Asfarvirus\tGroup I (dsDNA)\t89\t450.3\t12.2
    viral_contig_005\tsample_C\tcontig\t3200\tboth\t0.93\t11676\tVirus\tNucleocytoviricota\tMegaviricetes\tMegavirales\tPoxviridae\tOrthopoxvirus\tVaccinia virus\tPoxviridae; Orthopoxvirus\tGroup I (dsDNA)\t312\t1567.3\t25.4
""")

MATRIX_TSV = textwrap.dedent("""\
    taxon\ttaxid\trank\tsample_A\tsample_B\tsample_C
    Ebolavirus\t40566\tgenus\t1230.5\t0.0\t0.0
    Enterovirus\t12059\tgenus\t644.2\t0.0\t0.0
    Asfarvirus\t40359\tgenus\t0.0\t450.3\t0.0
    Orthopoxvirus\t10244\tgenus\t0.0\t0.0\t1567.3
""")

ALPHA_TSV = textwrap.dedent("""\
    sample\tobserved_species\tshannon\tsimpson\tchao1\tpielou_evenness
    sample_A\t2\t0.693\t0.667\t2.0\t0.5
    sample_B\t1\t0.0\t0.0\t1.0\t0.0
    sample_C\t1\t0.0\t0.0\t1.0\t0.0
""")

BETA_TSV = textwrap.dedent("""\
    \tsample_A\tsample_B\tsample_C
    sample_A\t0.0\t0.45\t0.89
    sample_B\t0.45\t0.0\t0.72
    sample_C\t0.89\t0.72\t0.0
""")

PCOA_TSV = textwrap.dedent("""\
    sample\tPC1\tPC2\tPC3
    sample_A\t0.5\t0.2\t-0.1
    sample_B\t-0.3\t0.4\t0.0
    sample_C\t-0.2\t-0.6\t0.1
""")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_inputs(tmp_path: Path) -> dict[str, Path]:
    """Write all mock TSV files to a temporary directory."""
    files = {
        "bigtable": tmp_path / "bigtable.tsv",
        "matrix": tmp_path / "sample_taxon_matrix.tsv",
        "alpha": tmp_path / "alpha_diversity.tsv",
        "beta": tmp_path / "beta_diversity.tsv",
        "pcoa": tmp_path / "pcoa_coordinates.tsv",
        "output": tmp_path / "dashboard.html",
    }
    files["bigtable"].write_text(BIGTABLE_TSV)
    files["matrix"].write_text(MATRIX_TSV)
    files["alpha"].write_text(ALPHA_TSV)
    files["beta"].write_text(BETA_TSV)
    files["pcoa"].write_text(PCOA_TSV)
    return files


def _run_generate(inputs: dict[str, Path]) -> Path:
    """Invoke generate_dashboard.py via subprocess and return output path."""
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--bigtable", str(inputs["bigtable"]),
        "--matrix",   str(inputs["matrix"]),
        "--alpha",    str(inputs["alpha"]),
        "--beta",     str(inputs["beta"]),
        "--pcoa",     str(inputs["pcoa"]),
        "--output",   str(inputs["output"]),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"generate_dashboard.py failed:\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
    return inputs["output"]


# ---------------------------------------------------------------------------
# Tests: script existence
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_script_exists():
    """generate_dashboard.py must exist at bin/generate_dashboard.py."""
    assert SCRIPT.exists(), f"Script not found: {SCRIPT}"


@pytest.mark.unit
def test_template_exists():
    """assets/dashboard_template.html must exist."""
    assert TEMPLATE.exists(), f"Template not found: {TEMPLATE}"


# ---------------------------------------------------------------------------
# Tests: HTML generation
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_output_file_created(tmp_inputs: dict[str, Path]):
    """Running the script must create the output HTML file."""
    output = _run_generate(tmp_inputs)
    assert output.exists(), "Output dashboard.html was not created"
    assert output.stat().st_size > 0, "Output HTML is empty"


@pytest.mark.unit
def test_output_is_html(tmp_inputs: dict[str, Path]):
    """Output file must begin with a valid HTML doctype or html tag."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    lowered = content.lower().lstrip()
    assert lowered.startswith("<!doctype html") or lowered.startswith("<html"), (
        "Output file does not start with an HTML declaration"
    )


# ---------------------------------------------------------------------------
# Tests: Plotly.js CDN
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_plotly_cdn_present(tmp_inputs: dict[str, Path]):
    """Output HTML must include the Plotly.js CDN <script> tag."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    assert "plotly" in content.lower(), (
        "Plotly.js CDN script tag not found in dashboard HTML"
    )
    assert "cdn.plot.ly" in content or "cdn.jsdelivr.net/npm/plotly" in content or "unpkg.com/plotly" in content, (
        "Expected a known Plotly CDN URL (cdn.plot.ly, jsdelivr, or unpkg)"
    )


# ---------------------------------------------------------------------------
# Tests: Four tabs
# ---------------------------------------------------------------------------

TAB_IDS = ["tab-overview", "tab-composition", "tab-diversity", "tab-search"]


@pytest.mark.unit
@pytest.mark.parametrize("tab_id", TAB_IDS)
def test_tab_id_present(tmp_inputs: dict[str, Path], tab_id: str):
    """Each of the four tab IDs must appear in the output HTML."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    assert tab_id in content, f"Tab ID '{tab_id}' not found in dashboard HTML"


@pytest.mark.unit
def test_all_four_tabs_present(tmp_inputs: dict[str, Path]):
    """All four tab labels (Overview, Composition, Diversity, Search) must appear."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    for label in ["Overview", "Composition", "Diversity", "Search"]:
        assert label in content, f"Tab label '{label}' not found in dashboard HTML"


# ---------------------------------------------------------------------------
# Tests: JSON data injection
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_json_data_injected(tmp_inputs: dict[str, Path]):
    """Dashboard HTML must contain a JSON data block embedded by Jinja2."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    # The template injects data as a JS variable assignment
    assert "window.__DASHBOARD_DATA__" in content or '"samples"' in content, (
        "No embedded JSON data block found in dashboard HTML"
    )


@pytest.mark.unit
def test_sample_names_in_json(tmp_inputs: dict[str, Path]):
    """Sample names from input TSV must appear in the embedded JSON."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    for sample in ["sample_A", "sample_B", "sample_C"]:
        assert sample in content, (
            f"Sample name '{sample}' not found in dashboard HTML"
        )


@pytest.mark.unit
def test_taxon_names_in_json(tmp_inputs: dict[str, Path]):
    """Taxon names from the matrix TSV must appear in the HTML."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    for taxon in ["Ebolavirus", "Enterovirus", "Asfarvirus", "Orthopoxvirus"]:
        assert taxon in content, (
            f"Taxon '{taxon}' not found in dashboard HTML"
        )


# ---------------------------------------------------------------------------
# Tests: Summary statistics (Overview tab)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_summary_stats_present(tmp_inputs: dict[str, Path]):
    """Dashboard HTML must contain summary statistic values."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    # 3 samples in mock data
    assert "3" in content, "Total sample count (3) not found in dashboard"


@pytest.mark.unit
def test_overview_sankey_div_present(tmp_inputs: dict[str, Path]):
    """Overview tab must contain a Sankey diagram div."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    assert "sankey" in content.lower(), (
        "Sankey diagram placeholder/div not found in Overview tab"
    )


# ---------------------------------------------------------------------------
# Tests: Diversity tab
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_pcoa_div_present(tmp_inputs: dict[str, Path]):
    """Diversity tab must contain a PCoA plot div."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    assert "pcoa" in content.lower(), (
        "PCoA plot div not found in Diversity tab"
    )


@pytest.mark.unit
def test_alpha_diversity_div_present(tmp_inputs: dict[str, Path]):
    """Diversity tab must contain an Alpha diversity plot div."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    assert "alpha" in content.lower(), (
        "Alpha diversity div not found in Diversity tab"
    )


# ---------------------------------------------------------------------------
# Tests: Search tab
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_search_input_present(tmp_inputs: dict[str, Path]):
    """Search tab must contain a text input element for species search."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    assert 'type="text"' in content or 'type=\\"text\\"' in content or "search" in content.lower(), (
        "Search input element not found in dashboard HTML"
    )


# ---------------------------------------------------------------------------
# Tests: Standalone (no external JS other than Plotly CDN)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_no_external_js_except_plotly(tmp_inputs: dict[str, Path]):
    """Dashboard must not load any external JS apart from Plotly CDN."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    # Find all <script src="..."> or <script src='...'>
    external_scripts = re.findall(
        r'<script[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE
    )
    for src in external_scripts:
        assert "plotly" in src.lower(), (
            f"Unexpected external script found: {src}. "
            "Only Plotly CDN is allowed."
        )


# ---------------------------------------------------------------------------
# Tests: CLI help / argparse
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cli_help_exits_zero():
    """generate_dashboard.py --help must exit with code 0."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"--help returned non-zero exit code: {result.returncode}\n"
        f"STDERR: {result.stderr}"
    )


@pytest.mark.unit
def test_cli_help_contains_required_args():
    """--help output must document all required CLI arguments."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    help_text = result.stdout + result.stderr
    for arg in ["--bigtable", "--matrix", "--alpha", "--beta", "--pcoa", "--output"]:
        assert arg in help_text, (
            f"Required CLI argument '{arg}' not documented in --help output"
        )


# ---------------------------------------------------------------------------
# Tests: Template rendering (import-level, no subprocess)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_template_has_four_tab_ids():
    """dashboard_template.html must contain all four tab ID anchors."""
    content = TEMPLATE.read_text()
    for tab_id in TAB_IDS:
        assert tab_id in content, (
            f"Tab ID '{tab_id}' not found in dashboard_template.html"
        )


@pytest.mark.unit
def test_template_has_jinja2_data_placeholder():
    """dashboard_template.html must use Jinja2 variable syntax for data."""
    content = TEMPLATE.read_text()
    # Must have at least one {{ variable }} or {% block %}
    assert "{{" in content or "{%" in content, (
        "No Jinja2 template syntax found in dashboard_template.html"
    )


@pytest.mark.unit
def test_template_has_plotly_cdn():
    """dashboard_template.html must contain the Plotly.js CDN URL."""
    content = TEMPLATE.read_text()
    assert "plotly" in content.lower(), (
        "Plotly CDN not referenced in dashboard_template.html"
    )
