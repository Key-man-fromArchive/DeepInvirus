"""Pytest fixtures and configuration for DeepInvirus tests.

# @TASK T0.5 - Python 테스트 프레임워크 설정
# @SPEC docs/planning/02-trd.md#6-테스트-전략
# @SPEC docs/planning/07-coding-convention.md#6-테스트-규칙
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


# Test data paths
TESTS_DIR = Path(__file__).parent
DATA_DIR = TESTS_DIR / "data"
READS_DIR = DATA_DIR / "reads"
EXPECTED_OUTPUT_DIR = DATA_DIR / "expected"


@pytest.fixture
def tmp_dir() -> Path:
    """Create a temporary directory for test files.

    Yields:
        Path to temporary directory (auto-cleaned after test).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_reads_dir() -> Path:
    """Get path to sample reads test data directory.

    Returns:
        Path to tests/data/reads/ directory.

    Note:
        Directory may not exist during early testing phases.
        Tests should handle gracefully.
    """
    return READS_DIR


@pytest.fixture
def expected_output_dir() -> Path:
    """Get path to expected output test data directory.

    Returns:
        Path to tests/data/expected/ directory.

    Note:
        Directory may not exist during early testing phases.
        Tests should handle gracefully.
    """
    return EXPECTED_OUTPUT_DIR


@pytest.fixture
def mock_bigtable() -> dict:
    """Create a mock bigtable (unified results table) for testing.

    Returns:
        Dictionary with mock bigtable structure:
        - keys: column names
        - values: lists of mock data (one row per element)

    Example:
        {
            'sample_id': ['S1', 'S2'],
            'contig_id': ['NODE_1', 'NODE_2'],
            'virus_score': [0.95, 0.87],
            'kingdom': ['Viruses', 'Viruses'],
        }
    """
    return {
        "sample_id": ["S1", "S1", "S2"],
        "contig_id": ["NODE_1", "NODE_2", "NODE_3"],
        "contig_length": [5000, 3500, 4200],
        "virus_score": [0.95, 0.87, 0.92],
        "virus_category": ["dsDNA", "ssRNA", "dsDNA"],
        "kingdom": ["Viruses", "Viruses", "Viruses"],
        "superkingdom": ["Viruses", "Viruses", "Viruses"],
        "phylum": ["Nucleocytoviricota", "Leviviricota", "Nucleocytoviricota"],
        "class": ["Megaviricetes", "Leviviricetes", "Megaviricetes"],
        "order": ["Imitervirales", "Norzivirales", "Imitervirales"],
        "family": ["Nucleocytoplasmic large DNA viruses", "Leviviridae", "Nucleocytoplasmic large DNA viruses"],
        "genus": ["Virus-A", "Virus-B", "Virus-C"],
        "species": ["Virus-A sp.", "Virus-B sp.", "Virus-C sp."],
        "rpm": [150.5, 120.3, 130.2],
    }


def pytest_configure(config):
    """Configure pytest with custom markers.

    Args:
        config: pytest config object.
    """
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test (fast, isolated)"
    )
    config.addinivalue_line(
        "markers",
        "module: mark test as a module-level test (Nextflow process integration)",
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as an integration test (full pipeline)",
    )
    config.addinivalue_line(
        "markers",
        "validation: mark test as a validation test (benchmark datasets)",
    )
