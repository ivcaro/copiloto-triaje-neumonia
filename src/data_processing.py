"""Procesamiento de datos: de los DICOM de RSNA a los manifiestos de entrenamiento.

QUÉ ES. El `data_processing.py` que pide la estructura del curso: el punto de
entrada a todo lo que prepara los datos. No contiene lógica propia.

DÓNDE ESTÁ LA IMPLEMENTACIÓN. En `src/copiloto_triaje/datos/`:

- `dicom.py`        lectura de DICOM, conversión a PNG y la regla de lo que el motor
                    puede evaluar (`comprobar_que_se_puede_evaluar`).
- `preparacion.py`  cruce de metadatos con etiquetas, filtro de edad (adultos) y
                    escritura de los manifiestos.
- `particion.py`    partición POR PACIENTE y la comprobación de que no hay fuga.
- `dataset.py`      el `Dataset` de PyTorch, que lee siempre desde un manifiesto, y las
                    transformaciones (normalización de ImageNet).

Aquí solo se reexportan esas piezas con los nombres que usan los notebooks y las
pruebas. La orden completa (zip -> PNG -> manifiestos), con su comprobación de fuga,
es `scripts/preparar_datos.py`, y este módulo la llama:

    python -m src.data_processing --crudo <carpeta descomprimida> --raiz <RSNA_RAIZ>
    python -m src.data_processing --zip <rsna-pneumonia-detection-challenge.zip> --raiz <RSNA_RAIZ>

Los datos NO están en el repositorio (`data/README.md`): `--raiz` es la carpeta donde se
dejan los PNG y los manifiestos, la misma que después se pone en `RSNA_RAIZ`.
"""
from __future__ import annotations

import sys

from copiloto_triaje.datos.dataset import DatasetRadiografias, construir_transformaciones
from copiloto_triaje.datos.dicom import (
    PlacaNoEvaluable, comprobar_que_se_puede_evaluar, convertir_a_png, convertir_lote,
    leer_dicom, leer_dicom_desde_bytes,
)
from copiloto_triaje.datos.particion import (
    FugaDeDatos, particionar_por_paciente, verificar_sin_fuga,
)
from copiloto_triaje.datos.preparacion import (
    cargar_etiquetas, construir_registros, edad_en_anios, escribir_manifiestos,
    filtrar_por_edad,
)

from .utils import ejecutar_guion

__all__ = [
    "DatasetRadiografias", "construir_transformaciones",
    "PlacaNoEvaluable", "comprobar_que_se_puede_evaluar", "convertir_a_png",
    "convertir_lote", "leer_dicom", "leer_dicom_desde_bytes",
    "FugaDeDatos", "particionar_por_paciente", "verificar_sin_fuga",
    "cargar_etiquetas", "construir_registros", "edad_en_anios", "escribir_manifiestos",
    "filtrar_por_edad", "main",
]

GUION = "scripts/preparar_datos.py"


def main(argv=None) -> int:
    """Prepara los datos de RSNA: llama a `scripts/preparar_datos.py` con estos
    argumentos (`--zip` o `--crudo`, `--raiz`, `--limite`, `--semilla`). `--help` los lista."""
    return ejecutar_guion(GUION, argv, prog="python -m src.data_processing")


if __name__ == "__main__":
    sys.exit(main())
