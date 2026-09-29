"""Kappas, intervalos, acuerdo continuo, tiempos y el análisis de la sesión
(spec de SP5 §5.4-§5.5, §8, §11.4; plan SP5-A D9).

Los kappas se comprueban contra un ejemplo calculado a mano de 8 casos:
  a = baja baja alta alta inter inter baja alta
  b = baja inter alta alta inter baja baja alta
  acuerdo bruto 6/8; marginales 3/2/3 en los dos; Cohen = 0,6190;
  ponderado lineal: (b,inter) e (inter,b) pesan 0,5 → po 0,875, pe 0,53125 → 0,7333.
"""
import csv
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys

import numpy as np
import pytest

from copiloto_triaje.validacion import concordancia as cc

A = ["baja", "baja", "alta", "alta", "intermedia", "intermedia", "baja", "alta"]
B = ["baja", "intermedia", "alta", "alta", "intermedia", "baja", "baja", "alta"]


def test_kappa_de_cohen_y_ponderado_lineal_del_ejemplo_a_mano():
    ia, ib = cc.indices(A), cc.indices(B)
    cohen = cc.kappa(ia, ib, 3, "ninguno")
    lineal = cc.kappa(ia, ib, 3, "lineal")
    assert cohen["kappa"] == pytest.approx(0.6190, abs=1e-4)
    assert cohen["po"] == pytest.approx(0.75) and cohen["pe"] == pytest.approx(0.34375)
    assert lineal["kappa"] == pytest.approx(0.7333, abs=1e-4)
    assert lineal["po"] == pytest.approx(0.875) and lineal["pe"] == pytest.approx(0.53125)
    assert cohen["ee"] > 0 and lineal["ee"] > 0
    assert cohen["ic95"][0] < cohen["kappa"] < cohen["ic95"][1]
    assert cc.kappa(ib, ia, 3, "lineal")["kappa"] == pytest.approx(lineal["kappa"])


def test_el_intervalo_analitico_se_acota_al_recorrido_del_kappa():
    # sin acotar, el ejemplo a mano da [0,175; 1,063] (Cohen) y [0,398; 1,069] (lineal)
    ia, ib = cc.indices(A), cc.indices(B)
    for tipo in ("ninguno", "lineal"):
        r = cc.kappa(ia, ib, 3, tipo)
        assert r["kappa"] + 1.96 * r["ee"] > 1.0
        assert r["ic95"][1] == 1.0
        assert r["ic95"][0] == pytest.approx(r["kappa"] - 1.96 * r["ee"])
    # por abajo: un desacuerdo sistemático da un kappa negativo, nunca menor que −1
    r = cc.kappa([0, 1, 0, 1], [1, 0, 1, 0], 2, "ninguno")
    assert r["ic95"][0] >= -1.0


def test_el_acuerdo_perfecto_da_kappa_1_con_error_tipico_0():
    ia = cc.indices(A)
    r = cc.kappa(ia, ia, 3, "lineal")
    assert r["kappa"] == pytest.approx(1.0) and r["ee"] == pytest.approx(0.0)


def test_kappa_binario_en_alta():
    r = cc.kappa_binario(A, B)
    assert r["kappa"] == pytest.approx(1.0)          # coinciden en todas las «alta»
    assert cc.kappa_binario(A, ["baja"] * 8)["kappa"] == pytest.approx(0.0)


def test_los_intervalos_bca_contienen_la_estimacion_y_son_reproducibles():
    r = cc.kappa_con_intervalos(A * 3, B * 3, "lineal")
    assert r["ic95_bca"][0] <= r["kappa"] <= r["ic95_bca"][1]
    assert r["ic95_bca"] == cc.kappa_con_intervalos(A * 3, B * 3, "lineal")["ic95_bca"]
    assert r["n"] == 24
    binario = cc.kappa_con_intervalos(A * 3, B * 3, "binario_alta")
    assert binario["kappa"] == pytest.approx(1.0)


def test_bca_sobre_una_media_conocida():
    datos = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    lo, hi = cc.bca(datos, lambda d: float(np.mean(d)), B=500, semilla=1)
    assert lo < 4.5 < hi and 2.0 < lo and hi < 7.0
    assert cc.bca(np.ones(10), lambda d: float(np.mean(d))) == [1.0, 1.0]


def test_acuerdo_continuo_acota_0_y_100_y_mide_spearman():
    pct = [0, 10, 40, 70, 100]
    p = [0.02, 0.15, 0.45, 0.7, 0.95]
    r = cc.acuerdo_continuo(pct, p, minima=[0.0, 0.1, 0.3, 0.6, 0.9], maxima=[0.05, 0.2, 0.5, 0.8, 1.0])
    assert r["spearman"] == pytest.approx(1.0)
    assert r["acotados_0_o_100"] == 2
    assert np.isfinite(r["diferencia_media_log_odds"]) and r["n"] == 5
    assert r["fraccion_dentro_de_la_horquilla"] == pytest.approx(1.0)
    assert r["dentro_de_la_horquilla"] == 5
    assert r["sistema_fuera_de_la_cota"] == 0


def test_donde_el_sistema_queda_fuera_de_la_cota_la_diferencia_no_puede_ser_cero():
    """Se acota al médico y no al sistema (spec §5.5): con el sistema por
    debajo del 0,5 %, contestar 0 % cuenta como contestar MÁS que él."""
    assert cc.COTA_DEL_MEDICO == (0.005, 0.995)
    r = cc.acuerdo_continuo([0, 0, 100, 50], [0.0034, 0.005, 0.9960, 0.5])
    assert r["sistema_fuera_de_la_cota"] == 2           # 0,005 justo no queda fuera
    assert r["acotados_0_o_100"] == 3
    solo = cc.acuerdo_continuo([0, 0], [0.0034, 0.0009])
    assert solo["sistema_fuera_de_la_cota"] == 2 and solo["diferencia_media_log_odds"] > 0.3
    arriba = cc.acuerdo_continuo([100, 100], [0.9960, 0.9991])
    assert arriba["diferencia_media_log_odds"] < -0.2
    # acotar sigue dando lo de siempre: un 0 % es un 0,5 %
    igual = cc.acuerdo_continuo([0, 100], [0.005, 0.995])
    assert igual["diferencia_media_log_odds"] == pytest.approx(0.0, abs=1e-12)
    assert igual["de"] == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("minima, maxima, pct, dentro", [
    (0.4406, 0.4406, 44, True),     # horquilla de un solo valor: el bot imprime «44 %»
    (0.4406, 0.4406, 45, False),
    (0.0003, 0.0028, 0, True),      # el bot imprime «< 1 %»; el 0 no se acota a 0,5 aquí
    (0.0003, 0.0028, 1, False),
    (0.8000, 0.9940, 99, True),
    (0.8000, 0.9940, 100, True),    # 0,9940 se imprime «> 99 %»: el límite superior es 100
    (0.8000, 0.9900, 100, False),   # 0,99 exacto se imprime «99 %»
    (0.0060, 0.3000, 0, True),      # 0,0060 se imprime «< 1 %»: el límite inferior es 0
    (0.0100, 0.3000, 0, False),     # 0,01 exacto se imprime «1 %»
    # los DOS extremos bajo 0,01: el bot imprime un solo «< 1 %», que no admite el 1
    (0.0030, 0.0080, 0, True),
    (0.0030, 0.0080, 1, False),
    (0.0070, 0.0070, 0, True),      # un discordante: «< 1 %», y es de un solo valor
    (0.0070, 0.0070, 1, False),
    # y los dos sobre 0,99: un solo «> 99 %», que no admite el 99
    (0.9920, 0.9980, 100, True),
    (0.9920, 0.9980, 99, False),
])
def test_dentro_de_la_horquilla_compara_enteros_como_los_imprime_el_bot(minima, maxima, pct, dentro):
    r = cc.acuerdo_continuo([pct, 50], [0.5, 0.5], minima=[minima, 0.4], maxima=[maxima, 0.6])
    assert r["fraccion_dentro_de_la_horquilla"] == pytest.approx(0.5 + 0.5 * dentro)
    # «de un solo valor» es lo que el bot imprime como un solo valor
    un_solo_valor = cc._pct_como_el_bot(minima) == cc._pct_como_el_bot(maxima)
    assert r["horquillas_de_anchura_cero"] == int(un_solo_valor)
    # y de esas, las que el bot imprime como una cota
    assert r["horquillas_que_son_una_cota"] == int(
        un_solo_valor and cc._pct_como_el_bot(minima) in ("< 1 %", "> 99 %"))
    assert r["dentro_de_la_horquilla"] == 1 + int(dentro)
    assert cc._horquilla_como_el_bot(minima, maxima).count("%") == (1 if un_solo_valor else 2)


