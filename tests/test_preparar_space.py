# -*- coding: utf-8 -*-
"""El Space de Hugging Face (SP5-C3, P8): `despliegue/huggingface/`.

TRES CLASES DE PRUEBAS, y ninguna usa la red, Docker ni el modelo.

Las del GUION (`preparar_space.py`) arman la carpeta en un repositorio de JUGUETE, con
señuelos de todo lo que no puede viajar (docs, pruebas, notebooks, datos, `.git`, `.env`, un
`.pyc`, un CSV dentro del paquete…), y comprueban que sale EXACTAMENTE lo que tiene que salir,
que los pesos se comprueban por su SHA-256 (también cuando faltan o no son los que se
midieron: entonces no queda nada escrito), que el destino queda fuera del repositorio y vacío
de antes, y que los finales de línea de los textos son LF y los binarios no se tocan.

Las del REPOSITORIO REAL no necesitan los pesos (no viajan en git): que lo que el guion
selecciona es lo que el Dockerfile del Space copia, que ese Dockerfile es el de `app/Dockerfile`
(la misma base, las mismas variables, los mismos COPY y las mismas opciones de Streamlit) más
las dos que necesita el iframe de Hugging Face, y que el README del Space tiene una cabecera
YAML válida y coherente con el Dockerfile. La armada completa con los pesos de verdad se SALTA
si el clon no los tiene (`-rs` lo muestra).

Las de la DOCUMENTACIÓN: que `docs/desarrollo.md` tiene la sección «Publicar la app» y que lo
que dice coincide con lo que hay (la versión fijada de huggingface_hub, los nombres de los
guiones y la orden de subida).

Lo que NO se comprueba aquí, porque necesita Docker, un navegador y la red: que la imagen
construye, que la página corre dentro de un iframe de otro sitio y sube un DICOM (se probó a
mano, y el procedimiento está en docs/desarrollo.md, «Publicar la app»), y el Space mismo.
"""
import hashlib
import importlib.util
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GUION = REPO / "despliegue" / "huggingface" / "preparar_space.py"
DOCKERFILE_DEL_SPACE = REPO / "despliegue" / "huggingface" / "Dockerfile"
README_DEL_SPACE = REPO / "despliegue" / "huggingface" / "README.md"
DOCKERFILE_DE_LA_APP = REPO / "app" / "Dockerfile"
EXCLUSIONES = REPO / "app" / "Dockerfile.dockerignore"
DESARROLLO = REPO / "docs" / "desarrollo.md"
PESOS_REALES = REPO / "servidor" / "pesos_modelo_cpu.pt"

# Los colores que acepta la cabecera de un Space (docs del Hub, «Spaces Configuration
# Reference»).
COLORES = {"red", "yellow", "green", "blue", "indigo", "purple", "pink", "gray"}
# El Hub corta la descripción corta de la miniatura en 60 caracteres.
LARGO_MAXIMO_DE_LA_DESCRIPCION_CORTA = 60


def _cargar_guion():
    especificacion = importlib.util.spec_from_file_location("preparar_space", GUION)
    modulo = importlib.util.module_from_spec(especificacion)
    sys.modules["preparar_space"] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


ps = _cargar_guion()


# --------------------------------------------------------------------------
# Un repositorio de juguete, con señuelos
# --------------------------------------------------------------------------
PESOS_DE_JUGUETE = b"pesos de juguete \x00\x01\r\n\xff"
# Lo que SÍ tiene que viajar, por ruta. Los `.dcm` llevan un \r\n dentro a propósito: un
# binario no se toca.
BINARIO = b"DICM\x00\r\n\x00\r\n\xff\xfe"
QUE_VIAJA = {
    "README.md", "Dockerfile", "pyproject.toml", "servidor/calibrador.json",
    "servidor/pesos_modelo_cpu.pt",
    "app/app.py", "app/requirements.txt", "app/.streamlit/config.toml",
    "app/assets/metricas.json", "app/assets/LICENCIAS.md", "app/assets/ejemplos/uno.dcm",
    "src/copiloto_triaje/__init__.py", "src/copiloto_triaje/sub/__init__.py",
    "src/copiloto_triaje/sub/modulo.py",
}


