"""Evaluación en el conjunto de prueba: métricas globales y por subgrupo, y las figuras.

QUÉ ES. El `evaluate.py` que pide la estructura del curso. Parte de las puntuaciones
congeladas del modelo sobre las 3 811 placas de PRUEBA y escribe, en agregados:

    results/metrics/metricas_prueba.json   AUC, sensibilidad (recall) y especificidad con su
                                           intervalo de Wilson, globales y en 13 subgrupos; el
                                           efecto del umbral por vista; y la calibración
    results/figures/roc_prueba.png         curva ROC: todas las placas, PA y AP
    results/figures/calibracion.png        fiabilidad de la puntuación cruda y de la calibrada
    results/figures/subgrupos.png          sensibilidad y especificidad por subgrupo, con su IC

Ni el JSON ni las figuras llevan una fila por paciente.

DÓNDE ESTÁ LA IMPLEMENTACIÓN. Las cuentas NO se reescriben aquí:

- `app/generar_metricas.py`  el AUC (Mann-Whitney), los intervalos de Wilson, el recall y la
  especificidad con el umbral global y por vista, y los 13 subgrupos de la tabla 2 del workshop
  S4. Es el guion que escribe `app/assets/metricas.json`, y este módulo lo llama: por eso los
  números de `metricas_prueba.json` son los de «Acerca de» de la app (una prueba lo comprueba).
- `copiloto_triaje.validacion.metricas`  Brier, pendiente e intercepto de calibración, ECE con
  su suelo de ruido y la curva de fiabilidad. Los empates de la ECE se rompen por el rango del
  identificador de la placa (`simulacion.rango_de_los_ids`), como en la simulación
  semisintética, para que las dos publiquen la misma cifra.
- `copiloto_triaje.servicio.calibracion`  el calibrador isotónico desplegado
  (`servidor/calibrador.json`), que convierte la puntuación cruda en probabilidad.

Lo único propio de este módulo es dibujar.

USO, desde la raíz del repositorio:

    python -m src.evaluate                       # escribe results/
    python -m src.evaluate --salida otra/carpeta
    python -m src.evaluate --sin-figuras         # solo el JSON (no hace falta matplotlib)

Las puntuaciones congeladas están en `docs/validacion-semisintetica/crudas_prueba.csv`, con el
`.sha256` de los pesos que las generaron al lado; si no están en tu copia del repositorio, el
guion lo dice y sale con 1 sin tocar `results/`. El umbral es el del servidor (0,4258) sobre la
puntuación cruda, y los del umbral por vista (PA 0,1798, AP 0,5815), apagado por defecto en el
sistema, son los de la tabla 3 del workshop S4; se cambian con `--umbral`, `--umbral-pa` y
`--umbral-ap`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve

from copiloto_triaje.servicio.calibracion import Calibrador
from copiloto_triaje.validacion import metricas as metricas_de_validacion
from copiloto_triaje.validacion import simulacion

from .utils import (
    CALIBRADOR_DESPLEGADO, DIR_RESULTADOS, PESOS_DESPLEGADOS, PUNTUACIONES_DE_PRUEBA, RAIZ,
    cargar_guion, configurar_registro, registro,
)

__all__ = [
    "ErrorDeEvaluacion", "calcular_calibracion", "evaluar", "dibujar_roc",
    "dibujar_calibracion", "dibujar_subgrupos", "leer_puntuaciones", "main",
]

NOMBRE_JSON = "metricas_prueba.json"
NOMBRES_DE_LAS_FIGURAS = ("roc_prueba.png", "calibracion.png", "subgrupos.png")
GUION_DE_METRICAS = "app/generar_metricas.py"
COLUMNAS_QUE_SE_LEEN = ("patientId", "etiqueta", "cruda", "vista")


class ErrorDeEvaluacion(Exception):
    """Lo que impide evaluar y se le puede decir a quien ejecuta: falta un fichero, falta
    matplotlib. `main` lo convierte en un mensaje y en el código de salida 1."""


def _guion_de_metricas():
    """El guion que ya calcula las métricas (`app/generar_metricas.py`), cargado por ruta."""
    return cargar_guion(GUION_DE_METRICAS)


def _relativa(ruta) -> str:
    try:
        return Path(ruta).resolve().relative_to(RAIZ).as_posix()
    except ValueError:
        return Path(ruta).name


# --------------------------------------------------------------------------
# Las cuentas
# --------------------------------------------------------------------------
def _exigir_las_puntuaciones(ruta_crudas) -> Path:
    ruta = Path(ruta_crudas)
    if not ruta.is_file():
        raise ErrorDeEvaluacion(
            f"faltan las puntuaciones congeladas de prueba ({_relativa(ruta)}): son lo único "
            "que este guion necesita, y las puntuaciones por placa pueden no viajar al "
            "repositorio público. results/ conserva lo que se generó con ellas")
    return ruta


def leer_puntuaciones(ruta_crudas=PUNTUACIONES_DE_PRUEBA) -> pd.DataFrame:
    """Lo que hace falta para medir y dibujar: etiqueta, puntuación cruda y vista, y el
    `orden` (el rango del identificador de la placa, que rompe los empates de la ECE).
    El identificador se lee para calcular ese rango y no se conserva: el resultado no
    lleva nada que señale una placa."""
    ruta = _exigir_las_puntuaciones(ruta_crudas)
    placas = pd.read_csv(ruta, usecols=list(COLUMNAS_QUE_SE_LEEN))
    placas["vista"] = placas["vista"].astype(str).str.strip().str.upper()
    placas["orden"] = simulacion.rango_de_los_ids(placas.pop("patientId"))
    return placas


def _redondeado(valor, decimales: int):
    """Los números con los mismos decimales que `app/assets/metricas.json`, en cualquier
    profundidad; lo que no es un número (None, texto) se queda como está."""
    if isinstance(valor, dict):
        return {k: _redondeado(v, decimales) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_redondeado(v, decimales) for v in valor]
    if isinstance(valor, (float, np.floating)):
        return round(float(valor), decimales)
    if isinstance(valor, (int, np.integer)):
        return int(valor)
    return valor


def calcular_calibracion(placas: pd.DataFrame, ruta_calibrador=CALIBRADOR_DESPLEGADO) -> dict:
    """La calibración de la puntuación cruda y de la calibrada con el calibrador desplegado.

    Brier, pendiente, intercepto, ECE (con su suelo de ruido: la ECE de un modelo perfectamente
    calibrado con estas mismas probabilidades) y la curva de fiabilidad en deciles de igual
    masa: todo de `copiloto_triaje.validacion.metricas`. Los empates de probabilidad (el
    calibrador isotónico deja 674 valores distintos entre 3 811 placas) se rompen por el rango
    del identificador de la placa, igual que en la simulación semisintética: la ECE depende de
    cómo se rompen los empates, y así las dos publican la misma cifra.

    La puntuación cruda NO es una probabilidad (el modelo se entrenó con las positivas
    ponderadas): se mide para ver qué corrige el calibrador, no como producto."""
    ruta = Path(ruta_calibrador)
    if not ruta.is_file():
        raise ErrorDeEvaluacion(f"falta el calibrador desplegado ({_relativa(ruta)})")
    y = placas["etiqueta"].to_numpy().astype(int)
    cruda = placas["cruda"].to_numpy().astype(float)
    calibrador = Calibrador.desde_json(ruta)
    calibrada = np.array([calibrador.calibrar(c) for c in cruda])
    orden = placas["orden"].to_numpy().astype(int)
    m = metricas_de_validacion

    def bloque(p):
        return {
            "brier": m.brier(y, p),
            "ece": m.ece(y, p, orden),
            "ece_suelo": m.suelo_de_ece(p, orden),
            "pendiente": m.pendiente_de_calibracion(y, p),
            "intercepto": m.intercepto_de_calibracion(y, p),
            "fiabilidad": m.fiabilidad(y, p, orden),
        }

    return _redondeado({
        "grupos": m.BINS,
        "prevalencia_observada": float(y.mean()),
        "cruda": bloque(cruda),
        "calibrada": bloque(calibrada),
    }, _guion_de_metricas().DECIMALES)


def evaluar(ruta_crudas=PUNTUACIONES_DE_PRUEBA, ruta_calibrador=CALIBRADOR_DESPLEGADO,
            ruta_pesos=PESOS_DESPLEGADOS, umbral: float | None = None,
            umbrales_por_vista=None, generado: str | None = None) -> dict:
    """Todos los agregados, como diccionario: lo que `app/generar_metricas.py` escribe en
    `metricas.json` (global, subgrupos, umbral por vista, con las huellas de los pesos y de las
    puntuaciones) y, además, la calibración. Sin umbrales, los del servidor."""
    guion = _guion_de_metricas()
    ruta_crudas = _exigir_las_puntuaciones(ruta_crudas)
    try:
        agregados = guion.generar(
            ruta_crudas, guion.UMBRAL if umbral is None else umbral,
            guion.UMBRALES_POR_VISTA if umbrales_por_vista is None else umbrales_por_vista,
            ruta_pesos, generado=generado)
    except (ValueError, OSError) as error:
        raise ErrorDeEvaluacion(str(error)) from error
    agregados["calibracion"] = calcular_calibracion(leer_puntuaciones(ruta_crudas),
                                                    ruta_calibrador)
    return agregados


# --------------------------------------------------------------------------
# Las figuras
#
# matplotlib es el extra `figuras` del pyproject, no una dependencia del paquete
# `copiloto_triaje`: las imágenes de Docker lo instalan sin él, y
# `tests/test_informe.py::test_nada_del_paquete_importa_matplotlib` vigila que ningún módulo
# de ese paquete lo importe. Este módulo es de la capa del curso, no del paquete (ni el
# servidor ni la app lo instalan): importa matplotlib con un `import` normal, pero dentro de
# `_matplotlib`, al dibujar, para que `--sin-figuras` funcione también donde no está.
#
# Los colores son los de las figuras de la validación semisintética (azul, naranja y
# morado: comprobados contra el daltonismo), y la identidad de cada serie no depende del
# color: cada una lleva su marca, su ancho y su rótulo.
# --------------------------------------------------------------------------
DPI = 200
TINTA = "#0b0b0b"
TINTA_SUAVE = "#52514e"
REJILLA = "#d9d8d3"
DIAGONAL = "#7a7974"
AZUL = "#2a78d6"
NARANJA = "#eb6834"
MORADO = "#4a3aa7"

ESTILO = {
    "font.size": 10, "axes.labelsize": 10.5, "text.color": TINTA, "axes.labelcolor": TINTA,
    "axes.edgecolor": TINTA_SUAVE, "axes.linewidth": 0.8, "xtick.color": TINTA_SUAVE,
    "ytick.color": TINTA_SUAVE, "axes.spines.top": False, "axes.spines.right": False,
    "grid.color": REJILLA, "grid.linewidth": 0.7, "legend.frameon": False,
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
}


def _matplotlib():
    """(matplotlib, pyplot, ticker), con el motor «Agg» (sin ventana)."""
    try:
        import matplotlib
    except ModuleNotFoundError as error:
        if error.name != "matplotlib":
            raise
        raise ErrorDeEvaluacion(
            "para dibujar las figuras hace falta matplotlib (pip install -r requirements.txt); "
            "sin él, usa --sin-figuras y se escribe solo el JSON") from None
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    return matplotlib, plt, ticker


def _coma(valor, decimales: int) -> str:
    """La cifra con coma decimal; «n/d» si no hay cifra."""
    if valor is None or valor != valor:
        return "n/d"
    return f"{valor:.{decimales}f}".replace(".", ",")


def _porcentaje(valor, decimales: int = 1) -> str:
    return "n/d" if valor is None else f"{_coma(100 * valor, decimales)} %"


def _miles(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _formateador_de_porcentaje(ticker):
    return ticker.FuncFormatter(lambda valor, _: f"{valor * 100:.0f} %")


def _titulo(fig, titulo: str, subtitulo: str, y: float = 0.965) -> None:
    fig.text(0.02, y, titulo, fontsize=13, fontweight="bold", ha="left", va="top")
    fig.text(0.02, y - 0.04, subtitulo, fontsize=9.5, color=TINTA_SUAVE, ha="left", va="top")


def _guardar(mpl, plt, fig, destino, titulo: str) -> Path:
    """Los metadatos del PNG llevan el título y la versión de matplotlib (sin la dirección web
    que éste pone por defecto), como las figuras de `docs/validacion-semisintetica/`."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=DPI, metadata={"Title": titulo,
                                            "Software": f"matplotlib {mpl.__version__}"})
    plt.close(fig)
    return destino


