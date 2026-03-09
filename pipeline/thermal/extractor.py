"""Steg 3: Termisk extraktion och anomalidetektion."""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional
import numpy as np
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ThermalAnomaly(BaseModel):
    image_path: str
    anomaly_id: str
    center_x: float  # pixel coordinates
    center_y: float
    bbox: list[int]  # [x1, y1, x2, y2]
    max_temp: float
    mean_temp: float
    area_px: int
    delta_temp: float  # deviation from surroundings
    anomaly_type: str  # "hotspot", "cold_bridge", "moisture"
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None


class ThermalResult(BaseModel):
    run_id: str
    anomalies: list[ThermalAnomaly] = []
    images_processed: int = 0
    demo_mode: bool = False


class ThermalExtractor:
    """Extracts temperature data from thermal images and identifies anomalies."""

    THERMAL_MIN_TEMP = 0.0   # Celsius mapped to pixel 0
    THERMAL_MAX_TEMP = 60.0  # Celsius mapped to pixel 255

    def __init__(
        self,
        anomaly_threshold_c: float = 3.0,
        min_area_px: int = 50,
        demo_mode: bool = False,
    ):
        self.anomaly_threshold_c = anomaly_threshold_c
        self.min_area_px = min_area_px
        self.demo_mode = demo_mode

    def process(
        self,
        thermal_images: list[str],
        output_dir: Path,
        run_id: str,
    ) -> ThermalResult:
        """Process thermal images and detect anomalies."""
        output_dir.mkdir(parents=True, exist_ok=True)
        anomalies = []
        processed = 0

        for img_path_str in thermal_images:
            img_path = Path(img_path_str)
            img_anomalies = self._process_single(img_path)
            anomalies.extend(img_anomalies)
            processed += 1

        result = ThermalResult(
            run_id=run_id,
            anomalies=anomalies,
            images_processed=processed,
            demo_mode=self.demo_mode,
        )

        # Save findings
        findings_path = output_dir / "findings.json"
        findings_path.write_text(result.model_dump_json(indent=2))
        logger.info(f"Thermal: {len(anomalies)} anomalies found in {processed} images")

        return result

    def _process_single(self, img_path: Path) -> list[ThermalAnomaly]:
        """Process a single thermal image."""
        # Load temperature matrix
        temp_matrix = self._load_temperature_matrix(img_path)
        if temp_matrix is None:
            return []

        # Load GPS from sidecar if available
        gps_lat, gps_lon = self._load_gps_sidecar(img_path)

        # Detect anomalies
        return self._detect_anomalies(temp_matrix, str(img_path), gps_lat, gps_lon)

    def _load_temperature_matrix(self, img_path: Path) -> Optional[np.ndarray]:
        """Load temperature matrix from image file."""
        try:
            # Check for companion .npy file (synthetic data)
            npy_path = img_path.with_suffix(".npy")
            if npy_path.exists():
                return np.load(str(npy_path)).astype(float)

            # For .npy files directly
            if img_path.suffix.lower() == ".npy":
                return np.load(str(img_path)).astype(float)

            # For PNG/JPEG: decode pixel values to temperatures
            from PIL import Image
            img = Image.open(img_path).convert("L")
            pixel_array = np.array(img, dtype=float)
            # Map [0, 255] to [THERMAL_MIN_TEMP, THERMAL_MAX_TEMP]
            temp_matrix = (pixel_array / 255.0) * (
                self.THERMAL_MAX_TEMP - self.THERMAL_MIN_TEMP
            ) + self.THERMAL_MIN_TEMP
            return temp_matrix

        except Exception as e:
            logger.warning(f"Could not load temperature matrix from {img_path}: {e}")
            return None

    def _load_gps_sidecar(self, img_path: Path) -> tuple[Optional[float], Optional[float]]:
        """Load GPS from JSON sidecar file."""
        sidecar = img_path.with_suffix(".json")
        if sidecar.exists():
            try:
                data = json.loads(sidecar.read_text())
                return data.get("latitude"), data.get("longitude")
            except Exception:
                pass
        return None, None

    def _detect_anomalies(
        self,
        temp_matrix: np.ndarray,
        image_path: str,
        gps_lat: Optional[float],
        gps_lon: Optional[float],
    ) -> list[ThermalAnomaly]:
        """Detect thermal anomalies using threshold analysis."""
        image_name = Path(image_path).stem
        mean_temp = float(np.mean(temp_matrix))
        std_temp = float(np.std(temp_matrix))

        anomalies = []
        anomaly_idx = 0

        # Detect hotspots (moisture, leaks, electrical)
        hotspot_mask = temp_matrix > (mean_temp + self.anomaly_threshold_c)
        anomalies.extend(
            self._extract_regions(
                hotspot_mask, temp_matrix, mean_temp, image_path,
                gps_lat, gps_lon, "hotspot", image_name, anomaly_idx
            )
        )
        anomaly_idx += len(anomalies)

        # Detect cold bridges
        coldbridge_mask = temp_matrix < (mean_temp - self.anomaly_threshold_c)
        cold_anomalies = self._extract_regions(
            coldbridge_mask, temp_matrix, mean_temp, image_path,
            gps_lat, gps_lon, "cold_bridge", image_name, anomaly_idx
        )
        anomalies.extend(cold_anomalies)

        return anomalies

    def _extract_regions(
        self,
        mask: np.ndarray,
        temp_matrix: np.ndarray,
        mean_temp: float,
        image_path: str,
        gps_lat: Optional[float],
        gps_lon: Optional[float],
        anomaly_type: str,
        image_name: str,
        start_idx: int,
    ) -> list[ThermalAnomaly]:
        """Extract individual anomaly regions from a binary mask."""
        try:
            from scipy import ndimage
        except ImportError:
            # Fallback without scipy: treat all connected pixels as one region
            return self._extract_regions_simple(
                mask, temp_matrix, mean_temp, image_path,
                gps_lat, gps_lon, anomaly_type, image_name, start_idx
            )

        labeled, num_features = ndimage.label(mask)
        result = []

        for i in range(1, num_features + 1):
            region = labeled == i
            area = int(np.sum(region))
            if area < self.min_area_px:
                continue

            region_temps = temp_matrix[region]
            rows, cols = np.where(region)
            y1, x1 = int(rows.min()), int(cols.min())
            y2, x2 = int(rows.max()), int(cols.max())
            cy = float(np.mean(rows))
            cx = float(np.mean(cols))

            max_temp = float(region_temps.max())
            mean_region_temp = float(region_temps.mean())
            delta = abs(mean_region_temp - mean_temp)

            anomaly = ThermalAnomaly(
                image_path=image_path,
                anomaly_id=f"{image_name}_{anomaly_type}_{start_idx + len(result):03d}",
                center_x=cx,
                center_y=cy,
                bbox=[x1, y1, x2, y2],
                max_temp=max_temp,
                mean_temp=mean_region_temp,
                area_px=area,
                delta_temp=delta,
                anomaly_type=anomaly_type,
                gps_lat=gps_lat,
                gps_lon=gps_lon,
            )
            result.append(anomaly)

        return result

    def _extract_regions_simple(
        self,
        mask: np.ndarray,
        temp_matrix: np.ndarray,
        mean_temp: float,
        image_path: str,
        gps_lat: Optional[float],
        gps_lon: Optional[float],
        anomaly_type: str,
        image_name: str,
        start_idx: int,
    ) -> list[ThermalAnomaly]:
        """Simple region extraction without scipy."""
        if not np.any(mask):
            return []

        rows, cols = np.where(mask)
        if len(rows) < self.min_area_px:
            return []

        y1, x1 = int(rows.min()), int(cols.min())
        y2, x2 = int(rows.max()), int(cols.max())
        cy = float(np.mean(rows))
        cx = float(np.mean(cols))

        region_temps = temp_matrix[mask]
        max_temp = float(region_temps.max())
        mean_region_temp = float(region_temps.mean())
        delta = abs(mean_region_temp - mean_temp)
        area = int(np.sum(mask))

        return [ThermalAnomaly(
            image_path=image_path,
            anomaly_id=f"{image_name}_{anomaly_type}_{start_idx:03d}",
            center_x=cx,
            center_y=cy,
            bbox=[x1, y1, x2, y2],
            max_temp=max_temp,
            mean_temp=mean_region_temp,
            area_px=area,
            delta_temp=delta,
            anomaly_type=anomaly_type,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
        )]
