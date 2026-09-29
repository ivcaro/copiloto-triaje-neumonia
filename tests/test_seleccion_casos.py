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
def casos(rsna_raiz, pesos_desplegados):
    """La seleccion de verdad: necesita el dataset (`rsna_raiz`) y los pesos
    desplegados (`pesos_desplegados`), y sin cualquiera de los dos las cinco
    pruebas que la usan se saltan diciendo cual falta. Con los dos y sin la
    cache de puntuaciones, esta llamada la genera (infiere sobre las 3 811
    imagenes de prueba: minutos)."""
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


# --------------------------------------------------------------------------
# Lo que se prueba sin dataset: de donde sale la ruta de cada placa
# --------------------------------------------------------------------------
REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture
def con_puntuaciones_de_mentira(monkeypatch):
    """Tres filas en lugar de la cache: asi `seleccionar` no infiere ni lee
    los pesos. Los metadatos (`docs/eda/metadatos_eda.csv`) si son los reales,
    que estan versionados: de ahi salen los tres adultos de las filas, y los
    menores y las edades imposibles que `seleccionar` busca por su cuenta."""
    import pandas as pd
    from pruebas import seleccionar_casos
    meta = pd.read_csv(REPO / "docs" / "eda" / "metadatos_eda.csv")
    adultos = sorted(meta[(meta.edad_num >= 18) & (meta.edad_num <= 100)]
                     .patientId)[:3]
    df = pd.DataFrame({"patientId": adultos, "etiqueta": [1, 0, 1],
                       "cruda": [0.95, 0.05, 0.50]})
    monkeypatch.setattr(seleccionar_casos, "puntuaciones_de_prueba",
                        lambda: df.copy())
    return seleccionar_casos


def test_las_rutas_cuelgan_de_rsna_raiz(con_puntuaciones_de_mentira, tmp_path,
                                        monkeypatch):
    monkeypatch.setenv("RSNA_RAIZ", str(tmp_path))
    casos = con_puntuaciones_de_mentira.seleccionar(n_por_perfil=2)
    crudo = tmp_path / "crudo" / "stage_2_train_images"
    alta = casos["positiva_clara"][0]
    assert alta["ruta_dcm"] == str(crudo / f"{alta['patientId']}.dcm")
    for nombre, perfil in casos.items():
        assert perfil, f"el perfil {nombre} salio vacio"
        for c in perfil:
            assert pathlib.Path(c["ruta_dcm"]).parent == crudo, c


def test_sin_rsna_raiz_seleccionar_se_detiene_nombrandola(
        con_puntuaciones_de_mentira, monkeypatch):
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    with pytest.raises(SystemExit, match="RSNA_RAIZ"):
        con_puntuaciones_de_mentira.seleccionar(n_por_perfil=2)


def test_el_modulo_no_guarda_ninguna_ruta_del_dataset():
    from pruebas import seleccionar_casos
    assert not hasattr(seleccionar_casos, "RAIZ")
    assert not hasattr(seleccionar_casos, "CRUDO")


def test_lo_que_llega_al_dataset_se_importa_sin_rsna_raiz():
    """En un proceso aparte, porque en este ya estan importados. Van los cinco
    ficheros desde los que se llega a `raiz_rsna()`: los dos modulos que la
    llaman, los dos que los importan y el script de la sesion. Si alguno leyera
    la variable al importarse, las pruebas que lo importan darian error de
    coleccion en un clon limpio; y en la maquina de desarrollo, que tiene la
    variable puesta, no se veria."""
    import os
    import subprocess
    entorno = {k: v for k, v in os.environ.items() if k != "RSNA_RAIZ"}
    codigo = "\n".join((
        "import importlib.util",
        "import pruebas.puntuaciones, pruebas.seleccionar_casos",
        "import pruebas.reproducir_casos, pruebas.caracterizar_conjunto",
        "spec = importlib.util.spec_from_file_location(",
        "    'preparar_sesion', 'scripts/preparar_sesion.py')",
        "spec.loader.exec_module(importlib.util.module_from_spec(spec))",
        "print('importados')"))
    r = subprocess.run([sys.executable, "-B", "-c", codigo], cwd=REPO, env=entorno,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "importados"