def dibujar_roc(placas: pd.DataFrame, agregados: dict, destino) -> Path:
    """La curva ROC en prueba: todas las placas y, aparte, las PA y las AP (la proyección
    predice la etiqueta, y por eso cambia la curva), con el punto de operación del umbral
    global. Los AUC de la leyenda se calculan con `app/generar_metricas.py`."""
    mpl, plt, ticker = _matplotlib()
    guion = _guion_de_metricas()
    y_todas = placas["etiqueta"].to_numpy()
    s_todas = placas["cruda"].to_numpy()
    vistas = placas["vista"].to_numpy()
    series = (("Todas las placas", None, AZUL, 2.6, "-"),
              ("Placa PA (de pie)", "PA", NARANJA, 1.7, "-"),
              ("Placa AP (portátil)", "AP", MORADO, 1.7, "-"))
    with plt.rc_context(ESTILO):
        fig, ax = plt.subplots(figsize=(6.6, 6.5))
        ax.plot([0, 1], [0, 1], color=DIAGONAL, lw=1, ls=(0, (4, 3)), label="Azar (AUC 0,5)")
        for nombre, vista, color, ancho, trazo in series:
            dentro = np.ones(len(placas), dtype=bool) if vista is None else vistas == vista
            y, s = y_todas[dentro], s_todas[dentro]
            auc = guion.auc(y, s)
            if auc is None:
                continue
            fpr, tpr, _ = roc_curve(y, s)
            ax.plot(fpr, tpr, color=color, lw=ancho, ls=trazo,
                    label=f"{nombre}: AUC {_coma(auc, 3)} (n = {_miles(int(dentro.sum()))})")
        g = agregados["global"]
        ax.plot([1 - g["especificidad"]], [g["recall"]], ls="", marker="o", ms=10, mfc="white",
                mec=TINTA, mew=2, zorder=6,
                label=f"Umbral {_coma(agregados['umbral'], 4)}: sensibilidad "
                      f"{_porcentaje(g['recall'])}, especificidad {_porcentaje(g['especificidad'])}")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.grid(True, ls="--", alpha=0.6)
        for eje in (ax.xaxis, ax.yaxis):
            eje.set_major_formatter(_formateador_de_porcentaje(ticker))
        ax.set_xlabel("1 − especificidad (falsos positivos entre las placas sin opacidad)")
        ax.set_ylabel("Sensibilidad (positivas detectadas entre las que tienen opacidad)")
        ax.legend(loc="lower right", fontsize=8.6, handlelength=2.4)
        titulo = "Curva ROC en el conjunto de prueba"
        _titulo(fig, titulo, f"{_miles(g['n'])} placas, {_miles(g['positivos'])} con opacidad "
                             f"({_porcentaje(g['positivos'] / g['n'])})")
        fig.subplots_adjust(left=0.12, right=0.97, bottom=0.09, top=0.88)
        return _guardar(mpl, plt, fig, destino, titulo)


