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
- El «≥» / «<» de «puntuación … umbral …» es el de la etiqueta del motor, no el de
  comparar los dos números redondeados que se enseñan (un empate redondeado de un
  negativo no dice «≥»).
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
import struct
import sys
import tomllib
import zlib
from pathlib import Path

import numpy as np
import pydicom
import pytest
import streamlit as st
import torch
from PIL import Image
from streamlit.runtime.memory_media_file_storage import MemoryMediaFileStorage
from streamlit.testing.v1 import AppTest

from copiloto_triaje.datos.dicom import leer_dicom_desde_bytes
from copiloto_triaje.modelo.arquitectura import construir_modelo
from copiloto_triaje.servicio.calibracion import Calibrador
from copiloto_triaje.servicio.heckerling import combinacion
from copiloto_triaje.servicio.inferencia import ErrorDeInferencia, Motor

from test_dicom import crear_dicom

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

FUENTE_EJEMPLO = "Usar un ejemplo"
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
# La frase del bot («Leer respuesta») para lo que no se pudo interpretar, sin su punto
# final: la app le añade «, o pruebe con un ejemplo.» (M9).
SIN_CODIGO = ("No pude interpretar el contenido del fichero. Si lo recortó al "
              "enviarlo, vuelva a exportarlo completo")
INESPERADO = "\n\n".join([NO_PUDE_LEER, SIN_CODIGO + ", o pruebe con un ejemplo."])
# R24: lo que se dice de una placa que el modelo vería mal, y no se calcula.
DIECISEIS_BITS = "\n\n".join([
    "Esta placa es de 16 bits: los visores la enseñan bien, pero el modelo se entrenó "
    "con placas de 8 bits, como las de RSNA, y hoy no convierte las demás: la vería "
    "saturada, casi blanca. Así que no se calcula nada.",
    "Expórtela en 8 bits, o pruebe con un ejemplo."])
INVERTIDA = "\n\n".join([
    "Esta placa guarda la escala de grises invertida: los visores la enseñan bien, pero "
    "el modelo se entrenó con placas como las de RSNA, con el hueso claro, y hoy no las "
    "invierte: la vería al revés, con el hueso oscuro. Así que no se calcula nada.",
    "Expórtela con la escala de grises normal (en DICOM, MONOCHROME2), o pruebe con un "
    "ejemplo."])
# R27: lo que se dice mirando solo la cabecera, antes de descodificar un píxel.
EN_COLOR = "\n\n".join([
    "Esta placa no está en escala de grises: los visores la enseñan bien, pero el modelo "
    "se entrenó con placas en grises, como las de RSNA, y hoy no convierte las demás. Así "
    "que no se calcula nada.",
    "Expórtela en escala de grises (en DICOM, MONOCHROME2), o pruebe con un ejemplo."])
NBSP = " "


def _lado(filas, columnas):
    return "\n\n".join([
        f"Esta placa declara {filas} × {columnas} píxeles, y la app no lee placas de más "
        f"de 5{NBSP}000 de lado (una placa de tórax digital no llega a tanto). Así que no "
        "se calcula nada.",
        "Expórtela más pequeña, o pruebe con un ejemplo."])


def _bits(bits, como):
    return "\n\n".join([
        f"Esta placa es de {bits}: los visores la enseñan bien, pero el modelo se entrenó "
        f"con placas de 8 bits, como las de RSNA, y hoy no convierte las demás: {como}. Así "
        "que no se calcula nada.",
        "Expórtela en 8 bits, o pruebe con un ejemplo."])


VARIOS_CUADROS = "\n\n".join([
    "Este fichero trae 2 imágenes, y la app evalúa una placa sola. Así que no se calcula "
    "nada.",
    "Exporte solo la placa de tórax, o pruebe con un ejemplo."])
# R28: lo que se dice mirando solo la metainformación (el grupo 0002).
DEFLATED = "\n\n".join([
    "Este fichero viene comprimido entero (en DICOM, «Deflated Explicit VR Little "
    "Endian»), y la app no lo descomprime: podría ocupar cientos de veces lo que pesa. "
    "Así que no se calcula nada.",
    "Expórtelo sin comprimir, o pruebe con un ejemplo."])
# Lo que el motor dice de un fichero que no es un DICOM (`dicom_invalido`): ahora lo
# dice la app antes de leer nada, con las mismas palabras.
NO_ES_UN_DICOM = "\n\n".join([
    NO_PUDE_LEER,
    "Compruebe que es el DICOM de la placa y que está completo (una foto o un JPEG no "
    "sirven), o pruebe con un ejemplo."])
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


@pytest.fixture
def motor_que_no_se_llama(monkeypatch):
    """Un `Motor` que no se puede usar: cada llamada a `clasificar` o a `mapa_de_calor`
    se apunta y revienta. La lista de llamadas tiene que acabar vacía."""
    llamadas = []

    def no_me_llames(self, *args, **kwargs):
        llamadas.append(args)
        raise AssertionError("el motor no se tenía que llamar")

    monkeypatch.setattr(Motor, "clasificar", no_me_llames)
    monkeypatch.setattr(Motor, "mapa_de_calor", no_me_llames)
    return llamadas


