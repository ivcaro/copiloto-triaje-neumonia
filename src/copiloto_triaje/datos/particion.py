"""Particion de registros POR PACIENTE, con verificacion de fuga de datos.

Un mismo paciente nunca puede aparecer en dos particiones: si ocurre, el
modelo se evalua sobre datos que ya vio y las metricas dejan de significar
nada. Es el error documentado que invalida al dataset pediatrico de Kermany.
"""
from __future__ import annotations

import random
from collections import defaultdict


class FugaDeDatos(Exception):
    """Un mismo paciente aparece en mas de una particion."""


def particionar_por_paciente(
    registros: list[dict],
    proporciones: tuple[float, float, float],
    semilla: int,
) -> dict[str, list[dict]]:
    """Reparte los registros en train/val/test agrupando por paciente.

    Todas las imagenes de un paciente caen en la misma particion. La
    estratificacion se hace sobre la etiqueta del paciente: es positivo si
    alguno de sus registros lo es.
    """
    total = sum(proporciones)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Las proporciones deben sumar 1, suman {total}")

    por_paciente: dict[str, list[dict]] = defaultdict(list)
    for r in registros:
        por_paciente[r["patientId"]].append(r)

    positivos, negativos = [], []
    for pid, regs in por_paciente.items():
        destino = positivos if any(x["etiqueta"] == 1 for x in regs) else negativos
        destino.append(pid)

    rng = random.Random(semilla)
    resultado: dict[str, list[dict]] = {"train": [], "val": [], "test": []}

    for grupo in (sorted(positivos), sorted(negativos)):
        rng.shuffle(grupo)
        n = len(grupo)
        corte_train = round(n * proporciones[0])
        corte_val = corte_train + round(n * proporciones[1])
        reparto = (
            ("train", grupo[:corte_train]),
            ("val", grupo[corte_train:corte_val]),
            ("test", grupo[corte_val:]),
        )
        for nombre, pids in reparto:
            for pid in pids:
                resultado[nombre].extend(por_paciente[pid])

    return resultado


def verificar_sin_fuga(particiones: dict[str, list[dict]]) -> None:
    """Lanza FugaDeDatos si un patientId aparece en dos particiones."""
    conjuntos = {k: {r["patientId"] for r in v} for k, v in particiones.items()}
    nombres = sorted(conjuntos)
    for i, a in enumerate(nombres):
        for b in nombres[i + 1:]:
            comun = conjuntos[a] & conjuntos[b]
            if comun:
                muestra = sorted(comun)[:3]
                raise FugaDeDatos(
                    f"{len(comun)} paciente(s) en '{a}' y '{b}' a la vez: {muestra}"
                )