def test_un_extremo_de_la_horquilla_es_un_entero_con_la_regla_del_bot():
    casos = [(0.0, 0, "< 1 %"), (0.0099, 0, "< 1 %"), (0.01, 1, "1 %"), (0.0149, 1, "1 %"),
             (0.4406, 44, "44 %"), (0.984, 98, "98 %"), (0.985, 99, "99 %"), (0.99, 99, "99 %"),
             (0.9901, 100, "> 99 %"), (0.995, 100, "> 99 %"), (1.0, 100, "> 99 %")]
    for x, entero, impreso in casos:
        assert cc._entero_como_el_bot(x) == entero, x
        assert cc._pct_como_el_bot(x) == impreso, x
    # de 0,01 a 0,99 el entero nunca es 0 ni 100: las cotas no se confunden
    for x in np.linspace(0.01, 0.99, 981):
        assert 1 <= cc._entero_como_el_bot(float(x)) <= 99


def test_un_kappa_que_es_exactamente_un_umbral_lo_alcanza(tmp_path):
    """Con 24 casos el kappa es un racional. Esta tabla da 0,4 exacto
    (1 − 24·7/280), y la coma flotante lo deja un ulp por debajo."""
    tabla = {("baja", "baja"): 13, ("baja", "intermedia"): 3, ("intermedia", "baja"): 2,
             ("intermedia", "intermedia"): 5, ("alta", "baja"): 1}
    a = [fila for (fila, _), n in tabla.items() for _ in range(n)]
    b = [columna for (_, columna), n in tabla.items() for _ in range(n)]
    assert len(a) == 24
    k = cc.kappa_con_intervalos(a, b, tipo="lineal")
    assert k["kappa"] == pytest.approx(0.4, abs=1e-12)
    assert k["kappa"] != 0.4, "si algun dia sale 0,4 exacto, esta prueba no prueba nada"
    k["frente_a_umbrales"] = cc.frente_a_umbrales(k)
    assert k["frente_a_umbrales"]["puntual_ge_0_4"] is True
    assert k["frente_a_umbrales"]["puntual_ge_0_6"] is False
    frase = cc._criterio("El kappa ponderado", k)
    assert frase.startswith("El kappa ponderado (0,40) alcanza el mínimo de 0,4 de la Semana 1 "
                            "y no el objetivo de 0,6;")
    assert "0,400000" not in frase and "0,399" not in frase

    def con(kappa, li_a=0.1, li_b=0.1):
        r = {"kappa": kappa, "ic95": [li_a, 1.0], "ic95_bca": [li_b, 1.0]}
        r["frente_a_umbrales"] = cc.frente_a_umbrales(r)
        return r
    un_ulp = 0.3999999999999999
    assert con(un_ulp)["frente_a_umbrales"]["puntual_ge_0_4"] is True
    assert con(0.5999999999999999)["frente_a_umbrales"]["puntual_ge_0_6"] is True
    assert cc._criterio("K", con(0.5999999999999999)).startswith(
        "K (0,60) alcanza el mínimo de 0,4 de la Semana 1 y el objetivo de 0,6;")
    # lo mismo en los limites inferiores: un limite que es el umbral no queda por debajo
    u = con(0.7, li_a=un_ulp, li_b=0.39)["frente_a_umbrales"]
    assert (u["li_analitico_lt_0_4"], u["li_bca_lt_0_4"]) == (False, True)
    assert "con el BCa (0,39) y no con el método analítico (0,40)" in cc._criterio(
        "K", con(0.7, li_a=un_ulp, li_b=0.39))
    # tambien con el ulp en el limite del BCa
    u = con(0.7, li_a=0.39, li_b=un_ulp)["frente_a_umbrales"]
    assert (u["li_analitico_lt_0_4"], u["li_bca_lt_0_4"]) == (True, False)
    assert "con el método analítico (0,39) y no con el BCa (0,40)" in cc._criterio(
        "K", con(0.7, li_a=0.39, li_b=un_ulp))
    # un limite que ES el umbral no queda por debajo; tampoco «por encima»
    en_el_umbral = cc._criterio("K", con(0.7, li_a=un_ulp, li_b=0.4))
    assert ("el límite inferior del intervalo no queda por debajo de 0,4 con ninguno de los "
            "dos métodos (analítico 0,40; BCa 0,40).") in en_el_umbral
    assert "por encima" not in en_el_umbral
    # y lo que a seis decimales NO es el umbral sigue sin alcanzarlo, y se ve
    assert con(0.399999)["frente_a_umbrales"]["puntual_ge_0_4"] is False
    assert cc._criterio("K", con(0.399999)).startswith("K (0,399999) no alcanza el mínimo")
    # la tolerancia son SEIS decimales, ni siete ni 1e-9: lo que a seis es el
    # umbral lo alcanza, y no puede salir «K (0,400000) no alcanza»
    assert con(0.3999996)["frente_a_umbrales"]["puntual_ge_0_4"] is True
    assert cc._criterio("K", con(0.3999996)).startswith("K (0,40) alcanza el mínimo de 0,4")
    assert con(0.3999994)["frente_a_umbrales"]["puntual_ge_0_4"] is False
    assert cc._criterio("K", con(0.3999994)).startswith("K (0,399999) no alcanza el mínimo")
    assert con(0.5999996)["frente_a_umbrales"]["puntual_ge_0_6"] is True


@pytest.mark.filterwarnings("error::RuntimeWarning")
def test_acuerdo_continuo_con_porcentaje_constante_da_spearman_nan_sin_avisos():
    # Ruling 5: un vector de rangos constante (porcentaje del médico fijo)
    # no debe llamar a np.corrcoef; el resultado es NaN, no un aviso.
    r = cc.acuerdo_continuo([50, 50, 50, 50], [0.08, 0.45, 0.9, 0.45])
    assert math.isnan(r["spearman"])
    # el sistema constante también degenera, en el otro eje
    r2 = cc.acuerdo_continuo([10, 40, 70, 90], [0.5, 0.5, 0.5, 0.5])
    assert math.isnan(r2["spearman"])


def test_razon_de_tiempos_pareada():
    r = cc.razon_de_tiempos([60, 80, 100, 120], [30, 40, 50, 60])
    assert r["razon_medias_geometricas"] == pytest.approx(0.5)
    assert r["reduccion_pct"] == pytest.approx(50.0)
    assert r["n"] == 4 and r["ic95_bca"][0] <= 0.5 <= r["ic95_bca"][1]
    with pytest.raises(ValueError):
        cc.razon_de_tiempos([1, 2], [1])


def test_razon_corregida_colapsa_cuando_todas_las_razones_son_iguales():
    # Ruling 6: con/sin exactamente 0,5 y controles exactamente 1,0 (como en
    # la sesión fabricada) el intervalo percentil colapsa sobre el punto.
    ln_con = np.log([0.5] * 20)
    ln_ctl = np.log([1.0] * 4)
    r = cc.razon_corregida(ln_con, ln_ctl)
    assert r["punto"] == pytest.approx(0.5)
    assert r["ic95"] == pytest.approx([0.5, 0.5])


def test_razon_corregida_con_tiempos_variables_da_un_intervalo_que_contiene_el_punto():
    ln_con = np.log([0.35, 0.42, 0.58, 0.5, 0.47, 0.61, 0.39, 0.55])
    ln_ctl = np.log([0.85, 1.05, 1.2, 0.95])
    r = cc.razon_corregida(ln_con, ln_ctl)
    assert r["ic95"][0] <= r["punto"] <= r["ic95"][1]
    assert r["ic95"][0] < r["ic95"][1]
    # reproducible: misma semilla, mismo intervalo
    assert cc.razon_corregida(ln_con, ln_ctl)["ic95"] == r["ic95"]
    with pytest.raises(ValueError):
        cc.razon_corregida([], [1.0])


