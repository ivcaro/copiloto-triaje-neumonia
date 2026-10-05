# -*- coding: utf-8 -*-
"""Concordancia, acuerdo continuo, tiempos y el analisis de la sesion con el
medico (spec de SP5 §5.4-§5.5, §11.4; plan SP5-A D9).

Primario: kappa ponderado lineal sobre las 24 lecturas SIN copiloto. Tambien
el de Cohen sin ponderar (el prometido literalmente) y el binario en «alta».
Dos intervalos: el analitico de Fleiss, Cohen y Everitt (1969) y el BCa por
remuestreo de casos. El texto que se declaro antes de la sesion (con 24 casos,
un intervalo de 0,5 a 0,6 de anchura) esta fijado aqui; el acta lo cita como
lo declarado y da detras lo observado.
"""
from __future__ import annotations

import csv
import datetime
import decimal
import math
import pathlib
import statistics

import numpy as np
from scipy.special import ndtr, ndtri
from scipy.stats import rankdata

from .categoria import porcentaje_entero

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
# Las fechas del acta son el dia en la hora de Ecuador continental (UTC−5, sin
# horario de verano), no en la zona de la maquina que analiza.
ZONA_DE_LA_SESION = datetime.timezone(datetime.timedelta(hours=-5))
# Bland-Altman acota el porcentaje del medico antes del logit (spec §5.5): un
# 0 % es 0,5 % y un 100 %, 99,5 %.
COTA_DEL_MEDICO = (0.005, 0.995)


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
    con w̄_i. = Σ_j p_.j w_ij y w̄_.j = Σ_i p_i. w_ij. El intervalo analitico
    κ ± 1,96·ee se acota a [−1, 1], el recorrido del kappa (con 24 casos y un
    kappa alto, sin acotar pasaria de 1)."""
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
            "ic95": [max(-1.0, float(k - 1.96 * ee)), min(1.0, float(k + 1.96 * ee))],
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
def _entero_como_el_bot(x: float) -> int:
    """Un extremo de la horquilla como el ENTERO que el medico puede contestar,
    con la convencion de Desenlace: por debajo de 0,01 el bot imprime «< 1 %»
    y el entero es 0; por encima de 0,99 imprime «> 99 %» y es 100; si no,
    `porcentaje_entero` (Math.round), que da de 1 a 99."""
    if x < 0.01:
        return 0
    if x > 0.99:
        return 100
    return porcentaje_entero(x)


def acuerdo_continuo(pct_medico, p_sistema, minima=None, maxima=None) -> dict:
    """Spearman entre el porcentaje del medico y el punto medio del sistema;
    Bland-Altman en log-odds con 0 y 100 acotados a 0,5 y 99,5; y la fraccion
    de porcentajes que caen dentro de la horquilla.

    Se acota al medico y no al sistema (spec §5.5). Donde el punto medio del
    sistema queda fuera de la cota, la diferencia no puede ser cero ni
    contestando lo mismo: esos casos se cuentan, para que el acta lo diga.

    «Dentro» compara el porcentaje entero del medico, SIN acotar, con la
    horquilla tal como la imprime el bot: los DOS extremos pasan por
    `_entero_como_el_bot`. Un extremo por debajo de 0,01 se imprime «< 1 %» y
    vale 0; uno por encima de 0,99 se imprime «> 99 %» y vale 100. Si los dos
    extremos dan el mismo entero el bot imprime un solo valor (los
    discordantes con el asma conocida, y cualquier horquilla entera bajo el
    1 % o sobre el 99 %): solo admite ese entero, y se cuentan aparte para
    que el acta lo diga."""
    pct = np.asarray(pct_medico, dtype=float)
    p = np.asarray(p_sistema, dtype=float)
    acotados = int(np.sum((pct <= 0) | (pct >= 100)))
    pm = np.clip(pct / 100.0, *COTA_DEL_MEDICO)
    d = np.log(pm / (1 - pm)) - np.log(p / (1 - p))
    de = float(d.std(ddof=1)) if d.size > 1 else 0.0
    if pct.size > 1:
        rp, rs = rankdata(pct), rankdata(p)
        spearman = float("nan") if (np.ptp(rp) == 0 or np.ptp(rs) == 0) else float(np.corrcoef(rp, rs)[0, 1])
    else:
        spearman = float("nan")
    salida = {"n": int(pct.size), "spearman": spearman,
              "diferencia_media_log_odds": float(d.mean()), "de": de,
              "limites_95": [float(d.mean() - 1.96 * de), float(d.mean() + 1.96 * de)],
              "acotados_0_o_100": acotados,
              "sistema_fuera_de_la_cota": int(np.sum(
                  (p < COTA_DEL_MEDICO[0]) | (p > COTA_DEL_MEDICO[1])))}
    if minima is not None and maxima is not None:
        lo = np.array([_entero_como_el_bot(x) for x in minima], dtype=int)
        hi = np.array([_entero_como_el_bot(x) for x in maxima], dtype=int)
        dentro = (pct >= lo) & (pct <= hi)
        salida["dentro_de_la_horquilla"] = int(dentro.sum())
        salida["fraccion_dentro_de_la_horquilla"] = float(dentro.mean())
        salida["horquillas_de_anchura_cero"] = int(np.sum(lo == hi))
        # de las de un solo valor, las que el bot imprime como una cota
        salida["horquillas_que_son_una_cota"] = int(np.sum(
            (lo == hi) & ((lo == 0) | (lo == 100))))
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


def razon_corregida(ln_con, ln_ctl, B: int = B_BOOTSTRAP, semilla: int = SEMILLA_BOOTSTRAP,
                     alfa: float = 0.05) -> dict:
    """Razon de tiempos corregida por releer: exp(mean(ln_con) - mean(ln_ctl)),
    con un intervalo percentil del 95 % por bootstrap estratificado (los pares
    con mensaje y los controles se remuestrean por separado, con reemplazo,
    cada uno dentro de su propio estrato, con una sola `default_rng(semilla)`)."""
    ln_con = np.asarray(ln_con, dtype=float)
    ln_ctl = np.asarray(ln_ctl, dtype=float)
    if ln_con.size == 0 or ln_ctl.size == 0:
        raise ValueError("hacen falta pares con mensaje y controles")
    punto = float(np.exp(ln_con.mean() - ln_ctl.mean()))
    rng = np.random.default_rng(semilla)
    n_con, n_ctl = ln_con.size, ln_ctl.size
    boots = np.empty(B, dtype=float)
    for i in range(B):
        muestra_con = ln_con[rng.integers(0, n_con, n_con)]
        muestra_ctl = ln_ctl[rng.integers(0, n_ctl, n_ctl)]
        boots[i] = np.exp(muestra_con.mean() - muestra_ctl.mean())
    lo, hi = np.percentile(boots, [100 * alfa / 2, 100 * (1 - alfa / 2)])
    return {"punto": punto, "ic95": [float(lo), float(hi)]}


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


def _fecha(ms) -> str:
    """El dia (YYYY-MM-DD, en `ZONA_DE_LA_SESION`) de un instante del
    formulario en ms."""
    if not ms:
        return "—"
    return datetime.datetime.fromtimestamp(ms / 1000, tz=ZONA_DE_LA_SESION).strftime("%Y-%m-%d")


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


def frente_a_umbrales(k: dict) -> dict | None:
    """El kappa frente al 0,4 de la Semana 1 y el 0,6 (spec §5.5, §11.4):
    la estimacion puntual y el limite inferior de cada intervalo. None si el
    kappa no es calculable.

    Se compara a seis decimales (`_a_seis`): con 24 casos un kappa es un
    racional que puede valer EXACTAMENTE 0,4 o 0,6, y la coma flotante lo
    deja en 0,3999999999999999. Eso alcanza el umbral."""
    if k["kappa"] is None or math.isnan(k["kappa"]):
        return None
    return {"puntual_ge_0_4": bool(_a_seis(k["kappa"]) >= 0.4),
            "puntual_ge_0_6": bool(_a_seis(k["kappa"]) >= 0.6),
            "li_analitico_lt_0_4": bool(_a_seis(k["ic95"][0]) < 0.4),
            "li_bca_lt_0_4": bool(_a_seis(k["ic95_bca"][0]) < 0.4)}


def _con_umbrales(k: dict) -> dict:
    k["frente_a_umbrales"] = frente_a_umbrales(k)
    return k


def _problemas_de_las_lecturas(clave: dict, casos: dict, lectura1: list,
                               lectura2: list | None, planb: list | None) -> list:
    """Lo que impide analizar: la columna `lectura` que no toca (ficheros
    cambiados, el mismo CSV dos veces), casos que faltan o se repiten, y
    controles que no son los de la clave (restriccion 8: el kappa sale solo
    de la lectura 1). Todas las filas de practica quedan fuera."""
    problemas = []
    l1 = _sin_practica(lectura1)
    otras = sorted({str(f["lectura"]) for f in l1} - {"1"})
    if otras:
        problemas.append(f"la lectura 1 lleva filas de la lectura {', '.join(otras)} "
                         f"(¿ficheros cambiados?)")
    ids = [f["id"] for f in l1]
    if len(ids) != len(casos) or set(ids) != set(casos):
        problemas.append(f"la lectura 1 tiene {len(ids)} filas para {len(casos)} casos, "
                         f"o ids que no son los de la clave")
    if lectura2 is not None:
        l2 = _sin_practica(lectura2)
        otras = sorted({str(f["lectura"]) for f in l2} - {"2"})
        if otras:
            problemas.append(f"la lectura 2 lleva filas de la lectura {', '.join(otras)} "
                             f"(¿ficheros cambiados, o el mismo CSV dos veces?)")
        ids2 = [f["id"] for f in l2]
        repetidos = sorted({i for i in ids2 if ids2.count(i) > 1})
        if repetidos:
            problemas.append(f"la lectura 2 repite {', '.join(repetidos)}")
        if set(ids2) != set(casos):
            problemas.append(f"la lectura 2 no tiene los casos de la clave: faltan "
                             f"{len(set(casos) - set(ids2))} y sobran {len(set(ids2) - set(casos))}")
        controles = {f["id"] for f in l2 if f["control"]}
        if controles != set(clave["ordenes"]["controles"]):
            problemas.append(f"los controles de la lectura 2 ({', '.join(sorted(controles)) or 'ninguno'}) "
                             f"no son los de la clave")
    if planb is not None:
        pb = _sin_practica(planb)
        if any(str(f["lectura"]) != "1" for f in pb):
            problemas.append("el plan B lleva filas que no son de la lectura 1")
        sin_respuesta = [f["id"] for f in pb if not f["banda_con"]]
        if sin_respuesta:
            problemas.append(f"el plan B no tiene la respuesta con el mensaje en "
                             f"{len(sin_respuesta)} filas")
    return problemas


def analizar(clave: dict, lectura1: list, lectura2: list | None = None,
             planb: list | None = None, huellas: dict | None = None) -> dict:
    """De los CSV y la clave DEFINITIVA (la de `--fase mensajes`) a la
    estructura de `sesion.json`. `huellas`, si se pasa, son los sha256 de
    `corpus/mensajes.json` y `clave.json` que el acta cita."""
    casos = {c["patientId"]: c for c in clave["casos"]}
    if any("categoria" not in c or "bloque" not in c for c in casos.values()):
        raise ValueError("la clave no es la definitiva: corre --fase mensajes antes de analizar")
    faltan = [k for k in ("origen_mensajes", "prevalencia_sesion") if k not in clave]
    if faltan:
        raise ValueError(f"la clave no lleva {' ni '.join(faltan)}: corre --fase mensajes "
                         f"antes de analizar")
    problemas = _problemas_de_las_lecturas(clave, casos, lectura1, lectura2, planb)
    if problemas:
        raise ValueError("las lecturas no sirven para analizar:\n  " + "\n  ".join(problemas))
    # La categoria y la horquilla son las del bloque DEL MENSAJE (D3).
    clave_cat, clave_bloque = "categoria", "bloque"

    l1 = _sin_practica(lectura1)
    ids = [f["id"] for f in l1]
    sistema = [casos[i][clave_cat]["primaria"] for i in ids]
    medico = [f["banda"] for f in l1]
    pct = [f["porcentaje"] for f in l1]

    kappas = {"ponderado_lineal": _con_umbrales(kappa_con_intervalos(sistema, medico, "lineal")),
              "cohen": _con_umbrales(kappa_con_intervalos(sistema, medico, "ninguno")),
              "binario_alta": _con_umbrales(kappa_con_intervalos(sistema, medico, "binario_alta"))}
    sensibilidad = {v: kappa(indices([casos[i][clave_cat][v] for i in ids]), indices(medico), 3, "lineal")["kappa"]
                    for v in ("independencia", "conservador", "cruza")}
    n_cruzan = sum(bool(casos[i][clave_cat]["cruza_limite"]) for i in ids)
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
    # El dia de cada lectura: el de la primera fila (la primera practica).
    if planb is not None:
        fechas = {"sesion_unica": _fecha(lectura1[0]["abierto_en"])}
    elif lectura2 is not None:
        fechas = {"lectura1": _fecha(lectura1[0]["abierto_en"]),
                  "lectura2": _fecha(lectura2[0]["abierto_en"])}
    else:
        fechas = {"lectura1": _fecha(lectura1[0]["abierto_en"])}

    salida = {"rotulo": clave.get("rotulo", "simulación semisintética — sesión H7"),
              "n": len(ids), "fechas": fechas,
              "prevalencia_sesion": clave["prevalencia_sesion"],
              "origen_mensajes": clave["origen_mensajes"], "huellas": huellas,
              "kappa": kappas,
              "sensibilidad_categoria": sensibilidad, "n_cruzan_un_limite": n_cruzan,
              "acuerdo_continuo": acuerdo,
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
        if razones_c:
            ln_con = np.log([f["segundos"] / t1[f["id"]] for f in con])
            ln_ctl = np.log(razones_c)
            rc = razon_corregida(ln_con, ln_ctl)
            tiempo["razon_corregida_por_releer"] = rc["punto"]
            tiempo["ic95_razon_corregida"] = rc["ic95"]
        else:
            tiempo["razon_corregida_por_releer"] = None
            tiempo["ic95_razon_corregida"] = None
        tiempo["medido"] = True
        salida["lectura2"] = {
            "n_con_mensaje": len(con), "n_controles": len(controles),
            "kappa_con_mensaje": _con_umbrales(kappa_con_intervalos(
                [casos[f["id"]][clave_cat]["primaria"] for f in con], [f["banda"] for f in con], "lineal")),
            "cambios_de_banda": sum(f["banda"] != medico1[f["id"]] for f in con),
            "utilidad": _notas(con), "tiempo": tiempo}

    if planb is not None:
        pb = _sin_practica(planb)
        salida["plan_b"] = {
            "tiempo_medido": False,
            "segundos_adicionales_leer_mensaje": {
                "mediana": float(statistics.median([f["segundos_con"] for f in pb if f["segundos_con"] is not None])),
                "n": sum(f["segundos_con"] is not None for f in pb)},
            "kappa_con_mensaje": _con_umbrales(kappa_con_intervalos(
                [casos[f["id"]][clave_cat]["primaria"] for f in pb], [f["banda_con"] for f in pb], "lineal")),
            "cambios_de_banda": sum(f["banda_con"] != f["banda"] for f in pb),
            "utilidad": _notas(pb)}
    return salida


# --------------------------------------------------------------------------
# El acta
# --------------------------------------------------------------------------
def _f(x, decimales=2):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    texto = f"{x:.{decimales}f}"
    if float(texto) == 0:
        # un cero con residuo de coma flotante (−5e-16) no es «-0,00»
        texto = texto.lstrip("-")
    return texto.replace(".", ",")


def _kappa_texto(k: dict) -> str:
    """Un kappa y sus dos intervalos, en una linea. Las cifras van con
    `_f_frente_a_umbral`, como en la frase del criterio y en «Observado»: en
    el acta, el mismo limite se lee igual en las tres."""
    f = _f_frente_a_umbral
    return (f"{f(k['kappa'])} (IC 95 % analítico {f(k['ic95'][0])} a {f(k['ic95'][1])}; "
            f"BCa {f(k['ic95_bca'][0])} a {f(k['ic95_bca'][1])}; n = {k['n']})")


def _pct_como_el_bot(x: float) -> str:
    """Un extremo de la horquilla como lo imprime Desenlace: entero con
    Math.round (`porcentaje_entero`), y nunca 0 % ni 100 %. Las cotas son las
    de `_entero_como_el_bot`: estan escritas una sola vez."""
    entero = _entero_como_el_bot(x)
    return {0: "< 1 %", 100: "> 99 %"}.get(entero, f"{entero} %")


def _horquilla_como_el_bot(minima: float, maxima: float) -> str:
    """La horquilla con la convencion de Desenlace: un solo valor si los dos
    extremos se imprimen igual, y las cotas en palabras dentro de un rango."""
    lo, hi = _pct_como_el_bot(minima), _pct_como_el_bot(maxima)
    if lo == hi:
        return lo
    palabras = {"< 1 %": "menos de 1 %", "> 99 %": "más de 99 %"}
    return f"entre {palabras.get(lo, lo)} y {palabras.get(hi, hi)}"


UMBRALES_KAPPA = (0.4, 0.6)
_DECIMALES_MAXIMOS = 6


def _a_seis(x: float) -> float:
    """Un kappa a seis decimales, que es con lo que se compara con los
    umbrales y lo mas que se imprime: lo que a seis decimales es el umbral, es
    el umbral."""
    return round(x, _DECIMALES_MAXIMOS)


def _f_frente_a_umbral(x) -> str:
    """Un kappa, o un limite de su intervalo, para cualquier linea del acta que
    lo imprima: la frase que lo compara con 0,4 y 0,6, la linea del kappa y
    «Observado». Asi el mismo valor se lee igual en todas. Si los dos
    decimales de siempre dieran justo un umbral sin que el valor lo sea
    (0,3996 → «0,40»), la frase se contradiria; entonces se imprime con tres
    decimales, y con los que hagan falta (hasta seis) si tres aun dan el
    umbral. Un valor que a seis decimales ES el umbral se imprime como el
    umbral, y `frente_a_umbrales` lo trata igual."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return _f(x)
    for umbral in UMBRALES_KAPPA:
        if _a_seis(x) != umbral and round(x, 2) == umbral:
            for decimales in range(3, _DECIMALES_MAXIMOS + 1):
                if round(x, decimales) != umbral:
                    break
            return _f(x, decimales)
    return _f(x)


