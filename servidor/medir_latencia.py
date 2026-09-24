# -*- coding: utf-8 -*-
"""Mide la latencia de las dos puertas DENTRO del contenedor.

Se mide aqui y no en la maquina de desarrollo porque el criterio de aceptacion
del hito H4 habla del servicio desplegado: el contenedor tiene otro limite de
memoria, otra CPU disponible y otro numero de hilos de torch que el portatil
donde se programo.

Uso (desde `servidor/`, con el contenedor ya arriba):

    docker compose cp <una-radiografia>.dcm copiloto-mcp:/modelo/ejemplo.dcm
    docker compose cp medir_latencia.py copiloto-mcp:/modelo/medir_latencia.py
    docker compose exec copiloto-mcp python /modelo/medir_latencia.py

La placa tiene que ser de un paciente de 18 a 100 anios: el servicio rechaza
las demas y el script moriria al imprimir la inferencia de muestra.
"""
import base64
import json
import statistics
import time
import urllib.request

PRESUPUESTO_SEGUNDOS = 4.0

datos = open("/modelo/ejemplo.dcm", "rb").read()
print(f"DICOM de prueba: {len(datos)} bytes")


def cronometrar(envio, repes=20):
    envio()  # una de calentamiento: la primera paga el arranque perezoso
    tiempos = []
    for _ in range(repes):
        t0 = time.perf_counter()
        envio()
        tiempos.append(time.perf_counter() - t0)
    return statistics.median(tiempos), max(tiempos)


def por_rest():
    frontera = "----x"
    cabecera = (f"--{frontera}\r\n"
                'Content-Disposition: form-data; name="archivo"; '
                'filename="a.dcm"\r\n'
                "Content-Type: application/octet-stream\r\n\r\n").encode()
    cuerpo = cabecera + datos + f"\r\n--{frontera}--\r\n".encode()
    pet = urllib.request.Request(
        "http://127.0.0.1:8000/inferir", data=cuerpo,
        headers={"Content-Type": f"multipart/form-data; boundary={frontera}"})
    return json.load(urllib.request.urlopen(pet))


def por_mcp():
    cuerpo = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "clasificar_radiografia",
                   "arguments": {"dicom_base64":
                                 base64.b64encode(datos).decode()}}}).encode()
    pet = urllib.request.Request(
        "http://127.0.0.1:8000/mcp", data=cuerpo,
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"})
    return urllib.request.urlopen(pet).read()


print("resultado de una inferencia:", json.dumps(por_rest(), indent=2))
for nombre, envio in (("REST", por_rest), ("MCP ", por_mcp)):
    mediana, peor = cronometrar(envio)
    print(f"{nombre}: mediana {mediana*1000:.0f} ms | peor {peor*1000:.0f} ms "
          f"| presupuesto {PRESUPUESTO_SEGUNDOS*1000:.0f} ms -> "
          f"{PRESUPUESTO_SEGUNDOS/mediana:.0f}x de margen")
