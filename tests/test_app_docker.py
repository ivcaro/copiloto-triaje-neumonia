# -*- coding: utf-8 -*-
"""La imagen Docker de la interfaz (SP5-C1, spec §8 y §9): `app/Dockerfile`.

TRES CLASES DE PRUEBAS

Las ESTÁTICAS leen el Dockerfile, su fichero de exclusiones y el README, y corren siempre,
también en la imagen Linux de pruebas, que no tiene Docker. Fijan lo que no se ve al
ejecutar: que la base es la del servidor (la misma, por su digest), que las variables del
despliegue valen lo que en `servidor/docker-compose.yml`, que Streamlit arranca sin
telemetría, sin llamar a nadie y con su límite, que el contexto de la construcción es una
lista blanca POR RUTAS (de `app/`, lo que la app lee; de `src/`, solo los `.py`) y que la
orden documentada es la que se prueba (R19, R21 y R22).

La del CONTEXTO necesita Docker con BuildKit pero no la imagen: arma un árbol de juguete con
señuelos de lo que no puede viajar y le pide a BuildKit el contexto que recibiría (R19).

Las DE HUMO usan la imagen `copiloto-app` YA CONSTRUIDA (R20): construirla es instalar
torch, minutos y cientos de MB en cada corrida de la suite, y eso es trabajo del que
despliega, no de las pruebas. Arrancan contenedores de verdad, siempre con nombre propio y
borrados en un `finally`, y publicados SOLO en 127.0.0.1 (o sin red ninguna). Antes miran
que la imagen sea la de ESTE árbol: la huella (SHA-256, sin que importen los finales de
línea) de todo lo que la app lee, del calibrador y de los `.py` del paquete de `src/`, que
la imagen lleva instalado. Una imagen rancia pasaría todas las demás y no probaría nada.

Sin Docker, sin su demonio o sin la imagen, las que lo necesitan se SALTAN diciendo por qué
y con qué orden construir (desde la raíz del repositorio, con los pesos en
servidor/pesos_modelo_cpu.pt):

    docker build -t copiloto-app -f app/Dockerfile .

Lo que se queda sin comprobar entonces: que la imagen arranca, que su página responde, que
no llama a nadie al arrancar, que no corre como root, que lleva la configuración de
Streamlit, que no trae nada de lo que no debe viajar y que la app calcula un ejemplo sin
red con los pesos que lleva dentro. La imagen Linux de pruebas no tiene Docker: esas
pruebas se corren en la máquina que lo tiene (`python -m pytest tests/test_app_docker.py
-rs`). Un salto se ve verde: `-rs` los lista.

Los valores esperados están escritos aquí a mano o salen de los ficheros de despliegue (el
compose, el Dockerfile del servidor, `app/.streamlit/config.toml`) y del propio código de la
app (lo que lee), nunca del Dockerfile que se está probando: una constante equivocada no
puede dar por buena a la prueba que la comprueba.
"""
import ast
import contextlib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import time
import tomllib
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "app" / "app.py"
DOCKERFILE = REPO / "app" / "Dockerfile"
EXCLUSIONES = REPO / "app" / "Dockerfile.dockerignore"
DOCKERFILE_DEL_SERVIDOR = REPO / "servidor" / "Dockerfile"
COMPOSE = REPO / "servidor" / "docker-compose.yml"
PYPROJECT = REPO / "pyproject.toml"
CONFIG_DE_STREAMLIT = REPO / "app" / ".streamlit" / "config.toml"
README = REPO / "README.md"
CAPTURAS = REPO / "docs" / "interfaz"

IMAGEN = "copiloto-app"
PAQUETE = "copiloto_triaje"             # el paquete de `src/`, que la imagen instala
PUERTO = 8501
ORDEN_DE_CONSTRUIR = "docker build -t copiloto-app -f app/Dockerfile ."
# El límite de memoria de la orden que documenta el README: la red de debajo de la guarda
# que la app ya tiene en la cabecera del DICOM (el motor y el servidor no la tienen).
# `--memory-swap` igual a `--memory`: sin él, Docker deja usar otro tanto de swap.
LIMITE_DE_MEMORIA = ("--memory=2g", "--memory-swap=2g")

# Lo que la imagen copia del repositorio FUERA de `app/` (R19); de `src/`, solo sus `.py`
# (a cualquier profundidad): es lo que `pip install .` instala, y un `.pem`, unas
# credenciales o unas notas sueltas en `src/` no entran. Lo de `app/` se saca del código de
# la app (`_lo_que_la_app_lee`). Todo lo demás -`.git`, `.superpowers`, `pruebas/`
# (puntuaciones por placa y un corpus de RSNA), `docs/`, `tests/`, `notebooks/`, los
# `.env`, `n8n/valores.local.json`- no entra ni al contexto.
LO_QUE_LA_IMAGEN_COPIA_FUERA_DE_APP = ("pyproject.toml", "servidor/calibrador.json",
                                       "servidor/pesos_modelo_cpu.pt", "src/**/*.py")
LO_QUE_NO_DEBE_VIAJAR = (".git", ".superpowers", "pruebas", "docs", "tests",
                         "notebooks", "scripts", "bd", "n8n", ".env",
                         "valores.local.json", "app/assets/originales")


# --------------------------------------------------------------------------
# Leer un Dockerfile, su fichero de exclusiones y el código de la app
# --------------------------------------------------------------------------
def _leer(ruta: Path) -> str:
    assert ruta.is_file(), f"falta {ruta.relative_to(REPO).as_posix()}"
    return ruta.read_text(encoding="utf-8")


def _instrucciones(ruta: Path) -> list[tuple[str, str]]:
    """Las instrucciones de un Dockerfile como (`FROM`, `resto`): sin comentarios ni
    líneas en blanco, y con las partidas por `\\` ya unidas."""
    instrucciones, pendiente = [], ""
    for cruda in _leer(ruta).splitlines():
        linea = cruda.strip()
        if not linea or linea.startswith("#"):
            continue
        if linea.endswith("\\"):
            pendiente += linea[:-1] + " "
            continue
        completa = " ".join((pendiente + linea).split())
        pendiente = ""
        palabra, _, resto = completa.partition(" ")
        instrucciones.append((palabra.upper(), resto))
    assert not pendiente, "el Dockerfile acaba con una instrucción partida"
    return instrucciones


