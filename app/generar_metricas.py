# -*- coding: utf-8 -*-
"""Escribe las métricas de «Acerca de», en agregados: app/assets/metricas.json.

USO
    python app/generar_metricas.py
    python app/generar_metricas.py --umbral 0.5 --umbral-pa 0.18 --umbral-ap 0.58 --salida OTRO.json

Lee las puntuaciones crudas congeladas del conjunto de PRUEBA
(docs/validacion-semisintetica/crudas_prueba.csv, con su .sha256 al lado) y deja
un JSON con AUC, recall y especificidad, con sus intervalos de Wilson (z = 1,96),
globales y por subgrupo, y el efecto en prueba del umbral por vista. El JSON no
lleva ninguna fila por paciente: este guion ni siquiera lee la columna de los
identificadores. Las puntuaciones por placa no viajan al repositorio público;
sí viajan este guion y el JSON, que lleva la huella (sha256) de los pesos y de las
puntuaciones de las que sale, para que se pueda comprobar.

Solo NumPy y pandas. El AUC es el de Mann-Whitney: la probabilidad de que una placa
con opacidad puntúe más que una sin ella, con los empates a la mitad (los rangos
medios). Una placa se marca (`opacidad_probable`) cuando su puntuación es MAYOR O
IGUAL que el umbral, como en el motor.

Los subgrupos son los de la tabla 2 del workshop S4, sus 13 filas con sus nombres y en
su orden: todas las placas, sexo, tres tramos de edad (18 a 39, 40 a 59 y 60 o más),
vista y los cruces de la vista con el sexo y, en PA, con los 60 o más. Los umbrales por
vista son los de la tabla 3 de ese workshop, elegidos en validación (PA 0,1798 y AP
0,5815); el global es el del servidor (0,4258). Los tres se pueden cambiar con --umbral,
--umbral-pa y --umbral-ap.

En el JSON todo lo que mide va entre 0 y 1 (no en porcentaje) y con 6 decimales; lo
que no se puede medir (un subgrupo sin positivas no tiene AUC ni recall) va como null.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import numbers
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
CRUDAS = REPO / "docs" / "validacion-semisintetica" / "crudas_prueba.csv"
PESOS = REPO / "servidor" / "pesos_modelo_cpu.pt"
SALIDA = REPO / "app" / "assets" / "metricas.json"

UMBRAL = 0.4258                                  # el del servidor (docker-compose.yml)
UMBRALES_POR_VISTA = {"PA": 0.1798, "AP": 0.5815}      # workshop S4, tabla 3
VISTAS = ("PA", "AP")
Z = 1.96
DECIMALES = 6
# Lo único que se lee del CSV: ni `patientId` ni nada que identifique una placa.
COLUMNAS = ("edad", "sexo", "vista", "etiqueta", "cruda")


class Subgrupo(NamedTuple):
    """Un subgrupo de la tabla 2: lo que no se da, no filtra. Las edades, en años
    cumplidos y con los dos extremos dentro."""
    nombre: str
    sexo: str | None = None
    vista: str | None = None
    edad_desde: int | None = None
    edad_hasta: int | None = None

    def mascara(self, placas: pd.DataFrame) -> np.ndarray:
        dentro = np.ones(len(placas), dtype=bool)
        if self.sexo is not None:
            dentro &= np.asarray(placas["sexo"].to_numpy() == self.sexo, dtype=bool)
        if self.vista is not None:
            dentro &= np.asarray(placas["vista"].to_numpy() == self.vista, dtype=bool)
        if self.edad_desde is not None:
            dentro &= placas["edad"].to_numpy() >= self.edad_desde
        if self.edad_hasta is not None:
            dentro &= placas["edad"].to_numpy() <= self.edad_hasta
        return dentro


# Las 13 filas de la tabla 2 del workshop S4, con sus nombres y en su orden: el JSON
# las lleva tal cual y la app las pinta tal cual.
SUBGRUPOS = (
    Subgrupo("Todas las placas"),
    Subgrupo("Mujeres", sexo="F"),
    Subgrupo("Hombres", sexo="M"),
    Subgrupo("18 a 39 años", edad_desde=18, edad_hasta=39),
    Subgrupo("40 a 59 años", edad_desde=40, edad_hasta=59),
    Subgrupo("60 años o más", edad_desde=60),
    Subgrupo("Placa PA (de pie)", vista="PA"),
    Subgrupo("Placa AP (portátil)", vista="AP"),
    Subgrupo("PA, mujeres", sexo="F", vista="PA"),
    Subgrupo("PA, hombres", sexo="M", vista="PA"),
    Subgrupo("PA, 60 años o más", vista="PA", edad_desde=60),
    Subgrupo("AP, mujeres", sexo="F", vista="AP"),
    Subgrupo("AP, hombres", sexo="M", vista="AP"),
)


# --------------------------------------------------------------------------
# Las cuentas
# --------------------------------------------------------------------------
def auc(etiqueta, puntuacion) -> float | None:
    """El AUC por Mann-Whitney con rangos medios: la suma de los rangos de las
    positivas, menos lo mínimo que podría sumar, entre el número de pares. Los
    empates cuentan como medio acierto. `None` si falta una de las dos clases."""
    y = np.asarray(etiqueta)
    puntuaciones = np.asarray(puntuacion, dtype=float)
    positivas = int((y == 1).sum())
    negativas = int((y == 0).sum())
    if positivas == 0 or negativas == 0:
        return None
    rangos = pd.Series(puntuaciones).rank(method="average").to_numpy()
    u = rangos[y == 1].sum() - positivas * (positivas + 1) / 2
    return float(u / (positivas * negativas))


def wilson(exitos: int, n: int, z: float = Z) -> tuple[float, float] | None:
    """El intervalo de Wilson de `exitos` de `n` (z = 1,96: el del 95 %). `None`
    sin casos. Con 0 aciertos el límite inferior es exactamente 0, y con todos, el
    superior es exactamente 1: no se deja a los redondeos."""
    if n == 0:
        return None
    p = exitos / n
    denominador = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denominador
    margen = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominador
    inferior = 0.0 if exitos == 0 else max(0.0, centro - margen)
    superior = 1.0 if exitos == n else min(1.0, centro + margen)
    return inferior, superior


def marcadas(puntuacion, vista, umbral: float, umbrales_por_vista: Mapping | None = None):
    """Qué placas marca el sistema (puntuación >= umbral). Con `umbrales_por_vista`,
    las PA y las AP usan el suyo; cualquier otra vista, el global: como el motor."""
    puntuacion = np.asarray(puntuacion, dtype=float)
    umbrales = np.full(puntuacion.shape, float(umbral))
    if umbrales_por_vista is not None:
        vista = np.asarray(vista)
        for nombre, valor in umbrales_por_vista.items():
            umbrales[vista == nombre] = valor
    return puntuacion >= umbrales


def _redondeado(valor):
    return None if valor is None else round(float(valor), DECIMALES)


def _intervalo(exitos: int, n: int):
    ic = wilson(exitos, n)
    return None if ic is None else [_redondeado(ic[0]), _redondeado(ic[1])]


def _tasas(etiqueta, marcada) -> dict:
    """Recall (de las positivas, las que se marcan) y especificidad (de las
    negativas, las que no), con su intervalo de Wilson cada una."""
    enfermas = np.asarray(etiqueta) == 1
    marcada = np.asarray(marcada, dtype=bool)
    positivas = int(enfermas.sum())
    negativas = int((~enfermas).sum())
    aciertos_positivas = int((marcada & enfermas).sum())
    aciertos_negativas = int((~marcada & ~enfermas).sum())
    return {
        "n": int(enfermas.size),
        "positivos": positivas,
        "recall": _redondeado(aciertos_positivas / positivas) if positivas else None,
        "recall_ic": _intervalo(aciertos_positivas, positivas),
        "especificidad": _redondeado(aciertos_negativas / negativas) if negativas else None,
        "especificidad_ic": _intervalo(aciertos_negativas, negativas),
    }


def _fila(placas: pd.DataFrame, umbral: float) -> dict:
    """n, positivas, AUC, y recall y especificidad con el umbral global."""
    y = placas["etiqueta"].to_numpy()
    puntuacion = placas["cruda"].to_numpy()
    tasas = _tasas(y, marcadas(puntuacion, placas["vista"].to_numpy(), umbral))
    return {
        "n": tasas["n"],
        "positivos": tasas["positivos"],
        "auc": _redondeado(auc(y, puntuacion)),
        "recall": tasas["recall"],
        "recall_ic": tasas["recall_ic"],
        "especificidad": tasas["especificidad"],
        "especificidad_ic": tasas["especificidad_ic"],
    }


def _efecto_del_umbral_por_vista(placas: pd.DataFrame, umbral: float, umbrales_por_vista) -> dict:
    """Recall y especificidad en PA, en AP y en todas, con un umbral para todas y
    con uno por vista. El AUC no está: no depende del umbral."""
    y = placas["etiqueta"].to_numpy()
    puntuacion = placas["cruda"].to_numpy()
    vista = placas["vista"].to_numpy()
    efecto = {}
    for clave, por_vista in (("un_umbral", None), ("dos_umbrales", umbrales_por_vista)):
        marcada = marcadas(puntuacion, vista, umbral, por_vista)
        bloque = {}
        for esta in VISTAS:
            dentro = vista == esta
            bloque[esta] = _tasas(y[dentro], marcada[dentro])
        bloque["global"] = _tasas(y, marcada)
        efecto[clave] = bloque
    return efecto


# --------------------------------------------------------------------------
# Lo que se acepta
# --------------------------------------------------------------------------
def _validar_umbral(nombre: str, valor) -> None:
    """Un número estrictamente entre 0 y 1, como pide el motor (un `bool` queda fuera
    solo: vale 0 o 1)."""
    if not isinstance(valor, numbers.Real) or not 0.0 < valor < 1.0:
        raise ValueError(f"el {nombre} debe ser un número estrictamente entre 0 y 1, y es {valor!r}")


def _validar_umbrales(umbral, umbrales_por_vista) -> None:
    _validar_umbral("umbral", umbral)
    if not isinstance(umbrales_por_vista, Mapping) or set(umbrales_por_vista) != set(VISTAS):
        raise ValueError("los umbrales por vista deben ser un mapa con exactamente las claves "
                         f"'PA' y 'AP', y son {umbrales_por_vista!r}")
    for vista in VISTAS:
        _validar_umbral(f"umbral de {vista}", umbrales_por_vista[vista])


def _preparar(placas: pd.DataFrame) -> pd.DataFrame:
    """Las cinco columnas que se usan, comprobadas y con la vista y el sexo como los
    lee el motor (en mayúsculas y sin espacios). Se rechaza lo que no vale: un valor
    que falta o una etiqueta que no es 0/1 falsearía una tasa sin avisar."""
    faltan = [c for c in COLUMNAS if c not in placas.columns]
    if faltan:
        raise ValueError(f"a las placas les faltan las columnas {faltan}")
    d = placas[list(COLUMNAS)].copy()
    if d.empty:
        raise ValueError("el conjunto de placas está vacío: no hay nada que medir")
    sin_valor = [c for c in COLUMNAS if d[c].isna().any()]
    if sin_valor:
        raise ValueError(f"faltan valores en {sin_valor}")
    etiqueta = pd.to_numeric(d["etiqueta"], errors="coerce")
    if not etiqueta.isin([0, 1]).all():
        raise ValueError("la etiqueta debe valer 0 o 1 en todas las placas")
    cruda = pd.to_numeric(d["cruda"], errors="coerce")
    if not ((cruda >= 0.0) & (cruda <= 1.0)).all():
        raise ValueError("la cruda debe ser una probabilidad (entre 0 y 1) en todas las placas")
    edad = pd.to_numeric(d["edad"], errors="coerce")
    if edad.isna().any():
        raise ValueError("la edad debe ser un número en todas las placas")
    d["etiqueta"] = etiqueta.astype(int)
    d["cruda"] = cruda.astype(float)
    d["edad"] = edad.astype(float)
    d["sexo"] = d["sexo"].astype(str).str.strip().str.upper()
    d["vista"] = d["vista"].astype(str).str.strip().str.upper()
    return d


def calcular(placas: pd.DataFrame, umbral: float = UMBRAL,
             umbrales_por_vista: Mapping = UMBRALES_POR_VISTA) -> dict:
    """Los agregados de unas placas con (edad, sexo, vista, etiqueta, cruda): el
    global, los subgrupos y el efecto del umbral por vista. Sin huellas ni fecha."""
    _validar_umbrales(umbral, umbrales_por_vista)
    d = _preparar(placas)
    return {
        "umbral": float(umbral),
        "umbrales_por_vista": {vista: float(umbrales_por_vista[vista]) for vista in VISTAS},
        "global": _fila(d, umbral),
        "subgrupos": [{"nombre": s.nombre, **_fila(d[s.mascara(d)], umbral)} for s in SUBGRUPOS],
        "umbral_por_vista_en_prueba": _efecto_del_umbral_por_vista(d, umbral, umbrales_por_vista),
    }


# --------------------------------------------------------------------------
# Los ficheros
# --------------------------------------------------------------------------
def _sha256_de(ruta) -> str:
    """El sha256 de los BYTES de un fichero: el de los pesos."""
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _huella_de_texto(ruta) -> str:
    """El sha256 de un fichero de TEXTO versionado, con los finales de línea
    normalizados a LF (con `core.autocrlf`, un clon de Windows lo tiene con CRLF y
    es el mismo fichero). Es la misma huella que lleva `resultados_simulacion.json`."""
    return hashlib.sha256(Path(ruta).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _huella_de_los_pesos(ruta_crudas: Path, ruta_pesos) -> str:
    """El sha256 de los pesos con que se generaron las puntuaciones: lo dice el
    `.sha256` que está al lado del CSV. Si los pesos están en esta máquina, se
    comprueba que son esos: unas puntuaciones de otros pesos no son las de este modelo."""
    ruta = ruta_crudas.with_suffix(".sha256")
    partes = ruta.read_text(encoding="utf-8").split()
    if len(partes) != 1 or not re.fullmatch(r"[0-9a-f]{64}", partes[0]):
        raise ValueError(f"{ruta.name} no lleva un sha256: no se sabe con qué pesos se "
                         "generaron las puntuaciones")
    if ruta_pesos is not None and Path(ruta_pesos).is_file() and _sha256_de(ruta_pesos) != partes[0]:
        raise ValueError(f"los pesos de {Path(ruta_pesos).name} no son con los que se generaron las "
                         f"puntuaciones ({ruta.name}): vuelve a congelar las puntuaciones con "
                         "estos pesos, o usa los que son")
    return partes[0]


def generar(ruta_crudas=CRUDAS, umbral: float = UMBRAL,
            umbrales_por_vista: Mapping = UMBRALES_POR_VISTA, ruta_pesos=PESOS,
            generado: str | None = None) -> dict:
    """El JSON completo, como diccionario, desde las puntuaciones congeladas. La
    fecha (`generado`) es la de hoy si no se da."""
    ruta_crudas = Path(ruta_crudas)
    placas = pd.read_csv(ruta_crudas, usecols=lambda columna: columna in COLUMNAS)
    return {
        "generado": generado or datetime.date.today().isoformat(),
        "pesos_sha256": _huella_de_los_pesos(ruta_crudas, ruta_pesos),
        "puntuaciones_sha256": _huella_de_texto(ruta_crudas),
        **calcular(placas, umbral, umbrales_por_vista),
    }


def serializar(metricas: dict) -> str:
    """El texto del JSON: UTF-8 sin escapes, sangría de 2, el orden de las claves tal
    cual y un salto de línea al final. Sin NaN: «NaN» no es JSON."""
    return json.dumps(metricas, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def escribir(metricas: dict, ruta) -> Path:
    # Se serializa ANTES de abrir: si falla, el fichero anterior sigue entero.
    texto = serializar(metricas)
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    return ruta


def _relativa(ruta) -> str:
    try:
        return Path(ruta).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(ruta).name


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--crudas", default=str(CRUDAS),
                   help="las puntuaciones congeladas de prueba, con su .sha256 al lado")
    p.add_argument("--salida", default=str(SALIDA), help="el JSON que se escribe")
    p.add_argument("--pesos", default=str(PESOS),
                   help="los pesos: si están, se comprueba que son los de las puntuaciones")
    p.add_argument("--umbral", type=float, default=UMBRAL, help="el umbral global (%(default)s)")
    p.add_argument("--umbral-pa", type=float, default=UMBRALES_POR_VISTA["PA"],
                   help="el umbral de las placas PA (%(default)s)")
    p.add_argument("--umbral-ap", type=float, default=UMBRALES_POR_VISTA["AP"],
                   help="el umbral de las placas AP (%(default)s)")
    args = p.parse_args(argv)
    try:
        metricas = generar(args.crudas, args.umbral,
                           {"PA": args.umbral_pa, "AP": args.umbral_ap}, args.pesos)
        destino = escribir(metricas, args.salida)
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Métricas de {metricas['global']['n']} placas, en agregados: {_relativa(destino)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
