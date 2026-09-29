# -*- coding: utf-8 -*-
"""El documento de análisis de la simulación semisintética (spec de SP5 §4.8).

`redactar(resultados, figuras)` devuelve el Markdown del análisis a partir
del diccionario de `resultados_simulacion.json`. Es una función pura: ni lee
ni escribe ficheros, ni dibuja; de eso se ocupa
`scripts/validar_combinacion.py`.

NINGUNA CIFRA SE TECLEA. Todo número del documento sale del diccionario: los
de las tablas y también los de la prosa (placas, prevalencia, réplicas, ε, el
umbral de la hipótesis, los ρ de la rejilla). Las frases de la «Lectura de
los resultados» se componen contando sobre las cifras, de modo que el texto
no puede decir algo que sus tablas no sostengan. Lo único fijo son las
definiciones del diseño: las bandas (< 20 %, 20-70 %, > 70 %), el nivel de
los intervalos (95 %), el corte de «poco informativa» (|ln RV| < 0,5, que
son k = 2 y k = 3; las extremas son k ≤ 1 y k ≥ 4), los valores de λ en los
extremos de la horquilla (0 y 1) y lo que la fila 0A tiene que dar (colas 0,
contención 100 %).

Formato: coma decimal, el menos tipográfico («−»), porcentajes con un
decimal, y «n/d» donde no hay cifra.
"""
from __future__ import annotations

import math

TITULO = "Validación de la combinación de clínica e imagen: simulación semisintética (SP5)"
GUION = "scripts/validar_combinacion.py"
GENERADOR = "src/copiloto_triaje/validacion/informe.py"
RESULTADOS = "resultados_simulacion.json"
PRUEBA_0A = "tests/test_validacion_0a.py"
# Como se escribe cada libreria de `entorno`, en el orden en que se citan.
LIBRERIAS = (("python", "Python"), ("numpy", "NumPy"), ("scipy", "SciPy"),
             ("pandas", "pandas"), ("scikit-learn", "scikit-learn"))
SIN_CIFRA = "n/d"
MENOS = "−"
HUELLA = 12                  # caracteres de cada sha256 que se imprimen
RHO_EXTREMO = 0.6            # spec §4.5: a partir de aqui, «caso extremo, no plausible»
MODELOS = (("imagen", "imagen sola"), ("clinica", "clínica sola"),
           ("independencia", "combinación, independencia"),
           ("conservador", "combinación, extremo conservador"))
COMBINADOS = MODELOS[2:]
LADOS = (("todos", "todos los concordantes"), ("a_favor", "imagen a favor (RV ≥ 1)"),
         ("en_contra", "imagen en contra (RV < 1)"))
LADOS_DE_LA_IMAGEN = (("a_favor", "con la imagen a favor"),
                      ("en_contra", "con la imagen en contra"))
METRICAS = (("auc", "AUC", 3), ("brier", "Brier", 3), ("pendiente", "pendiente", 2),
            ("intercepto", "intercepto", 3), ("ece", "ECE", 3))
PAREADAS = (("auc", "ΔAUC", 3), ("brier", "ΔBrier", 3), ("pendiente", "Δpendiente", 2))
# Los titulos de las figuras, los nombres de las celdas y el titulo del
# documento se escriben aqui y solo aqui: el guion los toma de este modulo.
# Los nombres de las figuras los dice tambien el guion, que es quien sabe
# que funcion dibuja cada una; una prueba ata las dos listas.
PREFIJO_FIABILIDAD = "fiabilidad_"
TITULO_FIABILIDAD = "Fiabilidad por deciles"
FIGURAS_GLOBALES = (
    ("horquilla_por_celda", "El oráculo frente a la horquilla, por celda y lado"),
    ("contencion_rejilla", "Contención del oráculo en la horquilla, por celda"),
    ("pendiente_rejilla", "Pendiente de la independencia, por celda"),
)


# ---------------------------------------------------------------------------
# Formatos
# ---------------------------------------------------------------------------
def _falta(x) -> bool:
    return x is None or (isinstance(x, float) and not math.isfinite(x))


def numero(x, decimales: int = 3, signo: bool = False) -> str:
    """La cifra con coma decimal y un espacio en los millares; con `signo`,
    las positivas llevan «+». Un valor que se redondea a cero no lleva signo."""
    if _falta(x):
        return SIN_CIFRA
    x = float(x)
    texto = f"{abs(x):,.{decimales}f}"
    nulo = float(texto.replace(",", "")) == 0.0
    texto = texto.replace(",", " ").replace(".", ",")
    if x < 0 and not nulo:
        return MENOS + texto
    if signo and not nulo:
        return "+" + texto
    return texto


def porcentaje(x, decimales: int = 1) -> str:
    if _falta(x):
        return SIN_CIFRA
    return numero(100.0 * float(x), decimales) + " %"


def entero(n) -> str:
    """Con un espacio en los millares: 3 811."""
    if _falta(n):
        return SIN_CIFRA
    return f"{int(n):,}".replace(",", " ")


def rho(x) -> str:
    return f"{float(x):g}".replace(".", ",")


def huella(sha256: str) -> str:
    return str(sha256)[:HUELLA]


def _valor(d: dict, ruta: str):
    for clave in ruta.split("."):
        d = d[clave]
    return d


def _intervalo(celda: dict, ruta: str, formato) -> str:
    """« (IC 95 %: a a b)» si la celda tiene intervalo para esa ruta."""
    par = (celda.get("intervalos") or {}).get(ruta)
    if not par:
        return ""
    return f" (IC 95 %: {formato(par[0])} a {formato(par[1])})"


def _par(celda: dict, ruta: str):
    """El intervalo de esa ruta, o None si la celda no lo lleva o no son dos
    cifras."""
    par = (celda.get("intervalos") or {}).get(ruta)
    if not par or _falta(par[0]) or _falta(par[1]):
        return None
    return par


def _a_la_vista(x, decimales: int) -> float:
    """La cifra con los decimales con que se imprime. Las comparaciones de la
    prosa se hacen asi: el documento no afirma de una cifra lo que su forma
    impresa no deja ver (un extremo 1,004 se imprime «1,00» y no queda por
    encima de 1)."""
    return float(f"{float(x):.{decimales}f}")


def _umbral(x) -> str:
    """Un umbral, en porcentaje y con los decimales que tenga: «90», «90,5».
    Se imprime con la misma precision con que `_alcanza` lo compara."""
    return f"{_a_la_vista(100.0 * x, 1):g}".replace(".", ",")


def _alcanza(x, umbral) -> bool:
    """Si una fraccion alcanza un umbral que se cumple con la igualdad («≥»),
    con las dos cifras tal como se imprimen: en porcentaje y con un decimal."""
    return _a_la_vista(100.0 * x, 1) >= _a_la_vista(100.0 * umbral, 1)


def _cifra(celda: dict, ruta: str, decimales: int, signo: bool = False) -> str:
    return (numero(_valor(celda, ruta), decimales, signo)
            + _intervalo(celda, ruta, lambda v: numero(v, decimales, signo)))


def _fraccion(celda: dict, ruta: str) -> str:
    """Un porcentaje con su intervalo: «70,7 % (IC 95 %: 69,5 a 72,7)»."""
    return (porcentaje(_valor(celda, ruta))
            + _intervalo(celda, ruta, lambda v: numero(None if _falta(v) else 100.0 * v, 1)))


def _cuartiles(d: dict, decimales: int = 2) -> str:
    """«mediana (q1 a q3)»."""
    if _falta(d["mediana"]):
        return SIN_CIFRA
    return (f"{numero(d['mediana'], decimales)} "
            f"({numero(d['q1'], decimales)} a {numero(d['q3'], decimales)})")


def _tabla(cabeceras, filas, izquierdas: int = 1, texto=()) -> list:
    """Una tabla de Markdown: las primeras columnas y las de `texto` (por su
    cabecera) a la izquierda, las cifras a la derecha."""
    guia = [":---" if i < izquierdas or cabecera in texto else "---:"
            for i, cabecera in enumerate(cabeceras)]
    lineas = ["| " + " | ".join(cabeceras) + " |", "| " + " | ".join(guia) + " |"]
    lineas += ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]
    return lineas + [""]


