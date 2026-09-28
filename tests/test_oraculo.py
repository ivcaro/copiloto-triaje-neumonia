"""El modelo de umbral latente y su oráculo (spec de SP5 §4.4-§4.5, §8).

Todo en forma cerrada: nada de aquí sortea. Los valores esperados de la
correlación son los que el spec §4.5 declara, medidos el 27-sep sobre las
crudas congeladas; si cambian las crudas, cambian ellos y hay que decirlo.
"""
import numpy as np
import pytest
from scipy.special import ndtri

from copiloto_triaje.validacion import datos, oraculo


@pytest.fixture(scope="module")
def prueba():
    df = datos.cargar_crudas()
    _, q, _ = datos.evidencia_imagen(df["cruda"].values, datos.calibrador_desplegado())
    return q, df["etiqueta"].values.astype(int)


def test_los_recuentos_son_los_de_sp4():
    assert sum(oraculo.RECUENTOS[1]) == oraculo.TOTALES[1] == 134
    assert sum(oraculo.RECUENTOS[0]) == oraculo.TOTALES[0] == 780
    assert round(oraculo.rv_recuentos(0), 2) == 0.12
    assert round(oraculo.rv_recuentos(3), 2) == 1.64
    assert round(oraculo.rv_recuentos(5), 1) == 17.5
    assert np.allclose(oraculo.probabilidad_puntuacion(1).sum(), 1.0)


def test_la_fda_de_rango_medio_esta_definida_sobre_todo_q():
    clase = np.array([1.0, 2.0, 2.0, 3.0])
    fda = oraculo.fda_rango_medio
    assert fda(clase, [1.0]) == pytest.approx(0.5 / 4)          # rango medio propio
    assert fda(clase, [2.0]) == pytest.approx((1 + 0.5 * 2) / 4)  # empate: 1 menor + ½·2 iguales
    assert fda(clase, [2.5]) == pytest.approx(3 / 4)            # fuera de la clase: cuenta menores
    assert fda(clase, [-5.0]) == pytest.approx(0.5 / 4)         # la cota inferior
    assert fda(clase, [99.0]) == pytest.approx(1 - 0.5 / 4)     # la cota superior


def test_z_de_una_placa_negativa_es_el_rango_que_tendria_entre_las_positivas(prueba):
    """Spec §8: z_1(q) de una negativa = Φ⁻¹ de su rango medio al insertarla entre las positivas."""
    q, y = prueba
    z1, z0 = oraculo.puntuaciones_normales(q, y)
    i = int(np.flatnonzero(y == 0)[10])
    positivas = np.sort(q[y == 1])
    menores = np.sum(positivas < q[i])
    iguales = np.sum(positivas == q[i])
    n = positivas.size
    esperado = ndtri(np.clip((menores + 0.5 * iguales) / n, 0.5 / n, 1 - 0.5 / n))
    assert z1[i] == pytest.approx(esperado)
    assert z1.shape == z0.shape == q.shape


def test_con_rho_cero_los_umbrales_son_los_cuantiles_de_los_recuentos(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.0, 0.0)
    for clase, tau in ((1, m.tau1), (0, m.tau0)):
        acumulada = np.cumsum(oraculo.probabilidad_puntuacion(clase))[:-1]
        assert np.allclose(tau, ndtri(acumulada), atol=1e-9, rtol=0)
        assert np.all(np.diff(tau) > 0)


def test_con_rho_cero_la_rv_condicional_es_la_de_los_recuentos_en_todo_q(prueba):
    q, y = prueba
    lrv = oraculo.log_rv_condicional(oraculo.ajustar(q, y))
    esperado = np.log([oraculo.rv_recuentos(k) for k in range(6)])
    assert np.allclose(lrv, esperado[None, :], atol=1e-9, rtol=0)
    k = np.full(q.size, 3)
    assert np.allclose(oraculo.logit_oraculo(oraculo.ajustar(q, y), q, k),
                       q + np.log(oraculo.rv_recuentos(3)))


@pytest.mark.parametrize("rho", [0.3, 0.6])
def test_la_forma_cerrada_conserva_p_k_dado_y_con_dependencia(prueba, rho):
    """Spec §4.5 y §8: la media sobre la clase de P(k | q_i, y) son los recuentos (±1e-9)."""
    q, y = prueba
    m = oraculo.ajustar(q, y, rho, rho)
    p1, p0 = m.probabilidades()
    assert np.allclose(p1[y == 1].mean(axis=0), oraculo.probabilidad_puntuacion(1), atol=1e-9, rtol=0)
    assert np.allclose(p0[y == 0].mean(axis=0), oraculo.probabilidad_puntuacion(0), atol=1e-9, rtol=0)
    assert np.allclose(p1.sum(axis=1), 1.0) and np.allclose(p0.sum(axis=1), 1.0)
    assert np.all(p1 > 0) and np.all(p0 > 0)


@pytest.mark.parametrize("rho, esperadas", [(0.3, (0.275, 0.286)), (0.6, (0.558, 0.574))])
def test_la_correlacion_teorica_reproduce_los_valores_del_spec(prueba, rho, esperadas):
    q, y = prueba
    m = oraculo.ajustar(q, y, rho, rho)
    assert oraculo.correlacion_teorica(m, 0) == pytest.approx(esperadas[0], abs=0.005)
    assert oraculo.correlacion_teorica(m, 1) == pytest.approx(esperadas[1], abs=0.005)
    assert oraculo.correlacion_teorica(oraculo.ajustar(q, y), 1) == pytest.approx(0.0, abs=1e-9)