# --------------------------------------------------------------------------
# El análisis entero sobre una sesión fabricada con valores conocidos.
# --------------------------------------------------------------------------
BANDAS_SISTEMA = (["baja"] * 8 + ["alta"] * 8 + ["intermedia"] * 4 + ["intermedia"] * 4)
ESTRATOS = (["positiva_clara"] * 8 + ["negativa_clara"] * 8
            + ["banda_contradictoria"] * 4 + ["asma_no_se"] * 4)
PUNTO_MEDIO = {"baja": 0.08, "intermedia": 0.45, "alta": 0.9}


def _clave(controles=("c-00", "c-01", "c-08", "c-09")):
    """Una clave DEFINITIVA (la de `--fase mensajes`): cada caso con su bloque
    y su categoría del mensaje, y la clave con el origen de los mensajes."""
    casos = []
    for i in range(24):
        banda = BANDAS_SISTEMA[i]
        pm = PUNTO_MEDIO[banda]
        casos.append({"patientId": f"c-{i:02d}", "estrato": ESTRATOS[i], "concordante": i % 2 == 0,
                      "bloque": {"minima": pm - 0.05, "maxima": pm + 0.05},
                      "categoria": {"primaria": banda, "punto_medio": pm, "independencia": banda,
                                    "conservador": banda, "cruza": banda, "cruza_limite": False}})
    # un caso cuya horquilla cruza el 20 %: la variante «cruza» lo pone en intermedia
    casos[0]["bloque"] = {"minima": 0.12, "maxima": 0.22}
    casos[0]["categoria"].update({"cruza": "intermedia", "cruza_limite": True})
    for c in casos:
        c["bloque_previsto"] = dict(c["bloque"])
        c["categoria_prevista"] = dict(c["categoria"])
    return {"rotulo": "simulación semisintética — sesión H7", "casos": casos, "fase": "mensajes",
            "prevalencia_sesion": 0.1466,
            "origen_mensajes": {"con_bots": True, "imagen_tag": None, "imagen_digest": None},
            "ordenes": {"lectura1": [c["patientId"] for c in casos],
                        "lectura2": [c["patientId"] for c in casos][::-1],
                        "controles": list(controles)}}


def _csv(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cc.COLUMNAS_CSV)
        w.writeheader()
        w.writerows(filas)


INICIO = 1760000000000                 # la lectura 1, en ms
SIETE_DIAS = 7 * 24 * 3600 * 1000      # la lectura 2, una semana después


def _fila(lectura, orden, caso, banda, pct, segundos, control=False, notas=None, banda_con="", pct_con="",
          seg_con="", comentario=None):
    n = notas or {}
    inicio = INICIO + (SIETE_DIAS if lectura == 2 else 0)
    return {"lectura": lectura, "orden": orden, "id": caso["patientId"], "practica": "false",
            "control": "true" if control else "false", "banda": banda, "porcentaje": pct,
            "abierto_en": inicio + orden * 100000, "enviado_en": inicio + orden * 100000 + int(segundos * 1000),
            "segundos": segundos, "banda_con": banda_con, "porcentaje_con": pct_con, "segundos_con": seg_con,
            "correccion": n.get("correccion", ""), "utilidad": n.get("utilidad", ""), "lenguaje": n.get("lenguaje", ""),
            "comentario": (comentario if comentario is not None
                           else "dudoso" if banda != caso["categoria"]["primaria"] else "")}


def _lecturas(clave, discrepa=None, segundos_con=30.0, segundos_control=60.0):
    """La lectura 1 (24 filas, el médico coincide salvo en `discrepa`) y la
    lectura 2 (con mensaje en los casos que no son controles), ya leídas."""
    casos = {c["patientId"]: c for c in clave["casos"]}
    discrepa = discrepa or {}
    controles = set(clave["ordenes"]["controles"])
    l1 = [_fila(1, i + 1, casos[pid], discrepa.get(pid, casos[pid]["categoria"]["primaria"]),
                int(casos[pid]["categoria"]["punto_medio"] * 100), 60.0)
          for i, pid in enumerate(clave["ordenes"]["lectura1"])]
    l2 = [_fila(2, i + 1, casos[pid], casos[pid]["categoria"]["primaria"], 50,
                segundos_control if pid in controles else segundos_con, control=pid in controles,
                notas=None if pid in controles else {"correccion": 5, "utilidad": 4, "lenguaje": 3})
          for i, pid in enumerate(clave["ordenes"]["lectura2"])]
    return l1, l2


def _leidas(tmp_path, nombre, filas):
    _csv(tmp_path / nombre, filas)
    return cc.leer_csv(tmp_path / nombre)


def test_analizar_una_sesion_fabricada(tmp_path):
    clave = _clave()
    casos = {c["patientId"]: c for c in clave["casos"]}
    # Lectura 1: el médico coincide en 20 y discrepa en 4 (dos de ellas a la banda vecina).
    discrepa = {"c-02": "intermedia", "c-10": "intermedia", "c-17": "baja", "c-21": "alta"}
    l1 = [_fila(1, i + 1, casos[pid], discrepa.get(pid, casos[pid]["categoria"]["primaria"]),
                int(casos[pid]["categoria"]["punto_medio"] * 100), 60.0)
          for i, pid in enumerate(clave["ordenes"]["lectura1"])]
    # Lectura 2: con mensaje en 20 (mitad de tiempo, notas 5/4/3) y 4 controles (mismo tiempo).
    controles = set(clave["ordenes"]["controles"])
    l2 = []
    for i, pid in enumerate(clave["ordenes"]["lectura2"]):
        c = casos[pid]
        if pid in controles:
            l2.append(_fila(2, i + 1, c, c["categoria"]["primaria"], 50, 60.0, control=True))
        else:
            l2.append(_fila(2, i + 1, c, c["categoria"]["primaria"], 50, 30.0,
                            notas={"correccion": 5, "utilidad": 4, "lenguaje": 3}))
    _csv(tmp_path / "lectura1.csv", l1)
    _csv(tmp_path / "lectura2.csv", l2)
    huellas = {"mensajes_json": "a" * 64, "clave_json": "b" * 64}
    s = cc.analizar(clave, cc.leer_csv(tmp_path / "lectura1.csv"), cc.leer_csv(tmp_path / "lectura2.csv"),
                    huellas=huellas)

    assert s["n"] == 24 and "categoria_de" not in s          # Ruling 11: siempre la del mensaje
    assert s["origen_mensajes"] == clave["origen_mensajes"]
    assert s["prevalencia_sesion"] == clave["prevalencia_sesion"]
    assert s["huellas"] == huellas
    assert s["fechas"] == {"lectura1": cc._fecha(INICIO + 100000),
                           "lectura2": cc._fecha(INICIO + SIETE_DIAS + 100000)}
    assert s["fechas"]["lectura1"] != s["fechas"]["lectura2"]
    assert json.loads(json.dumps(s)) == s                    # sesion.json es JSON puro
    assert s["kappa"]["ponderado_lineal"]["n"] == 24
    assert 0.6 < s["kappa"]["ponderado_lineal"]["kappa"] < 1.0
    assert s["kappa"]["cohen"]["kappa"] < s["kappa"]["ponderado_lineal"]["kappa"]
    for nombre in ("ponderado_lineal", "cohen", "binario_alta"):
        k = s["kappa"][nombre]
        assert k["ic95"][0] <= k["kappa"] <= k["ic95"][1]
        assert k["ic95_bca"][0] <= k["kappa"] <= k["ic95_bca"][1]
    assert set(s["sensibilidad_categoria"]) == {"independencia", "conservador", "cruza"}
    assert s["n_cruzan_un_limite"] == 1
    assert s["sensibilidad_categoria"]["cruza"] < s["kappa"]["ponderado_lineal"]["kappa"]
    for nombre in ("ponderado_lineal", "cohen", "binario_alta"):
        u = s["kappa"][nombre]["frente_a_umbrales"]
        assert set(u) == {"puntual_ge_0_4", "puntual_ge_0_6", "li_analitico_lt_0_4", "li_bca_lt_0_4"}
    assert s["lectura2"]["kappa_con_mensaje"]["frente_a_umbrales"]["puntual_ge_0_6"] is True
    assert s["acuerdo_continuo"]["horquillas_de_anchura_cero"] == 0
    assert len(s["desacuerdos"]) == 4
    assert {d["id"] for d in s["desacuerdos"]} == set(discrepa)
    assert all(d["comentario"] == "dudoso" for d in s["desacuerdos"])
    assert s["acuerdo_continuo"]["n"] == 24 and s["acuerdo_continuo"]["spearman"] > 0.9
    l2s = s["lectura2"]
    assert l2s["n_con_mensaje"] == 20 and l2s["n_controles"] == 4
    assert l2s["kappa_con_mensaje"]["kappa"] == pytest.approx(1.0)
    assert l2s["cambios_de_banda"] == 4          # los 4 discrepantes de la lectura 1 vuelven a la del sistema
    assert l2s["utilidad"]["correccion"]["media"] == pytest.approx(5.0)
    assert l2s["utilidad"]["lenguaje"]["media"] == pytest.approx(3.0)
    assert l2s["tiempo"]["medido"] is True
    assert l2s["tiempo"]["razon_medias_geometricas"] == pytest.approx(0.5)
    assert l2s["tiempo"]["controles"]["media_geometrica"] == pytest.approx(1.0)
    assert l2s["tiempo"]["razon_corregida_por_releer"] == pytest.approx(0.5)
    assert l2s["tiempo"]["ic95_razon_corregida"] == pytest.approx([0.5, 0.5])
    assert s["plan_b"] is None
    assert s["texto_fijado"] == cc.TEXTO_FIJADO


