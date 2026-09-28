# -*- coding: utf-8 -*-
"""La simulación semisintética, celda a celda (spec de SP5 §4.3-§4.6).

Une las cuatro piezas: las placas congeladas (`datos`), el generador de la
clínica (`generador`), el oráculo de la celda (`oraculo`) y el SISTEMA, que
es `heckerling.combinacion` y `heckerling.combinar`: el mismo código que
sirve el contenedor, llamado caso a caso, nunca una reimplementación.

Una CELDA es un par (ρ1, ρ0). Su estimación puntual usa la clínica sorteada
con `SEMILLA_PUNTUAL` sobre las 3 811 placas. Su bootstrap remuestrea placas
con reemplazo y vuelve a sortear la clínica en cada réplica, con `z_y`, los
umbrales y el calibrador FIJOS: el generador es el mismo en todas.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from copiloto_triaje.servicio.heckerling import (
    RV_POR_PUNTUACION, combinacion, combinar, mas_informativa,
)
from . import datos, generador, metricas, oraculo
from .categoria import categoria_del_sistema

SEMILLA_PUNTUAL = 1          # la misma clinica que comprueba 0A
MODELOS = ("imagen", "clinica", "independencia", "conservador")
COMBINADOS = ("independencia", "conservador")


@dataclass(frozen=True, eq=False)
class Conjunto:
    """Las placas de prueba y su evidencia de imagen, en el orden del CSV."""
    ids: np.ndarray
    y: np.ndarray
    p_cal: np.ndarray
    q: np.ndarray
    rv: np.ndarray
    orden: np.ndarray        # el rango de patientId: rompe los empates de la ECE
    prevalencia: float


def cargar_conjunto(ruta=datos.CRUDAS_CONGELADAS, calibrador=None) -> Conjunto:
    df = datos.cargar_crudas(ruta)
    cal = calibrador if calibrador is not None else datos.calibrador_desplegado()
    p, q, rv = datos.evidencia_imagen(df["cruda"].values, cal)
    ids = df["patientId"].values.astype(str)
    return Conjunto(ids, df["etiqueta"].values.astype(int), p, q, rv,
                    np.argsort(np.argsort(ids, kind="stable"), kind="stable"),
                    float(cal.prevalencia))


def nombre_de_celda(rho1: float, rho0: float) -> str:
    if rho1 == 0.0 and rho0 == 0.0:
        return "0A"
    return f"({rho1:g}; {rho0:g})".replace(".", ",")


def salidas_del_sistema(prevalencia: float, clinica: pd.DataFrame, rv) -> dict:
    """Lo que el codigo del servidor da para cada caso. Las probabilidades de
    los modelos puntuales son las del BLOQUE (redondeadas a 4 decimales, lo
    que el sistema entrega); los extremos de la horquilla van SIN redondear,
    recalculados con `combinar` y contrastados con el bloque.

    Con el asma desconocida el sistema da DOS puntuaciones: no hay UN modelo
    puntual ni UNA horquilla, y `independencia`, `conservador`, `clinica`,
    `l_independencia` y `l_dependencia` quedan en nan. Esos casos se miden con
    `l_minima`, `l_maxima` y `l_medio`."""
    n = len(clinica)
    rv = np.asarray(rv, dtype=float)
    if rv.shape != (n,):
        raise ValueError(f"hay {n} casos y {rv.size} RV de imagen: tienen que casar")
    s = {"conocida": np.zeros(n, bool), "concordantes": np.zeros(n, bool),
         "puntuacion": np.zeros(n, int), "primaria": np.empty(n, dtype=object)}
    for nombre in ("independencia", "conservador", "clinica", "l_independencia",
                   "l_dependencia", "l_minima", "l_maxima", "l_medio"):
        s[nombre] = np.full(n, np.nan)
    for i, (fila, r) in enumerate(zip(clinica.to_dict("records"), rv)):
        r = float(r)
        b = combinacion(prevalencia, generador.hallazgos(fila), r)
        ind = [combinar(prevalencia, rc, r) for rc in b["rv_clinica"]]
        dep = ([combinar(prevalencia, mas_informativa(rc, r), 1.0) for rc in b["rv_clinica"]]
               if b["concordantes"] else [])
        if ([round(x, 4) for x in ind] != b["independencia"]
                or ([round(x, 4) for x in dep] or None) != b["dependencia"]):
            raise AssertionError(f"el bloque del caso {i} no es el redondeo de combinar(): {b}")
        s["conocida"][i] = fila["asma"] != "no_se"
        s["concordantes"][i] = b["concordantes"]
        s["puntuacion"][i] = b["puntuacion"][0]
        s["primaria"][i] = categoria_del_sistema(b)["primaria"]
        l_ind = [math.log(x / (1.0 - x)) for x in ind]
        todas = [math.log(x / (1.0 - x)) for x in ind + dep]
        s["l_minima"][i], s["l_maxima"][i] = min(todas), max(todas)
        s["l_medio"][i] = sum(l_ind) / len(l_ind)
        if not s["conocida"][i]:
            continue
        s["independencia"][i] = b["independencia"][0]
        s["conservador"][i] = b["dependencia"][0] if b["concordantes"] else b["independencia"][0]
        s["clinica"][i] = combinar(prevalencia, RV_POR_PUNTUACION[b["puntuacion"][0]], 1.0)
        s["l_independencia"][i] = l_ind[0]
        if dep:
            s["l_dependencia"][i] = math.log(dep[0] / (1.0 - dep[0]))
    return s


def oraculo_de_los_casos(modelo: oraculo.Modelo, q, clinica: pd.DataFrame) -> np.ndarray:
    """El logit del oraculo con la MISMA informacion que el sistema: (q, k)
    con el asma conocida y (q, k4) con el asma oculta."""
    q = np.asarray(q, dtype=float)
    conocida = (clinica["asma"] != "no_se").values
    salida = np.empty(q.size)
    salida[conocida] = oraculo.logit_oraculo(modelo, q[conocida],
                                             clinica["k"].values[conocida])
    salida[~conocida] = oraculo.logit_oraculo_no_se(modelo, q[~conocida],
                                                    clinica["k4"].values[~conocida])
    return salida


def medir(conjunto: Conjunto, salidas: dict, l_oraculo, filas=None) -> dict:
    """Todas las metricas del §4.6 sobre las filas dadas (con repeticiones en
    el bootstrap; todas si `filas` es None)."""
    f = np.arange(conjunto.y.size) if filas is None else np.asarray(filas, dtype=int)
    y, orden, rv = conjunto.y[f], conjunto.orden[f], conjunto.rv[f]
    l_or = np.asarray(l_oraculo, dtype=float)[f]
    conocida, conc = salidas["conocida"][f], salidas["concordantes"][f]
    p = {"imagen": conjunto.p_cal[f], "clinica": salidas["clinica"][f],
         "independencia": salidas["independencia"][f],
         "conservador": salidas["conservador"][f]}
    modelos = {m: metricas.resumen_de_modelo(y[conocida], p[m][conocida], orden[conocida])
               for m in MODELOS}
    pareadas = {c: {m: modelos[c][m] - modelos["imagen"][m]
                    for m in ("auc", "brier", "pendiente")} for c in COMBINADOS}
    l_ind, l_dep = salidas["l_independencia"][f], salidas["l_dependencia"][f]
    h = conocida & conc
    lados = {"todos": h, "a_favor": h & (rv >= 1.0), "en_contra": h & (rv < 1.0)}
    d = conocida & ~conc
    ns = ~conocida
    no_se = metricas.contencion_en_rango(l_or[ns], salidas["l_minima"][f][ns],
                                         salidas["l_maxima"][f][ns])
    no_se["punto_medio"] = metricas.error_puntual(salidas["l_medio"][f][ns], l_or[ns])
    return {
        "recuentos": {"casos": int(f.size), "asma_conocida": int(conocida.sum()),
                      "concordantes": int(h.sum()),
                      "concordantes_a_favor": int(lados["a_favor"].sum()),
                      "concordantes_en_contra": int(lados["en_contra"].sum()),
                      "discordantes": int(d.sum()), "no_se": int(ns.sum())},
        "modelos": modelos,
        "pareadas": pareadas,
        "horquilla": {lado: metricas.horquilla(l_or[m], l_dep[m], l_ind[m])
                      for lado, m in lados.items()},
        "discordantes": metricas.error_puntual(l_ind[d], l_or[d]),
        "no_se": no_se,
    }


def aplanar(d: dict, prefijo: str = "") -> dict:
    """{«a.b.c»: valor} con las hojas `float` de un diccionario anidado: son
    las cifras que llevan intervalo. Los recuentos (`int`) y los `None` no."""
    plano = {}
    for clave, valor in d.items():
        ruta = f"{prefijo}.{clave}" if prefijo else str(clave)
        if isinstance(valor, dict):
            plano.update(aplanar(valor, ruta))
        elif isinstance(valor, float):
            plano[ruta] = valor
    return plano