@pytest.fixture
def sin_descodificar(monkeypatch):
    """Nadie descodifica un píxel: `Dataset.pixel_array`, por donde pasan el lector del
    proyecto, la app y el motor, se apunta y revienta EN EL ACTO, antes de reservar nada.
    Así, si la app descodificara una placa que declara 60 000 × 60 000, la prueba falla
    (la app daría otro mensaje y esta lista no estaría vacía) en vez de colgarse
    reservando 3,35 GiB."""
    descodificados = []

    def no_descodifiques(self):
        descodificados.append((self.get("Rows"), self.get("Columns")))
        raise AssertionError("no se tenía que descodificar ni un píxel")

    monkeypatch.setattr(pydicom.dataset.Dataset, "pixel_array", property(no_descodifiques))
    return descodificados


@pytest.fixture
def sin_leer_el_conjunto(monkeypatch):
    """Devuelve `vigilar()`: desde que se llama, ninguna lectura del CONJUNTO de datos
    -`pydicom.dcmread` y, por debajo, `read_partial`, que es donde pydicom infla un
    deflated- ni ningún `zlib.decompress`: se apuntan y revientan en el acto. Leer el
    grupo 0002 (`read_preamble` y `_read_file_meta_info`) sí se puede. Se activa DESPUÉS
    de escribir el fichero de la prueba, que también usa pydicom."""
    lecturas = []

    def espia(nombre):
        def no_leas(*args, **kwargs):
            lecturas.append(nombre)
            raise AssertionError(f"no se tenía que llamar a {nombre}")
        return no_leas

    def vigilar():
        monkeypatch.setattr(pydicom, "dcmread", espia("pydicom.dcmread"))
        monkeypatch.setattr(pydicom.filereader, "dcmread", espia("filereader.dcmread"))
        monkeypatch.setattr(pydicom.filereader, "read_partial", espia("read_partial"))
        monkeypatch.setattr(zlib, "decompress", espia("zlib.decompress"))
        return lecturas

    return vigilar


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
    uno = METRICAS["umbral_por_vista_en_prueba"]["un_umbral"]
    dos = METRICAS["umbral_por_vista_en_prueba"]["dos_umbrales"]
    assert list(precio["Especificidad, dos umbrales"])[2].startswith(
        _dec(dos["global"]["especificidad"], 2))
    # M5: la frase del precio dice también lo que cada vista PIERDE, con las cifras
    # del JSON: la especificidad de las PA y la sensibilidad de las AP.
    clave = {"sensibilidad": "recall", "especificidad": "especificidad"}
    pierde = lambda vista, medida: (f"la {medida} baja de {_dec(uno[vista][clave[medida]], 2)}"
                                    f" a {_dec(dos[vista][clave[medida]], 2)}")
    assert "en las placas PA, la sensibilidad sube de " in texto
    assert pierde("PA", "especificidad") in texto
    assert pierde("AP", "sensibilidad") in texto
    assert pierde("global", "especificidad") in texto
    # M3: las cotas de la RV de la imagen, las de los extremos SOSTENIDOS del
    # calibrador versionado, recalculadas aquí con su fórmula y no con la del motor.
    calibrador = Calibrador.desde_json(CALIBRADOR)
    odds = lambda p: p / (1 - p)
    cota = lambda p: odds(p) / odds(calibrador.prevalencia)
    rv = lambda v: _dec(v, 2 if v < 10 else 1)
    assert (f"entre {rv(cota(calibrador.probabilidad_minima_sostenida))} y "
            f"{rv(cota(calibrador.probabilidad_maxima_sostenida))}.") in texto
    # M7: la combinación, también cuando la clínica y la imagen se oponen (entonces
    # `combinacion` no calcula la dependencia: ver RAMAS, más abajo).
    assert ("cuando se oponen, esa segunda no se calcula, y el resultado es la "
            "probabilidad bajo independencia —una, o dos si el asma no se sabe—, que el "
            "informe da por orientativa") in texto
    # La atribución de los ejemplos, con su licencia.
    assert any("CC0" in _textos(e) for e in acerca.expander)
    # Honestidad: estas métricas son de otros pesos que los cargados (aquí, la red
    # aleatoria), y la app lo dice.
    assert any("otros pesos" in w.value for w in acerca.warning)
    # M6: la placa viaja al servidor de la app; lo que no hace es ir a ningún OTRO.
    cabecera = _textos(at)
    assert "la placa no se envía a ningún otro sitio" in cabecera
    assert "no se envía a ningún sitio" not in cabecera


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


