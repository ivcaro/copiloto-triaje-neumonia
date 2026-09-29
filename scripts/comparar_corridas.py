"""Compara varias corridas de entrenamiento y dice cual queda.

Uso:
    C:\\venv-copiloto\\Scripts\\python.exe scripts/comparar_corridas.py ^
        "D:\\corridas\\corrida1_mobilenet_224px" ^
        "D:\\corridas\\corrida2_densenet121_320px\\reporte_metricas.json" ^
        [--salida docs/comparativa-corridas.md]

Cada ruta puede ser el propio `reporte_metricas.json` o la carpeta de la
corrida que lo contiene, que es como quedan en Drive.

La regla de seleccion se escribe entera dentro del Markdown generado, y no
solo aqui: un informe que corona una ganadora sin decir con que criterio lo
hizo no se puede auditar, y elegir modelo es justo la decision que hay que
defender.

Vive en `scripts/` y no en el paquete a proposito: `copiloto_triaje` es lo que
instala SP2 para servir inferencia, y comparar corridas es trabajo de
laboratorio que corre en local sobre los JSON bajados de Drive.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_REPO / "src"))

from copiloto_triaje.modelo.reporte import CRITERIOS_ACEPTACION  # noqa: E402

NOMBRE_REPORTE = "reporte_metricas.json"

# La salida por defecto se ancla al repositorio y no al directorio de trabajo:
# el script se invoca tanto desde la raiz como desde `scripts/`, y un informe
# que aparece en un sitio distinto segun desde donde se llame no se encuentra.
SALIDA_POR_DEFECTO = RAIZ_REPO / "docs" / "comparativa-corridas.md"

# Nombres de los escalones de la regla. Se devuelven junto a la ganadora, igual
# que `elegir_umbral` devuelve el paso que aplico: sin el, la decision no se
# puede auditar desde fuera ni fijar en una prueba.
PASO_UNICA = "unica_corrida"
PASO_CRITERIOS = "paso_1_mas_criterios_cumplidos"
PASO_RECALL = "paso_2_mayor_recall"
PASO_AUC = "paso_3_mayor_auc"
PASO_EMPATE = "paso_4_empate_total_se_conserva_el_orden_de_entrada"
NINGUNA = "ninguna_cumple_los_minimos"

EXPLICACION_PASO = {
    PASO_UNICA:
        "Es la única corrida comparada y cumple los tres mínimos. No le ganó a "
        "nadie: simplemente es aceptable.",
    PASO_CRITERIOS:
        "Paso 1: satisface más criterios de aceptación que cualquier otra. "
        "Ninguna métrica individual entra a discutir esto.",
    PASO_RECALL:
        "Paso 2: empataba con otra en número de criterios satisfechos y ganó "
        "por recall. En triaje el falso negativo es el error caro, así que el "
        "recall desempata antes que cualquier otra métrica.",
    PASO_AUC:
        "Paso 3: empataba con otra en criterios satisfechos y en recall, y ganó "
        "por AUC, que mide la calidad del ordenamiento del modelo con "
        "independencia del umbral.",
    PASO_EMPATE:
        "Paso 4: empata con otra en los tres escalones de la regla. Se conserva "
        "el orden en que se pasaron los reportes, y queda dicho aquí que la "
        "regla NO decidió: elegir entre ellas exige un criterio nuevo "
        "(latencia, tamaño del modelo, coste de entrenamiento).",
    NINGUNA:
        "Ninguna corrida satisface los tres mínimos, así que no se corona "
        "ninguna.",
}

# El texto que se copia tal cual al informe. Es la regla, en el mismo orden en
# que la aplica `elegir_ganadora`; si una cambia sin la otra, el informe
# mentiria sobre como se decidio.
REGLA_DE_SELECCION = (
    "1. **Cuántos criterios del spec §2 satisface** cada corrida sobre el "
    "conjunto de prueba: recall >= 0,80, especificidad >= 0,70 y AUC >= 0,85. "
    "Gana la que satisface más. Un criterio que el reporte no trae medido no "
    "cuenta como satisfecho.",
    "2. **A igualdad de criterios, mayor recall.** El coste clínico de un falso "
    "negativo (mandar a casa una neumonía) es mayor que el de un falso positivo "
    "(una placa revisada de más), así que el recall desempata antes que "
    "cualquier otra métrica.",
    "3. **Si también empatan en recall, mayor AUC**, que mide la calidad del "
    "ordenamiento del modelo con independencia del umbral elegido.",
    "4. **Si ninguna satisface los tres mínimos, no se corona ninguna.** El "
    "informe dice que ninguna cumple y muestra cuánto le falta a cada una, en "
    "vez de presentar como ganadora a una corrida que el proyecto ya declaró "
    "inaceptable.",
)

# Campos del bloque `corrida` que se comparan para decir QUE cambio entre dos
# corridas. El orden es de lo que mas efecto conocido tiene a lo que menos,
# para que el primer cambio listado sea tambien el sospechoso principal.
CAMPOS_CORRIDA = (
    ("arquitectura", "arquitectura"),
    ("tam_imagen", "resolución (px)"),
    ("epocas", "épocas"),
    ("ajuste_fino_completo", "ajuste fino completo"),
    ("scheduler_coseno", "planificador coseno"),
    ("lote", "tamaño de lote"),
    ("paciencia", "paciencia"),
    ("edad", "rango de edad"),
    # El coste entra en la tabla aunque no entre en la regla de seleccion. Es
    # lo que el informe le pide al lector cuando dos corridas empatan en los
    # tres criterios ("hace falta un criterio nuevo: latencia, tamanio del
    # modelo, coste de entrenamiento") y estaba en los reportes sin que nadie
    # lo mirara: entre mobilenet (3,1 h) y densenet121 (24,9 h) hay un factor
    # de ocho que decide solo.
    ("segundos_entrenamiento", "coste de entrenamiento"),
    ("dispositivo", "dispositivo"),
)

# Listas que se leen mejor con un separador propio: [4, 20] epocas es "4+20"
# (cabeza mas ajuste) y [18, 100] anios es un rango, "18-100".
SEPARADOR_LISTA = {"epocas": "+", "edad": "-"}


# --- lectura ------------------------------------------------------------

def cargar_reporte(ruta) -> tuple[dict, Path]:
    """Lee un `reporte_metricas.json`, admitiendo la carpeta que lo contiene.

    Devuelve (contenido, ruta_del_json). Los mensajes de error citan la ruta:
    comparando varias corridas a la vez, un fallo que no diga CUAL de ellas
    falla obliga a adivinar.
    """
    ruta = Path(ruta)
    ruta_json = ruta / NOMBRE_REPORTE if ruta.is_dir() else ruta
    if not ruta_json.is_file():
        raise FileNotFoundError(f"No existe el reporte {ruta_json}")
    try:
        contenido = json.loads(ruta_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        # Los mensajes de error van sin tildes, como los del resto de scripts
        # del repo: acaban en una consola de Windows que no siempre sabe
        # codificarlas, y ahi un acento roto tapa el mensaje.
        raise ValueError(f"{ruta_json} no es un JSON valido: {error}") from error
    # El bloque 'corrida' puede faltar (los reportes viejos no lo traen), pero
    # sin 'prueba' no hay nada que comparar, y es mejor decirlo que emitir una
    # tabla entera de 'n/d' con aspecto de resultado.
    if not isinstance(contenido, dict) or "prueba" not in contenido:
        raise ValueError(
            f"{ruta_json} no parece un reporte de metricas: falta el bloque "
            f"'prueba', que es de donde salen las metricas que se comparan")
    return contenido, ruta_json


def evaluar_criterios(prueba: dict) -> tuple[dict, int]:
    """Para cada criterio del spec: True, False o None si no esta reportado.

    None no es False. Un reporte antiguo hecho con `metricas_binarias` no trae
    AUC, y decir que "no cumple" un criterio que nadie midio seria mentir. Para
    el recuento, eso si, un criterio no medido no suma.
    """
    criterios: dict[str, bool | None] = {}
    cumplidos = 0
    for _, clave, minimo, _ in CRITERIOS_ACEPTACION:
        valor = prueba.get(clave)
        if valor is None:
            criterios[clave] = None
            continue
        criterios[clave] = float(valor) >= minimo
        cumplidos += int(criterios[clave])
    return criterios, cumplidos


def resumir(reporte: dict, ruta_json: Path) -> dict:
    """Aplana un reporte a lo unico que entra en la comparativa."""
    corrida = reporte.get("corrida") or {}
    prueba = reporte.get("prueba") or {}
    criterios, cumplidos = evaluar_criterios(prueba)
    return {
        # Sin bloque 'corrida' el unico identificador que queda es el nombre de
        # la carpeta, que en este proyecto ES el nombre de la corrida.
        "nombre": corrida.get("nombre") or ruta_json.parent.name or ruta_json.stem,
        "ruta": ruta_json,
        "corrida": corrida,
        "sin_bloque_corrida": not corrida,
        "prueba": prueba,
        "umbral": reporte.get("umbral"),
        # El paso de `elegir_umbral` con el que salio ese umbral. Se cargaba y
        # no lo leia nadie, y no es un detalle: un umbral de
        # `paso_1_especificidad_objetivo` cumple el objetivo, y uno de
        # `paso_5_no_se_alcanza_el_recall_minimo` significa que NINGUN umbral
        # alcanzaba el minimo y se reporta el menos malo. Mostrar los dos
        # numeros sin decir eso los presenta como equivalentes.
        "regla_umbral": reporte.get("regla"),
        "mejor_epoca": reporte.get("mejor_epoca"),
        "criterios": criterios,
        "criterios_cumplidos": cumplidos,
        "cumple_todo": cumplidos == len(CRITERIOS_ACEPTACION),
    }


# --- regla de seleccion -------------------------------------------------

def _numero_o(valor, ausente: float = -1.0) -> float:
    # Lo ausente tiene que perder cualquier desempate, y 0,0 es un valor
    # legitimo de recall: un `or` aqui confundiria los dos casos.
    return ausente if valor is None else float(valor)


def clave_de_orden(resumen: dict) -> tuple[int, float, float]:
    """La regla de seleccion, escrita como clave de ordenacion.

    El orden de la tupla ES la jerarquia: criterios satisfechos, luego recall,
    luego AUC. Vive en una sola funcion para que la tabla, el veredicto y la
    explicacion no puedan discrepar entre si.
    """
    return (resumen["criterios_cumplidos"],
            _numero_o(resumen["prueba"].get("recall")),
            _numero_o(resumen["prueba"].get("auc")))


def ordenar_corridas(resumenes: list[dict]) -> list[dict]:
    """De mejor a peor segun la regla.

    `sorted` es estable, asi que lo que la regla no desempata lo desempata el
    orden en que se pasaron los reportes: el informe sale igual cada vez.
    """
    return sorted(resumenes, key=clave_de_orden, reverse=True)


def elegir_ganadora(resumenes: list[dict]) -> tuple[dict | None, str]:
    """Devuelve (ganadora, paso). `ganadora` es None si ninguna cumple.

    Devolver ademas el paso es lo que hace auditable la decision, igual que
    `elegir_umbral` devuelve el paso con el que eligio el umbral.
    """
    if not resumenes:
        raise ValueError("No hay ninguna corrida que comparar")
    ordenadas = ordenar_corridas(resumenes)
    primera = ordenadas[0]
    # La primera acumula el maximo de criterios: si ella no los cumple todos,
    # no los cumple nadie.
    if not primera["cumple_todo"]:
        return None, NINGUNA
    if len(ordenadas) == 1:
        return primera, PASO_UNICA
    mejor, siguiente = clave_de_orden(primera), clave_de_orden(ordenadas[1])
    if mejor[0] != siguiente[0]:
        paso = PASO_CRITERIOS
    elif mejor[1] != siguiente[1]:
        paso = PASO_RECALL
    elif mejor[2] != siguiente[2]:
        paso = PASO_AUC
    else:
        paso = PASO_EMPATE
    return primera, paso


def diferencias(uno: dict, otro: dict) -> list[str]:
    """Que campos de configuracion cambian entre dos corridas, ya redactados.

    Es la base de lo unico honesto que se puede decir de una comparacion: si
    cambian dos cosas a la vez, la mejora no es atribuible a ninguna de ellas.
    """
    cambios = []
    for clave, etiqueta in CAMPOS_CORRIDA:
        separador = SEPARADOR_LISTA.get(clave, ", ")
        valor_uno, valor_otro = uno["corrida"].get(clave), otro["corrida"].get(clave)
        if valor_uno == valor_otro:
            continue
        cambios.append(f"{etiqueta}: {_texto(valor_otro, separador)} -> "
                       f"{_texto(valor_uno, separador)}")
    return cambios


# --- informe ------------------------------------------------------------

def _numero(valor, decimales: int = 3) -> str:
    return "n/d" if valor is None else f"{float(valor):.{decimales}f}"


def _texto(valor, separador: str = ", ") -> str:
    if valor is None:
        return "n/d"
    if isinstance(valor, bool):
        return "sí" if valor else "no"
    if isinstance(valor, (list, tuple)):
        return separador.join(str(elemento) for elemento in valor)
    return str(valor)


def _faltantes(resumen: dict) -> list[str]:
    """Cuanto le falta a una corrida en cada criterio que no satisface."""
    pendientes = []
    for nombre, clave, minimo, _ in CRITERIOS_ACEPTACION:
        estado = resumen["criterios"][clave]
        if estado is True:
            continue
        if estado is None:
            pendientes.append(f"{nombre}: NO REPORTADO (mínimo {minimo:.2f})")
            continue
        valor = float(resumen["prueba"][clave])
        pendientes.append(f"{nombre}: {valor:.3f}, faltan {minimo - valor:.3f} "
                          f"para el mínimo {minimo:.2f}")
    return pendientes


def _seccion_veredicto(ordenadas: list[dict], ganadora, paso: str) -> list[str]:
    lineas = ["## Veredicto", ""]
    if ganadora is None:
        lineas += [
            f"**Ninguna corrida cumple los {len(CRITERIOS_ACEPTACION)} mínimos "
            "del spec §2.** No se corona una ganadora: hacerlo daría por bueno "
            "un modelo que el propio proyecto declaró inaceptable. Esto es lo "
            "que le falta a cada una, **en el orden de la regla de selección** "
            "(cuántos criterios cumple, luego recall, luego AUC) — que no es "
            "el mismo que la distancia al mínimo:",
            "",
        ]
        for resumen in ordenadas:
            lineas.append(f"- `{resumen['nombre']}` "
                          f"({resumen['criterios_cumplidos']}/"
                          f"{len(CRITERIOS_ACEPTACION)} criterios) -> "
                          + "; ".join(_faltantes(resumen)))
        lineas += ["",
                   "Lo que toca es otra corrida, no otro umbral: el umbral ya "
                   "se eligió sobre la curva ROC de validación, y mover el "
                   "punto de operación no crea información que el modelo no "
                   "tenga."]
        return lineas + [""]

    prueba = ganadora["prueba"]
    lineas += [
        f"**Gana `{ganadora['nombre']}`.**",
        "",
        f"- Regla aplicada: `{paso}`",
        f"- {EXPLICACION_PASO.get(paso, 'Regla no reconocida.')}",
        f"- Sobre el conjunto de prueba: recall {_numero(prueba.get('recall'))}, "
        f"especificidad {_numero(prueba.get('especificidad'))}, "
        f"AUC {_numero(prueba.get('auc'))}.",
    ]
    # Cumplir el minimo no es cumplir el objetivo. Decirlo aqui evita que el
    # informe se lea como un aprobado redondo cuando no lo es.
    solo_minimo = [nombre for nombre, clave, _, objetivo in CRITERIOS_ACEPTACION
                   if prueba.get(clave) is not None
                   and float(prueba[clave]) < objetivo]
    if solo_minimo:
        lineas.append(f"- Cumple el mínimo pero **no el objetivo** en: "
                      f"{', '.join(solo_minimo)}.")
    return lineas + [""]


def _seccion_regla() -> list[str]:
    return ["## Regla de selección", "",
            "Quien lea este informe tiene que poder auditar por qué ganó la que "
            "ganó, así que la regla se escribe aquí entera y en el mismo orden "
            "en que la aplica el código (`scripts/comparar_corridas.py`):",
            ""] + list(REGLA_DE_SELECCION) + [""]


def _tabla_metricas(ordenadas: list[dict]) -> list[str]:
    lineas = [
        "| # | Corrida | Arquitectura | Resolución (px) | Épocas | Mejor época | "
        "Umbral | Recall | Especificidad | AUC | F1 | Criterios |",
        "| ---: | :--- | :--- | ---: | :--- | ---: | ---: | ---: | ---: | "
        "---: | ---: | :--- |",
    ]
    for posicion, resumen in enumerate(ordenadas, start=1):
        corrida, prueba = resumen["corrida"], resumen["prueba"]
        lineas.append(
            f"| {posicion} | `{resumen['nombre']}` | "
            f"{_texto(corrida.get('arquitectura'))} | "
            f"{_texto(corrida.get('tam_imagen'))} | "
            f"{_texto(corrida.get('epocas'), '+')} | "
            f"{_texto(resumen['mejor_epoca'])} | "
            f"{_numero(resumen['umbral'], 4)} | "
            f"{_numero(prueba.get('recall'))} | "
            f"{_numero(prueba.get('especificidad'))} | "
            f"{_numero(prueba.get('auc'))} | "
            f"{_numero(prueba.get('f1'))} | "
            f"{resumen['criterios_cumplidos']}/{len(CRITERIOS_ACEPTACION)} |")
    return lineas


def _tabla_criterios(ordenadas: list[dict]) -> list[str]:
    encabezado, separador = "| Corrida |", "| :--- |"
    for nombre, _, minimo, _ in CRITERIOS_ACEPTACION:
        encabezado += f" {nombre} >= {minimo:.2f} |"
        separador += " :--- |"
    lineas = [f"{encabezado} Total |", f"{separador} ---: |"]
    for resumen in ordenadas:
        fila = f"| `{resumen['nombre']}` |"
        for _, clave, _, _ in CRITERIOS_ACEPTACION:
            estado = resumen["criterios"][clave]
            if estado is None:
                fila += " NO REPORTADO |"
            else:
                fila += " cumple |" if estado else " **NO CUMPLE** |"
        lineas.append(f"{fila} {resumen['criterios_cumplidos']}/"
                      f"{len(CRITERIOS_ACEPTACION)} |")
    return lineas


def _delta(uno: dict, otro: dict, clave: str) -> str:
    valor_uno, valor_otro = uno["prueba"].get(clave), otro["prueba"].get(clave)
    if valor_uno is None or valor_otro is None:
        return "n/d"
    return f"{float(valor_uno) - float(valor_otro):+.3f}"


def _parrafo_comparacion(mejor: dict, otra: dict) -> str:
    deltas = ", ".join(
        f"{etiqueta} {_delta(mejor, otra, clave)}"
        for etiqueta, clave in (("recall", "recall"),
                                ("especificidad", "especificidad"),
                                ("AUC", "auc")))
    cambios = diferencias(mejor, otra)
    if mejor["sin_bloque_corrida"] or otra["sin_bloque_corrida"]:
        lectura = ("No se puede decir qué cambió entre las dos, porque al menos "
                   "uno de los dos reportes no trae el bloque `corrida` con la "
                   "configuración con la que se entrenó.")
    elif not cambios:
        lectura = ("Las dos declaran la misma configuración, así que la "
                   "diferencia es variabilidad del entrenamiento (semilla, "
                   "orden de los lotes) y no una mejora atribuible a nada.")
    elif len(cambios) == 1:
        lectura = (f"Cambia una sola cosa ({cambios[0]}), así que la diferencia "
                   f"sí es atribuible a ese cambio, con la reserva de que es "
                   f"una sola corrida por configuración y una sola semilla.")
    else:
        lectura = (f"Cambian {len(cambios)} cosas a la vez "
                   f"({'; '.join(cambios)}), así que la mejora "
                   f"**no se puede atribuir** a ninguna de ellas por separado: "
                   f"haría falta una corrida que cambiase solo una.")
    # Metricas medidas sobre conjuntos de prueba de distinto tamanio no son
    # comparables sin mas, y con --limite o con otro filtrado de edad es facil
    # que lo sean sin que nadie se de cuenta.
    n_mejor, n_otra = mejor["corrida"].get("n_test"), otra["corrida"].get("n_test")
    if n_mejor is not None and n_otra is not None and n_mejor != n_otra:
        lectura += (f" Ojo: los conjuntos de prueba no son del mismo tamaño "
                    f"({n_mejor} frente a {n_otra}), así que las métricas no "
                    f"son estrictamente comparables.")
    return (f"- **`{mejor['nombre']}`** frente a **`{otra['nombre']}`**: "
            f"{deltas}. {lectura}")


def _seccion_lectura(ordenadas: list[dict]) -> list[str]:
    lineas = ["## Lectura de los resultados", ""]
    if len(ordenadas) == 1:
        lineas += ["Solo hay una corrida: no hay ninguna diferencia que "
                   "atribuir. Lo único que dice este informe es si esa corrida "
                   "cumple o no los criterios de aceptación; para saber a qué "
                   "se debe lo que mide haría falta al menos una segunda "
                   "corrida que cambiase una sola cosa.", ""]
    else:
        lineas += ["Diferencias frente a la corrida mejor clasificada, y a qué "
                   "se pueden atribuir:", ""]
        referencia = ordenadas[0]
        for otra in ordenadas[1:]:
            lineas.append(_parrafo_comparacion(referencia, otra))
        lineas.append("")
    lineas += [
        "Dos reservas que este informe no puede resolver por sí solo:",
        "",
        "- Elegir la mejor de varias corridas mirando el conjunto de prueba es, "
        "en rigor, usar la prueba para seleccionar, y eso deja la métrica de la "
        "ganadora algo optimista. La comparación limpia se hace sobre "
        "validación y la prueba se toca una sola vez, al final, con la "
        "configuración ya elegida.",
        "- Cada configuración se entrenó una vez y con una sola semilla. Las "
        "diferencias pequeñas, del orden de 0,01, caben dentro de lo que una "
        "semilla distinta mueve por sí sola.",
        "",
    ]
    return lineas


def reporte_sin_ruta(ruta_json) -> str:
    """`<carpeta de la corrida>/<fichero>`: los dos ultimos componentes.

    El informe se versiona y se publica, y la ruta tal como se paso lleva
    dentro el usuario y las carpetas de la maquina donde se genero (spec de
    SP5 §6.1). La carpeta de la corrida y el nombre del fichero bastan para
    saber que reporte se leyo. Siempre con `/`, para que el informe no cambie
    segun el sistema donde se genere.
    """
    ruta_json = Path(ruta_json).resolve()
    carpeta = ruta_json.parent.name
    return f"{carpeta}/{ruta_json.name}" if carpeta else ruta_json.name


def _seccion_procedencia(ordenadas: list[dict]) -> list[str]:
    lineas = ["## Procedencia", "", "| Corrida | Reporte leído |", "| :--- | :--- |"]
    for resumen in ordenadas:
        lineas.append(f"| `{resumen['nombre']}` "
                      f"| `{reporte_sin_ruta(resumen['ruta'])}` |")
    if any(resumen["sin_bloque_corrida"] for resumen in ordenadas):
        lineas += ["",
                   "Alguno de estos reportes no trae el bloque `corrida`, que "
                   "es donde se guarda la configuración con la que se entrenó. "
                   "Los reportes que lo llevan son los generados a partir del "
                   "commit `2aa33c5`; los anteriores guardaban las métricas "
                   "pero no con qué se obtuvieron, y por eso su fila lleva "
                   "`n/d` en esas columnas."]
    return lineas + [""]


def escribir_comparativa(resumenes: list[dict], ruta) -> Path:
    """Escribe la comparativa en Markdown y devuelve la ruta."""
    ruta = Path(ruta)
    ordenadas = ordenar_corridas(resumenes)
    ganadora, paso = elegir_ganadora(resumenes)
    lineas = [
        "# Comparativa de corridas - SP1 núcleo de imagen",
        "",
        f"Generado el {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC a partir "
        f"de {len(ordenadas)} reporte(s) de métricas.",
        "",
    ]
    lineas += _seccion_veredicto(ordenadas, ganadora, paso)
    lineas += _seccion_regla()
    lineas += ["## Tabla comparativa", ""] + _tabla_metricas(ordenadas)
    lineas += ["", "### Criterios de aceptación (spec §2), sobre el conjunto de "
                   "PRUEBA", ""] + _tabla_criterios(ordenadas) + [""]
    lineas += _seccion_lectura(ordenadas)
    lineas += _seccion_procedencia(ordenadas)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Compara corridas de entrenamiento y dice cual queda")
    parser.add_argument("rutas", nargs="+", type=Path,
                        help="reporte_metricas.json, o la carpeta que lo "
                             "contiene; uno por corrida")
    parser.add_argument("--salida", type=Path, default=SALIDA_POR_DEFECTO,
                        help="Markdown de salida (por defecto "
                             "docs/comparativa-corridas.md)")
    args = parser.parse_args(argv)

    resumenes = []
    # Se deduplica por el JSON ya resuelto, no por la ruta escrita: la carpeta
    # y su reporte son rutas distintas que llevan al mismo sitio, y pasar las
    # dos es un descuido facil. Antes salian dos filas identicas y un parrafo
    # que atribuia a la semilla la diferencia entre un archivo y el mismo
    # archivo.
    vistos = set()
    for ruta in args.rutas:
        # Se cargan TODOS antes de escribir nada: con una ruta mal escrita el
        # error tiene que salir antes de dejar un informe a medias en disco.
        #
        # resumir() va DENTRO del try, no fuera: un JSON que pasa la
        # comprobacion de cargar_reporte (tiene la clave 'prueba') pero cuyo
        # contenido no sirve -{"prueba": [1, 2]}, o un recall que es la cadena
        # "n/d"- soltaba una traza cruda sin decir de que corrida se trataba,
        # que es justo lo que el contrato de esta funcion promete.
        try:
            reporte, ruta_json = cargar_reporte(ruta)
            clave = ruta_json.resolve()
            if clave in vistos:
                print(f"aviso: {ruta} lleva al mismo reporte que otra ruta ya "
                      "leída; se ignora la repetición")
                continue
            vistos.add(clave)
            resumenes.append(resumir(reporte, ruta_json))
        except (FileNotFoundError, ValueError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
        except (AttributeError, TypeError, KeyError) as error:
            print(f"ERROR: {ruta} no es un reporte utilizable "
                  f"({type(error).__name__}: {error})", file=sys.stderr)
            return 2
        print(f"leido {ruta_json}")

    ganadora, paso = elegir_ganadora(resumenes)
    # Escribir tambien puede fallar, y hacerlo despues de haber leido todos los
    # reportes con una traza cruda no ayuda a nadie: en Kaggle el script se
    # invoca desde el Dataset adjunto, que cuelga de /kaggle/input y es de solo
    # lectura, asi que un --salida olvidado cae justo aqui.
    try:
        salida = escribir_comparativa(resumenes, args.salida)
    except OSError as error:
        print(f"ERROR: no se pudo escribir {args.salida}: {error}",
              file=sys.stderr)
        return 2
    # El veredicto tambien por consola: el informe lo dice entero, pero tras
    # horas de entrenamiento lo primero que se quiere saber es cual queda.
    if ganadora is None:
        print("VEREDICTO: ninguna corrida cumple los minimos del spec.")
        # El detalle con tildes queda en el Markdown, que se escribe en UTF-8.
        # Por consola se escribe sin ellas, como el resto de los scripts del
        # repo: la consola de Windows no siempre las puede codificar.
        for resumen in ordenar_corridas(resumenes):
            faltan = ", ".join(
                f"{clave} {_numero(resumen['prueba'].get(clave))} "
                f"(minimo {minimo:.2f})"
                for _, clave, minimo, _ in CRITERIOS_ACEPTACION
                if resumen["criterios"][clave] is not True)
            print(f"  {resumen['nombre']}: falta {faltan}")
    else:
        print(f"VEREDICTO: gana {ganadora['nombre']} (regla: {paso})")
    print(f"comparativa en {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