def dibujar_calibracion(agregados: dict, destino) -> Path:
    """El diagrama de fiabilidad: en cada décimo de las placas (por su probabilidad), la
    probabilidad media que da el modelo frente a la frecuencia de opacidades que se observa.
    La diagonal es la calibración perfecta."""
    mpl, plt, ticker = _matplotlib()
    cal = agregados["calibracion"]
    series = (("calibrada", "Calibrada (isotónica): la que usa el sistema", AZUL, "o", 2.4),
              ("cruda", "Puntuación cruda del modelo", NARANJA, "s", 1.7))
    with plt.rc_context(ESTILO):
        fig, ax = plt.subplots(figsize=(6.6, 6.5))
        ax.plot([0, 1], [0, 1], color=DIAGONAL, lw=1, ls=(0, (4, 3)),
                label="Calibración perfecta")
        for clave, nombre, color, marca, ancho in series:
            grupos = cal[clave]["fiabilidad"]
            ax.plot([b["p_media"] for b in grupos], [b["observada"] for b in grupos],
                    color=color, lw=ancho, marker=marca, ms=7, mec="white", mew=1,
                    label=f"{nombre}\n    ECE {_coma(cal[clave]['ece'], 3)} · "
                          f"Brier {_coma(cal[clave]['brier'], 3)}")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.grid(True, ls="--", alpha=0.6)
        for eje in (ax.xaxis, ax.yaxis):
            eje.set_major_formatter(_formateador_de_porcentaje(ticker))
        ax.set_xlabel("Probabilidad media que da el modelo")
        ax.set_ylabel("Frecuencia observada de opacidad")
        ax.legend(loc="upper left", fontsize=8.8, handlelength=2.4, labelspacing=0.9)
        titulo = "Calibración en el conjunto de prueba"
        n = agregados["global"]["n"]
        _titulo(fig, titulo,
                f"{cal['grupos']} grupos de igual tamaño, {_miles(n)} placas; prevalencia "
                f"observada {_porcentaje(cal['prevalencia_observada'])}")
        fig.subplots_adjust(left=0.12, right=0.97, bottom=0.09, top=0.88)
        return _guardar(mpl, plt, fig, destino, titulo)


