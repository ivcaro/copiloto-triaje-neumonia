"""La selección de casos y las viñetas de la sesión (spec de SP5 §5.1, §5.3, §5.4, §5.8)."""
import importlib.util
import json
import pathlib
import re
import shutil

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
    assert ("\nRefiere fiebre; tos con flema; entre 3 y 7 días de evolución; sin disnea; "
            "con dolor torácico; no sabe si tiene asma.") in v
    assert "temperatura 38,2 °C; frecuencia cardíaca 104 lpm; crepitantes: sí; murmullo vesicular: normal." in v
    sin_fiebre = dict(c, signos={**c["signos"], "temperatura_c": 37.1},
                      sintomas={**c["sintomas"], "fiebre": "no", "asma": "no"})
    v = sesion.vineta(sin_fiebre)
    assert "\nNo refiere fiebre; tos con flema;" in v and "\nRefiere fiebre" not in v
    assert "no tiene asma." in v and "temperatura 37,1 °C" in v


@pytest.mark.parametrize("signos", [
    {"temperatura_c": 37.8, "frecuencia_cardiaca": 101, "crepitantes": False, "murmullo_disminuido": True},
    {"temperatura_c": 39.4, "frecuencia_cardiaca": 88, "crepitantes": True, "murmullo_disminuido": False},
])
def test_linea_explorado_es_la_que_redacta_el_nodo_desenlace(signos):
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


