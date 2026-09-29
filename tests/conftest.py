# -*- coding: utf-8 -*-
"""Fijadores compartidos de las pruebas de SP3.

`webhook_n8n` habla con un n8n REAL. Las pruebas que lo usan son de
integracion: mas lentas que las unitarias, y con efectos que se ven desde
fuera.

`webhook_n8n` SALTA SIN `N8N_URL`. La variable dice a que n8n se habla y no
tiene valor por defecto: el repositorio no lleva la URL de ningun despliegue,
asi que sin ella las pruebas conducidas se saltan, y lo dicen. Es la primera
guarda. La segunda son los `skipif` de cada clase de pruebas por sus SECRETOS
-`TELEGRAM_SECRET_PRUEBA`, `TELEGRAM_TOKEN_PROFESIONAL`,
`CHAT_SUBIDA_PLACAS`-: sin el secreto no se pasa la puerta del secret_token del
§4.2, asi que la peticion no llega a ningun sitio. El fijador `bd_sp3` de abajo
salta por `COPILOTO_BD_DSN`.

Las dos guardas hacen falta. En la maquina que SI tiene `N8N_URL` el fijador no
salta, y una prueba nueva que use `webhook_n8n` sin guardar su secreto mandaria
trafico a ese n8n cada vez que alguien corra la suite alli.
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

    Sin `N8N_URL` la prueba que lo pide se salta: no hay n8n por defecto.
    """
    base = os.environ.get("N8N_URL", "").strip().rstrip("/")
    if not base:
        pytest.skip(
            "sin N8N_URL no se sabe a qué n8n hablar: las pruebas conducidas "
            "de los dos bots se quedan sin correr. Para correrlas, pon en "
            "N8N_URL la URL base del n8n que los sirve, además de los secretos "
            "de cada prueba")

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


# --------------------------------------------------------------------------
# La simulacion semisintetica (SP5 §4.6): el script y una rejilla minima
# --------------------------------------------------------------------------
def _cargar_validar_combinacion():
    import importlib.util
    import pathlib
    ruta = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "validar_combinacion.py"
    spec = importlib.util.spec_from_file_location("validar_combinacion", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="session")
def validar():
    """`scripts/validar_combinacion.py` cargado como modulo."""
    return _cargar_validar_combinacion()


@pytest.fixture(scope="session")
def resultados_minimos(validar):
    """Una rejilla de 2 x 2 con 2 replicas, tal como quedaria en el JSON: las
    celdas 0A, (0; 0,3), (0,3; 0) y (0,3; 0,3); con intervalos y sensibilidad
    en 0A y en (0,3; 0,3)."""
    import json
    r = validar.calcular(replicas=2, procesos=1, rejilla=(0.0, 0.3),
                         destacadas=((0.3, 0.3),))
    return json.loads(json.dumps(r, ensure_ascii=False))
