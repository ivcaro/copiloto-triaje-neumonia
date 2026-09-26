"""Pruebas de las dos puertas.

Las de equivalencia son las que de verdad protegen: si MCP y REST divergen, el
respaldo comprometido en el cronograma deja de ser un respaldo y nadie se
entera hasta que hace falta. Hay DOS, y no una: la del camino bueno, que
compara el resultado, y la del camino de ERROR, que compara el codigo. La
segunda existe porque la divergencia se colo justo por ahi -MCP descartaba el
mensaje entero- sin que la primera se enterara.
"""
import base64
import contextlib
import json

import httpx
import numpy as np
import pytest
import starlette.datastructures
import torch

from copiloto_triaje.servicio.aplicacion import (
    MAXIMO_BYTES, MAXIMO_CUERPO_MCP, construir_aplicacion,
)
from copiloto_triaje.servicio.calibracion import ajustar_calibrador
from copiloto_triaje.servicio.inferencia import Motor

from test_dicom import crear_dicom

CABECERAS_MCP = {"Accept": "application/json, text/event-stream",
                 "Content-Type": "application/json"}

# El SDK antepone esto al mensaje de todo ToolError que sale de la herramienta.
PREFIJO_DEL_SDK = "Error executing tool clasificar_radiografia: "


@pytest.fixture
def motor():
    rng = np.random.default_rng(0)
    y = (rng.random(500) < 0.2215).astype(int)
    crudo = 1 / (1 + np.exp(-rng.normal(1.7 * y, 1.0)))

    class Trivial(torch.nn.Module):
        def forward(self, x):
            return x.mean(dim=(1, 2, 3)).view(-1, 1)

    return Motor(modelo=Trivial(),
                 calibrador=ajustar_calibrador(y, crudo, 0.2215, "prueba"),
                 umbral=0.5, tam_imagen=32, nombre_modelo="prueba",
                 auc_validacion=0.88, prevalencia_local=0.1466)


@contextlib.asynccontextmanager
async def cliente_de(motor):
    """httpx.ASGITransport NO dispara los eventos de lifespan, y el gestor de
    sesiones de MCP vive ahi. Se entra al contexto a mano; en produccion lo
    hace uvicorn.

    NO es un `pytest_asyncio.fixture`: el gestor de sesiones de MCP abre un
    `anyio.create_task_group()` dentro del lifespan, y esa clase de recurso
    solo se puede entrar Y salir desde la MISMA Task de asyncio. Un fixture
    con `yield` hace el setup y el teardown en dos llamadas separadas a
    `run_until_complete`, cada una con su propia Task nueva -eso vale para
    CUALQUIER version de pytest-asyncio, se comprobo con 1.4.0 y con 0.24.0-,
    y el teardown revienta con "Attempted to exit cancel scope in a different
    task than it was entered in". Entrando y saliendo dentro del mismo `test_`
    (una sola Task) el problema no existe."""
    app = construir_aplicacion(motor)
    transporte = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app), \
            httpx.AsyncClient(transport=transporte,
                              base_url="http://prueba", timeout=120) as c:
        yield c


async def _llamar_por_mcp(cliente, dicom, hallazgos=None) -> httpx.Response:
    """Llama a la herramienta por la puerta MCP. `dicom` son los bytes del
    fichero, o ya el texto base64 cuando la prueba quiere uno invalido.
    `hallazgos`, si se da, viaja como segundo argumento del tool (SP4)."""
    b64 = dicom if isinstance(dicom, str) else base64.b64encode(dicom).decode()
    argumentos = {"dicom_base64": b64}
    if hallazgos is not None:
        argumentos["hallazgos"] = hallazgos
    return await cliente.post(
        "/mcp", headers=CABECERAS_MCP,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "clasificar_radiografia",
                         "arguments": argumentos}})


def _carga_del_evento(texto: str) -> dict:
    """La respuesta puede venir como SSE; se queda con el JSON del evento."""
    for linea in texto.splitlines():
        if linea.startswith("data: "):
            texto = linea[6:]
            break
    return json.loads(texto)


