# -*- coding: utf-8 -*-
"""Puntuaciones crudas del modelo desplegado sobre el conjunto de PRUEBA.

Antes esta inferencia vivia por duplicado: una copia en
`caracterizar_conjunto.py` y otra en `seleccionar_casos.py`, cada una
cargando el modelo por su cuenta. Dos copias asi se desincronizan en
silencio en cuanto el modelo se reentrena, y entonces la seleccion de casos
terminaria describiendo un modelo y la caracterizacion otro. Se extrae aqui
una sola fuente de verdad; los dos ficheros la importan.

Inferir sobre las 3 811 imagenes de prueba tarda minutos; el resultado se
cachea en `crudas_prueba.csv` para que las corridas siguientes sean
instantaneas. Esa cache NO se versiona (va en `.gitignore`): se regenera
sola y describe el modelo desplegado en cada momento, no una verdad fija.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.datos.dataset import DatasetRadiografias  # noqa: E402
from copiloto_triaje.modelo.arquitectura import construir_modelo  # noqa: E402

RAIZ = pathlib.Path(r"C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo")
CACHE = REPO / "pruebas" / "crudas_prueba.csv"


def puntuaciones_de_prueba() -> pd.DataFrame:
    """El manifiesto de prueba (`test.csv`) con una columna `cruda` anadida.

    Cachea en `CACHE`: si el fichero ya existe, se lee de ahi y no se vuelve
    a inferir.
    """
    if CACHE.is_file():
        return pd.read_csv(CACHE)
    df = pd.read_csv(RAIZ / "manifiestos" / "test.csv")
    cargador = DataLoader(
        DatasetRadiografias(df, RAIZ / "png", 320, entrenamiento=False),
        batch_size=32, num_workers=4)
    modelo = construir_modelo("efficientnet_b0", congelar_backbone=False,
                              preentrenado=False)
    modelo.load_state_dict(torch.load(
        REPO / "servidor" / "pesos_modelo_cpu.pt",
        map_location="cpu", weights_only=True))
    modelo.eval()
    crudas = []
    with torch.no_grad():
        for x, _ in cargador:
            crudas.append(torch.sigmoid(modelo(x).view(-1)).numpy())
    df["cruda"] = np.concatenate(crudas)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE, index=False)
    # Se relee del propio fichero en vez de devolver `df` tal cual: la
    # columna `cruda` es float32 (numpy la produce asi), y `to_csv` la
    # escribe con la precision corta de float32 (~8 cifras), no con la
    # de float64. Devolver `df` directamente daria, en esta primera
    # llamada, valores float64 "exactos" (el bit a bit de cada float32
    # subido a float64); una segunda llamada, que lee la cache ya escrita,
    # daria los mismos numeros pero reconstruidos desde esa cadena corta:
    # DIFERENTES en el ultimo digito, aunque el modelo no haya cambiado.
    # Eso rompia `test_la_seleccion_es_determinista` exactamente en la
    # primera corrida (cache fria) y solo en ella -- se detecto ejecutando
    # la prueba en frio, no se documentaba en el brief. Releer aqui hace
    # que TODA llamada, incluida esta que crea la cache, pase por la misma
    # serializacion, y la comparacion de la prueba de determinismo sea
    # entre dos lecturas identicas del mismo fichero.
    return pd.read_csv(CACHE)