def _lista(nombres) -> str:
    """«a, b y c»."""
    nombres = list(nombres)
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _nombradas(celdas) -> str:
    """Cuantas celdas y cuales: «ninguna», «1, que es a», «3, que son a, b y c»."""
    nombres = [c["nombre"] for c in celdas]
    if not nombres:
        return "ninguna"
    return f"{len(nombres)}, que {'es' if len(nombres) == 1 else 'son'} {_lista(nombres)}"


def _con_su_cifra(celdas, ruta: str, decimales: int) -> str:
    """«: a, 0,87 (IC 95 %: 0,81 a 0,92); b, ...», o nada si no hay celdas."""
    if not celdas:
        return ""
    return ": " + "; ".join(f"{c['nombre']}, {_cifra(c, ruta, decimales)}" for c in celdas)


def _semilla(x) -> str:
    """Una semilla se copia y se pega: sin separador de millares."""
    return SIN_CIFRA if _falta(x) else str(int(x))


def _transiciones(bandas: dict) -> str:
    if not bandas["transiciones"]:
        return "ninguna"
    return "; ".join(f"{sentido}: {entero(n)}" for sentido, n in bandas["transiciones"].items())


def slug_de_celda(celda: dict) -> str:
    """El nombre de una celda en sus ficheros: `0a` para 0A; `r1-030_r0-000`
    para el resto (ρ × 100, tres cifras)."""
    if celda["nombre"] == "0A":
        return "0a"
    return f"r1-{round(celda['rho1'] * 100):03d}_r0-{round(celda['rho0'] * 100):03d}"


def _frente_al_suelo(ece, suelo: dict) -> str:
    """La ECE solo se lee al lado de su suelo de ruido."""
    if _falta(ece) or _falta(suelo["p95"]):
        return "no se puede comparar con su suelo"
    if _a_la_vista(ece, 3) <= _a_la_vista(suelo["p95"], 3):
        return "no supera el percentil 95 de su suelo: no se distingue del ruido de muestreo"
    return "supera el percentil 95 de su suelo: hay descalibración más allá del ruido de muestreo"


# ---------------------------------------------------------------------------
# Las celdas
# ---------------------------------------------------------------------------
def _cero(resultados: dict):
    for celda in resultados["celdas"]:
        if celda["nombre"] == "0A":
            return celda
    return None


def _destacadas(resultados: dict) -> list:
    return [c for c in resultados["celdas"] if c["destacada"]]


def celdas_completas(resultados: dict) -> list:
    """0A y las destacadas, en el orden de la rejilla: las que llevan
    intervalos y figura de fiabilidad."""
    return [c for c in resultados["celdas"] if c["nombre"] == "0A" or c["destacada"]]


def _la_fila_0a_se_cumple(cero: dict) -> bool:
    """Colas exactamente 0 y contencion 100 %: la comprobacion de la metrica.
    Es exacta, no «tal como se imprime»: un solo caso fuera la incumple."""
    h = cero["horquilla"]["todos"]
    return h["bajo"] == 0 and h["sobre"] == 0 and h["contencion"] == 1


def _estado_de_0a(cero: dict) -> str:
    """`cumple`, `no_cumple` o `sin_casos`: sin casos con horquilla la
    comprobacion no se puede hacer, que no es lo mismo que fallarla."""
    h = cero["horquilla"]["todos"]
    if _falta(h["bajo"]) or _falta(h["sobre"]) or not h["n"]:
        return "sin_casos"
    return "cumple" if _la_fila_0a_se_cumple(cero) else "no_cumple"


def _la_fila_0a(cero: dict) -> str:
    """Lo que se dice debajo de la fila 0A. Si no se cumple se da la cuenta:
    la tabla puede imprimir «0,0 %» con un caso fuera."""
    estado = _estado_de_0a(cero)
    if estado == "sin_casos":
        return ("**No se puede comprobar: no hay casos concordantes con horquilla. Las "
                "tablas de la horquilla de este documento quedan sin la comprobación de "
                "0A.**")
    if estado == "cumple":
        return "Se cumple: la métrica de la horquilla pasa su comprobación en el caso nulo."
    h = cero["horquilla"]["todos"]
    fuera = round((h["bajo"] + h["sobre"]) * h["n"])
    return (f"**NO se cumple: {'queda' if fuera == 1 else 'quedan'} fuera de la horquilla "
            f"{entero(fuera)} de los {entero(h['n'])} concordantes. La métrica de la "
            f"horquilla o el generador tienen un defecto, y las tablas de la horquilla de "
            f"este documento no se pueden leer hasta corregirlo.**")


def _que_previo(insumos: dict) -> str:
    """El previo del analisis principal es el del calibrador: se dice si es,
    como tiene que ser, la prevalencia del conjunto."""
    del_conjunto = (insumos["positivas"] / insumos["placas"] if insumos["placas"] else None)
    if numero(del_conjunto, 4) == numero(insumos["prevalencia"], 4):
        return "el del calibrador, que es la prevalencia del conjunto"
    return (f"el del calibrador, que **no es la prevalencia del conjunto** "
            f"({numero(del_conjunto, 4)})")


def _pendiente_de_0a(cero: dict) -> str:
    """La pendiente de la independencia en 0A, con lo que dice su intervalo."""
    par = _par(cero, "modelos.independencia.pendiente")
    return (_cifra(cero, "modelos.independencia.pendiente", 2)
            + ("" if par is None else
               "; su intervalo contiene el 1"
               if _a_la_vista(par[0], 2) <= 1 <= _a_la_vista(par[1], 2)
               else "; su intervalo no contiene el 1"))


VEREDICTOS = {
    "se_sostiene": "se sostiene",
    "no_se_sostiene": "no se sostiene",
    "no_se_puede_decir": "no se puede decir: la estimación y su intervalo no quedan "
                         "enteros a un lado del umbral",
    "punto_si": "se sostiene (estimación puntual, sin intervalo)",
    "punto_no": "no se sostiene (estimación puntual, sin intervalo)",
    "sin_casos": "no se puede decir: no hay casos concordantes con horquilla",
}


def _veredicto(celda: dict) -> tuple:
    """(clave, texto) del veredicto de la hipotesis en una celda. Con
    intervalo decide el intervalo ENTERO, y tiene que quedar del mismo lado
    del umbral que la estimacion; sin el, solo esta la estimacion puntual, y
    el texto lo dice. Todo, con las cifras tal como se imprimen: una
    contencion que se imprime «90,0 %» alcanza un umbral del 90 %."""
    umbral = celda["hipotesis"]["umbral"]
    punto = celda["horquilla"]["todos"]["contencion"]
    if _falta(punto):
        clave = "sin_casos"
    else:
        par = _par(celda, "horquilla.todos.contencion")
        alcanza = _alcanza(punto, umbral)
        if par is None:
            clave = "punto_si" if alcanza else "punto_no"
        elif alcanza and _alcanza(par[0], umbral):
            clave = "se_sostiene"
        elif not alcanza and not _alcanza(par[1], umbral):
            clave = "no_se_sostiene"
        else:
            clave = "no_se_puede_decir"
    return clave, VEREDICTOS[clave]


# ---------------------------------------------------------------------------
# Las secciones
# ---------------------------------------------------------------------------
def _cabecera(r: dict) -> list:
    return [
        f"# {TITULO}",
        "",
        f"**{r['advertencia']}**",
        "",
        f"> Este documento es GENERADO por `{GUION}` a partir de `{RESULTADOS}`: ninguna "
        f"cifra se teclea y no se edita a mano. Para cambiar una frase se cambia "
        f"`{GENERADOR}` y se vuelve a generar; para cambiar una cifra, se vuelve a correr "
        f"la simulación.",
        "",
    ]