def _de(ruta: Path, instruccion: str) -> list[str]:
    return [resto for palabra, resto in _instrucciones(ruta) if palabra == instruccion]


def _entorno(ruta: Path) -> dict[str, str]:
    """Las variables de las instrucciones `ENV` (`CLAVE=valor CLAVE=valor`)."""
    entorno = {}
    for resto in _de(ruta, "ENV"):
        for par in shlex.split(resto):
            clave, igual, valor = par.partition("=")
            assert igual, f"ENV sin `=` en {par!r}: usa la forma CLAVE=valor"
            entorno[clave] = valor
    return entorno


def _copias(ruta: Path) -> list[tuple[str, str]]:
    """(origen, destino) de cada `COPY` con un solo origen y sin `--from`."""
    copias = []
    for resto in _de(ruta, "COPY"):
        partes = [p for p in shlex.split(resto) if not p.startswith("--")]
        assert len(partes) == 2, f"un COPY con varios orígenes: {resto!r}"
        copias.append((partes[0].rstrip("/"), partes[1]))
    return copias


def _reglas(ruta: Path) -> list[str]:
    return [l.strip() for l in _leer(ruta).splitlines()
            if l.strip() and not l.strip().startswith("#")]


def _valor_del_compose(clave: str) -> str:
    encontrado = re.search(rf'^\s*{clave}:\s*"([0-9.]+)"', _leer(COMPOSE), re.MULTILINE)
    assert encontrado, f"servidor/docker-compose.yml no fija {clave}"
    return encontrado.group(1)


def _partes(nodo) -> list[str] | None:
    """`CARPETA_APP / "assets" / "x"` -> ["CARPETA_APP", "assets", "x"]; otra cosa, None."""
    if isinstance(nodo, ast.Name):
        return [nodo.id]
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return [nodo.value]
    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Div):
        izquierda, derecha = _partes(nodo.left), _partes(nodo.right)
        if izquierda and derecha:
            return izquierda + derecha
    return None


def _lo_que_la_app_lee() -> set[str]:
    """Las rutas, desde la raíz del repositorio, de lo que la imagen lleva de `app/`: lo
    que el código de la app construye desde su carpeta (`CARPETA_APP / "assets" / …`),
    cada ejemplo por su nombre (`EJEMPLOS`), el guion mismo, la configuración que
    Streamlit lee del directorio de trabajo y el `requirements.txt` que lee la
    construcción. Sacado del código de la app y no de una lista a mano: un fichero nuevo
    que la app lea hace fallar la prueba hasta que alguien lo readmite a propósito."""
    arbol = ast.parse(_leer(APP))
    de_la_app, ejemplos = {}, None
    for nodo in arbol.body:
        if not (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)):
            continue
        nombre = nodo.targets[0].id
        if nombre == "EJEMPLOS":
            ejemplos = list(ast.literal_eval(nodo.value))
            continue
        partes = _partes(nodo.value)
        if partes and partes[0] == "CARPETA_APP" and len(partes) > 1:
            de_la_app[nombre] = "app/" + "/".join(partes[1:])
    assert "CARPETA_EJEMPLOS" in de_la_app and ejemplos, (
        "app.py ya no define CARPETA_EJEMPLOS y EJEMPLOS como los leía esta prueba: "
        "ponla al día")
    carpeta = de_la_app.pop("CARPETA_EJEMPLOS")
    leidas = set(de_la_app.values()) | {f"{carpeta}/{clave}.dcm" for clave in ejemplos}
    return leidas | {"app/app.py", "app/.streamlit/config.toml", "app/requirements.txt"}


# --------------------------------------------------------------------------
# Las estáticas
# --------------------------------------------------------------------------
def test_el_fichero_de_exclusiones_lleva_el_nombre_que_docker_lee():
    """R19. El contexto de la construcción es la raíz del repositorio: ahí Docker solo
    lee un `.dockerignore` de la RAÍZ, o `<dockerfile>.dockerignore` junto al
    Dockerfile. Un `app/.dockerignore` se ignora en silencio, y el contexto entero
    -`pruebas/`, con puntuaciones por placa y un corpus de RSNA- viajaría al demonio."""
    assert EXCLUSIONES.is_file()
    assert not (REPO / "app" / ".dockerignore").exists(), (
        "Docker no lee app/.dockerignore con el contexto en la raíz: se llama "
        "app/Dockerfile.dockerignore")


def test_el_contexto_es_una_lista_blanca_por_rutas_y_es_la_de_lo_que_la_app_lee():
    """R19: se excluye todo y se readmite SOLO lo que la imagen copia, y de `app/`, solo
    lo que la app lee, fichero a fichero: una carpeta entera deja pasar lo que alguien
    suelta en ella para probar en local (un `.git`, un `.pem`, un CSV de pruebas)."""
    reglas = _reglas(EXCLUSIONES)
    assert reglas[0] == "*", "la primera regla tiene que excluirlo todo"
    readmitidas = [r[1:] for r in reglas if r.startswith("!")]
    esperadas = set(LO_QUE_LA_IMAGEN_COPIA_FUERA_DE_APP) | _lo_que_la_app_lee()
    assert sorted(readmitidas) == sorted(esperadas), (
        f"readmitidas de más: {sorted(set(readmitidas) - esperadas)}; "
        f"faltan: {sorted(esperadas - set(readmitidas))}")
    assert "app" not in readmitidas, "`app/` no se readmite entera"
    assert "src" not in readmitidas, "`src/` no se readmite entera: solo sus `.py`"
    for prohibido in LO_QUE_NO_DEBE_VIAJAR:
        assert prohibido not in readmitidas
    # Todo lo readmitido existe (menos los pesos, que no se versionan; y `src/**/*.py` es
    # un patrón, que tiene que casar con algo)...
    for ruta in readmitidas:
        if ruta == "servidor/pesos_modelo_cpu.pt":
            continue
        casan = list(REPO.glob(ruta)) if "*" in ruta else [REPO / ruta]
        assert casan and all(c.exists() for c in casan), f"se readmite {ruta}, que no existe"
    # ...y el Dockerfile y el contexto se corresponden: nada readmitido que ningún COPY
    # copie, y ningún COPY que no copie nada de lo readmitido.
    def bajo(ruta, base):
        return ruta == base or ruta.startswith(base + "/")
    origenes = {origen for origen, _ in _copias(DOCKERFILE)}
    for ruta in readmitidas:
        assert any(bajo(ruta, o) for o in origenes), f"ningún COPY copia {ruta}"
    for origen in origenes:
        assert any(bajo(r, origen) for r in readmitidas), f"el COPY de {origen} no copia nada"


