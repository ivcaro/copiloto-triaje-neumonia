"""Las dos puertas del servicio, sobre el mismo nucleo.

MCP es lo comprometido en el hito H4; REST es la contingencia que el propio
cronograma previo por si n8n y MCP no se entendian. Las dos llaman a
`Motor.clasificar`, asi que no pueden divergir.
"""
from __future__ import annotations

import base64

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from mcp.server.mcpserver import MCPServer

from copiloto_triaje.servicio.inferencia import ErrorDeInferencia, Motor

MAXIMO_BYTES = 5 * 1024 * 1024


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
        try:
            datos = base64.b64decode(dicom_base64, validate=True)
        except Exception as exc:
            raise ValueError(f"base64 invalido: {exc}") from exc
        if len(datos) > MAXIMO_BYTES:
            raise ValueError(
                f"payload_excesivo: {len(datos)} bytes, maximo {MAXIMO_BYTES}")
        try:
            return motor.clasificar(datos)
        except ErrorDeInferencia as exc:
            # El codigo viaja en el texto: MCP transporta el error como
            # mensaje, y quien llama necesita distinguir "fuera de alcance"
            # de "no es un DICOM" sin interpretar prosa.
            raise ValueError(f"{exc.codigo}: {exc}") from exc

    mcp_app = servidor.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        max_request_body_size=MAXIMO_BYTES,
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
        datos = await archivo.read()
        if len(datos) > MAXIMO_BYTES:
            return JSONResponse(status_code=413, content={
                "codigo": "payload_excesivo",
                "detalle": f"{len(datos)} bytes, maximo {MAXIMO_BYTES}"})
        try:
            return motor.clasificar(datos)
        except ErrorDeInferencia as exc:
            # 422 y no 400: la peticion esta bien formada, lo que no sirve es
            # su contenido para este modelo.
            return JSONResponse(status_code=422, content={
                "codigo": exc.codigo, "detalle": str(exc)})

    api.mount("/", mcp_app)
    return api
