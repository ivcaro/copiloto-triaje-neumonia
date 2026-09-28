# -*- coding: utf-8 -*-
"""Concordancia, acuerdo continuo, tiempos y el analisis de la sesion con el
medico (spec de SP5 §5.4-§5.5, §11.4; plan SP5-A D9).

Primario: kappa ponderado lineal sobre las 24 lecturas SIN copiloto. Tambien
el de Cohen sin ponderar (el prometido literalmente) y el binario en «alta».
Dos intervalos: el analitico de Fleiss, Cohen y Everitt (1969) y el BCa por
remuestreo de casos. Con 24 casos el intervalo mide 0,5-0,6 y el texto que lo
dice esta fijado aqui, antes de la sesion.
"""
from __future__ import annotations

import csv
import math
import pathlib
import statistics

import numpy as np
from scipy.special import ndtr, ndtri
from scipy.stats import rankdata

CATEGORIAS = ("baja", "intermedia", "alta")
NOTAS = ("correccion", "utilidad", "lenguaje")
COLUMNAS_CSV = ("lectura", "orden", "id", "practica", "control", "banda", "porcentaje",
                "abierto_en", "enviado_en", "segundos", "banda_con", "porcentaje_con",
                "segundos_con", "correccion", "utilidad", "lenguaje", "comentario")
B_BOOTSTRAP = 2000
SEMILLA_BOOTSTRAP = 20261013
TEXTO_FIJADO = (
    "Con 24 casos y un solo evaluador, el intervalo del 95 % del kappa tiene una "
    "anchura de 0,5 a 0,6. El diseño no distingue una concordancia moderada (0,4) "
    "de una sustancial (0,6), ni generaliza a otros médicos ni a otro reparto de "
    "casos, que aquí es deliberado. El criterio ≥ 0,4 de la Semana 1 se evalúa "
    "sobre la estimación puntual y se publica siempre con su intervalo; si el "
    "límite inferior queda por debajo de 0,4, se dice.")


# --------------------------------------------------------------------------
# Kappas
# --------------------------------------------------------------------------
def indices(categorias_obs, categorias=CATEGORIAS) -> np.ndarray:
    try:
        return np.array([categorias.index(c) for c in categorias_obs], dtype=int)
    except ValueError as exc:
        raise ValueError(f"categoría desconocida: {exc}") from None


def pesos(c: int, tipo: str) -> np.ndarray:
    i = np.arange(c)
    if tipo == "lineal":
        return 1.0 - np.abs(i[:, None] - i[None, :]) / (c - 1)
    if tipo == "ninguno":
        return np.eye(c)
    raise ValueError(f"tipo de pesos desconocido: {tipo!r}")


def kappa(a, b, c: int = 3, tipo: str = "lineal") -> dict:
    """Kappa (ponderado lineal o de Cohen) con el error tipico de Fleiss,
    Cohen y Everitt (1969):
        Var = [Σ p_ij (w_ij − (w̄_i. + w̄_.j)(1 − κ))² − (κ − p_e(1 − κ))²] / [n (1 − p_e)²]
    con w̄_i. = Σ_j p_.j w_ij y w̄_.j = Σ_i p_i. w_ij."""
    a = np.asarray(a, dtype=int)
    b = np.asarray(b, dtype=int)
    n = a.size
    if n == 0 or b.size != n:
        raise ValueError("las dos listas deben tener la misma longitud, y no estar vacías")
    m = np.zeros((c, c))
    np.add.at(m, (a, b), 1.0)
    m /= n
    w = pesos(c, tipo)
    pi, pj = m.sum(axis=1), m.sum(axis=0)
    po = float((m * w).sum())
    pe = float((np.outer(pi, pj) * w).sum())
    if pe >= 1.0:
        nan = float("nan")
        return {"kappa": nan, "ee": nan, "ic95": [nan, nan], "po": po, "pe": pe, "n": int(n)}
    k = (po - pe) / (1.0 - pe)
    wi = w @ pj
    wj = pi @ w
    termino = (w - (wi[:, None] + wj[None, :]) * (1.0 - k)) ** 2
    var = ((m * termino).sum() - (k - pe * (1.0 - k)) ** 2) / (n * (1.0 - pe) ** 2)
    ee = math.sqrt(max(float(var), 0.0))
    return {"kappa": float(k), "ee": ee,
            "ic95": [float(k - 1.96 * ee), float(k + 1.96 * ee)],
            "po": po, "pe": pe, "n": int(n)}