def test_el_boton_prueba_con_ejemplo_calcula_el_ejemplo_elegido(pesos_aleatorios):
    """M2: el mínimo del curso pide un botón «Prueba con ejemplo». Junto al selector, y
    calcula el ejemplo elegido, con los hallazgos y el interruptor que haya; «Calcular»
    sigue haciendo lo mismo. Al subir un fichero, el botón no está."""
    at = _elegir_ejemplo(_app(), "neumonia_ap")
    # Con el botón, la opción del control ya no se llama igual: dos «Prueba con
    # ejemplo» en la misma columna confundirían.
    assert at.segmented_control(key="fuente").options == [FUENTE_EJEMPLO, FUENTE_FICHERO]
    boton = at.button(key="probar_ejemplo")
    assert boton.label == "Prueba con ejemplo"
    boton.click().run()
    _sin_traza(at)
    esperado = _motor(pesos_aleatorios).clasificar(_ejemplo("neumonia_ap"))
    obtenido = at.session_state["ultimo"]["resultado"]
    assert {k: v for k, v in obtenido.items() if k != "milisegundos"} == {
        k: v for k, v in esperado.items() if k != "milisegundos"}
    assert "Resultado: ejemplo «Neumonía, AP — según su fuente»" in _textos(at.tabs[0])
    assert [f["origen"] for f in at.session_state["historial"]] == ["ejemplo: neumonia_ap"]
    at.segmented_control(key="fuente").set_value(FUENTE_FICHERO).run()
    assert "probar_ejemplo" not in [b.key for b in at.button]


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
    # Desde R28 lo dice la app antes de leer nada, con las palabras del motor.
    assert errores == [NO_ES_UN_DICOM]
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
    """Un DICOM sano salvo que `Rows` está presente y SIN valor (pydicom lo devuelve como
    `None`), con los mismos bytes en ese elemento que el de `crear_dicom_con_tag_vacio`.
    Esa ayuda escribe la edad como «51», que no es un valor del VR AS, y pydicom avisa;
    aquí va con el formato DICOM («054Y»), y el aviso no sale."""
    ruta = _dicom(tmp_path, "rows_vacio.dcm", edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    ds.Rows = None
    ds.save_as(str(ruta), enforce_file_format=True)
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
    assert error == INESPERADO
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
    assert error == INESPERADO
    assert "detalle interno" not in _textos(at)
    _sin_resultado(at)


# --------------------------------------------------------------------------
# R24: una placa que el modelo vería mal no se calcula
# --------------------------------------------------------------------------
def _de_16_bits(tmp_path):
    """El DICOM del ayudante, con sus píxeles en 16 bits (y valores por encima de 255,
    como los de un PACS)."""
    ruta = _dicom(tmp_path, nombre="placa16.dcm", edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    pixeles = (np.arange(64 * 64).reshape(64, 64) * 16).astype(np.uint16)
    ds.BitsAllocated, ds.BitsStored, ds.HighBit = 16, 16, 15
    ds.PixelData = pixeles.tobytes()
    ds.save_as(str(ruta), enforce_file_format=True)
    return ruta.read_bytes()


def _invertida(tmp_path):
    """El DICOM del ayudante, de 8 bits pero MONOCHROME1: blanco y negro invertidos."""
    ruta = _dicom(tmp_path, nombre="invertida.dcm", edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    ds.PhotometricInterpretation = "MONOCHROME1"
    ds.save_as(str(ruta), enforce_file_format=True)
    return ruta.read_bytes()


def _en_color(tmp_path):
    """El DICOM del ayudante, en RGB: tres muestras por píxel."""
    ruta = _dicom(tmp_path, nombre="color.dcm", edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    ds.PhotometricInterpretation, ds.SamplesPerPixel, ds.PlanarConfiguration = "RGB", 3, 0
    ds.PixelData = bytes(64 * 64 * 3)
    ds.save_as(str(ruta), enforce_file_format=True)
    return ruta.read_bytes()


def _enorme(tmp_path):
    """Unos 600 bytes que declaran 60 000 × 60 000, en RLE: un solo fragmento con su
    cabecera de 64 bytes (un segmento) y un segmento de dos bytes. `pixel_array`
    intentaría reservar 3,35 GiB (medido, con un tope de memoria, en el informe)."""
    from pydicom.encaps import encapsulate
    from pydicom.uid import RLELossless
    ruta = _dicom(tmp_path, nombre="enorme.dcm", edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    ds.Rows = ds.Columns = 60000
    ds.file_meta.TransferSyntaxUID = RLELossless
    ds.PixelData = encapsulate([struct.pack("<16L", 1, 64, *([0] * 14)) + b"\x81\x00"])
    ds["PixelData"].VR = "OB"
    ds["PixelData"].is_undefined_length = True
    ds.save_as(str(ruta), enforce_file_format=True)
    return ruta.read_bytes()


def _sin_fotometria(tmp_path):
    """El DICOM del ayudante sin `PhotometricInterpretation`: no se sabe cómo leerlo."""
    ruta = _dicom(tmp_path, nombre="incompleta.dcm", edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    del ds.PhotometricInterpretation
    ds.save_as(str(ruta), enforce_file_format=True)
    return ruta.read_bytes()


@pytest.mark.parametrize("hacer, mensaje", [
    (_de_16_bits, DIECISEIS_BITS), (_invertida, INVERTIDA), (_en_color, EN_COLOR),
    (_enorme, _lado(f"60{NBSP}000", f"60{NBSP}000")), (_sin_fotometria, INESPERADO)],
    ids=["16_bits", "monochrome1", "rgb", "60000x60000", "sin_fotometria"])
def test_una_placa_que_el_modelo_veria_mal_se_rechaza_por_la_cabecera(
        tmp_path, motor_que_no_se_llama, sin_descodificar, hacer, mensaje):
    """R24 y R27: el motor convierte con `Image.fromarray(arreglo).convert("RGB")`, que
    satura todo lo que pasa de 255, no invierte una MONOCHROME1 y no lleva tope de
    memoria. Una cifra que se sabe que no vale no se enseña, ni con aviso: rechazo
    mirando SOLO la cabecera, sin descodificar un píxel y sin llamar al motor, sin
    ningún bloque ni mapa, y sin entrar en el historial. Con hallazgos y con el
    interruptor encendido, igual."""
    datos = hacer(tmp_path)
    assert len(datos) < 20_000                          # ninguna pesa nada
    at = _subir(_app(), "placa.dcm", datos)
    _poner_hallazgos(at, HALLAZGOS)
    at.toggle(key="por_vista").set_value(True)
    _calcular(at)
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    assert error == mensaje
    _sin_resultado(at)
    assert motor_que_no_se_llama == []
    assert sin_descodificar == []


def test_un_entero_con_signo_lo_para_la_segunda_red(tmp_path, motor_que_no_se_llama):
    """La cabecera de 8 bits pasa, pero con `PixelRepresentation` 1 los píxeles salen
    `int8`: la comprobación del arreglo (la segunda red) lo para, sin llamar al motor."""
    ruta = _dicom(tmp_path, nombre="con_signo.dcm", edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    ds.PixelRepresentation = 1
    ds.save_as(str(ruta), enforce_file_format=True)
    at = _calcular(_subir(_app(), "placa.dcm", ruta.read_bytes()))
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    assert error == _bits("8 bits con signo", "la vería mal")
    _sin_resultado(at)
    assert motor_que_no_se_llama == []


# --------------------------------------------------------------------------
# R28: antes de leer el conjunto de datos, solo la metainformación (el grupo 0002)
# --------------------------------------------------------------------------
def _deflated(tmp_path):
    """El DICOM del ayudante con la sintaxis Deflated Explicit VR Little Endian, escrita
    por pydicom: TODO el conjunto de datos tras el grupo 0002, comprimido con zlib. Leer
    su cabecera con `dcmread(..., stop_before_pixels=True)` ya lo infla entero (con 400
    MiB de ceros dentro, un fichero de 398 KiB llevó el pico de 54 a 854 MiB: informe)."""
    ruta = _dicom(tmp_path, nombre="deflated.dcm", edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    ds.file_meta.TransferSyntaxUID = pydicom.uid.DeflatedExplicitVRLittleEndian
    ds.save_as(str(ruta), enforce_file_format=True)
    return ruta.read_bytes()


def _sin_sintaxis(tmp_path):
    """Un grupo 0002 que se lee, pero sin `TransferSyntaxUID`, y un conjunto de datos
    sano detrás: pydicom lee la cabecera y no sabe descodificar los píxeles."""
    ruta = _dicom(tmp_path, nombre="sin_sintaxis.dcm", edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    del ds.file_meta.TransferSyntaxUID
    ds.preamble = bytes(128)
    salida = io.BytesIO()
    pydicom.dcmwrite(salida, ds, enforce_file_format=False, implicit_vr=False,
                     little_endian=True)
    return salida.getvalue()


def test_un_dicom_deflated_se_rechaza_sin_inflarlo(tmp_path, motor_que_no_se_llama,
                                                   sin_leer_el_conjunto):
    """R28: la sintaxis se mira en el grupo 0002, que nunca va comprimido, ANTES de
    cualquier `dcmread`. Deflated: rechazo en lenguaje llano, nada se infla, el motor no
    se llama y el historial no crece. Con hallazgos y el interruptor encendido, igual."""
    datos = _deflated(tmp_path)
    # Lo es de verdad (se comprueba antes de los espías, leyéndolo entero: es pequeño).
    assert pydicom.dcmread(io.BytesIO(datos)).file_meta.TransferSyntaxUID == (
        pydicom.uid.DeflatedExplicitVRLittleEndian)
    lecturas = sin_leer_el_conjunto()
    at = _subir(_app(), "deflated.dcm", datos)
    _poner_hallazgos(at, HALLAZGOS)
    at.toggle(key="por_vista").set_value(True)
    _calcular(at)
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    assert error == DEFLATED
    _sin_resultado(at)
    assert motor_que_no_se_llama == [] and lecturas == []


def _solo_el_preambulo(tmp_path):
    return _ejemplo("normal_pa")[:132]                  # 128 bytes y «DICM», nada más


def _metainformacion_cortada(tmp_path):
    return _ejemplo("normal_pa")[:150]                  # el grupo 0002, a medias


def _texto(tmp_path):
    return b"esto no es un DICOM"


@pytest.mark.parametrize("hacer", [_texto, _solo_el_preambulo, _metainformacion_cortada,
                                   _sin_sintaxis],
                         ids=["texto", "solo_el_preambulo", "0002_cortado",
                              "0002_sin_sintaxis"])
def test_un_fichero_sin_metainformacion_legible_no_se_evalua(
        tmp_path, motor_que_no_se_llama, sin_leer_el_conjunto, hacer):
    """R28: sin el prefijo «DICM», con el grupo 0002 cortado o sin la sintaxis de
    transferencia, la placa no se puede evaluar. Se dice en llano, con las palabras que
    el motor da a lo que no es un DICOM, sin leer el conjunto de datos y sin llamar al
    motor."""
    datos = hacer(tmp_path)
    lecturas = sin_leer_el_conjunto()
    at = _calcular(_subir(_app(), "placa.dcm", datos))
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    assert error == NO_ES_UN_DICOM
    _sin_resultado(at)
    assert motor_que_no_se_llama == [] and lecturas == []


def test_una_placa_sana_pasa_la_metainformacion_y_se_calcula(tmp_path):
    """Lo contrario: con la sintaxis de siempre (Explicit VR Little Endian), la app sigue
    adelante y calcula."""
    at = _calcular(_subir(_app(), "placa.dcm", _dicom(tmp_path, edad="054Y")
                          .read_bytes()))
    _sin_traza(at)
    assert at.session_state["ultimo"]["resultado"]["clasificacion"]
    assert len(at.session_state["historial"]) == 1


def _cabecera(**cambios):
    """La cabecera de una placa que pasa (la de `normal_pa`), con cambios: un valor lo
    pone, `None` lo deja vacío y `QUITAR` lo borra."""
    ds = pydicom.Dataset()
    ds.Rows, ds.Columns, ds.BitsAllocated, ds.SamplesPerPixel = 768, 671, 8, 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    # SP5-B4: la regla es la del motor (datos/dicom.py), que pide además los dos campos
    # sin los que pydicom no descodifica (sin uno, un AttributeError), como los trae
    # `normal_pa`.
    ds.BitsStored, ds.PixelRepresentation = 8, 0
    for campo, valor in cambios.items():
        if valor is QUITAR:
            delattr(ds, campo)
        else:
            setattr(ds, campo, valor)
    return ds


QUITAR = object()
CAMPOS_DE_LA_IMAGEN = ("Rows", "Columns", "BitsAllocated", "SamplesPerPixel",
                       "PhotometricInterpretation")


@pytest.mark.parametrize("cambios, mensaje", [
    ({}, None),
    ({"Rows": 5000, "Columns": 5000}, None),                    # el borde: pasa
    ({"Rows": 5001}, _lado(f"5{NBSP}001", "671")),
    ({"Columns": 5001}, _lado("768", f"5{NBSP}001")),
    ({"NumberOfFrames": 1}, None),
    ({"NumberOfFrames": 2}, VARIOS_CUADROS),
    ({"BitsAllocated": 16}, DIECISEIS_BITS),
    ({"BitsAllocated": 1}, _bits("1 bit", "la vería mal")),
    ({"PhotometricInterpretation": "MONOCHROME1"}, INVERTIDA),
    ({"PhotometricInterpretation": "RGB", "SamplesPerPixel": 3}, EN_COLOR),
    ({"PhotometricInterpretation": "PALETTE COLOR"}, EN_COLOR),
    ({"PhotometricInterpretation": "YBR_FULL_422", "SamplesPerPixel": 3}, EN_COLOR),
    ({"SamplesPerPixel": 3}, EN_COLOR),
    ({"Rows": None}, INESPERADO),                               # presente pero vacío
    *[({campo: QUITAR}, INESPERADO) for campo in CAMPOS_DE_LA_IMAGEN],
], ids=["pasa", "5000x5000_pasa", "rows_5001", "columns_5001", "un_cuadro_pasa",
        "dos_cuadros", "16_bits", "1_bit", "monochrome1", "rgb", "paleta", "ybr",
        "tres_muestras", "rows_vacio", *[f"sin_{c}" for c in CAMPOS_DE_LA_IMAGEN]])
def test_lo_que_dice_la_cabecera(modulo_app, cambios, mensaje):
    """R27, campo a campo: `BitsAllocated` 8, `PhotometricInterpretation` MONOCHROME2,
    `SamplesPerPixel` 1, `Rows` y `Columns` hasta 5 000 y, además, un solo cuadro (con
    5 000 × 5 000 por N cuadros, el mismo agujero de memoria). Si falta uno de los
    cinco campos, la placa no se puede evaluar: el mensaje de R18."""
    assert modulo_app.motivo_por_la_cabecera(_cabecera(**cambios)) == mensaje


@pytest.mark.parametrize("tipo, mensaje", [
    (np.uint8, None), (np.int8, _bits("8 bits con signo", "la vería mal")),
    (np.uint16, DIECISEIS_BITS)], ids=["uint8", "int8", "uint16"])
def test_la_segunda_red_mira_el_tipo_del_arreglo(modulo_app, tipo, mensaje):
    assert modulo_app.motivo_por_los_pixeles(np.zeros((4, 4), tipo)) == mensaje


def test_la_placa_que_se_ensena_es_la_que_recibe_el_modelo(modulo_app):
    """Sin estirar nada: `Image.fromarray(arreglo).convert("L")`, lo mismo que el
    motor antes de `convert("RGB")` (cada canal de su RGB es esto). Con 16 bits sería la
    placa saturada; se rechaza antes (R24), pero lo que se enseña nunca puede ser una
    placa más bonita que la que puntuó el modelo."""
    pixeles = (np.arange(40 * 30).reshape(40, 30) * 50).astype(np.uint16)
    modelo = np.asarray(Image.fromarray(pixeles).convert("RGB"))
    vista = modulo_app.placa_para_ver(pixeles)
    assert vista.dtype == np.uint8 and vista.shape == (40, 30)
    assert np.array_equal(vista, modelo[..., 0])
    assert np.array_equal(vista, np.clip(pixeles, 0, 255).astype(np.uint8))
    # Una de 8 bits, tal cual.
    gris = np.random.default_rng(0).integers(100, 150, (40, 30), dtype=np.uint8)
    assert np.array_equal(modulo_app.placa_para_ver(gris), gris)


def test_el_resultado_ensena_la_placa_que_puntuo_el_modelo():
    at = _calcular(_elegir_ejemplo(_app(), "neumonia_pa"))
    arreglo, _ = leer_dicom_desde_bytes(_ejemplo("neumonia_pa"))
    assert np.array_equal(at.session_state["ultimo"]["placa"],
                          np.asarray(Image.fromarray(arreglo).convert("L")))


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
    aplica si se lanza desde la raíz). 5 MB justos pasan el tamaño, y se quedan en la
    metainformación (unos ceros no son un DICOM: R28); uno más, ni eso."""
    at = _subir(_app(), "grande.dcm", b"\0" * (5 * 1024 * 1024 + de_mas))
    assert at.file_uploader(key="dicom").proto.max_upload_size_mb == 5
    _calcular(at)
    _sin_traza(at)
    (error,) = [e.value for e in at.tabs[0].error]
    if de_mas:
        assert error.startswith("El archivo supera los 5 MB.")
    else:
        assert error == NO_ES_UN_DICOM
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


def test_la_temperatura_que_puntua_es_la_que_ensena_el_campo():
    """M1: el campo enseña un decimal («%.1f»), y el motor recibe ese mismo número. Con
    37,84 el campo dice 37,8, que no pasa del corte de 37,8: la temperatura no puntúa
    (antes, el motor recibía 37,84 y sí puntuaba, con «37,8 °C» en el informe)."""
    at = _app()
    _poner_hallazgos(at, HALLAZGOS | {"temperatura_c": 37.84})
    _calcular(at)
    _sin_traza(at)
    c = at.session_state["ultimo"]["resultado"]["combinacion"]
    # 104 lpm y crepitantes, sin murmullo, asma no sé: 2 o 3, sin la temperatura.
    assert c["puntuacion"] == [2, 3]
    texto = _textos(at.tabs[0])
    assert "Heckerling 2 o 3 de 5" in texto and "(37,8 °C, 104 lpm" in texto
    assert at.session_state["historial"][0]["temperatura_c"] == 37.8


@pytest.mark.parametrize("tecleada, enviada", [(37.84, 37.8), (37.86, 37.9),
                                               (38.25, 38.3), (36.0, 36.0)])
def test_la_temperatura_se_redondea_como_la_ensena_el_campo(modulo_app, tecleada,
                                                            enviada):
    """El campo formatea con «%.1f» como `toFixed` de JavaScript: la mitad hacia arriba
    sobre el valor exacto (38,25 es exacto en binario y el campo enseña 38.3). El
    `round` de Python iría al par (38,2): el informe diría otro número que el campo."""
    hallazgos, falta = modulo_app._hallazgos_o_que_falta(
        (tecleada, 104, "si", "no", "no_se"))
    assert falta is None and hallazgos["temperatura_c"] == enviada
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
# El «≥» / «<» de «puntuación … umbral …» es el de la etiqueta del motor
# --------------------------------------------------------------------------
# La etiqueta la decide el motor con la puntuación SIN redondear, y la respuesta lleva la
# puntuación y el umbral a 4 decimales: con una cruda de 0,42575 y un umbral de 0,4258 la
# etiqueta es «sin opacidad probable» y la respuesta dice 0,4258 y 0,4258. Comparar esos
# dos números diría «0,4258 ≥ 0,4258» junto a un negativo. La verdad es la etiqueta.
@pytest.mark.parametrize("cruda, clasificacion, comparador", [
    (UMBRAL_GLOBAL, "sin_opacidad_probable", "<"),      # el empate redondeado, negativo
    (UMBRAL_GLOBAL, "opacidad_probable", "≥"),          # los mismos números, la otra etiqueta
    (0.2000, "sin_opacidad_probable", "<"),
    (0.9000, "opacidad_probable", "≥"),
])
def test_el_comparador_de_la_puntuacion_sale_de_la_etiqueta_del_motor(
        modulo_app, cruda, clasificacion, comparador):
    r = {"probabilidad_cruda": cruda, "umbral": UMBRAL_GLOBAL, "clasificacion": clasificacion}
    texto = modulo_app.texto_del_punto(r, METRICAS)
    assert texto.startswith(f"puntuación {_dec(cruda, 4)} {comparador} umbral "
                            f"{_dec(UMBRAL_GLOBAL, 4)}"), texto
    assert ("<" if comparador == "≥" else "≥") not in texto, texto


def test_la_pantalla_pinta_menor_si_la_etiqueta_es_negativa_aunque_los_numeros_empaten(
        monkeypatch):
    """La respuesta del motor con la puntuación a 0,4258 y el umbral a 0,4258 y,
    aun así, «sin_opacidad_probable» (la sin redondear caía por debajo): la pantalla
    dice «0,4258 < umbral 0,4258», y no «≥» junto a un negativo."""
    clasificar = Motor.clasificar

    def con_la_cruda_en_el_umbral(self, datos, hallazgos=None):
        return {**clasificar(self, datos, hallazgos), "probabilidad_cruda": UMBRAL_GLOBAL,
                "umbral": UMBRAL_GLOBAL, "clasificacion": "sin_opacidad_probable"}

    monkeypatch.setattr(Motor, "clasificar", con_la_cruda_en_el_umbral)
    at = _calcular(_app())
    _sin_traza(at)
    texto = _textos(at.tabs[0])
    assert "CRIBADO — sin opacidad probable" in texto
    assert f"puntuación {_dec(UMBRAL_GLOBAL, 4)} < umbral {_dec(UMBRAL_GLOBAL, 4)}" in texto
    assert "≥" not in texto


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


# --------------------------------------------------------------------------
# El aviso de dependencia y la horquilla (M3), rama por rama
# --------------------------------------------------------------------------
def _hallazgos(temperatura=36.5, frecuencia=80, crepitantes=False, murmullo=False,
               asma="si"):
    return {"temperatura_c": temperatura, "frecuencia_cardiaca": frecuencia,
            "crepitantes": crepitantes, "murmullo_disminuido": murmullo, "asma": asma}


_MISMA = ("⚠️ La auscultación y la imagen miran la misma consolidación, así que no son "
          "pruebas independientes: ")
_FIEBRE = dict(temperatura=38.5, frecuencia=110, crepitantes=True)


# (hallazgos, RV de la imagen, lo que tiene que salir del motor, la horquilla, el aviso).
# Cada RV está elegida para llegar a una rama; las cifras, recalculadas a mano: con
# prevalencia 0,1466 las odds de partida son 0,1718.
RAMAS = {
    # 3 puntos (RV 1,64) y una imagen de 6: concordantes, manda la imagen.
    # 0,1718 x 1,64 x 6 = 1,690 -> 63 %; 0,1718 x 6 = 1,031 -> 51 %.
    "concordante_absorbe_la_imagen": (
        _hallazgos(**_FIEBRE), 6.0, {"concordantes": True, "absorbe": "imagen"},
        "entre 51 % y 63 %",
        _MISMA + "el 63 % supone que cada una aporta información nueva, y el 51 %, que "
                 "la auscultación no añade nada sobre la imagen. Decide usted."),
    # 5 puntos (RV 17,5) y una imagen de 1,2: manda la clínica.
    # 0,1718 x 17,5 x 1,2 = 3,607 -> 78 %; 0,1718 x 17,5 = 3,006 -> 75 %.
    "concordante_absorbe_la_clinica": (
        _hallazgos(**_FIEBRE, murmullo=True, asma="no"), 1.2,
        {"concordantes": True, "absorbe": "clinica"}, "entre 75 % y 78 %",
        _MISMA + "el 78 % supone que cada una aporta información nueva, y el 75 %, que "
                 "la imagen no añade nada sobre la auscultación. Decide usted."),
    # 3 o 4 (RV 1,64 o 7,18) y una imagen de 2: con 3 manda la imagen, con 4 la clínica.
    "concordante_mixta": (
        _hallazgos(**_FIEBRE, asma="no_se"), 2.0,
        {"concordantes": True, "absorbe": "mixta"}, "entre 26 % y 71 %",
        _MISMA + "el 71 % supone que cada una aporta información nueva, y el 26 %, que "
                 "solo cuenta la más informativa de las dos. Decide usted."),
    # 5 puntos y la imagen casi en su cota (77): 99,6 % -> «> 99 %», así que no se
    # pueden nombrar los dos extremos y la frase es la corta. Y «más de 99 %».
    "puede_exagerar_y_mas_de_99": (
        _hallazgos(**_FIEBRE, murmullo=True, asma="no"), 77.0,
        {"concordantes": True, "absorbe": "imagen"}, "entre 93 % y más de 99 %",
        _MISMA + "la cifra puede exagerar. Decide usted."),
    # 0 puntos (RV 0,12) y una imagen de 0,1: 0,2 % -> «< 1 %» y 1,7 % -> 2 %.
    "menos_de_1": (
        _hallazgos(), 0.1, {"concordantes": True, "absorbe": "imagen"},
        "entre menos de 1 % y 2 %", _MISMA + "la cifra puede exagerar. Decide usted."),
    # 2 o 3 (RV 0,70 o 1,64) contra una imagen de 3: a lados distintos de 1.
    "depende_del_asma": (
        _hallazgos(temperatura=38.5, frecuencia=110, asma="no_se"), 3.0,
        {"concordantes": False, "absorbe": None}, "entre 27 % y 46 %",
        "⚠️ Que la clínica apunte en el mismo sentido que la imagen o en el contrario "
        "depende de si tiene asma, y además no son pruebas independientes: la horquilla "
        "es orientativa. Decide usted."),
    # 1 punto (RV 0,20) contra una imagen de 3: un solo número, que la frase llama «la
    # cifra». 0,1718 x 0,2 x 3 = 0,103 -> 9 %.
    "opuestos_en_un_numero": (
        _hallazgos(crepitantes=True), 3.0, {"concordantes": False, "absorbe": None},
        "9 %",
        "⚠️ La clínica y la imagen apuntan en sentidos opuestos, y además no son pruebas "
        "independientes: la cifra es orientativa. Decide usted."),
}


@pytest.mark.parametrize("rama", list(RAMAS))
def test_el_aviso_de_dependencia_y_la_horquilla_son_los_del_bot_en_cada_rama(
        modulo_app, rama):
    hallazgos, rv_imagen, del_motor, horquilla, aviso = RAMAS[rama]
    c = combinacion(float(PREVALENCIA), hallazgos, rv_imagen)
    assert {k: c[k] for k in del_motor} == del_motor          # se llega a la rama
    assert modulo_app.texto_de_la_horquilla(c) == horquilla
    assert modulo_app.aviso_de_dependencia(c) == aviso


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
    # La tabla de la pantalla enseña lo mismo, para una persona (M4): rótulos llanos,
    # «—» en lo vacío, coma decimal y la temperatura como la enseña el campo.
    (tabla,) = [d.value for d in at.tabs[1].dataframe]
    assert tuple(tabla.columns) == COLUMNAS and len(tabla) == 3
    assert "zoila" not in tabla.to_csv().lower()
    filas = tabla.to_dict("records")
    assert [f["origen"] for f in filas] == ["fichero subido",
                                            "Neumonía, PA — según su fuente",
                                            "Neumonía, PA — según su fuente"]
    assert [f["clasificacion"] for f in filas] == ["opacidad probable"] * 3
    assert [f["vista_del_umbral"] for f in filas] == ["—", "—", "PA"]
    assert [f["probabilidad_cruda"] for f in filas] == [
        _dec(float(d["probabilidad_cruda"]), 4) for d in datos]
    assert filas[2]["umbral"] == _dec(UMBRAL_PA, 4)
    assert {k: filas[2][k] for k in ("temperatura_c", "frecuencia_cardiaca", "crepitantes",
                                     "murmullo_disminuido", "asma",
                                     "puntuacion_heckerling", "rv_clinica",
                                     "prevalencia")} == {
        "temperatura_c": "38,2", "frecuencia_cardiaca": "104", "crepitantes": "sí",
        "murmullo_disminuido": "no", "asma": "no sé", "puntuacion_heckerling": "3 o 4",
        "rv_clinica": "1,64–7,18", "prevalencia": "14,7 %"}
    for clave in ("temperatura_c", "asma", "puntuacion_heckerling", "combinado_minima"):
        assert filas[0][clave] == "—", clave
    celdas = [str(v) for f in filas for v in f.values()]
    for crudo in ("None", "nan", "opacidad_probable", "no_se"):
        assert not any(crudo in c for c in celdas), crudo
    numericas = ("probabilidad_cruda", "umbral", "probabilidad_calibrada",
                 "razon_de_verosimilitud", "temperatura_c", "rv_clinica", "prevalencia")
    assert not any("." in f[k] for f in filas for k in numericas)


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
    # M8: torch y torchvision, de las ruedas para CPU, y lo demás de PyPI: las mismas
    # dos direcciones que `servidor/Dockerfile` pone en PIP_INDEX_URL y
    # PIP_EXTRA_INDEX_URL. Sin ellas, `pip install -r` baja la compilación con CUDA.
    opciones = [l for l in lineas if l.startswith("-")]
    assert opciones == ["--index-url https://download.pytorch.org/whl/cpu",
                        "--extra-index-url https://pypi.org/simple"]
    servidor = (REPO / "servidor" / "Dockerfile").read_text(encoding="utf-8")
    assert "PIP_INDEX_URL=https://download.pytorch.org/whl/cpu" in servidor
    assert "PIP_EXTRA_INDEX_URL=https://pypi.org/simple" in servidor
    fijadas = dict(l.split("==") for l in lineas if l and not l.startswith("-"))
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
