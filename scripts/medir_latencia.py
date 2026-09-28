# -*- coding: utf-8 -*-
"""Mide la latencia de extremo a extremo: de latencias.json del arnes a latencia.json.

USO
    python scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json
    python scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json --manual "5.2,4.8,6.1,5.0,5.5"

Lee el `latencias.json` que deja una corrida CON BOTS de
`pruebas/reproducir_casos.py` contra el sistema desplegado y escribe
docs/validacion-semisintetica/latencia.json (spec de SP5 §6.3). Es una
MEDICION, no una simulacion: lo dice el titulo del JSON.

Cuenta solo las consultas que pasaron por los bots, llegaron al final, no
dieron error y llevan `ms_extremo`. Con menos de 30 no escribe nada: la
latencia queda «no medida», y el informe lo dice con la causa.

`--manual` son segundos medidos a mano en el cliente de Telegram (hora del
envio de la placa frente a hora de la respuesta), en los 5 casos con que se
acota el tramo que `ms_extremo` no ve.
"""
import argparse
import json
import math
import pathlib
import statistics
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
CARPETA = REPO / "docs" / "validacion-semisintetica"
NOMBRE = "latencia.json"

TITULO = ("Latencia de extremo a extremo: medición con el arnés sobre el "
          "sistema desplegado (no es una simulación)")
TRAMO = ("`ms_extremo` de la tabla `consultas`: desde que `Normalizar update` "
         "recibe el update con la placa hasta que `Desenlace` compone la "
         "respuesta. Excluye la subida a Telegram, la entrega del webhook y "
         "el envío de `Responder`: no es el tiempo desde que el profesional "
         "sube la radiografía hasta que recibe el pre-informe.")
MINIMO = 30
UMBRALES_S = {"minimo": 8, "objetivo": 3}
NO_MEDIDO = "no medido"
# Los motivos de descarte, en el orden en que se miran: cada fila cuenta en
# uno solo, el primero que le toca.
MOTIVOS = ("sin_bots", "fallo", "error", "sin_ms_extremo")


def _es_una_medida(v) -> bool:
    """Unos milisegundos: un numero finito y no negativo. Ni `None`, ni una
    cadena, ni un booleano (`True` contaria como 1 ms)."""
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v) and v >= 0)


def _motivo(fila):
    """Por que una fila no cuenta, o None si cuenta."""
    if not fila.get("con_bots"):
        return "sin_bots"
    if fila.get("fallo"):
        return "fallo"
    if fila.get("error"):
        return "error"
    if not _es_una_medida(fila.get("ms_extremo")):
        return "sin_ms_extremo"
    return None


def _frente_a(ms):
    return {"cumple_minimo": bool(ms <= UMBRALES_S["minimo"] * 1000),
            "cumple_objetivo": bool(ms <= UMBRALES_S["objetivo"] * 1000)}


def resumir(filas, minimo=MINIMO, manual=None) -> dict:
    """El contenido de latencia.json, desde las filas de latencias.json.

    `manual` son los segundos del tramo que falta, medidos a mano; sin ellos,
    `tramo_manual` dice «no medido». Con menos de `minimo` consultas validas
    sale con `SystemExit`: no hay cifra que dar.
    """
    descartadas = {"total": 0, **{m: 0 for m in MOTIVOS}}
    validas = []
    for fila in filas:
        motivo = _motivo(fila)
        if motivo is None:
            validas.append(fila)
        else:
            descartadas[motivo] += 1
            descartadas["total"] += 1
    if len(validas) < minimo:
        raise SystemExit(
            f"hay {len(validas)} consultas con bots, sin fallo ni error y con "
            f"ms_extremo, y hacen falta {minimo}: la latencia de extremo a "
            f"extremo queda «no medida» y no se escribe nada "
            f"(descartadas: {descartadas})")

    ms = np.array([float(f["ms_extremo"]) for f in validas])
    # Los umbrales se comparan con el percentil SIN redondear: 8 000,04 ms se
    # escribe «8000,0» y no cumple los 8 s. Se redondea solo lo que se escribe.
    p50, p95 = (float(v) for v in np.percentile(ms, [50, 95]))
    modelo = [float(f["ms_modelo"]) for f in validas if _es_una_medida(f.get("ms_modelo"))]
    manual = [float(v) for v in (manual or [])]
    return {
        "titulo": TITULO,
        "tramo": TRAMO,
        "n": len(validas),
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "minimo_ms": round(float(ms.min()), 1),
        "maximo_ms": round(float(ms.max()), 1),
        "modelo_p50_ms": round(statistics.median(modelo), 1) if modelo else None,
        "umbrales_s": dict(UMBRALES_S),
        "frente_a_umbrales": {"p50": _frente_a(p50), "p95": _frente_a(p95)},
        "tramo_manual": ({"valores_s": manual, "n": len(manual),
                          "mediana_s": round(statistics.median(manual), 2)}
                         if manual else NO_MEDIDO),
        "descartadas": descartadas,
    }


def leer_manual(texto):
    """Los segundos de `--manual`: separados por comas y con punto decimal."""
    if texto is None:
        return None
    try:
        valores = [float(trozo) for trozo in texto.split(",")]
    except ValueError:
        valores = []
    if not valores or any(not 0 < v < float("inf") for v in valores):
        raise SystemExit(
            f"--manual espera segundos positivos separados por comas y con "
            f"punto decimal, como \"5.2,4.8,6.1,5.0,5.5\"; llegó «{texto}»")
    return valores


def _segundos(ms):
    return f"{ms / 1000:.2f}".replace(".", ",") + " s"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--corrida", required=True,
                   help="el latencias.json de una corrida con bots del arnés")
    p.add_argument("--salida", default=str(CARPETA / NOMBRE))
    p.add_argument("--manual", metavar="SEGUNDOS",
                   help="el tramo que falta, medido a mano en el cliente de "
                        "Telegram: \"5.2,4.8,6.1,5.0,5.5\"")
    args = p.parse_args(argv)

    manual = leer_manual(args.manual)
    corrida = pathlib.Path(args.corrida)
    if not corrida.is_file():
        raise SystemExit(f"no existe {corrida}: lo escribe una corrida de "
                         f"pruebas/reproducir_casos.py en su carpeta de salida")
    filas = json.loads(corrida.read_text(encoding="utf-8"))
    if not isinstance(filas, list):
        raise SystemExit(f"{corrida} no es una lista de filas de latencia")
    resultado = resumir(filas, manual=manual)

    salida = pathlib.Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n")
    print(f"{resultado['n']} consultas: p50 {_segundos(resultado['p50_ms'])}, "
          f"p95 {_segundos(resultado['p95_ms'])} "
          f"({resultado['descartadas']['total']} descartadas); {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
