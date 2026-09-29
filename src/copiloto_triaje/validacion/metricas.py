# -*- coding: utf-8 -*-
"""Las métricas de la simulación semisintética (spec de SP5 §4.6).

Funciones puras sobre vectores: ni leen ficheros ni dibujan. Todo lo que se
compara con el oráculo se compara en LOG-ODDS, que es la escala en la que el
sistema suma evidencia.

- Por modelo: AUC, Brier, pendiente e intercepto de calibracion, ECE con su
  suelo de ruido y la curva de fiabilidad.
- La horquilla frente al oraculo: posicion λ, las dos colas y la contencion,
  con la tolerancia ε = 0,015 (el redondeo maximo de las RV publicadas, la
  misma de 0A.3).
- Un solo numero o un rango frente al oraculo: error puntual (los
  discordantes) y contencion en un rango (el asma desconocida).
- Percentiles, para los intervalos del bootstrap, y cuantiles ponderados,
  para la escala legible.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq, minimize
from scipy.special import expit
from sklearn.metrics import roc_auc_score

EPSILON = 0.015              # log-odds; la tolerancia de 0A.3
BINS = 10                    # ECE y fiabilidad: deciles de igual masa
REPETICIONES_SUELO = 200     # etiquetas simuladas para el suelo de la ECE
SEMILLA_SUELO = 20261009
MARGEN = 1e-6                # una p redondeada a 4 decimales no llega a 0 ni a 1
CUARTILES = (0.25, 0.5, 0.75)


def logit(p) -> np.ndarray:
    """ln(p / (1 − p)), con p acotada a [MARGEN, 1 − MARGEN]."""
    p = np.clip(np.asarray(p, dtype=float), MARGEN, 1.0 - MARGEN)
    return np.log(p / (1.0 - p))


def _vectores(y, p):
    """`y` como 0/1 y `p` como probabilidades, de la misma forma. Se rechaza
    lo que no lo es en vez de truncarlo: un 0,7 en `y` pasaria a 0 sin aviso."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    if y.ndim != 1 or y.shape != p.shape or y.size == 0:
        raise ValueError(f"y y p deben ser vectores no vacíos de la misma forma, "
                         f"y son {y.shape} y {p.shape}")
    if not np.isin(y, (0.0, 1.0)).all():
        raise ValueError("y debe valer 0 o 1 en todos los casos")
    if not (np.isfinite(p).all() and (p >= 0.0).all() and (p <= 1.0).all()):
        raise ValueError("p debe ser una probabilidad (entre 0 y 1) en todos los casos")
    return y.astype(int), p


def _dos_clases(y, que: str) -> None:
    if float(np.ptp(y)) == 0.0:
        raise ArithmeticError(f"con una sola clase no hay {que} que estimar")


def auc(y, p) -> float:
    y, p = _vectores(y, p)
    _dos_clases(y, "AUC")
    return float(roc_auc_score(y, p))


def brier(y, p) -> float:
    y, p = _vectores(y, p)
    return float(np.mean((p - y) ** 2))


def _verosimilitud(y, x, a: float, b: float) -> float:
    eta = a + b * x
    return float(np.sum(y * eta - np.logaddexp(0.0, eta)))


def _gradiente_y_hessiana(y, x, a: float, b: float):
    mu = expit(a + b * x)
    w = mu * (1.0 - mu)
    g = np.array([np.sum(y - mu), np.sum((y - mu) * x)])
    h = np.array([[np.sum(w), np.sum(w * x)],
                  [np.sum(w * x), np.sum(w * x * x)]])
    return g, h


def _newton(y, x, a: float, b: float, pasos: int):
    """Newton con retroceso desde (a, b): (a, b) al converger, o None si se
    queda sin paso que dar. La verosimilitud es concava, asi que un paso que
    la empeora se acorta a la mitad; el margen de la comparacion es el ruido
    de redondeo de la propia verosimilitud (cerca del maximo un paso bueno la
    cambia menos que eso)."""
    for _ in range(pasos):
        g, h = _gradiente_y_hessiana(y, x, a, b)
        try:
            paso = np.linalg.solve(h, g)
        except np.linalg.LinAlgError:
            return None
        if not np.all(np.isfinite(paso)):
            return None
        if float(np.max(np.abs(paso))) < 1e-8:
            return a + paso[0], b + paso[1]
        actual, t = _verosimilitud(y, x, a, b), 1.0
        margen = 1e-10 * (1.0 + abs(actual))
        while _verosimilitud(y, x, a + t * paso[0], b + t * paso[1]) < actual - margen:
            t *= 0.5
            if t < 1e-10:
                return None
        a, b = a + t * paso[0], b + t * paso[1]
    return None


