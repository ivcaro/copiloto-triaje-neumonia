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
# Los nombres de las figuras son los que les pone el script (tarea 5).
PREFIJO_FIABILIDAD = "fiabilidad_"
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


def _tabla(cabeceras, filas, izquierdas: int = 1) -> list:
    """Una tabla de Markdown: las primeras columnas a la izquierda, las
    cifras a la derecha."""
    guia = [":---" if i < izquierdas else "---:" for i in range(len(cabeceras))]
    lineas = ["| " + " | ".join(cabeceras) + " |", "| " + " | ".join(guia) + " |"]
    lineas += ["| " + " | ".join(str(c) for c in fila) + " |" for fila in filas]
    return lineas + [""]


def _lista(nombres) -> str:
    """«a, b y c»."""
    nombres = list(nombres)
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _transiciones(bandas: dict) -> str:
    if not bandas["transiciones"]:
        return "ninguna"
    return "; ".join(f"{sentido}: {entero(n)}" for sentido, n in bandas["transiciones"].items())


def _slug(celda: dict) -> str:
    """El de `slug_de_celda` del script: `0a`, `r1-030_r0-000`."""
    if celda["nombre"] == "0A":
        return "0a"
    return f"r1-{round(celda['rho1'] * 100):03d}_r0-{round(celda['rho0'] * 100):03d}"


def _frente_al_suelo(ece, suelo: dict) -> str:
    """La ECE solo se lee al lado de su suelo de ruido."""
    if _falta(ece) or _falta(suelo["p95"]):
        return "no se puede comparar con su suelo"
    if ece <= suelo["p95"]:
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


def _completas(resultados: dict) -> list:
    """0A y las destacadas, en el orden de la rejilla."""
    return [c for c in resultados["celdas"] if c["nombre"] == "0A" or c["destacada"]]


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
                f"réplica remuestrea las placas con reemplazo (una placa por paciente, así "
                f"que es un bootstrap por paciente) y vuelve a sortear la clínica. El "
                f"generador queda fijo en todas. Intervalos del 95 % por percentiles; las "
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
        f"{numero(i['prevalencia'], 4)}), nunca usadas para entrenar ni calibrar, con su "
        f"etiqueta real de opacidad. Es un desenlace análogo al de Heckerling (infiltrado "
        f"radiográfico) en una población distinta: RSNA no es una cohorte con sospecha de "
        f"neumonía.",
        "- **Clínica:** a cada placa se le sortea la puntuación de Heckerling dada su "
        "etiqueta, con las frecuencias publicadas de la cohorte de derivación. No se "
        "inventa la exactitud de la regla: se usa la publicada, tal como la usa el sistema.",
        "- **Dependencia:** la estructura de dependencia entre clínica e imagen es un "
        "supuesto: nula en 0A y barrida en el resto de la rejilla.",
        "- **Transporte:** el generador supone que la distribución de la puntuación por "
        "clase, medida en la cohorte de derivación, se transporta al espectro de RSNA. Eso "
        "no se comprueba ni se puede comprobar aquí.",
        "",
        "Con qué se calculó:",
        "",
        f"- Puntuaciones crudas del modelo desplegado: `{i['crudas']}` "
        f"(sha256 `{huella(i['crudas_sha256'])}…`), generadas con los pesos de sha256 "
        f"`{huella(i['pesos_sha256'])}…`.",
        f"- Calibrador: `{i['calibrador']}` (sha256 `{huella(i['calibrador_sha256'])}…`).",
        f"- Previo del análisis principal: {numero(i['prevalencia'], 4)}, la prevalencia de "
        f"la población simulada. El previo desplegado, "
        f"{numero(p['previo_desplegado'], 4)}, solo entra en la sensibilidad al previo.",
        f"- Rejilla: ρ1 y ρ0 toman los valores {' / '.join(rho(x) for x in p['rejilla'])}: "
        f"{entero(len(r['celdas']))} celdas. El origen es 0A y se cuenta aparte; "
        + (f"celdas destacadas: {_lista(destacadas)}." if destacadas
           else "esta corrida no tiene celdas destacadas."),
        f"- Bootstrap: {replicas}.",
        f"- Semillas: clínica de la estimación puntual, {entero(p['semilla_puntual'])}; "
        f"clínica de la réplica b, {entero(p['semilla_clinica'])} + b; placas de la réplica "
        f"b, {entero(p['semilla_indices'])} + b.",
        f"- Tolerancia de las colas de la horquilla: ε = {numero(p['epsilon'], 3)} log-odds, "
        f"el redondeo máximo de las RV publicadas (la misma tolerancia de la comprobación "
        f"0A).",
        f"- ECE: {entero(p['bins'])} tramos de igual masa, con los empates rotos por el orden "
        f"del identificador de la placa. Su suelo de ruido: "
        f"{entero(p['repeticiones_suelo'])} juegos de etiquetas simuladas con las "
        f"probabilidades del propio modelo (semilla {entero(p['semilla_suelo'])}); se "
        f"publican la media y el percentil 95.",
        f"- Hipótesis de la horquilla: contención ≥ "
        f"{numero(100.0 * p['hipotesis_contencion'], 0)} % de los concordantes.",
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
    cifras = [(_cifra(celda, f"modelos.{clave}.{metrica}", decimales) if con_intervalos
               else numero(m[metrica], decimales))
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
        "Lo que 0A demuestra es que el sistema calcula lo que dice calcular; no que la "
        "posterior sea exacta en pacientes.",
        "",
    ]
    cero = _cero(r)
    if cero is None:
        return lineas + ["Esta corrida no incluye la celda 0A.", ""]
    n = cero["recuentos"]
    h = cero["horquilla"]["todos"]
    limpia = h["bajo"] == 0 and h["sobre"] == 0 and h["contencion"] == 1
    lineas += [
        f"Los cuatro modelos puntuales en 0A, sobre los {entero(n['asma_conocida'])} casos "
        f"con el asma conocida:",
        "",
        *_tabla(["modelo"] + [titulo for _, titulo, _ in METRICAS]
                + ["suelo de la ECE (media)", "suelo de la ECE (p95)"],
                [[nombre] + _fila_de_modelo(cero, clave, True) for clave, nombre in MODELOS]),
        f"La ECE de la combinación por independencia "
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
        ("Se cumple: la métrica de la horquilla mide lo que tiene que medir." if limpia else
         "**NO se cumple: la métrica de la horquilla o el generador tienen un defecto, y las "
         "tablas de la horquilla de este documento no se pueden leer hasta corregirlo.**"),
        "",
    ]
    return lineas


