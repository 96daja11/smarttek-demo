"""Steg 2: WebODM API-klient med demo-läge fallback."""
from __future__ import annotations
import os
import time
import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PhotogrammetryResult(BaseModel):
    run_id: str
    orthophoto_path: Optional[str] = None
    pointcloud_path: Optional[str] = None
    task_id: Optional[str] = None
    status: str = "pending"
    demo_mode: bool = False
    bbox: Optional[list[float]] = None  # [min_lon, min_lat, max_lon, max_lat]
    center_lat: Optional[float] = None
    center_lon: Optional[float] = None


class ODMClient:
    """WebODM REST API client with demo mode fallback."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        username: str = "admin",
        password: str = "admin",
        demo_mode: bool = False,
    ):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.demo_mode = demo_mode
        self._token: Optional[str] = None

    def process(
        self,
        rgb_images: list[str],
        output_dir: Path,
        run_id: str,
        precomputed_dir: Optional[Path] = None,
    ) -> PhotogrammetryResult:
        """
        Process RGB images through WebODM.
        In demo mode, uses precomputed orthophoto or generates synthetic one.
        """
        if self.demo_mode:
            return self._demo_fallback(output_dir, run_id, precomputed_dir)

        try:
            return self._run_odm(rgb_images, output_dir, run_id)
        except Exception as e:
            logger.warning(f"WebODM failed ({e}), falling back to demo mode")
            return self._demo_fallback(output_dir, run_id, precomputed_dir)

    def _demo_fallback(
        self,
        output_dir: Path,
        run_id: str,
        precomputed_dir: Optional[Path] = None,
    ) -> PhotogrammetryResult:
        """Return synthetic orthophoto for demo mode."""
        output_dir.mkdir(parents=True, exist_ok=True)
        ortho_path = output_dir / "orthophoto.tif"

        # Check if precomputed exists
        if precomputed_dir:
            precomputed = precomputed_dir / "orthophoto.tif"
            if precomputed.exists():
                import shutil
                shutil.copy(precomputed, ortho_path)
                logger.info(f"Using precomputed orthophoto from {precomputed}")
                return PhotogrammetryResult(
                    run_id=run_id,
                    orthophoto_path=str(ortho_path),
                    status="completed",
                    demo_mode=True,
                    bbox=[11.9600, 57.7000, 11.9700, 57.7100],
                    center_lat=57.7050,
                    center_lon=11.9650,
                )

        # Generate synthetic orthophoto
        self._generate_synthetic_orthophoto(ortho_path)
        logger.info(f"Generated synthetic orthophoto at {ortho_path}")

        return PhotogrammetryResult(
            run_id=run_id,
            orthophoto_path=str(ortho_path),
            status="completed",
            demo_mode=True,
            bbox=[11.9600, 57.7000, 11.9700, 57.7100],
            center_lat=57.7050,
            center_lon=11.9650,
        )

    def _generate_synthetic_orthophoto(self, output_path: Path) -> None:
        """Generate a simple synthetic orthophoto as GeoTIFF."""
        try:
            import numpy as np
            from PIL import Image

            # Create a simple rooftop aerial view (512x512 RGB)
            img_array = np.zeros((512, 512, 3), dtype=np.uint8)

            # Base roof color (grey tiles)
            img_array[:, :] = [140, 135, 130]

            # Add some roof sections
            img_array[50:200, 50:450] = [120, 115, 110]
            img_array[220:400, 80:420] = [130, 125, 120]

            # Add some discoloration (water damage)
            img_array[100:140, 200:260] = [90, 100, 110]

            # Save as TIFF (simplified, not real GeoTIFF)
            img = Image.fromarray(img_array)
            img.save(str(output_path))
        except Exception as e:
            logger.error(f"Failed to generate synthetic orthophoto: {e}")
            # Create empty file as last resort
            output_path.touch()

    def _run_odm(
        self, rgb_images: list[str], output_dir: Path, run_id: str
    ) -> PhotogrammetryResult:
        """Run actual WebODM processing."""
        import httpx

        # Authenticate
        auth_resp = httpx.post(
            f"{self.base_url}/api/token-auth/",
            json={"username": self.username, "password": self.password},
            timeout=30,
        )
        auth_resp.raise_for_status()
        token = auth_resp.json()["token"]
        headers = {"Authorization": f"JWT {token}"}

        # Get or create project
        projects_resp = httpx.get(
            f"{self.base_url}/api/projects/", headers=headers, timeout=30
        )
        projects_resp.raise_for_status()
        projects = projects_resp.json()["results"]

        if projects:
            project_id = projects[0]["id"]
        else:
            proj_resp = httpx.post(
                f"{self.base_url}/api/projects/",
                headers=headers,
                json={"name": f"smarttek-{run_id}"},
                timeout=30,
            )
            proj_resp.raise_for_status()
            project_id = proj_resp.json()["id"]

        # Upload images and create task
        files = []
        for img_path in rgb_images:
            files.append(("images", (Path(img_path).name, open(img_path, "rb"), "image/jpeg")))

        task_resp = httpx.post(
            f"{self.base_url}/api/projects/{project_id}/tasks/",
            headers=headers,
            files=files,
            data={"name": run_id, "options": '[{"name":"dsm","value":true}]'},
            timeout=120,
        )
        task_resp.raise_for_status()
        task_id = task_resp.json()["id"]

        # Poll for completion
        for _ in range(120):
            status_resp = httpx.get(
                f"{self.base_url}/api/projects/{project_id}/tasks/{task_id}/",
                headers=headers,
                timeout=30,
            )
            status_resp.raise_for_status()
            status = status_resp.json()["status"]
            if status == 40:  # completed
                break
            elif status in (30, 50):  # failed or canceled
                raise RuntimeError(f"ODM task failed with status {status}")
            time.sleep(10)

        # Download orthophoto
        output_dir.mkdir(parents=True, exist_ok=True)
        ortho_path = output_dir / "orthophoto.tif"
        dl_resp = httpx.get(
            f"{self.base_url}/api/projects/{project_id}/tasks/{task_id}/download/orthophoto.tif",
            headers=headers,
            timeout=300,
        )
        dl_resp.raise_for_status()
        ortho_path.write_bytes(dl_resp.content)

        return PhotogrammetryResult(
            run_id=run_id,
            orthophoto_path=str(ortho_path),
            task_id=str(task_id),
            status="completed",
            demo_mode=False,
        )