def test_el_oraculo_de_no_se_marginaliza_el_asma_con_la_regla_de_reparto(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.0)
    p1, p0 = m.probabilidades()
    pa = oraculo.PROBABILIDAD_ASMA_PRESENTE
    # k4 = 3 viene de k = 3 con asma presente o de k = 4 con asma ausente
    s1 = p1[:, 3] * pa[3] + p1[:, 4] * (1 - pa[4])
    s0 = p0[:, 3] * pa[3] + p0[:, 4] * (1 - pa[4])
    k4 = np.full(q.size, 3)
    assert np.allclose(oraculo.logit_oraculo_no_se(m, q, k4), q + np.log(s1) - np.log(s0))
    matriz = oraculo.matriz_k4()
    assert matriz.shape == (6, 5) and np.allclose(matriz.sum(axis=1), 1.0)
    assert matriz[0, 0] == 1.0 and matriz[5, 4] == 1.0 and matriz[4, 3] == pytest.approx(0.9)


def _anterior_logit_oraculo(m, q, k):
    """El oráculo tal como estaba: la RV condicional de la FILA i del ajuste."""
    return q + oraculo.log_rv_condicional(m)[np.arange(k.size), k]


def _anterior_logit_oraculo_no_se(m, q, k4):
    p1, p0 = m.probabilidades()
    mk = oraculo.matriz_k4()
    filas = np.arange(k4.size)
    return q + np.log((p1 @ mk)[filas, k4]) - np.log((p0 @ mk)[filas, k4])


def test_con_el_q_completo_el_oraculo_es_el_de_las_filas_del_ajuste(prueba):
    """Ruling 9: evaluar z_y en el q recibido no cambia nada con el q del ajuste."""
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.3)
    rng = np.random.default_rng(11)
    k = rng.integers(0, 6, q.size)
    k4 = rng.integers(0, 5, q.size)
    assert np.allclose(oraculo.logit_oraculo(m, q, k), _anterior_logit_oraculo(m, q, k),
                       atol=1e-12, rtol=0)
    assert np.allclose(oraculo.logit_oraculo_no_se(m, q, k4), _anterior_logit_oraculo_no_se(m, q, k4),
                       atol=1e-12, rtol=0)


def test_el_oraculo_es_funcion_del_q_que_recibe_y_no_de_la_fila(prueba):
    """Ruling 9: el bootstrap del §4.6 remuestrea placas con z y τ fijos. Con
    un remuestreo `idx`, el oráculo de (q[idx], k[idx]) tiene que ser el
    oráculo completo indexado; antes difería en ~3 600 de 3 811 filas."""
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.3)
    rng = np.random.default_rng(12)
    k = rng.integers(0, 6, q.size)
    k4 = rng.integers(0, 5, q.size)
    idx = rng.integers(0, q.size, q.size)
    assert np.allclose(oraculo.logit_oraculo(m, q[idx], k[idx]), oraculo.logit_oraculo(m, q, k)[idx],
                       atol=1e-12, rtol=0)
    assert np.allclose(oraculo.logit_oraculo_no_se(m, q[idx], k4[idx]),
                       oraculo.logit_oraculo_no_se(m, q, k4)[idx], atol=1e-12, rtol=0)
    # el de antes no lo era: así se ve que la prueba caza el defecto
    assert not np.allclose(_anterior_logit_oraculo(m, q[idx], k[idx]), oraculo.logit_oraculo(m, q, k)[idx])


def test_el_oraculo_rechaza_formas_distintas_y_puntuaciones_fuera_de_rango(prueba):
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.3)
    k = np.full(q.size, 3)
    with pytest.raises(ValueError, match="misma forma"):
        oraculo.logit_oraculo(m, q, k[:-1])
    with pytest.raises(ValueError, match="misma forma"):
        oraculo.logit_oraculo(m, q.reshape(1, -1), k.reshape(1, -1))
    with pytest.raises(ValueError, match="0..5"):
        oraculo.logit_oraculo(m, q[:3], [0, 6, 2])
    with pytest.raises(ValueError, match="0..5"):
        oraculo.logit_oraculo(m, q[:3], [0, -1, 2])
    with pytest.raises(ValueError, match="misma forma"):
        oraculo.logit_oraculo_no_se(m, q, k[:10])
    with pytest.raises(ValueError, match="0..4"):
        oraculo.logit_oraculo_no_se(m, q[:3], [0, 5, 2])


def test_la_trampa_del_rango_propio_invierte_la_conclusion(prueba):
    """Restricción 4: z_1 y z_0 en el MISMO q. Con el rango de la propia clase
    para las dos densidades, la fracción de log-RV conservada sale > 1 (la
    clínica «gana» información al ver la imagen), que es lo contrario de lo
    que el modelo simétrico produce. La prueba caza ese error."""
    q, y = prueba
    m = oraculo.ajustar(q, y, 0.3, 0.3)
    correcto = oraculo.log_rv_condicional(m)
    zp = m.z_propia()
    trampa = (np.log(oraculo.probabilidad_k_dado_q(zp, 0.3, m.tau1))
              - np.log(oraculo.probabilidad_k_dado_q(zp, 0.3, m.tau0)))
    ln_rv = np.log([oraculo.rv_recuentos(k) for k in range(6)])
    extremas = [0, 1, 4, 5]
    assert np.median(correcto[:, extremas] / ln_rv[extremas]) < 1.0
    assert np.median(trampa[:, extremas] / ln_rv[extremas]) > 1.0


def test_ajustar_rechaza_rho_fuera_de_rango(prueba):
    q, y = prueba
    with pytest.raises(ValueError):
        oraculo.ajustar(q, y, 1.0, 0.0)
    with pytest.raises(ValueError):
        oraculo.ajustar(q, y, 0.0, -0.1)