def pendiente_de_calibracion(y, p, pasos: int = 100) -> float:
    """La pendiente de la regresion logistica SIN penalizar de Y sobre
    logit p (con intercepto libre). Menor que 1: el modelo exagera; mayor
    que 1: se queda corto.

    Antes de iterar se dice cuando NO existe: con una sola clase, con todas
    las p iguales, o con las clases separadas por las p (la pendiente seria
    infinita). Si existe, es unica: la busca Newton con retroceso y, si se
    queda sin paso (con muy pocos valores distintos de p y el orden invertido,
    el primer paso puede caer donde la hessiana ya no distingue nada), una
    region de confianza con la hessiana exacta, que Newton pule despues."""
    y, p = _vectores(y, p)
    _dos_clases(y, "pendiente de calibración")
    x = logit(p)
    if float(np.ptp(x)) == 0.0:
        raise ArithmeticError("con todas las p iguales no hay pendiente de calibración "
                              "que estimar")
    unos, ceros = x[y == 1], x[y == 0]
    if unos.min() >= ceros.max() or ceros.min() >= unos.max():
        raise ArithmeticError("las p separan del todo las clases: la pendiente de "
                              "calibración no es finita")
    solucion = _newton(y, x, 0.0, 1.0, pasos)
    if solucion is None:
        n = float(y.size)
        respaldo = minimize(
            lambda t: -_verosimilitud(y, x, t[0], t[1]) / n, np.array([0.0, 1.0]),
            jac=lambda t: -_gradiente_y_hessiana(y, x, t[0], t[1])[0] / n,
            hess=lambda t: _gradiente_y_hessiana(y, x, t[0], t[1])[1] / n,
            method="trust-exact", options={"gtol": 1e-8, "maxiter": 1000})
        solucion = _newton(y, x, float(respaldo.x[0]), float(respaldo.x[1]), pasos)
    if solucion is None:
        raise ArithmeticError("la regresión de calibración no converge, aunque la "
                              "pendiente existe: revisa las p")
    return float(solucion[1])


def intercepto_de_calibracion(y, p) -> float:
    """El intercepto con la pendiente FIJADA en 1 (calibracion global): la
    `a` que iguala la media de expit(a + logit p) a la frecuencia observada.
    Positivo: el modelo predice de menos."""
    y, p = _vectores(y, p)
    _dos_clases(y, "intercepto de calibración")
    x = logit(p)
    objetivo = float(np.mean(y))
    # logit() acota x a ±13,8: con a = ±50 la media predicha pasa de la
    # observada por los dos lados, por desequilibradas que esten las clases.
    return float(brentq(lambda a: float(np.mean(expit(a + x))) - objetivo, -50.0, 50.0,
                        xtol=1e-12))


def _deciles(p, orden, bins: int):
    """Los indices de cada bin de igual masa: se ordena por p y los empates
    se rompen con `orden` (el rango de patientId, declarado en el spec)."""
    return np.array_split(np.lexsort((np.asarray(orden), np.asarray(p, dtype=float))), bins)


def ece(y, p, orden, bins: int = BINS) -> float:
    y, p = _vectores(y, p)
    return float(sum(len(b) / y.size * abs(float(y[b].mean()) - float(p[b].mean()))
                     for b in _deciles(p, orden, bins) if len(b)))


def fiabilidad(y, p, orden, bins: int = BINS) -> list:
    """La curva de fiabilidad: por bin, cuantos casos, la p media y la
    frecuencia observada."""
    y, p = _vectores(y, p)
    return [{"n": int(len(b)), "p_media": float(p[b].mean()), "observada": float(y[b].mean())}
            for b in _deciles(p, orden, bins) if len(b)]


def suelo_de_ece(p, orden, repeticiones: int = REPETICIONES_SUELO,
                 semilla: int = SEMILLA_SUELO, bins: int = BINS) -> dict:
    """La ECE que daria un modelo PERFECTAMENTE calibrado con estas mismas p:
    etiquetas simuladas Bernoulli(p), `repeticiones` veces. Una ECE solo se
    lee al lado de este suelo, nunca contra un umbral absoluto."""
    p = np.asarray(p, dtype=float)
    rng = np.random.default_rng(semilla)
    valores = np.array([ece((rng.random(p.size) < p).astype(int), p, orden, bins)
                        for _ in range(repeticiones)])
    return {"media": float(valores.mean()), "p95": float(np.percentile(valores, 95))}


def resumen_de_modelo(y, p, orden) -> dict:
    """Las cinco cifras de un modelo puntual (sin el suelo, que es caro)."""
    return {"auc": auc(y, p), "brier": brier(y, p),
            "pendiente": pendiente_de_calibracion(y, p),
            "intercepto": intercepto_de_calibracion(y, p),
            "ece": ece(y, p, orden)}


