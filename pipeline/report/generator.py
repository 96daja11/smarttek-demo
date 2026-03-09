"""Steg 6: Rapport-generering med WeasyPrint och Jinja2."""
from __future__ import annotations
import base64
import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SEVERITY_COLORS = {
    "KRITISK": "#9b1d1d",
    "HÖG":     "#b5451b",
    "MEDEL":   "#c87d2f",
    "LÅG":     "#2d6a4f",
}

FINDING_TYPE_LABELS = {
    "crack":        "Spricka",
    "water_damage": "Vattenskada",
    "delamination": "Avlösning",
    "rust":         "Rost",
    "vegetation":   "Vegetation",
    "anomaly":      "Termisk anomali",
}

SOURCE_LABELS = {
    "RGB-AI":    "RGB-AI",
    "Termisk":   "Termisk",
    "Kombinerad":"Kombinerad",
}


class ReportResult(BaseModel):
    run_id: str
    pdf_path: str
    html_path: Optional[str] = None
    generated_at: str = ""


def _encode_image_b64(img_path: str) -> Optional[str]:
    """Encode image file as base64 data URI."""
    try:
        path = Path(img_path)
        if not path.exists():
            return None
        ext = path.suffix.lower()
        mime = {
            ".png":  "image/png",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".svg":  "image/svg+xml",
        }.get(ext, "image/png")
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def _generate_logo_svg() -> str:
    """Generate SmartTek logo as inline SVG."""
    return """<svg width="180" height="40" viewBox="0 0 180 40" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="40" height="40" rx="6" fill="#00d4aa"/>
  <path d="M8 32 L8 8 L20 8 L20 20 L32 20 L32 32 Z" fill="#0d1b2a" stroke="none"/>
  <path d="M20 8 L32 8 L32 20 Z" fill="#0d1b2a" opacity="0.5"/>
  <text x="50" y="27" font-family="DM Serif Display, Georgia, serif" font-size="20" fill="#ffffff" font-weight="400">SmartTek</text>
</svg>"""


def _generate_pie_chart(kritisk: int, hog: int, medel: int, lag: int) -> str:
    """Generate a pie chart as base64 PNG."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np

        fig, ax = plt.subplots(figsize=(5, 4), facecolor="#0d1b2a")
        ax.set_facecolor("#0d1b2a")

        values = [kritisk, hog, medel, lag]
        labels = ["KRITISK", "HÖG", "MEDEL", "LÅG"]
        colors = ["#9b1d1d", "#b5451b", "#c87d2f", "#2d6a4f"]

        # Filter out zeros
        active = [(v, l, c) for v, l, c in zip(values, labels, colors) if v > 0]
        if not active:
            active = [(1, "INGA FYND", "#4a5568")]

        vals, labs, cols = zip(*active)

        wedges, texts, autotexts = ax.pie(
            vals,
            labels=labs,
            colors=cols,
            autopct="%1.0f%%",
            startangle=90,
            wedgeprops={"edgecolor": "#0d1b2a", "linewidth": 2},
            textprops={"color": "white", "fontsize": 10},
        )
        for at in autotexts:
            at.set_color("white")
            at.set_fontsize(9)
            at.set_fontweight("bold")

        ax.set_title("Fynd per allvarlighetsgrad", color="white", fontsize=12, pad=15)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                    facecolor="#0d1b2a", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return "data:image/png;base64," + base64.b64encode(buf.read()).decode()
    except Exception as e:
        logger.warning(f"Could not generate pie chart: {e}")
        return ""


def _generate_temperature_heatmap(thermal_findings: list) -> str:
    """Generate a temperature distribution chart as base64 PNG."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        fig, ax = plt.subplots(figsize=(7, 3.5), facecolor="#0d1b2a")
        ax.set_facecolor("#111827")

        if thermal_findings:
            temps = [f.max_temp for f in thermal_findings if hasattr(f, 'max_temp')]
            deltas = [f.delta_temp for f in thermal_findings if hasattr(f, 'delta_temp')]
        else:
            # Demo data
            np.random.seed(42)
            temps = list(np.random.normal(18, 5, 15)) + list(np.random.normal(32, 3, 5))
            deltas = [abs(t - 18) for t in temps]

        ax.bar(range(len(temps)), temps, color=[
            "#9b1d1d" if t > 28 else "#b5451b" if t > 24 else "#c87d2f" if t > 20 else "#2d6a4f"
            for t in temps
        ], edgecolor="#0d1b2a", linewidth=0.5)

        ax.axhline(y=sum(temps)/len(temps), color="#00d4aa", linestyle="--",
                   linewidth=1.5, label=f"Medel: {sum(temps)/len(temps):.1f}°C")

        ax.set_xlabel("Termisk punkt", color="#94a3b8", fontsize=9)
        ax.set_ylabel("Temperatur (°C)", color="#94a3b8", fontsize=9)
        ax.set_title("Termiska avvikelser – temperaturprofil", color="white", fontsize=11)
        ax.tick_params(colors="#64748b")
        ax.spines['bottom'].set_color("#334155")
        ax.spines['left'].set_color("#334155")
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.legend(facecolor="#1e293b", labelcolor="white", fontsize=8)

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=120, bbox_inches="tight",
                    facecolor="#0d1b2a", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return "data:image/png;base64," + base64.b64encode(buf.read()).decode()
    except Exception as e:
        logger.warning(f"Could not generate temperature chart: {e}")
        return ""