def _escribir(raiz: Path, ruta: str, contenido: str | bytes = "x\n") -> None:
    destino = raiz / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(contenido, str):
        contenido = contenido.encode("utf-8")
    destino.write_bytes(contenido)


def _repo_de_juguete(tmp_path: Path, pesos: bytes = PESOS_DE_JUGUETE,
                     huella: str | None = None) -> Path:
    raiz = tmp_path / "repo"
    huella = huella or hashlib.sha256(pesos).hexdigest()
    # Lo que viaja.
    _escribir(raiz, "despliegue/huggingface/README.md", "---\nsdk: docker\n---\r\nSpace\r\n")
    _escribir(raiz, "despliegue/huggingface/Dockerfile", "FROM x\r\nCMD [\"a\"]\r\n")
    _escribir(raiz, "pyproject.toml", "[project]\r\nname = \"x\"\r\n")
    _escribir(raiz, "servidor/calibrador.json", "{}\n")
    _escribir(raiz, "servidor/pesos_modelo_cpu.pt", pesos)
    _escribir(raiz, "app/app.py", "print('hola')\r\n")
    _escribir(raiz, "app/requirements.txt", "streamlit==1\n")
    _escribir(raiz, "app/.streamlit/config.toml", "[server]\n")
    _escribir(raiz, "app/assets/metricas.json", json.dumps({"pesos_sha256": huella}) + "\n")
    _escribir(raiz, "app/assets/LICENCIAS.md", "# Licencias\n")
    _escribir(raiz, "app/assets/ejemplos/uno.dcm", BINARIO)
    _escribir(raiz, "src/copiloto_triaje/__init__.py", "")
    _escribir(raiz, "src/copiloto_triaje/sub/__init__.py", "")
    _escribir(raiz, "src/copiloto_triaje/sub/modulo.py", "X = 1\r\n")
    _escribir(raiz, "app/Dockerfile.dockerignore", "\n".join([
        "# comentario", "*", "!pyproject.toml", "!src/**/*.py",
        "!servidor/pesos_modelo_cpu.pt", "!servidor/calibrador.json",
        "!app/app.py", "!app/requirements.txt", "!app/.streamlit/config.toml",
        "!app/assets/metricas.json", "!app/assets/LICENCIAS.md",
        "!app/assets/ejemplos/uno.dcm", "**/.git", ""]))
    # Los señuelos: nada de esto puede llegar al Space.
    for senuelo in (
            "app/Dockerfile", "app/empaquetar_ejemplos.py", "app/generar_metricas.py",
            "app/assets/originales/uno.png", "app/notas.txt", "app/.env", "app/secrets.toml",
            "app/.streamlit/secrets.toml", "src/copiloto_triaje/datos.csv",
            "src/copiloto_triaje/clave.pem", "src/copiloto_triaje/__pycache__/m.cpython-312.pyc",
            "src/model.py", "src/__init__.py", "servidor/Dockerfile", "servidor/.env",
            "servidor/docker-compose.yml", "docs/desarrollo.md", "tests/test_x.py",
            "notebooks/n.ipynb", "data/raw/a.dcm", "pruebas/puntuaciones.csv", "models/README.md",
            ".git/config", ".env", "README.md", "n8n/valores.local.json"):
        _escribir(raiz, senuelo, "señuelo\n")
    return raiz


def _arbol(carpeta: Path) -> set[str]:
    return {p.relative_to(carpeta).as_posix() for p in carpeta.rglob("*") if p.is_file()}


