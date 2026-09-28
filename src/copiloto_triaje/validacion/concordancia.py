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
def acuerdo_continuo(pct_medico, p_sistema, minima=None, maxima=None) -> dict:
    """Spearman entre el porcentaje del medico y el punto medio del sistema;
    Bland-Altman en log-odds con 0 y 100 acotados a 0,5 y 99,5; y la fraccion
    de porcentajes que caen dentro de la horquilla.

    «Dentro» compara el porcentaje entero del medico, SIN acotar, con la
    horquilla tal como la imprime el bot: `porcentaje_entero` de la minima y
    de la maxima (Math.round en Desenlace). Una horquilla de un solo valor
    (los discordantes con el asma conocida) solo admite ese entero, y se
    cuentan aparte para que el acta lo diga."""
    pct = np.asarray(pct_medico, dtype=float)
    p = np.asarray(p_sistema, dtype=float)
    acotados = int(np.sum((pct <= 0) | (pct >= 100)))
    pm = np.clip(pct, 0.5, 99.5) / 100.0
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
              "acotados_0_o_100": acotados}
    if minima is not None and maxima is not None:
        lo = np.array([porcentaje_entero(x) for x in minima], dtype=int)
        hi = np.array([porcentaje_entero(x) for x in maxima], dtype=int)
        dentro = (pct >= lo) & (pct <= hi)
        salida["fraccion_dentro_de_la_horquilla"] = float(dentro.mean())
        salida["horquillas_de_anchura_cero"] = int(np.sum(lo == hi))
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
    kappa no es calculable."""
    if k["kappa"] is None or math.isnan(k["kappa"]):
        return None
    return {"puntual_ge_0_4": bool(k["kappa"] >= 0.4), "puntual_ge_0_6": bool(k["kappa"] >= 0.6),
            "li_analitico_lt_0_4": bool(k["ic95"][0] < 0.4),
            "li_bca_lt_0_4": bool(k["ic95_bca"][0] < 0.4)}


def _con_umbrales(k: dict) -> dict:
    k["frente_a_umbrales"] = frente_a_umbrales(k)
    return k


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

    salida = {"rotulo": clave.get("rotulo", "simulación semisintética — sesión H7"),
              "n": len(ids), "categoria_de": categoria_de, "kappa": kappas,
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
    return f"{x:.{decimales}f}".replace(".", ",")


def _kappa_texto(k: dict) -> str:
    return (f"{_f(k['kappa'])} (IC 95 % analítico {_f(k['ic95'][0])} a {_f(k['ic95'][1])}; "
            f"BCa {_f(k['ic95_bca'][0])} a {_f(k['ic95_bca'][1])}; n = {k['n']})")


def _fecha(ms):
    import datetime
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d") if ms else "—"


def _pct_como_el_bot(x: float) -> str:
    """Un extremo de la horquilla como lo imprime Desenlace: entero con
    Math.round (`porcentaje_entero`), y nunca 0 % ni 100 %."""
    if x < 0.01:
        return "< 1 %"
    if x > 0.99:
        return "> 99 %"
    return f"{porcentaje_entero(x)} %"


def _horquilla_como_el_bot(minima: float, maxima: float) -> str:
    """La horquilla con la convencion de Desenlace: un solo valor si los dos
    extremos se imprimen igual, y las cotas en palabras dentro de un rango."""
    lo, hi = _pct_como_el_bot(minima), _pct_como_el_bot(maxima)
    if lo == hi:
        return lo
    palabras = {"< 1 %": "menos de 1 %", "> 99 %": "más de 99 %"}
    return f"entre {palabras.get(lo, lo)} y {palabras.get(hi, hi)}"


NOMBRES_KAPPA = {"ponderado_lineal": "El kappa ponderado", "cohen": "El kappa de Cohen",
                 "binario_alta": "El kappa binario en «alta»"}


def _criterio(nombre: str, k: dict) -> str:
    """Una frase: el kappa frente a 0,4 y 0,6, y su limite inferior frente a
    0,4 con los dos intervalos (spec §5.5, §11.4), desde `frente_a_umbrales`."""
    u = k.get("frente_a_umbrales")
    if u is None:
        return f"{nombre} no es calculable con estas lecturas."
    if not u["puntual_ge_0_4"]:
        alcance = "no alcanza el mínimo de 0,4 de la Semana 1"
    elif not u["puntual_ge_0_6"]:
        alcance = "alcanza el mínimo de 0,4 de la Semana 1 y no el objetivo de 0,6"
    else:
        alcance = "alcanza el mínimo de 0,4 de la Semana 1 y el objetivo de 0,6"
    la, lb = _f(k["ic95"][0]), _f(k["ic95_bca"][0])
    if u["li_analitico_lt_0_4"] and u["li_bca_lt_0_4"]:
        limite = f"queda por debajo de 0,4 con los dos métodos (analítico {la}; BCa {lb})"
    elif u["li_analitico_lt_0_4"]:
        limite = f"queda por debajo de 0,4 con el método analítico ({la}) y no con el BCa ({lb})"
    elif u["li_bca_lt_0_4"]:
        limite = f"queda por debajo de 0,4 con el BCa ({lb}) y no con el método analítico ({la})"
    else:
        limite = f"queda por encima de 0,4 con los dos métodos (analítico {la}; BCa {lb})"
    return f"{nombre} ({_f(k['kappa'])}) {alcance}; el límite inferior del intervalo {limite}."


def valores_para_acta(sesion: dict, clave: dict, lectura1: list | None = None,
                      lectura2: list | None = None) -> dict:
    """Los valores que rellenan la plantilla. Ninguno se teclea: salen de
    `sesion.json` y de la clave."""
    k = sesion["kappa"]
    casos = "\n".join(f"| {c['patientId']} | {c['estrato']} | {'concordante' if c['concordante'] else 'discordante'} |"
                      for c in clave["casos"])
    desacuerdos = "\n".join(
        f"| {d['id']} | {d['estrato']} | {d['sistema']} | {d['medico']} ({d['porcentaje']} %) | "
        f"{_horquilla_como_el_bot(*d['horquilla'])} | {d['comentario']} |"
        for d in sesion["desacuerdos"]) or "| (ninguno) | | | | | |"
    fecha1 = _fecha(lectura1[0]["abierto_en"]) if lectura1 else "—"
    fecha2 = _fecha(lectura2[0]["abierto_en"]) if lectura2 else "—"
    l2 = sesion.get("lectura2")
    pb = sesion.get("plan_b")
    if l2:
        t = l2["tiempo"]
        ic_corregida = t.get("ic95_razon_corregida")
        corregida = (f"{_f(t['razon_corregida_por_releer'])} (IC 95 % {_f(ic_corregida[0])} a {_f(ic_corregida[1])})"
                     if ic_corregida else _f(t["razon_corregida_por_releer"]))
        tiempo = (f"razón de medias geométricas con/sin {_f(t['razon_medias_geometricas'])} "
                  f"(IC 95 % BCa {_f(t['ic95_bca'][0])} a {_f(t['ic95_bca'][1])}; n = {t['n']}), "
                  f"reducción {_f(t['reduccion_pct'], 0)} %; controles releídos sin copiloto: "
                  f"media geométrica {_f(t['controles']['media_geometrica'])} (n = {t['controles']['n']}); "
                  f"razón corregida por releer {corregida}. La reducción mezcla "
                  f"el efecto del copiloto con el de releer; los controles lo estiman de forma descriptiva.")
        influencia = (f"kappa con el mensaje delante {_kappa_texto(l2['kappa_con_mensaje'])}; "
                      f"cambió de banda en {l2['cambios_de_banda']} de {l2['n_con_mensaje']} casos")
        u = l2["utilidad"]
        fechas = f"lectura 1 el {fecha1}; lectura 2 el {fecha2}"
        metodo = (f"Dos lecturas del mismo conjunto: la primera sin copiloto el {fecha1}; la segunda, "
                  f"con el mensaje real del sistema en {l2['n_con_mensaje']} casos y {l2['n_controles']} "
                  f"controles sin mensaje, el {fecha2}. El kappa sale solo de la primera.")
    elif pb:
        tiempo = (f"no medido (plan B, una sola sesión); leer el mensaje añadió una mediana de "
                  f"{_f(pb['segundos_adicionales_leer_mensaje']['mediana'], 0)} s por caso")
        influencia = (f"kappa tras revelar el mensaje {_kappa_texto(pb['kappa_con_mensaje'])}; "
                      f"cambió de banda en {pb['cambios_de_banda']} de {pb['kappa_con_mensaje']['n']} casos")
        u = pb["utilidad"]
        fechas = f"sesión única el {fecha1}"
        metodo = (f"Una sola sesión el {fecha1}, en lectura secuencial caso a caso: primero banda, "
                  f"porcentaje y tiempo sin ayuda; después el formulario reveló el mensaje y pidió "
                  f"banda final, porcentaje final y las tres notas. El kappa sale de la primera "
                  f"respuesta; la reducción del tiempo no se midió.")
    else:
        tiempo = "no medido"
        influencia = "no medida"
        u = None
        fechas = f"lectura el {fecha1}"
        metodo = f"Solo la lectura sin copiloto, el {fecha1}."
    utilidad = ("; ".join(f"{n} {_f(u[n]['media'], 1)} (n = {u[n]['n']})" for n in NOTAS) if u else "no medida")
    a = sesion["acuerdo_continuo"]
    return {
        "rotulo": sesion["rotulo"], "n": str(sesion["n"]),
        "fechas": fechas, "metodo": metodo,
        "prevalencia_sesion": _f(clave.get("prevalencia_sesion"), 4),
        "categoria_de": sesion["categoria_de"],
        "kappa_ponderado": _kappa_texto(k["ponderado_lineal"]),
        "kappa_cohen": _kappa_texto(k["cohen"]),
        "kappa_binario": _kappa_texto(k["binario_alta"]),
        "criterio_kappa": " ".join(_criterio(NOMBRES_KAPPA[v], k[v]) for v in NOMBRES_KAPPA),
        "sensibilidad": "; ".join(f"{v} {_f(x)}" for v, x in sesion["sensibilidad_categoria"].items()),
        "n_cruzan_un_limite": str(sesion["n_cruzan_un_limite"]),
        "spearman": _f(a["spearman"]), "bland_altman": f"{_f(a['diferencia_media_log_odds'])} (DE {_f(a['de'])})",
        "dentro_horquilla": _f(a.get("fraccion_dentro_de_la_horquilla", float("nan")) * 100, 0),
        "horquillas_anchura_cero": str(a.get("horquillas_de_anchura_cero", "—")),
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
