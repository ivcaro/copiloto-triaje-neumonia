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
import pathlib
import urllib.error
import urllib.request

import pytest

from copiloto_triaje.config import url_base_n8n


@pytest.fixture
def webhook_n8n():
    """POST a un webhook de n8n. Devuelve (codigo_http, texto).

    El `secreto` viaja en la cabecera `X-Telegram-Bot-Api-Secret-Token`, que es
    la que Telegram manda y la que los flujos de SP3 comprueban ANTES de mirar
    nada mas: el webhook es publico, asi que el `chat_id` del cuerpo lo aporta
    quien llama y no prueba nada por si solo.

    Sin `N8N_URL` la prueba que lo pide se salta: no hay n8n por defecto. Mal
    puesta, FALLA diciendo por que: un salto se ve verde, y quien la puso
    quiere correr las pruebas conducidas.
    """
    base = os.environ.get("N8N_URL", "").strip()
    if not base:
        pytest.skip(
            "sin N8N_URL no se sabe a qué n8n hablar: las pruebas conducidas "
            "de los dos bots se quedan sin correr. Para correrlas, pon en "
            "N8N_URL la URL base del n8n que los sirve, además de los secretos "
            "de cada prueba")
    try:
        base = url_base_n8n(base)
    except ValueError as e:
        # el motivo, y no el valor: la salida de las pruebas tambien se publica
        pytest.fail(
            f"N8N_URL está mal puesta ({e}): las pruebas conducidas no se "
            "pueden correr contra ella. Pon en N8N_URL solo la URL base del "
            "n8n que sirve a los dos bots (por ejemplo "
            "https://n8n.ejemplo.test), o quítala para saltarlas",
            pytrace=False)

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


# --------------------------------------------------------------------------
# Lo que vive fuera del repositorio: el dataset de RSNA y los pesos desplegados
# --------------------------------------------------------------------------
def raiz_rsna_o_salta():
    """La raiz del dataset preparado (`RSNA_RAIZ`), o un skip que dice que se
    queda sin verificar y como verificarlo.

    No hay valor por defecto (spec de SP5 §6.1): una ruta por defecto seria la
    de una maquina concreta. La variable la lee `copiloto_triaje.config`, el
    unico lector que hay; aqui solo se convierte su `SystemExit` en un skip.
    Si la variable esta puesta pero la carpeta no tiene el dataset, NO se
    salta: las pruebas fallan con la ruta que no encuentran, que es lo que
    hace falta ver cuando la variable esta mal escrita.
    """
    from copiloto_triaje.config import raiz_rsna
    try:
        return raiz_rsna()
    except SystemExit:
        pytest.skip(
            "PRUEBAS CON RADIOGRAFÍAS REALES SIN VERIFICAR: falta RSNA_RAIZ, la"
            " raíz del dataset de RSNA preparado, que no tiene valor por"
            " defecto. Se quedan sin comprobar la selección de casos sobre los"
            " ficheros reales, el contrato con copiloto-mcp cuando recibe un"
            " DICOM y las consultas conducidas del bot del profesional que"
            " suben una placa. Para verificarlo, define RSNA_RAIZ con la"
            " carpeta que tiene dentro manifiestos/, png/ y"
            " crudo/stage_2_train_images/, y repite.")


def pesos_desplegados_o_salta():
    """La ruta de los pesos desplegados, o un skip si el fichero no esta.

    Los pesos no se versionan (16 MB binarios; `.gitignore`), y sin ellos no
    se puede ni inferir ni saber si la cache de puntuaciones es la del modelo
    desplegado: `pruebas/puntuaciones.py` compara su sha256 con el guardado.
    """
    import pathlib
    import sys
    repo = str(pathlib.Path(__file__).resolve().parents[1])
    if repo not in sys.path:
        sys.path.insert(0, repo)
    from pruebas import puntuaciones
    if not puntuaciones.PESOS.is_file():
        pytest.skip(
            "PRUEBAS CON LAS PUNTUACIONES DEL MODELO SIN VERIFICAR: faltan los"
            " pesos desplegados, servidor/pesos_modelo_cpu.pt, que no se"
            " versionan. Sin ellos no se puede inferir ni validar la caché de"
            " puntuaciones del conjunto de prueba, así que se quedan sin"
            " comprobar la selección de casos, las dos pruebas del recorte de"
            " la razón de verosimilitud y las consultas conducidas del bot del"
            " profesional que suben una placa. Para verificarlo, copia los"
            " pesos a esa ruta (se descargan: models/README.md; o salen del"
            " entrenamiento: docs/desarrollo.md, «Reproducir desde cero»)"
            " y repite; la primera vez, sin caché, infiere sobre"
            " las 3 811 imágenes de prueba y tarda minutos.")
    return puntuaciones.PESOS


@pytest.fixture(scope="module")
def rsna_raiz():
    """La raiz del dataset de RSNA. Sin `RSNA_RAIZ`, la prueba se salta."""
    return raiz_rsna_o_salta()


@pytest.fixture(scope="module")
def pesos_desplegados():
    """Los pesos desplegados. Sin el fichero, la prueba se salta."""
    return pesos_desplegados_o_salta()