def _leer_clave(salida):
    return json.loads((salida / "clave.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rsna(tmp_path_factory):
    """Una raíz de RSNA falsa con un PNG por placa de las crudas congeladas."""
    raiz = tmp_path_factory.mktemp("rsna")
    (raiz / "png").mkdir()
    for pid in datos.cargar_crudas()["patientId"]:
        (raiz / "png" / f"{pid}.png").write_bytes(b"png")
    return raiz


@pytest.fixture(scope="module")
def elegida(rsna, tmp_path_factory):
    """`--fase elegir` con la semilla de la sesión, una sola vez por módulo."""
    salida = tmp_path_factory.mktemp("elegida") / "sesion"
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("RSNA_RAIZ", str(rsna))
        _preparar().fase_elegir(salida, semilla=20261006)
    return salida


@pytest.fixture
def sesion_elegida(elegida, rsna, tmp_path, monkeypatch):
    """Una copia propia de la sesión elegida, con RSNA_RAIZ puesta."""
    monkeypatch.setenv("RSNA_RAIZ", str(rsna))
    salida = tmp_path / "sesion"
    shutil.copytree(elegida, salida)
    return _preparar(), salida


def test_fase_elegir_deja_lo_que_el_arnes_y_el_formulario_necesitan(sesion_elegida):
    _, salida = sesion_elegida
    casos = json.loads((salida / "casos.json").read_text(encoding="utf-8"))
    assert len(casos) == 27
    assert all(set(c) == {"patientId", "ruta_dcm", "signos", "sintomas", "cruda"} for c in casos)
    assert casos[0]["ruta_dcm"].endswith(f"{casos[0]['patientId']}.dcm")
    d1 = _leer_datos_js(salida / "formulario" / "datos_lectura1.js")
    assert d1["lectura"] == 1 and d1["modo"] == "simple"
    assert len(d1["casos"]) == 24 and len(d1["practica"]) == 3
    assert all(e["mensaje"] is None and not e["control"] for e in d1["casos"])
    assert (salida / "formulario" / "placas" / f"{d1['casos'][0]['id']}.png").is_file()
    clave = _leer_clave(salida)
    assert clave["fase"] == "elegir" and clave["prevalencia_sesion"] == PREVALENCIA_COHORTE
    assert "simulación semisintética" in clave["rotulo"]
    # la marca de la preparación: semilla y hora de la elección, la misma en la clave y en los datos
    assert re.fullmatch(r"20261006-\d{8}T\d{6}", clave["preparacion"])
    assert d1["preparacion"] == clave["preparacion"]
    dosier = (salida / "dosier_lectura1.md").read_text(encoding="utf-8")
    assert "simulación semisintética" in dosier
    # la numeración del formulario: tres de práctica y luego los casos, con el patientId
    assert f"\n## Práctica 1 — {d1['practica'][0]['id']}\n" in dosier
    assert f"\n## Práctica 3 — {d1['practica'][2]['id']}\n" in dosier
    assert f"\n## Caso 1 — {d1['casos'][0]['id']}\n" in dosier
    assert f"\n## Caso 24 — {d1['casos'][23]['id']}\n" in dosier
    assert "## Caso 25" not in dosier and "## Práctica 4" not in dosier


def _mensajes_coherentes(clave, con_bots=False):
    return {c["patientId"]: {"texto": "CRIBADO — ...\n" + sesion.linea_explorado(c["signos"]) + "\nCOMBINADO — ...",
                             "texto_paciente": None, "error": None,
                             "resultado": {"combinacion": dict(c["bloque_previsto"])},
                             "codigo": "ABC123", "ms_extremo": 1500, "con_bots": con_bots, "fallo": None,
                             "coincide": "sí" if con_bots else None}
            for c in clave["casos"] + clave["practica"]}


def _escribir_mensajes(salida, mensajes):
    (salida / "corpus").mkdir(exist_ok=True)
    (salida / "corpus" / "mensajes.json").write_text(json.dumps(mensajes), encoding="utf-8")


IMAGEN = {"imagen_tag": "h7-sesion", "imagen_digest": "sha256:0123abcd"}


def test_fase_mensajes_construye_la_lectura_2_con_20_mensajes_y_4_controles(sesion_elegida):
    preparar, salida = sesion_elegida
    clave = _leer_clave(salida)
    _escribir_mensajes(salida, _mensajes_coherentes(clave))
    preparar.fase_mensajes(salida, **IMAGEN)
    d2 = _leer_datos_js(salida / "formulario" / "datos_lectura2.js")
    assert d2["lectura"] == 2 and d2["modo"] == "simple" and len(d2["casos"]) == 24
    assert sum(e["mensaje"] is not None for e in d2["casos"]) == 20
    assert sum(e["control"] for e in d2["casos"]) == 4
    assert all((e["mensaje"] is None) == e["control"] for e in d2["casos"])
    assert [e["id"] for e in d2["casos"]] == clave["ordenes"]["lectura2"]
    planb = _leer_datos_js(salida / "formulario" / "datos_planb.js")
    assert planb["modo"] == "secuencial" and all(e["mensaje"] for e in planb["casos"])
    d1 = _leer_datos_js(salida / "formulario" / "datos_lectura1.js")
    clave = _leer_clave(salida)
    assert clave["fase"] == "mensajes"
    assert all("categoria" in c and c["bloque"] == c["bloque_previsto"] for c in clave["casos"])
    # Ruling 14: la misma preparación en la clave y en los tres ficheros de datos
    assert d1["preparacion"] == d2["preparacion"] == planb["preparacion"] == clave["preparacion"]
    # Ruling 13: sin bots, el origen es la imagen local, con su tag y su digest
    assert clave["origen_mensajes"] == {"con_bots": False, **IMAGEN}
    assert "## Práctica 1 — " in (salida / "dosier_lectura2.md").read_text(encoding="utf-8")


def test_fase_mensajes_con_bots_no_pide_la_imagen(sesion_elegida):
    preparar, salida = sesion_elegida
    _escribir_mensajes(salida, _mensajes_coherentes(_leer_clave(salida), con_bots=True))
    preparar.fase_mensajes(salida)
    assert _leer_clave(salida)["origen_mensajes"] == {"con_bots": True, "imagen_tag": None,
                                                      "imagen_digest": None}


def test_fase_mensajes_sin_bots_exige_el_tag_y_el_digest_de_la_imagen(sesion_elegida):
    preparar, salida = sesion_elegida
    _escribir_mensajes(salida, _mensajes_coherentes(_leer_clave(salida)))
    with pytest.raises(SystemExit, match="--imagen-digest"):
        preparar.fase_mensajes(salida, imagen_tag="h7-sesion")
    assert not (salida / "formulario" / "datos_lectura2.js").exists()
    assert _leer_clave(salida)["fase"] == "elegir"


def test_fase_mensajes_rechaza_una_mezcla_de_origenes(sesion_elegida):
    """El acta cita UN origen: los 27 mensajes salen todos con bots o todos
    de la imagen local, aunque se pasen el tag y el digest."""
    preparar, salida = sesion_elegida
    clave = _leer_clave(salida)
    mensajes = _mensajes_coherentes(clave, con_bots=True)
    sin_bots = [c["patientId"] for c in clave["casos"][:2]]
    for pid in sin_bots:
        mensajes[pid].update(con_bots=False, coincide=None)
    _escribir_mensajes(salida, mensajes)
    with pytest.raises(SystemExit) as e:
        preparar.fase_mensajes(salida, **IMAGEN)
    assert "los mensajes mezclan orígenes: 25 con bots y 2 sin bots" in str(e.value)
    assert f"sin bots: {', '.join(sin_bots)}" in str(e.value)
    assert "un solo modo para los 27 casos" in str(e.value)
    assert not (salida / "formulario" / "datos_lectura2.js").exists()
    assert _leer_clave(salida)["fase"] == "elegir"


def _sin_explorado(m, c):
    m["texto"] = "EXPLORADO — 40,0 °C, 150 lpm, crepitantes sí, murmullo disminuido"


def _otra_concordancia(m, c):
    m["resultado"]["combinacion"]["concordantes"] = not c["concordante"]


def _sin_mensaje(m, c):
    m.clear()


def _con_error(m, c):
    m["error"] = "E_IMAGEN: la placa no se pudo leer"


def _con_fallo(m, c):
    m["fallo"] = "no hubo codigo: el bot no contestó"


def _otra_puntuacion(m, c):
    m["resultado"]["combinacion"]["puntuacion"] = [c["bloque_previsto"]["puntuacion"][0] + 1]


def _otra_rv_imagen(m, c):
    m["resultado"]["combinacion"]["rv_imagen"] = c["rv_imagen"] * 1.01


def _otra_prevalencia(m, c):
    m["resultado"]["combinacion"]["prevalencia"] = 0.2215


def _no_coincide(m, c):
    m.update(con_bots=True, coincide="NO: clasificaciones distintas")


@pytest.mark.parametrize("estropear, motivo", [
    (_sin_explorado, "EXPLORADO no repite la viñeta"),
    (_otra_concordancia, "concordancia"),
    (_sin_mensaje, "sin mensaje"),
    (_con_error, "E_IMAGEN"),
    (_con_fallo, "no hubo codigo"),
    (_otra_puntuacion, "puntuación"),
    (_otra_rv_imagen, "RV de imagen"),
    (_otra_prevalencia, "prevalencia 0.2215"),
    (_no_coincide, "no coinciden \\(NO: clasificaciones distintas\\)"),
])
def test_fase_mensajes_aborta_y_lista_cada_mensaje_que_no_sirve(sesion_elegida, estropear, motivo):
    preparar, salida = sesion_elegida
    clave = _leer_clave(salida)
    mensajes = _mensajes_coherentes(clave)
    c = clave["casos"][0]
    estropear(mensajes[c["patientId"]], c)
    if not mensajes[c["patientId"]]:
        del mensajes[c["patientId"]]
    _escribir_mensajes(salida, mensajes)
    with pytest.raises(SystemExit, match=f"{c['patientId']}: .*{motivo}"):
        preparar.fase_mensajes(salida, **IMAGEN)
    assert not (salida / "formulario" / "datos_lectura2.js").exists()
    assert _leer_clave(salida)["fase"] == "elegir"


def test_la_rv_de_imagen_admite_el_redondeo_del_servidor(sesion_elegida):
    preparar, salida = sesion_elegida
    clave = _leer_clave(salida)
    mensajes = _mensajes_coherentes(clave)
    for c in clave["casos"] + clave["practica"]:
        mensajes[c["patientId"]]["resultado"]["combinacion"]["rv_imagen"] = c["rv_imagen"] * (1 + 5e-4)
        mensajes[c["patientId"]]["resultado"]["combinacion"]["prevalencia"] = 0.1466   # la de docker-compose
    _escribir_mensajes(salida, mensajes)
    preparar.fase_mensajes(salida, **IMAGEN)
    assert _leer_clave(salida)["fase"] == "mensajes"


def test_elegir_otra_vez_con_forzar_borra_lo_de_la_eleccion_anterior(sesion_elegida):
    preparar, salida = sesion_elegida
    _escribir_mensajes(salida, _mensajes_coherentes(_leer_clave(salida)))
    preparar.fase_mensajes(salida, **IMAGEN)
    viejos = [salida / "formulario" / "datos_lectura2.js", salida / "formulario" / "datos_planb.js",
              salida / "dosier_lectura2.md", salida / "corpus" / "mensajes.json"]
    assert all(r.is_file() for r in viejos)
    placas_antes = {p.name for p in (salida / "formulario" / "placas").iterdir()}
    preparacion_antes = _leer_clave(salida)["preparacion"]
    preparar.fase_elegir(salida, semilla=20261007, forzar=True)
    assert not any(r.exists() for r in viejos)
    clave = _leer_clave(salida)
    assert clave["fase"] == "elegir" and clave["semilla"] == 20261007
    assert clave["preparacion"].startswith("20261007-") and clave["preparacion"] != preparacion_antes
    placas = {p.name for p in (salida / "formulario" / "placas").iterdir()}
    assert placas == {f"{c['patientId']}.png" for c in clave["casos"] + clave["practica"]}
    assert placas != placas_antes                                  # las de la otra semilla ya no están


def test_elegir_otra_vez_sin_forzar_no_pisa_la_clave_definitiva(sesion_elegida):
    preparar, salida = sesion_elegida
    _escribir_mensajes(salida, _mensajes_coherentes(_leer_clave(salida)))
    preparar.fase_mensajes(salida, **IMAGEN)
    with pytest.raises(SystemExit, match="ya tiene la fase mensajes.*--forzar"):
        preparar.fase_elegir(salida, semilla=20261007)
    assert _leer_clave(salida)["fase"] == "mensajes"
    assert (salida / "formulario" / "datos_lectura2.js").is_file()


def test_sin_rsna_raiz_el_script_lo_dice(monkeypatch):
    preparar = _preparar()
    monkeypatch.delenv("RSNA_RAIZ", raising=False)
    with pytest.raises(SystemExit, match="RSNA_RAIZ"):
        preparar.raiz_rsna()