def _extraer_resultado(respuesta: httpx.Response) -> dict:
    contenido = _carga_del_evento(respuesta.text)["result"]
    assert not contenido.get("isError"), contenido
    if "structuredContent" in contenido:
        return contenido["structuredContent"]
    return json.loads(contenido["content"][0]["text"])


def _texto_del_error_mcp(respuesta: httpx.Response) -> str:
    """El texto del fallo tal y como lo lee el cliente MCP.

    Que el cuerpo venga marcado con `isError` se comprueba AQUI: sin esa
    comprobacion, una prueba que solo busca el codigo dentro del texto podria
    pasar sobre un resultado bueno que por casualidad lo contuviera.
    """
    assert respuesta.status_code == 200, (respuesta.status_code, respuesta.text)
    resultado = _carga_del_evento(respuesta.text)["result"]
    assert resultado.get("isError") is True, resultado
    return resultado["content"][0]["text"]


def _codigo_del_error_mcp(respuesta: httpx.Response) -> str:
    """El codigo, aislado del texto que ve el cliente.

    NO vale partir por el PRIMER ":": el SDK antepone al mensaje del
    `ToolError` su propio "Error executing tool <nombre>: ", asi que el codigo
    es el primer campo DESPUES de ese prefijo. Que el prefijo este es parte de
    lo que se comprueba; si el SDK dejara de ponerlo, esta funcion debe fallar
    y no adivinar.
    """
    texto = _texto_del_error_mcp(respuesta)
    assert texto.startswith(PREFIJO_DEL_SDK), texto
    return texto[len(PREFIJO_DEL_SDK):].split(":", 1)[0]


@pytest.mark.asyncio
async def test_salud_responde_listo(motor):
    async with cliente_de(motor) as cliente:
        r = await cliente.get("/salud")
        assert r.status_code == 200
        assert r.json()["estado"] == "listo"


@pytest.mark.asyncio
async def test_salud_publica_la_prevalencia_local(motor):
    """Es la prueba de despliegue de SP4: un /salud sin esta clave es un
    contenedor anterior (tests/test_contrato_sp4.py se salta por esto)."""
    async with cliente_de(motor) as cliente:
        assert (await cliente.get("/salud")).json()["prevalencia_local"] == 0.1466


@pytest.mark.asyncio
async def test_rest_clasifica_un_dicom(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/inferir",
                               files={"archivo": ("a.dcm", ruta.read_bytes())})
        assert r.status_code == 200
        assert r.json()["edad_paciente"] == 54


@pytest.mark.asyncio
async def test_rest_devuelve_el_codigo_de_error_en_el_cuerpo(motor, tmp_path):
    ruta = tmp_path / "nino.dcm"
    crear_dicom(ruta, edad="012Y")
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/inferir",
                               files={"archivo": ("n.dcm", ruta.read_bytes())})
        assert r.status_code == 422
        assert r.json()["codigo"] == "fuera_de_alcance"


@pytest.mark.asyncio
async def test_las_dos_puertas_dan_lo_mismo(motor, tmp_path):
    """El criterio de aceptacion anadido en el spec. Sin esta prueba el
    respaldo puede divergir del camino principal."""
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    datos = ruta.read_bytes()

    async with cliente_de(motor) as cliente:
        por_rest = (await cliente.post(
            "/inferir", files={"archivo": ("a.dcm", datos)})).json()
        respuesta = await _llamar_por_mcp(cliente, datos)
        assert respuesta.status_code == 200
        por_mcp = _extraer_resultado(respuesta)

    # Los milisegundos difieren por construccion: se comparan los demas.
    sin_tiempo = lambda d: {k: v for k, v in d.items() if k != "milisegundos"}
    assert sin_tiempo(por_mcp) == sin_tiempo(por_rest)


