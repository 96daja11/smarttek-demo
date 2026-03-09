"""FastAPI main application."""
from __future__ import annotations
import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from .routes.pipeline import router as pipeline_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SmartTek Inspection API",
    description="Drönbaserad fastighetsinspektion pipeline API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline_router, prefix="/api", tags=["pipeline"])

# Serve generated reports
reports_dir = Path("data/outputs")
if reports_dir.exists():
    app.mount("/reports", StaticFiles(directory=str(reports_dir)), name="reports")


@app.get("/health")
async def health():
    return {"status": "ok", "demo_mode": os.getenv("DEMO_MODE", "true")}


@app.get("/")
async def root():
    return JSONResponse({
        "service": "SmartTek Inspection API",
        "version": "0.1.0",
        "docs": "/docs",
    })