def test_analizar_el_plan_b(tmp_path):
    clave = _clave()
    casos = {c["patientId"]: c for c in clave["casos"]}
    filas = [_fila(1, i + 1, casos[pid], casos[pid]["categoria"]["primaria"],
                   int(casos[pid]["categoria"]["punto_medio"] * 100), 40.0,
                   notas={"correccion": 4, "utilidad": 4, "lenguaje": 4},
                   banda_con="alta" if i < 3 else casos[pid]["categoria"]["primaria"], pct_con=80, seg_con=20.0)
             for i, pid in enumerate(clave["ordenes"]["lectura1"])]
    _csv(tmp_path / "planb.csv", filas)
    s = cc.analizar(clave, cc.leer_csv(tmp_path / "planb.csv"), planb=cc.leer_csv(tmp_path / "planb.csv"))
    assert s["kappa"]["ponderado_lineal"]["kappa"] == pytest.approx(1.0)
    assert s["fechas"] == {"sesion_unica": cc._fecha(INICIO + 100000)}
    assert s["huellas"] is None
    assert s["lectura2"] is None
    pb = s["plan_b"]
    assert pb["tiempo_medido"] is False
    assert pb["segundos_adicionales_leer_mensaje"]["mediana"] == pytest.approx(20.0)
    assert pb["cambios_de_banda"] == 3          # las tres primeras filas llevan «alta» y su sistema es «baja»
    assert pb["kappa_con_mensaje"]["n"] == 24


def test_leer_csv_convierte_los_tipos_del_formulario(tmp_path):
    clave = _clave()
    _csv(tmp_path / "l.csv", [_fila(1, 1, clave["casos"][0], "baja", 7, 12.5, notas={"correccion": 5, "utilidad": 4, "lenguaje": 3})])
    fila = cc.leer_csv(tmp_path / "l.csv")[0]
    assert fila["practica"] is False and fila["control"] is False
    assert fila["porcentaje"] == 7 and fila["segundos"] == 12.5 and fila["orden"] == 1
    assert fila["correccion"] == 5 and fila["porcentaje_con"] is None and fila["segundos_con"] is None


def test_el_acta_se_rellena_desde_sesion_json_y_no_deja_huecos(tmp_path):
    clave = _clave()
    casos = {c["patientId"]: c for c in clave["casos"]}
    l1 = [_fila(1, i + 1, casos[pid], casos[pid]["categoria"]["primaria"], 50, 60.0)
          for i, pid in enumerate(clave["ordenes"]["lectura1"])]
    _csv(tmp_path / "l1.csv", l1)
    s = cc.analizar(clave, cc.leer_csv(tmp_path / "l1.csv"))
    plantilla = (pathlib.Path(__file__).resolve().parents[1] / "docs" / "validacion-semisintetica"
                 / "acta-h7-plantilla.md").read_text(encoding="utf-8")
    acta = cc.rellenar_acta(plantilla, cc.valores_para_acta(s, clave))
    assert "{{" not in acta
    assert "simulación semisintética" in acta
    assert cc.TEXTO_FIJADO in acta
    assert "| c-00 | positiva clara | concordante |" in acta and "positiva_clara" not in acta
    assert "no medido" in acta       # sin lectura 2 ni plan B, el tiempo no se midió
    plano = _plano(acta)
    assert f"**Fechas:** lectura el {cc._fecha(INICIO + 100000)}." in plano
    assert "no hay controles (solo la lectura sin copiloto)" in plano
    assert "**Congelado verificable:** sin huellas (el análisis no recibió los ficheros de la sesión)." in plano
    assert "casos cuya horquilla cruza un límite: 1 de 24" in plano
    assert ("el porcentaje del médico cae dentro de la horquilla en 8 de 24 casos (33 %) "
            "(0 de 24 horquillas son un solo valor impreso, y 0 de ellas una cota, «< 1 %» "
            "o «> 99 %»: en ellas solo cuenta ese entero, y una «< 1 %» solo la cumple un "
            "0 y una «> 99 %», un 100; en un rango, «menos de 1 %» admite desde el 0 y "
            "«más de 99 %», hasta el 100); porcentajes de 0 o 100 acotados: 0; puntos "
            "medios del sistema por debajo de 0,5 % o por encima de 99,5 %: 0 (en ellos la "
            "diferencia no puede ser cero: lo que conteste el médico se acota a 0,5 % y "
            "99,5 %, y el sistema no).") in plano
    # acuerdo perfecto: los tres kappas valen 1 y su límite inferior no queda por debajo de 0,4
    assert ("El kappa ponderado (1,00) alcanza el mínimo de 0,4 de la Semana 1 y el objetivo de 0,6; "
            "el límite inferior del intervalo no queda por debajo de 0,4 con ninguno de los dos "
            "métodos") in plano
    # el texto fijado se cita como lo declarado, y detrás va lo observado
    assert ("**Declarado antes de la sesión** (spec de SP5 §5.5): «" + cc.TEXTO_FIJADO
            + "» **Observado en esta sesión:** el intervalo del 95 % del kappa ponderado "
            "va de 1,00 a 1,00 con el método analítico (anchura 0,00) y de 1,00 a 1,00 con "
            "el BCa (anchura 0,00); el 0,4 y el 0,6 quedan fuera con los dos métodos."
            ) in plano
    assert "El kappa de Cohen (1,00)" in plano and "El kappa binario en «alta» (1,00)" in plano
    assert plano.index("Kappa binario en «alta»") < plano.index("El kappa ponderado (1,00)") < plano.index(cc.TEXTO_FIJADO)
    with pytest.raises(KeyError):
        cc.rellenar_acta("{{no_existe}}", {})


# Ocho discrepancias en 24, dos de ellas de dos bandas: kappa ponderado 0,55
# con los límites inferiores de los dos intervalos por debajo de 0,4.
OCHO = {"c-02": "alta", "c-04": "intermedia", "c-10": "baja", "c-12": "intermedia",
        "c-17": "baja", "c-19": "alta", "c-21": "alta", "c-23": "baja"}


