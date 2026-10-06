# -*- coding: utf-8 -*-
"""La imagen Docker de la interfaz (SP5-C1, spec §8 y §9): `app/Dockerfile`.

TRES CLASES DE PRUEBAS

Las ESTÁTICAS leen el Dockerfile y su fichero de exclusiones, y corren siempre, también
en la imagen Linux de pruebas, que no tiene Docker. Fijan lo que no se ve al ejecutar: que
la base es la del servidor (la misma, por su digest), que las variables del despliegue
valen lo que en `servidor/docker-compose.yml`, que Streamlit arranca sin telemetría, sin
llamar a nadie y con su límite, y que el contexto de la construcción es una lista blanca
(R19, R21 y R22).

La del CONTEXTO necesita Docker pero no la imagen: arma un árbol de juguete con señuelos
de lo que no puede viajar y le pide a BuildKit el contexto que recibiría (R19).

Las DE HUMO usan la imagen `copiloto-app` YA CONSTRUIDA (R20): construirla es instalar
torch, minutos y cientos de MB en cada corrida de la suite, y eso es trabajo del que
despliega, no de las pruebas. Arrancan contenedores de verdad, siempre con nombre propio y
borrados en un `finally`, y publicados SOLO en 127.0.0.1 (o sin red ninguna).

Sin Docker, sin su demonio o sin la imagen, las que lo necesitan se SALTAN diciendo qué se
queda sin comprobar y con qué orden construir (desde la raíz del repositorio, con los pesos
en servidor/pesos_modelo_cpu.pt):

    docker build -t copiloto-app -f app/Dockerfile .

La imagen Linux de pruebas no tiene Docker: esas pruebas se corren en la máquina que lo
tiene (`python -m pytest tests/test_app_docker.py -rs`). Un salto se ve verde: `-rs` lista
cada uno con lo que deja sin verificar.

Los valores esperados están escritos aquí a mano o salen de los ficheros de despliegue (el
compose, el Dockerfile del servidor, `app/.streamlit/config.toml`), nunca del Dockerfile
que se está probando: una constante equivocada no puede dar por buena a la prueba que la
comprueba.
"""
import contextlib
import json
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
DOCKERFILE = REPO / "app" / "Dockerfile"
EXCLUSIONES = REPO / "app" / "Dockerfile.dockerignore"
DOCKERFILE_DEL_SERVIDOR = REPO / "servidor" / "Dockerfile"
COMPOSE = REPO / "servidor" / "docker-compose.yml"
CONFIG_DE_STREAMLIT = REPO / "app" / ".streamlit" / "config.toml"
README = REPO / "README.md"

IMAGEN = "copiloto-app"
PUERTO = 8501
ORDEN_DE_CONSTRUIR = "docker build -t copiloto-app -f app/Dockerfile ."
# El límite de memoria de la orden que documenta el README. Un DICOM de pocos KB puede
# declarar unas dimensiones enormes y el lector reserva la memoria de todas ellas (con
# RLE, 742 bytes que declaraban 40 000 x 40 000 píxeles hicieron reservar 1,5 GB): el
# límite protege la máquina. 2 GB son el del servidor, con ~4 veces lo que usa la app
# tras los cuatro ejemplos y el mapa de calor (457 MiB medidos). `--memory-swap` igual a
# `--memory`: sin él, Docker deja usar otro tanto de swap y el límite deja de serlo.
LIMITE_DE_MEMORIA = ("--memory=2g", "--memory-swap=2g")

# Lo único que la imagen copia del repositorio (R19). Todo lo demás -`.git`,
# `.superpowers`, `pruebas/` (puntuaciones por placa y un corpus de RSNA), `docs/`,
# `tests/`, `notebooks/`, los `.env`, `n8n/valores.local.json`- no entra ni al contexto.
LO_QUE_LA_IMAGEN_COPIA = ("app", "pyproject.toml", "servidor/calibrador.json",
                          "servidor/pesos_modelo_cpu.pt", "src")
LO_QUE_NO_DEBE_VIAJAR = (".git", ".superpowers", "pruebas", "docs", "tests",
                         "notebooks", "scripts", "bd", "n8n", ".env",
                         "valores.local.json")