NOMBRES_KAPPA = {"ponderado_lineal": "El kappa ponderado", "cohen": "El kappa de Cohen",
                 "binario_alta": "El kappa binario en «alta»"}


def _criterio(nombre: str, k: dict) -> str:
    """Una frase: el kappa frente a 0,4 y 0,6, y su limite inferior frente a
    0,4 con los dos intervalos (spec §5.5, §11.4), desde `frente_a_umbrales`.
    Las cifras van con `_f_frente_a_umbral`, para que no contradigan la frase."""
    u = k.get("frente_a_umbrales")
    if u is None:
        return f"{nombre} no es calculable con estas lecturas."
    if not u["puntual_ge_0_4"]:
        alcance = "no alcanza el mínimo de 0,4 de la Semana 1"
    elif not u["puntual_ge_0_6"]:
        alcance = "alcanza el mínimo de 0,4 de la Semana 1 y no el objetivo de 0,6"
    else:
        alcance = "alcanza el mínimo de 0,4 de la Semana 1 y el objetivo de 0,6"
    la, lb = _f_frente_a_umbral(k["ic95"][0]), _f_frente_a_umbral(k["ic95_bca"][0])
    if u["li_analitico_lt_0_4"] and u["li_bca_lt_0_4"]:
        limite = f"queda por debajo de 0,4 con los dos métodos (analítico {la}; BCa {lb})"
    elif u["li_analitico_lt_0_4"]:
        limite = f"queda por debajo de 0,4 con el método analítico ({la}) y no con el BCa ({lb})"
    elif u["li_bca_lt_0_4"]:
        limite = f"queda por debajo de 0,4 con el BCa ({lb}) y no con el método analítico ({la})"
    else:
        # «no queda por debajo», y no «queda por encima»: un limite que ES
        # 0,4 llega aqui, y por encima no esta
        limite = (f"no queda por debajo de 0,4 con ninguno de los dos métodos "
                  f"(analítico {la}; BCa {lb})")
    return (f"{nombre} ({_f_frente_a_umbral(k['kappa'])}) {alcance}; "
            f"el límite inferior del intervalo {limite}.")


