"""El generador de la simulación semisintética (spec de SP5 §4.2, §8).

Las comprobaciones empíricas agregan R = 50 sorteos por placa, como pide el
§8: con un solo sorteo las tolerancias caerían dentro del ruido de muestreo
y un generador correcto fallaría la mitad de las veces.
"""
import numpy as np
import pandas as pd
import pytest

from copiloto_triaje.servicio.heckerling import (
    PULSO_CORTE_LPM, TEMPERATURA_CORTE_C, puntuar,
)
from copiloto_triaje.validacion import datos, generador, oraculo

R = 50


@pytest.fixture(scope="module")
def prueba():
    df = datos.cargar_crudas()
    _, q, _ = datos.evidencia_imagen(df["cruda"].values, datos.calibrador_desplegado())
    return q, df["etiqueta"].values.astype(int)


def _sorteos(modelo):
    ks = np.concatenate([generador.sortear_puntuacion(modelo, np.random.default_rng(s))
                         for s in range(1, R + 1)])
    return ks, np.tile(modelo.etiquetas, R), np.tile(modelo.z_propia(), R)


@pytest.mark.parametrize("rho", [0.0, 0.6])
def test_p_k_dado_y_empirica_coincide_con_los_recuentos(prueba, rho):
    q, y = prueba
    ks, ys, _ = _sorteos(oraculo.ajustar(q, y, rho, rho))
    for clase in (0, 1):
        empirica = np.bincount(ks[ys == clase], minlength=6) / np.sum(ys == clase)
        assert np.allclose(empirica, oraculo.probabilidad_puntuacion(clase), atol=0.01)


@pytest.mark.parametrize("rho", [0.0, 0.3, 0.6])
def test_la_correlacion_empirica_dentro_de_cada_clase_es_la_teorica(prueba, rho):
    """Spec §8: Pearson entre k y z_y(q) dentro de la clase, contra la forma cerrada (±0,03)."""
    q, y = prueba
    m = oraculo.ajustar(q, y, rho, rho)
    ks, ys, z = _sorteos(m)
    for clase in (0, 1):
        r = np.corrcoef(ks[ys == clase], z[ys == clase])[0, 1]
        esperada = 0.0 if rho == 0.0 else oraculo.correlacion_teorica(m, clase)
        assert r == pytest.approx(esperada, abs=0.03)


def test_repartir_da_exactamente_k_puntos_y_respeta_el_asma():
    """La puntuación que `heckerling.puntuar` calcula sobre lo repartido es k,
    siempre; y el punto de «sin asma» sigue la regla del §4.2."""
    rng = np.random.default_rng(7)
    sin_asma = {k: [] for k in range(6)}
    for _ in range(6000):
        k = int(rng.integers(0, 6))
        h = generador.repartir(k, rng)
        assert puntuar({s: h[s] for s in generador.SIGNOS}, h["asma_real"]) == (k,)
        assert h["k4"] == k - (h["asma_real"] == "no")
        sin_asma[k].append(h["asma_real"] == "no")
    assert not any(sin_asma[0]) and all(sin_asma[5])
    for k in (1, 2, 3, 4):
        assert np.mean(sin_asma[k]) == pytest.approx(0.9, abs=0.03)
    with pytest.raises(ValueError):
        generador.repartir(6, rng)


def test_los_numeros_caen_en_su_rejilla_y_el_20_por_ciento_en_el_corte():
    """Spec §4.2 paso 3 y §8: décimas y enteros; 37,9 / 101 exactos si el
    hallazgo está presente y 37,8 / 100 exactos si está ausente, en el 20 %."""
    rng = np.random.default_rng(11)
    filas = [generador.repartir(int(rng.integers(0, 6)), rng) for _ in range(20000)]
    t = np.array([f["temperatura_c"] for f in filas])
    fc = np.array([f["frecuencia_cardiaca"] for f in filas])
    assert np.all(np.round(t, 1) == t)
    assert all(isinstance(f["frecuencia_cardiaca"], int) for f in filas)
    presentes_t = t > TEMPERATURA_CORTE_C
    assert t[~presentes_t].min() >= 36.0 and t[presentes_t].max() <= 39.5
    assert np.mean(t[presentes_t] == 37.9) == pytest.approx(0.2, abs=0.02)
    assert np.mean(t[~presentes_t] == TEMPERATURA_CORTE_C) == pytest.approx(0.2, abs=0.02)
    presentes_p = fc > PULSO_CORTE_LPM
    assert fc[~presentes_p].min() >= 60 and fc[presentes_p].max() <= 130
    assert np.mean(fc[presentes_p] == 101) == pytest.approx(0.2, abs=0.02)
    assert np.mean(fc[~presentes_p] == PULSO_CORTE_LPM) == pytest.approx(0.2, abs=0.02)


def test_no_se_es_el_10_por_ciento_e_independiente_de_la_etiqueta(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y)
    diferencias, fracciones = [], []
    for semilla in range(1, R + 1):
        df = generador.generar(m, semilla)
        no_se = (df["asma"] == "no_se").values
        fracciones.append(no_se.mean())
        diferencias.append(no_se[y == 1].mean() - no_se[y == 0].mean())
    assert np.mean(fracciones) == pytest.approx(generador.FRACCION_NO_SE, abs=0.01)
    assert abs(np.mean(diferencias)) < 0.01
    assert list(df.columns) == list(generador.COLUMNAS) and len(df) == y.size
    assert set(df["asma"]) <= {"si", "no", "no_se"} and set(df["asma_real"]) <= {"si", "no"}


def test_generar_es_reproducible_por_semilla(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.0)
    a, b = generador.generar(m, 5), generador.generar(m, 5)
    pd.testing.assert_frame_equal(a, b)
    assert not generador.generar(m, 6).equals(a)


def test_sortear_caso_fuerza_el_asma_declarada(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.3)
    caso = generador.sortear_caso(m, 0, np.random.default_rng(1), asma="no_se")
    assert caso["asma"] == "no_se" and caso["asma_real"] in ("si", "no")
    signos = {s: caso[s] for s in generador.SIGNOS}
    assert puntuar(signos, "no_se") == (caso["k4"], caso["k4"] + 1)
    libre = generador.sortear_caso(m, 0, np.random.default_rng(1))
    assert libre["asma"] == libre["asma_real"]


def test_hallazgos_lleva_tipos_de_python(prueba):
    """`heckerling.validar_hallazgos` rechaza `numpy.bool_`: los tipos son de Python."""
    q, y = prueba
    df = generador.generar(oraculo.ajustar(q, y), semilla=1)
    h = generador.hallazgos(df.iloc[0])
    assert set(h) == set(generador.SIGNOS) | {"asma"}
    assert type(h["crepitantes"]) is bool and type(h["murmullo_disminuido"]) is bool
    assert type(h["frecuencia_cardiaca"]) is int and type(h["temperatura_c"]) is float
    assert type(h["asma"]) is str