def _insumos(r: dict) -> list:
    i, p = r["insumos"], r["parametros"]
    destacadas = [c["nombre"] for c in _destacadas(r)]
    replicas = (f"{entero(p['replicas'])} réplicas en 0A y en las celdas destacadas; cada "
                f"réplica remuestrea con reemplazo los casos de la estimación puntual, "
                f"cada placa con la clínica que se le sorteó (una placa por paciente, así "
                f"que es un bootstrap por paciente). La clínica no se vuelve a sortear: "
                f"el remuestreo de los casos ya lleva el ruido del sorteo, y sortearla "
                f"otra vez lo contaría dos veces. Intervalos del 95 % por percentiles; las "
                f"diferencias entre modelos se calculan dentro de cada réplica (pareadas)"
                if p["replicas"] else
                "sin bootstrap: esta corrida no tiene intervalos")
    return [
        "## Insumos y parámetros",
        "",
        "Qué es real y qué se supone:",
        "",
        f"- **Placas y verdad:** las {entero(i['placas'])} placas del conjunto de prueba de "
        f"RSNA (una por paciente; {entero(i['positivas'])} positivas, prevalencia "
        f"{numero(i['positivas'] / i['placas'] if i['placas'] else None, 4)}), nunca "
        f"usadas para entrenar ni calibrar, con su "
        f"etiqueta real de opacidad. Es un desenlace análogo al de Heckerling (infiltrado "
        f"radiográfico) en una población distinta: RSNA no es una cohorte con sospecha de "
        f"neumonía.",
        "- **Clínica:** a cada placa se le sortea la puntuación de Heckerling dada su "
        "etiqueta, con las frecuencias publicadas de la cohorte de derivación. No se "
        "inventa la exactitud de la regla: se usa la publicada, tal como la usa el sistema. "
        "Cada placa con su clínica sorteada es una viñeta.",
        "- **Dependencia:** la estructura de dependencia entre clínica e imagen es un "
        "supuesto: nula en 0A y barrida en el resto de la rejilla.",
        "- **Transporte:** el generador supone que la distribución de la puntuación por "
        "clase, medida en la cohorte de derivación, se transporta al espectro de RSNA. Eso "
        "no se comprueba ni se puede comprobar aquí.",
        "",
        "Los términos que se repiten:",
        "",
        "- **RV:** razón de verosimilitud. La RV de recuentos de una puntuación sale de "
        "las frecuencias publicadas de esa puntuación en cada clase; la RV de la imagen, "
        "de la probabilidad calibrada de la placa.",
        "- **Oráculo:** la probabilidad posterior que da el propio generador de la "
        "simulación con la misma información que ve el sistema: la imagen y la "
        "puntuación (con el asma desconocida, la puntuación de los otros cuatro "
        "hallazgos). Es la verdad de la simulación, no la de un paciente.",
        "- **Modelos puntuales:** la imagen sola (la probabilidad calibrada de la placa); "
        "la clínica sola (el previo con la RV de la puntuación, sin imagen); la "
        "combinación por independencia (el previo con las dos RV); y el extremo "
        "conservador de la combinación (dependencia total: solo cuenta la evidencia más "
        "informativa; en los casos discordantes es el mismo número que la "
        "independencia).",
        "- **Clases:** «con opacidad» y «sin opacidad» son las dos clases de la etiqueta "
        "de RSNA, que en la simulación hace de desenlace.",
        "",
        "Con qué se calculó:",
        "",
        f"- Puntuaciones crudas del modelo desplegado: `{i['crudas']}` "
        f"(sha256 `{huella(i['crudas_sha256'])}…`), generadas con los pesos de sha256 "
        f"`{huella(i['pesos_sha256'])}…`.",
        f"- Calibrador: `{i['calibrador']}` (sha256 `{huella(i['calibrador_sha256'])}…`).",
        f"- Previo del análisis principal: {numero(i['prevalencia'], 4)}, {_que_previo(i)}. "
        f"El previo desplegado, "
        f"{numero(p['previo_desplegado'], 4)}, solo entra en la sensibilidad al previo.",
        f"- Rejilla: ρ1 y ρ0 toman los valores {' / '.join(rho(x) for x in p['rejilla'])}: "
        f"{entero(len(r['celdas']))} celdas. El origen es 0A y se cuenta aparte; "
        + (f"celdas destacadas: {_lista(destacadas)}." if destacadas
           else "esta corrida no tiene celdas destacadas."),
        f"- Bootstrap: {replicas}.",
        f"- Semillas: clínica, {_semilla(p['semilla_puntual'])}; casos de la réplica b, "
        f"{_semilla(p['semilla_indices'])} + b.",
        f"- Tolerancia de las colas de la horquilla: ε = {numero(p['epsilon'], 3)} log-odds, "
        f"que cubre el redondeo de las RV publicadas (la misma tolerancia de la "
        f"comprobación 0A).",
        f"- ECE: {entero(p['bins'])} tramos de igual masa, con los empates rotos por el orden "
        f"del identificador de la placa. Su suelo de ruido: "
        f"{entero(p['repeticiones_suelo'])} juegos de etiquetas simuladas con las "
        f"probabilidades del propio modelo (semilla {_semilla(p['semilla_suelo'])}); se "
        f"publican la media y el percentil 95.",
        f"- Hipótesis de la horquilla: contención ≥ "
        f"{_umbral(p['hipotesis_contencion'])} % de los concordantes.",
        "",
    ]


def _imagen_sola(r: dict) -> list:
    m = r["imagen_sola"]
    return [
        "## La imagen sola",
        "",
        f"La probabilidad calibrada de la imagen sobre las {entero(m['casos'])} placas. El "
        f"oráculo toma esa probabilidad como la verdad de la imagen: así la diferencia entre "
        f"el sistema y el oráculo aísla la parte clínica, y la calibración de la imagen se "
        f"publica aparte, aquí, como el suelo de calibración de todo lo demás.",
        "",
        *_tabla(["AUC", "Brier", "pendiente", "intercepto", "ECE", "suelo de la ECE (media)",
                 "suelo de la ECE (p95)"],
                [[numero(m["auc"], 3), numero(m["brier"], 3), numero(m["pendiente"], 2),
                  numero(m["intercepto"], 3), numero(m["ece"], 3),
                  numero(m["suelo"]["media"], 3), numero(m["suelo"]["p95"], 3)]],
                izquierdas=0),
        f"La ECE ({numero(m['ece'], 3)}) {_frente_al_suelo(m['ece'], m['suelo'])}. La ECE "
        f"solo se lee al lado de su suelo, nunca contra un umbral absoluto. Una pendiente "
        f"menor que 1 quiere decir que el modelo exagera; mayor que 1, que se queda corto.",
        "",
    ]


def _fila_de_modelo(celda: dict, clave: str, con_intervalos: bool) -> list:
    m = celda["modelos"][clave]
    # la ECE va siempre sin intervalo: se lee al lado de su suelo
    cifras = [(_cifra(celda, f"modelos.{clave}.{metrica}", decimales)
               if con_intervalos and metrica != "ece" else numero(m[metrica], decimales))
              for metrica, _, decimales in METRICAS]
    return cifras + [numero(m["suelo"]["media"], 3), numero(m["suelo"]["p95"], 3)]


def _escenario_0a(r: dict) -> list:
    lineas = [
        "## Escenario 0A: la aritmética",
        "",
        "Con dependencia nula (ρ1 = ρ0 = 0) el oráculo de cada caso es la suma, en log-odds, "
        "de la evidencia de la imagen y del logaritmo de la RV de recuentos de su "
        "puntuación. Las tres comprobaciones de 0A son deterministas y caso a caso, y no "
        f"viven en este documento sino en `{PRUEBA_0A}`: la puntuación que calcula el "
        "sistema es la que sorteó el generador; el bloque que entrega es el redondeo de su "
        "propia aritmética; y la posterior del sistema coincide con la del oráculo dentro "
        f"de ε = {numero(r['parametros']['epsilon'], 3)} log-odds en todos los casos. Son "
        "pruebas, no estadísticas: una RV o un corte mutados las hacen fallar.",
        "",
        "Lo que 0A puede demostrar es que el sistema calcula lo que dice calcular; no que "
        "la posterior sea exacta en pacientes.",
        "",
    ]
    cero = _cero(r)
    if cero is None:
        return lineas + ["Esta corrida no incluye la celda 0A.", ""]
    n = cero["recuentos"]
    h = cero["horquilla"]["todos"]
    lineas += [
        f"Los cuatro modelos puntuales en 0A, sobre los {entero(n['asma_conocida'])} casos "
        f"con el asma conocida:",
        "",
        *_tabla(["modelo"] + [titulo for _, titulo, _ in METRICAS]
                + ["suelo de la ECE (media)", "suelo de la ECE (p95)"],
                [[nombre] + _fila_de_modelo(cero, clave, True) for clave, nombre in MODELOS]),
        f"La ECE va sin intervalo: se lee al lado de su suelo. La de la combinación por "
        f"independencia "
        f"({numero(cero['modelos']['independencia']['ece'], 3)}) "
        f"{_frente_al_suelo(cero['modelos']['independencia']['ece'], cero['modelos']['independencia']['suelo'])}.",
        "",
        "**La fila 0A de la horquilla es la comprobación de la métrica.** Con ρ = 0 el único "
        "desvío entre el sistema y el oráculo es el redondeo de las RV, así que las dos "
        "colas tienen que ser exactamente 0 y la contención, 100 %:",
        "",
        *_tabla(["celda", "concordantes", "por el lado conservador",
                 "más allá de la independencia", "contención"],
                [[cero["nombre"], entero(h["n"]), _fraccion(cero, "horquilla.todos.bajo"),
                  _fraccion(cero, "horquilla.todos.sobre"),
                  _fraccion(cero, "horquilla.todos.contencion")]]),
        _la_fila_0a(cero),
        "",
    ]
    return lineas


