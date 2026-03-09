"""Steg 1: Validering och metadata-extraktion."""
from __future__ import annotations
import os
import struct
from pathlib import Path
from typing import Optional
import logging

from .models import IngestResult, ImageMetadata, GPSCoordinate

logger = logging.getLogger(__name__)

SUPPORTED_RGB_FORMATS = {".jpg", ".jpeg", ".dng", ".tiff", ".tif"}
SUPPORTED_THERMAL_FORMATS = {".jpg", ".jpeg", ".png", ".npy"}


def _dms_to_decimal(degrees: float, minutes: float, seconds: float, ref: str) -> float:
    """Convert DMS GPS to decimal degrees."""
    decimal = degrees + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def _extract_gps_from_exif(exif_data: dict) -> Optional[GPSCoordinate]:
    """Extract GPS coordinates from EXIF data."""
    try:
        from PIL.ExifTags import TAGS, GPSTAGS
        gps_info = exif_data.get("GPSInfo")
        if not gps_info:
            return None

        gps_decoded = {}
        for key, val in gps_info.items():
            tag = GPSTAGS.get(key, key)
            gps_decoded[tag] = val

        lat_dms = gps_decoded.get("GPSLatitude")
        lat_ref = gps_decoded.get("GPSLatitudeRef", "N")
        lon_dms = gps_decoded.get("GPSLongitude")
        lon_ref = gps_decoded.get("GPSLongitudeRef", "E")

        if not (lat_dms and lon_dms):
            return None

        lat = _dms_to_decimal(
            float(lat_dms[0]), float(lat_dms[1]), float(lat_dms[2]), lat_ref
        )
        lon = _dms_to_decimal(
            float(lon_dms[0]), float(lon_dms[1]), float(lon_dms[2]), lon_ref
        )

        alt = None
        alt_val = gps_decoded.get("GPSAltitude")
        if alt_val:
            alt = float(alt_val)

        return GPSCoordinate(latitude=lat, longitude=lon, altitude=alt)

    except Exception as e:
        logger.debug(f"GPS extraction failed: {e}")
        return None


def _analyze_image(path: Path, file_type: str) -> Optional[ImageMetadata]:
    """Analyze a single image file and return metadata."""
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        stat = path.stat()

        if path.suffix.lower() == ".npy":
            import numpy as np
            arr = np.load(str(path))
            return ImageMetadata(
                path=str(path),
                filename=path.name,
                file_type=file_type,
                format="NPY",
                width=arr.shape[1] if arr.ndim >= 2 else 0,
                height=arr.shape[0] if arr.ndim >= 2 else 0,
                gps=None,
                file_size_bytes=stat.st_size,
            )

        img = Image.open(path)
        width, height = img.size
        fmt = img.format or path.suffix.upper().lstrip(".")

        gps = None
        camera_model = None
        capture_time = None

        try:
            exif_data = img._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == "Model":
                        camera_model = str(value)
                    elif tag == "DateTimeOriginal":
                        capture_time = str(value)

                gps = _extract_gps_from_exif({"GPSInfo": exif_data.get(34853)})
        except Exception:
            pass

        return ImageMetadata(
            path=str(path),
            filename=path.name,
            file_type=file_type,
            format=fmt,
            width=width,
            height=height,
            gps=gps,
            camera_model=camera_model,
            capture_time=capture_time,
            file_size_bytes=stat.st_size,
        )
    except Exception as e:
        logger.warning(f"Failed to analyze {path}: {e}")
        return None


class IngestValidator:
    """Validates and ingests image files for the pipeline."""

    def __init__(self, demo_mode: bool = False):
        self.demo_mode = demo_mode

    def validate(self, data_dir: Path, run_id: str) -> IngestResult:
        """
        Validate all images in data_dir and return IngestResult.
        Expects data_dir to contain rgb/ and thermal/ subdirectories.
        """
        errors = []
        rgb_images = []
        thermal_images = []

        rgb_dir = data_dir / "rgb"
        thermal_dir = data_dir / "thermal"

        if not data_dir.exists():
            errors.append(f"Data directory does not exist: {data_dir}")
            return IngestResult(
                run_id=run_id,
                validation_errors=errors,
                demo_mode=self.demo_mode,
            )

        # Process RGB images
        if rgb_dir.exists():
            for path in sorted(rgb_dir.iterdir()):
                if path.suffix.lower() in SUPPORTED_RGB_FORMATS:
                    metadata = _analyze_image(path, "rgb")
                    if metadata:
                        rgb_images.append(metadata)
                    else:
                        errors.append(f"Could not read RGB image: {path.name}")
        else:
            if not self.demo_mode:
                errors.append(f"RGB directory not found: {rgb_dir}")

        # Process thermal images
        if thermal_dir.exists():
            for path in sorted(thermal_dir.iterdir()):
                if path.suffix.lower() in SUPPORTED_THERMAL_FORMATS:
                    metadata = _analyze_image(path, "thermal")
                    if metadata:
                        thermal_images.append(metadata)
                    else:
                        errors.append(f"Could not read thermal image: {path.name}")
        else:
            if not self.demo_mode:
                errors.append(f"Thermal directory not found: {thermal_dir}")

        if not rgb_images and not self.demo_mode:
            errors.append("No valid RGB images found")

        if not thermal_images and not self.demo_mode:
            errors.append("No valid thermal images found")

        logger.info(
            f"Ingest complete: {len(rgb_images)} RGB, {len(thermal_images)} thermal images"
        )

        return IngestResult(
            run_id=run_id,
            rgb_images=rgb_images,
            thermal_images=thermal_images,
            validation_errors=errors,
            demo_mode=self.demo_mode,
        )
