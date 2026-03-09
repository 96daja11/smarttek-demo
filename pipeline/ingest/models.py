"""Pydantic-modeller för ingest-steget."""
from __future__ import annotations
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class GPSCoordinate(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float] = None

    def __str__(self) -> str:
        return f"{self.latitude:.6f}, {self.longitude:.6f}"


class ImageMetadata(BaseModel):
    path: str
    filename: str
    file_type: str  # "rgb", "thermal"
    format: str     # "JPEG", "DNG", "RJPEG"
    width: int
    height: int
    gps: Optional[GPSCoordinate] = None
    camera_model: Optional[str] = None
    capture_time: Optional[str] = None
    file_size_bytes: int


class IngestResult(BaseModel):
    run_id: str
    rgb_images: list[ImageMetadata] = Field(default_factory=list)
    thermal_images: list[ImageMetadata] = Field(default_factory=list)
    total_images: int = 0
    validation_errors: list[str] = Field(default_factory=list)
    demo_mode: bool = False

    @property
    def is_valid(self) -> bool:
        return len(self.validation_errors) == 0

    def model_post_init(self, __context) -> None:
        self.total_images = len(self.rgb_images) + len(self.thermal_images)
