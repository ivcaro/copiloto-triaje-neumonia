"""Las métricas de la simulación (spec de SP5 §4.6, §8): cada una sobre
vectores cuyos valores se conocen a mano."""
import math

import numpy as np
import pytest

from copiloto_triaje.validacion import metricas


def _logit(p):
    return math.log(p / (1.0 - p))


def _grupos(*grupos):
    """(y, p) a partir de (p, casos, positivos) por grupo."""
    y, p = [], []
    for prob, casos, positivos in grupos:
        y += [1] * positivos + [0] * (casos - positivos)
        p += [prob] * casos
    return np.array(y), np.array(p)


def test_logit_acota_los_extremos():
    assert metricas.logit([0.5])[0] == 0.0
    assert metricas.logit([0.0])[0] == pytest.approx(_logit(metricas.MARGEN))
    assert metricas.logit([1.0])[0] == pytest.approx(-_logit(metricas.MARGEN))


def test_auc_y_brier_a_mano():
    assert metricas.auc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == pytest.approx(0.75)
    assert metricas.brier([0, 1], [0.2, 0.7]) == pytest.approx((0.04 + 0.09) / 2)


def test_un_modelo_calibrado_tiene_pendiente_uno_e_intercepto_cero():
    y, p = _grupos((0.2, 10, 2), (0.8, 10, 8))
    assert metricas.pendiente_de_calibracion(y, p) == pytest.approx(1.0, abs=1e-8)
    assert metricas.intercepto_de_calibracion(y, p) == pytest.approx(0.0, abs=1e-8)


def test_un_modelo_que_exagera_tiene_pendiente_menor_que_uno():
    """Dice 0,1 y 0,9 donde ocurre 0,2 y 0,8: la pendiente es el cociente de logits."""
    y, p = _grupos((0.1, 10, 2), (0.9, 10, 8))
    assert metricas.pendiente_de_calibracion(y, p) == pytest.approx(
        _logit(0.8) / _logit(0.9), abs=1e-8)


def test_un_modelo_que_se_queda_corto_tiene_pendiente_mayor_que_uno():
    y, p = _grupos((0.3, 10, 1), (0.7, 10, 9))
    assert metricas.pendiente_de_calibracion(y, p) == pytest.approx(
        _logit(0.9) / _logit(0.7), abs=1e-8)


def test_sin_pendiente_finita_se_dice_y_no_se_devuelve_la_ultima_iteracion():
    """Clases separadas del todo: la verosimilitud no tiene máximo finito."""
    with pytest.raises(ArithmeticError, match="no converge"):
        metricas.pendiente_de_calibracion([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9])
    # todas las p iguales: la pendiente no está identificada
    with pytest.raises(ArithmeticError, match="no converge"):
        metricas.pendiente_de_calibracion([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5])


def test_el_intercepto_es_el_desplazamiento_en_log_odds():
    """Dice 0,2 donde ocurre 0,3: hay que sumar logit 0,3 − logit 0,2."""
    y, p = _grupos((0.2, 10, 3))
    assert metricas.intercepto_de_calibracion(y, p) == pytest.approx(
        _logit(0.3) - _logit(0.2), abs=1e-9)


def test_la_pendiente_coincide_con_la_de_sklearn_sin_penalizar():
    from sklearn.linear_model import LogisticRegression
    rng = np.random.default_rng(7)
    p = rng.uniform(0.02, 0.98, 500)
    y = (rng.random(500) < p ** 1.5).astype(int)
    modelo = LogisticRegression(C=np.inf, solver="lbfgs", tol=1e-10, max_iter=5000).fit(
        metricas.logit(p).reshape(-1, 1), y)
    assert metricas.pendiente_de_calibracion(y, p) == pytest.approx(
        float(modelo.coef_[0, 0]), abs=1e-4)


def test_ece_a_mano_con_dos_bins():
    y, p = np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])
    assert metricas.ece(y, p, orden=[0, 1, 2, 3], bins=2) == pytest.approx(0.15)