METODOS = (("ic95", "el método analítico"), ("ic95_bca", "el BCa"))


def _anchura_observada(k: dict) -> str:
    """Lo que el intervalo del kappa ponderado dio EN ESTA SESION, para
    ponerlo al lado del texto declarado antes de ella: sus limites y su
    anchura por los dos metodos, y si 0,4 y 0,6 quedan dentro.

    Los limites se IMPRIMEN como en la frase del criterio y en la linea del
    kappa, que estan mas arriba en el acta: con `_f_frente_a_umbral` sobre el
    limite tal como se calculo (redondearlo antes a seis decimales puede
    cambiarle la segunda cifra: 0,5750004 es «0,58» y 0,575, «0,57»). Se
    COMPARAN con los umbrales a seis decimales, como `frente_a_umbrales`. Asi
    las tres lineas dicen lo mismo del mismo limite. La anchura es la resta
    de los limites tal como se imprimen, hecha en decimal y con el ,5 hacia
    arriba: «de 0,395 a 0,95» mide 0,555, que es «0,56»."""
    if k.get("frente_a_umbrales") is None:
        return "el kappa ponderado no es calculable con estas lecturas, y su intervalo tampoco."
    crudos = {nombre: list(k[clave]) for clave, nombre in METODOS}
    limites = {nombre: [_a_seis(x) for x in par] for nombre, par in crudos.items()}

    def impreso(x) -> decimal.Decimal:
        return decimal.Decimal(_f_frente_a_umbral(x).replace(",", "."))

    def anchura(li, ls) -> str:
        resta = (impreso(ls) - impreso(li)).quantize(
            decimal.Decimal("0.01"), rounding=decimal.ROUND_HALF_UP)
        return str(resta).replace(".", ",")

    va = " y ".join(
        f"de {_f_frente_a_umbral(li)} a {_f_frente_a_umbral(ls)} con {nombre} "
        f"(anchura {anchura(li, ls)})"
        for nombre, (li, ls) in crudos.items())

    def dentro(umbral):
        return [nombre for nombre, (li, ls) in limites.items() if li <= umbral <= ls]

    def frase(umbrales):
        sujeto = " y ".join(f"el {_f(u, 1)}" for u in umbrales)
        queda = "queda" if len(umbrales) == 1 else "quedan"
        con = dentro(umbrales[0])
        sin = [nombre for nombre in limites if nombre not in con]
        if not sin:
            return f"{sujeto} {queda} dentro con los dos métodos"
        if not con:
            return f"{sujeto} {queda} fuera con los dos métodos"
        return f"{sujeto} {queda} dentro con {con[0]} y fuera con {sin[0]}"

    bajo, alto = UMBRALES_KAPPA
    lectura = (frase((bajo, alto)) if dentro(bajo) == dentro(alto)
               else f"{frase((bajo,))} y {frase((alto,))}")
    return f"el intervalo del 95 % del kappa ponderado va {va}; {lectura}."


