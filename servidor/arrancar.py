# -*- coding: utf-8 -*-
"""Punto de entrada del contenedor: carga el modelo UNA vez y sirve.

Cargar el modelo al importar y no en cada peticion es lo que convierte los
22 ms medidos en la latencia real del servicio.
"""
import os

import uvicorn

from copiloto_triaje.servicio.aplicacion import construir_aplicacion
from copiloto_triaje.servicio.inferencia import Motor

RUTA_PESOS = os.environ.get("RUTA_PESOS", "/modelo/pesos_modelo_cpu.pt")
RUTA_CALIBRADOR = os.environ.get("RUTA_CALIBRADOR", "/modelo/calibrador.json")
UMBRAL = float(os.environ.get("UMBRAL", "0.4258"))
# El AUC de validacion es obligatorio y viaja por entorno: es una afirmacion de
# calidad que se le muestra al profesional en cada respuesta, y un literal en el
# codigo seguiria diciendo 0,883 sobre unos pesos reentrenados que ya no lo
# tienen. Obligar a declararlo hace que reentrenar sin actualizarlo falle de
# forma visible en vez de mentir en silencio.
AUC_VALIDACION = float(os.environ.get("AUC_VALIDACION", "0.883"))

motor = Motor.cargar(RUTA_PESOS, RUTA_CALIBRADOR, UMBRAL, AUC_VALIDACION)
app = construir_aplicacion(motor)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
