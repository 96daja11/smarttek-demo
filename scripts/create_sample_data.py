"""
Create synthetic sample data for SmartTek demo pipeline.
Generates realistic-looking aerial roof images and thermal images with anomalies.
"""
from __future__ import annotations
import json
import math
import os
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# GPS coordinates in Gothenburg, Sweden
BASE_LAT = 57.7089
BASE_LON = 11.9746
ALTITUDE = 75.0  # meters

RGB_DIR   = Path("data/sample/rgb")
THERMAL_DIR = Path("data/sample/thermal")
PRECOMPUTED_DIR = Path("data/sample/precomputed")


def _encode_dms(decimal_degrees: float):
    """Encode decimal degrees to EXIF DMS rational format."""
    is_negative = decimal_degrees < 0
    decimal_degrees = abs(decimal_degrees)
    degrees = int(decimal_degrees)
    minutes_float = (decimal_degrees - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    # Return as tuples of (numerator, denominator)
    return (degrees, 1), (minutes, 1), (int(seconds * 1000), 1000)


def _write_exif_gps(img: Image.Image, lat: float, lon: float, alt: float) -> Image.Image:
    """Write GPS EXIF data to PIL image."""
    try:
        import piexif
        exif_dict = {"GPS": {}}
        gps = exif_dict["GPS"]

        lat_ref = b"N" if lat >= 0 else b"S"
        lon_ref = b"E" if lon >= 0 else b"W"

        gps[piexif.GPSIFD.GPSLatitudeRef] = lat_ref
        gps[piexif.GPSIFD.GPSLatitude] = _encode_dms(lat)
        gps[piexif.GPSIFD.GPSLongitudeRef] = lon_ref
        gps[piexif.GPSIFD.GPSLongitude] = _encode_dms(lon)
        gps[piexif.GPSIFD.GPSAltitude] = (int(alt * 100), 100)
        gps[piexif.GPSIFD.GPSAltitudeRef] = 0

        exif_bytes = piexif.dump(exif_dict)

        buf = __import__("io").BytesIO()
        img.save(buf, format="JPEG", exif=exif_bytes, quality=90)
        buf.seek(0)
        return Image.open(buf)
    except Exception as e:
        print(f"  Warning: could not write EXIF GPS: {e}")
        return img


def create_rgb_roof_image(
    output_path: Path,
    lat: float,
    lon: float,
    image_num: int,
    size: tuple[int, int] = (1280, 960),
) -> None:
    """Create a synthetic aerial roof image."""
    w, h = size
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)

    # Base color: gravel/concrete roof
    base_colors = [
        (128, 122, 115),
        (140, 132, 125),
        (118, 115, 110),
    ]
    base_color = base_colors[image_num % len(base_colors)]

    # Fill background with slight noise
    arr = np.random.randint(
        max(0, base_color[0] - 15),
        min(255, base_color[0] + 15),
        (h, w, 3),
        dtype=np.uint8
    )
    arr[:, :, 1] = np.clip(arr[:, :, 0] - 8 + np.random.randint(-5, 5, (h, w)), 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 0] - 12 + np.random.randint(-5, 5, (h, w)), 0, 255)

    img = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(img)

    # Draw roof sections with slightly different shades
    sections = [
        (int(w * 0.05), int(h * 0.05), int(w * 0.55), int(h * 0.45), 12),
        (int(w * 0.60), int(h * 0.08), int(w * 0.95), int(h * 0.50), -8),
        (int(w * 0.08), int(h * 0.55), int(w * 0.45), int(h * 0.92), 8),
        (int(w * 0.55), int(h * 0.55), int(w * 0.92), int(h * 0.92), -5),
    ]
    for x1, y1, x2, y2, delta in sections:
        section_color = tuple(max(0, min(255, c + delta + np.random.randint(-5, 5))) for c in base_color)
        draw.rectangle([x1, y1, x2, y2], fill=section_color, outline=(90, 85, 80), width=3)

    # Add skylights
    for sx, sy in [(int(w*0.25), int(h*0.2)), (int(w*0.72), int(h*0.25))]:
        draw.rectangle([sx, sy, sx+60, sy+40], fill=(50, 50, 55), outline=(40, 40, 45), width=2)
        draw.line([sx, sy, sx+60, sy+40], fill=(40, 40, 45), width=1)
        draw.line([sx+60, sy, sx, sy+40], fill=(40, 40, 45), width=1)

    # Add drainage/pipes
    draw.rectangle([int(w*0.5)-5, int(h*0.05), int(w*0.5)+5, int(h*0.95)],
                   fill=(80, 78, 75), outline=(60, 58, 55))

    # Add DAMAGE based on image number
    if image_num == 0:
        # Cracks
        np.random.seed(10)
        for _ in range(3):
            x1 = np.random.randint(100, w-200)
            y1 = np.random.randint(100, h-200)
            length = np.random.randint(60, 180)
            angle = np.random.uniform(0, math.pi)
            x2 = int(x1 + length * math.cos(angle))
            y2 = int(y1 + length * math.sin(angle))
            draw.line([x1, y1, x2, y2], fill=(55, 50, 45), width=2)
            # Add crack branching
            mid_x, mid_y = (x1 + x2) // 2, (y1 + y2) // 2
            branch_angle = angle + math.pi/4
            draw.line([mid_x, mid_y,
                       int(mid_x + 40 * math.cos(branch_angle)),
                       int(mid_y + 40 * math.sin(branch_angle))],
                      fill=(60, 55, 50), width=1)

    elif image_num == 1:
        # Water damage / discoloration patches
        np.random.seed(20)
        for _ in range(2):
            x1 = np.random.randint(150, w-200)
            y1 = np.random.randint(150, h-200)
            patch_w = np.random.randint(80, 160)
            patch_h = np.random.randint(60, 120)
            # Dark stain
            stain = Image.new("RGBA", (patch_w, patch_h), (70, 85, 95, 140))
            img.paste(stain, (x1, y1), stain)

    elif image_num == 2:
        # Vegetation / moss growth
        np.random.seed(30)
        for _ in range(4):
            x = np.random.randint(50, w-50)
            y = np.random.randint(50, h-50)
            r = np.random.randint(20, 60)
            # Green patches
            for dy in range(-r, r):
                for dx in range(-r, r):
                    if dx*dx + dy*dy < r*r and 0 <= x+dx < w and 0 <= y+dy < h:
                        if np.random.random() > 0.4:
                            green_val = np.random.randint(60, 100)
                            gray_val = np.random.randint(60, 90)
                            img.putpixel((x+dx, y+dy), (gray_val, green_val, gray_val-20))

    # Apply slight blur for realism
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    # Add GPS EXIF
    img = _write_exif_gps(img, lat, lon, ALTITUDE)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), format="JPEG", quality=88)
    print(f"  Created RGB: {output_path.name} ({lat:.5f}°N, {lon:.5f}°E)")