# --------------------------------------------------------------------------
# Leer un Dockerfile y su fichero de exclusiones
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


def test_el_contexto_es_una_lista_blanca_y_es_la_de_lo_que_la_imagen_copia():
    """R19: se excluye todo y se readmite SOLO lo que la imagen copia. Si alguien
    readmite `docs` «para luego», o la imagen copia algo que el contexto no lleva,
    esta prueba lo dice."""
    reglas = _reglas(EXCLUSIONES)
    assert reglas[0] == "*", "la primera regla tiene que excluirlo todo"
    readmitidas = [r[1:] for r in reglas if r.startswith("!")]
    assert sorted(readmitidas) == sorted(LO_QUE_LA_IMAGEN_COPIA)
    # Lo que el Dockerfile copia, sin lo que ya cae dentro de otro origen copiado.
    origenes = {origen for origen, _ in _copias(DOCKERFILE)}
    en_el_nivel_de_arriba = {o for o in origenes
                             if not any(o.startswith(otro + "/") for otro in origenes)}
    assert en_el_nivel_de_arriba == set(readmitidas)
    for prohibido in LO_QUE_NO_DEBE_VIAJAR:
        assert prohibido not in readmitidas


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
    separadas: tocar `src/` no vuelve a bajar torch."""
    ordenes = [o for o in _de(DOCKERFILE, "RUN") if "pip install" in o]
    assert len(ordenes) == 2, ordenes
    primera, segunda = ordenes
    assert "-r app/requirements.txt" in primera
    assert "--no-deps ." in segunda
    assert all("--no-cache-dir" in o for o in ordenes)
    copias = _copias(DOCKERFILE)
    posicion = {origen: i for i, (origen, _) in enumerate(copias)}
    assert posicion["app/requirements.txt"] < posicion["src"]
    # Y la imagen no fija nada por su cuenta: las versiones viven en un solo sitio.
    assert not any("==" in orden for orden in ordenes)


def test_el_paquete_se_instala_y_no_se_mete_por_pythonpath():
    """Meter `src/` por `PYTHONPATH` no vale: Streamlit vigila y recarga los módulos de
    `PYTHONPATH`, y el código que correría no sería el instalado."""
    assert "PYTHONPATH" not in _entorno(DOCKERFILE)
    assert any("--no-deps ." in orden for orden in _de(DOCKERFILE, "RUN"))


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
    nada."""
    usuarios = _de(DOCKERFILE, "USER")
    assert usuarios, "falta `USER`: el contenedor correría como root"
    assert usuarios[-1] not in ("root", "0")


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


def test_las_imagenes_que_el_readme_ensena_existen():
    """Un enlace roto a una captura solo se ve al abrir el README en un navegador."""
    enlaces = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", _leer(README))
    for enlace in enlaces:
        if "://" not in enlace:
            assert (REPO / enlace).is_file(), f"el README enseña {enlace}, que no existe"


# --------------------------------------------------------------------------
# Ayudas de Docker
# --------------------------------------------------------------------------
def _docker(*argumentos, timeout=60) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *argumentos], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


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
# Un árbol de juguete con la forma del repositorio: lo que la imagen necesita, y
# SEÑUELOS de lo que no puede llegar al demonio, también dentro de `app/`, que se
# readmite entera.
ENTRAN = {
    "pyproject.toml",
    "src/paquete/__init__.py",
    "app/app.py", "app/requirements.txt", "app/.streamlit/config.toml",
    "app/assets/LICENCIAS.md", "app/assets/metricas.json",
    "app/assets/ejemplos/uno.dcm",
    "servidor/pesos_modelo_cpu.pt", "servidor/calibrador.json",
}
NO_ENTRAN = {
    ".git/HEAD", ".gitignore", "README.md", ".env", ".superpowers/nota.md",
    "pruebas/corpus/placa.png", "pruebas/sesion/respuestas.csv", "docs/informe.md",
    "tests/test_algo.py", "notebooks/uno.ipynb", "scripts/uno.py", "bd/esquema.sql",
    "n8n/valores.local.json", "servidor/.env", "servidor/Dockerfile",
    "servidor/arrancar.py",
    "app/.env", "app/.env.local", "app/produccion.env", "app/.streamlit/secrets.toml",
    "app/valores.local.json", "app/assets/originales/placa.png",
    "app/empaquetar_ejemplos.py", "app/generar_metricas.py", "app/Dockerfile",
    "app/Dockerfile.dockerignore",
    "src/paquete/__pycache__/modulo.cpython-312.pyc", "src/paquete.egg-info/PKG-INFO",
}

