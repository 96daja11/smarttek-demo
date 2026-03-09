"""POST /run – kör pipeline, returnerar rapport-URL."""
from __future__ import annotations
import os
import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job store
_jobs: dict[str, dict] = {}


class RunRequest(BaseModel):
    use_sample_data: bool = True
    data_dir: Optional[str] = None


class RunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    run_id: str
    status: str
    step: Optional[str] = None
    progress: int = 0
    report_url: Optional[str] = None
    error: Optional[str] = None


def _run_pipeline_sync(run_id: str, data_dir: Path, demo_mode: bool):
    """Run the full pipeline synchronously (called in thread)."""
    try:
        from pipeline.ingest import IngestValidator
        from pipeline.photogrammetry import ODMClient
        from pipeline.thermal import ThermalExtractor
        from pipeline.detection import Detector
        from pipeline.analysis import Analyzer
        from pipeline.report import ReportGenerator

        output_base = Path("data/outputs") / run_id

        _jobs[run_id]["step"] = "ingest"
        _jobs[run_id]["progress"] = 10

        # Step 1: Ingest
        validator = IngestValidator(demo_mode=demo_mode)
        ingest_result = validator.validate(data_dir, run_id)

        _jobs[run_id]["step"] = "photogrammetry"
        _jobs[run_id]["progress"] = 25

        # Step 2: Photogrammetry
        odm = ODMClient(
            base_url=os.getenv("WEBODM_URL", "http://localhost:8000"),
            username=os.getenv("WEBODM_USERNAME", "admin"),
            password=os.getenv("WEBODM_PASSWORD", "admin"),
            demo_mode=demo_mode,
        )
        photogrammetry_result = odm.process(
            rgb_images=[i.path for i in ingest_result.rgb_images],
            output_dir=output_base / "photogrammetry",
            run_id=run_id,
            precomputed_dir=data_dir / "precomputed",
        )

        _jobs[run_id]["step"] = "thermal"
        _jobs[run_id]["progress"] = 45

        # Step 3: Thermal
        extractor = ThermalExtractor(
            anomaly_threshold_c=float(os.getenv("THERMAL_ANOMALY_THRESHOLD_C", "3.0")),
            min_area_px=int(os.getenv("THERMAL_MIN_AREA_PX", "50")),
            demo_mode=demo_mode,
        )
        thermal_result = extractor.process(
            thermal_images=[i.path for i in ingest_result.thermal_images],
            output_dir=output_base / "thermal",
            run_id=run_id,
        )

        _jobs[run_id]["step"] = "detection"
        _jobs[run_id]["progress"] = 62

        # Step 4: Detection
        detector = Detector(
            model_path=os.getenv("DETECTION_MODEL_PATH"),
            confidence=float(os.getenv("DETECTION_CONFIDENCE", "0.4")),
            demo_mode=demo_mode,
        )
        detection_result = detector.process(
            rgb_images=[i.path for i in ingest_result.rgb_images],
            thermal_anomalies=thermal_result.anomalies,
            output_dir=output_base / "detection",
            run_id=run_id,
        )

        _jobs[run_id]["step"] = "analysis"
        _jobs[run_id]["progress"] = 78

        # Step 5: Analysis
        analyzer = Analyzer(demo_mode=demo_mode)
        analysis_result = analyzer.process(
            detection_result=detection_result,
            photogrammetry_result=photogrammetry_result,
            output_dir=output_base / "analysis",
            run_id=run_id,
        )

        _jobs[run_id]["step"] = "report"
        _jobs[run_id]["progress"] = 90

        # Step 6: Report
        generator = ReportGenerator(
            company_name=os.getenv("REPORT_COMPANY_NAME", "SmartTek AB"),
            demo_mode=demo_mode,
        )
        report_result = generator.generate(
            analysis_result=analysis_result,
            detection_result=detection_result,
            thermal_result=thermal_result,
            ingest_result=ingest_result,
            output_dir=output_base / "report",
            run_id=run_id,
        )

        _jobs[run_id]["status"] = "completed"
        _jobs[run_id]["progress"] = 100
        _jobs[run_id]["report_path"] = report_result.pdf_path
        _jobs[run_id]["report_url"] = f"/reports/{run_id}/rapport_{run_id}.pdf"

    except Exception as e:
        logger.exception(f"Pipeline failed for {run_id}: {e}")
        _jobs[run_id]["status"] = "failed"
        _jobs[run_id]["error"] = str(e)


@router.post("/run", response_model=RunResponse)
async def run_pipeline(request: RunRequest, background_tasks: BackgroundTasks):
    """Start a pipeline run and return the run_id."""
    run_id = str(uuid.uuid4())[:8]
    demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"

    if request.use_sample_data:
        data_dir = Path("data/sample")
    elif request.data_dir:
        data_dir = Path(request.data_dir)
    else:
        raise HTTPException(status_code=400, detail="No data source specified")

    _jobs[run_id] = {
        "status": "running",
        "step": "starting",
        "progress": 0,
    }

    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None, _run_pipeline_sync, run_id, data_dir, demo_mode
    )

    return RunResponse(
        run_id=run_id,
        status="running",
        message=f"Pipeline started. Poll /status/{run_id} for progress.",
    )


@router.get("/status/{run_id}", response_model=StatusResponse)
async def get_status(run_id: str):
    """Get pipeline run status."""
    if run_id not in _jobs:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")

    job = _jobs[run_id]
    return StatusResponse(
        run_id=run_id,
        status=job.get("status", "unknown"),
        step=job.get("step"),
        progress=job.get("progress", 0),
        report_url=job.get("report_url"),
        error=job.get("error"),
    )
