# -*- coding: utf-8 -*-
"""La interfaz de demostración (SP5-C1, spec §3): `app/app.py`, conducida con
`streamlit.testing.v1.AppTest` como la conduciría una persona.

QUÉ VIGILA
- Arranca sin excepciones y enseña «Acerca de»: el modelo, los datos (solo con
  referencias), las métricas del JSON por subgrupo con sus intervalos, las
  limitaciones, el umbral por vista y su precio, la atribución de los ejemplos, el
  aviso de que no es un producto sanitario y los valores del entorno. Si los pesos
  cargados no son aquellos de los que salen las métricas, o el umbral no es el
  medido, lo dice.
- Cada ejemplo con «Calcular» da sus bloques (cribado, evidencia, clínica y
  combinado si hay hallazgos, el mapa de calor y «Esto no es un diagnóstico.») con
  las cifras del motor, las mismas que da `Motor` llamado aparte; sin hallazgos, solo
  la evidencia de la imagen.
- Los rechazos, en lenguaje llano y sin ningún bloque de resultado: el «rechazado»
  con el texto del bot, un fichero que no es DICOM, uno de más de 5 MB (con su
  borde), un DICOM que pydicom no puede leer (R18) y cualquier error inesperado:
  nunca una traza, y el detalle del motor solo donde el bot lo relata.
- Los hallazgos: fuera de los límites de interfaz no se pueden enviar, y a medias no
  se calcula.
- El interruptor: cambia el umbral aplicado y enseña la vista; con otra vista, el
  global; y si la etiqueta cambia, dice cuál daría el umbral global (R17).
- El historial crece con cada cálculo y el CSV tiene exactamente las columnas
  declaradas, ni la imagen, ni el nombre del fichero, ni nada de la cabecera.
- El mapa se reescala a la placa sin trasponerla; los textos copiados del bot son
  los del bot; la configuración y las versiones fijadas.

EL MOTOR DE LAS PRUEBAS (R8). La app carga SIEMPRE por `Motor.cargar`, como en
producción, y no tiene ningún camino solo de pruebas: las pruebas guardan el
`state_dict` de una EfficientNet-B0 con pesos aleatorios (semilla fija) y apuntan
`RUTA_PESOS` a él, que es la variable de entorno que la app documenta para esto; el
calibrador es el versionado. Esa red puntúa igual cualquier placa (0,4989 con la
semilla 0: el logit es el sesgo de la cabeza), y la prueba del interruptor lo usa
y lo comprueba antes. La caché de `st.cache_resource` se limpia entre pruebas.

Las pruebas con los pesos desplegados se SALTAN, diciéndolo, donde no están.

Los valores esperados están escritos aquí a mano, no sacados de la app: una
constante equivocada no puede dar por buena a la prueba que la comprueba.
"""
import csv
import importlib
import importlib.util
import io
import json
import re
import sys
import tomllib
from pathlib import Path

import numpy as np
import pydicom
import pytest
import streamlit as st
import torch
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
from streamlit.testing.v1 import AppTest

from copiloto_triaje.modelo.arquitectura import construir_modelo
from copiloto_triaje.servicio.inferencia import ErrorDeInferencia, Motor

from test_dicom import crear_dicom, crear_dicom_con_tag_vacio

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app" / "app.py"
CONFIG = REPO / "app" / ".streamlit" / "config.toml"
REQUISITOS = REPO / "app" / "requirements.txt"
PYPROJECT = REPO / "pyproject.toml"
CALIBRADOR = REPO / "servidor" / "calibrador.json"
CARPETA_EJEMPLOS = REPO / "app" / "assets" / "ejemplos"
BOT = REPO / "n8n" / "copiloto-profesional.json"
METRICAS = json.loads((REPO / "app" / "assets" / "metricas.json")
                      .read_text(encoding="utf-8"))

# AppTest corre el guion en este proceso; 3 s por defecto no bastan para cargar la red.
TIEMPO = 120

FUENTE_EJEMPLO = "Prueba con ejemplo"
FUENTE_FICHERO = "Subir un DICOM"
PESTANAS = ["Probar el modelo", "Historial de la sesión", "Acerca de"]
ADULTOS = ("normal_pa", "neumonia_pa", "neumonia_ap")

# El AUC NO es el desplegado (0,8827) a propósito: así se ve que la app enseña el del
# entorno y no uno escrito en su código. La prevalencia es la del docker-compose.yml.
AUC = "0.8765"
PREVALENCIA = "0.1466"

# Los tres umbrales del workshop S4 (y de metricas.json): el global y los de vista.
UMBRAL_GLOBAL = 0.4258
UMBRAL_PA = 0.1798
UMBRAL_AP = 0.5815

HALLAZGOS = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104, "crepitantes": True,
             "murmullo_disminuido": False, "asma": "no_se"}

# Las columnas del CSV del historial (R10), en su orden.
COLUMNAS = ("n", "origen", "umbral_por_vista", "vista_del_umbral", "clasificacion",
            "probabilidad_cruda", "umbral", "probabilidad_calibrada",
            "razon_de_verosimilitud", "temperatura_c", "frecuencia_cardiaca",
            "crepitantes", "murmullo_disminuido", "asma", "puntuacion_heckerling",
            "rv_clinica", "prevalencia", "combinado_minima", "combinado_maxima")

# Los textos del bot que se buscan en la pantalla.
DESCARGO = "Esto no es un diagnóstico."
NO_PUDE_LEER = "No pude leer esa radiografía."
SIN_CODIGO = ("No pude interpretar el contenido del fichero. Si lo recortó al "
              "enviarlo, vuelva a exportarlo completo.")
