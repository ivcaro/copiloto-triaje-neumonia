# -*- coding: utf-8 -*-
"""La categoria del sistema para el kappa, fijada ANTES de la sesion (spec §5.3).

Regla primaria: la banda del punto medio en log-odds de [minima, maxima],
convertido a porcentaje entero con redondeo hacia arriba en ,5 (el mismo
`Math.round` del nodo Desenlace). Bandas: [0, 20) baja, [20, 70] intermedia,
(70, 100] alta. Los cortes 20 y 70 son una convencion del equipo fijada el
27-sep, no un estandar publicado.

Variantes, fijadas de antemano como analisis de sensibilidad: la banda del
extremo de independencia, la del extremo conservador, y la regla «si la
horquilla cruza un limite, intermedia». Con las tablas actuales ninguna
horquilla cruza a la vez el 20 % y el 70 % (prueba): el cociente de odds de
los dos extremos vale min(RV_clinica, RV_imagen) ≤ 17,5, y cruzar los dos
exige ademas odds_previas × max(RV) < 0,25, que solo ocurre con prevalencia
declarada por debajo de ≈ 2,6 %.
"""
from __future__ import annotations

import math

BANDAS = ("baja", "intermedia", "alta")
_MARGEN = 1e-6   # un bloque redondeado a 4 decimales no llega a 0 ni a 1, pero por si acaso


def porcentaje_entero(p: float) -> int:
    """floor(100 p + 0,5): hacia arriba en ,5, como `Math.round` en el bot."""
    return int(math.floor(p * 100.0 + 0.5))


def banda(pct: int) -> str:
    if pct < 20:
        return "baja"
    if pct > 70:
        return "alta"
    return "intermedia"


def _logit(p: float) -> float:
    p = min(max(float(p), _MARGEN), 1.0 - _MARGEN)
    return math.log(p / (1.0 - p))


def punto_medio_log_odds(a: float, b: float) -> float:
    medio = 0.5 * (_logit(a) + _logit(b))
    return 1.0 / (1.0 + math.exp(-medio))


def categoria_del_sistema(bloque: dict) -> dict:
    """La primaria y las tres variantes, a partir del bloque `combinacion`."""
    medio = punto_medio_log_odds(bloque["minima"], bloque["maxima"])
    indep = bloque["independencia"]
    independencia = punto_medio_log_odds(indep[0], indep[-1])
    dep = bloque["dependencia"]
    conservador = (punto_medio_log_odds(dep[0], dep[-1]) if bloque["concordantes"] and dep
                   else independencia)
    baja_, alta_ = banda(porcentaje_entero(bloque["minima"])), banda(porcentaje_entero(bloque["maxima"]))
    return {
        "primaria": banda(porcentaje_entero(medio)),
        "punto_medio": medio,
        "independencia": banda(porcentaje_entero(independencia)),
        "conservador": banda(porcentaje_entero(conservador)),
        "cruza": baja_ if baja_ == alta_ else "intermedia",
        "cruza_limite": baja_ != alta_,
    }
