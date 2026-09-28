"""Escenario 0A: la aritmética del sistema, caso a caso contra el generador
(spec de SP5 §4.4, §8, §11.1).

Tres comprobaciones deterministas sobre las 3 811 placas de prueba con
dependencia nula, y las mutaciones que tienen que romperlas. No hay
estadística: un caso basta para que falle. Es lo que la Semana 1 §5.2
prometió: «la probabilidad posterior calculada debe coincidir con la del
generador de casos».
"""
import math

import numpy as np
import pytest

from copiloto_triaje.servicio import heckerling
from copiloto_triaje.servicio.heckerling import (
    RV_POR_PUNTUACION, combinacion, combinar, mas_informativa,
)
from copiloto_triaje.validacion import datos, generador, oraculo

TOLERANCIA = 0.015   # el redondeo máximo de las RV publicadas (0,013 en k = 1)
SEMILLA = 1


def _logit(p):
    return math.log(p / (1.0 - p))


@pytest.fixture(scope="module")
def escenario():
    df = datos.cargar_crudas()
    cal = datos.calibrador_desplegado()
    _, q, rv = datos.evidencia_imagen(df["cruda"].values, cal)
    modelo = oraculo.ajustar(q, df["etiqueta"].values.astype(int))   # ρ1 = ρ0 = 0
    clinica = generador.generar(modelo, SEMILLA).to_dict("records")
    return cal.prevalencia, q, rv, modelo, clinica


def bloques(prevalencia, rv, clinica):
    return [combinacion(prevalencia, generador.hallazgos(fila), float(r))
            for fila, r in zip(clinica, rv)]


def fallos_0a1(prevalencia, rv, clinica):
    """Casos con asma conocida cuya puntuación del sistema no es la k del generador."""
    return [i for i, (fila, b) in enumerate(zip(clinica, bloques(prevalencia, rv, clinica)))
            if fila["asma"] != "no_se" and b["puntuacion"][0] != fila["k"]]


def fallos_0a3(prevalencia, q, rv, modelo, clinica):
    """Casos en que la aritmética sin redondear se aleja del oráculo más de la
    tolerancia. La k verdadera va en los dos lados, también con el asma oculta."""
    k = np.array([fila["k"] for fila in clinica])
    esperado = oraculo.logit_oraculo(modelo, q, k)
    sistema = np.array([_logit(combinar(prevalencia, RV_POR_PUNTUACION[int(kk)], float(r)))
                        for kk, r in zip(k, rv)])
    return list(np.flatnonzero(np.abs(sistema - esperado) > TOLERANCIA))


def test_0a1_la_puntuacion_del_sistema_es_la_del_generador(escenario):
    prevalencia, q, rv, modelo, clinica = escenario
    conocidas = sum(fila["asma"] != "no_se" for fila in clinica)
    assert conocidas > 3000
    assert fallos_0a1(prevalencia, rv, clinica) == []


def test_0a2_el_bloque_no_altera_la_aritmetica(escenario):
    """`independencia`, `dependencia`, `minima` y `maxima` son exactamente
    `round(combinar(...), 4)` de lo que heckerling.py dice que son."""
    prevalencia, q, rv, modelo, clinica = escenario
    for b, r in zip(bloques(prevalencia, rv, clinica), rv):
        r = float(r)
        for i, rvc in enumerate(b["rv_clinica"]):
            assert b["independencia"][i] == round(combinar(prevalencia, rvc, r), 4)
            if b["concordantes"]:
                assert b["dependencia"][i] == round(
                    combinar(prevalencia, mas_informativa(rvc, r), 1.0), 4)
        todas = b["independencia"] + (b["dependencia"] or [])
        assert b["minima"] == min(todas) and b["maxima"] == max(todas)


def test_0a3_la_aritmetica_coincide_con_el_oraculo_en_los_3811_casos(escenario):
    prevalencia, q, rv, modelo, clinica = escenario
    assert len(clinica) == 3811
    assert fallos_0a3(prevalencia, q, rv, modelo, clinica) == []


def test_0a3_la_diferencia_es_exactamente_el_redondeo_de_las_rv_publicadas(escenario):
    prevalencia, q, rv, modelo, clinica = escenario
    k = np.array([fila["k"] for fila in clinica])
    sistema = np.array([_logit(combinar(prevalencia, RV_POR_PUNTUACION[int(kk)], float(r)))
                        for kk, r in zip(k, rv)])
    diferencia = sistema - oraculo.logit_oraculo(modelo, q, k)
    esperada = np.array([math.log(RV_POR_PUNTUACION[int(kk)] / oraculo.rv_recuentos(int(kk)))
                         for kk in k])
    assert np.allclose(diferencia, esperada, atol=1e-9)
    assert 0.010 < np.abs(esperada).max() < TOLERANCIA


@pytest.mark.parametrize("k, mutada", [(5, 1.75), (4, 7.81), (3, 1.46)])
def test_una_rv_mutada_rompe_0a3_en_todos_los_casos_con_esa_puntuacion(
        escenario, monkeypatch, k, mutada):
    prevalencia, q, rv, modelo, clinica = escenario
    monkeypatch.setitem(RV_POR_PUNTUACION, k, mutada)
    con_esa_k = {i for i, fila in enumerate(clinica) if fila["k"] == k}
    assert con_esa_k
    assert set(fallos_0a3(prevalencia, q, rv, modelo, clinica)) == con_esa_k


@pytest.mark.parametrize("atributo, corte, afectado", [
    # el corte movido a 38,0: 37,9 y 38,0 dejan de puntuar
    ("TEMPERATURA_CORTE_C", 38.0, lambda t, fc: 37.8 < t <= 38.0),
    # 37,79 equivale a `>=` sobre la rejilla de décimas: 37,8 pasa a puntuar (D6)
    ("TEMPERATURA_CORTE_C", 37.79, lambda t, fc: t == 37.8),
    # 99 equivale a `>=` en el pulso: 100 pasa a puntuar
    ("PULSO_CORTE_LPM", 99, lambda t, fc: fc == 100),
])
def test_un_corte_mutado_rompe_0a1_caso_a_caso(escenario, monkeypatch, atributo, corte, afectado):
    prevalencia, q, rv, modelo, clinica = escenario
    monkeypatch.setattr(heckerling, atributo, corte)
    afectados = {i for i, fila in enumerate(clinica)
                 if fila["asma"] != "no_se"
                 and afectado(fila["temperatura_c"], fila["frecuencia_cardiaca"])}
    assert len(afectados) > 100
    assert set(fallos_0a1(prevalencia, rv, clinica)) == afectados