def test_el_acta_compara_cada_kappa_con_0_4_y_0_6(tmp_path):
    clave = _clave()
    casos = {c["patientId"]: c for c in clave["casos"]}
    l1 = [_fila(1, i + 1, casos[pid], OCHO.get(pid, casos[pid]["categoria"]["primaria"]), 50, 60.0)
          for i, pid in enumerate(clave["ordenes"]["lectura1"])]
    _csv(tmp_path / "l1.csv", l1)
    s = cc.analizar(clave, cc.leer_csv(tmp_path / "l1.csv"))
    k = s["kappa"]["ponderado_lineal"]
    assert 0.4 <= k["kappa"] < 0.6
    assert k["frente_a_umbrales"] == {"puntual_ge_0_4": True, "puntual_ge_0_6": False,
                                      "li_analitico_lt_0_4": True, "li_bca_lt_0_4": True}
    acta = cc.rellenar_acta(_plantilla(), cc.valores_para_acta(s, clave))
    assert (f"El kappa ponderado ({cc._f(k['kappa'])}) alcanza el mínimo de 0,4 de la Semana 1 y no "
            f"el objetivo de 0,6; el límite inferior del intervalo queda por debajo de 0,4 con los dos "
            f"métodos (analítico {cc._f(k['ic95'][0])}; BCa {cc._f(k['ic95_bca'][0])}).") in _plano(acta)


def test_la_frase_del_criterio_cubre_cada_combinacion():
    def k(kappa, li_a, li_b):
        r = {"kappa": kappa, "ic95": [li_a, 1.0], "ic95_bca": [li_b, 1.0]}
        r["frente_a_umbrales"] = cc.frente_a_umbrales(r)
        return r
    assert "no alcanza el mínimo de 0,4" in cc._criterio("El kappa de Cohen", k(0.3, 0.1, 0.05))
    assert "con el método analítico (0,38) y no con el BCa (0,41)" in cc._criterio("K", k(0.7, 0.38, 0.41))
    assert "con el BCa (0,35) y no con el método analítico (0,42)" in cc._criterio("K", k(0.7, 0.42, 0.35))
    # pegado a un umbral, los dos decimales contradirían la frase: se imprimen los que hagan falta
    frase = cc._criterio("K", k(0.3996, 0.397, 0.4))
    assert frase.startswith("K (0,3996) no alcanza el mínimo de 0,4 de la Semana 1;")
    assert "con el método analítico (0,397) y no con el BCa (0,40)" in frase
    assert cc._criterio("K", k(0.5996, 0.1, 0.1)).startswith("K (0,5996) alcanza el mínimo de 0,4 de la Semana 1 y no el objetivo")
    assert cc._criterio("K", k(0.6, 0.4049, 0.1)).startswith("K (0,60) alcanza el mínimo de 0,4 de la Semana 1 y el objetivo")
    assert "con el BCa (0,10) y no con el método analítico (0,405)" in cc._criterio("K", k(0.6, 0.4049, 0.1))
    nan = float("nan")
    assert cc.frente_a_umbrales({"kappa": nan, "ic95": [nan, nan], "ic95_bca": [nan, nan]}) is None
    assert cc._criterio("El kappa binario en «alta»", {"kappa": nan, "frente_a_umbrales": None}) == \
        "El kappa binario en «alta» no es calculable con estas lecturas."


def test_un_cero_con_residuo_de_coma_flotante_no_se_imprime_negativo():
    """El limite inferior del BCa de una tabla puede ser −5e-16: es un 0."""
    assert cc._f(-5.3e-16) == "0,00" and cc._f(-0.0) == "0,00" and cc._f(0.0) == "0,00"
    assert cc._f(-0.004) == "0,00" and cc._f(-0.0004, 3) == "0,000"
    assert cc._f(-0.005001) == "-0,01" and cc._f(-0.12) == "-0,12"
    assert cc._f_frente_a_umbral(-5.3e-16) == "0,00"
    k = {"kappa": 0.5, "ic95": [-5.3e-16, 0.75], "ic95_bca": [-1e-17, 0.75], "n": 24}
    assert cc._kappa_texto(k) == ("0,50 (IC 95 % analítico 0,00 a 0,75; BCa 0,00 a 0,75; "
                                  "n = 24)")


def test_lo_observado_va_al_lado_de_lo_declarado_y_no_lo_contradice():
    """El texto fijado dice «una anchura de 0,5 a 0,6»: con un kappa alto el
    intervalo es mucho más estrecho, y el acta tiene que decir el suyo."""
    def k(kappa, analitico, bca):
        r = {"kappa": kappa, "ic95": list(analitico), "ic95_bca": list(bca), "n": 24}
        r["frente_a_umbrales"] = cc.frente_a_umbrales(r)
        return r
    assert cc._anchura_observada(k(0.893, (0.7512, 1.0), (0.6488, 1.0))) == (
        "el intervalo del 95 % del kappa ponderado va de 0,75 a 1,00 con el método "
        "analítico (anchura 0,25) y de 0,65 a 1,00 con el BCa (anchura 0,35); el 0,4 y el "
        "0,6 quedan fuera con los dos métodos.")
    assert cc._anchura_observada(k(0.55, (0.28, 0.82), (0.25, 0.79))) == (
        "el intervalo del 95 % del kappa ponderado va de 0,28 a 0,82 con el método "
        "analítico (anchura 0,54) y de 0,25 a 0,79 con el BCa (anchura 0,54); el 0,4 y el "
        "0,6 quedan dentro con los dos métodos.")
    # pegado a un umbral, el límite se imprime con los decimales que lo
    # distinguen, como en la frase del criterio, y con esos se decide
    assert cc._anchura_observada(k(0.7, (0.3996, 0.95), (0.41, 0.95))) == (
        "el intervalo del 95 % del kappa ponderado va de 0,3996 a 0,95 con el método "
        "analítico (anchura 0,55) y de 0,41 a 0,95 con el BCa (anchura 0,54); el 0,4 queda "
        "dentro con el método analítico y fuera con el BCa y el 0,6 queda dentro con los "
        "dos métodos.")
    # el caso que se contradecía: a dos decimales 0,4027 es «0,40» y contendría
    # el 0,4, mientras el criterio dice que el límite (0,403) no queda por debajo
    sesion = k(0.674, (0.4027, 0.9457), (0.36, 0.93))
    observado = cc._anchura_observada(sesion)
    assert observado == (
        "el intervalo del 95 % del kappa ponderado va de 0,403 a 0,95 con el método "
        "analítico (anchura 0,55) y de 0,36 a 0,93 con el BCa (anchura 0,57); el 0,4 queda "
        "dentro con el BCa y fuera con el método analítico y el 0,6 queda dentro con los "
        "dos métodos.")
    criterio = cc._criterio("El kappa ponderado", sesion)
    assert "con el BCa (0,36) y no con el método analítico (0,403)" in criterio
    # lo que a seis decimales ES el umbral queda dentro, y se imprime como el umbral
    assert "va de 0,40 a 0,95 con el método analítico" in cc._anchura_observada(
        k(0.7, (0.3999999999999999, 0.95), (0.4000004, 0.95)))
    assert "el 0,4 y el 0,6 quedan dentro con los dos métodos" in cc._anchura_observada(
        k(0.7, (0.3999999999999999, 0.95), (0.4000004, 0.95)))
    assert "de 0,00 a 0,00 con el método analítico (anchura 0,00)" in cc._anchura_observada(
        k(0.0, (-5.3e-16, 0.0), (0.0, 0.0)))
    nan = float("nan")
    for sin_kappa in ({"kappa": nan, "ic95": [nan, nan], "ic95_bca": [nan, nan],
                       "frente_a_umbrales": None},
                      {"kappa": None, "ic95": [None, None], "ic95_bca": [None, None],
                       "frente_a_umbrales": None}):
        assert cc._anchura_observada(sin_kappa) == (
            "el kappa ponderado no es calculable con estas lecturas, y su intervalo tampoco.")


