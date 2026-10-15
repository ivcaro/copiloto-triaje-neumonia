"""Definición del modelo: la red, sus pesos desplegados y el calibrador.

QUÉ ES. El `model.py` que pide la estructura del curso. No define ninguna red: reexporta
las que ya están definidas y probadas, y da un atajo para cargar la que se despliega.

DÓNDE ESTÁ LA IMPLEMENTACIÓN.

- `copiloto_triaje.modelo.arquitectura`  `construir_modelo`: las tres arquitecturas
  soportadas (DenseNet121, MobileNetV3-Large y EfficientNet-B0) con una sola salida
  (un logit), y el congelado y descongelado por bloques.
- `copiloto_triaje.servicio.inferencia`  `Motor`: carga los pesos en CPU y con
  `weights_only`, calibra y clasifica. Es el MISMO que usan el servidor y la app.
- `copiloto_triaje.servicio.calibracion`  `Calibrador`: la regresión isotónica ajustada
  en validación, que viaja como JSON (`servidor/calibrador.json`).

EL MODELO DESPLEGADO es EfficientNet-B0 a 320 px, corrida 6 (`efficientnet_b0_320px_lote24_4+20ep`).
Sus pesos son un `state_dict` de PyTorch (`.pt`), no están en git y su huella SHA-256
es la que lleva `app/assets/metricas.json`: `comprobar_pesos` la comprueba. Ver
`models/README.md`. El umbral, el AUC de validación y la prevalencia local son los de
`servidor/docker-compose.yml`, y una prueba (`tests/test_model.py`) vigila que no se
desincronicen.

    python -m src.model        # resumen del modelo desplegado, en JSON
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from copiloto_triaje.config import ARQUITECTURAS
from copiloto_triaje.modelo.arquitectura import (
    construir_modelo, contar_parametros_entrenables, descongelar_para_ajuste,
    descongelar_todo,
)
from copiloto_triaje.servicio.calibracion import Calibrador, ajustar_calibrador
from copiloto_triaje.servicio.inferencia import ErrorDeInferencia, Motor

from .utils import (
    CALIBRADOR_DESPLEGADO, METRICAS_PUBLICADAS, PESOS_DESPLEGADOS, sha256_de,
)

__all__ = [
    "ARQUITECTURAS", "construir_modelo", "contar_parametros_entrenables",
    "descongelar_para_ajuste", "descongelar_todo", "Calibrador", "ajustar_calibrador",
    "ErrorDeInferencia", "Motor", "ARQUITECTURA_DESPLEGADA", "TAM_IMAGEN_DESPLEGADO",
    "CORRIDA_DESPLEGADA", "UMBRAL", "AUC_VALIDACION", "PREVALENCIA_LOCAL",
    "comprobar_pesos", "cargar_motor", "cargar_modelo", "resumen", "main",
]

ARQUITECTURA_DESPLEGADA = "efficientnet_b0"
TAM_IMAGEN_DESPLEGADO = 320
CORRIDA_DESPLEGADA = "efficientnet_b0_320px_lote24_4+20ep"
# Los de `servidor/docker-compose.yml` (con la fuente de cada cifra, en sus comentarios).
UMBRAL = 0.4258
AUC_VALIDACION = 0.8827
PREVALENCIA_LOCAL = 0.1466


def comprobar_pesos(ruta_pesos=PESOS_DESPLEGADOS) -> str:
    """Comprueba que el fichero de pesos es el del modelo desplegado y devuelve su SHA-256.

    La huella esperada es la `pesos_sha256` de `app/assets/metricas.json`, la de los pesos
    con los que se midió todo. Lanza `FileNotFoundError` si no están (no viajan en git: ver
    `models/README.md`) y `ValueError` si son otros, porque unas métricas de otros pesos no
    son las de este modelo."""
    ruta = _existente(ruta_pesos, "los pesos")
    esperada = json.loads(METRICAS_PUBLICADAS.read_text(encoding="utf-8"))["pesos_sha256"]
    huella = sha256_de(ruta)
    if huella != esperada:
        raise ValueError(
            f"los pesos de {ruta.name} no son los del modelo desplegado: su SHA-256 no "
            "coincide con el de app/assets/metricas.json (models/README.md dice de dónde "
            "bajar los buenos)")
    return huella


def cargar_motor(ruta_pesos=PESOS_DESPLEGADOS, ruta_calibrador=CALIBRADOR_DESPLEGADO) -> Motor:
    """El motor de inferencia con el modelo desplegado: la llamada a `Motor.cargar` que hace
    el servidor, con el umbral, el AUC de validación y la prevalencia de arriba."""
    return Motor.cargar(_existente(ruta_pesos, "los pesos"), ruta_calibrador, UMBRAL,
                        AUC_VALIDACION, PREVALENCIA_LOCAL,
                        arquitectura=ARQUITECTURA_DESPLEGADA, tam_imagen=TAM_IMAGEN_DESPLEGADO)


def cargar_modelo(ruta_pesos=PESOS_DESPLEGADOS):
    """La red desplegada (un `torch.nn.Module` en modo evaluación) con sus pesos cargados."""
    return cargar_motor(ruta_pesos).modelo


def resumen(ruta_pesos=PESOS_DESPLEGADOS) -> dict:
    """Lo que dice el modelo desplegado de sí mismo, sin inferir nada. Si los pesos no están,
    `pesos` lo dice y el resto se calcula igual."""
    modelo = construir_modelo(ARQUITECTURA_DESPLEGADA, congelar_backbone=False, preentrenado=False)
    try:
        pesos = {"sha256": comprobar_pesos(ruta_pesos), "coincide_con_metricas_json": True}
    except FileNotFoundError:
        pesos = {"sha256": None, "coincide_con_metricas_json": None,
                 "nota": "los pesos no están: ver models/README.md"}
    return {
        "corrida": CORRIDA_DESPLEGADA,
        "arquitectura": ARQUITECTURA_DESPLEGADA,
        "tam_imagen": TAM_IMAGEN_DESPLEGADO,
        "parametros": contar_parametros_entrenables(modelo),
        "umbral": UMBRAL,
        "auc_validacion": AUC_VALIDACION,
        "prevalencia_local": PREVALENCIA_LOCAL,
        "pesos": pesos,
    }


def _existente(ruta, que: str):
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(
            f"no están {que} en {ruta}: no viajan en git, se bajan del release del "
            "repositorio (models/README.md)")
    return ruta


def main(argv=None) -> int:
    """Imprime `resumen()` como JSON."""
    if argv is None:
        argv = sys.argv[1:]
    if argv:
        print("uso: python -m src.model   (sin argumentos)", file=sys.stderr)
        return 2
    print(json.dumps(resumen(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