@pytest.mark.asyncio
async def test_las_dos_puertas_dan_el_mismo_codigo_de_error(motor, tmp_path):
    """La hermana de la anterior, y la que faltaba.

    El mismo DICOM de un menor por las dos puertas tiene que dar el MISMO
    codigo. Con `ValueError` en la herramienta, esta puerta no daba ninguno:
    el SDK lo trataba como crash y el cliente recibia solo "Error executing
    tool clasificar_radiografia", identico para un menor de edad, para un
    base64 roto y para unos bytes que no son DICOM. La equivalencia del camino
    bueno seguia pasando y nadie lo noto.
    """
    ruta = tmp_path / "nino.dcm"
    crear_dicom(ruta, edad="012Y")
    datos = ruta.read_bytes()

    async with cliente_de(motor) as cliente:
        por_rest = await cliente.post("/inferir",
                                      files={"archivo": ("n.dcm", datos)})
        assert por_rest.status_code == 422
        codigo_por_mcp = _codigo_del_error_mcp(
            await _llamar_por_mcp(cliente, datos))

    assert codigo_por_mcp == por_rest.json()["codigo"] == "fuera_de_alcance"


@pytest.mark.asyncio
async def test_mcp_devuelve_el_codigo_fuera_de_alcance(motor, tmp_path):
    ruta = tmp_path / "nino.dcm"
    crear_dicom(ruta, edad="012Y")
    async with cliente_de(motor) as cliente:
        respuesta = await _llamar_por_mcp(cliente, ruta.read_bytes())
    assert _codigo_del_error_mcp(respuesta) == "fuera_de_alcance"


@pytest.mark.asyncio
async def test_mcp_devuelve_el_codigo_edad_desconocida(motor, tmp_path):
    ruta = tmp_path / "sin_edad.dcm"
    crear_dicom(ruta, edad="")
    async with cliente_de(motor) as cliente:
        respuesta = await _llamar_por_mcp(cliente, ruta.read_bytes())
    assert _codigo_del_error_mcp(respuesta) == "edad_desconocida"


@pytest.mark.asyncio
async def test_mcp_devuelve_el_codigo_dicom_invalido(motor):
    async with cliente_de(motor) as cliente:
        respuesta = await _llamar_por_mcp(cliente, b"esto no es un DICOM")
    assert _codigo_del_error_mcp(respuesta) == "dicom_invalido"


@pytest.mark.asyncio
async def test_mcp_acepta_el_base64_envuelto_en_lineas(motor, tmp_path):
    """El mismo DICOM con saltos de linea tiene que dar el mismo resultado.

    `base64.encodebytes` -y varias librerias por defecto, siguiendo el MIME de
    toda la vida- envuelve a 76 columnas. Con `validate=True` a secas esos
    saltos de linea daban `base64_invalido` por una radiografia perfectamente
    valida, que es el peor rechazo posible: el cliente no tiene forma de saber
    que el problema es el formato del sobre y no la placa.
    """
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    datos = ruta.read_bytes()
    de_una_linea = base64.b64encode(datos).decode()
    envuelto = base64.encodebytes(datos).decode()  # con \n cada 76 columnas
    assert "\n" in envuelto

    async with cliente_de(motor) as cliente:
        liso = _extraer_resultado(await _llamar_por_mcp(cliente, de_una_linea))
        con_saltos = _extraer_resultado(await _llamar_por_mcp(cliente, envuelto))

    sin_tiempo = lambda d: {k: v for k, v in d.items() if k != "milisegundos"}
    assert sin_tiempo(con_saltos) == sin_tiempo(liso)


