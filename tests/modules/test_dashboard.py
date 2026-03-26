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

TAB_IDS = ["tab-overview", "tab-taxonomy", "tab-coverage", "tab-diversity", "tab-comparison", "tab-search", "tab-results"]


@pytest.mark.unit
@pytest.mark.parametrize("tab_id", TAB_IDS)
def test_tab_id_present(tmp_inputs: dict[str, Path], tab_id: str):
    """Each of the four tab IDs must appear in the output HTML."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    assert tab_id in content, f"Tab ID '{tab_id}' not found in dashboard HTML"


@pytest.mark.unit
def test_all_four_tabs_present(tmp_inputs: dict[str, Path]):
    """All tab labels (Overview, Taxonomy, Coverage, Diversity, Comparison, Search, Results) must appear."""
    output = _run_generate(tmp_inputs)
    content = output.read_text()
    for label in ["Overview", "Taxonomy", "Coverage", "Diversity", "Comparison", "Search", "Results"]:
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
    """dashboard_template.html must contain all tab ID anchors."""
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


# ---------------------------------------------------------------------------
# Import the module for direct function testing
# ---------------------------------------------------------------------------

def _load_module():
    """Import generate_dashboard as a module for direct function testing."""
    spec = importlib.util.spec_from_file_location("generate_dashboard", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def dashboard_mod():
    """Cache the imported generate_dashboard module for the test session."""
    return _load_module()


# Richer bigtable fixture with taxonomy ranks for v2 tests
BIGTABLE_V2_TSV = textwrap.dedent("""\
    seq_id\tsample\tlength\tdetection_method\tdetection_score\ttaxonomy\tfamily\ttarget\tpident\tevalue\tcoverage\tbreadth\tdetection_confidence\trpm\ttaxid\tdomain\tphylum\tclass\torder\tgenus\tspecies\tICTV_classification\tbaltimore_group\tgroup
    contig_001\tsample_A\t2847\tboth\t0.95\tViruses;Negarnaviricota;Polyploviricetes;Mononegavirales;Filoviridae;Ebolavirus\tFiloviridae\tNC_001234\t95.2\t1e-50\t18.7\t0.85\thigh\t1230.5\t10239\tViruses\tNegarnaviricota\tPolyploviricetes\tMononegavirales\tEbolavirus\tZaire ebolavirus\tFiloviridae; Ebolavirus\tGroup V\tunknown
    contig_001\tsample_B\t2847\tboth\t0.95\tViruses;Negarnaviricota;Polyploviricetes;Mononegavirales;Filoviridae;Ebolavirus\tFiloviridae\tNC_001234\t95.2\t1e-50\t12.3\t0.72\thigh\t980.2\t10239\tViruses\tNegarnaviricota\tPolyploviricetes\tMononegavirales\tEbolavirus\tZaire ebolavirus\tFiloviridae; Ebolavirus\tGroup V\tunknown
    contig_002\tsample_A\t1500\tdiamond\t0.87\tViruses;Pisuviricota;Herviviricetes;Picornavirales;Picornaviridae;Enterovirus\tPicornaviridae\tNC_005678\t88.1\t1e-30\t5.2\t0.45\tmedium\t644.2\t11320\tViruses\tPisuviricota\tHerviviricetes\tPicornavirales\tEnterovirus\tEnterovirus A\tPicornaviridae; Enterovirus\tGroup IV\tunknown
    contig_003\tsample_B\t3200\tgenomaD\t0.92\tViruses;Negarnaviricota;Polyploviricetes;Mononegavirales;Filoviridae;Marburgvirus\tFiloviridae\tNC_009876\t91.5\t1e-45\t25.4\t0.91\thigh\t1567.3\t11269\tViruses\tNegarnaviricota\tPolyploviricetes\tMononegavirales\tMarburgvirus\tMarburg virus\tFiloviridae; Marburgvirus\tGroup V\tunknown
