"""Pruebas de la regla de Heckerling y de la aritmetica de la combinacion.

La que sostiene todo lo demas es la reproduccion del articulo (spec §11.1):
con la prevalencia de la propia cohorte, la cadena tiene que dar la columna de
VPP publicada. Si alguien toca una RV o la aritmetica, deja de darla.
"""
import math

import pytest

from copiloto_triaje.servicio.heckerling import (
    ESTADOS_ASMA, PREVALENCIA_COHORTE, PULSO_CORTE_LPM, PUNTOS,
    RV_POR_PUNTUACION, TEMPERATURA_CORTE_C, HallazgosInvalidos, combinar,
    mas_informativa, puntuar, validar_hallazgos,
)

# La tabla 2 de PMC7422644 (conjunto de derivacion de Heckerling), COPIADA A
# MANO: testigo independiente del modulo. Por puntuacion: (con neumonia, sin
# neumonia, VPP publicado en %, decimales con los que se publica la RV).
ARTICULO = {
    0: (1, 48, 2.0, 2),
    1: (11, 316, 3.4, 2),
    2: (28, 232, 10.8, 2),
    3: (42, 149, 22.0, 2),
    4: (37, 30, 55.2, 2),
    5: (15, 5, 75.0, 1),
}
CON_NEUMONIA = 134
SIN_NEUMONIA = 780

# Tres de los cuatro puntos del profesional presentes; el asma decide el cuarto.
SIGNOS_3 = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
            "crepitantes": True, "murmullo_disminuido": False}


def test_las_celdas_del_articulo_suman_lo_que_el_articulo_dice():
    assert sum(c for c, _, _, _ in ARTICULO.values()) == CON_NEUMONIA
    assert sum(s for _, s, _, _ in ARTICULO.values()) == SIN_NEUMONIA
    assert PREVALENCIA_COHORTE == pytest.approx(CON_NEUMONIA / (CON_NEUMONIA + SIN_NEUMONIA))


@pytest.mark.parametrize("puntuacion", sorted(ARTICULO))
def test_cada_rv_sale_de_las_celdas_del_articulo(puntuacion):
    """RV = (con/134) / (sin/780), redondeada como la publica el articulo.
    Una RV tecleada mal -o «mejorada»- deja de coincidir."""
    con, sin, _, decimales = ARTICULO[puntuacion]
    calculada = (con / CON_NEUMONIA) / (sin / SIN_NEUMONIA)
    assert round(calculada, decimales) == RV_POR_PUNTUACION[puntuacion]


@pytest.mark.parametrize("puntuacion", sorted(ARTICULO))
def test_la_cadena_reproduce_la_columna_de_vpp_del_articulo(puntuacion):
    """Spec §11.1 y criterio 1: con la prevalencia de la cohorte y RV de imagen
    1 (sin imagen), la posterior es el VPP publicado salvo redondeo a una
    decima."""
    _, _, vpp, _ = ARTICULO[puntuacion]
    posterior = combinar(PREVALENCIA_COHORTE, RV_POR_PUNTUACION[puntuacion], 1.0)
    assert abs(posterior * 100 - vpp) <= 0.1, (posterior * 100, vpp)


def test_los_cinco_predictores_son_los_datos_que_los_bots_recogen():
    assert PUNTOS == ("temperatura_c", "frecuencia_cardiaca", "crepitantes",
                      "murmullo_disminuido", "asma")
    assert TEMPERATURA_CORTE_C == 37.8
    assert PULSO_CORTE_LPM == 100
    assert ESTADOS_ASMA == ("si", "no", "no_se")


def test_los_cortes_son_estrictos():
    """Spec §11.2: 37,8 exactos NO puntuan; 100 exactos NO puntuan."""
    justo = {"temperatura_c": 37.8, "frecuencia_cardiaca": 100,
             "crepitantes": False, "murmullo_disminuido": False}
    assert puntuar(justo, "si") == (0,)
    encima = {"temperatura_c": 37.9, "frecuencia_cardiaca": 101,
              "crepitantes": False, "murmullo_disminuido": False}
    assert puntuar(encima, "si") == (2,)


def test_el_asma_puntua_por_ausencia():
    assert puntuar(SIGNOS_3, "si") == (3,)
    assert puntuar(SIGNOS_3, "no") == (4,)


