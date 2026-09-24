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
                 auc_validacion=0.88)


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


async def _llamar_por_mcp(cliente, dicom) -> httpx.Response:
    """Llama a la herramienta por la puerta MCP. `dicom` son los bytes del
    fichero, o ya el texto base64 cuando la prueba quiere uno invalido."""
    b64 = dicom if isinstance(dicom, str) else base64.b64encode(dicom).decode()
    return await cliente.post(
        "/mcp", headers=CABECERAS_MCP,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": "clasificar_radiografia",
                         "arguments": {"dicom_base64": b64}}})


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