def kappa_binario(a, b, positiva: str = "alta") -> dict:
    ia = (np.asarray(a) == positiva).astype(int)
    ib = (np.asarray(b) == positiva).astype(int)
    return kappa(ia, ib, c=2, tipo="ninguno")


def bca(datos, estadistico, B: int = B_BOOTSTRAP, semilla: int = SEMILLA_BOOTSTRAP,
        alfa: float = 0.05) -> list:
    """Intervalo BCa por remuestreo de casos (las filas de `datos`)."""
    datos = np.asarray(datos)
    n = datos.shape[0]
    rng = np.random.default_rng(semilla)
    theta = float(estadistico(datos))
    boots = np.array([estadistico(datos[rng.integers(0, n, n)]) for _ in range(B)], dtype=float)
    boots = boots[np.isfinite(boots)]
    if boots.size == 0 or np.all(boots == boots[0]):
        return [theta, theta]
    fraccion = (np.sum(boots < theta) + 0.5 * np.sum(boots == theta)) / boots.size
    z0 = ndtri(min(max(float(fraccion), 1e-6), 1 - 1e-6))
    jack = np.array([estadistico(np.delete(datos, i, axis=0)) for i in range(n)], dtype=float)
    jack = jack[np.isfinite(jack)]
    d = jack.mean() - jack
    den = 6.0 * (np.sum(d ** 2) ** 1.5)
    a = float(np.sum(d ** 3) / den) if den > 0 else 0.0

    def ajustada(z):
        return float(ndtr(z0 + (z0 + z) / (1.0 - a * (z0 + z))))

    lo, hi = ajustada(ndtri(alfa / 2)), ajustada(ndtri(1 - alfa / 2))
    return [float(np.percentile(boots, 100 * lo)), float(np.percentile(boots, 100 * hi))]


def kappa_con_intervalos(a, b, tipo: str = "lineal") -> dict:
    """`tipo`: lineal | ninguno | binario_alta. Devuelve el kappa con los dos intervalos."""
    if tipo == "binario_alta":
        ia = (np.asarray(a) == "alta").astype(int)
        ib = (np.asarray(b) == "alta").astype(int)
        c, pesos_ = 2, "ninguno"
    else:
        ia, ib, c, pesos_ = indices(a), indices(b), 3, tipo
    r = kappa(ia, ib, c, pesos_)
    pares = np.stack([ia, ib], axis=1)
    r["ic95_bca"] = bca(pares, lambda d: kappa(d[:, 0], d[:, 1], c, pesos_)["kappa"])
    r["tipo"] = tipo
    return r


# --------------------------------------------------------------------------
# Acuerdo continuo y tiempos
# --------------------------------------------------------------------------
def acuerdo_continuo(pct_medico, p_sistema, minima=None, maxima=None) -> dict:
    """Spearman entre el porcentaje del medico y el punto medio del sistema;
    Bland-Altman en log-odds con 0 y 100 acotados a 0,5 y 99,5; y la fraccion
    de porcentajes que caen dentro de la horquilla."""
    pct = np.asarray(pct_medico, dtype=float)
    p = np.asarray(p_sistema, dtype=float)
    acotados = int(np.sum((pct <= 0) | (pct >= 100)))
    pm = np.clip(pct, 0.5, 99.5) / 100.0
    d = np.log(pm / (1 - pm)) - np.log(p / (1 - p))
    de = float(d.std(ddof=1)) if d.size > 1 else 0.0
    salida = {"n": int(pct.size),
              "spearman": float(np.corrcoef(rankdata(pct), rankdata(p))[0, 1]) if pct.size > 1 else float("nan"),
              "diferencia_media_log_odds": float(d.mean()), "de": de,
              "limites_95": [float(d.mean() - 1.96 * de), float(d.mean() + 1.96 * de)],
              "acotados_0_o_100": acotados}
    if minima is not None and maxima is not None:
        dentro = (pm >= np.asarray(minima, dtype=float)) & (pm <= np.asarray(maxima, dtype=float))
        salida["fraccion_dentro_de_la_horquilla"] = float(dentro.mean())
    return salida


