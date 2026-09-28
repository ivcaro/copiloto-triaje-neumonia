"""La selección de casos y las viñetas de la sesión (spec de SP5 §5.1, §5.3, §5.4, §5.8)."""
import importlib.util
import json
import pathlib
import re

import numpy as np
import pytest

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE, validar_hallazgos
from copiloto_triaje.validacion import datos, oraculo, sesion
from test_reproducir_casos import UN_RESULTADO, _redactar, _sse

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def conjunto():
    df = datos.cargar_crudas()
    _, q, rv = datos.evidencia_imagen(df["cruda"].values, datos.calibrador_desplegado())
    modelo = oraculo.ajustar(q, df["etiqueta"].values.astype(int), *sesion.RHO_SESION)
    return df, rv, modelo


@pytest.fixture(scope="module")
def eleccion(conjunto):
    df, rv, modelo = conjunto
    return sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, semilla=20261006)


def test_el_umbral_de_cribado_es_el_del_selector_de_casos():
    from pruebas.seleccionar_casos import UMBRAL
    assert sesion.UMBRAL_CRIBADO == UMBRAL


def test_la_prevalencia_de_la_sesion_es_la_desplegada():
    compose = (REPO / "servidor" / "docker-compose.yml").read_text(encoding="utf-8")
    declarada = float(re.search(r'PREVALENCIA_LOCAL:\s*"([0-9.]+)"', compose).group(1))
    assert round(PREVALENCIA_COHORTE, 4) == declarada


def test_hay_candidatos_de_sobra_en_cada_estrato(conjunto):
    df, rv, _ = conjunto
    e = sesion.estratos(df, rv)
    assert len(e["positiva_clara"]) > 300 and len(e["negativa_clara"]) > 1000
    assert len(e["banda_contradictoria"]) > 300 and len(e["asma_no_se"]) == len(df)
    assert (df["etiqueta"].values[e["positiva_clara"]] == 1).all()
    assert (rv[e["banda_contradictoria"]] < 1.0).all()


def test_elegir_llena_las_cuotas_por_estrato_y_por_concordancia(eleccion):
    casos, practica = eleccion
    assert len(casos) == 24 and len(practica) == 3
    for estrato, cuota in sesion.CUOTA.items():
        del_estrato = [c for c in casos if c["estrato"] == estrato]
        assert len(del_estrato) == 2 * cuota
        assert sum(c["concordante"] for c in del_estrato) == cuota
    ids = [c["patientId"] for c in casos + practica]
    assert len(set(ids)) == 27
    assert [p["estrato"] for p in practica] == list(sesion.PRACTICA)
    for c in casos:
        assert c["concordante"] == c["bloque_previsto"]["concordantes"]
        assert c["categoria_prevista"]["primaria"] in ("baja", "intermedia", "alta")
        validar_hallazgos({**c["signos"], "asma": c["sintomas"]["asma"]})
    assert all(c["sintomas"]["asma"] == "no_se" for c in casos if c["estrato"] == "asma_no_se")
    assert all(c["sintomas"]["asma"] != "no_se" for c in casos if c["estrato"] != "asma_no_se")


def test_la_fiebre_referida_sigue_a_la_temperatura(eleccion):
    casos, _ = eleccion
    for c in casos:
        assert c["sintomas"]["fiebre"] == ("si" if c["signos"]["temperatura_c"] > 37.8 else "no")
        assert {k: v for k, v in c["sintomas"].items() if k not in ("fiebre", "asma")} == sesion.SINTOMAS_FIJOS


def test_elegir_es_reproducible_por_semilla(conjunto):
    df, rv, modelo = conjunto
    a = sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, 1)
    b = sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, 1)
    assert a == b
    assert sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, 2) != a


def test_la_vineta_se_lee_como_un_caso_y_con_coma_decimal(eleccion):
    casos, _ = eleccion
    c = dict(casos[0])
    c.update({"edad": 57, "sexo": "M", "vista": "AP",
              "signos": {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
                         "crepitantes": True, "murmullo_disminuido": False},
              "sintomas": {**sesion.SINTOMAS_FIJOS, "fiebre": "si", "asma": "no_se"}})
    v = sesion.vineta(c)
    assert v.startswith("Paciente de 57 años, sexo masculino; radiografía de tórax en proyección AP.")
    assert "fiebre; tos con flema; entre 3 y 7 días de evolución; sin disnea; con dolor torácico; no sabe si tiene asma." in v
    assert "temperatura 38,2 °C; frecuencia cardíaca 104 lpm; crepitantes: sí; murmullo vesicular: normal." in v


def test_linea_explorado_es_la_que_redacta_el_nodo_desenlace():
    signos = {"temperatura_c": 37.8, "frecuencia_cardiaca": 101,
              "crepitantes": False, "murmullo_disminuido": True}
    d = _redactar({"statusCode": 200, "cuerpo": _sse(UN_RESULTADO)}, signos=signos)
    assert sesion.linea_explorado(signos) in d["texto"]


def test_los_ordenes_son_permutaciones_y_los_controles_salen_de_los_estratos_claros(eleccion):
    casos, _ = eleccion
    o = sesion.ordenes(casos, np.random.default_rng(3))
    ids = {c["patientId"] for c in casos}
    assert set(o["lectura1"]) == ids and set(o["lectura2"]) == ids
    assert len(o["lectura1"]) == len(o["lectura2"]) == 24
    assert len(set(o["controles"])) == 4
    por_id = {c["patientId"]: c for c in casos}
    pares = {(por_id[i]["estrato"], por_id[i]["concordante"]) for i in o["controles"]}
    assert pares == {("positiva_clara", True), ("positiva_clara", False),
                     ("negativa_clara", True), ("negativa_clara", False)}


