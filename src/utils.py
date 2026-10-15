"""Funciones auxiliares de la capa del curso: rutas, registro y carga de guiones.

QUÉ ES. El `utils.py` que pide la estructura del curso. Reúne lo que los otros
módulos de `src/` comparten y no merece vivir en cada uno: la raíz del
repositorio, las rutas por defecto (siempre relativas a ella, nunca absolutas), la
configuración del registro de eventos y el cargador de los guiones de `scripts/` y
`app/`, que no son paquetes.

DÓNDE ESTÁ LA IMPLEMENTACIÓN. En `src/copiloto_triaje/`. Aquí solo se reexporta lo
que el curso espera encontrar en un módulo de utilidades:

- `Config`, `ARQUITECTURAS`, `raiz_rsna`  <- `copiloto_triaje.config`
- `fijar_semillas`                        <- `copiloto_triaje.modelo.entrenamiento`
  (se importa al usarla, no al importar este módulo: arrastra torch)

Las rutas de los datos preparados NO tienen valor por defecto: salen de la variable
de entorno `RSNA_RAIZ` (ver `data/README.md`).
"""
from __future__ import annotations

import hashlib
import importlib.util
import logging
import sys
from pathlib import Path

from copiloto_triaje.config import ARQUITECTURAS, Config, raiz_rsna

__all__ = [
    "ARQUITECTURAS", "Config", "raiz_rsna", "RAIZ", "PESOS_DESPLEGADOS",
    "CALIBRADOR_DESPLEGADO", "PUNTUACIONES_DE_PRUEBA", "METRICAS_PUBLICADAS",
    "DIR_RESULTADOS", "registro", "cargar_guion", "ejecutar_guion", "configurar_registro",
    "fijar_semillas", "sha256_de",
]

# `src/utils.py` -> `src/` -> la raíz del repositorio.
RAIZ = Path(__file__).resolve().parents[1]

# Lo que el repositorio versiona (las rutas, relativas a la raíz).
CALIBRADOR_DESPLEGADO = RAIZ / "servidor" / "calibrador.json"
PUNTUACIONES_DE_PRUEBA = RAIZ / "docs" / "validacion-semisintetica" / "crudas_prueba.csv"
METRICAS_PUBLICADAS = RAIZ / "app" / "assets" / "metricas.json"
DIR_RESULTADOS = RAIZ / "results"
# Los pesos NO viajan en git (se publican como descarga del release): `models/README.md`
# dice cómo bajarlos. Si se descargan en `models/`, esa carpeta tiene prioridad; si no,
# se usa la copia de `servidor/`, que es la que empaquetan las imágenes de Docker.
_PESOS_EN_MODELS = RAIZ / "models" / "pesos_modelo_cpu.pt"
_PESOS_EN_SERVIDOR = RAIZ / "servidor" / "pesos_modelo_cpu.pt"
PESOS_DESPLEGADOS = _PESOS_EN_MODELS if _PESOS_EN_MODELS.is_file() else _PESOS_EN_SERVIDOR

registro = logging.getLogger("copiloto")


def configurar_registro(detallado: bool = False) -> logging.Logger:
    """Deja el registro de eventos listo: hora, nivel y mensaje, por la salida de errores.

    Idempotente: llamarlo dos veces no duplica los mensajes. `detallado` sube de
    INFO a DEBUG."""
    logging.basicConfig(
        level=logging.DEBUG if detallado else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
        stream=sys.stderr)
    # matplotlib cuenta en INFO cosas que no son del proyecto (la caché de tipos de letra)
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    return registro


def sha256_de(ruta) -> str:
    """El SHA-256 de los bytes de un fichero (los pesos, por ejemplo), leído por bloques."""
    huella = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            huella.update(bloque)
    return huella.hexdigest()


def cargar_guion(ruta_relativa: str):
    """Carga por ruta un guion de `scripts/` o de `app/` (que no son paquetes) y
    devuelve el módulo, para llamar a sus funciones sin copiarlas.

    `ruta_relativa` va desde la raíz del repositorio, p. ej. `scripts/entrenar_local.py`.
    Lanza `FileNotFoundError`, con la ruta buscada, si el guion no está: es lo que
    pasa si se ejecuta una copia incompleta del repositorio."""
    ruta = RAIZ / ruta_relativa
    if not ruta.is_file():
        raise FileNotFoundError(
            f"no está el guion {ruta_relativa} en {RAIZ.name}/: este módulo lo llama "
            "en vez de copiarlo, y sin él no hay nada que ejecutar")
    nombre = f"_guion_{ruta.stem}"
    if nombre in sys.modules:
        return sys.modules[nombre]
    especificacion = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    # Se registra ANTES de ejecutarlo: los `dataclass` y los `NamedTuple` del guion
    # buscan su módulo en `sys.modules`.
    sys.modules[nombre] = modulo
    try:
        especificacion.loader.exec_module(modulo)
    except BaseException:
        sys.modules.pop(nombre, None)
        raise
    return modulo


def ejecutar_guion(ruta_relativa: str, argv=None, prog: str | None = None) -> int:
    """Ejecuta el `main()` de un guion de `scripts/` con estos argumentos y devuelve su
    código de salida (0 si no devuelve nada).

    Los guiones leen `sys.argv` (argparse): se le pone `[prog, *argv]` mientras corre y se
    restaura al terminar, también si falla. `argv=None` toma los de la línea de órdenes
    actual. `--help` o un argumento mal puesto salen con `SystemExit`, como siempre."""
    guion = cargar_guion(ruta_relativa)
    anteriores = sys.argv
    argumentos = anteriores[1:] if argv is None else list(argv)
    sys.argv = [prog or Path(ruta_relativa).name, *argumentos]
    try:
        salida = guion.main()
    finally:
        sys.argv = anteriores
    return 0 if salida is None else int(salida)


def fijar_semillas(semilla: int) -> None:
    """Fija las semillas de Python, NumPy y torch (`copiloto_triaje.modelo.entrenamiento`).

    Es la misma función; solo se importa al llamarla porque ese módulo trae torch."""
    from copiloto_triaje.modelo.entrenamiento import fijar_semillas as _fijar
    _fijar(semilla)
