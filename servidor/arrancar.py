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
#
# Y por eso SIN default: un `os.environ.get(..., "0.883")` seria literalmente la
# mentira en silencio que las cinco lineas de arriba dicen evitar, solo que
# escrita una linea mas abajo. El compose ya declara la variable, asi que exigirla
# no rompe el despliegue; lo que rompe es un despliegue que se olvido de ponerla,
# que es exactamente cuando hay que enterarse.
if not os.environ.get("AUC_VALIDACION"):
    raise SystemExit(
        "Falta la variable de entorno AUC_VALIDACION. Es el AUC en validacion "
        "de LOS PESOS que se estan sirviendo y se le muestra al profesional en "
        "cada respuesta, asi que no tiene valor por defecto: uno silencioso "
        "sobreviviria a un reentrenamiento y seguiria citando la cifra vieja. "
        "Declarala en el docker-compose.yml (ya viene puesta) o pasala al "
        "arrancar, p. ej. AUC_VALIDACION=0.8827.")
AUC_VALIDACION = float(os.environ["AUC_VALIDACION"])

# La prevalencia previa de la combinacion bayesiana (SP4 §5), con la MISMA
# disciplina que AUC_VALIDACION y por la misma razon: es una cifra que acaba
# delante de un clinico en cada informe con combinacion, y un valor por defecto
# silencioso sobreviviria a un cambio de entorno sin que nadie lo mirara.
# Arranca en 0,1466 -134/914, la cohorte de derivacion de Heckerling- y se
# cambia en el compose, con su fuente al lado, cuando haya dato local.
if not os.environ.get("PREVALENCIA_LOCAL"):
    raise SystemExit(
        "Falta la variable de entorno PREVALENCIA_LOCAL. Es la probabilidad "
        "previa con la que se combina la regla clinica con la imagen y se le "
        "muestra al profesional en cada informe con combinacion, asi que no "
        "tiene valor por defecto. Declarala en el docker-compose.yml (ya "
        "viene puesta) o "
        "pasala al arrancar, p. ej. PREVALENCIA_LOCAL=0.1466.")
PREVALENCIA_LOCAL = float(os.environ["PREVALENCIA_LOCAL"])
if not 0.0 < PREVALENCIA_LOCAL < 1.0:
    raise SystemExit(
        f"PREVALENCIA_LOCAL vale {PREVALENCIA_LOCAL!r} y tiene que ser una "
        "probabilidad estrictamente entre 0 y 1 (p. ej. 0.1466).")


def _umbral_de_entorno(nombre):
    """El valor de la variable, que tiene que ser un numero estrictamente entre
    0 y 1. `nan` no cumple ninguna comparacion e `inf` no esta por debajo de 1:
    caen en la misma guarda que un 1,5. Un texto tambien, con su mensaje y no
    con el traceback de `float()`."""
    crudo = os.environ[nombre]
    try:
        valor = float(crudo)
    except ValueError:
        valor = float("nan")
    if not 0.0 < valor < 1.0:
        raise SystemExit(
            f"{nombre} vale {crudo!r} y tiene que ser un numero estrictamente "
            "entre 0 y 1.")
    return valor


# El umbral por vista (SP5-C1 §4): una mitigacion de equidad y, a diferencia de
# las dos anteriores, OPCIONAL y APAGADA por defecto: el compose no las define y
# encenderla lo decide la institucion. Las dos o ninguna: con una sola, una de
# las vistas se quedaria con el umbral global sin que nadie lo hubiera decidido.
# Una variable vacia cuenta como no definida, igual que en las obligatorias.
UMBRALES_POR_VISTA = None
if os.environ.get("UMBRAL_PA") or os.environ.get("UMBRAL_AP"):
    faltan = [n for n in ("UMBRAL_PA", "UMBRAL_AP") if not os.environ.get(n)]
    if faltan:
        raise SystemExit(
            "UMBRAL_PA y UMBRAL_AP van juntas: hacen falta las dos, o ninguna. "
            f"Falta {faltan[0]}. Sin ninguna, el umbral por vista queda "
            "apagado y toda placa se clasifica con UMBRAL.")
    UMBRALES_POR_VISTA = {"PA": _umbral_de_entorno("UMBRAL_PA"),
                          "AP": _umbral_de_entorno("UMBRAL_AP")}

motor = Motor.cargar(RUTA_PESOS, RUTA_CALIBRADOR, UMBRAL, AUC_VALIDACION,
                     PREVALENCIA_LOCAL, umbrales_por_vista=UMBRALES_POR_VISTA)
app = construir_aplicacion(motor)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