def _dentro_de_la_horquilla(a: dict) -> str:
    """«7 de 24 casos (29 %)»: el recuento, y el porcentaje con la regla del
    bot (el ,5 hacia arriba), como el resto del acta."""
    if "dentro_de_la_horquilla" not in a or not a["n"]:
        return "—"
    dentro, n = a["dentro_de_la_horquilla"], a["n"]
    return f"{dentro} de {_plural(n, 'caso', 'casos')} ({porcentaje_entero(dentro / n)} %)"


ESTRATOS_LEGIBLES = {"positiva_clara": "positiva clara", "negativa_clara": "negativa clara",
                     "banda_contradictoria": "banda contradictoria", "asma_no_se": "asma «no sé»"}
NOTAS_LEGIBLES = {"correccion": "corrección", "utilidad": "utilidad", "lenguaje": "lenguaje"}
SENSIBILIDAD_LEGIBLE = {"independencia": "extremo de independencia",
                        "conservador": "extremo conservador",
                        "cruza": "«si cruza un límite, intermedia»"}


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _celda(x) -> str:
    """Una celda de tabla Markdown: `|` escapada y los saltos de linea como « / »."""
    texto = str(x).replace("|", "\\|")
    return " / ".join(t.strip() for t in texto.replace("\r\n", "\n").replace("\r", "\n").split("\n"))