def test_el_paquete_no_declara_datos_porque_de_src_solo_viajan_los_py():
    """De `src/` se readmiten solo los `.py`. Si el paquete declarara ficheros de datos
    (`package-data`, `data-files` o un `MANIFEST.in`), `pip install .` los esperaría y la
    imagen no los tendría: se construiría sin avisar y fallaría al usarlos. Hoy el paquete
    es solo código."""
    setuptools = tomllib.loads(_leer(PYPROJECT)).get("tool", {}).get("setuptools", {})
    for clave in ("package-data", "data-files"):
        assert clave not in setuptools, (
            f"pyproject.toml declara `{clave}`, y la imagen solo copia los `.py` de `src/`: "
            "readmite esos ficheros en app/Dockerfile.dockerignore")
    assert not (REPO / "MANIFEST.in").exists(), (
        "hay un MANIFEST.in, y la imagen solo copia los `.py` de `src/`")


def test_la_base_es_la_del_servidor_y_va_fijada_por_digest():
    """R21: la app es la puerta de evaluación del mismo motor, así que corre sobre la
    misma base que el servidor, la misma de verdad (su digest) y no la que la
    etiqueta `python:3.12-slim` sea dentro de un mes."""
    (base,) = _de(DOCKERFILE, "FROM")
    assert "@sha256:" in base, "la base tiene que ir fijada por su digest"
    assert base == _de(DOCKERFILE_DEL_SERVIDOR, "FROM")[0]


def test_torch_sale_del_indice_de_ruedas_para_cpu_como_en_el_servidor():
    """Sin él, `pip install torch` baja la compilación con CUDA: 2,5 GB para una
    demostración que no usa GPU."""
    del_servidor = _entorno(DOCKERFILE_DEL_SERVIDOR)
    de_la_app = _entorno(DOCKERFILE)
    for clave in ("PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL"):
        assert de_la_app[clave] == del_servidor[clave]
    assert de_la_app["PIP_INDEX_URL"] == "https://download.pytorch.org/whl/cpu"


def test_instala_las_dependencias_de_la_app_y_despues_el_paquete_sin_las_suyas():
    """Es la receta que `app/requirements.txt` documenta en su cabecera, en capas
    separadas (tocar `src/` no vuelve a bajar torch); el paquete se INSTALA, y no se
    mete por `PYTHONPATH`, que Streamlit vigila y recarga; y el árbol de la construcción
    (`src/`, `build/`) no se queda en la imagen, donde alguien lo tomaría por el código
    que corre."""
    ordenes = [o for o in _de(DOCKERFILE, "RUN") if "pip install" in o]
    assert len(ordenes) == 2, ordenes
    primera, segunda = ordenes
    assert "-r app/requirements.txt" in primera
    assert "--no-deps ." in segunda
    assert "rm -rf /app/src /app/build" in segunda
    assert all("--no-cache-dir" in o for o in ordenes)
    copias = _copias(DOCKERFILE)
    posicion = {origen: i for i, (origen, _) in enumerate(copias)}
    assert posicion["app/requirements.txt"] < posicion["src"]
    # Y la imagen no fija nada por su cuenta: las versiones viven en un solo sitio.
    assert not any("==" in orden for orden in ordenes)
    assert "PYTHONPATH" not in _entorno(DOCKERFILE)


def test_las_variables_del_despliegue_son_las_del_compose_del_servidor():
    """Spec §8: `UMBRAL`, `AUC_VALIDACION` y `PREVALENCIA_LOCAL` se fijan en la imagen
    con los mismos valores que el compose del servidor, y la app los enseña. Si el
    compose cambia, esta imagen no puede seguir diciendo la cifra vieja."""
    entorno = _entorno(DOCKERFILE)
    for clave in ("UMBRAL", "AUC_VALIDACION", "PREVALENCIA_LOCAL"):
        assert entorno[clave] == _valor_del_compose(clave), clave
    assert (entorno["UMBRAL"], entorno["AUC_VALIDACION"],
            entorno["PREVALENCIA_LOCAL"]) == ("0.4258", "0.8827", "0.1466")


def test_los_pesos_y_el_calibrador_van_dentro_de_la_imagen_y_la_app_los_encuentra():
    copias = dict(_copias(DOCKERFILE))
    entorno = _entorno(DOCKERFILE)
    assert copias["servidor/pesos_modelo_cpu.pt"] == entorno["RUTA_PESOS"]
    assert copias["servidor/calibrador.json"] == entorno["RUTA_CALIBRADOR"]
    assert entorno["RUTA_PESOS"] == "/modelo/pesos_modelo_cpu.pt"