def _familia(subgrupo) -> int:
    """A qué bloque de la tabla 2 pertenece un subgrupo: 0 todas las placas, 1 sexo, 2 edad,
    3 vista y 4 los cruces. Sirve para separar los bloques con una raya."""
    filtros = [subgrupo.sexo is not None, subgrupo.vista is not None,
               subgrupo.edad_desde is not None or subgrupo.edad_hasta is not None]
    if sum(filtros) == 0:
        return 0
    if sum(filtros) > 1:
        return 4
    return 1 if filtros[0] else 3 if filtros[1] else 2


def dibujar_subgrupos(agregados: dict, destino) -> Path:
    """Sensibilidad y especificidad de cada uno de los 13 subgrupos, con su intervalo de
    Wilson del 95 %. La raya discontinua es el valor de todas las placas."""
    mpl, plt, ticker = _matplotlib()
    familias = [_familia(s) for s in _guion_de_metricas().SUBGRUPOS]
    filas = agregados["subgrupos"]
    if len(familias) != len(filas):
        raise ErrorDeEvaluacion("los subgrupos del JSON no son los de app/generar_metricas.py")
    with plt.rc_context(ESTILO):
        fig, ejes = plt.subplots(1, 2, sharey=True, figsize=(11.8, 7.0),
                                 gridspec_kw={"wspace": 0.07})
        medidas = (("recall", "Sensibilidad (recall)", AZUL, "o"),
                   ("especificidad", "Especificidad", NARANJA, "s"))
        for eje, (clave, nombre, color, marca) in zip(ejes, medidas):
            intervalos = [f[f"{clave}_ic"] for f in filas if f[f"{clave}_ic"] is not None]
            inferior = max(0.0, min((ic[0] for ic in intervalos), default=0.0) - 0.04)
            superior = min(1.0, max((ic[1] for ic in intervalos), default=1.0) + 0.04)
            eje.axvline(agregados["global"][clave], color=DIAGONAL, lw=1.1, ls=(0, (4, 3)))
            for i, fila in enumerate(filas):
                if i and familias[i] != familias[i - 1]:
                    eje.axhline(i - 0.5, color=REJILLA, lw=0.9)
                if fila[clave] is None:
                    eje.text(inferior + 0.01, i, "sin placas positivas", va="center",
                             fontsize=8.5, color=TINTA_SUAVE)
                    continue
                a, b = fila[f"{clave}_ic"]
                eje.plot([a, b], [i, i], color=color, lw=2.2, solid_capstyle="round")
                eje.plot([fila[clave]], [i], ls="", marker=marca, ms=7.5, color=color,
                         mec="white", mew=1.2, zorder=4)
            eje.set_xlim(inferior, superior)
            eje.set_ylim(len(filas) - 0.5, -1.35)
            eje.xaxis.set_major_formatter(_formateador_de_porcentaje(ticker))
            eje.grid(True, axis="x", ls="--", alpha=0.6)
            eje.set_title(nombre, loc="left", fontsize=11, fontweight="bold", pad=6)
            eje.text(agregados["global"][clave], -0.95,
                     f"todas las placas: {_porcentaje(agregados['global'][clave])}",
                     ha="center", va="center", fontsize=8.5, color=TINTA_SUAVE,
                     bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5})
            eje.spines["left"].set_visible(False)
            eje.tick_params(axis="y", length=0)
        ejes[0].set_yticks(range(len(filas)))
        ejes[0].set_yticklabels([f"{f['nombre']}  (n = {_miles(f['n'])})" for f in filas],
                                fontsize=9.3)
        ejes[0].get_yticklabels()[0].set_fontweight("bold")
        g = agregados["global"]
        titulo = "Sensibilidad y especificidad por subgrupo, en el conjunto de prueba"
        _titulo(fig, titulo, f"{_miles(g['n'])} placas, {_miles(g['positivos'])} con opacidad. "
                             "Punto: valor; barra: intervalo de Wilson del 95 %.", y=0.975)
        fig.text(0.02, 0.012,
                 f"Umbral {_coma(agregados['umbral'], 4)} sobre la puntuación cruda. La "
                 "sensibilidad se mide sobre las placas con opacidad y la especificidad sobre "
                 "las que no la tienen.", fontsize=8.8, color=TINTA_SUAVE, ha="left", va="bottom")
        fig.subplots_adjust(left=0.24, right=0.98, bottom=0.09, top=0.86)
        return _guardar(mpl, plt, fig, destino, titulo)


