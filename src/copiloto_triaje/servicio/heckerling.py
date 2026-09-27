"""La regla de Heckerling y la combinacion bayesiana con la imagen (SP4).

    Heckerling PS, Tape TG, Wigton RS, Hissong KK, Leikin JB, Ornato JP, et al.
    Clinical prediction rule for pulmonary infiltrates.
    Ann Intern Med. 1990;113(9):664-70.

Las razones de verosimilitud (RV) por puntuacion son las del conjunto de
DERIVACION (Illinois), tal como las reproduce la revision sistematica con
metaanalisis PMC7422644 (tabla 2). No se pudo leer el articulo primario
-PubMed contesta con un CAPTCHA y Annals es de pago-, asi que la fuente es esa
revision, y se dice. Las RV se verificaron contra los recuentos de la tabla
antes de escribirlas aqui, y `tests/test_heckerling.py` lo vuelve a hacer en
cada corrida.

La aritmetica es la MISMA que `calibracion.py` usa para la imagen, al reves:

    odds_previas     = prevalencia / (1 - prevalencia)
    odds_posteriores = odds_previas x RV_clinica x RV_imagen
    posterior        = odds_posteriores / (1 + odds_posteriores)

Multiplicar dos RV asume que son condicionalmente independientes, y aqui eso
es discutible: los crepitantes y la opacidad son el mismo fenomeno visto de
dos maneras. No se corrige con un factor inventado; se ACOTA (spec §7): la
posterior bajo independencia y la posterior con solo la RV mas informativa
son los dos extremos calculables, y el informe entrega los dos.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

# Los cinco predictores de la regla, con el nombre del dato que los bots ya
# recogen (spec §2). El asma entra al reves: puntua su AUSENCIA.
PUNTOS = ("temperatura_c", "frecuencia_cardiaca", "crepitantes",
          "murmullo_disminuido", "asma")

# Los dos cortes, ESTRICTOS: 37,8 exactos no puntuan y 100 exactos no puntuan
# (spec §11.2). Un corte mal puesto mueve la puntuacion entera, y ninguna
# prueba de redondeo lo cazaria.
TEMPERATURA_CORTE_C = 37.8
PULSO_CORTE_LPM = 100

ESTADOS_ASMA = ("si", "no", "no_se")

# RV de la derivacion (spec §4). Cada una es (con neumonia / 134) / (sin / 780)
# con las celdas de la tabla 2 de PMC7422644; la prueba las recalcula.
RV_POR_PUNTUACION = {0: 0.12, 1: 0.20, 2: 0.70, 3: 1.64, 4: 7.18, 5: 17.5}

# La prevalencia de la propia cohorte de derivacion: 134 de 914 (spec §5). Es
# el valor con el que ARRANCA `PREVALENCIA_LOCAL`; el servidor la lee del
# entorno (servidor/arrancar.py), no de aqui.
PREVALENCIA_COHORTE = 134 / 914


class HallazgosInvalidos(ValueError):
    """Unos hallazgos con los que no se puede puntuar. El mensaje lo lee una
    persona -acaba en `consultas.error`-, asi que va bien escrito."""


def _corto(x) -> str:
    """Lo que el llamante mando, acotado a 40 caracteres para el mensaje de
    error. El texto viaja por MCP como `Error executing tool ...:
    hallazgos_invalidos: ...` y acaba en `consultas.error`: sin tope, una
    clave o un valor ajeno de cualquier longitud se copiaba entero en el. El
    corte se marca con «…»: un `10**400` recortado a secas se leeria como
    otro numero."""
    texto = repr(x)
    return texto if len(texto) <= 40 else texto[:39] + "…"


def _finito(v) -> float | None:
    """`v` como `float` finito, o `None`. Ni `bool` -es subclase de `int`: un
    `True` colaria como un grado- ni cadenas. Un `int` de Python enorme
    (`10**400`) no desborda al construirlo pero si al convertirlo a `float`:
    se convierte dentro del `try` para que no escape un `OverflowError`."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        numero = float(v)
    except OverflowError:
        return None
    return numero if math.isfinite(numero) else None


def _numero(hallazgos: Mapping, clave: str) -> float:
    v = hallazgos.get(clave)
    numero = _finito(v)
    if numero is not None:
        return numero
    raise HallazgosInvalidos(
        f"«{clave}» debe ser un número finito, y es {_corto(v)}.")


