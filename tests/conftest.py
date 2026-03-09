"""Pytest configuration and fixtures."""
import pytest
from pathlib import Path

SAMPLE_DIR = Path(__file__).parent.parent / "data" / "sample"
TEST_RUN_ID = "test-001"


@pytest.fixture(scope="session")
def sample_dir():
    return SAMPLE_DIR


@pytest.fixture(scope="session")
def test_run_id():
    return TEST_RUN_ID


@pytest.fixture(scope="session", autouse=True)
def ensure_sample_data(tmp_path_factory):
    """Ensure sample data exists before tests run."""
    if not (SAMPLE_DIR / "rgb").exists() or not any((SAMPLE_DIR / "rgb").glob("*.jpg")):
        import subprocess
        import sys
        subprocess.run(
            [sys.executable, "scripts/create_sample_data.py"],
            cwd=Path(__file__).parent.parent,
            check=True,
        )
