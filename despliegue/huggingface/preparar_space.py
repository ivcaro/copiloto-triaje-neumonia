# -*- coding: utf-8 -*-
"""Arma la carpeta que se sube al Space de Hugging Face (SP5-C3, P8).

USO
    python despliegue/huggingface/preparar_space.py CARPETA
    python despliegue/huggingface/preparar_space.py CARPETA --pesos RUTA/pesos_modelo_cpu.pt

Escribe en CARPETA, que tiene que quedar FUERA del repositorio y no existir o estar vacía,
exactamente lo que el Space necesita para construir su imagen, con la misma disposición que
el repositorio (para que los COPY del Dockerfile sean los de app/Dockerfile):

    README.md                       el del Space, con su cabecera YAML (despliegue/huggingface/)
    Dockerfile                      el del Space (despliegue/huggingface/)
    app/                            lo que la app lee, fichero a fichero
    src/copiloto_triaje/            el paquete, solo sus .py
    pyproject.toml                  lo que `pip install .` necesita
    servidor/calibrador.json        el calibrador
    servidor/pesos_modelo_cpu.pt    los pesos

y nada más: ni docs, ni pruebas, ni notebooks, ni datos, ni .git, ni .env.

QUÉ ES «LO QUE LA APP LEE». No es una lista escrita aquí: son las rutas que
app/Dockerfile.dockerignore readmite de `app/` (las líneas `!app/...`), que
tests/test_app_docker.py comprueba contra el código de la app. Si la app pasa a leer un
fichero nuevo, esa prueba obliga a readmitirlo allí, y esta carpeta lo lleva sin tocar
este guion.

LOS PESOS. No viajan en git (`.gitignore` deja fuera los `*.pt`). Por defecto se toman de
servidor/pesos_modelo_cpu.pt; con --pesos, de otro sitio (por ejemplo, la descarga del
release). Su SHA-256 se compara con el `pesos_sha256` de app/assets/metricas.json (los
pesos con los que se midieron las métricas que la página enseña en «Acerca de»), y se
compara el de la COPIA ya escrita en CARPETA, que es lo que se sube. Si no coincide, o
falta cualquier cosa, no queda nada escrito.

Los ficheros de texto se copian con finales de línea LF (un Dockerfile o un guion con CRLF,
de un clon hecho en Windows, no debe viajar al Space); los binarios, byte a byte.

Sale con 0 si la carpeta quedó lista y con 1 si no (con el motivo, en la salida de error).
No crea nada en Hugging Face ni usa la red: la subida es un paso aparte (docs/desarrollo.md,
«Publicar la app»).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Las rutas del repositorio (y del Space: la disposición es la misma).
CARPETA_DEL_SPACE = "despliegue/huggingface"
README_DEL_SPACE = f"{CARPETA_DEL_SPACE}/README.md"
DOCKERFILE_DEL_SPACE = f"{CARPETA_DEL_SPACE}/Dockerfile"
EXCLUSIONES_DE_LA_APP = "app/Dockerfile.dockerignore"
METRICAS = "app/assets/metricas.json"
PAQUETE = "src/copiloto_triaje"
PYPROJECT = "pyproject.toml"
CALIBRADOR = "servidor/calibrador.json"
PESOS = "servidor/pesos_modelo_cpu.pt"

# Se copian con LF; lo demás, byte a byte (los DICOM y los pesos).
SUFIJOS_DE_TEXTO = {".py", ".md", ".toml", ".json", ".txt"}
NOMBRES_DE_TEXTO = {"Dockerfile"}


class ErrorDePreparacion(Exception):
    """Algo impide armar la carpeta; el mensaje dice qué y cómo arreglarlo."""


def huella_sha256(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with ruta.open("rb") as fichero:
        for trozo in iter(lambda: fichero.read(1 << 20), b""):
            resumen.update(trozo)
    return resumen.hexdigest()


def _es_de_texto(ruta: str) -> bool:
    nombre = Path(ruta)
    return nombre.suffix in SUFIJOS_DE_TEXTO or nombre.name in NOMBRES_DE_TEXTO


def archivos_de_la_app(raiz: Path) -> list[str]:
    """Las rutas de `app/` que la imagen lleva: las `!app/...` de su fichero de exclusiones
    (ver la nota de «QUÉ ES LO QUE LA APP LEE» arriba)."""
    exclusiones = raiz / EXCLUSIONES_DE_LA_APP
    if not exclusiones.is_file():
        raise ErrorDePreparacion(f"falta {EXCLUSIONES_DE_LA_APP}, de donde sale lo que la app lee")
    rutas = []
    for linea in exclusiones.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea.startswith("!app/"):
            ruta = linea[1:]
            if any(c in ruta for c in "*?["):
                raise ErrorDePreparacion(
                    f"{EXCLUSIONES_DE_LA_APP} readmite un patrón ({ruta}): se esperan rutas "
                    "fichero a fichero")
            rutas.append(ruta)
    if not rutas:
        raise ErrorDePreparacion(f"{EXCLUSIONES_DE_LA_APP} no readmite nada de app/")
    return sorted(rutas)


def archivos_del_paquete(raiz: Path) -> list[str]:
    """Los `.py` de `src/copiloto_triaje/`, a cualquier profundidad y sin cachés."""
    carpeta = raiz / PAQUETE
    if not carpeta.is_dir():
        raise ErrorDePreparacion(f"falta {PAQUETE}/")
    return sorted(p.relative_to(raiz).as_posix() for p in carpeta.rglob("*.py")
                  if "__pycache__" not in p.relative_to(raiz).parts and p.is_file())


def seleccionar(raiz: Path) -> list[str]:
    """Las rutas (relativas a la raíz, y las mismas en el Space) de todo lo que viaja SALVO
    los pesos, que se tratan aparte por su comprobación."""
    rutas = [README_DEL_SPACE, DOCKERFILE_DEL_SPACE, PYPROJECT, CALIBRADOR]
    rutas += archivos_de_la_app(raiz) + archivos_del_paquete(raiz)
    faltan = [r for r in rutas if not (raiz / r).is_file()]
    if faltan:
        raise ErrorDePreparacion("faltan en el repositorio: " + ", ".join(faltan))
    return rutas


def _destino_en_el_space(ruta: str) -> str:
    """README.md y Dockerfile del Space salen de despliegue/huggingface/ y van a la raíz de
    la carpeta; todo lo demás conserva su ruta."""
    if ruta == README_DEL_SPACE:
        return "README.md"
    if ruta == DOCKERFILE_DEL_SPACE:
        return "Dockerfile"
    return ruta


def _huella_esperada(raiz: Path) -> str:
    ruta = raiz / METRICAS
    if not ruta.is_file():
        raise ErrorDePreparacion(f"falta {METRICAS}, de donde sale la huella de los pesos")
    huella = json.loads(ruta.read_text(encoding="utf-8")).get("pesos_sha256")
    if not isinstance(huella, str) or len(huella) != 64:
        raise ErrorDePreparacion(f"{METRICAS} no lleva un `pesos_sha256` válido")
    return huella.lower()


def _fuera_del_repositorio(raiz: Path, destino: Path) -> None:
    raiz, destino = raiz.resolve(), destino.resolve()
    if destino == raiz or raiz in destino.parents or destino in raiz.parents:
        raise ErrorDePreparacion(
            f"CARPETA ({destino}) tiene que estar fuera del repositorio ({raiz}): lo que "
            "se arma lleva los pesos, que no se versionan, y no debe acabar en un commit")


def _vaciar(carpeta: Path) -> None:
    for hijo in carpeta.iterdir():
        if hijo.is_dir() and not hijo.is_symlink():
            shutil.rmtree(hijo)
        else:
            hijo.unlink()


def preparar(raiz: Path, destino: Path, pesos: Path | None = None) -> list[str]:
    """Arma `destino` y devuelve las rutas que quedan escritas (relativas a él). Si algo
    falla, no deja nada escrito y lanza `ErrorDePreparacion`."""
    raiz, destino = Path(raiz), Path(destino)
    _fuera_del_repositorio(raiz, destino)
    if destino.exists() and (not destino.is_dir() or any(destino.iterdir())):
        raise ErrorDePreparacion(
            f"{destino} ya existe y no está vacía: bórrela o elija otra carpeta (así no se "
            "mezcla con una preparación anterior)")

    origen_de_los_pesos = Path(pesos) if pesos is not None else raiz / PESOS
    if not origen_de_los_pesos.is_file():
        raise ErrorDePreparacion(
            f"no hay pesos en {origen_de_los_pesos}: no viajan en git; póngalos ahí o dé su "
            "ruta con --pesos (models/README.md dice de dónde bajarlos)")
    esperada = _huella_esperada(raiz)
    rutas = seleccionar(raiz)

    existia = destino.exists()
    escritas: list[str] = []
    try:
        destino.mkdir(parents=True, exist_ok=True)
        for ruta in rutas:
            salida = destino / _destino_en_el_space(ruta)
            salida.parent.mkdir(parents=True, exist_ok=True)
            contenido = (raiz / ruta).read_bytes()
            if _es_de_texto(ruta):
                contenido = contenido.replace(b"\r\n", b"\n")
            salida.write_bytes(contenido)
            escritas.append(salida.relative_to(destino).as_posix())
        salida_de_los_pesos = destino / PESOS
        salida_de_los_pesos.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen_de_los_pesos, salida_de_los_pesos)
        escritas.append(PESOS)
        # La comprobación es sobre la COPIA, que es lo que se sube.
        obtenida = huella_sha256(salida_de_los_pesos)
        if obtenida != esperada:
            raise ErrorDePreparacion(
                f"los pesos de {origen_de_los_pesos} no son los que se midieron: su SHA-256 es "
                f"{obtenida} y {METRICAS} (`pesos_sha256`) dice {esperada}. Las métricas de la "
                "página «Acerca de» son las de otros pesos; use los del release v1.0")
    except BaseException:
        if existia:
            _vaciar(destino)
        else:
            shutil.rmtree(destino, ignore_errors=True)
        raise
    return sorted(escritas)


def principal(argv: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="Más en la cabecera de este guion y en docs/desarrollo.md, «Publicar la app».")
    analizador.add_argument("carpeta", type=Path,
                            help="dónde armar lo que se sube; fuera del repositorio, inexistente "
                                 "o vacía")
    analizador.add_argument("--pesos", type=Path, default=None,
                            help=f"los pesos; por defecto, {PESOS} del repositorio")
    analizador.add_argument("--raiz", type=Path, default=RAIZ,
                            help="la raíz del repositorio (por defecto, la de este guion; "
                                 "existe para las pruebas)")
    argumentos = analizador.parse_args(argv)
    try:
        escritas = preparar(argumentos.raiz, argumentos.carpeta, argumentos.pesos)
    except ErrorDePreparacion as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    carpeta = argumentos.carpeta.resolve()
    peso = sum((carpeta / r).stat().st_size for r in escritas)
    print(f"Listo: {len(escritas)} ficheros ({peso / 1e6:.1f} MB) en {carpeta}")
    print("Pesos: su SHA-256 es el de app/assets/metricas.json.")
    print("Para probarlo en local:  docker build -t copiloto-space " + str(carpeta))
    print("Para subirlo:            ver docs/desarrollo.md, «Publicar la app».")
    return 0


if __name__ == "__main__":
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(principal())