def _dependencia(r: dict) -> list:
    p = r["parametros"]
    celdas = _completas(r)
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
        "casos con neumonía, entre lo que la puntuación mide y lo que la imagen mide; "
        "**ρ0**, la misma entre los casos sin neumonía. Temperatura, pulso y asma diluyen "
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
        *_tabla(["celda", "ρ1", "ρ0", "correlación con neumonía", "correlación sin neumonía"],
                [[c["nombre"], rho(c["rho1"]), rho(c["rho0"]),
                  numero(c["correlacion_teorica"]["con_neumonia"], 3),
                  numero(c["correlacion_teorica"]["sin_neumonia"], 3)] for c in celdas]),
        "Los cuatro modelos puntuales por celda (casos con el asma conocida). La pendiente "
        "lleva su intervalo; la ECE va al lado de su suelo:",
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
    umbral = numero(100.0 * p["hipotesis_contencion"], 0)
    celdas = _completas(r)
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
        f"escrita antes de correr nada, era que solo se sostuviera en 0A y en las celdas más "
        f"suaves. Una contención baja es un resultado igual de publicable, y obliga a "
        f"repensar la cota, no a ocultarla.",
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
               "El veredicto, celda a celda, sobre todos los concordantes:", ""]
    lineas += _tabla(
        ["celda", "contención", "umbral", "veredicto"],
        [[c["nombre"], _fraccion(c, "horquilla.todos.contencion"),
          f"≥ {numero(100.0 * c['hipotesis']['umbral'], 0)} %",
          "se sostiene" if c["hipotesis"]["se_sostiene"] else "no se sostiene"]
         for c in r["celdas"]])
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
               "misma ε, y el error del punto medio del rango en log-odds:", ""]
    lineas += _tabla(
        ["celda", "n", "por debajo del rango", "por encima del rango", "dentro",
         "punto medio: error absoluto mediano", "punto medio: sesgo mediano"],
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
        lineas += ["En 0A la fracción mediana de las puntuaciones extremas (k ≤ 1 y k ≥ 4) es "
                   + _lista([f"{numero(cero['escala_legible'][lado]['fraccion_mediana_extremas'], 2)} "
                             f"{nombre}" for lado, nombre in LADOS_DE_LA_IMAGEN])
                   + ": sin dependencia la puntuación conserva toda su evidencia.", ""]
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
                [[str(f["k"]), numero(f["ln_rv_recuentos"], 2, signo=True),
                  numero(f["casos_esperados"], 1), _cuartiles(f["log_rv"]),
                  _cuartiles(f["fraccion"]), porcentaje(f["signo_invertido"]),
                  "poco informativa" if f["poco_informativa"] else ""]
                 for f in e["por_puntuacion"]])
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
        f"El análisis principal usa {principal}, la prevalencia de la población simulada; el "
        f"sistema desplegado arranca con {previo}. Declarar {previo} en una población de "
        f"{principal} tiene un efecto analítico: todas las odds posteriores se multiplican "
        f"por {numero(math.exp(d), 3)}, es decir, se desplazan {numero(d, 2, signo=True)} en "
        f"log-odds por igual. El intercepto de calibración debe moverse, por tanto, en "
        f"torno a {numero(-d, 2, signo=True)} respecto del principal.",
        "",
        "**El AUC no cambia** (un desplazamiento común no altera el orden de los casos) y "
        "no se reporta en esta tabla. **Esto no recomienda configurar el despliegue con "
        f"{principal}:** es la prevalencia del conjunto de datos de un reto, no la de ningún "
        "servicio.",
        "",
        f"Con el previo {previo} (casos con el asma conocida); «principal» es la misma cifra "
        f"con {principal}. Las bandas son < 20 %, 20-70 % y > 70 %:",
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
                      "en qué sentido"], filas, izquierdas=2)
    lineas += ["La categoría que el sistema imprime (todos los casos, también los del asma "
               "desconocida):", ""]
    lineas += _tabla(
        ["celda", "cambian de categoría", "en qué sentido"],
        [[c["nombre"],
          f"{entero(c['sensibilidad_al_previo']['categoria_del_sistema']['cambian'])} de "
          f"{entero(c['sensibilidad_al_previo']['categoria_del_sistema']['casos'])}",
          _transiciones(c["sensibilidad_al_previo"]["categoria_del_sistema"])]
         for c in celdas])
    return lineas


