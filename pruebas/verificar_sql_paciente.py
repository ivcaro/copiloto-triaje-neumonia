# -*- coding: utf-8 -*-
"""Conduce el SQL REAL del flujo del paciente contra una PostgreSQL desechable.

No sustituye a las pruebas conducidas de `tests/test_flujo_paciente.py`: no
prueba el grafo de n8n. Prueba lo que no se puede afirmar sin ejecutarlo: que
las cinco consultas son validas, que las CTE que modifican datos se comportan
como uno cree, y que las respuestas acaban cada una en SU clave.

**Imita al nodo Postgres de n8n donde importa.** El parametro
`options.queryReplacement` es UNA cadena con expresiones; n8n la resuelve y la
pasa por `stringToArray`, que parte por comas, recorta cada trozo **y descarta
los vacios**. Esa ultima parte costo un fallo bloqueante: el «Omitir» de la
pregunta 7 mandaba cadena vacia para decir NULL, el parametro desaparecia, y la
consulta salia con 4 parametros referenciando `$5` -> `there is no parameter
$5`. El paciente no recibia nada. Por eso este arnes resuelve los parametros
igual que n8n en vez de pasarlos a mano: un arnes que no imita esa regla no ve
el fallo.

Uso (hace falta Docker):

    docker run -d --name sp3-verifica-sql -e POSTGRES_PASSWORD=verifica \\
        -e POSTGRES_DB=copiloto -p 15499:5432 postgres:16-alpine
    docker exec -i sp3-verifica-sql psql -U postgres -d copiloto < bd/esquema.sql
    C:/venv-copiloto/Scripts/python.exe pruebas/verificar_sql_paciente.py
    docker rm -f sp3-verifica-sql

La tarea 6 necesitara el equivalente para `sesiones_profesional` y `consultas`.
"""
import base64
import json
import pathlib
import re
import sys
import threading

import psycopg

DSN = "host=127.0.0.1 port=15499 dbname=copiloto user=postgres password=verifica"
CHAT = 999000001
REPO = pathlib.Path(__file__).resolve().parents[1]
FLUJO = json.loads((REPO / "n8n" / "copiloto-paciente.json").read_text(encoding="utf-8"))

NODOS = {n["name"]: n for n in FLUJO["nodes"]}
PREGUNTAS = [(int(n), c) for n, c in re.findall(
    r"\{n:\s*(\d+),\s*clave:\s*'([a-z_]+)'",
    NODOS["Decidir"]["parameters"]["jsCode"])]

fallos = []


def comprobar(etiqueta, ok, detalle=""):
    print(("  OK   " if ok else "  FALLO") + f" {etiqueta}" + (f"  {detalle}" if detalle else ""))
    if not ok:
        fallos.append(etiqueta)


def string_to_array(resuelto):
    """`stringToArray` de n8n: parte por comas, recorta, DESCARTA LOS VACIOS."""
    return [t for t in (x.strip() for x in resuelto.split(",")) if t != ""]


def parametros(nombre, ctx):
    """Los parametros que el nodo Postgres pasaria de verdad.

    `ctx` mapea el texto de cada expresion -tal cual esta en el workflow- a su
    valor. Si una expresion del nodo no esta en `ctx`, esto revienta: es
    deliberado, para que renombrar un campo en `Decidir` sin actualizar el nodo
    no pase inadvertido.
    """
    crudo = NODOS[nombre]["parameters"].get("options", {}).get("queryReplacement")
    if not crudo:
        return []
    assert crudo.startswith("="), crudo
    resuelto = re.sub(r"\{\{(.*?)\}\}",
                      lambda m: str(ctx[m.group(1).strip()]), crudo[1:])
    return string_to_array(resuelto)


def ejecutar(cur, nombre, ctx):
    consulta = NODOS[nombre]["parameters"]["query"]
    vals = parametros(nombre, ctx)
    # Cuantos `$N` referencia la consulta de verdad. Si no cuadra con los
    # parametros que n8n pasaria, Postgres dara `there is no parameter $N`: es
    # el fallo que se busca, asi que se deja fallar y se relata.
    referenciados = max((int(m) for m in re.findall(r"\$(\d+)", consulta)), default=0)
    if referenciados != len(vals):
        raise AssertionError(
            f"{nombre}: la consulta referencia ${referenciados} pero n8n pasaria "
            f"{len(vals)} parametros ({vals!r}). Postgres diria "
            f"'there is no parameter ${referenciados}'.")
    sql = re.sub(r"\$(\d+)", r"%(p\1)s", consulta)
    cur.execute(sql, {f"p{i + 1}": v for i, v in enumerate(vals)})
    r = cur.fetchone()
    return dict(zip([d.name for d in cur.description], r)) if r else None