def create_thermal_image(
    output_path: Path,
    lat: float,
    lon: float,
    image_num: int,
    size: tuple[int, int] = (640, 480),
) -> None:
    """
    Create a synthetic thermal image with injected anomalies.
    Saves both a PNG (grayscale, pixels mapped to temperature)
    and a .npy file with actual temperature values.
    Also creates a .json sidecar with GPS.
    """
    w, h = size
    np.random.seed(100 + image_num * 7)

    # Base temperature: uniform roof temperature ~15–20°C with natural variation
    base_temp = 16.0 + image_num * 1.5
    temp_matrix = np.random.normal(base_temp, 2.0, (h, w))

    # Add gradient (sun exposure effect)
    x_grad = np.linspace(-2, 2, w)
    y_grad = np.linspace(-1, 1, h)
    xx, yy = np.meshgrid(x_grad, y_grad)
    temp_matrix += xx * 0.8 + yy * 0.5

    # Inject HOTSPOTS (moisture, leak, electrical)
    hotspots = [
        (int(w * 0.25), int(h * 0.30), 35, 12.0),  # x, y, radius, extra_temp
        (int(w * 0.70), int(h * 0.60), 25, 9.0),
    ]
    for cx, cy, r, extra in hotspots:
        for y in range(max(0, cy-r), min(h, cy+r)):
            for x in range(max(0, cx-r), min(w, cx+r)):
                dist = math.sqrt((x-cx)**2 + (y-cy)**2)
                if dist < r:
                    factor = 1.0 - (dist / r) ** 2
                    temp_matrix[y, x] += extra * factor

    # Inject COLD BRIDGES (thermal bridges in wall/roof junction)
    cold_bridges = [
        (0, int(h * 0.5), w, int(h * 0.5) + 8, -5.0),   # horizontal cold bridge
        (int(w * 0.5), 0, int(w * 0.5) + 8, h, -4.0),   # vertical cold bridge
    ]
    for x1, y1, x2, y2, delta in cold_bridges:
        x1, x2 = max(0, x1), min(w, x2)
        y1, y2 = max(0, y1), min(h, y2)
        temp_matrix[y1:y2, x1:x2] += delta

    # Add sensor noise
    temp_matrix += np.random.normal(0, 0.3, (h, w))

    # Save numpy array (actual temperatures)
    npy_path = output_path.with_suffix(".npy")
    np.save(str(npy_path), temp_matrix.astype(np.float32))

    # Convert to grayscale PNG (0°C = 0, 60°C = 255)
    min_temp, max_temp = 0.0, 60.0
    normalized = np.clip((temp_matrix - min_temp) / (max_temp - min_temp), 0, 1)
    pixel_array = (normalized * 255).astype(np.uint8)
    img = Image.fromarray(pixel_array, mode="L")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), format="PNG")

    # Save GPS sidecar JSON
    sidecar = {
        "latitude": lat,
        "longitude": lon,
        "altitude": ALTITUDE,
        "camera": "DJI_FLIR_640",
        "min_temp_c": float(temp_matrix.min()),
        "max_temp_c": float(temp_matrix.max()),
        "mean_temp_c": float(temp_matrix.mean()),
    }
    output_path.with_suffix(".json").write_text(
        json.dumps(sidecar, indent=2)
    )

    print(f"  Created thermal: {output_path.name} "
          f"(temp range: {temp_matrix.min():.1f}–{temp_matrix.max():.1f}°C, "
          f"{lat:.5f}°N, {lon:.5f}°E)")


