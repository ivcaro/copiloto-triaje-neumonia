# -*- coding: utf-8 -*-
"""Mide la latencia del sistema desplegado: de latencias.json del arnes a latencia.json.

USO
    python scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json
    python scripts/medir_latencia.py --corrida pruebas/corpus/latencia/latencias.json --manual "S1,S2,S3,S4,S5"

Lee el `latencias.json` que deja una corrida CON BOTS de
`pruebas/reproducir_casos.py` contra el sistema desplegado y escribe
docs/validacion-semisintetica/latencia.json (spec de SP5 §6.3). Es una
MEDICION, no una simulacion: lo dice el titulo del JSON.

Cuenta solo las consultas que pasaron por los bots, llegaron al final, no
son un rechazo previsto, no dieron error EN LA CONSULTA MEDIDA, coinciden
con la lectura del arnes (que tambien tiene que haber salido bien) y llevan
`ms_extremo`. Con menos de 30 no escribe
nada: la latencia queda «no medida», y el informe lo dice con la causa.

`ms_extremo` es una COTA INFERIOR de lo que espera el profesional: no ve la
subida a Telegram, la entrega del webhook ni el envio de la respuesta. Por
eso el JSON dice que cumplir un umbral aqui es necesario y no suficiente.

`--manual` son los segundos, cronometrados a mano en el cliente de Telegram,
desde que se envia la placa hasta que aparece la respuesta: el tiempo TOTAL,
en 5 consultas. Acota lo que `ms_extremo` no ve; no es un percentil ni se
suma al p50. S1..S5 son los cinco tiempos, con punto decimal (con coma
saldrian diez valores, y se rechazan): sin medicion a mano, `--manual` se
omite.
"""
import argparse
import datetime
import json
import math
import pathlib
import statistics
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
CARPETA = REPO / "docs" / "validacion-semisintetica"
NOMBRE = "latencia.json"

TITULO = ("Latencia del sistema desplegado, medida con el arnés (no es una "
          "simulación): el tramo `ms_extremo`, cota inferior de la latencia "
          "de extremo a extremo")
TRAMO = ("`ms_extremo` de la tabla `consultas`: desde que `Normalizar update` "
         "recibe el update con la placa hasta que `Desenlace` compone la "
         "respuesta. Excluye la subida a Telegram, la entrega del webhook y "
         "el envío de `Responder`: no es el tiempo desde que el profesional "
         "sube la radiografía hasta que recibe el pre-informe.")
LECTURA = ("`ms_extremo` es una cota inferior de lo que espera el "
           "profesional. Si un percentil NO cumple un umbral aquí, tampoco "
           "lo cumple de extremo a extremo; si lo cumple aquí, es necesario "
           "pero no suficiente. Lo que `ms_extremo` no ve se acota, si se "
           "cronometró, en `total_a_mano`.")
PERCENTIL = ("interpolación lineal entre estadísticos de orden (el método "
             "«linear» de numpy, tipo 7 de Hyndman y Fan) sobre "
             "`ms_extremo_ordenados`")
A_MANO = ("segundos desde que se envía la placa hasta que aparece la "
          "respuesta, cronometrados a mano en el cliente de Telegram. Es el "
          "tiempo TOTAL, no el tramo que falta: una acotación en pocas "
          "consultas, no un percentil, y no se suma a `p50_ms`")
MINIMO = 30
A_MANO_N = 5                 # spec §6.3: se acota a mano en 5 consultas
UMBRALES_S = {"minimo": 8, "objetivo": 3}
NO_MEDIDO = "no medido"
# La regla del spec de SP5 §6.2, escrita en el JSON para que nadie tenga que
# deducir la etiqueta de cuatro booleanos.
REGLA = (f"La etiqueta del KPI se decide con el p95 de `ms_extremo` frente al "
         f"mínimo de {UMBRALES_S['minimo']} s: si no lo cumple, «no cumplido»; si lo "
         f"cumple, «cumplido con cambio», porque `ms_extremo` no ve todo el "
         f"tramo. Lo cronometrado a mano pesa en contra: si su mediana supera "
         f"los {UMBRALES_S['minimo']} s, «no cumplido»; si no se cronometró, no pesa. "
         f"El p50 y el objetivo de {UMBRALES_S['objetivo']} s se reportan al lado y no "
         f"deciden (spec de SP5 §6.2).")