def _preparar():
    spec = importlib.util.spec_from_file_location(
        "preparar_sesion", REPO / "scripts" / "preparar_sesion.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _leer_datos_js(ruta):
    texto = ruta.read_text(encoding="utf-8")
    assert texto.startswith("window.DATOS = ") and texto.rstrip().endswith(";")
    return json.loads(texto[len("window.DATOS = "):].rstrip().rstrip(";"))


def test_fase_elegir_deja_lo_que_el_arnes_y_el_formulario_necesitan(tmp_path, monkeypatch):
    preparar = _preparar()
    raiz = tmp_path / "rsna"
    (raiz / "png").mkdir(parents=True)
    for pid in datos.cargar_crudas()["patientId"]:
        (raiz / "png" / f"{pid}.png").write_bytes(b"png")
    monkeypatch.setenv("RSNA_RAIZ", str(raiz))
    salida = tmp_path / "sesion"
    preparar.fase_elegir(salida, semilla=20261006)
    casos = json.loads((salida / "casos.json").read_text(encoding="utf-8"))
    assert len(casos) == 27
    assert all(set(c) == {"patientId", "ruta_dcm", "signos", "sintomas", "cruda"} for c in casos)
    assert casos[0]["ruta_dcm"].endswith(f"{casos[0]['patientId']}.dcm")
    d1 = _leer_datos_js(salida / "formulario" / "datos_lectura1.js")
    assert d1["lectura"] == 1 and d1["modo"] == "simple"
    assert len(d1["casos"]) == 24 and len(d1["practica"]) == 3
    assert all(e["mensaje"] is None and not e["control"] for e in d1["casos"])
    assert (salida / "formulario" / "placas" / f"{d1['casos'][0]['id']}.png").is_file()
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    assert clave["fase"] == "elegir" and clave["prevalencia_sesion"] == PREVALENCIA_COHORTE
    assert "simulación semisintética" in clave["rotulo"]
    assert "simulación semisintética" in (salida / "dosier_lectura1.md").read_text(encoding="utf-8")


def _mensajes_coherentes(clave):
    return {c["patientId"]: {"texto": "CRIBADO — ...\n" + sesion.linea_explorado(c["signos"]) + "\nCOMBINADO — ...",
                             "texto_paciente": None, "error": None,
                             "resultado": {"combinacion": c["bloque_previsto"]},
                             "codigo": "ABC123", "ms_extremo": 1500, "con_bots": False, "fallo": None}
            for c in clave["casos"] + clave["practica"]}


def test_fase_mensajes_construye_la_lectura_2_con_20_mensajes_y_4_controles(tmp_path, monkeypatch):
    preparar = _preparar()
    raiz = tmp_path / "rsna"
    (raiz / "png").mkdir(parents=True)
    for pid in datos.cargar_crudas()["patientId"]:
        (raiz / "png" / f"{pid}.png").write_bytes(b"png")
    monkeypatch.setenv("RSNA_RAIZ", str(raiz))
    salida = tmp_path / "sesion"
    preparar.fase_elegir(salida, semilla=20261006)
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    (salida / "corpus").mkdir()
    (salida / "corpus" / "mensajes.json").write_text(
        json.dumps(_mensajes_coherentes(clave)), encoding="utf-8")
    preparar.fase_mensajes(salida)
    d2 = _leer_datos_js(salida / "formulario" / "datos_lectura2.js")
    assert d2["lectura"] == 2 and d2["modo"] == "simple" and len(d2["casos"]) == 24
    assert sum(e["mensaje"] is not None for e in d2["casos"]) == 20
    assert sum(e["control"] for e in d2["casos"]) == 4
    assert all((e["mensaje"] is None) == e["control"] for e in d2["casos"])
    assert [e["id"] for e in d2["casos"]] == clave["ordenes"]["lectura2"]
    planb = _leer_datos_js(salida / "formulario" / "datos_planb.js")
    assert planb["modo"] == "secuencial" and all(e["mensaje"] for e in planb["casos"])
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    assert clave["fase"] == "mensajes"
    assert all("categoria" in c and c["bloque"] == c["bloque_previsto"] for c in clave["casos"])


def test_fase_mensajes_aborta_si_un_mensaje_no_repite_la_vineta(tmp_path, monkeypatch):
    preparar = _preparar()
    raiz = tmp_path / "rsna"
    (raiz / "png").mkdir(parents=True)
    for pid in datos.cargar_crudas()["patientId"]:
        (raiz / "png" / f"{pid}.png").write_bytes(b"png")
    monkeypatch.setenv("RSNA_RAIZ", str(raiz))
    salida = tmp_path / "sesion"
    preparar.fase_elegir(salida, semilla=20261006)
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    mensajes = _mensajes_coherentes(clave)
    primero = clave["casos"][0]["patientId"]
    mensajes[primero]["texto"] = "EXPLORADO — 40,0 °C, 150 lpm, crepitantes sí, murmullo disminuido"
    (salida / "corpus").mkdir()
    (salida / "corpus" / "mensajes.json").write_text(json.dumps(mensajes), encoding="utf-8")
    with pytest.raises(SystemExit, match="EXPLORADO no repite"):
        preparar.fase_mensajes(salida)
    assert not (salida / "formulario" / "datos_lectura2.js").exists()


def test_sin_rsna_raiz_el_script_lo_dice(monkeypatch):
    preparar = _preparar()
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    with pytest.raises(SystemExit, match="RSNA_RAIZ"):
        preparar.raiz_rsna()
