# -*- coding: utf-8 -*-
"""Elige los ~60 casos del conjunto de prueba que cubren cada rama del bot.

Nivel 2 del §13.1 del spec. Telegram limita a ~1 mensaje por segundo y chat,
asi que reproducir las 3 811 conversaciones llevaria horas: se eligen unos
pocos, a proposito, uno o varios por rama.

Determinista: ordena por patientId y coge los primeros. Una seleccion aleatoria
haria que una prueba fallara hoy y pasara manana sin que nada hubiera cambiado.
"""
import pathlib
import sys

import pandas as pd

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pruebas.puntuaciones import puntuaciones_de_prueba  # noqa: E402

RAIZ = pathlib.Path(r"C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo")
CRUDO = RAIZ / "crudo" / "stage_2_train_images"
UMBRAL = 0.4258
CRUCE_RV = 0.5786          # donde la RV cruza 1,0; ver §3 del spec


def seleccionar(n_por_perfil: int = 10) -> dict:
    df = puntuaciones_de_prueba()
    meta = pd.read_csv(REPO / "docs" / "eda" / "metadatos_eda.csv")
    edades = dict(zip(meta.patientId, meta.edad_num))
    df["edad"] = df.patientId.map(edades)

    perfiles = {
        "positiva_clara":       df[df.cruda > 0.9],
        "negativa_clara":       df[df.cruda < 0.1],
        "banda_contradictoria": df[(df.cruda >= UMBRAL) & (df.cruda < CRUCE_RV)],
        # Los menores y las edades imposibles NO estan en test.csv: se filtraron
        # antes de particionar. Salen del metadato crudo.
        "menor_edad":           None,
        "edad_imposible":       None,
    }
    fuera = meta[(meta.edad_num < 18) | (meta.edad_num > 100)]
    # "cruda": None, no float("nan") -- estas placas ni siquiera estan en el
    # conjunto de prueba, asi que no es "no es un numero", es "no se ha
    # calculado". Ademas nan != nan en Python: un float("nan") aqui rompería
    # la comparacion de igualdad que usa la prueba de determinismo aunque la
    # seleccion fuera perfectamente reproducible.
    perfiles["menor_edad"] = fuera[fuera.edad_num < 18].assign(cruda=None,
                                                              etiqueta=-1)
    perfiles["edad_imposible"] = fuera[fuera.edad_num > 100].assign(
        cruda=None, etiqueta=-1)

    salida = {}
    for nombre, sub in perfiles.items():
        sub = sub.sort_values("patientId").head(n_por_perfil)
        salida[nombre] = [
            {"patientId": f.patientId,
             "ruta_dcm": str(CRUDO / f"{f.patientId}.dcm"),
             "cruda": None if pd.isna(f.cruda) else float(f.cruda),
             "etiqueta": int(f.etiqueta),
             "edad": int(f.edad_num if "edad_num" in sub.columns else f.edad)}
            for f in sub.itertuples()]
    return salida


if __name__ == "__main__":
    for nombre, casos in seleccionar().items():
        print(f"{nombre:<24} {len(casos):>3} casos")