# --------------------------------------------------------------------------
# La línea de órdenes
# --------------------------------------------------------------------------
def escribir_resultados(agregados: dict, placas: pd.DataFrame | None, salida,
                        con_figuras: bool = True) -> list[Path]:
    """Escribe el JSON en `<salida>/metrics/` y, si se piden, las tres figuras en
    `<salida>/figures/`. Devuelve las rutas escritas. Con figuras, comprueba antes que
    matplotlib está: sin él no se escribe nada a medias."""
    salida = Path(salida)
    if con_figuras:
        _matplotlib()
    escritas = [_guion_de_metricas().escribir(agregados, salida / "metrics" / NOMBRE_JSON)]
    if con_figuras:
        if placas is None:
            raise ErrorDeEvaluacion("para dibujar la curva ROC hacen falta las puntuaciones")
        figuras = salida / "figures"
        escritas.append(dibujar_roc(placas, agregados, figuras / NOMBRES_DE_LAS_FIGURAS[0]))
        escritas.append(dibujar_calibracion(agregados, figuras / NOMBRES_DE_LAS_FIGURAS[1]))
        escritas.append(dibujar_subgrupos(agregados, figuras / NOMBRES_DE_LAS_FIGURAS[2]))
    return escritas


def _parser() -> argparse.ArgumentParser:
    guion = _guion_de_metricas()
    p = argparse.ArgumentParser(
        prog="python -m src.evaluate",
        description="Métricas en prueba, globales y por subgrupo, y sus tres figuras")
    p.add_argument("--crudas", default=str(PUNTUACIONES_DE_PRUEBA),
                   help="las puntuaciones congeladas de prueba, con su .sha256 al lado")
    p.add_argument("--calibrador", default=str(CALIBRADOR_DESPLEGADO),
                   help="el calibrador isotónico desplegado")
    p.add_argument("--pesos", default=str(PESOS_DESPLEGADOS),
                   help="los pesos: si están, se comprueba que son los de las puntuaciones")
    p.add_argument("--salida", default=str(DIR_RESULTADOS),
                   help="la carpeta de resultados (lleva metrics/ y figures/)")
    p.add_argument("--umbral", type=float, default=guion.UMBRAL,
                   help="el umbral global, sobre la puntuación cruda (%(default)s)")
    p.add_argument("--umbral-pa", type=float, default=guion.UMBRALES_POR_VISTA["PA"],
                   help="el umbral de las placas PA (%(default)s)")
    p.add_argument("--umbral-ap", type=float, default=guion.UMBRALES_POR_VISTA["AP"],
                   help="el umbral de las placas AP (%(default)s)")
    p.add_argument("--sin-figuras", action="store_true",
                   help="escribe solo el JSON (no hace falta matplotlib)")
    p.add_argument("--detallado", action="store_true", help="registra también los pasos")
    return p


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    configurar_registro(args.detallado)
    try:
        if not args.sin_figuras:
            _matplotlib()       # falla ANTES de calcular nada
        registro.info("evaluando %s", _relativa(args.crudas))
        agregados = evaluar(args.crudas, args.calibrador, args.pesos, args.umbral,
                            {"PA": args.umbral_pa, "AP": args.umbral_ap})
        placas = None if args.sin_figuras else leer_puntuaciones(args.crudas)
        escritas = escribir_resultados(agregados, placas, args.salida, not args.sin_figuras)
    except ErrorDeEvaluacion as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    g = agregados["global"]
    registro.info("global: n = %d, AUC %.4f, sensibilidad %.4f, especificidad %.4f",
                  g["n"], g["auc"], g["recall"], g["especificidad"])
    for ruta in escritas:
        registro.info("escrito %s", _relativa(ruta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
