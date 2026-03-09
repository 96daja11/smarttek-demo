"""Tests for the detection step."""
import pytest
from pathlib import Path
from pipeline.detection import Detector, DetectionResult


def test_detection_demo_mode(sample_dir, test_run_id, tmp_path):
    rgb_dir = sample_dir / "rgb"
    images = [str(p) for p in rgb_dir.glob("*.jpg")]
    assert len(images) > 0, "No RGB images found"

    detector = Detector(demo_mode=True)
    result = detector.process(
        rgb_images=images,
        thermal_anomalies=[],
        output_dir=tmp_path / "detection",
        run_id=test_run_id,
    )

    assert isinstance(result, DetectionResult)
    assert len(result.findings) > 0
    assert result.images_processed == len(images)


def test_detection_finding_structure(sample_dir, test_run_id, tmp_path):
    rgb_dir = sample_dir / "rgb"
    images = [str(p) for p in rgb_dir.glob("*.jpg")]

    detector = Detector(demo_mode=True)
    result = detector.process(
        rgb_images=images[:1],
        thermal_anomalies=[],
        output_dir=tmp_path / "detection2",
        run_id=test_run_id,
    )

    for f in result.findings:
        assert 0.0 <= f.confidence <= 1.0
        assert len(f.bbox) == 4
        assert f.finding_type in {"crack", "water_damage", "delamination", "rust", "vegetation"}
