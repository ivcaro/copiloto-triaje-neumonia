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


def test_un_numero_que_desborda_a_float_no_escapa_como_overflowerror():
    """`math.isfinite` explota con un entero de Python enorme (`OverflowError`
    al convertirlo a `float`); se convierte primero dentro de un `try` y el
    fallo sigue siendo `HallazgosInvalidos`, nombrando la clave."""
    with pytest.raises(HallazgosInvalidos) as exc:
        puntuar({**SIGNOS_3, "temperatura_c": 10**400}, "no")
    assert "temperatura_c" in str(exc.value)


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


def test_combinar_rechaza_nan_e_inf_en_cualquiera_de_las_dos_rv():
    """El guardia viejo (`rv <= 0`) deja pasar `nan` -la comparacion es
    siempre falsa- e `inf`, y la posterior sale `nan`. Ahora exige finita y
    positiva en las dos RV."""
    with pytest.raises(ValueError):
        combinar(0.1466, float("nan"), 1.0)
    with pytest.raises(ValueError):
        combinar(0.1466, 1.0, float("inf"))


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


from copiloto_triaje.servicio.heckerling import combinacion  # noqa: E402

PREV = 0.1466
RV_MUY_POSITIVA = 30.3       # la placa positiva clara del corpus de SP3
RV_BANDA = 0.87              # la banda contradictoria
CLAVES_DEL_BLOQUE = {"prevalencia", "puntuacion", "rv_clinica", "rv_imagen",
                     "concordantes", "absorbe", "independencia", "dependencia",
                     "minima", "maxima"}


def _hallazgos(asma, **cambios):
    return {**SIGNOS_3, "asma": asma, **cambios}


def test_el_bloque_lleva_exactamente_las_diez_claves_del_spec():
    c = combinacion(PREV, _hallazgos("si"), RV_MUY_POSITIVA)
    assert set(c) == CLAVES_DEL_BLOQUE
    assert c["prevalencia"] == PREV
    assert c["rv_imagen"] == RV_MUY_POSITIVA


def test_ejemplo_1_del_spec_puntuacion_3_e_imagen_30_3():
    """§8, caso normal: entre 84 % (dependencia total) y 90 % (independencia)."""
    c = combinacion(PREV, _hallazgos("si"), RV_MUY_POSITIVA)
    assert c["puntuacion"] == [3] and c["rv_clinica"] == [1.64]
    assert c["concordantes"] is True and c["absorbe"] == "imagen"
    assert c["independencia"] == [pytest.approx(0.8951, abs=5e-4)]
    assert c["dependencia"] == [pytest.approx(0.8388, abs=5e-4)]
    assert c["minima"] == c["dependencia"][0]
    assert c["maxima"] == c["independencia"][0]


def test_ejemplo_2_del_spec_discordantes_no_se_acota():
    """§8: puntuacion 0 (RV 0,12) contra imagen 30,3 -> un numero, 38 %."""
    ceros = {"temperatura_c": 37.0, "frecuencia_cardiaca": 80,
             "crepitantes": False, "murmullo_disminuido": False, "asma": "si"}
    c = combinacion(PREV, ceros, RV_MUY_POSITIVA)
    assert c["puntuacion"] == [0] and c["rv_clinica"] == [0.12]
    assert c["concordantes"] is False
    assert c["dependencia"] is None and c["absorbe"] is None
    assert c["minima"] == c["maxima"] == c["independencia"][0]
    assert c["minima"] == pytest.approx(0.3845, abs=5e-4)


def test_ejemplo_3_del_spec_asma_no_se_funde_todo_en_una_horquilla():
    """§8 tercer ejemplo: 4 o 5 con imagen 30,3 -> del 84 % al 99 %."""
    cuatro = _hallazgos("no_se", murmullo_disminuido=True)
    c = combinacion(PREV, cuatro, RV_MUY_POSITIVA)
    assert c["puntuacion"] == [4, 5] and c["rv_clinica"] == [7.18, 17.5]
    assert c["concordantes"] is True and c["absorbe"] == "imagen"
    assert c["independencia"] == [pytest.approx(0.9739, abs=5e-4),
                                  pytest.approx(0.9891, abs=5e-4)]
    assert c["dependencia"] == [pytest.approx(0.8388, abs=5e-4)] * 2
    assert c["minima"] == pytest.approx(0.8388, abs=5e-4)
    assert c["maxima"] == pytest.approx(0.9891, abs=5e-4)


def test_con_asma_no_se_y_las_dos_puntuaciones_a_lados_distintos_de_1_no_se_acota():
    """D6: 2 y 3 (0,70 y 1,64) contra la banda (0,87): 0,70 esta del lado de la
    imagen y 1,64 no. Sin concordancia, la horquilla es la de independencia."""
    dos_o_tres = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
                  "crepitantes": False, "murmullo_disminuido": False,
                  "asma": "no_se"}
    c = combinacion(PREV, dos_o_tres, RV_BANDA)
    assert c["puntuacion"] == [2, 3]
    assert c["concordantes"] is False and c["dependencia"] is None
    assert c["minima"] == pytest.approx(0.0947, abs=5e-4)
    assert c["maxima"] == pytest.approx(0.1969, abs=5e-4)


def test_absorbe_dice_quien_es_la_mas_informativa():
    ceros = {"temperatura_c": 37.0, "frecuencia_cardiaca": 80,
             "crepitantes": False, "murmullo_disminuido": False, "asma": "si"}
    # 0,12 contra la banda 0,87: manda la clinica.
    assert combinacion(PREV, ceros, RV_BANDA)["absorbe"] == "clinica"
    # 4 o 5 (7,18 y 17,5) contra una imagen de 10: |ln 10| = 2,30 esta entre
    # |ln 7,18| = 1,97 y |ln 17,5| = 2,86 -> cambia de una puntuacion a otra.
    cuatro = _hallazgos("no_se", murmullo_disminuido=True)
    assert combinacion(PREV, cuatro, 10.0)["absorbe"] == "mixta"


def test_los_dos_extremos_por_debajo_de_1_tambien_se_acotan():
    """Ambas RV en contra: la independencia da el extremo BAJO y la dependencia
    el ALTO. Los numeros del corpus: negativa del borde, RV 0,5888, puntuacion 0."""
    ceros = {"temperatura_c": 37.0, "frecuencia_cardiaca": 80,
             "crepitantes": False, "murmullo_disminuido": False, "asma": "si"}
    c = combinacion(PREV, ceros, 0.5888)
    assert c["concordantes"] is True and c["absorbe"] == "clinica"
    assert c["independencia"] == [pytest.approx(0.0120, abs=5e-4)]
    assert c["dependencia"] == [pytest.approx(0.0202, abs=5e-4)]
    assert c["minima"] < c["maxima"]


def test_las_posteriores_van_a_cuatro_decimales_y_la_rv_de_imagen_tal_cual():
    c = combinacion(PREV, _hallazgos("si"), 30.29389781009622)
    for x in c["independencia"] + c["dependencia"] + [c["minima"], c["maxima"]]:
        assert x == round(x, 4)
    assert c["rv_imagen"] == 30.29389781009622


def test_combinacion_rechaza_hallazgos_invalidos_y_rv_no_positiva():
    with pytest.raises(HallazgosInvalidos):
        combinacion(PREV, {**SIGNOS_3}, RV_MUY_POSITIVA)      # sin asma
    for rv in (0.0, -1.0, float("nan"), float("inf"), "30", True):
        with pytest.raises(ValueError):
            combinacion(PREV, _hallazgos("si"), rv)