def test_streamlit_arranca_sin_telemetria_con_su_limite_y_sin_llamar_a_nadie():
    """R22. Cada opción de la orden tiene su razón:

    `--browser.gatherUsageStats=false`: Streamlit manda estadísticas de uso por
        defecto, y una app que recibe radiografías no manda nada a nadie.
    `--logger.hideWelcomeMessage=true`: en modo headless Streamlit consulta su IP
        pública al arrancar para escribir una «External URL». Fijar la dirección a
        `0.0.0.0` NO lo evita en la versión fijada (la trata como no fijada: se
        comprobó en los registros del contenedor), y ocultar el mensaje, sí.
    `--server.address=0.0.0.0`: escucha en todas las interfaces del contenedor, que
        es lo que hace falta para que Docker publique el puerto.
    `--server.maxUploadSize=5`: el límite del servidor, también si alguien lanza la
        orden desde otro directorio y el `config.toml` no se lee.
    `--server.headless=true`: nadie abre un navegador dentro del contenedor.
    `--server.fileWatcherType=none`: en la imagen no hay nada que vigilar, y por defecto
        Streamlit vigila los ficheros y recarga los módulos que cambian.
    """
    (cmd,) = _de(DOCKERFILE, "CMD")
    orden = json.loads(cmd)
    assert orden[:3] == ["streamlit", "run", "app.py"]
    opciones = set(orden[3:])
    esperadas = {"--server.address=0.0.0.0", f"--server.port={PUERTO}",
                 "--server.headless=true", "--browser.gatherUsageStats=false",
                 "--server.maxUploadSize=5", "--logger.hideWelcomeMessage=true",
                 "--server.fileWatcherType=none"}
    assert esperadas <= opciones, esperadas - opciones
    assert _de(DOCKERFILE, "EXPOSE") == [str(PUERTO)]
    # El límite de la orden es el del fichero de configuración de la app.
    config = tomllib.loads(_leer(CONFIG_DE_STREAMLIT))
    assert f"--server.maxUploadSize={config['server']['maxUploadSize']}" in opciones


def test_la_imagen_no_corre_como_root():
    """Una imagen que recibe ficheros de fuera y los parsea (DICOM) no necesita ser
    root, y si un fallo de un parser da una ejecución, que sea la de un usuario sin
    nada. (Lo que dice la imagen construida, en `test_la_imagen_por_dentro_…`.)"""
    usuarios = _de(DOCKERFILE, "USER")
    assert usuarios, "falta `USER`: el contenedor correría como root"
    assert usuarios[-1] not in ("root", "0")


def test_el_readme_y_la_cabecera_de_la_app_lanzan_desde_app_y_no_desde_la_raiz():
    """Streamlit lee `.streamlit/config.toml` del directorio desde el que se LANZA, y
    desde la raíz del repositorio no hay ninguno: se pierden en silencio la telemetría
    apagada, los 5 MB de subida y las trazas ocultas en el navegador (medido). Sin
    Docker se lanza con `cd app` y `streamlit run app.py`, en el README y en la
    cabecera de `app/app.py`."""
    cabecera = ast.get_docstring(ast.parse(_leer(APP)))
    for donde, texto in (("la cabecera de app/app.py", cabecera), ("el README", _leer(README))):
        assert "streamlit run app.py" in texto, donde
        assert re.search(r"cd app\b", texto), donde
        assert "streamlit run app/app.py" not in texto, (
            f"{donde} manda a lanzar desde la raíz, donde no se lee .streamlit/config.toml")


def test_la_orden_que_documenta_el_readme_publica_solo_en_loopback_y_limita_la_memoria():
    """El README dice cómo arrancar la imagen, y esa orden es la que cuenta: el puerto
    SOLO en 127.0.0.1 (sin él, Docker lo publica en todas las interfaces y la página no
    pide contraseña) y el límite de memoria (LIMITE_DE_MEMORIA). Las pruebas de humo
    arrancan sus contenedores con ese mismo límite, así que lo que se documenta es lo que
    se ha probado."""
    ordenes = [l.strip() for l in _leer(README).splitlines()
               if l.strip().startswith("docker run")]
    assert ordenes, "el README no documenta ninguna orden `docker run`"
    for orden in ordenes:
        partes = shlex.split(orden)
        assert f"127.0.0.1:{PUERTO}:{PUERTO}" in partes, orden
        assert not any(p.startswith(("0.0.0.0:", f"{PUERTO}:")) for p in partes), orden
        for opcion in LIMITE_DE_MEMORIA:
            assert opcion in partes, f"a `{orden}` le falta {opcion}"
        assert partes[-1] == IMAGEN, orden


def test_las_capturas_del_readme_existen_y_no_sobra_ninguna():
    """Un enlace roto a una captura solo se ve al abrir el README en un navegador, y una
    captura declarada que el README no enseña es un binario de más."""
    enlaces = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", _leer(README))
    for enlace in enlaces:
        if "://" not in enlace:
            assert (REPO / enlace).is_file(), f"el README enseña {enlace}, que no existe"
    de_la_interfaz = {e for e in enlaces if e.startswith("docs/interfaz/")}
    assert de_la_interfaz, "el README no enseña ninguna captura de la interfaz"
    en_disco = {p.relative_to(REPO).as_posix() for p in CAPTURAS.glob("*.png")}
    assert de_la_interfaz == en_disco


# --------------------------------------------------------------------------
# Ayudas de Docker
# --------------------------------------------------------------------------
def _docker(*argumentos, timeout=60, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *argumentos], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, env=env)


