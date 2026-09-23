"""Pruebas de las dos puertas.

La tercera es la que de verdad protege: si MCP y REST divergen, el respaldo
comprometido en el cronograma deja de ser un respaldo y nadie se entera hasta
que hace falta.
"""
import base64
import contextlib
import json

import httpx
import numpy as np
import pytest
import torch

from copiloto_triaje.servicio.aplicacion import construir_aplicacion
from copiloto_triaje.servicio.calibracion import ajustar_calibrador
from copiloto_triaje.servicio.inferencia import Motor

from test_dicom import crear_dicom


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
                              base_url="http://prueba") as c:
        yield c


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

        cuerpo = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": "clasificar_radiografia",
                             "arguments": {"dicom_base64":
                                           base64.b64encode(datos).decode()}}}
        r = await cliente.post("/mcp", json=cuerpo, headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"})
        assert r.status_code == 200
        por_mcp = _extraer_resultado(r.text)

    # Los milisegundos difieren por construccion: se comparan los demas.
    sin_tiempo = lambda d: {k: v for k, v in d.items() if k != "milisegundos"}
    assert sin_tiempo(por_mcp) == sin_tiempo(por_rest)


def _extraer_resultado(texto: str) -> dict:
    """La respuesta puede venir como SSE; se queda con el JSON del evento."""
    for linea in texto.splitlines():
        if linea.startswith("data: "):
            texto = linea[6:]
            break
    respuesta = json.loads(texto)
    contenido = respuesta["result"]
    if "structuredContent" in contenido:
        return contenido["structuredContent"]
    return json.loads(contenido["content"][0]["text"])


@pytest.mark.asyncio
async def test_mcp_acepta_una_cabecera_host_de_otro_contenedor(motor, tmp_path):
    """Con el host por defecto (127.0.0.1) el transporte responde 421 Invalid
    Host header a cualquier peticion que no venga de localhost, y en Docker
    n8n llama por nombre de servicio. Verificado durante el diseño."""
    async with cliente_de(motor) as cliente:
        r = await cliente.post("/mcp",
                               json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                               headers={"Host": "copiloto-mcp:8000",
                                        "Accept": "application/json, text/event-stream",
                                        "Content-Type": "application/json"})
        assert r.status_code == 200
        assert "clasificar_radiografia" in r.text
