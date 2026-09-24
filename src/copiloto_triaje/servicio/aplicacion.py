"""Las dos puertas del servicio, sobre el mismo nucleo.

MCP es lo comprometido en el hito H4; REST es la contingencia que el propio
cronograma previo por si n8n y MCP no se entendian. Las dos llaman a
`Motor.clasificar`, asi que no pueden divergir: ni en el resultado ni en el
camino de error, que es donde la divergencia pasa mas desapercibida.
"""
from __future__ import annotations

import base64

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from copiloto_triaje.servicio.inferencia import ErrorDeInferencia, Motor

MAXIMO_BYTES = 5 * 1024 * 1024

# Cuanto lee REST de golpe antes de volver a mirar el contador. Un solo
# `read()` sin limite se traeria a memoria el fichero entero -2 GB si eso es
# lo que subieron- para despues comparar su tamano con el maximo.
TROZO_BYTES = 1024 * 1024

# El limite del transporte de MCP NO es MAXIMO_BYTES, y el numero merece
# explicacion: el transporte mide el CUERPO HTTP, que lleva el DICOM ya
# convertido a base64, mientras que la comprobacion del tool y la de REST
# miden los bytes DECODIFICADOS. Con 5 MiB a secas en el transporte, las dos
# puertas aceptarian tamanos distintos: base64 gasta 4 caracteres por cada 3
# bytes, asi que 5 MiB de cuerpo son solo ~3,93 MB de DICOM, y un payload de
# 4,5 MB pasaba por REST y se estrellaba contra un 413 en MCP. Subiendo el
# limite del transporte a lo que ocupa en base64 un payload de MAXIMO_BYTES
# -mas un margen para el relleno, el sobre JSON-RPC y las cabeceras- el
# transporte deja pasar todo lo que decodificado quepa en MAXIMO_BYTES, y la
# comprobacion autoritativa pasa a ser la del tool sobre los bytes
# decodificados: el MISMO numero que aplica REST.
MARGEN_SOBRE_JSONRPC = 64 * 1024
MAXIMO_CUERPO_MCP = MAXIMO_BYTES * 4 // 3 + MARGEN_SOBRE_JSONRPC


def construir_aplicacion(motor: Motor, host_permitido: str = "0.0.0.0") -> FastAPI:
    """Monta MCP y REST en un solo proceso.

    `host_permitido` va a "0.0.0.0" y NO al 127.0.0.1 por defecto del SDK:
    el transporte valida la cabecera Host y con el valor por defecto responde
    421 "Invalid Host header" a todo lo que no venga de localhost. En Docker,
    n8n llama por nombre de servicio, asi que con el valor por defecto el
    despliegue falla entero. Comprobado durante el diseño.
    """
    servidor = MCPServer(name="copiloto-triaje", version="0.1.0",
                         instructions="Clasifica opacidad pulmonar en "
                                      "radiografia de torax de adultos.")

    @servidor.tool(
        name="clasificar_radiografia",
        description="Recibe una radiografia de torax en DICOM (base64) y "
                    "devuelve la evidencia de imagen: probabilidad calibrada "
                    "y razon de verosimilitud para combinar con la regla "
                    "clinica. Solo valida para pacientes de 18 a 100 anios.")
    def clasificar_radiografia(dicom_base64: str) -> dict:
        # Las tres ramas de fallo levantan ToolError y no ValueError: el SDK
        # documenta ToolError como "a failure you anticipated" y propaga su
        # texto al cliente, mientras que CUALQUIER otra excepcion la trata
        # como crash, la envuelve en UnexpectedToolError y DESCARTA el
        # mensaje. Con ValueError, un menor de edad, un base64 roto y unos
        # bytes que no son DICOM llegaban los tres como el mismo
        # "Error executing tool clasificar_radiografia", indistinguibles, y
        # esta puerta divergia entera de la REST justo en el camino de error.
        #
        # El codigo va delante y separado por ": " para que quien llame
        # parta por el primer ":" y no tenga que interpretar prosa.
        try:
            datos = base64.b64decode(dicom_base64, validate=True)
        except Exception as exc:
            raise ToolError(f"base64_invalido: {exc}") from exc
        if len(datos) > MAXIMO_BYTES:
            raise ToolError(
                f"payload_excesivo: {len(datos)} bytes, maximo {MAXIMO_BYTES}")
        try:
            return motor.clasificar(datos)
        except ErrorDeInferencia as exc:
            raise ToolError(f"{exc.codigo}: {exc}") from exc

    mcp_app = servidor.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        max_request_body_size=MAXIMO_CUERPO_MCP,
        host=host_permitido,
    )

    # El lifespan del app de MCP se cede al de FastAPI: montarlo sin esto deja
    # el gestor de sesiones sin arrancar y la herramienta falla con un
    # RuntimeError de grupo de tareas. Comprobado durante el diseño.
    api = FastAPI(title="copiloto-triaje", version="0.1.0",
                  lifespan=mcp_app.router.lifespan_context)

    @api.get("/salud")
    def salud() -> dict:
        return {"estado": "listo", "modelo": motor.nombre_modelo,
                "umbral": motor.umbral,
                "calibrador": motor.calibrador.procedencia}

    @api.post("/inferir")
    async def inferir(archivo: UploadFile = File(...)):
        # Se lee por trozos y se para en cuanto se pasa del maximo: con un
        # `await archivo.read()` sin limite, una subida de 2 GB se traia
        # entera a memoria para DESPUES comparar su tamano y contestar 413.
        # Por eso el detalle dice "mas de" y no la cifra exacta: el resto del
        # cuerpo no se lee a proposito, asi que el tamano real no se conoce.
        trozos: list[bytes] = []
        leidos = 0
        while leidos <= MAXIMO_BYTES:
            trozo = await archivo.read(min(TROZO_BYTES,
                                           MAXIMO_BYTES + 1 - leidos))
            if not trozo:
                break
            trozos.append(trozo)
            leidos += len(trozo)
        if leidos > MAXIMO_BYTES:
            return JSONResponse(status_code=413, content={
                "codigo": "payload_excesivo",
                "detalle": f"mas de {MAXIMO_BYTES} bytes"})
        datos = b"".join(trozos)
        try:
            return motor.clasificar(datos)
        except ErrorDeInferencia as exc:
            # 422 y no 400: la peticion esta bien formada, lo que no sirve es
            # su contenido para este modelo.
            return JSONResponse(status_code=422, content={
                "codigo": exc.codigo, "detalle": str(exc)})

    api.mount("/", mcp_app)
    return api