def _dependencia(r: dict) -> list:
    p = r["parametros"]
    celdas = celdas_completas(r)
    mayor = max(p["rejilla"])
    extremo = (f" Un ρ de {rho(mayor)} sobre la puntuación es un caso extremo, no plausible: "
               f"se incluye para acotar, no porque se espere." if mayor >= RHO_EXTREMO else "")
    lineas = [
        "## Dependencia entre clínica e imagen",
        "",
        "Crepitantes, murmullo y opacidad son el mismo fenómeno físico visto de dos maneras: "
        "la clínica y la imagen no son independientes. El sistema solo ve la puntuación, y "
        "los recuentos publicados no la descomponen por hallazgo; por eso la dependencia se "
        "induce sobre la puntuación entera. **ρ1** es la correlación latente, entre los "
        "casos con opacidad, entre lo que la puntuación mide y lo que la imagen mide; "
        "**ρ0**, la misma entre los casos sin opacidad. Temperatura, pulso y asma diluyen "
        f"esa correlación.{extremo}",
        "",
        "Son dos parámetros y no uno porque con un solo ρ, simétrico, la dirección del sesgo "
        "quedaría decidida de antemano por el diseño. Con dos, la dirección es un resultado "
        "de cada celda y de cada lado de la imagen, no una premisa. En todas las celdas la "
        "distribución de la puntuación dentro de cada clase es la publicada: lo que cambia "
        "es la RV de la puntuación una vez vista la imagen.",
        "",
        "La correlación de Pearson, dentro de cada clase, entre la puntuación y la imagen "
        "que implica cada celda:",
        "",
        *_tabla(["celda", "ρ1", "ρ0", "correlación con opacidad", "correlación sin opacidad"],
                [[c["nombre"], rho(c["rho1"]), rho(c["rho0"]),
                  numero(c["correlacion_teorica"]["con_opacidad"], 3),
                  numero(c["correlacion_teorica"]["sin_opacidad"], 3)] for c in celdas]),
        "Los cuatro modelos puntuales por celda (casos con el asma conocida). "
        + ("La pendiente lleva su intervalo; la ECE va al lado de su suelo:"
           if any(_par(c, "modelos.independencia.pendiente") for c in celdas)
           else "La ECE va al lado de su suelo:"),
        "",
    ]
    filas = []
    for c in celdas:
        for clave, nombre in MODELOS:
            m = c["modelos"][clave]
            filas.append([c["nombre"], nombre, numero(m["auc"], 3), numero(m["brier"], 3),
                          _cifra(c, f"modelos.{clave}.pendiente", 2),
                          numero(m["intercepto"], 3), numero(m["ece"], 3),
                          numero(m["suelo"]["media"], 3), numero(m["suelo"]["p95"], 3)])
    lineas += _tabla(["celda", "modelo", "AUC", "Brier", "pendiente", "intercepto", "ECE",
                      "suelo de la ECE (media)", "suelo de la ECE (p95)"], filas, izquierdas=2)
    lineas += ["La fila de la imagen sola cambia de una celda a otra aunque el modelo de "
               "imagen es el mismo: cada celda sortea su clínica, y con ella qué casos "
               "quedan con el asma desconocida, así que los casos con el asma conocida no "
               "son los mismos en todas. Por eso su ECE puede superar el percentil 95 de "
               "su suelo en una celda y no en otra sin que la imagen cambie.", ""]
    lineas += ["Diferencias pareadas de cada combinación frente a la imagen sola (combinación "
               "menos imagen, sobre los mismos casos):", ""]
    lineas += _tabla(
        ["celda", "modelo"] + [titulo for _, titulo, _ in PAREADAS],
        [[c["nombre"], nombre]
         + [_cifra(c, f"pareadas.{clave}.{metrica}", decimales, signo=True)
            for metrica, _, decimales in PAREADAS]
         for c in celdas for clave, nombre in COMBINADOS], izquierdas=2)
    lineas += ["Un ΔBrier negativo es una mejora. Estas diferencias dicen cuánto aporta la "
               "clínica sorteada en la simulación, no cuánto aporta la clínica en pacientes.",
               ""]
    return lineas


def _horquilla(r: dict) -> list:
    p = r["parametros"]
    umbral = _umbral(p["hipotesis_contencion"])
    celdas = celdas_completas(r)
    lineas = [
        "## La horquilla frente al oráculo",
        "",
        "La horquilla solo existe en los casos concordantes (clínica e imagen del mismo lado) "
        "con el asma conocida. Sus extremos son el conservador (dependencia total: solo "
        "cuenta la evidencia más informativa) y la independencia. La posición del oráculo se "
        "mide con λ, en log-odds: λ = 0 es el extremo conservador y λ = 1, la independencia.",
        "",
        f"- **Por el lado conservador:** el oráculo queda más allá del extremo conservador en "
        f"más de ε = {numero(p['epsilon'], 3)} log-odds. Ni la dependencia total recoge tanta "
        f"redundancia.",
        "- **Más allá de la independencia:** el oráculo queda más allá de la independencia en "
        "más de ε. La independencia se queda corta.",
        "- **Contención:** el complemento de las dos colas. Se llama contención y no "
        "cobertura: no es un intervalo de confianza.",
        "",
        f"**Hipótesis declarada de antemano, a refutar celda a celda:** «el oráculo queda "
        f"dentro de la horquilla en ≥ {umbral} % de los concordantes». La expectativa, "
        f"medida sobre el conjunto durante el diseño y no declarada a ciegas, era que solo "
        f"se sostuviera en 0A y en las celdas más suaves. Una contención baja es un "
        f"resultado igual de publicable, y obliga a repensar la cota, no a ocultarla.",
        "",
    ]
    filas = []
    for c in celdas:
        for lado, nombre in LADOS:
            h = c["horquilla"][lado]
            filas.append([c["nombre"], nombre, entero(h["n"]), _cuartiles(h["lambda"]),
                          _fraccion(c, f"horquilla.{lado}.bajo"),
                          _fraccion(c, f"horquilla.{lado}.sobre"),
                          _fraccion(c, f"horquilla.{lado}.contencion")])
    lineas += _tabla(["celda", "lado de la imagen", "n", "λ: mediana (q1 a q3)",
                      "por el lado conservador", "más allá de la independencia",
                      "contención"], filas, izquierdas=2)
    sin_horquilla = sum(c["horquilla"]["todos"]["sin_horquilla"] for c in celdas)
    lineas += [f"Casos concordantes sin horquilla (RV de imagen exactamente 1) en estas "
               f"celdas: {entero(sin_horquilla)}.", "",
               "El veredicto, celda a celda, sobre todos los concordantes. Donde hay "
               "intervalo decide el intervalo entero: si la estimación y su intervalo no "
               "quedan enteros a un lado del umbral, no se puede decir. Donde no lo hay "
               "solo está la estimación puntual, y el veredicto lo dice. Se decide con la "
               f"contención tal como se imprime (un «{porcentaje(p['hipotesis_contencion'])}» "
               f"alcanza un umbral del {umbral} %). El campo `se_sostiene` del fichero de "
               "resultados mira solo la estimación, sin su intervalo y sin redondear, y "
               "puede no coincidir con esta columna:", ""]
    lineas += _tabla(
        ["celda", "contención", "umbral", "veredicto"],
        [[c["nombre"], _fraccion(c, "horquilla.todos.contencion"),
          f"≥ {_umbral(c['hipotesis']['umbral'])} %", _veredicto(c)[1]]
         for c in r["celdas"]], texto=("veredicto",))
    lineas += ["**Casos discordantes** (clínica e imagen en lados opuestos): el sistema da un "
               "solo número, el de la independencia. Error frente al oráculo, en log-odds; "
               "el sesgo es sistema menos oráculo:", ""]
    lineas += _tabla(
        ["celda", "n", "error absoluto mediano", "sesgo mediano"],
        [[c["nombre"], entero(c["discordantes"]["n"]),
          _cifra(c, "discordantes.error_abs_mediano", 3),
          _cifra(c, "discordantes.sesgo_mediano", 3, signo=True)] for c in celdas])
    lineas += ["**Casos con el asma desconocida:** el sistema entrega un rango (dos "
               "puntuaciones posibles) y el oráculo marginaliza el asma con la misma "
               "información. La tabla dice si el oráculo cae dentro de ese rango, con la "
               "misma ε, y el error, en log-odds, de la media de las dos posteriores de "
               "independencia (una por puntuación posible). Esa media no es el centro del "
               "rango cuando clínica e imagen son concordantes, porque entonces el rango "
               "incluye además los extremos conservadores; tampoco es el punto medio con "
               "que se decide la categoría del sistema, que sí es el del rango:", ""]
    lineas += _tabla(
        ["celda", "n", "por debajo del rango", "por encima del rango", "dentro",
         "media de las independencias: error absoluto mediano",
         "media de las independencias: sesgo mediano"],
        [[c["nombre"], entero(c["no_se"]["n"]), _fraccion(c, "no_se.bajo"),
          _fraccion(c, "no_se.sobre"), _fraccion(c, "no_se.contencion"),
          _cifra(c, "no_se.punto_medio.error_abs_mediano", 3),
          _cifra(c, "no_se.punto_medio.sesgo_mediano", 3, signo=True)] for c in celdas])
    lineas += ["Cuántos casos hay de cada tipo:", ""]
    lineas += _tabla(
        ["celda", "casos", "asma conocida", "concordantes", "concordantes, imagen a favor",
         "concordantes, imagen en contra", "discordantes", "asma desconocida"],
        [[c["nombre"]] + [entero(c["recuentos"][clave]) for clave in (
            "casos", "asma_conocida", "concordantes", "concordantes_a_favor",
            "concordantes_en_contra", "discordantes", "no_se")] for c in celdas])
    return lineas


