# -*- coding: utf-8 -*-
"""La latencia de extremo a extremo (spec de SP5 §6.3), con filas fabricadas.

No hay sistema desplegado al que hablar desde una prueba: las filas son las
que `pruebas/reproducir_casos.py` deja en `latencias.json`, escritas a mano.
Lo que se ata es que filas cuentan, que cifras salen de ellas y que con
menos de 30 no se escribe nada: la latencia queda «no medida».
"""
import importlib.util
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def medir():
    """`scripts/medir_latencia.py` cargado como modulo."""
    spec = importlib.util.spec_from_file_location(
        "medir_latencia", REPO / "scripts" / "medir_latencia.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _fila(ms_extremo=1000, ms_modelo=150.0, **cambios):
    fila = {"patientId": "p", "perfil": "01-positiva_clara", "con_bots": True,
            "fallo": None, "error": None, "ms_extremo": ms_extremo,
            "ms_modelo": ms_modelo, "ms_arnes": 60.0}
    fila.update(cambios)
    return fila


def _validas(n=40):
    """n consultas validas de 1000, 1100, 1200... ms."""
    return [_fila(ms_extremo=1000 + 100 * i, ms_modelo=140.0 + i) for i in range(n)]


def test_resumir_da_p50_y_p95_de_las_consultas_validas(medir):
    r = medir.resumir(_validas(40))
    assert r["n"] == 40
    assert r["p50_ms"] == 2950.0
    assert r["p95_ms"] == 4705.0
    assert r["minimo_ms"] == 1000.0 and r["maximo_ms"] == 4900.0
    assert r["modelo_p50_ms"] == 159.5
    assert r["umbrales_s"] == {"minimo": 8, "objetivo": 3}
    assert r["frente_a_umbrales"] == {
        "p50": {"cumple_minimo": True, "cumple_objetivo": True},
        "p95": {"cumple_minimo": True, "cumple_objetivo": False}}
    assert r["descartadas"] == {"total": 0, "sin_bots": 0, "fallo": 0,
                                "error": 0, "sin_ms_extremo": 0}
    assert r["tramo_manual"] == "no medido"


def test_el_titulo_dice_que_es_una_medicion_y_el_tramo_dice_que_excluye(medir):
    r = medir.resumir(_validas(30))
    assert r["titulo"] == ("Latencia de extremo a extremo: medición con el "
                           "arnés sobre el sistema desplegado (no es una "
                           "simulación)")
    for trozo in ("`Normalizar update`", "`Desenlace`", "la subida a Telegram",
                  "la entrega del webhook", "el envío de `Responder`"):
        assert trozo in r["tramo"], trozo
    assert list(r) == ["titulo", "tramo", "n", "p50_ms", "p95_ms", "minimo_ms",
                       "maximo_ms", "modelo_p50_ms", "umbrales_s",
                       "frente_a_umbrales", "tramo_manual", "descartadas"]


def test_solo_cuentan_las_consultas_con_bots_sin_fallo_ni_error(medir):
    filas = _validas(30) + [
        _fila(con_bots=False, ms_extremo=None),
        _fila(con_bots=False, ms_extremo=None),
        _fila(fallo="no se pudo subir la placa", ms_extremo=None),
        _fila(error="fuera_de_alcance: eso", ms_extremo=90000, ms_modelo=None),
        _fila(ms_extremo=None),
        # Cada fila se descarta por UN motivo, el primero que le toca.
        _fila(con_bots=False, fallo="x", error="y", ms_extremo=None),
    ]
    r = medir.resumir(filas)
    assert r["n"] == 30
    assert r["maximo_ms"] == 3900.0, "el rechazo de 90 s no cuenta"
    assert r["descartadas"] == {"total": 6, "sin_bots": 3, "fallo": 1,
                                "error": 1, "sin_ms_extremo": 1}


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
    assert r["n"] == 30 and r["maximo_ms"] == 3900.0
    assert r["descartadas"] == {"total": 5, "sin_bots": 0, "fallo": 0,
                                "error": 0, "sin_ms_extremo": 5}
    # y un ms_modelo que no es una medida no entra en la mediana del modelo
    r = medir.resumir([_fila(ms_modelo="x")] * 15 + [_fila(ms_modelo=150.0)] * 15)
    assert r["modelo_p50_ms"] == 150.0


def test_con_menos_del_minimo_no_se_mide_y_dice_cuantas_hay(medir):
    filas = _validas(29) + [_fila(error="fuera_de_alcance: eso")]
    with pytest.raises(SystemExit) as salida:
        medir.resumir(filas)
    mensaje = str(salida.value)
    assert "29 consultas" in mensaje and "30" in mensaje
    assert "no medida" in mensaje
    with pytest.raises(SystemExit, match="0 consultas"):
        medir.resumir([])
    assert medir.resumir(filas, minimo=29)["n"] == 29


def test_el_tramo_manual_lleva_los_valores_y_su_mediana(medir):
    r = medir.resumir(_validas(30), manual=[5.2, 4.8, 6.1, 5.0, 5.5])
    assert r["tramo_manual"] == {"valores_s": [5.2, 4.8, 6.1, 5.0, 5.5],
                                 "n": 5, "mediana_s": 5.2}
    assert medir.resumir(_validas(30), manual=[])["tramo_manual"] == "no medido"


def test_leer_manual_acepta_segundos_con_punto_y_rechaza_lo_demas(medir):
    assert medir.leer_manual("5.2,4.8, 6.1,5.0,5.5") == [5.2, 4.8, 6.1, 5.0, 5.5]
    assert medir.leer_manual(None) is None
    for malo in ("5.2;4.8", "cinco", "5.2,,4.8", "5.2,-1", "5.2,0", ""):
        with pytest.raises(SystemExit, match="--manual"):
            medir.leer_manual(malo)


def test_la_cli_escribe_el_json_y_no_lo_escribe_si_no_hay_minimo(medir, tmp_path, capsys):
    corrida = tmp_path / "corpus" / "latencias.json"
    corrida.parent.mkdir()
    corrida.write_text(json.dumps(_validas(36)), encoding="utf-8")
    salida = tmp_path / "docs" / "latencia.json"
    assert medir.main(["--corrida", str(corrida), "--salida", str(salida),
                       "--manual", "5.2,4.8,6.1,5.0,5.5"]) == 0
    escrito = json.loads(salida.read_text(encoding="utf-8"))
    assert escrito == medir.resumir(_validas(36), manual=[5.2, 4.8, 6.1, 5.0, 5.5])
    assert "simulación)" in salida.read_text(encoding="utf-8"), "sin escapes \\u"
    dicho = capsys.readouterr().out
    assert "36 consultas" in dicho and "p50 2,75 s" in dicho and "p95 4,33 s" in dicho

    corta = tmp_path / "corta.json"
    corta.write_text(json.dumps(_validas(12)), encoding="utf-8")
    otra = tmp_path / "no-se-escribe.json"
    with pytest.raises(SystemExit, match="12 consultas"):
        medir.main(["--corrida", str(corta), "--salida", str(otra)])
    assert not otra.exists()


def test_la_cli_rechaza_una_corrida_que_no_existe_o_no_es_una_lista(medir, tmp_path):
    with pytest.raises(SystemExit, match="no existe"):
        medir.main(["--corrida", str(tmp_path / "nada.json"),
                    "--salida", str(tmp_path / "s.json")])
    rara = tmp_path / "rara.json"
    rara.write_text(json.dumps({"filas": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="no es una lista"):
        medir.main(["--corrida", str(rara), "--salida", str(tmp_path / "s.json")])