FUERA_DE_ALCANCE = "NO PROCEDE — fuera del alcance del modelo."
EDAD_DESCONOCIDA = "NO PROCEDE — no se puede saber la edad."
COLETILLA_EDAD = ("No hay resultado que dar: el modelo se validó entre 18 y 100 años, "
                  "y aplicarlo fuera de ahí no significaría nada. Decida clínicamente.")
POSITIVO_SIN_APOYO = ("⚠️ El cribado marca esta placa por estar orientado a detectar, "
                      "pero la imagen en sí no apoya el diagnóstico. Decide la clínica.")
SIN_COMBINAR = ("SIN COMBINAR — faltan signos de la exploración, así que no hay "
                "puntuación de Heckerling.")
AVISO_NEGATIVO = ("⚠️ El modelo mide opacidad en la placa, no neumonía. Un resultado "
                  "negativo no la descarta. Decide usted.")
OPUESTOS = ("⚠️ La clínica y la imagen apuntan en sentidos opuestos, y además no son "
            "pruebas independientes: la horquilla es orientativa. Decide usted.")

# Lo que nunca puede llegar a la pantalla: rastros de una traza o de una excepción.
RASTROS_DE_TRAZA = ("Traceback", "Error:", "File \"", "AttributeError", "TypeError",
                    "RuntimeError", "InvalidDicomError")
ROTULOS_DE_RESULTADO = ("CRIBADO", "EVIDENCIA DE LA IMAGEN", "CLÍNICA —", "COMBINADO",
                        DESCARGO)


# --------------------------------------------------------------------------
# Fijadores y ayudas
# --------------------------------------------------------------------------
@pytest.fixture(scope="session")
def pesos_aleatorios(tmp_path_factory):
    """El `state_dict` de una EfficientNet-B0 sin entrenar, semilla 0 (R8). La semilla
    se fija sin tocar el estado global de torch."""
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0)
        modelo = construir_modelo("efficientnet_b0", congelar_backbone=False,
                                  preentrenado=False)
    ruta = tmp_path_factory.mktemp("pesos") / "efficientnet_b0_aleatoria.pt"
    torch.save(modelo.state_dict(), ruta)
    return ruta


@pytest.fixture(autouse=True)
def entorno(monkeypatch, pesos_aleatorios):
    """El entorno de un despliegue, con la red aleatoria; sin `UMBRAL`, que tiene
    valor por defecto. La caché del motor, limpia antes y después."""
    monkeypatch.setenv("RUTA_PESOS", str(pesos_aleatorios))
    monkeypatch.setenv("RUTA_CALIBRADOR", str(CALIBRADOR))
    monkeypatch.setenv("AUC_VALIDACION", AUC)
    monkeypatch.setenv("PREVALENCIA_LOCAL", PREVALENCIA)
    monkeypatch.delenv("UMBRAL", raising=False)
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


@pytest.fixture
def descargas(monkeypatch):
    """Los ficheros que la app entrega al navegador (imágenes, el CSV), tal cual: se
    espía el almacén en memoria de AppTest, que es por donde pasan los datos de
    `st.download_button`. Lista de (tipo MIME, nombre, bytes)."""
    capturadas = []
    original = MemoryMediaFileStorage.load_and_get_id

    def espia(self, path_or_data, mimetype, kind, filename=None):
        capturadas.append((mimetype, filename, path_or_data))
        return original(self, path_or_data, mimetype, kind, filename)

    monkeypatch.setattr(MemoryMediaFileStorage, "load_and_get_id", espia)
    return capturadas


@pytest.fixture(scope="session")
def modulo_app():
    """`app/app.py` importado como módulo, sin pintar nada: la pantalla solo se pinta
    cuando Streamlit lo ejecuta como `__main__`."""
    especificacion = importlib.util.spec_from_file_location("app_de_demostracion", APP)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


def _motor(pesos, umbrales_por_vista=None):
    """Un `Motor` cargado aparte con lo mismo que la app, para comparar cifras."""
    return Motor.cargar(pesos, CALIBRADOR, UMBRAL_GLOBAL, float(AUC),
                        float(PREVALENCIA), umbrales_por_vista=umbrales_por_vista)


def _app():
    return AppTest.from_file(str(APP), default_timeout=TIEMPO).run()


def _textos(bloque) -> str:
    """Todo lo que dice la página (o un bloque suyo), junto, para buscar en ello."""
    trozos = []
    for tipo in ("title", "header", "subheader", "markdown", "caption", "text", "code",
                 "error", "warning", "info", "success"):
        trozos.extend(str(el.value) for el in bloque.get(tipo))
    for el in bloque.get("exception"):
        trozos.append(el.proto.message)
        trozos.extend(el.proto.stack_trace)
    return "\n".join(trozos)


def _dec(x, n):
    return f"{x:.{n}f}".replace(".", ",")


def _elegir_ejemplo(at, ejemplo):
    at.segmented_control(key="fuente").set_value(FUENTE_EJEMPLO).run()
    at.selectbox(key="ejemplo").set_value(ejemplo)
    return at.run()


def _subir(at, nombre, datos):
    at.segmented_control(key="fuente").set_value(FUENTE_FICHERO).run()
    at.file_uploader(key="dicom").upload(nombre, datos, "application/dicom")
    return at.run()


def _poner_hallazgos(at, hallazgos):
    si_no = {True: "si", False: "no"}
    at.toggle(key="con_hallazgos").set_value(True).run()
    at.number_input(key="temperatura").set_value(hallazgos["temperatura_c"])
    at.number_input(key="frecuencia").set_value(hallazgos["frecuencia_cardiaca"])
    at.radio(key="crepitantes").set_value(si_no[hallazgos["crepitantes"]])
    at.radio(key="murmullo").set_value(si_no[hallazgos["murmullo_disminuido"]])
    at.radio(key="asma").set_value(hallazgos["asma"])
    return at.run()


