"""
End-to-end pipeline run on sample data.
Runs all 6 pipeline steps and generates a PDF report.

Usage:
    python tests/sample_run.py
"""
from __future__ import annotations
import logging
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-30s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sample_run")


def step(num: int, name: str) -> None:
    logger.info(f"{'='*60}")
    logger.info(f"  STEG {num}: {name}")
    logger.info(f"{'='*60}")


def main() -> str:
    """Run complete pipeline and return PDF path."""
    t0 = time.time()

    # ── 0. Create sample data ─────────────────────────────────
    step(0, "Skapar exempeldata")
    from scripts.create_sample_data import main as create_data
    create_data()

    # ── Configuration ─────────────────────────────────────────
    RUN_ID       = "sample"
    DEMO_MODE    = True
    DATA_DIR     = Path("data/sample")
    OUTPUT_BASE  = Path("data/outputs") / RUN_ID

    from dotenv import load_dotenv
    load_dotenv()

    # ── 1. Ingest ─────────────────────────────────────────────
    step(1, "Ingest – validering och metadata")
    from pipeline.ingest import IngestValidator

    validator = IngestValidator(demo_mode=DEMO_MODE)
    ingest_result = validator.validate(DATA_DIR, RUN_ID)

    logger.info(f"RGB images:     {len(ingest_result.rgb_images)}")
    logger.info(f"Thermal images: {len(ingest_result.thermal_images)}")
    if ingest_result.validation_errors:
        logger.warning(f"Validation errors: {ingest_result.validation_errors}")

    # ── 2. Photogrammetry ─────────────────────────────────────
    step(2, "Fotogrammetri – syntetiskt ortofoto")
    from pipeline.photogrammetry import ODMClient

    odm = ODMClient(demo_mode=DEMO_MODE)
    photogrammetry_result = odm.process(
        rgb_images=[i.path for i in ingest_result.rgb_images],
        output_dir=OUTPUT_BASE / "photogrammetry",
        run_id=RUN_ID,
        precomputed_dir=DATA_DIR / "precomputed",
    )
    logger.info(f"Orthophoto: {photogrammetry_result.orthophoto_path}")

    # ── 3. Thermal ────────────────────────────────────────────
    step(3, "Termisk extraktion och anomalidetektion")
    from pipeline.thermal import ThermalExtractor

    extractor = ThermalExtractor(
        anomaly_threshold_c=float(os.getenv("THERMAL_ANOMALY_THRESHOLD_C", "3.0")),
        min_area_px=int(os.getenv("THERMAL_MIN_AREA_PX", "50")),
        demo_mode=DEMO_MODE,
    )
    thermal_result = extractor.process(
        thermal_images=[i.path for i in ingest_result.thermal_images],
        output_dir=OUTPUT_BASE / "thermal",
        run_id=RUN_ID,
    )
    logger.info(f"Thermal anomalies found: {len(thermal_result.anomalies)}")
    for a in thermal_result.anomalies[:5]:
        logger.info(f"  [{a.anomaly_type}] ΔT={a.delta_temp:.1f}°C  area={a.area_px}px")

    # ── 4. Detection ──────────────────────────────────────────
    step(4, "AI-skadedetektering (demo mock)")
    from pipeline.detection import Detector

    detector = Detector(
        confidence=float(os.getenv("DETECTION_CONFIDENCE", "0.4")),
        demo_mode=DEMO_MODE,
    )
    detection_result = detector.process(
        rgb_images=[i.path for i in ingest_result.rgb_images],
        thermal_anomalies=thermal_result.anomalies,
        output_dir=OUTPUT_BASE / "detection",
        run_id=RUN_ID,
    )
    logger.info(f"Total findings: {len(detection_result.findings)}")
    for f in detection_result.findings[:5]:
        logger.info(f"  [{f.source}] {f.finding_type} conf={f.confidence:.2f}")

    # ── 5. Analysis ───────────────────────────────────────────
    step(5, "GIS-analys och prioritering")
    from pipeline.analysis import Analyzer

    analyzer = Analyzer(demo_mode=DEMO_MODE)
    analysis_result = analyzer.process(
        detection_result=detection_result,
        photogrammetry_result=photogrammetry_result,
        output_dir=OUTPUT_BASE / "analysis",
        run_id=RUN_ID,
        inspection_date="2026-03-09",
    )
    s = analysis_result.summary
    logger.info(
        f"Summary: total={s.total_findings} "
        f"KRITISK={s.kritisk_count} HÖG={s.hog_count} "
        f"MEDEL={s.medel_count} LÅG={s.lag_count}"
    )
    if analysis_result.geojson_path:
        logger.info(f"GeoJSON: {analysis_result.geojson_path}")

    # ── 6. Report ─────────────────────────────────────────────
    step(6, "Rapportgenerering – PDF")
    from pipeline.report import ReportGenerator

    generator = ReportGenerator(
        company_name="SmartTek AB",
        demo_mode=DEMO_MODE,
    )
    report_result = generator.generate(
        analysis_result=analysis_result,
        detection_result=detection_result,
        thermal_result=thermal_result,
        ingest_result=ingest_result,
        output_dir=OUTPUT_BASE / "report",
        run_id=RUN_ID,
    )

    elapsed = time.time() - t0
    logger.info(f"{'='*60}")
    logger.info(f"  PIPELINE KLAR  ({elapsed:.1f}s)")
    logger.info(f"{'='*60}")
    logger.info(f"  PDF:  {report_result.pdf_path}")
    logger.info(f"  HTML: {report_result.html_path}")
    logger.info(f"{'='*60}")

    return report_result.pdf_path


if __name__ == "__main__":
    pdf_path = main()
    print(f"\nRapport skapad: {pdf_path}")