@pytest.mark.asyncio
async def test_el_transporte_deja_llegar_el_base64_envuelto_del_tamano_maximo(
        motor):
    """Aceptar el base64 envuelto no puede quedar deshecho por el transporte.

    Los saltos de linea engordan el CUERPO un 1,3%, y el limite del transporte
    mide el cuerpo. Sin contarlos, un payload envuelto cerca del maximo moria en
    el 413 del transporte mientras el mismo payload en una sola linea llegaba
    hasta la comprobacion del tool: las dos puertas volvian a aceptar tamanios
    distintos, que es el fallo que MAXIMO_CUERPO_MCP existe para cerrar.

    Se comprueba con un payload que se pasa del maximo por 1 KiB: tiene que
    llegar a la comprobacion del TOOL -y traer su codigo- y no morir antes.

    Con LOS DOS saltos, y no solo con el que usa `base64.encodebytes`: el MIME
    canonico corta con CRLF, que escapado cuesta el doble que LF. Presupuestar
    solo LF dejaba abierta una banda residual de casi 85 KiB por la que el CRLF
    seguia muriendo en el transporte. Sin este caso, ese agujero no lo veia
    nadie.
    """
    excesivo = b"\x00" * (MAXIMO_BYTES + 1024)
    crudo = base64.b64encode(excesivo)
    for salto in (b"\n", b"\r\n"):
        envuelto = salto.join(
            crudo[i:i + 76] for i in range(0, len(crudo), 76)).decode()
        assert salto.decode() in envuelto
        # El tamano que mide el transporte es el del CUERPO, donde cada salto de
        # linea va escapado dentro de la cadena JSON: dos caracteres si es LF,
        # cuatro si es CRLF.
        cuerpo = len(json.dumps(envuelto))
        assert cuerpo < MAXIMO_CUERPO_MCP, (salto, cuerpo, MAXIMO_CUERPO_MCP)

        async with cliente_de(motor) as cliente:
            respuesta = await _llamar_por_mcp(cliente, envuelto)
        assert _codigo_del_error_mcp(respuesta) == "payload_excesivo", salto


@pytest.mark.asyncio
async def test_la_herramienta_mcp_devuelve_exactamente_las_claves_del_contrato(
        motor, tmp_path):
    """Las claves son el contrato que SP4 va a leer, asi que se fijan aqui.

    Ni una menos -SP4 se quedaria sin el campo y fallaria en produccion- ni una
    mas sin decidirlo: anadir una obliga a pasar por esta prueba y por el §9 de
    la guia de despliegue, en vez de que aparezca sola en la respuesta.
    """
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    async with cliente_de(motor) as cliente:
        salida = _extraer_resultado(
            await _llamar_por_mcp(cliente, ruta.read_bytes()))

    assert set(salida) == {
        "probabilidad_cruda", "probabilidad_calibrada",
        "razon_de_verosimilitud", "umbral", "clasificacion", "edad_paciente",
        "modelo", "auc_validacion", "milisegundos",
    }
    # Y `razon_de_verosimilitud` llega como numero, no como texto: SP4 la
    # multiplica por las odds de la regla clinica sin convertir nada.
    assert isinstance(salida["razon_de_verosimilitud"], float)
    assert isinstance(salida["edad_paciente"], int)
    assert isinstance(salida["clasificacion"], str)


@pytest.mark.asyncio
async def test_mcp_rechaza_un_base64_invalido(motor):
    """`validate=True` rechaza lo que no sea base64, y ese rechazo tiene que
    llegar al cliente con su codigo, no como un fallo generico."""
    async with cliente_de(motor) as cliente:
        respuesta = await _llamar_por_mcp(cliente,
                                          "@@@@ esto no es base64 @@@@")
    assert _codigo_del_error_mcp(respuesta) == "base64_invalido"


@pytest.mark.asyncio
async def test_mcp_rechaza_por_tamano_lo_que_el_transporte_deja_pasar(motor):
    """La comprobacion de tamano de la herramienta tiene que ser ALCANZABLE.

    Mientras el limite del transporte fue MAXIMO_BYTES, este payload -que
    decodificado se pasa del maximo por 1 KiB- moria en el 413 del middleware
    y la comprobacion de la herramienta era codigo muerto. Ahora el transporte
    admite el cuerpo en base64 y es la herramienta la que lo rechaza, con su
    codigo, sobre los bytes DECODIFICADOS: el mismo numero que aplica REST.
    """
    excesivo = b"\x00" * (MAXIMO_BYTES + 1024)
    assert len(base64.b64encode(excesivo)) < MAXIMO_CUERPO_MCP
    async with cliente_de(motor) as cliente:
        respuesta = await _llamar_por_mcp(cliente, excesivo)
    assert _codigo_del_error_mcp(respuesta) == "payload_excesivo"


