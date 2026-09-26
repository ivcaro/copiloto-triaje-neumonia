# tests/test_contrato_mcp.py
"""Lo que el bot de SP3 espera de copiloto-mcp.

Estas pruebas no comprueban el modelo: comprueban el CONTRATO. Si SP4 cambia
la forma de la respuesta, falla aqui en vez de romperse el bot en produccion.

NECESITAN EL SERVIDOR VIVO, y sin el **se saltan** en vez de fallar. En esta
rama se ha dicho varias veces que un skip se ve verde, y es cierto; la
diferencia esta en el mensaje. Un `ConnectionRefusedError` repetido diez veces
no informa de nada y entrena a no mirar los fallos -que es lo contrario de lo
que queremos, porque el dia que una de estas diez se rompa de verdad hay que
verla-. El skip de `copiloto_vivo` dice las dos cosas que hacen falta: QUE se
ha quedado sin verificar y COMO verificarlo. Se leen con `pytest -rs`.
"""
import base64
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

import pytest

BASE = os.environ.get("COPILOTO_URL", "http://127.0.0.1:18000")
CRUDO = pathlib.Path(
    r"C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\crudo\stage_2_train_images")

# Rango en el que esta ajustada la curva isotonica del calibrador desplegado
# (ver src/copiloto_triaje/servicio/calibracion.py). OJO -- premisa falsa que
# sobrevivio a dos rondas de revision: el recorte NO actua solo fuera de este
# rango. `Calibrador.calibrar` recorta siempre que la probabilidad
# INTERPOLADA cae por debajo de `probabilidad_minima_sostenida` o por encima
# de `probabilidad_maxima_sostenida`, y eso pasa tanto fuera de este rango
# como DENTRO de su primer y ultimo tramo (la curva interpola de `y[0]=0,0` a
# `y[1]=0,004608...`, y todo ese tramo queda por debajo del minimo sostenido
# sin salirse del rango). Medido sobre las 3 811 radiografias de prueba: 339
# recortadas por abajo y 14 por arriba (cache `pruebas/crudas_prueba.csv`),
# no las 4 y 1 que caen literalmente fuera de [RANGO_AJUSTADO_MIN,
# RANGO_AJUSTADO_MAX] -- esas cifras cambian si se reentrena el modelo.
#
# Las cotas exactas se miden una vez con el calibrador real y se afirman como
# literales: si el modelo se reentrena y el calibrador cambia, esta prueba
# debe volver a medirlas, no recalcularlas por su cuenta -- afirmar un numero
# que la propia prueba recalcula no prueba nada.
RANGO_AJUSTADO_MIN = 0.000215
RANGO_AJUSTADO_MAX = 0.996927
COTA_INFERIOR_RV = 0.016271632806621517
COTA_SUPERIOR_RV = 77.32279909706551
# Margen de coma flotante entre lo que esta prueba afirma y el float64 que
# viaja por el JSON del servidor -- no un literal redondeado a mano como el
# `0.0163` que causaba que la prueba declarara invalidos datos validos (era
# MAYOR que COTA_INFERIOR_RV).
TOLERANCIA_RV = 1e-9


# `127.0.0.1:` delante del puerto, y no `-p 18000:8000` a secas: asi el
# contenedor de prueba solo escucha en el loopback. Con la forma corta, en el
# VPS queda un endpoint de inferencia SIN AUTENTICACION abierto a los 24
# contenedores que comparten la red, y el tunel SSH que usan las pruebas entra
# por el loopback igual. Este comando se imprime cuando las pruebas se saltan,
# asi que es el que la gente copia y pega.
ARRANCAR = ("docker run -d --rm --name copiloto-prueba "
            "-p 127.0.0.1:18000:8000 "
            "-e UMBRAL=0.4258 -e AUC_VALIDACION=0.8827 -e OMP_NUM_THREADS=2 "
            "copiloto-mcp:0.1.0")


