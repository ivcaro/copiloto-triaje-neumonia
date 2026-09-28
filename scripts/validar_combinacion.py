# -*- coding: utf-8 -*-
"""Corre la simulacion semisintetica de la combinacion y deja sus resultados.

USO
    python scripts/validar_combinacion.py
    python scripts/validar_combinacion.py --replicas 50 --sin-figuras     (ensayo rapido)
    python scripts/validar_combinacion.py --solo-documento                (sin recalcular)

Lee docs/validacion-semisintetica/crudas_prueba.csv (congelada) y
servidor/calibrador.json; no necesita los pesos, ni Docker, ni red. Escribe en
docs/validacion-semisintetica/ el fichero resultados_simulacion.json y las
figuras a 300 DPI, y en docs/validacion-semisintetica-sp5.md el analisis.
Ninguna cifra del analisis se teclea: el documento y las figuras se generan
LEYENDO resultados_simulacion.json, no las variables en memoria.

La rejilla son 25 celdas (ρ1, ρ0); el bootstrap (1 000 replicas) se corre en
0A y en las seis celdas destacadas, una celda por proceso.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE  # noqa: E402
from copiloto_triaje.validacion import (  # noqa: E402
    datos, informe, metricas, oraculo, simulacion,
)

CARPETA = datos.CARPETA
NOMBRE_RESULTADOS = "resultados_simulacion.json"
ANALISIS = REPO / "docs" / "validacion-semisintetica-sp5.md"
ROTULO = "simulación semisintética"
TITULO = "Validación de la combinación de clínica e imagen: simulación semisintética (SP5 §4)"
ADVERTENCIA = (
    "Las placas y sus etiquetas son reales (conjunto de prueba de RSNA); la clínica "
    "se sortea con la distribución publicada de la puntuación de Heckerling y la "
    "dependencia entre clínica e imagen es un supuesto declarado. Nada de esto mide "
    "exactitud clínica en pacientes.")


def tareas_de_la_rejilla(replicas: int, rejilla=oraculo.RHO_REJILLA,
                         destacadas=oraculo.CELDAS_DESTACADAS) -> list:
    """(ρ1, ρ0, replicas, con_sensibilidad) por celda, en el orden de la
    rejilla. Solo 0A y las destacadas llevan bootstrap y sensibilidad. Una
    destacada que no esta en la rejilla se rechaza: si no, el resultado la
    anunciaria en sus parametros sin haberla calculado."""
    rejilla = [float(r) for r in rejilla]
    destacadas = {(float(a), float(b)) for a, b in destacadas}
    fuera = sorted(d for d in destacadas
                   if d[0] not in rejilla or d[1] not in rejilla or d == (0.0, 0.0))
    if fuera:
        raise ValueError(f"las celdas destacadas {fuera} no valen: tienen que estar en la "
                         f"rejilla {rejilla}, y el origen es 0A, que se cuenta aparte")
    tareas = []
    for rho1 in rejilla:
        for rho0 in rejilla:
            completa = (rho1 == 0.0 and rho0 == 0.0) or (rho1, rho0) in destacadas
            tareas.append((rho1, rho0, replicas if completa else 0, completa))
    return tareas


def _relativa(ruta: Path) -> str:
    try:
        return Path(ruta).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(ruta).name


def huella_de_los_pesos() -> str:
    """El sha256 de los pesos con que se generaron las crudas congeladas. Aqui
    no se puede recalcular (los pesos no viajan con el repositorio): se
    comprueba que el fichero lleva UNA huella, y se escribe en los resultados."""
    partes = datos.HASH_CONGELADO.read_text(encoding="utf-8").split()
    if len(partes) != 1 or not re.fullmatch(r"[0-9a-f]{64}", partes[0]):
        raise SystemExit(f"{_relativa(datos.HASH_CONGELADO)} no lleva un sha256: no se sabe "
                         "con qué pesos se generaron las crudas congeladas")
    return partes[0]


def calcular(replicas: int = simulacion.B_REPLICAS, procesos: int = 1,
             rejilla=oraculo.RHO_REJILLA, destacadas=oraculo.CELDAS_DESTACADAS) -> dict:
    pesos = huella_de_los_pesos()
    conjunto = simulacion.cargar_conjunto()
    tareas = tareas_de_la_rejilla(replicas, rejilla, destacadas)
    if procesos > 1:
        with ProcessPoolExecutor(max_workers=procesos) as grupo:
            celdas = list(grupo.map(simulacion.evaluar_tarea, tareas))
    else:
        celdas = [simulacion.evaluar_tarea(t) for t in tareas]
    for celda, (rho1, rho0, _, completa) in zip(celdas, tareas):
        celda["destacada"] = bool(completa and not (rho1 == 0.0 and rho0 == 0.0))
    return {
        "rotulo": ROTULO,
        "titulo": TITULO,
        "advertencia": ADVERTENCIA,
        "insumos": {
            "crudas": _relativa(datos.CRUDAS_CONGELADAS),
            "crudas_sha256": datos.huella_de_texto(datos.CRUDAS_CONGELADAS),
            "pesos_sha256": pesos,
            "calibrador": _relativa(datos.CALIBRADOR),
            "calibrador_sha256": datos.huella_de_texto(datos.CALIBRADOR),
            "placas": int(conjunto.y.size),
            "positivas": int(conjunto.y.sum()),
            "prevalencia": conjunto.prevalencia,
        },
        "parametros": {
            "replicas": int(replicas),
            "semilla_puntual": simulacion.SEMILLA_PUNTUAL,
            "semilla_clinica": simulacion.SEMILLA_CLINICA,
            "semilla_indices": simulacion.SEMILLA_INDICES,
            "epsilon": metricas.EPSILON,
            "bins": metricas.BINS,
            "repeticiones_suelo": metricas.REPETICIONES_SUELO,
            "semilla_suelo": metricas.SEMILLA_SUELO,
            "hipotesis_contencion": simulacion.HIPOTESIS_CONTENCION,
            "previo_desplegado": PREVALENCIA_COHORTE,
            "rejilla": [float(r) for r in rejilla],
            "destacadas": [[float(a), float(b)] for a, b in destacadas],
        },
        "imagen_sola": simulacion.imagen_sola(conjunto),
        "celdas": celdas,
    }


def escribir_resultados(resultados: dict, ruta) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="\n") as f:
        # allow_nan=False: «NaN» no es JSON, y un tercero no podria leerlo.
        f.write(json.dumps(resultados, ensure_ascii=False, indent=1, allow_nan=False) + "\n")
    return ruta


def leer_resultados(ruta) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# LAS FIGURAS
#
# Se dibujan LEYENDO el diccionario de resultados_simulacion.json, a 300 DPI y
# con el estilo de scripts/diagnostico_curvas.py. matplotlib se importa DENTRO
# de las funciones, y con el motor «Agg» (sin ventana), para que el calculo se
# pueda correr -y probar- sin tenerlo instalado: es el extra `figuras` del
# pyproject, no una dependencia del paquete.
#
# Los colores salen de una paleta comprobada para daltonismo; ademas cada
# modelo lleva su marca, para que la identidad no dependa solo del color.
# ---------------------------------------------------------------------------
DPI = 300
TINTA = "#0b0b0b"
COLOR_DIAGONAL = "#7a7974"
COLOR_MODELO = {"imagen": "#2a78d6", "clinica": "#eb6834",
                "independencia": "#1baf7a", "conservador": "#4a3aa7"}
MARCA_MODELO = {"imagen": "o", "clinica": "s", "independencia": "^", "conservador": "D"}
NOMBRE_MODELO = {"imagen": "imagen sola", "clinica": "clínica sola",
                 "independencia": "combinación por independencia",
                 "conservador": "combinación conservadora"}
# Las tres fracciones de la horquilla, en el orden del eje de λ: por debajo de
# 0 (mas alla del extremo conservador), dentro, y por encima de 1. Los colores
# dicen lo mismo que en el mapa de la pendiente: rojo donde el sistema exagera
# (λ < 0: el oraculo queda mas cerca del previo que las dos combinaciones) y
# azul donde se queda corto (λ > 1).
TRAMOS = (("bajo", "por el lado conservador (λ < 0)", "#e34948"),
          ("contencion", "dentro de la horquilla", "#c9c8c3"),
          ("sobre", "más allá de la independencia (λ > 1)", "#2a78d6"))
LADOS = (("a_favor", "imagen a favor (RV ≥ 1)"),
         ("en_contra", "imagen en contra (RV < 1)"))
RAMPA_AZUL = ("#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b")
RAMPA_DIVERGENTE = ("#e34948", "#f0efec", "#2a78d6")
FIGURAS_GLOBALES = ("horquilla_por_celda", "contencion_rejilla", "pendiente_rejilla")
PREFIJO_FIABILIDAD = "fiabilidad_"
REJILLAS = ("contencion", "pendiente")


def _pyplot():
    try:
        import matplotlib
    except ImportError:
        raise SystemExit("para dibujar hace falta matplotlib, que es el extra `figuras` "
                         "(pip install -e .[figuras]); sin él, corre con --sin-figuras") from None
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _luminancia(color) -> float:
    """La luminancia relativa de un color (WCAG 2), de 0 (negro) a 1 (blanco)."""
    from matplotlib.colors import to_rgb
    lineal = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
              for c in to_rgb(color)]
    return 0.2126 * lineal[0] + 0.7152 * lineal[1] + 0.0722 * lineal[2]


def _tinta_sobre(color) -> str:
    """Blanco o tinta: la que mas contrasta (razon de contraste de WCAG) con el
    color que de verdad se pinta debajo, no con su posicion en la escala."""
    fondo = _luminancia(color) + 0.05
    con_blanco = 1.05 / fondo
    con_tinta = fondo / (_luminancia(TINTA) + 0.05)
    return "white" if con_blanco > con_tinta else TINTA


def _ejes(ax, titulo, x, y):
    ax.set_title(titulo, fontsize=12, fontweight="bold")
    ax.set_xlabel(x, fontsize=10)
    ax.set_ylabel(y, fontsize=10)
    ax.grid(True, alpha=0.3, linestyle="--")
    if ax.get_legend_handles_labels()[0]:
        ax.legend(fontsize=9)


def _coma(valor, decimales: int) -> str:
    """La cifra con coma decimal; «n/d» si no hay cifra."""
    if valor is None or valor != valor:
        return "n/d"
    return f"{valor:.{decimales}f}".replace(".", ",")


def _rho(valor) -> str:
    return f"{valor:g}".replace(".", ",")


def _guardar(plt, fig, destino, titulo) -> Path:
    """300 DPI, y el titulo -con su rotulo- tambien en los metadatos del PNG."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=DPI, metadata={"Title": titulo})
    plt.close(fig)
    return destino