def test_lo_observado_y_el_criterio_no_se_contradicen_sobre_el_0_4():
    """Un barrido de límites inferiores alrededor de 0,4: si el criterio dice
    que el límite queda por debajo de 0,4 con un método, «Observado» tiene
    el 0,4 dentro con ese método; si dice que no, lo tiene fuera o el límite
    es el propio umbral. Y cada frase cuadra con los límites que imprime."""
    import re
    candidatos = [0.4 + d for d in (-0.3, -0.05, -0.0051, -0.005, -0.0049, -0.0004,
                                    -4e-7, -1e-16, 0.0, 1e-16, 4e-7, 0.0004, 0.0027,
                                    0.0049, 0.005, 0.0051, 0.05)]
    for li_a in candidatos:
        for li_b in candidatos:
            r = {"kappa": 0.7, "ic95": [li_a, 0.95], "ic95_bca": [li_b, 0.93], "n": 24}
            r["frente_a_umbrales"] = cc.frente_a_umbrales(r)
            observado = cc._anchura_observada(r)
            # lo que dice del 0,4 (los límites superiores dejan el 0,6 dentro)
            del_0_4 = re.search(
                r"; el 0,4(?: y el 0,6)? quedan? (dentro con los dos métodos|fuera con "
                r"los dos métodos|dentro con (el método analítico|el BCa) y fuera con)",
                observado)
            assert del_0_4, observado
            for li, metodo, clave in ((li_a, "el método analítico", "li_analitico_lt_0_4"),
                                      (li_b, "el BCa", "li_bca_lt_0_4")):
                debajo = r["frente_a_umbrales"][clave]
                impreso = re.search(rf"de (-?[\d,]+) a [\d,]+ con {metodo}", observado)
                inferior = float(impreso.group(1).replace(",", "."))
                dentro = (del_0_4.group(1) == "dentro con los dos métodos"
                          or del_0_4.group(2) == metodo)
                # lo que dice del 0,4 cuadra con el límite que imprime...
                assert dentro == (inferior <= 0.4), (li, observado)
                # ...y con lo que dice el criterio de ese mismo límite
                if debajo:
                    assert dentro, (li, observado)
                else:
                    assert not dentro or inferior == 0.4, (li, observado)


def test_dentro_de_la_horquilla_da_el_recuento_y_redondea_como_el_bot():
    def dicho(dentro, n=24):
        return cc._dentro_de_la_horquilla({"dentro_de_la_horquilla": dentro, "n": n})
    assert dicho(7) == "7 de 24 casos (29 %)"
    # 3 de 24 son el 12,5 %: hacia arriba, como `Math.round` en el bot
    assert dicho(3) == "3 de 24 casos (13 %)" and dicho(15) == "15 de 24 casos (63 %)"
    assert dicho(9) == "9 de 24 casos (38 %)" and dicho(21) == "21 de 24 casos (88 %)"
    assert dicho(0) == "0 de 24 casos (0 %)" and dicho(24) == "24 de 24 casos (100 %)"
    assert dicho(1, 1) == "1 de 1 caso (100 %)"
    assert cc._dentro_de_la_horquilla({"n": 24}) == "—"