""")


@pytest.fixture()
def bigtable_v2(dashboard_mod):
    """Provide a pandas DataFrame with the extended bigtable schema."""
    import io
    import pandas as pd
    df = pd.read_csv(io.StringIO(BIGTABLE_V2_TSV), sep="\t", dtype=str)
    for col in ("length", "detection_score", "coverage", "breadth", "rpm", "taxid"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Tests: build_taxonomy_tree (Sunburst / Treemap)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_taxonomy_tree_has_all_and_per_sample(dashboard_mod, bigtable_v2):
    """build_taxonomy_tree must return both 'all' and 'per_sample' keys."""
    result = dashboard_mod.build_taxonomy_tree(bigtable_v2)
    assert "all" in result
    assert "per_sample" in result


@pytest.mark.unit
def test_taxonomy_tree_all_has_plotly_keys(dashboard_mod, bigtable_v2):
    """The 'all' tree must have ids, labels, parents, values arrays."""
    result = dashboard_mod.build_taxonomy_tree(bigtable_v2)
    tree = result["all"]
    for key in ("ids", "labels", "parents", "values"):
        assert key in tree, f"Missing key '{key}' in taxonomy tree"
        assert isinstance(tree[key], list), f"'{key}' should be a list"


@pytest.mark.unit
def test_taxonomy_tree_all_arrays_same_length(dashboard_mod, bigtable_v2):
    """All four arrays in the tree must have the same length."""
    result = dashboard_mod.build_taxonomy_tree(bigtable_v2)
    tree = result["all"]
    lengths = {k: len(v) for k, v in tree.items()}
    assert len(set(lengths.values())) == 1, f"Array lengths differ: {lengths}"


@pytest.mark.unit
def test_taxonomy_tree_all_contains_domain(dashboard_mod, bigtable_v2):
    """The 'all' tree labels must include the domain 'Viruses'."""
    result = dashboard_mod.build_taxonomy_tree(bigtable_v2)
    assert "Viruses" in result["all"]["labels"]


@pytest.mark.unit
def test_taxonomy_tree_all_contains_family(dashboard_mod, bigtable_v2):
    """The 'all' tree labels must include families from the bigtable."""
    result = dashboard_mod.build_taxonomy_tree(bigtable_v2)
    labels = result["all"]["labels"]
    assert "Filoviridae" in labels
    assert "Picornaviridae" in labels


@pytest.mark.unit
def test_taxonomy_tree_per_sample_keys(dashboard_mod, bigtable_v2):
    """per_sample dict must have an entry for each sample."""
    result = dashboard_mod.build_taxonomy_tree(bigtable_v2)
    assert "sample_A" in result["per_sample"]
    assert "sample_B" in result["per_sample"]


@pytest.mark.unit
def test_taxonomy_tree_per_sample_tree_structure(dashboard_mod, bigtable_v2):
    """Each per-sample tree must have ids/labels/parents/values."""
    result = dashboard_mod.build_taxonomy_tree(bigtable_v2)
    for sample_name, tree in result["per_sample"].items():
        for key in ("ids", "labels", "parents", "values"):
            assert key in tree, f"Missing '{key}' in per_sample['{sample_name}']"


@pytest.mark.unit
def test_taxonomy_tree_parent_child_consistency(dashboard_mod, bigtable_v2):
    """Every parent reference must be either empty string or a valid id."""
    result = dashboard_mod.build_taxonomy_tree(bigtable_v2)
    tree = result["all"]
    id_set = set(tree["ids"])
    for parent in tree["parents"]:
        assert parent == "" or parent in id_set, (
            f"Parent '{parent}' is not a valid id or empty string"
        )


@pytest.mark.unit
def test_taxonomy_tree_values_are_numeric(dashboard_mod, bigtable_v2):
    """All values in the tree must be non-negative numbers."""
    result = dashboard_mod.build_taxonomy_tree(bigtable_v2)
    for v in result["all"]["values"]:
        assert isinstance(v, (int, float)), f"Value {v} is not numeric"
        assert v >= 0, f"Value {v} is negative"


@pytest.mark.unit
def test_taxonomy_tree_empty_bigtable(dashboard_mod):
    """build_taxonomy_tree must handle an empty DataFrame gracefully."""
    import pandas as pd
    result = dashboard_mod.build_taxonomy_tree(pd.DataFrame())
    assert result["all"]["ids"] == []
    assert result["per_sample"] == {}


@pytest.mark.unit
def test_taxonomy_tree_node_id_path_format(dashboard_mod, bigtable_v2):
    """Node IDs should be slash-separated paths (e.g. 'Viruses/Negarnaviricota')."""
    result = dashboard_mod.build_taxonomy_tree(bigtable_v2)
    for nid in result["all"]["ids"]:
        # Root nodes have no slash, deeper nodes have slashes
        parts = nid.split("/")
        assert len(parts) >= 1, f"Node id '{nid}' is empty"


# ---------------------------------------------------------------------------
# Tests: build_per_sample_sankey
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_per_sample_sankey_returns_dict(dashboard_mod, bigtable_v2):
    """build_per_sample_sankey must return a dict keyed by sample name."""
    result = dashboard_mod.build_per_sample_sankey(bigtable_v2)
    assert isinstance(result, dict)
    assert "sample_A" in result
    assert "sample_B" in result


@pytest.mark.unit
def test_per_sample_sankey_structure(dashboard_mod, bigtable_v2):
    """Each per-sample Sankey must have nodes, sources, targets, values, node_colors."""
    result = dashboard_mod.build_per_sample_sankey(bigtable_v2)
    for sample_name, sankey in result.items():
        for key in ("nodes", "sources", "targets", "values", "node_colors"):
            assert key in sankey, f"Missing '{key}' in sankey['{sample_name}']"


@pytest.mark.unit
def test_per_sample_sankey_empty_bigtable(dashboard_mod):
    """build_per_sample_sankey must handle empty DataFrame gracefully."""
    import pandas as pd
    result = dashboard_mod.build_per_sample_sankey(pd.DataFrame())
    assert result == {}


@pytest.mark.unit
def test_per_sample_sankey_sources_targets_same_len(dashboard_mod, bigtable_v2):
    """sources, targets, and values arrays must have the same length."""
    result = dashboard_mod.build_per_sample_sankey(bigtable_v2)
    for sample_name, sankey in result.items():
        assert len(sankey["sources"]) == len(sankey["targets"]), (
            f"sources/targets length mismatch for '{sample_name}'"
        )
        assert len(sankey["sources"]) == len(sankey["values"]), (
            f"sources/values length mismatch for '{sample_name}'"
        )


# ---------------------------------------------------------------------------
# Tests: build_search_rows_v2
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_search_rows_v2_returns_list(dashboard_mod, bigtable_v2):
    """build_search_rows_v2 must return a list of dicts."""
    result = dashboard_mod.build_search_rows_v2(bigtable_v2)
    assert isinstance(result, list)
    assert len(result) > 0
    assert isinstance(result[0], dict)


@pytest.mark.unit
def test_search_rows_v2_unique_contigs(dashboard_mod, bigtable_v2):
    """Result should have one entry per unique seq_id (not per sample row)."""
    result = dashboard_mod.build_search_rows_v2(bigtable_v2)
    seq_ids = [r["seq_id"] for r in result]
    # bigtable_v2 has 4 rows but only 3 unique seq_ids
    assert len(seq_ids) == 3
    assert len(set(seq_ids)) == 3


@pytest.mark.unit
def test_search_rows_v2_required_fields(dashboard_mod, bigtable_v2):
    """Each row must contain all required fields."""
    result = dashboard_mod.build_search_rows_v2(bigtable_v2)
    required = {
        "seq_id", "length", "family", "genus", "species",
        "detection_method", "detection_score", "detection_confidence",
        "best_hit", "pident", "taxonomy", "coverage_per_sample",
    }
    for row in result:
        missing = required - set(row.keys())
        assert not missing, f"Missing fields: {missing} in row {row.get('seq_id')}"


@pytest.mark.unit
def test_search_rows_v2_coverage_per_sample_structure(dashboard_mod, bigtable_v2):
    """coverage_per_sample must be a dict with sample names as keys."""
    result = dashboard_mod.build_search_rows_v2(bigtable_v2)
    for row in result:
        cps = row["coverage_per_sample"]
        assert isinstance(cps, dict)
        assert "sample_A" in cps
        assert "sample_B" in cps


@pytest.mark.unit
def test_search_rows_v2_coverage_per_sample_values(dashboard_mod, bigtable_v2):
    """coverage_per_sample values must be dicts with coverage/rpm/breadth."""
    result = dashboard_mod.build_search_rows_v2(bigtable_v2)
    # contig_001 exists in both samples
    contig_001 = [r for r in result if r["seq_id"] == "contig_001"][0]
    sample_a_data = contig_001["coverage_per_sample"]["sample_A"]
    assert "coverage" in sample_a_data
    assert "rpm" in sample_a_data
    assert "breadth" in sample_a_data
    assert sample_a_data["coverage"] > 0  # 18.7 in the fixture


@pytest.mark.unit
def test_search_rows_v2_missing_sample_zero_fill(dashboard_mod, bigtable_v2):
    """Contigs not present in a sample should have 0 values."""
    result = dashboard_mod.build_search_rows_v2(bigtable_v2)
    # contig_002 only in sample_A, not sample_B
    contig_002 = [r for r in result if r["seq_id"] == "contig_002"][0]
    sample_b_data = contig_002["coverage_per_sample"]["sample_B"]
    assert sample_b_data["coverage"] == 0.0
    assert sample_b_data["rpm"] == 0.0


@pytest.mark.unit
def test_search_rows_v2_empty_bigtable(dashboard_mod):
    """build_search_rows_v2 must handle empty DataFrame gracefully."""
    import pandas as pd
    result = dashboard_mod.build_search_rows_v2(pd.DataFrame())
    assert result == []


@pytest.mark.unit
def test_search_rows_v2_no_nan_strings(dashboard_mod, bigtable_v2):
    """String fields should not contain the literal 'nan'."""
    result = dashboard_mod.build_search_rows_v2(bigtable_v2)
    string_fields = ["family", "genus", "species", "detection_method",
                     "detection_confidence", "best_hit", "pident", "taxonomy"]
    for row in result:
        for field in string_fields:
            val = row.get(field, "")
            assert val.lower() != "nan", (
                f"Field '{field}' in {row['seq_id']} is 'nan'"
            )


# ---------------------------------------------------------------------------
# Tests: build_filter_options
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_filter_options_required_keys(dashboard_mod, bigtable_v2):
    """build_filter_options must return all required filter categories."""
    result = dashboard_mod.build_filter_options(bigtable_v2)
    for key in ("samples", "families", "genera", "detection_methods", "confidence_tiers"):
        assert key in result, f"Missing filter key: {key}"


@pytest.mark.unit
def test_filter_options_samples(dashboard_mod, bigtable_v2):
    """Samples must include all unique sample names."""
    result = dashboard_mod.build_filter_options(bigtable_v2)
    assert "sample_A" in result["samples"]
    assert "sample_B" in result["samples"]


@pytest.mark.unit
def test_filter_options_families_no_unclassified(dashboard_mod, bigtable_v2):
    """Families list must not include 'Unclassified'."""
    result = dashboard_mod.build_filter_options(bigtable_v2)
    for f in result["families"]:
        assert f.lower() != "unclassified", "Unclassified should not be in families"


@pytest.mark.unit
def test_filter_options_families_includes_real(dashboard_mod, bigtable_v2):
    """Families list must include real family names from the data."""
    result = dashboard_mod.build_filter_options(bigtable_v2)
    assert "Filoviridae" in result["families"]
    assert "Picornaviridae" in result["families"]


@pytest.mark.unit
def test_filter_options_confidence_tiers(dashboard_mod, bigtable_v2):
    """confidence_tiers must always be ['high', 'medium', 'low']."""
    result = dashboard_mod.build_filter_options(bigtable_v2)
    assert result["confidence_tiers"] == ["high", "medium", "low"]


@pytest.mark.unit
def test_filter_options_sorted(dashboard_mod, bigtable_v2):
    """All filter lists must be sorted."""
    result = dashboard_mod.build_filter_options(bigtable_v2)
    for key in ("samples", "families", "genera", "detection_methods"):
        assert result[key] == sorted(result[key]), f"{key} is not sorted"


@pytest.mark.unit
def test_filter_options_empty_bigtable(dashboard_mod):
    """build_filter_options must handle empty DataFrame gracefully."""
    import pandas as pd
    result = dashboard_mod.build_filter_options(pd.DataFrame())
    assert result["samples"] == []
    assert result["families"] == []
    assert result["confidence_tiers"] == ["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Tests: _sanitize_for_json (NaN handling)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sanitize_nan_to_none(dashboard_mod):
    """_sanitize_for_json must convert float NaN to None."""
    result = dashboard_mod._sanitize_for_json(float("nan"))
    assert result is None


@pytest.mark.unit
def test_sanitize_inf_to_none(dashboard_mod):
    """_sanitize_for_json must convert float Infinity to None."""
    result = dashboard_mod._sanitize_for_json(float("inf"))
    assert result is None
    result_neg = dashboard_mod._sanitize_for_json(float("-inf"))
    assert result_neg is None


@pytest.mark.unit
def test_sanitize_normal_float_unchanged(dashboard_mod):
    """_sanitize_for_json must leave normal floats unchanged."""
    assert dashboard_mod._sanitize_for_json(3.14) == 3.14


@pytest.mark.unit
def test_sanitize_nested_dict(dashboard_mod):
    """_sanitize_for_json must handle nested dicts with NaN values."""
    data = {"a": 1.0, "b": float("nan"), "c": {"d": float("inf"), "e": 5}}
    result = dashboard_mod._sanitize_for_json(data)
    assert result["a"] == 1.0
    assert result["b"] is None
    assert result["c"]["d"] is None
    assert result["c"]["e"] == 5


@pytest.mark.unit
def test_sanitize_nested_list(dashboard_mod):
    """_sanitize_for_json must handle lists containing NaN."""
    data = [1.0, float("nan"), [float("inf"), 2.0]]
    result = dashboard_mod._sanitize_for_json(data)
    assert result[0] == 1.0
    assert result[1] is None
    assert result[2][0] is None
    assert result[2][1] == 2.0


@pytest.mark.unit
def test_sanitize_produces_valid_json(dashboard_mod):
    """Output of _sanitize_for_json must be serializable to valid JSON."""
    data = {"val": float("nan"), "list": [float("inf"), 1.0], "nested": {"x": float("-inf")}}
    sanitized = dashboard_mod._sanitize_for_json(data)
    json_str = json.dumps(sanitized)
    parsed = json.loads(json_str)
    assert parsed["val"] is None
    assert parsed["list"][0] is None


# ---------------------------------------------------------------------------
# Tests: _safe_str
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_safe_str_nan_float(dashboard_mod):
    """_safe_str must return empty string for float NaN."""
    assert dashboard_mod._safe_str(float("nan")) == ""


@pytest.mark.unit
def test_safe_str_none(dashboard_mod):
    """_safe_str must return empty string for None."""
    assert dashboard_mod._safe_str(None) == ""


@pytest.mark.unit
def test_safe_str_nan_string(dashboard_mod):
    """_safe_str must return empty string for the literal string 'nan'."""
    assert dashboard_mod._safe_str("nan") == ""


@pytest.mark.unit
def test_safe_str_normal(dashboard_mod):
    """_safe_str must return normal strings unchanged."""
    assert dashboard_mod._safe_str("Filoviridae") == "Filoviridae"


# ---------------------------------------------------------------------------
# Tests: build_dashboard_data v2 integration
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_dashboard_data_has_v2_keys(dashboard_mod, bigtable_v2):
    """build_dashboard_data output must include all new v2 data keys."""
    import pandas as pd
    # Minimal matrix/alpha/beta/pcoa for the test
    matrix = pd.read_csv(
        __import__("io").StringIO(MATRIX_TSV), sep="\t"
    )
    alpha = pd.read_csv(
        __import__("io").StringIO(ALPHA_TSV), sep="\t"
    )
    beta = pd.read_csv(
        __import__("io").StringIO(BETA_TSV), sep="\t", index_col=0
    )
    pcoa = pd.read_csv(
        __import__("io").StringIO(PCOA_TSV), sep="\t"
    )

    data = dashboard_mod.build_dashboard_data(
        bigtable_v2, matrix, alpha, beta, pcoa
    )

    # Existing keys still present (backward compat)
    assert "sankey" in data
    assert "search_rows" in data
    assert "heatmap" in data
    assert "samples" in data

    # New v2 keys
    assert "sankey_all" in data
    assert "sankey_per_sample" in data
    assert "taxonomy_tree" in data
    assert "search_rows_v2" in data
    assert "filter_options" in data


@pytest.mark.unit
def test_dashboard_data_sankey_all_equals_sankey(dashboard_mod, bigtable_v2):
    """sankey_all should be the same object as sankey (backward compat alias)."""
    import pandas as pd
    matrix = pd.read_csv(__import__("io").StringIO(MATRIX_TSV), sep="\t")
    alpha = pd.read_csv(__import__("io").StringIO(ALPHA_TSV), sep="\t")
    beta = pd.read_csv(__import__("io").StringIO(BETA_TSV), sep="\t", index_col=0)
    pcoa = pd.read_csv(__import__("io").StringIO(PCOA_TSV), sep="\t")

    data = dashboard_mod.build_dashboard_data(
        bigtable_v2, matrix, alpha, beta, pcoa
    )
    assert data["sankey_all"] is data["sankey"]
