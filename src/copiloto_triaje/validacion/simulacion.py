# -*- coding: utf-8 -*-
"""La simulación semisintética, celda a celda (spec de SP5 §4.3-§4.6).

Une las cuatro piezas: las placas congeladas (`datos`), el generador de la
clínica (`generador`), el oráculo de la celda (`oraculo`) y el SISTEMA, que
es `heckerling.combinacion` y `heckerling.combinar`: el mismo código que
sirve el contenedor, llamado caso a caso, nunca una reimplementación.

Una CELDA es un par (ρ1, ρ0). Su estimación puntual usa la clínica sorteada
con `SEMILLA_PUNTUAL` sobre las 3 811 placas. Su bootstrap remuestrea con
reemplazo esos mismos casos, cada placa con la clínica que se le sorteó: la
clínica NO se vuelve a sortear (ver `replica`).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from copiloto_triaje.servicio.heckerling import (
    PREVALENCIA_COHORTE, RV_POR_PUNTUACION, combinacion, combinar, mas_informativa,
)
from . import datos, generador, metricas, oraculo
from .categoria import BANDAS, banda, categoria_del_sistema, porcentaje_entero

SEMILLA_PUNTUAL = 1          # la misma clinica que comprueba 0A
SEMILLA_INDICES = 20_000     # replica b: default_rng(SEMILLA_INDICES + b)
B_REPLICAS = 1000
HIPOTESIS_CONTENCION = 0.90  # «el oraculo queda dentro en ≥ 90 % de los concordantes»
MODELOS = ("imagen", "clinica", "independencia", "conservador")
COMBINADOS = ("independencia", "conservador")
# Las bandas de la validacion externa de Heckerling (SP4 §4.1), para 0C.
RV_VALIDACION = {0: 0.19, 1: 0.19, 2: 1.04, 3: 1.04, 4: 8.33, 5: 8.33}
POCO_INFORMATIVA = 0.5       # |ln RV_recuentos(k)| por debajo: k = 2 y k = 3
EXTREMAS = (0, 1, 4, 5)


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


def replica(conjunto: Conjunto, salidas: dict, l_oraculo, b: int) -> dict:
    """Una replica del bootstrap: los casos de la estimacion puntual -cada
    placa CON la clinica que se le sorteo, lo que el sistema dio y su
    oraculo-, remuestreados con reemplazo.

    La clinica NO se vuelve a sortear. El remuestreo de las parejas ya
    lleva el ruido del sorteo: sorteando otra vez en cada replica ese ruido
    se cuenta dos veces (medido en esta simulacion: la varianza sale × 1,57
    en mediana, y un «IC 95 %» cubre mas del 99 %). Remuestrear primero y
    sortear despues quita la doble cuenta, pero centra las replicas en la
    media sobre la clinica y no en la estimacion que se publica, y el
    intervalo por percentiles sigue cubriendo mas del 99 %."""
    n = conjunto.y.size
    filas = np.random.default_rng(SEMILLA_INDICES + b).integers(0, n, n)
    return aplanar(medir(conjunto, salidas, l_oraculo, filas))


def bootstrap(conjunto: Conjunto, salidas: dict, l_oraculo,
              replicas: int = B_REPLICAS) -> dict:
    """{ruta: [li, ls]} al 95 % por percentiles, pareado: cada replica mide
    todos los modelos sobre los mismos casos. `salidas` y `l_oraculo` son
    los de la estimacion puntual."""
    corridas = [replica(conjunto, salidas, l_oraculo, b) for b in range(replicas)]
    rutas = sorted(set().union(*corridas)) if corridas else []
    incompletas = [r for r in rutas if any(r not in c for c in corridas)]
    if incompletas:
        # Una cifra falta en una replica cuando su grupo de casos quedo vacio
        # al remuestrear. No se calcula un intervalo sobre menos replicas de
        # las que el resultado dice que hubo.
        raise ArithmeticError(f"{len(incompletas)} cifras faltan en alguna réplica (la "
                              f"primera, {incompletas[0]}): algún grupo de casos quedó "
                              "vacío al remuestrear")
    intervalos = {}
    for r in rutas:
        try:
            intervalos[r] = metricas.percentiles([c[r] for c in corridas])
        except ArithmeticError as error:
            # tampoco sobre las que dieron algo que no es un numero
            raise ArithmeticError(f"{r}: {error}") from None
    return intervalos


def escala_legible(modelo: oraculo.Modelo, conjunto: Conjunto) -> dict:
    """Por lado de la imagen y por puntuacion: la RV de la puntuacion una vez
    vista la imagen, en log-odds, y que fraccion de su log-RV conserva. En
    forma cerrada: cada placa pesa P(k | q_i, y_i), la probabilidad con que
    el generador le da esa puntuacion."""
    lrv = oraculo.log_rv_condicional(modelo)
    p1, p0 = modelo.probabilidades()
    pesos = np.where((conjunto.y == 1)[:, None], p1, p0)
    salida = {}
    for lado, m in (("a_favor", conjunto.rv >= 1.0), ("en_contra", conjunto.rv < 1.0)):
        por_k, fr_ext, w_ext = [], [], []
        for k in range(6):
            ln_rv = math.log(oraculo.rv_recuentos(k))
            v, w = lrv[m, k], pesos[m, k]
            fr = v / ln_rv
            q = metricas.cuantiles_ponderados(v, w)
            qf = metricas.cuantiles_ponderados(fr, w)
            por_k.append({
                "k": k, "ln_rv_recuentos": ln_rv, "casos_esperados": float(w.sum()),
                "log_rv": {"q1": float(q[0]), "mediana": float(q[1]), "q3": float(q[2])},
                "fraccion": {"q1": float(qf[0]), "mediana": float(qf[1]), "q3": float(qf[2])},
                "signo_invertido": float(w[fr < 0].sum() / w.sum()),
                "poco_informativa": abs(ln_rv) < POCO_INFORMATIVA,
            })
            if k in EXTREMAS:
                fr_ext.append(fr)
                w_ext.append(w)
        salida[lado] = {
            "placas": int(m.sum()), "por_puntuacion": por_k,
            "fraccion_mediana_extremas": float(metricas.cuantiles_ponderados(
                np.concatenate(fr_ext), np.concatenate(w_ext), (0.5,))[0]),
        }
    return salida


def _bandas(p) -> np.ndarray:
    return np.array([banda(porcentaje_entero(float(x))) for x in p], dtype=object)


def cambios_de_banda(antes, despues) -> dict:
    """Cuantos casos cambian de banda y en que sentido («antes→despues»)."""
    antes, despues = np.asarray(antes, dtype=object), np.asarray(despues, dtype=object)
    transiciones = {}
    for a in BANDAS:
        for d in BANDAS:
            n = int(np.sum((antes == a) & (despues == d)))
            if a != d and n:
                transiciones[f"{a}→{d}"] = n
    return {"casos": int(antes.size), "cambian": int(np.sum(antes != despues)),
            "transiciones": transiciones}


def sensibilidad_al_previo(conjunto: Conjunto, clinica: pd.DataFrame, salidas: dict,
                           previo: float = PREVALENCIA_COHORTE) -> dict:
    """Lo que cuesta declarar `previo` en una poblacion cuya prevalencia es la
    del conjunto (spec §4.3): Brier, ECE e intercepto de los dos modelos
    combinados, y cuantos casos cambian de banda. El AUC no cambia."""
    otras = salidas_del_sistema(previo, clinica, conjunto.rv)
    s = salidas["conocida"]
    y, orden = conjunto.y[s], conjunto.orden[s]
    modelos = {}
    for c in COMBINADOS:
        antes, despues = salidas[c][s], otras[c][s]
        modelos[c] = {
            "brier": metricas.brier(y, despues), "brier_principal": metricas.brier(y, antes),
            "ece": metricas.ece(y, despues, orden), "ece_principal": metricas.ece(y, antes, orden),
            "suelo": metricas.suelo_de_ece(despues, orden),
            "intercepto": metricas.intercepto_de_calibracion(y, despues),
            "intercepto_principal": metricas.intercepto_de_calibracion(y, antes),
            "bandas": cambios_de_banda(_bandas(antes), _bandas(despues)),
        }
    desplazamiento = (math.log(previo / (1 - previo))
                      - math.log(conjunto.prevalencia / (1 - conjunto.prevalencia)))
    return {"previo": float(previo), "previo_principal": conjunto.prevalencia,
            "desplazamiento_log_odds": desplazamiento, "modelos": modelos,
            "categoria_del_sistema": cambios_de_banda(salidas["primaria"], otras["primaria"])}


def optimismo_de_la_derivacion(conjunto: Conjunto, clinica: pd.DataFrame, salidas: dict) -> dict:
    """0C, un CALCULO y no un experimento: cuanto difieren las RV de la
    derivacion (las del sistema) de las bandas de la validacion externa, y
    cuantos casos con el asma conocida cambiarian de banda con las segundas."""
    s = salidas["conocida"]
    k = salidas["puntuacion"][s]
    # A 4 decimales, como lo entregaria el sistema con esas RV: los dos lados
    # de la comparacion son lo mismo salvo la tabla.
    con_validacion = np.array([
        round(combinar(conjunto.prevalencia, RV_VALIDACION[int(kk)], float(r)), 4)
        for kk, r in zip(k, conjunto.rv[s])])
    return {
        "por_puntuacion": [{"k": kk, "rv_derivacion": RV_POR_PUNTUACION[kk],
                            "rv_validacion": RV_VALIDACION[kk],
                            "diferencia_log": math.log(RV_POR_PUNTUACION[kk] / RV_VALIDACION[kk])}
                           for kk in range(6)],
        "bandas": cambios_de_banda(_bandas(salidas["independencia"][s]), _bandas(con_validacion)),
    }


def evaluar_celda(conjunto: Conjunto, rho1: float, rho0: float, replicas: int = 0,
                  con_sensibilidad: bool = False) -> dict:
    """La celda (ρ1, ρ0): estimacion puntual, suelo de la ECE y fiabilidad
    por modelo, escala legible, y si se piden, intervalos y sensibilidad."""
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, rho1, rho0)
    clinica = generador.generar(modelo, SEMILLA_PUNTUAL)
    salidas = salidas_del_sistema(conjunto.prevalencia, clinica, conjunto.rv)
    l_or = oraculo_de_los_casos(modelo, conjunto.q, clinica)
    celda = {"rho1": float(rho1), "rho0": float(rho0),
             "nombre": nombre_de_celda(rho1, rho0),
             "correlacion_teorica": {"con_opacidad": oraculo.correlacion_teorica(modelo, 1),
                                     "sin_opacidad": oraculo.correlacion_teorica(modelo, 0)}}
    celda.update(medir(conjunto, salidas, l_or))
    s = salidas["conocida"]
    p = {"imagen": conjunto.p_cal, "clinica": salidas["clinica"],
         "independencia": salidas["independencia"], "conservador": salidas["conservador"]}
    for m in MODELOS:
        celda["modelos"][m]["suelo"] = metricas.suelo_de_ece(p[m][s], conjunto.orden[s])
        celda["modelos"][m]["fiabilidad"] = metricas.fiabilidad(
            conjunto.y[s], p[m][s], conjunto.orden[s])
    contencion = celda["horquilla"]["todos"]["contencion"]
    celda["hipotesis"] = {"umbral": HIPOTESIS_CONTENCION, "contencion": contencion,
                          "se_sostiene": bool(contencion >= HIPOTESIS_CONTENCION)}
    celda["escala_legible"] = escala_legible(modelo, conjunto)
    if replicas:
        celda["replicas"] = int(replicas)
        celda["intervalos"] = bootstrap(conjunto, salidas, l_or, replicas)
    if con_sensibilidad:
        celda["sensibilidad_al_previo"] = sensibilidad_al_previo(conjunto, clinica, salidas)
        if rho1 == 0.0 and rho0 == 0.0:
            celda["optimismo_de_la_derivacion"] = optimismo_de_la_derivacion(
                conjunto, clinica, salidas)
    return celda


def evaluar_tarea(tarea) -> dict:
    """Una celda desde cero, para correrla en su propio proceso: `tarea` es
    (ρ1, ρ0, replicas, con_sensibilidad). Carga el conjunto congelado."""
    rho1, rho0, replicas, con_sensibilidad = tarea
    return evaluar_celda(cargar_conjunto(), rho1, rho0, int(replicas), bool(con_sensibilidad))


def imagen_sola(conjunto: Conjunto) -> dict:
    """La calibracion de la imagen sobre las 3 811 placas: el suelo de todo
    lo demas (spec §4.4)."""
    r = metricas.resumen_de_modelo(conjunto.y, conjunto.p_cal, conjunto.orden)
    r["suelo"] = metricas.suelo_de_ece(conjunto.p_cal, conjunto.orden)
    r["fiabilidad"] = metricas.fiabilidad(conjunto.y, conjunto.p_cal, conjunto.orden)
    r["casos"] = int(conjunto.y.size)
    return r