def test_sesion_json_no_lleva_nan(tmp_path):
    """Con el porcentaje del médico constante Spearman no es calculable: en
    `sesion.json` va `null`, que un lector estricto abre, y en el acta «—»."""
    repo = pathlib.Path(__file__).resolve().parents[1]
    sesion = tmp_path / "sesion"
    (sesion / "corpus").mkdir(parents=True)
    clave = _clave()
    (sesion / "clave.json").write_text(json.dumps(clave, ensure_ascii=False), encoding="utf-8")
    (sesion / "corpus" / "mensajes.json").write_text("{}", encoding="utf-8")
    casos = {c["patientId"]: c for c in clave["casos"]}
    _csv(sesion / "lectura1.csv", [
        _fila(1, i + 1, casos[pid], casos[pid]["categoria"]["primaria"], 50, 60.0)
        for i, pid in enumerate(clave["ordenes"]["lectura1"])])
    salida, acta = tmp_path / "out" / "sesion.json", tmp_path / "out" / "acta-h7.md"
    r = subprocess.run(
        [sys.executable, str(repo / "scripts" / "analizar_sesion.py"), "--sesion", str(sesion),
         "--lectura1", "lectura1.csv", "--salida", str(salida), "--acta", str(acta)],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 0, r.stderr
    crudo = salida.read_text(encoding="utf-8")
    assert "NaN" not in crudo and "Infinity" not in crudo

    def estricto(constante):
        raise AssertionError(f"sesion.json lleva {constante}")
    s = json.loads(crudo, parse_constant=estricto)
    assert s["acuerdo_continuo"]["spearman"] is None
    assert s["kappa"]["ponderado_lineal"]["kappa"] == pytest.approx(1.0)
    assert "Spearman —;" in _plano(acta.read_text(encoding="utf-8"))


def test_pegado_a_un_umbral_imprime_los_decimales_que_lo_distinguen():
    assert cc._f_frente_a_umbral(0.3996) == "0,3996"
    assert cc._f_frente_a_umbral(0.397) == "0,397"
    assert cc._f_frente_a_umbral(0.4049) == "0,405"
    assert cc._f_frente_a_umbral(0.6041) == "0,604"
    assert cc._f_frente_a_umbral(0.4) == "0,40" and cc._f_frente_a_umbral(0.6) == "0,60"
    assert cc._f_frente_a_umbral(0.41) == "0,41" and cc._f_frente_a_umbral(0.5) == "0,50"
    assert cc._f_frente_a_umbral(-0.12) == "-0,12"
    assert cc._f_frente_a_umbral(float("nan")) == "—"
    assert cc._f_frente_a_umbral(None) == "—"
    # hasta seis decimales, los que hagan falta para que no se lea el umbral
    assert cc._f_frente_a_umbral(0.39996) == "0,39996"
    assert cc._f_frente_a_umbral(0.399996) == "0,399996"
    assert cc._f_frente_a_umbral(0.600004) == "0,600004"
    # y lo que a seis decimales es el umbral, se imprime como el umbral
    assert cc._f_frente_a_umbral(0.3999999999999999) == "0,40"
    assert cc._f_frente_a_umbral(0.4000000004) == "0,40"
    assert cc._f_frente_a_umbral(0.6000000000000001) == "0,60"


def test_la_fecha_es_la_de_ecuador_continental_y_no_la_de_la_maquina():
    import datetime
    assert cc.ZONA_DE_LA_SESION == datetime.timezone(datetime.timedelta(hours=-5))

    def ms(*cuando):
        return int(datetime.datetime(*cuando, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    assert cc._fecha(ms(2026, 10, 7, 4, 59, 59)) == "2026-10-06"     # las 23:59:59 del 6 en UTC−5
    assert cc._fecha(ms(2026, 10, 7, 5, 0, 0)) == "2026-10-07"       # las 00:00:00 del 7
    assert cc._fecha(None) == "—" and cc._fecha(0) == "—"


def test_la_fecha_sale_de_la_zona_de_la_sesion_y_de_ninguna_otra(monkeypatch):
    """En una maquina que ya esta en UTC−5 la prueba de arriba pasaria tambien
    con la hora local: aqui se cambia la zona y el dia tiene que cambiar."""
    import datetime
    instante = int(datetime.datetime(2026, 10, 7, 4, 59, 59,
                                     tzinfo=datetime.timezone.utc).timestamp() * 1000)
    assert cc._fecha(instante) == "2026-10-06"
    monkeypatch.setattr(cc, "ZONA_DE_LA_SESION",
                        datetime.timezone(datetime.timedelta(hours=9)))
    assert cc._fecha(instante) == "2026-10-07"
    monkeypatch.setattr(cc, "ZONA_DE_LA_SESION",
                        datetime.timezone(datetime.timedelta(hours=-12)))
    assert cc._fecha(instante) == "2026-10-06"
    assert cc._fecha(instante + 8 * 3600 * 1000) == "2026-10-07"


def test_el_acta_dice_la_zona_horaria_de_las_fechas(tmp_path):
    clave = _clave()
    l1, _ = _lecturas(clave)
    s = cc.analizar(clave, _leidas(tmp_path, "l1.csv", l1))
    plano = _plano(cc.rellenar_acta(_plantilla(), cc.valores_para_acta(s, clave)))
    assert (f"**Fechas:** lectura el {cc._fecha(INICIO + 100000)}. Cada fecha es el día en la hora "
            f"de Ecuador continental (UTC−5).") in plano


def test_la_tabla_de_desacuerdos_imprime_la_horquilla_como_el_bot(tmp_path):
    clave = _clave()
    clave["casos"][2]["bloque"] = {"minima": 0.125, "maxima": 0.125}     # el bot dice 13 %, no 12 %
    clave["casos"][4]["bloque"] = {"minima": 0.0047, "maxima": 0.0470}   # «entre menos de 1 % y 5 %»
    casos = {c["patientId"]: c for c in clave["casos"]}
    discrepa = {"c-02": "intermedia", "c-04": "intermedia"}
    l1 = [_fila(1, i + 1, casos[pid], discrepa.get(pid, casos[pid]["categoria"]["primaria"]), 50, 60.0)
          for i, pid in enumerate(clave["ordenes"]["lectura1"])]
    _csv(tmp_path / "l1.csv", l1)
    s = cc.analizar(clave, cc.leer_csv(tmp_path / "l1.csv"))
    acta = cc.rellenar_acta(_plantilla(), cc.valores_para_acta(s, clave))
    assert "| 13 % |" in acta
    assert "| entre menos de 1 % y 5 % |" in acta
    assert cc._horquilla_como_el_bot(0.97, 0.9960) == "entre 97 % y más de 99 %"


def _plantilla():
    return (pathlib.Path(__file__).resolve().parents[1] / "docs" / "validacion-semisintetica"
            / "acta-h7-plantilla.md").read_text(encoding="utf-8")


def _plano(acta):
    """El acta con los saltos de línea de la plantilla como espacios, para
    buscar frases que la plantilla parte en dos líneas."""
    return " ".join(acta.split())


def test_el_acta_del_plan_b_describe_una_sola_sesion_secuencial(tmp_path):
    # Ruling 7: bajo plan B, el método y las fechas no deben describir dos
    # lecturas separadas por siete días ni dejar «lectura 2 el —».
    clave = _clave()
    casos = {c["patientId"]: c for c in clave["casos"]}
    filas = [_fila(1, i + 1, casos[pid], casos[pid]["categoria"]["primaria"],
                   int(casos[pid]["categoria"]["punto_medio"] * 100), 40.0,
                   notas={"correccion": 4, "utilidad": 4, "lenguaje": 4},
                   banda_con=casos[pid]["categoria"]["primaria"], pct_con=50, seg_con=20.0)
             for i, pid in enumerate(clave["ordenes"]["lectura1"])]
    _csv(tmp_path / "planb.csv", filas)
    l1 = cc.leer_csv(tmp_path / "planb.csv")
    pb = cc.leer_csv(tmp_path / "planb.csv")
    s = cc.analizar(clave, l1, planb=pb)
    acta = cc.rellenar_acta(_plantilla(), cc.valores_para_acta(s, clave))
    assert "{{" not in acta
    assert "lectura secuencial" in acta
    assert "siete días" not in acta
    assert "lectura 2 el —" not in acta
    assert f"sesión única el {cc._fecha(INICIO + 100000)}" in acta
    assert "no hay controles en el plan B" in _plano(acta)


def test_el_acta_de_dos_lecturas_usa_los_recuentos_reales_no_cifras_tecleadas(tmp_path):
    # Ruling 7: el método debe citar los n_con_mensaje/n_controles reales de
    # la sesión, no los «20 casos y 4 controles» de la plantilla de antes.
    # Con 21/3 un «20»/«4» tecleado no pasaría.
    clave = _clave(controles=("c-00", "c-08", "c-09"))
    l1, l2 = _lecturas(clave)
    # tiempos distintos en los controles, para que la razón corregida tenga un intervalo de verdad
    for fila, segundos in zip([f for f in l2 if f["control"] == "true"], (54.0, 60.0, 69.0)):
        fila["segundos"] = segundos
    l1r, l2r = _leidas(tmp_path, "l1.csv", l1), _leidas(tmp_path, "l2.csv", l2)
    s = cc.analizar(clave, l1r, l2r, huellas={"mensajes_json": "a" * 64, "clave_json": "b" * 64})
    assert s["lectura2"]["n_con_mensaje"] == 21 and s["lectura2"]["n_controles"] == 3
    t = s["lectura2"]["tiempo"]
    acta = cc.rellenar_acta(_plantilla(), cc.valores_para_acta(s, clave))
    assert "{{" not in acta
    plano = _plano(acta)
    assert "con el mensaje real del sistema en 21 casos y 3 controles sin mensaje" in plano
    assert "la primera sin copiloto (placa y viñeta; banda y porcentaje) el" in plano
    lo, hi = t["ic95_razon_corregida"]
    assert lo < hi
    assert f"razón corregida por releer {cc._f(t['razon_corregida_por_releer'])} (IC 95 % {cc._f(lo)} a {cc._f(hi)})" in plano
    assert "reducción del 50 %" in plano and "reducción -" not in plano
    assert "Razones individuales de los controles (lectura 2 / lectura 1): 0,90; 1,00; 1,15." in plano
    assert f"**Fechas:** lectura 1 el {s['fechas']['lectura1']}; lectura 2 el {s['fechas']['lectura2']}." in plano
    assert "Los mensajes del sistema se generaron con bots contra el sistema desplegado, con la prevalencia desplegada (0,1466)" in plano
    assert "la categoría del sistema sale del bloque `combinacion` del mensaje." in plano
    assert ("Los síntomas referidos son un fondo constante en todos los casos (salvo el asma y la fiebre, "
            "que siguen a la clínica generada) y así se le dijo al médico.") in plano
    assert "## Pregunta sobre el PACS" in acta
    assert "(Respuesta del médico en la reunión de preparación; se anota a mano.)" in plano
    assert f"**Congelado verificable:** sha256 de mensajes.json `{'a' * 64}` y de clave.json `{'b' * 64}`." in plano
    assert "corrección 5,0 (n = 21); utilidad 4,0 (n = 21); lenguaje 3,0 (n = 21)" in plano
    assert ".." not in acta


def test_el_acta_dice_aumento_si_el_tiempo_sube_y_cita_la_imagen_local(tmp_path):
    clave = _clave()
    clave["origen_mensajes"] = {"con_bots": False, "imagen_tag": "h7-sesion", "imagen_digest": "sha256:0123abcd"}
    l1, l2 = _lecturas(clave, segundos_con=75.0)             # con el mensaje tarda más: razón 1,25
    s = cc.analizar(clave, _leidas(tmp_path, "l1.csv", l1), _leidas(tmp_path, "l2.csv", l2))
    plano = _plano(cc.rellenar_acta(_plantilla(), cc.valores_para_acta(s, clave)))
    assert "aumento del 25 %" in plano and "reducción del" not in plano
    assert "se generaron con la imagen local del tag h7-sesion, digest sha256:0123abcd, con la prevalencia" in plano
    assert cc._plural(1, "control", "controles") == "1 control"
    assert cc._plural(3, "control", "controles") == "3 controles"


def test_la_tabla_de_desacuerdos_escapa_barras_y_saltos_de_linea(tmp_path):
    clave = _clave()
    l1, _ = _lecturas(clave, discrepa={"c-02": "intermedia"})
    next(f for f in l1 if f["id"] == "c-02")["comentario"] = "opacidad | dudosa\nver base"
    s = cc.analizar(clave, _leidas(tmp_path, "l1.csv", l1))
    acta = cc.rellenar_acta(_plantilla(), cc.valores_para_acta(s, clave))
    fila = next(linea for linea in acta.splitlines() if linea.startswith("| c-02 |"))
    assert fila.endswith("| opacidad \\| dudosa / ver base |")
    assert fila.count(" | ") == 5                                # seis celdas, ni una más


def test_la_plantilla_no_teclea_cifras_de_la_sesion():
    plantilla = _plantilla()
    for tecleada in ("24 casos", "20 casos", "4 controles", "0,1466", "h7-sesion", "sha256:"):
        assert tecleada not in plantilla


# --------------------------------------------------------------------------
# B1-B2: lo que analizar rechaza antes de calcular nada.
# --------------------------------------------------------------------------
def test_analizar_rechaza_los_ficheros_cambiados(tmp_path):
    clave = _clave()
    l1, l2 = _lecturas(clave)
    l1r, l2r = _leidas(tmp_path, "l1.csv", l1), _leidas(tmp_path, "l2.csv", l2)
    with pytest.raises(ValueError, match="la lectura 1 lleva filas de la lectura 2"):
        cc.analizar(clave, l2r, l1r)


def test_analizar_rechaza_el_mismo_csv_dos_veces(tmp_path):
    clave = _clave()
    l1, _ = _lecturas(clave)
    l1r = _leidas(tmp_path, "l1.csv", l1)
    with pytest.raises(ValueError, match="la lectura 2 lleva filas de la lectura 1") as e:
        cc.analizar(clave, l1r, l1r)
    assert "controles de la lectura 2 (ninguno)" in str(e.value)


def test_analizar_rechaza_una_lectura_2_incompleta_o_con_duplicados(tmp_path):
    clave = _clave()
    l1, l2 = _lecturas(clave)
    l1r = _leidas(tmp_path, "l1.csv", l1)
    with pytest.raises(ValueError, match="faltan 3 y sobran 0"):
        cc.analizar(clave, l1r, _leidas(tmp_path, "l2a.csv", l2[:-3]))
    duplicada = l2[:5] + [dict(l2[4])] + l2[6:]                  # la sexta fila repite la quinta
    with pytest.raises(ValueError, match=f"la lectura 2 repite {l2[4]['id']}"):
        cc.analizar(clave, l1r, _leidas(tmp_path, "l2b.csv", duplicada))


def test_analizar_rechaza_controles_que_no_son_los_de_la_clave(tmp_path):
    clave = _clave()
    l1, l2 = _lecturas(clave)
    clave["ordenes"]["controles"] = ["c-00", "c-01", "c-08", "c-10"]
    with pytest.raises(ValueError, match="no son los de la clave"):
        cc.analizar(clave, _leidas(tmp_path, "l1.csv", l1), _leidas(tmp_path, "l2.csv", l2))


def test_analizar_rechaza_un_plan_b_sin_la_respuesta_con_el_mensaje(tmp_path):
    clave = _clave()
    l1, _ = _lecturas(clave)                                     # lectura 1 sin banda_con
    l1r = _leidas(tmp_path, "planb.csv", l1)
    with pytest.raises(ValueError, match="el plan B no tiene la respuesta con el mensaje en 24 filas"):
        cc.analizar(clave, l1r, planb=l1r)


def test_analizar_exige_la_clave_definitiva(tmp_path):
    clave = _clave()
    l1, _ = _lecturas(clave)
    l1r = _leidas(tmp_path, "l1.csv", l1)
    del clave["casos"][5]["categoria"]
    with pytest.raises(ValueError, match="la clave no es la definitiva: corre --fase mensajes antes de analizar"):
        cc.analizar(clave, l1r)
    clave = _clave()
    del clave["origen_mensajes"]
    with pytest.raises(ValueError, match="origen_mensajes"):
        cc.analizar(clave, l1r)


def test_la_categoria_del_kappa_es_la_del_mensaje_no_la_prevista(tmp_path):
    """D3: si el bloque del mensaje da otra categoría que la prevista, manda
    la del mensaje (es lo que el médico ve)."""
    clave = _clave()
    c = clave["casos"][3]                                        # baja en el mensaje
    c["categoria_prevista"] = dict(c["categoria"], primaria="alta")
    c["bloque_previsto"] = {"minima": 0.8, "maxima": 0.9}
    l1, _ = _lecturas(clave)                                     # el médico dice «baja», como el mensaje
    s = cc.analizar(clave, _leidas(tmp_path, "l1.csv", l1))
    assert s["desacuerdos"] == []
    assert s["kappa"]["ponderado_lineal"]["kappa"] == pytest.approx(1.0)
    l1, _ = _lecturas(clave, discrepa={"c-03": "alta"})          # ahora dice lo previsto, no lo del mensaje
    s = cc.analizar(clave, _leidas(tmp_path, "l1b.csv", l1))
    assert [(d["id"], d["sistema"], d["horquilla"]) for d in s["desacuerdos"]] == \
        [("c-03", "baja", [c["bloque"]["minima"], c["bloque"]["maxima"]])]


# --------------------------------------------------------------------------
# El script entero, como lo corre el equipo.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("modo", ["lectura2", "planb"])
def test_analizar_sesion_escribe_sesion_json_y_un_acta_sin_huecos(tmp_path, modo):
    repo = pathlib.Path(__file__).resolve().parents[1]
    entorno = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    sesion = tmp_path / "sesion"
    (sesion / "corpus").mkdir(parents=True)
    clave = _clave()
    (sesion / "clave.json").write_text(json.dumps(clave, ensure_ascii=False), encoding="utf-8")
    (sesion / "corpus" / "mensajes.json").write_text("{}", encoding="utf-8")
    l1, l2 = _lecturas(clave, discrepa={"c-02": "intermedia"})
    if modo == "lectura2":
        _csv(sesion / "lectura1.csv", l1)
        _csv(sesion / "lectura2.csv", l2)
        argumentos = ["--lectura1", "lectura1.csv", "--lectura2", "lectura2.csv"]
    else:
        for fila in l1:
            fila.update(banda_con=fila["banda"], porcentaje_con=fila["porcentaje"], segundos_con=20.0,
                        correccion=4, utilidad=4, lenguaje=4)
        _csv(sesion / "planb.csv", l1)
        argumentos = ["--lectura1", "planb.csv", "--planb", "planb.csv"]
    salida, acta = tmp_path / "out" / "sesion.json", tmp_path / "out" / "acta-h7.md"
    script = str(repo / "scripts" / "analizar_sesion.py")
    r = subprocess.run([sys.executable, script, "--sesion", str(sesion), *argumentos,
                        "--salida", str(salida), "--acta", str(acta)],
                       capture_output=True, text=True, encoding="utf-8", env=entorno)
    assert r.returncode == 0, r.stderr
    s = json.loads(salida.read_text(encoding="utf-8"))
    assert s["huellas"]["clave_json"] == _sha256(sesion / "clave.json")
    assert s["huellas"]["mensajes_json"] == _sha256(sesion / "corpus" / "mensajes.json")
    texto = acta.read_text(encoding="utf-8")
    assert "{{" not in texto and "}}" not in texto
    plano = _plano(texto)
    assert (f"**Congelado verificable:** sha256 de mensajes.json `{s['huellas']['mensajes_json']}` "
            f"y de clave.json `{s['huellas']['clave_json']}`.") in plano
    assert ("lectura 1 el" in texto) == (modo == "lectura2")
    assert ("lectura secuencial" in texto) == (modo == "planb")
    # las frases nuevas del acta, en el fichero que se escribe
    assert "se generaron con bots contra el sistema desplegado, con la prevalencia desplegada (0,1466)" in plano
    assert "**Frente a 0,4 y 0,6:** El kappa ponderado (" in plano
    assert "casos cuya horquilla cruza un límite: 1 de 24." in plano
    assert "horquillas son un solo valor impreso, y 0 de ellas una cota" in plano
    assert "**Declarado antes de la sesión** (spec de SP5 §5.5): «" + cc.TEXTO_FIJADO in plano
    assert "**Observado en esta sesión:** el intervalo del 95 % del kappa ponderado va de " in plano
    # sesion.json lo abre un lector estricto: no lleva NaN
    def estricto(constante):
        raise AssertionError(f"sesion.json lleva {constante}")
    json.loads(salida.read_text(encoding="utf-8"), parse_constant=estricto)
    assert "Los síntomas referidos son un fondo constante en todos los casos" in plano
    assert "## Pregunta sobre el PACS" in texto
    assert ("Razones individuales de los controles (lectura 2 / lectura 1): "
            + ("1,00; 1,00; 1,00; 1,00." if modo == "lectura2" else "no hay controles en el plan B.")) in plano
    assert "| c-02 | positiva clara | baja | intermedia (8 %) | entre 3 % y 13 % | dudoso |" in texto
    assert "_" not in plano.split("## Desacuerdos")[1].split("## Pregunta")[0]    # sin claves internas
    # sin mensajes.json no se escribe nada: el acta no podría citar su huella
    (sesion / "corpus" / "mensajes.json").unlink()
    r = subprocess.run([sys.executable, script, "--sesion", str(sesion), *argumentos,
                        "--salida", str(tmp_path / "otra.json"), "--acta", str(tmp_path / "otra.md")],
                       capture_output=True, text=True, encoding="utf-8", env=entorno)
    assert r.returncode != 0 and "mensajes.json" in r.stderr
    assert not (tmp_path / "otra.json").exists()


def _sha256(ruta):
    return hashlib.sha256(pathlib.Path(ruta).read_bytes()).hexdigest()