def slug_de_celda(celda: dict) -> str:
    """`0a` para 0A; `r1-030_r0-000` para el resto (ρ × 100, tres cifras)."""
    if celda["nombre"] == "0A":
        return "0a"
    return f"r1-{round(celda['rho1'] * 100):03d}_r0-{round(celda['rho0'] * 100):03d}"


def celdas_con_figura(resultados: dict) -> list:
    """0A y las destacadas, en el orden de la rejilla."""
    return [c for c in resultados["celdas"] if c["nombre"] == "0A" or c["destacada"]]


def figura_fiabilidad(celda: dict, destino) -> Path:
    """La curva de fiabilidad por deciles de los cuatro modelos de una celda.

    La ECE va en la leyenda AL LADO de su suelo (media y percentil 95): sola
    no dice nada, y contra la media sola parece fuera del ruido la que no lo
    esta."""
    plt = _pyplot()
    from matplotlib.ticker import FuncFormatter
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot([0, 1], [0, 1], "--", color=COLOR_DIAGONAL, linewidth=1.2,
            label="calibración perfecta")
    for modelo in simulacion.MODELOS:
        m = celda["modelos"][modelo]
        curva = [b for b in m["fiabilidad"]
                 if b["p_media"] is not None and b["observada"] is not None]
        ax.plot([b["p_media"] for b in curva], [b["observada"] for b in curva],
                "-" + MARCA_MODELO[modelo], color=COLOR_MODELO[modelo], linewidth=1.6,
                markersize=5, markeredgecolor="white", markeredgewidth=0.6,
                label=f"{NOMBRE_MODELO[modelo]} — ECE {_coma(m['ece'], 3)} (suelo "
                      f"{_coma(m['suelo']['media'], 3)}; p95 {_coma(m['suelo']['p95'], 3)})")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    for eje in (ax.xaxis, ax.yaxis):
        eje.set_major_formatter(FuncFormatter(lambda v, _: _coma(v, 1)))
    titulo = f"Fiabilidad por deciles — celda {celda['nombre']} — {ROTULO}"
    _ejes(ax, titulo, "probabilidad predicha (media del decil)", "frecuencia observada")
    ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout()
    return _guardar(plt, fig, destino, titulo)


