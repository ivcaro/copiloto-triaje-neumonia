"""Puntos de entrada del curso sobre el código real del proyecto.

El curso pide una carpeta `src/` con `data_processing.py`, `model.py`, `train.py`,
`evaluate.py` y `utils.py`. El código del proyecto está probado y desplegado con
otra estructura, y no se movió: vive en el paquete `src/copiloto_triaje/`, que es
lo que instalan `pip install .` y las imágenes de Docker. Los módulos de esta
carpeta son finos: cada uno dice en su docstring qué es y dónde está la
implementación, y reexporta o llama a `copiloto_triaje` sin duplicar lógica.

    data_processing  ->  copiloto_triaje.datos          (DICOM, manifiestos, partición)
    model            ->  copiloto_triaje.modelo, .servicio   (arquitectura, pesos desplegados)
    train            ->  scripts/entrenar_local.py      (entrenamiento, reanudable)
    evaluate         ->  app/generar_metricas.py        (métricas en prueba) + results/
    utils            ->  rutas, registro y utilidades comunes

Se ejecutan desde la raíz del repositorio, como módulos:

    python -m src.evaluate
    python -m src.train --help
    python -m src.data_processing --help

Para que eso funcione con solo `pip install -r requirements.txt` (sin instalar el
paquete), este `__init__` deja `src/` al FINAL de `sys.path`: `copiloto_triaje` se
encuentra ahí si no está instalado, y si lo está, gana la copia instalada.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parent)
if _SRC not in sys.path:
    sys.path.append(_SRC)
