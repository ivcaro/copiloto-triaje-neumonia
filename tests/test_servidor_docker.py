# -*- coding: utf-8 -*-
"""El contexto de la construcción de la imagen del servidor (SP5-B4): `servidor/Dockerfile`.

El compose construye con el contexto en la RAÍZ del repositorio (`context: ..`), así que lo
que llega al demonio lo decide `servidor/Dockerfile.dockerignore`. Hasta SP5-B4 era una lista
negra (`docs`, `tests`, `.git`…): dejaba entrar `pruebas/` -con puntuaciones por placa y un
corpus de RSNA-, `n8n/` con su `valores.local.json`, `.superpowers/` y cualquier `.env`. Ahora
es una LISTA BLANCA, como la de la app (`app/Dockerfile.dockerignore`): solo lo que el
Dockerfile copia.

DOS CLASES DE PRUEBAS, como en tests/test_app_docker.py (cuyas ayudas se reutilizan):

- La ESTÁTICA lee el fichero y el Dockerfile, y corre siempre: la primera regla lo excluye
  todo, se readmite exactamente lo que el Dockerfile copia, y cada `COPY` copia algo de lo
  readmitido.
- La del CONTEXTO necesita Docker con BuildKit, pero no la imagen: arma un árbol de juguete
  con lo que la imagen necesita y con SEÑUELOS de lo que no puede viajar, y le pide a BuildKit
  el contexto que recibiría. Sin Docker se SALTA diciéndolo; la imagen Linux de pruebas no lo
  tiene, y se corre en la máquina que sí (`python -m pytest tests/test_servidor_docker.py
  -rs`). Un salto se ve verde: `-rs` los lista.
"""
import os
import shutil
from pathlib import Path

import pytest

from test_app_docker import _copias, _docker, _reglas, _sin_docker

REPO = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO / "servidor" / "Dockerfile"
EXCLUSIONES = REPO / "servidor" / "Dockerfile.dockerignore"

# Lo que copia servidor/Dockerfile, escrito aquí a mano: el paquete (de `src/`, solo sus `.py`,
# a cualquier profundidad, que es lo que `pip install .` instala), los pesos, el calibrador y el
# punto de entrada.
LO_QUE_LA_IMAGEN_COPIA = ("pyproject.toml", "src/**/*.py", "servidor/pesos_modelo_cpu.pt",
                          "servidor/calibrador.json", "servidor/arrancar.py")


def test_el_fichero_de_exclusiones_lleva_el_nombre_que_docker_lee():
    """El contexto es la raíz: Docker solo lee un `.dockerignore` de la RAÍZ, o
    `<dockerfile>.dockerignore` junto al Dockerfile. Un `servidor/.dockerignore` se ignora en
    silencio (comprobado en SP2: con él, `tests/` seguía entrando)."""
    assert EXCLUSIONES.is_file()
    assert not (REPO / "servidor" / ".dockerignore").exists()


def test_el_contexto_es_una_lista_blanca_de_lo_que_copia_el_dockerfile():
    reglas = _reglas(EXCLUSIONES)
    assert reglas[0] == "*", "la primera regla tiene que excluirlo todo"
    readmitidas = [r[1:] for r in reglas if r.startswith("!")]
    assert sorted(readmitidas) == sorted(LO_QUE_LA_IMAGEN_COPIA), (
        f"readmitidas de más: {sorted(set(readmitidas) - set(LO_QUE_LA_IMAGEN_COPIA))}; "
        f"faltan: {sorted(set(LO_QUE_LA_IMAGEN_COPIA) - set(readmitidas))}")
    # Todo lo readmitido existe (menos los pesos, que no se versionan; y `src/**/*.py` es un
    # patrón, que tiene que casar con algo)...
    for ruta in readmitidas:
        if ruta == "servidor/pesos_modelo_cpu.pt":
            continue
        casan = list(REPO.glob(ruta)) if "*" in ruta else [REPO / ruta]
        assert casan and all(c.exists() for c in casan), f"se readmite {ruta}, que no existe"
    # ...y el Dockerfile y el contexto se corresponden: nada readmitido que ningún COPY copie,
    # y ningún COPY que no copie nada de lo readmitido.
    def bajo(ruta, base):
        return ruta == base or ruta.startswith(base + "/")
    origenes = {origen for origen, _ in _copias(DOCKERFILE)}
    for ruta in readmitidas:
        assert any(bajo(ruta, o) for o in origenes), f"ningún COPY copia {ruta}"
    for origen in origenes:
        assert any(bajo(r, origen) for r in readmitidas), f"el COPY de {origen} no copia nada"


