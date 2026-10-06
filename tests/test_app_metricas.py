# -*- coding: utf-8 -*-
"""Las métricas de «Acerca de» (SP5-C1, spec §7): `app/generar_metricas.py` y el
JSON de agregados que escribe, `app/assets/metricas.json`.

QUÉ VIGILA
- Las cuentas, sobre diez placas de juguete hechas a mano: el AUC por
  Mann-Whitney con rangos medios (contra la definición por pares, con empates),
  el intervalo de Wilson, el umbral con `>=` (como el motor), el umbral global
  como parámetro (con otro valor que 0,4258, también por la línea de órdenes),
  el umbral por vista, qué se hace con una vista que no es PA ni AP y qué
  entradas se rechazan (y cuáles, en el borde, se aceptan).
- El JSON versionado: las claves del contrato, ni un dato por paciente, ninguna
  ruta de una máquina, los subgrupos de la tabla 2 del workshop S4, las cifras
  del análisis previo y que está escrito como lo escribe el guion.
- Que el JSON sale de las puntuaciones congeladas: recalcular da lo mismo salvo la
  fecha. Esas pruebas se SALTAN, diciéndolo, donde las puntuaciones no están: el
  repositorio público lleva el guion y el JSON, no las puntuaciones por placa.

Solo NumPy y pandas: nada de esto toca scikit-learn.
"""
import datetime
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
GUION = REPO / "app" / "generar_metricas.py"
PUBLICADO = REPO / "app" / "assets" / "metricas.json"
CARPETA_DE_LAS_CRUDAS = REPO / "docs" / "validacion-semisintetica"
CRUDAS = CARPETA_DE_LAS_CRUDAS / "crudas_prueba.csv"
RESULTADOS_DE_LA_SIMULACION = CARPETA_DE_LAS_CRUDAS / "resultados_simulacion.json"
PESOS = REPO / "servidor" / "pesos_modelo_cpu.pt"
COMPOSE = REPO / "servidor" / "docker-compose.yml"

CLAVES = {"generado", "pesos_sha256", "puntuaciones_sha256", "umbral",
          "umbrales_por_vista", "global", "subgrupos", "umbral_por_vista_en_prueba"}
CLAVES_DE_UNA_FILA = {"n", "positivos", "auc", "recall", "recall_ic",
                      "especificidad", "especificidad_ic"}
CLAVES_DE_UN_SUBGRUPO = CLAVES_DE_UNA_FILA | {"nombre"}
CLAVES_DE_UNA_TASA = CLAVES_DE_UNA_FILA - {"auc"}       # el AUC no depende del umbral
# La tabla 2 del workshop S4, EXACTAMENTE: 13 filas, con estos nombres y en este orden.
# Todas las placas, sexo, tres tramos de edad, vista (con su aclaración entre
# paréntesis) y los cruces de la vista con el sexo y, en PA, con los 60 o más.
SUBGRUPOS = ["Todas las placas", "Mujeres", "Hombres",
             "18 a 39 años", "40 a 59 años", "60 años o más",
             "Placa PA (de pie)", "Placa AP (portátil)",
             "PA, mujeres", "PA, hombres", "PA, 60 años o más",
             "AP, mujeres", "AP, hombres"]
# Las columnas del CSV congelado: ninguna puede ser una clave del JSON.
COLUMNAS_POR_PACIENTE = {"patientId", "edad", "sexo", "vista", "filas", "columnas",
                         "archivo_png", "etiqueta", "edad_anios", "semilla", "cruda"}
LISTA_MAS_LARGA = 50     # la lista más larga que se espera: la de subgrupos tiene 13

SIN_CRUDAS = (
    "SIN VERIFICAR que app/assets/metricas.json sale de las puntuaciones: faltan las "
    "puntuaciones congeladas (docs/validacion-semisintetica/crudas_prueba.csv), que el "
    "repositorio público no lleva (solo el guion y el JSON). En el de desarrollo, esta "
    "prueba recalcula el JSON y lo compara con el versionado.")