def _escala_legible(r: dict) -> list:
    lineas = [
        "## Cuánto de su evidencia conserva la puntuación",
        "",
        "Por puntuación y por lado de la imagen: la RV de la puntuación una vez vista la "
        "imagen, en log-odds, y la **fracción** de su log-RV de recuentos que conserva. Una "
        "fracción de 1 es la independencia (la puntuación conserva toda su evidencia); menor "
        "que 1, que la imagen ya contaba parte; mayor que 1, que la independencia se queda "
        "corta; negativa, que el signo se invierte. Las puntuaciones k = 2 y k = 3 se "
        "rotulan «poco informativa» (|ln RV de recuentos| < 0,5): dividir por un número tan "
        "pequeño amplifica cualquier variación. La dirección se lee por lado, no global.",
        "",
    ]
    cero = _cero(r)
    if cero is not None:
        fracciones = [cero["escala_legible"][lado]["fraccion_mediana_extremas"]
                      for lado, _ in LADOS_DE_LA_IMAGEN]
        entera = all(numero(f, 2) == numero(1.0, 2) for f in fracciones)
        lineas += ["En 0A la fracción mediana de las puntuaciones extremas (k ≤ 1 y k ≥ 4) es "
                   + _lista([f"{numero(f, 2)} {nombre}"
                             for f, (_, nombre) in zip(fracciones, LADOS_DE_LA_IMAGEN)])
                   + (": sin dependencia la puntuación conserva toda su evidencia." if entera
                      else f": **sin dependencia tendría que ser {numero(1.0, 2)} en los dos "
                           f"lados, y no lo es.**"), ""]
    destacadas = _destacadas(r)
    if not destacadas:
        return lineas + ["Esta corrida no tiene celdas destacadas.", ""]
    for c in destacadas:
        lineas += [f"### Celda {c['nombre']}", ""]
        lineas += ["Fracción mediana de las puntuaciones extremas (k ≤ 1 y k ≥ 4): "
                   + _lista([f"{numero(c['escala_legible'][lado]['fraccion_mediana_extremas'], 2)} "
                             f"{nombre}" for lado, nombre in LADOS_DE_LA_IMAGEN]) + ".", ""]
        for lado, nombre in LADOS[1:]:
            e = c["escala_legible"][lado]
            lineas += [f"{nombre[0].upper()}{nombre[1:]}, {entero(e['placas'])} placas:", ""]
            lineas += _tabla(
                ["k", "ln RV de recuentos", "casos esperados", "log-RV: mediana (q1 a q3)",
                 "fracción: mediana (q1 a q3)", "signo invertido", "rótulo"],
                [[str(f["k"]), numero(f["ln_rv_recuentos"], 3, signo=True),
                  numero(f["casos_esperados"], 1), _cuartiles(f["log_rv"]),
                  _cuartiles(f["fraccion"]), porcentaje(f["signo_invertido"]),
                  "poco informativa" if f["poco_informativa"] else ""]
                 for f in e["por_puntuacion"]], texto=("rótulo",))
    return lineas


def _rejilla(r: dict) -> list:
    return [
        "## La rejilla completa",
        "",
        f"Las {entero(len(r['celdas']))} celdas, sin intervalos (el bootstrap solo se corre "
        f"en 0A y en las destacadas). La contención y las colas son las de todos los "
        f"concordantes.",
        "",
        *_tabla(["celda", "destacada", "contención", "por el lado conservador",
                 "más allá de la independencia", "pendiente de la independencia",
                 "AUC de la independencia", "pendiente del extremo conservador"],
                [[c["nombre"], "sí" if c["destacada"] else "",
                  porcentaje(c["horquilla"]["todos"]["contencion"]),
                  porcentaje(c["horquilla"]["todos"]["bajo"]),
                  porcentaje(c["horquilla"]["todos"]["sobre"]),
                  numero(c["modelos"]["independencia"]["pendiente"], 2),
                  numero(c["modelos"]["independencia"]["auc"], 3),
                  numero(c["modelos"]["conservador"]["pendiente"], 2)]
                 for c in r["celdas"]], izquierdas=2),
    ]


def _sensibilidad(r: dict) -> list:
    celdas = [c for c in r["celdas"] if "sensibilidad_al_previo" in c]
    lineas = ["## Sensibilidad al previo", ""]
    if not celdas:
        return lineas + ["Esta corrida no calculó la sensibilidad al previo.", ""]
    s = celdas[0]["sensibilidad_al_previo"]
    previo, principal = numero(s["previo"], 4), numero(s["previo_principal"], 4)
    d = s["desplazamiento_log_odds"]
    lineas += [
        f"El análisis principal usa como previo {principal} (el de «Insumos y parámetros»); "
        f"el sistema desplegado arranca con {previo}. Declarar {previo} donde el análisis "
        f"principal usa {principal} tiene un efecto analítico: todas las odds posteriores se multiplican "
        f"por {numero(math.exp(d), 3)}, es decir, se desplazan {numero(d, 2, signo=True)} en "
        f"log-odds por igual. El intercepto de calibración debe moverse, por tanto, en "
        f"torno a {numero(-d, 2, signo=True)} respecto del principal.",
        "",
        "**El AUC no cambia** (un desplazamiento común no altera el orden de los casos) y "
        "no se reporta en esta tabla. **Esto no recomienda configurar el despliegue con "
        f"{principal}:** es el previo de un conjunto de datos de un reto, no la prevalencia "
        "de ningún servicio.",
        "",
        f"Con el previo {previo} (casos con el asma conocida); «principal» es la misma cifra "
        f"con {principal}. Las bandas son baja (< 20 %), intermedia (20-70 %) y alta "
        f"(> 70 %): una convención del equipo, no un estándar publicado:",
        "",
    ]
    filas = []
    for c in celdas:
        for clave, nombre in COMBINADOS:
            m = c["sensibilidad_al_previo"]["modelos"][clave]
            filas.append([
                c["nombre"], nombre, numero(m["brier"], 3), numero(m["brier_principal"], 3),
                numero(m["ece"], 3),
                f"{numero(m['suelo']['media'], 3)}; {numero(m['suelo']['p95'], 3)}",
                numero(m["ece_principal"], 3), numero(m["intercepto"], 3, signo=True),
                numero(m["intercepto_principal"], 3, signo=True),
                numero(None if _falta(m["intercepto"]) or _falta(m["intercepto_principal"])
                       else m["intercepto"] - m["intercepto_principal"], 3, signo=True),
                f"{entero(m['bandas']['cambian'])} de {entero(m['bandas']['casos'])}",
                _transiciones(m["bandas"])])
    lineas += _tabla(["celda", "modelo", "Brier", "Brier principal", "ECE",
                      "suelo de la ECE (media; p95)", "ECE principal", "intercepto",
                      "intercepto principal", "diferencia", "cambian de banda",
                      "en qué sentido"], filas, izquierdas=2, texto=("en qué sentido",))
    lineas += ["La categoría del sistema (todos los casos, también los del asma "
               "desconocida). El sistema no imprime ninguna categoría: entrega un rango, "
               "[mínima, máxima]. La categoría es una regla de este análisis: la banda "
               "del punto medio, en log-odds, de ese rango:", ""]
    lineas += _tabla(
        ["celda", "cambian de categoría", "en qué sentido"],
        [[c["nombre"],
          f"{entero(c['sensibilidad_al_previo']['categoria_del_sistema']['cambian'])} de "
          f"{entero(c['sensibilidad_al_previo']['categoria_del_sistema']['casos'])}",
          _transiciones(c["sensibilidad_al_previo"]["categoria_del_sistema"])]
         for c in celdas], texto=("en qué sentido",))
    return lineas