@pytest.mark.parametrize("crepitantes", [False, True])
@pytest.mark.parametrize("murmullo", [False, True])
def test_con_asma_no_se_salen_dos_puntuaciones_que_difieren_en_uno(crepitantes, murmullo):
    """Spec §6 y §11.2: no se elige por el clinico; se le dan las dos, y son
    (con asma, sin asma)."""
    signos = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
              "crepitantes": crepitantes, "murmullo_disminuido": murmullo}
    con, sin = puntuar(signos, "no_se")
    assert sin == con + 1
    assert (con,) == puntuar(signos, "si")
    assert (sin,) == puntuar(signos, "no")


def test_todo_presente_y_sin_asma_da_cinco():
    signos = {"temperatura_c": 39.0, "frecuencia_cardiaca": 120,
              "crepitantes": True, "murmullo_disminuido": True}
    assert puntuar(signos, "no") == (5,)


@pytest.mark.parametrize("asma", ["quizas", "", None, True, "SI"])
def test_un_asma_fuera_de_los_tres_estados_se_rechaza(asma):
    with pytest.raises(HallazgosInvalidos):
        puntuar(SIGNOS_3, asma)


@pytest.mark.parametrize("clave, valor", [
    ("crepitantes", "true"),        # la cadena "true" no es un booleano
    ("crepitantes", 1),             # ni un entero
    ("murmullo_disminuido", None),
    ("temperatura_c", "38,2"),      # un numero en texto no es un numero
    ("temperatura_c", float("nan")),
    ("frecuencia_cardiaca", True),  # bool es subclase de int: colaria como 1
])
def test_un_signo_con_el_tipo_equivocado_se_rechaza_y_dice_cual(clave, valor):
    with pytest.raises(HallazgosInvalidos) as exc:
        puntuar({**SIGNOS_3, clave: valor}, "no")
    assert clave in str(exc.value)


def test_validar_hallazgos_exige_exactamente_las_cinco_claves():
    completos = {**SIGNOS_3, "asma": "no_se"}
    assert validar_hallazgos(completos) == completos
    with pytest.raises(HallazgosInvalidos) as falta:
        validar_hallazgos({**SIGNOS_3})                       # sin asma
    assert "asma" in str(falta.value)
    with pytest.raises(HallazgosInvalidos) as sobra:
        validar_hallazgos({**completos, "tos": "seca"})       # una de mas
    assert "tos" in str(sobra.value)
    with pytest.raises(HallazgosInvalidos):
        validar_hallazgos("no es un objeto")


def test_combinar_es_la_aritmetica_de_odds():
    prev, rv_c, rv_i = 0.1466, 1.64, 30.3
    odds = prev / (1 - prev) * rv_c * rv_i
    assert combinar(prev, rv_c, rv_i) == pytest.approx(odds / (1 + odds))
    # Con las dos RV en 1, la posterior es la prevalencia: no hay evidencia.
    assert combinar(prev, 1.0, 1.0) == pytest.approx(prev)


def test_combinar_rechaza_una_prevalencia_que_no_es_una_probabilidad():
    for prev in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            combinar(prev, 1.0, 1.0)
    with pytest.raises(ValueError):
        combinar(0.1466, 0.0, 1.0)


def test_la_posterior_nunca_toca_0_ni_1_con_las_rv_acotadas():
    """Con la RV de imagen dentro de lo que el calibrador sostiene
    ([0,0163 ; 77,32], SP2) y las seis RV clinicas, la posterior queda
    estrictamente dentro de (0, 1) para la prevalencia de arranque."""
    for rv_c in RV_POR_PUNTUACION.values():
        for rv_i in (0.016271632806621517, 77.32279909706551):
            p = combinar(0.1466, rv_c, rv_i)
            assert 0.0 < p < 1.0


def test_mas_informativa_es_la_de_mayor_log_absoluto():
    assert mas_informativa(0.12, 0.87) == 0.12
    assert mas_informativa(30.3, 1.64) == 30.3
    assert mas_informativa(1.64, 30.3) == 30.3
    # A ojo se diria lo contrario: |ln 0,14| = 1,966 y |ln 7,18| = 1,971.
    # Es la clase de error que esta funcion existe para no cometer a ojo.
    assert mas_informativa(0.14, 7.18) == 7.18
    # En empate exacto manda la primera.
    assert mas_informativa(2.0, 0.5) == 2.0
    assert math.isclose(abs(math.log(2.0)), abs(math.log(0.5)))