def _calcular(at):
    return at.button(key="calcular").click().run()


def _sin_traza(at):
    assert not at.exception, [e.proto.message for e in at.exception]
    texto = _textos(at)
    for rastro in RASTROS_DE_TRAZA:
        assert rastro not in texto, rastro


def _sin_resultado(at):
    texto = _textos(at)
    for rotulo in ROTULOS_DE_RESULTADO:
        assert rotulo not in texto, rotulo
    assert not at.get("image"), "una imagen sin resultado"
    assert not at.get("vega_lite_chart"), "un gráfico sin resultado"
    assert at.session_state["historial"] == []


def _ejemplo(nombre):
    return (CARPETA_EJEMPLOS / f"{nombre}.dcm").read_bytes()


def _dicom(tmp_path, nombre="placa.dcm", **campos):
    ruta = tmp_path / nombre
    crear_dicom(ruta, **campos)
    return ruta


# --------------------------------------------------------------------------
# Arranque y «Acerca de»
# --------------------------------------------------------------------------
def test_arranca_sin_excepciones_y_ensena_acerca_de():
    at = _app()
    _sin_traza(at)
    assert [t.label for t in at.tabs] == PESTANAS
    acerca = at.tabs[2]
    texto = _textos(acerca)
    minusculas = texto.lower()
    for frase in ("efficientnet-b0", "calibración", "razón de verosimilitud",
                  "heckerling", "grad-cam", "rsna", "opacidad no es neumonía",
                  "estados unidos", "semisintética", "no es un producto sanitario"):
        assert frase in minusculas, frase
    # Los datos, solo con referencias y enlaces.
    assert "kaggle.com/competitions/rsna-pneumonia-detection-challenge" in texto
    assert "doi.org/10.1148/ryai.2019180041" in texto
    # Los valores del despliegue, del entorno y del motor.
    assert _dec(float(AUC), 4) in texto
    assert _dec(UMBRAL_GLOBAL, 4) in texto
    assert _dec(float(PREVALENCIA) * 100, 2) + " %" in texto
    # Las métricas, del JSON: las globales con sus intervalos, y los trece subgrupos.
    g = METRICAS["global"]
    for cifra in (g["auc"], ):
        assert _dec(cifra, 3) in texto
    for cifra in (g["recall"], *g["recall_ic"], g["especificidad"], *g["especificidad_ic"]):
        assert _dec(cifra, 2) in texto
    tablas = [t.value for t in acerca.table]
    subgrupos = next(t for t in tablas if "Subgrupo" in t.columns)
    assert list(subgrupos["Subgrupo"]) == [s["nombre"] for s in METRICAS["subgrupos"]]
    for fila, s in zip(subgrupos.to_dict("records"), METRICAS["subgrupos"]):
        assert fila["AUC"] == _dec(s["auc"], 3)
        assert fila["Sensibilidad (IC 95 %)"] == (
            f"{_dec(s['recall'], 2)} ({_dec(s['recall_ic'][0], 2)}–"
            f"{_dec(s['recall_ic'][1], 2)})")
    # El umbral por vista y su precio: los dos umbrales y la tabla de prueba.
    assert _dec(UMBRAL_PA, 4) in texto and _dec(UMBRAL_AP, 4) in texto
    precio = next(t for t in tablas if "Placas" in t.columns)
    assert "Placas" not in subgrupos.columns
    assert list(precio["Placas"]) == ["PA", "AP", "Todas"]
    dos = METRICAS["umbral_por_vista_en_prueba"]["dos_umbrales"]
    assert list(precio["Especificidad, dos umbrales"])[2].startswith(
        _dec(dos["global"]["especificidad"], 2))
    # La atribución de los ejemplos, con su licencia.
    assert any("CC0" in _textos(e) for e in acerca.expander)
    # Honestidad: estas métricas son de otros pesos que los cargados (aquí, la red
    # aleatoria), y la app lo dice.
    assert any("otros pesos" in w.value for w in acerca.warning)


def test_avisa_de_que_los_ejemplos_no_se_han_medido():
    """R15: los ejemplos se nombran por lo que dice su fuente, y la app avisa de que
    el modelo no se ha medido con ellos."""
    at = _app()
    texto = _textos(at.tabs[0])
    assert "no se ha medido" in texto
    opciones = at.selectbox(key="ejemplo").options
    assert opciones[:3] == ["Normal, PA — según su fuente",
                            "Neumonía, PA — según su fuente",
                            "Neumonía, AP — según su fuente"]
    assert len(opciones) == 4


@pytest.mark.parametrize("variable", ["AUC_VALIDACION", "PREVALENCIA_LOCAL"])
def test_sin_una_variable_obligatoria_no_calcula_y_dice_cual(monkeypatch, variable):
    """La misma disciplina que el servidor: sin valor por defecto, y diciendo qué
    declarar. Una variable vacía cuenta como no declarada."""
    monkeypatch.setenv(variable, "")
    at = _app()
    _sin_traza(at)
    assert any(variable in e.value for e in at.error)
    assert not at.button, "con la configuración rota no hay nada que calcular"


@pytest.mark.parametrize("variable, valor", [("UMBRAL", "abc"), ("UMBRAL", "1.5"),
                                             ("PREVALENCIA_LOCAL", "0"),
                                             ("AUC_VALIDACION", "nan")])
def test_un_valor_imposible_en_el_entorno_se_dice_sin_traza(monkeypatch, variable, valor):
    monkeypatch.setenv(variable, valor)
    at = _app()
    _sin_traza(at)
    assert any(variable in e.value and repr(valor) in e.value for e in at.error)
    assert not at.button