def _optimismo(r: dict) -> list:
    lineas = ["## 0C: optimismo de la derivación (cálculo, no experimento)", ""]
    cero = _cero(r)
    if cero is None or "optimismo_de_la_derivacion" not in cero:
        return lineas + ["Esta corrida no calculó 0C.", ""]
    o = cero["optimismo_de_la_derivacion"]
    mas, menos, iguales = [], [], []
    for f in o["por_puntuacion"]:
        derivacion = abs(math.log(f["rv_derivacion"]))
        validacion = abs(math.log(f["rv_validacion"]))
        (mas if derivacion > validacion else menos if derivacion < validacion
         else iguales).append(str(f["k"]))
    reparto = []
    if mas:
        reparto.append(f"más extrema que la de validación en k = {_lista(mas)}")
    if menos:
        reparto.append(f"menos extrema en k = {_lista(menos)}")
    if iguales:
        reparto.append(f"igual de extrema en k = {_lista(iguales)}")
    lineas += [
        "El sistema usa las RV de la cohorte de derivación, por puntuación; la validación "
        "externa solo las publica por bandas de puntuación. **Esto es un cálculo, no un "
        "experimento:** no se sortea nada; se compara, puntuación a puntuación, la RV de la "
        "derivación con la de la banda de validación que le corresponde.",
        "",
        *_tabla(["k", "RV de la derivación", "RV de la validación",
                 "ln RV derivación − ln RV validación"],
                [[str(f["k"]), numero(f["rv_derivacion"], 2), numero(f["rv_validacion"], 2),
                  numero(f["diferencia_log"], 2, signo=True)] for f in o["por_puntuacion"]]),
        f"La RV de la derivación es {_lista(reparto)} (más extrema: más lejos de 1)."
        + (" El «optimismo» de la derivación no es uniforme."
           if mas and (menos or iguales) else ""),
        "",
        f"Si el sistema usara las RV de la validación, cambiarían de banda "
        f"{entero(o['bandas']['cambian'])} de los {entero(o['bandas']['casos'])} casos con el "
        f"asma conocida de 0A (combinación por independencia): {_transiciones(o['bandas'])}.",
        "",
    ]
    return lineas


def _colas(h: dict) -> str:
    """Hacia donde cae el oraculo, leido de las dos colas."""
    dentro = f"queda dentro el {porcentaje(h['contencion'])}"
    bajo, sobre = h["bajo"], h["sobre"]
    if _falta(bajo) or _falta(sobre):
        return "no hay casos que medir"
    if bajo == 0 and sobre == 0:
        return f"{dentro}; ninguna cola tiene casos"
    # cual es la mayor, con las dos tal como se imprimen
    if _a_la_vista(100.0 * bajo, 1) == _a_la_vista(100.0 * sobre, 1):
        if _a_la_vista(100.0 * bajo, 1) == 0:
            # se imprimen «0,0 %» y alguna tiene casos: se dice cual
            con_casos = ("las dos tienen casos" if bajo > 0 and sobre > 0 else
                         "la del lado conservador tiene casos" if bajo > 0 else
                         "la de más allá de la independencia tiene casos")
            return (f"{dentro}; las dos colas se imprimen «{porcentaje(0.0)}», pero "
                    f"{con_casos}")
        return f"{dentro}; las dos colas pesan lo mismo ({porcentaje(bajo)} cada una)"
    if sobre > bajo:
        return (f"{dentro}; la cola mayor es la de más allá de la independencia "
                f"({porcentaje(sobre)}, frente a {porcentaje(bajo)} por el lado conservador)")
    return (f"{dentro}; la cola mayor es la del lado conservador ({porcentaje(bajo)}, frente "
            f"a {porcentaje(sobre)} más allá de la independencia)")


EJES = ("Dependencia simétrica (ρ1 = ρ0)",
        "Dependencia solo entre los casos con opacidad (ρ0 = 0)",
        "Dependencia solo entre los casos sin opacidad (ρ1 = 0)",
        "Otras celdas")


def _eje(celda: dict) -> str:
    if celda["rho1"] == celda["rho0"]:
        return EJES[0]
    if celda["rho0"] == 0:
        return EJES[1]
    if celda["rho1"] == 0:
        return EJES[2]
    return EJES[3]


def _fuera_de_su_intervalo(celdas) -> tuple:
    """(cuantas cifras con intervalo quedan fuera de el, cuantas hay). Se
    compara el valor crudo con los extremos crudos, SIN redondear (con una
    holgura de 1e-9 para el ruido de coma flotante), y la frase lo dice: es
    una cuenta sobre el fichero de resultados, no sobre lo impreso."""
    fuera = total = 0
    for celda in celdas:
        for ruta, par in (celda.get("intervalos") or {}).items():
            valor = _valor(celda, ruta)
            if _falta(valor) or _falta(par[0]) or _falta(par[1]):
                continue
            total += 1
            fuera += valor < par[0] - 1e-9 or valor > par[1] + 1e-9
    return fuera, total


def _en_el_borde(celdas) -> tuple:
    """(cuantos intervalos tienen anchura cero, en cuantos mas la estimacion
    coincide con un extremo). Sin redondear."""
    sin_anchura = en_un_extremo = 0
    for celda in celdas:
        for ruta, par in (celda.get("intervalos") or {}).items():
            valor = _valor(celda, ruta)
            if _falta(valor) or _falta(par[0]) or _falta(par[1]):
                continue
            if par[0] == par[1]:
                sin_anchura += 1
            elif valor in (par[0], par[1]):
                en_un_extremo += 1
    return sin_anchura, en_un_extremo


def _lo_del_borde(celdas) -> str:
    """La frase de los intervalos sin anchura o con la estimacion en un
    extremo; nada si no hay ninguno."""
    sin_anchura, en_un_extremo = _en_el_borde(celdas)
    if not sin_anchura and not en_un_extremo:
        return ""
    partes = []
    if sin_anchura:
        partes.append(f"{entero(sin_anchura)} {'tiene' if sin_anchura == 1 else 'tienen'} "
                      f"anchura cero")
    if en_un_extremo:
        partes.append(f"en {entero(en_un_extremo)}{' más' if sin_anchura else ''} la "
                      f"estimación coincide con un extremo")
    return (f" De esos intervalos, {_lista(partes)}: pasa con las fracciones que valen "
            f"exactamente 0 o 1 y con las medianas y los cuartiles de cifras que se "
            f"repiten, donde muchas réplicas dan el mismo valor.")


def _del_lado(celdas, clave: str, debajo: bool) -> tuple:
    """Las celdas cuya pendiente de `clave` queda por debajo (o por encima) de
    1, las que de ellas llevan intervalo, y las que lo tienen ENTERO de ese
    lado."""
    ruta = f"modelos.{clave}.pendiente"

    def de_ese_lado(v) -> bool:
        return _a_la_vista(v, 2) < 1 if debajo else _a_la_vista(v, 2) > 1

    puntuales = [c for c in celdas if not _falta(c["modelos"][clave]["pendiente"])
                 and de_ese_lado(c["modelos"][clave]["pendiente"])]
    con_intervalo = [c for c in puntuales if _par(c, ruta) is not None]
    enteras = [c for c in con_intervalo if de_ese_lado(_par(c, ruta)[1 if debajo else 0])]
    return puntuales, con_intervalo, enteras


