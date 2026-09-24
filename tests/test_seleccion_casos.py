# -*- coding: utf-8 -*-
"""Los casos limite no se fabrican: estan en los datos.

RSNA trae 1 276 menores reales y 5 edades imposibles. Un DICOM sintetico de un
nino de 12 anios probaria nuestro generador, no el sistema.
"""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from pruebas.seleccionar_casos import seleccionar  # noqa: E402

UMBRAL = 0.4258
CRUCE_RV = 0.5786


@pytest.fixture(scope="module")
def casos():
    return seleccionar(n_por_perfil=5)


def test_hay_casos_en_todos_los_perfiles(casos):
    for perfil in ("positiva_clara", "negativa_clara", "banda_contradictoria",
                   "menor_edad", "edad_imposible"):
        assert casos[perfil], f"el perfil {perfil} salio vacio"


def test_la_banda_contradictoria_es_la_banda_de_verdad(casos):
    """El cribado etiqueta positivo y la RV es menor que 1: los dos a la vez."""
    for c in casos["banda_contradictoria"]:
        assert UMBRAL <= c["cruda"] < CRUCE_RV, c


def test_los_menores_son_menores_de_verdad(casos):
    for c in casos["menor_edad"]:
        assert c["edad"] < 18, c


def test_todos_los_ficheros_existen(casos):
    for perfil in casos.values():
        for c in perfil:
            assert pathlib.Path(c["ruta_dcm"]).is_file(), c["ruta_dcm"]


def test_la_seleccion_es_determinista(casos):
    """Dos corridas dan los mismos casos: si no, una prueba que falla hoy y
    pasa manana no dice nada."""
    assert seleccionar(n_por_perfil=5) == casos