def test_sin_los_pesos_lo_dice_sin_traza(monkeypatch, tmp_path):
    monkeypatch.setenv("RUTA_PESOS", str(tmp_path / "no_estan.pt"))
    at = _app()
    _sin_traza(at)
    assert any("RUTA_PESOS" in e.value for e in at.error)
    assert not at.button


# --------------------------------------------------------------------------
# Los ejemplos y sus bloques
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ejemplo", ADULTOS)
def test_cada_ejemplo_con_hallazgos_da_sus_bloques_con_las_cifras_del_motor(
        ejemplo, pesos_aleatorios):
    at = _app()
    _elegir_ejemplo(at, ejemplo)
    _poner_hallazgos(at, HALLAZGOS)
    _calcular(at)
    _sin_traza(at)

    esperado = _motor(pesos_aleatorios).clasificar(_ejemplo(ejemplo), HALLAZGOS)
    obtenido = at.session_state["ultimo"]["resultado"]
    sin_reloj = lambda r: {k: v for k, v in r.items() if k != "milisegundos"}
    assert sin_reloj(obtenido) == sin_reloj(esperado)

    texto = _textos(at.tabs[0])
    for rotulo in ("CRIBADO —", "EVIDENCIA DE LA IMAGEN —", "CLÍNICA —", "COMBINADO —",
                   DESCARGO):
        assert rotulo in texto, rotulo
    # Las cifras que se enseñan son las del motor, con el formato del bot.
    assert (f"puntuación {_dec(esperado['probabilidad_cruda'], 4)} ≥ umbral "
            f"{_dec(UMBRAL_GLOBAL, 4)}") in texto
    assert f"(probabilidad calibrada {_dec(esperado['probabilidad_calibrada'], 2)})" in texto
    c = esperado["combinacion"]
    assert f"Heckerling {c['puntuacion'][0]} o {c['puntuacion'][1]} de 5" in texto
    assert f"prevalencia {_dec(c['prevalencia'] * 100, 1)} %" in texto
    # Los avisos, letra a letra los del bot (con su ⚠️). La red aleatoria da siempre
    # un positivo con la RV por debajo de 1, contra una clínica por encima de 1.
    assert esperado["clasificacion"] == "opacidad_probable"
    assert esperado["razon_de_verosimilitud"] < 1 and not c["concordantes"]
    assert POSITIVO_SIN_APOYO in texto
    assert OPUESTOS in texto
    # La placa con el mapa encima, y dos gráficos: el del cribado y el combinado.
    assert at.get("image")
    assert len(at.get("vega_lite_chart")) == 2
    assert len(at.session_state["historial"]) == 1


def test_sin_hallazgos_da_solo_la_evidencia_de_la_imagen():
    at = _calcular(_app())                  # el primer ejemplo, tal como arranca
    _sin_traza(at)
    texto = _textos(at.tabs[0])
    for rotulo in ("CRIBADO —", "EVIDENCIA DE LA IMAGEN —", SIN_COMBINAR, DESCARGO):
        assert rotulo in texto, rotulo
    assert "CLÍNICA —" not in texto and "COMBINADO —" not in texto
    assert "combinacion" not in at.session_state["ultimo"]["resultado"]
    assert len(at.get("vega_lite_chart")) == 1


def test_un_resultado_no_se_queda_delante_de_otra_entrada():
    """Si la entrada cambia, el resultado de la anterior deja de enseñarse."""
    at = _calcular(_app())
    assert "CRIBADO —" in _textos(at)
    _elegir_ejemplo(at, "neumonia_pa")
    assert "CRIBADO —" not in _textos(at)
    assert "Calcular" in _textos(at)


# --------------------------------------------------------------------------
# Los rechazos: lenguaje llano y ningún resultado
# --------------------------------------------------------------------------
def test_el_rechazado_da_el_mensaje_del_bot_y_ningun_resultado():
    at = _elegir_ejemplo(_app(), "rechazado_menor")
    _calcular(at)
    _sin_traza(at)
    errores = [e.value for e in at.tabs[0].error]
    assert len(errores) == 1
    assert errores[0] == "\n\n".join([
        FUERA_DE_ALCANCE,
        "El paciente tiene 15 años y el modelo solo es válido entre 18 y 100.",
        COLETILLA_EDAD])
    _sin_resultado(at)


def test_un_fichero_que_no_es_dicom_da_dicom_invalido_sin_el_detalle_de_pydicom():
    at = _subir(_app(), "nota.txt", b"esto no es un DICOM")
    _calcular(at)
    _sin_traza(at)
    errores = [e.value for e in at.tabs[0].error]
    assert len(errores) == 1 and errores[0].startswith(NO_PUDE_LEER)
    # El detalle de pydicom (que habla del prefijo «DICM») es de un tercero: el bot no
    # lo relata, y la app tampoco.
    assert "DICM" not in _textos(at)
    _sin_resultado(at)


def test_una_edad_ilegible_da_el_mensaje_del_bot(tmp_path):
    at = _subir(_app(), "placa.dcm", _dicom(tmp_path, edad="").read_bytes())
    _calcular(at)
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    assert error.startswith(EDAD_DESCONOCIDA) and error.endswith(COLETILLA_EDAD)
    _sin_resultado(at)