# Los `ctx` de cada nodo. Las claves son el texto literal de las expresiones.
CHAT_EXPR = "$('Normalizar update').first().json.chat_id"


def ctx_chat():
    return {CHAT_EXPR: CHAT}


def ctx_guardar(clave, valor_cod, paso, paso_actual):
    return {CHAT_EXPR: CHAT, "$json.clave": clave, "$json.valor_cod": valor_cod,
            "$json.paso": paso, "$json.paso_actual": paso_actual}


def cod(texto):
    """La codificacion de `Decidir`: 'T' + base64. Nunca vacia, nunca con comas."""
    return "T" + base64.b64encode(texto.encode("utf-8")).decode("ascii")


NULO = "N"

with psycopg.connect(DSN, autocommit=True) as cx:
    cur = cx.cursor()
    cur.execute("TRUNCATE sesiones_paciente, cuestionarios, cuestionarios_iniciados,"
                " limite_paciente, consultas")

    print("\n0. el fallo bloqueante que costo esta ronda: no puede volver")
    # Asi mandaba `Decidir` el «Omitir» antes: cadena vacia para decir NULL.
    # `stringToArray` la descarta y la consulta sale con 4 parametros.
    try:
        ejecutar(cur, "Guardar respuesta", ctx_guardar("texto_libre", "", 8, 7))
        comprobar("un parametro vacio se detecta", False, "paso sin protestar")
    except AssertionError as e:
        comprobar("un parametro vacio se detecta antes de tocar Postgres",
                  "there is no parameter $5" in str(e), str(e)[:120])

    print("\n1. /start sin sesion previa")
    r = ejecutar(cur, "Leer sesion", ctx_chat())
    comprobar("Leer sesion da UNA fila aunque no haya sesion", r is not None, str(r))
    comprobar("existe=False, paso=0", r["existe"] is False and r["paso"] == 0)
    comprobar("paso vuelve como numero, no cadena", isinstance(r["paso"], int))
    r = ejecutar(cur, "Borrar sesion", ctx_chat())
    comprobar("Borrar sesion da UNA fila borrando 0", r is not None and r["borradas"] == 0, str(r))
    comprobar("no ha escrito nada (criterio 1 del §21)",
              cur.execute("SELECT count(*) FROM sesiones_paciente").fetchone()[0] == 0)

    print("\n2. «No acepto»: la rama no toca la base")
    total = sum(cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in
                ("sesiones_paciente", "cuestionarios", "cuestionarios_iniciados",
                 "limite_paciente", "consultas"))
    comprobar("cero filas en las cinco tablas", total == 0, f"total={total}")

    print("\n3. «Acepto»")
    r = ejecutar(cur, "Crear sesion", ctx_chat())
    comprobar("creada=1", r["creada"] == 1, str(r))
    comprobar("paso=1 y es numero", r["paso"] == 1 and isinstance(r["paso"], int))
    comprobar("cuestionarios_iniciados subio a 1", r["iniciados"] == 1)
    comprobar("consentido_en quedo puesto", cur.execute(
        "SELECT consentido_en IS NOT NULL FROM sesiones_paciente WHERE chat_id=%s",
        (CHAT,)).fetchone()[0])

    print("\n4. doble toque en «Acepto»: no reinicia el cuestionario")
    r2 = ejecutar(cur, "Crear sesion", ctx_chat())
    comprobar("creada=0 (ON CONFLICT DO NOTHING)", r2["creada"] == 0, str(r2))
    comprobar("cuestionarios_iniciados NO subio otra vez", cur.execute(
        "SELECT cuantos FROM cuestionarios_iniciados").fetchone()[0] == 1)

    print("\n5. las 6 respuestas de botones, cada una en su clave")
    valores = {"fiebre": "si", "tos": "con_flema", "dias_evolucion": "3_a_7",
               "disnea": "no", "dolor_toracico": "si", "asma": "no"}
    for n, clave in PREGUNTAS:
        if clave == "texto_libre":
            continue
        r = ejecutar(cur, "Guardar respuesta",
                     ctx_guardar(clave, cod(valores[clave]), n + 1, n))
        comprobar(f"p{n} -> {clave}", r is not None and r["paso"] == n + 1, str(r))
    resp = cur.execute("SELECT respuestas FROM sesiones_paciente WHERE chat_id=%s",
                       (CHAT,)).fetchone()[0]
    comprobar("respuestas == exactamente las 6 claves del §4.4", resp == valores,
              json.dumps(resp, ensure_ascii=False))

    print("\n6. doble toque en el MISMO boton (idempotencia del AND paso = $5)")
    r = ejecutar(cur, "Guardar respuesta", ctx_guardar("asma", cod("no"), 7, 6))
    comprobar("el segundo update no encuentra fila", r is None, str(r))
    comprobar("el paso sigue en 7", cur.execute(
        "SELECT paso FROM sesiones_paciente WHERE chat_id=%s", (CHAT,)).fetchone()[0] == 7)

    print("\n7. pregunta 7: texto libre CON COMAS, comillas y SQL")
    veneno = "me duele, mucho; ' OR 1=1 --  y \"tambien\" la espalda"
    r = ejecutar(cur, "Guardar respuesta", ctx_guardar("texto_libre", cod(veneno), 8, 7))
    comprobar("guardado, paso=8", r is not None and r["paso"] == 8, str(r))
    resp = cur.execute("SELECT respuestas FROM sesiones_paciente WHERE chat_id=%s",
                       (CHAT,)).fetchone()[0]
    comprobar("el texto llego INTACTO (comas incluidas)", resp["texto_libre"] == veneno,
              repr(resp["texto_libre"]))
    comprobar("las 6 respuestas siguen intactas",
              {k: v for k, v in resp.items() if k != "texto_libre"} == valores)

    print("\n8. Completar")
    r = ejecutar(cur, "Completar", ctx_chat())
    comprobar("nacio un codigo", bool(r["codigo"]), str(r))
    comprobar("6 caracteres del alfabeto del §5.2",
              len(r["codigo"]) == 6 and
              set(r["codigo"]) <= set("ABCDEFGHJKMNPQRSTUVWXYZ23456789"))
    comprobar("expira formateado dd/mm/aaaa",
              bool(re.fullmatch(r"\d{2}/\d{2}/\d{4}", r["expira"] or "")), r["expira"])
    comprobar("la sesion murio", r["borradas"] == 1 and cur.execute(
        "SELECT count(*) FROM sesiones_paciente").fetchone()[0] == 0)
    comprobar("limite_paciente subio a 1", r["completados_hoy"] == 1)
    guardado = cur.execute("SELECT respuestas, expira_en::date - creado_en::date"
                           " FROM cuestionarios").fetchone()
    comprobar("cuestionarios guarda las 7 respuestas", guardado[0] == dict(resp),
              json.dumps(guardado[0], ensure_ascii=False))
    comprobar("expira 7 dias despues (§5.4)", guardado[1] == 7, str(guardado[1]))

    print("\n9. «Omitir» guarda NULL, no la cadena 'omitir' -- el fallo bloqueante")
    cur.execute("TRUNCATE cuestionarios, limite_paciente")
    ejecutar(cur, "Crear sesion", ctx_chat())
    cur.execute("UPDATE sesiones_paciente SET paso=7 WHERE chat_id=%s", (CHAT,))
    r = ejecutar(cur, "Guardar respuesta", ctx_guardar("texto_libre", NULO, 8, 7))
    comprobar("«Omitir» se guarda y avanza al paso 8", r is not None and r["paso"] == 8, str(r))
    resp = cur.execute("SELECT respuestas FROM sesiones_paciente WHERE chat_id=%s",
                       (CHAT,)).fetchone()[0]
    comprobar("texto_libre es JSON null", "texto_libre" in resp and resp["texto_libre"] is None,
              json.dumps(resp, ensure_ascii=False))
    r = ejecutar(cur, "Completar", ctx_chat())
    comprobar("y el paciente recibe su codigo (esto es lo que estaba roto)",
              bool(r["codigo"]), str(r))
    comprobar("el cuestionario guardado lleva texto_libre null", cur.execute(
        "SELECT respuestas->'texto_libre' = 'null'::jsonb FROM cuestionarios").fetchone()[0])

    print("\n10. el limite de 5/dia del §4.2")
    for _ in range(4):
        ejecutar(cur, "Crear sesion", ctx_chat())
        cur.execute("UPDATE sesiones_paciente SET paso=8 WHERE chat_id=%s", (CHAT,))
        ejecutar(cur, "Completar", ctx_chat())
    n = cur.execute("SELECT cuantos FROM limite_paciente WHERE chat_id=%s",
                    (CHAT,)).fetchone()[0]
    comprobar("van 5 completados hoy", n == 5, str(n))
    r = ejecutar(cur, "Crear sesion", ctx_chat())
    comprobar("el 6º NO se crea", r["creada"] == 0, str(r))
    comprobar("y el flujo puede decir por que (completados_hoy>=5)", r["completados_hoy"] == 5)
    comprobar("no quedo sesion a medias", cur.execute(
        "SELECT count(*) FROM sesiones_paciente").fetchone()[0] == 0)
    comprobar("hay 5 cuestionarios con codigos DISTINTOS", cur.execute(
        "SELECT count(*) = count(DISTINCT codigo) AND count(*) = 5"
        " FROM cuestionarios").fetchone()[0])

    print("\n11. Completar sin sesion: no inventa nada")
    cur.execute("DELETE FROM limite_paciente")
    r = ejecutar(cur, "Completar", ctx_chat())
    comprobar("codigo NULL -> el flujo va a «Error al generar codigo»", r["codigo"] is None, str(r))
    comprobar("no inserto cuestionario de la nada", cur.execute(
        "SELECT count(*) FROM cuestionarios").fetchone()[0] == 5)
    comprobar("no toco el contador del limite", cur.execute(
        "SELECT count(*) FROM limite_paciente").fetchone()[0] == 0)

    print("\n12. el flujo NUNCA escribe en consultas (es del profesional)")
    comprobar("consultas sigue vacia", cur.execute(
        "SELECT count(*) FROM consultas").fetchone()[0] == 0)