def _optimismo(r: dict) -> list:
    lineas = ["## 0C: optimismo de la derivación (cálculo, no experimento)", ""]
    cero = _cero(r)
    if cero is None or "optimismo_de_la_derivacion" not in cero:
        return lineas + ["Esta corrida no calculó 0C.", ""]
    o = cero["optimismo_de_la_derivacion"]
    mas, menos = [], []
    for f in o["por_puntuacion"]:
        extrema = abs(math.log(f["rv_derivacion"])) > abs(math.log(f["rv_validacion"]))
        (mas if extrema else menos).append(str(f["k"]))
    reparto = []
    if mas:
        reparto.append(f"más extrema que la de validación en k = {_lista(mas)}")
    if menos:
        reparto.append(f"menos extrema en k = {_lista(menos)}")
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
        + (" El «optimismo» de la derivación no es uniforme." if mas and menos else ""),
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
        return "no hay casos"
    if bajo == 0 and sobre == 0:
        return f"{dentro}; ninguna cola tiene casos"
    if bajo == sobre:
        return f"{dentro}; las dos colas pesan lo mismo ({porcentaje(bajo)} cada una)"
    if sobre > bajo:
        return (f"{dentro}; la cola mayor es la de más allá de la independencia "
                f"({porcentaje(sobre)}, frente a {porcentaje(bajo)} por el lado conservador)")
    return (f"{dentro}; la cola mayor es la del lado conservador ({porcentaje(bajo)}, frente "
            f"a {porcentaje(sobre)} más allá de la independencia)")