def razon_de_tiempos(t_sin, t_con) -> dict:
    """Razon de medias geometricas con/sin, pareada por caso, con BCa."""
    t_sin = np.asarray(t_sin, dtype=float)
    t_con = np.asarray(t_con, dtype=float)
    if t_sin.size == 0 or t_sin.size != t_con.size or np.any(t_sin <= 0) or np.any(t_con <= 0):
        raise ValueError("hacen falta tiempos pareados y positivos")
    ln = np.log(t_con / t_sin)

    def razon(d):
        return float(np.exp(np.mean(d)))

    r = razon(ln)
    return {"n": int(ln.size), "razon_medias_geometricas": r,
            "ic95_bca": bca(ln, razon) if ln.size >= 3 else [r, r],
            "reduccion_pct": float((1.0 - r) * 100.0),
            "razones": [float(x) for x in np.exp(ln)]}


# --------------------------------------------------------------------------
# El CSV del formulario y el analisis
# --------------------------------------------------------------------------
def _entero(v):
    return None if v in ("", None) else int(float(v))


def _decimal(v):
    return None if v in ("", None) else float(v)


def leer_csv(ruta) -> list:
    """Las filas del CSV del formulario con sus tipos."""
    with open(ruta, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    salida = []
    for fila in filas:
        salida.append({
            "lectura": fila["lectura"], "orden": _entero(fila["orden"]), "id": fila["id"],
            "practica": fila["practica"].strip().lower() == "true",
            "control": fila["control"].strip().lower() == "true",
            "banda": fila["banda"], "porcentaje": _entero(fila["porcentaje"]),
            "abierto_en": _entero(fila["abierto_en"]), "enviado_en": _entero(fila["enviado_en"]),
            "segundos": _decimal(fila["segundos"]),
            "banda_con": fila["banda_con"] or None, "porcentaje_con": _entero(fila["porcentaje_con"]),
            "segundos_con": _decimal(fila["segundos_con"]),
            **{k: _entero(fila[k]) for k in NOTAS},
            "comentario": fila.get("comentario", "") or "",
        })
    return salida


def _sin_practica(filas):
    return [f for f in filas if not f["practica"]]


def _notas(filas) -> dict:
    salida = {}
    for k in NOTAS:
        valores = [f[k] for f in filas if f[k] is not None]
        salida[k] = {"media": float(np.mean(valores)) if valores else None,
                     "distribucion": {str(v): valores.count(v) for v in range(1, 6)},
                     "n": len(valores)}
    return salida


def analizar(clave: dict, lectura1: list, lectura2: list | None = None,
             planb: list | None = None) -> dict:
    """De los CSV y la clave a la estructura de `sesion.json`."""
    casos = {c["patientId"]: c for c in clave["casos"]}
    categoria_de = "mensaje" if all("categoria" in c for c in casos.values()) else "prevista"
    clave_cat = "categoria" if categoria_de == "mensaje" else "categoria_prevista"
    clave_bloque = "bloque" if categoria_de == "mensaje" else "bloque_previsto"

    l1 = _sin_practica(lectura1)
    ids = [f["id"] for f in l1]
    if set(ids) != set(casos) or len(ids) != len(casos):
        raise ValueError(f"la lectura 1 tiene {len(ids)} filas para {len(casos)} casos, o ids que no cuadran")
    sistema = [casos[i][clave_cat]["primaria"] for i in ids]
    medico = [f["banda"] for f in l1]
    pct = [f["porcentaje"] for f in l1]

    kappas = {"ponderado_lineal": kappa_con_intervalos(sistema, medico, "lineal"),
              "cohen": kappa_con_intervalos(sistema, medico, "ninguno"),
              "binario_alta": kappa_con_intervalos(sistema, medico, "binario_alta")}
    sensibilidad = {v: kappa(indices([casos[i][clave_cat][v] for i in ids]), indices(medico), 3, "lineal")["kappa"]
                    for v in ("independencia", "conservador", "cruza")}
    acuerdo = acuerdo_continuo(pct, [casos[i][clave_cat]["punto_medio"] for i in ids],
                               minima=[casos[i][clave_bloque]["minima"] for i in ids],
                               maxima=[casos[i][clave_bloque]["maxima"] for i in ids])
    desacuerdos = [{"id": f["id"], "estrato": casos[f["id"]]["estrato"], "sistema": s,
                    "medico": f["banda"], "porcentaje": f["porcentaje"],
                    "horquilla": [casos[f["id"]][clave_bloque]["minima"], casos[f["id"]][clave_bloque]["maxima"]],
                    "comentario": f["comentario"]}
                   for f, s in zip(l1, sistema) if f["banda"] != s]
    medico1 = {f["id"]: f["banda"] for f in l1}
    t1 = {f["id"]: f["segundos"] for f in l1}

    salida = {"rotulo": clave.get("rotulo", "simulación semisintética — sesión H7"),
              "n": len(ids), "categoria_de": categoria_de, "kappa": kappas,
              "sensibilidad_categoria": sensibilidad, "acuerdo_continuo": acuerdo,
              "desacuerdos": desacuerdos, "lectura2": None, "plan_b": None,
              "texto_fijado": TEXTO_FIJADO}

    if lectura2 is not None:
        l2 = _sin_practica(lectura2)
        con = [f for f in l2 if not f["control"]]
        controles = [f for f in l2 if f["control"]]
        tiempo = razon_de_tiempos([t1[f["id"]] for f in con], [f["segundos"] for f in con])
        razones_c = [f["segundos"] / t1[f["id"]] for f in controles]
        media_c = float(np.exp(np.mean(np.log(razones_c)))) if razones_c else None
        tiempo["controles"] = {"n": len(controles), "razones": razones_c, "media_geometrica": media_c}
        tiempo["razon_corregida_por_releer"] = (tiempo["razon_medias_geometricas"] / media_c
                                                if media_c else None)
        tiempo["medido"] = True
        salida["lectura2"] = {
            "n_con_mensaje": len(con), "n_controles": len(controles),
            "kappa_con_mensaje": kappa_con_intervalos(
                [casos[f["id"]][clave_cat]["primaria"] for f in con], [f["banda"] for f in con], "lineal"),
            "cambios_de_banda": sum(f["banda"] != medico1[f["id"]] for f in con),
            "utilidad": _notas(con), "tiempo": tiempo}

    if planb is not None:
        pb = _sin_practica(planb)
        salida["plan_b"] = {
            "tiempo_medido": False,
            "segundos_adicionales_leer_mensaje": {
                "mediana": float(statistics.median([f["segundos_con"] for f in pb if f["segundos_con"] is not None])),
                "n": sum(f["segundos_con"] is not None for f in pb)},
            "kappa_con_mensaje": kappa_con_intervalos(
                [casos[f["id"]][clave_cat]["primaria"] for f in pb], [f["banda_con"] for f in pb], "lineal"),
            "cambios_de_banda": sum(f["banda_con"] != f["banda"] for f in pb),
            "utilidad": _notas(pb)}
    return salida


# --------------------------------------------------------------------------
# El acta
# --------------------------------------------------------------------------
def _f(x, decimales=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    return f"{x:.{decimales}f}".replace(".", ",")


def _kappa_texto(k: dict) -> str:
    return (f"{_f(k['kappa'])} (IC 95 % analítico {_f(k['ic95'][0])} a {_f(k['ic95'][1])}; "
            f"BCa {_f(k['ic95_bca'][0])} a {_f(k['ic95_bca'][1])}; n = {k['n']})")


def _fecha(ms):
    import datetime
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d") if ms else "—"


def valores_para_acta(sesion: dict, clave: dict, lectura1: list | None = None,
                      lectura2: list | None = None) -> dict:
    """Los valores que rellenan la plantilla. Ninguno se teclea: salen de
    `sesion.json` y de la clave."""
    k = sesion["kappa"]
    casos = "\n".join(f"| {c['patientId']} | {c['estrato']} | {'concordante' if c['concordante'] else 'discordante'} |"
                      for c in clave["casos"])
    desacuerdos = "\n".join(
        f"| {d['id']} | {d['estrato']} | {d['sistema']} | {d['medico']} ({d['porcentaje']} %) | "
        f"{_f(d['horquilla'][0] * 100, 0)}-{_f(d['horquilla'][1] * 100, 0)} % | {d['comentario']} |"
        for d in sesion["desacuerdos"]) or "| (ninguno) | | | | | |"
    l2 = sesion.get("lectura2")
    pb = sesion.get("plan_b")
    if l2:
        t = l2["tiempo"]
        tiempo = (f"razón de medias geométricas con/sin {_f(t['razon_medias_geometricas'])} "
                  f"(IC 95 % BCa {_f(t['ic95_bca'][0])} a {_f(t['ic95_bca'][1])}; n = {t['n']}), "
                  f"reducción {_f(t['reduccion_pct'], 0)} %; controles releídos sin copiloto: "
                  f"media geométrica {_f(t['controles']['media_geometrica'])} (n = {t['controles']['n']}); "
                  f"razón corregida por releer {_f(t['razon_corregida_por_releer'])}. La reducción mezcla "
                  f"el efecto del copiloto con el de releer; los controles lo estiman de forma descriptiva.")
        influencia = (f"kappa con el mensaje delante {_kappa_texto(l2['kappa_con_mensaje'])}; "
                      f"cambió de banda en {l2['cambios_de_banda']} de {l2['n_con_mensaje']} casos")
        u = l2["utilidad"]
    elif pb:
        tiempo = (f"no medido (plan B, una sola sesión); leer el mensaje añadió una mediana de "
                  f"{_f(pb['segundos_adicionales_leer_mensaje']['mediana'], 0)} s por caso")
        influencia = (f"kappa tras revelar el mensaje {_kappa_texto(pb['kappa_con_mensaje'])}; "
                      f"cambió de banda en {pb['cambios_de_banda']} de {pb['kappa_con_mensaje']['n']} casos")
        u = pb["utilidad"]
    else:
        tiempo = "no medido"
        influencia = "no medida"
        u = None
    utilidad = ("; ".join(f"{n} {_f(u[n]['media'], 1)} (n = {u[n]['n']})" for n in NOTAS) if u else "no medida")
    a = sesion["acuerdo_continuo"]
    return {
        "rotulo": sesion["rotulo"], "n": str(sesion["n"]),
        "fecha_lectura1": _fecha(lectura1[0]["abierto_en"]) if lectura1 else "—",
        "fecha_lectura2": _fecha(lectura2[0]["abierto_en"]) if lectura2 else "—",
        "prevalencia_sesion": _f(clave.get("prevalencia_sesion"), 4),
        "categoria_de": sesion["categoria_de"],
        "kappa_ponderado": _kappa_texto(k["ponderado_lineal"]),
        "kappa_cohen": _kappa_texto(k["cohen"]),
        "kappa_binario": _kappa_texto(k["binario_alta"]),
        "sensibilidad": "; ".join(f"{v} {_f(x)}" for v, x in sesion["sensibilidad_categoria"].items()),
        "spearman": _f(a["spearman"]), "bland_altman": f"{_f(a['diferencia_media_log_odds'])} (DE {_f(a['de'])})",
        "dentro_horquilla": _f(a.get("fraccion_dentro_de_la_horquilla", float("nan")) * 100, 0),
        "acotados": str(a["acotados_0_o_100"]),
        "influencia": influencia, "utilidad": utilidad, "tiempo": tiempo,
        "tabla_casos": casos, "tabla_desacuerdos": desacuerdos,
        "texto_fijado": sesion["texto_fijado"],
    }


def rellenar_acta(plantilla: str, valores: dict) -> str:
    """Sustituye {{clave}}; una clave sin valor es KeyError, no un hueco."""
    import re
    def sustituir(m):
        return str(valores[m.group(1)])
    return re.sub(r"\{\{(\w+)\}\}", sustituir, plantilla)
