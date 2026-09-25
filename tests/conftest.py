# -*- coding: utf-8 -*-
"""Fijadores compartidos de las pruebas de SP3.

`webhook_n8n` habla con un n8n REAL. Las pruebas que lo usan son de
integracion: mas lentas que las unitarias, y con efectos que se ven desde
fuera. Se saltan solas si `N8N_URL` no esta declarada, para que la suite del
paquete siga corriendo en una maquina sin acceso a n8n.
"""
import json
import os
import urllib.error
import urllib.request

import pytest


@pytest.fixture
def webhook_n8n():
    """POST a un webhook de n8n. Devuelve (codigo_http, texto).

    El `secreto` viaja en la cabecera `X-Telegram-Bot-Api-Secret-Token`, que es
    la que Telegram manda y la que los flujos de SP3 comprueban ANTES de mirar
    nada mas: el webhook es publico, asi que el `chat_id` del cuerpo lo aporta
    quien llama y no prueba nada por si solo.
    """
    base = os.environ.get("N8N_URL", "https://n8n.[retirado].com").rstrip("/")

    def enviar(ruta: str, cuerpo: dict, secreto: str | None = None):
        cabeceras = {"Content-Type": "application/json"}
        if secreto:
            cabeceras["X-Telegram-Bot-Api-Secret-Token"] = secreto
        pet = urllib.request.Request(
            f"{base}/webhook/{ruta}", data=json.dumps(cuerpo).encode(),
            headers=cabeceras)
        try:
            r = urllib.request.urlopen(pet, timeout=30)
            return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    return enviar


@pytest.fixture
def bd_sp3():
    """Conexion a la `copiloto-bd` que n8n ve, para afirmar sobre ella.

    `copiloto-bd` NO publica puertos -restriccion 5 del spec, y es correcta: en
    un VPS compartido con 24 contenedores ajenos, un puerto publicado es una
    puerta de mas-. n8n la alcanza porque comparte su red de docker; pytest,
    que corre fuera, llega por un **tunel SSH temporal**:

        ssh -N -L 15433:<ip-del-contenedor>:5432 usuario@vps

    El tunel funciona porque el HOST del VPS si alcanza las IPs de su red
    docker, aunque nadie de fuera pueda. Al cerrar la ventana desaparece y no
    deja rastro: no se publica nada ni se cambia el compose.

    El DSN llega por entorno y **nunca se escribe en el repositorio**. Usa el
    formato CLAVE-VALOR, no el de URL:

        COPILOTO_BD_DSN="host=127.0.0.1 port=15433 dbname=copiloto user=copiloto password=<contrasena>"

    El de URL -`postgresql://usuario:clave@host:puerto/base`- se rompe en
    cuanto la contrasena lleva `/`, `+`, `:` o `@`, que son separadores de la
    propia URL. Y las contrasenas generadas con `openssl rand -base64` llevan
    `/` y `+` casi siempre: lo que se ve entonces no es un error de
    autenticacion sino un `getaddrinfo failed`, porque el parser ha troceado el
    DSN por los sitios equivocados y acaba buscando un servidor que no existe.
    Costo dos intentos descubrirlo.

    Sin esa variable las pruebas que lo usan se saltan, para que la suite del
    paquete siga corriendo en una maquina sin tunel.
    """
    dsn = os.environ.get("COPILOTO_BD_DSN")
    if not dsn:
        pytest.skip("sin COPILOTO_BD_DSN: hace falta el tunel a copiloto-bd")
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as conexion:
        yield conexion