EJES = ("Dependencia simétrica (ρ1 = ρ0)",
        "Dependencia solo entre los casos con neumonía (ρ0 = 0)",
        "Dependencia solo entre los casos sin neumonía (ρ1 = 0)",
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
    """(cuantas cifras con intervalo quedan fuera de el, cuantas hay)."""
    fuera = total = 0
    for celda in celdas:
        for ruta, par in (celda.get("intervalos") or {}).items():
            valor = _valor(celda, ruta)
            if _falta(valor) or _falta(par[0]) or _falta(par[1]):
                continue
            total += 1
            fuera += valor < par[0] - 1e-9 or valor > par[1] + 1e-9
    return fuera, total


def _lectura(r: dict) -> list:
    lineas = [
        "## Lectura de los resultados",
        "",
        "Estas frases se componen contando sobre las cifras de las tablas: dicen lo que las "
        "cifras dicen, y nada más. Todo se refiere a la simulación.",
        "",
    ]
    destacadas = _destacadas(r)
    total = len(destacadas)
    cero = _cero(r)
    if cero is not None:
        par = (cero.get("intervalos") or {}).get("modelos.independencia.pendiente")
        lineas.append(
            f"- **0A.** La pendiente de la combinación por independencia es "
            f"{_cifra(cero, 'modelos.independencia.pendiente', 2)}"
            + ("" if not par or _falta(par[0]) or _falta(par[1]) else
               ("; su intervalo contiene el 1" if par[0] <= 1 <= par[1]
                else "; su intervalo no contiene el 1"))
            + f". En la horquilla, {_colas(cero['horquilla']['todos'])}.")
    if not destacadas:
        lineas.append("- Esta corrida no tiene celdas destacadas.")
    else:
        debajo = [c for c in destacadas
                  if not _falta(c["modelos"]["independencia"]["pendiente"])
                  and c["modelos"]["independencia"]["pendiente"] < 1]
        lineas.append(
            f"- **La independencia.** Celdas destacadas en las que la pendiente de la "
            f"combinación por independencia es menor que 1: {len(debajo)} de {total}"
            + (" (" + "; ".join(
                f"{c['nombre']}: {_cifra(c, 'modelos.independencia.pendiente', 2)}"
                for c in debajo) + ")" if debajo else "")
            + ". Una pendiente menor que 1 es la forma cuantitativa de «exagera».")
        con_intervalo = [c for c in debajo
                         if (c.get("intervalos") or {}).get("modelos.independencia.pendiente")]
        if con_intervalo:
            enteros = [c for c in con_intervalo
                       if c["intervalos"]["modelos.independencia.pendiente"][1] < 1]
            lineas.append(
                f"- De esas, con el intervalo entero por debajo de 1: {len(enteros)} de "
                f"{len(con_intervalo)}"
                + (f" ({_lista(c['nombre'] for c in enteros)})" if enteros else "") + ".")
        encima = [c for c in destacadas
                  if not _falta(c["modelos"]["conservador"]["pendiente"])
                  and c["modelos"]["conservador"]["pendiente"] > 1]
        lineas.append(
            f"- **El extremo conservador.** Celdas destacadas en las que su pendiente es "
            f"mayor que 1 (se queda corto): {len(encima)} de {total}"
            + (" (" + "; ".join(
                f"{c['nombre']}: {_cifra(c, 'modelos.conservador.pendiente', 2)}"
                for c in encima) + ")" if encima else "") + ".")
        mejoran = [c for c in destacadas
                   if (c.get("intervalos") or {}).get("pareadas.independencia.auc")
                   and c["intervalos"]["pareadas.independencia.auc"][0] > 0]
        if any((c.get("intervalos") or {}).get("pareadas.independencia.auc")
               for c in destacadas):
            lineas.append(
                f"- **Discriminación.** Celdas destacadas en las que el intervalo de la "
                f"diferencia de AUC entre la independencia y la imagen sola queda entero por "
                f"encima de 0: {len(mejoran)} de {total}"
                + (f" ({_lista(c['nombre'] for c in mejoran)})" if mejoran else "") + ".")
    sostienen = [c["nombre"] for c in r["celdas"] if c["hipotesis"]["se_sostiene"]]
    rejilla = len(r["celdas"])
    lineas.append(
        "- **La hipótesis de la horquilla.** "
        + (f"Se sostiene en {len(sostienen)} de las {rejilla} celdas de la rejilla: "
           f"{_lista(sostienen)}." if sostienen else
           f"No se sostiene en ninguna de las {rejilla} celdas de la rejilla."))
    fuera, cifras = _fuera_de_su_intervalo(r["celdas"])
    if cifras:
        lineas.append(
            f"- **Los intervalos.** La estimación puntual usa la clínica sorteada con la "
            f"semilla {entero(r['parametros']['semilla_puntual'])} sobre todas las placas; "
            f"cada réplica remuestrea las placas y sortea otra clínica. El intervalo son los "
            f"percentiles de las réplicas y no está centrado en la estimación puntual: en "
            f"esta corrida, de {entero(r['parametros']['replicas'])} réplicas, quedan fuera "
            f"de su intervalo {entero(fuera)} de las {entero(cifras)} cifras que lo "
            f"llevan.")
    if destacadas:
        lineas += ["", "Hacia qué lado cae el oráculo, por eje y por lado de la imagen:", ""]
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
    return [
        "## Lo que esta simulación puede afirmar y lo que no",
        "",
        "**Puede afirmar:**",
        "",
        "- que el sistema reproduce caso a caso la posterior del generador (0A);",
        "- que, **si** la puntuación tiene la exactitud publicada y es condicionalmente "
        "independiente de la imagen, la aritmética y la calibración de la imagen dan una "
        "posterior calibrada en el conjunto de prueba de RSNA;",
        "- cuánto se desvía la independencia de la posterior del generador **bajo cada "
        "supuesto de dependencia**, en qué dirección, y dónde cae el oráculo respecto a la "
        "horquilla;",
        "- cuánto desplaza la calibración un previo equivocado.",
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
            if nombre == PREFIJO_FIABILIDAD + _slug(c):
                return f"Fiabilidad por deciles, celda {c['nombre']} ({rotulo})"
    return f"{nombre} ({rotulo})"


def _figuras(r: dict, figuras: dict) -> list:
    lineas = ["## Figuras", ""]
    if not figuras:
        return lineas + ["Esta versión del documento se generó sin figuras.", ""]
    orden = [PREFIJO_FIABILIDAD + _slug(c) for c in r["celdas"]]
    orden += [clave for clave, _ in FIGURAS_GLOBALES]
    orden = [n for n in orden if n in figuras] + sorted(n for n in figuras if n not in orden)
    lineas += ["El guion las dibuja leyendo el mismo fichero de resultados que este "
               "documento. Con `--sin-figuras` no se redibujan: se enlazan las que ya "
               "hubiera en la carpeta.", ""]
    for nombre in orden:
        lineas += [f"![{_titulo_de_figura(nombre, r)}]({figuras[nombre]})", ""]
    return lineas


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
        f"`figuras` del paquete; con `--sin-figuras` no se dibujan.",
        "",
        "Para regenerar las figuras y el documento sin recalcular:",
        "",
        "```",
        f"python {GUION} --solo-documento",
        "```",
        "",
    ]


def redactar(resultados: dict, figuras: dict | None = None) -> str:
    """El documento de analisis, en Markdown.

    `figuras` es {nombre sin extension: enlace relativo desde el documento};
    las figuras que no esten en el diccionario no se enlazan."""
    r = resultados
    lineas = (_cabecera(r) + _insumos(r) + _imagen_sola(r) + _escenario_0a(r)
              + _dependencia(r) + _horquilla(r) + _escala_legible(r) + _rejilla(r)
              + _sensibilidad(r) + _optimismo(r) + _lectura(r) + _limites(r)
              + _figuras(r, dict(figuras or {})) + _reproducir(r))
    return "\n".join(lineas).rstrip("\n") + "\n"