SIN_VERIFICAR_EL_CONTEXTO = (
    "CONTEXTO DE LA CONSTRUCCIÓN SIN VERIFICAR: {motivo}. Se queda sin comprobar que "
    "app/Dockerfile.dockerignore deja fuera del contexto lo que no debe viajar (.git, "
    "pruebas/, docs/, tests/, los .env, los secretos de Streamlit…). Para "
    "verificarlo, arranca Docker y repite.")


def test_el_contexto_de_la_construccion_es_solo_la_lista_blanca(tmp_path):
    """R19, con BuildKit de verdad y no con una lectura del fichero: se arma un árbol
    con la forma del repositorio, con lo que la imagen necesita y con señuelos de
    todo lo que no puede llegar al demonio (`pruebas/`, `.git`, los `.env`, los
    `valores.local.json`, el `secrets.toml` de Streamlit…), y se pide el contexto que
    recibiría la construcción: un Dockerfile de usar y tirar, `FROM scratch` + `COPY`,
    con una copia exacta de app/Dockerfile.dockerignore al lado, que es donde Docker
    la busca. `--output` vuelca el resultado a una carpeta, sin crear ninguna imagen.
    """
    motivo = _sin_docker()
    if motivo:
        pytest.skip(SIN_VERIFICAR_EL_CONTEXTO.format(motivo=motivo))
    arbol = tmp_path / "arbol"
    for ruta in ENTRAN | NO_ENTRAN:
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
                f"type=local,dest={salida}", str(arbol), timeout=180)
    assert r.returncode == 0, f"la construcción de usar y tirar falló:\n{r.stderr}"
    llegaron = {p.relative_to(salida / "ctx").as_posix()
                for p in (salida / "ctx").rglob("*") if p.is_file()}
    assert llegaron == ENTRAN, (
        f"llegaron de más: {sorted(llegaron - ENTRAN)}; faltan: "
        f"{sorted(ENTRAN - llegaron)}")


# --------------------------------------------------------------------------
# Las de humo: la imagen construida, con Docker
# --------------------------------------------------------------------------
SIN_VERIFICAR = (
    "PRUEBA DE HUMO DE LA IMAGEN DE LA APP SIN VERIFICAR: {motivo}. Se quedan sin "
    "comprobar que la imagen arranca, que su página responde, que no llama a nadie "
    "al arrancar, que no corre como root, que lleva la configuración de Streamlit, que "
    "no trae nada de lo que no debe viajar y que la app corre sin red con los pesos "
    "que lleva dentro. Para verificarlo, construye la imagen desde la raíz del "
    "repositorio, con los pesos en servidor/pesos_modelo_cpu.pt, y repite: "
    + ORDEN_DE_CONSTRUIR)


@pytest.fixture(scope="module")
def imagen():
    """La imagen construida, o un salto que dice por qué y cómo construirla. NO la
    construye (R20)."""
    motivo = _sin_docker()
    if motivo:
        pytest.skip(SIN_VERIFICAR.format(motivo=motivo))
    if _docker("image", "inspect", IMAGEN, timeout=30).returncode != 0:
        pytest.skip(SIN_VERIFICAR.format(motivo=f"no hay una imagen llamada `{IMAGEN}`"))
    return IMAGEN


