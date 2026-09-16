"""Lectura de DICOM de RSNA y conversion a PNG.

Verificado el 16-sep-2026: los DICOM de RSNA vienen en uint8 con
PhotometricInterpretation MONOCHROME2, de modo que la conversion es
directa. El reescalado solo actua como red de seguridad si algun archivo
llegara con otra profundidad de bits.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pydicom
import pydicom.errors
from PIL import Image

CAMPOS = {
    "patientId": "PatientID",
    "edad": "PatientAge",
    "sexo": "PatientSex",
    "vista": "ViewPosition",
}


def _extraer_metadatos(ds) -> dict:
    """Extrae metadatos de un dataset pydicom."""
    meta = {clave: str(getattr(ds, campo, "")) for clave, campo in CAMPOS.items()}
    meta["filas"] = int(getattr(ds, "Rows", 0))
    meta["columnas"] = int(getattr(ds, "Columns", 0))
    return meta


def leer_dicom(ruta: Path) -> tuple[np.ndarray, dict]:
    """Devuelve (pixeles, metadatos) de un DICOM."""
    ds = pydicom.dcmread(str(ruta))
    meta = _extraer_metadatos(ds)
    return ds.pixel_array, meta


def _leer_metadatos_dicom(ruta: Path) -> dict:
    """Lee solo metadatos de un DICOM sin decodificar píxeles."""
    ds = pydicom.dcmread(str(ruta), stop_before_pixels=True)
    return _extraer_metadatos(ds)


def convertir_a_png(ruta_dcm: Path, ruta_png: Path) -> dict:
    """Convierte un DICOM a PNG de 8 bits y devuelve sus metadatos."""
    arr, meta = leer_dicom(ruta_dcm)
    if arr.dtype != np.uint8:
        minimo, maximo = int(arr.min()), int(arr.max())
        rango = max(maximo - minimo, 1)
        arr = ((arr.astype(np.float32) - minimo) / rango * 255).astype(np.uint8)
    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr).save(ruta_png)
    meta["archivo_png"] = ruta_png.name
    return meta


def convertir_lote(rutas_dcm, dir_png: Path) -> tuple[list[dict], list[dict]]:
    """Convierte una lista de DICOM. Un archivo ilegible se omite y se
    registra, pero nunca aborta el proceso: una perdida silenciosa de datos
    seria peor que un fallo ruidoso.

    Es idempotente: si el PNG ya existe, no lo reescribe.
    """
    dir_png = Path(dir_png)
    dir_png.mkdir(parents=True, exist_ok=True)
    convertidos: list[dict] = []
    omitidos: list[dict] = []
    for ruta in rutas_dcm:
        ruta = Path(ruta)
        destino = dir_png / (ruta.stem + ".png")
        try:
            if destino.exists():
                meta = _leer_metadatos_dicom(ruta)
                meta["archivo_png"] = destino.name
            else:
                meta = convertir_a_png(ruta, destino)
            convertidos.append(meta)
        except (pydicom.errors.InvalidDicomError, OSError, ValueError) as exc:
            omitidos.append({"archivo": ruta.name, "motivo": f"{type(exc).__name__}: {exc}"})
    return convertidos, omitidos