def _log_odds(*vectores) -> list:
    """Los vectores como float, de la misma forma y FINITOS. Un NaN no es
    mayor ni menor que nada: sin esta guarda, un caso sin dato (la dependencia
    vacia de un discordante) contaria en silencio como «dentro». Y dos
    infinitos restados dan otro NaN."""
    v = [np.asarray(x, dtype=float) for x in vectores]
    if any(x.ndim != 1 or x.shape != v[0].shape for x in v):
        raise ValueError("los vectores deben tener la misma forma")
    if not all(np.isfinite(x).all() for x in v):
        raise ValueError("hay valores sin dato (NaN) o infinitos: se mide solo donde "
                         "hay dato; filtra los casos antes de medir")
    return v


def _cuartiles(x) -> dict:
    if x.size == 0:
        return {"q1": None, "mediana": None, "q3": None}
    q1, mediana, q3 = np.percentile(x, [25, 50, 75])
    return {"q1": float(q1), "mediana": float(mediana), "q3": float(q3)}


def horquilla(l_oraculo, l_dependencia, l_independencia, epsilon: float = EPSILON) -> dict:
    """Donde cae el oraculo respecto a [dependencia, independencia], en
    log-odds. λ = 0 es el extremo conservador y λ = 1 la independencia,
    apunte la evidencia hacia donde apunte. Las colas cuentan los casos en
    que el oraculo queda MAS ALLA de un extremo en mas de ε log-odds."""
    o, d, i = _log_odds(l_oraculo, l_dependencia, l_independencia)
    delta = i - d
    con = delta != 0.0
    n = int(con.sum())
    if n == 0:
        return {"n": 0, "sin_horquilla": int((~con).sum()), "lambda": _cuartiles(o[con]),
                "bajo": None, "sobre": None, "contencion": None}
    sentido = np.sign(delta[con])
    bajo = (o[con] - d[con]) * sentido < -epsilon
    sobre = (o[con] - i[con]) * sentido > epsilon
    # La contencion se CUENTA, no se resta: 1 − 0,06 − 0,04 da
    # 0,8999999999999999, y un 90 % exacto no alcanzaria su umbral.
    return {"n": n, "sin_horquilla": int((~con).sum()),
            "lambda": _cuartiles((o[con] - d[con]) / delta[con]),
            "bajo": float(bajo.mean()), "sobre": float(sobre.mean()),
            "contencion": float((~(bajo | sobre)).mean())}


def error_puntual(l_sistema, l_oraculo) -> dict:
    """Un solo numero del sistema frente al oraculo: |Δ logit| mediano y el
    sesgo (mediana de sistema − oraculo; positivo: el sistema da de mas)."""
    sistema, oraculo = _log_odds(l_sistema, l_oraculo)
    e = sistema - oraculo
    if e.size == 0:
        return {"n": 0, "error_abs_mediano": None, "sesgo_mediano": None}
    return {"n": int(e.size), "error_abs_mediano": float(np.median(np.abs(e))),
            "sesgo_mediano": float(np.median(e))}


def contencion_en_rango(l_oraculo, l_minima, l_maxima, epsilon: float = EPSILON) -> dict:
    """Fraccion de casos con el oraculo dentro de [minima − ε, maxima + ε]."""
    o, lo, hi = _log_odds(l_oraculo, l_minima, l_maxima)
    if np.any(lo > hi):
        raise ValueError("la mínima no puede superar a la máxima")
    if o.size == 0:
        return {"n": 0, "bajo": None, "sobre": None, "contencion": None}
    bajo, sobre = o < lo - epsilon, o > hi + epsilon
    return {"n": int(o.size), "bajo": float(bajo.mean()), "sobre": float(sobre.mean()),
            "contencion": float((~(bajo | sobre)).mean())}


def percentiles(valores, alfa: float = 0.05) -> list:
    """El intervalo por percentiles de las replicas. Cuentan TODAS: si
    alguna no es un numero se detiene, porque un intervalo no se calcula
    sobre menos replicas de las que el resultado dice que hubo."""
    v = np.asarray(valores, dtype=float)
    if v.size == 0:
        return [None, None]
    if not np.all(np.isfinite(v)):
        raise ArithmeticError(f"{int((~np.isfinite(v)).sum())} de las {v.size} réplicas "
                              "no dan un número")
    lo, hi = np.percentile(v, [100 * alfa / 2, 100 * (1 - alfa / 2)])
    return [float(lo), float(hi)]


def cuantiles_ponderados(valores, pesos, cuantiles=CUARTILES) -> np.ndarray:
    """Cuantiles de `valores` con pesos: el menor valor cuya masa acumulada
    alcanza el cuantil."""
    v = np.asarray(valores, dtype=float)
    w = np.asarray(pesos, dtype=float)
    if v.shape != w.shape or v.ndim != 1 or v.size == 0 or float(w.sum()) <= 0:
        raise ValueError("valores y pesos deben ser vectores no vacíos con masa positiva")
    orden = np.argsort(v, kind="stable")
    acumulada = np.cumsum(w[orden]) / float(w.sum())
    return np.array([v[orden][min(int(np.searchsorted(acumulada, c, side="left")), v.size - 1)]
                     for c in cuantiles])