def figura_horquilla(resultados: dict, destino) -> Path:
    """Donde queda el oraculo respecto de la horquilla, en 0A y las destacadas.

    Un panel por lado de la imagen; en cada celda, una barra apilada con las
    tres fracciones de los casos concordantes. No es una cobertura."""
    plt = _pyplot()
    from matplotlib.patches import Patch
    celdas = celdas_con_figura(resultados)
    posiciones = list(range(len(celdas)))
    fig, paneles = plt.subplots(1, 2, figsize=(9, 5.5), sharey=True)
    for ax, (lado, rotulo) in zip(paneles, LADOS):
        izquierda = [0.0] * len(celdas)
        for clave, _, color in TRAMOS:
            anchos = [100.0 * (c["horquilla"][lado][clave] or 0.0) for c in celdas]
            ax.barh(posiciones, anchos, left=izquierda, height=0.68, color=color,
                    edgecolor="white", linewidth=1.2)
            for y, (x0, ancho) in enumerate(zip(izquierda, anchos)):
                if ancho >= 12.0:
                    ax.text(x0 + ancho / 2, y, f"{_coma(ancho, 0)} %", ha="center",
                            va="center", fontsize=8, color=_tinta_sobre(color))
            izquierda = [a + b for a, b in zip(izquierda, anchos)]
        _ejes(ax, rotulo, "% de los casos concordantes", "")
        ax.set_title(rotulo, fontsize=10)
        ax.set_xlim(0, 100)
        ax.grid(False, axis="y")
    paneles[0].set_yticks(posiciones)
    paneles[0].set_yticklabels([c["nombre"] for c in celdas], fontsize=9)
    paneles[0].set_ylabel("celda (ρ1; ρ0)", fontsize=10)
    paneles[0].invert_yaxis()
    titulo = f"El oráculo frente a la horquilla, por celda y lado — {ROTULO}"
    fig.suptitle(titulo, fontsize=12, fontweight="bold")
    fig.legend(handles=[Patch(facecolor=color, label=nombre) for _, nombre, color in TRAMOS],
               loc="lower center", ncol=3, fontsize=9, frameon=False)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return _guardar(plt, fig, destino, titulo)


