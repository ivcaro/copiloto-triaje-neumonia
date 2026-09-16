"""Pruebas del reporte en Markdown y de la curva ROC (hallazgo I5).

El spec §7 y §12 los piden como entregables y hasta la oleada final solo se
escribia el JSON.
"""
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from copiloto_triaje.modelo.evaluacion import elegir_umbral, metricas_en_umbral
from copiloto_triaje.modelo.reporte import escribir_reporte_markdown, guardar_curva_roc


@pytest.fixture
def caso():
    """Un caso con clases separables pero no perfectas, y sus metricas ya
    calculadas con el mismo camino que usa el notebook."""
    rng = np.random.default_rng(3)
    y = np.array([1] * 120 + [0] * 380)
    score = np.where(y == 1, rng.normal(0.78, 0.12, 500), rng.normal(0.30, 0.12, 500))
    score = np.clip(score, 0.0, 1.0)
    umbral, m_val, paso = elegir_umbral(y, score)
    m_test = metricas_en_umbral(y, score, umbral)
    return y, score, umbral, paso, m_val, m_test


def test_la_curva_roc_se_guarda_como_svg_valido(tmp_path, caso):
    y, score, umbral, *_ = caso
    ruta = guardar_curva_roc(y, score, tmp_path / "curva_roc.svg", umbral=umbral)

    assert ruta.exists()
    contenido = ruta.read_text(encoding="utf-8")
    # Debe ser XML bien formado, no una cadena que se parezca a un SVG.
    raiz = ET.fromstring(contenido)
    assert raiz.tag.endswith("svg")

    # La curva en si: una polilinea con al menos un punto por umbral distinto.
    polilineas = [e for e in raiz.iter() if e.tag.endswith("polyline")]
    assert len(polilineas) == 1
    puntos = polilineas[0].attrib["points"].split()
    assert len(puntos) >= 3

    assert "AUC = " in contenido
    assert "umbral" in contenido  # el punto de operacion elegido esta marcado


def test_la_curva_roc_tambien_se_guarda_sin_punto_de_operacion(tmp_path, caso):
    y, score, *_ = caso
    ruta = guardar_curva_roc(y, score, tmp_path / "sub" / "roc.svg")
    assert ruta.exists()
    ET.fromstring(ruta.read_text(encoding="utf-8"))


def test_el_reporte_markdown_lleva_umbral_regla_matriz_y_auc(tmp_path, caso):
    y, score, umbral, paso, m_val, m_test = caso
    historial = [
        {"epoca": 0, "fase": "cabeza", "perdida": 0.8, "recall": 0.70,
         "especificidad": 0.76, "auc": 0.80, "umbral": 0.55,
         "recall_umbral_fijo": 1.0, "especificidad_umbral_fijo": 0.01},
        {"epoca": 1, "fase": "ajuste", "perdida": 0.6, "recall": 0.86,
         "especificidad": 0.72, "auc": 0.88, "umbral": 0.58,
         "recall_umbral_fijo": 0.98, "especificidad_umbral_fijo": 0.10},
    ]
    ruta_roc = guardar_curva_roc(y, score, tmp_path / "curva_roc.svg", umbral=umbral)
    ruta = escribir_reporte_markdown(
        tmp_path / "reporte_metricas.md", umbral=umbral, paso=paso,
        metricas_validacion=m_val, metricas_prueba=m_test,
        historial=historial, mejor_epoca=1, ruta_roc=ruta_roc,
        omitidos=[{"archivo": "a.dcm", "motivo": "InvalidDicomError: x"}])

    texto = ruta.read_text(encoding="utf-8")

    # Umbral elegido y regla aplicada, con su explicacion en castellano.
    assert f"{umbral:.4f}" in texto
    assert paso in texto
    assert "Paso " in texto or "Ningun umbral" in texto

    # Matriz de confusion completa, con las cuatro celdas.
    assert "Matriz de confusion" in texto
    for clave in ("tp", "tn", "fp", "fn"):
        assert str(m_test[clave]) in texto

    # El AUC del conjunto de PRUEBA (hallazgo I2) llega al reporte y se juzga
    # contra el criterio del spec.
    assert "AUC-ROC" in texto
    assert f"{m_test['auc']:.3f}" in texto

    # Curva ROC enlazada de forma relativa, e historial con la mejor epoca.
    assert "![Curva ROC](curva_roc.svg)" in texto
    assert "<- mejor" in texto
    assert "Archivos omitidos" in texto


def test_el_reporte_marca_en_rojo_un_criterio_que_no_se_cumple(tmp_path):
    """El reporte tiene que decir que NO se cumple, no limitarse a imprimir el
    numero: el spec pide documentar el resultado con honestidad."""
    pobre = {"recall": 0.55, "especificidad": 0.60, "precision": 0.4, "f1": 0.46,
             "auc": 0.62, "tp": 11, "tn": 12, "fp": 8, "fn": 9, "umbral": 0.5}
    ruta = escribir_reporte_markdown(
        tmp_path / "r.md", umbral=0.5, paso="paso_3_se_conserva_paso_1",
        metricas_validacion=pobre, metricas_prueba=pobre)
    texto = ruta.read_text(encoding="utf-8")
    assert texto.count("**NO CUMPLE**") == 3


def test_el_reporte_avisa_cuando_falta_el_auc_de_prueba(tmp_path):
    """Si alguien vuelve a reportar la prueba con `metricas_binarias` (sin
    AUC), el reporte no puede disimularlo: es uno de los cuatro criterios."""
    sin_auc = {"recall": 0.9, "especificidad": 0.8, "precision": 0.5, "f1": 0.64,
               "tp": 18, "tn": 16, "fp": 4, "fn": 2}
    ruta = escribir_reporte_markdown(
        tmp_path / "r.md", umbral=0.5, paso="paso_1_especificidad_objetivo",
        metricas_validacion=sin_auc, metricas_prueba=sin_auc)
    texto = ruta.read_text(encoding="utf-8")
    assert "NO REPORTADO" in texto