def _sin_pixeles(tmp_path):
    ruta = _dicom(tmp_path, edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    del ds.PixelData
    ds.save_as(str(ruta), enforce_file_format=True)
    return ruta.read_bytes()


def _rows_vacio(tmp_path):
    ruta = tmp_path / "rows_vacio.dcm"
    crear_dicom_con_tag_vacio(ruta)
    return ruta.read_bytes()


@pytest.mark.parametrize("hacer", [_sin_pixeles, _rows_vacio],
                         ids=["sin_pixel_data", "rows_vacio"])
def test_un_dicom_que_pydicom_no_puede_leer_no_da_una_traza(tmp_path, hacer):
    """R18: pydicom lanza un `AttributeError` que el motor no traduce. La app lo
    captura y da el mensaje del bot para lo que no se pudo interpretar."""
    at = _subir(_app(), "placa.dcm", hacer(tmp_path))
    _calcular(at)
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    assert error.startswith(NO_PUDE_LEER) and SIN_CODIGO in error
    for detalle in ("Pixel Data", "Rows", "Missing required element"):
        assert detalle not in _textos(at)
    _sin_resultado(at)


def test_si_streamlit_vuelve_a_importar_el_motor_un_rechazo_sigue_siendo_un_rechazo(
        monkeypatch):
    """Cuando cambia un fichero vigilado, Streamlit saca de `sys.modules` TODOS los
    módulos que vigila -los de la carpeta de la app y los de PYTHONPATH- y los vuelve
    a importar. Si la caché siguiera dando el `Motor` del código viejo, lanzaría el
    `ErrorDeInferencia` viejo, el `except` del nuevo no lo atraparía y el rechazado
    saldría como un fallo inesperado. Pasó al mirar la app con un fichero editado."""
    at = _calcular(_app())                  # el motor, ya en la caché
    import copiloto_triaje.servicio as servicio
    nombre = "copiloto_triaje.servicio.inferencia"
    monkeypatch.setattr(servicio, "inferencia", sys.modules[nombre])  # se repone al final
    monkeypatch.delitem(sys.modules, nombre)
    reimportado = importlib.import_module(nombre)
    assert reimportado.ErrorDeInferencia is not ErrorDeInferencia

    _calcular(_elegir_ejemplo(at, "rechazado_menor"))
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    assert error.startswith(FUERA_DE_ALCANCE)


def test_un_error_inesperado_del_motor_no_llega_como_traza(monkeypatch):
    def revienta(self, datos, hallazgos=None):
        raise RuntimeError("detalle interno que no se enseña")

    monkeypatch.setattr(Motor, "clasificar", revienta)
    at = _calcular(_app())
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    assert error.startswith(NO_PUDE_LEER)
    assert "detalle interno" not in _textos(at)
    _sin_resultado(at)


@pytest.mark.parametrize("codigo, empieza, relata", [
    ("dicom_invalido", NO_PUDE_LEER, False),
    ("edad_desconocida", EDAD_DESCONOCIDA, True),
    ("fuera_de_alcance", FUERA_DE_ALCANCE, True),
    ("hallazgos_invalidos", "Los hallazgos de la exploración no son válidos.", False),
])
def test_cada_rechazo_del_motor_se_dice_en_lenguaje_llano(monkeypatch, codigo, empieza,
                                                        relata):
    """El detalle del motor se relata SOLO donde lo relata el bot: en los dos rechazos
    por edad, cuyo texto compone nuestro código. El de `dicom_invalido` lleva el texto
    de pydicom sobre bytes ajenos, y el de `hallazgos_invalidos`, nombres de campo."""
    def rechaza(self, datos, hallazgos=None):
        raise ErrorDeInferencia(codigo, "DETALLE-DEL-MOTOR")

    monkeypatch.setattr(Motor, "clasificar", rechaza)
    at = _calcular(_app())
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    assert error.startswith(empieza)
    assert ("DETALLE-DEL-MOTOR" in error) is relata
    assert error.endswith(COLETILLA_EDAD) is relata
    _sin_resultado(at)


@pytest.mark.parametrize("de_mas", [0, 1], ids=["5_MB_justos", "un_byte_de_mas"])
def test_un_fichero_de_mas_de_5_mb_se_rechaza_antes_de_leerlo(de_mas):
    """R14: la app comprueba ella misma el tamaño (el `config.toml` de `app/` no se
    aplica si se lanza desde la raíz). 5 MB justos pasan, y llegan al motor (que no
    puede leer ceros); uno más, no."""
    at = _subir(_app(), "grande.dcm", b"\0" * (5 * 1024 * 1024 + de_mas))
    assert at.file_uploader(key="dicom").proto.max_upload_size_mb == 5
    _calcular(at)
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    if de_mas:
        assert error.startswith("El archivo supera los 5 MB.")
    else:
        assert error.startswith(NO_PUDE_LEER)
    _sin_resultado(at)


def test_sin_fichero_no_calcula():
    at = _app()
    at.segmented_control(key="fuente").set_value(FUENTE_FICHERO).run()
    _calcular(at)
    _sin_traza(at)
    assert any("Suba un fichero DICOM" in w.value for w in at.tabs[0].warning)
    _sin_resultado(at)


# --------------------------------------------------------------------------
# Los hallazgos
# --------------------------------------------------------------------------
def test_hallazgos_fuera_de_los_limites_de_interfaz_no_se_pueden_enviar():
    at = _app()
    at.toggle(key="con_hallazgos").set_value(True).run()
    temperatura = at.number_input(key="temperatura")
    frecuencia = at.number_input(key="frecuencia")
    assert (temperatura.min, temperatura.max) == (30, 45)
    assert (frecuencia.min, frecuencia.max) == (20, 250)
    # Ni vacíos por defecto rellenos con un valor inventado.
    assert temperatura.value is None and frecuencia.value is None
    temperatura.set_value(50.0)
    frecuencia.set_value(300)
    at.radio(key="crepitantes").set_value("si")
    at.radio(key="murmullo").set_value("no")
    at.radio(key="asma").set_value("no")
    at.run()
    # Streamlit no deja pasar un valor fuera de los límites del campo...
    assert at.number_input(key="temperatura").value is None
    assert at.number_input(key="frecuencia").value is None
    # ...y sin él no se calcula.
    _calcular(at)
    _sin_traza(at)
    (aviso,) = [w.value for w in at.tabs[0].warning]
    assert "la temperatura (de 30 a 45 °C)" in aviso
    assert "la frecuencia cardíaca (de 20 a 250 lpm)" in aviso
    _sin_resultado(at)


def test_unos_hallazgos_a_medias_no_se_calculan():
    at = _app()
    at.toggle(key="con_hallazgos").set_value(True).run()
    at.number_input(key="temperatura").set_value(38.2)
    at.number_input(key="frecuencia").set_value(104)
    at.radio(key="crepitantes").set_value("si")
    at.radio(key="murmullo").set_value("no")
    _calcular(at)
    (aviso,) = [w.value for w in at.tabs[0].warning]
    assert "el asma" in aviso and "temperatura" not in aviso
    _sin_resultado(at)


# --------------------------------------------------------------------------
# El interruptor del umbral por vista
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ejemplo, vista, umbral", [("normal_pa", "PA", UMBRAL_PA),
                                                    ("neumonia_ap", "AP", UMBRAL_AP)])