def test_los_empates_de_p_se_rompen_con_el_orden_declarado():
    y, p = np.array([1, 0, 1, 0]), np.array([0.5, 0.5, 0.5, 0.5])
    assert metricas.ece(y, p, orden=[0, 1, 2, 3], bins=2) == pytest.approx(0.0)
    assert metricas.ece(y, p, orden=[0, 2, 1, 3], bins=2) == pytest.approx(0.5)


def test_la_fiabilidad_reparte_todos_los_casos_en_bins_de_igual_masa():
    rng = np.random.default_rng(3)
    p = rng.uniform(0.0, 1.0, 105)
    y = (rng.random(105) < p).astype(int)
    curva = metricas.fiabilidad(y, p, orden=np.arange(105))
    assert len(curva) == metricas.BINS
    assert sum(b["n"] for b in curva) == 105
    assert {b["n"] for b in curva} == {10, 11}
    medias = [b["p_media"] for b in curva]
    assert medias == sorted(medias)
    assert metricas.ece(y, p, np.arange(105)) == pytest.approx(
        sum(b["n"] / 105 * abs(b["observada"] - b["p_media"]) for b in curva))


def test_el_suelo_de_la_ece_es_reproducible_con_semilla():
    rng = np.random.default_rng(5)
    p = rng.uniform(0.05, 0.95, 400)
    orden = np.arange(400)
    a = metricas.suelo_de_ece(p, orden, repeticiones=50, semilla=11)
    assert a == metricas.suelo_de_ece(p, orden, repeticiones=50, semilla=11)
    assert a != metricas.suelo_de_ece(p, orden, repeticiones=50, semilla=12)
    assert 0.0 < a["media"] < a["p95"] < 0.1


def test_resumen_de_modelo_lleva_las_cinco_cifras():
    y, p = _grupos((0.2, 10, 2), (0.8, 10, 8))
    r = metricas.resumen_de_modelo(y, p, np.arange(20))
    assert set(r) == {"auc", "brier", "pendiente", "intercepto", "ece"}
    assert all(isinstance(v, float) for v in r.values())
    assert r == {"auc": metricas.auc(y, p), "brier": metricas.brier(y, p),
                 "pendiente": metricas.pendiente_de_calibracion(y, p),
                 "intercepto": metricas.intercepto_de_calibracion(y, p),
                 "ece": metricas.ece(y, p, np.arange(20))}


def test_vectores_de_distinta_forma_se_rechazan():
    with pytest.raises(ValueError, match="misma forma"):
        metricas.brier([0, 1], [0.2])
    with pytest.raises(ValueError, match="misma forma"):
        metricas.auc([], [])


# La horquilla: los casos de borde del spec §8. Dependencia en 0, independencia
# en 1 (evidencia a favor) salvo el ultimo, que apunta hacia abajo.
L_DEP = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
L_IND = [1.0, 1.0, 1.0, 1.0, 0.0, 0.0]
L_ORA = [0.5,     # dentro
         1.01,    # mas alla de la independencia, pero dentro de ε: cuenta dentro
         1.02,    # mas alla de la independencia en mas de ε: cola «sobre»
         -0.02,   # mas alla del extremo conservador en mas de ε: cola «bajo»
         0.3,     # Δ = 0: sin horquilla
         -0.02]   # evidencia en contra: mas alla de la independencia (0) en 0,02


def test_la_horquilla_en_los_casos_de_borde():
    h = metricas.horquilla(L_ORA, L_DEP, L_IND)
    assert h["n"] == 5 and h["sin_horquilla"] == 1
    assert h["bajo"] == pytest.approx(1 / 5)
    assert h["sobre"] == pytest.approx(2 / 5)
    assert h["contencion"] == pytest.approx(2 / 5)
    # λ: 0,5; 1,01; 1,02; −0,02; y (−0,02 − 1)/(0 − 1) = 1,02
    assert h["lambda"]["mediana"] == pytest.approx(1.01)
    assert h["lambda"]["q1"] == pytest.approx(0.5)
    assert h["lambda"]["q3"] == pytest.approx(1.02)


