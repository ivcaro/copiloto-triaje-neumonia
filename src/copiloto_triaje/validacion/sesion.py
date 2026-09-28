# -*- coding: utf-8 -*-
"""La seleccion de casos, las viñetas y los ordenes de la sesion con el medico
(spec de SP5 §5.1, §5.3, §5.4). Puro: no lee ni escribe ficheros.

Estratos deliberados y, dentro de cada uno, mitad con clinica concordante y
mitad discordante segun el propio bloque `combinacion` del sistema, para que
el kappa no lo inflen los casos faciles. La clinica sale del generador con
(ρ1, ρ0) = RHO_SESION: ni independiente de la placa (viñetas incoherentes) ni
copia de ella. Los sintomas referidos son un fondo constante salvo la fiebre,
que sigue a la temperatura medida, y el asma, que sale del generador.
"""
from __future__ import annotations

import numpy as np

from copiloto_triaje.servicio.heckerling import TEMPERATURA_CORTE_C, combinacion

from .categoria import categoria_del_sistema
from .generador import SIGNOS, hallazgos, sortear_caso
from .oraculo import Modelo

UMBRAL_CRIBADO = 0.4258        # el desplegado (`/salud` -> umbral); prueba contra seleccionar_casos.UMBRAL
RV_POSITIVA_CLARA = 5.0
RV_NEGATIVA_CLARA = 0.2
ESTRATOS = ("positiva_clara", "negativa_clara", "banda_contradictoria", "asma_no_se")
# Casos por estrato Y por concordancia: 4+4, 4+4, 2+2, 2+2 = 24.
CUOTA = {"positiva_clara": 4, "negativa_clara": 4,
         "banda_contradictoria": 2, "asma_no_se": 2}
PRACTICA = ("positiva_clara", "negativa_clara", "banda_contradictoria")
RHO_SESION = (0.3, 0.3)
# Los de `pruebas/reproducir_casos.SINTOMAS`, salvo la fiebre y el asma.
SINTOMAS_FIJOS = {"tos": "con_flema", "dias_evolucion": "3_a_7", "disnea": "no",
                  "dolor_toracico": "si", "texto_libre": None}
SEXO = {"F": "femenino", "M": "masculino"}


def estratos(df, rv) -> dict:
    """Indices candidatos por estrato, sobre las crudas congeladas."""
    etiqueta = df["etiqueta"].values
    cruda = df["cruda"].values
    rv = np.asarray(rv, dtype=float)
    return {
        "positiva_clara": np.flatnonzero((etiqueta == 1) & (rv >= RV_POSITIVA_CLARA)),
        "negativa_clara": np.flatnonzero((etiqueta == 0) & (rv <= RV_NEGATIVA_CLARA)),
        "banda_contradictoria": np.flatnonzero((cruda >= UMBRAL_CRIBADO) & (rv < 1.0)),
        "asma_no_se": np.arange(len(df)),
    }


def sintomas_de(h: dict) -> dict:
    """Los siete campos del cuestionario para esta clinica."""
    return {"fiebre": "si" if h["temperatura_c"] > TEMPERATURA_CORTE_C else "no",
            **SINTOMAS_FIJOS, "asma": h["asma"]}


def _caso(df, i, rv_i, h, bloque, estrato) -> dict:
    fila = df.iloc[int(i)]
    return {
        "patientId": str(fila["patientId"]), "estrato": estrato,
        "etiqueta": int(fila["etiqueta"]), "edad": int(fila["edad"]),
        "sexo": str(fila["sexo"]), "vista": str(fila["vista"]),
        "cruda": float(fila["cruda"]), "rv_imagen": float(rv_i),
        "signos": {s: h[s] for s in SIGNOS}, "sintomas": sintomas_de(h),
        "k": int(h["k"]), "asma_real": h["asma_real"],
        "concordante": bool(bloque["concordantes"]),
        "bloque_previsto": bloque,
        "categoria_prevista": categoria_del_sistema(bloque),
    }


