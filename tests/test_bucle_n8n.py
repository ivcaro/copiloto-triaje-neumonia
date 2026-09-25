# -*- coding: utf-8 -*-
"""Prueba de que el bucle de pruebas del enfoque A existe de verdad.

Toda la estrategia de pruebas de SP3 se apoya en una suposicion que nadie
habia verificado: que pytest puede disparar el webhook de un workflow de n8n y
observar su efecto. Si no se puede, el enfoque A -toda la logica en workflows-
se queda sin red de seguridad, y eso hay que saberlo ANTES de construir los dos
bots, no despues.

Este fichero y el workflow desechable que lo acompana se BORRAN en cuanto la
respuesta sea si.

Por que la asercion va por la respuesta HTTP y no por la base de datos:
`copiloto-bd` no publica puertos -es la restriccion 5 del spec, y es correcta-,
asi que pytest, que corre en una maquina distinta, no la alcanza. n8n si, porque
comparte con ella la red de docker. De modo que el flujo escribe, relee, y
devuelve el conteo en su respuesta.

Eso basta para la pregunta que este fichero hace. NO basta para las tareas 5 y
6, que afirman sobre tablas con datos de pacientes: fiarse de lo que el propio
flujo informa sobre si mismo es lo contrario de una prueba. Donde corre pytest
para esas queda decidido aparte.
"""
import os

import pytest

RUTA = "copiloto-prueba-bucle"


@pytest.fixture(scope="module", autouse=True)
def exige_configuracion():
    if not os.environ.get("N8N_URL"):
        pytest.skip("sin N8N_URL: esta prueba habla con un n8n real")


def test_pytest_puede_conducir_un_workflow_de_n8n(webhook_n8n):
    """La pregunta entera, en una prueba.

    Se manda un POST al webhook con un identificador propio; el flujo lo
    escribe en `cuestionarios_iniciados` con una fecha centinela, lo relee, y
    devuelve el conteo. Si el numero sube, el bucle funciona: pytest dispara,
    n8n ejecuta, la base recibe, y la respuesta vuelve.
    """
    codigo, cuerpo = webhook_n8n(RUTA, {"origen": "pytest"})
    assert codigo == 200, f"el webhook no respondio 200: {codigo} {cuerpo[:200]}"

    import json
    datos = json.loads(cuerpo)
    if isinstance(datos, list):          # n8n devuelve una lista de items
        datos = datos[0]
    primero = int(datos["cuantos"])

    codigo, cuerpo = webhook_n8n(RUTA, {"origen": "pytest"})
    assert codigo == 200
    datos = json.loads(cuerpo)
    if isinstance(datos, list):
        datos = datos[0]
    segundo = int(datos["cuantos"])

    assert segundo == primero + 1, (
        f"el contador no subio: {primero} -> {segundo}. El workflow respondio "
        "pero no escribio, o escribio y no releyo.")


def test_el_workflow_alcanza_la_base_por_nombre_de_servicio(webhook_n8n):
    """Que el conteo sea un entero y no nulo demuestra que el nodo Postgres
    resolvio `copiloto-bd` por DNS de docker y se autentico.

    Es lo mismo que hara el flujo del paciente, y si fallara aqui fallaria alli
    con un mensaje mucho mas confuso, a mitad de una conversacion.
    """
    codigo, cuerpo = webhook_n8n(RUTA, {"origen": "pytest"})
    assert codigo == 200
    import json
    datos = json.loads(cuerpo)
    if isinstance(datos, list):
        datos = datos[0]
    assert isinstance(datos.get("cuantos"), (int, str)), datos
    assert int(datos["cuantos"]) > 0, datos


def test_lo_que_el_flujo_dice_coincide_con_lo_que_la_base_tiene(
        webhook_n8n, bd_sp3):
    """LA prueba de este fichero, y la razon de que el tunel merezca la pena.

    Las dos de arriba se fian de lo que el propio flujo informa sobre si mismo,
    que es lo contrario de una prueba: un workflow que devolviera un numero
    inventado las pasaria las dos. Esta va a la base por su cuenta y compara.

    Si esta pasa, el bucle del enfoque A esta demostrado de punta a punta -
    pytest dispara, n8n ejecuta, la base recibe, y pytest lo comprueba en la
    fuente- y las tareas 5 y 6 pueden afirmar sobre tablas de verdad en vez de
    sobre lo que el examinado cuenta de si mismo.
    """
    CENTINELA = "2000-01-01"
    antes = bd_sp3.execute(
        "SELECT coalesce(sum(cuantos), 0) FROM cuestionarios_iniciados"
        " WHERE dia = %s", (CENTINELA,)).fetchone()[0]

    codigo, cuerpo = webhook_n8n(RUTA, {"origen": "pytest"})
    assert codigo == 200, cuerpo[:200]

    import json
    datos = json.loads(cuerpo)
    if isinstance(datos, list):
        datos = datos[0]
    segun_el_flujo = int(datos["cuantos"])

    en_la_base = bd_sp3.execute(
        "SELECT coalesce(sum(cuantos), 0) FROM cuestionarios_iniciados"
        " WHERE dia = %s", (CENTINELA,)).fetchone()[0]

    assert en_la_base == antes + 1, (
        f"la base no registro la escritura: {antes} -> {en_la_base}")
    assert segun_el_flujo == en_la_base, (
        f"el flujo dijo {segun_el_flujo} y la base tiene {en_la_base}: "
        "el workflow esta informando algo distinto de lo que escribio")