# --------------------------------------------------------------------------
# Las tablas con una fila por paciente, que el repositorio publico no lleva
# --------------------------------------------------------------------------
# Decision del equipo (5-oct-2026, data/README.md): del conjunto de RSNA solo se
# publican agregados. Estos tres ficheros viven en el repositorio de desarrollo y
# `scripts/preparar_publicacion.py` los deja fuera de lo que se publica. Muchas
# pruebas las leen; en el repositorio publicado (o en una copia sin ellas) esas
# pruebas se SALTAN diciendo que se quedan sin comprobar, y no fallan.
_REPO = pathlib.Path(__file__).resolve().parents[1]
TABLAS_POR_PACIENTE = {
    "docs/eda/metadatos_eda.csv": (
        "la tabla de metadatos por placa del análisis exploratorio (26 684 filas)",
        "se regenera con scripts/extraer_metadatos.py desde los DICOM que cada uno descarga"),
    "docs/validacion-semisintetica/crudas_prueba.csv": (
        "la tabla de puntuaciones crudas congeladas de las 3 811 placas de prueba",
        "se regenera con los pesos y las placas de prueba (pruebas/puntuaciones.py)"),
    "docs/validacion-semisintetica/crudas_prueba.sha256": (
        "la huella que acompaña a las puntuaciones crudas congeladas",
        "sale de la misma regeneración de las puntuaciones (pruebas/puntuaciones.py)"),
}


def _motivo_de_la_tabla_ausente(ruta_relativa: str) -> str:
    que_es, como = TABLAS_POR_PACIENTE[ruta_relativa]
    return (
        f"PRUEBA SIN VERIFICAR: falta {ruta_relativa}, {que_es}, que el repositorio"
        " público no lleva (son tablas con una fila por paciente: decisión del equipo,"
        " 5-oct-2026, ver data/README.md). Lo que esta prueba comprueba se queda sin"
        " comprobar aquí; en el repositorio de desarrollo, que sí tiene la tabla, se"
        f" corre. Para tenerla: {como}.")


def tabla_por_paciente_o_salta(ruta_relativa: str):
    """La ruta de una tabla por paciente (relativa a la raiz del repo), o un skip
    que dice cual falta y que queda sin verificar."""
    ruta = _REPO / ruta_relativa
    if not ruta.is_file():
        pytest.skip(_motivo_de_la_tabla_ausente(ruta_relativa))
    return ruta


def _tabla_ausente_en(excepcion):
    """La tabla por paciente que falta y que causo `excepcion` (o alguna de sus
    causas), o None. Solo cuenta un `FileNotFoundError` cuyo fichero es EXACTAMENTE
    una de las tres tablas Y que de verdad no esta: un fallo cualquiera, o una
    tabla que esta pero que se lee mal, sigue siendo un fallo."""
    vistas = set()
    while excepcion is not None and id(excepcion) not in vistas:
        vistas.add(id(excepcion))
        if isinstance(excepcion, FileNotFoundError) and excepcion.filename:
            nombre = os.path.normcase(os.path.abspath(os.fsdecode(excepcion.filename)))
            for relativa in TABLAS_POR_PACIENTE:
                ruta = _REPO / relativa
                if os.path.normcase(os.path.abspath(ruta)) == nombre and not ruta.exists():
                    return relativa
        excepcion = excepcion.__cause__ or excepcion.__context__
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Una prueba (o un fijador) que revienta por leer una tabla por paciente que
    el repositorio publico no lleva se informa como SALTADA, con el motivo, y no
    como fallo ni error. No salta nada mas: cualquier otra excepcion, y cualquier
    otro fichero que falte, sigue siendo lo que es."""
    resultado = yield
    informe = resultado.get_result()
    if informe.passed or call.excinfo is None:
        return
    if isinstance(call.excinfo.value, pytest.skip.Exception):
        return
    relativa = _tabla_ausente_en(call.excinfo.value)
    if relativa is None:
        return
    archivo, linea, _ = item.location
    informe.outcome = "skipped"
    informe.longrepr = (str(archivo), (linea or 0) + 1,
                        "Skipped: " + _motivo_de_la_tabla_ausente(relativa))


# --------------------------------------------------------------------------
# Los espias de la regla de lo que el motor puede evaluar (SP5-B4)
# --------------------------------------------------------------------------
@pytest.fixture
def nadie_descodifica(monkeypatch):
    """Nadie descodifica un pixel: `Dataset.pixel_array` y, por debajo, el
    `DecodeRunner` por el que pasa toda descodificacion de pydicom 3, se apuntan
    y revientan EN EL ACTO, antes de reservar nada. Asi, si la regla dejara pasar
    una placa que declara 60 000 x 60 000, la prueba FALLA en vez de colgarse
    reservando 3,35 GiB. Devuelve la lista de intentos, que tiene que acabar
    vacia."""
    import pydicom.dataset
    from pydicom.pixels.decoders import base

    intentos = []

    def espia(nombre):
        def no_descodifiques(*args, **kwargs):
            intentos.append(nombre)
            raise AssertionError(f"no se tenia que descodificar ni un pixel ({nombre})")
        return no_descodifiques

    monkeypatch.setattr(pydicom.dataset.Dataset, "pixel_array",
                        property(espia("Dataset.pixel_array")))
    monkeypatch.setattr(base.DecodeRunner, "__init__", espia("DecodeRunner"))
    return intentos


@pytest.fixture
def nadie_infla(monkeypatch):
    """Nadie infla nada: `zlib.decompress` -con el que pydicom infla ENTERO un
    conjunto de datos «Deflated» en cuanto se le pide la cabecera- y
    `zlib.decompressobj` se apuntan y revientan en el acto. Devuelve la lista de
    intentos, que tiene que acabar vacia."""
    import zlib

    intentos = []

    def espia(nombre):
        def no_infles(*args, **kwargs):
            intentos.append(nombre)
            raise AssertionError(f"no se tenia que inflar nada ({nombre})")
        return no_infles

    monkeypatch.setattr(zlib, "decompress", espia("zlib.decompress"))
    monkeypatch.setattr(zlib, "decompressobj", espia("zlib.decompressobj"))
    return intentos