def _sin_docker() -> str | None:
    """Por qué no se puede usar Docker (sin el binario, o con su demonio parado), o
    `None` si se puede."""
    if shutil.which("docker") is None:
        return "no hay `docker` en el PATH"
    try:
        r = _docker("version", "--format", "{{.Server.Version}}", timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Docker no contesta ({type(exc).__name__})"
    if r.returncode != 0:
        return "el demonio de Docker no responde (¿está arrancado?)"
    return None


# --------------------------------------------------------------------------
# El contexto de la construcción, con Docker pero sin la imagen
# --------------------------------------------------------------------------
# Un árbol de juguete con la forma del repositorio: lo que la imagen necesita (lo de
# `app/`, lo que la app lee) y SEÑUELOS de lo que no puede llegar al demonio, también dentro
# de `app/` y de `src/`, que son las carpetas donde se suelta algo para probar en local.
ENTRAN_FUERA_DE_APP = {
    "pyproject.toml", "src/paquete/__init__.py", "src/paquete/modulo.py",
    "src/paquete/subpaquete/__init__.py", "src/paquete/subpaquete/modulo.py",
    "servidor/pesos_modelo_cpu.pt", "servidor/calibrador.json",
}
NO_ENTRAN = {
    ".git/HEAD", ".gitignore", "README.md", ".env", ".superpowers/nota.md",
    "pruebas/corpus/placa.png", "pruebas/sesion/respuestas.csv", "docs/informe.md",
    "tests/test_algo.py", "notebooks/uno.ipynb", "scripts/uno.py", "bd/esquema.sql",
    "n8n/valores.local.json", "servidor/.env", "servidor/Dockerfile",
    "servidor/arrancar.py",
    # dentro de `app/`: lo conocido y lo inocente
    "app/.env", "app/.env.local", "app/produccion.env", "app/.streamlit/secrets.toml",
    "app/valores.local.json", "app/assets/originales/placa.png",
    "app/empaquetar_ejemplos.py", "app/generar_metricas.py", "app/Dockerfile",
    "app/Dockerfile.dockerignore",
    "app/.git/HEAD", "app/.envrc", "app/.streamlit/credentials.toml",
    "app/credentials.json", "app/clave.pem", "app/server.key",
    "app/datos_pacientes.csv", "app/notas.md", "app/secrets/token.txt",
    "app/assets/placa_rsna.png", "app/assets/ejemplos/otro.dcm",
    # dentro de `src/`, donde solo entran los `.py`: lo que alguien suelta para probar
    "src/paquete/clave.pem", "src/paquete/server.key", "src/paquete/credentials.json",
    "src/paquete/datos.csv", "src/paquete/secrets.toml", "src/notas.md",
    "src/paquete/subpaquete/notas.txt",
    "src/paquete/__pycache__/modulo.cpython-312.pyc", "src/paquete.egg-info/PKG-INFO",
    "src/paquete/.git/HEAD", "src/paquete/.env",
    # y los `.py` que hay DENTRO de carpetas que no entran nunca: la exclusión de la carpeta
    # sola no los alcanza (BuildKit, medido), y las reglas `/**` de
    # app/Dockerfile.dockerignore, sí
    "src/paquete/__pycache__/cache.py", "src/paquete.egg-info/setup.py",
    "src/otro/.git/gancho.py", "src/otro/.env/entorno.py",
}

SIN_VERIFICAR_EL_CONTEXTO = (
    "CONTEXTO DE LA CONSTRUCCIÓN SIN VERIFICAR: {motivo}. Arranca Docker (con BuildKit) "
    "y repite.")


def test_el_contexto_de_la_construccion_es_solo_la_lista_blanca(tmp_path):
    """R19, con BuildKit de verdad y no con una lectura del fichero: se arma un árbol
    con la forma del repositorio, con lo que la imagen necesita y con señuelos de
    todo lo que no puede llegar al demonio (`pruebas/`, `.git`, los `.env`, los
    `valores.local.json`, el `secrets.toml` de Streamlit, un `.pem`, unas credenciales o un
    CSV suelto en `app/` o en `src/`, y hasta un `.py` dentro de un `.git` o de un `.env`
    de `src/`), y se pide el contexto que recibiría la construcción: un Dockerfile de usar
    y tirar, `FROM scratch` + `COPY`, con una copia exacta de app/Dockerfile.dockerignore
    al lado, que es donde Docker la busca. `--output` vuelca el resultado a una carpeta,
    sin crear ninguna imagen. Con BuildKit puesto a la fuerza: el fichero de exclusiones
    de un Dockerfile concreto solo lo lee BuildKit (por defecto desde Docker 23); el
    constructor antiguo manda el contexto entero."""
    motivo = _sin_docker()
    if motivo:
        pytest.skip(SIN_VERIFICAR_EL_CONTEXTO.format(motivo=motivo))
    entran = ENTRAN_FUERA_DE_APP | _lo_que_la_app_lee()
    arbol = tmp_path / "arbol"
    for ruta in entran | NO_ENTRAN:
        destino = arbol / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("contenido\n", encoding="utf-8")
    construccion = tmp_path / "construccion"
    construccion.mkdir()
    (construccion / "Dockerfile.contexto").write_text("FROM scratch\nCOPY . /ctx\n",
                                                      encoding="utf-8")
    shutil.copyfile(EXCLUSIONES, construccion / "Dockerfile.contexto.dockerignore")
    salida = tmp_path / "salida"
    r = _docker("build", "--progress", "plain", "-f",
                str(construccion / "Dockerfile.contexto"), "--output",
                f"type=local,dest={salida}", str(arbol), timeout=180,
                env={**os.environ, "DOCKER_BUILDKIT": "1"})
    assert r.returncode == 0, f"la construcción de usar y tirar falló:\n{r.stderr}"
    llegaron = {p.relative_to(salida / "ctx").as_posix()
                for p in (salida / "ctx").rglob("*") if p.is_file()}
    assert llegaron == entran, (
        f"llegaron de más: {sorted(llegaron - entran)}; faltan: "
        f"{sorted(entran - llegaron)}")


# --------------------------------------------------------------------------
# Las de humo: la imagen construida, con Docker
# --------------------------------------------------------------------------
SIN_VERIFICAR = (
    "PRUEBA DE HUMO DE LA IMAGEN SIN VERIFICAR: {motivo}. Para correrla, construye la "
    "imagen (desde la raíz, con los pesos en servidor/pesos_modelo_cpu.pt): "
    + ORDEN_DE_CONSTRUIR)


def _huella(datos: bytes) -> str:
    """El SHA-256 de un fichero, sin que importen los finales de línea si es de texto (un
    Windows con `autocrlf` los cambia); uno binario -con algún NUL, como los DICOM de los
    ejemplos- va tal cual. Lo mismo que hace `GUION_DE_LA_HUELLA` dentro de la imagen."""
    if b"\0" not in datos:
        datos = datos.replace(b"\r\n", b"\n")
    return hashlib.sha256(datos).hexdigest()


# La huella de lo que la imagen lleva de este árbol: de cada fichero, su SHA-256 con la ruta
# que tiene en el repositorio. Corre DENTRO de la imagen: recibe pares `ruta en el
# repositorio=ruta en la imagen` (lo que la app lee y el calibrador) y recorre por su cuenta
# el paquete `copiloto_triaje` que `pip install` dejó instalado (en /app no queda `src/`: se
# borra). Es la `_huella` de arriba, escrita otra vez. Sin comillas dobles: el guion viaja
# como un argumento de `docker run`.
GUION_DE_LA_HUELLA = r"""
import hashlib, importlib.util, json, os, sys

def huella(ruta):
    with open(ruta, 'rb') as f:
        datos = f.read()
    if b'\0' not in datos:
        datos = datos.replace(b'\r\n', b'\n')
    return hashlib.sha256(datos).hexdigest()

huellas = {}
for par in sys.argv[1:]:
    en_el_repositorio, _, en_la_imagen = par.partition('=')
    if os.path.isfile(en_la_imagen):
        huellas[en_el_repositorio] = huella(en_la_imagen)
paquete = list(importlib.util.find_spec('copiloto_triaje').submodule_search_locations)[0]
for carpeta, subcarpetas, ficheros in os.walk(paquete):
    subcarpetas[:] = [s for s in subcarpetas if s != '__pycache__']
    for nombre in ficheros:
        if nombre.endswith('.py'):
            ruta = os.path.join(carpeta, nombre)
            relativa = os.path.relpath(ruta, os.path.dirname(paquete)).replace(os.sep, '/')
            huellas['src/' + relativa] = huella(ruta)
print(json.dumps(huellas))
"""


def _huellas_de_este_arbol() -> dict[str, str]:
    """Las huellas, por su ruta en el repositorio, de lo que la imagen tiene que llevar de
    este árbol y se puede comparar: todo lo que la app lee, el calibrador y los `.py` del
    paquete de `src/`. Los pesos no viajan en git y no entran; lo que cambiaría con otros
    pesos, `app/assets/metricas.json`, sí."""
    rutas = sorted(_lo_que_la_app_lee()) + ["servidor/calibrador.json"]
    huellas = {ruta: _huella((REPO / ruta).read_bytes()) for ruta in rutas}
    for fuente in sorted((REPO / "src" / PAQUETE).rglob("*.py")):
        if "__pycache__" not in fuente.parts:
            huellas[fuente.relative_to(REPO).as_posix()] = _huella(fuente.read_bytes())
    return huellas


def _huellas_de_la_imagen() -> dict[str, str]:
    """Las mismas huellas, de lo que lleva la imagen: lo de `app/` está en `/app/app`, el
    calibrador en `/modelo` y el paquete, instalado. Un fichero que falta en la imagen no
    sale en el resultado."""
    pares = [f"{ruta}=/app/{ruta}" for ruta in sorted(_lo_que_la_app_lee())]
    pares.append("servidor/calibrador.json=/modelo/calibrador.json")
    r = _docker("run", "--rm", "--pull", "never", IMAGEN, "python", "-c",
                GUION_DE_LA_HUELLA, *pares, timeout=120)
    if r.returncode != 0 or not r.stdout.strip():
        pytest.fail(f"no se pudo leer lo que lleva la imagen `{IMAGEN}`: "
                    f"{r.stderr.strip()[-300:]}. Reconstruye con: {ORDEN_DE_CONSTRUIR}",
                    pytrace=False)
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def imagen():
    """La imagen construida, de ESTE árbol, o un salto que dice por qué y cómo
    construirla. NO la construye (R20). Si la imagen existe pero lo que lleva no es lo de
    aquí -algún fichero que la app lee, el calibrador o algún `.py` del paquete-, FALLA y
    dice cuáles: una imagen rancia pasaría todo lo demás y no probaría nada."""
    motivo = _sin_docker()
    if motivo:
        pytest.skip(SIN_VERIFICAR.format(motivo=motivo))
    if _docker("image", "inspect", IMAGEN, timeout=30).returncode != 0:
        pytest.skip(SIN_VERIFICAR.format(motivo=f"no hay una imagen llamada `{IMAGEN}`"))
    aqui, alli = _huellas_de_este_arbol(), _huellas_de_la_imagen()
    if aqui != alli:
        distintos = sorted(r for r in aqui.keys() | alli.keys() if aqui.get(r) != alli.get(r))
        primeros = ", ".join(distintos[:6]) + (", …" if len(distintos) > 6 else "")
        pytest.fail(f"la imagen `{IMAGEN}` no es de este árbol: difieren {len(distintos)} "
                    f"de sus ficheros ({primeros}). Reconstruye con: {ORDEN_DE_CONSTRUIR}",
                    pytrace=False)
    return IMAGEN


def _para_mostrar(registros: str, lineas: int = 40) -> str:
    """El final de unos registros, para un mensaje de fallo, sin la línea de la «External
    URL»: lleva la IP pública de la máquina, y la salida de una prueba que falla acaba
    pegada en sitios."""
    utiles = [l for l in registros.splitlines() if "External URL" not in l]
    return "\n".join(utiles[-lineas:])


def _sin_consulta_de_ip(registros: str):
    """Streamlit, en modo headless, pregunta a un servicio de fuera por la IP pública de
    la máquina: si contesta, la escribe como «External URL»; si no (sin Internet), escribe
    «Did not auto detect external IP». Cualquiera de las dos es que preguntó. Fijar
    `--server.address=0.0.0.0` no lo evita (el comodín cuenta como no fijado): se comprobó
    con la imagen. El mensaje no vuelca los registros: llevarían esa IP."""
    for senal in ("External URL", "external IP"):
        if senal in registros:
            pytest.fail("Streamlit preguntó por la IP pública de la máquina al arrancar: "
                        f"en los registros sale «{senal}»", pytrace=False)


class Contenedor:
    def __init__(self, nombre):
        self.nombre, self.puerto = nombre, None

    def corre(self) -> bool:
        r = _docker("inspect", "-f", "{{.State.Running}}", self.nombre)
        return r.stdout.strip() == "true"

    def registros(self) -> str:
        r = _docker("logs", self.nombre)
        return r.stdout + r.stderr

    def ejecutar(self, *orden, timeout=300) -> str:
        r = _docker("exec", self.nombre, *orden, timeout=timeout)
        assert r.returncode == 0, (
            f"`{' '.join(orden[:3])}…` dentro del contenedor salió con "
            f"{r.returncode}:\n{r.stdout}{r.stderr}")
        return r.stdout

    def fallar_porque(self, motivo: str):
        pytest.fail(f"{motivo}; sus registros:\n{_para_mostrar(self.registros())}",
                    pytrace=False)


@contextlib.contextmanager
def _contenedor_en_marcha(*opciones):
    """Un contenedor de la imagen con nombre propio, que se borra SIEMPRE."""
    nombre = f"copiloto-app-prueba-{uuid.uuid4().hex[:8]}"
    try:
        # Sin `--rm`: si el arranque falla, los registros siguen ahí para leerlos.
        r = _docker("run", "-d", "--pull", "never", "--name", nombre, *opciones,
                    IMAGEN, timeout=120)
        if r.returncode != 0:
            pytest.fail(f"`docker run` falló: {r.stderr.strip()}", pytrace=False)
        yield Contenedor(nombre)
    finally:
        _docker("rm", "-f", nombre)


_SIN_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _pedir(puerto, ruta):
    """(código, cuerpo, cabeceras) de un GET a 127.0.0.1, sin pasar por ningún proxy."""
    try:
        with _SIN_PROXY.open(f"http://127.0.0.1:{puerto}{ruta}", timeout=5) as r:
            return r.status, r.read().decode("utf-8", "replace"), r.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), exc.headers