def figura_rejilla(resultados: dict, destino, que: str) -> Path:
    """Mapa de calor ρ1 × ρ0 con la cifra escrita en cada casilla.

    `contencion`: la de `horquilla.todos`, en un solo tono. `pendiente`: la del
    modelo de independencia, en dos tonos alrededor de 1 (por debajo exagera;
    por encima se queda corta)."""
    if que not in REJILLAS:
        raise ValueError(f"que debe ser uno de {REJILLAS}: {que!r}")
    plt = _pyplot()
    from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm
    from matplotlib.ticker import FuncFormatter
    rejilla = [float(r) for r in resultados["parametros"]["rejilla"]]
    lugar = {round(r, 6): i for i, r in enumerate(rejilla)}
    numeros = [[float("nan")] * len(rejilla) for _ in rejilla]
    for c in resultados["celdas"]:
        valor = (c["horquilla"]["todos"]["contencion"] if que == "contencion"
                 else c["modelos"]["independencia"]["pendiente"])
        if valor is not None:
            numeros[lugar[round(c["rho1"], 6)]][lugar[round(c["rho0"], 6)]] = (
                100.0 * valor if que == "contencion" else float(valor))
    if que == "contencion":
        mapa = LinearSegmentedColormap.from_list("azul", RAMPA_AZUL)
        norma = Normalize(vmin=0.0, vmax=100.0)
        decimales, unidad = 1, " %"
        titulo = f"Contención del oráculo en la horquilla, por celda — {ROTULO}"
        barra = "contención (% de los casos concordantes)"
    else:
        presentes = [v for fila in numeros for v in fila if v == v]
        desvio = max([abs(v - 1.0) for v in presentes] + [0.05])
        mapa = LinearSegmentedColormap.from_list("divergente", RAMPA_DIVERGENTE)
        norma = TwoSlopeNorm(vcenter=1.0, vmin=1.0 - desvio, vmax=1.0 + desvio)
        decimales, unidad = 2, ""
        titulo = f"Pendiente de la independencia, por celda — {ROTULO}"
        barra = "pendiente de calibración (< 1 exagera; > 1 se queda corta)"
    mapa = mapa.with_extremes(bad="#f0efec")
    fig, ax = plt.subplots(figsize=(9, 5.5))
    imagen = ax.imshow(numeros, cmap=mapa, norm=norma, origin="lower", aspect="auto")
    for i, fila in enumerate(numeros):
        for j, v in enumerate(fila):
            ax.text(j, i, _coma(v, decimales) + (unidad if v == v else ""),
                    ha="center", va="center", fontsize=10 if len(rejilla) <= 5 else 8,
                    color=_tinta_sobre(mapa(norma(v))) if v == v else TINTA)
    _ejes(ax, titulo, "ρ0 (dependencia entre los casos sin neumonía)",
          "ρ1 (dependencia entre los casos con neumonía)")
    ax.grid(False)
    ax.set_xticks(range(len(rejilla)))
    ax.set_xticklabels([_rho(r) for r in rejilla])
    ax.set_yticks(range(len(rejilla)))
    ax.set_yticklabels([_rho(r) for r in rejilla])
    cifras = 0 if que == "contencion" else 2
    cbar = fig.colorbar(imagen, ax=ax, format=FuncFormatter(lambda v, _: _coma(v, cifras)))
    cbar.set_label(barra, fontsize=10)
    fig.tight_layout()
    return _guardar(plt, fig, destino, titulo)