# ---------------------------------------------------------------------------
# 13. DOS MENSAJES A LA VEZ EN EL PASO 8
#
# Necesita DOS conexiones de verdad, no dos llamadas seguidas: lo que se prueba
# es el cerrojo de fila de Postgres, y con una sola conexion las dos sentencias
# van en serie y no hay nada que probar.
#
# Medido antes del arreglo: dos cuestionarios, DOS codigos al mismo paciente y
# `limite_paciente` en 2, o sea dos de sus tres intentos diarios gastados por un
# doble toque. Y `cuestionarios_iniciados` se queda en 1, con lo que el panel
# del §16 ensena mas completados que iniciados, que es imposible y hace dudar
# de todo lo demas que ensena.
#
# El arreglo es que `ses` BORRE la sesion en vez de leerla: un
# `DELETE ... RETURNING` toma el cerrojo y solo una de las dos transacciones se
# lleva la fila.
# ---------------------------------------------------------------------------
print("\n13. dos mensajes a la vez en el paso 8 dan UN solo codigo")
CHAT_CARRERA = 999777001
_sql_completar = re.sub(r"\$(\d+)", lambda m: "%(p" + m.group(1) + ")s",
                        NODOS["Completar"]["parameters"]["query"])

with psycopg.connect(DSN, autocommit=True) as cx, cx.cursor() as cur:
    cur.execute("TRUNCATE sesiones_paciente, cuestionarios,"
                " cuestionarios_iniciados, limite_paciente, consultas")
    cur.execute("INSERT INTO sesiones_paciente (chat_id, paso, respuestas,"
                " consentido_en) VALUES (%s, 8, %s::jsonb, now())",
                (CHAT_CARRERA, json.dumps({"fiebre": "si", "tos": "seca"})))