@pytest.mark.asyncio
async def test_rest_rechaza_por_tamano_excesivo(motor):
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/inferir", files={
            "archivo": ("g.dcm", b"\x00" * (MAXIMO_BYTES + 1024))})
    assert r.status_code == 413
    assert r.json()["codigo"] == "payload_excesivo"


@pytest.mark.asyncio
async def test_rest_no_se_trae_a_memoria_mas_de_lo_que_admite(motor,
                                                              monkeypatch):
    """Que llegue el 413 no basta: con un `read()` sin limite el 413 tambien
    llegaba, pero despues de haberse traido el fichero entero -2 GB si eso es
    lo que subieron-. Se cuenta lo que la puerta lee de verdad."""
    leido = 0
    read_original = starlette.datastructures.UploadFile.read

    async def read_contado(self, size=-1):
        nonlocal leido
        trozo = await read_original(self, size)
        leido += len(trozo)
        return trozo

    monkeypatch.setattr(starlette.datastructures.UploadFile, "read",
                        read_contado)

    async with cliente_de(motor) as cliente:
        r = await cliente.post("/inferir", files={
            "archivo": ("g.dcm", b"\x00" * (MAXIMO_BYTES + 2 * 1024 * 1024))})
    assert r.status_code == 413
    assert r.json()["codigo"] == "payload_excesivo"
    assert leido <= MAXIMO_BYTES + 1, leido


@pytest.mark.asyncio
async def test_las_dos_puertas_aceptan_el_mismo_tamano(motor):
    """El umbral EFECTIVO tiene que ser el mismo por las dos puertas.

    4,5 MB estan por debajo de MAXIMO_BYTES, asi que ninguna de las dos puede
    rechazarlos por tamano: las dos deben llegar a mirar el contenido y
    quejarse de que no es un DICOM. Mientras el transporte de MCP midio 5 MiB
    sobre el cuerpo en BASE64 -unos 3,93 MB decodificados- este payload daba
    422 por REST (dicom_invalido, ya mirando el contenido) y 413 por MCP.
    """
    grande = b"\x01" * 4_500_000
    async with cliente_de(motor) as cliente:
        por_rest = await cliente.post("/inferir",
                                      files={"archivo": ("g.dcm", grande)})
        codigo_por_mcp = _codigo_del_error_mcp(
            await _llamar_por_mcp(cliente, grande))
    assert por_rest.status_code == 422
    assert codigo_por_mcp == por_rest.json()["codigo"] == "dicom_invalido"


@pytest.mark.asyncio
async def test_mcp_acepta_una_cabecera_host_de_otro_contenedor(motor):
    """Con el host por defecto (127.0.0.1) el transporte responde 421 Invalid
    Host header a cualquier peticion que no venga de localhost, y en Docker
    n8n llama por nombre de servicio. Verificado durante el diseño."""
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/mcp",
                               json={"jsonrpc": "2.0", "id": 1,
                                     "method": "tools/list"},
                               headers={"Host": "copiloto-mcp:8000",
                                        **CABECERAS_MCP})
        assert r.status_code == 200
        assert "clasificar_radiografia" in r.text


# Los cinco datos de SP4 §9.3. Con asma `no_se` salen DOS puntuaciones: 3 y 4.
HALLAZGOS = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
             "crepitantes": True, "murmullo_disminuido": False,
             "asma": "no_se"}
CONTRATO_SP3 = {"probabilidad_cruda", "probabilidad_calibrada",
                "razon_de_verosimilitud", "umbral", "clasificacion",
                "edad_paciente", "modelo", "auc_validacion", "milisegundos"}