def test_el_interruptor_cambia_el_umbral_aplicado_y_ensena_la_vista(ejemplo, vista,
                                                                    umbral):
    at = _calcular(_elegir_ejemplo(_app(), ejemplo))
    r = at.session_state["ultimo"]["resultado"]
    assert r["umbral"] == UMBRAL_GLOBAL and "umbral_por_vista" not in r
    assert f"umbral {_dec(UMBRAL_GLOBAL, 4)}" in _textos(at.tabs[0])
    assert "se aplicó el umbral" not in _textos(at.tabs[0])

    at.toggle(key="por_vista").set_value(True)
    _calcular(at)
    _sin_traza(at)
    r = at.session_state["ultimo"]["resultado"]
    assert r["umbral"] == umbral
    assert r["umbral_por_vista"] == {"vista": vista, "aplicado": True}
    texto = _textos(at.tabs[0])
    assert f"umbral {_dec(umbral, 4)}" in texto
    assert f"la cabecera dice {vista}, y se aplicó el umbral de {vista}" in texto
    # Solo cambia la etiqueta: la evidencia y su texto son los mismos.
    assert "EVIDENCIA DE LA IMAGEN —" in texto


def test_con_una_vista_que_no_es_pa_ni_ap_se_aplica_el_global(tmp_path):
    at = _subir(_app(), "lateral.dcm", _dicom(tmp_path, edad="054Y", vista="LL")
                .read_bytes())
    at.toggle(key="por_vista").set_value(True)
    _calcular(at)
    _sin_traza(at)
    r = at.session_state["ultimo"]["resultado"]
    assert r["umbral"] == UMBRAL_GLOBAL
    assert r["umbral_por_vista"] == {"vista": None, "aplicado": False}
    assert "la cabecera no declara PA ni AP, y se aplicó el umbral global" in _textos(at)


def test_si_el_interruptor_cambia_la_etiqueta_dice_cual_daria_el_global(
        pesos_aleatorios):
    """R17. La red aleatoria puntúa igual cualquier placa; entre el umbral global y
    el de AP, una placa AP cambia de etiqueta al encender el interruptor, y una PA
    no. Se comprueba antes, con un `Motor` aparte, que la puntuación cae ahí."""
    motores = (_motor(pesos_aleatorios),
               _motor(pesos_aleatorios, {"PA": UMBRAL_PA, "AP": UMBRAL_AP}))
    por_motor = [m.clasificar(_ejemplo("neumonia_ap")) for m in motores]
    assert UMBRAL_GLOBAL <= por_motor[0]["probabilidad_cruda"] < UMBRAL_AP
    assert [r["clasificacion"] for r in por_motor] == ["opacidad_probable",
                                                      "sin_opacidad_probable"]

    at = _elegir_ejemplo(_app(), "neumonia_ap")
    at.toggle(key="por_vista").set_value(True)
    _calcular(at)
    _sin_traza(at)
    ultimo = at.session_state["ultimo"]
    assert ultimo["resultado"]["clasificacion"] == "sin_opacidad_probable"
    assert ultimo["resultado_global"]["clasificacion"] == "opacidad_probable"
    texto = _textos(at.tabs[0])
    assert "CRIBADO — sin opacidad probable" in texto
    assert (f"Con el umbral global ({_dec(UMBRAL_GLOBAL, 4)}) sería «opacidad "
            "probable».") in texto

    _elegir_ejemplo(at, "normal_pa")        # PA: la misma etiqueta con los dos
    _calcular(at)
    assert at.session_state["ultimo"]["resultado"]["umbral"] == UMBRAL_PA
    assert "sería «" not in _textos(at.tabs[0])


def test_un_umbral_del_entorno_se_aplica_y_no_se_le_atribuyen_las_metricas(
        monkeypatch):
    """Con un UMBRAL que no es el medido, sensibilidad y especificidad son de otro
    punto de la curva: el bot no las afirma, y la app tampoco."""
    monkeypatch.setenv("UMBRAL", "0.5")
    at = _calcular(_app())
    _sin_traza(at)
    r = at.session_state["ultimo"]["resultado"]
    assert r["umbral"] == 0.5
    texto = _textos(at.tabs[0])
    assert "umbral 0,5000" in texto and "sens." not in texto
    # Con 0,5 la red aleatoria (0,4989) da un negativo, y va el aviso de los negativos.
    assert r["clasificacion"] == "sin_opacidad_probable"
    assert "CRIBADO — sin opacidad probable" in texto and AVISO_NEGATIVO in texto
    assert any("0,5000" in w.value and _dec(UMBRAL_GLOBAL, 4) in w.value
               for w in at.tabs[2].warning)