def _lectura_de_la_pendiente(celdas, clave: str, debajo: bool, esperada: str,
                             contraria: str, quiere_decir: dict) -> list:
    """Las frases de la pendiente de un modelo: primero el lado esperado y
    despues, si alguna celda cae en el, el contrario. La estimacion sola no
    decide: lo que la pendiente `quiere_decir` (por debajo de 1, True; por
    encima, False) se dice solo de las celdas con el intervalo ENTERO de ese
    lado."""
    ruta = f"modelos.{clave}.pendiente"
    lineas = []
    for lado, frase in ((debajo, esperada), (not debajo, contraria)):
        puntuales, con_intervalo, enteras = _del_lado(celdas, clave, lado)
        if lado != debajo and not puntuales:
            continue
        lineas.append(f"- {frase}: {len(puntuales)} de {len(celdas)}"
                      + _con_su_cifra(puntuales, ruta, 2) + ".")
        if con_intervalo:
            lineas.append(
                f"- De esas, con el intervalo entero por {'debajo' if lado else 'encima'} "
                f"de 1 ({quiere_decir[lado]}): {len(enteras)} de {len(con_intervalo)}"
                + (": " + _lista(c["nombre"] for c in enteras) if enteras else "") + ".")
    return lineas


def _lectura_de_las_pareadas(celdas) -> list:
    """Por combinacion y por metrica: en cuantas celdas el intervalo de la
    diferencia frente a la imagen sola queda entero del lado de la mejora,
    entero del contrario, o cruza el 0."""
    lineas = []
    for clave, nombre in COMBINADOS:
        for metrica, titulo, sube in (("auc", "ΔAUC", True), ("brier", "ΔBrier", False)):
            ruta = f"pareadas.{clave}.{metrica}"
            con_intervalo = [c for c in celdas if _par(c, ruta) is not None]
            if not con_intervalo:
                continue
            encima = [c for c in con_intervalo if _a_la_vista(_par(c, ruta)[0], 3) > 0]
            debajo = [c for c in con_intervalo if _a_la_vista(_par(c, ruta)[1], 3) < 0]
            cruzan = [c for c in con_intervalo if c not in encima and c not in debajo]
            mejoran, empeoran = (encima, debajo) if sube else (debajo, encima)
            lineas.append(
                f"- **Frente a la imagen sola: {titulo}, {nombre}.** Celdas destacadas con "
                f"intervalo: {len(con_intervalo)}. Con el intervalo entero del lado de la "
                f"mejora (por {'encima' if sube else 'debajo'} de 0): "
                f"{_nombradas(mejoran)}. Con el intervalo entero del lado contrario: "
                f"{_nombradas(empeoran)}. Con el 0 dentro del intervalo: "
                f"{_nombradas(cruzan)}.")
    return lineas


def _lectura_de_la_hipotesis(r: dict) -> str:
    """0A aparte. En las demas, las que llevan intervalo se leen por el; en
    las que no, se dice que solo hay estimacion puntual."""
    umbral = _umbral(r["parametros"]["hipotesis_contencion"])
    resto = [c for c in r["celdas"] if c["nombre"] != "0A"]
    clases = {clave: [] for clave in VEREDICTOS}
    for c in resto:
        clases[_veredicto(c)[0]].append(c)
    con_intervalo = clases["se_sostiene"] + clases["no_se_sostiene"] + clases["no_se_puede_decir"]
    sin_intervalo = clases["punto_si"] + clases["punto_no"]
    frases = [f"- **La hipótesis de la horquilla** (contención ≥ {umbral} % de los "
              f"concordantes)."]
    if _cero(r) is not None:
        frases.append("0A es la comprobación de la métrica y se cuenta aparte.")
    frases.append(f"Celdas con dependencia: {entero(len(resto))}; con intervalo, "
                  f"{entero(len(con_intervalo))}.")
    if con_intervalo:
        frases += [
            "Donde hay intervalo decide el intervalo entero.",
            f"Con dependencia y con intervalo, celdas en las que se sostiene: "
            f"{_nombradas(clases['se_sostiene'])}.",
            f"Con dependencia y con intervalo, celdas en las que no se sostiene: "
            f"{_nombradas(clases['no_se_sostiene'])}.",
            f"Con dependencia y con intervalo, celdas en las que no se puede decir, porque "
            f"la estimación y su intervalo no quedan enteros a un lado del umbral: "
            f"{_nombradas(clases['no_se_puede_decir'])}."]
    if sin_intervalo:
        frases.append(
            f"Sin intervalo, {entero(len(sin_intervalo))}: solo hay estimación puntual. "
            f"Sin intervalo, celdas en las que la estimación alcanza el umbral: "
            f"{_nombradas(clases['punto_si'])}.")
    if clases["sin_casos"]:
        frases.append(f"Celdas sin casos concordantes con horquilla: "
                      f"{_nombradas(clases['sin_casos'])}.")
    return " ".join(frases)


def _lectura(r: dict) -> list:
    lineas = [
        "## Lectura de los resultados",
        "",
        "Estas frases se componen contando sobre las cifras de las tablas: dicen lo que las "
        "cifras dicen, y nada más. Todo se refiere a la simulación. Las comparaciones con "
        "un umbral o con un valor de referencia se hacen con las cifras tal como se "
        "imprimen: «por encima» y «por debajo» son estrictos, y un umbral «≥» se alcanza "
        "también con la igualdad.",
        "",
    ]
    destacadas = _destacadas(r)
    cero = _cero(r)
    if cero is not None:
        lineas.append(
            f"- **0A.** La pendiente de la combinación por independencia es "
            f"{_pendiente_de_0a(cero)}. Horquilla: "
            f"{_colas(cero['horquilla']['todos'])}.")
    if not destacadas:
        lineas.append("- Esta corrida no tiene celdas destacadas.")
    else:
        independencia = _lectura_de_la_pendiente(
            destacadas, "independencia", True,
            "**La independencia.** Celdas destacadas en las que la estimación de la "
            "pendiente de la combinación por independencia es menor que 1",
            "En sentido contrario, la estimación de la pendiente de la combinación por "
            "independencia es mayor que 1",
            {True: "exagera", False: "se queda corta"})
        independencia[0] += " Una pendiente menor que 1 es la forma cuantitativa de «exagera»."
        lineas += independencia
        lineas += _lectura_de_la_pendiente(
            destacadas, "conservador", False,
            "**El extremo conservador.** Celdas destacadas en las que la estimación de su "
            "pendiente es mayor que 1",
            "En sentido contrario, la estimación de la pendiente del extremo conservador es "
            "menor que 1",
            {True: "también el extremo conservador exagera", False: "se queda corto"})
        lineas += _lectura_de_las_pareadas(destacadas)
    lineas.append(_lectura_de_la_hipotesis(r))
    fuera, cifras = _fuera_de_su_intervalo(r["celdas"])
    if cifras:
        if fuera == 0:
            cuenta = (f"no queda fuera de su intervalo ninguna de las {entero(cifras)} "
                      f"cifras que lo llevan")
        else:
            cuenta = (f"{'queda' if fuera == 1 else 'quedan'} fuera de su intervalo "
                      f"{entero(fuera)} de las {entero(cifras)} cifras que lo llevan")
        lineas.append(
            f"- **Los intervalos.** La estimación puntual usa la clínica sorteada con la "
            f"semilla {_semilla(r['parametros']['semilla_puntual'])} sobre todas las placas; "
            f"cada réplica remuestrea esos mismos casos, cada placa con su clínica. El "
            f"intervalo son los percentiles de las réplicas: en "
            f"esta corrida, de {entero(r['parametros']['replicas'])} réplicas, {cuenta} "
            f"(comparadas sin redondear).{_lo_del_borde(r['celdas'])} El "
            f"intervalo de la ECE está desplazado hacia "
            f"arriba por construcción: la ECE de un remuestreo suma el ruido del "
            f"remuestreo al de la muestra. Por eso la ECE se lee al lado de su suelo y "
            f"no contra su intervalo, que no se imprime. **Un intervalo recoge solo el "
            f"muestreo de los casos —la placa y su clínica— bajo este generador.** No "
            f"recoge la incertidumbre del calibrador ni la de los umbrales del "
            f"generador, que se ajustan una vez sobre estas mismas placas, ni la de las "
            f"RV publicadas, que se toman como exactas, ni la de ρ, que es el supuesto "
            f"de cada celda.")
    if destacadas:
        lineas += ["", "Hacia qué lado cae el oráculo, por eje y por lado de la imagen "
                       "(estimaciones puntuales):", ""]
        for eje in EJES:
            celdas = [c for c in destacadas if _eje(c) == eje]
            if not celdas:
                continue
            lineas.append(f"- **{eje}.**")
            for c in celdas:
                lineas.append(
                    f"  - {c['nombre']}: "
                    + "; ".join(f"{nombre} {_colas(c['horquilla'][lado])}"
                                for lado, nombre in LADOS_DE_LA_IMAGEN) + ".")
    return lineas + [""]


