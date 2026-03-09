"""Steg 5: Georeferering, klassificering och GIS-analys."""
from __future__ import annotations
import json
import logging
import random
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GeoFinding(BaseModel):
    finding_id: str
    finding_type: str
    source: str
    confidence: float
    severity: str  # KRITISK, HÖG, MEDEL, LÅG
    severity_score: int  # 4=KRITISK, 3=HÖG, 2=MEDEL, 1=LÅG
    lat: float
    lon: float
    area_m2: Optional[float] = None
    description: str = ""
    action_recommendation: str = ""
    urgency_weeks: Optional[int] = None
    estimated_cost_sek: Optional[int] = None
    source_image: str = ""
    bbox: list[float] = []


class AnalysisSummary(BaseModel):
    total_findings: int
    kritisk_count: int
    hog_count: int
    medel_count: int
    lag_count: int
    total_affected_area_m2: float
    property_address: str = "Demonstrationsfastigheten, Göteborg"
    inspection_date: str = ""
    client_name: str = "SmartTek Demo AB"
    order_reference: str = ""


class AnalysisResult(BaseModel):
    run_id: str
    findings: list[GeoFinding] = []
    summary: Optional[AnalysisSummary] = None
    geojson_path: Optional[str] = None
    demo_mode: bool = False

    # Bounding box for the inspection area
    bbox: list[float] = [11.9600, 57.7000, 11.9700, 57.7100]
    center_lat: float = 57.7050
    center_lon: float = 11.9650


# Severity classification rules
SEVERITY_RULES = {
    "crack": {
        "high_conf": ("KRITISK", 4, 2),    # (severity, score, urgency_weeks)
        "low_conf":  ("HÖG", 3, 8),
    },
    "water_damage": {
        "high_conf": ("KRITISK", 4, 2),
        "low_conf":  ("HÖG", 3, 4),
    },
    "delamination": {
        "high_conf": ("HÖG", 3, 8),
        "low_conf":  ("MEDEL", 2, 16),
    },
    "rust": {
        "high_conf": ("HÖG", 3, 12),
        "low_conf":  ("MEDEL", 2, 24),
    },
    "vegetation": {
        "high_conf": ("MEDEL", 2, 24),
        "low_conf":  ("LÅG", 1, 52),
    },
}

ACTION_RECOMMENDATIONS = {
    "crack": "Injektera spricka med epoxi. Kontrollera bärförmåga. Anlita konstruktör.",
    "water_damage": "Akut åtgärd: lokalisera läckkälla, torka ut konstruktion, täta om.",
    "delamination": "Byt ut avlöst tätskikt. Inspektera underliggande konstruktion.",
    "rust": "Rostskyddsbehandla metalldelar. Kontrollera anslutningsdetaljer.",
    "vegetation": "Rengör takyta. Applicera algdödande medel. Förebygg återväxt.",
}

COST_ESTIMATES = {
    "crack": (8000, 25000),
    "water_damage": (15000, 60000),
    "delamination": (12000, 45000),
    "rust": (3000, 12000),
    "vegetation": (2000, 6000),
}


def classify_severity(finding_type: str, confidence: float) -> tuple[str, int, int]:
    """Classify finding severity. Returns (severity, score, urgency_weeks)."""
    rules = SEVERITY_RULES.get(finding_type)
    if not rules:
        if confidence > 0.7:
            return "MEDEL", 2, 16
        return "LÅG", 1, 52

    threshold = 0.75
    if confidence >= threshold:
        return rules["high_conf"]
    return rules["low_conf"]