def create_synthetic_orthophoto() -> None:
    """Create a simple synthetic orthophoto as a placeholder."""
    PRECOMPUTED_DIR.mkdir(parents=True, exist_ok=True)
    ortho_path = PRECOMPUTED_DIR / "orthophoto.tif"

    arr = np.zeros((1024, 1024, 3), dtype=np.uint8)
    arr[:, :] = [130, 125, 120]

    # Roof sections
    arr[80:400, 80:900] = [115, 110, 105]
    arr[450:800, 100:850] = [125, 120, 115]
    arr[50:200, 50:200] = [80, 82, 88]  # shadow

    img = Image.fromarray(arr)
    img.save(str(ortho_path), format="TIFF")
    print(f"  Created orthophoto: {ortho_path}")


def main():
    print("SmartTek – Creating synthetic sample data...")
    print()

    RGB_DIR.mkdir(parents=True, exist_ok=True)
    THERMAL_DIR.mkdir(parents=True, exist_ok=True)

    # Create 3 RGB images
    print("RGB roof images:")
    for i in range(3):
        lat = BASE_LAT + i * 0.0001
        lon = BASE_LON + i * 0.0001
        path = RGB_DIR / f"roof_{i+1:02d}.jpg"
        create_rgb_roof_image(path, lat, lon, i)

    print()

    # Create 2 thermal images
    print("Thermal images with anomalies:")
    for i in range(2):
        lat = BASE_LAT + i * 0.0001 + 0.00005
        lon = BASE_LON + i * 0.0001 + 0.00003
        path = THERMAL_DIR / f"thermal_{i+1:02d}.png"
        create_thermal_image(path, lat, lon, i)

    print()

    # Create orthophoto
    print("Precomputed orthophoto:")
    create_synthetic_orthophoto()

    print()
    print("Sample data created successfully!")
    print(f"  RGB images:     {RGB_DIR}")
    print(f"  Thermal images: {THERMAL_DIR}")
    print(f"  Orthophoto:     {PRECOMPUTED_DIR}")


if __name__ == "__main__":
    # Change to project root if running from scripts/
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    main()
