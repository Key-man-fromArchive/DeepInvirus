"""Tests for A4: Dual-taxid taxonomy -- Diamond + MMseqs2 lineage merge.

# @TASK A4 - Dual-taxid taxonomy: Diamond + MMseqs2 lineage merge
# @SPEC docs/planning/10-workplan-v2-report-framework.md#Phase-A
# @TEST tests/modules/test_dual_taxid.py

Covers:
- NCBI nodes.dmp / names.dmp loading
- taxid_to_lineage tree walk
- build_diamond_lineage_map from detection DataFrame
- build_bigtable Diamond lineage backfill integration
- taxonomy_source tracking (mmseqs2 / diamond / both / unknown)
- Graceful degradation when taxonomy files are absent
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pandas as pd
import pytest

# Add bin/ to sys.path for direct import
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = PROJECT_ROOT / "bin"
sys.path.insert(0, str(BIN_DIR))

from merge_results import (
    build_bigtable,
    build_diamond_lineage_map,
    load_ncbi_names,
    load_ncbi_nodes,
    taxid_to_lineage,
)


# ---------------------------------------------------------------------------
# Fixtures: mock NCBI taxonomy data
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir(tmp_path):
    """Use pytest built-in tmp_path."""
    return tmp_path


@pytest.fixture
def mock_nodes_dmp(tmp_dir: Path) -> Path:
    """Create a minimal nodes.dmp with viral taxonomy hierarchy.

    Hierarchy:
        1 (root) -> 10239 (Viruses, superkingdom)
                      -> 2559587 (Riboviria, clade)
                        -> 2732396 (Orthornavirae, kingdom)
                          -> 2732408 (Kitrinoviricota, phylum)
                            -> 2732505 (Flasuviricetes, class)
                              -> 76804 (Amarillovirales, order)
                                -> 11050 (Flaviviridae, family)
                                  -> 11051 (Flavivirus, genus)
                                    -> 12637 (Dengue virus, species)
                      -> 35237 (Duplodnaviria, clade)
                        -> 2731341 (Heunggongvirae, kingdom)
                          -> 2731360 (Uroviricota, phylum)
                            -> 2731618 (Caudoviricetes, class)
                              -> 28883 (Caudovirales, order)
                                -> 10699 (Siphoviridae, family)
                                  -> 186765 (Lambdavirus, genus)
                                    -> 10710 (Lambda phage, species)
    """
    p = tmp_dir / "nodes.dmp"
    p.write_text(
        "1\t|\t1\t|\tno rank\t|\n"
        "10239\t|\t1\t|\tsuperkingdom\t|\n"
        "2559587\t|\t10239\t|\tclade\t|\n"
        "2732396\t|\t2559587\t|\tkingdom\t|\n"
        "2732408\t|\t2732396\t|\tphylum\t|\n"
        "2732505\t|\t2732408\t|\tclass\t|\n"
        "76804\t|\t2732505\t|\torder\t|\n"
        "11050\t|\t76804\t|\tfamily\t|\n"
        "11051\t|\t11050\t|\tgenus\t|\n"
        "12637\t|\t11051\t|\tspecies\t|\n"
        "35237\t|\t10239\t|\tclade\t|\n"
        "2731341\t|\t35237\t|\tkingdom\t|\n"
        "2731360\t|\t2731341\t|\tphylum\t|\n"
        "2731618\t|\t2731360\t|\tclass\t|\n"
        "28883\t|\t2731618\t|\torder\t|\n"
        "10699\t|\t28883\t|\tfamily\t|\n"
        "186765\t|\t10699\t|\tgenus\t|\n"
        "10710\t|\t186765\t|\tspecies\t|\n"
    )
    return p


@pytest.fixture
def mock_names_dmp(tmp_dir: Path) -> Path:
    """Create a minimal names.dmp matching mock_nodes_dmp."""
    p = tmp_dir / "names.dmp"
    p.write_text(
        "1\t|\troot\t|\t\t|\tscientific name\t|\n"
        "10239\t|\tViruses\t|\t\t|\tscientific name\t|\n"
        "2559587\t|\tRiboviria\t|\t\t|\tscientific name\t|\n"
        "2732396\t|\tOrthornavirae\t|\t\t|\tscientific name\t|\n"
        "2732408\t|\tKitrinoviricota\t|\t\t|\tscientific name\t|\n"
        "2732505\t|\tFlasuviricetes\t|\t\t|\tscientific name\t|\n"
        "76804\t|\tAmarillovirales\t|\t\t|\tscientific name\t|\n"
        "11050\t|\tFlaviviridae\t|\t\t|\tscientific name\t|\n"
        "11051\t|\tFlavivirus\t|\t\t|\tscientific name\t|\n"
        "12637\t|\tDengue virus\t|\t\t|\tscientific name\t|\n"
        "35237\t|\tDuplodnaviria\t|\t\t|\tscientific name\t|\n"
        "2731341\t|\tHeunggongvirae\t|\t\t|\tscientific name\t|\n"
        "2731360\t|\tUroviricota\t|\t\t|\tscientific name\t|\n"
        "2731618\t|\tCaudoviricetes\t|\t\t|\tscientific name\t|\n"
        "28883\t|\tCaudovirales\t|\t\t|\tscientific name\t|\n"
        "10699\t|\tSiphoviridae\t|\t\t|\tscientific name\t|\n"
        "186765\t|\tLambdavirus\t|\t\t|\tscientific name\t|\n"
        "10710\t|\tLambda phage\t|\t\t|\tscientific name\t|\n"
        # Non-scientific name entry -- should be ignored
        "10239\t|\tviral\t|\t\t|\tblast name\t|\n"
    )
    return p


@pytest.fixture
def node_map(mock_nodes_dmp: Path) -> dict[int, tuple[int, str]]:
    return load_ncbi_nodes(mock_nodes_dmp)


@pytest.fixture
def name_map(mock_names_dmp: Path) -> dict[int, str]:
    return load_ncbi_names(mock_names_dmp)


# ---------------------------------------------------------------------------
# Tests: NCBI taxonomy file loading
# ---------------------------------------------------------------------------

class TestLoadNcbiNodes:
    def test_load_valid_nodes(self, mock_nodes_dmp):
        nodes = load_ncbi_nodes(mock_nodes_dmp)
        assert len(nodes) == 18
        assert nodes[12637] == (11051, "species")
        assert nodes[11050] == (76804, "family")
        assert nodes[10239] == (1, "superkingdom")

    def test_load_missing_file(self, tmp_dir):
        nodes = load_ncbi_nodes(tmp_dir / "nonexistent.dmp")
        assert nodes == {}

    def test_load_none_path(self):
        nodes = load_ncbi_nodes(None)
        assert nodes == {}

    def test_load_directory_path(self, tmp_dir):
        nodes = load_ncbi_nodes(tmp_dir)
        assert nodes == {}


class TestLoadNcbiNames:
    def test_load_valid_names(self, mock_names_dmp):
        names = load_ncbi_names(mock_names_dmp)
        # Only scientific names should be loaded
        assert names[10239] == "Viruses"
        assert names[12637] == "Dengue virus"
        assert names[11050] == "Flaviviridae"
        # The "blast name" entry for 10239 should NOT overwrite scientific name
        assert names[10239] == "Viruses"

    def test_load_missing_file(self, tmp_dir):
        names = load_ncbi_names(tmp_dir / "nonexistent.dmp")
        assert names == {}

    def test_load_none_path(self):
        names = load_ncbi_names(None)
        assert names == {}

    def test_scientific_name_only(self, mock_names_dmp):
        """Ensure non-scientific name entries are excluded."""
        names = load_ncbi_names(mock_names_dmp)
        # Count: 18 scientific name entries
        assert len(names) == 18


# ---------------------------------------------------------------------------
# Tests: taxid_to_lineage tree walk
# ---------------------------------------------------------------------------

class TestTaxidToLineage:
    def test_dengue_virus_lineage(self, node_map, name_map):
        """Dengue virus (12637) should resolve full lineage."""
        lineage = taxid_to_lineage(12637, node_map, name_map)
        assert lineage["domain"] == "Viruses"
        assert lineage["phylum"] == "Kitrinoviricota"
        assert lineage["class"] == "Flasuviricetes"
        assert lineage["order"] == "Amarillovirales"
        assert lineage["family"] == "Flaviviridae"
        assert lineage["genus"] == "Flavivirus"
        assert lineage["species"] == "Dengue virus"

    def test_lambda_phage_lineage(self, node_map, name_map):
        """Lambda phage (10710) should resolve full lineage."""
        lineage = taxid_to_lineage(10710, node_map, name_map)
        assert lineage["domain"] == "Viruses"
        assert lineage["phylum"] == "Uroviricota"
        assert lineage["class"] == "Caudoviricetes"
        assert lineage["order"] == "Caudovirales"
        assert lineage["family"] == "Siphoviridae"
        assert lineage["genus"] == "Lambdavirus"
        assert lineage["species"] == "Lambda phage"

    def test_family_level_taxid(self, node_map, name_map):
        """Flaviviridae (11050) should resolve up to family, no genus/species."""
        lineage = taxid_to_lineage(11050, node_map, name_map)
        assert lineage["family"] == "Flaviviridae"
        assert lineage["genus"] == ""
        assert lineage["species"] == ""
        assert lineage["domain"] == "Viruses"

    def test_superkingdom_taxid(self, node_map, name_map):
        """Viruses (10239) should only set domain."""
        lineage = taxid_to_lineage(10239, node_map, name_map)
        assert lineage["domain"] == "Viruses"
        assert lineage["phylum"] == ""
        assert lineage["species"] == ""

    def test_invalid_taxid_zero(self, node_map, name_map):
        lineage = taxid_to_lineage(0, node_map, name_map)
        assert all(v == "" for v in lineage.values())

    def test_invalid_taxid_negative(self, node_map, name_map):
        lineage = taxid_to_lineage(-1, node_map, name_map)
        assert all(v == "" for v in lineage.values())

    def test_unknown_taxid(self, node_map, name_map):
        """Taxid not in nodes.dmp should return empty lineage."""
        lineage = taxid_to_lineage(999999999, node_map, name_map)
        assert all(v == "" for v in lineage.values())

    def test_empty_maps(self):
        lineage = taxid_to_lineage(12637, {}, {})
        assert all(v == "" for v in lineage.values())


# ---------------------------------------------------------------------------
# Tests: build_diamond_lineage_map
# ---------------------------------------------------------------------------

class TestBuildDiamondLineageMap:
    def test_basic_detection_to_lineage(self, node_map, name_map):
        detection = pd.DataFrame({
            "seq_id": ["contig_1", "contig_2", "contig_3"],
            "length": [1000, 2000, 3000],
            "detection_method": ["diamond", "diamond", "genomad"],
            "detection_score": [0.8, 0.9, 0.7],
            "taxonomy": ["", "", "Viruses"],
            "taxid": ["12637", "10710", "0"],
            "subject_id": ["acc1", "acc2", ""],
        })
        lineage_map = build_diamond_lineage_map(detection, node_map, name_map)
        # contig_3 has taxid=0, should not be in map
        assert "contig_3" not in lineage_map
        assert len(lineage_map) == 2
        assert lineage_map["contig_1"]["family"] == "Flaviviridae"
        assert lineage_map["contig_2"]["family"] == "Siphoviridae"

    def test_semicolon_separated_staxids(self, node_map, name_map):
        """Diamond staxids can be semicolon-separated; first is used."""
        detection = pd.DataFrame({
            "seq_id": ["contig_1"],
            "taxid": ["12637;11051;11050"],
        })
        lineage_map = build_diamond_lineage_map(detection, node_map, name_map)
        assert lineage_map["contig_1"]["species"] == "Dengue virus"

    def test_no_taxid_column(self, node_map, name_map):
        detection = pd.DataFrame({"seq_id": ["c1"], "length": [100]})
        lineage_map = build_diamond_lineage_map(detection, node_map, name_map)
        assert lineage_map == {}

    def test_all_zero_taxids(self, node_map, name_map):
        detection = pd.DataFrame({
            "seq_id": ["c1", "c2"],
            "taxid": ["0", "0"],
        })
        lineage_map = build_diamond_lineage_map(detection, node_map, name_map)
        assert lineage_map == {}


# ---------------------------------------------------------------------------
# Tests: build_bigtable integration with Diamond lineage backfill
# ---------------------------------------------------------------------------

class TestBigtableDiamondBackfill:
    """Test that build_bigtable correctly backfills empty ranks from Diamond taxid lineage."""

    @pytest.fixture
    def detection_df(self):
        return pd.DataFrame({
            "seq_id": ["contig_A", "contig_B", "contig_C"],
            "length": ["5000", "3000", "2000"],
            "detection_method": ["both", "diamond", "genomad"],
            "detection_score": ["0.95", "0.8", "0.7"],
            "taxonomy": [
                "Viruses;Riboviria;Orthornavirae;Kitrinoviricota;Flasuviricetes;Amarillovirales;Flaviviridae",
                "",
                "",
            ],
            "taxid": ["12637", "10710", "0"],
            "subject_id": ["acc_A", "acc_B", ""],
        })

    @pytest.fixture
    def empty_taxonomy_df(self):
        return pd.DataFrame(columns=["seq_id", "target", "pident", "evalue", "bitscore"])

    @pytest.fixture
    def coverage_df(self):
        return pd.DataFrame({
            "seq_id": ["contig_A", "contig_B", "contig_C"],
            "coverage": [10.0, 5.0, 2.0],
            "breadth": [0.8, 0.5, 0.3],
            "contig_length": [5000, 3000, 2000],
            "sample": ["sample1", "sample1", "sample1"],
        })

    @pytest.fixture
    def mmseqs_lineage_df(self):
        """MMseqs2 lineage only covers contig_A."""
        return pd.DataFrame({
            "seq_id": ["contig_A"],
            "taxid": ["12637"],
            "lineage": ["Viruses;Kitrinoviricota;Flasuviricetes;Amarillovirales;Flaviviridae;Flavivirus;Dengue virus"],
            "domain": ["Viruses"],
            "phylum": ["Kitrinoviricota"],
            "class": ["Flasuviricetes"],
            "order": ["Amarillovirales"],
            "family": ["Flaviviridae"],
            "genus": ["Flavivirus"],
            "species": ["Dengue virus"],
        })

    @pytest.fixture
    def empty_sample_map(self):
        return pd.DataFrame(columns=["sample", "group"])

    @pytest.fixture
    def empty_ictv(self):
        return pd.DataFrame(columns=["family", "genus", "species", "baltimore_group", "ictv_classification"])

    def test_backfill_empty_ranks_from_diamond(
        self, detection_df, empty_taxonomy_df, coverage_df,
        mmseqs_lineage_df, empty_sample_map, empty_ictv, node_map, name_map,
    ):
        """contig_B has no MMseqs2 lineage but has Diamond taxid=10710 (Lambda phage).
        Diamond lineage should backfill family, genus, species etc."""
        diamond_map = build_diamond_lineage_map(detection_df, node_map, name_map)
        bt = build_bigtable(
            detection_df, empty_taxonomy_df, coverage_df,
            mmseqs_lineage_df, empty_sample_map, empty_ictv,
            diamond_lineage_map=diamond_map,
        )
        # contig_A: covered by MMseqs2 lineage
        row_a = bt[bt["seq_id"] == "contig_A"].iloc[0]
        assert row_a["family"] == "Flaviviridae"
        assert row_a["genus"] == "Flavivirus"

        # contig_B: Diamond-only lineage backfill
        row_b = bt[bt["seq_id"] == "contig_B"].iloc[0]
        assert row_b["family"] == "Siphoviridae"
        assert row_b["genus"] == "Lambdavirus"
        assert row_b["species"] == "Lambda phage"

        # contig_C: no taxid (0) -- should remain empty (except domain normalization)
        row_c = bt[bt["seq_id"] == "contig_C"].iloc[0]
        assert row_c["family"] == "Unclassified"  # from extract_family_from_lineage_str

    def test_taxonomy_source_tracking(
        self, detection_df, empty_taxonomy_df, coverage_df,
        mmseqs_lineage_df, empty_sample_map, empty_ictv, node_map, name_map,
    ):
        """Verify taxonomy_source column correctly tracks data origin."""
        diamond_map = build_diamond_lineage_map(detection_df, node_map, name_map)
        bt = build_bigtable(
            detection_df, empty_taxonomy_df, coverage_df,
            mmseqs_lineage_df, empty_sample_map, empty_ictv,
            diamond_lineage_map=diamond_map,
        )
        assert "taxonomy_source" in bt.columns

        # contig_A: has both MMseqs2 and Diamond lineage
        assert bt[bt["seq_id"] == "contig_A"]["taxonomy_source"].iloc[0] == "both"
        # contig_B: Diamond only
        assert bt[bt["seq_id"] == "contig_B"]["taxonomy_source"].iloc[0] == "diamond"
        # contig_C: neither (taxid=0)
        assert bt[bt["seq_id"] == "contig_C"]["taxonomy_source"].iloc[0] == "unknown"

    def test_no_diamond_lineage_map(
        self, detection_df, empty_taxonomy_df, coverage_df,
        mmseqs_lineage_df, empty_sample_map, empty_ictv,
    ):
        """Without diamond_lineage_map, behavior should be same as before (no backfill)."""
        bt = build_bigtable(
            detection_df, empty_taxonomy_df, coverage_df,
            mmseqs_lineage_df, empty_sample_map, empty_ictv,
            diamond_lineage_map=None,
        )
        # contig_B should have no family resolution (only detection taxonomy string fallback)
        row_b = bt[bt["seq_id"] == "contig_B"].iloc[0]
        assert row_b["family"] == "Unclassified"  # no geNomad taxonomy string either
        # taxonomy_source column should not exist
        assert "taxonomy_source" not in bt.columns

    def test_mmseqs2_priority_over_diamond(
        self, detection_df, empty_taxonomy_df, coverage_df,
        empty_sample_map, empty_ictv, node_map, name_map,
    ):
        """MMseqs2 lineage should take priority; Diamond only fills gaps."""
        # MMseqs2 lineage covers contig_A with specific taxonomy
        mmseqs_lineage = pd.DataFrame({
            "seq_id": ["contig_A"],
            "taxid": ["12637"],
            "domain": ["Viruses"],
            "phylum": ["Kitrinoviricota"],
            "class": ["Flasuviricetes"],
            "order": ["Amarillovirales"],
            "family": ["Flaviviridae"],
            "genus": ["Flavivirus"],
            "species": ["Dengue virus"],
        })
        diamond_map = build_diamond_lineage_map(detection_df, node_map, name_map)
        bt = build_bigtable(
            detection_df, empty_taxonomy_df, coverage_df,
            mmseqs_lineage, empty_sample_map, empty_ictv,
            diamond_lineage_map=diamond_map,
        )
        row_a = bt[bt["seq_id"] == "contig_A"].iloc[0]
        # MMseqs2 values should be preserved, not overwritten by Diamond
        assert row_a["genus"] == "Flavivirus"
        assert row_a["species"] == "Dengue virus"


# ---------------------------------------------------------------------------
# Tests: CLI argument handling
# ---------------------------------------------------------------------------

class TestCLIArgs:
    def test_taxonomy_nodes_and_names_args(self):
        """Verify --taxonomy-nodes and --taxonomy-names are accepted."""
        from merge_results import parse_args
        args = parse_args([
            "--taxonomy", "tax.tsv",
            "--lineage", "lin.tsv",
            "--coverage", "cov.tsv",
            "--detection", "det.tsv",
            "--sample-map", "sm.tsv",
            "--ictv", "ictv.tsv",
            "--taxonomy-nodes", "/path/to/nodes.dmp",
            "--taxonomy-names", "/path/to/names.dmp",
            "--out-bigtable", "bt.tsv",
            "--out-matrix", "mx.tsv",
            "--out-counts", "ct.tsv",
        ])
        assert args.taxonomy_nodes == Path("/path/to/nodes.dmp")
        assert args.taxonomy_names == Path("/path/to/names.dmp")

    def test_optional_taxonomy_args(self):
        """--taxonomy-nodes/--taxonomy-names should be optional."""
        from merge_results import parse_args
        args = parse_args([
            "--taxonomy", "tax.tsv",
            "--lineage", "lin.tsv",
            "--coverage", "cov.tsv",
            "--detection", "det.tsv",
            "--sample-map", "sm.tsv",
            "--ictv", "ictv.tsv",
            "--out-bigtable", "bt.tsv",
            "--out-matrix", "mx.tsv",
            "--out-counts", "ct.tsv",
        ])
        assert args.taxonomy_nodes is None
        assert args.taxonomy_names is None