def figuras_presentes(carpeta) -> list[Path]:
    """Los PNG PROPIOS que hay en la carpeta, ordenados: los `fiabilidad_*.png`
    y los tres globales. Cualquier otro PNG es de otro y no se toca."""
    carpeta = Path(carpeta)
    if not carpeta.is_dir():
        return []
    globales = {f"{nombre}.png" for nombre in FIGURAS_GLOBALES}
    return sorted(p for p in carpeta.glob("*.png")
                  if p.name.startswith(PREFIJO_FIABILIDAD) or p.name in globales)


def figuras(resultados: dict, carpeta) -> list[Path]:
    """Dibuja todas las figuras y devuelve sus rutas en orden.

    Borra antes las propias que hubiera: si cambian las celdas destacadas, una
    `fiabilidad_*.png` de la corrida anterior quedaria en la carpeta con cifras
    que ya no son las del JSON."""
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    for rancia in figuras_presentes(carpeta):
        rancia.unlink()
    rutas = [figura_fiabilidad(c, carpeta / f"{PREFIJO_FIABILIDAD}{slug_de_celda(c)}.png")
             for c in celdas_con_figura(resultados)]
    rutas.append(figura_horquilla(resultados, carpeta / "horquilla_por_celda.png"))
    rutas.append(figura_rejilla(resultados, carpeta / "contencion_rejilla.png", "contencion"))
    rutas.append(figura_rejilla(resultados, carpeta / "pendiente_rejilla.png", "pendiente"))
    return rutas


# ---------------------------------------------------------------------------
# EL DOCUMENTO
# ---------------------------------------------------------------------------
def _enlace(figura: Path, desde: Path) -> str:
    """El enlace relativo desde la carpeta del documento, con barras `/`. Si
    no hay camino relativo (otra unidad de disco), el nombre del fichero: una
    ruta absoluta llevaria al documento el nombre de la maquina."""
    try:
        return os.path.relpath(figura.resolve(), desde.resolve()).replace(os.sep, "/")
    except ValueError:
        return figura.name


def escribir_analisis(resultados: dict, figuras: list, ruta) -> Path:
    """Escribe el documento de analisis en `ruta`, en UTF-8 y con LF.

    `figuras` son las rutas de los PNG que se enlazan; el texto lo redacta
    `informe.redactar` LEYENDO `resultados`."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    enlaces = {Path(f).stem: _enlace(Path(f), ruta.parent) for f in figuras}
    with ruta.open("w", encoding="utf-8", newline="\n") as f:
        f.write(informe.redactar(resultados, enlaces))
    return ruta


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--replicas", type=int, default=simulacion.B_REPLICAS,
                   help="réplicas del bootstrap en 0A y las seis celdas destacadas "
                        "(0: sin bootstrap ni intervalos, para ensayos)")
    p.add_argument("--procesos", type=int, default=min(7, os.cpu_count() or 1),
                   help="celdas en paralelo (1: en serie)")
    p.add_argument("--salida", default=str(CARPETA),
                   help="carpeta de resultados_simulacion.json y de las figuras")
    p.add_argument("--analisis", default=str(ANALISIS), help="el documento de análisis")
    p.add_argument("--sin-figuras", action="store_true",
                   help="no dibuja: deja las figuras que hubiera como estaban")
    p.add_argument("--solo-documento", action="store_true",
                   help="no recalcula: lee el JSON de --salida y regenera figuras y documento")
    args = p.parse_args(argv)
    if args.replicas < 0 or args.procesos < 1:
        raise SystemExit("--replicas no puede ser negativo y --procesos debe ser al menos 1")
    salida = Path(args.salida)
    ruta = salida / NOMBRE_RESULTADOS
    if not args.solo_documento:
        escribir_resultados(calcular(args.replicas, args.procesos), ruta)
        print(f"resultados: {ruta}")
    elif not ruta.is_file():
        raise SystemExit(f"no existe {ruta}: corre primero sin --solo-documento")
    resultados = leer_resultados(ruta)
    if not args.sin_figuras:
        for figura in figuras(resultados, salida):
            print(f"figura: {figura}")
    analisis = escribir_analisis(resultados, figuras_presentes(salida), args.analisis)
    print(f"análisis: {analisis}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