def _puerto_publicado(contenedor, segundos=20) -> int:
    """El puerto de 127.0.0.1 que Docker eligió para la app (`-p 127.0.0.1::8501`: lo
    elige él, y no hay carrera por un puerto «libre»). Y que sea SOLO el de 127.0.0.1."""
    limite = time.monotonic() + segundos
    while True:
        r = _docker("port", contenedor.nombre, f"{PUERTO}/tcp")
        publicados = r.stdout.strip().splitlines()
        if publicados:
            break
        if not contenedor.corre():
            contenedor.fallar_porque("el contenedor se detuvo nada más arrancar")
        if time.monotonic() > limite:
            contenedor.fallar_porque(f"Docker no publicó el puerto en {segundos} s")
        time.sleep(0.5)
    assert all(p.startswith("127.0.0.1:") for p in publicados), (
        f"el puerto no se publicó solo en 127.0.0.1: {publicados}")
    return int(publicados[0].rsplit(":", 1)[1])


def _esperar_a_la_salud(contenedor, segundos=90):
    limite = time.monotonic() + segundos
    ultimo = "sin respuesta"
    while time.monotonic() < limite:
        if not contenedor.corre():
            contenedor.fallar_porque("el contenedor se detuvo antes de responder")
        try:
            codigo, cuerpo, _ = _pedir(contenedor.puerto, "/_stcore/health")
            if codigo == 200 and cuerpo.strip() == "ok":
                return
            ultimo = f"{codigo} {cuerpo[:60]!r}"
        except OSError as exc:
            ultimo = type(exc).__name__
        time.sleep(1)
    contenedor.fallar_porque(f"/_stcore/health no dijo `ok` en {segundos} s "
                             f"(último: {ultimo})")