# Un árbol de juguete con la forma del repositorio: lo que la imagen necesita y SEÑUELOS de lo
# que no puede llegar al demonio, también dentro de `src/` y de `servidor/`.
ENTRAN = {
    "pyproject.toml", "src/paquete/__init__.py", "src/paquete/modulo.py",
    "src/paquete/subpaquete/__init__.py", "src/paquete/subpaquete/modulo.py",
    "servidor/pesos_modelo_cpu.pt", "servidor/calibrador.json", "servidor/arrancar.py",
}
NO_ENTRAN = {
    # los señuelos del encargo
    "servidor/.env", "pruebas/corpus/01-positiva_clara/caso.txt",
    "pruebas/corpus/_fabricados/truncado-FABRICADO.dcm", "pruebas/crudas_prueba.csv",
    "pruebas/sesion/respuestas.csv", "n8n/valores.local.json", ".superpowers/nota.md",
    ".superpowers/sdd/tarea/report.md",
    # y lo demás del repositorio, que la imagen no copia
    ".git/HEAD", ".gitignore", "README.md", ".env", "docs/informe.md", "tests/test_algo.py",
    "notebooks/uno.ipynb", "scripts/uno.py", "bd/esquema.sql", "n8n/copiloto-profesional.json",
    "app/app.py", "app/assets/ejemplos/normal_pa.dcm", "servidor/Dockerfile",
    "servidor/Dockerfile.dockerignore", "servidor/docker-compose.yml",
    "servidor/.env.ejemplo", "servidor/medir_latencia.py", "servidor/notas.md",
    "servidor/otro_calibrador.json",
    # dentro de `src/`, donde solo entran los `.py`: lo que alguien suelta para probar
    "src/paquete/clave.pem", "src/paquete/credentials.json", "src/paquete/datos.csv",
    "src/notas.md", "src/paquete/__pycache__/modulo.cpython-312.pyc",
    "src/paquete.egg-info/PKG-INFO", "src/paquete/.git/HEAD", "src/paquete/.env",
    # y los `.py` que hay DENTRO de carpetas que no entran nunca: la exclusión de la carpeta
    # sola no los alcanza (BuildKit, medido para la app), y las reglas `/**`, sí
    "src/paquete/__pycache__/cache.py", "src/paquete.egg-info/setup.py",
    "src/otro/.git/gancho.py", "src/otro/.env/entorno.py",
}

SIN_VERIFICAR_EL_CONTEXTO = (
    "CONTEXTO DE LA CONSTRUCCIÓN DEL SERVIDOR SIN VERIFICAR: {motivo}. Arranca Docker (con "
    "BuildKit) y repite.")


def test_el_contexto_de_la_construccion_del_servidor_es_solo_la_lista_blanca(tmp_path):
    """Con BuildKit de verdad y no con una lectura del fichero: un Dockerfile de usar y tirar,
    `FROM scratch` + `COPY`, con una copia exacta de servidor/Dockerfile.dockerignore al lado,
    que es donde Docker la busca, sobre el árbol de juguete. `--output` vuelca lo que llegó a
    una carpeta, sin crear ninguna imagen. Con BuildKit puesto a la fuerza: el fichero de
    exclusiones de un Dockerfile concreto solo lo lee BuildKit (por defecto desde Docker 23);
    el constructor antiguo manda el contexto entero."""
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
                f"type=local,dest={salida}", str(arbol), timeout=180,
                env={**os.environ, "DOCKER_BUILDKIT": "1"})
    assert r.returncode == 0, f"la construcción de usar y tirar falló:\n{r.stderr}"
    llegaron = {p.relative_to(salida / "ctx").as_posix()
                for p in (salida / "ctx").rglob("*") if p.is_file()}
    assert llegaron == ENTRAN, (
        f"llegaron de más: {sorted(llegaron - ENTRAN)}; faltan: {sorted(ENTRAN - llegaron)}")
