"""Lectura de DICOM de RSNA y conversion a PNG.

Verificado el 16-sep-2026: los DICOM de RSNA vienen en uint8 con
PhotometricInterpretation MONOCHROME2, de modo que la conversion es
directa. El reescalado solo actua como red de seguridad si algun archivo
llegara con otra profundidad de bits.
"""
from __future__ import annotations

import os
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


def _png_legible(ruta_png: Path) -> bool:
    """Un PNG existe y esta COMPLETO.

    Descodifica de verdad (`load()`) en vez de `verify()`. verify() recorre
    los chunks y detecta la mayoria de los truncados, pero la unica prueba
    que vale es la operacion que hace el entrenamiento al leer la imagen: si
    esta funcion dice que si y el DataLoader revienta con "image file is
    truncated", la comprobacion no sirve de nada. Cuesta mas, y es el precio
    correcto: el fallo alternativo aparece horas despues, a mitad de un
    entrenamiento, y obliga a repetirlo.
    """
    try:
        with Image.open(ruta_png) as imagen:
            imagen.load()
        return True
    except Exception:
        # Cualquier fallo al abrirlo o descodificarlo significa lo mismo para
        # quien llama: hay que reconvertirlo.
        return False


def convertir_a_png(ruta_dcm: Path, ruta_png: Path) -> dict:
    """Convierte un DICOM a PNG de 8 bits y devuelve sus metadatos."""
    arr, meta = leer_dicom(ruta_dcm)
    if arr.dtype != np.uint8:
        minimo, maximo = int(arr.min()), int(arr.max())
        rango = max(maximo - minimo, 1)
        arr = ((arr.astype(np.float32) - minimo) / rango * 255).astype(np.uint8)
    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    # Escritura ATOMICA: al temporal primero y luego os.replace, que en POSIX
    # es atomico. Guardar directo sobre el destino final significa que un
    # corte a mitad -disco lleno, runtime reciclado- deja un PNG truncado CON
    # EL NOMBRE DEFINITIVO, y a partir de ahi nadie lo distingue de uno bueno:
    # el entrenamiento reventaba horas despues con "image file is truncated".
    # Con el temporal, una escritura interrumpida deja un .tmp que no se
    # confunde con nada y el destino final o esta completo o no esta.
    temporal = ruta_png.with_name(ruta_png.name + ".tmp")
    try:
        Image.fromarray(arr).save(temporal, format="PNG")
        os.replace(temporal, ruta_png)
    finally:
        temporal.unlink(missing_ok=True)
    meta["archivo_png"] = ruta_png.name
    return meta


def convertir_lote(rutas_dcm, dir_png: Path) -> tuple[list[dict], list[dict]]:
    """Convierte una lista de DICOM. Un archivo ilegible se omite y se
    registra, pero nunca aborta el proceso: una perdida silenciosa de datos
    seria peor que un fallo ruidoso.

    Es idempotente: si el PNG ya existe Y SE PUEDE LEER, no lo reescribe. La
    comprobacion de lectura no sobra: con `destino.exists()` a secas, un PNG
    truncado por una escritura interrumpida se daba por convertido en cada
    reintento y no habia forma de repararlo salvo borrandolo a mano.
    """
    dir_png = Path(dir_png)
    dir_png.mkdir(parents=True, exist_ok=True)
    convertidos: list[dict] = []
    omitidos: list[dict] = []
    for ruta in rutas_dcm:
        ruta = Path(ruta)
        destino = dir_png / (ruta.stem + ".png")
        try:
            if destino.exists() and _png_legible(destino):
                meta = _leer_metadatos_dicom(ruta)
                meta["archivo_png"] = destino.name
            else:
                meta = convertir_a_png(ruta, destino)
            convertidos.append(meta)
        # TypeError esta en la lista porque un tag PRESENTE pero VACIO existe
        # en DICOM y devuelve None: `int(getattr(ds, "Rows", 0))` con Rows
        # vacio no lanza ValueError sino TypeError. Un solo archivo asi
        # abortaba a mitad una conversion de 21 minutos sobre los 26 684
        # DICOM de RSNA, que es exactamente lo que este try existe para
        # impedir. No se anade el TypeError a costa de la regla de la Tarea 4:
        # los errores de PROGRAMACION (NameError, AttributeError...) siguen
        # propagandose ruidosamente en vez de camuflarse como "omitidos".
        except (pydicom.errors.InvalidDicomError, OSError, ValueError,
                TypeError) as exc:
            omitidos.append({"archivo": ruta.name, "motivo": f"{type(exc).__name__}: {exc}"})
    return convertidos, omitidos
