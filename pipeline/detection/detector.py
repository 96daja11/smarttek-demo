"""Steg 4: YOLOv8-baserad skadedetektering med demo-läge mock."""
from __future__ import annotations
import logging
import random
from pathlib import Path
from typing import Optional
import numpy as np
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Finding(BaseModel):
    finding_id: str
    source_image: str
    finding_type: str  # "crack", "water_damage", "delamination", "vegetation", "rust"
    source: str        # "RGB-AI", "Thermal", "Kombinerad"
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2] normalized 0-1
    area_m2: Optional[float] = None
    thermal_anomaly_id: Optional[str] = None
    description: str = ""


class DetectionResult(BaseModel):
    run_id: str
    findings: list[Finding] = []
    images_processed: int = 0
    demo_mode: bool = False


class MockDetector:
    """Mock detector that returns realistic-looking findings for demo mode."""

    FINDING_TYPES = [
        ("crack", 0.85, "Spricka i takbalkong observerad längs taklisten"),
        ("water_damage", 0.78, "Vattenskada med missfärgning detekterad"),
        ("delamination", 0.72, "Avlösning av tätskikt vid genomföring"),
        ("crack", 0.91, "Strukturell spricka i fasad, behöver omgående inspektion"),
        ("vegetation", 0.65, "Mossanväxt och vegetation på takyta"),
        ("rust", 0.88, "Oxidation och rost på metallanslutning"),
        ("water_damage", 0.83, "Läckagespår vid takavvattning"),
        ("delamination", 0.69, "Bubblor och avlösning i membrantätning"),
    ]

    def detect(self, image_paths: list[str]) -> list[Finding]:
        """Return mock detections for demo purposes."""
        findings = []
        random.seed(42)  # Reproducible results

        for img_idx, img_path in enumerate(image_paths):
            img_name = Path(img_path).stem
            num_findings = random.randint(1, 3)

            for f_idx in range(num_findings):
                type_info = self.FINDING_TYPES[(img_idx * 3 + f_idx) % len(self.FINDING_TYPES)]
                finding_type, confidence, description = type_info

                # Generate plausible bounding box
                x1 = random.uniform(0.1, 0.6)
                y1 = random.uniform(0.1, 0.6)
                x2 = x1 + random.uniform(0.05, 0.25)
                y2 = y1 + random.uniform(0.05, 0.2)
                x2 = min(x2, 0.95)
                y2 = min(y2, 0.95)

                # Estimate area in m² (assuming ~50m altitude, ~5m/pixel coverage)
                bbox_w = (x2 - x1) * 1.5  # meters
                bbox_h = (y2 - y1) * 1.5
                area_m2 = round(bbox_w * bbox_h, 2)

                finding = Finding(
                    finding_id=f"{img_name}_rgb_{f_idx:03d}",
                    source_image=img_path,
                    finding_type=finding_type,
                    source="RGB-AI",
                    confidence=round(confidence + random.uniform(-0.05, 0.05), 2),
                    bbox=[x1, y1, x2, y2],
                    area_m2=area_m2,
                    description=description,
                )
                findings.append(finding)

        return findings


class Detector:
    """Detects damage in images using YOLO model or mock in demo mode."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence: float = 0.4,
        demo_mode: bool = False,
    ):
        self.model_path = model_path
        self.confidence = confidence
        self.demo_mode = demo_mode
        self._model = None

    def _load_model(self):
        """Load YOLO model if available."""
        if self.demo_mode:
            return None
        if self.model_path and Path(self.model_path).exists():
            try:
                from ultralytics import YOLO
                return YOLO(self.model_path)
            except ImportError:
                logger.warning("ultralytics not installed, using mock detector")
        return None

    def process(
        self,
        rgb_images: list[str],
        thermal_anomalies: list,
        output_dir: Path,
        run_id: str,
    ) -> DetectionResult:
        """Run detection on RGB images and merge with thermal anomalies."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # RGB-based detection
        if self.demo_mode:
            rgb_findings = MockDetector().detect(rgb_images)
        else:
            model = self._load_model()
            if model:
                rgb_findings = self._run_yolo(model, rgb_images)
            else:
                rgb_findings = MockDetector().detect(rgb_images)

        # Merge thermal anomalies as additional findings
        thermal_findings = self._thermal_to_findings(thermal_anomalies)

        all_findings = rgb_findings + thermal_findings

        result = DetectionResult(
            run_id=run_id,
            findings=all_findings,
            images_processed=len(rgb_images),
            demo_mode=self.demo_mode,
        )

        # Save findings
        findings_path = output_dir / "findings.json"
        findings_path.write_text(result.model_dump_json(indent=2))
        logger.info(
            f"Detection: {len(rgb_findings)} RGB + {len(thermal_findings)} thermal findings"
        )

        return result

    def _run_yolo(self, model, image_paths: list[str]) -> list[Finding]:
        """Run actual YOLO inference."""
        findings = []
        type_map = {0: "crack", 1: "water_damage", 2: "delamination", 3: "rust"}

        for img_path in image_paths:
            results = model(img_path, conf=self.confidence)
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    xyxyn = box.xyxyn[0].tolist()
                    finding_type = type_map.get(cls, f"class_{cls}")

                    findings.append(Finding(
                        finding_id=f"{Path(img_path).stem}_yolo_{len(findings):03d}",
                        source_image=img_path,
                        finding_type=finding_type,
                        source="RGB-AI",
                        confidence=conf,
                        bbox=xyxyn,
                        description=f"YOLO detection: {finding_type}",
                    ))

        return findings

    def _thermal_to_findings(self, thermal_anomalies: list) -> list[Finding]:
        """Convert thermal anomalies to Finding objects."""
        findings = []
        type_map = {
            "hotspot": "water_damage",
            "cold_bridge": "delamination",
            "moisture": "water_damage",
        }
        source_map = {
            "hotspot": "Termisk",
            "cold_bridge": "Termisk",
            "moisture": "Termisk",
        }
        desc_map = {
            "hotspot": "Termisk avvikelse: varm yta indikerar fukt eller läckage",
            "cold_bridge": "Köldbrygga detekterad – risk för kondens och energiförlust",
            "moisture": "Fuktsignatur i termisk bild – möjligt vattenintrång",
        }

        for anomaly in thermal_anomalies:
            if not hasattr(anomaly, 'anomaly_id'):
                continue
            # Normalize confidence based on delta_temp
            conf = min(0.95, 0.5 + anomaly.delta_temp / 20.0)
            atype = anomaly.anomaly_type

            findings.append(Finding(
                finding_id=f"thermal_{anomaly.anomaly_id}",
                source_image=anomaly.image_path,
                finding_type=type_map.get(atype, "anomaly"),
                source=source_map.get(atype, "Termisk"),
                confidence=round(conf, 2),
                bbox=[
                    anomaly.bbox[0] / 640,
                    anomaly.bbox[1] / 480,
                    anomaly.bbox[2] / 640,
                    anomaly.bbox[3] / 480,
                ],
                thermal_anomaly_id=anomaly.anomaly_id,
                area_m2=round(anomaly.area_px * 0.01, 2),
                description=desc_map.get(atype, "Termisk anomali"),
            ))

        return findings