def test_la_tolerancia_es_la_de_0a3_y_se_puede_cambiar():
    assert metricas.EPSILON == 0.015
    h = metricas.horquilla(L_ORA, L_DEP, L_IND, epsilon=0.0)
    assert h["sobre"] == pytest.approx(3 / 5) and h["contencion"] == pytest.approx(1 / 5)
    assert h["bajo"] == pytest.approx(1 / 5)
    # y del lado conservador: 0,01 más allá cuenta dentro; 0,02, fuera
    dentro = metricas.horquilla([-0.01, 1.01], [0.0, 1.0], [1.0, 0.0])
    assert (dentro["bajo"], dentro["sobre"], dentro["contencion"]) == (0.0, 0.0, 1.0)
    fuera = metricas.horquilla([-0.02, 1.02], [0.0, 1.0], [1.0, 0.0])
    assert (fuera["bajo"], fuera["sobre"], fuera["contencion"]) == (1.0, 0.0, 0.0)


def test_sin_ningun_caso_con_horquilla_no_hay_fracciones():
    h = metricas.horquilla([0.3], [0.0], [0.0])
    assert h == {"n": 0, "sin_horquilla": 1,
                 "lambda": {"q1": None, "mediana": None, "q3": None},
                 "bajo": None, "sobre": None, "contencion": None}
    assert metricas.horquilla([], [], [])["n"] == 0


def test_un_valor_sin_dato_no_cuenta_como_contenido():
    """Un NaN no es mayor ni menor que nada: sin la guarda, un caso sin
    horquilla (un discordante, con la dependencia vacía) contaría «dentro»
    aunque el oráculo quedara a 4 log-odds."""
    with pytest.raises(ValueError, match="sin dato"):
        metricas.horquilla([0.5, 5.0], [0.0, None], [1.0, 1.0])
    with pytest.raises(ValueError, match="sin dato"):
        metricas.horquilla([float("nan")], [0.0], [1.0])
    with pytest.raises(ValueError, match="sin dato"):
        metricas.contencion_en_rango([0.5], [float("nan")], [1.0])
    with pytest.raises(ValueError, match="sin dato"):
        metricas.error_puntual([0.5], [float("nan")])


def test_los_vectores_de_log_odds_tienen_que_casar():
    with pytest.raises(ValueError, match="misma forma"):
        metricas.horquilla([0.5], [0.0, 0.0], [1.0, 1.0])
    with pytest.raises(ValueError, match="misma forma"):
        metricas.error_puntual([1.0], [0.5, 2.5, 0.0])
    with pytest.raises(ValueError, match="misma forma"):
        metricas.contencion_en_rango([0.5, 0.5], [0.0], [1.0])
    with pytest.raises(ValueError, match="mínima"):
        metricas.contencion_en_rango([0.5], [1.0], [0.0])


def test_error_puntual_y_contencion_en_rango():
    e = metricas.error_puntual([1.0, 2.0, 0.0], [0.5, 2.5, 0.0])
    assert e == {"n": 3, "error_abs_mediano": 0.5, "sesgo_mediano": 0.0}
    assert metricas.error_puntual([], [])["error_abs_mediano"] is None
    c = metricas.contencion_en_rango([0.0, 1.01, 1.02, -0.02], [0.0] * 4, [1.0] * 4)
    assert c["n"] == 4
    assert (c["bajo"], c["sobre"], c["contencion"]) == pytest.approx((0.25, 0.25, 0.5))
    assert metricas.contencion_en_rango([], [], [])["contencion"] is None


def test_percentiles_ignora_lo_que_no_es_un_numero():
    lo, hi = metricas.percentiles(list(range(1, 101)) + [float("nan")])
    assert (lo, hi) == pytest.approx((3.475, 97.525))
    assert metricas.percentiles([float("nan")]) == [None, None]


def test_cuantiles_ponderados():
    q = metricas.cuantiles_ponderados([3.0, 1.0, 2.0], [2.0, 1.0, 1.0])
    assert list(q) == [1.0, 2.0, 3.0]
    # con un peso nulo el valor no cuenta
    assert list(metricas.cuantiles_ponderados([5.0, 1.0], [0.0, 1.0], (0.5,))) == [1.0]
    with pytest.raises(ValueError, match="masa positiva"):
        metricas.cuantiles_ponderados([1.0], [0.0])
