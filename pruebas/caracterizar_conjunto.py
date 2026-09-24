# -*- coding: utf-8 -*-
"""Cuantas radiografias reales caen en la banda donde el cribado y la evidencia
bayesiana se contradicen.

La etiqueta sale de `cruda >= 0,4258`; la razon de verosimilitud sale de la
isotonica y no cruza 1,0 hasta `cruda = 0,5786`. En medio, el bot dice
"opacidad probable" sobre una imagen que RESTA probabilidades a favor.

El aviso del §8 del spec de SP3 existe para ese caso. Esto responde cuantas
veces va a dispararse de verdad, y si el aviso es una rareza o el pan de cada
dia. Se mide sobre PRUEBA, que es el conjunto que nunca se toco para elegir
nada.
"""
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.servicio.calibracion import Calibrador  # noqa: E402
from pruebas.puntuaciones import puntuaciones_de_prueba  # noqa: E402

UMBRAL = 0.4258


def main() -> int:
    # La inferencia sobre las 3 811 imagenes de prueba vive en
    # pruebas/puntuaciones.py, compartida con seleccionar_casos.py: una sola
    # fuente de verdad para "que puntua el modelo desplegado sobre prueba".
    df = puntuaciones_de_prueba()
    crudas = df["cruda"].to_numpy()
    etiquetas = df["etiqueta"].to_numpy()

    cal = Calibrador.desde_json(REPO / "servidor" / "calibrador.json")
    rv = np.array([cal.razon_de_verosimilitud(float(p)) for p in crudas])

    positiva = crudas >= UMBRAL
    resta = rv < 1.0
    banda = positiva & resta

    print(f"conjunto de PRUEBA: {len(df)} radiografias\n")
    print(f"{'etiquetadas opacidad_probable':<42} {positiva.sum():>6} "
          f"({positiva.mean()*100:>5.1f}%)")
    print(f"{'...de esas, con RV < 1 (CONTRADICEN)':<42} {banda.sum():>6} "
          f"({banda.sum()/max(positiva.sum(),1)*100:>5.1f}% de las positivas)")
    print(f"{'sobre el total del conjunto':<42} {'':>6} "
          f"({banda.mean()*100:>5.1f}%)\n")

    print("de las que caen en la banda contradictoria, cual era la verdad:")
    for v, nombre in ((1, "SI tenian opacidad"), (0, "NO tenian opacidad")):
        n = int(((etiquetas == v) & banda).sum())
        print(f"  {nombre:<22} {n:>5}  ({n/max(banda.sum(),1)*100:>5.1f}%)")

    print("\nrango de RV dentro de la banda: "
          f"{rv[banda].min():.3f} a {rv[banda].max():.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
