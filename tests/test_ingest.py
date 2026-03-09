"""Tests for the ingest step."""
import pytest
from pathlib import Path
from pipeline.ingest import IngestValidator, IngestResult


def test_ingest_validates_sample_data(sample_dir, test_run_id):
    validator = IngestValidator(demo_mode=True)
    result = validator.validate(sample_dir, test_run_id)
    assert isinstance(result, IngestResult)
    assert len(result.rgb_images) >= 1
    assert len(result.thermal_images) >= 1
    assert result.total_images >= 2


def test_ingest_missing_dir(tmp_path, test_run_id):
    validator = IngestValidator(demo_mode=False)
    result = validator.validate(tmp_path / "nonexistent", test_run_id)
    assert len(result.validation_errors) > 0


def test_ingest_image_metadata(sample_dir, test_run_id):
    validator = IngestValidator(demo_mode=True)
    result = validator.validate(sample_dir, test_run_id)
    for img in result.rgb_images:
        assert img.width > 0
        assert img.height > 0
        assert img.file_size_bytes > 0