def _booleano(hallazgos: Mapping, clave: str) -> bool:
    v = hallazgos.get(clave)
    # Solo `True`/`False`: la cadena "false" es cierta en cualquier lenguaje, y
    # un 0/1 no dice si alguien auscultó o tecleó.
    if not isinstance(v, bool):
        raise HallazgosInvalidos(
            f"«{clave}» debe ser verdadero o falso, y es {_corto(v)}.")
    return v


def _rv_positiva(nombre: str, v) -> float:
    """Una RV como `float` finito y positivo, o `ValueError`. La misma
    conversion que `_numero`: una cadena daba `TypeError` desde
    `math.isfinite` y un `10**400`, `OverflowError`; ahora las dos son el
    mismo `ValueError` que un cero o un `nan`."""
    rv = _finito(v)
    if rv is not None and rv > 0:
        return rv
    raise ValueError(
        f"{nombre} debe ser un número positivo y finito, y es {_corto(v)}")


def validar_hallazgos(hallazgos) -> dict:
    """Los cinco hallazgos con su tipo, o `HallazgosInvalidos`.

    Estricta en las claves: ni una de menos -no se puntúa con cuatro- ni una
    de más -una clave desconocida es un error de quien llama, no un dato que
    ignorar-. No comprueba rangos clinicos: eso lo hace `Decidir` (§4.4 de
    SP3) antes de guardar el signo.
    """
    if not isinstance(hallazgos, Mapping):
        raise HallazgosInvalidos(
            "los hallazgos deben ser un objeto con cinco campos: "
            + ", ".join(PUNTOS) + ".")
    faltan = [k for k in PUNTOS if k not in hallazgos]
    sobran = [k for k in hallazgos if k not in PUNTOS]
    if faltan or sobran:
        raise HallazgosInvalidos(
            f"hallazgos incompletos o con campos de más: faltan "
            f"{_corto(faltan)}, sobran {_corto(sobran)}.")
    asma = hallazgos["asma"]
    if asma not in ESTADOS_ASMA:
        raise HallazgosInvalidos(
            f"«asma» debe ser uno de {list(ESTADOS_ASMA)}, y es {_corto(asma)}.")
    return {
        "temperatura_c": _numero(hallazgos, "temperatura_c"),
        "frecuencia_cardiaca": _numero(hallazgos, "frecuencia_cardiaca"),
        "crepitantes": _booleano(hallazgos, "crepitantes"),
        "murmullo_disminuido": _booleano(hallazgos, "murmullo_disminuido"),
        "asma": asma,
    }


def puntuar(signos: Mapping, asma: str) -> tuple[int, ...]:
    """La puntuacion de Heckerling: una, o DOS si el asma no se sabe.

    `signos` son los cuatro del profesional (temperatura_c,
    frecuencia_cardiaca, crepitantes, murmullo_disminuido); `asma` es uno de
    `ESTADOS_ASMA`. Devuelve siempre una tupla: `(3,)`, o con `no_se`
    `(con_asma, sin_asma)`, que difieren exactamente en uno. No se elige por
    el clinico: se le dan las dos (spec §6).
    """
    if not isinstance(signos, Mapping):
        raise HallazgosInvalidos("los signos deben ser un objeto con los "
                                 "cuatro datos de la exploración.")
    return _puntuar_validados(validar_hallazgos(
        {k: signos.get(k) for k in PUNTOS if k != "asma"} | {"asma": asma}))


def _puntuar_validados(h: Mapping) -> tuple[int, ...]:
    """La aritmetica de `puntuar` sobre unos hallazgos YA validados (los cinco,
    con su tipo). `combinacion` la llama con los que acaba de validar, para
    no pasarlos otra vez por `validar_hallazgos`."""
    base = (int(h["temperatura_c"] > TEMPERATURA_CORTE_C)
            + int(h["frecuencia_cardiaca"] > PULSO_CORTE_LPM)
            + int(h["crepitantes"])
            + int(h["murmullo_disminuido"]))
    if h["asma"] == "no_se":
        return (base, base + 1)
    return (base + (1 if h["asma"] == "no" else 0),)


