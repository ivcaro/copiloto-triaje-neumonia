"""Cruce de metadatos con etiquetas y escritura de manifiestos."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def cargar_etiquetas(ruta_csv: Path) -> dict[str, int]:
    """Lee stage_2_train_labels.csv y colapsa las filas por paciente.

    Hay mas filas que pacientes porque un positivo puede tener varias cajas;
    el paciente es positivo si alguna de sus filas lo es.
    """
    df = pd.read_csv(ruta_csv)
    agrupado = df.groupby("patientId")["Target"].max()
    return {str(k): int(v) for k, v in agrupado.items()}


def construir_registros(metadatos: list[dict], etiquetas: dict[str, int]) -> list[dict]:
    """Une metadatos de imagen con su etiqueta. Descarta los sin etiqueta."""
    registros = []
    for meta in metadatos:
        pid = meta.get("patientId")
        if pid in etiquetas:
            registro = dict(meta)
            registro["etiqueta"] = int(etiquetas[pid])
            registros.append(registro)
    return registros


def escribir_manifiestos(particiones: dict[str, list[dict]], dir_manifiestos,
                         semilla: int) -> dict[str, Path]:
    """Escribe train.csv, val.csv y test.csv con la semilla registrada."""
    dir_manifiestos = Path(dir_manifiestos)
    dir_manifiestos.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for nombre, registros in particiones.items():
        df = pd.DataFrame(registros)
        df["semilla"] = semilla
        ruta = dir_manifiestos / f"{nombre}.csv"
        df.to_csv(ruta, index=False)
        rutas[nombre] = ruta
    return rutas


def verificar_zip_existe(ruta_zip: Path) -> None:
    """Falla de inmediato y de forma explicita si el zip de RSNA no esta
    donde se indico, en vez de fallar a mitad de la descompresion.

    `Config` no puede hacer esta validacion (se construye a proposito con
    rutas temporales inexistentes en otras pruebas), asi que le corresponde
    al script de preparacion, tal como exige el spec para configuracion
    invalida: fallar al inicio, no a mitad del proceso. El mensaje siempre
    cita la ruta buscada para que el error sea accionable.
    """
    ruta_zip = Path(ruta_zip)
    if not ruta_zip.exists():
        raise FileNotFoundError(
            f"No se encontro el zip de RSNA en la ruta indicada con --zip: "
            f"{ruta_zip}\nVerifica la ruta (relativa al directorio actual o "
            f"absoluta) antes de volver a ejecutar el script."
        )
    if not ruta_zip.is_file():
        raise FileNotFoundError(
            f"La ruta indicada con --zip existe pero no es un archivo: "
            f"{ruta_zip}\nDebe apuntar al archivo .zip de RSNA, no a un "
            f"directorio."
        )
