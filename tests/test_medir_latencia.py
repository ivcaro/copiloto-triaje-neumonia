# -*- coding: utf-8 -*-
"""La latencia del sistema desplegado (spec de SP5 §6.3), con filas fabricadas.

No hay sistema desplegado al que hablar desde una prueba: las filas son las
que `pruebas/reproducir_casos.py` deja en `latencias.json`, escritas a mano.
Lo que se ata es que filas cuentan (y que lo decide LA CONSULTA MEDIDA, no la
llamada propia del arnes), que cifras salen de ellas, que el JSON dice por si
solo que mide y que no, y que con menos de 30 no se escribe nada.
"""
import importlib.util
import json
import pathlib

import numpy as np
import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
DESCARTES = {"total": 0, "sin_bots": 0, "rechazo_previsto": 0, "fallo": 0,
             "error": 0, "no_coincide": 0, "sin_ms_extremo": 0}
CINCO = [5.2, 4.8, 6.1, 5.0, 5.5]


@pytest.fixture(scope="module")
def medir():
    """`scripts/medir_latencia.py` cargado como modulo."""
    spec = importlib.util.spec_from_file_location(
        "medir_latencia", REPO / "scripts" / "medir_latencia.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _fila(ms_extremo=1000, ms_modelo=150.0, **cambios):
    fila = {"patientId": "p", "perfil": "01-positiva_clara",
            "rechazo_previsto": False, "con_bots": True, "fallo": None,
            "error_consulta": None, "coincide": "sí", "ms_extremo": ms_extremo,
            "ms_modelo": ms_modelo, "error_arnes": None, "ms_arnes": 60.0}
    fila.update(cambios)
    return fila


def _validas(n=40):
    """n consultas validas de 1000, 1100, 1200... ms."""
    return [_fila(ms_extremo=1000 + 100 * i, ms_modelo=140.0 + i) for i in range(n)]


def _descartes(**cuentas):
    return dict(DESCARTES, total=sum(cuentas.values()), **cuentas)


def test_las_claves_de_una_fila_son_las_que_escribe_el_arnes(medir):
    from pruebas.reproducir_casos import filas_de_latencia
    caso = {"patientId": "p", "perfil": type("P", (), {"carpeta": "01-positiva_clara"})()}
    fila = filas_de_latencia([(caso, {"con_bots": False}, {"error": None, "resultado": None})])[0]
    assert tuple(fila) == medir.CLAVES
    assert tuple(_fila()) == medir.CLAVES


def test_resumir_da_p50_y_p95_de_las_consultas_validas(medir):
    r = medir.resumir(_validas(40))
    assert r["n"] == 40
    assert r["p50_ms"] == 2950.0
    assert r["p95_ms"] == 4705.0
    assert r["menor_ms"] == 1000.0 and r["mayor_ms"] == 4900.0
    assert "minimo_ms" not in r and "maximo_ms" not in r
    assert r["modelo_p50_ms"] == 159.5
    assert r["umbrales_s"] == {"minimo": 8, "objetivo": 3}
    assert r["frente_a_umbrales"] == {
        "p50": {"cumple_minimo": True, "cumple_objetivo": True},
        "p95": {"cumple_minimo": True, "cumple_objetivo": False}}
    assert r["descartadas"] == DESCARTES
    assert r["total_a_mano"] == "no medido"


def test_cualquiera_puede_recalcular_los_percentiles(medir):
    """Se publican las medidas, ordenadas y sin identificadores, y el metodo."""
    desordenadas = list(reversed(_validas(37)))
    r = medir.resumir(desordenadas)
    assert r["ms_extremo_ordenados"] == [1000.0 + 100 * i for i in range(37)]
    assert len(r["ms_extremo_ordenados"]) == r["n"] == 37
    p50, p95 = np.percentile(r["ms_extremo_ordenados"], [50, 95], method="linear")
    assert (r["p50_ms"], r["p95_ms"]) == (round(float(p50), 1), round(float(p95), 1))
    assert "tipo 7 de Hyndman y Fan" in r["percentil"]
    assert "`ms_extremo_ordenados`" in r["percentil"]
    # con 37 consultas el p95 cae entre la 35.ª y la 36.ª: el maximo no entra
    assert r["ms_extremo_ordenados"][34] < r["p95_ms"] < r["ms_extremo_ordenados"][35]
    assert all(set(f) == set(medir.CLAVES) for f in desordenadas), "no se tocan las filas"


def test_el_json_dice_por_si_solo_que_mide_y_que_no(medir):
    r = medir.resumir(_validas(30), manual=CINCO)
    assert r["titulo"] == ("Latencia del sistema desplegado, medida con el arnés "
                           "(no es una simulación): el tramo `ms_extremo`, cota "
                           "inferior de la latencia de extremo a extremo")
    assert "semisintética" not in json.dumps(r, ensure_ascii=False)
    for trozo in ("`Normalizar update`", "`Desenlace`", "la subida a Telegram",
                  "la entrega del webhook", "el envío de `Responder`"):
        assert trozo in r["tramo"], trozo
    for trozo in ("cota inferior", "tampoco lo cumple de extremo a extremo",
                  "necesario pero no suficiente", "se acota, si se cronometró, en "
                  "`total_a_mano`"):
        assert trozo in r["lectura"], trozo
    for trozo in ("tiempo TOTAL, no el tramo que falta", "no un percentil",
                  "no se suma a `p50_ms`"):
        assert trozo in r["total_a_mano"]["que_es"], trozo
    assert list(r) == ["titulo", "tramo", "lectura", "corrida_del", "n", "percentil",
                       "p50_ms", "p95_ms", "menor_ms", "mayor_ms",
                       "ms_extremo_ordenados", "modelo_p50_ms", "umbrales_s",
                       "frente_a_umbrales", "total_a_mano", "veredicto",
                       "descartadas", "glosario"]
    assert list(r["descartadas"]) == ["total"] + list(medir.MOTIVOS)
    # cada motivo de descarte y cada clave que no se explica sola, glosados
    assert list(r["glosario"]["descartadas"]) == list(medir.MOTIVOS)
    assert set(r["glosario"]) == {"n", "menor_ms y mayor_ms", "modelo_p50_ms",
                                  "corrida_del", "descartadas"}
    assert "no son umbrales" in r["glosario"]["menor_ms y mayor_ms"]


def test_el_json_lleva_la_regla_y_la_etiqueta_que_sale_de_ella(medir):
    """Con el p95 cumpliendo y lo cronometrado por encima de 8 s, lo único que
    el JSON afirmaba como dato era `cumple_minimo: true`. La etiqueta que
    manda el spec §6.2 es «no cumplido»."""
    def v(ms, manual=None):
        return medir.resumir([_fila(ms_extremo=ms)] * 30, manual=manual)["veredicto"]
    lento = [9.4, 8.7, 10.2, 9.0, 8.9]
    assert v(4000) == {"regla": medir.REGLA, "p95_cumple_el_minimo": True,
                       "a_mano_supera_el_minimo": None, "etiqueta": "cumplido con cambio"}
    assert v(4000, CINCO)["etiqueta"] == "cumplido con cambio"
    assert v(4000, CINCO)["a_mano_supera_el_minimo"] is False
    assert v(4000, lento) == {"regla": medir.REGLA, "p95_cumple_el_minimo": True,
                              "a_mano_supera_el_minimo": True, "etiqueta": "no cumplido"}
    assert v(8001)["etiqueta"] == "no cumplido" and v(8001, CINCO)["etiqueta"] == "no cumplido"
    # los bordes: 8 s justos cumplen, y una mediana de 8 s justos no supera
    assert v(8000)["etiqueta"] == "cumplido con cambio"
    assert v(8000, [8.0] * 5)["etiqueta"] == "cumplido con cambio"
    # sin redondear: 8,004 s se escribe «8.0» y supera los 8 s
    apenas = medir.resumir([_fila(ms_extremo=4000)] * 30, manual=[8.004] * 5)
    assert apenas["total_a_mano"]["mediana_s"] == 8.0
    assert apenas["veredicto"]["a_mano_supera_el_minimo"] is True
    assert apenas["veredicto"]["etiqueta"] == "no cumplido"
    assert v(8000.04)["etiqueta"] == "no cumplido"
    for trozo in ("p95 de `ms_extremo` frente al mínimo de 8 s", "«cumplido con cambio»",
                  "Lo cronometrado a mano pesa en contra", "objetivo de 3 s",
                  "spec de SP5 §6.2"):
        assert trozo in medir.REGLA, trozo


def test_la_corrida_lleva_su_fecha_en_la_hora_de_ecuador(medir, tmp_path):
    import datetime
    import os
    corrida = tmp_path / "latencias.json"
    corrida.write_text(json.dumps(_validas(30)), encoding="utf-8")
    # las 04:59:59 UTC del 7 son las 23:59:59 del 6 en Ecuador continental
    instante = datetime.datetime(2026, 10, 7, 4, 59, 59,
                                 tzinfo=datetime.timezone.utc).timestamp()
    os.utime(corrida, (instante, instante))
    assert medir.fecha_de(corrida) == "2026-10-06"
    os.utime(corrida, (instante + 1, instante + 1))
    assert medir.fecha_de(corrida) == "2026-10-07"
    assert medir.ZONA == datetime.timezone(datetime.timedelta(hours=-5))
    salida = tmp_path / "latencia.json"
    assert medir.main(["--corrida", str(corrida), "--salida", str(salida)]) == 0
    assert json.loads(salida.read_text(encoding="utf-8"))["corrida_del"] == "2026-10-07"
    assert medir.resumir(_validas(30))["corrida_del"] is None


def test_cuenta_la_consulta_medida_y_no_la_llamada_del_arnes(medir):
    """`ms_extremo` es de la consulta de los bots: su error es el que decide.

    Un `copiloto_no_responde` DEL FLUJO (el copiloto no contesto a n8n) no
    alcanza a la llamada propia del arnes, que segundos despues sale limpia.
    Esa consulta NO es valida, y su medida no entra en el p95. (Los 30 450 ms
    son ilustrativos: el nodo reintenta, y un tiempo agotado de verdad pasa
    del minuto.)"""
    filas = _validas(30) + [
        _fila(error_consulta="copiloto_no_responde: tiempo agotado",
              error_arnes=None, ms_extremo=30450, ms_modelo=None,
              coincide="NO: uno dio resultado y el otro no"),
        _fila(error_consulta="descarga_fallida: x", error_arnes=None,
              ms_extremo=9000, coincide="NO: uno dio resultado y el otro no"),
    ]
    r = medir.resumir(filas)
    assert r["n"] == 30 and r["mayor_ms"] == 3900.0
    assert r["descartadas"] == _descartes(error=2)
    # y al reves: si lo que fallo fue la llamada del arnes, la medida es buena
    # solo si las dos lecturas coinciden; si no, se descarta diciendo por que
    filas = _validas(30) + [
        _fila(error_arnes="copiloto_no_responde: x", coincide="sí", ms_extremo=5000),
        _fila(error_arnes="copiloto_no_responde: x", ms_extremo=6000,
              coincide="NO: uno dio resultado y el otro no"),
        _fila(coincide=None, ms_extremo=7000),
    ]
    r = medir.resumir(filas)
    assert r["n"] == 31 and r["mayor_ms"] == 5000.0
    assert r["descartadas"] == _descartes(no_coincide=2)


def test_cada_fila_se_descarta_por_un_solo_motivo_y_en_orden(medir):
    filas = _validas(30) + [
        _fila(con_bots=False, ms_extremo=None),
        _fila(con_bots=False, ms_extremo=None),
        _fila(fallo="no se pudo subir la placa", ms_extremo=None, coincide=None),
        # los rechazos que el corpus busca a proposito (perfiles 05 a 09)
        _fila(perfil="05-menor_edad", rechazo_previsto=True,
              error_consulta="fuera_de_alcance: eso", error_arnes="fuera_de_alcance: eso",
              ms_extremo=410, ms_modelo=None),
        _fila(perfil="08-fichero_corrupto_FABRICADO", rechazo_previsto=True,
              error_consulta="dicom_invalido: x", ms_extremo=90000, ms_modelo=None),
        # un rechazo previsto que NO rechazo tampoco es una consulta de la medida
        _fila(perfil="05-menor_edad", rechazo_previsto=True, ms_extremo=1500),
        # un error que nadie esperaba, en un perfil que tenia que dar resultado
        _fila(error_consulta="copiloto_no_responde: x", ms_extremo=30001),
        _fila(ms_extremo=None),
        # el primero que le toca
        _fila(con_bots=False, fallo="x", rechazo_previsto=True,
              error_consulta="y", coincide="NO", ms_extremo=None),
        # un rechazo previsto que no llego al final es un rechazo previsto:
        # `fallo` cuenta solo las consultas que tenian que dar resultado
        _fila(fallo="x", rechazo_previsto=True, error_consulta="y", ms_extremo=None),
        _fila(perfil="09-fichero_enorme_FABRICADO", rechazo_previsto=True,
              fallo="no se pudo subir la placa", ms_extremo=None, coincide=None),
    ]
    r = medir.resumir(filas)
    assert r["n"] == 30
    assert r["mayor_ms"] == 3900.0, "ni el rechazo de 90 s ni el error de 30 s cuentan"
    assert r["descartadas"] == _descartes(sin_bots=3, rechazo_previsto=5, fallo=1,
                                          error=1, sin_ms_extremo=1)
    assert list(r["descartadas"]) == ["total", "sin_bots", "rechazo_previsto", "fallo",
                                      "error", "no_coincide", "sin_ms_extremo"]
    assert r["n"] + r["descartadas"]["total"] == len(filas)


def test_los_umbrales_se_comparan_en_segundos_y_el_limite_cumple(medir):
    r = medir.resumir([_fila(ms_extremo=3000)] * 20 + [_fila(ms_extremo=8000)] * 10,
                      minimo=30)
    assert r["p50_ms"] == 3000.0 and r["p95_ms"] == 8000.0
    assert r["frente_a_umbrales"] == {
        "p50": {"cumple_minimo": True, "cumple_objetivo": True},
        "p95": {"cumple_minimo": True, "cumple_objetivo": False}}
    lento = medir.resumir([_fila(ms_extremo=8001)] * 30)
    assert lento["frente_a_umbrales"]["p50"] == {"cumple_minimo": False,
                                                 "cumple_objetivo": False}


def test_los_umbrales_se_comparan_sin_redondear(medir):
    """8 000,04 ms se escribe «8000,0», pero no cumple los 8 s."""
    r = medir.resumir([_fila(ms_extremo=8000.04)] * 30)
    assert r["p50_ms"] == 8000.0 and r["p95_ms"] == 8000.0
    assert r["frente_a_umbrales"]["p50"] == {"cumple_minimo": False,
                                             "cumple_objetivo": False}


def test_un_ms_extremo_que_no_es_una_medida_se_descarta(medir):
    malas = [_fila(ms_extremo="1500"), _fila(ms_extremo=True), _fila(ms_extremo=-1),
             _fila(ms_extremo=float("nan")), _fila(ms_extremo=float("inf"))]
    r = medir.resumir(_validas(30) + malas)
    assert r["n"] == 30 and r["mayor_ms"] == 3900.0
    assert r["descartadas"] == _descartes(sin_ms_extremo=5)
    # y un ms_modelo que no es una medida no entra en la mediana del modelo
    r = medir.resumir([_fila(ms_modelo="x")] * 15 + [_fila(ms_modelo=150.0)] * 15)
    assert r["modelo_p50_ms"] == 150.0
    assert medir.resumir([_fila(ms_modelo=None)] * 30)["modelo_p50_ms"] is None


def test_con_menos_del_minimo_no_se_mide_y_dice_cuantas_hay_y_que_hacer(medir):
    filas = _validas(29) + [_fila(error_consulta="copiloto_no_responde: x")]
    with pytest.raises(SystemExit) as salida:
        medir.resumir(filas)
    mensaje = str(salida.value)
    assert "29 consultas" in mensaje and "30" in mensaje
    assert "no medida" in mensaje
    assert "'error': 1" in mensaje
    assert "--por-perfil mayor" in mensaje and "lleva esta causa al informe" in mensaje
    assert "que no son un rechazo previsto" in mensaje
    assert "COPILOTO_URL" not in mensaje
    # si lo que descarta es `no_coincide`, un --por-perfil mayor no arregla nada
    otro_copiloto = ([_fila(coincide="NO: el bot vio 0.9512 y aquí 0.9498")] * 35
                     + [_fila(rechazo_previsto=True)] * 20 + [_fila(fallo="x")])
    with pytest.raises(SystemExit) as salida:
        medir.resumir(otro_copiloto)
    mensaje = str(salida.value)
    assert "hay 0 consultas" in mensaje and "'no_coincide': 35" in mensaje
    assert ("Lo que más descarta es `no_coincide`: el copiloto que contesta al arnés "
            "(COPILOTO_URL) no da la misma lectura que el desplegado.") in mensaje
    assert "--por-perfil mayor" not in mensaje and "lleva esta causa al informe" in mensaje
    with pytest.raises(SystemExit, match="0 consultas"):
        medir.resumir([])
    assert medir.resumir(filas, minimo=29)["n"] == 29
    # con 31 validas hacen falta DOS fallos para quedarse sin medicion
    assert medir.resumir(_validas(30) + [_fila(fallo="x")])["n"] == 30
    with pytest.raises(SystemExit, match="29 consultas"):
        medir.resumir(_validas(29) + [_fila(fallo="x"), _fila(fallo="y")])


def test_lo_medido_a_mano_lleva_los_valores_su_mediana_y_lo_que_es(medir):
    r = medir.resumir(_validas(30), manual=CINCO)
    assert r["total_a_mano"] == {
        "que_es": medir.A_MANO, "valores_s": CINCO, "n": 5,
        "mediana_s": 5.2, "menor_s": 4.8, "mayor_s": 6.1}
    assert medir.resumir(_validas(30), manual=[])["total_a_mano"] == "no medido"
    assert medir.resumir(_validas(30), manual=None)["total_a_mano"] == "no medido"


def test_leer_manual_acepta_segundos_con_punto_y_rechaza_lo_demas(medir):
    assert medir.leer_manual("5.2,4.8, 6.1,5.0,5.5") == CINCO
    assert medir.leer_manual("5,4,6,5,5") == [5.0, 4.0, 6.0, 5.0, 5.0]
    assert medir.leer_manual(None) is None
    assert medir.A_MANO_N == 5
    # el marcador del runbook, copiado tal cual, NO escribe medidas inventadas
    for malo in ("S1,S2,S3,S4,S5", "<s1>,<s2>", "5.2;4.8", "cinco", "5.2,,4.8,6.1,5.0",
                 "5.2,4.8,6.1,5.0,-1", "5.2,4.8,6.1,5.0,0", "5.2,4.8,6.1,5.0,nan",
                 "5.2,4.8,6.1,5.0,inf", "",
                 # cuatro, seis, y los diez que salen de escribir los decimales con coma
                 "5.2,4.8,6.1,5.0", "5.2,4.8,6.1,5.0,5.5,5.1", "5,2,4,8,6,1,5,0,5,5"):
        with pytest.raises(SystemExit, match="--manual espera los 5 tiempos"):
            medir.leer_manual(malo)


def test_ni_el_script_ni_el_runbook_traen_medidas_de_ejemplo(medir):
    """Una orden lista para copiar con cinco tiempos inventados acabaria en un
    JSON versionado: el ejemplo es un marcador que `leer_manual` rechaza."""
    import re
    for ruta in (REPO / "scripts" / "medir_latencia.py", REPO / "docs" / "sp5-sesion.md",
                 REPO / "docs" / "validacion-semisintetica" / "README.md"):
        texto = ruta.read_text(encoding="utf-8")
        assert not re.search(r"--manual\s+\"?\d", texto), ruta.name
    runbook = (REPO / "docs" / "sp5-sesion.md").read_text(encoding="utf-8")
    marcador = re.search(r'--manual "([^"]+)"', runbook).group(1)
    with pytest.raises(SystemExit, match="--manual"):
        medir.leer_manual(marcador)


def test_la_cli_escribe_el_json_y_no_lo_escribe_si_no_hay_minimo(medir, tmp_path, capsys):
    corrida = tmp_path / "corpus" / "latencias.json"
    corrida.parent.mkdir()
    corrida.write_text(json.dumps(_validas(36)), encoding="utf-8")
    salida = tmp_path / "docs" / "latencia.json"
    assert medir.main(["--corrida", str(corrida), "--salida", str(salida),
                       "--manual", "5.2,4.8,6.1,5.0,5.5"]) == 0
    escrito = json.loads(salida.read_text(encoding="utf-8"))
    assert escrito == medir.resumir(_validas(36), manual=CINCO,
                                    corrida_del=medir.fecha_de(corrida))
    crudo = salida.read_bytes()
    assert "simulación)".encode("utf-8") in crudo, "sin escapes \\u"
    assert b"\r" not in crudo and crudo.endswith(b"}\n")
    dicho = capsys.readouterr().out
    assert "36 consultas" in dicho and "p50 2,75 s" in dicho and "p95 4,33 s" in dicho
    assert f"corrida del {medir.fecha_de(corrida)}" in dicho
    assert "etiqueta del KPI: «cumplido con cambio»" in dicho
    assert "AVISO" not in dicho
    # lo cronometrado se repite en pantalla: un decimal con coma se ve aqui
    assert "cronometrado a mano: 5,20 s; 4,80 s; 6,10 s; 5,00 s; 5,50 s" in dicho
    assert "cinco tiempos" in medir.leer_manual.__doc__.lower()

    corta = tmp_path / "corta.json"
    corta.write_text(json.dumps(_validas(12)), encoding="utf-8")
    with pytest.raises(SystemExit, match="12 consultas"):
        medir.main(["--corrida", str(corta), "--salida", str(salida)])
    assert json.loads(salida.read_text(encoding="utf-8")) == escrito, "no pisa el bueno"
    otra = tmp_path / "no-se-escribe.json"
    with pytest.raises(SystemExit, match="12 consultas"):
        medir.main(["--corrida", str(corta), "--salida", str(otra)])
    assert not otra.exists()
    with pytest.raises(SystemExit, match="--manual"):
        medir.main(["--corrida", str(corrida), "--salida", str(otra),
                    "--manual", "S1,S2,S3,S4,S5"])
    assert not otra.exists()


def test_la_ayuda_de_manual_dice_que_son_cinco_tiempos(medir, capsys):
    with pytest.raises(SystemExit) as salida:
        medir.main(["--help"])
    assert salida.value.code == 0
    ayuda = " ".join(capsys.readouterr().out.split())
    assert "los cinco tiempos, en segundos, de envío a respuesta" in ayuda
    assert "con punto decimal y separados por comas" in ayuda


def test_repetir_sin_manual_avisa_de_que_se_pierde_lo_medido_a_mano(medir, tmp_path, capsys):
    corrida = tmp_path / "latencias.json"
    corrida.write_text(json.dumps(_validas(30)), encoding="utf-8")
    salida = tmp_path / "latencia.json"
    orden = ["--corrida", str(corrida), "--salida", str(salida)]
    assert medir.main(orden) == 0
    dicho = capsys.readouterr().out
    assert "AVISO" not in dicho                            # no habia nada que perder
    assert "cronometrado a mano" not in dicho              # ni nada cronometrado
    assert medir.main(orden) == 0
    assert "AVISO" not in capsys.readouterr().out          # el anterior decia «no medido»
    assert medir.main(orden + ["--manual", "5.2,4.8,6.1,5.0,5.5"]) == 0
    assert "AVISO" not in capsys.readouterr().out
    assert medir.main(orden) == 0
    dicho = capsys.readouterr().out
    # el aviso da los valores que se pierden, listos para repetir la orden
    assert "AVISO" in dicho and '--manual "5.2,4.8,6.1,5.0,5.5"' in dicho
    assert json.loads(salida.read_text(encoding="utf-8"))["total_a_mano"] == "no medido"
    for roto in ("esto no es un JSON", "[1, 2]", '{"total_a_mano": {"n": 5}}',
                 '{"total_a_mano": {"valores_s": []}}'):
        salida.write_text(roto, encoding="utf-8")
        assert medir.main(orden) == 0                      # un fichero raro no estorba
        assert "AVISO" not in capsys.readouterr().out


def test_si_no_se_puede_escribir_el_json_el_anterior_sigue_entero(
        medir, tmp_path, monkeypatch):
    corrida = tmp_path / "latencias.json"
    corrida.write_text(json.dumps(_validas(30)), encoding="utf-8")
    salida = tmp_path / "latencia.json"
    orden = ["--corrida", str(corrida), "--salida", str(salida)]
    assert medir.main(orden) == 0
    bueno = salida.read_bytes()
    monkeypatch.setattr(medir, "resumir", lambda *a, **k: {"p50_ms": float("nan")})
    with pytest.raises(ValueError):
        medir.main(orden)
    assert salida.read_bytes() == bueno


def test_la_cli_rechaza_una_corrida_que_no_es_de_este_arnes(medir, tmp_path):
    destino = str(tmp_path / "s.json")
    with pytest.raises(SystemExit, match="no existe"):
        medir.main(["--corrida", str(tmp_path / "nada.json"), "--salida", destino])
    casos = {
        "rara.json": (json.dumps({"filas": []}), "no es una lista"),
        "vacia.json": ("", "no es un JSON"),
        "rota.json": ('[{"patientId": ', "no es un JSON"),
        "numeros.json": (json.dumps([1, 2, 3]), "la fila 1 de"),
        # la fila de una version anterior del arnes: llevaba `error`, no
        # `error_consulta`, y con ella se mediria la llamada equivocada
        "vieja.json": (json.dumps(
            [_fila()] + [{"patientId": "p", "perfil": "01-positiva_clara",
                          "con_bots": True, "fallo": None, "error": None,
                          "ms_extremo": 1000, "ms_modelo": 150.0, "ms_arnes": 60.0}]),
            "la fila 2 de"),
    }
    for nombre, (contenido, mensaje) in casos.items():
        ruta = tmp_path / nombre
        ruta.write_text(contenido, encoding="utf-8")
        with pytest.raises(SystemExit, match=mensaje):
            medir.main(["--corrida", str(ruta), "--salida", destino])
    assert not (tmp_path / "s.json").exists()
