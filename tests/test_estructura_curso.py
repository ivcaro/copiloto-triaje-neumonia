"""La estructura que pide el curso y los enlaces de la documentación (SP5-C2, spec §7).

QUÉ VIGILA.

- Que existe todo lo de la «Estructura de carpetas requerida» de la entrega final
  (`PROYECTO_FINAL_descripcion_2026.pdf`): los ficheros de la raíz, los seis documentos de
  `docs/`, `data/` con `raw/` y `processed/`, los cinco notebooks, los seis módulos de `src/`,
  `models/README.md`, `app/` con su `requirements.txt` y `assets/`, las tres pruebas del curso y
  las tres carpetas de `results/`.
- La ÚNICA adaptación: el curso muestra `models/best_model.pkl` y `models/model_v1.pkl`,
  pensando en scikit-learn. Este modelo es una red de PyTorch, sus pesos son un `state_dict`
  (`pesos_modelo_cpu.pt`) que no va en git (se descarga), y las versiones anteriores son las
  corridas de `docs/comparativa-corridas.md`. Lo que hay en su lugar es `models/README.md`, que
  lo explica; la prueba exige que lo explique.
- Que el README tiene las 14 secciones del curso, en su orden.
- Que cada enlace relativo del README, de `docs/*.md` y de los README de la capa del curso
  (`data/`, `models/`, `results/`) lleva a un fichero o carpeta que existe y, si apunta a una
  sección (`#...`), que esa sección existe (con la regla con que GitHub hace las anclas).

QUÉ NO VIGILA. Los enlaces externos (`https://...`) no se visitan: la suite no sale a la red.
Los documentos de diseño de `docs/superpowers/` no se miran: son el registro de cada
sub-proyecto, con las rutas de su momento.
"""
import re
import sys
import urllib.parse
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"

# La estructura del curso, fichero a fichero (salvo los `.pkl` de `models/`: ver arriba).
FICHEROS_DEL_CURSO = (
    "README.md", "requirements.txt", ".gitignore", "LICENSE",
    "docs/planificacion.md", "docs/analisis_datos.md", "docs/arquitectura.md",
    "docs/optimizacion.md", "docs/consideraciones_eticas.md", "docs/manual_usuario.md",
    "data/README.md",
    "notebooks/01_exploracion.ipynb", "notebooks/02_preprocesamiento.ipynb",
    "notebooks/03_modelado.ipynb", "notebooks/04_optimizacion.ipynb",
    "notebooks/05_evaluacion.ipynb",
    "src/__init__.py", "src/data_processing.py", "src/model.py", "src/train.py",
    "src/evaluate.py", "src/utils.py",
    "models/README.md",
    "app/app.py", "app/requirements.txt",
    "tests/test_data_processing.py", "tests/test_model.py", "tests/test_app.py",
)
CARPETAS_DEL_CURSO = (
    "docs", "data", "data/raw", "data/processed", "notebooks", "src", "models", "app",
    "app/assets", "tests", "results", "results/figures", "results/metrics", "results/reports",
)
# Las carpetas que el curso pide y que aquí van vacías a propósito (los datos no se
# redistribuyen): git no guarda carpetas vacías, así que llevan un `.gitkeep`.
CARPETAS_VACIAS = ("data/raw", "data/processed")
# Lo que el curso muestra y aquí se sustituye, y por qué fichero.
ADAPTACIONES = {"models/best_model.pkl": "models/README.md",
                "models/model_v1.pkl": "models/README.md"}

# Las 14 secciones del README que pide el curso, en su orden. La primera (encabezado y
# badges) es el título; las otras trece, las secciones de segundo nivel.
SECCIONES_DEL_README = (
    "Tabla de contenidos", "Descripción del problema", "Dataset", "Metodología",
    "Resultados", "Instalación y uso", "Interfaz de usuario", "Estructura del proyecto",
    "Consideraciones éticas", "Autores y contribuciones", "Licencia",
    "Agradecimientos y referencias", "Videos",
)


# --------------------------------------------------------------------------
# La estructura
# --------------------------------------------------------------------------
def test_existen_los_ficheros_de_la_estructura_del_curso():
    faltan = [f for f in FICHEROS_DEL_CURSO if not (REPO / f).is_file()]
    assert faltan == []


def test_existen_las_carpetas_de_la_estructura_del_curso():
    faltan = [c for c in CARPETAS_DEL_CURSO if not (REPO / c).is_dir()]
    assert faltan == []
    # Las vacías llevan su `.gitkeep`, para que existan también en un clon.
    sin_gitkeep = [c for c in CARPETAS_VACIAS if not (REPO / c / ".gitkeep").is_file()]
    assert sin_gitkeep == []
    # Las de `results/` no están vacías: llevan lo que escribe `src/evaluate.py`.
    vacias = [c for c in ("results/figures", "results/metrics", "results/reports")
              if not any(p.is_file() for p in (REPO / c).iterdir())]
    assert vacias == []


