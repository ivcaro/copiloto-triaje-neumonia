# -*- coding: utf-8 -*-
"""El generador de la simulación semisintética (spec de SP5 §4.2).

Por placa: (1) la puntuacion `k` sale del modelo de umbral latente de
`oraculo.py`, con la distribucion exacta de los recuentos de Heckerling;
(2) los `k` puntos se reparten en los cinco predictores con una regla
declarada que solo afecta a la redaccion de la viñeta y al oraculo de
`no_se`; (3) temperatura y pulso salen como numeros, con una decima y
enteros, y con probabilidad 0,2 EXACTAMENTE en el corte (ausente) o en el
valor inmediato superior (presente): asi un `>` cambiado por `>=`, o un
corte movido, cambia la puntuacion de una fraccion conocida de casos;
(4) el asma se oculta (`no_se`) en el 10 % de los casos, al azar.

Nada de esto inventa la exactitud de la regla: la RV de cada puntuacion es
la publicada. Lo unico que el generador decide es a que placa le toca que
puntuacion, y con que numeros se escribe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .oraculo import PROBABILIDAD_ASMA_PRESENTE, Modelo

FRACCION_NO_SE = 0.10          # asma oculta al azar (MCAR), §4.2 paso 4
FRACCION_EN_EL_CORTE = 0.20    # exactamente el corte / el inmediato superior
# Rejillas [a, b): temperatura en decimas de grado, pulso en lpm.
TEMPERATURA_PRESENTE = (379, 396)   # 37,9 … 39,5 °C
TEMPERATURA_AUSENTE = (360, 379)    # 36,0 … 37,8 °C
PULSO_PRESENTE = (101, 131)         # 101 … 130 lpm
PULSO_AUSENTE = (60, 101)           # 60 … 100 lpm
SIGNOS = ("temperatura_c", "frecuencia_cardiaca", "crepitantes",
          "murmullo_disminuido")
COLUMNAS = ("k", "k4", "asma_real", "asma") + SIGNOS


def sortear_puntuacion(modelo: Modelo, rng: np.random.Generator) -> np.ndarray:
    """k_i = #{j : u_i > τ_{y,j}},  u_i = ρ_y z_y(q_i) + √(1 − ρ_y²) ε_i."""
    y = modelo.etiquetas
    rho = np.where(y == 1, modelo.rho1, modelo.rho0)
    u = rho * modelo.z_propia() + np.sqrt(1.0 - rho ** 2) * rng.standard_normal(y.size)
    tau = np.where((y == 1)[:, None], modelo.tau1[None, :], modelo.tau0[None, :])
    return (u[:, None] > tau).sum(axis=1)


def _valor(presente: bool, rejilla_presente, rejilla_ausente,
           rng: np.random.Generator) -> int:
    """Un valor de la rejilla: con probabilidad FRACCION_EN_EL_CORTE el borde
    (el inmediato superior al corte si esta presente; el corte exacto si esta
    ausente) y, si no, uniforme sobre el RESTO de la rejilla, para que la
    fraccion total en el borde sea exactamente la declarada (D7)."""
    a, b = rejilla_presente if presente else rejilla_ausente
    if rng.random() < FRACCION_EN_EL_CORTE:
        return a if presente else b - 1
    return int(rng.integers(a + 1, b)) if presente else int(rng.integers(a, b - 1))


def repartir(k: int, rng: np.random.Generator) -> dict:
    """Los k puntos en los cinco predictores, con temperatura y pulso como numeros."""
    if not 0 <= k <= 5:
        raise ValueError(f"la puntuación va de 0 a 5, y es {k!r}")
    # Con k = 0 nunca (P = 1,0 de asma presente), con k = 5 siempre, y entre
    # medias con probabilidad 0,9: la MISMA tabla que usa el oraculo de no_se.
    sin_asma = bool(rng.random() >= PROBABILIDAD_ASMA_PRESENTE[k])
    puntos = k - int(sin_asma)
    presentes = np.zeros(4, dtype=bool)
    presentes[rng.choice(4, size=puntos, replace=False)] = True
    return {
        "k": int(k),
        "k4": int(puntos),
        "asma_real": "no" if sin_asma else "si",
        "temperatura_c": _valor(bool(presentes[0]), TEMPERATURA_PRESENTE,
                                TEMPERATURA_AUSENTE, rng) / 10.0,
        "frecuencia_cardiaca": _valor(bool(presentes[1]), PULSO_PRESENTE,
                                      PULSO_AUSENTE, rng),
        "crepitantes": bool(presentes[2]),
        "murmullo_disminuido": bool(presentes[3]),
    }


def ocultar_asma(asma_real: str, rng: np.random.Generator) -> str:
    return "no_se" if rng.random() < FRACCION_NO_SE else asma_real


def sortear_caso(modelo: Modelo, indice: int, rng: np.random.Generator,
                 asma: str | None = None) -> dict:
    """La clinica de UNA placa, para la sesion (spec §5.1). `asma` fuerza el
    estado DECLARADO (`no_se` en el estrato del asma); el real sigue sorteado."""
    y = int(modelo.etiquetas[indice])
    rho, tau = (modelo.rho1, modelo.tau1) if y == 1 else (modelo.rho0, modelo.tau0)
    u = rho * float(modelo.z_propia()[indice]) + np.sqrt(1.0 - rho ** 2) * rng.standard_normal()
    fila = repartir(int((u > tau).sum()), rng)
    fila["asma"] = asma if asma is not None else fila["asma_real"]
    return fila


def generar(modelo: Modelo, semilla: int) -> pd.DataFrame:
    """Una fila por placa, en el orden del modelo, reproducible por semilla."""
    rng = np.random.default_rng(semilla)
    filas = [repartir(int(k), rng) for k in sortear_puntuacion(modelo, rng)]
    for fila in filas:
        fila["asma"] = ocultar_asma(fila["asma_real"], rng)
    return pd.DataFrame(filas, columns=list(COLUMNAS))


def hallazgos(fila) -> dict:
    """Los cinco hallazgos tal como los recibe `heckerling.combinacion`, con
    tipos de Python: `validar_hallazgos` rechaza un `numpy.bool_`."""
    return {"temperatura_c": float(fila["temperatura_c"]),
            "frecuencia_cardiaca": int(fila["frecuencia_cardiaca"]),
            "crepitantes": bool(fila["crepitantes"]),
            "murmullo_disminuido": bool(fila["murmullo_disminuido"]),
            "asma": str(fila["asma"])}