@pytest.fixture(scope="module")
def contenedor(imagen):
    """Un contenedor publicado SOLO en 127.0.0.1, con el límite de memoria que documenta
    el README, y ya sano."""
    with _contenedor_en_marcha("-p", f"127.0.0.1::{PUERTO}", *LIMITE_DE_MEMORIA) as c:
        c.puerto = _puerto_publicado(c)
        _esperar_a_la_salud(c)
        yield c


def test_la_salud_y_la_pagina_responden(contenedor):
    codigo, cuerpo, _ = _pedir(contenedor.puerto, "/_stcore/health")
    assert (codigo, cuerpo.strip()) == (200, "ok")
    codigo, cuerpo, cabeceras = _pedir(contenedor.puerto, "/")
    assert codigo == 200
    assert "text/html" in cabeceras.get("Content-Type", "")
    assert "<title>Streamlit</title>" in cuerpo


def test_el_arranque_no_llama_a_nadie(contenedor):
    """Una imagen que recibe radiografías no llama a nadie al arrancar (la consulta de
    la IP pública, en `_sin_consulta_de_ip`). Y no vigila ficheros: en un Docker sobre
    WSL, Streamlit lo anuncia con «Using poll-based file watching» (en otros sistemas no
    dice nada, y esto no prueba nada)."""
    registros = contenedor.registros()
    assert "0.0.0.0:8501" in registros, "Streamlit no llegó a arrancar su servidor"
    _sin_consulta_de_ip(registros)
    assert "Traceback" not in registros, _para_mostrar(registros)
    assert "file watching" not in registros, (
        "Streamlit vigila los ficheros: falta --server.fileWatcherType=none")


def test_la_configuracion_de_streamlit_se_aplica_en_la_imagen(contenedor):
    """Streamlit lee `.streamlit/config.toml` del directorio desde el que se LANZA, no
    del de `app.py`: la imagen lo lanza desde el de la app. Se pregunta a un Python
    nuevo del contenedor, que parte del mismo directorio de trabajo, qué valen en
    la práctica las opciones del fichero (`showErrorDetails`, `toolbarMode`…, que la
    orden no repite)."""
    del_fichero = tomllib.loads(_leer(CONFIG_DE_STREAMLIT))
    opciones = [f"{seccion}.{clave}" for seccion, claves in del_fichero.items()
                for clave in claves]
    assert len(opciones) >= 4
    salida = contenedor.ejecutar(
        "python", "-c",
        "import json, sys; from streamlit import config; "
        "print(json.dumps({o: config.get_option(o) for o in sys.argv[1:]}))",
        *opciones)
    efectivas = json.loads(salida.strip().splitlines()[-1])
    esperadas = {f"{s}.{c}": v for s, claves in del_fichero.items()
                 for c, v in claves.items()}
    assert efectivas == esperadas


