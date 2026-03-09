# SmartTek AB – Drönbaserad Fastighetsinspektion

> De flesta levererar bilder. Vi levererar svar.

End-to-end pipeline för drönbaserad fastighetsinspektion med RGB-fotogrammetri,
termisk analys och AI-skadedetektering.

## Snabbstart

```bash
# 1. Klona repot
git clone https://github.com/96daja11/smarttek-demo
cd smarttek-demo

# 2. Installera beroenden (kräver uv)
uv sync

# 3. Kör demo-pipeline (skapar exempeldata + kör alla 6 steg + genererar PDF)
uv run python tests/sample_run.py

# 4. Öppna rapporten
open data/outputs/sample/report/rapport_sample.pdf
```

## Pipeline-steg

| Steg | Modul | Beskrivning |
|------|-------|-------------|
| 1 | `pipeline/ingest` | Validering, metadata-extraktion, GPS-parsing |
| 2 | `pipeline/photogrammetry` | WebODM-integration, ortofotogenerering |
| 3 | `pipeline/thermal` | FLIR-extraktion, anomalidetektion |
| 4 | `pipeline/detection` | YOLOv8-inferens på RGB-bilder |
| 5 | `pipeline/analysis` | Georeferering, klassificering, GeoJSON |
| 6 | `pipeline/report` | PDF-rapport med WeasyPrint + Jinja2 |

## Demo med Docker Compose

```bash
# Starta API + frontend (utan WebODM)
docker compose up api frontend

# Öppna demo-UI
open http://localhost:3000
```

## Konfiguration

Kopiera `.env.example` till `.env` och justera parametrarna:

```bash
cp .env.example .env
```

## Licens

Analyslogiken i `pipeline/` är proprietär – SmartTek AB.
Se `CLAUDE.md` för information om tredjepartslicenser.
