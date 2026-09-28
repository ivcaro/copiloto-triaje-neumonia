# -*- coding: utf-8 -*-
"""Los datos de la simulación semisintética (spec de SP5 §4.1, §4.8).

Dos insumos, y ninguno es una simulación:

- `crudas_prueba.csv` CONGELADA en `docs/validacion-semisintetica/`: las
  puntuaciones crudas del modelo desplegado sobre las 3 811 placas del
  conjunto de prueba de RSNA, una por paciente, con su etiqueta real. Es una
  copia de la caché de `pruebas/puntuaciones.py`, con el sha256 de los pesos
  al lado, para que un tercero reproduzca todos los números SIN los pesos.
- `servidor/calibrador.json`: el MISMO calibrador que sirve el contenedor. Su
  `prevalencia` (0,2215) es el previo de la simulación (§4.3): se lee de ahí y
  no se teclea.
"""
from __future__ import annotations

import hashlib
import pathlib

import numpy as np
import pandas as pd

from copiloto_triaje.servicio.calibracion import Calibrador

REPO = pathlib.Path(__file__).resolve().parents[3]
CARPETA = REPO / "docs" / "validacion-semisintetica"
CRUDAS_CONGELADAS = CARPETA / "crudas_prueba.csv"
HASH_CONGELADO = CARPETA / "crudas_prueba.sha256"
CALIBRADOR = REPO / "servidor" / "calibrador.json"
COLUMNAS = ("patientId", "edad", "sexo", "vista", "etiqueta", "cruda")


def sha256_de(ruta) -> str:
    """El sha256 de los BYTES de un fichero, tal como estan: sin normalizar
    finales de linea. Es el de los ficheros que NO se versionan y que el acta
    cita (`mensajes.json`, `clave.json`): quien los guarda comprueba esos
    bytes. Para un insumo versionado, `huella_de_texto`."""
    h = hashlib.sha256()
    with pathlib.Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def huella_de_texto(ruta) -> str:
    """El sha256 de un fichero de TEXTO con los finales de linea normalizados
    a LF: con `core.autocrlf` el mismo fichero versionado tiene CRLF en un
    clon de Windows y LF en uno de Linux, y la huella tiene que ser la misma."""
    crudo = pathlib.Path(ruta).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(crudo).hexdigest()


def cargar_crudas(ruta=CRUDAS_CONGELADAS) -> pd.DataFrame:
    """Las crudas congeladas, comprobadas: las seis columnas, una placa por
    paciente y etiquetas 0/1. Un fichero a medias se rechaza, no se lee."""
    df = pd.read_csv(ruta)
    faltan = [c for c in COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError(f"a {ruta} le faltan las columnas {faltan}")
    if df["patientId"].duplicated().any():
        raise ValueError(f"{ruta} repite pacientes: no es una placa por paciente")
    if not set(df["etiqueta"].unique()) <= {0, 1}:
        raise ValueError(f"{ruta} tiene etiquetas que no son 0/1")
    return df


def calibrador_desplegado(ruta=CALIBRADOR) -> Calibrador:
    return Calibrador.desde_json(ruta)


def evidencia_imagen(crudas, calibrador: Calibrador):
    """(p_cal, q, rv) por placa, con el mismo calibrador que sirve el contenedor.

    `q = logit p_cal` es lo que el oráculo toma como verdad de la imagen
    (§4.4); `rv` es lo que `heckerling.combinar` multiplica. Con la prevalencia
    del calibrador, `prevalencia × rv` son exactamente las odds de `p_cal`.
    """
    crudas = np.asarray(crudas, dtype=float)
    p = np.array([calibrador.calibrar(c) for c in crudas])
    rv = np.array([calibrador.razon_de_verosimilitud(c) for c in crudas])
    return p, np.log(p / (1.0 - p)), rv