class Analyzer:
    """Georeferencer and severity classifier for pipeline findings."""

    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode
        random.seed(42)

    def process(
        self,
        detection_result,
        photogrammetry_result,
        output_dir: Path,
        run_id: str,
        inspection_date: str = "2026-03-09",
    ) -> AnalysisResult:
        """Georeference findings and classify severity."""
        output_dir.mkdir(parents=True, exist_ok=True)

        bbox = getattr(photogrammetry_result, 'bbox', None) or [11.9600, 57.7000, 11.9700, 57.7100]
        center_lat = getattr(photogrammetry_result, 'center_lat', None) or 57.7050
        center_lon = getattr(photogrammetry_result, 'center_lon', None) or 11.9650

        geo_findings = []
        random.seed(42)

        for finding in detection_result.findings:
            # Georeference: map pixel bbox to GPS coords
            lat, lon = self._georeference(finding.bbox, bbox, center_lat, center_lon)

            severity, score, urgency = classify_severity(finding.finding_type, finding.confidence)

            cost_range = COST_ESTIMATES.get(finding.finding_type, (5000, 20000))
            cost = random.randint(cost_range[0], cost_range[1])

            geo_finding = GeoFinding(
                finding_id=finding.finding_id,
                finding_type=finding.finding_type,
                source=finding.source,
                confidence=finding.confidence,
                severity=severity,
                severity_score=score,
                lat=lat,
                lon=lon,
                area_m2=finding.area_m2,
                description=finding.description,
                action_recommendation=ACTION_RECOMMENDATIONS.get(
                    finding.finding_type, "Inspektera och åtgärda efter behov."
                ),
                urgency_weeks=urgency,
                estimated_cost_sek=cost,
                source_image=finding.source_image,
                bbox=finding.bbox,
            )
            geo_findings.append(geo_finding)

        # Sort by severity (most critical first)
        geo_findings.sort(key=lambda f: (-f.severity_score, -f.confidence))

        # Build summary
        summary = AnalysisSummary(
            total_findings=len(geo_findings),
            kritisk_count=sum(1 for f in geo_findings if f.severity == "KRITISK"),
            hog_count=sum(1 for f in geo_findings if f.severity == "HÖG"),
            medel_count=sum(1 for f in geo_findings if f.severity == "MEDEL"),
            lag_count=sum(1 for f in geo_findings if f.severity == "LÅG"),
            total_affected_area_m2=sum(f.area_m2 or 0 for f in geo_findings),
            inspection_date=inspection_date,
            order_reference=f"ST-{run_id.upper()[:8]}",
        )

        result = AnalysisResult(
            run_id=run_id,
            findings=geo_findings,
            summary=summary,
            demo_mode=self.demo_mode,
            bbox=bbox,
            center_lat=center_lat,
            center_lon=center_lon,
        )

        # Save GeoJSON
        geojson = self._to_geojson(geo_findings)
        geojson_path = output_dir / "findings.geojson"
        geojson_path.write_text(json.dumps(geojson, indent=2, ensure_ascii=False))
        result.geojson_path = str(geojson_path)

        # Save summary
        summary_path = output_dir / "summary.json"
        summary_path.write_text(result.model_dump_json(indent=2))

        logger.info(
            f"Analysis: {summary.total_findings} findings – "
            f"KRITISK:{summary.kritisk_count} HÖG:{summary.hog_count} "
            f"MEDEL:{summary.medel_count} LÅG:{summary.lag_count}"
        )

        return result

    def _georeference(
        self,
        bbox: list[float],
        area_bbox: list[float],
        center_lat: float,
        center_lon: float,
    ) -> tuple[float, float]:
        """Convert normalized image coords to GPS coordinates."""
        # bbox = [x1, y1, x2, y2] normalized 0-1
        cx = (bbox[0] + bbox[2]) / 2 if len(bbox) >= 4 else 0.5
        cy = (bbox[1] + bbox[3]) / 2 if len(bbox) >= 4 else 0.5

        # Map to geographic extent
        lon_range = area_bbox[2] - area_bbox[0]
        lat_range = area_bbox[3] - area_bbox[1]

        # Add some noise for realistic distribution
        jitter_lat = random.uniform(-lat_range * 0.1, lat_range * 0.1)
        jitter_lon = random.uniform(-lon_range * 0.1, lon_range * 0.1)

        lon = area_bbox[0] + cx * lon_range + jitter_lon
        lat = area_bbox[1] + (1 - cy) * lat_range + jitter_lat

        return round(lat, 6), round(lon, 6)

    def _to_geojson(self, findings: list[GeoFinding]) -> dict:
        """Convert findings to GeoJSON FeatureCollection."""
        features = []
        for f in findings:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [f.lon, f.lat],
                },
                "properties": {
                    "finding_id": f.finding_id,
                    "finding_type": f.finding_type,
                    "severity": f.severity,
                    "severity_score": f.severity_score,
                    "confidence": f.confidence,
                    "source": f.source,
                    "description": f.description,
                    "action": f.action_recommendation,
                    "urgency_weeks": f.urgency_weeks,
                    "cost_sek": f.estimated_cost_sek,
                    "area_m2": f.area_m2,
                },
            }
            features.append(feature)

        return {
            "type": "FeatureCollection",
            "features": features,
        }