def _generate_map_svg(findings: list, bbox: list, center_lat: float, center_lon: float) -> str:
    """Generate a static SVG map with georeferenced findings."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np

        fig, ax = plt.subplots(figsize=(8, 6), facecolor="#0d1b2a")
        ax.set_facecolor("#1a2744")

        # Draw a simple stylized map background
        # Property outline
        prop_rect = plt.Rectangle((0.1, 0.1), 0.8, 0.8,
                                   facecolor="#1e3a5f", edgecolor="#334f7a",
                                   linewidth=2, transform=ax.transAxes)
        ax.add_patch(prop_rect)

        # Add some roof sections
        for (x, y, w, h) in [(0.15, 0.15, 0.3, 0.35), (0.55, 0.2, 0.3, 0.3),
                               (0.2, 0.6, 0.25, 0.25), (0.6, 0.55, 0.25, 0.3)]:
            rect = plt.Rectangle((x, y), w, h,
                                  facecolor="#243852", edgecolor="#405880",
                                  linewidth=1, transform=ax.transAxes)
            ax.add_patch(rect)

        severity_colors = {
            "KRITISK": "#9b1d1d",
            "HÖG":     "#b5451b",
            "MEDEL":   "#c87d2f",
            "LÅG":     "#2d6a4f",
        }

        # Plot findings
        if bbox and len(bbox) >= 4:
            lon_min, lat_min, lon_max, lat_max = bbox
            lon_range = lon_max - lon_min or 0.01
            lat_range = lat_max - lat_min or 0.01
        else:
            lon_min, lat_min, lon_range, lat_range = 11.96, 57.70, 0.01, 0.01

        plotted = set()
        for f in findings:
            if not hasattr(f, 'lon') or not hasattr(f, 'lat'):
                continue
            x_norm = (f.lon - lon_min) / lon_range * 0.7 + 0.15
            y_norm = (f.lat - lat_min) / lat_range * 0.7 + 0.15
            x_norm = max(0.15, min(0.85, x_norm))
            y_norm = max(0.15, min(0.85, y_norm))

            color = severity_colors.get(f.severity, "#888888")
            ax.plot(x_norm, y_norm, "o", markersize=12, color=color,
                    markeredgecolor="white", markeredgewidth=1.5,
                    transform=ax.transAxes, zorder=5)

            # Label
            if f.finding_id not in plotted:
                label = f.finding_id.split("_")[-1] if "_" in f.finding_id else f.finding_id[:4]
                ax.text(x_norm + 0.02, y_norm + 0.02, label[:6],
                        color="white", fontsize=6, transform=ax.transAxes, zorder=6)
                plotted.add(f.finding_id)

        # Legend
        legend_elements = [
            mpatches.Patch(color=c, label=s)
            for s, c in severity_colors.items()
        ]
        ax.legend(handles=legend_elements, loc="lower right", facecolor="#0d1b2a",
                  labelcolor="white", fontsize=8, framealpha=0.9, edgecolor="#334155")

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_title(f"Georefererade fynd – {center_lat:.4f}°N, {center_lon:.4f}°E",
                     color="white", fontsize=11, pad=10)
        ax.set_xlabel("", color="white")
        ax.set_ylabel("", color="white")
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        for spine in ax.spines.values():
            spine.set_edgecolor("#334155")

        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                    facecolor="#0d1b2a", edgecolor="none")
        plt.close(fig)
        buf.seek(0)
        return "data:image/png;base64," + base64.b64encode(buf.read()).decode()
    except Exception as e:
        logger.warning(f"Could not generate map: {e}")
        return ""


def _generate_thermal_comparison(thermal_images: list, rgb_images: list) -> list[dict]:
    """Generate thermal/RGB side-by-side comparison images."""
    comparisons = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        import numpy as np
        from PIL import Image

        pairs = list(zip(
            thermal_images[:3],
            rgb_images[:3] if rgb_images else [None, None, None]
        ))

        for i, (thermal_path, rgb_path) in enumerate(pairs):
            if thermal_path is None:
                continue

            fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), facecolor="#0d1b2a")
            fig.suptitle(
                f"Termisk analys – bild {i+1}",
                color="white", fontsize=13, fontweight="bold"
            )

            # Load thermal
            try:
                npy_path = Path(str(thermal_path)).with_suffix(".npy")
                if npy_path.exists():
                    temp_matrix = np.load(str(npy_path))
                else:
                    img = Image.open(thermal_path).convert("L")
                    temp_matrix = np.array(img, dtype=float) / 255.0 * 60.0

                im = axes[0].imshow(temp_matrix, cmap="inferno", vmin=temp_matrix.min(), vmax=temp_matrix.max())
                axes[0].set_title("Termisk bild (°C)", color="white", fontsize=10)
                axes[0].axis("off")
                cbar = plt.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04)
                cbar.set_label("°C", color="white", fontsize=9)
                cbar.ax.yaxis.set_tick_params(color="white")
                plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color="white")
            except Exception as e:
                axes[0].set_facecolor("#1e293b")
                axes[0].text(0.5, 0.5, "Termisk bild\n(ej tillgänglig)",
                             ha="center", va="center", color="#64748b", transform=axes[0].transAxes)
                axes[0].set_title("Termisk bild", color="white", fontsize=10)
                axes[0].axis("off")

            # Load RGB
            try:
                if rgb_path and Path(str(rgb_path)).exists():
                    rgb_img = np.array(Image.open(str(rgb_path)))
                    axes[1].imshow(rgb_img)
                else:
                    raise FileNotFoundError
            except Exception:
                # Generate synthetic RGB view
                axes[1].set_facecolor("#243852")
                axes[1].text(0.5, 0.5, "RGB-bild",
                             ha="center", va="center", color="#64748b",
                             transform=axes[1].transAxes, fontsize=14)

            axes[1].set_title("RGB-bild", color="white", fontsize=10)
            axes[1].axis("off")

            for ax in axes:
                ax.set_facecolor("#1a2744")

            plt.tight_layout()
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                        facecolor="#0d1b2a", edgecolor="none")
            plt.close(fig)
            buf.seek(0)
            comparisons.append({
                "title": f"Bildanalys {i+1}",
                "image": "data:image/png;base64," + base64.b64encode(buf.read()).decode(),
            })

    except Exception as e:
        logger.warning(f"Could not generate thermal comparisons: {e}")

    return comparisons


class ReportGenerator:
    """Generates professional PDF inspection reports."""

    def __init__(
        self,
        template_dir: Optional[Path] = None,
        company_name: str = "SmartTek AB",
        logo_path: Optional[str] = None,
        demo_mode: bool = False,
    ):
        self.template_dir = template_dir or (
            Path(__file__).parent / "templates"
        )
        self.company_name = company_name
        self.logo_path = logo_path
        self.demo_mode = demo_mode

    def generate(
        self,
        analysis_result,
        detection_result,
        thermal_result,
        ingest_result,
        output_dir: Path,
        run_id: str,
    ) -> ReportResult:
        """Generate a complete PDF inspection report."""
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Generate charts
        summary = analysis_result.summary
        pie_chart = _generate_pie_chart(
            summary.kritisk_count,
            summary.hog_count,
            summary.medel_count,
            summary.lag_count,
        )

        temp_chart = _generate_temperature_heatmap(
            thermal_result.anomalies if thermal_result else []
        )

        map_image = _generate_map_svg(
            analysis_result.findings,
            analysis_result.bbox,
            analysis_result.center_lat,
            analysis_result.center_lon,
        )

        # Thermal comparisons
        thermal_paths = [i.path for i in (ingest_result.thermal_images or [])]
        rgb_paths = [i.path for i in (ingest_result.rgb_images or [])]
        comparisons = _generate_thermal_comparison(thermal_paths, rgb_paths)

        # Logo
        logo_svg = _generate_logo_svg()

        # Prepare findings data for template
        findings_data = []
        for f in analysis_result.findings:
            findings_data.append({
                "id": f.finding_id,
                "type": FINDING_TYPE_LABELS.get(f.finding_type, f.finding_type),
                "type_raw": f.finding_type,
                "severity": f.severity,
                "severity_color": SEVERITY_COLORS.get(f.severity, "#888"),
                "source": f.source,
                "confidence": f.confidence,
                "confidence_pct": int(f.confidence * 100),
                "lat": f.lat,
                "lon": f.lon,
                "area_m2": f.area_m2,
                "description": f.description,
                "action": f.action_recommendation,
                "urgency_weeks": f.urgency_weeks,
                "cost_sek": f"{f.estimated_cost_sek:,}".replace(",", " ") if f.estimated_cost_sek else "–",
                "cost_raw": f.estimated_cost_sek or 0,
            })

        # Action plan: top findings by severity and urgency
        severity_order = {"KRITISK": 0, "HÖG": 1, "MEDEL": 2, "LÅG": 3}
        action_plan = sorted(
            [f for f in findings_data if f.get("cost_raw", 0) > 0],
            key=lambda x: (severity_order.get(x["severity"], 9), x.get("urgency_weeks", 999))
        )[:10]

        # Calculate total cost
        total_cost = sum(f.get("cost_raw", 0) for f in findings_data)

        # Render HTML
        html = self._render_template(
            run_id=run_id,
            generated_at=generated_at,
            summary=summary,
            findings=findings_data,
            action_plan=action_plan,
            pie_chart=pie_chart,
            temp_chart=temp_chart,
            map_image=map_image,
            comparisons=comparisons,
            logo_svg=logo_svg,
            total_cost=f"{total_cost:,}".replace(",", " "),
        )

        # Save HTML
        html_path = output_dir / f"rapport_{run_id}.html"
        html_path.write_text(html, encoding="utf-8")

        # Generate PDF
        pdf_path = output_dir / f"rapport_{run_id}.pdf"
        try:
            import weasyprint
            pdf_bytes = weasyprint.HTML(string=html, base_url=str(output_dir)).write_pdf()
            pdf_path.write_bytes(pdf_bytes)
            logger.info(f"PDF report generated: {pdf_path}")
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            # Save HTML as fallback
            pdf_path = html_path

        return ReportResult(
            run_id=run_id,
            pdf_path=str(pdf_path),
            html_path=str(html_path),
            generated_at=generated_at,
        )

    def _render_template(self, **context) -> str:
        """Render the Jinja2 HTML template."""
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html"]),
        )

        try:
            template = env.get_template("report.html")
            return template.render(**context)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            raise
