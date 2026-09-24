# tests/test_contrato_mcp.py
"""Lo que el bot de SP3 espera de copiloto-mcp.

Estas pruebas no comprueban el modelo: comprueban el CONTRATO. Si SP4 cambia
la forma de la respuesta, falla aqui en vez de romperse el bot en produccion.
"""
import base64
import json
import os
import pathlib
import re
import urllib.error
import urllib.request

import pytest

BASE = os.environ.get("COPILOTO_URL", "http://127.0.0.1:18000")
CRUDO = pathlib.Path(
    r"C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\crudo\stage_2_train_images")


def _llamar(b64: str) -> dict:
    cuerpo = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "clasificar_radiografia",
                   "arguments": {"dicom_base64": b64}}}).encode()
    pet = urllib.request.Request(
        f"{BASE}/mcp", data=cuerpo,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    texto = urllib.request.urlopen(pet, timeout=30).read().decode()
    for linea in texto.splitlines():
        if linea.startswith("data: "):
            return json.loads(linea[6:])
    pytest.fail(f"la respuesta no traia ninguna linea 'data: ': {texto[:200]}")


@pytest.fixture(scope="module")
def dicom_adulto() -> bytes:
    import pandas as pd
    raiz = pathlib.Path(r"C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo")
    df = pd.read_csv(raiz / "manifiestos" / "test.csv")
    return (CRUDO / f"{df[df.etiqueta == 1].iloc[0].patientId}.dcm").read_bytes()


@pytest.fixture(scope="module")
def dicom_menor() -> bytes:
    import pandas as pd
    repo = pathlib.Path(__file__).resolve().parents[1]
    meta = pd.read_csv(repo / "docs" / "eda" / "metadatos_eda.csv")
    menor = meta[meta.edad_num < 18].iloc[0]
    return (CRUDO / f"{menor.patientId}.dcm").read_bytes()


def test_un_tools_call_suelto_basta_sin_saludo_initialize(dicom_adulto):
    """El servidor es stateless_http: n8n puede hacer UN solo HTTP Request.

    Si esto dejara de ser cierto, el flujo necesitaria mantener sesion MCP y
    el diseno entero de §10.1 se cae.
    """
    r = _llamar(base64.b64encode(dicom_adulto).decode())
    assert r["result"]["isError"] is False


def test_la_respuesta_trae_structuredContent_con_las_claves_del_spec(dicom_adulto):
    sc = _llamar(base64.b64encode(dicom_adulto).decode())["result"]["structuredContent"]
    assert set(sc) >= {
        "probabilidad_cruda", "probabilidad_calibrada", "razon_de_verosimilitud",
        "umbral", "clasificacion", "edad_paciente", "modelo", "auc_validacion",
        "milisegundos"}


def test_el_base64_envuelto_da_el_mismo_resultado_que_el_plano(dicom_adulto):
    """n8n puede envolver a 76 columnas; el servidor quita los saltos.

    Se comprueban LF y CRLF: CRLF es el salto del MIME canonico y escapado
    dentro del JSON cuesta el doble, que es por donde se colo un fallo en SP2.

    Se compara todo salvo "milisegundos": es un tiempo de pared y varia entre
    dos llamadas identicas al mismo b64 plano (comprobado empiricamente), no
    es parte del contrato de "mismo resultado".
    """
    plano = base64.b64encode(dicom_adulto).decode()
    esperado = _llamar(plano)["result"]["structuredContent"]
    esperado_sin_tiempo = {k: v for k, v in esperado.items() if k != "milisegundos"}
    for salto in ("\n", "\r\n"):
        envuelto = salto.join(plano[i:i + 76] for i in range(0, len(plano), 76))
        obtenido = _llamar(envuelto)["result"]["structuredContent"]
        obtenido_sin_tiempo = {k: v for k, v in obtenido.items() if k != "milisegundos"}
        assert obtenido_sin_tiempo == esperado_sin_tiempo


def test_el_codigo_de_error_es_el_SEGUNDO_campo_del_texto(dicom_menor):
    """El SDK antepone su propio prefijo. Partir por el primer ':' devuelve
    'Error executing tool clasificar_radiografia', no el codigo.

    Se afirma la POSICION exacta, no solo que el codigo aparezca en algun
    sitio: tras partir el texto por ':', 'fuera_de_alcance' tiene que estar
    en el indice 1. Si el SDK metiera un campo extra delante, una asercion
    mas debil (solo "esta en el texto" y "no es el primer campo") seguiria
    pasando mientras que el flujo de n8n, que parte por el segundo ':' a
    ciegas, se rompería.
    """
    r = _llamar(base64.b64encode(dicom_menor).decode())["result"]
    assert r["isError"] is True
    texto = r["content"][0]["text"]
    partes = texto.split(":")
    assert partes[1].strip() == "fuera_de_alcance", texto


def test_el_rechazo_por_edad_no_trae_ninguna_cifra_de_probabilidad(dicom_menor):
    """Restriccion global 7. Si un numero se colara junto al rechazo, alguien
    lo usaria.

    No se compara con la cadena literal "0." porque el propio mensaje de
    rechazo la contiene sin ser una probabilidad: "...valido entre 18 y
    100." incluye "0.". Lo que importa es que no aparezca un decimal con la
    forma de una probabilidad o de una razon de verosimilitud, es decir, con
    dos o mas digitos de parte fraccionaria.
    """
    r = _llamar(base64.b64encode(dicom_menor).decode())["result"]
    assert r.get("structuredContent") in (None, {})
    texto = r["content"][0]["text"]
    for clave in ("probabilidad", "razon_de_verosimilitud"):
        assert clave not in texto
    assert not re.search(r"\d\.\d{2,}", texto), texto


def test_el_base64_invalido_se_rechaza_y_no_se_ignora_en_silencio():
    r = _llamar("no-es-base64-*!")["result"]
    assert r["isError"] is True
    assert "base64_invalido" in r["content"][0]["text"]


def test_por_encima_del_limite_del_transporte_llega_un_413_y_no_un_SSE():
    """Hay DOS limites y no son el mismo (§10.4). Por encima de ~5,3 MiB el
    transporte corta ANTES del tool: la respuesta no es SSE, y buscar 'data: '
    en ella reventaria.
    """
    enorme = base64.b64encode(b"\x00" * (6 * 1024 * 1024)).decode()
    cuerpo = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "clasificar_radiografia",
                   "arguments": {"dicom_base64": enorme}}}).encode()
    pet = urllib.request.Request(
        f"{BASE}/mcp", data=cuerpo,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(pet, timeout=30)
    assert exc.value.code == 413


def test_la_razon_de_verosimilitud_es_float_positivo_dentro_del_rango_declarado(dicom_adulto):
    """NO ejercita el recorte de calibracion.py.

    Esta radiografia (una cualquiera con etiqueta positiva del CSV de
    prueba) da RV 19.24 -- lejisimos de los extremos. Para ejercitar el
    recorte de verdad hace falta una imagen cuya PROBABILIDAD CRUDA caiga
    fuera del rango ajustado de la curva, [0.000215, 0.996927]; hay unas 4
    asi entre las 3811 de prueba, pero encontrarlas exige inferir sobre el
    conjunto entero (minutos), y la cache que lo abarataria
    (pruebas/crudas_prueba.csv) todavia no existe -- la crea la Tarea 4, que
    es donde debe ir la prueba que si ejercita el recorte. Si alguien
    borrara el recorte de calibracion.py hoy, ESTA prueba seguiria pasando.

    Mientras tanto, aqui solo se afirma la invariante mas debil que se puede
    verificar sin mentir: la razon de verosimilitud llega, es un float,
    es estrictamente positiva, y cae dentro del rango que declara el spec.

    Cota superior: 77.33, no 77.32. El valor exacto medido con el
    calibrador desplegado es 77.32279909706551; el "77,32" del §10.5 del
    spec es un redondeo de lectura, y asertar `<= 77.32` fallaria contra el
    servidor real.
    """
    sc = _llamar(base64.b64encode(dicom_adulto).decode())["result"]["structuredContent"]
    rv = sc["razon_de_verosimilitud"]
    assert isinstance(rv, float)
    assert rv > 0
    assert 0.0163 <= rv <= 77.33