def test_los_pkl_del_curso_se_sustituyen_por_el_readme_de_models():
    """`models/README.md` hace el papel de `best_model.pkl` y `model_v1.pkl`: dice qué es el
    modelo, por qué es `.pt` y no `.pkl`, de dónde bajarlo y dónde están las versiones
    anteriores. Los pesos no van en git."""
    for del_curso, en_su_lugar in ADAPTACIONES.items():
        assert not (REPO / del_curso).exists(), del_curso
        assert (REPO / en_su_lugar).is_file(), en_su_lugar
    texto = (REPO / "models" / "README.md").read_text(encoding="utf-8")
    for necesario in ("best_model.pkl", "pesos_modelo_cpu.pt", "Por qué `.pt` y no `.pkl`",
                      "docs/comparativa-corridas.md", "SHA-256"):
        assert necesario in texto, necesario


def test_el_readme_tiene_las_14_secciones_del_curso_en_su_orden():
    texto = README.read_text(encoding="utf-8")
    lineas = _fuera_de_bloques_de_codigo(texto)
    titulos = [(n, m.group(1), m.group(2).strip()) for n, linea in lineas
               if (m := re.match(r"(#{1,6})\s+(.*)", linea))]
    # 1. Encabezado: el título es lo primero, y los badges van antes de la primera sección.
    assert titulos[0][1] == "#" and titulos[0][0] == 1
    primera_seccion = next(n for n, nivel, _ in titulos if nivel == "##")
    badges = [n for n, linea in lineas if "img.shields.io/badge/" in linea]
    assert badges and max(badges) < primera_seccion
    # 2 a 14, en su orden y sin otras secciones de segundo nivel entre ellas.
    assert [t for _, nivel, t in titulos if nivel == "##"] == list(SECCIONES_DEL_README)


def test_la_tabla_de_contenidos_del_readme_enlaza_cada_seccion():
    texto = README.read_text(encoding="utf-8")
    tabla = texto.split("## Tabla de contenidos", 1)[1].split("\n## ", 1)[0]
    anclas = re.findall(r"\]\(#([^)]+)\)", tabla)
    assert anclas == [_ancla(s) for s in SECCIONES_DEL_README[1:]]


def test_el_readme_enlaza_los_dos_videos_de_la_version_v1_2():
    """Los dos videos van adjuntos a la versión v1.2, no dentro del repositorio."""
    texto = README.read_text(encoding="utf-8")
    videos = texto.split("\n## Videos", 1)[1].split("\n## ", 1)[0]
    # La cuenta solo se nombra en el README (D5): la dirección se toma de su línea del repositorio.
    repositorio = re.search(r"\*\*Repositorio:\*\* <(https://github\.com/[^>]+)>", texto).group(1)
    descarga = repositorio + "/releases/download/v1.2/"
    assert re.findall(r"<(https://[^>]+\.mp4)>", videos) == [descarga + "Video_pitch.mp4",
                                                             descarga + "Video_preguntas.mp4"]
    assert "se añadirá" not in videos


# --------------------------------------------------------------------------
# Los enlaces
# --------------------------------------------------------------------------
def _fuera_de_bloques_de_codigo(texto: str) -> list[tuple[int, str]]:
    """(número, línea) de las líneas que no están dentro de un bloque ``` o ~~~."""
    lineas, dentro = [], None
    for n, linea in enumerate(texto.splitlines(), 1):
        marca = re.match(r"\s*(```|~~~)", linea)
        if marca:
            if dentro is None:
                dentro = marca.group(1)
            elif marca.group(1) == dentro:
                dentro = None
            continue
        if dentro is None:
            lineas.append((n, linea))
    return lineas


def _ancla(titulo: str) -> str:
    """El ancla que GitHub da a un título: minúsculas; sin el formato que no se ve (enlaces,
    código, énfasis con `*`); sin la puntuación salvo `-` y `_`; espacios a `-`. Las letras
    con tilde se quedan."""
    texto = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", titulo.strip())
    texto = texto.replace("`", "").replace("*", "").lower()
    texto = re.sub(r"[^\w\- ]", "", texto)
    return texto.replace(" ", "-")


