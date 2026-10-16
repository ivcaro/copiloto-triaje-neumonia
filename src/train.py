"""Entrenamiento: el punto de entrada del curso al bucle de entrenamiento del proyecto.

QUÉ ES. El `train.py` que pide la estructura del curso. No entrena por su cuenta: llama
al guion que ya entrena y reexporta las piezas de su bucle.

DÓNDE ESTÁ LA IMPLEMENTACIÓN.

- `copiloto_triaje.modelo.entrenamiento`  el bucle en dos fases (cabeza congelada y ajuste
  fino), con parada temprana por RECALL medido en el umbral que elige cada época,
  checkpoints y reanudación; `exportar_pesos_cpu` deja el `state_dict` limpio en CPU.
- `copiloto_triaje.modelo.evaluacion`     las métricas binarias y la regla que elige el umbral
  en validación.
- `scripts/entrenar_local.py`             la orden completa: carga los manifiestos, entrena UNA
  configuración, elige el umbral en validación, evalúa en prueba una sola vez y escribe el
  reporte (JSON, Markdown y curva ROC). Es reanudable porque una corrida son horas.

USO, desde la raíz del repositorio y con los datos ya preparados (`data/README.md`):

    python -m src.train --help
    python -m src.train --raiz <RSNA_RAIZ> --arquitectura efficientnet_b0 --tam-imagen 320 --lote 24

Los valores por defecto (320 px, 4 + 20 épocas, lote 24, semilla 42...) son los de
`copiloto_triaje.config.Config`; la corrida desplegada es la 6, `efficientnet_b0_320px_lote24_4+20ep`.
Una corrida son horas, también en CPU, y por eso el guion es reanudable; con GPU (Colab o Kaggle,
`notebooks/03_modelado.ipynb`) son menos.
"""
from __future__ import annotations

import sys

from copiloto_triaje.config import ARQUITECTURAS, Config
from copiloto_triaje.modelo.entrenamiento import (
    NOMBRE_PESOS_CPU, entrenar, evaluar_epoca, exportar_pesos_cpu, fijar_semillas,
)
from copiloto_triaje.modelo.evaluacion import elegir_umbral, metricas_en_umbral

from .utils import ejecutar_guion

__all__ = [
    "ARQUITECTURAS", "Config", "NOMBRE_PESOS_CPU", "entrenar", "evaluar_epoca",
    "exportar_pesos_cpu", "fijar_semillas", "elegir_umbral", "metricas_en_umbral", "main",
]

GUION = "scripts/entrenar_local.py"


def main(argv=None) -> int:
    """Entrena una configuración: llama a `scripts/entrenar_local.py` con estos argumentos
    (`--raiz`, `--arquitectura`, `--tam-imagen`, `--lote`, `--epocas-cabeza`, `--epocas-ajuste`,
    `--salida`, `--reanudar`, `--trabajadores`). `--help` los lista."""
    return ejecutar_guion(GUION, argv, prog="python -m src.train")


if __name__ == "__main__":
    sys.exit(main())
