"""Pruebas del calibrador.

Lo que se protege aqui es que la evidencia de imagen que SP4 va a meter en la
formula bayesiana signifique lo que dice significar. La salida cruda del
modelo NO es una probabilidad -se entreno con pos_weight=3,44- y combinar ese
numero con la probabilidad previa de la regla clinica da un posterior
equivocado sin que nada falle de forma visible.
"""
import json

import numpy as np
import pytest

from copiloto_triaje.servicio.calibracion import Calibrador, ajustar_calibrador

PREVALENCIA = 0.2215


def _puntuaciones(n=2000, semilla=3):
    """Puntuaciones separables con la prevalencia real del dataset."""
    rng = np.random.default_rng(semilla)
    y = (rng.random(n) < PREVALENCIA).astype(int)
    crudo = rng.normal(1.7 * y, 1.0)
    return y, 1 / (1 + np.exp(-crudo))


def test_calibrar_acerca_la_media_a_la_prevalencia():
    """Una probabilidad calibrada promedia, sobre la poblacion, la prevalencia
    real. La cruda no: el pos_weight la empuja hacia arriba."""
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "prueba")
    calibradas = np.array([cal.calibrar(p) for p in crudo])

    assert abs(calibradas.mean() - PREVALENCIA) < 0.02, (
        f"media calibrada {calibradas.mean():.4f}, prevalencia {PREVALENCIA}")


def test_la_razon_de_verosimilitud_es_coherente_con_la_probabilidad():
    """RV = odds_posterior / odds_previo. Si esta relacion se rompe, SP4
    calcula mal el posterior y nadie lo nota."""
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "prueba")
    odds_previo = PREVALENCIA / (1 - PREVALENCIA)

    for p in (0.1, 0.35, 0.6, 0.9):
        calibrada = cal.calibrar(p)
        esperada = (calibrada / (1 - calibrada)) / odds_previo
        assert cal.razon_de_verosimilitud(p) == pytest.approx(esperada, rel=1e-6)


def test_la_razon_de_verosimilitud_crece_con_la_puntuacion():
    """Mas evidencia de imagen no puede dar menos razon de verosimilitud."""
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "prueba")
    valores = [cal.razon_de_verosimilitud(p) for p in (0.05, 0.25, 0.5, 0.75, 0.95)]
    assert valores == sorted(valores)


def test_el_calibrador_va_y_vuelve_por_json(tmp_path):
    """Viaja en el repositorio como JSON -unos kilobytes que si se versionan-
    y no como un objeto de scikit-learn serializado, que ataria el despliegue
    a la version exacta de la libreria."""
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "corrida_x")
    ruta = tmp_path / "calibrador.json"
    cal.a_json(ruta)

    recuperado = Calibrador.desde_json(ruta)
    for p in (0.1, 0.5, 0.9):
        assert recuperado.calibrar(p) == pytest.approx(cal.calibrar(p))
    assert json.loads(ruta.read_text(encoding="utf-8"))["procedencia"] == "corrida_x"


def test_el_calibrador_registra_de_donde_sale(tmp_path):
    """Un calibrador sin procedencia es un numero magico: nadie puede saber si
    corresponde a los pesos que esta sirviendo el contenedor."""
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "efficientnet_b0_320px")
    assert cal.procedencia == "efficientnet_b0_320px"
    assert cal.prevalencia == PREVALENCIA


def test_calibrar_nunca_devuelve_cero_ni_uno_exactos():
    """La isotonica SI devuelve 0,0 y 1,0 exactos en los extremos: con la
    semilla de estas pruebas, 38 de 200 puntos de la curva son 0,0 y 2 son
    1,0. Dejarlos salir seria una mina para SP4, que lo primero que hara con
    la probabilidad es calcular p/(1-p).
    """
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "prueba")
    for p in np.linspace(0.0, 1.0, 50):
        calibrada = cal.calibrar(float(p))
        assert 0.0 < calibrada < 1.0, f"calibrar({p}) devolvio {calibrada}"
        # Y por tanto las odds siempre se pueden calcular.
        assert calibrada / (1 - calibrada) > 0