def test_la_imagen_por_dentro_trae_lo_que_la_app_lee_y_nada_mas_y_no_corre_como_root(
        contenedor):
    """El resultado de R19 mirado desde dentro, en la imagen construida: de `app/`, justo
    lo que la app lee; en `/app`, solo `app/` (ni el repositorio, ni `src/` ni `build/`
    de la construcción); ningún `.env` ni `.git`; los pesos y el calibrador donde los
    busca la app; y un usuario que no es root."""
    uid = contenedor.ejecutar("id", "-u").strip()
    assert uid.isdigit() and int(uid) != 0, "el contenedor corre como root"
    assert contenedor.ejecutar("ls", "-A", "/app").split() == ["app"]
    ficheros = {l.removeprefix("/app/")
                for l in contenedor.ejecutar("find", "/app/app", "-type", "f").split()
                if "__pycache__" not in l}
    assert ficheros == _lo_que_la_app_lee()
    sospechosos = contenedor.ejecutar(
        "find", "/app", "/modelo", "/home", "(", "-name", ".env*", "-o", "-name",
        "*.env", "-o", "-name", "valores.local.json", "-o", "-name", ".git", ")")
    assert sospechosos.strip() == ""
    assert contenedor.ejecutar("ls", "/modelo").split() == [
        "calibrador.json", "pesos_modelo_cpu.pt"]


# Corre `app/app.py` en el contenedor, con el entorno que trae y sin ninguna red: abre la
# página y calcula el ejemplo normal con el botón «Prueba con ejemplo», como lo haría una
# persona. Sin comillas dobles ni acentos: el guion viaja como un argumento de
# `docker exec`.
GUION_DE_LA_APP = """
import json
from streamlit.testing.v1 import AppTest

at = AppTest.from_file('/app/app/app.py', default_timeout=240).run()
pestanas = len(at.tabs)
at.selectbox(key='ejemplo').set_value('normal_pa')
at.run()
at.button(key='probar_ejemplo').click().run()
try:
    ultimo = at.session_state['ultimo']
except Exception:
    ultimo = {}
r = ultimo.get('resultado') or {}
print(json.dumps({'excepciones': [str(e.value) for e in at.exception],
                  'errores': [str(e.value) for e in at.error],
                  'pestanas': pestanas,
                  'historial': [f['origen'] for f in at.session_state['historial']],
                  'clasificacion': r.get('clasificacion'),
                  'cruda': r.get('probabilidad_cruda'),
                  'umbral': r.get('umbral'),
                  'cribado': any('CRIBADO' in str(m.value) for m in at.markdown),
                  'mapa': ultimo.get('mapa') is not None}))
"""


def test_la_app_corre_sin_red_con_los_pesos_de_la_imagen(imagen):
    """Lo que `GET /` no dice: la página de Streamlit es la misma con o sin modelo,
    porque el guion de la app solo corre cuando alguien abre una sesión. Aquí corre,
    dentro de la imagen y en un contenedor SIN RED (no hay puerto que publicar: se le
    habla por `docker exec`): si necesitara algo de fuera para arrancar -bajar pesos,
    consultar una versión, mandar una estadística-, no arrancaría. Carga el modelo
    con los pesos y el entorno de la imagen, pinta sus pestañas, sin error, y CALCULA un
    ejemplo de verdad (el normal, con «Prueba con ejemplo»): el resultado, el cribado y el
    mapa de calor. La lista de lo que la app lee sale de su código y solo ve rutas
    escritas de una manera; lo que el cálculo del ejemplo necesite y no esté en la imagen
    -el propio ejemplo, por ejemplo- se vería aquí. Y como sin red la consulta de la IP
    pública FALLA y no sale «External URL», mira también la señal del fallo: es el único
    sitio donde la consulta se vería sin Internet."""
    with _contenedor_en_marcha("--network", "none", *LIMITE_DE_MEMORIA) as c:
        limite = time.monotonic() + 90
        while True:
            r = _docker("exec", c.nombre, "python", "-c",
                        "import urllib.request as u; "
                        f"print(u.urlopen('http://127.0.0.1:{PUERTO}/_stcore/health', "
                        "timeout=3).read().decode())")
            if r.returncode == 0 and r.stdout.strip() == "ok":
                break
            if not c.corre():
                c.fallar_porque("el contenedor sin red se detuvo antes de responder")
            if time.monotonic() > limite:
                c.fallar_porque("sin red, /_stcore/health no dijo `ok` en 90 s")
            time.sleep(1)
        salida = c.ejecutar("python", "-c", GUION_DE_LA_APP)
        resultado = json.loads(salida.strip().splitlines()[-1])
        # Las pestañas solo se pintan si el modelo cargó: sin él, la app dice el error
        # y se detiene antes.
        assert resultado["excepciones"] == [] and resultado["errores"] == [], resultado
        assert resultado["pestanas"] >= 1, resultado
        # Y el ejemplo se calculó de verdad, con los pesos de la imagen: sin el fichero del
        # ejemplo habría un error en pantalla, y sin el resultado, ninguna de estas cifras.
        # El umbral es el global de la imagen (UMBRAL, el del compose), a mano.
        assert resultado["historial"] == ["ejemplo: normal_pa"], resultado
        assert resultado["clasificacion"] in ("opacidad_probable",
                                              "sin_opacidad_probable"), resultado
        assert 0 < resultado["cruda"] < 1 and resultado["umbral"] == 0.4258, resultado
        assert resultado["cribado"], f"la página no enseña el cribado: {resultado}"
        assert resultado["mapa"], f"no hay mapa de calor: {resultado}"
        _sin_consulta_de_ip(c.registros())