# --------------------------------------------------------------------------
# Los fallos del mapa de calor no tumban el resultado
# --------------------------------------------------------------------------
def test_un_mapa_que_falla_deja_el_resultado_y_lo_dice(monkeypatch):
    def revienta(self, datos):
        raise RuntimeError("el mapa revienta")

    monkeypatch.setattr(Motor, "mapa_de_calor", revienta)
    at = _calcular(_app())
    _sin_traza(at)
    texto = _textos(at.tabs[0])
    assert "CRIBADO —" in texto and DESCARGO in texto
    assert "No se pudo calcular el mapa de calor" in texto
    assert len(at.session_state["historial"]) == 1


def test_un_mapa_de_ceros_se_dice(monkeypatch):
    monkeypatch.setattr(Motor, "mapa_de_calor",
                        lambda self, datos: np.zeros((self.tam_imagen,) * 2, np.float32))
    at = _calcular(_app())
    _sin_traza(at)
    assert "El mapa vale cero en toda la placa" in _textos(at.tabs[0])


def test_el_mapa_se_reescala_a_la_placa_sin_trasponerla(modulo_app):
    """R12: el mapa es de la imagen aplastada a 320 x 320 (`Resize((tam, tam))`, sin
    recorte), así que vuelve a la placa con un `resize` simple. Una placa no
    cuadrada y un mapa caliente solo arriba a la izquierda: trasponer o voltear se
    nota."""
    placa = np.full((100, 60), 128, np.uint8)                   # alto 100, ancho 60
    mapa = np.zeros((320, 320), np.float32)
    mapa[:80, :80] = 1.0
    encima = modulo_app.superponer(placa, mapa, 0.5)
    assert encima.shape == (100, 60, 3) and encima.dtype == np.uint8
    gris = np.full(3, 128, np.uint8)
    assert not np.array_equal(encima[5, 5], gris)               # arriba a la izquierda
    assert np.array_equal(encima[95, 55], gris)                 # abajo a la derecha
    assert np.array_equal(encima[5, 55], gris)                  # arriba a la derecha
    assert np.array_equal(encima[95, 5], gris)                  # abajo a la izquierda
    # Sin opacidad, la placa tal cual.
    assert np.array_equal(modulo_app.superponer(placa, mapa, 0.0),
                          np.repeat(placa[..., None], 3, axis=2))


# --------------------------------------------------------------------------
# El historial y su CSV
# --------------------------------------------------------------------------
def test_el_historial_crece_y_su_csv_no_lleva_ni_imagen_ni_identificadores(
        tmp_path, descargas, modulo_app):
    # Un DICOM con todo lo que identifica a alguien: en la cabecera y en el nombre.
    ruta = _dicom(tmp_path, nombre="zoila_garcia_zqx.dcm",
                  patient_id="IDENTIFICADOR-ZQX", edad="067Y")
    ds = pydicom.dcmread(str(ruta))
    ds.PatientName = "Garcia^Zoila"
    ds.save_as(str(ruta), enforce_file_format=True)

    at = _subir(_app(), ruta.name, ruta.read_bytes())
    _calcular(at)
    assert len(at.session_state["historial"]) == 1
    _elegir_ejemplo(at, "neumonia_pa")
    _calcular(at)
    assert len(at.session_state["historial"]) == 2
    _poner_hallazgos(at, HALLAZGOS)
    at.toggle(key="por_vista").set_value(True)
    _calcular(at)
    assert len(at.session_state["historial"]) == 3
    # Un rechazo no es una predicción: no entra.
    _elegir_ejemplo(at, "rechazado_menor")
    _calcular(at)
    assert len(at.session_state["historial"]) == 3
    _sin_traza(at)

    assert modulo_app.COLUMNAS_HISTORIAL == COLUMNAS
    csvs = [datos for tipo, _, datos in descargas if tipo == "text/csv"]
    assert csvs, "no hay CSV que descargar"
    crudo = csvs[-1]
    contenido = crudo.decode("utf-8")
    filas = list(csv.reader(io.StringIO(contenido)))
    assert tuple(filas[0]) == COLUMNAS
    datos = [dict(zip(COLUMNAS, f)) for f in filas[1:]]
    assert [d["n"] for d in datos] == ["1", "2", "3"]
    assert [d["origen"] for d in datos] == ["fichero subido", "ejemplo: neumonia_pa",
                                            "ejemplo: neumonia_pa"]
    assert [d["umbral_por_vista"] for d in datos] == ["apagado", "apagado", "encendido"]
    assert [d["vista_del_umbral"] for d in datos] == ["", "", "PA"]
    assert [d["asma"] for d in datos] == ["", "", "no_se"]
    assert datos[2]["puntuacion_heckerling"] == "3/4"
    assert float(datos[2]["umbral"]) == UMBRAL_PA
    # Ni el nombre del fichero ni nada de la cabecera.
    for prohibido in ("zoila", "garcia", "zqx", "identificador"):
        assert prohibido not in contenido.lower(), prohibido
    # Ni imagen: ninguna firma de PNG o JPEG, nada en base64, ninguna celda larga.
    assert b"\x89PNG" not in crudo and b"\xff\xd8\xff" not in crudo
    assert "data:image" not in contenido
    assert not re.search(r"[A-Za-z0-9+/=]{100,}", contenido)
    assert max(len(celda) for fila in filas for celda in fila) < 40
    # La tabla de la pantalla enseña lo mismo.
    (tabla,) = [d.value for d in at.tabs[1].dataframe]
    assert tuple(tabla.columns) == COLUMNAS and len(tabla) == 3
    assert "zoila" not in tabla.to_csv().lower()