def _llenar(df, rv, modelo, prevalencia, rng, indices, usados, estrato, cuota):
    """Recorre `indices` (ya barajados) sorteando clinica hasta llenar `cuota`
    concordantes y `cuota` discordantes. Un candidato cuya concordancia ya
    esta llena se descarta con su clinica: el sorteo es de una sola vez."""
    pendientes = {True: cuota, False: cuota}
    casos = []
    for i in indices:
        if pendientes[True] == 0 and pendientes[False] == 0:
            break
        if int(i) in usados:
            continue
        h = sortear_caso(modelo, int(i), rng,
                         asma="no_se" if estrato == "asma_no_se" else None)
        bloque = combinacion(prevalencia, hallazgos(h), float(rv[i]))
        if pendientes[bloque["concordantes"]] == 0:
            continue
        pendientes[bloque["concordantes"]] -= 1
        usados.add(int(i))
        casos.append(_caso(df, i, rv[i], h, bloque, estrato))
    if pendientes[True] or pendientes[False]:
        raise RuntimeError(f"no hay candidatos suficientes en {estrato}: faltan {pendientes}")
    return casos


def elegir(df, rv, modelo: Modelo, prevalencia: float, semilla: int):
    """Los 24 casos con sus cuotas y los 3 de practica, reproducibles por semilla."""
    rng = np.random.default_rng(semilla)
    candidatos = estratos(df, rv)
    usados: set = set()
    casos = []
    for estrato in ESTRATOS:
        casos += _llenar(df, rv, modelo, prevalencia, rng,
                         rng.permutation(candidatos[estrato]), usados, estrato,
                         CUOTA[estrato])
    practica = []
    for estrato in PRACTICA:
        for i in rng.permutation(candidatos[estrato]):
            if int(i) in usados:
                continue
            h = sortear_caso(modelo, int(i), rng)
            bloque = combinacion(prevalencia, hallazgos(h), float(rv[i]))
            usados.add(int(i))
            practica.append(_caso(df, i, rv[i], h, bloque, estrato))
            break
    return casos, practica


def _coma(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def vineta(caso: dict) -> str:
    """La viñeta clinica en prosa breve, de usted y con tildes (§5.1)."""
    s, r = caso["signos"], caso["sintomas"]
    fiebre = "Refiere fiebre" if r["fiebre"] == "si" else "No refiere fiebre"
    asma = {"si": "tiene asma", "no": "no tiene asma",
            "no_se": "no sabe si tiene asma"}[r["asma"]]
    return (
        f"Paciente de {caso['edad']} años, sexo {SEXO[caso['sexo']]}; "
        f"radiografía de tórax en proyección {caso['vista']}.\n"
        f"{fiebre}; tos con flema; entre 3 y 7 días de evolución; "
        f"sin disnea; con dolor torácico; {asma}.\n"
        f"Exploración: temperatura {_coma(float(s['temperatura_c']))} °C; "
        f"frecuencia cardíaca {int(s['frecuencia_cardiaca'])} lpm; "
        f"crepitantes: {'sí' if s['crepitantes'] else 'no'}; "
        f"murmullo vesicular: {'disminuido' if s['murmullo_disminuido'] else 'normal'}."
    )


def linea_explorado(signos: dict) -> str:
    """El bloque EXPLORADO que redacta el nodo Desenlace (`redactarSignos`)
    para estos signos. Se usa para comprobar que el mensaje repite la viñeta."""
    return ("EXPLORADO — " + _coma(float(signos["temperatura_c"])) + " °C, "
            + str(int(signos["frecuencia_cardiaca"])) + " lpm, "
            + "crepitantes " + ("sí" if signos["crepitantes"] else "no") + ", "
            + ("murmullo disminuido" if signos["murmullo_disminuido"]
               else "murmullo normal"))


def ordenes(casos, rng: np.random.Generator) -> dict:
    """Los dos ordenes aleatorios y los 4 controles de la lectura 2 (§5.4):
    dos de positivas claras y dos de negativas claras, uno concordante y uno
    discordante en cada uno."""
    ids = [c["patientId"] for c in casos]
    controles = []
    for estrato in ("positiva_clara", "negativa_clara"):
        for concordante in (True, False):
            elegibles = [c["patientId"] for c in casos
                         if c["estrato"] == estrato and c["concordante"] == concordante]
            controles.append(elegibles[int(rng.integers(len(elegibles)))])
    return {"lectura1": [ids[i] for i in rng.permutation(len(ids))],
            "lectura2": [ids[i] for i in rng.permutation(len(ids))],
            "controles": controles}
