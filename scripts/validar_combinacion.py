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
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE  # noqa: E402
from copiloto_triaje.validacion import datos, metricas, oraculo, simulacion  # noqa: E402

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
    rejilla. Solo 0A y las destacadas llevan bootstrap y sensibilidad."""
    tareas = []
    for rho1 in rejilla:
        for rho0 in rejilla:
            completa = (rho1 == 0.0 and rho0 == 0.0) or (rho1, rho0) in tuple(destacadas)
            tareas.append((float(rho1), float(rho0), replicas if completa else 0, completa))
    return tareas


def _relativa(ruta: Path) -> str:
    try:
        return Path(ruta).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(ruta).name


def calcular(replicas: int = simulacion.B_REPLICAS, procesos: int = 1,
             rejilla=oraculo.RHO_REJILLA, destacadas=oraculo.CELDAS_DESTACADAS) -> dict:
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
            "pesos_sha256": datos.HASH_CONGELADO.read_text(encoding="utf-8").split()[0],
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
        f.write(json.dumps(resultados, ensure_ascii=False, indent=1) + "\n")
    return ruta


def leer_resultados(ruta) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--replicas", type=int, default=simulacion.B_REPLICAS,
                   help="réplicas del bootstrap en 0A y las seis celdas destacadas")
    p.add_argument("--procesos", type=int, default=min(7, os.cpu_count() or 1),
                   help="celdas en paralelo (1: en serie)")
    p.add_argument("--salida", default=str(CARPETA),
                   help="carpeta de resultados_simulacion.json y de las figuras")
    p.add_argument("--analisis", default=str(ANALISIS), help="el documento de análisis")
    p.add_argument("--sin-figuras", action="store_true")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