@pytest.mark.asyncio
async def test_la_herramienta_mcp_con_hallazgos_anade_exactamente_una_clave(
        motor, tmp_path):
    """La hermana de `test_la_herramienta_mcp_devuelve_exactamente_las_claves_del_contrato`,
    que sigue afirmando el conjunto de SP3 SIN hallazgos (criterio 2)."""
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    async with cliente_de(motor) as cliente:
        salida = _extraer_resultado(
            await _llamar_por_mcp(cliente, ruta.read_bytes(), HALLAZGOS))
    assert set(salida) == CONTRATO_SP3 | {"combinacion"}
    c = salida["combinacion"]
    assert c["puntuacion"] == [3, 4]
    assert c["rv_imagen"] == salida["razon_de_verosimilitud"]
    assert c["prevalencia"] == 0.1466


@pytest.mark.asyncio
async def test_rest_acepta_los_hallazgos_como_json_en_el_formulario(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/inferir",
                               files={"archivo": ("a.dcm", ruta.read_bytes())},
                               data={"hallazgos": json.dumps(HALLAZGOS)})
    assert r.status_code == 200, r.text
    assert r.json()["combinacion"]["puntuacion"] == [3, 4]


@pytest.mark.asyncio
async def test_las_dos_puertas_dan_la_misma_combinacion(motor, tmp_path):
    """El respaldo REST tiene que decir lo mismo que MCP tambien en lo nuevo."""
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    datos = ruta.read_bytes()
    async with cliente_de(motor) as cliente:
        por_rest = (await cliente.post(
            "/inferir", files={"archivo": ("a.dcm", datos)},
            data={"hallazgos": json.dumps(HALLAZGOS)})).json()
        por_mcp = _extraer_resultado(await _llamar_por_mcp(cliente, datos, HALLAZGOS))
    sin_tiempo = lambda d: {k: v for k, v in d.items() if k != "milisegundos"}
    assert sin_tiempo(por_mcp) == sin_tiempo(por_rest)


@pytest.mark.asyncio
async def test_las_dos_puertas_rechazan_igual_unos_hallazgos_invalidos(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    datos = ruta.read_bytes()
    malos = {**HALLAZGOS, "asma": "quizas"}
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/inferir",
                               files={"archivo": ("a.dcm", datos)},
                               data={"hallazgos": json.dumps(malos)})
        assert r.status_code == 422
        assert r.json()["codigo"] == "hallazgos_invalidos"
        assert "asma" in r.json()["detalle"]
        respuesta = await _llamar_por_mcp(cliente, datos, malos)
    assert _codigo_del_error_mcp(respuesta) == "hallazgos_invalidos"


@pytest.mark.asyncio
async def test_rest_rechaza_unos_hallazgos_que_no_son_un_objeto_json(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    async with cliente_de(motor) as cliente:
        # El ultimo, anidado a 100 000 niveles: `json.loads` lanza
        # RecursionError, que no es ValueError, y antes salia un 500.
        for texto in ("{no es json", '"una cadena"', "[1, 2]", "[" * 100000):
            r = await cliente.post("/inferir",
                                   files={"archivo": ("a.dcm", ruta.read_bytes())},
                                   data={"hallazgos": texto})
            assert r.status_code == 422, texto[:40]
            assert r.json()["codigo"] == "hallazgos_invalidos", texto[:40]


@pytest.mark.asyncio
async def test_el_rechazo_por_edad_no_trae_combinacion_ni_por_mcp_ni_por_rest(motor, tmp_path):
    """Restriccion 9: ninguna rama de error emite una cifra, tampoco la
    nueva. Un menor con hallazgos perfectos recibe el rechazo de siempre."""
    ruta = tmp_path / "n.dcm"
    crear_dicom(ruta, edad="012Y")
    datos = ruta.read_bytes()
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/inferir", files={"archivo": ("n.dcm", datos)},
                               data={"hallazgos": json.dumps(HALLAZGOS)})
        assert r.status_code == 422 and r.json()["codigo"] == "fuera_de_alcance"
        assert "combinacion" not in r.text
        texto = _texto_del_error_mcp(await _llamar_por_mcp(cliente, datos, HALLAZGOS))
    assert "combinacion" not in texto and "fuera_de_alcance" in texto