def _limites(r: dict) -> list:
    cero = _cero(r)
    if cero is None:
        corrida = ("Esta corrida no incluye la celda 0A: de los dos primeros puntos no dice "
                   "nada.")
    else:
        m = cero["modelos"]["independencia"]
        estado = {"cumple": "se cumple", "no_cumple": "**no se cumple**",
                  "sin_casos": "**no se puede comprobar**"}[_estado_de_0a(cero)]
        corrida = (
            f"En esta corrida, la fila 0A de la horquilla {estado}; la "
            f"pendiente de la combinación por independencia en 0A es "
            f"{_pendiente_de_0a(cero)}; y su ECE ({numero(m['ece'], 3)}) "
            f"{_frente_al_suelo(m['ece'], m['suelo'])}.")
    return [
        "## Lo que esta simulación puede afirmar y lo que no",
        "",
        "**Puede decir:**",
        "",
        f"- si el sistema reproduce caso a caso la posterior del generador (0A: lo "
        f"comprueban las pruebas de `{PRUEBA_0A}`; la fila 0A de la horquilla lo acompaña, "
        f"como control más débil y solo para los concordantes);",
        "- si, **cuando** la puntuación tiene la exactitud publicada y es condicionalmente "
        "independiente de la imagen, la aritmética y la calibración de la imagen dan una "
        "posterior calibrada en el conjunto de prueba de RSNA;",
        "- cuánto se desvía la independencia de la posterior del generador **bajo cada "
        "supuesto de dependencia**, en qué dirección, y dónde cae el oráculo respecto a la "
        "horquilla;",
        "- cuánto desplaza la calibración un previo equivocado.",
        "",
        corrida + " Lo demás se lee en «Lectura de los resultados» y, lo del previo, en "
                  "«Sensibilidad al previo».",
        "",
        "**No puede afirmar** exactitud clínica real ni cuánto aporta la clínica en "
        "pacientes: las viñetas no son pacientes, la exactitud es la publicada y la "
        "dependencia es la supuesta. Esta simulación no mide exactitud clínica.",
        "",
        "Aquí no se reentrena ni se recalibra el modelo de imagen, ni se ajustan las RV ni "
        "la prevalencia con estos datos. Solo se mide.",
        "",
    ]


def _titulo_de_figura(nombre: str, r: dict) -> str:
    rotulo = r["rotulo"]
    for clave, titulo in FIGURAS_GLOBALES:
        if nombre == clave:
            return f"{titulo} ({rotulo})"
    if nombre.startswith(PREFIJO_FIABILIDAD):
        for c in r["celdas"]:
            if nombre == PREFIJO_FIABILIDAD + slug_de_celda(c):
                return f"{TITULO_FIABILIDAD}, celda {c['nombre']} ({rotulo})"
    return f"{nombre} ({rotulo})"


def _figuras(r: dict, figuras: dict, ajenas=()) -> list:
    """`ajenas`: los nombres de las figuras enlazadas que NO llevan la huella
    de estos resultados. El documento lo dice de esas, y solo de esas."""
    lineas = ["## Figuras", ""]
    if not figuras:
        return lineas + ["Esta versión del documento se generó sin figuras.", ""]
    orden = [PREFIJO_FIABILIDAD + slug_de_celda(c) for c in r["celdas"]]
    orden += [clave for clave, _ in FIGURAS_GLOBALES]
    orden = [n for n in orden if n in figuras] + sorted(n for n in figuras if n not in orden)
    ajenas = [n for n in orden if n in set(ajenas)]
    lineas += ["El guion las dibuja leyendo el mismo fichero de resultados que este "
               "documento, y escribe en los metadatos de cada una la huella de los "
               "resultados de los que sale."]
    enlazadas, sin_huella = len(orden), len(ajenas)
    if not ajenas:
        lineas[-1] += (" La única figura enlazada lleva" if enlazadas == 1 else
                       f" Las {entero(enlazadas)} figuras enlazadas llevan")
        lineas[-1] += " la huella de los resultados de este documento."
    else:
        una = sin_huella == 1
        if enlazadas == 1:
            cuantas = "la única figura enlazada no lleva"
        elif sin_huella == enlazadas:
            cuantas = f"ninguna de las {entero(enlazadas)} figuras enlazadas lleva"
        else:
            cuantas = (f"{entero(sin_huella)} de las {entero(enlazadas)} figuras enlazadas "
                       f"no {'lleva' if una else 'llevan'}")
        lineas += ["", f"**Aviso: {cuantas} la huella de los resultados de este "
                       f"documento** ({_lista(f'`{n}`' for n in ajenas)}): "
                       f"{'es' if una else 'son'} de otra corrida, o no "
                       f"{'la' if una else 'las'} dibujó este guion. "
                       f"{'Se redibuja' if una else 'Se redibujan'} con "
                       f"`python {GUION} --solo-documento`."]
    lineas += [""]
    for nombre in orden:
        lineas += [f"![{_titulo_de_figura(nombre, r)}]({figuras[nombre]})", ""]
    return lineas


def _entorno(entorno: dict) -> str:
    """«`Python 3.13.1`, `NumPy 2.3.0` y …»: las versiones van entre acentos
    graves porque se copian tal cual (y llevan punto, no coma decimal)."""
    citadas = [f"`{nombre} {entorno[clave]}`" for clave, nombre in LIBRERIAS
               if clave in entorno]
    citadas += [f"`{clave} {entorno[clave]}`" for clave in sorted(entorno)
                if clave not in dict(LIBRERIAS)]
    return _lista(citadas)


def _reproducir(r: dict) -> list:
    i, p = r["insumos"], r["parametros"]
    return [
        "## Cómo se reproduce",
        "",
        "Desde la raíz del repositorio:",
        "",
        "```",
        f"python {GUION} --replicas {p['replicas']}",
        "```",
        "",
        f"La orden lee `{i['crudas']}` (una copia congelada de las puntuaciones crudas) y "
        f"`{i['calibrador']}`, y escribe `{RESULTADOS}`, las figuras y este documento. Se "
        f"reproduce **sin los pesos** del modelo, sin red y sin contenedores, y con las "
        f"semillas fijas que se citan arriba. Las figuras necesitan el extra "
        f"`figuras` del paquete; con `--sin-figuras` no se dibujan, y el documento "
        f"enlaza las que hubiera en la carpeta.",
        "",
        f"Estos resultados se calcularon con {_entorno(r['entorno'])}. Con otras "
        f"versiones las cifras pueden no ser las mismas: NumPy no garantiza el mismo "
        f"flujo de números aleatorios de una versión a otra.",
        "",
        "Para regenerar las figuras y el documento sin recalcular:",
        "",
        "```",
        f"python {GUION} --solo-documento",
        "```",
        "",
    ]


def redactar(resultados: dict, figuras: dict | None = None, ajenas=()) -> str:
    """El documento de analisis, en Markdown.

    `figuras` es {nombre sin extension: enlace relativo desde el documento};
    las figuras que no esten en el diccionario no se enlazan. `ajenas` son
    los nombres de las enlazadas que no llevan la huella de `resultados`:
    lo sabe quien llama, que es quien puede abrir los PNG."""
    r = resultados
    lineas = (_cabecera(r) + _insumos(r) + _imagen_sola(r) + _escenario_0a(r)
              + _dependencia(r) + _horquilla(r) + _escala_legible(r) + _rejilla(r)
              + _sensibilidad(r) + _optimismo(r) + _lectura(r) + _limites(r)
              + _figuras(r, dict(figuras or {}), ajenas) + _reproducir(r))
    return "\n".join(lineas).rstrip("\n") + "\n"
