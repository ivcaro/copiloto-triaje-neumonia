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

    Esta es la invariante DEBIL -que las odds se puedan calcular- y por si
    sola no basta: 1e-6 tambien la cumple y sigue siendo una certeza
    inventada. La invariante fuerte, que la cota sea la de la curva, la
    afirman las cuatro pruebas de mas abajo.
    """
    y, crudo = _puntuaciones()
    cal = ajustar_calibrador(y, crudo, PREVALENCIA, "prueba")
    for p in np.linspace(0.0, 1.0, 50):
        calibrada = cal.calibrar(float(p))
        assert 0.0 < calibrada < 1.0, f"calibrar({p}) devolvio {calibrada}"
        # Y por tanto las odds siempre se pueden calcular.
        assert calibrada / (1 - calibrada) > 0


# --- La cota de la evidencia: lo que los datos de validacion sostienen -------
#
# La isotonica satura en 0,0 y en 1,0 en los tramos de los extremos donde no
# queda ningun negativo (o ningun positivo). Con el calibrador desplegado eso
# es UN punto de 200 en cada lado. Recortar esos dos puntos a 1e-6 y 1-1e-6
# evita el p/(1-p) infinito, pero deja salir por `razon_de_verosimilitud` un
# 3,5e-06 y un 3,5e+06 que SP4 multiplicara por las odds de la regla clinica:
# un previo de 0,90 baja a 0,003% de posterior, frente al 12,8% del vecino
# inmediato que si tiene datos detras. La cota tiene que ser la curva.


def _curva_saturada_en_los_dos_extremos():
    """Una curva minima construida a mano, con 0,0 al principio y 1,0 al final.

    A mano y no ajustada: asi los valores sostenidos de los extremos son
    visibles en la propia prueba (0,1 y 0,9) y no dependen de una semilla.
    """
    x = np.linspace(0.0, 1.0, 7)
    y = np.array([0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0])
    return Calibrador(x, y, PREVALENCIA, "curva_saturada")


def test_la_probabilidad_no_pasa_de_la_certeza_que_la_curva_sostiene():
    """Por debajo del minimo de la curva sale el primer valor SOSTENIDO, y por
    encima del maximo el ultimo: 0,1 y 0,9, no 1e-6 ni 1-1e-6. Un epsilon es
    una certeza que ningun dato de validacion respalda."""
    cal = _curva_saturada_en_los_dos_extremos()

    assert cal.calibrar(-5.0) == pytest.approx(0.1)
    assert cal.calibrar(0.0) == pytest.approx(0.1)
    assert cal.calibrar(1.0) == pytest.approx(0.9)
    assert cal.calibrar(5.0) == pytest.approx(0.9)

    # Y explicitamente: NO es el recorte viejo.
    assert cal.calibrar(-5.0) != pytest.approx(1e-6)
    assert cal.calibrar(5.0) != pytest.approx(1 - 1e-6)


def test_la_razon_de_verosimilitud_esta_acotada_por_la_curva():
    """Barriendo el dominio entero -y saliendose por los dos lados-, la RV que
    SP4 va a multiplicar por las odds de la regla clinica nunca se escapa del
    intervalo que los valores sostenidos de la curva permiten."""
    cal = Calibrador.desde_json("servidor/calibrador.json")
    odds_previo = cal.prevalencia / (1 - cal.prevalencia)

    def rv_de(p):
        return (p / (1 - p)) / odds_previo

    minima = rv_de(cal.probabilidad_minima_sostenida)
    maxima = rv_de(cal.probabilidad_maxima_sostenida)

    for cruda in np.linspace(-0.5, 1.5, 501):
        rv = cal.razon_de_verosimilitud(float(cruda))
        assert minima <= rv <= maxima, f"RV({cruda}) = {rv}"

    # Los dos topes se ALCANZAN de verdad: si el barrido nunca llegara a
    # ellos, la prueba pasaria con una cota mucho mas laxa sin enterarse.
    assert cal.razon_de_verosimilitud(-0.5) == pytest.approx(minima)
    assert cal.razon_de_verosimilitud(1.5) == pytest.approx(maxima)


def test_el_calibrador_desplegado_acota_la_evidencia_donde_dice_el_contrato():
    """`docs/sp2-despliegue.md` publica los dos topes de la RV como parte del
    contrato que SP4 va a consumir. Si se reajusta el calibrador, esta prueba
    falla y obliga a actualizar el documento en vez de dejarlo mintiendo.
    """
    cal = Calibrador.desde_json("servidor/calibrador.json")
    odds_previo = cal.prevalencia / (1 - cal.prevalencia)

    assert cal.probabilidad_minima_sostenida == pytest.approx(0.004608, abs=5e-7)
    assert cal.probabilidad_maxima_sostenida == pytest.approx(0.956522, abs=5e-7)

    minima = (cal.probabilidad_minima_sostenida
              / (1 - cal.probabilidad_minima_sostenida)) / odds_previo
    maxima = (cal.probabilidad_maxima_sostenida
              / (1 - cal.probabilidad_maxima_sostenida)) / odds_previo
    assert minima == pytest.approx(0.0163, abs=5e-5)
    assert maxima == pytest.approx(77.32, abs=5e-3)


def test_una_curva_entera_saturada_no_divide_por_cero():
    """Caso degenerado que no deberia ocurrir: la curva completa a 0,0, sin un
    solo valor sostenido del que sacar la cota. No puede reventar ni devolver
    un 0 que haga estallar el p/(1-p) de SP4."""
    for constante in (0.0, 1.0):
        cal = Calibrador(np.linspace(0.0, 1.0, 10),
                         np.full(10, constante), PREVALENCIA, "degenerada")
        for p in (-1.0, 0.0, 0.5, 1.0, 2.0):
            calibrada = cal.calibrar(p)
            assert 0.0 < calibrada < 1.0, (constante, p, calibrada)
            assert cal.razon_de_verosimilitud(p) > 0.0


def test_acotar_la_evidencia_no_rompe_la_monotonia():
    """Acotar no puede desordenar: mas evidencia de imagen nunca puede dar
    menos probabilidad calibrada ni menos razon de verosimilitud, tampoco en
    los tramos donde la cota esta actuando."""
    cal = Calibrador.desde_json("servidor/calibrador.json")
    barrido = np.linspace(-0.5, 1.5, 501)
    calibradas = [cal.calibrar(float(p)) for p in barrido]
    razones = [cal.razon_de_verosimilitud(float(p)) for p in barrido]

    assert calibradas == sorted(calibradas)
    assert razones == sorted(razones)