@pytest.fixture(scope="module", autouse=True)
def copiloto_vivo():
    """Sondea `/salud` UNA vez y, si no responde, salta el modulo entero con un
    mensaje que dice que se queda sin verificar y como verificarlo.

    Va antes que los fijadores `dicom_*` a proposito -es `autouse`-: sin
    servidor no hace falta leer ni un manifiesto ni una radiografia.

    Las diez aserciones de abajo no cambian: lo unico que cambia es que la
    ausencia del contenedor se cuenta como «no verificado» y no como «roto».
    """
    try:
        with urllib.request.urlopen(f"{BASE}/salud", timeout=3) as r:
            estado = json.load(r).get("estado")
    except (OSError, ValueError) as e:
        pytest.skip(
            f"CONTRATO CON copiloto-mcp SIN VERIFICAR: {BASE}/salud no responde"
            f" ({type(e).__name__}). Se quedan sin comprobar la forma de"
            " `structuredContent` (§10.2), la posicion del codigo de error"
            " (§10.4 bis), los dos limites de tamano (§10.4) y las cotas de la"
            " razon de verosimilitud (§10.5). Para verificarlo, levanta el"
            f" contenedor y repite:  {ARRANCAR}  -- o apunta COPILOTO_URL a uno"
            " que ya este vivo.")
    if estado != "listo":
        pytest.skip(
            f"CONTRATO CON copiloto-mcp SIN VERIFICAR: {BASE}/salud contesta"
            f" estado={estado!r} en lugar de 'listo', asi que el modelo no ha"
            " cargado y lo que fallara no es el contrato. Mira el log del"
            " contenedor y repite.")


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
    dos o mas digitos de parte fraccionaria -- con coma O con punto: la coma
    es el formato nativo de este proyecto (los documentos, los comentarios y
    los mensajes del bot escriben "0,8827"), y una regex que solo atrape el
    punto dejaria pasar una probabilidad en formato espanol.
    """
    r = _llamar(base64.b64encode(dicom_menor).decode())["result"]
    assert r.get("structuredContent") in (None, {})
    texto = r["content"][0]["text"]
    for clave in ("probabilidad", "razon_de_verosimilitud"):
        assert clave not in texto
    assert not re.search(r"\d[.,]\d{2,}", texto), texto


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
    prueba) da RV 19.24 -- lejisimos de los extremos. El recorte actua
    cuando la probabilidad interpolada cae por debajo de
    `probabilidad_minima_sostenida` o por encima de `probabilidad_maxima_sostenida`
    (no solo con la cruda fuera del rango ajustado: ver el comentario de
    cabecera de este fichero). Medido sobre las 3 811 radiografias de
    prueba, eso son 339 casos por abajo y 14 por arriba -- las pruebas que
    SI ejercitan el recorte, cuarenta lineas mas abajo en este mismo
    fichero, seleccionan de ese conjunto. Si alguien borrara el recorte de
    calibracion.py hoy, ESTA prueba seguiria pasando; esas otras dos
    fallarian.

    Mientras tanto, aqui solo se afirma la invariante mas debil que se puede
    verificar sin mentir: la razon de verosimilitud llega, es un float,
    es estrictamente positiva, y cae dentro de [COTA_INFERIOR_RV,
    COTA_SUPERIOR_RV] -- las mismas constantes que usan las pruebas fuertes,
    con un margen de coma flotante explicito (`TOLERANCIA_RV`), no un
    literal redondeado a mano: un `0.0163` redondeado hacia arriba queda por
    ENCIMA de `COTA_INFERIOR_RV` (0.016271632806621517) y declara invalidos
    datos que son validos -- exactamente lo que le pasaria a 339 de las
    3 811 radiografias de prueba si esta prueba se ejercitara con ellas.
    """
    sc = _llamar(base64.b64encode(dicom_adulto).decode())["result"]["structuredContent"]
    rv = sc["razon_de_verosimilitud"]
    assert isinstance(rv, float)
    assert rv > 0
    assert COTA_INFERIOR_RV - TOLERANCIA_RV <= rv <= COTA_SUPERIOR_RV + TOLERANCIA_RV


def _cache_puntuaciones():
    """La cache de pruebas/puntuaciones.py: cruda por cada radiografia de
    PRUEBA. La construye la Tarea 4; si no existe todavia, este import la
    genera (infiere sobre las 3 811 imagenes, tarda minutos la primera vez).
    """
    repo = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo))
    from pruebas.puntuaciones import puntuaciones_de_prueba  # noqa: E402
    return puntuaciones_de_prueba()


def _calibrador_desplegado():
    """El calibrador que sirve copiloto-mcp, leido (no mutado) para decidir
    QUE radiografias de PRUEBA recorta de verdad. Solo se usa para elegir el
    fixture barato y localmente: la razon de verosimilitud que estas pruebas
    AFIRMAN siempre viene de la llamada HTTP real a `_llamar()`, nunca de
    este calibrador local.
    """
    repo = pathlib.Path(__file__).resolve().parents[1]
    ruta_src = str(repo / "src")
    if ruta_src not in sys.path:
        sys.path.insert(0, ruta_src)
    from copiloto_triaje.servicio.calibracion import Calibrador  # noqa: E402
    return Calibrador.desde_json(repo / "servidor" / "calibrador.json")