CUMPLIDO, NO_CUMPLIDO = "cumplido con cambio", "no cumplido"
# La fecha de la corrida es el dia en la hora de Ecuador continental (UTC−5).
ZONA = datetime.timezone(datetime.timedelta(hours=-5))
GLOSARIO = {
    "n": ("las consultas que cuentan: pasaron por los bots, llegaron al final, "
          "tenían que dar un pre-informe, no dieron error, las confirma la "
          "lectura propia del arnés y llevan `ms_extremo`"),
    "menor_ms y mayor_ms": ("la medida más pequeña y la más grande de "
                            "`ms_extremo_ordenados`; no son umbrales"),
    "modelo_p50_ms": ("la mediana de lo que el servidor dijo que tardó el modelo en "
                      "esas mismas consultas; es una parte de `ms_extremo`"),
    "corrida_del": ("el día, en la hora de Ecuador continental (UTC−5), en que el "
                    "arnés escribió la corrida que aquí se resume"),
    "descartadas": {
        "sin_bots": "la fila no pasó por los bots, y no tiene `ms_extremo`",
        "rechazo_previsto": ("un caso que el sistema tiene que rechazar (perfiles 05 "
                             "a 09 del arnés): no da un pre-informe que medir"),
        "fallo": "la conversación con los bots no llegó al final",
        "error": "la consulta medida acabó en error",
        "no_coincide": ("la lectura propia del arnés no dio lo mismo que el bot, o "
                        "no se pudo hacer"),
        "sin_ms_extremo": "la fila no lleva una medida válida",
    },
}
# Los motivos de descarte, en el orden en que se miran: cada fila cuenta en
# uno solo, el primero que le toca. Los rechazos previstos van antes que los
# fallos: asi `fallo` cuenta solo las consultas que tenian que dar resultado.
MOTIVOS = ("sin_bots", "rechazo_previsto", "fallo", "error", "no_coincide",
           "sin_ms_extremo")
# Las claves de una fila de latencias.json (las escribe
# `pruebas/reproducir_casos.py::filas_de_latencia`).
CLAVES = ("patientId", "perfil", "rechazo_previsto", "con_bots", "fallo",
          "error_consulta", "coincide", "ms_extremo", "ms_modelo",
          "error_arnes", "ms_arnes")


def _es_una_medida(v) -> bool:
    """Unos milisegundos: un numero finito y no negativo. Ni `None`, ni una
    cadena, ni un booleano (`True` contaria como 1 ms)."""
    return (isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v) and v >= 0)


def _motivo(fila):
    """Por que una fila no cuenta, o None si cuenta.

    El error que cuenta es el de LA CONSULTA MEDIDA, la que paso por los
    bots y escribio `ms_extremo`: un `copiloto_no_responde` del flujo no
    alcanza a la llamada propia del arnes, que es otra y no pasa por Telegram
    ni por n8n. `error_arnes` no se mira, pero la llamada del arnes si pesa
    por `coincide`: una consulta solo cuenta si la lectura del arnes la
    confirma, y si esa llamada fallo no hay con que confirmarla. Eso tambien
    es `no_coincide`."""
    if not fila.get("con_bots"):
        return "sin_bots"
    if fila.get("rechazo_previsto"):
        return "rechazo_previsto"
    if fila.get("fallo"):
        return "fallo"
    if fila.get("error_consulta"):
        return "error"
    if fila.get("coincide") != "sí":
        return "no_coincide"
    if not _es_una_medida(fila.get("ms_extremo")):
        return "sin_ms_extremo"
    return None


def _frente_a(ms):
    return {"cumple_minimo": bool(ms <= UMBRALES_S["minimo"] * 1000),
            "cumple_objetivo": bool(ms <= UMBRALES_S["objetivo"] * 1000)}


