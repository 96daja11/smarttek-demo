# Modellvikter – Sprickdetektering

## Produktionsmodell (ej inkluderad i repot)

För produktionsanvändning krävs en YOLOv8-modell tränad på fastighetsbilder.

### Ladda ner förtränad nano-modell (för test/demo)

```bash
# Ladda ner YOLOv8n (allmän objektdetektering) för felsökning
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
# Kopiera till rätt plats:
cp ~/.config/Ultralytics/yolov8n.pt models/crack_detection/best.pt
```

### Träna en domänspecifik modell

Se `notebooks/train_crack_detector.ipynb` för träningsscript på
fastighets- och takbilder.

Rekommenderade dataset:
- [RoofDamage Dataset](https://github.com/microsoft/RoofdamageDetection)
- [Crack Detection Dataset (Kaggle)](https://www.kaggle.com/datasets/arunrk7/surface-crack-detection)

### Demo-läge

I demo-läge används en mock-detektor som returnerar syntetiska fynd.
Inga modellvikter behövs för `python tests/sample_run.py`.

### Kommersiell licens

YOLOv8 är licensierat under AGPL-3.0.
Vid kommersiell skalning, utvärdera Ultralytics Enterprise (~400 USD/år).
Se: https://ultralytics.com/license