# --------------------------------------------------------------------------
# El guion, en un repositorio de juguete
# --------------------------------------------------------------------------
def test_sale_exactamente_lo_que_tiene_que_salir_y_nada_mas(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    destino = tmp_path / "space"
    escritas = ps.preparar(raiz, destino)
    assert _arbol(destino) == QUE_VIAJA
    assert set(escritas) == QUE_VIAJA
    # El README y el Dockerfile son los de despliegue/huggingface/, no los de la raíz...
    assert (destino / "README.md").read_text(encoding="utf-8").startswith("---\nsdk: docker")
    assert (destino / "Dockerfile").read_text(encoding="utf-8").startswith("FROM x")
    # ...y no hay ni `despliegue/` en la carpeta, ni nada de lo que no es del Space.
    assert not (destino / "despliegue").exists()
    for prohibido in (".git", ".env", "docs", "tests", "notebooks", "data", "pruebas", "models",
                      "n8n", "bd", "scripts"):
        assert not (destino / prohibido).exists(), prohibido


def test_los_pesos_se_copian_tal_cual_y_con_su_huella(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    destino = tmp_path / "space"
    ps.preparar(raiz, destino)
    copiados = (destino / "servidor" / "pesos_modelo_cpu.pt").read_bytes()
    assert copiados == PESOS_DE_JUGUETE
    assert ps.huella_sha256(destino / "servidor" / "pesos_modelo_cpu.pt") == \
        hashlib.sha256(PESOS_DE_JUGUETE).hexdigest()


def test_los_textos_salen_con_lf_y_los_binarios_no_se_tocan(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    destino = tmp_path / "space"
    ps.preparar(raiz, destino)
    for texto in ("Dockerfile", "README.md", "pyproject.toml", "app/app.py",
                  "src/copiloto_triaje/sub/modulo.py"):
        contenido = (destino / texto).read_bytes()
        assert b"\r" not in contenido, texto
    assert (destino / "app" / "assets" / "ejemplos" / "uno.dcm").read_bytes() == BINARIO


def test_con_pesos_que_no_son_los_medidos_no_queda_nada_escrito(tmp_path):
    raiz = _repo_de_juguete(tmp_path, huella="0" * 64)
    destino = tmp_path / "space"
    with pytest.raises(ps.ErrorDePreparacion) as error:
        ps.preparar(raiz, destino)
    assert "SHA-256" in str(error.value) and "metricas.json" in str(error.value)
    assert not destino.exists()


def test_con_pesos_equivocados_y_una_carpeta_vacia_de_antes_la_deja_vacia(tmp_path):
    raiz = _repo_de_juguete(tmp_path, huella="f" * 64)
    destino = tmp_path / "space"
    destino.mkdir()
    with pytest.raises(ps.ErrorDePreparacion):
        ps.preparar(raiz, destino)
    assert destino.is_dir() and list(destino.iterdir()) == []


def test_sin_pesos_se_dice_donde_ponerlos_o_como_darlos(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    (raiz / "servidor" / "pesos_modelo_cpu.pt").unlink()
    destino = tmp_path / "space"
    with pytest.raises(ps.ErrorDePreparacion) as error:
        ps.preparar(raiz, destino)
    assert "--pesos" in str(error.value)
    assert not destino.exists()


def test_los_pesos_pueden_venir_de_otro_sitio(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    (raiz / "servidor" / "pesos_modelo_cpu.pt").unlink()
    bajados = tmp_path / "descargas" / "pesos_modelo_cpu.pt"
    bajados.parent.mkdir()
    bajados.write_bytes(PESOS_DE_JUGUETE)
    destino = tmp_path / "space"
    ps.preparar(raiz, destino, pesos=bajados)
    assert (destino / "servidor" / "pesos_modelo_cpu.pt").read_bytes() == PESOS_DE_JUGUETE


def test_la_carpeta_tiene_que_estar_fuera_del_repositorio(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    for dentro in (raiz / "salida", raiz / "despliegue" / "huggingface" / "space", raiz):
        with pytest.raises(ps.ErrorDePreparacion) as error:
            ps.preparar(raiz, dentro)
        assert "fuera del repositorio" in str(error.value)
    assert not (raiz / "salida").exists()
    # Tampoco una carpeta que CONTIENE al repositorio.
    with pytest.raises(ps.ErrorDePreparacion):
        ps.preparar(raiz, tmp_path)


def test_una_carpeta_con_cosas_se_rechaza_sin_tocarla(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    destino = tmp_path / "space"
    destino.mkdir()
    (destino / "vieja.txt").write_text("de antes", encoding="utf-8")
    with pytest.raises(ps.ErrorDePreparacion) as error:
        ps.preparar(raiz, destino)
    assert "no está vacía" in str(error.value)
    assert _arbol(destino) == {"vieja.txt"}
    # Y un fichero en lugar de una carpeta, también.
    fichero = tmp_path / "fichero"
    fichero.write_text("x", encoding="utf-8")
    with pytest.raises(ps.ErrorDePreparacion):
        ps.preparar(raiz, fichero)


def test_en_una_carpeta_vacia_de_antes_se_arma_igual(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    destino = tmp_path / "space"
    destino.mkdir()
    ps.preparar(raiz, destino)
    assert _arbol(destino) == QUE_VIAJA


def test_un_fichero_que_falta_en_el_repositorio_se_dice_y_no_deja_nada(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    (raiz / "servidor" / "calibrador.json").unlink()
    destino = tmp_path / "space"
    with pytest.raises(ps.ErrorDePreparacion) as error:
        ps.preparar(raiz, destino)
    assert "calibrador.json" in str(error.value)
    assert not destino.exists()


def test_lo_que_la_app_lee_sale_del_fichero_de_exclusiones_y_sin_patrones(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    # Una ruta nueva readmitida allí viaja sin tocar el guion...
    _escribir(raiz, "app/assets/nuevo.json", "{}\n")
    with (raiz / "app" / "Dockerfile.dockerignore").open("a", encoding="utf-8") as f:
        f.write("!app/assets/nuevo.json\n")
    destino = tmp_path / "space"
    ps.preparar(raiz, destino)
    assert "app/assets/nuevo.json" in _arbol(destino)
    # ...y un patrón (que dejaría pasar lo que alguien suelte en la carpeta) se rechaza.
    with (raiz / "app" / "Dockerfile.dockerignore").open("a", encoding="utf-8") as f:
        f.write("!app/assets/*.json\n")
    with pytest.raises(ps.ErrorDePreparacion) as error:
        ps.preparar(raiz, tmp_path / "otro")
    assert "patrón" in str(error.value)


def test_el_paquete_lleva_solo_sus_py(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    destino = tmp_path / "space"
    ps.preparar(raiz, destino)
    del_paquete = {r for r in _arbol(destino) if r.startswith("src/")}
    assert del_paquete == {"src/copiloto_triaje/__init__.py", "src/copiloto_triaje/sub/__init__.py",
                           "src/copiloto_triaje/sub/modulo.py"}


def test_la_linea_de_ordenes_sale_con_0_y_con_1(tmp_path):
    raiz = _repo_de_juguete(tmp_path)
    bien = tmp_path / "bien"
    resultado = subprocess.run(
        [sys.executable, "-I", str(GUION), str(bien), "--raiz", str(raiz)],
        capture_output=True, text=True, encoding="utf-8")
    assert resultado.returncode == 0, resultado.stderr
    assert "Listo" in resultado.stdout and "Publicar la app" in resultado.stdout
    assert _arbol(bien) == QUE_VIAJA
    # Los pesos equivocados: 1, con el motivo en la salida de error, y nada escrito.
    mal_repo = _repo_de_juguete(tmp_path / "otro", huella="a" * 64)
    mal = tmp_path / "mal"
    resultado = subprocess.run(
        [sys.executable, "-I", str(GUION), str(mal), "--raiz", str(mal_repo)],
        capture_output=True, text=True, encoding="utf-8")
    assert resultado.returncode == 1
    assert "SHA-256" in resultado.stderr and resultado.stdout == ""
    assert not mal.exists()


# --------------------------------------------------------------------------
# El repositorio real: el guion, el Dockerfile y el README del Space
# --------------------------------------------------------------------------
def _instrucciones(ruta: Path) -> list[tuple[str, str]]:
    """Las instrucciones de un Dockerfile como (`FROM`, `resto`): sin comentarios ni líneas
    en blanco, y con las partidas por `\\` ya unidas."""
    instrucciones, pendiente = [], ""
    for cruda in ruta.read_text(encoding="utf-8").splitlines():
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
    assert not pendiente
    return instrucciones


def _de(ruta: Path, instruccion: str) -> list[str]:
    return [resto for palabra, resto in _instrucciones(ruta) if palabra == instruccion]


def _entorno(ruta: Path) -> dict[str, str]:
    entorno = {}
    for resto in _de(ruta, "ENV"):
        for par in shlex.split(resto):
            clave, igual, valor = par.partition("=")
            assert igual
            entorno[clave] = valor
    return entorno


def _copias(ruta: Path) -> set[tuple[str, str]]:
    copias = set()
    for resto in _de(ruta, "COPY"):
        partes = [p for p in shlex.split(resto) if not p.startswith("--")]
        assert len(partes) == 2, resto
        copias.add((partes[0].rstrip("/"), partes[1]))
    return copias


def _orden(ruta: Path) -> list[str]:
    (cmd,) = _de(ruta, "CMD")
    return json.loads(cmd)


def test_lo_que_el_guion_selecciona_es_lo_que_el_dockerfile_del_space_copia():
    rutas = set(ps.seleccionar(REPO))
    de_la_app = {r for r in rutas if r.startswith("app/")}
    # Lo de `app/` es exactamente lo que readmite el fichero de exclusiones de la app...
    readmitidas = {l.strip()[1:] for l in EXCLUSIONES.read_text(encoding="utf-8").splitlines()
                   if l.strip().startswith("!app/")}
    assert de_la_app == readmitidas and de_la_app
    # ...no lleva nada que no sea de la página...
    for no in ("app/Dockerfile", "app/Dockerfile.dockerignore", "app/empaquetar_ejemplos.py",
               "app/generar_metricas.py"):
        assert no not in rutas
    assert not any(r.startswith("app/assets/originales/") for r in rutas)
    # ...y cada origen de un COPY del Dockerfile del Space está en lo que se arma.
    en_el_space = {ps._destino_en_el_space(r) for r in rutas} | {ps.PESOS}
    for origen, _ in _copias(DOCKERFILE_DEL_SPACE):
        assert any(r == origen or r.startswith(origen + "/") for r in en_el_space), origen
    # Y al revés: todo lo que se arma lo copia algún COPY (salvo el README y el Dockerfile,
    # que son del Space y no de la imagen).
    for ruta in en_el_space - {"README.md", "Dockerfile"}:
        assert any(ruta == origen or ruta.startswith(origen + "/")
                   for origen, _ in _copias(DOCKERFILE_DEL_SPACE)), ruta


def test_del_paquete_viajan_los_py_del_paquete_y_ninguna_cache():
    rutas = [r for r in ps.seleccionar(REPO) if r.startswith("src/")]
    assert rutas and all(r.startswith("src/copiloto_triaje/") and r.endswith(".py") for r in rutas)
    assert "src/copiloto_triaje/__init__.py" in rutas
    assert not any("__pycache__" in r for r in rutas)


def test_el_dockerfile_del_space_es_el_de_la_app_con_su_base_sus_variables_y_sus_pasos():
    assert _de(DOCKERFILE_DEL_SPACE, "FROM") == _de(DOCKERFILE_DE_LA_APP, "FROM")
    assert "@sha256:" in _de(DOCKERFILE_DEL_SPACE, "FROM")[0]
    assert _entorno(DOCKERFILE_DEL_SPACE) == _entorno(DOCKERFILE_DE_LA_APP)
    assert _copias(DOCKERFILE_DEL_SPACE) == _copias(DOCKERFILE_DE_LA_APP)
    # Los pasos de `pip` (las versiones viven en app/requirements.txt, no aquí).
    pasos = [o for o in _de(DOCKERFILE_DEL_SPACE, "RUN") if "pip install" in o]
    assert pasos == [o for o in _de(DOCKERFILE_DE_LA_APP, "RUN") if "pip install" in o]
    assert not any("==" in paso for paso in pasos)


def test_el_dockerfile_del_space_no_corre_como_root_sino_con_el_uid_1000_de_hugging_face():
    usuario = _de(DOCKERFILE_DEL_SPACE, "USER")
    assert usuario and usuario[-1] not in ("root", "0")
    # El usuario se crea con el UID 1000 (docs del Hub, «Docker Spaces», «Permissions»).
    crea = [o for o in _de(DOCKERFILE_DEL_SPACE, "RUN") if "useradd" in o]
    assert len(crea) == 1 and re.search(r"--uid 1000\b", crea[0]) and usuario[-1] in crea[0]
    # Y la orden se lanza como ese usuario: el `USER` va antes del `CMD`.
    palabras = [p for p, _ in _instrucciones(DOCKERFILE_DEL_SPACE)]
    assert palabras.index("USER") < palabras.index("CMD")


def test_streamlit_lleva_las_opciones_de_la_app_mas_las_dos_del_iframe_y_nada_mas():
    del_space, de_la_app = _orden(DOCKERFILE_DEL_SPACE), _orden(DOCKERFILE_DE_LA_APP)
    assert del_space[:3] == de_la_app[:3] == ["streamlit", "run", "app.py"]
    opciones_space, opciones_app = set(del_space[3:]), set(de_la_app[3:])
    assert opciones_app <= opciones_space, "al Space le falta una opción de la app"
    assert opciones_space - opciones_app == {"--server.enableXsrfProtection=false",
                                             "--server.enableCORS=false"}
    # Las que protegen lo que recibe la página, sin tocar.
    for obligatoria in ("--browser.gatherUsageStats=false", "--logger.hideWelcomeMessage=true",
                        "--server.maxUploadSize=5", "--server.fileWatcherType=none",
                        "--server.headless=true", "--server.port=8501"):
        assert obligatoria in opciones_space
    # Y por qué se apagan, escrito junto a la orden.
    texto = DOCKERFILE_DEL_SPACE.read_text(encoding="utf-8")
    assert "iframe" in texto and "403" in texto


def _cabecera_del_readme() -> dict[str, str]:
    texto = README_DEL_SPACE.read_text(encoding="utf-8")
    assert texto.startswith("---\n"), "el README del Space tiene que abrir con la cabecera YAML"
    cabecera = texto[4:].split("\n---\n", 1)[0]
    campos = {}
    for linea in cabecera.splitlines():
        clave, dos_puntos, valor = linea.partition(":")
        assert dos_puntos, f"línea de la cabecera sin `:` → {linea!r}"
        campos[clave.strip()] = valor.strip()
    return campos


def test_el_readme_del_space_tiene_su_cabecera_y_coincide_con_el_dockerfile():
    campos = _cabecera_del_readme()
    for obligatorio in ("title", "emoji", "colorFrom", "colorTo", "sdk", "app_port",
                        "short_description"):
        assert campos.get(obligatorio), obligatorio
    assert campos["sdk"] == "docker"
    assert campos["colorFrom"] in COLORES and campos["colorTo"] in COLORES
    assert len(campos["short_description"]) <= LARGO_MAXIMO_DE_LA_DESCRIPCION_CORTA
    # El puerto de la cabecera es el que escucha Streamlit y el que expone la imagen.
    assert campos["app_port"] == "8501"
    assert _de(DOCKERFILE_DEL_SPACE, "EXPOSE") == ["8501"]
    assert "--server.port=8501" in _orden(DOCKERFILE_DEL_SPACE)


def test_el_readme_del_space_dice_que_es_una_demostracion_y_deja_pendiente_el_enlace():
    texto = README_DEL_SPACE.read_text(encoding="utf-8")
    minusculas = " ".join(texto.lower().split())
    assert "demostración académica" in minusculas
    assert "no es un producto sanitario" in minusculas
    assert "no suba radiografías de pacientes reales" in minusculas
    # El enlace al repositorio está marcado como pendiente: se rellena al hacerlo público.
    assert "PENDIENTE" in texto
    # Sin identificadores del cliente ni de la infraestructura (lo exhaustivo es el
    # verificador de anonimato; esto vigila lo que este README podría traer por su cuenta).
    assert "http://" not in texto


def test_la_armada_completa_con_los_pesos_de_verdad(tmp_path):
    """Con el repositorio real y sus pesos (los de servidor/pesos_modelo_cpu.pt, que no
    viajan en git): la huella coincide con la de las métricas y salen los cuatro ejemplos."""
    if not PESOS_REALES.is_file():
        pytest.skip("no hay servidor/pesos_modelo_cpu.pt en este clon (no viajan en git: "
                    "models/README.md); la armada completa se prueba donde estén")
    destino = tmp_path / "space"
    escritas = ps.preparar(REPO, destino)
    metricas = json.loads((REPO / "app" / "assets" / "metricas.json").read_text(encoding="utf-8"))
    assert ps.huella_sha256(destino / "servidor" / "pesos_modelo_cpu.pt") == metricas["pesos_sha256"]
    assert len([e for e in escritas if e.startswith("app/assets/ejemplos/")]) == 4
    for fuera in ("docs", "tests", "notebooks", "data", "models", "n8n", "scripts", "pruebas",
                  ".git", "despliegue"):
        assert not (destino / fuera).exists(), fuera
    assert not any(r.endswith((".csv", ".ipynb", ".env", ".pem", ".pyc")) for r in escritas)


# --------------------------------------------------------------------------
# La documentación
# --------------------------------------------------------------------------
def _seccion_publicar_la_app() -> str:
    texto = DESARROLLO.read_text(encoding="utf-8")
    encontrada = re.search(r"^## (?:\d+\. )?Publicar la app\s*$", texto, re.MULTILINE)
    assert encontrada, "docs/desarrollo.md no tiene la sección «Publicar la app»"
    resto = texto[encontrada.end():]
    siguiente = re.search(r"^## ", resto, re.MULTILINE)
    return resto[:siguiente.start()] if siguiente else resto


def test_desarrollo_explica_como_publicar_la_app_con_ordenes_que_existen():
    seccion = _seccion_publicar_la_app()
    # La versión de huggingface_hub, fijada con ==, y la CLI de ESA versión (`hf`): la
    # antigua `huggingface-cli` ya no existe en las versiones actuales.
    fijada = re.findall(r"huggingface_hub==(\d+\.\d+\.\d+)", seccion)
    assert fijada, "la sección tiene que fijar la versión de huggingface_hub con =="
    assert len(set(fijada)) == 1
    assert "hf auth login" in seccion
    assert "hf repos create" in seccion and "--private" in seccion and "--sdk docker" in seccion
    assert "python despliegue/huggingface/preparar_space.py" in seccion
    assert "hf upload" in seccion and "--repo-type space" in seccion
    assert "hf spaces logs" in seccion and "--build" in seccion
    assert "hf repos settings" in seccion and "--public" in seccion
    # Lo que hay que saber antes de empezar.
    minusculas = " ".join(seccion.lower().split())
    assert "se duerme" in minusculas
    assert "token" in minusculas
    # Los guiones y ficheros que nombra existen.
    for ruta in ("despliegue/huggingface/preparar_space.py", "despliegue/huggingface/Dockerfile",
                 "despliegue/huggingface/README.md"):
        assert ruta in seccion and (REPO / ruta).is_file(), ruta