def _para_mostrar(registros: str, lineas: int = 40) -> str:
    """El final de unos registros, para un mensaje de fallo, sin la línea de la «External
    URL»: lleva la IP pública de la máquina, y la salida de una prueba que falla acaba
    pegada en sitios."""
    utiles = [l for l in registros.splitlines() if "External URL" not in l]
    return "\n".join(utiles[-lineas:])


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
    """Una imagen que recibe radiografías no llama a nadie al arrancar. En modo
    headless, Streamlit pregunta a un servicio de fuera por la IP pública de la
    máquina y la escribe como «External URL», y fijar `--server.address=0.0.0.0` no lo
    evita (el comodín cuenta como no fijado): se comprobó con la imagen. Que no salga
    esa línea es que no preguntó. El mensaje de fallo no vuelca los registros: llevarían
    esa IP."""
    registros = contenedor.registros()
    assert "0.0.0.0:8501" in registros, "Streamlit no llegó a arrancar su servidor"
    if "External URL" in registros:
        pytest.fail("Streamlit preguntó por la IP pública de la máquina al arrancar: "
                    "salió una «External URL» en los registros", pytrace=False)
    assert "Traceback" not in registros, _para_mostrar(registros)
    # Y no vigila ficheros: en un Docker sobre WSL, Streamlit lo anuncia con «Using
    # poll-based file watching» (en otros sistemas no dice nada, y esto no prueba nada).
    assert "file watching" not in registros


def _en_bytes(cantidad: str) -> int:
    """`2g` -> 2 * 1024**3: la notación de `docker run --memory`."""
    unidades = {"b": 1, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}
    return int(cantidad[:-1]) * unidades[cantidad[-1].lower()]


def test_el_contenedor_corre_con_el_limite_de_memoria_documentado(contenedor):
    """Que la orden del README sea la que se prueba: el contenedor lleva el límite, sin
    swap de más, y la app arrancó dentro de él."""
    memoria_pedida, swap_pedido = (o.split("=")[1] for o in LIMITE_DE_MEMORIA)
    assert memoria_pedida == swap_pedido
    r = _docker("inspect", "-f", "{{.HostConfig.Memory}} {{.HostConfig.MemorySwap}}",
                contenedor.nombre)
    memoria, swap = (int(x) for x in r.stdout.split())
    assert memoria == swap == _en_bytes(memoria_pedida), r.stdout


def test_no_corre_como_root(contenedor):
    uid = contenedor.ejecutar("id", "-u").strip()
    assert uid.isdigit() and int(uid) != 0


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


def test_la_imagen_no_trae_lo_que_no_debe_viajar(contenedor):
    """El resultado de R19, mirado desde dentro: ni el repositorio entero ni los
    ficheros con secretos o con datos."""
    en_la_raiz = set(contenedor.ejecutar("ls", "-A", "/app").split())
    assert "app" in en_la_raiz
    assert not en_la_raiz & set(LO_QUE_NO_DEBE_VIAJAR), en_la_raiz
    sospechosos = contenedor.ejecutar(
        "find", "/app", "/modelo", "/home", "(", "-name", ".env*", "-o", "-name",
        "*.env", "-o", "-name", "valores.local.json", "-o", "-name", ".git", ")")
    assert sospechosos.strip() == ""
    # Los pesos y el calibrador, donde los busca la app.
    assert contenedor.ejecutar("ls", "/modelo").split() == [
        "calibrador.json", "pesos_modelo_cpu.pt"]


# Corre `app/app.py` en el contenedor, con el entorno que trae y sin ninguna red. Sin
# comillas dobles: el guion viaja como un argumento de `docker exec`.
GUION_DE_LA_APP = """
import json
from streamlit.testing.v1 import AppTest

at = AppTest.from_file('/app/app/app.py', default_timeout=240).run()
print(json.dumps({'excepciones': [str(e.value) for e in at.exception],
                  'errores': [str(e.value) for e in at.error],
                  'pestanas': len(at.tabs)}))
"""


def test_la_app_corre_sin_red_con_los_pesos_de_la_imagen(imagen):
    """Lo que `GET /` no dice: la página de Streamlit es la misma con o sin modelo,
    porque el guion de la app solo corre cuando alguien abre una sesión. Aquí corre,
    dentro de la imagen y en un contenedor SIN RED (no hay puerto que publicar: se le
    habla por `docker exec`): si necesitara algo de fuera para arrancar -bajar pesos,
    consultar una versión, mandar una estadística-, no arrancaría. Carga el modelo
    con los pesos y el entorno de la imagen y pinta sus pestañas, sin error."""
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