# --------------------------------------------------------------------------
# Lo que se carga y lo que se construye
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def guion():
    """`app/generar_metricas.py` cargado por ruta: `app/` no es un paquete."""
    spec = importlib.util.spec_from_file_location("generar_metricas", GUION)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["generar_metricas"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def publicado():
    return json.loads(PUBLICADO.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def crudas_congeladas():
    if not CRUDAS.is_file():
        pytest.skip(SIN_CRUDAS)
    return CRUDAS


def _placas():
    """Diez placas de juguete, con las cuentas hechas a mano (se explican en cada
    prueba). La última está justo en el umbral global, 0,4258."""
    return pd.DataFrame(
        [  # edad, sexo, vista, etiqueta, cruda
            (30, "F", "PA", 1, 0.30),
            (45, "M", "PA", 1, 0.10),
            (62, "F", "PA", 0, 0.20),
            (70, "M", "PA", 0, 0.05),
            (25, "F", "AP", 1, 0.90),
            (55, "M", "AP", 1, 0.50),
            (61, "F", "AP", 0, 0.60),
            (33, "M", "AP", 0, 0.45),
            (41, "F", "AP", 0, 0.20),
            (80, "M", "AP", 1, 0.4258),
        ],
        columns=["edad", "sexo", "vista", "etiqueta", "cruda"])


UMBRAL = 0.4258
POR_VISTA = {"PA": 0.18, "AP": 0.58}      # de juguete: no son los del workshop


def _por_nombre(resultado):
    return {fila["nombre"]: fila for fila in resultado["subgrupos"]}


def _comprobar(fila, **esperado):
    """Cada clave de `esperado` coincide con la de la fila: `None` es `None`, una
    lista o tupla se compara elemento a elemento y lo demás, con 1e-6."""
    for clave, valor in esperado.items():
        real = fila[clave]
        if valor is None:
            assert real is None, f"{clave}: {real!r}"
        elif isinstance(valor, (list, tuple)):
            assert real == pytest.approx(list(valor), abs=1e-6), f"{clave}: {real!r}"
        else:
            assert real == pytest.approx(valor, abs=1e-6), f"{clave}: {real!r}"


def _ic(guion, exitos, n):
    """El intervalo de Wilson de `exitos` de `n`, como lo escribe el JSON."""
    inferior, superior = guion.wilson(exitos, n)
    return [round(inferior, 6), round(superior, 6)]


def _auc_por_pares(y, p):
    """La definición: de cada par (positiva, negativa), 1 si la positiva puntúa
    más, 1/2 si empatan y 0 si puntúa menos."""
    pos, neg = p[y == 1], p[y == 0]
    mayor = int((pos[:, None] > neg[None, :]).sum())
    igual = int((pos[:, None] == neg[None, :]).sum())
    return (mayor + 0.5 * igual) / (len(pos) * len(neg))


def _recorrer(valor):
    """Cada nodo del JSON: (clave que lo contiene o None, el nodo)."""
    if isinstance(valor, dict):
        for clave, hijo in valor.items():
            yield clave, hijo
            yield from _recorrer(hijo)
    elif isinstance(valor, list):
        for hijo in valor:
            yield None, hijo
            yield from _recorrer(hijo)


# --------------------------------------------------------------------------
# El AUC: Mann-Whitney con rangos medios
# --------------------------------------------------------------------------
def test_auc_de_un_ejemplo_conocido(guion):
    # El de la documentación de scikit-learn: 3 de 4 pares bien ordenados.
    assert guion.auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)


def test_auc_cuenta_los_empates_como_la_mitad(guion):
    # Positivas {0,5; 0,9}, negativas {0,5; 0,2}: los pares dan 1/2, 1, 1 y 1.
    assert guion.auc([0, 1, 0, 1], [0.5, 0.5, 0.2, 0.9]) == pytest.approx(0.875)
    assert guion.auc([0, 1, 0, 1], [0.7, 0.7, 0.7, 0.7]) == pytest.approx(0.5)


def test_auc_coincide_con_la_definicion_por_pares_con_muchos_empates(guion):
    rng = np.random.default_rng(7)
    p = rng.integers(0, 12, 400) / 10          # solo 12 valores: casi todo empata
    y = rng.integers(0, 2, 400)
    assert guion.auc(y, p) == pytest.approx(_auc_por_pares(y, p), abs=1e-12)


def test_auc_sin_una_de_las_clases_no_existe(guion):
    assert guion.auc([1, 1, 1], [0.2, 0.5, 0.9]) is None
    assert guion.auc([0, 0], [0.2, 0.5]) is None


# --------------------------------------------------------------------------
# El intervalo de Wilson, con z = 1,96
# --------------------------------------------------------------------------
def test_wilson_de_un_ejemplo_conocido(guion):
    inferior, superior = guion.wilson(8, 10)
    assert inferior == pytest.approx(0.4902, abs=5e-5)
    assert superior == pytest.approx(0.9433, abs=5e-5)
    inferior, superior = guion.wilson(3, 5)
    assert inferior == pytest.approx(0.2307, abs=5e-5)
    assert superior == pytest.approx(0.8824, abs=5e-5)


def test_wilson_en_los_extremos_se_queda_en_cero_y_uno(guion):
    inferior, superior = guion.wilson(0, 20)
    assert inferior == 0.0 and 0.0 < superior < 0.2
    inferior, superior = guion.wilson(20, 20)
    assert superior == 1.0 and 0.8 < inferior < 1.0


def test_wilson_en_los_extremos_es_exacto_para_cualquier_n(guion):
    # La fórmula, tal cual, da 1e-17 en vez de 0 (o 0,9999999999999999 en vez de 1)
    # para muchos n: el límite inferior con 0 aciertos es 0 y el superior con todos, 1.
    for n in range(1, 120):
        assert guion.wilson(0, n)[0] == 0.0, n
        assert guion.wilson(n, n)[1] == 1.0, n


def test_wilson_sin_casos_no_existe(guion):
    assert guion.wilson(0, 0) is None


# --------------------------------------------------------------------------
# Las placas que se marcan: el umbral, con `>=`, y el umbral por vista
# --------------------------------------------------------------------------
def test_una_placa_justo_en_el_umbral_se_marca(guion):
    marcadas = guion.marcadas(np.array([0.4257, 0.4258, 0.4259]),
                              np.array(["PA", "PA", "PA"]), UMBRAL)
    assert marcadas.tolist() == [False, True, True]


def test_con_umbrales_por_vista_cada_vista_usa_el_suyo(guion):
    puntuacion = np.array([0.30, 0.10, 0.50, 0.60])
    vista = np.array(["PA", "PA", "AP", "AP"])
    assert guion.marcadas(puntuacion, vista, UMBRAL).tolist() == [False, False, True, True]
    # PA 0,18: la de 0,30 se marca y la de 0,10 no; AP 0,58: la de 0,50 no y la de 0,60 sí
    assert (guion.marcadas(puntuacion, vista, UMBRAL, POR_VISTA).tolist()
            == [True, False, False, True])


def test_una_vista_que_no_es_pa_ni_ap_usa_el_umbral_global(guion):
    puntuacion = np.array([0.30, 0.50, 0.30, 0.50])
    vista = np.array(["LL", "LL", "PA", "AP"])
    # LL 0,30 no llega a 0,4258 (con el de PA, sí) y LL 0,50 sí llega (con el de AP, no)
    assert (guion.marcadas(puntuacion, vista, UMBRAL, POR_VISTA).tolist()
            == [False, True, True, False])


# --------------------------------------------------------------------------
# Las métricas de las placas de juguete, a mano
# --------------------------------------------------------------------------
def test_el_global_de_las_placas_de_juguete(guion):
    r = guion.calcular(_placas(), UMBRAL, POR_VISTA)
    # Positivas: 0,30 0,10 0,90 0,50 0,4258; negativas: 0,20 0,05 0,60 0,45 0,20.
    # Pares bien ordenados: 3 + 1 + 5 + 4 + 3 = 16 de 25. Marcadas (>= 0,4258):
    # acierta 3 de las 5 positivas y no marca 3 de las 5 negativas.
    _comprobar(r["global"], n=10, positivos=5, auc=0.64, recall=0.6,
               recall_ic=_ic(guion, 3, 5), especificidad=0.6,
               especificidad_ic=_ic(guion, 3, 5))


def test_los_subgrupos_de_las_placas_de_juguete(guion):
    s = _por_nombre(guion.calcular(_placas(), UMBRAL, POR_VISTA))
    _comprobar(s["Todas las placas"], n=10, positivos=5, auc=0.64, recall=0.6, especificidad=0.6)
    # Mujeres: filas 1, 3, 5, 7, 9 (positivas la 1 y la 5; la 5 se marca; la 3 y la 9, no)
    _comprobar(s["Mujeres"], n=5, positivos=2, auc=5 / 6, recall=0.5,
               recall_ic=_ic(guion, 1, 2), especificidad=2 / 3,
               especificidad_ic=_ic(guion, 2, 3))
    # Hombres: filas 2, 4, 6, 8, 10 (la 2 no se marca, la 6 y la 10 sí; la 8 se marca y la 4, no)
    _comprobar(s["Hombres"], n=5, positivos=3, auc=4 / 6, recall=2 / 3, especificidad=0.5)
    # PA: filas 1 a 4: ninguna positiva se marca y las dos negativas, no
    _comprobar(s["Placa PA (de pie)"], n=4, positivos=2, auc=0.75, recall=0.0,
               especificidad=1.0)
    # AP: filas 5 a 10: las tres positivas se marcan y de las tres negativas, solo la 9 no
    _comprobar(s["Placa AP (portátil)"], n=6, positivos=3, auc=6 / 9, recall=1.0,
               especificidad=1 / 3)
    # 60 o más: filas 3, 4, 7 y 10; solo la 10 es positiva y se marca; la 7 se marca
    _comprobar(s["60 años o más"], n=4, positivos=1, auc=2 / 3, recall=1.0,
               especificidad=2 / 3)


def test_un_subgrupo_sin_positivas_da_nulos_y_no_nan(guion):
    # PA de 60 o más: las filas 3 y 4, las dos negativas
    fila = _por_nombre(guion.calcular(_placas(), UMBRAL, POR_VISTA))["PA, 60 años o más"]
    _comprobar(fila, n=2, positivos=0, auc=None, recall=None, recall_ic=None,
               especificidad=1.0, especificidad_ic=_ic(guion, 2, 2))


def test_con_otro_umbral_global_cambian_las_marcadas_y_con_ellas_las_cuentas(guion):
    r = guion.calcular(_placas(), 0.5, POR_VISTA)
    assert r["umbral"] == 0.5
    # Con 0,5 se marcan la 5 (0,90), la 6 (0,50: justo en el umbral) y la 7 (0,60), y ya no
    # la 10 (0,4258). De las 5 positivas se marcan 2 (la 5 y la 6), y de las 5 negativas no
    # se marcan 4 (todas menos la 7). El AUC no depende del umbral: sigue en 16/25.
    _comprobar(r["global"], n=10, positivos=5, auc=0.64, recall=0.4,
               recall_ic=_ic(guion, 2, 5), especificidad=0.8, especificidad_ic=_ic(guion, 4, 5))
    s = _por_nombre(r)
    # AP (filas 5 a 10): de las positivas 5, 6 y 10 se marcan 2; de las negativas 7, 8 y 9, no
    # se marcan la 8 ni la 9
    _comprobar(s["Placa AP (portátil)"], n=6, positivos=3, auc=6 / 9, recall=2 / 3,
               especificidad=2 / 3)
    # 60 o más (filas 3, 4, 7 y 10): la única positiva, la 10, ya no se marca; la 7 sí
    _comprobar(s["60 años o más"], n=4, positivos=1, auc=2 / 3, recall=0.0, especificidad=2 / 3)
    # el efecto «con un umbral» usa el mismo; el de «dos umbrales» no depende del global
    # (aquí no hay ninguna placa de otra vista)
    efecto = r["umbral_por_vista_en_prueba"]
    _comprobar(efecto["un_umbral"]["PA"], recall=0.0, especificidad=1.0)
    _comprobar(efecto["un_umbral"]["AP"], recall=2 / 3, especificidad=2 / 3)
    _comprobar(efecto["un_umbral"]["global"], recall=0.4, especificidad=0.8)
    con_el_de_siempre = guion.calcular(_placas(), UMBRAL, POR_VISTA)["umbral_por_vista_en_prueba"]
    assert efecto["dos_umbrales"] == con_el_de_siempre["dos_umbrales"]


def test_los_tramos_de_edad_incluyen_sus_extremos(guion):
    edades = [18, 39, 40, 59, 60, 91]
    placas = pd.DataFrame({"edad": edades, "sexo": "F", "vista": "PA",
                           "etiqueta": [0, 1, 0, 1, 0, 1],
                           "cruda": [0.1, 0.9, 0.2, 0.8, 0.3, 0.7]})
    s = _por_nombre(guion.calcular(placas, UMBRAL, POR_VISTA))
    assert (s["18 a 39 años"]["n"], s["40 a 59 años"]["n"], s["60 años o más"]["n"]) == (2, 2, 2)


def test_el_efecto_del_umbral_por_vista_en_las_placas_de_juguete(guion):
    efecto = guion.calcular(_placas(), UMBRAL, POR_VISTA)["umbral_por_vista_en_prueba"]
    assert set(efecto) == {"un_umbral", "dos_umbrales"}
    for bloque in efecto.values():
        assert set(bloque) == {"PA", "AP", "global"}
        for tasa in bloque.values():
            assert set(tasa) == CLAVES_DE_UNA_TASA
    # Con un umbral (0,4258): PA no marca ninguna positiva y AP las tres; global 3 de 5
    _comprobar(efecto["un_umbral"]["PA"], n=4, positivos=2, recall=0.0, especificidad=1.0)
    _comprobar(efecto["un_umbral"]["AP"], n=6, positivos=3, recall=1.0, especificidad=1 / 3)
    _comprobar(efecto["un_umbral"]["global"], n=10, positivos=5, recall=0.6, especificidad=0.6)
    # Con dos (PA 0,18; AP 0,58): PA marca la 1, la 3 y no la 2 ni la 4; AP marca la 5
    # y la 7, y no la 6, la 8, la 9 ni la 10
    _comprobar(efecto["dos_umbrales"]["PA"], n=4, positivos=2, recall=0.5,
               recall_ic=_ic(guion, 1, 2), especificidad=0.5,
               especificidad_ic=_ic(guion, 1, 2))
    _comprobar(efecto["dos_umbrales"]["AP"], n=6, positivos=3, recall=1 / 3, especificidad=2 / 3)
    _comprobar(efecto["dos_umbrales"]["global"], n=10, positivos=5, recall=0.4, especificidad=0.6)


def test_la_vista_se_lee_como_la_lee_el_motor(guion):
    # en mayúsculas y sin espacios: « pa» y «ap » son PA y AP
    sucias = _placas().assign(vista=lambda d: d["vista"].map({"PA": " pa", "AP": "ap "}))
    assert guion.calcular(sucias, UMBRAL, POR_VISTA) == guion.calcular(_placas(), UMBRAL, POR_VISTA)


def test_las_placas_se_leen_sin_necesitar_el_resto_de_columnas(guion):
    mas = _placas().assign(patientId=[f"paciente-{i}" for i in range(10)], archivo_png="x.png")
    assert guion.calcular(mas, UMBRAL, POR_VISTA) == guion.calcular(_placas(), UMBRAL, POR_VISTA)


# --------------------------------------------------------------------------
# Lo que se rechaza
# --------------------------------------------------------------------------
@pytest.mark.parametrize("umbral", [0, 1, -0.1, 1.5, float("nan"), True, "0.4258", None])
def test_un_umbral_global_mal_formado_da_value_error(guion, umbral):
    with pytest.raises(ValueError, match="umbral"):
        guion.calcular(_placas(), umbral, POR_VISTA)


@pytest.mark.parametrize("por_vista", [
    None, {}, {"PA": 0.18}, {"AP": 0.58}, {"PA": 0.18, "AP": 0.58, "LL": 0.3},
    {"pa": 0.18, "ap": 0.58}, {"PA": 0.0, "AP": 0.58}, {"PA": 0.18, "AP": 1.0},
    {"PA": float("nan"), "AP": 0.58}, {"PA": "0.18", "AP": 0.58}, {"PA": True, "AP": 0.58}])
def test_unos_umbrales_por_vista_mal_formados_dan_value_error(guion, por_vista):
    with pytest.raises(ValueError, match="umbral"):
        guion.calcular(_placas(), UMBRAL, por_vista)


@pytest.mark.parametrize("estropicio, dice", [
    (lambda d: d.drop(columns=["cruda"]), "cruda"),
    (lambda d: d.drop(columns=["edad"]), "edad"),
    (lambda d: d.assign(etiqueta=[0, 1, 0, 1, 0, 1, 0, 1, 0, 2]), "etiqueta"),
    (lambda d: d.assign(cruda=[0.3, 0.1, 0.2, 0.05, 0.9, 0.5, 0.6, 0.45, 0.2, 1.5]), "cruda"),
    (lambda d: d.assign(cruda=[0.3, 0.1, 0.2, 0.05, 0.9, 0.5, 0.6, 0.45, 0.2, -0.1]), "cruda"),
    (lambda d: d.assign(cruda=[0.3, 0.1, 0.2, 0.05, 0.9, 0.5, 0.6, 0.45, 0.2, float("nan")]), "cruda"),
    (lambda d: d.assign(edad=["30", "45", "62", "70", "veinticinco", "55", "61", "33", "41", "80"]),
     "edad"),
    (lambda d: d.assign(sexo=[None] + ["F"] * 9), "sexo"),
    (lambda d: d.iloc[0:0], "vacío"),
])
def test_unas_placas_mal_formadas_dan_value_error(guion, estropicio, dice):
    with pytest.raises(ValueError, match=dice):
        guion.calcular(estropicio(_placas()), UMBRAL, POR_VISTA)


def test_las_crudas_exactamente_0_y_1_se_aceptan(guion):
    # Una sigmoide saturada da 0,0 o 1,0 exactos, y son probabilidades: no se rechazan.
    # La 1 pasa de 0,30 a 1,0 (ahora se marca) y la 4 de 0,05 a 0,0. De las 5 positivas se
    # marcan 4 (todas menos la 2); de las 5 negativas no se marcan 3 (la 3, la 4 y la 9).
    # Pares bien ordenados: 5 + 1 + 5 + 4 + 3 = 18 de 25.
    placas = _placas().assign(
        cruda=[1.0, 0.10, 0.20, 0.0, 0.90, 0.50, 0.60, 0.45, 0.20, 0.4258])
    r = guion.calcular(placas, UMBRAL, POR_VISTA)
    _comprobar(r["global"], n=10, positivos=5, auc=0.72, recall=0.8, especificidad=0.6)


# --------------------------------------------------------------------------
# El guion de punta a punta, con ficheros de juguete
# --------------------------------------------------------------------------
HUELLA_DE_JUGUETE = "ab" * 32


def _fichero_de_crudas(carpeta, *, finales=b"\n", huella_de_los_pesos=HUELLA_DE_JUGUETE):
    """`crudas_prueba.csv` y, al lado, `crudas_prueba.sha256`, como en el repositorio."""
    carpeta.mkdir(parents=True, exist_ok=True)
    placas = _placas().assign(patientId=[f"paciente-{i}" for i in range(10)])
    texto = placas.to_csv(index=False, lineterminator="\n").encode("utf-8")
    ruta = carpeta / "crudas_prueba.csv"
    ruta.write_bytes(texto.replace(b"\n", finales))
    (carpeta / "crudas_prueba.sha256").write_text(huella_de_los_pesos + "\n", encoding="utf-8")
    return ruta


def test_generar_lleva_las_huellas_y_el_contrato(guion, tmp_path):
    ruta = _fichero_de_crudas(tmp_path)
    r = guion.generar(ruta, ruta_pesos=tmp_path / "no_hay.pt", generado="2026-10-05")
    assert set(r) == CLAVES
    assert r["generado"] == "2026-10-05"
    assert r["pesos_sha256"] == HUELLA_DE_JUGUETE
    assert r["puntuaciones_sha256"] == hashlib.sha256(ruta.read_bytes()).hexdigest()
    assert r["umbral"] == guion.UMBRAL == 0.4258
    assert r["umbrales_por_vista"] == guion.UMBRALES_POR_VISTA == {"PA": 0.1798, "AP": 0.5815}


def test_sin_fecha_el_json_lleva_la_de_hoy(guion, tmp_path):
    ruta = _fichero_de_crudas(tmp_path)
    antes = datetime.date.today().isoformat()
    r = guion.generar(ruta, ruta_pesos=tmp_path / "no_hay.pt")
    assert r["generado"] in (antes, datetime.date.today().isoformat())


def test_generar_acepta_otros_umbrales_por_vista(guion, tmp_path):
    ruta = _fichero_de_crudas(tmp_path)
    r = guion.generar(ruta, umbrales_por_vista=POR_VISTA, ruta_pesos=tmp_path / "no_hay.pt")
    assert r["umbrales_por_vista"] == POR_VISTA
    assert r["umbral_por_vista_en_prueba"]["dos_umbrales"]["global"]["recall"] == pytest.approx(0.4)


def test_el_guion_solo_lee_las_columnas_que_usa_y_no_los_identificadores(guion, tmp_path,
                                                                        monkeypatch):
    ruta = _fichero_de_crudas(tmp_path)            # el CSV lleva `patientId`
    leidas = []
    lee = pd.read_csv

    def espia(*args, **kwargs):
        placas = lee(*args, **kwargs)
        leidas.append(list(placas.columns))
        return placas

    monkeypatch.setattr(pd, "read_csv", espia)
    guion.generar(ruta, ruta_pesos=tmp_path / "no_hay.pt")
    assert len(leidas) == 1 and sorted(leidas[0]) == sorted(["edad", "sexo", "vista",
                                                             "etiqueta", "cruda"])


def test_la_huella_de_las_puntuaciones_no_depende_de_los_finales_de_linea(guion, tmp_path):
    con_lf = _fichero_de_crudas(tmp_path / "lf")
    con_crlf = _fichero_de_crudas(tmp_path / "crlf", finales=b"\r\n")
    assert con_lf.read_bytes() != con_crlf.read_bytes()
    a = guion.generar(con_lf, ruta_pesos=tmp_path / "no_hay.pt")
    b = guion.generar(con_crlf, ruta_pesos=tmp_path / "no_hay.pt")
    assert a["puntuaciones_sha256"] == b["puntuaciones_sha256"]


def test_los_pesos_que_hay_tienen_que_ser_los_de_las_puntuaciones(guion, tmp_path):
    pesos = tmp_path / "pesos.pt"
    pesos.write_bytes(b"unos pesos de juguete")
    suyos = hashlib.sha256(pesos.read_bytes()).hexdigest()
    bien = _fichero_de_crudas(tmp_path / "bien", huella_de_los_pesos=suyos)
    assert guion.generar(bien, ruta_pesos=pesos)["pesos_sha256"] == suyos
    mal = _fichero_de_crudas(tmp_path / "mal")           # la huella de juguete, que no es la suya
    with pytest.raises(ValueError, match="pesos"):
        guion.generar(mal, ruta_pesos=pesos)


@pytest.mark.parametrize("contenido", ["", "no es un sha256\n", ("ab" * 32 + " ") * 2, "AB" * 32])
def test_una_huella_de_los_pesos_mal_formada_da_value_error(guion, tmp_path, contenido):
    ruta = _fichero_de_crudas(tmp_path)
    (tmp_path / "crudas_prueba.sha256").write_text(contenido, encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        guion.generar(ruta, ruta_pesos=tmp_path / "no_hay.pt")


def test_escribir_deja_utf8_sin_escapes_con_sangria_de_dos(guion, tmp_path):
    destino = tmp_path / "carpeta nueva" / "metricas.json"
    guion.escribir({"nombre": "60 años o más", "ic": [0.5, 0.75]}, destino)
    texto = destino.read_bytes().decode("utf-8")
    assert "60 años o más" in texto and "\\u" not in texto
    assert texto.startswith('{\n  "nombre"') and texto.endswith("}\n") and "\r" not in texto
    assert json.loads(texto) == {"nombre": "60 años o más", "ic": [0.5, 0.75]}


def test_escribir_no_deja_pasar_un_nan(guion, tmp_path):
    destino = tmp_path / "metricas.json"
    with pytest.raises(ValueError):
        guion.escribir({"auc": float("nan")}, destino)
    assert not destino.exists()


def test_main_escribe_el_json_y_no_lleva_los_pacientes(guion, tmp_path):
    ruta = _fichero_de_crudas(tmp_path)
    destino = tmp_path / "salida" / "metricas.json"
    codigo = guion.main(["--crudas", str(ruta), "--salida", str(destino),
                         "--pesos", str(tmp_path / "no_hay.pt"),
                         "--umbral-pa", "0.18", "--umbral-ap", "0.58"])
    assert codigo == 0
    texto = destino.read_text(encoding="utf-8")
    escrito = json.loads(texto)
    assert set(escrito) == CLAVES
    assert escrito["umbrales_por_vista"] == POR_VISTA
    assert "paciente-" not in texto and "patientId" not in texto
    assert [f["nombre"] for f in escrito["subgrupos"]] == SUBGRUPOS


def test_main_con_otro_umbral_global_lo_escribe_y_lo_usa(guion, tmp_path):
    ruta = _fichero_de_crudas(tmp_path)
    destino = tmp_path / "metricas.json"
    codigo = guion.main(["--crudas", str(ruta), "--salida", str(destino),
                         "--pesos", str(tmp_path / "no_hay.pt"), "--umbral", "0.5"])
    assert codigo == 0
    escrito = json.loads(destino.read_text(encoding="utf-8"))
    assert escrito["umbral"] == 0.5
    # y lo usa: con 0,5, de las diez placas de juguete se marcan 2 de las 5 positivas y no
    # se marcan 4 de las 5 negativas (con 0,4258 serían 3 y 3)
    assert (escrito["global"]["recall"], escrito["global"]["especificidad"]) == (0.4, 0.8)
    assert escrito["umbrales_por_vista"] == guion.UMBRALES_POR_VISTA     # los de siempre


def test_main_dice_que_falla_y_no_escribe(guion, tmp_path, capsys):
    ruta = _fichero_de_crudas(tmp_path)
    destino = tmp_path / "metricas.json"
    codigo = guion.main(["--crudas", str(ruta), "--salida", str(destino),
                         "--pesos", str(tmp_path / "no_hay.pt"), "--umbral-pa", "1.5"])
    assert codigo != 0 and not destino.exists()
    assert "umbral" in capsys.readouterr().err
    assert guion.main(["--crudas", str(tmp_path / "no_existe.csv"),
                       "--salida", str(destino)]) != 0
    assert not destino.exists()


# --------------------------------------------------------------------------
# El JSON versionado, `app/assets/metricas.json`
# --------------------------------------------------------------------------
def test_el_json_versionado_tiene_las_claves_del_contrato(publicado):
    assert set(publicado) == CLAVES
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", publicado["generado"])
    for huella in ("pesos_sha256", "puntuaciones_sha256"):
        assert re.fullmatch(r"[0-9a-f]{64}", publicado[huella]), huella
    assert publicado["umbral"] == 0.4258
    assert publicado["umbrales_por_vista"] == {"PA": 0.1798, "AP": 0.5815}
    assert set(publicado["global"]) == CLAVES_DE_UNA_FILA
    assert isinstance(publicado["subgrupos"], list)
    for fila in publicado["subgrupos"]:
        assert set(fila) == CLAVES_DE_UN_SUBGRUPO, fila.get("nombre")
    efecto = publicado["umbral_por_vista_en_prueba"]
    assert set(efecto) == {"un_umbral", "dos_umbrales"}
    for bloque in efecto.values():
        assert set(bloque) == {"PA", "AP", "global"}
        for tasa in bloque.values():
            assert set(tasa) == CLAVES_DE_UNA_TASA


def test_el_json_versionado_no_lleva_ningun_dato_por_paciente(publicado):
    texto = PUBLICADO.read_text(encoding="utf-8")
    claves = {clave for clave, _ in _recorrer(publicado) if clave is not None}
    assert not claves & COLUMNAS_POR_PACIENTE, claves & COLUMNAS_POR_PACIENTE
    # ninguna lista con tantos elementos como placas (ni como positivas ni negativas)
    largas = [len(v) for _, v in _recorrer(publicado)
              if isinstance(v, list) and len(v) >= LISTA_MAS_LARGA]
    assert not largas, f"listas de {largas} elementos: ¿una fila por paciente?"
    # ni un identificador (un UUID, como los patientId) en ningún sitio
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", texto)


def test_el_json_versionado_no_lleva_rutas_de_ninguna_maquina():
    texto = PUBLICADO.read_text(encoding="utf-8")
    assert not re.search(r"[A-Za-z]:[\\/]", texto), "una ruta de Windows"
    assert not re.search(r"/(Users|home|tmp|mnt|var|opt)/", texto), "una ruta de Unix"
    assert "\\\\" not in texto, "una barra invertida escapada: ¿una ruta de Windows o una UNC?"


def _texto_versionado():
    """El JSON versionado, con LF: con `core.autocrlf`, un clon de Windows lo tiene
    con CRLF y es el mismo fichero."""
    return PUBLICADO.read_bytes().decode("utf-8").replace("\r\n", "\n")


def test_el_json_versionado_esta_escrito_como_lo_escribe_el_guion():
    # `ensure_ascii=False`, sangría de 2 y un salto de línea al final; sin retoques a mano
    texto = _texto_versionado()
    esperado = json.dumps(json.loads(texto), ensure_ascii=False, indent=2,
                          allow_nan=False) + "\n"
    assert texto == esperado


def test_los_subgrupos_son_los_de_la_tabla_2_del_workshop(publicado):
    assert [f["nombre"] for f in publicado["subgrupos"]] == SUBGRUPOS


def test_cada_variable_reparte_las_placas_sin_dejar_ninguna_fuera(publicado):
    s = {f["nombre"]: f for f in publicado["subgrupos"]}
    todas = s["Todas las placas"]
    reparto = {
        "sexo": ("Mujeres", "Hombres"),
        "edad": ("18 a 39 años", "40 a 59 años", "60 años o más"),
        "vista": ("Placa PA (de pie)", "Placa AP (portátil)"),
    }
    for variable, partes in reparto.items():
        for clave in ("n", "positivos"):
            assert sum(s[p][clave] for p in partes) == todas[clave], (variable, clave)
    for vista, partes in (("Placa PA (de pie)", ("PA, mujeres", "PA, hombres")),
                          ("Placa AP (portátil)", ("AP, mujeres", "AP, hombres"))):
        for clave in ("n", "positivos"):
            assert sum(s[p][clave] for p in partes) == s[vista][clave], (vista, clave)
    # el cruce de la PA con los 60 o más está dentro de la PA y dentro de los 60 o más
    assert s["PA, 60 años o más"]["n"] <= s["Placa PA (de pie)"]["n"]
    assert s["PA, 60 años o más"]["n"] <= s["60 años o más"]["n"]
    assert publicado["global"] == {k: v for k, v in todas.items() if k != "nombre"}


def test_las_cifras_del_json_son_las_del_analisis_previo(publicado):
    s = {f["nombre"]: f for f in publicado["subgrupos"]}
    g = publicado["global"]
    assert (g["n"], g["positivos"]) == (3811, 844)
    assert round(g["auc"], 3) == 0.885
    assert round(g["recall"], 3) == 0.882
    assert [round(v, 3) for v in g["recall_ic"]] == [0.858, 0.902]
    assert round(g["especificidad"], 3) == 0.702
    assert [round(v, 3) for v in g["especificidad_ic"]] == [0.686, 0.719]
    assert round(s["Placa PA (de pie)"]["recall"], 3) == 0.693
    assert round(s["Placa AP (portátil)"]["especificidad"], 3) == 0.393
    assert round(s["PA, 60 años o más"]["recall"], 3) == 0.636
    con_dos = publicado["umbral_por_vista_en_prueba"]["dos_umbrales"]
    assert round(con_dos["PA"]["recall"], 3) == 0.891
    assert round(con_dos["AP"]["recall"], 3) == 0.888
    assert round(con_dos["global"]["especificidad"], 3) == 0.615
    # con un solo umbral, el global del efecto es el global de todo
    con_uno = publicado["umbral_por_vista_en_prueba"]["un_umbral"]["global"]
    assert con_uno == {k: v for k, v in g.items() if k != "auc"}


def test_los_intervalos_rodean_a_su_cifra_y_cada_cifra_esta_en_su_rango(publicado):
    filas = [publicado["global"], *publicado["subgrupos"]]
    for bloque in publicado["umbral_por_vista_en_prueba"].values():
        filas += list(bloque.values())
    for fila in filas:
        for tasa in ("recall", "especificidad"):
            if fila[tasa] is None:
                assert fila[tasa + "_ic"] is None
                continue
            inferior, superior = fila[tasa + "_ic"]
            assert 0.0 <= inferior <= fila[tasa] <= superior <= 1.0, (fila.get("nombre"), tasa)
        if "auc" in fila and fila["auc"] is not None:
            assert 0.5 < fila["auc"] <= 1.0, fila.get("nombre")
        assert 0 <= fila["positivos"] <= fila["n"]


def test_el_umbral_global_del_json_es_el_que_sirve_el_servidor(guion, publicado):
    if not COMPOSE.is_file():
        pytest.skip("sin servidor/docker-compose.yml no se sabe qué umbral sirve el servidor")
    encontrado = re.search(r'^\s*UMBRAL:\s*"([0-9.]+)"', COMPOSE.read_text(encoding="utf-8"),
                           re.MULTILINE)
    assert encontrado, "servidor/docker-compose.yml no fija UMBRAL"
    assert publicado["umbral"] == guion.UMBRAL == float(encontrado.group(1))


def test_las_huellas_del_json_son_las_de_la_simulacion_semisintetica(publicado):
    if not RESULTADOS_DE_LA_SIMULACION.is_file():
        pytest.skip("sin docs/validacion-semisintetica/resultados_simulacion.json no hay con qué "
                    "comparar las huellas")
    insumos = json.loads(RESULTADOS_DE_LA_SIMULACION.read_text(encoding="utf-8"))["insumos"]
    assert publicado["puntuaciones_sha256"] == insumos["crudas_sha256"]
    assert publicado["pesos_sha256"] == insumos["pesos_sha256"]


def test_los_pesos_de_aqui_son_con_los_que_se_calcularon_las_puntuaciones(publicado):
    if not PESOS.is_file():
        pytest.skip("sin servidor/pesos_modelo_cpu.pt (no se versiona) no se puede comprobar que "
                    "son los pesos con los que se generaron las puntuaciones")
    assert hashlib.sha256(PESOS.read_bytes()).hexdigest() == publicado["pesos_sha256"]


# --------------------------------------------------------------------------
# El JSON sale de las puntuaciones congeladas (solo donde están)
# --------------------------------------------------------------------------
def test_recalcular_da_el_mismo_json_salvo_la_fecha(guion, publicado, crudas_congeladas):
    hoy = guion.generar()
    sin_fecha = lambda d: {k: v for k, v in d.items() if k != "generado"}   # noqa: E731
    assert sin_fecha(hoy) == sin_fecha(publicado)
    # y escrito, es el mismo fichero (la fecha aparte): el de hoy con la fecha del publicado
    assert guion.serializar({**hoy, "generado": publicado["generado"]}) == _texto_versionado()


def test_el_auc_publicado_es_el_de_la_definicion_por_pares(publicado, crudas_congeladas):
    placas = pd.read_csv(crudas_congeladas, usecols=["etiqueta", "cruda"])
    por_pares = _auc_por_pares(placas["etiqueta"].to_numpy(), placas["cruda"].to_numpy())
    assert publicado["global"]["auc"] == pytest.approx(por_pares, abs=1e-6)