_salidas, _errores, _cerrojo = [], [], threading.Lock()


def _un_mensaje():
    try:
        with psycopg.connect(DSN, autocommit=True) as c2, c2.cursor() as k:
            _barrera.wait()
            k.execute(_sql_completar, {"p1": CHAT_CARRERA})
            fila = k.fetchone()
            cols = [d.name for d in k.description]
        with _cerrojo:
            _salidas.append(dict(zip(cols, fila)) if fila else None)
    except Exception as exc:                              # noqa: BLE001
        with _cerrojo:
            _errores.append(f"{type(exc).__name__}: {exc}")


_barrera = threading.Barrier(2)
_hilos = [threading.Thread(target=_un_mensaje) for _ in range(2)]
for _h in _hilos:
    _h.start()
for _h in _hilos:
    _h.join()

comprobar("las dos consultas terminan sin reventar", not _errores,
          "; ".join(_errores)[:160])
with psycopg.connect(DSN, autocommit=True) as cx, cx.cursor() as cur:
    comprobar("se crea UN cuestionario, no dos", cur.execute(
        "SELECT count(*) FROM cuestionarios").fetchone()[0] == 1)
    comprobar("se gasta UN intento del limite diario, no dos", cur.execute(
        "SELECT coalesce(sum(cuantos), 0) FROM limite_paciente"
    ).fetchone()[0] == 1)
    comprobar("la sesion queda borrada", cur.execute(
        "SELECT count(*) FROM sesiones_paciente").fetchone()[0] == 0)
_codigos = [s["codigo"] for s in _salidas if s and s.get("codigo")]
comprobar("solo UNA de las dos entrega codigo", len(_codigos) == 1,
          str(_codigos))

print(f"\n{'TODO VERDE' if not fallos else 'FALLOS: ' + ', '.join(fallos)}")
sys.exit(1 if fallos else 0)
