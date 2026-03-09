"""Tests for the thermal extraction step."""
import pytest
from pathlib import Path
from pipeline.thermal import ThermalExtractor, ThermalResult


def test_thermal_detects_anomalies(sample_dir, test_run_id, tmp_path):
    thermal_dir = sample_dir / "thermal"
    images = [str(p) for p in thermal_dir.glob("*.png")]
    assert len(images) > 0, "No thermal PNG images found"

    extractor = ThermalExtractor(anomaly_threshold_c=3.0, min_area_px=10, demo_mode=True)
    result = extractor.process(images, tmp_path / "thermal", test_run_id)

    assert isinstance(result, ThermalResult)
    assert result.images_processed >= 1
    assert len(result.anomalies) > 0, "Should detect anomalies in synthetic thermal data"


def test_thermal_anomaly_types(sample_dir, test_run_id, tmp_path):
    thermal_dir = sample_dir / "thermal"
    images = [str(p) for p in thermal_dir.glob("*.png")]

    extractor = ThermalExtractor(anomaly_threshold_c=2.0, min_area_px=10, demo_mode=True)
    result = extractor.process(images, tmp_path / "thermal2", test_run_id)

    types = {a.anomaly_type for a in result.anomalies}
    assert len(types) > 0

    for anomaly in result.anomalies:
        assert anomaly.delta_temp >= 0
        assert anomaly.area_px > 0