def combinar(prevalencia: float, rv_clinica: float, rv_imagen: float) -> float:
    """Probabilidad posterior: odds previas por las dos RV, y de vuelta.

    No acota: las RV ya llegan acotadas -la de la imagen por la curva del
    calibrador, la clinica por la tabla- y con una prevalencia en (0, 1) el
    resultado no puede ser 0 ni 1.
    """
    if not 0.0 < prevalencia < 1.0:
        raise ValueError(
            f"la prevalencia debe estar entre 0 y 1, y es {prevalencia!r}")
    # El guardia viejo (`rv <= 0`) deja pasar `nan` -toda comparacion con
    # `nan` es falsa- e `inf`, y la posterior sale `nan`. Exige finita y
    # positiva en las dos RV, y lo que no lo es -tambien una cadena o un
    # entero que desborda- es siempre `ValueError`.
    rv_clinica = _rv_positiva("rv_clinica", rv_clinica)
    rv_imagen = _rv_positiva("rv_imagen", rv_imagen)
    odds = prevalencia / (1.0 - prevalencia) * rv_clinica * rv_imagen
    return odds / (1.0 + odds)


def mas_informativa(rv_a: float, rv_b: float) -> float:
    """La RV que mas mueve las odds: la de mayor |ln|. Es la «dependencia
    total» del spec §7.1: la otra no anade nada. En empate exacto, la
    primera."""
    return rv_a if abs(math.log(rv_a)) >= abs(math.log(rv_b)) else rv_b


def combinacion(prevalencia: float, hallazgos: Mapping, rv_imagen: float) -> dict:
    """El bloque `combinacion` del contrato (spec §9.2), listo para viajar.

    Para cada puntuacion posible -una, o dos si el asma no se sabe- calcula la
    posterior bajo INDEPENDENCIA (producto de las dos RV) y, solo si todas
    las RV clinicas estan del mismo lado de 1 que la de la imagen, bajo
    DEPENDENCIA TOTAL (la mas informativa sola, spec §7.1-7.2). `minima` y
    `maxima` son el minimo y el maximo de todo eso: la horquilla que
    `Desenlace` imprime. Nunca se anidan dos rangos: se funden aqui.

    `absorbe` dice quien es la mas informativa cuando hay concordancia, para
    que el aviso del informe nombre a quien absorbe a quien sin mentir:
    «la auscultacion no anade nada sobre la imagen» solo es cierto si la
    imagen es la que manda.
    """
    h = validar_hallazgos(hallazgos)
    rv_imagen = _rv_positiva("rv_imagen", rv_imagen)
    puntuaciones = _puntuar_validados(h)
    rv_clinica = [RV_POR_PUNTUACION[p] for p in puntuaciones]
    # 1,0 exacto cuenta como «a favor»: con una clinica por debajo de 1 el
    # bloque saldria discordante, y el aviso diria «sentidos opuestos» de una
    # imagen que no apunta a ningun lado. Con el calibrador desplegado (modelo
    # en float32, curva sin tramo plano en su prevalencia) no puede pasar: la
    # revision final recorrio todas las crudas float32 del unico tramo que
    # cruza la prevalencia y ninguna da RV == 1,0. Si un recalibrado tuviera
    # un tramo plano justo en la prevalencia, habria que decidir el empate.
    a_favor = rv_imagen >= 1.0
    concordantes = all((rv >= 1.0) == a_favor for rv in rv_clinica)
    independencia = [combinar(prevalencia, rv, rv_imagen) for rv in rv_clinica]
    dependencia = None
    absorbe = None
    if concordantes:
        informativas = [mas_informativa(rv, rv_imagen) for rv in rv_clinica]
        dependencia = [combinar(prevalencia, m, 1.0) for m in informativas]
        quien = {"imagen" if m == rv_imagen else "clinica"
                 for m in informativas}
        absorbe = quien.pop() if len(quien) == 1 else "mixta"
    todas = independencia + (dependencia or [])
    return {
        "prevalencia": float(prevalencia),
        "puntuacion": list(puntuaciones),
        "rv_clinica": rv_clinica,
        "rv_imagen": float(rv_imagen),
        "concordantes": concordantes,
        "absorbe": absorbe,
        "independencia": [round(x, 4) for x in independencia],
        "dependencia": (None if dependencia is None
                        else [round(x, 4) for x in dependencia]),
        "minima": round(min(todas), 4),
        "maxima": round(max(todas), 4),
    }