@pytest.fixture(scope="module")
def dicom_recortada_por_abajo() -> bytes:
    """Una radiografia real cuya probabilidad CALIBRADA queda recortada a
    `probabilidad_minima_sostenida`: la condicion de VERDAD del recorte.

    NO es "cruda por debajo de RANGO_AJUSTADO_MIN" -- ese filtro deja fuera
    335 de las 339 radiografias que si se recortan, porque el primer tramo
    de la curva isotonica ya interpola por debajo del minimo sostenido antes
    de llegar al otro extremo del rango ajustado (ver el comentario de
    cabecera de este fichero). Filtrar por "fuera de rango" reduce el charco
    de 339 a 4 -- y el simetrico de arriba, de 14 a 1 -- lo que vacia este
    fixture en cuanto el reentrenamiento mueva una sola radiografia, y un
    fixture vacio hace `pytest.skip`, que se ve verde.
    """
    df = _cache_puntuaciones()
    cal = _calibrador_desplegado()
    calibrada = df.cruda.apply(cal.calibrar)
    candidatas = df[calibrada == cal.probabilidad_minima_sostenida].sort_values("patientId")
    if candidatas.empty:
        pytest.skip(
            "ninguna radiografia de PRUEBA recorta por abajo con el "
            "calibrador desplegado: el recorte inferior no seria alcanzable "
            "con datos reales -- hallazgo en si mismo")
    patient_id = candidatas.iloc[0].patientId
    return (CRUDO / f"{patient_id}.dcm").read_bytes()


@pytest.fixture(scope="module")
def dicom_recortada_por_arriba() -> bytes:
    """Simetrica a `dicom_recortada_por_abajo`, contra
    `probabilidad_maxima_sostenida`."""
    df = _cache_puntuaciones()
    cal = _calibrador_desplegado()
    calibrada = df.cruda.apply(cal.calibrar)
    candidatas = df[calibrada == cal.probabilidad_maxima_sostenida].sort_values("patientId")
    if candidatas.empty:
        pytest.skip(
            "ninguna radiografia de PRUEBA recorta por arriba con el "
            "calibrador desplegado: el recorte superior no seria alcanzable "
            "con datos reales -- hallazgo en si mismo")
    patient_id = candidatas.iloc[0].patientId
    return (CRUDO / f"{patient_id}.dcm").read_bytes()


def test_la_razon_de_verosimilitud_se_recorta_a_la_cota_inferior(
        dicom_recortada_por_abajo):
    """Esta SI ejercita el recorte de calibracion.py -- la prueba que el
    docstring de `test_la_razon_de_verosimilitud_es_float_positivo_dentro_del_rango_declarado`
    promete.

    `dicom_recortada_por_abajo` tiene una probabilidad CALIBRADA (antes del
    recorte) por debajo de `Calibrador.probabilidad_minima_sostenida`
    (0.004608294930875576); su cruda puede caer dentro o fuera del rango
    ajustado de la curva, da igual -- lo que importa es que la curva
    interpola por debajo de lo que los datos de validacion sostienen.

    Sin el recorte, ese numero interpolado se usaria tal cual para la razon
    de verosimilitud. En el caso mas extremo de ese conjunto -una cruda en
    el propio borde del dominio ajustado, `x[0] = 0.000215`- la
    interpolacion degenera: `np.interp` devuelve `y[0] = 0.0` exacto,
    entonces `p/(1-p) = 0` y la RV sale **0.0** -- certeza fabricada de
    ausencia que ningun dato sostiene. Medido leyendo `calibracion.py` y
    `calibrador.json` sin mutar el fichero (`np.interp` directo sobre
    `cal.x, cal.y`, sin pasar por el recorte de `Calibrador.calibrar`). Las
    cifras "3,5e-06 / 3,5e+06" que circulaban en una version anterior de
    este comentario describen OTRO recorte, el de
    `MARGEN_CURVA_DEGENERADA = 1e-6` que ya no es el que usa
    `Calibrador.calibrar` hoy.

    CON el recorte, sale EXACTAMENTE la cota que fija
    `Calibrador.probabilidad_minima_sostenida`. Si alguien borrara el
    recorte hoy, esta prueba fallaria; la debil de arriba seguiria pasando.
    """
    sc = _llamar(base64.b64encode(dicom_recortada_por_abajo).decode())[
        "result"]["structuredContent"]
    assert sc["razon_de_verosimilitud"] == COTA_INFERIOR_RV


def test_la_razon_de_verosimilitud_se_recorta_a_la_cota_superior(
        dicom_recortada_por_arriba):
    """Simetrica a la anterior: `dicom_recortada_por_arriba` tiene una
    probabilidad CALIBRADA por ENCIMA de `probabilidad_maxima_sostenida`
    (0.9565217391304348). En el caso mas extremo de ese conjunto -una cruda
    en `x[-1] = 0.996927`- la interpolacion sin recorte degenera a
    `y[-1] = 1.0` exacto, y `p/(1-p)` es entonces una division por cero real
    (`ZeroDivisionError`): certeza fabricada de presencia, y esta vez ni
    siquiera llega a ser un numero -el servidor reventaria-. Con el recorte,
    sale EXACTAMENTE `Calibrador.probabilidad_maxima_sostenida`.
    """
    sc = _llamar(base64.b64encode(dicom_recortada_por_arriba).decode())[
        "result"]["structuredContent"]
    assert sc["razon_de_verosimilitud"] == COTA_SUPERIOR_RV