def _anclas(ruta: Path) -> set[str]:
    """Las anclas de un Markdown: las de sus títulos (con `-1`, `-2`... si se repiten, como
    GitHub) y las explícitas (`<a id="...">` o `name`)."""
    texto = ruta.read_text(encoding="utf-8")
    anclas, vistas = set(), {}
    for _n, linea in _fuera_de_bloques_de_codigo(texto):
        m = re.match(r"(#{1,6})\s+(.*?)\s*#*\s*$", linea)
        if m:
            base = _ancla(m.group(2))
            veces = vistas.get(base, 0)
            vistas[base] = veces + 1
            anclas.add(base if veces == 0 else f"{base}-{veces}")
    anclas |= set(re.findall(r"<a\s+(?:id|name)=\"([^\"]+)\"", texto))
    return anclas


ENLACE = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")


def _enlaces(ruta: Path) -> list[tuple[int, str]]:
    """(línea, destino) de cada enlace o imagen en línea de un Markdown, sin los de los
    bloques de código ni los de dentro de un `código en línea`."""
    enlaces = []
    for n, linea in _fuera_de_bloques_de_codigo(ruta.read_text(encoding="utf-8")):
        sin_codigo = re.sub(r"`[^`]*`", "", linea)
        enlaces += [(n, m.group(1)) for m in ENLACE.finditer(sin_codigo)]
    return enlaces


def _documentos_con_enlaces() -> list[Path]:
    documentos = [README, *sorted((REPO / "docs").glob("*.md"))]
    documentos += [REPO / r for r in ("data/README.md", "models/README.md",
                                      "results/README.md", "results/reports/README.md")]
    return documentos


def _enlaces_rotos(ruta: Path) -> list[str]:
    """Los enlaces relativos de `ruta` que no llevan a nada: «línea: destino (motivo)»."""
    rotos = []
    for n, destino in _enlaces(ruta):
        if re.match(r"[a-z][a-z0-9+.-]*:", destino, re.I):     # https:, mailto:...
            continue
        camino, _, ancla = urllib.parse.unquote(destino).partition("#")
        objetivo = (ruta.parent / camino).resolve() if camino else ruta
        if REPO not in objetivo.parents and objetivo != REPO:
            rotos.append(f"{n}: {destino} (sale del repositorio)")
        elif not objetivo.exists():
            rotos.append(f"{n}: {destino} (no existe)")
        elif ancla and objetivo.suffix == ".md" and ancla not in _anclas(objetivo):
            rotos.append(f"{n}: {destino} (no existe la sección)")
    return rotos


def test_los_documentos_que_se_miran_existen():
    faltan = [p.relative_to(REPO).as_posix() for p in _documentos_con_enlaces()
              if not p.is_file()]
    assert faltan == []
    assert len(_documentos_con_enlaces()) > 15


@pytest.mark.parametrize("documento", [p.relative_to(REPO).as_posix()
                                       for p in _documentos_con_enlaces()])
def test_los_enlaces_relativos_llevan_a_algo_que_existe(documento):
    rotos = _enlaces_rotos(REPO / documento)
    assert rotos == [], f"{documento}: " + "; ".join(rotos)


def test_el_buscador_de_enlaces_rotos_los_ve(tmp_path, monkeypatch):
    """La prueba de arriba no vale si no ve un enlace roto: se le dan unos de juguete."""
    raiz = tmp_path.resolve()
    monkeypatch.setattr(sys.modules[__name__], "REPO", raiz)
    (raiz / "docs").mkdir()
    (raiz / "docs" / "otro.md").write_text("# Otro\n\n## 2. Una sección *con* énfasis\n",
                                           encoding="utf-8")
    doc = raiz / "docs" / "doc.md"
    doc.write_text(
        "# Doc\n\n## Sección propia\n\n"
        "[bien](otro.md) [bien](otro.md#2-una-sección-con-énfasis) [bien](#sección-propia)\n"
        "[mal](falta.md) [mal](otro.md#no-existe) [mal](#tampoco)\n"
        "![mal](../figura.png) [fuera](https://ejemplo.test/x) `[no](es-codigo.md)`\n"
        "[fuera del repositorio](../../otro-sitio.md)\n"
        "```\n[no](dentro-de-un-bloque.md)\n```\n",
        encoding="utf-8")
    rotos = _enlaces_rotos(doc)
    assert rotos == ["6: falta.md (no existe)", "6: otro.md#no-existe (no existe la sección)",
                     "6: #tampoco (no existe la sección)", "7: ../figura.png (no existe)",
                     "8: ../../otro-sitio.md (sale del repositorio)"]


def test_el_ancla_es_la_de_github():
    assert _ancla("5. Equidad y *fairness*") == "5-equidad-y-fairness"
    assert _ancla("4.2. El servidor de inferencia (`copiloto-mcp`)") == (
        "42-el-servidor-de-inferencia-copiloto-mcp")
    assert _ancla("17. Lo que falta antes de cualquier uso clínico") == (
        "17-lo-que-falta-antes-de-cualquier-uso-clínico")
    assert _ancla("B.3. El bot del profesional") == "b3-el-bot-del-profesional"
