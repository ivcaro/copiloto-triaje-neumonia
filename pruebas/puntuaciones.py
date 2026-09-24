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
instantaneas. Esa cache NO se versiona (va en `.gitignore`): describe el
modelo desplegado en el momento en que se genero, y se invalida sola -junto
a ella se guarda el sha256 de `servidor/pesos_modelo_cpu.pt`, y si no
coincide con el de ahora mismo se vuelve a inferir- para que un
reentrenamiento no deje sirviendo, en silencio, las puntuaciones del modelo
viejo.
"""
from __future__ import annotations

import hashlib
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
PESOS = REPO / "servidor" / "pesos_modelo_cpu.pt"
CACHE = REPO / "pruebas" / "crudas_prueba.csv"
# El sha256 de PESOS en el momento en que se genero CACHE. Vive al lado y no
# dentro del CSV porque es metadato de la cache, no una columna de datos.
CACHE_HASH = REPO / "pruebas" / "crudas_prueba.sha256"


def _sha256(ruta: pathlib.Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _cache_valida() -> bool:
    if not (CACHE.is_file() and CACHE_HASH.is_file()):
        return False
    return CACHE_HASH.read_text(encoding="utf-8").strip() == _sha256(PESOS)


def puntuaciones_de_prueba() -> pd.DataFrame:
    """El manifiesto de prueba (`test.csv`) con una columna `cruda` anadida.

    Cachea en `CACHE`: si el fichero ya existe Y el sha256 de `PESOS`
    guardado junto a el coincide con el de ahora, se lee de ahi y no se
    vuelve a inferir. Si el modelo se reentreno desde la ultima corrida, el
    hash no coincide y se regenera -- sin esto, la cache seguiria sirviendo
    las puntuaciones del modelo viejo para siempre, y `caracterizar_conjunto.py`
    (§3 del spec, §13.1 exige volver a correrlo al reentrenar) no notaria
    nada distinto.
    """
    if _cache_valida():
        return pd.read_csv(CACHE)
    hash_actual = _sha256(PESOS)
    df = pd.read_csv(RAIZ / "manifiestos" / "test.csv")
    cargador = DataLoader(
        DatasetRadiografias(df, RAIZ / "png", 320, entrenamiento=False),
        batch_size=32, num_workers=4)
    modelo = construir_modelo("efficientnet_b0", congelar_backbone=False,
                              preentrenado=False)
    modelo.load_state_dict(torch.load(
        PESOS, map_location="cpu", weights_only=True))
    modelo.eval()
    crudas = []
    with torch.no_grad():
        for x, _ in cargador:
            crudas.append(torch.sigmoid(modelo(x).view(-1)).numpy())
    df["cruda"] = np.concatenate(crudas)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE, index=False)
    CACHE_HASH.write_text(hash_actual, encoding="utf-8")
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
