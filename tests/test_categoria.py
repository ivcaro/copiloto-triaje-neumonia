"""La categoría del sistema, fijada antes de la sesión (spec de SP5 §5.3, §8)."""
import itertools
import json
import pathlib

import numpy as np
import pytest

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE, combinacion
from copiloto_triaje.validacion import categoria

REPO = pathlib.Path(__file__).resolve().parents[1]


def test_el_porcentaje_se_redondea_hacia_arriba_en_medio_como_el_bot():
    assert categoria.porcentaje_entero(0.195) == 20
    assert categoria.porcentaje_entero(0.705) == 71
    assert categoria.porcentaje_entero(0.1949) == 19
    assert categoria.porcentaje_entero(0.0) == 0 and categoria.porcentaje_entero(1.0) == 100
    # el nodo Desenlace redondea igual: Math.round sube en ,5
    flujo = json.loads((REPO / "n8n" / "copiloto-profesional.json").read_text(encoding="utf-8"))
    desenlace = next(n for n in flujo["nodes"] if n["name"] == "Desenlace")
    assert "Math.round(v * 100)" in desenlace["parameters"]["jsCode"]


def test_las_bandas_tienen_los_bordes_20_y_70_dentro_de_intermedia():
    assert categoria.banda(19) == "baja"
    assert categoria.banda(20) == "intermedia"
    assert categoria.banda(70) == "intermedia"
    assert categoria.banda(71) == "alta"
    assert categoria.banda(0) == "baja" and categoria.banda(100) == "alta"


def test_el_punto_medio_es_en_log_odds():
    # logit 0,2 = −1,386; logit 0,8 = +1,386 → punto medio 0,5
    assert categoria.punto_medio_log_odds(0.2, 0.8) == pytest.approx(0.5)
    # y no es la media aritmética: (0,1 ; 0,9) también da 0,5, pero (0,1 ; 0,5) no da 0,3
    assert categoria.punto_medio_log_odds(0.1, 0.5) == pytest.approx(0.25, abs=0.01)


def _bloque(minima, maxima, independencia, dependencia, concordantes):
    return {"minima": minima, "maxima": maxima, "independencia": independencia,
            "dependencia": dependencia, "concordantes": concordantes}


def test_la_categoria_primaria_y_sus_variantes():
    # horquilla 0,65-0,95 (concordante, la imagen absorbe): punto medio en log-odds ≈ 0,87 → alta;
    # independencia 0,95 → alta; conservador 0,65 → intermedia; cruza el 70 % → intermedia
    c = categoria.categoria_del_sistema(_bloque(0.65, 0.95, [0.95], [0.65], True))
    assert c["primaria"] == "alta" and c["independencia"] == "alta"
    assert c["conservador"] == "intermedia" and c["cruza"] == "intermedia" and c["cruza_limite"]
    # discordante: un número, todas las variantes coinciden
    c = categoria.categoria_del_sistema(_bloque(0.12, 0.12, [0.12], None, False))
    assert {c["primaria"], c["independencia"], c["conservador"], c["cruza"]} == {"baja"}
    assert not c["cruza_limite"]
    # asma no_se: dos posteriores de independencia; el punto medio de las dos
    c = categoria.categoria_del_sistema(_bloque(0.30, 0.60, [0.30, 0.60], None, False))
    assert c["independencia"] == "intermedia" and c["primaria"] == "intermedia"


def _hallazgos():
    for t, fc, cr, mu, asma in itertools.product((37.8, 37.9), (100, 101), (False, True),
                                                 (False, True), ("si", "no", "no_se")):
        yield {"temperatura_c": t, "frecuencia_cardiaca": fc, "crepitantes": cr,
               "murmullo_disminuido": mu, "asma": asma}


def _los_cruces_dobles(prevalencia):
    """(hallazgos, bloque) de cada horquilla que cruza el 20 y el 70 % a la vez."""
    cruces = []
    for rv in np.geomspace(0.016, 77.3, 400):
        for h in _hallazgos():
            b = combinacion(prevalencia, h, float(rv))
            if (categoria.porcentaje_entero(b["minima"]) < 20
                    and categoria.porcentaje_entero(b["maxima"]) > 70):
                cruces.append((h, b))
    return cruces


def _cruces_dobles(prevalencia):
    return len(_los_cruces_dobles(prevalencia))


@pytest.mark.parametrize("prevalencia", [PREVALENCIA_COHORTE, 0.2215, 0.05, 0.034])
def test_ninguna_horquilla_cruza_los_dos_limites_con_las_tablas_actuales(prevalencia):
    """Spec §5.3 y §8: barrido de la RV de imagen desplegada (0,016-77,3) por las
    48 combinaciones de hallazgos. El umbral está en ≈ 3,3 % (Ruling 10): con
    0,034 ya no hay cruces dobles."""
    assert _cruces_dobles(prevalencia) == 0


@pytest.mark.parametrize("prevalencia", [0.02, 0.032])
def test_con_una_prevalencia_bajo_el_umbral_analitico_si_hay_cruces_dobles(prevalencia):
    """Con 0,032 cruza por la vía del asma `no_se` con puntuación [4, 5]."""
    assert _cruces_dobles(prevalencia) > 0


def test_con_0_032_todos_los_cruces_dobles_son_de_la_via_de_dos_puntuaciones():
    """Spec §5.3: entre ≈ 1,4 % y ≈ 3,3 % solo cruza el asma `no_se` con los
    otros cuatro hallazgos presentes, que da las dos puntuaciones [4, 5]."""
    cruces = _los_cruces_dobles(0.032)
    assert cruces
    for hallazgos, bloque in cruces:
        assert hallazgos["asma"] == "no_se"
        assert list(bloque["puntuacion"]) == [4, 5]
    # y por debajo del 1,4 % tambien cruza una sola puntuacion, la de 5 puntos
    una = [b for _, b in _los_cruces_dobles(0.012) if len(b["puntuacion"]) == 1]
    assert una and all(list(b["puntuacion"]) == [5] for b in una)
    assert not [b for _, b in _los_cruces_dobles(0.016) if len(b["puntuacion"]) == 1]