def veredicto(p95_ms, manual) -> dict:
    """La etiqueta del KPI segun `REGLA`. Se decide con el percentil y con la
    mediana de lo cronometrado SIN redondear: 8,004 s se escribe «8,0» y
    supera los 8 s."""
    minimo_ms = UMBRALES_S["minimo"] * 1000
    cumple = bool(p95_ms <= minimo_ms)
    supera = bool(statistics.median(manual) * 1000 > minimo_ms) if manual else None
    return {"regla": REGLA, "p95_cumple_el_minimo": cumple,
            "a_mano_supera_el_minimo": supera,
            "etiqueta": CUMPLIDO if cumple and not supera else NO_CUMPLIDO}


def fecha_de(ruta) -> str:
    """El dia (UTC−5) en que se escribio el fichero de la corrida."""
    escrito = pathlib.Path(ruta).stat().st_mtime
    return datetime.datetime.fromtimestamp(escrito, tz=ZONA).date().isoformat()


def resumir(filas, minimo=MINIMO, manual=None, corrida_del=None) -> dict:
    """El contenido de latencia.json, desde las filas de latencias.json.

    `manual` son los segundos de envio a respuesta cronometrados a mano (el
    tiempo total, no el tramo que falta); sin ellos, `total_a_mano` dice «no
    medido». `corrida_del` es el dia de la corrida (`fecha_de`). Con menos de
    `minimo` consultas validas sale con `SystemExit`: no hay cifra que dar.
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
        # lo que mas descarta entre las consultas que tenian que contar
        imprevistos = {m: descartadas[m] for m in MOTIVOS if m != "rechazo_previsto"}
        if descartadas["no_coincide"] and descartadas["no_coincide"] == max(
                imprevistos.values()):
            consejo = ("Lo que más descarta es `no_coincide`: el copiloto que contesta "
                       "al arnés (COPILOTO_URL) no da la misma lectura que el "
                       "desplegado. Comprueba que es la misma imagen y vuelve a "
                       "correr el arnés")
        else:
            consejo = "Vuelve a correr el arnés con un --por-perfil mayor"
        raise SystemExit(
            f"hay {len(validas)} consultas con bots, que no son un rechazo "
            f"previsto, sin fallo ni error, que coinciden con el arnés y llevan "
            f"ms_extremo, y hacen falta "
            f"{minimo}: la latencia de extremo a extremo queda «no medida» y "
            f"no se escribe nada (descartadas: {descartadas}). {consejo} o, si "
            f"no se puede, lleva esta causa al informe")

    ms = np.sort(np.array([float(f["ms_extremo"]) for f in validas]))
    # Los umbrales se comparan con el percentil SIN redondear: 8 000,04 ms se
    # escribe «8000,0» y no cumple los 8 s. Se redondea solo lo que se escribe.
    p50, p95 = (float(v) for v in np.percentile(ms, [50, 95]))
    modelo = [float(f["ms_modelo"]) for f in validas if _es_una_medida(f.get("ms_modelo"))]
    manual = [float(v) for v in (manual or [])]
    return {
        "titulo": TITULO,
        "tramo": TRAMO,
        "lectura": LECTURA,
        "corrida_del": corrida_del,
        "n": len(validas),
        "percentil": PERCENTIL,
        "p50_ms": round(p50, 1),
        "p95_ms": round(p95, 1),
        "menor_ms": round(float(ms.min()), 1),
        "mayor_ms": round(float(ms.max()), 1),
        "ms_extremo_ordenados": [round(float(v), 1) for v in ms],
        # lo que el servidor dijo que tardo el modelo EN las consultas medidas
        "modelo_p50_ms": round(statistics.median(modelo), 1) if modelo else None,
        "umbrales_s": dict(UMBRALES_S),
        "frente_a_umbrales": {"p50": _frente_a(p50), "p95": _frente_a(p95)},
        "total_a_mano": ({"que_es": A_MANO, "valores_s": manual, "n": len(manual),
                          "mediana_s": round(statistics.median(manual), 2),
                          "menor_s": min(manual), "mayor_s": max(manual)}
                         if manual else NO_MEDIDO),
        "veredicto": veredicto(p95, manual),
        "descartadas": descartadas,
        "glosario": GLOSARIO,
    }


def leer_manual(texto):
    """Los CINCO tiempos de `--manual` (`A_MANO_N`), en segundos: separados
    por comas y con punto decimal. Con coma decimal saldrian diez valores y se
    rechazan; una mezcla de comas y puntos que de justo cinco no se puede
    distinguir de cinco tiempos, y por eso la orden imprime lo que escribio."""
    if texto is None:
        return None
    try:
        valores = [float(trozo) for trozo in texto.split(",")]
    except ValueError:
        valores = []
    if len(valores) != A_MANO_N or any(not 0 < v < float("inf") for v in valores):
        raise SystemExit(
            f"--manual espera los {A_MANO_N} tiempos cronometrados, en segundos "
            f"positivos, con punto decimal (no coma) y separados por comas; "
            f"llegó «{texto}». Sin medición a mano, omite --manual")
    return valores


def leer_corrida(ruta) -> list:
    """Las filas de un latencias.json, comprobadas: lo que no es de este
    arnes no se mide."""
    ruta = pathlib.Path(ruta)
    if not ruta.is_file():
        raise SystemExit(f"no existe {ruta}: lo escribe una corrida de "
                         f"pruebas/reproducir_casos.py en su carpeta de salida")
    try:
        filas = json.loads(ruta.read_text(encoding="utf-8"))
    except ValueError as error:
        raise SystemExit(f"{ruta} no es un JSON ({error}): vuelve a correr "
                         f"pruebas/reproducir_casos.py") from None
    if not isinstance(filas, list):
        raise SystemExit(f"{ruta} no es una lista de filas de latencia")
    for n, fila in enumerate(filas, 1):
        if not isinstance(fila, dict) or set(fila) != set(CLAVES):
            raise SystemExit(
                f"la fila {n} de {ruta} no lleva las claves de una fila de "
                f"latencia ({', '.join(CLAVES)}): si es de una versión "
                f"anterior del arnés, vuelve a correr pruebas/reproducir_casos.py")
    return filas


def _a_mano_anterior(salida):
    """Los tiempos a mano del latencia.json que se va a pisar, o None si no
    los llevaba (o no se puede leer)."""
    try:
        anterior = json.loads(pathlib.Path(salida).read_text(encoding="utf-8"))
        return list(anterior["total_a_mano"]["valores_s"]) or None
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _segundos(ms):
    return f"{ms / 1000:.2f}".replace(".", ",") + " s"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--corrida", required=True,
                   help="el latencias.json de una corrida con bots del arnés")
    p.add_argument("--salida", default=str(CARPETA / NOMBRE))
    p.add_argument("--manual", metavar="SEGUNDOS",
                   help="los cinco tiempos, en segundos, de envío a respuesta "
                        "cronometrados a mano en el cliente de Telegram, con "
                        "punto decimal y separados por comas; sin medición a "
                        "mano se omite")
    args = p.parse_args(argv)

    manual = leer_manual(args.manual)
    filas = leer_corrida(args.corrida)
    resultado = resumir(filas, manual=manual, corrida_del=fecha_de(args.corrida))

    # Se serializa ANTES de abrir: si fallara, el fichero anterior sigue entero.
    texto = json.dumps(resultado, ensure_ascii=False, indent=1, allow_nan=False) + "\n"
    salida = pathlib.Path(args.salida)
    anteriores = _a_mano_anterior(salida)
    if manual is None and anteriores:
        print(f"AVISO: el {salida.name} anterior llevaba una medición a mano y "
              f"este no. Para conservarla, repite la orden con "
              f"--manual \"{','.join(str(v) for v in anteriores)}\"")
    salida.parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    print(f"{resultado['n']} consultas: p50 {_segundos(resultado['p50_ms'])}, "
          f"p95 {_segundos(resultado['p95_ms'])} "
          f"({resultado['descartadas']['total']} descartadas); corrida del "
          f"{resultado['corrida_del']}; etiqueta del KPI: "
          f"«{resultado['veredicto']['etiqueta']}»; {salida}")
    if manual is not None:
        # para que un decimal escrito con coma se vea antes de versionar nada
        print("cronometrado a mano: " + "; ".join(_segundos(1000 * v) for v in manual))
    return 0


if __name__ == "__main__":
    # Los mensajes llevan tildes y «», y el de «no medida» sale por stderr: en
    # una consola que no es UTF-8 saldrian rotos.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