def test_sin_calculos_no_hay_csv(descargas):
    at = _app()
    assert not [d for tipo, _, d in descargas if tipo == "text/csv"]
    assert not at.tabs[1].get("download_button")
    assert "Aún no hay cálculos" in _textos(at.tabs[1])


# --------------------------------------------------------------------------
# Con los pesos desplegados (se salta donde no están)
# --------------------------------------------------------------------------
def test_con_los_pesos_desplegados(monkeypatch, pesos_desplegados):
    """Las métricas de «Acerca de» son de estos pesos (su huella coincide). R15: el
    ejemplo normal sale «opacidad probable» con una RV por debajo de 1, y la app lo
    enseña tal cual. R17: encendido, el ejemplo AP pasa a «sin opacidad probable»
    y la app dice qué daría el global."""
    monkeypatch.setenv("RUTA_PESOS", str(pesos_desplegados))
    at = _app()
    assert any("coincide" in s.value for s in at.tabs[2].success)
    assert not any("otros pesos" in w.value for w in at.tabs[2].warning)

    _calcular(at)
    _sin_traza(at)
    r = at.session_state["ultimo"]["resultado"]
    assert r["clasificacion"] == "opacidad_probable" and r["razon_de_verosimilitud"] < 1
    texto = _textos(at.tabs[0])
    assert "CRIBADO — opacidad probable" in texto
    assert "La imagen apenas mueve la probabilidad" in texto
    assert POSITIVO_SIN_APOYO in texto

    _elegir_ejemplo(at, "neumonia_ap")
    at.toggle(key="por_vista").set_value(True)
    _calcular(at)
    assert at.session_state["ultimo"]["resultado"]["clasificacion"] == (
        "sin_opacidad_probable")
    texto = _textos(at.tabs[0])
    assert "CRIBADO — sin opacidad probable" in texto
    assert "sería «opacidad probable»" in texto


# --------------------------------------------------------------------------
# Los textos del bot, la configuración y las dependencias
# --------------------------------------------------------------------------
def _codigo_del_nodo(nombre) -> str:
    """El `jsCode` de un nodo del bot del profesional, con las cadenas que se parten
    en varias líneas (un `'...' +` y, en la siguiente, `'...'`) ya unidas."""
    nodos = json.loads(BOT.read_text(encoding="utf-8"))["nodes"]
    (codigo,) = [n["parameters"]["jsCode"] for n in nodos if n["name"] == nombre]
    return re.sub(r"'\s*\+\s*'", "", codigo)


def test_los_textos_copiados_del_bot_son_los_del_bot(modulo_app):
    """R12: los avisos y los rechazos se copian del bot: los del informe, de su nodo
    «Desenlace», y la frase de lo que no se pudo interpretar, de «Leer respuesta».
    Si el bot cambia una frase, esto avisa de que la app dice otra cosa."""
    desenlace = _codigo_del_nodo("Desenlace")
    assert len(modulo_app.DEL_BOT) >= 30
    for clave, texto in modulo_app.DEL_BOT.items():
        assert texto in desenlace, clave
    lectura = _codigo_del_nodo("Leer respuesta")
    assert modulo_app.DEL_BOT_LECTURA
    for clave, texto in modulo_app.DEL_BOT_LECTURA.items():
        assert texto in lectura, clave
    # Y los que aquí se buscan en la pantalla son esos mismos.
    for texto in (DESCARGO, NO_PUDE_LEER, FUERA_DE_ALCANCE, EDAD_DESCONOCIDA,
                  COLETILLA_EDAD, POSITIVO_SIN_APOYO, SIN_COMBINAR):
        assert texto in desenlace
    assert SIN_CODIGO in lectura


def test_la_configuracion_de_streamlit(modulo_app):
    config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
    assert config["server"]["maxUploadSize"] == 5 == modulo_app.TAMANO_MAXIMO_MB
    assert modulo_app.TAMANO_MAXIMO_BYTES == 5 * 1024 * 1024
    assert config["browser"]["gatherUsageStats"] is False
    assert config["client"]["showErrorDetails"] == "none"


def test_las_dependencias_de_la_app_van_fijadas():
    lineas = [l.split("#")[0].strip() for l in
              REQUISITOS.read_text(encoding="utf-8").splitlines()]
    fijadas = dict(l.split("==") for l in lineas if l)
    assert all(re.fullmatch(r"[A-Za-z0-9_.\-\[\]]+==[0-9][0-9A-Za-z.]*", f"{k}=={v}")
               for k, v in fijadas.items())
    assert fijadas["streamlit"] == "1.65.0"
    assert fijadas["altair"] == "6.3.0"
    assert fijadas["matplotlib"] == "3.11.2"
    # Todas las que pyproject.toml declara, fijadas; y las que allí ya van fijadas,
    # con su misma versión.
    proyecto = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    for dependencia in proyecto["dependencies"]:
        nombre = re.split(r"[=<>\[]", dependencia)[0]
        assert any(re.split(r"\[", k)[0] == nombre for k in fijadas), nombre
        if "==" in dependencia:
            assert fijadas[nombre] == dependencia.split("==")[1], nombre
    # Y las que servidor/Dockerfile fija, con su misma versión.
    dockerfile = (REPO / "servidor" / "Dockerfile").read_text(encoding="utf-8")
    del_servidor = dict(re.findall(r'"([A-Za-z0-9_.\-\[\]]+)==([0-9.]+)"', dockerfile))
    assert del_servidor
    for nombre, version in del_servidor.items():
        assert fijadas[nombre] == version, nombre