def _origen(o: dict) -> str:
    if o.get("con_bots"):
        return "con bots contra el sistema desplegado"
    return f"con la imagen local del tag {o.get('imagen_tag')}, digest {o.get('imagen_digest')}"


def _huellas(h: dict | None) -> str:
    if not h:
        return "sin huellas (el análisis no recibió los ficheros de la sesión)"
    return f"sha256 de mensajes.json `{h['mensajes_json']}` y de clave.json `{h['clave_json']}`"


def valores_para_acta(sesion: dict, clave: dict) -> dict:
    """Los valores que rellenan la plantilla. Ninguno se teclea: salen de
    `sesion.json` (cifras, fechas, prevalencia, origen de los mensajes y
    huellas) y de la clave (la tabla de casos)."""
    k = sesion["kappa"]
    casos = "\n".join(f"| {c['patientId']} | {ESTRATOS_LEGIBLES.get(c['estrato'], c['estrato'])} | "
                      f"{'concordante' if c['concordante'] else 'discordante'} |"
                      for c in clave["casos"])
    desacuerdos = "\n".join(
        "| " + " | ".join(_celda(x) for x in (
            d["id"], ESTRATOS_LEGIBLES.get(d["estrato"], d["estrato"]), d["sistema"],
            f"{d['medico']} ({d['porcentaje']} %)", _horquilla_como_el_bot(*d["horquilla"]),
            d["comentario"])) + " |"
        for d in sesion["desacuerdos"]) or "| (ninguno) | | | | | |"
    dias = sesion["fechas"]
    fecha1 = dias.get("lectura1") or dias.get("sesion_unica") or "—"
    fecha2 = dias.get("lectura2") or "—"
    l2 = sesion.get("lectura2")
    pb = sesion.get("plan_b")
    if l2:
        t = l2["tiempo"]
        r = t["razon_medias_geometricas"]
        cambio = (f"aumento del {_f((r - 1.0) * 100.0, 0)} %" if r > 1.0
                  else f"reducción del {_f(t['reduccion_pct'], 0)} %")
        ic_corregida = t.get("ic95_razon_corregida")
        corregida = (f"{_f(t['razon_corregida_por_releer'])} (IC 95 % {_f(ic_corregida[0])} a {_f(ic_corregida[1])})"
                     if ic_corregida else _f(t["razon_corregida_por_releer"]))
        tiempo = (f"razón de medias geométricas con/sin {_f(r)} "
                  f"(IC 95 % BCa {_f(t['ic95_bca'][0])} a {_f(t['ic95_bca'][1])}; n = {t['n']}), "
                  f"{cambio}; controles releídos sin copiloto: "
                  f"media geométrica {_f(t['controles']['media_geometrica'])} (n = {t['controles']['n']}); "
                  f"razón corregida por releer {corregida}. El cambio medido mezcla "
                  f"el efecto del copiloto con el de releer; los controles estiman el de releer "
                  f"de forma descriptiva")
        razones_controles = ("; ".join(_f(x) for x in t["controles"]["razones"])
                             or "no hubo controles en la lectura 2")
        influencia = (f"kappa con el mensaje delante {_kappa_texto(l2['kappa_con_mensaje'])}; "
                      f"cambió de banda en {l2['cambios_de_banda']} de "
                      f"{_plural(l2['n_con_mensaje'], 'caso', 'casos')}")
        u = l2["utilidad"]
        fechas = f"lectura 1 el {fecha1}; lectura 2 el {fecha2}"
        metodo = (f"Dos lecturas del mismo conjunto: la primera sin copiloto (placa y viñeta; banda y "
                  f"porcentaje) el {fecha1}; la segunda, con el mensaje real del sistema en "
                  f"{_plural(l2['n_con_mensaje'], 'caso', 'casos')} y "
                  f"{_plural(l2['n_controles'], 'control', 'controles')} sin mensaje, el {fecha2}. "
                  f"El kappa sale solo de la primera.")
    elif pb:
        tiempo = (f"no medido (plan B, una sola sesión); leer el mensaje añadió una mediana de "
                  f"{_f(pb['segundos_adicionales_leer_mensaje']['mediana'], 0)} s por caso")
        razones_controles = "no hay controles en el plan B"
        influencia = (f"kappa tras revelar el mensaje {_kappa_texto(pb['kappa_con_mensaje'])}; "
                      f"cambió de banda en {pb['cambios_de_banda']} de "
                      f"{_plural(pb['kappa_con_mensaje']['n'], 'caso', 'casos')}")
        u = pb["utilidad"]
        fechas = f"sesión única el {fecha1}"
        metodo = (f"Una sola sesión el {fecha1}, en lectura secuencial caso a caso: primero banda, "
                  f"porcentaje y tiempo sin ayuda; después el formulario reveló el mensaje y pidió "
                  f"banda final, porcentaje final y las tres notas. El kappa sale de la primera "
                  f"respuesta; la reducción del tiempo no se midió.")
    else:
        tiempo = "no medido"
        razones_controles = "no hay controles (solo la lectura sin copiloto)"
        influencia = "no medida"
        u = None
        fechas = f"lectura el {fecha1}"
        metodo = f"Solo la lectura sin copiloto, el {fecha1}."
    utilidad = ("; ".join(f"{NOTAS_LEGIBLES[n]} {_f(u[n]['media'], 1)} (n = {u[n]['n']})" for n in NOTAS)
                if u else "no medida")
    a = sesion["acuerdo_continuo"]
    return {
        "rotulo": sesion["rotulo"], "n": str(sesion["n"]),
        "fechas": fechas, "metodo": metodo,
        "prevalencia_sesion": _f(sesion["prevalencia_sesion"], 4),
        "origen_mensajes": _origen(sesion["origen_mensajes"]),
        "kappa_ponderado": _kappa_texto(k["ponderado_lineal"]),
        "kappa_cohen": _kappa_texto(k["cohen"]),
        "kappa_binario": _kappa_texto(k["binario_alta"]),
        "criterio_kappa": " ".join(_criterio(NOMBRES_KAPPA[v], k[v]) for v in NOMBRES_KAPPA),
        "sensibilidad": "; ".join(f"{SENSIBILIDAD_LEGIBLE.get(v, v)} {_f(x)}"
                                  for v, x in sesion["sensibilidad_categoria"].items()),
        "n_cruzan_un_limite": str(sesion["n_cruzan_un_limite"]),
        "razones_controles": razones_controles,
        "huellas": _huellas(sesion.get("huellas")),
        "spearman": _f(a["spearman"]), "bland_altman": f"{_f(a['diferencia_media_log_odds'])} (DE {_f(a['de'])})",
        "dentro_horquilla": _dentro_de_la_horquilla(a),
        "horquillas_anchura_cero": str(a.get("horquillas_de_anchura_cero", "—")),
        "horquillas_cota": str(a.get("horquillas_que_son_una_cota", "—")),
        "acotados": str(a["acotados_0_o_100"]),
        "sistema_fuera": str(a["sistema_fuera_de_la_cota"]),
        "anchura_observada": _anchura_observada(k["ponderado_lineal"]),
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
